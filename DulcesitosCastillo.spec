# -*- mode: python ; coding: utf-8 -*-
"""Empaquetado de Windows con PyInstaller (modo carpeta).

La aplicación se distribuye como una carpeta autocontenida. Esto evita
extraer cientos de megas en cada arranque y conserva los recursos gráficos.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

raiz = Path(SPECPATH)
datas = [
    (str(raiz / "assets"), "assets"),
    (str(raiz / "datos_ejemplo"), "datos_ejemplo"),
]
# Recursos que algunos backends de PDF/Excel cargan de forma dinámica.
datas += collect_data_files("reportlab")
datas += collect_data_files("pdfplumber")
datas += collect_data_files("pypdfium2")

hiddenimports = []
hiddenimports += collect_submodules("openpyxl")
hiddenimports += collect_submodules("reportlab")
hiddenimports += collect_submodules("pdfplumber")
hiddenimports += collect_submodules("pdfminer")
hiddenimports += collect_submodules("pypdfium2")
hiddenimports += ["serial", "serial.tools", "serial.tools.list_ports", "xlrd"]

a = Analysis(
    ["app.py"],
    pathex=[str(raiz)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter.test", "test", "unittest", "pydoc"],
    noarchive=False,
    optimize=1,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DulcesitosCastillo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(raiz / "assets" / "icono.ico"),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="DulcesitosCastillo",
)
