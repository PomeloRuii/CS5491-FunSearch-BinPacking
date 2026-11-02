"""Independent 100% audit of sampled-behavior matches. Never updates search state."""
import argparse
import hashlib
import json
from pathlib import Path
from time import perf_counter

import phase2_bootstrap
from phase2_bootstrap import ROOT
from backend import read,checked_runner
from catalogue import reviewed_candidate
from interface import parse_candidate
from replay import accepted_full,accepted_fingerprint
from run_log import RunLog,write_json


def original_candidate(row=None):
    if row is None:
        candidate=reviewed_candidate('seed','priority');name='priority'
    else:
        name='priority_v'+str(row['version_generated'])
        candidate=reviewed_candidate(row['fixture'],name)
        if candidate.text!=row['raw_source']:raise PermissionError('Saved source differs from fixed reviewed fixture')
    return candidate,parse_candidate(candidate.text,name)


def audit_run(runner,directory):
    directory=Path(directory);manifest=read(directory/'manifest.json');normal=read(directory/'summary.json')
    if manifest['mode']!='behavioral' or normal['status']!='completed':raise ValueError('A completed behavioral replay is required')
    rows=[read(path) for path in directory.glob('candidate_*.json')];rows.sort(key=lambda r:r['candidate_id'])
    by_id={r['candidate_id']:r for r in rows}
    skipped=[r for r in rows if r['status']=='skipped_behavioral']
    reps=read(directory/'representatives.json');rep_by_id={r['candidate_id']:r for r in reps}
    before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir() if p.is_file()}
    log=RunLog(ROOT/'audits');start=perf_counter();tasks=[];outcomes=[];reference_vectors={}
    bank=read(ROOT/'data/states.json');expected_ids=[s['state_id'] for s in bank['audit']]
    log.manifest(phase='2_independent_audit',original_replay=str(directory),image=runner.image,
                 strategy='Audit every behavioral match; exact-source skips excluded',
                 audit_state_ids=expected_ids,dataset_scope='development full fitness plus reserved-audit-instance probe states',
                 final_heldout_used=False,new_llm_requests=0)
    try:
        for row in skipped:
            rep_id=row['matched_representative_id']
            if rep_id not in rep_by_id:raise ValueError('Missing fully evaluated representative')
            if rep_id not in reference_vectors:
                candidate,parsed=original_candidate(by_id.get(rep_id))
                record=runner.run_task(candidate,parsed,'fingerprint',state_set='audit',size=256)
                tasks.append(record);log.emit('audit_representative_probe',representative_id=rep_id,**record)
                if not accepted_fingerprint(record,256,expected_ids):raise RuntimeError('Representative audit probe failed')
                reference_vectors[rep_id]=record['result']['decisions']
            candidate,parsed=original_candidate(row)
            record=runner.run_task(candidate,parsed,'audit_full',state_set='audit',size=256)
            tasks.append(record);log.emit('audit_candidate_execution',candidate_id=row['candidate_id'],**record)
            valid=accepted_full(record,runner.data['development']) and accepted_fingerprint(record,256,expected_ids)
            result=record.get('result',{});decisions=result.get('decisions',[])
            disagreements=(sum(a!=b for a,b in zip(decisions,reference_vectors[rep_id])) if valid else None)
            outcome={'candidate_id':row['candidate_id'],'fixture':row['fixture'],
                     'representative_id':rep_id,'normal_search_status':row['status'],
                     'audit_valid':valid,'audit_scores_per_group':result.get('scores_per_group') if valid else None,
                     'audit_score':result.get('score') if valid else None,
                     'representative_scores':rep_by_id[rep_id]['scores'],
                     'different_full_score_vector':bool(valid and result['scores_per_group']!=rep_by_id[rep_id]['scores']),
                     'different_aggregate_fitness':bool(valid and result['score']!=rep_by_id[rep_id]['score']),
                     'best_at_skip':row['best_before'],
                     'would_improve_current_best':bool(valid and result['score']>row['best_before']),
                     'outside_disagreements':disagreements,'outside_state_count':256,
                     'outside_disagreement_rate':disagreements/256 if valid else None,
                     'registered_in_search':False,'audit_container_seconds':record['total_seconds']}
            outcomes.append(outcome);log.emit('audit_outcome',**outcome)
        after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in directory.iterdir() if p.is_file()}
        if before!=after:raise RuntimeError('Audit modified the original replay artifacts')
        write_json(log.directory/'audit_candidates.json',outcomes)
        summary=log.finish('completed',original_replay=str(directory),mode=manifest['mode'],
            fingerprint_size=manifest['fingerprint_size'],audited_candidates=len(outcomes),
            audit_full_evaluations_attempted=sum(r.get('full_evaluation_started',False) for r in tasks),
            audit_full_evaluations_completed=sum(r['audit_valid'] for r in outcomes),
            representative_probe_count=len(reference_vectors),
            audit_container_invocations=len(tasks),audit_container_seconds=sum(r['total_seconds'] for r in tasks),
            audit_pure_full_seconds=sum(r.get('result',{}).get('pure_evaluate_seconds',0) for r in tasks),
            audit_fingerprint_pure_seconds=sum(r.get('fingerprint_phase_seconds',0) for r in tasks),
            different_full_score_vectors=sum(r['different_full_score_vector'] for r in outcomes),
            outside_behavior_disagreement_candidates=sum(bool(r['outside_disagreements']) for r in outcomes),
            missed_improvement_candidates=sum(r['would_improve_current_best'] for r in outcomes),
            audit_invalid_candidates=sum(not r['audit_valid'] for r in outcomes),
            original_trajectory_unchanged=True,new_llm_requests=0)
        summary['run_directory']=str(log.directory)
        return summary
    except Exception as exc:
        log.finish('failed',message=str(exc),completed_audits=len(outcomes));raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--image',required=True);p.add_argument('--security-run',type=Path,required=True)
    p.add_argument('--replay-run',type=Path,required=True);a=p.parse_args()
    print(json.dumps(audit_run(checked_runner(a.image,a.security_run),a.replay_run),indent=2))
