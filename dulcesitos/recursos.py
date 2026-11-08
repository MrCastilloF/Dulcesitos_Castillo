"""Localización de recursos compatible con el modo desarrollo y PyInstaller."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def raiz_recursos() -> Path:
    comprimido = getattr(sys, "_MEIPASS", None)
    if comprimido:
        return Path(comprimido)
    return Path(__file__).resolve().parent.parent


def ruta_recurso(*partes: str) -> Path:
    return raiz_recursos().joinpath(*partes)


def ruta_asset(nombre: str) -> Path:
    return ruta_recurso("assets", nombre)


def configurar_icono(ventana: object) -> None:
    """Asigna el icono .ico/.png sin impedir el arranque si falta el recurso."""

    try:
        ico = ruta_asset("icono.ico")
        if ico.exists() and os.name == "nt":
            ventana.iconbitmap(str(ico))  # type: ignore[attr-defined]
    except Exception:
        pass
    try:
        png = ruta_asset("logo.png")
        if png.exists():
            import tkinter as tk

            imagen = tk.PhotoImage(file=str(png))
            ventana.iconphoto(True, imagen)  # type: ignore[attr-defined]
            ventana._icono_referencia = imagen  # type: ignore[attr-defined]
    except Exception:
        pass
