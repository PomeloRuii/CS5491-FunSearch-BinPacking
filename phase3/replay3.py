"""Reuse original islands/Evaluator and Phase 2 acceptance/filtering, scoped sources."""
from time import perf_counter
import hashlib
import bootstrap3
from bootstrap3 import ROOT, PHASE2
from common import read, write, digest
from replay import Replay, accepted_full, accepted_fingerprint
from filters import exact_source
from interface import parse_candidate, expected_name, messages_for
from static_policy import validate
from catalogue import STREAM, reviewed_candidate
from implementation import code_manipulation as cm, evaluator
from trusted_cases import SPECIFICATION
from run_log import RunLog

class CheckedBatch(evaluator.Sandbox):
    def __init__(self, runner, candidate, parsed, record, groups):
        self.runner,self.candidate,self.parsed,self.record,self.groups=runner,candidate,parsed,record,groups
        self.last_result={}
    def run(self, program, run, evolve, inputs, key, timeout_seconds, **kwargs):
        self.runner.check_candidate(self.candidate)
        expected=cm.text_to_program(SPECIFICATION)
        expected.get_function('priority').body=cm.rename_function_calls(self.parsed.body,self.parsed.function_name,'priority')
        if program!=str(expected) or inputs!=self.groups or run!='evaluate' or evolve!='priority':
            raise PermissionError('Benchmark/candidate substitution refused')
        self.last_result={'status':self.record['status'],'cleanup_verified':self.record['cleanup_verified']}
        if not accepted_full(self.record,self.groups): return None,False
        return self.record['result']['scores_per_group'][key],True

class ScopedReplay(Replay):
    def register(self,candidate,parsed,prompt,candidate_id,record):
        before=[island._num_programs for island in self.database._islands]
        engine=evaluator.Evaluator(self.database,self.template,'priority','evaluate',self.groups,
            sandbox_class=lambda:CheckedBatch(self.runner,candidate,parsed,record,self.groups))
        outcome=engine.analyse(parsed.body,None if prompt is None else prompt.island_id,
            None if prompt is None else prompt.version_generated,candidate_id=candidate_id,
            origin=candidate.origin,audit_logger=self.log)
        after=[island._num_programs for island in self.database._islands]
        expected=before.copy()
        if outcome['status']=='ok':
            for i in (range(len(expected)) if prompt is None else [prompt.island_id]): expected[i]+=1
        if after!=expected: raise RuntimeError('Database registration changed unexpectedly')
        outcome['island_counts_before']=before;outcome['island_counts_after']=after
        return outcome

    def process(self,candidate,prompt,candidate_id):
        # A fixed pool retains its original source/header and generation island.
        # Replay island/version are new real metadata, never substituted as history.
        start=perf_counter();model=candidate.origin=='ollama'
        name=candidate.response_metadata['expected_name'] if model else expected_name(prompt)
        row={'candidate_id':candidate_id,'fixture':candidate.fixture,'origin':candidate.origin,
            'island_id':int(prompt.island_id),'version_generated':prompt.version_generated,
            'generation_metadata':candidate.response_metadata if model else None,
            'raw_source':candidate.text,'source_sha256':hashlib.sha256(candidate.text.encode()).hexdigest(),
            'prompt_code':prompt.code,'messages':messages_for(prompt),'score':None,'scores_per_group':None,
            'matched_representative_id':None,'best_before':self.best,'registered':False,
            'fingerprint':None,'filter_seconds':0.0}
        stage=perf_counter()
        try:
            if model: parsed,static=validate(candidate.text,name,candidate.finish_reason);row['static']=static
            else: parsed=parse_candidate(candidate.text,name,candidate.finish_reason)
        except (ValueError,SyntaxError) as exc:
            self.counts['static_rejections']+=1;row.update(status='static_rejected',reason=str(exc),parse_seconds=perf_counter()-stage)
        else:
            row['parse_seconds']=perf_counter()-stage;row['parsed_body']=parsed.body
            try: self.runner.check_candidate(candidate)
            except PermissionError as exc:
                self.counts['blocked_generated']+=1;row.update(status='blocked_generated_execution',reason=str(exc))
            else:
                key=exact_source(candidate.text,name)
                row['exact_source_key_sha256']=hashlib.sha256(key.encode()).hexdigest()
                stage=perf_counter();match=self.reps.exact(key) if self.mode!='standard' else None
                row['filter_seconds']+=perf_counter()-stage
                record=None;fp=None
                if match is not None:
                    row.update(status='skipped_exact',matched_representative_id=match['candidate_id'])
                    self.counts['exact_matches']+=1
                else:
                    if self.mode=='behavioral':
                        action='fused' if self.architecture=='fused' else 'fingerprint'
                        record=self.task(candidate,parsed,action,size=self.size,representatives=self.reps.wire())
                        expected=[s['state_id'] for s in self.states['fingerprint'][:self.size]]
                        if not accepted_fingerprint(record,self.size,expected):
                            row.update(status='runtime_rejected',reason='Fingerprint failed',worker_status=record['status'])
                            self.counts['runtime_rejections']+=1
                        else:
                            fp=record['result']['decisions'];row['fingerprint']=fp
                            stage=perf_counter();match=self.reps.behavioral(fp);row['filter_seconds']+=perf_counter()-stage
                            if match is not None:
                                if self.architecture=='fused' and (record['result'].get('full_evaluation_performed') or
                                    record['result'].get('matched_representative_id')!=match['candidate_id']):
                                    raise RuntimeError('Fused match differs from host')
                                row.update(status='skipped_behavioral',matched_representative_id=match['candidate_id'],
                                           representative_score=match['score'])
                                self.counts['behavioral_matches']+=1
                    if match is None and row.get('status')!='runtime_rejected':
                        if self.mode!='behavioral' or self.architecture=='separate': record=self.task(candidate,parsed,'full')
                        outcome=self.register(candidate,parsed,prompt,candidate_id,record);row['evaluation']=outcome
                        if outcome['status']=='ok':
                            self.counts['full_completed']+=1;self.counts['registrations']+=1
                            self.reps.retain(candidate_id,key,fp,outcome['scores_per_group'])
                            row.update(status='evaluated',score=outcome['score'],scores_per_group=outcome['scores_per_group'],registered=True)
                            self.best=max(self.best,outcome['score']);self.final=outcome['score']
                        else:
                            self.counts['runtime_rejections']+=1
                            row.update(status='runtime_rejected',reason='Complete finite evaluation required',worker_status=record['status'])
                if row.get('status','').startswith('skipped_'):self.counts['skipped']+=1
        row['best_after']=self.best;row['processing_seconds']=perf_counter()-start
        self.records.append(row);self.log.emit('candidate_outcome',**row)
        return row

def run_trusted(runner,mode,size=16,architecture='separate',seed=5491):
    log=RunLog(ROOT/'trusted_runs');replay=ScopedReplay(runner,mode,size,architecture,log,seed)
    log.manifest(phase='3_trusted_timing',mode=mode,fingerprint_size=size,architecture=architecture,
                 image=runner.image,seed=seed,llm_requests=0,model_sources_executed=0)
    try:
        result=replay.run()
        for row in replay.records:write(log.directory/f"candidate_{row['candidate_id']}.json",row)
        write(log.directory/'representatives.json',replay.reps.all)
        summary=log.finish('completed',**result);summary['run_directory']=str(log.directory)
        return summary,replay
    except Exception as exc:
        log.finish('failed',message=str(exc));raise
