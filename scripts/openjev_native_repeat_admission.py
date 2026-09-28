#!/usr/bin/env python3
"""Frozen OpenJev native P0 fresh matched-three admission. No inference on import or verify."""
import argparse
import base64
import fcntl
import hashlib
import http.client
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import platform
import socket
import subprocess
import sys
import time
import uuid

from development_benchmark import ROOT, KEYS, digest, read_rows
from jev_benchmark import QUESTION_VERSION, make_payload, parse_response

WORK = Path('/Users/adamkovacs/Documents/Codex/2026-09-21/continue-the-recruitment-feedback-benchmark-from/work')
SOURCE = WORK / 'openjev-source'
MODEL = WORK / 'openjev-model'
PYTHON = WORK / 'openjev-venv/bin/python'
PLAN_PATH = ROOT / 'results/repeatability-v1/openjev-native-fresh-v1/manifest.json'
HOST_LOCK = ROOT / 'results/repeatability-v1/laya-expanded-cpu-v1/execution.lock'
SETUP = ROOT / 'results/openjev/setup-audit.json'
MODES = ('fixed', 'adaptive', 'thinking')
CONFIGS = {mode: f'openjev-{mode}' for mode in MODES}
HISTORY = {mode: ROOT / f'results/openjev-local-{mode}-2026-09-23' for mode in MODES}
SOURCE_COMMIT = 'e04794ab36e4f7e6040c2547baecdb2737ce2e79'
REVISION = 'a7a81407613811e8ba63af92ac0d852b809e191f'
SERVER_ENV = {'OPENJEV_BACKEND': 'mlx', 'OPENJEV_MLX_MODEL': str(MODEL),
              'OPENJEV_HOST': '127.0.0.1', 'OPENJEV_PORT': '8080',
              'OPENJEV_CANVAS': '64', 'OPENJEV_CANVAS_STEP': '16',
              'OPENJEV_AUTO_MAX': '4', 'OPENJEV_AUTO_THRESHOLD': '0.1',
              'OPENJEV_MLX_MAX_PROMPT': '32768', 'OPENJEV_WARMUP': '1',
              'OPENJEV_MAX_INFLIGHT': '1', 'OPENJEV_MAX_QUEUE': '1',
              'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
              'TOKENIZERS_PARALLELISM': 'false'}
PACKAGES = ('openjev', 'mlx', 'mlx-vlm', 'transformers', 'fastapi', 'uvicorn')
SOURCE_FILES = ('openjev/config.py', 'openjev/api.py', 'openjev/engine.py',
                'openjev/mlx_backend.py', 'openjev/warmup.py', 'openjev/__main__.py')
TIMEOUT = 180
MAX_BODY = 8 * 1024 * 1024


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def blob_sha(path):
    path = Path(path)
    result = hashlib.sha1(f'blob {path.stat().st_size}\0'.encode())
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(chunk)
    return result.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


def read_json(path):
    return json.loads(Path(path).read_text())


def rows(path):
    data = Path(path).read_bytes()
    if data and (not data.endswith(b'\n') or any(not line for line in data.splitlines())):
        raise ValueError(f'Incomplete JSONL: {path}')
    return [json.loads(line) for line in data.splitlines()]


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


def write_new(path, value):
    with Path(path).open('x') as stream:
        stream.write(json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2) + '\n')
        stream.flush(); os.fsync(stream.fileno())
    sync_dir(Path(path).parent)


def append(path, value):
    with Path(path).open('a') as stream:
        stream.write(canonical(value) + '\n')
        stream.flush(); os.fsync(stream.fileno())


def verify_assets():
    manifest = read_json(MODEL / 'download-manifest.json')
    if manifest.get('sha') != REVISION or len(manifest.get('siblings', [])) != 13:
        raise ValueError('OpenJev artifact revision or inventory differs')
    expected = {item['rfilename'] for item in manifest['siblings']}
    if expected != {p.name for p in MODEL.iterdir() if p.is_file()} - {'download-manifest.json'}:
        raise ValueError('OpenJev artifact file set differs')
    hashes = {}
    for item in manifest['siblings']:
        path = MODEL / item['rfilename']
        if path.stat().st_size != item['size']:
            raise ValueError(f'OpenJev artifact size differs: {path.name}')
        actual = sha(path)
        if 'lfs' in item:
            if item['lfs']['sha256'] != actual or item['lfs']['size'] != item['size']:
                raise ValueError(f'OpenJev LFS hash differs: {path.name}')
        elif blob_sha(path) != item['blobId']:
            raise ValueError(f'OpenJev Git blob differs: {path.name}')
        hashes[path.name] = actual
    return hashes


def source_rows(root=ROOT):
    data = read_rows(root / 'data/pilot/inputs.jsonl')
    if len(data) != 60 or [r.get('id') for r in data] != [f'DEV-{i:03d}' for i in range(1, 61)] or any(set(r) != {'id', 'feedback'} for r in data):
        raise ValueError('Expected ordered input-only 60 records')
    policy = (root / 'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    requests = {}
    for mode in MODES:
        requests[mode] = [{'id': r['id'], 'input_sha256': digest(r['feedback']),
                           'payload': make_payload(r['feedback'], policy, 'openjev-0.1', mode)} for r in data]
        for item in requests[mode]:
            item['request_sha256'] = digest(json.dumps(item['payload'], sort_keys=True))
    return data, policy, requests


def hardware_identity():
    return {'machine': platform.machine(),
            'memory_bytes': os.sysconf('SC_PHYS_PAGES') * os.sysconf('SC_PAGE_SIZE'),
            'model_identifier': 'not exposed by this read-only controller'}


def history(root, requests):
    out = {}
    for mode in MODES:
        directory = root / HISTORY[mode].relative_to(ROOT)
        names = (('development.jsonl', 'development-continuation.jsonl',
                  'development-reconciled.jsonl', 'interruption.json', 'reconciliation.json')
                 if mode == 'fixed' else ('development.jsonl', 'reconciliation.json'))
        saved = {name: sha(directory / name) for name in names}
        records = rows(directory / ('development-reconciled.jsonl' if mode == 'fixed' else 'development.jsonl'))
        if len(records) != 60 or [r.get('id') for r in records] != [f'DEV-{i:03d}' for i in range(1, 61)]:
            raise ValueError('Historical OpenJev membership differs')
        for record, planned in zip(records, requests[mode]):
            if (record.get('status') != 'ok' or record.get('mode') != mode
                    or record.get('requested_model') != 'openjev-0.1'
                    or record.get('surface') != 'openjev'
                    or record.get('question_version') != QUESTION_VERSION
                    or record.get('question_order') != list(KEYS)
                    or record.get('input_sha256') != planned['input_sha256']
                    or record.get('request_sha256') != planned['request_sha256']
                    or record.get('local_extensions') != {k: planned['payload'][k] for k in ('steps', 'samples', 'think', 'sequential') if k in planned['payload']}
                    or record.get('prediction') != parse_response(record.get('raw_response'), 'openjev-0.1')):
                raise ValueError('Historical OpenJev request/raw parity differs')
        out[mode] = {'directory': str(directory.relative_to(root)), 'files_sha256': saved,
                     'eligible_as_fresh_pass1': False,
                     'reason': 'fixed interruption or adaptive/thinking unobserved prior warm cache state'}
    fixed = rows(root / HISTORY['fixed'].relative_to(ROOT) / 'development.jsonl')
    resumed = rows(root / HISTORY['fixed'].relative_to(ROOT) / 'development-continuation.jsonl')
    if len(fixed) != 7 or len(resumed) != 53 or resumed[0]['id'] != 'DEV-008':
        raise ValueError('Fixed historical interrupted composite differs')
    return out


def expected_plan(root=ROOT):
    if Path(sys.executable).resolve() != PYTHON.resolve():
        raise ValueError('Use pinned OpenJev Python for plan preparation')
    origin = importlib.util.find_spec('openjev').origin
    if Path(origin).resolve() != (SOURCE / 'openjev/__init__.py').resolve():
        raise ValueError('OpenJev import is not pinned local source')
    checkout = subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip()
    if checkout != SOURCE_COMMIT or subprocess.check_output(['git', '-C', str(SOURCE), 'status', '--porcelain']):
        raise ValueError('OpenJev source checkout differs or is dirty')
    data, policy, requests = source_rows(root)
    assets = verify_assets()
    audit = read_json(root / SETUP.relative_to(ROOT))
    if (audit.get('source_commit') != SOURCE_COMMIT or audit.get('artifact_revision') != REVISION
            or audit.get('settings', {}).get('OPENJEV_WARMUP') != 1
            or audit.get('settings', {}).get('OPENJEV_CANVAS') != 64
            or audit.get('settings', {}).get('OPENJEV_AUTO_MAX') != 4
            or audit.get('settings', {}).get('OPENJEV_AUTO_THRESHOLD') != 0.1
            or audit.get('cache_policy', '').find('16384') < 0):
        raise ValueError('Saved OpenJev setup audit differs')
    versions = {name: importlib.metadata.version(name) for name in PACKAGES}
    if versions != {'openjev': '0.3.0', 'mlx': '0.32.2', 'mlx-vlm': '0.6.15',
                    'transformers': '5.17.0', 'fastapi': '0.141.1', 'uvicorn': '0.53.0'}:
        raise ValueError('OpenJev package versions differ')
    src_hashes = {str((SOURCE / name)): sha(SOURCE / name) for name in SOURCE_FILES}
    source_sha = {str(root / name): sha(root / name) for name in (
        'scripts/openjev_native_repeat_admission.py', 'scripts/jev_benchmark.py',
        'scripts/development_benchmark.py', 'docs/LABELING_GUIDE.md',
        'data/pilot/inputs.jsonl', 'results/openjev/setup-audit.json')}
    plan = {'schema': 'openjev-native-fresh-p0-v1', 'status': 'offline_frozen_no_inference',
            'reference_labels_used_for_requests': False,
            'historical_predictions_used_for_requests': False,
            'disposition': 'fresh_matched_three_historical_observational',
            'source_sha256': {**source_sha, **src_hashes},
            'artifact_revision': REVISION, 'artifact_manifest_sha256': sha(MODEL / 'download-manifest.json'),
            'asset_sha256': assets, 'historical': history(root, requests),
            'runtime': {'python': str(PYTHON), 'source_commit': SOURCE_COMMIT,
                        'platform': platform.platform(), 'hardware': hardware_identity(),
                        'packages': versions,
                        'backend': 'mlx', 'host': '127.0.0.1', 'port': 8080,
                        'quantization': audit['quantization'], 'server_env': SERVER_ENV,
                        'prefill_cache_tokens': 16384, 'prefill_eviction': 'LRU retaining at least one prompt',
                        'server_policy': 'fresh server per stage, warmup on; smoke and development each restart',
                        'actual_adaptive_rereads': None, 'seed': 'server derives request seed from state/questions; no client seed',
                        'client_duration': 'HTTP wall clock, not model-only inference',
                        'timeout_seconds': TIMEOUT, 'max_raw_body_bytes': MAX_BODY},
            'policy_prefix_sha256': digest(policy),
            'requests': requests,
            'schedule': [f'openjev-{mode}/fresh{number}/P0' for mode in MODES for number in (1, 2, 3)],
            'stage_inputs': {'smoke_ids': ['DEV-001', 'DEV-002', 'DEV-003'], 'development_count': 60},
            'failure': 'one attempt per ID; unknown start stops without retry or replay'}
    return plan


def verify_plan():
    saved = read_json(PLAN_PATH)
    if saved != expected_plan():
        raise ValueError('Frozen OpenJev plan differs from assets, sources, history or runtime')
    return saved, sha(PLAN_PATH)


def phase_folder(phase):
    pieces = phase.split('/')
    if len(pieces) != 3 or pieces[0] not in CONFIGS.values() or pieces[1] not in ('fresh1', 'fresh2', 'fresh3') or pieces[2] != 'P0':
        raise ValueError('Phase outside frozen OpenJev schedule')
    return PLAN_PATH.parent.joinpath(*pieces)


def predecessor(plan, plan_sha, phase, stage):
    if phase not in plan['schedule']:
        raise ValueError('Phase outside frozen schedule')
    for older in plan['schedule'][:plan['schedule'].index(phase)]:
        path = phase_folder(older) / 'development.completion.json'
        terminal = read_json(path)
        if terminal.get('status') != 'completed' or terminal.get('count') != 60 or terminal.get('plan_sha256') != plan_sha:
            raise ValueError('Earlier native phase incomplete')
        verify_output(older, 'development', terminal)
    if stage == 'development':
        path = phase_folder(phase) / 'smoke.completion.json'
        terminal = read_json(path)
        if terminal.get('status') != 'completed' or terminal.get('count') != 3:
            raise ValueError('Inspected smoke not complete')
        verify_output(phase, 'smoke', terminal)
        inspect = read_json(phase_folder(phase) / 'smoke-inspection.json')
        if (inspect.get('kind') != 'openjev-native-smoke-inspection-v1'
                or inspect.get('approved') is not True
                or inspect.get('phase') != phase
                or inspect.get('plan_sha256') != plan_sha
                or inspect.get('raw_sha256') != terminal['raw_sha256']
                or inspect.get('records_sha256') != terminal['records_sha256']
                or inspect.get('reference_labels_read') is not False):
            raise ValueError('Smoke inspection differs')
        return sha(phase_folder(phase) / 'smoke-inspection.json')
    return None


def check_receipt(receipt_path, plan, plan_sha, phase, stage, predecessor_sha):
    receipt = read_json(receipt_path)
    if (receipt.get('kind') != 'root-reviewed-openjev-native-stage-v1'
            or receipt.get('approved') is not True or receipt.get('phase') != phase
            or receipt.get('stage') != stage or receipt.get('plan_sha256') != plan_sha
            or receipt.get('controller_sha256') != sha(__file__)
            or receipt.get('predecessor_sha256') != predecessor_sha
            or receipt.get('reference_labels_read') is not False
            or receipt.get('source_commit') != SOURCE_COMMIT
            or receipt.get('artifact_manifest_sha256') != plan['artifact_manifest_sha256']):
        raise ValueError('OpenJev stage not root reviewed against current frozen controls')
    return sha(receipt_path)


def verify_output(phase, stage, terminal=None):
    folder = phase_folder(phase)
    terminal = terminal or read_json(folder / f'{stage}.completion.json')
    files = {key: folder / f'{stage}.{key}.jsonl' for key in ('journal', 'raw', 'records')}
    if any(sha(file) != terminal.get(key + '_sha256') for key, file in files.items()):
        raise ValueError('Native stage evidence hash differs')
    if terminal.get('count') != len(rows(files['records'])):
        raise ValueError('Native stage saved count differs')
    return terminal


def transport(payload, timeout=TIMEOUT):
    connection = http.client.HTTPConnection('127.0.0.1', 8080, timeout=timeout)
    try:
        connection.request('POST', '/v1/systemone', body=json.dumps(payload).encode(),
                           headers={'Content-Type': 'application/json'})
        response = connection.getresponse()
        incomplete = False
        try: body = response.read(MAX_BODY + 1)
        except http.client.IncompleteRead as error:
            body, incomplete = error.partial[:MAX_BODY + 1], True
        return {'http_status': response.status, 'headers': {
            key.lower(): value for key, value in response.getheaders()
            if key.lower() in ('content-type', 'x-request-id', 'x-typesafe-request-id')},
            'body_base64': base64.b64encode(body).decode(),
            'truncated': len(body) > MAX_BODY, 'incomplete': incomplete}
    finally:
        connection.close()


def server_env():
    env = {key: value for key in ('PATH', 'HOME', 'TMPDIR', 'LANG')
           if (value := os.environ.get(key)) is not None}
    env.update(SERVER_ENV)
    return env


def start_server(folder, stage, lock_fd):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(1)
        if probe.connect_ex(('127.0.0.1', 8080)) == 0:
            raise ValueError('Port 8080 already has a listener; refuse competing or stale server')
    with (folder / f'{stage}.server.log').open('x') as log:
        process = subprocess.Popen([str(PYTHON), '-m', 'openjev'], cwd=SOURCE,
                                   env=server_env(), stdout=log, stderr=subprocess.STDOUT,
                                   pass_fds=(lock_fd,))
    try:
        for _ in range(600):
            if process.poll() is not None:
                raise ValueError('Pinned OpenJev server exited during warmup')
            try:
                connection = http.client.HTTPConnection('127.0.0.1', 8080, timeout=1)
                connection.request('GET', '/health')
                health = connection.getresponse()
                healthy = health.status == 200 and json.loads(health.read()) == {'status': 'ok'}
                connection.close()
                if healthy: return process
            except (ConnectionRefusedError, OSError, ValueError, json.JSONDecodeError):
                pass
            time.sleep(1)
        raise TimeoutError('OpenJev warmup did not expose local healthy endpoint')
    except BaseException:
        if process.poll() is None:
            process.terminate()
            try: process.wait(timeout=30)
            except subprocess.TimeoutExpired: process.kill(); process.wait()
        raise


def execute(plan, plan_sha, phase, stage, receipt_path):
    folder = phase_folder(phase)
    mode = phase.split('/')[0].removeprefix('openjev-')
    source = plan['requests'][mode]
    selection = source[:3] if stage == 'smoke' else source
    folder.mkdir(parents=True, exist_ok=True)
    lock_file = HOST_LOCK.open('a+')
    locked = False
    process = None
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        locked = True
        prior = predecessor(plan, plan_sha, phase, stage)
        receipt_sha = check_receipt(receipt_path, plan, plan_sha, phase, stage, prior)
        paths = {kind: folder / f'{stage}.{kind}.jsonl' for kind in ('journal', 'raw', 'records')}
        claim = folder / f'{stage}.claim.json'
        completion = folder / f'{stage}.completion.json'
        if any(path.exists() for path in (*paths.values(), claim, completion,
                                          folder / f'{stage}.server.log')):
            raise ValueError('Native stage already claimed; no replay')
        write_new(claim, {'phase': phase, 'stage': stage, 'plan_sha256': plan_sha,
                          'controller_sha256': sha(__file__), 'receipt_sha256': receipt_sha,
                          'claimed_utc': time.time(), 'reference_labels_read': False})
        for path in paths.values(): path.touch(exist_ok=False)
        process = start_server(folder, stage, lock_file.fileno())
        stopped = None
        for item in selection:
            attempt = str(uuid.uuid4())
            append(paths['journal'], {'event': 'started', 'id': item['id'], 'attempt_id': attempt,
                                      'request_sha256': item['request_sha256']})
            started = time.monotonic()
            try:
                raw = transport(item['payload'])
                raw.update({'id': item['id'], 'attempt_id': attempt,
                            'request_sha256': item['request_sha256'],
                            'elapsed_seconds': time.monotonic() - started})
                append(paths['raw'], raw)
                if raw['http_status'] != 200:
                    raise ValueError(f'OpenJev HTTP status {raw["http_status"]}')
                if raw['truncated'] or raw['incomplete']:
                    raise OverflowError('Bounded or incomplete OpenJev HTTP body')
                body = json.loads(base64.b64decode(raw['body_base64']))
                prediction = parse_response(body, 'openjev-0.1')
                decision = {'status': 'ok', 'prediction': prediction}
            except (ValueError, TypeError, KeyError, UnicodeDecodeError) as error:
                if 'raw' not in locals() or raw.get('attempt_id') != attempt:
                    append(paths['raw'], {'id': item['id'], 'attempt_id': attempt,
                                          'request_sha256': item['request_sha256'],
                                          'error_type': type(error).__name__, 'elapsed_seconds': time.monotonic() - started})
                    stopped = str(error)
                    append(paths['journal'], {'event': 'stopped_unknown', 'id': item['id'], 'attempt_id': attempt})
                    break
                if raw['http_status'] != 200:
                    stopped = str(error)
                    append(paths['journal'], {'event': 'stopped_unknown', 'id': item['id'], 'attempt_id': attempt})
                    break
                decision = {'status': 'invalid_output', 'reason': type(error).__name__}
            except Exception as error:
                if 'raw' not in locals() or raw.get('attempt_id') != attempt:
                    append(paths['raw'], {'id': item['id'], 'attempt_id': attempt,
                                          'request_sha256': item['request_sha256'],
                                          'error_type': type(error).__name__, 'elapsed_seconds': time.monotonic() - started})
                stopped = type(error).__name__
                append(paths['journal'], {'event': 'stopped_unknown', 'id': item['id'], 'attempt_id': attempt})
                break
            append(paths['records'], {'id': item['id'], 'attempt_id': attempt,
                                      'request_sha256': item['request_sha256'], 'decision': decision,
                                      'reference_labels_read': False})
            append(paths['journal'], {'event': 'finished', 'id': item['id'],
                                      'attempt_id': attempt, 'status': decision['status']})
            if stage == 'smoke' and decision['status'] != 'ok':
                stopped = 'Smoke intrinsic invalid; development admission refused'
                break
        write_new(completion, {'phase': phase, 'stage': stage,
                               'status': 'completed' if stopped is None else 'stopped',
                               'reason': stopped, 'count': len(rows(paths['records'])),
                               'attempted': sum(r['event'] == 'started' for r in rows(paths['journal'])),
                               'raw_sha256': sha(paths['raw']),
                               'records_sha256': sha(paths['records']),
                               'journal_sha256': sha(paths['journal']),
                               'plan_sha256': plan_sha, 'receipt_sha256': receipt_sha})
        if stopped is not None:
            raise ValueError(stopped)
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try: process.wait(timeout=30)
            except subprocess.TimeoutExpired: process.kill(); process.wait()
        if locked: fcntl.flock(lock_file, fcntl.LOCK_UN)
        lock_file.close()


def prepare():
    plan = expected_plan()
    PLAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    write_new(PLAN_PATH, plan)
    print(sha(PLAN_PATH))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'verify', 'smoke', 'development'))
    parser.add_argument('--phase')
    parser.add_argument('--receipt', type=Path)
    args = parser.parse_args()
    if args.command == 'prepare': prepare(); return
    plan, plan_sha = verify_plan()
    if args.command == 'verify': print(plan_sha); return
    if args.phase is None or args.receipt is None:
        raise ValueError('Stage requires exact phase and root-reviewed receipt')
    stage = args.command
    execute(plan, plan_sha, args.phase, stage, args.receipt)


if __name__ == '__main__': main()
