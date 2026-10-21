# 05 — Fase 4: atletas y países

**Objetivo:** construir las colecciones `atletas` y `paises`, con perfiles y
resúmenes derivados de `resultados`.

**Depende de:** `resultados` cargado.

**Scripts:**

| Script | Qué hace |
|---|---|
| `fase4/scripts/01_atletas.py` | Perfiles de 145,500 atletas + `resumen` |
| `fase4/scripts/02_paises.py` | 247 países con geografía, población, sedes y `resumen` |
| `fase4/run_fase4.sh` | Ejecuta ambos y guarda log en `evidencia/fase4/` |

```bash
cd Fase3
./fase4/run_fase4.sh
# o:
../.venv/bin/python fase4/scripts/01_atletas.py --recrear
../.venv/bin/python fase4/scripts/02_paises.py --recrear
```

---

## 1. `atletas` (145,500)

Perfil desde `ATLETA`, con ciudad/región/país de nacimiento. **No** se embebe
el historial de participaciones: la ficha se arma consultando `resultados`.

```json
{
  "_id": 93860,
  "nombre": "Michael Phelps",
  "nombreNormalizado": "michael phelps",
  "normalizado": true,
  "sexo": "M",
  "fechaNacimiento": "1985-06-30",
  "fechaFallecimiento": null,
  "altura": 193.0,
  "peso": 91.0,
  "lugarNacimiento": {
    "ciudad": "Baltimore", "region": "Maryland",
    "pais": "United States", "paisNoc": "USA"
  },
  "resumen": {
    "participaciones": 30,
    "juegos": 5,
    "anios": [2000, 2004, 2008, 2012, 2016],
    "deportes": ["Swimming (Aquatics)"],
    "medallas": { "oro": 23, "plata": 3, "bronce": 2, "total": 28 }
  }
}
```

El `resumen` se calcula con una agregación sobre `resultados`
(`$unwind: atletas`, `$group by atletas.id`, `$merge` en `atletas`).
Los 238 atletas sin participación conservan el resumen en cero.

## 2. `paises` (247)

Perfil, regiones con ciudades, población histórica, sedes y resumen.

```json
{
  "_id": 86,
  "nombre": "Guatemala",
  "noc": "GUA",
  "nombreNormalizado": "guatemala",
  "alias": [],
  "aliasNormalizado": [],
  "regiones": [
    { "id": 100, "nombre": "Guatemala",
      "ciudades": [{ "id": 500, "nombre": "Ciudad de Guatemala",
                     "lat": 14.63, "long": -90.51 }] }
  ],
  "poblacion": [{ "anio": 1960, "cantidad": 4128880 }],
  "sedes": [],
  "resumen": {
    "participaciones": 463,
    "atletas": 254,
    "juegos": 18,
    "anios": [1952, 1968, 1972, 1976, 1980, 1984, 1988, 1992, 1996, 2000, 2004, 2008, 2010, 2012, 2014, 2016, 2020],
    "deportes": ["Athletics", "Badminton"],
    "medallas": { "oro": 0, "plata": 1, "bronce": 0, "total": 1 },
    "medallasAtleta": { "oro": 0, "plata": 1, "bronce": 0, "total": 1 },
    "medallasMixtas": { "oro": 0, "plata": 0, "bronce": 0, "total": 0 },
    "primerAnio": 1952, "ultimoAnio": 2020
  }
}
```

Reglas de resumen:

- `participaciones`: suma de atletas de ese país en todos los resultados.
- `atletas`: IDs únicos.
- `juegos`, `anios`, `deportes`: conjuntos únicos.
- `medallas`: **una por país/equipo por resultado**, excluyendo equipos
  mixtos. Los empates suman una medalla a cada país/equipo.
- `medallasAtleta`: conteo por participación de atleta (métrica secundaria).
- `medallasMixtas`: medallas de equipos mixtos, separadas.
- `sedes`: desde `dim_sedes.csv`, con año, temporada, categoría y ciudad.

## 3. Datos que debes conocer

- `paises` contiene **2,540 regiones** y **22,353 ciudades** asignables.
  Las **14 regiones sin país** y **20 ciudades sin país/región** del dataset
  no se inventan: se conservan en `catalogos` como `region_sin_pais` y
  `ciudad_sin_pais`. Así los 2,554 regiones y 22,373 ciudades quedan
  representados en la base.
- `aliasNormalizado` permite buscar “Grecia” sin cambiar `nombre: "Greece"`.
- `normalizado` indica si el nombre se pudo normalizar; si no, se conserva el
  original.

## 4. Evidencia

- `evidencia/fase4/atletas.json`: conteos y control de Phelps.
- `evidencia/fase4/paises.json`: Guatemala, Grecia y ciudades sin región.
- `evidencia/fase4/ejecucion_<fecha>.log`.
