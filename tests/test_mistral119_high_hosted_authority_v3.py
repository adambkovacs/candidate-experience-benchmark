"""Offline checks for the high-only Mistral119 authority proposal."""
import base64
from copy import deepcopy
import json
from pathlib import Path
from unittest import mock

import pytest

import mistral119_high_hosted_authority_v3 as bridge


def test_high_unstarted_and_public_route_exact():
    bridge.no_previous_dispatch()
    route = bridge.route_snapshot()
    original, _ = bridge.study.historical(bridge.OLD_CONFIG)
    bridge.check_route(route['model'], route['selected_endpoint'],
                       original['model_catalog_entry'], original['provider_endpoint'])
    assert route['inference_sent'] is False
    assert route['selected_endpoint']['tag'] == 'mistral/zdr'
    assert bridge.RESERVE == bridge.study.RESERVE
    assert bridge.CAP >= bridge.study.RESERVE * 3


def test_every_fresh_request_keeps_frozen_payload_bytes():
    for repeat in bridge.study.ORDERS:
        original_path = bridge.study.BASE / bridge.OLD_CONFIG / repeat / 'manifest.json'
        original = bridge.study.verify(bridge.OLD_CONFIG, repeat, bridge.sha(original_path))
        proposed = bridge.plan_data(repeat)
        assert proposed['condition_order'] == original['condition_order']
        assert proposed['configuration_id'] == bridge.CONFIG
        assert proposed['reference_labels_read'] is False
        for condition in bridge.study.CONDITIONS:
            for phase, count in (('smoke', 3), ('development', 60)):
                before = original['conditions'][condition][phase]
                after = proposed['conditions'][condition][phase]
                assert len(after) == len(before) == count
                assert after == before
                assert all(row['request_sha256'] == bridge.study.digest(
                    json.dumps(row['payload'], sort_keys=True)) for row in after)


def test_route_and_price_drift_are_rejected():
    route = bridge.route_snapshot()
    endpoint = json.loads(json.dumps(route['selected_endpoint']))
    endpoint['pricing']['completion'] = '0.00000061'
    with pytest.raises(ValueError, match='route|price'):
        bridge.check_route(route['model'], endpoint, route['model'], route['selected_endpoint'])
    endpoint = json.loads(json.dumps(route['selected_endpoint']))
    endpoint['tag'] = 'mistral'
    with pytest.raises(ValueError, match='route|price'):
        bridge.check_route(route['model'], endpoint, route['model'], route['selected_endpoint'])


def test_execution_manifest_and_sequential_order_gate():
    execution = bridge.verify()
    assert execution['status'] == 'offline_proposal_unapproved'
    assert execution['inference_authorized'] is False
    assert execution['partition_id'] == bridge.PARTITION_ID
    core = bridge._private_runner()
    plan = bridge.verify_plan('fresh1', bridge.sha(bridge.BASE / 'fresh1/manifest.json'))
    core.require_order(plan, 'P0', 'smoke')
    with mock.patch.object(core, 'verify_phase_closure', side_effect=ValueError('smoke closure blocked')):
        with pytest.raises(ValueError):
            core.require_order(plan, 'P0', 'development')
    assert core.CONTINUE_INTRINSIC_INVALID is False
    assert core.partitions is bridge.partitions
    assert core.execute.__code__.co_filename == str(bridge.__file__)


def test_private_real_closure_reads_versioned_manifest_and_inspected_smoke(tmp_path):
    core = bridge._private_runner()
    plan = deepcopy(bridge.plan_data('fresh1'))
    request = plan['conditions']['P0']['smoke'][0]
    plan['conditions']['P0']['smoke'] = [request]
    folder = tmp_path / 'fresh1/P0'
    folder.mkdir(parents=True)
    manifest = tmp_path / 'fresh1/manifest.json'
    manifest.write_text(json.dumps(plan))
    manifest_sha = bridge.sha(manifest)
    prediction = {'sentiment': 'neutral', 'follow_up_needed': 'no',
                  'serious_concern_reported': 'no', 'testimonial_potential': 'no'}
    body = {'model': bridge.study.MODEL, 'provider': bridge.study.PROVIDER_NAME,
            'usage': {'cost': '0.001'},
            'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(prediction)}}]}
    attempt = {'id': request['record_id'], 'attempt_id': 'synthetic-1',
               'configuration_id': bridge.CONFIG, 'fresh_pass': 'fresh1',
               'condition': 'P0', 'phase': 'smoke', 'manifest_sha256': manifest_sha,
               'request_sha256': request['request_sha256'], 'request': request['payload'],
               'input_sha256': request['input_sha256'],
               'instruction_sha256': request['instruction_sha256'],
               'status': 'ok', 'billing_ok': True, 'cost_unknown': False,
               'observed_cost_usd': '0.001', 'reserved_cost_usd': str(bridge.RESERVE),
               'response_diagnostic': {'passed': True}, 'raw_response': body,
               'prediction': prediction, 'usage': body['usage'],
               'returned_model': body['model'], 'returned_provider': body['provider'],
               'provider_endpoint': bridge.route_snapshot()['selected_endpoint'],
               'reasoning_effort': 'high'}
    raw = {'id': request['record_id'], 'attempt_id': attempt['attempt_id'],
           'request_sha256': request['request_sha256'], 'http_status': 200,
           'body_truncated_at_limit': False, 'read_error': None,
           'body_base64': base64.b64encode(json.dumps(body).encode()).decode()}
    events = [
        {'event': 'phase_started', 'configuration_id': bridge.CONFIG,
         'fresh_pass': 'fresh1', 'condition': 'P0', 'phase': 'smoke'},
        {'event': 'request_intent', 'id': request['record_id'],
         'request_sha256': request['request_sha256']},
        {'event': 'request_started', 'id': request['record_id'],
         'attempt_id': attempt['attempt_id'], 'request_sha256': request['request_sha256']},
        {'event': 'request_finished', 'id': request['record_id'],
         'attempt_id': attempt['attempt_id'], 'status': 'ok', 'billing_ok': True,
         'cost_unknown': False, 'observed_cost_usd': attempt['observed_cost_usd']},
        {'event': 'phase_completed', 'configuration_id': bridge.CONFIG,
         'fresh_pass': 'fresh1', 'condition': 'P0', 'phase': 'smoke',
         'request_count': 1, 'attempt_ids': [attempt['attempt_id']]},
    ]
    (folder / 'smoke.claim.json').write_text(json.dumps({
        'configuration_id': bridge.CONFIG, 'fresh_pass': 'fresh1',
        'condition': 'P0', 'phase': 'smoke', 'manifest_sha256': manifest_sha}))
    for name, rows in [('smoke.attempts.jsonl', [attempt]),
                       ('smoke.responses.jsonl', [raw]),
                       ('smoke.journal.jsonl', events)]:
        (folder / name).write_text(''.join(json.dumps(row) + '\n' for row in rows))
    def synthetic_verify(repeat, digest):
        assert (repeat, digest) == ('fresh1', manifest_sha)
        return plan
    with mock.patch.object(bridge, 'BASE', tmp_path), \
         mock.patch.object(bridge, 'verify_plan', side_effect=synthetic_verify):
        bindings = core.verify_phase_closure(plan, 'P0', 'smoke')
        with pytest.raises(ValueError, match='Inspected smoke'):
            core.require_order(plan, 'P0', 'development')
        (folder / 'smoke-inspection.json').write_text(json.dumps({
            'decision': 'accepted_unchanged', 'configuration_id': bridge.CONFIG,
            **bindings}))
        core.require_order(plan, 'P0', 'development')


def test_review_precedes_network_and_child_gate_checks_full_reserve():
    core = bridge._private_runner()
    digest = bridge.sha(bridge.BASE / 'fresh1/manifest.json')
    with mock.patch.object(core, 'review_receipt', side_effect=ValueError('review rejected')), \
         mock.patch.object(core, 'live_controls', side_effect=AssertionError('network reached')):
        with pytest.raises((FileExistsError, ValueError)):
            core.execute(bridge.CONFIG, 'fresh1', 'P0', 'smoke', digest,
                         bridge.BASE / 'fresh1/P0/smoke.root-review.json')
    assert bridge.CAP > bridge.RESERVE
    assert bridge.CAP < bridge.RESERVE * 567
    class NearlyFull:
        cap = bridge.CAP
        master_cap = bridge.Decimal('22.38')
        closed = False
        def state(self):
            return {}, set(), False
        def accounted(self):
            return bridge.CAP - bridge.RESERVE / 2
        def close(self):
            pass
    with mock.patch.object(bridge.partitions, 'open_partition', return_value=NearlyFull()):
        with pytest.raises(ValueError, match='unavailable'):
            core.budget_gate({}, bridge.BASE / 'budget.json', bridge.CONFIG)
