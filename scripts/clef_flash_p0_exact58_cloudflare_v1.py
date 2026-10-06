#!/usr/bin/env python3
"""Cloudflare-only exact DEV-003–060 continuation of interrupted Clef Flash P0.

Preparation is offline and writes only the requested manifest.  Execution is
explicitly gated by a reviewed manifest, smoke/root review, and a single-stage
grant.  A missing, malformed, unknown, or provider-error result stops the
suffix and preserves the remaining requests as never sent.
"""
import argparse
import base64
from decimal import Decimal
import json
import os
from pathlib import Path
import time
import uuid
from urllib.parse import urlparse

import clef_native_preparation as prep
import clef_native_remaining as remaining
import clef_native_smoke_runner as smoke
import clef_connected_app_bridge as bridge
import clef_native_remaining_cloudflare_v1 as cf
import clef_native_remaining_cloudflare_v2 as inventory
import clef_cloudflare_authority_v1 as historical
import clef_flash_p0_suffix as first_controller

ROOT = prep.ROOT
BASE = ROOT / 'results/clef-native-v1'
PARENT = BASE / 'clef-flash/fresh3/P0/development'
PARENT_COMPLETION = PARENT / 'completion.json'
PARENT_AUDIT = PARENT / 'external-error-audit.json'
PARENT_SMOKE_REVIEW = BASE / 'clef-flash/fresh3/P0/smoke/smoke-review.json'
SOURCE_MANIFEST = BASE / 'repeat-continuation-v1/remaining-admission-v1.json'
FIRST_MANIFEST = BASE / 'clef-flash/fresh3/P0/development-suffix-manifest-v1.json'
FIRST = BASE / 'clef-flash/fresh3/P0/development-suffix-v1'
DEFAULT_MANIFEST = BASE / 'cloudflare-budget-v1/flash-exact58-v1/plan.json'
DEFAULT_BASE = BASE / 'cloudflare-budget-v1/flash-exact58-v1/development'
AUTHORITY = cf.LEDGER
AUTHORITY_SNAPSHOT = cf.BASE / 'historical-upper-bound.json'  # reviewed cap provenance
CAP = Decimal('10.00')
HOLD = Decimal('0.342142')
MODEL = 'clef-flash'
REPEAT = 'fresh3'
CONDITION = 'P0'
PHASE = 'development'
STAGE = 'clef-flash/fresh3/P0/development-exact58-cloudflare-v1'
SUFFIX_IDS = tuple(f'DEV-{i:03d}' for i in range(3, 61))
KIND = 'clef-flash-p0-exact58-cloudflare-v1'
GRANT_KIND = 'clef-flash-p0-exact58-cloudflare-v1-grant'
CLAIM_KIND = 'clef-flash-p0-exact58-cloudflare-v1-claim'
COMPLETION_KIND = 'clef-flash-p0-exact58-cloudflare-v1-completion'
HOLD_ID = 'cloudflare-only-clef-flash-fresh3-p0-development-exact58-v1'
SOURCE_FILES = (
    'scripts/clef_flash_p0_exact58_cloudflare_v1.py',
    'scripts/clef_flash_cloudflare_dispatcher_v1.js',
    'scripts/clef_flash_p0_suffix.py',
    'scripts/clef_cloudflare_operator_v1.py',
    'scripts/clef_native_remaining_cloudflare_v1.py',
    'scripts/clef_native_remaining_cloudflare_v2.py',
    'scripts/clef_cloudflare_authority_v1.py',
    'scripts/clef_native_preparation.py',
    'scripts/clef_native_remaining.py',
    'scripts/clef_native_smoke_runner.py',
    'scripts/clef_connected_app_bridge.py',
    'tests/test_clef_flash_p0_exact58_cloudflare_v1.py',
    'tests/test_clef_flash_cloudflare_dispatcher_v1.cjs',
)


def read_json(path):
    return json.loads(Path(path).read_bytes())


def canonical(value):
    return prep.canonical(value) + b'\n'


def sha(path_or_bytes):
    value = path_or_bytes if isinstance(path_or_bytes, bytes) else Path(path_or_bytes).read_bytes()
    return prep.sha(value)


def parent_checked(root=ROOT):
    root = Path(root)
    completion = read_json(root / PARENT_COMPLETION.relative_to(ROOT))
    audit = read_json(root / PARENT_AUDIT.relative_to(ROOT))
    if (completion.get('model') != MODEL or completion.get('stage') != 'clef-flash/fresh3/P0/development' or
            completion.get('status') != 'stopped' or completion.get('attempted') != 1 or
            completion.get('counts') != {'valid': 0, 'invalid_output': 0, 'service_error': 0, 'unknown_outcome': 1} or
            completion.get('never_sent') != [f'DEV-{i:03d}' for i in range(2, 61)]):
        raise ValueError('Parent completion is not the frozen DEV-001 unknown boundary')
    if (audit.get('kind') != 'clef-native-connected-app-external-error-audit-v1' or
            audit.get('stage') != 'clef-flash/fresh3/P0/development' or audit.get('id') != 'DEV-001' or
            audit.get('no_replay') is not True or audit.get('charge_status') != 'unknown_reserved' or
            audit.get('provider_envelope_available') is not False):
        raise ValueError('Parent external error audit is not the frozen no-replay boundary')
    directory = root / PARENT.relative_to(ROOT)
    for name, key in [('claim.json', 'claim_sha256'), ('journal.jsonl', 'journal_sha256'),
                      ('raw.jsonl', 'raw_sha256'), ('records.jsonl', 'records_sha256')]:
        if sha(directory / name) != completion.get(key):
            raise ValueError('Parent evidence changed')
    records = [json.loads(line) for line in (directory / 'records.jsonl').read_bytes().splitlines()]
    if len(records) != 1 or records[0].get('id') != 'DEV-001' or records[0].get('status') != 'unknown_outcome':
        raise ValueError('Parent attempted records differ from boundary')
    bridge_request_path = directory / 'app-bridge' / (records[0]['attempt_id'] + '.request.json')
    bridge_request = read_json(bridge_request_path)
    if (audit.get('completion_sha256') != sha(root / PARENT_COMPLETION.relative_to(ROOT)) or
            audit.get('attempt_id') != records[0].get('attempt_id') or
            audit.get('request_sha256') != sha(bridge_request_path) or
            bridge_request.get('request_sha256') != records[0].get('request_sha256') or
            prep.sha(prep.canonical(bridge_request.get('body'))) != records[0].get('request_sha256')):
        raise ValueError('Parent external audit differs from terminal record')
    return completion, audit


def first_suffix_checked(root=ROOT):
    root = Path(root)
    directory = root / FIRST.relative_to(ROOT)
    completion = read_json(directory / 'completion.json')
    audit = read_json(directory / 'external-error-audit.json')
    if (completion.get('kind') != 'clef-flash-p0-suffix-completion-v1' or
            completion.get('model') != MODEL or
            completion.get('stage') != 'clef-flash/fresh3/P0/development-suffix-v1' or
            completion.get('status') != 'stopped' or completion.get('attempted') != 1 or
            completion.get('counts') != {'valid': 0, 'invalid_output': 0,
                                         'service_error': 0, 'unknown_outcome': 1} or
            completion.get('never_sent') != list(SUFFIX_IDS) or
            audit.get('id') != 'DEV-002' or audit.get('no_replay') is not True or
            audit.get('charge_status') != 'unknown_reserved' or
            audit.get('provider_envelope_available') is not False or
            audit.get('completion_sha256') != sha(directory / 'completion.json')):
        raise ValueError('First suffix is not exact DEV-002 unknown boundary')
    bindings = {}
    for name in ('claim.json', 'budget.jsonl', 'journal.jsonl', 'raw.jsonl',
                 'records.jsonl', 'completion.json', 'external-error-audit.json'):
        path = directory / name
        bindings[str(path.relative_to(root))] = sha(path)
    for name, key in [('claim.json', 'claim_sha256'),
                      ('journal.jsonl', 'journal_sha256'),
                      ('raw.jsonl', 'raw_sha256'),
                      ('records.jsonl', 'records_sha256')]:
        if bindings[str((directory / name).relative_to(root))] != completion[key]:
            raise ValueError('First suffix evidence changed')
    records = [json.loads(line) for line in (directory / 'records.jsonl').read_bytes().splitlines()]
    raw = [json.loads(line) for line in (directory / 'raw.jsonl').read_bytes().splitlines()]
    budget = [json.loads(line) for line in (directory / 'budget.jsonl').read_bytes().splitlines()]
    if (len(records) != len(raw) or len(records) != 1 or len(budget) != 2 or
            records[0].get('id') != 'DEV-002' or records[0].get('status') != 'unknown_outcome' or
            raw[0].get('id') != 'DEV-002' or budget[1].get('id') != 'DEV-002' or
            len({records[0].get('attempt_id'), raw[0].get('attempt_id'),
                 budget[1].get('attempt_id')}) != 1):
        raise ValueError('First suffix attempted record differs')
    attempt = records[0]['attempt_id']
    for name in ('request.json', 'dispatch.json', 'tool-result.json', 'app-result.json'):
        path = directory / 'app-bridge' / f'{attempt}.{name}'
        bindings[str(path.relative_to(root))] = sha(path)
    request_path = directory / 'app-bridge' / f'{attempt}.request.json'
    request = read_json(request_path)
    if (audit.get('attempt_id') != attempt or
            audit.get('request_sha256') != sha(request_path) or
            audit.get('dispatch_sha256') != bindings[str((directory / 'app-bridge' /
                f'{attempt}.dispatch.json').relative_to(root))] or
            audit.get('outer_tool_result_sha256') != bindings[str((directory / 'app-bridge' /
                f'{attempt}.tool-result.json').relative_to(root))] or
            audit.get('app_result_sha256') != bindings[str((directory / 'app-bridge' /
                f'{attempt}.app-result.json').relative_to(root))] or
            request.get('id') != 'DEV-002' or request.get('model') != MODEL or
            request.get('request_sha256') != records[0].get('request_sha256') or
            prep.sha(prep.canonical(request.get('body'))) != records[0].get('request_sha256')):
        raise ValueError('First suffix audit differs from saved request or outer result')
    return bindings


def manifest_value(root=ROOT):
    root = Path(root)
    if HOLD != prep.reservation_usd(MODEL, len(SUFFIX_IDS)):
        raise ValueError('Flash suffix cap differs from full-context request bound')
    completion, audit = parent_checked(root)
    first_bindings = first_suffix_checked(root)
    first_manifest, first_manifest_hash = first_controller.checked_manifest(
        root / FIRST_MANIFEST.relative_to(ROOT), root=root)
    source = read_json(root / SOURCE_MANIFEST.relative_to(ROOT))
    identity = 'clef-flash/fresh3/P0'
    stage = source.get('stages', {}).get(identity)
    if not isinstance(stage, dict):
        raise ValueError('Frozen full request manifest missing Flash P0')
    requests = stage.get('requests')
    if (not isinstance(requests, list) or [r.get('id') for r in requests] != list(prep.IDS)):
        raise ValueError('Frozen request source differs')
    if (first_manifest['source_manifest_sha256'] !=
            sha(root / SOURCE_MANIFEST.relative_to(ROOT)) or
            [r['id'] for r in first_manifest['requests']] !=
            [f'DEV-{i:03d}' for i in range(2, 61)]):
        raise ValueError('First suffix frozen plan changed')
    suffix = [r for r in requests if r.get('id') in SUFFIX_IDS]
    if len(suffix) != 58 or [r['id'] for r in suffix] != list(SUFFIX_IDS):
        raise ValueError('Suffix is not exactly DEV-003 through DEV-060')
    return {
        'kind': KIND,
        'status': 'prepared_no_grant_no_dispatch',
        'model': MODEL, 'repeat': REPEAT, 'condition': CONDITION, 'phase': PHASE,
        'stage': STAGE, 'route': prep.MODELS[MODEL]['route'],
        'request_ids': list(SUFFIX_IDS), 'requests': suffix,
        'request_count': 58, 'hold_usd': str(HOLD),
        'transport': 'mcp__codex_apps__cloudflare_execute',
        'reference_labels_sent': False,
        'source_manifest_sha256': sha(root / SOURCE_MANIFEST.relative_to(ROOT)),
        'parent_completion_sha256': sha(root / PARENT_COMPLETION.relative_to(ROOT)),
        'parent_external_error_audit_sha256': sha(root / PARENT_AUDIT.relative_to(ROOT)),
        'parent_smoke_review_sha256': sha(root / PARENT_SMOKE_REVIEW.relative_to(ROOT)),
        'parent_request_set_sha256': prep.sha(prep.canonical({'requests': requests})),
        'parent_never_sent_sha256': prep.sha(prep.canonical([f'DEV-{i:03d}' for i in range(2, 61)])),
        'first_suffix_file_bindings': first_bindings,
        'first_suffix_manifest_sha256': first_manifest_hash,
        'controller_sha256': sha(Path(__file__)),
        'bridge_sha256': sha(Path(bridge.__file__)),
        'helper_sha256': {name: sha(Path(module.__file__)) for name, module in [('preparation', prep), ('remaining', remaining), ('smoke', smoke)]},
        'billing_source_sha256': sha(root / 'results/clef-native-v1/clef-flash-billing-source.md'),
        'historical_receipt_sha256': sha(root / cf.HISTORICAL.relative_to(ROOT)),
        'cloudflare_authority_plan_sha256': sha(root / cf.PLAN.relative_to(ROOT)),
        'operator_sha256': sha(root / 'scripts/clef_cloudflare_operator_v1.py'),
        'dispatcher_sha256': sha(root / 'scripts/clef_flash_cloudflare_dispatcher_v1.js'),
        'source_bindings': {name: sha(root / name) for name in SOURCE_FILES},
    }


def checked_manifest(path=DEFAULT_MANIFEST, root=ROOT):
    saved = read_json(path)
    expected = manifest_value(root)
    if saved != expected:
        raise ValueError('Reviewed suffix manifest differs from frozen parent/request sources')
    return saved, sha(path)


def checked_parent_inputs(root=ROOT):
    rows, policy = prep.inputs_and_policy(Path(root))
    if [row['id'] for row in rows] != list(prep.IDS):
        raise ValueError('Input order changed')
    return rows, policy


class AuthorityLedger(cf.AuthorityLedger):
    def __init__(self, path, expected_head_hash, snapshot_path=AUTHORITY_SNAPSHOT):
        with inventory.historical_inventory():
            super().__init__(path, snapshot_path, expected_head_hash)

    def hold(self, grant_hash):
        if HOLD_ID in self.ids or self.total + HOLD > cf.CAP:
            raise ValueError('Duplicate Flash suffix or Cloudflare $10 cap exhausted')
        smoke.durable(self.stream, {'event': 'hold', 'id': HOLD_ID, 'usd': str(HOLD),
                                    'grant_sha256': grant_hash})
        self.ids.add(HOLD_ID); self.total += HOLD


class StageLedger:
    def __init__(self, path, manifest_hash, grant_hash):
        self.handle = Path(path).open('xb+')
        self.total = Decimal(0); self.seen = set()
        smoke.durable(self.handle, {'event': 'budget', 'cap_usd': str(HOLD), 'stage': STAGE,
                                    'manifest_sha256': manifest_hash, 'grant_sha256': grant_hash})

    def reserve(self, rid):
        if rid not in SUFFIX_IDS or rid in self.seen or self.total + prep.reservation_usd(MODEL, 1) > HOLD:
            raise ValueError('Duplicate request or suffix stage cap exhausted')
        attempt_id = str(uuid.uuid4()); amount = prep.reservation_usd(MODEL, 1)
        smoke.durable(self.handle, {'event': 'reserve', 'stage': STAGE,
                                    'attempt_id': attempt_id, 'id': rid, 'usd': str(amount)})
        self.seen.add(rid); self.total += amount
        return attempt_id, amount

    def close(self): self.handle.close()


class AppTransport:
    def __init__(self, directory, account_id, grant_hash, wait_seconds):
        self.directory = Path(directory); self.account_id = account_id
        self.grant_hash = grant_hash; self.wait_seconds = wait_seconds

    def __call__(self, url, headers, body):
        expected = f'/client/v4/accounts/{self.account_id}/ai/run/{prep.MODELS[MODEL]["route"]}'
        parsed = urlparse(url)
        if (parsed.scheme != 'https' or parsed.netloc != 'api.cloudflare.com' or parsed.path != expected or
                parsed.query or parsed.fragment or headers.get('Content-Type') != 'application/json' or
                headers.get('Accept') != 'application/json' or
                not headers.get('Authorization', '').startswith('Bearer ') or not isinstance(body, bytes) or
                json.loads(body).get('model') != MODEL):
            raise ValueError('Unpinned connected-app request')
        journal = [json.loads(line) for line in (self.directory / 'journal.jsonl').read_bytes().splitlines()]
        if len(journal) < 2 or journal[-2].get('event') != 'reserved' or journal[-1].get('event') != 'started' or journal[-2]['request_sha256'] != sha(body):
            raise ValueError('No matching durable stage reservation')
        attempt_id = journal[-1]['attempt_id']; bridge_dir = self.directory / 'app-bridge'; bridge_dir.mkdir(exist_ok=True)
        request = {'kind': bridge.KIND + '-request', 'attempt_id': attempt_id, 'id': journal[-1]['id'],
                   'model': MODEL, 'stage': STAGE, 'review_sha256': self.grant_hash,
                   'account_id_sha256': prep.sha(self.account_id.encode('ascii')), 'request_sha256': sha(body),
                   'method': 'POST', 'path': '/accounts/{ACCOUNT_ID}/ai/run/' + prep.MODELS[MODEL]['route'],
                   'body': json.loads(body)}
        bridge.atomic_json(bridge_dir / f'{attempt_id}.request.json', request)
        deadline = time.monotonic() + self.wait_seconds
        while time.monotonic() < deadline:
            try: raw = (bridge_dir / f'{attempt_id}.response.json').read_bytes()
            except FileNotFoundError: time.sleep(0.1); continue
            if len(raw) > smoke.MAX_RESPONSE_BYTES + 4096: raise ValueError('Bridge response too large')
            reply = json.loads(raw)
            if (set(reply) != {'kind','attempt_id','request_sha256','http_status','body_base64'} or
                    reply.get('kind') != bridge.KIND + '-response' or reply.get('attempt_id') != attempt_id or
                    reply.get('request_sha256') != sha(body) or type(reply.get('http_status')) is not int):
                raise ValueError('Malformed or mismatched bridge response')
            response = base64.b64decode(reply['body_base64'], validate=True)
            if len(response) > smoke.MAX_RESPONSE_BYTES: raise ValueError('Bridge response too large')
            if (bridge_dir / f'{attempt_id}.app-result.json').read_bytes() != response:
                raise ValueError('Saved app result differs')
            tool = read_json(bridge_dir / f'{attempt_id}.tool-result.json')
            if tool.get('isError', False) is not False or json.loads(tool['content'][0]['text']) != json.loads(response):
                raise ValueError('Outer tool result differs')
            dispatch = read_json(bridge_dir / f'{attempt_id}.dispatch.json')
            if dispatch.get('request_sha256') != sha(body) or not dispatch.get('operator'):
                raise ValueError('Operator dispatch evidence absent')
            return reply['http_status'], response
        raise TimeoutError('Connected-app outcome unknown; do not retry')


def grant_value(account_id, authority_head, wait_seconds=300, *, root=ROOT):
    root = Path(root)
    plan, manifest_hash = checked_manifest(root / DEFAULT_MANIFEST.relative_to(ROOT), root=root)
    if (not smoke.ACCOUNT_PATTERN.fullmatch(account_id) or
            type(wait_seconds) is not int or not 1 <= wait_seconds <= 600 or
            not isinstance(authority_head, str) or len(authority_head) != 64):
        raise ValueError('Exact Flash account, bounded wait, and authority head required')
    return {'kind': GRANT_KIND, 'approved': True, 'authorized_by_user': True,
                'reviewer': '/root',
                'model': MODEL, 'stage': STAGE, 'pass': REPEAT, 'condition': CONDITION,
                'phase': PHASE, 'manifest_sha256': manifest_hash,
                'controller_sha256': sha(Path(__file__)), 'bridge_sha256': sha(Path(bridge.__file__)),
                'account_id_sha256': prep.sha(account_id.encode('ascii')),
                'transport': 'mcp__codex_apps__cloudflare_execute', 'full_context_hold_usd': str(HOLD),
                'global_authority_cap_usd': str(CAP),
                'authority_hold_id': HOLD_ID,
                'historical_receipt_sha256': plan['historical_receipt_sha256'],
                'smoke_review_sha256': sha(root / PARENT_SMOKE_REVIEW.relative_to(ROOT)), 'prior_completion_sha256': sha(root / PARENT_COMPLETION.relative_to(ROOT)),
                'first_suffix_completion_sha256': plan['first_suffix_file_bindings'][str(FIRST.relative_to(ROOT) / 'completion.json')],
                'exhaustion_policy': 'pause', 'wait_seconds': wait_seconds,
                'global_authority_ledger_sha256_at_admission': authority_head,
                'billing_source_sha256': sha(root / 'results/clef-native-v1/clef-flash-billing-source.md'),
                'parent_external_error_audit_sha256': sha(root / PARENT_AUDIT.relative_to(ROOT))}


def checked_grant(path, manifest_hash, account_id, wait_seconds, root=ROOT):
    grant = read_json(path)
    expected = grant_value(account_id, grant.get('global_authority_ledger_sha256_at_admission'),
                           wait_seconds, root=root)
    if grant != expected or grant['manifest_sha256'] != manifest_hash:
        raise ValueError('Exact reviewed suffix grant required')
    return grant, sha(path)


def run_stage(manifest_path, grant_path, *, root=ROOT, base=DEFAULT_BASE, authority_path=AUTHORITY,
              snapshot_path=AUTHORITY_SNAPSHOT, environment=None, env_file=None,
              wait_seconds=300, transport=None, billing_source=None):
    if type(wait_seconds) is not int or not 1 <= wait_seconds <= 600: raise ValueError('Invalid bounded wait')
    account_id, token = smoke.credentials(os.environ if environment is None else environment, env_file)
    if not isinstance(account_id, str) or not smoke.ACCOUNT_PATTERN.fullmatch(account_id) or not isinstance(token, str) or not token.strip():
        raise ValueError('Cloudflare credentials unavailable')
    root = Path(root)
    manifest, manifest_hash = checked_manifest(manifest_path, root=root)
    parent_claim = read_json(root / PARENT.relative_to(ROOT) / 'claim.json')
    if (parent_claim.get('account_id_sha256') != prep.sha(account_id.encode('ascii')) or
            parent_claim.get('manifest_sha256') != manifest['source_manifest_sha256'] or
            parent_claim.get('model') != MODEL or parent_claim.get('stage') != 'clef-flash/fresh3/P0/development'):
        raise ValueError('Parent account or controls differ from suffix')
    remaining.checked_smoke_review(root / PARENT_SMOKE_REVIEW.relative_to(ROOT),
        model=MODEL, repeat=REPEAT, condition=CONDITION,
        manifest_hash=manifest['source_manifest_sha256'], account_id=account_id,
        base=root / BASE.relative_to(ROOT))
    if sha((billing_source or smoke.billing_fetch)(prep.MODELS[MODEL]['source'])) != manifest['billing_source_sha256']:
        raise ValueError('Reviewed Cloudflare billing page changed')
    rows, policy = checked_parent_inputs(root)
    requests = []
    by_id = {r['id']: r for r in rows}
    for item in manifest['requests']:
        row = by_id.get(item['id'])
        body = prep.canonical(prep.request_payload(row['feedback'], policy, MODEL, CONDITION))
        if prep.sha(body) != item['payload_sha256'] or prep.sha(row['feedback'].encode()) != item['input_sha256']:
            raise ValueError('Frozen input-only request differs')
        requests.append((row['id'], body, item['payload_sha256']))
    directory = Path(base)
    if directory.exists(): raise ValueError('Suffix already claimed; no replay')
    grant, grant_hash = checked_grant(grant_path, manifest_hash, account_id, wait_seconds, root=root)
    authority = AuthorityLedger(authority_path, grant['global_authority_ledger_sha256_at_admission'], snapshot_path)
    try:
        authority.hold(grant_hash); directory.mkdir(parents=True, exist_ok=False)
        smoke.exclusive_json(directory / 'claim.json', {'kind': CLAIM_KIND, 'model': MODEL, 'stage': STAGE,
            'manifest_sha256': manifest_hash, 'grant_sha256': grant_hash, 'controller_sha256': sha(Path(__file__)),
            'bridge_sha256': sha(Path(bridge.__file__)), 'account_id_sha256': prep.sha(account_id.encode('ascii')),
            'parent_completion_sha256': sha(root / PARENT_COMPLETION.relative_to(ROOT)),
            'first_suffix_completion_sha256': manifest['first_suffix_file_bindings'][str(FIRST.relative_to(ROOT) / 'completion.json')],
            'global_authority_hold_usd': str(HOLD),
            'charge_status': 'unknown_reserved'})
        ledger = StageLedger(directory / 'budget.jsonl', manifest_hash, grant_hash)
        try:
            caller = transport or AppTransport(directory, account_id, grant_hash, wait_seconds)
            counts = {'valid': 0, 'invalid_output': 0, 'service_error': 0, 'unknown_outcome': 0}; sent = 0
            with (directory / 'journal.jsonl').open('xb') as journal, (directory / 'raw.jsonl').open('xb') as raw_file, (directory / 'records.jsonl').open('xb') as records_file:
                for rid, body, request_hash in requests:
                    attempt_id, amount = ledger.reserve(rid)
                    smoke.durable(journal, {'event': 'reserved', 'attempt_id': attempt_id, 'id': rid, 'request_sha256': request_hash, 'usd': str(amount)})
                    smoke.durable(journal, {'event': 'started', 'attempt_id': attempt_id, 'id': rid}); sent += 1
                    url = f'https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/run/{prep.MODELS[MODEL]["route"]}'
                    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json', 'Accept': 'application/json'}
                    start = time.monotonic(); status = None; response = b''; error_type = None
                    try:
                        status, response = caller(url, headers, body)
                        if type(status) is not int or not isinstance(response, bytes) or len(response) > smoke.MAX_RESPONSE_BYTES:
                            raise ValueError('Malformed or oversized transport response')
                    except Exception as error:
                        error_type = type(error).__name__
                        status, response = None, b'' 
                    if not isinstance(response, bytes): response = b''
                    redacted = token.encode() in response
                    if redacted: response = response.replace(token.encode(), b'[REDACTED]')
                    smoke.durable(raw_file, {'attempt_id': attempt_id, 'id': rid, 'request_sha256': request_hash, 'http_status': status, 'raw_response_base64': base64.b64encode(response).decode(), 'response_sha256': prep.sha(response), 'redacted': redacted, 'error_type': error_type, 'client_seconds': time.monotonic()-start})
                    parsed = None
                    if error_type or status is None: outcome, reason = 'unknown_outcome', 'transport_outcome_unknown'
                    elif status != 200 or redacted: outcome, reason = 'service_error', f'HTTP_{status}' if status != 200 else 'credential_echo_redacted'
                    else:
                        try:
                            envelope = json.loads(response)
                        except (UnicodeError, json.JSONDecodeError, ValueError, TypeError):
                            outcome, reason = 'service_error', 'malformed_provider_envelope'
                        else:
                            if (not isinstance(envelope, dict) or envelope.get('success') is not True or
                                    envelope.get('errors') != [] or not isinstance(envelope.get('result'), dict)):
                                outcome, reason = 'service_error', 'provider_envelope_error'
                            else:
                                try:
                                    parsed = prep.parse_rest_response(envelope, MODEL); outcome, reason = 'valid', None
                                except (UnicodeError, ValueError, KeyError, TypeError):
                                    outcome, reason = 'invalid_output', 'strict_response_validation'
                    counts[outcome] += 1
                    smoke.durable(records_file, {'attempt_id': attempt_id, 'id': rid, 'request_sha256': request_hash, 'status': outcome, 'reason': reason, 'parsed': parsed, 'charge_status': 'unknown_reserved', 'reservation_usd': str(amount), 'reference_labels_read': False})
                    smoke.durable(journal, {'event': 'finished', 'attempt_id': attempt_id, 'id': rid, 'status': outcome})
                    if outcome in ('service_error', 'unknown_outcome', 'invalid_output'): break
            completion = {'kind': COMPLETION_KIND, 'model': MODEL, 'stage': STAGE, 'status': 'complete' if sent == len(SUFFIX_IDS) and counts['valid'] == len(SUFFIX_IDS) else 'stopped', 'attempted': sent, 'counts': counts, 'never_sent': list(SUFFIX_IDS[sent:]), 'claim_sha256': sha(directory/'claim.json'), 'journal_sha256': sha(directory/'journal.jsonl'), 'raw_sha256': sha(directory/'raw.jsonl'), 'records_sha256': sha(directory/'records.jsonl'), 'unknown_cost_reserved_usd': str(prep.reservation_usd(MODEL, sent)), 'parent_completion_sha256': sha(root / PARENT_COMPLETION.relative_to(ROOT)), 'first_suffix_completion_sha256': manifest['first_suffix_file_bindings'][str(FIRST.relative_to(ROOT) / 'completion.json')], 'parent_external_error_audit_sha256': sha(root / PARENT_AUDIT.relative_to(ROOT))}
            smoke.exclusive_json(directory / 'completion.json', completion); return completion
        finally: ledger.close()
    finally: authority.close()


def submit_response(request_path, app_result_path, tool_result_path=None):
    """Bind the operator's pre-call dispatch and full MCP result before release."""
    request_path, app_result_path = Path(request_path), Path(app_result_path)
    ready = read_json(request_path)
    attempt = ready.get('attempt_id', '')
    if (ready.get('kind') != bridge.KIND + '-request' or ready.get('stage') != STAGE or
            ready.get('model') != MODEL or ready.get('id') not in SUFFIX_IDS or
            request_path.name != attempt + '.request.json' or
            ready.get('request_sha256') != prep.sha(prep.canonical(ready.get('body')))):
        raise ValueError('Invalid suffix ready request')
    parent = request_path.parent
    dispatch = read_json(parent / (attempt + '.dispatch.json'))
    if dispatch.get('request_sha256') != ready['request_sha256'] or not dispatch.get('operator'):
        raise ValueError('Pre-call operator dispatch evidence absent')
    app_bytes = app_result_path.read_bytes()
    if len(app_bytes) > smoke.MAX_RESPONSE_BYTES:
        raise ValueError('App result too large')
    app = json.loads(app_bytes)
    tool_path = Path(tool_result_path) if tool_result_path else parent / (attempt + '.tool-result.json')
    tool_bytes = tool_path.read_bytes()
    if len(tool_bytes) > smoke.MAX_RESPONSE_BYTES * 2:
        raise ValueError('Tool result too large')
    tool = json.loads(tool_bytes)
    if (tool.get('isError', False) is not False or not isinstance(tool.get('content'), list) or
            len(tool['content']) != 1 or tool['content'][0].get('type') != 'text' or
            json.loads(tool['content'][0].get('text', '')) != app):
        raise ValueError('Tool result differs from app response')
    for target, content in [(parent / (attempt + '.app-result.json'), app_bytes),
                            (parent / (attempt + '.tool-result.json'), tool_bytes)]:
        if target.exists():
            if target.read_bytes() != content:
                raise ValueError('Existing bridge evidence differs')
        else:
            with target.open('xb') as handle:
                handle.write(content); handle.flush(); os.fsync(handle.fileno())
    return bridge.submit_response(request_path, parent / (attempt + '.app-result.json'))


def record_timing(request_path, start_ms, end_ms, duration_ms, clock, outcome):
    """Persist only caller-observed MCP interval; provider server time is unknown."""
    request_path = Path(request_path)
    ready = read_json(request_path)
    attempt = ready.get('attempt_id', '')
    dispatch = read_json(request_path.with_name(attempt + '.dispatch.json'))
    if (request_path.name != attempt + '.request.json' or
            ready.get('kind') != bridge.KIND + '-request' or
            ready.get('model') != MODEL or ready.get('stage') != STAGE or
            ready.get('id') not in SUFFIX_IDS or
            dispatch.get('request_sha256') != ready.get('request_sha256') or
            not dispatch.get('operator') or
            not all(type(value) is int and value >= 0 for value in
                    (start_ms, end_ms, duration_ms)) or
            duration_ms > 3_600_000 or
            clock not in ('performance_now_monotonic', 'date_now_wall') or
            outcome not in ('outer_tool_exception',
                            'outer_returned_original_save_failed',
                            'outer_returned_original_saved')):
        raise ValueError('Unbound or malformed Flash dispatch timing')
    target = request_path.with_name(attempt + '.dispatch-timing.json')
    bridge.atomic_json(target, {
        'kind': 'clef-flash-exact58-client-timing-v1',
        'attempt_id': attempt, 'id': ready['id'],
        'request_sha256': ready['request_sha256'],
        'client_start_unix_ms': start_ms,
        'client_end_unix_ms': end_ms,
        'client_duration_ms': duration_ms,
        'clock': clock, 'outcome': outcome,
        'provider_server_duration_ms': None,
    })
    return target


def main():
    parser = argparse.ArgumentParser(); sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare'); p.add_argument('--output', type=Path, required=True)
    c = sub.add_parser('check'); c.add_argument('--manifest', type=Path, default=DEFAULT_MANIFEST)
    r = sub.add_parser('run'); r.add_argument('--execute', action='store_true', required=True); r.add_argument('--manifest', type=Path, required=True); r.add_argument('--grant', type=Path, required=True); r.add_argument('--base', type=Path, default=DEFAULT_BASE); r.add_argument('--env-file', type=Path); r.add_argument('--wait-seconds', type=int, default=300)
    s = sub.add_parser('submit'); s.add_argument('--request', type=Path, required=True); s.add_argument('--app-result-file', type=Path, required=True); s.add_argument('--tool-result-file', type=Path)
    t = sub.add_parser('record-timing'); t.add_argument('--request', type=Path, required=True); t.add_argument('--start-ms', type=int, required=True); t.add_argument('--end-ms', type=int, required=True); t.add_argument('--duration-ms', type=int, required=True); t.add_argument('--clock', required=True); t.add_argument('--outcome', required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        args.output.parent.mkdir(parents=True, exist_ok=True); smoke.exclusive_json(args.output, manifest_value()); print(args.output); return
    if args.command == 'check': print(sha(checked_manifest(args.manifest)[0] and args.manifest)); return
    if args.command == 'submit': print(submit_response(args.request, args.app_result_file, args.tool_result_file)); return
    if args.command == 'record-timing': print(record_timing(args.request, args.start_ms, args.end_ms, args.duration_ms, args.clock, args.outcome)); return
    print(json.dumps(run_stage(args.manifest, args.grant, base=args.base, env_file=args.env_file, wait_seconds=args.wait_seconds), indent=2))


if __name__ == '__main__': main()
