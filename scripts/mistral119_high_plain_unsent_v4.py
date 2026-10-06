#!/usr/bin/env python3
"""Offline proposal for two never-sent plain-Mistral high smoke requests."""
import argparse
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import tempfile

import mistral119_high_plain_authority_v1 as old
import openrouter_authority_release_v4 as authority
from openrouter_budget_v4 import BudgetLedger

ROOT = old.study.ROOT
BASE = old.BASE / 'unsent-v4'
PLAN = BASE / 'fresh1/P0/smoke-suffix-plan.json'
PROPOSAL = BASE / 'proposal.json'
SCHEMA = 'mistral119-high-plain-unsent-v4'
PARTITION_ID = 'mistral119-high-plain-unsent-v4-smoke'
CHILD_CAP = Decimal('0.10')
UNSENT = ['DEV-002', 'DEV-003']
NO_RETRY = ['DEV-001']
RESERVE = Decimal('0.04177920')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relative(path):
    return str(Path(path).resolve().relative_to(ROOT.resolve()))


def closed_parent():
    terminal = json.loads(old.BASE.joinpath('terminal-public.json').read_text())
    reconciliation = json.loads(old.BASE.joinpath('reconciliation.json').read_text())
    child_path = old.BASE / ('budget-' + old.PARTITION_ID + '.jsonl')
    child = [json.loads(line) for line in child_path.read_text().splitlines()]
    if (terminal.get('schema') != 'mistral119-high-plain-terminal-public-v1' or
            terminal.get('configuration_id') != old.CONFIG or
            terminal.get('stage') != 'fresh1/P0/smoke' or
            terminal.get('status') != 'stopped_provider_rate_limit' or
            terminal.get('provider') != 'mistral' or
            terminal.get('model') != old.study.MODEL or
            terminal.get('attempted_ids') != NO_RETRY or
            terminal.get('never_sent_smoke_ids') != UNSENT or
            terminal.get('http_status') != 429 or
            terminal.get('valid_count') != 0 or
            terminal.get('retry_sent') is not False or
            terminal.get('unknown_cost_upper_bound_usd') != str(RESERVE) or
            terminal.get('reconciliation_sha256') != sha(old.BASE / 'reconciliation.json') or
            reconciliation.get('event') != 'partition_reconciled' or
            reconciliation.get('partition_id') != old.PARTITION_ID or
            reconciliation.get('known_actual_usd') != '0' or
            reconciliation.get('unknown_upper_bound_usd') != str(RESERVE) or
            Decimal(reconciliation.get('unused_allocation_released_usd', '-1')) + RESERVE != old.CAP or
            reconciliation.get('child_sha256') != sha(child_path) or
            len(child) != 4 or child[0] != {'event': 'budget', 'cap_usd': str(old.CAP)} or
            child[1].get('event') != 'reserve' or
            child[1].get('record_id') != 'DEV-001' or
            child[1].get('usd') != str(RESERVE) or
            child[2].get('event') != 'unknown_cost_accounted_as_upper_bound' or
            child[2].get('attempt_id') != child[1].get('attempt_id') or
            child[2].get('usd') != str(RESERVE) or
            child[2].get('actual_cost_usd') is not None or
            child[2].get('evidence_sha256') !=
            terminal.get('private_evidence_hashes', {}).get('smoke.attempts.jsonl') or
            child[3].get('event') != 'partition_closed'):
        raise ValueError('Plain Mistral stopped parent or unknown cost differs')
    old.verify()
    return terminal


def plan_data():
    closed_parent()
    original = old.verify_plan('fresh1', sha(old.BASE / 'fresh1/manifest.json'))
    smoke = original['conditions']['P0']['smoke']
    if ([row['record_id'] for row in smoke] != NO_RETRY + UNSENT or
            [row['position'] for row in smoke] != [1, 2, 3] or
            old.RESERVE != RESERVE or CHILD_CAP < RESERVE * 2):
        raise ValueError('Plain Mistral frozen smoke membership or budget differs')
    requests = deepcopy(smoke[1:])
    return {'schema': SCHEMA + '-plan',
            'configuration_id': old.CONFIG,
            'continuation_id': SCHEMA,
            'stage': 'fresh1/P0/smoke-suffix',
            'provider': old.PROVIDER,
            'model': old.study.MODEL,
            'reasoning_effort': 'high',
            'no_retry_ids': NO_RETRY,
            'never_sent_ids': UNSENT,
            'smoke_requests': requests,
            'original_plan_sha256': sha(old.BASE / 'fresh1/manifest.json'),
            'public_route_sha256': sha(old.ROUTE),
            'parent_terminal_sha256': sha(old.BASE / 'terminal-public.json'),
            'parent_reconciliation_sha256': sha(old.BASE / 'reconciliation.json'),
            'per_request_reserve_usd': str(RESERVE),
            'new_child_cap_usd': str(CHILD_CAP),
            'stop_on_first_provider_or_intrinsic_failure': True,
            'complete_three_request_smoke': False,
            'full_development_authorized': False,
            'later_high_passes_authorized': False}


def source_paths():
    names = ('mistral119_high_plain_unsent_v4.py',
             'mistral119_high_plain_authority_v1.py',
             'mistral119_fresh_repeat_execution.py',
             'mistral119_fresh_repeat_study.py',
             'qwen27_fresh_repeat_execution.py',
             'openrouter_authority_release_v4.py',
             'postapproval_authority_v3.py',
             'postapproval_authority_v2.py',
             'paid_budget_partitions_v4.py',
             'paid_budget_partitions_v3.py',
             'openrouter_budget_v4.py',
             'openrouter_budget_v3.py',
             'openrouter_budget_amendment_v3.py',
             'openrouter_paid_benchmark.py')
    paths = [ROOT / 'scripts' / name for name in names]
    paths += [ROOT / 'tests/test_mistral119_high_plain_unsent_v4.py',
              old.ROUTE, old.EXECUTION, old.BASE / 'fresh1/manifest.json',
              old.BASE / 'terminal-public.json', old.BASE / 'reconciliation.json',
              old.BASE / ('budget-' + old.PARTITION_ID + '.jsonl')]
    return paths


def proposal_data():
    planned = plan_data()
    if not PLAN.is_file() or json.loads(PLAN.read_text()) != planned:
        raise ValueError('Exact Mistral unsent plan must be prepared first')
    return {'schema': SCHEMA + '-proposal',
            'status': 'offline_unadmitted',
            'configuration_id': old.CONFIG,
            'continuation_id': SCHEMA,
            'stage': 'fresh1/P0/smoke-suffix',
            'no_retry_ids': NO_RETRY,
            'never_sent_ids': UNSENT,
            'never_sent_request_sha256': [row['request_sha256'] for row in planned['smoke_requests']],
            'plan_sha256': sha(PLAN),
            'predecessor_unknown_cost_id': 'DEV-001',
            'predecessor_unknown_cost_upper_bound_usd': str(RESERVE),
            'new_child_partition_id': PARTITION_ID,
            'new_child_cap_usd': str(CHILD_CAP),
            'funding_pool': 'openrouter_additional',
            'authority_reader': authority.SCHEMA,
            'budget_partition_protocol': 'paid-partitions-v4',
            'sequence_policy': 'Send DEV-002, then DEV-003 only if DEV-002 is valid and billed; stop on failure; never replay DEV-001.',
            'result_policy': 'Two-request suffix is diagnostic only. DEV-001 remains failed with unknown cost. Do not mark the original three-request smoke passed or admit development/later phases from this suffix.',
            'later_work_policy': 'Any full high stage requires a separately declared configuration or explicit root-reviewed interrupted-smoke composite protocol, new budget admission, and its own execution gate.',
            'allocation_authorized': False,
            'dispatch_authorized': False,
            'execution_adapter_admitted': False,
            'source_bindings': {relative(path): sha(path) for path in source_paths()}}


def prepare():
    if PLAN.exists() or PROPOSAL.exists():
        raise FileExistsError('Mistral unsent proposal already prepared')
    PLAN.parent.mkdir(parents=True, exist_ok=True)
    with PLAN.open('x') as out:
        json.dump(plan_data(), out, indent=2)
        out.write('\n'); out.flush(); os.fsync(out.fileno())
    value = proposal_data()
    with tempfile.NamedTemporaryFile(mode='w', dir=BASE, prefix='.proposal-',
                                     delete=False) as out:
        staged = Path(out.name)
        json.dump(value, out, indent=2)
        out.write('\n'); out.flush(); os.fsync(out.fileno())
    try:
        os.link(staged, PROPOSAL)
    finally:
        staged.unlink()
    return sha(PROPOSAL)


def verify():
    if json.loads(PROPOSAL.read_text()) != proposal_data():
        raise ValueError('Mistral unsent proposal or source bindings differ')
    return sha(PROPOSAL)


def capacity():
    """Read-only current v4 admission headroom; never creates a child."""
    verify()
    snapshot = authority.read_authority(old.AUTHORITY)
    ledger = BudgetLedger(old.MASTER)
    try:
        _, pending, blocked = ledger.state()
        available = ledger.cap - ledger.accounted()
        if pending or blocked or ledger.closed:
            available = Decimal(0)
    finally:
        ledger.close()
    return {'authority_head_sha256': snapshot.head_sha256,
            'openrouter_additional_available_usd': str(snapshot.openrouter_available_usd),
            'master_available_usd': str(available),
            'proposed_child_cap_usd': str(CHILD_CAP),
            'admissible_now': min(snapshot.openrouter_available_usd, available) >= CHILD_CAP,
            'inference_sent': False, 'allocation_written': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify', 'capacity'))
    args = parser.parse_args()
    result = {'prepare': prepare, 'verify': verify, 'capacity': capacity}[args.action]()
    print(json.dumps(result, sort_keys=True) if isinstance(result, dict) else result)


if __name__ == '__main__':
    main()
