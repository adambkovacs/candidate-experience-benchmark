#!/usr/bin/env python3
"""Reviewed Antigravity P1/P2 batches; preparation is entirely offline."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import gemini_batch_benchmark as native
import prompt_schedule
from codex_benchmark import variant_instruction
from codex_batch_benchmark import batch_prompt, batch_schema, durable_write
from development_benchmark import digest, read_rows
from gemini_benchmark import clean_environment

FOLDER = ROOT / 'results/prompt-comparison-v1-2026-09-24/gemini-exact-v2'
MANIFEST = FOLDER / 'execution-manifest.draft.json'
PREFLIGHT = FOLDER / 'preflight.json'
JOURNAL = ROOT / 'results/prompt-comparison-v1-2026-09-24/execution-journal.jsonl'
STOP = {'service_error', 'model_mismatch', 'isolation_violation', 'unverified_configuration'}


def sha(raw): return hashlib.sha256(raw).hexdigest()
def utc(): return datetime.now(timezone.utc).isoformat()
def bind(path):
    path = Path(path).resolve()
    return {'file': str(path.relative_to(ROOT.resolve())), 'sha256': sha(path.read_bytes())}
def bound(spec):
    path = ROOT / spec['file']
    if set(spec) != {'file', 'sha256'} or bind(path) != spec:
        raise ValueError('Source binding mismatch: ' + str(path))
    return path
def bound_json(spec): return json.loads(bound(spec).read_text())
def load_hash(path, expected):
    if not path.is_file() or sha(path.read_bytes()) != expected:
        raise ValueError('Frozen SHA-256 mismatch: ' + str(path))
    return json.loads(path.read_text())
def write_json_exclusive(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def inputs(manifest):
    rows = read_rows(bound(manifest['inputs']))
    if [r.get('id') for r in rows] != [f'DEV-{i:03}' for i in range(1, 61)] or any(set(r) != {'id', 'feedback'} for r in rows):
        raise ValueError('Exact ordered input-only development60 required')
    return rows


def verify_manifest(manifest):
    if manifest.get('contract') != 'gemini-exact-draft-v2' or manifest.get('status') != 'offline_preparation_review_required' or manifest.get('inference_authorized_by_this_manifest') is not False:
        raise ValueError('Unexpected draft contract or status')
    transition = manifest.get('transition')
    if (not isinstance(transition, dict) or transition.get('parent_manifest') !=
            {'file': 'results/prompt-comparison-v1-2026-09-24/gemini-exact-v1/execution-manifest.draft.json',
             'sha256': '809105ff029c07622206a9d4d37bef28d25dba6192a3576cf84f440ab1f8563e'}
            or transition.get('reason') != 'Native CLI changed from 1.2.9 parent baselines to 1.2.10 before P1/P2 execution; P0 baselines remain unchanged.'):
        raise ValueError('CLI version-transition lineage changed')
    bound(transition['parent_manifest'])
    for key in ('inputs', 'policy_source', 'schema', 'schedule', 'readiness', 'roster_freeze', 'cli_interface_attestation'):
        bound(manifest[key])
    for spec in manifest['source_files'].values(): bound(spec)
    cli = Path(manifest['cli']['path'])
    if sha(cli.read_bytes()) != manifest['cli']['sha256'] or manifest['cli']['version'] != '1.2.10':
        raise ValueError('Pinned native CLI changed')
    interface = bound_json(manifest['cli_interface_attestation'])
    required_flags = ['--agent', '--model', '--effort', '--disable-slash-commands', '--sandbox',
        '--output-format', '--json-schema', '--print-timeout', '--log-file', '-p', 'models']
    if (interface.get('contract') != 'gemini-cli-transition-attestation-v2'
            or interface.get('current_launcher_sha256') != manifest['cli']['sha256']
            or interface.get('current_runtime_version') != '1.2.10'
            or interface.get('parent_runtime_version') != '1.2.9'
            or interface.get('parent_launcher_sha256') != '0ff346ae903f15d863bd6a3e401638b612848210d28b174461acdb8780ac8c22'
            or interface.get('required_flags_observed') != required_flags
            or interface.get('inference_performed') is not False):
        raise ValueError('Native CLI transition evidence changed')
    rows = inputs(manifest)
    readiness = bound_json(manifest['readiness'])
    schedule = bound_json(manifest['schedule'])['order']
    gems = [r for r in schedule if r['id'].startswith('antigravity-gemini-')]
    configs = readiness['configurations']
    if len(configs) != 7 or [r['configuration_id'] for r in configs] != [r['id'] for r in gems] or [r['configuration_id'] for r in manifest['configurations']] != [r['id'] for r in gems]:
        raise ValueError('Seven Gemini configurations must match frozen schedule')
    if manifest.get('policy') != {'workflow_mode': 'native-agent-observed-no-external-tools', 'configured_batch_size': 10, 'smoke_size': 3, 'development_size': 60, 'controller_retries': 0, 'intrinsic_invalid_output': 'retain_unchanged_continue', 'control_or_service_failure': 'stop', 'subscription_credits': 'explicit_off'}:
        raise ValueError('Versioned continuation policy changed')
    policy = bound(manifest['policy_source']).read_text().split('## Simulated routing')[0]
    for expected, item in zip(configs, manifest['configurations']):
        cid = item['configuration_id']
        if (item['model'], item['effort'], item['parent_baseline_id'], item['condition_order']) != (expected['model'], expected['effort'], expected['parent_baseline_id'], expected['scheduled_condition_order']):
            raise ValueError('Readiness identity or order differs')
        if item['parent_baseline'] != {'file': expected['baseline_output']['path'], 'sha256': expected['baseline_output']['sha256']}:
            raise ValueError('Parent baseline binding differs')
        bound(item['parent_baseline'])
        if set(item['conditions']) != {'P1', 'P2'}:
            raise ValueError('Both conditions required')
        for condition, evidence in item['conditions'].items():
            for stage, size in (('smoke', 3), ('development', 60)):
                preview = bound_json(evidence[stage + '_preview'])
                if any(preview.get(k) != v for k, v in {'offline_only': True, 'inference_performed': False, 'reference_labels_read': False, 'requested_model': item['model'], 'requested_effort': item['effort'], 'workflow_mode': manifest['policy']['workflow_mode'], 'configured_batch_size': 10, 'controller_timeout_seconds': 600, 'agent_definition': native.AGENT}.items()):
                    raise ValueError('Preview controls differ')
                selected = rows[:size]
                groups = [selected[i:i + 10] for i in range(0, size, 10)]
                if len(preview['requests']) != len(groups): raise ValueError('Preview group count differs')
                for group, request in zip(groups, preview['requests']):
                    prompt = batch_prompt(policy, group, condition, cid)
                    schema = batch_schema(group)
                    _, variant_audit = variant_instruction(policy, 'batch10', condition, cid)
                    if request['record_ids'] != [r['id'] for r in group] or request['request'] != {'prompt': prompt, 'output_schema': schema} or request['request_sha256'] != digest(prompt) or request['schema_sha256'] != digest(json.dumps(schema, sort_keys=True)) or request['prompt_variant'] != variant_audit:
                        raise ValueError('Exact preview request differs')
            for stage in ('smoke', 'development'):
                output = ROOT / evidence[stage + '_output']
                output.resolve().relative_to(FOLDER.resolve())
                if output.name != stage + '.jsonl': raise ValueError('Unexpected output name')
    return rows


def preflight():
    manifest = json.loads(MANIFEST.read_text())
    verify_manifest(manifest)
    return {'contract': 'gemini-exact-offline-preflight-v2', 'manifest': bind(MANIFEST),
        'configuration_count': 7, 'condition_count': 14, 'preview_count': 28,
        'record_count': 60, 'smoke_size': 3, 'development_batches': 6,
        'model_invoked': False, 'inference_performed': False, 'reference_labels_read': False,
        'runtime_identity_status': 'Local 1.2.10 version/help checked; model listing and behavior await live smoke',
        'admission': 'Separate hash-bound root review receipt required'}


def load_review(manifest_sha, preflight_sha, receipt_path, receipt_sha):
    manifest = load_hash(MANIFEST, manifest_sha)
    verify_manifest(manifest)
    evidence = load_hash(PREFLIGHT, preflight_sha)
    expected = preflight()
    if evidence != expected: raise ValueError('Exact offline preflight changed')
    receipt_path = Path(receipt_path).resolve()
    if receipt_path.parent != FOLDER.resolve(): raise ValueError('Review receipt must be within evidence directory')
    receipt = load_hash(receipt_path, receipt_sha)
    required = {'contract': 'gemini-exact-root-review-v2', 'decision': 'approved_for_smoke_then_inspected_development', 'manifest': bind(MANIFEST), 'preflight': bind(PREFLIGHT), 'configurations': [x['configuration_id'] for x in manifest['configurations']]}
    if any(receipt.get(k) != v for k, v in required.items()) or not receipt.get('reviewer') or not receipt.get('reviewed_utc'):
        raise ValueError('Root review does not bind this Gemini execution')
    return manifest, evidence, receipt


def strict_response(stdout, stderr, code, model, group):
    result = native.inspect_stream(stdout, code, model, group, 'native-agent-observed-no-external-tools')
    init = [e['init'] for e in result['raw_events'] if e.get('event') == 'init' and isinstance(e.get('init'), dict)]
    if len(init) == 1 and (any(k in init[0] and init[0][k] != [] for k in ('mcpServers', 'skills', 'plugins'))
            or init[0].get('memory_enabled', False) is not False):
        result['status'] = 'isolation_violation'
    if result['status'] == 'invalid_output' and result.get('error') == 'Finish payload differs from structured result':
        result['status'] = 'isolation_violation'
    if native.control_warning(stderr) and result['status'] in ('ok', 'invalid_output'):
        result['status'] = 'unverified_configuration'
    # The native validator separates complete structured output from service or
    # identity failure. An invalid payload is retained only on successful finish.
    if result['status'] == 'invalid_output' and (code or not any(e.get('event') == 'result' and e.get('result', {}).get('status') == 'SUCCESS' for e in result['raw_events'])):
        result['status'] = 'service_error'
    return result


def inspect_smoke(manifest, item, condition, inspection_path, inspection_sha):
    evidence = item['conditions'][condition]
    output = ROOT / evidence['smoke_output']
    attempts = output.with_name('smoke-attempts.jsonl')
    terminal = output.with_name('smoke.terminal.json')
    inspection_path = Path(inspection_path).resolve()
    if inspection_path.parent != output.parent.resolve(): raise ValueError('Condition-specific smoke inspection required')
    document = load_hash(inspection_path, inspection_sha)
    expected = {'contract': 'gemini-exact-smoke-inspection-v2', 'manifest': bind(MANIFEST), 'configuration_id': item['configuration_id'], 'condition': condition, 'predictions': bind(output), 'raw_attempts': bind(attempts), 'terminal': bind(terminal)}
    if any(document.get(k) != v for k, v in expected.items()) or not document.get('inspector') or not document.get('inspected_utc'):
        raise ValueError('Smoke inspection binding or inspector missing')
    if json.loads(terminal.read_text()).get('status') != 'completed': raise ValueError('Smoke did not complete')
    raw = read_rows(attempts); predictions = read_rows(output)
    if len(raw) != 1 or len(predictions) != 3 or len(document.get('records', [])) != 3:
        raise ValueError('Exact smoke3 inspection required')
    attempt = raw[0]
    if attempt['status'] not in ('ok', 'invalid_output') or attempt['record_order'] != [r['id'] for r in predictions]:
        raise ValueError('Smoke service or ordering failure')
    preview = bound_json(evidence['smoke_preview'])['requests'][0]
    if (attempt.get('request') != preview['request'] or attempt.get('request_sha256') != preview['request_sha256']
            or attempt.get('schema_sha256') != preview['schema_sha256']
            or attempt.get('prompt_variant') != preview['prompt_variant']
            or attempt.get('agent_definition') != native.AGENT
            or attempt.get('reference_labels_read') is not False
            or attempt.get('controller_retries') != 0
            or attempt.get('cli_binary_sha256') != manifest['cli']['sha256']
            or attempt.get('cli_version') != manifest['cli']['version']
            or attempt.get('billing_audit', {}).get('useG1Credits') is not False):
        raise ValueError('Smoke request or subscription controls differ from frozen preview')
    parsed = strict_response(attempt['raw_stdout'], attempt['raw_stderr'], attempt['returncode'], item['model'], inputs(manifest)[:3])
    if parsed['status'] != attempt['status'] or parsed['predictions'] != attempt['predictions']:
        raise ValueError('Saved smoke differs from raw native stream')
    for row, inspected in zip(predictions, document['records']):
        if row['id'] != inspected.get('id') or row['status'] != inspected.get('status') or row['prediction'] != inspected.get('prediction') or row['status'] != attempt['status'] or row['prediction'] != parsed['predictions'].get(row['id']):
            raise ValueError('Smoke inspection differs from raw predictions')
        if row['status'] == 'invalid_output' and not (inspected.get('accepted_unchanged') is True and inspected.get('inspection_reason')):
            raise ValueError('Invalid smoke must be accepted unchanged')
    finished = datetime.fromisoformat(attempt['finished_utc'])
    inspected = datetime.fromisoformat(document['inspected_utc'])
    if finished.tzinfo is None or inspected.tzinfo is None or not finished < inspected <= datetime.now(timezone.utc):
        raise ValueError('Smoke inspection chronology invalid')
    return bind(inspection_path)


def runtime(manifest, item):
    env = clean_environment()
    if 'HOME' not in env: raise ValueError('HOME must be explicit')
    home = Path(env['HOME'])
    audit = native.context_audit(home)
    credits = native.require_credits_off(home)
    cli = manifest['cli']['path']
    version = subprocess.run([cli, '--version'], env=env, text=True, capture_output=True, timeout=30, check=True).stdout.strip()
    if version != manifest['cli']['version']: raise ValueError('Native CLI version changed')
    inventory = subprocess.run([cli, 'models'], env=env, text=True, capture_output=True, timeout=45, check=True)
    if item['model'] not in [line.split()[0] for line in inventory.stdout.splitlines() if line.strip()]:
        raise ValueError('Requested model absent from live native inventory')
    return env, audit, credits, version, inventory.stdout


def run_stage(manifest, item, condition, stage, inspection_path=None, inspection_sha=None):
    if stage not in ('smoke', 'development') or condition not in item['conditions']:
        raise ValueError('Unknown stage or condition')
    evidence = item['conditions'][condition]
    output = ROOT / evidence[stage + '_output']
    attempts = output.with_name(stage + '-attempts.jsonl')
    local_journal = output.with_name(stage + '-attempts.events.jsonl')
    terminal = output.with_name(stage + '.terminal.json')
    if any(p.exists() for p in (output, attempts, local_journal, terminal)):
        raise FileExistsError('Exclusive Gemini output/attempt/event/terminal artifacts required')
    smoke_inspection = None
    if stage == 'development':
        smoke_inspection = inspect_smoke(manifest, item, condition, inspection_path, inspection_sha)
    env, context, credits, version, inventory = runtime(manifest, item)
    rows = inputs(manifest)
    selected = rows[:3] if stage == 'smoke' else rows
    preview = bound_json(evidence[stage + '_preview'])
    # Verify preview and all source hashes again immediately before the claim.
    verify_manifest(manifest)
    if stage == 'development':
        admitted = prompt_schedule.claim(manifest['schedule'], JOURNAL, item['configuration_id'], condition, 'inspected_admission', ROOT)
        prompt_schedule.finish(manifest['schedule'], JOURNAL, admitted['attempt_id'], 'completed', [smoke_inspection, bind(MANIFEST), bind(PREFLIGHT)], ROOT)
    claim = prompt_schedule.claim(manifest['schedule'], JOURNAL, item['configuration_id'], condition, stage, ROOT)
    count = 0; status = 'stopped'; error = None
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('x') as out, attempts.open('x') as attempt_file, local_journal.open('x') as events:
            for index, request in enumerate(preview['requests']):
                group = selected[index * 10:index * 10 + 10]
                if request['record_ids'] != [r['id'] for r in group]: raise ValueError('Live group differs from preview')
                context = native.context_audit(Path(env['HOME']))
                credits = native.require_credits_off(Path(env['HOME']))
                started = utc(); started_clock = time.perf_counter()
                rec = {'id': f'batch-{index + 1:02}', 'phase': stage, 'condition': condition,
                    'configuration_id': item['configuration_id'], 'requested_model': item['model'],
                    'effort': item['effort'], 'workflow_mode': manifest['policy']['workflow_mode'],
                    'record_order': request['record_ids'], 'batch_size': len(group), 'configured_batch_size': 10,
                    'request': request['request'], 'request_sha256': request['request_sha256'],
                    'schema_sha256': request['schema_sha256'], 'prompt_variant': request['prompt_variant'],
                    'agent_definition': native.AGENT, 'cli_version': version, 'cli_binary_sha256': manifest['cli']['sha256'],
                    'model_catalogue_stdout': inventory, 'context_audit': context, 'billing_audit': credits,
                    'reference_labels_read': False, 'controller_retries': 0, 'controller_timeout_seconds': 600,
                    'native_internal_retry_count': 'not_exposed', 'schedule_attempt_id': claim['attempt_id'], 'started_utc': started}
                with tempfile.TemporaryDirectory(prefix='agy-benchmark-', dir='/private/tmp') as tmp:
                    cwd = Path(tmp); agent = cwd / '.agents/agents/recruitment-benchmark.md'
                    agent.parent.mkdir(parents=True); agent.write_text(native.AGENT)
                    schema_file = cwd / 'schema.json'; schema_file.write_text(json.dumps(request['request']['output_schema']))
                    cmd = [manifest['cli']['path'], '--agent', 'recruitment-benchmark', '--model', item['model'], '--effort', item['effort'], '--disable-slash-commands', '--sandbox', '--output-format', 'stream-json', '--json-schema', str(schema_file), '--print-timeout', '600s', '--log-file', str(cwd / 'agy.log'), '-p', request['request']['prompt']]
                    rec['command'] = cmd
                    durable_write(events, {'event': 'request_started', 'id': rec['id'], 'utc': started, 'request_sha256': rec['request_sha256']})
                    try:
                        proc = subprocess.run(cmd, env=env, cwd=cwd, text=True, capture_output=True, timeout=615)
                        rec.update(strict_response(proc.stdout, proc.stderr, proc.returncode, item['model'], group), raw_stdout=proc.stdout, raw_stderr=proc.stderr, returncode=proc.returncode)
                    except subprocess.TimeoutExpired as exc:
                        decode = lambda v: v.decode(errors='replace') if isinstance(v, bytes) else (v or '')
                        rec.update(status='service_error', error_type='TimeoutExpired', raw_stdout=decode(exc.stdout), raw_stderr=decode(exc.stderr), predictions={})
                    logfile = cwd / 'agy.log'
                    if logfile.exists(): rec['runtime_log_metadata'] = {'bytes': logfile.stat().st_size, 'sha256': sha(logfile.read_bytes())}
                rec['elapsed_seconds'] = time.perf_counter() - started_clock
                rec['finished_utc'] = utc()
                durable_write(attempt_file, rec)
                durable_write(events, {'event': 'request_completed', 'id': rec['id'], 'utc': rec['finished_utc'], 'status': rec['status']})
                for position, row in enumerate(group):
                    durable_write(out, {'id': row['id'], 'phase': stage, 'condition': condition, 'status': rec['status'],
                        'prediction': rec['predictions'].get(row['id']), 'requested_model': item['model'],
                        'returned_model': rec.get('reported_model'), 'reasoning_effort': item['effort'],
                        'workflow_mode': manifest['policy']['workflow_mode'], 'batch_id': rec['id'], 'batch_size': len(group),
                        'configured_batch_size': 10, 'batch_position': position, 'started_utc': started,
                        'batch_elapsed_seconds': rec['elapsed_seconds'], 'elapsed_seconds': rec['elapsed_seconds'] / len(group),
                        'timing_kind': 'amortized_batch_share_not_individual_latency', 'request_sha256': rec['request_sha256'],
                        'input_sha256': digest(row['feedback']), 'reference_labels_read': False})
                    count += 1
                print(item['configuration_id'], condition, stage, rec['id'], rec['status'], flush=True)
                if rec['status'] in STOP: break
        status = 'completed' if count == len(selected) and rec['status'] in ('ok', 'invalid_output') else 'stopped'
    except BaseException as exc:
        error = exc
    write_json_exclusive(terminal, {'contract': 'gemini-exact-stage-terminal-v2', 'status': status,
        'records_saved': count, 'expected': len(selected), 'error_type': type(error).__name__ if error else None,
        'error': str(error)[:500] if error else None, 'utc': utc(), 'manifest': bind(MANIFEST)})
    evidence_files = [bind(terminal), bind(MANIFEST), bind(PREFLIGHT)]
    evidence_files.extend(bind(p) for p in (output, attempts, local_journal) if p.exists())
    prompt_schedule.finish(manifest['schedule'], JOURNAL, claim['attempt_id'], status, evidence_files, ROOT)
    if error: raise error
    if status != 'completed': raise RuntimeError('Gemini stage stopped after retained control/service failure')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    action = p.add_mutually_exclusive_group(required=True)
    action.add_argument('--preflight', action='store_true')
    action.add_argument('--run-stage', choices=('smoke', 'development'))
    p.add_argument('--manifest-sha256'); p.add_argument('--preflight-sha256')
    p.add_argument('--review-receipt'); p.add_argument('--review-receipt-sha256')
    p.add_argument('--configuration-id'); p.add_argument('--condition', choices=('P1', 'P2'))
    p.add_argument('--smoke-inspection'); p.add_argument('--smoke-inspection-sha256')
    args = p.parse_args()
    if args.preflight:
        if any((args.manifest_sha256, args.preflight_sha256, args.review_receipt, args.review_receipt_sha256, args.configuration_id, args.condition, args.smoke_inspection, args.smoke_inspection_sha256)):
            p.error('--preflight accepts no live execution arguments')
        write_json_exclusive(PREFLIGHT, preflight()); return
    if not all((args.manifest_sha256, args.preflight_sha256, args.review_receipt, args.review_receipt_sha256, args.configuration_id, args.condition)):
        p.error('Live stage requires frozen hashes, review receipt, configuration, and condition')
    manifest, _, _ = load_review(args.manifest_sha256, args.preflight_sha256, args.review_receipt, args.review_receipt_sha256)
    item = next((x for x in manifest['configurations'] if x['configuration_id'] == args.configuration_id), None)
    if item is None: raise ValueError('Unscheduled Gemini configuration')
    run_stage(manifest, item, args.condition, args.run_stage, args.smoke_inspection, args.smoke_inspection_sha256)


if __name__ == '__main__': main()
