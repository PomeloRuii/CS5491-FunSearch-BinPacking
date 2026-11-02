"""Seal an offline two-wave proposal; never generates, evaluates or grants consent."""
from copy import deepcopy
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap3
from bootstrap3 import ROOT,PROJECT
from common import read,write,file_hash,digest
from approval import control_sources,check_controls
from filters import exact_source
from catalogue import reviewed_candidate
from generation_policy_v3 import POLICY_PATH

HERE=Path(__file__).resolve().parent


def ref(path):
    return {'path':Path(path).relative_to(PROJECT).as_posix(),'sha256':file_hash(path)}


def main():
    target=HERE/'two_wave_generation_request.json'
    if target.exists():raise PermissionError('Existing sealed proposal must not be silently overwritten')
    old=read(HERE/'generation_request.json');check_controls(old)
    if file_hash(HERE/'generation_request.json')!='48492ee3bc6616d361a4c51420c82c7c362d047e56259b223abb516e18f61c40':
        raise PermissionError('Eight-call proposal changed')
    reconciliation=read(HERE/'call_reconciliation.json')
    assert reconciliation['known_logged_calls']==14
    parent=ROOT/'feedback_runs/20261102T060406746432Z_07113903'
    for name,sha in read(parent/'evidence_sha256.json')['sha256'].items():
        if file_hash(parent/name)!=sha:raise PermissionError('Actual Slot-12 evidence changed')
    # exact-source keys use raw UTF-8 SHA-256, consistent with filter indexing.
    import hashlib
    known=[hashlib.sha256(exact_source(reviewed_candidate(f,'priority').text,'priority').encode()).hexdigest()
           for f in ('seed','first_fit','best_fit')]
    raw=read(ROOT/'feedback_generated/20261102T052500617671Z_74cc148e/candidate_001/candidate.json')
    known.append(hashlib.sha256(exact_source(raw['source'],raw['expected_name']).encode()).hexdigest())
    protocol=deepcopy(read(HERE/'replay_protocol.json'))
    first_order=protocol['mode_order'];protocol.update({
        'generation_design':'Two genuine waves separated by actual Wave-1 pilot evaluation/registration; no live evaluations within either generation wave',
        'max_candidate_attempt_rows':16,'stream_freeze':'Wave-1 slot order followed by Wave-2 slot order; include every duplicate, invalid output and failure; no replacements',
        'starting_checkpoint_sha256':old['parent_actual_feedback']['database_sha256'],
        'pilot_evolution_database':'Separate mutable copy of Wave-1 post-generation state; only actual intermediate full results register. Never overwrite frozen replay checkpoint.',
        'comparison_database':'Each arm/block restores original post-Slot-12 checkpoint; no Wave-1 evolution or comparison-arm score imports',
        'initial_representative_cache':'Empty for every arm/block; prior DB fitness is history, not a free fingerprint/exact cache',
        'timing_blocks':2,'runs_per_mode':2,'mode_orders':[first_order,list(reversed(first_order))],
        'timing_design':'Serial candidate workers; randomized first order seed 5494, reversed second order for balanced average positions. Same fixed stream/checkpoint each time. Report both observations, mean/spread and logical-trace equality; not independent search seeds.',
        'audit_policy':'Independently full-evaluate each behaviorally skipped candidate per N once; compute each needed source/representative reserved-256 vector once per N in separate workers. Check every skip against its original representative/best-at-position. Timing repeats reference these audit receipts only after trace equality; new skip identities must also be audited. Audit scores never register in replay.',
        'audit_decision_reuse':'Controller may reuse a verified reserved-audit vector for the same exact source/data/policy within N; no Python worker state sharing, cross-arm fitness cache or normal-trajectory use',
        'audit_parallelism_default':1,'audit_parallelism_ceiling':2,
        'audit_parallelism_gate':'Enable two only after focused trusted concurrent-job validation proves independent runners/authorities, correct finite reservations and termination/cleanup; otherwise serial. No audits during timing blocks.',
        'max_intermediate_full_evaluations':8,'max_normal_dispatches_two_blocks_if16_valid':256,
        'max_independent_audit_dispatches_if16_valid':96,'max_total_model_dispatches_all_stages':360,
        'max_normal_full_evaluations_two_blocks':160,'max_audit_full_evaluations':48,
        'generation_cost':'Common G for <=16 actual requests once; intermediate evolution cost E also separate. Report T_arm and G+E+T_arm, plus audit and timing-repeat costs. No free imported pilot fitness; no generation-savings claim from fixed replay.',
        'inference_limit':'Common adaptively generated pool is off-policy evidence for filter effects: arms do not causally generate their own Wave-2 stream. Two timing blocks are not multiseed search proof or statistical general speedup.',
        'main_campaign_enabled':False})
    for key in ('max_normal_dispatches_if_8_static_valid','max_audit_dispatches_if_all_8_skipped_in_each_behavioral_arm',
                'conservative_total_dispatch_ceiling_for_later_source_approval','max_normal_full_evaluations'):
        protocol.pop(key,None)
    write(HERE/'two_wave_replay_protocol.json',protocol)
    draws=deepcopy(old['draws'])
    for x in draws:x['wave']=1;x['index_in_wave']=x['batch_slot']
    gate={'required_new_wave1_feedback':True,'execution_configuration':'pilot_evolution_wave1',
        'execution_role':'evolution','wave1_attempts_must_be_terminal':8,
        'previous_evaluated_exact_key_sha256':known,
        'eligibility':'First occurrence of a static-valid exact-source key absent from frozen fully evaluated seed/FF/BF/Slot-12 references; not a claim of functional/behavioral novelty',
        'minimum_new_complete_registered_candidates':1,'improvement_required':False,
        'all_intermediate_results_complete_or_explicit_rejections':True,
        'any_uncertain_dispatch_or_cleanup_blocks_wave2':True,
        'required_evidence':['new-grant Wave-1 immutable pool and raw model responses',
            'separate actual source-specific user execution approval',
            'actual finite worker dispatch/results in evolution role, correct image/data/body',
            'complete coverage/finite scores/cleanup for accepted registrations',
            'original generation island counts and program/score/RNG checkpoint reconstruction',
            'actual subsequent upstream prompt and post-registration Pilot DB'],
        'forbidden_unlocks':['existing Slot-12 feedback alone','static validity alone','predicted fitness',
            'cached score from a comparison arm','source substitution','forced island or invented ancestor'],
        'failure_action':'Keep Wave 2 locked and its slots unused; stop/report blocker, never spend them on another seed-only wave or replacements'}
    settings=deepcopy(old['generation_settings'])
    controls={**old['control_sha256']}
    for p in [Path(__file__),HERE/'two_wave_guards.py',HERE/'two_wave_replay_protocol.json',
              ROOT/'config.json',POLICY_PATH,ROOT/'acceptance_policy.json']:
        controls[p.relative_to(PROJECT).as_posix()]=file_hash(p)
    request={'schema':'finite_qwen_two_wave_pilot-v1','approved':False,
        'kind':'finite_two_wave_generation_only','max_new_generation_requests':16,
        'per_wave_cap':8,'per_slot_max_attempts':1,'fresh_allocation':True,
        'supersedes_unapproved_eight_call_request_sha256':file_hash(HERE/'generation_request.json'),
        'old_twelve_slot_allocation_sha256':old['old_allocation_sha256'],'old_allocation_exhausted':True,
        'known_logged_pilot_calls_before':14,'known_logged_pilot_calls_max_after':30,
        'historical_connectivity_exact_count':None,'historical_connectivity_known_minimum':2,
        'lifetime_budget_certified':False,'nominal_pilot_plan':30,
        'model':settings['model'],'model_digest':settings['expected_digest'],'quantization':'Q4_K_M',
        'generation_settings':settings,'generation_policy_id':old['generation_policy_id'],
        'generation_policy_sha256':file_hash(POLICY_PATH),'active_static_policy':'phase3-numerical-ast-v2',
        'effective_context_length':32768,'fresh_non_generating_preload_required':True,'preload_keep_alive_seconds':120,
        'wave1':{'max_requests':8,'seeds':list(range(549199013,549199021)),'draws':draws,
            'starting_checkpoint':ref(parent/'database_after_registration.json'),
            'first_actual_next_prompt':ref(parent/'next_prompt.json'),
            'actual_parent_feedback':old['parent_actual_feedback'],
            'post_generation_state_reference':ref(PROJECT/draws[-1]['checkpoint']),
            'note':'First wave uses the existing authentic prompt schedule. Only selection/RNG advances; no new fitness is fabricated. Runtime age is recorded separately, not frozen as a fictitious generation duration.'},
        'intermediate':{'separate_source_specific_authorization_required':True,
            'max_full_development_evaluations':8,'one_per_new_exact_source_representative':True,
            'duplicate_or_invalid_records_preserved':True,'database':'Separate Pilot evolution copy; original replay checkpoint untouched',
            'no_score_from_replay_arm':True,'no_retry':True},
        'wave2':{'max_requests':8,'seeds':list(range(549199021,549199029)),
            'prompt_payloads':'Unknown until receipt-verified Wave-1 registration; derive only from actual upstream get_prompt and measured feedback using unchanged v3 wrapper',
            'do_not_force_island':True,'new_generation_approval_between_waves_required':False,
            'conditional_on':gate},
        'wave2_dependency':gate,
        'worker_images':{s:b['ImageId'] for s,b in read(ROOT/'slot12_recovery/build_receipt.json')['images'].items()},
        'development_dataset_sha256':read(ROOT/'slot12_recovery/build_receipt.json')['images']['development']['dataset_sha256'],
        'failure_policy':'No replacement or retry. Preserve every scheduled outcome. Completed invalid/truncated/duplicate outputs do not alter the next seed. A known HTTP failure remains consumed; a later distinct scheduled call requires fresh successful readiness. Readiness failure stops before reservation; uncertain transport/dispatch/cleanup stops without reset or implicit resumption.',
        'unused_wave1_slots_transfer_to_wave2':False,'third_wave_allowed':False,
        'candidate_execution_authorized':False,'maximum_candidate_evaluations':0,
        'future_execution_reviews':'One consolidated Wave-1 source manifest, then one consolidated final-pool replay/audit manifest after Wave-2 sources exist; no per-source preparation stages.',
        'main_calls':0,'heldout_access':False,'push_or_publication_authorized':False,
        'replay_protocol':ref(HERE/'two_wave_replay_protocol.json'),'control_sha256':controls,
        'implementation_status':'Finite counter and receipt-chain Wave-2 verifier implemented; positive new-wave path requires actual authorized generation/evaluation artifacts. Existing transport/database/worker retained; no environment rebuild.'}
    write(target,request)
    write(HERE/'two_wave_generation_approval.template.json',{'approved':False,'kind':request['kind'],
        'manifest_sha256':file_hash(target),'user_authorization_verbatim':None,'recorded_at_utc':None,
        'conditional_wave2_acknowledged':False,'note':'Only generation up to 8+8; execution remains separately source-approved. Inactive until exact explicit user approval.'})
    write(HERE/'eight_call_proposal_superseded.json',{'previous_request_sha256':file_hash(HERE/'generation_request.json'),
        'previous_proposal_was_approved':False,'status':'superseded_unapproved_proposal_not_additional_budget',
        'new_request':target.relative_to(PROJECT).as_posix(),'new_request_sha256':file_hash(target),
        'new_maximum_not_8_plus_16':16})
    print(str(target)+' '+file_hash(target)+' INACTIVE; no model calls')


if __name__=='__main__':main()
