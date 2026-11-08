"""Ventana principal y controlador de navegación de la aplicación."""

from __future__ import annotations

import logging
import queue
import tkinter as tk
import traceback
from typing import Any

from ..archivo_maestro import (
    ArchivoMaestro,
    ErrorArchivoMaestro,
    cargar_instantanea,
    cargar_maestro_actual,
)
from ..base_datos import BaseDatos
from ..config import APP_NAME, APP_SUBTITLE, APP_VERSION, RutasApp
from ..lector import (
    EVENTO_ESTADO,
    EVENTO_LECTURA,
    ServicioLector,
    configuracion_desde_ajustes,
    puertos_seriales,
)
from ..modelos import (
    ConfiguracionLector,
    EstadoLector,
    Sesion,
    SesionOperador,
)
from ..recursos import configurar_icono
from ..servicios import (
    ErrorInventario,
    ServicioAdministracion,
    ServicioAutenticacion,
    ServicioInventario,
)
from ..utilidades import ahora_utc, formatear_fecha_hora, iniciales
from . import tema
from .componentes import Avatar, Boton, IndicadorLector, MarcaCandy, etiqueta, separador
from .dialogos import DialogoAutorizacionCierre, DialogoMensaje, DialogoProgreso
from .sonido import Sonidos

LOG = logging.getLogger(__name__)


class Aplicacion(tk.Tk):
    """Orquesta pantallas, servicios, lector y seguridad."""

    def __init__(
        self,
        rutas: RutasApp,
        db: BaseDatos,
        *,
        iniciar_lector: bool = True,
    ):
        super().__init__()
        self.rutas = rutas
        self.db = db
        self.auth = ServicioAutenticacion(db)
        self.administracion = ServicioAdministracion(db)
        self.inventario = ServicioInventario(db, rutas)
        self.sonidos = Sonidos()

        self.operador: SesionOperador | None = None
        self.sesion: Sesion | None = None
        self.sesion_pendiente: Sesion | None = None
        self.maestro: ArchivoMaestro | None = None
        self.error_maestro: str | None = None
        self.catalogo_es_instantanea = False
        self.calibrado = False
        self.codigo_calibracion = ""
        self.mensaje_bienvenida = ""
        self._panel_admin: Any = None
        self._cerrando = False
        self._pantalla_actual: Any = None

        self._configurar_ventana()
        self._fuentes_app = tema.preparar_entorno(self)
        self._construir_estructura()

        self.config_lector = configuracion_desde_ajustes(self.db.obtener_ajuste)
        self._cola_lector: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=200)
        self.lector = ServicioLector(self.config_lector, self._cola_lector)
        self.estado_lector: EstadoLector = self.lector.estado_actual()
        if iniciar_lector:
            self.lector.iniciar()
        self._actualizar_indicador_lector()
        self._actualizar_barra()
        self.after(120, self._procesar_eventos_lector)
        self.protocol("WM_DELETE_WINDOW", self._al_cerrar_ventana)
        self.report_callback_exception = self._reportar_excepcion_tk
        self._mostrar_inicio()

    # ------------------------------------------------------------------
    # Configuración general
    # ------------------------------------------------------------------
    def _configurar_ventana(self) -> None:
        self.title(f"{APP_NAME} · {APP_SUBTITLE}")
        self.configure(bg=tema.FONDO)
        configurar_icono(self)
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "DulcesitosCastillo.Inventario.1"
            )
        except Exception:
            pass

        # Escalado según el DPI real de Windows, después de activar DPI awareness.
        try:
            dpi = float(self.winfo_fpixels("1i"))
            if dpi > 0:
                self.tk.call("tk", "scaling", dpi / 72.0)
        except tk.TclError:
            pass

        ancho_pantalla = self.winfo_screenwidth()
        alto_pantalla = self.winfo_screenheight()
        ancho = min(1460, max(1120, int(ancho_pantalla * 0.91)))
        alto = min(920, max(670, int(alto_pantalla * 0.9)))
        x = max(0, (ancho_pantalla - ancho) // 2)
        y = max(0, (alto_pantalla - alto) // 2 - 10)
        self.geometry(f"{ancho}x{alto}+{x}+{y}")
        self.minsize(1080, 650)
        self._ancho_inicial = ancho
        self._alto_inicial = alto

    def _construir_estructura(self) -> None:
        barra = tk.Frame(self, bg=tema.FONDO, height=70)
        barra.pack(fill="x", side="top")
        barra.pack_propagate(False)
        interior = tk.Frame(barra, bg=tema.FONDO)
        interior.pack(fill="both", expand=True, padx=26, pady=12)

        marca = tk.Frame(interior, bg=tema.FONDO)
        marca.pack(side="left")
        MarcaCandy(marca, 44, fondo=tema.FONDO).pack(side="left", padx=(0, 12))
        textos = tk.Frame(marca, bg=tema.FONDO)
        textos.pack(side="left")
        etiqueta(
            textos,
            APP_NAME.upper(),
            fuente=self._fuentes_app.cuerpo_fuerte,
            color=tema.CREMA,
            fondo=tema.FONDO,
        ).pack(anchor="w")
        etiqueta(
            textos,
            "INVENTARIO DE BODEGA · SENA",
            fuente=self._fuentes_app.micro,
            color=tema.MUTED,
            fondo=tema.FONDO,
        ).pack(anchor="w")

        derecha = tk.Frame(interior, bg=tema.FONDO)
        derecha.pack(side="right")
        self._indicador_lector = IndicadorLector(
            derecha,
            fondo=tema.FONDO,
            comando=self._solicitar_redeteccion,
            ancho=204,
            alto=34,
        )
        self._indicador_lector.pack(side="right")
        self._zona_operador = tk.Frame(derecha, bg=tema.FONDO)
        self._zona_operador.pack(side="right", padx=(0, 14))

        separador(self, tema.BORDE, 1).pack(fill="x", side="top")
        self.contenido = tk.Frame(self, bg=tema.FONDO)
        self.contenido.pack(fill="both", expand=True)

    def _actualizar_barra(self) -> None:
        if not hasattr(self, "_zona_operador"):
            return
        for hijo in self._zona_operador.winfo_children():
            hijo.destroy()
        zona = self._zona_operador
        if self.operador:
            Boton(
                zona,
                "Salir",
                self._solicitar_cierre_sesion,
                variante="fantasma",
                ancho=78,
                alto=34,
                fuente=self._fuentes_app.pequena,
                fondo=tema.FONDO,
                takefocus=False,
            ).pack(side="right", padx=(8, 0))
            Boton(
                zona,
                "Admin",
                self.abrir_panel_admin,
                variante="secundario",
                ancho=90,
                alto=34,
                fuente=self._fuentes_app.pequena,
                fondo=tema.FONDO,
                takefocus=False,
            ).pack(side="right", padx=(10, 0))
            perfil = tk.Frame(zona, bg=tema.FONDO)
            perfil.pack(side="right", padx=(10, 0))
            Avatar(
                perfil,
                iniciales(self.operador.nombre),
                38,
                fondo=tema.FONDO,
            ).pack(side="left", padx=(0, 9))
            datos = tk.Frame(perfil, bg=tema.FONDO)
            datos.pack(side="left")
            nombre = self.operador.nombre
            etiqueta(
                datos,
                nombre if len(nombre) <= 28 else nombre[:27] + "…",
                fuente=self._fuentes_app.pequena,
                color=tema.TEXTO,
                fondo=tema.FONDO,
                anchor="e",
            ).pack(anchor="e")
            etiqueta(
                datos,
                f"C.C. {self.operador.cedula}",
                fuente=self._fuentes_app.micro,
                color=tema.MUTED,
                fondo=tema.FONDO,
                anchor="e",
            ).pack(anchor="e")
        else:
            Boton(
                zona,
                "Acceso administración",
                self.abrir_panel_admin,
                variante="fantasma",
                ancho=172,
                alto=34,
                fuente=self._fuentes_app.pequena,
                fondo=tema.FONDO,
                takefocus=False,
            ).pack(side="right")
            etiqueta(
                zona,
                f"v{APP_VERSION}",
                fuente=self._fuentes_app.micro,
                color=tema.MUTED,
                fondo=tema.FONDO,
            ).pack(side="right", padx=(0, 14))

    def _actualizar_indicador_lector(self) -> None:
        try:
            self._indicador_lector.actualizar(self.estado_lector)
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Navegación
    # ------------------------------------------------------------------
    def _mostrar_inicio(self) -> None:
        if self.auth.requiere_configuracion():
            self.ir_configuracion_inicial()
        else:
            self.ir_acceso()

    def _cambiar_pantalla(self, clase: type[Any], **kwargs: Any) -> None:
        anterior = self._pantalla_actual
        self._pantalla_actual = None
        if anterior is not None:
            try:
                anterior.destroy()
            except tk.TclError:
                pass
        pantalla = clase(self.contenido, self, **kwargs)
        pantalla.pack(fill="both", expand=True)
        self._pantalla_actual = pantalla
        self._actualizar_barra()

    def ir_configuracion_inicial(self) -> None:
        from .pantalla_acceso import PantallaConfiguracionInicial

        self.operador = None
        self.sesion = None
        self._cambiar_pantalla(PantallaConfiguracionInicial)

    def ir_acceso(
        self,
        *,
        mensaje_exito: str = "",
        aviso: str = "",
        tab: str = "login",
    ) -> None:
        from .pantalla_acceso import PantallaAcceso

        self.operador = None
        self.sesion = None
        self.sesion_pendiente = None
        self.maestro = None
        self.error_maestro = None
        self.calibrado = False
        self.catalogo_es_instantanea = False
        self.lector.invalidar_calibracion()
        self._cambiar_pantalla(
            PantallaAcceso,
            mensaje_exito=mensaje_exito,
            aviso=aviso,
            tab=tab,
        )

    def iniciar_sesion_operador(
        self,
        operador: SesionOperador,
        *,
        mensaje_bienvenida: str = "",
    ) -> None:
        self.operador = operador
        self.sesion = None
        self.sesion_pendiente = None
        self.maestro = None
        self.error_maestro = None
        self.calibrado = False
        self.codigo_calibracion = ""
        self.catalogo_es_instantanea = False
        self.lector.invalidar_calibracion()
        self.mensaje_bienvenida = mensaje_bienvenida

        pendiente = self.inventario.sesion_abierta(operador.operador_id)
        if pendiente is not None:
            self.sesion_pendiente = pendiente
            try:
                self.maestro = cargar_instantanea(pendiente.instantanea_ruta or "")
                self.catalogo_es_instantanea = True
                self.error_maestro = None
            except (ErrorArchivoMaestro, OSError) as exc:
                # Plan de recuperación: si la copia se perdió pero el archivo
                # original sigue intacto, se puede reanudar con él.
                recuperado = False
                try:
                    original = cargar_maestro_actual(self.rutas.maestra)
                    if original.huella == pendiente.maestro_hash:
                        self.maestro = original
                        self.catalogo_es_instantanea = True
                        self.error_maestro = None
                        recuperado = True
                except ErrorArchivoMaestro:
                    recuperado = False
                if not recuperado:
                    self.maestro = None
                    self.error_maestro = (
                        "Tienes una sesión abierta, pero no fue posible cargar su "
                        "copia del catálogo y el archivo maestro actual ya no "
                        "coincide. Pide al administrador que revise la carpeta de "
                        "datos de la aplicación.\n\nDetalle: "
                        f"{exc}"
                    )
        else:
            self._cargar_catalogo_actual(silencioso=False)

        self.estado_lector = self.lector.estado_actual()
        self._actualizar_indicador_lector()
        self._ir_estacion()

    def _ir_estacion(self) -> None:
        from .pantalla_estacion import PantallaEstacion

        self._cambiar_pantalla(
            PantallaEstacion,
            mensaje_bienvenida=self.mensaje_bienvenida,
        )
        self.mensaje_bienvenida = ""

    def _cargar_catalogo_actual(self, *, silencioso: bool = False) -> bool:
        try:
            maestro = cargar_maestro_actual(self.rutas.maestra)
        except ErrorArchivoMaestro as exc:
            self.maestro = None
            self.error_maestro = str(exc)
            self.catalogo_es_instantanea = False
            if not silencioso:
                LOG.warning("No se pudo cargar el catálogo: %s", exc)
            return False
        self.maestro = maestro
        self.error_maestro = None
        self.catalogo_es_instantanea = False
        return True

    def recargar_catalogo(self, *, mostrar_aviso: bool = True) -> bool:
        if self.sesion_pendiente is not None:
            if mostrar_aviso:
                DialogoMensaje.aviso(
                    self,
                    titulo="Catálogo bloqueado",
                    mensaje=(
                        "Hay una sesión sin finalizar que usa el catálogo original. "
                        "Reábrela y finalízala antes de cargar un archivo nuevo."
                    ),
                    estado="advertencia",
                )
            return False
        self.calibrado = False
        self.codigo_calibracion = ""
        self.lector.invalidar_calibracion("El catálogo cambió; calibra de nuevo.")
        resultado = self._cargar_catalogo_actual(silencioso=False)
        if self._pantalla_actual is not None and hasattr(
            self._pantalla_actual, "refrescar_catalogo"
        ):
            self._pantalla_actual.refrescar_catalogo()
        if mostrar_aviso:
            if resultado and self.maestro:
                self._pantalla_actual.mostrar_aviso(
                    f"Catálogo actualizado: {self.maestro.nombre} "
                    f"({self.maestro.total} productos).",
                    "ok",
                )
            else:
                self._pantalla_actual.mostrar_aviso(
                    "No se pudo actualizar el catálogo. Revisa el detalle en la tarjeta.",
                    "error",
                )
        return resultado

    def iniciar_registro(self, codigo_calibracion: str) -> None:
        if not self.operador:
            self.ir_acceso(aviso="La sesión de operador se perdió. Ingresa de nuevo.")
            return
        if not self.maestro:
            DialogoMensaje.aviso(
                self,
                titulo="Catálogo no disponible",
                mensaje="Debes cargar un archivo maestro válido antes de registrar.",
                estado="error",
            )
            return
        if not self.calibrado:
            DialogoMensaje.aviso(
                self,
                titulo="Calibración pendiente",
                mensaje="Realiza la prueba de sincronización con el lector antes de continuar.",
                estado="advertencia",
            )
            return
        if not self.auth.sesion_operador_vigente(self.operador):
            DialogoMensaje.aviso(
                self,
                titulo="Acceso vencido",
                mensaje=(
                    "Tu código de acceso venció o fue revocado. Solicita una "
                    "renovación al administrador antes de iniciar otra sesión."
                ),
                estado="error",
            )
            self.cerrar_sesion_operador()
            return
        if self.estado_lector.estado == "desconectado":
            DialogoMensaje.aviso(
                self,
                titulo="Lector desconectado",
                mensaje="Conecta el lector USB y realiza de nuevo la calibración.",
                estado="error",
            )
            return

        if self.sesion_pendiente is not None:
            self.sesion = self.sesion_pendiente
            self.sesion_pendiente = None
            self._ir_registro(
                mensaje="Sesión reanudada. Los registros anteriores se conservaron."
            )
            return

        try:
            sesion = self.inventario.iniciar_sesion(
                self.operador, self.maestro, codigo_calibracion
            )
        except ErrorInventario as exc:
            DialogoMensaje.aviso(
                self,
                titulo="No se pudo iniciar la sesión",
                mensaje=str(exc),
                estado="error",
            )
            return
        self.sesion = sesion
        self._ir_registro(mensaje="Sesión iniciada. Ya puedes escanear productos.")

    def _ir_registro(self, *, mensaje: str = "") -> None:
        from .pantalla_registro import PantallaRegistro

        self._cambiar_pantalla(PantallaRegistro, mensaje_inicial=mensaje)

    def finalizar_registro(self) -> None:
        if self.sesion is None or self.operador is None or self.maestro is None:
            return
        estadisticas = self.inventario.estadisticas(self.sesion.id)
        if estadisticas.registrados == 0:
            DialogoMensaje.aviso(
                self,
                titulo="Sesión sin productos",
                mensaje=(
                    "Escanea y registra al menos un producto antes de finalizar "
                    "el proceso."
                ),
                estado="advertencia",
            )
            return

        def autorizar(nombre: str, clave: str):
            return self.auth.autorizar_cierre(
                self.operador,
                nombre_confirmado=nombre,
                clave=clave,
            )

        dialogo = DialogoAutorizacionCierre(
            self,
            operador=self.operador,
            estadisticas=estadisticas,
            sesion_id=self.sesion.id,
            al_autorizar=autorizar,
        )
        dialogo.mostrar()
        self.wait_window(dialogo)
        autorizacion = dialogo.resultado
        if autorizacion is None:
            return

        progreso = DialogoProgreso(self)
        self.configure(cursor="watch")
        try:
            final, archivos = self.inventario.finalizar_sesion(
                sesion=self.sesion,
                operador=self.operador,
                autorizacion=autorizacion,
                maestro=self.maestro,
            )
        except Exception as exc:
            progreso.cerrar()
            self.configure(cursor="")
            LOG.exception("No se pudo finalizar la sesión")
            DialogoMensaje.aviso(
                self,
                titulo="El cierre no se completó",
                mensaje=(
                    "La sesión sigue abierta y tus registros están a salvo. "
                    "Revisa el detalle e intenta de nuevo."
                ),
                estado="error",
                detalle=str(exc),
            )
            return
        progreso.cerrar()
        self.configure(cursor="")
        self.sesion = final
        self.sesion_pendiente = None
        self.calibrado = False
        self.codigo_calibracion = ""
        self.lector.invalidar_calibracion()
        self.sonidos.exito()
        self._ir_cierre(final, archivos)

    def _ir_cierre(self, sesion: Sesion, archivos: list[Any]) -> None:
        from .pantalla_cierre import PantallaCierre

        self._cambiar_pantalla(
            PantallaCierre,
            sesion=sesion,
            archivos=archivos,
            operador=self.operador,
        )

    def volver_a_estacion_sesion_abierta(self) -> None:
        """Conserva la sesión abierta y exige recalibrar antes de reanudarla."""

        if self.sesion is None:
            return
        self.sesion_pendiente = self.sesion
        self.sesion = None
        self.calibrado = False
        self.codigo_calibracion = ""
        self.lector.invalidar_calibracion()
        self.mensaje_bienvenida = (
            "Sesión conservada. Valida de nuevo el lector para reanudar el registro."
        )
        self._ir_estacion()

    def nueva_sesion(self) -> None:
        if not self.operador:
            self.ir_acceso()
            return
        self.sesion = None
        self.sesion_pendiente = None
        self.calibrado = False
        self.codigo_calibracion = ""
        self.lector.invalidar_calibracion()
        self._cargar_catalogo_actual(silencioso=False)
        self.mensaje_bienvenida = (
            "Sesión anterior cerrada. Calibra el lector para iniciar una nueva."
        )
        self._ir_estacion()

    def _solicitar_cierre_sesion(self) -> None:
        sesion_abierta = (
            self.sesion is not None and self.sesion.estado == "abierta"
        ) or self.sesion_pendiente is not None or (
            self.operador is not None
            and self.inventario.sesion_abierta(self.operador.operador_id) is not None
        )
        if sesion_abierta and not DialogoMensaje.preguntar(
            self,
            titulo="Cerrar la sesión de operador",
            mensaje=(
                "Tus registros ya están guardados y podrás reanudar esta sesión "
                "cuando vuelvas a ingresar. ¿Deseas cerrar la sesión ahora?"
            ),
            estado="advertencia",
            texto_aceptar="Cerrar sesión",
            texto_cancelar="Seguir trabajando",
        ):
            return
        self.cerrar_sesion_operador()

    def cerrar_sesion_operador(self) -> None:
        self.operador = None
        self.sesion = None
        self.sesion_pendiente = None
        self.maestro = None
        self.error_maestro = None
        self.calibrado = False
        self.codigo_calibracion = ""
        self.catalogo_es_instantanea = False
        self.lector.invalidar_calibracion()
        self.ir_acceso(mensaje_exito="Sesión cerrada. Los registros guardados siguen disponibles.")

    # ------------------------------------------------------------------
    # Lector
    # ------------------------------------------------------------------
    def notificar_lectura_hid(self, codigo: str) -> None:
        if self.config_lector.modo != "HID":
            return
        self.lector.notificar_lectura_hid(codigo)
        self.estado_lector = self.lector.estado_actual()
        self._actualizar_indicador_lector()

    def invalidar_calibracion(self, motivo: str = "") -> None:
        self.calibrado = False
        self.codigo_calibracion = ""
        self.lector.invalidar_calibracion(motivo)

    def _solicitar_redeteccion(self) -> None:
        self.lector.solicitar_redeteccion()
        if self._pantalla_actual is not None and hasattr(
            self._pantalla_actual, "mostrar_aviso"
        ):
            self._pantalla_actual.mostrar_aviso(
                "Buscando de nuevo el lector USB…", "info"
            )

    def aplicar_configuracion_lector(self, configuracion: ConfiguracionLector) -> None:
        self.db.guardar_ajuste("lector_modo", configuracion.modo)
        self.db.guardar_ajuste("lector_puerto", configuracion.puerto)
        self.db.guardar_ajuste("lector_baudios", str(configuracion.baudios))
        self.config_lector = configuracion
        self.calibrado = False
        self.codigo_calibracion = ""
        self.lector.reconfigurar(configuracion)
        self.estado_lector = self.lector.estado_actual()
        self._actualizar_indicador_lector()
        if self._pantalla_actual is not None and hasattr(
            self._pantalla_actual, "actualizar_lector"
        ):
            self._pantalla_actual.actualizar_lector(self.estado_lector)

    def puertos_disponibles(self) -> list[tuple[str, str]]:
        return puertos_seriales()

    def _procesar_eventos_lector(self) -> None:
        if self._cerrando:
            return
        try:
            while True:
                tipo, dato = self._cola_lector.get_nowait()
                if tipo == EVENTO_ESTADO:
                    self._al_cambiar_estado_lector(dato)
                elif tipo == EVENTO_LECTURA:
                    self._al_lectura_serial(dato)
        except queue.Empty:
            pass
        except Exception:
            LOG.exception("Error procesando eventos del lector")
        try:
            self.after(120, self._procesar_eventos_lector)
        except tk.TclError:
            pass

    def _al_cambiar_estado_lector(self, nuevo: EstadoLector) -> None:
        anterior = self.estado_lector
        self.estado_lector = nuevo
        self._actualizar_indicador_lector()
        if self._pantalla_actual is not None and hasattr(
            self._pantalla_actual, "actualizar_lector"
        ):
            self._pantalla_actual.actualizar_lector(nuevo)
        if self._panel_admin is not None and hasattr(
            self._panel_admin, "actualizar_estado_lector"
        ):
            self._panel_admin.actualizar_estado_lector(nuevo)
        if anterior.estado != nuevo.estado:
            LOG.info("Estado del lector: %s", nuevo.estado)
        if nuevo.estado == "desconectado" and self.calibrado:
            self.calibrado = False
            self.codigo_calibracion = ""
            if self._pantalla_actual is not None and hasattr(
                self._pantalla_actual, "perder_calibracion"
            ):
                self._pantalla_actual.perder_calibracion(
                    "El lector se desconectó. Reconéctalo y realiza de nuevo la calibración."
                )

    def _al_lectura_serial(self, codigo: str) -> None:
        if self.grab_current() is not None:
            return
        pantalla = self._pantalla_actual
        if pantalla is not None and hasattr(pantalla, "recibir_lectura_serial"):
            pantalla.recibir_lectura_serial(codigo)

    # ------------------------------------------------------------------
    # Administración
    # ------------------------------------------------------------------
    def abrir_panel_admin(self) -> None:
        if not self.db.hay_administrador():
            DialogoMensaje.aviso(
                self,
                titulo="Administrador no configurado",
                mensaje=(
                    "Primero debes crear el administrador inicial desde la "
                    "pantalla de configuración."
                ),
                estado="advertencia",
            )
            return
        if self._panel_admin is not None:
            try:
                self._panel_admin.deiconify()
                self._panel_admin.lift()
                self._panel_admin.focus_force()
                return
            except tk.TclError:
                self._panel_admin = None
        from .panel_admin import PanelAdministracion

        panel = PanelAdministracion(self, self)
        panel.protocol(
            "WM_DELETE_WINDOW",
            lambda: self._cerrar_panel_admin(panel),
        )
        self._panel_admin = panel
        panel.mostrar()

    def _cerrar_panel_admin(self, panel: Any) -> None:
        self._panel_admin = None
        try:
            panel.destroy()
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Utilidades de UI
    # ------------------------------------------------------------------
    def mostrar_error(self, titulo: str, mensaje: str, detalle: str = "") -> None:
        DialogoMensaje.aviso(
            self,
            titulo=titulo,
            mensaje=mensaje,
            estado="error",
            detalle=detalle,
        )

    def mostrar_info(self, titulo: str, mensaje: str) -> None:
        DialogoMensaje.aviso(
            self,
            titulo=titulo,
            mensaje=mensaje,
            estado="info",
        )

    def _reportar_excepcion_tk(
        self, tipo: type[BaseException], valor: BaseException, tb: Any
    ) -> None:
        LOG.error(
            "Excepción no controlada en la interfaz",
            exc_info=(tipo, valor, tb),
        )
        detalle = "".join(traceback.format_exception(tipo, valor, tb))[-1800:]
        try:
            DialogoMensaje.aviso(
                self,
                titulo="Ocurrió un error inesperado",
                mensaje=(
                    "La aplicación encontró un problema, pero tus datos locales "
                    "no se borraron. Puedes continuar o reiniciar la aplicación."
                ),
                estado="error",
                detalle=detalle,
            )
        except Exception:
            LOG.debug("No se pudo mostrar el diálogo de error", exc_info=True)

    def _al_cerrar_ventana(self) -> None:
        if self._cerrando:
            return
        sesion_abierta = False
        if self.operador is not None:
            sesion_abierta = self.inventario.sesion_abierta(self.operador.operador_id) is not None
        if sesion_abierta:
            if not DialogoMensaje.preguntar(
                self,
                titulo="Salir de la aplicación",
                mensaje=(
                    "Hay una sesión de inventario sin finalizar. Todos los "
                    "registros ya están guardados y podrás reanudarla al "
                    "volver a ingresar."
                ),
                estado="advertencia",
                texto_aceptar="Salir ahora",
                texto_cancelar="Volver",
            ):
                return
        self._cerrando = True
        try:
            self.lector.detener()
        except Exception:
            LOG.debug("No se pudo detener el monitor del lector", exc_info=True)
        try:
            self.db.cerrar()
        except Exception:
            LOG.debug("No se pudo cerrar la base de datos", exc_info=True)
        try:
            self.destroy()
        except tk.TclError:
            pass

    def mostrar_portada_operador(self) -> str:
        if not self.operador:
            return ""
        fecha = formatear_fecha_hora(ahora_utc())
        return fecha
