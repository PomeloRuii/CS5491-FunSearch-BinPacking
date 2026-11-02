"""AST-only verification of the actual eight-response pool and finite task scope.

This module neither imports candidate sources nor calls candidate functions.
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap3
from bootstrap3 import ROOT, PROJECT
from common import read, write, file_hash, digest
from approval import check_controls, control_sources
from generation3 import load_candidate
from interface import parse_candidate
from static_policy import validate, POLICY_ID, NP_CALLS
from filters import exact_source
from database_state import restore, snapshot
from manifest3 import scope_slot
from backend_policy_v2 import check_build
from two_wave_guards import same_database

HERE = Path(__file__).resolve().parent
REQUEST = HERE/'two_wave_generation_request.json'
REQUEST_SHA = '954e19cd4201de94e6b09d237f6a9cb77bb045ef33ec06759fee84b7c8f853f8'
POOL = HERE/'sessions/20261102T091941782691Z_8039146d/wave1/pool.json'
MANIFEST = HERE/'wave1_execution_request.json'


def ref(path):
    path = Path(path).resolve()
    return {'path': path.relative_to(PROJECT).as_posix(), 'sha256': file_hash(path)}


def verify_pool(path=POOL):
    path = Path(path).resolve()
    if file_hash(REQUEST) != REQUEST_SHA:
        raise PermissionError('Generation grant changed')
    plan = read(REQUEST); check_controls(plan)
    pool = read(path)
    if (pool.get('schema') != 'qwen-two-wave-wave-pool-v1' or pool.get('wave') != 1
            or pool.get('generation_request_sha256') != REQUEST_SHA
            or pool.get('session_status') != 'wave_complete' or pool.get('api_attempts') != 8
            or pool.get('model') != plan['model'] or pool.get('model_digest') != plan['model_digest']
            or pool.get('generated_sources_executed') != 0 or pool.get('registration_count') != 0
            or pool.get('wave2_dispatched') is not False
            or [r['candidate_id'] for r in pool['candidates']] != list(range(1, 9))):
        raise PermissionError('Incomplete, substituted or already-executed generation pool')
    original = path.parent/'original_comparison_checkpoint.json'
    if file_hash(original) != pool['original_comparison_checkpoint_sha256']:
        raise PermissionError('Original checkpoint changed')
    database = restore(read(original))
    known = set(plan['wave2_dependency']['previous_evaluated_exact_key_sha256'])
    analysis = []; selected = []
    for row, draw in zip(pool['candidates'], plan['wave1']['draws']):
        cid = row['candidate_id']; directory = path.parent/f'candidate_{cid:03d}'
        request = read(directory/'request.json'); sealed = read(PROJECT/draw['request'])
        slot = ROOT/'dispatch_state'/REQUEST_SHA/f'call_{cid:03d}'
        marker = read(slot/'transport_attempt_started.json')
        if (read(directory/'candidate.json') != row or read(slot/'outcome.json') != row
                or read(slot/'request.json') != request['reservation']
                or marker['payload_sha256'] != draw['payload_sha256']
                or marker['sampling_seed'] != draw['seed'] or row['allocation_call_slot'] != cid
                or row['api_attempts'] != 1 or row.get('executed') is not False
                or row.get('observed_fitness') is not None):
            raise PermissionError('Generation reservation/outcome differs')
        if (request['payload'] != sealed['payload'] or digest(request['payload']) != draw['payload_sha256']
                or digest(request['payload']['messages']) != row['prompt_sha256']
                or request['database_prompt'] != sealed['database_prompt']
                or request['generation_request_sha256'] != REQUEST_SHA
                or row['sampling_seed'] != draw['seed']
                or row['island_id'] != draw['island_id'] or row['version_generated'] != draw['version_generated']):
            raise PermissionError('Sealed prompt, seed or real island differs')
        for key in ('request', 'checkpoint'):
            if file_hash(PROJECT/draw[key]) != draw[key+'_sha256']:
                raise PermissionError('Planned artifact changed')
        if cid > 1:
            prompt = database.get_prompt()
            if request['database_prompt'] != {'code': prompt.code, 'island_id': int(prompt.island_id),
                                              'version_generated': prompt.version_generated}:
                raise PermissionError('Prompt not derived from upstream database')
        checkpoint = path.parent/f'database_before_{cid:03d}.json'
        if (file_hash(checkpoint) != row['database_checkpoint_sha256']
                or not same_database(snapshot(database), read(checkpoint))
                or not same_database(read(PROJECT/draw['checkpoint']), read(checkpoint))):
            raise PermissionError('Program or RNG checkpoint differs')
        ready = read(directory/'service_preload/readiness.json')
        resident = ready['resident_model']
        if (file_hash(directory/'service_preload/readiness.json') != request['service_readiness_sha256']
                or ready['status'] != 'PASS' or ready['candidate_generation_requests'] != 0
                or ready['preload_response']['done_reason'] != 'load'
                or ready['preload_response']['message']['content'] != ''
                or resident['digest'] != plan['model_digest'] or resident['context_length'] != 32768
                or resident['details']['quantization_level'] != 'Q4_K_M'
                or resident['size_vram'] != resident['size'] or not ready['gpu_after']['ollama_compute_processes']
                or not any('RTX 5090' in g['name'] for g in ready['gpu_after']['gpus'])
                or request['model_metadata']['digest'] != plan['model_digest']):
            raise PermissionError('Pinned GPU/model/context readiness missing')
        for name, sha in ready['raw_response_hashes'].items():
            if file_hash(directory/'service_preload'/name) != sha:
                raise PermissionError('Service readiness raw evidence changed')
        raw = directory/'raw_http_response.bin'; response = json.loads(raw.read_bytes())
        candidate = load_candidate(path, row)
        if (file_hash(raw) != row['raw_response_sha256'] or read(directory/'response.json') != response
                or response['model'] != plan['model'] or len(response['choices']) != 1
                or response['choices'][0]['message']['content'] != candidate.text
                or response['choices'][0]['finish_reason'] != row['finish_reason']
                or response.get('usage') != row['usage'] or row['http_status'] != 200):
            raise PermissionError('Source is not the byte-preserved original response')
        item = {'candidate_id': cid, 'source_sha256': row['source_sha256'],
                'sampling_seed': row['sampling_seed'], 'island_id': row['island_id'],
                'finish_reason': row['finish_reason'], 'status': row['status'],
                'completion_tokens': row['usage']['completion_tokens'],
                'generation_seconds': row['generation_seconds'], 'eligible_intermediate': False}
        try:
            parsed = parse_candidate(candidate.text, row['expected_name'], row['finish_reason'])
            tree = ast.parse('def priority(item, bins):\n'+parsed.body)
            item['function_ast_sha256'] = digest(ast.dump(tree, include_attributes=False))
            item['exact_key_sha256'] = hashlib.sha256(exact_source(candidate.text, row['expected_name']).encode()).hexdigest()
            item['unsupported_numpy_calls'] = sorted({n.func.attr for n in ast.walk(tree)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and isinstance(n.func.value, ast.Name) and n.func.value.id == 'np' and n.func.attr not in NP_CALLS})
        except (ValueError, SyntaxError) as exc:
            item['parse_rejection'] = str(exc)
        try:
            parsed, static = validate(candidate.text, row['expected_name'], row['finish_reason'])
        except (ValueError, SyntaxError) as exc:
            if row['status'] != 'static_rejected' or row['failure_reason'] != str(exc):
                raise PermissionError('Historical rejection differs under frozen v2')
            item['static_rejection'] = str(exc)
        else:
            if row['status'] != 'static_valid_pending_execution_approval' or static != row['static']:
                raise PermissionError('Stored static pass differs')
            key = item['exact_key_sha256']; item['known_exact_match'] = key in known
            if key not in known:
                item['eligible_intermediate'] = True; selected.append(cid); known.add(key)
        analysis.append(item)
    if not same_database(snapshot(database), read(path.parent/'database_after_wave1_generation.json')):
        raise PermissionError('End-of-generation database changed')
    return pool, analysis, selected


def make_manifest(output=MANIFEST):
    pool, analysis, selected = verify_pool()
    build = check_build('development'); reviewed = []
    for row in pool['candidates']:
        if row['candidate_id'] not in selected: continue
        reviewed.append({'candidate_id': row['candidate_id'], 'source_sha256': row['source_sha256'],
            'expected_name': row['expected_name'], 'source': row['source'], 'static': row['static'],
            'generation_island_id': row['island_id'], 'generation_version': row['version_generated']})
    controls = control_sources()
    extra = [REQUEST, HERE/'PLAN.md', HERE/'two_wave_guards.py', Path(__file__), HERE/'evaluate_wave1_once.py',
        HERE/'run_wave1.py', ROOT/'acceptance_policy.json', ROOT/'slot12_recovery/build_receipt.json',
        ROOT/'slot12_recovery/validation.json']
    extra += [p for p in POOL.parent.rglob('*') if p.is_file()]
    controls.update({p.relative_to(PROJECT).as_posix(): file_hash(p) for p in extra})
    result = {'schema': 'finite-source-task-set-v1', 'approved': False,
        'generation_request_sha256': REQUEST_SHA, 'wave': 1, 'static_policy': POLICY_ID,
        'candidate_pool': str(POOL.resolve()), 'candidate_pool_sha256': file_hash(POOL),
        'pilot_database_start': ref(POOL.parent/'database_after_wave1_generation.json'),
        'original_comparison_checkpoint': ref(POOL.parent/'original_comparison_checkpoint.json'),
        'candidates': reviewed, 'selection_rule': 'All first static-valid new exact-source representatives in original order; no behavioral selection',
        'candidate_decisions': analysis,
        'dispatch_slots': [scope_slot('pilot_evolution_wave1', 'evolution', row, build, 'full')
                           for row in pool['candidates'] if row['candidate_id'] in selected],
        'maximum_container_dispatches': len(selected), 'maximum_full_evaluations': len(selected),
        'maximum_wall_seconds_per_task': 10, 'heldout_access': False, 'fused_model_execution': False,
        'new_generation_calls_authorized': 0, 'automatic_retries': 0,
        'fingerprint_or_audit_tasks_authorized': 0, 'control_sha256': controls,
        'risk': 'Ordinary Docker residual shared-kernel/controller/output/score-integrity and crash risks; static screening is not a safety proof.',
        'execution_policy': 'Existing disposable non-root, read-only, no-network, no-host-mount worker; one CPU, 512 MiB, 64 PIDs, 16 MiB tmpfs, bounded output and external 10-second deadline; stop on uncertain dispatch or cleanup.',
        'feedback_policy': 'Actual complete accepted registrations in original generation islands only; separate Pilot database. This executable stops after evaluation receipts, never dispatches Wave 2.'}
    if Path(output).exists(): raise PermissionError('Never overwrite a sealed execution request')
    write(output, result)
    write(HERE/'wave1_execution_approval.template.json', {'approved': False,
        'kind': 'finite_source_execution', 'manifest_sha256': file_hash(output),
        'user_authorization_verbatim': None, 'recorded_at_utc': None, 'residual_risks_acknowledged': False})
    return result


def verify_manifest(path=MANIFEST):
    m = read(path); check_controls(m)
    pool_file = Path(m['candidate_pool']); pool, analysis, selected = verify_pool(pool_file)
    build = check_build('development')
    expected_slots = [scope_slot('pilot_evolution_wave1', 'evolution', r, build, 'full')
                      for r in pool['candidates'] if r['candidate_id'] in selected]
    if (file_hash(pool_file) != m['candidate_pool_sha256'] or m['dispatch_slots'] != expected_slots
            or [r['candidate_id'] for r in m['candidates']] != selected
            or m['candidate_decisions'] != analysis or m['static_policy'] != POLICY_ID
            or m['maximum_container_dispatches'] != len(selected) or m['maximum_full_evaluations'] != len(selected)
            or m['maximum_wall_seconds_per_task'] != 10 or m['heldout_access'] is not False
            or m['fused_model_execution'] is not False or m['new_generation_calls_authorized'] != 0):
        raise PermissionError('Finite task/source selection changed')
    for selected_row in m['candidates']:
        original = next(r for r in pool['candidates'] if r['candidate_id'] == selected_row['candidate_id'])
        if (selected_row['source'] != original['source'] or selected_row['source_sha256'] != original['source_sha256']
                or selected_row['expected_name'] != original['expected_name']):
            raise PermissionError('Reviewed source substitution')
    return m


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--make-manifest', action='store_true')
    args = parser.parse_args()
    if args.make_manifest: make_manifest()
    else: verify_manifest()
    print(str(MANIFEST)+' SHA-256 '+file_hash(MANIFEST)+'; static/provenance checks only, zero execution')
