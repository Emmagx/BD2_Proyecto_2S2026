import csv
import json
import unicodedata
from collections import Counter
from pathlib import Path
from pymongo import MongoClient
BASE = Path(__file__).resolve().parents[1]
ENTRADA = BASE / "evidencias" / "lote_preliminar_tiro_2024.jsonl"
SALIDA = BASE / "evidencias" / "auditoria_identidades_tiro_2024.csv"
def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto or "")
    texto = "".join(
        c for c in texto if not unicodedata.combining(c)
    )
    return " ".join(texto.casefold().split())
def main():
    cliente = MongoClient(
        "mongodb://127.0.0.1:27017/?directConnection=true",
        serverSelectionTimeoutMS=5000
    )
    cliente.admin.command("ping")
    db = cliente["olimpiadas_mongo"]
    assert db.resultados.count_documents(
        {"edicion.anio": 2024}
    ) == 0, "Ya existen resultados de 2024: revisar antes de continuar"
    # Índice de nombres históricos: consulta de solo lectura.
    nombres = {}
    for atleta in db.atletas.find(
        {},
        {"_id": 1, "nombre": 1}
    ):
        clave = normalizar(atleta.get("nombre"))
        nombres.setdefault(clave, []).append(atleta)
    filas = []
    conteos = Counter()
    with ENTRADA.open("r", encoding="utf-8") as archivo:
        for linea in archivo:
            if not linea.strip():
                continue
            doc = json.loads(linea)
            participante = doc["atletas"][0]
            nombre = participante["nombre"]
            noc = participante["noc"]
            candidatos = nombres.get(normalizar(nombre), [])
            compatibles = []
            for candidato in candidatos:
                historial = db.resultados.count_documents({
                    "atletas.id": candidato["_id"],
                    "atletas.noc": noc
                })
                if historial:
                    compatibles.append(candidato)
            if len(compatibles) == 1:
                estado = "CANDIDATO_NOMBRE_Y_PAIS"
                ids = [compatibles[0]["_id"]]
            elif len(compatibles) > 1:
                estado = "AMBIGUO"
                ids = [a["_id"] for a in compatibles]
            elif candidatos:
                estado = "REVISAR_NOMBRE_SIN_PAIS"
                ids = [a["_id"] for a in candidatos]
            else:
                estado = "SIN_COINCIDENCIA"
                ids = []
            conteos[estado] += 1
            filas.append({
                "id_fuente": participante.get("idFuente2024", ""),
                "nombre_2024": nombre,
                "noc": noc,
                "evento": doc["evento"]["nombre"],
                "medalla": (
                    doc["medalla"]["codigo"]
                    if isinstance(doc.get("medalla"), dict)
                    else ""
                ),
                "estado": estado,
                "ids_historicos_candidatos": ";".join(map(str, ids)),
            })
    with SALIDA.open("w", newline="", encoding="utf-8-sig") as archivo:
        escritor = csv.DictWriter(archivo, fieldnames=filas[0].keys())
        escritor.writeheader()
        escritor.writerows(filas)
    print("\n=== AUDITORIA PARIS 2024 ===")
    print("Registros revisados:", len(filas))
    for estado, cantidad in conteos.most_common():
        print(f"{estado}: {cantidad}")
    print("\n=== GUATEMALA ===")
    for fila in filas:
        if fila["noc"] == "GUA":
            print(fila)
    print("\nArchivo generado:")
    print(SALIDA)
    print("\nSOLO LECTURA EN MONGODB: no se modificaron documentos.")
    cliente.close()
if __name__ == "__main__":
    main()
