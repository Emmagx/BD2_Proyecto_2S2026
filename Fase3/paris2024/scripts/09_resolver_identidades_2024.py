import csv
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]
ENTRADA = BASE / "evidencias" / "auditoria_identidades_tiro_2024.csv"
SALIDA = BASE / "evidencias" / "equivalencias_atletas_tiro_2024.csv"
# Equivalencias propuestas a partir de la revisión histórica.
# NO se consideran confirmadas hasta cotejar la identidad en la fuente.
REVISION_GUA = {
    "1958899": (143537, "ADRIANA_RUANO", "Coincidencia de nombre, pais y evento"),
    "1959163": (143538, "WALESKA_SOTO", "Posible abreviacion de Ana Waleska Soto"),
    "1958970": (123253, "PIERRE_BROL", "Posible abreviacion de Jean-Pierre Brol"),
}
with ENTRADA.open("r", encoding="utf-8-sig", newline="") as archivo:
    registros = list(csv.DictReader(archivo))
salida = []
for registro in registros:
    fuente = registro["id_fuente"]
    propuesto = REVISION_GUA.get(fuente)
    if propuesto:
        id_historico, referencia, motivo = propuesto
        id_candidato = id_historico
        estado = "PENDIENTE_CONFIRMACION"
    elif registro["estado"] == "CANDIDATO_NOMBRE_Y_PAIS":
        id_candidato = registro["ids_historicos_candidatos"]
        estado = "PENDIENTE_CONFIRMACION"
        motivo = "Coincidencia automatica por nombre y NOC"
    else:
        id_candidato = ""
        estado = "SIN_RESOLVER"
        motivo = "Requiere revision de identidad"
    salida.append({
        "id_fuente_2024": fuente,
        "nombre_2024": registro["nombre_2024"],
        "noc": registro["noc"],
        "evento": registro["evento"],
        "id_historico_candidato": id_candidato,
        "estado_identidad": estado,
        "motivo": motivo,
        "id_historico_confirmado": "",
    })
with SALIDA.open("w", encoding="utf-8-sig", newline="") as archivo:
    escritor = csv.DictWriter(archivo, fieldnames=salida[0].keys())
    escritor.writeheader()
    escritor.writerows(salida)
print("=== EQUIVALENCIAS PARIS 2024 ===")
print("Registros procesados:", len(salida))
print("Archivo:", SALIDA)
print("\nCASOS GUATEMALA:")
for fila in salida:
    if fila["noc"] == "GUA":
        print(fila)
print("\nSIN CAMBIOS EN MONGODB.")
