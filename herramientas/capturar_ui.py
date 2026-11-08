"""Capturas de interfaz para revisión visual y documentación.

Uso:
    python herramientas/capturar_ui.py setup
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("DULCESITOS_SIN_SONIDO", "1")

from PIL import ImageGrab

from dulcesitos.archivo_maestro import cargar_maestro_actual
from dulcesitos.base_datos import BaseDatos
from dulcesitos.config import preparar_rutas
from dulcesitos.servicios import (
    ServicioAdministracion,
    ServicioAutenticacion,
)
from dulcesitos.ui.aplicacion import Aplicacion

BASE = Path(os.environ.get("DELCE_CAPTURA_DIR", tempfile.mkdtemp(prefix="delce_ui_")))
os.environ["DULCESITOS_MAESTRO_DIR"] = str(BASE / "maestro")
os.environ["DULCESITOS_DATA_DIR"] = str(BASE / "datos")
CAPTURAS = RAIZ / "docs" / "capturas"
CAPTURAS.mkdir(parents=True, exist_ok=True)

modo = sys.argv[1] if len(sys.argv) > 1 else "setup"
GEOMETRIA = os.environ.get("DELCE_GEOMETRY", "").strip()


def ajustar_geometria(app) -> None:
    if GEOMETRIA:
        app.geometry(GEOMETRIA)
        app.update_idletasks()
        app.update()


def preparar() -> tuple:
    rutas = preparar_rutas()
    shutil.copy2(
        RAIZ / "datos_ejemplo" / "DEMO_maestro_dulcesitos.xlsx",
        rutas.maestra / "DEMO_maestro_dulcesitos.xlsx",
    )
    db = BaseDatos(rutas.base_datos)
    return rutas, db


def sembrar(db, rutas):
    auth = ServicioAutenticacion(db)
    if auth.requiere_configuracion():
        auth.crear_administrador_inicial(
            nombre="Carlos Castillo",
            cedula="1020304050",
            correo="admin@dulcesitos.local",
            clave="Cacao2026Seguro",
            confirmacion="Cacao2026Seguro",
        )
    admin = auth.autenticar_administrador("1020304050", "Cacao2026Seguro")
    admin_svc = ServicioAdministracion(db)
    existente = db.operador_por_cedula("1098765432")
    if existente is None:
        emitido = admin_svc.emitir_codigo(
            admin=admin,
            dias_vigencia=30,
            nombre="María Fernanda Gómez",
            cedula="1098765432",
            correo="maria.gomez@dulcesitos.local",
        )
        operador = auth.registrar_operador(
            nombre="María Fernanda Gómez",
            cedula="1098765432",
            correo="maria.gomez@dulcesitos.local",
            codigo=emitido.codigo,
        )
    else:
        emitido = admin_svc.emitir_codigo(
            admin=admin,
            dias_vigencia=30,
            operador_id=existente.id,
        )
        operador = auth.iniciar_sesion_operador("1098765432", emitido.codigo)
    return auth, admin, admin_svc, operador


def capturar_ventana(ventana, nombre: str, demora: float = 1.0):
    ventana.update_idletasks()
    ventana.update()
    time.sleep(demora)
    ventana.lift()
    ventana.attributes("-topmost", True)
    ventana.update()
    time.sleep(0.3)
    x = ventana.winfo_rootx()
    y = ventana.winfo_rooty()
    w = ventana.winfo_width()
    h = ventana.winfo_height()
    destino = CAPTURAS / f"{nombre}.png"
    ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True).save(destino)
    print(f"Captura: {destino} ({w}x{h})")
    return destino


def capturar(app: Aplicacion, nombre: str, demora: float = 1.2) -> None:
    app.update_idletasks()
    app.update()
    time.sleep(demora)
    app.update()
    app.lift()
    app.attributes("-topmost", True)
    app.update()
    time.sleep(0.4)
    x = app.winfo_rootx()
    y = app.winfo_rooty()
    w = app.winfo_width()
    h = app.winfo_height()
    destino = CAPTURAS / f"{nombre}.png"
    imagen = ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True)
    imagen.save(destino)
    print(f"Captura: {destino} ({imagen.width}x{imagen.height})")
    print(f"Ventana: {w}x{h} en {x},{y}; root: {app.winfo_screenwidth()}x{app.winfo_screenheight()}")


if modo == "setup":
    rutas, db = preparar()
    app = Aplicacion(rutas, db, iniciar_lector=False)
    ajustar_geometria(app)
    capturar(app, "01_configuracion_inicial")
    app._cerrando = True
    app.destroy()
elif modo == "login":
    rutas, db = preparar()
    sembrar(db, rutas)
    app = Aplicacion(rutas, db, iniciar_lector=False)
    ajustar_geometria(app)
    capturar(app, "02_ingreso")
    app._cerrando = True
    app.destroy()
elif modo == "estacion":
    rutas, db = preparar()
    auth, admin, admin_svc, operador = sembrar(db, rutas)
    app = Aplicacion(rutas, db, iniciar_lector=False)
    app.operador = operador
    app.iniciar_sesion_operador(operador)
    ajustar_geometria(app)
    capturar(app, "03_estacion")
    app._cerrando = True
    app.destroy()
elif modo == "registro":
    rutas, db = preparar()
    auth, admin, admin_svc, operador = sembrar(db, rutas)
    maestro = cargar_maestro_actual(rutas.maestra)
    app = Aplicacion(rutas, db, iniciar_lector=False)
    app.operador = operador
    pendiente = app.inventario.sesion_abierta(operador.operador_id)
    if pendiente:
        app.sesion = pendiente
        app.sesion_pendiente = None
        app.maestro = app.inventario.cargar_maestro_sesion(pendiente)
    else:
        app.maestro = maestro
        app.calibrado = True
        app.codigo_calibracion = maestro.registros[0].codigo
        app.sesion = app.inventario.iniciar_sesion(
            operador, maestro, maestro.registros[0].codigo
        )
    app.calibrado = True
    for i in range(3):
        app.inventario.procesar_escaneo(app.sesion, app.maestro, maestro.registros[i].codigo)
    app.inventario.procesar_escaneo(app.sesion, app.maestro, maestro.registros[0].codigo)
    app.inventario.procesar_escaneo(app.sesion, app.maestro, "9999999999999")
    if maestro.columna_stock:
        from dulcesitos.archivo_maestro import convertir_numero

        registros = app.inventario.registros_sesion(app.sesion.id)
        objetivo = registros[-1] if registros else None
        original = (
            convertir_numero(objetivo.campos.get(maestro.columna_stock, ""))
            if objetivo is not None
            else None
        )
        if original is not None:
            app.inventario.ajustar_stock(
                sesion=app.sesion,
                maestro=maestro,
                registro=objetivo,
                stock_nuevo=original - 2,
                operador=operador,
            )
    while not app._cola_lector.empty():
        try:
            app._cola_lector.get_nowait()
        except Exception:
            break
    app.estado_lector = app.lector.estado_actual().__class__(
        estado="activo",
        modo="HID",
        puerto="",
        detalle="Lector USB HID validado por lectura. Captura funcionando.",
        dispositivos=("Lector de códigos USB",),
        identificado=True,
        validado_por_lectura=True,
    )
    app._actualizar_indicador_lector()
    from dulcesitos.ui.pantalla_registro import PantallaRegistro

    app._cambiar_pantalla(PantallaRegistro, mensaje_inicial="Sesión iniciada correctamente.")
    app._pantalla_actual.after(50, lambda: app._pantalla_actual.actualizar_lector(app.estado_lector))
    ajustar_geometria(app)
    capturar(app, "04_registro")
    app._cerrando = True
    app.destroy()
elif modo == "registro_form":
    rutas, db = preparar()
    sembrar(db, rutas)
    app = Aplicacion(rutas, db, iniciar_lector=False)
    app._pantalla_actual._cambiar_modo("registro")
    ajustar_geometria(app)
    capturar(app, "02b_activar_codigo")
    app._cerrando = True
    app.destroy()
elif modo == "estacion_ok":
    rutas, db = preparar()
    auth, admin, admin_svc, operador = sembrar(db, rutas)
    app = Aplicacion(rutas, db, iniciar_lector=False)
    app.operador = operador
    app.iniciar_sesion_operador(operador)
    while not app._cola_lector.empty():
        try:
            app._cola_lector.get_nowait()
        except Exception:
            break
    app.estado_lector = app.lector.estado_actual().__class__(
        estado="activo",
        modo="HID",
        puerto="",
        detalle="Lector USB detectado: Lector de códigos USB · calibración vigente",
        dispositivos=("Lector de códigos USB",),
        identificado=True,
        validado_por_lectura=True,
    )
    app._actualizar_indicador_lector()
    maestro = cargar_maestro_actual(rutas.maestra)
    app.maestro = maestro
    app.calibrado = True
    app.codigo_calibracion = maestro.registros[0].codigo
    app._pantalla_actual.actualizar_lector(app.estado_lector)
    app._pantalla_actual._actualizar_calibracion_visual()
    app._pantalla_actual._actualizar_stepper()
    capturar(app, "03b_calibracion_ok")
    app._cerrando = True
    app.destroy()
elif modo == "admin_login":
    rutas, db = preparar()
    sembrar(db, rutas)
    app = Aplicacion(rutas, db, iniciar_lector=False)
    from dulcesitos.ui.panel_admin import PanelAdministracion

    panel = PanelAdministracion(app, app)
    panel.mostrar()
    panel.update_idletasks()
    panel.update()
    time.sleep(1)
    panel.lift()
    panel.attributes("-topmost", True)
    panel.update()
    time.sleep(0.3)
    x, y = panel.winfo_rootx(), panel.winfo_rooty()
    w, h = panel.winfo_width(), panel.winfo_height()
    destino = CAPTURAS / "05a_admin_login.png"
    ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True).save(destino)
    print(f"Captura: {destino} ({w}x{h})")
    panel._cerrando = True
    app._panel_admin = None
    panel.destroy()
    app._cerrando = True
    app.destroy()
elif modo in {"admin_lector", "admin_operadores", "admin_historial", "admin_catalogo"}:
    rutas, db = preparar()
    auth, admin, admin_svc, operador = sembrar(db, rutas)
    app = Aplicacion(rutas, db, iniciar_lector=False)
    if modo == "admin_catalogo":
        from dulcesitos.catalogo import ServicioCatalogo

        catalogo = ServicioCatalogo(db)
        maestro = cargar_maestro_actual(rutas.maestra)
        catalogo.crear_producto(
            admin=admin,
            maestro=maestro,
            codigo="7709999000123",
            descripcion="Dulce de temporada",
            campos={"Categoría": "Dulces", "Precio": "4800", "Stock": "18"},
        )
        catalogo.dar_de_baja(
            admin=admin,
            maestro=maestro,
            codigo=maestro.registros[2].codigo,
            motivo="Producto descontinuado",
        )
    from dulcesitos.ui.panel_admin import PanelAdministracion

    panel = PanelAdministracion(app, app)
    panel.admin = auth.autenticar_administrador("1020304050", "Cacao2026Seguro")
    panel._construir_panel()
    panel._mostrar_seccion(modo.replace("admin_", ""))
    panel.mostrar()
    panel.update_idletasks()
    panel.update()
    time.sleep(1)
    panel.lift()
    panel.attributes("-topmost", True)
    panel.update()
    time.sleep(0.3)
    x, y = panel.winfo_rootx(), panel.winfo_rooty()
    w, h = panel.winfo_width(), panel.winfo_height()
    destino = CAPTURAS / f"05_{modo}.png"
    ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True).save(destino)
    print(f"Captura: {destino} ({w}x{h})")
    panel._cerrando = True
    app._panel_admin = None
    panel.destroy()
    app._cerrando = True
    app.destroy()
elif modo == "generar_codigo":
    rutas, db = preparar()
    auth, admin, admin_svc, operador = sembrar(db, rutas)
    app = Aplicacion(rutas, db, iniciar_lector=False)
    from dulcesitos.ui.panel_admin import DialogoGenerarCodigo

    dialogo = DialogoGenerarCodigo(app, app=app, admin=admin)
    dialogo.mostrar()
    capturar_ventana(dialogo, "07_generar_codigo")
    dialogo.cerrar()
    app._cerrando = True
    app.destroy()
elif modo == "generar_codigo_asignado":
    rutas, db = preparar()
    auth, admin, admin_svc, operador = sembrar(db, rutas)
    app = Aplicacion(rutas, db, iniciar_lector=False)
    from dulcesitos.ui.panel_admin import DialogoGenerarCodigo

    dialogo = DialogoGenerarCodigo(app, app=app, admin=admin)
    dialogo._cambiar_modo("asignado")
    dialogo.mostrar()
    capturar_ventana(dialogo, "07b_generar_codigo_asignado")
    dialogo.cerrar()
    app._cerrando = True
    app.destroy()
elif modo == "codigo_generado":
    rutas, db = preparar()
    auth, admin, admin_svc, operador = sembrar(db, rutas)
    emitido = admin_svc.emitir_codigo(
        admin=admin, dias_vigencia=7, nombre="Andrés Felipe Rojas",
        cedula="1032456789", correo="andres@dulcesitos.local"
    )
    app = Aplicacion(rutas, db, iniciar_lector=False)
    from dulcesitos.ui.dialogos import DialogoCodigoGenerado

    dialogo = DialogoCodigoGenerado(
        app,
        codigo=emitido.codigo,
        asignado_a=emitido.asignado_a,
        expira_en=emitido.expira_en,
        tipo=emitido.tipo,
    )
    dialogo.mostrar()
    capturar_ventana(dialogo, "08_codigo_generado")
    dialogo.cerrar()
    app._cerrando = True
    app.destroy()
elif modo == "autorizacion":
    rutas, db = preparar()
    auth, admin, admin_svc, operador = sembrar(db, rutas)
    maestro = cargar_maestro_actual(rutas.maestra)
    app = Aplicacion(rutas, db, iniciar_lector=False)
    app.operador = operador
    app.sesion = app.inventario.iniciar_sesion(
        operador, maestro, maestro.registros[0].codigo
    )
    app.maestro = maestro
    app.calibrado = True
    for i in range(3):
        app.inventario.procesar_escaneo(app.sesion, maestro, maestro.registros[i].codigo)
    from dulcesitos.ui.dialogos import DialogoAutorizacionCierre

    dialogo = DialogoAutorizacionCierre(
        app,
        operador=operador,
        estadisticas=app.inventario.estadisticas(app.sesion.id),
        sesion_id=app.sesion.id,
        al_autorizar=lambda n, c: auth.autorizar_cierre(operador, nombre_confirmado=n, clave=c),
    )
    dialogo.mostrar()
    capturar_ventana(dialogo, "09_autorizacion_cierre")
    dialogo.cerrar()
    app._cerrando = True
    app.destroy()
elif modo == "manual":
    rutas, db = preparar()
    auth, admin, admin_svc, operador = sembrar(db, rutas)
    maestro = cargar_maestro_actual(rutas.maestra)
    app = Aplicacion(rutas, db, iniciar_lector=False)
    app.operador = operador
    app.maestro = maestro
    app.sesion = app.inventario.iniciar_sesion(
        operador, maestro, maestro.registros[0].codigo
    )
    app.inventario.procesar_escaneo(
        app.sesion, maestro, maestro.registros[0].codigo
    )
    from dulcesitos.ui.dialogos import DialogoRegistroManual

    dialogo = DialogoRegistroManual(
        app,
        servicio=app.inventario,
        sesion=app.sesion,
        maestro=maestro,
        operador=operador,
    )
    dialogo.mostrar()
    dialogo.codigo.variable.set("SIN-CODIGO-ETIQUETA")
    dialogo.descripcion.variable.set("Chocolatina Castillo doble")
    dialogo.novedad.variable.set(
        "Etiqueta deteriorada: el lector no detecta el código y no hay "
        "coincidencia en el Excel."
    )
    if dialogo.stock is not None:
        dialogo.stock.variable.set("176")
    dialogo.update_idletasks()
    dialogo.update()
    capturar_ventana(dialogo, "06_registro_manual")
    dialogo.cerrar()
    app._cerrando = True
    app.destroy()
elif modo == "cierre":
    rutas, db = preparar()
    auth, admin, admin_svc, operador = sembrar(db, rutas)
    maestro = cargar_maestro_actual(rutas.maestra)
    app = Aplicacion(rutas, db, iniciar_lector=False)
    app.operador = operador
    app.maestro = maestro
    app.sesion = app.inventario.iniciar_sesion(
        operador, maestro, maestro.registros[0].codigo
    )
    for i in range(7):
        app.inventario.procesar_escaneo(app.sesion, maestro, maestro.registros[i].codigo)
    app.inventario.procesar_escaneo(app.sesion, maestro, maestro.registros[0].codigo)
    app.inventario.procesar_escaneo(app.sesion, maestro, "0000000000000")
    autorizacion = auth.autorizar_cierre(
        operador,
        nombre_confirmado=operador.nombre,
        clave="Cacao2026Seguro",
    )
    final, archivos = app.inventario.finalizar_sesion(
        sesion=app.sesion,
        operador=operador,
        autorizacion=autorizacion,
        maestro=maestro,
    )
    app.sesion = final
    from dulcesitos.ui.pantalla_cierre import PantallaCierre

    app._cambiar_pantalla(PantallaCierre, sesion=final, archivos=archivos, operador=operador)
    ajustar_geometria(app)
    capturar(app, "10_cierre")
    app._cerrando = True
    app.destroy()
elif modo == "admin":
    rutas, db = preparar()
    auth, admin, admin_svc, operador = sembrar(db, rutas)
    extra = admin_svc.emitir_codigo(
        admin=admin,
        dias_vigencia=12,
        nombre="Andrés Felipe Rojas",
        cedula="1032456789",
        correo="andres@dulcesitos.local",
    )
    libre = admin_svc.emitir_codigo(
        admin=admin,
        dias_vigencia=4,
    )
    app = Aplicacion(rutas, db, iniciar_lector=False)
    from dulcesitos.ui.panel_admin import PanelAdministracion

    panel = PanelAdministracion(app, app)
    panel.admin = auth.autenticar_administrador("1020304050", "Cacao2026Seguro")
    panel._construir_panel()
    if GEOMETRIA:
        panel.geometry(GEOMETRIA)
    panel.mostrar()
    panel.update_idletasks()
    panel.update()
    time.sleep(1)
    panel.lift()
    panel.attributes("-topmost", True)
    panel.update()
    time.sleep(0.3)
    x, y = panel.winfo_rootx(), panel.winfo_rooty()
    w, h = panel.winfo_width(), panel.winfo_height()
    destino = CAPTURAS / "05_admin.png"
    ImageGrab.grab(bbox=(x, y, x + w, y + h), all_screens=True).save(destino)
    print(f"Captura: {destino} ({w}x{h})")
    panel._cerrando = True
    app._panel_admin = None
    panel.destroy()
    app._cerrando = True
    app.destroy()
else:
    raise SystemExit(f"Modo desconocido: {modo}")
