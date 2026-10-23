import argparse
import hashlib
import json
from collections import defaultdict, Counter
from pathlib import Path
from pymongo import MongoClient, UpdateOne
BASE = Path("paris2024/evidencias")
BASE.mkdir(parents=True, exist_ok=True)
parser = argparse.ArgumentParser()
parser.add_argument("--aplicar", action="store_true")
args = parser.parse_args()
DEPORTES_EQUIPO = {
    "Football",
    "Hockey",
    "Handball",
    "Basketball",
    "Basketball 3x3",
    "Rugby Sevens",
    "Volleyball",
    "Beach Volleyball",
    "Water Polo"
}
c = MongoClient(
    "mongodb://127.0.0.1:27017/?directConnection=true",
    serverSelectionTimeoutMS=5000
)
c.admin.command("ping")
db = c["olimpiadas_mongo"]
assert db.paris2024_fuente.count_documents({}) == 14892
assert db.resultados.count_documents({"edicion.anio": 2024}) == 4081
assert db.resultados.count_documents({"edicion.anio": {"$lt": 2024}}) == 156032
grupos = defaultdict(list)
conteos = Counter()
for fila in db.paris2024_fuente.find({}):
    comp = fila["competenciaFuente"]
    atleta = fila["atletaFuente"]
    deporte = comp["deporte"]
    if deporte not in DEPORTES_EQUIPO:
        continue
    equipo = str(
        fila.get("filaOriginal", {}).get("Team") or ""
    ).strip()
    if not equipo:
        conteos["SIN_NOMBRE_EQUIPO"] += 1
        continue
    clave = (
        deporte,
        comp["evento"],
        atleta["noc"],
        equipo
    )
    grupos[clave].append(fila)
documentos = []
pendientes = []
for (deporte, evento, noc, equipo), filas in sorted(grupos.items()):
    atletas = {}
    medallas = set()
    staging_ids = []
    for fila in filas:
        atleta = fila["atletaFuente"]
        pid = str(atleta["playerId"])
        atletas[pid] = {
            "playerId": pid,
            "nombre": atleta["nombre"],
            "noc": noc,
            "sexo": atleta["sexo"]
        }
        medallas.add(fila["medallaFuente"])
        staging_ids.append(fila["_id"])
    if len(atletas) < 2:
        conteos["GRUPO_UNIPERSONAL"] += 1
        pendientes.append({
            "deporte": deporte,
            "evento": evento,
            "noc": noc,
            "equipo": equipo,
            "motivo": "GRUPO_UNIPERSONAL"
        })
        continue
    if len(medallas) != 1:
        conteos["MEDALLAS_INCONSISTENTES"] += 1
        pendientes.append({
            "deporte": deporte,
            "evento": evento,
            "noc": noc,
            "equipo": equipo,
            "motivo": "MEDALLAS_INCONSISTENTES",
            "medallas": sorted(medallas)
        })
        continue
    medalla = next(iter(medallas))
    # ID reproducible a partir de la identidad del equipo.
    identidad = json.dumps(
        [deporte, evento, noc, equipo],
        ensure_ascii=False
    )
    gid = hashlib.sha256(
        identidad.encode("utf-8")
    ).hexdigest()[:24]
    documentos.append({
        "_id": "paris2024_equipo:" + gid,
        "edicion": 2024,
        "deporteFuente": deporte,
        "eventoFuente": evento,
        "noc": noc,
        "equipoFuente": equipo,
        "atletasFuente": list(atletas.values()),
        "numeroIntegrantes": len(atletas),
        "medallaFuente": medalla,
        "stagingIds": sorted(staging_ids),
        "integracion": {
            "estado": "PENDIENTE_VALIDACION",
            "resultadoId": None,
            "eventoId": None,
            "identidadesVerificadas": False
        }
    })
    conteos["EQUIPO_PREPARADO"] += 1
reporte = {
    "grupos_encontrados": len(grupos),
    "equipos_preparados": len(documentos),
    "integrantes_fuente": sum(
        d["numeroIntegrantes"] for d in documentos
    ),
    "clasificacion": dict(conteos),
    "pendientes": pendientes,
    "mongo_modificado": args.aplicar
}
ruta = BASE / "reporte_equipos_preparados_2024.json"
ruta.write_text(
    json.dumps(reporte, ensure_ascii=False, indent=2),
    encoding="utf-8"
)
print("\n=== AGRUPACION MASIVA DE EQUIPOS ===")
print("Grupos encontrados:", len(grupos))
print("Equipos preparados:", len(documentos))
print("Integrantes representados:", reporte["integrantes_fuente"])
print("Clasificacion:", dict(conteos))
print("\nEJEMPLOS:")
for doc in documentos[:10]:
    print(
        doc["deporteFuente"],
        "|", doc["eventoFuente"],
        "|", doc["equipoFuente"],
        "| integrantes:", doc["numeroIntegrantes"],
        "| medalla:", doc["medallaFuente"]
    )
if args.aplicar:
    coleccion = db["paris2024_equipos_preparados"]
    # No sobrescribir documentos de una preparacion anterior.
    operaciones = [
        UpdateOne(
            {"_id": d["_id"]},
            {"$setOnInsert": d},
            upsert=True
        )
        for d in documentos
    ]
    if operaciones:
        coleccion.bulk_write(operaciones, ordered=False)
    ids = {d["_id"] for d in documentos}
    almacenados = {
        d["_id"]: d
        for d in coleccion.find({"_id": {"$in": list(ids)}})
    }
    assert set(almacenados) == ids
    for d in documentos:
        assert almacenados[d["_id"]] == d, (
            "Equipo almacenado diferente: " + d["_id"]
        )
    assert db.resultados.count_documents({
        "edicion.anio": 2024
    }) == 4081
    print("\nEQUIPOS PREPARADOS EN MONGODB")
    print("Coleccion: paris2024_equipos_preparados")
else:
    print("\nSIMULACION: MongoDB no fue modificado.")
print("Reporte:", ruta)
c.close()
