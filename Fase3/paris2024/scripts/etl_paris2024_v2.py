#!/usr/bin/env python3
"""ETL incremental Paris 2024. Default: dry-run. --aplicar: writes.

Safely integrates individual, no-medal participations with unique exact event mapping,
existing historical athlete identity or a clearly new provisional profile.
Ambiguous athletes, medals, teams and unrecognized events remain in the report.
Idempotent by source staging ID and resumable after interrupted Mongo bulk operations.
"""
import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from pymongo import MongoClient, UpdateOne

ROOT = Path(__file__).resolve().parents[1]
EVID = ROOT / 'evidencias'
OUT = EVID / 'etl_general_paris2024_reporte.json'
PLAN = EVID / 'etl_general_paris2024_plan.jsonl'
BACKUP = ROOT / 'respaldos' / 'antes_etl_v2.archive.gz'

# Conservative positive selection: one human competes for one result.
# Avoid generic sport-wide inclusion for events that might be pairs/teams.
ALLOW = {
    'Athletics': lambda x: not has_team(x),
    'Swimming': lambda x: not has_team(x),
    'Artistic Gymnastics': lambda x: not has_team(x),
    'Shooting': lambda x: not has_team(x),
    'Judo': lambda x: not has_team(x),
    'Fencing': lambda x: not has_team(x),
    'Wrestling': lambda x: not has_team(x),
    'Boxing': lambda x: not has_team(x),
    'Taekwondo': lambda x: not has_team(x),
    'Weightlifting': lambda x: not has_team(x),
    'Skateboarding': lambda x: not has_team(x),
    'Cycling Track': lambda x: not has_team(x),
    'Cycling Road': lambda x: not has_team(x),
    'Cycling Mountain Bike': lambda x: not has_team(x),
    'Cycling BMX Freestyle': lambda x: not has_team(x),
    'Cycling BMX Racing': lambda x: not has_team(x),
    'Modern Pentathlon': lambda x: not has_team(x),
    'Badminton': lambda x: 'singles' in norm(x),
    'Tennis': lambda x: 'singles' in norm(x),
    'Table Tennis': lambda x: 'singles' in norm(x),
    'Archery': lambda x: 'individual' in norm(x),
    'Rowing': lambda x: 'single sculls' in norm(x),
    'Canoe Slalom': lambda x: not has_team(x),
    'Surfing': lambda x: not has_team(x),
    'Sport Climbing': lambda x: not has_team(x),
    'Triathlon': lambda x: not has_team(x),
    'Golf': lambda x: not has_team(x),
    'Equestrian': lambda x: 'individual' in norm(x),
}

# Avoid substring matching e.g. 'four' inside other words.
TEAM = re.compile(r'\b(team|teams|relay|relays|doubles|pairs|pair|four|fours|eight|eights|'
                  r'quadruple|double sculls|skiff|mixed|synchronised|synchronized|'
                  r'madison|crew)\b', re.I)

def has_team(x):
    return bool(TEAM.search(x))

def norm(x):
    x = unicodedata.normalize('NFKD', str(x or ''))
    x = ''.join(c for c in x if not unicodedata.combining(c))
    x = x.casefold().replace("women's", 'women').replace("men's", 'men')
    x = re.sub(r'[^a-z0-9]+', ' ', x)
    return ' '.join(x.split())

def event_key(x):
    # Normalize equivalent metric notation without fuzzy matching:
    # '100 metres'/'100 meters'/'100m' -> '100m'.
    value = norm(str(x).replace('×', ' x '))
    value = re.sub(r'\b(\d+)\s*(?:metres|meters|m)\b', r'\1m', value)
    return tuple(sorted(p for p in value.split() if p != 'olympic'))

def sport_key(x):
    return norm(str(x).split('(')[0])

def medal_zero():
    return {'oro': 0, 'plata': 0, 'bronce': 0, 'total': 0}

def athlete_summary(db, aid):
    games, years, sports, medals = set(), set(), set(), Counter()
    participation = 0
    for r in db.resultados.find({'atletas.id': aid}, {'atletas': 1, 'edicion': 1, 'deporte': 1, 'medalla': 1}):
        n = sum(1 for a in r.get('atletas', []) if a.get('id') == aid)
        if not n:
            continue
        participation += n
        games.add(r['edicion']['id'])
        years.add(r['edicion']['anio'])
        sports.add(r['deporte']['nombre'])
        key = (r.get('medalla') or {}).get('codigo')
        if key in ('ORO', 'PLATA', 'BRONCE'):
            medals[key.lower()] += n
    m = {k: medals[k] for k in ('oro', 'plata', 'bronce')}
    m['total'] = sum(m.values())
    return {'participaciones': participation, 'juegos': len(games), 'anios': sorted(years),
            'deportes': sorted(sports), 'medallas': m}

def country_summary(db, noc):
    games, years, sports, athletes = set(), set(), set(), set()
    medal_event, medal_athlete, medal_mixed = Counter(), Counter(), Counter()
    participation = 0
    cursor = db.resultados.find({'$or': [{'atletas.noc': noc}, {'paises': noc}]},
                {'atletas': 1, 'paises': 1, 'edicion': 1, 'deporte': 1,
                 'medalla': 1, 'equipoMixto': 1})
    for r in cursor:
        members = [a for a in r.get('atletas', []) if a.get('noc') == noc]
        participation += len(members)
        for a in members:
            athletes.add(a['id'])
            games.add(r['edicion']['id'])
            years.add(r['edicion']['anio'])
            sports.add(r['deporte']['nombre'])
        key = (r.get('medalla') or {}).get('codigo')
        if key in ('ORO', 'PLATA', 'BRONCE'):
            key = key.lower()
            medal_athlete[key] += len(members)
            if noc in r.get('paises', []):
                (medal_mixed if r.get('equipoMixto') else medal_event)[key] += 1
    def pack(c):
        m = {k: c[k] for k in ('oro', 'plata', 'bronce')}
        m['total'] = sum(m.values())
        return m
    return {'participaciones': participation, 'atletas': len(athletes),
            'juegos': len(games), 'anios': sorted(years), 'deportes': sorted(sports),
            'medallas': pack(medal_event), 'medallasAtleta': pack(medal_athlete),
            'medallasMixtas': pack(medal_mixed), 'primerAnio': min(years) if years else None,
            'ultimoAnio': max(years) if years else None}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--aplicar', action='store_true', help='Write missing results and sync affected summaries')
    ap.add_argument('--solo-historicos', action='store_true', help='Do not create provisional athlete profiles')
    ap.add_argument('--mongo', default='mongodb://127.0.0.1:27017/?directConnection=true')
    args = ap.parse_args()
    EVID.mkdir(exist_ok=True, parents=True)
    client = MongoClient(args.mongo, serverSelectionTimeoutMS=6000)
    client.admin.command('ping')
    db = client.olimpiadas_mongo
    nsrc = db.paris2024_fuente.count_documents({})
    assert nsrc == 14892, f'Fuente incompleta: {nsrc}'
    assert db.resultados.count_documents({'edicion.anio': {'$lt': 2024}}) == 156032
    assert db.catalogos.find_one({'_id': 'juego:63'})

    source = list(db.paris2024_fuente.find({}, {'atletaFuente': 1, 'competenciaFuente': 1, 'medallaFuente': 1, 'origen': 1}))
    sports = {d['id']: d for d in db.catalogos.find({'tipo': 'deporte'})}
    discs = {d['id']: d for d in db.catalogos.find({'tipo': 'disciplina'})}
    sport_idx = defaultdict(set)
    for did, d in sports.items():
        sport_idx[sport_key(d['nombre'])].add(did)
    # Index all events within their verified sport/discipline, never by a
    # cross-sport fuzzy match. Handle names such as 'Football, Men (Olympic)'
    # as 'Men' for the same sport. Duplicate index entries are deduplicated.
    event_idx = defaultdict(dict)
    for e in db.catalogos.find({'tipo': 'evento'}):
        did, dcid = e.get('deporteId'), e.get('disciplinaId')
        if did not in sports or dcid not in discs or discs[dcid].get('deporteId') != did:
            continue
        keys = {event_key(e['nombre'])}
        main_sport = sports[did]['nombre'].split('(')[0].strip()
        prefix = main_sport + ','
        if e['nombre'].casefold().startswith(prefix.casefold()):
            keys.add(event_key(e['nombre'][len(prefix):]))
        for key in keys:
            event_idx[(did, key)][e['id']] = e
    nocs = {p['noc'] for p in db.paises.find({}, {'noc': 1}) if p.get('noc')}

    # Index by exact (normalized name, country, sex, historical sport).
    names = {norm(f['atletaFuente']['nombre']) for f in source}
    relevant = {a['_id']: a for a in db.atletas.find({}, {'nombre': 1, 'sexo': 1}) if norm(a.get('nombre')) in names}
    historical = defaultdict(set)
    for r in db.resultados.find({'edicion.anio': {'$lt': 2024}}, {'deporte.id': 1, 'atletas': 1}):
        did = r.get('deporte', {}).get('id')
        for a in r.get('atletas', []):
            p = relevant.get(a.get('id'))
            if p:
                historical[(norm(p.get('nombre')), a.get('noc'), str(p.get('sexo') or '').upper(), did)].add(a['id'])

    pids = defaultdict(set)
    for f in source:
        a = f['atletaFuente']
        pids[str(a['playerId'])].add((norm(a['nombre']), a['noc'], str(a['sexo']).upper()))
    # Account for possible multiple historical links from different disciplines.
    identity_by_pid = defaultdict(set)
    for f in source:
        a, c = f['atletaFuente'], f['competenciaFuente']
        dids = sport_idx.get(sport_key(c['deporte']), set())
        if len(dids) == 1:
            did = next(iter(dids))
            identity_by_pid[str(a['playerId'])].update(historical.get((norm(a['nombre']), a['noc'], str(a['sexo']).upper(), did), set()))
    reverse_historical = defaultdict(set)
    for pid, ids in identity_by_pid.items():
        for aid in ids:
            reverse_historical[aid].add(pid)

    existing_keys = set()
    existing_source = set()
    for r in db.resultados.find({'edicion.anio': 2024}, {'atletas': 1, 'evento.id': 1, 'fuente.stagingId': 1}):
        for a in r.get('atletas', []):
            existing_keys.add((r.get('evento', {}).get('id'), a.get('id')))
        sid = r.get('fuente', {}).get('stagingId')
        if sid:
            existing_source.add(sid)

    # Persistent provisional source identity; ids minted in same run only after validation.
    provisional = {}
    for a in db.atletas.find({'fuenteParis2024.playerId': {'$exists': True}},
                             {'_id': 1, 'nombre': 1, 'sexo': 1, 'fuenteParis2024': 1}):
        info = a['fuenteParis2024']
        pid = str(info['playerId'])
        assert pid not in provisional, f'Identidad provisional duplicada: {pid}'
        provisional[pid] = a
    next_id = (db.atletas.find_one(sort=[('_id', -1)], projection={'_id': 1}) or {'_id': 0})['_id'] + 1
    max_result = (db.resultados.find_one(sort=[('_id', -1)], projection={'_id': 1}) or {'_id': 0})['_id']
    additions = []
    created = {}
    selected_source = set()
    selected_key = set()
    counts, bysport = Counter(), Counter()
    profile_names = defaultdict(set)
    # Safeguard new profile duplicates: if exact same name/sex exists historically,
    # do not create unless country history can unambiguously rule out overlap.
    for p in relevant.values():
        profile_names[(norm(p.get('nombre')), str(p.get('sexo') or '').upper())].add(p['_id'])

    for f in sorted(source, key=lambda x: x['_id']):
        a, c = f['atletaFuente'], f['competenciaFuente']
        pid, noc, sex = str(a['playerId']), a['noc'], str(a['sexo']).upper()
        sport, ev = c['deporte'], c['evento']
        sid = f['_id']
        reason = None
        if sid in existing_source:
            reason = 'YA_INTEGRADO_STAGING'
        elif f['medallaFuente'] != 'No medal':
            reason = 'MEDALLA_PENDIENTE_VERIFICACION'
        elif len(pids[pid]) != 1 or sex not in ('M', 'F'):
            reason = 'IDENTIDAD_ORIGEN_INCONSISTENTE'
        elif noc not in nocs:
            reason = 'NOC_SIN_PAIS'
        elif sport not in ALLOW or not ALLOW[sport](ev):
            reason = 'PRUEBA_COLECTIVA_O_MODALIDAD_PENDIENTE'
        else:
            dids = sport_idx.get(sport_key(sport), set())
            if len(dids) != 1:
                reason = 'DEPORTE_SIN_MAPEO_UNICO'
            else:
                did = next(iter(dids))
                options = list(event_idx.get((did, event_key(ev)), {}).values())
                if len(options) != 1:
                    reason = 'EVENTO_SIN_MAPEO_UNICO'
                else:
                    e = options[0]
                    eid = e['id']
                    if sex == 'M' and 'women' in norm(ev).split() or sex == 'F' and 'men' in norm(ev).split():
                        reason = 'SEXO_EVENTO_INCOMPATIBLE'
                    elif len(identity_by_pid[pid]) > 1:
                        reason = 'IDENTIDAD_HISTORICA_AMBIGUA'
                    else:
                        ids = historical.get((norm(a['nombre']), noc, sex, did), set())
                        if len(ids) > 1:
                            reason = 'IDENTIDAD_HISTORICA_AMBIGUA'
                        elif len(ids) == 1:
                            aid = next(iter(ids))
                            if identity_by_pid[pid] != {aid} or len(reverse_historical[aid]) != 1:
                                reason = 'IDENTIDAD_COMPARTIDA'
                        elif identity_by_pid[pid]:
                            reason = 'IDENTIDAD_HISTORICA_OTRO_DEPORTE'
                        elif pid in provisional:
                            old = provisional[pid]
                            info = old['fuenteParis2024']
                            if (norm(old.get('nombre')), str(old.get('sexo')).upper(), info.get('noc')) != (norm(a['nombre']), sex, noc):
                                reason = 'PERFIL_PROVISIONAL_INCONSISTENTE'
                            else:
                                aid = old['_id']
                        elif args.solo_historicos:
                            reason = 'ATLETA_NUEVO_PENDIENTE'
                        elif profile_names.get((norm(a['nombre']), sex)):
                            reason = 'POTENCIAL_HOMONIMO_HISTORICO'
                        else:
                            if pid not in created:
                                aid = next_id + len(created)
                                created[pid] = {'_id': aid, 'nombre': a['nombre'], 'sexo': sex,
                                    'fuenteParis2024': {'playerId': pid, 'noc': noc, 'identidadProvisional': True},
                                    'resumen': {'participaciones': 0, 'juegos': 0, 'anios': [],
                                               'deportes': [], 'medallas': medal_zero()}}
                            aid = created[pid]['_id']
                        if reason is None:
                            key = (eid, aid)
                            if key in existing_keys:
                                reason = 'YA_INTEGRADO_EVENTO_ATLETA'
                            elif key in selected_key or sid in selected_source:
                                reason = 'DUPLICADO_EN_LOTE'
                            else:
                                selected_key.add(key)
                                selected_source.add(sid)
                                additions.append({'_id': max_result + 1 + len(additions),
                                    'edicion': {'id': 63, 'anio': 2024, 'temporada': 'Summer', 'categoria': 'Senior'},
                                    'deporte': {'id': did, 'nombre': sports[did]['nombre']},
                                    'disciplina': {'id': e['disciplinaId'], 'nombre': discs[e['disciplinaId']]['nombre']},
                                    'evento': {'id': eid, 'nombre': e['nombre']},
                                    'posicion': None, 'empate': False, 'equipoMixto': False,
                                    'estado': 'PENDING_VERIFICATION', 'medalla': None,
                                    'multipais': False, 'paisEquipo': noc, 'paises': [noc],
                                    'atletas': [{'id': aid, 'nombre': a['nombre'] if pid in created else (
                                        provisional[pid]['nombre'] if pid in provisional else relevant[aid]['nombre']),
                                        'noc': noc, 'edad': None}],
                                    'revisar': True,
                                    'fuente': {'dataset': 'olympics_dataset.csv', 'stagingId': sid,
                                        'playerIdOriginal': pid, 'eventoOriginal': ev,
                                        'mapeo': 'exacto_unico', 'identidadProvisional': pid in created or pid in provisional,
                                        'posicionVerificada': False, 'estadoVerificado': False,
                                        'tipoParticipacion': 'individual', 'etlMotor': 'general_v1'}})
                                bysport[sport] += 1
                                reason = 'PREPARADO'
        counts[reason] += 1

    # New athletes may have been reserved for rejected duplicate rows; do not create orphans.
    referenced = {a['id'] for d in additions for a in d['atletas']}
    new_profiles = [v for v in created.values() if v['_id'] in referenced]
    report = {'fuente': len(source), 'resultados_2024_actuales': db.resultados.count_documents({'edicion.anio': 2024}),
        'nuevos_resultados_propuestos': len(additions), 'nuevos_perfiles_provisionales': len(new_profiles),
        'atletas_existentes_impactados': len(referenced - {p['_id'] for p in new_profiles}),
        'paises_afectados': len({d['paisEquipo'] for d in additions}),
        'clasificacion': dict(counts), 'deportes_preparados': dict(bysport),
        'modo': 'APLICAR' if args.aplicar else 'SIMULACION'}
    assert sum(counts.values()) == len(source)
    PLAN.write_text(''.join(json.dumps(x, ensure_ascii=False) + '\n' for x in additions), encoding='utf-8')
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('\n=== ETL GENERAL PARIS 2024 ===')
    print('Fuente:', len(source), '| Resultados nuevos propuestos:', len(additions))
    print('Perfiles provisionales nuevos:', len(new_profiles))
    print('Atletas afectados:', len(referenced), '| Paises afectados:', report['paises_afectados'])
    print('Clasificacion:')
    for k, v in counts.most_common():
        print(f'  {k}: {v}')
    print('Deportes preparados:', dict(bysport))
    print('Plan:', PLAN)
    print('Reporte:', OUT)
    if not args.aplicar:
        print('SIMULACION: MongoDB NO se modifico. Ejecuta --aplicar solo tras revisar el plan y respaldo.')
        return
    # Controlled resumable writes: existing source IDs and source-profile IDs make reruns safe.
    # Do not overwrite any existing document if a competing write happened after the dry run.
    assert BACKUP.is_file() and BACKUP.stat().st_size > 1000000, (
        f'Falta respaldo actualizado: {BACKUP}')
    print('\nINSERTANDO...')
    for p in new_profiles:
        # source player id acts as a unique identity reference, avoid conflicting ID.
        assert db.atletas.find_one({'_id': p['_id']}) is None
        assert db.atletas.find_one({'fuenteParis2024.playerId': p['fuenteParis2024']['playerId']}) is None
    for d in additions:
        assert db.resultados.find_one({'_id': d['_id']}) is None
        assert db.resultados.find_one({'fuente.stagingId': d['fuente']['stagingId']}) is None
        assert db.resultados.find_one({'edicion.anio': 2024, 'evento.id': d['evento']['id'],
            'atletas.id': d['atletas'][0]['id']}) is None
    if new_profiles:
        db.atletas.insert_many(new_profiles, ordered=True)
    for start in range(0, len(additions), 500):
        batch = additions[start:start + 500]
        if batch:
            db.resultados.insert_many(batch, ordered=True)
            print('  Insertados:', start + len(batch), '/', len(additions))
    # Resume safe: recompute summaries for earlier partially-written ETL rows too.
    affected = list(db.resultados.find(
        {'edicion.anio': 2024, 'fuente.etlMotor': 'general_v1'},
        {'atletas.id': 1, 'paisEquipo': 1}))
    aids = sorted(referenced | {a['id'] for r in affected for a in r.get('atletas', [])})
    changed_nocs = sorted({d['paisEquipo'] for d in additions} |
                          {r['paisEquipo'] for r in affected})
    for batch_start in range(0, len(aids), 250):
        batch = aids[batch_start:batch_start+250]
        ops = [UpdateOne({'_id': aid}, {'$set': {'resumen': athlete_summary(db, aid)}}) for aid in batch]
        if ops:
            db.atletas.bulk_write(ops, ordered=False)
    for noc in changed_nocs:
        summary = country_summary(db, noc)
        db.paises.update_one({'noc': noc}, {'$set': {'resumen': summary}})
    assert db.resultados.count_documents({'edicion.anio': {'$lt': 2024}}) == 156032
    print('\nCARGA EXITOSA. Nuevos resultados:', len(additions))
    print('Paris 2024 total:', db.resultados.count_documents({'edicion.anio': 2024}))
    print('Perfiles nuevos:', len(new_profiles), '| Resumenes de paises:', len(changed_nocs))

if __name__ == '__main__':
    main()


