#!/usr/bin/env python3
"""Reviewed Clef fresh1/P0 60-record development continuation. No retries."""

import argparse
import base64
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path
import time
import uuid
from urllib.parse import urlparse

import clef_native_preparation as prep
import clef_native_smoke_runner as smoke
import clef_connected_app_bridge as bridge
import inspect_clef_native_smoke as inspection

BASE = prep.ROOT / smoke.BASE
STAGE = 'fresh1/P0/development'
GLOBAL_CAP = Decimal('10.00')
DEVELOPMENT_CAP = Decimal('1.30')
AUTHORITY_KEY = 'candidate-experience-benchmark/user-ten-dollar-tests-20261002'
APPROVAL_TEXT = "you're approved to run tests and live runs up to 10 dollars overall"
APPROVAL_SHA256 = prep.sha(APPROVAL_TEXT.encode('utf-8'))
AUTHORITY_LEDGER = prep.ROOT / 'results/postapproval-paid-work-2026-10-02.jsonl'
DEVELOPMENT_LEDGER = BASE / 'development-budget.jsonl'
GEMMA_BUDGET = prep.ROOT / ('results/repeatability-v1/gemma26-on-fresh-matched3-v2/'
                            'fifth-suffix-017-046-v1/budget.json')


def manifest_value():
    plan = prep.build_plan()
    smoke_receipt = inspection.inspect()
    saved = json.loads(inspection.OUTPUT.read_bytes())
    if saved != smoke_receipt:
        raise ValueError('Smoke inspection no longer matches saved evidence')
    return {'kind': 'clef-native-full-p0-manifest-v1', 'stage': STAGE,
            'records': 60, 'models': {model: {'route': prep.MODELS[model]['route'],
            'ids': list(prep.IDS),
            'requests': plan['models'][model]['requests']['P0'],
            'full_context_reservation_usd': str(prep.reservation_usd(model, 60))}
            for model in prep.MODELS},
            'total_full_context_reservation_usd': str(sum(
                (prep.reservation_usd(model, 60) for model in prep.MODELS), Decimal(0))),
            'development_cap_usd': str(DEVELOPMENT_CAP),
            'global_new_authority_cap_usd': str(GLOBAL_CAP),
            'preparation_sha256': prep.sha((BASE / 'preparation.json').read_bytes()),
            'smoke_inspection_sha256': prep.sha(inspection.OUTPUT.read_bytes()),
            'smoke_inspector_sha256': prep.sha(Path(inspection.__file__).read_bytes()),
            'controller_sha256': prep.sha(Path(__file__).read_bytes()),
            'bridge_sha256': prep.sha(Path(bridge.__file__).read_bytes()),
            'transport': 'mcp__codex_apps__cloudflare_execute'}


def checked_manifest(path):
    saved = json.loads(Path(path).read_bytes())
    expected = manifest_value()
    if saved != expected:
        raise ValueError('Full P0 manifest differs from frozen sources')
    return prep.sha(Path(path).read_bytes())


def checked_grant(path, *, model, manifest_hash, account_id, wait_seconds,
                  billing_fetcher=smoke.billing_fetch):
    raw = Path(path).read_bytes()
    grant = json.loads(raw)
    expected = {'kind': 'clef-native-full-p0-grant-v1', 'approved': True,
                'authorized_by_user': True, 'model': model, 'stage': STAGE,
                'manifest_sha256': manifest_hash,
                'controller_sha256': prep.sha(Path(__file__).read_bytes()),
                'bridge_sha256': prep.sha(Path(bridge.__file__).read_bytes()),
                'smoke_inspector_sha256': prep.sha(Path(inspection.__file__).read_bytes()),
                'smoke_inspection_sha256': prep.sha(inspection.OUTPUT.read_bytes()),
                'account_id_sha256': prep.sha(account_id.encode('ascii')),
                'transport': 'mcp__codex_apps__cloudflare_execute',
                'full_context_reservation_usd': str(prep.reservation_usd(model, 60)),
                'development_cap_usd': str(DEVELOPMENT_CAP),
                'global_authority_cap_usd': str(GLOBAL_CAP),
                'exhaustion_policy': 'pause', 'wait_seconds': wait_seconds}
    extra = {'reviewer', 'global_authority_approval_sha256',
             'global_authority_ledger_sha256_at_admission', 'billing_source_sha256'}
    if (not isinstance(grant, dict) or set(grant) != set(expected) | extra or
            any(grant.get(key) != value for key, value in expected.items()) or
            not isinstance(grant.get('reviewer'), str) or not grant['reviewer'].strip() or
            not isinstance(grant.get('global_authority_approval_sha256'), str) or
            grant['global_authority_approval_sha256'] != APPROVAL_SHA256 or
            not isinstance(grant.get('global_authority_ledger_sha256_at_admission'), str) or
            len(grant['global_authority_ledger_sha256_at_admission']) != 64 or
            not isinstance(grant.get('billing_source_sha256'), dict) or
            set(grant['billing_source_sha256']) != set(prep.MODELS)):
        raise ValueError('Exact reviewed full P0 grant required')
    for name, spec in prep.MODELS.items():
        observed = billing_fetcher(spec['source'])
        if prep.sha(observed) != grant['billing_source_sha256'][name]:
            raise ValueError('Reviewed billing source changed')
    return grant, prep.sha(raw)


class GlobalAuthorityLedger:
    """Monotonic cross-provider holds against the postapproval $10 ceiling."""

    def __init__(self, path, approval_hash, expected_head_hash):
        self.path = Path(path)
        self.handle = self.path.open('r+b')  # Root creates and reviews this ledger.
        try:
            fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.handle.seek(0)
            raw = self.handle.read()
            if (not raw or not raw.endswith(b'\n') or
                    prep.sha(raw) != expected_head_hash):
                raise ValueError('Global authority ledger head changed')
            events = [json.loads(line) for line in raw.splitlines()]
            if events[0] != {'event': 'authority', 'kind': 'postapproval-paid-work-v1',
                             'cap_usd': str(GLOBAL_CAP),
                             'decision_key': AUTHORITY_KEY,
                             'approval_sha256': approval_hash}:
                raise ValueError('Global authority provenance differs')
            holds = {}
            total = Decimal(0)
            for event in events[1:]:
                if (set(event) != {'event', 'id', 'usd', 'source_sha256'} or
                        event['event'] != 'hold' or event['id'] in holds or
                        not isinstance(event['source_sha256'], str) or
                        len(event['source_sha256']) != 64):
                    raise ValueError('Global authority hold differs')
                amount = Decimal(event['usd'])
                if not amount.is_finite() or amount <= 0:
                    raise ValueError('Invalid global authority amount')
                holds[event['id']] = event
                total += amount
            smoke_hold = holds.get('cloudflare-initial-smoke')
            gemma_hold = holds.get('openrouter-gemma-fifth')
            if (smoke_hold != {'event': 'hold', 'id': 'cloudflare-initial-smoke',
                               'usd': '0.064884',
                               'source_sha256': prep.sha((BASE / 'budget.jsonl').read_bytes())} or
                    gemma_hold != {'event': 'hold', 'id': 'openrouter-gemma-fifth',
                                   'usd': '0.60',
                                   'source_sha256': prep.sha(GEMMA_BUDGET.read_bytes())} or
                    total > GLOBAL_CAP):
                raise ValueError('Initial cross-provider holds absent or over cap')
            self.holds, self.total = holds, total
            self.handle.seek(0, os.SEEK_END)
        except BaseException:
            self.handle.close()
            raise

    def hold(self, model, grant_hash):
        hold_id = 'cloudflare-' + model + '-fresh1-p0-development'
        amount = prep.reservation_usd(model, 60)
        if hold_id in self.holds or self.total + amount > GLOBAL_CAP:
            raise ValueError('Global authority exhausted or duplicate stage')
        event = {'event': 'hold', 'id': hold_id, 'usd': str(amount),
                 'source_sha256': grant_hash}
        smoke.durable(self.handle, event)
        self.holds[hold_id] = event
        self.total += amount
        return event

    def close(self):
        self.handle.close()


class DevelopmentLedger:
    def __init__(self, path, manifest_hash, approval_hash):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = path.open('a+b')
        try:
            fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.handle.seek(0)
            raw = self.handle.read()
            if raw and not raw.endswith(b'\n'):
                raise ValueError('Incomplete development ledger')
            events = [json.loads(line) for line in raw.splitlines()]
            header = {'event': 'budget', 'cap_usd': str(DEVELOPMENT_CAP),
                      'manifest_sha256': manifest_hash,
                      'global_authority_approval_sha256': approval_hash}
            if not events:
                smoke.durable(self.handle, header)
                events = [header]
            if events[0] != header:
                raise ValueError('Development ledger provenance differs')
            self.total = Decimal(0)
            self.seen = set()
            self.attempts = set()
            for event in events[1:]:
                if (set(event) != {'event', 'attempt_id', 'model', 'id', 'stage', 'usd'} or
                        event['event'] != 'reserve' or event['model'] not in prep.MODELS or
                        event['id'] not in prep.IDS or event['stage'] != STAGE or
                        event['attempt_id'] in self.attempts or
                        (event['model'], event['id']) in self.seen or
                        Decimal(event['usd']) != prep.reservation_usd(event['model'], 1)):
                    raise ValueError('Development reservation differs')
                self.seen.add((event['model'], event['id']))
                self.attempts.add(event['attempt_id'])
                self.total += Decimal(event['usd'])
            if self.total > DEVELOPMENT_CAP:
                raise ValueError('Development cap exceeded')
            self.handle.seek(0, os.SEEK_END)
        except BaseException:
            self.handle.close()
            raise

    def reserve(self, model, rid):
        amount = prep.reservation_usd(model, 1)
        if (model, rid) in self.seen or self.total + amount > DEVELOPMENT_CAP:
            raise ValueError('Development cap exhausted or request already reserved')
        attempt_id = str(uuid.uuid4())
        smoke.durable(self.handle, {'event': 'reserve', 'attempt_id': attempt_id,
                                    'model': model, 'id': rid, 'stage': STAGE,
                                    'usd': str(amount)})
        self.seen.add((model, rid))
        self.attempts.add(attempt_id)
        self.total += amount
        return attempt_id, amount

    def close(self):
        self.handle.close()


class DevelopmentAppTransport:
    def __init__(self, directory, ledger_path, model, account_id, grant_hash,
                 wait_seconds=300, poll_seconds=0.1):
        self.directory = Path(directory)
        self.ledger_path = Path(ledger_path)
        self.model = model
        self.account_id = account_id
        self.grant_hash = grant_hash
        self.wait_seconds = wait_seconds
        self.poll_seconds = poll_seconds

    def __call__(self, url, headers, body):
        expected_path = f'/client/v4/accounts/{self.account_id}/ai/run/{prep.MODELS[self.model]["route"]}'
        parsed_url = urlparse(url)
        if (parsed_url.scheme != 'https' or parsed_url.netloc != 'api.cloudflare.com' or
                parsed_url.path != expected_path or parsed_url.query or parsed_url.fragment or
                headers.get('Content-Type') != 'application/json' or
                headers.get('Accept') != 'application/json' or
                not headers.get('Authorization', '').startswith('Bearer ') or
                not isinstance(body, bytes)):
            raise ValueError('Unpinned development request')
        payload = json.loads(body)
        if payload.get('model') != self.model:
            raise ValueError('Unpinned development model')
        journal = [json.loads(line) for line in (self.directory / 'journal.jsonl').read_bytes().splitlines()]
        ledger = [json.loads(line) for line in self.ledger_path.read_bytes().splitlines()]
        if (len(journal) < 2 or journal[-2].get('event') != 'reserved' or
                journal[-1].get('event') != 'started' or
                journal[-2]['attempt_id'] != journal[-1]['attempt_id'] or
                journal[-2]['id'] != journal[-1]['id'] or
                journal[-2]['request_sha256'] != prep.sha(body) or
                ledger[-1] != {'event': 'reserve', 'attempt_id': journal[-1]['attempt_id'],
                               'model': self.model, 'id': journal[-1]['id'],
                               'stage': STAGE, 'usd': journal[-2]['usd']}):
            raise ValueError('No matching durable development reservation')
        attempt_id = journal[-1]['attempt_id']
        bridge_dir = self.directory / 'app-bridge'
        bridge_dir.mkdir(exist_ok=True)
        ready = {'kind': bridge.KIND + '-request', 'attempt_id': attempt_id,
                 'id': journal[-1]['id'], 'model': self.model, 'stage': STAGE,
                 'review_sha256': self.grant_hash,
                 'account_id_sha256': prep.sha(self.account_id.encode('ascii')),
                 'request_sha256': prep.sha(body), 'method': 'POST',
                 'path': '/accounts/{ACCOUNT_ID}/ai/run/' + prep.MODELS[self.model]['route'],
                 'body': payload}
        bridge.atomic_json(bridge_dir / f'{attempt_id}.request.json', ready)
        response_path = bridge_dir / f'{attempt_id}.response.json'
        deadline = time.monotonic() + self.wait_seconds
        while time.monotonic() < deadline:
            try:
                raw = response_path.read_bytes()
            except FileNotFoundError:
                time.sleep(self.poll_seconds)
                continue
            if len(raw) > smoke.MAX_RESPONSE_BYTES + 4096:
                raise ValueError('Bridge response too large')
            reply = json.loads(raw)
            if (not isinstance(reply, dict) or set(reply) !=
                    {'kind', 'attempt_id', 'request_sha256', 'http_status', 'body_base64'} or
                    reply['kind'] != bridge.KIND + '-response' or
                    reply['attempt_id'] != attempt_id or
                    reply['request_sha256'] != prep.sha(body) or
                    type(reply['http_status']) is not int or
                    not 100 <= reply['http_status'] <= 599):
                raise ValueError('Mismatched bridge response')
            response = base64.b64decode(reply['body_base64'], validate=True)
            if len(response) > smoke.MAX_RESPONSE_BYTES:
                raise ValueError('Bridge response too large')
            app_result_path = bridge_dir / f'{attempt_id}.app-result.json'
            tool_result_path = bridge_dir / f'{attempt_id}.tool-result.json'
            if app_result_path.read_bytes() != response:
                raise ValueError('Saved connector result differs from reply')
            tool_result = json.loads(tool_result_path.read_bytes())
            if (tool_result.get('isError') is not False or
                    len(tool_result.get('content', [])) != 1 or
                    tool_result['content'][0].get('type') != 'text' or
                    json.loads(tool_result['content'][0]['text']) != json.loads(response)):
                raise ValueError('Outer connected-app tool result differs')
            return reply['http_status'], response
        raise TimeoutError('Connected-app development outcome unknown; do not retry')


def run_full(model, manifest_path, grant_path, *, root=prep.ROOT, base=BASE,
             authority_path=AUTHORITY_LEDGER, environment=None, env_file=None,
             wait_seconds=300, transport=None, billing_source=None):
    if model not in prep.MODELS or type(wait_seconds) is not int or not 1 <= wait_seconds <= 600:
        raise ValueError('Unpinned model or wait')
    root, base = Path(root), Path(base)
    account_id, token = smoke.credentials(os.environ if environment is None else environment, env_file)
    if (not isinstance(account_id, str) or not smoke.ACCOUNT_PATTERN.fullmatch(account_id) or
            not isinstance(token, str) or not token.strip()):
        raise ValueError('Cloudflare account or token unavailable')
    # The manifest and six-smoke gate are checked before any ledger mutation.
    manifest_hash = checked_manifest(manifest_path)
    grant, grant_hash = checked_grant(grant_path, model=model, manifest_hash=manifest_hash,
                                      account_id=account_id, wait_seconds=wait_seconds,
                                      billing_fetcher=billing_source or smoke.billing_fetch)
    rows, policy = prep.inputs_and_policy(root)
    selected = json.loads(Path(manifest_path).read_bytes())['models'][model]['requests']
    requests = []
    for row, planned in zip(rows, selected):
        body = prep.canonical(prep.request_payload(row['feedback'], policy, model, 'P0'))
        if (row['id'] != planned['id'] or prep.sha(body) != planned['payload_sha256'] or
                prep.sha(row['feedback'].encode('utf-8')) != planned['input_sha256']):
            raise ValueError('Frozen full P0 request differs')
        requests.append((row['id'], body, planned['payload_sha256']))
    if len(requests) != 60:
        raise ValueError('Expected exact 60 development requests')
    directory = base / model / 'fresh1/P0/development'
    authority = GlobalAuthorityLedger(authority_path,
        grant['global_authority_approval_sha256'],
        grant['global_authority_ledger_sha256_at_admission'])
    ledger = None
    try:
        # Hold the entire model stage under the shared $10 authority before any send.
        authority.hold(model, grant_hash)
        ledger = DevelopmentLedger(base / 'development-budget.jsonl', manifest_hash,
                                   grant['global_authority_approval_sha256'])
        directory.mkdir(parents=True, exist_ok=False)
        claim = {'kind': 'clef-native-full-p0-claim-v1', 'model': model,
                 'stage': STAGE, 'manifest_sha256': manifest_hash,
                 'grant_sha256': grant_hash,
                 'controller_sha256': prep.sha(Path(__file__).read_bytes()),
                 'account_id_sha256': prep.sha(account_id.encode('ascii')),
                 'global_authority_hold_usd': str(prep.reservation_usd(model, 60)),
                 'charge_status': 'unknown_reserved'}
        smoke.exclusive_json(directory / 'claim.json', claim)
        sent = 0
        counts = {'valid': 0, 'invalid_output': 0, 'service_error': 0,
                  'unknown_outcome': 0}
        caller = transport or DevelopmentAppTransport(directory,
            base / 'development-budget.jsonl', model, account_id, grant_hash,
            wait_seconds)
        with (directory / 'journal.jsonl').open('xb') as journal, \
             (directory / 'raw.jsonl').open('xb') as raw_file, \
             (directory / 'records.jsonl').open('xb') as records_file:
            for rid, body, request_hash in requests:
                attempt_id, amount = ledger.reserve(model, rid)
                smoke.durable(journal, {'event': 'reserved', 'attempt_id': attempt_id,
                                        'id': rid, 'request_sha256': request_hash,
                                        'usd': str(amount)})
                smoke.durable(journal, {'event': 'started', 'attempt_id': attempt_id,
                                        'id': rid})
                sent += 1
                url = (f'https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/'
                       f'{prep.MODELS[model]["route"]}')
                headers = {'Authorization': f'Bearer {token}',
                           'Content-Type': 'application/json', 'Accept': 'application/json'}
                started = time.monotonic()
                status, response, error_type = None, b'', None
                try:
                    status, response = caller(url, headers, body)
                    if (type(status) is not int or not isinstance(response, bytes) or
                            len(response) > smoke.MAX_RESPONSE_BYTES):
                        raise ValueError('Malformed or oversized transport response')
                except Exception as error:
                    error_type = type(error).__name__
                    status, response = None, b''
                elapsed = time.monotonic() - started
                redacted = token.encode('utf-8') in response
                if redacted:
                    response = response.replace(token.encode('utf-8'), b'[REDACTED]')
                smoke.durable(raw_file, {'attempt_id': attempt_id, 'id': rid,
                    'request_sha256': request_hash, 'http_status': status,
                    'raw_response_base64': base64.b64encode(response).decode('ascii'),
                    'response_sha256': prep.sha(response), 'redacted': redacted,
                    'error_type': error_type, 'client_seconds': elapsed})
                parsed = None
                if error_type or status is None:
                    outcome, reason = 'unknown_outcome', 'transport_outcome_unknown'
                elif status != 200:
                    outcome, reason = 'service_error', f'HTTP_{status}'
                elif redacted:
                    outcome, reason = 'service_error', 'credential_echo_redacted'
                else:
                    try:
                        envelope = json.loads(response)
                    except (UnicodeError, json.JSONDecodeError, ValueError, KeyError, TypeError):
                        outcome, reason = 'service_error', 'malformed_provider_envelope'
                    else:
                        if (not isinstance(envelope, dict) or
                                envelope.get('success') is not True or
                                envelope.get('errors') != [] or
                                not isinstance(envelope.get('result'), dict)):
                            outcome, reason = 'service_error', 'provider_envelope_error'
                        else:
                            try:
                                parsed = prep.parse_rest_response(envelope, model)
                                outcome, reason = 'valid', None
                            except (UnicodeError, ValueError, KeyError, TypeError):
                                outcome, reason = 'invalid_output', 'strict_response_validation'
                counts[outcome] += 1
                smoke.durable(records_file, {'attempt_id': attempt_id, 'id': rid,
                    'request_sha256': request_hash, 'status': outcome, 'reason': reason,
                    'parsed': parsed, 'charge_status': 'unknown_reserved',
                    'reservation_usd': str(amount), 'reference_labels_read': False})
                smoke.durable(journal, {'event': 'finished', 'attempt_id': attempt_id,
                                        'id': rid, 'status': outcome})
                if outcome in ('service_error', 'unknown_outcome'):
                    break
        completion = {'kind': 'clef-native-full-p0-completion-v1', 'model': model,
            'stage': STAGE, 'status': 'complete' if sent == 60 else 'stopped',
            'attempted': sent, 'counts': counts, 'never_sent': list(prep.IDS[sent:]),
            'claim_sha256': prep.sha((directory / 'claim.json').read_bytes()),
            'journal_sha256': prep.sha((directory / 'journal.jsonl').read_bytes()),
            'raw_sha256': prep.sha((directory / 'raw.jsonl').read_bytes()),
            'records_sha256': prep.sha((directory / 'records.jsonl').read_bytes()),
            'unknown_cost_reserved_usd': str(prep.reservation_usd(model, sent))}
        smoke.exclusive_json(directory / 'completion.json', completion)
        return completion
    finally:
        if ledger is not None:
            ledger.close()
        authority.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    verify = sub.add_parser('verify')
    verify.add_argument('--manifest', type=Path, required=True)
    run = sub.add_parser('run')
    run.add_argument('--execute', action='store_true', required=True)
    run.add_argument('--model', choices=list(prep.MODELS), required=True)
    run.add_argument('--manifest', type=Path, required=True)
    run.add_argument('--grant', type=Path, required=True)
    run.add_argument('--env-file', type=Path)
    run.add_argument('--authority-ledger', type=Path, default=AUTHORITY_LEDGER)
    run.add_argument('--wait-seconds', type=int, default=300)
    args = parser.parse_args()
    if args.command == 'verify':
        print(checked_manifest(args.manifest))
        return
    result = run_full(args.model, args.manifest, args.grant,
                      authority_path=args.authority_ledger,
                      env_file=args.env_file, wait_seconds=args.wait_seconds)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
