@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    call instalar.bat
    if errorlevel 1 exit /b 1
)

echo Iniciando Dulcesitos Castillo con consola de diagnóstico...
echo Cierra esta ventana cuando termines.
echo.
".venv\Scripts\python.exe" "%~dp0app.py"
echo.
echo La aplicación terminó con código %errorlevel%.
pause
