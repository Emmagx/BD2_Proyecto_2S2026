import argparse
import importlib.util
import json
from pathlib import Path
from pymongo import MongoClient
BASE = Path(__file__).resolve().parents[1]
SCRIPTS = Path(__file__).resolve().parent
EVID = BASE / "evidencias"
LOTE = EVID / "lote_104_gimnasia_validado.jsonl"
REPORTE = EVID / "resumenes_lote_104_gimnasia.json"
# Reutilizar las funciones del script 33.
ruta = SCRIPTS / "33_actualizar_resumenes_gimnasia_2024.py"
spec = importlib.util.spec_from_file_location(
    "actualizador_gimnasia", ruta
)
modulo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(modulo)
parser = argparse.ArgumentParser()
parser.add_argument("--aplicar", action="store_true")
args = parser.parse_args()
docs = [
    json.loads(linea)
    for linea in LOTE.read_text(
        encoding="utf-8"
    ).splitlines()
    if linea.strip()
]
assert len(docs) == 104
ids_resultados = {d["_id"] for d in docs}
assert ids_resultados == set(range(156044, 156148))
assert all(d["medalla"] is None for d in docs)
assert all(d["revisar"] is True for d in docs)
ids_atletas = sorted({
    a["id"]
    for d in docs
    for a in d["atletas"]
})
nocs = sorted({
    a["noc"]
    for d in docs
    for a in d["atletas"]
})
assert len(ids_atletas) == 45
cliente = MongoClient(
    "mongodb://127.0.0.1:27017/?directConnection=true",
    serverSelectionTimeoutMS=5000
)
cliente.admin.command("ping")
db = cliente["olimpiadas_mongo"]
assert db.resultados.count_documents({
    "edicion.anio": 2024
}) == 115
assert db.resultados.count_documents({
    "edicion.anio": {"$lt": 2024}
}) == 156032
# Verificar que se conservaron los resultados del lote.
for doc in docs:
    guardado = db.resultados.find_one({"_id": doc["_id"]})
    assert guardado == doc, (
        f"Resultado diferente o ausente: {doc['_id']}"
    )
resumenes_atletas = {}
resumenes_paises = {}
perfiles = {}
paises = {}
for aid in ids_atletas:
    perfil = db.atletas.find_one({"_id": aid})
    assert perfil is not None
    perfiles[aid] = perfil
    resumenes_atletas[aid] = modulo.resumen_atleta(
        db, aid
    )
for noc in nocs:
    pais = db.paises.find_one({"noc": noc})
    assert pais is not None, f"Pais inexistente: {noc}"
    paises[noc] = pais
    resumenes_paises[noc] = modulo.resumen_pais(
        db, noc
    )
print("\n=== RESUMENES LOTE MASIVO GIMNASIA ===")
print("Resultados Paris 2024:", 115)
print("Resultados del lote:", len(docs))
print("Atletas afectados:", len(ids_atletas))
print("Paises afectados:", len(nocs))
print("\nPARTICIPACIONES POR ATLETA:")
for aid in ids_atletas:
    antes = perfiles[aid].get("resumen", {})
    nuevo = resumenes_atletas[aid]
    diferencia = (
        nuevo["participaciones"] -
        antes.get("participaciones", 0)
    )
    # Este lote no debe agregar medallas.
    assert nuevo["medallas"] == antes["medallas"], (
        f"Cambio inesperado de medallas: {aid}"
    )
    assert diferencia >= 0
    print(
        perfiles[aid]["nombre"],
        "| antes:", antes.get("participaciones"),
        "| ahora:", nuevo["participaciones"],
        "| diferencia:", diferencia
    )
print("\nPAISES:")
for noc in nocs:
    antes = paises[noc].get("resumen", {})
    nuevo = resumenes_paises[noc]
    diferencia = (
        nuevo["participaciones"] -
        antes.get("participaciones", 0)
    )
    assert nuevo["medallas"] == antes["medallas"], (
        f"Cambio inesperado de medallas del pais {noc}"
    )
    assert diferencia >= 0
    print(
        noc,
        "| antes:", antes.get("participaciones"),
        "| ahora:", nuevo["participaciones"],
        "| diferencia:", diferencia
    )
if args.aplicar:
    print("\nAPLICANDO ACTUALIZACIONES...")
    for aid in ids_atletas:
        r = db.atletas.update_one(
            {"_id": aid},
            {"$set": {
                "resumen": resumenes_atletas[aid]
            }}
        )
        assert r.matched_count == 1
    for noc in nocs:
        r = db.paises.update_one(
            {"_id": paises[noc]["_id"]},
            {"$set": {
                "resumen": resumenes_paises[noc]
            }}
        )
        assert r.matched_count == 1
    for aid in ids_atletas:
        assert db.atletas.find_one(
            {"_id": aid}
        )["resumen"] == resumenes_atletas[aid]
    for noc in nocs:
        assert db.paises.find_one(
            {"_id": paises[noc]["_id"]}
        )["resumen"] == resumenes_paises[noc]
    print("\n=== ACTUALIZACION EXITOSA ===")
    print("Atletas actualizados:", len(ids_atletas))
    print("Paises actualizados:", len(nocs))
    print("Resultados 2024:", 115)
else:
    print("\nSIMULACION EXITOSA")
    print("MongoDB no fue modificado.")
REPORTE.write_text(
    json.dumps({
        "modo": "APLICACION" if args.aplicar else "SIMULACION",
        "resultados_2024": 115,
        "atletas_actualizados": len(ids_atletas),
        "paises_actualizados": len(nocs),
        "resumenes_atletas": {
            str(k): v for k, v in resumenes_atletas.items()
        },
        "resumenes_paises": resumenes_paises
    }, ensure_ascii=False, indent=2),
    encoding="utf-8"
)
print("\nReporte:", REPORTE)
cliente.close()
