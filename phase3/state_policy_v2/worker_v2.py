"""Container-only S2 worker with independently versioned F1 fallback.

Production code requires Linux Docker. Offline tests supply inert core doubles;
this module never imports or executes a generated source on the host.
"""
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

VERSION = 'state-policy-worker-v2.0-runtime-v1'
FALLBACK_VERSION = 'conservative-fallback-f1-v1'
RECOVERABLE = frozenset(('priority must return one score for each feasible bin.',
                        'Priority scores must be finite real numbers under obp-validity-v1',
                        'Fingerprint selected-bin shape/coverage invalid'))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def valid_vector(value, states):
    return (value.get('state_ids') == [s['state_id'] for s in states]
            and len(value.get('decisions', [])) == len(states)
            and all(type(d) is int and d in s['valid_bin_indices']
                    for d, s in zip(value.get('decisions', []), states)))


def execute(payload, root=Path('/app'), core=None, validator=None, clock=perf_counter):
    if core is None:
        if sys.platform != 'linux' or not Path('/.dockerenv').is_file():
            raise PermissionError('Production candidate execution requires Linux container')
        import research_core as core
    elif getattr(core, '_inert_worker_double', False) is not True:
        raise PermissionError('Host tests require inert core double')
    if validator is None:
        from static_policy import validate as validator
    started = clock(); deadline = started + 10
    body = payload['body']; task = payload['task']
    if not isinstance(body, str) or len(body) > 32768 or hashlib.sha256(body.encode()).hexdigest() != payload['body_sha256']:
        raise ValueError('Body identity differs')
    validator('def priority(item, bins):\n' + body, 'priority')
    scope = json.loads((root/'dataset_scope.json').read_text())
    if (task['worker_version'] != VERSION or task['dataset'] != scope['dataset']
            or task['action'] not in scope['actions'] or task['deadline_seconds'] != 10
            or task['fallback'] not in ('F0', 'F1')):
        raise PermissionError('Worker version/action/deadline/fallback differs')
    if task['action'] != 'full' and (task['state_set'] != scope['state_set'] or task['fingerprint_size'] not in scope['sizes']):
        raise PermissionError('State scope differs')
    groups = json.loads((root/'research_data.json').read_text())[task['dataset']]
    if digest(groups) != task['dataset_sha256']:
        raise PermissionError('Dataset substitution')
    out = dict(job_id=payload['job_id'], body_sha256=payload['body_sha256'], task=task,
               worker_version=VERSION, validity_policy='obp-validity-v1',
               full_evaluation_performed=False, fingerprint_valid=False, fallback_used=False,
               fingerprint_invocations=0)
    original = core.namespace_for; namespaces = []; namespace_objects = []

    def fresh(value):
        then = clock()
        try:
            namespace = original(value)
            namespace_objects.append(namespace)
            return namespace
        finally:
            namespaces.append(clock()-then)
    core.namespace_for = fresh
    try:
        if task['action'] in ('fused', 'fingerprint'):
            bank = json.loads((root/'states.json').read_text())
            if digest(bank) != task['state_bank_sha256']:
                raise PermissionError('State bank substitution')
            states = bank[task['state_set']][:task['fingerprint_size']]
            if len(states) != task['fingerprint_size']:
                raise PermissionError('Truncated sealed state bank')
            reps = task['representatives']
            if any(not valid_vector(dict(decisions=r['decisions'], state_ids=[s['state_id'] for s in states]), states) for r in reps):
                raise PermissionError('Malformed accepted representative')
            then = clock()
            try:
                if not task['coverage_supported']:
                    raise ValueError('Fingerprint selected-bin shape/coverage invalid')
                out['fingerprint_invocations'] = 1
                fp = core.fingerprint(body, states)
                if not valid_vector(fp, states):
                    raise ValueError('Fingerprint selected-bin shape/coverage invalid')
            except ValueError as exc:
                if (task['fallback'] != 'F1' or task['action'] != 'fused' or str(exc) not in RECOVERABLE):
                    raise
                out['fallback_used'] = True
                out['fallback_reason'] = dict(type=type(exc).__name__, message=str(exc))
                print(json.dumps(dict(kind='task_stage',stage='fallback_started',reason=out['fallback_reason'])),file=sys.stderr,flush=True)
            else:
                out.update(fp); out['fingerprint_valid'] = True
                if task['action'] == 'fingerprint':
                    return out
                match = next((r['candidate_id'] for r in reps if r['decisions'] == out['decisions']), None)
                if match is not None:
                    out['matched_representative_id'] = match
                    if task.get('required_branch') == 'full':
                        raise RuntimeError('Trusted branch mismatch')
                    return out
            finally:
                out['fingerprint_phase_seconds'] = clock()-then
                print(json.dumps(dict(kind='task_stage', stage='fingerprint_finished',
                                      fingerprint_phase_seconds=clock()-then,
                                      fingerprint_invocations=out['fingerprint_invocations'])), file=sys.stderr, flush=True)
        if not task['allow_full'] or task.get('required_branch') == 'skip':
            raise PermissionError('Full evaluation outside scope')
        if clock() >= deadline:
            raise TimeoutError('Original task deadline exhausted; no fallback retry')
        before = len(namespaces)
        print(json.dumps(dict(kind='task_stage', stage='full_evaluation_started')), file=sys.stderr, flush=True)
        # Unchanged full_evaluation creates a new namespace. It is NOT a second
        # transport job and never resets the external controller's deadline.
        full_started=clock()
        try:
            out.update(core.full_evaluation(body, groups))
        finally:
            out['full_phase_seconds']=clock()-full_started
            print(json.dumps(dict(kind='task_stage',stage='full_evaluation_finished',
                                  full_phase_seconds=clock()-full_started)),file=sys.stderr,flush=True)
        if clock() >= deadline:
            raise TimeoutError('Original task deadline exhausted')
        out.update(full_evaluation_performed=True, full_namespace_seconds=sum(namespaces[before:]))
        return out
    finally:
        core.namespace_for = original
        out['worker_execute_seconds'] = clock()-started
        out['namespace_creations'] = len(namespace_objects)
        out['independent_namespaces'] = len({id(value) for value in namespace_objects}) == len(namespace_objects)
        print(json.dumps(dict(kind='task_stage', stage='worker_finished', worker_execute_seconds=clock()-started,
                              namespace_creations=out['namespace_creations'],
                              independent_namespaces=out['independent_namespaces'])), file=sys.stderr, flush=True)


def main():
    try:
        if sys.platform != 'linux' or not Path('/.dockerenv').is_file():
            raise PermissionError('Linux Docker required')
        sys.path.insert(0, '/app')
        from worker import context
        print(json.dumps(dict(kind='context', context=context())), file=sys.stderr, flush=True)
        line = sys.stdin.buffer.readline(65537)
        if len(line) > 65536 or not line.endswith(b'\n'):
            raise ValueError('Request framing differs')
        result = execute(json.loads(line))
        print(json.dumps(dict(kind='result', result=result), allow_nan=False), flush=True)
        return 0
    except Exception as exc:
        print(json.dumps(dict(kind='error', error=dict(type=type(exc).__name__, message=str(exc)))), file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
