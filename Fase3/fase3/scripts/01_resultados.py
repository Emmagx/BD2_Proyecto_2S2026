#!/usr/bin/env python3
"""
Fase 3.1 - Construir la colección `resultados`.

Un documento por fila de RESULTADO. Los atletas del resultado se guardan en
`atletas[]`; `paises[]` contiene los NOC únicos y `multipais` indica si hay más
de uno. La medalla vive una sola vez en el documento.

Uso:
  python3 fase3/scripts/01_resultados.py --recrear
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

FASE3_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FASE3_DIR))

from lib.common import (  # noqa: E402
    ahora,
    codigo_medalla,
    conectar_mongo,
    evidencia,
    insertar_lotes,
    leer_dim_juegos,
    log,
    preparar_coleccion,
    psql_stream,
)

SQL = '''
SELECT json_build_object(
  '_id', r."ID",
  'edicion', json_build_object(
      'id', r."ID_OLIMPIADA",
      'anio', o."YEAR",
      'temporada', o."SEASON"
  ),
  'deporte', json_build_object('id', d."ID", 'nombre', d."NOMBRE"),
  'disciplina', json_build_object('id', di."ID", 'nombre', di."NOMBRE"),
  'evento', json_build_object('id', e."ID", 'nombre', e."NOMBRE"),
  'posicion', r."PLACE",
  'empate', r."TIED",
  'estado', r."STATE",
  'medalla', CASE WHEN r."ID_MEDALLA" = 1 THEN NULL
                  ELSE json_build_object('id', m."ID", 'nombre', m."NOMBRE") END,
  'atletas', json_agg(
      json_build_object(
        'id', a."ID", 'nombre', a."NOMBRE", 'noc', p."NOC", 'edad', ra."EDAD"
      ) ORDER BY a."ID"
  )
)
FROM "RESULTADO" r
JOIN "OLIMPIADA" o       ON o."ID" = r."ID_OLIMPIADA"
JOIN "EVENTO" e          ON e."ID" = r."ID_EVENTO"
JOIN "DISCIPLINA" di     ON di."ID" = e."ID_DISCIPLINA"
JOIN "DEPORTE" d         ON d."ID" = di."ID_DEPORTE"
JOIN "MEDALLA" m         ON m."ID" = r."ID_MEDALLA"
JOIN "RESULTADO_ATLETA" ra ON ra."ID_RESULTADO" = r."ID"
JOIN "ATLETA" a          ON a."ID" = ra."ID_ATLETA"
JOIN "PAIS" p            ON p."ID" = ra."ID_PAIS_REPRESENTA"
GROUP BY r."ID", r."ID_OLIMPIADA", o."YEAR", o."SEASON",
         d."ID", d."NOMBRE", di."ID", di."NOMBRE",
         e."ID", e."NOMBRE", r."PLACE", r."TIED", r."STATE",
         r."ID_MEDALLA", m."ID", m."NOMBRE"
ORDER BY r."ID";
'''


def main() -> int:
    ap = argparse.ArgumentParser(description="Construye resultados (Fase 3)")
    ap.add_argument("--recrear", action="store_true", help="reconstruye la colección")
    args = ap.parse_args()

    log("Fase 3.1 - Construyendo resultados")
    _, db = conectar_mongo()
    preparar_coleccion(db, "resultados", args.recrear)
    juegos = leer_dim_juegos()

    conteos = Counter()
    medallas = Counter()
    total = 0
    muestra_25 = None

    def generar():
        nonlocal total, muestra_25
        for doc in psql_stream(SQL):
            jid = doc["edicion"]["id"]
            j = juegos.get(jid)
            if not j:
                raise RuntimeError(f"Juego {jid} no está en dim_juegos")
            doc["edicion"]["temporada"] = j["TEMPORADA"]
            doc["edicion"]["categoria"] = j["CATEGORIA"]

            atletas = doc["atletas"]
            paises = sorted({a["noc"] for a in atletas if a.get("noc")})
            evento_nombre = doc["evento"]["nombre"] or ""
            doc["paises"] = paises
            doc["multipais"] = len(paises) > 1
            doc["paisEquipo"] = paises[0] if len(paises) == 1 else None
            doc["equipoMixto"] = bool(
                doc["multipais"]
                and (
                    "Mixed" in evento_nombre
                    or "Youth" in evento_nombre
                    or "YOG" in evento_nombre
                )
            )
            doc["revisar"] = bool(
                doc["multipais"]
                and not doc["empate"]
                and doc["medalla"] is not None
                and not doc["equipoMixto"]
            )

            med = doc["medalla"]
            if med:
                med["codigo"] = codigo_medalla(med["nombre"])
                medallas[med["codigo"]] += 1
            else:
                medallas["SIN_MEDALLA"] += 1

            conteos["resultados"] += 1
            if doc["multipais"]:
                conteos["multipais"] += 1
            if doc["multipais"] and doc["empate"]:
                conteos["multipais_empate"] += 1
            if doc["multipais"] and not doc["empate"]:
                conteos["multipais_no_empate"] += 1
            if doc["equipoMixto"]:
                conteos["equipo_mixto"] += 1
            if doc["revisar"]:
                conteos["revisar"] += 1
            if doc["_id"] == 25:
                muestra_25 = doc
            total += 1
            yield doc

    insertados = insertar_lotes(db.resultados, generar())
    if insertados != 156_032:
        raise SystemExit(f"Se esperaban 156,032 resultados y se insertaron {insertados:,}")

    evidencia(
        "fase3",
        "resultados",
        {
            "generado_en": ahora(),
            "insertados": insertados,
            "conteos": dict(conteos),
            "medallas": dict(medallas),
            "muestra_resultado_25": muestra_25,
        },
    )
    log(f"Resultados insertados: {insertados:,}")
    log(f"Conteos: {dict(conteos)}")
    log(f"Medallas: {dict(medallas)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
