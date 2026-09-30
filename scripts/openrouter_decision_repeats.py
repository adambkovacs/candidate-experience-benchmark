#!/usr/bin/env python3
"""Separate Kev native P0 fresh2/fresh3 candidates and receipt-gated execution.

Candidate preparation is offline. A pass can be frozen only after its actual
predecessor has 60 reconciled native responses, known settlements and a bound
completion. No candidate or plan grants inference authorization.
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
import openrouter_decision_development as first
import openrouter_decision_smoke as smoke

BASE = ROOT / 'results/route-audits/decision-kev-repeats-20260930'
FIRST_BASE = first.BASE
ROUTE = first.ROUTE
COUNT = 60
PASSES = {2: 'kev-openrouter-native-p0-fresh2',
          3: 'kev-openrouter-native-p0-fresh3'}


def pass_dir(base, ordinal):
    if ordinal not in PASSES:
        raise ValueError('Only Kev native P0 fresh2/fresh3 are supported')
    return Path(base) / ('fresh' + str(ordinal))


def load_first_static(first_base=FIRST_BASE):
    saved = json.loads((Path(first_base) / 'manifest.json').read_text())
    plan = json.loads((Path(first_base) / 'native-plan.json').read_text())
    rows = validate_rows(read_rows(ROOT / 'data/pilot/inputs.jsonl'))
    policy = smoke.policy_text()
    expected = [{'id': row['id'], 'input_sha256': smoke.sha(row['feedback'].encode()),
                 'payload_sha256': smoke.sha(smoke.canonical(smoke.request_payload(row['feedback'], policy, ROUTE))),
                 'payload': smoke.request_payload(row['feedback'], policy, ROUTE)} for row in rows]
    if (plan != first.build_plan() or saved.get('native_plan_sha256') != smoke.sha(smoke.canonical(plan)) or
        saved.get('pass_id') != first.PASS_ID or saved.get('record_count') != COUNT or
        saved.get('pass_bound_usd') != str(COUNT * smoke.bound(ROUTE)) or
        saved.get('model') != ROUTE['model'] or saved.get('provider_tag') != ROUTE['tag'] or
        saved.get('requests') != expected or
        saved.get('controller_sha256') != smoke.sha((ROOT / 'scripts/openrouter_decision_development.py').read_bytes()) or
        saved.get('smoke_runner_sha256') != smoke.sha((ROOT / 'scripts/openrouter_decision_smoke.py').read_bytes()) or
        saved.get('jev_adapter_sha256') != smoke.sha((ROOT / 'scripts/jev_benchmark.py').read_bytes()) or
        saved.get('development_source_sha256') != smoke.sha((ROOT / 'scripts/development_benchmark.py').read_bytes()) or
        saved.get('base_ledger_sha256') != smoke.sha((ROOT / 'scripts/openrouter_paid_benchmark.py').read_bytes()) or
        saved.get('master_ledger_sha256') != smoke.sha((ROOT / 'scripts/openrouter_budget_v2.py').read_bytes()) or
        saved.get('policy_sha256') != smoke.sha(policy.encode()) or
        saved.get('inputs_sha256') != smoke.sha((ROOT / 'data/pilot/inputs.jsonl').read_bytes())):
        raise ValueError('Frozen first-pass source, plan or request bytes differ')
    return saved


def build_candidate(ordinal, first_manifest):
    if ordinal not in PASSES:
        raise ValueError('Unknown successor pass')
    return {'kind': 'openrouter-kev-native-p0-repeat-candidate-v1',
            'admission_ready': False, 'inference_performed': False,
            'reference_labels_read': False, 'ordinal': ordinal,
            'pass_id': PASSES[ordinal],
            'predecessor_pass_id': first.PASS_ID if ordinal == 2 else PASSES[2],
            'condition': 'native P0 Choice', 'record_count': COUNT,
            'model': ROUTE['model'], 'expected_returned_model': ROUTE['version'],
            'provider_tag': ROUTE['tag'], 'expected_returned_provider': ROUTE['provider'],
            'per_request_bound_usd': str(smoke.bound(ROUTE)),
            'pass_bound_usd': str(COUNT * smoke.bound(ROUTE)),
            'first_manifest_sha256': smoke.sha(smoke.canonical(first_manifest)),
            'native_plan_sha256': first_manifest['native_plan_sha256'],
            'repeat_controller_sha256': smoke.sha((ROOT / 'scripts/openrouter_decision_repeats.py').read_bytes()),
            'shared_budget_sha256': smoke.sha((ROOT / 'scripts/openrouter_budget_v2.py').read_bytes()),
            'base_budget_sha256': smoke.sha((ROOT / 'scripts/openrouter_paid_benchmark.py').read_bytes()),
            'smoke_runner_sha256': smoke.sha((ROOT / 'scripts/openrouter_decision_smoke.py').read_bytes()),
            'first_controller_sha256': smoke.sha((ROOT / 'scripts/openrouter_decision_development.py').read_bytes()),
            'requests': first_manifest['requests']}


def prepare_candidates(base=BASE, first_base=FIRST_BASE):
    first_manifest = load_first_static(first_base)
    result = {}
    for ordinal in PASSES:
        directory = pass_dir(base, ordinal)
        directory.mkdir(parents=True, exist_ok=True)
        candidate = build_candidate(ordinal, first_manifest)
        with (directory / 'candidate.json').open('x') as output:
            output.write(json.dumps(candidate, indent=2, ensure_ascii=False) + '\n')
        result[PASSES[ordinal]] = smoke.sha(smoke.canonical(candidate))
    return result


def load_candidate(ordinal, base=BASE, first_base=FIRST_BASE):
    saved = json.loads((pass_dir(base, ordinal) / 'candidate.json').read_text())
    expected = build_candidate(ordinal, load_first_static(first_base))
    if saved != expected:
        raise ValueError('Successor candidate differs from frozen first-pass wire source')
    return saved


def validate_receipt(receipt, manifest):
    if not isinstance(receipt, dict) or receipt.get('approved') is not True:
        raise ValueError('Separate reviewed successor receipt required')
    if not isinstance(receipt.get('reviewer'), str) or not receipt['reviewer'].strip():
        raise ValueError('Receipt must name reviewer')
    if (receipt.get('pass_id') != manifest['pass_id'] or
        receipt.get('manifest_sha256') != smoke.sha(smoke.canonical(manifest)) or
        receipt.get('max_reservation_usd') != manifest['pass_bound_usd'] or
        receipt.get('record_count') != COUNT):
        raise ValueError('Receipt does not bind exact successor pass and bound')


def inspect_finished(manifest, directory, ledger_path, receipt_validator):
    directory = Path(directory)
    receipt_path = directory / 'root-review.json'
    attempts_path = directory / 'attempts.jsonl'
    completion_path = directory / 'completion.json'
    receipt = json.loads(receipt_path.read_text())
    receipt_validator(receipt, manifest)
    attempt_bytes = attempts_path.read_bytes()
    rows = [json.loads(line) for line in attempt_bytes.decode().splitlines() if line.strip()]
    completion = json.loads(completion_path.read_text())
    if (len(rows) != 3 * COUNT or completion.get('pass_id') != manifest['pass_id'] or
        completion.get('manifest_sha256') != smoke.sha(smoke.canonical(manifest)) or
        completion.get('attempts_sha256') != smoke.sha(attempt_bytes) or
        completion.get('record_count') != COUNT or completion.get('valid_count') != COUNT or
        completion.get('inference_performed') is not True or
        completion.get('reference_labels_read') is not False):
        raise ValueError('Predecessor lacks exact terminal 60-record completion')
    ledger_events = [json.loads(line) for line in Path(ledger_path).read_text().splitlines() if line.strip()]
    total = Decimal(0)
    for index, expected in enumerate(manifest['requests']):
        reserved, response, validated = rows[index*3:index*3+3]
        attempt_id = reserved.get('ledger_attempt_id')
        record_id = expected['id']
        if (not isinstance(attempt_id, str) or not attempt_id or
            [row.get('stage') for row in (reserved, response, validated)] != ['reserved', 'response', 'validated'] or
            any(row.get('id') != record_id for row in (reserved, response, validated)) or
            response.get('attempt_id') != attempt_id or validated.get('attempt_id') != attempt_id or
            reserved.get('payload_sha256') != expected['payload_sha256'] or
            number(reserved.get('reserved_cost_usd')) != smoke.bound(ROUTE) or
            number(response.get('reserved_cost_usd')) != smoke.bound(ROUTE) or
            response.get('http_status') != 200 or response.get('cost_unknown') is not False or
            response.get('parse_error_type') is not None or
            validated.get('cost_unknown') is not False or
            type(response.get('client_request_elapsed_ns')) is not int or
            response['client_request_elapsed_ns'] < 0 or
            not isinstance(response.get('request_start_utc'), str) or
            not isinstance(response.get('request_end_utc'), str)):
            raise ValueError('Predecessor attempt order or timing differs')
        raw = base64.b64decode(response['raw_response_base64'], validate=True)
        body = json.loads(raw)
        if (smoke.sha(raw) != response.get('raw_response_sha256') or
            len(raw) != response.get('raw_response_size_bytes') or
            body != response.get('body') or
            smoke.validate_response(body, ROUTE) != validated.get('prediction')):
            raise ValueError('Predecessor native raw response differs')
        cost = smoke.response_cost(body)
        if cost is None or cost != number(response.get('actual_cost_usd')) or cost > smoke.bound(ROUTE):
            raise ValueError('Predecessor cost differs')
        reserves = [event for event in ledger_events if event.get('event') == 'reserve' and event.get('attempt_id') == attempt_id]
        settles = [event for event in ledger_events if event.get('event') == 'settle' and event.get('attempt_id') == attempt_id]
        if (len(reserves) != 1 or len(settles) != 1 or
            reserves[0].get('record_id') != manifest['pass_id'] + ':' + record_id or
            number(reserves[0].get('usd')) != smoke.bound(ROUTE) or
            number(settles[0].get('usd')) != cost):
            raise ValueError('Predecessor shared-ledger settlement differs')
        total += cost
    if number(completion.get('known_actual_cost_usd')) != total:
        raise ValueError('Predecessor completion cost differs')
    return {'predecessor_pass_id': manifest['pass_id'],
            'predecessor_manifest_sha256': smoke.sha(smoke.canonical(manifest)),
            'predecessor_review_sha256': smoke.sha(receipt_path.read_bytes()),
            'predecessor_attempts_sha256': smoke.sha(attempt_bytes),
            'predecessor_completion_sha256': smoke.sha(completion_path.read_bytes()),
            'predecessor_actual_cost_usd': str(total)}


def predecessor_proof(ordinal, base=BASE, first_base=FIRST_BASE, ledger_path=LEDGER_PATH):
    if ordinal == 2:
        manifest = load_first_static(first_base)
        return inspect_finished(manifest, first_base, ledger_path, first.validate_receipt)
    if ordinal == 3:
        manifest = load_frozen(2, base, first_base, ledger_path)
        return inspect_finished(manifest, pass_dir(base, 2), ledger_path, validate_receipt)
    raise ValueError('Unknown successor pass')


def build_frozen(candidate, proof):
    if candidate.get('admission_ready') is not False or proof.get('predecessor_pass_id') != candidate['predecessor_pass_id']:
        raise ValueError('Candidate or predecessor identity differs')
    return {'kind': 'openrouter-kev-native-p0-repeat-execution-v1',
            'admission_ready': True, 'candidate_sha256': smoke.sha(smoke.canonical(candidate)),
            'predecessor_proof': proof, **{key: value for key, value in candidate.items()
                                          if key not in ('kind', 'admission_ready')}}


def freeze(ordinal, base=BASE, first_base=FIRST_BASE, ledger_path=LEDGER_PATH):
    candidate = load_candidate(ordinal, base, first_base)
    proof = predecessor_proof(ordinal, base, first_base, ledger_path)
    manifest = build_frozen(candidate, proof)
    with (pass_dir(base, ordinal) / 'manifest.json').open('x') as output:
        output.write(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    return smoke.sha(smoke.canonical(manifest))


def load_frozen(ordinal, base=BASE, first_base=FIRST_BASE, ledger_path=LEDGER_PATH):
    saved = json.loads((pass_dir(base, ordinal) / 'manifest.json').read_text())
    expected = build_frozen(load_candidate(ordinal, base, first_base),
                            predecessor_proof(ordinal, base, first_base, ledger_path))
    if saved != expected:
        raise ValueError('Frozen successor manifest differs from candidate or terminal predecessor')
    return saved


def execute(ordinal, receipt_path, base=BASE, first_base=FIRST_BASE, ledger_path=LEDGER_PATH):
    manifest = load_frozen(ordinal, base, first_base, ledger_path)
    validate_receipt(json.loads(Path(receipt_path).read_text()), manifest)
    smoke.validate_endpoint(smoke.fetch_catalog(ROUTE), ROUTE)
    token = os.environ.get('OPENROUTER_API_KEY')
    if not token:
        raise ValueError('OPENROUTER_API_KEY required in process environment')
    if not Path(ledger_path).is_file() or not Path(ledger_path).stat().st_size:
        raise ValueError('Existing shared master ledger required')
    directory = pass_dir(base, ordinal)
    attempts_path = directory / 'attempts.jsonl'
    completion_path = directory / 'completion.json'
    if attempts_path.exists() or completion_path.exists():
        raise FileExistsError('Successor pass already started or completed; no automatic retry')
    ledger = BudgetLedger(ledger_path)
    try:
        _, pending, blocked = ledger.state()
        if pending or blocked or ledger.closed or any(part['active'] for part in ledger.partitions.values()):
            raise ValueError('Master ledger not idle')
        if ledger.accounted() + COUNT * smoke.bound(ROUTE) > ledger.cap:
            raise ValueError('Whole successor pass bound exceeds current master cap headroom')
        known_cost = Decimal(0)
        validated_ids = []
        with attempts_path.open('x') as attempts:
            for item in manifest['requests']:
                attempt_id = ledger.reserve(smoke.bound(ROUTE), manifest['pass_id'] + ':' + item['id'])
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
        if validated_ids != [f'DEV-{index:03}' for index in range(1, COUNT + 1)]:
            raise ValueError('Successor pass did not validate all ordered records')
        completion = {'kind': 'openrouter-kev-native-decisions-p0-fresh' + str(ordinal) + '-completion-v1',
            'pass_id': manifest['pass_id'], 'record_count': COUNT, 'valid_count': COUNT,
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
    sub.add_parser('prepare-candidates', help='Create unadmitted fresh2/fresh3 input-only candidates')
    verify = sub.add_parser('verify-candidate', help='Offline candidate/source verification')
    verify.add_argument('--pass', dest='ordinal', type=int, choices=(2, 3), required=True)
    freeze_cmd = sub.add_parser('freeze', help='Freeze after predecessor terminal reconciliation; no inference')
    freeze_cmd.add_argument('--pass', dest='ordinal', type=int, choices=(2, 3), required=True)
    live = sub.add_parser('execute', help='Execute one separately reviewed successor pass')
    live.add_argument('--pass', dest='ordinal', type=int, choices=(2, 3), required=True)
    live.add_argument('--review-receipt', required=True)
    args = parser.parse_args()
    if args.command == 'prepare-candidates':
        print(json.dumps(prepare_candidates(), sort_keys=True))
    elif args.command == 'verify-candidate':
        print(smoke.sha(smoke.canonical(load_candidate(args.ordinal))))
    elif args.command == 'freeze':
        print(freeze(args.ordinal))
    else:
        execute(args.ordinal, args.review_receipt)


if __name__ == '__main__':
    main()
