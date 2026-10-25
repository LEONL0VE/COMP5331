"""Fetch a bounded, historical public spatial dataset after mock validation succeeds."""

import csv
import hashlib
import io
import json
import os
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import numpy as np
from _common import ROOT, require_mock_success, save_json, timestamp
from density_explain.datasets import load_usgs_csv


def main():
    require_mock_success()
    config = json.loads((ROOT / 'configs' / 'real.json').read_text())
    url = 'https://earthquake.usgs.gov/fdsnws/event/1/query?' + urlencode(config['query'])
    raw_path = ROOT / 'data' / 'raw' / (config['dataset'] + '.csv')
    provenance_path = raw_path.with_suffix('.json')
    if not raw_path.exists():
        request = Request(url, headers={'User-Agent': 'COMP5331-ExDBSCAN-reproduction/0.1'})
        with urlopen(request, timeout=60) as response:
            payload = response.read(20_000_001)
        if len(payload) > 20_000_000:
            raise RuntimeError('Unexpectedly large response; narrow the configured query')
        text = payload.decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(text))
        required = {'id', 'time', 'latitude', 'longitude'}
        if not required.issubset(reader.fieldnames or []):
            raise RuntimeError('USGS response is not the expected CSV format')
        count = sum(1 for _ in reader)
        if not count or count >= config['query']['limit']:
            raise RuntimeError('Empty or possibly truncated dataset; revise the query before proceeding')
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = raw_path.with_suffix('.download')
        temporary.write_bytes(payload)
        os.replace(temporary, raw_path)
        save_json(provenance_path, {
            'source': 'USGS FDSN Earthquake Catalog', 'source_url': url,
            'documentation': 'https://earthquake.usgs.gov/fdsnws/event/1/',
            'retrieved_at': timestamp(), 'raw_sha256': hashlib.sha256(payload).hexdigest(),
            'raw_records': count,
        })
    if not provenance_path.exists():
        raise RuntimeError('Raw data exists without provenance; verify its source before processing')
    provenance = json.loads(provenance_path.read_text())
    if provenance['source_url'] != url:
        raise RuntimeError('Existing snapshot belongs to a different query; use a new dataset name')
    if hashlib.sha256(raw_path.read_bytes()).hexdigest() != provenance['raw_sha256']:
        raise RuntimeError('Raw file differs from the recorded hash')
    X, ids = load_usgs_csv(raw_path, max_points=config['max_points'], origin=tuple(config['origin_lat_lon']))
    processed = ROOT / 'data' / 'processed' / (config['dataset'] + '.npz')
    processed.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(processed, X=X, event_ids=np.array(ids))
    np.savetxt(processed.with_suffix('.csv'), X, delimiter=',', header='east_m,north_m', comments='')
    save_json(processed.with_suffix('.json'), {
        **provenance, 'processed_records': len(X), 'max_points': config['max_points'],
        'origin_lat_lon': config['origin_lat_lon'], 'earth_radius_m': 6371008.8,
        'features': ['east_m', 'north_m'],
        'projection': 'Local equirectangular approximation. Euclidean distances in this plane, not geodesic distances.',
        'cleaning': 'Discard invalid coordinates and repeated event IDs; preserve distinct co-located events; sort by time and ID.',
        'sampling': 'If over max_points, deterministic equally spaced indices in time order.',
        'processed_sha256': hashlib.sha256(processed.read_bytes()).hexdigest(),
    })
    print(f'Prepared {len(X)} real spatial observations from {provenance["raw_records"]} records')
    print(processed)


if __name__ == '__main__':
    main()
