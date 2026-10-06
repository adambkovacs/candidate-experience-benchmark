#!/usr/bin/env python3
"""Reviewed-entrypoint candidate for a new nine-phase Solar native Choice series."""
import argparse
import base64
from datetime import datetime, timezone
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path
import tempfile
import time

from development_benchmark import ROOT
from jev_benchmark import parse_response
from openrouter_paid_benchmark import durable, load_key
import openrouter_decision_smoke as native
import openrouter_authority_release_v4 as authority
import openrouter_budget_v4 as budget_v4
import paid_budget_partitions_v4 as partitions
import solar_decide_native_full_v1 as full
import solar_decide_offline_plan as solar
import solar_decide_risk_hold_v1 as risk
import solar_decide_smoke_v1 as old

BASE = full.BASE / 'execution-adapter-v1'
MANIFEST = BASE / 'manifest.json'
REVIEW = BASE / 'root-review.json'
BUDGET = BASE / 'budget.json'
PARTITION_ID = 'solar-decide-upstage-native-full-v1'
CHILD = BASE / ('budget-' + PARTITION_ID + '.jsonl')
CAP = Decimal('1.00')
BOUND = full.BOUND
REASONING = 'native-decisions-four-choice-new-postinterruption-series'
SCHEMA = 'solar-decide-native-full-execution-v1'
PHASES = full.PHASES
SOURCES = (
    'scripts/solar_decide_native_full_execution_v1.py',
    'tests/test_solar_decide_native_full_execution_v1.py',
    'scripts/solar_decide_native_full_v1.py',
    'tests/test_solar_decide_native_full_v1.py',
    'scripts/solar_decide_offline_plan.py',
    'scripts/solar_decide_smoke_v1.py',
    'scripts/jev_benchmark.py',
    'scripts/openrouter_decision_smoke.py',
    'scripts/openrouter_paid_benchmark.py',
    'scripts/openrouter_benchmark.py',
    'scripts/development_benchmark.py',
    'scripts/openrouter_authority_release_v4.py',
    'scripts/postapproval_authority_v3.py',
    'scripts/postapproval_authority_v2.py',
    'scripts/paid_budget_partitions_v4.py',
    'scripts/paid_budget_partitions_v3.py',
    'scripts/openrouter_budget_v4.py',
    'scripts/openrouter_budget_v3.py',
    'scripts/openrouter_budget_v2.py',
    'scripts/openrouter_budget_amendment_v3.py',
)
ARCHIVED = (
    'results/solar-decide-native-full-v1/plan.json',
    'results/solar-decide-native-smoke-v1/terminal-public.json',
    'results/solar-decide-native-smoke-v1/budget-reconciliation.json',
    'results/solar-decide-risk-hold-v1/risk-hold.claim.json',
    'results/solar-decide-unsent-smoke-v2/execution-adapter-v1/terminal-public.json',
    'results/solar-decide-unsent-smoke-v2/execution-adapter-v1/budget-solar-decide-upstage-p0-unsent-smoke-v2.jsonl',
)


def sha(path):
    return native.sha(Path(path).read_bytes())


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def jsonl(path):
    raw = Path(path).read_bytes()
    if raw and not raw.endswith(b'\n'):
        raise ValueError('Incomplete Solar full JSONL')
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def manifest_value():
    plan_sha = full.verify()
    plan = json.loads(full.PLAN.read_text())
    if (plan['phase_order'] != list(PHASES) or
            plan['historical_smoke_reused_as_passed_three_record_gate'] is not False or
            plan['new_smoke_stage_count'] != 9 or BOUND != Decimal('0.10485760') or
            CAP <= 3 * BOUND):
        raise ValueError('Solar full series stage or reserve changed')
    return {'schema': SCHEMA + '-manifest', 'status': 'offline_unadmitted',
        'inference_authorized': False, 'allocation_authorized': False,
        'configuration_id': plan['configuration_id'],
        'model': solar.MODEL, 'returned_model': solar.VERSION,
        'provider': solar.PROVIDER, 'provider_tag': 'upstage',
        'api_url': native.DECISIONS_URL,
        'frozen_plan_sha256': plan_sha, 'phase_order': list(PHASES),
        'phase_count': 9, 'new_smoke_stage_count': 9,
        'development_stage_count': 9, 'smoke_record_count_per_stage': 3,
        'development_record_count_per_stage': 60,
        'historical_failed_smoke_reused': False,
        'historical_exact_unsent_continuation_reused': False,
        'historical_dev001_unknown_upper_bound_usd': str(risk.OLD_UNKNOWN),
        'separate_historical_risk_hold_usd': str(risk.CAP),
        'question_count': 4, 'context_tokens_per_question': solar.CONTEXT,
        'max_aggregate_billable_input_tokens_per_request': 4 * solar.CONTEXT,
        'per_request_conservative_reserve_usd': str(BOUND),
        'proposed_child_cap_usd': str(CAP),
        'rolling_cap_note': 'Each request reserves the full four-question bound and settles before the next. A $1 child does not guarantee that all 567 worst-case calls fit.',
        'funding_pool': 'openrouter_additional', 'partition_id': PARTITION_ID,
        'request_sets': {p['id']: p['requests_sha256'] for p in plan['phases']},
        'context_limit_note': 'No exact all-record tokenizer proof. Stop on context rejection; never truncate.',
        'provider_failure_policy': 'Stop on provider, transport, unknown-cost, over-bound, or context failure. No retry.',
        'intrinsic_invalid_policy': 'Retain known-cost invalid native output in development denominator and continue; stop a smoke.',
        'source_sha256': {name: sha(ROOT / name) for name in SOURCES},
        'archive_sha256': {name: sha(ROOT / name) for name in ARCHIVED}}


def review_template():
    return {'schema': SCHEMA + '-root-review', 'approved': False,
        'independent_review': False, 'authorized_by_root': False,
        'reviewer': None, 'manifest_sha256': sha(MANIFEST),
        'controller_sha256': sha(__file__), 'partition_id': PARTITION_ID,
        'proposed_child_cap_usd': str(CAP), 'phase_count': 9,
        'first_stage': 'fresh1/P0 smoke', 'historical_smoke_reused': False}


def prepare():
    raw = (json.dumps(manifest_value(), indent=2, sort_keys=True) + '\n').encode()
    digest = native.sha(raw)
    review = {'schema': SCHEMA + '-root-review', 'approved': False,
        'independent_review': False, 'authorized_by_root': False,
        'reviewer': None, 'manifest_sha256': digest,
        'controller_sha256': sha(__file__), 'partition_id': PARTITION_ID,
        'proposed_child_cap_usd': str(CAP), 'phase_count': 9,
        'first_stage': 'fresh1/P0 smoke', 'historical_smoke_reused': False}
    BASE.parent.mkdir(parents=True, exist_ok=True)
    with (BASE.parent / '.solar-full-v1-prepare.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if BASE.exists():
            raise FileExistsError('Solar full adapter already prepared')
        with tempfile.TemporaryDirectory(dir=BASE.parent, prefix='.solar-full-v1-') as temporary:
            stage = Path(temporary)
            (stage / 'manifest.json').write_bytes(raw)
            (stage / 'root-review.json').write_text(json.dumps(review, indent=2, sort_keys=True) + '\n')
            os.rename(stage, BASE)
    return digest


def verify():
    if json.loads(MANIFEST.read_text()) != manifest_value():
        raise ValueError('Solar full manifest, sources, or archive changed')
    return sha(MANIFEST)


def require_review():
    expected = review_template()
    expected.update(approved=True, independent_review=True,
                    authorized_by_root=True, reviewer='root')
    if json.loads(REVIEW.read_text()) != expected:
        raise ValueError('Independent Solar full execution review missing')
    full.require_review()


def exact_budget():
    expected = {'id': PARTITION_ID, 'cap_usd': str(CAP),
        'child_ledger': str(CHILD.resolve()), 'model': solar.MODEL,
        'provider': solar.PROVIDER, 'reasoning': REASONING}
    if json.loads(BUDGET.read_text()) != {'version': 'paid-partitions-v1',
            'master_ledger': str(risk.MASTER.resolve()), 'partitions': [expected]}:
        raise ValueError('Exact Solar full child allocation differs')
    return expected


def hold_source():
    return native.sha(native.canonical({'schema': SCHEMA + '-hold',
        'manifest_sha256': sha(MANIFEST), 'budget_manifest_path': str(BUDGET.resolve()),
        'budget_manifest_sha256': sha(BUDGET), 'partition_id': PARTITION_ID,
        'cap_usd': str(CAP), 'model': solar.MODEL,
        'provider': solar.PROVIDER, 'reasoning': REASONING}))


def verify_hold():
    with authority.old._locked(risk.AUTHORITY) as handle:
        snapshot, holds, released = authority._scan(handle.read())
    hold = holds.get(PARTITION_ID)
    if (PARTITION_ID in released or not hold or hold.get('version') != 3 or
            hold.get('funding_pool') != 'openrouter_additional' or
            hold.get('usd') != str(CAP) or hold.get('source_sha256') != hold_source() or
            hold.get('budget_manifest_path') != str(BUDGET.resolve()) or
            hold.get('budget_manifest_sha256') != sha(BUDGET) or
            hold.get('master_path') != str(risk.MASTER.resolve()) or
            hold.get('partition_id') != PARTITION_ID):
        raise ValueError('Exact active Solar full v4 hold missing')
    return snapshot


def phase(stage):
    if stage not in PHASES:
        raise ValueError('Unknown Solar full stage')
    return next(row for row in json.loads(full.PLAN.read_text())['phases'] if row['id'] == stage)


def stage_paths(stage, mode):
    if stage not in PHASES or mode not in ('smoke', 'development'):
        raise ValueError('Unknown Solar full stage or mode')
    folder = BASE / stage
    return folder, {name: folder / (mode + '.' + name) for name in
                    ('claim.json', 'journal.jsonl', 'raw.jsonl', 'attempts.jsonl',
                     'parsed.jsonl', 'root-review.json')}


def stage_rows(stage, mode):
    requests = phase(stage)['requests']
    return requests[:3] if mode == 'smoke' else requests


def live_route(fetch=old.fetch_endpoint):
    raw, catalog = fetch()
    selected = solar.validate_catalog(catalog)['upstage']
    if (selected.get('tag') != 'upstage' or selected.get('model_id') != solar.MODEL or
            selected.get('provider_name') != solar.PROVIDER):
        raise ValueError('Solar full live route differs')
    return raw, catalog


def checked_body(body):
    if (not isinstance(body, dict) or body.get('model') != solar.VERSION or
            body.get('provider') != solar.PROVIDER):
        raise ValueError('Solar returned model or provider differs')
    usage = body.get('usage')
    if (not isinstance(usage, dict) or type(usage.get('input_tokens')) is not int or
            not 0 <= usage['input_tokens'] <= 4 * solar.CONTEXT or
            type(usage.get('output_tokens')) is not int or usage['output_tokens'] < 0):
        raise ValueError('Solar returned aggregate usage differs')
    cost = native.response_cost(body)
    if cost is None or cost > Decimal(usage['input_tokens']) * solar.PROMPT_RATE:
        raise ValueError('Solar cost exceeds pinned input tariff')
    return usage, cost


def settlement_map():
    events = jsonl(CHILD)
    if events and events[-1].get('event') == 'partition_closed':
        events = events[:-1]
    if (not events or events[0] != {'event': 'budget', 'cap_usd': str(CAP)} or
            len(events[1:]) % 2):
        raise ValueError('Solar full child ledger structure differs')
    settled = {}
    for reserve, settle in zip(events[1::2], events[2::2]):
        aid = reserve.get('attempt_id')
        if (reserve.get('event') != 'reserve' or settle.get('event') != 'settle' or
                settle.get('attempt_id') != aid or aid in settled):
            raise ValueError('Solar full child has pending or duplicate settlement')
        settled[aid] = (reserve, Decimal(settle['usd']))
    return settled


def verify_phase_closure(stage, mode):
    _, paths = stage_paths(stage, mode)
    expected = stage_rows(stage, mode)
    claim = json.loads(paths['claim.json'].read_text())
    journal, raw, attempts, parsed = (jsonl(paths[name]) for name in
        ('journal.jsonl', 'raw.jsonl', 'attempts.jsonl', 'parsed.jsonl'))
    if (claim.get('manifest_sha256') != sha(MANIFEST) or
            claim.get('stage') != stage or claim.get('mode') != mode or
            claim.get('request_set_sha256') != phase(stage)['requests_sha256'] or
            claim.get('root_review_sha256') != sha(paths['root-review.json']) or
            claim.get('reference_labels_sent') is not False or
            len(raw) != len(expected) or len(attempts) != len(expected) or
            len(parsed) != len(expected) or len(journal) != 2 + 3 * len(expected) or
            journal[0].get('event') != 'phase_started' or
            journal[-1].get('event') != 'phase_completed' or
            journal[-1].get('stage') != stage or journal[-1].get('mode') != mode or
            journal[-1].get('request_count') != len(expected)):
        raise ValueError('Solar full phase lifecycle incomplete')
    settled = settlement_map(); invalid = 0
    for index, item in enumerate(expected):
        intent, started, finished = journal[1 + 3 * index:4 + 3 * index]
        record, attempt, output = raw[index], attempts[index], parsed[index]
        aid = started.get('attempt_id')
        if (intent.get('event') != 'request_intent' or
                started.get('event') != 'request_started' or
                finished.get('event') != 'request_finished' or
                any(row.get('id') != item['id'] for row in
                    (intent, started, finished, record, attempt, output)) or
                any(row.get('attempt_id') != aid for row in
                    (finished, record, attempt, output)) or
                any(row.get('payload_sha256') != item['payload_sha256'] for row in
                    (intent, started, record)) or record.get('http_status') != 200 or
                attempt.get('cost_unknown') is not False or
                attempt.get('status') not in ('ok', 'invalid_native') or
                finished.get('status') != attempt['status'] or
                Decimal(finished.get('actual_cost_usd', '-1')) != Decimal(attempt['actual_cost_usd'])):
            raise ValueError('Solar full request identity, order, or outcome differs')
        live = base64.b64decode(started['live_endpoint_base64'], validate=True)
        if (native.sha(live) != started['live_endpoint_sha256'] or
                not solar.validate_catalog(json.loads(live))['upstage']):
            raise ValueError('Solar full route capture differs')
        wire = base64.b64decode(record['response_base64'], validate=True)
        if native.sha(wire) != record['response_sha256']:
            raise ValueError('Solar full raw response differs')
        body = json.loads(wire); usage, cost = checked_body(body)
        saved = settled.get(aid)
        if (not saved or saved[0].get('record_id') != stage + ':' + mode + ':' + item['id'] or
                Decimal(saved[0]['usd']) != BOUND or saved[1] != cost or
                Decimal(attempt['actual_cost_usd']) != cost or
                Decimal(output['actual_cost_usd']) != cost or
                output.get('usage') != usage):
            raise ValueError('Solar full cost, usage, or settlement differs')
        try:
            prediction = parse_response(body, solar.VERSION)
        except (ValueError, TypeError):
            if (mode == 'smoke' or attempt['status'] != 'invalid_native' or
                    output.get('prediction') is not None):
                raise ValueError('Solar invalid native response not retained honestly')
            invalid += 1
        else:
            if attempt['status'] != 'ok' or output.get('prediction') != prediction:
                raise ValueError('Solar parsed native response differs')
    if journal[-1].get('intrinsic_invalid_count') != invalid:
        raise ValueError('Solar full intrinsic invalid count differs')
    return {'manifest_sha256': sha(MANIFEST), 'claim_sha256': sha(paths['claim.json']),
        'journal_sha256': sha(paths['journal.jsonl']), 'raw_sha256': sha(paths['raw.jsonl']),
        'attempts_sha256': sha(paths['attempts.jsonl']),
        'parsed_sha256': sha(paths['parsed.jsonl']), 'request_count': len(expected),
        'known_valid_count': len(expected) - invalid, 'intrinsic_invalid_count': invalid}


def require_inspection(stage):
    evidence = verify_phase_closure(stage, 'smoke')
    path = BASE / stage / 'smoke-inspection.json'
    inspection = json.loads(path.read_text())
    if (inspection.get('decision') != 'accepted_unchanged' or
            inspection.get('reviewer') != 'root' or
            inspection.get('stage') != stage or inspection.get('closure') != evidence):
        raise ValueError('Solar full three-record smoke inspection absent or changed')


def require_order(stage, mode):
    if stage not in PHASES or mode not in ('smoke', 'development'):
        raise ValueError('Unknown Solar full stage')
    for earlier in PHASES[:PHASES.index(stage)]:
        require_inspection(earlier)
        verify_phase_closure(earlier, 'development')
    if mode == 'development':
        require_inspection(stage)


def stage_template(stage, mode):
    verify(); require_review(); exact_budget(); snapshot = verify_hold()
    require_order(stage, mode)
    return {'schema': SCHEMA + '-stage-root-review', 'approved': False,
        'independent_review': False, 'authorized_by_root': False,
        'reviewer': None, 'stage': stage, 'mode': mode,
        'manifest_sha256': sha(MANIFEST), 'controller_sha256': sha(__file__),
        'frozen_plan_sha256': sha(full.PLAN),
        'request_set_sha256': phase(stage)['requests_sha256'],
        'budget_manifest_sha256': sha(BUDGET), 'partition_id': PARTITION_ID,
        'child_cap_usd': str(CAP), 'per_request_reserve_usd': str(BOUND),
        'authority_hold_source_sha256': hold_source(),
        'authority_head_sha256': snapshot.head_sha256}


def verify_stage_review(path, stage, mode):
    _, paths = stage_paths(stage, mode)
    if Path(path).resolve() != paths['root-review.json'].resolve():
        raise ValueError('Wrong Solar full stage review path')
    expected = stage_template(stage, mode)
    expected.update(approved=True, independent_review=True,
                    authorized_by_root=True, reviewer='root')
    if json.loads(Path(path).read_text()) != expected:
        raise ValueError('Solar full stage review differs')


def execute(stage, mode, review, *, fetch=old.fetch_endpoint,
            send=old.post, env_file=None):
    verify_stage_review(review, stage, mode)
    folder, paths = stage_paths(stage, mode)
    if any(paths[name].exists() for name in
           ('claim.json', 'journal.jsonl', 'raw.jsonl', 'attempts.jsonl', 'parsed.jsonl')):
        raise FileExistsError('Solar full stage already claimed; no replay')
    live_route(fetch)
    ledger = partitions.open_partition(risk.MASTER, BUDGET, PARTITION_ID,
                                       solar.MODEL, solar.PROVIDER, REASONING)
    try:
        _, pending, blocked = ledger.state()
        if (ledger.cap != CAP or ledger.master_cap != budget_v4.CAP or
                pending or blocked or ledger.closed or ledger.accounted() + BOUND > ledger.cap):
            raise ValueError('Solar full child unavailable for next four-question reserve')
        token = load_key(env_file)
        folder.mkdir(parents=True, exist_ok=True)
        with paths['claim.json'].open('x') as out:
            durable(out, {'schema': SCHEMA + '-stage-claim', 'stage': stage,
                'mode': mode, 'manifest_sha256': sha(MANIFEST),
                'root_review_sha256': sha(review),
                'request_set_sha256': phase(stage)['requests_sha256'],
                'reference_labels_sent': False, 'claimed_utc': now()})
        with paths['journal.jsonl'].open('x') as journal, \
                paths['raw.jsonl'].open('x') as raw, \
                paths['attempts.jsonl'].open('x') as attempts, \
                paths['parsed.jsonl'].open('x') as parsed:
            durable(journal, {'event': 'phase_started', 'stage': stage,
                              'mode': mode, 'utc': now()})
            invalid = 0
            for item in stage_rows(stage, mode):
                rid = item['id']
                try:
                    # The active child lock is held. A v4 authority read here
                    # would invert authority -> master -> child lock order.
                    verify()
                    live_raw, _ = live_route(fetch)
                    if native.sha(native.canonical(item['payload'])) != item['payload_sha256']:
                        raise ValueError('Solar full frozen request changed')
                    if ledger.accounted() + BOUND > ledger.cap:
                        raise ValueError('Solar full rolling reserve exhausted')
                    durable(journal, {'event': 'request_intent', 'id': rid,
                        'payload_sha256': item['payload_sha256'], 'utc': now()})
                    aid = ledger.reserve(BOUND, stage + ':' + mode + ':' + rid)
                    durable(journal, {'event': 'request_started', 'id': rid,
                        'attempt_id': aid, 'payload_sha256': item['payload_sha256'],
                        'live_endpoint_sha256': native.sha(live_raw),
                        'live_endpoint_base64': base64.b64encode(live_raw).decode('ascii'),
                        'utc': now()})
                    started, t0 = now(), time.perf_counter_ns()
                    try:
                        status, wire = send(item['payload'], token)
                    except BaseException as error:
                        durable(attempts, {'id': rid, 'attempt_id': aid,
                            'status': 'transport_error', 'error_type': type(error).__name__,
                            'cost_unknown': True, 'reserved_cost_usd': str(BOUND)})
                        raise
                    durable(raw, {'id': rid, 'attempt_id': aid,
                        'payload_sha256': item['payload_sha256'], 'http_status': status,
                        'response_sha256': native.sha(wire),
                        'response_base64': base64.b64encode(wire).decode('ascii'),
                        'request_started_utc': started, 'request_ended_utc': now(),
                        'client_request_elapsed_ns': time.perf_counter_ns() - t0})
                    try:
                        body = json.loads(wire)
                    except (ValueError, UnicodeDecodeError):
                        body = None
                    try:
                        cost = native.response_cost(body)
                    except (ValueError, TypeError, ArithmeticError):
                        cost = None
                    if cost is None:
                        durable(attempts, {'id': rid, 'attempt_id': aid,
                            'status': 'unknown_cost', 'http_status': status,
                            'cost_unknown': True, 'reserved_cost_usd': str(BOUND)})
                        raise ValueError('Solar full cost unknown; reserve retained')
                    if not ledger.settle(aid, cost):
                        durable(attempts, {'id': rid, 'attempt_id': aid,
                            'status': 'over_bound', 'actual_cost_usd': str(cost),
                            'cost_unknown': False})
                        raise ValueError('Solar full observed cost exceeds reserve')
                    if status != 200:
                        durable(attempts, {'id': rid, 'attempt_id': aid,
                            'status': 'http_error', 'http_status': status,
                            'actual_cost_usd': str(cost), 'cost_unknown': False})
                        raise ValueError('Solar full provider HTTP failure; no retry')
                    try:
                        usage, checked_cost = checked_body(body)
                    except (ValueError, TypeError):
                        durable(attempts, {'id': rid, 'attempt_id': aid,
                            'status': 'identity_usage_or_price_violation',
                            'actual_cost_usd': str(cost), 'cost_unknown': False})
                        raise
                    if checked_cost != cost:
                        raise ValueError('Solar full checked cost changed')
                    try:
                        prediction = parse_response(body, solar.VERSION)
                    except (ValueError, TypeError):
                        if mode == 'smoke':
                            durable(attempts, {'id': rid, 'attempt_id': aid,
                                'status': 'invalid_native', 'actual_cost_usd': str(cost),
                                'cost_unknown': False})
                            durable(parsed, {'id': rid, 'attempt_id': aid,
                                'prediction': None, 'usage': usage,
                                'actual_cost_usd': str(cost)})
                            raise ValueError('Solar full smoke invalid; inspect and stop')
                        outcome = 'invalid_native'; prediction = None; invalid += 1
                    else:
                        outcome = 'ok'
                    durable(parsed, {'id': rid, 'attempt_id': aid,
                        'prediction': prediction, 'usage': usage,
                        'actual_cost_usd': str(cost)})
                    durable(attempts, {'id': rid, 'attempt_id': aid,
                        'status': outcome, 'actual_cost_usd': str(cost),
                        'cost_unknown': False})
                    durable(journal, {'event': 'request_finished', 'id': rid,
                        'attempt_id': aid, 'status': outcome,
                        'actual_cost_usd': str(cost), 'utc': now()})
                except BaseException as error:
                    durable(journal, {'event': 'phase_stopped', 'id': rid,
                        'error_type': type(error).__name__, 'utc': now()})
                    raise
            durable(journal, {'event': 'phase_completed', 'stage': stage,
                'mode': mode, 'request_count': len(stage_rows(stage, mode)),
                'intrinsic_invalid_count': invalid, 'utc': now()})
    finally:
        ledger.close()
    return verify_phase_closure(stage, mode)


def inspection_template(stage):
    closure = verify_phase_closure(stage, 'smoke')
    return {'schema': SCHEMA + '-smoke-inspection', 'decision': 'pending',
            'reviewer': None, 'stage': stage, 'closure': closure}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify', 'live-check',
        'hold-source', 'stage-template', 'smoke', 'development', 'inspect-template'))
    parser.add_argument('--stage', choices=PHASES, default='fresh1/P0')
    parser.add_argument('--mode', choices=('smoke', 'development'), default='development')
    parser.add_argument('--review', type=Path)
    parser.add_argument('--env-file')
    args = parser.parse_args()
    if args.action == 'prepare':
        print(prepare()); return
    print(verify())
    if args.action == 'verify':
        return
    if args.action == 'live-check':
        live_route(); print('Solar live route passed; no inference'); return
    if args.action == 'hold-source':
        exact_budget(); print(hold_source()); return
    if args.action == 'stage-template':
        print(json.dumps(stage_template(args.stage, args.mode), indent=2)); return
    if args.action == 'inspect-template':
        print(json.dumps(inspection_template(args.stage), indent=2)); return
    if args.action != args.mode or not args.review:
        parser.error('Solar stage mode or review differs')
    print(execute(args.stage, args.mode, args.review, env_file=args.env_file))


if __name__ == '__main__':
    main()
