#!/usr/bin/env python3
"""
Fase 1.2 - Generar dim_alias_paises.

Entrada:
  datos/insumos/alias_paises.csv
  PAIS (PostgreSQL o CSV)
Salida:
  datos/dim_alias_paises.csv
"""
from __future__ import annotations

import argparse
import sys

from common import (
    DATOS_DIR,
    EVIDENCIA_DIR,
    INSUMOS_DIR,
    ahora,
    cargar_pais,
    escribir_csv,
    escribir_json,
    leer_csv,
    log,
    normalizar,
    sha256,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Genera dim_alias_paises")
    ap.add_argument("--fuente", default="auto", choices=["auto", "pg", "csv"])
    args = ap.parse_args()

    log("Fase 1.2 - Generando dim_alias_paises")
    paises = cargar_pais(args.fuente)
    por_noc = {p["NOC"]: p for p in paises}
    insumos = leer_csv(INSUMOS_DIR / "alias_paises.csv")

    filas, omitidos, duplicados = [], [], []
    vistos = set()
    for r in insumos:
        noc = r["NOC"].strip()
        alias = r["ALIAS"].strip()
        if noc not in por_noc:
            omitidos.append({"NOC": noc, "ALIAS": alias, "motivo": "NOC no existe en PAIS"})
            continue
        clave = (noc, normalizar(alias))
        if clave in vistos:
            duplicados.append({"NOC": noc, "ALIAS": alias})
            continue
        vistos.add(clave)
        filas.append(
            {
                "NOC": noc,
                "NOMBRE_PAIS": por_noc[noc]["NOMBRE"],
                "ALIAS": alias,
                "ALIAS_NORMALIZADO": normalizar(alias),
            }
        )

    filas.sort(key=lambda x: (x["NOC"], x["ALIAS_NORMALIZADO"]))
    escribir_csv(
        DATOS_DIR / "dim_alias_paises.csv",
        ["NOC", "NOMBRE_PAIS", "ALIAS", "ALIAS_NORMALIZADO"],
        filas,
    )

    reporte = {
        "generado_en": ahora(),
        "fuente": args.fuente,
        "paises": len(paises),
        "alias_validos": len(filas),
        "alias_omitidos": omitidos,
        "alias_duplicados": duplicados,
        "sha256": {"dim_alias_paises.csv": sha256(DATOS_DIR / "dim_alias_paises.csv")},
    }
    escribir_json(EVIDENCIA_DIR / "reporte_alias.json", reporte)
    log(f"Alias válidos: {len(filas)} | omitidos: {len(omitidos)} | duplicados: {len(duplicados)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
