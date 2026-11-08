"""Pruebas integradas del registro manual cuando falla el lector."""

from __future__ import annotations

import pytest
from openpyxl import load_workbook

from dulcesitos.archivo_maestro import cargar_maestro_actual
from dulcesitos.servicios import (
    ErrorInventario,
    ServicioAdministracion,
    ServicioAutenticacion,
    ServicioInventario,
)


def _preparar(db, rutas, admin):
    auth = ServicioAutenticacion(db)
    emitido = ServicioAdministracion(db).emitir_codigo(
        admin=admin,
        dias_vigencia=15,
        nombre="Carlos Operador",
        cedula="1087654321",
        correo="operador@dulcesitos.local",
    )
    operador = auth.registrar_operador(
        nombre="Carlos Operador",
        cedula="1087654321",
        correo="operador@dulcesitos.local",
        codigo=emitido.codigo,
    )
    maestro = cargar_maestro_actual(rutas.maestra)
    servicio = ServicioInventario(db, rutas)
    sesion = servicio.iniciar_sesion(
        operador, maestro, maestro.registros[0].codigo
    )
    return auth, emitido, operador, maestro, servicio, sesion


def test_registro_manual_sin_match_se_incluye_en_la_salida(db, rutas, admin):
    auth, emitido, operador, maestro, servicio, sesion = _preparar(
        db, rutas, admin
    )
    registro = servicio.registrar_manual(
        sesion=sesion,
        maestro=maestro,
        operador=operador,
        codigo="MANUAL-0001",
        descripcion="Producto sin etiqueta legible",
        novedad="El lector no detecta el código y no hay coincidencia en el Excel.",
        stock=7,
    )
    assert registro.es_manual
    assert registro.novedad.startswith("El lector")
    assert registro.stock_nuevo == 7
    assert servicio.estadisticas(sesion.id).manuales == 1
    with pytest.raises(ErrorInventario):
        servicio.registrar_manual(
            sesion=sesion,
            maestro=maestro,
            operador=operador,
            codigo="MANUAL-0001",
            descripcion="Duplicado",
            novedad="Duplicado",
        )
    autorizacion = auth.autorizar_cierre(
        operador,
        nombre_confirmado=operador.nombre,
        clave=emitido.codigo,
    )
    _, archivos = servicio.finalizar_sesion(
        sesion=servicio.obtener_sesion(sesion.id),
        operador=operador,
        autorizacion=autorizacion,
        maestro=maestro,
    )
    xlsx = next(a.ruta for a in archivos if a.tipo == "xlsx")
    libro = load_workbook(xlsx, read_only=True, data_only=True)
    hoja = libro["Actualización"]
    encabezados = [c.value for c in next(hoja.iter_rows(max_row=1))]
    assert "ORIGEN DEL REGISTRO" in encabezados
    assert "NOVEDAD MANUAL" in encabezados
    pos_codigo = encabezados.index(maestro.columna_codigo)
    pos_origen = encabezados.index("ORIGEN DEL REGISTRO")
    pos_novedad = encabezados.index("NOVEDAD MANUAL")
    fila = next(
        fila
        for fila in hoja.iter_rows(min_row=2, values_only=True)
        if fila[pos_codigo] == "MANUAL-0001"
    )
    assert fila[pos_origen] == "MANUAL"
    assert "lector" in fila[pos_novedad].lower()
    libro.close()
    txt = next(a.ruta for a in archivos if a.tipo == "txt")
    contenido = txt.read_text(encoding="utf-8-sig")
    assert "MANUAL-0001" in contenido
    assert "ORIGEN DEL REGISTRO" in contenido


def test_registro_manual_de_codigo_conocido_usa_catalogo(db, rutas, admin):
    _, _, operador, maestro, servicio, sesion = _preparar(db, rutas, admin)
    producto = maestro.registros[1]
    registro = servicio.registrar_manual(
        sesion=sesion,
        maestro=maestro,
        operador=operador,
        codigo=producto.codigo,
        descripcion="Texto escrito por el operador",
        novedad="Etiqueta dañada; se digita el código.",
    )
    assert registro.descripcion == producto.descripcion
    assert registro.es_manual
    assert registro.campos[maestro.columna_descripcion] == producto.descripcion


def test_producto_dado_de_baja_no_se_registra_manual(db, rutas, admin):
    from dulcesitos.catalogo import ServicioCatalogo

    maestro = cargar_maestro_actual(rutas.maestra)
    producto = maestro.registros[0]
    ServicioCatalogo(db).dar_de_baja(
        admin=admin,
        maestro=maestro,
        codigo=producto.codigo,
        motivo="Descontinuado",
    )
    efectivo = ServicioCatalogo(db).aplicar(maestro)
    auth = ServicioAutenticacion(db)
    emitido = ServicioAdministracion(db).emitir_codigo(
        admin=admin,
        dias_vigencia=15,
        nombre="Carlos Operador",
        cedula="1087654321",
        correo="operador@dulcesitos.local",
    )
    operador = auth.registrar_operador(
        nombre="Carlos Operador",
        cedula="1087654321",
        correo="operador@dulcesitos.local",
        codigo=emitido.codigo,
    )
    servicio = ServicioInventario(db, rutas)
    sesion = servicio.iniciar_sesion(
        operador, efectivo, efectivo.registros[0].codigo
    )
    with pytest.raises(ErrorInventario):
        servicio.registrar_manual(
            sesion=sesion,
            maestro=efectivo,
            operador=operador,
            codigo=producto.codigo,
            descripcion=producto.descripcion,
            novedad="No debe permitirse",
        )
