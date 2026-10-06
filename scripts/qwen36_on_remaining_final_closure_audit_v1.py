#!/usr/bin/env python3
"""Read-only audit of the final hosted Qwen fresh3/P1 phase and child snapshot."""
import argparse
from decimal import Decimal
import json
from pathlib import Path

import qwen36_on_remaining_hosted_v1 as q

SNAPSHOT = q.BASE / 'budget-at-fresh3-p1-closure.jsonl'
RECEIPT = q.BASE / 'fresh3-p1-final-closure-audit.json'
SOURCE = q.ROOT / 'scripts/qwen36_on_remaining_final_closure_audit_v1.py'


def rows(path):
    raw = Path(path).read_bytes()
    if not raw.endswith(b'\n'):
        raise ValueError('Incomplete Qwen JSONL')
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def value():
    q.verify(q.study.sha(q.EXECUTION))
    plan = json.loads(q.plan_path('fresh3').read_text())
    bindings = q.private_runner().verify_phase_closure(plan, 'P1', 'development')
    stage = q.BASE / q.parent.CONFIG / 'fresh3/P1'
    attempts = rows(stage / 'development.attempts.jsonl')
    if (len(attempts) != 60 or [x['id'] for x in attempts] != [f'DEV-{i:03}' for i in range(1, 61)] or
            any(x.get('status') != 'ok' or x.get('cost_unknown') is not False or
                x.get('billing_ok') is not True for x in attempts)):
        raise ValueError('Final Qwen stage lacks 60 known valid attempts')
    ledger = rows(SNAPSHOT)
    if len(ledger) != 883 or ledger[0] != {'event': 'budget', 'cap_usd': '1.00'}:
        raise ValueError('Final Qwen child snapshot differs')
    settles = {}
    for reserve, settle in zip(ledger[1::2], ledger[2::2]):
        if (reserve.get('event') != 'reserve' or settle.get('event') != 'settle' or
                reserve.get('attempt_id') != settle.get('attempt_id') or
                reserve['attempt_id'] in settles):
            raise ValueError('Qwen child settlement ancestry differs')
        settles[reserve['attempt_id']] = Decimal(settle['usd'])
    if len(settles) != 441:
        raise ValueError('Qwen child attempt count differs')
    phase_cost = Decimal(0)
    for attempt in attempts:
        actual = Decimal(attempt['observed_cost_usd'])
        if settles.get(attempt['attempt_id']) != actual:
            raise ValueError('Qwen final stage cost differs from child settlement')
        phase_cost += actual
    known = sum(settles.values(), Decimal(0))
    return {'schema': 'qwen36-on-remaining-hosted-final-closure-audit-v1',
            'status': 'fresh3_p1_development_closed', 'full_60_result': True,
            'configuration_id': q.parent.CONFIG, 'fresh_pass': 'fresh3', 'condition': 'P1',
            'attempt_count': 60, 'valid_count': 60, 'first_id': 'DEV-001', 'last_id': 'DEV-060',
            'phase_known_actual_usd': str(phase_cost), 'child_known_actual_usd': str(known),
            'child_unknown_upper_bound_usd': '0', 'child_cap_usd': '1.00',
            'expected_unused_child_usd': str(Decimal('1.00')-known),
            'child_snapshot_sha256': q.study.sha(SNAPSHOT),
            'execution_manifest_sha256': q.study.sha(q.EXECUTION),
            'audit_source_sha256': q.study.sha(SOURCE),
            'phase_closure': bindings,
            'stage_evidence_sha256': {str((stage/name).relative_to(q.ROOT)):q.study.sha(stage/name)
                for name in ('development.claim.json','development.journal.jsonl',
                             'development.attempts.jsonl','development.responses.jsonl')}}


def prepare():
    with RECEIPT.open('x') as out: out.write(json.dumps(value(),indent=2)+'\n')
    return q.study.sha(RECEIPT)


def verify():
    if json.loads(RECEIPT.read_text()) != value():
        raise ValueError('Qwen final closure audit differs')
    return q.study.sha(RECEIPT)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('operation',choices=('prepare','verify'))
    a=p.parse_args();print(prepare() if a.operation=='prepare' else verify())


if __name__=='__main__':main()
