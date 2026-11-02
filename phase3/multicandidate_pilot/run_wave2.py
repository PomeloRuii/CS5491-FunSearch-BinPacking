"""Conditional generation-only second wave, using actual intermediate receipts.

Uses the same frozen transport, sampler, preload and AST policy as Wave 1.
No worker is created and no generated program is executed by this entry point.
"""
import argparse
from dataclasses import asdict, replace
import hashlib
import json
from pathlib import Path
import shutil
import sys
from time import perf_counter
from urllib import request, error
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap3
from bootstrap3 import ROOT, PROJECT
from common import read, write, append, file_hash, digest, stamp
from approval import durable_reservation
from generation3 import fixed_config, EventLog
from generation_policy_v3 import messages_for, POLICY_PATH
from interface import expected_name
from static_policy import validate
from ollama_adapter import OllamaAdapter, NoRedirect, MAX_RESPONSE_BYTES
from ollama_readiness import preload
from database_state import restore, snapshot
from implementation.programs_database import Prompt
from two_wave_guards import TwoWaveBudget, feedback_condition, project_file
from wave1_artifacts import HERE, REQUEST, REQUEST_SHA


def generate_once(budget, index, payload, prompt, database, directory, cfg, metadata, ready, bundle_file):
    cid = 8+index
    checkpoint = directory.parent/f'database_before_{cid:03d}.json'
    write(checkpoint, snapshot(database))
    if ready['status'] != 'PASS' or ready['resident_model']['context_length'] != 32768:
        raise PermissionError('Fresh GPU/model/context readiness required before reservation')
    slot, reservation = budget.reserve(2, index, payload, wave1_feedback_bundle=bundle_file)
    write(directory/'request.json', {'payload': payload, 'reservation': reservation,
        'generation_request_sha256': budget.hash, 'generation_settings': asdict(cfg),
        'database_prompt': {'code': prompt.code, 'island_id': int(prompt.island_id),
                            'version_generated': prompt.version_generated},
        'database_checkpoint_sha256': file_hash(checkpoint), 'model_metadata': metadata,
        'service_readiness_sha256': file_hash(directory/'service_preload/readiness.json'),
        'verified_feedback_bundle_sha256': file_hash(bundle_file),
        'generation_policy_sha256': file_hash(POLICY_PATH), 'runner_sha256': file_hash(Path(__file__)),
        'generation_policy': 'obp-objective-alternatives-distinct-seeds-v3',
        'generation_payload_sha256': digest(payload), 'candidate_execution_authorized': False})
    row = {'candidate_id': cid, 'wave': 2, 'index_in_wave': index, 'origin': 'ollama',
        'model': cfg.model, 'digest': cfg.expected_digest, 'quantization': cfg.expected_quantization,
        'sampling_seed': cfg.seed, 'island_id': int(prompt.island_id),
        'version_generated': prompt.version_generated, 'expected_name': expected_name(prompt),
        'prompt_sha256': digest(payload['messages']), 'database_checkpoint_sha256': file_hash(checkpoint),
        'observed_fitness': None, 'executed': False, 'source_sha256': None, 'api_attempts': 0,
        'status': 'request_failed', 'http_status': None, 'allocation_call_slot': reservation['call_slot']}
    started = perf_counter(); hard_stop = False
    try:
        req = request.Request(cfg.base_url+'/chat/completions',
            data=json.dumps(payload, ensure_ascii=False, allow_nan=False).encode(),
            headers={'Content-Type': 'application/json'})
        opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
        write(slot/'transport_attempt_started.json', {'candidate_id': cid, 'wave': 2,
            'timestamp': stamp(), 'payload_sha256': digest(payload), 'sampling_seed': cfg.seed})
        row['api_attempts'] = 1
        try:
            with opener.open(req, timeout=cfg.request_timeout_seconds) as response:
                raw = response.read(MAX_RESPONSE_BYTES+1); row['http_status'] = response.status
        except error.HTTPError as exc:
            raw = exc.read(MAX_RESPONSE_BYTES+1); row['http_status'] = exc.code
            (directory/'raw_http_response.bin').write_bytes(raw)
            row.update(raw_response_sha256=hashlib.sha256(raw).hexdigest(),
                delivery_status='server_error_response_received', failure_type=type(exc).__name__, failure_reason=str(exc))
            return row, False
        (directory/'raw_http_response.bin').write_bytes(raw)
        row.update(raw_response_sha256=hashlib.sha256(raw).hexdigest(), delivery_status='response_received')
        if len(raw) > MAX_RESPONSE_BYTES: raise ValueError('Response exceeds bounded 1 MiB retention policy')
        value = json.loads(raw); write(directory/'response.json', value)
        if isinstance(value, dict):
            row.update(response_id=value.get('id'), response_model=value.get('model'), usage=value.get('usage'))
            choices = value.get('choices')
            if isinstance(choices, list) and len(choices) == 1 and isinstance(choices[0], dict):
                choice = choices[0]; message = choice.get('message'); row['finish_reason'] = choice.get('finish_reason')
                if isinstance(message, dict) and isinstance(message.get('content'), str):
                    source = message['content']; (directory/'source.py.txt').write_bytes(source.encode())
                    row.update(source=source, source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                        source_file=str((directory/'source.py.txt').relative_to(directory.parent)))
        if not isinstance(value, dict) or value.get('model') != cfg.model:
            raise ValueError('Response model identity differs')
        choices = value.get('choices')
        if not isinstance(choices, list) or len(choices) != 1:
            raise ValueError('Exactly one response per actual request required')
        message = choices[0].get('message')
        if not isinstance(message, dict) or message.get('tool_calls') or message.get('function_call'):
            raise ValueError('Unsupported response/tool-call structure')
        if 'source' not in row: raise ValueError('Missing candidate text')
        try:
            parsed, static = validate(row['source'], row['expected_name'], row['finish_reason'])
            row.update(status='static_valid_pending_execution_approval', static=static,
                parsed_body_sha256=hashlib.sha256(parsed.body.encode()).hexdigest())
        except (ValueError, SyntaxError) as exc:
            row.update(status='static_rejected', static={'status': 'FAIL'}, failure_reason=str(exc))
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError, PermissionError) as exc:
        row.update(status='request_failed' if row.get('http_status') is None else 'protocol_rejected',
            failure_type=type(exc).__name__, failure_reason=str(exc))
        row.setdefault('delivery_status', 'uncertain_transport_or_dispatch'); hard_stop = True
    finally:
        row['generation_seconds'] = perf_counter()-started; row['session_hard_stop'] = hard_stop
        write(directory/'candidate.json', row); write(slot/'outcome.json', row)
        append(directory.parent/'artifact_ledger.jsonl', row)
    return row, hard_stop


def main(args):
    if file_hash(REQUEST) != REQUEST_SHA: raise PermissionError('Sealed two-wave request changed')
    budget = TwoWaveBudget(REQUEST, args.approval)
    if (budget.root/'wave2_session_reserved.json').exists() or any((budget.root/f'call_{i:03d}').exists() for i in range(9, 17)):
        raise PermissionError('Existing Wave-2 session/dispatch: inspect, never reset or retry')
    bundle_file = args.feedback_bundle.resolve()
    gate = feedback_condition(budget.plan, budget.hash, bundle_file)
    bundle = read(bundle_file)
    last = next(event for event in reversed(bundle['evaluations']) if event.get('next_prompt'))
    latest = read(project_file(last['candidate_result'])); saved = read(project_file(last['next_prompt']))
    prompt = Prompt(saved['code'], saved['version_generated'], saved['island_id'])
    database = restore(read(project_file(bundle['pilot_database_after'])))
    feedback = {'verified_real_model_feedback': True, 'candidate_id': latest['candidate_id'],
        'source_sha256': latest['source_sha256'], 'evaluated_island_id': latest['island_id'],
        'score': latest['score'], 'scores_per_group': latest['scores_per_group'],
        'feedback_receipt_sha256': file_hash(project_file(last['candidate_result']))}
    durable_reservation(budget.root/'wave2_session_reserved.json', {'wave': 2,
        'feedback_bundle_sha256': file_hash(bundle_file), 'generation_request_sha256': budget.hash,
        'candidate_execution_authorized': False, 'started': stamp()})
    output = HERE/'sessions'/stamp()/'wave2'; output.mkdir(parents=True)
    log = EventLog(output/'events.jsonl'); rows = []; failure = None; started = perf_counter()
    write(output/'verified_feedback_gate.json', gate)
    shutil.copyfile(project_file(bundle['pilot_database_after']), output/'pilot_database_start.json')
    shutil.copyfile(project_file(read(project_file(bundle['execution_manifest']))['original_comparison_checkpoint']),
                    output/'original_comparison_checkpoint.json')

    def save(status):
        write(output/'pool.json', {'schema': 'qwen-two-wave-wave-pool-v1', 'wave': 2,
            'generation_request_sha256': budget.hash, 'session_status': status,
            'api_attempts': sum(r['api_attempts'] for r in rows), 'candidates': rows,
            'model': budget.plan['model'], 'model_digest': budget.plan['model_digest'], 'quantization': 'Q4_K_M',
            'verified_feedback_bundle': {'path': str(bundle_file.relative_to(PROJECT)), 'sha256': file_hash(bundle_file)},
            'wave1_pool_sha256': gate['wave1_pool_sha256'], 'generated_sources_executed': 0,
            'new_registrations_during_generation': 0, 'session_wall_seconds': perf_counter()-started,
            'failure': failure, 'timing_scope': 'Generation and service readiness only; intermediate learning, replay and audit separate.'})
    save('generating')
    for index, payload in enumerate(gate['payloads'], 1):
        cid = 8+index; directory = output/f'candidate_{cid:03d}'; directory.mkdir()
        try:
            if index > 1: prompt = database.get_prompt()
            context = {**feedback, 'selected_next_island_id': int(prompt.island_id)}
            if messages_for(prompt, context) != payload['messages']:
                raise PermissionError('Actual upstream prompt/feedback differs from dependency-derived payload')
            cfg = replace(fixed_config(), seed=549199020+index)
            if {k: v for k, v in asdict(cfg).items() if k != 'seed'} != budget.plan['generation_settings']:
                raise PermissionError('Frozen non-seed settings changed')
            metadata = OllamaAdapter(cfg, log).model_metadata()
            ready = preload(directory/'service_preload', expected_context=32768)
            if ready['api_version']['version'] != metadata['ollama_version']:
                raise PermissionError('Service identity changed during readiness')
            row, hard_stop = generate_once(budget, index, payload, prompt, database, directory,
                cfg, metadata, ready, bundle_file)
            rows.append(row); save('generating')
            print(f"Wave 2 {index}/8 seed {cfg.seed}: {row['status']} ({row['generation_seconds']:.3f}s)", flush=True)
            if hard_stop:
                failure = {'stage': 'generation', 'candidate_id': cid, 'reason': row.get('failure_reason')}; break
        except Exception as exc:
            failure = {'stage': 'pre_dispatch_or_controller', 'candidate_id': cid,
                'error_type': type(exc).__name__, 'reason': str(exc)}
            write(output/'stopped.json', failure); break
    write(output/'database_after_wave2_generation.json', snapshot(database))
    save('wave_complete' if len(rows) == 8 and not failure else 'stopped_without_retry')
    print(str(output/'pool.json'), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--approval', type=Path, required=True)
    parser.add_argument('--feedback-bundle', type=Path, required=True)
    main(parser.parse_args())
