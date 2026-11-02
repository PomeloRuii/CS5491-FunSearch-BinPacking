"""Versioned policy-only images over frozen Phase 3 data/transport layers."""
import bootstrap3
from bootstrap3 import ROOT, PROJECT
from common import read, file_hash
from backend3 import MinimizedRunner
from backend import ResearchRunner
from static_policy import POLICY_ID

RECEIPT = ROOT/'slot12_recovery/build_receipt.json'
VALIDATION = ROOT/'slot12_recovery/validation.json'


def check_build(scope):
    if scope not in ('development', 'audit'):
        raise PermissionError('Only existing minimized development/audit scopes')
    receipt = read(RECEIPT); build = receipt['images'][scope]
    old = read(ROOT/'build_receipt.json')['images'][scope]
    if (receipt['static_policy'] != POLICY_ID
            or build['base_image'] != old['ImageId']
            or receipt['static_policy_sha256'] != file_hash(ROOT/'static_policy.py')
            or receipt['isolation_policy_sha256'] != file_hash(PROJECT/'phase1b/phase1c/policy.json')):
        raise PermissionError('Active static/isolation/base image seals differ')
    for name, sha in old['context_sha256'].items():
        if file_hash(ROOT/'build_contexts'/scope/name) != sha:
            raise PermissionError('Frozen base context changed: '+name)
    for source, name in [('worker3.py','candidate_worker.py'),('common.py','common.py')]:
        if file_hash(ROOT/source) != old['context_sha256'][name]:
            raise PermissionError('Worker transport changed; new validation required')
    for name, sha in receipt['patch_context_sha256'].items():
        if file_hash(ROOT/'slot12_recovery/image_patch'/name) != sha:
            raise PermissionError('Policy-only image patch changed')
    if (build['dataset_sha256'] != old['dataset_sha256']
            or build['state_bank_sha256'] != old['state_bank_sha256']
            or build['scope'] != old['scope']):
        raise PermissionError('Frozen data/state scope differs')
    return build


class PolicyV2Runner(MinimizedRunner):
    def __init__(self, scope='development', authority=None):
        build = check_build(scope)
        ResearchRunner.__init__(self, build['ImageId'])
        self.scope, self.build, self.authority = scope, build, authority
        self.data = read(ROOT/'build_contexts'/scope/'research_data.json')


def checked_runner(scope='development', authority=None):
    active = read(ROOT/'acceptance_policy.json')
    validation = read(VALIDATION)
    if (active['policy'] != POLICY_ID
            or active['static_policy_sha256'] != file_hash(ROOT/'static_policy.py')
            or active['build_receipt_sha256'] != file_hash(RECEIPT)
            or active['validation_sha256'] != file_hash(VALIDATION)
            or active['comparison_modes'] != ['standard','exact','behavioral']
            or active['fingerprint_sizes'] != [16,64,128]
            or validation['status'] != 'PASS'
            or validation['build_receipt_sha256'] != file_hash(RECEIPT)):
        raise PermissionError('Shared active policy/build/validation mismatch')
    return PolicyV2Runner(scope, authority)
