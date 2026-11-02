"""Recompute public comparison statistics; no Docker/model/source execution."""
import argparse
import csv
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]


def main(output):
    with (ROOT/'results/timing_runs.csv').open(newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    result = []
    for label in ('standard','exact','behavioral-16','behavioral-64','behavioral-128'):
        pair = [r for r in rows if r['configuration'] == label]
        times = [float(r['normal_wall_seconds']) for r in pair]
        assert len(pair) == 2 and pair[0]['logical_trace_sha256'] == pair[1]['logical_trace_sha256']
        result.append({'configuration':label,'full_attempted_per_block':int(pair[0]['full_dispatches']),
            'full_completed_per_block':int(pair[0]['full_completed']), 'wall_mean_seconds':statistics.mean(times),
            'wall_sample_sd_seconds':statistics.stdev(times),'wall_range_seconds':[min(times),max(times)]})
    with (ROOT/'results/unique_behavioral_audits.csv').open(newline='', encoding='utf-8') as f:
        audits = list(csv.DictReader(f))
    final = {'comparison':result,'unique_N_source_matches':len(audits),
        'score_false_matches':sum(r['different_score']=='True' for r in audits),
        'outside_disagreement_pairs':sum(int(r['outside_disagreements']) > 0 for r in audits),
        'missed_best_improvements':sum(r['missed_improvement']=='True' for r in audits),
        'new_generation_calls':0,'candidate_source_executions':0}
    with (ROOT/'results/configuration_comparison.csv').open(newline='', encoding='utf-8') as f:
        published = list(csv.DictReader(f))
    for a,b in zip(result,published):
        assert a['configuration']==b['configuration'] and abs(a['wall_mean_seconds']-float(b['wall_mean_seconds']))<1e-9
    Path(output).write_text(json.dumps(final,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(final,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    main(parser.parse_args().output)
