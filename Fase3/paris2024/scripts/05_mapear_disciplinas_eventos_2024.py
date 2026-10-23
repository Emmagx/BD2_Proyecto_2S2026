#!/usr/bin/env python3
"""Audita eventos París 2024 frente a DEPORTE/DISCIPLINA/EVENTO históricos.
SOLO LECTURA. No asigna IDs automáticamente ni modifica PostgreSQL/MongoDB.
Ejecutar desde Fase3: python paris2024/scripts/05_mapear_disciplinas_eventos_2024.py
"""
import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parent.parent
DATOS = BASE / 'datos' / 'olympics_dataset.csv'
EVIDENCIAS = BASE / 'evidencias'
CATALOGOS = REPO / 'Fase2' / 'csv-limpios'


def leer_csv(ruta):
    with ruta.open('r', encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def norm(s):
    s = unicodedata.normalize('NFKD', str(s or '').lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', s)).strip()


def main():
    EVIDENCIAS.mkdir(exist_ok=True)
    for ruta in [DATOS, CATALOGOS/'2_DEPORTE.csv', CATALOGOS/'6_DISCIPLINA.csv', CATALOGOS/'9_EVENTO.csv']:
        if not ruta.is_file():
            raise SystemExit(f'No existe: {ruta}')

    deportes = {int(d['ID']):d['NOMBRE'] for d in leer_csv(CATALOGOS/'2_DEPORTE.csv')}
    disciplinas = {int(d['ID']):d for d in leer_csv(CATALOGOS/'6_DISCIPLINA.csv')}
    eventos = leer_csv(CATALOGOS/'9_EVENTO.csv')
    indice = defaultdict(list)
    for e in eventos:
        di = disciplinas.get(int(e['ID_DISCIPLINA']))
        if not di:
            continue
        did = int(di['ID_DEPORTE'])
        ficha = {'id_evento':int(e['ID']), 'evento':e['NOMBRE'],
                 'id_disciplina':int(di['ID']), 'disciplina':di['NOMBRE'],
                 'id_deporte':did, 'deporte':deportes.get(did, '')}
        indice[norm(e['NOMBRE'])].append(ficha)

    filas = [r for r in leer_csv(DATOS) if r['Year'].strip() == '2024' and r['Season'].strip().lower() == 'summer']
    pares = Counter((r['Sport'].strip(), r['Event'].strip()) for r in filas)
    salida = []
    estados = Counter()
    for (sport, evento), numero in sorted(pares.items()):
        candidatos = indice.get(norm(evento), [])
        if not candidatos:
            estado = 'SIN_COINCIDENCIA_EXACTA'
        elif len(candidatos) == 1:
            estado = 'UN_CANDIDATO_POR_NOMBRE'
        else:
            estado = 'MULTIPLES_CANDIDATOS'
        estados[estado] += 1
        salida.append({
            'sport_2024':sport, 'evento_2024':evento, 'participaciones':numero,
            'estado':estado, 'cantidad_candidatos':len(candidatos),
            'candidatos_historicos':json.dumps(candidatos[:12], ensure_ascii=False),
            'id_deporte_confirmado':'', 'id_disciplina_confirmado':'',
            'id_evento_confirmado':'', 'accion_confirmada':'',
            'observaciones':'',
        })

    archivo = EVIDENCIAS / 'revision_disciplinas_eventos_2024.csv'
    with archivo.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(salida[0].keys()))
        writer.writeheader()
        writer.writerows(salida)

    reporte = {
        'generado_en':datetime.now().astimezone().isoformat(timespec='seconds'),
        'origen':DATOS.name,
        'registros_2024':len(filas),
        'eventos_distintos_por_nombre':len({e for _, e in pares}),
        'pares_sport_evento':len(pares),
        'conteos_estados':dict(estados),
        'archivo_csv':archivo.name,
        'nota':'Una coincidencia de nombre NO valida identidad: requiere verificar deporte y disciplina. Sin inserciones.'
    }
    (EVIDENCIAS/'revision_disciplinas_eventos_2024.json').write_text(
        json.dumps(reporte, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(reporte, ensure_ascii=False, indent=2))
    print('CSV:', archivo)

if __name__ == '__main__':
    main()
