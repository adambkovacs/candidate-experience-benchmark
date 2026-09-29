#!/usr/bin/env python3
"""Stage-specific lower-price admission for the frozen DeepSeek low v2 runner.

Only the selected endpoint's prompt-price metadata may change. The old runner
retains the request loop, durable evidence, budget settlement, and no-replay
claim. This entry point must run in its own process because it temporarily
substitutes the validated endpoint returned by source_state().
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

import deepseek_low_fresh_repeat_admission as admission
import deepseek_low_fresh_repeat_execution_v2 as original
from development_benchmark import ROOT, digest, read_rows
import openrouter_paid_benchmark as paid

BASE = ROOT / 'results/repeatability-v1/deepseek-low-fresh3-v2'
MANIFEST_SHA = 'c1c685db6a4e6a9c4b8376d1d11adc98942fcf9f66eb137daed867b1dc2c5004'
PARTITION_ID = 'deepseek-low-fresh3-20260929'
ROUTE_AUDIT = BASE / 'lower-price-endpoint-audit-v1.json'
OLD_PROMPT_PRICE = '0.0000001'
NEW_PROMPT_PRICE = '0.00000003'
SCHEMA = 'deepseek-low-lower-prompt-price-stage-review-v1'
AUDIT_SCHEMA = 'deepseek-low-lower-prompt-price-public-route-audit-v1'


def stage_path(index, stage, suffix):
    if type(index) is not int or index < 1 or index > 8 or stage not in ('smoke', 'development'):
        raise ValueError('Stage is outside the never-sent successor schedule')
    if index == 1 and stage != 'development':
        raise ValueError('Phase 02 smoke is already closed and may not be replayed')
    return BASE / f'phase-{index + 1:02d}-{stage}.{suffix}'


def verify_route_audit():
    audit = json.loads(ROUTE_AUDIT.read_text())
    endpoint = audit.get('selected_endpoint', {})
    if (audit.get('schema') != AUDIT_SCHEMA or
            audit.get('manifest_sha256') != MANIFEST_SHA or
            audit.get('model_id') != admission.MODEL or
            audit.get('provider_tag') != admission.PROVIDER or
            audit.get('frozen_prompt_price_usd_per_token') != OLD_PROMPT_PRICE or
            audit.get('admitted_prompt_price_usd_per_token') != NEW_PROMPT_PRICE or
            endpoint.get('tag') != admission.PROVIDER or
            endpoint.get('model_id') != admission.MODEL or
            endpoint.get('status') != 0 or
            endpoint.get('pricing', {}).get('prompt') != NEW_PROMPT_PRICE):
        raise ValueError('Immutable public route audit differs')
    return original.sha(ROUTE_AUDIT)


def amendment_fields(index, stage, manifest_sha, old_review):
    """Exact offline fields for one supplemental root review or report check."""
    stage_path(index, stage, 'price-amendment.root-review.json')
    return {
        'schema': SCHEMA, 'approved': True,
        'manifest_sha256': manifest_sha,
        'budget_manifest_sha256': original.sha(BASE / 'budget.json'),
        'original_review_sha256': original.sha(old_review),
        'original_controller_sha256': original.sha(original.__file__),
        'successor_controller_sha256': original.sha(__file__),
        'successor_tests_sha256': original.sha(ROOT / 'tests/test_deepseek_low_price_successor_v1.py'),
        'route_audit_sha256': verify_route_audit(),
        'partition_id': PARTITION_ID, 'phase_index': index, 'stage': stage,
        'frozen_prompt_price_usd_per_token': OLD_PROMPT_PRICE,
        'admitted_prompt_price_usd_per_token': NEW_PROMPT_PRICE,
        'per_request_reserve_usd': str(admission.RESERVE),
    }


def verify_amendment(index, stage, manifest_sha, old_review, supplement):
    supplement = original.checked_path(supplement)
    if supplement != stage_path(index, stage, 'price-amendment.root-review.json'):
        raise ValueError('Price amendment receipt path differs')
    expected = amendment_fields(index, stage, manifest_sha, old_review)
    if json.loads(supplement.read_text()) != expected:
        raise ValueError('Exact supplemental root review differs')
    return expected


def checked_live_context(manifest, phase, stage, catalog, endpoints):
    """Verify one documented metadata delta and every frozen request digest."""
    history, controls, historical_endpoint, historical_model = admission.source_state()
    if historical_endpoint.get('pricing', {}).get('prompt') != OLD_PROMPT_PRICE:
        raise ValueError('Frozen endpoint prompt price differs')
    live_model, live_endpoint = paid.select_endpoint(
        admission.MODEL, admission.PROVIDER, catalog, endpoints,
        paid.number('0.1'), paid.number('0.5'))
    critical = ('tag', 'provider_name', 'quantization', 'model_id',
                'context_length', 'max_prompt_tokens', 'max_completion_tokens',
                'supported_parameters')
    if any(live_endpoint.get(key) != historical_endpoint.get(key) for key in critical):
        raise ValueError('Live endpoint control or identity differs')
    expected_pricing = deepcopy(historical_endpoint['pricing'])
    expected_pricing['prompt'] = NEW_PROMPT_PRICE
    if live_endpoint.get('pricing') != expected_pricing:
        raise ValueError('Live endpoint price differs beyond reviewed lower prompt price')
    if paid.reasoning(live_model, live_endpoint, 'low') != {'enabled': True, 'effort': 'low'}:
        raise ValueError('Live low-reasoning support differs')
    if paid.reservation(live_endpoint, 4096, paid.number('0.1'), paid.number('0.5')) != admission.RESERVE:
        raise ValueError('Original conservative request reserve differs')
    rows = read_rows(admission.INPUTS)
    ids = phase['smoke_ids'] if stage == 'smoke' else phase['development_ids']
    selected = rows[:len(ids)]
    policy_source = (history['baseline_instruction'] if phase['condition'] == 'P0'
                     else history['conditions'][phase['condition']]['instruction'])
    policy = (ROOT / policy_source['file']).read_text()
    schema = controls['response_format']['json_schema']['schema']
    frozen = manifest['requests_by_condition'][phase['condition']]
    if [row['id'] for row in selected] != ids or [item['id'] for item in frozen[:len(ids)]] != ids:
        raise ValueError('Frozen stage membership differs')
    for row, item in zip(selected, frozen):
        old_payload = paid.make_payload(admission.MODEL, historical_endpoint, row['feedback'],
            policy, schema, 'low', 4096, paid.number('0.1'), paid.number('0.5'), historical_model)
        new_payload = paid.make_payload(admission.MODEL, live_endpoint, row['feedback'],
            policy, schema, 'low', 4096, paid.number('0.1'), paid.number('0.5'), historical_model)
        if (old_payload != new_payload or
                digest(json.dumps(new_payload, sort_keys=True)) != item['request_sha256'] or
                digest(row['feedback']) != item['input_sha256'] or
                digest(policy) != item['instruction_sha256']):
            raise ValueError('Lower-price route changes the frozen request')
    return history, controls, live_endpoint, historical_model


def run(index, stage, supplement, env_file=None):
    manifest_path = BASE / 'manifest.json'
    budget_path = BASE / 'budget.json'
    old_review = stage_path(index, stage, 'root-review.json')
    manifest, phase, _ = original.prepare(manifest_path, MANIFEST_SHA, budget_path,
        PARTITION_ID, index, stage, old_review, BASE)
    verify_amendment(index, stage, MANIFEST_SHA, old_review, supplement)
    # Both public catalog checks precede key access, reservation, and stage claim.
    catalog = paid.fetch('/models', timeout=300)
    endpoints = paid.fetch('/models/' + quote(admission.MODEL, safe='/') + '/endpoints', timeout=300)
    context = checked_live_context(manifest, phase, stage, catalog, endpoints)
    original.verify_sources(manifest)
    # The old execute() fetches the catalogs again. A price or route change
    # between these checks still fails before it loads a key or claims a stage.
    with patch.object(admission, 'source_state', return_value=context):
        return original.execute(manifest_path, MANIFEST_SHA, budget_path,
            PARTITION_ID, index, stage, old_review, BASE, env_file)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase-index', type=int, required=True)
    parser.add_argument('--stage', choices=('smoke', 'development'), required=True)
    parser.add_argument('--amendment-review', type=Path, required=True)
    parser.add_argument('--env-file')
    args = parser.parse_args()
    print(run(args.phase_index, args.stage, args.amendment_review, args.env_file))


if __name__ == '__main__':
    main()
