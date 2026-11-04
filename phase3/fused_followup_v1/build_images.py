"""Build two local worker versions only; never creates/starts research containers.

No pulls/downloads. Contexts read minimized development inputs and six local
development challenges only. Boundary image inherits clean Python, not an audit
image/layer. Original pinned images and contexts are never changed.
"""
import argparse
import shutil
import subprocess
from .protocol import HERE, PROJECT, DEV, BOUNDARY, VERSION, read, digest, file_hash, write_new

BASE='sha256:a33f8214653b7d5368f622a860de848c20c77864db93ec9d5227373ebe2a405d'
CONTEXTS=HERE/'image_contexts_v1'
DEV_TAG='cs5491-followup-local:dev-a33f8214653b'
PY_TAG='cs5491-followup-local:python-5be5aaecb962'
NP_TAG='cs5491-followup-local:numpy-a10efedb2382'


def prepare():
    target=CONTEXTS
    if target.exists():raise PermissionError('Do not overwrite frozen image contexts')
    development=target/'development';boundary=target/'boundary'
    development.mkdir(parents=True);boundary.mkdir()
    shutil.copyfile(HERE/'worker_v1.py',development/'candidate_worker.py')
    (development/'Dockerfile').write_text('FROM '+DEV_TAG+'\nCOPY --chown=0:0 candidate_worker.py /app/candidate_worker.py\n',encoding='utf-8')
    # COPY does not require root or a RUN command; the resulting file is read-only
    # under the same read-only root runtime. Config/user remain inherited.
    for name in ('worker.py','phase1d_worker.py','research_core.py','interface.py','common.py','specification.txt','LICENSE'):
        shutil.copyfile(DEV/name,boundary/name)
    shutil.copyfile(PROJECT/'phase3/static_policy.py',boundary/'static_policy.py')
    shutil.copyfile(HERE/'worker_v1.py',boundary/'candidate_worker.py')
    shutil.copyfile(BOUNDARY,boundary/'states.json')
    write_new(boundary/'research_data.json',{'boundary':{}})
    write_new(boundary/'development_or3.json',{'synthetic_security_fixture':{'capacity':10,'num_items':2,'items':[4,4]}})
    write_new(boundary/'dataset_scope.json',{'dataset':'boundary','state_set':'fingerprint','sizes':[6],'actions':['fingerprint']})
    shutil.copyfile(PROJECT/'phase3/Dockerfile',boundary/'Dockerfile')
    return target


def build():
    if (HERE/'image_receipt.json').exists():raise PermissionError('Build receipt exists; do not rebuild')
    target=prepare();old=read(PROJECT/'phase3/slot12_recovery/build_receipt.json')['images']['development']
    docker=shutil.which('docker')
    if not docker:raise RuntimeError('Docker CLI unavailable')
    # BuildKit interprets bare sha256 image IDs in FROM as registry names.
    # Use explicit local-only aliases and verify each alias against the sealed
    # immutable image before build. No pull or remote base substitution.
    import json
    for image,tag in ((BASE,DEV_TAG),(old['PythonImage'],PY_TAG),(old['NumpyCopySource'],NP_TAG)):
        subprocess.run([docker,'image','inspect',image],capture_output=True,check=True,timeout=20)
        subprocess.run([docker,'tag',image,tag],capture_output=True,check=True,timeout=20)
        actual=json.loads(subprocess.run([docker,'image','inspect',tag],capture_output=True,text=True,check=True,timeout=20).stdout)[0]['Id']
        if actual!=image:raise RuntimeError('Local base alias differs')
    images={}
    for name in ('development','boundary'):
        context=target/name;iid=HERE/(name+'.iid')
        args=[docker,'build','--network=none','--pull=false','--iidfile',str(iid)]
        if name=='boundary':args+=['--build-arg','PYTHON_IMAGE='+PY_TAG,'--build-arg','NUMPY_IMAGE='+NP_TAG]
        p=subprocess.run(args+[str(context)],capture_output=True,text=True,timeout=180,check=False)
        (HERE/(name+'_local_refs_build.log')).write_text(p.stdout+'\n'+p.stderr,encoding='utf-8')
        if p.returncode:raise RuntimeError('Build failed; do not retry automatically: '+name)
        image=iid.read_text().strip()
        info=json.loads(subprocess.run([docker,'image','inspect',image],capture_output=True,text=True,check=True,timeout=20).stdout)[0]
        if info['Id']!=image or info['Os']!='linux' or info['Config']['User']!='65532:65532':raise RuntimeError('Image identity/config differs')
        images[name]={'image':image,'base':BASE if name=='development' else old['PythonImage'],
            'context_sha256':{p.name:file_hash(p) for p in sorted(context.iterdir()) if p.is_file()},
            'rootfs_layers':info['RootFS']['Layers'],'runtime_container_validation':'NOT TESTED; first three authorized tasks required'}
    write_new(HERE/'image_receipt.json',{'version':VERSION,'images':images,'research_tasks_started':0,
        'new_model_calls':0,'new_candidate_executions':0,'network':'none','pull':False,
        'initial_failed_build':'development_build.log; bare image-ID FROM triggered failed registry metadata resolution, no image/candidate task produced',
        'local_base_aliases':{DEV_TAG:BASE,PY_TAG:old['PythonImage'],NP_TAG:old['NumpyCopySource']},
        'development_dataset_sha256':old['dataset_sha256'],'old_state_bank_sha256':old['state_bank_sha256'],
        'boundary_state_bank_sha256':digest(read(BOUNDARY))})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--build',action='store_true',required=True)
    parser.parse_args();build()
