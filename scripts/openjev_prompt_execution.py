#!/usr/bin/env python3
"""Reviewed, exact OpenJev generated-control smoke and development controller.

This is separate from jev_benchmark.py, whose P1/P2 live path remains closed.
The --serve action loads the pinned local MLX model but performs no inference.
Every live action requires a separate review receipt for the frozen manifest
and tokenizer-only preflight. No automatic retry or output repair exists.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import socket
import sys
import time
import urllib.error
import urllib.request
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
import prompt_schedule as schedule
from development_benchmark import read_rows, valid
from jev_benchmark import NoRedirect, generated_variant_payload

FOLDER = ROOT / 'results/prompt-comparison-v1-2026-09-24/openjev-generated-exact-v1'
MANIFEST = FOLDER / 'execution-manifest.draft.json'
PREFLIGHT = FOLDER / 'preflight.json'
ATTESTATION = FOLDER / 'server-attestation.json'
JOURNAL = ROOT / 'results/prompt-comparison-v1-2026-09-24/execution-journal.jsonl'
MODES = {'generated-off': 'openjev-generated-off', 'generated-on': 'openjev-generated-on'}
OPENER = urllib.request.build_opener(NoRedirect)


def utc():
    return datetime.now(timezone.utc).isoformat()


def sha(data):
    return hashlib.sha256(data).hexdigest()


def binding(path):
    path = Path(path).resolve()
    return {'file': str(path.relative_to(ROOT.resolve())), 'sha256': sha(path.read_bytes())}


def load_bound(path, expected):
    path = Path(path)
    if not path.is_file() or sha(path.read_bytes()) != expected:
        raise ValueError('Frozen SHA-256 mismatch: ' + str(path))
    return json.loads(path.read_text())


def load_review(manifest_sha, preflight_sha, receipt_path, receipt_sha):
    manifest = load_bound(MANIFEST, manifest_sha)
    preflight = load_bound(PREFLIGHT, preflight_sha)
    if manifest.get('contract') != 'openjev-generated-exact-draft-v1' or preflight.get('contract') != 'openjev-generated-exact-offline-preflight-v1' or preflight.get('manifest') != binding(MANIFEST):
        raise ValueError('OpenJev manifest or exact preflight identity changed')
    if manifest.get('status') != 'offline_preparation_review_required' or manifest.get('inference_authorized_by_this_manifest') is not False:
        raise ValueError('Draft manifest policy changed')
    receipt_path = Path(receipt_path).resolve()
    if receipt_path.parent != FOLDER.resolve():
        raise ValueError('Review receipt must be within the OpenJev evidence directory')
    receipt = load_bound(receipt_path, receipt_sha)
    expected = {'contract': 'openjev-generated-exact-root-review-v1',
        'decision': 'approved_for_smoke_then_inspected_development',
        'manifest': binding(MANIFEST), 'preflight': binding(PREFLIGHT),
        'configurations': ['openjev-generated-off', 'openjev-generated-on'],
        'canonical_denominator': 60}
    if any(receipt.get(k) != v for k, v in expected.items()):
        raise ValueError('Root-review receipt does not approve these frozen OpenJev inputs')
    if not isinstance(receipt.get('reviewer'), str) or not receipt['reviewer'].strip() or not isinstance(receipt.get('reviewed_utc'), str) or not receipt['reviewed_utc'].strip():
        raise ValueError('Root-review receipt lacks reviewer or review time')
    for path, expected_hash in manifest['source_sha256'].items():
        if not Path(path).is_file() or sha(Path(path).read_bytes()) != expected_hash:
            raise ValueError('Pinned OpenJev source changed: ' + path)
    for key in ('inputs', 'schema', 'roster_freeze', 'schedule', 'policy_source', 'prior_token_preflight'):
        spec = manifest[key]
        if binding(ROOT / spec['file']) != spec:
            raise ValueError('Pinned project source changed: ' + key)
    corrected = manifest['corrected_capacity_audit']
    if sha(Path(corrected['file']).read_bytes()) != corrected['sha256']:
        raise ValueError('Corrected capacity audit changed')
    native_audit = manifest['native_setup_audit']
    if binding(ROOT / native_audit['file']) != native_audit:
        raise ValueError('Native OpenJev setup audit changed')
    if sha((Path(manifest['model_artifact']) / 'download-manifest.json').read_bytes()) != manifest['artifact_manifest_sha256']:
        raise ValueError('Model artifact manifest changed')
    for mode, spec in manifest['baselines'].items():
        if mode not in MODES or binding(ROOT / spec['file']) != spec:
            raise ValueError('Historical OpenJev baseline changed: ' + mode)
    for filename, expected_hash in preflight['verified_artifact_sha256'].items():
        path = Path(manifest['model_artifact']) / filename
        with path.open('rb') as stream:
            if hashlib.file_digest(stream, 'sha256').hexdigest() != expected_hash:
                raise ValueError('Pinned OpenJev artifact changed: ' + filename)
    if (preflight['record_count'], preflight['input_guard'], preflight['requested_output_tokens'],
            preflight['normalization_ceiling'], preflight['artifact_context'], preflight['native_canvas']) != (360, 32768, 2048, 8192, 262144, 256):
        raise ValueError('Exact capacity controls changed')
    if any(preflight.get(k) is not False for k in ('model_loaded', 'server_started', 'inference_performed', 'reference_labels_read')):
        raise ValueError('Expected offline-only preflight')
    return manifest, preflight, receipt


def runtime_identity(manifest):
    """Observe live host and installed versions; quantization comes from pinned artifact evidence."""
    expected = manifest['runtime_versions']
    observed = {'python': platform.python_version()}
    observed.update({name: importlib.metadata.version(name) for name in expected if name != 'python'})
    if observed != expected or platform.platform() != manifest['hardware']:
        raise ValueError('OpenJev native runtime or hardware changed')
    config = json.loads((Path(manifest['model_artifact']) / 'config.json').read_text())
    quant = config['quantization']
    observed_quant = {'default_bits': quant['bits'], 'group_size': quant['group_size'],
        'mode': quant['mode'], '8bit_layer_overrides': sum(isinstance(v, dict) and v.get('bits') == 8 for v in quant.values())}
    if observed_quant != manifest['quantization']:
        raise ValueError('Pinned artifact quantization differs from baseline setup audit')
    return {'runtime_versions': observed, 'hardware': platform.platform(),
        'artifact_quantization_sha256': sha(json.dumps(quant, sort_keys=True, separators=(',', ':')).encode()),
        'quantization': observed_quant,
        'quantization_basis': 'Pinned model config and weight hashes; loaded layer structure not separately attested'}


def condition(manifest, mode, variant):
    if mode not in MODES or variant not in ('P1', 'P2'):
        raise ValueError('Only frozen generated P1/P2 conditions are executable')
    item = next((c for c in manifest['conditions'] if c['mode'] == mode), None)
    if item is None or item['configuration_id'] != MODES[mode]:
        raise ValueError('Unknown OpenJev condition')
    scheduled = {s['id']: s['conditions'] for s in json.loads((ROOT / manifest['schedule']['file']).read_text())['order']}
    if scheduled[item['configuration_id']] != item['variant_order']:
        raise ValueError('Counterbalanced schedule changed')
    if item['parent_baseline_id'] != MODES[mode] or item['chat_template_enable_thinking'] is not (mode == 'generated-on'):
        raise ValueError('Mode-specific frozen controls changed')
    return item


def verify_server_attestation(manifest, preflight_sha, receipt_sha, attestation_sha):
    attestation = load_bound(ATTESTATION, attestation_sha)
    expected = {'contract': 'openjev-generated-exact-loaded-server-v1',
        'manifest': binding(MANIFEST), 'preflight': binding(PREFLIGHT),
        'review_receipt_sha256': receipt_sha, 'source_commit': manifest['source_commit'],
        'artifact_revision': manifest['artifact_revision'], 'host': '127.0.0.1', 'port': 8080,
        'backend': 'mlx', 'mlx_max_prompt': 32768, 'gen_max_tokens': 8192,
        'upstream_model': 'diffusiongemma-26b',
        'readout_canvas_setting': 64, 'loaded_model_context': 262144,
        'loaded_native_canvas': 256, 'runtime_identity': runtime_identity(manifest)}
    if any(attestation.get(k) != v for k, v in expected.items()):
        raise ValueError('Loaded server attestation differs from frozen controls')
    pid = attestation.get('pid')
    if type(pid) is not int or pid <= 0:
        raise ValueError('Loaded server PID missing')
    try:
        os.kill(pid, 0)
    except OSError as exc:
        raise ValueError('Attested server process is no longer running') from exc
    request = urllib.request.Request('http://127.0.0.1:8080/health')
    with OPENER.open(request, timeout=5) as response:
        if json.load(response) != {'status': 'ok'}:
            raise ValueError('Attested OpenJev server health changed')
    return binding(ATTESTATION)


def serve(manifest, preflight_sha, receipt_sha):
    if ATTESTATION.exists():
        raise FileExistsError(ATTESTATION)
    with socket.socket() as sock:
        if sock.connect_ex(('127.0.0.1', 8080)) == 0:
            raise ValueError('OpenJev port already occupied')
    identity = runtime_identity(manifest)
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', TOKENIZERS_PARALLELISM='false')
    source = Path(manifest['source_checkout'])
    sys.path.insert(0, str(source))
    from transformers import AutoTokenizer
    from openjev.api import create_app
    from openjev.config import Settings
    import uvicorn
    settings = Settings(backend='mlx', mlx_model=manifest['model_artifact'],
                        upstream_model='diffusiongemma-26b',
                        mlx_max_prompt=32768, gen_max_tokens=8192, canvas=64,
                        api_key=os.environ.get('OPENJEV_API_KEY', ''), origin_secret='')
    tokenizer = AutoTokenizer.from_pretrained(manifest['model_artifact'], local_files_only=True)
    app = create_app(settings=settings, tokenizer=tokenizer)
    original_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def checked_lifespan(active):
        async with original_lifespan(active):
            generator = active.state.generator
            engine = active.state.engine
            config = engine.runtime.model.config
            actual = {'backend': generator.s.backend, 'upstream_model': generator.s.upstream_model,
                'mlx_max_prompt': generator.s.mlx_max_prompt,
                'gen_max_tokens': generator.s.gen_max_tokens,
                'readout_canvas_setting': generator.s.canvas,
                'loaded_model_context': config.text_config.max_position_embeddings,
                'loaded_native_canvas': config.canvas_length}
            expected = {'backend': 'mlx', 'upstream_model': 'diffusiongemma-26b',
                'mlx_max_prompt': 32768, 'gen_max_tokens': 8192,
                'readout_canvas_setting': 64, 'loaded_model_context': 262144,
                'loaded_native_canvas': 256}
            if actual != expected or generator.s.mlx_model != manifest['model_artifact']:
                raise ValueError('Loaded OpenJev server settings or model capacity differ')
            record = {'contract': 'openjev-generated-exact-loaded-server-v1',
                'manifest': binding(MANIFEST), 'preflight': binding(PREFLIGHT),
                'review_receipt_sha256': receipt_sha, 'source_commit': manifest['source_commit'],
                'artifact_revision': manifest['artifact_revision'], 'host': '127.0.0.1',
                'port': 8080, 'pid': os.getpid(), 'loaded_utc': utc(), **actual,
                'runtime_identity': identity,
                'model_loaded': True, 'inference_performed_at_attestation': False}
            with ATTESTATION.open('x') as stream:
                json.dump(record, stream, indent=2)
                stream.write('\n')
                stream.flush(); os.fsync(stream.fileno())
            yield

    app.router.lifespan_context = checked_lifespan
    uvicorn.run(app, host='127.0.0.1', port=8080, log_level='warning')


def inspect_smoke(manifest, item, variant, inspection_path, inspection_sha):
    if not inspection_path or not inspection_sha:
        raise ValueError('Development requires a separate reviewed smoke inspection')
    smoke = ROOT / item['outputs'][variant]['smoke']
    terminal = smoke.with_name(smoke.name + '.terminal.json')
    if not smoke.is_file() or not terminal.is_file():
        raise ValueError('Smoke evidence is incomplete')
    record = load_bound(inspection_path, inspection_sha)
    expected = {'contract': 'openjev-generated-exact-smoke-inspection-v1',
        'manifest': binding(MANIFEST), 'mode': item['mode'], 'condition': variant,
        'raw_attempts': binding(smoke), 'terminal': binding(terminal)}
    if any(record.get(k) != v for k, v in expected.items()):
        raise ValueError('Smoke inspection identity or evidence changed')
    if not record.get('inspector') or not record.get('inspected_utc'):
        raise ValueError('Smoke inspection lacks inspector or timestamp')
    raw = read_rows(smoke)
    declared = record.get('records')
    if len(raw) != 3 or not isinstance(declared, list) or len(declared) != 3:
        raise ValueError('Complete three-record smoke inspection required')
    for row, declaration in zip(raw, declared):
        if declaration.get('id') != row['id'] or declaration.get('status') != row['status'] or declaration.get('prediction') != row['prediction']:
            raise ValueError('Inspected smoke row differs')
        if row['status'] == 'invalid_output' and not (declaration.get('accepted_unchanged') is True and declaration.get('inspection_reason')):
            raise ValueError('Intrinsic invalid output needs explicit unchanged acceptance')
        if row['status'] not in ('ok', 'invalid_output') or row['finish_reason'] != 'stop':
            raise ValueError('Smoke had a service or truncation failure')
        parsed = parse_native_response(row['raw_response'], row['input_tokens'])
        if (row['prediction'] != parsed['prediction'] or row['status'] != parsed['status']
                or row['finish_reason'] != parsed['finish_reason'] or row['returned_model'] != parsed['returned_model']):
            raise ValueError('Smoke strict parse or model identity differs from raw response')
    inspected = datetime.fromisoformat(record['inspected_utc'])
    finished = max(datetime.fromisoformat(row['finished_utc']) for row in raw)
    if inspected.tzinfo is None or not finished < inspected <= datetime.now(timezone.utc):
        raise ValueError('Smoke inspection chronology changed')
    return binding(inspection_path)


def parse_native_response(response, input_tokens):
    """Keep intrinsic JSON invalidity distinct from service/control failures."""
    if not isinstance(response, dict) or response.get('model') != 'diffusiongemma-26b':
        raise ValueError('Returned model identity mismatch')
    usage = response.get('usage')
    # Native stream stops emitting at max_tokens=2048. The extra 255-token
    # capacity reserve is a denoising canvas allocation, not emitted tokens.
    if (not isinstance(usage, dict) or type(usage.get('prompt_tokens')) is not int
            or usage['prompt_tokens'] != input_tokens
            or type(usage.get('completion_tokens')) is not int
            or not 0 <= usage['completion_tokens'] <= 2048):
        raise ValueError('Native usage differs from exact request or output reserve')
    choices = response.get('choices')
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        raise ValueError('Malformed native completion envelope')
    choice = choices[0]
    finish = choice.get('finish_reason')
    content = choice.get('message', {}).get('content') if isinstance(choice.get('message'), dict) else None
    if not isinstance(finish, str) or not isinstance(content, str):
        raise ValueError('Malformed native completion choice')
    try:
        prediction = json.loads(content)
    except (ValueError, TypeError):
        prediction = None
    prediction = prediction if valid(prediction) else None
    return {'returned_model': response['model'], 'usage': usage, 'finish_reason': finish,
            'prediction': prediction,
            'status': 'ok' if prediction is not None and finish == 'stop' else 'invalid_output'}


def execute(manifest, preflight, receipt_sha, attestation_sha, item, variant, stage,
            inspection_path=None, inspection_sha=None):
    if stage not in ('smoke', 'development'):
        raise ValueError('Only smoke or development can execute')
    output = ROOT / item['outputs'][variant][stage]
    events = output.with_name(output.name + '.events.jsonl')
    terminal = output.with_name(output.name + '.terminal.json')
    if any(path.exists() for path in (output, events, terminal)):
        raise FileExistsError('An OpenJev output, event, or terminal artifact already exists')
    runtime_identity(manifest)
    attestation = verify_server_attestation(manifest, binding(PREFLIGHT)['sha256'], receipt_sha, attestation_sha)
    inspection = None
    if stage == 'development':
        inspection = inspect_smoke(manifest, item, variant, inspection_path, inspection_sha)
    rows = read_rows(ROOT / manifest['inputs']['file'])
    expected_ids = [f'DEV-{n:03d}' for n in range(1, 61)]
    if [r['id'] for r in rows] != expected_ids or any(set(r) != {'id', 'feedback'} for r in rows):
        raise ValueError('Exact 60 input-only records required')
    selected = rows[:3] if stage == 'smoke' else rows
    token_rows = preflight['conditions'][item['mode'] + '/' + variant]['records']
    if [r['id'] for r in token_rows] != expected_ids:
        raise ValueError('Exact token preflight membership changed')
    policy = (ROOT / manifest['policy_source']['file']).read_text().split('## Simulated routing')[0]
    payloads = []
    for row, token in zip(selected, token_rows):
        payload, audit = generated_variant_payload(row['feedback'], policy, 'diffusiongemma-26b',
            item['mode'], variant, item['parent_baseline_id'])
        if sha(json.dumps(payload, sort_keys=True).encode()) != token['wire_request_sha256'] or token['input_tokens'] > 32768:
            raise ValueError('Live OpenJev client request differs from exact preflight')
        payloads.append((row, token, payload, audit))
    if stage == 'development':
        inspected = schedule.claim(manifest['schedule'], JOURNAL, item['configuration_id'], variant, 'inspected_admission', ROOT)
        schedule.finish(manifest['schedule'], JOURNAL, inspected['attempt_id'], 'completed',
                        [inspection, binding(MANIFEST), binding(PREFLIGHT)], ROOT)
    claim = schedule.claim(manifest['schedule'], JOURNAL, item['configuration_id'], variant, stage, ROOT)
    count = 0
    status = 'stopped'
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x') as out, events.open('x') as event_file:
            for row, token, payload, audit in payloads:
                body_bytes = json.dumps(payload).encode()
                started = utc()
                event_file.write(json.dumps({'event': 'started', 'id': row['id'], 'utc': started,
                    'request_body_sha256': sha(body_bytes)}) + '\n')
                event_file.flush(); os.fsync(event_file.fileno())
                rec = {'id': row['id'], 'mode': item['mode'], 'condition': variant,
                    'stage': stage, 'requested_model': 'diffusiongemma-26b',
                    'artifact_revision': manifest['artifact_revision'], 'host': platform.platform(),
                    'execution_manifest': binding(MANIFEST), 'server_attestation': attestation,
                    'schedule_attempt_id': claim['attempt_id'], 'prompt_variant': audit,
                    'request': payload, 'request_body_utf8': body_bytes.decode(),
                    'request_body_sha256': sha(body_bytes), 'request_sha256': token['wire_request_sha256'],
                    'rendered_token_ids_sha256': token['rendered_token_ids_sha256'],
                    'input_tokens': token['input_tokens'], 'reference_labels_read': False,
                    'retry_policy': 'none', 'attempts': 1, 'started_utc': started}
                clock = time.perf_counter()
                try:
                    request = urllib.request.Request('http://127.0.0.1:8080/v1/chat/completions',
                        data=body_bytes, headers={'Content-Type': 'application/json'})
                    token_value = os.environ.get('OPENJEV_API_KEY')
                    if token_value:
                        request.add_header('Authorization', 'Bearer ' + token_value)
                    with OPENER.open(request, timeout=180) as response:
                        response_bytes = response.read()
                        rec['http_status'] = response.status
                    rec['response_body_utf8'] = response_bytes.decode()
                    response = json.loads(response_bytes)
                    rec['raw_response'] = response
                    rec.update(parse_native_response(response, token['input_tokens']))
                except Exception as exc:
                    if isinstance(exc, urllib.error.HTTPError):
                        rec['http_status'] = exc.code
                        rec['response_body_utf8'] = exc.read().decode('utf-8', errors='replace')
                    rec.update(status='service_error', prediction=None,
                               error_type=type(exc).__name__, error=str(exc)[:500])
                rec['elapsed_seconds'] = time.perf_counter() - clock
                rec['finished_utc'] = utc()
                out.write(json.dumps(rec) + '\n'); out.flush(); os.fsync(out.fileno()); count += 1
                event_file.write(json.dumps({'event': 'finished', 'id': row['id'],
                    'utc': rec['finished_utc'], 'status': rec['status']}) + '\n')
                event_file.flush(); os.fsync(event_file.fileno())
                print(row['id'], rec['status'], flush=True)
                if rec['status'] == 'service_error' or rec.get('finish_reason') != 'stop':
                    break
        status = 'completed' if count == len(selected) and rec['status'] != 'service_error' and rec.get('finish_reason') == 'stop' else 'stopped'
    except BaseException as exc:
        with terminal.open('x') as stream:
            json.dump({'status': 'stopped', 'records_saved': count, 'exception': type(exc).__name__,
                       'error': str(exc)[:500], 'utc': utc(), 'manifest': binding(MANIFEST)}, stream, indent=2)
            stream.write('\n')
        schedule.finish(manifest['schedule'], JOURNAL, claim['attempt_id'], 'stopped',
                        [binding(terminal), binding(MANIFEST), attestation], ROOT)
        raise
    with terminal.open('x') as stream:
        json.dump({'status': status, 'records_saved': count, 'expected': len(selected),
                   'utc': utc(), 'manifest': binding(MANIFEST)}, stream, indent=2)
        stream.write('\n')
    schedule.finish(manifest['schedule'], JOURNAL, claim['attempt_id'], status,
                    [binding(output), binding(events), binding(terminal), binding(MANIFEST), attestation], ROOT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--serve', action='store_true')
    action.add_argument('--run-stage', choices=('smoke', 'development'))
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--preflight-sha256', required=True)
    parser.add_argument('--review-receipt', required=True)
    parser.add_argument('--review-receipt-sha256', required=True)
    parser.add_argument('--server-attestation-sha256')
    parser.add_argument('--mode', choices=tuple(MODES))
    parser.add_argument('--variant', choices=('P1', 'P2'))
    parser.add_argument('--smoke-inspection')
    parser.add_argument('--smoke-inspection-sha256')
    args = parser.parse_args()
    manifest, preflight, _ = load_review(args.manifest_sha256, args.preflight_sha256,
                                          args.review_receipt, args.review_receipt_sha256)
    if args.serve:
        if args.mode or args.variant or args.server_attestation_sha256:
            parser.error('--serve takes no mode, variant, or server attestation')
        serve(manifest, args.preflight_sha256, args.review_receipt_sha256)
    else:
        if not (args.mode and args.variant and args.server_attestation_sha256):
            parser.error('--run-stage requires --mode, --variant, and --server-attestation-sha256')
        item = condition(manifest, args.mode, args.variant)
        execute(manifest, preflight, args.review_receipt_sha256, args.server_attestation_sha256,
                item, args.variant, args.run_stage, args.smoke_inspection,
                args.smoke_inspection_sha256)


if __name__ == '__main__':
    main()
