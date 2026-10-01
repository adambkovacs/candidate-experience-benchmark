#!/usr/bin/env python3
"""Exact public price exception for the second DeepSeek low continuation.

The frozen requests and conservative reserve do not change. This module only
admits the three selected endpoint rates captured in the dated public audit.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import deepseek_low_fresh_repeat_admission as admission
import deepseek_low_price_successor_v1 as prior
from development_benchmark import ROOT, digest, read_rows
import openrouter_paid_benchmark as paid

MANIFEST_SHA = prior.MANIFEST_SHA
ROUTE_DIR = ROOT / 'results/route-audits/deepseek-low-second-price-20261001T014436Z'
ROUTE_AUDIT = ROUTE_DIR / 'audit.json'
RAW_MODELS = ROUTE_DIR / 'models.json'
RAW_ENDPOINTS = ROUTE_DIR / 'endpoints.json'
PRICES = {'prompt': '0.000000017523', 'completion': '0.000000396',
          'input_cache_read': '0.00000000291'}
NEW_PROMPT_PRICE = PRICES['prompt']
SCHEMA = 'deepseek-low-second-price-public-route-audit-v1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def expected_pricing(historical_endpoint):
    pricing = deepcopy(historical_endpoint['pricing'])
    pricing.update(PRICES)
    return pricing


def verify_route_audit():
    """Bind the selected endpoint to both uncredentialed public responses."""
    prior.verify_route_audit()
    audit = json.loads(ROUTE_AUDIT.read_text())
    expected_sources = ((RAW_MODELS, 'https://openrouter.ai/api/v1/models'),
        (RAW_ENDPOINTS, 'https://openrouter.ai/api/v1/models/' +
         admission.MODEL + '/endpoints'))
    sources = audit.get('sources')
    if not isinstance(sources, list) or len(sources) != len(expected_sources):
        raise ValueError('Second public route source list differs')
    parsed = []
    for source, (path, url) in zip(sources, expected_sources):
        if (source.get('file') != str(path.relative_to(ROOT)) or
                source.get('url') != url or source.get('sha256') != sha(path) or
                source.get('bytes') != path.stat().st_size):
            raise ValueError('Second public route source changed')
        parsed.append(json.loads(path.read_text()))
    catalog, endpoints = parsed
    model, endpoint = paid.select_endpoint(admission.MODEL, admission.PROVIDER,
        catalog, endpoints, paid.number('0.1'), paid.number('0.5'))
    historical_endpoint = admission.source_state()[2]
    if (audit.get('schema') != SCHEMA or
            audit.get('scope') != 'Public catalog metadata only; no key or inference.' or
            audit.get('original_manifest_sha256') != MANIFEST_SHA or
            audit.get('model_id') != admission.MODEL or
            audit.get('provider_tag') != admission.PROVIDER or
            audit.get('previous_reviewed_prices_usd_per_token') != {
                'prompt': prior.NEW_PROMPT_PRICE,
                'completion': historical_endpoint['pricing']['completion'],
                'input_cache_read': historical_endpoint['pricing']['input_cache_read']} or
            audit.get('admitted_prices_usd_per_token') != PRICES or
            audit.get('selected_endpoint') != endpoint or
            audit.get('model_reasoning') != model.get('reasoning') or
            endpoint.get('pricing') != expected_pricing(historical_endpoint)):
        raise ValueError('Second public route audit differs')
    return sha(ROUTE_AUDIT)


def checked_live_context(manifest, phase, stage, catalog, endpoints):
    """Reject all route drift except the three reviewed lower rates."""
    verify_route_audit()
    history, controls, historical_endpoint, historical_model = admission.source_state()
    if historical_endpoint.get('pricing', {}).get('prompt') != prior.OLD_PROMPT_PRICE:
        raise ValueError('Frozen endpoint prompt price differs')
    model, endpoint = paid.select_endpoint(admission.MODEL, admission.PROVIDER,
        catalog, endpoints, paid.number('0.1'), paid.number('0.5'))
    critical = ('tag', 'provider_name', 'quantization', 'model_id',
                'context_length', 'max_prompt_tokens', 'max_completion_tokens',
                'supported_parameters')
    if any(endpoint.get(key) != historical_endpoint.get(key) for key in critical):
        raise ValueError('Live endpoint control or identity differs')
    if endpoint.get('pricing') != expected_pricing(historical_endpoint):
        raise ValueError('Live endpoint prices differ from reviewed second exception')
    if paid.reasoning(model, endpoint, 'low') != {'enabled': True, 'effort': 'low'}:
        raise ValueError('Live low-reasoning support differs')
    if paid.reservation(endpoint, 4096, paid.number('0.1'), paid.number('0.5')) != admission.RESERVE:
        raise ValueError('Original conservative request reserve differs')
    inputs = read_rows(admission.INPUTS)
    ids = phase['smoke_ids'] if stage == 'smoke' else phase['development_ids']
    selected = inputs[:len(ids)]
    policy_source = (history['baseline_instruction'] if phase['condition'] == 'P0'
                     else history['conditions'][phase['condition']]['instruction'])
    policy = (ROOT / policy_source['file']).read_text()
    schema = controls['response_format']['json_schema']['schema']
    frozen = manifest['requests_by_condition'][phase['condition']]
    if [row['id'] for row in selected] != ids or [item['id'] for item in frozen[:len(ids)]] != ids:
        raise ValueError('Frozen stage membership differs')
    for row, item in zip(selected, frozen):
        old_payload = paid.make_payload(admission.MODEL, historical_endpoint,
            row['feedback'], policy, schema, 'low', 4096,
            paid.number('0.1'), paid.number('0.5'), historical_model)
        new_payload = paid.make_payload(admission.MODEL, endpoint,
            row['feedback'], policy, schema, 'low', 4096,
            paid.number('0.1'), paid.number('0.5'), historical_model)
        if (old_payload != new_payload or
                digest(json.dumps(new_payload, sort_keys=True)) != item['request_sha256'] or
                digest(row['feedback']) != item['input_sha256'] or
                digest(policy) != item['instruction_sha256']):
            raise ValueError('Second price route changes the frozen request')
    return history, controls, endpoint, historical_model
