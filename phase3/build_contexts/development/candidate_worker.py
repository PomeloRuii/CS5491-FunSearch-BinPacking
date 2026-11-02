"""Data-minimized task transport; reusable packing functions are from Phase 2."""
import hashlib
import json
from pathlib import Path
import sys

def execute(payload):
    from research_core import content_hash, fingerprint, full_evaluation
    from static_policy import validate
    body = payload['body']
    if not isinstance(body, str) or len(body) > 32768:
        raise ValueError('Body size invalid')
    if hashlib.sha256(body.encode()).hexdigest() != payload['body_sha256']:
        raise ValueError('Body identity differs')
    if payload.get('model_origin'):
        validate('def priority(item, bins):\n'+body, 'priority')
    task = payload['task']; action = task['action']
    scope = json.loads(Path('/app/dataset_scope.json').read_text())
    if task['dataset'] != scope['dataset'] or action not in scope['actions']:
        raise PermissionError('Dataset/action is outside this image scope')
    data = json.loads(Path('/app/research_data.json').read_text())
    groups = data[task['dataset']]
    if content_hash(groups) != task['dataset_sha256']:
        raise ValueError('Dataset hash differs')
    out = {'job_id': payload['job_id'], 'body_sha256': payload['body_sha256'],
           'task': task, 'validity_policy': 'obp-validity-v1', 'full_evaluation_performed': False}
    if action in ('fingerprint','fused'):
        bank = json.loads(Path('/app/states.json').read_text())
        if content_hash(bank) != task['state_bank_sha256']:
            raise ValueError('State bank hash differs')
        state_set = task['state_set']; size = task['fingerprint_size']
        if state_set != scope['state_set'] or type(size) is not int or size not in scope['sizes']:
            raise PermissionError('State scope differs')
        fp = fingerprint(body, bank[state_set][:size]); out.update(fp)
        print(json.dumps({'kind':'task_stage','stage':'fingerprint_completed',
                          'fingerprint_seconds':fp['fingerprint_seconds']}), file=sys.stderr, flush=True)
        if action == 'fingerprint': return out
        for rep in task.get('representatives', []):
            if rep['decisions'] == fp['decisions']:
                out['matched_representative_id'] = rep['candidate_id']; return out
    print(json.dumps({'kind':'task_stage','stage':'full_evaluation_started'}), file=sys.stderr, flush=True)
    out.update(full_evaluation(body, groups)); out['full_evaluation_performed'] = True
    return out

def main():
    try:
        sys.path.insert(0, '/app')
        from worker import context
        print(json.dumps({'kind':'context','context':context()}), file=sys.stderr, flush=True)
        line = sys.stdin.buffer.readline(65537)
        if len(line) > 65536 or not line.endswith(b'\n'):
            raise ValueError('Request framing/size invalid')
        result = execute(json.loads(line))
        print(json.dumps({'kind':'result','result':result}, allow_nan=False), flush=True)
        return 0
    except Exception as exc:
        print(json.dumps({'kind':'error','error':{'type':type(exc).__name__,'message':str(exc)}}), file=sys.stderr, flush=True)
        return 1

if __name__ == '__main__': raise SystemExit(main())
