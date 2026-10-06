#!/usr/bin/env python3
"""Offline proposal for seven remaining DeepSeek high phases at declared prices.

There is no allocation, API key, inference, or stage execution action here.
The previously closed P0 and P1 stages remain in their original configuration.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

import deepseek_high_authority_v3 as prior
import deepseek_high_v3_closure_bridge as closure
import openrouter_paid_benchmark as paid
import openrouter_budget_amendment_v3 as amendment
import openrouter_budget_v4 as budget_v4
import postapproval_authority_v3 as authority

study = prior.study
SCHEMA = 'deepseek-high-remaining7-price-v1'
CONFIG = prior.CONFIG + '-remaining7-price-v1'
BASE = study.ROOT / 'results/repeatability-v1/deepseek-high-remaining7-price-v1'
ROUTE = BASE / 'public-route.json'
MANIFEST = BASE / 'execution-manifest.json'
REVIEW = BASE / 'design.root-review-candidate.json'
PARTITION_ID = 'deepseek-high-remaining7-price-v1'
CHILD_CAP = Decimal('1.00')
INPUT_CEILING = Decimal('0.06')
OUTPUT_CEILING = Decimal('1.5')
CACHE_CEILING = Decimal('0.06')
RESERVE = Decimal('0.06905856')
PHASES = (('fresh1', 'P2'), ('fresh2', 'P2'), ('fresh2', 'P0'),
          ('fresh2', 'P1'), ('fresh3', 'P1'), ('fresh3', 'P2'),
          ('fresh3', 'P0'))
SEALED = (prior.EXECUTION, prior.ROUTE, prior.BASE / 'budget.json',
          prior.BASE / 'fresh1/P0/closure.root-review.json',
          prior.BASE / 'fresh1/P0/closure-ledger-snapshot.jsonl',
          prior.BASE / 'fresh1/P1/closure.root-review.json',
          prior.BASE / 'fresh1/P1/closure-ledger-snapshot.jsonl',
          closure.MANIFEST, closure.REVIEW)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def public_route():
    catalog = paid.fetch('/models', timeout=120)
    endpoints = paid.fetch('/models/' + quote(study.MODEL, safe='/') + '/endpoints', timeout=120)
    model, endpoint = paid.select_endpoint(study.MODEL, study.PROVIDER, catalog,
                                            endpoints, INPUT_CEILING, OUTPUT_CEILING)
    saved = prior.route_snapshot()
    check_route(model, endpoint, saved['model'], saved['selected_endpoint'])
    return {'schema': SCHEMA + '-public-route',
            'retrieved_utc': datetime.now(timezone.utc).isoformat(),
            'source': 'https://openrouter.ai/api/v1/models/' + study.MODEL + '/endpoints',
            'model': model, 'selected_endpoint': endpoint,
            'inference_sent': False}


def check_route(model, endpoint, saved_model, saved_endpoint):
    live, saved = endpoint['pricing'], saved_endpoint['pricing']
    token = ('prompt', 'completion', 'input_cache_read')
    if (any(model.get(k) != saved_model.get(k) for k in prior.MODEL_FIELDS) or
            any(endpoint.get(k) != saved_endpoint.get(k) for k in prior.ENDPOINT_FIELDS) or
            set(live) != set(saved) or
            any(paid.number(live[k]) != paid.number(saved[k]) for k in live if k not in token) or
            not Decimal(0) <= paid.number(live['prompt']) <= INPUT_CEILING / paid.MILLION or
            not Decimal(0) <= paid.number(live['completion']) <= OUTPUT_CEILING / paid.MILLION or
            not Decimal(0) <= paid.number(live['input_cache_read']) <= CACHE_CEILING / paid.MILLION or
            model.get('id') != study.MODEL or endpoint.get('model_id') != study.MODEL or
            endpoint.get('tag') != study.PROVIDER or
            endpoint.get('provider_name') != study.PROVIDER_NAME or
            endpoint.get('quantization') != study.QUANTIZATION or
            endpoint.get('status') != 0 or
            paid.reasoning(model, endpoint, study.EFFORT) !=
                {'enabled': True, 'effort': study.EFFORT} or
            paid.reservation(endpoint, study.MAX_TOKENS,
                INPUT_CEILING, OUTPUT_CEILING) != RESERVE):
        raise ValueError('New DeepSeek high route, price, reasoning or reserve differs')
    return RESERVE


def sealed_sources():
    prior.verify()
    closure.verify(sha(closure.MANIFEST))
    closure.require_review()
    phases = tuple((repeat, condition) for repeat in study.ORDERS
                   for condition in study.ORDERS[repeat]
                   if (repeat, condition) not in (('fresh1', 'P0'), ('fresh1', 'P1')))
    if phases != PHASES:
        raise ValueError('Original DeepSeek high remaining order differs')
    for repeat, condition in PHASES:
        folder = prior.BASE / repeat / condition
        for stage in ('smoke', 'development'):
            for name in (stage + '.claim.json', stage + '.attempts.jsonl',
                         stage + '.responses.jsonl'):
                if (folder / name).exists():
                    raise ValueError('Remaining old high phase already claimed')
    return {str(p.relative_to(study.ROOT)): sha(p) for p in SEALED}


def capacity_observation():
    raw = amendment.MASTER.read_bytes()
    master = object.__new__(budget_v4.BudgetLedger)
    master.events = [json.loads(x) for x in raw.splitlines() if x.strip()]
    master.cap_limit = budget_v4.CAP
    master.is_master = True
    master.file = SimpleNamespace(name=str(amendment.MASTER))
    amounts, pending, blocked = master.state()
    observed = authority.read_authority(amendment.AUTHORITY)
    return {'master_cap_usd': str(master.cap),
            'master_head_sha256': hashlib.sha256(raw).hexdigest(),
            'master_available_usd': str(master.cap - sum(amounts.values(), Decimal(0))),
            'master_pending_count': len(pending), 'master_blocked': blocked,
            'master_closed': master.closed,
            'authority_head_sha256': observed.head_sha256,
            'openrouter_additional_available_usd': str(observed.openrouter_available_usd),
            'amendment_complete': observed.amendment_complete,
            'observation_only': True}


def execution_plan(route, capacity):
    if route.get('schema') != SCHEMA + '-public-route' or route.get('inference_sent') is not False:
        raise ValueError('Require exact public inference-free route')
    saved = prior.route_snapshot()
    check_route(route['model'], route['selected_endpoint'],
                saved['model'], saved['selected_endpoint'])
    if (capacity.get('master_cap_usd') != '22.38' or
            capacity.get('master_pending_count') != 0 or
            capacity.get('master_blocked') is not False or
            capacity.get('master_closed') is not False or
            capacity.get('amendment_complete') is not True or
            capacity.get('observation_only') is not True or
            Decimal(capacity['master_available_usd']) < CHILD_CAP or
            Decimal(capacity['openrouter_additional_available_usd']) < CHILD_CAP):
        raise ValueError('Insufficient current OpenRouter-only capacity')
    sources = sealed_sources()
    inputs = {row['id']: row['feedback'] for row in study.input_rows()}
    requests = {}
    for repeat, condition in PHASES:
        old = prior.verify_plan(repeat, sha(prior.BASE / repeat / 'manifest.json'))
        sources[str((prior.BASE / repeat / 'manifest.json').relative_to(study.ROOT))] = sha(
            prior.BASE / repeat / 'manifest.json')
        condition_plan = old['conditions'][condition]
        for stage in ('smoke', 'development'):
            rows = []
            for request in condition_plan[stage]:
                frozen = request['payload']
                payload = paid.make_payload(study.MODEL, route['selected_endpoint'],
                    inputs[request['record_id']], frozen['messages'][0]['content'],
                    frozen['response_format']['json_schema']['schema'], study.EFFORT,
                    study.MAX_TOKENS, INPUT_CEILING, OUTPUT_CEILING, route['model'])
                expected = deepcopy(frozen)
                expected['provider']['max_price'] = {
                    'prompt': float(INPUT_CEILING), 'completion': float(OUTPUT_CEILING),
                    'request': 0, 'image': 0}
                if payload != expected:
                    raise ValueError('High request differs beyond declared max_price amendment')
                rows.append({'id': request['record_id'], 'payload': payload,
                             'request_sha256': study.digest(json.dumps(payload, sort_keys=True)),
                             'original_request_sha256': request['request_sha256'],
                             'input_sha256': request['input_sha256'],
                             'instruction_sha256': request['instruction_sha256']})
            if len(rows) != (3 if stage == 'smoke' else 60):
                raise ValueError('DeepSeek high stage count differs')
            requests[f'{repeat}/{condition}/{stage}'] = rows
    for name in ('deepseek_high_remaining7_price_v1.py',
                 'deepseek_high_authority_v3.py',
                 'deepseek_high_v3_closure_bridge.py',
                 'deepseek_high_fresh_repeat_execution.py',
                 'deepseek_high_fresh_repeat_study.py',
                 'openrouter_paid_benchmark.py',
                 'postapproval_authority_v3.py',
                 'openrouter_budget_v4.py'):
        p = study.ROOT / 'scripts' / name
        sources[str(p.relative_to(study.ROOT))] = sha(p)
    test = study.ROOT / 'tests/test_deepseek_high_remaining7_price_v1.py'
    sources[str(test.relative_to(study.ROOT))] = sha(test)
    return {'schema': SCHEMA + '-execution-plan',
            'status': 'offline_prepared_unapproved',
            'configuration_id': CONFIG, 'original_configuration_id': prior.CONFIG,
            'model': study.MODEL, 'provider': study.PROVIDER,
            'provider_name': study.PROVIDER_NAME,
            'quantization': study.QUANTIZATION, 'reasoning': study.EFFORT,
            'price_control_amendment': 'provider.max_price prompt 0.0495 to 0.06 USD/M; completion 1.32 to 1.5 USD/M; cache-read admissible up to 0.06 USD/M; preserve other controls',
            'original_closed_stages': ['fresh1/P0', 'fresh1/P1'],
            'phase_order': [{'phase_index': i, 'repeat': repeat,
                             'condition': condition, 'smoke_count': 3,
                             'development_count': 60}
                            for i, (repeat, condition) in enumerate(PHASES, start=2)],
            'requests_by_stage': requests, 'request_count': 441,
            'route_sha256': sha(ROUTE),
            'observed_endpoint_prices': route['selected_endpoint']['pricing'],
            'prompt_ceiling_usd_per_million': str(INPUT_CEILING),
            'completion_ceiling_usd_per_million': str(OUTPUT_CEILING),
            'cache_read_ceiling_usd_per_million': str(CACHE_CEILING),
            'per_request_reserve_usd': str(RESERVE),
            'all_request_reserve_if_concurrent_usd': str(RESERVE * 441),
            'full_series_completion_guaranteed': False,
            'partition_id': PARTITION_ID,
            'proposed_child_cap_usd': str(CHILD_CAP),
            'funding_pool': 'openrouter_additional',
            'master_cap_usd': '22.38',
            'capacity_observation': capacity,
            'source_bindings': sources,
            'inference_authorized': False, 'allocation_authorized': False,
            'execution_adapter_admitted': False,
            'admission_gate': 'Close and reconcile old child first; independent review of new execution adapter and exact stage receipts; new $1.00 OpenRouter-only child and authority hold; fresh route and per-request reserve check; inspected smoke before development; no retry'}


def prepare():
    if ROUTE.exists() or MANIFEST.exists() or REVIEW.exists():
        raise FileExistsError('DeepSeek high remaining7 proposal already exists')
    route = public_route()
    BASE.mkdir(parents=True, exist_ok=True)
    ROUTE.write_text(json.dumps(route, indent=2, ensure_ascii=False) + '\n')
    value = execution_plan(route, capacity_observation())
    MANIFEST.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    REVIEW.write_text(json.dumps({'schema': SCHEMA + '-design-root-review',
        'approved': False, 'independent_review': False,
        'authorized_by_root': False, 'reviewer': None,
        'manifest_sha256': sha(MANIFEST), 'controller_sha256': sha(__file__),
        'inference_authorized': False}, indent=2) + '\n')
    return sha(MANIFEST)


def verify():
    saved = json.loads(MANIFEST.read_text())
    route = json.loads(ROUTE.read_text())
    if saved != execution_plan(route, saved['capacity_observation']):
        raise ValueError('DeepSeek high remaining7 proposal or source differs')
    return sha(MANIFEST)


def live_check():
    verify()
    fresh = public_route()
    return {'inference_sent': False,
            'observed_endpoint_prices': fresh['selected_endpoint']['pricing']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify', 'live-check'))
    args = parser.parse_args()
    if args.action == 'prepare': print(prepare())
    elif args.action == 'verify': print(verify())
    else: print(json.dumps(live_check()))


if __name__ == '__main__': main()
