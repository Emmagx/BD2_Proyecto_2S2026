import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from pymongo import MongoClient, UpdateOne
BASE = Path(__file__).resolve().parents[1]
CSV = BASE / "datos" / "olympics_dataset.csv"
EVID = BASE / "evidencias"
REPORTE = EVID / "carga_masiva_paris2024.json"
parser = argparse.ArgumentParser()
parser.add_argument("--aplicar", action="store_true")
args = parser.parse_args()
assert CSV.is_file(), f"No existe el CSV: {CSV}"
EVID.mkdir(parents=True, exist_ok=True)
# Identificador de version para impedir mezclar archivos
# diferentes en una misma coleccion de preparacion.
hash_archivo = hashlib.sha256(CSV.read_bytes()).hexdigest()
documentos = []
deportes = Counter()
eventos = Counter()
medallas = Counter()
nocs = set()
jugadores = set()
campos_necesarios = {
    "Year", "Season", "Sport", "Event",
    "player_id", "Name", "Sex", "NOC", "Medal"
}
with CSV.open(encoding="utf-8-sig", newline="") as f:
    lector = csv.DictReader(f)
    assert campos_necesarios.issubset(
        set(lector.fieldnames or [])
    ), "Faltan columnas requeridas en el CSV"
    for numero_fila, fila in enumerate(lector, start=2):
        if (
            fila["Year"].strip() != "2024"
            or fila["Season"].strip() != "Summer"
        ):
            continue
        nombre = fila["Name"].strip()
        player_id = fila["player_id"].strip()
        noc = fila["NOC"].strip()
        deporte = fila["Sport"].strip()
        evento = fila["Event"].strip()
        medalla = fila["Medal"].strip()
        assert player_id, (
            f"Sin player_id en fila {numero_fila}"
        )
        assert nombre and noc and deporte and evento, (
            f"Datos incompletos en fila {numero_fila}"
        )
        assert medalla in (
            "Gold", "Silver", "Bronze", "No medal"
        ), f"Medalla desconocida: {medalla}"
        # El numero de fila preserva incluso registros
        # repetidos por jugador o equipos.
        identificador = f"paris2024:{numero_fila}"
        doc = {
            "_id": identificador,
            "origen": {
                "archivo": CSV.name,
                "sha256Archivo": hash_archivo,
                "filaCSV": numero_fila,
            },
            "edicion": {
                "anio": 2024,
                "temporada": "Summer",
                "id": 63,
            },
            "atletaFuente": {
                "playerId": player_id,
                "nombre": nombre,
                "sexo": fila["Sex"].strip(),
                "noc": noc,
            },
            "competenciaFuente": {
                "deporte": deporte,
                "evento": evento,
            },
            "medallaFuente": medalla,
            "filaOriginal": fila,
            "integracion": {
                "estado": "PENDIENTE_MAPEO",
                "resultadoId": None,
                "atletaId": None,
                "eventoId": None,
            },
        }
        documentos.append(doc)
        deportes[deporte] += 1
        eventos[(deporte, evento)] += 1
        medallas[medalla] += 1
        nocs.add(noc)
        jugadores.add(player_id)
assert len(documentos) == 14892, (
    f"Se esperaban 14892 filas: "
    f"encontradas {len(documentos)}"
)
assert len({
    d["_id"] for d in documentos
}) == len(documentos)
print("\n=== CARGA MASIVA PARIS 2024 ===")
print("Filas de la edicion:", len(documentos))
print("Atletas fuente distintos:", len(jugadores))
print("Deportes originales:", len(deportes))
print("Combinaciones deporte/evento:", len(eventos))
print("NOCs originales:", len(nocs))
print("Medallas en filas fuente:", dict(medallas))
print("\nDeportes con mas participaciones:")
for deporte, cantidad in deportes.most_common(15):
    print(f"  {deporte}: {cantidad}")
cliente = MongoClient(
    "mongodb://127.0.0.1:27017/?directConnection=true",
    serverSelectionTimeoutMS=5000
)
cliente.admin.command("ping")
db = cliente["olimpiadas_mongo"]
# Coleccion separada del modelo historico y definitivo.
coleccion = db["paris2024_fuente"]
# Comprobar la fuente antes de cualquier escritura.
otra_version = coleccion.find_one({
    "origen.sha256Archivo": {"$ne": hash_archivo}
}, {"_id": 1})
assert otra_version is None, (
    "La coleccion contiene otra version del CSV. "
    "No se mezclaran fuentes."
)
actualmente = coleccion.count_documents({})
print("\nFilas ya almacenadas en staging:", actualmente)
# El modelo definitivo permanece sin cambios.
resultados_2024 = db.resultados.count_documents({
    "edicion.anio": 2024
})
assert resultados_2024 == 115, (
    "La cantidad de resultados definitivos cambio. "
    "Revisar antes de continuar."
)
print("Resultados definitivos 2024:", resultados_2024)
if args.aplicar:
    print("\nIMPORTANDO A MONGODB...")
    coleccion.create_index(
        "atletaFuente.playerId"
    )
    coleccion.create_index(
        "atletaFuente.noc"
    )
    coleccion.create_index([
        ("competenciaFuente.deporte", 1),
        ("competenciaFuente.evento", 1),
    ])
    coleccion.create_index(
        "integracion.estado"
    )
    operaciones = []
    for doc in documentos:
        operaciones.append(
            UpdateOne(
                {"_id": doc["_id"]},
                {"$setOnInsert": doc},
                upsert=True
            )
        )
        if len(operaciones) == 1000:
            coleccion.bulk_write(
                operaciones, ordered=False
            )
            operaciones = []
    if operaciones:
        coleccion.bulk_write(
            operaciones, ordered=False
        )
    total = coleccion.count_documents({})
    assert total == 14892, (
        f"Conteo inesperado en staging: {total}"
    )
    # Comprobar que no se perdieron filas.
    ids_almacenados = {
        d["_id"]
        for d in coleccion.find({}, {"_id": 1})
    }
    assert ids_almacenados == {
        d["_id"] for d in documentos
    }
    assert db.resultados.count_documents({
        "edicion.anio": 2024
    }) == 115
    print("\n=== IMPORTACION MASIVA EXITOSA ===")
    print("Filas almacenadas:", total)
    print("Resultados definitivos conservados:", 115)
else:
    print("\n=== SIMULACION ===")
    print("Filas listas para importar:", len(documentos))
    print("MongoDB no fue modificado.")
reporte = {
    "modo": "APLICACION" if args.aplicar else "SIMULACION",
    "coleccion": "paris2024_fuente",
    "filas_fuente": len(documentos),
    "atletas_fuente": len(jugadores),
    "deportes": len(deportes),
    "combinaciones_deporte_evento": len(eventos),
    "nocs": len(nocs),
    "medallas_fuente": dict(medallas),
    "deportes_detalle": dict(deportes),
    "hash_fuente": hash_archivo,
    "resultados_definitivos_2024": 115,
}
REPORTE.write_text(
    json.dumps(reporte, ensure_ascii=False, indent=2),
    encoding="utf-8"
)
print("\nReporte:", REPORTE)
cliente.close()
