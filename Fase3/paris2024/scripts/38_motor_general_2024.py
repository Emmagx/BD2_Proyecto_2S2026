import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from pymongo import MongoClient
BASE = Path(__file__).resolve().parents[1]
EVID = BASE / "evidencias"
SALIDA = EVID / "candidatos_generales_2024.jsonl"
REPORTE = EVID / "reporte_motor_general_2024.json"
EVID.mkdir(parents=True, exist_ok=True)
def normalizar(valor):
    valor = unicodedata.normalize("NFKD", str(valor or ""))
    valor = "".join(
        c for c in valor if not unicodedata.combining(c)
    )
    valor = valor.casefold()
    valor = re.sub(r"[^a-z0-9]+", " ", valor)
    return " ".join(valor.split())
def clave_evento(valor):
    valor = str(valor or "")
    valor = re.sub(r"\bWomen's\b", "Women", valor, flags=re.I)
    valor = re.sub(r"\bMen's\b", "Men", valor, flags=re.I)
    tokens = normalizar(valor).split()
    tokens = [t for t in tokens if t not in ("olympic",)]
    return tuple(sorted(tokens))
def deporte_principal(valor):
    return normalizar(str(valor).split("(")[0])
# Exclusiones conservadoras de pruebas colectivas.
PATRON_EQUIPO = re.compile(
    r"\b(team|relay|doubles|pairs|pair|"
    r"four|fours|eight|eights|quadruple|"
    r"synchronised|synchronized|madison)\b",
    re.I
)
DEPORTES_COLECTIVOS = {
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
assert db.resultados.count_documents(
    {"edicion.anio": 2024}
) == 115
print("\n=== MOTOR GENERAL PARIS 2024 ===")
print("Cargando catalogos...")
catalogos = list(db.catalogos.find({
    "tipo": {"$in": ["deporte", "disciplina", "evento"]}
}))
deportes = {}
disciplinas = {}
eventos = {}
for c in catalogos:
    tipo = c["tipo"]
    if tipo == "deporte":
        deportes[c["id"]] = c
    elif tipo == "disciplina":
        disciplinas[c["id"]] = c
    else:
        eventos[c["id"]] = c
deportes_por_nombre = defaultdict(set)
for did, d in deportes.items():
    deportes_por_nombre[
        deporte_principal(d["nombre"])
    ].add(did)
eventos_por_clave = defaultdict(list)
for eid, e in eventos.items():
    did = e.get("deporteId")
    discid = e.get("disciplinaId")
    if did not in deportes or discid not in disciplinas:
        continue
    if disciplinas[discid].get("deporteId") != did:
        continue
    clave = (did, clave_evento(e["nombre"]))
    eventos_por_clave[clave].append(e)
fuente = list(db.paris2024_fuente.find({}))
assert len(fuente) == 14892
# Identificamos los nombres que realmente necesitamos.
nombres_fuente = {
    normalizar(f["atletaFuente"]["nombre"])
    for f in fuente
}
print("Buscando perfiles historicos compatibles...")
perfiles = {}
for atleta in db.atletas.find(
    {},
    {"_id": 1, "nombre": 1, "sexo": 1}
):
    if normalizar(atleta.get("nombre")) in nombres_fuente:
        perfiles[atleta["_id"]] = atleta
print("Perfiles historicos con nombre relevante:", len(perfiles))
# Un nombre similar NO basta: exigimos una participacion
# historica del mismo ID, NOC y deporte.
identidades = defaultdict(set)
for r in db.resultados.find(
    {"edicion.anio": {"$lt": 2024}},
    {"atletas": 1, "deporte.id": 1}
):
    did = r.get("deporte", {}).get("id")
    for a in r.get("atletas", []):
        aid = a.get("id")
        perfil = perfiles.get(aid)
        if perfil is None:
            continue
        noc = a.get("noc")
        sexo = str(perfil.get("sexo") or "").upper()
        clave = (
            normalizar(perfil.get("nombre")),
            noc,
            sexo,
            did
        )
        identidades[clave].add(aid)
# Controlar inconsistencias de un player_id en la fuente.
datos_por_player = defaultdict(set)
for f in fuente:
    a = f["atletaFuente"]
    datos_por_player[str(a["playerId"])].add((
        normalizar(a["nombre"]),
        a["noc"],
        str(a["sexo"]).upper()
    ))
jugadores_inconsistentes = {
    pid for pid, valores in datos_por_player.items()
    if len(valores) != 1
}
# Evitar duplicar resultados ya integrados.
integrados = set()
for r in db.resultados.find(
    {"edicion.anio": 2024},
    {"evento.id": 1, "atletas.id": 1}
):
    eid = r.get("evento", {}).get("id")
    for a in r.get("atletas", []):
        integrados.add((eid, a.get("id")))
nocs_validos = {
    p["noc"]
    for p in db.paises.find({}, {"noc": 1})
    if p.get("noc")
}
conteos = Counter()
por_deporte = Counter()
candidatos = []
claves_candidatos = set()
for fila in fuente:
    atleta = fila["atletaFuente"]
    competencia = fila["competenciaFuente"]
    pid = str(atleta["playerId"])
    noc = atleta["noc"]
    nombre = atleta["nombre"]
    sexo = str(atleta["sexo"]).upper()
    deporte = competencia["deporte"]
    evento = competencia["evento"]
    if pid in jugadores_inconsistentes:
        motivo = "PLAYER_ID_INCONSISTENTE"
    elif noc not in nocs_validos:
        motivo = "NOC_SIN_PAIS"
    elif (
        normalizar(deporte) in DEPORTES_COLECTIVOS
        or PATRON_EQUIPO.search(evento)
    ):
        motivo = "PRUEBA_COLECTIVA_REVISAR"
    else:
        dids = deportes_por_nombre.get(
            normalizar(deporte), set()
        )
        if len(dids) != 1:
            motivo = "DEPORTE_SIN_MAPEO_UNICO"
        else:
            did = next(iter(dids))
            posibles = eventos_por_clave.get(
                (did, clave_evento(evento)), []
            )
            if len(posibles) != 1:
                motivo = "EVENTO_SIN_MAPEO_UNICO"
            else:
                e = posibles[0]
                eid = e["id"]
                ids = identidades.get((
                    normalizar(nombre), noc, sexo, did
                ), set())
                if len(ids) != 1:
                    motivo = "IDENTIDAD_SIN_MAPEO_UNICO"
                else:
                    aid = next(iter(ids))
                    if (eid, aid) in integrados:
                        motivo = "YA_INTEGRADO"
                    elif fila["medallaFuente"] != "No medal":
                        motivo = "MEDALLA_REQUIERE_VALIDACION"
                    else:
                        clave = (eid, aid)
                        if clave in claves_candidatos:
                            motivo = "DUPLICADO_EN_FUENTE"
                        else:
                            claves_candidatos.add(clave)
                            motivo = "CANDIDATO_PARA_REVISION"
                            candidatos.append({
                                "stagingId": fila["_id"],
                                "playerId2024": pid,
                                "nombre2024": nombre,
                                "noc": noc,
                                "sexo": sexo,
                                "deporteOriginal": deporte,
                                "eventoOriginal": evento,
                                "deporteId": did,
                                "disciplinaId": e["disciplinaId"],
                                "eventoId": eid,
                                "atletaId": aid,
                                "medalla": None,
                                "posicion": None,
                                "estadoFinalVerificado": False,
                                "aptoParaInsercion": False
                            })
                            por_deporte[deporte] += 1
    conteos[motivo] += 1
assert sum(conteos.values()) == 14892
assert len(candidatos) == conteos["CANDIDATO_PARA_REVISION"]
with SALIDA.open("w", encoding="utf-8") as f:
    for c in candidatos:
        f.write(json.dumps(c, ensure_ascii=False) + "\n")
reporte = {
    "filas_fuente": len(fuente),
    "resultados_definitivos_2024": 115,
    "candidatos": len(candidatos),
    "clasificacion": dict(conteos),
    "candidatos_por_deporte": dict(por_deporte),
    "mongo_modificado": False
}
REPORTE.write_text(
    json.dumps(reporte, ensure_ascii=False, indent=2),
    encoding="utf-8"
)
print("\n=== CLASIFICACION GENERAL ===")
for estado, cantidad in conteos.most_common():
    print(f"{estado}: {cantidad}")
print("\n=== CANDIDATOS POR DEPORTE ===")
for deporte, cantidad in por_deporte.most_common():
    print(f"{deporte}: {cantidad}")
print("\nTOTAL CANDIDATOS:", len(candidatos))
print("Archivo:", SALIDA)
print("Reporte:", REPORTE)
print("MongoDB no fue modificado.")
cliente.close()
