# 06 — Fase 5: índices, validación y consultas

**Objetivo:** crear índices, validar las 4 colecciones y ejecutar las dos
consultas obligatorias del enunciado.

**Depende de:** Fases 2, 3 y 4.

**Scripts:**

| Script | Qué hace |
|---|---|
| `fase5/scripts/01_indices.py` | Crea 14 índices |
| `fase5/scripts/02_validar.py` | Valida conteos, integridad, medallas y rendimiento |
| `fase5/scripts/03_consulta_atleta.py` | Requisito (c): ficha de un atleta |
| `fase5/scripts/04_consulta_pais.py` | Requisito (d): ficha de un país |
| `fase5/run_fase5.sh` | Índices + validación con log |

```bash
cd Fase3
./fase5/run_fase5.sh

# Consultas
python3 fase5/scripts/03_consulta_atleta.py "Michael Phelps"
python3 fase5/scripts/04_consulta_pais.py "Guatemala"
```

---

## 1. Índices

Se crean **después** de las cargas:

| Colección | Índice | Uso |
|---|---|---|
| `atletas` | `nombreNormalizado` | búsqueda de atleta |
| `atletas` | `lugarNacimiento.paisNoc` | atletas nacidos en un país |
| `resultados` | `atletas.id + edicion.anio` | ficha de atleta |
| `resultados` | `atletas.noc + edicion.anio + medalla.codigo` | país + filtros |
| `resultados` | `edicion.anio + medalla.codigo` | medallero por edición |
| `resultados` | `evento.id + edicion.anio` | resultados de un evento |
| `resultados` | `deporte.id + edicion.anio` | filtros por deporte |
| `resultados` | `multipais + revisar` | auditoría de casos especiales |
| `paises` | `noc` (único) | búsqueda por NOC |
| `paises` | `nombreNormalizado` | búsqueda por nombre |
| `paises` | `aliasNormalizado` | búsqueda “Grecia”, “EE. UU.” |
| `paises` | `sedes.anio` | sedes por año |
| `catalogos` | `tipo + nombreNormalizado` | catálogos |
| `catalogos` | `tipo + anio` | juegos por año |

Regla: `atletas.id` y `atletas.noc` son arrays distintos; van en índices
separados. No se combinan dos campos de arreglo en un mismo índice.

## 2. Validación

`02_validar.py` comprueba:

- `atletas`: 145,500.
- `resultados`: 156,032.
- `paises`: 247.
- `catalogos`: 3,617 (62 juegos, 93 deportes, 1,520 disciplinas, 1,904
  eventos, 4 medallas, 14 regiones sin país y 20 ciudades sin país).
- Suma de `resultados.atletas[]`: 308,238.
- 145,262 atletas con participación; 238 sin participación.
- Integridad: atletas de resultados existen en `atletas`; NOC de resultados
  existen en `paises`; ediciones/eventos existen en `catalogos`.
- Medallas: 6,953 oro, 6,880 plata, 6,830 bronce, 135,369 sin medalla.
- Multipaís: 17,308; empatados 9,616; no empatados 7,692; `revisar` 45;
  equipos mixtos 264.
- Grecia: sedes 1896, 1906, 2004.
- Planes de ejecución con `IXSCAN`.

La última corrida terminó con **0 fallos**:

| Consulta | Mediana |
|---|---:|
| Atleta por nombre | **~2 ms** |
| País por NOC | **~2 ms** |
| Detalle país 100 filas | **~4–5 ms** |

Evidencia: `evidencia/fase5/validacion.md` y `validacion.json`.

## 3. Consulta de atleta (requisito c)

```bash
python3 fase5/scripts/03_consulta_atleta.py "Michael Phelps"
python3 fase5/scripts/03_consulta_atleta.py "Michael Phelps" --anio 2008
python3 fase5/scripts/03_consulta_atleta.py "Usain Bolt" --medalla oro
python3 fase5/scripts/03_consulta_atleta.py "Phelps" --deporte swimming --pais USA
python3 fase5/scripts/03_consulta_atleta.py --id 93860 --json
```

Opciones: `--deporte`, `--pais` (NOC o nombre), `--anio`, `--medalla`
(`oro/plata/bronce/ninguna`), `--todos` (homónimos), `--json`.

Salida: perfil, nacimiento, fechas, altura/peso, número de juegos,
participaciones, medallas, años, deportes y tabla de resultados.

## 4. Consulta de país (requisito d)

```bash
python3 fase5/scripts/04_consulta_pais.py "Guatemala"
python3 fase5/scripts/04_consulta_pais.py "Estados Unidos" --anio 2012
python3 fase5/scripts/04_consulta_pais.py GUA --limite 0
python3 fase5/scripts/04_consulta_pais.py "Grecia" --deporte atletismo
python3 fase5/scripts/04_consulta_pais.py "Japón" --json
```

Acepta nombre en inglés, alias en español o NOC. Opciones: `--noc`,
`--deporte`, `--medalla`, `--anio`, `--limite` (0 = todos), `--json`.

Salida: perfil, regiones/ciudades, población, **si fue sede y en qué años**,
resumen global (participaciones, atletas, juegos, medallas por evento y por
atleta) y detalle de resultados con filtros.

Ejemplo de control:

```text
PAÍS: Greece (NOC GRE)
Sede: Sí — 1896 Summer: Atenas; 1906 Summer [Intercalado]: Atenas; 2004 Summer: Atenas
Global: 3,659 participaciones | 1,760 atletas | 55 juegos
Medallas: por evento Oro 43, Plata 63, Bronce 52
```

## 5. Evidencia

- `evidencia/fase5/indices.json`: índices creados.
- `evidencia/fase5/validacion.md`: reporte legible con fecha/hora.
- `evidencia/fase5/validacion.json`: misma información en JSON.
- `evidencia/fase5/ejecucion_<fecha>.log`: log de la fase.
