"""Independent offline reconstruction of counts, matches, coverage and audit claims."""
import argparse
import hashlib
import json
from pathlib import Path

import phase2_bootstrap
from phase2_bootstrap import ROOT
from backend import read
from catalogue import STREAM
from candidate_runner import verify_candidate_config
from filters import exact_source
from replay import accepted_full
from run_log import write_json


def events(directory):
    return [json.loads(line) for line in (Path(directory)/'events.jsonl').read_text(encoding='utf-8').splitlines()]


def verify(directory):
    directory=Path(directory);total=read(directory/'results.json');groups=read(ROOT/'data/research_data.json')['development']
    names=set();verdicts=[];stream=None
    for result in total['primary']+total['optimized']:
        run=Path(result['run_directory']);manifest=read(run/'manifest.json');log=events(run)
        current_stream=manifest['candidate_stream']
        if stream is None:stream=current_stream
        assert stream==current_stream,'Candidate stream changed between modes'
        for relative,digest in manifest['phase2_source_sha256'].items():
            if relative=='latest_experiment.json':
                continue  # Derived output pointer, never an execution input.
            if relative=='budget_ledger.json' and hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()!=digest:
                snapshot=ROOT/'evidence/budget_ledger_at_replay.json'
                assert hashlib.sha256(snapshot.read_bytes()).hexdigest()==digest
                old,new=read(snapshot),read(ROOT/relative)
                for key in ('proposal_total_cap','proposal_pilot_cap','proposal_main_cap',
                            'known_historical_requests','known_pilot_calls_used','new_phase2_pilot_calls',
                            'main_calls_used','model','digest'):
                    assert old[key]==new[key],key
                continue  # User's later unknown-count clarification changed memo fields only.
            assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==digest,relative
        rows=[read(run/f'candidate_{i}.json') for i in range(1,len(STREAM)+1)]
        assert [r['fixture'] for r in rows]==STREAM
        assert [r['candidate_id'] for r in rows]==list(range(1,22))
        assert all(r['origin']=='phase2_reviewed_fixture' for r in rows)
        reps=read(run/'representatives.json');by_id={r['candidate_id']:r for r in reps}
        counts=result['counts']
        assert counts['static_rejections']==sum(r['status']=='static_rejected' for r in rows)==2
        assert counts['runtime_rejections']==sum(r['status']=='runtime_rejected' for r in rows)==3
        assert counts['full_completed']==sum(r['status']=='evaluated' for r in rows)
        assert counts['registrations']==sum(r['registered'] for r in rows)==len(reps)-1
        assert counts['skipped']==sum(r['status'].startswith('skipped_') for r in rows)
        tasks=[e for e in log if e['event']=='isolated_task' and e['candidate_id']!=0]
        assert counts['full_attempted']==sum(e['full_evaluation_started'] for e in tasks)
        assert counts['full_completed']==sum(accepted_full(e,groups) for e in tasks)
        assert len([e for e in log if e['event']=='prompt_transition'])==21
        for row in rows:
            assert type(row['island_id']) is int and 0<=row['island_id']<10
            if row['status'].startswith('skipped_'):
                assert row['score'] is None and row['scores_per_group'] is None and not row['registered']
                rep=by_id[row['matched_representative_id']]
                assert rep['candidate_id']<row['candidate_id']
                if row['status']=='skipped_exact':
                    assert rep['source']==exact_source(row['raw_source'],'priority_v'+str(row['version_generated']))
                else:assert rep['fingerprint']==row['fingerprint']
        for task in [e for e in log if e['event']=='isolated_task']:
            assert task['cleanup_verified']
            assert task['container_name'] not in names,'Container reused between candidates/tasks'
            names.add(task['container_name']);verify_candidate_config(task['inspected_configuration'],manifest['image'])
        verdicts.append({'run_id':result['run_id'],'mode':result['mode'],'size':result['fingerprint_size'],
                         'architecture':result['architecture'],'verified':True})
    audit_verdicts=[]
    for summary in total['audits']:
        run=Path(summary['run_directory']);rows=read(run/'audit_candidates.json')
        assert summary['audited_candidates']==len(rows)
        assert summary['different_full_score_vectors']==sum(r['different_full_score_vector'] for r in rows)
        assert summary['missed_improvement_candidates']==sum(r['audit_valid'] and r['audit_score']>r['best_at_skip'] for r in rows)
        assert all(not r['registered_in_search'] for r in rows)
        for task in [e for e in events(run) if e['event'] in ('audit_candidate_execution','audit_representative_probe')]:
            assert task['cleanup_verified'] and task['container_name'] not in names
            names.add(task['container_name']);verify_candidate_config(task['inspected_configuration'],total['primary'][0].get('image',read(Path(total['primary'][0]['run_directory'])/'manifest.json')['image']))
        audit_verdicts.append({'size':summary['fingerprint_size'],'verified':True,'audit_rows':len(rows)})
    assert len(total['primary'])==5 and len(total['optimized'])==3 and len(total['audits'])==3
    assert total['new_llm_requests']==total['generated_candidates_executed']==0
    assert not (ROOT.parent/'phase1b/phase1e/authorization.json').exists()
    verdict={'status':'PASS','normal_replays':verdicts,'independent_audits':audit_verdicts,
             'unique_replay_and_audit_containers':len(names),'generated_code_executed':0,'new_llm_requests':0,
             'scope':'Offline verification of actual records, not additional evaluation or equivalence proof'}
    write_json(directory/'verification.json',verdict)
    print(json.dumps(verdict,indent=2))
    return verdict


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args();verify(a.directory)
