#!/usr/bin/env python3
"""Frozen OpenRouter Gemini low-effort repeat plans and gated batch execution."""
import argparse
import base64
import binascii
from decimal import Decimal
import hashlib
import http.client
import json
import os
from pathlib import Path
import time
import urllib.error
from urllib.parse import quote

from codex_batch_benchmark import parse_batch
from development_benchmark import ROOT, read_rows
import gemini_openrouter_batch_v3 as v3
import openrouter_repeat_wave as wave
from openrouter_benchmark import allowed_returned_models
from paid_budget_partitions_v2 import open_partition

BASE = ROOT / 'results/repeatability-v1'
COVERAGE = ROOT / 'results/repeatability-v1/coverage.json'
MASTER = ROOT / 'results/openrouter-paid-budget.jsonl'
SCHEMA = 'gemini-openrouter-repeat-study-v1'
REVIEW_SCHEMA = 'gemini-openrouter-repeat-root-review-v1'
CAP = '0.30'
ORDERS = {'repeat2': ('P1', 'P2', 'P0'), 'repeat3': ('P2', 'P0', 'P1')}
CONFIGS = {
    'gemini36-flash-low-p0-openrouter-v3': ('gemini36-flash-low', 'google/gemini-3.6-flash', 'g36-low-repeat-v1'),
    'gemini37-flash-low-p0-openrouter-v3': ('gemini37-flash-low', 'google/gemini-3.7-flash', 'g37-low-repeat-v1'),
}
SOURCE_CODE = ('scripts/gemini_openrouter_batch_v3.py', 'scripts/codex_batch_benchmark.py',
               'scripts/frozen_prompt_variants.py', 'scripts/openrouter_repeat_wave.py',
               'scripts/openrouter_paid_benchmark.py', 'scripts/paid_budget_partitions_v2.py',
               'scripts/openrouter_budget_v2.py', 'data/pilot/inputs.jsonl',
               'docs/LABELING_GUIDE.md', 'schemas/judgments.schema.json',
               'prompts/variants-v1/manifest.json', 'prompts/variants-v1/P1-classifier.txt',
               'prompts/variants-v1/P2-classifier-sop.txt')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def path_inside(path):
    path = Path(path).resolve()
    path.relative_to(ROOT.resolve())
    return path


def bind(path):
    path = path_inside(path)
    return {'path': str(path.relative_to(ROOT)), 'sha256': digest(path.read_bytes())}


def bound(item):
    path = path_inside(ROOT / item['path'])
    if digest(path.read_bytes()) != item['sha256']:
        raise ValueError('Bound source changed: ' + item['path'])
    return path


def lines(path):
    raw = Path(path).read_bytes()
    if raw and not raw.endswith(b'\n'):
        raise ValueError('Incomplete JSONL tail: ' + str(path))
    return [json.loads(row) for row in raw.splitlines() if row.strip()]


def paths_for(config, repeat, condition):
    if config not in CONFIGS or repeat not in ORDERS or condition not in ORDERS[repeat]:
        raise ValueError('Outside exact Gemini repeat roster')
    return BASE / config / repeat / condition


def plan_path(config, repeat):
    return BASE / config / repeat / 'manifest.json'


def historical_paths(coverage, condition):
    entry = coverage['source_paths'][condition]
    output = path_inside(ROOT / entry['outputs'])
    folder = output.parent
    return {'manifest': ROOT / entry['manifest'], 'development_records': output,
            'development_attempts': ROOT / entry['attempts'],
            'development_journal': ROOT / entry['journal'],
            'smoke_records': folder / 'smoke-records.jsonl',
            'smoke_attempts': folder / 'smoke-attempts.jsonl',
            'smoke_journal': folder / 'smoke-journal.jsonl',
            'smoke_inspection': folder / 'smoke-inspection-v3.json'}


def source_phase(binding_map, phase, batches):
    attempts = lines(bound(binding_map[phase + '_attempts']))
    journal = lines(bound(binding_map[phase + '_journal']))
    records = lines(bound(binding_map[phase + '_records']))
    expected_ids = ([f'DEV-{i:03}' for i in range(1, 4)] if phase == 'smoke'
                    else [f'DEV-{i:03}' for i in range(1, 61)])
    if len(attempts) != batches or [x.get('id') for x in records] != expected_ids:
        raise ValueError('Historical Gemini phase lacks exact batch/record coverage')
    expected_groups = [expected_ids] if phase == 'smoke' else [expected_ids[i:i + 10] for i in range(0, 60, 10)]
    if ([x.get('ids') for x in attempts] != expected_groups or
            any(x.get('status') not in ('ok', 'invalid_output') or x.get('billing_ok') is not True or
                x.get('cost_unknown') is not False for x in attempts)):
        raise ValueError('Historical Gemini batch controls or billing differ')
    for index, group in enumerate(expected_groups):
        attempt = attempts[index]
        for position, rid in enumerate(group):
            record = records[(index * 10 if phase == 'development' else 0) + position]
            if (record.get('id'), record.get('phase'), record.get('status'),
                    record.get('request_sha256'), record.get('batch_position')) != (
                    rid, phase, attempt['status'], attempt.get('request_sha256'), position):
                raise ValueError('Historical Gemini record differs from its batch attempt')
    terminal = journal[-1] if journal else None
    if (not isinstance(terminal, dict) or terminal.get('event') != 'terminal' or
            terminal.get('completed') is not True or terminal.get('expected_batches') != batches or
            terminal.get('started_batches') != batches or terminal.get('finished_batches') != batches):
        raise ValueError('Historical Gemini phase did not terminate complete')
    if phase == 'smoke':
        inspection = json.loads(bound(binding_map['smoke_inspection']).read_text())
        if inspection != {'schema': 'gemini-openrouter-smoke-inspection-v3', 'approved': True,
                          'manifest_sha256': binding_map['manifest']['sha256'],
                          'smoke_attempts_sha256': binding_map['smoke_attempts']['sha256'],
                          'smoke_records_sha256': binding_map['smoke_records']['sha256'],
                          'smoke_journal_sha256': binding_map['smoke_journal']['sha256']}:
            raise ValueError('Historical inspected Gemini smoke differs')
    return attempts


def expected_plan(config, repeat):
    if config not in CONFIGS or repeat not in ORDERS:
        raise ValueError('Outside exact Gemini repeat roster')
    short, model, partition_id = CONFIGS[config]
    coverage_raw = COVERAGE.read_bytes()
    coverage = json.loads(coverage_raw)
    groups = [x for x in coverage['groups'] if x.get('id') == config]
    if len(groups) != 1:
        raise ValueError('Missing or duplicate Gemini historical coverage')
    group = groups[0]
    if (group.get('historical_triple_status') != 'eligible_first_pass' or
            group.get('observed_condition_order') != ['P0', 'P1', 'P2'] or
            any(group['condition_status'].get(c) != 'eligible_first_pass' for c in ('P0', 'P1', 'P2'))):
        raise ValueError('Historical Gemini triple is not eligible')
    sources = {'coverage': bind(COVERAGE), 'controller': bind(__file__)}
    for item in SOURCE_CODE:
        sources[item] = bind(ROOT / item)
    conditions = {}
    original_p0 = config
    for condition in ('P0', 'P1', 'P2'):
        history = {key: bind(path) for key, path in historical_paths(group, condition).items()}
        historical_smoke = source_phase(history, 'smoke', 1)
        historical_development = source_phase(history, 'development', 6)
        old = json.loads(bound(history['manifest']).read_text())
        if (old.get('schema'), old.get('model'), old.get('effort'), old.get('provider'),
                old.get('variant'), old.get('timeout_seconds'), old.get('reference_labels_read'),
                old.get('no_automatic_retry')) != (
                'gemini-openrouter-batch-v3', model, 'low', v3.PROVIDER,
                condition, 300, False, True):
            raise ValueError('Historical Gemini manifest controls differ')
        if old.get('configuration_id') != (config if condition == 'P0' else f'{short}-{condition.lower()}-openrouter-v3'):
            raise ValueError('Historical Gemini configuration differs')
        if condition == 'P0':
            if old.get('parent_p0') is not None:
                raise ValueError('Historical P0 has a parent')
        elif not old.get('parent_p0') or old['parent_p0'].get('baseline_id') != original_p0:
            raise ValueError('Historical variant lacks original P0 identity')
        for item in old['source_bindings'].values():
            bound(item)
        catalog = json.loads(bound(old['catalog']).read_text())
        endpoints = json.loads(bound(old['endpoints']).read_text())
        _, endpoint = v3.check_catalog(model, 'low', catalog, endpoints)
        requests = v3.prepared_requests(model, 'low', condition, original_p0, endpoint)
        if requests != old['requests'] or len(requests) != 7:
            raise ValueError('Historical Gemini request reconstruction differs')
        for attempt, request in zip(historical_smoke + historical_development, requests):
            if (attempt.get('request'), attempt.get('request_sha256'), attempt.get('reference_labels_read')) != (
                    request['payload'], request['payload_sha256'], False):
                raise ValueError('Historical Gemini attempt request differs from frozen payload')
        if [x['record_ids'] for x in requests] != [
                [f'DEV-{i:03}' for i in range(1, 4)],
                *[[f'DEV-{i:03}' for i in range(start, start + 10)] for start in range(1, 61, 10)]]:
            raise ValueError('Historical Gemini batch membership differs')
        conditions[condition] = {'historical': history, 'catalog': old['catalog'],
                                 'endpoints': old['endpoints'], 'requests': requests}
    return {'schema': SCHEMA, 'configuration_id': config, 'model': model,
            'provider': v3.PROVIDER, 'provider_name': v3.PROVIDER_NAME, 'effort': 'low',
            'repeat': repeat, 'condition_order': list(ORDERS[repeat]),
            'historical_order': ['P0', 'P1', 'P2'], 'original_p0_baseline_id': original_p0,
            'timeout_seconds': 300, 'partition_id': partition_id,
            'proposed_partition_cap_usd': CAP, 'partition_allocated': False,
            'reference_labels_read': False, 'no_automatic_retry': True,
            'request_unit': 'one smoke3 then six development batch10',
            'source_bindings': sources, 'conditions': conditions}


def validate_plan(path, sha=None):
    path = path_inside(path)
    raw = path.read_bytes()
    if sha is not None and digest(raw) != sha:
        raise ValueError('Repeat plan hash differs')
    plan = json.loads(raw)
    if plan != expected_plan(plan['configuration_id'], plan['repeat']):
        raise ValueError('Repeat plan differs from frozen source reconstruction')
    return plan


def prepare(config):
    for repeat in ORDERS:
        path = plan_path(config, repeat)
        value = expected_plan(config, repeat)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x') as out:
            json.dump(value, out, indent=2, ensure_ascii=False)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        print(repeat, digest(path.read_bytes()), path)


def phase_paths(config, repeat, condition, phase):
    if phase not in ('smoke', 'development'):
        raise ValueError('Unknown phase')
    folder = paths_for(config, repeat, condition)
    return {key: folder / (phase + '.' + filename) for key, filename in (
        ('claim', 'claim.json'), ('journal', 'journal.jsonl'),
        ('attempts', 'attempts.jsonl'), ('responses', 'responses.jsonl'),
        ('records', 'records.jsonl'))}


def complete(plan, condition):
    journal = phase_paths(plan['configuration_id'], plan['repeat'], condition, 'development')['journal']
    if not journal.exists():
        return False
    events = lines(journal)
    return bool(events) and events[-1].get('event') == 'phase_completed'


def require_order(plan, condition, phase):
    order = plan['condition_order']
    if condition not in order:
        raise ValueError('Condition outside frozen order')
    if plan['repeat'] == 'repeat3':
        prior_plan = validate_plan(plan_path(plan['configuration_id'], 'repeat2'))
        if not all(complete(prior_plan, c) for c in prior_plan['condition_order']):
            raise ValueError('Repeat 2 is incomplete')
    if not all(complete(plan, c) for c in order[:order.index(condition)]):
        raise ValueError('Prior condition is incomplete')
    if phase == 'development':
        proof_path = paths_for(plan['configuration_id'], plan['repeat'], condition) / 'smoke-inspection.json'
        if not proof_path.exists():
            raise ValueError('New inspected smoke required')
        proof = json.loads(proof_path.read_text())
        smoke = phase_paths(plan['configuration_id'], plan['repeat'], condition, 'smoke')
        if (proof.get('schema') != 'gemini-repeat-smoke-inspection-v1' or
                proof.get('decision') != 'accepted_unchanged' or
                proof.get('plan_sha256') != digest(plan_path(plan['configuration_id'], plan['repeat']).read_bytes()) or
                any(proof.get(k + '_sha256') != digest(smoke[k].read_bytes()) for k in ('journal', 'attempts', 'responses', 'records'))):
            raise ValueError('New smoke inspection binding differs')


def review_gate(plan, phase, condition, review_path, plan_sha):
    receipt = json.loads(path_inside(review_path).read_text())
    expected = {'schema': REVIEW_SCHEMA, 'approved': True,
                'configuration_id': plan['configuration_id'], 'repeat': plan['repeat'],
                'condition': condition, 'phase': phase, 'plan_sha256': plan_sha,
                'plan_sha256_by_repeat': {r: digest(plan_path(plan['configuration_id'], r).read_bytes()) for r in ORDERS},
                'controller_sha256': plan['source_bindings']['controller']['sha256'],
                'partition_id': plan['partition_id'], 'partition_cap_usd': CAP,
                'master_ledger': str(MASTER)}
    if not all(receipt.get(k) == v for k, v in expected.items()):
        raise ValueError('Exact Gemini repeat root review missing or differs')
    budget = receipt.get('budget_manifest')
    if not isinstance(budget, dict) or set(budget) != {'path', 'sha256'}:
        raise ValueError('Reviewed budget manifest binding missing')
    budget_path = bound(budget)
    if phase == 'development':
        inspection = paths_for(plan['configuration_id'], plan['repeat'], condition) / 'smoke-inspection.json'
        if receipt.get('smoke_inspection_sha256') != digest(inspection.read_bytes()):
            raise ValueError('Root review does not bind new smoke inspection')
    elif receipt.get('smoke_inspection_sha256') is not None:
        raise ValueError('Smoke review cannot carry development inspection')
    return budget_path


def live_controls(plan, condition):
    model = plan['model']
    catalog = v3.fetch('/models', timeout=plan['timeout_seconds'])
    endpoints = v3.fetch('/models/' + quote(model, safe='/') + '/endpoints', timeout=plan['timeout_seconds'])
    live_model, live_endpoint = v3.check_catalog(model, plan['effort'], catalog, endpoints)
    old = plan['conditions'][condition]
    frozen_model = json.loads(bound(old['catalog']).read_text())
    frozen_endpoints = json.loads(bound(old['endpoints']).read_text())
    expected_model, expected_endpoint = v3.check_catalog(model, plan['effort'], frozen_model, frozen_endpoints)
    for key in ('reasoning', 'supported_parameters'):
        if live_model.get(key) != expected_model.get(key):
            raise ValueError('Live Gemini model controls differ')
    for key in ('tag', 'provider_name', 'model_id', 'context_length', 'max_completion_tokens',
                'pricing', 'supported_parameters'):
        if live_endpoint.get(key) != expected_endpoint.get(key):
            raise ValueError('Live Gemini endpoint controls or price differ')
    if v3.prepared_requests(model, plan['effort'], condition,
                            plan['original_p0_baseline_id'], live_endpoint) != old['requests']:
        raise ValueError('Live Gemini payload would differ from frozen request')
    return live_model, live_endpoint


def capture_http_error(exc, token, out, request, attempt_id):
    read_error = None
    try:
        body = exc.read(wave.MAX_RESPONSE_BYTES + 1)
    except http.client.IncompleteRead as interrupted:
        body = interrupted.partial
        read_error = 'IncompleteRead'
    truncated = len(body) > wave.MAX_RESPONSE_BYTES
    body = body[:wave.MAX_RESPONSE_BYTES].replace(token.encode(), b'[REDACTED]')
    item = {'record_ids': request['record_ids'], 'attempt_id': attempt_id,
            'request_sha256': request['payload_sha256'], 'http_status': exc.code,
            'error_body': body.decode('utf-8', errors='replace'),
            'body_truncated_at_limit': truncated, 'read_error': read_error,
            'error_headers': {key: str(exc.headers[key]).replace(token, '[REDACTED]')
                              for key in ('x-request-id', 'request-id', 'retry-after', 'cf-ray')
                              if exc.headers is not None and exc.headers.get(key) is not None}}
    v3.durable(out, item)
    return item


def classify(plan, request, body, endpoint):
    if not isinstance(body, dict):
        return {'status': 'control_violation', 'predictions': {}}
    choice_list = body.get('choices')
    if not isinstance(choice_list, list) or len(choice_list) != 1 or not isinstance(choice_list[0], dict):
        return {'status': 'control_violation', 'predictions': {}}
    choice = choice_list[0]
    message = choice.get('message')
    if not isinstance(message, dict) or choice.get('error'):
        return {'status': 'control_violation', 'predictions': {}}
    usage = body.get('usage') or {}
    tools = usage.get('server_tool_use_details') if isinstance(usage, dict) else None
    if (message.get('tool_calls') or message.get('function_call') or message.get('refusal') or
            (isinstance(tools, dict) and any(tools.values()))):
        return {'status': 'control_violation', 'predictions': {}}
    if (body.get('model') not in allowed_returned_models(plan['model'], endpoint) or
            body.get('provider') != v3.PROVIDER_NAME):
        return {'status': 'identity_violation', 'predictions': {}}
    inputs = {x['id']: x for x in read_rows(ROOT / 'data/pilot/inputs.jsonl')}
    group = [inputs[rid] for rid in request['record_ids']]
    try:
        predictions = parse_batch(message.get('content'), group)
    except (ValueError, TypeError) as exc:
        return {'status': 'invalid_output', 'predictions': {}, 'parse_error': str(exc)}
    return {'status': 'ok' if choice.get('finish_reason') == 'stop' else 'invalid_output',
            'predictions': predictions, 'finish_reason': choice.get('finish_reason')}


def run(plan_path_value, plan_sha, review_path, condition, phase, env_file=None):
    plan = validate_plan(plan_path_value, plan_sha)
    require_order(plan, condition, phase)
    paths = phase_paths(plan['configuration_id'], plan['repeat'], condition, phase)
    if any(path.exists() for path in paths.values()):
        raise FileExistsError('Gemini repeat phase already claimed; no replay')
    budget_path = review_gate(plan, phase, condition, review_path, plan_sha)
    model, endpoint = live_controls(plan, condition)
    requests = plan['conditions'][condition]['requests'][:1 if phase == 'smoke' else 7]
    if phase == 'development':
        requests = requests[1:]
    ledger = open_partition(MASTER, budget_path, plan['partition_id'], plan['model'], v3.PROVIDER, 'low')
    try:
        if ledger.cap != Decimal(CAP):
            raise ValueError('Gemini child partition cap differs')
        _, pending, blocked = ledger.state()
        if pending or blocked:
            raise ValueError('Unresolved Gemini budget charge blocks calls')
        token = v3.load_key(env_file)
        if not isinstance(token, str) or not token.strip():
            raise ValueError('OpenRouter key unavailable')
        paths['claim'].parent.mkdir(parents=True, exist_ok=True)
        with paths['claim'].open('x') as out:
            v3.durable(out, {'schema': SCHEMA + '-claim', 'plan_sha256': plan_sha,
                             'review_sha256': digest(path_inside(review_path).read_bytes()),
                             'condition': condition, 'phase': phase, 'utc': wave.utc()})
        with paths['journal'].open('x') as journal, paths['attempts'].open('x') as attempts, \
                paths['responses'].open('x') as responses, paths['records'].open('x') as records:
            v3.durable(journal, {'event': 'phase_started', 'phase': phase, 'condition': condition,
                                 'expected_batches': len(requests), 'utc': wave.utc()})
            completed = True
            try:
                for index, request in enumerate(requests):
                    ids = request['record_ids']
                    v3.durable(journal, {'event': 'request_intent', 'record_ids': ids,
                                         'request_sha256': request['payload_sha256'], 'utc': wave.utc()})
                    attempt_id = ledger.reserve(Decimal(request['reserve_usd']), ','.join(ids))
                    v3.durable(journal, {'event': 'request_started', 'record_ids': ids,
                                         'attempt_id': attempt_id, 'request_sha256': request['payload_sha256'],
                                         'utc': wave.utc()})
                    row = {'attempt_id': attempt_id, 'phase': phase, 'condition': condition,
                           'repeat': plan['repeat'], 'batch_index': index if phase == 'smoke' else index + 1,
                           'ids': ids, 'request': request['payload'], 'request_sha256': request['payload_sha256'],
                           'reserved_cost_usd': request['reserve_usd'], 'model': plan['model'], 'effort': 'low',
                           'provider': v3.PROVIDER, 'requested_endpoint': endpoint,
                           'reference_labels_read': False, 'plan_sha256': plan_sha, 'started_utc': wave.utc()}
                    actual = None
                    try:
                        body = wave.fetch_recorded(request['payload'], token, plan['timeout_seconds'], responses,
                                                   ','.join(ids), attempt_id, request['payload_sha256'])
                        body = json.loads(json.dumps(body).replace(token, '[REDACTED]'))
                        row['raw_response'] = body
                        if isinstance(body, dict):
                            usage = body.get('usage') or {}
                            if isinstance(usage, dict) and usage.get('cost') is not None:
                                actual = v3.price(usage['cost'])
                        row.update(classify(plan, request, body, endpoint))
                    except Exception as exc:
                        row.update(status='service_error', error_type=type(exc).__name__, predictions={})
                        if isinstance(exc, urllib.error.HTTPError):
                            error = capture_http_error(exc, token, responses, request, attempt_id)
                            row.update({k: error[k] for k in ('http_status', 'error_body', 'read_error',
                                                               'body_truncated_at_limit', 'error_headers')})
                    billing_ok = ledger.settle(attempt_id, actual)
                    row.update(observed_cost_usd=str(actual) if actual is not None else None,
                               cost_unknown=actual is None, billing_ok=billing_ok)
                    v3.durable(attempts, row)
                    v3.durable(journal, {'event': 'request_finished', 'attempt_id': attempt_id,
                                         'status': row['status'], 'billing_ok': billing_ok,
                                         'cost_unknown': row['cost_unknown'], 'utc': wave.utc()})
                    for pos, rid in enumerate(ids):
                        v3.durable(records, {'id': rid, 'status': row['status'],
                                             'prediction': row.get('predictions', {}).get(rid),
                                             'phase': phase, 'batch_index': row['batch_index'],
                                             'batch_position': pos, 'attempt_id': attempt_id,
                                             'request_sha256': row['request_sha256'],
                                             'cost_amortization': 'Batch cost remains in attempt; no per-record charge'})
                    if not billing_ok or row['status'] not in ('ok', 'invalid_output'):
                        completed = False
                        v3.durable(journal, {'event': 'phase_stopped', 'attempt_id': attempt_id,
                                             'reason': row['status'], 'utc': wave.utc()})
                        break
                if completed:
                    v3.durable(journal, {'event': 'phase_completed', 'phase': phase,
                                         'batch_count': len(requests), 'utc': wave.utc()})
            finally:
                events = lines(paths['journal'])
                if events and events[-1].get('event') not in ('phase_completed', 'phase_stopped', 'phase_aborted'):
                    v3.durable(journal, {'event': 'phase_aborted', 'reason': 'exception_or_interruption',
                                         'utc': wave.utc()})
        return completed
    finally:
        ledger.close()


def inspect(plan_file, plan_sha, condition, review_path, note):
    if not isinstance(note, str) or not note.strip():
        raise ValueError('Inspection note required')
    plan = validate_plan(plan_file, plan_sha)
    budget_path = review_gate(plan, 'smoke', condition, review_path, plan_sha)
    paths = phase_paths(plan['configuration_id'], plan['repeat'], condition, 'smoke')
    claim = lines(paths['claim'])
    if len(claim) != 1 or claim[0].get('review_sha256') != digest(path_inside(review_path).read_bytes()):
        raise ValueError('Gemini smoke claim differs from reviewed admission')
    journal = lines(paths['journal'])
    attempts = lines(paths['attempts'])
    raw = lines(paths['responses'])
    records = lines(paths['records'])
    request = plan['conditions'][condition]['requests'][0]
    expected_ids = ['DEV-001', 'DEV-002', 'DEV-003']
    if (not journal or journal[-1].get('event') != 'phase_completed' or len(attempts) != 1 or len(raw) != 1 or
            [x.get('id') for x in records] != expected_ids or
            attempts[0].get('ids') != expected_ids or attempts[0].get('request') != request['payload'] or
            attempts[0].get('request_sha256') != request['payload_sha256'] or
            attempts[0].get('plan_sha256') != plan_sha or attempts[0].get('reference_labels_read') is not False or
            attempts[0].get('status') != 'ok' or attempts[0].get('billing_ok') is not True or
            attempts[0].get('cost_unknown') is not False or
            any(x.get('status') != 'ok' or x.get('request_sha256') != request['payload_sha256'] or
                x.get('attempt_id') != attempts[0].get('attempt_id') for x in records) or
            raw[0].get('id') != ','.join(expected_ids) or
            raw[0].get('attempt_id') != attempts[0].get('attempt_id') or
            raw[0].get('request_sha256') != attempts[0].get('request_sha256') or
            raw[0].get('body_truncated_at_limit') or raw[0].get('read_error') or not raw[0].get('body_base64')):
        raise ValueError('Gemini repeat smoke is not one intact admitted batch')
    try:
        captured = json.loads(base64.b64decode(raw[0]['body_base64'], validate=True))
    except (ValueError, binascii.Error):
        raise ValueError('Gemini smoke response bytes malformed') from None
    if captured != attempts[0].get('raw_response'):
        raise ValueError('Gemini smoke attempt differs from raw bytes')
    budget = json.loads(budget_path.read_text())
    partitions = [x for x in budget['partitions'] if x['id'] == plan['partition_id']]
    if len(partitions) != 1 or partitions[0]['cap_usd'] != CAP:
        raise ValueError('Gemini smoke child partition differs')
    ledger_events = lines(partitions[0]['child_ledger'])
    attempt_id = attempts[0]['attempt_id']
    reservations = [x for x in ledger_events if x.get('event') == 'reserve' and x.get('attempt_id') == attempt_id]
    settlements = [x for x in ledger_events if x.get('event') == 'settle' and x.get('attempt_id') == attempt_id]
    if (len(reservations) != 1 or len(settlements) != 1 or
            Decimal(reservations[0]['usd']) != Decimal(attempts[0]['reserved_cost_usd']) or
            Decimal(settlements[0]['usd']) != Decimal(attempts[0]['observed_cost_usd'])):
        raise ValueError('Gemini smoke budget settlement differs')
    receipt = {'schema': 'gemini-repeat-smoke-inspection-v1', 'decision': 'accepted_unchanged',
               'note': note, 'plan_sha256': plan_sha,
               **{key + '_sha256': digest(paths[key].read_bytes())
                  for key in ('journal', 'attempts', 'responses', 'records')}}
    path = paths_for(plan['configuration_id'], plan['repeat'], condition) / 'smoke-inspection.json'
    with path.open('x') as out:
        json.dump(receipt, out, indent=2)
        out.write('\n')
        out.flush()
        os.fsync(out.fileno())
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--config', required=True, choices=tuple(CONFIGS))
    v = sub.add_parser('validate')
    v.add_argument('--config', required=True, choices=tuple(CONFIGS))
    v.add_argument('--repeat', required=True, choices=tuple(ORDERS))
    v.add_argument('--sha256', required=True)
    for action in ('smoke', 'development', 'inspect'):
        p = sub.add_parser(action)
        p.add_argument('--config', required=True, choices=tuple(CONFIGS))
        p.add_argument('--repeat', required=True, choices=tuple(ORDERS))
        p.add_argument('--condition', required=True, choices=('P0', 'P1', 'P2'))
        p.add_argument('--sha256', required=True)
        if action in ('smoke', 'development'):
            p.add_argument('--review', required=True)
            p.add_argument('--env-file')
        else:
            p.add_argument('--review', required=True)
            p.add_argument('--note', required=True)
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare(args.config)
    elif args.action == 'validate':
        validate_plan(plan_path(args.config, args.repeat), args.sha256)
        print('validated')
    elif args.action == 'inspect':
        inspect(plan_path(args.config, args.repeat), args.sha256, args.condition, args.review, args.note)
        print('inspected')
    else:
        print('completed' if run(plan_path(args.config, args.repeat), args.sha256,
                                 args.review, args.condition, args.action, args.env_file) else 'stopped')


if __name__ == '__main__':
    main()
