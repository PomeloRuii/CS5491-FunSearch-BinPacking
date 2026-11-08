"""Full held-out evaluation. Production candidate code runs only in Linux Docker."""

from hashlib import sha256
import json
from pathlib import Path
import sys
from time import perf_counter

VERSION = 'heldout-full-worker-v1'


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def task(contract):
    return dict(worker_version=VERSION, action='full', dataset='heldout',
                dataset_sha256=contract['dataset_sha256'], allow_full=True,
                state_bank_sha256=None, fingerprint_size=0, fallback='F0',
                deadline_seconds=10)


def validate_groups(groups, contract):
    if digest(groups) != contract['dataset_sha256'] or set(groups) != set(contract['instance_ids']):
        raise PermissionError('Frozen held-out dataset differs')
    for family, ids in contract['instance_ids'].items():
        if set(groups[family]) != set(ids):
            raise PermissionError('Held-out instance membership differs')
        for instance in groups[family].values():
            if (type(instance['num_items']) is not int
                    or instance['num_items'] != contract['items_per_instance'][family]
                    or len(instance['items']) != instance['num_items']):
                raise PermissionError('Held-out instance coverage differs')


def execute(payload, root=Path('/app'), core=None, validator=None):
    if core is None:
        if sys.platform != 'linux' or not Path('/.dockerenv').is_file():
            raise PermissionError('Production candidate execution requires Linux Docker')
        import research_core as core
    elif getattr(core, '_inert_worker_double', False) is not True:
        raise PermissionError('Host tests require inert numerical doubles')
    if validator is None:
        from static_policy import validate as validator
    started = perf_counter()
    contract = json.loads((root/'heldout_contract.json').read_text(encoding='utf-8'))
    if payload['task'] != dict(task(contract), representatives=[]):
        raise PermissionError('Held-out worker action or task scope differs')
    body = payload['body']
    if (not isinstance(body, str) or not 0 < len(body) <= 32768
            or sha256(body.encode()).hexdigest() != payload['body_sha256']):
        raise PermissionError('Candidate body seal differs')
    validator('def priority(item, bins):\n'+body, 'priority')
    groups = payload['groups']
    validate_groups(groups, contract)
    original = core.namespace_for
    namespaces = []

    def fresh(source):
        namespace = original(source)
        namespaces.append(namespace)
        return namespace

    core.namespace_for = fresh
    try:
        print(json.dumps(dict(kind='task_stage', stage='full_evaluation_started')), file=sys.stderr, flush=True)
        result = core.full_evaluation(body, groups)
        if perf_counter()-started >= 10:
            raise TimeoutError('Held-out task deadline exhausted')
        if len(namespaces) != 1:
            raise RuntimeError('Unexpected candidate namespace count')
        result.update(job_id=payload['job_id'], body_sha256=payload['body_sha256'], task=payload['task'],
                      worker_version=VERSION, validity_policy='obp-validity-v1',
                      full_evaluation_performed=True, fingerprint_valid=False, fingerprint_invocations=0,
                      fallback_used=False, namespace_creations=1, independent_namespaces=True)
        return result
    finally:
        core.namespace_for = original
        print(json.dumps(dict(kind='task_stage', stage='worker_finished',
                              worker_execute_seconds=perf_counter()-started,
                              namespace_creations=len(namespaces), independent_namespaces=len(namespaces)==1)),
              file=sys.stderr, flush=True)


def main():
    try:
        if sys.platform != 'linux' or not Path('/.dockerenv').is_file():
            raise PermissionError('Linux Docker required')
        from worker import context
        print(json.dumps(dict(kind='context', context=context())), file=sys.stderr, flush=True)
        line = sys.stdin.buffer.readline(65537)
        if len(line) > 65536 or not line.endswith(b'\n'):
            raise ValueError('Request framing differs')
        result = execute(json.loads(line))
        print(json.dumps(dict(kind='result', result=result), allow_nan=False), flush=True)
        return 0
    except Exception as exc:
        print(json.dumps(dict(kind='error', error=dict(type=type(exc).__name__, message=str(exc)))),
              file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())

