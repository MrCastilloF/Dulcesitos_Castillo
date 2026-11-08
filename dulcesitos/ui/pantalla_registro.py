"""Pantalla de registro de productos de una sesión de inventario."""

from __future__ import annotations

import logging
import tkinter as tk

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
from .dialogos import DialogoMensaje
from .pantalla_acceso import (
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
        self._filas: dict[str, RegistroSesion] = {}
        self._contador_filas = 0
        self._bind_f2: str | None = None
        self._after_foco: str | None = None
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
                ("codigo", "Código", 134, "w"),
                ("descripcion", "Descripción", 330, "w"),
                ("hora", "Hora", 82, "center"),
            ],
            alto=5,
            fondo=tema.SUPERFICIE,
            mensaje_vacio="Aún no hay productos.\nEl primero que escanees aparecerá aquí.",
            autoseleccionar=False,
        )
        self.tabla.pack(fill="both", expand=True)
        self.tabla.aplicar_etiquetas(
            {
                "impar": {"background": tema.SUPERFICIE},
                "par": {"background": "#1A120F"},
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
            etiqueta(
                fila,
                valor,
                fuente=tema_fuente_micro(fila),
                color=tema.TEXTO_SUAVE,
                fondo=tema.SUPERFICIE,
            ).pack(side="right")

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
        estado = self._estado_lector
        if estado.estado == "activo":
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
            self._render_detalle(registros[0], "registrado", "Producto ya registrado")
        self._actualizar_boton_deshacer()

    def _fila_desde_registro(self, registro: RegistroSesion) -> dict[str, str]:
        self._contador_filas += 1
        clave = f"fila_{registro.id}_{self._contador_filas}"
        self._filas[clave] = registro
        return {
            "_id": clave,
            "codigo": registro.codigo,
            "descripcion": truncar(registro.descripcion, 58),
            "hora": formatear_hora(registro.escaneado_en),
            "_tags": ("par" if self._contador_filas % 2 == 0 else "impar",),
        }

    def _insertar_registro_tabla(self, registro: RegistroSesion) -> None:
        fila = self._fila_desde_registro(registro)
        # Se inserta al inicio para mantener la lectura más reciente visible.
        self.tabla.insertar_inicio(fila, fila["_id"])
        self.tabla.arbol.see(fila["_id"])

    # ------------------------------------------------------------------
    # Escaneo
    # ------------------------------------------------------------------
    def recibir_lectura_serial(self, codigo: str) -> None:
        self._procesar_codigo(codigo)

    def _procesar_codigo(self, codigo: str) -> None:
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
                None, "duplicado", "DUPLICADO", campos=resultado.campos
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
            "ok" if estado == "registrado" else "advertencia" if estado == "duplicado" else "error",
        )
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
    def _enfocar_escaneo(self) -> None:
        if self.entrada._habilitado and self.app.grab_current() is None:
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
            if self.app.grab_current() is not None or not self.app.winfo_viewable():
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
