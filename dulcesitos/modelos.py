"""Modelos de dominio compartidos por la lógica y la interfaz."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

EstadoLectorValor = Literal["desconectado", "pendiente", "conectado", "activo"]
ResultadoLectura = Literal["registrado", "duplicado", "no_encontrado"]
ModoLector = Literal["HID", "SERIAL"]


@dataclass(frozen=True)
class Administrador:
    id: int
    nombre: str
    cedula: str
    correo: str
    creado_en: datetime | None = None


@dataclass(frozen=True)
class Operador:
    id: int
    nombre: str
    cedula: str
    correo: str
    creado_en: datetime | None = None
    activo: bool = True
    acceso_expira_en: datetime | None = None


@dataclass(frozen=True)
class CodigoAcceso:
    id: int
    pista: str
    estado: str
    operador_id: int | None
    operador_nombre: str | None
    nombre_asignado: str | None
    cedula_asignada: str | None
    correo_asignado: str | None
    creado_en: datetime | None
    expira_en: datetime | None
    activado_en: datetime | None
    revocado_en: datetime | None
    ultimo_uso_en: datetime | None
    usos: int
    emitido_por_nombre: str | None = None

    @property
    def vencido(self) -> bool:
        from .utilidades import ahora_utc

        return bool(self.expira_en and self.expira_en <= ahora_utc())

    @property
    def estado_visible(self) -> str:
        if self.estado == "revocado":
            return "Revocado"
        if self.vencido:
            return "Vencido"
        if self.estado == "pendiente":
            return "Pendiente"
        return "Activo"


@dataclass(frozen=True)
class SesionOperador:
    operador_id: int
    nombre: str
    cedula: str
    correo: str
    codigo_id: int
    acceso_expira_en: datetime | None
    iniciada_en: datetime


@dataclass(frozen=True)
class RegistroSesion:
    id: int
    sesion_id: int
    codigo: str
    codigo_clave: str
    descripcion: str
    campos: dict[str, str]
    escaneado_en: datetime
    operador_nombre: str
    operador_cedula: str
    stock_original: float | None = None
    stock_nuevo: float | None = None
    stock_diferencia: float | None = None
    ajuste_stock_en: datetime | None = None
    origen: str = "lector"
    novedad: str = ""

    @property
    def es_manual(self) -> bool:
        return self.origen == "manual"

    @property
    def tiene_ajuste_stock(self) -> bool:
        return self.stock_nuevo is not None

    @property
    def detalle_campos(self) -> str:
        from .utilidades import unir_valores

        return unir_valores(self.campos.values())


@dataclass(frozen=True)
class EstadisticasSesion:
    registrados: int = 0
    duplicados: int = 0
    no_encontrados: int = 0
    ultima_lectura_en: datetime | None = None
    ajustes_stock: int = 0
    manuales: int = 0

    @property
    def total_lecturas(self) -> int:
        return self.registrados + self.duplicados + self.no_encontrados


@dataclass(frozen=True)
class Sesion:
    id: int
    operador_id: int
    operador_nombre: str
    operador_cedula: str
    codigo_id: int | None
    estado: str
    inicio_en: datetime
    fin_en: datetime | None
    maestro_nombre: str
    maestro_ruta: str
    maestro_hash: str
    instantanea_ruta: str | None
    calibracion_codigo: str
    calibracion_en: datetime
    autorizado_por: str | None = None
    metodo_autorizacion: str | None = None
    exportaciones: tuple[ArchivoGenerado, ...] = field(default_factory=tuple)

    @property
    def abierta(self) -> bool:
        return self.estado == "abierta"


@dataclass(frozen=True)
class ArchivoGenerado:
    tipo: Literal["xlsx", "pdf", "txt"]
    ruta: Path
    tamano_bytes: int = 0


@dataclass(frozen=True)
class ResultadoEscaneo:
    estado: Literal["registrado", "duplicado", "no_encontrado", "vacio"]
    mensaje: str
    codigo: str
    codigo_clave: str = ""
    registro: RegistroSesion | None = None
    registro_existente: RegistroSesion | None = None
    estadisticas: EstadisticasSesion = field(default_factory=EstadisticasSesion)
    campos: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ConfiguracionLector:
    modo: ModoLector = "HID"
    puerto: str = ""
    baudios: int = 9600

    @property
    def descripcion(self) -> str:
        if self.modo == "SERIAL":
            puerto = self.puerto or "sin puerto"
            return f"Lector serie · {puerto} · {self.baudios} bps"
        return "Lector USB · emulación de teclado (HID)"


@dataclass(frozen=True)
class EstadoLector:
    estado: EstadoLectorValor = "pendiente"
    modo: ModoLector = "HID"
    puerto: str = ""
    detalle: str = ""
    dispositivos: tuple[str, ...] = ()
    identificado: bool = False
    validado_por_lectura: bool = False
    actualizado_en: datetime | None = None

    @property
    def etiqueta(self) -> str:
        return {
            "activo": "ACTIVO",
            "conectado": "CONECTADO",
            "desconectado": "DESCONECTADO",
            "pendiente": "HID EN ESPERA",
        }.get(self.estado, self.estado.upper())

    @property
    def permite_escanear(self) -> bool:
        return self.estado in {"conectado", "activo"}


@dataclass(frozen=True)
class ResultadoAutorizacion:
    metodo: Literal["operador", "administrador"]
    descripcion: str
