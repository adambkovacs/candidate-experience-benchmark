from copy import deepcopy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import deepseek_low_fourth_price_suffix_v1 as s


def catalogs(endpoint=None, model=None):
    if endpoint is None or model is None:
        model, endpoint = s.route_context()
    return {'data': [deepcopy(model)]}, {
        'data': {'id': s.admission.MODEL, 'endpoints': [deepcopy(endpoint)]}}


@pytest.fixture(scope='module')
def manifest_value():
    return s.manifest_value()


def test_exact_ids_reserve_and_preserved_outcomes(manifest_value):
    value = manifest_value
    assert value['ids'] == [f'DEV-{n:03d}' for n in range(51, 61)]
    assert value['preserved_status_counts'] == {
        'ok': 46, 'invalid_output': 1, 'service_error': 3, 'never_sent': 10}
    assert value['preserved_failed_ids'] == ['DEV-040', 'DEV-049', 'DEV-050']
    assert value['preserved_invalid_ids'] == ['DEV-039']
    assert s.RESERVE == Decimal('0.0169771008')
    assert s.TOTAL_RESERVE == Decimal('0.169771008') < s.CHILD_CAP


def test_requests_change_only_both_exact_max_price_controls(manifest_value):
    selected = manifest_value['requests']
    assert [item['id'] for item in selected] == s.IDS
    assert all(item['old_request_sha256'] != item['request_sha256']
               for item in selected)
    assert s.INPUT_CEILING == Decimal('0.0033')
    assert s.OUTPUT_CEILING == Decimal('3.3')


def test_manifest_recomputes_from_frozen_sources(manifest_value):
    assert json.loads(s.MANIFEST.read_text()) == manifest_value
    assert s.sha(s.THIRD_MANIFEST) == s.PRIOR_MANIFEST_SHA


def test_superseding_public_snapshot_is_bound_as_blocker_only(manifest_value):
    audit, _, endpoint = s.blocking_route_receipt()
    assert audit['retrieved_utc'] == '2026-10-06T08:59:21.840862+00:00'
    assert endpoint['status'] == -2
    assert endpoint['pricing']['prompt'] == '0.0000000495'
    assert manifest_value['status'] == (
        'offline_prepared_current_route_blocked_no_allocation_or_dispatch')


@pytest.mark.parametrize(('field', 'value'), [
    ('prompt', '0.000000003299'),
    ('prompt', '0.000000003301'),
    ('completion', '0.000003299'),
    ('completion', '0.000003301'),
])
def test_live_route_rejects_any_nonexact_prompt_or_completion_rate(field, value):
    model, endpoint = s.route_context()
    endpoint['pricing'][field] = value
    catalog, endpoints = catalogs(endpoint, model)
    with patch.object(s.paid, 'fetch', side_effect=(catalog, endpoints)):
        with pytest.raises(ValueError):
            s.live_controls()


def test_live_route_rejects_identity_drift_before_paid_state():
    model, endpoint = s.route_context()
    endpoint['context_length'] -= 1
    catalog, endpoints = catalogs(endpoint, model)
    with patch.object(s.paid, 'fetch', side_effect=(catalog, endpoints)), \
         patch.object(s.prior.partitions, 'open_partition') as child, \
         patch.object(s.prior.paid, 'load_key') as key, \
         patch.object(s.prior.frozen, 'atomic_json') as claim:
        with pytest.raises(ValueError):
            s.live_controls()
        child.assert_not_called()
        key.assert_not_called()
        claim.assert_not_called()


def test_current_blocking_snapshot_cannot_pass_live_gate():
    catalog = json.loads(s.BLOCK_MODELS.read_text())
    endpoints = json.loads(s.BLOCK_ENDPOINTS.read_text())
    with patch.object(s.paid, 'fetch', side_effect=(catalog, endpoints)), \
         patch.object(s.prior.partitions, 'open_partition') as child, \
         patch.object(s.prior.paid, 'load_key') as key:
        with pytest.raises(ValueError):
            s.live_controls()
        child.assert_not_called()
        key.assert_not_called()


def test_exact_live_route_rebuilds_frozen_manifest_requests(manifest_value):
    model, endpoint = s.route_context()
    endpoint['pricing']['prompt'] = '3.3000e-9'
    endpoint['pricing']['completion'] = '3.300e-6'
    catalog, endpoints = catalogs(endpoint, model)
    with patch.object(s.paid, 'fetch', side_effect=(catalog, endpoints)), \
         patch.object(s, 'verify', return_value=manifest_value):
        assert s.live_controls() == (model, endpoint)


def test_runner_binding_uses_new_paths_prices_and_single_hold_id():
    with s._bind_prior_runner():
        assert s.prior.BASE == s.BASE
        assert s.prior.MANIFEST == s.MANIFEST
        assert s.prior.PARTITION_ID == s.PARTITION_ID
        assert s.prior.AUTHORITY_ID == s.PARTITION_ID
        assert s.prior.INPUT_CEILING == s.INPUT_CEILING
        assert s.prior.OUTPUT_CEILING == s.OUTPUT_CEILING
        assert s.prior.RESERVE == s.RESERVE
    assert s.prior.PARTITION_ID != s.PARTITION_ID


def test_dispatch_requires_exact_new_review_path_before_live(tmp_path, manifest_value):
    with patch.object(s, 'verify', return_value=manifest_value):
        with pytest.raises(ValueError, match='Exact stage review path differs'):
            s.run(tmp_path / 'unreviewed.json', tmp_path / 'budget.json')


def test_bound_runner_reaches_live_gate_before_child_key_or_claim(tmp_path, manifest_value):
    class ReachedLive(Exception):
        pass

    base = tmp_path / 'fourth'
    base.mkdir()
    manifest_path = base / 'manifest.json'
    budget = base / 'budget.json'
    budget.write_text('{}')
    value = manifest_value
    manifest_path.write_text(json.dumps(value) + '\n')
    review = base / 'suffix.root-review.json'
    receipt = {'schema': s.SCHEMA + '-root-review', 'approved': True,
        'reviewer': '/root', 'manifest_sha256': s.sha(manifest_path),
        'controller_sha256': s.sha(s.__file__),
        'prior_terminal_sha256': s.prior.PRIOR_TERMINAL_SHA,
        'budget_manifest_sha256': s.sha(budget),
        'partition_id': s.PARTITION_ID, 'child_cap_usd': str(s.CHILD_CAP),
        'ids': s.IDS,
        'request_sha256': [item['request_sha256'] for item in value['requests']],
        'global_authority_head_sha256': 'reviewed-head',
        'global_hold_source_sha256': 'reviewed-child'}
    review.write_text(json.dumps(receipt))
    with patch.object(s, 'BASE', base), patch.object(s, 'MANIFEST', manifest_path), \
         patch.object(s, 'live_controls', side_effect=ReachedLive), \
         patch.object(s.prior, 'global_hold_source', return_value='reviewed-child'), \
         patch.object(s.prior.partitions, 'open_partition') as child, \
         patch.object(s.prior.paid, 'load_key') as key, \
         patch.object(s.prior.frozen, 'atomic_json') as claim:
        with pytest.raises(ReachedLive):
            s.run(review, budget)
        child.assert_not_called()
        key.assert_not_called()
        claim.assert_not_called()


def test_bound_runner_completes_suffix_with_temporary_atomic_budgets(
        tmp_path, manifest_value):
    base = tmp_path / 'fourth'
    base.mkdir()
    manifest_path = base / 'manifest.json'
    manifest_path.write_text(json.dumps(manifest_value) + '\n')
    master = tmp_path / 'master.jsonl'
    budget = base / 'budget.json'
    s.prior.partitions.allocate(master, budget, [{
        'id': s.PARTITION_ID, 'cap_usd': str(s.CHILD_CAP),
        'model': s.admission.MODEL, 'provider': s.admission.PROVIDER,
        'reasoning': 'low'}])
    child_path = base / f'budget-{s.PARTITION_ID}.jsonl'
    authority = tmp_path / 'authority.jsonl'
    authority.write_text(json.dumps({
        'event': 'authority', 'kind': 'postapproval-paid-work-v1',
        'cap_usd': str(s.prior.AUTHORITY_CAP),
        'decision_key': s.prior.AUTHORITY_DECISION_KEY,
        'approval_sha256': s.prior.AUTHORITY_APPROVAL_SHA}) + '\n')
    authority_head = hashlib.sha256(authority.read_bytes()).hexdigest()
    model, endpoint = s.route_context()
    sent = []

    def fake_transport(payload, token, timeout, raw, rid, attempt, request_sha):
        assert token == 'offline-test-key'
        assert timeout == 300
        assert s.digest(json.dumps(payload, sort_keys=True)) == request_sha
        sent.append(rid)
        s.paid.durable(raw, {'id': rid, 'attempt_id': attempt,
                             'request_sha256': request_sha})
        return {'usage': {'cost': '0.001'}, 'model': s.admission.MODEL,
                'provider': 'OpenInference'}

    with patch.object(s, 'BASE', base), patch.object(s, 'MANIFEST', manifest_path), \
         patch.object(s.admission, 'MASTER', master), \
         patch.object(s.prior, 'AUTHORITY', authority), \
         patch.object(s, 'verify', return_value=manifest_value), \
         patch.object(s, 'live_controls', return_value=(model, endpoint)), \
         patch.object(s.prior.paid, 'load_key', return_value='offline-test-key'), \
         patch.object(s.prior.transport, 'fetch_recorded', side_effect=fake_transport), \
         patch.object(s.prior.prior, '_body_result', return_value=('ok', {}, None, 'stop')):
        source = s.global_hold_source(budget)
        review = base / 'suffix.root-review.json'
        review.write_text(json.dumps({
            'schema': s.SCHEMA + '-root-review', 'approved': True,
            'reviewer': '/root', 'manifest_sha256': s.sha(manifest_path),
            'controller_sha256': s.sha(s.__file__),
            'prior_terminal_sha256': s.prior.PRIOR_TERMINAL_SHA,
            'budget_manifest_sha256': s.sha(budget),
            'partition_id': s.PARTITION_ID,
            'child_cap_usd': str(s.CHILD_CAP), 'ids': s.IDS,
            'request_sha256': [item['request_sha256']
                               for item in manifest_value['requests']],
            'global_authority_head_sha256': authority_head,
            'global_hold_source_sha256': source}) + '\n')
        assert s.run(review, budget) == {'completed': True, 'count': 10}

    assert sent == s.IDS
    events = [json.loads(line) for line in child_path.read_text().splitlines()]
    reserves = [event for event in events if event['event'] == 'reserve']
    settles = [event for event in events if event['event'] == 'settle']
    assert [event['record_id'] for event in reserves] == s.IDS
    assert len(settles) == 10
    assert {event['attempt_id'] for event in reserves} == {
        event['attempt_id'] for event in settles}
    assert all(Decimal(event['usd']) == s.RESERVE for event in reserves)
    assert sum((Decimal(event['usd']) for event in settles), Decimal(0)) == Decimal('0.010')
    assert [json.loads(line)['id'] for line in
            (base / 'suffix.records.jsonl').read_text().splitlines()] == s.IDS
    holds = [json.loads(line) for line in authority.read_text().splitlines()]
    assert holds[1:] == [{'event': 'hold', 'id': s.PARTITION_ID,
                           'source_sha256': source, 'usd': str(s.CHILD_CAP)}]
