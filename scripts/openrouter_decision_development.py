#!/usr/bin/env python3
"""Receipt-gated first 60-record Kev native Decisions pass through OpenRouter.

Preparation and verification are offline. Execution is one fresh P0 pass only,
with no retry, continuation, cap increase, or repeat-series admission.
"""
import argparse
import base64
from decimal import Decimal
import json
import os
from pathlib import Path
import time

from development_benchmark import ROOT, read_rows
from openrouter_paid_benchmark import LEDGER_PATH, durable, number, validate_rows
from openrouter_budget_v2 import BudgetLedger
import openrouter_decision_smoke as smoke

BASE = ROOT / 'results/route-audits/decision-kev-development-20260930'
SMOKE_BASE = smoke.BASE
PASS_ID = 'kev-openrouter-native-p0-fresh1'
ROUTE = smoke.ROUTES['kev']
COUNT = 60


def build_plan():
    per_pass = str(COUNT * smoke.bound(ROUTE))
    return {'kind': 'openrouter-kev-native-three-pass-plan-v1',
            'model': ROUTE['model'], 'provider_tag': ROUTE['tag'],
            'interface': smoke.DECISIONS_URL, 'condition': 'native P0 Choice',
            'record_ids': [f'DEV-{index:03}' for index in range(1, COUNT + 1)],
            'pass_bound_usd': per_pass,
            'three_pass_catalog_bound_usd': str(3 * COUNT * smoke.bound(ROUTE)),
            'passes': [
                {'pass_id': PASS_ID, 'ordinal': 1, 'status': 'prepared_separately; review_required'},
                {'pass_id': 'kev-openrouter-native-p0-fresh2', 'ordinal': 2,
                 'status': 'pending_separate_manifest_review_and_funding'},
                {'pass_id': 'kev-openrouter-native-p0-fresh3', 'ordinal': 3,
                 'status': 'pending_separate_manifest_review_and_funding'},
            ],
            'funding_rule': 'Recheck locked shared $10 master headroom per pass after prior actual settlement; this plan does not fund or admit all three.',
            'native_prompt_comparisons': {
                'P1_equivalent': 'design_pending; candidate native criteria/policy variant requires a declared request transform and comparability review',
                'P2_equivalent': 'design_pending; candidate native criteria/policy variant requires a declared request transform and comparability review'},
            'chat_role_note': 'Native Decisions accepts questions and state rather than chat role messages; lack of system-message field does not exclude native policy/criteria variants.',
            'reference_labels_in_requests': False,
            'no_inference_authorized_by_plan': True}


def inspect_smoke(smoke_base=SMOKE_BASE, ledger_path=LEDGER_PATH):
    prepared = smoke.load_prepared(smoke_base)
    receipt_path = smoke_base / 'kev-root-review.json'
    attempts_path = smoke_base / 'kev-attempts.jsonl'
    receipt = json.loads(receipt_path.read_text())
    smoke.validate_receipt(receipt, prepared, 'kev')
    rows = [json.loads(line) for line in attempts_path.read_text().splitlines() if line.strip()]
    if len(rows) != 9:
        raise ValueError('Kev smoke must have exactly three complete attempt triplets')
    ids = ['DEV-001', 'DEV-002', 'DEV-003']
    ledger_events = [json.loads(line) for line in Path(ledger_path).read_text().splitlines() if line.strip()]
    total = Decimal(0)
    proof = []
    for index, record_id in enumerate(ids):
        reserved, response, validated = rows[3*index:3*index+3]
        attempt_id = reserved.get('ledger_attempt_id')
        expected_payload = prepared['routes']['kev']['requests'][index]
        if (not isinstance(attempt_id, str) or not attempt_id or
            [row.get('stage') for row in (reserved, response, validated)] != ['reserved', 'response', 'validated'] or
            any(row.get('id') != record_id for row in (reserved, response, validated)) or
            response.get('attempt_id') != attempt_id or validated.get('attempt_id') != attempt_id or
            reserved.get('payload_sha256') != expected_payload['payload_sha256'] or
            response.get('http_status') != 200 or response.get('cost_unknown') is not False or
            validated.get('cost_unknown') is not False):
            raise ValueError('Kev smoke attempt structure or identity differs')
        raw = base64.b64decode(response['raw_response_base64'], validate=True)
        body = json.loads(raw)
        if (smoke.sha(raw) != response.get('raw_response_sha256') or
            len(raw) != response.get('raw_response_size_bytes') or body != response.get('body') or
            smoke.validate_response(body, ROUTE) != validated.get('prediction')):
            raise ValueError('Kev smoke raw native response differs')
        cost = smoke.response_cost(body)
        if cost is None or cost != number(response.get('actual_cost_usd')) or cost > smoke.bound(ROUTE):
            raise ValueError('Kev smoke cost differs')
        reserves = [event for event in ledger_events if event.get('event') == 'reserve' and event.get('attempt_id') == attempt_id]
        settles = [event for event in ledger_events if event.get('event') == 'settle' and event.get('attempt_id') == attempt_id]
        if (len(reserves) != 1 or len(settles) != 1 or
            reserves[0].get('record_id') != 'kev:' + record_id or
            number(reserves[0].get('usd')) != smoke.bound(ROUTE) or number(settles[0].get('usd')) != cost):
            raise ValueError('Kev smoke shared-ledger accounting differs')
        total += cost
        proof.append({'id': record_id, 'attempt_id': attempt_id,
                      'raw_response_sha256': smoke.sha(raw), 'actual_cost_usd': str(cost)})
    return {'smoke_manifest_sha256': smoke.sha(smoke.canonical(prepared)),
            'smoke_receipt_sha256': smoke.sha(receipt_path.read_bytes()),
            'smoke_attempts_sha256': smoke.sha(attempts_path.read_bytes()),
            'smoke_cost_usd': str(total), 'smoke_attempts': proof}


def build_manifest(catalog, smoke_proof, plan):
    smoke.validate_endpoint(catalog, ROUTE)
    if plan != build_plan():
        raise ValueError('Native three-pass plan differs')
    rows = validate_rows(read_rows(ROOT / 'data/pilot/inputs.jsonl'))
    policy = smoke.policy_text()
    requests = []
    for row in rows:
        payload = smoke.request_payload(row['feedback'], policy, ROUTE)
        requests.append({'id': row['id'], 'input_sha256': smoke.sha(row['feedback'].encode()),
                         'payload_sha256': smoke.sha(smoke.canonical(payload)), 'payload': payload})
    return {'kind': 'openrouter-kev-native-decisions-p0-fresh1-preparation-v1',
            'pass_id': PASS_ID, 'status': 'prepared_offline', 'inference_performed': False,
            'reference_labels_read': False, 'record_count': COUNT,
            'api_url': smoke.DECISIONS_URL, 'model': ROUTE['model'],
            'expected_returned_model': ROUTE['version'], 'provider_tag': ROUTE['tag'],
            'expected_returned_provider': ROUTE['provider'],
            'per_request_bound_usd': str(smoke.bound(ROUTE)),
            'pass_bound_usd': str(COUNT * smoke.bound(ROUTE)),
            'policy_sha256': smoke.sha(policy.encode()),
            'inputs_sha256': smoke.sha((ROOT / 'data/pilot/inputs.jsonl').read_bytes()),
            'controller_sha256': smoke.sha((ROOT / 'scripts/openrouter_decision_development.py').read_bytes()),
            'smoke_runner_sha256': smoke.sha((ROOT / 'scripts/openrouter_decision_smoke.py').read_bytes()),
            'jev_adapter_sha256': smoke.sha((ROOT / 'scripts/jev_benchmark.py').read_bytes()),
            'development_source_sha256': smoke.sha((ROOT / 'scripts/development_benchmark.py').read_bytes()),
            'base_ledger_sha256': smoke.sha((ROOT / 'scripts/openrouter_paid_benchmark.py').read_bytes()),
            'master_ledger_sha256': smoke.sha((ROOT / 'scripts/openrouter_budget_v2.py').read_bytes()),
            'catalog_snapshot_sha256': smoke.sha(smoke.canonical(catalog)),
            'native_plan_sha256': smoke.sha(smoke.canonical(plan)),
            'smoke_proof': smoke_proof, 'requests': requests}


def prepare(base=BASE, smoke_base=SMOKE_BASE, ledger_path=LEDGER_PATH):
    proof = inspect_smoke(smoke_base, ledger_path)
    catalog = json.loads((smoke_base / 'kev-endpoint.json').read_text())
    plan = build_plan()
    manifest = build_manifest(catalog, proof, plan)
    base.mkdir(parents=True, exist_ok=True)
    with (base / 'native-plan.json').open('x') as output:
        output.write(json.dumps(plan, indent=2) + '\n')
    with (base / 'manifest.json').open('x') as output:
        output.write(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    return smoke.sha(smoke.canonical(manifest))


def load_prepared(base=BASE, smoke_base=SMOKE_BASE, ledger_path=LEDGER_PATH):
    saved = json.loads((base / 'manifest.json').read_text())
    plan = json.loads((base / 'native-plan.json').read_text())
    proof = inspect_smoke(smoke_base, ledger_path)
    catalog = json.loads((smoke_base / 'kev-endpoint.json').read_text())
    rebuilt = build_manifest(catalog, proof, plan)
    if saved != rebuilt:
        raise ValueError('Prepared Kev development manifest differs from sources or closed smoke')
    return saved


def validate_receipt(receipt, manifest):
    if not isinstance(receipt, dict) or receipt.get('approved') is not True:
        raise ValueError('Separate reviewed development receipt required')
    if not isinstance(receipt.get('reviewer'), str) or not receipt['reviewer'].strip():
        raise ValueError('Receipt must name reviewer')
    if (receipt.get('pass_id') != PASS_ID or
        receipt.get('manifest_sha256') != smoke.sha(smoke.canonical(manifest)) or
        receipt.get('max_reservation_usd') != manifest['pass_bound_usd'] or
        receipt.get('record_count') != COUNT):
        raise ValueError('Receipt does not bind exact Kev first pass and bound')


def execute(receipt_path, base=BASE, smoke_base=SMOKE_BASE, ledger_path=LEDGER_PATH):
    manifest = load_prepared(base, smoke_base, ledger_path)
    validate_receipt(json.loads(Path(receipt_path).read_text()), manifest)
    live_catalog = smoke.fetch_catalog(ROUTE)
    smoke.validate_endpoint(live_catalog, ROUTE)
    token = os.environ.get('OPENROUTER_API_KEY')
    if not token:
        raise ValueError('OPENROUTER_API_KEY required in process environment')
    if not Path(ledger_path).is_file() or not Path(ledger_path).stat().st_size:
        raise ValueError('Existing shared master ledger required')
    attempts_path = base / 'attempts.jsonl'
    completion_path = base / 'completion.json'
    if attempts_path.exists() or completion_path.exists():
        raise FileExistsError('Kev first pass already started or completed; no automatic retry')
    ledger = BudgetLedger(ledger_path)
    try:
        _, pending, blocked = ledger.state()
        if pending or blocked or ledger.closed or any(p['active'] for p in ledger.partitions.values()):
            raise ValueError('Master ledger not idle')
        if ledger.accounted() + COUNT * smoke.bound(ROUTE) > ledger.cap:
            raise ValueError('Full Kev first-pass bound exceeds current master cap headroom')
        known_cost = Decimal(0)
        validated_ids = []
        with attempts_path.open('x') as attempts:
            for item in manifest['requests']:
                attempt_id = ledger.reserve(smoke.bound(ROUTE), PASS_ID + ':' + item['id'])
                durable(attempts, {'stage': 'reserved', 'ledger_attempt_id': attempt_id,
                    'id': item['id'], 'payload_sha256': item['payload_sha256'],
                    'reserved_cost_usd': str(smoke.bound(ROUTE)), 'cost_unknown': True})
                started_utc = smoke.utc_now()
                started_ns = time.monotonic_ns()
                try:
                    status, raw = smoke.post(item['payload'], token)
                except BaseException as error:
                    elapsed_ns = time.monotonic_ns() - started_ns
                    durable(attempts, {'stage': 'transport_error', 'attempt_id': attempt_id,
                        'id': item['id'], 'error_type': type(error).__name__,
                        'request_start_utc': started_utc, 'request_end_utc': smoke.utc_now(),
                        'client_request_elapsed_ns': elapsed_ns,
                        'reserved_cost_usd': str(smoke.bound(ROUTE)), 'cost_unknown': True})
                    raise
                elapsed_ns = time.monotonic_ns() - started_ns
                ended_utc = smoke.utc_now()
                try:
                    body = json.loads(raw)
                    parse_error = None
                except (ValueError, UnicodeDecodeError) as error:
                    body = None
                    parse_error = type(error).__name__
                actual = smoke.response_cost(body)
                durable(attempts, {'stage': 'response', 'attempt_id': attempt_id, 'id': item['id'],
                    'http_status': status, 'body': body, 'parse_error_type': parse_error,
                    'raw_response_base64': base64.b64encode(raw).decode('ascii'),
                    'raw_response_sha256': smoke.sha(raw), 'raw_response_size_bytes': len(raw),
                    'request_start_utc': started_utc, 'request_end_utc': ended_utc,
                    'client_request_elapsed_ns': elapsed_ns,
                    'reserved_cost_usd': str(smoke.bound(ROUTE)), 'cost_unknown': actual is None,
                    'actual_cost_usd': str(actual) if actual is not None else None})
                if actual is None:
                    raise ValueError('Unknown provider cost; reservation remains pending')
                if not ledger.settle(attempt_id, actual):
                    raise ValueError('Actual cost exceeded reserved bound; master ledger blocked')
                known_cost += actual
                if status != 200:
                    raise ValueError('Provider returned non-200 response; no retry')
                prediction = smoke.validate_response(body, ROUTE)
                durable(attempts, {'stage': 'validated', 'attempt_id': attempt_id,
                    'id': item['id'], 'prediction': prediction, 'cost_unknown': False})
                validated_ids.append(item['id'])
        if validated_ids != [f'DEV-{index:03}' for index in range(1, COUNT+1)]:
            raise ValueError('Kev first pass did not validate all 60 ordered records')
        completion = {'kind': 'openrouter-kev-native-decisions-p0-fresh1-completion-v1',
            'pass_id': PASS_ID, 'record_count': COUNT, 'valid_count': COUNT,
            'manifest_sha256': smoke.sha(smoke.canonical(manifest)),
            'attempts_sha256': smoke.sha(attempts_path.read_bytes()),
            'known_actual_cost_usd': str(known_cost),
            'inference_performed': True, 'reference_labels_read': False}
        with completion_path.open('x') as output:
            durable(output, completion)
    finally:
        ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('prepare', help='Freeze all 60 input-only requests; no inference')
    sub.add_parser('verify', help='Rebuild manifest from sources and closed smoke; no inference')
    live = sub.add_parser('execute', help='One reviewed 60-record Kev first pass')
    live.add_argument('--review-receipt', required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        print(prepare())
    elif args.command == 'verify':
        print(smoke.sha(smoke.canonical(load_prepared())))
    else:
        execute(args.review_receipt)


if __name__ == '__main__':
    main()
