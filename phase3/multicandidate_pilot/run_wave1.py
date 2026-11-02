"""One authorized Wave-1 session: actual requests, no candidate execution.

Uses the existing metadata/parser/preload/HTTP controls and sealed 8+8 counter.
Every response is retained. No retry or Wave-2 entry point is provided here.
"""
import argparse
from dataclasses import asdict,replace
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
from time import perf_counter
from urllib import request,error
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap3
from bootstrap3 import ROOT,PROJECT
from common import read,write,append,file_hash,digest,stamp
from approval import check_controls,durable_reservation
from generation3 import fixed_config,EventLog
from generation_policy_v3 import messages_for
from interface import expected_name
from static_policy import validate
from ollama_adapter import OllamaAdapter,NoRedirect,MAX_RESPONSE_BYTES
from ollama_readiness import preload
from verified_feedback_v3 import load_verified_feedback
from database_state import restore,snapshot
from two_wave_guards import TwoWaveBudget,same_database

HERE=Path(__file__).resolve().parent
REQUEST=HERE/'two_wave_generation_request.json'
EXPECTED='954e19cd4201de94e6b09d237f6a9cb77bb045ef33ec06759fee84b7c8f853f8'
PARENT=ROOT/'feedback_runs/20261102T060406746432Z_07113903'


def utc():return datetime.now(timezone.utc).isoformat()


def draw_once(budget,draw,prompt,database,directory,cfg,metadata,ready):
    sealed=read(PROJECT/draw['request']);payload=sealed['payload']
    if digest(payload)!=draw['payload_sha256'] or payload['seed']!=cfg.seed:
        raise PermissionError('Exact approved request changed')
    checkpoint=directory.parent/f"database_before_{draw['batch_slot']:03d}.json"
    write(checkpoint,snapshot(database))
    if not same_database(read(checkpoint),read(PROJECT/draw['checkpoint'])):
        raise PermissionError('Actual upstream program/RNG state differs from sealed schedule')
    source_id=draw['batch_slot']
    row={'candidate_id':source_id,'wave':1,'origin':'ollama','model':cfg.model,
        'digest':cfg.expected_digest,'quantization':cfg.expected_quantization,
        'sampling_seed':cfg.seed,'island_id':int(prompt.island_id),
        'version_generated':prompt.version_generated,'expected_name':expected_name(prompt),
        'prompt_sha256':digest(payload['messages']),'database_checkpoint_sha256':file_hash(checkpoint),
        'sealed_planned_checkpoint_sha256':draw['checkpoint_sha256'],
        'observed_fitness':None,'executed':False,'source_sha256':None,
        'api_attempts':0,'status':'request_failed','http_status':None}
    slot,reservation=budget.reserve(1,source_id,payload)
    row['allocation_call_slot']=reservation['call_slot']
    write(directory/'request.json',{'payload':payload,'reservation':reservation,
        'generation_request_sha256':budget.hash,'generation_settings':asdict(cfg),
        'database_prompt':{'code':prompt.code,'island_id':int(prompt.island_id),
                           'version_generated':prompt.version_generated},
        'database_checkpoint_sha256':file_hash(checkpoint),
        'sealed_request':draw,'model_metadata':metadata,
        'service_readiness_sha256':file_hash(directory/'service_preload/readiness.json'),
        'runner_sha256':file_hash(Path(__file__)),
        'generation_policy':'obp-objective-alternatives-distinct-seeds-v3',
        'generation_payload_sha256':digest(payload),'candidate_execution_authorized':False})
    started=perf_counter();hard_stop=False
    try:
        if ready['status']!='PASS' or ready['resident_model']['context_length']!=32768:
            raise PermissionError('Fresh pinned GPU/context readiness required')
        req=request.Request(cfg.base_url+'/chat/completions',
            data=json.dumps(payload,ensure_ascii=False,allow_nan=False).encode(),
            headers={'Content-Type':'application/json'})
        opener=request.build_opener(request.ProxyHandler({}),NoRedirect())
        write(slot/'transport_attempt_started.json',{'candidate_id':source_id,'wave':1,
            'timestamp':stamp(),'payload_sha256':digest(payload),'sampling_seed':cfg.seed})
        row['api_attempts']=1
        try:
            with opener.open(req,timeout=cfg.request_timeout_seconds) as response:
                raw=response.read(MAX_RESPONSE_BYTES+1);row['http_status']=response.status
        except error.HTTPError as exc:
            raw=exc.read(MAX_RESPONSE_BYTES+1);row['http_status']=exc.code
            (directory/'raw_http_response.bin').write_bytes(raw)
            row.update(raw_response_sha256=hashlib.sha256(raw).hexdigest(),
                delivery_status='server_error_response_received',failure_type=type(exc).__name__,
                failure_reason=str(exc))
            return row,False
        (directory/'raw_http_response.bin').write_bytes(raw)
        row['raw_response_sha256']=hashlib.sha256(raw).hexdigest()
        row['delivery_status']='response_received'
        if len(raw)>MAX_RESPONSE_BYTES:
            raise ValueError('Response exceeds bounded 1 MiB retention policy')
        value=json.loads(raw);write(directory/'response.json',value)
        # Preserve returned source/usage even when the protocol is subsequently rejected.
        if isinstance(value,dict):
            row.update(response_id=value.get('id'),response_model=value.get('model'),usage=value.get('usage'))
            choices=value.get('choices')
            if isinstance(choices,list) and len(choices)==1 and isinstance(choices[0],dict):
                choice=choices[0];message=choice.get('message')
                row['finish_reason']=choice.get('finish_reason')
                if isinstance(message,dict) and isinstance(message.get('content'),str):
                    source=message['content'];(directory/'source.py.txt').write_bytes(source.encode())
                    row.update(source=source,source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                        source_file=str((directory/'source.py.txt').relative_to(directory.parent)))
        if not isinstance(value,dict) or value.get('model')!=cfg.model:
            raise ValueError('Response model identity differs')
        choices=value.get('choices')
        if not isinstance(choices,list) or len(choices)!=1:
            raise ValueError('Exactly one response per actual request is required')
        message=choices[0].get('message')
        if not isinstance(message,dict) or message.get('tool_calls') or message.get('function_call'):
            raise ValueError('Unsupported response/tool-call structure')
        if 'source' not in row:raise ValueError('Missing candidate text')
        try:
            parsed,static=validate(row['source'],row['expected_name'],row['finish_reason'])
            row.update(status='static_valid_pending_execution_approval',static=static,
                parsed_body_sha256=hashlib.sha256(parsed.body.encode()).hexdigest())
        except (ValueError,SyntaxError) as exc:
            row.update(status='static_rejected',static={'status':'FAIL'},failure_reason=str(exc))
    except (OSError,ValueError,KeyError,TypeError,IndexError,AttributeError,PermissionError) as exc:
        row.update(status='request_failed' if row.get('http_status') is None else 'protocol_rejected',
            failure_type=type(exc).__name__,failure_reason=str(exc))
        row.setdefault('delivery_status','uncertain_transport_or_dispatch')
        hard_stop=True
    finally:
        row['generation_seconds']=perf_counter()-started
        row['session_hard_stop']=hard_stop
        write(directory/'candidate.json',row);write(slot/'outcome.json',row)
        append(directory.parent/'artifact_ledger.jsonl',row)
    return row,hard_stop


def main(args):
    if file_hash(REQUEST)!=EXPECTED:raise PermissionError('Sealed two-wave request differs')
    plan=read(REQUEST);check_controls(plan)
    budget=TwoWaveBudget(REQUEST,args.approval)
    if any(budget.root.iterdir()):raise PermissionError('Existing generation state: inspect; no silent restart/reset')
    durable_reservation(budget.root/'wave1_session_reserved.json',{'started_at_utc':utc(),
        'request_sha256':budget.hash,'wave':1,'wave2_execution_not_requested':True})
    output=HERE/'sessions'/stamp()/'wave1';output.mkdir(parents=True)
    log=EventLog(output/'events.jsonl');rows=[];failure=None;session_start=perf_counter()
    shutil.copyfile(PARENT/'database_after_registration.json',output/'original_comparison_checkpoint.json')
    prompt,proof,state=load_verified_feedback(PARENT,ROOT/'slot12_recovery/evaluation_request.json',
        ROOT/'approvals/slot12_evaluation_v2.json')
    write(output/'actual_parent_feedback.json',proof)
    database=restore(state)

    def save(status):
        write(output/'pool.json',{'schema':'qwen-two-wave-wave-pool-v1','wave':1,
            'generation_request_sha256':budget.hash,'session_status':status,
            'api_attempts':sum(r['api_attempts'] for r in rows),'candidates':rows,
            'model':plan['model'],'model_digest':plan['model_digest'],'quantization':'Q4_K_M',
            'wave2_dispatched':False,'generated_sources_executed':0,'registration_count':0,
            'original_comparison_checkpoint_sha256':file_hash(output/'original_comparison_checkpoint.json'),
            'session_wall_seconds':perf_counter()-session_start,'failure':failure,
            'timing_scope':'Generation/session and service readiness only; no learning, replay or audit cost incurred.'})
    save('generating')
    for index,draw in enumerate(plan['wave1']['draws'],1):
        directory=output/f'candidate_{index:03d}';directory.mkdir()
        try:
            for key in ('request','checkpoint'):
                if file_hash(PROJECT/draw[key])!=draw[key+'_sha256']:
                    raise PermissionError('Approved planned evidence changed')
            if index>1:prompt=database.get_prompt()
            sealed=read(PROJECT/draw['request'])
            if {'code':prompt.code,'island_id':int(prompt.island_id),
                'version_generated':prompt.version_generated}!=sealed['database_prompt']:
                raise PermissionError('Actual upstream prompt differs from reviewed schedule')
            context={**proof,'selected_next_island_id':int(prompt.island_id)}
            if messages_for(prompt,context)!=sealed['payload']['messages']:
                raise PermissionError('Actual feedback wrapper differs from sealed messages')
            cfg=replace(fixed_config(),seed=draw['seed'])
            if {k:v for k,v in asdict(cfg).items() if k!='seed'}!=plan['generation_settings']:
                raise PermissionError('Frozen non-seed controls changed')
            metadata=OllamaAdapter(cfg,log).model_metadata()
            ready=preload(directory/'service_preload',expected_context=32768)
            if ready['api_version']['version']!=metadata['ollama_version']:
                raise PermissionError('Service identity changed during readiness')
            row,hard_stop=draw_once(budget,draw,prompt,database,directory,cfg,metadata,ready)
            rows.append(row);save('generating')
            print(f"Wave 1 {index}/8 seed {draw['seed']}: {row['status']} ({row['generation_seconds']:.3f}s)",flush=True)
            if hard_stop:
                failure={'stage':'generation','candidate_id':index,'reason':row.get('failure_reason')}
                break
        except Exception as exc:
            failure={'stage':'pre_dispatch_or_controller','candidate_id':index,
                     'error_type':type(exc).__name__,'reason':str(exc)}
            write(output/'stopped.json',failure);break
    write(output/'database_after_wave1_generation.json',snapshot(database))
    save('wave_complete' if len(rows)==8 and not failure else 'stopped_without_retry')
    print(str(output/'pool.json'),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--approval',type=Path,required=True)
    main(parser.parse_args())
