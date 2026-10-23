#!/usr/bin/env python3
"""Cierre verificable de la carga Paris 2024. Solo lectura en MongoDB.
Ejecutar desde Fase3: python paris2024/scripts/50_cierre_paris2024.py
"""
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from pymongo import MongoClient

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / 'evidencias'
EVID.mkdir(parents=True, exist_ok=True)

client = MongoClient('mongodb://127.0.0.1:27017/?directConnection=true', serverSelectionTimeoutMS=8000)
client.admin.command('ping')
db = client.olimpiadas_mongo

counts = {
 'resultados_historicos': db.resultados.count_documents({'edicion.anio': {'$lt': 2024}}),
 'resultados_paris2024': db.resultados.count_documents({'edicion.anio': 2024}),
 'resultados_totales': db.resultados.count_documents({}),
 'atletas_totales': db.atletas.count_documents({}),
 'paises_totales': db.paises.count_documents({}),
 'catalogos_totales': db.catalogos.count_documents({}),
 'fuente_paris2024': db.paris2024_fuente.count_documents({}),
 'equipos_preparados': db.paris2024_equipos_preparados.count_documents({}),
}
expected = {
 'resultados_historicos':156032,
 'resultados_paris2024':4212,
 'resultados_totales':160244,
 'atletas_totales':149081,
 'fuente_paris2024':14892,
 'equipos_preparados':199,
}
failures = [f'{k}: esperado {v}, real {counts[k]}' for k,v in expected.items() if counts[k]!=v]

# Verificar los 131 resultados colectivos, su relacion con el staging y la consistencia del estado.
teams = list(db.paris2024_equipos_preparados.find({}, {
 '_id':1, 'deporteFuente':1,'eventoFuente':1,'noc':1,'equipoFuente':1,
 'medallaFuente':1, 'numeroIntegrantes':1,'integracion':1
}))
by_status = Counter(t.get('integracion',{}).get('estado','SIN_ESTADO') for t in teams)
team_results = list(db.resultados.find({'edicion.anio':2024,'fuente.etlMotor':'equipos_v1'}, {
 '_id':1,'fuente.equipoPreparadoId':1,'atletas.id':1,'evento.id':1,'paisEquipo':1,
 'medalla':1,'revisar':1,'estado':1,
}))
team_map = {t['_id']:t for t in teams}
seen_teams = Counter()
collective_athletes = 0
for r in team_results:
    tid = r.get('fuente',{}).get('equipoPreparadoId')
    seen_teams[tid] += 1
    t = team_map.get(tid)
    if t is None:
        failures.append(f'Resultado {r["_id"]} refiere equipo inexistente {tid}')
        continue
    if t.get('integracion',{}).get('resultadoId') != r['_id']:
        failures.append(f'Equipo {tid}: resultadoId de integracion distinto')
    if t.get('integracion',{}).get('eventoId') != r.get('evento',{}).get('id'):
        failures.append(f'Equipo {tid}: eventoId de integracion distinto')
    if t.get('noc') != r.get('paisEquipo'):
        failures.append(f'Equipo {tid}: NOC distinto')
    if t.get('medallaFuente') != 'No medal':
        failures.append(f'Equipo medallista {tid} agregado como no medallista')
    if r.get('medalla') is not None or r.get('revisar') is not True:
        failures.append(f'Resultado colectivo {r["_id"]} tiene medalla o estado no provisional')
    ids = [a['id'] for a in r.get('atletas',[]) if 'id' in a]
    if len(ids) != t.get('numeroIntegrantes') or len(ids) != len(set(ids)):
        failures.append(f'Resultado colectivo {r["_id"]}: integrantes inconsistentes')
    collective_athletes += len(ids)
for tid,n in seen_teams.items():
    if n!=1: failures.append(f'Equipo {tid} tiene {n} resultados')
for t in teams:
    integ=t.get('integracion',{})
    if integ.get('estado') == 'INTEGRADO_PROVISIONAL' and seen_teams[t['_id']]!=1:
        failures.append(f'Equipo {t["_id"]}: integrado sin resultado unico')

# Todos los no-integrados quedan en una hoja de pendientes con causa observable.
pendientes=[]
for t in teams:
    if t.get('integracion',{}).get('estado') == 'INTEGRADO_PROVISIONAL':
        continue
    pendientes.append({
        'equipo_id':t['_id'], 'deporte':t.get('deporteFuente',''),
        'evento':t.get('eventoFuente',''),'noc':t.get('noc',''),
        'equipo':t.get('equipoFuente',''),'integrantes':t.get('numeroIntegrantes',0),
        'medalla_origen':t.get('medallaFuente',''),
        'estado_integracion':t.get('integracion',{}).get('estado',''),
        'revision': 'Medalla e identidades/duplicados por verificar' if t.get('medallaFuente')!='No medal' else 'Identidad ambigua u otra validacion pendiente'
    })
pendientes.sort(key=lambda x:(x['revision'],x['deporte'],x['evento'],x['noc']))

# Comprobar la procedencia de las 131 cargas colectivas sin reconstruir medallas.
if len(team_results)!=131:
    failures.append(f'Resultados colectivos cargados: esperado 131, real {len(team_results)}')
if collective_athletes!=1607:
    failures.append(f'Integrantes en resultados colectivos: esperado 1607, real {collective_athletes}')
if len(pendientes)!=68:
    failures.append(f'Equipos sin integrar: esperado 68, real {len(pendientes)}')

csv_path = EVID/'pendientes_equipos_paris2024.csv'
with csv_path.open('w',encoding='utf-8-sig',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=['equipo_id','deporte','evento','noc','equipo','integrantes','medalla_origen','estado_integracion','revision'])
    writer.writeheader();writer.writerows(pendientes)

report={
 'generado':datetime.now().astimezone().isoformat(),
 'tipo':'Cierre tecnico de carga incremental; no certificacion de resultados deportivos',
 'conteos':counts,
 'equipos':{'cargados':len(team_results),'integrantes_referenciados':collective_athletes,'por_estado':dict(by_status), 'sin_integrar':len(pendientes),
           'pendientes_medallistas':sum(p['medalla_origen']!='No medal' for p in pendientes)},
 'validaciones':{'exitosas':not failures,'errores':failures},
 'advertencias':['Los 14,892 registros de fuente son participaciones atleta-evento, no resultados independientes.',
 'Resultados 2024 provisionales conservan estado por verificar; no constituyen clasificaciones oficiales completas.',
 'La consistencia de conteos y referencias no equivale a verificacion deportiva de medallas, posiciones o identidades.',
 'No volver a ejecutar --aplicar sobre cargas ya confirmadas sin auditoria y respaldo actualizado.'],
 'documentos_salida':{'pendientes_csv':str(csv_path)}
}
json_path=EVID/'cierre_paris2024.json'
json_path.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
md_path=EVID/'CIERRE_PARIS2024.md'
lines=['# Cierre tecnico - Integracion Paris 2024','',f'Fecha de verificacion: {report["generado"]}','','## Estado de MongoDB','', '| Indicador | Cantidad |','|---|---:|']
for k,v in counts.items():lines.append(f'| {k.replace("_"," ").capitalize()} | {v:,} |')
lines += ['', '## Resultados colectivos', '',f'- Equipos inicialmente preparados: {len(teams)}.',f'- Resultados colectivos cargados: {len(team_results)}.',f'- Integrantes referenciados por resultados colectivos: {collective_athletes}.', f'- Equipos pendientes: {len(pendientes)}.',f'- Equipos medallistas pendientes: {report["equipos"]["pendientes_medallistas"]}.','', '## Alcance y limitaciones', '', 'La carga incremental agrega participaciones estructuradas a MongoDB y conserva los registros historicos. Las filas fuente no equivalen a resultados independientes. Los resultados provisionales no implican clasificaciones oficiales completas ni validacion de medallas o identidades.','', '## Evidencias','', '- `cierre_paris2024.json`: conteos y verificaciones automaticas.', '- `pendientes_equipos_paris2024.csv`: casos no integrados para revision.', '- Respaldos creados antes de las cargas anteriores en `paris2024/respaldos/`.','', f'## Estado de verificacion: {"CORRECTO" if not failures else "REVISAR"}', '']
if failures: lines += ['### Problemas detectados',''] + [f'- {x}' for x in failures]
md_path.write_text('\n'.join(lines),encoding='utf-8')

print('\n=== CIERRE PARIS 2024 (SOLO LECTURA) ===')
for k,v in counts.items(): print(f'{k}: {v}')
print('Resultados colectivos cargados:',len(team_results),'| Integrantes:',collective_athletes)
print('Equipos pendientes:',len(pendientes),'| Medallistas pendientes:',report['equipos']['pendientes_medallistas'])
print('Validaciones:', 'EXITOSAS' if not failures else 'REVISAR')
for f in failures[:20]:print('  -',f)
print('Reporte:',json_path)
print('Pendientes:',csv_path)
print('Informe:',md_path)
print('MongoDB NO fue modificado.')
client.close()
if failures:raise SystemExit(2)
