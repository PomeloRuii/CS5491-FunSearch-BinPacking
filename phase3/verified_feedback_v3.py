"""Require actual approved model execution receipts; never synthesize fitness."""
from pathlib import Path
import hashlib
import bootstrap3
from bootstrap3 import ROOT,PHASE2
from common import read,file_hash,digest
from approval import approved_receipt,check_controls
from paths3 import recorded_path
from policy_artifacts_v3 import check_pool
from generation3 import load_candidate
from static_policy import validate
from replay import accepted_full
from candidate_runner import verify_candidate_config
from database_state import restore,snapshot
from implementation import evaluator
from implementation import code_manipulation as cm
from implementation.programs_database import Prompt
from trusted_cases import SPECIFICATION

_VERIFIED_PROOFS={}

def require_verified_proof(proof):
    entry=_VERIFIED_PROOFS.get(id(proof))
    if entry is None or entry[0] is not proof or entry[1]!=digest(proof):
        raise PermissionError('Only an in-process receipt-verified feedback proof can dispatch generation')

def load_verified_feedback(directory, execution_manifest, execution_approval):
    directory=Path(directory)
    manifest=read(execution_manifest);manifest_hash=file_hash(execution_manifest)
    approved_receipt(execution_approval,'finite_source_execution',manifest_hash)
    check_controls(manifest)
    saved=read(directory/'next_prompt.json');row=read(directory/'candidate_result.json')
    after_file=directory/'database_after_registration.json'
    if (saved.get('registration_verified') is not True
        or file_hash(after_file)!=saved['database_sha256']
        or file_hash(directory/'candidate_result.json')!=saved['evaluation_receipt_sha256']
        or row.get('origin')!='ollama' or row.get('status')!='evaluated' or row.get('registered') is not True):
        raise PermissionError('Actual registered model feedback is required, not trusted/mock/predicted fitness')
    candidate_id=row['candidate_id']
    sources=[s for s in manifest['candidates'] if s['candidate_id']==candidate_id]
    if len(sources)!=1:raise PermissionError('Missing approved model source')
    source=sources[0]
    if row['source_sha256']!=source['source_sha256']:
        raise PermissionError('Source differs from approved evaluation')
    slots=[s for s in manifest['dispatch_slots'] if s['configuration']=='live_feedback'
           and s['role']=='feedback' and s['candidate_id']==candidate_id and s['action']=='full']
    if len(slots)!=1:raise PermissionError('Need one actual feedback evaluation slot')
    slot=slots[0];root=ROOT/'dispatch_state'/manifest_hash/slot['slot_id']
    dispatch=read(root/'dispatch.json');record=read(root/'result.json')
    if dispatch['scope']!={k:v for k,v in slot.items() if k!='slot_id'}:
        raise PermissionError('Dispatch scope differs')
    groups=read(PHASE2/'data/research_data.json')['development']
    if not accepted_full(record,groups) or record['image']!=slot['image']:
        raise PermissionError('Complete actual isolated evaluation and cleanup required')
    verify_candidate_config(record['inspected_configuration'],slot['image'])
    for key in ('action','dataset','dataset_sha256','state_bank_sha256','state_set','fingerprint_size'):
        if record['result']['task'][key]!=slot[key]:raise PermissionError('Runtime scope differs')
    if (record['result']['score']!=row['score'] or record['result']['scores_per_group']!=row['scores_per_group']
        or row['evaluation']['status']!='ok' or row['evaluation']['score']!=row['score']):
        raise PermissionError('Fitness does not match actual worker/registration receipts')
    pool_file=recorded_path(manifest['candidate_pool']);pool=check_pool(pool_file)
    if file_hash(pool_file)!=manifest['candidate_pool_sha256'] or saved['source_pool_sha256']!=file_hash(pool_file):
        raise PermissionError('Source session checkpoint differs')
    original=next(r for r in pool['candidates'] if r['candidate_id']==candidate_id)
    candidate=load_candidate(pool_file,original)
    parsed,_=validate(candidate.text,original['expected_name'],candidate.finish_reason)
    body=cm.rename_function_calls(parsed.body,parsed.function_name,'priority')
    if hashlib.sha256(body.encode()).hexdigest()!=record['body_sha256']:
        raise PermissionError('Executed body differs from approved original source')
    before_file=pool_file.parent/f'database_before_{candidate_id:03d}.json'
    if file_hash(before_file)!=original['database_checkpoint_sha256']:
        raise PermissionError('Original real database checkpoint changed')
    original_checkpoint=read(before_file);actual_after=read(after_file)
    database=restore(original_checkpoint)
    function,program=evaluator._sample_to_program(parsed.body,row['version_generated'],
                                                cm.text_to_program(SPECIFICATION),'priority')
    if program!=row['evaluation']['program']:raise PermissionError('Packing specification/program differs')
    before=[i._num_programs for i in database._islands]
    if before!=row['evaluation']['island_counts_before']:raise PermissionError('Pre-registration state differs')
    # Replay ONLY registration of the receipt-verified actual result, never an invented score.
    database.register_program(function,row['island_id'],record['result']['scores_per_group'])
    after=[i._num_programs for i in database._islands]
    expected=before.copy();expected[row['island_id']]+=1
    if after!=expected or after!=row['evaluation']['island_counts_after']:
        raise PermissionError('Real island registration count differs')
    reconstructed=database.get_prompt()
    prompt=Prompt(saved['code'],saved['version_generated'],saved['island_id'])
    if reconstructed!=prompt:raise PermissionError('Next prompt not reproducible from actual state and result')
    rebuilt=snapshot(database)
    for key in rebuilt:
        if key!='reset_age_seconds' and digest(rebuilt[key])!=digest(actual_after[key]):
            raise PermissionError('Saved post-registration state differs: '+key)
    proof={'verified_real_model_feedback':True,'candidate_id':candidate_id,
        'source_sha256':source['source_sha256'],'evaluated_island_id':row['island_id'],
        'score':row['score'],'scores_per_group':row['scores_per_group'],
        'selected_next_island_id':prompt.island_id,
        'feedback_receipt_sha256':file_hash(directory/'candidate_result.json'),
        'execution_manifest_sha256':manifest_hash,'worker_result_sha256':file_hash(root/'result.json'),
        'database_sha256':file_hash(after_file),'next_prompt_reconstructed_identically':True,
        'generation_source_pool_sha256':file_hash(pool_file),'candidate_job_id':record['job_id']}
    _VERIFIED_PROOFS[id(proof)]=(proof,digest(proof))
    return prompt,proof,actual_after
