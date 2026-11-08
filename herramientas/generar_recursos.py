"""Genera los recursos de demostración y el icono de la aplicación.

Se ejecuta solo durante el desarrollo. No es necesario para usar la aplicación.
"""

from __future__ import annotations

import csv
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from PIL import Image, ImageDraw

RAIZ = Path(__file__).resolve().parent.parent
ASSETS = RAIZ / "assets"
EJEMPLO = RAIZ / "datos_ejemplo"
ASSETS.mkdir(exist_ok=True)
EJEMPLO.mkdir(exist_ok=True)

PRODUCTOS = [
    ("7702001001018", "Arepa de chocolate Dulcesitos", "Arepas", "Paquete x 5", "8500", "74", "Planta principal"),
    ("7702001001025", "Bocadillo veleño artesanal", "Bocadillos", "Caja x 12", "12500", "52", "Proveedor Veleño"),
    ("7702001001032", "Chocolatina Castillo doble", "Chocolatinas", "Unidad 50 g", "2500", "180", "Planta principal"),
    ("7702001001049", "Galleta de caramelo", "Galletas", "Paquete x 6", "6700", "94", "Horno central"),
    ("7702001001056", "Dulce de leche tradicional", "Dulces", "Frasco 250 g", "9800", "33", "Lácteos del Norte"),
    ("7702001001063", "Panelita de leche", "Dulces", "Caja x 10", "7200", "61", "Proveedor Veleño"),
    ("7702001001070", "Mermelada de mora", "Conservas", "Frasco 300 g", "11300", "27", "Frutas de la región"),
    ("7702001001087", "Mermelada de guayaba", "Conservas", "Frasco 300 g", "10800", "41", "Frutas de la región"),
    ("7702001001094", "Arequipe campesino", "Lácteos", "Frasco 400 g", "13400", "22", "Lácteos del Norte"),
    ("7702001001100", "Turrón de maní", "Turrones", "Unidad 80 g", "3200", "105", "Proveedor Veleño"),
    ("7702001001117", "Cocada artesanal", "Cocadas", "Paquete x 4", "5600", "48", "Horno central"),
    ("7702001001124", "Alfajor de arequipe", "Galletas", "Paquete x 6", "8400", "72", "Horno central"),
    ("7702001001131", "Chocolate caliente en tableta", "Chocolates", "Caja x 8", "9600", "88", "Planta principal"),
    ("7702001001148", "Bolitas de chocolate", "Chocolatinas", "Bolsa 120 g", "4900", "130", "Planta principal"),
    ("7702001001155", "Obleas con arequipe", "Obleas", "Paquete x 10", "7800", "63", "Horno central"),
    ("7702001001162", "Dulce de tamarindo", "Dulces", "Bolsa 200 g", "4100", "39", "Frutas de la región"),
    ("7702001001179", "Jalea de naranja", "Conservas", "Frasco 250 g", "8900", "18", "Frutas de la región"),
    ("7702001001186", "Brownie de cacao", "Repostería", "Unidad 90 g", "5200", "44", "Horno central"),
    ("7702001001193", "Torta de zanahoria", "Repostería", "Porción 120 g", "6100", "16", "Horno central"),
    ("7702001001209", "Masmelos de fresa", "Dulces", "Bolsa 150 g", "3700", "115", "Distribuidora Dulce"),
    ("7702001001216", "Barquillo de vainilla", "Galletas", "Paquete x 8", "4600", "83", "Horno central"),
    ("7702001001223", "Dulce de coco", "Cocadas", "Unidad 70 g", "2900", "96", "Proveedor Veleño"),
    ("7702001001230", "Chocolate con almendras", "Chocolates", "Barra 100 g", "7900", "57", "Planta principal"),
    ("7702001001247", "Salsa de chocolate", "Conservas", "Frasco 220 g", "10200", "24", "Planta principal"),
]
ENCABEZADOS = [
    "Código de barras",
    "Descripción",
    "Categoría",
    "Presentación",
    "Precio",
    "Stock",
    "Proveedor",
]


def crear_maestro() -> None:
    libro = Workbook()
    hoja = libro.active
    hoja.title = "Catálogo"
    hoja.append(ENCABEZADOS)
    for producto in PRODUCTOS:
        hoja.append([producto[0], *producto[1:]])
    for columna in range(1, len(ENCABEZADOS) + 1):
        celda = hoja.cell(row=1, column=columna)
        celda.fill = PatternFill("solid", fgColor="241A17")
        celda.font = Font(bold=True, color="FFF8F0")
        celda.alignment = Alignment(horizontal="center")
    for fila in hoja.iter_rows(min_row=2, max_row=hoja.max_row, min_col=1, max_col=1):
        for celda in fila:
            celda.number_format = "@"
    anchos = [23, 38, 18, 18, 12, 10, 24]
    for i, ancho in enumerate(anchos, start=1):
        hoja.column_dimensions[get_column_letter(i)].width = ancho
    hoja.freeze_panes = "A2"
    hoja.auto_filter.ref = f"A1:G{hoja.max_row}"
    ruta = EJEMPLO / "DEMO_maestro_dulcesitos.xlsx"
    libro.save(ruta)
    print(f"Creado {ruta}")

    ruta_csv = EJEMPLO / "DEMO_maestro_dulcesitos.csv"
    with ruta_csv.open("w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(ENCABEZADOS)
        escritor.writerows(PRODUCTOS)
    print(f"Creado {ruta_csv}")


def crear_icono() -> None:
    tamano = 512
    imagen = Image.new("RGBA", (tamano, tamano), (0, 0, 0, 0))
    dibujo = ImageDraw.Draw(imagen)
    dibujo.rounded_rectangle((16, 16, 496, 496), radius=118, fill="#241A17")
    dibujo.rounded_rectangle((42, 42, 470, 470), radius=96, outline="#FBBF24", width=8)
    # Forma de caramelo envuelto.
    dibujo.ellipse((142, 142, 370, 370), fill="#FB7185")
    dibujo.polygon([(157, 194), (92, 150), (92, 362), (157, 318)], fill="#FB7185")
    dibujo.polygon([(355, 194), (420, 150), (420, 362), (355, 318)], fill="#FB7185")
    dibujo.ellipse((180, 180, 332, 332), outline="#FFF8F0", width=12)
    for angulo in range(0, 360, 45):
        import math

        x1 = 256 + 46 * math.cos(math.radians(angulo))
        y1 = 256 + 46 * math.sin(math.radians(angulo))
        x2 = 256 + 96 * math.cos(math.radians(angulo))
        y2 = 256 + 96 * math.sin(math.radians(angulo))
        dibujo.line((x1, y1, x2, y2), fill="#FFF8F0", width=9)
    dibujo.ellipse((222, 222, 290, 290), fill="#FBBF24")
    dibujo.ellipse((240, 240, 272, 272), fill="#FFF8F0")
    imagen.save(ASSETS / "logo.png")
    imagen.save(
        ASSETS / "icono.ico",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Creado {ASSETS / 'logo.png'}")
    print(f"Creado {ASSETS / 'icono.ico'}")


if __name__ == "__main__":
    crear_maestro()
    crear_icono()
