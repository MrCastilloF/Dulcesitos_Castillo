@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    call instalar.bat
    if errorlevel 1 exit /b 1
)

echo Instalando herramientas de empaquetado...
".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
if errorlevel 1 goto :error

echo.
echo Construyendo aplicacion de Windows...
".venv\Scripts\pyinstaller.exe" --noconfirm --clean DulcesitosCastillo.spec
if errorlevel 1 goto :error

echo.
echo Preparando carpeta de distribucion y ZIP...
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "herramientas\preparar_distribucion.ps1" -Version 1.0.0
if errorlevel 1 goto :error

echo.
echo Compilacion terminada.
echo Ejecutable: dist\DulcesitosCastillo\DulcesitosCastillo.exe
echo ZIP: dist\DulcesitosCastillo-1.0.0-win64.zip
echo Copia TODA la carpeta dist\DulcesitosCastillo para distribuirla.
echo.
pause
exit /b 0

:error
echo.
echo ERROR durante la compilacion.
pause
exit /b 1
