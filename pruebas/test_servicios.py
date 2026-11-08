"""Pruebas integrales de autenticación, sesiones y exportaciones."""

from __future__ import annotations

from datetime import timedelta

import pytest
from openpyxl import load_workbook

from dulcesitos.archivo_maestro import cargar_maestro_actual
from dulcesitos.servicios import (
    ErrorAutenticacion,
    ErrorInventario,
    ServicioAdministracion,
    ServicioAutenticacion,
    ServicioInventario,
)
from dulcesitos.utilidades import a_iso, ahora_utc


def _crear_operador(auth, admin, **cambios):
    datos = {
        "nombre": "María Fernanda Gómez",
        "cedula": "1098765432",
        "correo": "maria@dulcesitos.local",
        "dias": 7,
    }
    datos.update(cambios)
    admin_svc = ServicioAdministracion(auth.db)
    emitido = admin_svc.emitir_codigo(
        admin=admin,
        dias_vigencia=datos.pop("dias"),
        nombre=datos["nombre"],
        cedula=datos["cedula"],
        correo=datos["correo"],
    )
    operador = auth.registrar_operador(
        **datos,
        codigo=emitido.codigo,
    )
    return admin_svc, emitido, operador


def _sesion_con_productos(db, rutas, operador, cantidad=3):
    maestro = cargar_maestro_actual(rutas.maestra)
    servicio = ServicioInventario(db, rutas)
    sesion = servicio.iniciar_sesion(operador, maestro, maestro.registros[0].codigo)
    for indice in range(cantidad):
        servicio.procesar_escaneo(sesion, maestro, maestro.registros[indice].codigo)
    return servicio, maestro, sesion


def test_flujo_completo_de_operador_y_cierre(db, rutas, admin):
    auth = ServicioAutenticacion(db)
    admin_svc, emitido, operador = _crear_operador(auth, admin)
    assert auth.sesion_operador_vigente(operador)
    assert auth.iniciar_sesion_operador("1098765432", emitido.codigo).operador_id == operador.operador_id
    with pytest.raises(ErrorAutenticacion):
        auth.iniciar_sesion_operador("1098765432", "DLC-AAAA-AAAA-AAAA")


    servicio = ServicioInventario(db, rutas)
    maestro = cargar_maestro_actual(rutas.maestra)
    sesion = servicio.iniciar_sesion(operador, maestro, maestro.registros[0].codigo)
    r1 = servicio.procesar_escaneo(sesion, maestro, maestro.registros[0].codigo)
    assert r1.estado == "registrado" and r1.registro is not None
    r2 = servicio.procesar_escaneo(sesion, maestro, maestro.registros[1].codigo)
    assert r2.estado == "registrado"
    r3 = servicio.procesar_escaneo(sesion, maestro, maestro.registros[0].codigo)
    assert r3.estado == "duplicado"
    r4 = servicio.procesar_escaneo(sesion, maestro, "NO-EXISTE-999")
    assert r4.estado == "no_encontrado"
    assert servicio.estadisticas(sesion.id).registrados == 2
    autorizacion = auth.autorizar_cierre(
        operador,
        nombre_confirmado=operador.nombre,
        clave=emitido.codigo,
    )
    assert autorizacion.metodo == "operador"
    sesion = servicio.obtener_sesion(sesion.id)
    final, archivos = servicio.finalizar_sesion(
        sesion=sesion,
        operador=operador,
        autorizacion=autorizacion,
        maestro=maestro,
    )
    assert final.estado == "finalizada"
    assert {a.tipo for a in archivos} == {"xlsx", "pdf", "txt"}
    assert all(a.ruta.exists() and a.ruta.stat().st_size > 0 for a in archivos)
    assert final.fin_en is not None

    # El Excel conserva las columnas originales y agrega auditoría.
    xlsx = next(a.ruta for a in archivos if a.tipo == "xlsx")
    libro = load_workbook(xlsx, read_only=True, data_only=True)
    assert "Actualización" in libro.sheetnames
    assert "Registros de sesión" in libro.sheetnames
    encabezados = [c.value for c in next(libro["Actualización"].iter_rows(max_row=1))]
    for columna in maestro.columnas:
        assert columna in encabezados
    assert "REGISTRADO EN SESIÓN" in encabezados
    libro.close()

    # El original no fue modificado.
    assert maestro.ruta.exists()
    assert maestro.buscar(maestro.registros[0].codigo) is not None

    with pytest.raises(ErrorInventario):
        servicio.procesar_escaneo(final, maestro, maestro.registros[0].codigo)


def test_renovacion_revoca_el_codigo_anterior(db, rutas, admin):
    auth = ServicioAutenticacion(db)
    admin_svc, emitido, operador = _crear_operador(auth, admin)
    renovado = admin_svc.emitir_codigo(
        admin=admin,
        dias_vigencia=10,
        operador_id=operador.operador_id,
    )
    with pytest.raises(ErrorAutenticacion):
        auth.iniciar_sesion_operador("1098765432", emitido.codigo)
    assert auth.iniciar_sesion_operador("1098765432", renovado.codigo).operador_id == operador.operador_id


def test_revocacion_y_vencimiento(db, rutas, admin):
    auth = ServicioAutenticacion(db)
    admin_svc, emitido, operador = _crear_operador(auth, admin)
    admin_svc.revocar_codigo(admin, emitido.codigo_id)
    with pytest.raises(ErrorAutenticacion):
        auth.iniciar_sesion_operador("1098765432", emitido.codigo)

    otro = admin_svc.emitir_codigo(
        admin=admin,
        dias_vigencia=3,
        operador_id=operador.operador_id,
    )
    db._conexion.execute(
        "UPDATE codigos_acceso SET expira_en = ? WHERE id = ?",
        (a_iso(ahora_utc() - timedelta(days=1)), otro.codigo_id),
    )
    with pytest.raises(ErrorAutenticacion):
        auth.iniciar_sesion_operador("1098765432", otro.codigo)


def test_invitacion_asignada_debe_coincidir(db, rutas, admin):
    auth = ServicioAutenticacion(db)
    admin_svc = ServicioAdministracion(db)
    emitido = admin_svc.emitir_codigo(
        admin=admin,
        dias_vigencia=5,
        nombre="Andrés Felipe Rojas",
        cedula="1032456789",
        correo="andres@dulcesitos.local",
    )
    with pytest.raises(ErrorAutenticacion):
        auth.registrar_operador(
            nombre="Otra Persona",
            cedula="1032456789",
            correo="andres@dulcesitos.local",
            codigo=emitido.codigo,
        )
    with pytest.raises(ErrorAutenticacion):
        auth.registrar_operador(
            nombre="Andrés Felipe Rojas",
            cedula="1032456789",
            correo="otro@dulcesitos.local",
            codigo=emitido.codigo,
        )
    operador = auth.registrar_operador(
        nombre="Andrés Felipe Rojas",
        cedula="1032456789",
        correo="andres@dulcesitos.local",
        codigo=emitido.codigo,
    )
    assert operador.nombre == "Andrés Felipe Rojas"


def test_sesion_abierta_se_reanuda_con_instantanea(db, rutas, admin):
    auth = ServicioAutenticacion(db)
    _, _emitido, operador = _crear_operador(auth, admin)
    maestro = cargar_maestro_actual(rutas.maestra)
    servicio = ServicioInventario(db, rutas)
    sesion = servicio.iniciar_sesion(operador, maestro, maestro.registros[0].codigo)
    servicio.procesar_escaneo(sesion, maestro, maestro.registros[0].codigo)
    pendiente = servicio.sesion_abierta(operador.operador_id)
    assert pendiente is not None
    recuperado = servicio.cargar_maestro_sesion(pendiente)
    assert recuperado.huella == maestro.huella
    assert recuperado.buscar(maestro.registros[0].codigo) is not None
    # No se puede abrir una segunda sesión.
    with pytest.raises(ErrorInventario):
        servicio.iniciar_sesion(operador, maestro, maestro.registros[0].codigo)


def test_autorizacion_de_administrador_para_cierre(db, rutas, admin):
    auth = ServicioAutenticacion(db)
    _, emitido, operador = _crear_operador(auth, admin)
    resultado = auth.autorizar_cierre(
        operador,
        nombre_confirmado=operador.nombre,
        clave="Cacao2026Seguro",
    )
    assert resultado.metodo == "administrador"
    with pytest.raises(ErrorAutenticacion):
        auth.autorizar_cierre(
            operador,
            nombre_confirmado="Nombre Incorrecto",
            clave="Cacao2026Seguro",
        )
    with pytest.raises(ErrorAutenticacion):
        auth.autorizar_cierre(
            operador,
            nombre_confirmado=operador.nombre,
            clave="ClaveIncorrecta123",
        )


def test_deshacer_ultimo_registro(db, rutas, admin):
    auth = ServicioAutenticacion(db)
    _, _, operador = _crear_operador(auth, admin)
    servicio, maestro, sesion = _sesion_con_productos(db, rutas, operador, 2)
    eliminado = servicio.deshacer_ultimo(sesion)
    assert eliminado is not None
    assert servicio.estadisticas(sesion.id).registrados == 1
    assert servicio.deshacer_ultimo(sesion) is not None
    assert servicio.deshacer_ultimo(sesion) is None


def test_archivo_original_no_se_modifica(db, rutas, admin):
    auth = ServicioAutenticacion(db)
    _, _, operador = _crear_operador(auth, admin)
    maestro = cargar_maestro_actual(rutas.maestra)
    original = maestro.ruta.read_bytes()
    hash_original = maestro.huella
    servicio = ServicioInventario(db, rutas)
    sesion = servicio.iniciar_sesion(operador, maestro, maestro.registros[0].codigo)
    servicio.procesar_escaneo(sesion, maestro, maestro.registros[0].codigo)
    autorizacion = auth.autorizar_cierre(
        operador,
        nombre_confirmado=operador.nombre,
        clave="Cacao2026Seguro",
    )
    servicio.finalizar_sesion(
        sesion=servicio.obtener_sesion(sesion.id),
        operador=operador,
        autorizacion=autorizacion,
        maestro=maestro,
    )
    assert maestro.ruta.read_bytes() == original
    assert maestro.huella == hash_original
    assert db.contar("exportaciones") == 3
