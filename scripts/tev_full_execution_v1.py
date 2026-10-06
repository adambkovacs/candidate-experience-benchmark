#!/usr/bin/env python3
"""Separately reviewed Tev native Choice full-stage executor; offline until admitted."""
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
from openrouter_paid_benchmark import durable
import tev_native_v1 as tev
import tev_smoke_v1 as smoke
import openrouter_decision_smoke as native
import openrouter_budget_v4 as budget_v4
import paid_budget_partitions_v4 as partitions
import openrouter_authority_release_v4 as authority_v4

BASE = ROOT / 'results/tev-native-v1/full-v1'
MANIFEST = BASE / 'manifest.json'
REVIEW = BASE / 'root-review.json'
BUDGET = BASE / 'budget.json'
MASTER = smoke.MASTER
AUTHORITY = smoke.AUTHORITY
PARTITION_ID = 'tev-native-full-v1'
CHILD = BASE / ('budget-' + PARTITION_ID + '.jsonl')
CAP = Decimal('1.00')
REASONING = 'native-decisions-four-choice'
SCHEMA = 'tev-native-full-execution-v1'
PHASES = tuple(f'fresh{i}/{p}' for i in (1, 2, 3) for p in ('P0', 'P1', 'P2'))
SOURCES = ('scripts/tev_full_execution_v1.py', 'tests/test_tev_full_execution_v1.py',
           'scripts/tev_native_v1.py', 'scripts/tev_smoke_v1.py',
           'scripts/openrouter_decision_smoke.py',
           'scripts/jev_benchmark.py', 'scripts/openrouter_paid_benchmark.py',
           'scripts/openrouter_budget_v4.py', 'scripts/openrouter_budget_v3.py', 'scripts/openrouter_budget_v2.py',
           'scripts/paid_budget_partitions_v4.py', 'scripts/paid_budget_partitions_v3.py',
           'scripts/openrouter_authority_release_v4.py', 'scripts/postapproval_authority_v3.py',
           'scripts/postapproval_authority_v2.py', 'scripts/openrouter_budget_amendment_v3.py')


def sha(path):
    return native.sha(Path(path).read_bytes())


def now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def jsonl(path):
    raw = Path(path).read_bytes()
    if not raw.endswith(b'\n'):
        raise ValueError('Incomplete Tev stage JSONL')
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def original_smoke_archived():
    plan, digest = tev.verify()
    receipt = json.loads((tev.BASE / 'smoke.closure-audit.json').read_text())
    inspection = json.loads((tev.BASE / 'smoke-inspection.root.json').read_text())
    reconciliation = json.loads((tev.BASE / 'smoke.reconciliation.json').read_text()).get('partition_reconciled')
    if not isinstance(reconciliation, dict):
        raise ValueError('Tev smoke reconciliation missing')
    if (receipt.get('plan_sha256') != digest or receipt.get('status') != 'three_record_smoke_closed' or
            receipt.get('valid_native_responses') != 3 or receipt.get('known_actual_usd') != '0.000816018' or
            receipt.get('child_ledger_snapshot_sha256') != sha(tev.BASE / 'smoke.closure-ledger-snapshot.jsonl') or
            inspection.get('decision') != 'accepted_unchanged' or inspection.get('reviewer') != 'root' or
            inspection.get('raw_sha256') != sha(tev.BASE / 'smoke.raw.jsonl') or
            inspection.get('ids') != [r['id'] for r in receipt['records']] or
            inspection.get('exact_model_and_provider') is not True or
            inspection.get('native_choices_valid') is not True or
            inspection.get('observed_output_tokens_per_request') != 8 or
            inspection.get('reference_labels_sent') is not False or
            inspection.get('full_run_authorized') is not False or
            reconciliation.get('event') != 'partition_reconciled' or
            reconciliation.get('partition_id') != smoke.PARTITION_ID or
            reconciliation.get('known_actual_usd') != receipt['known_actual_usd'] or
            reconciliation.get('unknown_upper_bound_usd') != '0' or
            reconciliation.get('unused_allocation_released_usd') != '0.024183982' or
            Path(str(reconciliation.get('child_ledger'))).name != smoke.CHILD.name or
            reconciliation.get('child_sha256') != sha(smoke.CHILD)):
        raise ValueError('Closed original Tev P0 smoke differs')
    if len(receipt.get('records', [])) != 3:
        raise ValueError('Original Tev smoke record count differs')
    for name, expected_sha in receipt['evidence_sha256'].items():
        if sha(tev.BASE / name) != expected_sha:
            raise ValueError('Original Tev smoke evidence changed: ' + name)
    raw = jsonl(tev.BASE / 'smoke.raw.jsonl')
    attempts = jsonl(tev.BASE / 'smoke.attempts.jsonl')
    parsed = jsonl(tev.BASE / 'smoke.parsed.jsonl')
    snapshot = jsonl(tev.BASE / 'smoke.closure-ledger-snapshot.jsonl')
    child = jsonl(smoke.CHILD)
    if (len(raw) != 3 or len(attempts) != 3 or len(parsed) != 3 or len(snapshot) != 7 or
            snapshot[0] != {'event': 'budget', 'cap_usd': str(smoke.CAP)} or
            child[:7] != snapshot or len(child) != 8 or child[-1].get('event') != 'partition_closed'):
        raise ValueError('Original Tev smoke lifecycle differs')
    for index, (recorded, attempt, output, expected) in enumerate(zip(raw, attempts, parsed, receipt['records'])):
        wire = base64.b64decode(recorded['response_base64'], validate=True)
        body = json.loads(wire)
        if (recorded['id'] != expected['id'] or native.sha(wire) != expected['response_sha256'] or
                recorded['response_sha256'] != expected['response_sha256'] or
                recorded['http_status'] != 200 or
                attempt.get('id') != expected['id'] or attempt.get('status') != 'ok' or
                attempt.get('attempt_id') != recorded['attempt_id'] or
                attempt.get('actual_cost_usd') != expected['actual_cost_usd'] or
                snapshot[1+2*index] != {'event': 'reserve', 'attempt_id': attempt['attempt_id'],
                                        'record_id': expected['id'], 'usd': str(tev.BOUND)} or
                snapshot[2+2*index] != {'event': 'settle', 'attempt_id': attempt['attempt_id'],
                                        'usd': expected['actual_cost_usd']} or
                body.get('usage', {}).get('input_tokens') != expected['input_tokens'] or
                body.get('usage', {}).get('output_tokens') != expected['output_tokens'] or
                native.response_cost(body) != Decimal(expected['actual_cost_usd'])):
            raise ValueError('Original Tev smoke raw response differs')
        prediction, optional = smoke.validate_returned(body)
        if (prediction != expected['prediction'] or output.get('prediction') != prediction or
                output.get('optional') != optional or
                all(value['probabilities_available'] for value in optional.values()) != expected['probabilities_present'] or
                all(value['confidence_available'] for value in optional.values()) != expected['confidence_present']):
            raise ValueError('Original Tev parsed Choice response differs')
    return receipt


def verify_original_smoke_runtime():
    """Recheck the frozen smoke evidence under the post-release v4 reader."""
    receipt = original_smoke_archived()
    reconciliation = json.loads((tev.BASE / 'smoke.reconciliation.json').read_text())['partition_reconciled']
    if reconciliation['child_ledger'] != str(smoke.CHILD.resolve()):
        raise ValueError('Historical Tev child belongs to another host path')
    plan, plan_sha = tev.verify()
    budget = tev.BASE / 'budget-manifest.json'
    smoke.verify_review(tev.BASE / 'smoke.root-review.json', plan, plan_sha, budget, tev.BASE)
    with authority_v4.old._locked(AUTHORITY) as handle:
        _, holds, _ = authority_v4._scan(handle.read())
    hold = holds.get(smoke.PARTITION_ID)
    if (not hold or hold.get('source_sha256') != smoke.hold_source(plan_sha, budget) or
            hold.get('budget_manifest_sha256') != sha(budget) or
            hold.get('budget_manifest_path') != str(budget.resolve()) or
            hold.get('usd') != str(smoke.CAP)):
        raise ValueError('Historical Tev smoke hold differs after v4 release')
    return receipt


def manifest_value():
    plan, plan_sha = tev.verify()
    original_smoke_archived()
    source = {name: sha(ROOT / name) for name in SOURCES}
    archived = ('results/tev-native-v1/plan.json',
                'results/route-audits/tev-public-20261006-evening/audit.json',
                'results/route-audits/tev-public-20261006-evening/endpoints.json',
                'results/tev-native-v1/smoke.closure-audit.json',
                'results/tev-native-v1/smoke.closure-ledger-snapshot.jsonl',
                'results/tev-native-v1/smoke.raw.jsonl',
                'results/tev-native-v1/smoke.attempts.jsonl',
                'results/tev-native-v1/smoke.journal.jsonl',
                'results/tev-native-v1/smoke.parsed.jsonl',
                'results/tev-native-v1/smoke.root-review.json',
                'results/tev-native-v1/budget-manifest.json',
                'results/tev-native-v1/budget-manifest-tev-native-fresh1-p0-smoke-v1.jsonl',
                'results/tev-native-v1/smoke-inspection.root.json',
                'results/tev-native-v1/smoke.reconciliation.json')
    return {'schema': SCHEMA + '-manifest', 'status': 'offline_prepared_unapproved',
            'inference_authorized': False, 'allocation_authorized': False,
            'configuration_id': 'tev-openrouter-native-choice-v1',
            'model': tev.MODEL, 'returned_model': tev.VERSION,
            'provider': tev.PROVIDER, 'provider_tag': tev.TAG,
            'api_url': native.DECISIONS_URL, 'frozen_plan_sha256': plan_sha,
            'phase_order': list(PHASES), 'phase_count': 9,
            'development_record_count_per_phase': 60,
            'new_smoke_record_count_per_phase': 3,
            'original_fresh1_p0_smoke_reused': True,
            'new_smoke_stage_count': 8, 'development_stage_count': 9,
            'development_intrinsic_invalid_policy': 'retain known-cost invalid native outputs in the 60-attempt denominator and continue; never award clean credit',
            'provider_failure_policy': 'stop with exact evidence; never retry automatically',
            'question_count': tev.QUESTION_COUNT,
            'context_tokens_per_question': tev.CONTEXT,
            'max_billable_input_tokens_per_request': tev.QUESTION_COUNT * tev.CONTEXT,
            'per_request_full_context_reserve_usd': str(tev.BOUND),
            'proposed_child_cap_usd': str(CAP), 'funding_pool': 'openrouter_additional',
            'partition_id': PARTITION_ID,
            'request_sets': {p['id']:p['requests_sha256'] for p in plan['phases']},
            'max_canonical_request_bytes': {p['id']:max(len(native.canonical(r['payload'])) for r in p['requests']) for p in plan['phases']},
            'context_preflight': 'Catalog names tokenizer Qwen3 but no exact four-question token-count endpoint is published; byte sizes and observed smoke usage are evidence, not an all-record token proof. No truncation is permitted.',
            'source_sha256': source,
            'archive_sha256': {name: sha(ROOT / name) for name in archived}}


def review_template(manifest_sha=None):
    return {'schema': SCHEMA + '-root-review', 'approved': False,
            'independent_review': False, 'authorized_by_root': False, 'reviewer': None,
            'manifest_sha256': manifest_sha or sha(MANIFEST),
            'controller_sha256': sha(__file__),
            'proposed_child_cap_usd': str(CAP), 'partition_id': PARTITION_ID,
            'phase_count': 9, 'funding_pool': 'openrouter_additional'}


def prepare():
    raw = (json.dumps(manifest_value(), indent=2, ensure_ascii=False) + '\n').encode()
    digest = native.sha(raw)
    review = (json.dumps(review_template(digest), indent=2) + '\n').encode()
    BASE.parent.mkdir(parents=True, exist_ok=True)
    lock_path = BASE.parent / '.tev-full-v1-prepare.lock'
    with lock_path.open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if BASE.exists():
            raise FileExistsError('Tev full adapter already prepared')
        with tempfile.TemporaryDirectory(dir=BASE.parent, prefix='.tev-full-v1-') as temp:
            stage = Path(temp)
            (stage / 'manifest.json').write_bytes(raw)
            (stage / 'root-review.json').write_bytes(review)
            os.rename(stage, BASE)
    return digest


def verify():
    saved = json.loads(MANIFEST.read_text())
    if saved != manifest_value():
        raise ValueError('Tev full manifest/source/archive drift')
    return sha(MANIFEST)


def require_review():
    expected = review_template()
    expected.update(approved=True, independent_review=True, authorized_by_root=True, reviewer='root')
    if json.loads(REVIEW.read_text()) != expected:
        raise ValueError('Independent Tev full adapter review missing')


def exact_budget():
    budget = json.loads(BUDGET.read_text())
    if budget.get('version') != 'paid-partitions-v1' or budget.get('master_ledger') != str(MASTER.resolve()):
        raise ValueError('Tev budget master differs')
    entries = budget.get('partitions')
    expected = {'id': PARTITION_ID, 'cap_usd': str(CAP), 'child_ledger': str(CHILD.resolve()),
                'model': tev.MODEL, 'provider': tev.PROVIDER, 'reasoning': REASONING}
    if not isinstance(entries, list) or len(entries) != 1 or entries[0] != expected:
        raise ValueError('Tev full child allocation differs')
    return expected


def hold_source():
    return native.sha(native.canonical({'schema': SCHEMA + '-authority-hold',
        'manifest_sha256': sha(MANIFEST), 'budget_manifest_path': str(BUDGET.resolve()),
        'budget_manifest_sha256': sha(BUDGET), 'partition_id': PARTITION_ID,
        'cap_usd': str(CAP), 'model': tev.MODEL, 'provider': tev.PROVIDER,
        'reasoning': REASONING}))


def verify_hold():
    with authority_v4.old._locked(AUTHORITY) as handle:
        snapshot, holds, released = authority_v4._scan(handle.read())
    hold = holds.get(PARTITION_ID)
    if (PARTITION_ID in released or not hold or hold.get('version') != 3 or
            hold.get('funding_pool') != 'openrouter_additional' or hold.get('usd') != str(CAP) or
            hold.get('source_sha256') != hold_source() or
            hold.get('budget_manifest_path') != str(BUDGET.resolve()) or
            hold.get('budget_manifest_sha256') != sha(BUDGET) or
            hold.get('master_path') != str(MASTER.resolve()) or
            hold.get('partition_id') != PARTITION_ID):
        raise ValueError('Exact unreleased Tev v4 authority hold missing')
    return snapshot


def phase(stage):
    if stage not in PHASES:
        raise ValueError('Unknown Tev full stage')
    return next(p for p in tev.verify()[0]['phases'] if p['id'] == stage)


def stage_paths(stage, mode):
    if mode not in ('smoke', 'development') or stage not in PHASES or (stage == 'fresh1/P0' and mode == 'smoke'):
        raise ValueError('Unknown or already completed Tev stage')
    folder = BASE / stage
    return folder, {key:folder / (mode + '.' + key) for key in
                    ('claim.json','journal.jsonl','raw.jsonl','attempts.jsonl','parsed.jsonl','root-review.json')}


def stage_rows(stage, mode):
    requests = phase(stage)['requests']
    return requests[:3] if mode == 'smoke' else requests


def settlement_map():
    events = jsonl(CHILD)
    if events and events[-1].get('event') == 'partition_closed':
        events = events[:-1]
    if not events or events[0] != {'event': 'budget', 'cap_usd': str(CAP)} or len(events[1:]) % 2:
        raise ValueError('Tev child ledger structure differs')
    known = {}
    for reserve, settle in zip(events[1::2],events[2::2]):
        if reserve.get('event') != 'reserve' or settle.get('event') != 'settle' or reserve.get('attempt_id') != settle.get('attempt_id') or reserve['attempt_id'] in known:
            raise ValueError('Tev child has unresolved or duplicate attempt')
        known[reserve['attempt_id']] = (reserve, Decimal(settle['usd']))
    return known


def verify_phase_closure(stage, mode):
    folder, paths = stage_paths(stage,mode)
    expected = stage_rows(stage,mode)
    claim = json.loads(paths['claim.json'].read_text())
    journal, raw, attempts, parsed = (jsonl(paths[name]) for name in
                                      ('journal.jsonl','raw.jsonl','attempts.jsonl','parsed.jsonl'))
    if (claim.get('manifest_sha256') != sha(MANIFEST) or claim.get('stage') != stage or
            claim.get('mode') != mode or claim.get('request_set_sha256') != phase(stage)['requests_sha256'] or
            claim.get('root_review_sha256') != sha(paths['root-review.json']) or
            claim.get('reference_labels_sent') is not False or
            len(raw) != len(expected) or len(attempts) != len(expected) or
            len(parsed) != len(expected) or len(journal) != 2+3*len(expected) or
            journal[0].get('event') != 'phase_started' or journal[0].get('stage') != stage or
            journal[0].get('mode') != mode or journal[-1].get('event') != 'phase_completed' or
            journal[-1].get('stage') != stage or journal[-1].get('mode') != mode or
            journal[-1].get('request_count') != len(expected)):
        raise ValueError('Tev phase lifecycle incomplete')
    ledger = settlement_map()
    invalid = 0
    for index, item in enumerate(expected):
        intent, started, finished = journal[1+3*index:4+3*index]
        record, attempt, parsed_record = raw[index],attempts[index],parsed[index]
        aid = started.get('attempt_id')
        if (intent.get('event') != 'request_intent' or started.get('event') != 'request_started' or
                finished.get('event') != 'request_finished' or
                any(row.get('id') != item['id'] for row in (intent,started,finished,record,attempt,parsed_record)) or
                any(row.get('attempt_id') != aid for row in (finished,record,attempt,parsed_record)) or
                intent.get('payload_sha256') != item['payload_sha256'] or
                started.get('payload_sha256') != item['payload_sha256'] or
                record.get('payload_sha256') != item['payload_sha256'] or
                record.get('http_status') != 200 or attempt.get('cost_unknown') is not False or
                attempt.get('status') not in ('ok','invalid_native') or
                finished.get('status') != attempt['status'] or
                Decimal(finished.get('actual_cost_usd', '-1')) != Decimal(attempt['actual_cost_usd'])):
            raise ValueError('Tev phase request identity or status differs')
        live = base64.b64decode(started['live_endpoint_base64'],validate=True)
        if native.sha(live) != started['live_endpoint_sha256']:
            raise ValueError('Tev live endpoint capture differs')
        tev.validate_catalog(json.loads(live))
        body_raw = base64.b64decode(record['response_base64'],validate=True)
        if native.sha(body_raw) != record['response_sha256']:
            raise ValueError('Tev raw response hash differs')
        body = json.loads(body_raw)
        if body.get('model') != tev.VERSION or body.get('provider') != tev.PROVIDER:
            raise ValueError('Tev returned model/provider differs')
        usage = body.get('usage')
        if (not isinstance(usage,dict) or type(usage.get('input_tokens')) is not int or
                not 0 <= usage['input_tokens'] <= tev.QUESTION_COUNT*tev.CONTEXT or
                type(usage.get('output_tokens')) is not int or usage['output_tokens'] < 0 or
                parsed_record.get('input_tokens') != usage['input_tokens'] or
                parsed_record.get('output_tokens') != usage['output_tokens']):
            raise ValueError('Tev usage exceeds reviewed context')
        cost = native.response_cost(body)
        saved = ledger.get(aid)
        if (cost is None or cost != Decimal(usage['input_tokens'])*tev.RATE or
                not saved or saved[0].get('record_id') != stage+':'+mode+':'+item['id'] or
                Decimal(saved[0]['usd']) != tev.BOUND or saved[1] != cost or
                cost != Decimal(attempt['actual_cost_usd']) or
                cost != Decimal(parsed_record['actual_cost_usd']) or cost > tev.BOUND):
            raise ValueError('Tev cost/ledger differs')
        try:
            prediction, optional = smoke.validate_returned(body)
        except (ValueError, TypeError):
            if (attempt['status'] != 'invalid_native' or mode == 'smoke' or
                    parsed_record.get('prediction') is not None or parsed_record.get('optional') is not None):
                raise ValueError('Tev invalid response not retained honestly')
            invalid += 1
        else:
            if (attempt['status'] != 'ok' or parsed_record.get('prediction') != prediction or
                    parsed_record.get('optional') != optional):
                raise ValueError('Tev parsed Choice response differs')
    if mode == 'smoke' and invalid:
        raise ValueError('Tev smoke not wholly valid')
    if journal[-1].get('intrinsic_invalid_count') != invalid:
        raise ValueError('Tev intrinsic invalid count differs')
    return {'manifest_sha256': sha(MANIFEST), 'claim_sha256': sha(paths['claim.json']),
            'journal_sha256': sha(paths['journal.jsonl']), 'raw_sha256': sha(paths['raw.jsonl']),
            'attempts_sha256': sha(paths['attempts.jsonl']), 'parsed_sha256': sha(paths['parsed.jsonl']),
            'request_count': len(expected), 'known_valid_count': len(expected)-invalid,
            'intrinsic_invalid_count': invalid}


def require_order(stage, mode):
    if stage not in PHASES or mode not in ('smoke','development') or (stage == 'fresh1/P0' and mode == 'smoke'):
        raise ValueError('Unknown Tev stage')
    for earlier in PHASES[:PHASES.index(stage)]:
        verify_phase_closure(earlier,'development')
    if mode == 'development':
        if stage == 'fresh1/P0':
            verify_original_smoke_runtime()
        else:
            evidence = verify_phase_closure(stage,'smoke')
            folder,_ = stage_paths(stage,'smoke')
            inspection = json.loads((folder / 'smoke-inspection.json').read_text())
            if (inspection.get('decision') != 'accepted_unchanged' or inspection.get('reviewer') != 'root' or
                    inspection.get('closure') != evidence):
                raise ValueError('Tev smoke inspection absent or changed')


def stage_template(stage, mode):
    verify(); require_review(); exact_budget(); verify_hold(); require_order(stage,mode)
    return {'schema': SCHEMA + '-stage-root-review', 'approved': False,
            'independent_review': False, 'authorized_by_root': False, 'reviewer': None,
            'stage': stage, 'mode': mode, 'manifest_sha256': sha(MANIFEST),
            'controller_sha256': sha(__file__), 'frozen_plan_sha256': tev.verify()[1],
            'request_set_sha256': phase(stage)['requests_sha256'],
            'budget_manifest_sha256': sha(BUDGET), 'partition_id': PARTITION_ID,
            'child_cap_usd': str(CAP), 'per_request_reserve_usd': str(tev.BOUND),
            'authority_hold_source_sha256': hold_source(),
            'authority_head_sha256': authority_v4.read_authority(AUTHORITY).head_sha256}


def verify_stage_review(path, stage, mode):
    folder,paths=stage_paths(stage,mode)
    if Path(path).resolve()!=paths['root-review.json'].resolve():
        raise ValueError('Wrong Tev stage review path')
    actual=json.loads(Path(path).read_text())
    expected=stage_template(stage,mode)
    expected.update(approved=True,independent_review=True,authorized_by_root=True,reviewer='root')
    if actual!=expected:
        raise ValueError('Tev stage review differs')
    return actual


def execute(stage, mode, review, *, fetch=smoke.fetch_endpoint, send=smoke.post):
    verify_stage_review(review,stage,mode)
    folder,paths=stage_paths(stage,mode)
    if any(paths[key].exists() for key in ('claim.json','journal.jsonl','raw.jsonl','attempts.jsonl','parsed.jsonl')):
        raise FileExistsError('Tev full stage already claimed; no replay')
    _,route=fetch();tev.validate_catalog(route)
    ledger=partitions.open_partition(MASTER,BUDGET,PARTITION_ID,tev.MODEL,tev.PROVIDER,REASONING)
    try:
        _,pending,blocked=ledger.state()
        if ledger.cap!=CAP or ledger.master_cap!=budget_v4.CAP or pending or blocked or ledger.closed or ledger.accounted()+tev.BOUND>ledger.cap:
            raise ValueError('Tev full child unavailable for next full-context reserve')
        token=os.environ.get('OPENROUTER_API_KEY')
        if not token:
            raise ValueError('OPENROUTER_API_KEY required')
        folder.mkdir(parents=True,exist_ok=True)
        with paths['claim.json'].open('x') as out:
            durable(out,{'schema':SCHEMA+'-stage-claim','stage':stage,'mode':mode,
                'manifest_sha256':sha(MANIFEST),'root_review_sha256':sha(review),
                'request_set_sha256':phase(stage)['requests_sha256'],'claimed_utc':now(),
                'reference_labels_sent':False})
        with paths['journal.jsonl'].open('x') as journal,paths['raw.jsonl'].open('x') as raw,\
             paths['attempts.jsonl'].open('x') as attempts,paths['parsed.jsonl'].open('x') as parsed:
            durable(journal,{'event':'phase_started','stage':stage,'mode':mode,'utc':now()})
            invalid=0
            for item in stage_rows(stage,mode):
                rid=item['id']
                try:
                    # Admission checked the v4 hold before opening this child.
                    # A v4 release cannot release an active child; acquiring the
                    # authority lock here would invert v4's authority->master order.
                    verify()
                    live_raw,live=fetch();tev.validate_catalog(live)
                    if native.sha(native.canonical(item['payload']))!=item['payload_sha256']:
                        raise ValueError('Tev frozen request changed')
                    if ledger.accounted()+tev.BOUND>ledger.cap:
                        raise ValueError('Tev rolling reserve exhausted')
                    durable(journal,{'event':'request_intent','id':rid,'payload_sha256':item['payload_sha256'],'utc':now()})
                    aid=ledger.reserve(tev.BOUND,stage+':'+mode+':'+rid)
                    durable(journal,{'event':'request_started','id':rid,'attempt_id':aid,
                        'payload_sha256':item['payload_sha256'],'live_endpoint_sha256':native.sha(live_raw),
                        'live_endpoint_base64':base64.b64encode(live_raw).decode('ascii'),'utc':now()})
                    started,t0=now(),time.perf_counter_ns()
                    try:status,wire=send(item['payload'],token)
                    except BaseException as error:
                        durable(attempts,{'id':rid,'attempt_id':aid,'status':'transport_error',
                            'error_type':type(error).__name__,'cost_unknown':True,
                            'reserved_cost_usd':str(tev.BOUND),'utc':now()})
                        raise
                    ended,elapsed=now(),time.perf_counter_ns()-t0
                    durable(raw,{'id':rid,'attempt_id':aid,'payload_sha256':item['payload_sha256'],
                        'http_status':status,'response_sha256':native.sha(wire),
                        'response_base64':base64.b64encode(wire).decode('ascii'),
                        'request_started_utc':started,'request_ended_utc':ended,
                        'client_request_elapsed_ns':elapsed})
                    try:body=json.loads(wire)
                    except (ValueError,UnicodeDecodeError):body=None
                    try:cost=native.response_cost(body)
                    except (ValueError,TypeError,ArithmeticError):cost=None
                    if cost is None:
                        durable(attempts,{'id':rid,'attempt_id':aid,'status':'unknown_cost','http_status':status,
                            'cost_unknown':True,'reserved_cost_usd':str(tev.BOUND)})
                        raise ValueError('Tev cost unknown; full reserve retained')
                    if not ledger.settle(aid,cost):
                        durable(attempts,{'id':rid,'attempt_id':aid,'status':'over_bound',
                            'actual_cost_usd':str(cost),'cost_unknown':False})
                        raise ValueError('Tev cost exceeded reserve')
                    if status!=200:
                        durable(attempts,{'id':rid,'attempt_id':aid,'status':'http_error','http_status':status,
                            'actual_cost_usd':str(cost),'cost_unknown':False})
                        raise ValueError('Tev provider HTTP failure; no retry')
                    usage=body.get('usage') if isinstance(body,dict) else None
                    if (not isinstance(usage,dict) or type(usage.get('input_tokens')) is not int or
                            not 0<=usage['input_tokens']<=tev.QUESTION_COUNT*tev.CONTEXT or
                            type(usage.get('output_tokens')) is not int or usage['output_tokens']<0 or
                            cost!=Decimal(usage['input_tokens'])*tev.RATE):
                        durable(attempts,{'id':rid,'attempt_id':aid,'status':'usage_or_price_violation',
                            'actual_cost_usd':str(cost),'cost_unknown':False})
                        raise ValueError('Tev context or tariff violation')
                    if body.get('model')!=tev.VERSION or body.get('provider')!=tev.PROVIDER:
                        durable(attempts,{'id':rid,'attempt_id':aid,'status':'identity_violation',
                            'actual_cost_usd':str(cost),'cost_unknown':False})
                        raise ValueError('Tev returned model/provider violation')
                    try:prediction,optional=smoke.validate_returned(body)
                    except (ValueError, TypeError):
                        if mode=='smoke':
                            durable(attempts,{'id':rid,'attempt_id':aid,'status':'invalid_native',
                                'actual_cost_usd':str(cost),'cost_unknown':False})
                            durable(parsed,{'id':rid,'attempt_id':aid,'prediction':None,'optional':None,
                                'input_tokens':usage['input_tokens'],'output_tokens':usage['output_tokens'],
                                'actual_cost_usd':str(cost)})
                            raise ValueError('Tev smoke invalid; inspect and stop')
                        outcome='invalid_native';prediction=None;optional=None;invalid+=1
                    else:outcome='ok'
                    durable(parsed,{'id':rid,'attempt_id':aid,'prediction':prediction,'optional':optional,
                        'input_tokens':usage['input_tokens'],'output_tokens':usage['output_tokens'],
                        'actual_cost_usd':str(cost)})
                    durable(attempts,{'id':rid,'attempt_id':aid,'status':outcome,
                        'actual_cost_usd':str(cost),'cost_unknown':False})
                    durable(journal,{'event':'request_finished','id':rid,'attempt_id':aid,
                        'status':outcome,'actual_cost_usd':str(cost),'utc':now()})
                except BaseException as error:
                    durable(journal,{'event':'phase_stopped','id':rid,'error_type':type(error).__name__,'utc':now()})
                    raise
            durable(journal,{'event':'phase_completed','stage':stage,'mode':mode,
                'request_count':len(stage_rows(stage,mode)),'intrinsic_invalid_count':invalid,'utc':now()})
    finally:ledger.close()
    return verify_phase_closure(stage,mode)


def inspection_template(stage):
    closure=verify_phase_closure(stage,'smoke')
    return {'schema':SCHEMA+'-smoke-inspection','decision':'pending','reviewer':None,
            'stage':stage,'closure':closure}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('prepare','verify','live-check','hold-source','stage-template','smoke','development','inspect-template'))
    p.add_argument('--stage',choices=PHASES,default='fresh1/P0')
    p.add_argument('--mode',choices=('smoke','development'),default='development')
    p.add_argument('--review',type=Path)
    a=p.parse_args()
    if a.action=='prepare':print(prepare());return
    print(verify())
    if a.action=='verify':return
    if a.action=='live-check':
        _,route=smoke.fetch_endpoint();tev.validate_catalog(route);print('live route passed; no inference');return
    if a.action=='hold-source':exact_budget();print(hold_source());return
    if a.action=='stage-template':print(json.dumps(stage_template(a.stage,a.mode),indent=2));return
    if a.action=='inspect-template':print(json.dumps(inspection_template(a.stage),indent=2));return
    if a.action!=a.mode or not a.review:p.error('mode/review differs')
    print(execute(a.stage,a.mode,a.review))


if __name__=='__main__':main()
