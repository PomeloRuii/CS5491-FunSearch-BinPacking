"""Reviewed-source adapter over the existing unchanged container security policy."""
import json
from pathlib import Path
import hashlib

import phase2_bootstrap
from phase2_bootstrap import ROOT,PHASE1B
from candidate_runner import CandidateRunner
from catalogue import require_reviewed
from trusted_cases import GROUPS,content_hash
from validate import require_validation_receipt


def read(path):return json.loads(Path(path).read_text(encoding='utf-8'))


class ResearchRunner(CandidateRunner):
    def __init__(self,image):
        super().__init__(image)
        self.manifest=read(ROOT/'data/manifest.json')
        self.data=read(ROOT/'data/research_data.json')
        self.task=None

    def _require_candidate_permission(self,candidate):require_reviewed(candidate)

    def _request_payload(self,candidate,parsed,body,job_id,body_hash):
        return {**super()._request_payload(candidate,parsed,body,job_id,body_hash),'task':self.task}

    def task_spec(self,action,dataset='development',size=16,state_set='fingerprint',representatives=None):
        groups={'OR3':GROUPS['OR3']} if dataset=='legacy_validation' else self.data[dataset]
        return {'action':action,'dataset':dataset,'dataset_sha256':content_hash(groups),
                'state_bank_sha256':self.manifest['state_bank_sha256'],
                'fingerprint_size':size,'state_set':state_set,
                'representatives':representatives or []}

    def run_task(self,candidate,parsed,action,dataset='development',size=16,state_set='fingerprint',representatives=None):
        require_reviewed(candidate)  # No model-origin code may reach task preparation or Docker.
        self.task=self.task_spec(action,dataset,size,state_set,representatives)
        record=self.run_candidate(candidate,parsed,10)
        result=record.get('result',{})
        stages=[m for m in record.get('worker_messages',[]) if m.get('kind')=='task_stage']
        record['full_evaluation_started']=any(m.get('stage')=='full_evaluation_started' for m in stages)
        record['fingerprint_phase_seconds']=sum(m.get('fingerprint_seconds',0) for m in stages)
        context=any(m.get('kind')=='context' for m in record.get('worker_messages',[]))
        if record['status']=='ok' and (not context or not record['cleanup_verified']
              or result.get('task')!=self.task or result.get('validity_policy')!='obp-validity-v1'):
            record['status']='invalid_protocol_or_cleanup'
        if not record.get('cleanup_verified'):
            raise RuntimeError('Container cleanup unverified; stop rather than continue replay')
        return record


def checked_runner(image,security_run):
    security_run=Path(security_run);summary=read(security_run/'summary.json');manifest=read(security_run/'manifest.json')
    sources={p:hashlib.sha256((PHASE1B/p).read_bytes()).hexdigest() for p in manifest['source_sha256']}
    require_validation_receipt(summary,manifest,image,sources)
    # Research image build manifest pins the new worker and research files too.
    build=read(ROOT/'build_receipt.json')
    if build['ImageId']!=image:raise PermissionError('Research image identity differs')
    for p,digest in build['research_source_sha256'].items():
        if hashlib.sha256((ROOT/p).read_bytes()).hexdigest()!=digest:
            raise PermissionError('Research worker/data changed since image build: '+p)
    return ResearchRunner(image)
