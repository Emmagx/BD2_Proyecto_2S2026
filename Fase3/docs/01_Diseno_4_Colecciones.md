# 01 — Diseño de las 4 colecciones

**Base:** `olimpiadas_mongo` (MongoDB 7.0)  
**Diseño acordado:** `atletas`, `resultados`, `paises`, `catalogos`.

---

## 1. Regla de diseño

- **`atletas`**: perfil del atleta + resumen derivado. **Sin** array de
  participaciones (la ficha se arma con `resultados`).
- **`resultados`**: un documento por fila de `RESULTADO`; los atletas del
  resultado van dentro (`atletas[]`). Es la fuente de verdad de los hechos.
- **`paises`**: perfil geográfico, población, sedes y resumen precalculado.
- **`catalogos`**: juegos, deportes, disciplinas, eventos y medallas.

```text
                         ┌──────────────────────────┐
                         │        catalogos         │
                         │ juego / deporte /        │
                         │ disciplina / evento /    │
                         │ medalla                  │
                         └────────────▲─────────────┘
                                      │ id
┌──────────────┐        ┌─────────────┴─────────────┐        ┌──────────────┐
│   atletas    │        │        resultados         │        │    paises    │
│   (perfil)   │◄───────┤  atletas[]  /  paises[]   ├───────►│  (catálogo)  │
│   + resumen  │  id    │  edicion / evento / medalla│  noc   │  + resumen   │
└──────────────┘        └───────────────────────────┘        └──────────────┘
        │                                                            ▲
        └──────────── lugarNacimiento ──────────────────────────────┘
```

---

## 2. `resultados` (156,032)

Un documento por `RESULTADO`. La medalla vive una sola vez en el resultado.

```json
{
  "_id": 25,
  "edicion": { "id": 9, "anio": 1900, "temporada": "Summer", "categoria": "Senior" },
  "deporte": { "id": 28, "nombre": "Tennis" },
  "disciplina": { "id": 2, "nombre": "Tennis" },
  "evento": { "id": 2, "nombre": "Doubles, Men (Olympic)" },
  "posicion": 3,
  "empate": true,
  "estado": "COMPLETED",
  "medalla": { "codigo": "BRONCE", "nombre": "Bronze" },
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

Reglas:

- `paises` = NOC únicos de `atletas[]`.
- `multipais` = `paises.length > 1`.
- `paisEquipo` = NOC si `paises.length == 1`; si no, `null`.
- `equipoMixto` = `true` solo para equipos mixtos reales (YOG, equipos
  combinados).
- `revisar` = `true` para casos no empatados con medalla y varios países que
  no sean equipos mixtos.
- `medalla` = `null` cuando `ID_MEDALLA = 1` (“No medal”).
- Para el medallero de país: **una medalla por país/equipo por resultado**.
  Un empate con FRA y GBR suma un bronce a cada uno, no cuatro por los atletas.

---

## 3. `atletas` (145,500)

```json
{
  "_id": 93860,
  "nombre": "Michael Phelps",
  "nombreNormalizado": "michael phelps",
  "sexo": "M",
  "fechaNacimiento": "1985-06-30",
  "fechaFallecimiento": null,
  "altura": 193.0,
  "peso": 91.0,
  "lugarNacimiento": {
    "ciudad": "Baltimore",
    "region": "Maryland",
    "pais": "United States",
    "paisNoc": "USA"
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

`resumen` se calcula desde `resultados`; no se embebe el historial completo.

---

## 4. `paises` (247)

```json
{
  "_id": 86,
  "nombre": "Guatemala",
  "noc": "GUA",
  "nombreNormalizado": "guatemala",
  "alias": [],
  "regiones": [
    {
      "id": 100,
      "nombre": "Guatemala",
      "ciudades": [
        { "id": 500, "nombre": "Ciudad de Guatemala", "lat": 14.63, "long": -90.51 }
      ]
    }
  ],
  "poblacion": [{ "anio": 1960, "cantidad": 4128880 }],
  "sedes": [],
  "resumen": {
    "participaciones": 463,
    "atletas": 254,
    "juegos": 18,
    "anios": [1952, 1968, 1972, 1976, 1980, 1984, 1988, 1992, 1996, 2000, 2004, 2008, 2010, 2012, 2014, 2016, 2020],
    "deportes": ["Athletics", "Badminton", "Boxing"],
    "medallas": { "oro": 0, "plata": 1, "bronce": 0, "total": 1 },
    "medallasAtleta": { "oro": 0, "plata": 1, "bronce": 0, "total": 1 }
  }
}
```

`sedes` se llena desde `fase1/datos/dim_sedes.csv`; no desde el mapeo crudo.

---

## 5. `catalogos` (3,583)

Una colección para los cinco catálogos. `_id` con prefijo para evitar choques:

```json
{ "_id": "juego:16", "tipo": "juego", "anio": 2012, "temporada": "Summer",
  "categoria": "Senior", "sedes": [{ "ciudad": "Londres", "paisNoc": "GBR" }] }

{ "_id": "deporte:28", "tipo": "deporte", "nombre": "Tennis", "nombreNormalizado": "tennis" }

{ "_id": "disciplina:2", "tipo": "disciplina", "nombre": "Tennis", "deporteId": 28 }

{ "_id": "evento:2", "tipo": "evento", "nombre": "Doubles, Men (Olympic)",
  "nombreNormalizado": "doubles men olympic", "deporteId": 28, "disciplinaId": 2 }

{ "_id": "medalla:2", "tipo": "medalla", "codigo": "BRONCE", "nombre": "Bronze" }
```

Conteo: 62 juegos + 93 deportes + 1,520 disciplinas + 1,904 eventos + 4 medallas
= **3,583**.

---

## 6. Mapa de las 13 tablas

| Tabla relacional | Destino |
|---|---|
| `PAIS` | `paises` (perfil) |
| `REGION` | `paises.regiones[]` |
| `CIUDAD` | `paises.regiones[].ciudades[]` y `atletas.lugarNacimiento` |
| `POBLACION` | `paises.poblacion[]` |
| `ATLETA` | `atletas` (perfil) |
| `RESULTADO` | `resultados` (documento base) |
| `RESULTADO_ATLETA` | `resultados.atletas[]` |
| `OLIMPIADA` | `catalogos` tipo `juego` + `resultados.edicion` |
| `CIUDAD_OLIMPIADA` | `catalogos` tipo `juego`.sedes (corregido) |
| `DEPORTE` | `catalogos` tipo `deporte` + `resultados.deporte` |
| `DISCIPLINA` | `catalogos` tipo `disciplina` + `resultados.disciplina` |
| `EVENTO` | `catalogos` tipo `evento` + `resultados.evento` |
| `MEDALLA` | `catalogos` tipo `medalla` + `resultados.medalla` |

---

## 7. Índices

```text
atletas:
  { nombreNormalizado: 1 }
  { "lugarNacimiento.paisNoc": 1 }

resultados:
  { "atletas.id": 1, "edicion.anio": -1 }
  { "atletas.noc": 1, "edicion.anio": -1, "medalla.codigo": 1 }
  { "edicion.anio": 1, "medalla.codigo": 1 }
  { "evento.id": 1, "edicion.anio": 1 }
  { "deporte.id": 1, "edicion.anio": 1 }
  { multipais: 1, revisar: 1 }

paises:
  { noc: 1 }                 // único
  { nombreNormalizado: 1 }
  { alias: 1 }
  { "sedes.anio": 1 }

catalogos:
  { tipo: 1, nombreNormalizado: 1 }
  { tipo: 1, anio: 1 }
```

`atletas.id` y `atletas.noc` son arrays distintos: van en índices separados, no
en un mismo compuesto.

---

## 8. Consultas objetivo

- Atleta: `atletas.findOne({nombreNormalizado})` +
  `resultados.find({"atletas.id": id})`.
- País: `paises.findOne({noc})` +
  `resultados.find({"atletas.noc": noc})`.
- Medallero: `resultados` con medalla, agrupando por `edicion.anio` y
  `paises[]`/`paisEquipo`; una medalla por país/equipo por resultado.
- Evento: `resultados.find({"evento.id": ..., "edicion.anio": ...})`.
