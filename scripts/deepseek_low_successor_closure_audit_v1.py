#!/usr/bin/env python3
"""Read-only closure audit of DeepSeek low DEV-006–060 successor."""
import argparse
from decimal import Decimal
import json
from pathlib import Path

import deepseek_low_remaining6_successor_execution_v1 as execution

BASE = execution.successor.BASE
SNAPSHOT = BASE / 'closure-ledger-snapshot-after-dev060.jsonl'
RECEIPT = BASE / 'fresh2-p2-suffix-closure-audit.json'
PUBLIC = BASE / 'fresh2-p2-composite-public.json'
SOURCE = execution.ROOT / 'scripts/deepseek_low_successor_closure_audit_v1.py'


def jsonl(path):
    raw = Path(path).read_bytes()
    if not raw.endswith(b'\n'):
        raise ValueError('Incomplete low successor JSONL')
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def value():
    execution.verify(); execution.require_review(); execution.exact_budget_entry()
    execution.successor.verify()
    plan = execution.verify_plan('fresh2', execution.sha(execution.BASE / 'fresh2/manifest.json'))
    core = execution.repaired_core()
    smoke = core.verify_phase_closure(plan, 'P2', 'smoke')
    development = core.verify_phase_closure(plan, 'P2', 'development')
    stage = execution.BASE / 'fresh2/P2'
    smoke_attempts = jsonl(stage / 'smoke.attempts.jsonl')
    dev_attempts = jsonl(stage / 'development.attempts.jsonl')
    if ([r['id'] for r in smoke_attempts] != [f'DEV-{i:03}' for i in (6, 7, 8)] or
            [r['id'] for r in dev_attempts] != [f'DEV-{i:03}' for i in range(6, 61)] or
            any(r.get('status') != 'ok' or r.get('billing_ok') is not True or
                r.get('cost_unknown') is not False for r in smoke_attempts + dev_attempts)):
        raise ValueError('Exact low successor smoke/development members differ')
    ledger = jsonl(SNAPSHOT)
    if len(ledger) != 117 or ledger[0] != {'event': 'budget', 'cap_usd': str(execution.CHILD_CAP)}:
        raise ValueError('Low successor ledger snapshot length/cap differs')
    known = Decimal(0)
    for i, attempt in enumerate(smoke_attempts + dev_attempts):
        reserve, settle = ledger[1 + 2*i:3 + 2*i]
        cost = Decimal(attempt['observed_cost_usd'])
        if (reserve.get('event') != 'reserve' or reserve.get('attempt_id') != attempt['attempt_id'] or
                reserve.get('record_id') != attempt['id'] or
                Decimal(reserve.get('usd')) != execution.prior.proposal.RESERVE or
                settle.get('event') != 'settle' or settle.get('attempt_id') != attempt['attempt_id'] or
                Decimal(settle['usd']) != cost):
            raise ValueError('Low successor ledger settlement differs from exact attempts')
        known += cost
    prior = json.loads(execution.successor.RECONCILIATION.read_text())
    parent = json.loads(execution.successor.INTERRUPTION.read_text())
    reconciliation = prior['partition_reconciled']
    if (parent['known_valid_prefix_ids'] != [f'DEV-{i:03}' for i in range(1,5)] or
            parent['unknown_cost_ids'] != ['DEV-005'] or parent['terminal_phase_completed'] is not False or
            reconciliation['known_actual_usd'] != parent['known_child_settled_usd'] or
            reconciliation['unknown_upper_bound_usd'] != parent['unknown_reserved_usd'] or
            Decimal(parent['unknown_reserved_usd']) != execution.prior.proposal.RESERVE):
        raise ValueError('Low interrupted parent cannot support descriptive composite')
    return {'schema': 'deepseek-low-successor-fresh2-p2-closure-audit-v1',
            'status': 'suffix_closed_composite_interrupted', 'clean_full_phase': False,
            'configuration_id': execution.prior.proposal.CONFIG, 'fresh_pass': 'fresh2', 'condition': 'P2',
            'source_audit_sha256': execution.sha(SOURCE),
            'execution_manifest_sha256': execution.sha(execution.MANIFEST),
            'successor_proposal_sha256': execution.sha(execution.successor.MANIFEST),
            'parent_interruption_sha256': execution.sha(execution.successor.INTERRUPTION),
            'parent_reconciliation_sha256': execution.sha(execution.successor.RECONCILIATION),
            'child_snapshot_sha256': execution.sha(SNAPSHOT),
            'smoke_closure': smoke, 'development_closure': development,
            'smoke_attempt_count': 3, 'smoke_known_actual_usd': str(sum((Decimal(r['observed_cost_usd']) for r in smoke_attempts),Decimal(0))),
            'suffix_first_id': 'DEV-006', 'suffix_last_id': 'DEV-060',
            'suffix_attempt_count': 55, 'suffix_valid_count': 55,
            'suffix_known_actual_usd': str(sum((Decimal(r['observed_cost_usd']) for r in dev_attempts),Decimal(0))),
            'child_known_actual_usd': str(known), 'child_unknown_upper_bound_usd': '0',
            'child_cap_usd': str(execution.CHILD_CAP),
            'expected_child_unused_usd': str(execution.CHILD_CAP-known),
            'composite_development_attempt_count': 60,
            'composite_known_valid_count': 59,
            'composite_unknown_cost_ids': ['DEV-005'],
            'composite_parent_known_usd': parent['known_child_settled_usd'],
            'composite_parent_unknown_upper_bound_usd': parent['unknown_reserved_usd'],
            'composite_known_development_usd': str(Decimal(parent['known_child_settled_usd'])+
                                                   sum((Decimal(r['observed_cost_usd']) for r in dev_attempts),Decimal(0))),
            'full_60_clean_score': None,
            'stage_evidence_sha256': {str((stage/name).relative_to(execution.ROOT)): execution.sha(stage/name)
                for name in ('development.claim.json', 'development.journal.jsonl',
                             'development.attempts.jsonl', 'development.responses.jsonl',
                             'smoke.claim.json', 'smoke.journal.jsonl',
                             'smoke.attempts.jsonl', 'smoke.responses.jsonl')}}


def public(receipt):
    return {k: receipt[k] for k in ('schema','status','clean_full_phase','configuration_id',
            'fresh_pass','condition','suffix_attempt_count','suffix_valid_count',
            'suffix_known_actual_usd','composite_development_attempt_count',
            'composite_known_valid_count','composite_unknown_cost_ids',
            'composite_known_development_usd','composite_parent_unknown_upper_bound_usd',
            'full_60_clean_score')}


def prepare():
    receipt = value()
    with RECEIPT.open('x') as out: out.write(json.dumps(receipt,indent=2)+'\n')
    with PUBLIC.open('x') as out: out.write(json.dumps(public(receipt),indent=2)+'\n')
    return execution.sha(RECEIPT)


def verify():
    receipt = value()
    if json.loads(RECEIPT.read_text()) != receipt or json.loads(PUBLIC.read_text()) != public(receipt):
        raise ValueError('Low successor closure artifacts differ')
    return execution.sha(RECEIPT)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation',choices=('prepare','verify'))
    args=parser.parse_args()
    print(prepare() if args.operation=='prepare' else verify())


if __name__=='__main__': main()
