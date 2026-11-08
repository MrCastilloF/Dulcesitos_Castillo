"""Crea el resumen ejecutivo en Word con las capturas exitosas de la app."""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

RAIZ = Path(__file__).resolve().parent.parent
ENTREGA = RAIZ / "docs" / "entrega"
ASSETS = ENTREGA / "assets"
CAPTURAS = RAIZ / "docs" / "capturas"
DESTINO = ENTREGA / "Resumen_Ejecutivo_Dulcesitos_Castillo.docx"

NEGRO = RGBColor(0x0B, 0x07, 0x06)
CACAO = RGBColor(0x2B, 0x1A, 0x15)
TEXTO = RGBColor(0x3B, 0x2A, 0x24)
MUTED = RGBColor(0x7C, 0x6A, 0x61)
CREMA = RGBColor(0xFB, 0xF6, 0xF1)
ROSA = RGBColor(0xE9, 0x6A, 0x8D)
ROSA_OSCURA = RGBColor(0xB8, 0x3E, 0x5E)
CARAMELO = RGBColor(0xC2, 0x8A, 0x2C)
AMARILLO = RGBColor(0xF2, 0xB8, 0x4B)
VERDE = RGBColor(0x16, 0x7A, 0x4A)
VERDE_CLARO = RGBColor(0xD1, 0xFA, 0xE5)
AZUL = RGBColor(0x1D, 0x4E, 0xD8)
AZUL_FONDO = RGBColor(0xE8, 0xF1, 0xFD)
CREMA_FONDO = RGBColor(0xFB, 0xF6, 0xF1)
GRIS_FONDO = RGBColor(0xF5, 0xEF, 0xEA)
BORDE = RGBColor(0xE4, 0xD7, 0xCE)
BLANCO = RGBColor(0xFF, 0xFF, 0xFF)
AMBAR_TEXTO = RGBColor(0x8A, 0x5A, 0x12)
AMBAR_CUERPO = RGBColor(0x5B, 0x3D, 0x21)


def _sombrear(celda, color: str) -> None:
    tc_pr = celda._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), color)
    tc_pr.append(shd)


def _borde_celda(celda, borde: str, tamano: float, color: str) -> None:
    tc_pr = celda._tc.get_or_add_tcPr()
    bordes = tc_pr.first_child_found_in("w:tcBorders")
    if bordes is None:
        bordes = OxmlElement("w:tcBorders")
        tc_pr.append(bordes)
    elemento = OxmlElement(f"w:{borde}")
    elemento.set(qn("w:val"), "single")
    elemento.set(qn("w:sz"), str(int(tamano * 8)))
    elemento.set(qn("w:space"), "0")
    elemento.set(qn("w:color"), color)
    bordes.append(elemento)


def _sin_bordes(tabla) -> None:
    tbl_pr = tabla._tbl.tblPr
    bordes = OxmlElement("w:tblBorders")
    for lado in ("top", "left", "bottom", "right", "insideH", "insideV"):
        elemento = OxmlElement(f"w:{lado}")
        elemento.set(qn("w:val"), "nil")
        bordes.append(elemento)
    tbl_pr.append(bordes)


def _margen_celda(celda, arriba: float, abajo: float, izquierda: float, derecha: float) -> None:
    tc_pr = celda._tc.get_or_add_tcPr()
    margenes = tc_pr.first_child_found_in("w:tcMar")
    if margenes is None:
        margenes = OxmlElement("w:tcMar")
        tc_pr.append(margenes)
    for lado, valor in (
        ("top", arriba),
        ("bottom", abajo),
        ("left", izquierda),
        ("right", derecha),
    ):
        elemento = OxmlElement(f"w:{lado}")
        elemento.set(qn("w:w"), str(int(valor * 567)))
        elemento.set(qn("w:type"), "dxa")
        margenes.append(elemento)


def _parrafo(
    doc,
    texto: str = "",
    *,
    tamano: float = 10,
    color: RGBColor = TEXTO,
    negrita: bool = False,
    cursiva: bool = False,
    fuente: str = "Segoe UI",
    espacio_antes: float = 0,
    espacio_despues: float = 4,
    alineacion=WD_ALIGN_PARAGRAPH.LEFT,
    interlineado: float = 1.12,
    mantener: bool = False,
):
    p = doc.add_paragraph()
    p.alignment = alineacion
    p.paragraph_format.space_before = Pt(espacio_antes)
    p.paragraph_format.space_after = Pt(espacio_despues)
    p.paragraph_format.line_spacing = interlineado
    p.paragraph_format.keep_with_next = mantener
    run = p.add_run(texto)
    run.font.name = fuente
    run.font.size = Pt(tamano)
    run.font.color.rgb = color
    run.bold = negrita
    run.italic = cursiva
    return p


def _kicker(doc, texto: str, *, nueva_pagina: bool = False) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(5)
    p.paragraph_format.line_spacing = 1
    if nueva_pagina:
        p.paragraph_format.page_break_before = True
    run = p.add_run("▍  ")
    run.font.name = "Segoe UI"
    run.font.size = Pt(9)
    run.font.color.rgb = ROSA
    run2 = p.add_run(texto.upper())
    run2.font.name = "Segoe UI Semibold"
    run2.font.size = Pt(8)
    run2.font.color.rgb = ROSA_OSCURA
    r_pr = run2._element.get_or_add_rPr()
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:val"), "26")
    r_pr.append(spacing)


def _titulo(doc, texto: str, *, tamano: float = 25) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.line_spacing = 0.95
    p.paragraph_format.keep_with_next = True
    run = p.add_run(texto)
    run.font.name = "Segoe UI"
    run.font.size = Pt(tamano)
    run.font.bold = True
    run.font.color.rgb = CACAO


def _lede(doc, texto: str) -> None:
    _parrafo(
        doc,
        texto,
        tamano=10.5,
        color=MUTED,
        espacio_despues=9,
        interlineado=1.18,
    )


def _imagen(doc, ruta: Path, ancho_cm: float, caption: str, alt: str = "") -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.keep_with_next = True
    run = p.add_run()
    inline = run.add_picture(str(ruta), width=Cm(ancho_cm))
    if alt:
        inline._inline.docPr.set("descr", alt)
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.LEFT
    cap.paragraph_format.space_before = Pt(0)
    cap.paragraph_format.space_after = Pt(6)
    cap.paragraph_format.line_spacing = 1
    r1 = cap.add_run("FIGURA · ")
    r1.font.name = "Segoe UI Semibold"
    r1.font.size = Pt(7)
    r1.font.color.rgb = ROSA_OSCURA
    r2 = cap.add_run(caption)
    r2.font.name = "Segoe UI"
    r2.font.size = Pt(7.4)
    r2.font.color.rgb = MUTED


def _tabla_base(doc, filas: int, columnas: int, *, ancho: float = 17.3):
    tabla = doc.add_table(rows=filas, cols=columnas)
    tabla.alignment = WD_TABLE_ALIGNMENT.CENTER
    tabla.autofit = False
    _sin_bordes(tabla)
    for fila in tabla.rows:
        tr_pr = fila._tr.get_or_add_trPr()
        cant_split = OxmlElement("w:cantSplit")
        tr_pr.append(cant_split)
        for celda in fila.cells:
            _margen_celda(celda, 0.08, 0.08, 0.1, 0.1)
            celda.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
    return tabla


def _ancho_columna(tabla, indice: int, ancho_cm: float) -> None:
    for fila in tabla.rows:
        fila.cells[indice].width = Cm(ancho_cm)


def _callout(
    doc,
    titulo: str,
    texto: str,
    *,
    fondo: str = "FFF6E8",
    borde: str = "C28A2C",
    color_titulo: RGBColor = AMBAR_TEXTO,
    color_texto: RGBColor = AMBAR_CUERPO,
) -> None:
    tabla = _tabla_base(doc, 1, 1)
    celda = tabla.cell(0, 0)
    _sombrear(celda, fondo)
    _borde_celda(celda, "left", 4.0, borde)
    _margen_celda(celda, 0.25, 0.25, 0.35, 0.3)
    p = celda.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(titulo)
    r.font.name = "Segoe UI Semibold"
    r.font.size = Pt(8.2)
    r.font.color.rgb = color_titulo
    p2 = celda.add_paragraph()
    p2.paragraph_format.space_after = Pt(0)
    p2.paragraph_format.line_spacing = 1.08
    r2 = p2.add_run(texto)
    r2.font.name = "Segoe UI"
    r2.font.size = Pt(9)
    r2.font.color.rgb = color_texto
    doc.add_paragraph().paragraph_format.space_after = Pt(1)


def _tabla_kpi(doc) -> None:
    tabla = _tabla_base(doc, 1, 4)
    datos = [
        ("01", "administrador único", "sin crear otros roles", "E96A8D"),
        ("0", "claves en texto plano", "PBKDF2 + sal aleatoria", "C28A2C"),
        ("03", "salidas por sesión", "Excel · PDF · TXT", "1D4ED8"),
        ("100%", "trazabilidad", "producto · hora · operador", "167A4A"),
    ]
    for i, (valor, titulo, detalle, color) in enumerate(datos):
        celda = tabla.cell(0, i)
        _ancho_columna(tabla, i, 4.3)
        _sombrear(celda, "FBF6F1")
        _borde_celda(celda, "top", 3.0, color)
        _margen_celda(celda, 0.24, 0.2, 0.28, 0.22)
        p = celda.paragraphs[0]
        p.paragraph_format.space_after = Pt(1)
        r = p.add_run(valor)
        r.font.name = "Segoe UI"
        r.font.size = Pt(24 if valor != "100%" else 20)
        r.font.bold = True
        r.font.color.rgb = RGBColor.from_string(color)
        p2 = celda.add_paragraph()
        p2.paragraph_format.space_after = Pt(1)
        r2 = p2.add_run(titulo)
        r2.font.name = "Segoe UI Semibold"
        r2.font.size = Pt(8.2)
        r2.font.color.rgb = CACAO
        p3 = celda.add_paragraph()
        p3.paragraph_format.space_after = Pt(2)
        r3 = p3.add_run(detalle)
        r3.font.name = "Segoe UI"
        r3.font.size = Pt(7.2)
        r3.font.color.rgb = MUTED
    doc.add_paragraph().paragraph_format.space_after = Pt(1)


def _tarjeta_rol(
    doc,
    *,
    titulo: str,
    etiqueta: str,
    puntos: list[str],
    oscuro: bool,
) -> None:
    tabla = _tabla_base(doc, 2, 2)
    _ancho_columna(tabla, 0, 8.6)
    _ancho_columna(tabla, 1, 8.6)
    tabla.rows[0].height = Cm(0.1)
    celda = tabla.cell(0, 0).merge(tabla.cell(1, 0))
    _sombrear(celda, "1B100C" if oscuro else "FBF6F1")
    if not oscuro:
        _borde_celda(celda, "top", 3, "E96A8D")
    _margen_celda(celda, 0.28, 0.28, 0.32, 0.3)
    p = celda.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run(etiqueta.upper())
    r.font.name = "Segoe UI Semibold"
    r.font.size = Pt(7)
    r.font.color.rgb = AMARILLO if oscuro else ROSA_OSCURA
    p2 = celda.add_paragraph()
    p2.paragraph_format.space_after = Pt(4)
    r2 = p2.add_run(titulo)
    r2.font.name = "Segoe UI"
    r2.font.size = Pt(14)
    r2.font.bold = True
    r2.font.color.rgb = CREMA if oscuro else CACAO
    for punto in puntos:
        p3 = celda.add_paragraph()
        p3.paragraph_format.space_after = Pt(2)
        p3.paragraph_format.line_spacing = 1.05
        r3 = p3.add_run("·  ")
        r3.font.name = "Segoe UI"
        r3.font.size = Pt(9)
        r3.font.color.rgb = ROSA if oscuro else ROSA_OSCURA
        r4 = p3.add_run(punto)
        r4.font.name = "Segoe UI"
        r4.font.size = Pt(8.5)
        r4.font.color.rgb = RGBColor(0xE8, 0xDD, 0xD7) if oscuro else TEXTO
    # La segunda columna se ocupa después con la otra tarjeta.
    return tabla


def _tres_tarjetas(doc, items: list[tuple[str, str, str]], colores: list[str]) -> None:
    tabla = _tabla_base(doc, 1, 3)
    for i, (titulo, subtitulo, texto) in enumerate(items):
        c = tabla.cell(0, i)
        _ancho_columna(tabla, i, 5.65)
        _sombrear(c, "FBF6F1")
        _borde_celda(c, "top", 2.5, colores[i])
        _margen_celda(c, 0.2, 0.18, 0.24, 0.2)
        p = c.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(subtitulo.upper())
        r.font.name = "Segoe UI Semibold"
        r.font.size = Pt(6.4)
        r.font.color.rgb = RGBColor.from_string(colores[i])
        p = c.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(titulo)
        r.font.name = "Segoe UI Semibold"
        r.font.size = Pt(8.6)
        r.font.color.rgb = CACAO
        p = c.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.04
        r = p.add_run(texto)
        r.font.name = "Segoe UI"
        r.font.size = Pt(7.4)
        r.font.color.rgb = TEXTO


def _cita(doc, texto: str) -> None:
    tabla = _tabla_base(doc, 1, 1)
    c = tabla.cell(0, 0)
    _sombrear(c, "1B100C")
    _margen_celda(c, 0.25, 0.25, 0.32, 0.3)
    p = c.paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.05
    r = p.add_run("“")
    r.font.name = "Georgia"
    r.font.size = Pt(22)
    r.font.color.rgb = AMARILLO
    r2 = p.add_run(texto)
    r2.font.name = "Segoe UI"
    r2.font.size = Pt(10)
    r2.font.italic = True
    r2.font.color.rgb = CREMA


def _checklist_compacta(doc, items: list[str]) -> None:
    tabla = _tabla_base(doc, 2, 2)
    _ancho_columna(tabla, 0, 8.55)
    _ancho_columna(tabla, 1, 8.55)
    for i, item in enumerate(items):
        c = tabla.cell(i // 2, i % 2)
        _margen_celda(c, 0.08, 0.08, 0.1, 0.1)
        p = c.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run("☐  ")
        r.font.name = "Segoe UI"
        r.font.size = Pt(8.5)
        r.font.color.rgb = ROSA_OSCURA
        r2 = p.add_run(item)
        r2.font.name = "Segoe UI"
        r2.font.size = Pt(8)
        r2.font.color.rgb = TEXTO


def _pasos(doc, pasos: list[str]) -> None:
    tabla = _tabla_base(doc, len(pasos), 2)
    _ancho_columna(tabla, 0, 1.1)
    _ancho_columna(tabla, 1, 16.2)
    for i, texto in enumerate(pasos, start=1):
        n = tabla.cell(i - 1, 0)
        t = tabla.cell(i - 1, 1)
        _margen_celda(n, 0.08, 0.08, 0.05, 0.05)
        _margen_celda(t, 0.08, 0.08, 0.1, 0.1)
        p = n.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(f"{i:02d}")
        r.font.name = "Segoe UI"
        r.font.size = Pt(10)
        r.font.bold = True
        r.font.color.rgb = ROSA_OSCURA
        p2 = t.paragraphs[0]
        p2.paragraph_format.space_after = Pt(0)
        p2.paragraph_format.line_spacing = 1.05
        r2 = p2.add_run(texto)
        r2.font.name = "Segoe UI"
        r2.font.size = Pt(9)
        r2.font.color.rgb = TEXTO


def _encabezado_pie(seccion, titulo: str) -> None:
    seccion.header.is_linked_to_previous = False
    seccion.footer.is_linked_to_previous = False
    hp = seccion.header.paragraphs[0]
    hp.paragraph_format.space_after = Pt(0)
    hp.paragraph_format.tab_stops.add_tab_stop(Cm(17.6), WD_TAB_ALIGNMENT.RIGHT)
    hr = hp.add_run("DULCESITOS CASTILLO")
    hr.font.name = "Segoe UI Semibold"
    hr.font.size = Pt(7)
    hr.font.color.rgb = CACAO
    hr2 = hp.add_run("\tRESUMEN EJECUTIVO · 2026")
    hr2.font.name = "Segoe UI"
    hr2.font.size = Pt(7)
    hr2.font.color.rgb = MUTED
    p_pr = hp._p.get_or_add_pPr()
    p_bdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), "4")
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), "E4D7CE")
    p_bdr.append(bottom)
    p_pr.append(p_bdr)

    fp = seccion.footer.paragraphs[0]
    fp.paragraph_format.space_before = Pt(2)
    fp.paragraph_format.tab_stops.add_tab_stop(Cm(17.6), WD_TAB_ALIGNMENT.RIGHT)
    fr = fp.add_run("Operación de bodega · SENA  |  ")
    fr.font.name = "Segoe UI"
    fr.font.size = Pt(7)
    fr.font.color.rgb = MUTED
    _campo_pagina(fp, "PAGE")
    fr2 = fp.add_run(" de ")
    fr2.font.name = "Segoe UI"
    fr2.font.size = Pt(7)
    fr2.font.color.rgb = MUTED
    _campo_pagina(fp, "NUMPAGES")


def _campo_pagina(parrafo, instruccion: str) -> None:
    run = parrafo.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = f" {instruccion} "
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    txt = OxmlElement("w:t")
    txt.text = "1"
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr)
    run._r.append(fld_sep)
    run._r.append(txt)
    run._r.append(fld_end)
    run.font.name = "Segoe UI"
    run.font.size = Pt(7)
    run.font.color.rgb = MUTED


def _tabla_problemas(doc) -> None:
    filas = [
        ("El lector no aparece", "Revisa el cable USB, pulsa «Volver a detectar» y calibra."),
        ("El código no se lee", "Pulsa «Registro manual». El lector se pausa y puedes digitar código, descripción y novedad."),
        ("El código no existe en el maestro", "Regístralo manualmente; se incluye en la salida con la novedad."),
        ("El producto está dado de baja", "No se puede registrar. El administrador debe reactivarlo en «Catálogo»."),
        ("El acceso venció o fue revocado", "La estación se bloquea. El administrador renueva y autoriza el cierre."),
        ("La aplicación no abre", "Ejecuta diagnostico.bat y revisa %LOCALAPPDATA%\\DulcesitosCastillo\\logs."),
        ("No se puede escribir en C:\\dulcesito_castillo", "Usa una cuenta con permisos sobre C:\\ o instala en una carpeta autorizada."),
        ("El PDF no se genera", "Verifica que el reporte PDF esté disponible y que la carpeta de salidas tenga permisos."),
    ]
    tabla = _tabla_base(doc, len(filas) + 1, 2)
    _ancho_columna(tabla, 0, 4.55)
    _ancho_columna(tabla, 1, 12.75)
    for i, (sintoma, accion) in enumerate(filas, start=1):
        c0, c1 = tabla.cell(i, 0), tabla.cell(i, 1)
        _sombrear(c0, "FFFFFF" if i % 2 else "FBF6F1")
        _sombrear(c1, "FFFFFF" if i % 2 else "FBF6F1")
        _margen_celda(c0, 0.1, 0.1, 0.15, 0.1)
        _margen_celda(c1, 0.1, 0.1, 0.15, 0.1)
        p0 = c0.paragraphs[0]
        p0.paragraph_format.space_after = Pt(0)
        r0 = p0.add_run(sintoma)
        r0.font.name = "Segoe UI Semibold"
        r0.font.size = Pt(8.1)
        r0.font.color.rgb = CACAO
        p1 = c1.paragraphs[0]
        p1.paragraph_format.space_after = Pt(0)
        p1.paragraph_format.line_spacing = 1.05
        r1 = p1.add_run(accion)
        r1.font.name = "Segoe UI"
        r1.font.size = Pt(8)
        r1.font.color.rgb = TEXTO
    # Encabezado creado aparte para controlar el orden visual.
    tabla._tbl.remove(tabla.rows[0]._tr)
    encabezado = tabla.add_row()
    # add_row agrega al final; se mueve al inicio.
    tabla._tbl.remove(encabezado._tr)
    tabla._tbl.insert(1, encabezado._tr)
    c0, c1 = encabezado.cells
    _sombrear(c0, "1B100C")
    _sombrear(c1, "1B100C")
    _margen_celda(c0, 0.13, 0.13, 0.15, 0.1)
    _margen_celda(c1, 0.13, 0.13, 0.15, 0.1)
    p0 = c0.paragraphs[0]
    r0 = p0.add_run("SÍNTOMA")
    r0.font.name = "Segoe UI Semibold"
    r0.font.size = Pt(7.2)
    r0.font.color.rgb = AMARILLO
    p1 = c1.paragraphs[0]
    r1 = p1.add_run("QUÉ HACER")
    r1.font.name = "Segoe UI Semibold"
    r1.font.size = Pt(7.2)
    r1.font.color.rgb = AMARILLO


def _checklist(doc) -> None:
    items = [
        "Archivo maestro real en C:\\dulcesito_castillo (sin DEMO).",
        "Acceso del administrador configurado y clave resguardada.",
        "Códigos de operador vigentes, con vencimiento definido.",
        "Lector calibrado: «Prueba Match Sincronización OK».",
        "Sesión cerrada y archivos de salida revisados.",
    ]
    tabla = _tabla_base(doc, 1, 2)
    _ancho_columna(tabla, 0, 8.6)
    _ancho_columna(tabla, 1, 8.6)
    for i, item in enumerate(items):
        celda = tabla.cell(0, 0 if i < 3 else 1)
        if i == 0:
            celda.paragraphs[0].text = ""
        p = celda.paragraphs[0] if i in (0, 3) else celda.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run("☐  ")
        r.font.name = "Segoe UI"
        r.font.size = Pt(9)
        r.font.color.rgb = ROSA_OSCURA
        r2 = p.add_run(item)
        r2.font.name = "Segoe UI"
        r2.font.size = Pt(8.2)
        r2.font.color.rgb = TEXTO


def construir() -> Path:
    doc = Document()
    doc.core_properties.title = "Dulcesitos Castillo · Resumen ejecutivo de operación"
    doc.core_properties.subject = "Inventario de bodega, roles, accesos y operación"
    doc.core_properties.author = "Carlos Castillo · SENA"
    doc.core_properties.keywords = "Dulcesitos Castillo, inventario, SENA, bodega, resumen ejecutivo"
    doc.core_properties.comments = (
        "Documento de demostración. Las capturas usan el catálogo DEMO y datos de ejemplo."
    )

    normal = doc.styles["Normal"]
    normal.font.name = "Segoe UI"
    normal.font.size = Pt(10)
    normal.font.color.rgb = TEXTO
    normal.paragraph_format.space_after = Pt(4)
    normal.paragraph_format.line_spacing = 1.12

    cover = doc.sections[0]
    cover.page_width = Cm(21)
    cover.page_height = Cm(29.7)
    cover.top_margin = Cm(0)
    cover.bottom_margin = Cm(0)
    cover.left_margin = Cm(0)
    cover.right_margin = Cm(0)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.add_run().add_picture(str(ASSETS / "portada.png"), width=Cm(21), height=Cm(29.7))

    sec = doc.add_section(WD_SECTION.NEW_PAGE)
    sec.page_width = Cm(21)
    sec.page_height = Cm(29.7)
    sec.top_margin = Cm(1.5)
    sec.bottom_margin = Cm(1.35)
    sec.left_margin = Cm(1.7)
    sec.right_margin = Cm(1.7)
    sec.header_distance = Cm(0.75)
    sec.footer_distance = Cm(0.65)
    _encabezado_pie(sec, "RESUMEN EJECUTIVO")

    # Página 2 · visión ejecutiva.
    _kicker(doc, "01 · EN UNA PÁGINA")
    _titulo(doc, "La bodega, bajo control.", tamano=25)
    _lede(
        doc,
        "Dulcesitos Castillo convierte el inventario en un flujo guiado: un administrador "
        "único habilita accesos, el operador valida productos y ajusta stock, y al cierre "
        "se generan tres archivos auditables. Sin planillas paralelas y sin claves en texto plano.",
    )
    _tabla_kpi(doc)
    _imagen(
        doc,
        ASSETS / "flujo_operativo.png",
        17.2,
        "Flujo operativo completo: del acceso único al cierre con Excel, PDF y TXT.",
        "Diagrama de seis pasos: configura, emite, calibra, escanea, manual y cierra.",
    )
    _parrafo(doc, "DOS MODOS, UNA MISMA VERDAD", tamano=7.4, color=ROSA_OSCURA, negrita=True, espacio_despues=4)
    tabla_roles = _tabla_base(doc, 1, 2)
    _ancho_columna(tabla_roles, 0, 8.55)
    _ancho_columna(tabla_roles, 1, 8.55)
    celda_admin = tabla_roles.cell(0, 0)
    celda_oper = tabla_roles.cell(0, 1)
    for celda, fondo, borde in (
        (celda_admin, "1B100C", "E96A8D"),
        (celda_oper, "FBF6F1", "C28A2C"),
    ):
        _sombrear(celda, fondo)
        _borde_celda(celda, "top", 4, borde)
        _margen_celda(celda, 0.3, 0.25, 0.3, 0.28)
    # Administrador.
    p = celda_admin.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run("MODO ADMINISTRADOR · ÚNICO")
    r.font.name = "Segoe UI Semibold"
    r.font.size = Pt(6.8)
    r.font.color.rgb = AMARILLO
    p = celda_admin.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run("La llave de la operación")
    r.font.name = "Segoe UI"
    r.font.size = Pt(13)
    r.font.bold = True
    r.font.color.rgb = CREMA
    for linea in [
        "Configura su acceso una sola vez.",
        "Emite, renueva y revoca códigos.",
        "Crea, da de baja o reactiva productos.",
        "Autoriza cierres y consulta historial.",
    ]:
        q = celda_admin.add_paragraph()
        q.paragraph_format.space_after = Pt(2)
        q.paragraph_format.line_spacing = 1.05
        rr = q.add_run("·  " + linea)
        rr.font.name = "Segoe UI"
        rr.font.size = Pt(8)
        rr.font.color.rgb = RGBColor(0xEA, 0xDF, 0xD8)
    # Operador.
    p = celda_oper.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run("MODO OPERADOR · CON ACCESO")
    r.font.name = "Segoe UI Semibold"
    r.font.size = Pt(6.8)
    r.font.color.rgb = ROSA_OSCURA
    p = celda_oper.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run("La operación en la estación")
    r.font.name = "Segoe UI"
    r.font.size = Pt(13)
    r.font.bold = True
    r.font.color.rgb = CACAO
    for linea in [
        "Ingresa con cédula y código vigente.",
        "Calibra con un producto real.",
        "Escanea, valida y ajusta stock.",
        "Registra manual si el lector falla.",
    ]:
        q = celda_oper.add_paragraph()
        q.paragraph_format.space_after = Pt(2)
        q.paragraph_format.line_spacing = 1.05
        rr = q.add_run("·  " + linea)
        rr.font.name = "Segoe UI"
        rr.font.size = Pt(8)
        rr.font.color.rgb = TEXTO
    _parrafo(
        doc,
        "El operador no ve botones de administración, catálogo ni configuración del lector.",
        tamano=7.8,
        color=MUTED,
        cursiva=True,
        espacio_antes=3,
        espacio_despues=6,
    )
    _parrafo(doc, "LO QUE RESUELVE", tamano=7.4, color=ROSA_OSCURA, negrita=True, espacio_antes=1, espacio_despues=3)
    _tres_tarjetas(
        doc,
        [
            (
                "Acceso con reloj",
                "CONTROL",
                "Códigos con vigencia, revocación y renovación. El operador no tiene una llave permanente.",
            ),
            (
                "Catálogo vivo",
                "BODEGA",
                "Altas y bajas locales con historial. El Excel maestro se conserva sin cambios.",
            ),
            (
                "Cierre que se imprime",
                "SALIDA",
                "PDF con firmas, Excel de actualización y TXT para integrar. Todo en una misma carpeta.",
            ),
        ],
        ["E96A8D", "C28A2C", "1D4ED8"],
    )
    _cita(
        doc,
        "La velocidad no está reñida con el control. Una bodega puede trabajar rápido y dejar rastro de cada decisión.",
    )
    _parrafo(doc, "FICHA TÉCNICA", tamano=7.4, color=ROSA_OSCURA, negrita=True, espacio_antes=4, espacio_despues=3)
    ficha = _tabla_base(doc, 1, 4)
    for i, (titulo, valor, detalle) in enumerate(
        [
            ("ENTORNO", "Windows 10/11", "EXE o Python 3.10+"),
            ("OPERACIÓN", "100% local", "Sin nube obligatoria"),
            ("PERSISTENCIA", "SQLite", "Reanuda sesiones"),
            ("SALIDAS", "03 formatos", "Excel · PDF · TXT"),
        ]
    ):
        c = ficha.cell(0, i)
        _ancho_columna(ficha, i, 4.25)
        _sombrear(c, "FBF6F1")
        _margen_celda(c, 0.15, 0.12, 0.2, 0.15)
        p = c.paragraphs[0]
        p.paragraph_format.space_after = Pt(1)
        r = p.add_run(titulo)
        r.font.name = "Segoe UI Semibold"
        r.font.size = Pt(6)
        r.font.color.rgb = MUTED
        p = c.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(valor)
        r.font.name = "Segoe UI"
        r.font.size = Pt(9)
        r.font.bold = True
        r.font.color.rgb = CACAO
        p = c.add_paragraph()
        p.paragraph_format.space_after = Pt(0)
        r = p.add_run(detalle)
        r.font.name = "Segoe UI"
        r.font.size = Pt(6.8)
        r.font.color.rgb = TEXTO
    _callout(
        doc,
        "CÓMO ABRIR",
        "Doble clic en DulcesitosCastillo.exe dentro de la carpeta completa. Si usas el código "
        "fuente, ejecuta ejecutar.bat. La primera vez se configura el acceso único del propietario; "
        "después, cada operador entra con el código que tú emitas.",
        fondo="FBF6F1",
        borde="C28A2C",
        color_titulo=CARAMELO,
        color_texto=TEXTO,
    )

    # Página 3 · administrador.
    _kicker(doc, "02 · MODO ADMINISTRADOR", nueva_pagina=True)
    _titulo(doc, "Una sola llave. Sin atajos.", tamano=25)
    _lede(
        doc,
        "El botón de configuración aparece una sola vez, en el primer arranque. No es un "
        "botón para crear administradores adicionales: es el alta del propietario. Después "
        "no existe ninguna opción para duplicar, ceder o cambiar el rol.",
    )
    _imagen(
        doc,
        CAPTURAS / "01_configuracion_inicial.png",
        17.2,
        "Configuración única del administrador en el primer arranque. No hay credenciales por defecto.",
        "Pantalla de configuración del acceso único del administrador.",
    )
    _callout(
        doc,
        "LO QUE NO EXISTE",
        "No hay botón para crear otro administrador, ni para asignar el rol, ni para cambiar "
        "de administrador. El propietario puede rotar su propia clave, pero el rol sigue siendo único.",
        fondo="FDF2F4",
        borde="E96A8D",
        color_titulo=ROSA_OSCURA,
        color_texto=RGBColor(0x6E, 0x2C, 0x3E),
    )
    _parrafo(doc, "CÓMO SE OPERA", tamano=7.4, color=ROSA_OSCURA, negrita=True, espacio_antes=1, espacio_despues=3)
    _pasos(
        doc,
        [
            "Configura nombre, cédula, correo y una clave de administración robusta.",
            "Cierra la sesión del operador y abre «Acceso administración» desde el ingreso.",
            "Genera el código del operador, define la vigencia y entrégalo en mano.",
            "Controla el catálogo: alta local, baja y reactivación sin tocar el maestro.",
            "Revisa historial, respaldos, lector y cierre de cada sesión.",
        ],
    )
    _callout(
        doc,
        "FRONTERA DE ROLES",
        "El operador nunca ve este panel. No puede crear códigos, cambiar productos ni configurar "
        "el lector. Su alcance termina en la estación y en el cierre autorizado.",
        fondo="FBF6F1",
        borde="C28A2C",
        color_titulo=CARAMELO,
        color_texto=TEXTO,
    )

    # Página 4 · accesos y catálogo.
    _kicker(doc, "03 · ACCESOS Y CATÁLOGO", nueva_pagina=True)
    _titulo(doc, "Permitir, vencer, retirar.", tamano=25)
    _lede(
        doc,
        "El operador solo entra con un código emitido por el administrador. La vigencia y "
        "la revocación son decisiones del administrador; el código completo se muestra una "
        "vez y después solo se conserva su hash.",
    )
    _imagen(
        doc,
        CAPTURAS / "05_admin_catalogo.png",
        17.1,
        "Catálogo efectivo: 24 activos, 1 alta local y 1 baja. El archivo maestro original no se modifica.",
        "Panel de catálogo con productos activos, altas locales y bajas.",
    )
    tabla_cred = _tabla_base(doc, 1, 2)
    _ancho_columna(tabla_cred, 0, 7.15)
    _ancho_columna(tabla_cred, 1, 10.15)
    c_img, c_txt = tabla_cred.cell(0, 0), tabla_cred.cell(0, 1)
    _margen_celda(c_img, 0.05, 0.05, 0.05, 0.15)
    _margen_celda(c_txt, 0.25, 0.2, 0.28, 0.25)
    _sombrear(c_txt, "1B100C")
    pimg = c_img.paragraphs[0]
    pimg.paragraph_format.space_after = Pt(0)
    pimg.add_run().add_picture(str(CAPTURAS / "08_codigo_generado.png"), width=Cm(6.8))
    p = c_txt.paragraphs[0]
    p.paragraph_format.space_after = Pt(2)
    r = p.add_run("CREDENCIAL DE OPERADOR")
    r.font.name = "Segoe UI Semibold"
    r.font.size = Pt(7)
    r.font.color.rgb = AMARILLO
    p = c_txt.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run("DLC-XXXX-XXXX-XXXX")
    r.font.name = "Segoe UI"
    r.font.size = Pt(12)
    r.font.bold = True
    r.font.color.rgb = CREMA
    for linea in [
        "Vigencia definida por el administrador (1 a 365 días).",
        "Revocación inmediata: el login y el cierre quedan bloqueados.",
        "La renovación invalida los códigos anteriores del operador.",
        "Sin recuperación del código: si se pierde, se emite otro.",
    ]:
        q = c_txt.add_paragraph()
        q.paragraph_format.space_after = Pt(2)
        q.paragraph_format.line_spacing = 1.02
        rr = q.add_run("·  " + linea)
        rr.font.name = "Segoe UI"
        rr.font.size = Pt(7.4)
        rr.font.color.rgb = RGBColor(0xEA, 0xDF, 0xD8)
    _parrafo(
        doc,
        "Las capturas de esta página provienen del entorno de demostración: el código mostrado "
        "no es válido en una instalación real.",
        tamano=7.1,
        color=MUTED,
        cursiva=True,
        espacio_antes=1,
        espacio_despues=5,
    )
    _callout(
        doc,
        "CATÁLOGO EFECTIVO",
        "Maestro + altas locales − bajas locales. El producto dado de baja no se puede escanear "
        "ni registrar manualmente; el historial anterior se conserva y la reactivación lo devuelve.",
        fondo="FBF6F1",
        borde="C28A2C",
        color_titulo=CARAMELO,
        color_texto=TEXTO,
    )
    _parrafo(doc, "QUÉ PASA CON EL CÓDIGO", tamano=7.4, color=ROSA_OSCURA, negrita=True, espacio_antes=2, espacio_despues=3)
    _tres_tarjetas(
        doc,
        [
            ("Vence", "BLOQUEO", "El login se rechaza y la sesión activa se bloquea en segundos."),
            ("Se revoca", "CONTROL", "El acceso se retira de inmediato; el cierre requiere autorización."),
            ("Se renueva", "REEMPLAZO", "Se emite un código nuevo y los anteriores quedan inválidos."),
        ],
        ["E96A8D", "C28A2C", "1D4ED8"],
    )

    # Página 5 · operador.
    _kicker(doc, "04 · MODO OPERADOR", nueva_pagina=True)
    _titulo(doc, "Entrar, calibrar, escanear.", tamano=25)
    _lede(
        doc,
        "La estación es deliberadamente simple: cédula, código, lector calibrado y un producto "
        "por lectura. El operador no administra el sistema; lo usa para validar la bodega.",
    )
    _imagen(
        doc,
        CAPTURAS / "03b_calibracion_ok.png",
        17.2,
        "Calibración exitosa: el lector y el archivo maestro quedan sincronizados.",
        "Estación de trabajo con la calibración superada y el aviso Prueba Match Sincronización OK.",
    )
    _callout(
        doc,
        "MENSAJE EXACTO DE CALIBRACIÓN",
        "«Prueba Match Sincronización OK». Solo con este aviso verde se habilita «Comenzar registro».",
        fondo="E8F8EF",
        borde="167A4A",
        color_titulo=VERDE,
        color_texto=RGBColor(0x18, 0x4A, 0x32),
    )
    _parrafo(doc, "TRES MOMENTOS", tamano=7.4, color=ROSA_OSCURA, negrita=True, espacio_antes=1, espacio_despues=3)
    tabla_momentos = _tabla_base(doc, 1, 3)
    for i, (n, titulo, texto) in enumerate(
        [
            ("01", "Ingreso", "Cédula + código vigente. Sin código, no hay estación."),
            ("02", "Calibración", "Producto real. El aviso verde confirma la sincronización."),
            ("03", "Registro", "Escanea, valida y ajusta. Cada lectura se guarda al instante."),
        ]
    ):
        c = tabla_momentos.cell(0, i)
        _ancho_columna(tabla_momentos, i, 5.65)
        _sombrear(c, "FBF6F1")
        _borde_celda(c, "top", 2.5, "C28A2C" if i == 1 else "E96A8D")
        _margen_celda(c, 0.2, 0.18, 0.25, 0.2)
        p = c.paragraphs[0]
        p.paragraph_format.space_after = Pt(1)
        r = p.add_run(n)
        r.font.name = "Segoe UI"
        r.font.size = Pt(15)
        r.font.bold = True
        r.font.color.rgb = ROSA_OSCURA
        p = c.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(titulo)
        r.font.name = "Segoe UI Semibold"
        r.font.size = Pt(8.2)
        r.font.color.rgb = CACAO
        p = c.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(texto)
        r.font.name = "Segoe UI"
        r.font.size = Pt(7.4)
        r.font.color.rgb = TEXTO
    _parrafo(doc, "ANTES DE ABRIR", tamano=7.4, color=ROSA_OSCURA, negrita=True, espacio_antes=6, espacio_despues=3)
    _checklist_compacta(
        doc,
        [
            "Archivo maestro en C:\\dulcesito_castillo.",
            "Lector USB conectado y calibrado.",
            "Código de acceso vigente entregado en mano.",
            "Estación con energía y equipo desbloqueado.",
        ],
    )
    _callout(
        doc,
        "REGLA DE ORO",
        "Si no aparece el aviso verde «Prueba Match Sincronización OK», no comiences el inventario. "
        "Revisa el producto, el cable y la calibración; si el lector no responde, usa el registro manual.",
        fondo="FFF6E8",
        borde="C28A2C",
        color_titulo=CARAMELO,
        color_texto=RGBColor(0x5B, 0x3D, 0x21),
    )
    _parrafo(
        doc,
        "El operador no puede crear administradores, modificar el maestro ni saltar la calibración.",
        tamano=7.6,
        color=MUTED,
        cursiva=True,
        espacio_antes=5,
        espacio_despues=1,
    )

    # Página 6 · registro y stock.
    _kicker(doc, "05 · REGISTRO Y STOCK", nueva_pagina=True)
    _titulo(doc, "Cada lectura deja huella.", tamano=25)
    _lede(
        doc,
        "El operador ve el producto, su stock de catálogo y el ajuste contado en el mismo "
        "panel. Si no ajusta, se conserva el valor del maestro; si ajusta, la salida lo "
        "reemplaza y agrega la diferencia auditada.",
    )
    _imagen(
        doc,
        CAPTURAS / "04_registro.png",
        17.2,
        "Registro en curso: producto validado, stock contado y botón de registro manual.",
        "Pantalla de registro con tabla de productos, ajuste de stock y registro manual.",
    )
    tabla_stock = _tabla_base(doc, 1, 2)
    _ancho_columna(tabla_stock, 0, 8.55)
    _ancho_columna(tabla_stock, 1, 8.55)
    for i, (titulo, texto) in enumerate(
        [
            ("AJUSTE DE STOCK", "Stock original, contado y diferencia. Se guarda con fecha, hora y operador; se puede retirar."),
            ("CONTROL DE LA SESIÓN", "Cobertura, duplicados, no encontrados y deshacer. El cierre se autoriza con clave."),
        ]
    ):
        c = tabla_stock.cell(0, i)
        _sombrear(c, "FBF6F1" if i == 0 else "1B100C")
        _borde_celda(c, "top", 3, "E96A8D" if i == 0 else "C28A2C")
        _margen_celda(c, 0.22, 0.2, 0.25, 0.22)
        p = c.paragraphs[0]
        p.paragraph_format.space_after = Pt(2)
        r = p.add_run(titulo)
        r.font.name = "Segoe UI Semibold"
        r.font.size = Pt(7)
        r.font.color.rgb = ROSA_OSCURA if i == 0 else AMARILLO
        p = c.add_paragraph()
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.line_spacing = 1.05
        r = p.add_run(texto)
        r.font.name = "Segoe UI"
        r.font.size = Pt(8.2)
        r.font.color.rgb = TEXTO if i == 0 else RGBColor(0xEA, 0xDF, 0xD8)
    _callout(
        doc,
        "EN LA SALIDA",
        "La hoja «Actualización» reemplaza el stock para los productos ajustados y agrega "
        "STOCK ORIGINAL, STOCK CONTADO y DIFERENCIA DE STOCK. El archivo maestro no se toca.",
        fondo="E8F1FD",
        borde="1D4ED8",
        color_titulo=AZUL,
        color_texto=RGBColor(0x1E, 0x3A, 0x6E),
    )
    _parrafo(doc, "QUÉ QUEDA REGISTRADO", tamano=7.4, color=ROSA_OSCURA, negrita=True, espacio_antes=2, espacio_despues=3)
    _tres_tarjetas(
        doc,
        [
            ("Producto", "IDENTIDAD", "Código, descripción y campos del catálogo, con la lectura validada."),
            ("Stock", "CANTIDAD", "Valor original, conteo físico y diferencia; se aplica al archivo de salida."),
            ("Sesión", "AUDITORÍA", "Operador, cédula, fecha y hora. El cierre se autoriza con clave."),
        ],
        ["E96A8D", "167A4A", "1D4ED8"],
    )
    _cita(
        doc,
        "Cada producto se puede explicar: quién lo contó, cuándo, con qué stock y en qué sesión.",
    )
    _callout(
        doc,
        "LECTURA DE LA DIFERENCIA",
        "Catálogo 180 · conteo 178 · diferencia −2. La salida escribe 178, conserva 180 como "
        "stock original y deja la diferencia visible. Un sobrante se muestra en positivo.",
        fondo="FBF6F1",
        borde="C28A2C",
        color_titulo=CARAMELO,
        color_texto=TEXTO,
    )

    # Página 7 · manual y cierre.
    _kicker(doc, "06 · NOVEDADES Y CIERRE", nueva_pagina=True)
    _titulo(doc, "Si el lector falla, la operación sigue.", tamano=24)
    _lede(
        doc,
        "El registro manual existe para el mundo real: etiquetas deterioradas, códigos "
        "ilegibles o productos que no están en el Excel. El lector se pausa, el operador "
        "escribe la novedad y el cierre sigue siendo trazable.",
    )
    tabla_imgs = _tabla_base(doc, 1, 2)
    _ancho_columna(tabla_imgs, 0, 7.4)
    _ancho_columna(tabla_imgs, 1, 9.5)
    for i, (ruta, ancho, cap) in enumerate(
        [
            (CAPTURAS / "06_registro_manual.png", 7.1, "Registro manual: código, descripción, novedad y stock opcional."),
            (CAPTURAS / "10_cierre.png", 9.2, "Cierre: reporte visual, Excel, TXT y autorización."),
        ]
    ):
        c = tabla_imgs.cell(0, i)
        c.vertical_alignment = WD_ALIGN_VERTICAL.TOP
        _margen_celda(c, 0.05, 0.05, 0.05, 0.1)
        p = c.paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        p.add_run().add_picture(str(ruta), width=Cm(ancho))
        cap_p = c.add_paragraph()
        cap_p.paragraph_format.space_before = Pt(2)
        cap_p.paragraph_format.space_after = Pt(0)
        rr = cap_p.add_run(cap)
        rr.font.name = "Segoe UI"
        rr.font.size = Pt(7)
        rr.font.color.rgb = MUTED
    _parrafo(doc, "REGISTRO MANUAL EN 4 PASOS", tamano=7.4, color=ROSA_OSCURA, negrita=True, espacio_antes=2, espacio_despues=3)
    _pasos(
        doc,
        [
            "Pulsa «Registro manual»: el lector queda en pausa.",
            "Escribe código y descripción; si el código existe, se usan los datos del catálogo.",
            "Escribe la novedad (obligatoria) y, si aplica, el stock contado.",
            "Registra y cierra. El producto manual aparece en Excel, TXT y PDF.",
        ],
    )
    _callout(
        doc,
        "SALIDAS DEL CIERRE",
        "Excel con Actualización, Registros de sesión y Resumen · TXT tabulado · PDF visual con "
        "firmas y sello de integridad. Todo queda en C:\\dulcesito_castillo\\salidas.",
        fondo="E8F8EF",
        borde="167A4A",
        color_titulo=VERDE,
        color_texto=RGBColor(0x18, 0x4A, 0x32),
    )
    _parrafo(doc, "TRES ARCHIVOS, UN MISMO HECHO", tamano=7.4, color=ROSA_OSCURA, negrita=True, espacio_antes=2, espacio_despues=3)
    _tres_tarjetas(
        doc,
        [
            ("Excel", "ACTUALIZACIÓN", "Catálogo completo, stock ajustado y auditoría por producto."),
            ("PDF", "REPORTE VISUAL", "Resumen, firmas y sello de integridad para imprimir o archivar."),
            ("TXT", "INTEGRACIÓN", "Texto tabulado con las columnas originales y los registros de la sesión."),
        ],
        ["167A4A", "E96A8D", "C28A2C"],
    )
    _parrafo(
        doc,
        "El administrador revisa y conserva los tres archivos; el operador no necesita abrir Excel.",
        tamano=7.6,
        color=MUTED,
        cursiva=True,
        espacio_antes=2,
        espacio_despues=4,
    )
    _callout(
        doc,
        "LA NOVEDAD NO SE ESCONDE",
        "Un registro manual no reemplaza un escaneo exitoso: lo documenta. Código, descripción, "
        "novedad, operador y hora quedan en la sesión y en los tres archivos de salida.",
        fondo="FDF2F4",
        borde="E96A8D",
        color_titulo=ROSA_OSCURA,
        color_texto=RGBColor(0x6E, 0x2C, 0x3E),
    )

    # Página 8 · problemas y conclusión.
    _kicker(doc, "07 · RESPUESTA OPERATIVA", nueva_pagina=True)
    _titulo(doc, "Cuando algo no sale.", tamano=25)
    _lede(
        doc,
        "La app está diseñada para no detener la bodega: avisa, conserva lo registrado y "
        "ofrece una salida controlada. Estas son las respuestas rápidas.",
    )
    _tabla_problemas(doc)
    _parrafo(doc, "CONCLUSIÓN", tamano=7.4, color=ROSA_OSCURA, negrita=True, espacio_antes=4, espacio_despues=3)
    tabla_concl = _tabla_base(doc, 1, 1)
    c = tabla_concl.cell(0, 0)
    _sombrear(c, "1B100C")
    _margen_celda(c, 0.3, 0.3, 0.35, 0.35)
    p = c.paragraphs[0]
    p.paragraph_format.space_after = Pt(3)
    r = p.add_run("Rápida para operar. Estricta para auditar.")
    r.font.name = "Segoe UI"
    r.font.size = Pt(14)
    r.font.bold = True
    r.font.color.rgb = CREMA
    p = c.add_paragraph()
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.05
    r = p.add_run(
        "Un solo administrador, operadores con acceso temporal, catálogo controlado y tres "
        "salidas auditables. La aplicación no reemplaza el criterio de la bodega: lo ordena "
        "y lo deja por escrito."
    )
    r.font.name = "Segoe UI"
    r.font.size = Pt(9.2)
    r.font.color.rgb = RGBColor(0xEA, 0xDF, 0xD8)
    _parrafo(doc, "CHECKLIST DE PUESTA EN MARCHA", tamano=7.4, color=ROSA_OSCURA, negrita=True, espacio_antes=5, espacio_despues=3)
    _checklist(doc)
    tabla_contacto = _tabla_base(doc, 1, 2)
    _ancho_columna(tabla_contacto, 0, 10.5)
    _ancho_columna(tabla_contacto, 1, 6.8)
    c0, c1 = tabla_contacto.cell(0, 0), tabla_contacto.cell(0, 1)
    for c in (c0, c1):
        _sombrear(c, "1B100C")
        _margen_celda(c, 0.25, 0.22, 0.3, 0.25)
    p = c0.paragraphs[0]
    p.paragraph_format.space_after = Pt(1)
    r = p.add_run("PROYECTO FORMATIVO · SENA")
    r.font.name = "Segoe UI Semibold"
    r.font.size = Pt(6.5)
    r.font.color.rgb = AMARILLO
    p = c0.add_paragraph()
    p.paragraph_format.space_after = Pt(1)
    r = p.add_run("Dulcesitos Castillo · Carlos Castillo")
    r.font.name = "Segoe UI"
    r.font.size = Pt(9.2)
    r.font.bold = True
    r.font.color.rgb = CREMA
    p = c1.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p.paragraph_format.space_after = Pt(1)
    r = p.add_run("CÓDIGO Y DOCUMENTACIÓN")
    r.font.name = "Segoe UI Semibold"
    r.font.size = Pt(6.2)
    r.font.color.rgb = AMARILLO
    p = c1.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    p.paragraph_format.space_after = Pt(0)
    r = p.add_run("github.com/MrCastilloF/Dulcesitos_Castillo")
    r.font.name = "Consolas"
    r.font.size = Pt(7.2)
    r.font.color.rgb = CREMA
    _parrafo(
        doc,
        "Documento de demostración · capturas tomadas del entorno DEMO · Versión 1.0.0 · Noviembre de 2026.",
        tamano=6.8,
        color=MUTED,
        cursiva=True,
        alineacion=WD_ALIGN_PARAGRAPH.CENTER,
        espacio_antes=3,
        espacio_despues=0,
    )

    doc.save(DESTINO)
    return DESTINO


if __name__ == "__main__":
    print(construir())
