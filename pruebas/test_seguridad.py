"""Pruebas de hashing, códigos y validaciones."""

from __future__ import annotations

import sqlite3

import pytest

from dulcesitos.seguridad import (
    formatear_codigo_acceso,
    generar_codigo_acceso,
    hash_clave,
    huella_codigo_acceso,
    normalizar_codigo_acceso,
    pista_codigo,
    validar_fortaleza_clave,
    verificar_clave,
)
from dulcesitos.servicios import (
    ErrorAutenticacion,
    ServicioAdministracion,
    ServicioAutenticacion,
)


def test_hash_no_expone_la_clave_y_verifica():
    clave = "Cacao2026Seguro"
    valor = hash_clave(clave, iteraciones=120_000)
    assert clave not in valor
    assert valor.startswith("pbkdf2_sha256$120000$")
    assert verificar_clave(clave, valor)
    assert not verificar_clave("otra", valor)
    assert not verificar_clave("", valor)
    assert not verificar_clave(clave, "cadena-invalida")


def test_dos_hashes_de_la_misma_clave_son_distintos():
    clave = "MismaClave123"
    assert hash_clave(clave, iteraciones=120_000) != hash_clave(
        clave, iteraciones=120_000
    )


def test_codigo_generado_tiene_formato_y_entropia_suficiente():
    codigos = {generar_codigo_acceso() for _ in range(40)}
    assert len(codigos) == 40
    for codigo in codigos:
        assert codigo.startswith("DLC-")
        assert len(codigo) == 18
        assert len(normalizar_codigo_acceso(codigo)) == 15
        assert formatear_codigo_acceso(codigo) == codigo
        assert pista_codigo(codigo).startswith("••••-")
        assert huella_codigo_acceso(codigo) == huella_codigo_acceso(
            codigo.lower().replace("-", " ")
        )


def test_fortaleza_de_clave():
    assert validar_fortaleza_clave("Cacao2026Seguro") == []
    assert validar_fortaleza_clave("corta")
    assert validar_fortaleza_clave("solamenteletras")
    assert validar_fortaleza_clave("1234567890")
    assert validar_fortaleza_clave("Cacao 2026Seguro")


def test_base_de_datos_no_guarda_credenciales_en_texto_plano(db, admin):
    auth = ServicioAutenticacion(db)
    emitido = ServicioAdministracion(db).emitir_codigo(
        admin=admin, dias_vigencia=7
    )
    filas = db._conexion.execute(
        "SELECT codigo_hash, huella FROM codigos_acceso"
    ).fetchall()
    textos = " ".join(str(v) for fila in filas for v in fila)
    assert emitido.codigo not in textos
    assert normalizar_codigo_acceso(emitido.codigo) not in textos
    admin_fila = db._conexion.execute(
        "SELECT clave_hash FROM administradores"
    ).fetchone()
    assert "Cacao2026Seguro" not in admin_fila["clave_hash"]
    # La verificación real sigue funcionando desde el servicio.
    assert auth.autenticar_administrador("1020304050", "Cacao2026Seguro").id == admin.id


def test_solo_existe_un_administrador(db, admin):
    auth = ServicioAutenticacion(db)
    with pytest.raises(ErrorAutenticacion):
        auth.crear_administrador_inicial(
            nombre="Otro Administrador",
            cedula="9999999999",
            correo="otro@dulcesitos.local",
            clave="OtraClave2026",
            confirmacion="OtraClave2026",
        )
    assert db.contar("administradores") == 1


def test_hash_guardado_es_compatible_con_sqlite(db, admin):
    fila = db._conexion.execute(
        "SELECT clave_hash FROM administradores WHERE id = ?", (admin.id,)
    ).fetchone()
    assert isinstance(fila["clave_hash"], str)
    assert len(fila["clave_hash"]) > 60
    with pytest.raises(sqlite3.IntegrityError):
        with db._conexion:
            db._conexion.execute(
                "INSERT INTO administradores (nombre, cedula, correo, clave_hash, creado_en, actualizado_en) "
                "VALUES ('Duplicado', '1020304050', 'x@y.co', 'x', '2026-01-01', '2026-01-01')"
            )
