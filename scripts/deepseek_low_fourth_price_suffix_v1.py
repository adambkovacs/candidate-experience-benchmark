#!/usr/bin/env python3
"""Exact-price DEV-051..060 continuation for the DeepSeek low suffix.

The 6 October public audit changed both token-price controls. Preparation and
verification are offline. Execution retains the reviewed third suffix's atomic
child/global-budget implementation, but dispatch is gated on the exact public
route and exact audited prompt/completion rates.
"""
import argparse
from contextlib import contextmanager
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from urllib.parse import quote

from development_benchmark import ROOT, digest, read_rows
import deepseek_low_fresh_repeat_admission as admission
import deepseek_low_third_suffix_v1 as prior
import openrouter_paid_benchmark as paid

THIRD_CONTROLLER = Path(prior.__file__).resolve()
THIRD_MANIFEST = Path(prior.MANIFEST).resolve()
THIRD_VERIFY = prior.verify
THIRD_ROUTE_AUDIT = prior.route_audit
THIRD_INPUT_CEILING = prior.INPUT_CEILING
THIRD_OUTPUT_CEILING = prior.OUTPUT_CEILING
SCHEMA = 'deepseek-low-fourth-price-suffix-051-060-v1'
BASE = prior.prior.BASE / 'fourth-price-suffix-051-060-v1'
MANIFEST = BASE / 'manifest.json'
PARTITION_ID = SCHEMA
CHILD_CAP = Decimal('0.25')
INPUT_CEILING = Decimal('0.0033')
OUTPUT_CEILING = Decimal('3.3')
PROMPT_RATE = Decimal('0.0000000033')
COMPLETION_RATE = Decimal('0.0000033')
RESERVE = Decimal('0.0169771008')
TOTAL_RESERVE = Decimal('0.169771008')
IDS = [f'DEV-{n:03d}' for n in range(51, 61)]
PRIOR_SCRIPT_SHA = '0c493a407dcc8ff0b50c97f85ca4253469c012bd0c644c40fcb1393b232fbe2f'
PRIOR_MANIFEST_SHA = '3c5c76142f7bf2f16e577de15848e5fed248a2606d6392e8be959513513ef203'
BLOCK_DIR = ROOT / 'results/route-audits/deepseek-fourth-price-20261006'
BLOCK_AUDIT = BLOCK_DIR / 'audit.json'
BLOCK_MODELS = BLOCK_DIR / 'models.raw.json'
BLOCK_ENDPOINTS = BLOCK_DIR / 'endpoints.raw.json'
BLOCK_AUDIT_SHA = '38c0c6bb41bd76d337b5b346c05da75be98378cad0f49ea6f02bbf499cd580cf'
BLOCK_MODELS_SHA = '159137cead92218b204dc6d57d3fce4bc1fe89f1584765528897fdc8701f7d3b'
BLOCK_ENDPOINTS_SHA = 'ef19906e9a52799db63c98f6fe03f3b19a72dd2225f489f21dbbb7d799ffd428'
ROUTE_FIELDS = prior.ROUTE_FIELDS
_THIRD_RUNNER_GLOBALS = {name: getattr(prior, name) for name in (
    'SCHEMA', 'BASE', 'MANIFEST', 'PARTITION_ID', 'AUTHORITY_ID', 'CHILD_CAP',
    'INPUT_CEILING', 'OUTPUT_CEILING', 'RESERVE', 'IDS', 'verify',
    'live_controls', '__file__')}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bound(path):
    path = Path(path).resolve()
    return {'path': str(path.relative_to(ROOT.resolve())), 'sha256': sha(path)}


@contextmanager
def _prior_globals(values):
    saved = {name: getattr(prior, name) for name in values}
    try:
        for name, value in values.items():
            setattr(prior, name, value)
        yield
    finally:
        for name, value in saved.items():
            setattr(prior, name, value)


def _third_verify():
    with _prior_globals(_THIRD_RUNNER_GLOBALS):
        return THIRD_VERIFY()


def _third_route_audit():
    with _prior_globals(_THIRD_RUNNER_GLOBALS):
        return THIRD_ROUTE_AUDIT()


def prior_gate(third_manifest=None):
    """Bind the sealed prefix and the unused third price-bound manifest."""
    _, evidence = prior.prior_gate()
    if third_manifest is None:
        third_manifest = _third_verify()
    if (sha(THIRD_CONTROLLER) != PRIOR_SCRIPT_SHA or
            sha(THIRD_MANIFEST) != PRIOR_MANIFEST_SHA or
            third_manifest['ids'] != IDS):
        raise ValueError('Frozen third suffix differs')
    return {**evidence, 'third_suffix_manifest': bound(THIRD_MANIFEST),
            'third_suffix_controller': bound(THIRD_CONTROLLER),
            'current_blocking_route_audit': bound(BLOCK_AUDIT),
            'current_blocking_route_models': bound(BLOCK_MODELS),
            'current_blocking_route_endpoints': bound(BLOCK_ENDPOINTS)}


def blocking_route_receipt(historical=None):
    """Verify the superseding 08:59 public snapshot as a blocker only."""
    if (sha(BLOCK_AUDIT) != BLOCK_AUDIT_SHA or
            sha(BLOCK_MODELS) != BLOCK_MODELS_SHA or
            sha(BLOCK_ENDPOINTS) != BLOCK_ENDPOINTS_SHA):
        raise ValueError('Current blocking route evidence changed')
    audit = json.loads(BLOCK_AUDIT.read_text())
    models = json.loads(BLOCK_MODELS.read_text())
    endpoints = json.loads(BLOCK_ENDPOINTS.read_text())
    expected_sources = [(BLOCK_MODELS, BLOCK_MODELS_SHA),
                        (BLOCK_ENDPOINTS, BLOCK_ENDPOINTS_SHA)]
    if (audit.get('retrieved_utc') != '2026-10-06T08:59:21.840862+00:00' or
            audit.get('scope') != 'Public unauthenticated metadata; no inference' or
            [(ROOT / item.get('file', ''), item.get('sha256'))
             for item in audit.get('sources', [])] != expected_sources):
        raise ValueError('Current blocking route receipt differs')
    candidates = [item for item in endpoints['data']['endpoints']
                  if item.get('tag') == admission.PROVIDER]
    model = [item for item in models['data'] if item.get('id') == admission.MODEL]
    if len(candidates) != 1 or len(model) != 1:
        raise ValueError('Current blocking exact route identity differs')
    endpoint = candidates[0]
    if historical is None:
        historical = _third_route_audit()['selected_endpoint']
    elif 'selected_endpoint' in historical:
        historical = historical['selected_endpoint']
    if (any(endpoint.get(key) != historical.get(key) for key in ROUTE_FIELDS) or
            endpoint.get('status') != -2 or
            paid.number(endpoint['pricing']['prompt']) != Decimal('0.0000000495') or
            paid.number(endpoint['pricing']['completion']) != Decimal('0.00000132') or
            paid.number(endpoint['pricing']['input_cache_read']) != Decimal('0.0000000165')):
        raise ValueError('Current route is not the frozen unavailable blocker')
    return audit, model[0], endpoint


def route_context(old=None):
    """Build the proposed future gate from historical route identity."""
    if old is None:
        old = _third_route_audit()
    model = deepcopy(old['selected_model'])
    endpoint = deepcopy(old['selected_endpoint'])
    endpoint['pricing']['prompt'] = str(PROMPT_RATE)
    endpoint['pricing']['completion'] = str(COMPLETION_RATE)
    if (endpoint.get('tag') != admission.PROVIDER or
            endpoint.get('provider_name') != 'OpenInference' or
            endpoint.get('quantization') != 'fp4' or
            endpoint.get('status') != 0 or
            endpoint.get('context_length') != 1048576 or
            endpoint.get('max_completion_tokens') != 943718 or
            paid.reasoning(model, endpoint, 'low') != {'enabled': True, 'effort': 'low'} or
            paid.reservation(endpoint, 4096, INPUT_CEILING, OUTPUT_CEILING) != RESERVE):
        raise ValueError('Exact public route identity, controls or reserve differ')
    return model, endpoint


def requests(endpoint=None, model=None, previous=None, old_audit=None):
    if previous is None:
        previous = _third_verify()['requests']
    if old_audit is None:
        old_audit = _third_route_audit()
    current_model, current_endpoint = route_context(old_audit)
    if endpoint is None:
        endpoint = current_endpoint
    if model is None:
        model = current_model
    history, controls, _, _ = admission.source_state()
    policy = (ROOT / history['conditions']['P2']['instruction']['file']).read_text()
    schema = controls['response_format']['json_schema']['schema']
    inputs = read_rows(admission.INPUTS)[50:]
    selected = []
    for row, old_item in zip(inputs, previous):
        old_payload = paid.make_payload(admission.MODEL,
            old_audit['selected_endpoint'], row['feedback'], policy, schema,
            'low', 4096, THIRD_INPUT_CEILING, THIRD_OUTPUT_CEILING,
            old_audit['selected_model'])
        new_payload = paid.make_payload(admission.MODEL, endpoint, row['feedback'],
            policy, schema, 'low', 4096, INPUT_CEILING, OUTPUT_CEILING, model)
        exact_change = deepcopy(old_payload)
        exact_change['provider']['max_price']['prompt'] = float(INPUT_CEILING)
        exact_change['provider']['max_price']['completion'] = float(OUTPUT_CEILING)
        if (row['id'] != old_item['id'] or
                digest(json.dumps(old_payload, sort_keys=True)) != old_item['request_sha256'] or
                new_payload != exact_change or
                digest(row['feedback']) != old_item['input_sha256'] or
                digest(policy) != old_item['instruction_sha256']):
            raise ValueError('Suffix request changes beyond exact price controls')
        selected.append({'id': row['id'],
            'old_request_sha256': old_item['request_sha256'],
            'request_sha256': digest(json.dumps(new_payload, sort_keys=True)),
            'input_sha256': old_item['input_sha256'],
            'instruction_sha256': old_item['instruction_sha256']})
    if [item['id'] for item in selected] != IDS:
        raise ValueError('Exact unsent suffix membership changed')
    return selected


def manifest_value():
    third_manifest = _third_verify()
    old_audit = _third_route_audit()
    sources = prior_gate(third_manifest)
    _, blocked_model, blocked_endpoint = blocking_route_receipt(old_audit)
    sources['fourth_suffix_controller'] = bound(__file__)
    return {'schema': SCHEMA,
        'status': 'offline_prepared_current_route_blocked_no_allocation_or_dispatch',
        'configuration_id': admission.CONFIG + '-exact-prices-0.0033-3.3-v1',
        'original_configuration_id': admission.CONFIG,
        'method': 'descriptive_continuation_not_clean_matched_three',
        'fresh_pass': 'fresh1', 'condition': 'P2', 'stage': 'suffix',
        'ids': IDS, 'preserved_status_counts': {'ok': 46, 'invalid_output': 1,
            'service_error': 3, 'never_sent': 10},
        'preserved_failed_ids': ['DEV-040', 'DEV-049', 'DEV-050'],
        'preserved_invalid_ids': ['DEV-039'], 'sources': sources,
        'requests': requests(previous=third_manifest['requests'], old_audit=old_audit),
        'partition_id': PARTITION_ID,
        'child_cap_usd': str(CHILD_CAP),
        'per_request_reserve_usd': str(RESERVE),
        'ten_request_reserve_usd': str(TOTAL_RESERVE),
        'global_hold_id': PARTITION_ID, 'global_hold_usd': str(CHILD_CAP),
        'reference_labels_read': False,
        'price_control_change': {
            'provider.max_price.prompt_usd_per_million':
                [str(THIRD_INPUT_CEILING), str(INPUT_CEILING)],
            'provider.max_price.completion_usd_per_million':
                [str(THIRD_OUTPUT_CEILING), str(OUTPUT_CEILING)]},
        'exact_live_rates_usd_per_token': {'prompt': str(PROMPT_RATE),
                                            'completion': str(COMPLETION_RATE)},
        'current_route_blocker': {'retrieved_utc':
            '2026-10-06T08:59:21.840862+00:00',
            'provider_tag': blocked_endpoint['tag'], 'status': blocked_endpoint['status'],
            'pricing': blocked_endpoint['pricing'], 'model_id': blocked_model['id'],
            'disposition': 'blocked_no_allocation_or_dispatch'},
        'admission': ('current blocker must clear, then independent review, fresh exact available '
                      'route/rates, allocated exact child, root stage receipt and fixed shared hold')}


def prepare():
    value = manifest_value()
    with MANIFEST.open('x') as file:
        json.dump(value, file, indent=2)
        file.write('\n')
    return sha(MANIFEST)


def verify():
    value = manifest_value()
    if json.loads(MANIFEST.read_text()) != value:
        raise ValueError('Versioned exact-price suffix manifest changed')
    return value


def live_controls():
    """Require the exact route and exact audited prices before paid state."""
    recorded_model, recorded = route_context()
    catalog = paid.fetch('/models', timeout=300)
    endpoints = paid.fetch('/models/' + quote(admission.MODEL, safe='/') +
                           '/endpoints', timeout=300)
    model, endpoint = paid.select_endpoint(admission.MODEL, admission.PROVIDER,
        catalog, endpoints, INPUT_CEILING, OUTPUT_CEILING)
    if (any(endpoint.get(key) != recorded.get(key) for key in ROUTE_FIELDS) or
            set(endpoint.get('pricing', {})) != set(recorded['pricing']) or
            paid.number(endpoint['pricing']['prompt']) != PROMPT_RATE or
            paid.number(endpoint['pricing']['completion']) != COMPLETION_RATE or
            any(endpoint['pricing'][key] != recorded['pricing'][key] for key in
                recorded['pricing'] if key not in ('prompt', 'completion')) or
            paid.reasoning(model, endpoint, 'low') != {'enabled': True, 'effort': 'low'} or
            paid.reservation(endpoint, 4096, INPUT_CEILING, OUTPUT_CEILING) != RESERVE or
            requests(endpoint, model) != verify()['requests']):
        raise ValueError('Live exact route, prices, reasoning or request hash changed')
    return model, endpoint


@contextmanager
def _bind_prior_runner():
    """Bind the reviewed atomic runner to this separately versioned suffix."""
    replacements = {'SCHEMA': SCHEMA, 'BASE': BASE, 'MANIFEST': MANIFEST,
        'PARTITION_ID': PARTITION_ID, 'AUTHORITY_ID': PARTITION_ID,
        'CHILD_CAP': CHILD_CAP, 'INPUT_CEILING': INPUT_CEILING,
        'OUTPUT_CEILING': OUTPUT_CEILING, 'RESERVE': RESERVE, 'IDS': IDS,
        'verify': verify, 'live_controls': live_controls, '__file__': __file__}
    with _prior_globals(replacements):
        yield


def global_hold_source(budget_path):
    with _bind_prior_runner():
        return prior.global_hold_source(budget_path)


def run(receipt_path, budget_path, env_file=None):
    with _bind_prior_runner():
        return prior.run(receipt_path, budget_path, env_file)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify', 'execute-stage'))
    parser.add_argument('--review', type=Path)
    parser.add_argument('--budget', type=Path)
    parser.add_argument('--env-file')
    args = parser.parse_args()
    if args.action == 'prepare':
        print(prepare())
    elif args.action == 'verify':
        verify(); print(sha(MANIFEST))
    else:
        if not args.review or not args.budget:
            parser.error('execute-stage requires --review and --budget')
        print(json.dumps(run(args.review, args.budget, args.env_file)))


if __name__ == '__main__':
    main()
