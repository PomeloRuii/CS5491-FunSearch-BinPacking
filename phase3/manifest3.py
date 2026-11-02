"""Inspect actual Qwen artifacts and prepare an INACTIVE finite task manifest."""
import argparse
import hashlib
from pathlib import Path
import bootstrap3
from bootstrap3 import ROOT,PROJECT
from common import read,write,file_hash,digest
from generation3 import load_candidate
from static_policy import validate
from approval import control_sources

CONFIGURATIONS=[('standard',16),('exact',16),('behavioral',16),('behavioral',64),('behavioral',128)]

def check_pool(path):
    path=Path(path).resolve();pool=read(path)
    cfg=read(ROOT/'config.json')
    if (pool.get('schema')!='qwen-fixed-pool-v1' or pool.get('model')!=cfg['model']
        or pool.get('model_digest')!=cfg['expected_digest']):raise PermissionError('Unknown model/pool provenance')
    rows=pool['candidates']
    if [r['candidate_id'] for r in rows]!=list(range(1,len(rows)+1)) or len(rows)>12:
        raise PermissionError('Pool order/count changed')
    for row in rows:
        directory=path.parent/f"candidate_{row['candidate_id']:03d}"
        if read(directory/'candidate.json')!=row:raise PermissionError('Pool/artifact ledger differs')
        request=read(directory/'request.json')
        if request['island_id']!=row['island_id'] or request['version_generated']!=row['version_generated']:
            raise PermissionError('Generation metadata differs')
        if (request['model_metadata']['digest']!=cfg['expected_digest']
            or request['model_metadata']['details']['quantization_level']!=cfg['expected_quantization']
            or request['payload']['n']!=1 or request['payload']['stream'] is not False):
            raise PermissionError('Model metadata or one-candidate policy differs')
        for setting in ('model','temperature','top_p','max_tokens','seed','reasoning_effort'):
            if request['payload'][setting]!=cfg[setting]:raise PermissionError('Mixed generation settings')
        checkpoint=path.parent/f"database_before_{row['candidate_id']:03d}.json"
        if file_hash(checkpoint)!=row['database_checkpoint_sha256']:raise PermissionError('Database checkpoint changed')
        if row.get('source_sha256'):
            candidate=load_candidate(path,row)
            raw=(directory/'raw_http_response.bin').read_bytes()
            if hashlib.sha256(raw).hexdigest()!=row['raw_response_sha256']:
                raise PermissionError('Raw response changed')
            response=read(directory/'response.json')
            if (__import__('json').loads(raw)!=response or response['model']!=cfg['model']
                or response['choices'][0]['message']['content']!=candidate.text
                or response['choices'][0]['finish_reason']!=row['finish_reason']
                or response.get('usage')!=row.get('usage')):
                raise PermissionError('Source not identical to original response')
    return pool

def scope_slot(configuration,role,row,build,action,size=16,state_set='fingerprint'):
    spec=build['scope']
    value={'configuration':configuration,'role':role,'candidate_id':row['candidate_id'],
        'source_sha256':row['source_sha256'],'image':build['ImageId'],'action':action,
        'dataset':spec['dataset'],'dataset_sha256':build['dataset_sha256'],
        'state_bank_sha256':build['state_bank_sha256'],'state_set':state_set,'fingerprint_size':size}
    return {'slot_id':digest(value),**value}

def make_manifest(pool_file, output, include_feedback=False):
    pool_file=Path(pool_file);pool=check_pool(pool_file);build=read(ROOT/'build_receipt.json')['images']
    reviewed=[];slots=[];invalid=[]
    for row in pool['candidates']:
        if not row.get('source_sha256') or row['status']!='static_valid_pending_execution_approval':
            invalid.append({'candidate_id':row['candidate_id'],'status':row['status'],
                            'failure_reason':row.get('failure_reason')});continue
        candidate=load_candidate(pool_file,row)
        parsed,static=validate(candidate.text,row['expected_name'],row['finish_reason'])
        reviewed.append({'candidate_id':row['candidate_id'],'source_sha256':row['source_sha256'],
            'expected_name':row['expected_name'],'static':static,'source':candidate.text,
            'generation_island_id':row['island_id'],'generation_version':row['version_generated']})
        for mode,size in CONFIGURATIONS:
            label=mode+('-'+str(size) if mode=='behavioral' else '')
            slots.append(scope_slot(label,'normal',row,build['development'],'full'))
            if mode=='behavioral':
                slots.append(scope_slot(label,'normal',row,build['development'],'fingerprint',size))
                slots.append(scope_slot(label,'audit_candidate',row,build['development'],'full'))
                for role in ('audit_candidate','audit_representative'):
                    slots.append(scope_slot(label,role,row,build['audit'],'fingerprint',256,'audit'))
        if include_feedback:
            slots.append(scope_slot('live_feedback','feedback',row,build['development'],'full'))
    value={'schema':'finite-source-task-set-v1','approved':False,
        'candidate_pool':str(pool_file.resolve()),'candidate_pool_sha256':file_hash(pool_file),
        'candidates':reviewed,'invalid_artifacts':invalid,'dispatch_slots':slots,
        'maximum_container_dispatches':len(slots),
        'maximum_full_evaluations':sum(s['action']=='full' for s in slots),
        'fused_model_execution':False,'maximum_wall_seconds_per_task':10,
        'new_generation_calls_authorized':0,'heldout_access':False,
        'control_sha256':control_sources(),
        'risk':'ordinary Docker shared-kernel/controller/output/score-integrity residual risks; no arbitrary-hostile-code claim'}
    write(output,value)
    return value

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pool',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--include-feedback',action='store_true')
    a=p.parse_args();m=make_manifest(a.pool,a.output,a.include_feedback)
    print(str(a.output)+' '+str(len(m['candidates']))+' sources, '+str(len(m['dispatch_slots']))+' finite maximum dispatches; NOT APPROVAL')
