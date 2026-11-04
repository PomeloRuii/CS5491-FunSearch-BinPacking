"""Finite v1 adapter over unchanged hardened disposable-container transport."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap3
from candidate_runner import CandidateRunner
from static_policy import validate
from development_data_v1 import load_development
from .protocol import VERSION, DEV, read, verify_branch, confirmed_terminal, expected_runtime_rejection


class Runner(CandidateRunner):
    def __init__(self,image,authority,scope='development'):
        self.authority=authority;self.scope=scope;self.task=None
        self.data={'development':load_development()} if scope=='development' else {'boundary':{}}
        super().__init__(image)

    def check_candidate(self,candidate):
        self.authority.check_source(candidate)
        name=self.authority.active['expected_name']
        validate(candidate.text,name,candidate.finish_reason)

    def _require_candidate_permission(self,candidate):self.check_candidate(candidate)

    def _request_payload(self,candidate,parsed,body,job_id,body_hash):
        return {**super()._request_payload(candidate,parsed,body,job_id,body_hash),
                'model_origin':candidate.origin=='ollama','task':self.task}

    def run_task(self,candidate,parsed,action,**kwargs):
        self.check_candidate(candidate)
        slot=self.authority.active
        reps=kwargs.get('representatives',[]) if action=='fused' else []
        self.task={**slot['task'],'representatives':reps}
        if self.task['action']!=action:raise PermissionError('Action outside selected slot')
        self.authority.reserve(candidate,self.image,self.task)
        record=self.run_candidate(candidate,parsed,10)
        try:
            if record.get('body_sha256')!=slot['body_sha256']:raise RuntimeError('Returned candidate body identity differs')
            confirmed_terminal(record)
            stages=[m for m in record.get('worker_messages',[]) if m.get('kind')=='task_stage']
            record['full_evaluation_started']=any(m.get('stage')=='full_evaluation_started' for m in stages)
            record['fingerprint_phase_seconds']=sum(m.get('fingerprint_phase_seconds',0) for m in stages)
            if record['status']=='ok':
                if slot['role']=='normal' and slot['source_id']==5:
                    raise RuntimeError('Previously invalid unchanged source unexpectedly accepted; investigate')
                if not any(m.get('kind')=='context' for m in record.get('worker_messages',[])):
                    raise RuntimeError('Missing worker context')
                bank=read(DEV/'states.json') if self.scope=='development' else read(Path(__file__).parent/'image_contexts_v1/boundary/states.json')
                states=bank[self.task['state_set']][:self.task['fingerprint_size']] if action!='full' else []
                verify_branch(record['result'],self.task,states)
                if record['result']['full_evaluation_performed']:
                    from replay import accepted_full
                    if not accepted_full(record,self.data['development']):raise RuntimeError('Incomplete/invalid full fitness protocol')
                if self.task.get('required_branch')=='skip' and record['result']['full_evaluation_performed']:
                    raise RuntimeError('Trusted skip unexpectedly evaluated')
            else:expected_runtime_rejection(record,slot)
        except Exception:
            record['protocol_stop']=True
            raise
        finally:
            self.authority.record_result(record)
        return record
