import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from pymongo import MongoClient
BASE = Path(__file__).resolve().parents[1]
EVID = BASE / "evidencias"
SALIDA = EVID / "lote_multideporte_2024.jsonl"
REPORTE = EVID / "reporte_lote_multideporte_2024.json"
def norm(valor):
    valor = unicodedata.normalize("NFKD", str(valor or ""))
    valor = "".join(
        c for c in valor if not unicodedata.combining(c)
    )
    valor = valor.casefold()
    valor = valor.replace("women's", "women")
    valor = valor.replace("men's", "men")
    valor = re.sub(r"[^a-z0-9]+", " ", valor)
    return " ".join(valor.split())
def clave_evento(nombre):
    palabras = norm(nombre).split()
    return tuple(sorted(
        p for p in palabras if p != "olympic"
    ))
def clave_deporte(nombre):
    return norm(nombre.split("(")[0])
PATRON_EQUIPO = re.compile(
    r"\b(team|relay|doubles|pairs|pair|"
    r"four|fours|eight|eights|quadruple|"
    r"synchronized|synchronised|madison|"
    r"mixed)\b", re.I
)
DEPORTES_EQUIPO = {
    "football", "hockey", "handball",
    "basketball", "basketball 3x3",
    "rugby sevens", "volleyball",
    "beach volleyball", "water polo"
}
cliente = MongoClient(
    "mongodb://127.0.0.1:27017/?directConnection=true",
    serverSelectionTimeoutMS=5000
)
cliente.admin.command("ping")
db = cliente["olimpiadas_mongo"]
assert db.paris2024_fuente.count_documents({}) == 14892
assert db.resultados.count_documents({
    "edicion.anio": 2024
}) == 115
assert db.resultados.count_documents({
    "edicion.anio": {"$lt": 2024}
}) == 156032
fuente = list(db.paris2024_fuente.find({}))
deportes = {
    d["id"]: d
    for d in db.catalogos.find({"tipo": "deporte"})
}
disciplinas = {
    d["id"]: d
    for d in db.catalogos.find({"tipo": "disciplina"})
}
eventos = list(db.catalogos.find({"tipo": "evento"}))
# Indexar todos los deportes, no solo las sugerencias CSV.
deportes_nombre = defaultdict(set)
for did, d in deportes.items():
    deportes_nombre[clave_deporte(d["nombre"])].add(did)
eventos_clave = defaultdict(list)
for e in eventos:
    did = e.get("deporteId")
    discid = e.get("disciplinaId")
    if did not in deportes or discid not in disciplinas:
        continue
    if disciplinas[discid].get("deporteId") != did:
        continue
    eventos_clave[
        (did, clave_evento(e["nombre"]))
    ].append(e)
# Buscar únicamente nombres relevantes para el CSV 2024.
nombres = {
    norm(f["atletaFuente"]["nombre"])
    for f in fuente
}
perfiles = {}
for a in db.atletas.find(
    {}, {"_id": 1, "nombre": 1, "sexo": 1}
):
    if norm(a.get("nombre")) in nombres:
        perfiles[a["_id"]] = a
identidades = defaultdict(set)
for r in db.resultados.find(
    {"edicion.anio": {"$lt": 2024}},
    {"atletas": 1, "deporte.id": 1}
):
    did = r.get("deporte", {}).get("id")
    for a in r.get("atletas", []):
        perfil = perfiles.get(a.get("id"))
        if perfil is None:
            continue
        identidades[(
            norm(perfil["nombre"]),
            a.get("noc"),
            str(perfil.get("sexo") or "").upper(),
            did
        )].add(a["id"])
integrados = set()
for r in db.resultados.find(
    {"edicion.anio": 2024},
    {"evento.id": 1, "atletas.id": 1}
):
    eid = r.get("evento", {}).get("id")
    for a in r.get("atletas", []):
        integrados.add((eid, a["id"]))
nocs = {
    p["noc"]
    for p in db.paises.find({}, {"noc": 1})
    if p.get("noc")
}
# Evitar que un mismo ID de origen identifique
# personas diferentes.
identidad_player = defaultdict(set)
for f in fuente:
    a = f["atletaFuente"]
    identidad_player[str(a["playerId"])].add((
        norm(a["nombre"]),
        a["noc"],
        str(a["sexo"]).upper()
    ))
# Evitar duplicados entre filas de origen de un mismo evento.
claves_origen = Counter()
for f in fuente:
    a = f["atletaFuente"]
    c = f["competenciaFuente"]
    claves_origen[(
        str(a["playerId"]),
        c["deporte"],
        c["evento"]
    )] += 1
# Evitar unir dos player_id distintos al mismo
# perfil historico dentro del lote.
players_por_atleta = defaultdict(set)
for f in fuente:
    a = f["atletaFuente"]
    for did in deportes_nombre.get(
        clave_deporte(f["competenciaFuente"]["deporte"]), set()
    ):
        ids = identidades.get((
            norm(a["nombre"]), a["noc"],
            str(a["sexo"]).upper(), did
        ), set())
        if len(ids) == 1:
            players_por_atleta[next(iter(ids))].add(
                str(a["playerId"])
            )
conteos = Counter()
por_deporte = Counter()
lote = []
claves_lote = set()
for f in fuente:
    a = f["atletaFuente"]
    c = f["competenciaFuente"]
    pid = str(a["playerId"])
    noc = a["noc"]
    sexo = str(a["sexo"]).upper()
    nombre = a["nombre"]
    deporte = c["deporte"]
    evento = c["evento"]
    clave_origen = (pid, deporte, evento)
    if len(identidad_player[pid]) != 1:
        motivo = "PLAYER_INCONSISTENTE"
    elif claves_origen[clave_origen] != 1:
        motivo = "DUPLICADO_ORIGEN"
    elif noc not in nocs:
        motivo = "NOC_DESCONOCIDO"
    elif (
        norm(deporte) in DEPORTES_EQUIPO
        or PATRON_EQUIPO.search(evento)
    ):
        motivo = "EVENTO_EQUIPO"
    else:
        dids = deportes_nombre.get(
            clave_deporte(deporte), set()
        )
        if len(dids) != 1:
            motivo = "DEPORTE_NO_UNICO"
        else:
            did = next(iter(dids))
            opciones = eventos_clave.get((
                did, clave_evento(evento)
            ), [])
            if len(opciones) != 1:
                motivo = "EVENTO_NO_UNICO"
            else:
                e = opciones[0]
                eid = e["id"]
                ids = identidades.get((
                    norm(nombre), noc, sexo, did
                ), set())
                if len(ids) != 1:
                    motivo = "ATLETA_NO_UNICO"
                else:
                    aid = next(iter(ids))
                    if len(players_por_atleta[aid]) != 1:
                        motivo = "IDENTIDAD_COMPARTIDA"
                    elif (eid, aid) in integrados:
                        motivo = "YA_INTEGRADO"
                    elif f["medallaFuente"] != "No medal":
                        motivo = "MEDALLA_PENDIENTE"
                    elif (eid, aid) in claves_lote:
                        motivo = "DUPLICADO_LOTE"
                    else:
                        claves_lote.add((eid, aid))
                        motivo = "PREPARADO"
                        lote.append({
                            "stagingId": f["_id"],
                            "playerIdOriginal": pid,
                            "atletaId": aid,
                            "nombre": perfiles[aid]["nombre"],
                            "noc": noc,
                            "deporte": {
                                "id": did,
                                "nombre": deportes[did]["nombre"]
                            },
                            "disciplina": {
                                "id": e["disciplinaId"],
                                "nombre": disciplinas[
                                    e["disciplinaId"]
                                ]["nombre"]
                            },
                            "evento": {
                                "id": eid,
                                "nombre": e["nombre"]
                            },
                            "eventoOriginal": evento,
                            "posicion": None,
                            "medalla": None,
                            "revisar": True
                        })
                        por_deporte[deporte] += 1
    conteos[motivo] += 1
assert sum(conteos.values()) == 14892
assert len(lote) == conteos["PREPARADO"]
assert len({
    (d["evento"]["id"], d["atletaId"])
    for d in lote
}) == len(lote)
with SALIDA.open("w", encoding="utf-8") as archivo:
    for d in lote:
        archivo.write(
            json.dumps(d, ensure_ascii=False) + "\n"
        )
reporte = {
    "filas_fuente": 14892,
    "resultados_2024_actuales": 115,
    "preparados": len(lote),
    "clasificacion": dict(conteos),
    "deportes_preparados": dict(por_deporte),
    "mongo_modificado": False
}
REPORTE.write_text(
    json.dumps(
        reporte, ensure_ascii=False, indent=2
    ),
    encoding="utf-8"
)
print("\n=== LOTE MASIVO MULTIDEPORTE PARIS 2024 ===")
print("Fuente analizada:", len(fuente))
print("Resultados actuales 2024:", 115)
print("Participaciones preparadas:", len(lote))
print("Deportes incluidos:", len(por_deporte))
print("\n=== CLASIFICACION ===")
for motivo, cantidad in conteos.most_common():
    print(f"{motivo}: {cantidad}")
print("\n=== DEPORTES DEL LOTE ===")
for deporte, cantidad in por_deporte.most_common():
    print(f"{deporte}: {cantidad}")
print("\nLote:", SALIDA)
print("Reporte:", REPORTE)
print("MongoDB no fue modificado.")
cliente.close()
