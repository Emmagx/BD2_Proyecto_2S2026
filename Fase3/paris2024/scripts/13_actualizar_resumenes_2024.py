import argparse
import json
from collections import Counter
from pathlib import Path
from pymongo import MongoClient
IDS = [143537, 123253, 143538]
CODIGOS = {"ORO": "oro", "PLATA": "plata", "BRONCE": "bronce"}
BASE = Path(__file__).resolve().parents[1]
REPORTE = BASE / "evidencias" / "resumenes_piloto_2024.json"
def contar_medallas(codigos):
    c = Counter(codigos)
    salida = {v: c.get(k, 0) for k, v in CODIGOS.items()}
    salida["total"] = sum(salida.values())
    return salida
def resumen_atleta(db, aid):
    resultados = db.resultados.find(
        {"atletas.id": aid},
        {"atletas": 1, "edicion": 1, "deporte": 1, "medalla": 1}
    )
    participaciones = 0
    juegos, anios, deportes, medallas = set(), set(), set(), []
    for r in resultados:
        for a in r["atletas"]:
            if a["id"] != aid:
                continue
            participaciones += 1
            juegos.add(r["edicion"]["id"])
            anios.add(r["edicion"]["anio"])
            deportes.add(r["deporte"]["nombre"])
            codigo = (r.get("medalla") or {}).get("codigo")
            if codigo in CODIGOS:
                medallas.append(codigo)
    return {
        "participaciones": participaciones,
        "juegos": len(juegos),
        "anios": sorted(anios),
        "deportes": sorted(deportes),
        "medallas": contar_medallas(medallas),
    }
def resumen_guatemala(db):
    resultados = db.resultados.find(
        {"$or": [{"atletas.noc": "GUA"}, {"paises": "GUA"}]},
        {
            "atletas": 1, "paises": 1, "edicion": 1,
            "deporte": 1, "medalla": 1, "equipoMixto": 1
        }
    )
    participaciones = 0
    atletas, juegos, anios, deportes = set(), set(), set(), set()
    medallas, medallas_atleta, medallas_mixtas = [], [], []
    for r in resultados:
        guatemaltecos = [
            a for a in r.get("atletas", [])
            if a.get("noc") == "GUA"
        ]
        for a in guatemaltecos:
            participaciones += 1
            atletas.add(a["id"])
            juegos.add(r["edicion"]["id"])
            anios.add(r["edicion"]["anio"])
            deportes.add(r["deporte"]["nombre"])
        codigo = (r.get("medalla") or {}).get("codigo")
        if codigo in CODIGOS:
            medallas_atleta.extend([codigo] * len(guatemaltecos))
            if "GUA" in r.get("paises", []):
                if r.get("equipoMixto") is True:
                    medallas_mixtas.append(codigo)
                else:
                    medallas.append(codigo)
    return {
        "participaciones": participaciones,
        "atletas": len(atletas),
        "juegos": len(juegos),
        "anios": sorted(anios),
        "deportes": sorted(deportes),
        "medallas": contar_medallas(medallas),
        "medallasAtleta": contar_medallas(medallas_atleta),
        "medallasMixtas": contar_medallas(medallas_mixtas),
        "primerAnio": min(anios) if anios else None,
        "ultimoAnio": max(anios) if anios else None,
    }
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--aplicar", action="store_true")
    args = parser.parse_args()
    cliente = MongoClient(
        "mongodb://127.0.0.1:27017/?directConnection=true",
        serverSelectionTimeoutMS=5000
    )
    cliente.admin.command("ping")
    db = cliente["olimpiadas_mongo"]
    assert db.catalogos.find_one({"_id": "juego:63"})
    assert db.resultados.count_documents({"edicion.anio": 2024}) == 3
    assert db.resultados.count_documents({
        "_id": {"$in": [156033, 156034, 156035]},
        "edicion.anio": 2024
    }) == 3
    nuevos = {}
    for aid in IDS:
        actual = db.atletas.find_one({"_id": aid})
        assert actual is not None
        nuevos[aid] = resumen_atleta(db, aid)
    pais = db.paises.find_one({"noc": "GUA"})
    assert pais is not None
    nuevo_pais = resumen_guatemala(db)
    # Controles específicos de nuestro piloto.
    assert nuevo_pais["participaciones"] == 466
    assert nuevo_pais["medallas"] == {
        "oro": 1, "plata": 1, "bronce": 1, "total": 3
    }
    assert nuevo_pais["ultimoAnio"] == 2024
    assert nuevos[143537]["medallas"]["oro"] == 1
    assert nuevos[123253]["medallas"]["bronce"] == 1
    assert nuevos[143538]["medallas"]["total"] == 0
    print("\n=== RESUMENES PARIS 2024 ===")
    for aid in IDS:
        actual = db.atletas.find_one({"_id": aid})
        print(
            actual["nombre"],
            "| antes:", actual["resumen"]["medallas"],
            "| calculado:", nuevos[aid]["medallas"],
            "| participaciones:", nuevos[aid]["participaciones"]
        )
    print(
        "\nGuatemala:",
        "\nAntes:", pais["resumen"]["medallas"],
        "\nCalculado:", nuevo_pais["medallas"],
        "\nParticipaciones:", nuevo_pais["participaciones"],
        "\nJuegos:", nuevo_pais["juegos"]
    )
    if args.aplicar:
        print("\nAPLICANDO ACTUALIZACIONES...")
        for aid in IDS:
            db.atletas.update_one(
                {"_id": aid},
                {"$set": {"resumen": nuevos[aid]}}
            )
        db.paises.update_one(
            {"_id": pais["_id"]},
            {"$set": {"resumen": nuevo_pais}}
        )
        for aid in IDS:
            assert db.atletas.find_one({"_id": aid})["resumen"] == nuevos[aid]
        assert db.paises.find_one({"_id": pais["_id"]})["resumen"] == nuevo_pais
        print("Actualizados: 3 atletas y Guatemala.")
    else:
        print("\nMODO SIMULACION: MongoDB no fue modificado.")
    reporte = {
        "modo": "APLICACION" if args.aplicar else "SIMULACION",
        "atletas": {str(k): v for k, v in nuevos.items()},
        "guatemala": nuevo_pais
    }
    REPORTE.write_text(
        json.dumps(reporte, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print("Reporte:", REPORTE)
    cliente.close()
if __name__ == "__main__":
    main()
