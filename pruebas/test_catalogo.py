"""Pruebas de altas, bajas y reactivación de productos."""

from __future__ import annotations

import pytest

from dulcesitos.archivo_maestro import cargar_maestro_actual
from dulcesitos.catalogo import ErrorCatalogo, ServicioCatalogo
from dulcesitos.servicios import (
    ServicioAdministracion,
    ServicioAutenticacion,
    ServicioInventario,
)


def _operador(auth, admin):
    emitido = ServicioAdministracion(auth.db).emitir_codigo(
        admin=admin,
        dias_vigencia=10,
        nombre="María Fernanda Gómez",
        cedula="1098765432",
        correo="maria@dulcesitos.local",
    )
    return auth.registrar_operador(
        nombre="María Fernanda Gómez",
        cedula="1098765432",
        correo="maria@dulcesitos.local",
        codigo=emitido.codigo,
    ), emitido


def test_alta_local_aparece_en_catalogo_efectivo(db, rutas, admin):
    maestro = cargar_maestro_actual(rutas.maestra)
    servicio = ServicioCatalogo(db)
    campos = {columna: "" for columna in maestro.columnas}
    campos["Categoría"] = "Dulces"
    campos["Precio"] = "3200"
    registro = servicio.crear_producto(
        admin=admin,
        maestro=maestro,
        codigo="7709999000001",
        descripcion="Nuevo dulce de prueba",
        campos=campos,
    )
    assert registro.codigo == "7709999000001"
    efectivo = servicio.aplicar(maestro)
    assert efectivo.total == maestro.total + 1
    assert efectivo.ajustes_locales == 1
    assert efectivo.buscar("7709999000001").descripcion == "Nuevo dulce de prueba"
    assert efectivo.huella != maestro.huella
    vista = {p.codigo: p for p in servicio.vista(maestro)}
    assert vista["7709999000001"].estado == "nuevo"
    assert vista["7709999000001"].origen == "local"
    resumen = servicio.resumen(maestro)
    assert resumen.nuevos == 1
    assert resumen.activos == maestro.total + 1


def test_baja_y_reactivacion_de_producto_del_maestro(db, rutas, admin):
    maestro = cargar_maestro_actual(rutas.maestra)
    servicio = ServicioCatalogo(db)
    producto = maestro.registros[0]
    servicio.dar_de_baja(
        admin=admin,
        maestro=maestro,
        codigo=producto.codigo,
        motivo="Producto descontinuado",
    )
    efectivo = servicio.aplicar(maestro)
    assert efectivo.buscar(producto.codigo) is None
    assert producto.codigo_clave in efectivo.inactivos
    assert efectivo.total == maestro.total - 1
    assert any(
        p.codigo_clave == producto.codigo_clave and p.estado == "inactivo"
        for p in servicio.vista(maestro)
    )
    servicio.reactivar(admin=admin, maestro=maestro, codigo=producto.codigo)
    recuperado = servicio.aplicar(maestro)
    assert recuperado.buscar(producto.codigo) is not None
    assert recuperado.inactivos == {}
    assert recuperado.total == maestro.total


def test_baja_de_producto_local_y_reactivacion(db, rutas, admin):
    maestro = cargar_maestro_actual(rutas.maestra)
    servicio = ServicioCatalogo(db)
    servicio.crear_producto(
        admin=admin,
        maestro=maestro,
        codigo="LOCAL-001",
        descripcion="Producto local",
        campos={"Categoría": "Local"},
    )
    servicio.dar_de_baja(
        admin=admin,
        maestro=maestro,
        codigo="LOCAL-001",
        motivo="Error de creación",
    )
    efectivo = servicio.aplicar(maestro)
    assert efectivo.buscar("LOCAL-001") is None
    servicio.reactivar(admin=admin, maestro=maestro, codigo="LOCAL-001")
    recuperado = servicio.aplicar(maestro)
    assert recuperado.buscar("LOCAL-001") is not None


def test_no_se_pueden_duplicar_codigos(db, rutas, admin):
    maestro = cargar_maestro_actual(rutas.maestra)
    servicio = ServicioCatalogo(db)
    with pytest.raises(ErrorCatalogo):
        servicio.crear_producto(
            admin=admin,
            maestro=maestro,
            codigo=maestro.registros[0].codigo,
            descripcion="Duplicado",
            campos={},
        )
    servicio.crear_producto(
        admin=admin,
        maestro=maestro,
        codigo="NUEVO-01",
        descripcion="Primero",
        campos={},
    )
    with pytest.raises(ErrorCatalogo):
        servicio.crear_producto(
            admin=admin,
            maestro=maestro,
            codigo="nuevo-01",
            descripcion="Duplicado local",
            campos={},
        )


def test_baja_bloquea_escaneo_pero_conserva_la_sesion(db, rutas, admin):
    auth = ServicioAutenticacion(db)
    operador, _ = _operador(auth, admin)
    maestro = cargar_maestro_actual(rutas.maestra)
    catalogo = ServicioCatalogo(db)
    objetivo = maestro.registros[0]
    catalogo.dar_de_baja(
        admin=admin,
        maestro=maestro,
        codigo=objetivo.codigo,
        motivo="Baja para prueba",
    )
    efectivo = catalogo.aplicar(maestro)
    inventario = ServicioInventario(db, rutas)
    sesion = inventario.iniciar_sesion(
        operador, efectivo, efectivo.registros[0].codigo
    )
    resultado = inventario.procesar_escaneo(sesion, efectivo, objetivo.codigo)
    assert resultado.estado == "no_encontrado"
    assert "dado de baja" in resultado.mensaje.lower()
    # La sesión sigue existiendo y sus estadísticas contabilizan la incidencia.
    assert inventario.estadisticas(sesion.id).no_encontrados == 1


def test_ajuste_persiste_y_cambia_la_huella(db, rutas, admin):
    maestro = cargar_maestro_actual(rutas.maestra)
    catalogo = ServicioCatalogo(db)
    original = catalogo.aplicar(maestro)
    catalogo.dar_de_baja(
        admin=admin,
        maestro=maestro,
        codigo=maestro.registros[1].codigo,
    )
    modificado = catalogo.aplicar(maestro)
    assert modificado.huella != original.huella
    # Una segunda instancia del servicio lee el mismo ajuste desde SQLite.
    otro = ServicioCatalogo(db)
    assert otro.aplicar(maestro).huella == modificado.huella
