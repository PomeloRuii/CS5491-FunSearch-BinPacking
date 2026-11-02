"""Check inventoried files and original candidate static statuses; never execute."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    manifest=json.loads((ROOT/'RELEASE_INVENTORY.json').read_text(encoding='utf-8'))
    for row in manifest['files']:
        path=(ROOT/row['path']).resolve()
        if not path.is_relative_to(ROOT) or hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('Inventory file changed: '+row['path'])
    expected={r['path'] for r in manifest['files']}|{'RELEASE_INVENTORY.json'}
    actual={p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file()
            and '.git' not in p.relative_to(ROOT).parts and '__pycache__' not in p.relative_to(ROOT).parts}
    if actual!=expected:raise ValueError('Uninventoried/missing release files')
    sys.path.insert(0,str(ROOT/'phase3'))
    import bootstrap3
    from static_policy import validate
    ledger=json.loads((ROOT/'candidates/ledger.json').read_text(encoding='utf-8'));passed=0;rejected=0
    for row in ledger:
        path=ROOT/f'candidates/{row["candidate_id"]:03d}/source.py.txt'
        source=path.read_bytes()
        assert hashlib.sha256(source).hexdigest()==row['source_sha256']
        try:validate(source.decode(),row['expected_name'],row['finish_reason'])
        except (ValueError,SyntaxError):
            assert row['status']=='static_rejected';rejected+=1
        else:
            assert row['status']=='static_valid_pending_execution_approval';passed+=1
    assert len(ledger)==16 and passed==10 and rejected==6
    print(json.dumps({'inventory_files_checked':len(manifest['files']),'static_passes':passed,
        'static_rejections':rejected,'candidate_functions_executed':0,'model_requests':0},indent=2))


if __name__=='__main__':main()
