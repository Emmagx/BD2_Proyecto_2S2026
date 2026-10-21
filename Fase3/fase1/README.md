# Fase 1 — Preparación y corrección de datos

Esta carpeta contiene la implementación de la primera etapa de la Fase 3:
dejar listos los insumos que usarán las colecciones de MongoDB.

## Ejecutar

```bash
cd Fase3
./fase1/scripts/run_fase1.sh
```

Fuentes disponibles:

```bash
./fase1/scripts/run_fase1.sh --fuente pg    # PostgreSQL (contenedor postgres_cali)
./fase1/scripts/run_fase1.sh --fuente csv   # CSV de Fase2/csv-limpios
```

Sin `--fuente`, intenta PostgreSQL y cae automáticamente a CSV.

## Salidas

| Archivo | Qué es |
|---|---|
| `datos/insumos/sedes_olimpiadas.csv` | 61 sedes verificadas |
| `datos/insumos/alias_paises.csv` | Alias únicos en español |
| `datos/dim_juegos.csv` | 62 juegos con categoría y sede |
| `datos/dim_sedes.csv` | 61 juegos con sede |
| `datos/dim_alias_paises.csv` | Alias validados |
| `datos/dim_paises_normalizados.csv` | Nombres originales + normalizados |
| `datos/MANIFEST.csv` | Checksums de los entregables |

La constancia con fecha/hora, conteos y validaciones está en
`evidencia/validacion_fase1.md` y `evidencia/validacion_fase1.json`.

## Scripts

| Script | Responsabilidad |
|---|---|
| `00_generar_insumos.py` | Genera y valida las sedes y alias curados |
| `01_generar_dim_juegos.py` | Construye `dim_juegos` y `dim_sedes` |
| `02_generar_alias_paises.py` | Valida/deduplica alias contra `PAIS` |
| `03_generar_nombres_normalizados.py` | Normaliza países y atletas con fallback |
| `04_validar_fase1.py` | Valida y genera evidencia |

No hay dependencias externas: solo Python 3.10+ y, opcionalmente, Docker para
leer PostgreSQL. Si no hay Docker, use `--fuente csv`.
