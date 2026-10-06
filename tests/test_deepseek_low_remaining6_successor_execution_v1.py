"""Offline gates for the exact-unsent low successor execution adapter."""
import json
from pathlib import Path
import sys
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import deepseek_low_remaining6_successor_execution_v1 as adapter


def test_suffix_and_later_plans_preserve_frozen_requests_without_replay():
    fresh2 = adapter.plan_data('fresh2')
    fresh3 = adapter.plan_data('fresh3')
    suffix = fresh2['conditions']['P2']
    assert fresh2['condition_order'] == ['P2', 'P0', 'P1']
    assert fresh3['condition_order'] == ['P1', 'P2', 'P0']
    assert [row['record_id'] for row in suffix['smoke']] == [
        'DEV-006', 'DEV-007', 'DEV-008']
    assert [row['record_id'] for row in suffix['development']] == [
        f'DEV-{n:03}' for n in range(6, 61)]
    assert len(suffix['development']) == 55
    assert [row['position'] for row in suffix['development']] == list(range(55))
    original = adapter.prior.plan_data('fresh2')
    for repeat, plan in (('fresh2', fresh2), ('fresh3', fresh3)):
        for condition in plan['condition_order']:
            if (repeat, condition) == ('fresh2', 'P2'):
                continue
            assert plan['conditions'][condition] == adapter.prior.plan_data(repeat)[
                'conditions'][condition]
    assert [row['request_sha256'] for row in suffix['development']] == [
        row['request_sha256'] for row in original['conditions']['P2']['development'][5:]]
    assert fresh2['proposed_child_budget_usd'] == '0.35'
    assert fresh2['per_request_reserve_usd'] == '0.06905856'
    assert suffix['clean_full_phase'] is False
    assert suffix['suffix_completion_descriptive_only'] is True


def test_core_routes_evidence_to_new_child_and_smoke_six_through_eight(tmp_path):
    core = adapter.repaired_core()
    plan = adapter.plan_data('fresh2')
    assert core.phase_paths(adapter.prior.proposal.CONFIG, 'fresh2', 'P2',
                            'smoke')[0] == adapter.BASE / 'fresh2/P2'
    core.require_order(plan, 'P2', 'smoke')
    manifest = tmp_path / 'fresh2/manifest.json'
    manifest.parent.mkdir(parents=True)
    manifest.write_bytes((adapter.BASE / 'fresh2/manifest.json').read_bytes())
    with mock.patch.object(adapter, 'BASE', tmp_path), \
         mock.patch.object(adapter, 'verify_plan', return_value=plan):
        with pytest.raises(ValueError, match='Phase closure evidence missing'):
            core.verify_phase_closure(plan, 'P2', 'development')
    with mock.patch.object(adapter, 'BASE', tmp_path), \
         mock.patch.object(adapter, 'verify_plan', return_value=plan), \
         mock.patch.object(core, 'verify_phase_closure',
                           return_value={'manifest_sha256': 'm',
                               'journal_sha256': 'j', 'attempts_sha256': 'a',
                               'responses_sha256': 'r'}), \
         mock.patch.object(core, 'jsonl', return_value=[
             {'id': f'DEV-{n:03}', 'status': 'ok',
              'billing_ok': True, 'cost_unknown': False}
             for n in range(6, 9)]):
        folder = tmp_path / 'fresh2/P2'
        folder.mkdir(parents=True)
        value = core.inspect(adapter.prior.proposal.CONFIG, 'fresh2', 'P2',
                             'synthetic-sha', 'Three valid bounded calls')
        assert value['decision'] == 'accepted_unchanged'
        assert json.loads((folder / 'smoke-inspection.json').read_text()) == value


def test_live_route_rebuilds_exact_successor_requests_without_inference():
    saved = json.loads(adapter.prior.proposal.ROUTE.read_text())
    catalog = {'data': [saved['model']]}
    endpoints = {'data': {'id': adapter.prior.proposal.old.MODEL,
                          'endpoints': [saved['endpoint']]}}
    with mock.patch.object(adapter.prior.paid, 'fetch',
                           side_effect=[catalog, endpoints]):
        model, endpoint, reserve = adapter.live_controls(
            adapter.plan_data('fresh2'), 'P2')
    assert model == saved['model']
    assert endpoint == saved['endpoint']
    assert reserve == adapter.prior.proposal.RESERVE
    changed = json.loads(json.dumps(saved['endpoint']))
    changed['pricing']['prompt'] = '0.000000061'
    with mock.patch.object(adapter.prior.paid, 'fetch',
                           side_effect=[catalog, {'data': {'id': adapter.prior.proposal.old.MODEL,
                                                            'endpoints': [changed]}}]):
        with pytest.raises(ValueError):
            adapter.live_controls(adapter.plan_data('fresh2'), 'P2')


def test_budget_manifest_must_bind_exact_new_child(tmp_path):
    budget = tmp_path / 'budget.json'
    child = tmp_path / 'child.jsonl'
    entry = {'id': adapter.PARTITION_ID, 'cap_usd': '0.35',
             'model': adapter.prior.proposal.old.MODEL,
             'provider': adapter.prior.proposal.old.PROVIDER,
             'reasoning': 'low', 'child_ledger': str(child)}
    budget.write_text(json.dumps({'version': 'paid-partitions-v1',
        'master_ledger': str(adapter.MASTER), 'partitions': [entry]}) + '\n')
    with mock.patch.object(adapter, 'BUDGET', budget), \
         mock.patch.object(adapter, 'CHILD_LEDGER', child):
        assert adapter.exact_budget_entry() == entry
        entry['cap_usd'] = '0.36'
        budget.write_text(json.dumps({'version': 'paid-partitions-v1',
            'master_ledger': str(adapter.MASTER), 'partitions': [entry]}) + '\n')
        with pytest.raises(ValueError, match='child binding'):
            adapter.exact_budget_entry()


def test_manifest_review_and_budget_are_independent_from_closed_child(tmp_path):
    assert adapter.verify() == adapter.sha(adapter.MANIFEST)
    assert adapter.PARTITION_ID != adapter.prior.proposal.PARTITION_ID
    assert adapter.CHILD_CAP != adapter.prior.proposal.CHILD_CAP
    manifest = json.loads(adapter.MANIFEST.read_text())
    assert manifest['allocation_authorized'] is False
    assert manifest['inference_authorized'] is False
    assert str(adapter.prior.CHILD_LEDGER.relative_to(adapter.ROOT)) in \
        manifest['source_bindings']
    review = tmp_path / 'review.json'
    review.write_text(json.dumps(adapter.review_template()) + '\n')
    with mock.patch.object(adapter, 'REVIEW', review):
        with pytest.raises(ValueError, match='review missing'):
            adapter.require_review()
    with pytest.raises(FileExistsError):
        adapter.prepare()
