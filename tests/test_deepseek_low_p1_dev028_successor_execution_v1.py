"""Offline controls for the never-sent low P1 tail execution candidate."""
from decimal import Decimal
import json
from pathlib import Path
import sys
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import deepseek_low_p1_dev028_successor_execution_v1 as candidate


def test_exact_tail_only_and_full_later_phases():
    assert candidate.PHASES == (('fresh2', 'P1'), ('fresh3', 'P1'),
                                ('fresh3', 'P2'), ('fresh3', 'P0'))
    first = candidate.plan_data('fresh2')
    assert first['condition_order'] == ['P1']
    assert list(first['conditions']) == ['P1']
    assert first['conditions']['P1']['smoke'] == []
    tail = first['conditions']['P1']['development']
    assert [x['record_id'] for x in tail] == candidate.successor.UNSENT
    assert [x['position'] for x in tail] == list(range(33))
    assert [x['request_sha256'] for x in tail] == json.loads(
        candidate.successor.MANIFEST.read_text())['development_suffix_request_sha256']
    assert first['conditions']['P1']['clean_full_phase'] is False
    assert first['conditions']['P1']['suffix_completion_descriptive_only'] is True
    later = candidate.plan_data('fresh3')
    assert later['condition_order'] == ['P1', 'P2', 'P0']
    for condition in later['condition_order']:
        assert len(later['conditions'][condition]['smoke']) == 3
        assert len(later['conditions'][condition]['development']) == 60


def test_first_stage_requires_sealed_predecessor_and_no_smoke_replay():
    core = candidate.repaired_core()
    first = candidate.plan_data('fresh2')
    core.require_order(first, 'P1', 'development')
    with pytest.raises(ValueError, match='outside low P1 successor order'):
        core.require_order(first, 'P1', 'smoke')
    with pytest.raises(ValueError, match='outside low P1 successor order'):
        core.require_order(first, 'P0', 'development')


def test_no_spend_without_separate_review_and_child(tmp_path):
    assert candidate.CHILD_CAP == Decimal('0.50')
    assert candidate.PARTITION_ID != candidate.prior.PARTITION_ID
    assert candidate.CHILD_LEDGER != candidate.prior.CHILD_LEDGER
    saved = json.loads(candidate.MANIFEST.read_text())
    assert saved['allocation_authorized'] is False
    assert saved['inference_authorized'] is False
    review = tmp_path / 'review.json'
    review.write_text(json.dumps(candidate.review_template()))
    with mock.patch.object(candidate, 'REVIEW', review):
        with pytest.raises(ValueError, match='review missing'):
            candidate.require_review()
    with mock.patch.object(candidate, 'BUDGET', tmp_path / 'no-budget.json'):
        with pytest.raises(FileNotFoundError):
            candidate.exact_budget_entry()


def test_source_binding_covers_money_and_parent_evidence():
    saved = json.loads(candidate.MANIFEST.read_text())
    for path in (candidate.successor.AUDIT, candidate.successor.SNAPSHOT,
                 candidate.successor.RECONCILIATION, candidate.successor.CLOSED):
        assert str(path.relative_to(ROOT)) in saved['source_bindings']
    for name in ('scripts/openrouter_authority_release_v4.py',
                 'scripts/postapproval_authority_v3.py',
                 'scripts/openrouter_budget_v4.py',
                 'scripts/paid_budget_partitions_v4.py'):
        assert name in saved['source_bindings']
    assert candidate.verify() == candidate.sha(candidate.MANIFEST)


def test_bound_source_drift_blocks_verification():
    actual = candidate.sha
    with mock.patch.object(candidate, 'sha', side_effect=lambda path:
            '0' * 64 if Path(path) == candidate.successor.RECONCILIATION else actual(path)):
        with pytest.raises(ValueError, match='Bound low P1 successor source changed'):
            candidate.verify()
