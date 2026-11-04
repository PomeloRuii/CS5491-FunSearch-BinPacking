"""Prospective host contract v1: minimized frozen development inputs only.

No legacy import, dataset reconstruction, held-out fallback or module-level data
initialization. Historical receipts retain their original source identities.
"""
import hashlib
import json
from pathlib import Path

CONTRACT = 'host-development-only-v1'
PROJECT = Path(__file__).resolve().parent.parent
DATA = PROJECT / 'phase3/build_contexts/development/research_data.json'
EXPECTED = 'a9709f23f17aaf0e083a989e1b5ccf53ac91221987128d5480ff1093f594c401'


def canonical_hash(value):
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def load_development(path=DATA):
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    if set(value) != {'development'} or canonical_hash(value['development']) != EXPECTED:
        raise PermissionError('Frozen development-only input identity differs; no fallback')
    groups = value['development']
    if set(groups) != {'OR3', 'Weibull 5k'} or [len(groups[k]) for k in ('OR3', 'Weibull 5k')] != [12, 3]:
        raise PermissionError('Development group coverage differs')
    return groups
