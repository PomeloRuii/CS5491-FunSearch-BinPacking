"""Build one minimal extension from the existing pinned local worker image."""
import hashlib
import json
import os
from pathlib import Path
import shutil
from time import perf_counter

import phase2_bootstrap
from phase2_bootstrap import ROOT,PHASE1B
from container_runner import docker_path,cli


def main():
    context=ROOT/'build_context';context.mkdir(exist_ok=True)
    sources={'Dockerfile':ROOT/'Dockerfile','research_worker.py':ROOT/'research_worker.py',
             'phase1d_worker.py':PHASE1B/'phase1d/candidate_worker.py',
             'research_data.json':ROOT/'data/research_data.json','states.json':ROOT/'data/states.json',
             'LICENSE':PHASE1B/'reference/LICENSE'}
    if any(p.name not in sources or not p.is_file() for p in context.iterdir()):
        raise PermissionError('Unexpected build context contents')
    for name,path in sources.items():shutil.copyfile(path,context/name)
    docker=docker_path();os.environ['PATH']=str(Path(docker).parent)+os.pathsep+os.environ['PATH']
    base=json.loads((PHASE1B/'phase1d/build_receipt.json').read_text())['ImageId']
    tag='cs5491-phase1d:reviewed'
    if json.loads(cli(docker,['image','inspect',tag]).stdout)[0]['Id']!=base:raise PermissionError('Base tag differs')
    start=perf_counter()
    cli(docker,['build','--network=none','--pull=false','--build-arg','BASE_IMAGE='+tag,
                '--tag','cs5491-phase2:reviewed',str(context)],timeout=120)
    image=json.loads(cli(docker,['image','inspect','cs5491-phase2:reviewed']).stdout)[0]['Id']
    record={'ImageId':image,'BaseImageId':base,'build_seconds':perf_counter()-start,
            'research_source_sha256':{str(path.relative_to(ROOT)).replace('\\','/'):hashlib.sha256(path.read_bytes()).hexdigest()
                                     for path in sources.values() if path.is_relative_to(ROOT)},
            'context_sha256':{name:hashlib.sha256(path.read_bytes()).hexdigest() for name,path in sources.items()},
            'network_during_build':'none','generated_execution_enabled':False}
    (ROOT/'build_receipt.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record,indent=2))


if __name__=='__main__':main()
