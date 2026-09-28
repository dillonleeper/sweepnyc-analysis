"""Recount pilot metrics independently and check audit partition/sensitivity output."""
import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/processed/validation'

def main():
    oath = json.loads((ROOT / 'data/raw/pilot/oath.json').read_text())
    matches = list(csv.DictReader((ROOT / 'data/processed/pilot/matches.csv').open(encoding='utf-8')))
    sweep = json.loads((ROOT / 'data/raw/pilot/sweepnyc.json').read_text())
    evidence = json.loads((OUT / 'evidence.json').read_text())
    sample_ids = {r['ticket_number'] for r in csv.DictReader((OUT / 'sample_100.csv').open())}
    pattern = re.compile(r'DIRTY SIDEWALK|DIRTY AREA|18 INCH|18"|EIGHTEEN INCH', re.I)
    eligible = [r for r in oath if pattern.search(' '.join(str(r.get(k, '')) for k in ['violation_description'] + [f'charge_{i}_code_description' for i in range(1, 11)]))]
    if {r['ticket_number'] for r in eligible} != {r['ticket_number'] for r in matches}:
        raise ValueError('Independent eligibility recount disagrees with pilot output')
    if len({r['ticket_number'] for r in matches}) != len(matches):
        raise ValueError('Duplicate pilot tickets need a denominator decision')
    quality = Counter(r['match_quality'] for r in matches)
    swept = {r['physical_id'] for r in sweep}
    overlap = sum(bool(r['matched_physical_id'] and r['matched_physical_id'] in swept) for r in matches)
    if {r['ticket_number'] for r in evidence} != {r['ticket_number'] for r in matches} or len(evidence) != len(matches):
        raise ValueError('Audit population does not reconcile to pilot')
    sensitivity = []
    for cap, margin in [(100, 20), (150, 10), (150, 20), (150, 30), (200, 20)]:
        good = []
        for row in evidence:
            if not row['assigned_physical_id'] or not row['evidence']:
                continue
            supported = all(e['nearest_physical_id'] == row['assigned_physical_id']
                and e['nearest_distance_ft'] <= cap
                and (e['runner_up_distance_ft'] is None or e['runner_up_distance_ft'] - e['nearest_distance_ft'] >= margin)
                and e['endpoint_along_distance_ft'] >= 20 for e in row['evidence'])
            if supported:
                good.append(row)
        sensitivity.append({'max_distance_ft': cap, 'min_margin_ft': margin, 'endpoint_buffer_ft': 20,
            'corroborated_matched_records': len(good), 'corroborated_sample_records': sum(r['ticket_number'] in sample_ids for r in good)})
    receipt = {'independent_recount': {'oath_rows': len(oath), 'eligible_records': len(eligible),
        'quality_counts': dict(quality), 'sweep_overlap': overlap}, 'threshold_sensitivity': sensitivity,
        'ground_truth_accuracy': None, 'historical_23c_resolved': False}
    (OUT / 'verification.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt, indent=2))

if __name__ == '__main__':
    main()
