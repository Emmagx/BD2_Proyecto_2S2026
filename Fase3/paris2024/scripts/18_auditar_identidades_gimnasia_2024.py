import csv
import json
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from pymongo import MongoClient
BASE = Path(__file__).resolve().parents[1]
ENTRADA = BASE / "datos" / "olympics_dataset.csv"
SALIDA = BASE / "evidencias" / "identidades_gimnasia_2024.csv"
REPORTE = BASE / "evidencias" / "resumen_identidades_gimnasia_2024.json"
EVENTOS = {
    "Women's Balance Beam",
    "Women's Floor Exercise",
    "Men's Horizontal Bar",
    "Men's Floor Exercise",
    "Men's Rings",
}
def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )
    return " ".join(texto.casefold().split())
# 1. Leer las participaciones de gimnasia.
filas = []
with ENTRADA.open(encoding="utf-8-sig", newline="") as f:
    for fila in csv.DictReader(f):
        if (
            fila["Year"].strip() == "2024"
            and fila["Season"].strip() == "Summer"
            and fila["Sport"].strip() == "Artistic Gymnastics"
            and fila["Event"].strip() in EVENTOS
        ):
            filas.append(fila)
assert len(filas) == 410, (
    f"Se esperaban 410 filas, hay {len(filas)}"
)
# 2. Agrupar participaciones por ID de origen.
por_atleta = defaultdict(list)
for fila in filas:
    por_atleta[fila["player_id"].strip()].append(fila)
# 3. Buscar nombres candidatos en MongoDB.
cliente = MongoClient(
    "mongodb://127.0.0.1:27017/?directConnection=true",
    serverSelectionTimeoutMS=5000
)
cliente.admin.command("ping")
db = cliente["olimpiadas_mongo"]
nombres_origen = {
    normalizar(fila["Name"]) for fila in filas
}
candidatos = defaultdict(list)
for atleta in db.atletas.find(
    {},
    {"_id": 1, "nombre": 1}
):
    clave = normalizar(atleta.get("nombre", ""))
    if clave in nombres_origen:
        candidatos[clave].append({
            "id": atleta["_id"],
            "nombre": atleta.get("nombre", "")
        })
# 4. Generar auditoria, sin confirmar identidades.
salida = []
conteos = Counter()
for player_id, participaciones in sorted(por_atleta.items()):
    nombres = {f["Name"].strip() for f in participaciones}
    nocs = {f["NOC"].strip() for f in participaciones}
    sexos = {f["Sex"].strip() for f in participaciones}
    nombre = participaciones[0]["Name"].strip()
    coincidencias = candidatos.get(normalizar(nombre), [])
    if len(nombres) != 1 or len(nocs) != 1 or len(sexos) != 1:
        estado = "DATOS_FUENTE_INCONSISTENTES"
    elif len(coincidencias) == 1:
        estado = "CANDIDATO_POR_NOMBRE"
    elif len(coincidencias) > 1:
        estado = "NOMBRE_AMBIGUO"
    else:
        estado = "SIN_COINCIDENCIA_NOMBRE"
    conteos[estado] += 1
    salida.append({
        "player_id_2024": player_id,
        "nombre_2024": nombre,
        "noc_2024": ",".join(sorted(nocs)),
        "sexo_2024": ",".join(sorted(sexos)),
        "cantidad_eventos": len(participaciones),
        "eventos": " | ".join(sorted({
            f["Event"] for f in participaciones
        })),
        "estado_identidad": estado,
        "ids_historicos_candidatos": "|".join(
            str(c["id"]) for c in coincidencias
        ),
        "nombres_historicos_candidatos": "|".join(
            c["nombre"] for c in coincidencias
        ),
        "id_historico_confirmado": "",
        "observaciones": "",
    })
campos = list(salida[0].keys())
with SALIDA.open(
    "w", encoding="utf-8-sig", newline=""
) as f:
    escritor = csv.DictWriter(f, fieldnames=campos)
    escritor.writeheader()
    escritor.writerows(salida)
reporte = {
    "participaciones": len(filas),
    "atletas_fuente_distintos": len(por_atleta),
    "estados": dict(conteos),
    "identidades_confirmadas_automaticamente": 0,
    "mongo_modificado": False
}
REPORTE.write_text(
    json.dumps(reporte, indent=2, ensure_ascii=False),
    encoding="utf-8"
)
print("\n=== IDENTIDADES GIMNASIA PARIS 2024 ===")
print("Participaciones:", len(filas))
print("Atletas de origen distintos:", len(por_atleta))
print("\nCLASIFICACION:")
for estado, cantidad in conteos.most_common():
    print(f"  {estado}: {cantidad}")
print("\nPRIMEROS 10 ATLETAS:")
for fila in salida[:10]:
    print(
        fila["nombre_2024"],
        "| NOC:", fila["noc_2024"],
        "| eventos:", fila["cantidad_eventos"],
        "| estado:", fila["estado_identidad"],
        "| candidatos:", fila["ids_historicos_candidatos"] or "-"
    )
print("\nArchivo:", SALIDA)
print("Reporte:", REPORTE)
print("Ninguna identidad fue confirmada automaticamente.")
print("MongoDB no fue modificado.")
cliente.close()
