"""Reuse local Python and NumPy; construct disjoint dev/audit task layers offline."""
import argparse
import os
from pathlib import Path
import shutil
from time import perf_counter
import bootstrap3
from bootstrap3 import ROOT, PHASE2, PROJECT
from common import read, write, file_hash, digest
from container_runner import cli, docker_path

def main():
    docker = docker_path()
    os.environ['PATH'] = str(Path(docker).parent)+os.pathsep+os.environ['PATH']
    old = read(PHASE2/'build_receipt.json')['ImageId']
    tag = 'cs5491-phase2:reviewed'
    if read_inspect(docker, tag)['Id'] != old: raise PermissionError('NumPy source tag changed')
    python = read(PROJECT/'phase1b/phase1c/build_receipt.json')['BaseImageDigest']
    pure = read_inspect(docker, python)
    data = read(PHASE2/'data/research_data.json'); bank = read(PHASE2/'data/states.json')
    receipts = {}; start = perf_counter()
    for scope in ('development','audit'):
        context = ROOT/'build_contexts'/scope; context.mkdir(parents=True, exist_ok=True)
        # Old worker probes remain byte-identical except the declared baseline file.
        probe = (PROJECT/'phase1b/phase1c/worker.py').read_text().replace('/app/or3.json','/app/development_or3.json')
        (context/'worker.py').write_text(probe, encoding='utf-8')
        sources = {'Dockerfile':ROOT/'Dockerfile','candidate_worker.py':ROOT/'worker3.py',
            'research_core.py':PHASE2/'research_worker.py',
            'phase1d_worker.py':PROJECT/'phase1b/phase1d/candidate_worker.py',
            'interface.py':PROJECT/'phase1b/phase1d/interface.py',
            'common.py':ROOT/'common.py','static_policy.py':ROOT/'static_policy.py',
            'specification.txt':PROJECT/'phase1b/reference/specification.txt',
            'LICENSE':PROJECT/'phase1b/reference/LICENSE'}
        for name, path in sources.items(): shutil.copyfile(path, context/name)
        if scope == 'development':
            selected = {'development':data['development']}
            selected_states = {'fingerprint':bank['fingerprint']}
            spec = {'dataset':scope,'state_set':'fingerprint','sizes':[16,64,128],
                    'actions':['full','fingerprint','fused']}
            baseline = data['development']['OR3']
        else:
            # No full dev/audit instances needed for a reserved-state decision audit.
            selected = {'audit':{}}
            selected_states = {'audit':bank['audit']}
            spec = {'dataset':scope,'state_set':'audit','sizes':[256], 'actions':['fingerprint']}
            baseline = {'synthetic_security_fixture':{'capacity':10,'num_items':2,'items':[4,4]}}
        for name,value in [('research_data.json',selected),('states.json',selected_states),
                           ('dataset_scope.json',spec),('development_or3.json',baseline)]:
            write(context/name,value)
        allowed = set(sources)|{'worker.py','research_data.json','states.json','dataset_scope.json','development_or3.json'}
        if {p.name for p in context.iterdir()} != allowed: raise PermissionError('Unexpected build context')
        target = 'cs5491-phase3-'+scope+':reviewed'
        began = perf_counter()
        cli(docker, ['build','--network=none','--pull=false','--build-arg','NUMPY_IMAGE='+tag,
                     '--build-arg','PYTHON_IMAGE='+python,'--tag',target,str(context)], timeout=120)
        image = read_inspect(docker,target)
        # Legacy task layers must not be ancestors of this image. Python-only layers allowed.
        # Docker may reuse the canonical empty tar layer for WORKDIR in both
        # images. Its bytes are 1024 zero bytes, not an inherited data layer.
        import hashlib
        empty_tar = 'sha256:'+hashlib.sha256(bytes(1024)).hexdigest()
        legacy_layers = set(read_inspect(docker,old)['RootFS']['Layers'])-set(pure['RootFS']['Layers'])-{empty_tar}
        if legacy_layers & set(image['RootFS']['Layers']): raise PermissionError('Legacy data layer inherited')
        receipts[scope] = {'ImageId':image['Id'],'tag':target,'PythonImage':pure['Id'],
            'NumpyCopySource':old,'legacy_task_layers_inherited':False,
            'scope':spec,'dataset_sha256':digest(selected[scope]),'state_bank_sha256':digest(selected_states),
            'context_sha256':{p.name:file_hash(p) for p in sorted(context.iterdir())},
            'rootfs_layers':image['RootFS']['Layers'],'build_seconds':perf_counter()-began}
        print(scope+' '+image['Id'],flush=True)
    write(ROOT/'build_receipt.json', {'images':receipts,'build_seconds':perf_counter()-start,
        'network_during_build':'none','downloads':0,'generated_execution_authorized':False})

def read_inspect(docker, image):
    import json
    return json.loads(cli(docker,['image','inspect',image]).stdout)[0]

if __name__ == '__main__': main()
