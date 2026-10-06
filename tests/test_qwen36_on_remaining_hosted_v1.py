"""Offline proof for the seven Qwen3.6 ON hosted successor phases."""
import json
from pathlib import Path
import sys
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import qwen36_on_remaining_hosted_v1 as successor


def test_predecessor_is_descriptive_interrupted_composite():
    proof = successor.verify_predecessor()
    assert proof['parent_p0'] == 'closed_60_valid'
    assert proof['parent_p1'] == 'interrupted_48_valid_1_unknown'
    assert proof['p1_suffix'] == 'closed_11_valid'
    assert proof['p1_composite'] == 'descriptive_59_valid_1_unknown'


def test_successor_preserves_original_payloads_and_declared_order():
    assert successor.STAGES == (
        ('fresh1', 'P2'), ('fresh2', 'P1'), ('fresh2', 'P2'),
        ('fresh2', 'P0'), ('fresh3', 'P2'), ('fresh3', 'P0'),
        ('fresh3', 'P1'))
    assert successor.CAP == 1
    for repeat in successor.study.ORDERS:
        original_path = successor.parent.BASE / repeat / 'manifest.json'
        original = successor.parent.verify_plan(repeat, successor.study.sha(original_path))
        plan = successor.expected_plan(repeat)
        assert plan['condition_order'] == original['condition_order']
        assert plan['predecessor_p1_status'] == 'descriptive_59_valid_1_unknown'
        for condition in successor.study.CONDITIONS:
            for phase, expected_count in (('smoke', 3), ('development', 60)):
                saved = original['conditions'][condition][phase]
                proposed = plan['conditions'][condition][phase]
                assert proposed == saved
                assert len(proposed) == expected_count
                assert all(r['request_sha256'] == successor.study.digest(
                    json.dumps(r['payload'], sort_keys=True)) for r in proposed)


def test_frozen_execution_has_only_seven_scheduled_phases():
    digest = successor.study.sha(successor.EXECUTION)
    execution = successor.verify(digest)
    assert execution['status'] == 'offline_proposal_unapproved'
    assert execution['inference_authorized'] is False
    assert execution['clean_matched_three_eligible'] is False
    assert [(s['fresh_pass'], s['condition']) for s in execution['schedule']] == list(successor.STAGES)
    assert all(len(s['smoke_ids']) == 3 and len(s['development_ids']) == 60
               for s in execution['schedule'])
    assert execution['full_reserve_total_usd'] == str(successor.parent.RESERVE * 441)


def test_order_gate_uses_successor_paths_and_requires_inspected_smoke():
    core = successor.private_runner()
    first = core.study.verify(successor.parent.CONFIG, 'fresh1',
                              successor.study.sha(successor.plan_path('fresh1')))
    assert core.phase_paths(successor.parent.CONFIG, 'fresh1', 'P2', 'smoke')[0] == (
        successor.BASE / successor.parent.CONFIG / 'fresh1/P2')
    core.require_order(first, 'P2', 'smoke')
    with mock.patch.object(core, 'verify_phase_closure', side_effect=ValueError('smoke not inspected')) as closure:
        with pytest.raises(ValueError, match='smoke not inspected'):
            core.require_order(first, 'P2', 'development')
        closure.assert_called_once()
    with pytest.raises(ValueError, match='Stage outside seven-phase successor'):
        core.require_order(first, 'P0', 'smoke')
    second = core.study.verify(successor.parent.CONFIG, 'fresh2',
                               successor.study.sha(successor.plan_path('fresh2')))
    with mock.patch.object(core, 'verify_phase_closure', side_effect=ValueError('prior development missing')) as closure:
        with pytest.raises(ValueError, match='prior development missing'):
            core.require_order(second, 'P1', 'smoke')
        closure.assert_called_once()


def test_runner_checks_root_review_before_network():
    core = successor.private_runner()
    digest = successor.study.sha(successor.plan_path('fresh1'))
    with mock.patch.object(core, 'live_controls', side_effect=AssertionError('network reached')), \
         mock.patch.object(core, 'review_receipt', side_effect=ValueError('review rejected')):
        with pytest.raises((FileExistsError, ValueError)):
            core.execute(successor.parent.CONFIG, 'fresh1', 'P2', 'smoke', digest,
                         successor.BASE / successor.parent.CONFIG / 'fresh1/P2/smoke.root-review.json')
