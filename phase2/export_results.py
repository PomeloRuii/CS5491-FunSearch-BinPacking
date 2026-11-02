"""Analysis/export from measured logs; never assigns fitness to skipped candidates."""
import argparse
import csv
import json
from pathlib import Path
import statistics

import phase2_bootstrap
from backend import read
from run_log import write_json


def dump_csv(path,rows,fields):
    with path.open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fields,extrasaction='ignore');writer.writeheader()
        writer.writerows({k:json.dumps(v,sort_keys=True) if isinstance(v,(dict,list)) else v
                          for k,v in row.items()} for row in rows)


def export(directory):
    directory=Path(directory);results=read(directory/'results.json');quality=[];audit_rows=[];costs=[]
    for run in results['primary']+results['optimized']:
        base={k:run[k] for k in ('mode','fingerprint_size','architecture')}
        events=[json.loads(x) for x in (Path(run['run_directory'])/'events.jsonl').read_text(encoding='utf-8').splitlines()]
        for path in Path(run['run_directory']).glob('candidate_*.json'):
            row=read(path);scores=row.get('scores_per_group') or {}
            candidate_tasks=[e for e in events if e['event']=='isolated_task' and e['candidate_id']==row['candidate_id']]
            measured_full=[e for e in candidate_tasks if e.get('result',{}).get('full_evaluation_performed')]
            measured_probe=[e for e in candidate_tasks if 'fingerprint_seconds' in e.get('result',{})]
            quality.append({**base,'candidate_id':row['candidate_id'],'fixture':row['fixture'],
                'status':row['status'],'fitness':row['score'],
                'OR3_mean_bins':-scores['OR3'] if 'OR3' in scores else None,
                'Weibull_mean_bins':-scores['Weibull 5k'] if 'Weibull 5k' in scores else None,
                'registered':row['registered'],'matched_representative_id':row['matched_representative_id'],
                'island_id':row['island_id'],'version_generated':row['version_generated'],
                'candidate_processing_seconds':row['processing_seconds'],'parse_seconds':row['parse_seconds'],
                'candidate_container_lifecycle_seconds':sum(e['total_seconds'] for e in candidate_tasks),
                'worker_readiness_seconds':sum(e.get('worker_ready_seconds',0) for e in candidate_tasks),
                'pure_full_evaluation_seconds':sum(e['result']['pure_evaluate_seconds'] for e in measured_full) if measured_full else None,
                'pure_fingerprint_seconds':sum(e['result']['fingerprint_seconds'] for e in measured_probe) if measured_probe else None,
                'evaluator_score_bridge_seconds':row.get('evaluation',{}).get('full_evaluation_seconds')})
        tasks=[e for e in events if e['event']=='isolated_task' and e['candidate_id']!=0 and e['status']=='ok']
        probes=[e for e in tasks if e['action']=='fingerprint'];full=[e for e in tasks if e['action']=='full']
        fp_ids={e['candidate_id']:e for e in probes};pairs=[(fp_ids[e['candidate_id']],e) for e in full if e['candidate_id'] in fp_ids]
        average=lambda values:statistics.mean(values) if values else None
        cost={**base,'completed_standalone_fp_tasks':len(probes),
              'mean_fp_lifecycle_seconds':average([e['total_seconds'] for e in probes]),
              'mean_full_lifecycle_seconds':average([e['total_seconds'] for e in full]),
              'mean_fp_pure_seconds':average([e['result']['fingerprint_seconds'] for e in probes]),
              'mean_full_pure_seconds':average([e['result']['pure_evaluate_seconds'] for e in full]),
              'paired_candidates':len(pairs),
              'paired_mean_fp_lifecycle_seconds':average([a['total_seconds'] for a,b in pairs]),
              'paired_mean_full_lifecycle_seconds':average([b['total_seconds'] for a,b in pairs]),
              'mean_fp_readiness_seconds':average([e['worker_ready_seconds'] for e in probes]),
              'fingerprint_cpu_total_seconds':run['fingerprint_pure_seconds'],
              'fp_only_lifecycle_seconds':run['fingerprint_only_container_seconds'],
              'shared_fused_lifecycle_seconds':run['shared_fused_container_seconds'],
              'full_cpu_total_seconds':run['pure_full_evaluation_seconds'],
              'replay_wall_seconds':run['run_wall_seconds'],
              'deduplication_full_evaluations_avoided':run['counts']['skipped'],
              'rejection_before_full_due_to_probe':run['counts']['runtime_rejections'] if run['mode']=='behavioral' else 0}
        costs.append(cost)
    for audit in results['audits']:
        for row in read(Path(audit['run_directory'])/'audit_candidates.json'):
            audit_rows.append({'fingerprint_size':audit['fingerprint_size'],**row})
    quality.sort(key=lambda r:(r['mode'],r['fingerprint_size'] or 0,r['architecture'],r['candidate_id']))
    dump_csv(directory/'candidate_quality.csv',quality,list(quality[0]))
    dump_csv(directory/'audit_details.csv',audit_rows,list(audit_rows[0]))
    dump_csv(directory/'cost_breakdown.csv',costs,list(costs[0]))
    write_json(directory/'cost_breakdown.json',costs)
    print(json.dumps({'candidate_quality_rows':len(quality),'audit_rows':len(audit_rows),'cost_rows':len(costs)},indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);args=parser.parse_args();export(args.directory)
