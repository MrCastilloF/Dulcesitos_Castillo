"""Prueba de humo de la interfaz (sin interacción manual)."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ["DULCESITOS_SIN_SONIDO"] = "1"
BASE = Path(tempfile.mkdtemp(prefix="dulce_ui_"))
os.environ["DULCESITOS_MAESTRO_DIR"] = str(BASE / "maestro")
os.environ["DULCESITOS_DATA_DIR"] = str(BASE / "datos")

from dulcesitos.base_datos import BaseDatos
from dulcesitos.config import preparar_rutas
from dulcesitos.modelos import EstadoLector
from dulcesitos.servicios import ServicioAdministracion
from dulcesitos.ui.aplicacion import Aplicacion
from dulcesitos.ui.pantalla_acceso import PantallaAcceso, PantallaConfiguracionInicial
from dulcesitos.ui.pantalla_estacion import PantallaEstacion
from dulcesitos.ui.pantalla_registro import PantallaRegistro


def actualizar(app: Aplicacion) -> None:
    for _ in range(5):
        app.update_idletasks()
        app.update()
        time.sleep(0.03)


def forzar_lector(app: Aplicacion, estado: str = "activo") -> None:
    app.estado_lector = EstadoLector(
        estado=estado,
        modo="HID",
        puerto="",
        detalle="Lector simulado para prueba de interfaz.",
        dispositivos=("Lector de códigos USB",),
        identificado=True,
        validado_por_lectura=True,
    )
    app._actualizar_indicador_lector()
    if hasattr(app._pantalla_actual, "actualizar_lector"):
        app._pantalla_actual.actualizar_lector(app.estado_lector)


rutas = preparar_rutas()
shutil.copy2(
    RAIZ / "datos_ejemplo" / "DEMO_maestro_dulcesitos.xlsx",
    rutas.maestra / "DEMO_maestro_dulcesitos.xlsx",
)
db = BaseDatos(rutas.base_datos)
app = Aplicacion(rutas, db, iniciar_lector=False)
actualizar(app)
assert isinstance(app._pantalla_actual, PantallaConfiguracionInicial)
print("✓ Pantalla de configuración inicial")

pantalla = app._pantalla_actual
pantalla.nombre.set("Carlos Castillo")
pantalla.cedula.set("1020304050")
pantalla.correo.set("admin@dulcesitos.local")
pantalla.clave.set("Cacao2026Seguro")
pantalla.confirmacion.set("Cacao2026Seguro")
pantalla._crear()
actualizar(app)
assert isinstance(app._pantalla_actual, PantallaAcceso)
print("✓ Administrador creado desde la interfaz")

admin = app.auth.autenticar_administrador("1020304050", "Cacao2026Seguro")
admin_svc = ServicioAdministracion(db)
emitido = admin_svc.emitir_codigo(
    admin=admin,
    dias_vigencia=7,
    nombre="María Fernanda Gómez",
    cedula="1098765432",
    correo="maria.gomez@dulcesitos.local",
)
pantalla = app._pantalla_actual
pantalla._cambiar_modo("registro")
assert pantalla.selector.seleccion == "registro"
pantalla.reg_nombre.set("María Fernanda Gómez")
pantalla.reg_cedula.set("1098765432")
pantalla.reg_correo.set("maria.gomez@dulcesitos.local")
pantalla.reg_codigo.set(emitido.codigo)
pantalla._registrar()
actualizar(app)
assert isinstance(app._pantalla_actual, PantallaEstacion)
assert app.operador is not None
print("✓ Registro de operador y llegada a la estación")

forzar_lector(app)
pantalla = app._pantalla_actual
pantalla._procesar_codigo(app.maestro.registros[0].codigo, origen="hid")
actualizar(app)
assert app.calibrado is True
assert pantalla.banner_calibracion._estado == "ok"
pantalla._iniciar_registro()
actualizar(app)
assert isinstance(app._pantalla_actual, PantallaRegistro)
assert app.sesion is not None
print("✓ Calibración y apertura de sesión")

pantalla = app._pantalla_actual
pantalla._procesar_codigo(app.maestro.registros[0].codigo)
pantalla._procesar_codigo(app.maestro.registros[1].codigo)
pantalla._procesar_codigo(app.maestro.registros[0].codigo)
pantalla._procesar_codigo("NO-EXISTE-123")
actualizar(app)
stats = app.inventario.estadisticas(app.sesion.id)
assert stats.registrados == 2, stats
assert stats.duplicados == 1
assert stats.no_encontrados == 1
assert len(pantalla.tabla.arbol.get_children()) == 2
print("✓ Registro, duplicado y no encontrado en interfaz")

app.cerrar_sesion_operador()
actualizar(app)
assert isinstance(app._pantalla_actual, PantallaAcceso)
app.iniciar_sesion_operador(
    app.auth.iniciar_sesion_operador("1098765432", emitido.codigo)
)
actualizar(app)
assert app.sesion_pendiente is not None
assert app.maestro is not None
assert isinstance(app._pantalla_actual, PantallaEstacion)
forzar_lector(app)
pantalla = app._pantalla_actual
pantalla._procesar_codigo(app.maestro.registros[0].codigo, origen="hid")
pantalla._iniciar_registro()
actualizar(app)
assert isinstance(app._pantalla_actual, PantallaRegistro)
assert app.inventario.estadisticas(app.sesion.id).registrados == 2
print("✓ Sesión reanudada sin perder registros")

app.abrir_panel_admin()
actualizar(app)
panel = app._panel_admin
assert panel is not None
panel.cedula_admin.set("1020304050")
panel.clave_admin.set("Cacao2026Seguro")
panel._autenticar()
actualizar(app)
assert panel.admin is not None
assert panel._seccion_actual == "accesos"
for seccion in ("operadores", "catalogo", "lector", "historial"):
    panel._mostrar_seccion(seccion)
    actualizar(app)
print("✓ Panel administrativo y sus secciones")

# Escenario de catálogo: alta local, baja y reactivación desde los servicios.
from dulcesitos.catalogo import ServicioCatalogo

catalogo = ServicioCatalogo(db)
maestro_bruto = app.cargar_maestro_para_administracion()
nuevo = catalogo.crear_producto(
    admin=admin,
    maestro=maestro_bruto,
    codigo="7709999123456",
    descripcion="Dulce nuevo de temporada",
    campos={"Categoría": "Dulces", "Precio": "4500", "Stock": "20"},
)
assert app.catalogo.aplicar(maestro_bruto).buscar(nuevo.codigo) is not None
catalogo.dar_de_baja(
    admin=admin,
    maestro=maestro_bruto,
    codigo=nuevo.codigo,
    motivo="Prueba de baja",
)
assert app.catalogo.aplicar(maestro_bruto).buscar(nuevo.codigo) is None
catalogo.reactivar(admin=admin, maestro=maestro_bruto, codigo=nuevo.codigo)
assert app.catalogo.aplicar(maestro_bruto).buscar(nuevo.codigo) is not None
print("✓ Altas, bajas y reactivación de catálogo")

# Bloqueo de una sesión si se revoca el código del operador.
panel._mostrar_seccion("accesos")
actualizar(app)
app.administracion.revocar_operador(admin, app.operador.operador_id)
assert not app.auth.sesion_operador_vigente(app.operador)
print("✓ Revocación inmediata detectable por la sesión")
app._cerrando = True
panel._cerrando = True
panel.destroy()
app.destroy()
db.cerrar()
print("PRUEBA DE INTERFAZ OK")
