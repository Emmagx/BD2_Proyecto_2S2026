
import csv
import json
from collections import Counter
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent.parent
ARCHIVO = BASE / "datos" / "olympics_dataset.csv"
EVIDENCIAS = BASE / "evidencias"
EVIDENCIAS.mkdir(exist_ok=True)

COLUMNAS = {
    "player_id", "Name", "Sex", "Team", "NOC",
    "Year", "Season", "City", "Sport", "Event", "Medal"
}

def analizar():
    total = 0
    registros_2024 = 0
    atletas = set()
    paises = set()
    deportes = set()
    eventos = set()
    medallas = Counter()
    muestras = []

    with ARCHIVO.open("r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)
        faltantes = COLUMNAS - set(lector.fieldnames or [])

        if faltantes:
            raise ValueError(f"Columnas faltantes: {sorted(faltantes)}")

        for fila in lector:
            total += 1

            if fila["Year"].strip() != "2024":
                continue

            if fila["Season"].strip().lower() != "summer":
                continue

            registros_2024 += 1
            atletas.add(fila["player_id"].strip())
            paises.add(fila["NOC"].strip())
            deportes.add(fila["Sport"].strip())
            eventos.add(fila["Event"].strip())

            medalla = fila["Medal"].strip() or "Sin dato"
            medallas[medalla] += 1

            if len(muestras) < 5:
                muestras.append(fila)

    reporte = {
        "fecha_ejecucion": datetime.now().astimezone().isoformat(),
        "archivo": ARCHIVO.name,
        "registros_historicos": total,
        "participaciones_2024": registros_2024,
        "atletas_distintos_por_id": len(atletas),
        "delegaciones_distintas_por_noc": len(paises),
        "deportes_distintos": len(deportes),
        "eventos_distintos": len(eventos),
        "registros_por_medalla": dict(medallas),
        "muestras": muestras
    }

    salida = EVIDENCIAS / "analisis_2024.json"
    salida.write_text(
        json.dumps(reporte, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(json.dumps(
        {k: v for k, v in reporte.items() if k != "muestras"},
        indent=2,
        ensure_ascii=False
    ))
    print(f"\nEvidencia guardada en: {salida}")


if __name__ == "__main__":
    analizar()
