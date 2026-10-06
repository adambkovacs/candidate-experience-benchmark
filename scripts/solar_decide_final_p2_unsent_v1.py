#!/usr/bin/env python3
"""Separate, unapproved Solar DEV-010–060 continuation after a read timeout."""
import argparse
import base64
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path
import tempfile
import time

from development_benchmark import ROOT
from openrouter_paid_benchmark import durable, load_key
import openrouter_decision_smoke as native
import openrouter_authority_release_v4 as authority
import openrouter_budget_v4 as budget_v4
import paid_budget_partitions_v4 as partitions
import solar_decide_native_full_execution_v2 as prior

SCHEMA = 'solar-decide-final-p2-unsent-v1'
BASE = ROOT / 'results/solar-decide-native-full-v1/final-p2-unsent-v1'
MANIFEST = BASE / 'manifest.json'
REVIEW = BASE / 'root-review.json'
BUDGET = BASE / 'budget.json'
PARTITION_ID = 'solar-decide-final-p2-dev010-v1'
CHILD = BASE / ('budget-' + PARTITION_ID + '.jsonl')
CAP = Decimal('0.50')
BOUND = prior.BOUND
REASONING = 'native-decisions-four-choice-final-p2-dev010-060-continuation'
STAGE = 'fresh3/P2'
OLD_BASE = prior.BASE
AUDIT = OLD_BASE / STAGE / 'development.interruption-audit.json'
PRE_SNAPSHOT = OLD_BASE / STAGE / 'interrupted-child-pre-reconciliation.jsonl'
TERMINAL = OLD_BASE / 'terminal-reconciliation.json'
SEALED = OLD_BASE / 'terminal-child-snapshot.jsonl'
RELEASE_PLAN = OLD_BASE / 'unused-release-plan.json'
RELEASE_REVIEW = OLD_BASE / 'unused-release-review.json'
RELEASE_RECEIPT = OLD_BASE / 'unused-release-receipt.json'
SOURCES = (
    'scripts/solar_decide_final_p2_unsent_v1.py',
    'tests/test_solar_decide_final_p2_unsent_v1.py',
    'scripts/solar_decide_native_full_execution_v2.py',
    'scripts/solar_decide_native_full_v1.py',
    'scripts/solar_decide_offline_plan.py',
    'scripts/solar_decide_risk_hold_v1.py',
    'scripts/solar_decide_unsent_smoke_v2.py',
    'scripts/solar_decide_unsent_smoke_v2_execution.py',
    'scripts/jev_native_prompt_variants_v1.py',
    'scripts/solar_decide_smoke_v1.py',
    'scripts/openrouter_decision_smoke.py',
    'scripts/jev_benchmark.py',
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
    'results/solar-decide-native-full-v1/plan.json',
    'results/solar-decide-native-full-v1/execution-adapter-v2/manifest.json',
    'results/solar-decide-native-full-v1/execution-adapter-v2/fresh3/P2/development.interruption-audit.json',
    'results/solar-decide-native-full-v1/execution-adapter-v2/fresh3/P2/interrupted-child-pre-reconciliation.jsonl',
    'results/solar-decide-native-full-v1/execution-adapter-v2/terminal-reconciliation.json',
    'results/solar-decide-native-full-v1/execution-adapter-v2/terminal-child-snapshot.jsonl',
    'results/solar-decide-native-full-v1/execution-adapter-v2/unused-release-plan.json',
    'results/solar-decide-native-full-v1/execution-adapter-v2/unused-release-review.json',
    'results/solar-decide-native-full-v1/execution-adapter-v2/unused-release-receipt.json',
    'results/route-audits/solar-openrouter-endpoint-20260930.json',
)


def sha(path):
    return native.sha(Path(path).read_bytes())


def jsonl(path):
    raw = Path(path).read_bytes()
    if raw and not raw.endswith(b'\n'):
        raise ValueError('Incomplete Solar successor JSONL')
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def original_proof():
    audit = json.loads(AUDIT.read_text())
    terminal = json.loads(TERMINAL.read_text())
    pre = jsonl(PRE_SNAPSHOT)
    sealed = jsonl(SEALED)
    release_plan = json.loads(RELEASE_PLAN.read_text())
    release_review = json.loads(RELEASE_REVIEW.read_text())
    release_receipt = json.loads(RELEASE_RECEIPT.read_text())
    if (audit.get('schema') != 'solar-decide-native-full-v2-development-interruption-v1' or
            audit.get('stage') != STAGE or audit.get('failed_record_id') != 'DEV-009' or
            audit.get('completed_response_count') != 8 or audit.get('attempt_count') != 9 or
            audit.get('failed_attempt_status') != 'transport_error' or
            audit.get('failed_error_type') != 'TimeoutError' or
            audit.get('failed_cost_unknown') is not True or
            audit.get('failed_reserved_upper_bound_usd') != str(BOUND) or
            audit.get('retry_performed') is not False or
            audit.get('completed_ids') != [f'DEV-{i:03}' for i in range(1, 9)] or
            audit.get('never_sent_ids') != [f'DEV-{i:03}' for i in range(10, 61)] or
            audit['source_sha256'].get('child_pre_reconciliation_snapshot') != sha(PRE_SNAPSHOT) or
            pre[-1].get('event') != 'reserve' or
            pre[-1].get('record_id') != STAGE + ':development:DEV-009' or
            pre[-1].get('attempt_id') != audit['failed_attempt_id'] or
            pre[-1].get('usd') != str(BOUND) or
            terminal.get('event') != 'partition_reconciled' or
            terminal.get('partition_id') != prior.PARTITION_ID or
            terminal.get('known_actual_usd') != '0.19373795' or
            terminal.get('unknown_upper_bound_usd') != str(BOUND) or
            terminal.get('unused_allocation_released_usd') != '0.70140445' or
            terminal.get('child_sha256') != sha(SEALED) or
            sealed[:-2] != pre or sealed[-2].get('event') != 'unknown_cost_accounted_as_upper_bound' or
            sealed[-2].get('attempt_id') != audit['failed_attempt_id'] or
            sealed[-2].get('usd') != str(BOUND) or
            sealed[-1].get('event') != 'partition_closed'):
        raise ValueError('Solar original interruption or reconciliation differs')
    event = release_receipt.get('event', {})
    if (release_plan.get('event') != event or
            release_review.get('plan_sha256') != native.sha(native.canonical(release_plan)) or
            release_review.get('approved') is not True or
            release_review.get('independent_review') is not True or
            release_receipt.get('review_sha256') != sha(RELEASE_REVIEW) or
            event.get('event') != 'release' or event.get('version') != 4 or
            event.get('hold_id') != prior.PARTITION_ID or
            event.get('usd') != terminal['unused_allocation_released_usd'] or
            event.get('funding_pool') != 'openrouter_additional' or
            event.get('child_sha256') != sha(SEALED) or
            event.get('known_actual_usd') != terminal['known_actual_usd'] or
            event.get('unknown_upper_bound_usd') != terminal['unknown_upper_bound_usd']):
        raise ValueError('Solar original authority release differs')
    for key, name in (('stage_journal_private','development.journal.jsonl'),
                      ('stage_attempts_private','development.attempts.jsonl'),
                      ('stage_raw_private','development.raw.jsonl'),
                      ('stage_parsed_private','development.parsed.jsonl')):
        path = OLD_BASE / STAGE / name
        if path.exists() and audit['source_sha256'].get(key) != sha(path):
            raise ValueError('Solar private original changed: ' + name)
    return audit, terminal


def suffix():
    original_proof()
    plan = json.loads(prior.full.PLAN.read_text())
    phase = next(row for row in plan['phases'] if row['id'] == STAGE)
    rows = phase['requests']
    if (len(rows) != 60 or [row['id'] for row in rows] !=
            [f'DEV-{i:03}' for i in range(1, 61)] or
            [row['id'] for row in rows[9:]] != [f'DEV-{i:03}' for i in range(10, 61)]):
        raise ValueError('Solar exact unsent suffix differs')
    for row in rows:
        if native.sha(native.canonical(row['payload'])) != row['payload_sha256']:
            raise ValueError('Solar frozen payload changed')
    return rows[9:]


def manifest_value():
    rows = suffix()
    return {'schema': SCHEMA + '-manifest', 'status': 'offline_prepared_unapproved',
        'configuration_id': 'solar-decide-upstage-native-four-choice-p2-final-suffix',
        'original_stage': STAGE, 'original_failed_record': 'DEV-009',
        'original_completed_ids': [f'DEV-{i:03}' for i in range(1, 9)],
        'original_failed_cost_unknown': True,
        'original_unknown_upper_bound_usd': str(BOUND),
        'never_sent_ids': [row['id'] for row in rows],
        'never_sent_request_sha256': [row['payload_sha256'] for row in rows],
        'suffix_request_set_sha256': native.sha(native.canonical(rows)),
        'first_request_id': 'DEV-010', 'last_request_id': 'DEV-060',
        'request_count': 51, 'retry_policy': 'none',
        'model': prior.solar.MODEL, 'returned_model': prior.solar.VERSION,
        'provider': prior.solar.PROVIDER, 'interface': 'four native Choice questions',
        'reference_labels_sent': False, 'no_new_smoke': True,
        'no_new_smoke_reason': 'Exact unsent suffix of a root-inspected original stage; DEV-001–009 remain historical and are never replayed.',
        'per_request_conservative_reserve_usd': str(BOUND),
        'proposed_child_cap_usd': str(CAP), 'funding_pool': 'openrouter_additional',
        'partition_id': PARTITION_ID, 'allocation_authorized': False,
        'inference_authorized': False,
        'source_sha256': {name: sha(ROOT / name) for name in SOURCES}}


def review_template():
    return {'schema': SCHEMA + '-root-review', 'approved': False,
        'independent_review': False, 'authorized_by_root': False,
        'reviewer': None, 'manifest_sha256': sha(MANIFEST),
        'controller_sha256': sha(__file__), 'partition_id': PARTITION_ID,
        'proposed_child_cap_usd': str(CAP), 'request_count': 51,
        'first_request_id': 'DEV-010', 'no_new_smoke': True}


def prepare():
    value = manifest_value()
    raw = json.dumps(value, indent=2, sort_keys=True).encode() + b'\n'
    digest = native.sha(raw)
    review = {'schema': SCHEMA + '-root-review', 'approved': False,
        'independent_review': False, 'authorized_by_root': False,
        'reviewer': None, 'manifest_sha256': digest,
        'controller_sha256': sha(__file__), 'partition_id': PARTITION_ID,
        'proposed_child_cap_usd': str(CAP), 'request_count': 51,
        'first_request_id': 'DEV-010', 'no_new_smoke': True}
    BASE.parent.mkdir(parents=True, exist_ok=True)
    with (BASE.parent / '.solar-final-p2-unsent-prepare.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if BASE.exists():
            raise FileExistsError('Solar suffix adapter already prepared')
        with tempfile.TemporaryDirectory(dir=BASE.parent, prefix='.solar-final-p2-unsent-') as temp:
            folder = Path(temp)
            (folder / 'manifest.json').write_bytes(raw)
            (folder / 'root-review.json').write_text(json.dumps(review, indent=2, sort_keys=True) + '\n')
            os.rename(folder, BASE)
    return digest


def verify():
    if json.loads(MANIFEST.read_text()) != manifest_value():
        raise ValueError('Solar suffix manifest or source bytes changed')
    return sha(MANIFEST)


def require_review():
    expected = review_template()
    expected.update(approved=True, independent_review=True,
                    authorized_by_root=True, reviewer='root')
    if json.loads(REVIEW.read_text()) != expected:
        raise ValueError('Solar suffix root review missing')


def exact_budget():
    expected = {'id': PARTITION_ID, 'cap_usd': str(CAP),
        'child_ledger': str(CHILD.resolve()), 'model': prior.solar.MODEL,
        'provider': prior.solar.PROVIDER, 'reasoning': REASONING}
    if json.loads(BUDGET.read_text()) != {'version': 'paid-partitions-v1',
            'master_ledger': str(prior.risk.MASTER.resolve()),
            'partitions': [expected]}:
        raise ValueError('Exact Solar suffix child allocation differs')
    return expected


def hold_source():
    return native.sha(native.canonical({'schema': SCHEMA + '-hold',
        'manifest_sha256': sha(MANIFEST), 'budget_manifest_path': str(BUDGET.resolve()),
        'budget_manifest_sha256': sha(BUDGET), 'partition_id': PARTITION_ID,
        'cap_usd': str(CAP), 'model': prior.solar.MODEL,
        'provider': prior.solar.PROVIDER, 'reasoning': REASONING}))


def verify_hold():
    with authority.old._locked(prior.risk.AUTHORITY) as handle:
        state, holds, released = authority._scan(handle.read())
    hold = holds.get(PARTITION_ID)
    if (prior.PARTITION_ID not in released or PARTITION_ID in released or
            not hold or hold.get('version') != 3 or
            hold.get('funding_pool') != 'openrouter_additional' or
            hold.get('usd') != str(CAP) or hold.get('source_sha256') != hold_source() or
            hold.get('budget_manifest_path') != str(BUDGET.resolve()) or
            hold.get('budget_manifest_sha256') != sha(BUDGET) or
            hold.get('master_path') != str(prior.risk.MASTER.resolve()) or
            hold.get('partition_id') != PARTITION_ID):
        raise ValueError('Exact active Solar suffix hold missing')
    return state


def stage_paths():
    folder = BASE / STAGE
    return folder, {name: folder / ('development.' + name) for name in
                    ('claim.json','journal.jsonl','raw.jsonl','attempts.jsonl',
                     'parsed.jsonl','root-review.json')}


def stage_template():
    verify(); require_review(); exact_budget(); state = verify_hold()
    rows = suffix()
    folder, paths = stage_paths()
    if any(paths[name].exists() for name in
           ('claim.json','journal.jsonl','raw.jsonl','attempts.jsonl','parsed.jsonl')):
        raise FileExistsError('Solar suffix already claimed')
    return {'schema': SCHEMA + '-stage-root-review', 'approved': False,
        'independent_review': False, 'authorized_by_root': False, 'reviewer': None,
        'stage': STAGE, 'mode': 'development_suffix',
        'manifest_sha256': sha(MANIFEST), 'controller_sha256': sha(__file__),
        'frozen_plan_sha256': sha(prior.full.PLAN),
        'request_set_sha256': native.sha(native.canonical(rows)),
        'budget_manifest_sha256': sha(BUDGET), 'partition_id': PARTITION_ID,
        'child_cap_usd': str(CAP), 'per_request_reserve_usd': str(BOUND),
        'authority_hold_source_sha256': hold_source(),
        'authority_head_sha256': state.head_sha256,
        'original_interruption_audit_sha256': sha(AUDIT),
        'original_terminal_reconciliation_sha256': sha(TERMINAL)}


def verify_stage_review(path):
    _, paths = stage_paths()
    if Path(path).resolve() != paths['root-review.json'].resolve():
        raise ValueError('Wrong Solar suffix stage review path')
    expected = stage_template()
    expected.update(approved=True, independent_review=True,
                    authorized_by_root=True, reviewer='root')
    if json.loads(Path(path).read_text()) != expected:
        raise ValueError('Solar suffix stage review differs')


def settlement_map():
    events = jsonl(CHILD)
    if events and events[-1].get('event') == 'partition_closed':
        events = events[:-1]
    if not events or events[0] != {'event': 'budget', 'cap_usd': str(CAP)} or len(events[1:]) % 2:
        raise ValueError('Solar suffix child ledger structure differs')
    settled = {}
    for reserve, settle in zip(events[1::2], events[2::2]):
        aid = reserve.get('attempt_id')
        if (reserve.get('event') != 'reserve' or settle.get('event') != 'settle' or
                settle.get('attempt_id') != aid or aid in settled):
            raise ValueError('Solar suffix pending or duplicate settlement')
        settled[aid] = (reserve, Decimal(settle['usd']))
    return settled


def verify_phase_closure():
    folder, paths = stage_paths()
    expected = suffix()
    claim = json.loads(paths['claim.json'].read_text())
    journal, raw, attempts, parsed = (jsonl(paths[name]) for name in
                                     ('journal.jsonl','raw.jsonl','attempts.jsonl','parsed.jsonl'))
    if (claim.get('manifest_sha256') != sha(MANIFEST) or
            claim.get('stage') != STAGE or claim.get('mode') != 'development_suffix' or
            claim.get('request_set_sha256') != native.sha(native.canonical(expected)) or
            claim.get('root_review_sha256') != sha(paths['root-review.json']) or
            claim.get('reference_labels_sent') is not False or
            len(raw) != len(expected) or len(attempts) != len(expected) or
            len(parsed) != len(expected) or len(journal) != 2 + 3 * len(expected) or
            journal[0].get('event') != 'phase_started' or
            journal[-1].get('event') != 'phase_completed' or
            journal[-1].get('request_count') != len(expected)):
        raise ValueError('Solar suffix lifecycle incomplete')
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
                attempt.get('status') not in ('ok','invalid_native') or
                finished.get('status') != attempt['status']):
            raise ValueError('Solar suffix request identity or outcome differs')
        live = base64.b64decode(started['live_endpoint_base64'], validate=True)
        if (native.sha(live) != started['live_endpoint_sha256'] or
                not prior.solar.validate_catalog(json.loads(live))['upstage']):
            raise ValueError('Solar suffix route capture differs')
        wire = base64.b64decode(record['response_base64'], validate=True)
        if native.sha(wire) != record['response_sha256']:
            raise ValueError('Solar suffix raw response differs')
        body = json.loads(wire); usage, cost = prior.checked_body(body)
        saved = settled.get(aid)
        if (not saved or saved[0].get('record_id') != STAGE + ':development_suffix:' + item['id'] or
                Decimal(saved[0]['usd']) != BOUND or saved[1] != cost or
                Decimal(attempt['actual_cost_usd']) != cost or
                Decimal(output['actual_cost_usd']) != cost or output.get('usage') != usage):
            raise ValueError('Solar suffix settlement or usage differs')
        try:
            prediction = prior.parse_response(body, prior.solar.VERSION)
        except (ValueError, TypeError):
            if attempt['status'] != 'invalid_native' or output.get('prediction') is not None:
                raise ValueError('Solar invalid native response not retained')
            invalid += 1
        else:
            if attempt['status'] != 'ok' or output.get('prediction') != prediction:
                raise ValueError('Solar suffix parsed native response differs')
    if journal[-1].get('intrinsic_invalid_count') != invalid:
        raise ValueError('Solar suffix invalid count differs')
    return {'manifest_sha256': sha(MANIFEST), 'claim_sha256': sha(paths['claim.json']),
        'journal_sha256': sha(paths['journal.jsonl']), 'raw_sha256': sha(paths['raw.jsonl']),
        'attempts_sha256': sha(paths['attempts.jsonl']),
        'parsed_sha256': sha(paths['parsed.jsonl']), 'request_count': len(expected),
        'known_valid_count': len(expected) - invalid, 'intrinsic_invalid_count': invalid}


def execute(review, *, fetch=prior.old.fetch_endpoint, send=prior.old.post, env_file=None):
    verify_stage_review(review)
    folder, paths = stage_paths()
    if any(paths[name].exists() for name in
           ('claim.json','journal.jsonl','raw.jsonl','attempts.jsonl','parsed.jsonl')):
        raise FileExistsError('Solar suffix already claimed; no replay')
    prior.live_route(fetch)
    ledger = partitions.open_partition(prior.risk.MASTER, BUDGET, PARTITION_ID,
                                       prior.solar.MODEL, prior.solar.PROVIDER, REASONING)
    try:
        _, pending, blocked = ledger.state()
        if (ledger.cap != CAP or ledger.master_cap != budget_v4.CAP or
                pending or blocked or ledger.closed or ledger.accounted() + BOUND > ledger.cap):
            raise ValueError('Solar suffix child unavailable')
        token = load_key(env_file)
        rows = suffix()
        folder.mkdir(parents=True, exist_ok=True)
        with paths['claim.json'].open('x') as out:
            durable(out, {'schema': SCHEMA + '-stage-claim', 'stage': STAGE,
                'mode': 'development_suffix', 'manifest_sha256': sha(MANIFEST),
                'root_review_sha256': sha(review),
                'request_set_sha256': native.sha(native.canonical(rows)),
                'reference_labels_sent': False, 'claimed_utc': prior.now()})
        with paths['journal.jsonl'].open('x') as journal, \
                paths['raw.jsonl'].open('x') as raw, \
                paths['attempts.jsonl'].open('x') as attempts, \
                paths['parsed.jsonl'].open('x') as parsed:
            durable(journal, {'event': 'phase_started', 'stage': STAGE,
                              'mode': 'development_suffix', 'utc': prior.now()})
            invalid = 0
            for item in rows:
                rid = item['id']
                try:
                    verify()
                    live_raw, _ = prior.live_route(fetch)
                    if native.sha(native.canonical(item['payload'])) != item['payload_sha256']:
                        raise ValueError('Solar suffix frozen request changed')
                    if ledger.accounted() + BOUND > ledger.cap:
                        raise ValueError('Solar suffix rolling reserve exhausted')
                    durable(journal, {'event': 'request_intent', 'id': rid,
                        'payload_sha256': item['payload_sha256'], 'utc': prior.now()})
                    aid = ledger.reserve(BOUND, STAGE + ':development_suffix:' + rid)
                    durable(journal, {'event': 'request_started', 'id': rid,
                        'attempt_id': aid, 'payload_sha256': item['payload_sha256'],
                        'live_endpoint_sha256': native.sha(live_raw),
                        'live_endpoint_base64': base64.b64encode(live_raw).decode('ascii'),
                        'utc': prior.now()})
                    started, t0 = prior.now(), time.perf_counter_ns()
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
                        'request_started_utc': started, 'request_ended_utc': prior.now(),
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
                        raise ValueError('Solar suffix cost unknown; reserve retained')
                    if not ledger.settle(aid, cost):
                        durable(attempts, {'id': rid, 'attempt_id': aid,
                            'status': 'over_bound', 'actual_cost_usd': str(cost),
                            'cost_unknown': False})
                        raise ValueError('Solar suffix observed cost exceeds reserve')
                    if status != 200:
                        durable(attempts, {'id': rid, 'attempt_id': aid,
                            'status': 'http_error', 'http_status': status,
                            'actual_cost_usd': str(cost), 'cost_unknown': False})
                        raise ValueError('Solar suffix provider HTTP failure; no retry')
                    try:
                        usage, checked_cost = prior.checked_body(body)
                    except (ValueError, TypeError):
                        durable(attempts, {'id': rid, 'attempt_id': aid,
                            'status': 'identity_usage_or_price_violation',
                            'actual_cost_usd': str(cost), 'cost_unknown': False})
                        raise
                    if checked_cost != cost:
                        raise ValueError('Solar suffix checked cost changed')
                    try:
                        prediction = prior.parse_response(body, prior.solar.VERSION)
                    except (ValueError, TypeError):
                        prediction = None; invalid += 1; outcome = 'invalid_native'
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
                        'actual_cost_usd': str(cost), 'utc': prior.now()})
                except BaseException as error:
                    durable(journal, {'event': 'phase_stopped', 'id': rid,
                        'error_type': type(error).__name__, 'utc': prior.now()})
                    raise
            durable(journal, {'event': 'phase_completed', 'stage': STAGE,
                'mode': 'development_suffix', 'request_count': len(rows),
                'intrinsic_invalid_count': invalid, 'utc': prior.now()})
    finally:
        ledger.close()
    return verify_phase_closure()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare','verify','live-check',
                                           'hold-source','stage-template','development'))
    parser.add_argument('--review', type=Path)
    parser.add_argument('--env-file')
    args = parser.parse_args()
    if args.action == 'prepare':
        print(prepare()); return
    print(verify())
    if args.action == 'verify':
        return
    if args.action == 'live-check':
        prior.live_route(); print('Solar suffix live route passed; no inference'); return
    if args.action == 'hold-source':
        exact_budget(); print(hold_source()); return
    if args.action == 'stage-template':
        print(json.dumps(stage_template(), indent=2)); return
    if not args.review:
        parser.error('Solar suffix development requires exact root review')
    print(execute(args.review, env_file=args.env_file))


if __name__ == '__main__':
    main()
