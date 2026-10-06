#!/usr/bin/env python3
"""One-shot Liquid native Choice smoke; exact allocation and root receipt required."""
import argparse
import base64
from datetime import datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request

from development_benchmark import ROOT
from jev_benchmark import parse_response
from openrouter_paid_benchmark import durable
import openrouter_decision_smoke as native
import openrouter_budget_v4
import paid_budget_partitions_v4 as partitions
import postapproval_authority_v3 as authority
import liquid_d1_native_v1 as liquid

BASE = ROOT / 'results/liquid-d1-native-v1'
MASTER = ROOT / 'results/openrouter-paid-budget.jsonl'
AUTHORITY = ROOT / 'results/postapproval-paid-work-2026-10-02.jsonl'
PARTITION_ID = 'liquid-d1-native-fresh1-p0-smoke-v1'
REASONING = 'native-decisions-P0-smoke'
CATALOG_URL = native.CATALOG_URL.format(model=liquid.MODEL)
MAX_BODY = 2_000_000


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def sha_path(path):
    return native.sha(Path(path).read_bytes())


def hold_source(plan_digest, budget_path):
    return native.sha(native.canonical({'kind': 'liquid-d1-native-smoke-hold-v1',
                                       'plan_sha256': plan_digest,
                                       'budget_manifest_sha256': sha_path(budget_path),
                                       'partition_id': PARTITION_ID,
                                       'bound_usd': str(liquid.SMOKE_BOUND)}))


def expected_receipt(plan, digest, budget_path):
    return {'kind': 'liquid-d1-native-smoke-root-review-v1', 'approved': True,
            'plan_sha256': digest, 'runner_sha256': plan['source_sha256']['scripts/liquid_d1_smoke_v1.py'],
            'budget_manifest_sha256': sha_path(budget_path), 'partition_id': PARTITION_ID,
            'authority_hold_source_sha256': hold_source(digest, budget_path),
            'three_record_bound_usd': str(liquid.SMOKE_BOUND),
            'smoke_ids': plan['smoke_ids'], 'reference_labels_sent': False}


def verify_review(path, plan, digest, budget_path, base=BASE):
    path = Path(path)
    if path.resolve() != (Path(base) / 'smoke.root-review.json').resolve():
        raise ValueError('Wrong Liquid root-review path')
    receipt = json.loads(path.read_text())
    if any(receipt.get(k) != v for k, v in expected_receipt(plan, digest, budget_path).items()):
        raise ValueError('Liquid root review differs from frozen plan and allocation')
    if not isinstance(receipt.get('reviewer'), str) or not receipt['reviewer'].strip():
        raise ValueError('Named reviewer required')
    return receipt


def verify_hold(digest, budget_path, authority_path=AUTHORITY):
    with authority.old._locked(authority_path) as handle:
        _, holds = authority._scan(handle.read())
        hold = holds.get(PARTITION_ID)
        if (not hold or hold.get('version') != 3 or hold.get('funding_pool') != 'openrouter_additional' or
                hold.get('usd') != str(liquid.SMOKE_BOUND) or
                hold.get('source_sha256') != hold_source(digest, budget_path) or
                hold.get('budget_manifest_sha256') != sha_path(budget_path) or
                hold.get('budget_manifest_path') != str(budget_path.resolve()) or
                hold.get('master_path') != str(MASTER.resolve()) or
                hold.get('partition_id') != PARTITION_ID):
            raise ValueError('Exact additional OpenRouter authority hold missing')


def fetch_endpoint():
    request = urllib.request.Request(CATALOG_URL, headers={'Accept': 'application/json'}, method='GET')
    with native.OPENER.open(request, timeout=20) as response:
        if response.status != 200:
            raise ValueError('Liquid public endpoint lookup failed')
        raw = response.read(MAX_BODY + 1)
    if len(raw) > MAX_BODY:
        raise ValueError('Liquid endpoint response too large')
    liquid.validate_catalog(json.loads(raw))
    return raw, json.loads(raw)


def post(payload, token):
    request = urllib.request.Request(native.DECISIONS_URL, data=native.canonical(payload), method='POST',
                                     headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token})
    try:
        with native.OPENER.open(request, timeout=60) as response:
            status, raw = response.status, response.read(MAX_BODY + 1)
    except urllib.error.HTTPError as error:
        status, raw = error.code, error.read(MAX_BODY + 1)
    if len(raw) > MAX_BODY:
        raise ValueError('Liquid raw response too large; reservation remains unknown')
    return status, raw


def validate_returned(body):
    if not isinstance(body, dict) or body.get('provider') != liquid.PROVIDER:
        raise ValueError('Liquid returned provider mismatch')
    prediction = parse_response(body, liquid.VERSION)
    usage = body.get('usage')
    if (not isinstance(usage, dict) or type(usage.get('input_tokens')) is not int or
            not 0 <= usage['input_tokens'] <= liquid.QUESTION_COUNT * liquid.CONTEXT or
            type(usage.get('output_tokens')) is not int or usage['output_tokens'] < 0):
        raise ValueError('Liquid aggregate usage missing or beyond four-question context')
    return prediction


def run(receipt_path, budget_path, *, base=BASE, root=ROOT, master=MASTER,
        authority_path=AUTHORITY, fetch=fetch_endpoint, send=post,
        open_child=partitions.open_partition):
    base, budget_path = Path(base), Path(budget_path)
    plan, digest = liquid.verify(base, root)
    verify_review(receipt_path, plan, digest, budget_path, base)
    verify_hold(digest, budget_path, authority_path)
    paths = {name: base / ('smoke.' + name) for name in
             ('claim.json', 'journal.jsonl', 'raw.jsonl', 'attempts.jsonl', 'parsed.jsonl')}
    if any(path.exists() for path in paths.values()):
        raise FileExistsError('Liquid smoke already claimed; no replay')
    _, route = fetch()
    liquid.validate_catalog(route)
    ledger = open_child(master, budget_path, PARTITION_ID, liquid.MODEL, liquid.PROVIDER, REASONING)
    try:
        if ledger.master_cap != openrouter_budget_v4.CAP:
            raise ValueError('OpenRouter master cap changed')
        _, pending, blocked = ledger.state()
        if pending or blocked or ledger.closed or ledger.accounted() + liquid.SMOKE_BOUND > ledger.cap:
            raise ValueError('Liquid child cannot cover all three full-context requests')
        token = os.environ.get('OPENROUTER_API_KEY')
        if not token:
            raise ValueError('OPENROUTER_API_KEY required in process environment')
        with paths['claim.json'].open('x') as out:
            durable(out, {'kind': 'liquid-d1-native-smoke-claim-v1', 'plan_sha256': digest,
                          'root_review_sha256': sha_path(receipt_path),
                          'budget_manifest_sha256': sha_path(budget_path),
                          'claimed_utc': now(), 'reference_labels_sent': False})
        phase = next(p for p in plan['phases'] if p['id'] == 'fresh1/P0')
        with paths['journal.jsonl'].open('x') as journal, paths['raw.jsonl'].open('x') as raw_file, \
                paths['attempts.jsonl'].open('x') as attempts, paths['parsed.jsonl'].open('x') as parsed:
            durable(journal, {'event': 'stage_started', 'utc': now(), 'plan_sha256': digest})
            for item in phase['requests'][:3]:
                rid = item['id']
                try:
                    liquid.verify(base, root)
                    verify_hold(digest, budget_path, authority_path)
                    route_raw, route = fetch()
                    liquid.validate_catalog(route)
                    if native.sha(native.canonical(item['payload'])) != item['payload_sha256']:
                        raise ValueError('Liquid request payload drift')
                    if ledger.accounted() + liquid.BOUND > ledger.cap:
                        raise ValueError('Liquid child lacks request reserve')
                    durable(journal, {'event': 'request_intent', 'id': rid,
                                      'payload_sha256': item['payload_sha256'], 'utc': now()})
                    attempt = ledger.reserve(liquid.BOUND, rid)
                    durable(journal, {'event': 'request_started', 'id': rid, 'attempt_id': attempt,
                                      'live_endpoint_sha256': native.sha(route_raw),
                                      'live_endpoint_base64': base64.b64encode(route_raw).decode('ascii'), 'utc': now()})
                    started, t0 = now(), time.perf_counter_ns()
                    try:
                        status, wire = send(item['payload'], token)
                    except BaseException as error:
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'transport_error',
                                           'error_type': type(error).__name__, 'cost_unknown': True,
                                           'reserved_cost_usd': str(liquid.BOUND), 'utc': now()})
                        raise
                    ended, elapsed = now(), time.perf_counter_ns() - t0
                    durable(raw_file, {'id': rid, 'attempt_id': attempt, 'payload_sha256': item['payload_sha256'],
                                       'http_status': status, 'response_sha256': native.sha(wire),
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
                                           'reserved_cost_usd': str(liquid.BOUND)})
                        raise ValueError('Liquid cost unknown; full reservation retained')
                    if not ledger.settle(attempt, actual):
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'over_bound',
                                           'http_status': status, 'actual_cost_usd': str(actual)})
                        raise ValueError('Liquid observed cost exceeded reserve')
                    if status != 200:
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'http_error',
                                           'http_status': status, 'actual_cost_usd': str(actual)})
                        raise ValueError('Liquid provider HTTP error; no retry')
                    try:
                        prediction = validate_returned(body)
                    except ValueError:
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'invalid_native_response',
                                           'actual_cost_usd': str(actual)})
                        raise
                    durable(parsed, {'id': rid, 'attempt_id': attempt, 'prediction': prediction,
                                     'actual_cost_usd': str(actual)})
                    durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'ok',
                                       'actual_cost_usd': str(actual), 'cost_unknown': False})
                except BaseException as error:
                    durable(journal, {'event': 'stage_stopped', 'id': rid,
                                      'error_type': type(error).__name__, 'utc': now()})
                    raise
            durable(journal, {'event': 'stage_completed', 'utc': now(), 'count': 3})
    finally:
        ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('run',))
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--budget', type=Path, required=True)
    args = parser.parse_args()
    run(args.receipt, args.budget)


if __name__ == '__main__':
    main()
