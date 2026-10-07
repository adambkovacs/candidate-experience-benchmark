#!/usr/bin/env python3
"""Exact never-sent Flash DEV040–060 continuation after retained DEV039 risk.

Offline plan creation does not finalize the parent's unknown charge, allocate,
hold funds or send inference. A separately reviewed run needs a reconciled
parent, fresh child, active authority hold and root receipt.
"""

import argparse
import base64
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import time

from development_benchmark import ROOT
from openrouter_paid_benchmark import durable
import openrouter_budget_v4
import paid_budget_partitions_v4 as partitions
import openrouter_authority_release_v4 as authority
import clef_openrouter_native_v1 as route
import clef_openrouter_full_v1 as full
import clef_openrouter_smoke_v1 as smoke
import openrouter_decision_smoke as native


KEY = 'clef-flash'
STAGE = 'fresh3/P2'
IDS = tuple(f'DEV-{i:03}' for i in range(40, 61))
BASE = route.BASE / 'flash-p2-exact21-v1'
PLAN = BASE / 'plan.json'
PROOF = BASE / 'parent-public-proof.json'
REVIEW = BASE / 'root-review.json'
PARTITION_ID = 'clef-openrouter-v1-clef-flash-fresh3-p2-dev040-060-exact-v1'
REASONING = 'native-decisions-exact-unsent'
PARENT_NAMES = ('development.claim.json', 'development.journal.jsonl',
                'development.raw.jsonl', 'development.attempts.jsonl',
                'development.parsed.jsonl', 'smoke.root-inspection.json')
UNKNOWN_ID = 'DEV-039'
COOLDOWN_SECONDS = 120


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def sha_path(path):
    return native.sha(Path(path).read_bytes())


def rows(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]


def parent_paths(root):
    parent = full.stage_dir(root, KEY, STAGE)
    budget_path = Path(root) / full.BASE / KEY / 'full-budget.json'
    budget = json.loads(budget_path.read_text())
    entries = budget.get('partitions')
    if not isinstance(entries, list) or len(entries) != 1 or entries[0].get('id') != full.partition_id(KEY):
        raise ValueError('Flash parent budget identity differs')
    return parent, budget_path, Path(entries[0]['child_ledger']), entries[0]


def parent_pending(root, original):
    parent, budget_path, child_path, entry = parent_paths(root)
    source = {str(parent.relative_to(root) / name): sha_path(parent / name) for name in PARENT_NAMES}
    source[str(budget_path.relative_to(root))] = sha_path(budget_path)
    raw, attempts, parsed, journal = (rows(parent / name) for name in
                                      ('development.raw.jsonl', 'development.attempts.jsonl',
                                       'development.parsed.jsonl', 'development.journal.jsonl'))
    if ([x.get('id') for x in raw] != list(route.IDS[:39]) or
            [x.get('id') for x in attempts] != list(route.IDS[:39]) or
            [x.get('id') for x in parsed] != list(route.IDS[:38]) or
            any(x.get('status') != 'ok' for x in attempts[:38]) or
            attempts[-1].get('status') != 'unknown_cost' or
            attempts[-1].get('cost_unknown') is not True or
            attempts[-1].get('reserved_cost_usd') != str(route.bound(KEY, 1)) or
            raw[-1].get('http_status') != 429 or
            raw[-1].get('attempt_id') != attempts[-1].get('attempt_id') or
            journal[-1].get('event') != 'stage_stopped' or journal[-1].get('id') != UNKNOWN_ID or
            json.loads((parent / 'development.claim.json').read_text()).get('full_plan_sha256') != full.verify(root)[1]):
        raise ValueError('Exact parent stopped attempt or never-sent suffix differs')
    wire = base64.b64decode(raw[-1]['response_base64'], validate=True)
    if native.sha(wire) != raw[-1]['response_sha256'] or b'rate limiting: inference request per min rate reached' not in wire:
        raise ValueError('Exact provider rate-limit original response differs')
    child = rows(child_path)
    reserves = [x for x in child if x.get('event') == 'reserve']
    settles = [x for x in child if x.get('event') == 'settle']
    attempt = attempts[-1]['attempt_id']
    unsettled = [x for x in reserves if x['attempt_id'] not in {y['attempt_id'] for y in settles}]
    known = sum((Decimal(x['usd']) for x in settles), Decimal(0))
    risk = route.bound(KEY, 1)
    cap = Decimal(entry['cap_usd'])
    suffix = child[child.index(unsettled[0]) + 1:]
    if (len(unsettled) != 1 or unsettled[0]['attempt_id'] != attempt or
            unsettled[0]['record_id'] != f'{STAGE}:development:{UNKNOWN_ID}' or
            Decimal(unsettled[0]['usd']) != risk or known + risk > cap or
            (suffix and (len(suffix) != 2 or
                         suffix[0].get('event') != 'unknown_cost_accounted_as_upper_bound' or
                         suffix[0].get('attempt_id') != attempt or
                         Decimal(suffix[0].get('usd')) != risk or
                         suffix[1].get('event') != 'partition_closed'))):
        raise ValueError('Flash child pending charge differs')
    next_items = original['models'][KEY]['requests']['P2'][39:]
    if tuple(x['id'] for x in next_items) != IDS:
        raise ValueError('Only DEV040–060 never-sent suffix is eligible')
    return {'source_sha256': source, 'child_path': str(child_path.resolve()),
            'child_prefix_sha256': native.sha(b''.join(child_path.read_bytes().splitlines(keepends=True)[:len(child)-len(suffix)])),
            'child_prefix_events': len(child)-len(suffix),
            'parent_budget_manifest_sha256': sha_path(budget_path),
            'unknown_attempt_id': attempt, 'unknown_response_sha256': raw[-1]['response_sha256'],
            'unknown_request_ended_utc': raw[-1]['request_ended_utc'],
            'known_actual_usd': str(known), 'unknown_upper_bound_usd': str(risk),
            'child_cap_usd': str(cap), 'unused_after_finalization_usd': str(cap - known - risk),
            'parent_partition_id': full.partition_id(KEY),
            'exact_requests': next_items}


def make_public_proof(root=ROOT):
    root = Path(root)
    original, _ = route.verify(root)
    parent = parent_pending(root, original)
    _, _, child, _ = parent_paths(root)
    receipt = root / full.BASE / KEY / 'full-reconciliation.json'
    closed = json.loads(receipt.read_text())
    if (closed.get('kind') != 'clef-openrouter-flash-full-v1-interrupted-reconciliation' or
            closed.get('unknown_id') != UNKNOWN_ID or
            closed.get('event', {}).get('child_sha256') != sha_path(child) or
            closed.get('event', {}).get('known_actual_usd') != parent['known_actual_usd'] or
            closed.get('event', {}).get('unknown_upper_bound_usd') != parent['unknown_upper_bound_usd'] or
            closed.get('event', {}).get('unused_allocation_released_usd') != parent['unused_after_finalization_usd']):
        raise ValueError('Public Flash reconciliation differs')
    return {'schema': 'clef-openrouter-flash-p2-parent-proof-v1',
            'parent_snapshot': {k: v for k, v in parent.items() if k != 'exact_requests'},
            'parent_source_sha256': parent['source_sha256'],
            'child_relative_path': str(child.relative_to(root)),
            'child_prefix_sha256': parent['child_prefix_sha256'],
            'child_prefix_events': parent['child_prefix_events'],
            'child_closed_sha256': sha_path(child),
            'reconciliation_relative_path': str(receipt.relative_to(root)),
            'reconciliation_sha256': sha_path(receipt),
            'known_actual_usd': parent['known_actual_usd'],
            'unknown_upper_bound_usd': parent['unknown_upper_bound_usd'],
            'unused_after_finalization_usd': parent['unused_after_finalization_usd'],
            'unknown_attempt_id': parent['unknown_attempt_id'],
            'unknown_response_sha256': parent['unknown_response_sha256'],
            'original_attempt_status': 'unknown_cost',
            'never_sent_ids': list(IDS)}


def verify_public_proof(root, plan):
    root = Path(root)
    proof_path = root / PROOF
    if sha_path(proof_path) != plan.get('parent_public_proof_sha256'):
        raise ValueError('Public Flash parent proof changed')
    proof = json.loads(proof_path.read_text())
    parent = plan['parent']
    if proof.get('parent_snapshot') != {k: v for k, v in parent.items() if k != 'exact_requests'}:
        raise ValueError('Public Flash parent snapshot differs')
    expected = {'schema': 'clef-openrouter-flash-p2-parent-proof-v1',
                'parent_source_sha256': parent['source_sha256'],
                'child_prefix_sha256': parent['child_prefix_sha256'],
                'child_prefix_events': parent['child_prefix_events'],
                'known_actual_usd': parent['known_actual_usd'],
                'unknown_upper_bound_usd': parent['unknown_upper_bound_usd'],
                'unused_after_finalization_usd': parent['unused_after_finalization_usd'],
                'unknown_attempt_id': parent['unknown_attempt_id'],
                'unknown_response_sha256': parent['unknown_response_sha256'],
                'original_attempt_status': 'unknown_cost',
                'never_sent_ids': list(IDS)}
    if any(proof.get(k) != v for k, v in expected.items()):
        raise ValueError('Public Flash parent proof facts differ')
    child_rel, receipt_rel = (Path(proof.get(k, '')) for k in
                              ('child_relative_path', 'reconciliation_relative_path'))
    if (child_rel.is_absolute() or receipt_rel.is_absolute() or
            '..' in child_rel.parts or '..' in receipt_rel.parts):
        raise ValueError('Public Flash proof path is not relative')
    child_path, receipt_path = root / child_rel, root / receipt_rel
    budget_rel = full.BASE / KEY / 'full-budget.json'
    if sha_path(root / budget_rel) != parent['parent_budget_manifest_sha256']:
        raise ValueError('Public Flash parent budget manifest differs')
    if (sha_path(child_path) != proof.get('child_closed_sha256') or
            sha_path(receipt_path) != proof.get('reconciliation_sha256')):
        raise ValueError('Public Flash sealed child or receipt differs')
    receipt = json.loads(receipt_path.read_text())
    event = receipt.get('event', {})
    if (event.get('child_sha256') != proof['child_closed_sha256'] or
            event.get('known_actual_usd') != parent['known_actual_usd'] or
            event.get('unknown_upper_bound_usd') != parent['unknown_upper_bound_usd'] or
            event.get('unused_allocation_released_usd') != parent['unused_after_finalization_usd']):
        raise ValueError('Public Flash closure amounts differ')
    child = rows(child_path)
    n = parent['child_prefix_events']
    prefix = b''.join(child_path.read_bytes().splitlines(keepends=True)[:n])
    if (native.sha(prefix) != parent['child_prefix_sha256'] or len(child) != n + 2 or
            child[-2].get('event') != 'unknown_cost_accounted_as_upper_bound' or
            child[-2].get('attempt_id') != parent['unknown_attempt_id'] or
            Decimal(child[-2].get('usd')) != Decimal(parent['unknown_upper_bound_usd']) or
            child[-1].get('event') != 'partition_closed'):
        raise ValueError('Public Flash closure event tail differs')
    return proof


def build(root=ROOT):
    root = Path(root)
    original, route_sha = route.verify(root)
    _, full_sha = full.verify(root)
    parent = parent_pending(root, original)
    return {'schema': 'clef-openrouter-flash-p2-exact21-v1',
            'status': 'offline_unadmitted_parent_risk_retained',
            'inference_performed': False, 'allocation_performed': False,
            'reference_labels_sent': False, 'model': route.MODELS[KEY]['model'],
            'provider': route.MODELS[KEY]['provider'], 'stage': STAGE,
            'request_ids': list(IDS), 'route_plan_sha256': route_sha,
            'full_plan_sha256': full_sha,
            'controller_sha256': sha_path(root / 'scripts/clef_openrouter_flash_p2_exact21_v1.py'),
            'parent_public_proof_sha256': sha_path(root / PROOF),
            'parent': parent, 'partition_id': PARTITION_ID,
            'per_request_reserve_usd': str(route.bound(KEY, 1)),
            'twenty_one_request_upper_bound_usd': str(route.bound(KEY, 21)),
            'cooldown_seconds_after_429': COOLDOWN_SECONDS,
            'gate': 'Finalize DEV039 once at full unknown upper bound, seal and reconcile parent; review fresh child and active hold; never replay DEV001–039.'}


def verify(root=ROOT, *, require_private=False):
    root = Path(root)
    plan = json.loads((root / PLAN).read_text())
    original, route_sha = route.verify(root)
    _, full_sha = full.verify(root)
    if (plan.get('schema') != 'clef-openrouter-flash-p2-exact21-v1' or
            plan.get('route_plan_sha256') != route_sha or
            plan.get('full_plan_sha256') != full_sha or
            plan.get('controller_sha256') != sha_path(root / 'scripts/clef_openrouter_flash_p2_exact21_v1.py') or
            plan.get('request_ids') != list(IDS) or
            plan.get('partition_id') != PARTITION_ID or
            plan.get('per_request_reserve_usd') != str(route.bound(KEY, 1)) or
            plan.get('twenty_one_request_upper_bound_usd') != str(route.bound(KEY, 21)) or
            plan.get('cooldown_seconds_after_429') != COOLDOWN_SECONDS or
            plan.get('parent', {}).get('exact_requests') != original['models'][KEY]['requests']['P2'][39:]):
        raise ValueError('Flash exact suffix plan/source identity differs')
    verify_public_proof(root, plan)
    if not require_private:
        return plan, native.sha(native.canonical(plan))
    parent, budget_path, child_path, entry = parent_paths(root)
    evidence = plan['parent']
    for path, expected in evidence['source_sha256'].items():
        if sha_path(root / path) != expected:
            raise ValueError('Flash parent immutable evidence changed')
    child = rows(child_path)
    prefix_len = evidence['child_prefix_events']
    prefix = b''.join(child_path.read_bytes().splitlines(keepends=True)[:prefix_len])
    if (str(child_path.resolve()) != evidence['child_path'] or
            native.sha(prefix) != evidence['child_prefix_sha256'] or
            entry.get('id') != evidence['parent_partition_id'] or
            sha_path(budget_path) != evidence['parent_budget_manifest_sha256']):
        raise ValueError('Flash child prefix or budget changed')
    if build(root) != plan:
        raise ValueError('Flash exact suffix plan differs from all bound evidence')
    return plan, native.sha(native.canonical(plan))


def verify_parent_reconciled(root, plan):
    parent, budget_path, child_path, entry = parent_paths(root)
    child = rows(child_path)
    prefix_len = plan['parent']['child_prefix_events']
    appended = child[prefix_len:]
    attempt = plan['parent']['unknown_attempt_id']
    risk = Decimal(plan['parent']['unknown_upper_bound_usd'])
    known = Decimal(plan['parent']['known_actual_usd'])
    if (len(appended) != 2 or appended[0].get('event') != 'unknown_cost_accounted_as_upper_bound' or
            appended[0].get('attempt_id') != attempt or Decimal(appended[0].get('usd')) != risk or
            appended[0].get('evidence_sha256') != sha_path(parent / 'development.attempts.jsonl') or
            appended[0].get('evidence_path') != str((parent / 'development.attempts.jsonl').resolve()) or
            appended[1].get('event') != 'partition_closed'):
        raise ValueError('Parent unknown risk not exactly finalized and child sealed')
    master = openrouter_budget_v4.BudgetLedger(smoke.MASTER)
    try:
        part = master.partitions.get(full.partition_id(KEY))
        matches = [x for x in master.events if x.get('event') == 'partition_reconciled' and
                   x.get('partition_id') == full.partition_id(KEY)]
        if (not part or part['active'] or len(matches) != 1 or
                Decimal(matches[0]['known_actual_usd']) != known or
                Decimal(matches[0]['unknown_upper_bound_usd']) != risk or
                Decimal(matches[0]['unused_allocation_released_usd']) != Decimal(plan['parent']['unused_after_finalization_usd']) or
                matches[0]['child_sha256'] != sha_path(child_path)):
            raise ValueError('Parent master reconciliation differs')
    finally:
        master.close()
    end = datetime.fromisoformat(plan['parent']['unknown_request_ended_utc'].replace('Z', '+00:00'))
    if datetime.now(timezone.utc) < end + timedelta(seconds=COOLDOWN_SECONDS):
        raise ValueError('Rate-limit cooldown not elapsed; no automatic retry')
    return sha_path(child_path)


def _budget_entry(budget_path, master=smoke.MASTER):
    manifest = json.loads(Path(budget_path).read_text())
    entries = manifest.get('partitions')
    if (manifest.get('version') != 'paid-partitions-v1' or
            manifest.get('master_ledger') != str(Path(master).resolve()) or
            not isinstance(entries, list) or len(entries) != 1):
        raise ValueError('Require one fresh exact suffix child')
    entry = entries[0]
    if (entry.get('id') != PARTITION_ID or entry.get('model') != route.MODELS[KEY]['model'] or
            entry.get('provider') != route.MODELS[KEY]['provider'] or
            entry.get('reasoning') != REASONING or
            Decimal(str(entry.get('cap_usd'))) < route.bound(KEY, 1)):
        raise ValueError('Exact suffix child identity or cap differs')
    return entry


def hold_source(plan_sha, budget_path, master=smoke.MASTER):
    entry = _budget_entry(budget_path, master)
    return native.sha(native.canonical({'kind': 'clef-openrouter-flash-p2-exact21-hold-v1',
        'plan_sha256': plan_sha, 'budget_manifest_sha256': sha_path(budget_path),
        'partition_id': PARTITION_ID, 'child_cap_usd': str(Decimal(entry['cap_usd'])),
        'request_ids': list(IDS)}))


def verify_hold(plan_sha, budget_path, authority_path=smoke.AUTHORITY, master=smoke.MASTER):
    entry = _budget_entry(budget_path, master)
    for retry in range(30):
        try:
            with authority.old._locked(authority_path) as handle:
                _, holds, released = authority._scan(handle.read())
                hold = holds.get(PARTITION_ID)
                if (not hold or PARTITION_ID in released or hold.get('version') != 3 or
                        hold.get('funding_pool') != 'openrouter_additional' or
                        hold.get('usd') != str(Decimal(entry['cap_usd'])) or
                        hold.get('source_sha256') != hold_source(plan_sha, budget_path, master) or
                        hold.get('budget_manifest_sha256') != sha_path(budget_path) or
                        hold.get('budget_manifest_path') != str(Path(budget_path).resolve()) or
                        hold.get('master_path') != str(Path(master).resolve()) or
                        hold.get('partition_id') != PARTITION_ID):
                    raise ValueError('Exact active suffix authority hold missing')
                return
        except BlockingIOError:
            if retry == 29:
                raise
            time.sleep(.1)


def verify_review(root, plan_sha, budget_path):
    path = Path(root) / REVIEW
    receipt = json.loads(path.read_text())
    expected = {'kind': 'clef-openrouter-flash-p2-exact21-root-review-v1',
                'approved': True, 'plan_sha256': plan_sha,
                'controller_sha256': sha_path(Path(root) / 'scripts/clef_openrouter_flash_p2_exact21_v1.py'),
                'budget_manifest_sha256': sha_path(budget_path),
                'partition_id': PARTITION_ID,
                'authority_hold_source_sha256': hold_source(plan_sha, budget_path),
                'request_ids': list(IDS), 'parent_unknown_finalized': True}
    if (any(receipt.get(k) != v for k, v in expected.items()) or
            not isinstance(receipt.get('reviewer'), str) or not receipt['reviewer'].strip()):
        raise ValueError('Exact suffix root approval missing or changed')
    return sha_path(path)


def run(budget_path, *, root=ROOT, master=smoke.MASTER, authority_path=smoke.AUTHORITY,
        fetch=smoke.fetch_endpoint, send=smoke.post, open_child=partitions.open_partition):
    root, budget_path = Path(root), Path(budget_path)
    plan, plan_sha = verify(root, require_private=True)
    parent_child_sha = verify_parent_reconciled(root, plan)
    review_sha = verify_review(root, plan_sha, budget_path)
    verify_hold(plan_sha, budget_path, authority_path, master)
    folder = root / BASE
    files = {name: folder / ('development.' + name) for name in
             ('claim.json', 'journal.jsonl', 'raw.jsonl', 'attempts.jsonl', 'parsed.jsonl')}
    if any(path.exists() for path in files.values()):
        raise FileExistsError('Exact suffix already claimed; no replay')
    _, endpoint = fetch(KEY)
    smoke.verify_live_endpoint(KEY, endpoint, route.verify(root)[0]['models'][KEY]['endpoint'])
    spec = route.MODELS[KEY]
    ledger = open_child(master, budget_path, PARTITION_ID,
                        spec['model'], spec['provider'], REASONING)
    try:
        _, pending, blocked = ledger.state()
        if (ledger.master_cap != openrouter_budget_v4.CAP or pending or blocked or ledger.closed or
                ledger.accounted() + route.bound(KEY, 1) > ledger.cap):
            raise ValueError('Exact suffix child lacks first full reserve')
        token = os.environ.get('OPENROUTER_API_KEY')
        if not token:
            raise ValueError('OPENROUTER_API_KEY required')
        folder.mkdir(parents=True, exist_ok=True)
        with files['claim.json'].open('x') as out:
            durable(out, {'kind': 'clef-openrouter-flash-p2-exact21-claim-v1',
                'plan_sha256': plan_sha, 'root_review_sha256': review_sha,
                'parent_reconciled_child_sha256': parent_child_sha,
                'budget_manifest_sha256': sha_path(budget_path),
                'request_ids': list(IDS), 'reference_labels_sent': False, 'claimed_utc': now()})
        with files['journal.jsonl'].open('x') as journal, files['raw.jsonl'].open('x') as raw, \
                files['attempts.jsonl'].open('x') as attempts, files['parsed.jsonl'].open('x') as parsed:
            durable(journal, {'event': 'stage_started', 'utc': now(), 'plan_sha256': plan_sha})
            for item in plan['parent']['exact_requests']:
                rid = item['id']
                try:
                    verify(root, require_private=True)
                    verify_parent_reconciled(root, plan)
                    verify_review(root, plan_sha, budget_path)
                    verify_hold(plan_sha, budget_path, authority_path, master)
                    endpoint_raw, endpoint = fetch(KEY)
                    smoke.verify_live_endpoint(KEY, endpoint, route.verify(root)[0]['models'][KEY]['endpoint'])
                    if native.sha(native.canonical(item['payload'])) != item['payload_sha256']:
                        raise ValueError('Exact suffix payload drift')
                    if ledger.accounted() + route.bound(KEY, 1) > ledger.cap:
                        raise ValueError('Exact suffix child lacks next reserve')
                    durable(journal, {'event': 'request_intent', 'id': rid,
                        'payload_sha256': item['payload_sha256'], 'utc': now()})
                    attempt = ledger.reserve(route.bound(KEY, 1), f'{STAGE}:exact-unsent:{rid}')
                    durable(journal, {'event': 'request_started', 'id': rid, 'attempt_id': attempt,
                        'live_endpoint_sha256': native.sha(endpoint_raw), 'utc': now()})
                    started, t0 = now(), time.perf_counter_ns()
                    try:
                        status, wire = send(item['payload'], token)
                    except BaseException as error:
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'transport_error',
                            'error_type': type(error).__name__, 'cost_unknown': True,
                            'reserved_cost_usd': str(route.bound(KEY, 1)),
                            'request_started_utc': started, 'request_ended_utc': now(),
                            'client_request_elapsed_ns': time.perf_counter_ns() - t0})
                        raise
                    ended, elapsed = now(), time.perf_counter_ns() - t0
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
                            'reserved_cost_usd': str(route.bound(KEY, 1))})
                        raise ValueError('Exact suffix cost unknown; reservation retained')
                    if not ledger.settle(attempt, actual):
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'over_bound',
                            'http_status': status, 'actual_cost_usd': str(actual)})
                        raise ValueError('Exact suffix actual cost exceeded reserve')
                    if status != 200:
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'http_error',
                            'http_status': status, 'actual_cost_usd': str(actual)})
                        raise ValueError('Exact suffix provider HTTP error; no retry')
                    try:
                        prediction = full.validate_returned(KEY, body)
                    except ValueError:
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'invalid_native_response',
                            'actual_cost_usd': str(actual)})
                        raise
                    durable(parsed, {'id': rid, 'attempt_id': attempt, 'prediction': prediction,
                        'input_tokens': body['usage']['input_tokens'],
                        'output_tokens': body['usage']['output_tokens'],
                        'actual_cost_usd': str(actual)})
                    durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'ok',
                        'actual_cost_usd': str(actual), 'cost_unknown': False})
                except BaseException as error:
                    durable(journal, {'event': 'stage_stopped', 'id': rid,
                        'error_type': type(error).__name__, 'utc': now()})
                    raise
            durable(journal, {'event': 'stage_completed', 'utc': now(), 'count': len(IDS)})
    finally:
        ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('write-proof', 'write', 'check', 'run'))
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--budget', type=Path)
    args = parser.parse_args()
    if args.action == 'run':
        if not args.budget:
            parser.error('run requires --budget')
        run(args.budget, root=args.root)
        return
    if args.action == 'write-proof':
        value = make_public_proof(args.root)
        path = args.root / PROOF
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x') as out:
            out.write(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
        print(sha_path(path))
        return
    path = args.root / PLAN
    if args.action == 'write':
        value = build(args.root)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x') as out:
            out.write(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
        print(native.sha(native.canonical(value)))
    else:
        _, digest = verify(args.root)
        print(digest)


if __name__ == '__main__':
    main()
