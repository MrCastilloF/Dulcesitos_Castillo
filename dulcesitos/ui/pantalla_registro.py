"""Pantalla de registro de productos de una sesión de inventario."""

from __future__ import annotations

import logging
import tkinter as tk
from typing import Any

from ..archivo_maestro import convertir_numero, formatear_cantidad
from ..modelos import EstadoLector, RegistroSesion, ResultadoEscaneo
from ..servicios import ErrorInventario
from ..utilidades import (
    formatear_fecha_hora,
    formatear_hora,
    truncar,
)
from . import tema
from .componentes import (
    BannerEstado,
    BarraProgreso,
    Boton,
    EntradaEscaneo,
    MarcoDesplazable,
    Pildora,
    TablaDatos,
    Tarjeta,
    TarjetaMetrica,
    encabezado_tarjeta,
    etiqueta,
)
from .dialogos import DialogoMensaje, DialogoRegistroManual
from .pantalla_acceso import (
    tema_fuente_cuerpo,
    tema_fuente_cuerpo_fuerte,
    tema_fuente_micro,
    tema_fuente_pequena,
    tema_fuente_titulo,
)

LOG = logging.getLogger(__name__)


class PantallaRegistro(tk.Frame):
    def __init__(self, master: tk.Misc, app, *, mensaje_inicial: str = ""):
        super().__init__(master, bg=tema.FONDO)
        self.app = app
        self.sesion = app.sesion
        self.operador = app.operador
        self.maestro = app.maestro
        self._mensaje_inicial = mensaje_inicial
        self._estado_lector: EstadoLector = app.estado_lector
        self._ultimo_resultado: ResultadoEscaneo | None = None
        self._registro_en_detalle: RegistroSesion | None = None
        self._entrada_stock: tk.Entry | None = None
        self._filas: dict[str, RegistroSesion] = {}
        self._contador_filas = 0
        self._bind_f2: str | None = None
        self._after_foco: str | None = None
        self._after_acceso: str | None = None
        self._acceso_bloqueado = False
        self._dialogo_manual_abierto = False
        self._dialogo_manual = None
        self._construir()
        self._actualizar_lector_visual()
        self._refrescar_tabla_inicial()
        self._actualizar_contadores()
        self._actualizar_boton_final()
        if not self._filas:
            self._render_detalle_vacio()
        if mensaje_inicial:
            self._mostrar_feedback(
                "Sesión lista",
                mensaje_inicial,
                "ok",
            )
        self.after(120, self._enfocar_escaneo)
        self._bind_f2 = self.winfo_toplevel().bind("<F2>", self._tecla_f2, add="+")
        self.bind("<Destroy>", self._al_destruir, add="+")
        self._programar_foco()
        self._programar_verificacion_acceso()

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------
    def _construir(self) -> None:
        scroll = MarcoDesplazable(self, fondo=tema.FONDO, expandir_alto=True)
        scroll.pack(fill="both", expand=True)
        self._scroll = scroll
        raiz = tk.Frame(scroll.interior, bg=tema.FONDO)
        raiz.pack(fill="both", expand=True, padx=26, pady=(13, 17))
        raiz.grid_columnconfigure(0, weight=1)
        raiz.grid_rowconfigure(2, weight=1)

        self._construir_cabecera(raiz)
        self._construir_metricas(raiz)
        cuerpo = tk.Frame(raiz, bg=tema.FONDO)
        cuerpo.grid(row=2, column=0, sticky="nsew", pady=(11, 0))
        cuerpo.grid_columnconfigure(0, weight=3, uniform="registro")
        cuerpo.grid_columnconfigure(1, weight=2, uniform="registro")
        cuerpo.grid_rowconfigure(0, weight=1)

        izquierda = tk.Frame(cuerpo, bg=tema.FONDO)
        izquierda.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        derecha = tk.Frame(cuerpo, bg=tema.FONDO)
        derecha.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        derecha.grid_rowconfigure(0, weight=1)

        self._construir_tarjeta_escaneo(izquierda)
        self._construir_tarjeta_tabla(izquierda)
        self._construir_tarjeta_detalle(derecha)
        self._construir_tarjeta_control(derecha)

    def _construir_cabecera(self, raiz: tk.Frame) -> None:
        fila = tk.Frame(raiz, bg=tema.FONDO)
        fila.grid(row=0, column=0, sticky="ew")
        izquierda = tk.Frame(fila, bg=tema.FONDO)
        izquierda.pack(side="left", fill="x", expand=True)
        etiqueta(
            izquierda,
            "REGISTRO EN CURSO",
            fuente=tema_fuente_micro(izquierda),
            color=tema.CARAMELO,
            fondo=tema.FONDO,
        ).pack(anchor="w")
        etiqueta(
            izquierda,
            "Escanea. Valida. Listo.",
            fuente=tema_fuente_titulo(izquierda),
            color=tema.TEXTO,
            fondo=tema.FONDO,
        ).pack(anchor="w", pady=(1, 1))
        inicio = formatear_fecha_hora(self.sesion.inicio_en) if self.sesion else "—"
        etiqueta(
            izquierda,
            f"Sesión #{self.sesion.id if self.sesion else '—'} · iniciada {inicio} · "
            f"catálogo {self.maestro.nombre if self.maestro else '—'}",
            fuente=tema_fuente_pequena(izquierda),
            color=tema.MUTED,
            fondo=tema.FONDO,
            wraplength=820,
            justify="left",
        ).pack(anchor="w")

        acciones = tk.Frame(fila, bg=tema.FONDO)
        acciones.pack(side="right", anchor="e", padx=(16, 0))
        self.pildora_sesion = Pildora(
            acciones,
            "SESIÓN ABIERTA",
            "ok",
            fondo=tema.FONDO,
        )
        self.pildora_sesion.pack(anchor="e", pady=(0, 6))
        self.boton_finalizar = Boton(
            acciones,
            "Proceso/Registro terminado",
            self._finalizar,
            variante="caramelo",
            icono="✓",
            ancho=290,
            alto=46,
            fondo=tema.FONDO,
        )
        self.boton_finalizar.pack(anchor="e")

    def _construir_metricas(self, raiz: tk.Frame) -> None:
        fila = tk.Frame(raiz, bg=tema.FONDO)
        fila.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        for indice in range(4):
            fila.grid_columnconfigure(indice, weight=1, uniform="metricas")
        self.metrica_registrados = TarjetaMetrica(
            fila, "Registrados", "0", color=tema.VERDE, compacta=True
        )
        self.metrica_registrados.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.metrica_duplicados = TarjetaMetrica(
            fila, "Duplicados", "0", color=tema.CARAMELO, compacta=True
        )
        self.metrica_duplicados.grid(row=0, column=1, sticky="ew", padx=5)
        self.metrica_no_encontrados = TarjetaMetrica(
            fila, "No encontrados", "0", color=tema.ROJO, compacta=True
        )
        self.metrica_no_encontrados.grid(row=0, column=2, sticky="ew", padx=5)
        self.metrica_lecturas = TarjetaMetrica(
            fila, "Lecturas totales", "0", color=tema.AZUL, compacta=True
        )
        self.metrica_lecturas.grid(row=0, column=3, sticky="ew", padx=(5, 0))

    def _construir_tarjeta_escaneo(self, padre: tk.Frame) -> None:
        self.tarjeta_escaneo = Tarjeta(
            padre, padding=17, acento=tema.ROSA
        )
        self.tarjeta_escaneo.pack(fill="x")
        contenido = self.tarjeta_escaneo.contenido
        cabecera = encabezado_tarjeta(
            contenido,
            "Lector de códigos",
            "Un producto por lectura. Si ya existe, te lo avisaremos.",
            fondo=tema.SUPERFICIE,
            derecha_texto="LECTOR ACTIVO",
            derecha_estado="ok",
        )
        cabecera.pack(fill="x")
        self.pildora_lector = cabecera.pildora_derecha
        self.entrada = EntradaEscaneo(
            contenido,
            self._procesar_codigo,
            fondo=tema.SUPERFICIE,
            borde=tema.ROSA,
            placeholder="Escanea el producto…",
            texto_deshabilitado="Lector no activo. Revisa la calibración.",
            habilitado=True,
        )
        self.entrada.pack(fill="x", pady=(11, 9))
        fila_manual = tk.Frame(contenido, bg=tema.SUPERFICIE)
        fila_manual.pack(fill="x", pady=(0, 9))
        self.boton_manual = Boton(
            fila_manual,
            "Registro manual",
            self._abrir_registro_manual,
            variante="secundario",
            icono="⌨",
            ancho=174,
            alto=34,
            fuente=tema_fuente_pequena(fila_manual),
            fondo=tema.SUPERFICIE,
        )
        self.boton_manual.pack(side="left")
        etiqueta(
            fila_manual,
            "Si el código no se lee o no aparece: pausa el lector y escribe la novedad.",
            fuente=tema_fuente_micro(fila_manual),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
            wraplength=350,
            justify="left",
        ).pack(side="left", padx=(9, 0))
        self.banner = BannerEstado(contenido, fondo=tema.SUPERFICIE)
        self.banner.pack(fill="x")
        self.banner.mostrar(
            "Listo para escanear",
            "Apunta el lector al código de barras. La lectura se guarda al instante.",
            "info",
        )

    def _construir_tarjeta_tabla(self, padre: tk.Frame) -> None:
        self.tarjeta_tabla = Tarjeta(padre, padding=13)
        self.tarjeta_tabla.pack(fill="both", expand=True, pady=(12, 0))
        contenido = self.tarjeta_tabla.contenido
        cabecera = encabezado_tarjeta(
            contenido,
            "Productos registrados",
            "Los más recientes aparecen primero.",
            fondo=tema.SUPERFICIE,
            derecha_texto="0 PRODUCTOS",
            derecha_estado="neutro",
        )
        cabecera.pack(fill="x", pady=(0, 8))
        self.pildora_tabla = cabecera.pildora_derecha
        self.tabla = TablaDatos(
            contenido,
            [
                ("codigo", "Código", 132, "w"),
                ("descripcion", "Descripción", 278, "w"),
                ("origen", "Origen", 76, "center"),
                ("hora", "Hora", 72, "center"),
            ],
            alto=5,
            fondo=tema.SUPERFICIE,
            mensaje_vacio="Aún no hay productos.\nEl primero que escanees aparecerá aquí.",
            autoseleccionar=False,
            al_seleccionar=self._seleccionar_registro_tabla,
        )
        self.tabla.pack(fill="both", expand=True)
        self.tabla.aplicar_etiquetas(
            {
                "impar": {"background": tema.SUPERFICIE},
                "par": {"background": "#1A120F"},
                "manual": {"foreground": tema.AMBAR_CLARO},
            }
        )

    def _construir_tarjeta_detalle(self, padre: tk.Frame) -> None:
        self.tarjeta_detalle = Tarjeta(
            padre, padding=17, acento=tema.VERDE
        )
        self.tarjeta_detalle.grid(row=0, column=0, sticky="nsew")
        self.contenido_detalle = self.tarjeta_detalle.contenido
        cabecera = encabezado_tarjeta(
            self.contenido_detalle,
            "Último producto",
            "Aquí ves lo que acabas de escanear.",
            fondo=tema.SUPERFICIE,
            derecha_texto="SIN LECTURAS",
            derecha_estado="neutro",
        )
        cabecera.pack(fill="x")
        self.pildora_detalle = cabecera.pildora_derecha

        cobertura = tk.Frame(
            self.contenido_detalle,
            bg=tema.SUPERFICIE_2,
            highlightbackground=tema.BORDE_SUAVE,
            highlightthickness=1,
        )
        cobertura.pack(fill="x", side="bottom", pady=(10, 0))
        fila_cobertura = tk.Frame(cobertura, bg=tema.SUPERFICIE_2)
        fila_cobertura.pack(fill="x", padx=10, pady=(7, 5))
        etiqueta(
            fila_cobertura,
            "COBERTURA DEL CATÁLOGO",
            fuente=tema_fuente_micro(fila_cobertura),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE_2,
        ).pack(side="left")
        self.lbl_cobertura = etiqueta(
            fila_cobertura,
            "0 de 0",
            fuente=tema_fuente_micro(fila_cobertura),
            color=tema.VERDE_CLARO,
            fondo=tema.SUPERFICIE_2,
        )
        self.lbl_cobertura.pack(side="right")
        self.barra_cobertura = BarraProgreso(
            cobertura,
            fondo=tema.SUPERFICIE_3,
            color=tema.VERDE,
            alto=7,
        )
        self.barra_cobertura.pack(fill="x", padx=10, pady=(0, 8))

        self.cuerpo_detalle = tk.Frame(self.contenido_detalle, bg=tema.SUPERFICIE)
        self.cuerpo_detalle.pack(fill="both", expand=True, pady=(12, 0))

    def _construir_tarjeta_control(self, padre: tk.Frame) -> None:
        self.tarjeta_control = Tarjeta(padre, padding=16)
        self.tarjeta_control.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        contenido = self.tarjeta_control.contenido
        encabezado_tarjeta(
            contenido,
            "Control de la sesión",
            f"Operador: {self.operador.nombre if self.operador else '—'}",
            fondo=tema.SUPERFICIE,
        ).pack(fill="x")
        info = tk.Frame(contenido, bg=tema.SUPERFICIE)
        info.pack(fill="x", pady=(9, 0))
        for rotulo, valor in [
            ("CÉDULA", self.operador.cedula if self.operador else "—"),
            ("ARCHIVO", truncar(self.maestro.nombre if self.maestro else "—", 34)),
            ("AJUSTES DE STOCK", "0"),
            ("REGISTROS MANUALES", "0"),
        ]:
            fila = tk.Frame(info, bg=tema.SUPERFICIE)
            fila.pack(fill="x", pady=1)
            etiqueta(
                fila,
                rotulo,
                fuente=tema_fuente_micro(fila),
                color=tema.MUTED,
                fondo=tema.SUPERFICIE,
            ).pack(side="left")
            valor_label = etiqueta(
                fila,
                valor,
                fuente=tema_fuente_micro(fila),
                color=tema.TEXTO_SUAVE,
                fondo=tema.SUPERFICIE,
            )
            valor_label.pack(side="right")
            if rotulo == "AJUSTES DE STOCK":
                self.lbl_ajustes_stock = valor_label
            elif rotulo == "REGISTROS MANUALES":
                self.lbl_manuales = valor_label

        self.boton_deshacer = Boton(
            contenido,
            "Deshacer última lectura",
            self._deshacer,
            variante="secundario",
            ancho=220,
            alto=38,
            fuente=tema_fuente_pequena(contenido),
            fondo=tema.SUPERFICIE,
        )
        self.boton_deshacer.pack(fill="x", pady=(12, 0))
        self.boton_deshacer.configurar_estado("deshabilitado")
        Boton(
            contenido,
            "Revisar lector y calibrar",
            self._volver_a_calibrar,
            variante="fantasma",
            ancho=220,
            alto=34,
            fuente=tema_fuente_pequena(contenido),
            fondo=tema.SUPERFICIE,
        ).pack(fill="x", pady=(3, 0))
        etiqueta(
            contenido,
            "Tus registros quedan guardados aunque cierres la sesión.",
            fuente=tema_fuente_micro(contenido),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
            wraplength=450,
            justify="left",
        ).pack(anchor="w", pady=(9, 0))
        etiqueta(
            contenido,
            "F2 · ENFOCAR ESCANEO",
            fuente=tema_fuente_micro(contenido),
            color=tema.CARAMELO,
            fondo=tema.SUPERFICIE,
        ).pack(anchor="w", pady=(5, 0))

    # ------------------------------------------------------------------
    # Lector y datos
    # ------------------------------------------------------------------
    def _actualizar_lector_visual(self) -> None:
        if self._dialogo_manual_abierto:
            self.pildora_lector.actualizar("MODO MANUAL", "advertencia")
            self.entrada.habilitar(False)
            return
        estado = self._estado_lector
        if estado.estado == "activo" and not self._acceso_bloqueado:
            self.pildora_lector.actualizar("LECTOR ACTIVO", "ok")
            self.entrada.habilitar(True)
            self.tarjeta_escaneo.configure(
                highlightbackground=tema.BORDE, highlightcolor=tema.BORDE
            )
            self.tarjeta_escaneo._borde_original = tema.BORDE
        else:
            self.pildora_lector.actualizar(
                estado.etiqueta,
                "advertencia" if estado.estado != "desconectado" else "error",
            )
            self.entrada.habilitar(False)
            self.tarjeta_escaneo.configure(
                highlightbackground=tema.ROJO if estado.estado == "desconectado" else tema.CARAMELO,
                highlightcolor=tema.ROJO if estado.estado == "desconectado" else tema.CARAMELO,
            )
            self.tarjeta_escaneo._borde_original = tema.BORDE

    def actualizar_lector(self, estado: EstadoLector) -> None:
        anterior = self._estado_lector
        self._estado_lector = estado
        self._actualizar_lector_visual()
        if estado.estado != "activo" and anterior.estado == "activo":
            self._mostrar_feedback(
                "Lector fuera de servicio",
                "El lector dejó de estar activo. Reconéctalo y usa «Revisar lector "
                "y calibrar» para volver a validarlo. Los registros están guardados.",
                "error",
            )

    def _refrescar_tabla_inicial(self) -> None:
        try:
            registros = self.app.inventario.registros_sesion(self.sesion.id)
        except Exception:
            LOG.exception("No se pudieron cargar los registros")
            registros = []
        registros = list(reversed(registros))
        filas = []
        self._filas.clear()
        self._contador_filas = 0
        for registro in registros:
            fila = self._fila_desde_registro(registro)
            filas.append(fila)
        self.tabla.cargar(filas)
        if registros:
            self._ultimo_resultado = None
            primero = registros[0]
            self._render_detalle(
                primero,
                "manual" if primero.es_manual else "registrado",
                "MANUAL" if primero.es_manual else "Producto ya registrado",
            )
        self._actualizar_boton_deshacer()

    def _fila_desde_registro(self, registro: RegistroSesion) -> dict[str, str]:
        self._contador_filas += 1
        clave = f"fila_{registro.id}_{self._contador_filas}"
        self._filas[clave] = registro
        etiquetas = ["par" if self._contador_filas % 2 == 0 else "impar"]
        if registro.es_manual:
            etiquetas.append("manual")
        return {
            "_id": clave,
            "codigo": registro.codigo,
            "descripcion": truncar(registro.descripcion, 48),
            "origen": "Manual" if registro.es_manual else "Lector",
            "hora": formatear_hora(registro.escaneado_en),
            "_tags": tuple(etiquetas),
        }

    def _insertar_registro_tabla(self, registro: RegistroSesion) -> None:
        fila = self._fila_desde_registro(registro)
        # Se inserta al inicio para mantener la lectura más reciente visible.
        self.tabla.insertar_inicio(fila, fila["_id"])
        self.tabla.arbol.see(fila["_id"])

    def _seleccionar_registro_tabla(self, fila: Any) -> None:
        if not fila:
            return
        base = self._filas.get(fila.get("_id"))
        if base is None:
            return
        actual = self.app.inventario.db.obtener_registro_por_clave(
            self.sesion.id, base.codigo_clave
        )
        if actual is None:
            return
        self._render_detalle(
            actual,
            "manual" if actual.es_manual else "registrado",
            "MANUAL" if actual.es_manual else "REGISTRADO",
        )

    # ------------------------------------------------------------------
    # Escaneo y registro manual
    # ------------------------------------------------------------------
    def _abrir_registro_manual(self) -> None:
        if self._dialogo_manual_abierto:
            return
        if (
            self._acceso_bloqueado
            or self.app.operador is None
            or not self.app.auth.sesion_operador_vigente(self.app.operador)
        ):
            self._bloquear_por_acceso()
            return
        self._dialogo_manual_abierto = True
        self.app.lector.pausar_captura()
        self.entrada.habilitar(False)
        self.pildora_lector.actualizar("MODO MANUAL", "advertencia")
        self.boton_manual.configurar_estado("deshabilitado")
        self.boton_manual.configurar_texto("Lector en pausa", icono="⌨")
        dialogo = None
        try:
            dialogo = DialogoRegistroManual(
                self,
                servicio=self.app.inventario,
                sesion=self.sesion,
                maestro=self.maestro,
                operador=self.app.operador,
            )
            self._dialogo_manual = dialogo
            dialogo.mostrar()
            self.wait_window(dialogo)
            registro = dialogo.resultado
        finally:
            self._dialogo_manual = None
            self._dialogo_manual_abierto = False
            self.app.lector.reanudar_captura()
            self.boton_manual.configurar_estado(
                "deshabilitado" if self._acceso_bloqueado else "normal"
            )
            self.boton_manual.configurar_texto("Registro manual", icono="⌨")
            self._actualizar_lector_visual()
        if self._acceso_bloqueado:
            return
        if registro is not None:
            self._insertar_registro_tabla(registro)
            self._render_detalle(registro, "manual", "MANUAL")
            self._actualizar_contadores()
            self._mostrar_feedback(
                "Registro manual guardado",
                f"{registro.descripcion}. La novedad quedó guardada en la sesión "
                "y saldrá en el archivo de actualización.",
                "ok",
            )
            self.app.sonidos.exito()
        else:
            self._mostrar_feedback(
                "Modo normal",
                "El formulario se cerró y el lector vuelve a estar disponible. "
                "No se creó ningún registro.",
                "info",
            )
        self.after(120, self._enfocar_escaneo)

    def recibir_lectura_serial(self, codigo: str) -> None:
        if self._dialogo_manual_abierto:
            return
        self._procesar_codigo(codigo)

    def _procesar_codigo(self, codigo: str) -> None:
        if (
            self._acceso_bloqueado
            or self.app.operador is None
            or not self.app.auth.sesion_operador_vigente(self.app.operador)
        ):
            self._bloquear_por_acceso()
            return
        codigo = codigo.strip()
        if not codigo:
            self._mostrar_feedback(
                "Lectura vacía",
                "El lector no envió un código. Intenta de nuevo.",
                "advertencia",
            )
            self.app.sonidos.advertencia()
            return
        if self._estado_lector.estado != "activo":
            self.app.sonidos.error()
            self._mostrar_feedback(
                "Registro bloqueado",
                "El lector no está activo. Revisa la calibración antes de seguir.",
                "error",
            )
            self.entrada.marcar_estado("error")
            return
        if self.app.config_lector.modo == "HID":
            self.app.notificar_lectura_hid(codigo)
            self._estado_lector = self.app.estado_lector
            self._actualizar_lector_visual()
        try:
            resultado = self.app.inventario.procesar_escaneo(
                self.sesion, self.maestro, codigo
            )
        except ErrorInventario as exc:
            self.app.sonidos.error()
            self._mostrar_feedback("No se pudo registrar", str(exc), "error")
            self.entrada.marcar_estado("error")
            return
        except Exception as exc:
            LOG.exception("Error procesando escaneo")
            self.app.sonidos.error()
            self._mostrar_feedback(
                "Error inesperado",
                f"No se pudo guardar la lectura. Tus registros anteriores están a salvo.\n{exc}",
                "error",
            )
            return

        self._ultimo_resultado = resultado
        self._actualizar_metricas(resultado.estadisticas)
        if resultado.estado == "registrado" and resultado.registro is not None:
            self.app.sonidos.exito()
            self._insertar_registro_tabla(resultado.registro)
            self._render_detalle(resultado.registro, "registrado", "REGISTRADO")
            self._mostrar_feedback(
                "Producto registrado",
                f"{resultado.registro.descripcion} · {resultado.registro.codigo}. "
                "Continúa con el siguiente.",
                "ok",
            )
            self.entrada.marcar_estado("ok")
            self._actualizar_boton_deshacer()
        elif resultado.estado == "duplicado":
            self.app.sonidos.advertencia()
            self._render_detalle(
                resultado.registro_existente,
                "duplicado",
                "DUPLICADO",
                campos=resultado.campos,
            )
            self._mostrar_feedback(
                "Lectura duplicada",
                resultado.mensaje + " No se agregó otro registro.",
                "advertencia",
            )
            self.entrada.marcar_estado("advertencia")
        elif resultado.estado == "no_encontrado":
            self.app.sonidos.error()
            self._render_detalle(None, "no_encontrado", "NO ENCONTRADO", codigo=codigo)
            self._mostrar_feedback(
                "Código no encontrado",
                resultado.mensaje
                + " Revisa que el producto esté en el catálogo y que el código "
                "haya llegado completo.",
                "error",
            )
            self.entrada.marcar_estado("error")
        else:
            self.app.sonidos.advertencia()
            self._mostrar_feedback(
                "Lectura vacía",
                resultado.mensaje,
                "advertencia",
            )
        self._actualizar_contadores()
        self._actualizar_boton_final()

    def _actualizar_metricas(self, estadisticas) -> None:
        self.metrica_registrados.actualizar(estadisticas.registrados)
        self.metrica_duplicados.actualizar(estadisticas.duplicados)
        self.metrica_no_encontrados.actualizar(estadisticas.no_encontrados)
        self.metrica_lecturas.actualizar(estadisticas.total_lecturas)
        self._actualizar_cobertura(estadisticas.registrados)
        if hasattr(self, "lbl_ajustes_stock"):
            self.lbl_ajustes_stock.configure(text=str(estadisticas.ajustes_stock))
        if hasattr(self, "lbl_manuales"):
            self.lbl_manuales.configure(text=str(estadisticas.manuales))
        self._actualizar_boton_final()

    def _actualizar_cobertura(self, registrados: int) -> None:
        total = self.maestro.total if self.maestro else 0
        proporcion = (registrados / total) if total else 0.0
        self.lbl_cobertura.configure(
            text=f"{registrados} de {total} · {proporcion * 100:.0f}%"
        )
        self.barra_cobertura.actualizar(proporcion)

    def _actualizar_contadores(self) -> None:
        try:
            estadisticas = self.app.inventario.estadisticas(self.sesion.id)
        except Exception:
            LOG.exception("No se pudieron actualizar los contadores")
            return
        self._actualizar_metricas(estadisticas)
        self.pildora_tabla.actualizar(
            f"{estadisticas.registrados} PRODUCTO"
            + ("" if estadisticas.registrados == 1 else "S"),
            "ok" if estadisticas.registrados else "neutro",
        )

    def _actualizar_boton_final(self) -> None:
        try:
            total = self.app.inventario.estadisticas(self.sesion.id).registrados
        except Exception:
            total = 0
        self.boton_finalizar.configurar_estado("normal" if total else "deshabilitado")

    def _actualizar_boton_deshacer(self) -> None:
        try:
            tiene = self.app.inventario.estadisticas(self.sesion.id).registrados > 0
        except Exception:
            tiene = False
        self.boton_deshacer.configurar_estado("normal" if tiene else "deshabilitado")

    def _mostrar_feedback(self, titulo: str, mensaje: str, estado: str) -> None:
        self.banner.mostrar(titulo, mensaje, estado)

    # ------------------------------------------------------------------
    # Detalle
    # ------------------------------------------------------------------
    def _render_detalle_vacio(self) -> None:
        for hijo in self.cuerpo_detalle.winfo_children():
            hijo.destroy()
        self.pildora_detalle.actualizar("SIN LECTURAS", "neutro")
        marco = tk.Frame(self.cuerpo_detalle, bg=tema.SUPERFICIE)
        marco.pack(fill="both", expand=True)
        icono = tk.Canvas(marco, width=78, height=70, bg=tema.SUPERFICIE, highlightthickness=0, bd=0)
        icono.pack(pady=(20, 6))
        for i, alto_linea in enumerate((30, 46, 38, 52, 34, 44, 28)):
            x = 8 + i * 9
            icono.create_line(x, 20, x, 20 + alto_linea, fill=tema.BORDE, width=3)
        etiqueta(
            marco,
            "Esperando la primera lectura",
            fuente=tema_fuente_cuerpo_fuerte(marco),
            color=tema.TEXTO_SUAVE,
            fondo=tema.SUPERFICIE,
        ).pack()
        etiqueta(
            marco,
            "El detalle del producto aparecerá aquí con todos\nlos campos del catálogo.",
            fuente=tema_fuente_pequena(marco),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
            justify="center",
        ).pack(pady=(3, 0))

    def _render_detalle(
        self,
        registro: RegistroSesion | None,
        estado: str,
        etiqueta_estado: str,
        *,
        campos: dict[str, str] | None = None,
        codigo: str = "",
    ) -> None:
        for hijo in self.cuerpo_detalle.winfo_children():
            hijo.destroy()
        self.pildora_detalle.actualizar(
            etiqueta_estado,
            "ok"
            if estado in {"registrado", "manual"}
            else "advertencia"
            if estado == "duplicado"
            else "error",
        )
        self._registro_en_detalle = registro
        self._entrada_stock = None
        if estado == "no_encontrado":
            self._render_no_encontrado(codigo)
            return
        datos = campos or (registro.campos if registro else {})
        descripcion = (
            registro.descripcion
            if registro
            else datos.get(self.maestro.columna_descripcion, "Producto del catálogo")
        )
        codigo_producto = (
            registro.codigo
            if registro
            else datos.get(self.maestro.columna_codigo, codigo)
        )
        if registro is not None and registro.es_manual:
            nota_manual = tk.Frame(
                self.cuerpo_detalle,
                bg=tema.AMBAR_FONDO,
                highlightbackground="#6B4B0B",
                highlightthickness=1,
            )
            nota_manual.pack(fill="x", pady=(0, 8))
            etiqueta(
                nota_manual,
                "REGISTRO MANUAL · NOVEDAD",
                fuente=tema_fuente_micro(nota_manual),
                color=tema.AMBAR_CLARO,
                fondo=tema.AMBAR_FONDO,
            ).pack(anchor="w", padx=9, pady=(6, 1))
            etiqueta(
                nota_manual,
                registro.novedad or "Sin novedad escrita.",
                fuente=tema_fuente_micro(nota_manual),
                color=tema.TEXTO_SUAVE,
                fondo=tema.AMBAR_FONDO,
                wraplength=430,
                justify="left",
            ).pack(anchor="w", padx=9, pady=(0, 6))
        etiqueta(
            self.cuerpo_detalle,
            descripcion,
            fuente=tema_fuente_cuerpo_fuerte(self.cuerpo_detalle),
            color=tema.TEXTO,
            fondo=tema.SUPERFICIE,
            wraplength=460,
            justify="left",
        ).pack(anchor="w")
        fila_codigo = tk.Frame(self.cuerpo_detalle, bg=tema.SUPERFICIE)
        fila_codigo.pack(fill="x", pady=(2, 8))
        etiqueta(
            fila_codigo,
            codigo_producto,
            fuente=tema_fuente_micro(fila_codigo),
            color=tema.CARAMELO_CLARO,
            fondo=tema.SUPERFICIE,
        ).pack(side="left")
        if registro:
            etiqueta(
                fila_codigo,
                f"· {formatear_hora(registro.escaneado_en)}",
                fuente=tema_fuente_micro(fila_codigo),
                color=tema.MUTED,
                fondo=tema.SUPERFICIE,
            ).pack(side="left", padx=(5, 0))
        if estado == "duplicado":
            nota = tk.Frame(
                self.cuerpo_detalle,
                bg=tema.AMBAR_FONDO,
                highlightbackground="#6B4B0B",
                highlightthickness=1,
            )
            nota.pack(fill="x", pady=(0, 8))
            etiqueta(
                nota,
                "Este producto ya estaba registrado en la sesión.",
                fuente=tema_fuente_micro(nota),
                color=tema.AMBAR_CLARO,
                fondo=tema.AMBAR_FONDO,
                wraplength=430,
                justify="left",
            ).pack(anchor="w", padx=9, pady=6)

        extras = []
        for columna, valor in datos.items():
            if columna in {
                self.maestro.columna_codigo,
                self.maestro.columna_descripcion,
                self.maestro.columna_stock,
            }:
                continue
            if valor:
                extras.append((columna, valor))
        if not extras:
            etiqueta(
                self.cuerpo_detalle,
                "Sin campos adicionales en el catálogo.",
                fuente=tema_fuente_micro(self.cuerpo_detalle),
                color=tema.MUTED,
                fondo=tema.SUPERFICIE,
            ).pack(anchor="w")
        for rotulo, valor in extras[:7]:
            fila = tk.Frame(self.cuerpo_detalle, bg=tema.SUPERFICIE)
            fila.pack(fill="x", pady=2)
            etiqueta(
                fila,
                truncar(rotulo.upper(), 24),
                fuente=tema_fuente_micro(fila),
                color=tema.MUTED,
                fondo=tema.SUPERFICIE,
            ).pack(side="left", anchor="n")
            etiqueta(
                fila,
                truncar(valor, 46),
                fuente=tema_fuente_micro(fila),
                color=tema.TEXTO_SUAVE,
                fondo=tema.SUPERFICIE,
                anchor="e",
                wraplength=310,
                justify="right",
            ).pack(side="right", anchor="e")
        if len(extras) > 7:
            etiqueta(
                self.cuerpo_detalle,
                f"+ {len(extras) - 7} campos guardados en el archivo de salida",
                fuente=tema_fuente_micro(self.cuerpo_detalle),
                color=tema.MUTED,
                fondo=tema.SUPERFICIE,
            ).pack(anchor="w", pady=(2, 0))
        if registro is not None:
            self._render_editor_stock(registro, datos)

    def _render_editor_stock(
        self, registro: RegistroSesion, datos: dict[str, str]
    ) -> None:
        columna = self.maestro.columna_stock
        if not columna:
            return
        original = registro.stock_original
        if original is None:
            original = convertir_numero(datos.get(columna, ""))
        nuevo = registro.stock_nuevo
        caja = tk.Frame(
            self.cuerpo_detalle,
            bg=tema.AZUL_FONDO,
            highlightbackground="#1E4B77",
            highlightthickness=1,
        )
        caja.pack(fill="x", pady=(11, 0))
        cabecera = tk.Frame(caja, bg=tema.AZUL_FONDO)
        cabecera.pack(fill="x", padx=10, pady=(7, 3))
        etiqueta(
            cabecera,
            "AJUSTAR STOCK CONTADO",
            fuente=tema_fuente_micro(cabecera),
            color=tema.AZUL_CLARO,
            fondo=tema.AZUL_FONDO,
        ).pack(side="left")
        etiqueta(
            cabecera,
            f"Catálogo: {formatear_cantidad(original) or '—'}",
            fuente=tema_fuente_micro(cabecera),
            color=tema.TEXTO_SUAVE,
            fondo=tema.AZUL_FONDO,
        ).pack(side="right")
        fila = tk.Frame(caja, bg=tema.AZUL_FONDO)
        fila.pack(fill="x", padx=10, pady=(0, 8))
        variable = tk.StringVar(
            value=formatear_cantidad(nuevo if nuevo is not None else original)
        )
        self._variable_stock = variable
        entrada = tk.Entry(
            fila,
            textvariable=variable,
            bg=tema.SUPERFICIE_2,
            fg=tema.TEXTO,
            insertbackground=tema.CARAMELO,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightbackground=tema.BORDE,
            highlightcolor=tema.CARAMELO,
            font=tema_fuente_cuerpo(fila),
            width=10,
            justify="right",
        )
        entrada.pack(side="left", ipady=7)
        entrada.bind("<Return>", lambda _e: self._guardar_stock(registro))
        self._entrada_stock = entrada
        Boton(
            fila,
            "Guardar stock",
            lambda: self._guardar_stock(registro),
            variante="primario",
            icono="✓",
            ancho=152,
            alto=34,
            fuente=tema_fuente_pequena(fila),
            fondo=tema.AZUL_FONDO,
            takefocus=False,
        ).pack(side="right")
        if nuevo is not None:
            Boton(
                fila,
                "Quitar ajuste",
                lambda: self._quitar_stock(registro),
                variante="fantasma",
                ancho=120,
                alto=32,
                fuente=tema_fuente_micro(fila),
                fondo=tema.AZUL_FONDO,
                takefocus=False,
            ).pack(side="right", padx=(0, 6))
        if nuevo is not None:
            diferencia = registro.stock_diferencia
            signo = "+" if diferencia is not None and diferencia > 0 else ""
            etiqueta(
                caja,
                "Ajuste guardado: "
                f"{formatear_cantidad(nuevo)}"
                + (
                    f" ({signo}{formatear_cantidad(diferencia)} frente al catálogo)"
                    if diferencia is not None
                    else ""
                ),
                fuente=tema_fuente_micro(caja),
                color=tema.VERDE_CLARO,
                fondo=tema.AZUL_FONDO,
                wraplength=430,
                justify="left",
            ).pack(anchor="w", padx=10, pady=(0, 7))
        else:
            etiqueta(
                caja,
                "Opcional: escribe el conteo físico y guárdalo. Si no ajustas, "
                "se conserva el stock del catálogo.",
                fuente=tema_fuente_micro(caja),
                color=tema.MUTED,
                fondo=tema.AZUL_FONDO,
                wraplength=430,
                justify="left",
            ).pack(anchor="w", padx=10, pady=(0, 7))

    def _guardar_stock(self, registro: RegistroSesion) -> None:
        if (
            self._acceso_bloqueado
            or self.app.operador is None
            or not self.app.auth.sesion_operador_vigente(self.app.operador)
        ):
            self._bloquear_por_acceso()
            return
        texto = self._variable_stock.get().strip()
        nuevo = convertir_numero(texto)
        if nuevo is None:
            self._mostrar_feedback(
                "Stock inválido",
                "Escribe una cantidad numérica para el stock contado.",
                "error",
            )
            self.app.sonidos.error()
            self._entrada_stock.focus_set()
            return
        try:
            actualizado = self.app.inventario.ajustar_stock(
                sesion=self.sesion,
                maestro=self.maestro,
                registro=registro,
                stock_nuevo=nuevo,
                operador=self.app.operador,
            )
        except ErrorInventario as exc:
            self._mostrar_feedback("No se pudo ajustar el stock", str(exc), "error")
            self.app.sonidos.error()
            return
        self.app.sonidos.exito()
        self._render_detalle(actualizado, "registrado", "REGISTRADO")
        self._actualizar_contadores()
        self._mostrar_feedback(
            "Stock ajustado",
            f"{actualizado.descripcion}: stock contado "
            f"{formatear_cantidad(actualizado.stock_nuevo)}. "
            "El valor se aplicará en el archivo de actualización.",
            "ok",
        )
        self.after(100, self._enfocar_escaneo)

    def _quitar_stock(self, registro: RegistroSesion) -> None:
        try:
            actualizado = self.app.inventario.quitar_ajuste_stock(
                sesion=self.sesion, registro=registro
            )
        except ErrorInventario as exc:
            self._mostrar_feedback("No se pudo quitar el ajuste", str(exc), "error")
            return
        self._render_detalle(actualizado, "registrado", "REGISTRADO")
        self._actualizar_contadores()
        self._mostrar_feedback(
            "Ajuste retirado",
            "El producto conservará el stock del catálogo en el archivo de salida.",
            "advertencia",
        )
        self.after(100, self._enfocar_escaneo)

    def _render_no_encontrado(self, codigo: str) -> None:
        self.pildora_detalle.actualizar("NO ENCONTRADO", "error")
        etiqueta(
            self.cuerpo_detalle,
            "Código fuera del catálogo",
            fuente=tema_fuente_cuerpo_fuerte(self.cuerpo_detalle),
            color=tema.ROJO_CLARO,
            fondo=tema.SUPERFICIE,
        ).pack(anchor="w", pady=(2, 0))
        caja = tk.Frame(
            self.cuerpo_detalle,
            bg=tema.ROJO_FONDO,
            highlightbackground="#71212A",
            highlightthickness=1,
        )
        caja.pack(fill="x", pady=(9, 0))
        etiqueta(
            caja,
            truncar(codigo, 60),
            fuente=tema_fuente_pequena(caja),
            color=tema.TEXTO,
            fondo=tema.ROJO_FONDO,
            wraplength=430,
            justify="left",
        ).pack(anchor="w", padx=10, pady=10)
        etiqueta(
            self.cuerpo_detalle,
            "Verifica que el producto exista en el archivo maestro y que el "
            "código se haya escaneado completo. La lectura quedó registrada "
            "como incidencia, pero no suma al inventario.",
            fuente=tema_fuente_micro(self.cuerpo_detalle),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
            wraplength=460,
            justify="left",
        ).pack(anchor="w", pady=(9, 0))

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def _deshacer(self) -> None:
        try:
            total = self.app.inventario.estadisticas(self.sesion.id).registrados
        except Exception:
            total = 0
        if total == 0:
            return
        if not DialogoMensaje.preguntar(
            self,
            titulo="Deshacer última lectura",
            mensaje=(
                "Se eliminará el último producto registrado de esta sesión. "
                "Esta acción no modifica el archivo maestro. ¿Deseas continuar?"
            ),
            estado="advertencia",
            texto_aceptar="Deshacer registro",
            texto_cancelar="Conservar",
        ):
            self._enfocar_escaneo()
            return
        try:
            eliminado = self.app.inventario.deshacer_ultimo(self.sesion)
        except Exception as exc:
            self._mostrar_feedback("No se pudo deshacer", str(exc), "error")
            return
        if eliminado is None:
            self._mostrar_feedback(
                "Nada que deshacer",
                "No quedan productos registrados en esta sesión.",
                "advertencia",
            )
        else:
            self._mostrar_feedback(
                "Lectura deshecha",
                f"Se retiró «{eliminado.descripcion}» de esta sesión.",
                "advertencia",
            )
            self.app.sonidos.advertencia()
        self._refrescar_tabla_inicial()
        self._actualizar_contadores()
        self._actualizar_boton_final()
        self._actualizar_boton_deshacer()
        self._enfocar_escaneo()

    def _finalizar(self) -> None:
        self.app.finalizar_registro()

    def _volver_a_calibrar(self) -> None:
        if not DialogoMensaje.preguntar(
            self,
            titulo="Volver a la calibración",
            mensaje=(
                "La sesión quedará abierta. Podrás reanudarla después de validar "
                "de nuevo el lector. No se perderá ningún registro."
            ),
            estado="info",
            texto_aceptar="Ir a calibrar",
            texto_cancelar="Seguir registrando",
        ):
            self._enfocar_escaneo()
            return
        self.app.volver_a_estacion_sesion_abierta()

    # ------------------------------------------------------------------
    # Foco y teclado
    # ------------------------------------------------------------------
    def _programar_verificacion_acceso(self) -> None:
        try:
            self._after_acceso = self.after(7000, self._verificar_acceso)
        except tk.TclError:
            self._after_acceso = None

    def _verificar_acceso(self) -> None:
        try:
            if not self.winfo_exists() or self.app._pantalla_actual is not self:
                return
            if (
                not self._acceso_bloqueado
                and (
                    self.app.operador is None
                    or not self.app.auth.sesion_operador_vigente(self.app.operador)
                )
            ):
                self._bloquear_por_acceso()
        except tk.TclError:
            return
        finally:
            self._programar_verificacion_acceso()

    def _bloquear_por_acceso(self) -> None:
        if self._acceso_bloqueado:
            return
        self._acceso_bloqueado = True
        self.entrada.habilitar(False)
        self.entrada.configurar_texto_deshabilitado(
            "Acceso vencido o revocado. Solo puedes finalizar con autorización de administración."
        )
        if hasattr(self, "boton_manual"):
            self.boton_manual.configurar_estado("deshabilitado")
        if self._dialogo_manual is not None:
            try:
                self._dialogo_manual.cerrar()
            except tk.TclError:
                pass
            self._dialogo_manual = None
        self.pildora_sesion.actualizar("ACCESO BLOQUEADO", "error")
        self._mostrar_feedback(
            "Acceso bloqueado",
            "Tu código de acceso venció o fue revocado. No se pueden registrar "
            "más productos. Los registros están guardados; un administrador puede "
            "renovarte el acceso y autorizar el cierre de esta sesión.",
            "error",
        )
        self.app.sonidos.error()

    def _enfocar_escaneo(self) -> None:
        if (
            self.entrada._habilitado
            and not self._acceso_bloqueado
            and self.app.grab_current() is None
        ):
            self.entrada.enfocar()

    def _programar_foco(self) -> None:
        try:
            self._after_foco = self.after(1300, self._refrescar_foco)
        except tk.TclError:
            self._after_foco = None

    def _refrescar_foco(self) -> None:
        try:
            if not self.winfo_exists() or self.app._pantalla_actual is not self:
                return
            if (
                self.app.grab_current() is not None
                or not self.app.winfo_viewable()
                or self._acceso_bloqueado
            ):
                return
            actual = self.focus_get()
            if actual is None or actual is self.entrada.entrada:
                if actual is None:
                    self.entrada.enfocar()
                return
            # Si el foco está en la tabla o en un botón, se devuelve al escáner
            # para que una lectura nunca se pierda en medio de la bodega.
            toplevel_actual = actual.winfo_toplevel()
            if toplevel_actual is self.app and not isinstance(actual, (tk.Entry, tk.Text)):
                self.entrada.enfocar()
        except tk.TclError:
            return
        finally:
            self._programar_foco()

    def _tecla_f2(self, _evento: tk.Event) -> str:
        self._enfocar_escaneo()
        return "break"

    def _al_destruir(self, evento: tk.Event) -> None:
        if evento.widget is not self:
            return
        if self._bind_f2:
            try:
                self.winfo_toplevel().unbind("<F2>", self._bind_f2)
            except tk.TclError:
                pass
        if self._after_foco:
            try:
                self.after_cancel(self._after_foco)
            except tk.TclError:
                pass
            self._after_foco = None
        if self._after_acceso:
            try:
                self.after_cancel(self._after_acceso)
            except tk.TclError:
                pass
            self._after_acceso = None
        if self._dialogo_manual_abierto:
            try:
                self.app.lector.reanudar_captura()
            except Exception:
                pass
            self._dialogo_manual_abierto = False
