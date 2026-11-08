"""Lógica de autenticación, administración de accesos e inventario."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from .archivo_maestro import (
    ArchivoMaestro,
    ErrorArchivoMaestro,
    cargar_instantanea,
    formatear_cantidad,
    guardar_instantanea,
    normalizar_codigo_barras,
)
from .base_datos import BaseDatos, ErrorBaseDatos, ErrorCodigo
from .config import RutasApp
from .modelos import (
    Administrador,
    ArchivoGenerado,
    CodigoAcceso,
    EstadisticasSesion,
    ResultadoAutorizacion,
    ResultadoEscaneo,
    Sesion,
    SesionOperador,
)
from .seguridad import (
    ErrorSeguridad,
    formatear_codigo_acceso,
    generar_codigo_acceso,
    hash_clave,
    huella_codigo_acceso,
    normalizar_codigo_acceso,
    pista_codigo,
    validar_fortaleza_clave,
    verificar_clave,
)
from .utilidades import (
    ErrorValidacion,
    a_iso,
    ahora_utc,
    desde_iso,
    formatear_hora,
    limpiar_espacios,
    nombre_coincide,
    normalizar_cedula,
    normalizar_correo,
    normalizar_nombre,
    validar_cedula,
    validar_codigo_acceso_ingresado,
    validar_correo,
    validar_nombre,
)

LOG = logging.getLogger(__name__)


class ErrorAutenticacion(RuntimeError):
    """Credenciales no válidas o acceso no disponible."""


class ErrorAdministracion(RuntimeError):
    """Operación administrativa no permitida."""


class ErrorInventario(RuntimeError):
    """Operación inválida sobre la sesión de inventario."""


@dataclass(frozen=True)
class CodigoEmitido:
    codigo: str
    codigo_id: int
    expira_en: datetime
    asignado_a: str
    tipo: Literal["invitacion", "asignado", "renovacion"]


def _texto_fecha(valor: Any) -> datetime | None:
    return desde_iso(valor) if valor else None


def _sesion_operador_desde(
    operador: dict[str, Any], codigo: dict[str, Any]
) -> SesionOperador:
    return SesionOperador(
        operador_id=int(operador["id"]),
        nombre=str(operador["nombre"]),
        cedula=str(operador["cedula"]),
        correo=str(operador["correo"]),
        codigo_id=int(codigo["id"]),
        acceso_expira_en=_texto_fecha(codigo.get("expira_en")),
        iniciada_en=ahora_utc(),
    )


class ServicioAutenticacion:
    """Registro, ingreso y autorización de cierre."""

    def __init__(self, db: BaseDatos):
        self.db = db

    # ------------------------------------------------------------------
    # Administrador inicial
    # ------------------------------------------------------------------
    def requiere_configuracion(self) -> bool:
        return not self.db.hay_administrador()

    def crear_administrador_inicial(
        self,
        *,
        nombre: str,
        cedula: str,
        correo: str,
        clave: str,
        confirmacion: str,
    ) -> Administrador:
        if self.db.hay_administrador():
            raise ErrorAutenticacion(
                "La aplicación ya tiene un administrador configurado."
            )
        nombre = validar_nombre(nombre, "nombre del administrador")
        cedula = validar_cedula(cedula)
        correo = validar_correo(correo)
        errores = validar_fortaleza_clave(clave)
        if errores:
            raise ErrorValidacion("\n".join(errores))
        if clave != confirmacion:
            raise ErrorValidacion("Las dos claves de administración no coinciden.")
        try:
            clave_hash = hash_clave(clave)
        except ErrorSeguridad as exc:
            raise ErrorAutenticacion(str(exc)) from exc
        admin = self.db.crear_administrador(nombre, cedula, correo, clave_hash)
        LOG.info("Administrador inicial creado (cédula %s)", cedula)
        return admin

    def autenticar_administrador(
        self, cedula: str, clave: str
    ) -> Administrador:
        cedula = normalizar_cedula(cedula)
        registro = self.db.administrador_por_cedula(cedula)
        if not registro or not verificar_clave(clave, registro["clave_hash"]):
            raise ErrorAutenticacion(
                "Cédula o clave de administración incorrecta."
            )
        return Administrador(
            id=int(registro["id"]),
            nombre=str(registro["nombre"]),
            cedula=str(registro["cedula"]),
            correo=str(registro["correo"]),
            creado_en=_texto_fecha(registro["creado_en"]),
        )

    def cambiar_clave_administrador(
        self, admin_id: int, clave_actual: str, clave_nueva: str, confirmacion: str
    ) -> None:
        registro = self.db.administrador_por_id(admin_id)
        if registro is None:
            raise ErrorAutenticacion("El administrador ya no está activo.")
        datos = self.db.administrador_por_cedula(registro.cedula)
        if not datos or not verificar_clave(clave_actual, datos["clave_hash"]):
            raise ErrorAutenticacion("La clave actual no es correcta.")
        errores = validar_fortaleza_clave(clave_nueva)
        if errores:
            raise ErrorValidacion("\n".join(errores))
        if clave_nueva != confirmacion:
            raise ErrorValidacion("Las dos claves nuevas no coinciden.")
        if clave_nueva == clave_actual:
            raise ErrorValidacion("La clave nueva debe ser diferente a la actual.")
        self.db.actualizar_clave_administrador(admin_id, hash_clave(clave_nueva))
        LOG.info("Clave de administrador actualizada (id %s)", admin_id)

    # ------------------------------------------------------------------
    # Operadores
    # ------------------------------------------------------------------
    def registrar_operador(
        self,
        *,
        nombre: str,
        cedula: str,
        correo: str,
        codigo: str,
    ) -> SesionOperador:
        nombre = validar_nombre(nombre)
        cedula = validar_cedula(cedula)
        correo = validar_correo(correo)
        try:
            codigo_limpio = validar_codigo_acceso_ingresado(codigo)
        except ErrorValidacion as exc:
            raise ErrorAutenticacion(str(exc)) from exc

        huella = huella_codigo_acceso(codigo_limpio)
        acceso = self.db.codigo_por_huella(huella)
        if acceso is None:
            raise ErrorAutenticacion(
                "El código de acceso no existe. Verifica que lo hayas "
                "copiado completo o solicita uno nuevo al administrador."
            )
        if not verificar_clave(codigo_limpio, acceso["codigo_hash"]):
            raise ErrorAutenticacion(
                "El código de acceso no es válido. Solicita uno nuevo al "
                "administrador."
            )
        if acceso["estado"] == "revocado":
            raise ErrorAutenticacion(
                "Este código fue revocado por el administrador. Solicita uno nuevo."
            )
        if acceso["estado"] == "activo":
            raise ErrorAutenticacion(
                "Este código ya fue activado. Ingresa desde la pestaña "
                "«Ingresar» con tu cédula y el mismo código."
            )
        expira = desde_iso(acceso["expira_en"])
        if expira is None or expira <= ahora_utc():
            raise ErrorAutenticacion(
                "Este código de acceso venció. Solicita uno nuevo al administrador."
            )

        cedula_asignada = acceso.get("cedula_asignada")
        if cedula_asignada and normalizar_cedula(str(cedula_asignada)) != cedula:
            raise ErrorAutenticacion(
                "Este código fue asignado a otra cédula. Usa los datos "
                "entregados por el administrador."
            )
        nombre_asignado = acceso.get("nombre_asignado")
        if nombre_asignado and not nombre_coincide(nombre, str(nombre_asignado)):
            raise ErrorAutenticacion(
                "El nombre no coincide con el que registró el administrador "
                "para este código."
            )
        correo_asignado = acceso.get("correo_asignado")
        if correo_asignado and normalizar_correo(str(correo_asignado)) != correo:
            raise ErrorAutenticacion(
                "El correo no coincide con el que registró el administrador "
                "para este código."
            )

        existente = self.db.operador_por_cedula(cedula)
        if existente is not None:
            raise ErrorAutenticacion(
                "Ya existe un operador con esta cédula. Pide al administrador "
                "un código de renovación o inicia sesión con tu código vigente."
            )

        try:
            operador, codigo_actualizado = self.db.canjear_codigo(
                codigo_id=int(acceso["id"]),
                nombre=nombre,
                cedula=cedula,
                correo=correo,
                ahora=a_iso(ahora_utc()) or "",
            )
        except ErrorCodigo as exc:
            raise ErrorAutenticacion(str(exc)) from exc
        except ErrorBaseDatos as exc:
            raise ErrorAutenticacion(str(exc)) from exc

        LOG.info("Operador registrado con código (id %s)", operador["id"])
        return _sesion_operador_desde(operador, codigo_actualizado)

    def iniciar_sesion_operador(self, cedula: str, codigo: str) -> SesionOperador:
        cedula = normalizar_cedula(cedula)
        try:
            codigo_limpio = validar_codigo_acceso_ingresado(codigo)
        except ErrorValidacion as exc:
            raise ErrorAutenticacion(str(exc)) from exc
        huella = huella_codigo_acceso(codigo_limpio)
        acceso = self.db.codigo_por_huella(huella)
        generico = ErrorAutenticacion(
            "Cédula o código de acceso incorrectos. Verifica los datos e intenta "
            "de nuevo."
        )
        if acceso is None or not verificar_clave(codigo_limpio, acceso["codigo_hash"]):
            raise generico
        if acceso["estado"] == "revocado":
            raise ErrorAutenticacion(
                "Tu código de acceso fue revocado. Solicita uno nuevo al "
                "administrador."
            )
        if acceso["estado"] != "activo":
            raise ErrorAutenticacion(
                "Este código aún no está activo. Regístrate primero desde la "
                "pestaña «Crear cuenta»."
            )
        operador = self.db.operador_por_cedula(cedula)
        if (
            operador is None
            or not operador.activo
            or int(acceso["operador_id"] or 0) != operador.id
        ):
            raise generico
        expira = desde_iso(acceso["expira_en"])
        if expira is None or expira <= ahora_utc():
            raise ErrorAutenticacion(
                "Tu código de acceso venció. Solicita una renovación al "
                "administrador."
            )
        self.db.registrar_uso_codigo(int(acceso["id"]))
        LOG.info("Ingreso de operador (id %s)", operador.id)
        return _sesion_operador_desde(
            {
                "id": operador.id,
                "nombre": operador.nombre,
                "cedula": operador.cedula,
                "correo": operador.correo,
            },
            acceso,
        )

    def sesion_operador_vigente(self, sesion: SesionOperador) -> bool:
        codigo = self.db.codigo_por_id(sesion.codigo_id)
        if not codigo or codigo["estado"] != "activo":
            return False
        if int(codigo["operador_id"] or 0) != sesion.operador_id:
            return False
        expira = desde_iso(codigo["expira_en"])
        return bool(expira and expira > ahora_utc())

    def autorizar_cierre(
        self,
        sesion: SesionOperador,
        *,
        nombre_confirmado: str,
        clave: str,
    ) -> ResultadoAutorizacion:
        """Acepta la clave vigente del operador o, como excepción, la del admin."""

        nombre_confirmado = normalizar_nombre(nombre_confirmado)
        if not nombre_confirmado or not nombre_coincide(
            nombre_confirmado, sesion.nombre
        ):
            raise ErrorAutenticacion(
                "El nombre del operador no coincide con la sesión activa."
            )
        if not clave:
            raise ErrorAutenticacion("Escribe la clave de autorización.")

        try:
            codigo_limpio = validar_codigo_acceso_ingresado(clave)
        except ErrorValidacion:
            codigo_limpio = ""
        if codigo_limpio:
            huella = huella_codigo_acceso(codigo_limpio)
            acceso = self.db.codigo_por_huella(huella)
            if acceso and verificar_clave(codigo_limpio, acceso["codigo_hash"]):
                expira = desde_iso(acceso["expira_en"])
                if (
                    acceso["estado"] == "activo"
                    and int(acceso["operador_id"] or 0) == sesion.operador_id
                    and expira is not None
                    and expira > ahora_utc()
                ):
                    return ResultadoAutorizacion(
                        metodo="operador",
                        descripcion=f"Clave de {sesion.nombre}",
                    )

        # Clave de administrador: se verifica contra los administradores activos.
        for admin in self.db.administradores_activos():
            if verificar_clave(clave, admin["clave_hash"]):
                return ResultadoAutorizacion(
                    metodo="administrador",
                    descripcion=f"Autorización de administración · {admin['nombre']}",
                )
        raise ErrorAutenticacion(
            "La clave de autorización no es válida o ya venció. Usa tu código "
            "de acceso vigente o solicita autorización al administrador."
        )


class ServicioAdministracion:
    """Emisión, revocación y consulta de accesos."""

    def __init__(self, db: BaseDatos):
        self.db = db

    def listar_codigos(self) -> list[CodigoAcceso]:
        resultado: list[CodigoAcceso] = []
        for fila in self.db.listar_codigos():
            resultado.append(self._codigo_desde(fila))
        return resultado

    def listar_operadores(self) -> list[dict[str, Any]]:
        return self.db.listar_operadores()

    def _codigo_desde(self, fila: dict[str, Any]) -> CodigoAcceso:
        return CodigoAcceso(
            id=int(fila["id"]),
            pista=str(fila["pista"]),
            estado=str(fila["estado"]),
            operador_id=int(fila["operador_id"]) if fila.get("operador_id") else None,
            operador_nombre=fila.get("operador_nombre_actual"),
            nombre_asignado=fila.get("nombre_asignado"),
            cedula_asignada=fila.get("cedula_asignada"),
            correo_asignado=fila.get("correo_asignado"),
            creado_en=_texto_fecha(fila.get("creado_en")),
            expira_en=_texto_fecha(fila.get("expira_en")),
            activado_en=_texto_fecha(fila.get("activado_en")),
            revocado_en=_texto_fecha(fila.get("revocado_en")),
            ultimo_uso_en=_texto_fecha(fila.get("ultimo_uso_en")),
            usos=int(fila.get("usos", 0)),
            emitido_por_nombre=fila.get("emitido_por_nombre"),
        )

    def emitir_codigo(
        self,
        *,
        admin: Administrador,
        dias_vigencia: int,
        operador_id: int | None = None,
        nombre: str | None = None,
        cedula: str | None = None,
        correo: str | None = None,
    ) -> CodigoEmitido:
        """Emite una invitación libre, una invitación asignada o una renovación."""

        try:
            dias = int(dias_vigencia)
        except (TypeError, ValueError) as exc:
            raise ErrorValidacion("La vigencia debe ser un número de días.") from exc
        if dias < 1 or dias > 365:
            raise ErrorValidacion("La vigencia debe estar entre 1 y 365 días.")

        ahora = ahora_utc()
        expira = ahora + timedelta(days=dias)
        asignado_a = ""
        nombre_asignado: str | None = None
        cedula_asignada: str | None = None
        correo_asignado: str | None = None
        estado = "pendiente"
        tipo: Literal["invitacion", "asignado", "renovacion"] = "invitacion"

        if operador_id is not None:
            operador = self.db.operador_por_id(operador_id)
            if operador is None:
                raise ErrorAdministracion("El operador seleccionado no existe.")
            asignado_a = operador.nombre
            nombre_asignado = operador.nombre
            cedula_asignada = operador.cedula
            correo_asignado = operador.correo
            estado = "activo"
            tipo = "renovacion"
        elif nombre or cedula or correo:
            if not (nombre and cedula and correo):
                raise ErrorValidacion(
                    "Para asignar el código debes indicar nombre, cédula y correo, "
                    "o dejar los tres campos vacíos para una invitación libre."
                )
            nombre_asignado = validar_nombre(nombre, "nombre del operador")
            cedula_asignada = validar_cedula(cedula)
            correo_asignado = validar_correo(correo)
            existente = self.db.operador_por_cedula(cedula_asignada)
            if existente:
                raise ErrorValidacion(
                    "Esa cédula ya pertenece a un operador. Selecciona "
                    "«Renovar operador existente» para emitir su nuevo acceso."
                )
            asignado_a = f"{nombre_asignado} · {cedula_asignada}"
            tipo = "asignado"

        codigo = ""
        for intento in range(1, 12):
            candidato = generar_codigo_acceso()
            huella = huella_codigo_acceso(candidato)
            if self.db.codigo_por_huella(huella) is None:
                codigo = candidato
                break
            LOG.warning("Colisión de huella de código (intento %s)", intento)
        if not codigo:
            raise ErrorAdministracion(
                "No fue posible generar un código único. Intenta de nuevo."
            )

        codigo_normalizado = normalizar_codigo_acceso(codigo)
        codigo_hash = hash_clave(codigo_normalizado)
        codigo_id = self.db.crear_codigo_acceso(
            huella=huella_codigo_acceso(codigo_normalizado),
            codigo_hash=codigo_hash,
            pista=pista_codigo(codigo),
            estado=estado,
            operador_id=operador_id,
            nombre_asignado=nombre_asignado,
            cedula_asignada=cedula_asignada,
            correo_asignado=correo_asignado,
            emitido_por=admin.id,
            creado_en=a_iso(ahora) or "",
            expira_en=a_iso(expira) or "",
        )
        if operador_id is not None:
            self.db.revocar_codigos_operador(
                operador_id, admin.id, excepto_id=codigo_id
            )
        LOG.info(
            "Código emitido por admin %s (id %s, tipo %s)",
            admin.cedula,
            codigo_id,
            tipo,
        )
        return CodigoEmitido(
            codigo=formatear_codigo_acceso(codigo),
            codigo_id=codigo_id,
            expira_en=expira,
            asignado_a=asignado_a or "Invitación libre",
            tipo=tipo,
        )

    def revocar_codigo(self, admin: Administrador, codigo_id: int) -> bool:
        codigo = self.db.codigo_por_id(codigo_id)
        if not codigo:
            raise ErrorAdministracion("El código seleccionado no existe.")
        if codigo["estado"] == "revocado":
            return False
        revocado = self.db.revocar_codigo(codigo_id, admin.id)
        if revocado:
            LOG.info("Código %s revocado por admin %s", codigo_id, admin.cedula)
        return revocado

    def revocar_operador(self, admin: Administrador, operador_id: int) -> int:
        operador = self.db.operador_por_id(operador_id)
        if operador is None:
            raise ErrorAdministracion("El operador seleccionado no existe.")
        cantidad = self.db.revocar_codigos_operador(operador_id, admin.id)
        LOG.info(
            "Accesos revocados del operador %s (%s códigos)",
            operador.cedula,
            cantidad,
        )
        return cantidad

    def crear_respaldo(self, carpeta: str | Path) -> Path:
        return self.db.respaldar_en(carpeta)


class ServicioInventario:
    """Sesiones de conteo y registro de productos."""

    def __init__(self, db: BaseDatos, rutas: RutasApp):
        self.db = db
        self.rutas = rutas

    # ------------------------------------------------------------------
    # Sesiones
    # ------------------------------------------------------------------
    def sesion_abierta(self, operador_id: int) -> Sesion | None:
        return self.db.sesion_abierta_operador(operador_id)

    def iniciar_sesion(
        self,
        operador: SesionOperador,
        maestro: ArchivoMaestro,
        codigo_calibracion: str,
    ) -> Sesion:
        if self.db.sesion_abierta_operador(operador.operador_id):
            raise ErrorInventario(
                "Ya tienes una sesión abierta. Reábrela para continuar."
            )
        if maestro.buscar(codigo_calibracion) is None:
            raise ErrorInventario(
                "La calibración ya no coincide con el archivo maestro. "
                "Realiza de nuevo la prueba de sincronización."
            )
        ahora = a_iso(ahora_utc()) or ""
        try:
            sesion_id = self.db.crear_sesion(
                operador=operador,
                maestro_nombre=maestro.nombre,
                maestro_ruta=str(maestro.ruta),
                maestro_hash=maestro.huella,
                instantanea_ruta=None,
                calibracion_codigo=limpiar_espacios(codigo_calibracion),
                ahora=ahora,
            )
        except ErrorBaseDatos as exc:
            raise ErrorInventario(str(exc)) from exc

        ruta_instantanea = self.rutas.instantaneas / f"sesion_{sesion_id}.json"
        try:
            guardar_instantanea(maestro, ruta_instantanea)
            self.db.actualizar_instantanea(sesion_id, str(ruta_instantanea))
        except (ErrorArchivoMaestro, ErrorBaseDatos) as exc:
            self.db.archivar_sesion_incompleta(sesion_id)
            try:
                ruta_instantanea.unlink(missing_ok=True)
            except OSError:
                pass
            raise ErrorInventario(
                "No se pudo preparar la copia de seguridad del catálogo para "
                f"la sesión: {exc}"
            ) from exc
        sesion = self.db.sesion_por_id(sesion_id)
        if sesion is None:
            raise ErrorInventario("No fue posible recuperar la sesión creada.")
        LOG.info(
            "Sesión %s iniciada por operador %s",
            sesion_id,
            operador.cedula,
        )
        return sesion

    def cargar_maestro_sesion(self, sesion: Sesion) -> ArchivoMaestro:
        if not sesion.instantanea_ruta:
            raise ErrorInventario(
                "La sesión no tiene una copia del catálogo y no puede reanudarse "
                "de forma segura."
            )
        return cargar_instantanea(sesion.instantanea_ruta)

    def estadisticas(self, sesion_id: int) -> EstadisticasSesion:
        return self.db.estadisticas_sesion(sesion_id)

    def registros_sesion(self, sesion_id: int) -> list[Any]:
        return self.db.listar_registros(sesion_id)

    def obtener_sesion(self, sesion_id: int) -> Sesion | None:
        return self.db.sesion_por_id(sesion_id)

    # ------------------------------------------------------------------
    # Lecturas
    # ------------------------------------------------------------------
    def procesar_escaneo(
        self,
        sesion: Sesion,
        maestro: ArchivoMaestro,
        codigo_ingresado: str,
    ) -> ResultadoEscaneo:
        if not sesion.abierta:
            raise ErrorInventario("La sesión ya fue finalizada.")
        texto = limpiar_espacios(codigo_ingresado)
        if not texto:
            return ResultadoEscaneo(
                estado="vacio",
                mensaje="Escanea un código de barras.",
                codigo="",
                estadisticas=self.estadisticas(sesion.id),
            )
        if len(texto) > 200:
            texto = texto[:200]
        clave = normalizar_codigo_barras(texto)
        if not clave:
            return ResultadoEscaneo(
                estado="vacio",
                mensaje="La lectura no contiene un código válido.",
                codigo=texto,
                estadisticas=self.estadisticas(sesion.id),
            )
        if maestro.huella != sesion.maestro_hash:
            raise ErrorInventario(
                "El catálogo cargado no corresponde al de esta sesión. "
                "Vuelve a abrir la sesión para conservar la consistencia."
            )

        ahora = a_iso(ahora_utc()) or ""
        producto = maestro.buscar(texto)
        if producto is None:
            self.db.registrar_lectura(
                sesion_id=sesion.id,
                codigo_ingresado=texto,
                codigo_clave=clave,
                resultado="no_encontrado",
                creado_en=ahora,
            )
            descripcion_baja = maestro.inactivos.get(clave)
            if descripcion_baja:
                mensaje = (
                    f"Producto dado de baja: «{descripcion_baja}». "
                    "No se registra en el inventario."
                )
                LOG.info("Lectura de producto inactivo en sesión %s", sesion.id)
            else:
                mensaje = f"Código no encontrado en el archivo maestro: {texto}"
                LOG.info("Lectura no encontrada en sesión %s", sesion.id)
            return ResultadoEscaneo(
                estado="no_encontrado",
                mensaje=mensaje,
                codigo=texto,
                codigo_clave=clave,
                estadisticas=self.estadisticas(sesion.id),
            )

        existente = self.db.obtener_registro_por_clave(sesion.id, clave)
        if existente is not None:
            self.db.registrar_lectura(
                sesion_id=sesion.id,
                codigo_ingresado=texto,
                codigo_clave=clave,
                resultado="duplicado",
                producto_codigo=producto.codigo,
                descripcion=producto.descripcion,
                datos=producto.campos,
                creado_en=ahora,
            )
            return ResultadoEscaneo(
                estado="duplicado",
                mensaje=(
                    f"Producto duplicado: «{producto.descripcion}» ya fue "
                    f"registrado a las {formatear_hora(existente.escaneado_en)}."
                ),
                codigo=texto,
                codigo_clave=clave,
                registro_existente=existente,
                campos=producto.campos,
                estadisticas=self.estadisticas(sesion.id),
            )

        _, registro = self.db.registrar_lectura(
            sesion_id=sesion.id,
            codigo_ingresado=texto,
            codigo_clave=clave,
            resultado="registrado",
            producto_codigo=producto.codigo,
            descripcion=producto.descripcion,
            datos=producto.campos,
            creado_en=ahora,
        )
        return ResultadoEscaneo(
            estado="registrado",
            mensaje=f"Producto registrado: {producto.descripcion}",
            codigo=texto,
            codigo_clave=clave,
            registro=registro,
            campos=producto.campos,
            estadisticas=self.estadisticas(sesion.id),
        )

    def deshacer_ultimo(self, sesion: Sesion) -> Any | None:
        if not sesion.abierta:
            raise ErrorInventario("La sesión ya fue finalizada.")
        return self.db.deshacer_ultimo(sesion.id)

    def registrar_manual(
        self,
        *,
        sesion: Sesion,
        maestro: ArchivoMaestro,
        operador: SesionOperador,
        codigo: str,
        descripcion: str,
        novedad: str,
        stock: float | None = None,
    ) -> Any:
        """Registra un producto sin lectura del lector.

        Se usa cuando el código no se puede leer o no existe en el maestro. El
        registro queda marcado como ``manual`` y la novedad se conserva en la
        sesión y en los archivos de salida.
        """

        if not sesion.abierta:
            raise ErrorInventario("La sesión ya fue finalizada.")
        codigo = str(codigo or "").strip()
        descripcion = str(descripcion or "").strip()
        novedad = str(novedad or "").strip()
        if not codigo:
            raise ErrorInventario("Escribe el código del producto.")
        if len(codigo) > 200:
            raise ErrorInventario("El código es demasiado largo.")
        if not descripcion:
            raise ErrorInventario("Escribe la descripción del producto.")
        if len(descripcion) > 300:
            raise ErrorInventario("La descripción no puede superar 300 caracteres.")
        if not novedad:
            raise ErrorInventario(
                "Escribe la novedad: por qué se registra manualmente."
            )
        clave = normalizar_codigo_barras(codigo)
        if not clave:
            raise ErrorInventario("El código no es válido.")
        if clave in maestro.inactivos:
            raise ErrorInventario(
                "Ese producto está dado de baja en el catálogo y no se puede registrar."
            )
        if self.db.obtener_registro_por_clave(sesion.id, clave) is not None:
            raise ErrorInventario("Ese producto ya está registrado en la sesión.")
        if stock is not None:
            if not maestro.columna_stock:
                raise ErrorInventario(
                    "El archivo maestro no tiene una columna de stock reconocida."
                )
            if stock < 0:
                raise ErrorInventario("El stock contado no puede ser negativo.")

        producto = maestro.buscar(codigo)
        if producto is not None:
            campos = dict(producto.campos)
            descripcion = producto.descripcion
        else:
            campos = {columna: "" for columna in maestro.columnas}
        campos[maestro.columna_codigo] = codigo
        campos[maestro.columna_descripcion] = descripcion
        if stock is not None and maestro.columna_stock:
            campos[maestro.columna_stock] = formatear_cantidad(stock)

        ahora = a_iso(ahora_utc()) or ""
        try:
            _, registro = self.db.registrar_lectura(
                sesion_id=sesion.id,
                codigo_ingresado=codigo,
                codigo_clave=clave,
                resultado="registrado",
                producto_codigo=codigo,
                descripcion=descripcion,
                datos=campos,
                creado_en=ahora,
                operador_nombre=operador.nombre,
                operador_cedula=operador.cedula,
                origen="manual",
                novedad=novedad,
            )
        except ErrorBaseDatos as exc:
            raise ErrorInventario(str(exc)) from exc
        if registro is None:
            raise ErrorInventario("No se pudo crear el registro manual.")
        LOG.info(
            "Registro manual en sesión %s: %s (%s)",
            sesion.id,
            codigo,
            operador.cedula,
        )
        if stock is not None:
            return self.ajustar_stock(
                sesion=sesion,
                maestro=maestro,
                registro=registro,
                stock_nuevo=stock,
                operador=operador,
            )
        return self.db.obtener_registro_por_clave(sesion.id, clave) or registro

    def ajustar_stock(
        self,
        *,
        sesion: Sesion,
        maestro: ArchivoMaestro,
        registro: Any,
        stock_nuevo: float,
        operador: SesionOperador,
    ) -> Any:
        if not sesion.abierta:
            raise ErrorInventario("La sesión ya fue finalizada.")
        columna = maestro.columna_stock
        if not columna:
            raise ErrorInventario(
                "El archivo maestro no tiene una columna de stock reconocida."
            )
        try:
            nuevo = float(stock_nuevo)
        except (TypeError, ValueError) as exc:
            raise ErrorInventario("El stock contado debe ser un número.") from exc
        if not (nuevo == nuevo) or nuevo in {float("inf"), float("-inf")}:
            raise ErrorInventario("El stock contado no es un número válido.")
        if nuevo < 0:
            raise ErrorInventario("El stock contado no puede ser negativo.")
        if registro is None or registro.sesion_id != sesion.id:
            raise ErrorInventario("El registro no pertenece a la sesión activa.")
        from .archivo_maestro import convertir_numero

        original = convertir_numero(registro.campos.get(columna, ""))
        diferencia = (nuevo - original) if original is not None else None
        try:
            self.db.guardar_ajuste_stock(
                sesion_id=sesion.id,
                registro_id=registro.id,
                codigo=registro.codigo,
                stock_original=original,
                stock_nuevo=nuevo,
                diferencia=diferencia,
                operador_nombre=operador.nombre,
                operador_cedula=operador.cedula,
            )
        except ErrorBaseDatos as exc:
            raise ErrorInventario(str(exc)) from exc
        actualizado = self.db.obtener_registro_por_clave(
            sesion.id, registro.codigo_clave
        )
        if actualizado is None:
            raise ErrorInventario("No se pudo recuperar el registro actualizado.")
        LOG.info("Stock ajustado en sesión %s: %s -> %s", sesion.id, original, nuevo)
        return actualizado

    def quitar_ajuste_stock(
        self, *, sesion: Sesion, registro: Any
    ) -> Any:
        if not sesion.abierta:
            raise ErrorInventario("La sesión ya fue finalizada.")
        if registro is None:
            raise ErrorInventario("No hay un registro seleccionado.")
        self.db.eliminar_ajuste_stock(registro.id)
        actualizado = self.db.obtener_registro_por_clave(
            sesion.id, registro.codigo_clave
        )
        if actualizado is None:
            raise ErrorInventario("No se pudo recuperar el registro.")
        return actualizado

    # ------------------------------------------------------------------
    # Cierre y exportación
    # ------------------------------------------------------------------
    def finalizar_sesion(
        self,
        *,
        sesion: Sesion,
        operador: SesionOperador,
        autorizacion: ResultadoAutorizacion,
        maestro: ArchivoMaestro,
    ) -> tuple[Sesion, list[ArchivoGenerado]]:
        if not sesion.abierta:
            raise ErrorInventario("La sesión ya fue finalizada.")
        if sesion.operador_id != operador.operador_id:
            raise ErrorInventario("La sesión no pertenece al operador activo.")
        if not autorizacion.descripcion:
            raise ErrorInventario("La autorización no es válida.")

        from .exportacion import generar_exportaciones

        registros = self.db.listar_registros(sesion.id)
        if not registros:
            raise ErrorInventario(
                "No hay productos registrados en esta sesión. Escanea al menos "
                "un producto antes de finalizar."
            )
        estadisticas = self.db.estadisticas_sesion(sesion.id)
        try:
            archivos = generar_exportaciones(
                sesion=sesion,
                operador=operador,
                autorizacion=autorizacion,
                maestro=maestro,
                registros=registros,
                estadisticas=estadisticas,
                carpeta_salida=self.rutas.salidas,
            )
        except Exception as exc:
            LOG.exception("Falló la generación de archivos de la sesión %s", sesion.id)
            raise ErrorInventario(
                "No fue posible generar los archivos de cierre. La sesión "
                f"sigue abierta y tus registros están a salvo.\n\nDetalle: {exc}"
            ) from exc

        try:
            self.db.finalizar_sesion_con_exportaciones(
                sesion_id=sesion.id,
                fin_en=a_iso(ahora_utc()) or "",
                autorizado_por=autorizacion.descripcion,
                metodo_autorizacion=autorizacion.metodo,
                archivos=archivos,
            )
        except ErrorBaseDatos as exc:
            # Se retiran los archivos recién creados para poder reintentar sin
            # dejar salidas duplicadas huérfanas.
            for archivo in archivos:
                try:
                    archivo.ruta.unlink(missing_ok=True)
                except OSError:
                    pass
            raise ErrorInventario(
                "Los archivos se generaron, pero no se pudo cerrar la sesión en "
                "la base de datos. No se modificó el archivo original. "
                f"Detalle: {exc}"
            ) from exc
        final = self.db.sesion_por_id(sesion.id)
        if final is None:
            raise ErrorInventario("No fue posible recuperar la sesión finalizada.")
        LOG.info(
            "Sesión %s finalizada con %s registros y %s archivos",
            sesion.id,
            len(registros),
            len(archivos),
        )
        return final, archivos
