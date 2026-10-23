import argparse
import json
from pathlib import Path
from pymongo import MongoClient
BASE = Path(__file__).resolve().parents[1]
EVID = BASE / "evidencias"
LOTE = EVID / "lote_individual_ampliado_2024.jsonl"
PLAN = EVID / "plan_carga_multideporte_657.jsonl"
BACKUP = BASE / "respaldos" / "antes_multideporte_657.gz"
parser = argparse.ArgumentParser()
parser.add_argument("--aplicar", action="store_true")
args = parser.parse_args()
assert BACKUP.exists(), "Falta el respaldo."
assert BACKUP.stat().st_size > 1000000
filas = [
    json.loads(x)
    for x in LOTE.read_text(encoding="utf-8").splitlines()
    if x.strip()
]
assert len(filas) == 657
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
assert actuales == 115
assert db.paris2024_fuente.count_documents({}) == 14892
ultimo = db.resultados.find_one(
    sort=[("_id", -1)],
    projection={"_id": 1}
)
assert ultimo["_id"] == 156147
integrados = set()
for r in db.resultados.find(
    {"edicion.anio": 2024},
    {"evento.id": 1, "atletas.id": 1}
):
    for a in r.get("atletas", []):
        integrados.add((r["evento"]["id"], a["id"]))
deportes = {
    x["id"]: x
    for x in db.catalogos.find({"tipo": "deporte"})
}
disciplinas = {
    x["id"]: x
    for x in db.catalogos.find({"tipo": "disciplina"})
}
eventos = {
    x["id"]: x
    for x in db.catalogos.find({"tipo": "evento"})
}
nocs = {
    x["noc"]
    for x in db.paises.find({}, {"noc": 1})
    if x.get("noc")
}
ids_atletas = sorted({x["atletaId"] for x in filas})
atletas = {
    x["_id"]: x
    for x in db.atletas.find(
        {"_id": {"$in": ids_atletas}},
        {"_id": 1, "nombre": 1, "sexo": 1}
    )
}
assert len(atletas) == 639
ids_staging = [x["stagingId"] for x in filas]
fuentes = {
    x["_id"]: x
    for x in db.paris2024_fuente.find({
        "_id": {"$in": ids_staging}
    })
}
assert len(fuentes) == 657
documentos = []
claves = set()
por_atleta = {}
paises_afectados = set()
for fila in filas:
    aid = fila["atletaId"]
    pid = str(fila["playerIdOriginal"])
    eid = fila["evento"]["id"]
    did = fila["deporte"]["id"]
    discid = fila["disciplina"]["id"]
    noc = fila["noc"]
    assert aid in atletas
    assert noc in nocs
    assert did in deportes
    assert discid in disciplinas
    assert eid in eventos
    assert disciplinas[discid]["deporteId"] == did
    assert eventos[eid]["deporteId"] == did
    assert eventos[eid]["disciplinaId"] == discid
    assert fila["nombre"] == atletas[aid]["nombre"]
    assert fila["medalla"] is None
    assert fila["posicion"] is None
    assert fila["revisar"] is True
    fuente = fuentes[fila["stagingId"]]
    af = fuente["atletaFuente"]
    cf = fuente["competenciaFuente"]
    assert str(af["playerId"]) == pid
    assert af["noc"] == noc
    assert af["sexo"].upper() == atletas[aid]["sexo"].upper()
    assert cf["evento"] == fila["eventoOriginal"]
    assert fuente["medallaFuente"] == "No medal"
    if aid in por_atleta:
        assert por_atleta[aid] == pid
    else:
        por_atleta[aid] = pid
    clave = (eid, aid)
    assert clave not in integrados
    assert clave not in claves
    claves.add(clave)
    rid = 156148 + len(documentos)
    documentos.append({
        "_id": rid,
        "edicion": {
            "id": 63,
            "anio": 2024,
            "temporada": "Summer",
            "categoria": "Senior"
        },
        "deporte": {
            "id": did,
            "nombre": deportes[did]["nombre"]
        },
        "disciplina": {
            "id": discid,
            "nombre": disciplinas[discid]["nombre"]
        },
        "evento": {
            "id": eid,
            "nombre": eventos[eid]["nombre"]
        },
        "posicion": None,
        "empate": False,
        "equipoMixto": False,
        "estado": "PENDING_VERIFICATION",
        "medalla": None,
        "multipais": False,
        "paisEquipo": noc,
        "paises": [noc],
        "atletas": [{
            "id": aid,
            "nombre": atletas[aid]["nombre"],
            "noc": noc,
            "edad": None
        }],
        "revisar": True,
        "fuente": {
            "dataset": "olympics_dataset.csv",
            "stagingId": fila["stagingId"],
            "playerIdOriginal": pid,
            "eventoOriginal": fila["eventoOriginal"],
            "identidadCriterio": "coincidencia_historica",
            "posicionVerificada": False,
            "estadoVerificado": False,
            "tipoParticipacion": "individual"
        }
    })
    paises_afectados.add(noc)
assert len(documentos) == 657
assert len(claves) == 657
assert len(por_atleta) == 639
with PLAN.open("w", encoding="utf-8") as f:
    for d in documentos:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")
print("\n=== VALIDACION MASIVA MULTIDEPORTE ===")
print("Historicos conservados:", historicos)
print("Paris 2024 actuales:", actuales)
print("Participaciones preparadas:", len(documentos))
print("Atletas afectados:", len(por_atleta))
print("Paises afectados:", len(paises_afectados))
print("IDs propuestos: 156148 - 156804")
print("Archivo de plan:", PLAN)
if not args.aplicar:
    print("\nSIMULACION EXITOSA")
    print("MongoDB no fue modificado.")
else:
    print("\nINSERTANDO LOTE...")
    resultado = db.resultados.insert_many(
        documentos, ordered=True
    )
    assert len(resultado.inserted_ids) == 657
    total_2024 = db.resultados.count_documents({
        "edicion.anio": 2024
    })
    total_general = db.resultados.count_documents({})
    assert total_2024 == 772
    assert total_general == 156804
    print("\n=== CARGA MASIVA EXITOSA ===")
    print("Documentos nuevos:", 657)
    print("Resultados Paris 2024:", total_2024)
    print("Resultados generales:", total_general)
    print("PENDIENTE: actualizar resumenes.")
cliente.close()
