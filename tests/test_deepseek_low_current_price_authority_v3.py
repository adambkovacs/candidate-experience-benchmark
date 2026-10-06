"""Offline dispatch simulation using real temporary v4/v3 ledgers and locks."""
from decimal import Decimal
import json
from pathlib import Path
import sys
from unittest.mock import patch
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import deepseek_low_current_price_authority_v3 as s
import test_openrouter_budget_amendment_v3 as budget_fixture


@pytest.fixture(scope='module')
def proposal():
    return s.manifest_value()


def test_bridge_preserves_requests_history_and_supersedes_point_fifty_five(proposal):
    previous = s._historical_current_price().verify()
    assert proposal['requests'] == previous['requests']
    assert proposal['ids'] == [f'DEV-{n:03d}' for n in range(51, 61)]
    assert proposal['preserved_status_counts'] == previous['preserved_status_counts']
    assert proposal['preserved_failed_ids'] == previous['preserved_failed_ids']
    assert proposal['funding_pool'] == 'openrouter_additional'
    assert proposal['budget_master_cap_usd'] == '22.38'
    assert proposal['global_shared_cap_usd'] == '10.00'
    assert proposal['global_openrouter_additional_cap_usd'] == '10.00'
    assert proposal['authority_amendment']['prior_0_55_request_superseded'] is True
    assert proposal['inference_authorized'] is False
    assert proposal['reference_labels_read'] is False


def test_private_bridge_changes_only_cap_and_preserves_shared_modules():
    previous = s.prior._private_core()
    original = s.prior.fourth.prior
    before = {k: getattr(original, k) for k in ('run', 'BASE', 'MANIFEST', 'partitions', 'hold_authority')}
    core = s._private_core()
    assert core.run.__code__.co_consts == tuple('22.38' if value == '12.38' else value
                                               for value in previous.run.__code__.co_consts)
    assert core.run.__code__.co_code == previous.run.__code__.co_code
    assert core.run.__code__.co_names == previous.run.__code__.co_names
    assert core.run.__code__.co_varnames == previous.run.__code__.co_varnames
    assert core.partitions is s.partitions
    assert {k: getattr(original, k) for k in before} == before


def test_historical_prefix_is_private_and_live_master_stays_amended():
    original = s.prior.fourth.prior.prior
    historical = s._historical_current_price()._historical().prior.prior
    before = original.rows
    old_events = historical.rows(s.amendment.MASTER)
    live_events = original.rows(s.amendment.MASTER)
    assert [e['cap_usd'] for e in old_events if e['event'] == 'cap_amendment'][-1] == '12.38'
    assert [e['cap_usd'] for e in live_events if e['event'] == 'cap_amendment'][-1] == '22.38'
    assert original.rows is before
    old_events[0]['cap_usd'] = '999'
    assert historical.rows(s.amendment.MASTER)[0]['cap_usd'] != '999'


def test_historical_prefix_digest_must_match_reviewed_proposal(tmp_path):
    proposal = json.loads(s.AMENDMENT.read_text())
    proposal['master']['sha256'] = '0' * 64
    changed = tmp_path / 'proposal.json'; changed.write_text(json.dumps(proposal))
    with patch.object(s, 'AMENDMENT', changed):
        with pytest.raises(ValueError, match='original master prefix changed'):
            s._historical_current_price()


def test_unapproved_stage_stops_before_paid_surface(tmp_path):
    review = tmp_path / 'suffix.root-review.json'
    review.write_text(json.dumps({'approved': False, 'reviewer': 'root'}))
    with patch.object(s, 'BASE', tmp_path), patch.object(s, '_private_core') as core:
        with pytest.raises(ValueError, match='Independent root'): s.run(review, tmp_path / 'budget.json')
        core.assert_not_called()


@pytest.mark.parametrize('first_status,cost,count', [('ok', '0.001', 10),
    ('invalid_output', '0.001', 10), ('ok', None, 1)])
def test_real_amended_ledgers_feed_dispatch_and_keep_unknowns(proposal, first_status, cost, count):
    fixture = budget_fixture.AdditionalOpenRouterBudgetTest()
    fixture.setUp()
    try:
        fixture.activate()
        base = fixture.base / 'bridge'; base.mkdir()
        manifest = base / 'manifest.json'; manifest.write_text(json.dumps(proposal))
        budget = base / 'budget.json'
        model, endpoint = s.prior.route_context()
        sent = []
        original_hold = s.authority.hold_authority

        def hold(*args, **kwargs):
            assert args[0] == fixture.auth
            assert kwargs['funding_pool'] == 'openrouter_additional'
            return original_hold(*args, **kwargs, **fixture.baseline)

        def transport(payload, token, timeout, raw, rid, attempt, request_sha):
            assert token == 'synthetic-offline-key'
            assert s.prior.digest(json.dumps(payload, sort_keys=True)) == request_sha
            sent.append(rid)
            s.prior.paid.durable(raw, {'id': rid, 'attempt_id': attempt, 'request_sha256': request_sha})
            return {'usage': {'cost': cost}, 'model': s.prior.admission.MODEL, 'provider': 'OpenInference'}

        with patch.object(s, 'BASE', base), patch.object(s, 'MANIFEST', manifest), \
             patch.object(s.prior.admission, 'MASTER', fixture.master), \
             patch.object(s, 'verify', return_value=proposal), \
             patch.object(s, '_historical_current_price') as historical:
            historical.return_value.live_controls.return_value = (model, endpoint)
            core = s._private_core(); core.AUTHORITY = fixture.auth
            core.partitions.allocate(fixture.master, budget, [{'id': s.PARTITION_ID,
                'cap_usd': str(s.CHILD_CAP), 'model': s.prior.admission.MODEL,
                'provider': s.prior.admission.PROVIDER, 'reasoning': 'low'}])
            source = core.global_hold_source(budget)
            head = fixture.snapshot().head_sha256
            review = base / 'suffix.root-review.json'
            review.write_text(json.dumps({'schema': s.SCHEMA + '-root-review', 'approved': True,
                'reviewer': 'root', 'manifest_sha256': s.sha(manifest), 'controller_sha256': s.sha(s.__file__),
                'prior_terminal_sha256': core.PRIOR_TERMINAL_SHA, 'budget_manifest_sha256': s.sha(budget),
                'partition_id': s.PARTITION_ID, 'child_cap_usd': str(s.CHILD_CAP), 'ids': s.IDS,
                'request_sha256': [r['request_sha256'] for r in proposal['requests']],
                'global_authority_head_sha256': head, 'global_hold_source_sha256': source}))
            with patch.object(s, '_private_core', return_value=core), \
                 patch.object(s.authority, 'hold_authority', side_effect=hold), \
                 patch.object(s.prior.paid, 'load_key', return_value='synthetic-offline-key'), \
                 patch.object(core.transport, 'fetch_recorded', side_effect=transport), \
                 patch.object(core.prior, '_body_result', side_effect=[
                     (first_status if i == 0 else 'ok', {}, None, 'stop') for i in range(10)]):
                outcome = s.run(review, budget)
        assert sent == s.IDS[:count]
        assert fixture.snapshot().openrouter_accounted_usd == s.CHILD_CAP
        rows = [json.loads(line) for line in (base / 'suffix.records.jsonl').read_text().splitlines()]
        assert [r['id'] for r in rows] == sent
        if cost is None:
            assert outcome == {'completed': False, 'status': 'unknown_cost', 'stopped_id': 'DEV-051'}
            assert rows[0]['cost_unknown'] is True
            child = s.partitions.open_partition(fixture.master, budget, s.PARTITION_ID,
                s.prior.admission.MODEL, s.prior.admission.PROVIDER, 'low')
            try:
                assert child.state()[1]
                with pytest.raises(ValueError): child.reserve(Decimal('0.0630784'), 'DEV-052')
            finally: child.close()
        else:
            assert outcome == {'completed': True, 'count': 10}
            assert rows[0]['status'] == first_status
        with patch.object(s.prior.admission, 'MASTER', fixture.master), \
             patch.object(s.prior.paid, 'load_key') as key:
            with pytest.raises(FileExistsError): core.run(review, budget)
            key.assert_not_called()
    finally:
        fixture.doCleanups()
