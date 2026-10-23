import csv
import json
from pathlib import Path
from pymongo import MongoClient
base = Path(__file__).resolve().parents[1] / "evidencias"
archivo_ids = base / "identidades_validadas_tiro_2024.csv"
archivo_lote = base / "lote_preliminar_tiro_2024.jsonl"
salida = base / "piloto_guatemala_2024.jsonl"
db = MongoClient(
    "mongodb://127.0.0.1:27017/?directConnection=true"
)["olimpiadas_mongo"]
confirmados = {}
with archivo_ids.open(encoding="utf-8-sig", newline="") as f:
    for fila in csv.DictReader(f):
        if fila["estado_identidad"] == "CONFIRMADO":
            confirmados[fila["id_fuente_2024"]] = int(
                fila["id_historico_confirmado"]
            )
# Solo los tres casos guatemaltecos ya revisados.
esperados = {
    "1958899": (143537, "ORO", 1),
    "1958970": (123253, "BRONCE", 3),
    "1959163": (143538, None, None),
}
assert all(confirmados.get(k) == v[0] for k, v in esperados.items())
assert db.resultados.count_documents({"edicion.anio": 2024}) == 0
assert db.catalogos.count_documents({"_id": "juego:63"}) == 0
ultimo = db.resultados.find_one(sort=[("_id", -1)], projection={"_id": 1})
siguiente_id = ultimo["_id"] + 1
documentos = []
with archivo_lote.open(encoding="utf-8") as f:
    for linea in f:
        if not linea.strip():
            continue
        doc = json.loads(linea)
        atleta = doc["atletas"][0]
        fuente = str(atleta["idFuente2024"])
        if fuente not in esperados:
            continue
        id_atleta, codigo, posicion = esperados[fuente]
        assert atleta["noc"] == "GUA"
        assert confirmados[fuente] == id_atleta
        historico = db.atletas.find_one({"_id": id_atleta})
        assert historico is not None
        medalla = None
        if codigo:
            catalogo = db.catalogos.find_one({
                "tipo": "medalla", "codigo": codigo
            })
            assert catalogo is not None
            medalla = {
                "id": catalogo["id"],
                "nombre": catalogo["nombre"],
                "codigo": catalogo["codigo"]
            }
        doc["_id"] = siguiente_id
        siguiente_id += 1
        doc["edicion"] = {
            "id": 63,
            "anio": 2024,
            "temporada": "Summer",
            "categoria": "Senior"
        }
        doc["posicion"] = posicion
        doc["estado"] = "COMPLETED" if posicion else None
        doc["medalla"] = medalla
        doc["revisar"] = posicion is None
        doc["atletas"] = [{
            "id": id_atleta,
            "nombre": historico["nombre"],
            "noc": "GUA",
            "edad": None
        }]
        # Campos auxiliares de auditoria, no del esquema final.
        doc.pop("pendienteMapeo", None)
        documentos.append(doc)
assert len(documentos) == 3, (
    f"Se esperaban 3 registros, encontrados: {len(documentos)}"
)
with salida.open("w", encoding="utf-8") as f:
    for doc in documentos:
        f.write(json.dumps(doc, ensure_ascii=False) + "\n")
print("\n=== PILOTO GUATEMALA PARIS 2024 ===")
for doc in documentos:
    print({
        "resultado_id_propuesto": doc["_id"],
        "atleta": doc["atletas"][0]["nombre"],
        "atleta_id": doc["atletas"][0]["id"],
        "evento": doc["evento"]["nombre"],
        "puesto": doc["posicion"],
        "medalla": doc["medalla"]["codigo"] if doc["medalla"] else None
    })
print("\nArchivo generado:", salida)
print("MONGODB NO FUE MODIFICADO.")
