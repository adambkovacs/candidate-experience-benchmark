"""Offline admission checks for the DeepSeek low v4 continuation."""
from decimal import Decimal
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import deepseek_low_remaining5_v4_execution as candidate


def test_only_five_remaining_phases_and_identical_payloads():
    assert candidate.PHASES == (('fresh2', 'P0'), ('fresh2', 'P1'),
                                ('fresh3', 'P1'), ('fresh3', 'P2'), ('fresh3', 'P0'))
    for repeat in candidate.PASSES:
        plan = candidate.plan_data(repeat)
        source = json.loads((candidate.successor.PREDECESSOR_PLAN / repeat / 'manifest.json').read_text())
        assert plan['condition_order'] == [condition for pass_name, condition in candidate.PHASES if pass_name == repeat]
        assert set(plan['conditions']) == set(plan['condition_order'])
        for condition in plan['condition_order']:
            assert plan['conditions'][condition] == source['conditions'][condition]
            assert len(plan['conditions'][condition]['development']) == 60
    assert candidate.plan_data('fresh2')['conditions'].get('P2') is None


def test_new_child_and_v4_gate_without_allocation():
    core = candidate.repaired_core()
    assert candidate.CHILD_CAP == Decimal('0.50')
    ledger = mock.Mock()
    ledger.cap = candidate.CHILD_CAP
    ledger.master_cap = Decimal('22.38')
    ledger.closed = False
    ledger.state.return_value = ({}, {}, False)
    ledger.accounted.return_value = Decimal(0)
    locked = mock.MagicMock()
    locked.__enter__.return_value.read.return_value = b'v3-only'
    snapshot = SimpleNamespace(head_sha256='head')
    with mock.patch.object(candidate, 'exact_budget_entry'), \
         mock.patch.object(candidate.partitions, 'open_partition', return_value=ledger), \
         mock.patch.object(candidate.authority.old, '_locked', return_value=locked), \
         mock.patch.object(candidate.authority, '_scan', return_value=(snapshot, {}, set())), \
         mock.patch.object(candidate.authority, 'hold_authority') as hold:
        with pytest.raises(ValueError, match='V4 transition'):
            core.budget_gate({'global_authority_head_sha256': 'head'}, candidate.BUDGET,
                             candidate.prior.prior.proposal.CONFIG)
    ledger.close.assert_called_once()
    hold.assert_not_called()


def test_first_stage_order_and_no_old_p2_replay():
    core = candidate.repaired_core()
    first = candidate.plan_data('fresh2')
    core.require_order(first, 'P0', 'smoke')
    with pytest.raises(ValueError, match='outside low remaining-five order'):
        core.require_order(first, 'P2', 'smoke')


@pytest.mark.parametrize('name', [
    'scripts/postapproval_authority_v2.py',
    'scripts/qwen27_fresh_repeat_execution.py',
    'scripts/deepseek_low_remaining6_execution_v1.py',
])
def test_transitive_runtime_drift_invalidates_adapter(name):
    saved = json.loads(candidate.MANIFEST.read_text())
    assert name in saved['source_bindings']
    actual_sha = candidate.sha
    with mock.patch.object(candidate, 'sha', side_effect=lambda path:
            '0' * 64 if Path(path).name == Path(name).name else actual_sha(path)):
        with pytest.raises(ValueError, match='Bound low remaining-five source changed'):
            candidate.verify()
