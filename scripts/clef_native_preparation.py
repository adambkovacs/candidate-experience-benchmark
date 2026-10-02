#!/usr/bin/env python3
"""Offline-only Clef/Clef Flash native Choice preparation for 60 development cases.

This module has no network, credential, or inference function. It does not
authorize spending. Provider access, billing and output shape require a live
three-record smoke after a separate budget and account review.
"""

import argparse
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
from pathlib import Path

from development_benchmark import ROOT, KEYS, VALUES, read_rows
from jev_benchmark import make_payload, parse_response
from jev_native_prompt_variants_v1 import P1, P2

MODELS = {
    'clef': {'route': '@cf/cloudflare/clef', 'selector': 'clef',
             'input_usd_per_million': Decimal('0.24'),
             'source': 'https://developers.cloudflare.com/workers-ai/models/clef/'},
    'clef-flash': {'route': '@cf/cloudflare/clef-flash', 'selector': 'clef-flash',
                   'input_usd_per_million': Decimal('0.09'),
                   'source': 'https://developers.cloudflare.com/workers-ai/models/clef-flash/'},
}
CONTEXT_TOKENS = 65_536
CONDITIONS = ('P0', 'P1', 'P2')
PASSES = ('fresh1', 'fresh2', 'fresh3')
SMOKE_IDS = tuple(f'DEV-{number:03d}' for number in range(1, 4))
IDS = tuple(f'DEV-{number:03d}' for number in range(1, 61))
ACCOUNT_ENV = 'CLOUDFLARE_ACCOUNT_ID'
TOKEN_ENV = 'CLOUDFLARE_API_TOKEN'
PROPOSED_INITIAL_SMOKE_CAP_USD = Decimal('0.10')
INPUTS = Path('data/pilot/inputs.jsonl')
POLICY = Path('docs/LABELING_GUIDE.md')
SOURCE_FILES = (INPUTS, POLICY, Path('scripts/development_benchmark.py'),
                Path('scripts/jev_benchmark.py'), Path('scripts/jev_native_prompt_variants_v1.py'),
                Path('scripts/clef_native_preparation.py'))


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':')).encode('utf-8')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inputs_and_policy(root=ROOT):
    root = Path(root)
    rows = read_rows(root / INPUTS)
    if ([row.get('id') for row in rows] != list(IDS) or
            any(set(row) != {'id', 'feedback'} or
                not isinstance(row['feedback'], str) or not row['feedback'].strip()
                for row in rows)):
        raise ValueError('Expected exact input-only 60 development records')
    policy = (root / POLICY).read_text().split('## Simulated routing')[0]
    if not policy.strip():
        raise ValueError('Empty policy')
    return rows, policy


def request_payload(feedback, policy, model, condition):
    if model not in MODELS or condition not in CONDITIONS:
        raise ValueError('Unknown model or native prompt condition')
    payload = make_payload(feedback, policy, MODELS[model]['selector'], 'official')
    if set(payload) != {'model', 'state', 'questions'} or list(payload['questions']) != list(KEYS):
        raise ValueError('Unexpected native decision envelope')
    for field in KEYS:
        question = payload['questions'][field]
        if (set(question) != {'type', 'instructions', 'criteria'} or
                question['type'] != 'choice' or
                list(question['criteria']) != list(VALUES[field])):
            raise ValueError('Unexpected native Choice question')
        if condition != 'P0':
            question['instructions'] += P1
            if condition == 'P2':
                question['instructions'] += P2[field]
    return payload


def reservation_usd(model, request_count):
    if model not in MODELS or type(request_count) is not int or request_count < 0:
        raise ValueError('Unknown model or request count')
    per_request = (Decimal(CONTEXT_TOKENS) * MODELS[model]['input_usd_per_million']
                   / Decimal(1_000_000))
    # Reserve integer micro-dollars per request in the separate Cloudflare ledger.
    micro_usd = (per_request * 1_000_000).to_integral_value(rounding=ROUND_CEILING)
    return Decimal(request_count) * micro_usd / Decimal(1_000_000)


def build_plan(root=ROOT):
    root = Path(root)
    rows, policy = inputs_and_policy(root)
    bindings = {str(path): sha((root / path).read_bytes()) for path in SOURCE_FILES}
    models = {}
    for model, spec in MODELS.items():
        requests = {}
        for condition in CONDITIONS:
            requests[condition] = []
            for row in rows:
                payload = request_payload(row['feedback'], policy, model, condition)
                requests[condition].append({'id': row['id'],
                    'input_sha256': sha(row['feedback'].encode('utf-8')),
                    'payload_sha256': sha(canonical(payload))})
        stages = [{'pass': repeat, 'condition': condition,
                   'smoke_ids': list(SMOKE_IDS), 'development_ids': list(IDS),
                   'admission': 'three_smoke_then_sixty_after_review',
                   'status': 'offline_prepared_no_inference'}
                  for repeat in PASSES for condition in CONDITIONS]
        count = len(stages) * (len(SMOKE_IDS) + len(IDS))
        models[model] = {'route': spec['route'], 'selector': spec['selector'],
                         'price_source': spec['source'], 'context_tokens': CONTEXT_TOKENS,
                         'published_input_usd_per_million': str(spec['input_usd_per_million']),
                         'request_count_if_all_stages_run': count,
                         'full_context_planning_reservation_usd': str(reservation_usd(model, count)),
                         'requests': requests, 'stages': stages}
    return {'schema': 'clef-native-input-only-preparation-v1',
            'status': 'offline_prepared_unapproved', 'inference_performed': False,
            'reference_labels_read': False, 'records': len(rows),
            'models': models, 'source_sha256': bindings,
            'future_credential_env_names': [ACCOUNT_ENV, TOKEN_ENV],
            'initial_smoke_for_review': {
                'pass': 'fresh1', 'condition': 'P0', 'ids': list(SMOKE_IDS),
                'models': list(MODELS), 'request_count': len(MODELS) * len(SMOKE_IDS),
                'full_context_planning_reservation_usd': str(sum(
                    (reservation_usd(model, len(SMOKE_IDS)) for model in MODELS), Decimal(0))),
                'proposed_cloudflare_cap_usd': str(PROPOSED_INITIAL_SMOKE_CAP_USD),
                'status': 'needs_account_token_budget_and_live_review'},
            'request_scope': 'one_state_and_four_choice_questions_per_record',
            'score_policy': 'offline_against_frozen_60_references_only_after_terminal_phases',
            'repeat_policy': 'three_separately_dispatched_full_passes_per_condition',
            'budget_note': 'Planning reservation uses full published context per request; no Cloudflare billing or account access was verified.'}


def parse_rest_response(envelope, model):
    """Parse a saved Cloudflare REST envelope; never infer or repair labels."""
    if model not in MODELS or not isinstance(envelope, dict):
        raise ValueError('Unknown model or malformed REST envelope')
    if (envelope.get('success') is not True or envelope.get('errors') != [] or
            not isinstance(envelope.get('result'), dict)):
        raise ValueError('Cloudflare REST envelope unsuccessful or incomplete')
    result = envelope['result']
    prediction = parse_response(result, MODELS[model]['selector'])
    answers = result['answers']
    usage = result.get('usage')
    if usage is not None and not isinstance(usage, dict):
        raise ValueError('Malformed usage')
    if isinstance(usage, dict) and 'input_tokens' in usage and (
            type(usage['input_tokens']) is not int or usage['input_tokens'] < 0):
        raise ValueError('Malformed input token usage')
    return {'prediction': prediction,
            'probabilities': {field: answers[field]['probabilities'] for field in KEYS},
            'confidence': {field: answers[field]['confidence'] for field in KEYS},
            'usage': usage, 'returned_model': result['model'],
            'actual_charge_usd': None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path,
                        help='Optional path for an offline preparation manifest')
    args = parser.parse_args()
    plan = build_plan()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n')
        print(args.output)
    else:
        print(json.dumps({'schema': plan['schema'], 'status': plan['status'],
                          'records': plan['records'],
                          'initial_smoke_for_review': plan['initial_smoke_for_review'],
                          'models': {name: {'route': item['route'],
                              'stages': len(item['stages']),
                              'request_count_if_all_stages_run': item['request_count_if_all_stages_run'],
                              'full_context_planning_reservation_usd': item['full_context_planning_reservation_usd']}
                              for name, item in plan['models'].items()}}, indent=2))


if __name__ == '__main__':
    main()
