#!/usr/bin/env python3
"""Metadata proof and development-only continuation for one frozen v2 Gemini smoke.

The recovery proof is offline and additive. This controller cannot replay a smoke.
Generation metadata GETs may retry; chat completion POSTs never do.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.error
from urllib.parse import quote

from gemini_openrouter_batch_v2 import *
from codex_batch_benchmark import parse_batch
from development_benchmark import read_rows

RECOVERY_SCHEMA = 'gemini-openrouter-smoke-recovery-proof-v1'
APPROVAL_SCHEMA = 'gemini-openrouter-continuation-approval-v1'
METADATA_FILE = 'smoke-recovered-generation-metadata.json'


def one_jsonl(path, expected):
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if len(rows) != expected:
        raise ValueError('Unexpected row count: ' + path.name)
    return rows


def recovery_evidence(manifest_path):
    manifest_path = inside(manifest_path)
    m = json.loads(manifest_path.read_text())
    if m.get('schema') != 'gemini-openrouter-batch-v2' or m.get('variant') != 'P0':
        raise ValueError('Recovery requires original v2 P0 manifest')
    if m.get('model') not in ROSTER or m.get('effort') not in ROSTER[m['model']]:
        raise ValueError('Unexpected Gemini model or effort')
    folder = manifest_path.parent
    bindings = {name: binding(folder / name) for name in (
        'manifest.json', 'smoke-attempts.jsonl', 'smoke-records.jsonl',
        'smoke-journal.jsonl', METADATA_FILE)}
    attempt = one_jsonl(folder / 'smoke-attempts.jsonl', 1)[0]
    rows = one_jsonl(folder / 'smoke-records.jsonl', 3)
    journal = [json.loads(line) for line in (folder / 'smoke-journal.jsonl').read_text().splitlines() if line.strip()]
    if len(journal) != 4 or journal[-1] != {
        'event': 'terminal', 'phase': 'smoke', 'expected_batches': 1,
        'started_batches': 1, 'finished_batches': 1, 'completed': False,
        'reason': 'identity_unverified'}:
        raise ValueError('Original smoke terminal evidence mismatch')
    if attempt.get('status') != 'identity_unverified' or attempt.get('billing_ok') is not True or attempt.get('cost_unknown') is not False:
        raise ValueError('Recovery accepts only one known-cost metadata lookup failure')
    if attempt.get('generation_metadata_error_type') != 'HTTPError':
        raise ValueError('Unexpected reason for original identity failure')
    if attempt.get('manifest_sha256') != sha(manifest_path.read_bytes()) or attempt.get('request_sha256') != m['requests'][0]['payload_sha256']:
        raise ValueError('Original attempt is not bound to frozen smoke request')
    if attempt.get('ids') != ['DEV-001', 'DEV-002', 'DEV-003'] or [r.get('id') for r in rows] != attempt['ids']:
        raise ValueError('Smoke IDs mismatch')
    if any(r.get('status') != 'identity_unverified' or r.get('generation_id') != attempt.get('generation_id') or r.get('request_sha256') != attempt['request_sha256'] for r in rows):
        raise ValueError('Smoke rows do not match attempt')
    if journal[0].get('payload_sha256') != attempt['request_sha256'] or journal[1].get('attempt_id') != attempt['attempt_id'] or journal[2].get('attempt_id') != attempt['attempt_id']:
        raise ValueError('Smoke journal attempt mismatch')
    raw = attempt.get('raw_response')
    if not isinstance(raw, dict) or raw.get('id') != attempt.get('generation_id') or raw.get('provider') != PROVIDER_NAME:
        raise ValueError('Original response identity mismatch')
    if raw.get('model') != attempt.get('returned_model') or raw.get('model') != m['model']:
        raise ValueError('Original response model mismatch')
    metadata = json.loads((folder / METADATA_FILE).read_text())
    allowed_meta = {'id', 'model', 'provider_name', 'generation_time', 'latency',
                    'native_tokens_prompt', 'native_tokens_completion',
                    'native_tokens_reasoning', 'total_cost', 'num_search_results', 'num_fetches'}
    if not isinstance(metadata, dict) or set(metadata) - allowed_meta:
        raise ValueError('Metadata sidecar contains unapproved fields')
    endpoints = json.loads(bound(m['endpoints']).read_text())
    catalog = json.loads(bound(m['catalog']).read_text())
    _, endpoint = check_catalog(m['model'], m['effort'], catalog, endpoints)
    allowed = allowed_returned_models(m['model'], endpoint)
    if metadata.get('id') != raw['id'] or metadata.get('provider_name') != PROVIDER_NAME or metadata.get('model') not in allowed:
        raise ValueError('Recovered generation identity mismatch')
    if (metadata.get('num_search_results') not in (None, 0) or metadata.get('num_fetches') not in (None, 0)):
        raise ValueError('Recovered generation used search or fetches')
    cost = price(metadata.get('total_cost'))
    if cost != price(attempt['observed_cost_usd']) or cost != price((raw.get('usage') or {}).get('cost')):
        raise ValueError('Recovered generation cost mismatch')
    usage = raw.get('usage') or {}
    if any((usage.get('server_tool_use_details') or {}).values()):
        raise ValueError('Original generation used server tools')
    for key, usage_key in (('native_tokens_prompt', 'prompt_tokens'), ('native_tokens_completion', 'completion_tokens')):
        if metadata.get(key) != usage.get(usage_key):
            raise ValueError('Recovered token count mismatch')
    choices = raw.get('choices')
    if not isinstance(choices, list) or len(choices) != 1 or choices[0].get('finish_reason') != 'stop' or choices[0].get('error'):
        raise ValueError('Original generation incomplete')
    message = choices[0].get('message') or {}
    if message.get('tool_calls') or message.get('function_call') or message.get('refusal'):
        raise ValueError('Original generation violated controls')
    source_rows = read_rows(ROOT / 'data/pilot/inputs.jsonl')[:3]
    if [r['id'] for r in source_rows] != attempt['ids']:
        raise ValueError('Frozen source IDs mismatch')
    predictions = parse_batch(message.get('content'), source_rows)
    for item in m['source_bindings'].values():
        bound(item)
    return {'schema': RECOVERY_SCHEMA, 'configuration_id': m['configuration_id'],
            'model': m['model'], 'effort': m['effort'], 'generation_id': raw['id'],
            'attempt_id': attempt['attempt_id'], 'observed_cost_usd': str(cost),
            'source_bindings': bindings, 'predictions': predictions,
            'recovered_metadata': metadata, 'original_smoke_terminal': 'identity_unverified'}


def write_proof(args):
    manifest = inside(args.manifest)
    proof = recovery_evidence(manifest)
    path = manifest.parent / 'smoke-recovery-proof-v1.json'
    with path.open('x') as handle:
        handle.write(json.dumps(proof, indent=2, ensure_ascii=False) + '\n')
        handle.flush(); os.fsync(handle.fileno())
    print(json.dumps({'proof': str(path), 'sha256': sha(path.read_bytes())}))


def validate_recovery(manifest_path, proof_path):
    proof_path = inside(proof_path)
    if proof_path != inside(Path(manifest_path).parent / 'smoke-recovery-proof-v1.json'):
        raise ValueError('Unexpected recovery proof location')
    saved = json.loads(proof_path.read_text())
    fresh = recovery_evidence(manifest_path)
    if saved != fresh:
        raise ValueError('Recovery proof or original evidence changed')
    return saved


def continuation_approval(path, manifest_sha, proof_sha, budget_sha, partition_id):
    data = json.loads(inside(path).read_text())
    expected = {'schema': APPROVAL_SCHEMA, 'approved': True,
                'manifest_sha256': manifest_sha, 'smoke_recovery_proof_sha256': proof_sha,
                'controller_sha256': sha(Path(__file__).read_bytes()),
                'budget_manifest_sha256': budget_sha, 'partition_id': partition_id,
                'phase': 'development'}
    if data != expected:
        raise ValueError('Exact reviewed continuation approval missing or mismatched')


def fetch_generation_with_retry(generation_id, key, timeout):
    # GET only: a freshly returned generation may not yet be indexed.
    for index in range(3):
        try:
            return fetch('/generation?id=' + quote(generation_id, safe=''), key,
                         timeout=min(timeout, 30))
        except urllib.error.HTTPError as exc:
            if exc.code != 404 or index == 2:
                raise
            time.sleep(1)

def run_development(args):
    path = inside(args.manifest)
    manifest_bytes = path.read_bytes()
    digest_sha = sha(manifest_bytes)
    if digest_sha != args.manifest_sha256:
        raise ValueError('Manifest hash mismatch')
    m = json.loads(manifest_bytes)
    if m.get('schema') != 'gemini-openrouter-batch-v2' or m.get('model') not in ROSTER or m.get('variant') not in ('P0', 'P1', 'P2'):
        raise ValueError('Invalid frozen manifest')
    model, effort, variant = m['model'], m['effort'], m['variant']
    if effort not in ROSTER[model] or m['provider'] != PROVIDER or m['max_output_tokens'] != MAX_OUTPUT or m['input_allowance_tokens'] != ALLOWANCE_TOKENS:
        raise ValueError('Frozen configuration drift')
    if m.get('parent_p0'):
        parent = m['parent_p0']
        for key in ('manifest', 'development_records', 'development_attempts', 'development_journal'):
            bound(parent[key])
        if json.loads(bound(parent['manifest']).read_text()).get('configuration_id') != parent['baseline_id']:
            raise ValueError('Parent baseline mismatch')
    elif variant != 'P0':
        raise ValueError('Prompt comparison lacks hosted P0 parent')
    for item in m['source_bindings'].values():
        bound(item)
    cat = json.loads(bound(m['catalog']).read_text())
    eps = json.loads(bound(m['endpoints']).read_text())
    frozen_model, frozen_endpoint = check_catalog(model, effort, cat, eps)
    expected = prepared_requests(model, effort, variant, m['parent_p0']['baseline_id'] if m['parent_p0'] else m['configuration_id'], frozen_endpoint)
    if expected != m['requests'] or len(expected) != 7:
        raise ValueError('Frozen requests differ from controller output')
    phase = 'development'
    output_dir = path.parent
    outfile = output_dir / (phase + '-records.jsonl')
    attemptsfile = output_dir / (phase + '-attempts.jsonl')
    journalfile = output_dir / (phase + '-journal.jsonl')
    if any(p.exists() for p in (outfile, attemptsfile, journalfile)):
        raise FileExistsError('Exclusive phase outputs already exist')
    budget_manifest = inside(args.budget_manifest)
    budget_sha = sha(budget_manifest.read_bytes())
    proof_path = output_dir / 'smoke-recovery-proof-v1.json'
    proof_sha = sha(proof_path.read_bytes())
    validate_recovery(path, proof_path)
    continuation_approval(args.approval, digest_sha, proof_sha, budget_sha,
                          args.partition_id)
    # Fresh public metadata can only confirm unchanged exact endpoint controls.
    live_catalog = fetch('/models', timeout=m['timeout_seconds'])
    live_eps = fetch('/models/' + quote(model, safe='/') + '/endpoints', timeout=m['timeout_seconds'])
    live_model, live_endpoint = check_catalog(model, effort, live_catalog, live_eps)
    for key_name in ('reasoning', 'supported_parameters'):
        if live_model.get(key_name) != frozen_model.get(key_name):
            raise ValueError('Live model control drift: ' + key_name)
    for key in ('tag', 'provider_name', 'model_id', 'context_length', 'max_completion_tokens', 'pricing', 'supported_parameters'):
        if live_endpoint.get(key) != frozen_endpoint.get(key):
            raise ValueError('Live endpoint drift: ' + key)
    requests = expected[:1] if phase == 'smoke' else expected[1:]
    key = load_key(args.env_file)
    if not isinstance(key, str) or not key.strip():
        raise ValueError('Nonempty OpenRouter key required before budget or inference')
    ledger = open_partition(MASTER, budget_manifest, args.partition_id, model, PROVIDER, effort)
    try:
        with outfile.open('x') as out, attemptsfile.open('x') as audits, journalfile.open('x') as journal:
            started_count = 0
            finished_count = 0
            stop_reason = None
            try:
                for index, request in enumerate(requests):
                    payload = request['payload']
                    reserve = Decimal(request['reserve_usd'])
                    group_ids = request['record_ids']
                    durable(journal, {'event': 'intent', 'phase': phase, 'ids': group_ids, 'payload_sha256': request['payload_sha256'], 'reserve_usd': str(reserve)})
                    attempt_id = ledger.reserve(reserve, ','.join(group_ids))
                    started_count += 1
                    started = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
                    record = {'attempt_id': attempt_id, 'phase': phase, 'batch_index': index if phase == 'smoke' else index + 1,
                              'ids': group_ids, 'started_utc': started, 'model': model, 'effort': effort,
                              'provider': PROVIDER, 'requested_endpoint': frozen_endpoint,
                              'request': payload, 'request_sha256': request['payload_sha256'],
                              'reserved_cost_usd': str(reserve), 'reference_labels_read': False,
                              'manifest_sha256': digest_sha, 'budget_partition_id': args.partition_id,
                              'timing_note': 'No client wall time is labeled provider inference time.'}
                    durable(journal, {'event': 'started', 'attempt_id': attempt_id, 'ids': group_ids, 'started_utc': started})
                    actual = None
                    response = None
                    try:
                        response = fetch('/chat/completions', key, payload, m['timeout_seconds'])
                        response = json.loads(json.dumps(response).replace(key, '[REDACTED]'))
                        record['raw_response'] = response
                        record['generation_id'] = response.get('id')
                        record['returned_model'] = response.get('model')
                        record['returned_provider'] = response.get('provider')
                        record['usage'] = response.get('usage')
                        reported_cost = (response.get('usage') or {}).get('cost')
                        if reported_cost is not None:
                            actual = price(reported_cost)
                        generation_id = response.get('id')
                        metadata = None
                        if isinstance(generation_id, str) and generation_id:
                            try:
                                lookup = fetch_generation_with_retry(generation_id, key, m['timeout_seconds'])
                                raw_metadata = lookup.get('data') if isinstance(lookup, dict) else None
                                if not isinstance(raw_metadata, dict) or raw_metadata.get('id') != generation_id:
                                    raise ValueError('Generation metadata identity mismatch')
                                allowed_fields = ('id', 'model', 'provider_name', 'generation_time', 'latency',
                                                  'native_tokens_prompt', 'native_tokens_completion',
                                                  'native_tokens_reasoning', 'tokens_prompt', 'tokens_completion',
                                                  'total_cost', 'num_fetches', 'num_search_results', 'web_search_engine')
                                metadata = {field: raw_metadata.get(field) for field in allowed_fields}
                                record['generation_metadata'] = metadata
                                if metadata.get('total_cost') is not None:
                                    metadata_cost = price(metadata['total_cost'])
                                    record['generation_total_cost_usd'] = str(metadata_cost)
                                    if actual is None:
                                        actual = metadata_cost
                                    elif abs(actual - metadata_cost) > Decimal('0.000001'):
                                        record['billing_mismatch'] = True
                                        actual = max(actual, metadata_cost)
                            except Exception as metadata_error:
                                record['generation_metadata_error_type'] = type(metadata_error).__name__
                        else:
                            record['generation_metadata_error_type'] = 'MissingGenerationId'
                        choices = response['choices']
                        if not isinstance(choices, list) or len(choices) != 1 or choices[0].get('error'):
                            raise ValueError('Provider returned no single clean choice')
                        choice = choices[0]
                        message = choice['message']
                        record['finish_reason'] = choice.get('finish_reason')
                        tool_usage = (response.get('usage') or {}).get('server_tool_use_details') or {}
                        allowed_models = allowed_returned_models(model, frozen_endpoint)
                        record['allowed_returned_models'] = sorted(allowed_models)
                        if response.get('model') not in allowed_models or (response.get('provider') is not None and response.get('provider') != PROVIDER_NAME):
                            record['status'] = 'identity_violation'
                        elif metadata is None or metadata.get('provider_name') != PROVIDER_NAME or metadata.get('model') not in allowed_models:
                            record['status'] = 'identity_unverified'
                        elif record.get('billing_mismatch'):
                            record['status'] = 'billing_mismatch'
                        elif message.get('tool_calls') or message.get('function_call') or message.get('refusal') or any(tool_usage.values()) or (metadata.get('num_fetches') or 0) or (metadata.get('num_search_results') or 0):
                            record['status'] = 'control_violation'
                        else:
                            try:
                                ids_to_rows = {r['id']: r for r in read_rows(ROOT / 'data/pilot/inputs.jsonl')}
                                group = [ids_to_rows[i] for i in group_ids]
                                predictions = parse_batch(message.get('content'), group)
                                record['predictions'] = predictions
                                record['status'] = 'ok' if choice.get('finish_reason') == 'stop' else 'invalid_output'
                            except (ValueError, TypeError) as exc:
                                record['status'] = 'invalid_output'
                                record['parse_error'] = str(exc)
                    except Exception as exc:
                        record['status'] = 'service_error'
                        record['error_type'] = type(exc).__name__
                        if isinstance(exc, urllib.error.HTTPError):
                            record['http_status'] = exc.code
                            try:
                                record['raw_error_response'] = json.loads(exc.read(1000000).decode().replace(key, '[REDACTED]'))
                            except (ValueError, UnicodeError):
                                pass
                    billing_ok = ledger.settle(attempt_id, actual)
                    record['observed_cost_usd'] = str(actual) if actual is not None else None
                    record['cost_unknown'] = actual is None
                    record['billing_ok'] = billing_ok
                    record['aggregate_cap_usd'] = str(ledger.master_cap)
                    durable(audits, record)
                    durable(journal, {'event': 'finished', 'attempt_id': attempt_id, 'status': record['status'], 'billing_ok': billing_ok})
                    finished_count += 1
                    for pos, case_id in enumerate(group_ids):
                        durable(out, {'id': case_id, 'phase': phase, 'status': record['status'],
                                      'prediction': (record.get('predictions') or {}).get(case_id),
                                      'model': model, 'effort': effort, 'surface': 'OpenRouter Gemini hosted batch10',
                                      'batch_index': record['batch_index'], 'batch_size': len(group_ids),
                                      'batch_position': pos, 'generation_id': record.get('generation_id'),
                                      'request_sha256': record['request_sha256'],
                                      'cost_amortization': 'batch cost retained once in attempt; not an individual-record charge'})
                    print(phase, record['batch_index'], record['status'], 'billing_ok', billing_ok, flush=True)
                    if not billing_ok or record['status'] not in ('ok', 'invalid_output'):
                        stop_reason = 'billing_unknown_or_overrun' if not billing_ok else record['status']
                        break
            except BaseException as exc:
                stop_reason = 'exception:' + type(exc).__name__
                raise
            finally:
                complete = finished_count == len(requests) and stop_reason is None
                durable(journal, {'event': 'terminal', 'phase': phase, 'expected_batches': len(requests),
                                  'started_batches': started_count, 'finished_batches': finished_count,
                                  'completed': complete, 'reason': 'completed' if complete else stop_reason})
    finally:
        ledger.close()



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('write-proof', help='Offline additive proof for recovered v2 smoke')
    p.add_argument('--manifest', required=True)
    d = sub.add_parser('run-development', help='Paid six batches; no smoke replay')
    d.add_argument('--manifest', required=True)
    d.add_argument('--manifest-sha256', required=True)
    d.add_argument('--budget-manifest', required=True)
    d.add_argument('--partition-id', required=True)
    d.add_argument('--approval', required=True)
    d.add_argument('--env-file')
    args = parser.parse_args()
    if args.command == 'write-proof':
        write_proof(args)
    else:
        run_development(args)


if __name__ == '__main__':
    main()
