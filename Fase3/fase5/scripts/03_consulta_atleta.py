#!/usr/bin/env python3
"""
Fase 5.3 - Consulta de un atleta.

Uso:
  python3 fase5/scripts/03_consulta_atleta.py "Michael Phelps"
  python3 fase5/scripts/03_consulta_atleta.py "Michael Phelps" --anio 2008
  python3 fase5/scripts/03_consulta_atleta.py "Usain Bolt" --medalla oro
  python3 fase5/scripts/03_consulta_atleta.py --id 93860 --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

FASE3_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FASE3_DIR))

from lib.common import conectar_mongo, normalizar, normalizar_deporte  # noqa: E402

MEDALLAS = {"oro": "ORO", "gold": "ORO", "plata": "PLATA", "silver": "PLATA", "bronce": "BRONCE", "bronze": "BRONCE", "ninguna": None, "no medal": None}


def texto_medalla(m) -> str:
    if not m:
        return "—"
    return {"ORO": "Oro", "PLATA": "Plata", "BRONCE": "Bronce"}.get(m.get("codigo"), m.get("nombre", "—"))


def recortar(s: str, n: int) -> str:
    s = "" if s is None else str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


def tabla(cabeceras, filas):
    anchos = [len(c) for c in cabeceras]
    for f in filas:
        for i, c in enumerate(f):
            anchos[i] = max(anchos[i], len(str(c)))
    lineas = ["  ".join(str(c).ljust(anchos[i]) for i, c in enumerate(cabeceras))]
    lineas.append("  ".join("-" * a for a in anchos))
    for f in filas:
        lineas.append("  ".join(str(c).ljust(anchos[i]) for i, c in enumerate(f)))
    return "\n".join(lineas)


def main() -> int:
    ap = argparse.ArgumentParser(description="Consulta de atleta (Fase 3)")
    ap.add_argument("nombre", nargs="?", help="nombre del atleta")
    ap.add_argument("--id", type=int, help="ID exacto")
    ap.add_argument("--deporte")
    ap.add_argument("--pais", help="NOC o nombre del país representado")
    ap.add_argument("--anio", type=int)
    ap.add_argument("--medalla", help="oro/plata/bronce/ninguna")
    ap.add_argument("--todos", action="store_true", help="mostrar todos los homónimos")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if not args.nombre and not args.id:
        ap.error("indique un nombre o use --id")

    _, db = conectar_mongo()
    # Si --pais viene como nombre ("Estados Unidos"), resolverlo a NOC.
    if args.pais:
        qp = normalizar(args.pais)
        pais_doc = db.paises.find_one(
            {"$or": [{"noc": args.pais.upper()}, {"nombreNormalizado": qp}, {"aliasNormalizado": qp}]}
        )
        if pais_doc:
            args.pais = pais_doc["noc"]
    if args.id:
        doc = db.atletas.find_one({"_id": args.id})
        candidatos = [doc] if doc else []
    else:
        q = normalizar(args.nombre)
        candidatos = list(db.atletas.find({"nombreNormalizado": q}).limit(20))
        if not candidatos:
            candidatos = list(db.atletas.find({"nombreNormalizado": {"$regex": "^" + q}}).limit(20))
        if not candidatos:
            candidatos = list(db.atletas.find({"nombreNormalizado": {"$regex": q}}).limit(20))
    if not candidatos:
        print(f"No se encontró un atleta para '{args.nombre}'.", file=sys.stderr)
        return 2

    def puntaje(d):
        r = d.get("resumen") or {}
        m = r.get("medallas") or {}
        return (m.get("total", 0), r.get("participaciones", 0))

    elegido = max(candidatos, key=puntaje)
    if len(candidatos) > 1:
        print(f"Se encontraron {len(candidatos)} atletas para '{args.nombre}':")
        for c in sorted(candidatos, key=lambda d: -puntaje(d)[1]):
            print(f"  - ID {c['_id']:>6}  {c['nombre']:<32} participaciones: {(c.get('resumen') or {}).get('participaciones', 0)}")
        if not args.todos:
            print(f"\nSe mostrará el de mayor trayectoria (ID {elegido['_id']}). Use --id o --todos.\n")

    docs = candidatos if (args.todos and len(candidatos) > 1 and not args.id) else [elegido]
    med_q = MEDALLAS.get(args.medalla.lower()) if args.medalla else "NO_FILTRO"
    salida_json = []

    for doc in docs:
        resultados = list(db.resultados.find({"atletas.id": doc["_id"]}).sort("edicion.anio", 1))
        filas, partes = [], []
        for r in resultados:
            atleta = next((a for a in r["atletas"] if a["id"] == doc["_id"]), None)
            if not atleta:
                continue
            if args.deporte and normalizar_deporte(args.deporte) not in normalizar(r["deporte"]["nombre"]):
                continue
            if args.pais and normalizar(args.pais) not in normalizar(atleta.get("noc")):
                continue
            if args.anio is not None and r["edicion"]["anio"] != args.anio:
                continue
            if med_q != "NO_FILTRO":
                cod = r["medalla"]["codigo"] if r["medalla"] else None
                if cod != med_q:
                    continue
            partes.append(
                {
                    "resultado_id": r["_id"],
                    "edicion": r["edicion"],
                    "deporte": r["deporte"],
                    "disciplina": r["disciplina"],
                    "evento": r["evento"],
                    "pais": atleta["noc"],
                    "edad": atleta.get("edad"),
                    "posicion": r.get("posicion"),
                    "empate": r.get("empate"),
                    "estado": r.get("estado"),
                    "medalla": r.get("medalla"),
                }
            )
            filas.append(
                [
                    r["edicion"]["anio"],
                    f"{r['edicion']['anio']} {r['edicion']['temporada'][:1]}",
                    recortar(r["deporte"]["nombre"], 22),
                    recortar(r["evento"]["nombre"], 34),
                    atleta["noc"],
                    atleta.get("edad") if atleta.get("edad") is not None else "—",
                    texto_medalla(r.get("medalla")),
                    ("—" if r.get("posicion") is None else str(r.get("posicion"))) + ("*" if r.get("empate") else ""),
                    r.get("estado"),
                ]
            )

        medallas = {"oro": 0, "plata": 0, "bronce": 0}
        for p in partes:
            m = p.get("medalla")
            if m:
                clave = {"ORO": "oro", "PLATA": "plata", "BRONCE": "bronce"}.get(m.get("codigo"))
                if clave:
                    medallas[clave] += 1
        juegos = len({(p["edicion"]["anio"], p["edicion"]["temporada"]) for p in partes})
        anios = sorted({p["edicion"]["anio"] for p in partes})
        deportes = sorted({p["deporte"]["nombre"] for p in partes})

        if args.json:
            salida_json.append(
                {
                    "atleta": {k: v for k, v in doc.items()},
                    "resumen": {
                        "participaciones": len(partes),
                        "juegos": juegos,
                        "anios": anios,
                        "deportes": deportes,
                        "medallas": {**medallas, "total": sum(medallas.values())},
                    },
                    "participaciones": partes,
                }
            )
            continue

        nac = doc.get("lugarNacimiento") or {}
        lugar = ", ".join(x for x in [nac.get("ciudad"), nac.get("region"), nac.get("pais")] if x) or "No registrado"
        print("=" * 78)
        print(f"ATLETA: {doc['nombre']}  (ID {doc['_id']})")
        print("=" * 78)
        print(f"Nacimiento : {lugar}")
        print(f"Fechas     : {doc.get('fechaNacimiento') or '—'} → {doc.get('fechaFallecimiento') or '—'}")
        print(f"Sexo       : {doc.get('sexo') or '—'}   Altura: {doc.get('altura') or '—'} cm   Peso: {doc.get('peso') or '—'} kg")
        print(f"Juegos     : {juegos}   Participaciones: {len(partes)}")
        print(f"Medallas   : {sum(medallas.values())} (Oro {medallas['oro']}, Plata {medallas['plata']}, Bronce {medallas['bronce']})")
        if anios:
            print(f"Años       : {', '.join(map(str, anios))}")
        if deportes:
            print(f"Deportes   : {', '.join(deportes)}")
        if not filas:
            print("\nSin participaciones que coincidan con los filtros.")
        else:
            print()
            print(tabla(["Año", "Juego", "Deporte", "Evento", "País", "Edad", "Medalla", "Puesto", "Estado"], filas))
            print("\n* = puesto compartido (empate).")

    if args.json:
        print(json.dumps(salida_json[0] if len(salida_json) == 1 else salida_json, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
