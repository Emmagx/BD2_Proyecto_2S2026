import csv
import json
from pathlib import Path
from pymongo import MongoClient
BASE = Path(__file__).resolve().parents[1] / "evidencias"
ENTRADA = BASE / "candidatos_medallistas_gimnasia_2024.csv"
SALIDA = BASE / "identidades_medallistas_verificadas_2024.csv"
# Vinculaciones seleccionadas para comprobacion documental.
# No se aceptan IDs de similitud baja sin evidencia.
IDS = {
    "Edriel Yulo": 145888,
    "Chia-hung Tang": 146858,
    "Yang Liu": 133182,
    "Jingyuan Zou": 141859,
    "Eleftherios Petrounias": 134270,
    "Alice D'amato": 144053,
    "Rebeca Andrade": 129288,
    "Simone Biles": 132107,
}
with ENTRADA.open(encoding="utf-8-sig", newline="") as f:
    registros = list(csv.DictReader(f))
assert len(registros) == 16
cliente = MongoClient(
    "mongodb://127.0.0.1:27017/?directConnection=true"
)
db = cliente["olimpiadas_mongo"]
salida = []
for fila in registros:
    nombre = fila["nombre_2024"]
    if nombre not in IDS:
        continue
    aid = IDS[nombre]
    atleta = db.atletas.find_one({"_id": aid})
    assert atleta is not None, f"Atleta inexistente: {aid}"
    anteriores = list(db.resultados.find(
        {
            "atletas.id": aid,
            "edicion.anio": {"$lt": 2024},
            "deporte.id": 50
        },
        {"atletas": 1}
    ))
    assert anteriores, f"Sin historial de gimnasia: {aid}"
    nocs = {
        a["noc"]
        for r in anteriores
        for a in r.get("atletas", [])
        if a.get("id") == aid
    }
    assert fila["noc"] in nocs, (
        f"NOC incompatible para {nombre}: {nocs}"
    )
    sexo_h = str(atleta.get("sexo") or "").upper()
    assert sexo_h in ("M", "F")
    assert sexo_h == (
        "F" if fila["evento_2024"].startswith("Women's")
        else "M"
    ), f"Sexo incompatible: {nombre}"
    salida.append({
        "player_id_2024": fila["player_id_2024"],
        "nombre_2024": nombre,
        "noc_2024": fila["noc"],
        "id_historico": aid,
        "nombre_historico": atleta["nombre"],
        "evento_2024": fila["evento_2024"],
        "medalla": fila["medalla"],
        "estado": "COMPATIBLE_PENDIENTE_APROBACION",
        "fuente_verificacion": "FIG / Olympedia / historial MongoDB",
        "observaciones": "Revisar evidencia individual antes de aprobar",
    })
assert len(salida) == 8
assert len({f["id_historico"] for f in salida}) == 8
assert len({f["player_id_2024"] for f in salida}) == 8
with SALIDA.open("w", encoding="utf-8-sig", newline="") as f:
    escritor = csv.DictWriter(
        f, fieldnames=list(salida[0].keys())
    )
    escritor.writeheader()
    escritor.writerows(salida)
print("\n=== IDENTIDADES MEDALLISTAS - PRIMER GRUPO ===")
print("Vinculaciones compatibles:", len(salida))
for fila in salida:
    print(
        fila["nombre_2024"],
        "->", fila["nombre_historico"],
        "| ID:", fila["id_historico"],
        "|", fila["medalla"]
    )
print("\nArchivo:", SALIDA)
print("Pendiente aprobacion documental individual.")
print("MongoDB no fue modificado.")
cliente.close()
