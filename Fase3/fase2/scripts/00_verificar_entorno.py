#!/usr/bin/env python3
"""
Fase 2.0 - Verificación de entorno para las fases 2-5.

Comprueba Python, pymongo, PostgreSQL completo, MongoDB y los insumos de la
Fase 1. No modifica datos.
"""
from __future__ import annotations

import argparse
import platform
import sys
from pathlib import Path

FASE3_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FASE3_DIR))

from lib.common import (  # noqa: E402
    DATOS_FASE1,
    MONGO_DB,
    MONGO_URI,
    ahora,
    comprobar_pg,
    conectar_mongo,
    escribir_json,
    evidencia,
    log,
    psql_json,
    sha256,
)

REQUERIDOS = [
    "dim_juegos.csv",
    "dim_sedes.csv",
    "dim_alias_paises.csv",
    "dim_paises_normalizados.csv",
]


def main() -> int:
    ap = argparse.ArgumentParser(description="Verifica entorno Fase 3 (fases 2-5)")
    ap.add_argument("--solo-chequear", action="store_true", help="no escribe evidencia")
    args = ap.parse_args()

    log("Fase 2.0 - Verificando entorno")
    fallos, avisos = [], []

    if sys.version_info < (3, 10):
        fallos.append(f"Python {sys.version_info.major}.{sys.version_info.minor} < 3.10")
    try:
        import pymongo

        log(f"pymongo {pymongo.version} disponible")
    except ImportError:
        fallos.append("Falta pymongo; instale requirements.txt")

    if not comprobar_pg():
        fallos.append(
            "No se pudo consultar PostgreSQL con docker exec. "
            "Verifique el contenedor postgres_cali."
        )
    else:
        try:
            filas = psql_json(
                'SELECT json_build_object('
                "'atletas',(SELECT count(*) FROM \"ATLETA\"),"
                "'resultados',(SELECT count(*) FROM \"RESULTADO\"),"
                "'participaciones',(SELECT count(*) FROM \"RESULTADO_ATLETA\"));"
            )
            log(f"PostgreSQL: {filas[0]}")
            if filas[0]["resultados"] != 156_032 or filas[0]["participaciones"] != 308_238:
                fallos.append(
                    "PostgreSQL no tiene los hechos completos: "
                    f"{filas[0]}"
                )
        except Exception as exc:
            fallos.append(f"Error consultando PostgreSQL: {exc}")

    faltan = [f for f in REQUERIDOS if not (DATOS_FASE1 / f).exists()]
    if faltan:
        fallos.append(f"Faltan insumos de Fase 1: {faltan}")
    else:
        log("Insumos de Fase 1 presentes")

    try:
        _, db = conectar_mongo()
        db.command("ping")
        log(f"MongoDB disponible: {MONGO_URI} / {MONGO_DB}")
        log(f"Colecciones actuales: {sorted(db.list_collection_names())}")
    except SystemExit as exc:
        fallos.append(str(exc))

    if not args.solo_chequear:
        datos = {
            "generado_en": ahora(),
            "python": platform.python_version(),
            "host": platform.node(),
            "mongo_uri": MONGO_URI,
            "mongo_db": MONGO_DB,
            "fallos": fallos,
            "avisos": avisos,
            "insumos": {
                f: sha256(DATOS_FASE1 / f)
                for f in REQUERIDOS
                if (DATOS_FASE1 / f).exists()
            },
            "ok": not fallos,
        }
        evidencia("fase2", "verificacion_entorno", datos)

    print()
    print(f"Fallos: {len(fallos)}")
    for f in fallos:
        print(f"  [FALLO] {f}")
    for a in avisos:
        print(f"  [AVISO] {a}")
    return 1 if fallos else 0


if __name__ == "__main__":
    sys.exit(main())
