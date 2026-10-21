# Fase 5 - Validación final

**Fecha y hora:** 2026-10-21T13:32:50-06:00  
**Host:** `Ema-Ubuntu` · **Python:** 3.10.12  
**MongoDB:** `olimpiadas_mongo`

## 1. Conteos

| Colección | Documentos | Esperado |
|---|---:|---:|
| `atletas` | 145,500 | 145,500 |
| `resultados` | 156,032 | 156,032 |
| `paises` | 247 | 247 |
| `catalogos` | 3,617 | 3,617 |

## 2. Validaciones

| Validación | Resultado |
|---|---|
| Suma de `atletas[]` en resultados | 308,238 |
| Atletas con participación | 145,262 |
| Regiones (países + catálogo) | 2,540 + 14 |
| Ciudades (países + catálogo) | 22,353 + 20 |
| Población en países | 11,136 |
| Resultados multipaís | 17,308 (empates 9,616, no empates 7,692) |
| Marcados para revisar | 45 |
| Equipos mixtos | 264 |
| Medallas (Oro/Plata/Bronce/Sin) | 6,953 / 6,880 / 6,830 / 135,369 |
| Fallos | **0** |

## 3. Rendimiento

| Consulta | Mediana (ms) | Plan |
|---|---:|---|
| Atleta por nombre | 1.747 | FETCH, IXSCAN |
| País por NOC | 2.103 | FETCH, IXSCAN |
| Detalle país, 100 | 5.103 | FETCH, IXSCAN |

## 4. Controles

```json
{
  "phelps": {
    "participaciones": 30,
    "juegos": 5,
    "anios": [
      2000,
      2004,
      2008,
      2012,
      2016
    ],
    "deportes": [
      "Swimming (Aquatics)"
    ],
    "medallas": {
      "oro": 23,
      "plata": 3,
      "bronce": 2,
      "total": 28
    }
  },
  "guatemala": {
    "participaciones": 463,
    "atletas": 254,
    "juegos": 18,
    "anios": [
      1952,
      1968,
      1972,
      1976,
      1980,
      1984,
      1988,
      1992,
      1996,
      2000,
      2004,
      2008,
      2010,
      2012,
      2014,
      2016,
      2020
    ],
    "deportes": [
      "Alpine Skiing (Skiing)",
      "Artistic Gymnastics (Gymnastics)",
      "Athletics",
      "Badminton",
      "Boxing",
      "Canoe Slalom (Canoeing)",
      "Cross Country Skiing (Skiing)",
      "Cycling Road (Cycling)",
      "Cycling Track (Cycling)",
      "Equestrian Eventing (Equestrian)",
      "Equestrian Jumping (Equestrian)",
      "Fencing",
      "Football (Football)",
      "Judo",
      "Modern Pentathlon",
      "Rowing",
      "Sailing",
      "Shooting",
      "Swimming (Aquatics)",
      "Taekwondo",
      "Weightlifting",
      "Wrestling"
    ],
    "medallas": {
      "oro": 0,
      "plata": 1,
      "bronce": 0,
      "total": 1
    },
    "medallasAtleta": {
      "oro": 0,
      "plata": 1,
      "bronce": 0,
      "total": 1
    },
    "medallasMixtas": {
      "oro": 0,
      "plata": 0,
      "bronce": 0,
      "total": 0
    },
    "primerAnio": 1952,
    "ultimoAnio": 2020
  }
}
```

## 5. Reproducción

```bash
cd Fase3
./run_all.sh
```
