import json
from pathlib import Path
from pymongo import MongoClient
BASE = Path(__file__).resolve().parents[1] / "evidencias"
ENTRADA = BASE / "lote_medallistas_gimnasia_preparado.jsonl"
SALIDA = BASE / "lote_medallistas_gimnasia_validado.jsonl"
REPORTE = BASE / "validacion_documental_medallistas_2024.json"
# ID de atleta, evento, puesto, medalla y NOC
# contrastados con resultados de Olympedia.
VALIDADOS = {
    145888: (490, 1, "ORO", "PHI"),
    146858: (493, 3, "BRONCE", "TPE"),
    133182: (494, 1, "ORO", "CHN"),
    141859: (494, 2, "PLATA", "CHN"),
    134270: (494, 3, "BRONCE", "GRE"),
    144053: (483, 1, "ORO", "ITA"),
    129288: (480, 1, "ORO", "BRA"),
    132107: (480, 2, "PLATA", "USA"),
}
RESULTADOS_OFICIALES = {
    490: "https://www.olympedia.org/results/2012231",
    493: "https://www.olympedia.org/results/2012244",
    494: "https://www.olympedia.org/results/2012247",
    483: "https://www.olympedia.org/results/2012288",
    480: "https://www.olympedia.org/results/2012274",
}
documentos = [
    json.loads(linea)
    for linea in ENTRADA.read_text(encoding="utf-8").splitlines()
    if linea.strip()
]
assert len(documentos) == 8
cliente = MongoClient(
    "mongodb://127.0.0.1:27017/?directConnection=true",
    serverSelectionTimeoutMS=5000
)
cliente.admin.command("ping")
db = cliente["olimpiadas_mongo"]
assert db.resultados.count_documents({"edicion.anio": 2024}) == 3
ids_resultados = set()
ids_atletas = set()
for doc in documentos:
    rid = doc["_id"]
    aid = doc["atletas"][0]["id"]
    noc = doc["atletas"][0]["noc"]
    evento = doc["evento"]["id"]
    puesto = doc["posicion"]
    medalla = doc["medalla"]["codigo"]
    assert aid in VALIDADOS
    assert (evento, puesto, medalla, noc) == VALIDADOS[aid]
    assert rid not in ids_resultados
    assert aid not in ids_atletas
    ids_resultados.add(rid)
    ids_atletas.add(aid)
    assert db.atletas.find_one({"_id": aid}) is not None
    assert db.resultados.find_one({"_id": rid}) is None
    assert db.resultados.find_one({
        "edicion.anio": 2024,
        "evento.id": evento,
        "atletas.id": aid
    }) is None
    doc["fuente"]["referenciaResultados"] = (
        RESULTADOS_OFICIALES[evento]
    )
    doc["fuente"]["referenciaIdentidad"] = (
        f"https://www.olympedia.org/athletes/{aid}"
    )
    doc["fuente"]["identidadVerificada"] = True
    doc["fuente"]["resultadoVerificado"] = True
assert ids_atletas == set(VALIDADOS)
assert ids_resultados == set(range(156036, 156044))
with SALIDA.open("w", encoding="utf-8") as f:
    for doc in documentos:
        f.write(json.dumps(doc, ensure_ascii=False) + "\n")
reporte = {
    "documentos_validados": 8,
    "identidades_con_referencia_documental": 8,
    "resultados_con_referencia_documental": 8,
    "ids_resultados": sorted(ids_resultados),
    "estado": "VALIDADO_PENDIENTE_CARGA",
    "mongo_modificado": False
}
REPORTE.write_text(
    json.dumps(reporte, ensure_ascii=False, indent=2),
    encoding="utf-8"
)
print("\n=== VALIDACION DOCUMENTAL GIMNASIA 2024 ===")
print("Identidades validadas:", len(ids_atletas))
print("Resultados validados:", len(documentos))
print("IDs:", sorted(ids_resultados))
print("Archivo:", SALIDA)
print("Estado: VALIDADO_PENDIENTE_CARGA")
print("MongoDB no fue modificado.")
cliente.close()
