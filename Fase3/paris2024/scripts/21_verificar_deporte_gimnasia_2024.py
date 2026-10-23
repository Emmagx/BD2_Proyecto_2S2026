import csv
from collections import Counter, defaultdict
from pathlib import Path
from pymongo import MongoClient
BASE = Path(__file__).resolve().parents[1] / "evidencias"
ENTRADA = BASE / "variantes_nombres_gimnasia_2024.csv"
SALIDA = BASE / "revision_deporte_identidades_gimnasia_2024.csv"
with ENTRADA.open(encoding="utf-8-sig", newline="") as f:
    filas = list(csv.DictReader(f))
assert len(filas) == 134
ids = {
    int(f["id_sugerido_1"])
    for f in filas if f["id_sugerido_1"].strip()
}
cliente = MongoClient(
    "mongodb://127.0.0.1:27017/?directConnection=true",
    serverSelectionTimeoutMS=5000
)
cliente.admin.command("ping")
db = cliente["olimpiadas_mongo"]
deportes = defaultdict(set)
anios = defaultdict(set)
for r in db.resultados.find(
    {
        "atletas.id": {"$in": list(ids)},
        "edicion.anio": {"$lt": 2024}
    },
    {"atletas.id": 1, "deporte.nombre": 1, "edicion.anio": 1}
):
    for a in r.get("atletas", []):
        aid = a.get("id")
        if aid in ids:
            deportes[aid].add(r["deporte"]["nombre"])
            anios[aid].add(r["edicion"]["anio"])
conteos = Counter()
salida = []
for fila in filas:
    valor = fila["id_sugerido_1"].strip()
    aid = int(valor) if valor else None
    deportes_h = sorted(deportes.get(aid, set()))
    anios_h = sorted(anios.get(aid, set()))
    if aid is None:
        estado = "SIN_CANDIDATO"
    elif any("Artistic Gymnastics" in d for d in deportes_h):
        estado = "MISMO_DEPORTE_REVISAR_IDENTIDAD"
    elif deportes_h:
        estado = "DEPORTE_DIFERENTE_NO_VINCULAR"
    else:
        estado = "SIN_PARTICIPACION_HISTORICA"
    conteos[estado] += 1
    salida.append({
        **fila,
        "deportes_historicos": " | ".join(deportes_h),
        "anios_historicos": " | ".join(map(str, anios_h)),
        "estado_revision_deporte": estado,
        "identidad_confirmada": "NO",
    })
with SALIDA.open("w", encoding="utf-8-sig", newline="") as f:
    escritor = csv.DictWriter(f, fieldnames=list(salida[0].keys()))
    escritor.writeheader()
    escritor.writerows(salida)
print("\n=== REVISION DE DEPORTE - GIMNASIA 2024 ===")
print("Atletas pendientes:", len(filas))
for estado, cantidad in conteos.most_common():
    print(f"{estado}: {cantidad}")
print("\nCASOS DE SIMILITUD ALTA:")
for f in salida:
    if f["estado_busqueda"] == "SIMILITUD_ALTA_REVISAR":
        print(
            f["nombre_2024"],
            "->", f["nombre_sugerido_1"],
            "|", f["estado_revision_deporte"],
            "|", f["deportes_historicos"] or "-"
        )
print("\nArchivo:", SALIDA)
print("No se confirmaron identidades automaticamente.")
print("MongoDB no fue modificado.")
cliente.close()
