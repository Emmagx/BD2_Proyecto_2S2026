# Restaurar la base MongoDB de Fase 3 (París 2024)
## Archivos necesarios

- `restaurar_fase3.ps1`, colocado en la carpeta `Fase3/`.
- `paris2024/respaldos/olimpiadas_mongo_fase3.archive.gz`, respaldo **final** generado por la persona que hizo la carga, **después** de los ETL y de la conciliación. No usar `antes_etl_equipos.archive.gz`.
- Docker Desktop funcionando y un contenedor MongoDB en ejecución, por defecto `mongo_fase3`.

## Preparar el respaldo en la computadora de origen

Desde `Fase3`:

```powershell
docker exec mongo_fase3 mongodump --db olimpiadas_mongo --archive=/tmp/olimpiadas_mongo_fase3.archive.gz --gzip
docker cp mongo_fase3:/tmp/olimpiadas_mongo_fase3.archive.gz ".\paris2024\respaldos\olimpiadas_mongo_fase3.archive.gz"
```

Compartir el `.archive.gz` con el equipo por Drive o una ubicación acordada. Subir el código a Git; evitar subir los numerosos respaldos intermedios. Comprobar el tamaño del archivo antes de compartir.

## En la computadora de cada compañero

Abrir PowerShell en `Fase3`. Con Docker y el contenedor ya iniciados:

```powershell
.\restaurar_fase3.ps1
```

Esto **solo valida** los requisitos y no modifica los datos. Para ejecutar la restauración:

```powershell
.\restaurar_fase3.ps1 -Reemplazar
```

**Advertencia:** `-Reemplazar` utiliza `mongorestore --drop`: sustituye las colecciones incluidas en el respaldo dentro de `olimpiadas_mongo`. Usarlo solamente en una base local de pruebas cuando se acepta reemplazar su contenido. Si el contenedor tiene otro nombre:

```powershell
.\restaurar_fase3.ps1 -Contenedor nombre_real -Reemplazar
```

Si PowerShell impide ejecutar archivos `.ps1`, se puede invocar puntualmente desde `Fase3`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\restaurar_fase3.ps1 -Reemplazar
```

## Estado esperado

- Resultados totales: **160244**
- Resultados de París 2024: **4212**
- Atletas: **149081**
- Equipos preparados: **199** (131 resultados colectivos integrados, 68 equipos pendientes)

El respaldo contiene las cargas realmente realizadas, **no la totalidad de resultados oficiales de París 2024**. Existen medallas, identidades y participaciones pendientes de verificación. También está pendiente la comprobación exhaustiva de ciertos resúmenes derivados tras la interrupción del cargador colectivo.

Los scripts de ETL pueden conservarse en el repositorio como trazabilidad, pero no hace falta ejecutarlos para reproducir el estado final compartido.
