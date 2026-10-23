import json
from pathlib import Path
from pymongo import MongoClient
BASE = Path(__file__).resolve().parents[1]
ENTRADA = BASE / "evidencias" / "piloto_guatemala_2024_validado.jsonl"
SALIDA = BASE / "evidencias" / "preflight_piloto_2024.json"
def main():
    cliente = MongoClient(
        "mongodb://127.0.0.1:27017/?directConnection=true",
        serverSelectionTimeoutMS=5000
    )
    db = cliente["olimpiadas_mongo"]
    cliente.admin.command("ping")
    documentos = [
        json.loads(linea)
        for linea in ENTRADA.read_text(encoding="utf-8").splitlines()
        if linea.strip()
    ]
    errores = []
    ids = []
    claves = []
    esperados = {
        143537: (687, 1, "ORO"),
        123253: (670, 3, "BRONCE"),
        143538: (687, 19, None),
    }
    if len(documentos) != 3:
        errores.append("El piloto debe contener exactamente 3 resultados")
    if db.catalogos.find_one({"_id": "juego:63"}):
        errores.append("El catalogo juego:63 ya existe")
    if db.catalogos.count_documents({
        "tipo": "juego", "anio": 2024
    }) != 0:
        errores.append("Ya existe una edicion de 2024")
    if db.resultados.count_documents({
        "edicion.anio": 2024
    }) != 0:
        errores.append("Ya existen resultados de 2024")
    for doc in documentos:
        resultado_id = doc["_id"]
        atleta_id = doc["atletas"][0]["id"]
        evento_id = doc["evento"]["id"]
        ids.append(resultado_id)
        if atleta_id not in esperados:
            errores.append(f"Atleta inesperado: {atleta_id}")
            continue
        evento_esperado, puesto, codigo = esperados[atleta_id]
        if db.atletas.find_one({"_id": atleta_id}) is None:
            errores.append(f"No existe atleta: {atleta_id}")
        catalogo_evento = db.catalogos.find_one({
            "_id": f"evento:{evento_id}"
        })
        if catalogo_evento is None:
            errores.append(f"No existe evento: {evento_id}")
        elif (
            catalogo_evento.get("deporteId") != doc["deporte"]["id"]
            or catalogo_evento.get("disciplinaId") != doc["disciplina"]["id"]
        ):
            errores.append(f"Evento incompatible: {evento_id}")
        if db.resultados.find_one({"_id": resultado_id}):
            errores.append(f"ID de resultado ocupado: {resultado_id}")
        medalla = doc.get("medalla")
        codigo_actual = medalla.get("codigo") if medalla else None
        if (
            evento_id != evento_esperado
            or doc["posicion"] != puesto
            or codigo_actual != codigo
        ):
            errores.append(f"Resultado incorrecto: {atleta_id}")
        if doc.get("edicion") != {
            "id": 63,
            "anio": 2024,
            "temporada": "Summer",
            "categoria": "Senior"
        }:
            errores.append(f"Edicion incorrecta: {resultado_id}")
        if doc.get("paises") != ["GUA"]:
            errores.append(f"Pais incorrecto: {resultado_id}")
        if doc.get("estado") != "COMPLETED":
            errores.append(f"Estado incorrecto: {resultado_id}")
        fuente = doc.get("fuente", {})
        clave = (fuente.get("playerIdOriginal"), evento_id)
        claves.append(clave)
        print(
            f"Resultado {resultado_id}: "
            f"atleta {atleta_id}, "
            f"evento {evento_id}, "
            f"puesto {doc['posicion']} "
            f"=> {'OK' if not errores else 'REVISAR'}"
        )
    if len(ids) != len(set(ids)):
        errores.append("Hay IDs de resultados duplicados")
    if len(claves) != len(set(claves)):
        errores.append("Hay participaciones duplicadas")
    reporte = {
        "fase": "Paris 2024 - Preflight",
        "registros_evaluados": len(documentos),
        "resultados_historicos": db.resultados.count_documents({}),
        "catalogos_historicos": db.catalogos.count_documents({}),
        "errores": errores,
        "apto_para_siguiente_etapa": len(errores) == 0,
        "mongo_modificado": False
    }
    SALIDA.write_text(
        json.dumps(reporte, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    print("\n=== PREFLIGHT PARIS 2024 ===")
    print(json.dumps(reporte, indent=2, ensure_ascii=False))
    print("\nArchivo:", SALIDA)
    print("No se modificaron datos en MongoDB.")
    cliente.close()
    if errores:
        raise SystemExit(1)
if __name__ == "__main__":
    main()
