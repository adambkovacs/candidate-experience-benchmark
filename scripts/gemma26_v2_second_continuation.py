#!/usr/bin/env python3
"""Offline-prepared second Gemma26 continuation after fresh2/P0 DEV-002.

The first continuation and its failed position remain immutable. Freeze and
dispatch require a separately reconciled old child and a new v3 child. This
module does neither operation on import or during its read-only audit command.
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
import gemma26_v2_continuation as first
import openrouter_paid_benchmark as paid
import paid_budget_partitions_v3 as partitions
from prompt_admission import audit_response

SCHEMA = 'gemma26-on-v2-second-interruption-continuation-v1'
FIRST_SHA = '1e6d02c83306eb8e61de8d71048c974b98aedc08c07ffa69cb8a26c21c98e1e3'
FIRST_SEALED_CHILD_SHA = 'd8483377f27b085ebefbc6bb280b563f59e62ff703f1a23d945a721802bc0ec0'
FIRST_RECONCILIATION_SHA = 'f3a2154549a9c437c52058e33faebc3f8c733920b4012c9d00c771fe0c8cf88c'
FIRST_STOP_SHA = {
    'claim': '805c0346cc1e5186eba96e93a66f446d44cc85e5e56414f77a5512b40c0f257e',
    'review': 'ec9a548ceb6ac490979d1c1c2d8e389d4a4bcee5a24b82d572c73f43ce423da4',
    'journal': 'dfacabfe0e2c72975772ca84547736e01b57b0125c3ad9b0ecda02b9278ddd00',
    'attempts': '97ab8826f07400cedc7e686ba453fd4006a0a3d45e4a7e0a9c031d0646995780',
    'responses': '181a7f63c2e89c43316348ec928ffd02fdefa9fd2f88dbe54a69fed32d57343d',
    'wire': '46e0b76409866acb304df1fb0b89de8ba9b56b7a7455b58544dd933ca34b95a7',
}
BASE = study.BASE
PREVIOUS = first.OUTPUT
OUTPUT = BASE / 'second-interruption-continuation-v1'
MASTER = original.MASTER
PARTITION_ID = 'gemma26-on-v2-second-interruption-v1'
RESERVE = first.RESERVE
IDS = first.IDS
SUFFIX = IDS[2:]
STAGES = [('fresh2', 'P0', 'suffix')]
for _condition in study.ORDERS['fresh3']:
    STAGES.extend((('fresh3', _condition, 'smoke'),
                   ('fresh3', _condition, 'development')))
RUNTIME_HELPERS = (
    'development_benchmark', 'openrouter_paid_benchmark',
    'paid_budget_partitions_v3', 'openrouter_budget_v3',
    'openrouter_benchmark', 'prompt_admission',
    'prompt_execution_gates', 'frozen_prompt_variants',
)
RUNTIME_SOURCE_KEYS = ('controller', 'first_controller',
                       'original_controller', 'original_study') + tuple(
                           'runtime_' + name for name in RUNTIME_HELPERS)


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


def verify_runtime_sources(manifest):
    """Catch a normal helper edit before another frozen request is reserved."""
    sources = manifest['source_bindings']
    for key in RUNTIME_SOURCE_KEYS:
        read_bound(sources[key])


def selected_requests(repeat, condition, stage):
    if (repeat, condition, stage) not in STAGES:
        raise ValueError('Stage outside second continuation schedule')
    plan = study.verify(repeat, first.PLAN_SHAS[repeat])
    source = plan['conditions'][condition][
        'development' if stage == 'suffix' else stage]
    chosen = source[2:] if stage == 'suffix' else source
    expected = SUFFIX if stage == 'suffix' else IDS[:3] if stage == 'smoke' else IDS
    if [item['record_id'] for item in chosen] != expected:
        raise ValueError('Frozen selected request membership differs')
    return chosen


def verify_stopped_prefix():
    """Verify prior closure and the exact unsent boundary without error text output."""
    manifest = first.verify_manifest(FIRST_SHA)
    first.require_order(manifest, FIRST_SHA, 'fresh2', 'P0', 'development')
    paths = first.stage_paths('fresh2', 'P0', 'development')
    paths['review'] = first.review_path('fresh2', 'P0', 'development')
    for kind, expected in FIRST_STOP_SHA.items():
        if sha(paths[kind]) != expected:
            raise ValueError('First continuation stopped evidence changed: ' + kind)
    first.verify_review(paths['review'], manifest, FIRST_SHA,
                        'fresh2', 'P0', 'development')
    claim = json.loads(paths['claim'].read_text())
    if any(claim.get(k) != v for k, v in {
            'series_id': first.SCHEMA, 'fresh_pass': 'fresh2',
            'condition': 'P0', 'phase': 'development',
            'manifest_sha256': FIRST_SHA,
            'root_review_sha256': FIRST_STOP_SHA['review']}.items()):
        raise ValueError('First continuation stopped claim differs')
    attempts, responses, wire, journal = (rows(paths[k]) for k in
                                            ('attempts', 'responses', 'wire', 'journal'))
    requests = study.verify('fresh2', first.PLAN_SHAS['fresh2'])['conditions']['P0']['development'][:2]
    if ([r.get('id') for r in attempts] != IDS[:2] or
            [r.get('id') for r in responses] != IDS[:1] or
            [r.get('id') for r in wire] != IDS[:1] or
            len(journal) != 8 or journal[0].get('event') != 'phase_started' or
            journal[-1].get('event') != 'phase_stopped' or
            journal[-1].get('id') != 'DEV-002' or
            journal[-1].get('reason') != 'service_error'):
        raise ValueError('First continuation stopped membership or terminal differs')
    seen = set()
    for i, (request, record) in enumerate(zip(requests, attempts)):
        rid, attempt = request['record_id'], record.get('attempt_id')
        intent, started, finished = journal[1 + 3*i:4 + 3*i]
        if (not isinstance(attempt, str) or not attempt or attempt in seen or
                record.get('series_id') != first.SCHEMA or
                record.get('manifest_sha256') != FIRST_SHA or
                record.get('request') != request['payload'] or
                record.get('request_sha256') != request['request_sha256'] or
                record.get('reference_labels_read') is not False or
                paid.number(record.get('reserved_cost_usd')) != RESERVE or
                (intent.get('event'), intent.get('id'),
                 intent.get('request_sha256')) !=
                    ('request_intent', rid, request['request_sha256']) or
                (started.get('event'), started.get('id'),
                 started.get('attempt_id'), started.get('request_sha256')) !=
                    ('request_started', rid, attempt, request['request_sha256']) or
                (finished.get('event'), finished.get('id'), finished.get('attempt_id'),
                 finished.get('status'), finished.get('billing_ok'),
                 finished.get('cost_unknown'), finished.get('observed_cost_usd')) !=
                    ('request_finished', rid, attempt, record.get('status'),
                     record.get('billing_ok'), record.get('cost_unknown'),
                     record.get('observed_cost_usd'))):
            raise ValueError('Stopped attempt or journal differs at ' + rid)
        seen.add(attempt)
    good, failed = attempts
    captured, raw = wire[0], responses[0]
    if (good.get('status') != 'ok' or good.get('billing_ok') is not True or
            good.get('cost_unknown') is not False or
            good.get('observed_cost_usd') != '0.00028017' or
            raw.get('attempt_id') != good['attempt_id'] or
            raw.get('raw_response') != good.get('raw_response') or
            captured.get('attempt_id') != good['attempt_id'] or
            captured.get('http_status') != 200 or
            captured.get('body_truncated_at_limit') is not False or
            captured.get('read_error') is not None or
            json.loads(base64.b64decode(captured['body_base64'], validate=True)) !=
                good.get('raw_response') or
            failed.get('status') != 'service_error' or
            failed.get('error_type') != 'URLError' or
            failed.get('billing_ok') is not False or
            failed.get('cost_unknown') is not True or
            failed.get('observed_cost_usd') is not None):
        raise ValueError('DEV-001 known or DEV-002 unknown outcome differs')
    child = PREVIOUS / ('budget-' + first.PARTITION_ID + '.jsonl')
    charges = [e for e in rows(child) if e.get('attempt_id') == failed['attempt_id']]
    if not charges or charges[0] != {
            'event': 'reserve', 'attempt_id': failed['attempt_id'],
            'record_id': 'DEV-002', 'usd': str(RESERVE)}:
        raise ValueError('DEV-002 full reservation differs')
    return {'failed_id': 'DEV-002', 'failed_attempt_id': failed['attempt_id'],
            'never_sent_ids': SUFFIX, 'known_prefix_usd': good['observed_cost_usd'],
            'files': {key: binding(path) for key, path in paths.items()},
            'first_manifest': binding(PREVIOUS / 'manifest.json'),
            'child_path': child, 'child_events': rows(child)}


def verify_old_seal(path, prefix):
    """Require operator accounting of DEV-002 before a new allocation."""
    path = Path(path).resolve()
    expected_path = (PREVIOUS / 'terminal-reconciliation-after-dev002.json').resolve()
    if path != expected_path:
        raise ValueError('Exact first-child reconciliation path differs')
    child = prefix['child_path']
    if sha(child) != FIRST_SEALED_CHILD_SHA or sha(path) != FIRST_RECONCILIATION_SHA:
        raise ValueError('First child sealed evidence changed')
    events = rows(child)
    charges = [e for e in events if e.get('attempt_id') == prefix['failed_attempt_id']]
    if (len(charges) != 2 or charges[0] != {
            'event': 'reserve', 'attempt_id': prefix['failed_attempt_id'],
            'record_id': 'DEV-002', 'usd': str(RESERVE)} or
            charges[1].get('event') != 'unknown_cost_accounted_as_upper_bound' or
            paid.number(charges[1].get('usd')) != RESERVE or
            charges[1].get('actual_cost_usd') is not None or
            charges[1].get('evidence_sha256') != FIRST_STOP_SHA['attempts'] or
            Path(charges[1].get('evidence_path', '')).resolve() !=
                first.stage_paths('fresh2', 'P0', 'development')['attempts'].resolve() or
            events[-1].get('event') != 'partition_closed'):
        raise ValueError('DEV-002 bound or first child seal differs')
    known = sum((paid.number(e['usd']) for e in events if e['event'] == 'settle'), Decimal(0))
    unknown = sum((paid.number(e['usd']) for e in events
                   if e['event'] == 'unknown_cost_accounted_as_upper_bound'), Decimal(0))
    cap = paid.number(events[0]['cap_usd'])
    if unknown != RESERVE or known + unknown > cap:
        raise ValueError('First child terminal accounting differs')
    expected = {'event': 'partition_reconciled',
                'partition_id': first.PARTITION_ID,
                'known_actual_usd': str(known),
                'unknown_upper_bound_usd': str(unknown),
                'unused_allocation_released_usd': str(cap - known - unknown),
                'child_ledger': str(child.resolve()), 'child_sha256': sha(child)}
    if json.loads(path.read_text()) != expected or expected not in rows(MASTER):
        raise ValueError('First child master reconciliation differs')
    first.budget_entry(PREVIOUS / 'budget.json', require_active=False)
    return {'old_child_ledger': binding(child),
            'old_reconciliation': binding(path),
            'known_actual_usd': str(known),
            'unknown_upper_bound_usd': str(unknown)}


def budget_entry(path, require_fresh=False, require_dispatch=False):
    path = Path(path).resolve()
    if path != (OUTPUT / 'budget.json').resolve():
        raise ValueError('Second child manifest path differs')
    data = json.loads(path.read_text())
    entries = data.get('partitions')
    if (data.get('version') != 'paid-partitions-v1' or
            data.get('master_ledger') != str(MASTER.resolve()) or
            not isinstance(entries, list) or len(entries) != 1):
        raise ValueError('Second child manifest differs')
    entry = entries[0]
    cap = paid.number(entry.get('cap_usd'))
    child = OUTPUT / ('budget-' + PARTITION_ID + '.jsonl')
    if (entry.get('id') != PARTITION_ID or cap < RESERVE or cap > Decimal('12.38') or
            (entry.get('model'), entry.get('provider'), entry.get('reasoning')) !=
            (study.MODEL, study.PROVIDER, study.EFFORT) or
            Path(entry.get('child_ledger', '')).resolve() != child.resolve()):
        raise ValueError('Second child route or cap differs')
    master = rows(MASTER)
    allocations = [e for e in master if e.get('event') == 'budget_partition'
                   and e.get('partition_id') == PARTITION_ID]
    if len(allocations) != 1 or any(allocations[0].get(k) != v for k, v in {
            'allocated_usd': entry['cap_usd'], 'manifest_path': str(path),
            'manifest_sha256': sha(path), 'child_ledger': str(child.resolve()),
            'model': study.MODEL, 'provider': study.PROVIDER,
            'reasoning': study.EFFORT}.items()):
        raise ValueError('Second child allocation differs')
    events = rows(child)
    if not events or events[0] != {'event': 'budget', 'cap_usd': entry['cap_usd']}:
        raise ValueError('Second child opening differs')
    reconciled = [e for e in master if e.get('event') == 'partition_reconciled'
                  and e.get('partition_id') == PARTITION_ID]
    closed = [i for i, e in enumerate(events) if e.get('event') == 'partition_closed']
    if require_fresh and (reconciled or closed or len(events) != 1):
        raise ValueError('Second child is spent, sealed or reconciled')
    if require_dispatch and (reconciled or closed):
        raise ValueError('Second child is sealed or reconciled')
    if reconciled or closed:
        if len(reconciled) != 1 or closed != [len(events) - 1]:
            raise ValueError('Second child terminal lifecycle differs')
        pending, known, unknown = {}, Decimal(0), Decimal(0)
        for event in events[1:-1]:
            kind, attempt = event.get('event'), event.get('attempt_id')
            if kind == 'reserve':
                amount = paid.number(event.get('usd'))
                if pending or amount != RESERVE or not attempt:
                    raise ValueError('Second child reserve lifecycle differs')
                pending[attempt] = amount
            elif kind == 'settle':
                amount = paid.number(event.get('usd'))
                if attempt not in pending or not Decimal(0) <= amount <= pending[attempt]:
                    raise ValueError('Second child settle lifecycle differs')
                known += amount
                del pending[attempt]
            elif kind == 'unknown_cost_accounted_as_upper_bound':
                amount = paid.number(event.get('usd'))
                if (attempt not in pending or amount != pending[attempt] or
                        event.get('actual_cost_usd') is not None or
                        not event.get('evidence_path') or not event.get('evidence_sha256')):
                    raise ValueError('Second child unknown lifecycle differs')
                unknown += amount
                del pending[attempt]
            else:
                raise ValueError('Second child terminal event differs')
        expected = {'event': 'partition_reconciled', 'partition_id': PARTITION_ID,
                    'known_actual_usd': str(known),
                    'unknown_upper_bound_usd': str(unknown),
                    'unused_allocation_released_usd': str(cap - known - unknown),
                    'child_ledger': str(child.resolve()), 'child_sha256': sha(child)}
        if pending or known + unknown > cap or reconciled[0] != expected:
            raise ValueError('Second child terminal accounting differs')
    return entry


def expected_manifest(budget_path, reconciliation_path, require_fresh=False):
    prefix = verify_stopped_prefix()
    old = verify_old_seal(reconciliation_path, prefix)
    entry = budget_entry(budget_path, require_fresh=require_fresh)
    sources = {'controller': binding(__file__),
               'first_controller': binding(first.__file__),
               'original_controller': binding(original.__file__),
               'original_study': binding(study.__file__),
               'first_manifest': prefix['first_manifest'],
               'new_budget_manifest': binding(budget_path),
               'old_child_ledger': old['old_child_ledger'],
               'old_reconciliation': old['old_reconciliation'],
               **{'stopped_' + k: v for k, v in prefix['files'].items()}}
    for name in RUNTIME_HELPERS:
        sources['runtime_' + name] = binding(ROOT / 'scripts' / (name + '.py'))
    for repeat in study.ORDERS:
        sources['original_plan_' + repeat] = binding(BASE / repeat / 'manifest.json')
    first_manifest = first.verify_manifest(FIRST_SHA)
    for repeat, condition, stage in first.STAGES[:6]:
        first.verify_stage_closure(first_manifest, FIRST_SHA, repeat, condition, stage)
        for kind, file in first.stage_paths(repeat, condition, stage).items():
            sources[f'first_{repeat}_{condition}_{stage}_{kind}'] = binding(file)
        sources[f'first_{repeat}_{condition}_{stage}_review'] = binding(
            first.review_path(repeat, condition, stage))
    stages = []
    for repeat, condition, stage in STAGES:
        selected = selected_requests(repeat, condition, stage)
        stages.append({'fresh_pass': repeat, 'condition': condition, 'stage': stage,
                       'ids': [r['record_id'] for r in selected],
                       'request_sha256': [r['request_sha256'] for r in selected]})
    return {'schema': SCHEMA, 'status': 'FROZEN', 'series_id': SCHEMA,
            'configuration_id': study.CONFIG,
            'method': 'descriptive-second-interruption-continuation',
            'clean_matched_three_eligible': False,
            'original_failed_id': 'DEV-007', 'first_suffix_failed_id': 'DEV-002',
            'original_never_sent_ids': SUFFIX,
            'old_known_actual_usd': old['known_actual_usd'],
            'old_unknown_upper_bound_usd': old['unknown_upper_bound_usd'],
            'stages': stages, 'source_bindings': sources,
            'partition_id': PARTITION_ID, 'child_cap_usd': entry['cap_usd'],
            'reserve_usd': str(RESERVE),
            'retry_policy': 'no retries, repairs or replay of fresh2/P0 DEV-001 or DEV-002',
            'reference_labels_read': False}


def freeze(budget_path, reconciliation_path):
    path = OUTPUT / 'manifest.json'
    if path.exists():
        raise FileExistsError('Second continuation manifest already frozen')
    value = expected_manifest(budget_path, reconciliation_path, require_fresh=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with path.open('x') as out:
        json.dump(value, out, indent=2)
        out.write('\n'); out.flush(); os.fsync(out.fileno())
    return sha(path)


def verify_manifest(expected_sha):
    path = OUTPUT / 'manifest.json'
    if sha(path) != expected_sha:
        raise ValueError('Second continuation manifest hash differs')
    value = json.loads(path.read_text())
    for item in value['source_bindings'].values():
        read_bound(item)
    verify_runtime_sources(value)
    if value != expected_manifest(
            read_bound(value['source_bindings']['new_budget_manifest']),
            read_bound(value['source_bindings']['old_reconciliation'])):
        raise ValueError('Second continuation manifest differs from sealed sources')
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
        raise ValueError('Exact second root review path differs')
    value = json.loads(path.read_text())
    if any(value.get(k) != v for k, v in expected_review(
            manifest, manifest_sha, repeat, condition, stage).items()):
        raise ValueError('Second root review differs')
    return value


def verify_stage_closure(manifest, manifest_sha, repeat, condition, stage):
    paths = stage_paths(repeat, condition, stage)
    if not all(path.is_file() for path in paths.values()):
        raise ValueError('Second continuation stage evidence missing')
    review = review_path(repeat, condition, stage)
    verify_review(review, manifest, manifest_sha, repeat, condition, stage)
    claim = json.loads(paths['claim'].read_text())
    if any(claim.get(k) != v for k, v in {
            'series_id': SCHEMA, 'fresh_pass': repeat, 'condition': condition,
            'phase': stage, 'manifest_sha256': manifest_sha,
            'root_review_sha256': sha(review)}.items()):
        raise ValueError('Second continuation claim differs')
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
            journal[-1].get('attempt_ids') != [r['attempt_id'] for r in attempts]):
        raise ValueError('Second continuation closure membership differs')
    entry = budget_entry(read_bound(manifest['source_bindings']['new_budget_manifest']))
    charges = rows(Path(entry['child_ledger']))
    for i, (request, record, response, captured) in enumerate(
            zip(requests, attempts, responses, wire)):
        rid, attempt = request['record_id'], record['attempt_id']
        intent, started, finished = journal[1 + 3*i:4 + 3*i]
        if (record.get('series_id') != SCHEMA or
                record.get('manifest_sha256') != manifest_sha or
                record.get('request') != request['payload'] or
                record.get('request_sha256') != request['request_sha256'] or
                record.get('reference_labels_read') is not False or
                record.get('reserved_cost_usd') != str(RESERVE) or
                record.get('status') != 'ok' or
                record.get('billing_ok') is not True or
                record.get('cost_unknown') is not False or
                record.get('observed_cost_usd') is None or
                not Decimal(0) <= paid.number(record['observed_cost_usd']) <= RESERVE or
                response.get('attempt_id') != attempt or
                response.get('request_sha256') != request['request_sha256'] or
                response.get('raw_response') != record.get('raw_response') or
                captured.get('attempt_id') != attempt or
                captured.get('http_status') != 200 or
                captured.get('request_sha256') != request['request_sha256'] or
                captured.get('body_truncated_at_limit') is not False or
                captured.get('read_error') is not None or
                json.loads(base64.b64decode(captured['body_base64'], validate=True)) !=
                    record.get('raw_response') or
                [(e.get('event'), e.get('id'), e.get('attempt_id'),
                  e.get('request_sha256')) for e in
                 (intent, started, finished)] !=
                    [('request_intent', rid, None, request['request_sha256']),
                     ('request_started', rid, attempt, request['request_sha256']),
                     ('request_finished', rid, attempt, None)] or
                finished.get('status') != 'ok' or
                finished.get('billing_ok') is not True or
                finished.get('cost_unknown') is not False or
                finished.get('observed_cost_usd') != record['observed_cost_usd'] or
                [e for e in charges if e.get('attempt_id') == attempt] != [
                    {'event': 'reserve', 'attempt_id': attempt,
                     'record_id': rid, 'usd': str(RESERVE)},
                    {'event': 'settle', 'attempt_id': attempt,
                     'usd': record['observed_cost_usd']}]):
            raise ValueError('Second continuation response or charge differs at ' + rid)
        classified = original.classify(record['raw_response'],
                                       record['model_catalog_entry'],
                                       record['provider_endpoint'])
        if (any(record.get(k) != v for k, v in classified.items()) or
                paid.number(record['raw_response']['usage']['cost']) !=
                    paid.number(record['observed_cost_usd']) or
                record.get('response_diagnostic') != audit_response(
                    record, 'openrouter_paid_v1',
                    record['provider_endpoint']['context_length'] - 4096) or
                record['response_diagnostic'].get('passed') is not True):
            raise ValueError('Second continuation classification differs at ' + rid)
    return {k + '_sha256': sha(v) for k, v in paths.items()}


def require_order(manifest, manifest_sha, repeat, condition, stage):
    target = (repeat, condition, stage)
    if target not in STAGES:
        raise ValueError('Unknown second continuation stage')
    for prior in STAGES[:STAGES.index(target)]:
        verify_stage_closure(manifest, manifest_sha, *prior)
    if stage == 'development':
        smoke = verify_stage_closure(manifest, manifest_sha,
                                     repeat, condition, 'smoke')
        path = OUTPUT / repeat / condition / 'smoke-inspection.json'
        value = json.loads(path.read_text())
        if any(value.get(k) != v for k, v in {
                'schema': SCHEMA + '-smoke-inspection',
                'decision': 'accepted_unchanged', 'series_id': SCHEMA,
                'manifest_sha256': manifest_sha,
                'attempts_sha256': smoke['attempts_sha256'],
                'responses_sha256': smoke['responses_sha256'],
                'wire_sha256': smoke['wire_sha256'],
                'journal_sha256': smoke['journal_sha256']}.items()):
            raise ValueError('Second continuation smoke inspection differs')


def execute(manifest_sha, repeat, condition, stage, review, env_file=None):
    manifest = verify_manifest(manifest_sha)
    verify_runtime_sources(manifest)
    require_order(manifest, manifest_sha, repeat, condition, stage)
    verify_review(review, manifest, manifest_sha, repeat, condition, stage)
    paths = stage_paths(repeat, condition, stage)
    if any(path.exists() for path in paths.values()):
        raise FileExistsError('Second continuation stage already claimed')
    plan = study.verify(repeat, first.PLAN_SHAS[repeat])
    model, endpoint, reserve = original.live_controls(plan, condition)
    if reserve != RESERVE:
        raise ValueError('Live reserve differs from frozen request')
    budget_path = read_bound(manifest['source_bindings']['new_budget_manifest'])
    budget_entry(budget_path, require_dispatch=True)
    ledger = partitions.open_partition(MASTER, budget_path, PARTITION_ID,
                                       study.MODEL, study.PROVIDER, study.EFFORT)
    try:
        if ledger.cap != paid.number(manifest['child_cap_usd']) or ledger.master_cap != Decimal('12.38'):
            raise ValueError('Master or second child cap differs')
        _, pending, blocked = ledger.state()
        if pending or blocked or ledger.closed or ledger.accounted() + RESERVE > ledger.cap:
            raise ValueError('Second child unavailable for full reserve')
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
                verify_runtime_sources(manifest)
                rid, payload = request['record_id'], request['payload']
                original.durable(journal, {'event': 'request_intent',
                    'id': rid, 'request_sha256': request['request_sha256'],
                    'utc': original.utc()})
                if ledger.accounted() + RESERVE > ledger.cap:
                    complete = False
                    original.durable(journal, {'event': 'phase_stopped',
                        'id': rid, 'reason': 'child_cap_before_send',
                        'utc': original.utc()})
                    break
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
    sub.add_parser('audit-prefix')
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
    if args.action == 'audit-prefix':
        value = verify_stopped_prefix()
        print(json.dumps({'failed_id': value['failed_id'],
                          'never_sent_ids': value['never_sent_ids'],
                          'known_prefix_usd': value['known_prefix_usd']}))
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
