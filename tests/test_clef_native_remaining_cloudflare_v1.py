"""Real temporary budget ledger with the frozen Clef request loop and fake HTTP."""

import base64
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import clef_native_remaining_cloudflare_v1 as adapter
import clef_native_preparation as prep


def fixture(tmp_path):
    plan, plan_hash = adapter.checked_plan()
    review = tmp_path / 'initialization-review.json'
    review.write_text(json.dumps({
        'kind': adapter.LEDGER_KIND + '-initialization-review',
        'approved': True, 'reviewer': '/root', 'cap_usd': '10.00',
        'plan_sha256': plan_hash,
        'historical_receipt_sha256': adapter.digest(adapter.HISTORICAL),
    }))
    ledger = tmp_path / 'authority.jsonl'
    head = adapter.initialize(review, path=ledger)
    account = 'a' * 32
    model, repeat, condition, phase = 'clef', 'fresh1', 'P2', 'smoke'
    grant = tmp_path / 'stage-grant.json'
    grant.write_text(json.dumps({
        'kind': adapter.KIND + '-stage-grant', 'approved': True,
        'authorized_by_user': True, 'reviewer': '/root',
        'model': model, 'pass': repeat, 'condition': condition, 'phase': phase,
        'stage': f'{model}/{repeat}/{condition}/{phase}',
        'plan_sha256': plan_hash,
        'frozen_manifest_sha256': plan['frozen_manifest_sha256'],
        'historical_receipt_sha256': plan['historical_receipt_sha256'],
        'controller_sha256': adapter.digest(adapter.__file__),
        'account_id_sha256': prep.sha(account.encode()),
        'transport': 'mcp__codex_apps__cloudflare_execute',
        'full_context_hold_usd': '0.047187', 'global_authority_cap_usd': '10.00',
        'smoke_review_sha256': None, 'prior_completion_sha256': None,
        'exhaustion_policy': 'pause', 'wait_seconds': 300,
        'billing_source_sha256': adapter.frozen.read_json(adapter.frozen.PROPOSAL)
            ['published_rate_sources'][model]['sha256'],
        'global_authority_ledger_sha256_at_admission': head,
    }))
    return ledger, grant, account


def historical_response(rid):
    path = adapter.ROOT / 'results/clef-native-v1/clef/fresh1/P1/smoke/raw.jsonl'
    for line in path.read_bytes().splitlines():
        item = json.loads(line)
        if item['id'] == rid:
            return base64.b64decode(item['raw_response_base64'])
    raise AssertionError(rid)


def test_plan_exact_and_restricted_to_five_never_sent_clef_cells():
    plan, _ = adapter.checked_plan()
    assert plan['allowed_stages'] == list(adapter.ALLOWED)
    assert len(plan['allowed_stages']) == 5
    assert plan['historical_upper_bound_usd'] == '0.259584'
    with pytest.raises(ValueError, match='Previously completed'):
        adapter.run_stage('clef', 'fresh1', 'P0', 'smoke', Path('unused'))


def test_real_temp_ledger_and_frozen_smoke_success(tmp_path):
    ledger, grant, account = fixture(tmp_path)
    requests = []

    def fake_http(url, headers, body):
        payload = json.loads(body)
        assert url.endswith('/ai/run/@cf/cloudflare/clef')
        assert payload['model'] == 'clef'
        rid = f'DEV-{len(requests)+1:03d}'
        requests.append(rid)
        return 200, historical_response(rid)

    result = adapter.run_stage('clef', 'fresh1', 'P2', 'smoke', grant,
                               authority_path=ledger, base=tmp_path / 'runs',
                               environment={'CLOUDFLARE_ACCOUNT_ID': account,
                                            'CLOUDFLARE_API_TOKEN': 'test-only'},
                               transport=fake_http,
                               billing_source=lambda _: (adapter.ROOT /
                                   'results/clef-native-v1/clef-billing-source.md').read_bytes())
    assert requests == ['DEV-001', 'DEV-002', 'DEV-003']
    assert result['status'] == 'complete' and result['counts']['valid'] == 3
    events = adapter.historical.rows(ledger)
    assert len(events) == 2 and events[1]['usd'] == '0.047187'
    with pytest.raises(ValueError, match='already claimed'):
        adapter.run_stage('clef', 'fresh1', 'P2', 'smoke', grant,
                          authority_path=ledger, base=tmp_path / 'runs',
                          environment={'CLOUDFLARE_ACCOUNT_ID': account,
                                       'CLOUDFLARE_API_TOKEN': 'test-only'},
                          transport=fake_http,
                          billing_source=lambda _: (adapter.ROOT /
                              'results/clef-native-v1/clef-billing-source.md').read_bytes())


def test_first_unknown_stops_without_retry_and_keeps_full_hold(tmp_path):
    ledger, grant, account = fixture(tmp_path)
    calls = []

    def unknown_http(url, headers, body):
        calls.append(body)
        raise TimeoutError('unknown test outcome')

    result = adapter.run_stage('clef', 'fresh1', 'P2', 'smoke', grant,
                               authority_path=ledger, base=tmp_path / 'runs',
                               environment={'CLOUDFLARE_ACCOUNT_ID': account,
                                            'CLOUDFLARE_API_TOKEN': 'test-only'},
                               transport=unknown_http,
                               billing_source=lambda _: (adapter.ROOT /
                                   'results/clef-native-v1/clef-billing-source.md').read_bytes())
    assert len(calls) == 1
    assert result['status'] == 'stopped' and result['attempted'] == 1
    assert result['never_sent'] == ['DEV-002', 'DEV-003']
    assert adapter.historical.rows(ledger)[1]['usd'] == '0.047187'


def test_cap_and_head_are_enforced_with_real_temp_ledger(tmp_path):
    ledger, grant, account = fixture(tmp_path)
    with pytest.raises(ValueError, match='head changed'):
        adapter.AuthorityLedger(ledger, None, '0'*64)
    budget = adapter.AuthorityLedger(ledger, None, adapter.digest(ledger))
    try:
        budget.hold('clef', 'fresh1', 'P2', 'smoke', 'a'*64)
        with pytest.raises(ValueError, match='Duplicate'):
            budget.hold('clef', 'fresh1', 'P2', 'smoke', 'a'*64)
        with pytest.raises(ValueError, match='Unapproved'):
            budget.hold('clef', 'fresh1', 'P0', 'smoke', 'a'*64)
    finally:
        budget.close()
