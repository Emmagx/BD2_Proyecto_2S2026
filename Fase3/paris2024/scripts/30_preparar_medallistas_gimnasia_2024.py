import csv
import json
from pathlib import Path
from pymongo import MongoClient
BASE = Path(__file__).resolve().parents[1] / "evidencias"
ENTRADA = BASE / "identidades_medallistas_verificadas_2024.csv"
SALIDA = BASE / "lote_medallistas_gimnasia_preparado.jsonl"
EVENTOS = {
    "Men's Floor Exercise": (50, 390, 490),
    "Men's Horizontal Bar": (50, 399, 493),
    "Men's Rings": (50, 400, 494),
    "Women's Balance Beam": (50, 393, 483),
    "Women's Floor Exercise": (50, 390, 480),
}
PUESTOS = {
    "Edriel Yulo": 1,
    "Chia-hung Tang": 3,
    "Yang Liu": 1,
    "Jingyuan Zou": 2,
    "Eleftherios Petrounias": 3,
    "Alice D'amato": 1,
    "Rebeca Andrade": 1,
    "Simone Biles": 2,
}
with ENTRADA.open(encoding="utf-8-sig", newline="") as f:
    filas = list(csv.DictReader(f))
assert len(filas) == 8
assert len({f["player_id_2024"] for f in filas}) == 8
cliente = MongoClient(
    "mongodb://127.0.0.1:27017/?directConnection=true"
)
db = cliente["olimpiadas_mongo"]
cliente.admin.command("ping")
assert db.catalogos.find_one({"_id": "juego:63"})
assert db.resultados.count_documents({
    "edicion.anio": 2024
}) == 3
ultimo = db.resultados.find_one(
    {"_id": {"$type": "int"}},
    sort=[("_id", -1)],
    projection={"_id": 1}
)
siguiente = ultimo["_id"] + 1
documentos = []
for f in filas:
    nombre = f["nombre_2024"]
    aid = int(f["id_historico"])
    noc = f["noc_2024"]
    codigo = f["medalla"]
    evento_original = f["evento_2024"]
    assert nombre in PUESTOS
    assert evento_original in EVENTOS
    assert f["estado"] == "COMPATIBLE_PENDIENTE_APROBACION"
    dep_id, disc_id, evento_id = EVENTOS[evento_original]
    atleta = db.atletas.find_one({"_id": aid})
    deporte = db.catalogos.find_one({"_id": f"deporte:{dep_id}"})
    disciplina = db.catalogos.find_one({"_id": f"disciplina:{disc_id}"})
    evento = db.catalogos.find_one({"_id": f"evento:{evento_id}"})
    medalla = db.catalogos.find_one({
        "tipo": "medalla", "codigo": codigo
    })
    assert all([atleta, deporte, disciplina, evento, medalla])
    assert evento["deporteId"] == dep_id
    assert evento["disciplinaId"] == disc_id
    assert not db.resultados.find_one({
        "edicion.anio": 2024,
        "evento.id": evento_id,
        "atletas.id": aid
    }), f"Participacion ya insertada: {nombre}"
    assert not db.resultados.find_one({"_id": siguiente})
    puesto = PUESTOS[nombre]
    assert codigo == (
        "ORO" if puesto == 1
        else "PLATA" if puesto == 2
        else "BRONCE"
    )
    doc = {
        "_id": siguiente,
        "edicion": {
            "id": 63,
            "anio": 2024,
            "temporada": "Summer",
            "categoria": "Senior"
        },
        "deporte": {
            "id": dep_id,
            "nombre": deporte["nombre"]
        },
        "disciplina": {
            "id": disc_id,
            "nombre": disciplina["nombre"]
        },
        "evento": {
            "id": evento_id,
            "nombre": evento["nombre"]
        },
        "posicion": puesto,
        "empate": nombre == "Chia-hung Tang",
        "equipoMixto": False,
        "estado": "COMPLETED",
        "medalla": {
            "id": medalla["id"],
            "nombre": medalla["nombre"],
            "codigo": medalla["codigo"]
        },
        "multipais": False,
        "paisEquipo": noc,
        "paises": [noc],
        "atletas": [{
            "id": aid,
            "nombre": atleta["nombre"],
            "noc": noc,
            "edad": None
        }],
        "revisar": False,
        "fuente": {
            "dataset": "olympics_dataset.csv",
            "playerIdOriginal": f["player_id_2024"],
            "eventoOriginal": evento_original,
            "referenciaResultados":
                "https://www.olympedia.org/editions/63/sports/GAR"
        }
    }
    documentos.append(doc)
    siguiente += 1
assert len(documentos) == 8
with SALIDA.open("w", encoding="utf-8") as archivo:
    for doc in documentos:
        archivo.write(json.dumps(doc, ensure_ascii=False) + "\n")
print("\n=== LOTE DE MEDALLISTAS PREPARADO ===")
for d in documentos:
    print(
        d["_id"],
        "|", d["atletas"][0]["nombre"],
        "| evento:", d["evento"]["id"],
        "| puesto:", d["posicion"],
        "| medalla:", d["medalla"]["codigo"]
    )
print("\nDocumentos preparados:", len(documentos))
print("Archivo:", SALIDA)
print("Pendiente aprobacion final de identidades.")
print("NO SE MODIFICO MONGODB.")
cliente.close()
