"""Five primary trusted replay comparisons, three fused checks, independent audits."""
import argparse
import csv
from datetime import datetime,timezone
import json
from pathlib import Path
from time import perf_counter

import phase2_bootstrap
from phase2_bootstrap import ROOT
from backend import checked_runner,read
from replay import run_configuration
from audit import audit_run
from run_log import write_json


def logical(rows):
    return [(r['candidate_id'],r['status'],r['score'],r['matched_representative_id']) for r in rows]


def main(args):
    runner=checked_runner(args.image,args.security_run)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    output=ROOT/'experiments'/stamp;output.mkdir(parents=True,exist_ok=False)
    primary=[];optimized=[];audits=[];objects={};start=perf_counter()
    # Fixed logged order, sequential; timing samples are not randomized repetitions.
    configurations=[('standard',16),('exact',16),('behavioral',16),('behavioral',64),('behavioral',128)]
    write_json(output/'experiment.json',{'image':args.image,'security_run':str(args.security_run),
        'primary_order':configurations,'seed':5491,'candidate_stream_identical':True,
        'primary_architecture':'separate','optimized_architecture':'fused','llm_requests':0,
        'generated_execution_enabled':False,'main_campaign_started':False})
    for mode,size in configurations:
        result,obj=run_configuration(runner,mode,size,'separate');primary.append(result)
        if mode=='behavioral':objects[size]=obj
        write_json(output/'primary.json',primary)
        print(json.dumps({'completed':mode,'size':size,'counts':result['counts'],'wall_seconds':result['run_wall_seconds']}),flush=True)
    for size in (16,64,128):
        result,obj=run_configuration(runner,'behavioral',size,'fused')
        if logical(obj.records)!=logical(objects[size].records):raise RuntimeError('Fused replay changed decisions or fitness')
        result['logical_equivalence_to_separate']=True;optimized.append(result)
        write_json(output/'optimized.json',optimized)
        print(json.dumps({'completed':'fused','size':size,'counts':result['counts'],'wall_seconds':result['run_wall_seconds']}),flush=True)
    for result in primary:
        if result['mode']=='behavioral':
            audit=audit_run(runner,result['run_directory']);audits.append(audit)
            write_json(output/'audits.json',audits)
            print(json.dumps({'completed':'audit','size':audit['fingerprint_size'],
                              'candidates':audit['audited_candidates'],'different_scores':audit['different_full_score_vectors'],
                              'missed_improvements':audit['missed_improvement_candidates']}),flush=True)
    fields=['mode','fingerprint_size','architecture','full_attempted','full_completed','skipped','exact_matches',
            'behavioral_matches','rejected','registrations','fingerprint_pure_seconds','fingerprint_only_container_seconds',
            'shared_fused_container_seconds','pure_full_evaluation_seconds','run_wall_seconds','best_fitness',
            'final_accepted_candidate_fitness','representatives_including_seed']
    with (output/'comparison.csv').open('w',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fields);writer.writeheader()
        for result in primary+optimized:
            row={k:result.get(k) for k in fields};row.update({k:result['counts'][k] for k in result['counts'] if k in fields})
            row['rejected']=result['counts']['static_rejections']+result['counts']['runtime_rejections'];writer.writerow(row)
    total={'experiment_directory':str(output),'primary':primary,'optimized':optimized,'audits':audits,
           'total_experiment_wall_seconds':perf_counter()-start,'new_llm_requests':0,'generated_candidates_executed':0,
           'heldout_evaluations':0,'trusted_candidates_are_llm_discoveries':False}
    write_json(output/'results.json',total)
    write_json(ROOT/'latest_experiment.json',{'directory':str(output)})
    print(json.dumps({'results_directory':str(output),'wall_seconds':total['total_experiment_wall_seconds']}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--image',required=True);p.add_argument('--security-run',type=Path,required=True)
    main(p.parse_args())
