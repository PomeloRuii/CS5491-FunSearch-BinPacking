"""Host observer v1.1: corrected Windows event handling, same sealed campaign.

No campaign is started without a fresh exact-request approval. Use python -m.
Original observer, controller, consumed grant and task set remain unchanged.
"""
import argparse
import hashlib
import importlib.abc
import json
import os
from pathlib import Path
import runpy
import sys
from time import perf_counter
from ..recovery_v1_1.windows_popen_guard import validate_popen

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent


def main(args):
    manifest_path=args.manifest.resolve();approval_path=args.approval.resolve()
    actual=hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    if actual!=args.expected_sha256:raise PermissionError('Reviewed replacement request seal differs')
    sys.path.insert(0,str(ROOT))
    from phase3.fused_followup_v1.authority import verify_manifest
    manifest=verify_manifest(manifest_path)
    if manifest.get('request_revision')!='fused-followup-v1-recovery-1.2':raise PermissionError('Not the replacement request')
    approved=json.loads(approval_path.read_text(encoding='utf-8'))
    if (approved.get('approved') is not True or approved.get('kind')!='finite-fused-followup-v1'
        or approved.get('manifest_sha256')!=actual or not approved.get('user_authorization_verbatim')
        or not approved.get('recorded_at_utc') or approved.get('residual_risks_acknowledged') is not True):
        raise PermissionError('Fresh explicit matching approval required')
    state=manifest_path.parent/'dispatch_state'/actual
    if state.exists():raise PermissionError('Replacement campaign already entered; no resume/reset')
    # Resolve the same CLI as the unchanged transport, without invoking it.
    sys.path.insert(0,str(ROOT/'phase3'))
    import bootstrap3
    from container_runner import docker_path
    docker=docker_path()
    if not docker:raise RuntimeError('Existing Docker executable unavailable')
    # Exercise the native Windows representation before consuming any authority.
    import subprocess
    trial=[docker,'info','--format','{{json .}}']
    validate_popen(None,subprocess.list2cmdline(trial) if sys.platform=='win32' else trial,docker)
    allowed={str((ROOT/p).resolve()).casefold() for p in manifest['control_sha256'] if p.endswith('.json')}
    allowed|={str(manifest_path).casefold(),str(approval_path).casefold()}
    output=HERE/'observations';output.mkdir(exist_ok=False)
    opened={};blocked=[];commands=[];hook_seconds=0.;events=0
    class NoLegacy(importlib.abc.MetaPathFinder):
        def find_spec(self,fullname,path=None,target=None):
            if 'bin_packing_utils' in fullname:
                blocked.append({'kind':'legacy_import','module':fullname})
                raise PermissionError('Legacy reference-data import is prohibited')
    sys.meta_path.insert(0,NoLegacy())
    def audit(event,event_args):
        nonlocal hook_seconds,events
        then=perf_counter()
        try:
            if event=='socket.connect':
                blocked.append({'kind':'network_connect'})
                raise PermissionError('No host network/model request authorized')
            if event=='subprocess.Popen':
                try:argv=validate_popen(event_args[0],event_args[1],docker)
                except PermissionError:
                    blocked.append({'kind':'unexpected_subprocess','executable':str(event_args[0])})
                    raise
                commands.append(argv);return
            if event!='open' or not isinstance(event_args[0],(str,bytes)):return
            path=Path(os.fsdecode(event_args[0])).resolve()
            if not path.is_relative_to(ROOT):return
            relative=path.relative_to(ROOT).as_posix();lower=relative.casefold()
            mode=event_args[1];flags=event_args[2]
            reading=(isinstance(mode,str) and ('r' in mode or '+' in mode)) or mode is None and flags&3 in (0,2)
            if not reading:return
            if ('bin_packing_utils' in lower or 'heldout' in lower or lower.startswith('phase2/data/')
                or lower.startswith('phase3/build_contexts/audit/')):
                blocked.append({'kind':'forbidden_file','path':relative})
                raise PermissionError('Legacy/reserved/held-out host data access prohibited: '+relative)
            if path.suffix.lower()=='.json' and str(path).casefold() not in allowed and not path.is_relative_to(state):
                blocked.append({'kind':'unapproved_json','path':relative})
                raise PermissionError('Unapproved host JSON input: '+relative)
            opened[relative]=opened.get(relative,0)+1
        finally:events+=1;hook_seconds+=perf_counter()-then
    sys.addaudithook(audit)
    completed=False;failure=None;started=perf_counter()
    try:
        sys.argv=['phase3.fused_followup_v1.recovery_v1_2.run','--manifest',str(manifest_path),
                  '--expected-sha256',actual,'--approval',str(approval_path)]
        runpy.run_module('phase3.fused_followup_v1.recovery_v1_2.run',run_name='__main__',alter_sys=True)
        completed=True
    except BaseException as exc:
        failure={'type':type(exc).__name__,'message':str(exc)}
        raise
    finally:
        result={'observer':'host-access-observer-v1.1-controller-v1.2','sealed_entrypoint_unchanged':True,
            'manifest_sha256':actual,'campaign_completed':completed,'failure':failure,
            'project_reads':opened,'blocked_operations':blocked,'docker_commands':commands,
            'legacy_module_loaded':any('bin_packing_utils' in name for name in sys.modules),
            'guard_hook_seconds':hook_seconds,'guard_event_count':events,
            'observer_wall_seconds':perf_counter()-started,
            'timing_limit':'Observer overhead included in both arms; no uninstrumented timing claim.'}
        with (output/'host_access_evidence.json').open('x',encoding='utf-8') as f:
            f.write(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--manifest',type=Path,default=HERE/'execution_request.json')
    parser.add_argument('--expected-sha256',required=True);parser.add_argument('--approval',type=Path,required=True)
    main(parser.parse_args())
