#!/usr/bin/env python3
"""
Fase 1.0 - Generar los insumos curados de la migración.

Produce:
  datos/insumos/sedes_olimpiadas.csv   (61 juegos con sede verificada)
  datos/insumos/alias_paises.csv       (alias en español para búsquedas)

Los datos se validan contra OLIMPIADA y PAIS. Si un juego no tiene fila
(1888), se reporta como "sin sede". Si un NOC de alias no existe, se omite
y se deja constancia en el reporte.
"""
from __future__ import annotations

import argparse
import sys

from common import (
    EVIDENCIA_DIR,
    INSUMOS_DIR,
    ahora,
    cargar_olimpiada,
    cargar_pais,
    escribir_csv,
    escribir_json,
    log,
    normalizar,
    sha256,
)

# ---------------------------------------------------------------------------
# Sedes verificadas. (ID, anio, temporada, categoria, ciudad, noc, historico, nota)
# El juego 46 (1888) no tiene Juegos oficiales ni sede; no se incluye.
# ---------------------------------------------------------------------------
SEDES = [
    (12, 1896, "Summer", "Senior", "Atenas", "GRE", "Grecia", "Primeros Juegos Olímpicos modernos"),
    (9, 1900, "Summer", "Senior", "París", "FRA", "Francia", "Sede única"),
    (15, 1904, "Summer", "Senior", "San Luis", "USA", "Estados Unidos", "Sede única"),
    (10, 1906, "Summer", "Intercalado", "Atenas", "GRE", "Grecia", "Juegos Intercalados de 1906; el dataset los marca como temporada Unknown"),
    (11, 1908, "Summer", "Senior", "Londres", "GBR", "Gran Bretaña", "Sede única"),
    (1, 1912, "Summer", "Senior", "Estocolmo", "SWE", "Suecia", "Sede única"),
    (2, 1920, "Summer", "Senior", "Amberes", "BEL", "Bélgica", "Sede única"),
    (4, 1924, "Summer", "Senior", "París", "FRA", "Francia", "Sede única"),
    (34, 1924, "Winter", "Senior", "Chamonix", "FRA", "Francia", "Primeros Juegos Olímpicos de Invierno"),
    (21, 1928, "Summer", "Senior", "Ámsterdam", "NED", "Países Bajos", "Sede única"),
    (35, 1928, "Winter", "Senior", "Sankt Moritz", "SUI", "Suiza", "Sede única"),
    (29, 1932, "Summer", "Senior", "Los Ángeles", "USA", "Estados Unidos", "Sede única"),
    (31, 1932, "Winter", "Senior", "Lake Placid", "USA", "Estados Unidos", "Sede única"),
    (30, 1936, "Summer", "Senior", "Berlín", "GER", "Alemania", "Sede única"),
    (41, 1936, "Winter", "Senior", "Garmisch-Partenkirchen", "GER", "Alemania", "Sede única"),
    (28, 1948, "Summer", "Senior", "Londres", "GBR", "Gran Bretaña", "Sede única"),
    (33, 1948, "Winter", "Senior", "Sankt Moritz", "SUI", "Suiza", "Sede única"),
    (25, 1952, "Summer", "Senior", "Helsinki", "FIN", "Finlandia", "Sede única"),
    (40, 1952, "Winter", "Senior", "Oslo", "NOR", "Noruega", "Sede única"),
    (24, 1956, "Summer", "Senior", "Melbourne", "AUS", "Australia", "Sede principal; las pruebas ecuestres se celebraron en Estocolmo (ver registro 32)"),
    (32, 1956, "Summer", "Senior", "Estocolmo", "SWE", "Suecia", "Pruebas ecuestres de Melbourne 1956; el dataset las registra como temporada Unknown"),
    (45, 1956, "Winter", "Senior", "Cortina d'Ampezzo", "ITA", "Italia", "Sede única"),
    (26, 1960, "Summer", "Senior", "Roma", "ITA", "Italia", "Sede única"),
    (53, 1960, "Winter", "Senior", "Squaw Valley", "USA", "Estados Unidos", "Sede única"),
    (27, 1964, "Summer", "Senior", "Tokio", "JPN", "Japón", "Sede única"),
    (39, 1964, "Winter", "Senior", "Innsbruck", "AUT", "Austria", "Sede única"),
    (23, 1968, "Summer", "Senior", "Ciudad de México", "MEX", "México", "Sede única"),
    (52, 1968, "Winter", "Senior", "Grenoble", "FRA", "Francia", "Sede única"),
    (19, 1972, "Summer", "Senior", "Múnich", "GER", "Alemania", "En 1972 correspondía a Alemania Occidental (RFA)"),
    (49, 1972, "Winter", "Senior", "Sapporo", "JPN", "Japón", "Sede única"),
    (18, 1976, "Summer", "Senior", "Montreal", "CAN", "Canadá", "Sede única"),
    (48, 1976, "Winter", "Senior", "Innsbruck", "AUT", "Austria", "Sede única"),
    (20, 1980, "Summer", "Senior", "Moscú", "RUS", "Rusia", "En 1980 correspondía a la Unión Soviética (URSS)"),
    (51, 1980, "Winter", "Senior", "Lake Placid", "USA", "Estados Unidos", "Sede única"),
    (13, 1984, "Summer", "Senior", "Los Ángeles", "USA", "Estados Unidos", "Sede única"),
    (50, 1984, "Winter", "Senior", "Sarajevo", "BIH", "Bosnia y Herzegovina", "En 1984 correspondía a Yugoslavia"),
    (14, 1988, "Summer", "Senior", "Seúl", "KOR", "República de Corea", "Sede única"),
    (47, 1988, "Winter", "Senior", "Calgary", "CAN", "Canadá", "Sede única"),
    (5, 1992, "Summer", "Senior", "Barcelona", "ESP", "España", "Sede única"),
    (42, 1992, "Winter", "Senior", "Albertville", "FRA", "Francia", "Sede única"),
    (43, 1994, "Winter", "Senior", "Lillehammer", "NOR", "Noruega", "Sede única"),
    (3, 1996, "Summer", "Senior", "Atlanta", "USA", "Estados Unidos", "Sede única"),
    (44, 1998, "Winter", "Senior", "Nagano", "JPN", "Japón", "Sede única"),
    (6, 2000, "Summer", "Senior", "Sídney", "AUS", "Australia", "Sede única"),
    (36, 2002, "Winter", "Senior", "Salt Lake City", "USA", "Estados Unidos", "Sede única"),
    (7, 2004, "Summer", "Senior", "Atenas", "GRE", "Grecia", "Sede única"),
    (37, 2006, "Winter", "Senior", "Turín", "ITA", "Italia", "Sede única"),
    (8, 2008, "Summer", "Senior", "Pekín", "CHN", "República Popular China", "Sede única"),
    (57, 2010, "Summer", "Juvenil", "Singapur", "SGP", "Singapur", "Juegos Olímpicos de la Juventud de Verano 2010"),
    (38, 2010, "Winter", "Senior", "Vancouver", "CAN", "Canadá", "Sede única"),
    (16, 2012, "Summer", "Senior", "Londres", "GBR", "Gran Bretaña", "Sede única"),
    (59, 2012, "Winter", "Juvenil", "Innsbruck", "AUT", "Austria", "Juegos Olímpicos de la Juventud de Invierno 2012"),
    (58, 2014, "Summer", "Juvenil", "Nankín", "CHN", "República Popular China", "Juegos Olímpicos de la Juventud de Verano 2014"),
    (54, 2014, "Winter", "Senior", "Sochi", "RUS", "Rusia", "Sede única"),
    (17, 2016, "Summer", "Senior", "Río de Janeiro", "BRA", "Brasil", "Sede única"),
    (60, 2016, "Winter", "Juvenil", "Lillehammer", "NOR", "Noruega", "Juegos Olímpicos de la Juventud de Invierno 2016"),
    (61, 2018, "Summer", "Juvenil", "Buenos Aires", "ARG", "Argentina", "Juegos Olímpicos de la Juventud de Verano 2018"),
    (55, 2018, "Winter", "Senior", "Pyeongchang", "KOR", "República de Corea", "Sede única"),
    (22, 2020, "Summer", "Senior", "Tokio", "JPN", "Japón", "Celebrados en 2021 por la pandemia de COVID-19"),
    (62, 2020, "Winter", "Juvenil", "Lausana", "SUI", "Suiza", "Juegos Olímpicos de la Juventud de Invierno 2020"),
    (56, 2022, "Winter", "Senior", "Pekín", "CHN", "República Popular China", "Sede única"),
]

# ---------------------------------------------------------------------------
# Alias en español y variantes. Si un NOC no existe en PAIS, se omite.
# ---------------------------------------------------------------------------
ALIAS = [
    ("ARG", "Argentina"), ("AUS", "Australia"), ("AUT", "Austria"),
    ("BEL", "Bélgica"), ("BEL", "Belgica"), ("BIH", "Bosnia y Herzegovina"),
    ("BIH", "Bosnia"), ("BRA", "Brasil"), ("CAN", "Canadá"), ("CAN", "Canada"),
    ("CHN", "China"), ("CHN", "República Popular China"), ("ESP", "España"),
    ("ESP", "Espana"), ("FIN", "Finlandia"), ("FRA", "Francia"),
    ("GBR", "Reino Unido"), ("GBR", "Gran Bretaña"), ("GBR", "Gran Bretana"),
    ("GBR", "UK"), ("GER", "Alemania"), ("GRE", "Grecia"), ("ITA", "Italia"),
    ("JPN", "Japón"), ("JPN", "Japon"), ("KOR", "Corea del Sur"),
    ("KOR", "Corea"), ("MEX", "México"), ("MEX", "Mexico"), ("NED", "Países Bajos"),
    ("NED", "Paises Bajos"), ("NED", "Holanda"), ("NOR", "Noruega"),
    ("RUS", "Rusia"), ("SGP", "Singapur"), ("SUI", "Suiza"), ("SWE", "Suecia"),
    ("USA", "Estados Unidos"), ("USA", "EE.UU."), ("USA", "EEUU"), ("USA", "USA"),
    ("URS", "Unión Soviética"), ("URS", "Union Sovietica"), ("URS", "URSS"),
    ("YUG", "Yugoslavia"), ("FRG", "Alemania Occidental"), ("FRG", "RFA"),
    ("GDR", "Alemania Oriental"), ("GDR", "RDA"), ("TCH", "Checoslovaquia"),
    ("COL", "Colombia"), ("VEN", "Venezuela"), ("ECU", "Ecuador"),
    ("PER", "Perú"), ("PER", "Peru"), ("BOL", "Bolivia"), ("CHI", "Chile"),
    ("URU", "Uruguay"), ("PAR", "Paraguay"), ("CRC", "Costa Rica"),
    ("PAN", "Panamá"), ("PAN", "Panama"), ("CUB", "Cuba"),
    ("DOM", "República Dominicana"), ("DOM", "Republica Dominicana"),
    ("PUR", "Puerto Rico"), ("JAM", "Jamaica"), ("HAI", "Haití"),
    ("HAI", "Haiti"), ("HON", "Honduras"), ("ESA", "El Salvador"),
    ("NCA", "Nicaragua"), ("BAR", "Barbados"), ("BAH", "Bahamas"),
    ("ISL", "Islandia"), ("IRL", "Irlanda"), ("POR", "Portugal"),
    ("POL", "Polonia"), ("ROU", "Rumania"), ("BUL", "Bulgaria"),
    ("HUN", "Hungría"), ("HUN", "Hungria"), ("CZE", "República Checa"),
    ("CZE", "Republica Checa"), ("SVK", "Eslovaquia"), ("SLO", "Eslovenia"),
    ("CRO", "Croacia"), ("SRB", "Serbia"), ("MKD", "Macedonia del Norte"),
    ("ALB", "Albania"), ("UKR", "Ucrania"), ("BLR", "Bielorrusia"),
    ("GEO", "Georgia"), ("ARM", "Armenia"), ("AZE", "Azerbaiyán"),
    ("AZE", "Azerbaiyan"), ("KAZ", "Kazajistán"), ("KAZ", "Kazajistan"),
    ("UZB", "Uzbekistán"), ("IND", "India"), ("PAK", "Pakistán"),
    ("PAK", "Pakistan"), ("BAN", "Bangladesh"), ("SRI", "Sri Lanka"),
    ("THA", "Tailandia"), ("VIE", "Vietnam"), ("PHI", "Filipinas"),
    ("INA", "Indonesia"), ("MAS", "Malasia"), ("KSA", "Arabia Saudita"),
    ("IRI", "Irán"), ("IRI", "Iran"), ("IRQ", "Irak"), ("ISR", "Israel"),
    ("TUR", "Turquía"), ("TUR", "Turquia"), ("EGY", "Egipto"),
    ("RSA", "Sudáfrica"), ("RSA", "Sudafrica"), ("NGR", "Nigeria"),
    ("KEN", "Kenia"), ("ETH", "Etiopía"), ("ETH", "Etiopia"),
    ("MAR", "Marruecos"), ("ALG", "Argelia"), ("TUN", "Túnez"),
    ("TUN", "Tunez"), ("NZL", "Nueva Zelanda"), ("FIJ", "Fiyi"),
    ("SAM", "Samoa"), ("TGA", "Tonga"),
]


def main() -> int:
    ap = argparse.ArgumentParser(description="Genera insumos curados de Fase 1")
    ap.add_argument("--fuente", default="auto", choices=["auto", "pg", "csv"])
    args = ap.parse_args()

    log("Fase 1.0 - Generando insumos curados")
    olimpiadas = cargar_olimpiada(args.fuente)
    paises = cargar_pais(args.fuente)
    por_id = {o["ID"]: o for o in olimpiadas}
    nocs = {p["NOC"] for p in paises}

    # Validaciones de sedes
    if len(olimpiadas) != 62:
        raise SystemExit(f"Se esperaban 62 olimpiadas y hay {len(olimpiadas)}")
    ids_sedes = [s[0] for s in SEDES]
    if len(ids_sedes) != len(set(ids_sedes)):
        raise SystemExit("Hay ID_OLIMPIADA repetidos en las sedes")
    esperados = set(por_id) - {46}
    if set(ids_sedes) != esperados:
        faltan = esperados - set(ids_sedes)
        sobran = set(ids_sedes) - esperados
        raise SystemExit(f"Sedes incompletas. Faltan: {faltan}. Sobran: {sobran}")
    if 46 in ids_sedes:
        raise SystemExit("1888 no debe tener sede")

    for sid, anio, temporada, categoria, ciudad, noc, historico, nota in SEDES:
        real = por_id[sid]
        if real["YEAR"] != anio:
            raise SystemExit(f"Año inconsistente para olimpiada {sid}")
        if noc not in nocs:
            raise SystemExit(f"NOC inexistente en PAIS: {noc} (olimpiada {sid})")
        if categoria not in {"Senior", "Juvenil", "Intercalado", "Atipico"}:
            raise SystemExit(f"Categoría inválida: {categoria}")

    filas_sedes = [
        {
            "ID_OLIMPIADA": sid,
            "ANIO": anio,
            "TEMPORADA": temporada,
            "CATEGORIA": categoria,
            "CIUDAD": ciudad,
            "PAIS_NOC": noc,
            "PAIS_HISTORICO": historico,
            "NOTA": nota,
        }
        for sid, anio, temporada, categoria, ciudad, noc, historico, nota in SEDES
    ]
    escribir_csv(
        INSUMOS_DIR / "sedes_olimpiadas.csv",
        ["ID_OLIMPIADA", "ANIO", "TEMPORADA", "CATEGORIA", "CIUDAD", "PAIS_NOC", "PAIS_HISTORICO", "NOTA"],
        filas_sedes,
    )

    # Validaciones de alias (se deduplica por NOC + alias normalizado)
    alias_ok, alias_omitidos, alias_duplicados = [], [], []
    vistos = set()
    for noc, alias in ALIAS:
        if noc not in nocs:
            alias_omitidos.append({"NOC": noc, "ALIAS": alias, "motivo": "NOC no existe en PAIS"})
            continue
        clave = (noc, normalizar(alias))
        if clave in vistos:
            alias_duplicados.append({"NOC": noc, "ALIAS": alias})
            continue
        vistos.add(clave)
        alias_ok.append({"NOC": noc, "ALIAS": alias})
    alias_final = alias_ok
    escribir_csv(
        INSUMOS_DIR / "alias_paises.csv",
        ["NOC", "ALIAS"],
        alias_final,
    )

    categorias = {}
    for s in SEDES:
        categorias[s[3]] = categorias.get(s[3], 0) + 1
    # 1888 no tiene fila de sede, pero sí categoría.
    categorias["Atipico"] = 1

    reporte = {
        "generado_en": ahora(),
        "fuente": args.fuente,
        "juegos": len(olimpiadas),
        "juegos_con_sede": len(SEDES),
        "juegos_sin_sede": [46],
        "categorias": categorias,
        "alias_validos": len(alias_final),
        "alias_omitidos": alias_omitidos,
        "alias_duplicados": alias_duplicados,
        "sha256": {
            "sedes_olimpiadas.csv": sha256(INSUMOS_DIR / "sedes_olimpiadas.csv"),
            "alias_paises.csv": sha256(INSUMOS_DIR / "alias_paises.csv"),
        },
    }
    escribir_json(EVIDENCIA_DIR / "reporte_insumos.json", reporte)

    log(f"Juegos: {len(olimpiadas)} | con sede: {len(SEDES)} | sin sede: 1888")
    log(f"Categorías: {categorias}")
    log(f"Alias válidos: {len(alias_final)} | omitidos: {len(alias_omitidos)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
