"""Prueba de humo integral sin interfaz gráfica."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

base = Path(tempfile.mkdtemp(prefix="delce_humo_"))
os.environ["DULCESITOS_MAESTRO_DIR"] = str(base / "maestro")
os.environ["DULCESITOS_DATA_DIR"] = str(base / "datos")

from dulcesitos.archivo_maestro import cargar_maestro_actual
from dulcesitos.base_datos import BaseDatos
from dulcesitos.config import preparar_rutas
from dulcesitos.servicios import (
    ServicioAdministracion,
    ServicioAutenticacion,
    ServicioInventario,
)

print("Base temporal:", base)
rutas = preparar_rutas()
shutil.copy2(RAIZ / "datos_ejemplo" / "DEMO_maestro_dulcesitos.xlsx", rutas.maestra / "DEMO_maestro_dulcesitos.xlsx")
maestro = cargar_maestro_actual(rutas.maestra)
print("Maestro:", maestro.nombre, maestro.total, maestro.columna_codigo, maestro.columna_descripcion)
assert maestro.total == 24, maestro.total
codigo_calibracion = maestro.registros[0].codigo
assert maestro.buscar(codigo_calibracion)
assert maestro.buscar("  " + codigo_calibracion.lower() + " ")

db = BaseDatos(rutas.base_datos)
auth = ServicioAutenticacion(db)
admin = auth.crear_administrador_inicial(
    nombre="Carlos Castillo",
    cedula="1020304050",
    correo="admin@dulcesitos.local",
    clave="Cacao2026Seguro",
    confirmacion="Cacao2026Seguro",
)
print("Admin:", admin)
assert auth.autenticar_administrador("1020304050", "Cacao2026Seguro")
admin = auth.autenticar_administrador("1020304050", "Cacao2026Seguro")
admin_svc = ServicioAdministracion(db)
emitido = admin_svc.emitir_codigo(
    admin=admin,
    dias_vigencia=7,
    nombre="María Fernanda Gómez",
    cedula="1098765432",
    correo="maria@dulcesitos.local",
)
print("Código:", emitido.codigo, emitido.expira_en)
sesion_op = auth.registrar_operador(
    nombre="María Fernanda Gómez",
    cedula="1098765432",
    correo="maria@dulcesitos.local",
    codigo=emitido.codigo,
)
print("Operador:", sesion_op)
assert auth.sesion_operador_vigente(sesion_op)
assert auth.iniciar_sesion_operador("1098765432", emitido.codigo)
assert auth.autorizar_cierre(sesion_op, nombre_confirmado="María Fernanda Gómez", clave=emitido.codigo).metodo == "operador"
assert auth.autorizar_cierre(sesion_op, nombre_confirmado="María Fernanda Gómez", clave="Cacao2026Seguro").metodo == "administrador"

inv = ServicioInventario(db, rutas)
sesion = inv.iniciar_sesion(sesion_op, maestro, codigo_calibracion)
print("Sesión:", sesion.id)
r1 = inv.procesar_escaneo(sesion, maestro, maestro.registros[0].codigo)
assert r1.estado == "registrado", r1
r2 = inv.procesar_escaneo(sesion, maestro, maestro.registros[1].codigo)
assert r2.estado == "registrado", r2
r3 = inv.procesar_escaneo(sesion, maestro, maestro.registros[0].codigo)
assert r3.estado == "duplicado", r3
r4 = inv.procesar_escaneo(sesion, maestro, "NO-EXISTE-999")
assert r4.estado == "no_encontrado", r4
stats = inv.estadisticas(sesion.id)
print("Stats:", stats)
assert stats.registrados == 2 and stats.duplicados == 1 and stats.no_encontrados == 1
nuevo = inv.deshacer_ultimo(sesion)
assert nuevo is not None and nuevo.codigo == maestro.registros[1].codigo
assert inv.estadisticas(sesion.id).registrados == 1
# Volver a escanear para exportar dos.
inv.procesar_escaneo(sesion, maestro, maestro.registros[1].codigo)
autorizacion = auth.autorizar_cierre(sesion_op, nombre_confirmado="María Fernanda Gómez", clave=emitido.codigo)
sesion = inv.obtener_sesion(sesion.id)
final, archivos = inv.finalizar_sesion(
    sesion=sesion,
    operador=sesion_op,
    autorizacion=autorizacion,
    maestro=maestro,
)
print("Final:", final.estado, final.fin_en)
for archivo in archivos:
    print(archivo.tipo, archivo.ruta, archivo.tamano_bytes)
    assert archivo.ruta.exists() and archivo.ruta.stat().st_size > 0
assert final.estado == "finalizada"
assert not db.sesion_abierta_operador(sesion_op.operador_id)
# Reabrir la base y validar persistencia.
db.cerrar()
db2 = BaseDatos(rutas.base_datos)
print("Datos en disco:", db2.contar("operadores"), db2.contar("sesiones"), db2.contar("registros"), db2.contar("exportaciones"))
assert db2.contar("registros") == 2
db2.cerrar()
print("PRUEBA DE HUMO OK")
