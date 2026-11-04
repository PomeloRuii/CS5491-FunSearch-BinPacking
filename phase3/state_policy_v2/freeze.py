"""Freeze S2 and prospective diagnostic bank; trusted development processing only."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from phase1b.development_data_v1 import load_development, EXPECTED
from .states import construct, digest, SIZES

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
S0 = PROJECT / 'phase3/build_contexts/development/states.json'
CHALLENGES = PROJECT / 'phase3/post_publication_v1/boundary_challenges.local.json'
DATA = PROJECT / 'phase3/build_contexts/development/research_data.json'


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, indent=2, allow_nan=False) + '\n')


def build(directory=HERE):
    if (directory / 'freeze_manifest.json').exists() or (directory / '.local_data').exists():
        raise PermissionError('Frozen output already exists; do not overwrite or reroll')
    groups = load_development()
    original = json.loads(S0.read_text())
    challenges = json.loads(CHALLENGES.read_text())
    if set(original) != {'fingerprint'} or set(challenges) != {'fingerprint'}:
        raise PermissionError('Construction-only historical input scope differs')
    bank, validation, report = construct(groups, original['fingerprint'], challenges['fingerprint'])
    source_hashes = {f.name: file_hash(f) for f in (HERE/'states.py', HERE/'freeze.py')}
    raw = directory / '.local_data'
    write_new(raw / 's2_states.json', bank)
    write_new(raw / 'validation_states.json', validation)
    report['banks'] = {'S2': dict(path='.local_data/s2_states.json', sha256=file_hash(raw/'s2_states.json'), canonical_sha256=digest(bank)),
                       'validation': dict(path='.local_data/validation_states.json', sha256=file_hash(raw/'validation_states.json'), canonical_sha256=digest(validation))}
    report['prefixes'] = {str(n): dict(states=len(bank['fingerprint'][:n]),
                                          canonical_sha256=digest(bank['fingerprint'][:n]),
                                          input_ids=[s['state_id'] for s in bank['fingerprint'][:n]]) for n in SIZES}
    report['validation_input_ids'] = [s['state_id'] for s in validation['validation']]
    write_new(directory / 'coverage_report.json', report)
    manifest = dict(schema='state-policy-v2.0-freeze', frozen_at_utc=datetime.now(timezone.utc).isoformat(),
                    frozen_development_canonical_sha256=EXPECTED,
                    inputs={'development_file': file_hash(DATA), 'original_S0': file_hash(S0),
                            'historical_dev_challenges': file_hash(CHALLENGES)},
                    builder_source_sha256=source_hashes, banks=report['banks'],
                    coverage_report_sha256=file_hash(directory/'coverage_report.json'),
                    supported_sizes={str(n): report['construction']['sizes'][str(n)]['behavioral_skipping_supported'] for n in SIZES},
                    fixed_validation_states=len(validation['validation']),
                    validation_supported=report['validation']['coverage']['behavioral_skipping_supported'],
                    candidate_evaluations=0, model_calls=0, heldout_access=False,
                    freeze_before_candidate_evaluation=True)
    write_new(directory / 'freeze_manifest.json', manifest)
    print(json.dumps({'freeze_sha256': file_hash(directory/'freeze_manifest.json'),
                      'supported_sizes': manifest['supported_sizes'], 'validation_states': manifest['fixed_validation_states'],
                      'validation_supported': manifest['validation_supported'], 'banks': report['banks']}, indent=2))


if __name__ == '__main__':
    build()
