"""Continue ONLY an evidenced, known pre-dispatch stop, never a consumed request.

The initial Wave-2 artifacts and driver remain unchanged. Receipt verification
uses global upstream RNG internally; save/restore its caller's controller state.
This does not weaken the sealed guard, modify its inputs or reset any slot.
"""
import argparse
from dataclasses import asdict, replace
import hashlib
from pathlib import Path
import random
import sys
from time import perf_counter
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap3
from bootstrap3 import ROOT, PROJECT
from common import read, write, file_hash, digest, stamp
from approval import durable_reservation
from database_state import restore, snapshot
from generation3 import fixed_config, EventLog
from generation_policy_v3 import messages_for
from implementation.programs_database import Prompt
from ollama_adapter import OllamaAdapter
from ollama_readiness import preload
from two_wave_guards import TwoWaveBudget, feedback_condition, project_file, same_database
from wave1_artifacts import HERE, REQUEST, REQUEST_SHA
from run_wave2 import generate_once

STOPPED_POOL = HERE/'sessions/20261102T094153054114Z_e66a1097/wave2/pool.json'
EXPECTED_PREFIX_SHA = '20d25e5bd24f7159578f59fabb60bac39c3a4b28d6a0747d9d76b9b13c12a811'


def rng_neutral(function, *args, **kwargs):
    numpy_state, python_state = np.random.get_state(), random.getstate()
    try: return function(*args, **kwargs)
    finally:
        np.random.set_state(numpy_state); random.setstate(python_state)


class PreservingBudget(TwoWaveBudget):
    def reserve(self, *args, **kwargs):
        return rng_neutral(super().reserve, *args, **kwargs)


def verified_prefix(approval):
    budget = PreservingBudget(REQUEST, approval)
    pool = read(STOPPED_POOL); directory = STOPPED_POOL.parent
    expected_failure = {'stage': 'pre_dispatch_or_controller', 'candidate_id': 10,
        'error_type': 'PermissionError', 'reason': 'Actual upstream prompt/feedback differs from dependency-derived payload'}
    if (pool['failure'] != expected_failure or pool['api_attempts'] != 1
            or pool['session_status'] != 'stopped_without_retry' or len(pool['candidates']) != 1
            or read(directory/'stopped.json') != expected_failure):
        raise PermissionError('Only the exact known no-dispatch controller stop is continuable')
    row = pool['candidates'][0]; slot = budget.root/'call_009'
    if (row['candidate_id'] != 9 or row['source_sha256'] != EXPECTED_PREFIX_SHA
            or row['status'] != 'static_rejected' or row['http_status'] != 200
            or row['delivery_status'] != 'response_received' or row['session_hard_stop'] is not False
            or read(slot/'outcome.json') != row or read(directory/'candidate_009/candidate.json') != row
            or read(slot/'request.json') != read(directory/'candidate_009/request.json')['reservation']):
        raise PermissionError('Missing/uncertain or substituted consumed prefix: stop')
    raw = directory/'candidate_009/raw_http_response.bin'
    response = read(directory/'candidate_009/response.json')
    if (file_hash(raw) != row['raw_response_sha256'] or __import__('json').loads(raw.read_bytes()) != response
            or response['choices'][0]['message']['content'] != row['source']
            or hashlib.sha256(row['source'].encode()).hexdigest() != EXPECTED_PREFIX_SHA):
        raise PermissionError('Known terminal prefix source/response changed')
    if any((budget.root/f'call_{i:03d}').exists() for i in range(10, 17)):
        raise PermissionError('Any remaining slot state forbids this continuation; never reset')
    if (budget.root/'wave2_known_prefix_continuation.json').exists():
        raise PermissionError('Continuation already reserved; no implicit second resumption')
    if any((directory/'candidate_010').iterdir()):
        raise PermissionError('Unexpected next-candidate artifacts: stop')
    bundle_file = project_file(pool['verified_feedback_bundle'])
    gate = feedback_condition(budget.plan, budget.hash, bundle_file)
    if read(budget.root/'wave2_feedback_binding.json') != {k: v for k, v in gate.items() if k != 'payloads'}:
        raise PermissionError('Original Wave-2 feedback binding changed')
    first = read(directory/'candidate_009/request.json')
    marker = read(slot/'transport_attempt_started.json')
    if first['payload'] != gate['payloads'][0] or marker['payload_sha256'] != digest(gate['payloads'][0]):
        raise PermissionError('First call differs from exact dependency-derived request')
    return budget, pool, bundle_file, gate


def main(args):
    if file_hash(REQUEST) != REQUEST_SHA: raise PermissionError('Generation request changed')
    budget, pool, bundle_file, gate = verified_prefix(args.approval)
    bundle = read(bundle_file)
    last = next(e for e in reversed(bundle['evaluations']) if e.get('next_prompt'))
    result = read(project_file(last['candidate_result'])); saved = read(project_file(last['next_prompt']))
    prompt = Prompt(saved['code'], saved['version_generated'], saved['island_id'])
    database = restore(read(project_file(bundle['pilot_database_after'])))
    feedback = {'verified_real_model_feedback': True, 'candidate_id': result['candidate_id'],
        'source_sha256': result['source_sha256'], 'evaluated_island_id': result['island_id'],
        'score': result['score'], 'scores_per_group': result['scores_per_group'],
        'feedback_receipt_sha256': file_hash(project_file(last['candidate_result']))}
    # Reconstruct only the verified generation prefix, from its immutable input.
    # No candidate code, fitness or program history is reconstructed/invented.
    if not same_database(snapshot(database), read(STOPPED_POOL.parent/'database_before_009.json')):
        raise PermissionError('First generation checkpoint does not match actual Pilot input')
    before = snapshot(database)
    rng_neutral(feedback_condition, budget.plan, budget.hash, bundle_file)
    if not same_database(before, snapshot(database)):
        raise PermissionError('Receipt verifier still alters caller RNG')
    check = restore(before)
    for i in range(8):
        if i: prompt = check.get_prompt()
        if messages_for(prompt, {**feedback, 'selected_next_island_id': int(prompt.island_id)}) != gate['payloads'][i]['messages']:
            raise PermissionError('Upstream prompt sequence is not exactly receipt-derived')
    database = restore(before)
    durable_reservation(budget.root/'wave2_known_prefix_continuation.json', {
        'timestamp': stamp(), 'original_stopped_pool_sha256': file_hash(STOPPED_POOL),
        'feedback_bundle_sha256': file_hash(bundle_file), 'runner_sha256': file_hash(Path(__file__)),
        'permitted_first_attempt_slots': list(range(10, 17)), 'consumed_request_retry': False,
        'all_unused_slots_proven_absent': True, 'global_rng_preservation_check': 'PASS',
        'upstream_eight_prompt_reconstruction': 'PASS',
        'reason': 'Confirmed complete slot9, exact pre-dispatch stop before slot10 reservation. No delivery/authorization/cleanup uncertainty. Continue only unchanged unused approved requests; preserve initial stop and incorrect stopped controller RNG snapshot.'})
    directory = STOPPED_POOL.parent; rows = list(pool['candidates']); started = perf_counter(); failure = None
    log = EventLog(directory/'continuation_events.jsonl')
    output = directory/'continued_pool.json'
    if output.exists(): raise PermissionError('Never overwrite a previous continuation')

    def save(status):
        write(output, {**{k: v for k, v in pool.items() if k not in ('candidates', 'api_attempts', 'failure', 'session_status', 'session_wall_seconds')},
            'candidates': rows, 'api_attempts': sum(r['api_attempts'] for r in rows), 'session_status': status,
            'initial_session': {'path': str(STOPPED_POOL.relative_to(PROJECT)), 'sha256': file_hash(STOPPED_POOL)},
            'initial_controller_failure_preserved': pool['failure'], 'continuation_runner_sha256': file_hash(Path(__file__)),
            'initial_session_wall_seconds': pool['session_wall_seconds'], 'continuation_wall_seconds': perf_counter()-started,
            'session_wall_seconds': pool['session_wall_seconds']+perf_counter()-started,
            'failure': failure, 'resumed_requests_retried': 0, 'historical_prefix_outcome_modified': False})
    save('generating_remaining_first_attempts')
    for index in range(2, 9):
        cid = 8+index; target = directory/f'candidate_{cid:03d}'; target.mkdir(exist_ok=True)
        try:
            prompt = database.get_prompt(); payload = gate['payloads'][index-1]
            if messages_for(prompt, {**feedback, 'selected_next_island_id': int(prompt.island_id)}) != payload['messages']:
                raise PermissionError('Actual upstream sequence differs before dispatch')
            cfg = replace(fixed_config(), seed=549199020+index)
            if {k: v for k, v in asdict(cfg).items() if k != 'seed'} != budget.plan['generation_settings']:
                raise PermissionError('Frozen generation settings changed')
            metadata = OllamaAdapter(cfg, log).model_metadata()
            ready = preload(target/'service_preload', expected_context=32768)
            if ready['api_version']['version'] != metadata['ollama_version']:
                raise PermissionError('Service version changed during readiness')
            write(target/'controller_context.json', {'runner_sha256': file_hash(Path(__file__)),
                'consumed_prefix_retried': False, 'receipt_verification_rng_neutral': True})
            row, hard_stop = generate_once(budget, index, payload, prompt, database, target, cfg, metadata, ready, bundle_file)
            rows.append(row); save('generating_remaining_first_attempts')
            print(f"Wave 2 {index}/8 seed {cfg.seed}: {row['status']} ({row['generation_seconds']:.3f}s)", flush=True)
            if hard_stop:
                failure = {'stage': 'generation', 'candidate_id': cid, 'reason': row.get('failure_reason')}; break
        except Exception as exc:
            failure = {'stage': 'pre_dispatch_or_controller', 'candidate_id': cid,
                'error_type': type(exc).__name__, 'reason': str(exc)}
            write(directory/'continuation_stopped.json', failure); break
    write(directory/'database_after_wave2_continuation.json', snapshot(database))
    save('wave_complete' if len(rows) == 8 and not failure else 'stopped_without_retry')
    print(str(output), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--approval', type=Path, required=True)
    main(parser.parse_args())
