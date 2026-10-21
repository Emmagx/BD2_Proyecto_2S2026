# Fase 3 — Migración de las Olimpiadas a MongoDB

**Curso:** Sistemas de Bases de Datos 2 — USAC — 2S2026  
**Entrega:** 24 de octubre de 2026  
**Estado actual:** **Fase 1 completada** (preparación y corrección de datos).  
**Diseño acordado:** 4 colecciones (`atletas`, `resultados`, `paises`, `catalogos`).

---

## 1. Qué contiene esta carpeta

```text
Fase3/
├── Enunciado proyecto 3-1.pdf
├── README.md
├── docs/
│   ├── 01_Diseno_4_Colecciones.md
│   └── 02_Fase1_Implementacion.md
└── fase1/
    ├── datos/
    │   ├── insumos/
    │   │   ├── sedes_olimpiadas.csv     (61 juegos con sede verificada)
    │   │   └── alias_paises.csv         (109 alias únicos)
    │   ├── dim_juegos.csv               (62 juegos)
    │   ├── dim_sedes.csv                (61 sedes)
    │   ├── dim_alias_paises.csv         (109 alias)
    │   ├── dim_paises_normalizados.csv  (247 países)
    │   └── MANIFEST.csv                 (filas, bytes y SHA-256)
    ├── scripts/
    │   ├── common.py
    │   ├── 00_generar_insumos.py
    │   ├── 01_generar_dim_juegos.py
    │   ├── 02_generar_alias_paises.py
    │   ├── 03_generar_nombres_normalizados.py
    │   ├── 04_validar_fase1.py
    │   └── run_fase1.sh
    └── evidencia/
        ├── validacion_fase1.md
        ├── validacion_fase1.json
        ├── reporte_*.json
        ├── muestra_normalizacion.csv
        └── ejecucion_<fecha>.log
```

El PDF del enunciado se conservó; la implementación anterior de 10 colecciones
fue eliminada para no mezclar diseños.

---

## 2. Fase 1: qué se hizo

La Fase 1 **no carga MongoDB todavía**. Prepara y corrige los datos que usarán
las fases siguientes:

1. **Sedes verificadas:** reemplaza el mapeo crudo
   `CIUDAD_OLIMPIADA → CIUDAD → REGION → PAIS`, que falla por ciudades
   homónimas (Atenas/Alabama, París/Kentucky, Roma/Queensland, etc.).
2. **Categoría de juego:** agrega `Senior | Juvenil | Intercalado | Atipico`
   para distinguir los Juegos de la Juventud, 1906 y 1888.
3. **Alias de países:** agrega nombres en español para búsquedas
   (`Grecia`, `Estados Unidos`, `Alemania`, …), sin cambiar el nombre original.
4. **Normalización de nombres:** agrega una versión normalizada para buscar,
   sin modificar el nombre original. Si un nombre no se puede normalizar,
   se conserva tal cual y se marca `NORMALIZADO = NO`.

### Resultados de la Fase 1

| Entregable | Resultado |
|---|---|
| Juegos | **62** |
| Juegos con sede | **61** (1888 no tiene sede) |
| Categorías | 54 Senior, 6 Juvenil, 1 Intercalado, 1 Atipico |
| Sedes corregidas | **26** juegos no coincidían con el mapeo crudo |
| Alias únicos | **109** |
| Países normalizados | **247** |
| Atletas procesados | **145,500** |
| Atletas con fallback al original | **101** (escritura no latina) |

La evidencia completa, con fecha y hora, está en
[`fase1/evidencia/validacion_fase1.md`](fase1/evidencia/validacion_fase1.md).

---

## 3. Cómo ejecutar la Fase 1

Requisitos: Python 3.10+ y, opcionalmente, el contenedor PostgreSQL
`postgres_cali` con `olimpiadas_db`. Si no está disponible, el script cae
automáticamente a los CSV de `Fase2/csv-limpios`.

```bash
cd Fase3
./fase1/scripts/run_fase1.sh
```

Opciones:

```bash
# Forzar PostgreSQL
./fase1/scripts/run_fase1.sh --fuente pg

# Forzar los CSV de respaldo
./fase1/scripts/run_fase1.sh --fuente csv
```

Cada ejecución genera un log nuevo en `fase1/evidencia/` y reescribe los CSV
de salida y la validación con la fecha/hora de esa corrida.

---

## 4. Scripts y responsabilidad

| Script | Qué hace |
|---|---|
| `00_generar_insumos.py` | Genera las sedes curadas y los alias; valida NOCs y años |
| `01_generar_dim_juegos.py` | Construye `dim_juegos` y `dim_sedes` |
| `02_generar_alias_paises.py` | Deduplica y valida los alias contra `PAIS` |
| `03_generar_nombres_normalizados.py` | Normaliza países y atletas con fallback |
| `04_validar_fase1.py` | Valida todo y genera la evidencia Markdown/JSON |
| `run_fase1.sh` | Ejecuta la secuencia completa y guarda el log |

No se requieren librerías externas: todo usa la biblioteca estándar de Python.

---

## 5. Diseño de las 4 colecciones (contexto)

La Fase 1 prepara datos para este diseño, que se implementará en las fases
siguientes:

| Colección | Grano | Contenido |
|---|---|---|
| `atletas` | atleta | Perfil + `resumen` derivado; sin array de participaciones |
| `resultados` | resultado | Un doc por `RESULTADO`, con `atletas[]`, `paises[]`, `multipais`, `paisEquipo`, edición, deporte, evento, posición y medalla |
| `paises` | país | Perfil, regiones/ciudades, población, `sedes[]` y `resumen` |
| `catalogos` | catálogo | Juegos, deportes, disciplinas, eventos y medallas, con `tipo` |

Detalle completo en
[`docs/01_Diseno_4_Colecciones.md`](docs/01_Diseno_4_Colecciones.md).

---

## 6. Siguientes fases (aún no implementadas)

1. **Fase 2:** construir `catalogos` desde `OLIMPIADA`, `DEPORTE`,
   `DISCIPLINA`, `EVENTO` y `MEDALLA`, usando `dim_juegos.csv`.
2. **Fase 3:** construir `resultados` agrupando `RESULTADO` +
   `RESULTADO_ATLETA`, con `atletas[]`, `paises[]`, `multipais` y
   `paisEquipo`.
3. **Fase 4:** construir `atletas` y calcular `resumen`; construir
   `paises` con regiones, ciudades, población, sedes y resumen.
4. **Fase 5:** índices, validación de conteos y consultas de atleta/país.

La Fase 1 deja listos los insumos que necesitan esas fases; no se avanza a
MongoDB hasta cerrar la revisión de estos CSV.
