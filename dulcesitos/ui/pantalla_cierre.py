"""Pantalla posterior al cierre: inventario visual y archivos generados."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path

from ..config import APP_AUTHOR, APP_NAME, APP_VERSION
from ..modelos import ArchivoGenerado, Sesion, SesionOperador
from ..utilidades import (
    abrir_archivo,
    abrir_carpeta,
    formatear_fecha_hora,
    formatear_hora,
    formatear_tamano,
    imprimir_archivo,
    truncar,
)
from . import tema
from .componentes import (
    Boton,
    MarcoDesplazable,
    TablaDatos,
    Tarjeta,
    TarjetaMetrica,
    encabezado_tarjeta,
    etiqueta,
    separador,
)
from .pantalla_acceso import (
    tema_fuente_micro,
    tema_fuente_pequena,
    tema_fuente_titulo,
)


class PantallaCierre(tk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        app,
        *,
        sesion: Sesion,
        archivos: list[ArchivoGenerado],
        operador: SesionOperador | None,
    ):
        super().__init__(master, bg=tema.FONDO)
        self.app = app
        self.sesion = sesion
        self.archivos = archivos
        self.operador = operador or app.operador
        self._construir()

    def _construir(self) -> None:
        scroll = MarcoDesplazable(self, fondo=tema.FONDO, expandir_alto=True)
        scroll.pack(fill="both", expand=True)
        raiz = tk.Frame(scroll.interior, bg=tema.FONDO)
        raiz.pack(fill="both", expand=True, padx=28, pady=(16, 22))

        self._construir_cabecera(raiz)
        self._construir_metricas(raiz)

        cuerpo = tk.Frame(raiz, bg=tema.FONDO)
        cuerpo.pack(fill="both", expand=True, pady=(13, 0))
        cuerpo.grid_columnconfigure(0, weight=3, uniform="cierre")
        cuerpo.grid_columnconfigure(1, weight=2, uniform="cierre")

        izquierda = tk.Frame(cuerpo, bg=tema.FONDO)
        izquierda.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        derecha = tk.Frame(cuerpo, bg=tema.FONDO)
        derecha.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        self._construir_archivos(izquierda)
        self._construir_tabla(izquierda)
        self._construir_resumen(derecha)

        pie = tk.Frame(raiz, bg=tema.FONDO)
        pie.pack(fill="x", pady=(16, 0))
        etiqueta(
            pie,
            f"{APP_NAME} · v{APP_VERSION} · {APP_AUTHOR}",
            fuente=tema_fuente_micro(pie),
            color=tema.MUTED,
            fondo=tema.FONDO,
        ).pack(side="left")
        etiqueta(
            pie,
            "Los archivos se generaron en C:\\dulcesito_castillo\\salidas",
            fuente=tema_fuente_micro(pie),
            color=tema.MUTED,
            fondo=tema.FONDO,
        ).pack(side="right")

    def _construir_cabecera(self, raiz: tk.Frame) -> None:
        fila = tk.Frame(raiz, bg=tema.FONDO)
        fila.pack(fill="x")
        icono = tk.Canvas(fila, width=64, height=64, bg=tema.FONDO, highlightthickness=0, bd=0)
        icono.pack(side="left", padx=(0, 15))
        icono.create_oval(2, 2, 62, 62, fill=tema.VERDE_FONDO, outline="#1F6650", width=2)
        icono.create_text(32, 34, text="✓", fill=tema.VERDE, font=("Segoe UI", 27, "bold"))
        textos = tk.Frame(fila, bg=tema.FONDO)
        textos.pack(side="left", fill="x", expand=True)
        etiqueta(
            textos,
            "PROCESO FINALIZADO",
            fuente=tema_fuente_micro(textos),
            color=tema.VERDE,
            fondo=tema.FONDO,
        ).pack(anchor="w")
        etiqueta(
            textos,
            "Registro terminado.",
            fuente=tema_fuente_titulo(textos),
            color=tema.TEXTO,
            fondo=tema.FONDO,
        ).pack(anchor="w", pady=(1, 2))
        etiqueta(
            textos,
            "La sesión quedó cerrada y los archivos de actualización están listos. "
            "El archivo maestro original no fue modificado.",
            fuente=tema_fuente_pequena(textos),
            color=tema.MUTED,
            fondo=tema.FONDO,
            wraplength=900,
            justify="left",
        ).pack(anchor="w")

        acciones = tk.Frame(fila, bg=tema.FONDO)
        acciones.pack(side="right", padx=(14, 0))
        Boton(
            acciones,
            "Cerrar sesión",
            self.app._solicitar_cierre_sesion,
            variante="secundario",
            ancho=142,
            alto=40,
            fuente=tema_fuente_pequena(acciones),
            fondo=tema.FONDO,
        ).pack(side="right", padx=(8, 0))
        Boton(
            acciones,
            "Nueva sesión",
            self.app.nueva_sesion,
            variante="primario",
            icono="↻",
            ancho=170,
            alto=40,
            fuente=tema_fuente_pequena(acciones),
            fondo=tema.FONDO,
        ).pack(side="right")

    def _construir_metricas(self, raiz: tk.Frame) -> None:
        try:
            estadisticas = self.app.inventario.estadisticas(self.sesion.id)
        except Exception:
            from ..modelos import EstadisticasSesion

            estadisticas = EstadisticasSesion()
        fila = tk.Frame(raiz, bg=tema.FONDO)
        fila.pack(fill="x", pady=(13, 0))
        for indice in range(4):
            fila.grid_columnconfigure(indice, weight=1, uniform="cierre_metricas")
        tarjetas = [
            ("Registrados", estadisticas.registrados, tema.VERDE),
            ("Duplicados", estadisticas.duplicados, tema.CARAMELO),
            ("No encontrados", estadisticas.no_encontrados, tema.ROJO),
            ("Lecturas totales", estadisticas.total_lecturas, tema.AZUL),
        ]
        for indice, (titulo, valor, color) in enumerate(tarjetas):
            tarjeta = TarjetaMetrica(fila, titulo, valor, color=color, compacta=True)
            tarjeta.grid(
                row=0,
                column=indice,
                sticky="ew",
                padx=(0 if indice == 0 else 5, 0 if indice == 3 else 5),
            )

    def _construir_archivos(self, padre: tk.Frame) -> None:
        tarjeta = Tarjeta(padre, padding=17, acento=tema.VERDE)
        tarjeta.pack(fill="x")
        contenido = tarjeta.contenido
        encabezado_tarjeta(
            contenido,
            "Archivos de actualización",
            "Tres salidas nuevas para revisar, imprimir o integrar.",
            fondo=tema.SUPERFICIE,
            derecha_texto=f"{len(self.archivos)} ARCHIVOS",
            derecha_estado="ok",
        ).pack(fill="x")
        for archivo in sorted(self.archivos, key=lambda a: {"pdf": 0, "xlsx": 1, "txt": 2}.get(a.tipo, 3)):
            self._fila_archivo(contenido, archivo).pack(fill="x", pady=(9, 0))
        acciones = tk.Frame(contenido, bg=tema.SUPERFICIE)
        acciones.pack(fill="x", pady=(12, 0))
        Boton(
            acciones,
            "Abrir carpeta de salidas",
            lambda: self._abrir_carpeta(self.app.rutas.salidas),
            variante="secundario",
            ancho=200,
            alto=38,
            fuente=tema_fuente_pequena(acciones),
            fondo=tema.SUPERFICIE,
        ).pack(side="left")
        etiqueta(
            acciones,
            "Los archivos conservan las columnas originales del catálogo.",
            fuente=tema_fuente_micro(acciones),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
        ).pack(side="right")

    def _fila_archivo(self, padre: tk.Frame, archivo: ArchivoGenerado) -> tk.Frame:
        detalle = {
            "xlsx": ("XLSX", tema.VERDE, "Libro de actualización"),
            "pdf": ("PDF", tema.ROJO, "Reporte visual imprimible"),
            "txt": ("TXT", tema.AZUL, "Texto delimitado"),
        }
        sigla, color, descripcion = detalle.get(
            archivo.tipo, ("FILE", tema.MUTED, "Archivo generado")
        )
        fila = tk.Frame(
            padre,
            bg=tema.SUPERFICIE_2,
            highlightbackground=tema.BORDE_SUAVE,
            highlightthickness=1,
        )
        chip = tk.Frame(fila, bg=color, width=56, height=46)
        chip.pack(side="left", padx=(10, 10), pady=8)
        chip.pack_propagate(False)
        etiqueta(
            chip,
            sigla,
            fuente=tema_fuente_micro(chip),
            color=tema.NEGRO,
            fondo=color,
            anchor="center",
        ).pack(fill="both", expand=True)
        textos = tk.Frame(fila, bg=tema.SUPERFICIE_2)
        textos.pack(side="left", fill="x", expand=True)
        etiqueta(
            textos,
            descripcion,
            fuente=tema_fuente_pequena(textos),
            color=tema.TEXTO,
            fondo=tema.SUPERFICIE_2,
        ).pack(anchor="w")
        etiqueta(
            textos,
            truncar(archivo.ruta.name, 70),
            fuente=tema_fuente_micro(textos),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE_2,
        ).pack(anchor="w")
        etiqueta(
            textos,
            formatear_tamano(archivo.tamano_bytes),
            fuente=tema_fuente_micro(textos),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE_2,
        ).pack(anchor="w")
        Boton(
            fila,
            "Abrir",
            lambda ruta=archivo.ruta: self._abrir_archivo(ruta),
            variante="fantasma",
            ancho=72,
            alto=32,
            fuente=tema_fuente_pequena(fila),
            fondo=tema.SUPERFICIE_2,
            takefocus=False,
        ).pack(side="right", padx=(4, 8))
        if archivo.tipo == "pdf":
            Boton(
                fila,
                "Imprimir",
                lambda ruta=archivo.ruta: self._imprimir(ruta),
                variante="fantasma",
                ancho=86,
                alto=32,
                fuente=tema_fuente_pequena(fila),
                fondo=tema.SUPERFICIE_2,
                takefocus=False,
            ).pack(side="right")
        return fila

    def _construir_tabla(self, padre: tk.Frame) -> None:
        tarjeta = Tarjeta(padre, padding=13)
        tarjeta.pack(fill="both", expand=True, pady=(12, 0))
        contenido = tarjeta.contenido
        try:
            registros = self.app.inventario.registros_sesion(self.sesion.id)
        except Exception:
            registros = []
        encabezado_tarjeta(
            contenido,
            "Inventario visual de la sesión",
            f"{len(registros)} productos quedaron registrados.",
            fondo=tema.SUPERFICIE,
            derecha_texto="SESIÓN CERRADA",
            derecha_estado="ok",
        ).pack(fill="x", pady=(0, 8))
        tabla = TablaDatos(
            contenido,
            [
                ("codigo", "Código", 150, "w"),
                ("descripcion", "Descripción", 380, "w"),
                ("hora", "Hora", 90, "center"),
            ],
            alto=6,
            fondo=tema.SUPERFICIE,
            mensaje_vacio="No hay productos en esta sesión.",
            autoseleccionar=False,
        )
        tabla.pack(fill="both", expand=True)
        tabla.aplicar_etiquetas(
            {
                "impar": {"background": tema.SUPERFICIE},
                "par": {"background": "#1A120F"},
            }
        )
        filas = []
        for indice, registro in enumerate(reversed(registros)):
            filas.append(
                {
                    "codigo": registro.codigo,
                    "descripcion": truncar(registro.descripcion, 66),
                    "hora": formatear_hora(registro.escaneado_en),
                    "_tags": ("par" if indice % 2 else "impar",),
                }
            )
        tabla.cargar(filas)

    def _construir_resumen(self, padre: tk.Frame) -> None:
        tarjeta = Tarjeta(padre, padding=18, acento=tema.CARAMELO)
        tarjeta.pack(fill="x")
        contenido = tarjeta.contenido
        encabezado_tarjeta(
            contenido,
            "Acta de la sesión",
            "Datos de trazabilidad y autorización.",
            fondo=tema.SUPERFICIE,
        ).pack(fill="x")
        datos = [
            ("OPERADOR", self.operador.nombre if self.operador else self.sesion.operador_nombre),
            ("CÉDULA", self.operador.cedula if self.operador else self.sesion.operador_cedula),
            ("SESIÓN", f"#{self.sesion.id}"),
            ("INICIO", formatear_fecha_hora(self.sesion.inicio_en)),
            ("CIERRE", formatear_fecha_hora(self.sesion.fin_en)),
            ("AUTORIZACIÓN", self.sesion.autorizado_por or "—"),
            ("MÉTODO", "Clave de operador" if self.sesion.metodo_autorizacion == "operador" else "Clave de administración"),
            ("ARCHIVO MAESTRO", self.sesion.maestro_nombre),
            ("HUELLA SHA-256", self.sesion.maestro_hash[:28] + "…"),
        ]
        for rotulo, valor in datos:
            fila = tk.Frame(contenido, bg=tema.SUPERFICIE)
            fila.pack(fill="x", pady=3)
            etiqueta(
                fila,
                rotulo,
                fuente=tema_fuente_micro(fila),
                color=tema.MUTED,
                fondo=tema.SUPERFICIE,
            ).pack(side="left", anchor="n")
            etiqueta(
                fila,
                truncar(str(valor), 48),
                fuente=tema_fuente_micro(fila),
                color=tema.TEXTO_SUAVE,
                fondo=tema.SUPERFICIE,
                wraplength=260,
                justify="right",
                anchor="e",
            ).pack(side="right", anchor="e")

        separador(contenido, tema.BORDE, 1).pack(fill="x", pady=(12, 11))
        etiqueta(
            contenido,
            "El reporte PDF incluye el resumen, la tabla completa y el bloque de firmas.",
            fuente=tema_fuente_micro(contenido),
            color=tema.MUTED,
            fondo=tema.SUPERFICIE,
            wraplength=420,
            justify="left",
        ).pack(anchor="w")
        pdf = next((a for a in self.archivos if a.tipo == "pdf"), None)
        if pdf is not None:
            Boton(
                contenido,
                "Abrir reporte PDF",
                lambda: self._abrir_archivo(pdf.ruta),
                variante="exito",
                icono="↗",
                ancho=220,
                alto=42,
                fondo=tema.SUPERFICIE,
            ).pack(fill="x", pady=(12, 0))
            Boton(
                contenido,
                "Imprimir reporte",
                lambda: self._imprimir(pdf.ruta),
                variante="secundario",
                ancho=220,
                alto=38,
                fuente=tema_fuente_pequena(contenido),
                fondo=tema.SUPERFICIE,
            ).pack(fill="x", pady=(6, 0))

        acciones = tk.Frame(contenido, bg=tema.SUPERFICIE)
        acciones.pack(fill="x", pady=(16, 0))
        Boton(
            acciones,
            "Nueva sesión",
            self.app.nueva_sesion,
            variante="primario",
            icono="↻",
            ancho=160,
            alto=42,
            fondo=tema.SUPERFICIE,
        ).pack(fill="x")
        Boton(
            acciones,
            "Salir y cambiar de operador",
            self.app.cerrar_sesion_operador,
            variante="fantasma",
            ancho=200,
            alto=36,
            fuente=tema_fuente_pequena(acciones),
            fondo=tema.SUPERFICIE,
        ).pack(fill="x", pady=(4, 0))

    # ------------------------------------------------------------------
    # Acciones de archivos
    # ------------------------------------------------------------------
    def _abrir_archivo(self, ruta: Path) -> None:
        if not abrir_archivo(ruta):
            self.app.mostrar_error(
                "No se pudo abrir el archivo",
                f"Windows no pudo abrir:\n{ruta}\n\n"
                "Puedes abrirlo manualmente desde la carpeta de salidas.",
            )

    def _abrir_carpeta(self, ruta: Path) -> None:
        if not abrir_carpeta(ruta):
            self.app.mostrar_error(
                "No se pudo abrir la carpeta",
                f"Windows no pudo abrir:\n{ruta}",
            )

    def _imprimir(self, ruta: Path) -> None:
        if not imprimir_archivo(ruta):
            self._abrir_archivo(ruta)
