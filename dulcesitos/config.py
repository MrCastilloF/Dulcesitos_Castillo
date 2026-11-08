"""Rutas, constantes y preparación del entorno local de la aplicación.

Supuestos de despliegue
-----------------------
* El archivo maestro se descarga SIEMPRE en ``C:\\dulcesito_castillo``.
  Ese nombre y ubicación forman parte del contrato funcional del proyecto.
* Los datos internos (usuarios, hashes, sesiones y copias de seguridad del
  catálogo) viven en el perfil del usuario de Windows:
  ``%LOCALAPPDATA%\\DulcesitosCastillo``. No se guardan secretos en el archivo
  maestro ni en la carpeta compartida de C:\\.
* Los archivos de salida se escriben en ``C:\\dulcesito_castillo\\salidas``
  para que el operador los encuentre junto al archivo maestro.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

APP_NAME = "Dulcesitos Castillo"
APP_VERSION = "1.0.0"
APP_AUTHOR = "Carlos Castillo · SENA"
APP_SUBTITLE = "Registro y gestión de inventario"

RUTA_MAESTRA_POR_DEFECTO = Path(r"C:\dulcesito_castillo")

EXTENSIONES_MAESTRAS = (
    ".xlsx",
    ".xlsm",
    ".xls",
    ".csv",
    ".txt",
    ".tsv",
    ".pdf",
)

PREFIJO_SALIDA_ACTUALIZACION = "actualizacion"
PREFIJO_SALIDA_REPORTE = "inventario_sesion"
MAXIMO_ARCHIVO_MAESTRO_MB = 40


class ErrorRutas(RuntimeError):
    """Problema al preparar las carpetas de trabajo."""


@dataclass(frozen=True)
class RutasApp:
    """Conjunto de rutas utilizadas por la aplicación."""

    maestra: Path
    salidas: Path
    datos: Path
    base_datos: Path
    instantaneas: Path
    registros: Path
    respaldos: Path

    def como_diccionario(self) -> dict[str, str]:
        return {
            "maestra": str(self.maestra),
            "salidas": str(self.salidas),
            "datos": str(self.datos),
            "base_datos": str(self.base_datos),
            "instantaneas": str(self.instantaneas),
            "registros": str(self.registros),
            "respaldos": str(self.respaldos),
        }


def _entorno_ruta(nombre: str) -> Path | None:
    valor = os.environ.get(nombre, "").strip()
    return Path(valor).expanduser() if valor else None


def carpeta_maestra() -> Path:
    """Carpeta contractual del archivo maestro.

    ``DULCESITOS_MAESTRO_DIR`` permite aislar las pruebas automatizadas sin
    alterar la ruta real de producción.
    """

    return _entorno_ruta("DULCESITOS_MAESTRO_DIR") or RUTA_MAESTRA_POR_DEFECTO


def carpeta_datos() -> Path:
    """Carpeta privada de datos de la aplicación."""

    personalizada = _entorno_ruta("DULCESITOS_DATA_DIR")
    if personalizada:
        return personalizada
    base = os.environ.get("LOCALAPPDATA", "").strip()
    if base:
        return Path(base) / "DulcesitosCastillo"
    return Path.home() / "DulcesitosCastillo"


def preparar_rutas() -> RutasApp:
    """Crea las carpetas necesarias y devuelve las rutas activas.

    La carpeta maestra se crea si no existe, tal como exige el requerimiento.
    Los errores de permisos se transforman en un mensaje accionable en español.
    """

    maestra = carpeta_maestra()
    datos = carpeta_datos()
    salidas = maestra / "salidas"
    instantaneas = datos / "sesiones"
    registros = datos / "registros"
    respaldos = datos / "respaldos"

    try:
        for ruta in (maestra, salidas, datos, instantaneas, registros, respaldos):
            ruta.mkdir(parents=True, exist_ok=True)
    except PermissionError as exc:
        raise ErrorRutas(
            "Windows no permitió crear las carpetas de trabajo.\n\n"
            f"Verifica permisos de escritura sobre:\n{maestra}\n{datos}\n\n"
            "Si la carpeta C:\\dulcesito_castillo fue creada por otro usuario, "
            "inicia la aplicación con una cuenta con permisos o pide al "
            "administrador del equipo que habilite la escritura."
        ) from exc
    except OSError as exc:
        raise ErrorRutas(
            "No fue posible preparar las carpetas de la aplicación.\n\n"
            f"Detalle: {exc}"
        ) from exc

    return RutasApp(
        maestra=maestra,
        salidas=salidas,
        datos=datos,
        base_datos=datos / "inventario.db",
        instantaneas=instantaneas,
        registros=registros,
        respaldos=respaldos,
    )


def configurar_dpi() -> None:
    """Activa el escalado nítido de Windows antes de crear la ventana Tk."""

    if os.name != "nt":
        return
    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        # La aplicación sigue siendo usable si Windows no expone la API.
        pass
