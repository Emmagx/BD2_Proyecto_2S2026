import csv
from collections import Counter
from pathlib import Path
base = Path(__file__).resolve().parents[1] / "evidencias"
entrada = base / "auditoria_final_identidades_gimnasia_2024.csv"
salida = base / "decisiones_identidades_gimnasia_2024.csv"
with entrada.open(encoding="utf-8-sig", newline="") as f:
    filas = list(csv.DictReader(f))
assert len(filas) == 65
# Exclusiones respaldadas por diferencias de identidad.
exclusiones = {
    ("Luca Giubellini", "Daniel Giubellini"):
        "Son personas distintas: Luca es hijo de Daniel (FIG)",
    ("Matteo Giubellini", "Daniel Giubellini"):
        "Son personas distintas: Matteo es hijo de Daniel (FIG)",
    ("Andreea Preda", "Andreea Răducan"):
        "No hay evidencia suficiente para vincular personas distintas",
    ("Giorgia Villa", "Virginia Giorgi"):
        "No hay evidencia suficiente para vincular personas distintas",
}
# Casos con evidencia de una variante de nombre; aun requieren
# comprobar el ID historico del candidato.
revisar_variantes = {
    ("Sunisa Lee", "Suni Lee"):
        "USA Gymnastics documenta ambos nombres",
}
resultado = []
conteos = Counter()
for fila in filas:
    par = (fila["nombre_2024"], fila["nombre_historico"])
    if par in exclusiones:
        decision = "VINCULACION_DESCARTADA"
        observacion = exclusiones[par]
    elif par in revisar_variantes:
        decision = "VARIANTE_DOCUMENTADA_REVISAR_ID"
        observacion = revisar_variantes[par]
    else:
        decision = "PENDIENTE_REVISION"
        observacion = ""
    conteos[decision] += 1
    resultado.append({
        **fila,
        "decision_identidad": decision,
        "motivo_decision": observacion,
        "id_historico_aprobado": "",
        "fuente_documental": "",
    })
with salida.open("w", encoding="utf-8-sig", newline="") as f:
    escritor = csv.DictWriter(
        f, fieldnames=list(resultado[0].keys())
    )
    escritor.writeheader()
    escritor.writerows(resultado)
print("\n=== DECISIONES IDENTIDADES GIMNASIA 2024 ===")
print("Candidatos evaluados:", len(resultado))
for estado, cantidad in conteos.most_common():
    print(f"{estado}: {cantidad}")
print("\nVINCULACIONES DESCARTADAS:")
for fila in resultado:
    if fila["decision_identidad"] == "VINCULACION_DESCARTADA":
        print(
            fila["nombre_2024"],
            "NO corresponde a",
            fila["nombre_historico"]
        )
print("\nArchivo:", salida)
print("MongoDB no fue modificado.")
