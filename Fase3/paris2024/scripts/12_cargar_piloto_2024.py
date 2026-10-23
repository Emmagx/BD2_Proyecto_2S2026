import argparse
import json
from pathlib import Path
from pymongo import MongoClient
BASE = Path(__file__).resolve().parents[1]
ENTRADA = BASE / "evidencias" / "piloto_guatemala_2024_validado.jsonl"
JUEGO = {
    "_id": "juego:63",
    "tipo": "juego",
    "id": 63,
    "anio": 2024,
    "temporada": "Summer",
    "temporadaOriginal": "Summer",
    "categoria": "Senior",
    "nombreNormalizado": "2024 summer",
    "sedes": [{
        "ciudad": "Paris",
        "paisNoc": "FRA",
        "paisHistorico": "Francia",
        "nota": "Juegos Olimpicos de Paris 2024"
    }]
}
ESPERADOS = {
    143537: (687, 1, "ORO"),
    123253: (670, 3, "BRONCE"),
    143538: (687, 19, None),
}
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--aplicar",
        action="store_true",
        help="Realizar inserciones en MongoDB"
    )
    args = parser.parse_args()
    cliente = MongoClient(
        "mongodb://127.0.0.1:27017/?directConnection=true",
        serverSelectionTimeoutMS=5000
    )
    cliente.admin.command("ping")
    db = cliente["olimpiadas_mongo"]
    documentos = [
        json.loads(linea)
        for linea in ENTRADA.read_text(
            encoding="utf-8"
        ).splitlines()
        if linea.strip()
    ]
    assert len(documentos) == 3
    assert len({
        d["_id"] for d in documentos
    }) == 3
    assert db.catalogos.find_one({"_id": "juego:63"}) is None
    assert db.catalogos.count_documents({
        "tipo": "juego", "anio": 2024
    }) == 0
    assert db.resultados.count_documents({
        "edicion.anio": 2024
    }) == 0
    atletas_vistos = set()
    for doc in documentos:
        aid = doc["atletas"][0]["id"]
        assert aid in ESPERADOS
        assert aid not in atletas_vistos
        atletas_vistos.add(aid)
        evento_id, posicion, codigo = ESPERADOS[aid]
        assert doc["evento"]["id"] == evento_id
        assert doc["posicion"] == posicion
        assert doc["paises"] == ["GUA"]
        assert doc["edicion"] == {
            "id": 63,
            "anio": 2024,
            "temporada": "Summer",
            "categoria": "Senior"
        }
        assert doc["estado"] == "COMPLETED"
        assert doc["revisar"] is False
        actual = (
            doc["medalla"]["codigo"]
            if doc.get("medalla")
            else None
        )
        assert actual == codigo
        assert db.atletas.find_one({"_id": aid}) is not None
        assert db.resultados.find_one({"_id": doc["_id"]}) is None
        catalogo = db.catalogos.find_one({
            "_id": f"evento:{evento_id}"
        })
        assert catalogo is not None
        assert catalogo["deporteId"] == doc["deporte"]["id"]
        assert catalogo["disciplinaId"] == doc["disciplina"]["id"]
        if codigo:
            medalla = db.catalogos.find_one({
                "tipo": "medalla",
                "codigo": codigo
            })
            assert medalla is not None
            assert doc["medalla"]["id"] == medalla["id"]
    assert atletas_vistos == set(ESPERADOS)
    print("\n=== PARIS 2024 - CARGA PILOTO ===")
    print("Documentos verificados:", len(documentos))
    print("Catalogo propuesto:", JUEGO["_id"])
    if not args.aplicar:
        print("\nMODO SIMULACION")
        print("No se modifico MongoDB.")
        print("Para insertar, utilizar --aplicar")
        cliente.close()
        return
    print("\nMODO APLICACION")
    # MongoDB standalone no garantiza una transaccion
    # atomica entre estas dos colecciones.
    db.catalogos.insert_one(JUEGO)
    print("Catalogo insertado:", JUEGO["_id"])
    for doc in documentos:
        db.resultados.insert_one(doc)
        print("Resultado insertado:", doc["_id"])
    total = db.resultados.count_documents({
        "edicion.anio": 2024
    })
    assert total == 3, (
        f"Se esperaban 3 resultados de 2024, hay {total}"
    )
    print("\nINSERCION COMPLETADA")
    print("Resultados de Paris 2024:", total)
    print("Catalogo Paris 2024:",
          db.catalogos.count_documents({"_id": "juego:63"}))
    print("Resúmenes pendientes de recalcular.")
    cliente.close()
if __name__ == "__main__":
    main()
