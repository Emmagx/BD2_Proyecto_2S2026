import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from pymongo import MongoClient
BASE = Path(__file__).resolve().parents[1] / "evidencias"
EXACTOS = BASE / "revision_identidades_gimnasia_2024.csv"
VARIANTES = BASE / "revision_deporte_identidades_gimnasia_2024.csv"
SALIDA = BASE / "consolidado_identidades_gimnasia_2024.csv"
REPORTE = BASE / "consolidado_identidades_gimnasia_2024.json"
def leer_csv(ruta):
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))
exactos = leer_csv(EXACTOS)
variantes = leer_csv(VARIANTES)
assert len(exactos) == 178
assert len(variantes) == 134
cliente = MongoClient(
    "mongodb://127.0.0.1:27017/?directConnection=true",
    serverSelectionTimeoutMS=5000
)
cliente.admin.command("ping")
db = cliente["olimpiadas_mongo"]
propuestas = {}
# Primera fuente: nombre, NOC y sexo compatibles.
for fila in exactos:
    if fila["resultado_revision"] != "CANDIDATO_COMPATIBLE":
        continue
    aid = int(fila["id_candidato_verificado"])
    propuestas[fila["player_id_2024"]] = {
        "id": aid,
        "nombre": fila["nombre_2024"],
        "noc": fila["noc_2024"],
        "sexo": fila["sexo_2024"],
        "tipo": "NOMBRE_NOC_SEXO",
        "similitud": "1.0",
    }
# Segunda fuente: variantes con historial en gimnasia.
for fila in variantes:
    if fila["estado_revision_deporte"] != "MISMO_DEPORTE_REVISAR_IDENTIDAD":
        continue
    player_id = fila["player_id_2024"]
    assert player_id not in propuestas
    propuestas[player_id] = {
        "id": int(fila["id_sugerido_1"]),
        "nombre": fila["nombre_2024"],
        "noc": fila["noc_2024"],
        "sexo": fila["sexo_2024"],
        "tipo": "VARIANTE_MISMO_DEPORTE",
        "similitud": fila["similitud_1"],
    }
# Consultar perfiles historicos y verificar el deporte
# de TODOS los candidatos, incluidos los 44 exactos.
ids = {p["id"] for p in propuestas.values()}
perfiles = {
    a["_id"]: a
    for a in db.atletas.find({"_id": {"$in": list(ids)}})
}
deportes_por_id = defaultdict(set)
nocs_por_id = defaultdict(set)
for resultado in db.resultados.find(
    {
        "atletas.id": {"$in": list(ids)},
        "edicion.anio": {"$lt": 2024}
    },
    {"atletas": 1, "deporte.nombre": 1}
):
    for atleta in resultado.get("atletas", []):
        aid = atleta.get("id")
        if aid in ids:
            deportes_por_id[aid].add(
                resultado["deporte"]["nombre"]
            )
            if atleta.get("noc"):
                nocs_por_id[aid].add(atleta["noc"])
usos = defaultdict(list)
for player_id, propuesta in propuestas.items():
    usos[propuesta["id"]].append(player_id)
salida = []
conteos = Counter()
for player_id, propuesta in sorted(propuestas.items()):
    aid = propuesta["id"]
    perfil = perfiles.get(aid)
    nombre_h = perfil.get("nombre", "") if perfil else ""
    sexo_h = (
        str(perfil.get("sexo") or "").upper()
        if perfil else ""
    )
    nocs = nocs_por_id.get(aid, set())
    deportes = deportes_por_id.get(aid, set())
    mismo_deporte = any(
        "Artistic Gymnastics" in d for d in deportes
    )
    noc_compatible = propuesta["noc"] in nocs
    sexo_compatible = sexo_h == propuesta["sexo"].upper()
    id_compartido = len(usos[aid]) > 1
    if perfil is None:
        estado = "REVISAR_ID_INEXISTENTE"
    elif id_compartido:
        estado = "REVISAR_ID_COMPARTIDO"
    elif not mismo_deporte:
        estado = "REVISAR_DEPORTE"
    elif not noc_compatible:
        estado = "REVISAR_NOC"
    elif not sexo_compatible:
        estado = "REVISAR_SEXO"
    else:
        estado = "LISTO_PARA_REVISION_FINAL"
    conteos[estado] += 1
    salida.append({
        "player_id_2024": player_id,
        "nombre_2024": propuesta["nombre"],
        "noc_2024": propuesta["noc"],
        "sexo_2024": propuesta["sexo"],
        "id_historico_propuesto": aid,
        "nombre_historico": nombre_h,
        "tipo_coincidencia": propuesta["tipo"],
        "similitud": propuesta["similitud"],
        "nocs_historicos": "|".join(sorted(nocs)),
        "deportes_historicos": "|".join(sorted(deportes)),
        "estado": estado,
        "id_historico_confirmado": "",
        "decision_manual": "PENDIENTE",
        "observaciones": "",
    })
assert len(salida) == len(propuestas)
with SALIDA.open(
    "w", encoding="utf-8-sig", newline=""
) as archivo:
    escritor = csv.DictWriter(
        archivo, fieldnames=list(salida[0])
    )
    escritor.writeheader()
    escritor.writerows(salida)
reporte = {
    "atletas_fuente": 178,
    "candidatos_consolidados": len(salida),
    "clasificacion": dict(conteos),
    "confirmados_automaticamente": 0,
    "mongo_modificado": False
}
REPORTE.write_text(
    json.dumps(reporte, ensure_ascii=False, indent=2),
    encoding="utf-8"
)
print("\n=== CONSOLIDADO IDENTIDADES 2024 ===")
print("Atletas fuente:", 178)
print("Candidatos consolidados:", len(salida))
for estado, cantidad in conteos.most_common():
    print(f"{estado}: {cantidad}")
print("\nPRIMEROS 10:")
for fila in salida[:10]:
    print(
        fila["nombre_2024"],
        "->", fila["nombre_historico"],
        "| ID:", fila["id_historico_propuesto"],
        "|", fila["estado"]
    )
print("\nArchivo:", SALIDA)
print("Reporte:", REPORTE)
print("MongoDB no fue modificado.")
cliente.close()
