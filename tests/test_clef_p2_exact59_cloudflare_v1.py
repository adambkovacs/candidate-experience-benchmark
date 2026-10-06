"""Real frozen-loop tests for the Clef DEV-002–060 successor."""

import base64
import json
from pathlib import Path

import pytest

import clef_p2_exact59_cloudflare_v1 as suffix
import clef_native_preparation as prep
import clef_connected_app_bridge as bridge

ACCOUNT = '7455ff7abdb1d84bfd9f462f3645329c'


def fixture(tmp_path):
    (tmp_path / 'authority.jsonl').write_bytes(suffix.PARENT_AUTHORITY.read_bytes())
    head = suffix.digest(tmp_path / 'authority.jsonl')
    grant = tmp_path / 'grant.json'
    grant.write_text(json.dumps(suffix.grant_value(ACCOUNT, head), sort_keys=True))
    return grant


def response():
    path = suffix.ROOT / 'results/clef-native-v1/clef/fresh1/P1/smoke/raw.jsonl'
    return base64.b64decode(json.loads(path.read_bytes().splitlines()[0])['raw_response_base64'])


def options(tmp_path):
    return {'authority_path': tmp_path / 'authority.jsonl',
            'base': tmp_path / 'successor',
            'environment': {'CLOUDFLARE_ACCOUNT_ID': ACCOUNT,
                            'CLOUDFLARE_API_TOKEN': 'zzzzzz-only-test-token-999'},
            'billing_source': lambda _: (suffix.ROOT /
                'results/clef-native-v1/clef-billing-source.md').read_bytes()}


def test_exact_parent_and_all_59_frozen_payloads_complete_without_dev001(tmp_path):
    plan, _ = suffix.checked_plan()
    assert plan['request_ids'] == list(prep.IDS[1:])
    assert plan['parent_authority_hold_usd'] == '0.94374'
    assert plan['authority_policy'] == 'separate_conservative_hold_no_release_of_parent'
    assert len(plan['parent_file_bindings']) == 9
    grant = fixture(tmp_path)
    sent = []
    def fake(url, headers, body):
        index = len(sent)
        assert prep.sha(body) == plan['requests'][index]['payload_sha256']
        sent.append(plan['request_ids'][index])
        return 200, response()
    result = suffix.run(grant, transport=fake, **options(tmp_path))
    assert sent == list(prep.IDS[1:])
    assert result['status'] == 'complete' and result['attempted'] == 59
    assert result['counts'] == {'valid': 59, 'invalid_output': 0,
                                'service_error': 0, 'unknown_outcome': 0}
    hold = json.loads((tmp_path / 'authority.jsonl').read_bytes().splitlines()[-1])
    assert hold['id'] == suffix.HOLD_ID and hold['usd'] == '0.928011'
    with pytest.raises(ValueError, match='already claimed'):
        suffix.run(grant, transport=fake, **options(tmp_path))
    assert len(sent) == 59


def test_first_unknown_stops_and_retains_all_later_ids(tmp_path):
    grant = fixture(tmp_path)
    calls = []
    def unknown(*args):
        calls.append(1)
        raise TimeoutError('mocked unknown')
    result = suffix.run(grant, transport=unknown, **options(tmp_path))
    assert len(calls) == 1 and result['status'] == 'stopped'
    assert result['attempted'] == 1 and result['counts']['unknown_outcome'] == 1
    assert result['never_sent'] == list(prep.IDS[2:])
    assert json.loads((tmp_path / 'authority.jsonl').read_bytes().splitlines()[-1])['usd'] == '0.928011'


def test_dispatcher_source_drift_rejected_before_hold(monkeypatch):
    original = suffix.digest
    target = suffix.ROOT / 'scripts/clef_p2_exact59_cloudflare_v1.js'
    monkeypatch.setattr(suffix, 'digest', lambda path: '0' * 64 if Path(path) == target
                        else original(path))
    with pytest.raises(ValueError, match='plan differs'):
        suffix.checked_plan()


def test_parent_completion_or_account_change_is_rejected_before_hold(tmp_path, monkeypatch):
    original = suffix.digest
    target = suffix.PARENT / 'completion.json'
    monkeypatch.setattr(suffix, 'digest', lambda path: '0' * 64 if Path(path) == target
                        else original(path))
    with pytest.raises(ValueError, match='Parent'):
        suffix.plan_value()
    monkeypatch.setattr(suffix, 'digest', original)
    with pytest.raises(ValueError, match='Exact successor authority'):
        suffix.grant_value('0' * 32, '0' * 64)


def test_missing_parent_hold_stops_before_new_hold(tmp_path):
    grant = fixture(tmp_path)
    lines = (tmp_path / 'authority.jsonl').read_text().splitlines()
    lines = [line for line in lines if json.loads(line).get('id') != suffix.PARENT_HOLD_ID]
    (tmp_path / 'authority.jsonl').write_text('\n'.join(lines) + '\n')
    grant.write_text(json.dumps(suffix.grant_value(
        ACCOUNT, suffix.digest(tmp_path / 'authority.jsonl')), sort_keys=True))
    with pytest.raises(ValueError, match='Prior unknown'):
        suffix.run(grant, transport=lambda *_: (200, response()), **options(tmp_path))
    assert not (tmp_path / 'successor').exists()


def test_shared_cap_rejects_suffix_before_claim(tmp_path):
    grant = fixture(tmp_path)
    with (tmp_path / 'authority.jsonl').open('a') as handle:
        handle.write(json.dumps({'event': 'hold', 'id': 'other-reviewed-work',
                                 'usd': '4.0', 'grant_sha256': 'a' * 64}) + '\n')
    grant.write_text(json.dumps(suffix.grant_value(
        ACCOUNT, suffix.digest(tmp_path / 'authority.jsonl')), sort_keys=True))
    with pytest.raises(ValueError, match='cap exhausted'):
        suffix.run(grant, transport=lambda *_: (200, response()), **options(tmp_path))
    assert not (tmp_path / 'successor').exists()


@pytest.mark.parametrize('outcome', [
    'outer_tool_exception',
    'outer_returned_original_save_failed',
    'outer_returned_original_saved',
])
def test_client_mcp_timing_persists_with_explicit_provider_missingness(tmp_path, outcome):
    plan, _ = suffix.checked_plan()
    attempt = '123e4567-e89b-12d3-a456-426614174000'
    directory = tmp_path / 'app-bridge'
    directory.mkdir()
    request = directory / (attempt + '.request.json')
    rows, policy = prep.inputs_and_policy()
    body = prep.request_payload(rows[1]['feedback'], policy, 'clef', 'P2')
    ready = {'kind': bridge.KIND + '-request', 'attempt_id': attempt,
             'id': 'DEV-002', 'model': 'clef', 'stage': suffix.STAGE,
             'request_sha256': plan['requests'][0]['payload_sha256'],
             'body': body}
    assert prep.sha(prep.canonical(body)) == ready['request_sha256']
    bridge.atomic_json(request, ready)
    bridge.atomic_json(directory / (attempt + '.dispatch.json'),
                       {'operator': 'test', 'request_sha256': ready['request_sha256']})
    if outcome == 'outer_returned_original_saved':
        bridge.atomic_json(directory / (attempt + '.tool-result.original.json'),
                           {'content': [{'type': 'text', 'text': '{}'}]})
    path = suffix.record_timing(request, 1000, 1200, 180,
                                'performance_now_monotonic', outcome)
    saved = json.loads(path.read_bytes())
    assert saved['client_duration_ms'] == 180
    assert saved['outcome'] == outcome
    assert saved['provider_server_duration_ms'] is None
    with pytest.raises(ValueError, match='timing'):
        suffix.record_timing(request, 1000, 1200, -1,
                             'performance_now_monotonic', outcome)
