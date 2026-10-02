#!/usr/bin/env python3
"""Single-use Clef fresh2/P0 stages. Offline verify is the default action.

Each model's smoke and development phase needs its own reviewed grant. The
connected-app operator submits one saved result per durable attempt; a missing
result stops the stage with an unknown charge reservation and no retry.
"""

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

BASE = prep.ROOT / 'results/clef-native-v1'
PROPOSAL = BASE / 'repeat-continuation-v1/proposed-manifest.json'
MANIFEST = BASE / 'repeat-continuation-v1/fresh2-p0-admission-v1.json'
AUTHORITY = prep.ROOT / 'results/postapproval-paid-work-2026-10-02.jsonl'
AUTHORITY_SNAPSHOT = BASE / 'postapproval-ledger-after-full-p0.jsonl'
CAP = Decimal('10.00')
APPROVAL_SHA256 = prep.sha("you're approved to run tests and live runs up to 10 dollars overall".encode())
KIND = 'clef-native-fresh2-p0-admission-v1'
GRANT_KIND = 'clef-native-fresh2-p0-stage-grant-v1'
INSPECTION_KIND = 'clef-native-fresh2-p0-smoke-review-v1'
STAGES = ('smoke', 'development')


def read_json(path):
    return json.loads(Path(path).read_bytes())


def stage_name(model, phase):
    if model not in prep.MODELS or phase not in STAGES:
        raise ValueError('Unpinned Clef stage')
    return f'{model}/fresh2/P0/{phase}'


def stage_dir(base, model, phase):
    return Path(base) / model / 'fresh2' / 'P0' / phase


def proposal_checked(root=prep.ROOT, proposal_path=PROPOSAL):
    root, proposal_path = Path(root), Path(proposal_path)
    proposal = read_json(proposal_path)
    if (proposal.get('schema') != 'clef-native-repeat-continuation-proposal-v1' or
            proposal.get('status') != 'offline_proposal_only_no_allocation_no_inference' or
            proposal.get('reference_labels_sent') is not False):
        raise ValueError('Wrong frozen continuation proposal')
    for name, digest in proposal['source_sha256'].items():
        if prep.sha((root / name).read_bytes()) != digest:
            raise ValueError('Frozen proposal source changed: ' + name)
    plan = prep.build_plan(root)
    if plan != read_json(root / 'results/clef-native-v1/preparation.json'):
        raise ValueError('Input-only preparation changed')
    for model in prep.MODELS:
        selected = [s for s in proposal['pending_full_passes']
                    if s['model'] == model and s['pass'] == 'fresh2' and s['condition'] == 'P0']
        if len(selected) != 1 or selected[0]['status'] != 'never_dispatched':
            raise ValueError('Expected one never-dispatched fresh2/P0 stage')
        stage = selected[0]
        if (stage['route'] != prep.MODELS[model]['route'] or
                stage['stage_identity'] != f'{model}/fresh2/P0' or
                stage['smoke']['ids'] != list(prep.SMOKE_IDS) or
                stage['development']['ids'] != list(prep.IDS) or
                stage['smoke']['full_context_hold_usd'] != str(prep.reservation_usd(model, 3)) or
                stage['development']['full_context_hold_usd'] != str(prep.reservation_usd(model, 60))):
            raise ValueError('Proposed stage differs from frozen native controls')
        source = proposal['request_sets'][model]['P0']
        expected = plan['models'][model]['requests']['P0']
        if (source['ordered_ids'] != list(prep.IDS) or
                source['input_sha256'] != [r['input_sha256'] for r in expected] or
                source['request_sha256'] != [r['payload_sha256'] for r in expected]):
            raise ValueError('Proposed request set differs from input-only plan')
    return proposal, plan


def manifest_value(root=prep.ROOT, proposal_path=PROPOSAL):
    root, proposal_path = Path(root), Path(proposal_path)
    proposal, plan = proposal_checked(root, proposal_path)
    stages = {}
    for model in prep.MODELS:
        selected = next(s for s in proposal['pending_full_passes']
                        if s['model'] == model and s['pass'] == 'fresh2' and s['condition'] == 'P0')
        stages[model] = {'route': selected['route'], 'condition': 'P0', 'pass': 'fresh2',
                         'smoke': selected['smoke'], 'development': selected['development'],
                         'requests': plan['models'][model]['requests']['P0']}
    return {'kind': KIND, 'status': 'prepared_no_grants_or_dispatch',
            'proposal_sha256': prep.sha(proposal_path.read_bytes()),
            'preparation_sha256': prep.sha((root / 'results/clef-native-v1/preparation.json').read_bytes()),
            'authority_snapshot_sha256': prep.sha((root / 'results/clef-native-v1/postapproval-ledger-after-full-p0.jsonl').read_bytes()),
            'controller_sha256': prep.sha(Path(__file__).read_bytes()),
            'bridge_sha256': prep.sha(Path(bridge.__file__).read_bytes()),
            'models': stages, 'transport': 'mcp__codex_apps__cloudflare_execute',
            'reference_labels_sent': False}


def checked_manifest(path=MANIFEST, *, root=prep.ROOT, proposal_path=PROPOSAL):
    saved = read_json(path)
    if saved != manifest_value(root, proposal_path):
        raise ValueError('Reviewed fresh2/P0 manifest differs from frozen inputs')
    return saved, prep.sha(Path(path).read_bytes())


def checked_smoke_review(path, *, model, manifest_hash, account_id, base=BASE):
    directory = stage_dir(base, model, 'smoke')
    completion_path = directory / 'completion.json'
    completion = read_json(completion_path)
    if (completion.get('kind') != 'clef-native-fresh2-p0-completion-v1' or
            completion.get('model') != model or completion.get('stage') != stage_name(model, 'smoke') or
            completion.get('status') != 'complete' or completion.get('attempted') != 3 or
            completion.get('counts') != {'valid': 3, 'invalid_output': 0,
                                        'service_error': 0, 'unknown_outcome': 0} or
            completion.get('never_sent') != []):
        raise ValueError('Full run requires completed three-record smoke')
    for name, key in [('claim.json', 'claim_sha256'), ('journal.jsonl', 'journal_sha256'),
                      ('raw.jsonl', 'raw_sha256'), ('records.jsonl', 'records_sha256')]:
        if prep.sha((directory / name).read_bytes()) != completion.get(key):
            raise ValueError('Smoke evidence changed')
    claim = read_json(directory / 'claim.json')
    if (claim.get('model') != model or claim.get('stage') != stage_name(model, 'smoke') or
            claim.get('manifest_sha256') != manifest_hash or
            claim.get('account_id_sha256') != prep.sha(account_id.encode('ascii'))):
        raise ValueError('Smoke account or controls differ from full stage')
    records = [json.loads(line) for line in (directory / 'records.jsonl').read_bytes().splitlines()]
    if ([r.get('id') for r in records] != list(prep.SMOKE_IDS) or
            any(r.get('status') != 'valid' or not isinstance(r.get('parsed'), dict)
                for r in records)):
        raise ValueError('Smoke records differ')
    raw = Path(path).read_bytes()
    expected = {'kind': INSPECTION_KIND, 'approved': True,
                'model': model, 'stage': stage_name(model, 'smoke'),
                'manifest_sha256': manifest_hash,
                'completion_sha256': prep.sha(completion_path.read_bytes()),
                'records_sha256': completion['records_sha256'],
                'raw_sha256': completion['raw_sha256'],
                'decision': 'admit_unchanged_full_p0'}
    review = json.loads(raw)
    if (not isinstance(review, dict) or set(review) != set(expected) | {'reviewer'} or
            any(review.get(k) != v for k, v in expected.items()) or
            not isinstance(review.get('reviewer'), str) or not review['reviewer'].strip()):
        raise ValueError('Independent exact smoke review required')
    return prep.sha(raw)


def checked_grant(path, *, model, phase, manifest_hash, account_id,
                  wait_seconds, smoke_review_hash, billing_fetcher=smoke.billing_fetch):
    raw = Path(path).read_bytes()
    grant = json.loads(raw)
    expected = {'kind': GRANT_KIND, 'approved': True, 'authorized_by_user': True,
                'model': model, 'stage': stage_name(model, phase),
                'phase': phase, 'manifest_sha256': manifest_hash,
                'controller_sha256': prep.sha(Path(__file__).read_bytes()),
                'bridge_sha256': prep.sha(Path(bridge.__file__).read_bytes()),
                'account_id_sha256': prep.sha(account_id.encode('ascii')),
                'transport': 'mcp__codex_apps__cloudflare_execute',
                'full_context_hold_usd': str(prep.reservation_usd(model, 3 if phase == 'smoke' else 60)),
                'global_authority_cap_usd': str(CAP),
                'global_authority_approval_sha256': APPROVAL_SHA256,
                'smoke_review_sha256': smoke_review_hash,
                'exhaustion_policy': 'pause', 'wait_seconds': wait_seconds}
    extra = {'reviewer', 'global_authority_ledger_sha256_at_admission', 'billing_source_sha256'}
    if (not isinstance(grant, dict) or set(grant) != set(expected) | extra or
            any(grant.get(k) != v for k, v in expected.items()) or
            not isinstance(grant.get('reviewer'), str) or not grant['reviewer'].strip() or
            not isinstance(grant.get('global_authority_ledger_sha256_at_admission'), str) or
            len(grant['global_authority_ledger_sha256_at_admission']) != 64 or
            not isinstance(grant.get('billing_source_sha256'), str) or
            len(grant['billing_source_sha256']) != 64):
        raise ValueError('Exact reviewed single-stage grant required')
    if prep.sha(billing_fetcher(prep.MODELS[model]['source'])) != grant['billing_source_sha256']:
        raise ValueError('Reviewed Cloudflare billing page changed')
    return grant, prep.sha(raw)


class AuthorityLedger:
    def __init__(self, path, snapshot_path, expected_head_hash):
        self.path = Path(path)
        self.handle = self.path.open('r+b')
        try:
            fcntl.flock(self.handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.handle.seek(0)
            raw = self.handle.read()
            snapshot = Path(snapshot_path).read_bytes()
            if (not raw.startswith(snapshot) or not raw.endswith(b'\n') or
                    prep.sha(snapshot) != prep.sha(AUTHORITY_SNAPSHOT.read_bytes()) or
                    prep.sha(raw) != expected_head_hash):
                raise ValueError('Cross-provider authority ledger changed')
            events = [json.loads(line) for line in raw.splitlines()]
            if events[0] != {'event': 'authority', 'kind': 'postapproval-paid-work-v1',
                             'cap_usd': str(CAP),
                             'decision_key': 'candidate-experience-benchmark/user-ten-dollar-tests-20261002',
                             'approval_sha256': APPROVAL_SHA256}:
                raise ValueError('Wrong shared authority')
            holds, total = set(), Decimal(0)
            for event in events[1:]:
                if (set(event) != {'event', 'id', 'usd', 'source_sha256'} or
                        event['event'] != 'hold' or event['id'] in holds or
                        type(event['usd']) is not str or
                        not isinstance(event['source_sha256'], str) or
                        len(event['source_sha256']) != 64):
                    raise ValueError('Malformed or duplicate authority hold')
                amount = Decimal(event['usd'])
                if not amount.is_finite() or amount <= 0:
                    raise ValueError('Invalid authority amount')
                holds.add(event['id'])
                total += amount
            if total > CAP:
                raise ValueError('Shared authority exhausted')
            self.holds, self.total = holds, total
            self.handle.seek(0, os.SEEK_END)
        except BaseException:
            self.handle.close()
            raise

    def hold(self, model, phase, grant_hash):
        identity = f'cloudflare-{model}-fresh2-p0-{phase}'
        amount = prep.reservation_usd(model, 3 if phase == 'smoke' else 60)
        if identity in self.holds or self.total + amount > CAP:
            raise ValueError('Duplicate stage or shared authority cap exhausted')
        smoke.durable(self.handle, {'event': 'hold', 'id': identity, 'usd': str(amount),
                                    'source_sha256': grant_hash})
        self.holds.add(identity)
        self.total += amount

    def close(self):
        self.handle.close()


class StageLedger:
    def __init__(self, path, *, model, phase, manifest_hash, grant_hash):
        self.path = Path(path)
        self.handle = self.path.open('xb+')
        self.model, self.phase = model, phase
        self.cap = prep.reservation_usd(model, 3 if phase == 'smoke' else 60)
        self.total = Decimal(0)
        self.seen = set()
        smoke.durable(self.handle, {'event': 'budget', 'cap_usd': str(self.cap),
                                    'stage': stage_name(model, phase),
                                    'manifest_sha256': manifest_hash,
                                    'grant_sha256': grant_hash})

    def reserve(self, rid):
        amount = prep.reservation_usd(self.model, 1)
        if rid in self.seen or self.total + amount > self.cap:
            raise ValueError('Duplicate request or local stage cap exhausted')
        attempt_id = str(uuid.uuid4())
        smoke.durable(self.handle, {'event': 'reserve', 'stage': stage_name(self.model, self.phase),
                                    'attempt_id': attempt_id, 'id': rid, 'usd': str(amount)})
        self.seen.add(rid)
        self.total += amount
        return attempt_id, amount

    def close(self):
        self.handle.close()


class AppTransport:
    def __init__(self, directory, model, phase, account_id, grant_hash, wait_seconds):
        self.directory = Path(directory)
        self.model, self.phase = model, phase
        self.account_id, self.grant_hash = account_id, grant_hash
        self.wait_seconds = wait_seconds

    def __call__(self, url, headers, body):
        expected = f'/client/v4/accounts/{self.account_id}/ai/run/{prep.MODELS[self.model]["route"]}'
        parsed = urlparse(url)
        if (parsed.scheme != 'https' or parsed.netloc != 'api.cloudflare.com' or
                parsed.path != expected or parsed.query or parsed.fragment or
                headers.get('Content-Type') != 'application/json' or
                headers.get('Accept') != 'application/json' or
                not headers.get('Authorization', '').startswith('Bearer ') or
                not isinstance(body, bytes) or json.loads(body).get('model') != self.model):
            raise ValueError('Unpinned connected-app request')
        journal = [json.loads(line) for line in (self.directory / 'journal.jsonl').read_bytes().splitlines()]
        ledger = [json.loads(line) for line in (self.directory / 'budget.jsonl').read_bytes().splitlines()]
        if (len(journal) < 2 or journal[-2].get('event') != 'reserved' or
                journal[-1].get('event') != 'started' or
                journal[-2]['attempt_id'] != journal[-1]['attempt_id'] or
                journal[-2]['request_sha256'] != prep.sha(body) or
                ledger[-1] != {'event': 'reserve', 'stage': stage_name(self.model, self.phase),
                               'attempt_id': journal[-1]['attempt_id'],
                               'id': journal[-1]['id'], 'usd': journal[-2]['usd']}):
            raise ValueError('No matching durable stage reservation')
        attempt_id = journal[-1]['attempt_id']
        directory = self.directory / 'app-bridge'
        directory.mkdir(exist_ok=True)
        request = {'kind': bridge.KIND + '-request', 'attempt_id': attempt_id,
                   'id': journal[-1]['id'], 'model': self.model,
                   'stage': stage_name(self.model, self.phase),
                   'review_sha256': self.grant_hash,
                   'account_id_sha256': prep.sha(self.account_id.encode('ascii')),
                   'request_sha256': prep.sha(body), 'method': 'POST',
                   'path': '/accounts/{ACCOUNT_ID}/ai/run/' + prep.MODELS[self.model]['route'],
                   'body': json.loads(body)}
        bridge.atomic_json(directory / f'{attempt_id}.request.json', request)
        deadline = time.monotonic() + self.wait_seconds
        while time.monotonic() < deadline:
            response_path = directory / f'{attempt_id}.response.json'
            try:
                raw = response_path.read_bytes()
            except FileNotFoundError:
                time.sleep(0.1)
                continue
            if len(raw) > smoke.MAX_RESPONSE_BYTES + 4096:
                raise ValueError('Bridge response too large')
            reply = json.loads(raw)
            if (not isinstance(reply, dict) or set(reply) !=
                    {'kind', 'attempt_id', 'request_sha256', 'http_status', 'body_base64'} or
                    reply['kind'] != bridge.KIND + '-response' or
                    reply['attempt_id'] != attempt_id or reply['request_sha256'] != prep.sha(body) or
                    type(reply['http_status']) is not int or not 100 <= reply['http_status'] <= 599):
                raise ValueError('Mismatched connected-app reply')
            response = base64.b64decode(reply['body_base64'], validate=True)
            if len(response) > smoke.MAX_RESPONSE_BYTES:
                raise ValueError('Bridge response too large')
            if (directory / f'{attempt_id}.app-result.json').read_bytes() != response:
                raise ValueError('Saved app result differs')
            tool = read_json(directory / f'{attempt_id}.tool-result.json')
            if (tool.get('isError') is not False or len(tool.get('content', [])) != 1 or
                    tool['content'][0].get('type') != 'text' or
                    json.loads(tool['content'][0]['text']) != json.loads(response)):
                raise ValueError('Outer tool result differs')
            dispatch = read_json(directory / f'{attempt_id}.dispatch.json')
            if dispatch.get('request_sha256') != prep.sha(body) or not dispatch.get('operator'):
                raise ValueError('Operator dispatch evidence absent')
            return reply['http_status'], response
        raise TimeoutError('Connected-app outcome unknown; do not retry')


def run_stage(model, phase, manifest_path, grant_path, *, root=prep.ROOT,
              base=BASE, proposal_path=PROPOSAL, authority_path=AUTHORITY,
              snapshot_path=AUTHORITY_SNAPSHOT, environment=None, env_file=None,
              wait_seconds=300, transport=None, billing_source=None,
              smoke_review_path=None):
    if model not in prep.MODELS or phase not in STAGES or type(wait_seconds) is not int or not 1 <= wait_seconds <= 600:
        raise ValueError('Unpinned stage or bounded wait')
    root, base = Path(root), Path(base)
    account_id, token = smoke.credentials(os.environ if environment is None else environment, env_file)
    if (not isinstance(account_id, str) or not smoke.ACCOUNT_PATTERN.fullmatch(account_id) or
            not isinstance(token, str) or not token.strip()):
        raise ValueError('Cloudflare credentials unavailable')
    manifest, manifest_hash = checked_manifest(manifest_path, root=root, proposal_path=proposal_path)
    review_hash = None
    if phase == 'development':
        if smoke_review_path is None:
            raise ValueError('Independent smoke review required before full stage')
        review_hash = checked_smoke_review(smoke_review_path, model=model,
                                           manifest_hash=manifest_hash,
                                           account_id=account_id, base=base)
    grant, grant_hash = checked_grant(grant_path, model=model, phase=phase,
                                      manifest_hash=manifest_hash, account_id=account_id,
                                      wait_seconds=wait_seconds, smoke_review_hash=review_hash,
                                      billing_fetcher=billing_source or smoke.billing_fetch)
    rows, policy = prep.inputs_and_policy(root)
    ids = prep.SMOKE_IDS if phase == 'smoke' else prep.IDS
    planned = manifest['models'][model]['requests'][:len(ids)]
    requests = []
    for row, item in zip(rows[:len(ids)], planned):
        body = prep.canonical(prep.request_payload(row['feedback'], policy, model, 'P0'))
        if (row['id'] != item['id'] or prep.sha(body) != item['payload_sha256'] or
                prep.sha(row['feedback'].encode()) != item['input_sha256']):
            raise ValueError('Frozen input-only request differs')
        requests.append((row['id'], body, item['payload_sha256']))
    directory = stage_dir(base, model, phase)
    if directory.exists():
        raise ValueError('Stage already claimed; no replay')
    authority = AuthorityLedger(authority_path, snapshot_path,
                                 grant['global_authority_ledger_sha256_at_admission'])
    try:
        authority.hold(model, phase, grant_hash)
        directory.mkdir(parents=True, exist_ok=False)
        smoke.exclusive_json(directory / 'claim.json', {'kind': 'clef-native-fresh2-p0-claim-v1',
            'model': model, 'stage': stage_name(model, phase),
            'manifest_sha256': manifest_hash, 'grant_sha256': grant_hash,
            'controller_sha256': prep.sha(Path(__file__).read_bytes()),
            'account_id_sha256': prep.sha(account_id.encode('ascii')),
            'global_authority_hold_usd': str(prep.reservation_usd(model, len(ids))),
            'charge_status': 'unknown_reserved'})
        ledger = StageLedger(directory / 'budget.jsonl', model=model, phase=phase,
                             manifest_hash=manifest_hash, grant_hash=grant_hash)
        try:
            caller = transport or AppTransport(directory, model, phase, account_id,
                                                grant_hash, wait_seconds)
            counts = {'valid': 0, 'invalid_output': 0, 'service_error': 0,
                      'unknown_outcome': 0}
            sent = 0
            with (directory / 'journal.jsonl').open('xb') as journal, \
                 (directory / 'raw.jsonl').open('xb') as raw_file, \
                 (directory / 'records.jsonl').open('xb') as records_file:
                for rid, body, request_hash in requests:
                    attempt_id, amount = ledger.reserve(rid)
                    smoke.durable(journal, {'event': 'reserved', 'attempt_id': attempt_id,
                                            'id': rid, 'request_sha256': request_hash,
                                            'usd': str(amount)})
                    smoke.durable(journal, {'event': 'started', 'attempt_id': attempt_id, 'id': rid})
                    sent += 1
                    url = (f'https://api.cloudflare.com/client/v4/accounts/{account_id}'
                           f'/ai/run/{prep.MODELS[model]["route"]}')
                    headers = {'Authorization': f'Bearer {token}',
                               'Content-Type': 'application/json', 'Accept': 'application/json'}
                    start = time.monotonic()
                    status, response, error_type = None, b'', None
                    try:
                        status, response = caller(url, headers, body)
                        if type(status) is not int or not isinstance(response, bytes) or len(response) > smoke.MAX_RESPONSE_BYTES:
                            raise ValueError('Malformed or oversized transport response')
                    except Exception as error:
                        error_type = type(error).__name__
                        status, response = None, b''
                    elapsed = time.monotonic() - start
                    redacted = token.encode() in response
                    if redacted:
                        response = response.replace(token.encode(), b'[REDACTED]')
                    smoke.durable(raw_file, {'attempt_id': attempt_id, 'id': rid,
                        'request_sha256': request_hash, 'http_status': status,
                        'raw_response_base64': base64.b64encode(response).decode(),
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
                    smoke.durable(records_file, {'attempt_id': attempt_id, 'id': rid,
                        'request_sha256': request_hash, 'status': outcome, 'reason': reason,
                        'parsed': parsed, 'charge_status': 'unknown_reserved',
                        'reservation_usd': str(amount), 'reference_labels_read': False})
                    smoke.durable(journal, {'event': 'finished', 'attempt_id': attempt_id,
                                            'id': rid, 'status': outcome})
                    if outcome in ('service_error', 'unknown_outcome'):
                        break
            complete = sent == len(ids) and (phase == 'development' or counts['valid'] == 3)
            completion = {'kind': 'clef-native-fresh2-p0-completion-v1',
                'model': model, 'stage': stage_name(model, phase),
                'status': 'complete' if complete else 'stopped', 'attempted': sent,
                'counts': counts, 'never_sent': list(ids[sent:]),
                'claim_sha256': prep.sha((directory / 'claim.json').read_bytes()),
                'journal_sha256': prep.sha((directory / 'journal.jsonl').read_bytes()),
                'raw_sha256': prep.sha((directory / 'raw.jsonl').read_bytes()),
                'records_sha256': prep.sha((directory / 'records.jsonl').read_bytes()),
                'unknown_cost_reserved_usd': str(prep.reservation_usd(model, sent))}
            smoke.exclusive_json(directory / 'completion.json', completion)
            return completion
        finally:
            ledger.close()
    finally:
        authority.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('verify')
    check.add_argument('--manifest', type=Path, default=MANIFEST)
    run = sub.add_parser('run')
    run.add_argument('--execute', action='store_true', required=True)
    run.add_argument('--model', choices=list(prep.MODELS), required=True)
    run.add_argument('--phase', choices=STAGES, required=True)
    run.add_argument('--manifest', type=Path, default=MANIFEST)
    run.add_argument('--grant', type=Path, required=True)
    run.add_argument('--smoke-review', type=Path)
    run.add_argument('--env-file', type=Path)
    run.add_argument('--wait-seconds', type=int, default=300)
    submit = sub.add_parser('submit')
    submit.add_argument('--request', type=Path, required=True)
    submit.add_argument('--app-result-file', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'submit':
        print(bridge.submit_response(args.request, args.app_result_file))
    elif args.command == 'verify':
        print(checked_manifest(args.manifest)[1])
    else:
        print(json.dumps(run_stage(args.model, args.phase, args.manifest, args.grant,
                                   smoke_review_path=args.smoke_review,
                                   env_file=args.env_file, wait_seconds=args.wait_seconds), indent=2))


if __name__ == '__main__':
    main()
