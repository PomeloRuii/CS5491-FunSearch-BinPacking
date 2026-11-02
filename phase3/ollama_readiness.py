"""Empty-message model load, never a candidate draw or budget reservation."""
import argparse
import csv
from datetime import datetime, timezone
import io
import json
import shutil
import subprocess
from pathlib import Path
from time import perf_counter
from urllib import request, error

import bootstrap3
from common import write, file_hash
from generation_policy_v3 import policy
from ollama_adapter import NoRedirect

ORIGIN = 'http://127.0.0.1:11434'
LIMIT = 1024 * 1024


def utc():
    return datetime.now(timezone.utc).isoformat()


def load_payload(keep_alive_seconds):
    if type(keep_alive_seconds) is not int or not 1 <= keep_alive_seconds <= 300:
        raise ValueError('Preload keep_alive must be 1..300 seconds')
    return {'model': policy()['model'], 'messages': [], 'stream': False,
            'keep_alive': f'{keep_alive_seconds}s'}


def validate_load_response(value):
    message = value.get('message', {})
    if (value.get('model') != policy()['model'] or value.get('done') is not True
            or value.get('done_reason') != 'load' or not isinstance(message, dict)
            or message.get('content', '') or message.get('thinking')
            or message.get('tool_calls')
            or value.get('eval_count', 0) != 0
            or value.get('prompt_eval_count', 0) != 0):
        raise ValueError('Response does not confirm a non-generating model load')


def api(directory, label, endpoint, payload=None, timeout=10):
    # Closed endpoint set; neither a supplied prompt nor /v1 generation is accepted.
    if (endpoint not in ('/api/version', '/api/tags', '/api/ps', '/api/chat')
            or (endpoint == '/api/chat' and payload != load_payload(120))
            or (endpoint != '/api/chat' and payload is not None)):
        raise PermissionError('Only metadata GETs and the fixed empty preload are allowed')
    body = None if payload is None else json.dumps(payload, allow_nan=False).encode()
    opener = request.build_opener(request.ProxyHandler({}), NoRedirect())
    req = request.Request(ORIGIN + endpoint, data=body,
                          headers={'Content-Type': 'application/json'})
    start = perf_counter()
    status = None
    try:
        try:
            with opener.open(req, timeout=timeout) as response:
                status = response.status
                raw = response.read(LIMIT + 1)
        except error.HTTPError as exc:
            status = exc.code
            raw = exc.read(LIMIT + 1)
            (directory / (label + '.bin')).write_bytes(raw[:LIMIT])
            raise
        (directory / (label + '.bin')).write_bytes(raw[:LIMIT])
        if len(raw) > LIMIT:
            raise ValueError('Readiness response exceeds byte limit')
        return json.loads(raw)
    finally:
        write(directory / (label + '_transport.json'),
              {'endpoint': endpoint, 'payload': payload, 'http_status': status,
               'seconds': perf_counter() - start, 'attempts': 1,
               'operation': 'service_readiness_not_candidate_generation'})


def command(args):
    p = subprocess.run(args, capture_output=True, text=True, encoding='utf-8',
                       errors='replace', timeout=15, shell=False)
    if p.returncode:
        raise RuntimeError('Readiness command failed: ' + p.stderr[:2000])
    return p.stdout


def gpu_snapshot():
    smi = shutil.which('nvidia-smi')
    if not smi:
        raise RuntimeError('nvidia-smi unavailable; GPU readiness unverified')
    fields = 'name,uuid,driver_version,memory.total,memory.used,memory.free,utilization.gpu'
    raw = command([smi, '--query-gpu=' + fields, '--format=csv,nounits'])
    gpus = [{k.strip(): v.strip() for k, v in row.items()}
            for row in csv.DictReader(io.StringIO(raw))]
    apps = command([smi, '--query-compute-apps=pid,process_name,gpu_uuid,used_gpu_memory',
                    '--format=csv,nounits'])
    # Preserve only Ollama runner attribution, not unrelated personal applications.
    processes = [{k.strip(): v.strip() for k, v in row.items()}
                 for row in csv.DictReader(io.StringIO(apps))
                 if 'llama-server' in row.get(' process_name', row.get('process_name', '')).lower()]
    return {'gpus': gpus, 'ollama_compute_processes': processes}


def validate_residency(ps, cli_ps, gpu, expected_context):
    matches = [m for m in ps.get('models', []) if m.get('name') == policy()['model']]
    if len(matches) != 1:
        raise ValueError('Selected model is not uniquely resident')
    model = matches[0]
    if (model.get('digest') != policy()['digest'] or model.get('size_vram', 0) <= 0
            or model.get('context_length') != expected_context):
        raise ValueError('Resident digest, VRAM or declared context differs')
    lines = [s for s in cli_ps.splitlines() if s.split() and s.split()[0] == policy()['model']]
    if len(lines) != 1 or '100% GPU' not in lines[0]:
        raise ValueError('ollama ps does not confirm full GPU residency')
    devices = [g for g in gpu['gpus'] if 'RTX 5090' in g['name']]
    if len(devices) != 1 or not any(p['gpu_uuid'] == devices[0]['uuid']
                                  for p in gpu['ollama_compute_processes']):
        raise ValueError('Ollama runner not attributed to the RTX 5090')
    return model


def preload(directory, expected_context=32768):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    started = perf_counter()
    record = {'operation': 'ollama_service_preload', 'budget_class': 'service_readiness',
              'started_at_utc': utc(), 'status': 'FAIL', 'candidate_generation_requests': 0,
              'candidate_source_executions': 0, 'preload_attempts': 0,
              'automatic_retries': 0, 'keep_alive_seconds': 120,
              'expected_runtime_context': expected_context,
              'note': 'Warm residency check is not proof of cold-start or inference reliability.'}
    try:
        if type(expected_context) is not int or expected_context != 32768:
            raise ValueError('This bounded readiness session declares context 32768 only')
        record['gpu_before'] = gpu_snapshot()
        record['api_version'] = api(directory, 'version', '/api/version')
        tags = api(directory, 'tags', '/api/tags')
        installed = [m for m in tags.get('models', []) if m.get('name') == policy()['model']]
        if (len(installed) != 1 or installed[0].get('digest') != policy()['digest']
                or installed[0].get('details', {}).get('quantization_level') != 'Q4_K_M'
                or installed[0].get('remote_host') or installed[0].get('remote_model')):
            raise ValueError('Exact selected local digest/quantization not installed')
        record['installed_model'] = installed[0]
        record['ps_before'] = api(directory, 'ps_before', '/api/ps')
        payload = load_payload(120)
        write(directory / 'preload_request.json', {'endpoint': ORIGIN + '/api/chat',
              'payload': payload, 'operation': 'service_readiness',
              'no_candidate_prompt': True, 'generation_budget_charge': 0})
        record['preload_attempts'] = 1
        value = api(directory, 'preload_response', '/api/chat', payload, timeout=120)
        validate_load_response(value)
        record['preload_response'] = value
        record['ps_after'] = api(directory, 'ps_after', '/api/ps')
        record['gpu_after'] = gpu_snapshot()
        cli_ps = command([shutil.which('ollama') or 'ollama', 'ps'])
        (directory / 'ollama_ps.txt').write_text(cli_ps, encoding='utf-8')
        record['resident_model'] = validate_residency(record['ps_after'], cli_ps,
                                                     record['gpu_after'], expected_context)
        record['status'] = 'PASS'
        return record
    except Exception as exc:
        record.update(error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        record['completed_at_utc'] = utc()
        record['seconds'] = perf_counter() - started
        record['raw_response_hashes'] = {p.name: file_hash(p) for p in directory.glob('*.bin')}
        write(directory / 'readiness.json', record)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(preload(args.output), ensure_ascii=False, indent=2))
