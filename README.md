# Proyecto 2 — Sistemas de Bases de Datos 2

**Universidad de San Carlos de Guatemala — Facultad de Ingeniería**  
**Curso:** Sistemas de Bases de Datos 2 — 2S2026  
**Integrantes:** Norma Elizabeth Canú Xico (202300768), Brayan Emanuel García (202300848), Valery Nicolle Gálvez García (202200141)

Este repositorio contiene las tres fases del proyecto de las Olimpiadas:

1. **Fase 1:** creación de la base de datos relacional y limpieza de datos.
2. **Fase 2:** respaldos y restauración de PostgreSQL.
3. **Fase 3:** migración a MongoDB, con 4 colecciones, scripts, evidencia y
   consultas de atleta/país.

> **Estado actual:** Fase 3 implementada y validada. Última corrida:
> **21/10/2026 13:32:50**, **0 fallos**. Ver
> [`Fase3/evidencia/fase5/validacion.md`](Fase3/evidencia/fase5/validacion.md).

---

## 1. Mapa del repositorio

```text
BD2_Proyecto_2S2026/
├── Fase1/                  Base relacional, ETL y documentación
│   ├── docs/               Decisiones de modelado y diagramas
│   ├── postgresql/         DDL, consultas y procedimientos
│   ├── scripts/            ETL de los CSV
│   ├── datosPadre/         Fuentes crudas
│   └── csv-limpios/        CSV de trabajo de la Fase 1
├── Fase2/                  PostgreSQL en Docker y respaldos
│   ├── init/               Esquema, índices y procedimientos
│   ├── tools/              Backups/restauración
│   ├── cargas/             Cargas por deporte/atleta
│   ├── backups/            Respaldos físicos (locales)
│   └── Documentacion/      Informe técnico de respaldos
└── Fase3/                  Migración a MongoDB (entrega actual)
    ├── docker-compose.yml  MongoDB 7
    ├── run_all.sh          Pipeline completo
    ├── lib/                Utilidades compartidas
    ├── fase1/              Preparación y correcciones
    ├── fase2/              Catálogos
    ├── fase3/              Resultados
    ├── fase4/              Atletas y países
    ├── fase5/              Índices, validación y consultas
    ├── docs/               Documentación de la Fase 3
    └── evidencia/          Reportes y logs con fecha/hora
```

---

## 2. Flujo del proyecto

```text
PostgreSQL: olimpiadas_db (13 tablas, 156,032 resultados)
        │
        │  Fase 1: auditoría, sedes, categorías, alias, normalización
        ▼
CSV de trabajo (dim_juegos, dim_sedes, alias, nombres)
        │
        │  Fase 2: catálogos
        ▼
catalogos (3,617)
        │
        │  Fase 3: un documento por resultado
        ▼
resultados (156,032)
        │
        │  Fase 4: perfiles y resúmenes
        ▼
atletas (145,500) + paises (247)
        │
        │  Fase 5: 14 índices + validación
        ▼
consultas de atleta y país (≈ 2–5 ms)
```

La base objetivo es **`olimpiadas_mongo`** en MongoDB 7, contenedor
`mongo_fase3`.

---

## 3. Fase 3: las 4 colecciones

| Colección | Grano | Qué contiene |
|---|---|---|
| `atletas` | 1 atleta | Perfil, nacimiento y `resumen` derivado. Sin historial embebido |
| `resultados` | 1 fila de `RESULTADO` | Edición, deporte, disciplina, evento, posición, estado, medalla, `atletas[]`, `paises[]`, `multipais` |
| `paises` | 1 país | Regiones/ciudades, población, `sedes[]` y `resumen` |
| `catalogos` | 1 entidad | Juegos, deportes, disciplinas, eventos, medallas y geografía sin país |

Conteos finales:

| Colección | Documentos |
|---|---:|
| `atletas` | 145,500 |
| `resultados` | 156,032 |
| `paises` | 247 |
| `catalogos` | 3,617 |

- Participaciones dentro de `resultados.atletas[]`: **308,238**.
- Medallas: 6,953 oro, 6,880 plata, 6,830 bronce, 135,369 sin medalla.
- 14 regiones y 20 ciudades sin país se conservan en `catalogos` como
  `region_sin_pais` y `ciudad_sin_pais`; no se inventa un país.

Detalle del modelo: [`Fase3/docs/01_Diseno_4_Colecciones.md`](Fase3/docs/01_Diseno_4_Colecciones.md).

---

## 4. Cómo ejecutar la Fase 3

### Requisitos

- Docker y Docker Compose.
- Contenedor PostgreSQL `postgres_cali` con `olimpiadas_db` completo.
- Python 3.10+ y `pymongo`.

```bash
cd /home/emma/BD2_Proyecto_2S2026
.venv/bin/python -m pip install -r Fase3/requirements.txt
```

### Todo el pipeline

```bash
cd Fase3
./run_all.sh
```

Esto ejecuta, en orden:

1. Fase 1: insumos, `dim_juegos`, `dim_sedes`, alias y normalización.
2. Fase 2: `catalogos`.
3. Fase 3: `resultados`.
4. Fase 4: `atletas` y `paises`.
5. Fase 5: índices y validación.

MongoDB se levanta con `docker compose up -d`. El `run_all.sh` ya lo hace.

### Por fase

```bash
./fase1/scripts/run_fase1.sh --fuente pg
./fase2/run_fase2.sh
./fase3/run_fase3.sh
./fase4/run_fase4.sh
./fase5/run_fase5.sh
```

Cada fase guarda su log en `Fase3/evidencia/faseN/ejecucion_<fecha>.log`.

| Fase | Scripts principales | Salida |
|---|---|---|
| 1 | `00_generar_insumos.py`, `01_generar_dim_juegos.py`, `02_generar_alias_paises.py`, `03_generar_nombres_normalizados.py`, `04_validar_fase1.py` | 62 juegos, 61 sedes, 109 alias, nombres normalizados |
| 2 | `00_verificar_entorno.py`, `01_catalogos.py` | 3,617 catálogos |
| 3 | `01_resultados.py` | 156,032 resultados |
| 4 | `01_atletas.py`, `02_paises.py` | 145,500 atletas, 247 países |
| 5 | `01_indices.py`, `02_validar.py` | 14 índices y validación |

---

## 5. Cómo usar los scripts de consulta

Los dos scripts están en `Fase3/fase5/scripts/`. Los comandos usan
`../.venv/bin/python` porque ese entorno tiene `pymongo`; si usas otro
entorno, reemplázalo por tu Python con `pymongo` instalado.

### (c) Consulta de atleta

```bash
cd Fase3

../.venv/bin/python fase5/scripts/03_consulta_atleta.py "Michael Phelps"
../.venv/bin/python fase5/scripts/03_consulta_atleta.py "Michael Phelps" --anio 2008
../.venv/bin/python fase5/scripts/03_consulta_atleta.py "Usain Bolt" --medalla oro
../.venv/bin/python fase5/scripts/03_consulta_atleta.py "Phelps" --deporte natacion --pais USA
../.venv/bin/python fase5/scripts/03_consulta_atleta.py --id 93860 --json
```

Opciones:

- `--id`: ID exacto del atleta.
- `--deporte`: deporte (acepta inglés del dataset o alias español:
  `natacion`, `atletismo`, `ciclismo`, …).
- `--pais`: NOC o nombre del país representado.
- `--anio`: año olímpico.
- `--medalla`: `oro`, `plata`, `bronce`, `ninguna`.
- `--todos`: mostrar todos los homónimos.
- `--json`: salida estructurada.

Salida: perfil, nacimiento, fechas, altura/peso, número de juegos,
participaciones, medallas, años, deportes y tabla de resultados.

### (d) Consulta de país

```bash
../.venv/bin/python fase5/scripts/04_consulta_pais.py "Guatemala"
../.venv/bin/python fase5/scripts/04_consulta_pais.py "Estados Unidos" --anio 2012
../.venv/bin/python fase5/scripts/04_consulta_pais.py GUA --limite 0
../.venv/bin/python fase5/scripts/04_consulta_pais.py "Grecia" --deporte atletismo
../.venv/bin/python fase5/scripts/04_consulta_pais.py "Japón" --json
```

Opciones:

- `--noc`: código exacto.
- `--deporte`: deporte (inglés o alias español).
- `--medalla`: `oro`, `plata`, `bronce`, `ninguna`.
- `--anio`: año.
- `--limite`: máximo de resultados; `0` = todos.
- `--json`: salida estructurada.

Salida: perfil, regiones/ciudades, población, si fue sede y en qué años,
resumen global, medallas por evento/atleta, **medallas por año** y detalle de
resultados.

La guía completa de consultas está en
[`Fase3/docs/06_Fase5_Indices_Validacion_Consultas.md`](Fase3/docs/06_Fase5_Indices_Validacion_Consultas.md).

---

## 6. Documentación por fase

### Fase 1

- [`Fase1/README.md`](Fase1/README.md) — resumen de la fase.
- [`Fase1/docs/README.md`](Fase1/docs/README.md) — decisiones de modelado,
  normalización, índices y capturas.
- [`Fase1/postgresql/DB2.sql`](Fase1/postgresql/DB2.sql) — DDL.
- [`Fase1/postgresql/storageP.sql`](Fase1/postgresql/storageP.sql) —
  procedimientos de atleta y país.

### Fase 2

- [`Fase2/README.md`](Fase2/README.md) — cómo levantar PostgreSQL.
- [`Fase2/Documentacion/Informe_Tecnico_Con_Carga3.md`](Fase2/Documentacion/Informe_Tecnico_Con_Carga3.md)
  — informe de respaldos y restauración.
- [`Fase2/docker-compose.yml`](Fase2/docker-compose.yml) — configuración del
  contenedor.
- [`Fase2/init/03_stored_procedures.sql`](Fase2/init/03_stored_procedures.sql)
  — consultas equivalentes en PostgreSQL.

### Fase 3

- [`Fase3/README.md`](Fase3/README.md) — guía técnica de la migración.
- [`Fase3/docs/01_Diseno_4_Colecciones.md`](Fase3/docs/01_Diseno_4_Colecciones.md)
  — modelo documental.
- [`Fase3/docs/02_Fase1_Implementacion.md`](Fase3/docs/02_Fase1_Implementacion.md)
  — preparación y correcciones.
- [`Fase3/docs/03_Fase2_Catalogos.md`](Fase3/docs/03_Fase2_Catalogos.md).
- [`Fase3/docs/04_Fase3_Resultados.md`](Fase3/docs/04_Fase3_Resultados.md).
- [`Fase3/docs/05_Fase4_Atletas_Paises.md`](Fase3/docs/05_Fase4_Atletas_Paises.md).
- [`Fase3/docs/06_Fase5_Indices_Validacion_Consultas.md`](Fase3/docs/06_Fase5_Indices_Validacion_Consultas.md).
- [`Fase3/docs/07_Consultas_IA.md`](Fase3/docs/07_Consultas_IA.md) — capturas
  del proceso de consulta a IA.
- [`Fase3/evidencia/fase5/validacion.md`](Fase3/evidencia/fase5/validacion.md)
  — reporte final con fecha/hora.
- [`Fase3/fase1/README.md`](Fase3/fase1/README.md) — README de la Fase 1 de la
  migración.

### Enunciados

- [`Fase2/775_Proyecto_2_2S2026.pdf`](Fase2/775_Proyecto_2_2S2026.pdf).
- [`Fase3/Enunciado proyecto 3-1.pdf`](<Fase3/Enunciado proyecto 3-1.pdf>).

---

## 7. Evidencia y consultas a IA

La evidencia de ejecución está organizada por fase:

- `Fase3/evidencia/fase2/` — entorno y catálogos.
- `Fase3/evidencia/fase3/` — resultados y conteos.
- `Fase3/evidencia/fase4/` — atletas y países.
- `Fase3/evidencia/fase5/` — índices, validación y rendimiento.
- `Fase3/evidencia/run_all_<fecha>.log` — corrida completa.
- [`Fase3/fase1/evidencia/validacion_fase1.md`](Fase3/fase1/evidencia/validacion_fase1.md)
  — validación de la preparación.

Las capturas de las consultas a IA están en
[`Fase3/docs/07_Consultas_IA.md`](Fase3/docs/07_Consultas_IA.md):

| Momento | Imagen |
|---|---|
| Planteamiento inicial | [`ia1.png`](Fase3/docs/images/ia1.png) |
| Análisis del esquema | [`ia2.png`](Fase3/docs/images/ia2.png) |
| Propuesta de 4 colecciones | [`i3.png`](Fase3/docs/images/i3.png) |
| Revisión de la propuesta | [`ia4.png`](Fase3/docs/images/ia4.png) |
| Separar `olimpiadas`/`resultados` | [`ia5.png`](Fase3/docs/images/ia5.png) |
| Revisión de CSV y contenedor | [`ia6.png`](Fase3/docs/images/ia6.png) |

---

## 8. Decisiones y correcciones importantes

1. **El contenedor PostgreSQL ya está completo.** Tiene 156,032 resultados y
   308,238 participaciones; las fases 2–5 lo usan como fuente.
2. **Sedes corregidas.** El mapeo crudo por ciudad homónima fallaba
   (Atenas/Alabama, París/Kentucky, Roma/Queensland). Se usa una tabla curada
   de 61 juegos con sede.
3. **Categoría de juego.** `Senior`, `Juvenil`, `Intercalado`, `Atipico` para
   no mezclar Vancouver 2010 con Singapur 2010 o Londres 2012 con Innsbruck
   2012.
4. **Nombres.** Se conserva el original y se agrega `nombreNormalizado`. Si no
   se puede normalizar, se conserva y se marca `normalizado: false`.
5. **Medallas de país.** Se cuenta una por país/equipo por resultado; los
   empates suman una a cada país. `medallasAtleta` es la métrica secundaria y
   los equipos mixtos se separan en `medallasMixtas`.
6. **Multipaís.** 17,308 resultados tienen atletas de más de un país, pero
   9,616 son empates legítimos y el resto incluye equipos, estados no
   completados y 45 casos marcados `revisar`. No es un error masivo.
7. **Geografía sin país.** 14 regiones y 20 ciudades no tienen país/región
   asignable; se conservan en `catalogos` para no perder datos.

---

## 9. Checklist para la defensa

- [ ] `docker compose up -d` y `./run_all.sh` terminan con **0 fallos**.
- [ ] Mostrar los conteos: 145,500 atletas, 156,032 resultados, 247 países,
  3,617 catálogos.
- [ ] Ejecutar `03_consulta_atleta.py "Michael Phelps"` y el filtro `--anio
  2008`.
- [ ] Ejecutar `04_consulta_pais.py "Guatemala"` y `"Grecia"` (sedes).
- [ ] Mostrar `explain` con `IXSCAN` y los tiempos (~2–5 ms).
- [ ] Enseñar la evidencia con fecha/hora y las capturas de IA.
- [ ] Explicar por qué `resultados` es una colección aparte y por qué
  `atletas` no embebe el historial.
- [ ] Explicar que las medallas de país se cuentan por resultado/equipo, no por
  atleta.

---

## 10. Nota sobre el entorno

- MongoDB corre en `127.0.0.1:27017`, contenedor `mongo_fase3`.
- El `docker-compose.yml` ejecuta `mongod` como root del contenedor por el
  *user-namespace remapping* del equipo; el puerto no se expone a la red.
- PostgreSQL sigue en `postgres_cali`, puerto `5432`.
- Para detener MongoDB: `cd Fase3 && docker compose stop`.
- Para reconstruir desde cero: `docker compose down -v` (borra el volumen) y
  `./run_all.sh`.
