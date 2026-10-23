#!/usr/bin/env python3
"""Prepara un lote de prueba de Paris 2024, sin escribir en bases de datos.

Ejecutar desde Fase3:
  python paris2024/scripts/07_transformar_2024.py

Solo cuatro pruebas individuales de tiro con equivalencias verificadas.
Los atletas NO reciben ID histórico inventado y la edición queda pendiente.
"""
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
REPO = BASE.parent.parent
ORIGEN = BASE / 'datos' / 'olympics_dataset.csv'
EVIDENCIA = BASE / 'evidencias'
EVIDENCIA.mkdir(parents=True, exist_ok=True)
CATALOGOS = REPO / 'Fase2' / 'csv-limpios'

# Evento fuente -> evento histórico. Valores cotejados con 2_DEPORTE,
# 6_DISCIPLINA y 9_EVENTO, nunca inferidos por similitud automática.
MAPEO = {
    'Trap Men': 670,
    'Trap Women': 687,
    'Skeet Men': 681,
    'Skeet Women': 724,
}
MEDALLAS = {'Gold': ('Gold', 'ORO'), 'Silver': ('Silver', 'PLATA'),
            'Bronze': ('Bronze', 'BRONCE'), 'No medal': (None, None)}


def cargar_csv(nombre):
    ruta = CATALOGOS / nombre
    if not ruta.exists():
        raise FileNotFoundError(f'Falta catalogo: {ruta}')
    with ruta.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def main():
    deportes = {int(r['ID']): r for r in cargar_csv('2_DEPORTE.csv')}
    disciplinas = {int(r['ID']): r for r in cargar_csv('6_DISCIPLINA.csv')}
    eventos = {int(r['ID']): r for r in cargar_csv('9_EVENTO.csv')}
    medalla_ids = {r['NOMBRE']: int(r['ID']) for r in cargar_csv('4_MEDALLA.csv')}
    ids = {}
    for nombre, evento_id in MAPEO.items():
        e = eventos[evento_id]
        disciplina_id = int(e['ID_DISCIPLINA'])
        di = disciplinas[disciplina_id]
        deporte_id = int(di['ID_DEPORTE'])
        dep = deportes[deporte_id]
        if deporte_id != 24 or dep['NOMBRE'] != 'Shooting':
            raise ValueError(f'Catalogo inconsistente para {nombre}')
        ids[nombre] = (e, di, dep, evento_id, disciplina_id, deporte_id)

    docs = []
    vistos = set()
    conteos = Counter()
    with ORIGEN.open(encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        for fila in reader:
            if (fila['Year'].strip(), fila['Season'].strip(), fila['Sport'].strip()) != ('2024', 'Summer', 'Shooting'):
                continue
            nombre_evento = fila['Event'].strip()
            if nombre_evento not in MAPEO:
                continue
            pid = fila['player_id'].strip()
            noc = fila['NOC'].strip()
            if not pid or not noc:
                raise ValueError(f'ID o NOC vacio: {fila}')
            clave = (nombre_evento, pid)
            if clave in vistos:
                raise ValueError(f'Participacion repetida en origen: {clave}')
            vistos.add(clave)
            medalla_fuente = fila['Medal'].strip()
            if medalla_fuente not in MEDALLAS:
                raise ValueError(f'Medalla inesperada: {medalla_fuente}')
            med_nombre, codigo = MEDALLAS[medalla_fuente]
            e, di, dep, eid, did, depid = ids[nombre_evento]
            # Documento de PREPARACION, no listo para insertar:
            # _id histórico de atleta, id de edición y posibles coincidencias
            # en MongoDB aún deben resolverse sin inventarlos.
            doc = {
                '_id': f'paris2024:shooting:{eid}:{pid}',
                'edicion': {'id': None, 'anio': 2024, 'temporada': 'Summer', 'categoria': 'OLIMPICOS'},
                'deporte': {'id': depid, 'nombre': dep['NOMBRE']},
                'disciplina': {'id': did, 'nombre': di['NOMBRE']},
                'evento': {'id': eid, 'nombre': e['NOMBRE']},
                'posicion': None, 'empate': False, 'estado': None,
                'medalla': ({'id': medalla_ids[med_nombre],
                             'nombre': med_nombre, 'codigo': codigo} if med_nombre else None),
                'atletas': [{'id': None, 'nombre': fila['Name'].strip(), 'noc': noc,
                             'edad': None, 'idFuente2024': pid}],
                'paises': [noc], 'multipais': False, 'paisEquipo': noc,
                'equipoMixto': False, 'revisar': False,
                'fuente': {'dataset': ORIGEN.name, 'eventoOriginal': nombre_evento,
                           'playerIdOriginal': pid},
                'pendienteMapeo': ['edicion.id', 'atletas[0].id'],
            }
            docs.append(doc)
            conteos[nombre_evento] += 1
            conteos[f'medalla:{medalla_fuente}'] += 1

    if not docs:
        raise RuntimeError('No se encontraron filas para las cuatro pruebas')
    salida = EVIDENCIA / 'lote_preliminar_tiro_2024.jsonl'
    with salida.open('w', encoding='utf-8') as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + '\n')
    reporte = {
        'generado_en': datetime.now().astimezone().isoformat(timespec='seconds'),
        'dataset': ORIGEN.name,
        'estado': 'PRELIMINAR_NO_INSERTAR',
        'registros_transformados': len(docs),
        'conteos': dict(conteos),
        'ids_evento_verificados': MAPEO,
        'pendientes': ['resolver identidad de atleta contra MongoDB',
                       'resolver id real de la edicion 2024',
                       'verificar existencia previa para evitar doble carga',
                       'crear y actualizar resúmenes y catálogos'],
        'archivo_salida': salida.name,
    }
    path = EVIDENCIA / 'transformacion_tiro_2024.json'
    path.write_text(json.dumps(reporte, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(reporte, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()