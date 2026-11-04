"""Approval-gated paired experiment. No candidate execution on the host.

--verify-only checks local seals without Docker, slots or authorization receipts.
Execution requires a NEW operator receipt after exact-manifest user approval.
"""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path
import random
import statistics
import sys
from time import perf_counter
from ..protocol import *
from ..authority import Authority, verify_manifest, durable

CONTROLLER_VERSION='fused-controller-v1.2'
CONTROL_HERE=Path(__file__).resolve().parent


class Log:
    def __init__(self,directory):
        self.directory=directory;directory.mkdir(parents=True,exist_ok=False)
    def emit(self,event,**fields):
        # No broad source_hashes()/legacy-data read from historical RunLog.manifest.
        with (self.directory/'events.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps({'event':event,**fields},allow_nan=False)+'\n')


def same_db(a,b):
    return digest({k:v for k,v in a.items() if k!='reset_age_seconds'})==digest({k:v for k,v in b.items() if k!='reset_age_seconds'})


def reconstruct(replay,history,initial):
    """Only AST/database operations; preserve caller RNG around verification."""
    import numpy as np
    from database_state import restore,snapshot
    from implementation import evaluator,code_manipulation as cm
    from trusted_cases import SPECIFICATION
    ns=np.random.get_state();ps=random.getstate()
    try:
        database=restore(initial)
        for saved,row in history:
            p=database.get_prompt()
            if saved!={'code':p.code,'island_id':int(p.island_id),'version_generated':p.version_generated}:
                raise RuntimeError('Prompt/RNG transition inconsistent')
            if row['registered']:
                function,_=evaluator._sample_to_program(row['parsed_body'],p.version_generated,
                    cm.text_to_program(SPECIFICATION),'priority')
                database.register_program(function,p.island_id,row['scores_per_group'])
        if not same_db(snapshot(database),snapshot(replay.database)):
            raise RuntimeError('Cross-arm contamination or database history mismatch')
    finally:np.random.set_state(ns);random.setstate(ps)


def barrier(authority,records,runner):
    from container_runner import cli
    if authority.pending is not None:raise RuntimeError('Pending unknown dispatch')
    for record in records:confirmed_terminal(record)
    names={r['container_name'] for r in records}
    current=set(cli(runner.docker,['ps','--all','--format','{{.Names}}']).stdout.splitlines())
    if names&current:raise RuntimeError('Worker cleanup incomplete')
    for slotid in authority.completed:
        if not (authority.root/slotid/'dispatch.json').is_file() or not (authority.root/slotid/'result.json').is_file():
            raise RuntimeError('Missing terminal authority receipt')


def trusted(authority,development,boundary,output):
    from candidates import _mint
    from static_policy import validate
    from replay import accepted_full
    records=[]
    for name,runner in [('trusted_nonmatch',development),('trusted_match',development),('trusted_boundary',boundary)]:
        slot=next(s for s in authority.slots.values() if s['source_id']==name)
        authority.select(slot['configuration'],name)
        candidate=_mint((PROJECT/slot['source_file']).read_text(),name)
        parsed,_=validate(candidate.text,'priority')
        reps=slot.get('trusted_representatives',[])
        record=runner.run_task(candidate,parsed,slot['task']['action'],representatives=reps)
        if record['status']!='ok':raise RuntimeError('Trusted runtime check failed')
        if name=='trusted_nonmatch':
            if not accepted_full(record,development.data['development']):raise RuntimeError('Incomplete trusted full check')
            if record['result']['scores_per_group']!={'OR3':-212.41666666666666,'Weibull 5k':-2072.6666666666665}:
                raise RuntimeError('Unchanged Best Fit development fitness differs')
        elif name=='trusted_match':
            if record['result']['decisions']!=reps[0]['decisions'] or record['result']['full_evaluation_performed']:
                raise RuntimeError('Trusted skip path differs')
        else:
            states=read(BOUNDARY)['fingerprint']
            expected=[s['valid_bin_indices'][min(range(len(s['bins'])),key=lambda i:s['bins'][i])] for s in states]
            if record['result']['decisions']!=expected:raise RuntimeError('Boundary validity/argmax differs')
        records.append(record);write_new(output/(name+'.json'),record)
    barrier(authority,records,development)
    return records


def arm(authority,runner,pool,block,mode,output):
    from ..replay_v1 import FusedReplayV1
    from generation3 import load_candidate
    from database_state import restore,snapshot
    from replay import accepted_full
    directory=output/f'block{block}'/mode;log=Log(directory)
    replay=FusedReplayV1(runner,'exact' if mode=='exact' else 'behavioral',log)
    initial=read(CHECKPOINT);replay.database=restore(initial)
    replay.best=max(replay.database._best_score_per_island);replay.final=replay.best
    history=[];then=perf_counter()
    for source in pool['candidates']:
        start=perf_counter();cid=source['candidate_id'];prompt=replay.database.get_prompt()
        saved={'code':prompt.code,'island_id':int(prompt.island_id),'version_generated':prompt.version_generated}
        write_new(directory/f'prompt_{cid:03d}.json',saved)
        write_new(directory/f'database_before_{cid:03d}.json',snapshot(replay.database))
        if any(s['source_id']==cid and s['configuration']==f'block{block}/{mode}' for s in authority.slots.values()):
            authority.select(f'block{block}/{mode}',cid)
        replay.counts['candidates']+=1
        row=replay.process(load_candidate(POOL,source),prompt,cid)
        if row['status']=='blocked_generated_execution':raise RuntimeError('Unexpected authority rejection')
        row['complete_processing_seconds']=perf_counter()-start
        write_new(directory/f'candidate_{cid:03d}.json',row)
        write_new(directory/f'database_after_{cid:03d}.json',snapshot(replay.database))
        history.append((saved,row))
    elapsed=perf_counter()-then
    # Persist the observed loop interval BEFORE any history/cleanup barrier.
    # A failed diagnostic is never a successful-arm or paired timing sample.
    write_new(directory/'loop_elapsed_diagnostic.json', {'status':'candidate_loop_complete_unverified',
        'block':block,'configuration':mode,'candidate_loop_wall_seconds':elapsed,
        'eligible_for_paired_comparison':False})
    try:
        reconstruct(replay,history,initial)
        barrier(authority,replay.executions,runner)
        for row in replay.records:
            if row['status'].startswith('skipped_') and row['registered']:raise RuntimeError('Skipped candidate registered')
    except BaseException as exc:
        write_new(directory/'arm_verification_failed.json', {'status':'verification_failed',
            'block':block,'configuration':mode,'candidate_loop_wall_seconds':elapsed,
            'eligible_for_paired_comparison':False,'error_type':type(exc).__name__,'error':str(exc)})
        raise
    trace=[{k:r.get(k) for k in ('candidate_id','status','score','scores_per_group','registered','matched_representative_id','island_id','version_generated','fingerprint')} for r in replay.records]
    tasks=replay.executions;counts=Counter(r['status'] for r in replay.records)
    completed=[r for r in tasks if accepted_full(r,replay.groups)]
    accepted=[r for r in replay.records if r['registered']];best=max(accepted,key=lambda r:r['score']) if accepted else None
    summary={'controller_version':'fused-controller-v1.2','verification_status':'PASS',
        'eligible_for_paired_comparison':True,'block':block,'configuration':mode,'candidates':16,'statuses':dict(counts),
        'containers':len(tasks),'full_attempted':sum(r.get('full_evaluation_started',False) for r in tasks),
        'full_completed':len(completed),'full_rejected':sum(r.get('full_evaluation_started',False) and not accepted_full(r,replay.groups) for r in tasks),
        'full_avoided_by_matches':counts['skipped_exact']+counts['skipped_behavioral'],
        'exact_matches':counts['skipped_exact'],'behavioral_matches':counts['skipped_behavioral'],
        'registrations':len(accepted),'representatives':len(replay.reps.all),
        'fingerprint_invocations':sum(r['action']=='fused' for r in tasks),
        'fingerprint_phase_seconds':sum(r.get('fingerprint_phase_seconds',0) for r in tasks),
        'fingerprint_pure_seconds':sum(r.get('result',{}).get('fingerprint_seconds',0) for r in tasks),
        'namespace_seconds':sum(r.get('result',{}).get('fingerprint_namespace_seconds',0)+r.get('result',{}).get('full_namespace_seconds',0) for r in tasks),
        'full_pure_seconds':sum(r['result']['pure_evaluate_seconds'] for r in completed),
        'lifecycle_seconds':sum(r['total_seconds'] for r in tasks),
        'create_seconds':sum(r.get('create_seconds',0) for r in tasks),
        'ready_seconds':sum(r.get('worker_ready_seconds',0) for r in tasks),
        'cleanup_seconds':sum(r.get('cleanup_seconds',0) for r in tasks),
        'host_filter_seconds':sum(r['filter_seconds'] for r in replay.records),
        'registration_and_acceptance_seconds':sum(r.get('evaluation',{}).get('registration_and_acceptance_seconds',0) for r in replay.records),
        'host_task_outside_lifecycle_seconds':sum(r['host_task_seconds']-r['total_seconds'] for r in tasks),
        'serialization_accounting':'Included in host-task/whole-candidate time; not separately identified from static checking/protocol/receipt costs',
        'failed_tasks_without_complete_pure_timings':sum(r['status']!='ok' for r in tasks),
        'parse_seconds':sum(r['parse_seconds'] for r in replay.records),
        'normal_wall_seconds':elapsed,'best_fitness':replay.best,'final_accepted_fitness':replay.final,
        'best_mean_bins':{k:-v for k,v in best['scores_per_group'].items()} if best else None,
        'logical_trace_sha256':digest(trace),'initial_checkpoint_sha256':file_hash(CHECKPOINT),
        'initial_cache_size':0,'heldout_used':False,'llm_calls':0}
    write_new(directory/'database_final.json',snapshot(replay.database));write_new(directory/'trajectory.json',trace)
    write_new(directory/'representatives.json',replay.reps.all);write_new(directory/'summary.json',summary)
    return summary,tasks,replay.records


def execute(args):
    campaign_start=perf_counter()
    if file_hash(args.manifest)!=args.expected_sha256:raise PermissionError('Reviewed manifest SHA differs')
    manifest=verify_manifest(args.manifest)
    if args.verify_only:
        print(json.dumps({'status':'seals verified only','slots':45,'authorized':False}));return
    if args.approval is None:raise PermissionError('Separate exact-manifest explicit authorization required')
    # Approval and durable campaign reservation precede any Docker operation.
    authority=Authority(args.manifest,args.approval)
    from ..runner import Runner
    from static_policy import validate
    from generation3 import load_candidate
    images=read(HERE/'image_receipt.json')['images']
    output=authority.root/'measurements';output.mkdir(exist_ok=False)
    all_records=[]
    try:
        development=Runner(images['development']['image'],authority)
        boundary=Runner(images['boundary']['image'],authority,'boundary')
        validation_start=perf_counter()
        all_records+=trusted(authority,development,boundary,output)
        validation_wall=perf_counter()-validation_start
        pool=read(POOL);summaries=[];outcomes={}
        for block,order in enumerate(manifest['mode_orders'],1):
            for mode in order:
                summary,tasks,rows=arm(authority,development,pool,block,mode,output)
                if block==2 and summary['logical_trace_sha256']!=next(s for s in summaries if s['configuration']==mode)['logical_trace_sha256']:
                    raise RuntimeError('Repeated logical trajectory/RNG mismatch')
                summaries.append(summary);all_records+=tasks;outcomes[(block,mode)]=rows
            barrier(authority,all_records,development)
            write_new(output/f'block{block}_barrier.json',{'status':'PASS','terminal_tasks':len(all_records),'database_histories_reconstructed':True})
        vectors={};diagnostic_start=perf_counter()
        for cid in (8,10):
            source=next(s for s in pool['candidates'] if s['candidate_id']==cid)
            candidate=load_candidate(POOL,source);parsed,_=validate(candidate.text,source['expected_name'],source['finish_reason'])
            authority.select('boundary/model',cid);record=boundary.run_task(candidate,parsed,'fingerprint')
            vectors[cid]=record['result']['decisions'];all_records.append(record)
            write_new(output/f'boundary_{cid}.json',record)
        diagnostic_wall=perf_counter()-diagnostic_start
        with (output/'comparison.csv').open('x',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=list(summaries[0]));w.writeheader();w.writerows(summaries)
        stats={}
        for mode in ('exact','fused16'):
            values=[s['normal_wall_seconds'] for s in summaries if s['configuration']==mode]
            stats[mode]={'mean':statistics.mean(values),'sample_sd':statistics.stdev(values),'range':[min(values),max(values)]}
        # Post-hoc quality comparison only; never imported into a search cache.
        disagreements=[]
        for block in (1,2):
            all_exact={r['candidate_id']:r for r in outcomes[(block,'exact')]}
            exact={r['candidate_id']:r for r in all_exact.values() if r['registered']}
            for row in outcomes[(block,'fused16')]:
                if row['registered'] and row['candidate_id'] in exact and row['scores_per_group']!=exact[row['candidate_id']]['scores_per_group']:
                    raise RuntimeError('Fused/Exact common full-fitness disagreement')
                if row['status']=='skipped_behavioral':
                    cid=row['candidate_id'];reference=all_exact[cid]
                    if reference['status']=='skipped_exact':reference=all_exact[reference['matched_representative_id']]
                    if not reference['registered']:raise RuntimeError('Behavioral match lacks complete Exact-side quality reference')
                    real=reference
                    disagreements.append({'block':block,'candidate_id':row['candidate_id'],
                        'representative':row['matched_representative_id'],
                        'exact_side_measured_source':real['candidate_id'],
                        'exact_source_representative_used':real['candidate_id']!=cid,
                        'exact_score':real['score'],'representative_score':row['representative_score'],
                        'different_score':real['score']!=row['representative_score'],
                        'missed_best':real['score']>row['best_before']})
        barrier(authority,all_records,development)
        if len(all_records)>45:raise RuntimeError('Task ceiling exceeded')
        write_new(output/'results.json',{'status':'completed','timing':stats,
            'boundary_decisions':vectors,'boundary_disagreements':sum(a!=b for a,b in zip(vectors[8],vectors[10])),
            'posthoc_quality_checks_not_independent_audits':disagreements,
            'trusted_and_boundary_costs_separate':True,'trusted_validation_wall_seconds':validation_wall,
            'boundary_diagnostic_wall_seconds':diagnostic_wall,'campaign_wall_seconds':perf_counter()-campaign_start,
            'research_tasks':len(all_records)-3,
            'main_calls':0,'generation_calls':0,'new_speedup_claim':'Requires paired measured times, not accounting estimate'})
        durable(authority.root/'campaign_closed.json',{'status':'completed','used_slots':len(authority.completed),'unused_nontransferable':45-len(authority.completed)})
        print(str(output))
    except BaseException as exc:
        durable(authority.root/'stopped.json',{'status':'stopped_no_resume','error':str(exc),'used_slots':len(authority.completed)})
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',type=Path,default=CONTROL_HERE/'execution_request.json')
    parser.add_argument('--expected-sha256',required=True);parser.add_argument('--approval',type=Path)
    parser.add_argument('--verify-only',action='store_true');execute(parser.parse_args())
