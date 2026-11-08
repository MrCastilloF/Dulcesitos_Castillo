"""Punto de entrada de Dulcesitos Castillo · Operador de Inventarios."""

from __future__ import annotations

import logging
import platform
import sys
import tempfile
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dulcesitos.base_datos import BaseDatos
from dulcesitos.config import (
    APP_NAME,
    APP_VERSION,
    ErrorRutas,
    configurar_dpi,
    preparar_rutas,
)
from dulcesitos.ui.aplicacion import Aplicacion


def configurar_registro(rutas) -> None:
    carpeta_logs = rutas.datos / "logs"
    try:
        carpeta_logs.mkdir(parents=True, exist_ok=True)
        manejador = RotatingFileHandler(
            carpeta_logs / "aplicacion.log",
            maxBytes=1_500_000,
            backupCount=3,
            encoding="utf-8",
        )
        formato = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        manejador.setFormatter(formato)
        raiz = logging.getLogger()
        raiz.setLevel(logging.INFO)
        raiz.addHandler(manejador)
        # La consola también es útil al ejecutar desde código fuente.
        consola = logging.StreamHandler()
        consola.setFormatter(formato)
        raiz.addHandler(consola)
    except OSError:
        logging.basicConfig(level=logging.INFO)


def diagnosticar(rutas) -> int:
    """Autodiagnóstico útil para soporte y para validar el ejecutable."""

    lineas: list[str] = []
    errores: list[str] = []
    avisos: list[str] = []
    lineas.append(f"{APP_NAME} · v{APP_VERSION}")
    lineas.append(f"Windows: {platform.platform()}")
    lineas.append(f"Python: {sys.version.split()[0]} ({platform.architecture()[0]})")
    lineas.append(f"Carpeta maestra: {rutas.maestra}")
    lineas.append(f"Carpeta de datos: {rutas.datos}")
    lineas.append("")

    def probar(nombre: str, funcion) -> None:
        try:
            resultado = funcion()
            lineas.append(f"[OK]   {nombre}{': ' + str(resultado) if resultado else ''}")
        except Exception as exc:  # el diagnóstico debe continuar ante cualquier fallo
            errores.append(f"{nombre}: {exc}")
            lineas.append(f"[FALLA] {nombre}: {exc}")

    def comprobar_tk():
        import tkinter

        return f"Tk {tkinter.TkVersion}"

    def comprobar_openpyxl():
        import openpyxl

        return f"openpyxl {openpyxl.__version__}"

    def comprobar_reportlab():
        import reportlab

        return f"reportlab {reportlab.Version}"

    def comprobar_pdfplumber():
        import pdfplumber

        return f"pdfplumber {pdfplumber.__version__}"

    def comprobar_pyserial():
        import serial

        return f"pyserial {serial.__version__}"

    def comprobar_xlrd():
        import xlrd

        return f"xlrd {xlrd.__version__}"

    def comprobar_archivo_maestro():
        from dulcesitos.archivo_maestro import descubrir_archivos

        archivos = descubrir_archivos(rutas.maestra)
        if not archivos:
            avisos.append("No hay archivo maestro en la carpeta contractual.")
            return "sin archivo maestro"
        return f"{len(archivos)} archivo(s); se usaría {archivos[0].name}"

    def comprobar_generacion():
        import pdfplumber
        from openpyxl import Workbook, load_workbook
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

        with tempfile.TemporaryDirectory(prefix="diagnostico_", dir=str(rutas.datos)) as tmp:
            tmp_path = Path(tmp)
            xlsx = tmp_path / "prueba.xlsx"
            libro = Workbook()
            hoja = libro.active
            hoja.append(["Código de barras", "Descripción"])
            hoja.append(["00123", "Producto de prueba"])
            libro.save(xlsx)
            leido = load_workbook(xlsx, read_only=True, data_only=True)
            assert leido.active["A2"].value == "00123"
            leido.close()

            pdf = tmp_path / "prueba.pdf"
            doc = SimpleDocTemplate(str(pdf), pagesize=A4)
            tabla = Table(
                [
                    ["Código", "Descripción"],
                    ["00123", "Producto de prueba"],
                ]
            )
            tabla.setStyle(
                TableStyle(
                    [("GRID", (0, 0), (-1, -1), 0.5, colors.grey)]
                )
            )
            doc.build([tabla])
            with pdfplumber.open(pdf) as documento:
                texto = " ".join(
                    pagina.extract_text() or "" for pagina in documento.pages
                )
            assert "Producto de prueba" in texto
        return "PDF y XLSX generados y releídos"

    def comprobar_base():
        base = BaseDatos(rutas.base_datos)
        integridad, detalle = base.verificar_integridad()
        base.cerrar()
        if not integridad:
            raise RuntimeError(detalle)
        return "SQLite íntegra"

    probar("Tkinter", comprobar_tk)
    probar("openpyxl", comprobar_openpyxl)
    probar("ReportLab", comprobar_reportlab)
    probar("pdfplumber", comprobar_pdfplumber)
    probar("pyserial", comprobar_pyserial)
    probar("xlrd", comprobar_xlrd)
    probar("Base de datos", comprobar_base)
    probar("Generación y lectura de archivos", comprobar_generacion)
    probar("Archivo maestro", comprobar_archivo_maestro)

    try:
        from dulcesitos.lector import _ruta_powershell, puertos_seriales

        ps = _ruta_powershell()
        lineas.append(f"[OK]   PowerShell: {ps or 'no disponible (la lectura HID funciona)'}")
        lineas.append(
            "[OK]   Puertos serie: "
            + (
                ", ".join(puerto for puerto, _ in puertos_seriales())
                or "ninguno detectado"
            )
        )
    except Exception as exc:
        avisos.append(f"Lector: {exc}")
        lineas.append(f"[AVISO] Lector: {exc}")

    lineas.append("")
    for aviso in avisos:
        lineas.append(f"[AVISO] {aviso}")
    lineas.append("")
    if errores:
        lineas.append(f"RESULTADO: {len(errores)} error(es). Revisa los detalles.")
    else:
        lineas.append("RESULTADO: DIAGNÓSTICO CORRECTO.")
    texto = "\n".join(lineas) + "\n"
    destino = rutas.datos / "diagnostico.txt"
    try:
        destino.write_text(texto, encoding="utf-8")
    except OSError:
        pass
    print(texto)
    return 1 if errores else 0


def _mostrar_error_arranque(titulo: str, mensaje: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox

        raiz = tk.Tk()
        raiz.withdraw()
        messagebox.showerror(f"{APP_NAME} · {titulo}", mensaje)
        raiz.destroy()
    except Exception:
        print(f"{APP_NAME} · {titulo}\n{mensaje}", file=sys.stderr)


def main() -> int:
    configurar_dpi()
    try:
        rutas = preparar_rutas()
    except ErrorRutas as exc:
        _mostrar_error_arranque("No se pudo iniciar", str(exc))
        return 2
    configurar_registro(rutas)
    if "--diagnostico" in sys.argv:
        return diagnosticar(rutas)
    if "--version" in sys.argv:
        print(f"{APP_NAME} v{APP_VERSION}")
        return 0
    logging.getLogger(__name__).info(
        "Iniciando %s v%s", APP_NAME, APP_VERSION
    )
    try:
        db = BaseDatos(rutas.base_datos)
    except Exception as exc:
        _mostrar_error_arranque(
            "Base de datos local",
            "No fue posible abrir la base de datos de la aplicación.\n\n"
            f"{exc}\n\n"
            "Revisa los permisos de la carpeta de datos o restaura un respaldo.",
        )
        return 3
    integridad, detalle = db.verificar_integridad()
    if not integridad:
        db.cerrar()
        _mostrar_error_arranque(
            "Base de datos local",
            "La verificación de integridad de la base de datos falló.\n\n"
            f"{detalle}\n\n"
            "No se abrirá la aplicación para evitar pérdida de información. "
            "Restaura el último respaldo desde la carpeta de datos.",
        )
        return 4
    try:
        app = Aplicacion(rutas, db)
        app.mainloop()
    except Exception as exc:
        logging.getLogger(__name__).exception("Fallo fatal de la aplicación")
        _mostrar_error_arranque(
            "Error inesperado",
            "La aplicación se cerró por un error inesperado.\n\n"
            f"{exc}\n\n"
            "El detalle quedó registrado en la carpeta de logs.",
        )
        return 5
    finally:
        try:
            db.cerrar()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
