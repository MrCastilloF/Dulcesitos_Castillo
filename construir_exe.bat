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
echo Construyendo aplicación de Windows...
".venv\Scripts\pyinstaller.exe" --noconfirm --clean DulcesitosCastillo.spec
if errorlevel 1 goto :error

echo.
echo Compilación terminada.
echo Ejecutable: dist\DulcesitosCastillo\DulcesitosCastillo.exe
echo Copia TODA la carpeta dist\DulcesitosCastillo para distribuirla.
echo.
pause
exit /b 0

:error
echo.
echo ERROR durante la compilación.
pause
exit /b 1
