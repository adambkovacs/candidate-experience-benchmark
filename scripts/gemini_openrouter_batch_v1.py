#!/usr/bin/env python3
"""Frozen, budgeted OpenRouter Gemini batch10 benchmark; no automatic retries.

Prepare is offline. Run requires hash-bound operator approval and an existing v2
budget partition. A separately approved smoke inspection binds development.
"""
import argparse
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.error
from urllib.parse import quote

from codex_batch_benchmark import batch_prompt, batch_schema, parse_batch
from development_benchmark import ROOT, read_rows, digest
from openrouter_benchmark import fetch, load_key, allowed_returned_models
from openrouter_budget_v2 import BudgetLedger
from paid_budget_partitions_v2 import open_partition

ROSTER = {
    'google/gemini-3.1-pro-preview': ('low', 'high'),
    'google/gemini-3.6-flash': ('low', 'medium'),
    'google/gemini-3.7-flash': ('low', 'medium', 'high'),
    'google/gemini-3.8-flash': ('low', 'medium', 'high'),
}
PROVIDER = 'google-ai-studio'
PROVIDER_NAME = 'Google AI Studio'
PREP = ROOT / 'results/gemini-openrouter-prep-v1'
MASTER = ROOT / 'results/openrouter-paid-budget.jsonl'
ALLOWANCE_TOKENS = 4096
MAX_OUTPUT = 8192
CONTEXT_THRESHOLD = 200000


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canon(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf-8')


def inside(path):
    p = Path(path).resolve()
    p.relative_to(ROOT.resolve())
    return p


def binding(path):
    path = inside(path)
    return {'path': str(path.relative_to(ROOT)), 'sha256': sha(path.read_bytes())}


def bound(item):
    path = inside(ROOT / item['path'])
    if sha(path.read_bytes()) != item['sha256']:
        raise ValueError('Frozen source hash mismatch: ' + item['path'])
    return path


def durable(handle, obj):
    handle.write(json.dumps(obj, ensure_ascii=False) + '\n')
    handle.flush()
    os.fsync(handle.fileno())


def price(value):
    d = Decimal(str(value))
    if not d.is_finite() or d < 0:
        raise ValueError('Invalid price')
    return d


def check_catalog(model, effort, catalog, endpoints):
    if model not in ROSTER or effort not in ROSTER[model]:
        raise ValueError('Outside exact Gemini roster')
    entries = [m for m in catalog['data'] if m.get('id') == model]
    if len(entries) != 1 or endpoints.get('data', {}).get('id') != model:
        raise ValueError('Model catalog identity mismatch')
    m = entries[0]
    reasoning = m.get('reasoning')
    if not isinstance(reasoning, dict) or reasoning.get('mandatory') is not True or effort not in reasoning.get('supported_efforts', []):
        raise ValueError('Requested reasoning effort is not advertised')
    candidates = [e for e in endpoints['data']['endpoints'] if e.get('tag') == PROVIDER]
    if len(candidates) != 1:
        raise ValueError('Require one exact standard AI Studio endpoint')
    e = candidates[0]
    if (e.get('status'), e.get('model_id'), e.get('provider_name')) != (0, model, PROVIDER_NAME):
        raise ValueError('Endpoint identity or availability mismatch')
    required = {'temperature', 'max_tokens', 'response_format', 'structured_outputs', 'reasoning', 'reasoning_effort', 'tool_choice', 'tools'}
    if not required <= set(e.get('supported_parameters', [])):
        raise ValueError('Endpoint does not advertise required controls')
    if e.get('context_length') != 1048576 or e.get('max_completion_tokens', 0) < MAX_OUTPUT:
        raise ValueError('Unexpected context or output capacity')
    p = e.get('pricing')
    if not isinstance(p, dict):
        raise ValueError('Missing endpoint pricing')
    permitted = {'prompt', 'completion', 'image', 'audio', 'input_audio_cache', 'web_search', 'internal_reasoning', 'input_cache_read', 'input_cache_write', 'discount', 'overrides'}
    if set(p) - permitted:
        raise ValueError('Unexpected pricing category')
    if not isinstance(p.get('overrides'), list) and 'overrides' in p:
        raise ValueError('Unparseable tiered pricing')
    for entry in p.get('overrides', []):
        if not isinstance(entry, dict) or entry.get('min_prompt_tokens') != CONTEXT_THRESHOLD:
            raise ValueError('Unexpected pricing override')
    for k, v in p.items():
        if k != 'overrides':
            price(v)
    if price(p['internal_reasoning']) > price(p['completion']):
        raise ValueError('Reasoning price exceeds completion bound')
    if any(price(p.get(k, 0)) > price(p['prompt']) for k in ('input_cache_read', 'input_cache_write')):
        raise ValueError('Input cache price exceeds prompt bound')
    return m, e


def make_payload(model, effort, group, variant, parent_id, endpoint):
    policy = (ROOT / 'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    prompt = batch_prompt(policy, group, variant, parent_id)
    schema = batch_schema(group)
    p = endpoint['pricing']
    return {
        'model': model, 'temperature': 0, 'max_tokens': MAX_OUTPUT,
        'stream': False, 'reasoning': {'enabled': True, 'effort': effort},
        'provider': {'only': [PROVIDER], 'allow_fallbacks': False,
                     'require_parameters': True,
                     'max_price': {'prompt': float(price(p['prompt']) * 1000000),
                                   'completion': float(price(p['completion']) * 1000000),
                                   'request': 0, 'image': 0}},
        'tools': [], 'tool_choice': 'none',
        'plugins': [{'id': 'web', 'enabled': False}, {'id': 'response-healing', 'enabled': False}],
        'messages': [{'role': 'user', 'content': prompt}],
        'response_format': {'type': 'json_schema', 'json_schema': {
            'name': 'judgments_batch', 'strict': True, 'schema': schema}},
    }


def bound_cost(payload, endpoint):
    # Each UTF-8 byte is allowed to count as a token, plus explicit framing
    # allowance. Count max completion twice in case reasoning is billed apart.
    input_tokens = len(canon(payload)) + ALLOWANCE_TOKENS
    if input_tokens >= CONTEXT_THRESHOLD:
        raise ValueError('Prompt may enter higher price tier')
    p = endpoint['pricing']
    return input_tokens * price(p['prompt']) + MAX_OUTPUT * (price(p['completion']) + price(p['internal_reasoning']))


def prepared_requests(model, effort, variant, parent_id, endpoint):
    rows = read_rows(ROOT / 'data/pilot/inputs.jsonl')
    if len(rows) != 60 or [r.get('id') for r in rows] != [f'DEV-{i:03}' for i in range(1, 61)] or any(set(r) != {'id', 'feedback'} for r in rows):
        raise ValueError('Require exact input-only development60')
    groups = [rows[:3]] + [rows[i:i+10] for i in range(0, 60, 10)]
    result = []
    for group in groups:
        payload = make_payload(model, effort, group, variant, parent_id, endpoint)
        result.append({'record_ids': [r['id'] for r in group], 'payload': payload,
                       'payload_sha256': sha(canon(payload)), 'reserve_usd': str(bound_cost(payload, endpoint))})
    return result


def check_parent(parent, model, effort):
    if not parent:
        raise ValueError('P1/P2 require same-surface hosted P0 evidence')
    path = inside(parent)
    data = json.loads(path.read_text())
    if data.get('schema') != 'gemini-openrouter-batch-v1' or data.get('variant') != 'P0' or data.get('model') != model or data.get('effort') != effort:
        raise ValueError('Parent is not matching hosted Gemini P0')
    dev = inside(path.parent / 'development-records.jsonl')
    attempts = inside(path.parent / 'development-attempts.jsonl')
    dev_journal = inside(path.parent / 'development-journal.jsonl')
    records = [json.loads(x) for x in dev.read_text().splitlines() if x.strip()]
    if [r.get('id') for r in records] != [f'DEV-{i:03}' for i in range(1, 61)]:
        raise ValueError('Parent P0 has no complete ordered development60')
    attempt_rows = [json.loads(x) for x in attempts.read_text().splitlines() if x.strip()]
    if len(attempt_rows) != 6 or any(a.get('billing_ok') is not True or a.get('cost_unknown') or a.get('status') not in ('ok', 'invalid_output') for a in attempt_rows):
        raise ValueError('Parent P0 lacks six billed and admissible batch attempts')
    journal_rows = [json.loads(x) for x in dev_journal.read_text().splitlines() if x.strip()]
    if not journal_rows or journal_rows[-1] != {'event': 'terminal', 'phase': 'development', 'expected_batches': 6, 'started_batches': 6, 'finished_batches': 6, 'completed': True, 'reason': 'completed'}:
        raise ValueError('Parent P0 lacks completed terminal journal')
    return {'manifest': binding(path), 'development_records': binding(dev), 'development_attempts': binding(attempts), 'development_journal': binding(dev_journal), 'baseline_id': data['configuration_id']}


def prepare(args):
    model, effort, variant = args.model, args.effort, args.variant
    if model not in ROSTER or effort not in ROSTER[model] or variant not in ('P0', 'P1', 'P2'):
        raise ValueError('Outside approved roster/variant')
    if args.timeout <= 0 or args.timeout > 1800:
        raise ValueError('Invalid bounded timeout')
    output = inside(args.output_dir)
    if output.exists():
        raise FileExistsError('Preparation directory must be new')
    if not args.configuration_id or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-' for c in args.configuration_id):
        raise ValueError('Invalid configuration ID')
    parent = check_parent(args.parent_p0, model, effort) if variant != 'P0' else None
    if variant == 'P0' and args.parent_p0:
        raise ValueError('P0 cannot inherit a baseline')
    cat = PREP / 'catalog.json'
    ep = PREP / (model.split('/')[1] + '-endpoints.json')
    catalog = json.loads(cat.read_text())
    endpoints = json.loads(ep.read_text())
    _, endpoint = check_catalog(model, effort, catalog, endpoints)
    requests = prepared_requests(model, effort, variant, parent['baseline_id'] if parent else args.configuration_id, endpoint)
    sources = {name: binding(ROOT / file) for name, file in {
        'inputs': 'data/pilot/inputs.jsonl', 'policy': 'docs/LABELING_GUIDE.md',
        'schema': 'schemas/judgments.schema.json',
        'controller': 'scripts/gemini_openrouter_batch_v1.py',
        'batch_prompt': 'scripts/codex_batch_benchmark.py',
        'frozen_variants': 'scripts/frozen_prompt_variants.py',
        'variant_manifest': 'prompts/variants-v1/manifest.json',
        'P1_text': 'prompts/variants-v1/P1-classifier.txt',
        'P2_text': 'prompts/variants-v1/P2-classifier-sop.txt',
    }.items()}
    output.mkdir(parents=True)
    manifest = {'schema': 'gemini-openrouter-batch-v1', 'configuration_id': args.configuration_id,
                'model': model, 'effort': effort, 'variant': variant, 'provider': PROVIDER,
                'parent_p0': parent, 'source_bindings': sources,
                'catalog': binding(cat), 'endpoints': binding(ep),
                'max_output_tokens': MAX_OUTPUT, 'input_allowance_tokens': ALLOWANCE_TOKENS,
                'timeout_seconds': args.timeout,
                'requests': requests, 'reference_labels_read': False,
                'no_automatic_retry': True, 'workflow': 'OpenRouter hosted batch10; smoke3 then development60',
                'source_urls': ['https://openrouter.ai/api/v1/models',
                                'https://openrouter.ai/docs/api/api-reference/endpoints/list-endpoints',
                                'https://openrouter.ai/docs/guides/features/plugins/overview']}
    path = output / 'manifest.json'
    with path.open('x') as f:
        f.write(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
        f.flush(); os.fsync(f.fileno())
    print(json.dumps({'manifest': str(path), 'sha256': sha(path.read_bytes()),
                      'per_request_reserve_usd': [r['reserve_usd'] for r in requests]}))


def approval(path, manifest_sha, phase, partition_sha, partition_id, smoke_sha=None):
    data = json.loads(inside(path).read_text())
    expected = {'schema': 'gemini-openrouter-run-approval-v1', 'approved': True,
                'manifest_sha256': manifest_sha, 'phase': phase,
                'budget_manifest_sha256': partition_sha, 'partition_id': partition_id}
    if smoke_sha:
        expected['smoke_inspection_sha256'] = smoke_sha
    if data != expected:
        raise ValueError('Exact run approval missing or mismatched')


def run(args):
    path = inside(args.manifest)
    manifest_bytes = path.read_bytes()
    digest_sha = sha(manifest_bytes)
    if digest_sha != args.manifest_sha256:
        raise ValueError('Manifest hash mismatch')
    m = json.loads(manifest_bytes)
    if m.get('schema') != 'gemini-openrouter-batch-v1' or m.get('model') not in ROSTER or m.get('variant') not in ('P0', 'P1', 'P2'):
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
    phase = args.phase
    if phase not in ('smoke', 'development'):
        raise ValueError('Unknown phase')
    output_dir = path.parent
    outfile = output_dir / (phase + '-records.jsonl')
    attemptsfile = output_dir / (phase + '-attempts.jsonl')
    journalfile = output_dir / (phase + '-journal.jsonl')
    if any(p.exists() for p in (outfile, attemptsfile, journalfile)):
        raise FileExistsError('Exclusive phase outputs already exist')
    budget_manifest = inside(args.budget_manifest)
    budget_sha = sha(budget_manifest.read_bytes())
    smoke_sha = None
    if phase == 'development':
        inspection = inside(args.smoke_inspection)
        inspect = json.loads(inspection.read_text())
        smoke_path = output_dir / 'smoke-attempts.jsonl'
        smoke_records = output_dir / 'smoke-records.jsonl'
        smoke_journal = output_dir / 'smoke-journal.jsonl'
        if inspect != {'schema': 'gemini-openrouter-smoke-inspection-v1', 'approved': True,
                       'manifest_sha256': digest_sha, 'smoke_attempts_sha256': sha(smoke_path.read_bytes()),
                       'smoke_records_sha256': sha(smoke_records.read_bytes()),
                       'smoke_journal_sha256': sha(smoke_journal.read_bytes())}:
            raise ValueError('Smoke inspection does not bind completed observed smoke')
        rows = [json.loads(x) for x in smoke_records.read_text().splitlines() if x.strip()]
        if [r.get('id') for r in rows] != ['DEV-001', 'DEV-002', 'DEV-003'] or any(r.get('status') not in ('ok', 'invalid_output') for r in rows):
            raise ValueError('Smoke record count/order/status mismatch')
        smoke_attempts = [json.loads(x) for x in smoke_path.read_text().splitlines() if x.strip()]
        if len(smoke_attempts) != 1 or smoke_attempts[0].get('cost_unknown') or smoke_attempts[0].get('billing_ok') is not True or smoke_attempts[0].get('status') not in ('ok', 'invalid_output'):
            raise ValueError('Smoke attempt lacks known safe billing and inspected outcome')
        journal_rows = [json.loads(x) for x in smoke_journal.read_text().splitlines() if x.strip()]
        if not journal_rows or journal_rows[-1] != {'event': 'terminal', 'phase': 'smoke', 'expected_batches': 1, 'started_batches': 1, 'finished_batches': 1, 'completed': True, 'reason': 'completed'}:
            raise ValueError('Smoke lacks completed terminal journal')
        smoke_sha = sha(inspection.read_bytes())
    elif args.smoke_inspection:
        raise ValueError('Smoke phase must not carry inspection')
    approval(args.approval, digest_sha, phase, budget_sha, args.partition_id, smoke_sha)
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
                                lookup = fetch('/generation?id=' + quote(generation_id, safe=''), key,
                                               timeout=min(m['timeout_seconds'], 30))
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
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    a = sub.add_parser('prepare', help='Offline only; freeze exact input-only requests')
    a.add_argument('--model', required=True, choices=sorted(ROSTER))
    a.add_argument('--effort', required=True, choices=['low', 'medium', 'high'])
    a.add_argument('--variant', required=True, choices=['P0', 'P1', 'P2'])
    a.add_argument('--configuration-id', required=True)
    a.add_argument('--parent-p0')
    a.add_argument('--timeout', type=float, default=300)
    a.add_argument('--output-dir', required=True)
    b = sub.add_parser('run', help='Paid; requires exact reviewed approval and v2 ledger partition')
    b.add_argument('--manifest', required=True)
    b.add_argument('--manifest-sha256', required=True)
    b.add_argument('--phase', required=True, choices=['smoke', 'development'])
    b.add_argument('--budget-manifest', required=True)
    b.add_argument('--partition-id', required=True)
    b.add_argument('--approval', required=True)
    b.add_argument('--smoke-inspection')
    b.add_argument('--env-file')
    args = p.parse_args()
    if args.command == 'prepare': prepare(args)
    else: run(args)


if __name__ == '__main__':
    main()
