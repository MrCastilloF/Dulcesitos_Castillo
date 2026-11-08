"""Lectura y validación del archivo maestro de códigos de barras.

Supuestos documentados sobre el formato del archivo maestro
------------------------------------------------------------
1. La información debe ser tabular. Se aceptan ``.xlsx``, ``.xlsm``, ``.xls``,
   ``.csv``, ``.tsv``, ``.txt`` y ``.pdf`` con tablas extraíbles.
2. Debe existir una fila de encabezados (hasta las primeras 20 filas, para
   tolerar títulos o logos) con una columna de código y otra de descripción.
   Los nombres se reconocen en español e inglés, con o sin tildes.
3. Todas las columnas adicionales se conservan, en su orden original, para el
   archivo de actualización. Sus valores se normalizan a texto.
4. Los códigos se tratan como texto. Si un código contiene ceros a la izquierda,
   la celda de Excel debe estar formateada como texto; si Excel ya los perdió,
   ningún programa puede reconstruirlos.
5. Si hay códigos repetidos en el maestro, se usa la primera fila para buscar y
   se informa la inconsistencia como advertencia.
6. Para PDF se requieren tablas reales o texto con columnas separadas. Un PDF
   escaneado como imagen no es legible sin OCR y se rechaza con un mensaje
   explícito.

El archivo original nunca se modifica. Las salidas se generan en una carpeta
separada dentro de ``C:\\dulcesito_castillo``.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from functools import cached_property
from pathlib import Path
from typing import Any

from .config import (
    EXTENSIONES_MAESTRAS,
    MAXIMO_ARCHIVO_MAESTRO_MB,
)
from .utilidades import (
    limpiar_espacios,
    quitar_acentos,
    truncar,
)

LOG = logging.getLogger(__name__)


class ErrorArchivoMaestro(RuntimeError):
    """Error legible para el operador sobre el catálogo de productos."""


# ---------------------------------------------------------------------------
# Sinónimos de encabezados
# ---------------------------------------------------------------------------
_SINONIMOS_CODIGO: dict[str, int] = {
    "codigo de barras": 130,
    "codigo barras": 128,
    "codigo de barra": 126,
    "barcode": 130,
    "bar code": 130,
    "ean": 120,
    "ean 13": 124,
    "ean13": 124,
    "ean 8": 118,
    "ean8": 118,
    "upc": 120,
    "gtin": 120,
    "codigo": 108,
    "codigo producto": 118,
    "codigo del producto": 118,
    "codigo de producto": 118,
    "cod producto": 112,
    "cod articulo": 110,
    "codigo articulo": 112,
    "codigo interno": 95,
    "cod": 90,
    "sku": 100,
    "referencia": 82,
    "ref": 72,
    "id producto": 70,
    "clave producto": 65,
    "item code": 100,
}

_SINONIMOS_DESCRIPCION: dict[str, int] = {
    "descripcion": 130,
    "descripcion producto": 132,
    "descripcion del producto": 132,
    "descripcion de producto": 130,
    "description": 130,
    "product description": 130,
    "item description": 128,
    "nombre": 112,
    "nombre producto": 124,
    "nombre del producto": 124,
    "nombre de producto": 122,
    "producto": 112,
    "product": 110,
    "detalle": 88,
    "detalle producto": 92,
    "articulo": 82,
    "desc": 80,
}

_COLUMNAS_SISTEMA = {
    "registrado en sesion",
    "fecha y hora",
    "operador",
    "cedula operador",
    "id sesion",
    "resultado",
}

_COLUMNAS_STOCK = {
    "stock",
    "stock actual",
    "stock disponible",
    "cantidad",
    "cantidad actual",
    "existencia",
    "existencias",
    "unidades",
    "unidades disponibles",
    "inventario",
    "saldo",
    "disponible",
    "qty",
    "quantity",
    "on hand",
}


def convertir_numero(valor: object) -> float | None:
    """Convierte cantidades con punto o coma decimal a número.

    Se usa para el stock contado. No se interpretan valores no numéricos; el
    operador simplemente no verá habilitado el ajuste si la columna no es
    numérica.
    """

    texto = limpiar_espacios(valor)
    if not texto:
        return None
    texto = re.sub(r"[^0-9,.\-]", "", texto)
    if not texto:
        return None
    if "," in texto and "." in texto:
        if texto.rfind(",") > texto.rfind("."):
            texto = texto.replace(".", "").replace(",", ".")
        else:
            texto = texto.replace(",", "")
    elif "," in texto or "." in texto:
        separador = "," if "," in texto else "."
        entero, _, decimales = texto.partition(separador)
        # En inventarios, "1.250" normalmente significa mil doscientos
        # cincuenta, no 1,25. Se respeta el cero inicial para decimales.
        if len(decimales) == 3 and entero not in {"", "0", "-0"}:
            texto = entero + decimales
        else:
            texto = entero + "." + decimales
    try:
        numero = float(texto)
    except ValueError:
        return None
    if numero != numero or numero in {float("inf"), float("-inf")}:
        return None
    return numero


def formatear_cantidad(valor: float | None) -> str:
    if valor is None:
        return ""
    if float(valor).is_integer():
        return str(int(valor))
    return format(valor, ".4g")


def normalizar_codigo_barras(valor: object) -> str:
    """Normaliza para comparar sin alterar ceros a la izquierda."""

    texto = limpiar_espacios(valor)
    if not texto:
        return ""
    # NFKC unifica caracteres de ancho completo que algunos lectores envían.
    import unicodedata

    texto = unicodedata.normalize("NFKC", texto).strip()
    # Algunos lectores agregan caracteres de control al final.
    texto = texto.strip("\x00\r\n\t ")
    return texto.casefold()


def _texto_celda(valor: object) -> str:
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "SÍ" if valor else "NO"
    if isinstance(valor, datetime):
        if valor.time().isoformat() == "00:00:00":
            return valor.strftime("%d/%m/%Y")
        return valor.strftime("%d/%m/%Y %H:%M")
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    if isinstance(valor, float):
        if valor.is_integer():
            return str(int(valor))
        return format(valor, ".15g")
    return limpiar_espacios(valor)


def _normalizar_encabezado(valor: object) -> str:
    texto = quitar_acentos(limpiar_espacios(valor)).casefold()
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _puntaje_codigo(encabezado: str) -> int:
    normalizado = _normalizar_encabezado(encabezado)
    if normalizado in _SINONIMOS_CODIGO:
        return _SINONIMOS_CODIGO[normalizado]
    if "codigo de barras" in normalizado or "barcode" in normalizado:
        return 122
    if normalizado.startswith("codigo ") and "descripcion" not in normalizado:
        return 96
    if normalizado.endswith(" codigo") and "descripcion" not in normalizado:
        return 78
    return 0


def _puntaje_descripcion(encabezado: str) -> int:
    normalizado = _normalizar_encabezado(encabezado)
    if normalizado in _SINONIMOS_DESCRIPCION:
        return _SINONIMOS_DESCRIPCION[normalizado]
    if "descripcion" in normalizado and "categoria" not in normalizado:
        return 116
    if "nombre" in normalizado and "producto" in normalizado:
        return 118
    if normalizado.endswith(" nombre"):
        return 84
    return 0


def _encabezados_unicos(fila: Sequence[object], cantidad: int) -> list[str]:
    usados: dict[str, int] = {}
    resultado: list[str] = []
    for indice in range(cantidad):
        base = limpiar_espacios(fila[indice] if indice < len(fila) else "")
        if not base:
            base = f"Columna {indice + 1}"
        clave = base.casefold()
        if clave in usados:
            usados[clave] += 1
            base = f"{base} ({usados[clave]})"
        else:
            usados[clave] = 1
        resultado.append(base)
    return resultado


@dataclass(frozen=True)
class RegistroMaestro:
    codigo: str
    codigo_clave: str
    descripcion: str
    campos: dict[str, str]
    fila: int = 0

    @property
    def etiqueta(self) -> str:
        return self.descripcion or "(sin descripción)"


@dataclass(frozen=True)
class ArchivoMaestro:
    ruta: Path
    nombre: str
    hoja: str | None
    columnas: tuple[str, ...]
    columna_codigo: str
    columna_descripcion: str
    registros: tuple[RegistroMaestro, ...]
    advertencias: tuple[str, ...]
    cargado_en: datetime
    huella: str
    formato: str
    inactivos: dict[str, str] = field(default_factory=dict)
    ajustes_locales: int = 0

    @property
    def total(self) -> int:
        return len(self.registros)

    @property
    def es_demo(self) -> bool:
        return self.nombre.casefold().startswith("demo") or "demostracion" in (
            self.nombre.casefold()
        )

    @cached_property
    def indice(self) -> dict[str, RegistroMaestro]:
        """Índice de búsqueda construido una sola vez por catálogo cargado."""

        indice: dict[str, RegistroMaestro] = {}
        for registro in self.registros:
            indice.setdefault(registro.codigo_clave, registro)
        return indice

    @cached_property
    def columna_stock(self) -> str | None:
        for columna in self.columnas:
            if _normalizar_encabezado(columna) in _COLUMNAS_STOCK:
                return columna
        return None

    def valor_stock(self, registro: RegistroMaestro) -> float | None:
        columna = self.columna_stock
        if not columna:
            return None
        return convertir_numero(registro.campos.get(columna, ""))

    def buscar(self, codigo: str) -> RegistroMaestro | None:
        clave = normalizar_codigo_barras(codigo)
        if not clave:
            return None
        return self.indice.get(clave)

    def __len__(self) -> int:
        return len(self.registros)

    def a_diccionario(self) -> dict[str, Any]:
        return {
            "version": 2,
            "ruta": str(self.ruta),
            "nombre": self.nombre,
            "hoja": self.hoja,
            "columnas": list(self.columnas),
            "columna_codigo": self.columna_codigo,
            "columna_descripcion": self.columna_descripcion,
            "advertencias": list(self.advertencias),
            "cargado_en": self.cargado_en.isoformat(),
            "huella": self.huella,
            "formato": self.formato,
            "inactivos": self.inactivos,
            "ajustes_locales": self.ajustes_locales,
            "registros": [
                {
                    "codigo": r.codigo,
                    "codigo_clave": r.codigo_clave,
                    "descripcion": r.descripcion,
                    "campos": r.campos,
                    "fila": r.fila,
                }
                for r in self.registros
            ],
        }

    @classmethod
    def desde_diccionario(cls, datos: dict[str, Any]) -> ArchivoMaestro:
        try:
            registros = tuple(
                RegistroMaestro(
                    codigo=str(item["codigo"]),
                    codigo_clave=str(item["codigo_clave"]),
                    descripcion=str(item.get("descripcion", "")),
                    campos={str(k): str(v) for k, v in item.get("campos", {}).items()},
                    fila=int(item.get("fila", 0)),
                )
                for item in datos["registros"]
            )
            return cls(
                ruta=Path(datos["ruta"]),
                nombre=str(datos["nombre"]),
                hoja=datos.get("hoja"),
                columnas=tuple(datos["columnas"]),
                columna_codigo=str(datos["columna_codigo"]),
                columna_descripcion=str(datos["columna_descripcion"]),
                registros=registros,
                advertencias=tuple(datos.get("advertencias", [])),
                cargado_en=datetime.fromisoformat(datos["cargado_en"]),
                huella=str(datos["huella"]),
                formato=str(datos.get("formato", "snapshot")),
                inactivos={
                    str(k): str(v)
                    for k, v in datos.get("inactivos", {}).items()
                },
                ajustes_locales=int(datos.get("ajustes_locales", 0)),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ErrorArchivoMaestro(
                "La copia de seguridad del catálogo de la sesión está dañada."
            ) from exc


def guardar_instantanea(maestro: ArchivoMaestro, ruta: str | Path) -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    temporal = ruta.with_suffix(".tmp")
    try:
        temporal.write_text(
            json.dumps(maestro.a_diccionario(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporal.replace(ruta)
    except OSError as exc:
        raise ErrorArchivoMaestro(
            f"No fue posible guardar la copia de seguridad del catálogo: {exc}"
        ) from exc
    return ruta


def cargar_instantanea(ruta: str | Path) -> ArchivoMaestro:
    ruta = Path(ruta)
    if not ruta.exists():
        raise ErrorArchivoMaestro(
            "No se encontró la copia del catálogo asociada a esta sesión."
        )
    try:
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        return ArchivoMaestro.desde_diccionario(datos)
    except (OSError, ValueError) as exc:
        raise ErrorArchivoMaestro(
            "No fue posible leer la copia del catálogo de la sesión."
        ) from exc


def extension_soportada(ruta: Path) -> bool:
    return ruta.suffix.casefold() in EXTENSIONES_MAESTRAS


def descubrir_archivos(directorio: str | Path) -> list[Path]:
    directorio = Path(directorio)
    if not directorio.exists():
        return []
    archivos: list[Path] = []
    try:
        for ruta in directorio.iterdir():
            if not ruta.is_file():
                continue
            if ruta.name.startswith("~$") or ruta.name.startswith("."):
                continue
            if extension_soportada(ruta):
                archivos.append(ruta)
    except OSError as exc:
        raise ErrorArchivoMaestro(
            f"No fue posible revisar la carpeta maestra: {exc}"
        ) from exc
    return sorted(
        archivos, key=lambda p: (p.stat().st_mtime, p.name.casefold()), reverse=True
    )


def seleccionar_maestro(directorio: str | Path) -> Path:
    archivos = descubrir_archivos(directorio)
    if not archivos:
        raise ErrorArchivoMaestro(
            "No se encontró un archivo maestro en:\n"
            f"{Path(directorio)}\n\n"
            "Descarga el archivo de productos (.xlsx, .xls, .csv, .txt o .pdf) "
            "en esa carpeta y pulsa «Actualizar archivo»."
        )
    return archivos[0]


def _calcular_huella(ruta: Path) -> str:
    sha = hashlib.sha256()
    try:
        with ruta.open("rb") as archivo:
            for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
                sha.update(bloque)
    except OSError as exc:
        raise ErrorArchivoMaestro(
            f"No fue posible leer el archivo maestro: {exc}"
        ) from exc
    return sha.hexdigest()


def _validar_ruta(ruta: Path, directorio: Path | None = None) -> Path:
    ruta = Path(ruta)
    if not ruta.exists() or not ruta.is_file():
        raise ErrorArchivoMaestro(f"El archivo maestro no existe:\n{ruta}")
    if not extension_soportada(ruta):
        formatos = ", ".join(EXTENSIONES_MAESTRAS)
        raise ErrorArchivoMaestro(
            "Formato de archivo no compatible.\n\n"
            f"Formatos admitidos: {formatos}.\n"
            "Convierte el archivo a Excel o CSV si es necesario."
        )
    try:
        tamano = ruta.stat().st_size
    except OSError as exc:
        raise ErrorArchivoMaestro(f"No fue posible leer el archivo: {exc}") from exc
    if tamano == 0:
        raise ErrorArchivoMaestro("El archivo maestro está vacío.")
    if tamano > MAXIMO_ARCHIVO_MAESTRO_MB * 1024 * 1024:
        raise ErrorArchivoMaestro(
            "El archivo maestro es demasiado grande "
            f"({tamano / (1024 * 1024):.1f} MB). "
            f"El límite de seguridad es {MAXIMO_ARCHIVO_MAESTRO_MB} MB."
        )
    if directorio is not None:
        try:
            ruta.resolve().relative_to(Path(directorio).resolve())
        except ValueError as exc:
            raise ErrorArchivoMaestro(
                "El archivo maestro debe estar dentro de la carpeta "
                f"{directorio}."
            ) from exc
    return ruta


def _detectar_estructura(
    filas: Sequence[Sequence[object]], max_busqueda: int = 20
) -> tuple[int, list[str], int, int] | None:
    mejor: tuple[int, int, int, int, list[str]] | None = None
    limite = min(len(filas), max_busqueda)
    for indice in range(limite):
        fila = filas[indice]
        if not fila:
            continue
        cantidad = len(fila)
        columnas = _encabezados_unicos(fila, cantidad)
        codigos = [(_puntaje_codigo(col), pos) for pos, col in enumerate(columnas)]
        descripciones = [
            (_puntaje_descripcion(col), pos) for pos, col in enumerate(columnas)
        ]
        mejor_codigo = max(codigos, default=(0, -1))
        mejor_descripcion = max(descripciones, default=(0, -1))
        if mejor_codigo[0] < 60 or mejor_descripcion[0] < 60:
            continue
        puntaje = mejor_codigo[0] + mejor_descripcion[0]
        if mejor is None or puntaje > mejor[0]:
            mejor = (
                puntaje,
                indice,
                mejor_codigo[1],
                mejor_descripcion[1],
                columnas,
            )
    if mejor is None:
        return None
    _, indice, pos_codigo, pos_desc, columnas = mejor
    return indice, columnas, pos_codigo, pos_desc


def _construir_archivo(
    *,
    filas: Sequence[Sequence[object]],
    ruta: Path,
    hoja: str | None,
    formato: str,
    estructura: tuple[int, list[str], int, int],
    inicio_datos: int | None = None,
    filas_ignoradas: Iterable[int] = (),
) -> ArchivoMaestro:
    indice_encabezado, columnas, pos_codigo, pos_desc = estructura
    ignoradas = set(filas_ignoradas)
    registros: list[RegistroMaestro] = []
    claves_vistas: dict[str, int] = {}
    duplicados: list[str] = []
    sin_descripcion = 0
    fila_inicio = indice_encabezado + 1 if inicio_datos is None else inicio_datos

    for posicion in range(fila_inicio, len(filas)):
        if posicion in ignoradas:
            continue
        fila = filas[posicion]
        if not fila or not any(_texto_celda(v) for v in fila):
            continue
        codigo = _texto_celda(fila[pos_codigo] if pos_codigo < len(fila) else "")
        descripcion = _texto_celda(fila[pos_desc] if pos_desc < len(fila) else "")
        if not codigo and not descripcion:
            continue
        if not codigo:
            continue
        clave = normalizar_codigo_barras(codigo)
        if not clave:
            continue
        campos: dict[str, str] = {}
        for i, columna in enumerate(columnas):
            campos[columna] = _texto_celda(fila[i] if i < len(fila) else "")
        if not descripcion:
            sin_descripcion += 1
            descripcion = "(sin descripción)"
        if clave in claves_vistas:
            if len(duplicados) < 5:
                duplicados.append(
                    f"«{codigo}» (filas {claves_vistas[clave]} y {posicion + 1})"
                )
            continue
        claves_vistas[clave] = posicion + 1
        registros.append(
            RegistroMaestro(
                codigo=codigo,
                codigo_clave=clave,
                descripcion=descripcion,
                campos=campos,
                fila=posicion + 1,
            )
        )

    if not registros:
        raise ErrorArchivoMaestro(
            "El archivo tiene encabezados reconocibles, pero no contiene "
            "productos con código y descripción."
        )

    advertencias: list[str] = []
    if duplicados:
        advertencias.append(
            "Se encontraron códigos duplicados; se conserva la primera fila de "
            "cada código. Ejemplos: " + "; ".join(duplicados) + "."
        )
    if sin_descripcion:
        advertencias.append(
            f"{sin_descripcion} producto(s) no tienen descripción y se "
            "mostrarán como «(sin descripción)»."
        )
    if len(registros) > 50_000:
        advertencias.append(
            "El catálogo supera 50.000 productos; la carga puede tardar unos "
            "segundos."
        )

    return ArchivoMaestro(
        ruta=ruta,
        nombre=ruta.name,
        hoja=hoja,
        columnas=tuple(columnas),
        columna_codigo=columnas[pos_codigo],
        columna_descripcion=columnas[pos_desc],
        registros=tuple(registros),
        advertencias=tuple(advertencias),
        cargado_en=datetime.now().astimezone(),
        huella=_calcular_huella(ruta),
        formato=formato,
    )


def _leer_excel(ruta: Path) -> ArchivoMaestro:
    try:
        from openpyxl import load_workbook
        from openpyxl.utils.exceptions import InvalidFileException
    except ImportError as exc:  # pragma: no cover - dependencia declarada
        raise ErrorArchivoMaestro(
            "Falta la dependencia openpyxl para leer archivos de Excel."
        ) from exc

    try:
        libro = load_workbook(
            filename=str(ruta), read_only=True, data_only=True, keep_links=False
        )
    except (InvalidFileException, OSError, ValueError, KeyError) as exc:
        raise ErrorArchivoMaestro(
            "El archivo de Excel está dañado, protegido con contraseña o no es "
            "un libro válido. Ábrelo en Excel y guárdalo nuevamente."
        ) from exc

    try:
        hojas_revisadas: list[str] = []
        for hoja in libro.worksheets:
            hojas_revisadas.append(hoja.title)
            filas = [
                tuple(fila)
                for fila in hoja.iter_rows(values_only=True)
                if fila is not None
            ]
            if not filas:
                continue
            estructura = _detectar_estructura(filas)
            if estructura is None:
                continue
            return _construir_archivo(
                filas=filas,
                ruta=ruta,
                hoja=hoja.title,
                formato="Excel",
                estructura=estructura,
            )
        raise ErrorArchivoMaestro(
            "No se encontró una tabla de productos en el archivo de Excel.\n\n"
            "La primera fila de la tabla debe incluir una columna de código "
            "(por ejemplo «Código de barras») y otra de descripción "
            "(por ejemplo «Descripción» o «Nombre del producto»).\n"
            "Hojas revisadas: " + ", ".join(hojas_revisadas) + "."
        )
    except ErrorArchivoMaestro:
        raise
    except Exception as exc:  # openpyxl puede lanzar errores de bajo nivel
        LOG.exception("Error leyendo Excel %s", ruta)
        raise ErrorArchivoMaestro(
            "No fue posible interpretar el archivo de Excel. "
            "Verifica que no esté dañado ni protegido."
        ) from exc
    finally:
        libro.close()


def _leer_xls(ruta: Path) -> ArchivoMaestro:
    try:
        import xlrd
    except ImportError as exc:  # pragma: no cover
        raise ErrorArchivoMaestro(
            "Falta la dependencia xlrd para leer archivos .xls antiguos."
        ) from exc
    try:
        libro = xlrd.open_workbook(str(ruta), on_demand=True)
    except Exception as exc:
        raise ErrorArchivoMaestro(
            "El archivo .xls está dañado, protegido o no es un libro válido."
        ) from exc
    try:
        for nombre in libro.sheet_names():
            hoja = libro.sheet_by_name(nombre)
            filas = [
                tuple(hoja.row_values(indice)) for indice in range(hoja.nrows)
            ]
            estructura = _detectar_estructura(filas)
            if estructura is not None:
                return _construir_archivo(
                    filas=filas,
                    ruta=ruta,
                    hoja=nombre,
                    formato="Excel 97-2003",
                    estructura=estructura,
                )
        raise ErrorArchivoMaestro(
            "No se encontró una tabla con columnas de código y descripción "
            "en el archivo .xls."
        )
    except ErrorArchivoMaestro:
        raise
    except Exception as exc:
        raise ErrorArchivoMaestro(
            "No fue posible interpretar el archivo .xls."
        ) from exc
    finally:
        libro.release_resources()


def _decodificar_texto(datos: bytes) -> tuple[str, str]:
    for codificacion in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return datos.decode(codificacion), codificacion
        except UnicodeDecodeError:
            continue
    raise ErrorArchivoMaestro(
        "No fue posible decodificar el archivo de texto. "
        "Guárdalo como UTF-8 o CSV."
    )


def _detectar_delimitador(texto: str, extension: str) -> str:
    if extension == ".tsv":
        return "\t"
    muestra = "\n".join(
        [linea for linea in texto.splitlines() if linea.strip()][:15]
    )
    if not muestra:
        raise ErrorArchivoMaestro("El archivo de texto está vacío.")
    try:
        return csv.Sniffer().sniff(muestra, delimiters=",;\t|").delimiter
    except csv.Error:
        conteos = {d: muestra.count(d) for d in (",", ";", "\t", "|")}
        delimitador = max(conteos, key=conteos.get)
        if conteos[delimitador] == 0:
            raise ErrorArchivoMaestro(
                "El archivo de texto no parece tabular. Debe tener columnas "
                "separadas por comas, punto y coma, tabulaciones o barras (|), "
                "con una fila de encabezados."
            ) from None
        return delimitador


def _leer_texto(ruta: Path) -> ArchivoMaestro:
    try:
        datos = ruta.read_bytes()
    except OSError as exc:
        raise ErrorArchivoMaestro(f"No fue posible leer el archivo: {exc}") from exc
    texto, codificacion = _decodificar_texto(datos)
    delimitador = _detectar_delimitador(texto, ruta.suffix.casefold())
    try:
        filas = list(csv.reader(io.StringIO(texto), delimiter=delimitador))
    except csv.Error as exc:
        raise ErrorArchivoMaestro(
            "El archivo de texto tiene un formato CSV no válido."
        ) from exc
    estructura = _detectar_estructura(filas)
    if estructura is None:
        raise ErrorArchivoMaestro(
            "No se encontró la fila de encabezados en el archivo de texto.\n\n"
            "Incluye una columna de código (por ejemplo «Código de barras») y "
            "una de descripción («Descripción» o «Nombre del producto»), "
            "separadas por comas, punto y coma, tabulación o barra vertical.\n"
            f"Codificación detectada: {codificacion}."
        )
    archivo = _construir_archivo(
        filas=filas,
        ruta=ruta,
        hoja=None,
        formato="Texto delimitado",
        estructura=estructura,
    )
    advertencias = list(archivo.advertencias)
    if delimitador != ",":
        nombre = {"\t": "tabulación", ";": "punto y coma", "|": "barra"}.get(
            delimitador, delimitador
        )
        advertencias.append(f"Delimitador detectado: {nombre}.")
    if advertencias != list(archivo.advertencias):
        archivo = ArchivoMaestro(
            **{
                **archivo.__dict__,
                "advertencias": tuple(advertencias),
            }
        )
    return archivo


def _leer_pdf(ruta: Path) -> ArchivoMaestro:
    try:
        import pdfplumber
    except ImportError as exc:  # pragma: no cover
        raise ErrorArchivoMaestro(
            "Falta la dependencia pdfplumber para leer archivos PDF."
        ) from exc
    try:
        with pdfplumber.open(str(ruta)) as pdf:
            tablas: list[tuple[int, list[list[object]]]] = []
            for numero, pagina in enumerate(pdf.pages, start=1):
                try:
                    extraidas = pagina.extract_tables() or []
                except Exception:
                    extraidas = []
                for tabla in extraidas:
                    if tabla and any(any(c for c in fila) for fila in tabla):
                        tablas.append((numero, tabla))
            if not tablas:
                return _leer_pdf_por_texto(pdf, ruta)
    except ErrorArchivoMaestro:
        raise
    except Exception as exc:
        raise ErrorArchivoMaestro(
            "No fue posible leer el PDF. Verifica que no esté dañado o "
            "protegido con contraseña."
        ) from exc

    primera_estructura: tuple[int, list[str], int, int] | None = None
    columnas_esperadas = 0
    filas_recolectadas: list[tuple[object, ...]] = []
    filas_ignoradas: set[int] = set()
    hoja = "PDF"
    for _, tabla in tablas:
        estructura = _detectar_estructura(tabla)
        if primera_estructura is None:
            if estructura is None:
                continue
            primera_estructura = estructura
            columnas_esperadas = len(estructura[1])
            # Se conserva la fila de encabezado en la posición 0 del acumulado.
            inicio = estructura[0]
            filas_recolectadas.extend(tuple(f) for f in tabla[inicio:])
            continue
        # Las tablas posteriores deben tener la misma cantidad de columnas.
        for fila in tabla:
            if not fila or not any(_texto_celda(c) for c in fila):
                continue
            if len(fila) != columnas_esperadas:
                continue
            if _detectar_estructura([tuple(fila)]) is not None:
                continue
            filas_recolectadas.append(tuple(fila))

    if primera_estructura is None:
        raise ErrorArchivoMaestro(
            "El PDF no contiene una tabla reconocible con código y descripción. "
            "Si es un PDF escaneado, conviértelo a Excel o CSV con OCR."
        )
    ajustada = (0, primera_estructura[1], primera_estructura[2], primera_estructura[3])
    archivo = _construir_archivo(
        filas=filas_recolectadas,
        ruta=ruta,
        hoja=hoja,
        formato="PDF tabular",
        estructura=ajustada,
        filas_ignoradas=filas_ignoradas,
    )
    advertencias = list(archivo.advertencias)
    advertencias.append(
        "PDF leído como tabla; revisa el archivo de actualización antes de usarlo."
    )
    return ArchivoMaestro(
        **{**archivo.__dict__, "advertencias": tuple(advertencias)}
    )


def _leer_pdf_por_texto(pdf: Any, ruta: Path) -> ArchivoMaestro:
    """Respaldo para PDFs sin rejilla, separando columnas por espacios."""

    filas: list[list[str]] = []
    for pagina in pdf.pages:
        texto = pagina.extract_text() or ""
        for linea in texto.splitlines():
            limpia = linea.strip()
            if not limpia:
                continue
            celdas = re.split(r"\t+| {2,}", limpia)
            if len(celdas) >= 2:
                filas.append([limpiar_espacios(c) for c in celdas])
    estructura = _detectar_estructura(filas)
    if estructura is None:
        raise ErrorArchivoMaestro(
            "El PDF no contiene una tabla reconocible con código y descripción. "
            "Si es un PDF escaneado (una imagen), la aplicación no puede leerlo "
            "sin OCR. Expórtalo a Excel o CSV."
        )
    archivo = _construir_archivo(
        filas=filas,
        ruta=ruta,
        hoja="PDF",
        formato="PDF (texto)",
        estructura=estructura,
    )
    advertencias = list(archivo.advertencias)
    advertencias.append(
        "El PDF no tenía tablas con rejilla y se interpretó por columnas de "
        "texto. Verifica que los códigos y descripciones sean correctos."
    )
    return ArchivoMaestro(
        **{**archivo.__dict__, "advertencias": tuple(advertencias)}
    )


def cargar_maestro(
    ruta: str | Path, directorio_permitido: str | Path | None = None
) -> ArchivoMaestro:
    ruta = _validar_ruta(Path(ruta), Path(directorio_permitido) if directorio_permitido else None)
    extension = ruta.suffix.casefold()
    if extension in {".xlsx", ".xlsm"}:
        return _leer_excel(ruta)
    if extension == ".xls":
        return _leer_xls(ruta)
    if extension in {".csv", ".txt", ".tsv"}:
        return _leer_texto(ruta)
    if extension == ".pdf":
        return _leer_pdf(ruta)
    raise ErrorArchivoMaestro("El formato del archivo maestro no es compatible.")


def cargar_maestro_actual(directorio: str | Path) -> ArchivoMaestro:
    return cargar_maestro(seleccionar_maestro(directorio), directorio)


def resumen_para_error(ruta: Path) -> str:
    try:
        return f"{ruta.name} · {truncar(str(ruta), 70)}"
    except Exception:
        return str(ruta)


def columnas_para_exportacion(maestro: ArchivoMaestro) -> list[str]:
    """Columnas originales sin duplicar las columnas de auditoría del sistema."""

    resultado: list[str] = []
    for columna in maestro.columnas:
        limpia = columna.strip()
        if _normalizar_encabezado(limpia) in _COLUMNAS_SISTEMA:
            continue
        if limpia not in resultado:
            resultado.append(limpia)
    return resultado
