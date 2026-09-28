#!/usr/bin/env python3
"""Explicit, reviewed episodes for the never-sent Qwen on/P2 suffix only.

Import, prepare, inspect and reconcile are offline. Execute is intentionally
unusable without an exact frozen manifest, root review and budget partition.
"""
import argparse
import base64
import hashlib
import http.client
import json
import math
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
from urllib.parse import quote
from decimal import Decimal
from types import SimpleNamespace

import openrouter_paid_benchmark as paid
import paid_budget_partitions_v2 as partitions
import prompt_admission as admission
import qwen36_prompt_recovery_v1 as recovery
import qwen36_on_p2_suffix_v4 as v4
from development_benchmark import valid
from openrouter_benchmark import OPENER, BASE, allowed_returned_models

ROOT = recovery.ROOT
DEST = ROOT / 'results/qwen36-on-p2-never-sent-episodes-v1'
CONTRACT = 'qwen36-on-p2-never-sent-episode-v1'
REVIEW_SCHEMA = 'qwen36-on-p2-episode-root-review-v1'
INITIAL_PLAN_SHA = '0ef230a63963b44b4cff416a3b9131cc8b7841c1e576cc1449f0af057db3e9af'
INITIAL_REPORT_SHA = '4e1a40864be05a4c0d596b975ae700e92462a81af4f9ad5b48e726e7b15456c0'
ALL_IDS = [f'DEV-{n:03}' for n in range(1, 61)]
FAILED = ['DEV-033', 'DEV-039', 'DEV-040', 'DEV-041', 'DEV-042']
REMAINING = ALL_IDS[42:]
RESERVE = recovery.RESERVE
MAX_RAW = 16 * 1024 * 1024
TIMEOUT = 300


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_at(relative):
    path = (ROOT / relative).resolve()
    path.relative_to(ROOT.resolve())
    return path


def bind(path):
    path = Path(path).resolve()
    path.relative_to(ROOT.resolve())
    return {'file': str(path.relative_to(ROOT)), 'sha256': sha(path.read_bytes())}


def read_bound(item):
    path = file_at(item['file'])
    raw = path.read_bytes()
    if sha(raw) != item['sha256']:
        raise ValueError('Bound source changed: ' + item['file'])
    return raw


def lines(raw):
    if raw and not raw.endswith(b'\n'):
        raise ValueError('Incomplete JSONL tail')
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def episode_dir(index):
    if type(index) is not int or index < 1:
        raise ValueError('Episode index must be positive')
    return DEST / f'episode-{index:03}'


def initial_state():
    """Reconstruct the exact 42-attempt prefix and all five held 429 charges."""
    if recovery.sha(v4.PLAN) != INITIAL_PLAN_SHA or recovery.sha(v4.RESULT / 'reconciliation.json') != INITIAL_REPORT_SHA:
        raise ValueError('Pinned v4 plan or reconciliation changed')
    plan = json.loads(v4.PLAN.read_text())
    report = json.loads((v4.RESULT / 'reconciliation.json').read_text())
    if (plan.get('contract') != v4.CONTRACT or plan.get('record_ids') != [f'DEV-{n:03}' for n in range(42, 61)] or
            plan.get('excluded_failed_ids') != FAILED[:-1] or
            report.get('failed_ids') != FAILED or report.get('never_sent_ids') != REMAINING or
            report.get('attempted') != 42 or report.get('valid_outputs') != 37 or
            report.get('status_counts') != {'ok': 37, 'service_error': 5} or
            report.get('retry_performed') is not False or report.get('eligible_paired_comparison') is not False):
        raise ValueError('V4 predecessor coverage changed')
    if (recovery.source(plan['frozen_execution']) != recovery.FROZEN or
            recovery.source(plan['route_audit']) != recovery.ROUTE or
            report.get('sources', {}).get('prior_report') != plan['sources']['v3_report']):
        raise ValueError('V4 frozen source or predecessor report differs')
    v4.prior_state(plan['sources'])
    source_paths = [recovery.source(item) for item in plan['sources'].values()]
    histories = [(v4.ORIGINAL, v4.ORIGINAL_JOURNAL), (v4.V1, v4.V1_JOURNAL),
                 (v4.previous.V2, v4.previous.V2_JOURNAL), (v4.V3, v4.V3_JOURNAL),
                 (v4.OUTPUT, Path(str(v4.OUTPUT) + '.attempts.jsonl'))]
    if (report.get('sources', {}).get('suffix_v4', {}).get('sha256') != recovery.sha(v4.OUTPUT) or
            report.get('sources', {}).get('suffix_v4_journal', {}).get('sha256') != recovery.sha(histories[-1][1])):
        raise ValueError('V4 reconciliation does not bind its saved attempt')
    frozen = json.loads(recovery.FROZEN.read_text())
    config, _, evidence, _, _, _, _ = admission._checked(frozen, ROOT, v4.CID, 'P2')
    if config['controls']['effort'] != 'on':
        raise ValueError('Frozen Qwen effort changed')
    requests = evidence['requests'][3:]
    if len(requests) != 60 or [x['record_ids'] for x in requests] != [[rid] for rid in ALL_IDS]:
        raise ValueError('Frozen P2 request order changed')
    attempts = []
    attempt_sources = {}
    ledgers = []
    ledger_cache = {}
    for output, journal in histories:
        saved = lines(output.read_bytes())
        events = lines(journal.read_bytes())
        starts = [x for x in events if x.get('event') in ('started', 'request_started')]
        finishes = [x for x in events if x.get('event') in ('finished', 'request_finished') and x.get('id')]
        if ([(x.get('id'), x.get('attempt_id')) for x in saved] !=
                [(x.get('id'), x.get('attempt_id')) for x in starts] or
                [(x.get('id'), x.get('attempt_id')) for x in saved] !=
                [(x.get('id'), x.get('attempt_id')) for x in finishes]):
            raise ValueError('Historical raw/journal attempts disagree')
        attempts.extend(saved)
        attempt_sources.update((row['attempt_id'], output) for row in saved)
        source_paths.extend((output, journal))
    if len(attempts) != 42 or [x.get('id') for x in attempts] != ALL_IDS[:42]:
        raise ValueError('Historical prefix is not 42 unique attempts')
    for index, row in enumerate(attempts):
        envelope = json.loads(recovery.source(requests[index]['client_request']).read_text())
        if (row.get('request') != envelope['request'] or row.get('reference_labels_read') is not False or
                row.get('requested_model') != recovery.MODEL or row.get('reasoning_effort') != 'on' or
                row.get('request_sha256') != paid.digest(json.dumps(row['request'], sort_keys=True))):
            raise ValueError('Historical request or isolation changed: ' + row.get('id', '?'))
        ledger_path = file_at(row['budget_ledger'])
        if ledger_path not in ledger_cache:
            ledger_cache[ledger_path] = lines(ledger_path.read_bytes())
        ledger = ledger_cache[ledger_path]
        matching = [x for x in ledger if x.get('attempt_id') == row['attempt_id']]
        ledgers.append(ledger_path)
        if row['id'] in FAILED:
            if (row.get('status') != 'service_error' or row.get('http_status') != 429 or
                    row.get('cost_unknown') is not True or row.get('observed_cost_usd') is not None or
                    paid.number(row.get('reserved_cost_usd')) != RESERVE):
                raise ValueError('Historical 429 outcome changed: ' + row['id'])
            if ([x['event'] for x in matching] != ['reserve', 'unknown_cost_accounted_as_upper_bound'] or
                    matching[0].get('record_id') != row['id'] or
                    any(paid.number(x['usd']) != RESERVE for x in matching) or
                    matching[1].get('actual_cost_usd') is not None or
                    Path(matching[1].get('evidence_path', '')).resolve() != attempt_sources[row['attempt_id']].resolve() or
                    matching[1].get('evidence_sha256') != recovery.sha(attempt_sources[row['attempt_id']]) or
                    ledger[-1].get('event') != 'partition_closed'):
                raise ValueError('Historical unknown charge is not held at bound: ' + row['id'])
        elif (row.get('status') != 'ok' or row.get('cost_unknown') is not False or
              row.get('billing_ok') is not True or
              [x['event'] for x in matching] != ['reserve', 'settle'] or
              matching[0].get('record_id') != row['id'] or
              paid.number(matching[0]['usd']) != RESERVE or
              paid.number(row.get('reserved_cost_usd')) != RESERVE or
              paid.number(matching[1]['usd']) != paid.number(row.get('observed_cost_usd'))):
            raise ValueError('Historical known settlement or output changed: ' + row['id'])
    source_paths.extend((v4.PLAN, v4.RESULT / 'reconciliation.json', recovery.FROZEN, recovery.ROUTE, *ledgers))
    unique = list(dict.fromkeys(Path(x).resolve() for x in source_paths))
    return {'attempted_ids': ALL_IDS[:42], 'failed_ids': FAILED,
            'source_bindings': [bind(path) for path in unique],
            'previous_reconciliation': None, 'requests': requests}


def predecessor(index):
    initial = initial_state()
    if index == 1:
        return initial
    for number in range(1, index):
        report_path = episode_dir(number) / 'reconciliation.json'
        if not report_path.is_file():
            raise ValueError('Previous episode has no explicit reconciliation')
        report = json.loads(report_path.read_text())
        if (report.get('schema') != CONTRACT + '-reconciliation' or
                report.get('episode_index') != number or
                report.get('previous_attempted_ids') != initial['attempted_ids'] or
                report.get('failed_ids')[:5] != FAILED):
            raise ValueError('Previous episode reconciliation differs')
        validate_reconciliation(number, report)
        initial['attempted_ids'] = report['attempted_ids']
        initial['failed_ids'] = report['failed_ids']
        initial['previous_reconciliation'] = bind(report_path)
    return initial


def expected_manifest(index):
    state = predecessor(index)
    attempted = state['attempted_ids']
    if attempted != ALL_IDS[:len(attempted)] or len(attempted) >= 60:
        raise ValueError('No never-sent suffix remains')
    ids = ALL_IDS[len(attempted):]
    return {'contract': CONTRACT, 'status': 'FROZEN', 'episode_index': index,
            'configuration_id': v4.CID, 'condition': 'P2', 'reasoning': 'on',
            'model': recovery.MODEL, 'provider': recovery.PROVIDER,
            'reference_labels_read': False, 'retry_policy': 'never retry attempted IDs',
            'original_timing_preserved': False, 'controller': bind(__file__),
            'initial_sources': state['source_bindings'],
            'previous_reconciliation': state['previous_reconciliation'],
            'previous_attempted_ids': attempted, 'failed_ids': state['failed_ids'],
            'request_ids': ids,
            'requests': [x['client_request'] for x in state['requests'][len(attempted):]],
            'per_call_reserve_usd': str(RESERVE),
            'call_bound_usd': str(RESERVE * len(ids)),
            'request_timeout_seconds': TIMEOUT,
            'output_directory': str(episode_dir(index).relative_to(ROOT))}


def validate_manifest(path, expected_sha=None):
    path = Path(path).resolve()
    path.relative_to(DEST.resolve())
    raw = path.read_bytes()
    if expected_sha is not None and sha(raw) != expected_sha:
        raise ValueError('Episode manifest SHA differs')
    saved = json.loads(raw)
    if path != episode_dir(saved['episode_index']) / 'manifest.json':
        raise ValueError('Episode manifest path differs')
    if saved != expected_manifest(saved['episode_index']):
        raise ValueError('Episode manifest differs from frozen never-sent state')
    return saved


def prepare(index):
    manifest = expected_manifest(index)
    folder = episode_dir(index)
    folder.mkdir(parents=True, exist_ok=False)
    path = folder / 'manifest.json'
    with path.open('x') as out:
        out.write(json.dumps(manifest, indent=2) + '\n')
        out.flush(); os.fsync(out.fileno())
    return path, sha(path.read_bytes())


def paths(index):
    folder = episode_dir(index)
    return {key: folder / name for key, name in (
        ('claim', 'claim.json'), ('journal', 'journal.jsonl'),
        ('responses', 'responses.jsonl'), ('attempts', 'attempts.jsonl'))}


def review_gate(manifest, manifest_sha, review_path, budget_path, partition_id):
    budget_path = Path(budget_path).resolve()
    budget_path.relative_to(ROOT.resolve())
    review_path = Path(review_path).resolve()
    if review_path != episode_dir(manifest['episode_index']).resolve() / 'root-review.json':
        raise ValueError('Episode review must be the immutable root-review.json')
    review = json.loads(Path(review_path).read_text())
    if (review.get('schema') != REVIEW_SCHEMA or review.get('approved') is not True or
            review.get('manifest_sha256') != manifest_sha or
            review.get('controller_sha256') != manifest['controller']['sha256'] or
            review.get('budget_manifest_sha256') != recovery.sha(budget_path) or
            review.get('partition_id') != partition_id or
            review.get('request_ids') != manifest['request_ids'] or
            review.get('failed_ids_retained') != manifest['failed_ids'] or
            not isinstance(review.get('cooldown_note'), str) or not review['cooldown_note'].strip()):
        raise ValueError('Exact episode root review missing or changed')
    budget = json.loads(Path(budget_path).read_text())
    if (budget.get('version') != 'paid-partitions-v1' or
            Path(budget.get('master_ledger', '')).resolve() != (ROOT / 'results/openrouter-paid-budget.jsonl').resolve()):
        raise ValueError('Budget manifest differs from approved master')
    matches = [x for x in budget['partitions'] if x.get('id') == partition_id]
    if len(matches) != 1:
        raise ValueError('Missing unique episode partition')
    entry = matches[0]
    if ((entry['model'], entry['provider'], entry['reasoning']) != (recovery.MODEL, recovery.PROVIDER, 'on') or
            paid.number(entry['cap_usd']) < paid.number(manifest['call_bound_usd']) or
            paid.number(entry['cap_usd']) > Decimal('0.60')):
        raise ValueError('Episode partition route or bound changed')
    file_at(Path(entry['child_ledger']).relative_to(ROOT))
    return review, entry


def live_controls(manifest):
    """Unauthenticated public preflight; exact payloads checked before key load."""
    catalog = paid.fetch('/models', timeout=TIMEOUT)
    endpoints = paid.fetch('/models/' + quote(recovery.MODEL, safe='/') + '/endpoints', timeout=TIMEOUT)
    model, endpoint = recovery.live_endpoint(catalog, endpoints, recovery.endpoint_from_audit(recovery.ROUTE))
    if paid.reservation(endpoint, 4096, Decimal('0.1'), Decimal('0.9')) != RESERVE:
        raise ValueError('Live reservation or price differs')
    frozen = json.loads(recovery.FROZEN.read_text())
    config, _, _, inputs, schema, instruction, _ = admission._checked(frozen, ROOT, v4.CID, 'P2')
    controls = config['controls']['adapter_controls']
    for rid, item in zip(manifest['request_ids'], manifest['requests']):
        request = json.loads(recovery.source(item).read_text())
        expected = paid.make_payload(recovery.MODEL, endpoint, inputs[int(rid[-3:]) - 1]['feedback'],
                                     instruction, schema, 'on', 4096, Decimal('0.1'), Decimal('0.9'), model)
        if (request != {'request': expected, 'adapter_controls': controls} or
                paid.paid_adapter_controls(SimpleNamespace(model=recovery.MODEL, reasoning='on'), endpoint, expected) != controls):
            raise ValueError('Live request differs from frozen exact payload')
    return model, endpoint


def capture(response, token, rid, attempt, request_sha, output, http_status=None):
    read_error = None
    try:
        raw = response.read(MAX_RAW + 1)
    except http.client.IncompleteRead as exc:
        raw = exc.partial
        read_error = 'IncompleteRead'
    truncated = len(raw) > MAX_RAW
    data = raw[:MAX_RAW].replace(token.encode(), b'[REDACTED]')
    declared = getattr(response, 'headers', None)
    length = declared.get('Content-Length') if declared is not None else None
    if length is not None and read_error is None and not truncated:
        try:
            if int(length) != len(raw):
                read_error = 'ContentLengthMismatch'
        except ValueError:
            read_error = 'InvalidContentLength'
    sidecar = {'id': rid, 'attempt_id': attempt, 'request_sha256': request_sha,
               'http_status': http_status, 'body_base64': base64.b64encode(data).decode(),
               'body_truncated_at_limit': truncated, 'read_error': read_error,
               'credential_redacted': token.encode() in raw[:MAX_RAW]}
    paid.durable(output, sidecar)
    return sidecar


def execute(manifest_path, manifest_sha, review_path, budget_path, partition_id, env_file=None):
    manifest = validate_manifest(manifest_path, manifest_sha)
    review_gate(manifest, manifest_sha, review_path, budget_path, partition_id)
    files = paths(manifest['episode_index'])
    if any(path.exists() for path in files.values()):
        raise FileExistsError('Episode already claimed; no replay')
    model, endpoint = live_controls(manifest)
    ledger = partitions.open_partition(ROOT / 'results/openrouter-paid-budget.jsonl', budget_path,
                                       partition_id, recovery.MODEL, recovery.PROVIDER, 'on')
    try:
        _, pending, blocked = ledger.state()
        if pending or blocked or ledger.accounted() or ledger.closed:
            raise ValueError('Episode child ledger is not fresh and idle')
        token = paid.load_key(env_file)
        with files['claim'].open('x') as out:
            paid.durable(out, {'schema': CONTRACT + '-claim', 'manifest_sha256': manifest_sha,
                               'review_sha256': recovery.sha(review_path),
                               'budget_manifest_sha256': recovery.sha(budget_path),
                               'partition_id': partition_id, 'request_ids': manifest['request_ids']})
        with files['journal'].open('x') as journal, files['responses'].open('x') as responses, files['attempts'].open('x') as attempts:
            paid.durable(journal, {'event': 'episode_started', 'manifest_sha256': manifest_sha})
            for rid, item in zip(manifest['request_ids'], manifest['requests']):
                request = json.loads(recovery.source(item).read_text())['request']
                request_sha = paid.digest(json.dumps(request, sort_keys=True))
                attempt = ledger.reserve(RESERVE, rid)
                paid.durable(journal, {'event': 'request_started', 'id': rid, 'attempt_id': attempt,
                                       'request_sha256': request_sha, 'reserved_cost_usd': str(RESERVE)})
                record = {'id': rid, 'attempt_id': attempt, 'request': request,
                          'request_sha256': request_sha, 'manifest_sha256': manifest_sha,
                          'reference_labels_read': False, 'requested_model': recovery.MODEL,
                          'reasoning_effort': 'on', 'provider_endpoint': endpoint,
                          'model_catalog_entry': model, 'reserved_cost_usd': str(RESERVE),
                          'request_timeout_seconds': TIMEOUT, 'budget_partition_id': partition_id}
                actual = None
                started = time.perf_counter()
                try:
                    req = urllib.request.Request(BASE + '/chat/completions',
                        headers={'Content-Type': 'application/json', 'Authorization': 'Bearer ' + token},
                        data=json.dumps(request).encode())
                    try:
                        with OPENER.open(req, timeout=TIMEOUT) as response:
                            saved = capture(response, token, rid, attempt, request_sha, responses)
                    except urllib.error.HTTPError as exc:
                        saved = capture(exc, token, rid, attempt, request_sha, responses, exc.code)
                    if saved['body_truncated_at_limit'] or saved['read_error']:
                        record.update(status='service_error', error_type='truncated_or_incomplete_response')
                    elif saved['http_status'] is not None:
                        record.update(status='service_error', http_status=saved['http_status'])
                    else:
                        body = json.loads(base64.b64decode(saved['body_base64']))
                        record['raw_response'] = body
                        if not isinstance(body, dict):
                            record['status'] = 'control_violation'
                        else:
                            usage = body.get('usage') or {}
                            record['usage'] = usage
                            if isinstance(usage, dict) and usage.get('cost') is not None:
                                actual = paid.number(usage['cost'])
                            choices = body.get('choices') or []
                            choice = choices[0] if len(choices) == 1 else {}
                            message = choice.get('message') or {}
                            try:
                                prediction = json.loads(message.get('content'))
                            except (ValueError, TypeError):
                                prediction = None
                            record['prediction'] = prediction
                            record['status'] = 'ok' if valid(prediction) and choice.get('finish_reason') == 'stop' else 'invalid_output'
                            if (body.get('error') or len(choices) != 1 or choice.get('error') or
                                    message.get('tool_calls') or message.get('function_call') or message.get('refusal')):
                                record['status'] = 'control_violation'
                            if body.get('model') not in allowed_returned_models(recovery.MODEL, endpoint) or body.get('provider') != recovery.NAME:
                                record['status'] = 'identity_violation'
                            record['returned_model'] = body.get('model')
                            record['returned_provider'] = body.get('provider')
                except Exception as exc:
                    record.update(status='service_error', error_type=type(exc).__name__)
                if actual is not None:
                    billing_ok = ledger.settle(attempt, actual)
                else:
                    billing_ok = False
                record.update(observed_cost_usd=str(actual) if actual is not None else None,
                              cost_unknown=actual is None, billing_ok=billing_ok,
                              elapsed_seconds=time.perf_counter() - started,
                              timing_kind='client_request_elapsed')
                if isinstance(record.get('raw_response'), dict):
                    diagnostic = admission.audit_response(record, 'openrouter_paid_v1', 262144 - 4096)
                    record['prompt_response_diagnostics'] = diagnostic
                    if record['status'] == 'ok' and not diagnostic['passed']:
                        record['status'] = 'control_violation'
                paid.durable(attempts, record)
                paid.durable(journal, {'event': 'request_finished', 'id': rid, 'attempt_id': attempt,
                                       'status': record['status'], 'billing_ok': billing_ok,
                                       'cost_unknown': actual is None})
                if record['status'] != 'ok' or not billing_ok or actual is None:
                    paid.durable(journal, {'event': 'episode_stopped', 'id': rid, 'reason': record['status']})
                    break
            else:
                paid.durable(journal, {'event': 'episode_completed', 'request_count': len(manifest['request_ids'])})
    finally:
        ledger.close()


def validate_reconciliation(index, report):
    """Verify every started request has one saved raw receipt and a closed charge."""
    manifest_path = episode_dir(index) / 'manifest.json'
    manifest = validate_manifest(manifest_path)
    files = paths(index)
    claim = json.loads(read_bound(report['evidence']['claim']))
    review = json.loads(read_bound(report['evidence']['review']))
    journal = lines(read_bound(report['evidence']['journal']))
    responses = lines(read_bound(report['evidence']['responses']))
    attempts = lines(read_bound(report['evidence']['attempts']))
    if (claim.get('manifest_sha256') != recovery.sha(manifest_path) or
            claim.get('review_sha256') != report['evidence']['review']['sha256'] or
            review.get('schema') != REVIEW_SCHEMA or review.get('approved') is not True or
            review.get('manifest_sha256') != recovery.sha(manifest_path) or
            review.get('controller_sha256') != manifest['controller']['sha256'] or
            review.get('budget_manifest_sha256') != report['budget_manifest']['sha256'] or
            claim.get('budget_manifest_sha256') != report['budget_manifest']['sha256'] or
            claim.get('partition_id') != review.get('partition_id') or
            review.get('request_ids') != manifest['request_ids'] or
            review.get('failed_ids_retained') != manifest['failed_ids'] or
            journal[0].get('event') != 'episode_started' or
            journal[-1].get('event') not in ('episode_stopped', 'episode_completed')):
        raise ValueError('Episode claim or terminal journal differs')
    starts = [e for e in journal if e.get('event') == 'request_started']
    finishes = [e for e in journal if e.get('event') == 'request_finished']
    if not starts or not len(starts) == len(finishes) == len(responses) == len(attempts):
        raise ValueError('Started request has no unique raw/attempt/finish; delivery ambiguous')
    if [x.get('id') for x in starts] != manifest['request_ids'][:len(starts)]:
        raise ValueError('Episode attempted IDs are not the exact never-sent prefix')
    if journal[-1]['event'] == 'episode_completed':
        if (len(attempts) != len(manifest['request_ids']) or
                any(x.get('status') != 'ok' or x.get('cost_unknown') is not False or
                    x.get('billing_ok') is not True for x in attempts)):
            raise ValueError('Completed episode is not all requested valid attempts')
    elif (journal[-1].get('id') != attempts[-1].get('id') or
          journal[-1].get('reason') != attempts[-1].get('status') or
          (attempts[-1].get('status') == 'ok' and attempts[-1].get('cost_unknown') is not True and
           attempts[-1].get('billing_ok') is not False)):
        raise ValueError('Stopped episode does not identify its terminal failure')
    budget = json.loads(read_bound(report['budget_manifest']))
    entry = next(x for x in budget['partitions'] if x['id'] == claim['partition_id'])
    ledger = lines(read_bound(report['child_ledger']))
    if Path(entry['child_ledger']).resolve() != file_at(report['child_ledger']['file']) or ledger[-1].get('event') != 'partition_closed':
        raise ValueError('Episode child budget is not closed')
    master = lines((ROOT / 'results/openrouter-paid-budget.jsonl').read_bytes())
    reconciliation = [e for e in master if e.get('event') == 'partition_reconciled' and
                      e.get('partition_id') == claim['partition_id']]
    if (len(reconciliation) != 1 or reconciliation[0] != report.get('master_reconciliation_event') or
            reconciliation[0].get('child_sha256') != report['child_ledger']['sha256']):
        raise ValueError('Episode master budget reconciliation differs')
    known = sum((paid.number(x['usd']) for x in ledger if x.get('event') == 'settle'), Decimal(0))
    unknown = sum((paid.number(x['usd']) for x in ledger if x.get('event') == 'unknown_cost_accounted_as_upper_bound'), Decimal(0))
    if (paid.number(reconciliation[0]['known_actual_usd']) != known or
            paid.number(reconciliation[0]['unknown_upper_bound_usd']) != unknown):
        raise ValueError('Master and child settled amounts differ')
    if [(x.get('attempt_id'), x.get('record_id')) for x in ledger if x.get('event') == 'reserve'] != [
            (x.get('attempt_id'), x.get('id')) for x in starts]:
        raise ValueError('Episode budget contains an unattributed reservation')
    for planned, start, finish, sidecar, attempt in zip(manifest['requests'], starts, finishes, responses, attempts):
        ident = (start['id'], start['attempt_id'], start['request_sha256'])
        frozen_request = json.loads(recovery.source(planned).read_text())['request']
        if (ident != (sidecar.get('id'), sidecar.get('attempt_id'), sidecar.get('request_sha256')) or
                ident[:2] != (finish.get('id'), finish.get('attempt_id')) or
                ident[:2] != (attempt.get('id'), attempt.get('attempt_id')) or
                attempt.get('request_sha256') != ident[2] or
                attempt.get('request') != frozen_request or
                ident[2] != paid.digest(json.dumps(frozen_request, sort_keys=True)) or
                attempt.get('requested_model') != recovery.MODEL or
                attempt.get('reasoning_effort') != 'on' or
                attempt.get('request_timeout_seconds') != TIMEOUT or
                attempt.get('budget_partition_id') != claim['partition_id'] or
                attempt.get('manifest_sha256') != recovery.sha(manifest_path) or
                attempt.get('reference_labels_read') is not False or
                attempt.get('timing_kind') != 'client_request_elapsed' or
                type(attempt.get('elapsed_seconds')) not in (int, float) or
                not math.isfinite(attempt['elapsed_seconds']) or attempt['elapsed_seconds'] < 0 or
                finish.get('status') != attempt.get('status') or
                finish.get('cost_unknown') != attempt.get('cost_unknown') or
                finish.get('billing_ok') != attempt.get('billing_ok')):
            raise ValueError('Started/raw/attempt identity differs')
        try:
            raw = base64.b64decode(sidecar['body_base64'], validate=True)
        except (KeyError, ValueError):
            raise ValueError('Raw response evidence malformed') from None
        if b'[REDACTED]' in raw and sidecar.get('credential_redacted') is not True:
            raise ValueError('Raw response redaction evidence differs')
        if not sidecar.get('http_status') and not sidecar.get('body_truncated_at_limit') and not sidecar.get('read_error'):
            try:
                body = json.loads(raw)
            except (UnicodeError, ValueError):
                if (attempt.get('status') != 'service_error' or
                        attempt.get('error_type') not in ('JSONDecodeError', 'UnicodeDecodeError') or
                        attempt.get('cost_unknown') is not True or 'raw_response' in attempt):
                    raise ValueError('Malformed raw response is not retained as a service error') from None
                body = None
            if body is not None and body != attempt.get('raw_response'):
                raise ValueError('Parsed attempt differs from durable raw response')
            if isinstance(body, dict):
                usage = body.get('usage') or {}
                raw_cost = usage.get('cost') if isinstance(usage, dict) else None
                if raw_cost is None:
                    if attempt.get('cost_unknown') is not True:
                        raise ValueError('Attempt charge differs from durable raw usage')
                else:
                    try:
                        parsed_cost = paid.number(raw_cost)
                    except ValueError:
                        if (attempt.get('status') != 'service_error' or attempt.get('error_type') != 'ValueError' or
                                attempt.get('cost_unknown') is not True):
                            raise ValueError('Invalid raw charge was not held as unknown') from None
                    else:
                        if attempt.get('cost_unknown') is not False or parsed_cost != paid.number(attempt.get('observed_cost_usd')):
                            raise ValueError('Attempt charge differs from durable raw usage')
            if isinstance(body, dict) and attempt.get('status') == 'ok':
                choices = body.get('choices') or []
                if (len(choices) != 1 or choices[0].get('finish_reason') != 'stop' or
                        body.get('provider') != recovery.NAME or
                        body.get('model') not in allowed_returned_models(recovery.MODEL, attempt['provider_endpoint'])):
                    raise ValueError('Accepted attempt has no normal raw finish')
                prediction = json.loads((choices[0].get('message') or {}).get('content'))
                if not valid(prediction) or prediction != attempt.get('prediction'):
                    raise ValueError('Accepted prediction differs from durable raw response')
        billing = [x for x in ledger if x.get('attempt_id') == ident[1]]
        if not billing or billing[0].get('event') != 'reserve' or billing[0].get('record_id') != ident[0] or paid.number(billing[0]['usd']) != RESERVE:
            raise ValueError('Episode reservation differs')
        if attempt.get('cost_unknown'):
            if len(billing) != 2 or billing[1].get('event') != 'unknown_cost_accounted_as_upper_bound' or paid.number(billing[1]['usd']) != RESERVE:
                raise ValueError('Unknown cost lacks explicit full-bound accounting')
        elif len(billing) != 2 or billing[1].get('event') != 'settle' or paid.number(billing[1]['usd']) != paid.number(attempt.get('observed_cost_usd')):
            raise ValueError('Episode settled charge differs')
    expected_attempted = manifest['previous_attempted_ids'] + [x['id'] for x in attempts]
    expected_failed = manifest['failed_ids'] + [x['id'] for x in attempts if x['status'] != 'ok']
    if (report.get('previous_attempted_ids') != manifest['previous_attempted_ids'] or
            report.get('attempted_ids') != expected_attempted or report.get('failed_ids') != expected_failed or
            report.get('remaining_never_sent_ids') != ALL_IDS[len(expected_attempted):] or
            report.get('manifest_sha256') != recovery.sha(manifest_path)):
        raise ValueError('Episode reconciliation counts differ')
    return report


def reconcile(index, budget_path):
    manifest_path = episode_dir(index) / 'manifest.json'
    manifest = validate_manifest(manifest_path)
    files = paths(index)
    claim = json.loads(files['claim'].read_text())
    budget_path = Path(budget_path).resolve()
    budget_path.relative_to(ROOT)
    budget = json.loads(budget_path.read_text())
    entry = next(x for x in budget['partitions'] if x['id'] == claim['partition_id'])
    child = Path(entry['child_ledger']).resolve()
    child.relative_to(ROOT)
    child_sha = recovery.sha(child)
    master_events = lines((ROOT / 'results/openrouter-paid-budget.jsonl').read_bytes())
    matches = [e for e in master_events if e.get('event') == 'partition_reconciled' and
               e.get('partition_id') == claim['partition_id']]
    if len(matches) != 1 or matches[0].get('child_sha256') != child_sha:
        raise ValueError('Episode partition must be explicitly reconciled to master')
    events = lines(files['journal'].read_bytes())
    if not events or events[-1].get('event') not in ('episode_stopped', 'episode_completed'):
        raise ValueError('Episode has no terminal journal; delivery remains ambiguous')
    attempts = lines(files['attempts'].read_bytes())
    report = {'schema': CONTRACT + '-reconciliation', 'episode_index': index,
              'manifest_sha256': recovery.sha(manifest_path),
              'previous_attempted_ids': manifest['previous_attempted_ids'],
              'attempted_ids': manifest['previous_attempted_ids'] + [x['id'] for x in attempts],
              'failed_ids': manifest['failed_ids'] + [x['id'] for x in attempts if x['status'] != 'ok'],
              'remaining_never_sent_ids': ALL_IDS[len(manifest['previous_attempted_ids']) + len(attempts):],
              'evidence': {**{key: bind(path) for key, path in files.items()},
                           'review': bind(episode_dir(index) / 'root-review.json')},
              'budget_manifest': bind(budget_path), 'child_ledger': bind(child),
              'master_reconciliation_event': matches[0]}
    validate_reconciliation(index, report)
    destination = episode_dir(index) / 'reconciliation.json'
    with destination.open('x') as out:
        out.write(json.dumps(report, indent=2) + '\n'); out.flush(); os.fsync(out.fileno())
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    p = actions.add_parser('prepare'); p.add_argument('--episode', type=int, required=True)
    p = actions.add_parser('validate'); p.add_argument('--manifest', required=True); p.add_argument('--sha256', required=True)
    p = actions.add_parser('execute'); p.add_argument('--manifest', required=True); p.add_argument('--sha256', required=True)
    p.add_argument('--review', required=True); p.add_argument('--budget-manifest', required=True)
    p.add_argument('--partition-id', required=True); p.add_argument('--env-file')
    p = actions.add_parser('reconcile'); p.add_argument('--episode', type=int, required=True); p.add_argument('--budget-manifest', required=True)
    args = parser.parse_args()
    if args.action == 'prepare':
        path, digest = prepare(args.episode); print(path, digest)
    elif args.action == 'validate':
        print(json.dumps({'request_ids': validate_manifest(args.manifest, args.sha256)['request_ids']}))
    elif args.action == 'execute':
        execute(args.manifest, args.sha256, args.review, args.budget_manifest, args.partition_id, args.env_file)
    else:
        print(reconcile(args.episode, args.budget_manifest))


if __name__ == '__main__':
    main()
