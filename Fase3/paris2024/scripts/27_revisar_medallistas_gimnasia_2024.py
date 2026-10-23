import csv
import json
from collections import Counter
from pathlib import Path
BASE = Path(__file__).resolve().parents[1] / "evidencias"
ENTRADA = BASE / "lote_gimnasia_2024_preparado.jsonl"
SALIDA = BASE / "revision_medallistas_gimnasia_2024.csv"
documentos = [
    json.loads(linea)
    for linea in ENTRADA.read_text(encoding="utf-8").splitlines()
    if linea.strip()
]
assert len(documentos) == 410
medallistas = []
conteos = Counter()
for doc in documentos:
    codigo = doc["resultadoFuente"]["codigoMedalla"]
    if codigo is None:
        continue
    atleta = doc["atletaFuente"]
    identidad = doc["identidad"]
    fuente = doc["fuente"]
    conteos[codigo] += 1
    medallistas.append({
        "player_id_2024": fuente["playerIdOriginal"],
        "nombre_2024": atleta["nombre"],
        "noc": atleta["noc"],
        "evento_2024": fuente["eventoOriginal"],
        "medalla": codigo,
        "id_historico_candidato":
            identidad["idHistoricoCandidato"] or "",
        "estado_identidad": identidad["estado"],
        "identidad_confirmada": "NO",
        "evento_confirmado": "NO",
        "posicion_confirmada": "NO",
        "decision_manual": "PENDIENTE",
        "fuente_verificacion": "",
    })
medallistas.sort(key=lambda f: (
    f["evento_2024"],
    {"ORO": 0, "PLATA": 1, "BRONCE": 2}[f["medalla"]]
))
assert len(medallistas) == 16, (
    f"Se esperaban 16 filas con medalla; "
    f"encontradas: {len(medallistas)}"
)
with SALIDA.open(
    "w", encoding="utf-8-sig", newline=""
) as archivo:
    escritor = csv.DictWriter(
        archivo, fieldnames=list(medallistas[0].keys())
    )
    escritor.writeheader()
    escritor.writerows(medallistas)
print("\n=== MEDALLISTAS GIMNASIA PARIS 2024 ===")
print("Participaciones del lote:", len(documentos))
print("Filas con medalla:", len(medallistas))
print("Distribucion:", dict(conteos))
print("\nMEDALLISTAS POR EVENTO:")
for fila in medallistas:
    print(
        f"{fila['evento_2024']} | "
        f"{fila['medalla']} | "
        f"{fila['nombre_2024']} ({fila['noc']}) | "
        f"ID candidato: "
        f"{fila['id_historico_candidato'] or '-'} | "
        f"{fila['estado_identidad']}"
    )
print("\nArchivo:", SALIDA)
print("No se confirmaron identidades ni medallas.")
print("MongoDB no fue modificado.")
