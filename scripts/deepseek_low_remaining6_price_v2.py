#!/usr/bin/env python3
"""Offline successor proposal for six untouched hosted DeepSeek low phases.

This controller has no allocation, key access, or inference action. A separate
reviewed execution adapter is required before any stage may be dispatched.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from types import SimpleNamespace
from urllib.parse import quote

from development_benchmark import ROOT, digest, read_rows
import deepseek_low_fresh_repeat_admission as old
import openrouter_paid_benchmark as paid
import openrouter_budget_amendment_v3 as amendment
import postapproval_authority_v3 as authority
import openrouter_budget_v4 as budget_v4

SCHEMA = 'deepseek-low-remaining6-price-v2'
CONFIG = old.CONFIG + '-remaining6-price-v2'
BASE = ROOT / 'results/repeatability-v1/deepseek-low-remaining6-price-v2'
ROUTE = BASE / 'public-route.json'
MANIFEST = BASE / 'execution-manifest.json'
CANDIDATE = BASE / 'design.root-review-candidate.json'
LOCK = BASE.parent / '.deepseek-low-remaining6-price-v2.lock'
ORIGINAL = ROOT / 'results/repeatability-v1/deepseek-low-fresh3-v2'
PRIOR_PROPOSAL = ROOT / 'results/repeatability-v1/deepseek-low-remaining6-v1'
PARTITION_ID = 'deepseek-low-remaining6-price-v2'
CHILD_CAP = Decimal('0.75')
INPUT_CEILING = Decimal('0.06')
OUTPUT_CEILING = Decimal('1.5')
CACHE_READ_CEILING = Decimal('0.06')
MAX_TOKENS = 4096
RESERVE = Decimal('0.06905856')
PHASES = (('fresh2', 'P2'), ('fresh2', 'P0'), ('fresh2', 'P1'),
          ('fresh3', 'P1'), ('fresh3', 'P2'), ('fresh3', 'P0'))
IDS = [f'DEV-{n:03d}' for n in range(1, 61)]
MODEL_FIELDS = ('id', 'canonical_slug', 'hugging_face_id', 'context_length',
                'architecture', 'reasoning')
ENDPOINT_FIELDS = ('tag', 'provider_name', 'quantization', 'model_id', 'status',
                   'context_length', 'max_prompt_tokens', 'max_completion_tokens',
                   'supported_parameters')
SEALED = (
    ORIGINAL / 'manifest.json',
    ORIGINAL / 'terminal-reconciliation-after-dev040.json',
    ORIGINAL / 'interruption-continuation-v1/manifest.json',
    ORIGINAL / 'interruption-continuation-v1/terminal-reconciliation-after-dev049.json',
    ORIGINAL / 'second-interruption-continuation-v1/manifest.json',
    ORIGINAL / 'second-interruption-continuation-v1/terminal-reconciliation-after-dev050.json',
    ORIGINAL / 'current-price-authority-v3-051-060/prompt-ceiling-v4/manifest.json',
    ORIGINAL / 'current-price-authority-v3-051-060/prompt-ceiling-v4/closure.root-review.json',
    ORIGINAL / 'current-price-authority-v3-051-060/prompt-ceiling-v4/terminal-reconciliation.json',
)
PREDECESSOR_PARTS = (
    ('phase-01-development', IDS, 'stage_completed'),
    ('phase-02-development', IDS, 'stage_completed'),
    ('phase-03-development', IDS[:40], 'request_finished'),
    ('interruption-continuation-v1/phase-03-suffix', IDS[40:49], 'stage_stopped'),
    ('second-interruption-continuation-v1/phase-03-suffix', IDS[49:50], 'stage_stopped'),
    ('current-price-authority-v3-051-060/prompt-ceiling-v4/suffix', IDS[50:], 'stage_completed'),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def binding(path):
    path = Path(path)
    return {'path': str(path.relative_to(ROOT)), 'sha256': sha(path)}


def public_route():
    catalog = paid.fetch('/models', timeout=120)
    endpoints = paid.fetch('/models/' + quote(old.MODEL, safe='/') + '/endpoints', timeout=120)
    model, endpoint = paid.select_endpoint(old.MODEL, old.PROVIDER, catalog,
        endpoints, INPUT_CEILING, OUTPUT_CEILING)
    check_route(model, endpoint, model, endpoint)
    return {'schema': SCHEMA + '-public-route',
            'retrieved_utc': datetime.now(timezone.utc).isoformat(),
            'sources': ['https://openrouter.ai/api/v1/models',
                        'https://openrouter.ai/api/v1/models/' + old.MODEL + '/endpoints'],
            'model': model, 'endpoint': endpoint, 'inference_sent': False}


def check_route(model, endpoint, saved_model, saved_endpoint):
    live, saved = endpoint['pricing'], saved_endpoint['pricing']
    if (any(model.get(k) != saved_model.get(k) for k in MODEL_FIELDS) or
            any(endpoint.get(k) != saved_endpoint.get(k) for k in ENDPOINT_FIELDS) or
            model.get('id') != old.MODEL or endpoint.get('model_id') != old.MODEL or
            endpoint.get('tag') != old.PROVIDER or
            endpoint.get('provider_name') != 'OpenInference' or
            endpoint.get('quantization') != 'fp4' or endpoint.get('status') != 0 or
            set(live) != set(saved) or
            any(paid.number(live[k]) != paid.number(saved[k]) for k in live
                if k not in ('prompt', 'completion', 'input_cache_read')) or
            not Decimal(0) <= paid.number(live['prompt']) <= INPUT_CEILING / paid.MILLION or
            not Decimal(0) <= paid.number(live['completion']) <= OUTPUT_CEILING / paid.MILLION or
            not Decimal(0) <= paid.number(live['input_cache_read']) <= CACHE_READ_CEILING / paid.MILLION or
            paid.reasoning(model, endpoint, 'low') != {'enabled': True, 'effort': 'low'}):
        raise ValueError('Current DeepSeek low model, provider, interface or price differs')
    reserve = paid.reservation(endpoint, MAX_TOKENS, INPUT_CEILING, OUTPUT_CEILING)
    if reserve != RESERVE:
        raise ValueError('DeepSeek low full-context reserve changed')
    return reserve


def sealed_sources():
    original = json.loads((ORIGINAL / 'manifest.json').read_text())
    order = [(p['repeat'], p['condition']) for p in original['phases']]
    if (original.get('configuration_id') != old.CONFIG or
            order[:3] != [('fresh1', 'P0'), ('fresh1', 'P1'), ('fresh1', 'P2')] or
            order[3:] != list(PHASES)):
        raise ValueError('Original DeepSeek low phase matrix differs')
    for path in SEALED[1:]:
        value = json.loads(path.read_text())
        if (path.name.startswith('terminal-reconciliation') and
                value.get('event') != 'partition_reconciled'):
            raise ValueError('Predecessor child is not reconciled')
        if (path.name == 'closure.root-review.json' and
                value.get('completed') is not True):
            raise ValueError('Predecessor suffix is not closed')
    for path in ORIGINAL.rglob('*'):
        if path.is_file() and re.match(r'^phase-0[4-9]-', path.name):
            raise ValueError('Remaining original low phase already has evidence')
    if PRIOR_PROPOSAL.exists():
        for path in PRIOR_PROPOSAL.rglob('*'):
            if path.is_file() and path.name.endswith((
                    '.claim.json', '.attempts.jsonl', '.records.jsonl',
                    '.responses.jsonl')):
                raise ValueError('Superseded low proposal has dispatch evidence')
    sources = {str(path.relative_to(ROOT)): sha(path) for path in SEALED}
    fragments = []
    for name, expected_ids, terminal in PREDECESSOR_PARTS:
        records = ORIGINAL / (name + '.records.jsonl')
        journal = ORIGINAL / (name + '.journal.jsonl')
        rows = [json.loads(line) for line in records.read_text().splitlines() if line.strip()]
        events = [json.loads(line) for line in journal.read_text().splitlines() if line.strip()]
        if ([row.get('id') for row in rows] != expected_ids or
                not events or events[-1].get('event') != terminal):
            raise ValueError('Ordered DeepSeek low predecessor evidence differs')
        fragments.append([row['id'] for row in rows])
        sources[str(records.relative_to(ROOT))] = sha(records)
        sources[str(journal.relative_to(ROOT))] = sha(journal)
    if fragments[0] != IDS or fragments[1] != IDS or sum(fragments[2:], []) != IDS:
        raise ValueError('DeepSeek low fresh1 predecessor has gaps or duplicates')
    return original, sources


def capacity_observation():
    """Replay the master in memory and read the earmarked pool without allocation."""
    raw = amendment.MASTER.read_bytes()
    master = object.__new__(budget_v4.BudgetLedger)
    master.events = [json.loads(line) for line in raw.splitlines() if line.strip()]
    master.cap_limit = budget_v4.CAP
    master.is_master = True
    master.file = SimpleNamespace(name=str(amendment.MASTER))
    amounts, pending, blocked = master.state()
    observed = authority.read_authority(amendment.AUTHORITY)
    headroom = master.cap - sum(amounts.values(), Decimal(0))
    return {'master_cap_usd': str(master.cap), 'master_head_sha256': hashlib.sha256(raw).hexdigest(),
            'master_available_usd': str(headroom), 'master_pending_count': len(pending),
            'master_blocked': blocked, 'master_closed': master.closed,
            'authority_head_sha256': observed.head_sha256,
            'openrouter_additional_available_usd': str(observed.openrouter_available_usd),
            'amendment_complete': observed.amendment_complete,
            'observation_only': True}


def execution_plan(route, capacity, route_sha256):
    if (route.get('schema') != SCHEMA + '-public-route' or
            route.get('inference_sent') is not False):
        raise ValueError('Require public route with no inference')
    reserve = check_route(route['model'], route['endpoint'], route['model'], route['endpoint'])
    if (capacity.get('master_cap_usd') != '22.38' or
            capacity.get('master_pending_count') != 0 or
            capacity.get('master_blocked') is not False or
            capacity.get('master_closed') is not False or
            capacity.get('amendment_complete') is not True or
            capacity.get('observation_only') is not True or
            Decimal(capacity['master_available_usd']) < CHILD_CAP or
            Decimal(capacity['openrouter_additional_available_usd']) < CHILD_CAP):
        raise ValueError('Insufficient current OpenRouter-only admission capacity')
    original, sources = sealed_sources()
    history, controls, old_endpoint, old_model = old.source_state()
    inputs = read_rows(old.INPUTS)
    if [r['id'] for r in inputs] != IDS:
        raise ValueError('DeepSeek low development input membership differs')
    requests = {}
    for condition in ('P0', 'P1', 'P2'):
        source = (history['baseline_instruction'] if condition == 'P0'
                  else history['conditions'][condition]['instruction'])
        policy_path = ROOT / source['file']
        if sha(policy_path) != source['sha256']:
            raise ValueError('DeepSeek low frozen instruction differs')
        policy = policy_path.read_text()
        planned = original['requests_by_condition'][condition]
        rows = []
        for item, old_item in zip(inputs, planned):
            old_payload = paid.make_payload(old.MODEL, old_endpoint, item['feedback'],
                policy, controls['response_format']['json_schema']['schema'], 'low',
                MAX_TOKENS, Decimal('0.1'), Decimal('0.5'), old_model)
            if (old_item['id'] != item['id'] or
                    old_item['request_sha256'] != digest(json.dumps(old_payload, sort_keys=True)) or
                    old_item['input_sha256'] != digest(item['feedback']) or
                    old_item['instruction_sha256'] != digest(policy)):
                raise ValueError('Original DeepSeek low request changed')
            payload = paid.make_payload(old.MODEL, route['endpoint'], item['feedback'],
                policy, controls['response_format']['json_schema']['schema'], 'low',
                MAX_TOKENS, INPUT_CEILING, OUTPUT_CEILING, route['model'])
            expected = deepcopy(old_payload)
            expected['provider']['max_price'] = {
                'prompt': float(INPUT_CEILING), 'completion': float(OUTPUT_CEILING),
                'request': 0, 'image': 0}
            if payload != expected:
                raise ValueError('New DeepSeek low request changed beyond declared price ceilings')
            rows.append({'id': item['id'], 'payload': payload,
                         'request_sha256': digest(json.dumps(payload, sort_keys=True)),
                         'original_request_sha256': old_item['request_sha256']})
        if len(rows) != 60:
            raise ValueError('DeepSeek low request count differs')
        requests[condition] = rows
        sources[source['file']] = sha(policy_path)
    sources[str(old.INPUTS.relative_to(ROOT))] = sha(old.INPUTS)
    for name in ('deepseek_low_fresh_repeat_admission.py',
                 'openrouter_paid_benchmark.py', 'development_benchmark.py',
                 'deepseek_low_remaining6_price_v2.py', 'postapproval_authority_v3.py',
                 'paid_budget_partitions_v4.py', 'openrouter_budget_v4.py'):
        path = ROOT / 'scripts' / name
        sources[str(path.relative_to(ROOT))] = sha(path)
    test = ROOT / 'tests/test_deepseek_low_remaining6_price_v2.py'
    sources[str(test.relative_to(ROOT))] = sha(test)
    return {'schema': SCHEMA + '-execution-plan',
            'status': 'offline_prepared_unapproved', 'inference_authorized': False,
            'allocation_authorized': False, 'execution_adapter_admitted': False,
            'configuration_id': CONFIG, 'original_configuration_id': old.CONFIG,
            'supersedes_unadmitted_proposal': 'deepseek-low-remaining6-current-price-v1',
            'model': old.MODEL, 'provider': old.PROVIDER,
            'provider_name': 'OpenInference', 'quantization': 'fp4',
            'reasoning': 'low', 'route_sha256': route_sha256,
            'observed_endpoint_prices': route['endpoint']['pricing'],
            'price_control_amendment': 'provider.max_price prompt 0.03 to 0.06 USD/M, completion 1.32 to 1.5 USD/M; cache read ceiling 0.06 USD/M; other controls unchanged',
            'phase_order': [{'phase_index': i, 'repeat': repeat, 'condition': condition,
                             'smoke_ids': IDS[:3], 'development_ids': IDS}
                            for i, (repeat, condition) in enumerate(PHASES, start=3)],
            'requests_by_condition': requests,
            'request_count': 378, 'partition_id': PARTITION_ID,
            'funding_pool': 'openrouter_additional',
            'master_cap_usd': '22.38', 'proposed_child_cap_usd': str(CHILD_CAP),
            'input_price_ceiling_usd_per_million': str(INPUT_CEILING),
            'output_price_ceiling_usd_per_million': str(OUTPUT_CEILING),
            'cache_read_price_ceiling_usd_per_million': str(CACHE_READ_CEILING),
            'per_request_reserve_usd': str(reserve),
            'all_request_reserve_if_concurrent_usd': str(reserve * 378),
            'full_series_completion_guaranteed': False,
            'predecessor_status': 'fresh1 P0/P1/P2 sealed; historical unknown-cost upper bounds retained in older children; no completed phase rerun',
            'capacity_observation': capacity,
            'source_bindings': sources,
            'admission_gate': 'No dispatch adapter admitted. Requires independent review, exact $0.75 OpenRouter-only child and authority hold, reviewed smoke and stage receipts, fresh route/request/reserve checks, sequential capacity, no implicit retry.'}


def prepare():
    route = public_route()
    route_bytes = (json.dumps(route, indent=2, ensure_ascii=False) + '\n').encode()
    route_sha256 = hashlib.sha256(route_bytes).hexdigest()
    value = execution_plan(route, capacity_observation(), route_sha256)
    manifest_bytes = (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode()
    manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
    candidate = {
        'schema': SCHEMA + '-design-root-review', 'approved': False,
        'independent_review': False, 'authorized_by_root': False,
        'reviewer': None, 'manifest_sha256': manifest_sha256,
        'controller_sha256': sha(__file__), 'inference_authorized': False}
    candidate_bytes = (json.dumps(candidate, indent=2) + '\n').encode()
    BASE.parent.mkdir(parents=True, exist_ok=True)
    with LOCK.open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if BASE.exists():
            raise FileExistsError('DeepSeek low successor proposal already exists')
        with tempfile.TemporaryDirectory(dir=BASE.parent,
                                         prefix='.deepseek-low-remaining6-price-v2-') as temp:
            stage = Path(temp)
            (stage / ROUTE.name).write_bytes(route_bytes)
            (stage / MANIFEST.name).write_bytes(manifest_bytes)
            (stage / CANDIDATE.name).write_bytes(candidate_bytes)
            os.rename(stage, BASE)
    verify()
    return manifest_sha256


def verify():
    route = json.loads(ROUTE.read_text())
    saved = json.loads(MANIFEST.read_text())
    if saved != execution_plan(route, saved['capacity_observation'], sha(ROUTE)):
        raise ValueError('DeepSeek low offline proposal differs')
    return sha(MANIFEST)


def live_check():
    verify()
    saved = json.loads(ROUTE.read_text())
    fresh = public_route()
    check_route(fresh['model'], fresh['endpoint'], saved['model'], saved['endpoint'])
    return {'route_available': True, 'inference_sent': False,
            'observed_endpoint_prices': fresh['endpoint']['pricing'],
            'reserve_usd': str(RESERVE)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify', 'live-check'))
    args = parser.parse_args()
    if args.action == 'prepare': print(prepare())
    elif args.action == 'verify': print(verify())
    else: print(json.dumps(live_check()))


if __name__ == '__main__':
    main()
