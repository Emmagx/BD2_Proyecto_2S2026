import argparse
import csv
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from pymongo import MongoClient
BASE = Path(__file__).resolve().parents[1]
EVID = BASE / "evidencias"
ENTRADA = EVID / "siguiente_lote_gimnasia_2024.jsonl"
REVISION = EVID / "lote_revision_identidades_gimnasia_2024.csv"
SALIDA = EVID / "lote_104_gimnasia_validado.jsonl"
RESPALDO = BASE / "respaldos" / "antes_lote_104.archive.gz"
parser = argparse.ArgumentParser()
parser.add_argument("--aplicar", action="store_true")
args = parser.parse_args()
def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(
        c for c in texto if not unicodedata.combining(c)
    )
    texto = re.sub(r"[^a-z0-9 ]", " ", texto.casefold())
    return " ".join(texto.split())
assert RESPALDO.is_file(), "Falta el respaldo actualizado"
assert RESPALDO.stat().st_size > 1000000, "Respaldo sospechoso"
with REVISION.open(encoding="utf-8-sig", newline="") as f:
    revisiones = list(csv.DictReader(f))
aprobables = {
    r["player_id_2024"]: r
    for r in revisiones
    if r["clasificacion"] == "PRIORIDAD_ALTA"
    and r["estado_auditoria"] == "NOMBRE_EQUIVALENTE_REVISAR"
}
assert len(aprobables) == 45
filas = [
    json.loads(linea)
    for linea in ENTRADA.read_text(
        encoding="utf-8"
    ).splitlines()
    if linea.strip()
]
assert len(filas) == 104
cliente = MongoClient(
    "mongodb://127.0.0.1:27017/?directConnection=true",
    serverSelectionTimeoutMS=5000
)
cliente.admin.command("ping")
db = cliente["olimpiadas_mongo"]
historicos = db.resultados.count_documents({
    "edicion.anio": {"$lt": 2024}
})
actuales = db.resultados.count_documents({
    "edicion.anio": 2024
})
assert historicos == 156032
assert actuales == 11
assert db.catalogos.find_one({"_id": "juego:63"})
ultimo = db.resultados.find_one(
    sort=[("_id", -1)],
    projection={"_id": 1}
)
assert ultimo["_id"] == 156043
EVENTOS = {
    483: (50, 393),
    480: (50, 390),
    493: (50, 399),
    490: (50, 390),
    494: (50, 400),
}
ids_por_player = {}
players_por_id = {}
claves = set()
docs = []
conteo_eventos = Counter()
for fila in filas:
    pid = str(fila["player_id_2024"])
    aid = int(fila["id_historico_propuesto"])
    eid = int(fila["evento_id"])
    noc = fila["noc"]
    assert pid in aprobables, f"Atleta no elegible: {pid}"
    revision = aprobables[pid]
    assert aid == int(revision["id_historico_propuesto"])
    assert noc == revision["noc_2024"]
    # No permitir IDs compartidos entre personas distintas.
    if pid in ids_por_player:
        assert ids_por_player[pid] == aid
    else:
        ids_por_player[pid] = aid
    if aid in players_por_id:
        assert players_por_id[aid] == pid, (
            f"ID historico compartido: {aid}"
        )
    else:
        players_por_id[aid] = pid
    assert eid in EVENTOS
    assert fila["medalla"] is None
    assert fila["posicion"] is None
    atleta = db.atletas.find_one({"_id": aid})
    assert atleta is not None
    assert normalizar(fila["nombre_2024"]) == normalizar(
        atleta["nombre"]
    ), f"Nombre diferente: {fila['nombre_2024']}"
    sexo_esperado = (
        "F" if fila["evento_original"].startswith("Women's")
        else "M"
    )
    assert atleta["sexo"].upper() == sexo_esperado
    assert atleta["sexo"].upper() == sexo_esperado
    # Debe existir historial de este ID, mismo NOC y deporte.
    assert db.resultados.find_one({
        "edicion.anio": {"$lt": 2024},
        "deporte.id": 50,
        "atletas": {
            "$elemMatch": {
                "id": aid,
                "noc": noc
            }
        }
    }), f"Historial incompatible: {aid}, {noc}"
    dep_id, disc_id = EVENTOS[eid]
    deporte = db.catalogos.find_one({
        "_id": f"deporte:{dep_id}"
    })
    disciplina = db.catalogos.find_one({
        "_id": f"disciplina:{disc_id}"
    })
    evento = db.catalogos.find_one({
        "_id": f"evento:{eid}"
    })
    pais = db.paises.find_one({"noc": noc})
    assert all([deporte, disciplina, evento, pais])
    assert evento["deporteId"] == dep_id
    assert evento["disciplinaId"] == disc_id
    clave = (pid, eid)
    assert clave not in claves, f"Duplicado interno: {clave}"
    claves.add(clave)
    assert db.resultados.find_one({
        "edicion.anio": 2024,
        "evento.id": eid,
        "atletas.id": aid
    }) is None, f"Participacion ya cargada: {clave}"
    rid = 156044 + len(docs)
    assert db.resultados.find_one({"_id": rid}) is None
    docs.append({
        "_id": rid,
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
            "id": eid,
            "nombre": evento["nombre"]
        },
        "posicion": None,
        "empate": False,
        "equipoMixto": False,
        "estado": "COMPLETED",
        "medalla": None,
        "multipais": False,
        "paisEquipo": noc,
        "paises": [noc],
        "atletas": [{
            "id": aid,
            "nombre": atleta["nombre"],
            "noc": noc,
            "edad": None
        }],
        "revisar": True,
        "fuente": {
            "dataset": "olympics_dataset.csv",
            "playerIdOriginal": pid,
            "eventoOriginal": fila["evento_original"],
            "identidadCriterio":
                "nombre_normalizado_noc_sexo_deporte_historico",
            "posicionVerificada": False,
            "estadoVerificado": False,
            "mapeoEvento": "revision_estructural"
        }
    })
    conteo_eventos[eid] += 1
assert len(docs) == 104
assert len(claves) == 104
assert {d["_id"] for d in docs} == set(
    range(156044, 156148)
)
with SALIDA.open("w", encoding="utf-8") as f:
    for doc in docs:
        f.write(json.dumps(doc, ensure_ascii=False) + "\n")
print("\n=== PREVALIDACION LOTE MASIVO GIMNASIA ===")
print("Historicos conservados:", historicos)
print("Resultados 2024 actuales:", actuales)
print("Participaciones validadas:", len(docs))
print("Atletas involucrados:", len(ids_por_player))
print("Distribucion por evento:", dict(conteo_eventos))
print("IDs propuestos: 156044 - 156147")
print("Archivo:", SALIDA)
if not args.aplicar:
    print("\nSIMULACION EXITOSA")
    print("MongoDB no fue modificado.")
    print("Revisar los resultados antes de aplicar.")
else:
    print("\nAPLICANDO CARGA...")
    resultado = db.resultados.insert_many(docs, ordered=True)
    assert len(resultado.inserted_ids) == 104
    total = db.resultados.count_documents({
        "edicion.anio": 2024
    })
    assert total == 115
    print("\n=== CARGA EXITOSA ===")
    print("Nuevos resultados:", 104)
    print("Total Paris 2024:", total)
    print("PENDIENTE: actualizar resumenes.")
cliente.close()

