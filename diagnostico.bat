@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "EXE=dist\DulcesitosCastillo\DulcesitosCastillo.exe"
if exist "%EXE%" (
    echo Ejecutando diagnóstico del ejecutable...
    "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -Command "Start-Process -FilePath '%EXE%' -ArgumentList '--diagnostico' -Wait"
) else (
    if not exist ".venv\Scripts\python.exe" (
        echo No existe .venv ni el ejecutable compilado.
        echo Ejecuta instalar.bat o construir_exe.bat.
        pause
        exit /b 1
    )
    echo Ejecutando diagnóstico desde el código fuente...
    ".venv\Scripts\python.exe" "app.py" --diagnostico
)

echo.
type "%LOCALAPPDATA%\DulcesitosCastillo\diagnostico.txt" 2>nul
if errorlevel 1 (
    echo No se encontró el archivo de diagnóstico.
)
echo.
pause
