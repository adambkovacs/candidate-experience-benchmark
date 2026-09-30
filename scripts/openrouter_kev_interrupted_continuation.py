#!/usr/bin/env python3
"""Receipt-gated Kev fresh3 continuation for never-sent DEV-027..060 only.

The original DEV-026 timeout remains an unknown-cost attempted position. This
controller never resends it and never declares a clean third 60-record pass.
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
import openrouter_decision_development as first
import openrouter_decision_repeats as repeat
import openrouter_decision_smoke as smoke

BASE = ROOT / 'results/route-audits/kev-fresh3-continuation-20260930'
REPEAT_BASE = repeat.BASE
ORIGINAL_DIR = repeat.pass_dir(REPEAT_BASE, 3)
ROUTE = first.ROUTE
ORIGINAL_PASS_ID = repeat.PASSES[3]
PASS_ID = 'kev-openrouter-native-p0-fresh3-tail-DEV027-060'
START = 27
END = 60
COUNT = END - START + 1
UNKNOWN_ID = 'DEV-026'
ORIGINAL_ATTEMPTS_SUFFIX = (ORIGINAL_DIR / 'attempts.jsonl').relative_to(ROOT).parts


def matches_original_evidence_path(recorded_path, current_path):
    """Bind the historical ledger path by project-relative identity across exports."""
    if not isinstance(recorded_path, str) or not recorded_path:
        return False
    recorded = Path(recorded_path)
    current = Path(current_path)
    suffix_size = len(ORIGINAL_ATTEMPTS_SUFFIX)
    return (recorded.is_absolute() and current.is_absolute() and
            '..' not in recorded.parts and '..' not in current.parts and
            recorded.parts[-suffix_size:] == ORIGINAL_ATTEMPTS_SUFFIX and
            current.parts[-suffix_size:] == ORIGINAL_ATTEMPTS_SUFFIX)


def inspect_prefix(original, original_dir=ORIGINAL_DIR, ledger_path=LEDGER_PATH):
    original_dir = Path(original_dir)
    attempts_path = original_dir / 'attempts.jsonl'
    audit_path = original_dir / 'interruption-audit.json'
    receipt_path = original_dir / 'root-review.json'
    if (original_dir / 'completion.json').exists():
        raise ValueError('Original fresh3 unexpectedly has a completion')
    receipt = json.loads(receipt_path.read_text())
    repeat.validate_receipt(receipt, original)
    attempt_bytes = attempts_path.read_bytes()
    rows = [json.loads(line) for line in attempt_bytes.decode().splitlines() if line.strip()]
    audit = json.loads(audit_path.read_text())
    tail_ids = [f'DEV-{index:03}' for index in range(START, END + 1)]
    if (len(rows) != 25 * 3 + 2 or audit.get('kind') != 'openrouter-kev-native-interruption-audit-v1' or
        audit.get('pass_id') != ORIGINAL_PASS_ID or audit.get('status') != 'stopped_transport_unknown' or
        audit.get('attempts_sha256') != smoke.sha(attempt_bytes) or
        audit.get('attempted_count') != 26 or audit.get('valid_count') != 25 or
        audit.get('unknown_record_id') != UNKNOWN_ID or audit.get('never_sent_ids') != tail_ids or
        audit.get('retry_performed') is not False or audit.get('reference_labels_read') is not False or
        audit.get('full_pass_complete') is not False or audit.get('unknown_actual_cost_usd') is not None or
        number(audit.get('unknown_upper_bound_usd')) != smoke.bound(ROUTE) or
        audit.get('observed_exit_code') != 1):
        raise ValueError('Interrupted-prefix audit differs')
    ledger_events = [json.loads(line) for line in Path(ledger_path).read_text().splitlines() if line.strip()]
    reservations = [event for event in ledger_events if event.get('event') == 'reserve' and
                    isinstance(event.get('record_id'), str) and
                    event['record_id'].startswith(ORIGINAL_PASS_ID + ':')]
    if len(reservations) != 26 or [event['record_id'] for event in reservations] != [
            ORIGINAL_PASS_ID + ':DEV-' + f'{index:03}' for index in range(1, 27)]:
        raise ValueError('Original ledger includes missing, duplicate or later attempts')
    total = Decimal(0)
    for index in range(25):
        expected = original['requests'][index]
        reserved, response, validated = rows[3*index:3*index+3]
        attempt_id = reserved.get('ledger_attempt_id')
        if (not isinstance(attempt_id, str) or not attempt_id or
            [row.get('stage') for row in (reserved, response, validated)] != ['reserved', 'response', 'validated'] or
            any(row.get('id') != expected['id'] for row in (reserved, response, validated)) or
            response.get('attempt_id') != attempt_id or validated.get('attempt_id') != attempt_id or
            reserved.get('payload_sha256') != expected['payload_sha256'] or
            number(reserved.get('reserved_cost_usd')) != smoke.bound(ROUTE) or
            number(response.get('reserved_cost_usd')) != smoke.bound(ROUTE) or
            response.get('http_status') != 200 or response.get('cost_unknown') is not False or
            response.get('parse_error_type') is not None or validated.get('cost_unknown') is not False or
            type(response.get('client_request_elapsed_ns')) is not int or response['client_request_elapsed_ns'] < 0):
            raise ValueError('Validated original-prefix attempt differs')
        raw = base64.b64decode(response['raw_response_base64'], validate=True)
        body = json.loads(raw)
        if (smoke.sha(raw) != response.get('raw_response_sha256') or
            len(raw) != response.get('raw_response_size_bytes') or body != response.get('body') or
            smoke.validate_response(body, ROUTE) != validated.get('prediction')):
            raise ValueError('Original-prefix raw native response differs')
        cost = smoke.response_cost(body)
        if cost is None or cost != number(response.get('actual_cost_usd')) or cost > smoke.bound(ROUTE):
            raise ValueError('Original-prefix reported cost differs')
        reserve_events = [event for event in ledger_events if event.get('event') == 'reserve' and event.get('attempt_id') == attempt_id]
        settle_events = [event for event in ledger_events if event.get('event') == 'settle' and event.get('attempt_id') == attempt_id]
        if (len(reserve_events) != 1 or len(settle_events) != 1 or
            reserve_events[0] != reservations[index] or
            number(reserve_events[0].get('usd')) != smoke.bound(ROUTE) or
            number(settle_events[0].get('usd')) != cost):
            raise ValueError('Original-prefix shared-ledger settlement differs')
        total += cost
    reserved26, error26 = rows[-2:]
    unknown_attempt = audit.get('unknown_attempt_id')
    if (not isinstance(unknown_attempt, str) or not unknown_attempt or
        reserved26.get('stage') != 'reserved' or error26.get('stage') != 'transport_error' or
        reserved26.get('id') != UNKNOWN_ID or error26.get('id') != UNKNOWN_ID or
        reserved26.get('ledger_attempt_id') != unknown_attempt or error26.get('attempt_id') != unknown_attempt or
        reserved26.get('payload_sha256') != original['requests'][25]['payload_sha256'] or
        number(reserved26.get('reserved_cost_usd')) != smoke.bound(ROUTE) or
        number(error26.get('reserved_cost_usd')) != smoke.bound(ROUTE) or
        reserved26.get('cost_unknown') is not True or error26.get('cost_unknown') is not True or
        error26.get('error_type') != 'TimeoutError' or
        type(error26.get('client_request_elapsed_ns')) is not int or error26['client_request_elapsed_ns'] < 0):
        raise ValueError('Original DEV-026 unknown attempt differs')
    reserve26_events = [event for event in ledger_events if event.get('event') == 'reserve' and event.get('attempt_id') == unknown_attempt]
    settle26_events = [event for event in ledger_events if event.get('event') == 'settle' and event.get('attempt_id') == unknown_attempt]
    unknown_events = [event for event in ledger_events if event.get('event') == 'unknown_cost_accounted_as_upper_bound' and
                      event.get('attempt_id') == unknown_attempt]
    if (len(reserve26_events) != 1 or reserve26_events[0] != reservations[25] or
        number(reserve26_events[0].get('usd')) != smoke.bound(ROUTE) or settle26_events or
        len(unknown_events) != 1 or number(unknown_events[0].get('usd')) != smoke.bound(ROUTE) or
        unknown_events[0].get('actual_cost_usd') is not None or
        not matches_original_evidence_path(unknown_events[0].get('evidence_path'), attempts_path) or
        unknown_events[0].get('evidence_sha256') != smoke.sha(attempt_bytes) or
        number(audit.get('known_actual_cost_usd')) != total):
        raise ValueError('Original unknown-charge retention or known cost differs')
    return {'original_manifest_sha256': smoke.sha(smoke.canonical(original)),
            'original_review_sha256': smoke.sha(receipt_path.read_bytes()),
            'original_attempts_sha256': smoke.sha(attempt_bytes),
            'interruption_audit_sha256': smoke.sha(audit_path.read_bytes()),
            'unknown_accounting_event_sha256': smoke.sha(smoke.canonical(unknown_events[0])),
            'prefix_valid_count': 25, 'prefix_known_actual_cost_usd': str(total),
            'unknown_record_id': UNKNOWN_ID, 'unknown_attempt_id': unknown_attempt,
            'unknown_actual_cost_usd': None,
            'unknown_upper_bound_usd': str(smoke.bound(ROUTE)),
            'never_sent_ids': tail_ids}


def build_manifest(original, proof):
    tail_ids = [f'DEV-{index:03}' for index in range(START, END + 1)]
    requests = original['requests'][START-1:END]
    if (proof.get('never_sent_ids') != tail_ids or [row.get('id') for row in requests] != tail_ids or
        proof.get('original_manifest_sha256') != smoke.sha(smoke.canonical(original))):
        raise ValueError('Continuation membership or source differs')
    return {'kind': 'openrouter-kev-interrupted-fresh3-tail-preparation-v1',
            'pass_id': PASS_ID, 'original_pass_id': ORIGINAL_PASS_ID,
            'status': 'prepared_offline_only', 'inference_performed': False,
            'reference_labels_read': False, 'record_count': COUNT,
            'start_id': tail_ids[0], 'end_id': tail_ids[-1],
            'model': ROUTE['model'], 'expected_returned_model': ROUTE['version'],
            'provider_tag': ROUTE['tag'], 'expected_returned_provider': ROUTE['provider'],
            'per_request_bound_usd': str(smoke.bound(ROUTE)),
            'tail_bound_usd': str(COUNT * smoke.bound(ROUTE)),
            'controller_sha256': smoke.sha((ROOT / 'scripts/openrouter_kev_interrupted_continuation.py').read_bytes()),
            'repeat_controller_sha256': smoke.sha((ROOT / 'scripts/openrouter_decision_repeats.py').read_bytes()),
            'smoke_runner_sha256': smoke.sha((ROOT / 'scripts/openrouter_decision_smoke.py').read_bytes()),
            'jev_adapter_sha256': smoke.sha((ROOT / 'scripts/jev_benchmark.py').read_bytes()),
            'base_ledger_sha256': smoke.sha((ROOT / 'scripts/openrouter_paid_benchmark.py').read_bytes()),
            'master_ledger_sha256': smoke.sha((ROOT / 'scripts/openrouter_budget_v2.py').read_bytes()),
            'interruption_proof': proof, 'requests': requests,
            'interpretation': 'Never-sent DEV-027..060 tail only; DEV-026 remains attempted with unknown actual cost. Completion is not a clean 60-record third pass.'}


def prepare(base=BASE, repeat_base=REPEAT_BASE, first_base=first.BASE, ledger_path=LEDGER_PATH):
    original = repeat.load_frozen(3, repeat_base, first_base, ledger_path)
    proof = inspect_prefix(original, repeat.pass_dir(repeat_base, 3), ledger_path)
    manifest = build_manifest(original, proof)
    Path(base).mkdir(parents=True, exist_ok=True)
    with (Path(base) / 'manifest.json').open('x') as output:
        output.write(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    return smoke.sha(smoke.canonical(manifest))


def load_prepared(base=BASE, repeat_base=REPEAT_BASE, first_base=first.BASE, ledger_path=LEDGER_PATH):
    original = repeat.load_frozen(3, repeat_base, first_base, ledger_path)
    proof = inspect_prefix(original, repeat.pass_dir(repeat_base, 3), ledger_path)
    saved = json.loads((Path(base) / 'manifest.json').read_text())
    if saved != build_manifest(original, proof):
        raise ValueError('Continuation manifest differs from immutable interrupted evidence')
    return saved


def validate_receipt(receipt, manifest):
    if not isinstance(receipt, dict) or receipt.get('approved') is not True:
        raise ValueError('Separate reviewed tail receipt required')
    if not isinstance(receipt.get('reviewer'), str) or not receipt['reviewer'].strip():
        raise ValueError('Receipt must name reviewer')
    if (receipt.get('pass_id') != PASS_ID or
        receipt.get('manifest_sha256') != smoke.sha(smoke.canonical(manifest)) or
        receipt.get('start_id') != 'DEV-027' or receipt.get('end_id') != 'DEV-060' or
        receipt.get('record_count') != COUNT or
        receipt.get('max_reservation_usd') != manifest['tail_bound_usd']):
        raise ValueError('Receipt does not bind exact never-sent tail and bound')


def execute(receipt_path, base=BASE, repeat_base=REPEAT_BASE,
            first_base=first.BASE, ledger_path=LEDGER_PATH):
    manifest = load_prepared(base, repeat_base, first_base, ledger_path)
    validate_receipt(json.loads(Path(receipt_path).read_text()), manifest)
    smoke.validate_endpoint(smoke.fetch_catalog(ROUTE), ROUTE)
    token = os.environ.get('OPENROUTER_API_KEY')
    if not token:
        raise ValueError('OPENROUTER_API_KEY required in process environment')
    if not Path(ledger_path).is_file() or not Path(ledger_path).stat().st_size:
        raise ValueError('Existing shared master ledger required')
    attempts_path = Path(base) / 'attempts.jsonl'
    completion_path = Path(base) / 'completion.json'
    if attempts_path.exists() or completion_path.exists():
        raise FileExistsError('Tail already started or completed; no automatic retry')
    ledger = BudgetLedger(ledger_path)
    try:
        _, pending, blocked = ledger.state()
        if pending or blocked or ledger.closed or any(part['active'] for part in ledger.partitions.values()):
            raise ValueError('Master ledger not idle')
        if ledger.accounted() + COUNT * smoke.bound(ROUTE) > ledger.cap:
            raise ValueError('Whole 34-record tail bound exceeds current master cap headroom')
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
        if validated_ids != [f'DEV-{index:03}' for index in range(START, END + 1)]:
            raise ValueError('Tail did not validate all never-sent records in order')
        completion = {'kind': 'openrouter-kev-interrupted-fresh3-tail-completion-v1',
            'status': 'interrupted_series_tail_closed_not_clean_third_pass',
            'pass_id': PASS_ID, 'record_count': COUNT, 'tail_valid_count': COUNT,
            'original_prefix_valid_count': 25, 'original_unknown_record_id': UNKNOWN_ID,
            'original_unknown_attempt_id': manifest['interruption_proof']['unknown_attempt_id'],
            'original_unknown_actual_cost_usd': None,
            'original_unknown_upper_bound_usd': manifest['interruption_proof']['unknown_upper_bound_usd'],
            'combined_observed_valid_count': 25 + COUNT,
            'clean_full_third_pass_complete': False,
            'manifest_sha256': smoke.sha(smoke.canonical(manifest)),
            'attempts_sha256': smoke.sha(attempts_path.read_bytes()),
            'tail_known_actual_cost_usd': str(known_cost),
            'inference_performed': True, 'reference_labels_read': False}
        with completion_path.open('x') as output:
            durable(output, completion)
    finally:
        ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('prepare', help='Freeze never-sent DEV-027..060 only; no inference')
    sub.add_parser('verify', help='Reconcile prefix and frozen tail offline; no inference')
    live = sub.add_parser('execute', help='Execute one separately reviewed 34-record tail')
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
