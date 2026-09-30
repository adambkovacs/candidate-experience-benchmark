#!/usr/bin/env python3
"""Receipt-gated OpenRouter native P1/P2 smoke and full passes.

Execution is deliberately absent from the prepared plans. A separate root
review receipt, current endpoint identity, and locked whole-pass budget check
are required for every stage. This module never reads reference labels.
"""
import argparse
import base64
from decimal import Decimal
import json
import os
from pathlib import Path
import time

from development_benchmark import ROOT
from openrouter_paid_benchmark import LEDGER_PATH, durable, number
from openrouter_budget_v2 import BudgetLedger
import openrouter_decision_smoke as smoke
import openrouter_native_variants_plan as plan

BASE = ROOT / 'results/route-audits/native-variants-offline-20260930'
STAGES = ('smoke', 'fresh1', 'fresh2', 'fresh3')


def stage_dir(base, configuration_id, stage):
    if stage not in STAGES:
        raise ValueError('Unknown declared native stage')
    return Path(base) / configuration_id / stage


def load_manifest(configuration_id, base=BASE, root=ROOT):
    expected = plan.build_plan(root)
    if configuration_id not in expected:
        raise ValueError('Unknown declared native configuration')
    path = Path(base) / (configuration_id + '.json')
    manifest = expected[configuration_id]
    if path.read_bytes() != (json.dumps(manifest, indent=2, ensure_ascii=False) + '\n').encode():
        raise ValueError('Prepared native manifest differs from frozen sources')
    if manifest['status'] != 'prepared_not_admitted' or manifest['admission']['execution_authorized'] is not False:
        raise ValueError('Unexpected plan admission state')
    return manifest


def stage_id(manifest, stage):
    if stage == 'smoke':
        return manifest['configuration_id'] + '-smoke'
    for entry in manifest['passes']:
        if entry['pass_id'] == manifest['configuration_id'] + '-' + stage:
            return entry['pass_id']
    raise ValueError('Pass absent from frozen manifest')


def expected_items(manifest, stage):
    return manifest['requests'][:3] if stage == 'smoke' else manifest['requests']


def _event_pair(ledger_events, attempt_id, record_id, amount, actual):
    reserves = [e for e in ledger_events if e.get('event') == 'reserve' and e.get('attempt_id') == attempt_id]
    settles = [e for e in ledger_events if e.get('event') == 'settle' and e.get('attempt_id') == attempt_id]
    if (len(reserves) != 1 or len(settles) != 1 or
            reserves[0].get('record_id') != record_id or
            number(reserves[0].get('usd')) != amount or number(settles[0].get('usd')) != actual):
        raise ValueError('Stage evidence differs from shared-ledger accounting')


def inspect_completed(manifest, stage, base=BASE, ledger_path=LEDGER_PATH):
    """Reconcile exact raw requests, responses, parsing and ledger settlements."""
    directory = stage_dir(base, manifest['configuration_id'], stage)
    attempts_path = directory / 'attempts.jsonl'
    completion_path = directory / 'completion.json'
    review_path = directory / 'review-receipt.json'
    catalog_path = directory / 'endpoint-catalog.json'
    raw_attempts = attempts_path.read_bytes()
    raw_review = review_path.read_bytes()
    raw_catalog = catalog_path.read_bytes()
    rows = [json.loads(line) for line in raw_attempts.decode().splitlines() if line.strip()]
    completion = json.loads(completion_path.read_text())
    items = expected_items(manifest, stage)
    sid = stage_id(manifest, stage)
    if (len(rows) != 4 * len(items) or completion.get('kind') != 'openrouter-native-variant-stage-completion-v1' or
            completion.get('stage_id') != sid or completion.get('record_count') != len(items) or
            completion.get('valid_count') != len(items) or
            completion.get('manifest_sha256') != smoke.sha(smoke.canonical(manifest)) or
            completion.get('attempts_sha256') != smoke.sha(raw_attempts) or
            completion.get('review_receipt_sha256') != smoke.sha(raw_review) or
            completion.get('endpoint_catalog_sha256') != smoke.sha(raw_catalog) or
            completion.get('reference_labels_read') is not False):
        raise ValueError('Stage lacks exact terminal completion')
    validate_receipt(json.loads(raw_review), manifest, stage,
                     predecessor_proof(manifest, stage, base, ledger_path))
    ledger_events = [json.loads(line) for line in Path(ledger_path).read_text().splitlines() if line.strip()]
    route = smoke.ROUTES[manifest['route']]
    smoke.validate_endpoint(json.loads(raw_catalog), route)
    amount = smoke.bound(route)
    known = Decimal(0)
    for index, item in enumerate(items):
        reserved, started, response, parsed = rows[4 * index:4 * index + 4]
        attempt_id = reserved.get('ledger_attempt_id')
        if (not isinstance(attempt_id, str) or not attempt_id or
                [e.get('stage') for e in (reserved, started, response, parsed)] !=
                ['reserved', 'started', 'response', 'parsed'] or
                any(e.get('id') != item['id'] for e in (reserved, started, response, parsed)) or
                any(e.get('attempt_id') != attempt_id for e in (started, response, parsed)) or
                reserved.get('payload_sha256') != item['payload_sha256'] or
                started.get('request_sha256') != item['payload_sha256'] or
                number(reserved.get('reserved_cost_usd')) != amount or
                started.get('request_start_utc') != response.get('request_start_utc') or
                response.get('http_status') != 200 or response.get('cost_unknown') is not False or
                parsed.get('valid') is not True):
            raise ValueError('Stage attempt structure differs')
        if base64.b64decode(started['request_base64'], validate=True) != smoke.canonical(item['payload']):
            raise ValueError('Stage exact request bytes differ')
        raw = base64.b64decode(response['raw_response_base64'], validate=True)
        body = json.loads(raw)
        if (smoke.sha(raw) != response.get('raw_response_sha256') or
                len(raw) != response.get('raw_response_size_bytes') or
                body != response.get('body') or
                smoke.validate_response(body, route) != parsed.get('prediction')):
            raise ValueError('Stage raw/native response differs')
        actual = smoke.response_cost(body)
        if actual is None or actual > amount or number(response.get('actual_cost_usd')) != actual:
            raise ValueError('Stage actual cost differs')
        _event_pair(ledger_events, attempt_id, sid + ':' + item['id'], amount, actual)
        known += actual
    if number(completion.get('known_actual_cost_usd')) != known:
        raise ValueError('Stage completion cost differs')
    return {'stage_id': sid, 'manifest_sha256': smoke.sha(smoke.canonical(manifest)),
            'review_receipt_sha256': smoke.sha(raw_review),
            'endpoint_catalog_sha256': smoke.sha(raw_catalog),
            'attempts_sha256': smoke.sha(raw_attempts),
            'completion_sha256': smoke.sha(completion_path.read_bytes()),
            'known_actual_cost_usd': str(known)}


def predecessor_proof(manifest, stage, base=BASE, ledger_path=LEDGER_PATH):
    if stage == 'smoke':
        return None
    smoke_proof = inspect_completed(manifest, 'smoke', base, ledger_path)
    if stage == 'fresh1':
        return {'smoke': smoke_proof}
    previous = STAGES[STAGES.index(stage) - 1]
    return {'smoke': smoke_proof, 'previous_pass': inspect_completed(manifest, previous, base, ledger_path)}


def validate_receipt(receipt, manifest, stage, proof):
    route = smoke.ROUTES[manifest['route']]
    expected = {'approved': True, 'reviewer': receipt.get('reviewer'),
                'stage_id': stage_id(manifest, stage),
                'manifest_sha256': smoke.sha(smoke.canonical(manifest)),
                'runner_sha256': smoke.sha(Path(__file__).read_bytes()),
                'whole_pass_bound_usd': str(60 * smoke.bound(route)),
                'stage_bound_usd': str(len(expected_items(manifest, stage)) * smoke.bound(route)),
                'predecessor_proof': proof}
    if (not isinstance(receipt.get('reviewer'), str) or not receipt['reviewer'].strip() or
            receipt != expected):
        raise ValueError('Separate reviewed stage receipt required')


def execute(configuration_id, stage, receipt_path, *, base=BASE, root=ROOT,
            ledger_path=LEDGER_PATH, catalog_fetch=smoke.fetch_catalog,
            transport=smoke.post, ledger_factory=BudgetLedger, token=None):
    """Dispatch exactly one reviewed stage; there is no retry or resume path."""
    if stage not in STAGES:
        raise ValueError('Unknown native stage')
    manifest = load_manifest(configuration_id, base, root)
    route = smoke.ROUTES[manifest['route']]
    proof = predecessor_proof(manifest, stage, base, ledger_path)
    receipt = json.loads(Path(receipt_path).read_text())
    raw_receipt = Path(receipt_path).read_bytes()
    validate_receipt(receipt, manifest, stage, proof)
    live_catalog = catalog_fetch(route)
    smoke.validate_endpoint(live_catalog, route)
    catalog_bytes = smoke.canonical(live_catalog)
    token = os.environ.get('OPENROUTER_API_KEY') if token is None else token
    if not token:
        raise ValueError('OPENROUTER_API_KEY required')
    ledger_path = Path(ledger_path)
    if not ledger_path.is_file() or not ledger_path.stat().st_size:
        raise ValueError('Existing shared master ledger required')
    directory = stage_dir(base, configuration_id, stage)
    if directory.exists():
        raise FileExistsError('Native stage already started or completed; no retry')
    ledger = ledger_factory(ledger_path)
    try:
        _, pending, blocked = ledger.state()
        if pending or blocked or ledger.closed or any(p['active'] for p in ledger.partitions.values()):
            raise ValueError('Master ledger not idle')
        whole_pass_bound = 60 * smoke.bound(route)
        if ledger.accounted() + whole_pass_bound > ledger.cap:
            raise ValueError('Whole-pass bound exceeds current master cap headroom')
        directory.parent.mkdir(parents=True, exist_ok=True)
        directory.mkdir(parents=True, exist_ok=False)
        with (directory / 'review-receipt.json').open('xb') as review_copy:
            review_copy.write(raw_receipt)
            review_copy.flush()
            os.fsync(review_copy.fileno())
        with (directory / 'endpoint-catalog.json').open('xb') as catalog_copy:
            catalog_copy.write(catalog_bytes)
            catalog_copy.flush()
            os.fsync(catalog_copy.fileno())
        attempts_path = directory / 'attempts.jsonl'
        known_cost = Decimal(0)
        completed = []
        with attempts_path.open('x') as attempts:
            for item in expected_items(manifest, stage):
                sid = stage_id(manifest, stage)
                attempt_id = ledger.reserve(smoke.bound(route), sid + ':' + item['id'])
                durable(attempts, {'stage': 'reserved', 'ledger_attempt_id': attempt_id,
                    'id': item['id'], 'payload_sha256': item['payload_sha256'],
                    'reserved_cost_usd': str(smoke.bound(route)), 'cost_unknown': True})
                started_utc = smoke.utc_now()
                durable(attempts, {'stage': 'started', 'attempt_id': attempt_id,
                    'id': item['id'], 'request_start_utc': started_utc,
                    'request_sha256': item['payload_sha256'],
                    'request_base64': base64.b64encode(smoke.canonical(item['payload'])).decode('ascii'),
                    'cost_unknown': True})
                start_ns = time.monotonic_ns()
                try:
                    status, raw = transport(item['payload'], token)
                except BaseException as error:
                    durable(attempts, {'stage': 'transport_error', 'attempt_id': attempt_id,
                        'id': item['id'], 'error_type': type(error).__name__,
                        'request_end_utc': smoke.utc_now(),
                        'client_request_elapsed_ns': time.monotonic_ns() - start_ns,
                        'reserved_cost_usd': str(smoke.bound(route)), 'cost_unknown': True})
                    raise
                ended_utc = smoke.utc_now()
                elapsed_ns = time.monotonic_ns() - start_ns
                try:
                    body = json.loads(raw)
                    parse_error = None
                except (ValueError, UnicodeDecodeError) as error:
                    body, parse_error = None, type(error).__name__
                actual = smoke.response_cost(body)
                durable(attempts, {'stage': 'response', 'attempt_id': attempt_id, 'id': item['id'],
                    'http_status': status, 'body': body, 'parse_error_type': parse_error,
                    'raw_response_base64': base64.b64encode(raw).decode('ascii'),
                    'raw_response_sha256': smoke.sha(raw), 'raw_response_size_bytes': len(raw),
                    'request_start_utc': started_utc, 'request_end_utc': ended_utc,
                    'client_request_elapsed_ns': elapsed_ns,
                    'reserved_cost_usd': str(smoke.bound(route)), 'cost_unknown': actual is None,
                    'actual_cost_usd': str(actual) if actual is not None else None})
                if actual is None:
                    raise ValueError('Unknown provider cost; reservation remains pending')
                if not ledger.settle(attempt_id, actual):
                    raise ValueError('Actual cost exceeded reserved bound; master ledger blocked')
                known_cost += actual
                if status != 200:
                    durable(attempts, {'stage': 'parsed', 'attempt_id': attempt_id,
                        'id': item['id'], 'valid': False, 'reason': 'non_200_http'})
                    raise ValueError('Provider returned non-200 response; no retry')
                try:
                    prediction = smoke.validate_response(body, route)
                except ValueError as error:
                    durable(attempts, {'stage': 'parsed', 'attempt_id': attempt_id,
                        'id': item['id'], 'valid': False, 'reason': str(error)})
                    raise
                durable(attempts, {'stage': 'parsed', 'attempt_id': attempt_id,
                    'id': item['id'], 'valid': True, 'prediction': prediction})
                completed.append(item['id'])
        if completed != [item['id'] for item in expected_items(manifest, stage)]:
            raise ValueError('Stage lacked ordered valid outputs')
        completion = {'kind': 'openrouter-native-variant-stage-completion-v1',
            'stage_id': stage_id(manifest, stage), 'record_count': len(completed),
            'valid_count': len(completed),
            'manifest_sha256': smoke.sha(smoke.canonical(manifest)),
            'review_receipt_sha256': smoke.sha(raw_receipt),
            'endpoint_catalog_sha256': smoke.sha(catalog_bytes),
            'attempts_sha256': smoke.sha(attempts_path.read_bytes()),
            'known_actual_cost_usd': str(known_cost),
            'inference_performed': True, 'reference_labels_read': False}
        with (directory / 'completion.json').open('x') as output:
            durable(output, completion)
    finally:
        ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--configuration', choices=tuple(plan.build_plan()))
    parser.add_argument('--stage', choices=STAGES, required=True)
    parser.add_argument('--review-receipt', required=True)
    args = parser.parse_args()
    if not args.configuration:
        parser.error('--configuration required')
    execute(args.configuration, args.stage, args.review_receipt)


if __name__ == '__main__':
    main()
