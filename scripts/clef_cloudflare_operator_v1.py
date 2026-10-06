#!/usr/bin/env python3
"""Consume a durably saved Cloudflare app tool result without repeating its POST.

The caller must save the *original* outer result to ``.tool-result.original.json``
immediately after the tool returns. This module never invokes Cloudflare.
"""

import argparse
import json
from pathlib import Path

import clef_connected_app_bridge as bridge


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
    parser.add_argument('request', type=Path)
    args = parser.parse_args()
    print(consume(args.request))


if __name__ == '__main__':
    main()
