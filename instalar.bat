@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================================
echo   Dulcesitos Castillo - Operador de Inventarios
echo   Instalación de dependencias para Windows
echo ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python no está instalado o no está en el PATH.
    echo.
    echo Instala Python 3.10 o superior desde https://www.python.org/downloads/windows/
    echo y marca la opción "Add python.exe to PATH".
    pause
    exit /b 1
)

python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if errorlevel 1 (
    echo ERROR: se requiere Python 3.10 o superior.
    python --version
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creando entorno virtual local...
    python -m venv .venv
    if errorlevel 1 (
        echo ERROR: no se pudo crear el entorno virtual.
        pause
        exit /b 1
    )
)

echo Actualizando pip e instalando dependencias...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :error
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo.
echo Instalación completada.
echo Ejecuta ejecutar.bat para abrir la aplicación.
echo.
pause
exit /b 0

:error
echo.
echo ERROR: falló la instalación. Revisa tu conexión a Internet o el registro.
pause
exit /b 1
