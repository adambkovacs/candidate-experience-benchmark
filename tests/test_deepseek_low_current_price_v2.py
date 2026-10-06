from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import deepseek_low_current_price_v2 as s


@pytest.fixture(scope='module')
def proposal():
    return s.manifest_value()


def catalogs(endpoint=None, model=None):
    if endpoint is None or model is None:
        model, endpoint = s.route_context()
    return {'data': [deepcopy(model)]}, {'data': {'id': s.admission.MODEL, 'endpoints': [deepcopy(endpoint)]}}


def test_exact_ten_preserve_every_prior_failure_and_unapproved_cap(proposal):
    assert proposal['ids'] == [f'DEV-{n:03d}' for n in range(51, 61)]
    assert proposal['preserved_status_counts'] == {'ok': 46, 'invalid_output': 1,
        'service_error': 3, 'never_sent': 10}
    assert proposal['preserved_failed_ids'] == ['DEV-040', 'DEV-049', 'DEV-050']
    assert proposal['preserved_invalid_ids'] == ['DEV-039']
    assert proposal['reference_labels_read'] is False
    assert proposal['replay_authorized'] is False
    assert proposal['inference_authorized'] is False
    assert proposal['requested_global_cap_usd'] == '10.55'
    assert proposal['requested_cap_increase_approved'] is False
    assert proposal['global_authority_cap_usd'] == '10.00'
    assert s.authority_v2.CAP == Decimal('10.00')


def test_full_endpoint_context_reserve_uses_current_exact_rates(proposal):
    model, endpoint = s.route_context()
    assert endpoint['status'] == 0
    assert endpoint['tag'] == 'open-inference/fp4'
    assert s.INPUT_CEILING == Decimal('0.055')
    assert s.OUTPUT_CEILING == Decimal('1.32')
    assert s.RESERVE == Decimal(1048576) * Decimal('5.5e-8') + Decimal(4096) * Decimal('1.32e-6')
    assert s.RESERVE == Decimal('0.0630784')
    assert s.CHILD_CAP == s.TOTAL_RESERVE == s.RESERVE * 10
    assert Decimal(proposal['child_cap_usd']) == Decimal('0.630784')


def test_request_identity_changes_only_exact_price_controls(proposal):
    assert all(x['request_sha256'] != x['old_request_sha256'] for x in proposal['requests'])
    assert proposal['price_control_change'] == {
        'provider.max_price.prompt_usd_per_million': ['0.0033', '0.055'],
        'provider.max_price.completion_usd_per_million': ['3.3', '1.32']}
    assert [x['id'] for x in proposal['requests']] == s.IDS


def test_prepared_proposal_and_candidate_are_reviewable_without_admission(proposal):
    assert json.loads(s.MANIFEST.read_text()) == proposal
    candidate = json.loads(s.CANDIDATE.read_text())
    assert candidate['manifest_sha256'] == s.sha(s.MANIFEST)
    assert candidate['controller_sha256'] == s.sha(s.__file__)
    assert candidate['approved'] is False and candidate['independent_review'] is False
    assert candidate['inference_authorized'] is False


@pytest.mark.parametrize('field,rate', [
    ('prompt', '0.000000054999'), ('prompt', '0.000000055001'),
    ('completion', '0.00000131999'), ('completion', '0.00000132001'),
    ('input_cache_read', '0.0000000164')])
def test_live_gate_rejects_any_rate_drift_before_paid_state(field, rate, proposal):
    model, endpoint = s.route_context()
    endpoint['pricing'][field] = rate
    with patch.object(s.paid, 'fetch', side_effect=catalogs(endpoint, model)), \
         patch.object(s, 'verify', return_value=proposal), \
         patch.object(s, 'requests', return_value=proposal['requests']), \
         patch.object(s.paid, 'load_key') as key:
        with pytest.raises(ValueError):
            s.live_controls()
        key.assert_not_called()


@pytest.mark.parametrize('field,value', [('status', -2), ('tag', 'other/fp4'),
    ('context_length', 1048575), ('quantization', 'fp8')])
def test_live_gate_rejects_identity_or_availability_drift(field, value, proposal):
    model, endpoint = s.route_context()
    endpoint[field] = value
    with patch.object(s.paid, 'fetch', side_effect=catalogs(endpoint, model)), \
         patch.object(s, 'verify', return_value=proposal), \
         patch.object(s, 'requests', return_value=proposal['requests']):
        with pytest.raises(ValueError):
            s.live_controls()


def test_exact_live_route_passes_numerically_equivalent_prices(proposal):
    model, endpoint = s.route_context()
    endpoint['pricing']['prompt'] = '5.5000e-8'
    endpoint['pricing']['completion'] = '1.32000e-6'
    with patch.object(s.paid, 'fetch', side_effect=catalogs(endpoint, model)), \
         patch.object(s, 'verify', return_value=proposal), \
         patch.object(s, 'requests', return_value=proposal['requests']):
        assert s.live_controls() == (model, endpoint)


def test_private_runner_preserves_shared_frozen_globals():
    old = s.fourth.prior
    before = {k: getattr(old, k) for k in ('BASE', 'MANIFEST', 'PARTITION_ID', 'CHILD_CAP',
        'RESERVE', 'hold_authority', 'verify', '__file__')}
    core = s._private_core()
    assert core.BASE == s.BASE and core.RESERVE == s.RESERVE
    assert core.hold_authority is not old.hold_authority
    assert {k: getattr(old, k) for k in before} == before


def test_unapproved_review_blocks_before_any_key_network_or_paid_call(tmp_path):
    base = tmp_path / 'proposal'; base.mkdir()
    review = base / 'suffix.root-review.json'; review.write_text(json.dumps({'approved': False, 'reviewer': 'root'}))
    with patch.object(s, 'BASE', base), patch.object(s, '_private_core') as core, \
         patch.object(s.paid, 'fetch') as network, patch.object(s.paid, 'load_key') as key:
        with pytest.raises(ValueError, match='Independent root'):
            s.run(review, base / 'budget.json')
        core.assert_not_called(); network.assert_not_called(); key.assert_not_called()


def test_wrong_stage_review_path_is_rejected_without_reading_credentials(tmp_path):
    with patch.object(s.paid, 'load_key') as key:
        with pytest.raises(ValueError, match='Exact stage review path'):
            s.run(tmp_path / 'unreviewed.json', tmp_path / 'budget.json')
        key.assert_not_called()


def test_isolated_runner_uses_v2_hold_and_stops_before_key_on_cap_failure(tmp_path, proposal):
    base = tmp_path / 'current'; base.mkdir()
    manifest = base / 'manifest.json'; manifest.write_text(json.dumps(proposal))
    master = tmp_path / 'master.jsonl'; budget = base / 'budget.json'
    model, endpoint = s.route_context()
    core = s._private_core()
    with patch.object(s, 'BASE', base), patch.object(s, 'MANIFEST', manifest), \
         patch.object(s.admission, 'MASTER', master), \
         patch.object(s, 'verify', return_value=proposal), \
         patch.object(s, 'live_controls', return_value=(model, endpoint)):
        core = s._private_core()
        core.partitions.allocate(master, budget, [{'id': s.PARTITION_ID, 'cap_usd': str(s.CHILD_CAP),
            'model': s.admission.MODEL, 'provider': s.admission.PROVIDER, 'reasoning': 'low'}])
        source = core.global_hold_source(budget)
        review = base / 'suffix.root-review.json'
        review.write_text(json.dumps({'schema': s.SCHEMA + '-root-review', 'approved': True,
            'reviewer': 'root', 'manifest_sha256': s.sha(manifest), 'controller_sha256': s.sha(s.__file__),
            'prior_terminal_sha256': core.PRIOR_TERMINAL_SHA, 'budget_manifest_sha256': s.sha(budget),
            'partition_id': s.PARTITION_ID, 'child_cap_usd': str(s.CHILD_CAP), 'ids': s.IDS,
            'request_sha256': [r['request_sha256'] for r in proposal['requests']],
            'global_authority_head_sha256': 'a' * 64, 'global_hold_source_sha256': source}))
        with patch.object(s, '_private_core', return_value=core), \
             patch.object(s.authority_v2, 'hold_authority', side_effect=ValueError('Authority cap exhausted')) as hold, \
             patch.object(s.paid, 'load_key') as key:
            with pytest.raises(ValueError, match='Authority cap exhausted'):
                s.run(review, budget)
            assert hold.call_args.args[1:5] == (s.PARTITION_ID, str(s.CHILD_CAP), source, 'a' * 64)
            assert hold.call_args.kwargs['stage_path'] == base / 'suffix.claim.json'
            key.assert_not_called()
            assert not (base / 'suffix.claim.json').exists()

@pytest.mark.parametrize('first_status,cost,expected_count', [
    ('ok', '0.001', 10), ('invalid_output', '0.001', 10), ('ok', None, 1)])
def test_offline_simulation_preserves_invalid_and_unknown_without_replay(
        tmp_path, proposal, first_status, cost, expected_count):
    base = tmp_path / 'current'; base.mkdir()
    manifest = base / 'manifest.json'; manifest.write_text(json.dumps(proposal))
    master = tmp_path / 'master.jsonl'; budget = base / 'budget.json'
    model, endpoint = s.route_context()
    authority = tmp_path / 'authority.jsonl'
    authority.write_text(json.dumps(s.authority_v2.HEADER) + '\n')
    initial_head = s.sha(authority)
    original_hold = s.authority_v2.hold_authority
    sent = []

    def test_hold(*args, **kwargs):
        assert args[0] == authority
        return original_hold(*args, **kwargs, baseline_head=initial_head, baseline_events=1)

    def fake_transport(payload, token, timeout, raw, rid, attempt, request_sha):
        assert token == 'synthetic-offline-key'
        assert s.digest(json.dumps(payload, sort_keys=True)) == request_sha
        sent.append(rid)
        s.paid.durable(raw, {'id': rid, 'attempt_id': attempt, 'request_sha256': request_sha})
        return {'usage': {'cost': cost}, 'model': s.admission.MODEL, 'provider': 'OpenInference'}

    with patch.object(s, 'BASE', base), patch.object(s, 'MANIFEST', manifest), \
         patch.object(s.admission, 'MASTER', master), \
         patch.object(s, 'verify', return_value=proposal), \
         patch.object(s, 'live_controls', return_value=(model, endpoint)):
        core = s._private_core(); core.AUTHORITY = authority
        core.partitions.allocate(master, budget, [{'id': s.PARTITION_ID, 'cap_usd': str(s.CHILD_CAP),
            'model': s.admission.MODEL, 'provider': s.admission.PROVIDER, 'reasoning': 'low'}])
        source = core.global_hold_source(budget)
        review = base / 'suffix.root-review.json'
        review.write_text(json.dumps({'schema': s.SCHEMA + '-root-review', 'approved': True,
            'reviewer': 'root', 'manifest_sha256': s.sha(manifest), 'controller_sha256': s.sha(s.__file__),
            'prior_terminal_sha256': core.PRIOR_TERMINAL_SHA, 'budget_manifest_sha256': s.sha(budget),
            'partition_id': s.PARTITION_ID, 'child_cap_usd': str(s.CHILD_CAP), 'ids': s.IDS,
            'request_sha256': [r['request_sha256'] for r in proposal['requests']],
            'global_authority_head_sha256': initial_head, 'global_hold_source_sha256': source}))
        with patch.object(s, '_private_core', return_value=core), \
             patch.object(s.authority_v2, 'hold_authority', side_effect=test_hold), \
             patch.object(s.paid, 'load_key', return_value='synthetic-offline-key'), \
             patch.object(core.transport, 'fetch_recorded', side_effect=fake_transport), \
             patch.object(core.prior, '_body_result', side_effect=[
                 (first_status if i == 0 else 'ok', {}, None, 'stop') for i in range(10)]):
            outcome = s.run(review, budget)
    assert sent == s.IDS[:expected_count]
    records = [json.loads(x) for x in (base / 'suffix.records.jsonl').read_text().splitlines()]
    assert [x['id'] for x in records] == sent
    if cost is None:
        assert outcome == {'completed': False, 'status': 'unknown_cost', 'stopped_id': 'DEV-051'}
        assert records[0]['cost_unknown'] is True
    else:
        assert outcome == {'completed': True, 'count': 10}
        assert records[0]['status'] == first_status
    holds = [json.loads(x) for x in authority.read_text().splitlines()]
    assert holds[1:] == [{'event': 'hold', 'id': s.PARTITION_ID, 'usd': str(s.CHILD_CAP), 'source_sha256': source}]
    child = base / f'budget-{s.PARTITION_ID}.jsonl'
    reserves = [json.loads(x) for x in child.read_text().splitlines() if json.loads(x)['event'] == 'reserve']
    assert [x['record_id'] for x in reserves] == sent
    assert all(Decimal(x['usd']) == s.RESERVE for x in reserves)
