"""Offline gates for the remaining-six DeepSeek low execution candidate."""
import json
from pathlib import Path
import sys
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import deepseek_low_remaining6_execution_v1 as adapter


def test_runtime_plans_preserve_six_phase_order_and_exact_requests():
    first = adapter.plan_data('fresh2')
    second = adapter.plan_data('fresh3')
    assert first['condition_order'] == ['P2', 'P0', 'P1']
    assert second['condition_order'] == ['P1', 'P2', 'P0']
    source = json.loads(adapter.proposal.MANIFEST.read_text())
    for plan in (first, second):
        assert plan['configuration_id'] == adapter.proposal.CONFIG
        for condition in plan['condition_order']:
            for stage, count in (('smoke', 3), ('development', 60)):
                rows = plan['conditions'][condition][stage]
                assert len(rows) == count
                assert [r['request_sha256'] for r in rows] == [
                    r['request_sha256'] for r in source['requests_by_condition'][condition][:count]]
                assert all(r['payload']['provider']['max_price'] == {
                    'prompt': 0.06, 'completion': 1.5, 'request': 0, 'image': 0}
                    for r in rows)


def test_repaired_core_uses_low_effort_and_strict_order():
    core = adapter.repaired_core()
    first = adapter.plan_data('fresh2')
    assert core.study.BASE / adapter.proposal.CONFIG == adapter.BASE
    assert core.study.BASE / 'fresh2' == adapter.BASE / 'fresh2'
    assert core.study.CONFIGS[adapter.proposal.CONFIG]['effort'] == 'low'
    assert core.CONTINUE_INTRINSIC_INVALID is True
    assert core.verify_phase_closure.__globals__['route_check']
    core.require_order(first, 'P2', 'smoke')
    with pytest.raises(ValueError, match='Inspected smoke'):
        core.require_order(first, 'P2', 'development')
    with pytest.raises(ValueError, match='Phase closure evidence missing'):
        core.verify_phase_closure(first, 'P2', 'development')


def test_development_closure_reads_low_route_endpoint_key(tmp_path):
    core = adapter.repaired_core()
    plan = adapter.plan_data('fresh2')
    manifest = tmp_path / 'fresh2' / 'manifest.json'
    manifest.parent.mkdir(parents=True)
    manifest.write_bytes((adapter.BASE / 'fresh2' / 'manifest.json').read_bytes())
    folder = tmp_path / 'fresh2' / 'P2'
    folder.mkdir()
    (folder / 'development.claim.json').write_text(json.dumps({
        'configuration_id': adapter.proposal.CONFIG,
        'fresh_pass': 'fresh2', 'condition': 'P2', 'phase': 'development',
        'manifest_sha256': adapter.sha(manifest)}) + '\n')
    for suffix in ('journal', 'attempts', 'responses'):
        (folder / f'development.{suffix}.jsonl').write_text('')
    with mock.patch.object(adapter, 'BASE', tmp_path), \
         mock.patch.object(adapter, 'verify_plan', return_value=plan):
        with pytest.raises(ValueError, match='exact ordered attempts and raw bodies'):
            core.verify_phase_closure(plan, 'P2', 'development')


def test_live_route_rebuilds_frozen_low_requests_without_inference():
    saved = json.loads(adapter.proposal.ROUTE.read_text())
    catalog = {'data': [saved['model']]}
    endpoints = {'data': {'id': adapter.proposal.old.MODEL,
                          'endpoints': [saved['endpoint']]}}
    with mock.patch.object(adapter.paid, 'fetch', side_effect=[catalog, endpoints]):
        model, endpoint, reserve = adapter.live_controls(adapter.plan_data('fresh2'), 'P2')
    assert model == saved['model']
    assert endpoint == saved['endpoint']
    assert reserve == adapter.proposal.RESERVE


def test_exact_budget_entry_and_phase_template(tmp_path):
    budget = tmp_path / 'budget.json'
    child = tmp_path / 'child.jsonl'
    entry = {'id': adapter.proposal.PARTITION_ID, 'cap_usd': '0.75',
             'model': adapter.proposal.old.MODEL,
             'provider': adapter.proposal.old.PROVIDER,
             'reasoning': 'low', 'child_ledger': str(child)}
    budget.write_text(json.dumps({'version': 'paid-partitions-v1',
        'master_ledger': str(adapter.MASTER), 'partitions': [entry]}) + '\n')
    with mock.patch.object(adapter, 'BUDGET', budget), \
         mock.patch.object(adapter, 'CHILD_LEDGER', child):
        assert adapter.exact_budget_entry() == entry
        entry['child_ledger'] = str(tmp_path / 'other.jsonl')
        budget.write_text(json.dumps({'version': 'paid-partitions-v1',
            'master_ledger': str(adapter.MASTER), 'partitions': [entry]}) + '\n')
        with pytest.raises(ValueError, match='child ledger binding'):
            adapter.exact_budget_entry()
    plan = adapter.plan_data('fresh2')
    calls = []
    class FakeCore:
        def require_order(self, value, condition, phase):
            calls.append((value, condition, phase))
    with mock.patch.object(adapter, 'verify_plan', return_value=plan), \
         mock.patch.object(adapter, 'repaired_core', return_value=FakeCore()), \
         mock.patch.object(adapter, 'stage_receipt',
                           return_value={'stage': 'fresh2/P2/development'}) as receipt:
        assert adapter.stage_template('fresh2', 'P2', 'development') == {
            'stage': 'fresh2/P2/development'}
    assert calls == [(plan, 'P2', 'development')]
    receipt.assert_called_once_with('fresh2', 'P2', 'development')


def test_manifest_binding_review_gate_and_prepare_refusal():
    assert adapter.verify() == adapter.sha(adapter.MANIFEST)
    value = json.loads(adapter.MANIFEST.read_text())
    assert value['inference_authorized'] is False
    assert value['allocation_authorized'] is False
    assert value['proposed_child_cap_usd'] == '0.75'
    assert all(adapter.sha(adapter.ROOT / item['path']) == item['sha256']
               for item in value['source_bindings'].values())
    with pytest.raises(ValueError, match='review missing'):
        adapter.require_review()
    with pytest.raises(FileExistsError):
        adapter.prepare()
