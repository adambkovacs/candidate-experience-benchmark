#!/usr/bin/env python3
"""One never-sent Gemma fresh3/P1 development request after DEV059 stopped."""

import argparse
import base64
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time

import gemma26_on_fresh_repeat_execution_v2 as frozen
import gemma26_on_fresh_repeat_study_v2 as study
import gemma26_fresh3_p0_p1_composite_successor_v1 as predecessor
import openrouter_paid_benchmark as paid
import paid_budget_partitions_v3 as partitions
from openrouter_budget_v3 import BudgetLedger
from prompt_admission import audit_response

ROOT = study.ROOT
BASE = study.BASE / 'fresh3-p1-dev060-suffix-v1'
STAGE = BASE / 'fresh3/P1'
MANIFEST = BASE / 'manifest.json'
TERMINAL = predecessor.BASE / 'fresh3-p1-terminal-pending-review.json'
TERMINAL_REVIEW = predecessor.BASE / 'fresh3-p1-interrupted.root-review.json'
OLD_RECONCILIATION = predecessor.BASE / 'fresh3-p1-interrupted-reconciliation.json'
OLD_BUDGET = predecessor.BASE / 'budget.json'
OLD_CHILD = predecessor.BASE / 'budget-gemma26-fresh3-p0-p1-v1.jsonl'
OLD_PARTITION = 'gemma26-fresh3-p0-p1-v1'
OLD_REVIEW = predecessor.BASE / 'fresh3-p1-development.root-review.json'
SCHEMA = 'gemma26-fresh3-p1-dev060-suffix-v1'
PARTITION_ID = 'gemma26-fresh3-p1-dev060-v1'
CAP = Decimal('0.02')
RESERVE = Decimal('0.01974272')
AUTHORITY = predecessor.AUTHORITY
AUTHORITY_CAP = predecessor.AUTHORITY_CAP
AUTHORITY_ID = 'openrouter-gemma26-fresh3-p1-dev060-v1'
AUTHORITY_SNAPSHOT = ROOT / 'results/clef-native-v1/postapproval-ledger-after-full-p0.jsonl'
AUTHORITY_SNAPSHOT_SHA = '8df9eb02d667acad771ade2d2258e0344bf5178a52da07083d4a4bb30b7b6685'
SOURCES = (
    'scripts/gemma26_on_fresh_repeat_execution_v2.py',
    'scripts/gemma26_on_fresh_repeat_study_v2.py',
    'scripts/gemma26_fresh3_p0_p1_composite_successor_v1.py',
    'scripts/openrouter_paid_benchmark.py',
    'scripts/paid_budget_partitions_v3.py',
    'scripts/openrouter_budget_v3.py',
    'scripts/prompt_admission.py',
)
ROUTE_FIELDS = ('tag', 'provider_name', 'quantization', 'model_id',
                'context_length', 'max_prompt_tokens', 'max_completion_tokens',
                'supported_parameters', 'pricing')
PREFIX_FILES = ('claim', 'journal', 'attempts', 'responses', 'wire')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def stage_paths():
    return {name: STAGE / f'suffix.{"claim.json" if name == "claim" else name + ".jsonl"}'
            for name in PREFIX_FILES}


def old_paths():
    folder = study.BASE / 'fresh3/P1'
    return {name: folder / f'development.{"claim.json" if name == "claim" else name + ".jsonl"}'
            for name in PREFIX_FILES}


def selected_request():
    plan = study.verify('fresh3', sha(study.BASE / 'fresh3/manifest.json'))
    request = plan['conditions']['P1']['development'][59]
    if request['record_id'] != 'DEV-060' or study.digest(json.dumps(
            request['payload'], sort_keys=True)) != request['request_sha256']:
        raise ValueError('Frozen DEV060 request changed')
    return plan, request


def prior_gate():
    """Bind the stopped original phase without converting DEV059 into a retry."""
    predecessor.verify()
    plan, request = selected_request()
    paths = old_paths()
    actual = {name: sha(path) for name, path in paths.items()}
    terminal = json.loads(TERMINAL.read_text())
    # The owner receipt is an immutable observation, not an approval to spend.
    if (terminal.get('schema') != 'gemma26-fresh3-p1-interrupted-terminal-v1' or
            terminal.get('approved') is not False or
            terminal.get('status') != 'stopped_pending_reconciliation' or
            terminal.get('score') is not None or
            terminal.get('reference_labels_read') is not False or
            (terminal.get('expected_attempts'), terminal.get('attempted'),
             terminal.get('valid'), terminal.get('failed'), terminal.get('never_sent')) !=
            (126, 125, 124, 1, 1) or terminal.get('never_sent_ids') != ['DEV-060']):
        raise ValueError('Expected immutable stopped P1 terminal observation')
    stage = terminal.get('stages', {}).get('P1/development', {})
    if ((stage.get('expected'), stage.get('attempted'), stage.get('valid'),
         stage.get('failed'), stage.get('never_sent'), stage.get('terminal_event')) !=
            (60, 59, 58, 1, 1, 'phase_stopped')):
        raise ValueError('Stopped P1 terminal stage counts differ')
    source = stage.get('sourceSha256')
    if not isinstance(source, dict) or any(source.get(name) != actual[name] for name in PREFIX_FILES):
        raise ValueError('Original P1 terminal source hashes differ')
    claim = json.loads(paths['claim'].read_text())
    journal, attempts, responses, wire = (rows(paths[name]) for name in
                                         ('journal', 'attempts', 'responses', 'wire'))
    planned = plan['conditions']['P1']['development']
    ids = [x['record_id'] for x in planned]
    if (claim.get('series_id') != study.SERIES or claim.get('fresh_pass') != 'fresh3' or
            claim.get('condition') != 'P1' or claim.get('phase') != 'development' or
            claim.get('manifest_sha256') != sha(study.BASE / 'fresh3/manifest.json') or
            claim.get('root_review_sha256') != sha(OLD_REVIEW) or
            [x.get('id') for x in attempts] != ids[:59] or
            [x.get('id') for x in responses] != ids[:58] or
            [x.get('id') for x in wire] != ids[:58] or
            journal[-1].get('event') != 'phase_stopped' or
            journal[-1].get('id') != 'DEV-059' or
            journal[-1].get('reason') != 'service_error'):
        raise ValueError('Original P1 stopped prefix differs')
    if len(journal) != 179 or journal[0].get('event') != 'phase_started':
        raise ValueError('Original P1 journal lifecycle differs')
    for i, (attempt, response, capture) in enumerate(zip(attempts[:58], responses, wire)):
        expected = planned[i]
        if (attempt.get('id') != expected['record_id'] or
                attempt.get('request') != expected['payload'] or
                attempt.get('request_sha256') != expected['request_sha256'] or
                attempt.get('status') != 'ok' or attempt.get('billing_ok') is not True or
                attempt.get('cost_unknown') is not False or
                attempt.get('attempt_id') != response.get('attempt_id') or
                attempt.get('attempt_id') != capture.get('attempt_id') or
                response.get('raw_response') != attempt.get('raw_response') or
                capture.get('http_status') != 200 or
                capture.get('body_truncated_at_limit') is not False or
                capture.get('body_token_redacted') is not False or
                capture.get('read_error') is not None or
                json.loads(base64.b64decode(capture['body_base64'])) != response['raw_response'] or
                frozen.classify(response['raw_response'], attempt['model_catalog_entry'],
                                attempt['provider_endpoint'])['prediction'] != attempt.get('prediction') or
                frozen.classify(response['raw_response'], attempt['model_catalog_entry'],
                                attempt['provider_endpoint'])['status'] != 'ok' or
                paid.number(attempt['observed_cost_usd']) !=
                paid.number(response['raw_response']['usage']['cost'])):
            raise ValueError('Original P1 valid response differs from frozen request or wire')
    failed = attempts[-1]
    if (failed.get('id') != 'DEV-059' or failed.get('attempt_id') !=
            '84558e99-3982-449f-ba47-4f2f3176f2dc' or
            failed.get('request') != planned[58]['payload'] or
            failed.get('request_sha256') != planned[58]['request_sha256'] or
            failed.get('status') != 'service_error' or failed.get('error_type') != 'TimeoutError' or
            failed.get('cost_unknown') is not True or failed.get('billing_ok') is not False or
            failed.get('observed_cost_usd') is not None or
            paid.number(failed['reserved_cost_usd']) != RESERVE):
        raise ValueError('DEV059 unknown outcome changed')
    observed_failure = terminal.get('failure', {})
    if (observed_failure.get('id') != 'DEV-059' or
            observed_failure.get('attempt_id') != failed['attempt_id'] or
            observed_failure.get('request_sha256') != failed['request_sha256'] or
            observed_failure.get('status') != failed['status'] or
            observed_failure.get('error_type') != failed['error_type'] or
            observed_failure.get('provider_execution') != 'unknown' or
            observed_failure.get('provider_charge') != 'unknown' or
            observed_failure.get('reserved_cost_usd') != str(RESERVE)):
        raise ValueError('Terminal observation of DEV059 differs')
    child = terminal.get('child', {})
    if (child.get('partition_id') != OLD_PARTITION or child.get('cap_usd') != '0.40' or
            child.get('pending_unknown_reserve_usd') != str(RESERVE) or
            child.get('pending_attempt_ids') != [failed['attempt_id']] or
            child.get('closed') is not False or child.get('reconciled') is not False):
        raise ValueError('Terminal pending child observation differs')
    top_sources = terminal.get('sourceSha256', {})
    for key, binding in top_sources.items():
        if key == 'child_ledger_pending':
            continue
        if (not isinstance(binding, dict) or
                not isinstance(binding.get('path'), str) or
                (ROOT / binding['path']).resolve().is_relative_to(ROOT.resolve()) is not True or
                sha(ROOT / binding['path']) != binding.get('sha256')):
            raise ValueError('Terminal source binding differs: ' + key)
    if (top_sources.get('successor_manifest', {}).get('path') !=
            str(predecessor.MANIFEST.relative_to(ROOT)) or
            top_sources.get('budget_manifest', {}).get('path') !=
            str(OLD_BUDGET.relative_to(ROOT)) or
            top_sources.get('p1_development_review', {}).get('path') !=
            str(OLD_REVIEW.relative_to(ROOT))):
        raise ValueError('Terminal predecessor paths differ')
    old_lines = OLD_CHILD.read_bytes().splitlines(keepends=True)
    pending_child = top_sources.get('child_ledger_pending', {})
    if (len(old_lines) < 3 or pending_child.get('path') != str(OLD_CHILD.relative_to(ROOT)) or
            hashlib.sha256(b''.join(old_lines[:-2])).hexdigest() != pending_child.get('sha256')):
        raise ValueError('Original pending child prefix changed during reconciliation')
    root_review = json.loads(TERMINAL_REVIEW.read_text())
    if (root_review.get('schema') != 'gemma26-fresh3-p1-interrupted-root-review-v1' or
            root_review.get('approved') is not True or
            root_review.get('reviewer') != 'root' or
            root_review.get('proposal_sha256') != sha(TERMINAL) or
            root_review.get('global_hold') != 'unchanged'):
        raise ValueError('Independent root review of interruption missing')
    reconciliation = json.loads(OLD_RECONCILIATION.read_text())
    if (reconciliation.get('event') != 'partition_reconciled' or
            reconciliation.get('partition_id') != OLD_PARTITION or
            reconciliation.get('child_ledger') != str(OLD_CHILD.resolve()) or
            reconciliation.get('child_sha256') != sha(OLD_CHILD) or
            paid.number(reconciliation.get('known_actual_usd')) != Decimal('0.03995497') or
            paid.number(reconciliation.get('unknown_upper_bound_usd')) != RESERVE or
            paid.number(reconciliation.get('unused_allocation_released_usd')) !=
            Decimal('0.34030231')):
        raise ValueError('Original child reconciliation receipt differs')
    if [e.get('id') for e in journal if e.get('event') == 'request_started'] != ids[:59] or \
            [e.get('id') for e in journal if e.get('event') == 'request_finished'] != ids[:59]:
        raise ValueError('Original P1 journal request order differs')
    route = {key: attempts[57]['provider_endpoint'].get(key) for key in ROUTE_FIELDS}
    return {'terminal_sha256': sha(TERMINAL),
            'terminal_review_sha256': sha(TERMINAL_REVIEW),
            'old_reconciliation_sha256': sha(OLD_RECONCILIATION),
            'sealed_old_child_sha256': sha(OLD_CHILD),
            'prefix_sha256': actual,
            'original_review_sha256': sha(OLD_REVIEW), 'failed_id': 'DEV-059',
            'failed_attempt_id': failed['attempt_id'],
            'failed_request_sha256': failed['request_sha256'],
            'never_sent_id': request['record_id'], 'route_fields': route}


def manifest_value():
    gate = prior_gate()
    _, request = selected_request()
    return {'schema': SCHEMA, 'status': 'offline_prepared_no_allocation_no_dispatch',
            'series_id': study.SERIES, 'configuration_id': study.CONFIG,
            'fresh_pass': 'fresh3', 'condition': 'P1', 'stage': 'suffix',
            'preserved_unknown_id': 'DEV-059', 'ids': ['DEV-060'],
            'plan_sha256': sha(study.BASE / 'fresh3/manifest.json'),
            'prior': gate, 'prior_gate_sha256': digest(gate),
            'source_sha256': {name: sha(ROOT / name) for name in SOURCES},
            'child_cap_usd': str(CAP), 'per_request_reserve_usd': str(RESERVE),
            'partition_id': PARTITION_ID, 'global_hold_id': AUTHORITY_ID,
            'request': request, 'reference_labels_sent': False}


def prepare():
    value = manifest_value()
    BASE.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open('x') as file:
        json.dump(value, file, indent=2)
        file.write('\n')
        file.flush()
        os.fsync(file.fileno())
    return sha(MANIFEST)


def verify():
    saved = json.loads(MANIFEST.read_text())
    if saved != manifest_value():
        raise ValueError('DEV060 successor manifest or prior terminal changed')
    return saved, sha(MANIFEST)


def reconciled_old_child():
    """Require explicit upper-bound settlement and sealed prior child."""
    if not OLD_CHILD.is_file() or not frozen.MASTER.is_file():
        raise ValueError('Original child or master ledger missing')
    budget = json.loads(OLD_BUDGET.read_text())
    entries = [e for e in budget.get('partitions', []) if e.get('id') == OLD_PARTITION]
    if len(entries) != 1 or Path(entries[0]['child_ledger']).resolve() != OLD_CHILD.resolve():
        raise ValueError('Original child budget identity differs')
    child = BudgetLedger(OLD_CHILD, cap_limit=Decimal('0.40'))
    try:
        _, pending, blocked = child.state()
        unknown = [e for e in child.events if e.get('event') == 'unknown_cost_accounted_as_upper_bound'
                   and e.get('attempt_id') == '84558e99-3982-449f-ba47-4f2f3176f2dc']
        all_unknown = [e for e in child.events if e.get('event') == 'unknown_cost_accounted_as_upper_bound']
        reserves = [e for e in child.events if e.get('event') == 'reserve']
        settles = [e for e in child.events if e.get('event') == 'settle']
        if (pending or blocked or not child.closed or len(unknown) != 1 or
                len(all_unknown) != 1 or len(reserves) != 125 or len(settles) != 124 or
                reserves[-1].get('record_id') != 'DEV-059' or
                reserves[-1].get('attempt_id') != unknown[0]['attempt_id'] or
                paid.number(unknown[0]['usd']) != RESERVE or
                unknown[0].get('actual_cost_usd') is not None or
                unknown[0].get('evidence_path') != str(old_paths()['attempts'].resolve()) or
                unknown[0].get('evidence_sha256') != sha(old_paths()['attempts'])):
            raise ValueError('Original DEV059 upper-bound hold or seal missing')
        accounted = child.accounted()
    finally:
        child.close()
    master = BudgetLedger(frozen.MASTER)
    try:
        _, pending, blocked = master.state()
        old = master.partitions.get(OLD_PARTITION)
        matches = [e for e in master.events if e.get('event') == 'partition_reconciled'
                   and e.get('partition_id') == OLD_PARTITION]
        if (pending or blocked or not old or old['active'] or len(matches) != 1 or
                matches[0].get('child_sha256') != sha(OLD_CHILD) or
                paid.number(matches[0]['unknown_upper_bound_usd']) < RESERVE or
                paid.number(matches[0]['known_actual_usd']) +
                paid.number(matches[0]['unknown_upper_bound_usd']) != accounted):
            raise ValueError('Original child partition reconciliation missing')
        event = matches[0]
    finally:
        master.close()
    return {'old_child_sha256': sha(OLD_CHILD),
            'old_reconciliation_event_sha256': digest(event),
            'unknown_upper_bound_usd': str(RESERVE)}


def budget_entry(path):
    path = Path(path).resolve()
    if path != (BASE / 'budget.json').resolve():
        raise ValueError('New child budget path differs')
    budget = json.loads(path.read_text())
    matches = [e for e in budget.get('partitions', []) if e.get('id') == PARTITION_ID]
    if (budget.get('version') != 'paid-partitions-v1' or
            budget.get('master_ledger') != str(frozen.MASTER.resolve()) or
            len(matches) != 1 or matches[0].get('cap_usd') != str(CAP) or
            matches[0].get('model') != study.MODEL or
            matches[0].get('provider') != study.PROVIDER or
            matches[0].get('reasoning') != study.EFFORT or
            Path(matches[0]['child_ledger']).resolve() !=
            (BASE / f'budget-{PARTITION_ID}.jsonl').resolve()):
        raise ValueError('New child allocation differs')
    return matches[0]


def expected_review(manifest, manifest_sha, budget_path, authority_head_sha):
    if (not isinstance(authority_head_sha, str) or len(authority_head_sha) != 64 or
            any(c not in '0123456789abcdef' for c in authority_head_sha)):
        raise ValueError('Reviewed global authority head hash required')
    budget_entry(budget_path)
    old = reconciled_old_child()
    return {'schema': SCHEMA + '-root-review', 'approved': True,
            'reviewer': 'root',
            'manifest_sha256': manifest_sha, 'controller_sha256': sha(__file__),
            'prior_gate_sha256': manifest['prior_gate_sha256'],
            'terminal_sha256': manifest['prior']['terminal_sha256'],
            **old, 'budget_manifest_sha256': sha(budget_path),
            'global_authority_head_sha256': authority_head_sha,
            'global_authority_approval_sha256': predecessor.AUTHORITY_APPROVAL_SHA,
            'global_authority_hold_id': AUTHORITY_ID,
            'global_authority_hold_usd': str(CAP),
            'partition_id': PARTITION_ID, 'child_cap_usd': str(CAP),
            'fresh_pass': 'fresh3', 'condition': 'P1', 'stage': 'suffix',
            'ids': ['DEV-060'],
            'request_sha256': [manifest['request']['request_sha256']],
            'preserved_unknown_id': 'DEV-059', 'reference_labels_sent': False}


def hold_authority(expected_head, review_sha):
    if sha(AUTHORITY_SNAPSHOT) != AUTHORITY_SNAPSHOT_SHA:
        raise ValueError('Authority provenance snapshot changed')
    baseline = rows(AUTHORITY_SNAPSHOT)
    with AUTHORITY.open('r+') as file:
        fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        raw = file.read().encode()
        if not raw.endswith(b'\n') or hashlib.sha256(raw).hexdigest() != expected_head:
            raise ValueError('Reviewed global authority head changed')
        events = [json.loads(x) for x in raw.splitlines()]
        if (events[:len(baseline)] != baseline or
                events[0] != {'event': 'authority', 'kind': 'postapproval-paid-work-v1',
                              'cap_usd': str(AUTHORITY_CAP),
                              'decision_key': predecessor.AUTHORITY_DECISION_KEY,
                              'approval_sha256': predecessor.AUTHORITY_APPROVAL_SHA}):
            raise ValueError('Global authority provenance changed')
        total = Decimal(0)
        seen = set()
        for event in events[1:]:
            if (set(event) != {'event', 'id', 'usd', 'source_sha256'} or
                    event['event'] != 'hold' or event['id'] in seen or
                    not isinstance(event['source_sha256'], str) or
                    len(event['source_sha256']) != 64):
                raise ValueError('Malformed global hold')
            amount = paid.number(event['usd'])
            if amount <= 0 or event['id'] == AUTHORITY_ID:
                raise ValueError('Duplicate or invalid global hold')
            seen.add(event['id'])
            total += amount
        old_hold = {'event': 'hold', 'id': predecessor.AUTHORITY_ID,
                    'usd': str(predecessor.CHILD_CAP),
                    'source_sha256': predecessor.global_hold_source(OLD_BUDGET, OLD_PARTITION)}
        if events.count(old_hold) != 1:
            raise ValueError('Original Gemma global hold missing or changed')
        if total + CAP > AUTHORITY_CAP:
            raise ValueError('Global paid-work cap cannot fit DEV060 hold')
        file.seek(0, os.SEEK_END)
        frozen.durable(file, {'event': 'hold', 'id': AUTHORITY_ID,
                              'usd': str(CAP), 'source_sha256': review_sha})


def checked_route(plan, expected):
    model, endpoint, reserve = frozen.live_controls(plan, 'P1')
    if reserve != RESERVE or any(endpoint.get(k) != expected.get(k) for k in ROUTE_FIELDS):
        raise ValueError('Fresh exact Gemma route, price, or reserve changed')
    return model, endpoint


def run(review_path, budget_path, env_file=None):
    manifest, manifest_sha = verify()
    review_path = Path(review_path).resolve()
    if review_path != (STAGE / 'suffix.root-review.json').resolve():
        raise ValueError('DEV060 root review path differs')
    review = json.loads(review_path.read_text())
    if review != expected_review(manifest, manifest_sha, budget_path,
                                 review.get('global_authority_head_sha256')):
        raise ValueError('DEV060 root review differs')
    paths = stage_paths()
    if any(path.exists() for path in paths.values()):
        raise FileExistsError('DEV060 already claimed; no replay')
    plan, request = selected_request()
    model, endpoint = checked_route(plan, manifest['prior']['route_fields'])
    ledger = partitions.open_partition(frozen.MASTER, budget_path, PARTITION_ID,
                                       study.MODEL, study.PROVIDER, study.EFFORT)
    try:
        _, pending, blocked = ledger.state()
        if (ledger.cap != CAP or ledger.master_cap != Decimal('12.38') or
                pending or blocked or ledger.closed or ledger.accounted() + RESERVE > CAP):
            raise ValueError('New DEV060 child unavailable for full reserve')
        token = paid.load_key(env_file)
        hold_authority(review['global_authority_head_sha256'], sha(review_path))
        STAGE.mkdir(parents=True, exist_ok=True)
        with paths['claim'].open('x') as out:
            frozen.durable(out, {'schema': SCHEMA + '-claim', 'manifest_sha256': manifest_sha,
                                 'review_sha256': sha(review_path), 'ids': ['DEV-060'],
                                 'claimed_utc': frozen.utc()})
        with paths['journal'].open('x') as journal, paths['attempts'].open('x') as attempts, \
             paths['responses'].open('x') as responses, paths['wire'].open('x') as wire:
            frozen.durable(journal, {'event': 'phase_started', 'series_id': SCHEMA,
                                     'fresh_pass': 'fresh3', 'condition': 'P1',
                                     'stage': 'suffix', 'claim_sha256': sha(paths['claim']),
                                     'utc': frozen.utc()})
            for name, expected in manifest['source_sha256'].items():
                if sha(ROOT / name) != expected:
                    raise ValueError('Pinned runtime source changed: ' + name)
            if digest(prior_gate()) != manifest['prior_gate_sha256']:
                raise ValueError('Interrupted P1 prefix changed before DEV060')
            model, endpoint = checked_route(plan, manifest['prior']['route_fields'])
            frozen.durable(journal, {'event': 'request_intent', 'id': 'DEV-060',
                                     'request_sha256': request['request_sha256'],
                                     'utc': frozen.utc()})
            attempt_id = ledger.reserve(RESERVE, 'DEV-060')
            frozen.durable(journal, {'event': 'request_started', 'id': 'DEV-060',
                                     'attempt_id': attempt_id,
                                     'request_sha256': request['request_sha256'],
                                     'utc': frozen.utc()})
            record = {'id': 'DEV-060', 'series_id': study.SERIES,
                      'fresh_pass': 'fresh3', 'condition': 'P1', 'phase': 'suffix',
                      'attempt_id': attempt_id, 'request': request['payload'],
                      'request_sha256': request['request_sha256'],
                      'manifest_sha256': manifest_sha, 'requested_model': study.MODEL,
                      'reasoning_effort': study.EFFORT, 'provider_endpoint': endpoint,
                      'model_catalog_entry': model, 'reference_labels_read': False,
                      'reserved_cost_usd': str(RESERVE), 'budget_partition_id': PARTITION_ID,
                      'started_utc': frozen.utc()}
            actual = None
            started = time.perf_counter()
            wire_before = wire.tell()
            try:
                body = frozen.fetch_captured(request['payload'], token, wire, 'DEV-060',
                                             attempt_id, request['request_sha256'])
                record['raw_response'] = body
                frozen.durable(responses, {'id': 'DEV-060', 'attempt_id': attempt_id,
                                           'request_sha256': request['request_sha256'],
                                           'raw_response': body, 'received_utc': frozen.utc()})
                if isinstance(body, dict):
                    usage = body.get('usage') or {}
                    if usage.get('cost') is not None:
                        actual = paid.number(usage['cost'])
                record.update(frozen.classify(body, model, endpoint))
            except Exception as exc:
                record.update(status='service_error', error_type=type(exc).__name__)
                if isinstance(exc, frozen.CapturedHTTPError):
                    record.update(http_status=exc.status, error_body=exc.body,
                                  error_headers=exc.headers)
                    frozen.durable(responses, {'id': 'DEV-060', 'attempt_id': attempt_id,
                                               'request_sha256': request['request_sha256'],
                                               'http_status': exc.status,
                                               'error_body': exc.body,
                                               'error_headers': exc.headers,
                                               'received_utc': frozen.utc()})
                elif wire.tell() > wire_before:
                    frozen.durable(responses, {'id': 'DEV-060', 'attempt_id': attempt_id,
                                               'request_sha256': request['request_sha256'],
                                               'capture_error': type(exc).__name__,
                                               'received_utc': frozen.utc()})
            billing_ok = ledger.settle(attempt_id, actual)
            record.update(elapsed_seconds=time.perf_counter() - started,
                          timing_boundary='Client request through raw capture and billing settlement; not pure inference time.',
                          observed_cost_usd=str(actual) if actual is not None else None,
                          cost_unknown=actual is None, billing_ok=billing_ok)
            if record.get('raw_response') is not None:
                diagnostic = audit_response(record, 'openrouter_paid_v1',
                                            endpoint['context_length'] - 4096)
                record['response_diagnostic'] = diagnostic
                if not diagnostic['passed'] and record['status'] == 'ok':
                    record['status'] = 'prompt_admission_failure'
            frozen.durable(attempts, record)
            frozen.durable(journal, {'event': 'request_finished', 'id': 'DEV-060',
                                     'attempt_id': attempt_id, 'status': record['status'],
                                     'billing_ok': billing_ok, 'cost_unknown': record['cost_unknown'],
                                     'observed_cost_usd': record['observed_cost_usd'],
                                     'utc': frozen.utc()})
            completed = frozen.continue_record(record, 'development')
            frozen.durable(journal, {'event': 'phase_completed' if completed else 'phase_stopped',
                                     'id': 'DEV-060', 'reason': None if completed else record['status'],
                                     'utc': frozen.utc()})
            return completed
    finally:
        if paths['journal'].exists():
            events = rows(paths['journal'])
            if not events or events[-1].get('event') not in ('phase_completed', 'phase_stopped', 'phase_aborted'):
                with paths['journal'].open('a') as out:
                    frozen.durable(out, {'event': 'phase_aborted',
                                         'reason': 'exception_or_interruption', 'utc': frozen.utc()})
        ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify', 'run'))
    parser.add_argument('--root-review-receipt', type=Path)
    parser.add_argument('--budget-manifest', type=Path)
    parser.add_argument('--env-file', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare':
        print(prepare())
    elif args.action == 'verify':
        print(verify()[1])
    else:
        if not args.root_review_receipt or not args.budget_manifest:
            parser.error('run requires --root-review-receipt and --budget-manifest')
        print(json.dumps({'completed': run(args.root_review_receipt,
                                           args.budget_manifest, args.env_file)}))


if __name__ == '__main__':
    main()
