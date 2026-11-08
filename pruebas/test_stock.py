"""Pruebas de ajuste de stock por el operador."""

from __future__ import annotations

from openpyxl import load_workbook

from dulcesitos.archivo_maestro import cargar_maestro_actual, convertir_numero
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
    operador = auth.registrar_operador(
        nombre="María Fernanda Gómez",
        cedula="1098765432",
        correo="maria@dulcesitos.local",
        codigo=emitido.codigo,
    )
    return operador, emitido


def test_deteccion_de_columna_y_numeros():
    assert convertir_numero("1.250") == 1250
    assert convertir_numero("1,25") == 1.25
    assert convertir_numero(" 74 ") == 74
    assert convertir_numero("sin dato") is None


def test_operador_ajusta_stock_y_exportacion_lo_aplica(db, rutas, admin):
    auth = ServicioAutenticacion(db)
    operador, emitido = _operador(auth, admin)
    maestro = cargar_maestro_actual(rutas.maestra)
    assert maestro.columna_stock is not None
    servicio = ServicioInventario(db, rutas)
    sesion = servicio.iniciar_sesion(operador, maestro, maestro.registros[0].codigo)
    resultado = servicio.procesar_escaneo(
        sesion, maestro, maestro.registros[0].codigo
    )
    registro = resultado.registro
    assert registro is not None
    original = convertir_numero(registro.campos[maestro.columna_stock])
    assert original is not None
    actualizado = servicio.ajustar_stock(
        sesion=sesion,
        maestro=maestro,
        registro=registro,
        stock_nuevo=original + 5,
        operador=operador,
    )
    assert actualizado.stock_nuevo == original + 5
    assert actualizado.stock_original == original
    assert actualizado.stock_diferencia == 5
    assert servicio.estadisticas(sesion.id).ajustes_stock == 1

    actualizado = servicio.quitar_ajuste_stock(sesion=sesion, registro=actualizado)
    assert actualizado.stock_nuevo is None
    # Se vuelve a ajustar para comprobar la exportación.
    servicio.ajustar_stock(
        sesion=sesion,
        maestro=maestro,
        registro=actualizado,
        stock_nuevo=original + 3,
        operador=operador,
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
    assert "STOCK ORIGINAL" in encabezados
    assert "STOCK CONTADO" in encabezados
    pos_codigo = encabezados.index(maestro.columna_codigo)
    pos_stock = encabezados.index(maestro.columna_stock)
    pos_original = encabezados.index("STOCK ORIGINAL")
    pos_contado = encabezados.index("STOCK CONTADO")
    fila = next(
        fila
        for fila in hoja.iter_rows(min_row=2, values_only=True)
        if fila[pos_codigo] == maestro.registros[0].codigo
    )
    assert float(fila[pos_stock]) == original + 3
    assert float(fila[pos_original]) == original
    assert float(fila[pos_contado]) == original + 3
    libro.close()
    # El archivo maestro no cambia.
    assert convertir_numero(maestro.registros[0].campos[maestro.columna_stock]) == original
