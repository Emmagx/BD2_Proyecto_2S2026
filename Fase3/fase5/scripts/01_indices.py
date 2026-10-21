#!/usr/bin/env python3
"""
Fase 5.1 - Crear índices de las 4 colecciones.

Se ejecuta DESPUÉS de las cargas para no penalizar la inserción.

Uso:
  python3 fase5/scripts/01_indices.py
"""
from __future__ import annotations

import sys
from pathlib import Path

FASE3_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(FASE3_DIR))

from lib.common import ahora, conectar_mongo, evidencia, log  # noqa: E402

INDICES = [
    ("atletas", [("nombreNormalizado", 1)], {"name": "ix_atletas_nombre_norm"}),
    ("atletas", [("lugarNacimiento.paisNoc", 1)], {"name": "ix_atletas_pais_nac"}),
    (
        "resultados",
        [("atletas.id", 1), ("edicion.anio", -1)],
        {"name": "ix_resultados_atleta_anio"},
    ),
    (
        "resultados",
        [("atletas.noc", 1), ("edicion.anio", -1), ("medalla.codigo", 1)],
        {"name": "ix_resultados_pais_anio_medalla"},
    ),
    (
        "resultados",
        [("edicion.anio", 1), ("medalla.codigo", 1)],
        {"name": "ix_resultados_anio_medalla"},
    ),
    (
        "resultados",
        [("evento.id", 1), ("edicion.anio", 1)],
        {"name": "ix_resultados_evento_anio"},
    ),
    (
        "resultados",
        [("deporte.id", 1), ("edicion.anio", 1)],
        {"name": "ix_resultados_deporte_anio"},
    ),
    (
        "resultados",
        [("multipais", 1), ("revisar", 1)],
        {"name": "ix_resultados_multipais_revisar"},
    ),
    ("paises", [("noc", 1)], {"name": "ix_paises_noc", "unique": True}),
    ("paises", [("nombreNormalizado", 1)], {"name": "ix_paises_nombre_norm"}),
    ("paises", [("aliasNormalizado", 1)], {"name": "ix_paises_alias"}),
    ("paises", [("sedes.anio", 1)], {"name": "ix_paises_sedes_anio"}),
    (
        "catalogos",
        [("tipo", 1), ("nombreNormalizado", 1)],
        {"name": "ix_catalogos_tipo_nombre"},
    ),
    ("catalogos", [("tipo", 1), ("anio", 1)], {"name": "ix_catalogos_tipo_anio"}),
]


def main() -> int:
    log("Fase 5.1 - Creando índices")
    _, db = conectar_mongo()
    creados = []
    for coleccion, claves, opciones in INDICES:
        nombre = opciones.get("name")
        opts = {k: v for k, v in opciones.items() if k != "name"}
        db[coleccion].create_index(claves, name=nombre, **opts)
        creados.append(
            {
                "coleccion": coleccion,
                "nombre": nombre,
                "claves": {k: v for k, v in claves},
                "opciones": opts,
            }
        )
        log(f"  {coleccion}: {nombre}")

    evidencia("fase5", "indices", {"generado_en": ahora(), "indices": creados})
    log(f"Índices creados: {len(creados)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
