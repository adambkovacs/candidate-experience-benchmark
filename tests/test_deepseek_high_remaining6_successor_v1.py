"""Exact unsent high-model proposal, without budget or network operations."""
from pathlib import Path
import sys
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import deepseek_high_remaining6_successor_v1 as candidate


def test_exact_untouched_suffix_and_later_stage_order():
    plan = candidate.proposal_data()
    assert plan['development_suffix_ids'] == [f'DEV-{n:03d}' for n in range(28, 61)]
    assert plan['no_retry_ids'] == [f'DEV-{n:03d}' for n in range(1, 28)]
    assert len(plan['development_suffix_request_sha256']) == 33
    assert [(row['fresh_pass'], row['condition']) for row in plan['later_phase_order']] == [
        ('fresh2', 'P0'), ('fresh2', 'P1'), ('fresh3', 'P1'),
        ('fresh3', 'P2'), ('fresh3', 'P0')]
    assert plan['predecessor_unknown_cost_upper_bound_usd'] == '0.06905856'
    assert plan['allocation_authorized'] is False
    assert plan['dispatch_authorized'] is False


def test_proposal_uses_archived_plan_not_v3_runtime_gate():
    with mock.patch.object(candidate.old, 'verify_plan',
                           side_effect=AssertionError('v3 runtime verifier called')):
        assert candidate.proposal_data()['first_unsent_id'] == 'DEV-028'


def test_changed_frozen_request_fails_source_binding():
    original = candidate.report.portable_plan
    def changed(repeat, digest):
        plan = original(repeat, digest)
        if repeat == 'fresh2':
            plan['conditions']['P2']['development'][27]['request_sha256'] = '0' * 64
        return plan
    with mock.patch.object(candidate.report, 'portable_plan', side_effect=changed):
        with pytest.raises(ValueError, match='unsent request identity'):
            candidate.proposal_data()
