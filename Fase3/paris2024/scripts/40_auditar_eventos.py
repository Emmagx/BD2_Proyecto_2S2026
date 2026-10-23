import csv
import re
import unicodedata
from collections import Counter
from pathlib import Path
BASE = Path(__file__).resolve().parents[1] / "evidencias"
ENTRADA = BASE / "mapa_general_eventos_2024.csv"
SALIDA = BASE / "eventos_candidatos_exactos_2024.csv"
def normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(
        c for c in texto if not unicodedata.combining(c)
    )
    texto = texto.lower()
    texto = texto.replace("women's", "women")
    texto = texto.replace("men's", "men")
    texto = re.sub(r"\bolympic\b", "", texto)
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return " ".join(texto.split())
def clave(texto):
    return tuple(sorted(normalizar(texto).split()))
with ENTRADA.open(encoding="utf-8-sig", newline="") as f:
    filas = list(csv.DictReader(f))
assert len(filas) == 361
categorias = Counter()
participaciones = Counter()
exactos = []
sin_sugerencia = []
revisar = []
for fila in filas:
    opciones = []
    for i in range(1, 4):
        prefijo = f"opcion_{i}"
        eid = fila[f"{prefijo}_evento_id"]
        if not eid:
            continue
        coincide = (
            clave(fila["evento_2024"])
            == clave(fila[f"{prefijo}_evento"])
        )
        if coincide:
            opciones.append((eid, i))
    cantidad = int(fila["participaciones"])
    if not fila["opcion_1_evento_id"]:
        estado = "SIN_SUGERENCIA"
        sin_sugerencia.append(fila)
    elif len(opciones) == 1:
        estado = "COINCIDENCIA_EXACTA_UNICA"
        fila["evento_id_propuesto"] = opciones[0][0]
        exactos.append(fila)
    else:
        estado = "REQUIERE_REVISION"
        revisar.append(fila)
    fila["auditoria"] = estado
    categorias[estado] += 1
    participaciones[estado] += cantidad
with SALIDA.open(
    "w", encoding="utf-8-sig", newline=""
) as f:
    campos = list(dict.fromkeys(campo for fila in filas for campo in fila.keys()))
    escritor = csv.DictWriter(f, fieldnames=campos)
    escritor.writeheader()
    escritor.writerows(filas)
print("\n=== AUDITORIA GENERAL DE EVENTOS ===")
for estado, cantidad in categorias.items():
    print(
        estado,
        "| eventos:", cantidad,
        "| participaciones:", participaciones[estado]
    )
print("\n=== EVENTOS SIN SUGERENCIA ===")
for fila in sin_sugerencia:
    print(
        fila["deporte_2024"],
        "|", fila["evento_2024"],
        "| filas:", fila["participaciones"]
    )
print("\n=== EJEMPLOS DE COINCIDENCIA EXACTA ===")
for fila in exactos[:15]:
    print(
        fila["deporte_2024"],
        "|", fila["evento_2024"],
        "-> ID", fila["evento_id_propuesto"]
    )
print("\nArchivo:", SALIDA)
print("Las coincidencias aun deben comprobarse por deporte.")
print("MongoDB no fue modificado.")

