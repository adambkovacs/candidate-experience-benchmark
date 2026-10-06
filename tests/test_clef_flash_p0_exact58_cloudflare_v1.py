"""Offline identity, money, and one-shot behavior for the Flash exact-58 successor."""

import hashlib
import json
from pathlib import Path
import shutil

import pytest

import clef_flash_p0_exact58_cloudflare_v1 as successor
import clef_native_preparation as prep


ACCOUNT = '7455ff7abdb1d84bfd9f462f3645329c'
IMMUTABLE_AUTHORITY = (successor.BASE /
    'cloudflare-budget-v1/authority-after-fresh3-p2-interruption.jsonl')


def test_plan_binds_only_unsent_flash_records():
    plan = successor.manifest_value()
    assert plan['request_ids'] == [f'DEV-{number:03d}' for number in range(3, 61)]
    assert plan['request_count'] == 58
    assert plan['hold_usd'] == str(prep.reservation_usd('clef-flash', 58))
    assert plan['reference_labels_sent'] is False
    assert len(plan['first_suffix_file_bindings']) == 11
    assert successor.checked_manifest()[0] == plan


def test_parent_unknown_boundary_tamper_refused(tmp_path):
    root = tmp_path / 'checkout'
    shutil.copytree(successor.BASE, root / successor.BASE.relative_to(successor.ROOT))
    for source in successor.SOURCE_FILES:
        target = root / source
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(successor.ROOT / source, target)
    assert successor.manifest_value(root)['request_count'] == 58
    first = root / successor.FIRST.relative_to(successor.ROOT) / 'completion.json'
    altered = json.loads(first.read_bytes())
    altered['never_sent'] = altered['never_sent'][1:]
    first.write_text(json.dumps(altered))
    with pytest.raises(ValueError):
        successor.manifest_value(root)


def _grant(tmp_path, authority):
    head = hashlib.sha256(authority.read_bytes()).hexdigest()
    path = tmp_path / 'grant.json'
    path.write_text(json.dumps(successor.grant_value(ACCOUNT, head), sort_keys=True) + '\n')
    return path


def _valid_response():
    smoke = successor.BASE / 'clef-flash/fresh3/P0/smoke/app-bridge'
    result = next(smoke.glob('*.app-result.json'))
    value = json.loads(result.read_bytes())
    assert value['status'] == 200 and value['success'] is True
    return result.read_bytes()


def test_real_temporary_authority_full_and_no_replay(tmp_path):
    authority = tmp_path / 'authority.jsonl'
    shutil.copy2(IMMUTABLE_AUTHORITY, authority)
    grant = _grant(tmp_path, authority)
    base = tmp_path / 'development'
    response = _valid_response()
    calls = []

    def transport(url, headers, body):
        calls.append(json.loads(body))
        return 200, response

    completed = successor.run_stage(successor.DEFAULT_MANIFEST, grant,
        base=base, authority_path=authority,
        environment={prep.ACCOUNT_ENV: ACCOUNT, prep.TOKEN_ENV: 'synthetic-test-token'},
        billing_source=lambda _: (successor.BASE / 'clef-flash-billing-source.md').read_bytes(),
        transport=transport, wait_seconds=300)
    assert completed['status'] == 'complete' and completed['attempted'] == 58
    assert completed['counts'] == {'valid': 58, 'invalid_output': 0,
                                    'service_error': 0, 'unknown_outcome': 0}
    assert len(calls) == 58
    assert [json.loads(line)['id'] for line in (base / 'records.jsonl').read_text().splitlines()] == plan_ids()
    events = [json.loads(line) for line in authority.read_bytes().splitlines()]
    assert events[-1] == {'event': 'hold', 'id': successor.HOLD_ID,
                          'usd': str(successor.HOLD),
                          'grant_sha256': hashlib.sha256(grant.read_bytes()).hexdigest()}
    with pytest.raises(ValueError):
        successor.run_stage(successor.DEFAULT_MANIFEST, grant,
            base=base, authority_path=authority,
            environment={prep.ACCOUNT_ENV: ACCOUNT, prep.TOKEN_ENV: 'synthetic-test-token'},
            billing_source=lambda _: (successor.BASE / 'clef-flash-billing-source.md').read_bytes(),
            transport=transport, wait_seconds=300)
    assert len(calls) == 58


def test_real_temporary_authority_unknown_stops_without_replay(tmp_path):
    authority = tmp_path / 'authority.jsonl'
    shutil.copy2(IMMUTABLE_AUTHORITY, authority)
    grant = _grant(tmp_path, authority)
    calls = []

    def transport(url, headers, body):
        calls.append(body)
        raise TimeoutError('synthetic unknown')

    completion = successor.run_stage(successor.DEFAULT_MANIFEST, grant,
        base=tmp_path / 'development', authority_path=authority,
        environment={prep.ACCOUNT_ENV: ACCOUNT, prep.TOKEN_ENV: 'synthetic-test-token'},
        billing_source=lambda _: (successor.BASE / 'clef-flash-billing-source.md').read_bytes(),
        transport=transport, wait_seconds=300)
    assert completion['status'] == 'stopped' and completion['attempted'] == 1
    assert completion['counts']['unknown_outcome'] == 1
    assert completion['never_sent'] == plan_ids()[1:]
    assert len(calls) == 1


def test_client_timing_is_durable_and_never_claims_server_time(tmp_path):
    attempt = '123e4567-e89b-12d3-a456-426614174000'
    request = tmp_path / f'{attempt}.request.json'
    request.write_text(json.dumps({
        'kind': 'clef-connected-app-bridge-v1-request', 'attempt_id': attempt,
        'id': 'DEV-003', 'model': 'clef-flash', 'stage': successor.STAGE,
        'request_sha256': 'a' * 64}) + '\n')
    dispatch = tmp_path / f'{attempt}.dispatch.json'
    dispatch.write_text(json.dumps({'request_sha256': 'a' * 64,
                                    'operator': '/root/qwen_recovery'}) + '\n')
    path = successor.record_timing(request, 1000, 1200, 180,
        'performance_now_monotonic', 'outer_returned_original_saved')
    saved = json.loads(path.read_bytes())
    assert saved['client_duration_ms'] == 180
    assert saved['provider_server_duration_ms'] is None
    with pytest.raises(FileExistsError):
        successor.record_timing(request, 1000, 1200, 180,
            'performance_now_monotonic', 'outer_returned_original_saved')
    with pytest.raises(ValueError):
        successor.record_timing(request, 1000, 1200, -1,
            'performance_now_monotonic', 'outer_tool_exception')


def plan_ids():
    return [f'DEV-{number:03d}' for number in range(3, 61)]
