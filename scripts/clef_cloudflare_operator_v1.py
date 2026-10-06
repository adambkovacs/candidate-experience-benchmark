#!/usr/bin/env python3
"""Consume a durably saved Cloudflare app tool result without repeating its POST.

The caller must save the *original* outer result to ``.tool-result.original.json``
immediately after the tool returns. This module never invokes Cloudflare.
"""

import argparse
import json
from pathlib import Path

import clef_connected_app_bridge as bridge
import clef_native_preparation as prep
import clef_native_smoke_runner as smoke


def prepare(directory, account_id):
    directory = Path(directory)
    if (directory.parent / 'completion.json').exists():
        raise ValueError('Stage already terminal')
    pending = []
    for path in directory.glob('*.request.json'):
        attempt = path.name.removesuffix('.request.json')
        if not (directory / (attempt + '.dispatch.json')).exists():
            pending.append(path)
    if len(pending) != 1:
        raise ValueError('Expected exactly one durable, undispatched request')
    path = pending[0]
    ready = bridge.read_json(path)
    attempt = ready['attempt_id']
    if (path.name != attempt + '.request.json' or
            ready.get('kind') != bridge.KIND + '-request' or
            ready.get('account_id_sha256') != prep.sha(account_id.encode('ascii')) or
            ready.get('model') not in ('clef', 'clef-flash') or
            ready.get('method') != 'POST' or
            ready.get('path') != '/accounts/{ACCOUNT_ID}/ai/run/@cf/cloudflare/' + ready['model'] or
            not isinstance(ready.get('body'), dict) or
            ready['body'].get('model') != ready['model'] or
            any((directory / (attempt + suffix)).exists() for suffix in
                ('.response.json', '.tool-result.original.json', '.tool-result.json',
                 '.app-result.json'))):
        raise ValueError('Request identity or duplicate dispatch differs')
    bridge.atomic_json(directory / (attempt + '.dispatch.json'),
                       {'operator': '/root/qwen_recovery',
                        'request_sha256': ready['request_sha256']})
    return ready


def consume(request_path):
    request_path = Path(request_path)
    ready = bridge.read_json(request_path)
    attempt = ready['attempt_id']
    original_path = request_path.with_name(attempt + '.tool-result.original.json')
    normalized_path = request_path.with_name(attempt + '.tool-result.json')
    app_path = request_path.with_name(attempt + '.app-result.json')
    if not original_path.exists() or normalized_path.exists() or app_path.exists():
        raise ValueError('Original result absent or already consumed')
    original = bridge.read_json(original_path)
    if not isinstance(original, dict) or original.get('isError', False) is not False:
        raise ValueError('Original app tool result reports an error')
    blocks = original.get('content')
    if (not isinstance(blocks, list) or len(blocks) != 1 or
            not isinstance(blocks[0], dict) or blocks[0].get('type') != 'text' or
            not isinstance(blocks[0].get('text'), str)):
        raise ValueError('Ambiguous app result blocks; original preserved')
    envelope = json.loads(blocks[0]['text'])
    if (not isinstance(envelope, dict) or
            not {'status', 'success', 'errors', 'messages', 'result'} <= set(envelope) or
            type(envelope['status']) is not int or not 100 <= envelope['status'] <= 599 or
            type(envelope['success']) is not bool or
            not isinstance(envelope['errors'], list) or
            not isinstance(envelope['messages'], list)):
        raise ValueError('Original result lacks one exact Cloudflare envelope')
    # The frozen AppTransport reads the normalized bridge shape. A missing
    # optional MCP isError means false; the untouched original remains beside it.
    normalized = {'isError': False, 'content': blocks}
    bridge.atomic_json(normalized_path, normalized)
    bridge.atomic_json(app_path, envelope)
    return bridge.submit_response(request_path, app_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=('prepare', 'consume'))
    parser.add_argument('path', type=Path)
    parser.add_argument('--account-id')
    args = parser.parse_args()
    if args.command == 'prepare':
        if not args.account_id or not smoke.ACCOUNT_PATTERN.fullmatch(args.account_id):
            raise ValueError('Exact Cloudflare account ID required')
        print(json.dumps(prepare(args.path, args.account_id), separators=(',', ':')))
    else:
        print(consume(args.path))


if __name__ == '__main__':
    main()
