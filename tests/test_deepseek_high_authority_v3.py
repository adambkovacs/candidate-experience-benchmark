"""Offline tests for the versioned DeepSeek high price and authority bridge."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path

import pytest

import deepseek_high_authority_v3 as bridge
import openrouter_budget_amendment_v3 as amendment
import openrouter_budget_v4 as budget_v4
import paid_budget_partitions_v4 as partitions
import postapproval_authority_v2 as old_authority
import postapproval_authority_v3 as authority


def test_all_requests_change_only_declared_price_ceiling():
    for repeat in bridge.study.ORDERS:
        old = bridge.study.verify(repeat, bridge.sha(bridge.study.BASE / repeat / 'manifest.json'))
        new = bridge.plan_data(repeat)
        assert new['condition_order'] == old['condition_order']
        assert new['reference_labels_read'] is False
        for condition in bridge.study.CONDITIONS:
            for phase, length in (('smoke', 3), ('development', 60)):
                before = old['conditions'][condition][phase]
                after = new['conditions'][condition][phase]
                assert len(after) == length
                for prior, current in zip(before, after):
                    expected = deepcopy(prior['payload'])
                    expected['provider']['max_price'] = {
                        'prompt': float(bridge.INPUT_CEILING),
                        'completion': float(bridge.OUTPUT_CEILING),
                        'request': 0, 'image': 0}
                    assert current['payload'] == expected
                    assert current['record_id'] == prior['record_id']
                    assert current['input_sha256'] == prior['input_sha256']
                    assert current['instruction_sha256'] == prior['instruction_sha256']
                    assert current['request_sha256'] == bridge.study.digest(
                        json.dumps(expected, sort_keys=True))


def test_saved_route_and_execution_proposal_bind_sources(monkeypatch):
    route = bridge.route_snapshot()
    assert route['inference_sent'] is False
    assert bridge.paid.reservation(route['selected_endpoint'], bridge.study.MAX_TOKENS,
                                    bridge.INPUT_CEILING, bridge.OUTPUT_CEILING) == bridge.RESERVE
    assert bridge.verify()['schema'] == bridge.SCHEMA + '-execution'
    original = bridge.plan_data('fresh1')
    changed = deepcopy(original)
    changed['conditions']['P0']['smoke'][0]['payload']['provider']['max_price']['completion'] = 2.0
    assert changed != original
    with monkeypatch.context() as patch:
        patch.setattr(bridge, 'OUTPUT_CEILING', Decimal('1.33'))
        with pytest.raises(ValueError):
            bridge.route_snapshot()


def test_live_price_decrease_keeps_frozen_route_and_reserve():
    saved = bridge.route_snapshot()
    endpoint = deepcopy(saved['selected_endpoint'])
    endpoint['pricing']['prompt'] = '0.00000004345'
    endpoint['pricing']['completion'] = '0.00000120'
    bridge.check_route(saved['model'], endpoint,
                       saved['model'], saved['selected_endpoint'])
    assert bridge.paid.reservation(endpoint, bridge.study.MAX_TOKENS,
                                   bridge.INPUT_CEILING, bridge.OUTPUT_CEILING) == bridge.RESERVE


@pytest.mark.parametrize('key,value', [
    ('prompt', '-0.000000001'),
    ('completion', '-0.000000001'),
    ('prompt', '0.000000050'),
    ('completion', '0.00000133'),
    ('input_cache_read', '0.000000010'),
])
def test_live_price_change_refused(key, value):
    saved = bridge.route_snapshot()
    endpoint = deepcopy(saved['selected_endpoint'])
    endpoint['pricing'][key] = value
    with pytest.raises(ValueError, match='price|Invalid price'):
        bridge.check_route(saved['model'], endpoint,
                           saved['model'], saved['selected_endpoint'])


def test_private_executor_preserves_invalid_policy_and_capacity_gate():
    core = bridge._private_runner()
    assert core.CONTINUE_INTRINSIC_INVALID is True
    assert core.partitions is partitions
    assert core.study.CONFIG == bridge.CONFIG
    assert core.execute.__code__.co_filename == str(bridge.__file__)
    assert core.verify_phase_closure.__code__ is bridge.frozen.verify_phase_closure.__code__


def test_predecessor_and_inspected_smoke_required():
    core = bridge._private_runner()
    first = bridge.verify_plan('fresh1', bridge.sha(bridge.BASE / 'fresh1/manifest.json'))
    second = bridge.verify_plan('fresh2', bridge.sha(bridge.BASE / 'fresh2/manifest.json'))
    with pytest.raises(ValueError, match='Inspected smoke'):
        core.require_order(first, 'P0', 'development')
    with pytest.raises(ValueError, match='Earlier fresh pass incomplete'):
        core.require_order(second, 'P2', 'smoke')


def test_stage_receipt_rejects_changed_review(tmp_path, monkeypatch):
    base = tmp_path / 'results'
    stage = base / 'fresh1/P0'
    stage.mkdir(parents=True)
    (base / 'fresh1/manifest.json').write_text('{}\n')
    (base / 'execution-manifest.json').write_text('{}\n')
    budget = base / 'budget.json'
    budget.write_text('{}\n')
    monkeypatch.setattr(bridge, 'BASE', base)
    monkeypatch.setattr(bridge, 'EXECUTION', base / 'execution-manifest.json')
    monkeypatch.setattr(bridge, 'AUTHORITY', tmp_path / 'authority.jsonl')
    monkeypatch.setattr(bridge.authority, 'read_authority', lambda path: type('A', (), {'head_sha256': 'a'*64})())
    monkeypatch.setattr(bridge, 'verify', lambda: {'schema': bridge.SCHEMA + '-execution'})
    receipt = bridge.stage_receipt('fresh1', 'P0', 'smoke', budget)
    receipt.update(approved=True, independent_review=True, authorized_by_root=True, reviewer='root')
    path = stage / 'smoke.root-review.json'
    path.write_text(json.dumps(receipt) + '\n')
    core = bridge._private_runner()
    assert core.review_receipt(path, bridge.CONFIG, 'fresh1', 'P0', 'smoke', receipt['plan_sha256'])[1] == budget
    receipt['global_hold_source_sha256'] = '0'*64
    path.write_text(json.dumps(receipt) + '\n')
    with pytest.raises(ValueError, match='receipt differs'):
        core.review_receipt(path, bridge.CONFIG, 'fresh1', 'P0', 'smoke', receipt['plan_sha256'])


def test_real_v4_partition_reserves_and_stops_at_cap(tmp_path):
    master = tmp_path / 'master.jsonl'
    master.write_text(json.dumps({'event': 'budget', 'cap_usd': '10'}) + '\n')
    manifest = tmp_path / 'budget.json'
    partitions.allocate(master, manifest, [{'id': bridge.PARTITION_ID,
        'cap_usd': str(bridge.CAP), 'model': bridge.study.MODEL,
        'provider': bridge.study.PROVIDER, 'reasoning': bridge.study.EFFORT}])
    child = partitions.open_partition(master, manifest, bridge.PARTITION_ID,
                                      bridge.study.MODEL, bridge.study.PROVIDER, bridge.study.EFFORT)
    try:
        assert child.cap == bridge.CAP
        for index in range(15):
            assert child.accounted() + bridge.RESERVE <= child.cap
            attempt = child.reserve(bridge.RESERVE, f'DEV-{index + 1:03}')
            assert child.settle(attempt, bridge.RESERVE)
        assert child.accounted() == bridge.RESERVE * 15
        assert child.accounted() + bridge.RESERVE > child.cap
        with pytest.raises(ValueError):
            child.reserve(bridge.RESERVE, 'DEV-016')
    finally:
        child.close()


def test_real_amended_gate_hold_stale_receipt_and_capacity(tmp_path, monkeypatch):
    master = tmp_path / 'master.jsonl'
    master.write_text(json.dumps({'event': 'budget', 'cap_usd': '12.38'}) + '\n')
    auth = tmp_path / 'authority.jsonl'
    header = json.dumps(old_authority.HEADER).encode() + b'\n'
    auth.write_bytes(header)
    baseline = {'baseline_head': old_authority.sha(header), 'baseline_events': 1}
    proposal_path = tmp_path / 'proposal.json'
    amendment.prepare(proposal_path, master_path=master, authority_path=auth, **baseline)
    candidate = json.loads((tmp_path / 'root-review-candidate.json').read_text())
    candidate.update(approved=True, independent_review=True, authorized_by_root=True,
                     reviewer='root', reviewed_utc='2026-10-06T18:00:00+00:00')
    review = tmp_path / 'activation.root-review.json'
    review.write_text(json.dumps(candidate) + '\n')
    amendment.activate(review)
    partition = tmp_path / 'budget.json'
    partitions.allocate(master, partition, [{'id': bridge.PARTITION_ID,
        'cap_usd': str(bridge.CAP), 'model': bridge.study.MODEL,
        'provider': bridge.study.PROVIDER, 'reasoning': bridge.study.EFFORT}])
    base = tmp_path / 'versioned'
    base.mkdir()
    execution = base / 'execution-manifest.json'
    execution.write_text('{}\n')
    monkeypatch.setattr(bridge, 'BASE', base)
    monkeypatch.setattr(bridge, 'EXECUTION', execution)
    monkeypatch.setattr(bridge, 'MASTER', master)
    monkeypatch.setattr(bridge, 'AUTHORITY', auth)
    original_read = authority.read_authority
    original_scan = authority._scan
    original_hold = authority.hold_authority
    monkeypatch.setattr(authority, 'read_authority',
                        lambda path: original_read(path, **baseline))
    monkeypatch.setattr(authority, '_scan',
                        lambda raw, **kwargs: original_scan(raw, **(kwargs or baseline)))
    monkeypatch.setattr(authority, 'hold_authority',
                        lambda *args, **kwargs: original_hold(*args, **kwargs, **baseline))
    core = bridge._private_runner()
    receipt = {'global_authority_head_sha256': authority.read_authority(auth).head_sha256}
    child = core.budget_gate(receipt, partition, bridge.CONFIG)
    child.close()
    held = authority.read_authority(auth)
    assert held.openrouter_accounted_usd == bridge.CAP
    with pytest.raises(ValueError, match='Authority head changed'):
        core.budget_gate(receipt, partition, bridge.CONFIG)
    child = partitions.open_partition(master, partition, bridge.PARTITION_ID,
                                      bridge.study.MODEL, bridge.study.PROVIDER, bridge.study.EFFORT)
    try:
        prior = child.reserve(Decimal('0.85'), 'SYNTHETIC-PRIOR')
        assert child.settle(prior, Decimal('0.85'))
    finally:
        child.close()
    refreshed = {'global_authority_head_sha256': held.head_sha256}
    with pytest.raises(ValueError, match='Insufficient child capacity'):
        core.budget_gate(refreshed, partition, bridge.CONFIG)
    ledger = budget_v4.BudgetLedger(master)
    try:
        assert ledger.cap == Decimal('22.38')
        assert ledger.partitions[bridge.PARTITION_ID]['active']
    finally:
        ledger.close()
    assert authority.read_authority(auth).openrouter_accounted_usd == bridge.CAP
