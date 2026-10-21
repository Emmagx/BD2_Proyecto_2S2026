#!/usr/bin/env python3
"""
Fase 1.1 - Generar dim_juegos y dim_sedes.

Entrada:
  datos/insumos/sedes_olimpiadas.csv
  OLIMPIADA (PostgreSQL o CSV)
Salida:
  datos/dim_juegos.csv   (62 filas, una por olimpiada)
  datos/dim_sedes.csv    (61 filas, una por juego con sede)
"""
from __future__ import annotations

import argparse
import sys

from common import (
    DATOS_DIR,
    EVIDENCIA_DIR,
    INSUMOS_DIR,
    ahora,
    cargar_olimpiada,
    cargar_pais,
    escribir_csv,
    escribir_json,
    leer_csv,
    log,
    sha256,
)

CATEGORIA_ESPECIAL = {
    10: "Intercalado",
    46: "Atipico",
    57: "Juvenil",
    58: "Juvenil",
    59: "Juvenil",
    60: "Juvenil",
    61: "Juvenil",
    62: "Juvenil",
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Genera dim_juegos y dim_sedes")
    ap.add_argument("--fuente", default="auto", choices=["auto", "pg", "csv"])
    args = ap.parse_args()

    log("Fase 1.1 - Generando dim_juegos y dim_sedes")
    olimpiadas = cargar_olimpiada(args.fuente)
    paises = cargar_pais(args.fuente)
    nocs = {p["NOC"] for p in paises}
    por_id = {o["ID"]: o for o in olimpiadas}

    if len(olimpiadas) != 62:
        raise SystemExit(f"Se esperaban 62 olimpiadas y hay {len(olimpiadas)}")

    sedes = leer_csv(INSUMOS_DIR / "sedes_olimpiadas.csv")
    sede_por_id = {int(s["ID_OLIMPIADA"]): s for s in sedes}
    if len(sede_por_id) != 61:
        raise SystemExit(f"Se esperaban 61 sedes y hay {len(sede_por_id)}")
    if 46 in sede_por_id:
        raise SystemExit("1888 no debe tener sede")
    if set(sede_por_id) != set(por_id) - {46}:
        raise SystemExit("Las sedes no cubren exactamente los 62 juegos menos 1888")

    filas_juegos, filas_sedes = [], []
    for oid in sorted(por_id):
        o = por_id[oid]
        s = sede_por_id.get(oid)
        categoria = CATEGORIA_ESPECIAL.get(oid, "Senior")
        if s:
            if s["CATEGORIA"] != categoria:
                raise SystemExit(
                    f"Categoría inconsistente para {oid}: insumo={s['CATEGORIA']} esperada={categoria}"
                )
            if int(s["ANIO"]) != o["YEAR"]:
                raise SystemExit(f"Año inconsistente para {oid}")
            if s["PAIS_NOC"] not in nocs:
                raise SystemExit(f"NOC inexistente: {s['PAIS_NOC']} (juego {oid})")
            filas_juegos.append(
                {
                    "ID_OLIMPIADA": oid,
                    "ANIO": o["YEAR"],
                    "TEMPORADA": s["TEMPORADA"],
                    "TEMPORADA_ORIGINAL": o["SEASON"],
                    "CATEGORIA": categoria,
                    "CIUDAD_SEDE": s["CIUDAD"],
                    "PAIS_NOC": s["PAIS_NOC"],
                    "PAIS_HISTORICO": s["PAIS_HISTORICO"],
                    "NOTA": s["NOTA"],
                }
            )
            filas_sedes.append(
                {
                    "ID_OLIMPIADA": oid,
                    "ANIO": o["YEAR"],
                    "TEMPORADA": s["TEMPORADA"],
                    "CATEGORIA": categoria,
                    "CIUDAD": s["CIUDAD"],
                    "PAIS_NOC": s["PAIS_NOC"],
                    "PAIS_HISTORICO": s["PAIS_HISTORICO"],
                    "NOTA": s["NOTA"],
                }
            )
        else:
            # Solo 1888: registro atípico, sin sede.
            filas_juegos.append(
                {
                    "ID_OLIMPIADA": oid,
                    "ANIO": o["YEAR"],
                    "TEMPORADA": o["SEASON"],
                    "TEMPORADA_ORIGINAL": o["SEASON"],
                    "CATEGORIA": categoria,
                    "CIUDAD_SEDE": "",
                    "PAIS_NOC": "",
                    "PAIS_HISTORICO": "",
                    "NOTA": "Registro atípico de 1888; no corresponde a Juegos Olímpicos oficiales y no tiene sede",
                }
            )

    escribir_csv(
        DATOS_DIR / "dim_juegos.csv",
        [
            "ID_OLIMPIADA",
            "ANIO",
            "TEMPORADA",
            "TEMPORADA_ORIGINAL",
            "CATEGORIA",
            "CIUDAD_SEDE",
            "PAIS_NOC",
            "PAIS_HISTORICO",
            "NOTA",
        ],
        filas_juegos,
    )
    escribir_csv(
        DATOS_DIR / "dim_sedes.csv",
        [
            "ID_OLIMPIADA",
            "ANIO",
            "TEMPORADA",
            "CATEGORIA",
            "CIUDAD",
            "PAIS_NOC",
            "PAIS_HISTORICO",
            "NOTA",
        ],
        filas_sedes,
    )

    categorias = {}
    for f in filas_juegos:
        categorias[f["CATEGORIA"]] = categorias.get(f["CATEGORIA"], 0) + 1

    reporte = {
        "generado_en": ahora(),
        "fuente": args.fuente,
        "juegos": len(filas_juegos),
        "sedes": len(filas_sedes),
        "sin_sede": [46],
        "categorias": categorias,
        "correcciones_temporada": [
            {"id": 10, "original": "Unknown", "nueva": "Summer", "motivo": "Juegos Intercalados"},
            {"id": 32, "original": "Unknown", "nueva": "Summer", "motivo": "Pruebas ecuestres de 1956"},
        ],
        "sha256": {
            "dim_juegos.csv": sha256(DATOS_DIR / "dim_juegos.csv"),
            "dim_sedes.csv": sha256(DATOS_DIR / "dim_sedes.csv"),
        },
    }
    escribir_json(EVIDENCIA_DIR / "reporte_dim_juegos.json", reporte)

    log(f"dim_juegos: {len(filas_juegos)} | dim_sedes: {len(filas_sedes)}")
    log(f"Categorías: {categorias}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
