"""Offline checks for a distinct plain-Mistral high first smoke."""
from copy import deepcopy
import json
from unittest import mock

import pytest

import mistral119_high_plain_authority_v1 as plain


def test_parent_failure_is_terminal_and_privately_preserved():
    parent = plain.parent_terminal()
    assert parent['attempted_ids'] == ['DEV-001']
    assert parent['never_sent_smoke_ids'] == ['DEV-002', 'DEV-003']
    assert parent['unknown_cost_upper_bound_usd'] == str(plain.RESERVE)
    assert parent['reconciliation_sha256'] == plain.sha(plain.PARENT_RECONCILIATION)


def test_new_plain_route_changes_only_provider_tag_in_three_requests():
    plan = plain.plan_data('fresh1')
    original_path = plain.study.BASE / plain.OLD_CONFIG / 'fresh1/manifest.json'
    original = plain.study.verify(plain.OLD_CONFIG, 'fresh1', plain.sha(original_path))
    assert plan['configuration_id'] != original['configuration_id']
    assert plan['provider_tag'] == 'mistral'
    assert plan['condition_order'] == ['P0']
    assert plan['planned_request_count'] == 3
    assert plan['conditions']['P0']['development'] == []
    for before, after in zip(original['conditions']['P0']['smoke'],
                             plan['conditions']['P0']['smoke'], strict=True):
        expected = deepcopy(before['payload'])
        expected['provider']['only'] = ['mistral']
        assert after['payload'] == expected
        assert after['request_sha256'] == plain.study.digest(json.dumps(expected, sort_keys=True))
        assert after['request_sha256'] != before['request_sha256']
        assert after['record_id'] == before['record_id']
    assert plain.route_snapshot()['selected_endpoint']['tag'] == 'mistral'


def test_drift_and_other_stage_are_rejected():
    route = plain.route_snapshot()
    endpoint = deepcopy(route['selected_endpoint'])
    endpoint['tag'] = 'mistral/zdr'
    with pytest.raises(ValueError, match='route|price'):
        plain.check_route(route['model'], endpoint, route['model'], route['selected_endpoint'])
    endpoint = deepcopy(route['selected_endpoint'])
    endpoint['pricing']['completion'] = '0.00000061'
    with pytest.raises(ValueError, match='route|price'):
        plain.check_route(route['model'], endpoint, route['model'], route['selected_endpoint'])
    with pytest.raises(ValueError, match='Only fresh1'):
        plain.plan_data('fresh2')
    with pytest.raises(ValueError, match='outside exact'):
        plain.stage_receipt('fresh1', 'P0', 'development', plain.BASE / 'budget.json')


def test_manifest_private_runner_and_order_scope():
    execution = plain.verify()
    assert execution['inference_authorized'] is False
    assert execution['parent_terminal_sha256'] == plain.sha(plain.PARENT_TERMINAL)
    assert set(execution['plans_sha256']) == {'fresh1'}
    core = plain._private_runner()
    plan = plain.verify_plan('fresh1', plain.sha(plain.BASE / 'fresh1/manifest.json'))
    core.require_order(plan, 'P0', 'smoke')
    assert core.study.PROVIDER == 'mistral'
    assert core.study.ORDERS == {'fresh1': ['P0']}
    assert core.CONTINUE_INTRINSIC_INVALID is False
    assert core.execute.__code__.co_filename == str(plain.__file__)
    with pytest.raises((ValueError, KeyError)):
        core.require_order(plan, 'P1', 'smoke')


def test_review_precedes_live_route_and_full_reserve_gate():
    core = plain._private_runner()
    digest = plain.sha(plain.BASE / 'fresh1/manifest.json')
    with mock.patch.object(core, 'review_receipt', side_effect=ValueError('review missing')), \
         mock.patch.object(core, 'live_controls', side_effect=AssertionError('network reached')):
        with pytest.raises((FileExistsError, ValueError)):
            core.execute(plain.CONFIG, 'fresh1', 'P0', 'smoke', digest,
                         plain.BASE / 'fresh1/P0/smoke.root-review.json')
    assert plain.CAP >= 3 * plain.RESERVE
    class NearlyFull:
        cap = plain.CAP
        master_cap = plain.Decimal('22.38')
        closed = False
        def state(self):
            return {}, set(), False
        def accounted(self):
            return plain.CAP - plain.RESERVE / 2
        def close(self):
            pass
    with mock.patch.object(plain.partitions, 'open_partition', return_value=NearlyFull()):
        with pytest.raises(ValueError, match='unavailable'):
            core.budget_gate({}, plain.BASE / 'budget.json', plain.CONFIG)
