#!/usr/bin/env python3
"""Auditoría SIN ESCRITURA A BASES: compara París 2024 con CSV históricos."""
import csv
import json
import sys
import unicodedata
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]  # paris2024/
REPO = BASE.parents[1]                      # raíz del repositorio
FUENTE = BASE / 'datos' / 'olympics_dataset.csv'
HIST = REPO / 'Fase2' / 'csv-limpios'
SALIDA = BASE / 'evidencias' / 'mapeo_2024.json'


def normalizar(v):
    s = unicodedata.normalize('NFKD', str(v or '').strip())
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    s = s.translate(str.maketrans({'ø':'o','æ':'ae','œ':'oe','ß':'ss','ł':'l'}))
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', s)).strip()


def leer(ruta):
    if not ruta.is_file():
        raise FileNotFoundError(f'No se encontró: {ruta}')
    with ruta.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def indexar(filas, clave):
    index = defaultdict(set)
    for fila in filas:
        index[normalizar(fila[clave])].add(int(fila['ID']))
    return index


def estado(index, valor):
    ids = sorted(index.get(normalizar(valor), set()))
    return ('unico' if len(ids) == 1 else 'ambiguo' if ids else 'sin_coincidencia', ids)


def main():
    filas = [f for f in leer(FUENTE) if f['Year'].strip() == '2024' and f['Season'].strip().lower() == 'summer']
    deportes = indexar(leer(HIST / '2_DEPORTE.csv'), 'NOMBRE')
    eventos = indexar(leer(HIST / '9_EVENTO.csv'), 'NOMBRE')
    atletas = indexar(leer(HIST / '10_ATLETA.csv'), 'NOMBRE')
    paises = {r['NOC'].strip().upper(): int(r['ID']) for r in leer(HIST / '1_PAIS.csv') if r['NOC'].strip()}

    # player_id de esta fuente NO equivale al ID de PostgreSQL; comparar nombres
    # es solo diagnóstico y NO autoriza fusionar personas automáticamente.
    jugadores = {(f['player_id'], f['Name']) for f in filas}
    sports = {f['Sport'] for f in filas}
    events = {f['Event'] for f in filas}
    nocs = {f['NOC'].strip().upper() for f in filas}
    detalle = {}
    for tipo, elementos, indice in [
        ('deportes', sports, deportes), ('eventos', events, eventos),
        ('atletas_por_nombre', {nombre for _, nombre in jugadores}, atletas)
    ]:
        contadores = Counter()
        pendientes = []
        for nombre in sorted(elementos):
            e, ids = estado(indice, nombre)
            contadores[e] += 1
            if e != 'unico':
                pendientes.append({'nombre_fuente': nombre, 'estado': e, 'ids_candidatos': ids})
        detalle[tipo] = {'conteos': dict(contadores), 'pendientes': pendientes}

    reporte = {
        'generado_en': datetime.now().astimezone().isoformat(timespec='seconds'),
        'tipo': 'auditoria_solo_lectura',
        'registros_2024': len(filas),
        'jugadores_por_player_id': len({f['player_id'] for f in filas}),
        'noc': {'total': len(nocs), 'sin_correspondencia': sorted(n for n in nocs if n not in paises)},
        **detalle,
        'advertencias': [
            'Coincidencia por nombre no demuestra identidad del atleta.',
            'Evento y deporte requieren revisión semántica de alias.',
            'Los registros del CSV son atleta-evento, no resultados únicos ni medallas oficiales.',
            'Este script no modifica PostgreSQL ni MongoDB.'
        ]
    }
    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps(reporte, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Registros de París 2024:', len(filas))
    print('NOC sin correspondencia:', reporte['noc']['sin_correspondencia'])
    for tipo in ('deportes', 'eventos', 'atletas_por_nombre'):
        print(tipo, reporte[tipo]['conteos'])
    print('Evidencia:', SALIDA)

if __name__ == '__main__':
    try:
        main()
    except (FileNotFoundError, KeyError, ValueError) as e:
        print('ERROR:', e, file=sys.stderr)
        sys.exit(1)
