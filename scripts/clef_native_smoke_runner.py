#!/usr/bin/env python3
"""Reviewed, single-stage Cloudflare Clef P0 smoke runner. Never retries.

Only fresh1/P0 DEV-001..003 for one selected model can run. A saved manifest,
reviewed grant, account/token environment, billing-source hash, and separate
Cloudflare budget ledger are all required before dispatch.
"""

import argparse
import base64
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.request
import uuid

from development_benchmark import ROOT
import clef_native_preparation as prep

BASE = Path('results/clef-native-v1')
STAGE = 'fresh1/P0/smoke'
MAX_RESPONSE_BYTES = 1_048_576
TIMEOUT_SECONDS = 60
ACCOUNT_PATTERN = re.compile(r'[0-9a-fA-F]{32}\Z')


def durable(handle, value):
    handle.write(prep.canonical(value) + b'\n')
    handle.flush()
    os.fsync(handle.fileno())


def exclusive_json(path, value):
    with Path(path).open('xb') as handle:
        durable(handle, value)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('Redirect refused')


OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())


def billing_fetch(url):
    if url not in {spec['source'] for spec in prep.MODELS.values()}:
        raise ValueError('Unpinned billing source')
    request = urllib.request.Request(url, headers={'Accept': 'text/markdown',
                                                   'User-Agent': 'recruitment-feedback-clef/1.0'})
    with OPENER.open(request, timeout=TIMEOUT_SECONDS) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError('Billing source too large')
    return raw


def post(url, headers, body):
    request = urllib.request.Request(url, data=body, headers=headers, method='POST')
    try:
        with OPENER.open(request, timeout=TIMEOUT_SECONDS) as response:
            return response.status, response.read(MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as error:
        return error.code, error.read(MAX_RESPONSE_BYTES + 1)


def checked_manifest(path, root):
    saved = json.loads(Path(path).read_text())
    expected = prep.build_plan(root)
    if saved != expected:
        raise ValueError('Reviewed manifest differs from current input-only plan')
    return expected, prep.sha(prep.canonical(expected))


def credentials(environment, env_file=None):
    """Read only scoped Cloudflare names; process values take precedence."""
    aliases = {prep.ACCOUNT_ENV: 'CF_ACCOUNT_ID', prep.TOKEN_ENV: 'CF_API_TOKEN'}
    selected = {name: environment.get(name) or environment.get(alias)
                for name, alias in aliases.items()}
    if env_file is not None and any(not selected[name] for name in selected):
        found = {}
        for line in Path(env_file).read_text().splitlines():
            key, sep, value = line.partition('=')
            key = key.strip()
            if key.startswith('export '):
                key = key[7:].strip()
            if not sep or key not in set(aliases) | set(aliases.values()):
                continue
            if key in found:
                raise ValueError('Duplicate Cloudflare credential name in env file')
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            found[key] = value
        for name in selected:
            if not selected[name]:
                selected[name] = found.get(name) or found.get(aliases[name])
    return selected[prep.ACCOUNT_ENV], selected[prep.TOKEN_ENV]


def checked_grant(path, plan_hash, account_id, billing_fetcher):
    raw = Path(path).read_bytes()
    grant = json.loads(raw)
    expected_keys = {'kind', 'approved', 'authorized_by_user', 'reviewer',
                     'plan_sha256', 'runner_sha256', 'account_id_sha256',
                     'models', 'stage', 'cap_usd', 'exhaustion_policy',
                     'billing_source_sha256', 'input_usd_per_million'}
    if (not isinstance(grant, dict) or set(grant) != expected_keys or
            grant['kind'] != 'clef-native-initial-smoke-grant-v1' or
            grant['approved'] is not True or grant['authorized_by_user'] is not True or
            not isinstance(grant['reviewer'], str) or not grant['reviewer'].strip() or
            grant['plan_sha256'] != plan_hash or
            grant['runner_sha256'] != prep.sha(Path(__file__).read_bytes()) or
            grant['account_id_sha256'] != prep.sha(account_id.encode('ascii')) or
            grant['models'] != list(prep.MODELS) or grant['stage'] != STAGE or
            grant['cap_usd'] != str(prep.PROPOSED_INITIAL_SMOKE_CAP_USD) or
            grant['exhaustion_policy'] != 'pause' or
            not isinstance(grant['billing_source_sha256'], dict) or
            set(grant['billing_source_sha256']) != set(prep.MODELS) or
            grant['input_usd_per_million'] != {model: str(spec['input_usd_per_million'])
                                                for model, spec in prep.MODELS.items()}):
        raise ValueError('Explicit reviewed Cloudflare grant required')
    for model, spec in prep.MODELS.items():
        observed = billing_fetcher(spec['source'])
        if not isinstance(observed, bytes) or prep.sha(observed) != grant['billing_source_sha256'][model]:
            raise ValueError('Reviewed billing source changed')
    return prep.sha(raw)


class CloudflareLedger:
    """Exclusive, append-only unknown-charge reservations for this $0.10 grant."""

    def __init__(self, path, grant_hash, plan_hash):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = path.open('a+b')
        try:
            fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.handle.seek(0)
            raw = self.handle.read()
            if raw and (not raw.endswith(b'\n') or any(not line.strip() for line in raw.splitlines())):
                raise ValueError('Incomplete Cloudflare ledger')
            events = [json.loads(line) for line in raw.splitlines()]
            header = {'event': 'budget', 'cap_usd': str(prep.PROPOSED_INITIAL_SMOKE_CAP_USD),
                      'grant_sha256': grant_hash, 'plan_sha256': plan_hash}
            if not events:
                durable(self.handle, header)
                events = [header]
            if events[0] != header or any(e.get('event') != 'reserve' for e in events[1:]):
                raise ValueError('Cloudflare ledger provenance differs')
            seen = set()
            seen_request = set()
            total = Decimal(0)
            for event in events[1:]:
                if (set(event) != {'event', 'attempt_id', 'model', 'id', 'stage', 'usd'} or
                        event['model'] not in prep.MODELS or event['id'] not in prep.SMOKE_IDS or
                        event['stage'] != STAGE or not isinstance(event['attempt_id'], str) or
                        event['attempt_id'] in seen or
                        (event['model'], event['id']) in seen_request or
                        Decimal(event['usd']) != prep.reservation_usd(event['model'], 1)):
                    raise ValueError('Cloudflare ledger reservation differs')
                seen.add(event['attempt_id'])
                seen_request.add((event['model'], event['id']))
                total += Decimal(event['usd'])
            if total > prep.PROPOSED_INITIAL_SMOKE_CAP_USD:
                raise ValueError('Cloudflare cap exceeded')
            self.total = total
            self.seen_request = seen_request
            self.handle.seek(0, os.SEEK_END)
        except BaseException:
            self.handle.close()
            raise

    def reserve(self, model, rid):
        amount = prep.reservation_usd(model, 1)
        if (model, rid) in self.seen_request:
            raise ValueError('Request already reserved; no replay')
        if self.total + amount > prep.PROPOSED_INITIAL_SMOKE_CAP_USD:
            raise ValueError('Cloudflare cap exhausted; no send')
        attempt_id = str(uuid.uuid4())
        durable(self.handle, {'event': 'reserve', 'attempt_id': attempt_id,
                              'model': model, 'id': rid, 'stage': STAGE, 'usd': str(amount)})
        self.total += amount
        self.seen_request.add((model, rid))
        return attempt_id, amount

    def close(self):
        self.handle.close()


def run_smoke(model, manifest_path, grant_path, *, root=ROOT, output_root=None,
              environment=None, env_file=None, transport=None, billing_source=None):
    if model not in prep.MODELS:
        raise ValueError('Unpinned Clef model')
    root = Path(root)
    output_root = Path(output_root) if output_root is not None else root / BASE
    environment = os.environ if environment is None else environment
    account_id, token = credentials(environment, env_file)
    if not isinstance(account_id, str) or not ACCOUNT_PATTERN.fullmatch(account_id):
        raise ValueError('Cloudflare account ID unavailable or malformed')
    if not isinstance(token, str) or not token.strip():
        raise ValueError('Cloudflare API token unavailable')
    plan, plan_hash = checked_manifest(manifest_path, root)
    grant_hash = checked_grant(grant_path, plan_hash, account_id,
                                billing_source or billing_fetch)
    selected = plan['models'][model]['requests']['P0'][:3]
    rows, policy = prep.inputs_and_policy(root)
    requests = []
    for row, planned in zip(rows[:3], selected):
        payload = prep.request_payload(row['feedback'], policy, model, 'P0')
        body = prep.canonical(payload)
        if (row['id'] != planned['id'] or prep.sha(body) != planned['payload_sha256'] or
                prep.sha(row['feedback'].encode('utf-8')) != planned['input_sha256']):
            raise ValueError('Frozen initial smoke request differs')
        requests.append((row['id'], body, planned['payload_sha256']))
    directory = output_root / model / 'fresh1' / 'P0' / 'smoke'
    ledger = CloudflareLedger(output_root / 'budget.jsonl', grant_hash, plan_hash)
    try:
        directory.mkdir(parents=True, exist_ok=False)
        claim = {'kind': 'clef-native-initial-smoke-claim-v1', 'model': model,
                 'stage': STAGE, 'plan_sha256': plan_hash, 'grant_sha256': grant_hash,
                 'runner_sha256': prep.sha(Path(__file__).read_bytes()),
                 'account_id_sha256': prep.sha(account_id.encode('ascii')),
                 'charge_status': 'unknown_reserved'}
        exclusive_json(directory / 'claim.json', claim)
        journal_file = directory / 'journal.jsonl'
        raw_file = directory / 'raw.jsonl'
        records_file = directory / 'records.jsonl'
        counts = {'valid': 0, 'invalid_output': 0, 'service_error': 0, 'unknown_outcome': 0}
        sent = 0
        with journal_file.open('xb') as journal, raw_file.open('xb') as raw_handle, records_file.open('xb') as records:
            for rid, body, request_hash in requests:
                attempt_id, amount = ledger.reserve(model, rid)
                durable(journal, {'event': 'reserved', 'attempt_id': attempt_id, 'id': rid,
                                  'request_sha256': request_hash, 'usd': str(amount)})
                durable(journal, {'event': 'started', 'attempt_id': attempt_id, 'id': rid})
                sent += 1
                endpoint = (f'https://api.cloudflare.com/client/v4/accounts/{account_id}'
                            f'/ai/run/{prep.MODELS[model]["route"]}')
                headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json',
                           'Accept': 'application/json'}
                started = time.monotonic()
                status, response, error_type = None, b'', None
                try:
                    status, response = (transport or post)(endpoint, headers, body)
                    if type(status) is not int or not isinstance(response, bytes) or len(response) > MAX_RESPONSE_BYTES:
                        raise ValueError('Malformed or oversized transport response')
                except Exception as error:
                    error_type = type(error).__name__
                    status, response = None, b''
                elapsed = time.monotonic() - started
                redacted = token.encode('utf-8') in response
                if redacted:
                    response = response.replace(token.encode('utf-8'), b'[REDACTED]')
                durable(raw_handle, {'attempt_id': attempt_id, 'id': rid, 'request_sha256': request_hash,
                                     'http_status': status, 'raw_response_base64': base64.b64encode(response).decode('ascii'),
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
                        if (not isinstance(envelope, dict) or envelope.get('success') is not True or
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
                durable(records, {'attempt_id': attempt_id, 'id': rid, 'request_sha256': request_hash,
                                  'status': outcome, 'reason': reason, 'parsed': parsed,
                                  'charge_status': 'unknown_reserved', 'reservation_usd': str(amount),
                                  'reference_labels_read': False})
                durable(journal, {'event': 'finished', 'attempt_id': attempt_id, 'id': rid,
                                  'status': outcome})
                if outcome in ('service_error', 'unknown_outcome'):
                    break
        terminal_status = ('complete' if sent == 3 and counts['valid'] == 3 else
                           'smoke_rejected' if sent == 3 and counts['invalid_output'] else 'stopped')
        completion = {'kind': 'clef-native-initial-smoke-completion-v1', 'model': model,
                      'stage': STAGE, 'status': terminal_status, 'attempted': sent,
                      'counts': counts, 'never_sent': list(prep.SMOKE_IDS[sent:]),
                      'claim_sha256': prep.sha((directory / 'claim.json').read_bytes()),
                      'journal_sha256': prep.sha(journal_file.read_bytes()),
                      'raw_sha256': prep.sha(raw_file.read_bytes()),
                      'records_sha256': prep.sha(records_file.read_bytes()),
                      'unknown_cost_reserved_usd': str(prep.reservation_usd(model, sent))}
        exclusive_json(directory / 'completion.json', completion)
        return completion
    finally:
        ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute', action='store_true', help='Required for any dispatch')
    parser.add_argument('--model', choices=list(prep.MODELS), required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--grant', type=Path, required=True)
    parser.add_argument('--env-file', type=Path, help='Read missing Cloudflare names from a local env file')
    args = parser.parse_args()
    if not args.execute:
        parser.error('--execute and an exact reviewed grant are required')
    completion = run_smoke(args.model, args.manifest, args.grant, env_file=args.env_file)
    print(json.dumps(completion, indent=2))


if __name__ == '__main__':
    main()
