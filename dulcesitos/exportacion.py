"""Generación de las salidas de cierre.

Se producen tres archivos nuevos, con nombre que identifica al operador y la
fecha/hora, dentro de ``C:\\dulcesito_castillo\\salidas``:

* ``actualizacion_...xlsx``: libro con el catálogo completo actualizado (todas
  las columnas originales más la auditoría de la sesión) y una hoja exclusiva
  con los productos registrados.
* ``actualizacion_...txt``: la misma tabla en texto delimitado por tabulación,
  útil para integraciones sencillas.
* ``inventario_sesion_...pdf``: reporte visual imprimible con resumen, detalle
  de productos y bloque de firmas.

El archivo maestro original jamás se abre para escritura.
"""

from __future__ import annotations

import csv
import html
import logging
import os
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    LongTable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .archivo_maestro import ArchivoMaestro, convertir_numero, formatear_cantidad
from .config import (
    APP_AUTHOR,
    APP_NAME,
    APP_VERSION,
    PREFIJO_SALIDA_ACTUALIZACION,
    PREFIJO_SALIDA_REPORTE,
)
from .modelos import (
    ArchivoGenerado,
    EstadisticasSesion,
    RegistroSesion,
    ResultadoAutorizacion,
    Sesion,
    SesionOperador,
)
from .utilidades import (
    a_local,
    fecha_para_archivo,
    formatear_fecha_hora,
    formatear_hora,
    slug_archivo,
    unir_valores,
)

LOG = logging.getLogger(__name__)

# Paleta de marca compartida con la interfaz.
CACAO = "241A17"
CACAO_SUAVE = "3B2C27"
CREMA = "FFF8F0"
ROSA = "FB7185"
ROSA_OSCURO = "BE123C"
CARAMELO = "FBBF24"
VERDE = "059669"
VERDE_CLARO = "D1FAE5"
GRIS = "6B7280"
GRIS_CLARO = "F5EFE8"
BORDE = "E7D8CC"

AUDITORIA = (
    "REGISTRADO EN SESIÓN",
    "FECHA Y HORA REGISTRO",
    "OPERADOR REGISTRO",
    "CÉDULA OPERADOR",
    "ID SESIÓN",
)


def _color(valor: str) -> colors.Color:
    """ReportLab exige el prefijo #; openpyxl recibe el hex sin prefijo."""

    return colors.HexColor("#" + valor.lstrip("#"))


class ErrorExportacion(RuntimeError):
    """Fallo controlado al construir los archivos de salida."""


def _texto_seguro(valor: object) -> str:
    """Evita que un valor del catálogo se convierta en fórmula al abrir Excel."""

    texto = str(valor or "")
    if texto[:1] in {"=", "+", "@"} or texto.startswith("\t") or texto.startswith("\r"):
        return "'" + texto
    return texto


def _valor_pdf(valor: object) -> str:
    return html.escape(str(valor or ""), quote=True)


def _encabezados_auditoria(
    originales: Sequence[str],
    *,
    incluir_stock: bool = False,
    incluir_manual: bool = False,
) -> list[str]:
    vistos = {str(c).casefold() for c in originales}
    resultado: list[str] = []
    nombres = list(AUDITORIA)
    if incluir_stock:
        nombres.extend(["STOCK ORIGINAL", "STOCK CONTADO", "DIFERENCIA DE STOCK"])
    if incluir_manual:
        nombres.extend(["ORIGEN DEL REGISTRO", "NOVEDAD MANUAL"])
    for base in nombres:
        candidato = base
        contador = 2
        while candidato.casefold() in vistos:
            candidato = f"{base} ({contador})"
            contador += 1
        vistos.add(candidato.casefold())
        resultado.append(candidato)
    return resultado


def _numero_celda(valor: float | None) -> float | int | None:
    if valor is None:
        return None
    return int(valor) if float(valor).is_integer() else valor


def _base_archivos(operador: SesionOperador, momento: datetime) -> tuple[str, str]:
    identidad = f"{slug_archivo(operador.nombre, 30)}_{operador.cedula}"
    marca = fecha_para_archivo(momento)
    base = f"{PREFIJO_SALIDA_ACTUALIZACION}_DULCESITOS_{identidad}_{marca}"
    reporte = f"{PREFIJO_SALIDA_REPORTE}_DULCESITOS_{identidad}_{marca}"
    return base, reporte


def _ajustar_ancho(texto: str, minimo: int, maximo: int) -> int:
    largo = max((len(linea) for linea in str(texto).splitlines()), default=0)
    return max(minimo, min(maximo, largo + 2))


def _estilo_encabezado(hoja: Worksheet, cantidad_columnas: int, fila: int = 1) -> None:
    relleno = PatternFill("solid", fgColor=CACAO)
    borde = Border(bottom=Side(style="medium", color=ROSA))
    for columna in range(1, cantidad_columnas + 1):
        celda = hoja.cell(row=fila, column=columna)
        celda.fill = relleno
        celda.font = Font(name="Calibri", size=10, bold=True, color=CREMA)
        celda.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        celda.border = borde
    hoja.row_dimensions[fila].height = 34


def _configurar_impresion(hoja: Worksheet, cantidad_columnas: int) -> None:
    hoja.sheet_properties.pageSetUpPr.fitToPage = True
    hoja.page_setup.orientation = "landscape"
    hoja.page_setup.paperSize = hoja.PAPERSIZE_A4
    hoja.page_setup.fitToWidth = 1
    hoja.page_setup.fitToHeight = 0
    hoja.print_title_rows = "1:1"
    hoja.print_options.horizontalCentered = True
    hoja.oddFooter.center.text = "Dulcesitos Castillo · inventario de sesión"
    hoja.oddFooter.right.text = "Página &P de &N"


def _escribir_tabla_actualizacion(
    hoja: Worksheet,
    *,
    maestro: ArchivoMaestro,
    sesion: Sesion,
    operador: SesionOperador,
    registros: Sequence[RegistroSesion],
    solo_registrados: bool,
) -> tuple[int, int]:
    incluir_stock = bool(maestro.columna_stock)
    incluir_manual = any(r.es_manual for r in registros)
    auditadas = _encabezados_auditoria(
        maestro.columnas,
        incluir_stock=incluir_stock,
        incluir_manual=incluir_manual,
    )
    encabezados = list(maestro.columnas) + auditadas
    hoja.append(encabezados)
    _estilo_encabezado(hoja, len(encabezados))

    por_clave = {r.codigo_clave: r for r in registros}
    if solo_registrados:
        filas = list(registros)
    else:
        claves_maestro = {r.codigo_clave for r in maestro.registros}
        manuales_nuevos = [
            r
            for r in registros
            if r.es_manual and r.codigo_clave not in claves_maestro
        ]
        filas = list(maestro.registros) + manuales_nuevos
    relleno_verde = PatternFill("solid", fgColor="ECFDF5")
    relleno_alterno = PatternFill("solid", fgColor=CREMA)
    alineacion = Alignment(vertical="top", wrap_text=True)
    columnas_lista = list(maestro.columnas)
    indice_stock = (
        columnas_lista.index(maestro.columna_stock)
        if maestro.columna_stock in columnas_lista
        else None
    )

    for indice, origen in enumerate(filas, start=1):
        if solo_registrados:
            codigo_clave = origen.codigo_clave
            campos = origen.campos
            item = por_clave.get(codigo_clave)
        else:
            codigo_clave = origen.codigo_clave
            campos = origen.campos
            item = por_clave.get(codigo_clave)
        valores: list[Any] = [
            _texto_seguro(campos.get(col, "")) for col in maestro.columnas
        ]
        if (
            item is not None
            and item.stock_nuevo is not None
            and indice_stock is not None
        ):
            valores[indice_stock] = _numero_celda(item.stock_nuevo)
        if item:
            valores.extend(
                [
                    "SÍ",
                    a_local(item.escaneado_en).replace(tzinfo=None),
                    item.operador_nombre,
                    item.operador_cedula,
                    sesion.id,
                ]
            )
        else:
            valores.extend(["NO", None, None, None, sesion.id])
        if incluir_stock:
            if item:
                original = item.stock_original
                if original is None:
                    original = convertir_numero(
                        campos.get(maestro.columna_stock or "", "")
                    )
                valores.extend(
                    [
                        _numero_celda(original),
                        _numero_celda(item.stock_nuevo),
                        _numero_celda(item.stock_diferencia),
                    ]
                )
            else:
                valores.extend([None, None, None])
        if incluir_manual:
            if item:
                valores.extend(
                    [
                        "MANUAL" if item.es_manual else "LECTOR",
                        item.novedad if item.es_manual else "",
                    ]
                )
            else:
                valores.extend([None, None])
        hoja.append(valores)
        fila_actual = hoja.max_row
        for columna in range(1, len(encabezados) + 1):
            celda = hoja.cell(row=fila_actual, column=columna)
            celda.alignment = alineacion
            if item:
                celda.fill = relleno_verde
            elif indice % 2 == 0:
                celda.fill = relleno_alterno
            if columna > len(maestro.columnas) and columna == len(maestro.columnas) + 2:
                celda.number_format = "dd/mm/yyyy hh:mm"

    # Formatos de fecha para las columnas de auditoría.
    col_fecha = len(maestro.columnas) + 2
    for fila in range(2, hoja.max_row + 1):
        hoja.cell(row=fila, column=col_fecha).number_format = "dd/mm/yyyy hh:mm"

    for posicion, columna in enumerate(encabezados, start=1):
        letra = get_column_letter(posicion)
        nombre = columna.casefold()
        if "descrip" in nombre or "nombre" in nombre or "detalle" in nombre:
            ancho = 42
        elif "código" in nombre or "codigo" in nombre or "barcode" in nombre:
            ancho = 22
        elif "fecha" in nombre:
            ancho = 20
        elif "operador" in nombre:
            ancho = 28
        else:
            muestra = " ".join(
                str(hoja.cell(row=f, column=posicion).value or "")
                for f in range(1, min(hoja.max_row, 80) + 1)
            )
            ancho = _ajustar_ancho(muestra, 12, 34)
        hoja.column_dimensions[letra].width = ancho

    hoja.freeze_panes = "A2"
    if hoja.max_row >= 2:
        hoja.auto_filter.ref = f"A1:{get_column_letter(len(encabezados))}{hoja.max_row}"
    _configurar_impresion(hoja, len(encabezados))
    hoja.sheet_view.showGridLines = False
    hoja.sheet_properties.tabColor = ROSA
    return fila_actual, len(encabezados)


def _crear_hoja_resumen(
    libro: Workbook,
    *,
    sesion: Sesion,
    operador: SesionOperador,
    autorizacion: ResultadoAutorizacion,
    maestro: ArchivoMaestro,
    estadisticas: EstadisticasSesion,
    nombres: dict[str, str],
) -> None:
    hoja = libro.create_sheet("Resumen")
    hoja.sheet_view.showGridLines = False
    hoja.sheet_properties.tabColor = CARAMELO
    anchos = {"A": 26, "B": 54, "C": 20, "D": 22}
    for columna, ancho in anchos.items():
        hoja.column_dimensions[columna].width = ancho

    hoja.merge_cells("A1:D2")
    titulo = hoja["A1"]
    titulo.value = "DULCESITOS CASTILLO"
    titulo.fill = PatternFill("solid", fgColor=CACAO)
    titulo.font = Font(name="Calibri", size=22, bold=True, color=CREMA)
    titulo.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    hoja.row_dimensions[1].height = 31
    hoja.row_dimensions[2].height = 17

    hoja.merge_cells("A3:D3")
    subtitulo = hoja["A3"]
    subtitulo.value = "Acta de inventario · Archivo de actualización"
    subtitulo.fill = PatternFill("solid", fgColor=ROSA)
    subtitulo.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    subtitulo.alignment = Alignment(vertical="center", horizontal="left", indent=1)
    hoja.row_dimensions[3].height = 22

    fila = 5
    pares = [
        ("Operador", operador.nombre),
        ("Cédula", operador.cedula),
        ("Correo", operador.correo),
        ("Autorización de cierre", autorizacion.descripcion),
        ("Sesión", f"#{sesion.id}"),
        ("Inicio", formatear_fecha_hora(sesion.inicio_en)),
        ("Cierre", formatear_fecha_hora(sesion.fin_en or a_local(datetime.now().astimezone()))),
        ("Archivo maestro original", maestro.nombre),
        ("Ruta del catálogo", str(maestro.ruta)),
        ("Productos en el catálogo", maestro.total),
        ("Ajustes de stock aplicados", estadisticas.ajustes_stock),
        ("Registros manuales", estadisticas.manuales),
        ("Huella SHA-256 del catálogo", maestro.huella),
    ]
    for etiqueta, valor in pares:
        hoja.cell(row=fila, column=1, value=etiqueta)
        hoja.cell(row=fila, column=1).font = Font(
            name="Calibri", bold=True, size=10, color=CACAO
        )
        hoja.cell(row=fila, column=1).fill = PatternFill("solid", fgColor=GRIS_CLARO)
        hoja.merge_cells(start_row=fila, start_column=2, end_row=fila, end_column=4)
        celda = hoja.cell(row=fila, column=2, value=_texto_seguro(valor))
        celda.font = Font(name="Calibri", size=10, color=CACAO_SUAVE)
        celda.alignment = Alignment(vertical="center", wrap_text=True)
        hoja.row_dimensions[fila].height = 19 if len(str(valor)) < 70 else 30
        fila += 1

    fila += 1
    hoja.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=4)
    encabezado = hoja.cell(row=fila, column=1, value="RESUMEN DE LA SESIÓN")
    encabezado.fill = PatternFill("solid", fgColor=CACAO)
    encabezado.font = Font(name="Calibri", size=12, bold=True, color=CREMA)
    encabezado.alignment = Alignment(vertical="center", indent=1)
    hoja.row_dimensions[fila].height = 25
    fila += 1
    metricas = [
        ("REGISTRADOS", estadisticas.registrados, "ECFDF5", VERDE),
        ("DUPLICADOS", estadisticas.duplicados, "FEF3C7", "B45309"),
        ("NO ENCONTRADOS", estadisticas.no_encontrados, "FEE2E2", "B91C1C"),
        ("TOTAL LECTURAS", estadisticas.total_lecturas, "E0F2FE", "0369A1"),
    ]
    for columna, (etiqueta, valor, fondo, color_texto) in enumerate(metricas, start=1):
        hoja.cell(row=fila, column=columna, value=etiqueta)
        hoja.cell(row=fila, column=columna).font = Font(
            name="Calibri", size=8, bold=True, color=color_texto
        )
        hoja.cell(row=fila, column=columna).fill = PatternFill("solid", fgColor=fondo)
        hoja.cell(row=fila, column=columna).alignment = Alignment(horizontal="center")
        hoja.cell(row=fila + 1, column=columna, value=valor)
        hoja.cell(row=fila + 1, column=columna).font = Font(
            name="Calibri", size=20, bold=True, color=color_texto
        )
        hoja.cell(row=fila + 1, column=columna).fill = PatternFill("solid", fgColor=fondo)
        hoja.cell(row=fila + 1, column=columna).alignment = Alignment(horizontal="center")
        hoja.row_dimensions[fila + 1].height = 34
    fila += 3

    hoja.cell(row=fila, column=1, value="Archivos generados")
    hoja.cell(row=fila, column=1).font = Font(
        name="Calibri", bold=True, size=11, color=CACAO
    )
    fila += 1
    for tipo, nombre in nombres.items():
        hoja.cell(row=fila, column=1, value=tipo.upper())
        hoja.cell(row=fila, column=1).font = Font(
            name="Calibri", bold=True, size=9, color=ROSA_OSCURO
        )
        hoja.merge_cells(start_row=fila, start_column=2, end_row=fila, end_column=4)
        hoja.cell(row=fila, column=2, value=nombre).font = Font(
            name="Calibri", size=9, color=CACAO_SUAVE
        )
        fila += 1

    fila += 1
    hoja.merge_cells(start_row=fila, start_column=1, end_row=fila, end_column=4)
    nota = hoja.cell(
        row=fila,
        column=1,
        value=(
            "El archivo maestro original no fue modificado. Esta actualización "
            "se generó automáticamente y conserva las columnas originales más "
            "los campos de auditoría de la sesión."
        ),
    )
    nota.font = Font(name="Calibri", size=9, italic=True, color=GRIS)
    nota.alignment = Alignment(wrap_text=True, vertical="top")
    hoja.row_dimensions[fila].height = 32
    hoja.merge_cells(start_row=fila + 1, start_column=1, end_row=fila + 1, end_column=4)
    pie = hoja.cell(
        row=fila + 1,
        column=1,
        value=f"{APP_NAME} · v{APP_VERSION} · {APP_AUTHOR}",
    )
    pie.font = Font(name="Calibri", size=8, color=GRIS)
    pie.alignment = Alignment(horizontal="right")
    hoja.page_setup.orientation = "landscape"
    hoja.page_setup.fitToWidth = 1


def _generar_excel(
    ruta: Path,
    *,
    sesion: Sesion,
    operador: SesionOperador,
    autorizacion: ResultadoAutorizacion,
    maestro: ArchivoMaestro,
    registros: Sequence[RegistroSesion],
    estadisticas: EstadisticasSesion,
    nombres: dict[str, str],
) -> None:
    libro = Workbook()
    hoja_actualizacion = libro.active
    hoja_actualizacion.title = "Actualización"
    _escribir_tabla_actualizacion(
        hoja_actualizacion,
        maestro=maestro,
        sesion=sesion,
        operador=operador,
        registros=registros,
        solo_registrados=False,
    )

    hoja_sesion = libro.create_sheet("Registros de sesión")
    _escribir_tabla_actualizacion(
        hoja_sesion,
        maestro=maestro,
        sesion=sesion,
        operador=operador,
        registros=registros,
        solo_registrados=True,
    )
    hoja_sesion.sheet_properties.tabColor = VERDE
    _crear_hoja_resumen(
        libro,
        sesion=sesion,
        operador=operador,
        autorizacion=autorizacion,
        maestro=maestro,
        estadisticas=estadisticas,
        nombres=nombres,
    )
    libro.properties.title = f"Actualización de inventario · {operador.nombre}"
    libro.properties.subject = f"Sesión #{sesion.id} · {APP_NAME}"
    libro.properties.creator = APP_AUTHOR
    libro.properties.description = (
        "Archivo generado por la aplicación Dulcesitos Castillo. "
        "El catálogo original no fue modificado."
    )
    libro.properties.keywords = "inventario, bodega, SENA, Dulcesitos Castillo"
    libro.save(str(ruta))


def _generar_txt(
    ruta: Path,
    *,
    sesion: Sesion,
    operador: SesionOperador,
    maestro: ArchivoMaestro,
    registros: Sequence[RegistroSesion],
) -> None:
    incluir_stock = bool(maestro.columna_stock)
    incluir_manual = any(r.es_manual for r in registros)
    auditadas = _encabezados_auditoria(
        maestro.columnas,
        incluir_stock=incluir_stock,
        incluir_manual=incluir_manual,
    )
    encabezados = list(maestro.columnas) + auditadas
    por_clave = {r.codigo_clave: r for r in registros}
    claves_maestro = {r.codigo_clave for r in maestro.registros}
    manuales_nuevos = [
        r
        for r in registros
        if r.es_manual and r.codigo_clave not in claves_maestro
    ]
    columnas_lista = list(maestro.columnas)
    indice_stock = (
        columnas_lista.index(maestro.columna_stock)
        if maestro.columna_stock in columnas_lista
        else None
    )
    with ruta.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.writer(
            archivo,
            delimiter="\t",
            lineterminator="\r\n",
            quoting=csv.QUOTE_MINIMAL,
        )
        escritor.writerow(encabezados)
        for registro_maestro in [*maestro.registros, *manuales_nuevos]:
            item = por_clave.get(registro_maestro.codigo_clave)
            fila: list[Any] = [
                _texto_seguro(registro_maestro.campos.get(col, ""))
                for col in maestro.columnas
            ]
            if (
                item is not None
                and item.stock_nuevo is not None
                and indice_stock is not None
            ):
                fila[indice_stock] = formatear_cantidad(item.stock_nuevo)
            if item:
                fila.extend(
                    [
                        "SÍ",
                        a_local(item.escaneado_en).strftime("%d/%m/%Y %H:%M:%S"),
                        item.operador_nombre,
                        item.operador_cedula,
                        sesion.id,
                    ]
                )
            else:
                fila.extend(["NO", "", "", "", sesion.id])
            if incluir_stock:
                if item:
                    original = item.stock_original
                    if original is None:
                        original = convertir_numero(
                            registro_maestro.campos.get(maestro.columna_stock or "", "")
                        )
                    fila.extend(
                        [
                            formatear_cantidad(original),
                            formatear_cantidad(item.stock_nuevo),
                            formatear_cantidad(item.stock_diferencia),
                        ]
                    )
                else:
                    fila.extend(["", "", ""])
            if incluir_manual:
                if item:
                    fila.extend(
                        [
                            "MANUAL" if item.es_manual else "LECTOR",
                            item.novedad if item.es_manual else "",
                        ]
                    )
                else:
                    fila.extend(["", ""])
            escritor.writerow(fila)


# ---------------------------------------------------------------------------
# Reporte PDF
# ---------------------------------------------------------------------------
_ESTILOS_PDF: dict[str, ParagraphStyle] | None = None


def _estilos_pdf() -> dict[str, ParagraphStyle]:
    global _ESTILOS_PDF
    if _ESTILOS_PDF is not None:
        return _ESTILOS_PDF
    base = getSampleStyleSheet()
    _ESTILOS_PDF = {
        "titulo": ParagraphStyle(
            "TituloMarca",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=24,
            leading=28,
            textColor=_color(CACAO),
            alignment=TA_LEFT,
            spaceAfter=2,
        ),
        "subtitulo": ParagraphStyle(
            "SubtituloMarca",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
            textColor=_color(GRIS),
            alignment=TA_LEFT,
        ),
        "seccion": ParagraphStyle(
            "Seccion",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=_color(CACAO),
            spaceBefore=10,
            spaceAfter=6,
        ),
        "cuerpo": ParagraphStyle(
            "Cuerpo",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=10.5,
            textColor=_color(CACAO_SUAVE),
        ),
        "cuerpo_pequeno": ParagraphStyle(
            "CuerpoPequeno",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7,
            leading=8.5,
            textColor=_color(CACAO_SUAVE),
        ),
        "celda_encabezado": ParagraphStyle(
            "CeldaEncabezado",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.2,
            leading=8.2,
            textColor=colors.white,
            alignment=TA_LEFT,
        ),
        "celda_desc": ParagraphStyle(
            "CeldaDescripcion",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.2,
            leading=8.5,
            textColor=_color(CACAO),
        ),
        "celda": ParagraphStyle(
            "Celda",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7,
            leading=8.4,
            textColor=_color(CACAO_SUAVE),
        ),
        "derecha": ParagraphStyle(
            "Derecha",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=7,
            leading=8.4,
            textColor=_color(CACAO_SUAVE),
            alignment=TA_RIGHT,
        ),
        "firma": ParagraphStyle(
            "Firma",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=_color(CACAO_SUAVE),
            alignment=TA_CENTER,
        ),
        "nota": ParagraphStyle(
            "Nota",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=7.2,
            leading=9.5,
            textColor=_color(GRIS),
        ),
    }
    return _ESTILOS_PDF


def _encabezado_pdf(canvas: Any, doc: Any) -> None:
    ancho, alto = landscape(A4)
    canvas.saveState()
    canvas.setFillColor(_color(CACAO))
    canvas.rect(0, alto - 24 * mm, ancho, 24 * mm, fill=1, stroke=0)
    canvas.setFillColor(_color(ROSA))
    canvas.rect(0, alto - 24.8 * mm, ancho, 0.8 * mm, fill=1, stroke=0)

    # Marca gráfica: dos círculos tipo caramelo.
    canvas.setFillColor(_color(ROSA))
    canvas.circle(15 * mm, alto - 12 * mm, 4.2 * mm, fill=1, stroke=0)
    canvas.setFillColor(_color(CARAMELO))
    canvas.circle(19.5 * mm, alto - 12 * mm, 2.5 * mm, fill=1, stroke=0)

    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 14)
    canvas.drawString(26 * mm, alto - 11 * mm, "DULCESITOS CASTILLO")
    canvas.setFillColor(_color("D9C7BB"))
    canvas.setFont("Helvetica", 7.2)
    canvas.drawString(26 * mm, alto - 16 * mm, "REGISTRO Y GESTIÓN DE INVENTARIO · SENA")

    canvas.setFillColor(_color(CARAMELO))
    canvas.setFont("Helvetica-Bold", 8.5)
    canvas.drawRightString(ancho - 14 * mm, alto - 10 * mm, "INVENTARIO DE SESIÓN")
    canvas.setFillColor(_color("D9C7BB"))
    canvas.setFont("Helvetica", 7)
    canvas.drawRightString(
        ancho - 14 * mm,
        alto - 14.6 * mm,
        datetime.now().astimezone().strftime("%d/%m/%Y %H:%M"),
    )
    canvas.restoreState()


def _pie_pdf(canvas: Any, doc: Any) -> None:
    ancho, _ = landscape(A4)
    canvas.saveState()
    canvas.setStrokeColor(_color(BORDE))
    canvas.setLineWidth(0.5)
    canvas.line(14 * mm, 12 * mm, ancho - 14 * mm, 12 * mm)
    canvas.setFillColor(_color(GRIS))
    canvas.setFont("Helvetica", 6.8)
    canvas.drawString(
        14 * mm,
        7.5 * mm,
        "Documento generado automáticamente · El archivo maestro original no fue modificado.",
    )
    canvas.drawRightString(
        ancho - 14 * mm,
        7.5 * mm,
        f"{APP_NAME} · Página {canvas.getPageNumber()}",
    )
    canvas.restoreState()


def _celda_parrafo(texto: str, estilo: str) -> Paragraph:
    return Paragraph(_valor_pdf(texto) or "—", _estilos_pdf()[estilo])


def _tabla_metricas(estadisticas: EstadisticasSesion) -> Table:
    definiciones = [
        ("REGISTRADOS", estadisticas.registrados, "ECFDF5", "047857", "A7F3D0"),
        ("DUPLICADOS", estadisticas.duplicados, "FEF3C7", "92400E", "FDE68A"),
        ("NO ENCONTRADOS", estadisticas.no_encontrados, "FEE2E2", "991B1B", "FECACA"),
        ("LECTURAS TOTALES", estadisticas.total_lecturas, "E0F2FE", "075985", "BAE6FD"),
    ]
    encabezados: list[Paragraph] = []
    valores: list[Paragraph] = []
    for indice, (etiqueta, valor, _fondo, color, _borde) in enumerate(definiciones):
        encabezados.append(
            Paragraph(
                f"<b>{etiqueta}</b>",
                ParagraphStyle(
                    f"EtiquetaMetrica{indice}",
                    parent=_estilos_pdf()["celda_encabezado"],
                    textColor=_color(color),
                    fontSize=6.8,
                ),
            )
        )
        valores.append(
            Paragraph(
                f"<b>{valor}</b>",
                ParagraphStyle(
                    f"Metrica{indice}",
                    parent=_estilos_pdf()["titulo"],
                    fontSize=22,
                    leading=24,
                    textColor=_color(color),
                ),
            )
        )
    tabla = Table(
        [encabezados, valores],
        colWidths=[67.25 * mm] * 4,
        rowHeights=[8 * mm, 15 * mm],
    )
    comandos: list[tuple[Any, ...]] = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LINEBELOW", (0, 0), (-1, -1), 0.7, colors.white),
    ]
    for indice, (_etiqueta, _valor, fondo, _color_hex, borde) in enumerate(definiciones):
        comandos.append(("BACKGROUND", (indice, 0), (indice, -1), _color(fondo)))
        comandos.append(("BOX", (indice, 0), (indice, -1), 0.8, _color(borde)))
    tabla.setStyle(TableStyle(comandos))
    return tabla


def _tabla_info(
    sesion: Sesion,
    operador: SesionOperador,
    autorizacion: ResultadoAutorizacion,
    maestro: ArchivoMaestro,
) -> Table:
    datos = [
        [
            _celda_parrafo("OPERADOR", "celda_encabezado"),
            _celda_parrafo("CÉDULA", "celda_encabezado"),
            _celda_parrafo("SESIÓN", "celda_encabezado"),
            _celda_parrafo("AUTORIZACIÓN DE CIERRE", "celda_encabezado"),
        ],
        [
            _celda_parrafo(operador.nombre, "celda_desc"),
            _celda_parrafo(operador.cedula, "celda"),
            _celda_parrafo(f"#{sesion.id}", "celda"),
            _celda_parrafo(autorizacion.descripcion, "celda"),
        ],
        [
            _celda_parrafo("INICIO", "celda_encabezado"),
            _celda_parrafo("CIERRE", "celda_encabezado"),
            _celda_parrafo("ARCHIVO MAESTRO", "celda_encabezado"),
            _celda_parrafo("HUELLA DEL CATÁLOGO", "celda_encabezado"),
        ],
        [
            _celda_parrafo(formatear_fecha_hora(sesion.inicio_en), "celda"),
            _celda_parrafo(
                formatear_fecha_hora(
                    sesion.fin_en or datetime.now().astimezone()
                ),
                "celda",
            ),
            _celda_parrafo(maestro.nombre, "celda"),
            _celda_parrafo(maestro.huella[:24] + "…", "celda"),
        ],
    ]
    tabla = Table(
        datos,
        colWidths=[65 * mm, 35 * mm, 45 * mm, 124 * mm],
        rowHeights=[7 * mm, 9 * mm, 7 * mm, 9 * mm],
    )
    tabla.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _color(CACAO)),
                ("BACKGROUND", (0, 2), (-1, 2), _color(CACAO)),
                ("BACKGROUND", (0, 1), (-1, 1), _color(CREMA)),
                ("BACKGROUND", (0, 3), (-1, 3), _color(CREMA)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("GRID", (0, 0), (-1, -1), 0.35, _color(BORDE)),
                ("BOX", (0, 0), (-1, -1), 0.6, _color(BORDE)),
            ]
        )
    )
    return tabla


def _tabla_productos(
    maestro: ArchivoMaestro, registros: Sequence[RegistroSesion]
) -> LongTable:
    estilos = _estilos_pdf()
    encabezados = ["#", "CÓDIGO", "DESCRIPCIÓN", "DETALLE DEL CATÁLOGO", "HORA"]
    filas: list[list[Any]] = [
        [Paragraph(_valor_pdf(h), estilos["celda_encabezado"]) for h in encabezados]
    ]
    for indice, registro in enumerate(registros, start=1):
        extras = []
        for columna in maestro.columnas:
            if columna in {
                maestro.columna_codigo,
                maestro.columna_descripcion,
                maestro.columna_stock,
            }:
                continue
            valor = registro.campos.get(columna, "").strip()
            if valor:
                extras.append(f"{columna}: {valor}")
        if registro.stock_nuevo is not None:
            original = (
                formatear_cantidad(registro.stock_original)
                if registro.stock_original is not None
                else "—"
            )
            extras.append(
                f"Stock ajustado: {formatear_cantidad(registro.stock_nuevo)} "
                f"(antes {original})"
            )
        elif maestro.columna_stock:
            valor_stock = registro.campos.get(maestro.columna_stock, "").strip()
            if valor_stock:
                extras.append(f"Stock: {valor_stock}")
        if registro.es_manual:
            extras.append(f"Registro manual: {registro.novedad or 'sin novedad'}")
        detalle = unir_valores(extras) if extras else "Sin campos adicionales"
        filas.append(
            [
                Paragraph(str(indice), estilos["derecha"]),
                Paragraph(_valor_pdf(registro.codigo), estilos["celda"]),
                Paragraph(_valor_pdf(registro.descripcion), estilos["celda_desc"]),
                Paragraph(_valor_pdf(detalle), estilos["celda"]),
                Paragraph(formatear_hora(registro.escaneado_en), estilos["celda"]),
            ]
        )
    tabla = LongTable(
        filas,
        colWidths=[10 * mm, 34 * mm, 62 * mm, 144 * mm, 19 * mm],
        repeatRows=1,
    )
    estilos_tabla = [
        ("BACKGROUND", (0, 0), (-1, 0), _color(CACAO)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 1), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 3.5),
        ("LEFTPADDING", (0, 0), (-1, -1), 3.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3.5),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, _color("E9DDD2")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _color("FFFBF6")]),
        ("ALIGN", (0, 0), (0, -1), "RIGHT"),
    ]
    tabla.setStyle(TableStyle(estilos_tabla))
    return tabla


def _bloque_firmas(
    sesion: Sesion,
    operador: SesionOperador,
    autorizacion: ResultadoAutorizacion,
    maestro: ArchivoMaestro,
) -> KeepTogether:
    estilos = _estilos_pdf()
    linea = Table(
        [
            [
                Paragraph("______________________________", estilos["firma"]),
                Paragraph("______________________________", estilos["firma"]),
            ],
            [
                Paragraph(
                    f"<b>{_valor_pdf(operador.nombre)}</b><br/>"
                    f"C.C. {_valor_pdf(operador.cedula)}<br/>Operador responsable",
                    estilos["firma"],
                ),
                Paragraph(
                    f"<b>Autorización de cierre</b><br/>"
                    f"{_valor_pdf(autorizacion.descripcion)}<br/>"
                    "Supervisión / administración",
                    estilos["firma"],
                ),
            ],
        ],
        colWidths=[90 * mm, 90 * mm],
    )
    linea.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]
        )
    )
    sello = Table(
        [
            [
                Paragraph(
                    "<b>SELLO DE INTEGRIDAD</b>",
                    ParagraphStyle(
                        "SelloTitulo",
                        parent=estilos["celda_encabezado"],
                        textColor=_color(CARAMELO),
                    ),
                )
            ],
            [
                Paragraph(
                    f"Sesión <b>#{sesion.id}</b> · Catálogo <b>{_valor_pdf(maestro.nombre)}</b><br/>"
                    f"SHA-256: <font face='Courier'>{_valor_pdf(maestro.huella)}</font><br/>"
                    "Este reporte corresponde a la sesión registrada en la base local. "
                    "Conserva el archivo maestro original junto con este documento.",
                    estilos["cuerpo_pequeno"],
                )
            ],
        ],
        colWidths=[180 * mm],
    )
    sello.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _color("FFFBEB")),
                ("BOX", (0, 0), (-1, -1), 0.7, _color(CARAMELO)),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                ("BOTTOMPADDING", (0, -1), (-1, -1), 6),
            ]
        )
    )
    return KeepTogether(
        [
            Spacer(1, 8 * mm),
            _celda_parrafo("CONSTANCIA Y FIRMAS", "seccion"),
            linea,
            Spacer(1, 5 * mm),
            sello,
        ]
    )


def _generar_pdf(
    ruta: Path,
    *,
    sesion: Sesion,
    operador: SesionOperador,
    autorizacion: ResultadoAutorizacion,
    maestro: ArchivoMaestro,
    registros: Sequence[RegistroSesion],
    estadisticas: EstadisticasSesion,
) -> None:
    doc = SimpleDocTemplate(
        str(ruta),
        pagesize=landscape(A4),
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=30 * mm,
        bottomMargin=18 * mm,
        title=f"Inventario de sesión #{sesion.id}",
        author=f"{APP_NAME} · {operador.nombre}",
        subject="Reporte visual de inventario",
        creator="Dulcesitos Castillo",
    )
    estilos = _estilos_pdf()
    historia: list[Any] = []
    historia.append(Spacer(1, 1 * mm))
    historia.append(Paragraph("Inventario de la sesión", estilos["titulo"]))
    historia.append(
        Paragraph(
            f"Acta de registro · {_valor_pdf(operador.nombre)} · "
            f"{_valor_pdf(maestro.nombre)}",
            estilos["subtitulo"],
        )
    )
    historia.append(Spacer(1, 4 * mm))
    historia.append(_tabla_metricas(estadisticas))
    historia.append(Spacer(1, 3 * mm))
    historia.append(_tabla_info(sesion, operador, autorizacion, maestro))
    historia.append(Spacer(1, 2 * mm))
    historia.append(
        Paragraph(
            f"Ajustes de stock aplicados: <b>{estadisticas.ajustes_stock}</b> · "
            f"Registros manuales: <b>{estadisticas.manuales}</b>",
            estilos["nota"],
        )
    )
    historia.append(Spacer(1, 3 * mm))
    historia.append(
        Paragraph(
            f"PRODUCTOS REGISTRADOS · {len(registros)} en total",
            estilos["seccion"],
        )
    )

    # La tabla se coloca en varias páginas si es necesario; el encabezado se repite.
    if registros:
        historia.append(_tabla_productos(maestro, registros))
    else:
        historia.append(
            Paragraph("No se registraron productos en la sesión.", estilos["nota"])
        )
    historia.append(PageBreak())
    historia.append(Paragraph("Cierre y trazabilidad", estilos["titulo"]))
    historia.append(
        Paragraph(
            "Resumen de control, responsables y sello de integridad del reporte.",
            estilos["subtitulo"],
        )
    )
    historia.append(Spacer(1, 4 * mm))
    historia.append(_tabla_metricas(estadisticas))
    historia.append(Spacer(1, 4 * mm))
    historia.append(_tabla_info(sesion, operador, autorizacion, maestro))
    historia.append(_bloque_firmas(sesion, operador, autorizacion, maestro))
    doc.build(
        historia,
        onFirstPage=_decorar_pdf,
        onLaterPages=_decorar_pdf,
    )


def _decorar_pdf(canvas: Any, doc: Any) -> None:
    _encabezado_pdf(canvas, doc)
    _pie_pdf(canvas, doc)


def _limpiar_si_falla(rutas: Sequence[Path]) -> None:
    for ruta in rutas:
        try:
            ruta.unlink(missing_ok=True)
        except OSError:
            pass


def generar_exportaciones(
    *,
    sesion: Sesion,
    operador: SesionOperador,
    autorizacion: ResultadoAutorizacion,
    maestro: ArchivoMaestro,
    registros: Sequence[RegistroSesion],
    estadisticas: EstadisticasSesion,
    carpeta_salida: str | Path,
) -> list[ArchivoGenerado]:
    """Genera los tres archivos y devuelve sus rutas verificadas."""

    if not registros:
        raise ErrorExportacion("No hay registros para exportar.")
    carpeta = Path(carpeta_salida)
    try:
        carpeta.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ErrorExportacion(
            f"No se pudo crear la carpeta de salida {carpeta}: {exc}"
        ) from exc
    if not os.access(carpeta, os.W_OK):
        raise ErrorExportacion(
            f"La carpeta de salida no tiene permisos de escritura: {carpeta}"
        )

    ahora = datetime.now().astimezone()
    base, base_reporte = _base_archivos(operador, ahora)
    sufijo = 1
    while True:
        candidato_base = base if sufijo == 1 else f"{base}_{sufijo}"
        candidato_reporte = base_reporte if sufijo == 1 else f"{base_reporte}_{sufijo}"
        ruta_xlsx = carpeta / f"{candidato_base}.xlsx"
        ruta_txt = carpeta / f"{candidato_base}.txt"
        ruta_pdf = carpeta / f"{candidato_reporte}.pdf"
        if not (ruta_xlsx.exists() or ruta_txt.exists() or ruta_pdf.exists()):
            break
        sufijo += 1

    nombres = {
        "Excel": ruta_xlsx.name,
        "PDF visual / imprimible": ruta_pdf.name,
        "Texto": ruta_txt.name,
    }
    generados: list[Path] = [ruta_xlsx, ruta_txt, ruta_pdf]
    try:
        _generar_excel(
            ruta_xlsx,
            sesion=sesion,
            operador=operador,
            autorizacion=autorizacion,
            maestro=maestro,
            registros=registros,
            estadisticas=estadisticas,
            nombres=nombres,
        )
        if not ruta_xlsx.exists() or ruta_xlsx.stat().st_size == 0:
            raise ErrorExportacion("El archivo Excel quedó vacío.")

        _generar_txt(
            ruta_txt,
            sesion=sesion,
            operador=operador,
            maestro=maestro,
            registros=registros,
        )
        if not ruta_txt.exists() or ruta_txt.stat().st_size == 0:
            raise ErrorExportacion("El archivo de texto quedó vacío.")

        _generar_pdf(
            ruta_pdf,
            sesion=sesion,
            operador=operador,
            autorizacion=autorizacion,
            maestro=maestro,
            registros=registros,
            estadisticas=estadisticas,
        )
        if not ruta_pdf.exists() or ruta_pdf.stat().st_size == 0:
            raise ErrorExportacion("El reporte PDF quedó vacío.")
    except Exception as exc:
        _limpiar_si_falla(generados)
        if isinstance(exc, ErrorExportacion):
            raise
        LOG.exception("Error generando exportaciones")
        raise ErrorExportacion(
            f"No se pudieron generar los archivos de cierre: {exc}"
        ) from exc

    archivos = [
        ArchivoGenerado(tipo="xlsx", ruta=ruta_xlsx, tamano_bytes=ruta_xlsx.stat().st_size),
        ArchivoGenerado(tipo="pdf", ruta=ruta_pdf, tamano_bytes=ruta_pdf.stat().st_size),
        ArchivoGenerado(tipo="txt", ruta=ruta_txt, tamano_bytes=ruta_txt.stat().st_size),
    ]
    LOG.info("Exportaciones generadas en %s", carpeta)
    return archivos
