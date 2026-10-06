#!/usr/bin/env python3
"""Freeze an unadmitted low-v2 continuation after the sealed DEV-005 child."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

import deepseek_low_remaining6_execution_v1 as adapter

ROOT = adapter.ROOT
BASE = adapter.proposal.BASE / 'unsent-continuation-v1'
MANIFEST = BASE / 'proposal.json'
RECONCILIATION = adapter.proposal.BASE / 'reconciliation-after-dev005.json'
INTERRUPTION = adapter.proposal.BASE / 'fresh2-p2-dev005-interruption.audit-candidate.json'
SANITIZED = adapter.proposal.BASE / 'dev005-unknown-sanitized-evidence.json'
CHILD = adapter.CHILD_LEDGER
SCHEMA = 'deepseek-low-remaining6-price-v2-unsent-continuation-v1'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relative(path):
    return str(Path(path).resolve().relative_to(ROOT.resolve()))


def proposal_data():
    adapter.verify()
    receipt = json.loads(RECONCILIATION.read_text())
    interruption = json.loads(INTERRUPTION.read_text())
    sanitized = json.loads(SANITIZED.read_text())
    child = [json.loads(line) for line in CHILD.read_text().splitlines()]
    if (receipt.get('schema') != 'deepseek-low-remaining6-price-v2-dev005-reconciliation-v1' or
            receipt.get('configuration_id') != adapter.proposal.CONFIG or
            receipt.get('stage') != 'fresh2/P2/development' or
            receipt.get('source_interruption_candidate_sha256') != sha(INTERRUPTION) or
            receipt.get('child_ledger_sha256') != sha(CHILD) or
            receipt.get('source_interruption_ledger_snapshot_sha256') !=
                interruption['private_evidence_bindings'][str(
                    (adapter.BASE / 'fresh2/P2/interruption-ledger-snapshot.jsonl').relative_to(ROOT))] or
            interruption.get('terminal_phase_completed') is not False or
            interruption.get('completed_score') is not None or
            interruption.get('unknown_cost_ids') != ['DEV-005'] or
            interruption.get('next_unsent_id') != 'DEV-006' or
            interruption.get('continuation', {}).get('dispatch_authorized') is not False or
            sanitized.get('source_attempts_snapshot_sha256') !=
                receipt.get('source_attempts_snapshot_sha256') or
            sanitized.get('unknown_attempt', {}).get('attempt_id') !=
                receipt.get('unknown_attempt_id')):
        raise ValueError('Closed low interruption source differs')
    reconciled = receipt['partition_reconciled']
    unknown = receipt['unknown_cost_accounted_as_upper_bound']
    if (reconciled.get('partition_id') != adapter.proposal.PARTITION_ID or
            reconciled.get('child_sha256') != sha(CHILD) or
            reconciled.get('known_actual_usd') != '0.0021672585' or
            reconciled.get('unknown_upper_bound_usd') != '0.06905856' or
            reconciled.get('unused_allocation_released_usd') != '0.6787741815' or
            unknown.get('event') != 'unknown_cost_accounted_as_upper_bound' or
            unknown.get('attempt_id') != receipt['unknown_attempt_id'] or
            unknown.get('usd') != '0.06905856' or
            unknown.get('actual_cost_usd') is not None or
            child[-1].get('event') != 'partition_closed' or
            child[-2] != unknown):
        raise ValueError('Low child is not sealed with full unknown bound')
    plan = adapter.verify_plan('fresh2', sha(adapter.BASE / 'fresh2/manifest.json'))
    requests = plan['conditions']['P2']['development']
    unsent = interruption['unsent_ids']
    hashes = interruption['continuation']['request_sha256']
    if (unsent != [f'DEV-{n:03}' for n in range(6, 61)] or
            len(hashes) != len(unsent) or
            [row['record_id'] for row in requests[5:]] != unsent or
            [row['request_sha256'] for row in requests[5:]] != hashes or
            interruption['continuation'].get('no_retry_ids') !=
                [f'DEV-{n:03}' for n in range(1, 6)]):
        raise ValueError('Low unsent successor membership differs')
    sources = [adapter.proposal.MANIFEST, adapter.proposal.ROUTE,
               adapter.MANIFEST, adapter.BUDGET,
               adapter.BASE / 'fresh2/manifest.json',
               adapter.BASE / 'fresh3/manifest.json',
               RECONCILIATION, INTERRUPTION, SANITIZED, CHILD,
               adapter.BASE / 'fresh2/P2/interruption-ledger-snapshot.jsonl',
               ROOT / 'scripts/deepseek_low_remaining6_successor_v1.py',
               ROOT / 'tests/test_deepseek_low_remaining6_successor_v1.py']
    bindings = {relative(path): sha(path) for path in sources}
    return {'schema': SCHEMA, 'status': 'offline_proposal_unadmitted',
            'source_configuration_id': adapter.proposal.CONFIG,
            'interrupted_stage': 'fresh2/P2/development',
            'predecessor_child_closed': True,
            'predecessor_unknown_cost_id': 'DEV-005',
            'predecessor_unknown_cost_upper_bound_usd': '0.06905856',
            'no_retry_ids': [f'DEV-{n:03}' for n in range(1, 6)],
            'first_unsent_id': 'DEV-006',
            'development_suffix_ids': unsent,
            'development_suffix_request_sha256': hashes,
            'later_phase_order': [{'fresh_pass': repeat, 'condition': condition}
                                  for repeat, condition in adapter.PHASES[1:]],
            'new_child_partition_id': None,
            'new_child_cap_usd': None,
            'global_authority_review_required': True,
            'route_and_request_readmission_required': True,
            'continuation_execution_adapter_admitted': False,
            'allocation_authorized': False,
            'dispatch_authorized': False,
            'source_bindings': bindings}


def prepare():
    value = proposal_data()
    BASE.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=BASE, prefix='.proposal-',
                                     delete=False) as handle:
        staged = Path(handle.name)
        json.dump(value, handle, indent=2)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.link(staged, MANIFEST)
    finally:
        staged.unlink()
    return sha(MANIFEST)


def verify():
    saved = json.loads(MANIFEST.read_text())
    if saved != proposal_data():
        raise ValueError('Low successor proposal differs from sealed source')
    return sha(MANIFEST)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify'))
    args = parser.parse_args()
    print(prepare() if args.action == 'prepare' else verify())


if __name__ == '__main__':
    main()
