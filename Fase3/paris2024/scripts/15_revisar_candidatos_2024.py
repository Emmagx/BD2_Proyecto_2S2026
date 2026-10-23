import csv
from pathlib import Path
BASE = Path(__file__).resolve().parents[1] / "evidencias"
ENTRADA = BASE / "prioridad_mapeo_eventos_2024.csv"
SALIDA = BASE / "candidatos_fuertes_2024.csv"
with ENTRADA.open(
    encoding="utf-8-sig", newline=""
) as archivo:
    registros = list(csv.DictReader(archivo))
fuertes = [
    fila for fila in registros
    if fila["prioridad_revision"] == "CANDIDATO_FUERTE_VERIFICAR"
]
fuertes.sort(
    key=lambda fila: -int(fila["participaciones"])
)
campos = [
    "sport_2024",
    "evento_2024",
    "participaciones",
    "puntaje_mejor",
    "sugerencias",
    "id_deporte_confirmado",
    "id_disciplina_confirmado",
    "id_evento_confirmado",
    "decision_manual",
]
with SALIDA.open(
    "w", encoding="utf-8-sig", newline=""
) as archivo:
    escritor = csv.DictWriter(
        archivo, fieldnames=campos
    )
    escritor.writeheader()
    for fila in fuertes:
        escritor.writerow({
            campo: fila.get(campo, "")
            for campo in campos
        })
total = sum(
    int(fila["participaciones"])
    for fila in fuertes
)
print("\n=== CANDIDATOS FUERTES PARIS 2024 ===")
print("Combinaciones:", len(fuertes))
print("Participaciones cubiertas:", total)
print("\nTOP 15 CANDIDATOS:\n")
for numero, fila in enumerate(fuertes[:15], 1):
    sugerencia = fila.get("sugerencias", "")
    mejor = sugerencia.split(" | ")[0]
    print(
        f"{numero:02}. "
        f"{fila['sport_2024']} / "
        f"{fila['evento_2024']}"
    )
    print(
        f"    Participaciones: {fila['participaciones']}"
    )
    print(
        f"    Mejor candidato: {mejor}"
    )
    print()
print("Archivo generado:", SALIDA)
print("MongoDB no fue modificado.")
