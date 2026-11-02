"""Finite 8+8 generation reservations and receipt-derived Wave-2 dependency.

No API or candidate execution here. Prior/arm scores cannot unlock Wave 2: its
program state is reconstructed from approved Wave-1 worker results only.
"""
import hashlib
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap3
from bootstrap3 import ROOT,PROJECT
from common import read,write,file_hash,digest,stamp
from approval import approved_receipt,check_controls,durable_reservation
from database_state import restore,snapshot
from replay import accepted_full
from candidate_runner import verify_candidate_config
from static_policy import validate
from filters import exact_source
from generation_policy_v3 import messages_for
from implementation import evaluator,code_manipulation as cm
from implementation.programs_database import Prompt
from trusted_cases import SPECIFICATION


def project_file(reference):
    path=Path(reference['path'])
    if not path.is_absolute():path=PROJECT/path
    path=path.resolve()
    if not path.is_relative_to(PROJECT) or file_hash(path)!=reference['sha256']:
        raise PermissionError('Missing/changed workspace evidence file')
    return path


def same_database(expected,actual):
    return all(digest(v)==digest(actual.get(k)) for k,v in expected.items() if k!='reset_age_seconds')


def feedback_condition(plan,request_hash,bundle_file):
    """Return exact allowed Wave-2 payloads only from complete real registration."""
    try:
        return _feedback_condition(plan,request_hash,Path(bundle_file))
    except (OSError,KeyError,TypeError,ValueError,IndexError) as exc:
        raise PermissionError('Wave 2 locked: missing/invalid fresh Wave-1 feedback evidence') from exc


def _feedback_condition(plan,request_hash,bundle_file):
    bundle=read(bundle_file)
    if bundle.get('generation_request_sha256')!=request_hash or bundle.get('wave')!=1:
        raise PermissionError('Only this grant\'s actual Wave-1 evaluation can unlock Wave 2')
    pool_file=project_file(bundle['wave1_pool']);pool=read(pool_file)
    if (pool.get('schema')!='qwen-two-wave-wave-pool-v1' or pool.get('wave')!=1
            or pool.get('generation_request_sha256')!=request_hash
            or pool.get('session_status')!='wave_complete' or pool.get('api_attempts')!=8):
        raise PermissionError('Wave 1 is not a complete recorded eight-attempt wave')
    generation_root=ROOT/'dispatch_state'/request_hash
    for i in range(1,9):
        folder=generation_root/f'call_{i:03d}'
        read(folder/'transport_attempt_started.json');read(folder/'outcome.json')
    manifest_file=project_file(bundle['execution_manifest']);m=read(manifest_file)
    approval=project_file(bundle['execution_approval'])
    approved_receipt(approval,'finite_source_execution',file_hash(manifest_file));check_controls(m)
    if file_hash(pool_file)!=m['candidate_pool_sha256'] or m.get('static_policy')!='phase3-numerical-ast-v2':
        raise PermissionError('Evaluation source pool or static policy differs')
    slots={s['candidate_id']:s for s in m['dispatch_slots']
           if s['configuration']=='pilot_evolution_wave1' and s['role']=='evolution' and s['action']=='full'}
    if (not 1<=len(slots)<=8 or len(slots)!=len(m['dispatch_slots'])
            or m.get('maximum_container_dispatches')!=len(slots)
            or m.get('maximum_full_evaluations')!=len(slots)
            or m.get('maximum_wall_seconds_per_task')!=10
            or m.get('heldout_access') is not False or m.get('fused_model_execution') is not False):
        raise PermissionError('Only the finite intermediate Wave-1 full-development scope can supply feedback')
    events=bundle['evaluations']
    ids=[e['candidate_id'] for e in events]
    if not slots or ids!=sorted(set(ids)) or set(ids)!=set(slots):
        raise PermissionError('Every approved intermediate slot needs a terminal evaluation receipt')
    rows={r['candidate_id']:r for r in pool['candidates']}
    if set(rows)!=set(range(1,9)):raise PermissionError('Wave-1 stream order/IDs changed')
    db_file=project_file(bundle['pilot_database_start'])
    reference=read(project_file(plan['wave1']['post_generation_state_reference']))
    if not same_database(reference,read(db_file)):
        raise PermissionError('Pilot DB must start at the authentic end-of-Wave-1 prompt state')
    database=restore(read(db_file))
    groups=read(ROOT/'build_contexts/development/research_data.json')['development']
    known=set(plan['wave2_dependency']['previous_evaluated_exact_key_sha256'])
    eligible_successes=[];latest_prompt=None;latest_result_path=None
    for event in events:
        cid=event['candidate_id'];source_row=rows[cid];slot=slots[cid]
        selected=next(s for s in m['candidates'] if s['candidate_id']==cid)
        source=selected['source'];sha=hashlib.sha256(source.encode()).hexdigest()
        if sha!=source_row['source_sha256'] or sha!=slot['source_sha256']:
            raise PermissionError('Source substitution in Wave-1 feedback')
        candidate_source=project_file({'path':(pool_file.parent/source_row['source_file']).as_posix(),'sha256':sha})
        if candidate_source.read_bytes()!=source.encode():raise PermissionError('Original source bytes differ')
        outcome=read(generation_root/f'call_{cid:03d}'/'outcome.json')
        if outcome!=source_row:raise PermissionError('Wave-1 source differs from actual generation outcome')
        raw=project_file(event['raw_generation_response'])
        import json
        response=json.loads(raw.read_bytes())
        if (file_hash(raw)!=source_row['raw_response_sha256'] or response.get('model')!=plan['model']
                or len(response['choices'])!=1 or response['choices'][0]['message']['content']!=source
                or response['choices'][0]['finish_reason']!='stop'):
            raise PermissionError('Feedback source is not the complete original Qwen response')
        parsed,_=validate(source,selected['expected_name'],'stop')
        key=hashlib.sha256(exact_source(source,selected['expected_name']).encode()).hexdigest()
        if key in known:raise PermissionError('Intermediate eligibility requires a new exact-source representative')
        known.add(key)
        root=ROOT/'dispatch_state'/file_hash(manifest_file)/slot['slot_id']
        dispatch=read(root/'dispatch.json');worker=read(root/'result.json')
        if dispatch['scope']!={k:v for k,v in slot.items() if k!='slot_id'}:
            raise PermissionError('Worker dispatch scope differs')
        if (worker['image']!=plan['worker_images']['development'] or slot['dataset']!='development'
                or slot['dataset_sha256']!=plan['development_dataset_sha256']
                or not worker.get('cleanup_verified')):
            raise PermissionError('Unverified image/data/cleanup blocks Wave 2')
        verify_candidate_config(worker['inspected_configuration'],worker['image'])
        if worker.get('result'):
            task=worker['result'].get('task',{})
            if any(task.get(k)!=slot[k] for k in ('action','dataset','dataset_sha256','state_bank_sha256','state_set','fingerprint_size')):
                raise PermissionError('Worker task differs from approved evolution scope')
        body=cm.rename_function_calls(parsed.body,parsed.function_name,'priority')
        if hashlib.sha256(body.encode()).hexdigest()!=worker['body_sha256']:
            raise PermissionError('Worker body differs from actual approved Qwen source')
        result_path=project_file(event['candidate_result']);result=read(result_path)
        before=read(project_file(event['database_before']))
        if not same_database(snapshot(database),before):raise PermissionError('Pilot history contains imported or missing state')
        if result['source_sha256']!=sha or result.get('origin')!='ollama':
            raise PermissionError('Only actual Wave-1 model result receipts count')
        if result.get('status')=='evaluated':
            if (not accepted_full(worker,groups) or result.get('registered') is not True
                    or result['scores_per_group']!=worker['result']['scores_per_group']
                    or result['score']!=worker['result']['score']
                    or result['island_id']!=source_row['island_id']
                    or result['version_generated']!=source_row['version_generated']
                    or result['evaluation'].get('status')!='ok'
                    or result['evaluation'].get('score')!=result['score']):
                raise PermissionError('Complete actual score and original-island registration required')
            function,program=evaluator._sample_to_program(parsed.body,result['version_generated'],
                cm.text_to_program(SPECIFICATION),'priority')
            if program!=result['evaluation']['program']:raise PermissionError('Program/specification differs')
            counts=[i._num_programs for i in database._islands]
            database.register_program(function,result['island_id'],worker['result']['scores_per_group'])
            expected=counts.copy();expected[result['island_id']]+=1
            if ([i._num_programs for i in database._islands]!=expected
                    or result['evaluation']['island_counts_before']!=counts
                    or result['evaluation']['island_counts_after']!=expected):
                raise PermissionError('Registration counts differ from actual upstream state')
            latest_prompt=database.get_prompt();latest_result_path=result_path
            following=read(project_file(event['next_prompt']))
            if (latest_prompt.code!=following['code'] or int(latest_prompt.island_id)!=following['island_id']
                    or latest_prompt.version_generated!=following['version_generated']):
                raise PermissionError('Next prompt was forced or is not receipt-reproducible')
            eligible_successes.append(result)
        elif result.get('registered') or accepted_full(worker,groups):
            raise PermissionError('Rejected/partial outcomes cannot manufacture registration')
        after=read(project_file(event['database_after']))
        if not same_database(snapshot(database),after):
            raise PermissionError('Saved evolution DB is not reconstructed solely from Wave-1 results')
    if not eligible_successes or latest_prompt is None:
        raise PermissionError('No eligible newly evaluated/registered candidate: do not spend Wave 2')
    latest=eligible_successes[-1]
    final_file=project_file(bundle['pilot_database_after'])
    if not same_database(snapshot(database),read(final_file)):
        raise PermissionError('Final pilot DB differs; comparison-arm fitness import is forbidden')
    feedback={'verified_real_model_feedback':True,'candidate_id':latest['candidate_id'],
        'source_sha256':latest['source_sha256'],'evaluated_island_id':latest['island_id'],
        'score':latest['score'],'scores_per_group':latest['scores_per_group'],
        'selected_next_island_id':int(latest_prompt.island_id),
        'feedback_receipt_sha256':file_hash(latest_result_path)}
    payloads=[];prompt=latest_prompt
    for i in range(8):
        if i:prompt=database.get_prompt()
        context={**feedback,'selected_next_island_id':int(prompt.island_id)}
        settings=plan['generation_settings']
        payloads.append({'model':plan['model'],'messages':messages_for(prompt,context),
            'n':1,'stream':False,'temperature':settings['temperature'],'top_p':settings['top_p'],
            'max_tokens':settings['max_tokens'],'reasoning_effort':settings['reasoning_effort'],
            'seed':549199021+i})
    return {'payloads':payloads,'bundle_sha256':file_hash(bundle_file),
        'pilot_database_sha256':file_hash(final_file),'wave1_pool_sha256':file_hash(pool_file),
        'execution_manifest_sha256':file_hash(manifest_file),'successful_new_registrations':len(eligible_successes)}


class TwoWaveBudget:
    def __init__(self,request_path,approval_path,state_root=None):
        self.path=Path(request_path);self.plan=read(self.path);self.hash=file_hash(self.path)
        receipt=read(approval_path)
        if (receipt.get('approved') is not True or receipt.get('kind')!='finite_two_wave_generation_only'
                or receipt.get('manifest_sha256')!=self.hash or not receipt.get('user_authorization_verbatim')
                or not receipt.get('recorded_at_utc') or receipt.get('conditional_wave2_acknowledged') is not True):
            raise PermissionError('New exact two-wave generation-only approval required')
        check_controls(self.plan)
        if (self.plan.get('max_new_generation_requests')!=16 or self.plan.get('per_wave_cap')!=8
                or self.plan.get('per_slot_max_attempts')!=1 or self.plan.get('candidate_execution_authorized') is not False
                or self.plan.get('main_calls')!=0):
            raise PermissionError('Only the declared finite 8+8 scope is supported')
        self.root=Path(state_root or ROOT/'dispatch_state')/self.hash
        self.root.mkdir(parents=True,exist_ok=True)

    def reserve(self,wave,index,payload,wave1_feedback_bundle=None):
        if type(wave) is not int or type(index) is not int or wave not in (1,2) or not 1<=index<=8:
            raise PermissionError('No wave transfer, replacement seed or third wave')
        slot=(wave-1)*8+index
        if any(not (self.root/f'call_{j:03d}/outcome.json').exists() for j in range((wave-1)*8+1,slot)):
            raise PermissionError('Previous planned outcome missing/uncertain; no implicit resumption')
        binding=None
        if wave==1:
            if (self.root/'wave2_feedback_binding.json').exists():raise PermissionError('Wave 1 already closed')
            expected=self.plan['wave1']['draws'][index-1]['payload_sha256']
        else:
            if wave1_feedback_bundle is None:raise PermissionError('Fresh actual Wave-1 feedback is mandatory')
            gate=feedback_condition(self.plan,self.hash,wave1_feedback_bundle)
            expected=digest(gate['payloads'][index-1])
            binding={k:v for k,v in gate.items() if k!='payloads'}
        if payload.get('seed')!=549199012+slot or digest(payload)!=expected:
            raise PermissionError('Wrong predetermined seed/settings/prompt')
        if binding is not None:
            lock=self.root/'wave2_feedback_binding.json'
            if lock.exists():
                if read(lock)!=binding:raise PermissionError('Wave-2 feedback cannot be substituted mid-wave')
            else:durable_reservation(lock,binding)
        path=self.root/f'call_{slot:03d}'
        try:path.mkdir()
        except FileExistsError:raise PermissionError('Slot already reserved: never reset or retry')
        record={'reservation':stamp(),'call_slot':slot,'wave':wave,'index_in_wave':index,
            'sampling_seed':payload['seed'],'payload_sha256':digest(payload),
            'approval_manifest_sha256':self.hash,'budget_class':'pilot',
            'status':'reserved_before_dispatch_uncertain_until_outcome'}
        durable_reservation(path/'request.json',record)
        return path,record
