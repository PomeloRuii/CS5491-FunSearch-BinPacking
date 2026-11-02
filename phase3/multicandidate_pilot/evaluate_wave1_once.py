"""One separately approved finite intermediate batch; never runs generation.

No receipt means no worker construction. Existing dispatch state is never reset.
"""
import argparse
from pathlib import Path
import sys
from time import perf_counter
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap3
from bootstrap3 import ROOT, PROJECT
from common import read, write, file_hash, stamp
from approval import ExecutionAuthority, durable_reservation
from backend_policy_v2 import checked_runner
from database_state import restore, snapshot
from generation3 import load_candidate
from replay3 import ScopedReplay
from replay import accepted_full
from implementation.programs_database import Prompt
from run_log import RunLog
from wave1_artifacts import MANIFEST, REQUEST, REQUEST_SHA, ref, verify_manifest
from two_wave_guards import project_file, feedback_condition


def main(args):
    manifest = verify_manifest()
    authority = ExecutionAuthority(MANIFEST, args.approval)
    if not manifest['candidates']: raise PermissionError('No eligible sources')
    if any(authority.root.iterdir()):
        raise PermissionError('Existing batch reservation/dispatch state: inspect, never reset or retry')
    # This check inspects the existing pinned image and Docker engine, no test task.
    runner = checked_runner('development', authority)
    output = MANIFEST.parent/'learning_runs'/stamp(); output.mkdir(parents=True)
    durable_reservation(authority.root/'batch_reserved.json', {'manifest_sha256': authority.hash,
        'output': str(output), 'one_use': True, 'wave2_dispatch': False})
    log = RunLog(output/'events'); started = perf_counter()
    log.manifest(phase='wave1_real_intermediate_learning', manifest_sha256=authority.hash,
                 maximum_dispatches=len(manifest['dispatch_slots']), generation_requests=0)
    pool_file = Path(manifest['candidate_pool']); pool = read(pool_file)
    replay = ScopedReplay(runner, 'standard', 16, 'separate', log)
    start = project_file(manifest['pilot_database_start'])
    replay.database = restore(read(start)); replay.best = max(replay.database._best_score_per_island)
    replay.final = replay.best
    write(output/'pilot_database_start.json', snapshot(replay.database))
    bundle = {'generation_request_sha256': REQUEST_SHA, 'wave': 1, 'wave1_pool': ref(pool_file),
        'execution_manifest': ref(MANIFEST), 'execution_approval': ref(args.approval),
        'pilot_database_start': ref(output/'pilot_database_start.json'), 'evaluations': []}
    try:
        for slot in manifest['dispatch_slots']:
            cid = slot['candidate_id']; row = next(r for r in pool['candidates'] if r['candidate_id'] == cid)
            directory = output/f'candidate_{cid:03d}'; directory.mkdir()
            write(directory/'database_before.json', snapshot(replay.database))
            saved = read(pool_file.parent/f'candidate_{cid:03d}/request.json')['database_prompt']
            prompt = Prompt(saved['code'], saved['version_generated'], saved['island_id'])
            authority.set_context('pilot_evolution_wave1', 'evolution', cid)
            replay.counts['candidates'] += 1
            result = replay.process(load_candidate(pool_file, row), prompt, cid)
            write(directory/'candidate_result.json', result)
            worker_path = authority.root/slot['slot_id']/'result.json'
            worker = read(worker_path)
            if not worker.get('cleanup_verified'): raise RuntimeError('Cleanup unverified; stop')
            event = {'candidate_id': cid,
                'raw_generation_response': ref(pool_file.parent/f'candidate_{cid:03d}/raw_http_response.bin'),
                'candidate_result': ref(directory/'candidate_result.json'),
                'database_before': ref(directory/'database_before.json'), 'worker_result': ref(worker_path)}
            if result['status'] == 'evaluated':
                if (not accepted_full(worker, replay.groups) or not result['registered']
                        or result['score'] != worker['result']['score']
                        or result['scores_per_group'] != worker['result']['scores_per_group']):
                    raise RuntimeError('Incomplete/mismatched fitness or registration; stop')
                following = replay.database.get_prompt()
                write(directory/'next_prompt.json', {'code': following.code,
                    'island_id': int(following.island_id), 'version_generated': following.version_generated,
                    'registration_verified': True, 'evaluation_receipt_sha256': file_hash(directory/'candidate_result.json')})
                event['next_prompt'] = ref(directory/'next_prompt.json')
            elif result.get('registered') or accepted_full(worker, replay.groups):
                raise RuntimeError('Inconsistent rejection/registration; stop')
            write(directory/'database_after.json', snapshot(replay.database))
            event['database_after'] = ref(directory/'database_after.json')
            bundle['evaluations'].append(event)
            write(output/'partial_evidence.json', bundle)
            print(f"Candidate {cid}: {result['status']}; score {result['score']}; cleanup verified", flush=True)
        write(output/'pilot_database_after.json', snapshot(replay.database))
        bundle['pilot_database_after'] = ref(output/'pilot_database_after.json')
        write(output/'wave1_feedback_bundle.json', bundle)
        try:
            gate = feedback_condition(read(REQUEST), REQUEST_SHA, output/'wave1_feedback_bundle.json')
        except PermissionError as exc:
            log.finish('wave2_blocked_no_generation', reason=str(exc), seconds=perf_counter()-started)
            raise
        write(output/'feedback_verification.json', {'status': 'PASS',
            **{k: v for k, v in gate.items() if k != 'payloads'}, 'wave2_dispatched': False,
            'seconds': perf_counter()-started})
        log.finish('batch_complete_feedback_verified_no_generation', seconds=perf_counter()-started)
        print(str(output), flush=True)
    except Exception as exc:
        write(output/'stopped_without_retry.json', {'error_type': type(exc).__name__, 'reason': str(exc),
            'no_retry': True, 'wave2_dispatched': False})
        log.finish('stopped_no_retry_no_generation', error=str(exc)); raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--approval', type=Path, required=True)
    main(parser.parse_args())
