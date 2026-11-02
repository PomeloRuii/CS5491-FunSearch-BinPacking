"""Export actual bounded replay evidence; no candidate function execution."""
import csv
import json
from pathlib import Path
import statistics
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bootstrap3
from bootstrap3 import ROOT, PROJECT
from common import read, write, file_hash
from final_stream import HERE, POOL, MANIFEST

RUN = HERE/'comparisons/20261102T101228309130Z_0ecb4f0f'


def csv_write(path, rows):
    if not rows: return
    with Path(path).open('w', encoding='utf-8', newline='') as stream:
        writer = csv.DictWriter(stream, list(rows[0])); writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v, (dict, list)) else v for k, v in row.items()})


def main():
    experiment = read(RUN/'summary.json')
    if experiment['status'] != 'completed': raise PermissionError('Only actual completed campaign evidence')
    runs = experiment['runs']; audit = experiment['audit']; summary = []; candidates = []
    for config in ('standard', 'exact', 'behavioral-16', 'behavioral-64', 'behavioral-128'):
        pair = sorted([r for r in runs if r['configuration'] == config], key=lambda r: r['block'])
        if len(pair) != 2 or pair[0]['logical_trace_sha256'] != pair[1]['logical_trace_sha256']:
            raise RuntimeError('Non-identical two-block logical trajectory')
        first = pair[0]; walls = [r['normal_wall_seconds'] for r in pair]
        exact = [next(r for r in runs if r['block'] == b and r['configuration'] == 'exact') for b in (1, 2)]
        row = {'configuration': config, 'timing_blocks': 2, 'candidates_per_block': 16,
            'static_rejections_per_block': first['statuses'].get('static_rejected', 0),
            'runtime_rejections_per_block': first['statuses'].get('runtime_rejected', 0),
            'full_attempted_per_block': first['full_dispatches'], 'full_completed_per_block': first['full_completed'],
            'full_rejected_per_block': first['full_dispatches']-first['full_completed'],
            'exact_matches_per_block': first['exact_matches'], 'behavioral_matches_per_block': first['behavioral_matches'],
            'full_match_avoided_per_block': first['full_avoided_by_match'],
            'registrations_per_block': first['registrations'], 'representatives_per_block': first['representatives'],
            'fingerprint_tasks_per_block': first['fingerprint_dispatches'],
            'wall_block1_seconds': walls[0], 'wall_block2_seconds': walls[1], 'wall_mean_seconds': statistics.mean(walls),
            'wall_sample_sd_seconds': statistics.stdev(walls), 'wall_min_seconds': min(walls), 'wall_max_seconds': max(walls),
            'fingerprint_pure_mean_seconds': statistics.mean(r['fingerprint_pure_seconds'] for r in pair),
            'fingerprint_lifecycle_mean_seconds': statistics.mean(r['fingerprint_lifecycle_seconds'] for r in pair),
            'full_pure_successful_mean_seconds': statistics.mean(r['full_pure_seconds_completed'] for r in pair),
            'failed_full_pure_measurements_missing_per_block': first['full_pure_seconds_missing_for_failed_tasks'],
            'full_lifecycle_mean_seconds': statistics.mean(r['full_lifecycle_seconds'] for r in pair),
            'host_filter_mean_seconds': statistics.mean(r['host_filter_seconds'] for r in pair),
            'container_create_mean_seconds': statistics.mean(r['container_create_seconds'] for r in pair),
            'worker_ready_mean_seconds': statistics.mean(r['worker_ready_seconds'] for r in pair),
            'cleanup_mean_seconds': statistics.mean(r['container_cleanup_seconds'] for r in pair),
            'wall_difference_vs_exact_mean_seconds': statistics.mean(r['normal_wall_seconds']-e['normal_wall_seconds'] for r, e in zip(pair, exact)),
            'wall_ratio_to_exact_mean': statistics.mean(walls)/statistics.mean(r['normal_wall_seconds'] for r in exact),
            'full_attempts_saved_vs_exact_per_block': exact[0]['full_dispatches']-first['full_dispatches'],
            'successful_full_saved_vs_exact_per_block': exact[0]['full_completed']-first['full_completed'],
            'additional_match_skips_vs_exact_per_block': first['full_avoided_by_match']-exact[0]['full_avoided_by_match'],
            'best_fitness': first['best_database_fitness'], 'last_accepted_fitness': first['last_accepted_fitness'],
            'best_or3_mean_bins': first['best_new_mean_bins']['OR3'], 'best_weibull_mean_bins': first['best_new_mean_bins']['Weibull 5k'],
            'logical_repeat_identical': True}
        summary.append(row)
    for run in runs:
        directory = RUN/f'block{run["block"]}'/run['configuration']
        for i in range(1, 17):
            r = read(directory/f'candidate_{i:03d}.json')
            candidates.append({'block': run['block'], 'configuration': run['configuration'], 'candidate_id': i,
                'source_sha256': r['source_sha256'], 'status': r['status'], 'score': r['score'],
                'or3_mean_bins': -(r.get('scores_per_group') or {}).get('OR3', 0) if r.get('scores_per_group') else None,
                'weibull_mean_bins': -(r.get('scores_per_group') or {}).get('Weibull 5k', 0) if r.get('scores_per_group') else None,
                'registered': r['registered'], 'representative_id': r['matched_representative_id'],
                'best_before': r['best_before'], 'best_after': r['best_after'], 'parse_seconds': r['parse_seconds'],
                'host_filter_seconds': r['filter_seconds'], 'processing_seconds': r['processing_seconds'],
                'replay_island': r['island_id'], 'replay_version': r['version_generated'],
                'generation_island': r['generation_metadata']['island_id'],
                'generation_version': r['generation_metadata']['version_generated']})
    skips = audit['every_behavioral_skip']
    # Both timing blocks reference the same independent source/N audit receipts.
    unique = {(r['configuration'], r['candidate_id'], r['representative_id']): r for r in skips}
    collisions = [r for r in unique.values() if r['different_score']]
    standard = [r for r in candidates if r['block'] == 1 and r['configuration'] == 'standard' and r['registered']]
    best = max(r['score'] for r in standard); best_ids = [r['candidate_id'] for r in standard if r['score'] == best]
    observed_pairs = [r for r in unique.values() if r['candidate_id'] in best_ids and r['representative_id'] in best_ids]
    banks = {'fingerprint': read(ROOT/'build_contexts/development/states.json')['fingerprint'],
             'audit': read(ROOT/'build_contexts/audit/states.json')['audit']}
    # Static algebra from unchanged candidate10: coefficient of residual/max is
    # 1 - 1.5*item/(item+max_residual), changing sign at item>2*max_residual.
    # This is trusted scalar state-coverage analysis, not calling model priority.
    coverage = {}
    for name, states in banks.items():
        negative = sum(s['item'] > 2*max(b-s['item'] for b in s['bins']) for s in states)
        coverage[name] = {'states': len(states), 'candidate10_negative_slope_states': negative}
    details = {'status': 'completed', 'manifest_sha256': file_hash(MANIFEST), 'frozen_pool_sha256': file_hash(POOL),
        'comparison': summary, 'normal_candidate_records': len(candidates),
        'normal_worker_tasks': sum(r['full_dispatches']+r['fingerprint_dispatches'] for r in runs),
        'normal_full_attempts': sum(r['full_dispatches'] for r in runs),
        'normal_full_completed': sum(r['full_completed'] for r in runs),
        'normal_fingerprint_tasks': sum(r['fingerprint_dispatches'] for r in runs),
        'normal_full_rejections': sum(r['full_dispatches']-r['full_completed'] for r in runs),
        'behavioral_skip_events': len(skips), 'unique_N_source_match_audits': len(unique),
        'unique_false_match_N_source_pairs': len(collisions),
        'false_match_events_including_repeated_block': sum(r['different_score'] is True for r in skips),
        'false_match_source_ids': sorted({r['candidate_id'] for r in collisions}),
        'outside_decision_disagreement_pairs': sum(bool(r['outside_disagreements']) for r in unique.values()),
        'missed_best_improvement_pairs': sum(r['missed_improvement'] is True for r in unique.values()),
        'audit_valid_full_and_vector_pairs': sum(r['full_valid'] and r['vectors_valid'] for r in unique.values()),
        'audit_full_evaluations': audit['independent_full_evaluations'], 'audit_reserved_vectors': audit['independent_reserved_vectors'],
        'audit_total_worker_tasks': audit['independent_full_evaluations']+audit['independent_reserved_vectors'],
        'audit_wall_seconds': audit['audit_wall_seconds'], 'audit_lifecycle_seconds': audit['audit_lifecycle_seconds'],
        'audit_successful_pure_full_seconds': audit['audit_pure_full_seconds_completed'],
        'audit_pure_fingerprint_seconds': audit['audit_fingerprint_seconds'],
        'complete_campaign_wall_seconds_including_barriers': experiment['comparison_wall_seconds'],
        'observed_best_fit_score_source_ids': best_ids,
        'equal_best_score_audit_pairs': len(observed_pairs),
        'equal_best_score_audit_pair_disagreements': sum(bool(r['outside_disagreements']) for r in observed_pairs),
        'decision_evidence_limit': 'Equal queried decisions on nested development prefixes and reserved256 states; full21000-call bin-choice traces were not recorded. Equal aggregate fitness is not a proof of functional equivalence.',
        'candidate10_state_coverage_static_analysis': coverage,
        'all_trajectories_repeat': True, 'audit_did_not_update_trajectories': audit['original_trajectory_unchanged'],
        'new_generation_calls': 0, 'known_logged_pilot_calls_unchanged': 30, 'main_calls': 0,
        'inference': 'Fixed authentic pool, two timing blocks, not independent search seeds or evidence of reduced LLM calls. No end-to-end speedup over Exact observed.'}
    write(RUN/'research_results.json', details)
    csv_write(RUN/'configuration_comparison.csv', summary)
    csv_write(RUN/'candidate_outcomes.csv', candidates)
    csv_write(RUN/'behavioral_audits.csv', skips)
    csv_write(RUN/'unique_behavioral_audits.csv', list(unique.values()))
    csv_write(RUN/'timing_runs.csv', runs)
    print(json.dumps({k: v for k, v in details.items() if k != 'comparison'}, indent=2))
    for row in summary:
        print(row['configuration'], row['full_attempted_per_block'], row['full_completed_per_block'],
              f"{row['wall_mean_seconds']:.6f}s", f"{row['wall_difference_vs_exact_mean_seconds']:+.6f}s vs Exact")


if __name__ == '__main__': main()
