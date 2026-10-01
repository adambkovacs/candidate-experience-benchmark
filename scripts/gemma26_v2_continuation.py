#!/usr/bin/env python3
"""Versioned Gemma-on continuation after fresh1/P2 DEV-007 HTTP 429.

Freeze and verify are offline. Dispatch is a separate, root-receipted command;
this module never finalizes an unknown charge or allocates a budget partition.
"""
import argparse
import base64
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import time

from development_benchmark import ROOT
import gemma26_on_fresh_repeat_study_v2 as study
import gemma26_on_fresh_repeat_execution_v2 as original
import openrouter_paid_benchmark as paid
import paid_budget_partitions_v3 as partitions
from prompt_admission import audit_response

SCHEMA = 'gemma26-on-v2-interruption-continuation-v1'
BASE = study.BASE
OUTPUT = BASE / 'interruption-continuation-v1'
MASTER = original.MASTER
PARTITION_ID = 'gemma26-on-v2-interruption-v1'
RESERVE = Decimal('0.01974272')
IDS = [f'DEV-{i:03d}' for i in range(1, 61)]
SUFFIX = IDS[7:]
PLAN_SHAS = {
    'fresh1': 'fba7273c9691deff399e38e34970c642f268b761659132734962a8273aadca29',
    'fresh2': 'b1b89af36ac6137c7c085a4d51747038cbcc81d1a3ebf05b8b209adb2f9924d2',
    'fresh3': '86750c9372d18956e6665e8a23537fd87752b0da06144ce1f1254735093a65c3',
}
PREFIX_SHAS = {
    'claim': 'ff0fdeebb99affb68ca13816544ea1b14402db0069964b23af7ba7ce6ce043ff',
    'journal': 'b99211c175e21c7206c40b8ea84464efcdd92957a68bfe3039a84923e68faedd',
    'attempts': 'fdf0fcf388abcf4b7df4d8fa14b840f59193561dda59964bfba904dc3dd63fb8',
    'responses': '59a7c366d692a91f6c52c45f7757decf4346d04e67746a1feb2e1cb4d5e8feb5',
    'wire': 'faced8d96ff7dca117adf56c74111d8b1b130329601b7437e4ce25b10167d653',
    'review': '29ba17f71180a51c8608a40fb7922eeb313d444185fcd49b2522c8d479ec2054',
}
OLD_LEDGER_SHA = '12cff0f8833e8c1744854f0fb908814e240471126acb3107a06ee63031d62d2e'
OLD_LEDGER_LINES = 272
OLD_LEDGER = BASE / 'budget-partitions-v1-gemma26-on-v2.jsonl'
OLD_BUDGET = BASE / 'budget-partitions-v1.json'
OLD_PARTITION = 'gemma26-on-v2'
OLD_PHASE = BASE / 'fresh1/P2'
STAGES = [('fresh1', 'P2', 'suffix')]
for _pass in ('fresh2', 'fresh3'):
    for _condition in study.ORDERS[_pass]:
        STAGES.extend(((_pass, _condition, 'smoke'), (_pass, _condition, 'development')))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    data = Path(path).read_bytes()
    if data and not data.endswith(b'\n'):
        raise ValueError('Incomplete JSONL evidence: ' + str(path))
    return [json.loads(line) for line in data.splitlines() if line.strip()]


def binding(path):
    path = Path(path).resolve()
    return {'path': str(path.relative_to(ROOT.resolve())), 'sha256': sha(path)}


def read_bound(item):
    path = (ROOT / item['path']).resolve()
    path.relative_to(ROOT.resolve())
    if sha(path) != item['sha256']:
        raise ValueError('Bound source changed: ' + item['path'])
    return path


def source_plan(repeat):
    return study.verify(repeat, PLAN_SHAS[repeat])


def selected_requests(repeat, condition, stage):
    if (repeat, condition, stage) not in STAGES:
        raise ValueError('Stage outside versioned continuation schedule')
    plan = source_plan(repeat)
    requests = plan['conditions'][condition]['development' if stage == 'suffix' else stage]
    selected = requests[7:] if stage == 'suffix' else requests
    expected = SUFFIX if stage == 'suffix' else IDS[:3] if stage == 'smoke' else IDS
    if [r['record_id'] for r in selected] != expected:
        raise ValueError('Frozen selected request membership differs')
    return selected


def prefix_paths():
    return {kind: OLD_PHASE / ('development.' + name) for kind, name in {
        'claim': 'claim.json', 'journal': 'journal.jsonl',
        'attempts': 'attempts.jsonl', 'responses': 'responses.jsonl',
        'wire': 'wire.jsonl', 'review': 'root-review.json'}.items()}


def verify_stopped_prefix():
    """Verify exact original request/outcome bytes without reading references."""
    plans = {repeat: source_plan(repeat) for repeat in study.ORDERS}
    for condition in ('P0', 'P1'):
        original.verify_phase_closure(plans['fresh1'], condition, 'development')
    original.verify_phase_closure(plans['fresh1'], 'P2', 'smoke')
    paths = prefix_paths()
    for kind, path in paths.items():
        if sha(path) != PREFIX_SHAS[kind]:
            raise ValueError('Original stopped ' + kind + ' changed')
    claim = json.loads(paths['claim'].read_text())
    if any(claim.get(k) != v for k, v in {
            'series_id': study.SERIES, 'fresh_pass': 'fresh1', 'condition': 'P2',
            'phase': 'development', 'manifest_sha256': PLAN_SHAS['fresh1'],
            'root_review_sha256': PREFIX_SHAS['review']}.items()):
        raise ValueError('Original stopped claim differs')
    review = json.loads(paths['review'].read_text())
    if (review.get('approved') is not True or
            review.get('stage') != 'fresh1/P2/development' or
            review.get('plan_sha256') != PLAN_SHAS):
        raise ValueError('Original root review differs')
    attempts, responses, wire, journal = (rows(paths[k]) for k in
                                             ('attempts', 'responses', 'wire', 'journal'))
    if not all([len(attempts) == 7, len(responses) == 7, len(wire) == 7,
                len(journal) == 23, journal[0].get('event') == 'phase_started',
                journal[-1].get('event') == 'phase_stopped',
                journal[-1].get('id') == 'DEV-007',
                journal[-1].get('reason') == 'service_error']):
        raise ValueError('Original stopped lifecycle differs')
    expected = plans['fresh1']['conditions']['P2']['development'][:7]
    attempt_ids = []
    for index, (request, record, raw, captured) in enumerate(zip(expected, attempts, responses, wire)):
        rid = IDS[index]
        attempt = record.get('attempt_id')
        if (not isinstance(attempt, str) or not attempt or attempt in attempt_ids or
                record.get('id') != rid or raw.get('id') != rid or captured.get('id') != rid or
                raw.get('attempt_id') != attempt or captured.get('attempt_id') != attempt or
                record.get('request') != request['payload'] or
                record.get('request_sha256') != request['request_sha256'] or
                raw.get('request_sha256') != request['request_sha256'] or
                captured.get('request_sha256') != request['request_sha256'] or
                record.get('reference_labels_read') is not False or
                paid.number(record.get('reserved_cost_usd')) != RESERVE):
            raise ValueError('Original attempt or frozen request differs at ' + rid)
        attempt_ids.append(attempt)
        intent, started, finished = journal[1 + index * 3:4 + index * 3]
        if (intent.get('event'), intent.get('id'), intent.get('request_sha256')) != (
                'request_intent', rid, request['request_sha256']) or (
                started.get('event'), started.get('id'), started.get('attempt_id'),
                started.get('request_sha256')) != (
                'request_started', rid, attempt, request['request_sha256']) or (
                finished.get('event'), finished.get('id'), finished.get('attempt_id'),
                finished.get('status'), finished.get('billing_ok'),
                finished.get('cost_unknown'), finished.get('observed_cost_usd')) != (
                'request_finished', rid, attempt, record['status'],
                record['billing_ok'], record['cost_unknown'], record['observed_cost_usd']):
            raise ValueError('Original journal attempt binding differs at ' + rid)
        body = base64.b64decode(captured['body_base64'], validate=True).decode('utf-8')
        if index < 6:
            if (record.get('status') != 'ok' or record.get('billing_ok') is not True or
                    record.get('cost_unknown') is not False or
                    record.get('observed_cost_usd') is None or
                    raw.get('raw_response') != record.get('raw_response') or
                    json.loads(body) != record.get('raw_response') or
                    captured.get('http_status') != 200):
                raise ValueError('Original known-billed response differs at ' + rid)
        elif (record.get('status') != 'service_error' or record.get('billing_ok') is not False or
              record.get('cost_unknown') is not True or record.get('observed_cost_usd') is not None or
              record.get('http_status') != 429 or captured.get('http_status') != 429 or
              raw.get('error_body') != record.get('error_body') or body != record.get('error_body') or
              json.loads(body).get('error', {}).get('metadata', {}).get('raw') is None):
            raise ValueError('Original unknown-cost 429 differs')
        if captured.get('body_truncated_at_limit') is not False or captured.get('read_error') is not None:
            raise ValueError('Original wire capture incomplete')
    return {'failed_attempt_id': attempt_ids[-1],
            'prefix_ids': IDS[:7], 'never_sent_ids': SUFFIX,
            'files': {k: binding(v) for k, v in paths.items()},
            'known_prefix_usd': str(sum((paid.number(x['observed_cost_usd']) for x in attempts[:6]), Decimal(0)))}


def verify_old_seal(reconciliation_path, prefix):
    """Require explicit full-bound accounting and terminal reconciliation."""
    events = rows(OLD_LEDGER)
    lines = OLD_LEDGER.read_bytes().splitlines(keepends=True)
    if (len(lines) < OLD_LEDGER_LINES or
            hashlib.sha256(b''.join(lines[:OLD_LEDGER_LINES])).hexdigest() != OLD_LEDGER_SHA):
        raise ValueError('Original child ledger prefix changed')
    failed = [e for e in events if e.get('attempt_id') == prefix['failed_attempt_id']]
    if len(failed) != 2 or failed[0] != {
            'event': 'reserve', 'attempt_id': prefix['failed_attempt_id'],
            'record_id': 'DEV-007', 'usd': str(RESERVE)}:
        raise ValueError('Failed reservation differs')
    unknown = failed[1]
    if (unknown.get('event') != 'unknown_cost_accounted_as_upper_bound' or
            paid.number(unknown.get('usd')) != RESERVE or
            unknown.get('actual_cost_usd') is not None or
            unknown.get('evidence_sha256') != PREFIX_SHAS['attempts'] or
            Path(unknown.get('evidence_path', '')).resolve() != prefix_paths()['attempts'].resolve() or
            not isinstance(unknown.get('reason'), str) or not unknown['reason'].strip()):
        raise ValueError('DEV-007 unknown upper bound has not been accounted')
    if len(events) != OLD_LEDGER_LINES + 2 or events[-1].get('event') != 'partition_closed':
        raise ValueError('Original child partition is not exclusively sealed')
    known = sum((paid.number(e['usd']) for e in events if e['event'] == 'settle'), Decimal(0))
    bounds = sum((paid.number(e['usd']) for e in events
                  if e['event'] == 'unknown_cost_accounted_as_upper_bound'), Decimal(0))
    if (known, bounds, paid.number(events[0]['cap_usd'])) != (
            Decimal('0.04530062'), RESERVE, Decimal('0.40')):
        raise ValueError('Original child accounting differs')
    path = Path(reconciliation_path).resolve()
    path.relative_to(ROOT.resolve())
    event = json.loads(path.read_text())
    expected = {'event': 'partition_reconciled', 'partition_id': OLD_PARTITION,
                'known_actual_usd': str(known), 'unknown_upper_bound_usd': str(bounds),
                'unused_allocation_released_usd': str(Decimal('0.40') - known - bounds),
                'child_ledger': str(OLD_LEDGER.resolve()), 'child_sha256': sha(OLD_LEDGER)}
    if event != expected or event not in rows(MASTER):
        raise ValueError('Original child master reconciliation missing or changed')
    return {'old_child_ledger': binding(OLD_LEDGER), 'old_reconciliation': binding(path),
            'known_actual_usd': str(known), 'unknown_upper_bound_usd': str(bounds)}


def budget_entry(path, require_active=True):
    path = Path(path).resolve()
    if path != (OUTPUT / 'budget.json').resolve():
        raise ValueError('New budget manifest path differs')
    data = json.loads(path.read_text())
    entries = data.get('partitions')
    if (data.get('version') != 'paid-partitions-v1' or
            data.get('master_ledger') != str(MASTER.resolve()) or
            not isinstance(entries, list) or len(entries) != 1):
        raise ValueError('New budget manifest differs')
    entry = entries[0]
    cap = paid.number(entry.get('cap_usd'))
    if (entry.get('id') != PARTITION_ID or cap < RESERVE or
            cap > Decimal('12.38') or
            (entry.get('model'), entry.get('provider'), entry.get('reasoning')) != (
                study.MODEL, study.PROVIDER, study.EFFORT) or
            Path(entry.get('child_ledger', '')).resolve() != (
                OUTPUT / ('budget-' + PARTITION_ID + '.jsonl')).resolve()):
        raise ValueError('New partition route, cap or child path differs')
    master_events = rows(MASTER)
    allocations = [event for event in master_events
                   if event.get('event') == 'budget_partition' and
                   event.get('partition_id') == PARTITION_ID]
    if len(allocations) != 1 or any(allocations[0].get(k) != v for k, v in {
            'allocated_usd': entry['cap_usd'], 'manifest_path': str(path),
            'manifest_sha256': sha(path), 'child_ledger': entry['child_ledger'],
            'model': study.MODEL, 'provider': study.PROVIDER,
            'reasoning': study.EFFORT}.items()):
        raise ValueError('New child allocation absent or changed')
    child = Path(entry['child_ledger'])
    child_events = rows(child)
    if not child_events or child_events[0] != {'event': 'budget', 'cap_usd': entry['cap_usd']}:
        raise ValueError('New child ledger opening differs')
    reconciliations = [event for event in master_events
                       if event.get('event') == 'partition_reconciled' and
                       event.get('partition_id') == PARTITION_ID]
    closed = [index for index, event in enumerate(child_events)
              if event.get('event') == 'partition_closed']
    if require_active:
        if reconciliations or closed or len(child_events) != 1:
            raise ValueError('New child allocation is spent, sealed or reconciled')
    elif reconciliations or closed:
        if len(reconciliations) != 1 or closed != [len(child_events) - 1]:
            raise ValueError('New child terminal lifecycle differs')
        pending = {}
        known = Decimal(0)
        unknown = Decimal(0)
        for event in child_events[1:-1]:
            kind = event.get('event')
            attempt = event.get('attempt_id')
            if kind == 'reserve':
                amount = paid.number(event.get('usd'))
                if pending or not attempt or amount <= 0:
                    raise ValueError('New child reservation lifecycle differs')
                pending[attempt] = amount
            elif kind == 'settle':
                amount = paid.number(event.get('usd'))
                if attempt not in pending or not Decimal(0) <= amount <= pending[attempt]:
                    raise ValueError('New child settlement lifecycle differs')
                known += amount
                del pending[attempt]
            elif kind == 'unknown_cost_accounted_as_upper_bound':
                amount = paid.number(event.get('usd'))
                if (attempt not in pending or amount != pending[attempt] or
                        event.get('actual_cost_usd') is not None or
                        not event.get('reason') or not event.get('evidence_path') or
                        not event.get('evidence_sha256')):
                    raise ValueError('New child unknown-cost lifecycle differs')
                unknown += amount
                del pending[attempt]
            else:
                raise ValueError('New child terminal ledger has an unexpected event')
        if pending or known + unknown > cap:
            raise ValueError('New child terminal accounting differs')
        expected = {'event': 'partition_reconciled', 'partition_id': PARTITION_ID,
                    'known_actual_usd': str(known),
                    'unknown_upper_bound_usd': str(unknown),
                    'unused_allocation_released_usd': str(cap - known - unknown),
                    'child_ledger': str(child.resolve()), 'child_sha256': sha(child)}
        if reconciliations[0] != expected:
            raise ValueError('New child terminal reconciliation differs')
    return entry


def expected_manifest(budget_path, reconciliation_path, require_active=True):
    prefix = verify_stopped_prefix()
    old = verify_old_seal(reconciliation_path, prefix)
    entry = budget_entry(budget_path, require_active=require_active)
    sources = {'controller': binding(__file__),
               'original_controller': binding(original.__file__),
               'original_study': binding(study.__file__),
               'original_budget_manifest': binding(OLD_BUDGET),
               'new_budget_manifest': binding(budget_path),
               **{f'original_plan_{p}': binding(BASE / p / 'manifest.json') for p in study.ORDERS},
               **{f'stopped_{k}': v for k, v in prefix['files'].items()},
               **{k: old[k] for k in ('old_child_ledger', 'old_reconciliation')}}
    for condition, phase in (('P0', 'development'), ('P1', 'development'), ('P2', 'smoke')):
        for kind, extension in (('claim', 'json'), ('journal', 'jsonl'),
                                ('attempts', 'jsonl'), ('responses', 'jsonl'),
                                ('wire', 'jsonl')):
            sources[f'fresh1_{condition}_{phase}_{kind}'] = binding(
                BASE / 'fresh1' / condition / f'{phase}.{kind}.{extension}')
    stages = []
    for repeat, condition, stage in STAGES:
        requests = selected_requests(repeat, condition, stage)
        stages.append({'fresh_pass': repeat, 'condition': condition, 'stage': stage,
                       'ids': [r['record_id'] for r in requests],
                       'request_sha256': [r['request_sha256'] for r in requests]})
    return {'schema': SCHEMA, 'status': 'FROZEN',
            'series_id': SCHEMA, 'configuration_id': study.CONFIG,
            'method': 'descriptive-interrupted-series-continuation',
            'clean_matched_three_eligible': False,
            'original_failed_id': 'DEV-007', 'original_never_sent_ids': SUFFIX,
            'old_known_actual_usd': old['known_actual_usd'],
            'old_unknown_upper_bound_usd': old['unknown_upper_bound_usd'],
            'stages': stages, 'source_bindings': sources,
            'partition_id': PARTITION_ID, 'child_cap_usd': entry['cap_usd'],
            'reserve_usd': str(RESERVE),
            'retry_policy': 'no retries, repairs or replay of DEV-001 through DEV-007',
            'reference_labels_read': False}


def freeze(budget_path, reconciliation_path):
    path = OUTPUT / 'manifest.json'
    if path.exists():
        raise FileExistsError('Continuation manifest already frozen')
    value = expected_manifest(budget_path, reconciliation_path)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with path.open('x') as out:
        json.dump(value, out, indent=2)
        out.write('\n'); out.flush(); os.fsync(out.fileno())
    return sha(path)


def verify_manifest(expected_sha):
    path = OUTPUT / 'manifest.json'
    if sha(path) != expected_sha:
        raise ValueError('Continuation manifest hash differs')
    value = json.loads(path.read_text())
    for item in value['source_bindings'].values():
        read_bound(item)
    sources = value['source_bindings']
    if value != expected_manifest(read_bound(sources['new_budget_manifest']),
                                  read_bound(sources['old_reconciliation']),
                                  require_active=False):
        raise ValueError('Continuation manifest differs from source reconstruction')
    return value


def stage_paths(repeat, condition, stage):
    selected_requests(repeat, condition, stage)
    folder = OUTPUT / repeat / condition
    return {key: folder / f'{stage}.{extension}' for key, extension in {
        'claim': 'claim.json', 'journal': 'journal.jsonl', 'attempts': 'attempts.jsonl',
        'responses': 'responses.jsonl', 'wire': 'wire.jsonl'}.items()}


def review_path(repeat, condition, stage):
    return OUTPUT / repeat / condition / f'{stage}.root-review.json'


def expected_review(manifest, manifest_sha, repeat, condition, stage):
    selected = selected_requests(repeat, condition, stage)
    return {'schema': SCHEMA + '-stage-review', 'approved': True,
            'series_id': SCHEMA, 'manifest_sha256': manifest_sha,
            'controller_sha256': manifest['source_bindings']['controller']['sha256'],
            'old_reconciliation_sha256': manifest['source_bindings']['old_reconciliation']['sha256'],
            'new_budget_manifest_sha256': manifest['source_bindings']['new_budget_manifest']['sha256'],
            'partition_id': PARTITION_ID, 'child_cap_usd': manifest['child_cap_usd'],
            'stage': f'{repeat}/{condition}/{stage}',
            'ids': [r['record_id'] for r in selected],
            'request_sha256': [r['request_sha256'] for r in selected]}


def verify_review(path, manifest, manifest_sha, repeat, condition, stage):
    path = Path(path).resolve()
    if path != review_path(repeat, condition, stage).resolve():
        raise ValueError('Exact root review path differs')
    value = json.loads(path.read_text())
    expected = expected_review(manifest, manifest_sha, repeat, condition, stage)
    if any(value.get(k) != v for k, v in expected.items()):
        raise ValueError('Root review does not bind selected requests and budget')
    return value


def verify_stage_closure(manifest, manifest_sha, repeat, condition, stage):
    paths = stage_paths(repeat, condition, stage)
    for path in paths.values():
        if not path.is_file():
            raise ValueError('Continuation closure evidence missing: ' + path.name)
    review = review_path(repeat, condition, stage)
    verify_review(review, manifest, manifest_sha, repeat, condition, stage)
    claim = json.loads(paths['claim'].read_text())
    if any(claim.get(k) != v for k, v in {
            'series_id': SCHEMA, 'fresh_pass': repeat, 'condition': condition,
            'phase': stage, 'manifest_sha256': manifest_sha,
            'root_review_sha256': sha(review)}.items()):
        raise ValueError('Continuation claim differs')
    attempts, raw, wire, journal = (rows(paths[k]) for k in
                                    ('attempts', 'responses', 'wire', 'journal'))
    requests = selected_requests(repeat, condition, stage)
    expected_ids = [r['record_id'] for r in requests]
    if ([r.get('id') for r in attempts] != expected_ids or
            [r.get('id') for r in raw] != expected_ids or
            [r.get('id') for r in wire] != expected_ids or
            len(attempts) != len(requests) or len(set(r.get('attempt_id') for r in attempts)) != len(attempts)):
        raise ValueError('Continuation rows do not match exact selected requests')
    expected_events = [{'event': 'phase_started', 'fresh_pass': repeat,
                        'condition': condition, 'phase': stage}]
    child = Path(budget_entry(read_bound(manifest['source_bindings']['new_budget_manifest']),
                              require_active=False)['child_ledger'])
    charges = rows(child)
    for request, record, response, captured in zip(requests, attempts, raw, wire):
        rid, attempt = request['record_id'], record['attempt_id']
        if (record.get('series_id') != SCHEMA or record.get('manifest_sha256') != manifest_sha or
                record.get('request') != request['payload'] or
                record.get('request_sha256') != request['request_sha256'] or
                paid.number(record.get('reserved_cost_usd')) != RESERVE or
                record.get('reference_labels_read') is not False or
                record.get('status') != 'ok' or record.get('billing_ok') is not True or
                record.get('cost_unknown') is not False or
                record.get('observed_cost_usd') is None or
                not Decimal(0) <= paid.number(record['observed_cost_usd']) <= RESERVE or
                response.get('attempt_id') != attempt or
                response.get('request_sha256') != request['request_sha256'] or
                response.get('raw_response') != record.get('raw_response') or
                captured.get('attempt_id') != attempt or captured.get('http_status') != 200 or
                captured.get('request_sha256') != request['request_sha256'] or
                captured.get('body_truncated_at_limit') is not False or
                captured.get('read_error') is not None or
                json.loads(base64.b64decode(captured['body_base64'], validate=True)) != record.get('raw_response')):
            raise ValueError('Continuation response or frozen request differs at ' + rid)
        classified = original.classify(record['raw_response'], record['model_catalog_entry'],
                                       record['provider_endpoint'])
        if (any(record.get(key) != value for key, value in classified.items()) or
                (record.get('raw_response', {}).get('usage') or {}).get('cost') is None or
                paid.number(record['raw_response']['usage']['cost']) !=
                paid.number(record['observed_cost_usd']) or
                record.get('response_diagnostic') != audit_response(
                    record, 'openrouter_paid_v1',
                    record['provider_endpoint']['context_length'] - 4096) or
                record['response_diagnostic'].get('passed') is not True):
            raise ValueError('Continuation response classification or cost differs at ' + rid)
        matches = [e for e in charges if e.get('attempt_id') == attempt]
        if matches != [{'event': 'reserve', 'attempt_id': attempt, 'record_id': rid,
                        'usd': str(RESERVE)},
                       {'event': 'settle', 'attempt_id': attempt,
                        'usd': record['observed_cost_usd']}]:
            raise ValueError('Continuation charge binding differs at ' + rid)
        expected_events.extend([
            {'event': 'request_intent', 'id': rid, 'request_sha256': request['request_sha256']},
            {'event': 'request_started', 'id': rid, 'attempt_id': attempt,
             'request_sha256': request['request_sha256']},
            {'event': 'request_finished', 'id': rid, 'attempt_id': attempt,
             'status': 'ok', 'billing_ok': True, 'cost_unknown': False,
             'observed_cost_usd': record['observed_cost_usd']}])
    expected_events.append({'event': 'phase_completed', 'fresh_pass': repeat,
                            'condition': condition, 'phase': stage,
                            'request_count': len(requests),
                            'attempt_ids': [r['attempt_id'] for r in attempts]})
    if len(journal) != len(expected_events) or any(
            any(actual.get(k) != v for k, v in expected.items())
            for actual, expected in zip(journal, expected_events)):
        raise ValueError('Continuation lifecycle is not strictly closed')
    return {key + '_sha256': sha(path) for key, path in paths.items()}


def require_order(manifest, manifest_sha, repeat, condition, stage):
    target = (repeat, condition, stage)
    if target not in STAGES:
        raise ValueError('Unknown continuation stage')
    for prior in STAGES[:STAGES.index(target)]:
        verify_stage_closure(manifest, manifest_sha, *prior)
    if stage == 'development':
        smoke = stage_paths(repeat, condition, 'smoke')
        bindings = verify_stage_closure(manifest, manifest_sha, repeat, condition, 'smoke')
        path = OUTPUT / repeat / condition / 'smoke-inspection.json'
        value = json.loads(path.read_text())
        if any(value.get(k) != v for k, v in {
                'schema': SCHEMA + '-smoke-inspection',
                'decision': 'accepted_unchanged', 'series_id': SCHEMA,
                'manifest_sha256': manifest_sha,
                'attempts_sha256': bindings['attempts_sha256'],
                'responses_sha256': bindings['responses_sha256'],
                'wire_sha256': bindings['wire_sha256'],
                'journal_sha256': bindings['journal_sha256']}.items()):
            raise ValueError('Smoke inspection missing or unbound')


def inspect_smoke(manifest_sha, repeat, condition, note):
    manifest = verify_manifest(manifest_sha)
    require_order(manifest, manifest_sha, repeat, condition, 'smoke')
    bindings = verify_stage_closure(manifest, manifest_sha, repeat, condition, 'smoke')
    if not note.strip():
        raise ValueError('Root inspection note required')
    value = {'schema': SCHEMA + '-smoke-inspection', 'decision': 'accepted_unchanged',
             'series_id': SCHEMA, 'manifest_sha256': manifest_sha, 'note': note,
             **{k: bindings[k] for k in ('attempts_sha256', 'responses_sha256',
                                          'wire_sha256', 'journal_sha256')}}
    path = OUTPUT / repeat / condition / 'smoke-inspection.json'
    with path.open('x') as out:
        json.dump(value, out, indent=2); out.write('\n'); out.flush(); os.fsync(out.fileno())
    return value


PRIVATE_FIELDS = frozenset({'user_id', 'account_id', 'email', 'api_key',
                            'authorization', 'access_token', 'refresh_token'})


def redact_account_fields(value):
    """Remove structured account fields, including JSON encoded inside strings."""
    if isinstance(value, dict):
        return {key: redact_account_fields(item) for key, item in value.items()
                if key.lower() not in PRIVATE_FIELDS}
    if isinstance(value, list):
        return [redact_account_fields(item) for item in value]
    if isinstance(value, str):
        try:
            nested = json.loads(value)
        except (ValueError, TypeError):
            return value
        if isinstance(nested, (dict, list)):
            clean = redact_account_fields(nested)
            return json.dumps(clean, ensure_ascii=False) if clean != nested else value
    return value


def public_prefix_row(kind, row):
    result = redact_account_fields(row)
    if kind == 'wire':
        body = base64.b64decode(row['body_base64'], validate=True)
        parsed = json.loads(body)
        clean = redact_account_fields(parsed)
        if clean != parsed:
            encoded = json.dumps(clean, ensure_ascii=False).encode('utf-8')
            result['body_base64'] = base64.b64encode(encoded).decode('ascii')
            result['body_bytes_captured'] = len(encoded)
            if 'content-length' in result.get('response_headers', {}):
                result['response_headers']['content-length'] = str(len(encoded))
    return result


def export_public_prefix(destination):
    """Produce an independent account-redacted copy; never alter originals."""
    prefix = verify_stopped_prefix()
    destination = Path(destination).resolve()
    destination.relative_to(ROOT.resolve())
    if destination != (OUTPUT / 'public-prefix-v1').resolve() or destination.exists():
        raise ValueError('Require a new exact versioned public-prefix directory')
    private_error = json.loads(rows(prefix_paths()['attempts'])[-1]['error_body'])
    account_identifier = private_error.get('user_id')
    if not isinstance(account_identifier, str) or not account_identifier:
        raise ValueError('Expected structured account identifier changed')
    destination.mkdir(parents=True)
    mappings = []
    for kind in ('attempts', 'responses', 'wire'):
        source = read_bound(prefix['files'][kind])
        target = destination / source.name
        projected = [public_prefix_row(kind, row) for row in rows(source)]
        for row in projected:
            encoded = json.dumps(row, ensure_ascii=False)
            decoded_wire = (base64.b64decode(row['body_base64'], validate=True).decode('utf-8')
                            if kind == 'wire' else '')
            if account_identifier in encoded or account_identifier in decoded_wire:
                raise ValueError('Account identifier remains in public projection')
        with target.open('x') as out:
            for row in projected:
                json.dump(row, out, ensure_ascii=False)
                out.write('\n')
            out.flush(); os.fsync(out.fileno())
        saved = rows(target)
        if (saved != projected or [x.get('id') for x in saved] != IDS[:7] or
                [x.get('attempt_id') for x in saved] !=
                [x.get('attempt_id') for x in rows(source)] or
                any(public_prefix_row(kind, old) != new for old, new in zip(rows(source), saved))):
            raise ValueError('Public projection changes evidence beyond redaction')
        mappings.append({'kind': kind, 'private': binding(source), 'public': binding(target)})
    result = {'schema': SCHEMA + '-public-prefix-export',
              'policy': 'Remove structured account identifiers in objects, nested JSON strings and decoded wire bodies; preserve all other parsed fields.',
              'prefix_claim_sha256': PREFIX_SHAS['claim'],
              'prefix_journal_sha256': PREFIX_SHAS['journal'], 'mappings': mappings,
              'manual_privacy_review_required': True}
    with (destination / 'export-manifest.json').open('x') as out:
        json.dump(result, out, indent=2)
        out.write('\n'); out.flush(); os.fsync(out.fileno())
    return result


def execute(manifest_sha, repeat, condition, stage, review, env_file=None):
    """Future dispatch only: exact root receipt and new child are mandatory."""
    manifest = verify_manifest(manifest_sha)
    require_order(manifest, manifest_sha, repeat, condition, stage)
    verify_review(review, manifest, manifest_sha, repeat, condition, stage)
    paths = stage_paths(repeat, condition, stage)
    if any(path.exists() for path in paths.values()):
        raise FileExistsError('Stage already claimed; no replay')
    plan = source_plan(repeat)
    model, endpoint, reserve = original.live_controls(plan, condition)
    if reserve != RESERVE:
        raise ValueError('Live reserve differs from frozen bound')
    budget_path = read_bound(manifest['source_bindings']['new_budget_manifest'])
    ledger = partitions.open_partition(MASTER, budget_path, PARTITION_ID,
                                       study.MODEL, study.PROVIDER, study.EFFORT)
    try:
        if ledger.cap != paid.number(manifest['child_cap_usd']) or ledger.master_cap != Decimal('12.38'):
            raise ValueError('Master or child cap differs from root-reviewed manifest')
        _, pending, blocked = ledger.state()
        if pending or blocked or ledger.closed or ledger.accounted() + RESERVE > ledger.cap:
            raise ValueError('New child has unresolved cost, is blocked or lacks first reserve')
        token = paid.load_key(env_file)
        folder = paths['claim'].parent
        folder.mkdir(parents=True, exist_ok=True)
        with paths['claim'].open('x') as out:
            original.durable(out, {'series_id': SCHEMA, 'fresh_pass': repeat,
                                   'condition': condition, 'phase': stage,
                                   'manifest_sha256': manifest_sha,
                                   'root_review_sha256': sha(review), 'claimed_utc': original.utc()})
        requests = selected_requests(repeat, condition, stage)
        complete = True
        with paths['journal'].open('x') as journal, paths['attempts'].open('x') as attempts, \
             paths['responses'].open('x') as responses, paths['wire'].open('x') as wire:
            original.durable(journal, {'event': 'phase_started', 'fresh_pass': repeat,
                                       'condition': condition, 'phase': stage,
                                       'utc': original.utc()})
            for request in requests:
                rid, payload = request['record_id'], request['payload']
                original.durable(journal, {'event': 'request_intent', 'id': rid,
                                           'request_sha256': request['request_sha256'],
                                           'utc': original.utc()})
                if ledger.accounted() + reserve > ledger.cap:
                    complete = False
                    original.durable(journal, {'event': 'phase_stopped',
                                               'id': rid, 'reason': 'child_cap_before_send',
                                               'utc': original.utc()})
                    break
                attempt_id = ledger.reserve(reserve, rid)
                start = time.perf_counter()
                record = {'id': rid, 'series_id': SCHEMA, 'fresh_pass': repeat,
                          'condition': condition, 'phase': stage, 'attempt_id': attempt_id,
                          'request': payload, 'request_sha256': request['request_sha256'],
                          'manifest_sha256': manifest_sha, 'requested_model': study.MODEL,
                          'reasoning_effort': study.EFFORT, 'provider_endpoint': endpoint,
                          'model_catalog_entry': model, 'reference_labels_read': False,
                          'reserved_cost_usd': str(reserve), 'started_utc': original.utc()}
                original.durable(journal, {'event': 'request_started', 'id': rid,
                                           'attempt_id': attempt_id,
                                           'request_sha256': request['request_sha256'],
                                           'utc': original.utc()})
                actual = None
                wire_before = wire.tell()
                try:
                    body = original.fetch_captured(payload, token, wire, rid,
                                                   attempt_id, request['request_sha256'])
                    record['raw_response'] = body
                    original.durable(responses, {'id': rid, 'attempt_id': attempt_id,
                                                 'request_sha256': request['request_sha256'],
                                                 'raw_response': body, 'received_utc': original.utc()})
                    if isinstance(body, dict):
                        usage = body.get('usage') or {}
                        if usage.get('cost') is not None:
                            actual = paid.number(usage['cost'])
                    record.update(original.classify(body, model, endpoint))
                except Exception as exc:
                    record.update(status='service_error', error_type=type(exc).__name__)
                    if isinstance(exc, original.CapturedHTTPError):
                        record.update(http_status=exc.status, error_body=exc.body,
                                      error_headers=exc.headers)
                        original.durable(responses, {'id': rid, 'attempt_id': attempt_id,
                                                     'request_sha256': request['request_sha256'],
                                                     'http_status': exc.status, 'error_body': exc.body,
                                                     'error_headers': exc.headers,
                                                     'received_utc': original.utc()})
                    elif wire.tell() > wire_before:
                        original.durable(responses, {'id': rid, 'attempt_id': attempt_id,
                                                     'request_sha256': request['request_sha256'],
                                                     'capture_error': type(exc).__name__,
                                                     'received_utc': original.utc()})
                billing_ok = ledger.settle(attempt_id, actual)
                record.update(elapsed_seconds=time.perf_counter() - start,
                              timing_boundary='Request-to-record duration includes request-start journal fsync, provider call, raw-response fsync, billing settlement and response audit; it ends before attempt-row and request-finished journal fsync.',
                              observed_cost_usd=str(actual) if actual is not None else None,
                              cost_unknown=actual is None, billing_ok=billing_ok)
                if record.get('raw_response') is not None:
                    diagnostic = audit_response(record, 'openrouter_paid_v1',
                                                endpoint['context_length'] - 4096)
                    record['response_diagnostic'] = diagnostic
                    if not diagnostic['passed'] and record['status'] == 'ok':
                        record['status'] = 'prompt_admission_failure'
                original.durable(attempts, record)
                original.durable(journal, {'event': 'request_finished', 'id': rid,
                                           'attempt_id': attempt_id, 'status': record['status'],
                                           'billing_ok': billing_ok,
                                           'cost_unknown': record['cost_unknown'],
                                           'observed_cost_usd': record['observed_cost_usd'],
                                           'utc': original.utc()})
                if not original.continue_record(record, 'development' if stage == 'suffix' else stage):
                    complete = False
                    original.durable(journal, {'event': 'phase_stopped', 'id': rid,
                                               'reason': record['status'], 'utc': original.utc()})
                    break
            if complete:
                original.durable(journal, {'event': 'phase_completed', 'fresh_pass': repeat,
                                           'condition': condition, 'phase': stage,
                                           'request_count': len(requests),
                                           'attempt_ids': [x['attempt_id'] for x in rows(paths['attempts'])],
                                           'utc': original.utc()})
        return complete
    finally:
        if paths['journal'].exists():
            events = rows(paths['journal'])
            if not events or events[-1].get('event') not in ('phase_completed', 'phase_stopped', 'phase_aborted'):
                with paths['journal'].open('a') as out:
                    original.durable(out, {'event': 'phase_aborted',
                                           'reason': 'exception_or_interruption',
                                           'utc': original.utc()})
        ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('audit-prefix')
    export = sub.add_parser('export-public-prefix')
    export.add_argument('--destination', required=True)
    freeze_cmd = sub.add_parser('freeze')
    freeze_cmd.add_argument('--budget-manifest', required=True)
    freeze_cmd.add_argument('--old-reconciliation', required=True)
    check = sub.add_parser('verify')
    check.add_argument('--manifest-sha256', required=True)
    for name in ('receipt-template', 'inspect-smoke', 'run'):
        cmd = sub.add_parser(name)
        cmd.add_argument('--manifest-sha256', required=True)
        cmd.add_argument('--fresh-pass', required=True)
        cmd.add_argument('--condition', required=True)
        cmd.add_argument('--stage', required=True)
        if name == 'inspect-smoke':
            cmd.add_argument('--note', required=True)
        if name == 'run':
            cmd.add_argument('--root-review-receipt', required=True)
            cmd.add_argument('--env-file')
    args = parser.parse_args()
    if args.action == 'audit-prefix':
        print(json.dumps(verify_stopped_prefix(), indent=2))
    elif args.action == 'export-public-prefix':
        print(json.dumps(export_public_prefix(args.destination), indent=2))
    elif args.action == 'freeze':
        print(freeze(args.budget_manifest, args.old_reconciliation))
    elif args.action == 'verify':
        verify_manifest(args.manifest_sha256); print('verified')
    elif args.action == 'receipt-template':
        manifest = verify_manifest(args.manifest_sha256)
        print(json.dumps(expected_review(manifest, args.manifest_sha256,
                                         args.fresh_pass, args.condition, args.stage), indent=2))
    elif args.action == 'inspect-smoke':
        if args.stage != 'smoke':
            raise ValueError('Only smoke stages may be inspected')
        print(json.dumps(inspect_smoke(args.manifest_sha256, args.fresh_pass,
                                       args.condition, args.note), indent=2))
    else:
        execute(args.manifest_sha256, args.fresh_pass, args.condition, args.stage,
                args.root_review_receipt, args.env_file)


if __name__ == '__main__':
    main()
