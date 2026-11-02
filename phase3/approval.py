"""Finite source/task approval receipts and crash-conservative durable accounting.

Receipts are trusted operator records, not signatures or a defense against a host
administrator. This module never creates an approved receipt from a CLI flag.
"""
from pathlib import Path
import os
import json
import bootstrap3
from bootstrap3 import ROOT, PROJECT
from common import read, write, append, digest, file_hash, stamp

def durable_reservation(path,value):
    with Path(path).open('x',encoding='utf-8') as stream:
        stream.write(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
        stream.flush();os.fsync(stream.fileno())

def approved_receipt(path, kind, bound_hash):
    value = read(path)
    if (value.get('approved') is not True or value.get('kind') != kind
        or value.get('manifest_sha256') != bound_hash
        or not value.get('user_authorization_verbatim') or not value.get('recorded_at_utc')
        or value.get('residual_risks_acknowledged') is not True):
        raise PermissionError('Explicit matching user approval receipt required')
    return value

def check_controls(manifest):
    for path, expected in manifest.get('control_sha256', {}).items():
        target=(PROJECT/path).resolve()
        if not target.is_relative_to(PROJECT) or file_hash(target)!=expected:
            raise PermissionError('Approval-bound control source changed: '+path)

def control_sources():
    files=list(ROOT.glob('*.py'))
    files += [PROJECT/'phase2'/n for n in ('phase2_bootstrap.py','replay.py','filters.py','research_worker.py','catalogue.py')]
    files += [PROJECT/'phase1b'/n for n in ('phase1d/interface.py','phase1d/candidate_runner.py',
        'phase1d/candidate_worker.py','phase1d/candidates.py','phase1d/ollama_adapter.py',
        'phase1c/container_runner.py','phase1c/policy.json','trusted_cases.py','run_log.py','reference/specification.txt')]
    files += list((PROJECT/'phase1b/reference/implementation').glob('*.py'))
    files += [PROJECT/'phase2/data'/n for n in ('manifest.json','research_data.json','states.json')]
    return {p.relative_to(PROJECT).as_posix():file_hash(p) for p in sorted(set(files))}

class GenerationBudget:
    def __init__(self, request_manifest, approval, state_root=None):
        self.manifest = read(request_manifest)
        self.hash = file_hash(request_manifest)
        self.receipt = approved_receipt(approval, 'generation_only', self.hash)
        check_controls(self.manifest)
        if (self.manifest['max_new_requests'] > 12 or self.manifest['max_new_requests'] < 1
            or self.manifest['main_calls'] != 0 or self.manifest['max_attempts_per_call'] != 1):
            raise PermissionError('Prospective pilot scope exceeds declared cap')
        self.root = Path(state_root or ROOT/'dispatch_state')/self.hash
        self.root.mkdir(parents=True, exist_ok=True)

    def reserve(self, candidate_id, payload, purpose='pool'):
        # mkdir is an atomic exclusive reservation on this local filesystem.
        # Allocation has a finite slot set; concurrent users cannot exceed it.
        total=self.manifest['max_new_requests']
        initial=self.manifest.get('initial_fixed_pool_calls',total)
        if not 0<=initial<=total:raise PermissionError('Invalid pool/feedback allocation')
        if purpose=='pool':slots=range(1,initial+1)
        elif purpose=='feedback':slots=range(initial+1,total+1)
        else:raise PermissionError('Unknown generation purpose')
        for slot in slots:
            target = self.root/f'call_{slot:03d}'
            try: target.mkdir()
            except FileExistsError: continue
            value = {'reservation':stamp(),'candidate_id':candidate_id,'call_slot':slot,
                     'payload_sha256':digest(payload),'budget_class':'pilot',
                     'generation_purpose':purpose,
                     'delivery_status':'reserved_before_dispatch_unknown_until_response',
                     'approval_manifest_sha256':self.hash}
            durable_reservation(target/'request.json',value)
            return target, value
        raise PermissionError('Generation allocation exhausted; uncertain calls are not retried')

class ExecutionAuthority:
    def __init__(self, manifest, approval, state_root=None):
        self.path = Path(manifest); self.manifest = read(manifest); self.hash = file_hash(manifest)
        approved_receipt(approval, 'finite_source_execution', self.hash)
        check_controls(self.manifest)
        if self.manifest.get('fused_model_execution') is not False:
            raise PermissionError('Model fused execution is outside the reviewed scope')
        self.sources = {r['candidate_id']:r for r in self.manifest['candidates']}
        self.slots = {r['slot_id']:r for r in self.manifest['dispatch_slots']}
        if (len(self.slots) != len(self.manifest['dispatch_slots']) or len(self.sources)!=len(self.manifest['candidates'])
            or self.manifest.get('maximum_container_dispatches')!=len(self.slots)
            or self.manifest.get('maximum_full_evaluations')!=sum(s['action']=='full' for s in self.slots.values())
            or self.manifest.get('maximum_wall_seconds_per_task')!=10
            or self.manifest.get('heldout_access') is not False):
            raise PermissionError('Declared dispatch/evaluation maxima or scope differ from finite slot set')
        self.root = Path(state_root or ROOT/'dispatch_state')/self.hash
        self.root.mkdir(parents=True, exist_ok=True)
        self.context = None; self.last = None

    def set_context(self, configuration, role, candidate_id):
        self.context = (configuration,role,candidate_id)

    def check_source(self, candidate):
        if candidate.origin != 'ollama' or candidate.finish_reason != 'stop':
            raise PermissionError('Only explicitly approved complete model sources')
        metadata = candidate.response_metadata
        selected = self.sources.get(metadata.get('artifact_candidate_id'))
        sha = __import__('hashlib').sha256(candidate.text.encode()).hexdigest()
        if (selected is None or selected['source_sha256'] != sha
            or metadata.get('artifact_manifest_sha256') != self.manifest['candidate_pool_sha256']
            or metadata.get('expected_name') != selected['expected_name']):
            raise PermissionError('Candidate substitution or out-of-pool source refused')
        if self.context is None: raise PermissionError('Explicit execution configuration/role required')

    def reserve(self, candidate, image, task):
        self.check_source(candidate)
        configuration, role, candidate_id = self.context
        if candidate_id != candidate.response_metadata['artifact_candidate_id']:
            raise PermissionError('Candidate ID substitution refused')
        scope = {'configuration':configuration,'role':role,'candidate_id':candidate_id,
                 'source_sha256':__import__('hashlib').sha256(candidate.text.encode()).hexdigest(),
                 'image':image,'action':task['action'],'dataset':task['dataset'],
                 'dataset_sha256':task['dataset_sha256'], 'state_bank_sha256':task['state_bank_sha256'],
                 'state_set':task['state_set'],'fingerprint_size':task['fingerprint_size']}
        slot_id = digest(scope)
        if self.slots.get(slot_id) != {'slot_id':slot_id, **scope}:
            raise PermissionError('Image, data, action, size or scope differs from approval')
        target = self.root/slot_id
        try: target.mkdir()
        except FileExistsError: raise PermissionError('Authorized slot already reserved; no implicit retry')
        durable_reservation(target/'dispatch.json',{'scope':scope,'status':'reserved_before_dispatch','timestamp':stamp()})
        self.last = target

    def record_result(self, record):
        if self.last is None: raise PermissionError('Missing dispatch reservation')
        write(self.last/'result.json',record); self.last = None

