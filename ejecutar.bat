@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo No se encontró el entorno de ejecución. Iniciando instalación...
    call instalar.bat
    if errorlevel 1 (
        echo.
        echo No fue posible preparar la aplicación. Revisa el mensaje anterior.
        pause
        exit /b 1
    )
)

start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0app.py"
exit /b 0
