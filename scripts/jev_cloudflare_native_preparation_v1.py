#!/usr/bin/env python3
"""Offline preparation and saved-response parser for Cloudflare's native Jev route.

No credential, budget mutation, or network function is present. A separate
reviewed admission and dispatcher are required before any inference request.
"""

import argparse
from decimal import Decimal, ROUND_CEILING
import hashlib
import json
from pathlib import Path

from development_benchmark import ROOT, KEYS, VALUES
from clef_native_preparation import inputs_and_policy
from jev_benchmark import make_payload, parse_response
from jev_native_prompt_variants_v1 import P1, P2


ROUTE = 'typesafe/jev'
EXPECTED_RETURNED_VERSION = 'jev-1.13.0'  # Cloudflare example; live version unverified.
MODEL_PAGE = 'https://developers.cloudflare.com/ai/models/typesafe/jev/'
CHECKED_DATE = '2026-10-06'
CONTEXT_TOKENS = 32_000
INPUT_USD_PER_MILLION = Decimal('0.042')
OUTPUT_USD_PER_MILLION = Decimal('0.00')
CONDITIONS = ('P0', 'P1', 'P2')
PASSES = ('fresh1', 'fresh2', 'fresh3')
IDS = tuple(f'DEV-{number:03d}' for number in range(1, 61))
SMOKE_IDS = IDS[:3]
SOURCE_FILES = (
    'data/pilot/inputs.jsonl',
    'docs/LABELING_GUIDE.md',
    'scripts/development_benchmark.py',
    'scripts/jev_benchmark.py',
    'scripts/jev_native_prompt_variants_v1.py',
    'scripts/clef_native_preparation.py',
    'scripts/jev_cloudflare_native_preparation_v1.py',
)


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':')).encode('utf-8')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def request_payload(feedback, policy, condition):
    """Make the documented Cloudflare REST body with four native Choice questions."""
    if condition not in CONDITIONS:
        raise ValueError('Unknown prompt condition')
    native = make_payload(feedback, policy, EXPECTED_RETURNED_VERSION, 'official')
    if set(native) != {'model', 'state', 'questions'} or list(native['questions']) != list(KEYS):
        raise ValueError('Unexpected Jev native payload')
    for field in KEYS:
        question = native['questions'][field]
        if (set(question) != {'type', 'instructions', 'criteria'} or
                question['type'] != 'choice' or
                list(question['criteria']) != list(VALUES[field])):
            raise ValueError('Unexpected Jev Choice question')
        if condition != 'P0':
            question['instructions'] += P1
            if condition == 'P2':
                question['instructions'] += P2[field]
    return {'model': ROUTE, 'input': {'state': native['state'],
                                      'questions': native['questions']}}


def reservation_usd(request_count):
    """Full published context at the listed input rate, rounded up per request."""
    if type(request_count) is not int or request_count < 0:
        raise ValueError('Invalid request count')
    per_request_micro = (Decimal(CONTEXT_TOKENS) * INPUT_USD_PER_MILLION
                         ).to_integral_value(rounding=ROUND_CEILING)
    return Decimal(request_count) * per_request_micro / Decimal(1_000_000)


def build_plan(root=ROOT):
    root = Path(root)
    rows, policy = inputs_and_policy(root)
    if tuple(row['id'] for row in rows) != IDS:
        raise ValueError('Expected the frozen 60 development IDs')
    requests = {}
    for condition in CONDITIONS:
        requests[condition] = [
            {'id': row['id'],
             'input_sha256': sha(row['feedback'].encode('utf-8')),
             'rest_body_sha256': sha(canonical(request_payload(row['feedback'], policy,
                                                                condition)))}
            for row in rows
        ]
    stages = [
        {'pass': repeat, 'condition': condition,
         'smoke_ids': list(SMOKE_IDS), 'development_ids': list(IDS),
         'order': 'review_three_smoke_before_sixty_development',
         'status': 'offline_prepared_no_admission'}
        for repeat in PASSES for condition in CONDITIONS
    ]
    count = len(stages) * (len(SMOKE_IDS) + len(IDS))
    return {
        'schema': 'jev-cloudflare-native-choice-preparation-v1',
        'status': 'offline_prepared_unapproved',
        'inference_performed': False,
        'reference_labels_read_or_sent': False,
        'comparison_role': 'separate_host_of_typesafe_jev_not_independent_model',
        'route': ROUTE,
        'rest_endpoint_template': 'https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run',
        'expected_returned_version': EXPECTED_RETURNED_VERSION,
        'returned_version_status': 'documentation_example_only_live_smoke_required',
        'model_page': MODEL_PAGE,
        'model_page_checked_date': CHECKED_DATE,
        'published_context_tokens': CONTEXT_TOKENS,
        'published_input_usd_per_million': str(INPUT_USD_PER_MILLION),
        'published_output_usd_per_million': str(OUTPUT_USD_PER_MILLION),
        'records': len(rows),
        'question_order': list(KEYS),
        'conditions': list(CONDITIONS),
        'passes': list(PASSES),
        'requests': requests,
        'stages': stages,
        'request_count_if_all_stages_run': count,
        'full_context_planning_reservation_usd': str(reservation_usd(count)),
        'shared_authority': {
            'ledger': 'results/clef-native-v1/cloudflare-budget-v1/authority.jsonl',
            'cap_usd': '10.00',
            'status': 'no_hold_no_allocation_requires_reviewed_shared_ledger_admission',
        },
        'source_sha256': {name: sha((root / name).read_bytes()) for name in SOURCE_FILES},
        'score_policy': 'offline_against_frozen_references_after_terminal_phases',
        'budget_note': 'Published full-context rate is a planning hold, not an observed charge. Recheck price, account access and shared ledger before admission.',
    }


def checked_plan(path, root=ROOT):
    """Require the saved plan to match current input-only sources byte for byte."""
    raw = Path(path).read_bytes()
    expected = (json.dumps(build_plan(root), indent=2, ensure_ascii=False) + '\n').encode()
    if raw != expected:
        raise ValueError('Saved Jev Cloudflare plan differs from current sources')
    return json.loads(raw), sha(raw)


def parse_rest_response(envelope):
    """Parse an already saved REST envelope, failing closed on version drift."""
    if (not isinstance(envelope, dict) or envelope.get('success') is not True or
            envelope.get('errors') != [] or not isinstance(envelope.get('result'), dict)):
        raise ValueError('Cloudflare REST envelope unsuccessful or incomplete')
    result = envelope['result']
    prediction = parse_response(result, EXPECTED_RETURNED_VERSION)
    usage = result.get('usage')
    if usage is not None and not isinstance(usage, dict):
        raise ValueError('Malformed usage')
    if isinstance(usage, dict):
        for name in ('input_tokens', 'output_tokens'):
            if name in usage and (type(usage[name]) is not int or usage[name] < 0):
                raise ValueError('Malformed token usage')
    answers = result['answers']
    return {
        'prediction': prediction,
        'probabilities': {field: answers[field]['probabilities'] for field in KEYS},
        'confidence': {field: answers[field]['confidence'] for field in KEYS},
        'usage': usage,
        'returned_model': result['model'],
        'actual_charge_usd': None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    plan = build_plan()
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n')
        print(args.output)
    else:
        print(json.dumps({'schema': plan['schema'], 'status': plan['status'],
                          'stages': len(plan['stages']),
                          'request_count_if_all_stages_run': plan['request_count_if_all_stages_run'],
                          'full_context_planning_reservation_usd': plan['full_context_planning_reservation_usd']},
                         indent=2))


if __name__ == '__main__':
    main()
