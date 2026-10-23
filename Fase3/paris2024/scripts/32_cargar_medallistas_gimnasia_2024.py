import argparse
import json
from pathlib import Path
from pymongo import MongoClient
from pymongo.errors import BulkWriteError
BASE = Path(__file__).resolve().parents[1]
ARCHIVO = (
    BASE / "evidencias" /
    "lote_medallistas_gimnasia_validado.jsonl"
)
RESPALDO = (
    BASE / "respaldos" /
    "antes_gimnasia_2024.archive.gz"
)
parser = argparse.ArgumentParser()
parser.add_argument(
    "--aplicar",
    action="store_true",
    help="Insertar los documentos validados"
)
args = parser.parse_args()
assert RESPALDO.is_file(), "No existe el respaldo"
assert RESPALDO.stat().st_size > 0, "Respaldo vacio"
docs = [
    json.loads(linea)
    for linea in ARCHIVO.read_text(
        encoding="utf-8"
    ).splitlines()
    if linea.strip()
]
assert len(docs) == 8
assert {d["_id"] for d in docs} == set(
    range(156036, 156044)
)
cliente = MongoClient(
    "mongodb://127.0.0.1:27017/?directConnection=true",
    serverSelectionTimeoutMS=5000
)
cliente.admin.command("ping")
db = cliente["olimpiadas_mongo"]
# Validar los registros historicos y el piloto previo.
historicos = db.resultados.count_documents({
    "edicion.anio": {"$lt": 2024}
})
assert historicos == 156032, (
    f"Historicos inesperados: {historicos}"
)
# Detectar carga previa para evitar duplicados.
ids = [d["_id"] for d in docs]
existentes = list(db.resultados.find(
    {"_id": {"$in": ids}},
    {"_id": 1}
))
if existentes:
    raise RuntimeError(
        "Algunos IDs ya existen: " +
        str([d["_id"] for d in existentes]) +
        ". No se insertara nada."
    )
actuales_2024 = db.resultados.count_documents({
    "edicion.anio": 2024
})
assert actuales_2024 == 3, (
    f"Se esperaban 3 resultados de 2024; "
    f"hay {actuales_2024}. Revisar antes de cargar."
)
# Validar duplicados dentro del lote.
claves = set()
jugadores = set()
for doc in docs:
    assert doc["edicion"]["anio"] == 2024
    assert doc["edicion"]["id"] == 63
    assert doc["deporte"]["id"] == 50
    assert len(doc["atletas"]) == 1
    assert len(doc["paises"]) == 1
    atleta = doc["atletas"][0]
    aid = atleta["id"]
    noc = atleta["noc"]
    eid = doc["evento"]["id"]
    clave = (eid, aid)
    assert clave not in claves, (
        f"Duplicado dentro del lote: {clave}"
    )
    claves.add(clave)
    assert aid not in jugadores
    jugadores.add(aid)
    assert db.atletas.find_one({"_id": aid})
    assert doc["paisEquipo"] == noc
    assert doc["paises"] == [noc]
    assert doc["medalla"]["codigo"] in (
        "ORO", "PLATA", "BRONCE"
    )
    puesto = doc["posicion"]
    codigo = doc["medalla"]["codigo"]
    assert (
        (puesto == 1 and codigo == "ORO")
        or (puesto == 2 and codigo == "PLATA")
        or (puesto == 3 and codigo == "BRONCE")
    )
    assert doc["fuente"].get(
        "identidadVerificada"
    ) is True
    assert doc["fuente"].get(
        "resultadoVerificado"
    ) is True
    # Comprobar que el catalogo referenciado existe.
    assert db.catalogos.find_one({
        "_id": f"evento:{eid}"
    })
    assert db.catalogos.find_one({
        "_id": f"disciplina:{doc['disciplina']['id']}"
    })
    assert db.catalogos.find_one({
        "_id": f"deporte:{doc['deporte']['id']}"
    })
    assert db.catalogos.find_one({
        "tipo": "medalla",
        "codigo": codigo
    })
    # Evitar una misma participacion repetida.
    assert db.resultados.find_one({
        "edicion.anio": 2024,
        "evento.id": eid,
        "atletas.id": aid
    }) is None
print("\n=== CARGA GIMNASIA PARIS 2024 ===")
print("Historicos conservados:", historicos)
print("Resultados 2024 actuales:", actuales_2024)
print("Documentos validados:", len(docs))
print("Respaldo:", RESPALDO)
if not args.aplicar:
    print("\nMODO SIMULACION")
    print("Validaciones correctas.")
    print("MongoDB NO fue modificado.")
    print(
        "Para insertar, ejecutar con --aplicar"
    )
else:
    print("\nINSERTANDO DOCUMENTOS...")
    try:
        resultado = db.resultados.insert_many(
            docs, ordered=True
        )
    except BulkWriteError as error:
        print("ERROR DURANTE LA INSERCION")
        print(error.details)
        print(
            "Revisar el estado real de MongoDB. "
            "No repetir automaticamente."
        )
        raise
    assert len(resultado.inserted_ids) == 8
    nuevo_total = db.resultados.count_documents({
        "edicion.anio": 2024
    })
    assert nuevo_total == 11, (
        f"Total inesperado de 2024: {nuevo_total}"
    )
    for doc in docs:
        guardado = db.resultados.find_one({
            "_id": doc["_id"]
        })
        assert guardado == doc
    print("\n=== INSERCION EXITOSA ===")
    print("Documentos insertados:", 8)
    print("Resultados 2024:", nuevo_total)
    print("IDs insertados:", sorted(ids))
    print(
        "\nIMPORTANTE: Falta actualizar "
        "resumenes de atletas y paises."
    )
cliente.close()
