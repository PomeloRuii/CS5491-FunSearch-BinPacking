"""Narrow trusted regressions for the checker-only image delta; no model source."""
import hashlib
import bootstrap3
from bootstrap3 import ROOT, PROJECT
from common import read, write, file_hash
from backend_policy_v2 import PolicyV2Runner, RECEIPT, VALIDATION
from catalogue import reviewed_candidate, require_reviewed
from candidates import Candidate
from interface import parse_candidate
from replay import accepted_full
from static_policy import validate, POLICY_ID

# Handcrafted fixtures, not imported Qwen code. Each has a finite exact permit.
PROBES = {
    'local_rebinding_first_fit': '    bins = np.asarray(bins, dtype=float)\n    return -np.arange(len(bins), dtype=float)',
    'positional_output_rejected': '    alias = bins\n    x = np.add(bins, item, alias)\n    return x',
    'alias_write_rejected': '    alias = bins\n    alias[0] = 0\n    return alias',
    'overwrite_input_rejected': '    x = np.median(bins, overwrite_input=True)\n    return bins',
}
_PERMITS = {}


def probe_candidate(name):
    source = 'def priority(item, bins):\n'+PROBES[name]
    assert hashlib.sha256(source.encode()).hexdigest() != 'a6e1b252610023b6e3c968a00d8be3ee225951c91d657d8e557adbbf5661b309'
    permit=object();_PERMITS[permit]=(name,source)
    return Candidate(source,'hand_reviewed_policy_v2_probe',fixture=name,permit=permit)


class ProbeRunner(PolicyV2Runner):
    def check_candidate(self, candidate):
        if candidate.origin == 'hand_reviewed_policy_v2_probe':
            if _PERMITS.get(candidate.permit) != (candidate.fixture,candidate.text):
                raise PermissionError('Unreviewed probe source')
        else:
            # This validation runner can never mint/accept a model permit.
            require_reviewed(candidate)

    def _request_payload(self, candidate, parsed, body, job_id, body_hash):
        self.check_candidate(candidate)
        value=super()._request_payload(candidate,parsed,body,job_id,body_hash)
        # Exercise the worker AST check with only the reviewed sources above.
        value['model_origin']=True
        return value


def main():
    out=ROOT/'slot12_recovery/trusted_validation';out.mkdir(exist_ok=False)
    runner=ProbeRunner();tasks=[]
    expected={'first_fit':{'OR3':-213.08333333333334,'Weibull 5k':-2077.6666666666665},
              'best_fit':{'OR3':-212.41666666666666,'Weibull 5k':-2072.6666666666665},
              'seed':{'OR3':-500.0,'Weibull 5k':-5000.0}}
    for fixture,scores in expected.items():
        candidate=reviewed_candidate(fixture,'priority');parsed,_=validate(candidate.text,'priority')
        record=runner.run_task(candidate,parsed,'full')
        write(out/(fixture+'.json'),record);tasks.append(record)
        if not accepted_full(record,runner.data['development']) or record['result']['scores_per_group']!=scores:
            raise AssertionError('Trusted baseline changed: '+fixture)
    for name in PROBES:
        candidate=probe_candidate(name);parsed=parse_candidate(candidate.text,'priority')
        record=runner.run_task(candidate,parsed,'full')
        write(out/(name+'.json'),record);tasks.append(record)
        if name=='local_rebinding_first_fit':
            if not accepted_full(record,runner.data['development']) or record['result']['scores_per_group']!=expected['first_fit']:
                raise AssertionError('Worker failed safe rebinding/unchanged packing')
        elif (record['status']=='ok' or record.get('full_evaluation_started')
                or not any(m.get('kind')=='error' for m in record.get('worker_messages',[]))):
            raise AssertionError('Worker accepted input mutation: '+name)
    if not all(r['cleanup_verified'] for r in tasks):
        raise AssertionError('Cleanup failed')
    # The exact model artifact remains blocked before Docker task dispatch.
    from generation3 import load_candidate
    pool=ROOT/'feedback_generated/20261102T052500617671Z_74cc148e/pool.json'
    candidate=load_candidate(pool,read(pool)['candidates'][0])
    try:PolicyV2Runner().check_candidate(candidate)
    except PermissionError:pass
    else:raise AssertionError('Model execution without a new grant accepted')
    result={'status':'PASS','static_policy':POLICY_ID,'build_receipt_sha256':file_hash(RECEIPT),
        'scope':'Checker delta, actual container restrictions, complete trusted baselines and cleanup; inherited unchanged isolation controls; not a full repeated security suite',
        'trusted_worker_tasks':len(tasks),'trusted_complete_evaluations':4,'worker_static_refusals':3,
        'all_cleanup_verified':True,'model_origin_execution_gate_refused':True,
        'llm_generation_requests':0,'llm_generated_source_executions':0,
        'baseline_scores_per_group':expected,'runtime_validity_policy':'obp-validity-v1',
        'isolation_policy_sha256':file_hash(PROJECT/'phase1b/phase1c/policy.json'),
        'audit_scope_runtime_retested':False,
        'audit_scope_image_delta_verified':'same one-file checker delta and unchanged parent/runtime config'}
    write(VALIDATION,result)
    write(ROOT/'acceptance_policy.json',{'policy':POLICY_ID,
        'static_policy_sha256':file_hash(ROOT/'static_policy.py'),
        'build_receipt_sha256':file_hash(RECEIPT),'validation_sha256':file_hash(VALIDATION),
        'comparison_modes':['standard','exact','behavioral'],'fingerprint_sizes':[16,64,128],
        'runtime_validity_policy':'obp-validity-v1','historical_policy':'phase3-numerical-ast-v1',
        'versioning':'Applies prospectively; original v1 decisions and receipts are not reclassified.',
        'generated_execution_enabled_globally':False})
    print(str(VALIDATION)+' PASS; no model code executed')


if __name__=='__main__':main()
