import csv
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from pymongo import MongoClient
BASE = Path(__file__).resolve().parents[1]
SALIDA = BASE / "evidencias" / "mapa_general_eventos_2024.csv"
def norm(t):
    t = unicodedata.normalize("NFKD", str(t or ""))
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.casefold()
    t = re.sub(r"\bwomen's\b", "women", t)
    t = re.sub(r"\bmen's\b", "men", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    return " ".join(t.split())
def similitud(a, b):
    return SequenceMatcher(None, norm(a), norm(b)).ratio()
cliente = MongoClient(
    "mongodb://127.0.0.1:27017/?directConnection=true"
)
db = cliente["olimpiadas_mongo"]
conteos = Counter()
for d in db.paris2024_fuente.find(
    {},
    {"competenciaFuente": 1}
):
    c = d["competenciaFuente"]
    conteos[(c["deporte"], c["evento"])] += 1
assert len(conteos) == 361
deportes = {
    d["id"]: d["nombre"]
    for d in db.catalogos.find({"tipo": "deporte"})
}
eventos = list(db.catalogos.find(
    {"tipo": "evento"},
    {"id": 1, "nombre": 1, "deporteId": 1,
     "disciplinaId": 1}
))
filas = []
for (deporte, evento), cantidad in sorted(conteos.items()):
    opciones = []
    for e in eventos:
        nombre_deporte = deportes.get(e["deporteId"], "")
        nombre_evento = e["nombre"]
        score_deporte = similitud(
            deporte, nombre_deporte.split("(")[0]
        )
        # Solo comparar eventos dentro de deportes
        # razonablemente compatibles.
        if score_deporte < 0.65:
            continue
        score_evento = similitud(evento, nombre_evento)
        # No permitir equivalencias entre sexos opuestos.
        a = norm(evento)
        b = norm(nombre_evento)
        if ("women" in a) != ("women" in b):
            continue
        if ("men" in a.split()) != ("men" in b.split()):
            continue
        score = (
            score_evento * 0.80 +
            score_deporte * 0.20
        )
        opciones.append((score, e, nombre_deporte))
    opciones.sort(key=lambda x: x[0], reverse=True)
    registro = {
        "deporte_2024": deporte,
        "evento_2024": evento,
        "participaciones": cantidad,
        "estado": "PENDIENTE_VALIDACION"
    }
    for i in range(3):
        prefijo = f"opcion_{i+1}"
        if i < len(opciones):
            score, e, dnombre = opciones[i]
            registro[f"{prefijo}_evento_id"] = e["id"]
            registro[f"{prefijo}_evento"] = e["nombre"]
            registro[f"{prefijo}_deporte"] = dnombre
            registro[f"{prefijo}_score"] = round(score, 3)
        else:
            registro[f"{prefijo}_evento_id"] = ""
            registro[f"{prefijo}_evento"] = ""
            registro[f"{prefijo}_deporte"] = ""
            registro[f"{prefijo}_score"] = ""
    filas.append(registro)
campos = list(filas[0].keys())
with SALIDA.open(
    "w", encoding="utf-8-sig", newline=""
) as f:
    writer = csv.DictWriter(f, fieldnames=campos)
    writer.writeheader()
    writer.writerows(filas)
con_opciones = sum(
    1 for f in filas if f["opcion_1_evento_id"] != ""
)
print("\n=== MAPEO GENERAL DE EVENTOS ===")
print("Combinaciones analizadas:", len(filas))
print("Participaciones cubiertas:", sum(conteos.values()))
print("Eventos con al menos una sugerencia:", con_opciones)
print("Eventos sin sugerencias:", len(filas) - con_opciones)
print("\nArchivo:", SALIDA)
print("Todas las equivalencias requieren validacion.")
print("MongoDB no fue modificado.")
cliente.close()
