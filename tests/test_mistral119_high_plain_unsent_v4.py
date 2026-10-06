"""Offline gates for exact never-sent plain-Mistral high smoke suffix."""
from decimal import Decimal
import json
from pathlib import Path
import sys
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import mistral119_high_plain_unsent_v4 as candidate


def test_only_never_sent_plain_smoke_requests_are_proposed():
    plan = candidate.plan_data()
    original = candidate.old.verify_plan('fresh1', candidate.sha(
        candidate.old.BASE / 'fresh1/manifest.json'))
    assert plan['no_retry_ids'] == ['DEV-001']
    assert [row['record_id'] for row in plan['smoke_requests']] == ['DEV-002', 'DEV-003']
    assert [row['position'] for row in plan['smoke_requests']] == [2, 3]
    assert [row['request_sha256'] for row in plan['smoke_requests']] == [
        row['request_sha256'] for row in original['conditions']['P0']['smoke'][1:]]
    assert plan['complete_three_request_smoke'] is False
    assert plan['full_development_authorized'] is False
    assert plan['later_high_passes_authorized'] is False


def test_closed_parent_retains_unknown_full_reserve():
    terminal = candidate.closed_parent()
    assert terminal['attempted_ids'] == ['DEV-001']
    assert terminal['never_sent_smoke_ids'] == ['DEV-002', 'DEV-003']
    assert terminal['unknown_cost_upper_bound_usd'] == '0.04177920'
    child = [json.loads(x) for x in (candidate.old.BASE /
        ('budget-' + candidate.old.PARTITION_ID + '.jsonl')).read_text().splitlines()]
    assert child[2]['event'] == 'unknown_cost_accounted_as_upper_bound'
    assert child[3]['event'] == 'partition_closed'


def test_changed_unsent_membership_fails_closed():
    original = candidate.old.verify_plan
    def changed(*args):
        plan = original(*args)
        plan['conditions']['P0']['smoke'][1]['record_id'] = 'DEV-001'
        return plan
    with mock.patch.object(candidate.old, 'verify_plan', side_effect=changed):
        with pytest.raises(ValueError, match='membership'):
            candidate.plan_data()


def test_saved_proposal_is_offline_and_smoke_only():
    assert candidate.verify() == candidate.sha(candidate.PROPOSAL)
    value = json.loads(candidate.PROPOSAL.read_text())
    assert value['new_child_cap_usd'] == '0.10'
    assert Decimal(value['new_child_cap_usd']) >= candidate.RESERVE * 2
    assert value['authority_reader'] == 'openrouter-authority-release-v4'
    assert value['allocation_authorized'] is False
    assert value['dispatch_authorized'] is False
    assert value['execution_adapter_admitted'] is False
    assert 'Do not mark the original three-request smoke passed' in value['result_policy']
    assert 'scripts/openrouter_authority_release_v4.py' in value['source_bindings']
    assert 'scripts/openrouter_budget_v4.py' in value['source_bindings']


def test_capacity_reader_is_read_only(monkeypatch):
    class Ledger:
        cap = Decimal('22.38')
        closed = False
        def __init__(self, path):
            assert path == candidate.old.MASTER
        def state(self):
            return {}, set(), False
        def accounted(self):
            return Decimal('22')
        def close(self):
            pass
    snapshot = type('Snapshot', (), {'head_sha256': 'a' * 64,
        'openrouter_available_usd': Decimal('0.25')})()
    monkeypatch.setattr(candidate, 'BudgetLedger', Ledger)
    monkeypatch.setattr(candidate.authority, 'read_authority', lambda path: snapshot)
    result = candidate.capacity()
    assert result['admissible_now'] is True
    assert result['allocation_written'] is False
    assert result['inference_sent'] is False
