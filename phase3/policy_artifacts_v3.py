"""Static provenance for old/v3 sources and one-use full-feedback proposals."""
import argparse
import hashlib
import json
from pathlib import Path
import bootstrap3
from bootstrap3 import ROOT
from common import read,write,file_hash,digest
from generation3 import load_candidate
from generation_policy_v3 import policy,sampling_seed,POLICY_PATH
from manifest3 import check_pool as check_old_pool,scope_slot
from approval import control_sources
from static_policy import validate


def check_pool(path):
    path=Path(path).resolve();pool=read(path)
    if pool.get('schema')=='qwen-fixed-pool-v1':return check_old_pool(path)
    value=policy()
    if (pool.get('schema')!='qwen-policy-v3-pool-v1' or pool.get('model')!=value['model']
        or pool.get('model_digest')!=value['digest'] or pool.get('generation_policy_sha256')!=file_hash(POLICY_PATH)):
        raise PermissionError('Unknown/mixed generation policy')
    if len(pool['candidates'])!=1 or pool['actual_api_attempts']!=1:raise PermissionError('One source per real transition')
    row=pool['candidates'][0];directory=path.parent/'candidate_001'
    if row['candidate_id']!=1 or read(directory/'candidate.json')!=row:raise PermissionError('Source ledger differs')
    request=read(directory/'request.json');slot=request['reservation']['call_slot']
    if slot not in (11,12) or request['reservation']['generation_purpose']!='feedback':
        raise PermissionError('Not a reserved real-feedback call')
    if request['policy_sha256']!=file_hash(POLICY_PATH):raise PermissionError('Policy changed')
    payload=request['payload']
    for name in ('model','temperature','top_p','max_tokens','reasoning_effort','n','stream'):
        if payload[name]!=value[name]:raise PermissionError('Mixed generation controls: '+name)
    if payload['seed']!=sampling_seed(99,slot) or row['sampling_seed']!=payload['seed']:
        raise PermissionError('Sampling seed does not match frozen global ordinal')
    if (request['model_metadata']['digest']!=value['digest']
        or request['model_metadata']['details']['quantization_level']!=value['quantization']):
        raise PermissionError('Model identity changed')
    if (request['island_id']!=row['island_id'] or request['version_generated']!=row['version_generated']
        or file_hash(path.parent/'database_before_001.json')!=row['database_checkpoint_sha256']
        or digest(payload['messages'])!=row['prompt_sha256']):
        raise PermissionError('Real prompt/checkpoint identity differs')
    if not request['verified_feedback'].get('verified_real_model_feedback'):
        raise PermissionError('Missing real feedback proof')
    if row.get('source_sha256'):
        candidate=load_candidate(path,row)
        raw=(directory/'raw_http_response.bin').read_bytes();response=json.loads(raw)
        if hashlib.sha256(raw).hexdigest()!=row['raw_response_sha256'] or read(directory/'response.json')!=response:
            raise PermissionError('Raw server response changed')
        if (response['model']!=value['model'] or len(response['choices'])!=1
            or response['choices'][0]['message']['content']!=candidate.text
            or response['choices'][0]['finish_reason']!=row['finish_reason'] or response.get('usage')!=row.get('usage')):
            raise PermissionError('Source is not the original server response')
    return pool


def make_one_evaluation(pool_file,output):
    pool=check_pool(pool_file)
    if len(pool['candidates'])!=1:raise ValueError('For old nine-source pool use its existing first-evaluation request')
    row=pool['candidates'][0]
    candidate=load_candidate(pool_file,row)
    parsed,static=validate(candidate.text,row['expected_name'],row['finish_reason'])
    build=read(ROOT/'build_receipt.json')['images']['development']
    slot=scope_slot('live_feedback','feedback',row,build,'full')
    result={'schema':'finite-source-task-set-v1','approved':False,'candidate_pool':str(Path(pool_file).resolve()),
        'candidate_pool_sha256':file_hash(pool_file),'candidates':[{'candidate_id':1,
            'source_sha256':row['source_sha256'],'expected_name':row['expected_name'],'source':candidate.text,
            'static':static,'generation_island_id':row['island_id'],'generation_version':row['version_generated']}],
        'dispatch_slots':[slot],'maximum_container_dispatches':1,'maximum_full_evaluations':1,
        'maximum_wall_seconds_per_task':10,'heldout_access':False,'fused_model_execution':False,
        'new_generation_calls_authorized':0,'control_sha256':control_sources(),
        'generation_policy_sha256':file_hash(POLICY_PATH),
        'note':'Actual newly generated source; one isolated full evaluation/registration only, no extra requests or retries.'}
    write(output,result);return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pool',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();make_one_evaluation(a.pool,a.output);print(str(a.output)+' NOT APPROVAL')
