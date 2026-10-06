#!/usr/bin/env python3
"""Offline proposal for the never-sent low P1 tail and three fresh3 phases."""
import argparse
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import tempfile

import deepseek_low_remaining5_v4_execution as old

ROOT = old.ROOT
BASE = old.successor.BASE / 'p1-dev028-continuation-v1'
MANIFEST = BASE / 'proposal.json'
AUDIT = old.BASE / 'fresh2/P1/terminal-audit.json'
SNAPSHOT = old.BASE / 'fresh2/P1/terminal-ledger-snapshot.jsonl'
ATTEMPTS = old.BASE / 'fresh2/P1/development.attempts.jsonl'
RESPONSES = old.BASE / 'fresh2/P1/development.responses.jsonl'
JOURNAL = old.BASE / 'fresh2/P1/development.journal.jsonl'
RECONCILIATION = old.successor.BASE / 'reconciliation-after-dev027.json'
CHILD = old.CHILD_LEDGER
CLOSED = BASE / 'predecessor-closed-ledger-snapshot.jsonl'
SCHEMA = 'deepseek-low-p1-dev028-continuation-v1'
PHASES = (('fresh2', 'P1'), ('fresh3', 'P1'), ('fresh3', 'P2'), ('fresh3', 'P0'))
NO_RETRY = [f'DEV-{n:03}' for n in range(1, 28)]
UNSENT = [f'DEV-{n:03}' for n in range(28, 61)]
BOUND = Decimal('0.06905856')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relative(path):
    return str(Path(path).resolve().relative_to(ROOT.resolve()))


def rows(path):
    raw = Path(path).read_bytes()
    if not raw.endswith(b'\n'):
        raise ValueError('Incomplete predecessor evidence')
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def predecessor_closed():
    audit = json.loads(AUDIT.read_text())
    receipt = json.loads(RECONCILIATION.read_text())
    event = receipt['partition_reconciled']
    ledger = rows(CLOSED)
    terminal_ledger = rows(SNAPSHOT)
    plan = json.loads((old.BASE / 'fresh2/manifest.json').read_text())
    if (audit.get('schema') != 'deepseek-low-remaining5-v4-fresh2-p1-interruption-audit-v1' or
            audit.get('status') != 'interrupted_no_full_phase_score' or
            audit.get('attempted_ids') != NO_RETRY or
            audit.get('unsent_ids') != UNSENT or
            audit.get('valid_outputs') != 25 or
            audit.get('intrinsic_invalid_outputs') != 1 or
            audit.get('provider_failures') != 1 or
            audit.get('full_phase_score') is not None or
            audit.get('intrinsic_invalid', {}).get('id') != 'DEV-006' or
            audit.get('intrinsic_invalid', {}).get('finish_reason') != 'length' or
            audit.get('terminal_failure', {}).get('id') != 'DEV-027' or
            audit.get('terminal_failure', {}).get('http_status') != 503 or
            audit.get('terminal_failure', {}).get('cost_unknown') is not True or
            Decimal(audit['terminal_failure']['retained_reservation_usd']) != BOUND or
            audit.get('plan_sha256') != sha(old.BASE / 'fresh2/manifest.json') or
            audit.get('execution_manifest_sha256') != sha(old.MANIFEST) or
            audit.get('terminal_ledger_snapshot_sha256') != sha(SNAPSHOT) or
            ledger[:len(terminal_ledger)] != terminal_ledger or
            terminal_ledger[-1].get('event') != 'reserve' or
            terminal_ledger[-1].get('record_id') != 'DEV-027' or
            receipt.get('terminal_audit_sha256') != sha(AUDIT) or
            event.get('event') != 'partition_reconciled' or
            event.get('partition_id') != old.PARTITION_ID or
            event.get('child_sha256') != sha(CLOSED) or
            Decimal(event.get('known_actual_usd', '-1')) != Decimal('0.047458652852') or
            Decimal(event.get('unknown_upper_bound_usd', '-1')) != BOUND or
            Decimal(event.get('unused_allocation_released_usd', '-1')) !=
                old.CHILD_CAP - Decimal(event['known_actual_usd']) - BOUND):
        raise ValueError('Stopped low P1 or sealed child differs')
    raw_paths = (ATTEMPTS, RESPONSES, JOURNAL)
    if any(path.exists() for path in raw_paths):
        if not all(path.exists() for path in raw_paths):
            raise ValueError('Partial local predecessor raw evidence')
        for name, digest in audit['evidence_sha256'].items():
            if sha(old.BASE / 'fresh2/P1' / name) != digest:
                raise ValueError('Stopped low P1 evidence hash differs')
        attempts = rows(ATTEMPTS)
        if [row.get('id') for row in attempts] != NO_RETRY or len(attempts) != 27:
            raise ValueError('Predecessor attempt membership differs')
        failed = attempts[-1]
        if (failed.get('cost_unknown') is not True or
                Decimal(failed.get('reserved_cost_usd', '-1')) != BOUND or
                attempts[5].get('id') != 'DEV-006' or
                attempts[5].get('status') == 'ok' or
                attempts[5].get('cost_unknown') is not False):
            raise ValueError('Predecessor invalid or unknown outcome differs')
        failed_attempt_id = failed['attempt_id']
    else:
        failed_attempt_id = terminal_ledger[-1]['attempt_id']
    if CHILD.exists() and sha(CHILD) != sha(CLOSED):
        raise ValueError('Local sealed child differs from archived snapshot')
    reserves = {row['attempt_id']: Decimal(row['usd']) for row in ledger
                if row['event'] == 'reserve'}
    settled = {row['attempt_id']: Decimal(row['usd']) for row in ledger
               if row['event'] == 'settle'}
    unknown = {row['attempt_id']: Decimal(row['usd']) for row in ledger
               if row['event'] == 'unknown_cost_accounted_as_upper_bound'}
    if (ledger[-1].get('event') != 'partition_closed' or
            set(reserves) != set(settled) | set(unknown) or
            set(settled) & set(unknown) or
            unknown != {failed_attempt_id: BOUND} or
            sum(settled.values(), Decimal()) != Decimal(event['known_actual_usd']) or
            len(reserves) != 93 or len(settled) != 92 or
            any(value > reserves[key] for key, value in {**settled, **unknown}.items()) or
            sha(old.BASE / 'fresh2/P1/terminal-ledger-snapshot.jsonl') !=
                audit['terminal_ledger_snapshot_sha256']):
        raise ValueError('Predecessor ledger ancestry differs')
    frozen = plan['conditions']['P1']['development']
    if ([row['record_id'] for row in frozen[:27]] != NO_RETRY or
            [row['request_sha256'] for row in frozen[:27]] != audit['frozen_request_sha256'] or
            [row['record_id'] for row in frozen[27:]] != UNSENT):
        raise ValueError('Predecessor request inventory differs')
    return audit, plan


def proposal_data(*, require_unclaimed=False):
    audit, plan = predecessor_closed()
    later = json.loads((old.BASE / 'fresh3/manifest.json').read_text())
    if plan['condition_order'] != ['P0', 'P1'] or later['condition_order'] != ['P1', 'P2', 'P0']:
        raise ValueError('Frozen remaining phase order differs')
    for condition in ('P1', 'P2', 'P0'):
        dev = later['conditions'][condition]['development']
        if ([row['record_id'] for row in dev] != [f'DEV-{n:03}' for n in range(1, 61)] or
                later['conditions'][condition]['smoke'] != dev[:3]):
            raise ValueError('Fresh3 frozen request membership differs')
        if require_unclaimed:
            folder = old.BASE / 'fresh3' / condition
            if any((folder / (phase + '.claim.json')).exists() for phase in ('smoke', 'development')):
                raise ValueError('Fresh3 predecessor already claimed')
    paths = (AUDIT, SNAPSHOT, RECONCILIATION, CLOSED,
             old.MANIFEST, old.BASE / 'fresh2/manifest.json',
             old.BASE / 'fresh3/manifest.json', old.successor.MANIFEST,
             old.prior.prior.proposal.ROUTE,
             ROOT / 'scripts/deepseek_low_p1_dev028_successor_v1.py',
             ROOT / 'tests/test_deepseek_low_p1_dev028_successor_v1.py')
    return {'schema': SCHEMA, 'status': 'offline_proposal_unadmitted',
        'configuration_id': old.prior.prior.proposal.CONFIG,
        'interrupted_stage': 'fresh2/P1/development',
        'predecessor_child_closed': True,
        'predecessor_known_actual_usd': '0.047458652852',
        'predecessor_unknown_cost_id': 'DEV-027',
        'predecessor_unknown_cost_upper_bound_usd': str(BOUND),
        'predecessor_intrinsic_invalid_id': 'DEV-006',
        'no_retry_ids': NO_RETRY, 'development_suffix_ids': UNSENT,
        'development_suffix_request_sha256':
            [row['request_sha256'] for row in plan['conditions']['P1']['development'][27:]],
        'later_phase_order': [{'fresh_pass': repeat, 'condition': condition}
                              for repeat, condition in PHASES[1:]],
        'later_phase_request_sha256': {f'fresh3/{condition}':
            [row['request_sha256'] for row in later['conditions'][condition]['development']]
            for condition in ('P1', 'P2', 'P0')},
        'clean_full_p1_score': None,
        'authority_reader_required': 'openrouter-authority-release-v4',
        'new_child_partition_id': None, 'new_child_cap_usd': None,
        'route_and_request_readmission_required': True,
        'allocation_authorized': False, 'dispatch_authorized': False,
        'source_bindings': {relative(path): sha(path) for path in paths}}


def prepare():
    value = proposal_data(require_unclaimed=True)
    BASE.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=BASE, prefix='.proposal-', delete=False) as handle:
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
            raise ValueError('Bound successor source changed: ' + name)
    if saved != proposal_data():
        raise ValueError('Low P1 successor proposal differs')
    return sha(MANIFEST)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify'))
    args = parser.parse_args()
    print(prepare() if args.action == 'prepare' else verify())


if __name__ == '__main__':
    main()
