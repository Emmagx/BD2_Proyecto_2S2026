#!/usr/bin/env python3
"""
Fase 2.1 - Construir la colección `catalogos`.

Un documento por entidad, con `_id` prefijado para evitar choques:
  juego:<ID>, deporte:<ID>, disciplina:<ID>, evento:<ID>, medalla:<ID>

Fuente: PostgreSQL (OLIMPIADA, DEPORTE, DISCIPLINA, EVENTO, MEDALLA) y los
insumos de Fase 1 (dim_juegos.csv / dim_sedes.csv).

Uso:
  python3 fase2/scripts/01_catalogos.py --recrear
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
    leer_dim_sedes,
    log,
    normalizar,
    preparar_coleccion,
    psql_json,
)

ESPERADO = {"juego": 62, "deporte": 93, "disciplina": 1520, "evento": 1904, "medalla": 4}


def main() -> int:
    ap = argparse.ArgumentParser(description="Construye catalogos (Fase 2)")
    ap.add_argument("--recrear", action="store_true", help="reconstruye la colección")
    args = ap.parse_args()

    log("Fase 2.1 - Construyendo catalogos")
    _, db = conectar_mongo()
    preparar_coleccion(db, "catalogos", args.recrear)

    juegos = leer_dim_juegos()
    sedes = leer_dim_sedes()

    deportes = psql_json(
        'SELECT json_build_object(\'id\',"ID",\'nombre\',"NOMBRE") '
        'FROM "DEPORTE" ORDER BY "ID";'
    )
    disciplinas = psql_json(
        'SELECT json_build_object(\'id\',"ID",\'nombre\',"NOMBRE",\'deporteId\',"ID_DEPORTE") '
        'FROM "DISCIPLINA" ORDER BY "ID";'
    )
    eventos = psql_json(
        'SELECT json_build_object(\'id\',"ID",\'nombre\',"NOMBRE",\'disciplinaId\',"ID_DISCIPLINA") '
        'FROM "EVENTO" ORDER BY "ID";'
    )
    medallas = psql_json(
        'SELECT json_build_object(\'id\',"ID",\'nombre\',"NOMBRE") '
        'FROM "MEDALLA" ORDER BY "ID";'
    )

    documentos = []

    for jid, j in juegos.items():
        sede = sedes.get(jid)
        sedes_doc = []
        if sede:
            sedes_doc.append(
                {
                    "ciudad": sede["CIUDAD"],
                    "paisNoc": sede["PAIS_NOC"],
                    "paisHistorico": sede["PAIS_HISTORICO"],
                    "nota": sede["NOTA"],
                }
            )
        documentos.append(
            {
                "_id": f"juego:{jid}",
                "tipo": "juego",
                "id": jid,
                "anio": int(j["ANIO"]),
                "temporada": j["TEMPORADA"],
                "temporadaOriginal": j["TEMPORADA_ORIGINAL"],
                "categoria": j["CATEGORIA"],
                "sedes": sedes_doc,
                "nombreNormalizado": normalizar(f"{j['ANIO']} {j['TEMPORADA']}"),
            }
        )

    for d in deportes:
        documentos.append(
            {
                "_id": f"deporte:{d['id']}",
                "tipo": "deporte",
                "id": d["id"],
                "nombre": d["nombre"],
                "nombreNormalizado": normalizar(d["nombre"]),
            }
        )

    disciplinas_por_id = {d["id"]: d for d in disciplinas}
    for d in disciplinas:
        documentos.append(
            {
                "_id": f"disciplina:{d['id']}",
                "tipo": "disciplina",
                "id": d["id"],
                "nombre": d["nombre"],
                "nombreNormalizado": normalizar(d["nombre"]),
                "deporteId": d["deporteId"],
            }
        )

    for e in eventos:
        disciplina = disciplinas_por_id[e["disciplinaId"]]
        documentos.append(
            {
                "_id": f"evento:{e['id']}",
                "tipo": "evento",
                "id": e["id"],
                "nombre": e["nombre"],
                "nombreNormalizado": normalizar(e["nombre"]),
                "deporteId": disciplina["deporteId"],
                "disciplinaId": e["disciplinaId"],
            }
        )

    for m in medallas:
        documentos.append(
            {
                "_id": f"medalla:{m['id']}",
                "tipo": "medalla",
                "id": m["id"],
                "codigo": codigo_medalla(m["nombre"]),
                "nombre": m["nombre"],
                "nombreNormalizado": normalizar(m["nombre"]),
            }
        )

    if len(documentos) != 3583:
        raise SystemExit(f"Se esperaban 3,583 catálogos y se construyeron {len(documentos)}")
    conteos = Counter(d["tipo"] for d in documentos)
    for tipo, esperado in ESPERADO.items():
        if conteos[tipo] != esperado:
            raise SystemExit(f"{tipo}: {conteos[tipo]} != {esperado}")

    insertados = insertar_lotes(db.catalogos, documentos)
    evidencia(
        "fase2",
        "catalogos",
        {
            "generado_en": ahora(),
            "insertados": insertados,
            "conteos": dict(conteos),
            "muestra_juego": next(d for d in documentos if d["tipo"] == "juego"),
            "muestra_evento": next(d for d in documentos if d["tipo"] == "evento"),
        },
    )
    log(f"Catalogos insertados: {insertados:,} | {dict(conteos)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
