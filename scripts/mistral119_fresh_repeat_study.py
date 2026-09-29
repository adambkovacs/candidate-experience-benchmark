#!/usr/bin/env python3
"""Offline input-only matched-three plans for Mistral Small 4 none and high.

No provider, key, or budget operation is available from this module. The old
DEV-001 HTTP 429 smokes remain historical failures, never fresh pass members.
"""
import argparse
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path

from development_benchmark import ROOT, digest, read_rows
import frozen_prompt_variants as variants
import openrouter_paid_benchmark as paid

SERIES = 'mistral119-fresh-matched3-v1'
BASE = ROOT / 'results/repeatability-v1' / SERIES
MODEL = 'mistralai/mistral-small-2603'
PROVIDER = 'mistral/zdr'
PROVIDER_NAME = 'Mistral'
QUANTIZATION = 'unknown'
INPUT_PRICE = Decimal('0.15')
OUTPUT_PRICE = Decimal('0.60')
CONTEXT = 262144
MAX_TOKENS = 4096
TIMEOUT = 300
RESERVE = Decimal('0.04177920')
INPUTS = 'data/pilot/inputs.jsonl'
SCHEMA = 'schemas/judgments.schema.json'
ROUTE_AUDIT = 'results/mistral119-recovery-prep-v2/endpoint-audit.json'
REGISTRY = 'results/openrouter-paid-run-registry.json'
ORDERS = {
    'fresh1': ['P0', 'P1', 'P2'],
    'fresh2': ['P1', 'P2', 'P0'],
    'fresh3': ['P2', 'P0', 'P1'],
}
CONDITIONS = ('P0', 'P1', 'P2')
CONFIGS = {
    'openrouter-paid-mistral-small4-119b-none': {
        'effort': 'none',
        'historical_smokes': (
            'results/openrouter-partition-mistral119-none-2026-09-23/smoke.jsonl',
            'results/openrouter-mistral119-none-recovery-2026-09-23/smoke.jsonl',
            'results/openrouter-mistral119-none-cooldown-2026-09-24/smoke.jsonl',
            'results/mistral119-recovery-prep-v1/none-smoke.jsonl',
            'results/mistral119-recovery-prep-v2/none-smoke.jsonl',
        ),
    },
    'openrouter-paid-mistral-small4-119b-high': {
        'effort': 'high',
        'historical_smokes': (
            'results/openrouter-partition-mistral119-high-2026-09-23/smoke.jsonl',
            'results/mistral119-recovery-prep-v1/high-smoke.jsonl',
            'results/mistral119-recovery-prep-v2/high-smoke.jsonl',
        ),
    },
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind(relative):
    path = (ROOT / relative).resolve()
    path.relative_to(ROOT.resolve())
    return {'path': relative, 'sha256': sha(path)}


def jsonl(relative):
    return [json.loads(line) for line in (ROOT / relative).read_text().splitlines() if line.strip()]


def input_rows():
    rows = read_rows(ROOT / INPUTS)
    if (len(rows) != 60 or
            [row.get('id') for row in rows] != [f'DEV-{i:03}' for i in range(1, 61)] or
            any(set(row) != {'id', 'feedback'} or not isinstance(row['feedback'], str) for row in rows)):
        raise ValueError('Input roster is not the exact 60 feedback-only records')
    return rows


def historical(config):
    if config not in CONFIGS:
        raise ValueError('Unsupported exact Mistral119 configuration')
    spec = CONFIGS[config]
    rows = []
    for source in spec['historical_smokes']:
        attempts = jsonl(source)
        if len(attempts) != 1:
            raise ValueError('Historical smoke must retain one failed DEV-001 attempt')
        row = attempts[0]
        if (row.get('id'), row.get('status'), row.get('http_status'),
                row.get('requested_model'), row.get('reasoning_effort'),
                row.get('observed_cost_usd'), Decimal(str(row.get('reserved_cost_usd')))) != (
                'DEV-001', 'service_error', 429, MODEL, spec['effort'], None, RESERVE) or \
                row.get('reference_labels_read') is not False or row.get('cost_unknown') is not True:
            raise ValueError('Historical smoke failure or unknown bound differs: ' + source)
        request = row.get('request')
        if not isinstance(request, dict) or row.get('request_sha256') != digest(json.dumps(request, sort_keys=True)):
            raise ValueError('Historical request digest differs: ' + source)
        rows.append(row)
    original = rows[0]
    original_request = original['request']
    if any(row['request'] != original_request for row in rows[1:]):
        raise ValueError('Historical recovery changed the exact DEV-001 request')
    endpoint = original.get('provider_endpoint') or {}
    pricing = endpoint.get('pricing') or {}
    if (original.get('quantization'), endpoint.get('tag'), endpoint.get('provider_name'),
            endpoint.get('model_id'), endpoint.get('quantization'), endpoint.get('context_length'),
            endpoint.get('status')) != (QUANTIZATION, PROVIDER, PROVIDER_NAME,
                                       MODEL, QUANTIZATION, CONTEXT, 0):
        raise ValueError('Original endpoint identity differs')
    if (Decimal(str(pricing.get('prompt'))), Decimal(str(pricing.get('completion')))) != (
            INPUT_PRICE / Decimal(1_000_000), OUTPUT_PRICE / Decimal(1_000_000)):
        raise ValueError('Original endpoint pricing differs')
    model_info = original.get('model_catalog_entry')
    if not isinstance(model_info, dict) or model_info.get('id') != MODEL:
        raise ValueError('Original model catalog identity differs')
    if paid.reasoning(model_info, endpoint, spec['effort']) != original_request.get('reasoning'):
        raise ValueError('Original reasoning control differs')
    if paid.reservation(endpoint, MAX_TOKENS, INPUT_PRICE, OUTPUT_PRICE) != RESERVE:
        raise ValueError('Original full-context reserve differs')
    registry = json.loads((ROOT / REGISTRY).read_text())
    matches = [row for row in registry if row.get('id') == config]
    if (len(matches) != 1 or matches[0].get('model') != MODEL or
            matches[0].get('provider') != PROVIDER or matches[0].get('effort') != spec['effort'] or
            matches[0].get('status') != 'smoke_upstream_rate_limit'):
        raise ValueError('Historical registry identity or failure status differs')
    return original, len(rows)


def controls(original, effort, first_feedback):
    request = original['request']
    expected_provider = {
        'only': [PROVIDER], 'allow_fallbacks': False, 'require_parameters': True,
        'max_price': {'prompt': float(INPUT_PRICE), 'completion': float(OUTPUT_PRICE),
                      'request': 0, 'image': 0},
    }
    if set(request) != {'model', 'temperature', 'max_tokens', 'stream', 'provider',
                        'response_format', 'reasoning', 'messages'}:
        raise ValueError('Original request field set differs')
    if (request['model'], request['temperature'], request['max_tokens'], request['stream'],
            request['provider'], request['reasoning']) != (
            MODEL, 0, MAX_TOKENS, False, expected_provider,
            {'enabled': False, 'effort': 'none'} if effort == 'none' else
            {'enabled': True, 'effort': 'high'}):
        raise ValueError('Original request controls differ')
    fmt = request['response_format']
    schema = json.loads((ROOT / SCHEMA).read_text())
    if (fmt.get('type') != 'json_schema' or fmt.get('json_schema', {}).get('strict') is not True or
            fmt['json_schema'].get('schema') != schema):
        raise ValueError('Original strict output schema differs')
    messages = request['messages']
    if (not isinstance(messages, list) or len(messages) != 2 or
            messages[0].get('role') != 'system' or not isinstance(messages[0].get('content'), str) or
            messages[1] != {'role': 'user', 'content': json.dumps({'feedback': first_feedback})}):
        raise ValueError('Original prompt or DEV-001 feedback differs')
    instruction = messages[0]['content']
    if instruction != paid.baseline_instruction() or digest(instruction) != original.get('policy_sha256'):
        raise ValueError('Original baseline instruction differs from source policy')
    if original.get('schema_sha256') != digest(json.dumps(schema, sort_keys=True)):
        raise ValueError('Original schema hash differs')
    if original.get('input_sha256') != digest(first_feedback):
        raise ValueError('Original DEV-001 input hash differs')
    return instruction, schema


def estimate(historical_count):
    calls = 3 * 3 * (3 + 60)
    return {
        'historical_failed_smoke_attempts': historical_count,
        'historical_known_cost_proxy_usd': None,
        'historical_unknown_charge_bound_per_attempt_usd': str(RESERVE),
        'maximum_per_request_reserve_usd': str(RESERVE),
        'three_smoke_reservations_usd': str(RESERVE * 3),
        'calls_per_full_series': calls,
        'all_calls_at_maximum_reserve_usd': str(RESERVE * calls),
        'whole_series_child_cap_proposed_usd': None,
        'uncertainty': 'No successful historical Mistral119 response supplies token or charge usage. The all-call full-context amount is a stress bound, not a forecast or funded cap.',
    }


def plan_data(config, fresh_pass):
    if fresh_pass not in ORDERS:
        raise ValueError('Unknown fresh pass')
    original, count = historical(config)
    inputs = input_rows()
    effort = CONFIGS[config]['effort']
    baseline, schema = controls(original, effort, inputs[0]['feedback'])
    endpoint = original['provider_endpoint']
    model_info = original['model_catalog_entry']
    conditions = {}
    for condition in CONDITIONS:
        composed = variants.compose_instruction(baseline, condition, role='system',
                                                parent_baseline_id=config, root=ROOT)
        instruction = composed['instruction']
        requests = []
        for position, item in enumerate(inputs, 1):
            payload = paid.make_payload(MODEL, endpoint, item['feedback'], instruction,
                                        schema, effort, MAX_TOKENS, INPUT_PRICE,
                                        OUTPUT_PRICE, model_info)
            if condition == 'P0' and position == 1 and payload != original['request']:
                raise ValueError('Rebuilt P0 DEV-001 request differs from historical bytes')
            requests.append({
                'position': position, 'record_id': item['id'], 'payload': payload,
                'request_sha256': digest(json.dumps(payload, sort_keys=True)),
                'input_sha256': digest(item['feedback']),
                'instruction_sha256': digest(instruction),
            })
        conditions[condition] = {'instruction': composed['audit'],
                                 'smoke': requests[:3], 'development': requests}
    source_paths = [INPUTS, SCHEMA, ROUTE_AUDIT, REGISTRY,
                    'prompts/variants-v1/manifest.json',
                    'prompts/variants-v1/P1-classifier.txt',
                    'prompts/variants-v1/P2-classifier-sop.txt',
                    'docs/LABELING_GUIDE.md', 'docs/REPEATABILITY_PLAN.md',
                    'scripts/mistral119_fresh_repeat_study.py',
                    'tests/test_mistral119_fresh_repeat_study.py',
                    'scripts/development_benchmark.py',
                    'scripts/frozen_prompt_variants.py',
                    'scripts/openrouter_paid_benchmark.py',
                    'scripts/openrouter_benchmark.py',
                    'scripts/openrouter_budget_v2.py']
    source_paths.extend(CONFIGS[config]['historical_smokes'])
    return {
        'schema': 'hosted-fresh-matched-three-plan-v1', 'series_id': SERIES,
        'configuration_id': config, 'fresh_pass': fresh_pass,
        'condition_order': ORDERS[fresh_pass], 'model': MODEL,
        'provider_tag': PROVIDER, 'provider_name': PROVIDER_NAME,
        'quantization': QUANTIZATION, 'reasoning_effort': effort,
        'temperature': 0, 'max_tokens': MAX_TOKENS, 'stream': False,
        'context_reservation_tokens': CONTEXT, 'timeout_seconds': TIMEOUT,
        'workflow': 'single_record_fresh_context',
        'continue_on_invalid_output': False,
        'retry_policy': 'No retries or replays; retain every failed or unknown outcome.',
        'seed_policy': 'No explicit seed in original request; requested and effective seed unavailable.',
        'reference_labels_read': False,
        'smoke_count_per_condition': 3, 'development_count_per_condition': 60,
        'historical_status': 'Only failed DEV-001 smokes; zero model outputs. No old attempt is a fresh pass.',
        'historical_failed_smoke_sources': [bind(path) for path in CONFIGS[config]['historical_smokes']],
        'execution_status': 'offline_prepared_no_inference_no_allocation',
        'budget_estimate': estimate(count), 'conditions': conditions,
        'source_bindings': [bind(path) for path in dict.fromkeys(source_paths)],
        'dispatch_gate': 'Independent controller review, live exact route and serving-capacity check, funded child, and stage receipts required. Inspect three smoke outcomes before each development phase; stop before an unfunded call.',
    }


def prepare():
    for config in CONFIGS:
        for fresh_pass in ORDERS:
            folder = BASE / config / fresh_pass
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / 'manifest.json'
            with target.open('x') as stream:
                json.dump(plan_data(config, fresh_pass), stream, indent=2, ensure_ascii=False)
                stream.write('\n')
                stream.flush()
                os.fsync(stream.fileno())
            print(config, fresh_pass, sha(target))


def verify(config, fresh_pass, expected_sha):
    target = BASE / config / fresh_pass / 'manifest.json'
    if sha(target) != expected_sha:
        raise ValueError('Manifest SHA-256 mismatch')
    manifest = json.loads(target.read_text())
    for binding in manifest['source_bindings']:
        if bind(binding['path']) != binding:
            raise ValueError('Bound source changed: ' + binding['path'])
    if manifest != plan_data(config, fresh_pass):
        raise ValueError('Frozen plan differs from source reconstruction')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('prepare')
    check = sub.add_parser('verify')
    check.add_argument('--configuration-id', choices=tuple(CONFIGS), required=True)
    check.add_argument('--fresh-pass', choices=tuple(ORDERS), required=True)
    check.add_argument('--manifest-sha256', required=True)
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare()
    else:
        verify(args.configuration_id, args.fresh_pass, args.manifest_sha256)
        print('verified', args.configuration_id, args.fresh_pass)


if __name__ == '__main__':
    main()
