#!/usr/bin/env python3
"""Reconcile already inserted Paris 2024 team results with staging metadata.
Dry run by default. --aplicar only updates metadata for verified matches.
"""
import argparse
from collections import Counter
from pymongo import MongoClient, UpdateOne

p=argparse.ArgumentParser()
p.add_argument('--aplicar', action='store_true')
a=p.parse_args()
c=MongoClient('mongodb://127.0.0.1:27017/?directConnection=true',serverSelectionTimeoutMS=8000)
c.admin.command('ping'); db=c.olimpiadas_mongo
assert db.resultados.count_documents({'edicion.anio': {'$lt':2024}})==156032
assert db.resultados.count_documents({'edicion.anio':2024})==4212
assert db.resultados.count_documents({})==160244
assert db.atletas.count_documents({})==149081
assert db.paris2024_equipos_preparados.count_documents({})==199
teams={t['_id']:t for t in db.paris2024_equipos_preparados.find({})}
results=list(db.resultados.find({'edicion.anio':2024,'fuente.etlMotor':'equipos_v1'}))
assert len(results)==131, f'Esperados 131 resultados colectivos, encontrados {len(results)}'
counts=Counter(); seen=set(); fixes=[]; affected_aids=set(); affected_nocs=set(); errors=[]
for r in results:
    tid=r.get('fuente',{}).get('equipoPreparadoId')
    t=teams.get(tid)
    if t is None or tid in seen:
        errors.append(f'Equipo faltante o repetido: {tid}');continue
    seen.add(tid)
    ids=[m.get('id') for m in r.get('atletas',[])]
    if (len(ids)!=len(set(ids)) or None in ids or
        len(ids)!=t.get('numeroIntegrantes') or
        r.get('paisEquipo')!=t.get('noc') or
        t.get('medallaFuente')!='No medal' or
        r.get('medalla') is not None or r.get('revisar') is not True or
        r.get('estado')!='PENDING_VERIFICATION'):
        errors.append(f'Inconsistencia del resultado colectivo {r.get("_id")} equipo {tid}');continue
    affected_aids.update(ids); affected_nocs.add(r['paisEquipo'])
    integ=t.get('integracion') or {}
    if (integ.get('estado')=='INTEGRADO_PROVISIONAL' and
        integ.get('resultadoId')==r['_id'] and
        integ.get('eventoId')==r.get('evento',{}).get('id')):
        counts['YA_CONCILIADO']+=1
    else:
        counts['METADATOS_PENDIENTES']+=1
        fixes.append(UpdateOne({'_id':tid},{'$set':{'integracion.estado':'INTEGRADO_PROVISIONAL',
               'integracion.resultadoId':r['_id'],'integracion.eventoId':r['evento']['id'],
               'integracion.identidadesVerificadas':False}}))

pending=[t for tid,t in teams.items() if tid not in seen]
assert len(pending)==68, f'Se esperaban 68 equipos no integrados, hay {len(pending)}'
print('\n=== RECONCILIACION DE EQUIPOS PARIS 2024 ===')
print('Resultados colectivos encontrados:',len(results))
print('Ya conciliados:',counts['YA_CONCILIADO'])
print('Metadatos para corregir:',counts['METADATOS_PENDIENTES'])
print('Pendientes reales:',len(pending))
print('De ellos, medallistas:',sum(t['medallaFuente']!='No medal' for t in pending))
print('Atletas afectados por la carga:',len(affected_aids),'| Paises:',len(affected_nocs))
print('Errores de integridad:',len(errors))
for err in errors[:15]:print('  -',err)
if errors:
    print('No se modifica MongoDB: hay errores de integridad.');raise SystemExit(2)
if a.aplicar:
    if fixes:db.paris2024_equipos_preparados.bulk_write(fixes,ordered=False)
    assert db.paris2024_equipos_preparados.count_documents({'integracion.estado':'INTEGRADO_PROVISIONAL'})==131
    print('METADATOS CONCILIADOS. Los resultados, atletas y medallas NO fueron modificados.')
    print('IMPORTANTE: esta conciliacion no recalcula resumenes de atletas/paises; una interrupcion previa pudo dejarlos desactualizados.')
else:
    print('SIMULACION: MongoDB NO se modifico. Ejecuta --aplicar para reconciliar el seguimiento.')
c.close()
