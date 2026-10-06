#!/usr/bin/env python3
"""Single-use Cloudflare Jev stage admission and saved-result operator.

This module has no inference transport. The connected-app dispatcher in the
same versioned set makes at most one POST after a durable dispatch claim.
"""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path
import re
import urllib.request
import uuid

import clef_connected_app_bridge as bridge
import clef_native_remaining_cloudflare_v1 as clef_authority
import clef_native_smoke_runner as smoke
import jev_cloudflare_native_preparation_v1 as prep


ROOT = prep.ROOT
BASE = ROOT / 'results/jev-cloudflare-native-v1'
PLAN = BASE / 'plan.json'
AUTHORITY = ROOT / 'results/clef-native-v1/cloudflare-budget-v1/authority.jsonl'
DISPATCHER = ROOT / 'scripts/jev_cloudflare_dispatcher_v1.js'
KIND = 'jev-cloudflare-native-execution-v1'
CAP = Decimal('10.00')
PHASES = ('smoke', 'development')
ACCOUNT_PATTERN = re.compile(r'[a-f0-9]{32}\Z')
ATTEMPT_PATTERN = re.compile(r'[a-f0-9-]{36}\Z')
MAX_SOURCE_BYTES = 1_048_576
MAX_RESULT_BYTES = 1_048_576


def read_json(path):
    return json.loads(Path(path).read_bytes())


def read_jsonl(path):
    return [json.loads(line) for line in Path(path).read_bytes().splitlines() if line]


def verify_saved_originals(directory, raw_rows):
    bridge_dir = Path(directory) / 'app-bridge'
    for item in raw_rows:
        attempt = item.get('attempt_id')
        if not isinstance(attempt, str) or not ATTEMPT_PATTERN.fullmatch(attempt):
            raise ValueError('Raw attempt identity changed')
        timing_path = bridge_dir / f'{attempt}.timing.json'
        if (item.get('timing_file') != timing_path.name or
                prep.sha(timing_path.read_bytes()) != item.get('timing_sha256')):
            raise ValueError('Saved client timing changed')
        saved_hash = item.get('original_tool_result_sha256')
        saved_name = item.get('original_tool_result_file')
        if saved_hash is None:
            if saved_name is not None or read_json(
                    bridge_dir / f'{attempt}.tool-call-error.json') != {
                        'kind': KIND + '-tool-call-error', 'attempt_id': attempt,
                        'reason': 'outer_tool_exception_outcome_unknown'}:
                raise ValueError('Unknown tool outcome marker changed')
        elif (saved_name != f'{attempt}.tool-result.original.json' or
              prep.sha((bridge_dir / saved_name).read_bytes()) != saved_hash):
            raise ValueError('Saved original tool result changed')


def durable_file(path, value):
    bridge.atomic_json(path, value)


def append(path, value):
    with Path(path).open('ab') as handle:
        smoke.durable(handle, value)


def money(value):
    if type(value) is not str:
        raise ValueError('Money must be a decimal string')
    amount = Decimal(value)
    if not amount.is_finite() or amount <= 0:
        raise ValueError('Invalid authority amount')
    return amount


def stage_name(repeat, condition, phase):
    if repeat not in prep.PASSES or condition not in prep.CONDITIONS or phase not in PHASES:
        raise ValueError('Unplanned Jev stage')
    return f'jev/{repeat}/{condition}/{phase}'


def stage_dir(repeat, condition, phase, base=BASE):
    stage_name(repeat, condition, phase)
    return Path(base) / repeat / condition / phase


def hold_id(repeat, condition, phase):
    stage_name(repeat, condition, phase)
    return f'cloudflare-only-jev-{repeat}-{condition.lower()}-{phase}'


def billing_fetch(url):
    if url != prep.MODEL_PAGE:
        raise ValueError('Unpinned Jev billing source')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                         smoke.NoRedirect())
    request = urllib.request.Request(url, headers={'Accept': 'text/html',
                                                   'User-Agent': 'recruitment-feedback-jev/1.0'})
    with opener.open(request, timeout=60) as response:
        raw = response.read(MAX_SOURCE_BYTES + 1)
    if len(raw) > MAX_SOURCE_BYTES:
        raise ValueError('Jev billing source too large')
    return raw


def checked_price_source(expected_hash, fetcher=billing_fetch):
    raw = fetcher(prep.MODEL_PAGE)
    if (not isinstance(raw, bytes) or len(raw) > MAX_SOURCE_BYTES or
            prep.sha(raw) != expected_hash or
            b'typesafe/jev' not in raw or b'0.042' not in raw or
            b'32,000' not in raw):
        raise ValueError('Reviewed Jev model page changed or lacks pinned terms')
    return prep.sha(raw)


def checked_authority(handle, expected_head):
    handle.seek(0)
    raw = handle.read()
    if prep.sha(raw) != expected_head or not raw.endswith(b'\n'):
        raise ValueError('Shared Cloudflare authority head changed')
    events = [json.loads(line) for line in raw.splitlines()]
    if not events:
        raise ValueError('Shared Cloudflare authority empty')
    header = events[0]
    expected_header = {
        'event': 'budget', 'kind': clef_authority.LEDGER_KIND,
        'cap_usd': str(CAP), 'historical_upper_bound_usd': '0.259584',
        'historical_receipt_sha256': clef_authority.digest(clef_authority.HISTORICAL),
        'plan_sha256': clef_authority.digest(clef_authority.PLAN),
    }
    if (not isinstance(header, dict) or
            any(header.get(key) != value for key, value in expected_header.items()) or
            not isinstance(header.get('initialization_review_sha256'), str) or
            len(header['initialization_review_sha256']) != 64):
        raise ValueError('Wrong shared Cloudflare authority header')
    seen = set()
    total = money(header['historical_upper_bound_usd'])
    for event in events[1:]:
        if (not isinstance(event, dict) or
                set(event) != {'event', 'id', 'usd', 'grant_sha256'} or
                event['event'] != 'hold' or type(event['id']) is not str or
                event['id'] in seen or
                not isinstance(event['grant_sha256'], str) or
                len(event['grant_sha256']) != 64):
            raise ValueError('Malformed or duplicate Cloudflare hold')
        seen.add(event['id'])
        total += money(event['usd'])
    if total > CAP:
        raise ValueError('Shared Cloudflare cap exceeded')
    return seen, total


def predecessor_hash(repeat, condition, *, base=BASE):
    if repeat == 'fresh1':
        return None
    prior = prep.PASSES[prep.PASSES.index(repeat) - 1]
    directory = stage_dir(prior, condition, 'development', base)
    completion_path = directory / 'completion.json'
    completion = read_json(completion_path)
    if (completion.get('kind') != KIND + '-completion' or
            completion.get('stage') != stage_name(prior, condition, 'development') or
            completion.get('status') != 'complete' or
            completion.get('attempted') != 60 or completion.get('never_sent') != []):
        raise ValueError('Prior Jev repeat has not closed')
    for filename, key in [('claim.json', 'claim_sha256'),
                          ('budget.jsonl', 'budget_sha256'),
                          ('journal.jsonl', 'journal_sha256'),
                          ('raw.jsonl', 'raw_sha256'),
                          ('records.jsonl', 'records_sha256')]:
        if prep.sha((directory / filename).read_bytes()) != completion.get(key):
            raise ValueError('Prior Jev evidence changed')
    verify_saved_originals(directory, read_jsonl(directory / 'raw.jsonl'))
    return prep.sha(completion_path.read_bytes())


def checked_smoke_review(path, repeat, condition, *, base=BASE, plan_hash):
    directory = stage_dir(repeat, condition, 'smoke', base)
    completion_path = directory / 'completion.json'
    completion = read_json(completion_path)
    if (completion.get('kind') != KIND + '-completion' or
            completion.get('stage') != stage_name(repeat, condition, 'smoke') or
            completion.get('status') != 'complete' or
            completion.get('attempted') != 3 or
            completion.get('counts') != {'valid': 3, 'invalid_output': 0,
                                         'service_error': 0, 'unknown_outcome': 0} or
            completion.get('never_sent') != []):
        raise ValueError('Full stage requires three valid smoke records')
    for filename, key in [('claim.json', 'claim_sha256'),
                          ('budget.jsonl', 'budget_sha256'),
                          ('journal.jsonl', 'journal_sha256'),
                          ('raw.jsonl', 'raw_sha256'),
                          ('records.jsonl', 'records_sha256')]:
        if prep.sha((directory / filename).read_bytes()) != completion.get(key):
            raise ValueError('Smoke evidence changed')
    verify_saved_originals(directory, read_jsonl(directory / 'raw.jsonl'))
    expected = {'kind': KIND + '-smoke-review', 'approved': True,
                'reviewer': '/root', 'stage': stage_name(repeat, condition, 'smoke'),
                'plan_sha256': plan_hash,
                'completion_sha256': prep.sha(completion_path.read_bytes()),
                'raw_sha256': completion['raw_sha256'],
                'records_sha256': completion['records_sha256'],
                'decision': 'admit_unchanged_full_stage'}
    if read_json(path) != expected:
        raise ValueError('Exact independent smoke review required')
    return prep.sha(Path(path).read_bytes())


def grant_value(repeat, condition, phase, account_id, plan_hash,
                authority_head, price_source_hash, prior_hash, smoke_review_hash,
                *, controller_hash=None, dispatcher_hash=None):
    return {
        'kind': KIND + '-stage-grant', 'approved': True,
        'authorized_by_user': True, 'reviewer': '/root',
        'stage': stage_name(repeat, condition, phase),
        'plan_sha256': plan_hash,
        'controller_sha256': controller_hash or prep.sha(Path(__file__).read_bytes()),
        'dispatcher_sha256': dispatcher_hash or prep.sha(DISPATCHER.read_bytes()),
        'account_id_sha256': prep.sha(account_id.encode('ascii')),
        'shared_authority_head_sha256': authority_head,
        'shared_authority_cap_usd': str(CAP),
        'price_source_sha256': price_source_hash,
        'published_input_usd_per_million': str(prep.INPUT_USD_PER_MILLION),
        'full_context_hold_usd': str(prep.reservation_usd(3 if phase == 'smoke' else 60)),
        'prior_completion_sha256': prior_hash,
        'smoke_review_sha256': smoke_review_hash,
        'transport': 'mcp__codex_apps__cloudflare_execute',
        'retry_policy': 'never_replay_unknown',
    }


def admit(repeat, condition, phase, grant_path, account_id, *,
          plan_path=PLAN, authority_path=AUTHORITY, base=BASE,
          smoke_review_path=None, fetcher=billing_fetch):
    if not isinstance(account_id, str) or not ACCOUNT_PATTERN.fullmatch(account_id):
        raise ValueError('Exact Cloudflare account ID required')
    plan, plan_hash = prep.checked_plan(plan_path)
    if not any(item['pass'] == repeat and item['condition'] == condition
               for item in plan['stages']):
        raise ValueError('Stage absent from Jev plan')
    name = stage_name(repeat, condition, phase)
    prior_hash = predecessor_hash(repeat, condition, base=base)
    review_hash = None
    raw_review = None
    if phase == 'development':
        if smoke_review_path is None:
            raise ValueError('Smoke review required')
        review_hash = checked_smoke_review(smoke_review_path, repeat, condition,
                                           base=base, plan_hash=plan_hash)
        raw_review = Path(smoke_review_path).read_bytes()
    raw_grant = Path(grant_path).read_bytes()
    grant = json.loads(raw_grant)
    price_hash = grant.get('price_source_sha256') if isinstance(grant, dict) else None
    if not isinstance(price_hash, str) or len(price_hash) != 64:
        raise ValueError('Reviewed price source hash required')
    checked_price_source(price_hash, fetcher)
    expected = grant_value(repeat, condition, phase, account_id, plan_hash,
                           grant.get('shared_authority_head_sha256'), price_hash,
                           prior_hash, review_hash)
    if grant != expected:
        raise ValueError('Exact reviewed Jev stage grant required')
    grant_hash = prep.sha(raw_grant)
    directory = stage_dir(repeat, condition, phase, base)
    if directory.exists():
        raise ValueError('Stage already claimed; no replay')
    with Path(authority_path).open('r+b') as ledger:
        fcntl.flock(ledger, fcntl.LOCK_EX | fcntl.LOCK_NB)
        seen, total = checked_authority(ledger, grant['shared_authority_head_sha256'])
        identity, amount = hold_id(repeat, condition, phase), prep.reservation_usd(
            3 if phase == 'smoke' else 60)
        if identity in seen or total + amount > CAP:
            raise ValueError('Duplicate Jev hold or shared Cloudflare cap exhausted')
        directory.mkdir(parents=True, exist_ok=False)
        with (directory / 'grant.json').open('xb') as saved_grant:
            saved_grant.write(raw_grant)
            saved_grant.flush()
            os.fsync(saved_grant.fileno())
        if raw_review is not None:
            with (directory / 'smoke-review.json').open('xb') as saved_review:
                saved_review.write(raw_review)
                saved_review.flush()
                os.fsync(saved_review.fileno())
        ledger.seek(0, os.SEEK_END)
        smoke.durable(ledger, {'event': 'hold', 'id': identity,
                              'usd': str(amount), 'grant_sha256': grant_hash})
        ledger.seek(0)
        after_hash = prep.sha(ledger.read())
        durable_file(directory / 'claim.json', {
            'kind': KIND + '-claim', 'stage': name, 'plan_sha256': plan_hash,
            'grant_sha256': grant_hash,
            'controller_sha256': prep.sha(Path(__file__).read_bytes()),
            'dispatcher_sha256': prep.sha(DISPATCHER.read_bytes()),
            'account_id_sha256': prep.sha(account_id.encode('ascii')),
            'authority_hold_id': identity, 'authority_head_sha256_after_hold': after_hash,
            'authority_hold_usd': str(amount),
            'prior_completion_sha256': prior_hash,
            'smoke_review_sha256': review_hash,
            'price_source_sha256': price_hash,
        })
    append(directory / 'budget.jsonl', {'event': 'budget', 'stage': name,
                                        'cap_usd': str(amount),
                                        'plan_sha256': plan_hash,
                                        'grant_sha256': grant_hash})
    for filename in ('journal.jsonl', 'raw.jsonl', 'records.jsonl'):
        with (directory / filename).open('xb'):
            pass
    (directory / 'app-bridge').mkdir()
    return {'stage': name, 'claim_sha256': prep.sha((directory / 'claim.json').read_bytes()),
            'authority_head_sha256_after_hold': after_hash, 'status': 'admitted_no_request'}


def directory_stage(directory, base=BASE):
    directory = Path(directory).resolve()
    parts = directory.relative_to(Path(base).resolve()).parts
    if len(parts) != 3:
        raise ValueError('Expected exact Jev stage directory')
    repeat, condition, phase = parts
    stage_name(repeat, condition, phase)
    return repeat, condition, phase


def checked_claim(directory, account_id=None, *, base=BASE, plan_path=PLAN,
                  authority_path=AUTHORITY):
    repeat, condition, phase = directory_stage(directory, base)
    directory = Path(directory)
    _, plan_hash = prep.checked_plan(plan_path)
    claim = read_json(directory / 'claim.json')
    grant_path = directory / 'grant.json'
    grant_hash = prep.sha(grant_path.read_bytes())
    if (claim.get('kind') != KIND + '-claim' or
            claim.get('stage') != stage_name(repeat, condition, phase) or
            claim.get('plan_sha256') != plan_hash or
            claim.get('grant_sha256') != grant_hash or
            claim.get('controller_sha256') != prep.sha(Path(__file__).read_bytes()) or
            claim.get('dispatcher_sha256') != prep.sha(DISPATCHER.read_bytes()) or
            claim.get('authority_hold_id') != hold_id(repeat, condition, phase) or
            claim.get('authority_hold_usd') != str(prep.reservation_usd(
                3 if phase == 'smoke' else 60))):
        raise ValueError('Jev stage claim differs from reviewed controls')
    if account_id is not None and claim.get('account_id_sha256') != prep.sha(account_id.encode('ascii')):
        raise ValueError('Cloudflare account differs from stage claim')
    grant = read_json(grant_path)
    if (grant.get('stage') != claim['stage'] or
            grant.get('account_id_sha256') != claim['account_id_sha256'] or
            grant.get('plan_sha256') != plan_hash or
            grant.get('controller_sha256') != claim['controller_sha256'] or
            grant.get('dispatcher_sha256') != claim['dispatcher_sha256']):
        raise ValueError('Stage grant differs from claim')
    if (claim.get('prior_completion_sha256') !=
            predecessor_hash(repeat, condition, base=base)):
        raise ValueError('Prior Jev repeat evidence changed')
    expected_review = (checked_smoke_review(
        directory / 'smoke-review.json', repeat, condition,
        base=base, plan_hash=plan_hash) if phase == 'development' else None)
    if claim.get('smoke_review_sha256') != expected_review:
        raise ValueError('Smoke review evidence changed')
    events = read_jsonl(authority_path)
    holds = [event for event in events[1:] if event.get('id') == claim['authority_hold_id']]
    if (len(holds) != 1 or holds[0] != {'event': 'hold',
            'id': claim['authority_hold_id'], 'usd': claim['authority_hold_usd'],
            'grant_sha256': grant_hash}):
        raise ValueError('Shared Jev hold absent or changed')
    return repeat, condition, phase, claim


@contextmanager
def operator_lock(directory):
    path = Path(directory) / '.operator.lock'
    with path.open('a+b') as handle:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def stage_rows(directory):
    budget = read_jsonl(directory / 'budget.jsonl')
    journal = read_jsonl(directory / 'journal.jsonl')
    raw = read_jsonl(directory / 'raw.jsonl')
    records = read_jsonl(directory / 'records.jsonl')
    if (not budget or budget[0].get('event') != 'budget' or
            len(budget) != len(records) + 1 or
            len(journal) != 3 * len(records) or len(raw) != len(records)):
        raise ValueError('Stage evidence has an unresolved attempt; no replay')
    for index, record in enumerate(records):
        events = journal[index * 3:index * 3 + 3]
        if ([event.get('event') for event in events] != ['reserved', 'started', 'finished'] or
                len({event.get('attempt_id') for event in events}) != 1 or
                event_id(events[0]) != event_id(record) or
                budget[index + 1].get('attempt_id') != record.get('attempt_id') or
                raw[index].get('attempt_id') != record.get('attempt_id')):
            raise ValueError('Stage attempt evidence differs')
    verify_saved_originals(directory, raw)
    return budget, journal, raw, records


def event_id(value):
    return value.get('id'), value.get('attempt_id')


def timing_value(attempt, start_ms, end_ms, duration_ms, clock, outcome):
    if (not isinstance(attempt, str) or not ATTEMPT_PATTERN.fullmatch(attempt) or
            any(type(value) is not int or value < 0 for value in
                (start_ms, end_ms, duration_ms)) or
            start_ms < 1_600_000_000_000 or end_ms < 1_600_000_000_000 or
            start_ms > 4_000_000_000_000 or end_ms > 4_000_000_000_000 or
            clock not in ('performance_now_monotonic', 'date_now_wall') or
            outcome not in ('outer_returned_original_saved',
                            'outer_returned_original_save_failed',
                            'outer_tool_exception')):
        raise ValueError('Invalid measured client timing')
    if clock == 'date_now_wall' and duration_ms != max(0, end_ms - start_ms):
        raise ValueError('Wall-clock duration differs from timestamps')
    def stamp(value):
        return datetime.fromtimestamp(value / 1000, timezone.utc).isoformat(
            timespec='milliseconds').replace('+00:00', 'Z')
    return {'kind': KIND + '-timing', 'attempt_id': attempt,
            'scope': 'client_mcp_round_trip',
            'includes': 'connected_app_tool_and_transport',
            'started_at_utc': stamp(start_ms), 'ended_at_utc': stamp(end_ms),
            'started_epoch_ms': start_ms, 'ended_epoch_ms': end_ms,
            'client_mcp_round_trip_ms': duration_ms, 'duration_clock': clock,
            'outcome': outcome,
            'provider_server_timing_status': 'unavailable',
            'provider_server_duration_ms': None}


def record_timing(request_path, start_ms, end_ms, duration_ms, clock, outcome,
                  *, base=BASE, plan_path=PLAN, authority_path=AUTHORITY):
    request_path = Path(request_path)
    directory = request_path.parent.parent
    with operator_lock(directory):
        _, _, _, claim = checked_claim(directory, base=base,
            plan_path=plan_path, authority_path=authority_path)
        ready = read_json(request_path)
        attempt = ready.get('attempt_id')
        if (not isinstance(attempt, str) or not ATTEMPT_PATTERN.fullmatch(attempt) or
                request_path.name != attempt + '.request.json' or
                ready.get('stage') != claim['stage'] or
                read_json(request_path.with_name(attempt + '.dispatch.json')) != {
                    'kind': KIND + '-dispatch-claim', 'attempt_id': attempt,
                    'request_sha256': ready.get('request_sha256'),
                    'account_id_sha256': claim['account_id_sha256']}):
            raise ValueError('Timing request lacks exact dispatch claim')
        value = timing_value(attempt, start_ms, end_ms, duration_ms, clock, outcome)
        path = request_path.with_name(attempt + '.timing.json')
        durable_file(path, value)
        return prep.sha(path.read_bytes())


def prepare(directory, account_id, *, base=BASE, plan_path=PLAN,
            authority_path=AUTHORITY):
    if not isinstance(account_id, str) or not ACCOUNT_PATTERN.fullmatch(account_id):
        raise ValueError('Exact Cloudflare account ID required')
    directory = Path(directory)
    with operator_lock(directory):
        repeat, condition, phase, claim = checked_claim(directory, account_id,
            base=base, plan_path=plan_path, authority_path=authority_path)
        if (directory / 'completion.json').exists():
            raise ValueError('Stage already terminal')
        _, journal, _, records = stage_rows(directory)
        ids = prep.SMOKE_IDS if phase == 'smoke' else prep.IDS
        index = len(records)
        if index >= len(ids) or (records and records[-1]['status'] in
                                ('service_error', 'unknown_outcome')) or (
                                    phase == 'smoke' and records and records[-1]['status'] != 'valid'):
            raise ValueError('Stage stopped or exhausted')
        bridge_dir = directory / 'app-bridge'
        if len(list(bridge_dir.glob('*.request.json'))) != index:
            raise ValueError('Unresolved prepared request; no replay')
        rows, policy = prep.inputs_and_policy()
        source = rows[index]
        body = prep.request_payload(source['feedback'], policy, condition)
        body_hash = prep.sha(prep.canonical(body))
        plan, _ = prep.checked_plan(plan_path)
        expected = plan['requests'][condition][index]
        if (source['id'] != ids[index] or expected != {
                'id': source['id'], 'input_sha256': prep.sha(source['feedback'].encode()),
                'rest_body_sha256': body_hash}):
            raise ValueError('Frozen Jev request differs')
        attempt_id = str(uuid.uuid4())
        amount = str(prep.reservation_usd(1))
        append(directory / 'budget.jsonl', {'event': 'reserve', 'id': source['id'],
            'attempt_id': attempt_id, 'usd': amount, 'request_sha256': body_hash})
        append(directory / 'journal.jsonl', {'event': 'reserved', 'id': source['id'],
            'attempt_id': attempt_id, 'usd': amount, 'request_sha256': body_hash})
        append(directory / 'journal.jsonl', {'event': 'started', 'id': source['id'],
            'attempt_id': attempt_id})
        ready = {'kind': KIND + '-request', 'stage': claim['stage'],
            'id': source['id'], 'attempt_id': attempt_id,
            'account_id_sha256': claim['account_id_sha256'],
            'plan_sha256': claim['plan_sha256'],
            'request_sha256': body_hash,
            'method': 'POST', 'path': '/accounts/{ACCOUNT_ID}/ai/run',
            'model': prep.ROUTE, 'body': body}
        durable_file(bridge_dir / f'{attempt_id}.request.json', ready)
        durable_file(bridge_dir / f'{attempt_id}.dispatch.json', {
            'kind': KIND + '-dispatch-claim', 'attempt_id': attempt_id,
            'request_sha256': body_hash, 'account_id_sha256': claim['account_id_sha256']})
        return ready


def mark_unknown(request_path, *, base=BASE, plan_path=PLAN,
                 authority_path=AUTHORITY):
    request_path = Path(request_path)
    directory = request_path.parent.parent
    with operator_lock(directory):
        checked_claim(directory, base=base, plan_path=plan_path,
                      authority_path=authority_path)
        ready = read_json(request_path)
        attempt = ready['attempt_id']
        timing = read_json(request_path.with_name(attempt + '.timing.json'))
        if (request_path.name != attempt + '.request.json' or
                not (request_path.parent / f'{attempt}.dispatch.json').exists() or
                timing.get('outcome') != 'outer_tool_exception' or
                any((request_path.parent / f'{attempt}{suffix}').exists() for suffix in
                    ('.tool-result.original.json', '.tool-call-error.json'))):
            raise ValueError('Unknown marker cannot replace a saved outcome')
        durable_file(request_path.parent / f'{attempt}.tool-call-error.json', {
            'kind': KIND + '-tool-call-error', 'attempt_id': attempt,
            'reason': 'outer_tool_exception_outcome_unknown'})


def consume(request_path, *, base=BASE, plan_path=PLAN, authority_path=AUTHORITY):
    request_path = Path(request_path)
    directory = request_path.parent.parent
    with operator_lock(directory):
        repeat, condition, phase, claim = checked_claim(directory,
            base=base, plan_path=plan_path, authority_path=authority_path)
        if (directory / 'completion.json').exists():
            raise ValueError('Stage already terminal')
        ready = read_json(request_path)
        attempt = ready.get('attempt_id')
        if (not isinstance(attempt, str) or not ATTEMPT_PATTERN.fullmatch(attempt) or
                request_path.name != attempt + '.request.json' or
                ready.get('kind') != KIND + '-request' or
                ready.get('stage') != claim['stage'] or
                ready.get('plan_sha256') != claim['plan_sha256'] or
                ready.get('account_id_sha256') != claim['account_id_sha256'] or
                ready.get('model') != prep.ROUTE or
                ready.get('path') != '/accounts/{ACCOUNT_ID}/ai/run' or
                ready.get('method') != 'POST' or
                ready.get('request_sha256') != prep.sha(prep.canonical(ready.get('body')))):
            raise ValueError('Prepared Jev request changed')
        dispatch = read_json(request_path.with_name(attempt + '.dispatch.json'))
        if dispatch != {'kind': KIND + '-dispatch-claim', 'attempt_id': attempt,
                        'request_sha256': ready['request_sha256'],
                        'account_id_sha256': claim['account_id_sha256']}:
            raise ValueError('Durable dispatch claim absent')
        budget = read_jsonl(directory / 'budget.jsonl')
        journal = read_jsonl(directory / 'journal.jsonl')
        records = read_jsonl(directory / 'records.jsonl')
        ids = prep.SMOKE_IDS if phase == 'smoke' else prep.IDS
        index = len(records)
        if (index >= len(ids) or ready.get('id') != ids[index] or
                len(budget) != index + 2 or len(journal) != 3 * index + 2 or
                budget[-1].get('attempt_id') != attempt or
                journal[-2].get('event') != 'reserved' or
                journal[-1].get('event') != 'started' or
                journal[-1].get('attempt_id') != attempt or
                journal[-1].get('id') != ready['id']):
            raise ValueError('Durable reservation differs')
        original_path = request_path.with_name(attempt + '.tool-result.original.json')
        error_path = request_path.with_name(attempt + '.tool-call-error.json')
        timing_path = request_path.with_name(attempt + '.timing.json')
        timing = read_json(timing_path)
        if timing != timing_value(attempt, timing.get('started_epoch_ms'),
                                  timing.get('ended_epoch_ms'),
                                  timing.get('client_mcp_round_trip_ms'),
                                  timing.get('duration_clock'), timing.get('outcome')):
            raise ValueError('Client/MCP timing evidence differs')
        if original_path.exists() == error_path.exists():
            raise ValueError('Exactly one original result or unknown marker required')
        if original_path.exists() and timing['outcome'] not in (
                'outer_returned_original_saved', 'outer_returned_original_save_failed'):
            raise ValueError('Original result and timing outcome differ')
        if error_path.exists() and timing['outcome'] != 'outer_tool_exception':
            raise ValueError('Unknown marker and timing outcome differ')
        if original_path.exists() and original_path.stat().st_size > MAX_RESULT_BYTES:
            raise ValueError('Saved original result too large; no replay')
        if error_path.exists() and read_json(error_path) != {
                'kind': KIND + '-tool-call-error', 'attempt_id': attempt,
                'reason': 'outer_tool_exception_outcome_unknown'}:
            raise ValueError('Unknown marker differs')
        original_hash = prep.sha(original_path.read_bytes()) if original_path.exists() else None
        status, reason, parsed, envelope, shape = 'unknown_outcome', 'outer_tool_error', None, None, None
        if original_path.exists():
            try:
                outer = read_json(original_path)
                blocks = outer.get('content') if isinstance(outer, dict) else None
                if (not isinstance(outer, dict) or outer.get('isError', False) is not False or
                        not isinstance(blocks, list) or len(blocks) != 1 or
                        not isinstance(blocks[0], dict) or blocks[0].get('type') != 'text' or
                        not isinstance(blocks[0].get('text'), str)):
                    raise ValueError('Ambiguous original tool result')
                envelope = json.loads(blocks[0]['text'])
                if (not isinstance(envelope, dict) or
                        not {'status', 'success', 'errors', 'messages', 'result'} <= set(envelope) or
                        type(envelope['status']) is not int or
                        not 100 <= envelope['status'] <= 599 or
                        type(envelope['success']) is not bool or
                        not isinstance(envelope['errors'], list) or
                        not isinstance(envelope['messages'], list)):
                    raise ValueError('Malformed Cloudflare envelope')
                shape = 'single_cloudflare_envelope'
                if envelope['status'] != 200 or envelope['success'] is not True or envelope['errors'] != []:
                    status, reason = 'service_error', f'provider_status_{envelope["status"]}'
                elif (not isinstance(envelope['result'], dict) or
                      envelope['result'].get('model') != prep.EXPECTED_RETURNED_VERSION):
                    status, reason = 'service_error', 'returned_version_drift'
                else:
                    try:
                        parsed = prep.parse_rest_response(envelope)
                        usage = parsed['usage']
                        tokens = usage.get('input_tokens') if isinstance(usage, dict) else None
                        if tokens is not None and tokens > prep.CONTEXT_TOKENS:
                            status, reason = 'service_error', 'usage_exceeds_published_context'
                            parsed = None
                        else:
                            status, reason = 'valid', None
                    except (ValueError, KeyError, TypeError):
                        status, reason = 'invalid_output', 'strict_native_choice_validation'
            except (ValueError, UnicodeError, KeyError, TypeError):
                status, reason, envelope, shape = 'unknown_outcome', 'unparseable_original_tool_result', None, None
        result_body = envelope.get('result') if isinstance(envelope, dict) else None
        observed_usage = result_body.get('usage') if isinstance(result_body, dict) else None
        usage = observed_usage if isinstance(observed_usage, dict) and all(
            type(observed_usage.get(key)) is int and observed_usage[key] >= 0
            for key in ('input_tokens', 'output_tokens') if key in observed_usage
        ) else None
        tokens = usage.get('input_tokens') if isinstance(usage, dict) else None
        estimate = (str(Decimal(tokens) * prep.INPUT_USD_PER_MILLION / Decimal(1_000_000))
                    if type(tokens) is int else None)
        append(directory / 'raw.jsonl', {'id': ready['id'], 'attempt_id': attempt,
            'request_sha256': ready['request_sha256'],
            'timing_file': timing_path.name,
            'timing_sha256': prep.sha(timing_path.read_bytes()),
            'started_at_utc': timing['started_at_utc'],
            'ended_at_utc': timing['ended_at_utc'],
            'client_mcp_round_trip_ms': timing['client_mcp_round_trip_ms'],
            'client_timing_scope': timing['scope'],
            'provider_server_timing_status': timing['provider_server_timing_status'],
            'provider_server_duration_ms': None,
            'original_tool_result_sha256': original_hash,
            'original_tool_result_file': original_path.name if original_hash else None,
            'http_status': envelope['status'] if envelope else None,
            'provider_envelope_sha256': prep.sha(prep.canonical(envelope)) if envelope else None,
            'shape': shape, 'reason': reason})
        append(directory / 'records.jsonl', {'id': ready['id'], 'attempt_id': attempt,
            'request_sha256': ready['request_sha256'], 'status': status, 'reason': reason,
            'parsed': parsed, 'usage': usage,
            'client_mcp_round_trip_ms': timing['client_mcp_round_trip_ms'],
            'provider_server_timing_status': 'unavailable',
            'provider_server_duration_ms': None,
            'published_input_cost_estimate_usd': estimate,
            'actual_charge_usd': None, 'charge_status': 'unknown_reserved',
            'reservation_usd': str(prep.reservation_usd(1)),
            'reference_labels_read': False})
        append(directory / 'journal.jsonl', {'event': 'finished', 'id': ready['id'],
            'attempt_id': attempt, 'status': status})
        current = read_jsonl(directory / 'records.jsonl')
        verify_saved_originals(directory, read_jsonl(directory / 'raw.jsonl'))
        stop = (status in ('service_error', 'unknown_outcome') or
                (phase == 'smoke' and status != 'valid'))
        if stop or len(current) == len(ids):
            counts = {key: sum(record['status'] == key for record in current)
                      for key in ('valid', 'invalid_output', 'service_error', 'unknown_outcome')}
            complete = len(current) == len(ids) and (phase == 'development' or counts['valid'] == 3)
            completion = {'kind': KIND + '-completion', 'stage': claim['stage'],
                'status': 'complete' if complete else 'stopped',
                'attempted': len(current), 'counts': counts,
                'never_sent': list(ids[len(current):]),
                'claim_sha256': prep.sha((directory / 'claim.json').read_bytes()),
                'budget_sha256': prep.sha((directory / 'budget.jsonl').read_bytes()),
                'journal_sha256': prep.sha((directory / 'journal.jsonl').read_bytes()),
                'raw_sha256': prep.sha((directory / 'raw.jsonl').read_bytes()),
                'records_sha256': prep.sha((directory / 'records.jsonl').read_bytes()),
                'stage_hold_usd': claim['authority_hold_usd'],
                'attempted_reservation_usd': str(prep.reservation_usd(len(current))),
                'charge_status': 'unknown_reserved'}
            durable_file(directory / 'completion.json', completion)
        return {'id': ready['id'], 'attempt_id': attempt, 'status': status,
                'stage_status': read_json(directory / 'completion.json')['status']
                                if (directory / 'completion.json').exists() else 'in_progress'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    check = sub.add_parser('verify')
    check.add_argument('--plan', type=Path, default=PLAN)
    run = sub.add_parser('admit')
    run.add_argument('--pass', dest='repeat', choices=prep.PASSES, required=True)
    run.add_argument('--condition', choices=prep.CONDITIONS, required=True)
    run.add_argument('--phase', choices=PHASES, required=True)
    run.add_argument('--grant', type=Path, required=True)
    run.add_argument('--account-id', required=True)
    run.add_argument('--smoke-review', type=Path)
    ready = sub.add_parser('prepare')
    ready.add_argument('directory', type=Path)
    ready.add_argument('--account-id', required=True)
    failed = sub.add_parser('mark-unknown')
    failed.add_argument('request', type=Path)
    measured = sub.add_parser('record-timing')
    measured.add_argument('request', type=Path)
    measured.add_argument('--start-ms', type=int, required=True)
    measured.add_argument('--end-ms', type=int, required=True)
    measured.add_argument('--duration-ms', type=int, required=True)
    measured.add_argument('--clock', required=True)
    measured.add_argument('--outcome', required=True)
    finish = sub.add_parser('consume')
    finish.add_argument('request', type=Path)
    args = parser.parse_args()
    if args.command == 'verify':
        print(prep.checked_plan(args.plan)[1])
    elif args.command == 'admit':
        print(json.dumps(admit(args.repeat, args.condition, args.phase, args.grant,
                               args.account_id, smoke_review_path=args.smoke_review)))
    elif args.command == 'prepare':
        print(json.dumps(prepare(args.directory, args.account_id), separators=(',', ':')))
    elif args.command == 'mark-unknown':
        mark_unknown(args.request)
        print('outcome_unknown_no_replay')
    elif args.command == 'record-timing':
        print(record_timing(args.request, args.start_ms, args.end_ms,
                            args.duration_ms, args.clock, args.outcome))
    else:
        print(json.dumps(consume(args.request), separators=(',', ':')))


if __name__ == '__main__':
    main()
