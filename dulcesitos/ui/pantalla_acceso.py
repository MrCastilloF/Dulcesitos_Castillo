"""Pantallas de primer arranque, ingreso y registro de operadores."""

from __future__ import annotations

import re
import tkinter as tk

from ..seguridad import validar_fortaleza_clave
from ..servicios import ErrorAutenticacion
from ..utilidades import ErrorValidacion, formatear_fecha_hora
from . import tema
from .componentes import (
    BannerEstado,
    Boton,
    BotonEnlace,
    Campo,
    MarcaCandy,
    SelectorSegmentado,
    etiqueta,
    separador,
)

HEROE = "#211016"
HEROE_2 = "#2B141B"
SUPERFICIE_LOGIN = "#1C1412"


def _solo_digitos(texto: str, maximo: int = 12) -> str:
    return re.sub(r"[^0-9]", "", texto)[:maximo]


def _codigo_acceso(texto: str) -> str:
    limpio = re.sub(r"[^A-Za-z0-9-]", "", texto).upper()[:18]
    return limpio


def _panel_heroe(padre: tk.Misc, *, compacto: bool = False) -> tk.Frame:
    marco = tk.Frame(padre, bg=HEROE)
    pie = tk.Frame(marco, bg=HEROE)
    pie.pack(fill="x", side="bottom", padx=44, pady=(0, 26))
    separador(pie, tema.BORDE, 1).pack(fill="x", pady=(0, 12))
    fila_pie = tk.Frame(pie, bg=HEROE)
    fila_pie.pack(fill="x")
    etiqueta(
        fila_pie,
        "CARLOS CASTILLO · PROYECTO FORMATIVO",
        fuente=tema_fuente_micro(padre),
        color=tema.MUTED,
        fondo=HEROE,
    ).pack(side="left")
    etiqueta(
        fila_pie,
        "BODEGA · 2026",
        fuente=tema_fuente_micro(padre),
        color=tema.CARAMELO,
        fondo=HEROE,
    ).pack(side="right")

    contenido = tk.Frame(marco, bg=HEROE)
    contenido.pack(fill="both", expand=True, padx=44 if not compacto else 32, pady=34)

    chip = tk.Frame(contenido, bg=HEROE_2)
    chip.pack(anchor="w", pady=(0, 26))
    tk.Frame(chip, bg=tema.CARAMELO, width=18, height=3).pack(side="left", padx=(11, 8), pady=10)
    etiqueta(
        chip,
        "OPERADOR DE INVENTARIOS · SENA",
        fuente=tema_fuente_micro(padre),
        color=tema.CARAMELO_CLARO,
        fondo=HEROE_2,
    ).pack(side="left", padx=(0, 13), pady=6)
    etiqueta(
        chip,
        "DULCESITOS CASTILLO",
        fuente=tema_fuente_micro(padre),
        color=tema.MUTED,
        fondo=HEROE_2,
    ).pack(side="left", padx=(0, 11), pady=6)

    etiqueta(
        contenido,
        "Cada dulce,",
        fuente=tema_fuente_display(padre),
        color=tema.CREMA,
        fondo=HEROE,
    ).pack(anchor="w")
    etiqueta(
        contenido,
        "en su lugar.",
        fuente=tema_fuente_display(padre),
        color=tema.ROSA,
        fondo=HEROE,
    ).pack(anchor="w")
    etiqueta(
        contenido,
        "Un registro de bodega claro, rápido y trazable.\n"
        "Escanea, confirma y cierra tu inventario sin papeles.",
        fuente=tema_fuente_cuerpo(padre),
        color=tema.TEXTO_SUAVE,
        fondo=HEROE,
        justify="left",
    ).pack(anchor="w", pady=(18, 24))

    for titulo, descripcion in [
        ("Catálogo maestro validado", "Cada código se contrasta antes de registrarse."),
        ("Lector USB calibrado", "La prueba de sincronización es obligatoria."),
        ("Trazabilidad completa", "Operador, fecha y hora en cada producto."),
    ]:
        fila = tk.Frame(contenido, bg=HEROE)
        fila.pack(fill="x", anchor="w", pady=7)
        icono = tk.Canvas(fila, width=30, height=30, bg=HEROE, highlightthickness=0, bd=0)
        icono.pack(side="left", padx=(0, 12), anchor="n")
        icono.create_oval(2, 2, 28, 28, fill=tema.VERDE_FONDO, outline="#1F6650")
        icono.create_text(15, 16, text="✓", fill=tema.VERDE, font=("Segoe UI", 11, "bold"))
        textos = tk.Frame(fila, bg=HEROE)
        textos.pack(side="left", fill="x", expand=True)
        etiqueta(
            textos,
            titulo,
            fuente=tema_fuente_cuerpo_fuerte(padre),
            color=tema.CREMA,
            fondo=HEROE,
        ).pack(anchor="w")
        etiqueta(
            textos,
            descripcion,
            fuente=tema_fuente_pequena(padre),
            color=tema.MUTED,
            fondo=HEROE,
            wraplength=470,
            justify="left",
        ).pack(anchor="w", pady=(1, 0))

    return marco


def tema_fuente_micro(widget: tk.Misc) -> tk.font.Font:
    app = getattr(widget.winfo_toplevel(), "_fuentes_app", None)
    return app.micro if app else tk.font.nametofont("TkDefaultFont")


def tema_fuente_pequena(widget: tk.Misc) -> tk.font.Font:
    app = getattr(widget.winfo_toplevel(), "_fuentes_app", None)
    return app.pequena if app else tk.font.nametofont("TkDefaultFont")


def tema_fuente_cuerpo(widget: tk.Misc) -> tk.font.Font:
    app = getattr(widget.winfo_toplevel(), "_fuentes_app", None)
    return app.cuerpo if app else tk.font.nametofont("TkDefaultFont")


def tema_fuente_cuerpo_fuerte(widget: tk.Misc) -> tk.font.Font:
    app = getattr(widget.winfo_toplevel(), "_fuentes_app", None)
    return app.cuerpo_fuerte if app else tk.font.nametofont("TkDefaultFont")


def tema_fuente_display(widget: tk.Misc) -> tk.font.Font:
    app = getattr(widget.winfo_toplevel(), "_fuentes_app", None)
    return app.display if app else tk.font.nametofont("TkDefaultFont")


def tema_fuente_titulo(widget: tk.Misc) -> tk.font.Font:
    app = getattr(widget.winfo_toplevel(), "_fuentes_app", None)
    return app.titulo if app else tk.font.nametofont("TkDefaultFont")


class PantallaAcceso(tk.Frame):
    """Ingreso de operadores y activación de códigos emitidos por el admin."""

    def __init__(
        self,
        master: tk.Misc,
        app,
        *,
        mensaje_exito: str = "",
        aviso: str = "",
        tab: str = "login",
    ):
        super().__init__(master, bg=tema.FONDO)
        self.app = app
        self._modo = "registro" if tab == "registro" else "login"
        self._mensaje_exito = mensaje_exito
        self._aviso = aviso

        contenedor = tk.Frame(self, bg=tema.FONDO)
        contenedor.pack(fill="both", expand=True, padx=26, pady=18)
        contenedor.grid_columnconfigure(0, weight=11, uniform="acceso")
        contenedor.grid_columnconfigure(1, weight=9, uniform="acceso")
        contenedor.grid_rowconfigure(0, weight=1)

        self.heroe = _panel_heroe(contenedor)
        self.heroe.grid(row=0, column=0, sticky="nsew", padx=(0, 18))

        zona_derecha = tk.Frame(contenedor, bg=tema.FONDO)
        zona_derecha.grid(row=0, column=1, sticky="nsew")
        zona_derecha.grid_rowconfigure(0, weight=1)
        zona_derecha.grid_columnconfigure(0, weight=1)

        self.tarjeta = tk.Frame(
            zona_derecha,
            bg=tema.SUPERFICIE,
            highlightbackground=tema.BORDE,
            highlightthickness=1,
            bd=0,
        )
        self.tarjeta.grid(row=0, column=0, sticky="nsew", pady=4)
        interior = tk.Frame(self.tarjeta, bg=tema.SUPERFICIE)
        interior.pack(fill="both", expand=True, padx=32, pady=27)

        etiqueta(
            interior,
            "ACCESO OPERATIVO",
            fuente=tema_fuente_micro(self),
            color=tema.CARAMELO,
            fondo=tema.SUPERFICIE,
        ).pack(anchor="w")
        self.titulo = etiqueta(
            interior,
            "Ingresa a tu estación",
            fuente=tema_fuente_titulo(self),
            color=tema.TEXTO,
            fondo=tema.SUPERFICIE,
        )
        self.titulo.pack(anchor="w", pady=(4, 3))
        self.subtitulo = etiqueta(
            interior,
            "Tu código es personal y tiene fecha de vencimiento.",
            fuente=tema_fuente_pequena(self),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
            wraplength=500,
            justify="left",
        )
        self.subtitulo.pack(anchor="w", pady=(0, 14))

        self.selector = SelectorSegmentado(
            interior,
            [("login", "Ingresar"), ("registro", "Activar código")],
            self._cambiar_modo,
            ancho=460,
            alto=42,
            fondo=tema.SUPERFICIE,
            seleccionado=self._modo,
        )
        self.selector.pack(fill="x", pady=(0, 17))

        self.banner = BannerEstado(interior, fondo=tema.SUPERFICIE)
        self._banner_visible = False

        self.formulario = tk.Frame(interior, bg=tema.SUPERFICIE)
        self.formulario.pack(fill="x")
        self.formulario.grid_columnconfigure(0, weight=1, uniform="campos")
        self.formulario.grid_columnconfigure(1, weight=1, uniform="campos")

        self._construir_formulario_login()
        self._construir_formulario_registro()

        self.boton_enviar = Boton(
            interior,
            "Ingresar a la estación",
            self._enviar,
            variante="primario",
            icono="→",
            ancho=240,
            alto=48,
            fondo=tema.SUPERFICIE,
        )
        self.boton_enviar.pack(fill="x", pady=(15, 0))
        self._mostrar_formulario()

        pie = tk.Frame(interior, bg=tema.SUPERFICIE)
        pie.pack(fill="x", pady=(13, 0))
        etiqueta(
            pie,
            "¿Olvidaste tu código o venció?",
            fuente=tema_fuente_pequena(self),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
        ).pack(side="left")
        BotonEnlace(
            pie,
            "Solicita uno nuevo al administrador",
            self._ir_admin,
            fondo=tema.SUPERFICIE,
            color=tema.CARAMELO,
        ).pack(side="left", padx=(4, 0))

        self._proteccion = tk.Frame(interior, bg=tema.SUPERFICIE)
        self._proteccion.pack(fill="x", pady=(31, 0))
        separador(self._proteccion, tema.BORDE, 1).pack(fill="x", pady=(0, 15))
        etiqueta(
            self._proteccion,
            "ESTACIÓN PROTEGIDA",
            fuente=tema_fuente_micro(self),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
        ).pack(anchor="w")
        chips = tk.Frame(self._proteccion, bg=tema.SUPERFICIE)
        chips.pack(fill="x", pady=(9, 0))
        for columna in range(3):
            chips.grid_columnconfigure(columna, weight=1, uniform="proteccion")
        for indice, (simbolo, texto) in enumerate(
            [
                ("⌁", "Credenciales\ncon hash"),
                ("▣", "Registros\nguardados"),
                ("✓", "Cierre con\nautorización"),
            ]
        ):
            caja = tk.Frame(chips, bg=tema.SUPERFICIE_2)
            caja.grid(
                row=0,
                column=indice,
                sticky="nsew",
                padx=(0 if indice == 0 else 4, 0 if indice == 2 else 4),
            )
            etiqueta(
                caja,
                simbolo,
                fuente=tema_fuente_cuerpo_fuerte(caja),
                color=tema.CARAMELO,
                fondo=tema.SUPERFICIE_2,
            ).pack(anchor="w", padx=10, pady=(8, 0))
            etiqueta(
                caja,
                texto,
                fuente=tema_fuente_micro(caja),
                color=tema.TEXTO_SUAVE,
                fondo=tema.SUPERFICIE_2,
                justify="left",
            ).pack(anchor="w", padx=10, pady=(1, 8))

        self._nota_inferior = tk.Frame(interior, bg=tema.SUPERFICIE_2)
        self._nota_inferior.pack(fill="x", side="bottom", pady=(18, 0))
        etiqueta(
            self._nota_inferior,
            "Solo el administrador puede crear, asignar, renovar o revocar códigos.",
            fuente=tema_fuente_micro(self),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE_2,
            wraplength=450,
            justify="left",
        ).pack(anchor="w", padx=11, pady=8)

        if self._mensaje_exito:
            self._mostrar_banner(self._mensaje_exito, "ok")
        elif self._aviso:
            self._mostrar_banner(self._aviso, "advertencia")
        self.after(120, self._enfocar_inicial)
        self.after(180, self._adaptar_altura)

    def _adaptar_altura(self) -> None:
        """En pantallas bajas oculta adornos para no recortar el formulario."""

        try:
            alto = self.winfo_toplevel().winfo_height()
            if alto and alto < 780:
                self._proteccion.pack_forget()
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Formularios
    # ------------------------------------------------------------------
    def _construir_formulario_login(self) -> None:
        self.form_login = tk.Frame(self.formulario, bg=tema.SUPERFICIE)
        self.form_login.grid_columnconfigure(0, weight=1, uniform="campos")
        self.form_login.grid_columnconfigure(1, weight=1, uniform="campos")
        self.login_cedula = Campo(
            self.form_login,
            "Cédula",
            ayuda="",
            transformacion=_solo_digitos,
            fondo=tema.SUPERFICIE,
            fuente=tema_fuente_cuerpo(self),
        )
        self.login_cedula.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.login_codigo = Campo(
            self.form_login,
            "Código de acceso",
            secreto=True,
            ayuda="",
            transformacion=_codigo_acceso,
            fondo=tema.SUPERFICIE,
            fuente=tema_fuente_cuerpo(self),
            on_enter=self._enviar,
        )
        self.login_codigo.grid(row=0, column=1, sticky="ew", padx=(8, 0))

    def _construir_formulario_registro(self) -> None:
        self.form_registro = tk.Frame(self.formulario, bg=tema.SUPERFICIE)
        for columna in range(2):
            self.form_registro.grid_columnconfigure(columna, weight=1, uniform="campos")
        self.reg_nombre = Campo(
            self.form_registro,
            "Nombre completo",
            ayuda="",
            fondo=tema.SUPERFICIE,
            fuente=tema_fuente_cuerpo(self),
        )
        self.reg_nombre.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self.reg_cedula = Campo(
            self.form_registro,
            "Cédula",
            ayuda="",
            transformacion=_solo_digitos,
            fondo=tema.SUPERFICIE,
            fuente=tema_fuente_cuerpo(self),
        )
        self.reg_cedula.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(0, 8))
        self.reg_correo = Campo(
            self.form_registro,
            "Correo electrónico",
            ayuda="",
            fondo=tema.SUPERFICIE,
            fuente=tema_fuente_cuerpo(self),
        )
        self.reg_correo.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(0, 8))
        self.reg_codigo = Campo(
            self.form_registro,
            "Código entregado por el administrador",
            secreto=True,
            ayuda="Formato DLC-XXXX-XXXX-XXXX. Se activa una sola vez.",
            transformacion=_codigo_acceso,
            fondo=tema.SUPERFICIE,
            fuente=tema_fuente_cuerpo(self),
            on_enter=self._enviar,
        )
        self.reg_codigo.grid(row=2, column=0, columnspan=2, sticky="ew")

    def _mostrar_formulario(self) -> None:
        self.form_login.grid_forget()
        self.form_registro.grid_forget()
        if self._modo == "login":
            self.form_login.grid(row=0, column=0, columnspan=2, sticky="ew")
            self.titulo.configure(text="Ingresa a tu estación")
            self.subtitulo.configure(
                text="Tu código es personal y tiene fecha de vencimiento."
            )
            self.boton_enviar.configurar_texto("Ingresar a la estación", icono="→")
        else:
            self.form_registro.grid(row=0, column=0, columnspan=2, sticky="ew")
            self.titulo.configure(text="Activa tu código")
            self.subtitulo.configure(
                text="Completa tus datos una sola vez con el código que te entregó el administrador."
            )
            self.boton_enviar.configurar_texto("Validar y crear mi acceso", icono="✓")
        self.update_idletasks()

    def _cambiar_modo(self, modo: str) -> None:
        if modo == self._modo:
            return
        self._modo = modo
        if hasattr(self, "selector") and self.selector.seleccion != modo:
            self.selector.seleccionar(modo)
        self._ocultar_banner()
        for campo in (
            self.login_cedula,
            self.login_codigo,
            self.reg_nombre,
            self.reg_cedula,
            self.reg_correo,
            self.reg_codigo,
        ):
            campo.establecer_error(None)
        self._mostrar_formulario()
        self.after(100, self._enfocar_inicial)

    def _enfocar_inicial(self) -> None:
        if self._modo == "login":
            self.login_cedula.enfocar()
        else:
            self.reg_nombre.enfocar()

    def _ir_admin(self) -> None:
        self.app.abrir_panel_admin()

    # ------------------------------------------------------------------
    # Envío
    # ------------------------------------------------------------------
    def _mostrar_banner(self, mensaje: str, estado: str, titulo: str = "") -> None:
        if not titulo:
            titulo = {
                "ok": "Todo listo",
                "error": "No pudimos continuar",
                "advertencia": "Revisa la información",
                "info": "Ten en cuenta",
            }.get(estado, "Aviso")
        self.banner.mostrar(titulo, mensaje, estado)
        if not self._banner_visible:
            self.banner.pack(fill="x", pady=(0, 14), before=self.formulario)
            self._banner_visible = True

    def _ocultar_banner(self) -> None:
        if self._banner_visible:
            self.banner.pack_forget()
            self._banner_visible = False

    def _enviar(self) -> None:
        if self._modo == "login":
            self._ingresar()
        else:
            self._registrar()

    def _ocupar_boton(self, texto: str) -> None:
        self.boton_enviar.configurar_estado("deshabilitado")
        self.boton_enviar.configurar_texto(texto)
        self.update_idletasks()

    def _liberar_boton(self) -> None:
        self.boton_enviar.configurar_estado("normal")
        self.boton_enviar.configurar_texto(
            "Ingresar a la estación" if self._modo == "login" else "Validar y crear mi acceso",
            icono="→" if self._modo == "login" else "✓",
        )

    def _ingresar(self) -> None:
        cedula = self.login_cedula.get().strip()
        codigo = self.login_codigo.get().strip()
        self._ocultar_banner()
        self.login_cedula.establecer_error(None)
        self.login_codigo.establecer_error(None)
        if not cedula:
            self.login_cedula.establecer_error("Escribe tu cédula.")
            self.login_cedula.enfocar()
            return
        if not codigo:
            self.login_codigo.establecer_error("Escribe tu código de acceso.")
            self.login_codigo.enfocar()
            return
        self._ocupar_boton("Verificando acceso…")
        try:
            operador = self.app.auth.iniciar_sesion_operador(cedula, codigo)
        except ErrorAutenticacion as exc:
            self.app.sonidos.error()
            self._mostrar_banner(str(exc), "error")
            self.login_codigo.establecer_error("Verifica el código e intenta de nuevo.")
            self.login_codigo.set("")
            self.login_codigo.enfocar()
            self._liberar_boton()
            return
        except Exception as exc:
            self.app.sonidos.error()
            self._mostrar_banner(f"Error inesperado al ingresar: {exc}", "error")
            self._liberar_boton()
            return
        self.app.sonidos.exito()
        self.app.iniciar_sesion_operador(operador)

    def _registrar(self) -> None:
        nombre = self.reg_nombre.get().strip()
        cedula = self.reg_cedula.get().strip()
        correo = self.reg_correo.get().strip()
        codigo = self.reg_codigo.get().strip()
        self._ocultar_banner()
        for campo in (self.reg_nombre, self.reg_cedula, self.reg_correo, self.reg_codigo):
            campo.establecer_error(None)
        if not nombre:
            self.reg_nombre.establecer_error("Escribe tu nombre completo.")
            self.reg_nombre.enfocar()
            return
        if not cedula:
            self.reg_cedula.establecer_error("Escribe tu cédula.")
            self.reg_cedula.enfocar()
            return
        if not correo:
            self.reg_correo.establecer_error("Escribe tu correo electrónico.")
            self.reg_correo.enfocar()
            return
        if not codigo:
            self.reg_codigo.establecer_error("Escribe el código que te entregó el administrador.")
            self.reg_codigo.enfocar()
            return
        self._ocupar_boton("Validando código…")
        try:
            operador = self.app.auth.registrar_operador(
                nombre=nombre,
                cedula=cedula,
                correo=correo,
                codigo=codigo,
            )
        except (ErrorAutenticacion, ErrorValidacion) as exc:
            self.app.sonidos.error()
            self._mostrar_banner(str(exc), "error")
            self._liberar_boton()
            return
        except Exception as exc:
            self.app.sonidos.error()
            self._mostrar_banner(f"Error inesperado al crear el acceso: {exc}", "error")
            self._liberar_boton()
            return
        self.app.sonidos.exito()
        vence = (
            formatear_fecha_hora(operador.acceso_expira_en)
            if operador.acceso_expira_en
            else "la fecha indicada por el administrador"
        )
        self.app.iniciar_sesion_operador(
            operador,
            mensaje_bienvenida=(
                f"Acceso activado. Vence el {vence}. Escanea con calma: "
                "cada producto queda guardado al instante."
            ),
        )


class PantallaConfiguracionInicial(tk.Frame):
    """Creación única del administrador del sistema."""

    def __init__(self, master: tk.Misc, app):
        super().__init__(master, bg=tema.FONDO)
        self.app = app

        contenedor = tk.Frame(self, bg=tema.FONDO)
        contenedor.pack(fill="both", expand=True, padx=26, pady=18)
        contenedor.grid_columnconfigure(0, weight=8, uniform="inicio")
        contenedor.grid_columnconfigure(1, weight=12, uniform="inicio")
        contenedor.grid_rowconfigure(0, weight=1)

        lateral = tk.Frame(contenedor, bg=HEROE)
        lateral.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        self._construir_lateral(lateral)

        self.tarjeta = tk.Frame(
            contenedor,
            bg=tema.SUPERFICIE,
            highlightbackground=tema.BORDE,
            highlightthickness=1,
        )
        self.tarjeta.grid(row=0, column=1, sticky="nsew", pady=4)
        cuerpo = tk.Frame(self.tarjeta, bg=tema.SUPERFICIE)
        cuerpo.pack(fill="both", expand=True, padx=38, pady=28)

        etiqueta(
            cuerpo,
            "CONFIGURACIÓN ÚNICA · PASO 0",
            fuente=tema_fuente_micro(self),
            color=tema.CARAMELO,
            fondo=tema.SUPERFICIE,
        ).pack(anchor="w")
        etiqueta(
            cuerpo,
            "Crea el primer administrador",
            fuente=tema_fuente_titulo(self),
            color=tema.TEXTO,
            fondo=tema.SUPERFICIE,
        ).pack(anchor="w", pady=(3, 4))
        etiqueta(
            cuerpo,
            "Esta cuenta podrá emitir, renovar y revocar los códigos de acceso de "
            "los operadores. No existe recuperación automática de la clave.",
            fuente=tema_fuente_pequena(self),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
            wraplength=650,
            justify="left",
        ).pack(anchor="w", pady=(0, 15))

        self.banner = BannerEstado(cuerpo, fondo=tema.SUPERFICIE)
        self._banner_visible = False

        formulario = tk.Frame(cuerpo, bg=tema.SUPERFICIE)
        formulario.pack(fill="x")
        self.formulario = formulario
        formulario.grid_columnconfigure(0, weight=1, uniform="admin")
        formulario.grid_columnconfigure(1, weight=1, uniform="admin")

        self.nombre = Campo(
            formulario,
            "Nombre completo del administrador",
            fondo=tema.SUPERFICIE,
            fuente=tema_fuente_cuerpo(self),
        )
        self.nombre.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        self.cedula = Campo(
            formulario,
            "Cédula",
            transformacion=_solo_digitos,
            fondo=tema.SUPERFICIE,
            fuente=tema_fuente_cuerpo(self),
        )
        self.cedula.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=(0, 10))
        self.correo = Campo(
            formulario,
            "Correo electrónico",
            fondo=tema.SUPERFICIE,
            fuente=tema_fuente_cuerpo(self),
        )
        self.correo.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=(0, 10))
        self.clave = Campo(
            formulario,
            "Clave de administración",
            secreto=True,
            ayuda="Mínimo 10 caracteres, con letra y número. No uses espacios.",
            fondo=tema.SUPERFICIE,
            fuente=tema_fuente_cuerpo(self),
        )
        self.clave.grid(row=2, column=0, sticky="ew", padx=(0, 8), pady=(0, 10))
        self.confirmacion = Campo(
            formulario,
            "Confirmar clave",
            secreto=True,
            ayuda="La clave protege todo el panel administrativo.",
            fondo=tema.SUPERFICIE,
            fuente=tema_fuente_cuerpo(self),
            on_enter=self._crear,
        )
        self.confirmacion.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(0, 10))

        fila_botones = tk.Frame(cuerpo, bg=tema.SUPERFICIE)
        fila_botones.pack(fill="x", pady=(8, 0))
        self.boton = Boton(
            fila_botones,
            "Crear administrador",
            self._crear,
            variante="primario",
            icono="→",
            ancho=230,
            alto=48,
            fondo=tema.SUPERFICIE,
        )
        self.boton.pack(side="right")
        etiqueta(
            fila_botones,
            "La base de datos se guarda en el perfil de Windows.",
            fuente=tema_fuente_micro(self),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
        ).pack(side="left")

        self._proteccion_config = tk.Frame(cuerpo, bg=tema.SUPERFICIE)
        self._proteccion_config.pack(fill="x", pady=(25, 0))
        separador(self._proteccion_config, tema.BORDE, 1).pack(fill="x", pady=(0, 13))
        etiqueta(
            self._proteccion_config,
            "PROTECCIÓN APLICADA",
            fuente=tema_fuente_micro(self),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
        ).pack(anchor="w")
        chips = tk.Frame(self._proteccion_config, bg=tema.SUPERFICIE)
        chips.pack(fill="x", pady=(8, 0))
        for columna in range(3):
            chips.grid_columnconfigure(columna, weight=1, uniform="proteccion_admin")
        for indice, (simbolo, texto) in enumerate(
            [
                ("⌁", "Hash PBKDF2\ncon sal única"),
                ("▣", "Datos locales\nen tu perfil"),
                ("✓", "Sin claves\npor defecto"),
            ]
        ):
            caja = tk.Frame(chips, bg=tema.SUPERFICIE_2)
            caja.grid(
                row=0,
                column=indice,
                sticky="nsew",
                padx=(0 if indice == 0 else 4, 0 if indice == 2 else 4),
            )
            etiqueta(
                caja,
                simbolo,
                fuente=tema_fuente_cuerpo_fuerte(caja),
                color=tema.CARAMELO,
                fondo=tema.SUPERFICIE_2,
            ).pack(anchor="w", padx=10, pady=(8, 0))
            etiqueta(
                caja,
                texto,
                fuente=tema_fuente_micro(caja),
                color=tema.TEXTO_SUAVE,
                fondo=tema.SUPERFICIE_2,
                justify="left",
            ).pack(anchor="w", padx=10, pady=(1, 8))

        aviso = tk.Frame(cuerpo, bg=tema.SUPERFICIE_2)
        aviso.pack(fill="x", side="bottom", pady=(18, 0))
        etiqueta(
            aviso,
            "Recomendación: guarda la clave de administración en un gestor de "
            "contraseñas o en un sobre sellado. Solo se almacena su hash.",
            fuente=tema_fuente_micro(self),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE_2,
            wraplength=620,
            justify="left",
        ).pack(anchor="w", padx=12, pady=10)
        self.after(130, self.nombre.enfocar)
        self.after(200, self._adaptar_altura_config)

    def _adaptar_altura_config(self) -> None:
        try:
            if self.winfo_toplevel().winfo_height() and self.winfo_toplevel().winfo_height() < 780:
                self._proteccion_config.pack_forget()
        except tk.TclError:
            pass

    def _construir_lateral(self, marco: tk.Frame) -> None:
        pie = tk.Frame(marco, bg=HEROE)
        pie.pack(fill="x", side="bottom", padx=38, pady=(0, 28))
        etiqueta(
            pie,
            "Las credenciales nunca se guardan en texto plano.",
            fuente=tema_fuente_micro(self),
            color=tema.MUTED,
            fondo=HEROE,
            wraplength=320,
            justify="left",
        ).pack(anchor="w")
        contenido = tk.Frame(marco, bg=HEROE)
        contenido.pack(fill="both", expand=True, padx=38, pady=36)
        MarcaCandy(contenido, 50, fondo=HEROE).pack(anchor="w", pady=(0, 22))
        etiqueta(
            contenido,
            "Antes de abrir\nla bodega,",
            fuente=tema_fuente_display(self),
            color=tema.CREMA,
            fondo=HEROE,
            justify="left",
        ).pack(anchor="w")
        etiqueta(
            contenido,
            "protege la llave.",
            fuente=tema_fuente_display(self),
            color=tema.ROSA,
            fondo=HEROE,
        ).pack(anchor="w")
        etiqueta(
            contenido,
            "El administrador es la única persona que puede emitir códigos de "
            "acceso para los operadores. Su clave es independiente de las claves "
            "de operación.",
            fuente=tema_fuente_cuerpo(self),
            color=tema.TEXTO_SUAVE,
            fondo=HEROE,
            wraplength=330,
            justify="left",
        ).pack(anchor="w", pady=(18, 24))
        pasos = [
            ("01", "Crea esta cuenta una sola vez."),
            ("02", "Emite el primer código desde el panel."),
            ("03", "Entrega el código al operador de forma presencial."),
        ]
        for numero, texto in pasos:
            fila = tk.Frame(contenido, bg=HEROE)
            fila.pack(fill="x", pady=8)
            etiqueta(
                fila,
                numero,
                fuente=tema_fuente_micro(self),
                color=tema.CARAMELO,
                fondo=HEROE,
                anchor="w",
            ).pack(side="left", anchor="n", pady=2)
            etiqueta(
                fila,
                texto,
                fuente=tema_fuente_pequena(self),
                color=tema.TEXTO_SUAVE,
                fondo=HEROE,
                wraplength=290,
                justify="left",
            ).pack(side="left", padx=(12, 0), anchor="w")

    def _mostrar_banner(self, mensaje: str, estado: str) -> None:
        self.banner.mostrar(
            "Revisa la información" if estado != "error" else "No pudimos crear la cuenta",
            mensaje,
            estado,
        )
        if not self._banner_visible:
            self.banner.pack(fill="x", pady=(0, 14), before=self.formulario)
            self._banner_visible = True

    def _crear(self) -> None:
        nombre = self.nombre.get().strip()
        cedula = self.cedula.get().strip()
        correo = self.correo.get().strip()
        clave = self.clave.get()
        confirmacion = self.confirmacion.get()
        for campo in (self.nombre, self.cedula, self.correo, self.clave, self.confirmacion):
            campo.establecer_error(None)
        errores = validar_fortaleza_clave(clave) if clave else ["Escribe una clave de administración."]
        if not confirmacion:
            errores.append("Confirma la clave.")
        elif clave != confirmacion:
            errores.append("Las dos claves no coinciden.")
        if errores:
            self._mostrar_banner(" ".join(errores), "error")
            return
        self.boton.configurar_estado("deshabilitado")
        self.boton.configurar_texto("Creando cuenta segura…")
        self.update_idletasks()
        try:
            admin = self.app.auth.crear_administrador_inicial(
                nombre=nombre,
                cedula=cedula,
                correo=correo,
                clave=clave,
                confirmacion=confirmacion,
            )
        except (ErrorValidacion, ErrorAutenticacion) as exc:
            self.app.sonidos.error()
            self._mostrar_banner(str(exc), "error")
            self.boton.configurar_estado("normal")
            self.boton.configurar_texto("Crear administrador", icono="→")
            return
        except Exception as exc:
            self.app.sonidos.error()
            self._mostrar_banner(f"Error inesperado: {exc}", "error")
            self.boton.configurar_estado("normal")
            self.boton.configurar_texto("Crear administrador", icono="→")
            return
        self.app.sonidos.exito()
        self.app.ir_acceso(
            mensaje_exito=(
                f"Administrador {admin.nombre} creado. Abre el panel de "
                "administración para emitir el primer código de operador."
            )
        )
