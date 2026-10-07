#!/usr/bin/env python3
"""Source-bound offline native Decisions plan for OpenRouter Clef, Flash and Luna.

This module has no inference, credential, allocation or admission operation.
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
import openrouter_decision_smoke as native


BASE = Path('results/clef-openrouter-v1')
PLAN = BASE / 'plan.json'
TAG = {'clef': 'cloudflare', 'clef-flash': 'cloudflare', 'luna-decisions': 'openai'}
MODELS = {
    'clef': {'model': 'cloudflare/clef', 'provider': 'Cloudflare',
             'name': 'Cloudflare | cloudflare/clef', 'context': 65536,
             'max_completion_tokens': 58982, 'rate': Decimal('0.00000024')},
    'clef-flash': {'model': 'cloudflare/clef-flash', 'provider': 'Cloudflare',
                   'name': 'Cloudflare | cloudflare/clef-flash', 'context': 65536,
                   'max_completion_tokens': 58982, 'rate': Decimal('0.00000009')},
    'luna-decisions': {'model': 'openai/gpt-6-luna-decisions', 'provider': 'OpenAI',
                       'name': 'OpenAI | openai/gpt-6-luna-decisions-20261006', 'context': 1050000,
                       'max_completion_tokens': 945000, 'rate': Decimal('0.0000001')},
}
CONDITIONS = ('P0', 'P1', 'P2')
PASSES = ('fresh1', 'fresh2', 'fresh3')
IDS = tuple(f'DEV-{i:03}' for i in range(1, 61))
SMOKE_IDS = IDS[:3]
INPUT = Path('data/pilot/inputs.jsonl')
POLICY = Path('docs/LABELING_GUIDE.md')
SOURCES = (
    Path('scripts/clef_openrouter_native_v1.py'),
    Path('scripts/clef_openrouter_smoke_v1.py'),
    Path('scripts/jev_benchmark.py'),
    Path('scripts/jev_native_prompt_variants_v1.py'),
    Path('scripts/openrouter_decision_smoke.py'),
    Path('scripts/development_benchmark.py'),
    Path('scripts/openrouter_paid_benchmark.py'),
    Path('scripts/openrouter_budget_v4.py'),
    Path('scripts/openrouter_budget_v3.py'),
    Path('scripts/openrouter_budget_amendment_v3.py'),
    Path('scripts/paid_budget_partitions_v4.py'),
    Path('scripts/paid_budget_partitions_v3.py'),
    Path('scripts/openrouter_authority_release_v4.py'),
    Path('scripts/postapproval_authority_v3.py'),
    Path('scripts/postapproval_authority_v2.py'),
    INPUT, POLICY,
)
SUFFIX_SHA = '48ba1ad98ac7c085de87e1ddfb1b15f8083bb3d6a57786d708915c6d4981ccd7'


def catalog_path(key):
    if key not in MODELS:
        raise ValueError('Unknown native Decisions model')
    return BASE / f'{key}-endpoint.json'


def validate_catalog(key, catalog):
    spec = MODELS[key]
    data = catalog.get('response', {}).get('data') if isinstance(catalog, dict) else None
    if (catalog.get('source') !=
            f"https://openrouter.ai/api/v1/models/{spec['model']}/endpoints" or
            catalog.get('inference_requests') != 0 or
            not isinstance(catalog.get('checked_utc'), str) or
            not isinstance(data, dict) or data.get('id') != spec['model']):
        raise ValueError('Native route snapshot identity differs')
    architecture = data.get('architecture')
    if (not isinstance(architecture, dict) or
            architecture.get('modality') != 'text+image->decisions' or
            architecture.get('output_modalities') != ['decisions']):
        raise ValueError('Native Decisions interface unavailable')
    endpoints = data.get('endpoints')
    if not isinstance(endpoints, list) or len(endpoints) != 1:
        raise ValueError('Expected one exact native endpoint')
    endpoint = endpoints[0]
    expected = {'name': spec['name'], 'model_id': spec['model'],
                'provider_name': spec['provider'], 'tag': TAG[key],
                'context_length': spec['context'], 'max_completion_tokens': spec['max_completion_tokens'],
                'quantization': 'unknown', 'supported_parameters': [], 'status': 0}
    if (not isinstance(endpoint, dict) or any(endpoint.get(k) != v for k, v in expected.items()) or
            endpoint.get('native_tools') != {}):
        raise ValueError('Native provider/version/limits changed')
    price = endpoint.get('pricing')
    if (not isinstance(price, dict) or Decimal(str(price.get('prompt'))) != spec['rate'] or
            Decimal(str(price.get('completion'))) != 0 or
            Decimal(str(price.get('discount'))) != 0 or
            any(Decimal(str(v)) != 0 for k, v in price.items()
                if k not in {'prompt', 'completion', 'discount', 'web_search'})):
        raise ValueError('Native price or price dimensions changed')
    # Luna's separately priced web_search is not used by the exact request body.
    if key == 'luna-decisions' and Decimal(str(price.get('web_search'))) != Decimal('0.01'):
        raise ValueError('Luna optional web-search tariff changed')
    if key != 'luna-decisions' and 'web_search' in price:
        raise ValueError('Unexpected Clef optional tariff')
    return endpoint


def request(feedback, policy, key, condition):
    if key not in MODELS or condition not in CONDITIONS or not isinstance(feedback, str):
        raise ValueError('Unknown route, condition or nontext review')
    spec = MODELS[key]
    payload = make_payload(feedback, policy, spec['model'], 'official')
    payload['provider'] = {'only': [TAG[key]], 'allow_fallbacks': False,
                           'max_price': {'prompt': float(spec['rate'] * 1_000_000),
                                         'completion': 0, 'request': 0, 'image': 0}}
    if condition != 'P0':
        for field in KEYS:
            payload['questions'][field]['instructions'] += variants.P1
            if condition == 'P2':
                payload['questions'][field]['instructions'] += variants.P2[field]
    verify_request(payload, feedback, policy, key, condition)
    return payload


def verify_request(payload, feedback, policy, key, condition):
    spec = MODELS[key]
    original = make_payload(feedback, policy, spec['model'], 'official')
    original['provider'] = {'only': [TAG[key]], 'allow_fallbacks': False,
                            'max_price': {'prompt': float(spec['rate'] * 1_000_000),
                                          'completion': 0, 'request': 0, 'image': 0}}
    if (not isinstance(payload, dict) or set(payload) != {'model', 'state', 'questions', 'provider'} or
            payload['state'] != {'feedback': feedback, 'policy': policy} or
            payload['provider'] != original['provider'] or
            list(payload['questions']) != list(KEYS)):
        raise ValueError('Native request contains an extra or changed input')
    stripped = deepcopy(payload)
    for field in KEYS:
        q = payload['questions'][field]
        expected = original['questions'][field]['instructions']
        if condition != 'P0':
            expected += variants.P1
            if condition == 'P2':
                expected += variants.P2[field]
        if (set(q) != {'type', 'instructions', 'criteria'} or q['type'] != 'choice' or
                q['instructions'] != expected or list(q['criteria']) != list(VALUES[field])):
            raise ValueError('Native Choice schema or variant differs')
        stripped['questions'][field]['instructions'] = original['questions'][field]['instructions']
    if native.canonical(stripped) != native.canonical(original):
        raise ValueError('Native variant changed a non-instruction field')


def bound(key, request_count):
    if key not in MODELS or type(request_count) is not int or request_count < 0:
        raise ValueError('Invalid native cost-bound request count')
    spec = MODELS[key]
    # Charging semantics are unverified until smoke: reserve four full contexts.
    return Decimal(request_count) * len(KEYS) * spec['context'] * spec['rate']


def build(root=ROOT):
    root = Path(root)
    source_sha = {str(path): native.sha((root / path).read_bytes()) for path in SOURCES}
    if source_sha['scripts/jev_native_prompt_variants_v1.py'] != SUFFIX_SHA:
        raise ValueError('Frozen native prompt suffix changed')
    rows = validate_rows(read_rows(root / INPUT))
    if len(rows) != 60 or [r['id'] for r in rows] != list(IDS) or any(set(r) != {'id', 'feedback'} for r in rows):
        raise ValueError('Require exactly 60 input-only reviews')
    policy_raw = (root / POLICY).read_text()
    if policy_raw.count('## Simulated routing') != 1:
        raise ValueError('Frozen policy cutoff changed')
    policy = policy_raw.split('## Simulated routing')[0]
    if not policy.strip():
        raise ValueError('Empty frozen policy')
    models = {}
    for key, spec in MODELS.items():
        snapshot_path = catalog_path(key)
        snapshot = json.loads((root / snapshot_path).read_text())
        endpoint = validate_catalog(key, snapshot)
        source_sha[str(snapshot_path)] = native.sha((root / snapshot_path).read_bytes())
        requests = {}
        for condition in CONDITIONS:
            requests[condition] = []
            for row in rows:
                payload = request(row['feedback'], policy, key, condition)
                requests[condition].append({'id': row['id'],
                    'input_sha256': native.sha(row['feedback'].encode()),
                    'payload_sha256': native.sha(native.canonical(payload)), 'payload': payload})
        stages = [{'id': f'{fresh}/{condition}', 'request_set_sha256': native.sha(native.canonical(requests[condition])),
                   'smoke_ids': list(SMOKE_IDS), 'development_ids': list(IDS),
                   'smoke_status': 'unadmitted', 'development_status': 'unadmitted',
                   'gate': 'three native responses saved and root-inspected before 60 development requests'}
                  for fresh in PASSES for condition in CONDITIONS]
        models[key] = {
            'model': spec['model'], 'provider': spec['provider'], 'provider_tag': TAG[key],
            'expected_returned_model': spec['model'], 'endpoint': endpoint,
            'endpoint_snapshot_sha256': source_sha[str(snapshot_path)],
            'questions': list(KEYS), 'state_feedback_max_characters': max(len(r['feedback']) for r in rows),
            'state_truncation_note': ('Cloudflare model pages warn that roughly the first 2K state tokens are read. '
                                      'Each review is at most 206 characters and is first in state; the longer policy '
                                      'may be truncated. No exact provider tokenizer or full-policy fit is asserted.'
                                      if key != 'luna-decisions' else
                                      'No exact provider tokenizer or all-question context fit is asserted.'),
            'pricing': {'input_usd_per_token': str(spec['rate']), 'output_usd_per_token': '0',
                        'four_context_bound_per_request_usd': str(bound(key, 1)),
                        'three_smoke_bound_usd': str(bound(key, 3)),
                        'one_sixty_record_stage_bound_usd': str(bound(key, 60)),
                        'all_nine_stages_plus_smokes_bound_usd': str(bound(key, 9 * 63)),
                        'basis': 'Four full published contexts per request, no discount or cache credit'},
            'requests': requests, 'stages': stages,
        }
    return {'schema': 'clef-openrouter-native-choice-offline-v1',
            'status': 'prepared_not_admitted', 'inference_performed': False,
            'allocation_performed': False, 'reference_labels_read': False,
            'api_url': native.DECISIONS_URL, 'source_sha256': source_sha,
            'input_sha256': source_sha[str(INPUT)], 'policy_sha256': native.sha(policy.encode()),
            'pass_order': list(PASSES), 'condition_order': list(CONDITIONS),
            'smoke_policy': 'Exactly DEV-001–003 before each stage; no automatic retry or full admission',
            'budget_policy': 'One reviewed stage at a time under the existing cumulative OpenRouter cap. Reserve one full-context request, settle observed cost, then continue only while the remaining child cap fits the next full reserve; an interrupted or unknown-cost request stops without replay. Full-stage completion is not promised.',
            'models': models}


def verify(root=ROOT):
    expected = build(root)
    if json.loads((Path(root) / PLAN).read_text()) != expected:
        raise ValueError('Native plan differs from sources, catalog, or input-only payloads')
    return expected, native.sha(native.canonical(expected))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('write', 'check'))
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    value = build(args.root)
    target = args.root / PLAN
    if args.action == 'write':
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('x') as out:
            out.write(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    elif json.loads(target.read_text()) != value:
        raise SystemExit('Native route plan changed')
    print(native.sha(native.canonical(value)))


if __name__ == '__main__':
    main()
