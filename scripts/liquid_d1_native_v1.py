#!/usr/bin/env python3
"""Offline Liquid d1 native Choice plans. No inference or budget mutation."""
import argparse
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path

from development_benchmark import ROOT, KEYS, VALUES, read_rows
from jev_benchmark import make_payload
from openrouter_paid_benchmark import validate_rows
import jev_native_prompt_variants_v1 as variants
import openrouter_decision_smoke as native

BASE = ROOT / 'results/liquid-d1-native-v1'
MODEL = 'liquid/d1'
VERSION = 'liquid/d1-20260930'
PROVIDER = 'Liquid'
TAG = 'liquid'
CONTEXT = 65536
RATE = Decimal('0.00000004')
QUESTION_COUNT = len(KEYS)
# Liquid bills input across questions; the listed context may apply per question.
BOUND = QUESTION_COUNT * CONTEXT * RATE
SMOKE_BOUND = 3 * BOUND
SOURCE_PATHS = ('scripts/liquid_d1_native_v1.py', 'scripts/liquid_d1_smoke_v1.py',
                'scripts/jev_benchmark.py', 'scripts/jev_native_prompt_variants_v1.py',
                'scripts/openrouter_decision_smoke.py', 'scripts/development_benchmark.py',
                'scripts/openrouter_paid_benchmark.py', 'scripts/openrouter_budget_v4.py',
                'scripts/paid_budget_partitions_v4.py', 'scripts/paid_budget_partitions_v3.py',
                'scripts/postapproval_authority_v3.py', 'scripts/postapproval_authority_v2.py',
                'scripts/openrouter_budget_amendment_v3.py', 'scripts/openrouter_budget_v3.py')
SUFFIX_SHA = '48ba1ad98ac7c085de87e1ddfb1b15f8083bb3d6a57786d708915c6d4981ccd7'


def validate_catalog(catalog):
    data = catalog.get('data') if isinstance(catalog, dict) else None
    if not isinstance(data, dict) or data.get('id') != MODEL:
        raise ValueError('Liquid model identity changed')
    architecture = data.get('architecture')
    if not isinstance(architecture, dict) or architecture.get('modality') != 'text->decisions' or architecture.get('output_modalities') != ['decisions']:
        raise ValueError('Liquid native Decisions interface changed')
    endpoints = data.get('endpoints')
    if not isinstance(endpoints, list) or len(endpoints) != 1:
        raise ValueError('Liquid endpoint count changed')
    endpoint = endpoints[0]
    expected = {'name': PROVIDER + ' | ' + VERSION, 'model_id': MODEL, 'provider_name': PROVIDER,
                'tag': TAG, 'context_length': CONTEXT, 'max_completion_tokens': 58982,
                'quantization': 'unknown', 'supported_parameters': [], 'status': 0}
    if any(endpoint.get(key) != value for key, value in expected.items()):
        raise ValueError('Liquid endpoint version/provider/context changed')
    pricing = endpoint.get('pricing')
    if not isinstance(pricing, dict) or set(pricing) != {'prompt', 'completion', 'input_cache_read', 'discount'}:
        raise ValueError('Liquid pricing dimensions changed')
    if (Decimal(str(pricing['prompt'])) != RATE or Decimal(str(pricing['input_cache_read'])) != RATE or
            Decimal(str(pricing['completion'])) != 0 or Decimal(str(pricing['discount'])) != 0):
        raise ValueError('Liquid price changed')
    return endpoint


def payload(feedback, policy, condition):
    if condition not in ('P0', 'P1', 'P2'):
        raise ValueError('Unknown condition')
    base = make_payload(feedback, policy, MODEL, 'official')
    base['provider'] = {'only': [TAG], 'allow_fallbacks': False,
                        'max_price': {'prompt': 0.04, 'completion': 0, 'request': 0, 'image': 0}}
    value = deepcopy(base)
    if condition != 'P0':
        for key in KEYS:
            value['questions'][key]['instructions'] += variants.P1
            if condition == 'P2':
                value['questions'][key]['instructions'] += variants.P2[key]
    check_payload(value, feedback, policy, condition)
    return value


def check_payload(value, feedback, policy, condition):
    base = make_payload(feedback, policy, MODEL, 'official')
    base['provider'] = {'only': [TAG], 'allow_fallbacks': False,
                        'max_price': {'prompt': 0.04, 'completion': 0, 'request': 0, 'image': 0}}
    if set(value) != set(base) or value['model'] != MODEL or value['state'] != {'feedback': feedback, 'policy': policy} or value['provider'] != base['provider'] or list(value['questions']) != list(KEYS):
        raise ValueError('Liquid request identity or input changed')
    stripped = deepcopy(value)
    for key in KEYS:
        question = value['questions'][key]
        if set(question) != {'type', 'instructions', 'criteria'} or question['type'] != 'choice' or list(question['criteria']) != list(VALUES[key]):
            raise ValueError('Liquid Choice schema changed')
        expected = base['questions'][key]['instructions']
        if condition != 'P0':
            expected += variants.P1
            if condition == 'P2':
                expected += variants.P2[key]
        if question['instructions'] != expected or question['criteria'] != base['questions'][key]['criteria']:
            raise ValueError('Liquid Choice content changed')
        stripped['questions'][key]['instructions'] = base['questions'][key]['instructions']
    if native.canonical(stripped) != native.canonical(base):
        raise ValueError('Liquid variant changed other wire fields')


def build(root=ROOT, catalog=None):
    root = Path(root)
    if catalog is None:
        catalog = json.loads((root / 'results/liquid-d1-native-v1/endpoint-public.json').read_text())
    endpoint = validate_catalog(catalog)
    sources = {name: native.sha((root / name).read_bytes()) for name in SOURCE_PATHS}
    if sources['scripts/jev_native_prompt_variants_v1.py'] != SUFFIX_SHA:
        raise ValueError('Frozen native suffix changed')
    rows = validate_rows(read_rows(root / 'data/pilot/inputs.jsonl'))
    if len(rows) != 60 or [r['id'] for r in rows] != [f'DEV-{i:03}' for i in range(1, 61)] or any(set(r) != {'id', 'feedback'} for r in rows):
        raise ValueError('Require exactly 60 input-only development records')
    policy_raw = (root / 'docs/LABELING_GUIDE.md').read_text()
    if policy_raw.count('## Simulated routing') != 1:
        raise ValueError('Frozen policy cutoff changed')
    policy = policy_raw.split('## Simulated routing')[0]
    if not policy:
        raise ValueError('Empty policy')
    phases = []
    for fresh in (1, 2, 3):
        for condition in ('P0', 'P1', 'P2'):
            requests = []
            for row in rows:
                value = payload(row['feedback'], policy, condition)
                requests.append({'id': row['id'], 'feedback_sha256': native.sha(row['feedback'].encode()),
                                 'payload_sha256': native.sha(native.canonical(value)), 'payload': value})
            phases.append({'id': f'fresh{fresh}/{condition}', 'status': 'planned_not_admitted',
                           'request_count': 60, 'requests_sha256': native.sha(native.canonical(requests)),
                           'requests': requests})
    return {'kind': 'liquid-d1-openrouter-native-plan-v1', 'status': 'prepared_not_admitted',
            'inference_performed': False, 'reference_labels_read': False,
            'model': MODEL, 'expected_returned_model': VERSION, 'provider': PROVIDER, 'provider_tag': TAG,
            'api_url': native.DECISIONS_URL, 'interface': 'native Decisions, four Choice questions',
            'conditions': ['P0', 'P1', 'P2'], 'fresh_passes': [1, 2, 3],
            'question_order': list(KEYS), 'source_sha256': sources,
            'input_file_sha256': native.sha((root / 'data/pilot/inputs.jsonl').read_bytes()),
            'policy_sha256': native.sha(policy.encode()), 'suffix_sha256': SUFFIX_SHA,
            'endpoint_sha256': native.sha(native.canonical(catalog)), 'endpoint': endpoint,
            'pricing': {'prompt_usd_per_token': str(RATE), 'input_cache_read_usd_per_token': str(RATE),
                        'completion_usd_per_token': '0', 'discount': '0'},
            'context_tokens_per_question': CONTEXT, 'question_count': QUESTION_COUNT,
            'max_aggregate_billable_input_tokens': QUESTION_COUNT * CONTEXT,
            'full_context_bound_per_request_usd': str(BOUND),
            'three_record_smoke_bound_usd': str(SMOKE_BOUND),
            'sixty_record_phase_bound_usd': str(60 * BOUND),
            'all_nine_phase_bound_usd': str(9 * 60 * BOUND),
            'smoke_phase': 'fresh1/P0', 'smoke_ids': [r['id'] for r in rows[:3]],
            'provider_tokenizer': 'Other; no public exact tokenizer supplied',
            'context_proof': 'No all-record proof; live usage must be inspected after smoke',
            'phases': phases}


def verify(base=BASE, root=ROOT):
    base = Path(base)
    expected = build(root)
    if json.loads((base / 'plan.json').read_text()) != expected:
        raise ValueError('Liquid plan/source/catalog drift')
    return expected, native.sha(native.canonical(expected))


def prepare(base=BASE, root=ROOT):
    base = Path(base)
    value = build(root)
    if (base / 'plan.json').exists():
        raise FileExistsError('Liquid plan already exists')
    base.mkdir(parents=True, exist_ok=True)
    with (base / 'plan.json').open('x') as out:
        out.write(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return native.sha(native.canonical(value))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('prepare', 'verify'))
    args = parser.parse_args()
    print(prepare() if args.operation == 'prepare' else verify()[1])


if __name__ == '__main__':
    main()
