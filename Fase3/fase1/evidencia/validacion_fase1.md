# Fase 1 - Validación y constancia de ejecución

**Fecha y hora:** 2026-10-20T23:54:34-06:00  
**Fuente:** pg  
**Host:** `Ema-Ubuntu` · **Python:** 3.10.12  
**Base de datos de origen:** `olimpiadas_db` (PostgreSQL 17, contenedor `postgres_cali`)

## 1. Entregables generados

| Archivo | Filas | Bytes | SHA-256 |
|---|---:|---:|---|
| `datos/insumos/sedes_olimpiadas.csv` | 61 | 4,309 | `c938417295618b08…` |
| `datos/insumos/alias_paises.csv` | 109 | 1,584 | `5d0c13fb2fb525fd…` |
| `datos/dim_juegos.csv` | 62 | 4,886 | `36a354373a623940…` |
| `datos/dim_sedes.csv` | 61 | 4,309 | `cd19ee9bfab65568…` |
| `datos/dim_alias_paises.csv` | 109 | 3,757 | `21b14809e80733a9…` |
| `datos/dim_paises_normalizados.csv` | 247 | 7,905 | `fdecfa25ae6ef0e5…` |

## 2. Categorías de juegos

| Categoría | Juegos |
|---|---:|
| Senior | 54 |
| Juvenil | 6 |
| Intercalado | 1 |
| Atipico | 1 |

Total: **62** juegos; **61** con sede; **1888** sin sede.

## 3. Casos especiales

| ID | Año | Temporada | Original | Categoría | Sede | País |
|---:|---:|---|---|---|---|---|
| 10 | 1906 | Summer | Unknown | Intercalado | Atenas | GRE |
| 32 | 1956 | Summer | Unknown | Senior | Estocolmo | SWE |
| 46 | 1888 | Unknown | Unknown | Atipico | — | — |
| 57 | 2010 | Summer | Summer | Juvenil | Singapur | SGP |
| 58 | 2014 | Summer | Summer | Juvenil | Nankín | CHN |
| 59 | 2012 | Winter | Winter | Juvenil | Innsbruck | AUT |
| 60 | 2016 | Winter | Winter | Juvenil | Lillehammer | NOR |
| 61 | 2018 | Summer | Summer | Juvenil | Buenos Aires | ARG |
| 62 | 2020 | Winter | Winter | Juvenil | Lausana | SUI |

## 4. Normalización de nombres

- Atletas procesados: **145,500**
- Normalizados correctamente: **145,399**
- Con fallback al original (no normalizables): **101**
- Nombres que cambiaron al normalizar: **145,399**
- Países con fallback: **0**

Ejemplos de fallback (se conserva el original):

| ID | Original | Normalizado |
|---:|---|---|
| 5527 | Tsоnka Vaysilova | Tsоnka Vaysilova |
| 21214 | Elxan Məmmədov | Elxan Məmmədov |
| 33189 | Zülfiyyə Hüseynova | Zülfiyyə Hüseynova |
| 41255 | İradə Aşumova | İradə Aşumova |
| 45417 | Emin Cəbrayilov | Emin Cəbrayilov |
| 55230 | Tofiq Heydərov | Tofiq Heydərov |
| 55231 | Asif Məlikov | Asif Məlikov |
| 55331 | Zlatаn Vasilev | Zlatаn Vasilev |
| 57257 | Vilayət Ağayev | Vilayət Ağayev |
| 57259 | Məmmədsalam Haciyev | Məmmədsalam Haciyev |

## 5. Corrección de sedes

El mapeo crudo `CIUDAD_OLIMPIADA → CIUDAD → REGION → PAIS` no coincide con la sede verificada en **26** juegos: **10** con país distinto, **5** sin país deducible y **11** sin fila de sede. La causa principal son ciudades homónimas (Atenas/Alabama, París/Kentucky, etc.).

| Juego | Ciudad curada | País curado | País crudo | Tipo |
|---:|---|---|---|---|
| 1 | Estocolmo | SWE | USA | pais_distinto |
| 2 | Amberes | BEL | (sin país) | sin_pais |
| 4 | París | FRA | USA | pais_distinto |
| 5 | Barcelona | ESP | VEN | pais_distinto |
| 7 | Atenas | GRE | USA | pais_distinto |
| 9 | París | FRA | USA | pais_distinto |
| 10 | Atenas | GRE | (sin fila en CIUDAD_OLIMPIADA) | sin_fila |
| 12 | Atenas | GRE | USA | pais_distinto |
| 15 | San Luis | USA | SEN | pais_distinto |
| 19 | Múnich | GER | (sin país) | sin_pais |
| 20 | Moscú | RUS | USA | pais_distinto |
| 22 | Tokio | JPN | (sin fila en CIUDAD_OLIMPIADA) | sin_fila |
| 24 | Melbourne | AUS | USA | pais_distinto |
| 26 | Roma | ITA | AUS | pais_distinto |
| 32 | Estocolmo | SWE | (sin fila en CIUDAD_OLIMPIADA) | sin_fila |
| 34 | Chamonix | FRA | (sin país) | sin_pais |
| 45 | Cortina d'Ampezzo | ITA | (sin país) | sin_pais |
| 53 | Squaw Valley | USA | (sin país) | sin_pais |
| 55 | Pyeongchang | KOR | (sin fila en CIUDAD_OLIMPIADA) | sin_fila |
| 56 | Pekín | CHN | (sin fila en CIUDAD_OLIMPIADA) | sin_fila |

## 6. Validaciones

| Validación | Resultado |
|---|---|
| 62 juegos sin IDs repetidos | OK |
| 61 sedes, 1888 sin sede | OK |
| Categorías esperadas | OK |
| NOC de sedes existen en PAIS | OK |
| Alias sin NOC inválidos | OK |
| Nombres originales sin modificar | OK |
| Fallos totales | **0** |

## 7. Reproducción

```bash
cd Fase3
./fase1/scripts/run_fase1.sh
```
