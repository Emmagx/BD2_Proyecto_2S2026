#!/usr/bin/env python3
"""Propone equivalencias por deporte + nombre de evento; NO modifica bases de datos.
Ejecutar desde Fase3: python paris2024/scripts/06_proponer_equivalencias_eventos.py
"""
import csv
import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parent.parent
HIST = REPO / 'Fase2' / 'csv-limpios'
EVID = BASE / 'evidencias'

def leer(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def norm(s):
    s = unicodedata.normalize('NFKD',str(s or '').lower())
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r'\bmetres\b','m',s)
    s = re.sub(r'\bmeters\b','m',s)
    s = re.sub(r"\bmen's\b|\bmen\b",' masculino ',s)
    s = re.sub(r"\bwomen's\b|\bwomen\b",' femenino ',s)
    s = re.sub(r'\b(olympic|olympics)\b','',s)
    s = re.sub(r'[^a-z0-9]+',' ',s)
    return ' '.join(s.split())

def tokens(s):
    return set(norm(s).split()) - {'the','of','and','individual'}

def score(a,b):
    ta,tb=tokens(a),tokens(b)
    jac=len(ta & tb)/len(ta | tb) if ta|tb else 0
    return round(0.65*jac+0.35*SequenceMatcher(None,norm(a),norm(b)).ratio(),4)

D={int(x['ID']):x['NOMBRE'] for x in leer(HIST/'2_DEPORTE.csv')}
DI={int(x['ID']):x for x in leer(HIST/'6_DISCIPLINA.csv')}
EV=leer(HIST/'9_EVENTO.csv')
source=leer(EVID/'revision_disciplinas_eventos_2024.csv')
revised=leer(EVID/'revision_deportes_2024_anotada.csv')
# Solo identificadores propuestos, nunca confirmados automáticamente.
propuestas={}
for row in revised:
    raw=row.get('id_historico_exacto') or row.get('id_propuesto') or ''
    try:
        propuestas[row['deporte_2024']]=int(float(raw))
    except ValueError:
        pass
# Por evento, los nombres "Sport" multivalor se cotejan con cada deporte candidato.
by_sport=defaultdict(list)
for e in EV:
    disciplina=DI[int(e['ID_DISCIPLINA'])]
    id_dep=int(disciplina['ID_DEPORTE'])
    by_sport[id_dep].append((e,disciplina))

salida=[]
for r in source:
    sport=r['sport_2024']
    event=r['evento_2024']
    possibilities=[]
    names=[sport] if ',' not in sport else [s.strip() for s in sport.split(',')]
    for name in names:
        id_dep=propuestas.get(name)
        if id_dep is None:
            # Comparación del nombre principal frente a "Foo (Category)"
            cand=[did for did,dname in D.items() if norm(dname.split(' (')[0])==norm(name)]
            if len(cand)==1: id_dep=cand[0]
        if id_dep is None: continue
        for e,di in by_sport[id_dep]:
            sc=score(event,e['NOMBRE'])
            possibilities.append((sc,id_dep,e,di))
    possibilities.sort(key=lambda x:x[0],reverse=True)
    top=possibilities[:3]
    rec=dict(r)
    rec.update({
      'candidatos_deporte_evento':len(possibilities),
      'sugerencias': ' | '.join(f"puntaje={sc:.3f}; dep={did} ({D[did]}); disc={di['ID']} ({di['NOMBRE']}); evento={e['ID']} ({e['NOMBRE']})" for sc,did,e,di in top),
      'puntaje_mejor':top[0][0] if top else '',
      'decision_manual':'PENDIENTE',
    })
    salida.append(rec)

out=EVID/'propuestas_equivalencias_eventos_2024.csv'
with out.open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(salida[0]));w.writeheader();w.writerows(salida)
print('Fecha:',datetime.now().astimezone().isoformat(timespec='seconds'))
print('Combinaciones:',len(salida))
print('Con candidatos:',sum(bool(x['candidatos_deporte_evento']) for x in salida))
print('Sin candidatos:',sum(not x['candidatos_deporte_evento'] for x in salida))
print('Archivo:',out)
print('AVISO: el puntaje NO confirma la equivalencia; los campos confirmados permanecen vacíos.')