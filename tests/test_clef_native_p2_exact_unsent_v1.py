"""Real frozen-loop tests for the Clef DEV-002–060 successor."""

import base64
import json
from pathlib import Path

import pytest

import clef_native_p2_exact_unsent_v1 as suffix
import clef_native_remaining_cloudflare_v1 as authority
import clef_native_preparation as prep
from clef_native_remaining_cloudflare_v2 import historical_inventory

ACCOUNT = '7455ff7abdb1d84bfd9f462f3645329c'


def fixture(tmp_path):
    with historical_inventory():
        head = authority.initialize(authority.BASE / 'initialization-review.json',
                                    path=tmp_path / 'authority.jsonl')
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
    assert len(plan['parent_file_bindings']) == 6
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
    target = suffix.ROOT / 'scripts/clef_cloudflare_dispatcher_v1.js'
    monkeypatch.setattr(suffix, 'digest', lambda path: '0' * 64 if Path(path) == target
                        else original(path))
    with pytest.raises(ValueError, match='plan differs'):
        suffix.checked_plan()
