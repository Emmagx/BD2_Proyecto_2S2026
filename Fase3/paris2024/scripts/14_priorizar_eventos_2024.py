import csv
from collections import Counter
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
EVIDENCIAS = BASE / "evidencias"
ENTRADA = EVIDENCIAS / "auditoria_propuestas_paris2024.csv"
SALIDA = EVIDENCIAS / "prioridad_mapeo_eventos_2024.csv"
with ENTRADA.open(encoding="utf-8-sig", newline="") as archivo:
    registros = list(csv.DictReader(archivo))
if not registros:
    raise SystemExit("ERROR: La auditoria esta vacia")
prioridades = Counter()
decisiones = Counter()
total_participaciones = 0
filas = []
for fila in registros:
    try:
        cantidad = int(fila.get("participaciones") or 0)
    except ValueError:
        raise SystemExit(
            f"Cantidad invalida: {fila.get('participaciones')}"
        )
    prioridad = fila.get("prioridad_revision", "").strip()
    decision = fila.get("decision_manual", "").strip()
    confirmado = all([
        fila.get("id_deporte_confirmado", "").strip(),
        fila.get("id_disciplina_confirmado", "").strip(),
        fila.get("id_evento_confirmado", "").strip(),
    ])
    estado = (
        "MAPEO_DOCUMENTADO"
        if confirmado
        else "PENDIENTE_REVISION"
    )
    prioridades[prioridad or "SIN_CLASIFICAR"] += 1
    decisiones[estado] += 1
    total_participaciones += cantidad
    filas.append({
        "sport_2024": fila["sport_2024"],
        "evento_2024": fila["evento_2024"],
        "participaciones": cantidad,
        "prioridad_revision": prioridad,
        "decision_manual": decision,
        "puntaje_mejor": fila.get("puntaje_mejor", ""),
        "id_deporte_confirmado": fila.get(
            "id_deporte_confirmado", ""
        ),
        "id_disciplina_confirmado": fila.get(
            "id_disciplina_confirmado", ""
        ),
        "id_evento_confirmado": fila.get(
            "id_evento_confirmado", ""
        ),
        "estado_mapeo": estado,
        "sugerencias": fila.get("sugerencias", ""),
    })
# Primero eventos pendientes con mayor cantidad de participaciones.
filas.sort(
    key=lambda f: (
        f["estado_mapeo"] != "PENDIENTE_REVISION",
        -f["participaciones"],
        f["sport_2024"],
        f["evento_2024"],
    )
)
with SALIDA.open(
    "w", encoding="utf-8-sig", newline=""
) as archivo:
    escritor = csv.DictWriter(
        archivo, fieldnames=list(filas[0].keys())
    )
    escritor.writeheader()
    escritor.writerows(filas)
print("\n=== PARIS 2024 - PRIORIDAD DE EVENTOS ===")
print("Combinaciones deporte/evento:", len(filas))
print("Participaciones representadas:", total_participaciones)
print("\nESTADO:")
for estado, cantidad in decisiones.items():
    print(f"  {estado}: {cantidad}")
print("\nPRIORIDADES:")
for prioridad, cantidad in prioridades.most_common():
    print(f"  {prioridad}: {cantidad}")
print("\nTOP 10 PENDIENTES POR PARTICIPACIONES:")
for fila in filas[:10]:
    print(
        f"{fila['participaciones']:>5} | "
        f"{fila['sport_2024']} | "
        f"{fila['evento_2024']} | "
        f"{fila['prioridad_revision']}"
    )
print("\nArchivo:", SALIDA)
print("MongoDB no fue modificado.")
