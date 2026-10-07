#!/usr/bin/env python3
"""Exact never-sent Luna DEV-002–003 native smoke; offline plan and gated runner."""

import argparse
import base64
from decimal import Decimal
import json
import os
from pathlib import Path
import time

from development_benchmark import ROOT, KEYS
from jev_benchmark import parse_response
from openrouter_paid_benchmark import durable
import clef_openrouter_native_v1 as frozen
import clef_openrouter_smoke_v1 as old
import openrouter_decision_smoke as native
import openrouter_authority_release_v4 as authority
import openrouter_budget_v4
import paid_budget_partitions_v4 as partitions

BASE = Path('results/clef-openrouter-v1/luna-smoke-v2')
PARENT = frozen.BASE / 'luna-decisions/fresh1/P0'
PLAN = BASE / 'plan.json'
STAGE = 'fresh1/P0'
KEY = 'luna-decisions'
DATED_MODEL = 'openai/gpt-6-luna-decisions-20261006'
IDS = ('DEV-002', 'DEV-003')
PARTITION_ID = 'clef-openrouter-v1-luna-decisions-fresh1-p0-smoke-dev002-003-v2'
BOUND = frozen.bound(KEY, 2)
PARENT_FILES = ('smoke.root-review.json', 'smoke-budget.json', 'smoke.claim.json',
                'smoke.journal.jsonl', 'smoke.raw.jsonl', 'smoke.attempts.jsonl',
                'smoke.parsed.jsonl', 'smoke.reconciliation.json',
                'smoke-budget-clef-openrouter-v1-luna-decisions-fresh1-p0-smoke.jsonl')
SOURCES = (Path('scripts/clef_openrouter_luna_smoke_v2.py'),
           Path('tests/test_clef_openrouter_luna_smoke_v2.py'),
           *frozen.SOURCES, *(frozen.catalog_path(key) for key in frozen.MODELS))


def sha_path(path):
    return native.sha(Path(path).read_bytes())


def lines(path):
    return [json.loads(row) for row in Path(path).read_text().splitlines() if row.strip()]


def validate_dated(body):
    if not isinstance(body, dict) or body.get('provider') != 'OpenAI':
        raise ValueError('Returned Luna provider differs')
    prediction = parse_response(body, DATED_MODEL)
    usage = body.get('usage')
    if (not isinstance(usage, dict) or type(usage.get('input_tokens')) is not int or
            not 0 <= usage['input_tokens'] <= len(KEYS) * frozen.MODELS[KEY]['context'] or
            type(usage.get('output_tokens')) is not int or usage['output_tokens'] < 0):
        raise ValueError('Dated Luna usage invalid')
    return prediction


def parent_evidence(root, original_plan):
    folder = Path(root) / PARENT
    hashes = {str(PARENT / name): sha_path(folder / name) for name in PARENT_FILES}
    review = json.loads((folder / 'smoke.root-review.json').read_text())
    claim = json.loads((folder / 'smoke.claim.json').read_text())
    budget = json.loads((folder / 'smoke-budget.json').read_text())
    reconcile = json.loads((folder / 'smoke.reconciliation.json').read_text())
    raw, attempts, parsed = lines(folder / 'smoke.raw.jsonl'), lines(folder / 'smoke.attempts.jsonl'), lines(folder / 'smoke.parsed.jsonl')
    journal = lines(folder / 'smoke.journal.jsonl')
    child = lines(folder / PARENT_FILES[-1])
    item = original_plan['models'][KEY]['requests']['P0'][0]
    if (len(raw) != 1 or len(attempts) != 1 or parsed or
            raw[0]['id'] != 'DEV-001' or attempts[0]['id'] != 'DEV-001' or
            raw[0]['attempt_id'] != attempts[0]['attempt_id'] or
            raw[0]['payload_sha256'] != item['payload_sha256'] or raw[0]['http_status'] != 200 or
            attempts[0]['status'] != 'invalid_native_response' or
            [row['event'] for row in journal] != ['stage_started', 'request_intent', 'request_started', 'stage_stopped'] or
            any(row.get('id') != 'DEV-001' for row in journal[1:] if 'id' in row) or
            claim.get('plan_sha256') != old.plan_v1.verify(root)[1] or
            review.get('plan_sha256') != claim['plan_sha256'] or
            claim.get('root_review_sha256') != hashes[str(PARENT / 'smoke.root-review.json')] or
            claim.get('budget_manifest_sha256') != hashes[str(PARENT / 'smoke-budget.json')]):
        raise ValueError('Parent Luna DEV-001 attempt or gate differs')
    wire = base64.b64decode(raw[0]['response_base64'], validate=True)
    if native.sha(wire) != raw[0]['response_sha256']:
        raise ValueError('Parent Luna response hash differs')
    body = json.loads(wire)
    prediction = validate_dated(body)
    actual = native.response_cost(body)
    if actual != Decimal(attempts[0]['actual_cost_usd']):
        raise ValueError('Parent Luna known charge differs')
    if (budget.get('partitions', [{}])[0].get('id') != old.partition_id(KEY, STAGE) or
            reconcile.get('partition_id') != old.partition_id(KEY, STAGE) or
            reconcile.get('child_sha256') != hashes[str(PARENT / PARENT_FILES[-1])] or
            Decimal(reconcile.get('known_actual_usd')) != actual or
            Decimal(reconcile.get('unknown_upper_bound_usd')) != 0 or
            [row['event'] for row in child] != ['budget', 'reserve', 'settle', 'partition_closed'] or
            child[1].get('attempt_id') != attempts[0]['attempt_id'] or
            child[1].get('record_id') != 'DEV-001' or
            child[2].get('attempt_id') != attempts[0]['attempt_id'] or
            Decimal(child[2].get('usd')) != actual):
        raise ValueError('Parent Luna partition not sealed at exact known charge')
    return {'file_sha256': hashes, 'original_status': 'invalid_native_response',
            'dated_model_parse': 'valid_native_choice', 'dated_model': DATED_MODEL,
            'dev001_response_sha256': raw[0]['response_sha256'],
            'dev001_prediction': prediction, 'known_cost_usd': str(actual),
            'parent_partition_id': old.partition_id(KEY, STAGE)}


def build(root=ROOT):
    root = Path(root)
    original, original_sha = frozen.verify(root)
    parent = parent_evidence(root, original)
    source = {str(path): sha_path(root / path) for path in SOURCES}
    items = original['models'][KEY]['requests']['P0'][1:3]
    if tuple(item['id'] for item in items) != IDS:
        raise ValueError('Only original never-sent DEV-002–003 are eligible')
    return {'schema': 'clef-openrouter-luna-exact-unsent-smoke-v2',
            'status': 'offline_not_admitted', 'inference_performed': False,
            'allocation_performed': False, 'reference_labels_sent': False,
            'original_plan_sha256': original_sha, 'source_sha256': source,
            'parent': parent, 'model': frozen.MODELS[KEY]['model'],
            'expected_returned_model': DATED_MODEL, 'provider': 'OpenAI',
            'endpoint': original['models'][KEY]['endpoint'],
            'stage': STAGE, 'request_ids': list(IDS), 'requests': items,
            'partition_id': PARTITION_ID, 'child_cap_usd': str(BOUND),
            'per_request_reserve_usd': str(frozen.bound(KEY, 1)),
            'gate': 'Separate v4 hold and child, root raw inspection after exactly two never-sent requests; no automatic replay or development admission.'}


def verify(root=ROOT):
    expected = build(root)
    if json.loads((Path(root) / PLAN).read_text()) != expected:
        raise ValueError('Luna v2 plan differs from bound sources or parent evidence')
    return expected, native.sha(native.canonical(expected))


def hold_source(plan_sha, budget_path):
    return native.sha(native.canonical({'kind': 'clef-openrouter-luna-smoke-v2-hold',
        'plan_sha256': plan_sha, 'budget_manifest_sha256': sha_path(budget_path),
        'partition_id': PARTITION_ID, 'two_request_bound_usd': str(BOUND)}))


def verify_review(root, plan_sha, budget_path, review_path):
    root = Path(root)
    if Path(review_path).resolve() != (root / BASE / 'root-review.json').resolve():
        raise ValueError('Wrong Luna v2 root-review path')
    review = json.loads(Path(review_path).read_text())
    expected = {'kind': 'clef-openrouter-luna-smoke-v2-root-review', 'approved': True,
                'plan_sha256': plan_sha, 'runner_sha256': sha_path(root / SOURCES[0]),
                'budget_manifest_sha256': sha_path(budget_path), 'partition_id': PARTITION_ID,
                'authority_hold_source_sha256': hold_source(plan_sha, budget_path),
                'request_ids': list(IDS), 'two_request_bound_usd': str(BOUND)}
    if any(review.get(key) != value for key, value in expected.items()) or not review.get('reviewer'):
        raise ValueError('Luna v2 root review missing or differs')
    return review


def verify_hold(plan_sha, budget_path, authority_path=old.AUTHORITY, master=old.MASTER):
    with authority.old._locked(authority_path) as handle:
        _, holds, released = authority._scan(handle.read())
        hold = holds.get(PARTITION_ID)
        if (not hold or PARTITION_ID in released or hold.get('version') != 3 or
                hold.get('funding_pool') != 'openrouter_additional' or hold.get('usd') != str(BOUND) or
                hold.get('source_sha256') != hold_source(plan_sha, budget_path) or
                hold.get('budget_manifest_sha256') != sha_path(budget_path) or
                hold.get('budget_manifest_path') != str(Path(budget_path).resolve()) or
                hold.get('master_path') != str(Path(master).resolve()) or
                hold.get('partition_id') != PARTITION_ID):
            raise ValueError('Exact active Luna v2 authority hold missing')


def run(review_path, budget_path, *, root=ROOT, master=old.MASTER,
        authority_path=old.AUTHORITY, fetch=old.fetch_endpoint, send=old.post,
        open_child=partitions.open_partition):
    root, budget_path = Path(root), Path(budget_path)
    plan, plan_sha = verify(root)
    verify_review(root, plan_sha, budget_path, review_path)
    verify_hold(plan_sha, budget_path, authority_path, master)
    folder = root / BASE
    files = {name: folder / ('smoke.' + name) for name in
             ('claim.json', 'journal.jsonl', 'raw.jsonl', 'attempts.jsonl', 'parsed.jsonl')}
    if any(path.exists() for path in files.values()):
        raise FileExistsError('Luna v2 smoke already claimed; no replay')
    _, route = fetch(KEY)
    old.verify_live_endpoint(KEY, route, plan['endpoint'])
    ledger = open_child(master, budget_path, PARTITION_ID, plan['model'], plan['provider'], old.REASONING)
    try:
        _, pending, blocked = ledger.state()
        if (ledger.master_cap != openrouter_budget_v4.CAP or pending or blocked or ledger.closed or
                ledger.accounted() + BOUND > ledger.cap):
            raise ValueError('Luna v2 child not ready for exact two-request bound')
        token = os.environ.get('OPENROUTER_API_KEY')
        if not token:
            raise ValueError('OPENROUTER_API_KEY required')
        folder.mkdir(parents=True, exist_ok=True)
        with files['claim.json'].open('x') as out:
            durable(out, {'kind': 'clef-openrouter-luna-smoke-v2-claim',
                'plan_sha256': plan_sha, 'root_review_sha256': sha_path(review_path),
                'budget_manifest_sha256': sha_path(budget_path),
                'request_ids': list(IDS), 'reference_labels_sent': False, 'claimed_utc': old.now()})
        with files['journal.jsonl'].open('x') as journal, files['raw.jsonl'].open('x') as raw, \
                files['attempts.jsonl'].open('x') as attempts, files['parsed.jsonl'].open('x') as parsed:
            durable(journal, {'event': 'stage_started', 'utc': old.now(), 'plan_sha256': plan_sha})
            for item in plan['requests']:
                rid = item['id']
                try:
                    verify(root)
                    verify_hold(plan_sha, budget_path, authority_path, master)
                    route_raw, route = fetch(KEY)
                    old.verify_live_endpoint(KEY, route, plan['endpoint'])
                    if native.sha(native.canonical(item['payload'])) != item['payload_sha256']:
                        raise ValueError('Luna v2 request payload drift')
                    if ledger.accounted() + frozen.bound(KEY, 1) > ledger.cap:
                        raise ValueError('Luna v2 child lacks next reserve')
                    durable(journal, {'event': 'request_intent', 'id': rid,
                        'payload_sha256': item['payload_sha256'], 'utc': old.now()})
                    attempt = ledger.reserve(frozen.bound(KEY, 1), rid)
                    durable(journal, {'event': 'request_started', 'id': rid,
                        'attempt_id': attempt, 'live_endpoint_sha256': native.sha(route_raw), 'utc': old.now()})
                    started, t0 = old.now(), time.perf_counter_ns()
                    try:
                        status, wire = send(item['payload'], token)
                    except BaseException as error:
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'transport_error',
                            'error_type': type(error).__name__, 'cost_unknown': True,
                            'reserved_cost_usd': str(frozen.bound(KEY, 1)),
                            'request_started_utc': started, 'request_ended_utc': old.now(),
                            'client_request_elapsed_ns': time.perf_counter_ns() - t0})
                        raise
                    ended, elapsed = old.now(), time.perf_counter_ns() - t0
                    durable(raw, {'id': rid, 'attempt_id': attempt,
                        'payload_sha256': item['payload_sha256'], 'http_status': status,
                        'response_sha256': native.sha(wire),
                        'response_base64': base64.b64encode(wire).decode('ascii'),
                        'request_started_utc': started, 'request_ended_utc': ended,
                        'client_request_elapsed_ns': elapsed})
                    try:
                        body = json.loads(wire)
                    except (ValueError, UnicodeDecodeError):
                        body = None
                    actual = native.response_cost(body)
                    if actual is None:
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'unknown_cost',
                            'http_status': status, 'cost_unknown': True,
                            'reserved_cost_usd': str(frozen.bound(KEY, 1))})
                        raise ValueError('Luna v2 cost unknown; reservation retained')
                    if not ledger.settle(attempt, actual):
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'over_bound',
                            'http_status': status, 'actual_cost_usd': str(actual)})
                        raise ValueError('Luna v2 observed cost exceeded reserve')
                    if status != 200:
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'http_error',
                            'http_status': status, 'actual_cost_usd': str(actual)})
                        raise ValueError('Luna v2 provider HTTP error; no retry')
                    try:
                        prediction = validate_dated(body)
                    except ValueError:
                        durable(attempts, {'id': rid, 'attempt_id': attempt,
                            'status': 'invalid_native_response', 'actual_cost_usd': str(actual)})
                        raise
                    durable(parsed, {'id': rid, 'attempt_id': attempt, 'prediction': prediction,
                        'input_tokens': body['usage']['input_tokens'],
                        'output_tokens': body['usage']['output_tokens'],
                        'actual_cost_usd': str(actual)})
                    durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'ok',
                        'actual_cost_usd': str(actual), 'cost_unknown': False})
                except BaseException as error:
                    durable(journal, {'event': 'stage_stopped', 'id': rid,
                        'error_type': type(error).__name__, 'utc': old.now()})
                    raise
            durable(journal, {'event': 'stage_completed', 'utc': old.now(), 'count': 2})
    finally:
        ledger.close()


def composite_inspection(root=ROOT):
    """Return a hashable, read-only three-response projection; never an approval."""
    plan, plan_sha = verify(root)
    folder = Path(root) / BASE
    raw, attempts, parsed = (lines(folder / ('smoke.' + name)) for name in
                             ('raw.jsonl', 'attempts.jsonl', 'parsed.jsonl'))
    claim = json.loads((folder / 'smoke.claim.json').read_text())
    review = json.loads((folder / 'root-review.json').read_text())
    budget = json.loads((folder / 'budget.json').read_text())
    entries = budget.get('partitions', [])
    if (len(entries) != 1 or entries[0].get('id') != PARTITION_ID or
            Decimal(entries[0]['cap_usd']) != BOUND or
            claim.get('plan_sha256') != plan_sha or
            claim.get('root_review_sha256') != sha_path(folder / 'root-review.json') or
            claim.get('budget_manifest_sha256') != sha_path(folder / 'budget.json') or
            review.get('approved') is not True):
        raise ValueError('Suffix claim, root review, or child manifest differs')
    child = Path(entries[0]['child_ledger'])
    ledger = lines(child)
    journal = lines(folder / 'smoke.journal.jsonl')
    ledger_events = [row['event'] for row in ledger]
    settled_events = ['budget', 'reserve', 'settle', 'reserve', 'settle']
    sealed = ledger_events == settled_events + ['partition_closed']
    if ([row['event'] for row in journal] != ['stage_started', 'request_intent', 'request_started',
                                             'request_intent', 'request_started', 'stage_completed'] or
            not (ledger_events == settled_events or sealed) or
            [row['record_id'] for row in ledger if row['event'] == 'reserve'] != list(IDS) or
            any(Decimal(row['usd']) != frozen.bound(KEY, 1) for row in ledger if row['event'] == 'reserve')):
        raise ValueError('Suffix journal or ledger is not exactly two settled requests')
    reconciliation_path = folder / 'smoke.reconciliation.json'
    if sealed:
        if not reconciliation_path.is_file():
            raise ValueError('Sealed suffix child needs immutable reconciliation receipt')
        reconciliation = json.loads(reconciliation_path.read_text())
        if (reconciliation.get('event') != 'partition_reconciled' or
                reconciliation.get('partition_id') != PARTITION_ID or
                reconciliation.get('child_ledger') != str(child) or
                reconciliation.get('child_sha256') != sha_path(child) or
                Decimal(reconciliation.get('unknown_upper_bound_usd')) != 0 or
                Decimal(reconciliation.get('known_actual_usd')) !=
                sum((Decimal(row['usd']) for row in ledger if row['event'] == 'settle'), Decimal(0)) or
                Decimal(reconciliation.get('unused_allocation_released_usd')) !=
                BOUND - Decimal(reconciliation['known_actual_usd'])):
            raise ValueError('Sealed suffix reconciliation differs from exact child')
    elif reconciliation_path.exists():
        raise ValueError('Reconciliation receipt exists before suffix child sealing')
    if ([row['id'] for row in raw] != list(IDS) or
            [row['id'] for row in attempts] != list(IDS) or
            [row['id'] for row in parsed] != list(IDS) or
            any(row['status'] != 'ok' for row in attempts)):
        raise ValueError('Two exact successful suffix responses required')
    rows = [{'id': 'DEV-001', 'source': 'parent_original_failed',
             'original_status': plan['parent']['original_status'],
             'offline_dated_parse': plan['parent']['dated_model_parse'],
             'response_sha256': plan['parent']['dev001_response_sha256'],
             'prediction': plan['parent']['dev001_prediction']}]
    for expected, wire_row, attempt, parsed_row in zip(plan['requests'], raw, attempts, parsed):
        wire = base64.b64decode(wire_row['response_base64'], validate=True)
        body = json.loads(wire)
        if (wire_row['payload_sha256'] != expected['payload_sha256'] or
                native.sha(wire) != wire_row['response_sha256'] or
                wire_row['attempt_id'] != attempt['attempt_id'] or
                attempt['attempt_id'] != parsed_row['attempt_id'] or
                wire_row['http_status'] != 200 or
                validate_dated(body) != parsed_row['prediction'] or
                native.response_cost(body) != Decimal(attempt['actual_cost_usd']) or
                attempt['actual_cost_usd'] != parsed_row['actual_cost_usd']):
            raise ValueError('Suffix response, parser, or charge differs')
        settlements = [row for row in ledger if row['event'] == 'settle' and
                       row['attempt_id'] == attempt['attempt_id']]
        if len(settlements) != 1 or Decimal(settlements[0]['usd']) != Decimal(attempt['actual_cost_usd']):
            raise ValueError('Suffix known charge not settled exactly once')
        rows.append({'id': expected['id'], 'source': 'v2_suffix', 'status': 'ok',
                     'response_sha256': wire_row['response_sha256'],
                     'prediction': parsed_row['prediction']})
    projection = {'schema': 'clef-openrouter-luna-smoke-v2-composite-inspection',
                  'plan_sha256': plan_sha, 'original_dev001_status_preserved': 'invalid_native_response',
                  'dated_model': DATED_MODEL, 'rows': rows,
                  'suffix_raw_sha256': sha_path(folder / 'smoke.raw.jsonl'),
                  'suffix_attempts_sha256': sha_path(folder / 'smoke.attempts.jsonl'),
                  'suffix_parsed_sha256': sha_path(folder / 'smoke.parsed.jsonl')}
    projection['suffix_child_sha256'] = sha_path(child)
    projection['suffix_child_state'] = 'sealed_reconciled' if sealed else 'completed_open'
    if sealed:
        projection['suffix_reconciliation_sha256'] = sha_path(reconciliation_path)
    projection['suffix_claim_sha256'] = sha_path(folder / 'smoke.claim.json')
    projection['suffix_journal_sha256'] = sha_path(folder / 'smoke.journal.jsonl')
    return projection, native.sha(native.canonical(projection))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('write-plan', 'verify', 'run', 'inspect'))
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--review', type=Path)
    parser.add_argument('--budget', type=Path)
    args = parser.parse_args()
    if args.action == 'write-plan':
        value = build(args.root)
        path = args.root / PLAN
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x') as out:
            out.write(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
        print(native.sha(native.canonical(value)))
    elif args.action == 'verify':
        print(verify(args.root)[1])
    elif args.action == 'inspect':
        print(json.dumps(composite_inspection(args.root)[0], indent=2))
    else:
        if not args.review or not args.budget:
            parser.error('run requires --review and --budget')
        run(args.review, args.budget, root=args.root)


if __name__ == '__main__':
    main()
