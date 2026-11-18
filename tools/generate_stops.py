#!/usr/bin/env python3
"""Met à jour stops.js (lieux d'arrêt et quais) depuis le GTFS Naolib.

Usage :
    python3 tools/generate_stops.py <gtfs.zip> [stops.js]

Le GTFS (« Réseau urbain Naolib », Nantes Métropole) se télécharge sur
https://transport.data.gouv.fr/datasets/reseau-de-transports-collectifs-naolib
Le script lit l'archive directement (rien n'est extrait) et n'utilise que la bibliothèque
standard. Il FUSIONNE le GTFS avec le stops.js existant, sans rien retirer :
  - les lieux du GTFS sont ajoutés ou mis à jour (nom du GTFS) ;
  - les quais du GTFS sont ajoutés à ceux déjà connus : les numéros de quai changent
    d'une version à l'autre et rien ne permet, sans l'API temps réel, de savoir lesquels
    elle utilise ; garder les anciens ne coûte que quelques requêtes SIRI inutiles ;
  - les lieux absents du GTFS (sans service dans cette version) sont conservés.
Format de stops.js : [nom, identifiant du lieu, [identifiants des quais]].
Lancer ensuite tools/generate_lines.py pour régénérer lines.js.
"""
import csv
import io
import json
import sys
import zipfile
from datetime import date

PLACE_PREFIX = 'FR_NAOLIB:StopPlace:'
QUAY_PREFIX = 'FR_NAOLIB:Quay:'


def rows(archive, name):
    with archive.open(name) as raw:
        yield from csv.DictReader(io.TextIOWrapper(raw, encoding='utf-8-sig', newline=''))


def read_stops(path):
    """Lit stops.js : renvoie {identifiant du lieu: (nom, [quais])}."""
    stops = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip().rstrip(',')
            if line.startswith('["'):
                name, place_id, quays = json.loads(line)
                stops[place_id] = (name, quays)
    return stops


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    gtfs_path = sys.argv[1]
    stops_path = sys.argv[2] if len(sys.argv) > 2 else 'stops.js'

    archive = zipfile.ZipFile(gtfs_path)
    old = read_stops(stops_path)

    places = {}        # identifiant du lieu -> nom (GTFS)
    quays = {}         # identifiant du lieu -> {quais}
    for r in rows(archive, 'stops.txt'):
        sid = r['stop_id']
        if r['location_type'] == '1' and sid.startswith(PLACE_PREFIX):
            places[int(sid[len(PLACE_PREFIX):])] = r['stop_name']
        elif r['location_type'] in ('', '0') and sid.startswith(QUAY_PREFIX) and r['parent_station'].startswith(PLACE_PREFIX):
            quays.setdefault(int(r['parent_station'][len(PLACE_PREFIX):]), set()).add(int(sid[len(QUAY_PREFIX):]))

    merged = {}
    renamed, added_places, added_quays = [], [], 0
    for place_id in sorted(set(old) | set(places)):
        old_name, old_quays = old.get(place_id, (None, []))
        name = places.get(place_id, old_name)
        if old_name is not None and name != old_name:
            renamed.append((place_id, old_name, name))
        new_quays = sorted(set(old_quays) | quays.get(place_id, set()))
        added_quays += len(set(new_quays) - set(old_quays))
        if place_id not in old:
            added_places.append((place_id, name))
        merged[place_id] = (name, new_quays)

    entries = sorted(((name, pid, qs) for pid, (name, qs) in merged.items()), key=lambda e: (e[0], e[1]))
    with open(stops_path, 'w', encoding='utf-8') as f:
        f.write("'use strict';\n\n")
        f.write("// Arrêts Naolib (lieux et quais), extraits du GTFS « Réseau urbain Naolib » de Nantes Métropole,\n")
        f.write(f"// diffusé sur transport.data.gouv.fr. Données du {date.today().isoformat()}, sous Licence Ouverte 2.0.\n")
        f.write("// Généré par tools/generate_stops.py : fusionne le GTFS avec la liste précédente, sans rien retirer.\n")
        f.write("// Format : [nom, StopPlaceId, [quayIds...]]\n")
        f.write('const STOP_LIST = [\n')
        f.write(',\n'.join(json.dumps([n, p, qs], ensure_ascii=False, separators=(',', ':')) for n, p, qs in entries))
        f.write('\n];\n')

    print(f'lieux avant / après              : {len(old)} / {len(merged)}')
    print(f'  ajoutés                        : {len(added_places)} {[n for _p, n in added_places]}')
    print(f'  renommés                       : {len(renamed)}')
    for pid, a, b in renamed:
        print(f'      {pid:>5}  {a!r} -> {b!r}')
    print(f'  conservés sans service au GTFS : {len(set(old) - set(places))}')
    print(f'quais avant / après              : {sum(len(q) for _n, q in old.values())} / {sum(len(q) for _n, q in merged.values())}  (+{added_quays})')


if __name__ == '__main__':
    main()
