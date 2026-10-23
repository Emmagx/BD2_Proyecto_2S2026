# Fase 3 — Restaurar MongoDB para el equipo (4 colecciones)

 **no deben ejecutar los 55 scripts de carga**. Deben restaurar los datos ya procesados con `restaurar_fase3.ps1`.

## Archivos

- `Fase3/restaurar_fase3.ps1` (usar la nueva versión de cuatro colecciones).
- `Fase3/paris2024/respaldos/olimpiadas_mongo_fase3.archive.gz` (copia final que comparte quien realizó la carga, por Drive). **El respaldo no está en GitHub**.
- Docker Desktop con un contenedor MongoDB corriendo, normalmente `mongo_fase3`, y las herramientas `mongorestore` y `mongosh` dentro del contenedor.

## Cómo instalar en la computadora 

1. Obtener el código del repositorio y descargar el respaldo final compartido.
2. Colocar el respaldo en `Fase3/paris2024/respaldos/olimpiadas_mongo_fase3.archive.gz`.
3. Abrir PowerShell dentro de `Fase3` y comprobar que el contenedor esté en ejecución.
4. Ejecutar una comprobación sin modificar nada:

```powershell
.\restaurar_fase3.ps1
```

5. Restaurar:

```powershell
.\restaurar_fase3.ps1 -Reemplazar
```

Si el contenedor tiene otro nombre:

```powershell
.\restaurar_fase3.ps1 -Contenedor mi_mongo -Reemplazar
```

Si la política de ejecución bloquea el archivo:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\restaurar_fase3.ps1 -Reemplazar
```

**Cuidado:** `-Reemplazar` aplica `mongorestore --drop` a las **cuatro colecciones principales** del destino. No usar sobre una base cuyos datos deban conservarse. El script **no elimina otras colecciones preexistentes**: para ver exactamente cuatro en `show collections`, usar una base `olimpiadas_mongo` inicialmente vacía. No borraremos colecciones auxiliares automáticamente.

## ¿Qué se restaura?

Solamente estas cuatro colecciones, incluso si el respaldo incluye seis:

- `resultados`: 160,244 documentos (4,212 de París 2024 y 156,032 históricos).
- `atletas`: 149,081 documentos.
- `paises`: 247 documentos.
- `catalogos`: 3,618 documentos.

No se importan `paris2024_fuente` ni `paris2024_equipos_preparados`. Esas dos son auxiliares para ETL y auditoría, no necesarias para consultar el modelo principal ya cargado. Para repetir el ETL o auditar casos pendientes, conservar una copia completa de seis colecciones en el equipo de origen.

## Comprobar las consultas

```powershell
docker exec -it mongo_fase3 mongosh olimpiadas_mongo
```

Dentro de MongoDB:

```javascript
show collections
db.resultados.countDocuments({})
db.resultados.countDocuments({"edicion.anio":2024})
db.resultados.countDocuments({paises:"GUA", "medalla.nombre":{$in:["Gold","Silver","Bronze"]}})
```

El último ejemplo demuestra el acceso a un campo anidado (`medalla.nombre`), no `medalla` como texto.

## Alcance

El respaldo refleja las cargas realmente implementadas; **no incluye todos los resultados oficiales de París 2024**. Hay posiciones, medallas e identidades pendientes de revisión. La verificación final de conteos no sustituye una auditoría exhaustiva de los resúmenes derivados de atletas y países.
