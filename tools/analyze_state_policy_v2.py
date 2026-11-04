"""Recompute exported scalar evidence; never load states or execute candidates."""
import csv
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / 'results/state_policy_v2'


def rows(name):
    with (RESULTS / name).open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def main():
    arms = rows('arm_measurements.csv')
    audits = rows('audit_findings.csv')
    published = {r['configuration']: r for r in rows('comparison_summary.csv')}
    assert len(arms) == 24 and len(audits) == 138
    summary = {}
    for name in sorted({r['configuration'] for r in arms}):
        part = [r for r in arms if r['configuration'] == name]
        times = [float(r['normal_wall_seconds']) for r in part]
        mean = statistics.mean(times)
        assert abs(mean - float(published[name]['wall_mean_seconds'])) < 1e-9
        summary[name] = dict(mean_normal_wall_seconds=mean,
                             sample_sd_seconds=statistics.stdev(times),
                             full_completed_per_block=[int(r['full_completed']) for r in part])
    assert all(r['independent_audit_complete'] == 'True' for r in audits)
    s2 = [r for r in audits if '/s2_' in r['arm']]
    assert len(s2) == 54 and not any(r['fitness_disagreement'] == 'True' for r in s2)
    assert not any(int(r['outside_state_disagreements']) for r in s2)
    assert sum(int(r['containers']) for r in arms) == 219
    print(json.dumps(dict(settings=summary, audited_skip_events=138,
                          s2_false_matches_observed=0, candidate_execution=False,
                          docker_dispatches=0, model_requests=0), indent=2))


if __name__ == '__main__':
    main()
