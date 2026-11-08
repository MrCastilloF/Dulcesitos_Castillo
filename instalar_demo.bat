@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not exist "C:\dulcesito_castillo" (
    mkdir "C:\dulcesito_castillo"
    if errorlevel 1 (
        echo No se pudo crear C:\dulcesito_castillo.
        echo Ejecuta este archivo con permisos de administrador.
        pause
        exit /b 1
    )
)

copy /Y "datos_ejemplo\DEMO_maestro_dulcesitos.xlsx" "C:\dulcesito_castillo\DEMO_maestro_dulcesitos.xlsx" >nul
if errorlevel 1 (
    echo No se pudo copiar el catálogo de demostración.
    pause
    exit /b 1
)

echo ============================================================
echo Catálogo de DEMOSTRACIÓN instalado en:
echo   C:\dulcesito_castillo\DEMO_maestro_dulcesitos.xlsx
echo.
echo La aplicación lo marcará como DEMOSTRACIÓN. Reemplázalo por
echo el archivo real antes de operar la bodega.
echo ============================================================
start "" explorer.exe "C:\dulcesito_castillo"
pause
