#!/usr/bin/env python3
"""Versioned Gemma26 successor after fresh3/P2 DEV-005, offline until admitted."""
import argparse
import base64
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import time

from development_benchmark import ROOT
import gemma26_v2_second_continuation as second
import gemma26_v2_continuation as first
import gemma26_on_fresh_repeat_study_v2 as study
import gemma26_on_fresh_repeat_execution_v2 as original
import openrouter_paid_benchmark as paid
import paid_budget_partitions_v3 as partitions
from prompt_admission import audit_response

SCHEMA = 'gemma26-on-v2-third-interruption-continuation-v1'
SECOND_SHA = 'b50976253573afed508504bbcd9cc68dfbc6a677b6b8094bcef19a77717f4335'
SEALED_CHILD_SHA = '3ef746833f9324a700e6da8aeceead8b01f2b2af01c0016be99761bd88266eaf'
RECONCILIATION_SHA = '4f64b3d140ff2c0b5a8d86e3cb926f5bec68f7abebe5b488f22683680ae2ba13'
STOP_SHA = {
    'claim': '7e4d33f9fe8bc5eebcec57856e101c2a09eeaa2a372bf6b017d1b60521bee9bf',
    'review': 'c14a515d39f907ace1cf286bddf71bf1ed5c53af7ef5999888ee96f538998039',
    'journal': 'd4f7997d3c96a6ad0e151ae8faa36b96031092cfb55e292f92b7802d79fb2b1e',
    'attempts': 'e19af839c43e406ba10a08e1d0697391b929d233703f01bfc306564847dfec14',
    'responses': '54b381f12e8ad8c63f83b4eec09f84142e4a9e384e699f3bf5e743ebf1b13270',
    'wire': '692e06c1ee5a7781ff236a8e4ee272426412bf1f10ee6ee6cac181773919fe89',
}
CLOSED_SHA = {
    'fresh2_P0_suffix_claim': '85e4a3f9ec62e7ee9748880c9b51e055cd2a6164cfd10738a4ebf3f631dca319',
    'fresh2_P0_suffix_journal': '7dec80d4402c232000503403218c0221598051706e51f59d2f219de8d31150cb',
    'fresh2_P0_suffix_attempts': 'b07115d2644ac92485e42a6967a29ee938493ccf04c5603121f1af7b22b81584',
    'fresh2_P0_suffix_responses': '1eaeb2c046095fb2c26223f1ea86ea0f484ed93d996f4a03e3f64aef7d2aad32',
    'fresh2_P0_suffix_wire': 'ecac99dd33e7ae5ddb4a8d4dc5ac99eafaef851c7361ebc485bcf90de43815b3',
    'fresh2_P0_suffix_review': 'df9b5b4c41e0f248a41b61a7a1b04f627426d3992b2008935db578728f484d90',
    'fresh3_P2_smoke_claim': '6fd57d9cdfc9c130dccf6ac8c2669282e6f8653b6776740fe9e3abb3d756574a',
    'fresh3_P2_smoke_journal': 'bb1c0dbd5b506050f079c85ce89169a7b835320fc515682f4b5956dfb8557dbb',
    'fresh3_P2_smoke_attempts': '6dc4b60c9b31145ffdd726dcd2dbaeac3247f5e6c28eb9f91f3a0cc4d3cf24b3',
    'fresh3_P2_smoke_responses': 'f624e9223c324d1fcbebe57c7a0bc4a880a19528c0bb479ba9077c3cbf909725',
    'fresh3_P2_smoke_wire': 'a10f2f945dff2f6ae718d19d693ccaf5a28eab5f900b8e55bc39439b11532fef',
    'fresh3_P2_smoke_review': '2a0548bc97fca1dba5c0b5c2073fa48dba80aae80e6a35d0bccbd8a9ffbb1823',
    'fresh3_P2_smoke_inspection': '05cfa50a84ce9a60e2cbcb32f80dec1191136a8d1d473233f7cde3d68df8102d',
}
BASE = study.BASE
OUTPUT = BASE / 'third-interruption-continuation-v1'
MASTER = original.MASTER
PARTITION_ID = 'gemma26-on-v2-third-interruption-v1'
RESERVE = second.RESERVE
IDS = second.IDS
SUFFIX = IDS[5:]
STAGES = [('fresh3', 'P2', 'suffix'),
          ('fresh3', 'P0', 'smoke'), ('fresh3', 'P0', 'development'),
          ('fresh3', 'P1', 'smoke'), ('fresh3', 'P1', 'development')]
RUNTIME_HELPERS = second.RUNTIME_HELPERS
RUNTIME_SOURCE_KEYS = ('controller', 'second_controller', 'first_controller',
                       'original_controller', 'original_study') + tuple(
                           'runtime_' + name for name in RUNTIME_HELPERS)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return second.rows(path)


def binding(path):
    return second.binding(path)


def read_bound(item):
    return second.read_bound(item)


def selected_requests(repeat, condition, stage):
    if (repeat, condition, stage) not in STAGES:
        raise ValueError('Stage outside third continuation schedule')
    plan = study.verify(repeat, first.PLAN_SHAS[repeat])
    source = plan['conditions'][condition][
        'development' if stage == 'suffix' else stage]
    chosen = source[5:] if stage == 'suffix' else source
    expected = SUFFIX if stage == 'suffix' else IDS[:3] if stage == 'smoke' else IDS
    if [item['record_id'] for item in chosen] != expected:
        raise ValueError('Third continuation selected requests differ')
    return chosen


def audit_prior():
    """Read-only audit of all prior outcomes and the sealed DEV-005 child."""
    manifest = second.verify_manifest(SECOND_SHA)
    second.require_order(manifest, SECOND_SHA, 'fresh3', 'P2', 'development')
    predecessor = {}
    for repeat, condition, stage in (('fresh2', 'P0', 'suffix'),
                                     ('fresh3', 'P2', 'smoke')):
        verified = second.verify_stage_closure(manifest, SECOND_SHA,
                                               repeat, condition, stage)
        paths = second.stage_paths(repeat, condition, stage)
        paths['review'] = second.review_path(repeat, condition, stage)
        for kind, path in paths.items():
            key = f'{repeat}_{condition}_{stage}_{kind}'
            if sha(path) != CLOSED_SHA[key] or \
                    (kind != 'review' and sha(path) != verified[kind + '_sha256']):
                raise ValueError('Prior closed stage source differs')
            predecessor[key] = binding(path)
    inspection = second.OUTPUT / 'fresh3/P2/smoke-inspection.json'
    if sha(inspection) != CLOSED_SHA['fresh3_P2_smoke_inspection']:
        raise ValueError('Prior P2 smoke inspection changed')
    predecessor['fresh3_P2_smoke_inspection'] = binding(inspection)
    paths = second.stage_paths('fresh3', 'P2', 'development')
    paths['review'] = second.review_path('fresh3', 'P2', 'development')
    second.verify_review(paths['review'], manifest, SECOND_SHA,
                         'fresh3', 'P2', 'development')
    for kind, expected in STOP_SHA.items():
        if sha(paths[kind]) != expected:
            raise ValueError('DEV-005 stopped evidence changed: ' + kind)
    claim = json.loads(paths['claim'].read_text())
    if any(claim.get(key) != value for key, value in {
            'series_id': second.SCHEMA, 'fresh_pass': 'fresh3',
            'condition': 'P2', 'phase': 'development',
            'manifest_sha256': SECOND_SHA,
            'root_review_sha256': STOP_SHA['review']}.items()):
        raise ValueError('DEV-005 stopped claim differs')
    attempts, responses, wire, journal = (rows(paths[k]) for k in
                                          ('attempts', 'responses', 'wire', 'journal'))
    requests = study.verify('fresh3', first.PLAN_SHAS['fresh3'])[
        'conditions']['P2']['development'][:5]
    if ([x.get('id') for x in attempts] != IDS[:5] or
            [x.get('id') for x in responses] != IDS[:4] or
            [x.get('id') for x in wire] != IDS[:4] or
            len(journal) != 17 or journal[0].get('event') != 'phase_started' or
            journal[-1].get('event') != 'phase_stopped' or
            (journal[-1].get('id'), journal[-1].get('reason')) !=
                ('DEV-005', 'service_error')):
        raise ValueError('DEV-005 terminal membership differs')
    seen = set()
    for i, (request, attempt) in enumerate(zip(requests, attempts)):
        rid, attempt_id = request['record_id'], attempt.get('attempt_id')
        intent, started, finished = journal[1 + 3*i:4 + 3*i]
        if (not isinstance(attempt_id, str) or not attempt_id or attempt_id in seen or
                attempt.get('series_id') != second.SCHEMA or
                attempt.get('manifest_sha256') != SECOND_SHA or
                attempt.get('request') != request['payload'] or
                attempt.get('request_sha256') != request['request_sha256'] or
                attempt.get('reference_labels_read') is not False or
                paid.number(attempt.get('reserved_cost_usd')) != RESERVE or
                (intent.get('event'), intent.get('id'), intent.get('request_sha256')) !=
                    ('request_intent', rid, request['request_sha256']) or
                (started.get('event'), started.get('id'), started.get('attempt_id'),
                 started.get('request_sha256')) !=
                    ('request_started', rid, attempt_id, request['request_sha256']) or
                (finished.get('event'), finished.get('id'), finished.get('attempt_id'),
                 finished.get('status'), finished.get('billing_ok'),
                 finished.get('cost_unknown'), finished.get('observed_cost_usd')) !=
                    ('request_finished', rid, attempt_id, attempt.get('status'),
                     attempt.get('billing_ok'), attempt.get('cost_unknown'),
                     attempt.get('observed_cost_usd'))):
            raise ValueError('DEV-005 prefix attempt differs at ' + rid)
        seen.add(attempt_id)
        if i < 4:
            raw, captured = responses[i], wire[i]
            classified = original.classify(attempt['raw_response'],
                                           attempt['model_catalog_entry'],
                                           attempt['provider_endpoint'])
            if (attempt.get('status') != 'ok' or attempt.get('billing_ok') is not True or
                    attempt.get('cost_unknown') is not False or
                    raw.get('attempt_id') != attempt_id or
                    raw.get('raw_response') != attempt.get('raw_response') or
                    captured.get('attempt_id') != attempt_id or
                    captured.get('http_status') != 200 or
                    captured.get('body_truncated_at_limit') is not False or
                    captured.get('read_error') is not None or
                    json.loads(base64.b64decode(captured['body_base64'], validate=True)) !=
                        attempt.get('raw_response') or
                    any(attempt.get(k) != v for k, v in classified.items()) or
                    paid.number(attempt['raw_response']['usage']['cost']) !=
                        paid.number(attempt['observed_cost_usd'])):
                raise ValueError('Prior valid P2 response differs at ' + rid)
    failed = attempts[-1]
    if (failed.get('status') != 'service_error' or
            failed.get('error_type') != 'TimeoutError' or
            failed.get('billing_ok') is not False or
            failed.get('cost_unknown') is not True or
            failed.get('observed_cost_usd') is not None or
            failed.get('raw_response') is not None):
        raise ValueError('DEV-005 unknown-cost failure differs')
    child = second.OUTPUT / ('budget-' + second.PARTITION_ID + '.jsonl')
    reconciliation = second.OUTPUT / 'terminal-reconciliation-after-dev005.json'
    if sha(child) != SEALED_CHILD_SHA or sha(reconciliation) != RECONCILIATION_SHA:
        raise ValueError('DEV-005 child seal changed')
    second.budget_entry(second.OUTPUT / 'budget.json')
    events = rows(child)
    charges = [e for e in events if e.get('attempt_id') == failed['attempt_id']]
    if (len(charges) != 2 or charges[0] != {'event': 'reserve',
            'attempt_id': failed['attempt_id'], 'record_id': 'DEV-005',
            'usd': str(RESERVE)} or
            charges[1].get('event') != 'unknown_cost_accounted_as_upper_bound' or
            paid.number(charges[1].get('usd')) != RESERVE or
            charges[1].get('actual_cost_usd') is not None or
            charges[1].get('evidence_sha256') != STOP_SHA['attempts'] or
            Path(charges[1].get('evidence_path', '')).resolve() != paths['attempts'].resolve() or
            events[-1].get('event') != 'partition_closed'):
        raise ValueError('DEV-005 reservation or unknown hold differs')
    known = sum((paid.number(e['usd']) for e in events if e['event'] == 'settle'), Decimal(0))
    unknown = sum((paid.number(e['usd']) for e in events
                   if e['event'] == 'unknown_cost_accounted_as_upper_bound'), Decimal(0))
    terminal = json.loads(reconciliation.read_text())
    if (known != Decimal('0.02147655') or unknown != RESERVE or
            terminal != {'event': 'partition_reconciled',
                'partition_id': second.PARTITION_ID,
                'known_actual_usd': str(known),
                'unknown_upper_bound_usd': str(unknown),
                'unused_allocation_released_usd': str(paid.number(events[0]['cap_usd']) - known - unknown),
                'child_ledger': str(child.resolve()), 'child_sha256': sha(child)} or
            terminal not in rows(MASTER)):
        raise ValueError('DEV-005 terminal reconciliation differs')
    return {'prior_manifest': binding(second.OUTPUT / 'manifest.json'),
            'sealed_child': binding(child), 'sealed_reconciliation': binding(reconciliation),
            'stopped_files': {k: binding(v) for k, v in paths.items()},
            'predecessor_files': predecessor,
            'never_sent_ids': SUFFIX, 'failed_attempt_id': failed['attempt_id'],
            'historical_unknown_upper_bounds': {'DEV-007': str(RESERVE),
                                                'DEV-002': str(RESERVE),
                                                'DEV-005': str(RESERVE)}}


def budget_entry(path, *, require_fresh=False, require_dispatch=False):
    path = Path(path).resolve()
    if path != (OUTPUT / 'budget.json').resolve():
        raise ValueError('Third child manifest path differs')
    data = json.loads(path.read_text())
    entries = data.get('partitions')
    if (data.get('version') != 'paid-partitions-v1' or
            data.get('master_ledger') != str(MASTER.resolve()) or
            not isinstance(entries, list) or len(entries) != 1):
        raise ValueError('Third child manifest differs')
    entry = entries[0]
    cap = paid.number(entry.get('cap_usd'))
    child = OUTPUT / ('budget-' + PARTITION_ID + '.jsonl')
    if (entry.get('id') != PARTITION_ID or cap < RESERVE or cap > Decimal('12.38') or
            (entry.get('model'), entry.get('provider'), entry.get('reasoning')) !=
                (study.MODEL, study.PROVIDER, study.EFFORT) or
            Path(entry.get('child_ledger', '')).resolve() != child.resolve()):
        raise ValueError('Third child route or cap differs')
    master = rows(MASTER)
    allocations = [e for e in master if e.get('event') == 'budget_partition'
                   and e.get('partition_id') == PARTITION_ID]
    if len(allocations) != 1 or any(allocations[0].get(k) != v for k, v in {
            'allocated_usd': entry['cap_usd'], 'manifest_path': str(path),
            'manifest_sha256': sha(path), 'child_ledger': str(child.resolve()),
            'model': study.MODEL, 'provider': study.PROVIDER,
            'reasoning': study.EFFORT}.items()):
        raise ValueError('Third child allocation differs')
    events = rows(child)
    if not events or events[0] != {'event': 'budget', 'cap_usd': entry['cap_usd']}:
        raise ValueError('Third child opening differs')
    reconciled = [e for e in master if e.get('event') == 'partition_reconciled'
                  and e.get('partition_id') == PARTITION_ID]
    closed = [i for i, e in enumerate(events) if e.get('event') == 'partition_closed']
    if require_fresh and (reconciled or closed or len(events) != 1):
        raise ValueError('Third child is spent, sealed or reconciled')
    if require_dispatch and (reconciled or closed):
        raise ValueError('Third child is sealed or reconciled')
    if reconciled or closed:
        if len(reconciled) != 1 or closed != [len(events) - 1]:
            raise ValueError('Third child terminal lifecycle differs')
    return entry


def expected_manifest(budget_path, reconciliation_path, *, require_fresh=False):
    prior = audit_prior()
    if Path(reconciliation_path).resolve() != \
            (second.OUTPUT / 'terminal-reconciliation-after-dev005.json').resolve():
        raise ValueError('Exact DEV-005 reconciliation path differs')
    if sha(reconciliation_path) != RECONCILIATION_SHA:
        raise ValueError('DEV-005 reconciliation changed')
    entry = budget_entry(budget_path, require_fresh=require_fresh)
    sources = {'controller': binding(__file__),
               'second_controller': binding(second.__file__),
               'first_controller': binding(first.__file__),
               'original_controller': binding(original.__file__),
               'original_study': binding(study.__file__),
               'second_manifest': prior['prior_manifest'],
               'new_budget_manifest': binding(budget_path),
               'old_child_ledger': prior['sealed_child'],
               'old_reconciliation': prior['sealed_reconciliation'],
               **{'stopped_' + k: v for k, v in prior['stopped_files'].items()},
               **{'predecessor_' + k: v for k, v in prior['predecessor_files'].items()}}
    for name in RUNTIME_HELPERS:
        sources['runtime_' + name] = binding(ROOT / 'scripts' / (name + '.py'))
    for repeat in study.ORDERS:
        sources['original_plan_' + repeat] = binding(BASE / repeat / 'manifest.json')
    stages = []
    for repeat, condition, stage in STAGES:
        selected = selected_requests(repeat, condition, stage)
        stages.append({'fresh_pass': repeat, 'condition': condition, 'stage': stage,
                       'ids': [r['record_id'] for r in selected],
                       'request_sha256': [r['request_sha256'] for r in selected]})
    return {'schema': SCHEMA, 'status': 'FROZEN', 'series_id': SCHEMA,
            'configuration_id': study.CONFIG,
            'method': 'descriptive-third-interruption-continuation',
            'clean_matched_three_eligible': False,
            'original_failed_id': 'DEV-007', 'first_suffix_failed_id': 'DEV-002',
            'second_suffix_failed_id': 'DEV-005',
            'second_suffix_never_sent_ids': SUFFIX,
            'historical_unknown_upper_bounds': prior['historical_unknown_upper_bounds'],
            'stages': stages, 'source_bindings': sources,
            'partition_id': PARTITION_ID, 'child_cap_usd': entry['cap_usd'],
            'reserve_usd': str(RESERVE),
            'retry_policy': 'no retries, repairs or replay of DEV-001 through DEV-005',
            'reference_labels_read': False}


def freeze(budget_path, reconciliation_path):
    path = OUTPUT / 'manifest.json'
    if path.exists():
        raise FileExistsError('Third continuation manifest already frozen')
    value = expected_manifest(budget_path, reconciliation_path, require_fresh=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with path.open('x') as out:
        json.dump(value, out, indent=2)
        out.write('\n'); out.flush(); os.fsync(out.fileno())
    return sha(path)


def verify_manifest(expected_sha):
    path = OUTPUT / 'manifest.json'
    if sha(path) != expected_sha:
        raise ValueError('Third continuation manifest hash differs')
    value = json.loads(path.read_text())
    for item in value['source_bindings'].values():
        read_bound(item)
    if value != expected_manifest(
            read_bound(value['source_bindings']['new_budget_manifest']),
            read_bound(value['source_bindings']['old_reconciliation'])):
        raise ValueError('Third continuation manifest differs from sealed sources')
    return value


def stage_paths(repeat, condition, stage):
    selected_requests(repeat, condition, stage)
    folder = OUTPUT / repeat / condition
    return {key: folder / f'{stage}.{extension}' for key, extension in {
        'claim': 'claim.json', 'journal': 'journal.jsonl',
        'attempts': 'attempts.jsonl', 'responses': 'responses.jsonl',
        'wire': 'wire.jsonl'}.items()}


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
        raise ValueError('Exact third root review path differs')
    value = json.loads(path.read_text())
    if any(value.get(k) != v for k, v in expected_review(
            manifest, manifest_sha, repeat, condition, stage).items()):
        raise ValueError('Third root review differs')
    return value


def verify_stage_closure(manifest, manifest_sha, repeat, condition, stage):
    paths = stage_paths(repeat, condition, stage)
    if not all(path.is_file() for path in paths.values()):
        raise ValueError('Third continuation stage evidence missing')
    review = review_path(repeat, condition, stage)
    verify_review(review, manifest, manifest_sha, repeat, condition, stage)
    claim = json.loads(paths['claim'].read_text())
    if any(claim.get(k) != v for k, v in {
            'series_id': SCHEMA, 'fresh_pass': repeat, 'condition': condition,
            'phase': stage, 'manifest_sha256': manifest_sha,
            'root_review_sha256': sha(review)}.items()):
        raise ValueError('Third continuation claim differs')
    attempts, responses, wire, journal = (rows(paths[k]) for k in
                                          ('attempts', 'responses', 'wire', 'journal'))
    requests = selected_requests(repeat, condition, stage)
    if ([r.get('id') for r in attempts] != [r['record_id'] for r in requests] or
            [r.get('id') for r in responses] != [r['record_id'] for r in requests] or
            [r.get('id') for r in wire] != [r['record_id'] for r in requests] or
            len({r.get('attempt_id') for r in attempts}) != len(requests) or
            len(journal) != 2 + 3 * len(requests) or
            journal[0].get('event') != 'phase_started' or
            (journal[0].get('fresh_pass'), journal[0].get('condition'),
             journal[0].get('phase')) != (repeat, condition, stage) or
            journal[-1].get('event') != 'phase_completed' or
            (journal[-1].get('fresh_pass'), journal[-1].get('condition'),
             journal[-1].get('phase')) != (repeat, condition, stage) or
            journal[-1].get('request_count') != len(requests) or
            journal[-1].get('attempt_ids') != [r.get('attempt_id') for r in attempts]):
        raise ValueError('Third continuation stage membership differs')
    entry = budget_entry(read_bound(manifest['source_bindings']['new_budget_manifest']))
    charges = rows(Path(entry['child_ledger']))
    for i, (request, record, response, captured) in enumerate(
            zip(requests, attempts, responses, wire)):
        rid, attempt = request['record_id'], record['attempt_id']
        intent, started, finished = journal[1 + 3*i:4 + 3*i]
        if (record.get('series_id') != SCHEMA or
                (record.get('fresh_pass'), record.get('condition'),
                 record.get('phase')) != (repeat, condition, stage) or
                record.get('manifest_sha256') != manifest_sha or
                record.get('request') != request['payload'] or
                record.get('request_sha256') != request['request_sha256'] or
                record.get('requested_model') != study.MODEL or
                record.get('reasoning_effort') != study.EFFORT or
                record.get('reference_labels_read') is not False or
                record.get('reserved_cost_usd') != str(RESERVE) or
                record.get('status') != 'ok' or record.get('billing_ok') is not True or
                record.get('cost_unknown') is not False or
                response.get('id') != rid or response.get('attempt_id') != attempt or
                response.get('request_sha256') != request['request_sha256'] or
                response.get('raw_response') != record.get('raw_response') or
                captured.get('id') != rid or captured.get('attempt_id') != attempt or
                captured.get('http_status') != 200 or
                captured.get('request_sha256') != request['request_sha256'] or
                captured.get('body_truncated_at_limit') is not False or
                captured.get('read_error') is not None or
                json.loads(base64.b64decode(captured['body_base64'], validate=True)) !=
                    record.get('raw_response') or
                [(e.get('event'), e.get('id'), e.get('attempt_id'),
                  e.get('request_sha256')) for e in (intent, started, finished)] != [
                    ('request_intent', rid, None, request['request_sha256']),
                    ('request_started', rid, attempt, request['request_sha256']),
                    ('request_finished', rid, attempt, None)] or
                finished.get('status') != 'ok' or
                finished.get('billing_ok') is not True or
                finished.get('cost_unknown') is not False or
                finished.get('observed_cost_usd') != record.get('observed_cost_usd') or
                [e for e in charges if e.get('attempt_id') == attempt] != [
                    {'event': 'reserve', 'attempt_id': attempt,
                     'record_id': rid, 'usd': str(RESERVE)},
                    {'event': 'settle', 'attempt_id': attempt,
                     'usd': record['observed_cost_usd']}]):
            raise ValueError('Third continuation response or charge differs at ' + rid)
        classified = original.classify(record['raw_response'],
                                       record['model_catalog_entry'],
                                       record['provider_endpoint'])
        if (any(record.get(k) != v for k, v in classified.items()) or
                paid.number(record['raw_response']['usage']['cost']) !=
                    paid.number(record['observed_cost_usd']) or
                not Decimal(0) <= paid.number(record['observed_cost_usd']) <= RESERVE or
                record.get('response_diagnostic') != audit_response(
                    record, 'openrouter_paid_v1',
                    record['provider_endpoint']['context_length'] - 4096) or
                record['response_diagnostic'].get('passed') is not True):
            raise ValueError('Third continuation classification differs at ' + rid)
    return {k + '_sha256': sha(v) for k, v in paths.items()}


def require_order(manifest, manifest_sha, repeat, condition, stage):
    target = (repeat, condition, stage)
    if target not in STAGES:
        raise ValueError('Unknown third continuation stage')
    for prior in STAGES[:STAGES.index(target)]:
        verify_stage_closure(manifest, manifest_sha, *prior)
    if stage == 'development':
        smoke = verify_stage_closure(manifest, manifest_sha,
                                     repeat, condition, 'smoke')
        receipt = OUTPUT / repeat / condition / 'smoke-inspection.json'
        value = json.loads(receipt.read_text())
        if any(value.get(k) != v for k, v in {
                'schema': SCHEMA + '-smoke-inspection',
                'decision': 'accepted_unchanged', 'series_id': SCHEMA,
                'manifest_sha256': manifest_sha,
                'attempts_sha256': smoke['attempts_sha256'],
                'responses_sha256': smoke['responses_sha256'],
                'wire_sha256': smoke['wire_sha256'],
                'journal_sha256': smoke['journal_sha256']}.items()):
            raise ValueError('Third continuation smoke inspection differs')


def execute(manifest_sha, repeat, condition, stage, review, env_file=None):
    manifest = verify_manifest(manifest_sha)
    require_order(manifest, manifest_sha, repeat, condition, stage)
    verify_review(review, manifest, manifest_sha, repeat, condition, stage)
    paths = stage_paths(repeat, condition, stage)
    if any(path.exists() for path in paths.values()):
        raise FileExistsError('Third continuation stage already claimed')
    plan = study.verify(repeat, first.PLAN_SHAS[repeat])
    _, _, reserve = original.live_controls(plan, condition)
    if reserve != RESERVE:
        raise ValueError('Live reserve differs from frozen request')
    budget_path = read_bound(manifest['source_bindings']['new_budget_manifest'])
    budget_entry(budget_path, require_dispatch=True)
    ledger = partitions.open_partition(MASTER, budget_path, PARTITION_ID,
                                       study.MODEL, study.PROVIDER, study.EFFORT)
    try:
        if ledger.cap != paid.number(manifest['child_cap_usd']) or \
                ledger.master_cap != Decimal('12.38'):
            raise ValueError('Master or third child cap differs')
        _, pending, blocked = ledger.state()
        if pending or blocked or ledger.closed or ledger.accounted() + RESERVE > ledger.cap:
            raise ValueError('Third child unavailable for full reserve')
        token = paid.load_key(env_file)
        paths['claim'].parent.mkdir(parents=True, exist_ok=True)
        with paths['claim'].open('x') as out:
            original.durable(out, {'series_id': SCHEMA, 'fresh_pass': repeat,
                'condition': condition, 'phase': stage,
                'manifest_sha256': manifest_sha,
                'root_review_sha256': sha(review), 'claimed_utc': original.utc()})
        requests = selected_requests(repeat, condition, stage)
        complete = True
        with paths['journal'].open('x') as journal, paths['attempts'].open('x') as attempts, \
             paths['responses'].open('x') as responses, paths['wire'].open('x') as wire:
            original.durable(journal, {'event': 'phase_started',
                'fresh_pass': repeat, 'condition': condition, 'phase': stage,
                'utc': original.utc()})
            for request in requests:
                for key in RUNTIME_SOURCE_KEYS:
                    read_bound(manifest['source_bindings'][key])
                # Recheck the public route, context, pricing and exact frozen payload.
                model, endpoint, current_reserve = original.live_controls(plan, condition)
                if current_reserve != RESERVE:
                    raise ValueError('Live reserve changed')
                rid, payload = request['record_id'], request['payload']
                if ledger.accounted() + RESERVE > ledger.cap:
                    complete = False
                    original.durable(journal, {'event': 'phase_stopped',
                        'id': rid, 'reason': 'child_cap_before_send',
                        'utc': original.utc()})
                    break
                original.durable(journal, {'event': 'request_intent',
                    'id': rid, 'request_sha256': request['request_sha256'],
                    'utc': original.utc()})
                attempt_id = ledger.reserve(RESERVE, rid)
                start = time.perf_counter()
                record = {'id': rid, 'series_id': SCHEMA, 'fresh_pass': repeat,
                    'condition': condition, 'phase': stage,
                    'attempt_id': attempt_id, 'request': payload,
                    'request_sha256': request['request_sha256'],
                    'manifest_sha256': manifest_sha, 'requested_model': study.MODEL,
                    'reasoning_effort': study.EFFORT, 'provider_endpoint': endpoint,
                    'model_catalog_entry': model, 'reference_labels_read': False,
                    'reserved_cost_usd': str(RESERVE), 'started_utc': original.utc()}
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
                record.update(elapsed_seconds=time.perf_counter()-start,
                    timing_boundary='Client request through raw capture and billing settlement; not pure inference time.',
                    observed_cost_usd=str(actual) if actual is not None else None,
                    cost_unknown=actual is None, billing_ok=billing_ok)
                if record.get('raw_response') is not None:
                    diagnostic = audit_response(record, 'openrouter_paid_v1',
                                                endpoint['context_length'] - 4096)
                    record['response_diagnostic'] = diagnostic
                    if not diagnostic['passed'] and record['status'] == 'ok':
                        record['status'] = 'prompt_admission_failure'
                original.durable(attempts, record)
                original.durable(journal, {'event': 'request_finished',
                    'id': rid, 'attempt_id': attempt_id,
                    'status': record['status'], 'billing_ok': billing_ok,
                    'cost_unknown': record['cost_unknown'],
                    'observed_cost_usd': record['observed_cost_usd'],
                    'utc': original.utc()})
                if not original.continue_record(
                        record, 'development' if stage == 'suffix' else stage):
                    complete = False
                    original.durable(journal, {'event': 'phase_stopped',
                        'id': rid, 'reason': record['status'],
                        'utc': original.utc()})
                    break
            if complete:
                original.durable(journal, {'event': 'phase_completed',
                    'fresh_pass': repeat, 'condition': condition, 'phase': stage,
                    'request_count': len(requests),
                    'attempt_ids': [x['attempt_id'] for x in rows(paths['attempts'])],
                    'utc': original.utc()})
        return complete
    finally:
        if paths['journal'].exists():
            events = rows(paths['journal'])
            if not events or events[-1].get('event') not in (
                    'phase_completed', 'phase_stopped', 'phase_aborted'):
                with paths['journal'].open('a') as out:
                    original.durable(out, {'event': 'phase_aborted',
                        'reason': 'exception_or_interruption',
                        'utc': original.utc()})
        ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('audit-prior')
    freeze_cmd = sub.add_parser('freeze')
    freeze_cmd.add_argument('--budget-manifest', required=True)
    freeze_cmd.add_argument('--old-reconciliation', required=True)
    verify_cmd = sub.add_parser('verify')
    verify_cmd.add_argument('--manifest-sha256', required=True)
    run_cmd = sub.add_parser('run')
    run_cmd.add_argument('--manifest-sha256', required=True)
    run_cmd.add_argument('--fresh-pass', required=True)
    run_cmd.add_argument('--condition', required=True)
    run_cmd.add_argument('--stage', required=True)
    run_cmd.add_argument('--root-review-receipt', required=True)
    run_cmd.add_argument('--env-file')
    args = parser.parse_args()
    if args.action == 'audit-prior':
        value = audit_prior()
        print(json.dumps({'failed_id': 'DEV-005',
                          'never_sent_ids': value['never_sent_ids'],
                          'prior_unknown_bound_ids': list(value['historical_unknown_upper_bounds'])}))
    elif args.action == 'freeze':
        print(freeze(Path(args.budget_manifest), Path(args.old_reconciliation)))
    elif args.action == 'verify':
        verify_manifest(args.manifest_sha256)
        print(args.manifest_sha256)
    else:
        print(json.dumps({'completed': execute(
            args.manifest_sha256, args.fresh_pass, args.condition,
            args.stage, Path(args.root_review_receipt), args.env_file)}))


if __name__ == '__main__':
    main()
