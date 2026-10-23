import csv
from collections import Counter
from pathlib import Path
BASE = Path(__file__).resolve().parents[1] / "evidencias"
ENTRADA = BASE / "decisiones_identidades_gimnasia_2024.csv"
IDENTIDADES = BASE / "identidades_gimnasia_2024.csv"
SALIDA = BASE / "lote_revision_identidades_gimnasia_2024.csv"
def leer(ruta):
    with ruta.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))
decisiones = leer(ENTRADA)
identidades = leer(IDENTIDADES)
assert len(decisiones) == 65
assert len(identidades) == 178
eventos_por_id = {
    f["player_id_2024"]: int(f["cantidad_eventos"])
    for f in identidades
}
prioridad = {
    "NOMBRE_EQUIVALENTE_REVISAR": 1,
    "ORDEN_INVERTIDO_REVISAR": 2,
    "VARIANTE_MUY_SIMILAR_REVISAR": 3,
    "RIESGO_IDENTIDAD_DIFERENTE": 4,
    "CONFLICTO_ID_COMPARTIDO": 5,
}
salida = []
for fila in decisiones:
    estado = fila["estado_auditoria_final"]
    decision = fila["decision_identidad"]
    pid = fila["player_id_2024"]
    if decision == "VINCULACION_DESCARTADA":
        clasificacion = "BLOQUEADO"
    elif decision == "VARIANTE_DOCUMENTADA_REVISAR_ID":
        clasificacion = "REVISAR_IDENTIDAD_DOCUMENTADA"
    elif estado == "NOMBRE_EQUIVALENTE_REVISAR":
        clasificacion = "PRIORIDAD_ALTA"
    elif estado in (
        "ORDEN_INVERTIDO_REVISAR",
        "VARIANTE_MUY_SIMILAR_REVISAR"
    ):
        clasificacion = "REVISAR_VARIANTE"
    else:
        clasificacion = "REVISION_MANUAL_OBLIGATORIA"
    salida.append({
        "player_id_2024": pid,
        "nombre_2024": fila["nombre_2024"],
        "noc_2024": fila["noc_2024"],
        "id_historico_propuesto": fila["id_historico_propuesto"],
        "nombre_historico": fila["nombre_historico"],
        "participaciones_2024": eventos_por_id[pid],
        "tipo_coincidencia": fila["tipo_coincidencia"],
        "estado_auditoria": estado,
        "decision_previa": decision,
        "clasificacion": clasificacion,
        "decision_final": "PENDIENTE",
        "id_historico_aprobado": "",
        "evidencia": "",
    })
salida.sort(key=lambda f: (
    f["clasificacion"] != "PRIORIDAD_ALTA",
    prioridad.get(f["estado_auditoria"], 99),
    -f["participaciones_2024"],
    f["nombre_2024"]
))
with SALIDA.open("w", encoding="utf-8-sig", newline="") as f:
    escritor = csv.DictWriter(
        f, fieldnames=list(salida[0].keys())
    )
    escritor.writeheader()
    escritor.writerows(salida)
conteos = Counter(f["clasificacion"] for f in salida)
print("\n=== LOTE DE REVISION GIMNASIA 2024 ===")
print("Candidatos:", len(salida))
for estado, cantidad in conteos.most_common():
    print(f"{estado}: {cantidad}")
print("\nPRIMEROS 15 PARA REVISION:")
for fila in salida[:15]:
    print(
        fila["nombre_2024"],
        "->", fila["nombre_historico"],
        "| ID:", fila["id_historico_propuesto"],
        "| eventos:", fila["participaciones_2024"],
        "|", fila["clasificacion"]
    )
print("\nArchivo:", SALIDA)
print("Ningun ID fue aprobado automaticamente.")
print("MongoDB no fue modificado.")
