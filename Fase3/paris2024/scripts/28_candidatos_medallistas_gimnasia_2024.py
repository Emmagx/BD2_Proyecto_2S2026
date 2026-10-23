import csv
import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from pymongo import MongoClient
BASE = Path(__file__).resolve().parents[1] / "evidencias"
ENTRADA = BASE / "revision_medallistas_gimnasia_2024.csv"
SALIDA = BASE / "candidatos_medallistas_gimnasia_2024.csv"
def normalizar(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9 ]", " ", s.casefold())
    return " ".join(s.split())
def similitud(a, b):
    x, y = normalizar(a), normalizar(b)
    return max(
        SequenceMatcher(None, x, y).ratio(),
        SequenceMatcher(
            None,
            " ".join(sorted(x.split())),
            " ".join(sorted(y.split()))
        ).ratio()
    )
with ENTRADA.open(encoding="utf-8-sig", newline="") as f:
    medallistas = list(csv.DictReader(f))
assert len(medallistas) == 16
cliente = MongoClient(
    "mongodb://127.0.0.1:27017/?directConnection=true"
)
db = cliente["olimpiadas_mongo"]
# Solo deportistas con historial en gimnasia.
ids_noc = defaultdict(set)
for r in db.resultados.find(
    {
        "edicion.anio": {"$lt": 2024},
        "deporte.id": 50
    },
    {"atletas": 1}
):
    for a in r.get("atletas", []):
        if isinstance(a.get("id"), int) and a.get("noc"):
            ids_noc[a["noc"]].add(a["id"])
perfiles = defaultdict(list)
for noc, ids in ids_noc.items():
    for a in db.atletas.find(
        {"_id": {"$in": list(ids)}},
        {"_id": 1, "nombre": 1, "sexo": 1}
    ):
        perfiles[noc].append(a)
salida = []
for m in medallistas:
    noc = m["noc"]
    nombre = m["nombre_2024"]
    opciones = []
    for a in perfiles.get(noc, []):
        puntaje = similitud(nombre, a.get("nombre", ""))
        # Presentar candidatos; no aprobar automaticamente.
        if puntaje >= 0.50:
            opciones.append(
                (puntaje, a["_id"], a.get("nombre", ""))
            )
    opciones.sort(key=lambda x: (-x[0], x[1]))
    mejores = opciones[:3]
    registro = {
        **m,
        "candidato_1_id": mejores[0][1] if mejores else "",
        "candidato_1_nombre": mejores[0][2] if mejores else "",
        "candidato_1_similitud": (
            round(mejores[0][0], 3) if mejores else ""
        ),
        "otros_candidatos": " | ".join(
            f"{aid}: {nombre_h} ({puntaje:.3f})"
            for puntaje, aid, nombre_h in mejores[1:]
        ),
        "estado_verificacion": "PENDIENTE",
    }
    salida.append(registro)
with SALIDA.open("w", encoding="utf-8-sig", newline="") as f:
    escritor = csv.DictWriter(
        f, fieldnames=list(salida[0].keys())
    )
    escritor.writeheader()
    escritor.writerows(salida)
print("\n=== MEDALLISTAS: CANDIDATOS HISTORICOS ===")
for f in salida:
    print(
        f"{f['nombre_2024']} ({f['noc']}) "
        f"| {f['medalla']} "
        f"| {f['evento_2024']}"
    )
    print(
        "  Candidato:",
        f["candidato_1_nombre"] or "NINGUNO",
        "| ID:", f["candidato_1_id"] or "-",
        "| similitud:", f["candidato_1_similitud"] or "-"
    )
print("\nArchivo:", SALIDA)
print("Ninguna identidad fue aprobada.")
print("MongoDB no fue modificado.")
cliente.close()
