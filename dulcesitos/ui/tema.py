"""Paleta, tipografía y estilos visuales de la aplicación.

La estética parte de un chocolate profundo con acentos de caramelo y rosa
candy. Los estados operativos usan siempre el mismo código de color:
verde = correcto, ámbar = atención, rojo = error y azul = información.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import font as tkfont
from tkinter import ttk

# ---------------------------------------------------------------------------
# Paleta
# ---------------------------------------------------------------------------
FONDO = "#100C0B"
FONDO_ELEVADO = "#160F0D"
SUPERFICIE = "#1D1512"
SUPERFICIE_2 = "#261B17"
SUPERFICIE_3 = "#31231E"
BORDE = "#3C2B24"
BORDE_SUAVE = "#2C1F1A"
TEXTO = "#FFF8F1"
TEXTO_SUAVE = "#D8C5B9"
MUTED = "#A18A7D"
ROSA = "#FB7185"
ROSA_CLARA = "#FDA4AF"
ROSA_OSCURA = "#9F1239"
ROSA_FONDO = "#3A1421"
CARAMELO = "#FBBF24"
CARAMELO_CLARO = "#FDE68A"
CARAMELO_OSCURO = "#92400E"
VERDE = "#34D399"
VERDE_CLARO = "#A7F3D0"
VERDE_OSCURO = "#065F46"
VERDE_FONDO = "#0C2E25"
ROJO = "#F87171"
ROJO_CLARO = "#FECACA"
ROJO_OSCURO = "#991B1B"
ROJO_FONDO = "#351416"
AMBAR = "#FBBF24"
AMBAR_CLARO = "#FDE68A"
AMBAR_FONDO = "#33250B"
AZUL = "#60A5FA"
AZUL_CLARO = "#BAE6FD"
AZUL_FONDO = "#0D2237"
BLANCO = "#FFFFFF"
CREMA = "#FFF7ED"
NEGRO = "#0A0706"
GRIS_CLARO = "#F5EFE8"

COLORES_ESTADO = {
    "ok": {
        "fg": VERDE,
        "bg": VERDE_FONDO,
        "borde": "#1F6650",
        "suave": VERDE_CLARO,
        "icono": "✓",
    },
    "info": {
        "fg": AZUL,
        "bg": AZUL_FONDO,
        "borde": "#1E4B77",
        "suave": AZUL_CLARO,
        "icono": "i",
    },
    "advertencia": {
        "fg": AMBAR,
        "bg": AMBAR_FONDO,
        "borde": "#6B4B0B",
        "suave": AMBAR_CLARO,
        "icono": "!",
    },
    "error": {
        "fg": ROJO,
        "bg": ROJO_FONDO,
        "borde": "#71212A",
        "suave": ROJO_CLARO,
        "icono": "×",
    },
    "neutro": {
        "fg": TEXTO_SUAVE,
        "bg": SUPERFICIE_2,
        "borde": BORDE,
        "suave": MUTED,
        "icono": "·",
    },
}

COLORES_LECTOR = {
    "activo": {"fg": VERDE, "bg": VERDE_FONDO, "borde": "#1F6650"},
    "conectado": {"fg": AZUL, "bg": AZUL_FONDO, "borde": "#1E4B77"},
    "pendiente": {"fg": AMBAR, "bg": AMBAR_FONDO, "borde": "#6B4B0B"},
    "desconectado": {"fg": ROJO, "bg": ROJO_FONDO, "borde": "#71212A"},
}


@dataclass(frozen=True)
class Fuentes:
    display: tkfont.Font
    titulo: tkfont.Font
    encabezado: tkfont.Font
    subtitulo: tkfont.Font
    cuerpo: tkfont.Font
    cuerpo_mediano: tkfont.Font
    cuerpo_fuerte: tkfont.Font
    pequena: tkfont.Font
    micro: tkfont.Font
    boton: tkfont.Font
    entrada: tkfont.Font
    escaneo: tkfont.Font
    numero: tkfont.Font
    mono: tkfont.Font
    firma: tkfont.Font


def _familia(disponibles: set[str], *candidatas: str) -> str:
    for familia in candidatas:
        if familia in disponibles:
            return familia
    return "Segoe UI"


def _fuente(
    root: tk.Misc,
    nombre: str,
    familia: str,
    tamano: int,
    peso: str = "normal",
) -> tkfont.Font:
    existente = tkfont.nametofont(nombre, root=root) if nombre in tkfont.names(root) else None
    if existente is not None:
        existente.configure(family=familia, size=tamano, weight=peso)
        return existente
    return tkfont.Font(
        root=root,
        name=nombre,
        family=familia,
        size=tamano,
        weight=peso,
    )


def crear_fuentes(root: tk.Misc) -> Fuentes:
    disponibles = {f.casefold(): f for f in tkfont.families(root)}
    nombres = set(disponibles.values())

    def elegir(*candidatas: str) -> str:
        for candidata in candidatas:
            if candidata in nombres:
                return candidata
            if candidata.casefold() in disponibles:
                return disponibles[candidata.casefold()]
        return "Segoe UI"

    display = elegir(
        "Segoe UI Variable Display",
        "Segoe UI Semibold",
        "Bahnschrift",
        "Segoe UI",
    )
    cuerpo = elegir("Segoe UI Variable Text", "Segoe UI", "Tahoma")
    mono = elegir("Cascadia Mono", "Cascadia Code", "Consolas", "Courier New")

    return Fuentes(
        display=_fuente(root, "AppDisplay", display, 30, "bold"),
        titulo=_fuente(root, "AppTitulo", display, 24, "bold"),
        encabezado=_fuente(root, "AppEncabezado", display, 18, "bold"),
        subtitulo=_fuente(root, "AppSubtitulo", display, 14, "bold"),
        cuerpo=_fuente(root, "AppCuerpo", cuerpo, 11),
        cuerpo_mediano=_fuente(root, "AppCuerpoMediano", cuerpo, 12),
        cuerpo_fuerte=_fuente(root, "AppCuerpoFuerte", cuerpo, 11, "bold"),
        pequena=_fuente(root, "AppPequena", cuerpo, 9),
        micro=_fuente(root, "AppMicro", cuerpo, 8),
        boton=_fuente(root, "AppBoton", cuerpo, 11, "bold"),
        entrada=_fuente(root, "AppEntrada", cuerpo, 12),
        escaneo=_fuente(root, "AppEscaneo", mono, 18, "bold"),
        numero=_fuente(root, "AppNumero", display, 26, "bold"),
        mono=_fuente(root, "AppMono", mono, 10),
        firma=_fuente(root, "AppFirma", cuerpo, 10),
    )


def preparar_entorno(root: tk.Tk) -> Fuentes:
    root.configure(bg=FONDO)
    try:
        root.option_add("*Font", "AppCuerpo")
        root.option_add("*tearOff", False)
        root.option_add("*selectBackground", ROSA_OSCURA)
        root.option_add("*selectForeground", CREMA)
    except tk.TclError:
        pass
    fuentes = crear_fuentes(root)
    estilo = ttk.Style(root)
    try:
        estilo.theme_use("clam")
    except tk.TclError:
        pass

    estilo.configure(
        "Treeview",
        background=SUPERFICIE,
        fieldbackground=SUPERFICIE,
        foreground=TEXTO,
        borderwidth=0,
        rowheight=38,
        font=fuentes.pequena,
    )
    estilo.configure(
        "Treeview.Heading",
        background=SUPERFICIE_3,
        foreground=TEXTO_SUAVE,
        borderwidth=0,
        relief="flat",
        font=fuentes.micro,
        padding=(8, 8),
    )
    estilo.map(
        "Treeview",
        background=[("selected", ROSA_OSCURA)],
        foreground=[("selected", CREMA)],
    )
    estilo.map(
        "Treeview.Heading",
        background=[("active", SUPERFICIE_3)],
        foreground=[("active", CARAMELO)],
    )
    estilo.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])

    estilo.configure(
        "Vertical.TScrollbar",
        background=SUPERFICIE_3,
        troughcolor=SUPERFICIE,
        bordercolor=SUPERFICIE,
        arrowcolor=MUTED,
        darkcolor=SUPERFICIE_3,
        lightcolor=SUPERFICIE_3,
        gripcount=0,
        width=10,
    )
    estilo.map(
        "Vertical.TScrollbar",
        background=[("active", BORDE)],
    )
    estilo.configure(
        "TCombobox",
        fieldbackground=SUPERFICIE_2,
        background=SUPERFICIE_2,
        foreground=TEXTO,
        arrowcolor=CARAMELO,
        bordercolor=BORDE,
        lightcolor=BORDE,
        darkcolor=BORDE,
        padding=8,
    )
    estilo.map(
        "TCombobox",
        fieldbackground=[("readonly", SUPERFICIE_2)],
        foreground=[("readonly", TEXTO)],
        selectbackground=[("readonly", SUPERFICIE_2)],
        selectforeground=[("readonly", TEXTO)],
    )
    estilo.configure(
        "TSpinbox",
        fieldbackground=SUPERFICIE_2,
        background=SUPERFICIE_2,
        foreground=TEXTO,
        arrowcolor=CARAMELO,
        bordercolor=BORDE,
        lightcolor=BORDE,
        darkcolor=BORDE,
        padding=6,
    )
    root.option_add("*TCombobox*Listbox.background", SUPERFICIE_2)
    root.option_add("*TCombobox*Listbox.foreground", TEXTO)
    root.option_add("*TCombobox*Listbox.selectBackground", ROSA_OSCURA)
    root.option_add("*TCombobox*Listbox.selectForeground", CREMA)
    root.option_add("*TCombobox*Listbox.font", "AppCuerpo")
    return fuentes


def color_estado(nombre: str) -> dict[str, str]:
    return COLORES_ESTADO.get(nombre, COLORES_ESTADO["neutro"])


def color_lector(nombre: str) -> dict[str, str]:
    return COLORES_LECTOR.get(nombre, COLORES_LECTOR["pendiente"])
