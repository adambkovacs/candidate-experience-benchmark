#!/usr/bin/env python3
"""Read-only admission plan for one fresh matched hosted repeat series.

This module never opens a paid key, writes a ledger, or sends inference. Its
output is a reviewable plan, not a dispatch receipt. A separate reviewed runner
must implement the phase journal and smoke inspection before allocation.
"""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from development_benchmark import ROOT, digest, read_rows
import openrouter_paid_benchmark as paid

CONFIG = 'openrouter-paid-deepseek-v41-flash-off'
MODEL = 'deepseek/deepseek-v4.1-flash'
PROVIDER = 'open-inference/fp4'
CAP = Decimal('0.46')
RESERVE = Decimal('0.1069056')
HISTORICAL_KNOWN_TRIPLE = Decimal('0.009049320')
HISTORICAL_SMOKE_TRIPLE = Decimal('0.00046211')
HOSTED = ROOT / 'results/prompt-comparison-v1-2026-09-24/hosted-execution.json'
MASTER = ROOT / 'results/openrouter-paid-budget.jsonl'
INPUTS = ROOT / 'data/pilot/inputs.jsonl'
P0 = ROOT / 'results/openrouter-parallel-deepseek-flash-off-2026-09-23/development.jsonl'
P0_SMOKE = ROOT / 'results/openrouter-parallel-deepseek-flash-off-2026-09-23/smoke.jsonl'
P1 = ROOT / f'results/prompt-comparison-v1-2026-09-24/runs/{CONFIG}/P1/development.jsonl'
P1_SMOKE = ROOT / f'results/prompt-comparison-v1-2026-09-24/runs/{CONFIG}/P1/smoke-after-launch-failure.jsonl'
P2 = ROOT / f'results/prompt-comparison-v1-2026-09-24/runs/{CONFIG}/P2/development.jsonl'
P2_SMOKE = ROOT / f'results/prompt-comparison-v1-2026-09-24/runs/{CONFIG}/P2/smoke.jsonl'
REPORT = ROOT / ('results/prompt-comparison-v1-2026-09-24/paired-reports/'
                 'hosted-remaining-audit-v1/continuation-pairs-v1/' + CONFIG + '.json')
ORDERS = {'fresh1': ('P0', 'P1', 'P2'),
          'fresh2': ('P2', 'P0', 'P1'),
          'fresh3': ('P1', 'P2', 'P0')}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def binding(path):
    return {'path': str(Path(path).relative_to(ROOT)), 'sha256': sha(path)}


def source_state():
    configurations = json.loads(HOSTED.read_text())['configurations']
    matches = [x for x in configurations if x['id'] == CONFIG]
    if len(matches) != 1:
        raise ValueError('Exact historical configuration missing or duplicated')
    history = matches[0]
    controls = history['controls']['adapter_controls']
    rc = controls['request_controls']
    if (controls['requested_model'], controls['provider_tag'], controls['provider_name'],
            controls['quantization'], controls['reasoning_effort'], controls['workflow']) != (
            MODEL, PROVIDER, 'OpenInference', 'fp4', 'off', 'single_record'):
        raise ValueError('Historical route controls changed')
    if (rc['model'], rc['temperature'], rc['max_tokens'], rc['stream'],
            rc['reasoning'], rc['provider']) != (
            MODEL, 0, 4096, False, {'enabled': False},
            {'only': [PROVIDER], 'allow_fallbacks': False, 'require_parameters': True,
             'max_price': {'prompt': 0.1, 'completion': 0.5, 'request': 0, 'image': 0}}):
        raise ValueError('Frozen request controls changed')
    if (rc['response_format']['type'] != 'json_schema' or
            rc['response_format']['json_schema']['strict'] is not True or
            history['continue_on_invalid_output'] is not False or
            history['controller_timeout_seconds'] != 300.0):
        raise ValueError('Frozen parser or failure policy changed')
    report = json.loads(REPORT.read_text())
    if report.get('eligible_paired_comparison') is not False:
        raise ValueError('Fresh series eligibility decision changed')
    old = json.loads(P0.read_text().splitlines()[0])
    endpoint, model_info = old['provider_endpoint'], old['model_catalog_entry']
    if (endpoint['tag'], endpoint['provider_name'], endpoint['quantization'],
            endpoint['status'], endpoint['context_length'], endpoint['pricing']['prompt'],
            endpoint['pricing']['completion']) != (
            PROVIDER, 'OpenInference', 'fp4', 0, 1048576, '0.0000001', '0.0000005'):
        raise ValueError('Historical endpoint bound changed')
    if paid.reservation(endpoint, 4096, Decimal('0.1'), Decimal('0.5')) != RESERVE:
        raise ValueError('Conservative per-call reserve changed')
    return history, rc, endpoint, model_info


def ledger_snapshot():
    # Replay in memory. BudgetLedger(path) would open the live file in append mode.
    events = [json.loads(line) for line in MASTER.read_text().splitlines() if line.strip()]
    ledger = object.__new__(paid.BudgetLedger)
    ledger.events = events
    ledger.cap_limit = Decimal('10')
    _, pending, blocked = ledger.state()
    active = [key for key, value in ledger.partitions.items() if value['active']]
    headroom = ledger.cap - ledger.accounted()
    return {'cap_usd': str(ledger.cap), 'accounted_usd': str(ledger.accounted()),
            'headroom_usd': str(headroom), 'pending_attempts': len(pending),
            'active_partitions': active, 'blocked': blocked, 'closed': ledger.closed,
            'admission_capacity_now': not (pending or active or blocked or ledger.closed)
                                      and headroom >= CAP,
            'ledger_sha256': sha(MASTER)}


def plan_data():
    history, controls, endpoint, model_info = source_state()
    inputs = read_rows(INPUTS)
    if len(inputs) != 60 or any(set(row) != {'id', 'feedback'} for row in inputs):
        raise ValueError('Frozen input set changed')
    if [x['id'] for x in inputs] != [f'DEV-{n:03d}' for n in range(1, 61)]:
        raise ValueError('Frozen input order changed')
    instructions = {}
    for condition in ('P0', 'P1', 'P2'):
        source = history['baseline_instruction'] if condition == 'P0' else history['conditions'][condition]['instruction']
        path = ROOT / source['file']
        if sha(path) != source['sha256']:
            raise ValueError('Frozen instruction changed: ' + condition)
        instructions[condition] = path.read_text()
    requests = {}
    schema = controls['response_format']['json_schema']['schema']
    for condition, policy in instructions.items():
        one = []
        for item in inputs:
            payload = paid.make_payload(MODEL, endpoint, item['feedback'], policy, schema,
                                        'off', 4096, Decimal('0.1'), Decimal('0.5'), model_info)
            if any(payload[key] != value for key, value in controls.items() if key != 'messages'):
                raise ValueError('Reconstructed request controls changed')
            one.append({'id': item['id'], 'request_sha256': digest(json.dumps(payload, sort_keys=True)),
                        'input_sha256': digest(item['feedback']), 'instruction_sha256': digest(policy)})
        requests[condition] = one
    for condition, source in (('P0', P0), ('P1', P1), ('P2', P2)):
        first = json.loads(source.read_text().splitlines()[0])
        if first['id'] != 'DEV-001' or first['request_sha256'] != requests[condition][0]['request_sha256']:
            raise ValueError('Reconstruction differs from saved first request: ' + condition)
    smoke_cost = Decimal(0)
    for path in (P0_SMOKE, P1_SMOKE, P2_SMOKE):
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        if (len(rows) != 3 or [row['id'] for row in rows] !=
                ['DEV-001', 'DEV-002', 'DEV-003'] or
                any(row['cost_unknown'] or row['status'] != 'ok' for row in rows)):
            raise ValueError('Historical smoke proxy is incomplete')
        smoke_cost += sum((paid.number(row['observed_cost_usd']) for row in rows), Decimal(0))
    if smoke_cost != HISTORICAL_SMOKE_TRIPLE:
        raise ValueError('Historical smoke proxy changed')
    phases = [{'repeat': repeat, 'condition': condition, 'smoke_ids': [x['id'] for x in inputs[:3]],
               'development_ids': [x['id'] for x in inputs]}
              for repeat, order in ORDERS.items() for condition in order]
    snapshot = ledger_snapshot()
    return {'schema': 'affordable-hosted-repeat-admission-v1', 'configuration_id': CONFIG,
            'series': 'fresh-matched3', 'historical_first_pass_eligible': False,
            'orders': {key: list(value) for key, value in ORDERS.items()}, 'phases': phases,
            'requests_by_condition': requests, 'request_count': 9 * 63,
            'route': {'model': MODEL, 'provider': PROVIDER, 'provider_name': 'OpenInference',
                      'quantization': 'fp4', 'reasoning_effort': 'off',
                      'temperature': 0, 'max_tokens': 4096, 'seed_policy': 'No explicit seed',
                      'context_length': 1048576, 'timeout_seconds': 300.0,
                      'continue_on_invalid_output': False, 'fallbacks': False},
            'budget': {'proposed_child_cap_usd': str(CAP), 'per_call_reserve_usd': str(RESERVE),
                       'historical_three_triple_known_charge_proxy_usd': str(3 * HISTORICAL_KNOWN_TRIPLE),
                       'historical_three_triple_smoke_proxy_usd': str(3 * smoke_cost),
                       'historical_combined_proxy_usd': str(3 * (HISTORICAL_KNOWN_TRIPLE + smoke_cost)),
                       'worst_case_all_calls_reserved_usd': str(RESERVE * 567),
                       'conditional_completion': True, 'no_automatic_top_up': True,
                       'ledger': snapshot},
            'source_bindings': [binding(path) for path in (HOSTED, MASTER, INPUTS, P0, P1, P2,
                                P0_SMOKE, P1_SMOKE, P2_SMOKE, REPORT,
                                ROOT / history['baseline_instruction']['file'],
                                *(ROOT / history['conditions'][c]['instruction']['file'] for c in ('P1', 'P2')))],
            'dispatch_gate': ('Root review of plan and new fresh3 runner; recheck live exact route, price '
                              'and ledger; allocate at most $0.46 child with existing paid_budget_partitions_v2; '
                              'run each three-request smoke and inspect it before its 60-record development phase; '
                              'reserve each request atomically; retain failed, invalid and unknown outcomes; '
                              'stop before a request that cannot fit the child cap. No retry or automatic top-up.')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-capacity', action='store_true')
    args = parser.parse_args()
    plan = plan_data()
    if args.check_capacity and not plan['budget']['ledger']['admission_capacity_now']:
        raise SystemExit('Current master capacity cannot admit proposed child cap')
    print(json.dumps(plan, indent=2))


if __name__ == '__main__':
    main()
