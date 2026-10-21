# Fase 3 — Migración de las Olimpiadas a MongoDB

**Curso:** Sistemas de Bases de Datos 2 — USAC — 2S2026  
**Entrega:** 24 de octubre de 2026  
**Estado:** pipeline completo implementado y ejecutado (Fases 1–5).  
**Diseño:** 4 colecciones — `atletas`, `resultados`, `paises`, `catalogos`.

---

## 1. Inicio rápido

Requisitos:

- Docker y Docker Compose.
- Contenedor PostgreSQL `postgres_cali` con `olimpiadas_db` completo
  (156,032 resultados y 308,238 participaciones).
- Python 3.10+ y `pymongo`:
  ```bash
  cd /home/emma/BD2_Proyecto_2S2026
  .venv/bin/python -m pip install -r Fase3/requirements.txt
  ```

Ejecutar todo:

```bash
cd /home/emma/BD2_Proyecto_2S2026/Fase3
./run_all.sh
```

El pipeline tarda ~1–2 minutos y deja la evidencia en `evidencia/`.
Si quieres ejecutar fase por fase:

```bash
./fase1/scripts/run_fase1.sh --fuente pg   # preparación y correcciones
./fase2/run_fase2.sh                       # catálogos
./fase3/run_fase3.sh                       # resultados
./fase4/run_fase4.sh                       # atletas y países
./fase5/run_fase5.sh                       # índices y validación
```

MongoDB se levanta con `docker compose up -d` (puerto `127.0.0.1:27017`,
contenedor `mongo_fase3`). El compose ejecuta `mongod` como root del
contenedor por el *user-namespace remapping* de este equipo; el puerto queda
solo en loopback.

---

## 2. Qué hace cada fase

| Fase | Scripts | Resultado |
|---|---|---|
| **1. Preparación** | `fase1/scripts/00_generar_insumos.py`, `01_generar_dim_juegos.py`, `02_generar_alias_paises.py`, `03_generar_nombres_normalizados.py`, `04_validar_fase1.py` | `dim_juegos` (62), `dim_sedes` (61), alias, nombres normalizados |
| **2. Catálogos** | `fase2/scripts/00_verificar_entorno.py`, `01_catalogos.py` | `catalogos` (3,617) |
| **3. Resultados** | `fase3/scripts/01_resultados.py` | `resultados` (156,032) |
| **4. Atletas y países** | `fase4/scripts/01_atletas.py`, `02_paises.py` | `atletas` (145,500), `paises` (247) |
| **5. Índices y validación** | `fase5/scripts/01_indices.py`, `02_validar.py` | 14 índices + reporte final |
| **Consultas** | `fase5/scripts/03_consulta_atleta.py`, `04_consulta_pais.py` | requisitos (c) y (d) |

Cada fase tiene su `run_faseN.sh` y deja un log
`evidencia/faseN/ejecucion_<fecha>.log`.

---

## 3. Resultado final

| Colección | Documentos |
|---|---:|
| `atletas` | 145,500 |
| `resultados` | 156,032 |
| `paises` | 247 |
| `catalogos` | 3,617 |

- Suma de `resultados.atletas[]`: **308,238** (todas las participaciones).
- Medallas: 6,953 oro, 6,880 plata, 6,830 bronce, 135,369 sin medalla.
- Multipaís: 17,308 (9,616 empates, 7,692 no empatados); 264 equipos mixtos;
  45 marcados `revisar`.
- 145,262 atletas con participación; 238 sin participación.
- Rendimiento: atleta ~2 ms, país ~2 ms, detalle de país ~4–5 ms.

Evidencia final:

- [`evidencia/fase5/validacion.md`](evidencia/fase5/validacion.md) — reporte
  legible con fecha/hora, conteos, medallas y planes de ejecución.
- [`evidencia/fase5/validacion.json`](evidencia/fase5/validacion.json).
- [`evidencia/fase1/...`](fase1/evidencia/validacion_fase1.md) — preparación
  y correcciones.
- `evidencia/fase2/catalogos.json`, `evidencia/fase3/resultados.json`,
  `evidencia/fase4/atletas.json`, `evidencia/fase4/paises.json`.

---

## 4. Consultas obligatorias

### (c) Atleta

```bash
python3 fase5/scripts/03_consulta_atleta.py "Michael Phelps"
python3 fase5/scripts/03_consulta_atleta.py "Michael Phelps" --anio 2008
python3 fase5/scripts/03_consulta_atleta.py "Usain Bolt" --medalla oro
python3 fase5/scripts/03_consulta_atleta.py "Phelps" --deporte swimming --pais USA
python3 fase5/scripts/03_consulta_atleta.py --id 93860 --json
```

### (d) País

```bash
python3 fase5/scripts/04_consulta_pais.py "Guatemala"
python3 fase5/scripts/04_consulta_pais.py "Estados Unidos" --anio 2012
python3 fase5/scripts/04_consulta_pais.py GUA --limite 0
python3 fase5/scripts/04_consulta_pais.py "Grecia" --deporte atletismo
python3 fase5/scripts/04_consulta_pais.py "Japón" --json
```

Acepta nombre en inglés, alias en español o NOC; los filtros son opcionales.

---

## 5. Estructura

```text
Fase3/
├── Enunciado proyecto 3-1.pdf
├── README.md
├── docker-compose.yml
├── requirements.txt
├── run_all.sh
├── lib/common.py
├── docs/
│   ├── 01_Diseno_4_Colecciones.md
│   ├── 02_Fase1_Implementacion.md
│   ├── 03_Fase2_Catalogos.md
│   ├── 04_Fase3_Resultados.md
│   ├── 05_Fase4_Atletas_Paises.md
│   └── 06_Fase5_Indices_Validacion_Consultas.md
├── fase1/
│   ├── datos/ ...
│   ├── scripts/ ...
│   └── evidencia/ ...
├── fase2/
│   ├── scripts/00_verificar_entorno.py
│   ├── scripts/01_catalogos.py
│   └── run_fase2.sh
├── fase3/
│   ├── scripts/01_resultados.py
│   └── run_fase3.sh
├── fase4/
│   ├── scripts/01_atletas.py
│   ├── scripts/02_paises.py
│   └── run_fase4.sh
├── fase5/
│   ├── scripts/01_indices.py
│   ├── scripts/02_validar.py
│   ├── scripts/03_consulta_atleta.py
│   ├── scripts/04_consulta_pais.py
│   └── run_fase5.sh
└── evidencia/
    ├── fase2/ ...
    ├── fase3/ ...
    ├── fase4/ ...
    ├── fase5/ ...
    └── run_all_<fecha>.log
```

---

## 6. Decisiones de datos

1. **PostgreSQL es la fuente** para las fases 2–5; el contenedor ya está
   completo. La Fase 1 puede usar PostgreSQL o los CSV de
   `Fase2/csv-limpios` (`--fuente csv`).
2. **Sedes:** se usa `dim_sedes.csv` curado; el mapeo crudo
   `CIUDAD_OLIMPIADA → CIUDAD → REGION → PAIS` fallaba por ciudades
   homónimas.
3. **Categoría:** `Senior | Juvenil | Intercalado | Atipico`; evita mezclar
   Vancouver 2010 con Singapur 2010 (Juvenil) o Londres 2012 con Innsbruck
   2012.
4. **Nombres:** se agrega `nombreNormalizado`; el original nunca se modifica.
   Si no se puede normalizar, se conserva y se marca `normalizado: false`.
5. **Medallas:** en `paises` se cuenta una por país/equipo por resultado;
   `medallasAtleta` es la métrica secundaria. Los equipos mixtos se separan en
   `medallasMixtas`.
6. **Geografía sin país:** 14 regiones y 20 ciudades del dataset no tienen
   país/región asignable. No se inventan: se conservan en `catalogos` como
   `region_sin_pais` / `ciudad_sin_pais`, y se reportan en la evidencia.

---

## 7. Documentación

1. [Diseño de las 4 colecciones](docs/01_Diseno_4_Colecciones.md).
2. [Fase 1: preparación](docs/02_Fase1_Implementacion.md).
3. [Fase 2: catálogos](docs/03_Fase2_Catalogos.md).
4. [Fase 3: resultados](docs/04_Fase3_Resultados.md).
5. [Fase 4: atletas y países](docs/05_Fase4_Atletas_Paises.md).
6. [Fase 5: índices, validación y consultas](docs/06_Fase5_Indices_Validacion_Consultas.md).

---

## 8. Problemas comunes

- **Mongo no responde:** `docker compose up -d`, verifica
  `docker ps | grep mongo_fase3`; si el volumen quedó con otro dueño,
  `docker compose down -v` (borra datos) y vuelve a ejecutar `./run_all.sh`.
- **PostgreSQL no responde:** verifica `docker ps | grep postgres_cali`; las
  fases 2–5 necesitan el contenedor completo.
- **Falta pymongo:** `../.venv/bin/python -m pip install -r requirements.txt`.
- **Una colección ya tiene datos:** los scripts aceptan `--recrear`; los
  `run_faseN.sh` ya lo usan.
