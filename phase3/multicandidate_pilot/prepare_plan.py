"""Offline receipt reconciliation and eight authentic prospective DB prompts.

No API transport, Docker task, candidate function call, or approval creation.
"""
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import random
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap3
from bootstrap3 import ROOT,PROJECT
from common import read,write,file_hash,digest
from approval import control_sources,check_controls
from verified_feedback_v3 import load_verified_feedback
from database_state import restore,snapshot
from generation3 import fixed_config
from generation_policy_v3 import messages_for,policy,POLICY_PATH

DIRECTORY=Path(__file__).resolve().parent
PARENT=ROOT/'feedback_runs/20261102T060406746432Z_07113903'


def reconcile():
    records=[]
    phase1d=[PROJECT/'phase1b/phase1d/runs/20261031T065826343292Z_cf9ae10c/events.jsonl',
        PROJECT/'phase1b/phase1d/diagnostics/runs/20261031T073119815062Z_7d0f3c58/events.jsonl']
    for p in phase1d:
        events=[__import__('json').loads(s) for s in p.read_text(encoding='utf-8').splitlines()]
        starts=[e for e in events if e.get('event')=='api_attempt_started']
        responses=[e for e in events if e.get('event')=='generation_response']
        assert len(starts)==len(responses)==1
        r=responses[0]
        records.append({'known_logged_ordinal':len(records)+1,'phase':'1D','allocation_slot':None,
            'event_utc':starts[0]['utc'],'outcome':'response_received',
            'finish_reason':r['finish_reason'],'usage':r.get('usage'),
            'response_id':r['response_id'],'generation_seconds':r['generation_seconds'],
            'evidence':p.relative_to(PROJECT).as_posix(),'evidence_sha256':file_hash(p)})
    allocation=ROOT/'dispatch_state'/file_hash(ROOT/'generation_request.json')
    for n in range(1,13):
        folder=allocation/f'call_{n:03d}'
        attempt=read(folder/'transport_attempt_started.json');row=read(folder/'outcome.json')
        records.append({'known_logged_ordinal':len(records)+1,'phase':'3','allocation_slot':n,
            'event_utc_or_stamp':attempt['timestamp'],'outcome':row['status'],
            'finish_reason':row.get('finish_reason'),'http_status':row.get('http_status'),
            'usage':row.get('usage'),'response_id':row.get('response_id'),
            'source_sha256':row.get('source_sha256'),'generation_seconds':row['generation_seconds'],
            'evidence':(folder/'outcome.json').relative_to(PROJECT).as_posix(),
            'evidence_sha256':file_hash(folder/'outcome.json')})
    assert len(records)==14 and len(list(allocation.glob('call_*')))==12
    totals={key:sum((r.get('usage') or {}).get(key,0) for r in records)
            for key in ('prompt_tokens','completion_tokens','total_tokens')}
    value={'schema':'receipt_reconciled_pilot_ledger-v1','known_logged_calls':14,
        'logged_phase1d':2,'old_phase3_allocation_cap':12,'old_phase3_attempts':12,
        'old_allocation_unused_slots':0,'new_generation_calls_this_plan':0,
        'known_usage_all_logged_calls':totals,'calls_with_unknown_usage':2,
        'historical_connectivity_exact_count':None,'historical_connectivity_known_minimum':2,
        'later_unattributed_api_chat':read(ROOT/'ollama_reliability/unattributed_server_request.json'),
        'service_preloads_not_generation':True,'lifetime_exact_remaining_pilot_budget':None,
        'nominal_pilot_plan':30,'main_calls':0,'main_cap':540,
        'proposed_additional_calls_not_authorized':8,'known_logged_if_all_eight_attempted':22,
        'records':records,'note':'Original historical static statuses are preserved. Later v2 acceptance/fitness is a separate evaluation, not a new generation or retroactive edit.'}
    write(DIRECTORY/'call_reconciliation.json',value)
    with (DIRECTORY/'call_reconciliation.csv').open('w',newline='',encoding='utf-8') as stream:
        columns=['known_logged_ordinal','phase','allocation_slot','outcome','finish_reason','http_status','response_id','generation_seconds','evidence','evidence_sha256']
        writer=csv.DictWriter(stream,fieldnames=columns,extrasaction='ignore');writer.writeheader();writer.writerows(records)
    return value


def main():
    DIRECTORY.mkdir(exist_ok=True)
    if (DIRECTORY/'generation_request.json').exists():
        raise PermissionError('Existing sealed proposal: inspect instead of overwriting')
    reconciliation=reconcile()
    manifest=ROOT/'slot12_recovery/evaluation_request.json'
    prompt,proof,state=load_verified_feedback(PARENT,manifest,ROOT/'approvals/slot12_evaluation_v2.json')
    assert proof['score']==-2047.125 and proof['evaluated_island_id']==0
    database=restore(state);counts=[i._num_programs for i in database._islands]
    planned=DIRECTORY/'planned_prompts';planned.mkdir(exist_ok=False)
    rows=[];cfg=fixed_config();v3=policy()
    for i in range(1,9):
        if i>1:prompt=database.get_prompt()
        checkpoint=planned/f'database_before_{i:03d}.json'
        if i==1:shutil.copyfile(PARENT/'database_after_registration.json',checkpoint)
        else:write(checkpoint,snapshot(database))
        # Explicit new-manifest seed extension; never widen the old 11/12 guard.
        seed=v3['seed_base']+v3['seed_stream_stride']*v3['pilot_stream_id']+12+i
        feedback={**proof,'selected_next_island_id':int(prompt.island_id)}
        payload={'model':cfg.model,'messages':messages_for(prompt,feedback),'n':1,'stream':False,
            'temperature':cfg.temperature,'top_p':cfg.top_p,'max_tokens':cfg.max_tokens,
            'seed':seed,'reasoning_effort':cfg.reasoning_effort}
        path=planned/f'request_{i:03d}.json'
        value={'proposed_batch_slot':i,'proposed_known_logged_ordinal':14+i,'sampling_seed':seed,
            'seed_formula_ordinal':12+i,'database_prompt':{'code':prompt.code,
                'island_id':int(prompt.island_id),'version_generated':prompt.version_generated},
            'payload':payload,'payload_sha256':digest(payload),
            'messages_sha256':digest(payload['messages']),'checkpoint_sha256':file_hash(checkpoint),
            'actual_feedback':feedback,'candidate_generated':False,
            'new_feedback_between_batch_requests':False,
            'sampling_note':'Only authentic prompt selection/RNG advances in a copy of the real DB; program registrations and fitness are unchanged.'}
        write(path,value)
        rows.append({'batch_slot':i,'known_logged_ordinal_if_attempted':14+i,'seed':seed,
            'request':path.relative_to(PROJECT).as_posix(),'request_sha256':file_hash(path),
            'checkpoint':checkpoint.relative_to(PROJECT).as_posix(),'checkpoint_sha256':file_hash(checkpoint),
            'island_id':int(prompt.island_id),'version_generated':prompt.version_generated,
            'payload_sha256':digest(payload),'messages_sha256':digest(payload['messages'])})
        assert [island._num_programs for island in database._islands]==counts
    order=['standard','exact','behavioral-16','behavioral-64','behavioral-128']
    random.Random(5494).shuffle(order)
    protocol={'type':'fixed_real_Qwen_pool_replay_not_live_multigeneration_search',
        'candidate_stream':'Every attempted new batch slot in original order; failures/rejections retained. No old nine-response stream padding or candidate substitution.',
        'starting_checkpoint_sha256':proof['database_sha256'],'starting_database_best':-2047.125,
        'initial_representative_cache':'empty per arm; no uncounted fingerprints or imported dedup caches',
        'generation_metadata_immutable':True,'replay_island_metadata':'Log separately; real per-arm prompt/registration transitions, never rewrite generation history',
        'comparison_modes':['standard','exact','behavioral-16','behavioral-64','behavioral-128'],
        'behavioral_includes_same_exact_prefilter':True,'execution_architecture':'separate disposable containers; model fused remains blocked',
        'mode_order_seed':5494,'mode_order':order,'runs_per_mode':1,
        'all_behavioral_skips_audited':True,'audit_states':256,
        'audit_policy':'Reserved audit decisions versus matched representative plus full development score, after original trajectory, no feedback of audit fitness into search.',
        'max_normal_dispatches_if_8_static_valid':64,'max_audit_dispatches_if_all_8_skipped_in_each_behavioral_arm':72,
        'conservative_total_dispatch_ceiling_for_later_source_approval':136,
        'max_normal_full_evaluations':40,'max_audit_full_evaluations':24,
        'normal_and_audit_costs_separate':True,'fingerprint_sizes':[16,64,128],
        'generation_cost':'Actual <=8 calls once; common generation wall G reported separately and as G+T_arm; never charge five generated batches.',
        'metrics':['attempted_calls','returned_sources','static_and_runtime_rejections','full_attempted_completed',
            'exact_matches','behavior_matches','skipped_full_evaluations','registrations','representatives',
            'fingerprint_pure_seconds','fingerprint_container_lifecycle_seconds','startup_seconds',
            'full_evaluation_pure_seconds','normal_replay_wall_seconds','generation_wall_seconds',
            'audit_calls_and_wall_seconds','best_new_candidate_fitness','best_database_fitness','last_accepted_fitness',
            'per_family_bins','audit_outside_state_disagreement','matched_but_score_different',
            'missed_best_at_position','wall_time_and_full_count_difference_vs_exact'],
        'inference_limit':'Single small pool, one order, no statistical speedup/multiseed claim. Few/no duplicates is a legitimate outcome.',
        'main_campaign_enabled':False}
    write(DIRECTORY/'replay_protocol.json',protocol)
    extras=[Path(__file__),ROOT/'acceptance_policy.json',ROOT/'slot12_recovery/build_receipt.json',
        ROOT/'slot12_recovery/validation.json',PARENT/'database_after_registration.json',
        PARENT/'candidate_result.json',PARENT/'next_prompt.json',DIRECTORY/'replay_protocol.json',
        *planned.glob('*.json')]
    controls={**control_sources(),**{p.relative_to(PROJECT).as_posix():file_hash(p) for p in extras}}
    request={'schema':'prospective_real_qwen_batch8-v1','approved':False,
        'kind':'finite_generation_batch_only','max_new_generation_requests':8,
        'per_slot_max_attempts':1,'fresh_allocation_not_old_slot_reuse':True,
        'old_allocation_sha256':file_hash(ROOT/'generation_request.json'),
        'old_allocation_exhausted':True,'generation_settings':{k:v for k,v in asdict(cfg).items() if k!='seed'},
        'sampling_seeds':'Only the exact per-draw payload seeds apply; the historical base-config seed is not a batch setting.',
        'generation_policy_id':v3['policy_id'],'generation_policy_sha256':file_hash(POLICY_PATH),
        'active_static_policy':'phase3-numerical-ast-v2','effective_context_length':32768,
        'seed_extension':'New batch slots 1..8 use pilot-stream formula ordinals 13..20 (549199013..549199020), requiring this fresh finite approval; old seed guards/manifests unchanged.',
        'draws':rows,'parent_feedback_directory':PARENT.relative_to(PROJECT).as_posix(),
        'parent_actual_feedback':proof,'starting_island_counts':counts,
        'first_prompt':'Reuse actual saved next prompt, island 8/version 1; subsequent prompts are genuine upstream draws from the unmodified program state.',
        'unique_planned_message_hashes':len({r['messages_sha256'] for r in rows}),
        'unique_planned_database_code_hashes':len({digest(read(PROJECT/r['request'])['database_prompt']['code']) for r in rows}),
        'preload':'Fresh empty-message readiness before each draw; 120s keep_alive, pinned digest, RTX 5090, context 32768. No candidate prompt used as a health test.',
        'failure_policy':'Retain all complete/invalid/truncated/duplicate responses; continue scheduled distinct seeds after static rejection. HTTP/protocol/transport or readiness failure stops session without retry, slot substitution or silent later resumption.',
        'candidate_execution_authorized':False,'maximum_candidate_evaluations':0,'main_calls':0,
        'heldout_access':False,'push_or_publication_authorized':False,
        'known_logged_pilot_calls_before':14,'known_logged_if_all_8_attempted':22,
        'nominal_pilot_plan':30,'historical_total_exact':None,
        'control_sha256':controls,
        'implementation_note':'This is a sealed offline request/prompt schedule, not an authorization or a call to the exhausted two-slot adapter. The newly approved session must use a separate eight-slot one-use dispatcher over the existing single-attempt transport; wire that finite scope and generate directly in the approved batch task, not in another environment-preparation phase.'}
    write(DIRECTORY/'generation_request.json',request)
    write(DIRECTORY/'generation_approval.template.json',{'approved':False,'kind':request['kind'],
        'manifest_sha256':file_hash(DIRECTORY/'generation_request.json'),
        'user_authorization_verbatim':None,'recorded_at_utc':None,
        'generation_only_acknowledged':False,'note':'Fresh eight-call permission; zero source executions. No approval is inferred from nominal 30-call budget.'})
    write(DIRECTORY/'offline_checks.json',{'status':'PASS_OFFLINE_PLAN_ONLY','generation_calls':0,
        'candidate_executions':0,'actual_parent_proof_verified':True,'unchanged_island_program_counts':counts,
        'planned_prompt_draws':8,'seed_schedule':[r['seed'] for r in rows],
        'unique_prompt_hashes':request['unique_planned_message_hashes'],
        'request_sha256':file_hash(DIRECTORY/'generation_request.json'),
        'existing_milestone_complete':True,'new_batch_approved':False,
        'first_checkpoint_identical_to_actual':rows[0]['checkpoint_sha256']==proof['database_sha256']})
    print(__import__('json').dumps({'known_logged_calls':14,'proposed_calls':8,
        'seed_schedule':[r['seed'] for r in rows],
        'actual_planned_islands':[r['island_id'] for r in rows],
        'actual_planned_versions':[r['version_generated'] for r in rows],
        'unique_prompt_hashes':request['unique_planned_message_hashes'],
        'request_sha256':file_hash(DIRECTORY/'generation_request.json'),
        'generation_calls_made':0},indent=2))


if __name__=='__main__':main()
