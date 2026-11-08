"""Pruebas de lectura de catálogos en Excel, CSV, TXT y PDF."""

from __future__ import annotations

import json

import pytest
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

from dulcesitos.archivo_maestro import (
    ArchivoMaestro,
    ErrorArchivoMaestro,
    cargar_instantanea,
    cargar_maestro,
    cargar_maestro_actual,
    descubrir_archivos,
    guardar_instantanea,
    normalizar_codigo_barras,
)


def test_normalizacion_conserva_ceros_y_acentos():
    assert normalizar_codigo_barras(" 001234 ") == "001234"
    assert normalizar_codigo_barras("Edición-Ñ") == "edición-ñ"


def test_carga_excel_de_ejemplo(rutas):
    maestro = cargar_maestro_actual(rutas.maestra)
    assert maestro.total == 24
    assert maestro.columna_codigo == "Código de barras"
    assert maestro.columna_descripcion == "Descripción"
    assert maestro.buscar("7702001001018").descripcion.startswith("Arepa")
    assert maestro.buscar("7702001001018") is maestro.buscar(" 7702001001018 ")
    assert maestro.indice is maestro.indice


def test_csv_con_preamble_y_punto_y_coma(tmp_path):
    ruta = tmp_path / "catalogo.csv"
    ruta.write_text(
        "CATÁLOGO DE BODEGA\n"
        "Generado por el sistema\n"
        "Código;Descripción;Categoría;Precio\n"
        "00123;Chocolatina;Dulces;2500\n"
        "00124;Galleta;Galletas;1800\n",
        encoding="utf-8",
    )
    maestro = cargar_maestro(ruta)
    assert maestro.total == 2
    assert maestro.buscar("00123").descripcion == "Chocolatina"
    assert maestro.buscar("123") is None
    assert any("Delimitador" in aviso for aviso in maestro.advertencias)


def test_txt_tabulado(tmp_path):
    ruta = tmp_path / "catalogo.txt"
    ruta.write_text(
        "barcode\tdescription\tstock\n"
        "A-01\tProducto A\t10\n"
        "A-02\tProducto B\t8\n",
        encoding="utf-8",
    )
    maestro = cargar_maestro(ruta)
    assert maestro.buscar("a-01").descripcion == "Producto A"
    assert maestro.columnas == ("barcode", "description", "stock")


def test_xlsx_con_columnas_alternativas(tmp_path):
    ruta = tmp_path / "alternativo.xlsx"
    libro = Workbook()
    hoja = libro.active
    hoja.append(["Nombre del producto", "SKU", "Bodega"])
    hoja.append(["Dulce de leche", "DLC-01", "Central"])
    libro.save(ruta)
    maestro = cargar_maestro(ruta)
    assert maestro.columna_codigo == "SKU"
    assert maestro.columna_descripcion == "Nombre del producto"
    assert maestro.buscar("dlc-01").campos["Bodega"] == "Central"


def test_archivo_sin_columnas_claras(tmp_path):
    ruta = tmp_path / "sin_columnas.xlsx"
    libro = Workbook()
    hoja = libro.active
    hoja.append(["Categoría", "Precio"])
    hoja.append(["Dulces", 1000])
    libro.save(ruta)
    with pytest.raises(ErrorArchivoMaestro):
        cargar_maestro(ruta)


def test_duplicados_se_informan(tmp_path):
    ruta = tmp_path / "duplicados.csv"
    ruta.write_text(
        "Código,Descripción\n001,Primero\n001,Segundo\n002,Tercero\n",
        encoding="utf-8",
    )
    maestro = cargar_maestro(ruta)
    assert maestro.total == 2
    assert maestro.buscar("001").descripcion == "Primero"
    assert any("duplicados" in aviso for aviso in maestro.advertencias)


def test_pdf_con_tabla(tmp_path):
    ruta = tmp_path / "catalogo.pdf"
    doc = SimpleDocTemplate(str(ruta), pagesize=A4)
    estilos = getSampleStyleSheet()
    datos = [
        ["Código de barras", "Descripción", "Categoría"],
        ["7700000000001", Paragraph("Bocadillo", estilos["BodyText"]), "Dulces"],
        ["7700000000002", Paragraph("Panelita", estilos["BodyText"]), "Dulces"],
    ]
    tabla = Table(datos)
    tabla.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ]
        )
    )
    doc.build([tabla])
    maestro = cargar_maestro(ruta)
    assert maestro.total == 2
    assert maestro.buscar("7700000000001").descripcion == "Bocadillo"
    assert maestro.formato.startswith("PDF")


def test_instantanea_roundtrip(rutas, tmp_path):
    maestro = cargar_maestro_actual(rutas.maestra)
    destino = tmp_path / "sesion.json"
    guardar_instantanea(maestro, destino)
    recuperado = cargar_instantanea(destino)
    assert isinstance(recuperado, ArchivoMaestro)
    assert recuperado.huella == maestro.huella
    assert recuperado.total == maestro.total
    assert recuperado.buscar("7702001001018").descripcion.startswith("Arepa")
    # El JSON no debe contener hashes de credenciales, solo datos del catálogo.
    assert "clave" not in json.loads(destino.read_text(encoding="utf-8"))


def test_descubrir_archivos_ignora_temporales(rutas):
    (rutas.maestra / "~$temporal.xlsx").write_text("x")
    (rutas.maestra / "notas.md").write_text("x")
    archivos = descubrir_archivos(rutas.maestra)
    assert any(ruta.name == "DEMO_maestro_dulcesitos.xlsx" for ruta in archivos)
    assert all(not ruta.name.startswith("~$") for ruta in archivos)
    assert all(ruta.suffix == ".xlsx" for ruta in archivos)
