import sys
from pathlib import Path
from decimal import Decimal
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from openrouter_budget_v2 import BudgetLedger
from paid_budget_partitions_v2 import allocate, open_partition, reconcile_partition

def test_explicit_amendment_preserves_old_five_dollar_cap(tmp_path):
    p = tmp_path / 'master.jsonl'
    p.write_text('{"event":"budget","cap_usd":"5"}\n')
    ledger = BudgetLedger(p)
    assert ledger.cap == Decimal('5')
    with pytest.raises(ValueError): ledger.reserve(Decimal('6'), 'test')
    ledger.amend_cap('10', 'User explicitly approved ten dollars total')
    ledger.close()
    ledger = BudgetLedger(p)
    assert ledger.cap == Decimal('10')
    with pytest.raises(ValueError): ledger.amend_cap('11', 'not approved')
    ledger.close()

def test_partitions_cannot_exceed_master_with_concurrent_allocations(tmp_path):
    p = tmp_path / 'master.jsonl'
    ledger = BudgetLedger(p); ledger.close()
    spec = lambda i, c: {'id':i,'cap_usd':c,'model':'m','provider':'p','reasoning':'low'}
    manifest = tmp_path / 'partitions.json'
    allocate(p, manifest, [spec('one','6'),spec('two','4')])
    with pytest.raises(ValueError): allocate(p,tmp_path/'excess.json',[spec('three','.01')])
    child = open_partition(p,manifest,'one','m','p','low')
    attempt = child.reserve('.2','DEV-001')
    child.settle(attempt,'.1'); child.close()
    event = reconcile_partition(p,manifest,'one')
    assert Decimal(event['known_actual_usd']) == Decimal('.1')
    ledger = BudgetLedger(p); assert ledger.accounted() == Decimal('4.1'); ledger.close()

def test_pending_unknown_blocks_cap_amendment(tmp_path):
    p = tmp_path/'master.jsonl'
    p.write_text('{"event":"budget","cap_usd":"5"}\n')
    ledger = BudgetLedger(p)
    ledger.reserve('.5','DEV-001')
    with pytest.raises(ValueError): ledger.amend_cap('10','No pending changes allowed')
    ledger.close()
