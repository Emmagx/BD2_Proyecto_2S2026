import csv
import json
from collections import Counter
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
DATOS = BASE / "datos" / "olympics_dataset.csv"
EVID = BASE / "evidencias"
IDENTIDADES = EVID / "lote_revision_identidades_gimnasia_2024.csv"
SALIDA = EVID / "lote_gimnasia_2024_preparado.jsonl"
REPORTE = EVID / "reporte_lote_gimnasia_2024.json"
EVENTOS = {
    "Women's Balance Beam": (50, 393, 483),
    "Women's Floor Exercise": (50, 390, 480),
    "Men's Horizontal Bar": (50, 399, 493),
    "Men's Floor Exercise": (50, 390, 490),
    "Men's Rings": (50, 400, 494),
}
MEDALLAS = {
    "Gold": "ORO",
    "Silver": "PLATA",
    "Bronze": "BRONCE",
    "No medal": None,
}
with IDENTIDADES.open(
    encoding="utf-8-sig", newline=""
) as archivo:
    revisiones = list(csv.DictReader(archivo))
assert len(revisiones) == 65
por_player = {
    fila["player_id_2024"]: fila
    for fila in revisiones
}
assert len(por_player) == 65
documentos = []
claves = set()
conteo_estados = Counter()
conteo_eventos = Counter()
jugadores = set()
with DATOS.open(
    encoding="utf-8-sig", newline=""
) as archivo:
    for fila in csv.DictReader(archivo):
        if (
            fila["Year"].strip() != "2024"
            or fila["Season"].strip() != "Summer"
            or fila["Sport"].strip() != "Artistic Gymnastics"
            or fila["Event"].strip() not in EVENTOS
        ):
            continue
        player_id = fila["player_id"].strip()
        evento = fila["Event"].strip()
        clave = (player_id, evento)
        assert player_id, "Falta player_id"
        assert clave not in claves, (
            f"Participacion duplicada: {clave}"
        )
        claves.add(clave)
        jugadores.add(player_id)
        medalla_original = fila["Medal"].strip()
        assert medalla_original in MEDALLAS, medalla_original
        deporte_id, disciplina_id, evento_id = EVENTOS[evento]
        revision = por_player.get(player_id)
        # Propuesta de identidad, NO aprobacion definitiva.
        candidato_id = None
        estado_identidad = "SIN_CANDIDATO_CONSOLIDADO"
        if revision:
            estado_identidad = revision["clasificacion"]
            if estado_identidad == "PRIORIDAD_ALTA":
                candidato_id = int(
                    revision["id_historico_propuesto"]
                )
        doc = {
            "fuente": {
                "dataset": "olympics_dataset.csv",
                "playerIdOriginal": player_id,
                "eventoOriginal": evento,
                "deporteOriginal": fila["Sport"],
            },
            "edicion": {
                "id": 63,
                "anio": 2024,
                "temporada": "Summer",
                "categoria": "Senior",
            },
            "deporte": {
                "id": deporte_id,
                "nombre": "Artistic Gymnastics (Gymnastics)",
            },
            "disciplina": {
                "id": disciplina_id,
            },
            "evento": {
                "id": evento_id,
            },
            "atletaFuente": {
                "nombre": fila["Name"].strip(),
                "sexo": fila["Sex"].strip(),
                "noc": fila["NOC"].strip(),
                "playerId2024": player_id,
            },
            "identidad": {
                "idHistoricoCandidato": candidato_id,
                "estado": estado_identidad,
                "confirmada": False,
            },
            "resultadoFuente": {
                "medallaOriginal": medalla_original,
                "codigoMedalla": MEDALLAS[medalla_original],
                "posicion": None,
                "posicionVerificada": False,
            },
            "mapeoEvento": {
                "estado": "ESTRUCTURA_COHERENTE_PENDIENTE_APROBACION",
                "confirmado": False,
            },
            "aptoParaInsercion": False,
        }
        documentos.append(doc)
        conteo_estados[estado_identidad] += 1
        conteo_eventos[evento] += 1
assert len(documentos) == 410
assert len(jugadores) == 178
assert len(claves) == 410
with SALIDA.open("w", encoding="utf-8") as archivo:
    for doc in documentos:
        archivo.write(
            json.dumps(doc, ensure_ascii=False) + "\n"
        )
reporte = {
    "fase": "Preparacion gimnasio Paris 2024",
    "participaciones": len(documentos),
    "atletas_fuente": len(jugadores),
    "eventos": dict(conteo_eventos),
    "estados_identidad_por_participacion": dict(conteo_estados),
    "registros_aptos_insercion": 0,
    "mongo_modificado": False,
}
REPORTE.write_text(
    json.dumps(reporte, indent=2, ensure_ascii=False),
    encoding="utf-8"
)
print("\n=== LOTE GIMNASIA PARIS 2024 ===")
print("Participaciones preparadas:", len(documentos))
print("Atletas distintos:", len(jugadores))
print("\nEVENTOS:")
for evento, cantidad in conteo_eventos.items():
    print(f"  {evento}: {cantidad}")
print("\nESTADOS DE IDENTIDAD (PARTICIPACIONES):")
for estado, cantidad in conteo_estados.most_common():
    print(f"  {estado}: {cantidad}")
print("\nAptos para insercion: 0")
print("Archivo:", SALIDA)
print("Reporte:", REPORTE)
print("MongoDB no fue modificado.")
