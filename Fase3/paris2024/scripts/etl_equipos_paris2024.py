#!/usr/bin/env python3
"""ETL de equipos Paris 2024, conservador e incremental.
Simulacion por defecto; --aplicar requiere respaldo anterior a la insercion.
Integra un resultado por equipo SIN MEDALLA, preservando integrantes.
Los equipos medallistas, grupos ambiguos e identidades dudosas quedan pendientes.
"""
import argparse
import hashlib
import importlib.util
import json
from collections import Counter, defaultdict
from pathlib import Path
from pymongo import MongoClient, UpdateOne

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / 'evidencias'
BACKUP = ROOT / 'respaldos' / 'antes_etl_equipos.archive.gz'
SCRIPT = Path(__file__).with_name('etl_paris2024_v2.py')
OUT = EVID / 'etl_equipos_reporte.json'
PLAN = EVID / 'etl_equipos_plan.jsonl'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--aplicar', action='store_true')
    parser.add_argument('--mongo', default='mongodb://127.0.0.1:27017/?directConnection=true')
    args = parser.parse_args()
    assert SCRIPT.is_file(), f'Falta ETL v2: {SCRIPT}'
    spec = importlib.util.spec_from_file_location('etl_individual_v2', SCRIPT)
    lib = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lib)
    EVID.mkdir(parents=True, exist_ok=True)
    cli = MongoClient(args.mongo, serverSelectionTimeoutMS=6000)
    cli.admin.command('ping')
    db = cli.olimpiadas_mongo
    assert db.paris2024_fuente.count_documents({}) == 14892
    assert db.resultados.count_documents({'edicion.anio': {'$lt': 2024}}) == 156032
    assert db.paris2024_equipos_preparados.count_documents({}) == 199

    sports = {x['id']: x for x in db.catalogos.find({'tipo':'deporte'})}
    discs = {x['id']: x for x in db.catalogos.find({'tipo':'disciplina'})}
    sidx = defaultdict(set)
    for sid, s in sports.items():
        sidx[lib.sport_key(s['nombre'])].add(sid)
    eidx = defaultdict(dict)
    for e in db.catalogos.find({'tipo':'evento'}):
        sid, did = e.get('deporteId'), e.get('disciplinaId')
        if sid not in sports or did not in discs or discs[did].get('deporteId') != sid:
            continue
        names = {lib.event_key(e['nombre'])}
        prefix = sports[sid]['nombre'].split('(')[0].strip() + ','
        if e['nombre'].casefold().startswith(prefix.casefold()):
            names.add(lib.event_key(e['nombre'][len(prefix):]))
        for nk in names:
            eidx[(sid,nk)][e['id']] = e
    nocs = {p['noc'] for p in db.paises.find({}, {'noc':1}) if p.get('noc')}

    teams = sorted(db.paris2024_equipos_preparados.find({}), key=lambda x:x['_id'])
    source = list(db.paris2024_fuente.find({}, {'atletaFuente':1,'competenciaFuente':1}))
    pids = defaultdict(set)
    for f in source:
        a = f['atletaFuente']; pid = str(a['playerId'])
        pids[pid].add((lib.norm(a['nombre']), a['noc'], str(a['sexo']).upper()))

    # Match athletes with an exact historical (name, NOC, sex, sport) identity.
    relevant_names = {lib.norm(a['nombre']) for t in teams for a in t['atletasFuente']}
    relevant = {a['_id']:a for a in db.atletas.find({}, {'nombre':1,'sexo':1}) if lib.norm(a.get('nombre')) in relevant_names}
    historical = defaultdict(set)
    for r in db.resultados.find({'edicion.anio': {'$lt':2024}}, {'deporte.id':1,'atletas':1}):
        did = r.get('deporte',{}).get('id')
        for athlete in r.get('atletas',[]):
            prof = relevant.get(athlete.get('id'))
            if prof:
                historical[(lib.norm(prof['nombre']),athlete.get('noc'),str(prof.get('sexo') or '').upper(),did)].add(athlete['id'])
    source_historical = defaultdict(set)
    for f in source:
        a,c = f['atletaFuente'],f['competenciaFuente']
        dids = sidx.get(lib.sport_key(c['deporte']),set())
        if len(dids)==1:
            did=next(iter(dids))
            source_historical[str(a['playerId'])].update(historical.get((lib.norm(a['nombre']), a['noc'],str(a['sexo']).upper(),did),set()))
    historical_reverse = defaultdict(set)
    for pid, aids in source_historical.items():
        for aid in aids:
            historical_reverse[aid].add(pid)
    provisional = {}
    for a in db.atletas.find({'fuenteParis2024.playerId':{'$exists':True}}, {'nombre':1,'sexo':1,'fuenteParis2024':1}):
        pid=str(a['fuenteParis2024']['playerId'])
        assert pid not in provisional, f'Duplicated provisional playerId: {pid}'
        provisional[pid]=a
    other_name = defaultdict(set)
    for a in relevant.values():
        other_name[(lib.norm(a['nombre']),str(a.get('sexo') or '').upper())].add(a['_id'])

    used_team_ids = {r.get('fuente',{}).get('equipoPreparadoId') for r in db.resultados.find({'edicion.anio':2024},{'fuente.equipoPreparadoId':1})}
    source_used = {sid for r in db.resultados.find({'edicion.anio':2024},{'fuente.stagingId':1,'fuente.stagingIds':1}) for sid in ([r.get('fuente',{}).get('stagingId')] + r.get('fuente',{}).get('stagingIds',[])) if sid is not None}
    event_country = defaultdict(list)
    for r in db.resultados.find({'edicion.anio':2024},{'evento.id':1,'paisEquipo':1,'atletas.noc':1,'fuente.tipoParticipacion':1}):
        noc=r.get('paisEquipo')
        if noc: event_country[(r.get('evento',{}).get('id'),noc)].append(r)
    source_groups=defaultdict(set)
    for t in teams:
        source_groups[(t['deporteFuente'],t['eventoFuente'],t['noc'])].add(t['_id'])

    next_a=(db.atletas.find_one(sort=[('_id',-1)],projection={'_id':1}) or {'_id':0})['_id']+1
    next_r=(db.resultados.find_one(sort=[('_id',-1)],projection={'_id':1}) or {'_id':0})['_id']+1
    created={}; additions=[]; categories=Counter(); sample_pending=[]
    selected_event_noc=set()
    for t in teams:
        tid=t['_id']; sport=t['deporteFuente']; ev=t['eventoFuente']; noc=t['noc']
        reason=None
        if tid in used_team_ids:
            reason='YA_INTEGRADO'
        elif t['medallaFuente']!='No medal':
            reason='MEDALLA_PENDIENTE_VERIFICACION'
        elif len(source_groups[(sport,ev,noc)]) != 1:
            reason='MULTIPLES_EQUIPOS_MISMO_PAIS_EVENTO'
        elif noc not in nocs:
            reason='NOC_NO_EN_CATALOGO'
        elif len(sidx.get(lib.sport_key(sport),set()))!=1:
            reason='DEPORTE_AMBIGUO'
        else:
            did=next(iter(sidx[lib.sport_key(sport)]))
            opts=list(eidx.get((did,lib.event_key(ev)),{}).values())
            if len(opts)!=1:
                reason='EVENTO_NO_UNICO'
            else:
                e=opts[0]; eid=e['id']
                if (eid,noc) in event_country or (eid,noc) in selected_event_noc:
                    reason='RESULTADO_EVENTO_PAIS_EXISTENTE'
                elif any(sid in source_used for sid in t['stagingIds']):
                    reason='FILAS_FUENTE_YA_INTEGRADAS'
                else:
                    members=[]; needed=[]
                    for a in t['atletasFuente']:
                        pid=str(a['playerId']); sex=str(a['sexo']).upper()
                        name=a['nombre']
                        aid=None
                        if len(pids[pid])!=1 or sex not in ('M','F') or a['noc']!=noc:
                            reason='IDENTIDAD_FUENTE_INCONSISTENTE';break
                        if sex=='M' and 'women' in lib.norm(ev).split() or sex=='F' and 'men' in lib.norm(ev).split():
                            reason='SEXO_EVENTO_INCOMPATIBLE';break
                        h=historical.get((lib.norm(name),noc,sex,did),set())
                        if len(h)>1 or len(source_historical[pid])>1:
                            reason='IDENTIDAD_HISTORICA_AMBIGUA';break
                        if len(h)==1:
                            aid=next(iter(h))
                            if source_historical[pid]!={aid} or historical_reverse[aid]!={pid}:
                                reason='IDENTIDAD_HISTORICA_COMPARTIDA';break
                            label=relevant[aid]['nombre']
                        elif source_historical[pid]:
                            reason='HISTORICO_DE_OTRO_DEPORTE';break
                        elif pid in provisional:
                            p=provisional[pid]; meta=p['fuenteParis2024']
                            if (lib.norm(p['nombre']),str(p['sexo']).upper(),meta.get('noc'))!=(lib.norm(name),sex,noc):
                                reason='PERFIL_PROVISIONAL_INCONSISTENTE';break
                            aid=p['_id'];label=p['nombre']
                        elif other_name.get((lib.norm(name),sex)):
                            reason='POTENCIAL_HOMONIMO';break
                        else:
                            if pid not in created:
                                created[pid]={'_id':next_a+len(created),'nombre':name,'sexo':sex,
                                    'fuenteParis2024':{'playerId':pid,'noc':noc,'identidadProvisional':True},
                                    'resumen':{'participaciones':0,'juegos':0,'anios':[], 'deportes':[], 'medallas':lib.medal_zero()}}
                            aid=created[pid]['_id'];label=name;needed.append(pid)
                        if any(m['id']==aid for m in members):
                            reason='DUPLICADO_PERFIL_EN_EQUIPO';break
                        members.append({'id':aid,'nombre':label,'noc':noc,'edad':None})
                    if reason is None and len(members)<2:
                        reason='POCOS_INTEGRANTES'
                    if reason is None:
                        selected_event_noc.add((eid,noc))
                        additions.append({'_id':next_r+len(additions),
                            'edicion':{'id':63,'anio':2024,'temporada':'Summer','categoria':'Senior'},
                            'deporte':{'id':did,'nombre':sports[did]['nombre']},
                            'disciplina':{'id':e['disciplinaId'],'nombre':discs[e['disciplinaId']]['nombre']},
                            'evento':{'id':eid,'nombre':e['nombre']},
                            'posicion':None,'empate':False,'equipoMixto':False,
                            'estado':'PENDING_VERIFICATION','medalla':None,
                            'multipais':False,'paisEquipo':noc,'paises':[noc],
                            'atletas':members,'revisar':True,
                            'fuente':{'dataset':'olympics_dataset.csv','equipoPreparadoId':tid,
                                'stagingIds':t['stagingIds'],'equipoOriginal':t['equipoFuente'],
                                'eventoOriginal':ev,'mapeo':'exacto_unico',
                                'tipoParticipacion':'equipo','etlMotor':'equipos_v1',
                                'posicionVerificada':False,'estadoVerificado':False}})
                        reason='PREPARADO'
        categories[reason]+=1
        if reason not in ('PREPARADO','YA_INTEGRADO') and len(sample_pending)<30:
            sample_pending.append({'equipo':tid,'deporte':sport,'evento':ev,'noc':noc,'razon':reason})
    referenced={a['id'] for r in additions for a in r['atletas']}
    new_profiles=[p for p in created.values() if p['_id'] in referenced]
    report={'equipos_origen':len(teams),'resultados_2024_antes':db.resultados.count_documents({'edicion.anio':2024}),
        'nuevos_resultados':len(additions),'nuevos_perfiles':len(new_profiles),
        'integrantes_en_resultados':sum(len(x['atletas']) for x in additions),
        'clasificacion':dict(categories),'pendientes_ejemplo':sample_pending,'modo':'APLICAR' if args.aplicar else 'SIMULACION'}
    assert sum(categories.values())==len(teams)
    PLAN.write_text(''.join(json.dumps(x,ensure_ascii=False)+'\n' for x in additions),encoding='utf-8')
    OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print('\n=== ETL COLECTIVO PARIS 2024 ===')
    print('Equipos:',len(teams),'| Resultados adicionales:',len(additions))
    print('Integrantes vinculados:',report['integrantes_en_resultados'],'| Perfiles nuevos:',len(new_profiles))
    print('Clasificacion:')
    for reason,count in categories.most_common():print(' ',reason+':',count)
    print('Plan:',PLAN,'\nReporte:',OUT)
    if not args.aplicar:
        print('SIMULACION: MongoDB no modificado. Se requiere respaldo actualizado para --aplicar.')
        return
    assert BACKUP.is_file() and BACKUP.stat().st_size>1000000, f'Falta respaldo: {BACKUP}'
    # Reject outdated backup: filesystem modification time must be recent enough
    # to cover already-existing Paris results. User explicitly creates it before applying.
    for p in new_profiles:
        assert db.atletas.find_one({'_id':p['_id']}) is None
        assert db.atletas.find_one({'fuenteParis2024.playerId':p['fuenteParis2024']['playerId']}) is None
    for r in additions:
        assert db.resultados.find_one({'_id':r['_id']}) is None
        assert db.resultados.find_one({'fuente.equipoPreparadoId':r['fuente']['equipoPreparadoId']}) is None
        assert db.resultados.find_one({'edicion.anio':2024,'evento.id':r['evento']['id'],'paisEquipo':r['paisEquipo']}) is None
        assert db.resultados.find_one({'fuente.stagingId':{'$in':r['fuente']['stagingIds']}}) is None
    if new_profiles:db.atletas.insert_many(new_profiles,ordered=True)
    for start in range(0,len(additions),100):
        batch=additions[start:start+100]
        db.resultados.insert_many(batch,ordered=True)
        print('Insertados:',start+len(batch),'/',len(additions))
    aids=sorted(referenced)
    for start in range(0,len(aids),200):
        ops=[UpdateOne({'_id':aid},{'$set':{'resumen':lib.athlete_summary(db,aid)}}) for aid in aids[start:start+200]]
        if ops:db.atletas.bulk_write(ops,ordered=False)
    nocs_aff=sorted({r['paisEquipo'] for r in additions})
    for noc in nocs_aff:
        db.paises.update_one({'noc':noc},{'$set':{'resumen':lib.country_summary(db,noc)}})
    for t in additions:
        db.paris2024_equipos_preparados.update_one({'_id':t['fuente']['equipoPreparadoId']},
            {'$set':{'integracion.estado':'INTEGRADO_PROVISIONAL',
                'integracion.resultadoId':t['_id'],'integracion.eventoId':t['evento']['id'],
                'integracion.identidadesVerificadas':False}})
    assert db.resultados.count_documents({'edicion.anio':{'$lt':2024}})==156032
    print('\nCARGA COLECTIVA EXITOSA. Nuevos:',len(additions),
          '| Paris 2024:',db.resultados.count_documents({'edicion.anio':2024}))
    cli.close()

if __name__=='__main__':main()
