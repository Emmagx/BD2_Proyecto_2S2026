import csv
import re
import unicodedata
from collections import defaultdict, Counter
from pathlib import Path
from pymongo import MongoClient
BASE = Path("paris2024/evidencias")
ENTRADA = BASE / "mapa_general_eventos_2024.csv"
SALIDA = BASE / "mapa_eventos_mejorado_2024.csv"
def normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(
        c for c in texto if not unicodedata.combining(c)
    ).lower()
    texto = texto.replace("women's", "women")
    texto = texto.replace("men's", "men")
    texto = texto.replace("metres", "m")
    texto = texto.replace("meters", "m")
    texto = texto.replace("×", "x")
    texto = re.sub(r"\bolympic\b", "", texto)
    texto = re.sub(r"(\d+)\s*m\b", r"\1m", texto)
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split())
def clave(texto):
    return tuple(sorted(normalizar(texto).split()))
c = MongoClient(
    "mongodb://127.0.0.1:27017/?directConnection=true"
)
db = c["olimpiadas_mongo"]
deportes = {
    d["id"]: d["nombre"]
    for d in db.catalogos.find({"tipo": "deporte"})
}
eventos = list(db.catalogos.find({"tipo": "evento"}))
indice = defaultdict(list)
for e in eventos:
    did = e["deporteId"]
    deporte = deportes.get(did, "").split("(")[0].strip()
    indice[normalizar(deporte)].append(e)
with ENTRADA.open(encoding="utf-8-sig", newline="") as f:
    filas = list(csv.DictReader(f))
assert len(filas) == 361
conteo = Counter()
participaciones = Counter()
salida = []
for fila in filas:
    deporte = fila["deporte_2024"]
    evento = fila["evento_2024"]
    cantidad = int(fila["participaciones"])
    candidatos = indice.get(normalizar(deporte), [])
    coincidencias = []
    for e in candidatos:
        nombre = e["nombre"]
        # Comparar nombre directo.
        coincide = clave(evento) == clave(nombre)
        # Algunos eventos historicos incluyen
        # el nombre del deporte en el evento.
        coincide_con_deporte = (
            clave(deporte + " " + evento) == clave(nombre)
        )
        if coincide or coincide_con_deporte:
            coincidencias.append(e)
    ids = {e["id"] for e in coincidencias}
    if len(ids) == 1:
        estado = "MAPEO_EXACTO_CANDIDATO"
        elegido = coincidencias[0]
        eid = elegido["id"]
        nombre = elegido["nombre"]
    elif len(ids) > 1:
        estado = "MAPEO_AMBIGUO"
        eid = ""
        nombre = ""
    else:
        estado = "MAPEO_PENDIENTE"
        eid = ""
        nombre = ""
    conteo[estado] += 1
    participaciones[estado] += cantidad
    salida.append({
        "deporte_2024": deporte,
        "evento_2024": evento,
        "participaciones": cantidad,
        "estado": estado,
        "evento_id_candidato": eid,
        "evento_historico": nombre,
        "validado_manualmente": "NO"
    })
campos = list(salida[0].keys())
with SALIDA.open(
    "w", encoding="utf-8-sig", newline=""
) as f:
    escritor = csv.DictWriter(f, fieldnames=campos)
    escritor.writeheader()
    escritor.writerows(salida)
print("\n=== MAPEO MEJORADO PARIS 2024 ===")
for estado, cantidad in conteo.items():
    print(
        estado,
        "| eventos:", cantidad,
        "| participaciones:", participaciones[estado]
    )
print("\n=== EJEMPLOS DE CORRESPONDENCIA ===")
ejemplos = [
    ("Football", "Men"),
    ("Football", "Women"),
    ("Hockey", "Men"),
    ("Athletics", "Men's 100m"),
    ("Artistic Gymnastics", "Women's Uneven Bars")
]
for deporte, evento in ejemplos:
    encontrado = next(
        (x for x in salida
         if x["deporte_2024"] == deporte
         and x["evento_2024"] == evento),
        None
    )
    if encontrado:
        print(
            deporte, "|", evento,
            "->", encontrado["evento_historico"],
            "| ID:", encontrado["evento_id_candidato"],
            "|", encontrado["estado"]
        )
print("\nArchivo:", SALIDA)
print("MongoDB no fue modificado.")
c.close()
