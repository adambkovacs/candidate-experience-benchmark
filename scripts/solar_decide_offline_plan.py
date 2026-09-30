#!/usr/bin/env python3
"""Offline native Choice plans for both saved OpenRouter Solar Decide endpoints.

No request, credential, reservation, receipt, or live admission path exists here.
The 30 September catalog is dated source evidence, not current availability.
"""
import argparse
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path

from development_benchmark import ROOT, KEYS, VALUES, read_rows
from jev_benchmark import make_payload
from openrouter_paid_benchmark import validate_rows
import jev_native_prompt_variants_v1 as variants
import openrouter_decision_smoke as smoke

MODEL = 'upstage/solar-decide'
VERSION = 'upstage/solar-decide-20260928'
PROVIDER = 'Upstage'
TAGS = ('upstage', 'upstage/zdr')
CONTEXT = 524288
PROMPT_RATE = Decimal('0.00000005')
OUTPUT_RATE = Decimal('0')
CACHE_RATE = Decimal('0.00000005')
DISCOUNT = Decimal('0.5')
SNAPSHOT = Path('results/route-audits/solar-openrouter-endpoint-20260930.json')
AUDIT = Path('docs/DECISION_MODEL_ROUTE_AUDIT_2026-09-30.md')
SUFFIX_SHA = '48ba1ad98ac7c085de87e1ddfb1b15f8083bb3d6a57786d708915c6d4981ccd7'
SOURCE_PATHS = (
    'scripts/solar_decide_offline_plan.py',
    'scripts/jev_native_prompt_variants_v1.py',
    'scripts/jev_benchmark.py',
    'scripts/openrouter_decision_smoke.py',
    'scripts/openrouter_budget_v2.py',
    'scripts/openrouter_paid_benchmark.py',
    'scripts/development_benchmark.py',
)


def source_hashes(root):
    return {name: smoke.sha((root / name).read_bytes()) for name in SOURCE_PATHS}


def validate_catalog(catalog):
    data = catalog.get('data') if isinstance(catalog, dict) else None
    if not isinstance(data, dict) or data.get('id') != MODEL:
        raise ValueError('Solar catalog model differs')
    architecture = data.get('architecture')
    if (not isinstance(architecture, dict) or
            architecture.get('modality') != 'text->decisions' or
            architecture.get('output_modalities') != ['decisions']):
        raise ValueError('Solar native Decisions interface differs')
    endpoints = data.get('endpoints')
    if not isinstance(endpoints, list) or len(endpoints) != 2 or {e.get('tag') for e in endpoints if isinstance(e, dict)} != set(TAGS):
        raise ValueError('Solar endpoint choices differ')
    selected = {}
    for endpoint in endpoints:
        if any((endpoint.get('name') != PROVIDER + ' | ' + VERSION,
                endpoint.get('model_id') != MODEL,
                endpoint.get('provider_name') != PROVIDER,
                endpoint.get('status') != 0,
                endpoint.get('context_length') != CONTEXT,
                endpoint.get('quantization') != 'unknown',
                endpoint.get('supported_parameters') != [],
                endpoint.get('max_completion_tokens') != 471859)):
            raise ValueError('Solar endpoint identity, context or controls differ')
        prices = endpoint.get('pricing')
        if not isinstance(prices, dict) or set(prices) != {'prompt', 'completion', 'input_cache_read', 'discount'}:
            raise ValueError('Solar price dimensions differ')
        if (Decimal(str(prices['prompt'])) != PROMPT_RATE or
                Decimal(str(prices['completion'])) != OUTPUT_RATE or
                Decimal(str(prices['input_cache_read'])) != CACHE_RATE or
                Decimal(str(prices['discount'])) != DISCOUNT):
            raise ValueError('Solar catalog prices differ')
        selected[endpoint['tag']] = endpoint
    return selected


def p0_payload(feedback, policy, tag):
    if tag not in TAGS or not isinstance(feedback, str) or not isinstance(policy, str):
        raise ValueError('Unknown Solar route or nontext input')
    value = make_payload(feedback, policy, MODEL, 'official')
    value['provider'] = {'only': [tag], 'allow_fallbacks': False,
                         'max_price': {'prompt': 0.05, 'completion': 0, 'request': 0, 'image': 0}}
    check_payload(value, feedback, policy, tag)
    return value


def check_payload(value, feedback, policy, tag):
    if (set(value) != {'model', 'provider', 'state', 'questions'} or
            value['model'] != MODEL or value['state'] != {'feedback': feedback, 'policy': policy} or
            value['provider'] != {'only': [tag], 'allow_fallbacks': False,
                                  'max_price': {'prompt': 0.05, 'completion': 0, 'request': 0, 'image': 0}} or
            list(value['questions']) != list(KEYS)):
        raise ValueError('Solar native request contains extra or changed input fields')
    for key in KEYS:
        question = value['questions'][key]
        if (set(question) != {'type', 'instructions', 'criteria'} or question['type'] != 'choice' or
                list(question['criteria']) != list(VALUES[key])):
            raise ValueError('Solar Choice question schema or label order differs')


def variant_payload(parent, condition):
    if condition not in ('P0', 'P1', 'P2'):
        raise ValueError('Unknown Solar native condition')
    value = deepcopy(parent)
    if condition != 'P0':
        for key in KEYS:
            value['questions'][key]['instructions'] += variants.P1
            if condition == 'P2':
                value['questions'][key]['instructions'] += variants.P2[key]
    verify_delta(parent, value, condition)
    return value


def verify_delta(parent, value, condition):
    if condition not in ('P0', 'P1', 'P2') or list(value.get('questions', {})) != list(KEYS):
        raise ValueError('Unknown condition or changed question order')
    stripped = deepcopy(value)
    for key in KEYS:
        expected = parent['questions'][key]['instructions']
        if condition != 'P0':
            expected += variants.P1
            if condition == 'P2':
                expected += variants.P2[key]
        if value['questions'][key]['instructions'] != expected:
            raise ValueError('Solar native Choice instruction differs')
        stripped['questions'][key]['instructions'] = parent['questions'][key]['instructions']
    if smoke.canonical(stripped) != smoke.canonical(parent):
        raise ValueError('Solar variant changed more than Choice instructions')


def build_plans(root=ROOT):
    root = Path(root)
    hashes = source_hashes(root)
    if hashes['scripts/jev_native_prompt_variants_v1.py'] != SUFFIX_SHA:
        raise ValueError('Frozen native suffix source changed')
    catalog_path = root / SNAPSHOT
    catalog = json.loads(catalog_path.read_text())
    endpoints = validate_catalog(catalog)
    rows = validate_rows(read_rows(root / 'data/pilot/inputs.jsonl'))
    policy_path = root / 'docs/LABELING_GUIDE.md'
    full_policy = policy_path.read_text()
    if full_policy.count('## Simulated routing') != 1:
        raise ValueError('Frozen policy cutoff changed')
    policy = full_policy.split('## Simulated routing')[0]
    if not policy:
        raise ValueError('Empty Solar policy')
    per_request = CONTEXT * max(PROMPT_RATE, CACHE_RATE) + 471859 * OUTPUT_RATE
    plans = {}
    for tag in TAGS:
        route_id = 'upstage' if tag == 'upstage' else 'upstage-zdr'
        for condition in ('P0', 'P1', 'P2'):
            config_id = f'solar-decide-openrouter-{route_id}-native-{condition.lower()}-v1'
            requests = []
            for row in rows:
                parent = p0_payload(row['feedback'], policy, tag)
                value = variant_payload(parent, condition)
                check_payload(value, row['feedback'], policy, tag)
                requests.append({'id': row['id'], 'feedback_sha256': smoke.sha(row['feedback'].encode()),
                                 'p0_payload_sha256': smoke.sha(smoke.canonical(parent)),
                                 'payload_sha256': smoke.sha(smoke.canonical(value)), 'payload': value})
            requests_hash = smoke.sha(smoke.canonical(requests))
            plans[config_id] = {
                'kind': 'solar-decide-openrouter-native-offline-plan-v1',
                'status': 'prepared_not_admitted', 'inference_performed': False,
                'reference_labels_read': False, 'configuration_id': config_id,
                'model': MODEL, 'expected_returned_model': VERSION,
                'expected_returned_provider': PROVIDER, 'provider_tag': tag,
                'api_url': smoke.DECISIONS_URL, 'condition': condition,
                'interface': 'OpenRouter native Decisions Choice',
                'question_order': list(KEYS), 'changed_wire_fields': [] if condition == 'P0' else ['questions.*.instructions'],
                'p1_suffix': variants.P1 if condition != 'P0' else None,
                'p2_suffixes': variants.P2 if condition == 'P2' else None,
                'suffix_source_sha256': SUFFIX_SHA,
                'input_file_sha256': smoke.sha((root / 'data/pilot/inputs.jsonl').read_bytes()),
                'policy_sha256': smoke.sha(policy.encode()),
                'source_sha256': hashes,
                'route_audit_sha256': smoke.sha((root / AUDIT).read_bytes()),
                'endpoint_snapshot': {'path': str(SNAPSHOT), 'captured_as': '2026-09-30 saved public catalog; not live account access',
                                      'sha256': smoke.sha(catalog_path.read_bytes()),
                                      'canonical_sha256': smoke.sha(smoke.canonical(catalog)),
                                      'selected_endpoint': endpoints[tag]},
                'context_tokens': CONTEXT,
                'pricing': {'prompt_usd_per_token': str(PROMPT_RATE),
                            'input_cache_read_usd_per_token': str(CACHE_RATE),
                            'completion_usd_per_token': str(OUTPUT_RATE),
                            'catalog_discount_recorded_not_assumed': str(DISCOUNT)},
                'per_request_full_context_catalog_bound_usd': str(per_request),
                'three_record_smoke_catalog_bound_usd': str(3 * per_request),
                'full_pass_catalog_bound_usd': str(60 * per_request),
                'three_pass_catalog_bound_usd': str(180 * per_request),
                'seed_policy': 'no seed parameter; provider randomness and caching unknown',
                'parser': {'candidate': 'jev_benchmark.parse_response Choice shape',
                           'source_sha256': hashes['scripts/jev_benchmark.py'],
                           'solar_response_wrapper_verified': False},
                'request_count': 60, 'requests_sha256': requests_hash, 'requests': requests,
                'smoke_ids': [r['id'] for r in rows[:3]],
                'passes': [{'pass_id': f'{config_id}-fresh{i}', 'ordinal': i,
                            'request_set_sha256': requests_hash, 'status': 'planned_not_admitted'}
                           for i in (1, 2, 3)],
                'admission': {'execution_authorized': False, 'live_endpoint_and_account_check_required': True,
                              'response_parser_smoke_required': True, 'provider_context_accounting_required': True,
                              'whole_pass_budget_review_required': True,
                              'discount_not_used_for_bound': True}}
    return plans


def prepare(directory, root=ROOT):
    plans = build_plans(root)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    if any(directory.iterdir()):
        raise ValueError('Solar preparation directory must be empty')
    for name, value in plans.items():
        with (directory / (name + '.json')).open('x') as output:
            output.write(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {name: smoke.sha(smoke.canonical(value)) for name, value in plans.items()}


def verify(directory, root=ROOT):
    plans = build_plans(root)
    directory = Path(directory)
    if {p.name for p in directory.iterdir()} != {name + '.json' for name in plans}:
        raise ValueError('Solar plan file set differs')
    for name, value in plans.items():
        expected = (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode()
        if (directory / (name + '.json')).read_bytes() != expected:
            raise ValueError('Solar plan differs from frozen sources: ' + name)
    return {name: smoke.sha(smoke.canonical(value)) for name, value in plans.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('prepare', 'verify'))
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    result = prepare(args.directory) if args.operation == 'prepare' else verify(args.directory)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
