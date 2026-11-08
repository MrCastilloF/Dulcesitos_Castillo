param(
    [string]$Version = "1.0.0",
    [string]$Carpeta = ""
)

$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent $PSScriptRoot
if (-not $Carpeta) {
    $Carpeta = Join-Path $raiz "dist\DulcesitosCastillo"
}
$Carpeta = [System.IO.Path]::GetFullPath($Carpeta)
$exe = Join-Path $Carpeta "DulcesitosCastillo.exe"
if (-not (Test-Path $exe)) {
    throw "No se encontró el ejecutable: $exe"
}

Copy-Item (Join-Path $raiz "instalar_demo.bat") $Carpeta -Force
Copy-Item (Join-Path $raiz "README.md") $Carpeta -Force
Copy-Item (Join-Path $raiz "LICENSE") $Carpeta -Force
$datos = Join-Path $Carpeta "datos_ejemplo"
if (-not (Test-Path $datos)) {
    Copy-Item (Join-Path $raiz "datos_ejemplo") $Carpeta -Recurse -Force
}

$leeme = @"
DULCESITOS CASTILLO · INVENTARIO DE BODEGA
==========================================

Versión $Version · SENA · Carlos Castillo

QUÉ CONTIENE
------------
DulcesitosCastillo.exe
LEEME_PRIMERO.txt
diagnostico.bat
instalar_demo.bat
assets\
datos_ejemplo\

CÓMO ABRIR
----------
1. Descomprime TODA la carpeta en una ruta local, por ejemplo:
   C:\DulcesitosCastillo
2. Haz doble clic en DulcesitosCastillo.exe.
3. Windows puede mostrar SmartScreen porque el ejecutable no tiene firma
   comercial. Usa "Más información" > "Ejecutar de todas formas" solo si
   descargaste el archivo desde el repositorio oficial.
4. La primera vez se configura el acceso ÚNICO del administrador.
   No existe una clave por defecto ni un botón para crear otros
   administradores.
5. El administrador crea el código de acceso de cada operador desde
   "Acceso administración" > Accesos > Generar código.

CARPETA MAESTRA
---------------
El archivo maestro debe estar en:
C:\dulcesito_castillo

La aplicación no modifica ese archivo. Los ajustes de catálogo y stock
se guardan en la base local y se reflejan en las salidas.

SALIDAS
-------
C:\dulcesito_castillo\salidas

Se generan Excel (.xlsx), texto (.txt) y un reporte visual (.pdf).

DIAGNÓSTICO
-----------
Si la aplicación no abre, ejecuta diagnostico.bat y revisa el reporte.
También puedes abrir una consola y ejecutar:
DulcesitosCastillo.exe --diagnostico

MODO DEMOSTRACIÓN
-----------------
instalar_demo.bat copia un catálogo de ejemplo claramente marcado como
DEMOSTRACIÓN. Reemplázalo por el archivo real antes de operar la bodega.

SEGURIDAD
---------
- No hay claves en texto plano.
- El código de acceso se muestra una sola vez.
- El administrador puede fijar vencimiento, revocar y renovar.
- El operador no puede entrar al panel administrativo.
"@
Set-Content -Path (Join-Path $Carpeta "LEEME_PRIMERO.txt") -Value $leeme -Encoding utf8

$diagnostico = @"
@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo Generando diagnóstico de Dulcesitos Castillo...
"DulcesitosCastillo.exe" --diagnostico
echo.
echo El reporte también queda en la carpeta de datos de la aplicación.
pause
"@
Set-Content -Path (Join-Path $Carpeta "diagnostico.bat") -Value $diagnostico -Encoding oem

$destino = Join-Path $raiz "dist\DulcesitosCastillo-$Version-win64.zip"
if (Test-Path $destino) {
    Remove-Item $destino -Force
}
Compress-Archive -Path (Join-Path $Carpeta "*") -DestinationPath $destino -CompressionLevel Optimal
$hash = (Get-FileHash -Algorithm SHA256 $destino).Hash.ToLowerInvariant()
$nombre = Split-Path -Leaf $destino
Set-Content -Path "$destino.sha256" -Value "$hash  $nombre" -Encoding ascii
Write-Output "ZIP: $destino"
Write-Output "SHA256: $hash"
