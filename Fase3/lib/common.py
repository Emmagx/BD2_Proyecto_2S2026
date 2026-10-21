#!/usr/bin/env python3
"""
Utilidades compartidas por las fases 2 a 5 de la Fase 3.

- Rutas del proyecto.
- Lectura de PostgreSQL dentro del contenedor (psql) como JSON.
- Conexión a MongoDB con pymongo.
- Normalización de nombres con fallback al original.
- Evidencia JSON/Markdown y logs.
"""
from __future__ import annotations

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
LIB_DIR = Path(__file__).resolve().parent
FASE3_DIR = LIB_DIR.parent
REPO_ROOT = FASE3_DIR.parent
FASE1_DIR = FASE3_DIR / "fase1"
CSV_DIR = REPO_ROOT / "Fase2" / "csv-limpios"
EVIDENCIA_DIR = FASE3_DIR / "evidencia"
DATOS_FASE1 = FASE1_DIR / "datos"

PG_CONTAINER = os.environ.get("PG_CONTAINER", "postgres_cali")
PG_USER = os.environ.get("PG_USER", "postgres")
PG_DB = os.environ.get("PG_DB", "olimpiadas_db")
MONGO_URI = os.environ.get(
    "MONGO_URI", "mongodb://127.0.0.1:27017/?directConnection=true"
)
MONGO_DB = os.environ.get("MONGO_DB", "olimpiadas_mongo")

COLECCIONES = ["atletas", "resultados", "paises", "catalogos"]


# ---------------------------------------------------------------------------
# Log / tiempo
# ---------------------------------------------------------------------------
def ahora() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)


# ---------------------------------------------------------------------------
# CSV / JSON / checksums
# ---------------------------------------------------------------------------
def leer_csv(ruta: Path) -> list[dict]:
    import csv

    with Path(ruta).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def escribir_json(ruta: Path, datos) -> None:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2, default=str)


def sha256(ruta: Path, bloque: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with Path(ruta).open("rb") as f:
        while True:
            data = f.read(bloque)
            if not data:
                break
            h.update(data)
    return h.hexdigest()


def evidencia(fase: str, nombre: str, datos) -> Path:
    """Guarda evidencia en evidencia/<fase>/<nombre>.json."""
    ruta = EVIDENCIA_DIR / fase / f"{nombre}.json"
    escribir_json(ruta, datos)
    return ruta


# ---------------------------------------------------------------------------
# PostgreSQL en contenedor
# ---------------------------------------------------------------------------
def _cmd_psql(sql: str) -> list[str]:
    return [
        "docker",
        "exec",
        PG_CONTAINER,
        "psql",
        "-U",
        PG_USER,
        "-d",
        PG_DB,
        "-At",
        "-c",
        sql,
    ]


def comprobar_pg() -> bool:
    try:
        res = subprocess.run(
            _cmd_psql("SELECT 1;"), capture_output=True, text=True, timeout=20
        )
        return res.returncode == 0
    except Exception:
        return False


def psql_stream(sql: str):
    """Genera diccionarios desde una consulta que devuelve un JSON por fila."""
    proc = subprocess.Popen(
        _cmd_psql(sql), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    assert proc.stdout is not None
    for linea in proc.stdout:
        linea = linea.strip()
        if not linea:
            continue
        yield json.loads(linea)
    codigo = proc.wait()
    if codigo != 0:
        err = proc.stderr.read() if proc.stderr else ""
        raise RuntimeError(f"psql terminó con código {codigo}: {err.strip()}")


def psql_json(sql: str) -> list[dict]:
    return list(psql_stream(sql))


# ---------------------------------------------------------------------------
# MongoDB
# ---------------------------------------------------------------------------
def conectar_mongo():
    try:
        from pymongo import MongoClient
    except ImportError as exc:
        raise SystemExit(
            "Falta pymongo. Instale con:\n"
            "  .venv/bin/python -m pip install -r Fase3/requirements.txt"
        ) from exc

    cliente = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        cliente.admin.command("ping")
    except Exception as exc:
        raise SystemExit(
            f"No se pudo conectar a MongoDB en {MONGO_URI}.\n"
            "Levante el contenedor con: docker compose up -d\n"
            f"Detalle: {exc}"
        ) from exc
    return cliente, cliente[MONGO_DB]


def preparar_coleccion(db, nombre: str, recrear: bool) -> None:
    existentes = set(db.list_collection_names())
    if recrear and nombre in existentes:
        db.drop_collection(nombre)
        existentes.remove(nombre)
    if nombre not in existentes:
        db.create_collection(nombre)
    elif not recrear and db[nombre].estimated_document_count() > 0:
        raise SystemExit(
            f"La colección '{nombre}' ya tiene datos. Use --recrear para reconstruirla."
        )


def insertar_lotes(coleccion, documentos, tamano: int = 5000) -> int:
    total = 0
    lote = []
    for doc in documentos:
        lote.append(doc)
        if len(lote) >= tamano:
            coleccion.insert_many(lote, ordered=False)
            total += len(lote)
            lote = []
    if lote:
        coleccion.insert_many(lote, ordered=False)
        total += len(lote)
    return total


# ---------------------------------------------------------------------------
# Normalización
# ---------------------------------------------------------------------------
_TRANSLIT = str.maketrans(
    {
        "ø": "o", "æ": "ae", "œ": "oe", "ß": "ss", "ł": "l",
        "đ": "d", "ð": "d", "þ": "th", "ı": "i", "ħ": "h",
        "ŋ": "n", "ĳ": "ij",
    }
)


def normalizar(texto: object) -> str:
    if texto is None:
        return ""
    s = str(texto).strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().translate(_TRANSLIT)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def normalizar_con_fallback(original: object) -> dict:
    original = "" if original is None else str(original).strip()
    if not original:
        return {"original": original, "normalizado": original, "ok": False}
    base = unicodedata.normalize("NFKD", original)
    base = "".join(c for c in base if not unicodedata.combining(c))
    base = base.lower().translate(_TRANSLIT)
    residuales = [c for c in base if ord(c) > 127 and c.isalpha()]
    n = normalizar(original)
    if residuales or not n:
        return {"original": original, "normalizado": original, "ok": False}
    return {"original": original, "normalizado": n, "ok": True}


# ---------------------------------------------------------------------------
# Catálogos de Fase 1
# ---------------------------------------------------------------------------
def leer_dim_juegos() -> dict[int, dict]:
    filas = leer_csv(DATOS_FASE1 / "dim_juegos.csv")
    return {int(r["ID_OLIMPIADA"]): r for r in filas}


def leer_dim_sedes() -> dict[int, dict]:
    filas = leer_csv(DATOS_FASE1 / "dim_sedes.csv")
    return {int(r["ID_OLIMPIADA"]): r for r in filas}


def leer_alias() -> dict[str, list[str]]:
    ruta = DATOS_FASE1 / "dim_alias_paises.csv"
    if not ruta.exists():
        return {}
    salida: dict[str, list[str]] = {}
    for r in leer_csv(ruta):
        salida.setdefault(r["NOC"], []).append(r["ALIAS"])
    return salida


DEPORTE_ALIAS = {
    "atletismo": "athletics",
    "natacion": "swimming",
    "ciclismo": "cycling",
    "gimnasia": "gymnastics",
    "baloncesto": "basketball",
    "futbol": "football",
    "tenis": "tennis",
    "boxeo": "boxing",
    "lucha": "wrestling",
    "remo": "rowing",
    "vela": "sailing",
    "tiro": "shooting",
    "esgrima": "fencing",
    "halterofilia": "weightlifting",
    "badminton": "badminton",
    "hockey": "hockey",
    "voleibol": "volleyball",
    "beisbol": "baseball",
    "softbol": "softball",
    "taekwondo": "taekwondo",
    "judo": "judo",
    "esqui": "skiing",
    "patinaje": "skating",
    "natacion sincronizada": "synchronized swimming",
    "saltos": "diving",
    "waterpolo": "water polo",
}


def normalizar_deporte(texto: str | None) -> str:
    """Acepta el nombre del dataset o un alias común en español."""
    t = normalizar(texto)
    return DEPORTE_ALIAS.get(t, t)


def codigo_medalla(nombre: str | None) -> str | None:
    if not nombre:
        return None
    return {
        "Gold": "ORO",
        "Silver": "PLATA",
        "Bronze": "BRONCE",
        "No medal": None,
    }.get(nombre, nombre.upper())


def medalla_doc(medalla_id: int, nombre: str | None) -> dict | None:
    if not nombre or medalla_id == 1:
        return None
    return {"id": medalla_id, "codigo": codigo_medalla(nombre), "nombre": nombre}


def mongo_url() -> str:
    return MONGO_URI
