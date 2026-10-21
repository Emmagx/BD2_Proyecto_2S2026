#!/usr/bin/env python3
"""
Fase 1.3 - Normalización de nombres.

No modifica los nombres originales: agrega una versión normalizada para
búsquedas. Si un nombre no se puede normalizar (por ejemplo, escritura no
latina), se conserva el original y se marca NORMALIZADO = NO.

Salidas:
  datos/dim_paises_normalizados.csv
  evidencia/reporte_normalizacion.json
  evidencia/muestra_normalizacion.csv
"""
from __future__ import annotations

import argparse
import sys

from common import (
    DATOS_DIR,
    EVIDENCIA_DIR,
    ahora,
    cargar_pais,
    escribir_csv,
    escribir_json,
    iterar_atletas,
    log,
    normalizar_con_fallback,
    sha256,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Genera nombres normalizados")
    ap.add_argument("--fuente", default="auto", choices=["auto", "pg", "csv"])
    ap.add_argument("--limite", type=int, default=0, help="0 = todos los atletas")
    args = ap.parse_args()

    log("Fase 1.3 - Normalizando nombres")
    paises = cargar_pais(args.fuente)

    filas_paises = []
    for p in sorted(paises, key=lambda x: x["ID"]):
        n = normalizar_con_fallback(p["NOMBRE"])
        filas_paises.append(
            {
                "ID": p["ID"],
                "NOMBRE_ORIGINAL": n["original"],
                "NOMBRE_NORMALIZADO": n["normalizado"],
                "NORMALIZADO": "SI" if n["ok"] else "NO",
                "CAMBIO": "SI" if n["normalizado"] != n["original"] else "NO",
            }
        )
    escribir_csv(
        DATOS_DIR / "dim_paises_normalizados.csv",
        ["ID", "NOMBRE_ORIGINAL", "NOMBRE_NORMALIZADO", "NORMALIZADO", "CAMBIO"],
        filas_paises,
    )

    total = ok = fallback = cambiados = 0
    ejemplos_fallback, ejemplos_cambio = [], []
    muestra = []

    for aid, nombre in iterar_atletas(args.fuente):
        total += 1
        n = normalizar_con_fallback(nombre)
        if n["ok"]:
            ok += 1
        else:
            fallback += 1
            if len(ejemplos_fallback) < 20:
                ejemplos_fallback.append(
                    {"ID": aid, "ORIGINAL": n["original"], "NORMALIZADO": n["normalizado"], "motivo": n.get("motivo")}
                )
        if n["normalizado"] != n["original"]:
            cambiados += 1
            if len(ejemplos_cambio) < 20:
                ejemplos_cambio.append(
                    {"ID": aid, "ORIGINAL": n["original"], "NORMALIZADO": n["normalizado"]}
                )
        if len(muestra) < 100 and (not n["ok"] or n["normalizado"] != n["original"]):
            muestra.append(
                {
                    "ID": aid,
                    "NOMBRE_ORIGINAL": n["original"],
                    "NOMBRE_NORMALIZADO": n["normalizado"],
                    "NORMALIZADO": "SI" if n["ok"] else "NO",
                    "CAMBIO": "SI" if n["normalizado"] != n["original"] else "NO",
                }
            )
        if args.limite and total >= args.limite:
            break

    escribir_csv(
        EVIDENCIA_DIR / "muestra_normalizacion.csv",
        ["ID", "NOMBRE_ORIGINAL", "NOMBRE_NORMALIZADO", "NORMALIZADO", "CAMBIO"],
        muestra,
    )

    reporte = {
        "generado_en": ahora(),
        "fuente": args.fuente,
        "atletas_procesados": total,
        "normalizados_ok": ok,
        "fallback_original": fallback,
        "cambiados": cambiados,
        "limite": args.limite,
        "ejemplos_fallback": ejemplos_fallback,
        "ejemplos_cambio": ejemplos_cambio,
        "paises": {
            "total": len(filas_paises),
            "normalizados_ok": sum(1 for f in filas_paises if f["NORMALIZADO"] == "SI"),
            "fallback": sum(1 for f in filas_paises if f["NORMALIZADO"] == "NO"),
        },
        "sha256": {
            "dim_paises_normalizados.csv": sha256(DATOS_DIR / "dim_paises_normalizados.csv"),
            "muestra_normalizacion.csv": sha256(EVIDENCIA_DIR / "muestra_normalizacion.csv"),
        },
    }
    escribir_json(EVIDENCIA_DIR / "reporte_normalizacion.json", reporte)
    log(
        f"Atletas: {total:,} | normalizados: {ok:,} | fallback: {fallback:,} | "
        f"cambiados: {cambiados:,}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
