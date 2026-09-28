#!/usr/bin/env python3
"""Offline-frozen OpenJev generated fresh-three admission and gated execution.

Preparation/verification never starts a server or loads a model. Execution needs
an exact phase receipt, a free common GPU lock and an inspected three-record smoke.
"""
import argparse
import base64
import fcntl
import hashlib
import http.client
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import uuid

from development_benchmark import ROOT, digest, read_rows
from jev_benchmark import generated_variant_payload
import openjev_native_repeat_admission as native
from openjev_prompt_execution import parse_native_response, runtime_identity

PLAN_PATH = ROOT / 'results/repeatability-v1/openjev-generated-fresh-v1/manifest.json'
OLD_BASE = ROOT / 'results/prompt-comparison-v1-2026-09-24/openjev-generated-exact-v1'
OLD_MANIFEST = OLD_BASE / 'execution-manifest.draft.json'
OLD_PREFLIGHT = OLD_BASE / 'preflight.json'
MODES = ('generated-off', 'generated-on')
CONDITIONS = ('P0', 'P1', 'P2')
ROTATION = (('P0', 'P1', 'P2'), ('P1', 'P2', 'P0'), ('P2', 'P0', 'P1'))
TIMEOUT = 180
MAX_BODY = 8 * 1024 * 1024


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def rows(path):
    return native.rows(path)


def source_rows(root=ROOT):
    data = read_rows(root / 'data/pilot/inputs.jsonl')
    ids = [f'DEV-{i:03d}' for i in range(1, 61)]
    if len(data) != 60 or [r.get('id') for r in data] != ids or any(set(r) != {'id', 'feedback'} or not isinstance(r['feedback'], str) for r in data):
        raise ValueError('Exact input-only ordered 60 required')
    policy = (root / 'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    return data, policy


def historical(root=ROOT):
    result = {}
    old = json.loads((root / OLD_MANIFEST.relative_to(ROOT)).read_text())
    if old.get('contract') != 'openjev-generated-exact-draft-v1' or old.get('artifact_revision') != native.REVISION:
        raise ValueError('Historical generated manifest differs')
    for mode in MODES:
        baseline = root / f'results/openjev-local-{mode}-2026-09-23/development.jsonl'
        if sha(baseline) != old['baselines'][mode]['sha256']:
            raise ValueError('Historical OpenJev P0 binding differs')
        observed = [baseline] + [root / OLD_BASE.relative_to(ROOT) / mode / f'{condition}-development.jsonl' for condition in ('P1', 'P2')]
        expected_counts = {'generated-off': ((52, 8), (54, 6), (56, 4)),
                           'generated-on': ((59, 1), (50, 10), (53, 7))}[mode]
        bound = {}
        for condition, filename, counts in zip(CONDITIONS, observed, expected_counts):
            records = rows(filename)
            if len(records) != 60 or [r.get('id') for r in records] != [f'DEV-{i:03d}' for i in range(1, 61)]:
                raise ValueError('Historical generated membership differs')
            if (sum(r.get('status') == 'ok' for r in records), sum(r.get('status') == 'invalid_output' for r in records)) != counts:
                raise ValueError('Historical generated outcome count differs')
            bound[condition] = {'path': str(filename.relative_to(root)), 'sha256': sha(filename),
                                'valid': counts[0], 'invalid': counts[1]}
        result[mode] = {'conditions': bound, 'eligible_as_fresh_pass1': False,
                        'reason': 'P0 wire body and rendered token IDs were not saved; source reconstruction is observational'}
    return result


def expected_plan(root=ROOT):
    if Path(sys.executable).resolve() != native.PYTHON.resolve():
        raise ValueError('Use pinned OpenJev Python for plan preparation')
    data, policy = source_rows(root)
    old = json.loads((root / OLD_MANIFEST.relative_to(ROOT)).read_text())
    preflight = json.loads((root / OLD_PREFLIGHT.relative_to(ROOT)).read_text())
    if (old.get('contract') != 'openjev-generated-exact-draft-v1'
            or preflight.get('contract') != 'openjev-generated-exact-offline-preflight-v1'
            or preflight.get('record_count') != 360
            or preflight.get('manifest', {}).get('sha256') != sha(root / OLD_MANIFEST.relative_to(ROOT))
            or old.get('source_commit') != native.SOURCE_COMMIT
            or old.get('artifact_revision') != native.REVISION
            or preflight.get('input_guard') != 32768
            or preflight.get('requested_output_tokens') != 2048):
        raise ValueError('Historical exact generated preflight differs')
    if subprocess.check_output(['git', '-C', str(native.SOURCE), 'rev-parse', 'HEAD'], text=True).strip() != native.SOURCE_COMMIT or subprocess.check_output(['git', '-C', str(native.SOURCE), 'status', '--porcelain'], text=True).strip():
        raise ValueError('OpenJev source checkout drift')
    runtime_identity(old)  # package, platform and pinned artifact quantization; no model load
    assets = native.verify_assets()
    if sha(native.MODEL / 'download-manifest.json') != old['artifact_manifest_sha256']:
        raise ValueError('OpenJev artifact manifest drift')
    for filename, expected in preflight['verified_artifact_sha256'].items():
        if assets[filename] != expected:
            raise ValueError('OpenJev weight drift')
    for filename, expected in old['source_sha256'].items():
        if sha(filename) != expected:
            raise ValueError('Original generated controller or pinned server source drift')
    requests = {}
    for mode in MODES:
        requests[mode] = {}
        for condition in CONDITIONS:
            tokens = preflight['conditions'][mode + '/' + condition]['records']
            if len(tokens) != 60 or [x['id'] for x in tokens] != [r['id'] for r in data]:
                raise ValueError('Exact generated token membership differs')
            items = []
            for record, token in zip(data, tokens):
                payload, audit = generated_variant_payload(record['feedback'], policy,
                    'diffusiongemma-26b', mode, condition, 'openjev-' + mode)
                wire = json.dumps(payload, sort_keys=True).encode()
                if (hashlib.sha256(wire).hexdigest() != token['wire_request_sha256']
                        or token['input_tokens'] > 32768 or token['normalized_max_tokens'] != 2048):
                    raise ValueError('Generated wire request or rendered capacity differs')
                items.append({'id': record['id'], 'input_sha256': digest(record['feedback']),
                              'payload': payload, 'request_sha256': token['wire_request_sha256'],
                              'wire_body_sha256': hashlib.sha256(json.dumps(payload).encode()).hexdigest(),
                              'offline_rendered_token_ids_sha256': token['rendered_token_ids_sha256'],
                              'input_tokens': token['input_tokens'], 'prompt_audit': audit})
            requests[mode][condition] = items
    setup = json.loads((root / 'results/openjev/setup-audit.json').read_text())
    if setup.get('source_commit') != native.SOURCE_COMMIT or setup.get('artifact_revision') != native.REVISION or setup.get('cache_policy', '').find('16384') < 0:
        raise ValueError('OpenJev cache/setup audit drift')
    schedule = [f'{mode}/fresh{index}/{condition}' for mode in MODES for index, order in enumerate(ROTATION, 1) for condition in order]
    source_files = ('scripts/openjev_generated_repeat_admission.py', 'scripts/openjev_native_repeat_admission.py',
                    'scripts/openjev_prompt_execution.py', 'scripts/openjev_prompt_preflight.py',
                    'scripts/jev_benchmark.py', 'scripts/frozen_prompt_variants.py',
                    'docs/LABELING_GUIDE.md', 'schemas/judgments.schema.json', 'data/pilot/inputs.jsonl',
                    'results/openjev/setup-audit.json')
    return {'schema': 'openjev-generated-fresh-three-v1', 'status': 'offline_frozen_no_inference',
            'reference_labels_used_for_requests': False, 'historical_predictions_used_for_requests': False,
            'disposition': 'fresh_matched_three_historical_observational',
            'source_sha256': {str(root / p): sha(root / p) for p in source_files},
            'external_source_sha256': {p: sha(p) for p in old['source_sha256'] if not p.startswith(str(root) + '/')},
            'historical_manifest_sha256': sha(root / OLD_MANIFEST.relative_to(ROOT)),
            'historical_preflight_sha256': sha(root / OLD_PREFLIGHT.relative_to(ROOT)),
            'artifact_revision': native.REVISION,
            'artifact_manifest_sha256': sha(native.MODEL / 'download-manifest.json'),
            'asset_sha256': assets, 'historical': historical(root),
            'runtime': {'python': str(native.PYTHON), 'source_commit': native.SOURCE_COMMIT,
                        'platform': platform.platform(), 'packages': old['runtime_versions'],
                        'quantization': old['quantization'], 'server_env': native.SERVER_ENV,
                        'server_env_scope': 'configured launch environment; loaded settings not measured',
                        'configured_upstream_model_default': 'dgemma',
                        'logical_response_model': 'diffusiongemma-26b',
                        'rendered_token_hash_scope': 'historical offline preflight; live server token IDs not exposed',
                        'cache_policy': 'fresh server per stage; warmup on; 16384-token prefill cache LRU',
                        'backend': 'mlx', 'host': '127.0.0.1', 'port': 8080,
                        'route': 'POST /v1/chat/completions', 'timeout_seconds': TIMEOUT,
                        'max_raw_body_bytes': MAX_BODY,
                        'requested_on_effective_reasoning': 'unknown; requested setting only',
                        'seed_policy': 'no client seed; native server state-derived seed is not exposed',
                        'duration': 'HTTP client wall clock, not model-only inference'},
            'policy_prefix_sha256': digest(policy), 'requests': requests,
            'schedule': schedule, 'stage_inputs': {'smoke_ids': ['DEV-001', 'DEV-002', 'DEV-003'], 'development_count': 60},
            'failure': 'one attempt per ID; unknown started attempt stops without retry/replay; intrinsic invalid retained in development'}


def verify_plan():
    saved = native.read_json(PLAN_PATH)
    if saved != expected_plan():
        raise ValueError('Frozen generated plan differs from sources, assets, history or runtime')
    return saved, sha(PLAN_PATH)


def phase_folder(phase):
    parts = phase.split('/')
    if len(parts) != 3 or parts[0] not in MODES or parts[1] not in ('fresh1', 'fresh2', 'fresh3') or parts[2] not in CONDITIONS:
        raise ValueError('Phase outside generated schedule')
    return PLAN_PATH.parent.joinpath(*parts)


def verify_output(phase, stage):
    folder = phase_folder(phase)
    end = native.read_json(folder / f'{stage}.completion.json')
    files = {kind: folder / f'{stage}.{kind}.jsonl' for kind in ('journal', 'raw', 'records')}
    expected = 3 if stage == 'smoke' else 60
    if (end.get('status') != 'completed' or end.get('count') != expected or
            any(sha(path) != end.get(kind + '_sha256') for kind, path in files.items()) or
            len(rows(files['records'])) != expected or len(rows(files['raw'])) != expected):
        raise ValueError('Prior generated stage is not closed with intact evidence')
    return end


def predecessor(plan, plan_sha, phase, stage):
    if phase not in plan['schedule']:
        raise ValueError('Phase outside frozen generated order')
    for older in plan['schedule'][:plan['schedule'].index(phase)]:
        prior = verify_output(older, 'development')
        if prior.get('plan_sha256') != plan_sha:
            raise ValueError('Earlier generated phase plan drift')
    if stage == 'development':
        smoke = verify_output(phase, 'smoke')
        inspection_path = phase_folder(phase) / 'smoke-inspection.json'
        inspection = native.read_json(inspection_path)
        smoke_rows = rows(phase_folder(phase) / 'smoke.records.jsonl')
        raw_rows = rows(phase_folder(phase) / 'smoke.raw.jsonl')
        declared = inspection.get('records')
        if (smoke.get('plan_sha256') != plan_sha or
                inspection.get('kind') != 'openjev-generated-smoke-inspection-v1' or
                inspection.get('approved') is not True or inspection.get('phase') != phase or
                inspection.get('plan_sha256') != plan_sha or
                inspection.get('raw_sha256') != smoke['raw_sha256'] or
                inspection.get('records_sha256') != smoke['records_sha256'] or
                inspection.get('reference_labels_read') is not False or
                not isinstance(declared, list) or len(declared) != 3):
            raise ValueError('Generated development lacks bound three-record smoke')
        for saved, raw, declaration in zip(smoke_rows, raw_rows, declared):
            if (saved['id'] != raw['id'] or declaration.get('id') != saved['id'] or
                    declaration.get('status') != saved['decision']['status'] or
                    declaration.get('prediction') != saved['decision']['prediction'] or
                    saved['decision']['status'] not in ('ok', 'invalid_output') or
                    raw.get('http_status') != 200 or raw.get('incomplete') or raw.get('truncated')):
                raise ValueError('Smoke inspection does not match intact responses')
            response = json.loads(base64.b64decode(raw['body_base64']))
            if parse_native_response(response, raw['input_tokens']) != saved['decision']:
                raise ValueError('Smoke raw response does not reparse to saved decision')
            if saved['decision']['status'] == 'invalid_output' and not (declaration.get('accepted_unchanged') is True and declaration.get('inspection_reason')):
                raise ValueError('Intrinsic smoke invalid needs explicit unchanged acceptance')
        return sha(inspection_path)
    return None


def check_receipt(path, plan, plan_sha, phase, stage, predecessor_sha):
    receipt = native.read_json(path)
    if (receipt.get('kind') != 'root-reviewed-openjev-generated-stage-v1' or
            receipt.get('approved') is not True or receipt.get('phase') != phase or
            receipt.get('stage') != stage or receipt.get('plan_sha256') != plan_sha or
            receipt.get('controller_sha256') != sha(__file__) or
            receipt.get('predecessor_sha256') != predecessor_sha or
            receipt.get('reference_labels_read') is not False or
            receipt.get('source_commit') != native.SOURCE_COMMIT or
            receipt.get('artifact_manifest_sha256') != plan['artifact_manifest_sha256'] or
            receipt.get('historical_preflight_sha256') != plan['historical_preflight_sha256'] or
            receipt.get('server_policy') != plan['runtime']['cache_policy']):
        raise ValueError('Generated stage not root reviewed against frozen controls')
    return sha(path)


def transport(payload, timeout=TIMEOUT):
    connection = http.client.HTTPConnection('127.0.0.1', 8080, timeout=timeout)
    try:
        connection.request('POST', '/v1/chat/completions', body=json.dumps(payload).encode(),
                           headers={'Content-Type': 'application/json'})
        response = connection.getresponse()
        incomplete = False
        try: body = response.read(MAX_BODY + 1)
        except http.client.IncompleteRead as error:
            body, incomplete = error.partial[:MAX_BODY + 1], True
        return {'http_status': response.status,
                'headers': {k.lower(): v for k, v in response.getheaders()
                            if k.lower() in ('content-type', 'x-request-id', 'x-typesafe-request-id')},
                'body_base64': base64.b64encode(body).decode(),
                'truncated': len(body) > MAX_BODY, 'incomplete': incomplete}
    finally:
        connection.close()


def execute(plan, plan_sha, phase, stage, receipt_path):
    if stage not in ('smoke', 'development') or phase not in plan['schedule']:
        raise ValueError('Unscheduled generated stage')
    folder = phase_folder(phase)
    mode, _, condition = phase.split('/')
    items = plan['requests'][mode][condition]
    selected = items[:3] if stage == 'smoke' else items
    folder.mkdir(parents=True, exist_ok=True)
    lock_file = native.HOST_LOCK.open('a+')
    locked = False
    process = None
    try:
        fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB); locked = True
        prior = predecessor(plan, plan_sha, phase, stage)
        receipt_sha = check_receipt(receipt_path, plan, plan_sha, phase, stage, prior)
        files = {kind: folder / f'{stage}.{kind}.jsonl' for kind in ('journal', 'raw', 'records')}
        claim = folder / f'{stage}.claim.json'
        completion = folder / f'{stage}.completion.json'
        attestation_path = folder / f'{stage}.server-attestation.json'
        if any(p.exists() for p in (*files.values(), claim, completion, attestation_path, folder / f'{stage}.server.log')):
            raise ValueError('Generated stage already claimed; no replay')
        native.write_new(claim, {'phase': phase, 'stage': stage, 'plan_sha256': plan_sha,
                                  'controller_sha256': sha(__file__), 'receipt_sha256': receipt_sha,
                                  'claimed_utc': time.time(), 'reference_labels_read': False})
        for path in files.values(): path.touch(exist_ok=False)
        process = native.start_server(folder, stage, lock_file.fileno())
        native.write_new(attestation_path, {'kind': 'openjev-generated-server-launch-observation-v1',
                          'phase': phase, 'stage': stage, 'pid': process.pid,
                          'source_commit': native.SOURCE_COMMIT,
                          'artifact_manifest_sha256': plan['artifact_manifest_sha256'],
                          'configured_server_env': native.SERVER_ENV,
                          'configured_upstream_model_default': 'dgemma',
                          'logical_response_model': 'diffusiongemma-26b',
                          'cache_policy': plan['runtime']['cache_policy'],
                          'health_observed': True, 'loaded_settings_measured': False,
                          'live_rendered_token_ids_measured': False,
                          'loaded_engine_version': 'not independently exposed',
                          'attested_utc': time.time()})
        stopped = None
        for item in selected:
            attempt = str(uuid.uuid4())
            native.append(files['journal'], {'event': 'started', 'id': item['id'], 'attempt_id': attempt,
                                              'request_sha256': item['request_sha256'],
                                              'wire_body_sha256': item['wire_body_sha256']})
            started = time.monotonic()
            raw = None
            try:
                if hashlib.sha256(json.dumps(item['payload']).encode()).hexdigest() != item['wire_body_sha256']:
                    raise ValueError('Exact generated request body drift')
                raw = transport(item['payload'])
                raw.update({'id': item['id'], 'attempt_id': attempt,
                            'request_sha256': item['request_sha256'],
                            'wire_body_sha256': item['wire_body_sha256'],
                            'offline_rendered_token_ids_sha256': item['offline_rendered_token_ids_sha256'],
                            'input_tokens': item['input_tokens'],
                            'elapsed_seconds': time.monotonic() - started})
                native.append(files['raw'], raw)  # durable before JSON parse or projection
                if raw['http_status'] != 200 or raw['truncated'] or raw['incomplete']:
                    raise RuntimeError('HTTP, bounded-body or incomplete transport outcome')
                body = json.loads(base64.b64decode(raw['body_base64']))
                decision = parse_native_response(body, item['input_tokens'])
                if (decision['finish_reason'] not in ('stop', 'length') or
                        (decision['finish_reason'] == 'length' and decision['status'] != 'invalid_output')):
                    raise RuntimeError('Unexpected native finish reason')
            except (ValueError, TypeError, KeyError, UnicodeDecodeError, RuntimeError, json.JSONDecodeError) as error:
                if raw is None:
                    native.append(files['raw'], {'id': item['id'], 'attempt_id': attempt,
                                  'request_sha256': item['request_sha256'],
                                  'error_type': type(error).__name__,
                                  'elapsed_seconds': time.monotonic() - started})
                stopped = type(error).__name__
                native.append(files['journal'], {'event': 'stopped_unknown', 'id': item['id'], 'attempt_id': attempt})
                break
            except Exception as error:
                if raw is None:
                    native.append(files['raw'], {'id': item['id'], 'attempt_id': attempt,
                                  'request_sha256': item['request_sha256'],
                                  'error_type': type(error).__name__,
                                  'elapsed_seconds': time.monotonic() - started})
                stopped = type(error).__name__
                native.append(files['journal'], {'event': 'stopped_unknown', 'id': item['id'], 'attempt_id': attempt})
                break
            native.append(files['records'], {'id': item['id'], 'attempt_id': attempt,
                          'request_sha256': item['request_sha256'], 'decision': decision,
                          'reference_labels_read': False})
            native.append(files['journal'], {'event': 'finished', 'id': item['id'],
                          'attempt_id': attempt, 'status': decision['status']})
        native.write_new(completion, {'phase': phase, 'stage': stage,
                'status': 'completed' if stopped is None else 'stopped', 'reason': stopped,
                'count': len(rows(files['records'])),
                'attempted': sum(x['event'] == 'started' for x in rows(files['journal'])),
                'raw_sha256': sha(files['raw']), 'records_sha256': sha(files['records']),
                'journal_sha256': sha(files['journal']),
                'server_attestation_sha256': sha(attestation_path),
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
    native.write_new(PLAN_PATH, plan)
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
        raise ValueError('Stage needs exact phase and root-reviewed receipt')
    execute(plan, plan_sha, args.phase, args.command, args.receipt)


if __name__ == '__main__': main()
