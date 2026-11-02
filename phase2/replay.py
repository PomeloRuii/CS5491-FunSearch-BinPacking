"""Shared configurable FunSearch replay and audit; no generated-source execution."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import random
from time import perf_counter

import phase2_bootstrap
from phase2_bootstrap import ROOT
from backend import checked_runner,read
from catalogue import STREAM,reviewed_candidate,require_reviewed,stream_manifest
from filters import Representatives,exact_source
from interface import expected_name,messages_for,parse_candidate
from implementation import code_manipulation as cm,config,evaluator
from implementation.programs_database import ProgramsDatabase
from trusted_cases import SPECIFICATION
from run_log import RunLog,write_json
import numpy as np


def accepted_full(record,groups):
    result=record.get('result',{})
    if (record['status']!='ok' or not record.get('cleanup_verified')
            or result.get('validity_policy')!='obp-validity-v1'
            or not any(m.get('kind')=='context' for m in record.get('worker_messages',[]))
            or not result.get('full_evaluation_performed')):
        return False
    scores=result.get('scores_per_group',{});details=result.get('group_details',{})
    if set(scores)!=set(groups) or set(details)!=set(groups):return False
    for group,instances in groups.items():
        if type(scores[group]) not in (int,float) or not np.isfinite(scores[group]):return False
        if (details[group].get('instances_completed')!=len(instances)
                or details[group].get('priority_calls')!=sum(len(x['items']) for x in instances.values())):
            return False
    return (type(result.get('score')) in (int,float) and np.isfinite(result['score'])
            and result['score']==sum(scores.values())/len(scores))


def accepted_fingerprint(record,size,expected_state_ids):
    result=record.get('result',{});decisions=result.get('decisions',[])
    return (record['status']=='ok' and record.get('cleanup_verified')
            and result.get('validity_policy')=='obp-validity-v1'
            and any(m.get('kind')=='context' for m in record.get('worker_messages',[]))
            and len(decisions)==size
            and all(type(x) is int and x>=0 for x in decisions)
            and result.get('state_ids')==expected_state_ids)


class BatchSandbox(evaluator.Sandbox):
    """One isolated batch covers all original groups; Evaluator still aggregates/registers."""
    def __init__(self,record,candidate,parsed,groups):
        self.record,self.candidate,self.parsed,self.groups=record,candidate,parsed,groups
        self.first=True;self.last_result={}

    def run(self,program,run,evolve,inputs,key,timeout_seconds,**kwargs):
        require_reviewed(self.candidate)
        expected=cm.text_to_program(SPECIFICATION)
        expected.get_function('priority').body=cm.rename_function_calls(self.parsed.body,self.parsed.function_name,'priority')
        if program!=str(expected) or inputs!=self.groups or run!='evaluate' or evolve!='priority':
            raise PermissionError('Benchmark or candidate body substitution refused')
        self.last_result={'status':self.record['status'],'shared_batch':not self.first,
                          'result':self.record.get('result',{}),'cleanup_verified':self.record['cleanup_verified']}
        self.first=False
        if not accepted_full(self.record,self.groups):return None,False
        return self.record['result']['scores_per_group'][key],True


class Replay:
    def __init__(self,runner,mode,size,architecture,logger,seed=5491):
        if mode not in ('standard','exact','behavioral'):raise ValueError('Unknown mode')
        if architecture not in ('separate','fused') or size not in (16,64,128):raise ValueError('Invalid replay configuration')
        self.runner,self.mode,self.size,self.architecture,self.log=runner,mode,size,architecture,logger
        random.seed(seed);np.random.seed(seed)
        self.template=cm.text_to_program(SPECIFICATION)
        self.database=ProgramsDatabase(config.ProgramsDatabaseConfig(),self.template,'priority')
        self.groups=runner.data['development'];self.states=read(ROOT/'data/states.json')
        self.reps=Representatives();self.records=[];self.executions=[];self.seed_executions=[]
        self.counts={k:0 for k in ('candidates','static_rejections','runtime_rejections','full_attempted',
                                  'full_completed','exact_matches','behavioral_matches','skipped','registrations','blocked_generated')}
        self.best=None;self.final=None

    def task(self,candidate,parsed,action,seed=False,**kwargs):
        start=perf_counter();record=self.runner.run_task(candidate,parsed,action,**kwargs)
        record['host_task_seconds']=perf_counter()-start;record['action']=action
        (self.seed_executions if seed else self.executions).append(record)
        self.log.emit('isolated_task',candidate_id=0 if seed else self.counts['candidates'],**record)
        return record

    def register(self,candidate,parsed,prompt,candidate_id,record):
        before=None if prompt is None else self.database._islands[prompt.island_id]._num_programs
        engine=evaluator.Evaluator(self.database,self.template,'priority','evaluate',self.groups,
            sandbox_class=lambda:BatchSandbox(record,candidate,parsed,self.groups))
        outcome=engine.analyse(parsed.body,None if prompt is None else prompt.island_id,
                               None if prompt is None else prompt.version_generated,
                               candidate_id=candidate_id,origin=candidate.origin,audit_logger=self.log)
        if outcome['status']=='ok' and prompt is not None:
            if self.database._islands[prompt.island_id]._num_programs!=before+1:
                raise RuntimeError('Registration count mismatch')
        return outcome

    def initialize(self):
        candidate=reviewed_candidate('seed','priority');parsed=parse_candidate(candidate.text,'priority')
        action='fused' if self.mode=='behavioral' and self.architecture=='fused' else 'full'
        record=self.task(candidate,parsed,action,seed=True,size=self.size)
        outcome=self.register(candidate,parsed,None,0,record)
        if outcome['status']!='ok':raise RuntimeError('Development seed evaluation failed')
        fp=None
        if self.mode=='behavioral':
            if self.architecture=='separate':record=self.task(candidate,parsed,'fingerprint',seed=True,size=self.size)
            if not accepted_fingerprint(record,self.size,[s['state_id'] for s in self.states['fingerprint'][:self.size]]):
                raise RuntimeError('Seed fingerprint failed')
            fp=record['result']['decisions']
        self.reps.retain(0,exact_source(candidate.text,'priority'),fp,outcome['scores_per_group'])
        self.best=outcome['score'];self.final=outcome['score']
        self.seed_scores=outcome['scores_per_group']
        return self.database.get_prompt()

    def process(self,candidate,prompt,candidate_id):
        start=perf_counter();name=expected_name(prompt)
        row={'candidate_id':candidate_id,'fixture':candidate.fixture,'origin':candidate.origin,
             'island_id':int(prompt.island_id),'version_generated':prompt.version_generated,
             'raw_source':candidate.text,'prompt_code':prompt.code,'messages':messages_for(prompt),
             'score':None,'scores_per_group':None,'matched_representative_id':None,
             'best_before':self.best,'registered':False,'fingerprint':None,'filter_seconds':0.0}
        stage=perf_counter()
        try:parsed=parse_candidate(candidate.text,name,candidate.finish_reason)
        except (ValueError,SyntaxError) as exc:
            self.counts['static_rejections']+=1;row.update(status='static_rejected',reason=str(exc),parse_seconds=perf_counter()-stage)
        else:
            row['parse_seconds']=parsed.parse_seconds;row['parsed_body']=parsed.body
            try:require_reviewed(candidate)  # Applies before exact-cache lookup, too.
            except PermissionError as exc:
                self.counts['blocked_generated']+=1
                row.update(status='blocked_generated_execution',reason=str(exc),best_after=self.best,
                           processing_seconds=perf_counter()-start)
                self.records.append(row);self.log.emit('candidate_outcome',**row)
                return row
            key=exact_source(candidate.text,name);row['exact_source_key_sha256']=hashlib.sha256(key.encode()).hexdigest()
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
                        row.update(status='runtime_rejected',reason='Fingerprint task failed',worker_status=record['status'])
                        self.counts['runtime_rejections']+=1
                    else:
                        fp=record['result']['decisions'];row['fingerprint']=fp
                        stage=perf_counter();match=self.reps.behavioral(fp);row['filter_seconds']+=perf_counter()-stage
                        if match is not None:
                            if self.architecture=='fused' and (record['result'].get('full_evaluation_performed') or
                                  record['result'].get('matched_representative_id')!=match['candidate_id']):
                                raise RuntimeError('Fused decision disagrees with host representative index')
                            row.update(status='skipped_behavioral',matched_representative_id=match['candidate_id'],
                                       representative_score=match['score'])
                            self.counts['behavioral_matches']+=1
                if match is None and row.get('status')!='runtime_rejected':
                    self.counts['full_attempted']+=1
                    if self.mode!='behavioral' or self.architecture=='separate':record=self.task(candidate,parsed,'full')
                    outcome=self.register(candidate,parsed,prompt,candidate_id,record)
                    row['evaluation']=outcome
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

    def run(self,stream=STREAM):
        prompt=self.initialize()
        for candidate_id,fixture in enumerate(stream,1):
            self.counts['candidates']+=1
            candidate=reviewed_candidate(fixture,expected_name(prompt))
            self.log.emit('trusted_generation',candidate_id=candidate_id,fixture=fixture,
                          source=candidate.text,llm_api_requests=0,island_id=int(prompt.island_id),
                          version_generated=prompt.version_generated)
            self.process(candidate,prompt,candidate_id)
            stage=perf_counter();prompt=self.database.get_prompt()
            self.log.emit('prompt_transition',after_candidate_id=candidate_id,code=prompt.code,
                          island_id=int(prompt.island_id),version_generated=prompt.version_generated,
                          seconds=perf_counter()-stage)
        return self.summary()

    def summary(self):
        tasks=self.executions
        self.counts['full_attempted']=sum(r.get('full_evaluation_started',False) for r in tasks)
        return {'mode':self.mode,'fingerprint_size':self.size if self.mode=='behavioral' else None,
                'architecture':self.architecture,'counts':self.counts,
                'best_fitness':self.best,'final_accepted_candidate_fitness':self.final,
                'best_registered_fitness':max(r['score'] for r in self.reps.all),
                'representatives_including_seed':len(self.reps.all),
                'seed_scores_per_group':self.seed_scores,'new_llm_api_requests':0,
                'candidate_container_invocations':len(tasks),'seed_container_invocations':len(self.seed_executions),
                'seed_lifecycle_seconds':sum(r['total_seconds'] for r in self.seed_executions),
                'fingerprint_pure_seconds':sum(r.get('fingerprint_phase_seconds',0) for r in tasks),
                'pure_full_evaluation_seconds':sum(r.get('result',{}).get('pure_evaluate_seconds',0) for r in tasks),
                'fingerprint_only_container_seconds':sum(r['total_seconds'] for r in tasks if r['action']=='fingerprint'),
                'full_only_container_seconds':sum(r['total_seconds'] for r in tasks if r['action']=='full'),
                'shared_fused_container_seconds':sum(r['total_seconds'] for r in tasks if r['action']=='fused'),
                'worker_readiness_seconds':sum(r.get('worker_ready_seconds',0) for r in tasks),
                'all_candidate_lifecycle_seconds':sum(r['total_seconds'] for r in tasks),
                'exact_and_behavior_lookup_seconds':sum(r['filter_seconds'] for r in self.records),
                'candidate_processing_seconds':sum(r['processing_seconds'] for r in self.records)}


def source_hashes():
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted([*ROOT.glob('*.py'),*ROOT.glob('*.json'),ROOT/'Dockerfile',*ROOT.joinpath('tests').glob('*.py')])}


def run_configuration(runner,mode,size=16,architecture='separate',seed=5491):
    log=RunLog(ROOT/'runs');replay=None
    try:
        log.manifest(phase='2_controlled_trusted_replay',mode=mode,fingerprint_size=size,
                     architecture=architecture,seed=seed,image=runner.image,
                     phase2_source_sha256=source_hashes(),dataset_manifest=read(ROOT/'data/manifest.json'),
                     candidate_stream=stream_manifest(),generated_execution_enabled=False,
                     llm_requests=0,formal_experimental_budget_used=0)
        replay=Replay(runner,mode,size,architecture,log,seed)
        result=replay.run()
        for row in replay.records:write_json(log.directory/f"candidate_{row['candidate_id']}.json",row)
        write_json(log.directory/'representatives.json',replay.reps.all)
        result=log.finish('completed',**result)
        result['run_directory']=str(log.directory)
        return result,replay
    except Exception as exc:
        log.finish('failed',error_type=type(exc).__name__,message=str(exc),
                   counts=replay.counts if replay else None)
        raise


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--image',required=True)
    parser.add_argument('--security-run',type=Path,required=True)
    parser.add_argument('--mode',choices=['standard','exact','behavioral'],default='standard')
    parser.add_argument('--size',type=int,choices=[16,64,128],default=16)
    parser.add_argument('--architecture',choices=['separate','fused'],default='separate')
    args=parser.parse_args();runner=checked_runner(args.image,args.security_run)
    result,_=run_configuration(runner,args.mode,args.size,args.architecture)
    print(json.dumps(result,indent=2))
