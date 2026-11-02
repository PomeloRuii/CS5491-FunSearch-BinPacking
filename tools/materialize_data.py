"""Materialize separately supplied frozen JSON only, without held-out inputs."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists():raise PermissionError('Refuse to overwrite local data: '+str(path))
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')


def main(args):
    expected=read(ROOT/'data/DATA_REQUIREMENTS.json')
    data=read(args.development_data);dev=read(args.development_states);audit=read(args.audit_states)
    if set(data)!={'development'} or set(dev)!={'fingerprint'} or set(audit)!={'audit'}:
        raise ValueError('Only minimized development/fingerprint/reserved-audit JSON accepted')
    if (digest(data['development'])!=expected['development_dataset_canonical_sha256']
            or digest(dev)!=expected['development_state_bank_canonical_sha256']
            or digest(audit)!=expected['audit_state_bank_canonical_sha256']):
        raise ValueError('Frozen content hash differs: no substitution or regeneration')
    write(ROOT/'phase2/data/research_data.json',{'development':data['development'],'audit':{}})
    write(ROOT/'phase2/data/states.json',{**dev,**audit})
    for scope,d,s in (('development',data,dev),('audit',{'audit':{}},audit)):
        folder=ROOT/'phase3/build_contexts'/scope
        write(folder/'research_data.json',d);write(folder/'states.json',s)
        baseline=(data['development']['OR3'] if scope=='development' else
                  {'synthetic_security_fixture':{'capacity':10,'num_items':2,'items':[4,4]}})
        write(folder/'development_or3.json',baseline)
    print('Verified frozen minimized local inputs; no held-out values/model calls/source execution. Fresh image validation and execution grants still required.')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--development-data',type=Path,required=True)
    p.add_argument('--development-states',type=Path,required=True);p.add_argument('--audit-states',type=Path,required=True)
    main(p.parse_args())
