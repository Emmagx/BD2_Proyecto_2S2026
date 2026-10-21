#!/usr/bin/env python3
"""
Fase 1.4 - Validación y evidencia de la Fase 1.

Comprueba los CSV generados contra OLIMPIADA/PAIS, valida las correcciones
de sedes y categorías, revisa la normalización y deja constancia en:
  evidencia/validacion_fase1.md
  evidencia/validacion_fase1.json
  datos/MANIFEST.csv
"""
from __future__ import annotations

import argparse
import csv
import platform
import sys
from pathlib import Path

from common import (
    CSV_DIR,
    DATOS_DIR,
    EVIDENCIA_DIR,
    FASE1_DIR,
    ahora,
    cargar_olimpiada,
    cargar_pais,
    escribir_csv,
    escribir_json,
    leer_csv,
    log,
    normalizar_con_fallback,
    sha256,
)

CATEGORIAS_ESPERADAS = {"Senior": 54, "Juvenil": 6, "Intercalado": 1, "Atipico": 1}
ESPECIALES = [10, 32, 46, 57, 58, 59, 60, 61, 62]


def leer_csv_simple(ruta: Path) -> list[dict]:
    with Path(ruta).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def mapa_raw_sedes() -> dict[int, dict]:
    """Construye el mapeo crudo CIUDAD_OLIMPIADA -> ciudad -> region -> pais."""
    paises = {int(p["ID"]): p for p in leer_csv_simple(CSV_DIR / "1_PAIS.csv")}
    regiones = {int(r["ID"]): r for r in leer_csv_simple(CSV_DIR / "5_REGION.csv")}
    ciudades = {int(c["ID"]): c for c in leer_csv_simple(CSV_DIR / "8_CIUDAD.csv")}
    crudo: dict[int, dict] = {}
    for row in leer_csv_simple(CSV_DIR / "11_CIUDAD_OLIMPIADA.csv"):
        oid = int(row["ID_OLIMPIADA"])
        cid = int(row["ID_CIUDAD"])
        ciudad = ciudades.get(cid, {})
        region = regiones.get(int(ciudad["ID_REGION"])) if ciudad.get("ID_REGION") else None
        pais = paises.get(int(region["ID_PAIS"])) if region and region.get("ID_PAIS") else None
        item = crudo.setdefault(
            oid, {"ciudades": [], "nocs": set(), "paises": []}
        )
        item["ciudades"].append(ciudad.get("NOMBRE", f"ciudad {cid}"))
        if pais:
            item["nocs"].add(pais["NOC"])
            item["paises"].append(pais["NOMBRE"])
    return crudo


def main() -> int:
    ap = argparse.ArgumentParser(description="Valida la Fase 1")
    ap.add_argument("--fuente", default="auto", choices=["auto", "pg", "csv"])
    args = ap.parse_args()

    log("Fase 1.4 - Validando resultados")
    olimpiadas = cargar_olimpiada(args.fuente)
    paises = cargar_pais(args.fuente)
    nocs = {p["NOC"] for p in paises}
    por_id = {o["ID"]: o for o in olimpiadas}

    juegos = leer_csv(DATOS_DIR / "dim_juegos.csv")
    sedes = leer_csv(DATOS_DIR / "dim_sedes.csv")
    alias = leer_csv(DATOS_DIR / "dim_alias_paises.csv")
    paises_norm = leer_csv(DATOS_DIR / "dim_paises_normalizados.csv")
    import json

    with (EVIDENCIA_DIR / "reporte_normalizacion.json").open(encoding="utf-8") as f:
        reporte_norm = json.load(f)
    with (EVIDENCIA_DIR / "reporte_alias.json").open(encoding="utf-8") as f:
        reporte_alias = json.load(f)
    with (EVIDENCIA_DIR / "reporte_dim_juegos.json").open(encoding="utf-8") as f:
        reporte_dim = json.load(f)

    fallos: list[str] = []
    avisos: list[str] = []

    # ------------------------------------------------------------------
    # 1. dim_juegos
    # ------------------------------------------------------------------
    if len(juegos) != 62:
        fallos.append(f"dim_juegos: {len(juegos)} filas (esperado 62)")
    ids_juegos = [int(j["ID_OLIMPIADA"]) for j in juegos]
    if len(ids_juegos) != len(set(ids_juegos)):
        fallos.append("dim_juegos: IDs repetidos")
    if set(ids_juegos) != set(por_id):
        fallos.append("dim_juegos: los IDs no coinciden con OLIMPIADA")

    categorias: dict[str, int] = {}
    for j in juegos:
        categorias[j["CATEGORIA"]] = categorias.get(j["CATEGORIA"], 0) + 1
    if categorias != CATEGORIAS_ESPERADAS:
        fallos.append(f"dim_juegos: categorías {categorias} != {CATEGORIAS_ESPERADAS}")

    for j in juegos:
        oid = int(j["ID_OLIMPIADA"])
        if int(j["ANIO"]) != por_id[oid]["YEAR"]:
            fallos.append(f"dim_juegos {oid}: año distinto al de OLIMPIADA")
        if j["CATEGORIA"] not in CATEGORIAS_ESPERADAS:
            fallos.append(f"dim_juegos {oid}: categoría inválida {j['CATEGORIA']}")

    # ------------------------------------------------------------------
    # 2. dim_sedes
    # ------------------------------------------------------------------
    if len(sedes) != 61:
        fallos.append(f"dim_sedes: {len(sedes)} filas (esperado 61)")
    ids_sedes = [int(s["ID_OLIMPIADA"]) for s in sedes]
    if set(ids_sedes) != set(por_id) - {46}:
        fallos.append("dim_sedes: no cubre exactamente los 62 juegos menos 1888")
    if 46 in ids_sedes:
        fallos.append("dim_sedes: 1888 no debe tener sede")
    for s in sedes:
        if s["PAIS_NOC"] not in nocs:
            fallos.append(f"dim_sedes {s['ID_OLIMPIADA']}: NOC inexistente {s['PAIS_NOC']}")
        juego = next(j for j in juegos if int(j["ID_OLIMPIADA"]) == int(s["ID_OLIMPIADA"]))
        if s["CATEGORIA"] != juego["CATEGORIA"]:
            fallos.append(f"dim_sedes {s['ID_OLIMPIADA']}: categoría distinta a dim_juegos")
        if s["TEMPORADA"] != juego["TEMPORADA"]:
            fallos.append(f"dim_sedes {s['ID_OLIMPIADA']}: temporada distinta a dim_juegos")

    # La temporada solo se corrige en 10 y 32; el resto debe conservar la fuente.
    for j in juegos:
        oid = int(j["ID_OLIMPIADA"])
        if oid not in (10, 32, 46) and j["TEMPORADA"] != j["TEMPORADA_ORIGINAL"]:
            fallos.append(f"Juego {oid}: temporada cambiada sin justificación")
        if oid == 46:
            if j["CIUDAD_SEDE"] or j["PAIS_NOC"]:
                fallos.append("Juego 46: no debe tener sede ni país")
        elif not j["CIUDAD_SEDE"] or not j["PAIS_NOC"]:
            fallos.append(f"Juego {oid}: falta sede o país")

    # Correcciones de temporada
    for oid in (10, 32):
        fila = next(j for j in juegos if int(j["ID_OLIMPIADA"]) == oid)
        if fila["TEMPORADA"] != "Summer" or fila["TEMPORADA_ORIGINAL"] != "Unknown":
            fallos.append(f"Juego {oid}: corrección de temporada incompleta")
    fila_46 = next(j for j in juegos if int(j["ID_OLIMPIADA"]) == 46)
    if fila_46["TEMPORADA"] != "Unknown" or fila_46["CIUDAD_SEDE"]:
        fallos.append("Juego 46: debe quedar Unknown y sin sede")

    # ------------------------------------------------------------------
    # 3. Alias
    # ------------------------------------------------------------------
    if not alias:
        fallos.append("dim_alias_paises está vacío")
    vistos_alias = set()
    for a in alias:
        if a["NOC"] not in nocs:
            fallos.append(f"alias: NOC inexistente {a['NOC']}")
        clave = (a["NOC"], a["ALIAS_NORMALIZADO"])
        if clave in vistos_alias:
            fallos.append(f"alias duplicado: {clave}")
        vistos_alias.add(clave)
        if not a["ALIAS_NORMALIZADO"]:
            fallos.append(f"alias sin normalizar: {a}")

    # ------------------------------------------------------------------
    # 4. Nombres normalizados
    # ------------------------------------------------------------------
    if len(paises_norm) != len(paises):
        fallos.append(
            f"dim_paises_normalizados: {len(paises_norm)} filas != {len(paises)} países"
        )
    nombres_origen = {str(p["ID"]): p["NOMBRE"] for p in paises}
    fallback_paises = 0
    for p in paises_norm:
        if nombres_origen.get(p["ID"]) != p["NOMBRE_ORIGINAL"]:
            fallos.append(f"País {p['ID']}: el nombre original fue modificado")
        if not p["NOMBRE_NORMALIZADO"]:
            fallos.append(f"País {p['ID']}: nombre normalizado vacío")
        calc = normalizar_con_fallback(p["NOMBRE_ORIGINAL"])
        if calc["normalizado"] != p["NOMBRE_NORMALIZADO"]:
            fallos.append(f"País {p['ID']}: normalización no reproducible")
        if calc["ok"] != (p["NORMALIZADO"] == "SI"):
            fallos.append(f"País {p['ID']}: indicador NORMALIZADO inconsistente")
        if p["NORMALIZADO"] == "NO":
            fallback_paises += 1
            if p["NOMBRE_NORMALIZADO"] != p["NOMBRE_ORIGINAL"]:
                fallos.append(f"País {p['ID']}: fallback no conserva el original")

    total_atletas = int(reporte_norm.get("atletas_procesados", 0))
    ok_atletas = int(reporte_norm.get("normalizados_ok", 0))
    fallback_atletas = int(reporte_norm.get("fallback_original", 0))
    if ok_atletas + fallback_atletas != total_atletas:
        fallos.append("Normalización: ok + fallback != total de atletas")
    if total_atletas != 145_500:
        avisos.append(f"Atletas procesados: {total_atletas} (esperado 145,500)")

    # ------------------------------------------------------------------
    # 5. Comparación con el mapeo crudo de sedes
    # ------------------------------------------------------------------
    crudo = mapa_raw_sedes()
    discrepancias = []
    for s in sedes:
        oid = int(s["ID_OLIMPIADA"])
        raw = crudo.get(oid)
        if not raw:
            discrepancias.append(
                {
                    "ID_OLIMPIADA": oid,
                    "CIUDAD_CURADA": s["CIUDAD"],
                    "PAIS_CURADO": s["PAIS_NOC"],
                    "PAIS_CRUDO": "(sin fila en CIUDAD_OLIMPIADA)",
                    "TIPO": "sin_fila",
                }
            )
            continue
        if s["PAIS_NOC"] not in raw["nocs"]:
            tipo = "pais_distinto" if raw["nocs"] else "sin_pais"
            discrepancias.append(
                {
                    "ID_OLIMPIADA": oid,
                    "CIUDAD_CURADA": s["CIUDAD"],
                    "PAIS_CURADO": s["PAIS_NOC"],
                    "PAIS_CRUDO": ", ".join(sorted(raw["nocs"])) or "(sin país)",
                    "TIPO": tipo,
                }
            )
    resumen_disc = {
        "total": len(discrepancias),
        "pais_distinto": sum(1 for d in discrepancias if d["TIPO"] == "pais_distinto"),
        "sin_pais": sum(1 for d in discrepancias if d["TIPO"] == "sin_pais"),
        "sin_fila": sum(1 for d in discrepancias if d["TIPO"] == "sin_fila"),
    }

    # ------------------------------------------------------------------
    # 6. Reporte
    # ------------------------------------------------------------------
    archivos = [
        DATOS_DIR / "insumos" / "sedes_olimpiadas.csv",
        DATOS_DIR / "insumos" / "alias_paises.csv",
        DATOS_DIR / "dim_juegos.csv",
        DATOS_DIR / "dim_sedes.csv",
        DATOS_DIR / "dim_alias_paises.csv",
        DATOS_DIR / "dim_paises_normalizados.csv",
    ]
    manifest = []
    for ruta in archivos:
        filas = sum(1 for _ in ruta.open(encoding="utf-8")) - 1
        manifest.append(
            {
                "archivo": str(ruta.relative_to(FASE1_DIR)),
                "filas": filas,
                "bytes": ruta.stat().st_size,
                "sha256": sha256(ruta),
            }
        )
    escribir_csv(
        DATOS_DIR / "MANIFEST.csv",
        ["archivo", "filas", "bytes", "sha256"],
        manifest,
    )

    salida = {
        "generado_en": ahora(),
        "fuente": args.fuente,
        "host": platform.node(),
        "python": platform.python_version(),
        "conteos": {
            "dim_juegos": len(juegos),
            "dim_sedes": len(sedes),
            "dim_alias_paises": len(alias),
            "dim_paises_normalizados": len(paises_norm),
            "atletas_normalizados": total_atletas,
        },
        "categorias": categorias,
        "correcciones_temporada": reporte_dim.get("correcciones_temporada", []),
        "normalizacion": {
            "atletas_ok": ok_atletas,
            "atletas_fallback": fallback_atletas,
            "atletas_cambiados": reporte_norm.get("cambiados", 0),
            "paises_fallback": fallback_paises,
            "ejemplos_fallback": reporte_norm.get("ejemplos_fallback", []),
            "ejemplos_cambio": reporte_norm.get("ejemplos_cambio", []),
        },
        "alias": {
            "validos": len(alias),
            "omitidos": reporte_alias.get("alias_omitidos", []),
            "duplicados": reporte_alias.get("alias_duplicados", []),
        },
        "discrepancias_sedes_crudas": discrepancias,
        "resumen_discrepancias": resumen_disc,
        "fallos": fallos,
        "avisos": avisos,
        "ok": not fallos,
        "sha256": {m["archivo"]: m["sha256"] for m in manifest},
    }
    escribir_json(EVIDENCIA_DIR / "validacion_fase1.json", salida)

    md = []
    md.append("# Fase 1 - Validación y constancia de ejecución\n")
    md.append(f"**Fecha y hora:** {salida['generado_en']}  ")
    md.append(f"**Fuente:** {args.fuente}  ")
    md.append(f"**Host:** `{salida['host']}` · **Python:** {salida['python']}  ")
    md.append("**Base de datos de origen:** `olimpiadas_db` (PostgreSQL 17, contenedor `postgres_cali`)\n")
    md.append("## 1. Entregables generados\n")
    md.append("| Archivo | Filas | Bytes | SHA-256 |")
    md.append("|---|---:|---:|---|")
    for m in manifest:
        md.append(f"| `{m['archivo']}` | {m['filas']:,} | {m['bytes']:,} | `{m['sha256'][:16]}…` |")
    md.append("")
    md.append("## 2. Categorías de juegos\n")
    md.append("| Categoría | Juegos |")
    md.append("|---|---:|")
    for k in ["Senior", "Juvenil", "Intercalado", "Atipico"]:
        md.append(f"| {k} | {categorias.get(k, 0)} |")
    md.append(f"\nTotal: **{len(juegos)}** juegos; **{len(sedes)}** con sede; **1888** sin sede.\n")
    md.append("## 3. Casos especiales\n")
    md.append("| ID | Año | Temporada | Original | Categoría | Sede | País |")
    md.append("|---:|---:|---|---|---|---|---|")
    for oid in ESPECIALES:
        j = next(x for x in juegos if int(x["ID_OLIMPIADA"]) == oid)
        md.append(
            f"| {oid} | {j['ANIO']} | {j['TEMPORADA']} | {j['TEMPORADA_ORIGINAL']} | "
            f"{j['CATEGORIA']} | {j['CIUDAD_SEDE'] or '—'} | {j['PAIS_NOC'] or '—'} |"
        )
    md.append("")
    md.append("## 4. Normalización de nombres\n")
    md.append(
        f"- Atletas procesados: **{total_atletas:,}**\n"
        f"- Normalizados correctamente: **{ok_atletas:,}**\n"
        f"- Con fallback al original (no normalizables): **{fallback_atletas:,}**\n"
        f"- Nombres que cambiaron al normalizar: **{reporte_norm.get('cambiados', 0):,}**\n"
        f"- Países con fallback: **{fallback_paises}**\n"
    )
    md.append("Ejemplos de fallback (se conserva el original):\n")
    md.append("| ID | Original | Normalizado |")
    md.append("|---:|---|---|")
    for e in reporte_norm.get("ejemplos_fallback", [])[:10]:
        md.append(f"| {e['ID']} | {e['ORIGINAL']} | {e['NORMALIZADO']} |")
    md.append("")
    md.append("## 5. Corrección de sedes\n")
    md.append(
        f"El mapeo crudo `CIUDAD_OLIMPIADA → CIUDAD → REGION → PAIS` no coincide con la sede "
        f"verificada en **{resumen_disc['total']}** juegos: "
        f"**{resumen_disc['pais_distinto']}** con país distinto, "
        f"**{resumen_disc['sin_pais']}** sin país deducible y "
        f"**{resumen_disc['sin_fila']}** sin fila de sede. "
        "La causa principal son ciudades homónimas (Atenas/Alabama, París/Kentucky, etc.).\n"
    )
    md.append("| Juego | Ciudad curada | País curado | País crudo | Tipo |")
    md.append("|---:|---|---|---|---|")
    for d in discrepancias[:20]:
        md.append(
            f"| {d['ID_OLIMPIADA']} | {d['CIUDAD_CURADA']} | {d['PAIS_CURADO']} | "
            f"{d['PAIS_CRUDO']} | {d['TIPO']} |"
        )
    md.append("")
    md.append("## 6. Validaciones\n")
    md.append("| Validación | Resultado |")
    md.append("|---|---|")
    md.append(f"| 62 juegos sin IDs repetidos | {'OK' if not any('IDs repetidos' in f for f in fallos) else 'FALLO'} |")
    md.append(f"| 61 sedes, 1888 sin sede | {'OK' if len(sedes) == 61 and 46 not in ids_sedes else 'FALLO'} |")
    md.append(f"| Categorías esperadas | {'OK' if categorias == CATEGORIAS_ESPERADAS else 'FALLO'} |")
    md.append(f"| NOC de sedes existen en PAIS | {'OK' if not any('NOC inexistente' in f for f in fallos) else 'FALLO'} |")
    md.append(f"| Alias sin NOC inválidos | {'OK' if not any('alias: NOC' in f for f in fallos) else 'FALLO'} |")
    md.append(f"| Nombres originales sin modificar | {'OK' if not any('nombre original fue modificado' in f for f in fallos) else 'FALLO'} |")
    md.append(f"| Fallos totales | **{len(fallos)}** |")
    md.append("")
    if fallos:
        md.append("### Fallos\n")
        for f in fallos:
            md.append(f"- {f}")
        md.append("")
    if avisos:
        md.append("### Avisos\n")
        for a in avisos:
            md.append(f"- {a}")
        md.append("")
    md.append("## 7. Reproducción\n")
    md.append("```bash")
    md.append("cd Fase3")
    md.append("./fase1/scripts/run_fase1.sh")
    md.append("```")
    md.append("")
    (EVIDENCIA_DIR / "validacion_fase1.md").write_text("\n".join(md), encoding="utf-8")
    log(f"Evidencia Markdown: {EVIDENCIA_DIR / 'validacion_fase1.md'}")
    log(f"Evidencia JSON: {EVIDENCIA_DIR / 'validacion_fase1.json'}")

    print()
    print(f"Fallos: {len(fallos)}")
    for f in fallos:
        print(f"  [FALLO] {f}")
    for a in avisos:
        print(f"  [AVISO] {a}")
    print(f"Juegos: {len(juegos)} | Sedes: {len(sedes)} | Categorías: {categorias}")
    print(f"Atletas normalizados: {total_atletas:,} (fallback {fallback_atletas:,})")
    print(
        f"Discrepancias de sede cruda: {resumen_disc['total']} "
        f"(país distinto={resumen_disc['pais_distinto']}, "
        f"sin país={resumen_disc['sin_pais']}, sin fila={resumen_disc['sin_fila']})"
    )
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
