"""Genera la portada y el flujo visual del resumen ejecutivo."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "docs" / "entrega" / "assets"
SALIDA.mkdir(parents=True, exist_ok=True)
CAPTURAS = RAIZ / "docs" / "capturas"

NEGRO = (11, 7, 6)
CACAO = (27, 16, 12)
CREMA = (250, 244, 239)
TEXTO = (246, 238, 233)
MUTED = (177, 155, 145)
ROSA = (240, 110, 142)
ROSA_CLARA = (255, 158, 180)
CARAMELO = (242, 184, 75)
VERDE = (74, 222, 128)
AZUL = (56, 189, 248)
BORDE = (66, 45, 38)


def _fuente(nombre: str, tamano: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(Path("C:/Windows/Fonts") / nombre), tamano)


def _texto(draw: ImageDraw.ImageDraw, xy, texto, fuente, color, **kwargs):
    draw.text(xy, texto, font=fuente, fill=color, **kwargs)


def _gradiente(ancho: int, alto: int) -> Image.Image:
    imagen = Image.new("RGB", (ancho, alto), NEGRO)
    pix = imagen.load()
    for y in range(alto):
        t = y / max(1, alto - 1)
        r = int(11 + 28 * t)
        g = int(7 + 8 * t)
        b = int(6 + 13 * t)
        for x in range(ancho):
            # Un halo cálido hacia la esquina inferior derecha.
            halo = max(0.0, 1.0 - ((x - ancho * 0.78) ** 2 + (y - alto * 0.78) ** 2) ** 0.5 / (ancho * 0.8))
            pix[x, y] = (
                min(255, r + int(24 * halo)),
                min(255, g + int(4 * halo)),
                min(255, b + int(11 * halo)),
            )
    return imagen


def _miniatura(ruta: Path, tamano: tuple[int, int], radio: int = 18) -> Image.Image:
    original = Image.open(ruta).convert("RGB")
    imagen = ImageOps.fit(original, tamano, method=Image.Resampling.LANCZOS)
    mascara = Image.new("L", tamano, 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, tamano[0] - 1, tamano[1] - 1), radio, fill=255)
    resultado = Image.new("RGBA", tamano, (0, 0, 0, 0))
    resultado.paste(imagen, (0, 0), mascara)
    borde = ImageDraw.Draw(resultado)
    borde.rounded_rectangle(
        (0, 0, tamano[0] - 1, tamano[1] - 1),
        radio,
        outline=(94, 61, 53, 255),
        width=2,
    )
    return resultado


def crear_portada() -> Path:
    ancho, alto = 1488, 2105
    imagen = _gradiente(ancho, alto).convert("RGBA")
    dibujo = ImageDraw.Draw(imagen)
    # Halos decorativos.
    capa = Image.new("RGBA", (ancho, alto), (0, 0, 0, 0))
    cd = ImageDraw.Draw(capa)
    cd.ellipse((940, -280, 1700, 480), fill=(240, 110, 142, 34))
    cd.ellipse((1080, 250, 1760, 930), fill=(242, 184, 75, 18))
    cd.ellipse((-260, 1210, 280, 1750), fill=(240, 110, 142, 18))
    capa = capa.filter(ImageFilter.GaussianBlur(65))
    imagen.alpha_composite(capa)
    dibujo = ImageDraw.Draw(imagen)

    logo = Image.open(RAIZ / "assets" / "logo.png").convert("RGBA")
    logo.thumbnail((150, 150), Image.Resampling.LANCZOS)
    imagen.alpha_composite(logo, (92, 88))

    f_marca = _fuente("seguisb.ttf", 35)
    f_micro = _fuente("seguisb.ttf", 18)
    f_titulo = _fuente("segoeuib.ttf", 96)
    f_sub = _fuente("segoeuisl.ttf", 28)
    f_chip = _fuente("seguisb.ttf", 18)
    f_pie = _fuente("segoeui.ttf", 18)
    f_etiqueta = _fuente("seguisb.ttf", 16)

    _texto(dibujo, (270, 104), "DULCESITOS CASTILLO", f_marca, CREMA)
    _texto(dibujo, (272, 151), "INVENTARIO DE BODEGA · SENA", f_micro, MUTED)
    _texto(dibujo, (1050, 111), "RESUMEN EJECUTIVO · 2026", f_micro, CARAMELO)

    dibujo.rounded_rectangle((92, 318, 178, 328), 5, fill=CARAMELO)
    _texto(dibujo, (92, 368), "Resumen ejecutivo", f_titulo, CREMA)
    _texto(dibujo, (92, 484), "de operación", f_titulo, ROSA_CLARA)
    _texto(dibujo, (96, 625), "Dulcesitos Castillo", _fuente("georgiai.ttf", 42), CARAMELO)

    _texto(
        dibujo,
        (92, 724),
        "Cómo se ejecuta, quién hace qué y cómo responde",
        f_sub,
        TEXTO,
    )
    _texto(
        dibujo,
        (92, 768),
        "la aplicación en la bodega, de principio a fin.",
        f_sub,
        TEXTO,
    )

    chips = [
        ("1 SOLO ADMINISTRADOR", ROSA),
        ("ACCESOS CON VENCIMIENTO", CARAMELO),
        ("REGISTRO MANUAL", AZUL),
    ]
    x = 92
    for texto, color in chips:
        bbox = dibujo.textbbox((0, 0), texto, font=f_chip)
        ancho_chip = bbox[2] - bbox[0] + 42
        dibujo.rounded_rectangle((x, 874, x + ancho_chip, 920), 23, fill=(*color, 255))
        _texto(dibujo, (x + 21, 887), texto, f_chip, NEGRO)
        x += ancho_chip + 14

    # Collage de pantallas exitosas.
    _texto(dibujo, (92, 1002), "LA OPERACIÓN, EN PANTALLA", f_etiqueta, MUTED)
    imagenes = [
        ("REGISTRO Y STOCK", CAPTURAS / "04_registro.png"),
        ("ADMINISTRACIÓN", CAPTURAS / "05_admin_catalogo.png"),
        ("MODO MANUAL", CAPTURAS / "06_registro_manual.png"),
    ]
    tam = (408, 258)
    x = 92
    for etiqueta, ruta in imagenes:
        miniatura = _miniatura(ruta, tam)
        sombra = Image.new("RGBA", (tam[0] + 16, tam[1] + 16), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sombra)
        sd.rounded_rectangle((8, 8, tam[0] + 8, tam[1] + 8), 20, fill=(0, 0, 0, 100))
        sombra = sombra.filter(ImageFilter.GaussianBlur(10))
        imagen.alpha_composite(sombra, (x - 4, 1040))
        imagen.alpha_composite(miniatura, (x, 1038))
        _texto(dibujo, (x, 1312), etiqueta, f_etiqueta, CARAMELO)
        x += tam[0] + 25

    _texto(dibujo, (92, 1445), "DEL ESCANEO AL ARCHIVO, SIN PERDER TRAZABILIDAD", f_etiqueta, MUTED)
    metricas = [
        ("01", "administrador único", "sin roles duplicados"),
        ("0", "claves en texto plano", "hash + sal aleatoria"),
        ("03", "salidas auditables", "Excel · PDF · TXT"),
    ]
    ancho_metrica = 408
    x = 92
    for valor, titulo, detalle in metricas:
        dibujo.rounded_rectangle(
            (x, 1490, x + ancho_metrica, 1715),
            18,
            fill=(28, 15, 13),
            outline=(66, 45, 38),
            width=1,
        )
        _texto(dibujo, (x + 24, 1515), valor, _fuente("segoeuib.ttf", 64), CARAMELO)
        _texto(dibujo, (x + 24, 1605), titulo, _fuente("seguisb.ttf", 22), CREMA)
        _texto(dibujo, (x + 24, 1645), detalle, _fuente("segoeui.ttf", 17), MUTED)
        x += ancho_metrica + 27

    dibujo.line((92, 1960, 1396, 1960), fill=BORDE, width=1)
    _texto(dibujo, (92, 1990), "Noviembre de 2026 · Versión 1.0.0", f_pie, MUTED)
    _texto(
        dibujo,
        (1010, 1990),
        "Documento de demostración · capturas con datos DEMO",
        f_pie,
        MUTED,
    )
    ruta = SALIDA / "portada.png"
    imagen.convert("RGB").save(ruta, quality=95)
    return ruta


def crear_flujo() -> Path:
    ancho, alto = 2300, 310
    imagen = Image.new("RGB", (ancho, alto), (251, 246, 242))
    dibujo = ImageDraw.Draw(imagen)
    dibujo.rounded_rectangle((1, 1, ancho - 2, alto - 2), 28, outline=(232, 217, 207), width=2)
    pasos = [
        ("01", "Configura", "acceso único", ROSA),
        ("02", "Emite", "código y vigencia", CARAMELO),
        ("03", "Calibra", "Prueba Match OK", VERDE),
        ("04", "Escanea", "valida y ajusta", AZUL),
        ("05", "Manual", "si el lector falla", ROSA),
        ("06", "Cierra", "Excel · PDF · TXT", VERDE),
    ]
    margen = 72
    paso = (ancho - margen * 2) / len(pasos)
    line_y = 100
    dibujo.line((margen + paso / 2, line_y, ancho - margen - paso / 2, line_y), fill=(218, 199, 189), width=3)
    f_num = _fuente("segoeuib.ttf", 25)
    f_titulo = _fuente("seguisb.ttf", 27)
    f_sub = _fuente("segoeui.ttf", 19)
    for i, (numero, titulo, subtitulo, color) in enumerate(pasos):
        cx = margen + paso * i + paso / 2
        dibujo.ellipse((cx - 31, line_y - 31, cx + 31, line_y + 31), fill=(15, 10, 8), outline=color, width=3)
        bbox = dibujo.textbbox((0, 0), numero, font=f_num)
        _texto(dibujo, (cx - (bbox[2] - bbox[0]) / 2, line_y - 15), numero, f_num, color)
        bbox = dibujo.textbbox((0, 0), titulo, font=f_titulo)
        _texto(dibujo, (cx - (bbox[2] - bbox[0]) / 2, 158), titulo, f_titulo, (27, 16, 12))
        bbox = dibujo.textbbox((0, 0), subtitulo, font=f_sub)
        _texto(dibujo, (cx - (bbox[2] - bbox[0]) / 2, 200), subtitulo, f_sub, (118, 95, 85))
        if i < len(pasos) - 1:
            _texto(dibujo, (cx + paso / 2 - 14, 78), "›", _fuente("segoeuib.ttf", 40), (180, 154, 142))
    ruta = SALIDA / "flujo_operativo.png"
    imagen.save(ruta, quality=95)
    return ruta


if __name__ == "__main__":
    print(crear_portada())
    print(crear_flujo())
