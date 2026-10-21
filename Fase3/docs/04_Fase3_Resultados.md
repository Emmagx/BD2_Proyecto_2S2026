# 04 — Fase 3: resultados

**Objetivo:** construir la colección `resultados` con **un documento por fila
de `RESULTADO`** y los atletas del resultado dentro.

**Depende de:** catálogos (Fase 2) y PostgreSQL completo.

**Scripts:**

| Script | Qué hace |
|---|---|
| `fase3/scripts/01_resultados.py` | Agrupa `RESULTADO` + `RESULTADO_ATLETA` y carga 156,032 documentos |
| `fase3/run_fase3.sh` | Ejecuta la fase y guarda log en `evidencia/fase3/` |

```bash
cd Fase3
./fase3/run_fase3.sh
# o:
../.venv/bin/python fase3/scripts/01_resultados.py --recrear
```

---

## 1. Consulta de origen

El script hace un `JOIN` entre `RESULTADO`, `RESULTADO_ATLETA`, `ATLETA`,
`PAIS`, `EVENTO`, `DISCIPLINA`, `DEPORTE`, `OLIMPIADA` y `MEDALLA`, y agrupa
con `json_agg` por `RESULTADO.ID`.

Eso evita el error de generar un documento por participación: el documento es
el resultado; los atletas son un arreglo.

## 2. Documento

```json
{
  "_id": 25,
  "edicion": { "id": 9, "anio": 1900, "temporada": "Summer", "categoria": "Senior" },
  "deporte": { "id": 1, "nombre": "Tennis" },
  "disciplina": { "id": 2, "nombre": "Doubles" },
  "evento": { "id": 2, "nombre": "Doubles, Men (Olympic)" },
  "posicion": 3,
  "empate": true,
  "estado": "COMPLETED",
  "medalla": { "id": 2, "codigo": "BRONCE", "nombre": "Bronze" },
  "atletas": [
    { "id": 10, "nombre": "Guy de la Chapelle", "noc": "FRA", "edad": 32 },
    { "id": 31, "nombre": "André Prévost", "noc": "FRA", "edad": 25 },
    { "id": 106, "nombre": "Harold Mahony", "noc": "GBR", "edad": 33 },
    { "id": 109, "nombre": "Arthur Norris", "noc": "GBR", "edad": null }
  ],
  "paises": ["FRA", "GBR"],
  "multipais": true,
  "paisEquipo": null,
  "equipoMixto": false,
  "revisar": false
}
```

Este ejemplo es el bronce compartido de 1900: dos equipos empatados en 3.º.
La medalla está una vez; para el medallero se cuenta **una por país/equipo**:
FRA +1 bronce, GBR +1 bronce. No se cuenta una por atleta.

## 3. Reglas

- `paises` = NOC únicos de `atletas[]`.
- `multipais` = `len(paises) > 1`.
- `paisEquipo` = NOC si solo hay un país; si no, `null`.
- `equipoMixto` = resultado multipaís de un evento mixto/juvenil
  (`Mixed`, `Youth`, `YOG`). Se separa para no mezclarlo con el medallero
  normal.
- `revisar` = multipaís, no empatado, con medalla y no marcado como equipo
  mixto. Son casos para revisar antes de usarlos en el medallero.
- `medalla` = `null` cuando `ID_MEDALLA = 1` (“No medal”).

## 4. Resultado de la carga

| Métrica | Cantidad |
|---|---:|
| Documentos | **156,032** |
| Participaciones dentro de `atletas[]` | **308,238** |
| Multipaís | 17,308 |
| — empatados | 9,616 |
| — no empatados | 7,692 |
| Equipos mixtos | 264 |
| Marcados `revisar` | 45 |
| Oro / Plata / Bronce / Sin medalla | 6,953 / 6,880 / 6,830 / 135,369 |

## 5. Evidencia

- `evidencia/fase3/resultados.json`: conteos, medallas y muestra del
  resultado 25.
- `evidencia/fase3/ejecucion_<fecha>.log`.
