# Restauracion de la base final de Fase 3 desde un respaldo mongodump.
# Ejecutar en PowerShell desde Fase3: .\restaurar_fase3.ps1
# Requiere Docker Desktop, un contenedor MongoDB iniciado y el respaldo final.
param(
    [string]$Contenedor = 'mongo_fase3',
    [string]$Archivo = '',
    [switch]$Reemplazar
)
$ErrorActionPreference = 'Stop'
$raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
if ([string]::IsNullOrWhiteSpace($Archivo)) {
    $Archivo = Join-Path $raiz 'paris2024\respaldos\olimpiadas_mongo_fase3.archive.gz'
}
try { $Archivo = (Resolve-Path -LiteralPath $Archivo -ErrorAction Stop).Path }
catch { throw "No se encuentra el respaldo: $Archivo. Solicitalo al equipo y copialo a paris2024\respaldos\." }
if ((Get-Item -LiteralPath $Archivo).Length -lt 1000000) { throw 'El respaldo parece incompleto (menor de 1 MB).' }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Falta Docker. Instala e inicia Docker Desktop.' }
$enEjecucion = (& docker inspect -f '{{.State.Running}}' $Contenedor 2>$null)
if ($LASTEXITCODE -ne 0 -or $enEjecucion.Trim() -ne 'true') {
    throw "No esta iniciado el contenedor '$Contenedor'. Inicia tu MongoDB antes de continuar."
}
& docker exec $Contenedor mongosh --quiet --eval 'db.adminCommand({ping:1}).ok' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'No se pudo conectar a MongoDB dentro del contenedor.' }
if (-not $Reemplazar) {
    Write-Host ''
    Write-Host 'MODO SEGURO: no se modifico MongoDB.' -ForegroundColor Yellow
    Write-Host 'El respaldo esta listo para restaurarse.'
    Write-Host 'ADVERTENCIA: -Reemplazar usa mongorestore --drop y sustituye las colecciones de olimpiadas_mongo.'
    Write-Host 'Para continuar: .\restaurar_fase3.ps1 -Reemplazar'
    exit 0
}
Write-Host 'Copiando respaldo al contenedor...'
& docker cp $Archivo "${Contenedor}:/tmp/olimpiadas_mongo_fase3.archive.gz"
if ($LASTEXITCODE -ne 0) { throw 'Fallo docker cp.' }
Write-Host 'Restaurando olimpiadas_mongo (reemplaza colecciones actuales)...'
& docker exec $Contenedor mongorestore --archive=/tmp/olimpiadas_mongo_fase3.archive.gz --gzip '--nsInclude=olimpiadas_mongo.*' --drop
if ($LASTEXITCODE -ne 0) { throw 'Fallo la restauracion; revisar la salida de mongorestore.' }
Write-Host 'Verificando cantidades...'
$js = @'
const d = db.getSiblingDB('olimpiadas_mongo');
const resultados=d.resultados.countDocuments({});
const atletas=d.atletas.countDocuments({});
const paris=d.resultados.countDocuments({'edicion.anio':2024});
const equipos=d.paris2024_equipos_preparados.countDocuments({});
print('Resultados: '+resultados+' | Atletas: '+atletas+' | Paris 2024: '+paris+' | Equipos preparados: '+equipos);
if(resultados!==160244 || atletas!==149081 || paris!==4212 || equipos!==199){quit(2)}
'@
& docker exec $Contenedor mongosh --quiet --eval $js
if ($LASTEXITCODE -ne 0) { throw 'La restauracion termino, pero las cantidades difieren del respaldo esperado. Revisar el archivo usado.' }
Write-Host 'RESTAURACION EXITOSA.' -ForegroundColor Green
