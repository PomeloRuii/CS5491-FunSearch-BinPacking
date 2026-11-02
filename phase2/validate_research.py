"""Actual reviewed task validation after the complete existing isolation suite."""
import argparse
import json
from pathlib import Path

import phase2_bootstrap
from phase2_bootstrap import ROOT
from backend import checked_runner,read
from catalogue import reviewed_candidate
from interface import parse_candidate
from replay import accepted_full,accepted_fingerprint
from run_log import RunLog,write_json
import numpy as np


def main(args):
    runner=checked_runner(args.image,args.security_run);log=RunLog(ROOT/'validations');records=[]
    log.manifest(phase='2_reviewed_task_validation',image=args.image,security_receipt=str(args.security_run),generated_code_executed=False)
    try:
        for fixture,score in [('first_fit',-212.75),('best_fit',-212.0),('seed',-500.0)]:
            candidate=reviewed_candidate(fixture,'priority');parsed=parse_candidate(candidate.text,'priority')
            record=runner.run_task(candidate,parsed,'full',dataset='legacy_validation')
            if record.get('result',{}).get('score')!=score or record['status']!='ok':raise RuntimeError('Legacy baseline changed')
            records.append(record);log.emit('legacy_baseline',fixture=fixture,**record)
        bank=read(ROOT/'data/states.json')
        candidate=reviewed_candidate('best_fit','priority');parsed=parse_candidate(candidate.text,'priority')
        for size in (16,64,128):
            expected=[s['valid_bin_indices'][int(np.argmax(-np.asarray(s['bins'])))] for s in bank['fingerprint'][:size]]
            separate=runner.run_task(candidate,parsed,'fingerprint',size=size)
            if separate.get('result',{}).get('decisions')!=expected:raise RuntimeError('Fingerprint argmax/order mismatch')
            fused=runner.run_task(candidate,parsed,'fused',size=size)
            if not accepted_full(fused,runner.data['development']) or fused['result']['decisions']!=expected:
                raise RuntimeError('Fused full task failed')
            skipped=runner.run_task(candidate,parsed,'fused',size=size,representatives=[{'candidate_id':3,'decisions':expected}])
            if (skipped['result'].get('full_evaluation_performed') or skipped['result'].get('matched_representative_id')!=3):
                raise RuntimeError('Fused match did not avoid full evaluation')
            for action,r in [('fingerprint',separate),('fused_full',fused),('fused_skip',skipped)]:
                records.append(r);log.emit('research_task',size=size,action=action,**r)
        reference_scores=fused['result']['scores_per_group']
        full=runner.run_task(candidate,parsed,'full')
        if full['result']['scores_per_group']!=reference_scores:raise RuntimeError('Probe changed full fitness')
        records.append(full);log.emit('separate_full_equivalence',**full)
        for fixture in ('invalid_shape','invalid_nan','runtime_error'):
            candidate=reviewed_candidate(fixture,'priority');parsed=parse_candidate(candidate.text,'priority')
            for action in ('full','fingerprint','fused'):
                r=runner.run_task(candidate,parsed,action)
                if r['status']=='ok':raise RuntimeError('Invalid reviewed candidate accepted')
                records.append(r);log.emit('reviewed_invalid',fixture=fixture,action=action,**r)
        candidate=reviewed_candidate('validation_dtype','priority');parsed=parse_candidate(candidate.text,'priority')
        typed_full=runner.run_task(candidate,parsed,'full')
        if not accepted_full(typed_full,runner.data['development']):raise RuntimeError('Full evaluation dtype/scalar changed')
        records.append(typed_full);log.emit('typed_full_validation',**typed_full)
        for size in (16,64,128):
            typed_probe=runner.run_task(candidate,parsed,'fingerprint',size=size)
            if not accepted_fingerprint(typed_probe,size,[s['state_id'] for s in bank['fingerprint'][:size]]):
                raise RuntimeError('Probe dtype/scalar differs from full evaluator')
            records.append(typed_probe);log.emit('typed_probe_validation',size=size,**typed_probe)
        write_json(log.directory/'records.json',records)
        result=log.finish('PASS',checks=len(records),all_cleanup_verified=all(r['cleanup_verified'] for r in records),
                          image=args.image,security_run=str(args.security_run),generated_code_executed=False)
        write_json(ROOT/'research_validation.json',{'run_directory':str(log.directory),**result})
        print(json.dumps({'run_directory':str(log.directory),**result},indent=2))
    except Exception as exc:
        log.finish('FAIL',message=str(exc),completed_checks=len(records));raise


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--image',required=True);p.add_argument('--security-run',type=Path,required=True)
    main(p.parse_args())
