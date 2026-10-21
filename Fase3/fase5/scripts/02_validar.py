#!/usr/bin/env python3
"""
Fase 5.2 - Validación final de las 4 colecciones.

Comprueba conteos, integridad, medallas, sedes y rendimiento de las consultas
obligatorias. Genera:
  evidencia/fase5/validacion.md
  evidencia/fase5/validacion.json

Uso:
  python3 fase5/scripts/02_validar.py
"""
from __future__ import annotations

import json
import platform
import statistics
import sys
import time
from pathlib import Path

FASE3_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FASE3_DIR))

from lib.common import (  # noqa: E402
    EVIDENCIA_DIR,
    MONGO_DB,
    MONGO_URI,
    ahora,
    conectar_mongo,
    escribir_json,
    log,
)

ESPERADO = {"atletas": 145_500, "resultados": 156_032, "paises": 247, "catalogos": 3_617}
MEDALLAS = {"ORO": 6_953, "PLATA": 6_880, "BRONCE": 6_830, None: 135_369}


def stages(plan) -> list[str]:
    salida = []

    def recorrer(x):
        if isinstance(x, dict):
            if "stage" in x:
                salida.append(x["stage"])
            for v in x.values():
                recorrer(v)
        elif isinstance(x, list):
            for v in x:
                recorrer(v)

    recorrer(plan)
    return salida


def medir(fn, repeticiones=8) -> float:
    tiempos = []
    for _ in range(repeticiones):
        t = time.perf_counter()
        fn()
        tiempos.append((time.perf_counter() - t) * 1000)
    return statistics.median(tiempos)


def main() -> int:
    log("Fase 5.2 - Validando colecciones")
    cliente, db = conectar_mongo()
    fallos, avisos = [], []

    conteos = {c: db[c].count_documents({}) for c in ESPERADO}
    for c, esperado in ESPERADO.items():
        if conteos[c] != esperado:
            fallos.append(f"{c}: {conteos[c]:,} (esperado {esperado:,})")

    tipos = {d["_id"]: d["n"] for d in db.catalogos.aggregate([{"$group": {"_id": "$tipo", "n": {"$sum": 1}}}])}
    esperado_tipos = {
        "juego": 62,
        "deporte": 93,
        "disciplina": 1520,
        "evento": 1904,
        "medalla": 4,
        "region_sin_pais": 14,
        "ciudad_sin_pais": 20,
    }
    for t, n in esperado_tipos.items():
        if tipos.get(t) != n:
            fallos.append(f"catalogos.{t}: {tipos.get(t)} (esperado {n})")

    suma_atletas = next(
        db.resultados.aggregate(
            [
                {"$project": {"n": {"$size": "$atletas"}}},
                {"$group": {"_id": None, "total": {"$sum": "$n"}}},
            ]
        ),
        {"total": 0},
    )["total"]
    if suma_atletas != 308_238:
        fallos.append(f"suma de atletas[] en resultados: {suma_atletas:,} (esperado 308,238)")

    ids_atletas = set(db.atletas.distinct("_id"))
    ids_en_resultados = set(db.resultados.distinct("atletas.id"))
    huerfanos = ids_en_resultados - ids_atletas
    if huerfanos:
        fallos.append(f"{len(huerfanos)} atletas de resultados no existen en atletas")
    if len(ids_en_resultados) != 145_262:
        avisos.append(f"atletas con participación: {len(ids_en_resultados):,} (esperado 145,262)")
    if db.atletas.count_documents({"resumen.participaciones": 0}) != 238:
        avisos.append("Atletas sin participación distinto de 238")

    nocs_paises = set(db.paises.distinct("noc"))
    nocs_resultados = set(db.resultados.distinct("paises"))
    if nocs_resultados - nocs_paises:
        fallos.append(f"{len(nocs_resultados - nocs_paises)} NOC de resultados no existen en paises")

    juegos_catalogo = set(db.catalogos.distinct("id", {"tipo": "juego"}))
    juegos_resultados = set(db.resultados.distinct("edicion.id"))
    if juegos_resultados - juegos_catalogo:
        fallos.append("Hay ediciones de resultados sin juego en catalogos")

    eventos_catalogo = set(db.catalogos.distinct("id", {"tipo": "evento"}))
    eventos_resultados = set(db.resultados.distinct("evento.id"))
    if eventos_resultados - eventos_catalogo:
        fallos.append("Hay eventos de resultados sin documento en catalogos")

    regiones_paises = sum(
        len(p.get("regiones", [])) for p in db.paises.find({}, {"regiones": 1})
    )
    ciudades_paises = sum(
        sum(len(r.get("ciudades", [])) for r in p.get("regiones", []))
        for p in db.paises.find({}, {"regiones": 1})
    )
    sin_pais_ciudades = db.catalogos.count_documents({"tipo": "ciudad_sin_pais"})
    sin_pais_regiones = db.catalogos.count_documents({"tipo": "region_sin_pais"})
    poblacion_total = sum(
        len(p.get("poblacion", [])) for p in db.paises.find({}, {"poblacion": 1})
    )
    if regiones_paises + sin_pais_regiones != 2_554:
        fallos.append(
            f"regiones: {regiones_paises}+{sin_pais_regiones} != 2,554"
        )
    if ciudades_paises + sin_pais_ciudades != 22_373:
        fallos.append(
            f"ciudades: {ciudades_paises}+{sin_pais_ciudades} != 22,373"
        )
    if poblacion_total != 11_136:
        fallos.append(f"población: {poblacion_total:,} != 11,136")

    medallas = {}
    for f in db.resultados.aggregate([{"$group": {"_id": "$medalla.codigo", "n": {"$sum": 1}}}]):
        medallas[f["_id"]] = f["n"]
    for codigo, esperado in MEDALLAS.items():
        if medallas.get(codigo, 0) != esperado:
            fallos.append(f"medalla {codigo}: {medallas.get(codigo, 0):,} (esperado {esperado:,})")

    multipais = db.resultados.count_documents({"multipais": True})
    empates = db.resultados.count_documents({"multipais": True, "empate": True})
    no_empates = db.resultados.count_documents({"multipais": True, "empate": False})
    revisar = db.resultados.count_documents({"revisar": True})
    mixtos = db.resultados.count_documents({"equipoMixto": True})

    phelps = db.atletas.find_one({"nombreNormalizado": "michael phelps"})
    gua = db.paises.find_one({"noc": "GUA"})
    gre = db.paises.find_one({"noc": "GRE"})
    if not phelps:
        fallos.append("No se encontró a Michael Phelps")
    elif phelps["resumen"]["medallas"]["oro"] != 23:
        fallos.append(f"Phelps: oros {phelps['resumen']['medallas']['oro']} (esperado 23)")
    if not gua or gua["resumen"]["participaciones"] != 463:
        avisos.append(f"Guatemala: {gua['resumen']['participaciones'] if gua else 'no existe'}")
    if gre:
        anios_gre = sorted({s["anio"] for s in gre.get("sedes", [])})
        if anios_gre != [1896, 1906, 2004]:
            fallos.append(f"Grecia sedes: {anios_gre} != [1896, 1906, 2004]")

    # Rendimiento
    t_atleta = medir(lambda: db.atletas.find_one({"nombreNormalizado": "michael phelps"}))
    t_pais = medir(lambda: db.paises.find_one({"noc": "GUA"}))
    t_detalle = medir(
        lambda: list(db.resultados.find({"atletas.noc": "GUA"}).sort("edicion.anio", -1).limit(100))
    )

    planes = {}
    for nombre, cursor in {
        "atleta_nombre": db.atletas.find({"nombreNormalizado": "michael phelps"}),
        "pais_noc": db.paises.find({"noc": "GUA"}),
        "detalle_pais": db.resultados.find({"atletas.noc": "GUA"}).sort("edicion.anio", -1),
    }.items():
        exp = cursor.explain()
        st = stages(exp.get("queryPlanner", {}).get("winningPlan", {}))
        planes[nombre] = st
        if "IXSCAN" not in st:
            fallos.append(f"El plan de {nombre} no usa IXSCAN: {st}")

    reporte = {
        "generado_en": ahora(),
        "host": platform.node(),
        "python": platform.python_version(),
        "mongo_uri": MONGO_URI,
        "mongo_db": MONGO_DB,
        "conteos": conteos,
        "catalogos_por_tipo": tipos,
        "geografia": {
            "regiones_en_paises": regiones_paises,
            "regiones_sin_pais": sin_pais_regiones,
            "ciudades_en_paises": ciudades_paises,
            "ciudades_sin_pais": sin_pais_ciudades,
            "poblacion_en_paises": poblacion_total,
        },
        "suma_atletas_resultados": suma_atletas,
        "atletas_con_participacion": len(ids_en_resultados),
        "multipais": multipais,
        "multipais_empate": empates,
        "multipais_no_empate": no_empates,
        "revisar": revisar,
        "equipo_mixto": mixtos,
        "medallas": {str(k): v for k, v in medallas.items()},
        "rendimiento_ms": {
            "atleta": round(t_atleta, 3),
            "pais": round(t_pais, 3),
            "detalle_pais_100": round(t_detalle, 3),
        },
        "planes": planes,
        "phelps": phelps["resumen"] if phelps else None,
        "guatemala": gua["resumen"] if gua else None,
        "fallos": fallos,
        "avisos": avisos,
        "ok": not fallos,
    }
    EVIDENCIA_DIR.joinpath("fase5").mkdir(parents=True, exist_ok=True)
    escribir_json(EVIDENCIA_DIR / "fase5" / "validacion.json", reporte)

    md = []
    md.append("# Fase 5 - Validación final\n")
    md.append(f"**Fecha y hora:** {reporte['generado_en']}  ")
    md.append(f"**Host:** `{reporte['host']}` · **Python:** {reporte['python']}  ")
    md.append(f"**MongoDB:** `{MONGO_DB}`\n")
    md.append("## 1. Conteos\n")
    md.append("| Colección | Documentos | Esperado |")
    md.append("|---|---:|---:|")
    for c, n in conteos.items():
        md.append(f"| `{c}` | {n:,} | {ESPERADO[c]:,} |")
    md.append("\n## 2. Validaciones\n")
    md.append("| Validación | Resultado |")
    md.append("|---|---|")
    md.append(f"| Suma de `atletas[]` en resultados | {suma_atletas:,} |")
    md.append(f"| Atletas con participación | {len(ids_en_resultados):,} |")
    md.append(f"| Regiones (países + catálogo) | {regiones_paises:,} + {sin_pais_regiones} |")
    md.append(f"| Ciudades (países + catálogo) | {ciudades_paises:,} + {sin_pais_ciudades} |")
    md.append(f"| Población en países | {poblacion_total:,} |")
    md.append(f"| Resultados multipaís | {multipais:,} (empates {empates:,}, no empates {no_empates:,}) |")
    md.append(f"| Marcados para revisar | {revisar:,} |")
    md.append(f"| Equipos mixtos | {mixtos:,} |")
    md.append(f"| Medallas (Oro/Plata/Bronce/Sin) | {medallas.get('ORO',0):,} / {medallas.get('PLATA',0):,} / {medallas.get('BRONCE',0):,} / {medallas.get(None,0):,} |")
    md.append(f"| Fallos | **{len(fallos)}** |\n")
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
    md.append("## 3. Rendimiento\n")
    md.append("| Consulta | Mediana (ms) | Plan |")
    md.append("|---|---:|---|")
    md.append(f"| Atleta por nombre | {t_atleta:.3f} | {', '.join(planes['atleta_nombre'])} |")
    md.append(f"| País por NOC | {t_pais:.3f} | {', '.join(planes['pais_noc'])} |")
    md.append(f"| Detalle país, 100 | {t_detalle:.3f} | {', '.join(planes['detalle_pais'])} |")
    md.append("\n## 4. Controles\n")
    md.append("```json")
    md.append(json.dumps({"phelps": reporte["phelps"], "guatemala": reporte["guatemala"]}, ensure_ascii=False, indent=2))
    md.append("```")
    md.append("\n## 5. Reproducción\n")
    md.append("```bash")
    md.append("cd Fase3")
    md.append("./run_all.sh")
    md.append("```")
    md.append("")
    (EVIDENCIA_DIR / "fase5" / "validacion.md").write_text("\n".join(md), encoding="utf-8")

    log(f"Fallos: {len(fallos)}")
    for f in fallos:
        log(f"  [FALLO] {f}")
    log(f"Rendimiento: atleta {t_atleta:.2f} ms | país {t_pais:.2f} ms | detalle {t_detalle:.2f} ms")
    cliente.close()
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
