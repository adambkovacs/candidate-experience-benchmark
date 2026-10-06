#!/usr/bin/env python3
"""One-shot Tev native Choice smoke; exact allocation and root receipt required."""
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
from development_benchmark import KEYS, VALUES, valid
import math
from openrouter_paid_benchmark import durable
import openrouter_decision_smoke as native
import openrouter_budget_v4
import paid_budget_partitions_v4 as partitions
import openrouter_authority_release_v4 as authority
import tev_native_v1 as tev

BASE = ROOT / 'results/tev-native-v1'
MASTER = ROOT / 'results/openrouter-paid-budget.jsonl'
AUTHORITY = ROOT / 'results/postapproval-paid-work-2026-10-02.jsonl'
PARTITION_ID = 'tev-native-fresh1-p0-smoke-v1'
REASONING = 'native-decisions-four-choice-P0-smoke'
CAP = Decimal('0.025')
BUDGET = BASE / 'budget-manifest.json'
REVIEW = BASE / 'smoke.root-review.json'
CHILD = BASE / ('budget-manifest-' + PARTITION_ID + '.jsonl')
CATALOG_URL = native.CATALOG_URL.format(model=tev.MODEL)
MAX_BODY = 2_000_000


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def sha_path(path):
    return native.sha(Path(path).read_bytes())


def hold_source(plan_digest, budget_path):
    return native.sha(native.canonical({'kind': 'tev-native-smoke-hold-v1',
                                       'plan_sha256': plan_digest,
                                       'budget_manifest_sha256': sha_path(budget_path),
                                       'partition_id': PARTITION_ID,
                                       'bound_usd': str(tev.SMOKE_BOUND), 'child_cap_usd': str(CAP)}))


def expected_receipt(plan, digest, budget_path):
    return {'kind': 'tev-native-smoke-root-review-v1', 'approved': True,
            'independent_review': True,
            'plan_sha256': digest, 'runner_sha256': plan['source_sha256']['scripts/tev_smoke_v1.py'],
            'budget_manifest_sha256': sha_path(budget_path), 'partition_id': PARTITION_ID,
            'authority_hold_source_sha256': hold_source(digest, budget_path),
            'three_record_bound_usd': str(tev.SMOKE_BOUND),
            'child_cap_usd': str(CAP),
            'smoke_ids': plan['smoke_ids'], 'reference_labels_sent': False}


def verify_review(path, plan, digest, budget_path, base=BASE):
    path = Path(path)
    if path.resolve() != (Path(base) / 'smoke.root-review.json').resolve():
        raise ValueError('Wrong Tev root-review path')
    receipt = json.loads(path.read_text())
    if any(receipt.get(k) != v for k, v in expected_receipt(plan, digest, budget_path).items()):
        raise ValueError('Tev root review differs from frozen plan and allocation')
    if receipt.get('reviewer') != 'root':
        raise ValueError('Root reviewer required')
    return receipt


def exact_budget(budget_path):
    if Path(budget_path).resolve() != BUDGET.resolve():
        raise ValueError('Wrong Tev budget path')
    value = json.loads(BUDGET.read_text())
    expected = {'id': PARTITION_ID, 'cap_usd': str(CAP),
                'child_ledger': str(CHILD.resolve()), 'model': tev.MODEL,
                'provider': tev.PROVIDER, 'reasoning': REASONING}
    if (value.get('version') != 'paid-partitions-v1' or
            value.get('master_ledger') != str(MASTER.resolve()) or
            value.get('partitions') != [expected]):
        raise ValueError('Exact Tev child allocation missing')
    return expected


def verify_hold(digest, budget_path, authority_path=AUTHORITY):
    exact_budget(budget_path)
    with authority.old._locked(authority_path) as handle:
        _, holds, released = authority._scan(handle.read())
    hold = holds.get(PARTITION_ID)
    if (not released or PARTITION_ID in released or not hold or hold.get('version') != 3 or
            hold.get('funding_pool') != 'openrouter_additional' or
            hold.get('usd') != str(CAP) or
            hold.get('source_sha256') != hold_source(digest, budget_path) or
            hold.get('budget_manifest_sha256') != sha_path(budget_path) or
            hold.get('budget_manifest_path') != str(budget_path.resolve()) or
            hold.get('master_path') != str(MASTER.resolve()) or
            hold.get('partition_id') != PARTITION_ID):
        raise ValueError('Exact unreleased Tev v4 authority hold missing')


def fetch_endpoint():
    request = urllib.request.Request(CATALOG_URL, headers={'Accept': 'application/json'}, method='GET')
    with native.OPENER.open(request, timeout=20) as response:
        if response.status != 200:
            raise ValueError('Tev public endpoint lookup failed')
        raw = response.read(MAX_BODY + 1)
    if len(raw) > MAX_BODY:
        raise ValueError('Tev endpoint response too large')
    tev.validate_catalog(json.loads(raw))
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
        raise ValueError('Tev raw response too large; reservation remains unknown')
    return status, raw


def validate_returned(body):
    if not isinstance(body, dict) or body.get('provider') != tev.PROVIDER or body.get('model') != tev.VERSION:
        raise ValueError('Tev returned route mismatch')
    answers = body.get('answers')
    if not isinstance(answers, dict) or set(answers) != set(KEYS):
        raise ValueError('Tev answer keys missing')
    prediction, optional = {}, {}
    for key in KEYS:
        answer = answers[key]
        if not isinstance(answer, dict) or answer.get('type') != 'choice':
            raise ValueError('Tev answer type differs')
        choice = answer.get('choice')
        if not isinstance(choice, str) or choice not in VALUES[key]:
            raise ValueError('Tev Choice label differs')
        prediction[key] = choice
        has_probabilities = 'probabilities' in answer
        has_confidence = 'confidence' in answer
        probabilities = answer.get('probabilities')
        confidence = answer.get('confidence')
        if has_probabilities:
            if (not isinstance(probabilities, dict) or set(probabilities) != set(VALUES[key]) or
                    not all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for v in probabilities.values()) or
                    not math.isclose(sum(probabilities.values()), 1, abs_tol=0.001)):
                raise ValueError('Tev optional probabilities malformed')
        if has_confidence and (type(confidence) not in (int, float) or
                                       not math.isfinite(confidence) or not 0 <= confidence <= 1):
            raise ValueError('Tev optional confidence malformed')
        optional[key] = {'probabilities': probabilities, 'confidence': confidence,
                         'probabilities_available': has_probabilities,
                         'confidence_available': has_confidence}
    if not valid(prediction):
        raise ValueError('Tev categorical output invalid')
    usage = body.get('usage')
    if (not isinstance(usage, dict) or type(usage.get('input_tokens')) is not int or
            not 0 <= usage['input_tokens'] <= tev.QUESTION_COUNT * tev.CONTEXT or
            type(usage.get('output_tokens')) is not int or usage['output_tokens'] < 0):
        raise ValueError('Tev aggregate usage missing or beyond four-question context')
    return prediction, optional


def run(receipt_path, budget_path, *, base=BASE, root=ROOT, master=MASTER,
        authority_path=AUTHORITY, fetch=fetch_endpoint, send=post,
        open_child=partitions.open_partition):
    base, budget_path = Path(base), Path(budget_path)
    if base.resolve() != BASE.resolve() or Path(master).resolve() != MASTER.resolve() or Path(authority_path).resolve() != AUTHORITY.resolve():
        raise ValueError('Tev smoke must use the frozen evidence and ledger paths')
    plan, digest = tev.verify(base, root)
    verify_review(receipt_path, plan, digest, budget_path, base)
    verify_hold(digest, budget_path, authority_path)
    paths = {name: base / ('smoke.' + name) for name in
             ('claim.json', 'journal.jsonl', 'raw.jsonl', 'attempts.jsonl', 'parsed.jsonl')}
    if any(path.exists() for path in paths.values()):
        raise FileExistsError('Tev smoke already claimed; no replay')
    _, route = fetch()
    tev.validate_catalog(route)
    ledger = open_child(master, budget_path, PARTITION_ID, tev.MODEL, tev.PROVIDER, REASONING)
    try:
        if ledger.master_cap != openrouter_budget_v4.CAP or ledger.cap != CAP:
            raise ValueError('OpenRouter master cap changed')
        _, pending, blocked = ledger.state()
        if pending or blocked or ledger.closed or ledger.accounted() + tev.SMOKE_BOUND > ledger.cap:
            raise ValueError('Tev child cannot cover all three full-context requests')
        token = os.environ.get('OPENROUTER_API_KEY')
        if not token:
            raise ValueError('OPENROUTER_API_KEY required in process environment')
        with paths['claim.json'].open('x') as out:
            durable(out, {'kind': 'tev-native-smoke-claim-v1', 'plan_sha256': digest,
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
                    tev.verify(base, root)
                    route_raw, route = fetch()
                    tev.validate_catalog(route)
                    if native.sha(native.canonical(item['payload'])) != item['payload_sha256']:
                        raise ValueError('Tev request payload drift')
                    if ledger.accounted() + tev.BOUND > ledger.cap:
                        raise ValueError('Tev child lacks request reserve')
                    durable(journal, {'event': 'request_intent', 'id': rid,
                                      'payload_sha256': item['payload_sha256'], 'utc': now()})
                    attempt = ledger.reserve(tev.BOUND, rid)
                    durable(journal, {'event': 'request_started', 'id': rid, 'attempt_id': attempt,
                                      'live_endpoint_sha256': native.sha(route_raw),
                                      'live_endpoint_base64': base64.b64encode(route_raw).decode('ascii'), 'utc': now()})
                    started, t0 = now(), time.perf_counter_ns()
                    try:
                        status, wire = send(item['payload'], token)
                    except BaseException as error:
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'transport_error',
                                           'error_type': type(error).__name__, 'cost_unknown': True,
                                           'reserved_cost_usd': str(tev.BOUND), 'utc': now()})
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
                    try:
                        actual = native.response_cost(body)
                    except (ValueError, TypeError, ArithmeticError):
                        actual = None
                    if actual is None:
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'unknown_cost',
                                           'http_status': status, 'cost_unknown': True,
                                           'reserved_cost_usd': str(tev.BOUND)})
                        raise ValueError('Tev cost unknown; full reservation retained')
                    if not ledger.settle(attempt, actual):
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'over_bound',
                                           'http_status': status, 'actual_cost_usd': str(actual)})
                        raise ValueError('Tev observed cost exceeded reserve')
                    if status != 200:
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'http_error',
                                           'http_status': status, 'actual_cost_usd': str(actual)})
                        raise ValueError('Tev provider HTTP error; no retry')
                    try:
                        prediction, optional = validate_returned(body)
                    except (ValueError, TypeError):
                        durable(attempts, {'id': rid, 'attempt_id': attempt, 'status': 'invalid_native_response',
                                           'actual_cost_usd': str(actual)})
                        raise
                    durable(parsed, {'id': rid, 'attempt_id': attempt, 'prediction': prediction, 'optional': optional,
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
