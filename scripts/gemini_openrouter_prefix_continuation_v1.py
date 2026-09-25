#!/usr/bin/env python3
"""Additive proof for saved batch 1 and paid continuation for batches 2-6 only."""
import argparse
import json
import os
from pathlib import Path
import time
import urllib.error
from urllib.parse import quote
from decimal import Decimal

from gemini_openrouter_metadata_recovery_v1 import *
from codex_batch_benchmark import parse_batch
from development_benchmark import read_rows

PREFIX_SCHEMA = 'gemini-openrouter-development-prefix-proof-v1'
SUFFIX_APPROVAL_SCHEMA = 'gemini-openrouter-suffix-approval-v1'
BATCH1_METADATA = 'development-batch1-recovered-generation-metadata.json'


def prefix_evidence(manifest_path):
    manifest_path = inside(manifest_path)
    m = json.loads(manifest_path.read_text())
    if m.get('schema') != 'gemini-openrouter-batch-v2' or m.get('variant') != 'P0' or m.get('model') != 'google/gemini-3.8-flash' or m.get('effort') != 'low':
        raise ValueError('Prefix recovery is restricted to frozen 3.8 Flash low P0')
    folder = manifest_path.parent
    validate_recovery(manifest_path, folder / 'smoke-recovery-proof-v1.json')
    bindings = {name: binding(folder / name) for name in (
        'manifest.json', 'smoke-recovery-proof-v1.json',
        'development-attempts.jsonl', 'development-records.jsonl',
        'development-journal.jsonl', BATCH1_METADATA)}
    attempt = one_jsonl(folder / 'development-attempts.jsonl', 1)[0]
    rows = one_jsonl(folder / 'development-records.jsonl', 10)
    journal = [json.loads(line) for line in (folder / 'development-journal.jsonl').read_text().splitlines() if line.strip()]
    if len(journal) != 4 or journal[-1] != {
        'event': 'terminal', 'phase': 'development', 'expected_batches': 6,
        'started_batches': 1, 'finished_batches': 1, 'completed': False,
        'reason': 'identity_unverified'}:
        raise ValueError('Original development terminal evidence mismatch')
    ids = [f'DEV-{i:03}' for i in range(1, 11)]
    if attempt.get('batch_index') != 1 or attempt.get('ids') != ids or [r.get('id') for r in rows] != ids:
        raise ValueError('Original development prefix IDs mismatch')
    if attempt.get('status') != 'identity_unverified' or attempt.get('billing_ok') is not True or attempt.get('cost_unknown') is not False:
        raise ValueError('Original prefix is not a known-cost metadata lookup failure')
    if attempt.get('generation_metadata_error_type') != 'HTTPError' or attempt.get('manifest_sha256') != sha(manifest_path.read_bytes()):
        raise ValueError('Original prefix identity or manifest mismatch')
    if attempt.get('request_sha256') != m['requests'][1]['payload_sha256'] or attempt.get('request') != m['requests'][1]['payload']:
        raise ValueError('Original prefix was not frozen batch 1')
    if any(r.get('status') != 'identity_unverified' or r.get('generation_id') != attempt.get('generation_id') or r.get('request_sha256') != attempt['request_sha256'] for r in rows):
        raise ValueError('Original prefix rows mismatch')
    if journal[0].get('payload_sha256') != attempt['request_sha256'] or journal[1].get('attempt_id') != attempt['attempt_id'] or journal[2].get('attempt_id') != attempt['attempt_id']:
        raise ValueError('Original prefix journal mismatch')
    raw = attempt.get('raw_response')
    if not isinstance(raw, dict) or raw.get('id') != attempt.get('generation_id') or raw.get('provider') != PROVIDER_NAME:
        raise ValueError('Original prefix response provider mismatch')
    endpoints = json.loads(bound(m['endpoints']).read_text())
    catalog = json.loads(bound(m['catalog']).read_text())
    _, endpoint = check_catalog(m['model'], m['effort'], catalog, endpoints)
    allowed = allowed_returned_models(m['model'], endpoint)
    if raw.get('model') not in allowed or raw.get('model') != attempt.get('returned_model'):
        raise ValueError('Original prefix model mismatch')
    metadata = json.loads((folder / BATCH1_METADATA).read_text())
    allowed_meta = {'id', 'model', 'provider_name', 'generation_time', 'latency',
                    'native_tokens_prompt', 'native_tokens_completion',
                    'native_tokens_reasoning', 'total_cost', 'num_search_results', 'num_fetches'}
    if not isinstance(metadata, dict) or set(metadata) - allowed_meta:
        raise ValueError('Recovered prefix metadata contains unapproved fields')
    if metadata.get('id') != raw['id'] or metadata.get('model') not in allowed or metadata.get('provider_name') != PROVIDER_NAME:
        raise ValueError('Recovered prefix metadata identity mismatch')
    if metadata.get('num_search_results') not in (None, 0) or metadata.get('num_fetches') not in (None, 0):
        raise ValueError('Recovered prefix used search or fetches')
    cost = price(metadata.get('total_cost'))
    if cost != price(attempt['observed_cost_usd']) or cost != price((raw.get('usage') or {}).get('cost')):
        raise ValueError('Recovered prefix cost mismatch')
    usage = raw.get('usage') or {}
    if any((usage.get('server_tool_use_details') or {}).values()):
        raise ValueError('Original prefix used server tools')
    for key, usage_key in (('native_tokens_prompt', 'prompt_tokens'), ('native_tokens_completion', 'completion_tokens')):
        if metadata.get(key) != usage.get(usage_key):
            raise ValueError('Recovered prefix token count mismatch')
    choices = raw.get('choices')
    if not isinstance(choices, list) or len(choices) != 1 or choices[0].get('finish_reason') != 'stop' or choices[0].get('error'):
        raise ValueError('Original prefix incomplete')
    message = choices[0].get('message') or {}
    if message.get('tool_calls') or message.get('function_call') or message.get('refusal'):
        raise ValueError('Original prefix violated controls')
    source_rows = read_rows(ROOT / 'data/pilot/inputs.jsonl')[:10]
    if [r['id'] for r in source_rows] != ids:
        raise ValueError('Frozen source rows mismatch')
    predictions = parse_batch(message.get('content'), source_rows)
    return {'schema': PREFIX_SCHEMA, 'configuration_id': m['configuration_id'],
            'model': m['model'], 'effort': m['effort'], 'batch_index': 1,
            'attempt_id': attempt['attempt_id'], 'generation_id': raw['id'],
            'observed_cost_usd': str(cost), 'source_bindings': bindings,
            'predictions': predictions, 'recovered_metadata': metadata,
            'original_development_terminal': 'identity_unverified'}


def write_prefix_proof(args):
    manifest = inside(args.manifest)
    proof = prefix_evidence(manifest)
    path = manifest.parent / 'development-prefix-recovery-proof-v1.json'
    with path.open('x') as handle:
        handle.write(json.dumps(proof, indent=2, ensure_ascii=False) + '\n')
        handle.flush(); os.fsync(handle.fileno())
    print(json.dumps({'proof': str(path), 'sha256': sha(path.read_bytes())}))


def validate_prefix(manifest_path, proof_path):
    proof_path = inside(proof_path)
    if proof_path != inside(Path(manifest_path).parent / 'development-prefix-recovery-proof-v1.json'):
        raise ValueError('Unexpected prefix proof location')
    saved = json.loads(proof_path.read_text())
    if saved != prefix_evidence(manifest_path):
        raise ValueError('Prefix proof or original evidence changed')
    return saved


def suffix_approval(path, manifest_sha, proof_sha, budget_sha, partition_id):
    data = json.loads(inside(path).read_text())
    expected = {'schema': SUFFIX_APPROVAL_SCHEMA, 'approved': True,
                'manifest_sha256': manifest_sha, 'prefix_recovery_proof_sha256': proof_sha,
                'controller_sha256': sha(Path(__file__).read_bytes()),
                'budget_manifest_sha256': budget_sha, 'partition_id': partition_id,
                'first_batch_index': 2, 'last_batch_index': 6}
    if data != expected:
        raise ValueError('Exact suffix approval missing or mismatched')


def fetch_generation_fallback(generation_id, key, timeout):
    for index in range(12):
        try:
            return fetch('/generation?id=' + quote(generation_id, safe=''), key,
                         timeout=min(timeout, 30))
        except urllib.error.HTTPError as exc:
            if exc.code != 404 or index == 11:
                raise
            time.sleep(1)

def run_remaining(args):
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
    outfile = output_dir / 'development-continuation-v1-records.jsonl'
    attemptsfile = output_dir / 'development-continuation-v1-attempts.jsonl'
    journalfile = output_dir / 'development-continuation-v1-journal.jsonl'
    if any(p.exists() for p in (outfile, attemptsfile, journalfile)):
        raise FileExistsError('Exclusive phase outputs already exist')
    budget_manifest = inside(args.budget_manifest)
    budget_sha = sha(budget_manifest.read_bytes())
    smoke_proof = output_dir / 'smoke-recovery-proof-v1.json'
    validate_recovery(path, smoke_proof)
    proof_path = output_dir / 'development-prefix-recovery-proof-v1.json'
    proof_sha = sha(proof_path.read_bytes())
    validate_prefix(path, proof_path)
    suffix_approval(args.approval, digest_sha, proof_sha, budget_sha,
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
    requests = expected[2:]
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
                    record = {'attempt_id': attempt_id, 'phase': phase, 'batch_index': index + 2,
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
                        if response.get('provider') == PROVIDER_NAME:
                            # The observed completion includes the pinned provider. Telemetry
                            # can be enriched later without stopping a verified paid batch.
                            record['generation_metadata_deferred'] = True
                        elif isinstance(generation_id, str) and generation_id:
                            try:
                                lookup = fetch_generation_fallback(generation_id, key, m['timeout_seconds'])
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
                        elif metadata is not None and (metadata.get('provider_name') != PROVIDER_NAME or metadata.get('model') not in allowed_models):
                            record['status'] = 'identity_violation'
                        elif response.get('provider') != PROVIDER_NAME and metadata is None:
                            record['status'] = 'identity_unverified'
                        elif record.get('billing_mismatch'):
                            record['status'] = 'billing_mismatch'
                        elif message.get('tool_calls') or message.get('function_call') or message.get('refusal') or any(tool_usage.values()) or ((metadata or {}).get('num_fetches') or 0) or ((metadata or {}).get('num_search_results') or 0):
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
    p = sub.add_parser('write-prefix-proof', help='Offline proof for saved batch 1')
    p.add_argument('--manifest', required=True)
    d = sub.add_parser('run-remaining', help='Paid frozen development batches 2 through 6 only')
    d.add_argument('--manifest', required=True)
    d.add_argument('--manifest-sha256', required=True)
    d.add_argument('--budget-manifest', required=True)
    d.add_argument('--partition-id', required=True)
    d.add_argument('--approval', required=True)
    d.add_argument('--env-file')
    args = parser.parse_args()
    if args.command == 'write-prefix-proof': write_prefix_proof(args)
    else: run_remaining(args)


if __name__ == '__main__':
    main()
