#!/usr/bin/env python3
"""Offline exact-price DeepSeek suffix proposal and isolated v2 authority bridge.

Only DEV-051..060 may be dispatched after a separate root stage review and
allocation. Preparation reads saved public metadata, never credentials or live
catalogs. Existing failures, unknown charges and earlier route blockers remain.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
from urllib.parse import quote

from development_benchmark import ROOT, digest, read_rows
import deepseek_low_fourth_price_suffix_v1 as fourth
import deepseek_low_fresh_repeat_admission as admission
import openrouter_paid_benchmark as paid
import postapproval_authority_v2 as authority_v2

SCHEMA = 'deepseek-low-current-price-v2'
BASE = fourth.prior.prior.BASE / 'current-price-authority-v2-051-060'
MANIFEST = BASE / 'manifest.json'
CANDIDATE = BASE / 'root-review-candidate.json'
PARTITION_ID = SCHEMA + '-dev051-060'
IDS = [f'DEV-{n:03d}' for n in range(51, 61)]
INPUT_CEILING = Decimal('0.055')
OUTPUT_CEILING = Decimal('1.32')
PROMPT_RATE = Decimal('0.000000055')
COMPLETION_RATE = Decimal('0.00000132')
RESERVE = Decimal('0.0630784')
TOTAL_RESERVE = Decimal('0.6307840')
CHILD_CAP = TOTAL_RESERVE
ROUTE_DIR = ROOT / 'results/route-audits/deepseek-route-recheck-20261006-1320'
ROUTE_AUDIT = ROUTE_DIR / 'audit.json'
ROUTE_RAW = ROUTE_DIR / 'endpoints.json'
ROUTE_AUDIT_SHA = '2d02b15cfeb4f50ad189a77bfcf5c600d5683d96060536abe9fa58a173f98579'
ROUTE_RAW_SHA = 'c8b59eca62b06a12e9cf0b91d2e99c2392064cee5996535cbc14857a067a26ec'
RETRIEVED = '2026-10-06T13:20:13.739377+00:00'


def sha(path):
    return fourth.sha(path)


def bound(path):
    return fourth.bound(path)


def _load_private(name, source):
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _historical():
    # Fourth's historical helpers temporarily rebind third's globals. Give
    # those helpers a private third module, keeping all shared modules intact.
    third = _load_private('_deepseek_v2_historical_third', fourth.prior.__file__)
    old = _load_private('_deepseek_v2_historical_fourth', fourth.__file__)
    old.prior = third
    old.THIRD_VERIFY = third.verify
    old.THIRD_ROUTE_AUDIT = third.route_audit
    return old


def prior_gate():
    old = _historical()
    value = old.verify()
    # The third and fourth proposals were never dispatched. Their separate
    # terminal/claim files cannot appear unnoticed after this proposal is frozen.
    for base in (fourth.BASE, fourth.prior.BASE):
        for name in ('suffix.claim.json', 'suffix.journal.jsonl', 'suffix.raw.jsonl',
                     'suffix.records.jsonl', 'budget.json', 'suffix.root-review.json'):
            if (base / name).exists():
                raise ValueError('An earlier unsent suffix has been admitted or attempted')
    return old, value


def route_context(old=None):
    old = old or _historical()
    if sha(ROUTE_AUDIT) != ROUTE_AUDIT_SHA or sha(ROUTE_RAW) != ROUTE_RAW_SHA:
        raise ValueError('Current public route evidence changed')
    audit = json.loads(ROUTE_AUDIT.read_text())
    raw = json.loads(ROUTE_RAW.read_text())
    endpoint_rows = [x for x in raw['data']['endpoints'] if x.get('tag') == admission.PROVIDER]
    if len(endpoint_rows) != 1:
        raise ValueError('Exact public endpoint missing or duplicated')
    endpoint = endpoint_rows[0]
    if (audit.get('source') != 'https://openrouter.ai/api/v1/models/' + admission.MODEL + '/endpoints'
            or audit.get('retrieved_utc') != RETRIEVED or audit.get('model') != admission.MODEL
            or audit.get('inference_sent') is not False or audit.get('exact_provider_found') is not True
            or audit.get('exact_endpoints') != [endpoint]
            or audit.get('admission') != 'refused_live_price_exceeds_frozen_ceiling'):
        raise ValueError('Current public audit does not reconcile with raw endpoint')
    history = old._third_route_audit()
    model = history['selected_model']
    recorded = history['selected_endpoint']
    if (any(endpoint.get(k) != recorded.get(k) for k in old.ROUTE_FIELDS)
            or endpoint.get('status') != 0
            or set(endpoint['pricing']) != set(recorded['pricing'])
            or paid.number(endpoint['pricing']['prompt']) != PROMPT_RATE
            or paid.number(endpoint['pricing']['completion']) != COMPLETION_RATE
            or paid.number(endpoint['pricing']['input_cache_read']) != Decimal('0.0000000165')
            or any(endpoint['pricing'][k] != recorded['pricing'][k]
                   for k in recorded['pricing'] if k not in ('prompt', 'completion', 'input_cache_read'))
            or paid.reasoning(model, endpoint, 'low') != {'enabled': True, 'effort': 'low'}
            or paid.reservation(endpoint, 4096, INPUT_CEILING, OUTPUT_CEILING) != RESERVE):
        raise ValueError('Current exact route, prices, reasoning or full-context reserve differ')
    return deepcopy(model), deepcopy(endpoint)


def requests(endpoint=None, model=None, *, old=None, previous=None):
    old = old or _historical()
    previous = previous or old.verify()['requests']
    model_snapshot, endpoint_snapshot = route_context(old)
    model = model if model is not None else model_snapshot
    endpoint = endpoint if endpoint is not None else endpoint_snapshot
    old_model, old_endpoint = old.route_context()
    history, controls, _, _ = admission.source_state()
    policy = (ROOT / history['conditions']['P2']['instruction']['file']).read_text()
    schema = controls['response_format']['json_schema']['schema']
    rows = read_rows(admission.INPUTS)[50:]
    selected = []
    for row, item in zip(rows, previous):
        old_payload = paid.make_payload(admission.MODEL, old_endpoint, row['feedback'], policy,
            schema, 'low', 4096, old.INPUT_CEILING, old.OUTPUT_CEILING, old_model)
        new_payload = paid.make_payload(admission.MODEL, endpoint, row['feedback'], policy,
            schema, 'low', 4096, INPUT_CEILING, OUTPUT_CEILING, model)
        sole_change = deepcopy(old_payload)
        sole_change['provider']['max_price']['prompt'] = float(INPUT_CEILING)
        sole_change['provider']['max_price']['completion'] = float(OUTPUT_CEILING)
        if (row['id'] != item['id'] or digest(json.dumps(old_payload, sort_keys=True)) != item['request_sha256']
                or new_payload != sole_change or digest(row['feedback']) != item['input_sha256']
                or digest(policy) != item['instruction_sha256']):
            raise ValueError('Suffix differs beyond the two explicit price controls')
        selected.append({**item, 'old_request_sha256': item['request_sha256'],
                         'request_sha256': digest(json.dumps(new_payload, sort_keys=True))})
    if [x['id'] for x in selected] != IDS:
        raise ValueError('Only the exact ten never-sent positions are eligible')
    return selected


def manifest_value():
    old, previous = prior_gate()
    model, endpoint = route_context(old)
    sources = {**previous['sources'], 'fourth_manifest': bound(fourth.MANIFEST),
        'fourth_controller': bound(fourth.__file__), 'current_public_audit': bound(ROUTE_AUDIT),
        'current_public_endpoint_raw': bound(ROUTE_RAW), 'current_controller': bound(__file__),
        'authority_v2_module': bound(authority_v2.__file__)}
    return {'schema': SCHEMA, 'status': 'offline_prepared_unapproved_no_allocation_or_dispatch',
        'configuration_id': admission.CONFIG + '-exact-prices-0.055-1.32-authority-v2',
        'original_configuration_id': admission.CONFIG, 'model': admission.MODEL,
        'provider_tag': admission.PROVIDER, 'reasoning_effort': 'low',
        'method': 'descriptive_continuation_not_clean_matched_three',
        'fresh_pass': 'fresh1', 'condition': 'P2', 'stage': 'suffix', 'ids': IDS,
        'preserved_status_counts': previous['preserved_status_counts'],
        'preserved_failed_ids': previous['preserved_failed_ids'],
        'preserved_invalid_ids': previous['preserved_invalid_ids'], 'sources': sources,
        'requests': requests(endpoint, model, old=old, previous=previous['requests']),
        'partition_id': PARTITION_ID, 'child_cap_usd': str(CHILD_CAP),
        'per_request_reserve_usd': str(RESERVE), 'ten_request_reserve_usd': str(TOTAL_RESERVE),
        'global_hold_id': PARTITION_ID, 'global_hold_usd': str(CHILD_CAP),
        'global_authority_cap_usd': str(authority_v2.CAP),
        'global_authority_approval_sha256': authority_v2.HEADER['approval_sha256'],
        'budget_master_cap_usd': '12.38', 'requested_global_cap_usd': '10.55',
        'requested_cap_increase_approved': False, 'inference_authorized': False,
        'reference_labels_read': False, 'replay_authorized': False, 'output_repair': False,
        'price_control_change': {
            'provider.max_price.prompt_usd_per_million': [str(old.INPUT_CEILING), str(INPUT_CEILING)],
            'provider.max_price.completion_usd_per_million': [str(old.OUTPUT_CEILING), str(OUTPUT_CEILING)]},
        'exact_live_rates_usd_per_token': {'prompt': str(PROMPT_RATE), 'completion': str(COMPLETION_RATE)},
        'current_public_route': {'retrieved_utc': RETRIEVED, 'status': endpoint['status'],
            'provider_tag': endpoint['tag'], 'pricing': endpoint['pricing'],
            'historical_model_capability_source': previous['sources']['third_suffix_manifest']},
        'admission': ('separate root review; fresh exact available route/rates; allocated exact child; '
            'source-bound v2 authority hold against the unchanged approved $10 cap; '
            'no automatic allocation, authority release, cap increase or retry')}


def _write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as handle:
        json.dump(value, handle, indent=2)
        handle.write('\n')
    return sha(path)


def prepare():
    value = manifest_value()
    if MANIFEST.exists() or CANDIDATE.exists():
        raise FileExistsError('Proposal already exists')
    result = _write_new(MANIFEST, value)
    _write_new(CANDIDATE, {'schema': SCHEMA + '-design-root-review', 'approved': False,
        'authorized_by_root': False, 'independent_review': False, 'reviewer': None,
        'manifest_sha256': result, 'controller_sha256': sha(__file__),
        'authority_module_sha256': sha(authority_v2.__file__), 'ids': IDS,
        'partition_id': PARTITION_ID, 'child_cap_usd': str(CHILD_CAP),
        'inference_authorized': False, 'requested_cap_increase_approved': False})
    return result


def verify():
    value = manifest_value()
    if json.loads(MANIFEST.read_text()) != value:
        raise ValueError('Current-price v2 proposal differs from frozen sources')
    return value


def live_controls():
    recorded_model, recorded = route_context()
    catalog = paid.fetch('/models', timeout=300)
    endpoints = paid.fetch('/models/' + quote(admission.MODEL, safe='/') + '/endpoints', timeout=300)
    model, endpoint = paid.select_endpoint(admission.MODEL, admission.PROVIDER,
        catalog, endpoints, INPUT_CEILING, OUTPUT_CEILING)
    if (any(endpoint.get(k) != recorded.get(k) for k in fourth.ROUTE_FIELDS)
            or endpoint.get('status') != 0 or set(endpoint['pricing']) != set(recorded['pricing'])
            or any(paid.number(endpoint['pricing'][k]) != paid.number(recorded['pricing'][k])
                   for k in recorded['pricing'])
            or paid.reasoning(model, endpoint, 'low') != {'enabled': True, 'effort': 'low'}
            or paid.reservation(endpoint, 4096, INPUT_CEILING, OUTPUT_CEILING) != RESERVE
            or requests(endpoint, model) != verify()['requests']):
        raise ValueError('Live route, exact prices, reasoning or request identities changed')
    return model, endpoint


def _private_core():
    core = _load_private('_deepseek_current_price_private_core', fourth.prior.__file__)
    for name, value in {'SCHEMA': SCHEMA, 'BASE': BASE, 'MANIFEST': MANIFEST,
        'PARTITION_ID': PARTITION_ID, 'AUTHORITY_ID': PARTITION_ID, 'CHILD_CAP': CHILD_CAP,
        'INPUT_CEILING': INPUT_CEILING, 'OUTPUT_CEILING': OUTPUT_CEILING,
        'RESERVE': RESERVE, 'IDS': IDS, 'verify': verify, 'live_controls': live_controls,
        '__file__': __file__}.items():
        setattr(core, name, value)

    def hold(expected_head, budget_path, expected_source):
        source = core.global_hold_source(budget_path)
        if source != expected_source:
            raise ValueError('Reviewed shared hold source differs')
        return authority_v2.hold_authority(core.AUTHORITY, PARTITION_ID, str(CHILD_CAP),
            source, expected_head, stage_path=core.stage_paths()['claim'])
    core.hold_authority = hold
    return core


def global_hold_source(budget_path):
    return _private_core().global_hold_source(budget_path)


def run(receipt_path, budget_path, env_file=None):
    # The core validates exact receipt/path/budget/requests, then exact live
    # controls, then locked child and authority admission before loading a key.
    if Path(receipt_path).resolve() != (BASE / 'suffix.root-review.json').resolve():
        raise ValueError('Exact stage review path differs')
    receipt = json.loads(Path(receipt_path).read_text())
    if receipt.get('approved') is not True or receipt.get('reviewer') != 'root':
        raise ValueError('Independent root stage review required')
    return _private_core().run(receipt_path, budget_path, env_file)


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
