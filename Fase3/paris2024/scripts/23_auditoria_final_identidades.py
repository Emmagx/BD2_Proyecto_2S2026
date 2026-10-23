import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
BASE = Path(__file__).resolve().parents[1] / "evidencias"
ENTRADA = BASE / "consolidado_identidades_gimnasia_2024.csv"
SALIDA = BASE / "auditoria_final_identidades_gimnasia_2024.csv"
REPORTE = BASE / "auditoria_final_identidades_gimnasia_2024.json"
def normalizar(valor):
    valor = unicodedata.normalize("NFKD", valor or "")
    valor = "".join(
        c for c in valor if not unicodedata.combining(c)
    )
    valor = valor.casefold()
    valor = re.sub(r"[^a-z0-9 ]", " ", valor)
    return " ".join(valor.split())
def evaluar_nombres(a, b):
    x = normalizar(a)
    y = normalizar(b)
    exacto = x == y
    tokens_x = x.split()
    tokens_y = y.split()
    invertido = sorted(tokens_x) == sorted(tokens_y)
    similitud = max(
        SequenceMatcher(None, x, y).ratio(),
        SequenceMatcher(
            None,
            " ".join(sorted(tokens_x)),
            " ".join(sorted(tokens_y))
        ).ratio()
    )
    return exacto, invertido, round(similitud, 3)
with ENTRADA.open(encoding="utf-8-sig", newline="") as f:
    filas = list(csv.DictReader(f))
assert len(filas) == 65
usos = defaultdict(list)
for fila in filas:
    usos[fila["id_historico_propuesto"]].append(
        fila["player_id_2024"]
    )
salida = []
conteos = Counter()
for fila in filas:
    nombre_2024 = fila["nombre_2024"]
    nombre_h = fila["nombre_historico"]
    aid = fila["id_historico_propuesto"]
    exacto, invertido, similitud = evaluar_nombres(
        nombre_2024, nombre_h
    )
    if len(usos[aid]) > 1:
        estado = "CONFLICTO_ID_COMPARTIDO"
    elif exacto:
        estado = "NOMBRE_EQUIVALENTE_REVISAR"
    elif invertido:
        estado = "ORDEN_INVERTIDO_REVISAR"
    elif similitud >= 0.90:
        estado = "VARIANTE_MUY_SIMILAR_REVISAR"
    else:
        estado = "RIESGO_IDENTIDAD_DIFERENTE"
    conteos[estado] += 1
    salida.append({
        **fila,
        "similitud_recalculada": similitud,
        "nombre_normalizado_2024": normalizar(nombre_2024),
        "nombre_normalizado_historico": normalizar(nombre_h),
        "estado_auditoria_final": estado,
        "confirmacion_definitiva": "PENDIENTE",
        "fuente_verificacion": "",
    })
salida.sort(
    key=lambda f: (
        f["estado_auditoria_final"],
        f["nombre_2024"]
    )
)
with SALIDA.open(
    "w", encoding="utf-8-sig", newline=""
) as f:
    escritor = csv.DictWriter(
        f, fieldnames=list(salida[0].keys())
    )
    escritor.writeheader()
    escritor.writerows(salida)
reporte = {
    "candidatos": len(salida),
    "estados": dict(conteos),
    "identidades_confirmadas": 0,
    "mongo_modificado": False
}
REPORTE.write_text(
    json.dumps(reporte, indent=2, ensure_ascii=False),
    encoding="utf-8"
)
print("\n=== AUDITORIA FINAL DE IDENTIDADES ===")
print("Candidatos analizados:", len(salida))
for estado, cantidad in conteos.most_common():
    print(f"{estado}: {cantidad}")
print("\nCASOS PRIORITARIOS PARA INVESTIGAR:")
for fila in salida:
    if fila["estado_auditoria_final"] in (
        "RIESGO_IDENTIDAD_DIFERENTE",
        "CONFLICTO_ID_COMPARTIDO"
    ):
        print(
            fila["nombre_2024"],
            "->", fila["nombre_historico"],
            "| ID:", fila["id_historico_propuesto"],
            "| estado:", fila["estado_auditoria_final"]
        )
print("\nArchivo:", SALIDA)
print("Reporte:", REPORTE)
print("Ninguna identidad confirmada automaticamente.")
print("MongoDB no fue modificado.")
