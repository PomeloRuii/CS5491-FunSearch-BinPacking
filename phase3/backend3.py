"""Scoped extension of the existing container controller; default model gate closed."""
from pathlib import Path
import bootstrap3
from bootstrap3 import ROOT, PHASE2
from common import read, file_hash
from backend import ResearchRunner
from catalogue import require_reviewed
from static_policy import validate
from validate import expected_outcome
from container_runner import PROBES, POLICY

class MinimizedRunner(ResearchRunner):
    def __init__(self, scope='development', authority=None):
        build = read(ROOT/'build_receipt.json')['images'][scope]
        super().__init__(build['ImageId'])
        self.scope, self.build, self.authority = scope, build, authority
        self.data = read(ROOT/'build_contexts'/scope/'research_data.json')

    def check_candidate(self, candidate):
        if candidate.origin == 'ollama':
            # Execution grant is checked on every logical attempt, even cache-only skips.
            if self.authority is None: raise PermissionError('No explicit source-bound model execution approval')
            self.authority.check_source(candidate)
            validate(candidate.text, candidate.response_metadata['expected_name'], candidate.finish_reason)
        else: require_reviewed(candidate)

    def _require_candidate_permission(self, candidate):
        self.check_candidate(candidate)

    def _request_payload(self, candidate, parsed, body, job_id, body_hash):
        value = super()._request_payload(candidate,parsed,body,job_id,body_hash)
        value['model_origin'] = candidate.origin == 'ollama'
        return value

    def task_spec(self, action, dataset='development', size=16, state_set='fingerprint', representatives=None):
        spec = self.build['scope']
        if (dataset != self.scope or action not in spec['actions']
            or (action != 'full' and (size not in spec['sizes'] or state_set != spec['state_set']))):
            raise PermissionError('Task is outside minimized image scope')
        return {'action':action,'dataset':dataset,'dataset_sha256':self.build['dataset_sha256'],
                'state_bank_sha256':self.build['state_bank_sha256'],'fingerprint_size':size,
                'state_set':state_set,'representatives':representatives or []}

    def run_task(self, candidate, parsed, action, dataset='development', size=16, state_set='fingerprint', representatives=None):
        # This implementation preserves the prior controller/protocol/timing and cleanup path.
        self.check_candidate(candidate)
        self.task = self.task_spec(action,dataset,size,state_set,representatives)
        if candidate.origin == 'ollama':
            if action == 'fused': raise PermissionError('Fused path is not authorized for model source')
            self.authority.reserve(candidate,self.image,self.task)  # Durable before dispatch, no retries.
        record = self.run_candidate(candidate,parsed,10)
        result = record.get('result',{})
        stages = [m for m in record.get('worker_messages',[]) if m.get('kind')=='task_stage']
        record['full_evaluation_started'] = any(m.get('stage')=='full_evaluation_started' for m in stages)
        record['fingerprint_phase_seconds'] = sum(m.get('fingerprint_seconds',0) for m in stages)
        context = any(m.get('kind')=='context' for m in record.get('worker_messages',[]))
        if record['status']=='ok' and (not context or not record['cleanup_verified']
            or result.get('task')!=self.task or result.get('validity_policy')!='obp-validity-v1'):
            record['status']='invalid_protocol_or_cleanup'
        if candidate.origin == 'ollama': self.authority.record_result(record)
        if not record.get('cleanup_verified'): raise RuntimeError('Cleanup unverified; stop')
        return record

def checked_runner(scope='development', authority=None):
    if (ROOT/'acceptance_policy.json').exists():
        from backend_policy_v2 import checked_runner as active_runner
        return active_runner(scope, authority)
    build = read(ROOT/'build_receipt.json')['images'][scope]
    for name,sha in build['context_sha256'].items():
        if file_hash(ROOT/'build_contexts'/scope/name)!=sha: raise PermissionError('Built context changed')
    for source,name in [('worker3.py','candidate_worker.py'),('static_policy.py','static_policy.py'),('common.py','common.py')]:
        if file_hash(ROOT/source)!=build['context_sha256'][name]: raise PermissionError('Worker source changed since build')
    receipt = read(ROOT/'validation.json')
    if receipt.get('status')!='PASS' or receipt['images']!={s:b['ImageId'] for s,b in read(ROOT/'build_receipt.json')['images'].items()}:
        raise PermissionError('Equivalent isolation and evaluation validation required')
    if receipt['policy_sha256']!=file_hash(bootstrap3.PROJECT/'phase1b/phase1c/policy.json'):
        raise PermissionError('Execution policy changed')
    return MinimizedRunner(scope,authority)
