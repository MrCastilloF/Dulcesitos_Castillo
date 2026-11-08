"""Fixtures comunes de las pruebas automatizadas."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from dulcesitos.base_datos import BaseDatos
from dulcesitos.config import preparar_rutas
from dulcesitos.servicios import ServicioAutenticacion

RAIZ = Path(__file__).resolve().parent.parent
MUESTRA = RAIZ / "datos_ejemplo" / "DEMO_maestro_dulcesitos.xlsx"


@pytest.fixture()
def rutas(tmp_path, monkeypatch):
    maestro = tmp_path / "maestro"
    datos = tmp_path / "datos"
    monkeypatch.setenv("DULCESITOS_MAESTRO_DIR", str(maestro))
    monkeypatch.setenv("DULCESITOS_DATA_DIR", str(datos))
    rutas = preparar_rutas()
    if MUESTRA.exists():
        shutil.copy2(MUESTRA, rutas.maestra / MUESTRA.name)
    return rutas


@pytest.fixture()
def db(rutas):
    base = BaseDatos(rutas.base_datos)
    yield base
    base.cerrar()


@pytest.fixture()
def admin(db):
    auth = ServicioAutenticacion(db)
    return auth.crear_administrador_inicial(
        nombre="Carlos Castillo",
        cedula="1020304050",
        correo="admin@dulcesitos.local",
        clave="Cacao2026Seguro",
        confirmacion="Cacao2026Seguro",
    )
