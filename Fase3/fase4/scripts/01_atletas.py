#!/usr/bin/env python3
"""
Fase 4.1 - Construir la colección `atletas`.

Perfil desde ATLETA + ciudad/región/país. El resumen se calcula después con
una agregación sobre `resultados` (participaciones, juegos, años, deportes y
medallas). No se embebe el historial completo.

Uso:
  python3 fase4/scripts/01_atletas.py --recrear
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

FASE3_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FASE3_DIR))

from lib.common import (  # noqa: E402
    ahora,
    conectar_mongo,
    evidencia,
    insertar_lotes,
    log,
    normalizar_con_fallback,
    preparar_coleccion,
    psql_stream,
)

SQL = '''
SELECT json_build_object(
  '_id', a."ID",
  'nombre', a."NOMBRE",
  'sexo', a."SEXO",
  'fechaNacimiento', a."BORN_DATE",
  'fechaFallecimiento', a."DIED_DATE",
  'altura', a."ALTURA",
  'peso', a."PESO",
  'lugarNacimiento', CASE WHEN c."ID" IS NULL THEN NULL ELSE
    json_build_object(
      'ciudad', c."NOMBRE",
      'region', r."NOMBRE",
      'pais', p."NOMBRE",
      'paisNoc', p."NOC"
    ) END
)
FROM "ATLETA" a
LEFT JOIN "CIUDAD" c ON c."ID" = a."ID_CITY_NACIMIENTO"
LEFT JOIN "REGION" r ON r."ID" = c."ID_REGION"
LEFT JOIN "PAIS" p   ON p."ID" = r."ID_PAIS"
ORDER BY a."ID";
'''


def main() -> int:
    ap = argparse.ArgumentParser(description="Construye atletas (Fase 4)")
    ap.add_argument("--recrear", action="store_true", help="reconstruye la colección")
    args = ap.parse_args()

    log("Fase 4.1 - Construyendo atletas")
    _, db = conectar_mongo()
    if db.resultados.estimated_document_count() == 0:
        raise SystemExit("La colección resultados está vacía. Ejecute primero la Fase 3.")
    preparar_coleccion(db, "atletas", args.recrear)

    def generar():
        for p in psql_stream(SQL):
            n = normalizar_con_fallback(p["nombre"])
            p["nombreNormalizado"] = n["normalizado"]
            p["normalizado"] = n["ok"]
            p["resumen"] = {
                "participaciones": 0,
                "juegos": 0,
                "anios": [],
                "deportes": [],
                "medallas": {"oro": 0, "plata": 0, "bronce": 0, "total": 0},
            }
            yield p

    insertados = insertar_lotes(db.atletas, generar())
    if insertados != 145_500:
        raise SystemExit(f"Se esperaban 145,500 atletas y se insertaron {insertados:,}")

    log("Calculando resumen desde resultados...")
    pipeline = [
        {"$unwind": "$atletas"},
        {
            "$group": {
                "_id": "$atletas.id",
                "participaciones": {"$sum": 1},
                "juegos": {"$addToSet": "$edicion.id"},
                "anios": {"$addToSet": "$edicion.anio"},
                "deportes": {"$addToSet": "$deporte.nombre"},
                "oro": {"$sum": {"$cond": [{"$eq": ["$medalla.codigo", "ORO"]}, 1, 0]}},
                "plata": {"$sum": {"$cond": [{"$eq": ["$medalla.codigo", "PLATA"]}, 1, 0]}},
                "bronce": {"$sum": {"$cond": [{"$eq": ["$medalla.codigo", "BRONCE"]}, 1, 0]}},
            }
        },
        {
            "$project": {
                "resumen": {
                    "participaciones": "$participaciones",
                    "juegos": {"$size": "$juegos"},
                    "anios": {"$sortArray": {"input": "$anios", "sortBy": 1}},
                    "deportes": {"$sortArray": {"input": "$deportes", "sortBy": 1}},
                    "medallas": {
                        "oro": "$oro",
                        "plata": "$plata",
                        "bronce": "$bronce",
                        "total": {"$add": ["$oro", "$plata", "$bronce"]},
                    },
                }
            }
        },
        {
            "$merge": {
                "into": "atletas",
                "on": "_id",
                "whenMatched": "merge",
                "whenNotMatched": "discard",
            }
        },
    ]
    list(db.resultados.aggregate(pipeline, allowDiskUse=True))

    con_resumen = db.atletas.count_documents({"resumen.participaciones": {"$gt": 0}})
    sin_resumen = db.atletas.count_documents({"resumen.participaciones": 0})
    phelps = db.atletas.find_one({"nombreNormalizado": "michael phelps"}, {"nombre": 1, "resumen": 1})

    evidencia(
        "fase4",
        "atletas",
        {
            "generado_en": ahora(),
            "insertados": insertados,
            "con_participaciones": con_resumen,
            "sin_participaciones": sin_resumen,
            "phelps": phelps,
        },
    )
    log(f"Atletas insertados: {insertados:,} | con participación: {con_resumen:,} | sin: {sin_resumen:,}")
    log(f"Control Phelps: {phelps}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
