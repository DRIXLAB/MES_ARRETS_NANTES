#!/usr/bin/env python3
"""Génère lines.js (lignes de chaque arrêt + couleurs officielles) depuis le GTFS Naolib.

Usage :
    python3 tools/generate_lines.py <gtfs.zip> [stops.js] [lines.js]

Le GTFS (« Réseau urbain Naolib », publié par Nantes Métropole) est téléchargeable sur
https://transport.data.gouv.fr/datasets/reseau-de-transports-collectifs-naolib
Le script lit l'archive directement (rien n'est extrait sur le disque) et n'utilise que
la bibliothèque standard. Il rattache chaque quai du GTFS (FR_NAOLIB:Quay:<id>) à son lieu
parent (FR_NAOLIB:StopPlace:<id>, mêmes identifiants que stops.js), puis écrit :
  - LINE_INFO : code de ligne -> couleur, couleur du texte, nom, ordre d'affichage ;
  - STOP_LINES : identifiant de lieu -> codes de lignes qui y prennent des voyageurs.
Le code de ligne est celui de l'API temps réel (LineRef FR_NAOLIB:Line:<code>).
"""
import csv
import io
import json
import re
import sys
import zipfile
from datetime import date

LINE_PREFIX = 'FR_NAOLIB:Line:'
QUAY_PREFIX = 'FR_NAOLIB:Quay:'
PLACE_PREFIX = 'FR_NAOLIB:StopPlace:'


def rows(archive, name):
    """Lit un fichier CSV de l'archive, ligne par ligne, sous forme de dictionnaires."""
    with archive.open(name) as raw:
        yield from csv.DictReader(io.TextIOWrapper(raw, encoding='utf-8-sig', newline=''))


def natural_key(code):
    return [int(p) if p.isdigit() else p.lower() for p in re.split(r'(\d+)', code)]


def read_stops(path):
    """Lit stops.js : [nom, identifiant du lieu, [quais]]."""
    stops = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip().rstrip(',')
            if line.startswith('["'):
                name, place_id, quays = json.loads(line)
                stops.append((name, place_id, quays))
    return stops


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    gtfs_path = sys.argv[1]
    stops_path = sys.argv[2] if len(sys.argv) > 2 else 'stops.js'
    out_path = sys.argv[3] if len(sys.argv) > 3 else 'lines.js'

    archive = zipfile.ZipFile(gtfs_path)

    # Lignes
    lines = {}
    for r in rows(archive, 'routes.txt'):
        code = r['route_id'].removeprefix(LINE_PREFIX)
        lines[code] = {
            'color': (r['route_color'] or '').lower(),
            'text': (r['route_text_color'] or 'ffffff').lower(),
            'name': r['route_long_name'] or r['route_short_name'],
            'order': int(r['route_sort_order'] or 0),
            'short': r['route_short_name'],
        }
    trip_line = {r['trip_id']: r['route_id'].removeprefix(LINE_PREFIX) for r in rows(archive, 'trips.txt')}

    # Lieu parent de chaque quai, d'après le GTFS lui-même : les numéros de quai peuvent changer
    # d'une version à l'autre (c'est le cas de plusieurs quais de la ligne 1), pas les lieux.
    quay_place = {}
    for r in rows(archive, 'stops.txt'):
        if r['location_type'] in ('', '0') and r['parent_station'].startswith(PLACE_PREFIX):
            quay_place[r['stop_id']] = int(r['parent_station'][len(PLACE_PREFIX):])

    # Lignes par lieu : seuls comptent les arrêts où l'on peut monter (pickup_type != 1)
    place_lines = {}
    place_lines_any = {}
    for r in rows(archive, 'stop_times.txt'):
        line = trip_line.get(r['trip_id'])
        place = quay_place.get(r['stop_id'])
        if line is None or place is None:
            continue
        place_lines_any.setdefault(place, set()).add(line)
        if r['pickup_type'] != '1':
            place_lines.setdefault(place, set()).add(line)

    # Lieux de stops.js
    stops = read_stops(stops_path)
    stop_lines = {}
    for _name, place_id, _quays in stops:
        found = place_lines.get(place_id)
        if found:
            stop_lines[place_id] = sorted(found, key=lambda c: (lines.get(c, {}).get('order', 9999), natural_key(c)))

    used = sorted({c for ls in stop_lines.values() for c in ls}, key=lambda c: (lines.get(c, {}).get('order', 9999), natural_key(c)))
    unknown = [c for c in used if c not in lines]

    # Écriture
    info = {c: lines[c] for c in used if c in lines}
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write("'use strict';\n\n")
        f.write('// Lignes du réseau Naolib et lignes desservant chaque arrêt, extraites du GTFS « Réseau urbain Naolib »\n')
        f.write('// (Nantes Métropole, via transport.data.gouv.fr). Généré par tools/generate_lines.py : ne pas modifier à la main.\n')
        f.write(f'// Données de {date.today().isoformat()}. Voir le README pour la licence des données.\n')
        f.write('// LINE_INFO : code de ligne (celui de l\'API temps réel) -> couleur, couleur du texte, nom, ordre d\'affichage.\n')
        f.write('const LINE_INFO = {\n')
        for c in used:
            if c not in info:
                continue
            i = info[c]
            f.write(f'{json.dumps(c, ensure_ascii=False)}:{json.dumps({"c": i["color"], "t": i["text"], "n": i["name"], "o": i["order"]}, ensure_ascii=False, separators=(",", ":"))},\n')
        f.write('};\n\n')
        f.write("// STOP_LINES : identifiant de lieu (voir stops.js) -> codes des lignes qui y prennent des voyageurs.\n")
        f.write('const STOP_LINES = {\n')
        for place_id in sorted(stop_lines):
            f.write(f'{place_id}:{json.dumps(stop_lines[place_id], ensure_ascii=False, separators=(",", ":"))},\n')
        f.write('};\n')

    # Bilan
    total_pairs = sum(len(v) for v in stop_lines.values())
    served = len(stop_lines)
    print(f'lignes dans routes.txt           : {len(lines)}')
    print(f'lignes desservant un arrêt       : {len(used)}  (sans définition : {unknown or "aucune"})')
    print(f'lieux de stops.js                : {len(stops)}')
    print(f'  avec au moins une ligne        : {served}')
    print(f'  sans aucune ligne              : {len(stops) - served}')
    print(f'liaisons lieu-ligne              : {total_pairs}  (moyenne {total_pairs / max(served, 1):.1f} par lieu)')
    stops_places = {p for _n, p, _q in stops}
    print(f'lieux du GTFS (avec service) absents de stops.js : {len(set(place_lines_any) - stops_places)}')
    print(f'lieux de stops.js sans service dans le GTFS      : {len(stops_places - set(place_lines_any))}')
    only_dropoff = sum(1 for p, ls in place_lines_any.items() if ls != place_lines.get(p, set()))
    print(f'lieux où certaines lignes ne font que déposer (exclues) : {only_dropoff}')
    # Quais de stops.js dont le numéro a disparu du GTFS : leurs données temps réel dépendent de l'API
    gtfs_quays = {int(q[len(QUAY_PREFIX):]) for q in quay_place}
    stale = sorted({q for _n, _p, qs in stops for q in qs} - gtfs_quays)
    print(f'quais de stops.js absents du GTFS (numéro changé ou supprimé) : {len(stale)}')


if __name__ == '__main__':
    main()
