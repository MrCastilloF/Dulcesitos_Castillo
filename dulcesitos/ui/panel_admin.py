"""Panel de administración de accesos, operadores, lector e historial."""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import timedelta
from tkinter import ttk
from typing import Any

from ..modelos import (
    Administrador,
    CodigoAcceso,
    ConfiguracionLector,
    EstadoLector,
)
from ..recursos import configurar_icono
from ..servicios import (
    CodigoEmitido,
    ErrorAdministracion,
    ErrorAutenticacion,
)
from ..utilidades import (
    ErrorValidacion,
    abrir_carpeta,
    ahora_utc,
    desde_iso,
    formatear_fecha_hora,
    truncar,
)
from . import tema
from .componentes import (
    Avatar,
    BannerEstado,
    Boton,
    Campo,
    DialogoBase,
    MarcaCandy,
    SelectorSegmentado,
    TablaDatos,
    Tarjeta,
    TarjetaMetrica,
    cabecera_seccion,
    encabezado_tarjeta,
    etiqueta,
    separador,
)
from .dialogos import (
    DialogoCodigoGenerado,
    DialogoMensaje,
    tema_fuente_cuerpo,
    tema_fuente_cuerpo_fuerte,
    tema_fuente_encabezado,
    tema_fuente_micro,
    tema_fuente_pequena,
    tema_fuente_titulo,
)
from .sonido import Sonidos

LOG = logging.getLogger(__name__)


def _fecha_iso(valor: str | None):
    return desde_iso(valor)


class PanelAdministracion(tk.Toplevel):
    """Ventana modal con autenticación administrativa independiente."""

    def __init__(self, padre: tk.Misc, app):
        super().__init__(padre)
        self.withdraw()
        self._fuentes_app = getattr(app, "_fuentes_app", None)
        self.app = app
        self.admin: Administrador | None = None
        self._seccion_actual = "accesos"
        self._nav: dict[str, Boton] = {}
        self._after_aviso: str | None = None
        self._cerrando = False
        self.sonidos = Sonidos()
        self.title("Dulcesitos Castillo · Administración")
        self.configure(bg=tema.FONDO)
        self.resizable(True, True)
        self.transient(padre.winfo_toplevel())
        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        configurar_icono(self)
        self._calcular_geometria()
        self._construir_login()

    def _calcular_geometria(self) -> None:
        padre = self.app.winfo_toplevel()
        ancho = min(1360, max(1120, int(padre.winfo_width() * 0.95)))
        alto = min(860, max(650, int(padre.winfo_height() * 0.95)))
        x = padre.winfo_rootx() + max(0, (padre.winfo_width() - ancho) // 2)
        y = padre.winfo_rooty() + max(0, (padre.winfo_height() - alto) // 2)
        self.geometry(f"{ancho}x{alto}+{x}+{y}")
        self.minsize(1080, 640)

    def mostrar(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _cerrar(self) -> None:
        if self._cerrando:
            return
        self._cerrando = True
        self.app._cerrar_panel_admin(self)

    def _limpiar(self) -> None:
        for hijo in self.winfo_children():
            hijo.destroy()

    # ------------------------------------------------------------------
    # Autenticación del panel
    # ------------------------------------------------------------------
    def _construir_login(self) -> None:
        self._limpiar()
        self.configure(bg=tema.FONDO)
        self._construir_barra_simple()

        centro = tk.Frame(self, bg=tema.FONDO)
        centro.pack(fill="both", expand=True, padx=26, pady=20)
        centro.grid_rowconfigure(0, weight=1)
        centro.grid_columnconfigure(0, weight=1)
        bloque = tk.Frame(centro, bg=tema.FONDO)
        bloque.grid(row=0, column=0)
        bloque.grid_columnconfigure(0, weight=1, minsize=430)
        bloque.grid_columnconfigure(1, weight=1, minsize=470)
        bloque.grid_rowconfigure(0, weight=1)

        hero = tk.Frame(bloque, bg="#211016")
        hero.grid(row=0, column=0, sticky="nsew")
        contenido_hero = tk.Frame(hero, bg="#211016")
        contenido_hero.pack(fill="both", expand=True, padx=34, pady=30)
        MarcaCandy(contenido_hero, 52, fondo="#211016").pack(anchor="w", pady=(0, 18))
        etiqueta(
            contenido_hero,
            "La llave maestra",
            fuente=tema_fuente_titulo(contenido_hero),
            color=tema.CREMA,
            fondo="#211016",
        ).pack(anchor="w")
        etiqueta(
            contenido_hero,
            "de la operación.",
            fuente=tema_fuente_titulo(contenido_hero),
            color=tema.ROSA,
            fondo="#211016",
        ).pack(anchor="w")
        etiqueta(
            contenido_hero,
            "Desde aquí se crean, asignan, renuevan y revocan los códigos "
            "de los operadores. Cada acción queda registrada localmente.",
            fuente=tema_fuente_pequena(contenido_hero),
            color=tema.TEXTO_SUAVE,
            fondo="#211016",
            wraplength=365,
            justify="left",
        ).pack(anchor="w", pady=(13, 20))
        for texto in (
            "Accesos con vencimiento y revocación inmediata.",
            "Historial de sesiones y archivos generados.",
            "Configuración del lector HID o de puerto serie.",
        ):
            fila = tk.Frame(contenido_hero, bg="#211016")
            fila.pack(fill="x", pady=4)
            etiqueta(
                fila,
                "✓",
                fuente=tema_fuente_cuerpo_fuerte(fila),
                color=tema.VERDE,
                fondo="#211016",
            ).pack(side="left", anchor="n")
            etiqueta(
                fila,
                texto,
                fuente=tema_fuente_micro(fila),
                color=tema.TEXTO_SUAVE,
                fondo="#211016",
                wraplength=340,
                justify="left",
            ).pack(side="left", padx=(8, 0), anchor="w")
        pie_hero = tk.Frame(hero, bg="#211016")
        pie_hero.pack(fill="x", side="bottom", padx=34, pady=(0, 24))
        etiqueta(
            pie_hero,
            "Solo el administrador conoce esta clave.",
            fuente=tema_fuente_micro(pie_hero),
            color=tema.MUTED,
            fondo="#211016",
        ).pack(anchor="w")

        tarjeta = tk.Frame(
            bloque,
            bg=tema.SUPERFICIE,
            highlightbackground=tema.BORDE,
            highlightthickness=1,
        )
        tarjeta.grid(row=0, column=1, sticky="nsew")
        interior = tk.Frame(tarjeta, bg=tema.SUPERFICIE)
        interior.pack(fill="both", expand=True, padx=32, pady=28)
        etiqueta(
            interior,
            "PANEL ADMINISTRATIVO",
            fuente=tema_fuente_micro(interior),
            color=tema.CARAMELO,
            fondo=tema.SUPERFICIE,
        ).pack(anchor="w")
        etiqueta(
            interior,
            "Identifícate",
            fuente=tema_fuente_titulo(interior),
            color=tema.TEXTO,
            fondo=tema.SUPERFICIE,
        ).pack(anchor="w", pady=(3, 3))
        etiqueta(
            interior,
            "Usa la cédula y la clave creadas en el primer arranque.",
            fuente=tema_fuente_pequena(interior),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
            wraplength=400,
            justify="left",
        ).pack(anchor="w", pady=(0, 18))

        self.banner_login = BannerEstado(interior, fondo=tema.SUPERFICIE)
        self._banner_login_visible = False

        self.cedula_admin = Campo(
            interior,
            "Cédula del administrador",
            transformacion=lambda texto: "".join(c for c in texto if c.isdigit())[:12],
            fondo=tema.SUPERFICIE,
            fuente=tema_fuente_cuerpo(interior),
        )
        self.cedula_admin.pack(fill="x")
        self.clave_admin = Campo(
            interior,
            "Clave de administración",
            secreto=True,
            fondo=tema.SUPERFICIE,
            fuente=tema_fuente_cuerpo(interior),
            on_enter=self._autenticar,
        )
        self.clave_admin.pack(fill="x", pady=(11, 0))
        self.boton_login = Boton(
            interior,
            "Entrar al panel",
            self._autenticar,
            variante="caramelo",
            icono="→",
            ancho=230,
            alto=48,
            fondo=tema.SUPERFICIE,
        )
        self.boton_login.pack(fill="x", pady=(18, 0))
        etiqueta(
            interior,
            "La clave no se guarda en texto plano. Se aplica un hash con sal.",
            fuente=tema_fuente_micro(interior),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
            wraplength=390,
            justify="left",
        ).pack(anchor="w", pady=(13, 0))
        self.after(100, self.cedula_admin.enfocar)

    def _mostrar_error_login(self, mensaje: str) -> None:
        self.banner_login.mostrar("Acceso no autorizado", mensaje, "error")
        if not self._banner_login_visible:
            self.banner_login.pack(fill="x", pady=(0, 14), before=self.cedula_admin)
            self._banner_login_visible = True

    def _autenticar(self) -> None:
        cedula = self.cedula_admin.get().strip()
        clave = self.clave_admin.get()
        if not cedula or not clave:
            self._mostrar_error_login("Escribe la cédula y la clave de administración.")
            return
        self.boton_login.configurar_estado("deshabilitado")
        self.boton_login.configurar_texto("Verificando…")
        self.update_idletasks()
        try:
            admin = self.app.auth.autenticar_administrador(cedula, clave)
        except ErrorAutenticacion as exc:
            self.sonidos.error()
            self._mostrar_error_login(str(exc))
            self.clave_admin.set("")
            self.clave_admin.enfocar()
            self.boton_login.configurar_estado("normal")
            self.boton_login.configurar_texto("Entrar al panel", icono="→")
            return
        except Exception as exc:
            self._mostrar_error_login(f"Error inesperado: {exc}")
            self.boton_login.configurar_estado("normal")
            self.boton_login.configurar_texto("Entrar al panel", icono="→")
            return
        self.sonidos.exito()
        self.admin = admin
        self._construir_panel()

    # ------------------------------------------------------------------
    # Estructura del panel autenticado
    # ------------------------------------------------------------------
    def _construir_barra_simple(self) -> None:
        barra = tk.Frame(self, bg=tema.FONDO, height=64)
        barra.pack(fill="x")
        barra.pack_propagate(False)
        interior = tk.Frame(barra, bg=tema.FONDO)
        interior.pack(fill="both", expand=True, padx=22, pady=10)
        MarcaCandy(interior, 36, fondo=tema.FONDO).pack(side="left", padx=(0, 10))
        etiqueta(
            interior,
            "DULCESITOS CASTILLO",
            fuente=tema_fuente_cuerpo_fuerte(interior),
            color=tema.TEXTO,
            fondo=tema.FONDO,
        ).pack(side="left")
        etiqueta(
            interior,
            "· ADMINISTRACIÓN",
            fuente=tema_fuente_micro(interior),
            color=tema.CARAMELO,
            fondo=tema.FONDO,
        ).pack(side="left", padx=(5, 0))
        Boton(
            interior,
            "Cerrar",
            self._cerrar,
            variante="fantasma",
            ancho=88,
            alto=32,
            fuente=tema_fuente_pequena(interior),
            fondo=tema.FONDO,
        ).pack(side="right")
        separador(self, tema.BORDE, 1).pack(fill="x")

    def _construir_panel(self) -> None:
        self._limpiar()
        self.configure(bg=tema.FONDO)
        self._construir_barra_panel()
        cuerpo = tk.Frame(self, bg=tema.FONDO)
        cuerpo.pack(fill="both", expand=True)
        cuerpo.grid_columnconfigure(0, weight=0)
        cuerpo.grid_columnconfigure(1, weight=1)
        cuerpo.grid_rowconfigure(0, weight=1)
        sidebar = tk.Frame(cuerpo, bg=tema.SUPERFICIE, width=226)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        self._construir_sidebar(sidebar)
        principal = tk.Frame(cuerpo, bg=tema.FONDO)
        principal.grid(row=0, column=1, sticky="nsew", padx=22, pady=15)
        principal.grid_rowconfigure(1, weight=1)
        principal.grid_columnconfigure(0, weight=1)
        self.aviso_panel = BannerEstado(principal, fondo=tema.FONDO)
        self._aviso_visible = False
        self.area = tk.Frame(principal, bg=tema.FONDO)
        self.area.grid(row=1, column=0, sticky="nsew")
        self._mostrar_seccion(self._seccion_actual)

    def _construir_barra_panel(self) -> None:
        barra = tk.Frame(self, bg=tema.FONDO, height=62)
        barra.pack(fill="x")
        barra.pack_propagate(False)
        interior = tk.Frame(barra, bg=tema.FONDO)
        interior.pack(fill="both", expand=True, padx=22, pady=9)
        MarcaCandy(interior, 36, fondo=tema.FONDO).pack(side="left", padx=(0, 10))
        etiqueta(
            interior,
            "PANEL DE ADMINISTRACIÓN",
            fuente=tema_fuente_cuerpo_fuerte(interior),
            color=tema.TEXTO,
            fondo=tema.FONDO,
        ).pack(side="left")
        etiqueta(
            interior,
            "CONTROL DE ACCESOS Y OPERACIÓN",
            fuente=tema_fuente_micro(interior),
            color=tema.MUTED,
            fondo=tema.FONDO,
        ).pack(side="left", padx=(12, 0))
        Boton(
            interior,
            "Cerrar panel",
            self._cerrar,
            variante="fantasma",
            ancho=118,
            alto=34,
            fuente=tema_fuente_pequena(interior),
            fondo=tema.FONDO,
        ).pack(side="right")
        if self.admin:
            Avatar(interior, _iniciales(self.admin.nombre), 32, fondo=tema.FONDO).pack(
                side="right", padx=(10, 6)
            )
            etiqueta(
                interior,
                self.admin.nombre,
                fuente=tema_fuente_pequena(interior),
                color=tema.TEXTO_SUAVE,
                fondo=tema.FONDO,
            ).pack(side="right")
        separador(self, tema.BORDE, 1).pack(fill="x")

    def _construir_sidebar(self, sidebar: tk.Frame) -> None:
        if not self.admin:
            return
        contenido = tk.Frame(sidebar, bg=tema.SUPERFICIE)
        contenido.pack(fill="both", expand=True, padx=14, pady=17)
        etiqueta(
            contenido,
            "ADMINISTRADOR",
            fuente=tema_fuente_micro(contenido),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
        ).pack(anchor="w")
        perfil = tk.Frame(contenido, bg=tema.SUPERFICIE)
        perfil.pack(fill="x", pady=(8, 18))
        Avatar(perfil, _iniciales(self.admin.nombre), 48, fondo=tema.SUPERFICIE).pack(
            side="left", padx=(0, 10)
        )
        textos = tk.Frame(perfil, bg=tema.SUPERFICIE)
        textos.pack(side="left", fill="x", expand=True)
        etiqueta(
            textos,
            truncar(self.admin.nombre, 25),
            fuente=tema_fuente_pequena(textos),
            color=tema.TEXTO,
            fondo=tema.SUPERFICIE,
            wraplength=130,
            justify="left",
        ).pack(anchor="w")
        etiqueta(
            textos,
            f"C.C. {self.admin.cedula}",
            fuente=tema_fuente_micro(textos),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
        ).pack(anchor="w")
        separador(contenido, tema.BORDE, 1).pack(fill="x", pady=(0, 14))

        self._nav.clear()
        for clave, icono, texto in [
            ("accesos", "◇", "Accesos"),
            ("operadores", "◎", "Operadores"),
            ("lector", "⌁", "Lector"),
            ("historial", "▤", "Historial"),
        ]:
            boton = Boton(
                contenido,
                f"{icono}   {texto}",
                lambda k=clave: self._mostrar_seccion(k),
                variante="fantasma",
                ancho=192,
                alto=40,
                fuente=tema_fuente_pequena(contenido),
                fondo=tema.SUPERFICIE,
                takefocus=False,
            )
            boton.pack(fill="x", pady=2)
            self._nav[clave] = boton
        self._actualizar_nav()

        pie = tk.Frame(sidebar, bg=tema.SUPERFICIE)
        pie.pack(fill="x", side="bottom", padx=14, pady=16)
        separador(pie, tema.BORDE, 1).pack(fill="x", pady=(0, 10))
        for texto, comando in [
            ("Cambiar mi clave", self._cambiar_clave),
            ("Crear respaldo", self._crear_respaldo),
            ("Bloquear panel", self._bloquear),
        ]:
            Boton(
                pie,
                texto,
                comando,
                variante="fantasma",
                ancho=192,
                alto=32,
                fuente=tema_fuente_micro(pie),
                fondo=tema.SUPERFICIE,
                takefocus=False,
            ).pack(fill="x", pady=1)
        etiqueta(
            pie,
            "v1.0 · datos locales",
            fuente=tema_fuente_micro(pie),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
        ).pack(anchor="w", pady=(10, 0))

    def _actualizar_nav(self) -> None:
        for clave, boton in self._nav.items():
            boton.configurar_variante("secundario" if clave == self._seccion_actual else "fantasma")

    def _mostrar_seccion(self, seccion: str) -> None:
        self._seccion_actual = seccion
        self._actualizar_nav()
        self._limpiar_area()
        try:
            if seccion == "accesos":
                self._seccion_accesos()
            elif seccion == "operadores":
                self._seccion_operadores()
            elif seccion == "lector":
                self._seccion_lector()
            elif seccion == "historial":
                self._seccion_historial()
        except Exception as exc:
            LOG.exception("Error construyendo sección administrativa %s", seccion)
            etiqueta(
                self.area,
                f"No se pudo cargar esta sección: {exc}",
                fuente=tema_fuente_cuerpo(self.area),
                color=tema.ROJO,
                fondo=tema.FONDO,
            ).pack(anchor="w")

    def _limpiar_area(self) -> None:
        for hijo in self.area.winfo_children():
            hijo.destroy()

    def mostrar_aviso_panel(self, mensaje: str, estado: str = "ok") -> None:
        self.aviso_panel.mostrar(
            "Operación completada" if estado == "ok" else "Atención",
            mensaje,
            estado,
        )
        if not self._aviso_visible:
            self.aviso_panel.grid(row=0, column=0, sticky="ew", pady=(0, 12))
            self._aviso_visible = True
        if self._after_aviso:
            try:
                self.after_cancel(self._after_aviso)
            except tk.TclError:
                pass
        self._after_aviso = self.after(6500, self._ocultar_aviso_panel)

    def _ocultar_aviso_panel(self) -> None:
        try:
            if self._aviso_visible:
                self.aviso_panel.grid_remove()
                self._aviso_visible = False
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Sección: accesos
    # ------------------------------------------------------------------
    def _seccion_accesos(self) -> None:
        codigos = self.app.administracion.listar_codigos()
        self._codigos = codigos
        ahora = ahora_utc()
        pendientes = sum(1 for c in codigos if c.estado == "pendiente" and not c.vencido)
        activos = sum(
            1
            for c in codigos
            if c.estado == "activo"
            and c.expira_en is not None
            and c.expira_en > ahora
        )
        vencidos = sum(1 for c in codigos if c.vencido and c.estado != "revocado")
        revocados = sum(1 for c in codigos if c.estado == "revocado")

        header = tk.Frame(self.area, bg=tema.FONDO)
        header.pack(fill="x")
        cabecera_seccion(
            header,
            "Control de acceso",
            "Códigos de operador",
            "Solo el administrador puede emitir, asignar, renovar y revocar.",
        ).pack(side="left", fill="x", expand=True)
        Boton(
            header,
            "Generar código",
            lambda: self._abrir_generador_codigo(),
            variante="caramelo",
            icono="+",
            ancho=170,
            alto=42,
            fondo=tema.FONDO,
        ).pack(side="right", anchor="n", pady=(3, 0))

        metricas = tk.Frame(self.area, bg=tema.FONDO)
        metricas.pack(fill="x", pady=(12, 10))
        for i in range(4):
            metricas.grid_columnconfigure(i, weight=1, uniform="adm_metricas")
        for i, (titulo, valor, color) in enumerate(
            [
                ("Disponibles", pendientes, tema.CARAMELO),
                ("Activos", activos, tema.VERDE),
                ("Vencidos", vencidos, tema.ROJO),
                ("Revocados", revocados, tema.MUTED),
            ]
        ):
            tarjeta = TarjetaMetrica(metricas, titulo, valor, color=color, compacta=True)
            tarjeta.grid(
                row=0,
                column=i,
                sticky="ew",
                padx=(0 if i == 0 else 5, 0 if i == 3 else 5),
            )

        tarjeta = Tarjeta(self.area, padding=13)
        tarjeta.pack(fill="both", expand=True)
        contenido = tarjeta.contenido
        encabezado_tarjeta(
            contenido,
            "Credenciales emitidas",
            "Las pistas muestran solo los últimos cuatro caracteres. El código completo no es recuperable.",
            fondo=tema.SUPERFICIE,
        ).pack(fill="x", pady=(0, 8))

        self.tabla_accesos = TablaDatos(
            contenido,
            [
                ("pista", "Código", 106, "w"),
                ("asignado", "Asignado a", 238, "w"),
                ("cedula", "Cédula", 104, "w"),
                ("estado", "Estado", 96, "center"),
                ("expira", "Vence", 145, "w"),
                ("uso", "Último uso", 145, "w"),
            ],
            alto=7,
            fondo=tema.SUPERFICIE,
            mensaje_vacio="Aún no se han emitido códigos.\nGenera el primero para un operador.",
            al_seleccionar=self._seleccionar_acceso,
        )
        self.tabla_accesos.pack(fill="both", expand=True)
        self.tabla_accesos.aplicar_etiquetas(
            {
                "activo": {"foreground": tema.VERDE},
                "pendiente": {"foreground": tema.CARAMELO},
                "vencido": {"foreground": tema.ROJO},
                "revocado": {"foreground": tema.MUTED},
            }
        )
        filas = []
        self._codigos_por_id: dict[int, CodigoAcceso] = {}
        for codigo in codigos:
            if codigo.estado == "revocado":
                tag = "revocado"
            elif codigo.vencido:
                tag = "vencido"
            elif codigo.estado == "activo":
                tag = "activo"
            else:
                tag = "pendiente"
            asignado = (
                codigo.operador_nombre
                or codigo.nombre_asignado
                or "Invitación libre"
            )
            self._codigos_por_id[codigo.id] = codigo
            filas.append(
                {
                    "_id": codigo.id,
                    "pista": codigo.pista,
                    "asignado": truncar(asignado, 32),
                    "cedula": codigo.cedula_asignada or "—",
                    "estado": codigo.estado_visible,
                    "expira": formatear_fecha_hora(codigo.expira_en),
                    "uso": formatear_fecha_hora(codigo.ultimo_uso_en),
                    "_tags": (tag,),
                }
            )
        self._codigos_filas = filas
        self.tabla_accesos.cargar(filas)

        acciones = tk.Frame(contenido, bg=tema.SUPERFICIE)
        acciones.pack(fill="x", pady=(10, 0))
        self.boton_revocar_codigo = Boton(
            acciones,
            "Revocar seleccionado",
            self._revocar_codigo,
            variante="peligro",
            ancho=188,
            alto=36,
            fuente=tema_fuente_pequena(acciones),
            fondo=tema.SUPERFICIE,
        )
        self.boton_revocar_codigo.pack(side="left")
        self.boton_revocar_codigo.configurar_estado("deshabilitado")
        etiqueta(
            acciones,
            "Una renovación revoca automáticamente los accesos anteriores del operador.",
            fuente=tema_fuente_micro(acciones),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
            wraplength=520,
            justify="left",
        ).pack(side="left", padx=(12, 0))
        Boton(
            acciones,
            "Actualizar",
            lambda: self._mostrar_seccion("accesos"),
            variante="fantasma",
            ancho=100,
            alto=34,
            fuente=tema_fuente_pequena(acciones),
            fondo=tema.SUPERFICIE,
            takefocus=False,
        ).pack(side="right")

    def _seleccionar_acceso(self, fila: Any) -> None:
        if not hasattr(self, "boton_revocar_codigo"):
            return
        codigo_id = fila.get("_id") if fila else None
        codigo = self._codigos_por_id.get(codigo_id) if codigo_id else None
        habilitado = bool(codigo and codigo.estado != "revocado")
        self.boton_revocar_codigo.configurar_estado("normal" if habilitado else "deshabilitado")

    def _revocar_codigo(self) -> None:
        if not getattr(self, "tabla_accesos", None) or not self.admin:
            return
        fila = self.tabla_accesos.seleccion()
        if not fila:
            return
        codigo = self._codigos_por_id.get(fila.get("_id"))
        if not codigo:
            return
        if codigo.estado == "revocado":
            self.mostrar_aviso_panel("Ese código ya estaba revocado.", "advertencia")
            return
        if not DialogoMensaje.preguntar(
            self,
            titulo="Revocar código de acceso",
            mensaje=(
                f"El código {codigo.pista} dejará de servir de inmediato. "
                "El operador no podrá iniciar sesión con él. ¿Deseas revocarlo?"
            ),
            estado="advertencia",
            texto_aceptar="Revocar acceso",
            texto_cancelar="Conservar",
        ):
            return
        try:
            self.app.administracion.revocar_codigo(self.admin, codigo.id)
        except ErrorAdministracion as exc:
            DialogoMensaje.aviso(self, titulo="No se pudo revocar", mensaje=str(exc), estado="error")
            return
        self.sonidos.advertencia()
        self._mostrar_seccion("accesos")
        self.mostrar_aviso_panel("Código revocado correctamente.", "ok")

    def _abrir_generador_codigo(self, operador_id: int | None = None) -> None:
        if not self.admin:
            return
        dialogo = DialogoGenerarCodigo(
            self,
            app=self.app,
            admin=self.admin,
            operador_preseleccionado=operador_id,
        )
        dialogo.mostrar()
        self.wait_window(dialogo)
        emitido = dialogo.resultado
        if not emitido:
            return
        self._seccion_actual = "accesos"
        self._construir_panel_refresh()
        DialogoCodigoGenerado(
            self,
            codigo=emitido.codigo,
            asignado_a=emitido.asignado_a,
            expira_en=emitido.expira_en,
            tipo=emitido.tipo,
        ).mostrar()
        self._mostrar_seccion("accesos")
        self.mostrar_aviso_panel(
            "Código emitido. Compártelo ahora: no se puede volver a mostrar.",
            "advertencia",
        )

    def _construir_panel_refresh(self) -> None:
        # Reconstruye la estructura preservando la sesión autenticada.
        self._limpiar()
        self._construir_barra_panel()
        cuerpo = tk.Frame(self, bg=tema.FONDO)
        cuerpo.pack(fill="both", expand=True)
        cuerpo.grid_columnconfigure(1, weight=1)
        cuerpo.grid_rowconfigure(0, weight=1)
        sidebar = tk.Frame(cuerpo, bg=tema.SUPERFICIE, width=226)
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        self._construir_sidebar(sidebar)
        principal = tk.Frame(cuerpo, bg=tema.FONDO)
        principal.grid(row=0, column=1, sticky="nsew", padx=22, pady=15)
        principal.grid_rowconfigure(1, weight=1)
        principal.grid_columnconfigure(0, weight=1)
        self.aviso_panel = BannerEstado(principal, fondo=tema.FONDO)
        self._aviso_visible = False
        self.area = tk.Frame(principal, bg=tema.FONDO)
        self.area.grid(row=1, column=0, sticky="nsew")

    # ------------------------------------------------------------------
    # Sección: operadores
    # ------------------------------------------------------------------
    def _seccion_operadores(self) -> None:
        operadores = self.app.administracion.listar_operadores()
        self._operadores = operadores
        header = tk.Frame(self.area, bg=tema.FONDO)
        header.pack(fill="x")
        cabecera_seccion(
            header,
            "Personas autorizadas",
            "Operadores",
            "Renueva un acceso o revócalo cuando sea necesario.",
        ).pack(side="left", fill="x", expand=True)
        Boton(
            header,
            "Nuevo acceso",
            lambda: self._abrir_generador_codigo(),
            variante="caramelo",
            icono="+",
            ancho=156,
            alto=42,
            fondo=tema.FONDO,
        ).pack(side="right", anchor="n", pady=(3, 0))

        tarjeta = Tarjeta(self.area, padding=13)
        tarjeta.pack(fill="both", expand=True, pady=(12, 0))
        contenido = tarjeta.contenido
        encabezado_tarjeta(
            contenido,
            "Directorio de operadores",
            f"{len(operadores)} operador(es) registrados en este equipo.",
            fondo=tema.SUPERFICIE,
        ).pack(fill="x", pady=(0, 8))
        self.tabla_operadores = TablaDatos(
            contenido,
            [
                ("nombre", "Nombre", 215, "w"),
                ("cedula", "Cédula", 110, "w"),
                ("correo", "Correo", 230, "w"),
                ("acceso", "Acceso", 95, "center"),
                ("vence", "Vence", 142, "w"),
                ("sesiones", "Sesiones", 78, "center"),
                ("registros", "Registros", 82, "center"),
            ],
            alto=7,
            fondo=tema.SUPERFICIE,
            mensaje_vacio="No hay operadores registrados.\nEmite una invitación desde «Accesos».",
            al_seleccionar=self._seleccionar_operador,
        )
        self.tabla_operadores.pack(fill="both", expand=True)
        self.tabla_operadores.aplicar_etiquetas(
            {
                "activo": {"foreground": tema.VERDE},
                "sin": {"foreground": tema.MUTED},
                "vencido": {"foreground": tema.ROJO},
            }
        )
        filas = []
        self._operadores_por_id = {int(o["id"]): o for o in operadores}
        ahora = ahora_utc()
        for operador in operadores:
            expira = _fecha_iso(operador.get("acceso_expira_en"))
            if operador.get("acceso_id") and expira and expira > ahora:
                acceso = "Activo"
                tag = "activo"
            elif expira:
                acceso = "Vencido"
                tag = "vencido"
            else:
                acceso = "Sin acceso"
                tag = "sin"
            filas.append(
                {
                    "_id": int(operador["id"]),
                    "nombre": truncar(operador["nombre"], 32),
                    "cedula": operador["cedula"],
                    "correo": truncar(operador["correo"], 36),
                    "acceso": acceso,
                    "vence": formatear_fecha_hora(expira),
                    "sesiones": operador.get("total_sesiones", 0),
                    "registros": operador.get("total_registros", 0),
                    "_tags": (tag,),
                }
            )
        self.tabla_operadores.cargar(filas)

        acciones = tk.Frame(contenido, bg=tema.SUPERFICIE)
        acciones.pack(fill="x", pady=(10, 0))
        self.boton_renovar_operador = Boton(
            acciones,
            "Renovar acceso",
            self._renovar_operador,
            variante="caramelo",
            ancho=160,
            alto=36,
            fuente=tema_fuente_pequena(acciones),
            fondo=tema.SUPERFICIE,
        )
        self.boton_renovar_operador.pack(side="left")
        self.boton_renovar_operador.configurar_estado("deshabilitado")
        self.boton_revocar_operador = Boton(
            acciones,
            "Revocar acceso",
            self._revocar_operador,
            variante="peligro",
            ancho=154,
            alto=36,
            fuente=tema_fuente_pequena(acciones),
            fondo=tema.SUPERFICIE,
        )
        self.boton_revocar_operador.pack(side="left", padx=(8, 0))
        self.boton_revocar_operador.configurar_estado("deshabilitado")
        Boton(
            acciones,
            "Actualizar",
            lambda: self._mostrar_seccion("operadores"),
            variante="fantasma",
            ancho=100,
            alto=34,
            fuente=tema_fuente_pequena(acciones),
            fondo=tema.SUPERFICIE,
            takefocus=False,
        ).pack(side="right")
        etiqueta(
            contenido,
            "El historial de sesiones y registros se conserva aunque se revoque el acceso.",
            fuente=tema_fuente_micro(contenido),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
        ).pack(anchor="w", pady=(9, 0))

    def _seleccionar_operador(self, fila: Any) -> None:
        habilitado = bool(fila)
        for boton in (
            getattr(self, "boton_renovar_operador", None),
            getattr(self, "boton_revocar_operador", None),
        ):
            if boton is not None:
                boton.configurar_estado("normal" if habilitado else "deshabilitado")

    def _renovar_operador(self) -> None:
        if not hasattr(self, "tabla_operadores"):
            return
        fila = self.tabla_operadores.seleccion()
        if not fila:
            return
        self._abrir_generador_codigo(int(fila["_id"]))

    def _revocar_operador(self) -> None:
        if not self.admin or not hasattr(self, "tabla_operadores"):
            return
        fila = self.tabla_operadores.seleccion()
        if not fila:
            return
        operador = self._operadores_por_id.get(int(fila["_id"]))
        if not operador:
            return
        if not DialogoMensaje.preguntar(
            self,
            titulo="Revocar acceso del operador",
            mensaje=(
                f"Se revocarán todos los códigos activos de {operador['nombre']}. "
                "Sus sesiones y registros guardados se conservarán. ¿Continuar?"
            ),
            estado="advertencia",
            texto_aceptar="Revocar acceso",
            texto_cancelar="Cancelar",
        ):
            return
        try:
            cantidad = self.app.administracion.revocar_operador(
                self.admin, int(operador["id"])
            )
        except ErrorAdministracion as exc:
            DialogoMensaje.aviso(self, titulo="No se pudo revocar", mensaje=str(exc), estado="error")
            return
        self.sonidos.advertencia()
        self._mostrar_seccion("operadores")
        self.mostrar_aviso_panel(
            f"Acceso revocado. Códigos inhabilitados: {cantidad}.", "ok"
        )

    # ------------------------------------------------------------------
    # Sección: lector
    # ------------------------------------------------------------------
    def _seccion_lector(self) -> None:
        estado = self.app.estado_lector
        header = tk.Frame(self.area, bg=tema.FONDO)
        header.pack(fill="x")
        cabecera_seccion(
            header,
            "Hardware de captura",
            "Lector y calibración",
            "Configura cómo se conecta el lector. Cambiar de modo invalida la calibración.",
        ).pack(side="left", fill="x", expand=True)
        Boton(
            header,
            "Redetectar",
            self.app.lector.solicitar_redeteccion,
            variante="secundario",
            ancho=126,
            alto=38,
            fuente=tema_fuente_pequena(header),
            fondo=tema.FONDO,
            takefocus=False,
        ).pack(side="right", anchor="n", pady=(3, 0))

        dos = tk.Frame(self.area, bg=tema.FONDO)
        dos.pack(fill="x", pady=(12, 0))
        dos.grid_columnconfigure(0, weight=1, uniform="lector_adm")
        dos.grid_columnconfigure(1, weight=1, uniform="lector_adm")

        self.tarjeta_estado_lector = Tarjeta(dos, padding=18, acento=tema.CARAMELO)
        self.tarjeta_estado_lector.grid(row=0, column=0, sticky="nsew", padx=(0, 7))
        contenido_estado = self.tarjeta_estado_lector.contenido
        cabecera_estado = encabezado_tarjeta(
            contenido_estado,
            "Estado actual",
            "Actualización en tiempo real del monitor.",
            fondo=tema.SUPERFICIE,
            derecha_texto=estado.etiqueta,
            derecha_estado=self._estado_visual(estado),
        )
        cabecera_estado.pack(fill="x")
        self.pildora_lector_admin = cabecera_estado.pildora_derecha
        self.lbl_lector_admin_detalle = etiqueta(
            contenido_estado,
            estado.detalle,
            fuente=tema_fuente_pequena(contenido_estado),
            color=tema.TEXTO_SUAVE,
            fondo=tema.SUPERFICIE,
            wraplength=440,
            justify="left",
        )
        self.lbl_lector_admin_detalle.pack(anchor="w", pady=(13, 0))
        dispositivos = ", ".join(estado.dispositivos) if estado.dispositivos else (
            "No se detectó un modelo de lector por nombre."
        )
        etiqueta(
            contenido_estado,
            f"Detectado: {dispositivos}",
            fuente=tema_fuente_micro(contenido_estado),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
            wraplength=440,
            justify="left",
        ).pack(anchor="w", pady=(7, 0))
        etiqueta(
            contenido_estado,
            "Un lector HID genérico se valida con la prueba de calibración del operador.",
            fuente=tema_fuente_micro(contenido_estado),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
            wraplength=440,
            justify="left",
        ).pack(anchor="w", pady=(12, 0))
        Boton(
            contenido_estado,
            "Actualizar estado",
            self._refrescar_estado_lector_admin,
            variante="fantasma",
            ancho=140,
            alto=32,
            fuente=tema_fuente_pequena(contenido_estado),
            fondo=tema.SUPERFICIE,
            takefocus=False,
        ).pack(anchor="w", pady=(13, 0))

        tarjeta_config = Tarjeta(dos, padding=18)
        tarjeta_config.grid(row=0, column=1, sticky="nsew", padx=(7, 0))
        contenido = tarjeta_config.contenido
        encabezado_tarjeta(
            contenido,
            "Modo de conexión",
            "HID funciona sin instalar controladores. Serie requiere un puerto COM.",
            fondo=tema.SUPERFICIE,
        ).pack(fill="x")
        config = self.app.config_lector
        self.selector_modo = SelectorSegmentado(
            contenido,
            [("HID", "USB HID"), ("SERIAL", "Puerto serie")],
            self._cambiar_modo_lector,
            ancho=420,
            alto=40,
            fondo=tema.SUPERFICIE,
            seleccionado=config.modo,
        )
        self.selector_modo.pack(fill="x", pady=(13, 12))

        fila_puerto = tk.Frame(contenido, bg=tema.SUPERFICIE)
        fila_puerto.pack(fill="x", pady=(0, 10))
        etiqueta(
            fila_puerto,
            "PUERTO COM",
            fuente=tema_fuente_micro(fila_puerto),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
        ).pack(anchor="w", pady=(0, 5))
        puertos = self.app.puertos_disponibles()
        self.puerto_var = tk.StringVar(value=config.puerto)
        self.combo_puerto = ttk.Combobox(
            fila_puerto,
            textvariable=self.puerto_var,
            values=[p[0] for p in puertos],
            state="normal" if config.modo == "SERIAL" else "disabled",
        )
        self.combo_puerto.pack(fill="x")
        self.lbl_puertos = etiqueta(
            fila_puerto,
            " · ".join(descripcion for _, descripcion in puertos)
            or "No se detectaron puertos COM en este equipo.",
            fuente=tema_fuente_micro(fila_puerto),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
            wraplength=440,
            justify="left",
        )
        self.lbl_puertos.pack(anchor="w", pady=(4, 0))

        fila_baudios = tk.Frame(contenido, bg=tema.SUPERFICIE)
        fila_baudios.pack(fill="x", pady=(2, 0))
        etiqueta(
            fila_baudios,
            "VELOCIDAD",
            fuente=tema_fuente_micro(fila_baudios),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
        ).pack(side="left")
        self.baudios_var = tk.StringVar(value=str(config.baudios))
        self.combo_baudios = ttk.Combobox(
            fila_baudios,
            textvariable=self.baudios_var,
            values=["9600", "19200", "38400", "57600", "115200"],
            width=10,
            state="readonly" if config.modo == "SERIAL" else "disabled",
        )
        self.combo_baudios.pack(side="right")
        Boton(
            contenido,
            "Guardar configuración",
            self._guardar_config_lector,
            variante="caramelo",
            ancho=230,
            alto=42,
            fondo=tema.SUPERFICIE,
        ).pack(fill="x", pady=(16, 0))
        etiqueta(
            contenido,
            "Al guardar se invalida la calibración y se reinicia el monitor del lector.",
            fuente=tema_fuente_micro(contenido),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
            wraplength=440,
            justify="left",
        ).pack(anchor="w", pady=(9, 0))
        self._cambiar_modo_lector(config.modo, inicial=True)

    def _estado_visual(self, estado: EstadoLector) -> str:
        return {
            "activo": "ok",
            "conectado": "info",
            "pendiente": "advertencia",
            "desconectado": "error",
        }.get(estado.estado, "advertencia")

    def _cambiar_modo_lector(self, modo: str, *, inicial: bool = False) -> None:
        if not hasattr(self, "combo_puerto"):
            return
        if modo == "SERIAL":
            self.combo_puerto.configure(state="normal")
            self.combo_baudios.configure(state="readonly")
        else:
            self.combo_puerto.configure(state="disabled")
            self.combo_baudios.configure(state="disabled")

    def _guardar_config_lector(self) -> None:
        modo = self.selector_modo.seleccion
        puerto = self.puerto_var.get().strip().upper()
        try:
            baudios = int(self.baudios_var.get())
        except ValueError:
            baudios = 9600
        if modo == "SERIAL" and not puerto:
            self.mostrar_aviso_panel(
                "Selecciona un puerto COM o escribe uno manualmente.", "error"
            )
            return
        if self.app.operador is not None and self.app.inventario.sesion_abierta(
            self.app.operador.operador_id
        ):
            if not DialogoMensaje.preguntar(
                self,
                titulo="Cambiar configuración del lector",
                mensaje=(
                    "Hay una sesión de inventario abierta. El cambio reiniciará el "
                    "lector y exigirá calibrar de nuevo para continuar. Los registros "
                    "están guardados. ¿Deseas aplicar el cambio?"
                ),
                estado="advertencia",
                texto_aceptar="Aplicar cambio",
                texto_cancelar="Cancelar",
            ):
                return
        config = ConfiguracionLector(modo=modo, puerto=puerto if modo == "SERIAL" else "", baudios=baudios)
        self.app.aplicar_configuracion_lector(config)
        self._seccion_lector()
        self.mostrar_aviso_panel(
            "Configuración del lector guardada. Realiza una nueva calibración.", "ok"
        )

    def _refrescar_estado_lector_admin(self) -> None:
        self.app.lector.solicitar_redeteccion()
        self.update_idletasks()
        self.after(700, self._actualizar_estado_lector_admin_pintar)

    def _actualizar_estado_lector_admin_pintar(self) -> None:
        estado = self.app.estado_lector
        if hasattr(self, "pildora_lector_admin") and self.pildora_lector_admin.winfo_exists():
            self.pildora_lector_admin.actualizar(estado.etiqueta, self._estado_visual(estado))
            self.lbl_lector_admin_detalle.configure(text=estado.detalle)

    def actualizar_estado_lector(self, estado: EstadoLector) -> None:
        if self._seccion_actual != "lector":
            return
        self._actualizar_estado_lector_admin_pintar()

    # ------------------------------------------------------------------
    # Sección: historial
    # ------------------------------------------------------------------
    def _seccion_historial(self) -> None:
        sesiones = self.app.db.listar_sesiones()
        self._sesiones = sesiones
        header = tk.Frame(self.area, bg=tema.FONDO)
        header.pack(fill="x")
        cabecera_seccion(
            header,
            "Auditoría local",
            "Historial de sesiones",
            "Registros guardados, archivos generados y estado de cada proceso.",
        ).pack(side="left", fill="x", expand=True)
        Boton(
            header,
            "Abrir carpeta de salidas",
            lambda: self._abrir_carpeta(self.app.rutas.salidas),
            variante="secundario",
            ancho=200,
            alto=38,
            fuente=tema_fuente_pequena(header),
            fondo=tema.FONDO,
            takefocus=False,
        ).pack(side="right", anchor="n", pady=(3, 0))

        metricas = tk.Frame(self.area, bg=tema.FONDO)
        metricas.pack(fill="x", pady=(12, 10))
        for i in range(3):
            metricas.grid_columnconfigure(i, weight=1, uniform="hist_metricas")
        total_registros = sum(s.get("total_registrados", 0) for s in sesiones)
        abiertas = sum(1 for s in sesiones if s.get("estado") == "abierta")
        for i, (titulo, valor, color) in enumerate(
            [
                ("Sesiones", len(sesiones), tema.AZUL),
                ("Productos registrados", total_registros, tema.VERDE),
                ("Sesiones abiertas", abiertas, tema.CARAMELO),
            ]
        ):
            tarjeta = TarjetaMetrica(metricas, titulo, valor, color=color, compacta=True)
            tarjeta.grid(
                row=0,
                column=i,
                sticky="ew",
                padx=(0 if i == 0 else 5, 0 if i == 2 else 5),
            )

        tarjeta = Tarjeta(self.area, padding=13)
        tarjeta.pack(fill="both", expand=True)
        contenido = tarjeta.contenido
        encabezado_tarjeta(
            contenido,
            "Sesiones de inventario",
            "Doble clic para abrir la carpeta de los archivos de una sesión finalizada.",
            fondo=tema.SUPERFICIE,
        ).pack(fill="x", pady=(0, 8))
        self.tabla_historial = TablaDatos(
            contenido,
            [
                ("sesion", "Sesión", 64, "center"),
                ("operador", "Operador", 190, "w"),
                ("inicio", "Inicio", 145, "w"),
                ("estado", "Estado", 96, "center"),
                ("registrados", "Registrados", 90, "center"),
                ("incidencias", "Incidencias", 86, "center"),
                ("archivos", "Archivos", 72, "center"),
            ],
            alto=7,
            fondo=tema.SUPERFICIE,
            mensaje_vacio="Aún no hay sesiones de inventario.",
            al_doble_clic=self._abrir_salidas_sesion,
        )
        self.tabla_historial.pack(fill="both", expand=True)
        self.tabla_historial.aplicar_etiquetas(
            {
                "abierta": {"foreground": tema.CARAMELO},
                "finalizada": {"foreground": tema.VERDE},
            }
        )
        filas = []
        self._sesiones_por_id = {int(s["id"]): s for s in sesiones}
        for sesion in sesiones:
            estado = str(sesion.get("estado", ""))
            filas.append(
                {
                    "_id": int(sesion["id"]),
                    "sesion": f"#{sesion['id']}",
                    "operador": truncar(sesion["operador_nombre"], 32),
                    "inicio": formatear_fecha_hora(_fecha_iso(sesion["inicio_en"])),
                    "estado": "Abierta" if estado == "abierta" else "Finalizada",
                    "registrados": sesion.get("total_registrados", 0),
                    "incidencias": int(sesion.get("total_duplicados", 0))
                    + int(sesion.get("total_no_encontrados", 0)),
                    "archivos": sesion.get("total_archivos", 0),
                    "_tags": (estado,),
                }
            )
        self.tabla_historial.cargar(filas)

        acciones = tk.Frame(contenido, bg=tema.SUPERFICIE)
        acciones.pack(fill="x", pady=(10, 0))
        Boton(
            acciones,
            "Abrir archivos de la sesión",
            lambda: self._abrir_salidas_sesion(self.tabla_historial.seleccion()),
            variante="secundario",
            ancho=220,
            alto=36,
            fuente=tema_fuente_pequena(acciones),
            fondo=tema.SUPERFICIE,
        ).pack(side="left")
        Boton(
            acciones,
            "Actualizar",
            lambda: self._mostrar_seccion("historial"),
            variante="fantasma",
            ancho=100,
            alto=34,
            fuente=tema_fuente_pequena(acciones),
            fondo=tema.SUPERFICIE,
            takefocus=False,
        ).pack(side="right")
        etiqueta(
            acciones,
            "Los archivos de una sesión finalizada permanecen en la carpeta de salidas.",
            fuente=tema_fuente_micro(acciones),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
            wraplength=500,
            justify="left",
        ).pack(side="left", padx=(12, 0))

    def _abrir_salidas_sesion(self, fila: Any) -> None:
        if not fila:
            return
        sesion_id = int(fila["_id"])
        archivos = self.app.db.listar_exportaciones(sesion_id)
        if not archivos:
            self.mostrar_aviso_panel(
                "Esa sesión no tiene archivos exportados. Puede estar abierta o sin cierre.",
                "advertencia",
            )
            return
        carpeta = archivos[0].ruta.parent
        self._abrir_carpeta(carpeta)

    # ------------------------------------------------------------------
    # Acciones de seguridad
    # ------------------------------------------------------------------
    def _cambiar_clave(self) -> None:
        if not self.admin:
            return
        from .dialogos import DialogoCambiarClave

        dialogo = DialogoCambiarClave(
            self,
            al_cambiar=lambda actual, nueva, confirmacion: self.app.auth.cambiar_clave_administrador(
                self.admin.id, actual, nueva, confirmacion
            ),
        )
        dialogo.mostrar()
        self.wait_window(dialogo)
        if dialogo.resultado:
            self.sonidos.exito()
            DialogoMensaje.aviso(
                self,
                titulo="Clave actualizada",
                mensaje="La nueva clave de administración quedó guardada.",
                estado="ok",
            )

    def _crear_respaldo(self) -> None:
        try:
            ruta = self.app.administracion.crear_respaldo(self.app.rutas.respaldos)
        except Exception as exc:
            DialogoMensaje.aviso(
                self,
                titulo="No se pudo crear el respaldo",
                mensaje=str(exc),
                estado="error",
            )
            return
        self.sonidos.exito()
        DialogoMensaje.aviso(
            self,
            titulo="Respaldo creado",
            mensaje="Se guardó una copia de la base de datos local.",
            estado="ok",
            detalle=str(ruta),
        )

    def _bloquear(self) -> None:
        self.admin = None
        self._construir_login()

    def _abrir_carpeta(self, ruta) -> None:
        if not abrir_carpeta(ruta):
            DialogoMensaje.aviso(
                self,
                titulo="No se pudo abrir la carpeta",
                mensaje=f"Windows no pudo abrir:\n{ruta}",
                estado="error",
            )


# ---------------------------------------------------------------------------
# Generador de códigos
# ---------------------------------------------------------------------------
class DialogoGenerarCodigo(DialogoBase):
    MODOS = [
        ("libre", "Invitación libre"),
        ("asignado", "Invitación asignada"),
        ("renovacion", "Renovar operador"),
    ]

    def __init__(
        self,
        padre: tk.Misc,
        *,
        app,
        admin: Administrador,
        operador_preseleccionado: int | None = None,
    ):
        super().__init__(padre, "Generar código de acceso", ancho=680, alto=620)
        self.app = app
        self.admin = admin
        self.operador_preseleccionado = operador_preseleccionado
        self.resultado: CodigoEmitido | None = None
        self._operadores = app.administracion.listar_operadores()
        self._mapa_operadores: dict[str, dict[str, Any]] = {}
        for operador in self._operadores:
            etiqueta_operador = f"{operador['nombre']} · {operador['cedula']}"
            self._mapa_operadores[etiqueta_operador] = operador

        self._modo = "renovacion" if operador_preseleccionado else "libre"
        self._construir()
        self._cambiar_modo(self._modo, inicial=True)

    def _construir(self) -> None:
        _cabecera(
            self.tenedor,
            "Emitir un código de acceso",
            "Define a quién pertenece y cuánto tiempo estará vigente.",
            "NUEVA CREDENCIAL",
        )
        separador(self.tenedor, tema.BORDE, 1).pack(fill="x")
        cuerpo = tk.Frame(self.tenedor, bg=tema.FONDO)
        cuerpo.pack(fill="both", expand=True, padx=26, pady=17)

        self.selector = SelectorSegmentado(
            cuerpo,
            self.MODOS,
            self._cambiar_modo,
            ancho=600,
            alto=42,
            fondo=tema.FONDO,
            seleccionado=self._modo,
        )
        self.selector.pack(fill="x")
        self.descripcion_modo = etiqueta(
            cuerpo,
            "",
            fuente=tema_fuente_pequena(cuerpo),
            color=tema.MUTED,
            fondo=tema.FONDO,
            wraplength=610,
            justify="left",
        )
        self.descripcion_modo.pack(anchor="w", pady=(8, 10))

        self.banner = BannerEstado(cuerpo, fondo=tema.FONDO)
        self._banner_visible = False

        self.formulario = tk.Frame(cuerpo, bg=tema.FONDO)
        self.formulario.pack(fill="x")
        self.formulario.grid_columnconfigure(0, weight=1, uniform="gen")
        self.formulario.grid_columnconfigure(1, weight=1, uniform="gen")

        self.form_libre = tk.Frame(self.formulario, bg=tema.FONDO)
        etiqueta(
            self.form_libre,
            "El operador recibirá el código y completará sus datos al activarlo.",
            fuente=tema_fuente_micro(self.form_libre),
            color=tema.TEXTO_SUAVE,
            fondo=tema.FONDO,
            wraplength=580,
            justify="left",
        ).pack(anchor="w", pady=(0, 6))

        self.form_asignado = tk.Frame(self.formulario, bg=tema.FONDO)
        for col in range(2):
            self.form_asignado.grid_columnconfigure(col, weight=1, uniform="gen")
        self.asig_nombre = Campo(
            self.form_asignado,
            "Nombre completo",
            fondo=tema.FONDO,
            fuente=tema_fuente_cuerpo(self.form_asignado),
        )
        self.asig_nombre.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self.asig_cedula = Campo(
            self.form_asignado,
            "Cédula",
            transformacion=lambda t: "".join(c for c in t if c.isdigit())[:12],
            fondo=tema.FONDO,
            fuente=tema_fuente_cuerpo(self.form_asignado),
        )
        self.asig_cedula.grid(row=1, column=0, sticky="ew", padx=(0, 7), pady=(0, 8))
        self.asig_correo = Campo(
            self.form_asignado,
            "Correo electrónico",
            fondo=tema.FONDO,
            fuente=tema_fuente_cuerpo(self.form_asignado),
        )
        self.asig_correo.grid(row=1, column=1, sticky="ew", padx=(7, 0), pady=(0, 8))

        self.form_renovacion = tk.Frame(self.formulario, bg=tema.FONDO)
        etiqueta(
            self.form_renovacion,
            "OPERADOR EXISTENTE",
            fuente=tema_fuente_micro(self.form_renovacion),
            color=tema.MUTED,
            fondo=tema.FONDO,
        ).pack(anchor="w", pady=(0, 5))
        self.combo_operador = ttk.Combobox(
            self.form_renovacion,
            values=list(self._mapa_operadores.keys()),
            state="readonly" if self._operadores else "disabled",
        )
        self.combo_operador.pack(fill="x")
        if not self._operadores:
            etiqueta(
                self.form_renovacion,
                "No hay operadores registrados todavía.",
                fuente=tema_fuente_micro(self.form_renovacion),
                color=tema.AMBAR,
                fondo=tema.FONDO,
            ).pack(anchor="w", pady=(4, 0))
        etiqueta(
            self.form_renovacion,
            "Se revocarán los códigos anteriores del operador y se emitirá uno nuevo.",
            fuente=tema_fuente_micro(self.form_renovacion),
            color=tema.MUTED,
            fondo=tema.FONDO,
            wraplength=590,
            justify="left",
        ).pack(anchor="w", pady=(7, 0))

        vigencia = tk.Frame(cuerpo, bg=tema.FONDO)
        vigencia.pack(fill="x", pady=(15, 0))
        izquierda = tk.Frame(vigencia, bg=tema.FONDO)
        izquierda.pack(side="left")
        etiqueta(
            izquierda,
            "VIGENCIA EN DÍAS",
            fuente=tema_fuente_micro(izquierda),
            color=tema.MUTED,
            fondo=tema.FONDO,
        ).pack(anchor="w", pady=(0, 5))
        self.dias_var = tk.StringVar(value="7")
        self.spin_dias = ttk.Spinbox(
            izquierda,
            from_=1,
            to=365,
            textvariable=self.dias_var,
            width=7,
            command=self._actualizar_fecha,
        )
        self.spin_dias.pack(side="left")
        self.spin_dias.bind("<KeyRelease>", lambda _e: self._actualizar_fecha())
        etiqueta(
            izquierda,
            "días",
            fuente=tema_fuente_pequena(izquierda),
            color=tema.TEXTO_SUAVE,
            fondo=tema.FONDO,
        ).pack(side="left", padx=(7, 0))
        derecha = tk.Frame(vigencia, bg=tema.FONDO)
        derecha.pack(side="right")
        etiqueta(
            derecha,
            "VENCE APROXIMADAMENTE",
            fuente=tema_fuente_micro(derecha),
            color=tema.MUTED,
            fondo=tema.FONDO,
        ).pack(anchor="e")
        self.lbl_vence = etiqueta(
            derecha,
            "",
            fuente=tema_fuente_pequena(derecha),
            color=tema.CARAMELO_CLARO,
            fondo=tema.FONDO,
        )
        self.lbl_vence.pack(anchor="e")
        self._actualizar_fecha()

        etiqueta(
            cuerpo,
            "El código se muestra una sola vez. Se guarda únicamente su hash y su pista final.",
            fuente=tema_fuente_micro(cuerpo),
            color=tema.MUTED,
            fondo=tema.FONDO,
            wraplength=600,
            justify="left",
        ).pack(anchor="w", pady=(15, 0))

        pie = tk.Frame(self.tenedor, bg=tema.FONDO)
        pie.pack(fill="x", side="bottom", padx=26, pady=(0, 18))
        self.boton_generar = Boton(
            pie,
            "Generar código seguro",
            self._generar,
            variante="caramelo",
            icono="+",
            ancho=240,
            alto=46,
            fondo=tema.FONDO,
        )
        self.boton_generar.pack(side="right")
        Boton(
            pie,
            "Cancelar",
            self.cerrar,
            variante="fantasma",
            ancho=112,
            alto=40,
            fondo=tema.FONDO,
        ).pack(side="right", padx=(0, 8))

        if self.operador_preseleccionado:
            for etiqueta_operador, operador in self._mapa_operadores.items():
                if int(operador["id"]) == self.operador_preseleccionado:
                    self.combo_operador.set(etiqueta_operador)
                    break

    def _cambiar_modo(self, modo: str, *, inicial: bool = False) -> None:
        self._modo = modo
        if hasattr(self, "selector") and self.selector.seleccion != modo:
            self.selector.seleccionar(modo)
        for frame in (self.form_libre, self.form_asignado, self.form_renovacion):
            frame.pack_forget()
        if modo == "libre":
            self.form_libre.pack(fill="x")
            self.descripcion_modo.configure(
                text="Código abierto: el operador completará nombre, cédula y correo al activarlo."
            )
        elif modo == "asignado":
            self.form_asignado.pack(fill="x")
            self.descripcion_modo.configure(
                text="Los datos deben coincidir exactamente con los del operador al activar el código."
            )
        else:
            self.form_renovacion.pack(fill="x")
            self.descripcion_modo.configure(
                text="Emite un nuevo acceso para un operador ya registrado. El anterior queda revocado."
            )
        if not inicial:
            self.after(
                80,
                (
                    self.asig_nombre.enfocar
                    if modo == "asignado"
                    else self.combo_operador.focus_set
                    if modo == "renovacion" and self._operadores
                    else lambda: None
                ),
            )

    def _actualizar_fecha(self) -> None:
        try:
            dias = max(1, min(365, int(self.dias_var.get() or 7)))
        except (TypeError, ValueError):
            dias = 7
        vence = ahora_utc() + timedelta(days=dias)
        self.lbl_vence.configure(text=formatear_fecha_hora(vence))

    def _mostrar_error(self, mensaje: str) -> None:
        self.banner.mostrar("No se pudo generar", mensaje, "error")
        if not self._banner_visible:
            self.banner.pack(fill="x", pady=(0, 12), before=self.formulario)
            self._banner_visible = True

    def _generar(self) -> None:
        try:
            dias = int(self.dias_var.get() or 0)
        except ValueError:
            self._mostrar_error("La vigencia debe ser un número entero de días.")
            return
        operador_id = None
        nombre = None
        cedula = None
        correo = None
        if self._modo == "renovacion":
            seleccionado = self.combo_operador.get().strip()
            datos = self._mapa_operadores.get(seleccionado)
            if not datos:
                self._mostrar_error("Selecciona el operador que recibirá la renovación.")
                return
            operador_id = int(datos["id"])
        elif self._modo == "asignado":
            nombre = self.asig_nombre.get().strip()
            cedula = self.asig_cedula.get().strip()
            correo = self.asig_correo.get().strip()
            if not nombre or not cedula or not correo:
                self._mostrar_error(
                    "Completa nombre, cédula y correo para asignar la invitación."
                )
                return
        self.boton_generar.configurar_estado("deshabilitado")
        self.boton_generar.configurar_texto("Generando…")
        self.update_idletasks()
        try:
            emitido = self.app.administracion.emitir_codigo(
                admin=self.admin,
                dias_vigencia=dias,
                operador_id=operador_id,
                nombre=nombre,
                cedula=cedula,
                correo=correo,
            )
        except (ErrorValidacion, ErrorAdministracion) as exc:
            self._mostrar_error(str(exc))
            self.boton_generar.configurar_estado("normal")
            self.boton_generar.configurar_texto("Generar código seguro", icono="+")
            return
        except Exception as exc:
            self._mostrar_error(f"Error inesperado: {exc}")
            self.boton_generar.configurar_estado("normal")
            self.boton_generar.configurar_texto("Generar código seguro", icono="+")
            return
        self.resultado = emitido
        self.cerrar()


def _cabecera(
    padre: tk.Misc,
    titulo: str,
    subtitulo: str,
    sobre_titulo: str,
) -> None:
    marco = tk.Frame(padre, bg=tema.SUPERFICIE)
    marco.pack(fill="x")
    fila = tk.Frame(marco, bg=tema.SUPERFICIE)
    fila.pack(fill="x", padx=26, pady=(16, 13))
    MarcaCandy(fila, 38, fondo=tema.SUPERFICIE).pack(side="left", padx=(0, 11))
    textos = tk.Frame(fila, bg=tema.SUPERFICIE)
    textos.pack(side="left", fill="x", expand=True)
    etiqueta(
        textos,
        sobre_titulo,
        fuente=tema_fuente_micro(textos),
        color=tema.CARAMELO,
        fondo=tema.SUPERFICIE,
    ).pack(anchor="w")
    etiqueta(
        textos,
        titulo,
        fuente=tema_fuente_encabezado(textos),
        color=tema.TEXTO,
        fondo=tema.SUPERFICIE,
    ).pack(anchor="w")
    etiqueta(
        textos,
        subtitulo,
        fuente=tema_fuente_pequena(textos),
        color=tema.MUTED,
        fondo=tema.SUPERFICIE,
    ).pack(anchor="w")


def _iniciales(nombre: str) -> str:
    partes = [p for p in nombre.strip().split() if p]
    if not partes:
        return "AD"
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()
