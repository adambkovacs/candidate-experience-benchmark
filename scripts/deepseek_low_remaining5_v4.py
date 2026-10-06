#!/usr/bin/env python3
"""Offline proposal for five unsent DeepSeek low phases under v4 authority."""
import argparse
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import tempfile

import deepseek_low_remaining6_execution_v1 as old

ROOT = old.ROOT
PREDECESSOR = old.proposal.BASE / 'unsent-continuation-v1'
BASE = old.proposal.BASE / 'remaining5-v4'
MANIFEST = BASE / 'proposal.json'
AUDIT = PREDECESSOR / 'fresh2-p2-suffix-closure-audit.json'
SNAPSHOT = PREDECESSOR / 'closure-ledger-snapshot-after-dev060.jsonl'
RECONCILIATION = PREDECESSOR / 'reconciliation-after-dev060.json'
PARENT_RECONCILIATION = old.proposal.BASE / 'reconciliation-after-dev005.json'
PARENT_INTERRUPTION = old.proposal.BASE / 'fresh2-p2-dev005-interruption.audit-candidate.json'
PREDECESSOR_PLAN = PREDECESSOR / 'execution-adapter-v1'
PREDECESSOR_PROPOSAL = PREDECESSOR / 'proposal.json'
SCHEMA = 'deepseek-low-remaining5-v4-proposal-v1'
PHASES = (('fresh2', 'P0'), ('fresh2', 'P1'),
          ('fresh3', 'P1'), ('fresh3', 'P2'), ('fresh3', 'P0'))
NO_RETRY = tuple(f'DEV-{n:03}' for n in range(1, 61))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relative(path):
    return str(Path(path).resolve().relative_to(ROOT.resolve()))


def jsonl(path):
    raw = Path(path).read_bytes()
    if not raw.endswith(b'\n'):
        raise ValueError('Incomplete sealed ledger snapshot')
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def predecessor_closed():
    audit = json.loads(AUDIT.read_text())
    reconciliation = json.loads(RECONCILIATION.read_text())['partition_reconciled']
    parent = json.loads(PARENT_RECONCILIATION.read_text())
    interrupted = json.loads(PARENT_INTERRUPTION.read_text())
    ledger = jsonl(SNAPSHOT)
    if (audit.get('schema') != 'deepseek-low-successor-fresh2-p2-closure-audit-v1' or
            audit.get('status') != 'suffix_closed_composite_interrupted' or
            audit.get('clean_full_phase') is not False or
            audit.get('full_60_clean_score') is not None or
            audit.get('suffix_attempt_count') != 55 or audit.get('suffix_valid_count') != 55 or
            (audit.get('suffix_first_id'), audit.get('suffix_last_id')) != ('DEV-006', 'DEV-060') or
            audit.get('child_snapshot_sha256') != sha(SNAPSHOT) or
            audit.get('execution_manifest_sha256') != sha(PREDECESSOR_PLAN / 'manifest.json') or
            audit.get('composite_unknown_cost_ids') != ['DEV-005'] or
            parent.get('partition_reconciled', {}).get('unknown_upper_bound_usd') !=
                str(old.proposal.RESERVE) or
            interrupted.get('unknown_cost_ids') != ['DEV-005'] or
            interrupted.get('next_unsent_id') != 'DEV-006' or
            reconciliation.get('event') != 'partition_reconciled' or
            reconciliation.get('partition_id') != 'deepseek-low-remaining6-successor-v1' or
            reconciliation.get('child_sha256') != 'd5ceee322e0367aac273fcfde755a10748425a411d0441923ff2a59bf9030e1e' or
            Decimal(reconciliation.get('unknown_upper_bound_usd', '-1')) != 0 or
            Decimal(reconciliation.get('known_actual_usd', '-1')) !=
                Decimal(audit['child_known_actual_usd']) or
            Decimal(reconciliation.get('unused_allocation_released_usd', '-1')) !=
                Decimal(audit['expected_child_unused_usd'])):
        raise ValueError('Sealed predecessor or retained DEV-005 bound differs')
    if len(ledger) != 117 or ledger[0] != {'event': 'budget', 'cap_usd': '0.35'}:
        raise ValueError('Predecessor ledger snapshot differs')
    reserves, settlements = {}, {}
    for row in ledger[1:]:
        aid = row.get('attempt_id')
        if row.get('event') == 'reserve':
            if aid in reserves or Decimal(row.get('usd', '-1')) != old.proposal.RESERVE:
                raise ValueError('Predecessor reserve differs')
            reserves[aid] = row
        elif row.get('event') == 'settle':
            if aid in settlements or aid not in reserves or Decimal(row.get('usd', '-1')) < 0 or \
                    Decimal(row['usd']) > old.proposal.RESERVE:
                raise ValueError('Predecessor settlement differs')
            settlements[aid] = row
        else:
            raise ValueError('Unexpected predecessor ledger event')
    if (len(reserves) != 58 or set(reserves) != set(settlements) or
            sum((Decimal(row['usd']) for row in settlements.values()), Decimal()) !=
                Decimal(reconciliation['known_actual_usd']) or
            Decimal(reconciliation['known_actual_usd']) +
                Decimal(reconciliation['unused_allocation_released_usd']) != Decimal('0.35')):
        raise ValueError('Predecessor child settlement does not reconcile')
    return audit


def proposal_data(*, require_unclaimed=False):
    audit = predecessor_closed()
    plans = {repeat: json.loads((PREDECESSOR_PLAN / repeat / 'manifest.json').read_text())
             for repeat in ('fresh2', 'fresh3')}
    execution = json.loads((PREDECESSOR_PLAN / 'manifest.json').read_text())
    if (execution.get('plans_sha256') != {repeat: sha(PREDECESSOR_PLAN / repeat / 'manifest.json')
                                          for repeat in plans} or
            audit.get('successor_proposal_sha256') != sha(PREDECESSOR_PROPOSAL) or
            any(plan.get('configuration_id') != old.proposal.CONFIG or
                plan.get('model') != old.proposal.old.MODEL or
                plan.get('provider_tag') != old.proposal.old.PROVIDER or
                plan.get('reasoning_effort') != 'low' or
                plan.get('public_route_sha256') != sha(old.proposal.ROUTE) or
                plan.get('source_proposal_sha256') != sha(old.proposal.MANIFEST) or
                plan.get('source_successor_sha256') != sha(PREDECESSOR_PROPOSAL)
                for plan in plans.values())):
        raise ValueError('Frozen low plan provenance or route differs')
    if (plans['fresh2']['condition_order'] != ['P2', 'P0', 'P1'] or
            plans['fresh3']['condition_order'] != ['P1', 'P2', 'P0']):
        raise ValueError('Frozen phase order differs')
    p2 = plans['fresh2']['conditions']['P2']['development']
    if ([row['record_id'] for row in p2] != [f'DEV-{n:03}' for n in range(6, 61)] or
            audit['development_closure']['manifest_sha256'] !=
                sha(PREDECESSOR_PLAN / 'fresh2/manifest.json')):
        raise ValueError('Sealed P2 successor membership differs')
    for repeat, condition in PHASES:
        plan = plans[repeat]
        rows = plan['conditions'][condition]['development']
        smoke = plan['conditions'][condition]['smoke']
        if (len(rows) != 60 or tuple(row['record_id'] for row in rows) != NO_RETRY or
                smoke != rows[:3] or
                any(row['position'] != index or
                    old.proposal.digest(json.dumps(row['payload'], sort_keys=True)) != row['request_sha256']
                    for index, row in enumerate(rows))):
            raise ValueError('Frozen full-phase payload identity differs')
        folder = PREDECESSOR_PLAN / repeat / condition
        if require_unclaimed and any((folder / (phase + '.claim.json')).exists()
                                     for phase in ('smoke', 'development')):
            raise ValueError('Proposed low phase was already claimed')
    paths = (AUDIT, SNAPSHOT, RECONCILIATION, PARENT_RECONCILIATION,
             PARENT_INTERRUPTION, PREDECESSOR_PROPOSAL, PREDECESSOR_PLAN / 'manifest.json',
             PREDECESSOR_PLAN / 'fresh2/manifest.json',
             PREDECESSOR_PLAN / 'fresh3/manifest.json', old.proposal.ROUTE,
             old.proposal.MANIFEST, old.MANIFEST,
             ROOT / 'scripts/deepseek_low_remaining5_v4.py',
             ROOT / 'tests/test_deepseek_low_remaining5_v4.py')
    return {'schema': SCHEMA, 'status': 'offline_proposal_unadmitted',
        'configuration_id': old.proposal.CONFIG,
        'predecessor_stage': 'fresh2/P2/development',
        'predecessor_suffix_closed': True,
        'predecessor_composite_clean_full_phase': False,
        'predecessor_unknown_cost_id': 'DEV-005',
        'predecessor_unknown_cost_upper_bound_usd': str(old.proposal.RESERVE),
        'no_retry_predecessor_ids': list(NO_RETRY),
        'remaining_phase_order': [{'fresh_pass': repeat, 'condition': condition}
                                  for repeat, condition in PHASES],
        'phase_request_sha256': {f'{repeat}/{condition}':
            [row['request_sha256'] for row in plans[repeat]['conditions'][condition]['development']]
            for repeat, condition in PHASES},
        'authority_reader_required': 'openrouter-authority-release-v4',
        'new_child_partition_id': None, 'new_child_cap_usd': None,
        'route_and_request_readmission_required': True,
        'allocation_authorized': False, 'dispatch_authorized': False,
        'source_bindings': {relative(path): sha(path) for path in paths}}


def prepare():
    value = proposal_data(require_unclaimed=True)
    BASE.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=BASE, prefix='.proposal-',
                                     delete=False) as handle:
        staged = Path(handle.name)
        json.dump(value, handle, indent=2)
        handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
    try:
        os.link(staged, MANIFEST)
    finally:
        staged.unlink()
    return sha(MANIFEST)


def verify():
    saved = json.loads(MANIFEST.read_text())
    for name, digest in saved['source_bindings'].items():
        if sha(ROOT / name) != digest:
            raise ValueError('Bound source changed: ' + name)
    if saved != proposal_data():
        raise ValueError('Low remaining-five proposal differs from sealed source')
    return sha(MANIFEST)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify'))
    args = parser.parse_args()
    print(prepare() if args.action == 'prepare' else verify())


if __name__ == '__main__':
    main()
