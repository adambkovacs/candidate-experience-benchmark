#!/usr/bin/env python3
"""Reviewed, no-retry Jev repeat executor. No dispatch occurs on import or freeze."""
import argparse
import base64
from decimal import Decimal
import fcntl
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

from development_benchmark import ROOT, KEYS, digest
from jev_benchmark import (BudgetLedger, OPENER, PRICE_MODEL, PRICE_PER_MILLION_INPUT,
                           load_key, parse_response, reserve_cost, usage_cost, validate_config)
import jev_native_prompt_variants_v1 as native
import typesafe_repeat_study as study

BASE = ROOT / 'results/repeatability-v1/typesafe-jev113-v2'
CAP = Decimal('1')
MAX_RAW = 1024 * 1024
PRICE_URL = 'https://docs.typesafe.ai/models'
ENDPOINT = 'https://api.typesafe.ai/v1/systemone'
REQUEST_TIMEOUT = 120


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    return sha(Path(path).read_bytes())


def json_bytes(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode()


def exclusive_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as out:
        out.write(json_bytes(value))
        out.flush()
        os.fsync(out.fileno())


def append(path, value):
    with Path(path).open('ab') as out:
        out.write((json.dumps(value, ensure_ascii=False) + '\n').encode())
        out.flush()
        os.fsync(out.fileno())


def read_lines(path):
    raw = Path(path).read_bytes()
    if raw and (not raw.endswith(b'\n') or any(not x.strip() for x in raw.splitlines())):
        raise ValueError('Incomplete stage evidence')
    return [json.loads(x) for x in raw.splitlines()]


def reviewed(path, expected):
    receipt = json.loads(Path(path).read_text())
    if receipt != dict(expected, reviewed=True):
        raise ValueError('Review receipt does not bind this exact admission')


def freeze(draft_path, review_path, frozen_path):
    """Freeze only the exact currently reproducible offline plan after root review."""
    draft = Path(draft_path).read_bytes()
    with native.LEDGER.open('rb') as ledger_file:
        fcntl.flock(ledger_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if draft != json_bytes(study.plan()):
            raise ValueError('Offline draft differs from current historical evidence or ledger')
        reviewed(review_path, {'kind': 'typesafe-repeat-freeze-review-v1',
                               'draft_sha256': sha(draft), 'controller_sha256': file_sha(__file__)})
        ledger = ledger_file.read()
        if sha(ledger) != json.loads(draft)['budget_snapshot']['ledger']['sha256']:
            raise ValueError('Ledger changed during freeze')
        frozen = {'kind': 'typesafe-repeat-frozen-v1', 'draft_sha256': sha(draft),
                  'controller_sha256': file_sha(__file__),
                  'request_timeout_seconds': REQUEST_TIMEOUT,
                  'freeze_review_sha256': file_sha(review_path),
                  'ledger_prefix_length': len(ledger), 'ledger_prefix_sha256': sha(ledger),
                  'plan': json.loads(draft)}
        exclusive_json(frozen_path, frozen)
    return frozen


def load_frozen(path):
    frozen = json.loads(Path(path).read_text())
    plan = frozen.get('plan', {})
    if (frozen.get('kind') != 'typesafe-repeat-frozen-v1' or
            frozen.get('controller_sha256') != file_sha(__file__) or
            frozen.get('draft_sha256') != sha(json_bytes(plan)) or
            plan.get('schema') != 'typesafe-jev-repeat-offline-admission-v1' or
            frozen.get('request_timeout_seconds') != REQUEST_TIMEOUT or
            plan.get('model') != PRICE_MODEL or plan.get('endpoint') != ENDPOINT or
            plan.get('dispatch_authorized') is not False):
        raise ValueError('Frozen repeat plan or controller changed')
    raw = native.LEDGER.read_bytes()
    prefix = raw[:frozen['ledger_prefix_length']]
    if (len(prefix) != frozen['ledger_prefix_length'] or
            sha(prefix) != frozen['ledger_prefix_sha256']):
        raise ValueError('Shared TypeSafe ledger no longer extends frozen prefix')
    if plan['budget_snapshot']['ledger']['sha256'] != frozen['ledger_prefix_sha256']:
        raise ValueError('Frozen budget snapshot differs from ledger prefix')
    for binding in plan['source_bindings']:
        source = (ROOT / binding['path']).resolve()
        source.relative_to(ROOT.resolve())
        if binding['path'] == str(native.LEDGER.relative_to(ROOT)):
            continue
        if file_sha(source) != binding['sha256']:
            raise ValueError('Frozen source changed: ' + binding['path'])
    return frozen


def stage_dir(base, repeat, condition):
    return Path(base) / repeat / condition


def stage_paths(base, repeat, condition, phase, stage):
    stem = f'{phase}-{stage:03}'
    folder = stage_dir(base, repeat, condition)
    return {suffix: folder / f'{stem}.{suffix}' for suffix in
            ('claim.json', 'journal.jsonl', 'attempts.jsonl')}


def stage_history(base, repeat, condition, phase):
    folder = stage_dir(base, repeat, condition)
    claims = sorted(folder.glob(f'{phase}-*.claim.json')) if folder.exists() else []
    if [p.name for p in claims] != [f'{phase}-{i:03}.claim.json' for i in range(len(claims))]:
        raise ValueError('Stage claim sequence has a gap')
    attempted = []
    for i, claim_path in enumerate(claims):
        paths = stage_paths(base, repeat, condition, phase, i)
        claim = json.loads(claim_path.read_text())
        journal = read_lines(paths['journal.jsonl'])
        results = read_lines(paths['attempts.jsonl'])
        started = [e for e in journal if e.get('event') == 'started']
        finished = [e for e in journal if e.get('event') == 'finished']
        terminals = [e for e in journal if e.get('event') == 'terminal']
        if (len(terminals) != 1 or journal[-1] != terminals[0] or
                len(started) != len(finished) or len(results) != len(started) or
                [x['id'] for x in started] != [x['id'] for x in results] or
                [x['id'] for x in finished] != [x['id'] for x in results] or
                claim.get('start_index') != len(attempted)):
            raise ValueError('Unresolved or conflicting stage evidence; no automatic resend')
        for start, finish, row in zip(started, finished, results):
            raw_name = row.get('raw_path')
            if not isinstance(raw_name, str) or raw_name != f'{phase}-{i:03}-{row["id"]}.raw.json':
                raise ValueError('Stage raw evidence is missing or misattributed')
            raw_record = json.loads((folder / raw_name).read_text())
            raw = base64.b64decode(raw_record['raw_base64'], validate=True)
            if (start.get('attempt_id') != finish.get('attempt_id') or
                    start.get('attempt_id') != row.get('budget_attempt_id') or
                    start.get('request_sha256') != row.get('request_sha256') or
                    raw_record.get('attempt_id') != row.get('budget_attempt_id') or
                    raw_record.get('request_sha256') != row.get('request_sha256') or
                    sha(raw) != row.get('raw_sha256') or finish.get('raw_sha256') != sha(raw) or
                    finish.get('status') != row.get('status')):
                raise ValueError('Stage attempt and raw evidence disagree')
        attempted.extend(x['id'] for x in results)
    return attempted, claims


def previous_gate(base, repeat, condition, phase):
    order = [(r, c) for r, conditions in study.ORDERS.items() for c in conditions]
    index = order.index((repeat, condition))
    if phase == 'development':
        smoke_ids, smoke_claims = stage_history(base, repeat, condition, 'smoke')
        if smoke_ids != study.SMOKE_IDS or len(smoke_claims) != 1:
            raise ValueError('Three complete smoke attempts required')
        smoke = stage_paths(base, repeat, condition, 'smoke', 0)['attempts.jsonl']
        rows = read_lines(smoke)
        if any(r.get('status') != 'ok' or r.get('cost_unknown') for r in rows):
            raise ValueError('Smoke did not pass')
        receipt = stage_dir(base, repeat, condition) / 'smoke-inspection.json'
        reviewed(receipt, {'kind': 'typesafe-repeat-smoke-inspection-v1',
                           'smoke_attempts_sha256': file_sha(smoke)})
    elif index:
        prior_r, prior_c = order[index - 1]
        ids, _ = stage_history(base, prior_r, prior_c, 'development')
        if ids != study.IDS:
            raise ValueError('Prior ordered development pass lacks 60 first attempts')


def price_preflight(opener=OPENER):
    req = urllib.request.Request(PRICE_URL, headers={'User-Agent': 'classification-bench-price-check/1'})
    with opener.open(req, timeout=20) as response:
        if response.geturl() != PRICE_URL or response.status != 200:
            raise ValueError('Pricing route redirected')
        raw = response.read(512001)
    if len(raw) > 512000:
        raise ValueError('Pricing evidence too large')
    text = raw.decode('utf-8')
    model_position = text.find(PRICE_MODEL)
    if model_position < 0 or '$0.042' not in text[model_position:model_position + 2000]:
        raise ValueError('Pinned Jev model or price absent from official pricing page')
    return sha(raw)


def capture(request, token, timeout, opener=OPENER):
    wire = urllib.request.Request(ENDPOINT, data=json.dumps(request).encode(),
                                 headers={'Content-Type': 'application/json',
                                          'Authorization': 'Bearer ' + token}, method='POST')
    started = time.perf_counter()
    try:
        response = opener.open(wire, timeout=timeout)
        try:
            if response.geturl() != ENDPOINT:
                raise ValueError('Endpoint changed')
            raw = response.read(MAX_RAW + 1)
            status = response.status
        except http.client.IncompleteRead as exc:
            return {'raw': exc.partial[:MAX_RAW + 1], 'read_error': 'IncompleteRead',
                    'http_status': getattr(response, 'status', None),
                    'client_http_call_seconds': time.perf_counter() - started}
        finally:
            response.close()
        return {'raw': raw, 'http_status': status,
                'read_error': 'response_too_large' if len(raw) > MAX_RAW else None,
                'client_http_call_seconds': time.perf_counter() - started}
    except urllib.error.HTTPError as exc:
        try:
            raw = exc.read(MAX_RAW + 1)
            error = 'response_too_large' if len(raw) > MAX_RAW else None
        except http.client.IncompleteRead as partial:
            raw, error = partial.partial[:MAX_RAW + 1], 'IncompleteRead'
        return {'raw': raw, 'http_status': exc.code, 'read_error': error,
                'retry_after': exc.headers.get('Retry-After'),
                'client_http_call_seconds': time.perf_counter() - started}
    except Exception as exc:
        return {'raw': b'', 'transport_error': type(exc).__name__,
                'client_http_call_seconds': time.perf_counter() - started}


def pending_ids(events):
    reserved = {e['attempt_id'] for e in events if e['event'] == 'reserve'}
    settled = {e['attempt_id'] for e in events if e['event'] == 'settle'}
    if len(reserved) != len([e for e in events if e['event'] == 'reserve']):
        raise ValueError('Duplicate reservation in shared ledger')
    return reserved - settled


def run_stage(*, frozen_path, phase_review, repeat, condition, phase, stage=0,
              base=BASE, env_file=None, timeout=REQUEST_TIMEOUT, opener=OPENER):
    if repeat not in study.ORDERS or condition not in study.ORDERS[repeat] or phase not in ('smoke', 'development'):
        raise ValueError('Undeclared repeat, condition or phase')
    if type(stage) is not int or stage < 0 or stage > 999 or not math.isfinite(timeout) or timeout != REQUEST_TIMEOUT:
        raise ValueError('Invalid stage or timeout')
    validate_config('typesafe', 'https://api.typesafe.ai', PRICE_MODEL, 'official', True)
    frozen = load_frozen(frozen_path)
    manifest, manifest_sha = native.read_frozen_manifest(study.BASE / 'input-only-manifest.json')
    input_rows, policy = native.load_inputs(), native.load_policy()
    previous_gate(base, repeat, condition, phase)
    already, claims = stage_history(base, repeat, condition, phase)
    if stage != len(claims):
        raise ValueError('Stage number already claimed or skips a stage')
    ids = study.SMOKE_IDS if phase == 'smoke' else study.IDS
    if already != ids[:len(already)] or (phase == 'smoke' and stage != 0):
        raise ValueError('Only contiguous never-sent IDs may be admitted')
    if already and stage == 0:
        raise ValueError('Existing attempts cannot be repeated')
    if already and stage > 0:
        prior = read_lines(stage_paths(base, repeat, condition, phase, stage - 1)['journal.jsonl'])[-1]
        if prior.get('status') != 'stopped':
            raise ValueError('Completed stage cannot continue')
    price_sha = price_preflight(opener)
    reviewed(phase_review, {'kind': 'typesafe-repeat-phase-review-v1',
                            'frozen_sha256': file_sha(frozen_path),
                            'controller_sha256': file_sha(__file__),
                            'repeat': repeat, 'condition': condition, 'phase': phase,
                            'stage': stage, 'start_index': len(already),
                            'price_page_sha256': price_sha})
    paths = stage_paths(base, repeat, condition, phase, stage)
    if any(p.exists() for p in paths.values()):
        raise ValueError('Stage evidence already exists')
    ledger = BudgetLedger(native.LEDGER, CAP)
    try:
        load_frozen(frozen_path)
        if pending_ids(ledger.events) != {frozen['plan']['historical_selection']['P0']['failed_attempt_id']}:
            raise ValueError('Unreviewed pending TypeSafe cost blocks admission')
        token = load_key('typesafe', env_file)
        if not token:
            raise ValueError('TypeSafe key missing')
        exclusive_json(paths['claim.json'], {'kind': 'typesafe-repeat-stage-claim-v1',
                                             'frozen_sha256': file_sha(frozen_path),
                                             'review_sha256': file_sha(phase_review),
                                             'repeat': repeat, 'condition': condition,
                                             'phase': phase, 'stage': stage,
                                             'start_index': len(already)})
        paths['journal.jsonl'].touch(mode=0o600, exist_ok=False)
        paths['attempts.jsonl'].touch(mode=0o600, exist_ok=False)
        reason = None
        for index in range(len(already), len(ids)):
            rid = ids[index]
            row = input_rows[int(rid[4:]) - 1]
            request = native.payload(row['feedback'], policy, condition)
            expected = manifest['requests'][condition][int(rid[4:]) - 1]
            request_sha = digest(json.dumps(request, sort_keys=True))
            amount = reserve_cost(request)
            if (expected != {'id': rid, 'request_sha256': request_sha, 'reserve_usd': str(amount)} or
                    frozen['plan']['future_passes'][0 if repeat == 'repeat2' else 1]['conditions'][condition]['requests'][int(rid[4:]) - 1] != expected):
                reason = 'request_binding_failure'
                break
            attempt = ledger.reserve(amount, rid)
            if attempt is None:
                reason = 'budget_stop'
                break
            append(paths['journal.jsonl'], {'event': 'started', 'id': rid, 'attempt_id': attempt,
                                             'request_sha256': request_sha, 'reserved_usd': str(amount)})
            result = {'id': rid, 'repeat': repeat, 'condition': condition, 'phase': phase,
                      'stage': stage, 'request': request, 'request_sha256': request_sha,
                      'manifest_sha256': manifest_sha, 'requested_model': PRICE_MODEL,
                      'request_timeout_seconds': REQUEST_TIMEOUT,
                      'reference_labels_read': False,
                      'question_version': frozen['plan']['controls']['question_version'],
                      'question_order': list(KEYS),
                      'input_sha256': digest(row['feedback']), 'policy_sha256': digest(policy),
                      'budget_attempt_id': attempt, 'reserved_cost_usd': str(amount),
                      'retry_policy': 'none', 'provider_inference_seconds': None,
                      'actual_charge_usd': None,
                      'price_per_million_input_usd': str(PRICE_PER_MILLION_INPUT),
                      'cost_basis': 'Estimated from reported input tokens; provider invoice unavailable.'}
            observed = capture(request, token, timeout, opener)
            original_raw = observed.pop('raw')
            raw = original_raw.replace(token.encode(), b'[REDACTED_TOKEN]')
            redacted = raw != original_raw
            raw_path = paths['claim.json'].parent / f'{phase}-{stage:03}-{rid}.raw.json'
            exclusive_json(raw_path, {'attempt_id': attempt, 'request_sha256': request_sha,
                                      'raw_base64': base64.b64encode(raw).decode(),
                                      'token_redacted': redacted, **observed})
            result['raw_sha256'] = sha(raw)
            result['raw_path'] = raw_path.name
            result['token_redacted'] = redacted
            result.update(observed)
            body = None
            if (not observed.get('transport_error') and not observed.get('read_error') and
                    observed.get('http_status') == 200):
                try:
                    body = json.loads(raw)
                except (ValueError, UnicodeDecodeError):
                    pass
            result['raw_response'] = body
            result['returned_model'] = body.get('model') if isinstance(body, dict) else None
            usage = body.get('usage') if isinstance(body, dict) else None
            result['usage'] = usage
            actual = usage_cost(body) if isinstance(body, dict) else None
            result['estimated_usage_cost_usd'] = str(actual) if actual is not None else None
            result['cost_unknown'] = actual is None
            result['reported_input_tokens'] = usage.get('input_tokens') if isinstance(usage, dict) else None
            result['reported_output_tokens'] = usage.get('output_tokens') if isinstance(usage, dict) else None
            result['reported_reasoning_tokens'] = usage.get('reasoning_tokens') if isinstance(usage, dict) else None
            if body is not None and isinstance(body, dict) and body.get('model') != PRICE_MODEL:
                result['status'] = 'identity_violation'
            elif observed.get('http_status') != 200 or observed.get('transport_error') or observed.get('read_error'):
                result['status'] = 'service_error'
            else:
                try:
                    result['prediction'] = parse_response(body, PRICE_MODEL)
                    result['status'] = 'ok'
                except (ValueError, TypeError, KeyError, IndexError):
                    result['prediction'] = None
                    result['status'] = 'invalid_output'
            # The ledger records the full observed estimate even if above the reservation.
            # A missing usage estimate leaves the reservation outstanding at its bound.
            ledger.settle(attempt, actual)
            result['cumulative_accounted_usd'] = str(ledger.accounted())
            append(paths['attempts.jsonl'], result)
            append(paths['journal.jsonl'], {'event': 'finished', 'id': rid, 'attempt_id': attempt,
                                             'status': result['status'], 'raw_sha256': sha(raw)})
            if actual is None:
                reason = 'cost_unknown'
            elif actual > amount:
                reason = 'above_reservation'
            elif result['status'] in ('service_error', 'identity_violation'):
                reason = result['status']
            if reason:
                break
        append(paths['journal.jsonl'], {'event': 'terminal', 'status': 'stopped' if reason else 'complete',
                                         'reason': reason, 'attempted_total': len(already) + len(read_lines(paths['attempts.jsonl']))})
        return {'status': 'stopped' if reason else 'complete', 'reason': reason,
                'attempts': len(read_lines(paths['attempts.jsonl']))}
    finally:
        ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    fr = sub.add_parser('freeze')
    fr.add_argument('--draft', type=Path, required=True)
    fr.add_argument('--review', type=Path, required=True)
    fr.add_argument('--frozen', type=Path, required=True)
    run = sub.add_parser('run')
    run.add_argument('--frozen', type=Path, required=True)
    run.add_argument('--review', type=Path, required=True)
    run.add_argument('--repeat', choices=tuple(study.ORDERS), required=True)
    run.add_argument('--condition', choices=('P0', 'P1', 'P2'), required=True)
    run.add_argument('--phase', choices=('smoke', 'development'), required=True)
    run.add_argument('--stage', type=int, default=0)
    run.add_argument('--env-file', type=Path)
    run.add_argument('--timeout', type=float, default=REQUEST_TIMEOUT)
    args = parser.parse_args()
    if args.command == 'freeze':
        print(json.dumps({'frozen': str(args.frozen), 'sha256': sha(json_bytes(freeze(args.draft, args.review, args.frozen)))}))
    else:
        print(json.dumps(run_stage(frozen_path=args.frozen, phase_review=args.review,
                                   repeat=args.repeat, condition=args.condition,
                                   phase=args.phase, stage=args.stage,
                                   env_file=args.env_file, timeout=args.timeout)))


if __name__ == '__main__':
    main()
