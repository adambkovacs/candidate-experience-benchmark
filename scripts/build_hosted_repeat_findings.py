#!/usr/bin/env python3
"""Build an offline, source-bound Gemma 26 repeat report.

This reads saved evidence only. It never opens a budget ledger or makes a model call.
"""
import argparse
from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
from pathlib import Path

import build_repeat_findings as shared
import openrouter_repeat_study as study
from development_benchmark import digest, valid
from openrouter_benchmark import allowed_returned_models


ROOT = Path(__file__).resolve().parents[1]
CONFIG = study.CONFIG
BASE = Path('results/repeatability-v1') / CONFIG
PAIR = Path(study.PAIR)
LABELS = Path('data/pilot/proposed_labels.jsonl')
REVIEW = BASE / 'root-review-v1.json'
CONTROLLER = Path('scripts/openrouter_repeat_execution.py')
HOSTED_POLICY = Path('results/prompt-comparison-v1-2026-09-24/hosted-execution.json')
PASSES = ('original', 'repeat2', 'repeat3')
CONDITIONS = ('P0', 'P1', 'P2')
FIELDS = shared.FIELDS
LABEL_SHA = shared.PINNED_SHA[str(LABELS)]


def _file(root, relative):
    path = (root / relative).resolve()
    path.relative_to(root.resolve())
    return path


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _binding(root, relative, expected=None):
    path = _file(root, relative)
    actual = _sha(path)
    if expected is not None and actual != expected:
        raise ValueError(f'Source hash changed: {relative}')
    return {'path': str(relative), 'sha256': actual}


def _rows(root, relative):
    lines = _file(root, relative).read_text().splitlines()
    if any(not line.strip() for line in lines):
        raise ValueError(f'Blank evidence row: {relative}')
    return [json.loads(line) for line in lines]


def _money(value):
    if isinstance(value, bool) or value is None:
        raise ValueError('Missing or invalid observed cost')
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError('Invalid observed cost') from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError('Invalid observed cost')
    return amount


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError(f'Invalid {name}')
    return value


def _source_context(root):
    sources = []
    def bind(relative, expected=None):
        item = _binding(root, relative, expected)
        if item not in sources:
            sources.append(item)
        return item

    bind(LABELS, LABEL_SHA)
    labels_rows = _rows(root, LABELS)
    ids = [row['id'] for row in labels_rows]
    if ids != [f'DEV-{i:03}' for i in range(1, 61)] or any(row.get('review_version') != '0.2' for row in labels_rows):
        raise ValueError('Expected 60 ordered provisional v0.2 references')
    labels = {row['id']: row['proposed_labels'] for row in labels_rows}
    bind(PAIR)
    pair = json.loads(_file(root, PAIR).read_text())
    if pair.get('parent_baseline_id') != CONFIG or pair.get('controls', {}).get('requested_model') != study.MODEL:
        raise ValueError('Historical paired configuration mismatch')
    controls = pair['controls']
    if (controls.get('provider_tag'), controls.get('provider_name'), controls.get('quantization'),
            controls.get('reasoning_effort'), controls.get('workflow')) != (
            study.PROVIDER, 'DeepInfra', 'fp8', study.EFFORT, 'single_record'):
        raise ValueError('Historical route controls mismatch')

    bind(REVIEW)
    review = json.loads(_file(root, REVIEW).read_text())
    if (review.get('schema'), review.get('approved'), review.get('configuration_id'),
            review.get('partition_cap_usd')) != (
            'openrouter-repeat-root-review-v1', True, CONFIG, study.CAP_USD):
        raise ValueError('Root review binding mismatch')
    if review.get('review_verdict') != 'APPROVE':
        raise ValueError('Root review did not approve this controller')
    if not isinstance(review.get('master_ledger'), str) or not Path(review['master_ledger']).is_absolute():
        raise ValueError('Reviewed historical shared budget ledger path is invalid')
    bind(CONTROLLER, review['controller_sha256'])
    bind(HOSTED_POLICY, review['hosted_execution_sha256'])
    budget_spec = review['budget_manifest']
    bind(Path(budget_spec['path']), budget_spec['sha256'])
    budget = json.loads(_file(root, Path(budget_spec['path'])).read_text())
    if budget.get('master_ledger') != review['master_ledger']:
        raise ValueError('Partition manifest names a different shared ledger')
    partitions = [p for p in budget['partitions'] if p['id'] == review['partition_id']]
    if len(partitions) != 1 or any(partitions[0].get(k) != v for k, v in (
            ('model', study.MODEL), ('provider', study.PROVIDER), ('reasoning', study.EFFORT),
            ('cap_usd', study.CAP_USD))):
        raise ValueError('Reviewed budget partition differs')

    plans = {}
    for repeat in ('repeat2', 'repeat3'):
        relative = BASE / repeat / 'manifest.json'
        bind(relative, review['plan_sha256'][repeat])
        plan = json.loads(_file(root, relative).read_text())
        if (plan.get('schema'), plan.get('configuration_id'), plan.get('repeat'),
                plan.get('model'), plan.get('provider_tag'), plan.get('reasoning_effort'),
                plan.get('input_count'), plan.get('request_unit'), plan.get('partition_cap_usd')) != (
                'openrouter-paid-repeat-plan-v1', CONFIG, repeat, study.MODEL,
                study.PROVIDER, study.EFFORT, 60, 'single_record_fresh_context', study.CAP_USD):
            raise ValueError(f'Frozen plan identity changed: {repeat}')
        if plan.get('condition_order') != study.ORDERS[repeat]:
            raise ValueError(f'Frozen condition order changed: {repeat}')
        for source in plan['source_bindings']:
            bind(Path(source['path']), source['sha256'])
        for condition in CONDITIONS:
            requests = plan['conditions'][condition]['development']
            if [r['record_id'] for r in requests] != ids or [r['position'] for r in requests] != list(range(1, 61)):
                raise ValueError(f'Frozen request membership changed: {repeat} {condition}')
            for request in requests:
                if request['request_sha256'] != digest(json.dumps(request['payload'], sort_keys=True)):
                    raise ValueError('Frozen request payload hash changed')
        plans[repeat] = plan
    return ids, labels, pair, review, plans, bind, sources


def _check_attempt(row, planned, *, repeat=None, condition=None, phase='development'):
    if row.get('id') != planned['record_id'] or row.get('request_sha256') != planned['request_sha256']:
        raise ValueError('Attempt ID or request hash differs from frozen plan')
    if row.get('request') != planned['payload'] or row.get('reference_labels_read') is not False:
        raise ValueError('Attempt payload or reference isolation changed')
    endpoint = row.get('provider_endpoint') or {}
    if (row.get('requested_model'), row.get('reasoning_effort'), endpoint.get('tag'),
            endpoint.get('provider_name'), endpoint.get('quantization'), row.get('phase')) != (
            study.MODEL, study.EFFORT, study.PROVIDER, 'DeepInfra', 'fp8', phase):
        raise ValueError('Attempt route or phase differs')
    if repeat is not None and (row.get('repeat'), row.get('condition'), row.get('manifest_sha256')) != (
            repeat, condition, planned['_manifest_sha256']):
        raise ValueError('Repeat attempt identity differs')
    if not isinstance(row.get('attempt_id'), str) or not row['attempt_id']:
        raise ValueError('Attempt ID missing')
    response = row.get('raw_response')
    if response is not None:
        if isinstance(response, dict):
            raw_usage = response.get('usage')
            copied_usage = row.get('usage')
            strict_usage = row.get('status') in ('ok', 'invalid_output') or row.get('cost_unknown') is False
            if (strict_usage and copied_usage != raw_usage) or (
                    not strict_usage and copied_usage not in (None, {}) and copied_usage != raw_usage):
                raise ValueError('Attempt usage differs from original provider usage')
            for key, source in (('returned_model', 'model'), ('returned_provider', 'provider')):
                if key in row and row[key] != response.get(source):
                    raise ValueError('Returned identity differs from raw response')
            if row.get('status') in ('ok', 'invalid_output'):
                if (row.get('returned_model') != response.get('model') or
                        row.get('returned_provider') != response.get('provider') or
                        response.get('model') not in allowed_returned_models(study.MODEL, endpoint) or
                        response.get('provider') != 'DeepInfra'):
                    raise ValueError('Healthy output has wrong provider identity')
            raw_usage = response.get('usage')
            if row.get('cost_unknown') is False and (
                    not isinstance(raw_usage, dict) or raw_usage.get('cost') is None or
                    _money(raw_usage['cost']) != _money(row.get('observed_cost_usd'))):
                raise ValueError('Observed cost differs from original provider usage')
        elif row.get('status') not in ('service_error', 'control_violation'):
            raise ValueError('Non-object response cannot be a healthy output')
        elif row.get('usage') not in (None, {}):
            raise ValueError('Attempt usage has no original provider usage')
    elif row.get('usage') not in (None, {}):
        raise ValueError('Attempt usage has no original provider response')
    if row.get('status') == 'ok' and not valid(row.get('prediction')):
        raise ValueError('Successful attempt has invalid prediction')
    if row.get('status') == 'ok' and response is None:
        raise ValueError('Successful attempt lacks original response')
    if row.get('cost_unknown') is False and response is None:
        raise ValueError('Known charge lacks original provider response')
    if row.get('status') == 'ok':
        choices = response.get('choices')
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
            raise ValueError('Successful attempt lacks one original choice')
        message = choices[0].get('message')
        if not isinstance(message, dict):
            raise ValueError('Successful attempt lacks original message')
        try:
            parsed = json.loads(message['content'])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError('Successful prediction cannot be parsed from original response') from exc
        if (parsed != row['prediction'] or choices[0].get('finish_reason') != 'stop' or
                any(message.get(key) for key in ('refusal', 'tool_calls', 'function_call')) or
                choices[0].get('error')):
            raise ValueError('Successful prediction differs from original response')
        if repeat is not None and row.get('response_diagnostic', {}).get('passed') is not True:
            raise ValueError('Successful repeat lacks passed response diagnostics')
    if type(row.get('billing_ok')) is not bool:
        raise ValueError('Billing status missing')
    if row.get('cost_unknown') is True:
        if row.get('observed_cost_usd') is not None or row.get('billing_ok') is not False:
            raise ValueError('Unknown cost incorrectly settled')
    elif row.get('cost_unknown') is False:
        _money(row.get('observed_cost_usd'))
    else:
        raise ValueError('Cost uncertainty missing')
    if row.get('elapsed_seconds') is not None:
        _number(row['elapsed_seconds'], 'request duration')


def _usage(attempts, pending=False):
    known = []
    durations = []
    for row in attempts:
        durations.append(row.get('elapsed_seconds'))
        if row.get('cost_unknown') is False:
            known.append(_money(row.get('observed_cost_usd')))
    unknown = len(attempts) - len(known) + int(pending)
    names = {'input_tokens': ('prompt_tokens',),
             'output_tokens': ('completion_tokens',),
             'cached_input_tokens': ('prompt_tokens_details', 'cached_tokens'),
             'cache_write_input_tokens': ('prompt_tokens_details', 'cache_write_tokens'),
             'reasoning_output_tokens': ('completion_tokens_details', 'reasoning_tokens')}
    token_totals = {}
    for output, keys in names.items():
        values = []
        for row in attempts:
            response = row.get('raw_response')
            value = response.get('usage') if isinstance(response, dict) else None
            for key in keys:
                value = value.get(key) if isinstance(value, dict) else None
            values.append(value)
        token_totals[output] = sum(values) if values and all(type(v) is int and v >= 0 for v in values) else None
    seconds = sum(durations) if durations and all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x >= 0 for x in durations) else None
    return {'requestCount': len(attempts), 'startedRequestCount': len(attempts) + int(pending),
            'requestSeconds': durations, 'requestSecondsTotal': seconds,
            'tokens': token_totals,
            'knownCostUsd': str(sum(known, Decimal(0))),
            'actualCostUsd': str(sum(known, Decimal(0))) if unknown == 0 else None,
            'unknownCostCount': unknown,
            'costNote': 'USD amounts come from saved provider usage; unknown charges are not zero.'}


def _historical(root, condition, pair, plan, ids, labels, bind):
    source = pair['conditions'][condition]['request_evidence']
    predictions = pair['conditions'][condition]['predictions']
    if source != pair['conditions'][condition]['predictions']:
        # Historical P0 has a different path alias with identical bytes.
        if source['sha256'] != predictions['sha256']:
            raise ValueError('Historical predictions and attempts differ')
    evidence = bind(Path(source['file']), source['sha256'])
    prediction_evidence = bind(Path(predictions['file']), predictions['sha256'])
    rows = _rows(root, Path(source['file']))
    if len(rows) != 60 or [row.get('id') for row in rows] != ids:
        raise ValueError('Historical membership is not 60 ordered records')
    for row, planned in zip(rows, plan['conditions'][condition]['development']):
        _check_attempt(row, planned)
    if len({row['attempt_id'] for row in rows}) != 60:
        raise ValueError('Historical attempt IDs repeat')
    indexed = {row['id']: row for row in rows}
    return {'completionStatus': 'complete', 'score': shared.score(indexed, labels, ids),
            'usage': _usage(rows), 'evidence': {'attempts': evidence,
                                              'predictions': prediction_evidence}}, indexed


def _terminal_events(events, requests, repeat, condition):
    if not events or (events[0].get('event'), events[0].get('repeat'), events[0].get('condition'),
                      events[0].get('phase')) != ('phase_started', repeat, condition, 'development'):
        raise ValueError('Development journal start differs')
    terminal = events[-1]
    status = terminal.get('event')
    if status not in ('phase_completed', 'phase_stopped', 'phase_aborted'):
        return None
    cursor, finished, pending, dangling_intent = 1, [], None, False
    while cursor < len(events) - 1:
        if len(finished) >= len(requests):
            raise ValueError('Too many request events')
        planned = requests[len(finished)]
        intent = events[cursor]
        if (intent.get('event'), intent.get('id'), intent.get('request_sha256')) != (
                'request_intent', planned['record_id'], planned['request_sha256']):
            raise ValueError('Journal request intent differs from frozen plan')
        cursor += 1
        if cursor == len(events) - 1:
            dangling_intent = True
            break  # A reserve failure after intent sent no request.
        started = events[cursor]
        if (started.get('event'), started.get('id'), started.get('request_sha256')) != (
                'request_started', planned['record_id'], planned['request_sha256']):
            raise ValueError('Journal request start differs from frozen plan')
        if not isinstance(started.get('attempt_id'), str) or not started['attempt_id']:
            raise ValueError('Started attempt ID missing')
        cursor += 1
        if cursor == len(events) - 1:
            pending = started
            break
        done = events[cursor]
        if (done.get('event'), done.get('id'), done.get('attempt_id')) != (
                'request_finished', planned['record_id'], started['attempt_id']):
            raise ValueError('Journal completion differs from start')
        finished.append((started, done))
        cursor += 1
    if cursor != len(events) - 1:
        raise ValueError('Journal has trailing events')
    if status == 'phase_completed':
        if len(finished) != 60 or pending is not None or dangling_intent or terminal.get('request_count') != 60:
            raise ValueError('Completed phase lacks 60 finished requests')
        if (terminal.get('repeat'), terminal.get('condition'), terminal.get('phase')) != (
                repeat, condition, 'development'):
            raise ValueError('Completed terminal identity differs')
    elif status == 'phase_stopped':
        if (not finished or pending is not None or dangling_intent or
                terminal.get('id') != finished[-1][0]['id'] or
                terminal.get('reason') != finished[-1][1]['status']):
            raise ValueError('Stopped phase has no matching final attempt')
    return status, finished, pending


def _smoke_binding(root, folder, repeat, condition, plan, manifest_sha, review_sha, bind):
    inspection_path = folder / 'smoke-inspection.json'
    inspection_binding = bind(inspection_path)
    inspection = json.loads(_file(root, inspection_path).read_text())
    journal = folder / 'smoke.journal.jsonl'
    attempts = folder / 'smoke.attempts.jsonl'
    if (inspection.get('schema'), inspection.get('repeat'), inspection.get('condition'),
            inspection.get('decision')) != (
            'openrouter-repeat-smoke-inspection-v1', repeat, condition, 'accepted_unchanged'):
        raise ValueError('Smoke inspection identity differs')
    journal_binding = bind(journal, inspection['journal_sha256'])
    attempts_binding = bind(attempts, inspection['attempts_sha256'])
    events = _rows(root, journal)
    smoke_rows = _rows(root, attempts)
    if (not events or events[-1].get('event') != 'phase_completed' or
            events[-1].get('request_count') != 3 or len(smoke_rows) != 3 or
            [row.get('id') for row in smoke_rows] != [f'DEV-{i:03}' for i in range(1, 4)] or
            any(row.get('status') != 'ok' or row.get('billing_ok') is not True or row.get('cost_unknown') is not False for row in smoke_rows)):
        raise ValueError('Smoke did not close with three valid billed records')
    smoke_claim_path = folder / 'smoke.claim.json'
    claim = json.loads(_file(root, smoke_claim_path).read_text())
    if (claim.get('repeat'), claim.get('condition'), claim.get('phase'),
            claim.get('manifest_sha256'), claim.get('root_review_sha256')) != (
            repeat, condition, 'smoke', manifest_sha, review_sha):
        raise ValueError('Smoke claim binding differs')
    if (events[0].get('event'), events[0].get('repeat'), events[0].get('condition'),
            events[0].get('phase')) != ('phase_started', repeat, condition, 'smoke'):
        raise ValueError('Smoke journal start differs')
    for row, planned in zip(smoke_rows, plan['conditions'][condition]['smoke']):
        _check_attempt(row, dict(planned, _manifest_sha256=manifest_sha),
                       repeat=repeat, condition=condition, phase='smoke')
    if len(events) != 11 or len({row['attempt_id'] for row in smoke_rows}) != 3:
        raise ValueError('Smoke journal does not contain three unique calls')
    for index, row in enumerate(smoke_rows):
        intent, started, finished = events[1 + index * 3:4 + index * 3]
        if ((intent.get('event'), intent.get('id'), intent.get('request_sha256')) !=
                ('request_intent', row['id'], row['request_sha256']) or
                (started.get('event'), started.get('id'), started.get('attempt_id'),
                 started.get('request_sha256')) !=
                ('request_started', row['id'], row['attempt_id'], row['request_sha256']) or
                (finished.get('event'), finished.get('id'), finished.get('attempt_id'),
                 finished.get('status'), finished.get('billing_ok'), finished.get('cost_unknown')) !=
                ('request_finished', row['id'], row['attempt_id'], 'ok', True, False)):
            raise ValueError('Smoke journal differs from inspected attempts')
    return {'inspection': inspection_binding, 'smokeJournal': journal_binding,
            'smokeAttempts': attempts_binding, 'smokeClaim': bind(smoke_claim_path)}


def _repeat_phase(root, repeat, condition, plan, review_sha, ids, labels, bind):
    folder = BASE / repeat / condition
    journal_path = folder / 'development.journal.jsonl'
    if not _file(root, journal_path).exists():
        return None, 'not_started'
    journal_bytes = _file(root, journal_path).read_bytes()
    if not journal_bytes.endswith(b'\n'):
        return None, 'open_no_terminal'
    events = [json.loads(line) for line in journal_bytes.decode('utf-8').splitlines()]
    requests = plan['conditions'][condition]['development']
    parsed = _terminal_events(events, requests, repeat, condition)
    if parsed is None:
        return None, 'open_no_terminal'
    terminal, event_rows, pending = parsed
    claim_path = folder / 'development.claim.json'
    claim = json.loads(_file(root, claim_path).read_text())
    manifest_sha = _sha(_file(root, BASE / repeat / 'manifest.json'))
    if (claim.get('repeat'), claim.get('condition'), claim.get('phase'),
            claim.get('manifest_sha256'), claim.get('root_review_sha256')) != (
            repeat, condition, 'development', manifest_sha, review_sha):
        raise ValueError('Development claim binding differs')
    smoke = _smoke_binding(root, folder, repeat, condition, plan, manifest_sha, review_sha, bind)
    attempt_path = folder / 'development.attempts.jsonl'
    response_path = folder / 'development.responses.jsonl'
    attempts = _rows(root, attempt_path)
    responses = _rows(root, response_path)
    if len(attempts) != len(event_rows):
        raise ValueError('Attempt rows do not match finished journal requests')
    indexed = {}
    started_ids = []
    for index, ((started, done), row) in enumerate(zip(event_rows, attempts)):
        planned = dict(requests[index], _manifest_sha256=manifest_sha)
        _check_attempt(row, planned, repeat=repeat, condition=condition)
        if (row['attempt_id'], row.get('status'), row.get('billing_ok'), row.get('cost_unknown')) != (
                started['attempt_id'], done.get('status'), done.get('billing_ok'), done.get('cost_unknown')):
            raise ValueError('Attempt outcome differs from journal')
        indexed[row['id']] = row
        started_ids.append(row['attempt_id'])
    if pending is not None:
        started_ids.append(pending['attempt_id'])
        indexed[pending['id']] = {'id': pending['id'], 'status': 'unknown_started', 'prediction': None}
    if len(set(started_ids)) != len(started_ids):
        raise ValueError('Repeat attempt ID reused')
    for rid in ids:
        indexed.setdefault(rid, {'id': rid, 'status': 'never_sent', 'prediction': None})
    seen_responses = set()
    starts = {started['attempt_id']: started for started, _ in event_rows}
    if pending is not None:
        starts[pending['attempt_id']] = pending
    for response in responses:
        attempt_id = response.get('attempt_id')
        if attempt_id in seen_responses or attempt_id not in starts:
            raise ValueError('Response sidecar has duplicate or unstarted attempt')
        seen_responses.add(attempt_id)
        started = starts[attempt_id]
        if (response.get('id'), response.get('request_sha256')) != (
                started['id'], started['request_sha256']):
            raise ValueError('Response sidecar request binding differs')
        if attempt_id in {row['attempt_id'] for row in attempts}:
            row = next(row for row in attempts if row['attempt_id'] == attempt_id)
            for key in ('raw_response', 'error_body', 'http_status', 'error_headers'):
                if (key in response) != (key in row) or (key in response and response[key] != row[key]):
                    raise ValueError('Response sidecar differs from attempt row')
    for row in attempts:
        if ('raw_response' in row or 'error_body' in row) and row['attempt_id'] not in seen_responses:
            raise ValueError('Saved body lacks response sidecar')
    if terminal == 'phase_completed' and any(row.get('status') != 'ok' or row.get('billing_ok') is not True or row.get('cost_unknown') is not False for row in attempts):
        raise ValueError('Completed phase contains invalid or unknown-billing attempt')
    state = 'complete' if terminal == 'phase_completed' else 'partial'
    score = shared.score(indexed, labels, ids)
    evidence = {'claim': bind(claim_path), 'journal': bind(journal_path),
                'attempts': bind(attempt_path), 'responses': bind(response_path), **smoke}
    return {'completionStatus': state, 'terminalEvent': terminal,
            'finishedRequests': len(attempts), 'score': score,
            'usage': _usage(attempts, pending is not None), 'evidence': evidence}, None


def _stats(values):
    return {'completedPasses': len(values), 'values': values,
            'mean': sum(values) / len(values) if len(values) == 3 else None,
            'range': [min(values), max(values)] if len(values) == 3 else None}


def build(root=ROOT):
    root = Path(root)
    ids, labels, pair, review, plans, bind, sources = _source_context(root)
    data = {name: {} for name in PASSES}
    indexed = {name: {} for name in PASSES}
    missing, partial = [], []
    for condition in CONDITIONS:
        entry, rows = _historical(root, condition, pair, plans['repeat2'], ids, labels, bind)
        data['original'][condition], indexed['original'][condition] = entry, rows
    review_sha = _sha(_file(root, REVIEW))
    for repeat in ('repeat2', 'repeat3'):
        for condition in CONDITIONS:
            entry, why = _repeat_phase(root, repeat, condition, plans[repeat], review_sha, ids, labels, bind)
            if entry is None:
                missing.append({'pass': repeat, 'condition': condition, 'status': why})
                continue
            data[repeat][condition] = entry
            if entry['completionStatus'] == 'partial':
                partial.append({'pass': repeat, 'condition': condition,
                                'terminalEvent': entry['terminalEvent'],
                                'finishedRequests': entry['finishedRequests']})
            else:
                attempt_path = BASE / repeat / condition / 'development.attempts.jsonl'
                indexed[repeat][condition] = {row['id']: row for row in _rows(root, attempt_path)}
    full = lambda pass_name, condition: condition in data[pass_name] and data[pass_name][condition]['completionStatus'] == 'complete'
    deltas = []
    for pass_name in PASSES:
        for target in ('P1', 'P2'):
            if full(pass_name, 'P0') and full(pass_name, target):
                baseline = data[pass_name]['P0']['score']
                variant = data[pass_name][target]['score']
                deltas.append({'pass': pass_name, 'from': 'P0', 'to': target, 'denominator': 60,
                               'allFour': variant['allFour'] - baseline['allFour'],
                               'fields': {field: variant['fields'][field] - baseline['fields'][field] for field in FIELDS}})
    spread = {}
    for target in ('P1', 'P2'):
        entries = [item for item in deltas if item['to'] == target]
        spread[target] = {'completedPairs': len(entries), 'allFourValues': [item['allFour'] for item in entries],
                          'allFourRange': [min(item['allFour'] for item in entries), max(item['allFour'] for item in entries)] if len(entries) == 3 else None,
                          'fieldRanges': {field: [min(item['fields'][field] for item in entries), max(item['fields'][field] for item in entries)] if len(entries) == 3 else None for field in FIELDS}}
    flips = []
    for condition in CONDITIONS:
        for index, left in enumerate(PASSES):
            for right in PASSES[index + 1:]:
                if full(left, condition) and full(right, condition):
                    flips.append({'condition': condition, 'from': left, 'to': right,
                                  **shared.flip(indexed[left][condition], indexed[right][condition], ids)})
    ranges = {}
    for condition in CONDITIONS:
        scores = [data[name][condition]['score'] for name in PASSES if full(name, condition)]
        ranges[condition] = {'allFour': _stats([item['allFour'] for item in scores]),
                             'fields': {field: _stats([item['fields'][field] for item in scores]) for field in FIELDS}}
    across = {}
    for condition in CONDITIONS:
        if not all(full(name, condition) for name in PASSES):
            continue
        eligible = [rid for rid in ids if all(shared.outcome(indexed[name][condition][rid]) == 'valid' for name in PASSES)]
        across[condition] = {'denominator': len(eligible), 'excludedIds': [rid for rid in ids if rid not in eligible],
                             'fields': {field: [rid for rid in eligible if len({indexed[name][condition][rid]['prediction'][field] for name in PASSES}) > 1] for field in FIELDS},
                             'fourFieldVector': [rid for rid in eligible if len({tuple(indexed[name][condition][rid]['prediction'][field] for field in FIELDS) for name in PASSES}) > 1]}
    return {'schema': 'hosted-repeat-findings-v1', 'configuration': CONFIG,
            'displayName': 'Gemma 4 26B A4B · DeepInfra fp8 · reasoning off',
            'model': study.MODEL, 'effort': study.EFFORT, 'provider': study.PROVIDER,
            'referenceVersion': '0.2',
            'referenceStatus': 'AI reviewed provisional, not independent adjudication',
            'referenceClassCounts': {field: dict(sorted(Counter(labels[rid][field] for rid in ids).items())) for field in FIELDS},
            'denominator': 60, 'completedConditions': sum(full(name, condition) for name in PASSES for condition in CONDITIONS),
            'plannedConditions': 9, 'missingPasses': missing, 'partialPasses': partial,
            'passes': data, 'threePassSummary': ranges, 'pairwiseFlips': flips,
            'changesAcrossThreePasses': across, 'withinPassPromptDeltas': deltas,
            'pairedDeltaSpread': spread, 'sourceBindings': sources,
            'limitations': ['The same 60 synthetic development records appear in each pass.',
                            'Partial phases retain missing outcomes in the 60-record denominator but are not full passes.',
                            'Serving revision and effective seed are unavailable.',
                            'Provisional v0.2 references are not independent adjudication.',
                            'Unknown cost and missing request duration are unavailable, not zero.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Explicit JSON path to create or update')
    parser.add_argument('--check', action='store_true', help='Check existing output without writing')
    args = parser.parse_args(argv)
    report = build()
    content = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if not args.output.exists() or args.output.read_text() != content:
            raise ValueError(f'Stale report: {args.output}')
    else:
        args.output.write_text(content)
    print(f"{report['configuration']}: {report['completedConditions']}/9 complete; {len(report['partialPasses'])} partial")


if __name__ == '__main__':
    main()
