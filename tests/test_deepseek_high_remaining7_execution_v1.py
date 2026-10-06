"""Offline gates for the separately bound high remaining-seven executor."""
import json
from pathlib import Path
import sys
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import deepseek_high_remaining7_execution_v1 as adapter


def test_old_child_reconciled_and_new_plan_only_contains_remaining_stages():
    receipt = adapter.old_child_closed()
    assert receipt['unknown_upper_bound_usd'] == '0'
    first = adapter.plan_data('fresh1')
    assert first['configuration_id'] == adapter.proposal.CONFIG
    assert first['condition_order'] == ['P2']
    assert set(first['conditions']) == {'P2'}
    assert len(first['conditions']['P2']['smoke']) == 3
    assert len(first['conditions']['P2']['development']) == 60
    assert first['conditions']['P2']['smoke'][0]['payload']['provider']['max_price'] == {
        'prompt': 0.06, 'completion': 1.5, 'request': 0, 'image': 0}


def test_runtime_reuses_repaired_runner_and_requires_predecessors():
    core = adapter.repaired_core()
    first = adapter.plan_data('fresh1')
    assert core.study.CONFIG == adapter.proposal.CONFIG
    assert core.study.BASE / adapter.proposal.CONFIG == adapter.BASE
    assert core.study.BASE / 'fresh1' == adapter.BASE / 'fresh1'
    assert core.CONTINUE_INTRINSIC_INVALID is True
    assert core.live_controls is adapter.live_controls
    assert core.verify_phase_closure.__globals__['route_check']
    core.require_order(first, 'P2', 'smoke')
    with pytest.raises(ValueError, match='Inspected smoke'):
        core.require_order(first, 'P2', 'development')


def test_exact_stage_review_and_budget_required_before_execution():
    core = adapter.repaired_core()
    first = adapter.plan_data('fresh1')
    assert core.phase_paths(adapter.proposal.CONFIG, 'fresh1', 'P2', 'smoke')[0] == \
        adapter.BASE / 'fresh1/P2'
    # The adapter remains unapproved; the stage may not pass review.
    with pytest.raises(ValueError, match='review missing'):
        adapter.require_review()
    with pytest.raises((FileNotFoundError, ValueError)):
        core.review_receipt(adapter.BASE / 'fresh1/P2/smoke.root-review.json',
                            adapter.proposal.CONFIG, 'fresh1', 'P2', 'smoke',
                            adapter.sha(adapter.BASE / 'fresh1/manifest.json'))


def test_adapter_manifest_source_binding_and_exclusive_prepare():
    assert adapter.verify() == adapter.sha(adapter.MANIFEST)
    data = json.loads(adapter.MANIFEST.read_text())
    assert data['inference_authorized'] is False
    assert data['allocation_authorized'] is False
    assert data['proposed_child_cap_usd'] == '1.00'
    assert len(data['plans_sha256']) == 3
    assert all(adapter.sha(adapter.study.ROOT / item['path']) == item['sha256']
               for item in data['source_bindings'].values())
    with mock.patch.object(adapter, 'plan_data', side_effect=ValueError('prevalidation')):
        with pytest.raises(ValueError, match='prevalidation'):
            adapter.prepare()
    with pytest.raises(FileExistsError):
        adapter.prepare()


def test_budget_manifest_requires_exact_child_path(tmp_path):
    budget = tmp_path / 'budget.json'
    child = tmp_path / 'child.jsonl'
    entry = {'id': adapter.proposal.PARTITION_ID,
             'cap_usd': '1.00', 'model': adapter.study.MODEL,
             'provider': adapter.study.PROVIDER,
             'reasoning': adapter.study.EFFORT,
             'child_ledger': str(child)}
    budget.write_text(json.dumps({'version': 'paid-partitions-v1',
        'master_ledger': str(adapter.MASTER), 'partitions': [entry]}) + '\n')
    with mock.patch.object(adapter, 'BUDGET', budget), \
         mock.patch.object(adapter, 'CHILD_LEDGER', child):
        assert adapter.exact_budget_entry() == entry
        entry['child_ledger'] = str(tmp_path / 'other-child.jsonl')
        budget.write_text(json.dumps({'version': 'paid-partitions-v1',
            'master_ledger': str(adapter.MASTER), 'partitions': [entry]}) + '\n')
        with pytest.raises(ValueError, match='child ledger binding'):
            adapter.exact_budget_entry()


def test_stage_template_passes_explicit_development_phase_through_order_gate():
    plan = adapter.plan_data('fresh1')
    calls = []
    class FakeCore:
        def require_order(self, value, condition, phase):
            calls.append((value, condition, phase))
    with mock.patch.object(adapter, 'verify_plan', return_value=plan), \
         mock.patch.object(adapter, 'repaired_core', return_value=FakeCore()), \
         mock.patch.object(adapter, 'stage_receipt', return_value={'stage': 'fresh1/P2/development'}) as receipt:
        result = adapter.stage_template('fresh1', 'P2', 'development')
    assert result == {'stage': 'fresh1/P2/development'}
    assert calls == [(plan, 'P2', 'development')]
    receipt.assert_called_once_with('fresh1', 'P2', 'development')
