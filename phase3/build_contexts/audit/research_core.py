"""Fresh-container research tasks. Model-origin execution remains host-gated.

The unchanged specification defines packing/fitness. All probes and full calls use
the same obp-validity-v1 checker. No state is reused across different candidates.
"""
import ast
import hashlib
import json
import math
from pathlib import Path
import sys
from time import perf_counter


def content_hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()


def namespace_for(body):
    fragment=ast.parse("def priority(item, bins):\n"+body)
    if len(fragment.body)!=1 or len(list(ast.walk(fragment)))>3000:
        raise ValueError("Invalid bounded function body")
    tree=ast.parse(Path('/app/specification.txt').read_text(encoding='utf-8'))
    for node in tree.body:
        if isinstance(node,ast.FunctionDef):
            node.decorator_list=[]
            if node.name=='priority':node.body=fragment.body[0].body
    ast.fix_missing_locations(tree);namespace={}
    exec(compile(tree,'<isolated-research-candidate>','exec'),namespace)
    return namespace


def fingerprint(body,states):
    import numpy as np
    from phase1d_worker import validate_priority_scores
    namespace=namespace_for(body);priority=namespace['priority']
    decisions=[];start=perf_counter()
    for state in states:
        if state['bins_dtype'] not in ('int64','float64'):
            raise ValueError('State dtype differs from supported Linux evaluator types')
        bins=np.asarray(state['bins'],dtype=state['bins_dtype'])
        item=state['item'];indices=state['valid_bin_indices']
        if type(item).__name__!=state['item_scalar_type']:raise ValueError('Item scalar type differs')
        if bins.ndim!=1 or len(bins)!=len(indices) or not len(bins) or not np.all(bins>=item) or item<=0:
            raise ValueError('Invalid fingerprint state')
        scores=validate_priority_scores(priority(item,bins),bins)
        decisions.append(int(indices[int(np.argmax(scores))]))
    return {'decisions':decisions,'fingerprint_seconds':perf_counter()-start,
            'state_ids':[s['state_id'] for s in states]}


def full_evaluation(body,groups):
    from phase1d_worker import validate_priority_scores
    namespace=namespace_for(body);priority=namespace['priority'];calls=[0]
    def checked(item,bins):
        values=validate_priority_scores(priority(item,bins),bins);calls[0]+=1;return values
    namespace['priority']=checked
    scores={};details={};start=perf_counter()
    for family,instances in groups.items():
        before=calls[0];stage=perf_counter()
        score=float(namespace['evaluate'](instances))
        if not math.isfinite(score):raise ValueError('Nonfinite group fitness')
        expected=sum(len(x['items']) for x in instances.values())
        if calls[0]-before!=expected:raise ValueError('Incomplete group coverage')
        scores[family]=score
        details[family]={'instances_completed':len(instances),'priority_calls':expected,
                         'pure_evaluate_seconds':perf_counter()-stage}
    return {'scores_per_group':scores,'score':sum(scores.values())/len(scores),
            'group_details':details,'pure_evaluate_seconds':perf_counter()-start}


def execute(payload):
    body=payload['body']
    if not isinstance(body,str) or len(body)>32768:raise ValueError('Body size invalid')
    if hashlib.sha256(body.encode()).hexdigest()!=payload['body_sha256']:raise ValueError('Body checksum differs')
    task=payload['task'];action=task['action']
    if action not in ('full','fingerprint','fused','audit_full'):raise ValueError('Unsupported action')
    data=json.loads(Path('/app/research_data.json').read_text(encoding='utf-8'))
    bank=(json.loads(Path('/app/states.json').read_text(encoding='utf-8'))
          if action!='full' else None)
    dataset=task['dataset']
    if dataset=='legacy_validation':groups={'OR3':json.loads(Path('/app/or3.json').read_text())}
    elif dataset in ('development','audit'):groups=data[dataset]
    else:raise ValueError('Dataset scope not allowed')
    if content_hash(groups)!=task['dataset_sha256']:raise ValueError('Dataset identity differs')
    if bank is not None and content_hash(bank)!=task['state_bank_sha256']:raise ValueError('State bank identity differs')
    out={'job_id':payload['job_id'],'body_sha256':payload['body_sha256'],
         'task':task,'validity_policy':'obp-validity-v1','full_evaluation_performed':False}
    if action in ('fingerprint','fused','audit_full'):
        state_set=task['state_set'];n=task['fingerprint_size']
        if state_set not in ('fingerprint','audit') or type(n) is not int:
            raise ValueError('State request invalid')
        if (state_set=='fingerprint' and n not in (16,64,128)) or (state_set=='audit' and n!=256):
            raise ValueError('State count not allowed')
        fp=fingerprint(body,bank[state_set][:n]);out.update(fp)
        print(json.dumps({'kind':'task_stage','stage':'fingerprint_completed',
                          'fingerprint_seconds':fp['fingerprint_seconds']}),file=sys.stderr,flush=True)
        if action=='fingerprint':return out
        if action=='fused':
            for rep in task.get('representatives',[]):
                if rep['decisions']==fp['decisions']:
                    out['matched_representative_id']=rep['candidate_id']
                    return out
    # Recreate the candidate namespace before full evaluation. Same candidate,
    # same fresh container; no Python state ever crosses candidate boundaries.
    print(json.dumps({'kind':'task_stage','stage':'full_evaluation_started'}),file=sys.stderr,flush=True)
    out.update(full_evaluation(body,groups));out['full_evaluation_performed']=True
    return out


def main():
    try:
        if sys.platform!='linux' or not Path('/.dockerenv').is_file():raise PermissionError('Linux container required')
        sys.path.insert(0,'/app')
        from worker import context
        print(json.dumps({'kind':'context','context':context()}),file=sys.stderr,flush=True)
        line=sys.stdin.buffer.readline(65537)
        if len(line)>65536 or not line.endswith(b'\n'):raise ValueError('Request size/framing invalid')
        result=execute(json.loads(line))
        print(json.dumps({'kind':'result','result':result},allow_nan=False),flush=True)
        return 0
    except Exception as exc:
        print(json.dumps({'kind':'error','error':{'type':type(exc).__name__,'message':str(exc)}}),file=sys.stderr,flush=True)
        return 1


if __name__=='__main__':raise SystemExit(main())
