"""Estación de preparación: catálogo, lector, calibración y arranque."""

from __future__ import annotations

import logging
import tkinter as tk
from datetime import datetime

from ..modelos import EstadoLector
from ..utilidades import (
    abrir_carpeta,
    formatear_fecha_hora,
    truncar,
)
from . import tema
from .componentes import (
    BannerEstado,
    Boton,
    EntradaEscaneo,
    MarcoDesplazable,
    Pildora,
    Stepper,
    Tarjeta,
    cabecera_seccion,
    encabezado_tarjeta,
    etiqueta,
)
from .pantalla_acceso import (
    tema_fuente_cuerpo_fuerte,
    tema_fuente_micro,
    tema_fuente_pequena,
)

LOG = logging.getLogger(__name__)


class PantallaEstacion(tk.Frame):
    def __init__(self, master: tk.Misc, app, *, mensaje_bienvenida: str = ""):
        super().__init__(master, bg=tema.FONDO)
        self.app = app
        self.operador = app.operador
        self._mensaje_bienvenida = mensaje_bienvenida
        self._estado_lector: EstadoLector = app.estado_lector
        self._bind_f2 = None
        self._construir()
        self._actualizar_lector_visual()
        self._actualizar_calibracion_visual()
        self._actualizar_stepper()
        self.after(100, self._enfocar_escaner)
        self.bind("<Destroy>", self._al_destruir, add="+")
        self._bind_f2 = self.winfo_toplevel().bind("<F2>", self._tecla_f2, add="+")

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------
    def _construir(self) -> None:
        scroll = MarcoDesplazable(self, fondo=tema.FONDO)
        scroll.pack(fill="both", expand=True)
        self._scroll = scroll
        raiz = tk.Frame(scroll.interior, bg=tema.FONDO)
        raiz.pack(fill="both", expand=True, padx=28, pady=(14, 20))
        self._raiz = raiz

        self._construir_cabecera(raiz)
        self.stepper = Stepper(
            raiz,
            ["Catálogo", "Lector", "Calibración"],
            fondo=tema.FONDO,
        )
        self.stepper.pack(fill="x", pady=(6, 12))

        self.aviso_temporal = BannerEstado(raiz, fondo=tema.FONDO)

        cuerpo = tk.Frame(raiz, bg=tema.FONDO)
        cuerpo.pack(fill="both", expand=True)
        cuerpo.grid_columnconfigure(0, weight=3, uniform="estacion")
        cuerpo.grid_columnconfigure(1, weight=2, uniform="estacion")

        izquierda = tk.Frame(cuerpo, bg=tema.FONDO)
        izquierda.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        derecha = tk.Frame(cuerpo, bg=tema.FONDO)
        derecha.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        self.tarjeta_lector = Tarjeta(izquierda, padding=18, acento=tema.AZUL)
        self.tarjeta_lector.pack(fill="x")
        self._construir_tarjeta_lector()

        self.tarjeta_calibracion = Tarjeta(
            izquierda, padding=20, acento=tema.CARAMELO
        )
        self.tarjeta_calibracion.pack(fill="x", pady=(14, 0))
        self._construir_tarjeta_calibracion()

        self.tarjeta_catalogo = Tarjeta(derecha, padding=18, acento=tema.CARAMELO)
        self.tarjeta_catalogo.pack(fill="x")
        self._cuerpo_catalogo = tk.Frame(
            self.tarjeta_catalogo.contenido, bg=tema.SUPERFICIE
        )
        self._render_catalogo()

        self.tarjeta_contexto = Tarjeta(derecha, padding=18)
        self.tarjeta_contexto.pack(fill="x", pady=(14, 0))
        self._render_contexto()

        self._construir_franja_flujo(raiz)

        pie = tk.Frame(raiz, bg=tema.FONDO)
        pie.pack(fill="x", pady=(16, 0))
        etiqueta(
            pie,
            "Consejo: mantén el cursor en el campo de escaneo. La aplicación "
            "valida cada lectura antes de guardarla.",
            fuente=tema_fuente_micro(pie),
            color=tema.MUTED,
            fondo=tema.FONDO,
        ).pack(side="left")
        etiqueta(
            pie,
            "F2 · ENFOCAR LECTOR",
            fuente=tema_fuente_micro(pie),
            color=tema.CARAMELO,
            fondo=tema.FONDO,
        ).pack(side="right")

    def _construir_cabecera(self, raiz: tk.Frame) -> None:
        fila = tk.Frame(raiz, bg=tema.FONDO)
        fila.pack(fill="x", pady=(0, 8))
        primeros = (self.operador.nombre if self.operador else "operador").split()
        nombre = primeros[0] if primeros else "operador"
        subtitulo = self._mensaje_bienvenida or (
            "Carga el catálogo, valida el lector y realiza la prueba de "
            "sincronización para habilitar el registro."
        )
        cabecera = cabecera_seccion(
            fila,
            "ESTACIÓN DE TRABAJO",
            f"Hola, {nombre}.",
            subtitulo,
        )
        cabecera.pack(side="left", fill="x", expand=True)

        derecha = tk.Frame(fila, bg=tema.FONDO)
        derecha.pack(side="right", anchor="n")
        ahora = datetime.now().astimezone()
        tarjeta_fecha = tk.Frame(
            derecha,
            bg=tema.SUPERFICIE,
            highlightbackground=tema.BORDE,
            highlightthickness=1,
        )
        tarjeta_fecha.pack(anchor="e")
        etiqueta(
            tarjeta_fecha,
            ahora.strftime("%d/%m/%Y").upper(),
            fuente=tema_fuente_cuerpo_fuerte(tarjeta_fecha),
            color=tema.CARAMELO,
            fondo=tema.SUPERFICIE,
        ).pack(anchor="e", padx=14, pady=(8, 0))
        etiqueta(
            tarjeta_fecha,
            "CONTROL DE BODEGA",
            fuente=tema_fuente_micro(tarjeta_fecha),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
        ).pack(anchor="e", padx=14, pady=(0, 8))
        if self.app.sesion_pendiente is not None:
            Pildora(
                derecha,
                "SESIÓN SIN FINALIZAR",
                "advertencia",
                fondo=tema.FONDO,
            ).pack(anchor="e", pady=(7, 0))

    def _construir_tarjeta_lector(self) -> None:
        contenido = self.tarjeta_lector.contenido
        cabecera = encabezado_tarjeta(
            contenido,
            "2 · Lector USB",
            "Detección del dispositivo y modo de captura.",
            fondo=tema.SUPERFICIE,
            derecha_texto="HID EN ESPERA",
            derecha_estado="advertencia",
        )
        cabecera.pack(fill="x")
        self.pildora_lector = cabecera.pildora_derecha

        fila = tk.Frame(contenido, bg=tema.SUPERFICIE)
        fila.pack(fill="x", pady=(12, 0))
        self._icono_lector = tk.Canvas(
            fila,
            width=50,
            height=50,
            bg=tema.SUPERFICIE,
            highlightthickness=0,
            bd=0,
        )
        self._icono_lector.pack(side="left", padx=(0, 12))
        self._dibujar_icono_lector(tema.AMBAR)
        textos = tk.Frame(fila, bg=tema.SUPERFICIE)
        textos.pack(side="left", fill="x", expand=True)
        self.lbl_lector_detalle = etiqueta(
            textos,
            "",
            fuente=tema_fuente_pequena(textos),
            color=tema.TEXTO_SUAVE,
            fondo=tema.SUPERFICIE,
            wraplength=520,
            justify="left",
        )
        self.lbl_lector_detalle.pack(anchor="w")
        self.lbl_lector_dispositivos = etiqueta(
            textos,
            "",
            fuente=tema_fuente_micro(textos),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
            wraplength=500,
            justify="left",
        )
        self.lbl_lector_dispositivos.pack(anchor="w", pady=(3, 0))

        pie = tk.Frame(contenido, bg=tema.SUPERFICIE)
        pie.pack(fill="x", pady=(10, 0))
        self.lbl_lector_modo = etiqueta(
            pie,
            "",
            fuente=tema_fuente_micro(pie),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
        )
        self.lbl_lector_modo.pack(side="left")
        Boton(
            pie,
            "Volver a detectar",
            self.app._solicitar_redeteccion,
            variante="secundario",
            ancho=142,
            alto=32,
            fuente=tema_fuente_pequena(pie),
            fondo=tema.SUPERFICIE,
            takefocus=False,
        ).pack(side="right")
        Boton(
            pie,
            "Configurar",
            self.app.abrir_panel_admin,
            variante="fantasma",
            ancho=100,
            alto=32,
            fuente=tema_fuente_pequena(pie),
            fondo=tema.SUPERFICIE,
            takefocus=False,
        ).pack(side="right", padx=(0, 4))

    def _dibujar_icono_lector(self, color: str) -> None:
        c = self._icono_lector
        c.delete("all")
        c.create_rectangle(
            10, 10, 40, 28, outline=color, width=2, fill=""
        )
        c.create_line(15, 28, 15, 39, fill=color, width=2)
        c.create_line(35, 28, 35, 39, fill=color, width=2)
        c.create_line(21, 15, 21, 23, fill=color, width=2)
        c.create_line(27, 15, 27, 23, fill=color, width=2)
        c.create_line(33, 15, 33, 23, fill=color, width=2)
        c.create_oval(23, 32, 29, 38, outline=color, width=2)

    def _construir_tarjeta_calibracion(self) -> None:
        contenido = self.tarjeta_calibracion.contenido
        cabecera = encabezado_tarjeta(
            contenido,
            "3 · Prueba de calibración",
            "Escanea un producto del catálogo. Sin esta prueba no se habilita el registro.",
            fondo=tema.SUPERFICIE,
            derecha_texto="PENDIENTE",
            derecha_estado="advertencia",
        )
        cabecera.pack(fill="x")
        self.pildora_calibracion = cabecera.pildora_derecha
        self.entrada_calibracion = EntradaEscaneo(
            contenido,
            self._procesar_calibracion,
            fondo=tema.SUPERFICIE,
            borde=tema.CARAMELO,
            placeholder="Escanea el producto de prueba…",
            texto_deshabilitado="La calibración se habilitará cuando el catálogo esté listo",
            habilitado=False,
        )
        self.entrada_calibracion.pack(fill="x", pady=(14, 10))
        self.banner_calibracion = BannerEstado(contenido, fondo=tema.SUPERFICIE)
        self.banner_calibracion.pack(fill="x")

        acciones = tk.Frame(contenido, bg=tema.SUPERFICIE)
        acciones.pack(fill="x", pady=(13, 0))
        self.boton_iniciar = Boton(
            acciones,
            "Comenzar registro",
            self._iniciar_registro,
            variante="exito",
            icono="→",
            ancho=250,
            alto=48,
            fondo=tema.SUPERFICIE,
        )
        self.boton_iniciar.pack(side="right")
        self.boton_iniciar.configurar_estado("deshabilitado")
        self.acciones_izquierda = tk.Frame(acciones, bg=tema.SUPERFICIE)
        self.acciones_izquierda.pack(side="left", fill="x", expand=True)
        self.lbl_calibracion_ayuda = etiqueta(
            self.acciones_izquierda,
            "La calibración se conserva mientras el catálogo y el lector no cambien.",
            fuente=tema_fuente_micro(self.acciones_izquierda),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
            wraplength=380,
            justify="left",
        )
        self.lbl_calibracion_ayuda.pack(side="left")
        self.boton_repetir = Boton(
            self.acciones_izquierda,
            "Repetir prueba",
            self._repetir_calibracion,
            variante="secundario",
            ancho=138,
            alto=38,
            fuente=tema_fuente_pequena(self.acciones_izquierda),
            fondo=tema.SUPERFICIE,
        )

    def _construir_franja_flujo(self, raiz: tk.Frame) -> None:
        franja = tk.Frame(
            raiz,
            bg=tema.SUPERFICIE,
            highlightbackground=tema.BORDE_SUAVE,
            highlightthickness=1,
        )
        franja.pack(fill="x", pady=(15, 0))
        for columna in range(3):
            franja.grid_columnconfigure(columna, weight=1, uniform="flujo")
        pasos = [
            ("01", "ESCANEA", "Un producto por lectura, sin escribir."),
            ("02", "VALIDA", "Cada código contra el catálogo maestro."),
            ("03", "CIERRA", "Excel, TXT y reporte visual con tu nombre."),
        ]
        for indice, (numero, titulo, detalle) in enumerate(pasos):
            celda = tk.Frame(franja, bg=tema.SUPERFICIE)
            celda.grid(
                row=0,
                column=indice,
                sticky="nsew",
                padx=(16 if indice == 0 else 10, 15),
                pady=10,
            )
            etiqueta(
                celda,
                numero,
                fuente=tema_fuente_micro(celda),
                color=tema.CARAMELO,
                fondo=tema.SUPERFICIE,
            ).pack(anchor="w")
            fila = tk.Frame(celda, bg=tema.SUPERFICIE)
            fila.pack(anchor="w")
            etiqueta(
                fila,
                titulo,
                fuente=tema_fuente_pequena(fila),
                color=tema.TEXTO,
                fondo=tema.SUPERFICIE,
            ).pack(side="left")
            etiqueta(
                fila,
                "· " + detalle,
                fuente=tema_fuente_micro(fila),
                color=tema.MUTED,
                fondo=tema.SUPERFICIE,
            ).pack(side="left", padx=(5, 0))

    def _render_catalogo(self) -> None:
        for hijo in self._cuerpo_catalogo.winfo_children():
            hijo.destroy()
        self._cuerpo_catalogo.pack(fill="x")
        contenido = self._cuerpo_catalogo
        maestro = self.app.maestro
        error = self.app.error_maestro
        pendiente = self.app.sesion_pendiente
        if maestro is not None:
            texto_pildora = (
                "CATÁLOGO DE SESIÓN" if self.app.catalogo_es_instantanea else (
                    "DEMOSTRACIÓN" if maestro.es_demo else "CATÁLOGO VIGENTE"
                )
            )
            encabezado_tarjeta(
                contenido,
                "1 · Archivo maestro",
                "La fuente de verdad de códigos y descripciones.",
                fondo=tema.SUPERFICIE,
                derecha_texto=texto_pildora,
                derecha_estado="advertencia" if (maestro.es_demo or self.app.catalogo_es_instantanea) else "ok",
            ).pack(fill="x")
            fila = tk.Frame(contenido, bg=tema.SUPERFICIE)
            fila.pack(fill="x", pady=(12, 0))
            icono = tk.Canvas(
                fila,
                width=48,
                height=54,
                bg=tema.SUPERFICIE,
                highlightthickness=0,
                bd=0,
            )
            icono.pack(side="left", padx=(0, 10))
            icono.create_polygon(
                9, 3, 33, 3, 44, 14, 44, 51, 9, 51, fill=tema.SUPERFICIE_3,
                outline=tema.CARAMELO, width=1,
            )
            icono.create_polygon(33, 3, 33, 14, 44, 14, fill=tema.CARAMELO_OSCURO, outline=tema.CARAMELO)
            icono.create_line(15, 25, 37, 25, fill=tema.MUTED, width=2)
            icono.create_line(15, 31, 37, 31, fill=tema.MUTED, width=2)
            icono.create_line(15, 37, 29, 37, fill=tema.MUTED, width=2)
            textos = tk.Frame(fila, bg=tema.SUPERFICIE)
            textos.pack(side="left", fill="x", expand=True)
            etiqueta(
                textos,
                truncar(maestro.nombre, 42),
                fuente=tema_fuente_cuerpo_fuerte(textos),
                color=tema.TEXTO,
                fondo=tema.SUPERFICIE,
            ).pack(anchor="w")
            etiqueta(
                textos,
                f"{maestro.total} productos · {len(maestro.columnas)} columnas · "
                f"{maestro.formato}",
                fuente=tema_fuente_micro(textos),
                color=tema.MUTED,
                fondo=tema.SUPERFICIE,
            ).pack(anchor="w", pady=(2, 0))
            etiqueta(
                textos,
                truncar(str(maestro.ruta), 52),
                fuente=tema_fuente_micro(textos),
                color=tema.MUTED,
                fondo=tema.SUPERFICIE,
            ).pack(anchor="w", pady=(1, 0))

            detalles = tk.Frame(contenido, bg=tema.SUPERFICIE)
            detalles.pack(fill="x", pady=(10, 0))
            for rotulo, valor in [
                ("COLUMNA CÓDIGO", maestro.columna_codigo),
                ("COLUMNA DESCRIPCIÓN", maestro.columna_descripcion),
            ]:
                caja = tk.Frame(
                    detalles,
                    bg=tema.SUPERFICIE_2,
                    highlightbackground=tema.BORDE_SUAVE,
                    highlightthickness=1,
                )
                caja.pack(side="left", fill="x", expand=True, padx=(0, 6))
                etiqueta(
                    caja,
                    rotulo,
                    fuente=tema_fuente_micro(caja),
                    color=tema.MUTED,
                    fondo=tema.SUPERFICIE_2,
                ).pack(anchor="w", padx=8, pady=(5, 0))
                etiqueta(
                    caja,
                    truncar(valor, 28),
                    fuente=tema_fuente_micro(caja),
                    color=tema.CARAMELO_CLARO,
                    fondo=tema.SUPERFICIE_2,
                ).pack(anchor="w", padx=8, pady=(0, 5))

            if maestro.advertencias:
                etiqueta(
                    contenido,
                    "⚠ " + truncar(maestro.advertencias[0], 140),
                    fuente=tema_fuente_micro(contenido),
                    color=tema.AMBAR,
                    fondo=tema.SUPERFICIE,
                    wraplength=370,
                    justify="left",
                ).pack(anchor="w", pady=(9, 0))
            if maestro.es_demo:
                etiqueta(
                    contenido,
                    "Archivo de demostración. Reemplázalo por el catálogo real "
                    "antes de operar la bodega.",
                    fuente=tema_fuente_micro(contenido),
                    color=tema.AMBAR_CLARO,
                    fondo=tema.SUPERFICIE,
                    wraplength=370,
                    justify="left",
                ).pack(anchor="w", pady=(8, 0))

            acciones = tk.Frame(contenido, bg=tema.SUPERFICIE)
            acciones.pack(fill="x", pady=(12, 0))
            boton_actualizar = Boton(
                acciones,
                "Actualizar archivo",
                lambda: self.app.recargar_catalogo(mostrar_aviso=True),
                variante="secundario",
                ancho=160,
                alto=38,
                fuente=tema_fuente_pequena(acciones),
                fondo=tema.SUPERFICIE,
                takefocus=False,
            )
            boton_actualizar.pack(side="left")
            if pendiente is not None:
                boton_actualizar.configurar_estado("deshabilitado")
                etiqueta(
                    acciones,
                    "Bloqueado por la sesión pendiente",
                    fuente=tema_fuente_micro(acciones),
                    color=tema.MUTED,
                    fondo=tema.SUPERFICIE,
                ).pack(side="left", padx=(10, 0))
            Boton(
                acciones,
                "Abrir carpeta",
                lambda: self._abrir_carpeta(self.app.rutas.maestra),
                variante="fantasma",
                ancho=124,
                alto=38,
                fuente=tema_fuente_pequena(acciones),
                fondo=tema.SUPERFICIE,
                takefocus=False,
            ).pack(side="right")
            self._actualizar_pildora_catalogo(maestro)
        else:
            encabezado_tarjeta(
                contenido,
                "1 · Archivo maestro",
                "La fuente de verdad de códigos y descripciones.",
                fondo=tema.SUPERFICIE,
                derecha_texto="REQUERIDO",
                derecha_estado="error",
            ).pack(fill="x")
            etiqueta(
                contenido,
                "No hay un catálogo válido",
                fuente=tema_fuente_cuerpo_fuerte(contenido),
                color=tema.TEXTO,
                fondo=tema.SUPERFICIE,
            ).pack(anchor="w", pady=(14, 4))
            etiqueta(
                contenido,
                error or "Descarga el archivo maestro en la carpeta indicada.",
                fuente=tema_fuente_pequena(contenido),
                color=tema.ROJO_CLARO,
                fondo=tema.SUPERFICIE,
                wraplength=520,
                justify="left",
            ).pack(anchor="w")
            acciones = tk.Frame(contenido, bg=tema.SUPERFICIE)
            acciones.pack(fill="x", pady=(14, 0))
            Boton(
                acciones,
                "Actualizar archivo",
                lambda: self.app.recargar_catalogo(mostrar_aviso=True),
                variante="primario",
                ancho=166,
                alto=38,
                fuente=tema_fuente_pequena(acciones),
                fondo=tema.SUPERFICIE,
                takefocus=False,
            ).pack(side="left")
            Boton(
                acciones,
                "Abrir carpeta",
                lambda: self._abrir_carpeta(self.app.rutas.maestra),
                variante="fantasma",
                ancho=124,
                alto=38,
                fuente=tema_fuente_pequena(acciones),
                fondo=tema.SUPERFICIE,
                takefocus=False,
            ).pack(side="right")

    def _actualizar_pildora_catalogo(self, maestro) -> None:
        # La píldora se recrea en cada render; este método existe para futuras
        # actualizaciones sin reconstruir la tarjeta.
        return

    def _render_contexto(self) -> None:
        for hijo in self.tarjeta_contexto.contenido.winfo_children():
            hijo.destroy()
        contenido = self.tarjeta_contexto.contenido
        pendiente = self.app.sesion_pendiente
        if pendiente is not None:
            self.tarjeta_contexto._borde_original = "#6B4B0B"
            self.tarjeta_contexto.configure(
                highlightbackground="#6B4B0B", highlightcolor="#6B4B0B"
            )
            encabezado_tarjeta(
                contenido,
                "Sesión pendiente",
                "Tus registros guardados te esperan.",
                fondo=tema.SUPERFICIE,
            ).pack(fill="x")
            estadisticas = self.app.inventario.estadisticas(pendiente.id)
            caja = tk.Frame(contenido, bg=tema.AMBAR_FONDO, highlightbackground="#6B4B0B", highlightthickness=1)
            caja.pack(fill="x", pady=(11, 0))
            etiqueta(
                caja,
                f"Abierta el {formatear_fecha_hora(pendiente.inicio_en)}",
                fuente=tema_fuente_micro(caja),
                color=tema.AMBAR_CLARO,
                fondo=tema.AMBAR_FONDO,
            ).pack(anchor="w", padx=10, pady=(7, 0))
            etiqueta(
                caja,
                f"{estadisticas.registrados} productos registrados · "
                f"{estadisticas.duplicados + estadisticas.no_encontrados} incidencias",
                fuente=tema_fuente_pequena(caja),
                color=tema.TEXTO,
                fondo=tema.AMBAR_FONDO,
            ).pack(anchor="w", padx=10, pady=(2, 5))
            etiqueta(
                caja,
                "Se reanudará con la copia original del catálogo para conservar "
                "la consistencia. Realiza de nuevo la calibración.",
                fuente=tema_fuente_micro(caja),
                color=tema.AMBAR_CLARO,
                fondo=tema.AMBAR_FONDO,
                wraplength=500,
                justify="left",
            ).pack(anchor="w", padx=10, pady=(0, 8))
            etiqueta(
                contenido,
                "Al reanudar, el botón verde dirá «Reanudar registro».",
                fuente=tema_fuente_micro(contenido),
                color=tema.CARAMELO,
                fondo=tema.SUPERFICIE,
                wraplength=500,
                justify="left",
            ).pack(anchor="w", pady=(9, 0))
        else:
            self.tarjeta_contexto._borde_original = tema.BORDE
            self.tarjeta_contexto.configure(
                highlightbackground=tema.BORDE, highlightcolor=tema.BORDE
            )
            encabezado_tarjeta(
                contenido,
                "Buenas prácticas",
                "Una estación lista evita reprocesos.",
                fondo=tema.SUPERFICIE,
            ).pack(fill="x")
            for titulo, texto in [
                ("Catálogo correcto", "Verifica el nombre y la fecha del archivo maestro."),
                ("Lector en modo HID", "Windows no distingue un HID genérico; la lectura lo valida."),
                ("Una prueba, un match", "Escanea un código que exista en el catálogo."),
            ]:
                fila = tk.Frame(contenido, bg=tema.SUPERFICIE)
                fila.pack(fill="x", pady=(8, 0))
                tk.Frame(fila, bg=tema.CARAMELO, width=3, height=26).pack(side="left", padx=(0, 8))
                textos = tk.Frame(fila, bg=tema.SUPERFICIE)
                textos.pack(side="left", fill="x", expand=True)
                etiqueta(
                    textos,
                    titulo,
                    fuente=tema_fuente_micro(textos),
                    color=tema.TEXTO,
                    fondo=tema.SUPERFICIE,
                ).pack(anchor="w")
                etiqueta(
                    textos,
                    texto,
                    fuente=tema_fuente_micro(textos),
                    color=tema.MUTED,
                    fondo=tema.SUPERFICIE,
                    wraplength=490,
                    justify="left",
                ).pack(anchor="w")

    # ------------------------------------------------------------------
    # Estado visual
    # ------------------------------------------------------------------
    def _actualizar_lector_visual(self) -> None:
        estado = self._estado_lector
        estilo = {
            "activo": ("ACTIVO", "ok", tema.VERDE),
            "conectado": ("CONECTADO", "info", tema.AZUL),
            "pendiente": ("HID EN ESPERA", "advertencia", tema.AMBAR),
            "desconectado": ("DESCONECTADO", "error", tema.ROJO),
        }.get(estado.estado, ("PENDIENTE", "advertencia", tema.AMBAR))
        self.pildora_lector.actualizar(estilo[0], estilo[1])
        self.lbl_lector_detalle.configure(text=estado.detalle)
        self.lbl_lector_modo.configure(
            text=(
                f"MODO {estado.modo}"
                + (f" · {estado.puerto}" if estado.puerto else "")
                + " · DETECCIÓN AUTOMÁTICA"
            )
        )
        if estado.dispositivos:
            dispositivos = " · ".join(estado.dispositivos[:2])
            if len(estado.dispositivos) > 2:
                dispositivos += f" · +{len(estado.dispositivos) - 2}"
            self.lbl_lector_dispositivos.configure(text=f"Detectado: {dispositivos}")
        elif estado.modo == "SERIAL":
            self.lbl_lector_dispositivos.configure(
                text="Puertos disponibles: "
                + (", ".join(p for p, _ in self.app.puertos_disponibles()) or "ninguno")
            )
        else:
            self.lbl_lector_dispositivos.configure(
                text="Lector HID genérico: la primera lectura confirma el dispositivo."
            )
        self._dibujar_icono_lector(estilo[2])
        try:
            self.tarjeta_lector.configure(
                highlightbackground=estilo[2],
                highlightcolor=estilo[2],
            )
            self.tarjeta_lector._borde_original = estilo[2]
        except tk.TclError:
            pass

    def _actualizar_calibracion_visual(
        self, *, conservar_mensaje: bool = False
    ) -> None:
        maestro_ok = self.app.maestro is not None and self.app.error_maestro is None
        lector = self._estado_lector
        if self.app.calibrado:
            self.pildora_calibracion.actualizar("SINCRONIZADO", "ok")
            self.banner_calibracion.mostrar(
                "Prueba Match Sincronización OK",
                "El lector y el archivo maestro están sincronizados. "
                "Ya puedes comenzar a registrar productos.",
                "ok",
            )
            self.entrada_calibracion.configurar_texto_deshabilitado(
                "Calibración completada. Usa «Repetir prueba» si cambias de equipo."
            )
            self.entrada_calibracion.habilitar(False)
            self.entrada_calibracion.configure(
                highlightbackground=tema.VERDE, highlightcolor=tema.VERDE
            )
            self.boton_iniciar.configurar_estado("normal")
            self.boton_iniciar.configurar_texto(
                "Reanudar registro"
                if self.app.sesion_pendiente is not None
                else "Comenzar registro",
                icono="→",
            )
            if self.lbl_calibracion_ayuda.winfo_ismapped():
                self.lbl_calibracion_ayuda.pack_forget()
            if not self.boton_repetir.winfo_ismapped():
                self.boton_repetir.pack(side="left")
            self.tarjeta_calibracion.configure(
                highlightbackground=tema.VERDE, highlightcolor=tema.VERDE
            )
            self.tarjeta_calibracion._borde_original = tema.VERDE
            return

        self.boton_iniciar.configurar_estado("deshabilitado")
        self.boton_iniciar.configurar_texto(
            "Reanudar registro"
            if self.app.sesion_pendiente is not None
            else "Comenzar registro",
            icono="→",
        )
        if self.boton_repetir.winfo_ismapped():
            self.boton_repetir.pack_forget()
        if not self.lbl_calibracion_ayuda.winfo_ismapped():
            self.lbl_calibracion_ayuda.pack(side="left")
        self.entrada_calibracion.configure(
            highlightbackground=tema.CARAMELO, highlightcolor=tema.CARAMELO
        )
        self.tarjeta_calibracion.configure(
            highlightbackground=tema.BORDE, highlightcolor=tema.BORDE
        )
        self.tarjeta_calibracion._borde_original = tema.BORDE
        self.entrada_calibracion.configurar_texto_deshabilitado(
            "La calibración se habilitará cuando el catálogo esté listo"
        )

        if not maestro_ok:
            self.pildora_calibracion.actualizar("BLOQUEADA", "error")
            self.entrada_calibracion.habilitar(False)
            if not conservar_mensaje:
                self.banner_calibracion.mostrar(
                    "Primero necesitas un catálogo",
                    "Carga un archivo maestro válido en C:\\dulcesito_castillo "
                    "y pulsa «Actualizar archivo».",
                    "error",
                )
            return
        if lector.estado == "desconectado":
            self.pildora_calibracion.actualizar("LECTOR DESCONECTADO", "error")
            self.entrada_calibracion.habilitar(False)
            if not conservar_mensaje:
                self.banner_calibracion.mostrar(
                    "El lector no responde",
                    "Conecta el lector USB, usa «Volver a detectar» y realiza la "
                    "prueba de calibración.",
                    "error",
                )
            return
        self.pildora_calibracion.actualizar("PENDIENTE", "advertencia")
        self.entrada_calibracion.configurar_texto_deshabilitado(
            "Escanea el producto de prueba para calibrar"
        )
        self.entrada_calibracion.habilitar(True)
        if not conservar_mensaje:
            if lector.estado == "pendiente":
                self.banner_calibracion.mostrar(
                    "Lector HID en espera",
                    "Escanea un producto. La lectura confirma el lector y valida "
                    "la sincronización con el catálogo.",
                    "advertencia",
                )
            else:
                self.banner_calibracion.mostrar(
                    "Listo para la prueba",
                    "Escanea un producto del archivo maestro. Si coincide, verás "
                    "«Prueba Match Sincronización OK».",
                    "info",
                )
        self.entrada_calibracion.enfocar()

    def _actualizar_stepper(self) -> None:
        catalogo = self.app.maestro is not None and self.app.error_maestro is None
        lector = self._estado_lector.estado in {"conectado", "activo"}
        calibrado = self.app.calibrado
        estados = ["pendiente", "pendiente", "pendiente"]
        if catalogo:
            estados[0] = "completado"
        if lector:
            estados[1] = "completado"
        if calibrado:
            estados[2] = "completado"
        activo = 0 if not catalogo else (1 if not lector else 2)
        if calibrado:
            activo = 2
        self.stepper.actualizar(estados, activo)

    def actualizar_lector(self, estado: EstadoLector) -> None:
        self._estado_lector = estado
        self._actualizar_lector_visual()
        if not self.app.calibrado:
            self._actualizar_calibracion_visual()
        else:
            # La lectura y el catálogo siguen sincronizados; solo refrescamos
            # indicadores sin borrar el mensaje de éxito.
            self.pildora_lector.actualizar(
                "ACTIVO" if estado.estado == "activo" else estado.etiqueta,
                "ok" if estado.estado == "activo" else "advertencia",
            )
        self._actualizar_stepper()

    def perder_calibracion(self, mensaje: str) -> None:
        self.app.calibrado = False
        self._actualizar_calibracion_visual(conservar_mensaje=True)
        self.banner_calibracion.mostrar(
            "Calibración invalidada",
            mensaje,
            "error",
        )
        self.pildora_calibracion.actualizar("PENDIENTE", "error")
        self._actualizar_stepper()

    def refrescar_catalogo(self) -> None:
        if hasattr(self, "_cuerpo_catalogo"):
            self._render_catalogo()
            self._render_contexto()
        self._actualizar_calibracion_visual()
        self._actualizar_stepper()

    def mostrar_aviso(self, mensaje: str, estado: str = "info") -> None:
        self.aviso_temporal.mostrar(
            "Actualización" if estado == "ok" else "Atención",
            mensaje,
            estado,
        )
        if not self.aviso_temporal.winfo_ismapped():
            self.aviso_temporal.pack(fill="x", pady=(0, 10), before=self.stepper)
        self.after(5500, self._ocultar_aviso)

    def _ocultar_aviso(self) -> None:
        try:
            if self.aviso_temporal.winfo_ismapped():
                self.aviso_temporal.pack_forget()
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # Acciones
    # ------------------------------------------------------------------
    def _procesar_calibracion(self, codigo: str) -> None:
        self._procesar_codigo(codigo, origen="hid")

    def recibir_lectura_serial(self, codigo: str) -> None:
        self._procesar_codigo(codigo, origen="serial")

    def _procesar_codigo(self, codigo: str, *, origen: str) -> None:
        codigo = codigo.strip()
        if not codigo:
            return
        self.aviso_temporal.pack_forget()
        if origen == "hid":
            self.app.notificar_lectura_hid(codigo)
            self._estado_lector = self.app.estado_lector
            self._actualizar_lector_visual()
        if self.app.maestro is None:
            self.app.sonidos.error()
            self.banner_calibracion.mostrar(
                "Catálogo no disponible",
                "No hay un archivo maestro válido para contrastar el código.",
                "error",
            )
            self.entrada_calibracion.marcar_estado("error")
            return
        if self._estado_lector.estado == "desconectado":
            self.app.sonidos.error()
            self.banner_calibracion.mostrar(
                "Lector desconectado",
                "Conecta el lector USB y vuelve a detectarlo antes de calibrar.",
                "error",
            )
            return
        coincidencia = self.app.maestro.buscar(codigo)
        if coincidencia is None:
            self.app.sonidos.error()
            self.app.invalidar_calibracion()
            self.entrada_calibracion.marcar_estado("error")
            self.banner_calibracion.mostrar(
                "Código sin coincidencia",
                f"«{truncar(codigo, 48)}» no existe en el archivo maestro. "
                "Verifica el producto o actualiza el catálogo.",
                "error",
            )
            self.pildora_calibracion.actualizar("SIN COINCIDENCIA", "error")
            self._actualizar_stepper()
            return

        self.app.calibrado = True
        self.app.codigo_calibracion = coincidencia.codigo
        self.app.lector.marcar_activo(coincidencia.codigo)
        self.app.estado_lector = self.app.lector.estado_actual()
        self.app._actualizar_indicador_lector()
        self._estado_lector = self.app.estado_lector
        self.app.sonidos.calibracion()
        self.entrada_calibracion.marcar_estado("ok")
        self._actualizar_lector_visual()
        self._actualizar_calibracion_visual()
        self._actualizar_stepper()

    def _repetir_calibracion(self) -> None:
        self.app.invalidar_calibracion()
        self._estado_lector = self.app.lector.estado_actual()
        self._actualizar_calibracion_visual()
        self._actualizar_stepper()
        self.entrada_calibracion.enfocar()

    def _iniciar_registro(self) -> None:
        if self.app.calibrado:
            self.app.iniciar_registro(self.app.codigo_calibracion)

    def _abrir_carpeta(self, ruta) -> None:
        if not abrir_carpeta(ruta):
            self.app.mostrar_error(
                "No se pudo abrir la carpeta",
                f"Windows no pudo abrir:\n{ruta}",
            )

    def _enfocar_escaner(self) -> None:
        if self.entrada_calibracion._habilitado:
            self.entrada_calibracion.enfocar()

    def _tecla_f2(self, _evento: tk.Event) -> str:
        if self.app.grab_current() is None:
            self._enfocar_escaner()
        return "break"

    def _al_destruir(self, evento: tk.Event) -> None:
        if evento.widget is not self:
            return
        if self._bind_f2:
            try:
                self.winfo_toplevel().unbind("<F2>", self._bind_f2)
            except tk.TclError:
                pass
