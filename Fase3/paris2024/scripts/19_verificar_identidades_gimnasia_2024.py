import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from pymongo import MongoClient
BASE = Path(__file__).resolve().parents[1] / "evidencias"
ENTRADA = BASE / "identidades_gimnasia_2024.csv"
SALIDA = BASE / "revision_identidades_gimnasia_2024.csv"
REPORTE = BASE / "resumen_revision_identidades_gimnasia_2024.json"
with ENTRADA.open(encoding="utf-8-sig", newline="") as f:
    filas = list(csv.DictReader(f))
assert len(filas) == 178, f"Se esperaban 178 atletas; hay {len(filas)}"
ids = set()
for fila in filas:
    for valor in fila["ids_historicos_candidatos"].split("|"):
        if valor.strip():
            ids.add(int(valor.strip()))
cliente = MongoClient(
    "mongodb://127.0.0.1:27017/?directConnection=true",
    serverSelectionTimeoutMS=5000
)
cliente.admin.command("ping")
db = cliente["olimpiadas_mongo"]
historicos = {
    a["_id"]: a
    for a in db.atletas.find({"_id": {"$in": list(ids)}})
}
# Recuperar países de las participaciones históricas.
nocs_por_id = defaultdict(set)
for r in db.resultados.find(
    {
        "atletas.id": {"$in": list(ids)},
        "edicion.anio": {"$lt": 2024}
    },
    {"atletas": 1}
):
    for atleta in r.get("atletas", []):
        aid = atleta.get("id")
        if aid in ids and atleta.get("noc"):
            nocs_por_id[aid].add(atleta["noc"])
conteos = Counter()
salida = []
for fila in filas:
    candidatos = [
        int(x)
        for x in fila["ids_historicos_candidatos"].split("|")
        if x.strip()
    ]
    noc_2024 = fila["noc_2024"].strip()
    sexo_2024 = fila["sexo_2024"].strip().upper()
    estado = fila["estado_identidad"]
    id_candidato = ""
    nocs_historicos = ""
    sexo_historico = ""
    observacion = ""
    if estado == "DATOS_FUENTE_INCONSISTENTES":
        decision = "REVISAR_FUENTE"
    elif len(candidatos) == 0:
        decision = "SIN_CANDIDATO_EXACTO"
        observacion = "Revisar variantes de nombre antes de crear atleta"
    elif len(candidatos) > 1:
        decision = "AMBIGUO_REVISAR"
        observacion = "Hay varios IDs historicos candidatos"
    else:
        aid = candidatos[0]
        id_candidato = aid
        perfil = historicos.get(aid)
        if perfil is None:
            decision = "CANDIDATO_NO_EXISTE"
        else:
            nocs = nocs_por_id.get(aid, set())
            nocs_historicos = "|".join(sorted(nocs))
            sexo_historico = str(
                perfil.get("sexo") or perfil.get("sex") or ""
            ).strip().upper()
            noc_coincide = noc_2024 in nocs
            sexo_conocido = sexo_historico in ("M", "F")
            sexo_coincide = sexo_historico == sexo_2024
            if not nocs:
                decision = "REVISAR_SIN_NOC_HISTORICO"
            elif not noc_coincide:
                decision = "REVISAR_NOC"
            elif sexo_conocido and not sexo_coincide:
                decision = "REVISAR_SEXO"
            elif not sexo_conocido:
                decision = "REVISAR_SEXO_NO_DISPONIBLE"
            else:
                decision = "CANDIDATO_COMPATIBLE"
            observacion = (
                "Compatibilidad tecnica; falta confirmar identidad"
                if decision == "CANDIDATO_COMPATIBLE"
                else "Requiere revision antes de asignar ID"
            )
    conteos[decision] += 1
    salida.append({
        **fila,
        "id_candidato_verificado": id_candidato,
        "nocs_historicos": nocs_historicos,
        "sexo_historico": sexo_historico,
        "resultado_revision": decision,
        "detalle_revision": observacion,
    })
with SALIDA.open("w", encoding="utf-8-sig", newline="") as f:
    escritor = csv.DictWriter(f, fieldnames=list(salida[0].keys()))
    escritor.writeheader()
    escritor.writerows(salida)
reporte = {
    "atletas_evaluados": len(salida),
    "participaciones_representadas": sum(
        int(f["cantidad_eventos"]) for f in salida
    ),
    "candidatos_historicos_consultados": len(ids),
    "estados": dict(conteos),
    "identidades_confirmadas": 0,
    "mongo_modificado": False,
}
REPORTE.write_text(
    json.dumps(reporte, ensure_ascii=False, indent=2),
    encoding="utf-8"
)
print("\n=== REVISION IDENTIDADES GIMNASIA 2024 ===")
print("Atletas evaluados:", len(salida))
print("Candidatos historicos consultados:", len(ids))
print("\nCLASIFICACION:")
for estado, cantidad in conteos.most_common():
    print(f"  {estado}: {cantidad}")
print("\nEJEMPLOS DE CANDIDATOS:")
mostrados = 0
for fila in salida:
    if not fila["id_candidato_verificado"]:
        continue
    print(
        fila["nombre_2024"],
        "| NOC 2024:", fila["noc_2024"],
        "| NOC historico:", fila["nocs_historicos"] or "-",
        "| sexo historico:", fila["sexo_historico"] or "-",
        "| estado:", fila["resultado_revision"]
    )
    mostrados += 1
    if mostrados == 10:
        break
print("\nArchivo:", SALIDA)
print("Reporte:", REPORTE)
print("No se confirmaron identidades automaticamente.")
print("MongoDB no fue modificado.")
cliente.close()
