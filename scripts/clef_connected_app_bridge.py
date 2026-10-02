#!/usr/bin/env python3
"""File handoff for a reviewed Cloudflare app call after Clef's durable reserve.

The parent operator executes each ready request through the connected Cloudflare
app and submits its actual REST envelope. This process never calls the app or
retries an attempt. A missing or malformed reply becomes an unknown outcome in
the frozen smoke runner.
"""

import argparse
import base64
import json
import os
from pathlib import Path
import time
from urllib.parse import urlparse
import uuid

import clef_native_preparation as prep
import clef_native_smoke_runner as smoke

KIND = 'clef-connected-app-bridge-v1'
REVIEW_KIND = 'clef-connected-app-bridge-review-v1'
MAX_WAIT_SECONDS = 600


def read_json(path):
    return json.loads(Path(path).read_bytes())


def atomic_json(path, value):
    """Publish a complete immutable handoff file under its final name."""
    path = Path(path)
    temporary = path.with_name('.' + path.name + '.' + str(uuid.uuid4()) + '.tmp')
    try:
        with temporary.open('xb') as handle:
            smoke.durable(handle, value)
        os.link(temporary, path)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def checked_review(path, *, model, manifest, grant, account_id, wait_seconds):
    raw = Path(path).read_bytes()
    review = json.loads(raw)
    expected = {'kind': REVIEW_KIND, 'approved': True,
                'transport': 'mcp__codex_apps__cloudflare_execute', 'model': model,
                'stage': smoke.STAGE, 'manifest_sha256': prep.sha(Path(manifest).read_bytes()),
                'grant_sha256': prep.sha(Path(grant).read_bytes()),
                'runner_sha256': prep.sha(Path(smoke.__file__).read_bytes()),
                'bridge_sha256': prep.sha(Path(__file__).read_bytes()),
                'account_id_sha256': prep.sha(account_id.encode('ascii')),
                'wait_seconds': wait_seconds}
    if (not isinstance(review, dict) or set(review) != set(expected) | {'reviewer'} or
            any(review.get(key) != value for key, value in expected.items()) or
            not isinstance(review.get('reviewer'), str) or not review['reviewer'].strip()):
        raise ValueError('Exact reviewed connected-app bridge receipt required')
    return prep.sha(raw)


class AppBridgeTransport:
    def __init__(self, output_root, model, account_id, review_hash, wait_seconds=300,
                 poll_seconds=0.1):
        if model not in prep.MODELS or not smoke.ACCOUNT_PATTERN.fullmatch(account_id):
            raise ValueError('Unpinned model or account')
        if (type(wait_seconds) is not int or not 1 <= wait_seconds <= MAX_WAIT_SECONDS or
                poll_seconds <= 0):
            raise ValueError('Invalid bounded wait')
        self.output_root = Path(output_root)
        self.model = model
        self.account_id = account_id
        self.review_hash = review_hash
        self.wait_seconds = wait_seconds
        self.poll_seconds = poll_seconds
        self.stage_dir = self.output_root / model / 'fresh1' / 'P0' / 'smoke'
        self.bridge_dir = self.stage_dir / 'app-bridge'

    def __call__(self, url, headers, body):
        # The bearer token passed by the frozen runner is deliberately ignored.
        expected_path = f'/client/v4/accounts/{self.account_id}/ai/run/{prep.MODELS[self.model]["route"]}'
        parsed_url = urlparse(url)
        if (parsed_url.scheme != 'https' or parsed_url.netloc != 'api.cloudflare.com' or
                parsed_url.path != expected_path or parsed_url.query or parsed_url.fragment or
                headers.get('Content-Type') != 'application/json' or
                headers.get('Accept') != 'application/json' or
                not headers.get('Authorization', '').startswith('Bearer ') or
                not isinstance(body, bytes)):
            raise ValueError('Unpinned Cloudflare transport request')
        payload = json.loads(body)
        if payload.get('model') != self.model:
            raise ValueError('Unpinned Cloudflare model payload')
        journal_path = self.stage_dir / 'journal.jsonl'
        journal = [json.loads(line) for line in journal_path.read_bytes().splitlines()]
        if (len(journal) < 2 or journal[-2].get('event') != 'reserved' or
                journal[-1].get('event') != 'started' or
                journal[-2]['attempt_id'] != journal[-1]['attempt_id'] or
                journal[-2]['id'] != journal[-1]['id'] or
                journal[-2]['request_sha256'] != prep.sha(body)):
            raise ValueError('No matching durable started request')
        reserved, started = journal[-2:]
        ledger = [json.loads(line) for line in (self.output_root / 'budget.jsonl').read_bytes().splitlines()]
        if (not ledger or ledger[-1].get('event') != 'reserve' or
                any(ledger[-1].get(key) != reserved.get(key) for key in ('attempt_id', 'id', 'usd')) or
                ledger[-1].get('model') != self.model or ledger[-1].get('stage') != smoke.STAGE):
            raise ValueError('No matching durable budget reservation')
        self.bridge_dir.mkdir(exist_ok=True)
        attempt_id = started['attempt_id']
        request_path = self.bridge_dir / f'{attempt_id}.request.json'
        response_path = self.bridge_dir / f'{attempt_id}.response.json'
        ready = {'kind': KIND + '-request', 'attempt_id': attempt_id,
                 'id': started['id'], 'model': self.model, 'stage': smoke.STAGE,
                 'review_sha256': self.review_hash,
                 'account_id_sha256': prep.sha(self.account_id.encode('ascii')),
                 'request_sha256': prep.sha(body), 'method': 'POST',
                 'path': '/accounts/{ACCOUNT_ID}/ai/run/' + prep.MODELS[self.model]['route'],
                 'body': payload}
        atomic_json(request_path, ready)
        deadline = time.monotonic() + self.wait_seconds
        while time.monotonic() < deadline:
            try:
                with response_path.open('rb') as handle:
                    raw = handle.read(smoke.MAX_RESPONSE_BYTES + 4096)
            except FileNotFoundError:
                time.sleep(self.poll_seconds)
                continue
            if len(raw) > smoke.MAX_RESPONSE_BYTES + 4096:
                raise ValueError('Bridge response too large')
            reply = json.loads(raw)
            if (not isinstance(reply, dict) or set(reply) !=
                    {'kind', 'attempt_id', 'request_sha256', 'http_status', 'body_base64'} or
                    reply['kind'] != KIND + '-response' or
                    reply['attempt_id'] != attempt_id or
                    reply['request_sha256'] != ready['request_sha256'] or
                    type(reply['http_status']) is not int or
                    not 100 <= reply['http_status'] <= 599 or
                    not isinstance(reply['body_base64'], str)):
                raise ValueError('Malformed or mismatched bridge response')
            response = base64.b64decode(reply['body_base64'], validate=True)
            if len(response) > smoke.MAX_RESPONSE_BYTES:
                raise ValueError('Bridge response too large')
            return reply['http_status'], response
        raise TimeoutError('Connected-app response absent; outcome unknown; do not retry')


def submit_response(request_path, app_result_path):
    """Save one exact serialized cloudflare.request() result after operator review."""
    request_path = Path(request_path)
    ready = read_json(request_path)
    if (not isinstance(ready, dict) or ready.get('kind') != KIND + '-request' or
            request_path.name != ready.get('attempt_id', '') + '.request.json' or
            not isinstance(ready.get('request_sha256'), str)):
        raise ValueError('Invalid ready request')
    body = Path(app_result_path).read_bytes()
    if len(body) > smoke.MAX_RESPONSE_BYTES:
        raise ValueError('Bridge response too large')
    result = json.loads(body)
    if (not isinstance(result, dict) or
            not {'status', 'success', 'errors', 'messages', 'result'} <= set(result) or
            type(result['status']) is not int or not 100 <= result['status'] <= 599 or
            type(result['success']) is not bool or
            not isinstance(result['errors'], list) or
            not isinstance(result['messages'], list)):
        raise ValueError('Expected exact connected-app Cloudflare response object')
    # These are serialized app-result bytes, not captured HTTP wire bytes. The
    # frozen runner saves them in raw.jsonl and applies its strict REST parser.
    reply = {'kind': KIND + '-response', 'attempt_id': ready['attempt_id'],
             'request_sha256': ready['request_sha256'], 'http_status': result['status'],
             'body_base64': base64.b64encode(body).decode('ascii')}
    path = request_path.with_name(ready['attempt_id'] + '.response.json')
    atomic_json(path, reply)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('run')
    run.add_argument('--execute', action='store_true', required=True)
    run.add_argument('--model', choices=list(prep.MODELS), required=True)
    run.add_argument('--manifest', type=Path, required=True)
    run.add_argument('--grant', type=Path, required=True)
    run.add_argument('--review', type=Path, required=True)
    run.add_argument('--env-file', type=Path)
    run.add_argument('--wait-seconds', type=int, default=300)
    submit = sub.add_parser('submit')
    submit.add_argument('--request', type=Path, required=True)
    submit.add_argument('--app-result-file', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'submit':
        print(submit_response(args.request, args.app_result_file))
        return
    account_id, token = smoke.credentials(os.environ, args.env_file)
    if (not isinstance(account_id, str) or not smoke.ACCOUNT_PATTERN.fullmatch(account_id) or
            not isinstance(token, str) or not token.strip()):
        raise ValueError('Cloudflare account ID or token unavailable')
    if type(args.wait_seconds) is not int or not 1 <= args.wait_seconds <= MAX_WAIT_SECONDS:
        raise ValueError('Invalid bounded wait')
    review_hash = checked_review(args.review, model=args.model, manifest=args.manifest,
                                 grant=args.grant, account_id=account_id,
                                 wait_seconds=args.wait_seconds)
    bridge = AppBridgeTransport(smoke.ROOT / smoke.BASE, args.model, account_id,
                                review_hash, args.wait_seconds)
    result = smoke.run_smoke(args.model, args.manifest, args.grant, env_file=args.env_file,
                             transport=bridge)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
