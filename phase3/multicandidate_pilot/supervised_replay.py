"""Read-only arm/block barriers around the unchanged sealed batch entry point.

Adds receipt/history/cleanup checks, never tasks, score changes or retries.
All reconstruction is AST/database manipulation; candidate code runs only in
the original authorized disposable workers.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from time import perf_counter
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap3
from bootstrap3 import ROOT
from common import read, write, file_hash
from database_state import restore, snapshot
from implementation import evaluator, code_manipulation as cm
from trusted_cases import SPECIFICATION
from static_policy import validate
from replay import accepted_full
from candidate_runner import verify_candidate_config
from two_wave_guards import project_file, same_database
from run_wave2_remaining import rng_neutral
from final_stream import MANIFEST, POOL, WAVE1
import final_replay


def inspect_arm(authority, runner, pool, block, label, directory, summary):
    started = perf_counter(); database = restore(read(project_file(pool['replay_checkpoint'])))
    first = read(WAVE1.parent/'candidate_001/request.json')['database_prompt']
    tasks = []; counts = []; expected_slots = authority.manifest['dispatch_slots']
    for index, source in enumerate(pool['candidates']):
        cid = source['candidate_id']; row = read(directory/f'candidate_{cid:03d}.json')
        saved_prompt = read(directory/f'prompt_{cid:03d}.json')
        prompt = first if not index else None
        if index:
            actual = database.get_prompt(); prompt = {'code': actual.code, 'island_id': int(actual.island_id),
                                                     'version_generated': actual.version_generated}
        if any(saved_prompt[k] != v for k, v in prompt.items()): raise RuntimeError('Controller/RNG prompt inconsistency')
        if (row['candidate_id'] != cid or row['source_sha256'] != source['source_sha256']
                or row['island_id'] != prompt['island_id'] or row['version_generated'] != prompt['version_generated']
                or not same_database(snapshot(database), read(directory/f'database_before_{cid:03d}.json'))):
            raise RuntimeError('Candidate order, source or cross-arm initial/history state differs')
        slots = [s for s in expected_slots if s['configuration'] == f'block{block}/{label}' and s['candidate_id'] == cid]
        full = None
        for slot in slots:
            root = authority.root/slot['slot_id']
            if not root.exists(): continue
            dispatch = read(root/'dispatch.json'); worker = read(root/'result.json')
            if dispatch['scope'] != {k: v for k, v in slot.items() if k != 'slot_id'}:
                raise RuntimeError('Authority/task scope differs')
            final_replay.confirmed_terminal(worker)
            verify_candidate_config(worker['inspected_configuration'], slot['image'])
            parsed, _ = validate(source['source'], source['expected_name'], source['finish_reason'])
            body = cm.rename_function_calls(parsed.body, parsed.function_name, 'priority')
            if hashlib.sha256(body.encode()).hexdigest() != worker['body_sha256']:
                raise RuntimeError('Worker source body differs')
            if slot['action'] == 'full': full = worker
            tasks.append(worker)
        if row['registered']:
            if full is None or not accepted_full(full, runner.data['development']):
                raise RuntimeError('Registration lacks complete actual full receipt')
            if row['scores_per_group'] != full['result']['scores_per_group'] or row['score'] != full['result']['score']:
                raise RuntimeError('Fitness differs from worker')
            function, program = evaluator._sample_to_program(row['parsed_body'], row['version_generated'],
                cm.text_to_program(SPECIFICATION), 'priority')
            if program != row['evaluation']['program']: raise RuntimeError('Registered program differs')
            before = [i._num_programs for i in database._islands]
            database.register_program(function, prompt['island_id'], row['scores_per_group'])
            expected = before.copy(); expected[prompt['island_id']] += 1
            if [i._num_programs for i in database._islands] != expected:
                raise RuntimeError('Registration/island isolation differs')
        elif row['status'].startswith('skipped_') and full is not None:
            raise RuntimeError('Skipped candidate unexpectedly full-evaluated')
        if not same_database(snapshot(database), read(directory/f'database_after_{cid:03d}.json')):
            raise RuntimeError('Replay DB not reconstructed from only its own accepted outcomes')
        counts.append([i._num_programs for i in database._islands])
    if not same_database(snapshot(database), read(directory/'database_final.json')):
        raise RuntimeError('Final per-arm database mismatch')
    actual_statuses = [read(directory/f'candidate_{i:03d}.json')['status'] for i in range(1, 17)]
    if summary['candidates'] != 16 or len(tasks) != summary['full_dispatches']+summary['fingerprint_dispatches']:
        raise RuntimeError('Missing/extra terminal task receipt')
    if block == 2:
        previous = read(directory.parent.parent/'block1'/label/'summary.json')
        if previous['logical_trace_sha256'] != summary['logical_trace_sha256']:
            raise RuntimeError('Timing-block logical trajectory mismatch: stop immediately')
    result = {'status': 'PASS', 'block': block, 'configuration': label, 'candidate_order': list(range(1, 17)),
        'terminal_worker_receipts': len(tasks), 'registrations': summary['registrations'],
        'own_database_history_reconstructed': True, 'initial_checkpoint_unchanged': True,
        'source_hashes_verified': True, 'logical_repeat_verified': block == 2,
        'verification_seconds_outside_normal_timing': perf_counter()-started,
        'controller_sha256': file_hash(Path(__file__))}
    write(directory/'supervisor_verification.json', result)
    return tasks


def main(args):
    if read(args.approval).get('supervised_controller_sha256') != file_hash(Path(__file__)):
        raise PermissionError('Supervisor controller differs from pre-dispatch approval record')
    original = final_replay.normal_arm; block_tasks = {1: [], 2: []}

    def checked_arm(authority, runner, pool, block, label, root):
        directory, summary = original(authority, runner, pool, block, label, root)
        tasks = rng_neutral(inspect_arm, authority, runner, pool, block, label, directory, summary)
        block_tasks[block] += tasks
        order = authority.manifest['normal_mode_orders'][block-1]
        if label == order[-1]:
            names = {r['container_name'] for r in block_tasks[block]}
            current = set(subprocess.run([shutil.which('docker'), 'ps', '--all', '--format', '{{.Names}}'],
                check=True, capture_output=True, text=True, timeout=20).stdout.splitlines())
            if names & current: raise RuntimeError('Block cleanup uncertainty: stop')
            write(root/f'block{block}_barrier.json', {'status': 'PASS', 'block': block,
                'arms_verified': order, 'worker_names_remaining': [], 'terminal_receipts': len(names),
                'database_isolation_and_source_order_verified': True, 'next_block_or_audit_may_proceed': True})
            print(f'Block {block} barrier PASS: receipt/history/authority/cleanup checks complete', flush=True)
        return directory, summary

    final_replay.normal_arm = checked_arm
    final_replay.main(args)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--approval', type=Path, required=True)
    main(parser.parse_args())
