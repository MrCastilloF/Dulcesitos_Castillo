"""Diálogos modales de la aplicación."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import Any

from ..archivo_maestro import ArchivoMaestro, convertir_numero
from ..modelos import (
    EstadisticasSesion,
    ResultadoAutorizacion,
    Sesion,
    SesionOperador,
)
from ..seguridad import validar_fortaleza_clave
from ..servicios import (
    ErrorAdministracion,
    ErrorAutenticacion,
    ErrorInventario,
)
from ..utilidades import ErrorValidacion, formatear_fecha_hora
from . import tema
from .componentes import (
    BannerEstado,
    Boton,
    Campo,
    DialogoBase,
    MarcaCandy,
    Pildora,
    etiqueta,
    separador,
)


def _cabecera_dialogo(
    padre: tk.Misc,
    titulo: str,
    subtitulo: str = "",
    *,
    icono: str = "DULCESITOS CASTILLO",
) -> tk.Frame:
    marco = tk.Frame(padre, bg=tema.SUPERFICIE)
    marco.pack(fill="x")
    fila = tk.Frame(marco, bg=tema.SUPERFICIE)
    fila.pack(fill="x", padx=24, pady=(18, 14))
    MarcaCandy(fila, 38, fondo=tema.SUPERFICIE).pack(side="left", padx=(0, 12))
    textos = tk.Frame(fila, bg=tema.SUPERFICIE)
    textos.pack(side="left", fill="x", expand=True)
    etiqueta(
        textos,
        icono,
        fuente=tema_fuente_micro(padre),
        color=tema.CARAMELO,
        fondo=tema.SUPERFICIE,
    ).pack(anchor="w")
    etiqueta(
        textos,
        titulo,
        fuente=tema_fuente_encabezado(padre),
        color=tema.TEXTO,
        fondo=tema.SUPERFICIE,
    ).pack(anchor="w")
    if subtitulo:
        etiqueta(
            textos,
            subtitulo,
            fuente=tema_fuente_pequena(padre),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
        ).pack(anchor="w", pady=(2, 0))
    # Se evita un borde inferior que compita con el contenido.
    return marco


def tema_fuente_micro(widget: tk.Misc) -> tk.font.Font:
    app = getattr(widget.winfo_toplevel(), "_fuentes_app", None)
    if app:
        return app.micro
    return tk.font.nametofont("TkDefaultFont")


def tema_fuente_pequena(widget: tk.Misc) -> tk.font.Font:
    app = getattr(widget.winfo_toplevel(), "_fuentes_app", None)
    if app:
        return app.pequena
    return tk.font.nametofont("TkDefaultFont")


def tema_fuente_cuerpo(widget: tk.Misc) -> tk.font.Font:
    app = getattr(widget.winfo_toplevel(), "_fuentes_app", None)
    if app:
        return app.cuerpo
    return tk.font.nametofont("TkDefaultFont")


def tema_fuente_encabezado(widget: tk.Misc) -> tk.font.Font:
    app = getattr(widget.winfo_toplevel(), "_fuentes_app", None)
    if app:
        return app.encabezado
    return tk.font.nametofont("TkDefaultFont")


def tema_fuente_cuerpo_fuerte(widget: tk.Misc) -> tk.font.Font:
    app = getattr(widget.winfo_toplevel(), "_fuentes_app", None)
    if app:
        return app.cuerpo_fuerte
    return tk.font.nametofont("TkDefaultFont")


def tema_fuente_titulo(widget: tk.Misc) -> tk.font.Font:
    app = getattr(widget.winfo_toplevel(), "_fuentes_app", None)
    if app:
        return app.titulo
    return tk.font.nametofont("TkDefaultFont")


class DialogoMensaje(DialogoBase):
    """Aviso o confirmación con la identidad visual de la aplicación."""

    def __init__(
        self,
        padre: tk.Misc,
        *,
        titulo: str,
        mensaje: str,
        estado: str = "info",
        texto_aceptar: str = "Entendido",
        texto_cancelar: str | None = None,
        detalle: str = "",
    ):
        ancho = 600
        alto = 410 if detalle else 360
        super().__init__(padre, titulo, ancho=ancho, alto=alto)
        self.resultado = False
        colores = tema.color_estado(estado)
        self.tenedor.configure(bg=tema.FONDO)

        cuerpo = tk.Frame(self.tenedor, bg=tema.FONDO)
        cuerpo.pack(fill="both", expand=True, padx=28, pady=24)
        icono = tk.Canvas(
            cuerpo,
            width=52,
            height=52,
            bg=tema.FONDO,
            highlightthickness=0,
            bd=0,
        )
        icono.pack(anchor="w")
        icono.create_oval(2, 2, 50, 50, fill=colores["bg"], outline=colores["borde"], width=1)
        icono.create_text(26, 27, text=colores["icono"], fill=colores["fg"], font=("Segoe UI", 19, "bold"))

        etiqueta(
            cuerpo,
            titulo,
            fuente=tema_fuente_encabezado(cuerpo),
            color=tema.TEXTO,
            fondo=tema.FONDO,
            wraplength=ancho - 60,
            justify="left",
        ).pack(anchor="w", pady=(14, 7))
        etiqueta(
            cuerpo,
            mensaje,
            fuente=tema_fuente_cuerpo(cuerpo),
            color=tema.TEXTO_SUAVE,
            fondo=tema.FONDO,
            wraplength=ancho - 60,
            justify="left",
        ).pack(anchor="w")
        if detalle:
            caja = tk.Frame(cuerpo, bg=tema.SUPERFICIE_2, highlightbackground=tema.BORDE, highlightthickness=1)
            caja.pack(fill="x", pady=(13, 0))
            etiqueta(
                caja,
                detalle,
                fuente=tema_fuente_micro(cuerpo),
                color=tema.MUTED,
                fondo=tema.SUPERFICIE_2,
                wraplength=ancho - 90,
                justify="left",
            ).pack(anchor="w", padx=12, pady=10)

        botones = tk.Frame(cuerpo, bg=tema.FONDO)
        botones.pack(fill="x", side="bottom", pady=(20, 0))
        Boton(
            botones,
            texto_aceptar,
            self._aceptar,
            variante="peligro" if estado == "error" and texto_cancelar else "primario",
            ancho=176 if not texto_cancelar else 170,
            fondo=tema.FONDO,
        ).pack(side="right")
        if texto_cancelar:
            Boton(
                botones,
                texto_cancelar,
                self.cerrar,
                variante="secundario",
                ancho=132,
                fondo=tema.FONDO,
            ).pack(side="right", padx=(0, 10))

    def _aceptar(self) -> None:
        self.resultado = True
        self.cerrar()

    @classmethod
    def preguntar(
        cls,
        padre: tk.Misc,
        *,
        titulo: str,
        mensaje: str,
        estado: str = "info",
        texto_aceptar: str = "Entendido",
        texto_cancelar: str | None = "Cancelar",
        detalle: str = "",
    ) -> bool:
        dialogo = cls(
            padre,
            titulo=titulo,
            mensaje=mensaje,
            estado=estado,
            texto_aceptar=texto_aceptar,
            texto_cancelar=texto_cancelar,
            detalle=detalle,
        )
        dialogo.mostrar()
        try:
            padre.wait_window(dialogo)
        except tk.TclError:
            pass
        return bool(dialogo.resultado)

    @classmethod
    def aviso(
        cls,
        padre: tk.Misc,
        *,
        titulo: str,
        mensaje: str,
        estado: str = "info",
        texto_aceptar: str = "Entendido",
        detalle: str = "",
    ) -> None:
        cls.preguntar(
            padre,
            titulo=titulo,
            mensaje=mensaje,
            estado=estado,
            texto_aceptar=texto_aceptar,
            texto_cancelar=None,
            detalle=detalle,
        )


class DialogoAutorizacionCierre(DialogoBase):
    """Solicita nombre y clave de autorización antes de generar los archivos."""

    def __init__(
        self,
        padre: tk.Misc,
        *,
        operador: SesionOperador,
        estadisticas: EstadisticasSesion,
        sesion_id: int,
        al_autorizar: Callable[[str, str], ResultadoAutorizacion],
    ):
        super().__init__(padre, "Autorizar cierre", ancho=650, alto=615)
        self.resultado: ResultadoAutorizacion | None = None
        self._operador = operador
        self._estadisticas = estadisticas
        self._sesion_id = sesion_id
        self._al_autorizar = al_autorizar

        _cabecera_dialogo(
            self.tenedor,
            "Cierre y generación de archivos",
            "Confirma quién responde por esta sesión.",
            icono="AUTORIZACIÓN DE OPERADOR",
        )
        separador(self.tenedor, tema.BORDE, 1).pack(fill="x")
        cuerpo = tk.Frame(self.tenedor, bg=tema.FONDO)
        cuerpo.pack(fill="both", expand=True, padx=28, pady=20)

        resumen = tk.Frame(
            cuerpo,
            bg=tema.SUPERFICIE_2,
            highlightbackground=tema.BORDE,
            highlightthickness=1,
        )
        resumen.pack(fill="x")
        datos = tk.Frame(resumen, bg=tema.SUPERFICIE_2)
        datos.pack(fill="x", padx=16, pady=13)
        for columna, (rotulo, valor) in enumerate(
            [
                ("OPERADOR", operador.nombre),
                ("SESIÓN", f"#{sesion_id}"),
                ("PRODUCTOS", str(estadisticas.registrados)),
                ("INCIDENCIAS", str(estadisticas.duplicados + estadisticas.no_encontrados)),
            ]
        ):
            celda = tk.Frame(datos, bg=tema.SUPERFICIE_2)
            celda.grid(row=0, column=columna, sticky="w", padx=(0, 18))
            etiqueta(
                celda,
                rotulo,
                fuente=tema_fuente_micro(celda),
                color=tema.MUTED,
                fondo=tema.SUPERFICIE_2,
            ).pack(anchor="w")
            etiqueta(
                celda,
                valor,
                fuente=tema_fuente_pequena(celda),
                color=tema.TEXTO,
                fondo=tema.SUPERFICIE_2,
            ).pack(anchor="w")

        etiqueta(
            cuerpo,
            "Nombre del operador responsable",
            fuente=tema_fuente_micro(cuerpo),
            color=tema.MUTED,
            fondo=tema.FONDO,
        ).pack(anchor="w", pady=(18, 6))
        self.campo_nombre = Campo(
            cuerpo,
            "",
            texto_inicial=operador.nombre,
            fondo=tema.FONDO,
            fuente=tema_fuente_cuerpo(cuerpo),
            on_enter=lambda: self.campo_clave.enfocar(),
        )
        self.campo_nombre.pack(fill="x")
        self.campo_nombre.titulo.pack_forget()

        etiqueta(
            cuerpo,
            "Clave de autorización",
            fuente=tema_fuente_micro(cuerpo),
            color=tema.MUTED,
            fondo=tema.FONDO,
        ).pack(anchor="w", pady=(14, 6))
        self.campo_clave = Campo(
            cuerpo,
            "",
            secreto=True,
            ayuda="Usa tu código de acceso vigente. También se acepta la clave de administración.",
            fondo=tema.FONDO,
            fuente=tema_fuente_cuerpo(cuerpo),
            on_enter=self._autorizar,
        )
        self.campo_clave.pack(fill="x")
        self.campo_clave.titulo.pack_forget()

        self.banner = BannerEstado(cuerpo, fondo=tema.FONDO)
        self.banner.pack(fill="x", pady=(14, 0))
        self.banner.mostrar(
            "Los archivos se crearán como copias nuevas",
            "El archivo maestro original no se modifica. La sesión quedará cerrada al finalizar.",
            "info",
        )

        pie = tk.Frame(self.tenedor, bg=tema.FONDO)
        pie.pack(fill="x", side="bottom", padx=28, pady=(0, 22))
        self.boton_autorizar = Boton(
            pie,
            "Generar archivos y finalizar",
            self._autorizar,
            variante="exito",
            icono="✓",
            ancho=270,
            alto=48,
            fondo=tema.FONDO,
        )
        self.boton_autorizar.pack(side="right")
        Boton(
            pie,
            "Cancelar",
            self.cerrar,
            variante="fantasma",
            ancho=116,
            fondo=tema.FONDO,
        ).pack(side="right", padx=(0, 8))
        self.after(120, self.campo_clave.enfocar)

    def _autorizar(self) -> None:
        nombre = self.campo_nombre.get().strip()
        clave = self.campo_clave.get()
        self.campo_nombre.establecer_error(None)
        self.campo_clave.establecer_error(None)
        if not nombre:
            self.campo_nombre.establecer_error("Escribe el nombre del operador.")
            self.banner.mostrar("Falta el nombre", "El nombre es obligatorio para autorizar el cierre.", "error")
            return
        if not clave:
            self.campo_clave.establecer_error("Escribe la clave de autorización.")
            self.campo_clave.enfocar()
            self.banner.mostrar("Falta la clave", "La clave de autorización es obligatoria.", "error")
            return
        self.boton_autorizar.configurar_estado("deshabilitado")
        self.boton_autorizar.configurar_texto("Verificando…")
        self.update_idletasks()
        try:
            resultado = self._al_autorizar(nombre, clave)
        except (ErrorAutenticacion, ErrorValidacion, ErrorAdministracion) as exc:
            self.banner.mostrar("No fue posible autorizar", str(exc), "error")
            self.campo_clave.establecer_error("Revisa la clave e intenta de nuevo.")
            self.campo_clave.set("")
            self.boton_autorizar.configurar_texto("Generar archivos y finalizar", icono="✓")
            self.boton_autorizar.configurar_estado("normal")
            self.campo_clave.enfocar()
            return
        except Exception as exc:
            self.banner.mostrar("Error inesperado", str(exc), "error")
            self.boton_autorizar.configurar_texto("Generar archivos y finalizar", icono="✓")
            self.boton_autorizar.configurar_estado("normal")
            return
        self.resultado = resultado
        self.cerrar()


class DialogoCodigoGenerado(DialogoBase):
    """Muestra una sola vez el código que el administrador debe entregar."""

    def __init__(
        self,
        padre: tk.Misc,
        *,
        codigo: str,
        asignado_a: str,
        expira_en: Any,
        tipo: str,
    ):
        super().__init__(padre, "Código generado", ancho=640, alto=550)
        self.codigo = codigo
        _cabecera_dialogo(
            self.tenedor,
            "Código de acceso emitido",
            "Este es el único momento en que se mostrará.",
            icono="NUEVA CREDENCIAL",
        )
        separador(self.tenedor, tema.BORDE, 1).pack(fill="x")
        cuerpo = tk.Frame(self.tenedor, bg=tema.FONDO)
        cuerpo.pack(fill="both", expand=True, padx=28, pady=22)

        Pildora(cuerpo, "SE MUESTRA UNA SOLA VEZ", "advertencia", fondo=tema.FONDO).pack(anchor="w")
        caja = tk.Frame(
            cuerpo,
            bg=tema.SUPERFICIE_2,
            highlightbackground=tema.CARAMELO,
            highlightthickness=1,
        )
        caja.pack(fill="x", pady=(13, 0))
        etiqueta(
            caja,
            "ENTREGA ESTE CÓDIGO AL OPERADOR",
            fuente=tema_fuente_micro(caja),
            color=tema.CARAMELO,
            fondo=tema.SUPERFICIE_2,
        ).pack(anchor="w", padx=16, pady=(13, 4))
        self._variable = tk.StringVar(value=codigo)
        entrada = tk.Entry(
            caja,
            textvariable=self._variable,
            bg=tema.SUPERFICIE_2,
            fg=tema.CARAMELO_CLARO,
            readonlybackground=tema.SUPERFICIE_2,
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=("Cascadia Mono", 20, "bold"),
            justify="center",
            state="readonly",
        )
        entrada.pack(fill="x", padx=12, pady=(2, 15))

        info = tk.Frame(cuerpo, bg=tema.FONDO)
        info.pack(fill="x", pady=(16, 0))
        info.columnconfigure(1, weight=1)
        filas = [
            ("Asignado a", asignado_a),
            ("Tipo", {"invitacion": "Invitación libre", "asignado": "Invitación asignada", "renovacion": "Renovación de acceso"}.get(tipo, tipo)),
            ("Válido hasta", formatear_fecha_hora(expira_en)),
        ]
        for fila, (rotulo, valor) in enumerate(filas):
            etiqueta(
                info,
                rotulo.upper(),
                fuente=tema_fuente_micro(info),
                color=tema.MUTED,
                fondo=tema.FONDO,
            ).grid(row=fila, column=0, sticky="nw", pady=4)
            etiqueta(
                info,
                valor,
                fuente=tema_fuente_pequena(info),
                color=tema.TEXTO,
                fondo=tema.FONDO,
                wraplength=390,
                justify="left",
            ).grid(row=fila, column=1, sticky="nw", padx=(18, 0), pady=4)

        aviso = tk.Frame(cuerpo, bg=tema.AMBAR_FONDO, highlightbackground="#6B4B0B", highlightthickness=1)
        aviso.pack(fill="x", pady=(16, 0))
        etiqueta(
            aviso,
            "Guárdalo ahora. Por seguridad solo almacenamos su hash y no podremos "
            "mostrarlo de nuevo. Si se pierde, emite otro código.",
            fuente=tema_fuente_micro(aviso),
            color=tema.AMBAR_CLARO,
            fondo=tema.AMBAR_FONDO,
            wraplength=550,
            justify="left",
        ).pack(anchor="w", padx=12, pady=10)

        pie = tk.Frame(self.tenedor, bg=tema.FONDO)
        pie.pack(fill="x", side="bottom", padx=28, pady=(0, 22))
        self._boton_copiar = Boton(
            pie,
            "Copiar código",
            self._copiar,
            variante="caramelo",
            icono="⧉",
            ancho=170,
            fondo=tema.FONDO,
        )
        self._boton_copiar.pack(side="left")
        Boton(
            pie,
            "He guardado el código",
            self.cerrar,
            variante="secundario",
            ancho=190,
            fondo=tema.FONDO,
        ).pack(side="right")

    def _copiar(self) -> None:
        try:
            self.clipboard_clear()
            self.clipboard_append(self.codigo)
            self.update()
            self._boton_copiar.configurar_texto("Copiado al portapapeles", icono="✓")
        except tk.TclError:
            pass


class DialogoCambiarClave(DialogoBase):
    def __init__(
        self,
        padre: tk.Misc,
        *,
        al_cambiar: Callable[[str, str, str], None],
    ):
        super().__init__(padre, "Cambiar clave de administración", ancho=590, alto=620)
        self._al_cambiar = al_cambiar
        self.resultado = False
        _cabecera_dialogo(
            self.tenedor,
            "Cambiar clave de administración",
            "Actualiza la llave que protege el panel.",
            icono="SEGURIDAD",
        )
        separador(self.tenedor, tema.BORDE, 1).pack(fill="x")
        cuerpo = tk.Frame(self.tenedor, bg=tema.FONDO)
        cuerpo.pack(fill="both", expand=True, padx=28, pady=20)
        self.actual = Campo(
            cuerpo,
            "Clave actual",
            secreto=True,
            fondo=tema.FONDO,
            fuente=tema_fuente_cuerpo(cuerpo),
        )
        self.actual.pack(fill="x")
        self.nueva = Campo(
            cuerpo,
            "Clave nueva",
            secreto=True,
            ayuda="Mínimo 10 caracteres, con al menos una letra y un número.",
            fondo=tema.FONDO,
            fuente=tema_fuente_cuerpo(cuerpo),
        )
        self.nueva.pack(fill="x", pady=(12, 0))
        self.confirmacion = Campo(
            cuerpo,
            "Confirmar clave nueva",
            secreto=True,
            fondo=tema.FONDO,
            fuente=tema_fuente_cuerpo(cuerpo),
            on_enter=self._guardar,
        )
        self.confirmacion.pack(fill="x", pady=(12, 0))
        self.banner = BannerEstado(cuerpo, fondo=tema.FONDO)
        self.banner.pack(fill="x", pady=(16, 0))
        self.banner.mostrar(
            "La clave no se puede recuperar",
            "Consérvala en un lugar seguro. No se muestra ni se envía por correo.",
            "info",
        )
        pie = tk.Frame(self.tenedor, bg=tema.FONDO)
        pie.pack(fill="x", side="bottom", padx=28, pady=(0, 22))
        Boton(pie, "Actualizar clave", self._guardar, variante="caramelo", ancho=190, fondo=tema.FONDO).pack(side="right")
        Boton(pie, "Cancelar", self.cerrar, variante="fantasma", ancho=110, fondo=tema.FONDO).pack(side="right", padx=(0, 8))
        self.after(100, self.actual.enfocar)

    def _guardar(self) -> None:
        actual = self.actual.get()
        nueva = self.nueva.get()
        confirmacion = self.confirmacion.get()
        errores = validar_fortaleza_clave(nueva) if nueva else ["La clave nueva no puede estar vacía."]
        if not actual:
            errores = ["Escribe la clave actual."]
        elif nueva != confirmacion:
            errores = ["Las dos claves nuevas no coinciden."]
        if errores:
            self.banner.mostrar("Revisa los datos", " ".join(errores), "error")
            return
        try:
            self._al_cambiar(actual, nueva, confirmacion)
        except Exception as exc:
            self.banner.mostrar("No se pudo cambiar la clave", str(exc), "error")
            return
        self.resultado = True
        self.cerrar()


class DialogoProgreso(tk.Toplevel):
    """Ventana mínima de progreso para el cierre de sesión."""

    def __init__(self, padre: tk.Misc, mensaje: str = "Generando archivos de cierre…"):
        super().__init__(padre)
        self.withdraw()
        self._fuentes_app = getattr(
            padre.winfo_toplevel(), "_fuentes_app", None
        )
        self.title("Dulcesitos Castillo · Procesando")
        self.configure(bg=tema.FONDO)
        self.resizable(False, False)
        self.transient(padre.winfo_toplevel())
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        ancho, alto = 480, 210
        self._ancho = ancho
        self._alto = alto
        cuerpo = tk.Frame(self, bg=tema.FONDO)
        cuerpo.pack(fill="both", expand=True, padx=28, pady=24)
        MarcaCandy(cuerpo, 44, fondo=tema.FONDO).pack(anchor="w")
        etiqueta(
            cuerpo,
            "Procesando cierre",
            fuente=tema_fuente_encabezado(cuerpo),
            color=tema.TEXTO,
            fondo=tema.FONDO,
        ).pack(anchor="w", pady=(12, 4))
        self._mensaje = etiqueta(
            cuerpo,
            mensaje,
            fuente=tema_fuente_pequena(cuerpo),
            color=tema.MUTED,
            fondo=tema.FONDO,
        )
        self._mensaje.pack(anchor="w")
        estilo = ttk.Style(self)
        estilo.configure(
            "Cierre.Horizontal.TProgressbar",
            troughcolor=tema.SUPERFICIE_2,
            background=tema.CARAMELO,
            bordercolor=tema.FONDO,
            lightcolor=tema.CARAMELO,
            darkcolor=tema.CARAMELO,
        )
        self.barra = ttk.Progressbar(
            cuerpo,
            mode="indeterminate",
            style="Cierre.Horizontal.TProgressbar",
            length=420,
        )
        self.barra.pack(fill="x", pady=(18, 0))
        self.barra.start(14)
        self.update_idletasks()
        padre_w = padre.winfo_toplevel()
        x = padre_w.winfo_rootx() + max(0, (padre_w.winfo_width() - ancho) // 2)
        y = padre_w.winfo_rooty() + max(0, (padre_w.winfo_height() - alto) // 2)
        self.geometry(f"{ancho}x{alto}+{x}+{y}")
        self.deiconify()
        self.lift()
        self.grab_set()
        self.update()
        self.after(2500, self._avanzar_mensaje)

    def _avanzar_mensaje(self) -> None:
        try:
            self._mensaje.configure(
                text="Creando Excel, TXT y reporte visual…"
            )
        except tk.TclError:
            pass

    def cerrar(self) -> None:
        try:
            self.barra.stop()
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


class DialogoRegistroManual(DialogoBase):
    """Alta manual cuando el lector no puede leer o no hay coincidencia."""

    def __init__(
        self,
        padre: tk.Misc,
        *,
        servicio,
        sesion: Sesion,
        maestro: ArchivoMaestro,
        operador: SesionOperador,
    ):
        super().__init__(padre, "Registro manual", ancho=680, alto=710)
        self.servicio = servicio
        self.sesion = sesion
        self.maestro = maestro
        self.operador = operador
        self.resultado = None
        _cabecera_dialogo(
            self.tenedor,
            "Registro manual de producto",
            "Para códigos ilegibles, sin coincidencia o cuando el lector no responde.",
            icono="MODO MANUAL · LECTOR EN PAUSA",
        )
        separador(self.tenedor, tema.BORDE, 1).pack(fill="x")
        cuerpo = tk.Frame(self.tenedor, bg=tema.FONDO)
        cuerpo.pack(fill="both", expand=True, padx=26, pady=(14, 8))
        self.banner = BannerEstado(cuerpo, fondo=tema.FONDO)
        self.codigo = Campo(
            cuerpo,
            "Código del producto",
            ayuda="Escríbelo tal como aparece en la etiqueta, aunque el lector no lo detecte.",
            fondo=tema.FONDO,
            fuente=tema_fuente_cuerpo(cuerpo),
        )
        self.codigo.pack(fill="x", pady=(0, 7))
        self.descripcion = Campo(
            cuerpo,
            "Descripción del producto",
            ayuda="Si el código existe en el catálogo, se usará la descripción oficial.",
            fondo=tema.FONDO,
            fuente=tema_fuente_cuerpo(cuerpo),
        )
        self.descripcion.pack(fill="x", pady=(0, 7))
        self.novedad = Campo(
            cuerpo,
            "Novedad o motivo",
            ayuda="Obligatorio. Ej.: etiqueta deteriorada, lector sin respuesta o producto sin match.",
            fondo=tema.FONDO,
            fuente=tema_fuente_cuerpo(cuerpo),
        )
        self.novedad.pack(fill="x", pady=(0, 7))
        self.stock = None
        if maestro.columna_stock:
            self.stock = Campo(
                cuerpo,
                "Stock contado (opcional)",
                ayuda="Déjalo vacío para conservar el stock del catálogo.",
                fondo=tema.FONDO,
                fuente=tema_fuente_cuerpo(cuerpo),
                on_enter=self._guardar,
            )
            self.stock.pack(fill="x", pady=(0, 7))
        aviso = tk.Frame(cuerpo, bg=tema.AZUL_FONDO)
        aviso.pack(fill="x", pady=(2, 0))
        etiqueta(
            aviso,
            "La lectura del lector está pausada mientras este formulario esté abierto. "
            "Al cerrarlo, la estación vuelve a quedar lista para escanear.",
            fuente=tema_fuente_micro(aviso),
            color=tema.AZUL_CLARO,
            fondo=tema.AZUL_FONDO,
            wraplength=560,
            justify="left",
        ).pack(anchor="w", padx=11, pady=8)
        pie = tk.Frame(self.tenedor, bg=tema.FONDO)
        pie.pack(fill="x", side="bottom", padx=26, pady=(8, 18))
        self.boton_guardar = Boton(
            pie,
            "Registrar manual",
            self._guardar,
            variante="primario",
            icono="✓",
            ancho=190,
            alto=43,
            fondo=tema.FONDO,
        )
        self.boton_guardar.pack(side="right")
        Boton(
            pie,
            "Cancelar y volver al lector",
            self.cerrar,
            variante="fantasma",
            ancho=208,
            alto=40,
            fondo=tema.FONDO,
        ).pack(side="right", padx=(0, 8))
        self.after(100, self.codigo.enfocar)

    def _mostrar_error(self, mensaje: str) -> None:
        self.banner.mostrar(
            "No se pudo registrar manualmente", mensaje, "error"
        )
        if not self.banner.winfo_manager():
            self.banner.pack(fill="x", pady=(0, 8), before=self.codigo)

    def _guardar(self) -> None:
        stock = None
        if self.stock is not None:
            texto = self.stock.get().strip()
            if texto:
                stock = convertir_numero(texto)
                if stock is None:
                    self._mostrar_error(
                        "El stock contado debe ser un número válido."
                    )
                    self.stock.enfocar()
                    return
        self.boton_guardar.configurar_estado("deshabilitado")
        self.boton_guardar.configurar_texto("Registrando…")
        self.update_idletasks()
        try:
            registro = self.servicio.registrar_manual(
                sesion=self.sesion,
                maestro=self.maestro,
                operador=self.operador,
                codigo=self.codigo.get(),
                descripcion=self.descripcion.get(),
                novedad=self.novedad.get(),
                stock=stock,
            )
        except ErrorInventario as exc:
            self.boton_guardar.configurar_estado("normal")
            self.boton_guardar.configurar_texto("Registrar manual", icono="✓")
            self._mostrar_error(str(exc))
            return
        except Exception as exc:
            self.boton_guardar.configurar_estado("normal")
            self.boton_guardar.configurar_texto("Registrar manual", icono="✓")
            self._mostrar_error(f"Error inesperado: {exc}")
            return
        self.resultado = registro
        self.cerrar()
