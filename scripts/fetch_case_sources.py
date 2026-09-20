"""Fetch public case evidence, or safely extract the saved historical archive."""
import argparse
import hashlib
import json
import time
import zipfile
from datetime import datetime, timezone

import requests
from adjudicate_cases import RAW, CASES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--replay', action='store_true', help='Only extract saved archive; no network')
    args = parser.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    receipts = []
    def fetch(name, url, params=None, binary=False):
        response = requests.get(url, params=params, timeout=120)
        response.raise_for_status()
        value = response.content if binary else json.dumps(response.json(), indent=2).encode()
        (RAW / name).write_bytes(value)
        receipts.append({'file': name, 'url': response.url, 'retrieved_at': datetime.now(timezone.utc).isoformat(), 'sha256': hashlib.sha256(value).hexdigest()})
        return response
    if not args.replay:
        fetch('nyclion_23c.zip', 'https://s-media.nyc.gov/agencies/dcp/assets/files/zip/data-tools/bytes/lion/nyclion_23c.zip', binary=True)
        queries = [
            ('tax_lots', 'i38t-6if2', "boro='1' AND ((block=1982 AND lot in (5,7)) OR (block=857 AND lot=66))", 'bbl,boro,block,lot,the_geom'),
            ('pluto', '64uk-42ks', "borough='MN' AND ((block=1982 AND lot in (5,7)) OR (block=857 AND lot=66))", 'bbl,address,block,lot,latitude,longitude,xcoord,ycoord,version'),
            ('buildings', '5zhs-2jue', 'bin in (1059691,1059692,1016894)', 'bin,base_bbl,mappluto_bbl,the_geom,geom_source,construction_year,last_edited_date'),
        ]
        for name, dataset, where, select in queries:
            fetch(name + '.json', 'https://data.cityofnewyork.us/resource/' + dataset + '.json', {'$where': where, '$select': select, '$limit': 1000})
        for name, _, _, lon, lat, _ in CASES:
            filename = 'sweepinfo_' + name + '.json'
            response = fetch(filename, 'https://sweepnyc.nyc.gov/mappingapi/api/highlight/sweepinfo', {'lat': lat, 'lon': lon, 't': int(time.time() * 1000), 'radius': 0.5})
            (RAW / filename).write_text(json.dumps({'url': response.url, 'response': response.json()}, indent=2), encoding='utf-8')
            receipts[-1]['sha256'] = hashlib.sha256((RAW / filename).read_bytes()).hexdigest()
        (RAW / 'fetch_manifest.json').write_text(json.dumps(receipts, indent=2), encoding='utf-8')
    target = (RAW / 'lion_23c').resolve()
    with zipfile.ZipFile(RAW / 'nyclion_23c.zip') as archive:
        for name in archive.namelist():
            if not (target / name).resolve().is_relative_to(target):
                raise ValueError('Unsafe archive path')
        archive.extractall(target)


if __name__ == '__main__':
    main()
