"""Monitoreo del lector USB y captura en modo HID o puerto serie.

Realidad técnica de los lectores de código de barras
----------------------------------------------------
La mayoría de lectores USB se presentan ante Windows como un teclado HID. En
ese modo el sistema operativo no ofrece una API fiable para distinguir el
escáner de un teclado normal. Por eso la aplicación combina dos señales:

1. Enumeración de dispositivos USB/PNP por nombre de modelo o fabricante
   (Honeywell, Zebra, Datalogic, etc.).
2. Validación real mediante una lectura y la prueba de calibración.

Si el modelo es genérico, el estado inicial es «HID EN ESPERA» y pasa a
«CONECTADO»/«ACTIVO» cuando el operador escanea. Un lector serie, en cambio, sí
se puede detectar y desconectar de forma directa mediante su puerto COM.

El hilo de monitoreo nunca toca Tkinter: publica eventos en una cola que la
interfaz consume periódicamente.
"""

from __future__ import annotations

import json
import logging
import os
import queue
import re
import shutil
import subprocess
import threading
import time
from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from .modelos import ConfiguracionLector, EstadoLector
from .utilidades import ahora_utc

LOG = logging.getLogger(__name__)

EVENTO_ESTADO = "estado"
EVENTO_LECTURA = "lectura"

_PALABRAS_CLAVE = (
    "barcode",
    "bar code",
    "scanner",
    "escaner",
    "escáner",
    "symbol",
    "honeywell",
    "zebra",
    "datalogic",
    "opticon",
    "newline",
    "newland",
    "metrologic",
    "unitech",
    "argox",
    "cognex",
    "sick",
    "lector de codigo",
    "lector de código",
    "codigo de barras",
    "código de barras",
)
_EXCLUIR = ("tarjeta", "smartcard", "smart card", "usbccid", "ccid")


def _es_dispositivo_lector(nombre: str) -> bool:
    texto = (nombre or "").casefold()
    if not texto or any(palabra in texto for palabra in _EXCLUIR):
        return False
    return any(palabra.casefold() in texto for palabra in _PALABRAS_CLAVE)


def _comando_powershell() -> str:
    # Se filtra en PowerShell para no traer cientos de dispositivos cada ciclo.
    palabras = (
        "barcode|bar code|scanner|escaner|symbol|honeywell|zebra|datalogic|"
        "opticon|newline|newland|metrologic|unitech|argox|cognex|lector de codigo"
    )
    return (
        "$ErrorActionPreference='SilentlyContinue';"
        "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8;"
        f"$p='{palabras}';"
        "$d=@(Get-PnpDevice -PresentOnly | Where-Object {"
        " $_.Status -eq 'OK' -and \"$($_.FriendlyName)\" -match $p -and "
        "\"$($_.FriendlyName)\" -notmatch 'tarjeta|smartcard|smart card|usbccid|ccid'"
        "} | Select-Object FriendlyName,InstanceId,Class);"
        "$d | ConvertTo-Json -Compress"
    )


def _ruta_powershell() -> str | None:
    candidatos = ["powershell.exe", "pwsh.exe"]
    sistema = os.environ.get("SYSTEMROOT", r"C:\Windows")
    candidatos.extend(
        [
            str(
                Path(sistema)
                / "System32"
                / "WindowsPowerShell"
                / "v1.0"
                / "powershell.exe"
            ),
            str(
                Path(sistema)
                / "SysWOW64"
                / "WindowsPowerShell"
                / "v1.0"
                / "powershell.exe"
            ),
        ]
    )
    for candidato in candidatos:
        encontrado = shutil.which(candidato)
        if encontrado:
            return encontrado
        if os.path.isfile(candidato):
            return candidato
    return None


def detectar_lectores_hid() -> tuple[list[str], list[str], str | None]:
    """Devuelve nombres, identificadores y un mensaje de error opcional."""

    if os.name != "nt":
        return [], [], "La detección USB automática está disponible en Windows."
    ejecutable = _ruta_powershell()
    if not ejecutable:
        return [], [], (
            "No se encontró PowerShell para consultar dispositivos USB. "
            "La lectura y la calibración siguen funcionando."
        )
    comando = [
        ejecutable,
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        _comando_powershell(),
    ]
    try:
        resultado = subprocess.run(
            comando,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        LOG.warning("No se pudo consultar dispositivos USB: %s", exc)
        return [], [], "No fue posible consultar los dispositivos USB."
    if resultado.returncode != 0:
        LOG.warning("PowerShell devolvió error: %s", resultado.stderr.strip()[:300])
        return [], [], "Windows no respondió a la consulta de dispositivos USB."
    salida = (resultado.stdout or "").strip()
    if not salida or salida == "null":
        return [], [], None
    try:
        datos = json.loads(salida)
    except ValueError:
        LOG.warning("Respuesta USB no interpretable: %s", salida[:200])
        return [], [], "La consulta USB devolvió una respuesta inesperada."
    if isinstance(datos, dict):
        datos = [datos]
    if not isinstance(datos, list):
        return [], [], None
    nombres: list[str] = []
    ids: list[str] = []
    for item in datos:
        if not isinstance(item, dict):
            continue
        nombre = str(item.get("FriendlyName") or "").strip()
        if not nombre or not _es_dispositivo_lector(nombre):
            continue
        nombres.append(nombre)
        instancia = str(item.get("InstanceId") or "").strip()
        if instancia:
            ids.append(instancia)
    return sorted(set(nombres)), sorted(set(ids)), None


def puertos_seriales() -> list[tuple[str, str]]:
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    resultado: list[tuple[str, str]] = []
    try:
        for puerto in list_ports.comports():
            descripcion = " · ".join(
                parte
                for parte in (puerto.device, puerto.description)
                if parte and parte != "n/a"
            )
            resultado.append((puerto.device, descripcion))
    except Exception:
        LOG.debug("No se pudieron enumerar puertos serie", exc_info=True)
    return sorted(resultado, key=lambda p: p[0])


class ServicioLector:
    """Servicio de detección y lectura en segundo plano."""

    def __init__(
        self,
        configuracion: ConfiguracionLector,
        cola_eventos: queue.Queue[tuple[str, Any]] | None = None,
    ):
        self._configuracion = configuracion
        self.cola = cola_eventos or queue.Queue()
        self._estado = EstadoLector(
            estado="pendiente",
            modo=configuracion.modo,
            puerto=configuracion.puerto,
            detalle="Iniciando detección del lector USB…",
            actualizado_en=ahora_utc(),
        )
        self._lock = threading.RLock()
        self._detener = threading.Event()
        self._despertar = threading.Event()
        self._hilo: threading.Thread | None = None
        self._serial: Any = None
        self._buffer_serial = bytearray()
        self._ultimo_dato_serial = 0.0
        self._puertos: list[tuple[str, str]] = []
        self._hid_nombres: list[str] = []
        self._hid_ids: list[str] = []
        self._ultima_deteccion = 0.0
        self._ultima_publicacion = 0.0
        self._activo = False
        self._validado_por_lectura = False
        self._desconexion_detectada = False
        self._ultima_lectura: datetime | None = None
        self._detalle_error = ""

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------
    def iniciar(self) -> None:
        if self._hilo and self._hilo.is_alive():
            return
        self._detener.clear()
        self._hilo = threading.Thread(
            target=self._bucle,
            name="monitor-lector",
            daemon=True,
        )
        self._hilo.start()

    def detener(self) -> None:
        self._detener.set()
        self._despertar.set()
        self._cerrar_serial()
        hilo = self._hilo
        if hilo and hilo.is_alive():
            hilo.join(timeout=2.0)
        self._hilo = None

    def estado_actual(self) -> EstadoLector:
        with self._lock:
            return replace(
                self._estado,
                dispositivos=tuple(self._estado.dispositivos),
            )

    def reconfigurar(self, configuracion: ConfiguracionLector) -> None:
        with self._lock:
            self._configuracion = configuracion
            self._activo = False
            self._validado_por_lectura = False
            self._desconexion_detectada = False
            self._buffer_serial.clear()
            self._detalle_error = ""
            self._cerrar_serial_locked()
        self._despertar.set()
        self._publicar(force=True)

    def invalidar_calibracion(self, motivo: str = "") -> None:
        with self._lock:
            self._activo = False
        if motivo:
            self._detalle_error = motivo
        self._publicar(force=True)

    def marcar_activo(self, codigo_calibracion: str = "") -> None:
        with self._lock:
            self._activo = True
            self._validado_por_lectura = True
            self._desconexion_detectada = False
            self._detalle_error = ""
        self._publicar(force=True)
        LOG.info("Lector marcado como activo tras calibración")

    def notificar_lectura_hid(self, codigo: str) -> None:
        """Registra actividad HID; el teclado no expone un evento de conexión."""

        if self._configuracion.modo != "HID":
            return
        with self._lock:
            cambio = not self._validado_por_lectura
            self._validado_por_lectura = True
            self._desconexion_detectada = False
            self._ultima_lectura = ahora_utc()
            self._detalle_error = ""
        if cambio:
            self._publicar(force=True)
        else:
            self._publicar(force=False)

    def solicitar_redeteccion(self) -> None:
        self._ultima_deteccion = 0.0
        self._despertar.set()

    # ------------------------------------------------------------------
    # Publicación de estado
    # ------------------------------------------------------------------
    def _publicar(self, force: bool = False) -> None:
        ahora = time.monotonic()
        if not force and ahora - self._ultima_publicacion < 0.25:
            return
        estado = self._construir_estado()
        with self._lock:
            anterior = self._estado
            self._estado = estado
        self._ultima_publicacion = ahora
        if force or self._estado_distinto(anterior, estado):
            try:
                self.cola.put_nowait((EVENTO_ESTADO, estado))
            except queue.Full:
                LOG.debug("Cola de eventos del lector llena; se omite estado")

    @staticmethod
    def _estado_distinto(a: EstadoLector, b: EstadoLector) -> bool:
        return (
            a.estado != b.estado
            or a.detalle != b.detalle
            or a.dispositivos != b.dispositivos
            or a.modo != b.modo
            or a.puerto != b.puerto
            or a.identificado != b.identificado
            or a.validado_por_lectura != b.validado_por_lectura
        )

    def _construir_estado(self) -> EstadoLector:
        with self._lock:
            configuracion = self._configuracion
            activo = self._activo
            validado = self._validado_por_lectura
            desconexion = self._desconexion_detectada
            dispositivos = list(self._hid_nombres)
            puertos = list(self._puertos)
            error = self._detalle_error
            serial_abierto = bool(
                self._serial and getattr(self._serial, "is_open", False)
            )

        if configuracion.modo == "SERIAL":
            puerto = configuracion.puerto
            presente = any(p[0].casefold() == puerto.casefold() for p in puertos) if puerto else False
            if not puerto:
                return EstadoLector(
                    estado="desconectado",
                    modo="SERIAL",
                    puerto="",
                    detalle=(
                        "No hay un puerto COM configurado. El administrador debe "
                        "seleccionarlo en el panel de administración."
                    ),
                    dispositivos=tuple(p[1] for p in puertos),
                    actualizado_en=ahora_utc(),
                )
            if not presente:
                return EstadoLector(
                    estado="desconectado",
                    modo="SERIAL",
                    puerto=puerto,
                    detalle=(
                        f"El puerto {puerto} no está disponible. Verifica el cable "
                        "USB y vuelve a conectar el lector."
                    ),
                    dispositivos=tuple(p[1] for p in puertos),
                    actualizado_en=ahora_utc(),
                )
            if not serial_abierto:
                return EstadoLector(
                    estado="desconectado",
                    modo="SERIAL",
                    puerto=puerto,
                    detalle=error or f"El puerto {puerto} existe, pero aún no se pudo abrir.",
                    dispositivos=tuple(p[1] for p in puertos),
                    actualizado_en=ahora_utc(),
                )
            detalle = f"Lector serie en {puerto} · {configuracion.baudios} bps"
            if activo:
                detalle += " · calibrado y listo"
            return EstadoLector(
                estado="activo" if activo else "conectado",
                modo="SERIAL",
                puerto=puerto,
                detalle=detalle,
                dispositivos=tuple(p[1] for p in puertos),
                identificado=True,
                validado_por_lectura=activo,
                actualizado_en=ahora_utc(),
            )

        # Modo HID
        identificado = bool(dispositivos)
        if desconexion and not identificado and not validado:
            return EstadoLector(
                estado="desconectado",
                modo="HID",
                puerto="",
                detalle=(
                    "El lector USB detectado se desconectó. Vuelve a conectarlo "
                    "y escanea para validarlo."
                ),
                dispositivos=(),
                identificado=False,
                validado_por_lectura=False,
                actualizado_en=ahora_utc(),
            )
        if error and not identificado and not validado:
            detalle = error
        elif identificado:
            detalle = "Lector USB detectado: " + " / ".join(dispositivos[:2])
        elif validado:
            detalle = (
                "Lector USB HID validado por lectura. Windows no reporta un "
                "modelo específico, pero la captura funciona."
            )
        else:
            detalle = (
                "Conecta el lector USB y escanea un producto para detectarlo. "
                "Windows no distingue un lector HID genérico de un teclado."
            )
        if activo:
            detalle += " · calibración vigente"
        return EstadoLector(
            estado=("activo" if activo else "conectado" if (identificado or validado) else "pendiente"),
            modo="HID",
            puerto="",
            detalle=detalle,
            dispositivos=tuple(dispositivos),
            identificado=identificado,
            validado_por_lectura=validado,
            actualizado_en=ahora_utc(),
        )

    # ------------------------------------------------------------------
    # Hilo principal
    # ------------------------------------------------------------------
    def _bucle(self) -> None:
        self._publicar(force=True)
        while not self._detener.is_set():
            try:
                self._ciclo()
            except Exception:
                LOG.exception("Error inesperado en monitor del lector")
                time.sleep(1.0)
            self._despertar.wait(timeout=0.35)
            self._despertar.clear()

    def _ciclo(self) -> None:
        with self._lock:
            configuracion = self._configuracion
        if configuracion.modo == "SERIAL":
            self._ciclo_serial(configuracion)
        else:
            self._ciclo_hid()

    # ------------------------------------------------------------------
    # HID
    # ------------------------------------------------------------------
    def _ciclo_hid(self) -> None:
        ahora = time.monotonic()
        if ahora - self._ultima_deteccion >= 6.0:
            nombres, ids, error = detectar_lectores_hid()
            with self._lock:
                anteriores = set(self._hid_ids)
                self._hid_nombres = nombres
                self._hid_ids = ids
                self._ultima_deteccion = ahora
                if error:
                    self._detalle_error = error
                elif nombres:
                    self._detalle_error = ""
                # Si antes había un modelo identificado y ya no está, se
                # considera desconexión. Un HID genérico no se puede detectar
                # hasta que el operador escanea, por eso no se fuerza aquí.
                if anteriores and not set(ids):
                    self._activo = False
                    self._validado_por_lectura = False
                    self._desconexion_detectada = True
                if nombres:
                    self._desconexion_detectada = False
            self._publicar(force=True)
        self._publicar(force=False)

    # ------------------------------------------------------------------
    # Serie
    # ------------------------------------------------------------------
    def _ciclo_serial(self, configuracion: ConfiguracionLector) -> None:
        ahora = time.monotonic()
        if ahora - self._ultima_deteccion >= 3.0:
            self._puertos = puertos_seriales()
            self._ultima_deteccion = ahora
            con_puerto = [p for p in self._puertos if p[0].casefold() == configuracion.puerto.casefold()]
            if configuracion.puerto and not con_puerto:
                self._cerrar_serial()
                with self._lock:
                    self._activo = False
            self._publicar(force=True)
        if not configuracion.puerto:
            self._cerrar_serial()
            with self._lock:
                self._activo = False
            self._publicar(force=False)
            return
        if not any(p[0].casefold() == configuracion.puerto.casefold() for p in self._puertos):
            self._cerrar_serial()
            with self._lock:
                self._activo = False
            self._publicar(force=False)
            return
        if not self._serial or not getattr(self._serial, "is_open", False):
            if not self._abrir_serial(configuracion):
                self._publicar(force=False)
                return
            self._publicar(force=True)
        self._leer_serial()
        self._publicar(force=False)

    def _abrir_serial(self, configuracion: ConfiguracionLector) -> bool:
        try:
            import serial
        except ImportError:
            with self._lock:
                self._detalle_error = (
                    "Falta pyserial para leer el puerto serie. Instala las "
                    "dependencias de la aplicación."
                )
            return False
        try:
            conexion = serial.Serial(
                port=configuracion.puerto,
                baudrate=configuracion.baudios,
                timeout=0.18,
                write_timeout=0.5,
            )
            self._serial = conexion
            self._buffer_serial.clear()
            self._ultimo_dato_serial = time.monotonic()
            with self._lock:
                self._detalle_error = ""
            LOG.info(
                "Lector serie conectado en %s a %s bps",
                configuracion.puerto,
                configuracion.baudios,
            )
            return True
        except Exception as exc:
            with self._lock:
                self._detalle_error = (
                    f"No se pudo abrir {configuracion.puerto}. Puede estar en uso "
                    "por otra aplicación."
                )
            LOG.warning("Error abriendo puerto serie %s: %s", configuracion.puerto, exc)
            self._serial = None
            with self._lock:
                self._activo = False
            return False

    def _leer_serial(self) -> None:
        conexion = self._serial
        if not conexion:
            return
        try:
            cantidad = conexion.in_waiting
            datos = conexion.read(cantidad if cantidad > 0 else 1)
        except Exception as exc:
            LOG.warning("Lectura serie interrumpida: %s", exc)
            self._cerrar_serial()
            with self._lock:
                self._activo = False
                self._detalle_error = "Se perdió la comunicación con el lector serie."
            return
        if not datos:
            # Algunos lectores no envían salto de línea: se cierra por silencio.
            if self._buffer_serial and time.monotonic() - self._ultimo_dato_serial > 0.25:
                self._emitir_buffer_serial()
            return
        self._buffer_serial.extend(datos)
        self._ultimo_dato_serial = time.monotonic()
        if len(self._buffer_serial) > 256:
            self._buffer_serial.clear()
            return
        self._extraer_lineas_serial()

    def _extraer_lineas_serial(self) -> None:
        while True:
            indices = [
                i
                for i, byte in enumerate(self._buffer_serial)
                if byte in (0x0A, 0x0D)
            ]
            if not indices:
                return
            indice = indices[0]
            crudo = bytes(self._buffer_serial[:indice])
            del self._buffer_serial[: indice + 1]
            self._emitir_serial(crudo)

    def _emitir_buffer_serial(self) -> None:
        crudo = bytes(self._buffer_serial)
        self._buffer_serial.clear()
        self._emitir_serial(crudo)

    def _emitir_serial(self, crudo: bytes) -> None:
        # Se descartan bytes de control binario que no forman texto legible.
        codigo = crudo.decode("utf-8", errors="ignore").strip("\x00\r\n\t ")
        codigo = re.sub(r"[\x00-\x1f]", "", codigo).strip()
        if not codigo:
            return
        with self._lock:
            self._ultima_lectura = ahora_utc()
            self._validado_por_lectura = True
        try:
            self.cola.put_nowait((EVENTO_LECTURA, codigo))
        except queue.Full:
            LOG.warning("Cola del lector llena; lectura descartada")

    def _cerrar_serial(self) -> None:
        with self._lock:
            self._cerrar_serial_locked()

    def _cerrar_serial_locked(self) -> None:
        conexion = self._serial
        self._serial = None
        self._buffer_serial.clear()
        if conexion is not None:
            try:
                conexion.close()
            except Exception:
                pass


def configuracion_desde_ajustes(
    obtener: Any, por_defecto: ConfiguracionLector | None = None
) -> ConfiguracionLector:
    """Construye la configuración guardada, tolerando valores inválidos."""

    base = por_defecto or ConfiguracionLector()
    modo = str(obtener("lector_modo", base.modo) or base.modo).upper()
    if modo not in {"HID", "SERIAL"}:
        modo = "HID"
    puerto = str(obtener("lector_puerto", base.puerto) or "").strip()
    try:
        baudios = int(str(obtener("lector_baudios", base.baudios) or base.baudios))
    except (TypeError, ValueError):
        baudios = base.baudios
    if baudios not in {1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200}:
        baudios = 9600
    return ConfiguracionLector(modo=modo, puerto=puerto, baudios=baudios)  # type: ignore[arg-type]


def nombres_dispositivos(estado: EstadoLector) -> Iterable[str]:
    return estado.dispositivos
