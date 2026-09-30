"""The approved cap extension preserves earlier ledger and partition accounting."""
import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from openrouter_budget_v2 import BudgetLedger as BudgetLedgerV2, CAP as V2_CAP
from openrouter_budget_v3 import BudgetLedger, CAP
from paid_budget_partitions_v3 import allocate, open_partition, reconcile_partition


def test_historical_amendments_reopen_under_approved_ceiling(tmp_path):
    path = tmp_path / 'master.jsonl'
    path.write_text('{"event":"budget","cap_usd":"1"}\n')
    ledger = BudgetLedger(path)
    for old_cap, new_cap in (('1', '5'), ('5', '10'), ('10', '12.38')):
        assert ledger.cap == Decimal(old_cap)
        ledger.amend_cap(new_cap, 'Explicit approved aggregate cap increase')
    assert ledger.cap == CAP == Decimal('12.38')
    with pytest.raises(ValueError):
        ledger.amend_cap('12.39', 'Beyond approval')
    ledger.close()

    reopened = BudgetLedger(path)
    assert reopened.cap == CAP
    assert reopened.accounted() == 0
    reopened.close()
    assert V2_CAP == Decimal('10')
    with pytest.raises(ValueError):
        BudgetLedgerV2(path)
    assert [e['cap_usd'] for e in map(json.loads, path.read_text().splitlines())
            if e['event'] in ('budget', 'cap_amendment')] == ['1', '5', '10', '12.38']


def test_pending_and_retained_unknown_bound_survive_amendment(tmp_path):
    path = tmp_path / 'master.jsonl'
    path.write_text('{"event":"budget","cap_usd":"10"}\n')
    ledger = BudgetLedger(path)
    attempt = ledger.reserve('0.7', 'DEV-001')
    with pytest.raises(ValueError):
        ledger.amend_cap('12.38', 'Pending reservation')
    evidence = tmp_path / 'unknown.jsonl'
    evidence.write_text(json.dumps({'attempt_id': attempt, 'cost_unknown': True,
                                    'reserved_cost_usd': '0.7'}) + '\n')
    ledger.finalize_unknown_at_reserved_upper_bound(attempt, 'Provider charge unknown', evidence)
    ledger.amend_cap('12.38', 'Explicit approved aggregate cap increase')
    assert ledger.accounted() == Decimal('0.7')
    ledger.close()

    reopened = BudgetLedger(path)
    assert reopened.cap == CAP
    assert reopened.accounted() == Decimal('0.7')
    with pytest.raises(ValueError):
        reopened.reserve('11.69', 'DEV-002')
    reopened.close()


def test_v3_partitions_preserve_child_caps_and_master_encumbrance(tmp_path):
    master = tmp_path / 'master.jsonl'
    master.write_text('{"event":"budget","cap_usd":"10"}\n')
    ledger = BudgetLedger(master)
    ledger.amend_cap('12.38', 'Explicit approved aggregate cap increase')
    ledger.close()

    spec = lambda pid, cap: {'id': pid, 'cap_usd': cap, 'model': 'm',
                              'provider': 'p', 'reasoning': 'low'}
    manifest = tmp_path / 'parts.json'
    allocate(master, manifest, [spec('one', '6.18'), spec('two', '6.20')])
    with pytest.raises(ValueError):
        allocate(master, tmp_path / 'excess.json', [spec('three', '0.01')])

    child = open_partition(master, manifest, 'one', 'm', 'p', 'low')
    assert child.cap == Decimal('6.18')
    assert child.master_cap == CAP
    with pytest.raises(ValueError):
        child.reserve('6.19', 'DEV-001')
    attempt = child.reserve('0.2', 'DEV-001')
    assert child.settle(attempt, '0.1')
    child.close()
    event = reconcile_partition(master, manifest, 'one')
    assert Decimal(event['known_actual_usd']) == Decimal('0.1')
    assert Decimal(event['unused_allocation_released_usd']) == Decimal('6.08')

    reopened = BudgetLedger(master)
    assert reopened.accounted() == Decimal('6.30')
    assert reopened.partitions['two']['active'] is True
    with pytest.raises(ValueError):
        reopened.reserve('0.01', 'DEV-002')
    reopened.close()
