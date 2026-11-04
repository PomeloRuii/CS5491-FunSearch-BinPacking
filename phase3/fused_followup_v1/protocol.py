"""Pure host protocol checks. Never imports or evaluates a candidate function."""
import hashlib
import json
import math
from pathlib import Path

VERSION = 'fresh-candidate-fused-v1'
HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
POOL = PROJECT/'candidates/pool.json'
CHECKPOINT = PROJECT/'research/original_comparison_checkpoint.json'
DEV = PROJECT/'phase3/build_contexts/development'
BOUNDARY = PROJECT/'local_data/development_boundary_states.json'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_new(path, value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('x',encoding='utf-8') as f:
        f.write(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')


def expected_match(decisions, representatives):
    return next((r['candidate_id'] for r in representatives if r['decisions']==decisions), None)


def verify_branch(result, task, states):
    """Recompute worker match identity, validity and full/skip policy on host."""
    action=task['action']
    if result.get('task')!=task or result.get('worker_version')!=VERSION or result.get('validity_policy')!='obp-validity-v1':
        raise RuntimeError('Worker contract/task substitution')
    if action in ('fused','fingerprint'):
        decisions=result.get('decisions',[])
        if (len(decisions)!=len(states) or result.get('state_ids')!=[s['state_id'] for s in states]
                or any(type(d) is not int or d not in s['valid_bin_indices'] for d,s in zip(decisions,states))):
            raise RuntimeError('Fingerprint shape/state/selected-bin validity differs')
        match=expected_match(decisions,task['representatives']) if action=='fused' else None
        if result.get('matched_representative_id')!=match:
            raise RuntimeError('Worker/host representative disagreement')
        full=action=='fused' and match is None
    else:
        if result.get('matched_representative_id') is not None:raise RuntimeError('Full task returned a match')
        match=None;full=True
    if result.get('full_evaluation_performed') is not full:
        raise RuntimeError('Unexpected full-evaluation/skip branch')
    if not full and any(k in result for k in ('score','scores_per_group','group_details')):
        raise RuntimeError('Skipped/probe-only task returned independent fitness')
    if full and not task['allow_full']:
        raise RuntimeError('Full evaluation exceeds task scope')
    return match


def confirmed_terminal(record):
    if not record.get('cleanup_verified'):
        raise RuntimeError('Cleanup uncertain; stop without retry')
    if record['status']=='ok':return
    if record['status']=='runtime_error' and any(m.get('kind')=='error' for m in record.get('worker_messages',[])):return
    # Timeout/OOM are terminal resources failures, but the study stops rather
    # than interpreting incomplete fused phases as scientific rejections.
    raise RuntimeError('Dispatch/protocol/resource outcome uncertain; stop without retry')


def expected_runtime_rejection(record,slot):
    errors=[m.get('error',{}) for m in record.get('worker_messages',[]) if m.get('kind')=='error']
    expected={'type':'ValueError','message':'Priority scores must be finite real numbers under obp-validity-v1'}
    if slot['role']!='normal' or slot['source_id']!=5 or record['status']!='runtime_error' or expected not in errors:
        raise RuntimeError('Unexpected runtime outcome in unchanged pool; stop without retry')
