import csv
import json
from collections import Counter
from pathlib import Path
from pymongo import MongoClient
BASE = Path(__file__).resolve().parents[1] / "evidencias"
LOTE = BASE / "lote_gimnasia_2024_preparado.jsonl"
REVISION = BASE / "lote_revision_identidades_gimnasia_2024.csv"
SALIDA = BASE / "siguiente_lote_gimnasia_2024.jsonl"
with REVISION.open(encoding="utf-8-sig", newline="") as f:
    revisiones = list(csv.DictReader(f))
candidatos = {
    r["player_id_2024"]: r
    for r in revisiones
    if r["clasificacion"] == "PRIORIDAD_ALTA"
}
assert len(candidatos) == 45
documentos = [
    json.loads(linea)
    for linea in LOTE.read_text(encoding="utf-8").splitlines()
    if linea.strip()
]
assert len(documentos) == 410
cliente = MongoClient(
    "mongodb://127.0.0.1:27017/?directConnection=true",
    serverSelectionTimeoutMS=5000
)
cliente.admin.command("ping")
db = cliente["olimpiadas_mongo"]
assert db.resultados.count_documents({
    "edicion.anio": 2024
}) == 11
salida = []
conteos = Counter()
ids_vistos = set()
for doc in documentos:
    pid = doc["fuente"]["playerIdOriginal"]
    if pid not in candidatos:
        continue
    revision = candidatos[pid]
    aid = int(revision["id_historico_propuesto"])
    evento = doc["evento"]["id"]
    assert aid not in ids_vistos or pid in candidatos
    ids_vistos.add(aid)
    atleta = db.atletas.find_one({"_id": aid})
    assert atleta is not None
    noc = doc["atletaFuente"]["noc"]
    assert revision["noc_2024"] == noc
    existente = db.resultados.find_one({
        "edicion.anio": 2024,
        "evento.id": evento,
        "atletas.id": aid
    })
    if existente:
        conteos["YA_INSERTADO"] += 1
        continue
    # Las identidades siguen siendo candidatas:
    # este archivo NO autoriza su insercion.
    preparado = {
        "player_id_2024": pid,
        "nombre_2024": doc["atletaFuente"]["nombre"],
        "id_historico_propuesto": aid,
        "nombre_historico": atleta["nombre"],
        "noc": noc,
        "evento_id": evento,
        "evento_original": doc["fuente"]["eventoOriginal"],
        "medalla": doc["resultadoFuente"]["codigoMedalla"],
        "posicion": None,
        "identidad_aprobada": False,
        "evento_aprobado": False,
        "apto_para_insercion": False
    }
    salida.append(preparado)
    conteos["PENDIENTE_VALIDACION"] += 1
with SALIDA.open("w", encoding="utf-8") as f:
    for doc in salida:
        f.write(json.dumps(doc, ensure_ascii=False) + "\n")
print("\n=== SIGUIENTE LOTE GIMNASIA 2024 ===")
print("Atletas candidatos de prioridad alta:", len(candidatos))
print("Participaciones pendientes:", len(salida))
print("Participaciones ya insertadas:", conteos["YA_INSERTADO"])
print("\nMEDALLAS EN EL LOTE PENDIENTE:")
medallas = Counter(
    d["medalla"] or "SIN_MEDALLA"
    for d in salida
)
for medalla, cantidad in medallas.items():
    print(medalla, cantidad)
print("\nArchivo:", SALIDA)
print("Ninguna identidad aprobada automaticamente.")
print("MongoDB no fue modificado.")
cliente.close()
