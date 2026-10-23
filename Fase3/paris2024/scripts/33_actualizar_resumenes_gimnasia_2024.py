import argparse
import json
from collections import Counter
from pathlib import Path
from pymongo import MongoClient
BASE = Path(__file__).resolve().parents[1]
ENTRADA = BASE / "evidencias" / "lote_medallistas_gimnasia_validado.jsonl"
REPORTE = BASE / "evidencias" / "resumenes_gimnasia_2024.json"
CODIGOS = {
    "ORO": "oro",
    "PLATA": "plata",
    "BRONCE": "bronce"
}
def contar_medallas(codigos):
    c = Counter(codigos)
    resultado = {
        valor: c.get(clave, 0)
        for clave, valor in CODIGOS.items()
    }
    resultado["total"] = sum(resultado.values())
    return resultado
def resumen_atleta(db, aid):
    resultados = db.resultados.find(
        {"atletas.id": aid},
        {
            "atletas": 1,
            "edicion": 1,
            "deporte": 1,
            "medalla": 1
        }
    )
    participaciones = 0
    juegos = set()
    anios = set()
    deportes = set()
    medallas = []
    for r in resultados:
        for a in r.get("atletas", []):
            if a.get("id") != aid:
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
        "medallas": contar_medallas(medallas)
    }
def resumen_pais(db, noc):
    resultados = db.resultados.find(
        {
            "$or": [
                {"atletas.noc": noc},
                {"paises": noc}
            ]
        },
        {
            "atletas": 1,
            "paises": 1,
            "edicion": 1,
            "deporte": 1,
            "medalla": 1,
            "equipoMixto": 1
        }
    )
    participaciones = 0
    atletas = set()
    juegos = set()
    anios = set()
    deportes = set()
    medallas = []
    medallas_atleta = []
    medallas_mixtas = []
    for r in resultados:
        representantes = [
            a for a in r.get("atletas", [])
            if a.get("noc") == noc
        ]
        for a in representantes:
            participaciones += 1
            atletas.add(a["id"])
            juegos.add(r["edicion"]["id"])
            anios.add(r["edicion"]["anio"])
            deportes.add(r["deporte"]["nombre"])
        codigo = (r.get("medalla") or {}).get("codigo")
        if codigo in CODIGOS:
            medallas_atleta.extend(
                [codigo] * len(representantes)
            )
            if noc in r.get("paises", []):
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
        "ultimoAnio": max(anios) if anios else None
    }
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--aplicar", action="store_true")
    args = parser.parse_args()
    docs = [
        json.loads(linea)
        for linea in ENTRADA.read_text(
            encoding="utf-8"
        ).splitlines()
        if linea.strip()
    ]
    assert len(docs) == 8
    ids = sorted({
        d["atletas"][0]["id"]
        for d in docs
    })
    nocs = sorted({
        d["atletas"][0]["noc"]
        for d in docs
    })
    assert len(ids) == 8
    assert len(nocs) == 7
    cliente = MongoClient(
        "mongodb://127.0.0.1:27017/?directConnection=true",
        serverSelectionTimeoutMS=5000
    )
    cliente.admin.command("ping")
    db = cliente["olimpiadas_mongo"]
    # Asegurar que el lote realmente esta insertado.
    assert db.resultados.count_documents({
        "edicion.anio": 2024
    }) == 11
    assert db.resultados.count_documents({
        "edicion.anio": {"$lt": 2024}
    }) == 156032
    for doc in docs:
        guardado = db.resultados.find_one({
            "_id": doc["_id"]
        })
        assert guardado == doc, (
            f"Resultado ausente o diferente: {doc['_id']}"
        )
    perfiles = {}
    resumenes_atletas = {}
    for aid in ids:
        perfil = db.atletas.find_one({"_id": aid})
        assert perfil is not None
        perfiles[aid] = perfil
        resumenes_atletas[aid] = resumen_atleta(db, aid)
    paises = {}
    resumenes_paises = {}
    for noc in nocs:
        pais = db.paises.find_one({"noc": noc})
        assert pais is not None, (
            f"No existe el pais con NOC {noc}"
        )
        paises[noc] = pais
        resumenes_paises[noc] = resumen_pais(db, noc)
    print("\n=== RESUMENES GIMNASIA PARIS 2024 ===")
    print("Resultados 2024:", 11)
    print("Atletas por actualizar:", len(ids))
    print("Paises por actualizar:", len(nocs))
    print("\nATLETAS:")
    for aid in ids:
        actual = perfiles[aid]
        nuevo = resumenes_atletas[aid]
        print(
            actual["nombre"],
            "| antes:",
            actual.get("resumen", {}).get("medallas"),
            "| calculado:",
            nuevo["medallas"]
        )
    print("\nPAISES:")
    for noc in nocs:
        actual = paises[noc]
        nuevo = resumenes_paises[noc]
        print(
            noc,
            "| antes:",
            actual.get("resumen", {}).get("medallas"),
            "| calculado:",
            nuevo["medallas"],
            "| participaciones:",
            nuevo["participaciones"]
        )
    if args.aplicar:
        print("\nAPLICANDO ACTUALIZACIONES...")
        for aid in ids:
            resultado = db.atletas.update_one(
                {"_id": aid},
                {
                    "$set": {
                        "resumen": resumenes_atletas[aid]
                    }
                }
            )
            assert resultado.matched_count == 1
        for noc in nocs:
            resultado = db.paises.update_one(
                {"_id": paises[noc]["_id"]},
                {
                    "$set": {
                        "resumen": resumenes_paises[noc]
                    }
                }
            )
            assert resultado.matched_count == 1
        # Comprobar que todos quedaron actualizados.
        for aid in ids:
            guardado = db.atletas.find_one({"_id": aid})
            assert (
                guardado["resumen"] == resumenes_atletas[aid]
            )
        for noc in nocs:
            guardado = db.paises.find_one({
                "_id": paises[noc]["_id"]
            })
            assert (
                guardado["resumen"] == resumenes_paises[noc]
            )
        print("\n=== ACTUALIZACION EXITOSA ===")
        print("Atletas actualizados:", len(ids))
        print("Paises actualizados:", len(nocs))
        print("Resultados 2024 conservados:", 11)
    else:
        print("\nMODO SIMULACION")
        print("MongoDB no fue modificado.")
    reporte = {
        "modo": (
            "APLICACION" if args.aplicar
            else "SIMULACION"
        ),
        "resultados_2024": 11,
        "atletas": {
            str(aid): resumenes_atletas[aid]
            for aid in ids
        },
        "paises": resumenes_paises
    }
    REPORTE.write_text(
        json.dumps(
            reporte,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )
    print("\nReporte:", REPORTE)
    cliente.close()
if __name__ == "__main__":
    main()
