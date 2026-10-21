# 02 — Implementación de la Fase 1

**Objetivo:** dejar listos y validados los insumos de corrección que usarán las
fases de carga a MongoDB, con scripts reproducibles y evidencia fechada.

**Estado:** completada.  
**Fuente usada en la última ejecución:** PostgreSQL (`olimpiadas_db`,
contenedor `postgres_cali`), con respaldo automático a los CSV de
`Fase2/csv-limpios`.

---

## 1. Qué se corrige y por qué

### 1.1 Sedes

El modelo relacional obtiene el país sede con:

```text
CIUDAD_OLIMPIADA → CIUDAD → REGION → PAIS
```

Ese camino falla porque hay ciudades homónimas. Ejemplos reales:

| Juego | Ciudad | País deducido por el modelo crudo | País correcto |
|---|---|---|---|
| 1896 / 2004 | Atenas | Estados Unidos (Alabama) | Grecia |
| 1900 / 1924 | París | Estados Unidos (Kentucky) | Francia |
| 1904 | San Luis | Senegal | Estados Unidos |
| 1912 / 1956 | Estocolmo | Estados Unidos (Maine) | Suecia |
| 1960 | Roma | Australia (Queensland) | Italia |
| 1980 | Moscú | Estados Unidos (Idaho) | Rusia/URSS |
| 1992 | Barcelona | Venezuela | España |

La Fase 1 reemplaza ese mapeo por una tabla verificada:
`fase1/datos/insumos/sedes_olimpiadas.csv`, con **61 juegos con sede**.

- **1888** no tiene Juegos oficiales ni sede.
- **1906** se marca como Juegos Intercalados.
- **1956**: Melbourne (AUS) es la sede principal; las pruebas ecuestres se
  registran en Estocolmo (SWE), que en el dataset aparece como un juego aparte.
- **2018, 2020 y 2022** se agregaron porque el dataset no traía fila de sede.

### 1.2 Categoría de juego

El dataset tiene 62 filas de `OLIMPIADA`, pero no todas son Juegos de mayores.
La Fase 1 agrega `CATEGORIA`:

- **Senior:** 54 juegos.
- **Juvenil:** 6 (Singapur 2010, Innsbruck 2012, Nankín 2014, Lillehammer
  2016, Buenos Aires 2018, Lausana 2020).
- **Intercalado:** 1906.
- **Atipico:** 1888.

Sin esta etiqueta, “Juegos de 2010” mezclaría Vancouver 2010 (Senior) con
Singapur 2010 (Juvenil); “2012” mezclaría Londres con Innsbruck.

### 1.3 Temporada

Se corrige `Unknown` a `Summer` en:

- **1906** (Intercalados).
- **1956, ID 32** (pruebas ecuestres).

Se conserva la temporada original en `TEMPORADA_ORIGINAL` para no perder
trazabilidad. **1888** queda `Unknown`.

### 1.4 Alias de países

Se agregan nombres en español y variantes (`Grecia`, `Estados Unidos`,
`EE.UU.`, `Alemania`, `Reino Unido`, …) en
`fase1/datos/insumos/alias_paises.csv`.

- No se modifica `PAIS.NOMBRE`.
- Se deduplican por `NOC` + alias normalizado.
- Resultado: **109 alias únicos** para los 247 países.

### 1.5 Normalización de nombres

Se agrega `NOMBRE_NORMALIZADO` para búsquedas: minúsculas, sin acentos, sin
puntuación y con espacios colapsados.

Regla de fallback:

- Si el nombre solo tiene escritura latina (con o sin acentos), se normaliza.
- Si después de transliterar quedan letras no ASCII (chino, cirílico, etc.) o el
  resultado sería vacío, **se conserva el nombre original** y se marca
  `NORMALIZADO = NO`.
- El campo `NOMBRE_ORIGINAL` nunca se modifica.

Resultado con los 145,500 atletas:

| Métrica | Cantidad |
|---|---:|
| Atletas procesados | 145,500 |
| Normalizados correctamente | 145,399 |
| Fallback al original | **101** |
| Nombres que cambian al normalizar | 145,399 |
| Países con fallback | 0 |

Los 101 fallback son nombres con caracteres no latinos o combinaciones que no
se pueden transliterar sin perder información (por ejemplo, nombres en
cirílico o azerí). En la evidencia se listan ejemplos.

---

## 2. Entregables

| Archivo | Filas | Contenido |
|---|---:|---|
| `datos/insumos/sedes_olimpiadas.csv` | 61 | Insumo curado de sedes |
| `datos/insumos/alias_paises.csv` | 109 | Insumo curado de alias |
| `datos/dim_juegos.csv` | 62 | Juegos + temporada + categoría + sede |
| `datos/dim_sedes.csv` | 61 | Solo juegos con sede |
| `datos/dim_alias_paises.csv` | 109 | Alias validados + nombre del país |
| `datos/dim_paises_normalizados.csv` | 247 | Original + normalizado + flag |
| `datos/MANIFEST.csv` | 6 | Filas, bytes y SHA-256 |
| `evidencia/validacion_fase1.md` | — | Constancia legible con fecha/hora |
| `evidencia/validacion_fase1.json` | — | Misma constancia en JSON |
| `evidencia/reporte_*.json` | — | Reportes por etapa |
| `evidencia/muestra_normalizacion.csv` | 100 | Ejemplos de cambios/fallback |
| `evidencia/ejecucion_<fecha>.log` | — | Log completo de la corrida |

---

## 3. Validaciones automáticas

`04_validar_fase1.py` comprueba:

- 62 juegos, IDs únicos y coincidentes con `OLIMPIADA`.
- 61 sedes; 1888 sin sede.
- Categorías: 54 Senior, 6 Juvenil, 1 Intercalado, 1 Atipico.
- NOCs de sedes existen en `PAIS`.
- Temporada corregida solo en 1906 y 1956/32; el resto conserva la fuente.
- Alias sin NOCs inválidos ni duplicados.
- Nombres originales de países sin modificar.
- Normalización reproducible y fallback que conserva el original.
- Comparación con el mapeo crudo de sedes.
- Checksums de los archivos generados.

Resultado de la última corrida: **0 fallos**.

Discrepancias con el mapeo crudo: **26** juegos
(10 con país distinto, 5 sin país deducible, 11 sin fila de sede).
Esto evidencia por qué fue necesario curar las sedes.

La constancia completa está en
[`../fase1/evidencia/validacion_fase1.md`](../fase1/evidencia/validacion_fase1.md).

---

## 4. Cómo reproducir

```bash
cd Fase3

# Automático: intenta PostgreSQL y cae a CSV
./fase1/scripts/run_fase1.sh

# Forzar una fuente
./fase1/scripts/run_fase1.sh --fuente pg
./fase1/scripts/run_fase1.sh --fuente csv
```

Cada ejecución:

1. Genera/valida los insumos curados.
2. Construye `dim_juegos` y `dim_sedes`.
3. Valida y deduplica alias.
4. Normaliza países y atletas.
5. Valida todo y escribe la evidencia con fecha/hora y checksums.

---

## 5. Qué sigue

La Fase 1 deja los insumos listos. Las siguientes fases (aún no implementadas)
son:

1. **Catálogos:** construir `catalogos` con juegos, deportes, disciplinas,
   eventos y medallas, usando `dim_juegos.csv`.
2. **Resultados:** construir un documento por `RESULTADO` con `atletas[]`,
   `paises[]`, `multipais`, `paisEquipo` y la medalla.
3. **Atletas y países:** perfiles, `resumen`, población, regiones, ciudades y
   `sedes`.
4. **Índices y consultas:** crear índices después de la carga y validar las
   consultas de atleta/país con `explain`.
