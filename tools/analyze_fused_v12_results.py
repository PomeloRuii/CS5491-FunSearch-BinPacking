"""Recompute published paired statistics only; no files written or code evaluated."""
import csv,json,statistics
from pathlib import Path
root=Path(__file__).resolve().parent.parent
with (root/'results/fused_v12/paired_comparison.csv').open(newline='',encoding='utf-8') as f:rows=list(csv.DictReader(f))
exact=[float(r['exact_seconds']) for r in rows];fused=[float(r['fused16_seconds']) for r in rows]
assert len(rows)==2 and [r['order'] for r in rows]==['exact / fused16','fused16 / exact']
e=statistics.mean(exact);b=statistics.mean(fused)
print(json.dumps({'exact_mean_seconds':e,'fused16_mean_seconds':b,'seconds_saved':e-b,'percent_lower_than_exact':100*(e-b)/e,
 'exact_sample_sd':statistics.stdev(exact),'fused16_sample_sd':statistics.stdev(fused),'timing_observations':2,'new_model_calls':0},indent=2))
