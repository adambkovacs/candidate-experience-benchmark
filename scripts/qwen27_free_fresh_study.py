#!/usr/bin/env python3
"""Offline, distinct free-route Qwen27 medium and xhigh plans."""
import argparse
import copy
import json
import os

import qwen27_fresh_repeat_study as paid_study
from development_benchmark import ROOT, digest

SERIES = 'qwen27-free-fresh-matched3-v1'
BASE = ROOT / 'results/repeatability-v1' / SERIES
MODEL = 'qwen/qwen3.8-27b:free'
PROVIDER = 'modelrun/fp4'
PROVIDER_NAME = 'ModelRun'
CONTEXT = 262144
MAX_TOKENS = 4096
ORDERS = paid_study.ORDERS
CONFIGS = {
    'openrouter-free-qwen3.8-27b-medium-modelrun': ('openrouter-paid-qwen3.8-27b-medium', 'medium'),
    'openrouter-free-qwen3.8-27b-xhigh-modelrun': ('openrouter-paid-qwen3.8-27b-xhigh', 'xhigh'),
}
PAID_MANIFEST_SHA256 = {
    'openrouter-paid-qwen3.8-27b-medium': {
        'fresh1': '6824a780ddfe33a34fb547fa27c9426ce518150f1145617b436ab66acef796f0',
        'fresh2': '692f42760d5843860563e01d86c3b3fec849b31254e1761fea0ad177f01e701b',
        'fresh3': 'd5953fdcf75aac340ebc841c9a018976f7f0234bb0b3ee4015cbf9904b11c35a',
    },
    'openrouter-paid-qwen3.8-27b-xhigh': {
        'fresh1': 'aec48d2734c47016e4a5bc906cbedc839b3bf9a727ed966b98528d857ecf013b',
        'fresh2': 'd053f7da53652737c39d6a0c5d98cbfa1ebbde03a64e84f6ac43df27c54142ca',
        'fresh3': '80e21da94f6cd71ecc32317c35a026985be93a1812cbcad13bc90ac301c03f18',
    },
}


def sha(path):
    return paid_study.sha(path)


def bind(relative):
    return paid_study.bind(relative)


def convert(request, effort):
    value = copy.deepcopy(request)
    payload = value['payload']
    if (payload.get('model') != paid_study.MODEL or
            payload.get('reasoning') != {'enabled': True, 'effort': effort}):
        raise ValueError('Historical Qwen request controls changed')
    payload['model'] = MODEL
    payload['provider'] = {
        'only': [PROVIDER], 'allow_fallbacks': False, 'require_parameters': True,
        'max_price': {'prompt': 0, 'completion': 0, 'request': 0, 'image': 0},
    }
    if set(payload) != {'model', 'temperature', 'max_tokens', 'stream', 'provider',
                        'response_format', 'reasoning', 'messages'}:
        raise ValueError('Unexpected Qwen request field')
    value['request_sha256'] = digest(json.dumps(payload, sort_keys=True))
    value.pop('historical_outcome_excluded', None)
    return value


def source_plan(paid_config, effort, fresh_pass):
    old_path = paid_study.BASE / paid_config / fresh_pass / 'manifest.json'
    if sha(old_path) != PAID_MANIFEST_SHA256[paid_config][fresh_pass]:
        raise ValueError('Pinned paid input-only manifest changed')
    old = json.loads(old_path.read_text())
    if (old.get('configuration_id'), old.get('fresh_pass'), old.get('condition_order'),
            old.get('model'), old.get('provider_tag'), old.get('reasoning_effort')) != (
            paid_config, fresh_pass, ORDERS[fresh_pass], paid_study.MODEL,
            paid_study.PROVIDER, effort):
        raise ValueError('Pinned paid plan identity changed')
    feedback = paid_study.input_feedback()
    schema = json.loads((ROOT / 'schemas/judgments.schema.json').read_text())
    for condition in ('P0', 'P1', 'P2'):
        group = old['conditions'][condition]
        prompt_spec = group['instruction']
        if bind(prompt_spec['path']) != prompt_spec:
            raise ValueError('Prompt source binding differs')
        instruction = (ROOT / prompt_spec['path']).read_text()
        requests = group['development']
        if len(requests) != 60 or group['smoke'] != requests[:3]:
            raise ValueError('Pinned paid smoke/development membership differs')
        for position, row in enumerate(requests, 1):
            rid = f'DEV-{position:03}'
            payload = row['payload']
            if (row.get('record_id'), row.get('position'), row.get('input_sha256'),
                    row.get('instruction_sha256'), row.get('request_sha256')) != (
                    rid, position, digest(feedback[rid]), digest(instruction),
                    digest(json.dumps(payload, sort_keys=True))):
                raise ValueError('Pinned paid request hash, input, or order differs')
            if payload.get('messages') != [
                    {'role': 'system', 'content': instruction},
                    {'role': 'user', 'content': json.dumps({'feedback': feedback[rid]})}]:
                raise ValueError('Pinned paid prompt or input differs')
            if (payload.get('model'), payload.get('temperature'), payload.get('max_tokens'),
                    payload.get('stream'), payload.get('reasoning')) != (
                    paid_study.MODEL, 0, MAX_TOKENS, False,
                    {'enabled': True, 'effort': effort}):
                raise ValueError('Pinned paid inference controls differ')
            if payload.get('provider') != {
                    'only': [paid_study.PROVIDER], 'allow_fallbacks': False,
                    'require_parameters': True,
                    'max_price': {'prompt': float(paid_study.INPUT_PRICE),
                                  'completion': float(paid_study.OUTPUT_PRICE),
                                  'request': 0, 'image': 0}}:
                raise ValueError('Pinned paid route control differs')
            if payload.get('response_format') != {
                    'type': 'json_schema', 'json_schema':
                    {'name': 'judgments', 'strict': True, 'schema': schema}}:
                raise ValueError('Pinned paid strict schema differs')
    return old, old_path


def plan_data(config, fresh_pass):
    if config not in CONFIGS or fresh_pass not in ORDERS:
        raise ValueError('Unsupported free Qwen configuration or pass')
    paid_config, effort = CONFIGS[config]
    old, old_path = source_plan(paid_config, effort, fresh_pass)
    old_hash = sha(old_path)
    conditions = {}
    for condition in ('P0', 'P1', 'P2'):
        source = old['conditions'][condition]
        conditions[condition] = {
            'instruction': source['instruction'],
            'smoke': [convert(x, effort) for x in source['smoke']],
            'development': [convert(x, effort) for x in source['development']],
        }
        if [x['record_id'] for x in conditions[condition]['development']] != [f'DEV-{i:03}' for i in range(1, 61)]:
            raise ValueError('Ordered 60-record membership changed')
    sources = []
    for relative in (
        'scripts/qwen27_fresh_repeat_study.py',
        'scripts/qwen27_free_fresh_study.py',
        'scripts/qwen27_free_fresh_execution.py',
        'tests/test_qwen27_free_fresh.py',
        'docs/QWEN27_FREE_FRESH_ADMISSION_2026-09-29.md',
        'scripts/gemma26_free_fresh_execution.py',
        'scripts/gemma26_free_fresh_study.py',
        'scripts/gemma26_on_fresh_repeat_execution.py',
        'scripts/openrouter_free_quota_v1.py',
        'scripts/openrouter_benchmark.py',
        'scripts/openrouter_paid_benchmark.py',
        'scripts/prompt_admission.py',
        'data/pilot/inputs.jsonl',
        'schemas/judgments.schema.json',
    ):
        spec = bind(relative)
        if not any(x['path'] == relative for x in sources):
            sources.append(spec)
    for source_pass in ORDERS:
        relative = f'results/repeatability-v1/{paid_study.SERIES}/{paid_config}/{source_pass}/manifest.json'
        sources.append(bind(relative))
    for condition in ('P0', 'P1', 'P2'):
        spec = conditions[condition]['instruction']
        if not any(x['path'] == spec['path'] for x in sources):
            sources.append(spec)
    return {
        'schema': 'qwen27-free-fresh-plan-v1', 'series_id': SERIES,
        'configuration_id': config, 'historical_paid_configuration_id': paid_config,
        'historical_paid_status': 'separate_unfunded_0_of_9_not_fulfilled_by_this_series',
        'fresh_pass': fresh_pass, 'condition_order': ORDERS[fresh_pass],
        'model': MODEL, 'provider_tag': PROVIDER, 'provider_name': PROVIDER_NAME,
        'quantization': 'fp4', 'reasoning_effort': effort,
        'context_limit': CONTEXT, 'max_tokens': MAX_TOKENS,
        'temperature': 0, 'stream': False, 'timeout_seconds': 300,
        'seed_policy': 'No explicit seed; effective seed unavailable',
        'pricing_policy': 'Explicit :free variant and ModelRun-only no-fallback route; zero model and endpoint prices, zero max_price for prompt/completion/request/image; stop on any positive returned charge.',
        'quota_policy': 'Shared private cross-configuration ledger: reserve whole stages against provider daily remaining and 1000 rolling project calls per 24 hours, pace at most 20 starts per rolling 60 seconds. Other account activity may change remaining capacity.',
        'schema_support': 'Endpoint advertises structured_outputs, reasoning, and reasoning_effort. Three schema-valid raw smoke responses still require inspection before development.',
        'paid_manifest_sha256': old_hash,
        'conditions': conditions, 'source_bindings': sources,
        'reference_labels_read': False,
        'retry_policy': 'No retry or replay of a started request, including provider 429.',
        'continue_on_invalid_output': False,
        'execution_status': 'offline_prepared_no_provider_calls',
    }


def verify(config, fresh_pass, expected_sha):
    path = BASE / config / fresh_pass / 'manifest.json'
    if sha(path) != expected_sha:
        raise ValueError('Free Qwen plan SHA differs')
    data = json.loads(path.read_text())
    for source in data['source_bindings']:
        if bind(source['path']) != source:
            raise ValueError('Bound source changed: ' + source['path'])
    if data != plan_data(config, fresh_pass):
        raise ValueError('Free Qwen plan reconstruction differs')
    return data


def prepare():
    for config in CONFIGS:
        for fresh_pass in ORDERS:
            folder = BASE / config / fresh_pass
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / 'manifest.json'
            with path.open('x') as out:
                out.write(json.dumps(plan_data(config, fresh_pass), indent=2, ensure_ascii=False) + '\n')
                out.flush(); os.fsync(out.fileno())
            print(config, fresh_pass, sha(path))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('prepare', 'verify'))
    parser.add_argument('--configuration-id', choices=tuple(CONFIGS))
    parser.add_argument('--fresh-pass', choices=tuple(ORDERS))
    parser.add_argument('--sha256')
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare()
    elif not args.configuration_id or not args.fresh_pass or not args.sha256:
        parser.error('verify requires --configuration-id, --fresh-pass, and --sha256')
    else:
        verify(args.configuration_id, args.fresh_pass, args.sha256)
        print('verified', args.configuration_id, args.fresh_pass)


if __name__ == '__main__':
    main()
