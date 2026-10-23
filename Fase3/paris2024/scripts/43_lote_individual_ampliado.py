import json
from collections import Counter
from pathlib import Path
BASE = Path("paris2024") / "evidencias"
ENTRADA = BASE / "lote_multideporte_2024.jsonl"
SALIDA = BASE / "lote_individual_ampliado_2024.jsonl"
REPORTE = BASE / "reporte_individual_ampliado_2024.json"
filas = [
    json.loads(linea)
    for linea in ENTRADA.read_text(
        encoding="utf-8"
    ).splitlines()
    if linea.strip()
]
assert len(filas) == 709
# Deportes cuyas pruebas del lote son individuales,
# sujetos a las exclusiones de modalidad de abajo.
INDIVIDUALES = {
    "Athletics",
    "Fencing",
    "Table Tennis",
    "Tennis",
    "Shooting",
    "Archery",
    "Badminton",
    "Modern Pentathlon",
    "Artistic Gymnastics",
    "Cycling Track",
    "Cycling Mountain Bike",
    "Cycling Road",
    "Cycling BMX Freestyle",
    "Skateboarding",
}
def deporte_fuente(doc):
    return doc["deporte"]["nombre"].split("(")[0].strip()
def clasificar(doc):
    deporte = deporte_fuente(doc)
    evento = doc["eventoOriginal"].lower()
    # Excluir pruebas con varios integrantes.
    excluidas = (
        "team", "relay", "mixed", "doubles",
        "double sculls", "quadruple",
        "pair", "four", "eight",
        "madison", "synchron",
        "skiff", "crew"
    )
    if any(p in evento for p in excluidas):
        return "REVISION_EQUIPO"
    requisitos = {
        "Table Tennis": ("singles",),
        "Tennis": ("singles",),
        "Badminton": ("singles",),
        "Archery": ("individual",),
        "Fencing": ("individual",),
    }
    if deporte in requisitos:
        if not any(p in evento for p in requisitos[deporte]):
            return "REVISION_MODALIDAD"
    if deporte == "Rowing":
        if "single sculls" in evento:
            return "INDIVIDUAL"
        return "REVISION_EQUIPO"
    if deporte == "Sailing":
        return "REVISION_MODALIDAD"
    if deporte in INDIVIDUALES:
        return "INDIVIDUAL"
    return "REVISION_DEPORTE"
aprobables = []
revisar = []
conteos = Counter()
por_deporte = Counter()
for doc in filas:
    estado = clasificar(doc)
    conteos[estado] += 1
    if estado == "INDIVIDUAL":
        aprobables.append(doc)
        por_deporte[deporte_fuente(doc)] += 1
    else:
        revisar.append({
            "stagingId": doc["stagingId"],
            "deporte": deporte_fuente(doc),
            "evento": doc["eventoOriginal"],
            "motivo": estado
        })
# Comprobar que el lote es consistente.
assert len(aprobables) + len(revisar) == 709
claves = [
    (d["evento"]["id"], d["atletaId"])
    for d in aprobables
]
assert len(claves) == len(set(claves))
ids_origen = [d["stagingId"] for d in aprobables]
assert len(ids_origen) == len(set(ids_origen))
assert all(
    d["medalla"] is None
    and d["posicion"] is None
    and d["revisar"] is True
    for d in aprobables
)
# Verificar coherencia de identificadores historicos.
por_atleta = {}
for d in aprobables:
    aid = d["atletaId"]
    pid = str(d["playerIdOriginal"])
    if aid in por_atleta:
        assert por_atleta[aid] == pid, (
            f"Identidad compartida: {aid}"
        )
    else:
        por_atleta[aid] = pid
with SALIDA.open("w", encoding="utf-8") as f:
    for d in aprobables:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")
reporte = {
    "lote_original": 709,
    "individuales_preparadas": len(aprobables),
    "revisar": len(revisar),
    "clasificacion": dict(conteos),
    "por_deporte": dict(por_deporte),
    "pendientes": revisar,
    "mongo_modificado": False
}
REPORTE.write_text(
    json.dumps(reporte, ensure_ascii=False, indent=2),
    encoding="utf-8"
)
print("\n=== LOTE INDIVIDUAL AMPLIADO ===")
print("Lote original:", len(filas))
print("Individuales preparadas:", len(aprobables))
print("Pendientes de revision:", len(revisar))
print("Atletas distintos:", len(por_atleta))
print("Deportes incluidos:", len(por_deporte))
print("\n=== CLASIFICACION ===")
for estado, cantidad in conteos.most_common():
    print(estado, cantidad)
print("\n=== DEPORTES ===")
for deporte, cantidad in por_deporte.most_common():
    print(deporte, cantidad)
print("\nArchivo:", SALIDA)
print("Reporte:", REPORTE)
print("MongoDB no fue modificado.")
