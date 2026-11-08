"""Prueba de humo de los diálogos críticos."""

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
BASE = Path(tempfile.mkdtemp(prefix="dulce_dialogos_"))
os.environ["DULCESITOS_MAESTRO_DIR"] = str(BASE / "maestro")
os.environ["DULCESITOS_DATA_DIR"] = str(BASE / "datos")

from dulcesitos.archivo_maestro import cargar_maestro_actual
from dulcesitos.base_datos import BaseDatos
from dulcesitos.config import preparar_rutas
from dulcesitos.servicios import ServicioAutenticacion
from dulcesitos.ui.aplicacion import Aplicacion
from dulcesitos.ui.dialogos import (
    DialogoAutorizacionCierre,
    DialogoCambiarClave,
    DialogoCodigoGenerado,
    DialogoProgreso,
)
from dulcesitos.ui.panel_admin import DialogoGenerarCodigo

rutas = preparar_rutas()
shutil.copy2(
    RAIZ / "datos_ejemplo" / "DEMO_maestro_dulcesitos.xlsx",
    rutas.maestra / "DEMO_maestro_dulcesitos.xlsx",
)
db = BaseDatos(rutas.base_datos)
auth = ServicioAutenticacion(db)
admin = auth.crear_administrador_inicial(
    nombre="Carlos Castillo",
    cedula="1020304050",
    correo="admin@dulcesitos.local",
    clave="Cacao2026Seguro",
    confirmacion="Cacao2026Seguro",
)
app = Aplicacion(rutas, db, iniciar_lector=False)
app.update_idletasks()
app.update()


def actualizar() -> None:
    for _ in range(4):
        app.update_idletasks()
        app.update()
        time.sleep(0.02)


# Invitación libre
dialogo = DialogoGenerarCodigo(app, app=app, admin=admin)
dialogo.mostrar()
actualizar()
dialogo.dias_var.set("5")
dialogo._actualizar_fecha()
dialogo._generar()
actualizar()
assert dialogo.resultado is not None
assert dialogo.resultado.codigo.startswith("DLC-")
print("✓ Generación de invitación libre:", dialogo.resultado.codigo)

# Invitación asignada
dialogo = DialogoGenerarCodigo(app, app=app, admin=admin)
dialogo.mostrar()
actualizar()
dialogo._cambiar_modo("asignado")
dialogo.asig_nombre.set("Andrés Felipe Rojas")
dialogo.asig_cedula.set("1032456789")
dialogo.asig_correo.set("andres@dulcesitos.local")
dialogo.dias_var.set("9")
dialogo._generar()
actualizar()
assert dialogo.resultado is not None
print("✓ Generación de invitación asignada")

# Renovación: registrar primero al operador asignado
emitido_asignado = dialogo.resultado
operador = auth.registrar_operador(
    nombre="Andrés Felipe Rojas",
    cedula="1032456789",
    correo="andres@dulcesitos.local",
    codigo=emitido_asignado.codigo,
)
dialogo = DialogoGenerarCodigo(
    app,
    app=app,
    admin=admin,
    operador_preseleccionado=operador.operador_id,
)
dialogo.mostrar()
actualizar()
dialogo.dias_var.set("12")
dialogo._generar()
actualizar()
assert dialogo.resultado is not None
assert dialogo.resultado.tipo == "renovacion"
print("✓ Renovación de operador")

# Diálogo de código generado
codigo_dialogo = DialogoCodigoGenerado(
    app,
    codigo=dialogo.resultado.codigo,
    asignado_a=dialogo.resultado.asignado_a,
    expira_en=dialogo.resultado.expira_en,
    tipo=dialogo.resultado.tipo,
)
codigo_dialogo.mostrar()
actualizar()
codigo_dialogo._copiar()
codigo_dialogo.cerrar()
print("✓ Diálogo de código generado y copia")

# Cambio de clave
nueva = "NuevaClave2027"
cambio = DialogoCambiarClave(
    app,
    al_cambiar=lambda actual, nueva_clave, confirmacion: auth.cambiar_clave_administrador(
        admin.id, actual, nueva_clave, confirmacion
    ),
)
cambio.mostrar()
actualizar()
cambio.actual.set("Cacao2026Seguro")
cambio.nueva.set(nueva)
cambio.confirmacion.set(nueva)
cambio._guardar()
actualizar()
assert cambio.resultado is True
print("✓ Cambio de clave de administrador")

# Sesión y autorización de cierre
maestro = cargar_maestro_actual(rutas.maestra)
app.operador = auth.iniciar_sesion_operador("1032456789", dialogo.resultado.codigo)
app.maestro = maestro
app.sesion = app.inventario.iniciar_sesion(
    app.operador, maestro, maestro.registros[0].codigo
)
for i in range(4):
    app.inventario.procesar_escaneo(app.sesion, maestro, maestro.registros[i].codigo)
autorizacion_dialogo = DialogoAutorizacionCierre(
    app,
    operador=app.operador,
    estadisticas=app.inventario.estadisticas(app.sesion.id),
    sesion_id=app.sesion.id,
    al_autorizar=lambda nombre, clave: auth.autorizar_cierre(
        app.operador, nombre_confirmado=nombre, clave=clave
    ),
)
autorizacion_dialogo.mostrar()
actualizar()
autorizacion_dialogo.campo_clave.set("ClaveIncorrecta999")
autorizacion_dialogo._autorizar()
actualizar()
assert autorizacion_dialogo.resultado is None
autorizacion_dialogo.campo_clave.set("NuevaClave2027")
autorizacion_dialogo._autorizar()
actualizar()
assert autorizacion_dialogo.resultado is not None
print("✓ Validación de clave incorrecta y autorización administrativa")

progreso = DialogoProgreso(app)
progreso.update()
progreso.cerrar()
print("✓ Diálogo de progreso")

app._cerrando = True
app.destroy()
db.cerrar()
print("PRUEBA DE DIÁLOGOS OK")
