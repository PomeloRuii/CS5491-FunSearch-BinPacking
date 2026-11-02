"""Finite two-block five-arm replay plus independent all-skip audits.

No execution without a NEW exact final-pool user receipt. Never calls Ollama.
"""
import argparse
from collections import Counter
from pathlib import Path
import sys
from time import perf_counter
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap3
from bootstrap3 import ROOT, PROJECT
from common import read, write, file_hash, digest, stamp
from approval import ExecutionAuthority, durable_reservation
from backend_policy_v2 import checked_runner
from database_state import restore, snapshot
from generation3 import load_candidate
from static_policy import validate
from replay3 import ScopedReplay
from replay import accepted_full, accepted_fingerprint
from implementation.programs_database import Prompt
from run_log import RunLog
from two_wave_guards import project_file
from final_stream import MANIFEST, POOL, PROTOCOL, WAVE1, HERE, verify_manifest, ref


def confirmed_terminal(record):
    if not record.get('cleanup_verified'):
        raise RuntimeError('Cleanup uncertain: stop, no retry')
    if record['status'] == 'ok': return
    if record['status'] == 'runtime_error' and any(m.get('kind') == 'error' for m in record.get('worker_messages', [])):
        return
    if record['status'] in ('timeout', 'oom_killed', 'output_limit') and record.get('container_state'):
        return
    raise RuntimeError('Controller/protocol/dispatch state uncertain: stop, no retry')


def normal_arm(authority, runner, pool, block, label, root):
    started = perf_counter(); directory = root/f'block{block}'/label; directory.mkdir(parents=True)
    size = int(label.split('-')[1]) if label.startswith('behavioral-') else 16
    mode = 'behavioral' if label.startswith('behavioral-') else label
    log = RunLog(directory/'events')
    replay = ScopedReplay(runner, mode, size, 'separate', log)
    replay.database = restore(read(project_file(pool['replay_checkpoint'])))
    replay.best = max(replay.database._best_score_per_island); replay.final = replay.best
    first = read(WAVE1.parent/'candidate_001/request.json')['database_prompt']
    for index, source in enumerate(pool['candidates']):
        cid = source['candidate_id']; candidate_start = perf_counter()
        prompt = (Prompt(first['code'], first['version_generated'], first['island_id']) if not index
                  else replay.database.get_prompt())
        write(directory/f'prompt_{cid:03d}.json', {'code': prompt.code, 'island_id': int(prompt.island_id),
            'version_generated': prompt.version_generated, 'generation_metadata_unchanged': True})
        write(directory/f'database_before_{cid:03d}.json', snapshot(replay.database))
        authority.set_context(f'block{block}/{label}', 'normal', cid)
        replay.counts['candidates'] += 1; task_start = len(replay.executions)
        row = replay.process(load_candidate(POOL, source), prompt, cid)
        row['complete_candidate_seconds_including_prompt_logging'] = perf_counter()-candidate_start
        write(directory/f'candidate_{cid:03d}.json', row)
        for record in replay.executions[task_start:]: confirmed_terminal(record)
        if row['status'] == 'blocked_generated_execution': raise PermissionError('Unexpected source/task approval block')
        write(directory/f'database_after_{cid:03d}.json', snapshot(replay.database))
    write(directory/'representatives.json', replay.reps.all)
    write(directory/'database_final.json', snapshot(replay.database))
    statuses = Counter(r['status'] for r in replay.records)
    full = [r for r in replay.executions if r['action'] == 'full']
    fp = [r for r in replay.executions if r['action'] == 'fingerprint']
    valid = [r for r in replay.records if r['registered']]
    best_new = max(valid, key=lambda r: r['score']) if valid else None
    trace = [{k: row.get(k) for k in ('candidate_id', 'status', 'score', 'scores_per_group',
              'matched_representative_id', 'registered', 'island_id', 'version_generated', 'fingerprint')}
             for row in replay.records]
    summary = {'block': block, 'configuration': label, 'candidates': len(replay.records),
        'statuses': dict(statuses), 'full_dispatches': len(full),
        'full_started': sum(r.get('full_evaluation_started', False) for r in full),
        'full_completed': sum(accepted_full(r, replay.groups) for r in full),
        'full_avoided_by_match': statuses['skipped_exact']+statuses['skipped_behavioral'],
        'exact_matches': statuses['skipped_exact'], 'behavioral_matches': statuses['skipped_behavioral'],
        'registrations': len(valid), 'representatives': len(replay.reps.all),
        'fingerprint_dispatches': len(fp), 'fingerprint_pure_seconds': sum(r.get('fingerprint_phase_seconds', 0) for r in fp),
        'fingerprint_lifecycle_seconds': sum(r['total_seconds'] for r in fp),
        'full_pure_seconds_completed': sum(r.get('result', {}).get('pure_evaluate_seconds', 0) for r in full),
        'full_pure_seconds_missing_for_failed_tasks': sum('pure_evaluate_seconds' not in r.get('result', {}) for r in full),
        'full_lifecycle_seconds': sum(r['total_seconds'] for r in full),
        'container_create_seconds': sum(r.get('create_seconds', 0) for r in replay.executions),
        'worker_ready_seconds': sum(r.get('worker_ready_seconds', 0) for r in replay.executions),
        'container_cleanup_seconds': sum(r.get('cleanup_seconds', 0) for r in replay.executions),
        'host_filter_seconds': sum(r['filter_seconds'] for r in replay.records),
        'best_new_fitness': best_new['score'] if best_new else None,
        'best_new_mean_bins': {k: -v for k, v in best_new['scores_per_group'].items()} if best_new else None,
        'best_database_fitness': replay.best, 'last_accepted_fitness': replay.final,
        'normal_wall_seconds': perf_counter()-started, 'logical_trace_sha256': digest(trace),
        'llm_calls': 0, 'pilot_fitness_imported': False, 'initial_representative_cache_size': 0}
    write(directory/'summary.json', summary); write(directory/'trajectory.json', trace)
    log.finish('completed', **summary)
    return directory, summary


def audit_all(authority, development, reserved, pool, normal_runs, output):
    start = perf_counter(); cache = {}; comparisons = []; tasks = []
    by_id = {r['candidate_id']: r for r in pool['candidates']}
    expected = [s['state_id'] for s in read(ROOT/'build_contexts/audit/states.json')['audit']]
    before = {p: file_hash(p) for directory, summary in normal_runs for p in directory.rglob('*') if p.is_file()}

    def independent(size, cid, kind):
        key = (size, cid, kind)
        if key in cache: return cache[key]
        source = by_id[cid]; candidate = load_candidate(POOL, source)
        parsed, _ = validate(candidate.text, source['expected_name'], source['finish_reason'])
        role = 'audit_candidate' if kind == 'full' else 'audit_vector'
        authority.set_context(f'behavioral-{size}', role, cid)
        runner = development if kind == 'full' else reserved
        record = runner.run_task(candidate, parsed, 'full' if kind == 'full' else 'fingerprint',
            **({} if kind == 'full' else {'dataset': 'audit', 'size': 256, 'state_set': 'audit'}))
        confirmed_terminal(record)
        path = output/f'audit_{size}_{cid:03d}_{kind}.json'; write(path, record)
        cache[key] = (record, ref(path)); tasks.append((kind, record))
        return cache[key]

    for directory, summary in normal_runs:
        if not summary['configuration'].startswith('behavioral-'): continue
        size = int(summary['configuration'].split('-')[1])
        rows = [read(p) for p in sorted(directory.glob('candidate_*.json'))]
        by_normal_id = {r['candidate_id']: r for r in rows}
        for row in rows:
            if row['status'] != 'skipped_behavioral': continue
            cid, rep = row['candidate_id'], row['matched_representative_id']
            full, full_ref = independent(size, cid, 'full')
            vector, vector_ref = independent(size, cid, 'vector')
            rep_vector, rep_ref = independent(size, rep, 'vector')
            full_ok = accepted_full(full, development.data['development'])
            vectors_ok = (accepted_fingerprint(vector, 256, expected) and accepted_fingerprint(rep_vector, 256, expected))
            disagreements = sum(a != b for a, b in zip(vector['result']['decisions'], rep_vector['result']['decisions'])) if vectors_ok else None
            measured = full['result'] if full_ok else None
            comparisons.append({'block': summary['block'], 'configuration': summary['configuration'],
                'candidate_id': cid, 'representative_id': rep, 'full_valid': full_ok, 'vectors_valid': vectors_ok,
                'outside_state_count': 256, 'outside_disagreements': disagreements,
                'audit_score': measured['score'] if measured else None,
                'different_score': measured['score'] != by_normal_id[rep]['score'] if measured else None,
                'different_group_scores': measured['scores_per_group'] != by_normal_id[rep]['scores_per_group'] if measured else None,
                'best_at_skip': row['best_before'],
                'missed_improvement': measured['score'] > row['best_before'] if measured else None,
                'audit_full_receipt': full_ref, 'candidate_vector_receipt': vector_ref,
                'representative_vector_receipt': rep_ref, 'registered_in_replay': False})
    if any(file_hash(p) != sha for p, sha in before.items()):
        raise RuntimeError('Independent audit modified normal trajectory artifacts')
    result = {'every_behavioral_skip': comparisons, 'comparisons': len(comparisons),
        'independent_full_evaluations': sum(k == 'full' for k, _ in tasks),
        'independent_reserved_vectors': sum(k == 'vector' for k, _ in tasks),
        'audit_lifecycle_seconds': sum(r['total_seconds'] for _, r in tasks),
        'audit_pure_full_seconds_completed': sum(r.get('result', {}).get('pure_evaluate_seconds', 0) for k, r in tasks if k == 'full'),
        'audit_fingerprint_seconds': sum(r.get('fingerprint_phase_seconds', 0) for k, r in tasks if k == 'vector'),
        'audit_wall_seconds': perf_counter()-start, 'original_trajectory_unchanged': True,
        'serial_workers': True, 'final_heldout_used': False}
    write(output/'audit_summary.json', result)
    return result


def main(args):
    manifest, pool = verify_manifest()
    authority = ExecutionAuthority(MANIFEST, args.approval)
    if any(authority.root.iterdir()): raise PermissionError('Existing replay state: inspect, no reset or retry')
    dev = checked_runner('development', authority); reserved = checked_runner('audit', authority)
    output = HERE/'comparisons'/stamp(); output.mkdir(parents=True)
    durable_reservation(authority.root/'comparison_reserved.json', {'output': str(output), 'manifest_sha256': authority.hash, 'one_use': True})
    write(output/'scope.json', {'manifest_sha256': authority.hash, 'pool_sha256': file_hash(POOL), 'generation_calls': 0})
    runs = []; started = perf_counter()
    try:
        for block, order in enumerate(read(PROTOCOL)['mode_orders'], 1):
            for label in order:
                directory, result = normal_arm(authority, dev, pool, block, label, output)
                runs.append((directory, result)); print(f"Block {block} {label}: {result['full_completed']} complete, {result['normal_wall_seconds']:.3f}s", flush=True)
        for label in read(PROTOCOL)['comparison_modes']:
            pair = [s for _, s in runs if s['configuration'] == label]
            if pair[0]['logical_trace_sha256'] != pair[1]['logical_trace_sha256']:
                raise RuntimeError('Timing-block logical traces differ: preserve evidence, stop before audits')
        audit = audit_all(authority, dev, reserved, pool, runs, output)
        write(output/'summary.json', {'status': 'completed', 'runs': [s for _, s in runs],
            'audit': audit, 'comparison_wall_seconds': perf_counter()-started, 'generation_requests': 0})
        print(str(output))
    except Exception as exc:
        write(output/'stopped_without_retry.json', {'error_type': type(exc).__name__, 'reason': str(exc),
            'completed_runs': [s for _, s in runs], 'no_retry': True}); raise


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--approval', type=Path, required=True)
    main(p.parse_args())
