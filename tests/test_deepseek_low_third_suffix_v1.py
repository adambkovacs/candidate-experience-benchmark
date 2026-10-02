import copy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import deepseek_low_third_suffix_v1 as s
import openrouter_paid_benchmark as paid


def test_sealed_prefix_keeps_three_failures_and_ten_never_sent():
    _, evidence = s.prior_gate()
    assert evidence['prior_terminal']['sha256'] == s.PRIOR_TERMINAL_SHA
    assert s.IDS == [f'DEV-{n:03d}' for n in range(51, 61)]
    assert s.CHILD_CAP == Decimal('0.25')
    assert s.RESERVE == Decimal('0.1097728')


def test_request_changes_only_output_price_ceiling():
    selected = s.requests()
    assert [item['id'] for item in selected] == s.IDS
    assert all(item['old_request_sha256'] != item['request_sha256'] for item in selected)


def test_public_snapshot_and_manifest_recompute():
    audit = s.route_audit()
    assert audit['selected_endpoint']['pricing']['completion'] == '0.0000012'
    assert s.verify() == s.manifest_value()


def test_live_route_rejects_over_ceiling_without_key_or_inference():
    catalog = json.loads(s.RAW_MODELS.read_text())
    endpoints = json.loads(s.RAW_ENDPOINTS.read_text())
    endpoint = next(e for e in endpoints['data']['endpoints']
                    if e.get('tag') == s.admission.PROVIDER)
    endpoint['pricing']['completion'] = '0.00000121'
    def fetch(path, timeout):
        return endpoints if path.endswith('/endpoints') else catalog
    with patch.object(paid, 'fetch', side_effect=fetch):
        with pytest.raises(ValueError, match='price exceeds approved ceiling'):
            s.live_controls()


def test_prior_gate_rejects_a_reclassified_failure():
    original = s.prior.reconcile_suffix
    def changed(*args):
        result = copy.deepcopy(original(*args))
        result['status_counts']['service_error'] = 2
        return result
    with patch.object(s.prior, 'reconcile_suffix', side_effect=changed):
        with pytest.raises(ValueError, match='Sealed DEV-050 prefix differs'):
            s.prior_gate()


def test_global_hold_is_atomic_idempotent_and_child_bound(tmp_path):
    authority = tmp_path / 'authority.jsonl'
    header = {'event': 'authority', 'kind': 'postapproval-paid-work-v1',
              'cap_usd': str(s.AUTHORITY_CAP),
              'decision_key': s.AUTHORITY_DECISION_KEY,
              'approval_sha256': s.AUTHORITY_APPROVAL_SHA}
    authority.write_text(json.dumps(header) + '\n')
    head = hashlib.sha256(authority.read_bytes()).hexdigest()
    with patch.object(s, 'AUTHORITY', authority), \
         patch.object(s, 'global_hold_source', return_value='reviewed-child-source'):
        s.hold_authority(head, tmp_path / 'budget.json', 'reviewed-child-source')
        saved = authority.read_bytes()
        new_head = hashlib.sha256(saved).hexdigest()
        s.hold_authority(new_head, tmp_path / 'budget.json', 'reviewed-child-source')
        assert authority.read_bytes() == saved
        with pytest.raises(ValueError, match='source differs'):
            s.hold_authority(new_head, tmp_path / 'budget.json', 'other-child')
        with pytest.raises(ValueError, match='head changed'):
            s.hold_authority(head, tmp_path / 'budget.json', 'reviewed-child-source')


def test_global_hold_source_changes_with_child_or_budget(tmp_path):
    budget = tmp_path / 'budget.json'
    budget.write_text('{}')
    child = {'child_ledger': str(tmp_path / 'child-a.jsonl'),
             'model': s.admission.MODEL, 'provider': s.admission.PROVIDER,
             'reasoning': 'low', 'cap_usd': str(s.CHILD_CAP)}
    with patch.object(s, 'budget_entry', return_value=child):
        first = s.global_hold_source(budget)
        budget.write_text('{"changed":true}')
        second = s.global_hold_source(budget)
        child['child_ledger'] = str(tmp_path / 'child-b.jsonl')
        third = s.global_hold_source(budget)
    assert len({first, second, third}) == 3


def test_dispatch_requires_exact_stage_review_before_live(tmp_path):
    with pytest.raises(ValueError, match='Exact stage review path differs'):
        s.run(tmp_path / 'unreviewed.json', tmp_path / 'budget.json')


def test_transport_loop_preserves_order_and_stops_on_unknown_cost(tmp_path):
    base = tmp_path / 'suffix'
    base.mkdir()
    manifest_path = base / 'manifest.json'
    manifest_path.write_text('{}')
    budget = base / 'budget.json'
    budget.write_text('{}')
    payload = {'model': s.admission.MODEL, 'test': True}
    request_sha = s.digest(json.dumps(payload, sort_keys=True))
    manifest = {'requests': [dict(id=rid, request_sha256=request_sha,
                    input_sha256='input', instruction_sha256='policy')
                 for rid in s.IDS]}
    review = base / 'suffix.root-review.json'
    receipt = {'schema': s.SCHEMA + '-root-review', 'approved': True,
        'reviewer': '/root', 'manifest_sha256': s.sha(manifest_path),
        'controller_sha256': s.sha(s.__file__),
        'prior_terminal_sha256': s.PRIOR_TERMINAL_SHA,
        'budget_manifest_sha256': s.sha(budget),
        'partition_id': s.PARTITION_ID, 'child_cap_usd': str(s.CHILD_CAP),
        'ids': s.IDS, 'request_sha256': [request_sha] * 10,
        'global_authority_head_sha256': 'reviewed-head',
        'global_hold_source_sha256': 'reviewed-child'}
    review.write_text(json.dumps(receipt))

    class Child:
        cap = s.CHILD_CAP
        master_cap = Decimal('12.38')
        closed = False
        calls = 0
        def state(self): return {}, set(), False
        def accounted(self): return Decimal(0)
        def reserve(self, amount, rid):
            self.calls += 1
            return f'attempt-{self.calls}'
        def settle(self, attempt, actual): return actual is not None
        def close(self): pass

    def fetch_recorded(payload, token, timeout, raw, rid, attempt, request_sha):
        raw.write(json.dumps({'id': rid, 'attempt_id': attempt}) + '\n')
        raw.flush()
        return {'usage': {'cost': '0.0001'} if rid == 'DEV-051' else {},
                'model': s.admission.MODEL,
                'provider': 'OpenInference'}

    history, controls, _, _ = s.admission.source_state()
    with patch.object(s, 'BASE', base), patch.object(s, 'MANIFEST', manifest_path), \
         patch.object(s, 'verify', return_value=manifest), \
         patch.object(s, 'global_hold_source', return_value='reviewed-child'), \
         patch.object(s, 'hold_authority') as hold, \
         patch.object(s, 'live_controls', return_value=({}, {})), \
         patch.object(s.partitions, 'open_partition', return_value=Child()), \
         patch.object(s.paid, 'load_key', return_value='test-only'), \
         patch.object(s.frozen, 'load_manifest', return_value={}), \
         patch.object(s.admission, 'source_state', return_value=(history, controls, {}, {})), \
         patch.object(s, 'read_rows', return_value=[{'id': 'prior', 'feedback': 'prior'}] * 50 +
                                                    [{'id': rid, 'feedback': rid} for rid in s.IDS]), \
         patch.object(s.paid, 'make_payload', return_value=payload), \
         patch.object(s.transport, 'fetch_recorded', side_effect=fetch_recorded), \
         patch.object(s.prior, '_body_result', return_value=('ok', {}, None, 'stop')):
        outcome = s.run(review, budget)
        assert outcome == {'completed': False, 'status': 'unknown_cost',
                           'stopped_id': 'DEV-052'}
        records = s.rows(s.stage_paths()['records'])
        assert [r['id'] for r in records] == ['DEV-051', 'DEV-052']
        assert records[1]['cost_unknown'] is True
        assert records[1]['billing_ok'] is False
        hold.assert_called_once()
        with pytest.raises(FileExistsError, match='already claimed'):
            s.run(review, budget)
