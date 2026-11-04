"""Container-only fused worker v1; existing packing functions stay unchanged.

Tests inject inert core doubles; production imports/executes candidate functions
only after Linux container checks and inside the disposable restricted worker.
"""
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

VERSION='fresh-candidate-fused-v1'


def digest(v):
    return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def execute(payload, root=Path('/app'), core=None, validator=None):
    if core is None:
        if sys.platform!='linux' or not Path('/.dockerenv').is_file():
            raise PermissionError('Production candidate execution requires Linux container')
        import research_core as core
    if validator is None:
        from static_policy import validate as validator
    start=perf_counter();body=payload['body'];task=payload['task']
    if not isinstance(body,str) or len(body)>32768 or hashlib.sha256(body.encode()).hexdigest()!=payload['body_sha256']:
        raise ValueError('Body identity/size differs')
    validator('def priority(item, bins):\n'+body,'priority')
    scope=json.loads((root/'dataset_scope.json').read_text())
    if (task['worker_version']!=VERSION or task['dataset']!=scope['dataset'] or task['action'] not in scope['actions']):
        raise PermissionError('Image action/data/version differs')
    action=task['action']
    if action!='full' and (task['state_set']!=scope['state_set'] or task['fingerprint_size'] not in scope['sizes']):
        raise PermissionError('Fingerprint scope differs')
    data=json.loads((root/'research_data.json').read_text());groups=data[task['dataset']]
    if digest(groups)!=task['dataset_sha256']:raise ValueError('Dataset differs')
    out={'job_id':payload['job_id'],'body_sha256':payload['body_sha256'],'task':task,
         'worker_version':VERSION,'validity_policy':'obp-validity-v1','full_evaluation_performed':False}
    original=core.namespace_for;namespace_times=[]
    def fresh(body):
        then=perf_counter()
        try:return original(body)
        finally:namespace_times.append(perf_counter()-then)
    core.namespace_for=fresh
    try:
        if action in ('fused','fingerprint'):
            bank=json.loads((root/'states.json').read_text())
            if digest(bank)!=task['state_bank_sha256']:raise ValueError('State bank differs')
            states=bank[task['state_set']][:task['fingerprint_size']]
            if len(states)!=task['fingerprint_size']:raise ValueError('Incomplete state coverage')
            then=perf_counter()
            try:out.update(core.fingerprint(body,states))
            finally:
                print(json.dumps({'kind':'task_stage','stage':'fingerprint_finished',
                    'fingerprint_phase_seconds':perf_counter()-then,
                    'fingerprint_namespace_seconds':sum(namespace_times)}),file=sys.stderr,flush=True)
            out['fingerprint_namespace_seconds']=sum(namespace_times)
            if action=='fingerprint':return out
            reps=task['representatives']
            if any(len(r['decisions'])!=len(states) for r in reps):raise ValueError('Malformed representative vector')
            match=next((r['candidate_id'] for r in reps if r['decisions']==out['decisions']),None)
            if match is not None:
                out['matched_representative_id']=match
                if task.get('required_branch')=='full':raise RuntimeError('Trusted nonmatch unexpectedly matched')
                return out
        if not task['allow_full'] or task.get('required_branch')=='skip':
            raise PermissionError('Full evaluation outside this exact task scope')
        # full_evaluation calls namespace_for again: new namespace, same candidate,
        # same container. A different candidate always requires a new container.
        before=len(namespace_times)
        print(json.dumps({'kind':'task_stage','stage':'full_evaluation_started'}),file=sys.stderr,flush=True)
        out.update(core.full_evaluation(body,groups))
        out['full_namespace_seconds']=sum(namespace_times[before:])
        out['full_evaluation_performed']=True
        return out
    finally:
        core.namespace_for=original
        out['worker_execute_seconds']=perf_counter()-start
        print(json.dumps({'kind':'task_stage','stage':'worker_finished','worker_execute_seconds':perf_counter()-start}),file=sys.stderr,flush=True)


def main():
    try:
        if sys.platform!='linux' or not Path('/.dockerenv').is_file():raise PermissionError('Linux container required')
        sys.path.insert(0,'/app')
        from worker import context
        print(json.dumps({'kind':'context','context':context()}),file=sys.stderr,flush=True)
        line=sys.stdin.buffer.readline(65537)
        if len(line)>65536 or not line.endswith(b'\n'):raise ValueError('Request framing/size differs')
        result=execute(json.loads(line))
        print(json.dumps({'kind':'result','result':result},allow_nan=False),flush=True)
        return 0
    except Exception as exc:
        print(json.dumps({'kind':'error','error':{'type':type(exc).__name__,'message':str(exc)}}),file=sys.stderr,flush=True)
        return 1


if __name__=='__main__':raise SystemExit(main())
