"""Only replace the static checker in the existing minimized images, offline."""
import json
import os
from pathlib import Path
import shutil
from time import perf_counter
import bootstrap3
from bootstrap3 import ROOT, PROJECT
from common import read, write, file_hash
from container_runner import cli, docker_path, discover
from static_policy import POLICY_ID


def main():
    if not discover()['usable']:
        raise RuntimeError('Existing Docker Linux Engine unavailable')
    out = ROOT/'slot12_recovery'; context = out/'image_patch'
    context.mkdir(exist_ok=True)
    dockerfile = ('ARG BASE_IMAGE\nFROM ${BASE_IMAGE}\n'
        'COPY --chown=0:0 --chmod=0444 static_policy.py /app/static_policy.py\n')
    if (context/'Dockerfile').exists() and (context/'Dockerfile').read_text(encoding='utf-8') != dockerfile:
        raise PermissionError('Existing patch Dockerfile differs')
    if (context/'static_policy.py').exists() and file_hash(context/'static_policy.py') != file_hash(ROOT/'static_policy.py'):
        raise PermissionError('Existing patch policy differs')
    (context/'Dockerfile').write_text(dockerfile,encoding='utf-8')
    shutil.copyfile(ROOT/'static_policy.py',context/'static_policy.py')
    docker = docker_path(); images = {}
    os.environ['PATH'] = str(Path(docker).parent)+os.pathsep+os.environ['PATH']
    for scope, old in read(ROOT/'build_receipt.json')['images'].items():
        before = json.loads(cli(docker,['image','inspect',old['tag']]).stdout)[0]
        if before['Id'] != old['ImageId']:
            raise PermissionError('Existing base tag differs from its pinned receipt')
        tag = 'cs5491-phase3-'+scope+':static-policy-v2'
        started = perf_counter()
        result = cli(docker,['build','--network=none','--pull=false','--build-arg',
            'BASE_IMAGE='+old['tag'],'--tag',tag,str(context)],timeout=120)
        (out/(scope+'_build_stdout.txt')).write_text(result.stdout,encoding='utf-8')
        (out/(scope+'_build_stderr.txt')).write_text(result.stderr,encoding='utf-8')
        item = json.loads(cli(docker,['image','inspect',tag]).stdout)[0]
        if (item['RootFS']['Layers'][:-1] != before['RootFS']['Layers']
                or len(item['RootFS']['Layers']) != len(before['RootFS']['Layers'])+1
                or item['Config'] != before['Config']):
            raise PermissionError('Patch changed more than one policy file layer or image runtime config')
        images[scope] = {**old, 'ImageId':item['Id'], 'tag':tag,
            'base_image':old['ImageId'], 'rootfs_layers':item['RootFS']['Layers'],
            'build_seconds':perf_counter()-started,
            'note':'Base context receipt remains historical; only /app/static_policy.py is replaced.'}
        write(out/'build_progress.json',images)
        print(scope+' '+item['Id'],flush=True)
    write(out/'build_receipt.json', {'static_policy':POLICY_ID,
        'static_policy_sha256':file_hash(ROOT/'static_policy.py'),
        'isolation_policy_sha256':file_hash(PROJECT/'phase1b/phase1c/policy.json'),
        'network':'none','downloads':0,'images':images,
        'patch_context_sha256':{p.name:file_hash(p) for p in context.iterdir()}})


if __name__ == '__main__':main()
