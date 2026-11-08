"""Componentes visuales reutilizables, dibujados sobre Tkinter puro."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable, Sequence
from tkinter import ttk
from typing import Any

from . import tema


# ---------------------------------------------------------------------------
# Utilidades de dibujo
# ---------------------------------------------------------------------------
def rect_redondeado(
    canvas: tk.Canvas,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    radio: float,
    *,
    fill: str,
    outline: str = "",
    width: int = 1,
    tags: str | tuple[str, ...] = "",
) -> int:
    radio = max(0, min(radio, (x2 - x1) / 2, (y2 - y1) / 2))
    puntos = [
        x1 + radio,
        y1,
        x2 - radio,
        y1,
        x2,
        y1,
        x2,
        y1 + radio,
        x2,
        y2 - radio,
        x2,
        y2,
        x2 - radio,
        y2,
        x1 + radio,
        y2,
        x1,
        y2,
        x1,
        y2 - radio,
        x1,
        y1 + radio,
        x1,
        y1,
    ]
    return canvas.create_polygon(
        puntos,
        smooth=True,
        splinesteps=24,
        fill=fill,
        outline=outline,
        width=width,
        tags=tags,
    )


def etiqueta(
    master: tk.Misc,
    texto: str = "",
    *,
    fuente: tk.font.Font | None = None,
    color: str = tema.TEXTO,
    fondo: str = tema.FONDO,
    wraplength: int = 0,
    justify: str = "left",
    anchor: str = "w",
    cursor: str = "",
    padx: int = 0,
    pady: int = 0,
) -> tk.Label:
    return tk.Label(
        master,
        text=texto,
        font=fuente,
        fg=color,
        bg=fondo,
        wraplength=wraplength,
        justify=justify,
        anchor=anchor,
        cursor=cursor or "",
        padx=padx,
        pady=pady,
        bd=0,
        highlightthickness=0,
    )


def separador(master: tk.Misc, color: str = tema.BORDE_SUAVE, alto: int = 1) -> tk.Frame:
    return tk.Frame(master, bg=color, height=alto, bd=0, highlightthickness=0)


def _fuente_widget(widget: tk.Misc) -> tk.font.Font | None:
    return None


# ---------------------------------------------------------------------------
# Botón dibujado (esquinas redondeadas, foco y estados)
# ---------------------------------------------------------------------------
class Boton(tk.Canvas):
    VARIANTES: dict[str, dict[str, str]] = {
        "primario": {
            "fill": tema.ROSA,
            "hover": tema.ROSA_CLARA,
            "press": "#F43F5E",
            "fg": tema.NEGRO,
            "borde": "",
        },
        "exito": {
            "fill": tema.VERDE,
            "hover": "#6EE7B7",
            "press": "#10B981",
            "fg": tema.NEGRO,
            "borde": "",
        },
        "caramelo": {
            "fill": tema.CARAMELO,
            "hover": "#FCD34D",
            "press": "#F59E0B",
            "fg": tema.NEGRO,
            "borde": "",
        },
        "secundario": {
            "fill": tema.SUPERFICIE_2,
            "hover": tema.SUPERFICIE_3,
            "press": tema.BORDE,
            "fg": tema.TEXTO,
            "borde": tema.BORDE,
        },
        "fantasma": {
            "fill": "",
            "hover": tema.SUPERFICIE_2,
            "press": tema.SUPERFICIE_3,
            "fg": tema.TEXTO_SUAVE,
            "borde": "",
        },
        "peligro": {
            "fill": "#7F1D1D",
            "hover": "#991B1B",
            "press": "#6B1414",
            "fg": "#FFE4E6",
            "borde": "#B91C1C",
        },
        "oscuro": {
            "fill": tema.CACAO if hasattr(tema, "CACAO") else tema.SUPERFICIE_3,
            "hover": tema.SUPERFICIE_2,
            "press": tema.NEGRO,
            "fg": tema.CARAMELO,
            "borde": tema.BORDE,
        },
        "claro": {
            "fill": tema.CREMA,
            "hover": tema.BLANCO,
            "press": tema.CARAMELO_CLARO,
            "fg": tema.NEGRO,
            "borde": "",
        },
        "admin": {
            "fill": tema.CARAMELO,
            "hover": "#FCD34D",
            "press": "#F59E0B",
            "fg": tema.NEGRO,
            "borde": "",
        },
    }

    def __init__(
        self,
        master: tk.Misc,
        texto: str,
        comando: Callable[[], None] | None = None,
        *,
        variante: str = "primario",
        icono: str = "",
        ancho: int | None = None,
        alto: int = 46,
        radio: int = 13,
        fuente: tk.font.Font | None = None,
        fondo: str | None = None,
        tooltip: str = "",
        takefocus: bool = True,
    ):
        self._fondo = fondo or _color_fondo(master)
        super().__init__(
            master,
            width=ancho or 160,
            height=alto,
            bg=self._fondo,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
            takefocus=takefocus,
        )
        self.texto = texto
        self.comando = comando
        self.variante = variante
        self.icono = icono
        self.ancho_solicitado = ancho
        self.alto = alto
        self.radio = radio
        self.fuente = fuente or _fuente_boton(master)
        self._estado = "normal"
        self._hover = False
        self._presionado = False
        self._con_foco = False
        self._texto_render = ""
        self._ancho_calculado = ancho or self._medir_ancho()
        self.configure(width=self._ancho_calculado)
        self.bind("<Configure>", lambda _e: self._dibujar())
        self.bind("<Enter>", self._entrar)
        self.bind("<Leave>", self._salir)
        self.bind("<ButtonPress-1>", self._presionar)
        self.bind("<ButtonRelease-1>", self._soltar)
        self.bind("<FocusIn>", self._ganar_foco)
        self.bind("<FocusOut>", self._perder_foco)
        self.bind("<Return>", self._teclado)
        self.bind("<space>", self._teclado)
        if tooltip:
            self._tooltip = tooltip
            self.bind("<Enter>", lambda e: self._mostrar_tooltip(e), add="+")
            self.bind("<Leave>", lambda e: self._ocultar_tooltip(e), add="+")
        else:
            self._tooltip = ""
            self._tooltip_ventana: tk.Toplevel | None = None
        self.after(20, self._dibujar)

    def _medir_ancho(self) -> int:
        try:
            ancho_texto = self.fuente.measure(self.texto)
        except tk.TclError:
            ancho_texto = len(self.texto) * 8
        extra = (self.fuente.measure("  " + self.icono) if self.icono else 0) + 42
        return max(112, ancho_texto + extra)

    def _colores(self) -> dict[str, str]:
        if self._estado == "deshabilitado":
            return {
                "fill": tema.SUPERFICIE_2,
                "hover": tema.SUPERFICIE_2,
                "press": tema.SUPERFICIE_2,
                "fg": tema.MUTED,
                "borde": tema.BORDE_SUAVE,
            }
        base = dict(self.VARIANTES.get(self.variante, self.VARIANTES["primario"]))
        if self._presionado:
            base["fill"] = base["press"]
        elif self._hover:
            base["fill"] = base["hover"]
        if not base.get("fill"):
            base["fill"] = self._fondo
        return base

    def _dibujar(self) -> None:
        try:
            self.delete("all")
            ancho = max(2, self.winfo_width() or self._ancho_calculado)
            alto = max(2, self.winfo_height() or self.alto)
        except tk.TclError:
            return
        colores = self._colores()
        rect_redondeado(
            self,
            1,
            1,
            ancho - 1,
            alto - 1,
            self.radio,
            fill=colores["fill"],
            outline=colores.get("borde") or "",
            width=1,
        )
        if self._con_foco and self._estado != "deshabilitado":
            rect_redondeado(
                self,
                3,
                3,
                ancho - 3,
                alto - 3,
                max(2, self.radio - 2),
                fill="",
                outline=tema.CARAMELO,
                width=2,
            )
        color_texto = colores["fg"]
        if self.variante == "fantasma" and self._hover:
            color_texto = tema.TEXTO
        texto = self.texto
        if self.icono:
            icono = self.icono
            ancho_icono = self.fuente.measure(icono)
            ancho_texto = self.fuente.measure(texto)
            espacio = 8
            total = ancho_icono + espacio + ancho_texto
            x = (ancho - total) / 2
            self.create_text(
                x + ancho_icono / 2,
                alto / 2 + 1,
                text=icono,
                fill=color_texto,
                font=self.fuente,
            )
            self.create_text(
                x + ancho_icono + espacio + ancho_texto / 2,
                alto / 2 + 1,
                text=texto,
                fill=color_texto,
                font=self.fuente,
            )
        else:
            self.create_text(
                ancho / 2,
                alto / 2 + 1,
                text=texto,
                fill=color_texto,
                font=self.fuente,
            )

    def _entrar(self, _evento: tk.Event) -> None:
        if self._estado == "deshabilitado":
            return
        self._hover = True
        self.configure(cursor="hand2")
        self._dibujar()

    def _salir(self, _evento: tk.Event) -> None:
        self._hover = False
        self._presionado = False
        self._dibujar()

    def _presionar(self, _evento: tk.Event) -> None:
        if self._estado == "deshabilitado":
            return
        self._presionado = True
        self._dibujar()

    def _soltar(self, evento: tk.Event) -> None:
        if self._estado == "deshabilitado":
            return
        estaba = self._presionado
        self._presionado = False
        self._dibujar()
        dentro = 0 <= evento.x <= self.winfo_width() and 0 <= evento.y <= self.winfo_height()
        if estaba and dentro and self.comando:
            self.comando()

    def _teclado(self, _evento: tk.Event) -> str:
        if self._estado != "deshabilitado" and self.comando:
            self.comando()
        return "break"

    def _ganar_foco(self, _evento: tk.Event) -> None:
        self._con_foco = True
        self._dibujar()

    def _perder_foco(self, _evento: tk.Event) -> None:
        self._con_foco = False
        self._dibujar()

    def configurar_estado(self, estado: str) -> None:
        self._estado = "deshabilitado" if estado in {"deshabilitado", "disabled"} else "normal"
        self._hover = False
        self._presionado = False
        self.configure(cursor="arrow" if self._estado == "deshabilitado" else "hand2")
        self._dibujar()

    def configurar_texto(self, texto: str, icono: str | None = None) -> None:
        self.texto = texto
        if icono is not None:
            self.icono = icono
        if self.ancho_solicitado is None:
            self._ancho_calculado = self._medir_ancho()
            self.configure(width=self._ancho_calculado)
        self._dibujar()

    def configurar_variante(self, variante: str) -> None:
        self.variante = variante
        self._dibujar()

    # Tooltip sencillo -----------------------------------------------------
    def _mostrar_tooltip(self, evento: tk.Event) -> None:
        if not self._tooltip or self._tooltip_ventana is not None:
            return
        x = self.winfo_rootx() + 12
        y = self.winfo_rooty() + self.winfo_height() + 6
        ventana = tk.Toplevel(self)
        ventana.wm_overrideredirect(True)
        ventana.configure(bg=tema.BORDE)
        marco = tk.Frame(ventana, bg=tema.SUPERFICIE_3, padx=8, pady=5)
        marco.pack(padx=1, pady=1)
        tk.Label(
            marco,
            text=self._tooltip,
            bg=tema.SUPERFICIE_3,
            fg=tema.TEXTO_SUAVE,
            font=_fuente_pequena(self),
            justify="left",
            wraplength=280,
        ).pack()
        ventana.wm_geometry(f"+{x}+{y}")
        self._tooltip_ventana = ventana

    def _ocultar_tooltip(self, _evento: tk.Event) -> None:
        if getattr(self, "_tooltip_ventana", None):
            try:
                self._tooltip_ventana.destroy()
            except tk.TclError:
                pass
            self._tooltip_ventana = None


def _color_fondo(widget: tk.Misc) -> str:
    try:
        return str(widget.cget("bg"))
    except (tk.TclError, AttributeError):
        return tema.FONDO


def _fuente_boton(widget: tk.Misc) -> tk.font.Font:
    app = getattr(widget.winfo_toplevel(), "_fuentes_app", None)
    if app is not None:
        return app.boton
    return tk.font.nametofont("TkDefaultFont")


def _fuente_pequena(widget: tk.Misc) -> tk.font.Font:
    app = getattr(widget.winfo_toplevel(), "_fuentes_app", None)
    if app is not None:
        return app.pequena
    return tk.font.nametofont("TkDefaultFont")


def _fuente_cuerpo(widget: tk.Misc) -> tk.font.Font:
    app = getattr(widget.winfo_toplevel(), "_fuentes_app", None)
    if app is not None:
        return app.cuerpo
    return tk.font.nametofont("TkDefaultFont")


def _fuente_micro(widget: tk.Misc) -> tk.font.Font:
    app = getattr(widget.winfo_toplevel(), "_fuentes_app", None)
    if app is not None:
        return app.micro
    return tk.font.nametofont("TkDefaultFont")


# ---------------------------------------------------------------------------
# Marca
# ---------------------------------------------------------------------------
class MarcaCandy(tk.Canvas):
    def __init__(self, master: tk.Misc, tamano: int = 44, fondo: str | None = None):
        self._fondo = fondo or _color_fondo(master)
        super().__init__(
            master,
            width=tamano,
            height=tamano,
            bg=self._fondo,
            highlightthickness=0,
            bd=0,
        )
        self._tamano = tamano
        self._dibujar()

    def _dibujar(self) -> None:
        s = self._tamano
        self.delete("all")
        rect_redondeado(
            self, 0, 0, s, s, s * 0.27, fill=tema.SUPERFICIE_3, outline=tema.BORDE, width=1
        )
        cx, cy = s * 0.52, s * 0.5
        r = s * 0.23
        # Envolturas laterales.
        self.create_polygon(
            s * 0.25,
            cy - r * 0.7,
            s * 0.12,
            cy - r * 1.4,
            s * 0.12,
            cy + r * 1.4,
            s * 0.25,
            cy + r * 0.7,
            fill=tema.CARAMELO,
            outline="",
        )
        self.create_polygon(
            s * 0.79,
            cy - r * 0.7,
            s * 0.92,
            cy - r * 1.4,
            s * 0.92,
            cy + r * 1.4,
            s * 0.79,
            cy + r * 0.7,
            fill=tema.CARAMELO,
            outline="",
        )
        self.create_oval(
            cx - r,
            cy - r,
            cx + r,
            cy + r,
            fill=tema.ROSA,
            outline=tema.CREMA,
            width=max(1, int(s * 0.035)),
        )
        self.create_oval(
            cx - r * 0.46,
            cy - r * 0.46,
            cx + r * 0.46,
            cy + r * 0.46,
            fill=tema.CARAMELO,
            outline="",
        )
        self.create_oval(
            cx - r * 0.16,
            cy - r * 0.16,
            cx + r * 0.16,
            cy + r * 0.16,
            fill=tema.CREMA,
            outline="",
        )


class Avatar(tk.Canvas):
    def __init__(
        self,
        master: tk.Misc,
        iniciales: str,
        tamano: int = 38,
        fondo: str | None = None,
    ):
        self._fondo = fondo or _color_fondo(master)
        super().__init__(
            master,
            width=tamano,
            height=tamano,
            bg=self._fondo,
            highlightthickness=0,
            bd=0,
        )
        self._tamano = tamano
        self._iniciales = iniciales or "??"
        self._dibujar()

    def _dibujar(self) -> None:
        s = self._tamano
        self.delete("all")
        self.create_oval(1, 1, s - 1, s - 1, fill=tema.ROSA_FONDO, outline=tema.ROSA_OSCURA)
        fuente = _fuente_cuerpo(self)
        self.create_text(
            s / 2,
            s / 2 + 1,
            text=self._iniciales[:2],
            fill=tema.CARAMELO_CLARO,
            font=(fuente.actual("family"), max(8, int(fuente.actual("size")) - 1), "bold"),
        )


# ---------------------------------------------------------------------------
# Píldoras e indicadores
# ---------------------------------------------------------------------------
class Pildora(tk.Canvas):
    def __init__(
        self,
        master: tk.Misc,
        texto: str,
        estado: str = "neutro",
        *,
        ancho: int | None = None,
        alto: int = 27,
        fondo: str | None = None,
        con_punto: bool = True,
    ):
        self._fondo = fondo or _color_fondo(master)
        self._texto = texto
        self._estado = estado
        self._ancho = ancho or 140
        self._alto = alto
        self._con_punto = con_punto
        super().__init__(
            master,
            width=self._ancho,
            height=alto,
            bg=self._fondo,
            highlightthickness=0,
            bd=0,
        )
        if ancho is None:
            self._ancho = self._calcular_ancho()
            self.configure(width=self._ancho)
        self._dibujar()

    def _calcular_ancho(self) -> int:
        fuente = _fuente_micro(self)
        return max(88, fuente.measure(self._texto) + (44 if self._con_punto else 28))

    def _dibujar(self) -> None:
        colores = tema.color_estado(self._estado)
        self.delete("all")
        rect_redondeado(
            self,
            1,
            1,
            self._ancho - 1,
            self._alto - 1,
            (self._alto - 2) / 2,
            fill=colores["bg"],
            outline=colores["borde"],
            width=1,
        )
        x = 13
        if self._con_punto:
            self.create_oval(
                x - 3,
                self._alto / 2 - 3,
                x + 3,
                self._alto / 2 + 3,
                fill=colores["fg"],
                outline="",
            )
            x += 12
        self.create_text(
            x,
            self._alto / 2 + 1,
            text=self._texto,
            anchor="w",
            fill=colores["fg"],
            font=_fuente_micro(self),
        )

    def actualizar(self, texto: str, estado: str) -> None:
        self._texto = texto
        self._estado = estado
        self._ancho = self._calcular_ancho()
        self.configure(width=self._ancho)
        self._dibujar()


class IndicadorLector(tk.Canvas):
    """Indicador compacto siempre visible en la barra superior."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        fondo: str = tema.FONDO,
        comando: Callable[[], None] | None = None,
        ancho: int = 200,
        alto: int = 34,
    ):
        super().__init__(
            master,
            width=ancho,
            height=alto,
            bg=fondo,
            highlightthickness=0,
            bd=0,
            cursor="hand2" if comando else "",
        )
        self._fondo = fondo
        self._ancho = ancho
        self._alto = alto
        self._estado = "pendiente"
        self._detalle = "Lector: iniciando"
        self.comando = comando
        self._pulso = False
        if comando:
            self.bind("<Button-1>", lambda _e: self.comando())
        self._dibujar()
        self.after(900, self._latir)

    def actualizar(self, estado: Any) -> None:
        self._estado = getattr(estado, "estado", "pendiente")
        etiqueta = getattr(estado, "etiqueta", "HID EN ESPERA")
        self._detalle = f"LECTOR · {etiqueta}"
        self._dibujar()

    def _latir(self) -> None:
        try:
            if not self.winfo_exists():
                return
        except tk.TclError:
            return
        self._pulso = not self._pulso
        if self._estado in {"activo", "conectado"}:
            self._dibujar()
        try:
            self.after(900, self._latir)
        except tk.TclError:
            pass

    def _dibujar(self) -> None:
        colores = tema.color_lector(self._estado)
        self.delete("all")
        rect_redondeado(
            self,
            1,
            2,
            self._ancho - 1,
            self._alto - 2,
            (self._alto - 4) / 2,
            fill=colores["bg"],
            outline=colores["borde"],
            width=1,
        )
        radio = 5 if not self._pulso else 4
        cx = 16
        cy = self._alto / 2
        self.create_oval(
            cx - radio - 2,
            cy - radio - 2,
            cx + radio + 2,
            cy + radio + 2,
            outline=colores["borde"],
            width=1,
        )
        self.create_oval(
            cx - radio,
            cy - radio,
            cx + radio,
            cy + radio,
            fill=colores["fg"],
            outline="",
        )
        self.create_text(
            cx + 16,
            cy + 1,
            text=self._detalle.upper(),
            anchor="w",
            fill=colores["fg"],
            font=_fuente_micro(self),
        )


# ---------------------------------------------------------------------------
# Selector segmentado
# ---------------------------------------------------------------------------
class SelectorSegmentado(tk.Canvas):
    def __init__(
        self,
        master: tk.Misc,
        opciones: Sequence[tuple[str, str]],
        comando: Callable[[str], None],
        *,
        ancho: int = 420,
        alto: int = 44,
        fondo: str = tema.SUPERFICIE,
        seleccionado: str | None = None,
    ):
        super().__init__(
            master,
            width=ancho,
            height=alto,
            bg=fondo,
            highlightthickness=0,
            bd=0,
            cursor="hand2",
            takefocus=True,
        )
        self._opciones = list(opciones)
        self.comando = comando
        self._seleccionado = seleccionado or self._opciones[0][0]
        self._ancho = ancho
        self._alto = alto
        self._fondo = fondo
        self.bind("<Button-1>", self._clic)
        self.bind("<Configure>", lambda _e: self._dibujar())
        self.bind("<Left>", lambda _e: self._mover(-1))
        self.bind("<Right>", lambda _e: self._mover(1))
        self.bind("<Return>", lambda _e: self.comando(self._seleccionado))
        self.bind("<space>", lambda _e: self.comando(self._seleccionado))
        self._dibujar()

    @property
    def seleccion(self) -> str:
        return self._seleccionado

    def _indice_actual(self) -> int:
        for i, (clave, _) in enumerate(self._opciones):
            if clave == self._seleccionado:
                return i
        return 0

    def _mover(self, delta: int) -> str:
        indice = max(0, min(len(self._opciones) - 1, self._indice_actual() + delta))
        self._seleccionado = self._opciones[indice][0]
        self._dibujar()
        self.comando(self._seleccionado)
        return "break"

    def _clic(self, evento: tk.Event) -> None:
        ancho = max(1, self.winfo_width())
        indice = min(len(self._opciones) - 1, int(evento.x / (ancho / len(self._opciones))))
        self._seleccionado = self._opciones[indice][0]
        self._dibujar()
        self.comando(self._seleccionado)

    def seleccionar(self, clave: str) -> None:
        if any(k == clave for k, _ in self._opciones):
            self._seleccionado = clave
            self._dibujar()

    def _dibujar(self) -> None:
        self.delete("all")
        ancho = max(2, self.winfo_width() or self._ancho)
        alto = max(2, self.winfo_height() or self._alto)
        rect_redondeado(
            self,
            0,
            0,
            ancho,
            alto,
            alto / 2,
            fill=tema.SUPERFICIE_2,
            outline=tema.BORDE,
            width=1,
        )
        cantidad = max(1, len(self._opciones))
        ancho_item = ancho / cantidad
        indice = self._indice_actual()
        for i, (_clave, texto) in enumerate(self._opciones):
            activo = i == indice
            if activo:
                rect_redondeado(
                    self,
                    i * ancho_item + 4,
                    4,
                    (i + 1) * ancho_item - 4,
                    alto - 4,
                    (alto - 8) / 2,
                    fill=tema.ROSA_OSCURA,
                    outline=tema.ROSA,
                    width=1,
                )
            self.create_text(
                i * ancho_item + ancho_item / 2,
                alto / 2 + 1,
                text=texto,
                fill=tema.CREMA if activo else tema.MUTED,
                font=(
                    _fuente_boton(self).actual("family"),
                    max(9, int(_fuente_boton(self).actual("size")) - 1),
                    "bold" if activo else "normal",
                ),
            )


# ---------------------------------------------------------------------------
# Campo de formulario
# ---------------------------------------------------------------------------
class Campo(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        etiqueta_texto: str,
        *,
        secreto: bool = False,
        ayuda: str = "",
        texto_inicial: str = "",
        transformacion: Callable[[str], str] | None = None,
        on_enter: Callable[[], None] | None = None,
        fondo: str = tema.SUPERFICIE,
        fuente: tk.font.Font | None = None,
        mostrar_boton_clave: bool = True,
        ancho_ayuda: int = 360,
    ):
        super().__init__(master, bg=fondo, bd=0, highlightthickness=0)
        self._fondo = fondo
        self._secreto = secreto
        self._mostrar = False
        self._transformacion = transformacion
        self._on_enter = on_enter
        self._ayuda_original = ayuda
        self._ancho_ayuda = ancho_ayuda
        self.variable = tk.StringVar(value=texto_inicial)

        self.titulo = etiqueta(
            self,
            etiqueta_texto.upper(),
            fuente=_fuente_micro(self),
            color=tema.MUTED,
            fondo=fondo,
        )
        self.titulo.pack(fill="x", pady=(0, 6))

        self.caja = tk.Frame(
            self,
            bg=tema.SUPERFICIE_2,
            highlightbackground=tema.BORDE,
            highlightcolor=tema.CARAMELO,
            highlightthickness=1,
            bd=0,
        )
        self.caja.pack(fill="x")
        self.entrada = tk.Entry(
            self.caja,
            textvariable=self.variable,
            bg=tema.SUPERFICIE_2,
            fg=tema.TEXTO,
            insertbackground=tema.CARAMELO,
            disabledbackground=tema.SUPERFICIE_2,
            disabledforeground=tema.MUTED,
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=fuente or _fuente_cuerpo(self),
        )
        self._sufijo: tk.Label | None = None
        if secreto:
            self.entrada.configure(show="•")
            if mostrar_boton_clave:
                self._sufijo = etiqueta(
                    self.caja,
                    "MOSTRAR",
                    fuente=_fuente_micro(self),
                    color=tema.CARAMELO,
                    fondo=tema.SUPERFICIE_2,
                    cursor="hand2",
                )
                # El sufijo debe reservar su espacio ANTES de que la entrada
                # expansible consuma todo el ancho disponible.
                self._sufijo.pack(side="right", padx=(0, 12))
                self._sufijo.bind("<Button-1>", lambda _e: self._alternar_visible())
        self.entrada.pack(side="left", fill="both", expand=True, padx=12, pady=10)

        self.mensaje = etiqueta(
            self,
            ayuda,
            fuente=_fuente_micro(self),
            color=tema.MUTED,
            fondo=fondo,
            wraplength=ancho_ayuda,
            justify="left",
        )
        self.mensaje.pack(fill="x", pady=(5, 0))
        self.mensaje.configure(text=ayuda or " ")

        self.entrada.bind("<FocusIn>", self._foco_entra)
        self.entrada.bind("<FocusOut>", self._foco_sale)
        if on_enter:
            self.entrada.bind("<Return>", lambda _e: on_enter())
            self.entrada.bind("<KP_Enter>", lambda _e: on_enter())
        if transformacion:
            self.variable.trace_add("write", self._aplicar_transformacion)

    def _aplicar_transformacion(self, *_args: object) -> None:
        if not self._transformacion:
            return
        valor = self.variable.get()
        nuevo = self._transformacion(valor)
        if nuevo != valor:
            self.variable.set(nuevo)
            try:
                self.entrada.icursor("end")
            except tk.TclError:
                pass

    def _foco_entra(self, _evento: tk.Event) -> None:
        self.caja.configure(highlightbackground=tema.CARAMELO, highlightcolor=tema.CARAMELO)

    def _foco_sale(self, _evento: tk.Event) -> None:
        self.caja.configure(highlightbackground=tema.BORDE, highlightcolor=tema.CARAMELO)

    def _alternar_visible(self) -> None:
        self._mostrar = not self._mostrar
        self.entrada.configure(show="" if self._mostrar else "•")
        if self._sufijo:
            self._sufijo.configure(text="OCULTAR" if self._mostrar else "MOSTRAR")

    def get(self) -> str:
        return self.variable.get()

    def set(self, valor: str) -> None:
        self.variable.set(valor)
        self.establecer_error(None)

    def limpiar(self) -> None:
        self.variable.set("")
        self.establecer_error(None)

    def enfocar(self) -> None:
        try:
            if self.entrada.winfo_exists():
                self.entrada.focus_set()
                self.entrada.selection_range(0, "end")
        except tk.TclError:
            pass

    def establecer_error(self, mensaje: str | None) -> None:
        if mensaje:
            self.caja.configure(highlightbackground=tema.ROJO, highlightcolor=tema.ROJO)
            self.mensaje.configure(text=mensaje, fg=tema.ROJO)
        else:
            self.caja.configure(highlightbackground=tema.BORDE, highlightcolor=tema.CARAMELO)
            self.mensaje.configure(
                text=self._ayuda_original or " ", fg=tema.MUTED
            )

    def habilitar(self, habilitado: bool) -> None:
        estado = "normal" if habilitado else "disabled"
        self.entrada.configure(state=estado, cursor="xterm" if habilitado else "arrow")
        if self._sufijo:
            self._sufijo.configure(fg=tema.CARAMELO if habilitado else tema.MUTED)


# ---------------------------------------------------------------------------
# Tarjeta y encabezados
# ---------------------------------------------------------------------------
class Tarjeta(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        *,
        fondo: str = tema.SUPERFICIE,
        borde: str = tema.BORDE,
        padding: int = 20,
        acento: str = "",
        radio: int = 0,
    ):
        super().__init__(
            master,
            bg=fondo,
            highlightbackground=borde,
            highlightcolor=borde,
            highlightthickness=1,
            bd=0,
        )
        self._fondo = fondo
        self._borde_original = borde
        self.contenido = tk.Frame(self, bg=fondo, bd=0, highlightthickness=0)
        if acento:
            tk.Frame(self, bg=acento, height=3, bd=0, highlightthickness=0).pack(
                fill="x", side="top"
            )
        self.contenido.pack(fill="both", expand=True, padx=padding, pady=padding)

    def resaltar(self, color: str) -> None:
        self.configure(highlightbackground=color, highlightcolor=color)

    def restaurar_borde(self) -> None:
        self.configure(
            highlightbackground=self._borde_original,
            highlightcolor=self._borde_original,
        )


def encabezado_tarjeta(
    master: tk.Misc,
    titulo: str,
    subtitulo: str = "",
    *,
    fondo: str = tema.SUPERFICIE,
    color_titulo: str = tema.TEXTO,
    color_subtitulo: str = tema.MUTED,
    derecha_texto: str = "",
    derecha_estado: str = "neutro",
) -> tk.Frame:
    """Encabezado con una píldora opcional correctamente empaquetada a la derecha.

    La píldora se crea como hija del propio encabezado. Después de llamar a esta
    función se puede acceder a ella en ``encabezado.pildora_derecha``.
    """

    fila = tk.Frame(master, bg=fondo)
    fila.pildora_derecha = None  # type: ignore[attr-defined]
    if derecha_texto:
        pildora = Pildora(fila, derecha_texto, derecha_estado, fondo=fondo)
        pildora.pack(side="right", anchor="n", padx=(10, 0))
        fila.pildora_derecha = pildora  # type: ignore[attr-defined]
    izquierda = tk.Frame(fila, bg=fondo)
    izquierda.pack(side="left", fill="x", expand=True)
    etiqueta(
        izquierda,
        titulo,
        fuente=_fuente_encabezado(master),
        color=color_titulo,
        fondo=fondo,
    ).pack(anchor="w")
    if subtitulo:
        etiqueta(
            izquierda,
            subtitulo,
            fuente=_fuente_pequena(master),
            color=color_subtitulo,
            fondo=fondo,
            wraplength=490,
            justify="left",
        ).pack(anchor="w", pady=(3, 0))
    return fila


def _fuente_encabezado(widget: tk.Misc) -> tk.font.Font:
    app = getattr(widget.winfo_toplevel(), "_fuentes_app", None)
    if app is not None:
        return app.encabezado
    return _fuente_cuerpo(widget)


# ---------------------------------------------------------------------------
# Banner de estado
# ---------------------------------------------------------------------------
class BannerEstado(tk.Frame):
    def __init__(self, master: tk.Misc, *, fondo: str = tema.SUPERFICIE):
        super().__init__(
            master,
            bg=tema.SUPERFICIE_2,
            highlightbackground=tema.BORDE,
            highlightthickness=1,
            bd=0,
        )
        self._fondo_padre = fondo
        self._icono_canvas = tk.Canvas(
            self,
            width=44,
            height=44,
            bg=tema.SUPERFICIE_2,
            highlightthickness=0,
            bd=0,
        )
        self._icono_canvas.pack(side="left", padx=(16, 12), pady=16)
        contenido = tk.Frame(self, bg=tema.SUPERFICIE_2)
        contenido.pack(side="left", fill="both", expand=True, pady=(13, 13), padx=(0, 16))
        self.titulo = tk.Label(
            contenido,
            text="",
            bg=tema.SUPERFICIE_2,
            fg=tema.TEXTO,
            font=_fuente_boton(self),
            anchor="w",
            justify="left",
        )
        self.titulo.pack(fill="x", anchor="w")
        self.mensaje = tk.Label(
            contenido,
            text="",
            bg=tema.SUPERFICIE_2,
            fg=tema.TEXTO_SUAVE,
            font=_fuente_pequena(self),
            anchor="w",
            justify="left",
            wraplength=620,
        )
        self.mensaje.pack(fill="x", anchor="w", pady=(2, 0))
        self.bind("<Configure>", self._ajustar_wrap)
        self.mostrar(
            "Estación en preparación",
            "Carga el catálogo y calibra el lector para comenzar.",
            "neutro",
        )

    def _ajustar_wrap(self, evento: tk.Event) -> None:
        ancho = max(240, evento.width - 120)
        self.mensaje.configure(wraplength=ancho)

    def mostrar(self, titulo: str, mensaje: str, estado: str = "neutro") -> None:
        colores = tema.color_estado(estado)
        self.configure(
            bg=colores["bg"],
            highlightbackground=colores["borde"],
        )
        self._icono_canvas.configure(bg=colores["bg"])
        for hijo in self.winfo_children():
            if isinstance(hijo, tk.Frame):
                hijo.configure(bg=colores["bg"])
        self.titulo.configure(text=titulo, bg=colores["bg"], fg=colores["fg"])
        self.mensaje.configure(text=mensaje, bg=colores["bg"], fg=colores["suave"])
        self._dibujar_icono(colores)
        self._estado = estado

    def _dibujar_icono(self, colores: dict[str, str]) -> None:
        c = self._icono_canvas
        c.delete("all")
        c.create_oval(2, 2, 42, 42, fill=colores["borde"], outline="")
        c.create_text(
            22,
            23,
            text=colores["icono"],
            fill=tema.CREMA,
            font=(
                "Segoe UI",
                16,
                "bold",
            ),
        )


# ---------------------------------------------------------------------------
# Pasos y estadísticas
# ---------------------------------------------------------------------------
class Stepper(tk.Canvas):
    def __init__(self, master: tk.Misc, pasos: Sequence[str], *, fondo: str = tema.FONDO):
        super().__init__(
            master,
            height=58,
            bg=fondo,
            highlightthickness=0,
            bd=0,
            takefocus=False,
        )
        self._pasos = list(pasos)
        self._estados = ["pendiente"] * len(self._pasos)
        self._fondo = fondo
        self._activo = 0
        self.bind("<Configure>", lambda _e: self._dibujar())

    def actualizar(self, estados: Sequence[str], activo: int | None = None) -> None:
        self._estados = list(estados)
        if activo is not None:
            self._activo = activo
        self._dibujar()

    def _dibujar(self) -> None:
        self.delete("all")
        ancho = max(300, self.winfo_width() or 600)
        n = max(1, len(self._pasos))
        tramo = ancho / n
        centros = [tramo * i + tramo / 2 for i in range(n)]
        cy = 17
        for i in range(n - 1):
            x1 = centros[i] + 20
            x2 = centros[i + 1] - 20
            color = tema.VERDE if self._estados[i] == "completado" else tema.BORDE
            self.create_line(x1, cy, x2, cy, fill=color, width=2, dash=(3, 4))
        for i, paso in enumerate(self._pasos):
            estado = self._estados[i] if i < len(self._estados) else "pendiente"
            if estado == "completado":
                fill, borde, texto = tema.VERDE, tema.VERDE, tema.NEGRO
                numero = "✓"
                color_texto = tema.VERDE_CLARO
            elif estado == "activo" or i == self._activo:
                fill, borde, texto = tema.CARAMELO, tema.CARAMELO, tema.NEGRO
                numero = str(i + 1).zfill(2)
                color_texto = tema.CARAMELO_CLARO
            else:
                fill, borde, texto = tema.SUPERFICIE_2, tema.BORDE, tema.MUTED
                numero = str(i + 1).zfill(2)
                color_texto = tema.MUTED
            cx = centros[i]
            self.create_oval(
                cx - 15, cy - 15, cx + 15, cy + 15, fill=fill, outline=borde, width=1
            )
            self.create_text(
                cx,
                cy + 1,
                text=numero,
                fill=texto,
                font=_fuente_micro(self),
            )
            self.create_text(
                cx,
                cy + 29,
                text=paso,
                anchor="center",
                fill=color_texto,
                font=(
                    _fuente_pequena(self).actual("family"),
                    int(_fuente_pequena(self).actual("size")),
                    "bold" if estado != "pendiente" else "normal",
                ),
            )


class TarjetaMetrica(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        titulo: str,
        valor: str | int = "0",
        *,
        color: str = tema.CARAMELO,
        fondo: str = tema.SUPERFICIE,
        borde: str = tema.BORDE,
        compacta: bool = False,
    ):
        super().__init__(
            master,
            bg=fondo,
            highlightbackground=borde,
            highlightthickness=1,
            bd=0,
        )
        self._fondo = fondo
        self._color = color
        self._barra = tk.Frame(self, bg=color, width=4)
        self._barra.pack(side="left", fill="y")
        interior = tk.Frame(self, bg=fondo)
        interior.pack(fill="both", expand=True, padx=14, pady=8 if compacta else 12)
        self.titulo = etiqueta(
            interior,
            titulo.upper(),
            fuente=_fuente_micro(self),
            color=tema.MUTED,
            fondo=fondo,
        )
        self.titulo.pack(anchor="w")
        self.valor = etiqueta(
            interior,
            str(valor),
            fuente=_fuente_numero(self) if not compacta else _fuente_subtitulo(self),
            color=color,
            fondo=fondo,
        )
        self.valor.pack(anchor="w", pady=(0, 1))

    def actualizar(self, valor: str | int, color: str | None = None) -> None:
        self.valor.configure(text=str(valor))
        if color:
            self._color = color
            self._barra.configure(bg=color)
            self.valor.configure(fg=color)


def _fuente_numero(widget: tk.Misc) -> tk.font.Font:
    app = getattr(widget.winfo_toplevel(), "_fuentes_app", None)
    if app is not None:
        return app.numero
    return _fuente_cuerpo(widget)


def _fuente_subtitulo(widget: tk.Misc) -> tk.font.Font:
    app = getattr(widget.winfo_toplevel(), "_fuentes_app", None)
    if app is not None:
        return app.subtitulo
    return _fuente_cuerpo(widget)


# ---------------------------------------------------------------------------
# Entrada de escaneo
# ---------------------------------------------------------------------------
class EntradaEscaneo(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        al_escanear: Callable[[str], None],
        *,
        fondo: str = tema.SUPERFICIE,
        borde: str = tema.ROSA,
        placeholder: str = "Escanea el código de barras…",
        texto_deshabilitado: str = "Calibra y verifica el lector para continuar",
        habilitado: bool = True,
    ):
        super().__init__(
            master,
            bg=tema.SUPERFICIE_2,
            highlightbackground=borde,
            highlightcolor=borde,
            highlightthickness=2,
            bd=0,
        )
        self.al_escanear = al_escanear
        self._habilitado = habilitado
        self._placeholder_texto = placeholder
        self._texto_deshabilitado = texto_deshabilitado
        self._fondo = tema.SUPERFICIE_2
        self._borde = borde
        self._ocupado = False
        self._after_estado: str | None = None

        self._icono = tk.Canvas(
            self,
            width=52,
            height=54,
            bg=tema.SUPERFICIE_2,
            highlightthickness=0,
            bd=0,
        )
        self._icono.pack(side="left", padx=(12, 0))
        self._dibujar_icono(tema.ROSA)
        self._icono.bind("<Button-1>", lambda _e: self.enfocar())

        contenedor = tk.Frame(self, bg=tema.SUPERFICIE_2)
        contenedor.pack(side="left", fill="both", expand=True, padx=(10, 12), pady=8)
        self.variable = tk.StringVar()
        self.entrada = tk.Entry(
            contenedor,
            textvariable=self.variable,
            bg=tema.SUPERFICIE_2,
            fg=tema.CREMA,
            insertbackground=tema.CARAMELO,
            disabledbackground=tema.SUPERFICIE_2,
            disabledforeground=tema.MUTED,
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=_fuente_escaneo(self),
        )
        self.entrada.pack(fill="x", pady=(0, 0))
        self._placeholder = tk.Label(
            contenedor,
            text=placeholder,
            bg=tema.SUPERFICIE_2,
            fg=tema.MUTED,
            font=_fuente_escanear_placeholder(self),
            cursor="xterm",
        )
        self._placeholder.place(x=2, rely=0.5, anchor="w")
        self._placeholder.bind("<Button-1>", lambda _e: self.enfocar())
        self._pista = etiqueta(
            contenedor,
            "ENTER PARA CONFIRMAR",
            fuente=_fuente_micro(self),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE_2,
        )
        self._pista.pack(anchor="w", pady=(3, 0))

        self._tecla = tk.Label(
            self,
            text="↵",
            bg=tema.SUPERFICIE_3,
            fg=tema.TEXTO_SUAVE,
            font=("Segoe UI", 17, "bold"),
            padx=12,
            pady=5,
            bd=0,
        )
        self._tecla.pack(side="right", padx=12)

        self.entrada.bind("<Return>", self._al_presionar)
        self.entrada.bind("<KP_Enter>", self._al_presionar)
        self.entrada.bind("<FocusIn>", self._foco_entra)
        self.entrada.bind("<FocusOut>", self._foco_sale)
        self.variable.trace_add("write", self._al_escribir)
        for widget in (self, contenedor):
            widget.bind("<Button-1>", lambda _e: self.enfocar())
        self.habilitar(habilitado)

    def _dibujar_icono(self, color: str) -> None:
        c = self._icono
        c.delete("all")
        c.create_rectangle(5, 12, 8, 42, fill=color, outline="")
        c.create_rectangle(11, 9, 13, 45, fill=color, outline="")
        c.create_rectangle(17, 12, 20, 42, fill=color, outline="")
        c.create_rectangle(24, 9, 26, 45, fill=color, outline="")
        c.create_rectangle(30, 12, 33, 42, fill=color, outline="")
        c.create_rectangle(38, 9, 41, 45, fill=color, outline="")
        c.create_rectangle(45, 12, 47, 42, fill=color, outline="")

    def _al_escribir(self, *_args: object) -> None:
        hay_texto = bool(self.variable.get())
        if hay_texto:
            self._placeholder.place_forget()
        elif self._habilitado:
            self._placeholder.configure(text=self._placeholder_texto)
            self._placeholder.place(x=2, rely=0.5, anchor="w")

    def _foco_entra(self, _evento: tk.Event) -> None:
        if not self.variable.get() and self._habilitado:
            self._placeholder.configure(text=self._placeholder_texto)
            self._placeholder.place(x=2, rely=0.5, anchor="w")
        self.configure(highlightbackground=self._borde, highlightcolor=self._borde)
        self._dibujar_icono(tema.CARAMELO)

    def _foco_sale(self, _evento: tk.Event) -> None:
        if not self.variable.get() and self._habilitado:
            self._placeholder.configure(text=self._placeholder_texto)
            self._placeholder.place(x=2, rely=0.5, anchor="w")
        self._dibujar_icono(tema.ROSA if self._habilitado else tema.MUTED)

    def _al_presionar(self, _evento: tk.Event) -> str:
        if not self._habilitado or self._ocupado:
            return "break"
        codigo = self.variable.get().strip()
        if not codigo:
            return "break"
        self._ocupado = True
        self.variable.set("")
        self._ocupado = False
        try:
            self.al_escanear(codigo)
        finally:
            self.after(30, self.enfocar)
        return "break"

    def enfocar(self) -> None:
        if not self._habilitado:
            return
        try:
            if self.winfo_exists() and self.entrada.winfo_exists():
                self.entrada.focus_set()
        except tk.TclError:
            pass

    def configurar_texto_deshabilitado(self, texto: str) -> None:
        self._texto_deshabilitado = texto or "Escaneo deshabilitado"
        if not self._habilitado:
            self._placeholder.configure(text=self._texto_deshabilitado)
            self._placeholder.place(x=2, rely=0.5, anchor="w")

    def habilitar(self, habilitado: bool) -> None:
        self._habilitado = habilitado
        self.entrada.configure(
            state="normal" if habilitado else "disabled",
            cursor="xterm" if habilitado else "arrow",
        )
        self.configure(cursor="xterm" if habilitado else "arrow")
        if habilitado:
            self._dibujar_icono(tema.ROSA)
            if not self.variable.get():
                self._placeholder.configure(text=self._placeholder_texto)
                self._placeholder.place(x=2, rely=0.5, anchor="w")
            self.after(80, self.enfocar)
        else:
            self._placeholder.configure(text=self._texto_deshabilitado)
            self._placeholder.place(x=2, rely=0.5, anchor="w")
            self._dibujar_icono(tema.MUTED)

    def marcar_estado(self, estado: str) -> None:
        colores = tema.color_estado(estado)
        self.configure(
            highlightbackground=colores["fg"],
            highlightcolor=colores["fg"],
        )
        self._dibujar_icono(colores["fg"])
        if self._after_estado:
            try:
                self.after_cancel(self._after_estado)
            except tk.TclError:
                pass
        self._after_estado = self.after(
            900,
            lambda: self.configure(
                highlightbackground=self._borde,
                highlightcolor=self._borde,
            ),
        )


def _fuente_escaneo(widget: tk.Misc) -> tk.font.Font:
    app = getattr(widget.winfo_toplevel(), "_fuentes_app", None)
    if app is not None:
        return app.escaneo
    return _fuente_cuerpo(widget)


def _fuente_escanear_placeholder(widget: tk.Misc) -> tk.font.Font:
    app = getattr(widget.winfo_toplevel(), "_fuentes_app", None)
    if app is not None:
        return app.entrada
    return _fuente_cuerpo(widget)


class BarraProgreso(tk.Canvas):
    def __init__(
        self,
        master: tk.Misc,
        *,
        fondo: str = tema.SUPERFICIE_2,
        color: str = tema.VERDE,
        alto: int = 8,
    ):
        super().__init__(
            master,
            height=alto,
            bg=fondo,
            highlightthickness=0,
            bd=0,
        )
        self._fondo = fondo
        self._color = color
        self._proporcion = 0.0
        self.bind("<Configure>", lambda _e: self._dibujar())

    def actualizar(self, proporcion: float) -> None:
        self._proporcion = max(0.0, min(1.0, float(proporcion)))
        self._dibujar()

    def _dibujar(self) -> None:
        self.delete("all")
        ancho = max(2, self.winfo_width() or 100)
        alto = max(2, self.winfo_height() or 8)
        rect_redondeado(
            self, 0, 0, ancho, alto, alto / 2, fill=self._fondo, outline=""
        )
        relleno = max(alto, ancho * self._proporcion)
        if self._proporcion > 0:
            rect_redondeado(
                self,
                0,
                0,
                relleno,
                alto,
                alto / 2,
                fill=self._color,
                outline="",
            )


class MarcoDesplazable(tk.Frame):
    """Área vertical con barra de desplazamiento que aparece solo si hace falta."""

    def __init__(
        self,
        master: tk.Misc,
        *,
        fondo: str = tema.FONDO,
        expandir_alto: bool = False,
    ):
        super().__init__(master, bg=fondo, bd=0, highlightthickness=0)
        self._fondo = fondo
        self._expandir_alto = expandir_alto
        self.canvas = tk.Canvas(
            self,
            bg=fondo,
            highlightthickness=0,
            bd=0,
            yscrollincrement=24,
        )
        self.canvas.pack(side="left", fill="both", expand=True)
        self.barra = ttk.Scrollbar(
            self,
            orient="vertical",
            command=self.canvas.yview,
            style="Vertical.TScrollbar",
        )
        self.interior = tk.Frame(self.canvas, bg=fondo)
        self._ventana = self.canvas.create_window(
            (0, 0), window=self.interior, anchor="nw"
        )
        self._barra_visible = False
        self.canvas.configure(yscrollcommand=self._al_desplazar)
        self.interior.bind("<Configure>", self._contenido_cambio)
        self.canvas.bind("<Configure>", self._canvas_cambio)
        self._toplevel = self.winfo_toplevel()
        self._bind_id = self._toplevel.bind(
            "<MouseWheel>", self._rueda_raton, add="+"
        )
        self.bind("<Destroy>", self._al_destruir, add="+")

    def _contenido_cambio(self, _evento: tk.Event | None = None) -> None:
        try:
            self._ajustar_ventana()
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except tk.TclError:
            return
        self._revisar_barra()

    def _canvas_cambio(self, evento: tk.Event) -> None:
        self.canvas.itemconfigure(self._ventana, width=evento.width)
        self._ajustar_ventana()
        self._revisar_barra()

    def _ajustar_ventana(self) -> None:
        if not self._expandir_alto:
            return
        alto_visible = self.canvas.winfo_height()
        solicitado = self.interior.winfo_reqheight()
        if alto_visible > 1 and solicitado > 1:
            self.canvas.itemconfigure(
                self._ventana, height=max(alto_visible, solicitado)
            )

    def _al_desplazar(self, primero: str, ultimo: str) -> None:
        self.barra.set(primero, ultimo)
        self._revisar_barra(primero, ultimo)

    def _revisar_barra(self, primero: str | None = None, ultimo: str | None = None) -> None:
        if primero is None or ultimo is None:
            primero, ultimo = self.canvas.yview()
        necesita = not (float(primero) <= 0.001 and float(ultimo) >= 0.999)
        if necesita and not self._barra_visible:
            self.barra.pack(side="right", fill="y", padx=(5, 0))
            self._barra_visible = True
        elif not necesita and self._barra_visible:
            self.barra.pack_forget()
            self._barra_visible = False

    def _rueda_raton(self, evento: tk.Event) -> str | None:
        try:
            x = evento.x_root - self.canvas.winfo_rootx()
            y = evento.y_root - self.canvas.winfo_rooty()
            if not (0 <= x <= self.canvas.winfo_width() and 0 <= y <= self.canvas.winfo_height()):
                return None
            if not self._barra_visible:
                return None
            paso = -int(evento.delta / 120) if evento.delta else 0
            if paso == 0:
                paso = -1 if evento.delta > 0 else 1
            self.canvas.yview_scroll(paso * 3, "units")
            return "break"
        except tk.TclError:
            return None

    def _al_destruir(self, evento: tk.Event) -> None:
        if evento.widget is not self:
            return
        try:
            self._toplevel.unbind("<MouseWheel>", self._bind_id)
        except (tk.TclError, AttributeError):
            pass

    def ir_al_inicio(self) -> None:
        self.canvas.yview_moveto(0)


# ---------------------------------------------------------------------------
# Tabla
# ---------------------------------------------------------------------------
class TablaDatos(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        columnas: Sequence[tuple[str, str, int, str]],
        *,
        alto: int = 8,
        fondo: str = tema.SUPERFICIE,
        mostrar_scroll: bool = True,
        mensaje_vacio: str = "Sin datos por mostrar.",
        al_seleccionar: Callable[[Any], None] | None = None,
        al_doble_clic: Callable[[Any], None] | None = None,
        autoseleccionar: bool = True,
    ):
        super().__init__(master, bg=fondo, bd=0, highlightthickness=0)
        self._columnas = list(columnas)
        self._fondo = fondo
        self._datos: dict[str, Any] = {}
        self.al_seleccionar = al_seleccionar
        self.al_doble_clic = al_doble_clic
        self._autoseleccionar = autoseleccionar
        self._mensaje_vacio = mensaje_vacio

        self.arbol = ttk.Treeview(
            self,
            columns=[c[0] for c in columnas],
            show="headings",
            selectmode="browse",
            height=alto,
            style="Treeview",
        )
        for clave, titulo, ancho, anchor in columnas:
            self.arbol.heading(clave, text=titulo)
            self.arbol.column(
                clave,
                width=ancho,
                minwidth=max(50, int(ancho * 0.55)),
                anchor=anchor,
                stretch=True,
            )
        self.arbol.pack(side="left", fill="both", expand=True)
        if mostrar_scroll:
            self._scroll = ttk.Scrollbar(
                self,
                orient="vertical",
                command=self.arbol.yview,
                style="Vertical.TScrollbar",
            )
            self._scroll.pack(side="right", fill="y", padx=(5, 0))
            self.arbol.configure(yscrollcommand=self._scroll.set)
        self._vacio = tk.Label(
            self,
            text=mensaje_vacio,
            bg=fondo,
            fg=tema.MUTED,
            font=_fuente_pequena(self),
            justify="center",
            wraplength=380,
        )
        self.arbol.bind("<<TreeviewSelect>>", self._seleccion_cambio)
        self.arbol.bind("<Double-1>", self._doble_clic)
        self._mostrar_vacio(True)

    def _mostrar_vacio(self, visible: bool) -> None:
        if visible:
            self._vacio.place(relx=0.5, rely=0.55, anchor="center")
        else:
            self._vacio.place_forget()

    def cargar(self, filas: Sequence[dict[str, Any]]) -> None:
        for item in self.arbol.get_children():
            self.arbol.delete(item)
        self._datos.clear()
        for indice, fila in enumerate(filas):
            iid = f"item_{indice}"
            self._datos[iid] = fila
            valores = [fila.get(clave, "") for clave, _t, _a, _an in self._columnas]
            etiquetas = fila.get("_tags") or ()
            if not isinstance(etiquetas, (list, tuple)):
                etiquetas = (etiquetas,)
            self.arbol.insert(
                "",
                "end",
                iid=iid,
                values=valores,
                tags=tuple(etiquetas),
            )
        self._mostrar_vacio(not filas)
        if filas and self._autoseleccionar:
            primero = self.arbol.get_children()
            if primero:
                self.arbol.selection_set(primero[0])
                self.arbol.focus(primero[0])

    def _seleccion_cambio(self, _evento: tk.Event) -> None:
        if self.al_seleccionar:
            self.al_seleccionar(self.seleccion())

    def _doble_clic(self, _evento: tk.Event) -> None:
        if self.al_doble_clic:
            self.al_doble_clic(self.seleccion())
        return "break"

    def seleccion(self) -> Any | None:
        seleccion = self.arbol.selection()
        if not seleccion:
            return None
        return self._datos.get(seleccion[0])

    def limpiar(self) -> None:
        self.cargar([])

    def seleccionar_primera(self) -> None:
        hijos = self.arbol.get_children()
        if hijos:
            self.arbol.selection_set(hijos[0])
            self.arbol.focus(hijos[0])

    def insertar_inicio(self, fila: dict[str, Any], iid: str | None = None) -> None:
        clave = iid or f"dinamica_{len(self._datos) + 1}"
        valores = [
            fila.get(col, "") for col, _titulo, _ancho, _anchor in self._columnas
        ]
        etiquetas = fila.get("_tags") or ()
        if not isinstance(etiquetas, (list, tuple)):
            etiquetas = (etiquetas,)
        self._datos[clave] = fila
        self.arbol.insert("", 0, iid=clave, values=valores, tags=tuple(etiquetas))
        self._mostrar_vacio(False)

    def configurar_mensaje_vacio(self, texto: str) -> None:
        self._mensaje_vacio = texto
        self._vacio.configure(text=texto)

    def aplicar_etiquetas(self, configuracion: dict[str, dict[str, str]]) -> None:
        for nombre, estilo in configuracion.items():
            self.arbol.tag_configure(nombre, **estilo)


# ---------------------------------------------------------------------------
# Encabezado de sección
# ---------------------------------------------------------------------------
def cabecera_seccion(
    master: tk.Misc,
    sobre_titulo: str,
    titulo: str,
    subtitulo: str = "",
    *,
    fondo: str = tema.FONDO,
) -> tk.Frame:
    marco = tk.Frame(master, bg=fondo)
    etiqueta(
        marco,
        sobre_titulo.upper(),
        fuente=_fuente_micro(master),
        color=tema.CARAMELO,
        fondo=fondo,
    ).pack(anchor="w")
    etiqueta(
        marco,
        titulo,
        fuente=_fuente_titulo(master),
        color=tema.TEXTO,
        fondo=fondo,
    ).pack(anchor="w", pady=(2, 2))
    if subtitulo:
        etiqueta(
            marco,
            subtitulo,
            fuente=_fuente_cuerpo(master),
            color=tema.MUTED,
            fondo=fondo,
            wraplength=880,
            justify="left",
        ).pack(anchor="w")
    return marco


def _fuente_titulo(widget: tk.Misc) -> tk.font.Font:
    app = getattr(widget.winfo_toplevel(), "_fuentes_app", None)
    if app is not None:
        return app.titulo
    return _fuente_cuerpo(widget)


# ---------------------------------------------------------------------------
# Diálogo base
# ---------------------------------------------------------------------------
class DialogoBase(tk.Toplevel):
    def __init__(
        self,
        padre: tk.Misc,
        titulo: str,
        *,
        ancho: int = 560,
        alto: int = 520,
        cerrar_con_escape: bool = True,
    ):
        super().__init__(padre)
        self.withdraw()
        self._fuentes_app = getattr(
            padre.winfo_toplevel(), "_fuentes_app", None
        )
        self.title(f"Dulcesitos Castillo · {titulo}")
        self.configure(bg=tema.FONDO)
        self.resizable(False, False)
        self.transient(padre.winfo_toplevel())
        self._ancho = ancho
        self._alto = alto
        self.tenedor = tk.Frame(self, bg=tema.FONDO)
        self.tenedor.pack(fill="both", expand=True)
        self.resultado: Any = None
        self._cerrado = False
        if cerrar_con_escape:
            self.bind("<Escape>", lambda _e: self.cerrar())
        self.protocol("WM_DELETE_WINDOW", self.cerrar)

    def mostrar(self) -> None:
        self.update_idletasks()
        padre = self.master.winfo_toplevel()
        try:
            ancho_padre = padre.winfo_width()
            alto_padre = padre.winfo_height()
            x_padre = padre.winfo_rootx()
            y_padre = padre.winfo_rooty()
        except tk.TclError:
            ancho_padre, alto_padre, x_padre, y_padre = 1366, 820, 0, 0
        x = x_padre + max(0, (ancho_padre - self._ancho) // 2)
        y = y_padre + max(0, (alto_padre - self._alto) // 2)
        self.geometry(f"{self._ancho}x{self._alto}+{x}+{y}")
        self.deiconify()
        self.lift()
        self.grab_set()
        self.focus_force()

    def cerrar(self) -> None:
        if self._cerrado:
            return
        self._cerrado = True
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()

    def centrar_en_padre(self) -> None:
        pass


class BotonEnlace(tk.Label):
    def __init__(
        self,
        master: tk.Misc,
        texto: str,
        comando: Callable[[], None],
        *,
        fondo: str = tema.SUPERFICIE,
        color: str = tema.CARAMELO,
    ):
        super().__init__(
            master,
            text=texto,
            bg=fondo,
            fg=color,
            font=_fuente_pequena(master),
            cursor="hand2",
            bd=0,
            highlightthickness=0,
        )
        self.comando = comando
        self.bind("<Button-1>", lambda _e: self.comando())
        self.bind("<Enter>", lambda _e: self.configure(fg=tema.ROSA_CLARA))
        self.bind("<Leave>", lambda _e: self.configure(fg=color))
