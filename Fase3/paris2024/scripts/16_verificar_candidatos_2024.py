import csv
import re
from collections import Counter
from pathlib import Path
from pymongo import MongoClient
BASE = Path(__file__).resolve().parents[1] / "evidencias"
ENTRADA = BASE / "candidatos_fuertes_2024.csv"
SALIDA = BASE / "verificacion_candidatos_2024.csv"
cliente = MongoClient(
    "mongodb://127.0.0.1:27017/?directConnection=true",
    serverSelectionTimeoutMS=5000
)
cliente.admin.command("ping")
db = cliente["olimpiadas_mongo"]
with ENTRADA.open(encoding="utf-8-sig", newline="") as f:
    filas = list(csv.DictReader(f))
if len(filas) != 41:
    raise SystemExit(
        f"Se esperaban 41 candidatos; encontrados: {len(filas)}"
    )
salida = []
estados = Counter()
for fila in filas:
    sugerencia = fila["sugerencias"].split(" | ")[0]
    dep = re.search(r"\bdep=(\d+)", sugerencia)
    disc = re.search(r"\bdisc=(\d+)", sugerencia)
    ev = re.search(r"\bevento=(\d+)", sugerencia)
    motivos = []
    dep_id = disc_id = evento_id = None
    nombre_evento = ""
    if not all([dep, disc, ev]):
        motivos.append("No se pudieron extraer los tres IDs")
    else:
        dep_id = int(dep.group(1))
        disc_id = int(disc.group(1))
        evento_id = int(ev.group(1))
        deporte = db.catalogos.find_one({
            "_id": f"deporte:{dep_id}"
        })
        disciplina = db.catalogos.find_one({
            "_id": f"disciplina:{disc_id}"
        })
        evento = db.catalogos.find_one({
            "_id": f"evento:{evento_id}"
        })
        if not deporte:
            motivos.append("Deporte no encontrado")
        if not disciplina:
            motivos.append("Disciplina no encontrada")
        if not evento:
            motivos.append("Evento no encontrado")
        if evento:
            nombre_evento = evento.get("nombre", "")
            if evento.get("deporteId") != dep_id:
                motivos.append("Deporte incompatible con evento")
            if evento.get("disciplinaId") != disc_id:
                motivos.append("Disciplina incompatible con evento")
        if disciplina:
            if (
                "deporteId" in disciplina
                and disciplina["deporteId"] != dep_id
            ):
                motivos.append("Disciplina incompatible con deporte")
    estado = (
        "ESTRUCTURA_COHERENTE"
        if not motivos
        else "REVISAR_CATALOGO"
    )
    estados[estado] += 1
    salida.append({
        "sport_2024": fila["sport_2024"],
        "evento_2024": fila["evento_2024"],
        "participaciones": fila["participaciones"],
        "id_deporte_sugerido": dep_id,
        "id_disciplina_sugerido": disc_id,
        "id_evento_sugerido": evento_id,
        "nombre_evento_historico": nombre_evento,
        "estado_verificacion": estado,
        "detalle": "; ".join(motivos),
        "decision_manual": "PENDIENTE",
    })
campos = list(salida[0].keys())
with SALIDA.open("w", encoding="utf-8-sig", newline="") as f:
    escritor = csv.DictWriter(f, fieldnames=campos)
    escritor.writeheader()
    escritor.writerows(salida)
print("\n=== VERIFICACION CANDIDATOS PARIS 2024 ===")
print("Candidatos evaluados:", len(salida))
for estado, total in estados.items():
    print(f"{estado}: {total}")
print("\nPRIMEROS 10 RESULTADOS:\n")
for fila in salida[:10]:
    print(
        f"{fila['sport_2024']} / {fila['evento_2024']}"
    )
    print(
        f"  Evento historico: "
        f"{fila['nombre_evento_historico']}"
    )
    print(
        f"  IDs: deporte={fila['id_deporte_sugerido']}, "
        f"disciplina={fila['id_disciplina_sugerido']}, "
        f"evento={fila['id_evento_sugerido']}"
    )
    print(f"  Estado: {fila['estado_verificacion']}")
    if fila["detalle"]:
        print(f"  Detalle: {fila['detalle']}")
    print()
print("Archivo generado:", SALIDA)
print("Ningun mapeo fue confirmado automaticamente.")
print("MongoDB no fue modificado.")
cliente.close()
