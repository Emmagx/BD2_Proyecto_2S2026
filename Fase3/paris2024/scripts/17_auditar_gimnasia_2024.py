import csv
import json
from collections import Counter
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
ENTRADA = BASE / "datos" / "olympics_dataset.csv"
SALIDA = BASE / "evidencias" / "auditoria_gimnasia_2024.json"
EVENTOS = {
    "Women's Balance Beam": 483,
    "Women's Floor Exercise": 480,
    "Men's Horizontal Bar": 493,
    "Men's Floor Exercise": 490,
    "Men's Rings": 494,
}
def buscar_columna(columnas, opciones):
    normalizadas = {
        c.lower().strip(): c for c in columnas
    }
    for opcion in opciones:
        if opcion.lower() in normalizadas:
            return normalizadas[opcion.lower()]
    return None
with ENTRADA.open(encoding="utf-8-sig", newline="") as f:
    lector = csv.DictReader(f)
    columnas = lector.fieldnames or []
    print("\n=== COLUMNAS DEL DATASET ===")
    print(columnas)
    col_anio = buscar_columna(
        columnas, ["Year", "year", "anio"]
    )
    col_temporada = buscar_columna(
        columnas, ["Season", "season"]
    )
    col_deporte = buscar_columna(
        columnas, ["Sport", "sport"]
    )
    col_evento = buscar_columna(
        columnas, ["Event", "event"]
    )
    col_medalla = buscar_columna(
        columnas, ["Medal", "medal"]
    )
    col_atleta = buscar_columna(
        columnas, ["Name", "name", "Player", "player_name"]
    )
    col_id = buscar_columna(
        columnas, ["player_id", "Player_ID", "ID", "id"]
    )
    col_noc = buscar_columna(
        columnas, ["NOC", "noc", "Team_NOC"]
    )
    obligatorias = {
        "anio": col_anio,
        "deporte": col_deporte,
        "evento": col_evento,
    }
    faltantes = [
        nombre for nombre, columna in obligatorias.items()
        if columna is None
    ]
    if faltantes:
        raise SystemExit(
            "Columnas no identificadas: "
            + ", ".join(faltantes)
            + "\nComparte la lista de columnas mostrada arriba."
        )
    filas = []
    for fila in lector:
        if str(fila[col_anio]).strip() != "2024":
            continue
        if col_temporada:
            if fila[col_temporada].strip().lower() != "summer":
                continue
        if fila[col_deporte].strip() != "Artistic Gymnastics":
            continue
        if fila[col_evento].strip() not in EVENTOS:
            continue
        filas.append(fila)
print("\n=== AUDITORIA GIMNASIA PARIS 2024 ===")
print("Participaciones encontradas:", len(filas))
resumen = {}
duplicados = Counter()
for evento, evento_id in EVENTOS.items():
    grupo = [
        f for f in filas
        if f[col_evento].strip() == evento
    ]
    medallas = Counter(
        (f.get(col_medalla) or "").strip()
        if col_medalla else "SIN_COLUMNA"
        for f in grupo
    )
    nocs = {
        (f.get(col_noc) or "").strip()
        for f in grupo
    } if col_noc else set()
    resumen[evento] = {
        "id_evento_historico_propuesto": evento_id,
        "participaciones": len(grupo),
        "paises_distintos": len(nocs),
        "medallas_fuente": dict(medallas),
        "equivalencia_confirmada": False,
    }
    print(f"\n{evento} -> evento {evento_id}")
    print("  Participaciones:", len(grupo))
    print("  Paises distintos:", len(nocs))
    print("  Medallas del CSV:", dict(medallas))
    if col_id:
        for f in grupo:
            identificador = f[col_id].strip()
            if identificador:
                duplicados[(evento, identificador)] += 1
print("\n=== POSIBLES DUPLICADOS ===")
repetidos = [
    (evento, identificador, cantidad)
    for (evento, identificador), cantidad in duplicados.items()
    if cantidad > 1
]
print("Pares atleta/evento repetidos:", len(repetidos))
for item in repetidos[:10]:
    print(item)
print("\n=== EJEMPLOS DE REGISTROS ===")
for fila in filas[:3]:
    print(json.dumps(fila, ensure_ascii=False))
reporte = {
    "filas_encontradas": len(filas),
    "columnas": columnas,
    "campos_detectados": {
        "anio": col_anio,
        "temporada": col_temporada,
        "deporte": col_deporte,
        "evento": col_evento,
        "medalla": col_medalla,
        "atleta": col_atleta,
        "id_atleta": col_id,
        "noc": col_noc,
    },
    "eventos": resumen,
    "duplicados_atleta_evento": len(repetidos),
    "estado": "AUDITORIA_SIN_INSERCION"
}
SALIDA.write_text(
    json.dumps(reporte, ensure_ascii=False, indent=2),
    encoding="utf-8"
)
print("\nArchivo generado:", SALIDA)
print("MongoDB no fue modificado.")
