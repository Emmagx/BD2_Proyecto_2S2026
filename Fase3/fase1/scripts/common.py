#!/usr/bin/env python3
"""
Utilidades comunes de la Fase 1 de la Fase 3.

Contiene:
  * rutas del proyecto,
  * lectura de datos desde PostgreSQL (contenedor) o CSV de respaldo,
  * normalización de nombres con fallback al original,
  * escritura de CSV/JSON y checksums.

No depende de pandas ni de pymongo: solo biblioteca estándar.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------
# scripts/common.py -> fase1 -> Fase3 -> repositorio
SCRIPTS_DIR = Path(__file__).resolve().parent
FASE1_DIR = SCRIPTS_DIR.parent
FASE3_DIR = FASE1_DIR.parent
REPO_ROOT = FASE3_DIR.parent

DATOS_DIR = FASE1_DIR / "datos"
INSUMOS_DIR = DATOS_DIR / "insumos"
EVIDENCIA_DIR = FASE1_DIR / "evidencia"
CSV_DIR = REPO_ROOT / "Fase2" / "csv-limpios"

PG_CONTAINER = os.environ.get("PG_CONTAINER", "postgres_cali")
PG_USER = os.environ.get("PG_USER", "postgres")
PG_DB = os.environ.get("PG_DB", "olimpiadas_db")

# ---------------------------------------------------------------------------
# Fechas / log
# ---------------------------------------------------------------------------
def ahora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# CSV / JSON / checksums
# ---------------------------------------------------------------------------
def leer_csv(ruta: Path) -> list[dict]:
    ruta = Path(ruta)
    with ruta.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def escribir_csv(ruta: Path, campos: list[str], filas: list[dict]) -> None:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        for fila in filas:
            w.writerow(fila)
    log(f"CSV generado: {ruta} ({len(filas)} filas)")


def escribir_json(ruta: Path, datos) -> None:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2, default=str)
    log(f"JSON generado: {ruta}")


def sha256(ruta: Path, bloque: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with Path(ruta).open("rb") as f:
        while True:
            data = f.read(bloque)
            if not data:
                break
            h.update(data)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Fuente de datos: PostgreSQL (contenedor) o CSV
# ---------------------------------------------------------------------------
def _psql(sql: str) -> list[list[str]]:
    """Ejecuta SQL con psql dentro del contenedor y devuelve filas tabuladas."""
    cmd = [
        "docker",
        "exec",
        PG_CONTAINER,
        "psql",
        "-U",
        PG_USER,
        "-d",
        PG_DB,
        "-At",
        "-F",
        "\t",
        "-c",
        sql,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(
            f"psql falló (código {res.returncode}). stderr: {res.stderr.strip()}"
        )
    return [line.split("\t") for line in res.stdout.splitlines() if line]


def probar_pg() -> bool:
    try:
        _psql("SELECT 1;")
        return True
    except Exception:
        return False


def resolver_fuente(fuente: str) -> str:
    """Devuelve 'pg' o 'csv'. 'auto' intenta PostgreSQL y cae a CSV."""
    fuente = (fuente or "auto").lower()
    if fuente not in {"auto", "pg", "csv"}:
        raise ValueError("--fuente debe ser auto, pg o csv")
    if fuente == "csv":
        return "csv"
    if fuente == "pg":
        if not probar_pg():
            raise RuntimeError(
                "No se pudo conectar a PostgreSQL con docker exec. "
                "¿Está corriendo el contenedor? Use --fuente csv para el respaldo."
            )
        return "pg"
    if probar_pg():
        log("Fuente de datos: PostgreSQL (contenedor)")
        return "pg"
    log("PostgreSQL no disponible; se usará el respaldo CSV de Fase 2")
    return "csv"


def cargar_olimpiada(fuente: str) -> list[dict]:
    origen = resolver_fuente(fuente)
    if origen == "pg":
        filas = _psql('SELECT "ID","YEAR","SEASON" FROM "OLIMPIADA" ORDER BY "ID";')
        return [
            {"ID": int(f[0]), "YEAR": int(f[1]), "SEASON": f[2]}
            for f in filas
        ]
    filas = leer_csv(CSV_DIR / "3_OLIMPIADA.csv")
    return [
        {"ID": int(f["ID"]), "YEAR": int(f["YEAR"]), "SEASON": f["SEASON"]}
        for f in filas
    ]


def cargar_pais(fuente: str) -> list[dict]:
    origen = resolver_fuente(fuente)
    if origen == "pg":
        filas = _psql('SELECT "ID","NOMBRE","NOC" FROM "PAIS" ORDER BY "ID";')
        return [
            {"ID": int(f[0]), "NOMBRE": f[1], "NOC": f[2]}
            for f in filas
        ]
    filas = leer_csv(CSV_DIR / "1_PAIS.csv")
    return [
        {"ID": int(f["ID"]), "NOMBRE": f["NOMBRE"], "NOC": f["NOC"]}
        for f in filas
    ]


def iterar_atletas(fuente: str):
    """Genera (ID, NOMBRE) de ATLETA sin cargar los 145,500 en memoria."""
    origen = resolver_fuente(fuente)
    if origen == "pg":
        cmd = [
            "docker",
            "exec",
            PG_CONTAINER,
            "psql",
            "-U",
            PG_USER,
            "-d",
            PG_DB,
            "-At",
            "-F",
            "\t",
            "-c",
            'SELECT "ID","NOMBRE" FROM "ATLETA" ORDER BY "ID";',
        ]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, text=True)
        assert proc.stdout is not None
        for linea in proc.stdout:
            linea = linea.rstrip("\n")
            if not linea:
                continue
            partes = linea.split("\t", 1)
            if len(partes) != 2:
                continue
            yield int(partes[0]), partes[1]
        codigo = proc.wait()
        if codigo != 0:
            raise RuntimeError(f"psql terminó con código {codigo} al leer ATLETA")
        return
    with (CSV_DIR / "10_ATLETA.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as f:
        for fila in csv.DictReader(f):
            yield int(fila["ID"]), fila["NOMBRE"]


# ---------------------------------------------------------------------------
# Normalización de nombres
# ---------------------------------------------------------------------------
_TRANSLIT = str.maketrans(
    {
        "ø": "o",
        "æ": "ae",
        "œ": "oe",
        "ß": "ss",
        "ł": "l",
        "đ": "d",
        "ð": "d",
        "þ": "th",
        "ı": "i",
        "ħ": "h",
        "ŋ": "n",
        "ĳ": "ij",
    }
)


def normalizar(texto: object) -> str:
    """Minúsculas, sin acentos, sin puntuación y con espacios colapsados."""
    if texto is None:
        return ""
    s = str(texto).strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().translate(_TRANSLIT)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def normalizar_con_fallback(original: object) -> dict:
    """
    Normaliza sin perder el original.

    Si después de transliterar quedan letras no ASCII (chino, cirílico, etc.)
    o el resultado sería vacío, se devuelve el nombre original como
    'normalizado' y ok=False. El campo 'original' nunca se modifica.
    """
    original = "" if original is None else str(original).strip()
    if not original:
        return {"original": original, "normalizado": original, "ok": False}

    base = unicodedata.normalize("NFKD", original)
    base = "".join(c for c in base if not unicodedata.combining(c))
    base = base.lower().translate(_TRANSLIT)

    # Letras que no son ASCII y que no se pudieron transliterar.
    residuales = [c for c in base if ord(c) > 127 and c.isalpha()]
    normalizado = normalizar(original)

    if residuales or not normalizado:
        return {
            "original": original,
            "normalizado": original,
            "ok": False,
            "motivo": "letras no normalizables" if residuales else "resultado vacío",
        }

    return {"original": original, "normalizado": normalizado, "ok": True}
