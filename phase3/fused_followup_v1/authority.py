"""One finite campaign, atomic one-use slots, no approval minting or retry."""
import os
import json
from pathlib import Path
from .protocol import PROJECT, VERSION, read, digest, file_hash, write_new


def durable(path,value):
    with Path(path).open('x',encoding='utf-8') as stream:
        stream.write(json.dumps(value,indent=2,allow_nan=False)+'\n');stream.flush();os.fsync(stream.fileno())


def verify_manifest(path):
    m=read(path)
    if (m['version']!=VERSION or m['maximum_container_dispatches']!=45
        or len(m['dispatch_slots'])!=45 or m['maximum_full_evaluations']!=41
        or m['maximum_fingerprint_invocations']!=25 or m['heldout_access'] is not False
        or m['new_generation_calls']!=0 or m['main_calls']!=0 or m['automatic_retries']!=0
        or m['maximum_wall_seconds_per_task']!=10 or m['parallelism']!=1):
        raise PermissionError('Finite scope/ceilings differ')
    for relative,expected in m['control_sha256'].items():
        target=(PROJECT/relative).resolve()
        if not target.is_relative_to(PROJECT) or file_hash(target)!=expected:
            raise PermissionError('Control/data/source seal differs: '+relative)
    slots=m['dispatch_slots']
    if len({s['slot_id'] for s in slots})!=45 or any(s['slot_id']!=digest({k:v for k,v in s.items() if k!='slot_id'}) for s in slots):
        raise PermissionError('Task slot identity differs')
    if sum(s['task']['allow_full'] for s in slots)!=41 or sum(s['task']['action'] in ('fused','fingerprint') for s in slots)!=25:
        raise PermissionError('Action ceilings differ')
    return m


class Authority:
    def __init__(self,manifest,approval,state_root=None):
        self.manifest=verify_manifest(manifest);self.hash=file_hash(manifest)
        a=read(approval)
        if (a.get('approved') is not True or a.get('kind')!='finite-fused-followup-v1'
            or a.get('manifest_sha256')!=self.hash or not a.get('user_authorization_verbatim')
            or not a.get('recorded_at_utc') or a.get('residual_risks_acknowledged') is not True):
            raise PermissionError('New explicit exact-manifest approval is required')
        self.root=Path(state_root or Path(manifest).parent/'dispatch_state')/self.hash
        self.root.mkdir(parents=True,exist_ok=True)
        durable(self.root/'campaign_started.json',{'manifest_sha256':self.hash,'state':'one_use_no_resume'})
        self.slots={s['slot_id']:s for s in self.manifest['dispatch_slots']}
        self.active=None;self.pending=None;self.reps={};self.completed=[]

    def select(self,configuration,source_id):
        if self.pending is not None:raise RuntimeError('Missing terminal receipt')
        matches=[s for s in self.slots.values() if s['configuration']==configuration and s['source_id']==source_id]
        if len(matches)!=1:raise PermissionError('No unique scoped task')
        self.active=matches[0]

    def check_source(self,candidate):
        if self.active is None:raise PermissionError('Missing task context')
        slot=self.active
        if (candidate.finish_reason!='stop' or file_hash(PROJECT/slot['source_file'])!=slot['source_sha256']
            or __import__('hashlib').sha256(candidate.text.encode()).hexdigest()!=slot['source_sha256']):
            raise PermissionError('Source substitution/incomplete output')
        if slot['role']=='normal' or slot['role']=='boundary_model':
            if candidate.origin!='ollama' or candidate.response_metadata.get('artifact_candidate_id')!=slot['source_id']:
                raise PermissionError('Model source identity differs')
            if candidate.response_metadata.get('artifact_manifest_sha256')!=self.manifest['candidate_pool_sha256']:
                raise PermissionError('Frozen pool differs')
        elif candidate.origin!='trusted_fixture':raise PermissionError('Trusted fixture origin differs')

    def representatives(self):
        return self.reps.setdefault(self.active['configuration'],[])

    def reserve(self,candidate,image,task):
        self.check_source(candidate);slot=self.active
        static={k:v for k,v in task.items() if k!='representatives'}
        if image!=slot['image'] or static!=slot['task']:
            raise PermissionError('Task/image/data substitution')
        expected=self.representatives() if task['action']=='fused' else []
        if slot['role']=='trusted_match':expected=slot['trusted_representatives']
        if task['representatives']!=expected:raise PermissionError('Representative not from this arm accepted results')
        directory=self.root/slot['slot_id'];directory.mkdir(exist_ok=False)
        durable(directory/'dispatch.json',{'scope':slot,'request_sha256':digest(task),'representatives':expected,
                                         'status':'reserved_before_dispatch_no_retry'})
        self.pending=directory

    def record_result(self,record):
        if self.pending is None:raise RuntimeError('Missing reservation')
        durable(self.pending/'result.json',record)
        self.completed.append(self.active['slot_id']);self.pending=None

    def accept(self,candidate_id,record):
        """Only caller-validated complete fitness may create a representative."""
        from replay import accepted_full
        from development_data_v1 import load_development
        if not accepted_full(record,load_development()):raise RuntimeError('No complete finite full result')
        decisions=record['result'].get('decisions')
        if decisions is not None and not any(r['decisions']==decisions for r in self.representatives()):
            self.representatives().append({'candidate_id':candidate_id,'decisions':decisions})
