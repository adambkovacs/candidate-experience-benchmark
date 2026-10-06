#!/usr/bin/env python3
"""Offline proposal for the exact unsent DeepSeek high price-v1 work."""
import argparse
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import tempfile

import deepseek_high_remaining7_execution_v1 as old
import build_deepseek_high_remaining7_price_findings as report

ROOT = old.study.ROOT
BASE = old.proposal.BASE / 'unsent-continuation-v1'
MANIFEST = BASE / 'proposal.json'
RECONCILIATION = old.proposal.BASE / 'reconciliation-after-dev027.json'
INTERRUPTION = old.BASE / 'fresh2/P2/interruption.audit.json'
UNKNOWN_EVIDENCE = old.BASE / 'fresh2/P2/interruption-unknown-cost-evidence.jsonl'
SNAPSHOT = old.BASE / 'fresh2/P2/interruption-child-ledger-snapshot.jsonl'
CHILD = old.CHILD_LEDGER
SCHEMA = 'deepseek-high-remaining6-price-v1-unsent-continuation-v1'
PHASES = (('fresh2', 'P2'), ('fresh2', 'P0'), ('fresh2', 'P1'),
          ('fresh3', 'P1'), ('fresh3', 'P2'), ('fresh3', 'P0'))
UNSENT = [f'DEV-{n:03d}' for n in range(28, 61)]
NO_RETRY = [f'DEV-{n:03d}' for n in range(1, 28)]
BOUND = Decimal('0.06905856')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relative(path):
    return str(Path(path).resolve().relative_to(ROOT.resolve()))


def proposal_data(*, require_unclaimed=False):
    receipt = json.loads(RECONCILIATION.read_text())
    audit = json.loads(INTERRUPTION.read_text())
    unknown = json.loads(UNKNOWN_EVIDENCE.read_text())
    child = [json.loads(line) for line in CHILD.read_text().splitlines() if line.strip()]
    reserves = {row['attempt_id']: Decimal(row['usd']) for row in child
                if row['event'] == 'reserve'}
    settled = {row['attempt_id']: Decimal(row['usd']) for row in child
               if row['event'] == 'settle'}
    unknown_rows = {row['attempt_id']: Decimal(row['usd']) for row in child
                    if row['event'] == 'unknown_cost_accounted_as_upper_bound'}
    if (receipt.get('event') != 'partition_reconciled' or
            receipt.get('partition_id') != old.proposal.PARTITION_ID or
            receipt.get('child_sha256') != sha(CHILD) or
            Decimal(receipt.get('unknown_upper_bound_usd', '-1')) != BOUND or
            Decimal(receipt.get('known_actual_usd', '-1')) != Decimal('0.047026223585') or
            audit.get('schema') != 'deepseek-high-remaining7-fresh2-p2-interruption-audit-v1' or
            audit.get('configuration_id') != old.proposal.CONFIG or
            audit.get('status') != 'stopped_no_full_phase_score' or
            audit.get('attempted') != 27 or audit.get('valid_saved') != 26 or
            audit.get('child_ledger_snapshot_sha256') != sha(SNAPSHOT) or
            audit.get('unknown_cost_evidence_sha256') != sha(UNKNOWN_EVIDENCE) or
            audit.get('failed') != [{'id': 'DEV-027',
                'attempt_id': unknown.get('attempt_id'), 'status': 'service_error',
                'http_status': 429, 'cost_unknown': True,
                'reserved_upper_bound_usd': str(BOUND)}] or
            unknown.get('id') != 'DEV-027' or unknown.get('cost_unknown') is not True or
            Decimal(unknown.get('reserved_cost_usd', '-1')) != BOUND or
            child[-1].get('event') != 'partition_closed' or
            child[-2].get('event') != 'unknown_cost_accounted_as_upper_bound' or
            child[-2].get('attempt_id') != unknown['attempt_id'] or
            Decimal(child[-2].get('usd', '-1')) != BOUND or
            len(reserves) != len([row for row in child if row['event'] == 'reserve']) or
            len(settled) != len([row for row in child if row['event'] == 'settle']) or
            set(reserves) != set(settled) | set(unknown_rows) or
            any(value > reserves[key] for key, value in {**settled, **unknown_rows}.items()) or
            sum(settled.values(), Decimal()) != Decimal(receipt['known_actual_usd']) or
            sum(unknown_rows.values(), Decimal()) != BOUND):
        raise ValueError('Sealed high interruption or unknown-cost accounting differs')
    if (audit['source_sha256'].get('manifest.json') !=
            sha(old.BASE / 'fresh2/manifest.json') or
            unknown.get('source_attempts_sha256') !=
            audit['source_sha256'].get('development.attempts.jsonl')):
        raise ValueError('Sealed high interruption source hashes differ')
    plan = report.portable_plan('fresh2', sha(old.BASE / 'fresh2/manifest.json'))
    remaining = plan['conditions']['P2']['development'][27:]
    if ([row['record_id'] for row in remaining] != UNSENT or
            audit['unsent'] != [{'id': row['record_id'],
                'request_sha256': row['request_sha256'],
                'input_sha256': row['input_sha256'],
                'instruction_sha256': row['instruction_sha256']}
                for row in remaining]):
        raise ValueError('High unsent request identity or order differs')
    for repeat, condition in PHASES[1:]:
        plan = report.portable_plan(repeat, sha(old.BASE / repeat / 'manifest.json'))
        if condition not in plan['conditions']:
            raise ValueError('Later high stage missing from frozen plan')
        folder = old.BASE / repeat / condition
        if require_unclaimed and any((folder / (phase + '.claim.json')).exists()
                                     for phase in ('smoke', 'development')):
            raise ValueError('Later high stage already claimed')
    sources = [old.proposal.MANIFEST, old.proposal.ROUTE, old.MANIFEST,
               old.BASE / 'fresh2/manifest.json', old.BASE / 'fresh3/manifest.json',
               RECONCILIATION, INTERRUPTION, UNKNOWN_EVIDENCE, SNAPSHOT, CHILD,
               ROOT / 'scripts/deepseek_high_remaining6_successor_v1.py',
               ROOT / 'tests/test_deepseek_high_remaining6_successor_v1.py']
    return {'schema': SCHEMA, 'status': 'offline_proposal_unadmitted',
            'source_configuration_id': old.proposal.CONFIG,
            'interrupted_stage': 'fresh2/P2/development',
            'predecessor_child_closed': True,
            'predecessor_unknown_cost_id': 'DEV-027',
            'predecessor_unknown_cost_upper_bound_usd': str(BOUND),
            'no_retry_ids': NO_RETRY, 'first_unsent_id': UNSENT[0],
            'development_suffix_ids': UNSENT,
            'development_suffix_request_sha256':
                [row['request_sha256'] for row in remaining],
            'later_phase_order': [{'fresh_pass': repeat, 'condition': condition}
                                  for repeat, condition in PHASES[1:]],
            'new_child_partition_id': None, 'new_child_cap_usd': None,
            'authority_reader_required': 'openrouter-authority-release-v4',
            'v4_transition_and_available_capacity_required': True,
            'route_and_request_readmission_required': True,
            'continuation_execution_adapter_admitted': False,
            'allocation_authorized': False, 'dispatch_authorized': False,
            'source_bindings': {relative(path): sha(path) for path in sources}}


def prepare():
    value = proposal_data(require_unclaimed=True)
    BASE.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=BASE, prefix='.proposal-',
                                     delete=False) as handle:
        staged = Path(handle.name)
        json.dump(value, handle, indent=2)
        handle.write('\n')
        handle.flush(); os.fsync(handle.fileno())
    try:
        os.link(staged, MANIFEST)
    finally:
        staged.unlink()
    return sha(MANIFEST)


def verify():
    saved = json.loads(MANIFEST.read_text())
    if saved != proposal_data():
        raise ValueError('High successor proposal differs from sealed source')
    return sha(MANIFEST)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify'))
    args = parser.parse_args()
    print(prepare() if args.action == 'prepare' else verify())


if __name__ == '__main__':
    main()
