# Restaurar SOLO las 4 colecciones del modelo principal de MongoDB.
# Desde Fase3: .\restaurar_fase3.ps1 -Reemplazar
# Requiere respaldo final de la BD (puede contener las 6 colecciones; se filtran al restaurar).
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
catch { throw "No se encontro el respaldo: $Archivo. Colocalo en Fase3\paris2024\respaldos\." }
if ((Get-Item -LiteralPath $Archivo).Length -lt 1000000) {
    throw 'El respaldo parece incompleto (menos de 1 MB).'
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'No se encontro Docker. Inicia Docker Desktop.'
}
$running = & docker inspect -f '{{.State.Running}}' $Contenedor 2>$null
if ($LASTEXITCODE -ne 0 -or "$running".Trim() -ne 'true') {
    throw "El contenedor '$Contenedor' no esta en ejecucion."
}
& docker exec $Contenedor mongosh --quiet --eval 'db.adminCommand({ping:1}).ok' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'MongoDB no responde.' }

Write-Host ''
Write-Host 'Colecciones que se restauraran: atletas, paises, resultados, catalogos.'
Write-Host 'NO se importaran paris2024_fuente ni paris2024_equipos_preparados.'
if (-not $Reemplazar) {
    Write-Host 'MODO SIMULACION: no se modifico MongoDB.' -ForegroundColor Yellow
    Write-Host 'Para restaurar: .\restaurar_fase3.ps1 -Reemplazar'
    exit 0
}
Write-Host 'ADVERTENCIA: Se reemplazaran las 4 colecciones del destino.' -ForegroundColor Yellow
& docker cp $Archivo "${Contenedor}:/tmp/restaurar_fase3.archive.gz"
if ($LASTEXITCODE -ne 0) { throw 'Error al copiar el respaldo al contenedor.' }

# Filtrar la restauracion por namespace. Un archivo de 6 colecciones es compatible:
# solo se restauran las 4 indicadas.
$seleccion = @(
    '--nsInclude=olimpiadas_mongo.atletas',
    '--nsInclude=olimpiadas_mongo.paises',
    '--nsInclude=olimpiadas_mongo.resultados',
    '--nsInclude=olimpiadas_mongo.catalogos'
)
Write-Host 'Restaurando 4 colecciones del modelo principal...'
& docker exec $Contenedor mongorestore '--archive=/tmp/restaurar_fase3.archive.gz' --gzip --drop @seleccion
if ($LASTEXITCODE -ne 0) { throw 'Fallo mongorestore. No repitas sin revisar el error.' }

$verificacion = @'
const d=db.getSiblingDB("olimpiadas_mongo");
const r=d.resultados.countDocuments({});
const p=d.resultados.countDocuments({"edicion.anio":2024});
const h=d.resultados.countDocuments({"edicion.anio":{$lt:2024}});
const a=d.atletas.countDocuments({});
const n=d.paises.countDocuments({});
const k=d.catalogos.countDocuments({});
print("Resultados: "+r+" | Paris 2024: "+p+" | Historicos: "+h);
print("Atletas: "+a+" | Paises: "+n+" | Catalogos: "+k);
print("Colecciones presentes: "+d.getCollectionNames().sort().join(", "));
if (r!==160244 || p!==4212 || h!==156032 || a!==149081 || n!==247 || k!==3618) quit(2);
'@
Write-Host 'Verificando cantidades...'
& docker exec $Contenedor mongosh olimpiadas_mongo --quiet --eval $verificacion
if ($LASTEXITCODE -ne 0) {
    throw 'Los datos se restauraron, pero las cantidades no coinciden con el respaldo esperado.'
}
Write-Host 'RESTAURACION DE LAS 4 COLECCIONES EXITOSA.' -ForegroundColor Green
Write-Host 'NOTA: La restauracion no borra otras colecciones que ya existieran en el destino.'
