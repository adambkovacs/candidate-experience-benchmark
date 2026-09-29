#!/usr/bin/env python3
"""Offline plan for a distinct Google AI Studio free-route Gemma 26B study."""
import argparse
import copy
import json
import os
from pathlib import Path

import gemma26_on_fresh_repeat_study as historical
from development_benchmark import ROOT, digest

SERIES = 'gemma26-free-on-fresh-matched3-v1'
CONFIG = 'openrouter-free-gemma4-26b-a4b-on-google-ai-studio'
MODEL = 'google/gemma-4-26b-a4b-it:free'
PROVIDER = 'google-ai-studio'
PROVIDER_NAME = 'Google AI Studio'
BASE = ROOT / 'results/repeatability-v1' / SERIES
ORDERS = historical.ORDERS
CONTEXT = 262144
MAX_TOKENS = 4096
FREE_ENDPOINT_URL = 'https://openrouter.ai/api/v1/models/google/gemma-4-26b-a4b-it:free/endpoints'


def sha(path):
    return historical.sha(path)


def binding(relative):
    path = (ROOT / relative).resolve()
    path.relative_to(ROOT.resolve())
    return {'path': relative, 'sha256': sha(path)}


def free_request(request):
    value = copy.deepcopy(request)
    payload = value['payload']
    if payload['model'] != historical.MODEL or payload.get('reasoning') != {'enabled': True}:
        raise ValueError('Historical Gemma request controls changed')
    payload['model'] = MODEL
    payload['provider'] = {
        'only': [PROVIDER], 'allow_fallbacks': False,
        'require_parameters': True,
        'max_price': {'prompt': 0, 'completion': 0, 'request': 0, 'image': 0},
    }
    if set(payload) != {'model', 'temperature', 'max_tokens', 'stream', 'provider',
                        'response_format', 'reasoning', 'messages'}:
        raise ValueError('Unexpected request field')
    value['request_sha256'] = digest(json.dumps(payload, sort_keys=True))
    value.pop('historical_outcome_excluded', None)
    return value


def plan_data(fresh_pass):
    if fresh_pass not in ORDERS:
        raise ValueError('Unknown fresh pass')
    old_file = historical.BASE / fresh_pass / 'manifest.json'
    old_sha = sha(old_file)
    old = historical.verify(fresh_pass, old_sha)
    new_conditions = {}
    for condition in ('P0', 'P1', 'P2'):
        source = old['conditions'][condition]
        new_conditions[condition] = {
            'instruction': source['instruction'],
            'historical_attempts': source['historical_attempts'],
            'smoke': [free_request(x) for x in source['smoke']],
            'development': [free_request(x) for x in source['development']],
        }
        if [x['record_id'] for x in new_conditions[condition]['development']] != [f'DEV-{i:03}' for i in range(1, 61)]:
            raise ValueError('Ordered development membership changed')
    sources = list(old['source_bindings'])
    for relative in (
        'scripts/gemma26_free_fresh_study.py',
        'scripts/gemma26_free_fresh_execution.py',
        'tests/test_gemma26_free_fresh.py',
        'scripts/gemma26_on_fresh_repeat_study.py',
        'scripts/gemma26_on_fresh_repeat_execution.py',
        'scripts/openrouter_benchmark.py',
        'scripts/openrouter_free_quota_v1.py',
        'scripts/openrouter_paid_benchmark.py',
        'scripts/prompt_admission.py',
        'docs/GEMMA26_FREE_FRESH_ADMISSION_2026-09-29.md',
    ):
        spec = binding(relative)
        if not any(x['path'] == relative for x in sources):
            sources.append(spec)
    for repeat in ORDERS:
        relative = f'results/repeatability-v1/{historical.SERIES}/{repeat}/manifest.json'
        sources.append(binding(relative))
    return {
        'schema': 'gemma26-free-fresh-plan-v1', 'series_id': SERIES,
        'configuration_id': CONFIG, 'underlying_model': historical.MODEL,
        'historical_configuration_id': historical.CONFIG,
        'historical_deepinfra_status': 'unexecuted_0_of_9_funding_blocked_not_fulfilled_by_this_series',
        'fresh_pass': fresh_pass, 'condition_order': ORDERS[fresh_pass],
        'model': MODEL, 'provider_tag': PROVIDER, 'provider_name': PROVIDER_NAME,
        'quantization': 'unknown', 'reasoning_request': {'enabled': True},
        'effective_reasoning': None, 'context_limit': CONTEXT,
        'max_tokens': MAX_TOKENS, 'temperature': 0, 'stream': False,
        'timeout_seconds': 300, 'seed_policy': 'No explicit seed; effective seed unavailable',
        'pricing_policy': 'Explicit :free model, zero-priced model and sole selected endpoint, zero max_price for prompt/completion/request/image, no fallback; stop on any positive returned charge.',
        'quota_policy': {'published_max_rpm': 20, 'published_paid_tier_daily_requests': 1000,
                         'published_free_tier_daily_requests': 50,
                         'full_series_requests': 567,
                         'phase_requests': {'smoke': 3, 'development': 60},
                         'eligibility_gate': 'Authenticated read-only /key is_free_tier false and /credits total_credits >= 10 before every stage. Shared private ledger reserves all stage calls under 1000 known project calls per rolling 24 hours and paces 20 starts per rolling 60 seconds. Other account usage is unknown; stop on 429 without replay.'},
        'schema_support_limit': 'Endpoint advertises response_format but not structured_outputs. A three-record raw, schema-valid smoke and root inspection are required before development; unsupported response_format stops the series.',
        'endpoint_reference': FREE_ENDPOINT_URL,
        'historical_paid_manifest_sha256': old_sha,
        'conditions': new_conditions, 'source_bindings': sources,
        'reference_labels_read': False,
        'retry_policy': 'No retry or replay of any started request, including 429.',
        'continue_on_invalid_output': False,
        'execution_status': 'offline_prepared_no_provider_calls',
    }


def verify(fresh_pass, expected_sha):
    path = BASE / fresh_pass / 'manifest.json'
    if sha(path) != expected_sha:
        raise ValueError('Plan SHA differs')
    data = json.loads(path.read_text())
    for source in data['source_bindings']:
        if binding(source['path']) != source:
            raise ValueError('Bound source changed: ' + source['path'])
    if data != plan_data(fresh_pass):
        raise ValueError('Free plan reconstruction differs')
    return data


def prepare():
    for fresh_pass in ORDERS:
        folder = BASE / fresh_pass
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / 'manifest.json'
        data = json.dumps(plan_data(fresh_pass), indent=2, ensure_ascii=False) + '\n'
        with path.open('x') as out:
            out.write(data)
            out.flush(); os.fsync(out.fileno())
        print(fresh_pass, sha(path))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('prepare', 'verify'))
    parser.add_argument('--pass-name', choices=tuple(ORDERS))
    parser.add_argument('--sha256')
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare()
    elif not args.pass_name or not args.sha256:
        parser.error('verify requires --pass-name and --sha256')
    else:
        verify(args.pass_name, args.sha256)
        print('verified', args.pass_name)


if __name__ == '__main__':
    main()
