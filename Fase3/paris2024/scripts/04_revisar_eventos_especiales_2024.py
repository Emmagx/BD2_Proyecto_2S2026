        
        #!/usr/bin/env python3
import csv


"""Audita deportes especiales de París 2024 sin modificar los datos originales.

Ejecutar desde Fase3:
    python paris2024/scripts/04_revisar_eventos_especiales_2024.py

Crea CSV para revisión manual y JSON de evidencia. NO asigna IDs automáticamente.
"""
import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
REPO = BASE.parent.parent
ORIGEN = BASE / 'datos' / 'olympics_dataset.csv'
EVIDENCIAS = BASE / 'evidencias'
DEPORTES = REPO / 'Fase2' / 'csv-limpios' / '2_DEPORTE.csv'
SALIDA = EVIDENCIAS / 'revision_eventos_especiales_2024.csv'
REPORTE = EVIDENCIAS / 'revision_eventos_especiales_2024.json'

ESPECIALES = {
    'Breaking', 'Equestrian',
    'Cycling Road, Cycling Mountain Bike',
    'Cycling Road, Cycling Track',
    'Cycling Road, Triathlon',
    'Marathon Swimming, Swimming',
}

def normalizar(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', s.lower())).strip()

def sugerir_deporte(sport, event):
    """Pista por el nombre del EVENTO; requiere revisión humana."""
    e = normalizar(event)
    if sport == 'Breaking':
        return 'Breaking', 'Deporte nuevo en París 2024: validar alta en catálogo'
    if sport == 'Equestrian':
        if 'dressage' in e: return 'Equestrian - Dressage', 'Clasificación orientativa por evento'
        if 'eventing' in e: return 'Equestrian - Eventing', 'Clasificación orientativa por evento'
        if 'jumping' in e: return 'Equestrian - Jumping', 'Clasificación orientativa por evento'
        return '', 'Verificar disciplina ecuestre'
    if sport == 'Cycling Road, Cycling Mountain Bike':
        return ('Cycling Mountain Bike' if 'cross country' in e else 'Cycling Road'), 'Revisar deporte sugerido por evento'
    if sport == 'Cycling Road, Cycling Track':
        return ('Cycling Road' if ('road race' in e or 'time trial' in e) else 'Cycling Track'), 'Revisar deporte sugerido por evento'
    if sport == 'Cycling Road, Triathlon':
        return ('Cycling Road' if 'time trial' in e else 'Triathlon'), 'Revisar deporte sugerido por evento'
    if sport == 'Marathon Swimming, Swimming':
        return ('Marathon Swimming' if '10km' in e or '10 km' in e else 'Swimming'), 'Revisar deporte sugerido por evento'
    return '', 'Sin regla sugerida'

def main():
    if not ORIGEN.exists():
        raise SystemExit(f'No se encontró {ORIGEN}')
    EVIDENCIAS.mkdir(parents=True, exist_ok=True)
    grupos = defaultdict(lambda: {'registros': 0, 'atletas': set(), 'medallas': Counter()})
    total_2024 = 0
    with ORIGEN.open(encoding='utf-8-sig', newline='') as f:
        for fila in csv.DictReader(f):
            if fila['Year'].strip() != '2024' or fila['Season'].strip().lower() != 'summer':
                continue
            total_2024 += 1
            sport, event = fila['Sport'].strip(), fila['Event'].strip()
            if sport not in ESPECIALES: continue
            grupo = grupos[(sport, event)]
            grupo['registros'] += 1
            grupo['atletas'].add(fila['player_id'].strip())
            grupo['medallas'][fila['Medal'].strip()] += 1

    catalogo = []
    if DEPORTES.exists():
        with DEPORTES.open(encoding='utf-8-sig', newline='') as f:
            catalogo = list(csv.DictReader(f))
    filas = []
    for (sport, event), valores in sorted(grupos.items()):
        propuesto, nota = sugerir_deporte(sport, event)
        # Se listan candidatos por texto, no se toma su ID como confirmado.
        coincidencias = [d for d in catalogo if normalizar(propuesto) in normalizar(d['NOMBRE']) or normalizar(d['NOMBRE']) == normalizar(propuesto)] if propuesto else []
        candidatos = '; '.join(f"{x['ID']}:{x['NOMBRE']}" for x in coincidencias[:6])
        filas.append({
            'sport_original': sport, 'evento_2024': event,
            'participaciones': valores['registros'],
            'atletas_distintos': len(valores['atletas']),
            'oro_filas': valores['medallas'].get('Gold', 0),
            'plata_filas': valores['medallas'].get('Silver', 0),
            'bronce_filas': valores['medallas'].get('Bronze', 0),
            'deporte_sugerido': propuesto,
            'candidatos_catalogo_deporte': candidatos,
            'id_deporte_confirmado': '', 'id_evento_confirmado': '',
            'accion': 'PENDIENTE_VALIDACION', 'nota': nota,
        })

    with SALIDA.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]) if filas else ['sport_original', 'evento_2024'])
        w.writeheader(); w.writerows(filas)

    resumen = {
        'generado_en': datetime.now().astimezone().isoformat(timespec='seconds'),
        'archivo_origen': ORIGEN.name,
        'registros_2024_totales': total_2024,
        'registros_en_casos_especiales': sum(v['registros'] for v in grupos.values()),
        'pares_deporte_evento': len(filas),
        'conteo_por_deporte_original': dict(sorted(Counter({s:sum(v['registros'] for (sp,_),v in grupos.items() if sp==s) for s,_ in grupos}).items())),
        'catalogo_historico_disponible': bool(catalogo),
        'advertencia': 'Sugerencias orientativas. Sin asignación de IDs ni modificaciones a bases de datos.'
    }
    REPORTE.write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    print(f'CSV de revisión: {SALIDA}')
    print(f'Evidencia JSON: {REPORTE}')

if __name__ == '__main__':
    main()
