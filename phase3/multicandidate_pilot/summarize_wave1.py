"""Export measured generation costs and a static-only batch review, never execute."""
import csv
from pathlib import Path
from wave1_artifacts import POOL, MANIFEST, REQUEST, REQUEST_SHA, HERE, verify_pool, verify_manifest
from bootstrap3 import ROOT, PROJECT
from common import read, write, file_hash


def main():
    pool, analysis, selected = verify_pool(); verify_manifest()
    rows = pool['candidates']; directory = POOL.parent
    readiness = [read(directory/f'candidate_{r["candidate_id"]:03d}/service_preload/readiness.json') for r in rows]
    usage = {k: sum(r['usage'][k] for r in rows) for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')}
    old = read(HERE/'call_reconciliation.json')
    total_usage = {k: old['known_usage_all_logged_calls'][k]+usage[k] for k in usage}
    details = {
        1: '512-token truncation with repeated reciprocal powers; no repair or replacement.',
        2: 'Reciprocal positive-residual preference minus quadratic waste. Exact-fit entries score zero; behavior/fitness not measured.',
        3: 'Negative linear waste plus reciprocal residual term; zero-residual behavior differs from its positive-residual branch. Not measured.',
        4: 'Complete syntax; np.any is outside frozen v2 allowlist. Also contains a possible zero normalization denominator and -np.inf. Not executed.',
        5: 'Log item/residual ratio; an exact fit has residual_safe=0, so division/log may yield infinity. Shared finite-score checks will reject non-finite runtime results; no special exemption.',
        6: 'Complete syntax; np.any is outside frozen v2 allowlist. Not repaired or executed.',
        7: 'Complete syntax; np.any is outside frozen v2 allowlist. Uses -np.inf for masked entries. Not repaired or executed.',
        8: 'Both item-size branches increase scores with positive residual, suggesting largest-residual selection like the seed under ordinary finite inputs. Static source novelty does not imply behavioral novelty; no decision tests executed.'}
    summary = {'schema': 'actual-wave1-generation-analysis-v1', 'pool': str(POOL.relative_to(PROJECT)),
        'pool_sha256': file_hash(POOL), 'generation_request_sha256': REQUEST_SHA,
        'requests_attempted': 8, 'http_200_responses': 8, 'complete_responses': 7,
        'static_passes': 4, 'unsupported_operation_rejections': 3, 'truncated_rejections': 1,
        'retries': 0, 'replacement_calls': 0, 'unique_raw_sources': len({r['source_sha256'] for r in rows}),
        'unique_exact_keys_complete_sources': len({r['exact_key_sha256'] for r in analysis if 'exact_key_sha256' in r}),
        'unique_function_asts_complete_sources': len({r['function_ast_sha256'] for r in analysis if 'function_ast_sha256' in r}),
        'unique_actual_database_code_prompts': len({read(directory/f'candidate_{r["candidate_id"]:03d}/request.json')['database_prompt']['code'] for r in rows}),
        'unique_wrapper_message_hashes': len({r['prompt_sha256'] for r in rows}),
        'static_valid_new_exact_representatives': selected, 'duplicate_valid_candidates': 0,
        'usage': usage, 'generation_seconds': sum(r['generation_seconds'] for r in rows),
        'non_generating_preload_operations': 8, 'preload_seconds': sum(r['seconds'] for r in readiness),
        'generation_session_wall_seconds': pool['session_wall_seconds'],
        'new_full_evaluations': 0, 'new_registrations': 0, 'new_replay_seconds': 0, 'new_audit_seconds': 0,
        'fitness_observed': None, 'behavioral_diversity_measured': False,
        'known_logged_pilot_calls': 22, 'historical_connectivity_exact_count': None,
        'historical_connectivity_known_minimum': 2, 'nominal_lifetime_budget_certified': False,
        'conditional_wave2_requests_remaining': 8, 'wave2_feedback_verified': False,
        'main_requests': 0, 'execution_manifest_sha256': file_hash(MANIFEST),
        'candidate_analysis': [{**r, 'static_review': details[r['candidate_id']]} for r in analysis]}
    write(directory/'wave1_analysis.json', summary)
    reconciliation = {'schema': 'current-two-wave-pilot-ledger-v1',
        'historical_reconciliation': {'path': str((HERE/'call_reconciliation.json').relative_to(PROJECT)),
                                     'sha256': file_hash(HERE/'call_reconciliation.json')},
        'historical_known_logged_calls': 14, 'wave1_attempts': 8, 'known_logged_calls': 22,
        'known_usage_all_logged_calls': total_usage, 'calls_with_unknown_usage': old['calls_with_unknown_usage'],
        'historical_connectivity_exact_count': None, 'historical_connectivity_known_minimum': 2,
        'later_unattributed_api_chat': old['later_unattributed_api_chat'],
        'lifetime_exact_count': None, 'original_nominal_pilot_budget_certified': False,
        'new_grant_maximum': 16, 'new_grant_consumed': 8, 'new_grant_unused': 8,
        'unused_scope': 'Conditional Wave 2 only, seeds 549199021–549199028; locked pending separately authorized real Wave-1 evaluations and verified registrations/cleanup/checkpoint.',
        'service_preloads': {'operations': 8, 'candidate_generation_requests': 0},
        'main_calls': 0, 'records': old['records']+[
            {'known_logged_ordinal': 14+r['candidate_id'], 'phase': '3_two_wave_wave1',
             'generation_request_sha256': REQUEST_SHA, 'allocation_slot': r['allocation_call_slot'],
             'seed': r['sampling_seed'], 'outcome': r['status'], 'finish_reason': r['finish_reason'],
             'http_status': r['http_status'], 'usage': r['usage'], 'source_sha256': r['source_sha256'],
             'evidence': str((directory/f'candidate_{r["candidate_id"]:03d}/candidate.json').relative_to(PROJECT)),
             'evidence_sha256': file_hash(directory/f'candidate_{r["candidate_id"]:03d}/candidate.json')} for r in rows]}
    write(HERE/'wave1_call_accounting.json', reconciliation)
    with (HERE/'wave1_call_accounting.csv').open('w', encoding='utf-8', newline='') as stream:
        fields = ['known_logged_ordinal', 'phase', 'allocation_slot', 'outcome', 'finish_reason', 'http_status', 'source_sha256']
        writer = csv.DictWriter(stream, fields, extrasaction='ignore'); writer.writeheader(); writer.writerows(reconciliation['records'])
    ledger = read(ROOT/'budget_ledger.json')
    for key in ('phase3_allocation_proposed_max', 'phase3_allocation_authorized'): ledger.pop(key, None)
    ledger.update(known_pilot_requests_in_ledger=22, phase3_generation_reservations=20,
        phase3_attempts_started=20, phase3_recorded_outcomes=20,
        phase3_available_usage={k: sum((read(p).get('usage') or {}).get(k, 0)
                                     for p in (ROOT/'dispatch_state').glob('*/call_*/outcome.json')) for k in usage},
        allocations=[{'kind': 'old_twelve_slot_grant', 'maximum': 12, 'consumed': 12, 'remaining': 0},
                     {'kind': 'finite_two_wave_generation_only', 'manifest_sha256': REQUEST_SHA,
                      'maximum': 16, 'consumed': 8, 'remaining_conditional_wave2': 8, 'feedback_verified': False}],
        current_accounting=str((HERE/'wave1_call_accounting.json').relative_to(PROJECT)),
        budget_note='22 logged pilots: 2 Phase1D +12 old Phase3 +8 new Wave1. Earlier connectivity exact count unknown, at least two; unclassified chat event separate. Eight calls remain only in the conditionally authorized Wave2 scope. Even reaching 30 logged pilots would not certify the original lifetime estimate; historical tests may put it above nominal. No nominal remainder grants new calls; main540 untouched.')
    write(ROOT/'budget_ledger.json', ledger)
    lines = ['# Actual Wave-1 pool and consolidated source review', '',
        'Eight real requests, no retries/replacements. No generated source was executed. Fitness, runtime validity and sampled decisions are NOT TESTED.', '',
        '| ID | Seed | Island | Completion tokens | Outcome | Source SHA-256 |',
        '| ---: | ---: | ---: | ---: | --- | --- |']
    for r in rows:
        lines.append(f"| {r['candidate_id']} | {r['sampling_seed']} | {r['island_id']} | {r['usage']['completion_tokens']} | {r['status']} | `{r['source_sha256']}` |")
    lines += ['', f"Generation calls: {summary['generation_seconds']:.6f} s; eight empty-message preloads: {summary['preload_seconds']:.6f} s; complete session: {pool['session_wall_seconds']:.6f} s. Usage: {usage['prompt_tokens']} prompt +{usage['completion_tokens']} completion ={usage['total_tokens']} total tokens (reported by Ollama).", '',
        'All eight raw sources differ. All seven complete sources have distinct exact-source keys and function ASTs. The four static passes are new exact representatives relative to seed/FF/BF/Slot12 and one another. This does not establish different selected-bin behavior or better fitness.', '',
        'There is one actual database code prompt across this generation-only wave, and six wrapper hashes from genuine island routing. No new fitness was available between requests; the original post-Slot12 checkpoint and genuine feedback were preserved. Different scheduled sampling seeds yielded source diversity under the same objective/settings; this is not a controlled claim about the model’s general diversity.', '',
        'The frozen v2 rejection of np.any is a restricted search-domain limitation, not evidence that those complete numerical programs are hostile. It is not changed mid-batch. Markdown fencing was accepted by the existing transport parser without repairing algorithms. The target code-line count is soft, not an additional runtime acceptance rule.', '',
        '## One consolidated proposed execution scope', '',
        f"Manifest: `../../../wave1_execution_request.json`, SHA-256 `{file_hash(MANIFEST)}`.", '',
        'Approve IDs **2, 3, 5, 8** only: four disposable development-only full evaluations, once each, in generation order and original islands 2/9/1/3. No retry, fingerprint task, audit, fused worker, held-out access or extra generation is covered by this execution request. Actual complete accepted scores alone enter a separate Pilot evolution database; failures remain explicit rejections. The original comparison checkpoint remains unchanged.', '',
        'Ordinary Docker residual shared-kernel/controller/output/score-integrity/crash risks remain. Static screening cannot establish output shape, finiteness, resource cost or safety. Existing non-root/read-only/no-network/no-host-mount and CPU/memory/PID/tmpfs/deadline restrictions remain fixed. Cleanup uncertainty stops the batch.', '',
        'Wave2’s eight calls are already conditionally generation-authorized, but stay locked until actual intermediate worker/cleanup/registration and checkpoint reconstruction succeeds. This batch executable never dispatches generation. Main540 and GitHub publication remain disabled.', '',
        '## Unchanged candidate sources and static assessments', '']
    for row in rows:
        cid = row['candidate_id']
        lines += [f'### Candidate {cid}', '', details[cid], '', f"[Original source](candidate_{cid:03d}/source.py.txt); [request](candidate_{cid:03d}/request.json); [raw response](candidate_{cid:03d}/raw_http_response.bin).", '']
        if cid in selected: lines += [row['source'], '']
    (directory/'CANDIDATE_REVIEW.md').write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(__import__('json').dumps({k: v for k, v in summary.items() if k != 'candidate_analysis'}, indent=2))


if __name__ == '__main__': main()

