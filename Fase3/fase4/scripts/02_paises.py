#!/usr/bin/env python3
"""
Fase 4.2 - Construir la colección `paises`.

Perfil geográfico (regiones/ciudades), población, sedes y resumen derivado de
`resultados`. El resumen de medallas cuenta una medalla por país/equipo por
resultado; los equipos mixtos se separan en `medallasMixtas`.

Uso:
  python3 fase4/scripts/02_paises.py --recrear
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

FASE3_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FASE3_DIR))

from lib.common import (  # noqa: E402
    ahora,
    conectar_mongo,
    evidencia,
    insertar_lotes,
    leer_alias,
    leer_dim_sedes,
    log,
    normalizar,
    normalizar_con_fallback,
    preparar_coleccion,
    psql_json,
)


def resumen_vacio() -> dict:
    return {
        "participaciones": 0,
        "atletas": 0,
        "juegos": 0,
        "anios": [],
        "deportes": [],
        "medallas": {"oro": 0, "plata": 0, "bronce": 0, "total": 0},
        "medallasAtleta": {"oro": 0, "plata": 0, "bronce": 0, "total": 0},
        "medallasMixtas": {"oro": 0, "plata": 0, "bronce": 0, "total": 0},
        "primerAnio": None,
        "ultimoAnio": None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Construye paises (Fase 4)")
    ap.add_argument("--recrear", action="store_true", help="reconstruye la colección")
    args = ap.parse_args()

    log("Fase 4.2 - Construyendo paises")
    _, db = conectar_mongo()
    if db.resultados.estimated_document_count() == 0:
        raise SystemExit("La colección resultados está vacía. Ejecute primero la Fase 3.")
    preparar_coleccion(db, "paises", args.recrear)

    paises = psql_json(
        'SELECT json_build_object(\'id\',"ID",\'nombre\',"NOMBRE",\'noc\',"NOC") '
        'FROM "PAIS" ORDER BY "ID";'
    )
    regiones = psql_json(
        'SELECT json_build_object(\'id\',"ID",\'nombre\',"NOMBRE",\'paisId\',"ID_PAIS") '
        'FROM "REGION" ORDER BY "ID";'
    )
    ciudades = psql_json(
        'SELECT json_build_object(\'id\',"ID",\'nombre\',"NOMBRE",\'lat\',"LAT",'
        '\'long\',"LONG",\'regionId\',"ID_REGION") FROM "CIUDAD" ORDER BY "ID";'
    )
    poblacion = psql_json(
        'SELECT json_build_object(\'paisId\',"ID_PAIS",\'anio\',"YEAR",'
        '\'cantidad\',"CANTIDAD") FROM "POBLACION" ORDER BY "ID";'
    )

    alias = leer_alias()
    sedes_por_noc: dict[str, list] = defaultdict(list)
    for s in leer_dim_sedes().values():
        sedes_por_noc[s["PAIS_NOC"]].append(
            {
                "anio": int(s["ANIO"]),
                "temporada": s["TEMPORADA"],
                "categoria": s["CATEGORIA"],
                "ciudad": s["CIUDAD"],
                "nota": s["NOTA"],
            }
        )

    # Regiones con sus ciudades.
    regiones_por_pais: dict[int, list] = defaultdict(list)
    regiones_index = {}
    for r in regiones:
        item = {"id": r["id"], "nombre": r["nombre"], "ciudades": []}
        regiones_por_pais[r["paisId"]].append(item)
        regiones_index[r["id"]] = item

    ciudades_sin_region = 0
    for c in ciudades:
        item = {
            "id": c["id"],
            "nombre": c["nombre"],
            "lat": c["lat"],
            "long": c["long"],
        }
        region = regiones_index.get(c["regionId"])
        if region is None:
            ciudades_sin_region += 1
            continue
        region["ciudades"].append(item)

    pob_por_pais: dict[int, list] = defaultdict(list)
    for p in poblacion:
        pob_por_pais[p["paisId"]].append({"anio": p["anio"], "cantidad": p["cantidad"]})

    documentos = []
    for p in paises:
        n = normalizar_con_fallback(p["nombre"])
        documentos.append(
            {
                "_id": p["id"],
                "nombre": p["nombre"],
                "noc": p["noc"],
                "nombreNormalizado": n["normalizado"],
                "normalizado": n["ok"],
                "alias": sorted(alias.get(p["noc"], [])),
                "aliasNormalizado": sorted(
                    {normalizar(a) for a in alias.get(p["noc"], [])}
                ),
                "regiones": regiones_por_pais.get(p["id"], []),
                "poblacion": sorted(pob_por_pais.get(p["id"], []), key=lambda x: x["anio"]),
                "sedes": sorted(sedes_por_noc.get(p["noc"], []), key=lambda x: x["anio"]),
                "resumen": resumen_vacio(),
            }
        )

    insertados = insertar_lotes(db.paises, documentos)
    if insertados != 247:
        raise SystemExit(f"Se esperaban 247 países y se insertaron {insertados:,}")

    log("Calculando resumen de participaciones...")
    base = list(
        db.resultados.aggregate(
            [
                {"$unwind": "$atletas"},
                {
                    "$group": {
                        "_id": "$atletas.noc",
                        "participaciones": {"$sum": 1},
                        "atletas": {"$addToSet": "$atletas.id"},
                        "juegos": {"$addToSet": "$edicion.id"},
                        "anios": {"$addToSet": "$edicion.anio"},
                        "deportes": {"$addToSet": "$deporte.nombre"},
                        "primerAnio": {"$min": "$edicion.anio"},
                        "ultimoAnio": {"$max": "$edicion.anio"},
                    }
                },
            ],
            allowDiskUse=True,
        )
    )

    log("Calculando medallas por evento y por atleta...")
    medallas = list(
        db.resultados.aggregate(
            [
                {"$unwind": "$paises"},
                {"$match": {"medalla.codigo": {"$ne": None}, "equipoMixto": False}},
                {"$group": {"_id": {"pais": "$paises", "codigo": "$medalla.codigo"}, "n": {"$sum": 1}}},
            ],
            allowDiskUse=True,
        )
    )
    medallas_atleta = list(
        db.resultados.aggregate(
            [
                {"$unwind": "$atletas"},
                {"$match": {"medalla.codigo": {"$ne": None}}},
                {"$group": {"_id": {"pais": "$atletas.noc", "codigo": "$medalla.codigo"}, "n": {"$sum": 1}}},
            ],
            allowDiskUse=True,
        )
    )
    medallas_mixtas = list(
        db.resultados.aggregate(
            [
                {"$unwind": "$paises"},
                {"$match": {"medalla.codigo": {"$ne": None}, "equipoMixto": True}},
                {"$group": {"_id": {"pais": "$paises", "codigo": "$medalla.codigo"}, "n": {"$sum": 1}}},
            ],
            allowDiskUse=True,
        )
    )

    def mapa_medallas(filas):
        salida = defaultdict(dict)
        for f in filas:
            salida[f["_id"]["pais"]][f["_id"]["codigo"]] = f["n"]
        return salida

    mapa = mapa_medallas(medallas)
    mapa_atleta = mapa_medallas(medallas_atleta)
    mapa_mixtas = mapa_medallas(medallas_mixtas)
    base_por_noc = {b["_id"]: b for b in base}
    nocs = {p["noc"] for p in paises}

    for noc in nocs:
        b = base_por_noc.get(noc, {})
        p = db.paises.find_one({"noc": noc})
        resumen = {
            "participaciones": b.get("participaciones", 0),
            "atletas": len(b.get("atletas", [])),
            "juegos": len(b.get("juegos", [])),
            "anios": sorted(b.get("anios", [])),
            "deportes": sorted(b.get("deportes", [])),
            "medallas": {**{"oro": 0, "plata": 0, "bronce": 0},
                         **{k: v for k, v in {
                             "oro": mapa[noc].get("ORO", 0),
                             "plata": mapa[noc].get("PLATA", 0),
                             "bronce": mapa[noc].get("BRONCE", 0),
                         }.items()}},
            "medallasAtleta": {
                "oro": mapa_atleta[noc].get("ORO", 0),
                "plata": mapa_atleta[noc].get("PLATA", 0),
                "bronce": mapa_atleta[noc].get("BRONCE", 0),
            },
            "medallasMixtas": {
                "oro": mapa_mixtas[noc].get("ORO", 0),
                "plata": mapa_mixtas[noc].get("PLATA", 0),
                "bronce": mapa_mixtas[noc].get("BRONCE", 0),
            },
            "primerAnio": b.get("primerAnio"),
            "ultimoAnio": b.get("ultimoAnio"),
        }
        for campo in ("medallas", "medallasAtleta", "medallasMixtas"):
            resumen[campo]["total"] = sum(resumen[campo].values())
        db.paises.update_one({"_id": p["_id"]}, {"$set": {"resumen": resumen}})

    gua = db.paises.find_one({"noc": "GUA"}, {"nombre": 1, "resumen": 1, "sedes": 1})
    gre = db.paises.find_one({"noc": "GRE"}, {"nombre": 1, "resumen": 1, "sedes": 1})
    sin_pais = db.catalogos.count_documents({"tipo": "ciudad_sin_pais"})

    evidencia(
        "fase4",
        "paises",
        {
            "generado_en": ahora(),
            "insertados": insertados,
            "ciudades_sin_region": ciudades_sin_region,
            "ciudades_sin_pais_en_catalogos": sin_pais,
            "guatemala": gua,
            "grecia": gre,
        },
    )
    log(
        f"Países insertados: {insertados} | ciudades sin región: {ciudades_sin_region} | "
        f"ciudades sin país en catalogos: {sin_pais}"
    )
    log(f"Guatemala: {gua['resumen']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
