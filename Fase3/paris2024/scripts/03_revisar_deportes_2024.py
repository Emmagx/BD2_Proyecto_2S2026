#!/usr/bin/env python3
"""Genera revisión manual de nombres de deportes de París 2024. Solo lectura."""
import csv
import difflib
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
HIST = BASE.parents[1] / 'Fase2' / 'csv-limpios'
ORIGEN = BASE / 'datos' / 'olympics_dataset.csv'
EVIDENCIA = BASE / 'evidencias' / 'revision_deportes_2024.csv'

def normalizar(valor):
    s = unicodedata.normalize('NFKD', str(valor or '').strip())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = s.lower().translate(str.maketrans({'ø':'o','æ':'ae','œ':'oe','ß':'ss','ł':'l'}))
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', s)).strip()

def leer(ruta):
    with ruta.open(encoding='utf-8-sig', newline='') as f:
        yield from csv.DictReader(f)

def main():
    conteos = Counter(f['Sport'] for f in leer(ORIGEN)
                      if f['Year'].strip() == '2024' and f['Season'].strip().lower() == 'summer')
    historicos = list(leer(HIST / '2_DEPORTE.csv'))
    por_normalizado = defaultdict(list)
    for h in historicos:
        por_normalizado[normalizar(h['NOMBRE'])].append(h)
    claves = list(por_normalizado)
    EVIDENCIA.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCIA.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=[
            'deporte_2024','participaciones','estado','id_historico_exacto',
            'sugerencia_1','sugerencia_2','sugerencia_3','id_confirmado','observaciones'])
        w.writeheader()
        pendientes = 0
        for nombre, total in sorted(conteos.items()):
            encontrados = por_normalizado.get(normalizar(nombre), [])
            if len(encontrados) == 1:
                estado, ident = 'COINCIDENCIA_EXACTA', encontrados[0]['ID']
            else:
                estado, ident = ('AMBIGUO' if encontrados else 'REVISAR'), ''
                pendientes += 1
            cercanos = difflib.get_close_matches(normalizar(nombre), claves, n=3, cutoff=0.35)
            sugerencias = [f"{h['NOMBRE']} (ID {h['ID']})" for k in cercanos for h in por_normalizado[k]][:3]
            sugerencias += [''] * (3 - len(sugerencias))
            w.writerow(dict(deporte_2024=nombre, participaciones=total, estado=estado,
                            id_historico_exacto=ident, sugerencia_1=sugerencias[0],
                            sugerencia_2=sugerencias[1], sugerencia_3=sugerencias[2],
                            id_confirmado='', observaciones=''))
    print(f'Deportes de París 2024: {len(conteos)}')
    print(f'Deportes por revisar: {pendientes}')
    print(f'Generado en: {datetime.now().astimezone().isoformat(timespec="seconds")}')
    print(f'Archivo de revisión: {EVIDENCIA}')
    print('AVISO: las sugerencias son aproximadas; NO representan equivalencias confirmadas.')

if __name__ == '__main__':
    main()
