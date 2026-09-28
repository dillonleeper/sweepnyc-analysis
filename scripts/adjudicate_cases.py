"""Replay five case reviews; preserve original matches and expose separate decisions."""
import csv
import hashlib
import json
from pathlib import Path

import pyogrio
from pyproj import Transformer
from shapely.geometry import Point, shape
from shapely.ops import transform, unary_union

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw/adjudication'
OUT = ROOT / 'data/processed/adjudication'
CASES = [
    ('541_w125', '1019820007', '1059692', -73.957167885416, 40.814688018194, ['049853638J']),
    ('545_w125', '1019820005', '1059691', -73.95728946215, 40.814819270988, ['049886175N', '049918725M']),
    ('13_e27', '1008570066', '1016894', -73.986880770554, 40.743815998881, ['049909531J', '049909538M']),
]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    read = lambda name: json.loads((RAW / name).read_text(encoding='utf-8'))
    rows = list(csv.DictReader((ROOT / 'data/processed/pilot/matches.csv').open(encoding='utf-8')))
    tickets = {r['ticket_number']: r for r in rows}
    lots = {r['bbl']: r for r in read('tax_lots.json')}
    buildings = {r['bin']: r for r in read('buildings.json')}
    lion = pyogrio.read_dataframe(RAW / 'lion_23c/lion/lion.gdb', layer='lion', columns=['PhysicalID', 'RB_Layer'])
    assert str(lion.crs).upper() == 'EPSG:2263'
    ids = {str(int(x)) for x in lion.PhysicalID.dropna()}
    matched_ids = {r['matched_physical_id'] for r in rows if r['matched_physical_id']}
    project = Transformer.from_crs(4326, 2263, always_xy=True).transform
    decisions = []
    for name, bbl, bin_id, lon, lat, case_tickets in CASES:
        point = transform(project, Point(lon, lat))
        parcel = transform(project, shape(lots[bbl]['the_geom']))
        building = transform(project, shape(buildings[bin_id]['the_geom']))
        assert buildings[bin_id]['base_bbl'] == bbl
        service = read('sweepinfo_' + name + '.json')
        proposed = str(service['response']['ObjectId'])
        assert proposed in ids
        expected = '81213' if name == '13_e27' else '117672'
        if proposed != expected or point.distance(parcel) > 1 or point.distance(building) > 1:
            raise ValueError('Case evidence changed; human review required before applying saved decisions')
        for ticket in case_tickets:
            original = tickets[ticket]
            oath_bbl = '1' + original['violation_location_block_no'].zfill(5) + original['violation_location_lot_no'].zfill(4)
            assert oath_bbl == bbl
            distances = {}
            for physical_id in sorted({original['matched_physical_id'], proposed}):
                subset = lion[lion.PhysicalID == int(physical_id)]
                distances[physical_id] = round(point.distance(unary_union(subset.geometry)), 2)
            decisions.append({
                'ticket_number': ticket, 'address_case': name,
                'original_physical_id': original['matched_physical_id'],
                'reviewed_physical_id': proposed,
                'decision': 'correct_case' if proposed != original['matched_physical_id'] else 'retain_historical_id',
                'oath_bbl': bbl, 'building_bin': bin_id,
                'point_to_parcel_ft': round(point.distance(parcel), 2),
                'point_to_building_ft': round(point.distance(building), 2),
                'lion_23c_distances_ft': distances,
                'service_url': service['url'],
            })
    sweep_ids = {r['physical_id'] for r in json.loads((ROOT / 'data/raw/pilot/sweepnyc.json').read_text())}
    overrides = {d['ticket_number']: d['reviewed_physical_id'] for d in decisions}
    for row in rows:
        row['reviewed_physical_id'] = overrides.get(row['ticket_number'], row['matched_physical_id'])
        row['reviewed_sweep_overlap'] = bool(row['reviewed_physical_id'] and row['reviewed_physical_id'] in sweep_ids)
        row['case_reviewed'] = row['ticket_number'] in overrides
    with (OUT / 'reviewed_matches.csv').open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    summary = {
        'eligible_records': len(rows), 'matched_records': sum(bool(r['reviewed_physical_id']) for r in rows),
        'reviewed_sweep_overlap': sum(r['reviewed_sweep_overlap'] for r in rows),
        'cases': decisions, 'historical_lion_edition': '23C',
        'matched_unique_ids': len(matched_ids), 'matched_ids_present_in_lion_23c': len(matched_ids & ids),
        'matched_ids_absent_from_lion_23c': sorted(matched_ids - ids),
        'exact_dsny_cscl_23c_snapshot_verified': False,
        'limitations': 'LION is not an exact CSCL snapshot. Public SweepNYC responses are current, not August observations. Parcel/building evidence checks location; it does not certify every address or matcher accuracy.',
    }
    (OUT / 'summary.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    inputs = [ROOT / 'data/processed/pilot/matches.csv', ROOT / 'data/raw/pilot/sweepnyc.json']
    inputs += [RAW / name for name in ['nyclion_23c.zip', 'fetch_manifest.json',
        'tax_lots.json', 'buildings.json', 'pluto.json',
        'sweepinfo_541_w125.json', 'sweepinfo_545_w125.json', 'sweepinfo_13_e27.json']]
    (OUT / 'checksums.json').write_text(json.dumps({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
