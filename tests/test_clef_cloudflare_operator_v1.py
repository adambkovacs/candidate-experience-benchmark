"""A saved outer tool result is never lost on a parsing failure."""

import json

import pytest

import clef_cloudflare_operator_v1 as operator
import clef_connected_app_bridge as bridge
import clef_native_preparation as prep


def request(tmp_path, outer):
    attempt = '123e4567-e89b-12d3-a456-426614174000'
    path = tmp_path / f'{attempt}.request.json'
    bridge.atomic_json(path, {'kind': bridge.KIND + '-request',
                              'attempt_id': attempt, 'request_sha256': 'a' * 64})
    bridge.atomic_json(tmp_path / f'{attempt}.tool-result.original.json', outer)
    return path


def envelope():
    return {'status': 200, 'success': True, 'errors': [], 'messages': [],
            'result': {'model': 'clef', 'answers': {}}}


def test_missing_optional_iserror_yields_frozen_compatible_response(tmp_path):
    outer = {'content': [{'type': 'text', 'text': json.dumps(envelope())}]}
    path = request(tmp_path, outer)
    reply = operator.consume(path)
    assert reply.exists()
    assert bridge.read_json(path.with_name(path.name.replace('.request.json',
                      '.tool-result.original.json'))) == outer
    normalized = bridge.read_json(path.with_name(path.name.replace('.request.json',
                                   '.tool-result.json')))
    assert normalized['isError'] is False and normalized['content'] == outer['content']


@pytest.mark.parametrize('outer', [
    {'isError': True, 'content': [{'type': 'text', 'text': 'failed'}]},
    {'content': [{'type': 'text', 'text': json.dumps(envelope())},
                 {'type': 'text', 'text': 'another block'}]},
])
def test_error_or_multiple_blocks_preserve_original_and_do_not_reply(tmp_path, outer):
    path = request(tmp_path, outer)
    with pytest.raises(ValueError):
        operator.consume(path)
    attempt = bridge.read_json(path)['attempt_id']
    assert bridge.read_json(tmp_path / f'{attempt}.tool-result.original.json') == outer
    assert not (tmp_path / f'{attempt}.response.json').exists()
    assert not (tmp_path / f'{attempt}.app-result.json').exists()


def test_prepare_rejects_wrong_account_before_dispatch(tmp_path):
    account = 'a' * 32
    attempt = '123e4567-e89b-12d3-a456-426614174001'
    ready = {'kind': bridge.KIND + '-request', 'attempt_id': attempt,
             'id': 'DEV-002', 'model': 'clef', 'method': 'POST',
             'path': '/accounts/{ACCOUNT_ID}/ai/run/@cf/cloudflare/clef',
             'account_id_sha256': prep.sha(account.encode()),
             'request_sha256': 'a' * 64, 'body': {'model': 'clef'}}
    bridge.atomic_json(tmp_path / f'{attempt}.request.json', ready)
    with pytest.raises(ValueError, match='identity'):
        operator.prepare(tmp_path, 'b' * 32)
    assert not (tmp_path / f'{attempt}.dispatch.json').exists()
    assert operator.prepare(tmp_path, account) == ready
    assert (tmp_path / f'{attempt}.dispatch.json').exists()
