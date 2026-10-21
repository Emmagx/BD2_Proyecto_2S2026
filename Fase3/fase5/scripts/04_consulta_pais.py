#!/usr/bin/env python3
"""
Fase 5.4 - Consulta de un país.

Uso:
  python3 fase5/scripts/04_consulta_pais.py "Guatemala"
  python3 fase5/scripts/04_consulta_pais.py "Estados Unidos" --anio 2012
  python3 fase5/scripts/04_consulta_pais.py GUA --deporte swimming --medalla oro
  python3 fase5/scripts/04_consulta_pais.py "Grecia" --limite 10
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FASE3_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FASE3_DIR))

from lib.common import conectar_mongo, normalizar  # noqa: E402

MEDALLAS = {"oro": "ORO", "gold": "ORO", "plata": "PLATA", "silver": "PLATA", "bronce": "BRONCE", "bronze": "BRONCE", "ninguna": None, "no medal": None}


def texto_medalla(m):
    if not m:
        return "—"
    return {"ORO": "Oro", "PLATA": "Plata", "BRONCE": "Bronce"}.get(m.get("codigo"), m.get("nombre", "—"))


def recortar(s, n):
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


def buscar(db, texto: str):
    texto = texto.strip()
    doc = db.paises.find_one({"noc": texto.upper()})
    if doc:
        return [doc]
    q = normalizar(texto)
    candidatos = list(db.paises.find({"nombreNormalizado": q}))
    if candidatos:
        return candidatos
    candidatos = list(db.paises.find({"alias": q}))
    if candidatos:
        return candidatos
    return list(db.paises.find({"nombreNormalizado": {"$regex": "^" + re.escape(q)}}).limit(10))


def main() -> int:
    ap = argparse.ArgumentParser(description="Consulta de país (Fase 3)")
    ap.add_argument("pais", nargs="?", help="nombre, alias o NOC")
    ap.add_argument("--noc", help="NOC exacto")
    ap.add_argument("--deporte")
    ap.add_argument("--medalla", help="oro/plata/bronce/ninguna")
    ap.add_argument("--anio", type=int)
    ap.add_argument("--limite", type=int, default=100, help="0 = todos")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    texto = args.noc or args.pais
    if not texto:
        ap.error("indique un país o use --noc")

    _, db = conectar_mongo()
    candidatos = buscar(db, texto)
    if not candidatos:
        print(f"No se encontró un país para '{texto}'.", file=sys.stderr)
        return 2
    doc = max(candidatos, key=lambda d: (d.get("resumen") or {}).get("participaciones", 0))
    if len(candidatos) > 1:
        print(f"Se encontraron {len(candidatos)} países para '{texto}':")
        for c in candidatos:
            print(f"  - {c['nombre']:<35} NOC {c.get('noc') or '—':<4} participaciones: {(c.get('resumen') or {}).get('participaciones', 0)}")
        print(f"\nSe mostrará {doc['nombre']}. Use --noc para precisar.\n")

    query = {"atletas.noc": doc["noc"]}
    if args.anio is not None:
        query["edicion.anio"] = args.anio
    if args.deporte:
        query["deporte.nombre"] = {"$regex": re.escape(args.deporte), "$options": "i"}
    if args.medalla:
        codigo = MEDALLAS.get(args.medalla.lower())
        if codigo is None:
            query["medalla"] = None
        else:
            query["medalla.codigo"] = codigo

    cursor = db.resultados.find(query).sort("edicion.anio", -1)
    if args.limite and args.limite > 0:
        cursor = cursor.limit(args.limite)
    resultados = list(cursor)
    total_filtrado = db.resultados.count_documents(query)

    if args.json:
        print(json.dumps(
            {
                "pais": {k: v for k, v in doc.items() if k not in {"regiones"}},
                "resumen": doc.get("resumen", {}),
                "filtros": {"deporte": args.deporte, "medalla": args.medalla, "anio": args.anio},
                "total_filtrado": total_filtrado,
                "resultados": resultados,
            },
            ensure_ascii=False, indent=2, default=str,
        ))
        return 0

    resumen = doc.get("resumen") or {}
    med = resumen.get("medallas") or {}
    print("=" * 88)
    print(f"PAÍS: {doc['nombre']}  (NOC {doc.get('noc')}, ID {doc['_id']})")
    print("=" * 88)
    regiones = doc.get("regiones") or []
    n_ciudades = sum(len(r.get("ciudades", [])) for r in regiones)
    print(f"Regiones   : {len(regiones)} | Ciudades: {n_ciudades}")
    pob = doc.get("poblacion") or []
    if pob:
        print(f"Población  : {pob[-1]['anio']} = {pob[-1]['cantidad']:,}")
    sedes = doc.get("sedes") or []
    if sedes:
        partes = []
        for s in sedes:
            etiqueta = f"{s['anio']} {s['temporada']}"
            if s.get("categoria") and s["categoria"] != "Senior":
                etiqueta += f" [{s['categoria']}]"
            partes.append(f"{etiqueta}: {s['ciudad']}")
        print(f"Sede       : Sí — " + "; ".join(partes))
    else:
        print("Sede       : No ha sido sede de Juegos Olímpicos (según el dataset).")
    print(f"Global     : {resumen.get('participaciones', 0):,} participaciones | {resumen.get('atletas', 0):,} atletas | {resumen.get('juegos', 0)} juegos")
    print(f"Medallas   : por evento Oro {med.get('oro', 0)}, Plata {med.get('plata', 0)}, Bronce {med.get('bronce', 0)} (total {med.get('total', 0)})")
    if resumen.get("medallasAtleta"):
        ma = resumen["medallasAtleta"]
        print(f"             por atleta: Oro {ma.get('oro', 0)}, Plata {ma.get('plata', 0)}, Bronce {ma.get('bronce', 0)}")
    if args.deporte or args.medalla or args.anio is not None:
        print(f"Filtros    : deporte={args.deporte or '—'}, medalla={args.medalla or '—'}, anio={args.anio or '—'}")
        print(f"Resultados : {total_filtrado:,} coincidencias")

    print()
    if not resultados:
        print("Sin resultados para los filtros.")
        return 0

    filas = []
    for r in resultados:
        atletas = [a for a in r.get("atletas", []) if a.get("noc") == doc["noc"]]
        nombres = ", ".join(a["nombre"] for a in atletas)
        filas.append([
            r["edicion"]["anio"],
            recortar(nombres, 32),
            recortar(r["deporte"]["nombre"], 20),
            recortar(r["evento"]["nombre"], 34),
            texto_medalla(r.get("medalla")),
            "—" if r.get("posicion") is None else r.get("posicion"),
            r.get("estado"),
        ])
    print(tabla(["Año", "Atleta(s)", "Deporte", "Evento", "Medalla", "Puesto", "Estado"], filas))
    if args.limite and args.limite > 0 and total_filtrado > len(resultados):
        print(f"\nMostrando {len(resultados):,} de {total_filtrado:,} resultados. Use --limite 0 para todos.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
