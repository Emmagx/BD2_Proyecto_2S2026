# 03 — Fase 2: catálogos

**Objetivo:** construir la colección `catalogos` con juegos, deportes,
disciplinas, eventos y medallas.

**Depende de:** Fase 1 (`dim_juegos.csv`, `dim_sedes.csv`) y PostgreSQL
completo.

**Scripts:**

| Script | Qué hace |
|---|---|
| `fase2/scripts/00_verificar_entorno.py` | Verifica Python, pymongo, PostgreSQL, MongoDB e insumos |
| `fase2/scripts/01_catalogos.py` | Construye e inserta los 3,617 catálogos |
| `fase2/run_fase2.sh` | Ejecuta ambos y guarda log en `evidencia/fase2/` |

```bash
cd Fase3
./fase2/run_fase2.sh
# o por separado:
../.venv/bin/python fase2/scripts/00_verificar_entorno.py
../.venv/bin/python fase2/scripts/01_catalogos.py --recrear
```

---

## 1. Documentos

Una colección con cinco tipos de documento. El `_id` lleva prefijo para que no
choquen los IDs de tablas distintas:

```json
{ "_id": "juego:16", "tipo": "juego", "id": 16, "anio": 2012,
  "temporada": "Summer", "temporadaOriginal": "Summer",
  "categoria": "Senior",
  "sedes": [{ "ciudad": "Londres", "paisNoc": "GBR",
              "paisHistorico": "Gran Bretaña", "nota": "Sede única" }] }

{ "_id": "deporte:1", "tipo": "deporte", "id": 1,
  "nombre": "Tennis", "nombreNormalizado": "tennis" }

{ "_id": "disciplina:2", "tipo": "disciplina", "id": 2,
  "nombre": "Doubles", "nombreNormalizado": "doubles", "deporteId": 1 }

{ "_id": "evento:2", "tipo": "evento", "id": 2,
  "nombre": "Doubles, Men (Olympic)",
  "nombreNormalizado": "doubles men olympic",
  "deporteId": 1, "disciplinaId": 2 }

{ "_id": "medalla:2", "tipo": "medalla", "id": 2,
  "codigo": "BRONCE", "nombre": "Bronze", "nombreNormalizado": "bronze" }
```

- **Juego:** sale de `dim_juegos.csv`; la sede sale de `dim_sedes.csv`.
  Incluye `categoria` (Senior/Juvenil/Intercalado/Atipico) y la temporada
  original.
- **Deporte/disciplina/evento:** salen de `DEPORTE`, `DISCIPLINA` y
  `EVENTO`; se guarda la jerarquía (`deporteId`, `disciplinaId`).
- **Medalla:** catálogo de 4 valores; `No medal` queda con `codigo: null`.
- **Geografía sin país:** 14 regiones y 20 ciudades que el dataset no puede
  asignar a un país se guardan como `region_sin_pais` / `ciudad_sin_pais`,
  para no perder datos ni inventar un país.

## 2. Conteos

| Tipo | Documentos |
|---|---:|
| juego | 62 |
| deporte | 93 |
| disciplina | 1,520 |
| evento | 1,904 |
| medalla | 4 |
| region_sin_pais | 14 |
| ciudad_sin_pais | 20 |
| **Total** | **3,617** |

## 3. Evidencia

- `evidencia/fase2/verificacion_entorno.json`
- `evidencia/fase2/catalogos.json`
- `evidencia/fase2/ejecucion_<fecha>.log`

La evidencia incluye conteos por tipo y una muestra de juego/evento.
