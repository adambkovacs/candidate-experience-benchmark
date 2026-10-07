#!/usr/bin/env python3
"""Gated 60-review native Decisions executor for the frozen Clef/Flash/Luna routes.

The offline ``write`` and ``check`` commands do not allocate or send requests.
``run`` requires a separate reviewed smoke, funded child and active authority hold.
"""

import argparse
import base64
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import time

from development_benchmark import ROOT, KEYS
from jev_benchmark import parse_response
from openrouter_paid_benchmark import durable
import openrouter_budget_v4
import paid_budget_partitions_v4 as partitions
import openrouter_authority_release_v4 as authority
import clef_openrouter_native_v1 as route
import clef_openrouter_smoke_v1 as smoke
import openrouter_decision_smoke as native


BASE = route.BASE / 'full-v1'
PLAN = BASE / 'plan.json'
REVIEW = BASE / 'root-review.json'
REASONING = 'native-decisions-development'
RETURNED_MODEL = {
    'clef': 'cloudflare/clef',
    'clef-flash': 'cloudflare/clef-flash',
    'luna-decisions': 'openai/gpt-6-luna-decisions-20261006',
}


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def sha_path(path):
    return native.sha(Path(path).read_bytes())


def stage_dir(root, key, stage):
    smoke.partition_id(key, stage)
    return Path(root) / BASE / key / stage


def partition_id(key):
    if key not in route.MODELS:
        raise ValueError('Undeclared native development model')
    return f'clef-openrouter-v1-{key}-all-nine-development'


def build(root=ROOT):
    root = Path(root)
    _, route_sha = route.verify(root)
    source = root / 'scripts/clef_openrouter_full_v1.py'
    stages = [f'{p}/{c}' for p in route.PASSES for c in route.CONDITIONS]
    return {'schema': 'clef-openrouter-native-full-gate-v1',
            'status': 'prepared_not_admitted', 'inference_performed': False,
            'allocation_performed': False, 'reference_labels_read': False,
            'route_plan_sha256': route_sha, 'runner_sha256': sha_path(source),
            'models': {key: {'model': value['model'], 'provider': value['provider'],
                             'stages': stages, 'development_ids': list(route.IDS),
                             'per_request_four_context_bound_usd': str(route.bound(key, 1))}
                       for key, value in route.MODELS.items()},
            'gate': 'Each stage needs three saved valid smoke responses and a source-bound root inspection.',
            'budget': 'One reviewed child and active OpenRouter hold per model span nine separately claimed stages. Each next full-context reserve must fit the child; settle observed cost or retain unknown, stop without replay.'}


def verify(root=ROOT):
    value = build(root)
    if json.loads((Path(root) / PLAN).read_text()) != value:
        raise ValueError('Full gate plan differs from frozen sources')
    return value, native.sha(native.canonical(value))


def verify_global_review(root, full_sha):
    path = Path(root) / REVIEW
    receipt = json.loads(path.read_text())
    if (receipt.get('kind') != 'clef-openrouter-native-full-root-review-v1' or
            receipt.get('approved') is not True or
            receipt.get('full_plan_sha256') != full_sha or
            receipt.get('full_plan_file_sha256') != sha_path(Path(root) / PLAN) or
            receipt.get('runner_sha256') != sha_path(Path(root) / 'scripts/clef_openrouter_full_v1.py') or
            receipt.get('route_plan_sha256') != route.verify(root)[1] or
            not isinstance(receipt.get('reviewer'), str) or not receipt['reviewer'].strip()):
        raise ValueError('Root full-plan review missing or changed')
    return receipt


def _jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def verify_smoke_inspection(root, key, stage, route_sha, full_sha):
    new_folder = stage_dir(root, key, stage)
    folder = new_folder if (new_folder / 'smoke.claim.json').exists() else smoke.stage_dir(root, key, stage)
    names = ('claim.json', 'journal.jsonl', 'raw.jsonl', 'attempts.jsonl', 'parsed.jsonl')
    files = {name: folder / ('smoke.' + name) for name in names}
    hashes = {name: sha_path(path) for name, path in files.items()}
    claim = json.loads(files['claim.json'].read_text())
    raw, attempts, parsed, journal = (_jsonl(files[name]) for name in
                                      ('raw.jsonl', 'attempts.jsonl', 'parsed.jsonl', 'journal.jsonl'))
    ids = list(route.SMOKE_IDS)
    source_ok = (claim.get('plan_sha256') == route_sha or
                 (claim.get('full_plan_sha256') == full_sha and
                  claim.get('route_plan_sha256') == route_sha))
    if (not source_ok or claim.get('model_key') != key or
            claim.get('stage') != stage or
            [row.get('id') for row in raw] != ids or
            [row.get('id') for row in attempts] != ids or
            [row.get('id') for row in parsed] != ids or
            any(row.get('http_status') != 200 for row in raw) or
            any(row.get('status') != 'ok' or row.get('cost_unknown') is not False for row in attempts) or
            not journal or journal[-1].get('event') != 'stage_completed' or
            journal[-1].get('count') != 3 or
            len([row for row in journal if row.get('event') == 'request_started']) != 3):
        raise ValueError('Three valid smoke responses are not closed')
    for original, outcome, prediction in zip(raw, attempts, parsed):
        wire = base64.b64decode(original['response_base64'], validate=True)
        if (native.sha(wire) != original['response_sha256'] or
                original.get('attempt_id') != outcome.get('attempt_id') or
                original.get('attempt_id') != prediction.get('attempt_id') or
                outcome.get('actual_cost_usd') != prediction.get('actual_cost_usd')):
            raise ValueError('Saved smoke response identity or cost differs')
    receipt_path = folder / 'smoke.root-inspection.json'
    receipt = json.loads(receipt_path.read_text())
    expected = {'kind': 'clef-openrouter-native-smoke-inspection-v1', 'approved': True,
                'model_key': key, 'stage': stage, 'route_plan_sha256': route_sha,
                'smoke_file_sha256': hashes, 'valid_ids': ids}
    if (any(receipt.get(k) != v for k, v in expected.items()) or
            not isinstance(receipt.get('reviewer'), str) or not receipt['reviewer'].strip()):
        raise ValueError('Root smoke inspection does not bind three saved responses')
    return sha_path(receipt_path)


def verify_previous_stage(root, key, stage):
    stages = [f'{p}/{c}' for p in route.PASSES for c in route.CONDITIONS]
    position = stages.index(stage)
    if position == 0:
        return
    previous = stage_dir(root, key, stages[position - 1]) / 'development.journal.jsonl'
    journal = _jsonl(previous)
    if not journal or journal[-1].get('event') != 'stage_completed' or journal[-1].get('count') != 60:
        raise ValueError('Previous declared development stage is not closed')


def _budget_entry(budget_path, key, master):
    manifest = json.loads(Path(budget_path).read_text())
    entries = manifest.get('partitions')
    pid = partition_id(key)
    if (manifest.get('version') != 'paid-partitions-v1' or
            manifest.get('master_ledger') != str(Path(master).resolve()) or
            not isinstance(entries, list) or len(entries) != 1):
        raise ValueError('Require one exact development budget child')
    entry = entries[0]
    spec = route.MODELS[key]
    if (entry.get('id') != pid or entry.get('model') != spec['model'] or
            entry.get('provider') != spec['provider'] or
            entry.get('reasoning') != REASONING or
            Decimal(str(entry.get('cap_usd'))) < route.bound(key, 1)):
        raise ValueError('Development child identity or one-request cap differs')
    return entry


def hold_source(full_sha, budget_path, key, master=smoke.MASTER):
    entry = _budget_entry(budget_path, key, master)
    return native.sha(native.canonical({
        'kind': 'clef-openrouter-native-full-hold-v1', 'full_plan_sha256': full_sha,
        'budget_manifest_sha256': sha_path(budget_path), 'partition_id': entry['id'],
        'child_cap_usd': str(Decimal(str(entry['cap_usd']))),
        'declared_stages': [f'{p}/{c}' for p in route.PASSES for c in route.CONDITIONS]}))


def verify_hold(full_sha, budget_path, key,
                authority_path=smoke.AUTHORITY, master=smoke.MASTER):
    entry = _budget_entry(budget_path, key, master)
    pid = entry['id']
    # Concurrent stage admission may briefly own this nonblocking ledger lock.
    # This is a bounded pre-request read retry, never an inference retry.
    for retry in range(30):
        try:
            with authority.old._locked(authority_path) as handle:
                _, holds, released = authority._scan(handle.read())
                hold = holds.get(pid)
                if (not hold or pid in released or hold.get('version') != 3 or
                        hold.get('funding_pool') != 'openrouter_additional' or
                        hold.get('usd') != str(Decimal(str(entry['cap_usd']))) or
                        hold.get('source_sha256') != hold_source(full_sha, budget_path, key, master) or
                        hold.get('budget_manifest_sha256') != sha_path(budget_path) or
                        hold.get('budget_manifest_path') != str(Path(budget_path).resolve()) or
                        hold.get('master_path') != str(Path(master).resolve()) or
                        hold.get('partition_id') != pid):
                    raise ValueError('Exact active development authority hold missing')
                return
        except BlockingIOError:
            if retry == 29:
                raise
            time.sleep(.1)


def validate_returned(key, body):
    spec = route.MODELS[key]
    if not isinstance(body, dict) or body.get('provider') != spec['provider']:
        raise ValueError('Returned native provider differs')
    prediction = parse_response(body, RETURNED_MODEL[key])
    usage = body.get('usage')
    if (not isinstance(usage, dict) or type(usage.get('input_tokens')) is not int or
            not 0 <= usage['input_tokens'] <= len(KEYS) * spec['context'] or
            type(usage.get('output_tokens')) is not int or usage['output_tokens'] < 0):
        raise ValueError('Native token usage missing or outside reviewed context')
    return prediction


def run(key, stage, budget_path, *, phase='development', root=ROOT, master=smoke.MASTER,
        authority_path=smoke.AUTHORITY, fetch=smoke.fetch_endpoint,
        send=smoke.post, open_child=partitions.open_partition):
    root, budget_path = Path(root), Path(budget_path)
    full, full_sha = verify(root)
    route_plan, route_sha = route.verify(root)
    if key not in full['models'] or stage not in full['models'][key]['stages'] or phase not in ('smoke', 'development'):
        raise ValueError('Undeclared native development stage')
    verify_global_review(root, full_sha)
    verify_previous_stage(root, key, stage)
    inspection_sha = (verify_smoke_inspection(root, key, stage, route_sha, full_sha)
                      if phase == 'development' else None)
    verify_hold(full_sha, budget_path, key, authority_path, master)
    folder = stage_dir(root, key, stage)
    paths = {name: folder / (phase + '.' + name) for name in
             ('claim.json', 'journal.jsonl', 'raw.jsonl', 'attempts.jsonl', 'parsed.jsonl')}
    if any(path.exists() for path in paths.values()):
        raise FileExistsError('Native phase already claimed; no replay')
    if phase == 'smoke':
        if (smoke.stage_dir(root, key, stage) / 'smoke.claim.json').exists():
            raise FileExistsError('Historical smoke already claimed; no replay')
        try:
            verify_smoke_inspection(root, key, stage, route_sha, full_sha)
        except (FileNotFoundError, ValueError):
            pass
        else:
            raise FileExistsError('Smoke already completed and inspected; no replay')
    _, live = fetch(key)
    smoke.verify_live_endpoint(key, live, route_plan['models'][key]['endpoint'])
    spec = route.MODELS[key]
    ledger = open_child(master, budget_path, partition_id(key),
                        spec['model'], spec['provider'], REASONING)
    try:
        if ledger.master_cap != openrouter_budget_v4.CAP:
            raise ValueError('OpenRouter master cap differs')
        _, pending, blocked = ledger.state()
        if pending or blocked or ledger.closed or ledger.accounted() + route.bound(key, 1) > ledger.cap:
            raise ValueError('Native child lacks first full-context reserve')
        token = os.environ.get('OPENROUTER_API_KEY')
        if not token:
            raise ValueError('OPENROUTER_API_KEY required in process environment')
        folder.mkdir(parents=True, exist_ok=True)
        with paths['claim.json'].open('x') as out:
            durable(out, {'kind': 'clef-openrouter-native-full-phase-claim-v1',
                          'full_plan_sha256': full_sha, 'route_plan_sha256': route_sha,
                          'root_review_sha256': sha_path(root / REVIEW),
                          'smoke_inspection_sha256': inspection_sha, 'phase': phase,
                          'budget_manifest_sha256': sha_path(budget_path),
                          'claimed_utc': now(), 'model_key': key, 'stage': stage,
                          'reference_labels_sent': False})
        condition = stage.split('/')[1]
        items = route_plan['models'][key]['requests'][condition]
        if phase == 'smoke':
            items = items[:3]
        with paths['journal.jsonl'].open('x') as journal, paths['raw.jsonl'].open('x') as raw_file, \
                paths['attempts.jsonl'].open('x') as attempts, paths['parsed.jsonl'].open('x') as parsed:
            durable(journal, {'event': 'stage_started', 'utc': now(), 'full_plan_sha256': full_sha})
            for item in items:
                rid = item['id']
                try:
                    verify(root)
                    verify_global_review(root, full_sha)
                    if phase == 'development':
                        verify_smoke_inspection(root, key, stage, route_sha, full_sha)
                    verify_hold(full_sha, budget_path, key, authority_path, master)
                    route_raw, route_body = fetch(key)
                    smoke.verify_live_endpoint(key, route_body, route_plan['models'][key]['endpoint'])
                    if native.sha(native.canonical(item['payload'])) != item['payload_sha256']:
                        raise ValueError('Native phase payload drift')
                    if ledger.accounted() + route.bound(key, 1) > ledger.cap:
                        raise ValueError('Native child lacks next full-context reserve')
                    durable(journal, {'event': 'request_intent', 'id': rid,
                                      'payload_sha256': item['payload_sha256'], 'utc': now()})
                    attempt = ledger.reserve(route.bound(key, 1), f'{stage}:{phase}:{rid}')
                    durable(journal, {'event': 'request_started', 'id': rid, 'attempt_id': attempt,
                                      'live_endpoint_sha256': native.sha(route_raw), 'utc': now()})
                    started, t0 = now(), time.perf_counter_ns()
                    try:
                        status, wire = send(item['payload'], token)
                    except BaseException as error:
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'transport_error',
                                           'error_type': type(error).__name__, 'cost_unknown': True,
                                           'reserved_cost_usd': str(route.bound(key, 1)),
                                           'request_started_utc': started, 'request_ended_utc': now(),
                                           'client_request_elapsed_ns': time.perf_counter_ns() - t0})
                        raise
                    ended, elapsed = now(), time.perf_counter_ns() - t0
                    durable(raw_file, {'id': rid, 'attempt_id': attempt,
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
                                           'reserved_cost_usd': str(route.bound(key, 1))})
                        raise ValueError('Native phase cost unknown; full reservation retained')
                    if not ledger.settle(attempt, actual):
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'over_bound',
                                           'http_status': status, 'actual_cost_usd': str(actual)})
                        raise ValueError('Observed native phase cost exceeded reserve')
                    if status != 200:
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'http_error',
                                           'http_status': status, 'actual_cost_usd': str(actual)})
                        raise ValueError('Native phase provider HTTP error; no retry')
                    try:
                        prediction = validate_returned(key, body)
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
            durable(journal, {'event': 'stage_completed', 'utc': now(), 'count': len(items)})
    finally:
        ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('write', 'check', 'run'))
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--key', choices=tuple(route.MODELS))
    parser.add_argument('--stage')
    parser.add_argument('--phase', choices=('smoke', 'development'), default='development')
    parser.add_argument('--budget', type=Path)
    args = parser.parse_args()
    if args.action == 'run':
        if not args.key or not args.stage or not args.budget:
            parser.error('run requires key, stage and budget')
        run(args.key, args.stage, args.budget, phase=args.phase, root=args.root)
        return
    value = build(args.root)
    target = args.root / PLAN
    if args.action == 'write':
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('x') as out:
            out.write(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    elif json.loads(target.read_text()) != value:
        raise SystemExit('Full gate plan changed')
    print(native.sha(native.canonical(value)))


if __name__ == '__main__':
    main()
