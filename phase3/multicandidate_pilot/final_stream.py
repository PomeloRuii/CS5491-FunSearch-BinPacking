"""Static provenance, frozen authentic stream and finite replay/audit task scope."""
import argparse
import ast
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import shutil
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap3
from bootstrap3 import ROOT, PROJECT
from common import read, write, file_hash, digest
from approval import control_sources, check_controls
from backend_policy_v2 import check_build
from database_state import restore, snapshot
from generation3 import load_candidate
from generation_policy_v3 import messages_for
from interface import parse_candidate
from implementation.programs_database import Prompt
from static_policy import validate, POLICY_ID
from manifest3 import scope_slot
from two_wave_guards import feedback_condition, project_file, same_database
from wave1_artifacts import HERE, REQUEST, REQUEST_SHA, POOL as WAVE1, ref, verify_pool
from run_wave2_remaining import rng_neutral

WAVE2 = HERE/'sessions/20261102T094153054114Z_e66a1097/wave2/continued_pool.json'
LEARNING = HERE/'learning_runs/20261102T094004843784Z_45ae0300'
FINAL = HERE/'frozen_stream'
POOL = FINAL/'pool.json'
MANIFEST = HERE/'final_replay_execution_request.json'
PROTOCOL = HERE/'two_wave_replay_protocol.json'


def verify_wave2():
    pool = read(WAVE2); plan = read(REQUEST)
    if (pool['schema'] != 'qwen-two-wave-wave-pool-v1' or pool['wave'] != 2
            or pool['session_status'] != 'wave_complete' or pool['api_attempts'] != 8
            or [r['candidate_id'] for r in pool['candidates']] != list(range(9, 17))
            or pool['generation_request_sha256'] != REQUEST_SHA or pool['generated_sources_executed'] != 0):
        raise PermissionError('Wave2 is not the complete unchanged generation-only stream')
    bundle_file = project_file(pool['verified_feedback_bundle'])
    gate = rng_neutral(feedback_condition, plan, REQUEST_SHA, bundle_file)
    bundle = read(bundle_file); last = next(e for e in reversed(bundle['evaluations']) if e.get('next_prompt'))
    latest = read(project_file(last['candidate_result'])); following = read(project_file(last['next_prompt']))
    prompt = Prompt(following['code'], following['version_generated'], following['island_id'])
    database = restore(read(project_file(bundle['pilot_database_after'])))
    feedback = {'verified_real_model_feedback': True, 'candidate_id': latest['candidate_id'],
        'source_sha256': latest['source_sha256'], 'evaluated_island_id': latest['island_id'],
        'score': latest['score'], 'scores_per_group': latest['scores_per_group'],
        'feedback_receipt_sha256': file_hash(project_file(last['candidate_result']))}
    budget_root = ROOT/'dispatch_state'/REQUEST_SHA
    binding = {k: v for k, v in gate.items() if k != 'payloads'}
    if read(budget_root/'wave2_feedback_binding.json') != binding:
        raise PermissionError('Wave2 feedback binding differs')
    initial = project_file(pool['initial_session'])
    if read(initial)['candidates'] != pool['candidates'][:1]:
        raise PermissionError('Initial terminal response changed during continuation')
    continuation = read(budget_root/'wave2_known_prefix_continuation.json')
    if (continuation['consumed_request_retry'] is not False or continuation['all_unused_slots_proven_absent'] is not True
            or continuation['original_stopped_pool_sha256'] != file_hash(initial)
            or continuation['runner_sha256'] != file_hash(HERE/'run_wave2_remaining.py')):
        raise PermissionError('Known-prefix continuation provenance differs')
    for index, row in enumerate(pool['candidates']):
        cid = row['candidate_id']; directory = WAVE2.parent/f'candidate_{cid:03d}'
        req = read(directory/'request.json'); slot = budget_root/f'call_{cid:03d}'
        if index: prompt = database.get_prompt()
        actual_prompt = {'code': prompt.code, 'island_id': int(prompt.island_id), 'version_generated': prompt.version_generated}
        if (req['payload'] != gate['payloads'][index] or req['database_prompt'] != actual_prompt
                or messages_for(prompt, {**feedback, 'selected_next_island_id': int(prompt.island_id)}) != req['payload']['messages']
                or row['island_id'] != int(prompt.island_id) or row['version_generated'] != prompt.version_generated
                or row['sampling_seed'] != 549199021+index or row['expected_name'] != 'priority_v'+str(prompt.version_generated)
                or row['prompt_sha256'] != digest(req['payload']['messages'])):
            raise PermissionError('Real upstream Wave2 prompt/metadata/payload differs')
        if (read(directory/'candidate.json') != row or read(slot/'outcome.json') != row
                or read(slot/'request.json') != req['reservation']
                or read(slot/'transport_attempt_started.json')['payload_sha256'] != digest(req['payload'])
                or req['verified_feedback_bundle_sha256'] != file_hash(bundle_file)
                or req['runner_sha256'] != file_hash(HERE/'run_wave2.py')):
            raise PermissionError('Generation provenance differs')
        checkpoint = WAVE2.parent/f'database_before_{cid:03d}.json'
        if file_hash(checkpoint) != row['database_checkpoint_sha256'] or not same_database(snapshot(database), read(checkpoint)):
            raise PermissionError('Wave2 checkpoint differs from real upstream draw sequence')
        candidate = load_candidate(WAVE2, row)
        raw = directory/'raw_http_response.bin'; response = json.loads(raw.read_bytes())
        if (file_hash(raw) != row['raw_response_sha256'] or read(directory/'response.json') != response
                or response['model'] != plan['model'] or len(response['choices']) != 1
                or response['choices'][0]['message']['content'] != candidate.text
                or response['choices'][0]['finish_reason'] != row['finish_reason']
                or response.get('usage') != row['usage'] or row['api_attempts'] != 1
                or row['observed_fitness'] is not None or row['executed'] is not False):
            raise PermissionError('Raw generated candidate changed or substituted')
        ready = read(directory/'service_preload/readiness.json'); resident = ready['resident_model']
        if (ready['status'] != 'PASS' or file_hash(directory/'service_preload/readiness.json') != req['service_readiness_sha256']
                or resident['digest'] != plan['model_digest'] or resident['context_length'] != 32768
                or resident['size_vram'] != resident['size'] or resident['details']['quantization_level'] != 'Q4_K_M'
                or ready['preload_response']['done_reason'] != 'load' or ready['preload_response']['message']['content'] != ''
                or not any('RTX 5090' in g['name'] for g in ready['gpu_after']['gpus'])):
            raise PermissionError('Fresh model/GPU/context preload differs')
        for name, sha in ready['raw_response_hashes'].items():
            if file_hash(directory/'service_preload'/name) != sha:
                raise PermissionError('Raw readiness evidence changed')
        try: _, static = validate(candidate.text, row['expected_name'], row['finish_reason'])
        except (ValueError, SyntaxError) as exc:
            if row['status'] != 'static_rejected' or row['failure_reason'] != str(exc):
                raise PermissionError('Static rejection differs from frozen v2')
        else:
            if row['static'] != static or row['status'] != 'static_valid_pending_execution_approval':
                raise PermissionError('Static pass differs from frozen v2')
    if not same_database(snapshot(database), read(WAVE2.parent/'database_after_wave2_continuation.json')):
        raise PermissionError('End-of-wave checkpoint differs')
    if {p.name for p in budget_root.glob('call_*')} != {f'call_{i:03d}' for i in range(1, 17)}:
        raise PermissionError('Grant calls differ from finite16 slots')
    return pool, gate


def freeze():
    first, _, _ = verify_pool(WAVE1); second, _ = verify_wave2()
    if POOL.exists(): raise PermissionError('Do not overwrite a frozen stream')
    rows = []
    for source_pool, pool in ((WAVE1, first), (WAVE2, second)):
        for row in pool['candidates']:
            cid = row['candidate_id']; target = FINAL/f'candidate_{cid:03d}'/'source.py.txt'
            target.parent.mkdir(parents=True)
            shutil.copyfile(source_pool.parent/row['source_file'], target)
            rows.append({**row, 'source_file': target.relative_to(FINAL).as_posix(),
                'generation_provenance': {'pool': ref(source_pool), 'row_digest': digest(row),
                    'request': ref(source_pool.parent/f'candidate_{cid:03d}/request.json')}})
    write(POOL, {'schema': 'frozen-authentic-two-wave-stream-v1', 'generation_request_sha256': REQUEST_SHA,
        'model': first['model'], 'model_digest': first['model_digest'], 'quantization': 'Q4_K_M',
        'candidates': rows, 'api_attempts': 16, 'source_policy': POLICY_ID,
        'replay_checkpoint': ref(WAVE1.parent/'original_comparison_checkpoint.json'),
        'pilot_learning_bundle': ref(LEARNING/'wave1_feedback_bundle.json'),
        'selection': 'Every actual attempted slot, in order, including duplicates, invalids and truncation; no repairs or replacements',
        'scores_imported_into_replay': False})


def check_final_pool():
    first, _, _ = verify_pool(WAVE1); second, gate = verify_wave2()
    pool = read(POOL)
    expected = first['candidates']+second['candidates']
    if (pool['schema'] != 'frozen-authentic-two-wave-stream-v1' or pool['api_attempts'] != 16
            or len(pool['candidates']) != 16 or [r['candidate_id'] for r in pool['candidates']] != list(range(1, 17))):
        raise PermissionError('Frozen stream count/order differs')
    for row, original in zip(pool['candidates'], expected):
        source = row.copy(); source.pop('generation_provenance'); source['source_file'] = original['source_file']
        if source != original or row['generation_provenance']['row_digest'] != digest(original):
            raise PermissionError('Frozen source ledger differs from original actual outcome')
        project_file(row['generation_provenance']['pool']); project_file(row['generation_provenance']['request'])
        load_candidate(POOL, row)
    project_file(pool['replay_checkpoint']); project_file(pool['pilot_learning_bundle'])
    return pool


def diversity(pool):
    groups = {k: defaultdict(list) for k in ('raw', 'exact', 'ast')}; rows = []
    for row in pool['candidates']:
        cid = row['candidate_id']; groups['raw'][row['source_sha256']].append(cid)
        item = {'candidate_id': cid, 'status': row['status'], 'source_sha256': row['source_sha256']}
        try:
            parsed = parse_candidate(row['source'], row['expected_name'], row['finish_reason'])
            from filters import exact_source
            exact = hashlib.sha256(exact_source(row['source'], row['expected_name']).encode()).hexdigest()
            ast_sha = digest(ast.dump(ast.parse('def priority(item, bins):\n'+parsed.body), include_attributes=False))
            groups['exact'][exact].append(cid); groups['ast'][ast_sha].append(cid)
            item.update(exact_key_sha256=exact, function_ast_sha256=ast_sha)
        except (ValueError, SyntaxError) as exc: item['parse_rejection'] = str(exc)
        rows.append(item)
    valid_ids = {r['candidate_id'] for r in pool['candidates'] if r['status'] == 'static_valid_pending_execution_approval'}
    return {'raw_unique_all_sources': len(groups['raw']), 'complete_exact_unique': len(groups['exact']),
        'complete_ast_unique': len(groups['ast']), 'static_valid_count': len(valid_ids),
        'static_valid_exact_unique': len({r['exact_key_sha256'] for r in rows if r['candidate_id'] in valid_ids}),
        'static_valid_ast_unique': len({r['function_ast_sha256'] for r in rows if r['candidate_id'] in valid_ids}),
        'matching_groups': {k: [v for v in values.values() if len(v) > 1] for k, values in groups.items()},
        'candidate_analysis': rows, 'behavioral_diversity': 'NOT TESTED; AST/source equality is not full functional equivalence'}


def slots_for(rows):
    dev, audit = check_build('development'), check_build('audit')
    slots = []; protocol = read(PROTOCOL)
    for block, order in enumerate(protocol['mode_orders'], 1):
        for label in order:
            size = int(label.split('-')[1]) if label.startswith('behavioral-') else 16
            for row in rows:
                slots.append(scope_slot(f'block{block}/{label}', 'normal', row, dev, 'full'))
                if label.startswith('behavioral-'):
                    slots.append(scope_slot(f'block{block}/{label}', 'normal', row, dev, 'fingerprint', size))
    for size in (16, 64, 128):
        for row in rows:
            slots.append(scope_slot(f'behavioral-{size}', 'audit_candidate', row, dev, 'full'))
            slots.append(scope_slot(f'behavioral-{size}', 'audit_vector', row, audit, 'fingerprint', 256, 'audit'))
    return slots


def make_manifest():
    pool = check_final_pool()
    valid = [r for r in pool['candidates'] if r['status'] == 'static_valid_pending_execution_approval']
    slots = slots_for(valid); controls = control_sources()
    extra = [REQUEST, PROTOCOL, HERE/'two_wave_guards.py', ROOT/'acceptance_policy.json',
             ROOT/'slot12_recovery/build_receipt.json', ROOT/'slot12_recovery/validation.json']
    extra += list(HERE.glob('*.py'))
    for base in (WAVE1.parent, WAVE2.parent, LEARNING, FINAL):
        extra += [p for p in base.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
    controls.update({p.relative_to(PROJECT).as_posix(): file_hash(p) for p in set(extra)})
    m = {'schema': 'finite-source-task-set-v1', 'approved': False, 'static_policy': POLICY_ID,
        'candidate_pool': str(POOL.resolve()), 'candidate_pool_sha256': file_hash(POOL),
        'original_replay_checkpoint': pool['replay_checkpoint'], 'generation_request_sha256': REQUEST_SHA,
        'candidates': [{'candidate_id': r['candidate_id'], 'source_sha256': r['source_sha256'],
            'source': r['source'], 'expected_name': r['expected_name'], 'static': r['static'],
            'generation_island_id': r['island_id'], 'generation_version': r['version_generated']} for r in valid],
        'invalid_artifacts': [{'candidate_id': r['candidate_id'], 'status': r['status'],
            'reason': r.get('failure_reason')} for r in pool['candidates'] if r not in valid],
        'dispatch_slots': slots, 'maximum_container_dispatches': len(slots),
        'maximum_full_evaluations': sum(s['action'] == 'full' for s in slots),
        'maximum_fingerprint_tasks': sum(s['action'] == 'fingerprint' for s in slots),
        'maximum_wall_seconds_per_task': 10, 'heldout_access': False, 'fused_model_execution': False,
        'new_generation_calls_authorized': 0, 'automatic_retries': 0, 'main_calls': 0,
        'normal_blocks': 2, 'normal_mode_orders': read(PROTOCOL)['mode_orders'],
        'maximum_normal_dispatches': sum(s['role'] == 'normal' for s in slots),
        'maximum_audit_dispatches': sum(s['role'] != 'normal' for s in slots),
        'audit_policy': 'Every behavioral skip independently audited; per-N source full fitness and reserved-256 vectors once, referenced across identical timing repeats; audits never alter replay DB. Serial only.',
        'initial_cache': 'Empty in every arm/block. No intermediate fitness or vectors imported.',
        'known_runtime_invalid_source': 'ID5 remains in the same stream and shared runtime checks in all arms, without a privileged historical-score/rejection cache.',
        'execution_policy': 'Existing disposable read-only/non-root/no-network/no-host-mount worker; 1 CPU/512MiB/64PIDs/16MiB tmpfs/10-second external deadline/bounded output/verified cleanup. Stop on uncertain state; no retry.',
        'risk': 'Ordinary Docker residual shared-kernel, controller, resource, score-integrity and crash risks; not arbitrary-hostile-Python security.',
        'control_sha256': controls}
    if MANIFEST.exists(): raise PermissionError('Never overwrite sealed replay request')
    write(MANIFEST, m)
    write(HERE/'final_replay_approval.template.json', {'approved': False, 'kind': 'finite_source_execution',
        'manifest_sha256': file_hash(MANIFEST), 'user_authorization_verbatim': None,
        'recorded_at_utc': None, 'residual_risks_acknowledged': False})
    return m


def verify_manifest():
    m = read(MANIFEST); check_controls(m); pool = check_final_pool()
    valid = [r for r in pool['candidates'] if r['status'] == 'static_valid_pending_execution_approval']
    slots = slots_for(valid)
    if (file_hash(POOL) != m['candidate_pool_sha256'] or slots != m['dispatch_slots']
            or m['maximum_container_dispatches'] != len(slots)
            or m['maximum_full_evaluations'] != sum(s['action'] == 'full' for s in slots)
            or m['maximum_wall_seconds_per_task'] != 10 or m['static_policy'] != POLICY_ID
            or m['heldout_access'] is not False or m['fused_model_execution'] is not False
            or m['new_generation_calls_authorized'] != 0 or m['main_calls'] != 0
            or [r['candidate_id'] for r in m['candidates']] != [r['candidate_id'] for r in valid]):
        raise PermissionError('Finite replay/audit scope differs')
    for a, b in zip(m['candidates'], valid):
        if a['source'] != b['source'] or a['source_sha256'] != b['source_sha256']:
            raise PermissionError('Source substitution refused')
    return m, pool


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--freeze', action='store_true'); p.add_argument('--make-manifest', action='store_true')
    args = p.parse_args()
    if args.freeze: freeze()
    if args.make_manifest: make_manifest()
    if MANIFEST.exists(): verify_manifest()
    print(json.dumps(diversity(check_final_pool()), indent=2))
