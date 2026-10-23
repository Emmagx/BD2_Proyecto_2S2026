import csv
import difflib
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from pymongo import MongoClient
BASE = Path(__file__).resolve().parents[1] / "evidencias"
ENTRADA = BASE / "revision_identidades_gimnasia_2024.csv"
SALIDA = BASE / "variantes_nombres_gimnasia_2024.csv"
def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(
        c for c in texto if not unicodedata.combining(c)
    )
    texto = re.sub(r"[^a-z0-9 ]", " ", texto.casefold())
    return " ".join(texto.split())
def similitud(a, b):
    a, b = normalizar(a), normalizar(b)
    directa = difflib.SequenceMatcher(None, a, b).ratio()
    tokens_a = " ".join(sorted(a.split()))
    tokens_b = " ".join(sorted(b.split()))
    invertida = difflib.SequenceMatcher(
        None, tokens_a, tokens_b
    ).ratio()
    return max(directa, invertida)
with ENTRADA.open(encoding="utf-8-sig", newline="") as f:
    filas = list(csv.DictReader(f))
pendientes = [
    f for f in filas
    if f["resultado_revision"] != "CANDIDATO_COMPATIBLE"
]
assert len(filas) == 178
assert len(pendientes) == 134
nocs_objetivo = {
    f["noc_2024"] for f in pendientes
}
cliente = MongoClient(
    "mongodb://127.0.0.1:27017/?directConnection=true",
    serverSelectionTimeoutMS=5000
)
cliente.admin.command("ping")
db = cliente["olimpiadas_mongo"]
# Recuperar los IDs historicos asociados a cada NOC.
ids_por_noc = defaultdict(set)
for r in db.resultados.find(
    {"edicion.anio": {"$lt": 2024}},
    {"atletas.id": 1, "atletas.noc": 1}
):
    for atleta in r.get("atletas", []):
        noc = atleta.get("noc")
        aid = atleta.get("id")
        if noc in nocs_objetivo and isinstance(aid, int):
            ids_por_noc[noc].add(aid)
# Consultar perfiles historicos por lotes.
perfiles_por_noc = defaultdict(list)
for noc, ids in ids_por_noc.items():
    lista = sorted(ids)
    for inicio in range(0, len(lista), 1000):
        lote = lista[inicio:inicio + 1000]
        for atleta in db.atletas.find(
            {"_id": {"$in": lote}},
            {"_id": 1, "nombre": 1, "sexo": 1}
        ):
            perfiles_por_noc[noc].append(atleta)
salida = []
conteos = Counter()
for fila in pendientes:
    nombre = fila["nombre_2024"]
    noc = fila["noc_2024"]
    sexo = fila["sexo_2024"].strip().upper()
    sugerencias = []
    for perfil in perfiles_por_noc.get(noc, []):
        sexo_h = str(perfil.get("sexo") or "").upper()
        if sexo_h in ("M", "F") and sexo_h != sexo:
            continue
        puntuacion = similitud(nombre, perfil.get("nombre", ""))
        if puntuacion >= 0.70:
            sugerencias.append((
                puntuacion,
                perfil["_id"],
                perfil.get("nombre", "")
            ))
    sugerencias.sort(key=lambda x: (-x[0], x[1]))
    mejores = sugerencias[:3]
    if mejores and mejores[0][0] >= 0.90:
        estado = "SIMILITUD_ALTA_REVISAR"
    elif mejores:
        estado = "SIMILITUD_MEDIA_REVISAR"
    else:
        estado = "SIN_VARIANTE_DETECTADA"
    conteos[estado] += 1
    registro = {
        "player_id_2024": fila["player_id_2024"],
        "nombre_2024": nombre,
        "noc_2024": noc,
        "sexo_2024": sexo,
        "estado_original": fila["resultado_revision"],
        "estado_busqueda": estado,
        "id_sugerido_1": mejores[0][1] if mejores else "",
        "nombre_sugerido_1": mejores[0][2] if mejores else "",
        "similitud_1": round(mejores[0][0], 3) if mejores else "",
        "otras_sugerencias": " | ".join(
            f"{aid}: {n} ({p:.3f})"
            for p, aid, n in mejores[1:]
        ),
        "decision_manual": "PENDIENTE",
    }
    salida.append(registro)
with SALIDA.open("w", encoding="utf-8-sig", newline="") as f:
    escritor = csv.DictWriter(
        f, fieldnames=list(salida[0].keys())
    )
    escritor.writeheader()
    escritor.writerows(salida)
print("\n=== VARIANTES DE NOMBRES - PARIS 2024 ===")
print("Atletas pendientes evaluados:", len(salida))
for estado, cantidad in conteos.most_common():
    print(f"{estado}: {cantidad}")
print("\nPRIMERAS 15 SUGERENCIAS:")
for fila in [
    f for f in salida if f["id_sugerido_1"]
][:15]:
    print(
        f"{fila['nombre_2024']} ({fila['noc_2024']})"
        f" -> {fila['nombre_sugerido_1']}"
        f" [ID {fila['id_sugerido_1']}]"
        f" similitud={fila['similitud_1']}"
    )
print("\nArchivo generado:", SALIDA)
print("No se confirmaron identidades automaticamente.")
print("MongoDB no fue modificado.")
cliente.close()
