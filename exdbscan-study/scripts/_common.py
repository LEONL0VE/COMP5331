"""Paths, provenance, and verification gates for reproducible command-line runs."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def source_fingerprint():
    digest = hashlib.sha256()
    files = (sorted((ROOT / 'src').rglob('*.py')) + sorted((ROOT / 'tests').rglob('*.py'))
             + sorted((ROOT / 'scripts').glob('*.py')) + sorted((ROOT / 'configs').glob('*.json'))
             + [ROOT / 'pyproject.toml'])
    for path in files:
        digest.update(str(path.relative_to(ROOT)).encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')


def require_validation():
    path = ROOT / 'results' / 'validation.json'
    if not path.exists():
        raise RuntimeError('Run python scripts/run_validation.py first')
    gate = json.loads(path.read_text())
    if gate['status'] != 'passed' or gate['source_fingerprint'] != source_fingerprint():
        raise RuntimeError('Validation is failed or stale; rerun scripts/run_validation.py')


def require_mock_success():
    require_validation()
    path = ROOT / 'results' / 'mock_gate.json'
    if not path.exists():
        raise RuntimeError('Run python scripts/run_experiments.py --dataset mock first')
    gate = json.loads(path.read_text())
    if gate['status'] != 'passed' or gate['source_fingerprint'] != source_fingerprint():
        raise RuntimeError('Mock validation is failed or stale; rerun mock experiments')
