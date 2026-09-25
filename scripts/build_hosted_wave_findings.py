#!/usr/bin/env python3
"""Build offline, source-bound repeat findings for the hosted paid wave."""
import argparse
import base64
from collections import Counter
import hashlib
import json
from pathlib import Path

import build_hosted_repeat_findings as legacy
import build_repeat_findings as shared
import openrouter_qwen27_repeat as qwen
import openrouter_repeat_wave as wave
from development_benchmark import digest, valid
from openrouter_benchmark import allowed_returned_models

ROOT = Path(__file__).resolve().parents[1]
LABELS = Path('data/pilot/proposed_labels.jsonl')
HOSTED = Path(wave.HOSTED)
PASSES = ('original', 'repeat2', 'repeat3')
CONDITIONS = ('P0', 'P1', 'P2')
FIELDS = shared.FIELDS
DISPLAY = {
    'openrouter-paid-gemma4-31b-off': 'Gemma 4 31B · DeepInfra turbo fp4 · reasoning off',
    'openrouter-paid-gemma4-31b-on': 'Gemma 4 31B · DeepInfra turbo fp4 · reasoning on',
    'openrouter-paid-mistral-small32-24b-venice-not-applicable':
        'Mistral Small 3.2 24B · Venice fp8 · reasoning not applicable',
    'openrouter-paid-qwen3.8-27b-off': 'Qwen 3.8 27B · DeepInfra bf16 · reasoning off',
}


def file(root, relative):
    path = (root / relative).resolve()
    path.relative_to(root.resolve())
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(root, relative):
    raw = file(root, relative).read_bytes()
    if not raw.endswith(b'\n') or any(not line.strip() for line in raw.splitlines()):
        raise ValueError(f'Incomplete or blank evidence file: {relative}')
    return [json.loads(line) for line in raw.splitlines()]


def binder(root):
    sources = []

    def bind(relative, expected=None):
        relative = Path(relative)
        path = file(root, relative)
        result = {'path': str(relative), 'sha256': sha(path)}
        if expected is not None and result['sha256'] != expected:
            raise ValueError(f'Source hash changed: {relative}')
        if result not in sources:
            sources.append(result)
        return result

    return bind, sources


def money(value):
    return legacy._money(value)


def _source_context(root, spec):
    is_qwen = spec.id == qwen.SPEC.id
    bind, sources = binder(root)
    bind(LABELS, shared.PINNED_SHA[str(LABELS)])
    label_rows = rows(root, LABELS)
    ids = [row['id'] for row in label_rows]
    if ids != [f'DEV-{i:03d}' for i in range(1, 61)] or any(row.get('review_version') != '0.2' for row in label_rows):
        raise ValueError('Expected 60 ordered provisional v0.2 references')
    labels = {row['id']: row['proposed_labels'] for row in label_rows}
    base = Path('results/repeatability-v1') / spec.id
    pair_path = Path(spec.pair)
    bind(pair_path)
    pair = json.loads(file(root, pair_path).read_text())
    controls = pair['controls']
    if (pair.get('parent_baseline_id'), controls.get('requested_model'), controls.get('provider_tag'),
            controls.get('provider_name'), controls.get('quantization'), controls.get('reasoning_effort'),
            controls.get('workflow')) != (spec.id, spec.model, spec.provider, spec.provider_name,
                                          spec.quantization, spec.effort, 'single_record'):
        raise ValueError('Historical paired controls differ')
    review_path = base / 'root-review-v1.json'
    bind(review_path)
    review = json.loads(file(root, review_path).read_text())
    if (review.get('schema'), review.get('approved'), review.get('review_verdict'),
            review.get('configuration_id'), review.get('partition_cap_usd')) != (
            qwen.RECEIPT_SCHEMA if is_qwen else wave.RECEIPT_SCHEMA,
            True, 'APPROVE', spec.id, spec.cap):
        raise ValueError('Root review identity differs')
    bind('scripts/openrouter_qwen27_repeat.py' if is_qwen else
         'scripts/openrouter_repeat_wave.py', review['controller_sha256'])
    bind(HOSTED, review['hosted_execution_sha256'])
    if is_qwen:
        bind(qwen.PREFLIGHT, review['preflight_sha256'])
        preflight = json.loads(file(root, qwen.PREFLIGHT).read_text())
        route = preflight.get('exact_route') or {}
        if (preflight.get('schema'), preflight.get('configuration_id'),
                preflight.get('proposed_partition_cap_usd'),
                preflight.get('per_call_reserve_usd'),
                preflight.get('max_concurrent_requests_for_configuration'),
                preflight.get('max_tokens'),
                route.get('model_id'), route.get('tag'), route.get('provider_name'),
                route.get('quantization'), route.get('status'),
                route.get('context_length'), route.get('reasoning_mandatory')) != (
                'openrouter-qwen27-public-route-preflight-v1', spec.id, spec.cap,
                '0.047001600', 1, 4096, spec.model, spec.provider, spec.provider_name,
                spec.quantization, 0, spec.context, False):
            raise ValueError('Qwen public route preflight differs')
        if (money(route['pricing_usd_per_token']['prompt']) * 1000000 != money(spec.prompt_price) or
                money(route['pricing_usd_per_token']['completion']) * 1000000 != money(spec.completion_price) or
                not {'structured_outputs', 'max_tokens', 'temperature', 'reasoning', 'reasoning_effort'} <=
                set(route['required_supported_parameters'])):
            raise ValueError('Qwen preflight price or parameter support differs')
    historical = json.loads(file(root, HOSTED).read_text())
    policies = [x for x in historical['configurations'] if x['id'] == spec.id]
    if (len(policies) != 1 or policies[0]['continue_on_invalid_output'] is not spec.continue_invalid or
            policies[0]['controller_timeout_seconds'] != spec.timeout or
            policies[0]['controls']['adapter_controls'] != controls):
        raise ValueError('Historical continuation or timeout policy differs')
    budget_binding = review['budget_manifest']
    bind(budget_binding['path'], budget_binding['sha256'])
    budget = json.loads(file(root, budget_binding['path']).read_text())
    # These absolute paths are historical identities. Compare their bindings
    # to each other, never to the current checkout's absolute directory.
    if (review.get('master_ledger') != budget.get('master_ledger') or
            not isinstance(review['master_ledger'], str) or
            not Path(review['master_ledger']).is_absolute()):
        raise ValueError('Historical master ledger identities differ')
    historical_root = Path(review['master_ledger']).parent.parent
    if Path(review['master_ledger']) != historical_root / 'results/openrouter-paid-budget.jsonl':
        raise ValueError('Historical ledger layout differs')
    partitions = [p for p in budget['partitions'] if p['id'] == review['partition_id']]
    if len(partitions) != 1:
        raise ValueError('Reviewed partition absent or duplicated')
    partition = partitions[0]
    if any(partition.get(k) != v for k, v in (
            ('model', spec.model), ('provider', spec.provider),
            ('reasoning', spec.effort), ('cap_usd', spec.cap))):
        raise ValueError('Reviewed partition controls differ')
    if Path(partition['child_ledger']) != historical_root / base / f"budget-partition-v1-{review['partition_id']}.jsonl":
        raise ValueError('Historical child ledger identity differs')
    plans = {}
    for repeat in ('repeat2', 'repeat3'):
        path = base / repeat / 'manifest.json'
        bind(path, review['plan_sha256'][repeat])
        plan = json.loads(file(root, path).read_text())
        if (plan.get('schema'), plan.get('configuration_id'), plan.get('repeat'),
                plan.get('model'), plan.get('provider_tag'), plan.get('reasoning_effort'),
                plan.get('request_timeout_seconds'), plan.get('continue_on_invalid_output'),
                plan.get('partition_cap_usd'), plan.get('input_count'),
                plan.get('request_unit')) != (
                'openrouter-qwen27-repeat-plan-v1' if is_qwen else
                'openrouter-paid-repeat-wave-plan-v1', spec.id, repeat,
                spec.model, spec.provider, spec.effort, spec.timeout,
                spec.continue_invalid, spec.cap, 60, 'single_record_fresh_context'):
            raise ValueError('Frozen plan identity differs')
        if is_qwen and plan.get('per_call_reserve_usd') != preflight['per_call_reserve_usd']:
            raise ValueError('Qwen plan reserve differs from public preflight')
        if plan.get('condition_order') != list(spec.orders[repeat]) or plan.get('historical_pass_order') != list(spec.historical_order):
            raise ValueError('Frozen condition rotation differs')
        for source in plan['source_bindings']:
            bind(source['path'], source['sha256'])
        if is_qwen:
            paths = {source['path'] for source in plan['source_bindings']}
            required = {str(pair_path), str(HOSTED), str(qwen.PREFLIGHT),
                        'results/repeatability-v1/coverage.json',
                        'results/repeatability-v1/paid-wave-preflight-v1.json',
                        'data/pilot/inputs.jsonl', 'schemas/judgments.schema.json',
                        'scripts/openrouter_qwen27_repeat.py', 'scripts/openrouter_repeat_wave.py',
                        'scripts/openrouter_paid_benchmark.py', 'scripts/paid_budget_partitions_v2.py',
                        *(pair['conditions'][condition]['request_evidence']['file']
                          for condition in CONDITIONS)}
            if not required <= paths:
                raise ValueError('Qwen plan omits a required frozen source')
        for condition in CONDITIONS:
            planned = plan['conditions'][condition]['development']
            if ([x['record_id'] for x in planned] != ids or
                    [x['position'] for x in planned] != list(range(1, 61)) or
                    plan['conditions'][condition]['smoke'] != planned[:3]):
                raise ValueError('Frozen membership or smoke selection differs')
            evidence = pair['conditions'][condition]['request_evidence']
            if plan['conditions'][condition]['historical_attempts'] != {
                    'path': evidence['file'], 'sha256': evidence['sha256']}:
                raise ValueError('Historical request binding differs')
            for request in planned:
                payload = request['payload']
                if (request['request_sha256'] != digest(json.dumps(payload, sort_keys=True)) or
                        payload.get('model') != spec.model or
                        payload.get('provider', {}).get('only') != [spec.provider] or
                        payload.get('max_tokens') != 4096 or payload.get('temperature') != 0 or
                        payload.get('stream') is not False or
                        ('reasoning' in payload) != (spec.effort != 'na') or
                        payload.get('reasoning') != ({'enabled': spec.effort == 'on'} if spec.effort != 'na' else None)):
                    raise ValueError('Frozen request control differs')
                if is_qwen and (set(payload) != set(controls['request_controls']) | {'messages'} or
                                any(payload[key] != value for key, value in controls['request_controls'].items())):
                    raise ValueError('Qwen request differs from historical controls')
        plans[repeat] = plan
    return ids, labels, pair, review, plans, bind, sources, base


def _check_attempt(spec, row, planned, phase, repeat=None, condition=None, manifest_sha=None):
    if (row.get('id'), row.get('request_sha256'), row.get('request'),
            row.get('reference_labels_read')) != (
            planned['record_id'], planned['request_sha256'], planned['payload'], False):
        raise ValueError('Attempt request or reference isolation differs')
    endpoint = row.get('provider_endpoint') or {}
    if (row.get('requested_model'), row.get('reasoning_effort'), row.get('quantization', spec.quantization),
            row.get('request_timeout_seconds'), endpoint.get('tag'), endpoint.get('provider_name'),
            endpoint.get('quantization'), row.get('phase')) != (
            spec.model, spec.effort, spec.quantization, spec.timeout,
            spec.provider, spec.provider_name, spec.quantization, phase):
        raise ValueError('Attempt route, timeout or phase differs')
    if repeat is not None and (row.get('repeat'), row.get('condition'), row.get('manifest_sha256')) != (
            repeat, condition, manifest_sha):
        raise ValueError('Repeat attempt identity differs')
    if not isinstance(row.get('attempt_id'), str) or not row['attempt_id']:
        raise ValueError('Attempt ID missing')
    if row.get('cost_unknown') is True:
        if row.get('observed_cost_usd') is not None or row.get('billing_ok') is not False:
            raise ValueError('Unknown charge treated as known')
    elif row.get('cost_unknown') is False:
        observed = money(row.get('observed_cost_usd'))
        if type(row.get('billing_ok')) is not bool:
            raise ValueError('Known charge lacks billing status')
        raw_usage = (row.get('raw_response') or {}).get('usage') if isinstance(row.get('raw_response'), dict) else None
        if not isinstance(raw_usage, dict) or money(raw_usage.get('cost')) != observed:
            raise ValueError('Observed charge differs from raw provider usage')
    else:
        raise ValueError('Cost uncertainty missing')
    if row.get('elapsed_seconds') is not None:
        legacy._number(row['elapsed_seconds'], 'request duration')
    body = row.get('raw_response')
    if isinstance(body, dict):
        for key, source in (('returned_model', 'model'), ('returned_provider', 'provider')):
            if key in row and row[key] != body.get(source):
                raise ValueError('Returned identity differs from raw body')
        if 'usage' in row and row['usage'] != (body.get('usage') or {}):
            raise ValueError('Attempt usage differs from raw body')
        if row.get('status') in ('ok', 'invalid_output') and not isinstance(row.get('usage'), dict):
            raise ValueError('Healthy model output lacks usage mirror')
    if row.get('status') in ('ok', 'invalid_output'):
        if not isinstance(body, dict):
            raise ValueError('Model output lacks raw body')
        if (body.get('model') not in allowed_returned_models(spec.model, endpoint) or
                body.get('provider') != spec.provider_name or
                row.get('returned_model') != body.get('model') or
                row.get('returned_provider') != body.get('provider')):
            raise ValueError('Model output identity differs')
        if repeat is not None and row.get('response_diagnostic', {}).get('blockers') is None:
            raise ValueError('Repeat response diagnostics missing')
    if row.get('status') == 'ok':
        choices = body.get('choices')
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
            raise ValueError('Successful output lacks one choice')
        choice = choices[0]
        message = choice.get('message') or {}
        try:
            prediction = json.loads(message['content'])
        except (TypeError, ValueError, KeyError) as exc:
            raise ValueError('Successful output cannot be parsed') from exc
        if (prediction != row.get('prediction') or not valid(prediction) or
                choice.get('finish_reason') != 'stop' or choice.get('error') or
                any(message.get(k) for k in ('refusal', 'tool_calls', 'function_call'))):
            raise ValueError('Successful prediction differs from raw response')
        if repeat is not None and row['response_diagnostic'].get('passed') is not True:
            raise ValueError('Successful repeat failed diagnostics')
    if row.get('status') == 'invalid_output' and not spec.continue_invalid:
        # A stopped Gemma phase may contain one intrinsic invalid. It cannot
        # appear in a completed phase; that is checked at the phase level.
        pass


def _sidecar(root, relative, finished, bind, *, required=False, pending=None):
    path = file(root, relative)
    if not path.exists():
        if required:
            raise ValueError('Raw response sidecar missing')
        return None
    binding = bind(relative)
    sidecars = rows(root, relative)
    if len(sidecars) > len(finished) + int(pending is not None):
        raise ValueError('More raw responses than finished attempts')
    by_attempt = {row['attempt_id']: row for row in finished}
    if pending is not None:
        by_attempt[pending['attempt_id']] = {'id': pending['id'],
                                             'request_sha256': pending['request_sha256'],
                                             'status': 'unknown_started'}
    seen = set()
    for raw in sidecars:
        attempt = raw.get('attempt_id')
        if attempt in seen or attempt not in by_attempt:
            raise ValueError('Raw response has duplicate or unstarted attempt')
        seen.add(attempt)
        row = by_attempt[attempt]
        if (raw.get('id'), raw.get('request_sha256')) != (row['id'], row['request_sha256']):
            raise ValueError('Raw response request binding differs')
        if 'body_base64' in raw:
            try:
                body = base64.b64decode(raw['body_base64'], validate=True)
            except (ValueError, TypeError) as exc:
                raise ValueError('Raw body encoding invalid') from exc
            if raw.get('http_status') != 200 or not isinstance(raw.get('response_headers'), dict):
                raise ValueError('Raw HTTP metadata differs')
            if raw.get('body_token_redacted') is False and raw.get('body_bytes_captured') != len(body):
                raise ValueError('Raw body byte count differs')
            if not raw.get('body_truncated_at_limit') and not raw.get('read_error'):
                try:
                    parsed = json.loads(body)
                except (UnicodeDecodeError, ValueError):
                    parsed = None
                if parsed != row.get('raw_response') and row.get('status') not in (
                        'service_error', 'control_violation', 'unknown_started'):
                    raise ValueError('Raw body differs from attempt response')
            elif row.get('status') not in ('service_error', 'control_violation', 'unknown_started'):
                raise ValueError('Healthy output has truncated raw body')
        elif 'error_body' in raw:
            if row.get('status') != 'unknown_started' and (
                    raw.get('error_body'), raw.get('http_status'), raw.get('error_headers')) != (
                    row.get('error_body'), row.get('http_status'), row.get('error_headers')):
                raise ValueError('HTTP error sidecar differs from attempt')
        else:
            raise ValueError('Raw response sidecar has no body')
    for row in finished:
        if ('raw_response' in row or 'error_body' in row) and row['attempt_id'] not in seen:
            raise ValueError('Saved body lacks raw sidecar')
    return binding


def _continued_intrinsic_invalid(row):
    body = row.get('raw_response') or {}
    choices = body.get('choices') or []
    if len(choices) != 1 or not isinstance(choices[0], dict):
        return False
    choice = choices[0]
    message = choice.get('message') or {}
    blockers = set(row.get('response_diagnostic', {}).get('blockers', []))
    return (row.get('status') == 'invalid_output' and row.get('billing_ok') is True and
            row.get('cost_unknown') is False and choice.get('finish_reason') in ('stop', 'length') and
            not choice.get('error') and not any(message.get(k) for k in ('refusal', 'tool_calls', 'function_call')) and
            blockers <= {'truncation:length'})


def _historical(root, spec, condition, pair, plan, ids, labels, bind):
    source = pair['conditions'][condition]['request_evidence']
    evidence = bind(source['file'], source['sha256'])
    attempts = rows(root, source['file'])
    if len(attempts) != 60 or [row.get('id') for row in attempts] != ids:
        raise ValueError('Historical attempt membership differs')
    for row, planned in zip(attempts, plan['conditions'][condition]['development']):
        _check_attempt(spec, row, planned, 'development')
    if len({row['attempt_id'] for row in attempts}) != 60:
        raise ValueError('Historical attempt IDs reused')
    indexed = {row['id']: row for row in attempts}
    return {'completionStatus': 'complete', 'score': shared.score(indexed, labels, ids),
            'usage': legacy._usage(attempts), 'evidence': {'attempts': evidence}}, indexed


def _smoke(root, spec, base, repeat, condition, plan, manifest_sha, review_sha, bind):
    folder = base / repeat / condition
    inspection_path = folder / 'smoke-inspection.json'
    inspection_binding = bind(inspection_path)
    inspection = json.loads(file(root, inspection_path).read_text())
    journal_path = folder / 'smoke.journal.jsonl'
    attempts_path = folder / 'smoke.attempts.jsonl'
    responses_path = folder / 'smoke.responses.jsonl'
    if (inspection.get('schema'), inspection.get('repeat'), inspection.get('condition'),
            inspection.get('decision')) != (
            'openrouter-repeat-smoke-inspection-v1', repeat, condition, 'accepted_unchanged'):
        raise ValueError('Smoke inspection identity differs')
    journal_binding = bind(journal_path, inspection['journal_sha256'])
    attempts_binding = bind(attempts_path, inspection['attempts_sha256'])
    responses_binding = bind(responses_path, inspection['responses_sha256'])
    events = rows(root, journal_path)
    attempts = rows(root, attempts_path)
    if (len(attempts) != 3 or [r.get('id') for r in attempts] != [f'DEV-{i:03d}' for i in range(1, 4)] or
            len(events) != 11 or events[0].get('event') != 'phase_started' or
            events[-1].get('event') != 'phase_completed' or events[-1].get('request_count') != 3):
        raise ValueError('Inspected smoke did not close with three calls')
    claim_path = folder / 'smoke.claim.json'
    claim = json.loads(file(root, claim_path).read_text())
    if (claim.get('repeat'), claim.get('condition'), claim.get('phase'),
            claim.get('manifest_sha256'), claim.get('root_review_sha256')) != (
            repeat, condition, 'smoke', manifest_sha, review_sha):
        raise ValueError('Smoke claim binding differs')
    for index, (row, planned) in enumerate(zip(attempts, plan['conditions'][condition]['smoke'])):
        _check_attempt(spec, row, planned, 'smoke', repeat, condition, manifest_sha)
        if row['status'] != 'ok' or row['cost_unknown'] is not False:
            raise ValueError('Inspected smoke contains invalid or unknown billing')
        intent, started, finished = events[1 + index * 3:4 + index * 3]
        if ((intent.get('event'), intent.get('id'), intent.get('request_sha256')) !=
                ('request_intent', row['id'], row['request_sha256']) or
                (started.get('event'), started.get('id'), started.get('attempt_id'),
                 started.get('request_sha256')) !=
                ('request_started', row['id'], row['attempt_id'], row['request_sha256']) or
                (finished.get('event'), finished.get('id'), finished.get('attempt_id'),
                 finished.get('status'), finished.get('billing_ok'), finished.get('cost_unknown')) !=
                ('request_finished', row['id'], row['attempt_id'], 'ok', True, False)):
            raise ValueError('Smoke journal differs from attempts')
    _sidecar(root, responses_path, attempts, bind, required=True)
    if len(rows(root, responses_path)) != 3:
        raise ValueError('Inspected smoke lacks three raw bodies')
    return {'inspection': inspection_binding, 'smokeJournal': journal_binding,
            'smokeAttempts': attempts_binding, 'smokeResponses': responses_binding,
            'smokeClaim': bind(claim_path)}


def _repeat_phase(root, spec, base, repeat, condition, plan, review_sha, ids, labels, bind):
    folder = base / repeat / condition
    journal_path = folder / 'development.journal.jsonl'
    journal_file = file(root, journal_path)
    if not journal_file.exists():
        return None, 'not_started', None
    journal_raw = journal_file.read_bytes()
    if not journal_raw.endswith(b'\n'):
        return None, 'open_no_terminal', None
    events = [json.loads(line) for line in journal_raw.splitlines()]
    if not events or events[-1].get('event') not in ('phase_completed', 'phase_stopped', 'phase_aborted'):
        return None, 'open_no_terminal', None
    planned = plan['conditions'][condition]['development']
    parsed = legacy._terminal_events(events, planned, repeat, condition)
    if parsed is None:
        return None, 'open_no_terminal', None
    terminal, journal_rows, pending = parsed
    manifest_path = base / repeat / 'manifest.json'
    manifest_sha = sha(file(root, manifest_path))
    claim_path = folder / 'development.claim.json'
    claim = json.loads(file(root, claim_path).read_text())
    if (claim.get('repeat'), claim.get('condition'), claim.get('phase'),
            claim.get('manifest_sha256'), claim.get('root_review_sha256')) != (
            repeat, condition, 'development', manifest_sha, review_sha):
        raise ValueError('Development claim binding differs')
    smoke = _smoke(root, spec, base, repeat, condition, plan, manifest_sha, review_sha, bind)
    attempts_path = folder / 'development.attempts.jsonl'
    responses_path = folder / 'development.responses.jsonl'
    attempts = rows(root, attempts_path)
    if len(attempts) != len(journal_rows):
        raise ValueError('Finished journal count differs from attempts')
    indexed = {}
    started_ids = []
    for index, ((started, finished), row) in enumerate(zip(journal_rows, attempts)):
        _check_attempt(spec, row, planned[index], 'development', repeat, condition, manifest_sha)
        if (row['attempt_id'], row.get('status'), row.get('billing_ok'), row.get('cost_unknown')) != (
                started['attempt_id'], finished.get('status'), finished.get('billing_ok'), finished.get('cost_unknown')):
            raise ValueError('Development journal outcome differs from attempt')
        indexed[row['id']] = row
        started_ids.append(row['attempt_id'])
    if pending is not None:
        started_ids.append(pending['attempt_id'])
        indexed[pending['id']] = {'id': pending['id'], 'status': 'unknown_started', 'prediction': None}
    if len(set(started_ids)) != len(started_ids):
        raise ValueError('Repeat attempt ID reused')
    for rid in ids:
        indexed.setdefault(rid, {'id': rid, 'status': 'never_sent', 'prediction': None})
    response_binding = _sidecar(
        root, responses_path, attempts, bind, pending=pending,
        required=(terminal == 'phase_completed' or
                  any('raw_response' in row or 'error_body' in row for row in attempts)))
    if terminal == 'phase_completed':
        allowed = {'ok', 'invalid_output'} if spec.continue_invalid else {'ok'}
        if (len(attempts) != 60 or pending is not None or
                any(row.get('status') not in allowed or row.get('billing_ok') is not True or
                    row.get('cost_unknown') is not False for row in attempts)):
            raise ValueError('Completed phase has wrong count, status or billing')
        if spec.continue_invalid and any(row['status'] == 'invalid_output' and
                                         not _continued_intrinsic_invalid(row) for row in attempts):
            raise ValueError('Completed phase includes noncontinuable invalid output')
    state = 'complete' if terminal == 'phase_completed' else 'partial'
    evidence = {'claim': bind(claim_path), 'journal': bind(journal_path),
                'attempts': bind(attempts_path), **smoke}
    if response_binding is not None:
        evidence['responses'] = response_binding
    return {'completionStatus': state, 'terminalEvent': terminal,
            'finishedRequests': len(attempts), 'score': shared.score(indexed, labels, ids),
            'usage': legacy._usage(attempts, pending is not None), 'evidence': evidence}, None, indexed


def build_series(spec, root=ROOT):
    root = Path(root)
    ids, labels, pair, review, plans, bind, sources, base = _source_context(root, spec)
    data = {name: {} for name in PASSES}
    indexed = {name: {} for name in PASSES}
    missing, partial = [], []
    for condition in CONDITIONS:
        entry, records = _historical(root, spec, condition, pair, plans['repeat2'], ids, labels, bind)
        data['original'][condition], indexed['original'][condition] = entry, records
    review_sha = sha(file(root, base / 'root-review-v1.json'))
    for repeat in ('repeat2', 'repeat3'):
        for condition in CONDITIONS:
            entry, reason, records = _repeat_phase(root, spec, base, repeat, condition,
                                                   plans[repeat], review_sha, ids, labels, bind)
            if entry is None:
                missing.append({'pass': repeat, 'condition': condition, 'status': reason})
                continue
            data[repeat][condition] = entry
            if entry['completionStatus'] == 'partial':
                partial.append({'pass': repeat, 'condition': condition,
                                'terminalEvent': entry['terminalEvent'],
                                'finishedRequests': entry['finishedRequests']})
            else:
                indexed[repeat][condition] = records
    def full(pass_name, condition):
        return (condition in data[pass_name] and
                data[pass_name][condition]['completionStatus'] == 'complete')

    deltas = []
    for name in PASSES:
        for target in ('P1', 'P2'):
            if full(name, 'P0') and full(name, target):
                left, right = data[name]['P0']['score'], data[name][target]['score']
                deltas.append({'pass': name, 'from': 'P0', 'to': target, 'denominator': 60,
                               'allFour': right['allFour'] - left['allFour'],
                               'fields': {f: right['fields'][f] - left['fields'][f] for f in FIELDS}})
    spread = {}
    for target in ('P1', 'P2'):
        subset = [x for x in deltas if x['to'] == target]
        spread[target] = {'completedPairs': len(subset),
                          'allFourValues': [x['allFour'] for x in subset],
                          'allFourRange': [min(x['allFour'] for x in subset), max(x['allFour'] for x in subset)] if len(subset) == 3 else None,
                          'fieldRanges': {f: [min(x['fields'][f] for x in subset), max(x['fields'][f] for x in subset)] if len(subset) == 3 else None for f in FIELDS}}
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
        ranges[condition] = {'allFour': legacy._stats([x['allFour'] for x in scores]),
                             'fields': {f: legacy._stats([x['fields'][f] for x in scores]) for f in FIELDS}}
    across = {}
    for condition in CONDITIONS:
        if not all(full(name, condition) for name in PASSES):
            continue
        eligible = [rid for rid in ids if all(shared.outcome(indexed[name][condition][rid]) == 'valid'
                                              for name in PASSES)]
        across[condition] = {'denominator': len(eligible),
                             'excludedIds': [rid for rid in ids if rid not in eligible],
                             'fields': {f: [rid for rid in eligible if len({indexed[name][condition][rid]['prediction'][f]
                                                                          for name in PASSES}) > 1] for f in FIELDS},
                             'fourFieldVector': [rid for rid in eligible if len({tuple(indexed[name][condition][rid]['prediction'][f]
                                                                                      for f in FIELDS) for name in PASSES}) > 1]}
    return {'schema': 'hosted-repeat-findings-v1', 'configuration': spec.id,
            'displayName': DISPLAY[spec.id], 'model': spec.model, 'effort': spec.effort,
            'provider': spec.provider, 'referenceVersion': '0.2',
            'referenceStatus': 'AI reviewed provisional, not independent adjudication',
            'referenceClassCounts': {f: dict(sorted(Counter(labels[rid][f] for rid in ids).items())) for f in FIELDS},
            'denominator': 60,
            'completedConditions': sum(full(name, condition) for name in PASSES for condition in CONDITIONS),
            'plannedConditions': 9, 'missingPasses': missing, 'partialPasses': partial,
            'passes': data, 'threePassSummary': ranges, 'pairwiseFlips': flips,
            'changesAcrossThreePasses': across, 'withinPassPromptDeltas': deltas,
            'pairedDeltaSpread': spread, 'sourceBindings': sources,
            'limitations': ['The same 60 synthetic development records appear in each pass.',
                            'Partial phases retain missing outcomes in the 60-record denominator but are not full passes.',
                            'Serving revision and effective seed are unavailable.',
                            'Provisional v0.2 references are not independent adjudication.',
                            'Unknown cost, token counts and missing request duration are unavailable, not zero.']}


def build(root=ROOT):
    root = Path(root)
    return {'schema': 'hosted-repeat-series-v1',
            'series': [legacy.build(root), *(build_series(spec, root) for spec in wave.SPECS.values()),
                       build_series(qwen.SPEC, root)]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path, help='Explicit JSON path to create or update')
    parser.add_argument('--check', action='store_true', help='Check existing output without writing')
    args = parser.parse_args(argv)
    report = build()
    content = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if not args.output.exists() or args.output.read_text() != content:
            raise ValueError(f'Stale report: {args.output}')
    else:
        args.output.write_text(content)
    print(', '.join(f"{series['configuration']} {series['completedConditions']}/9"
                    for series in report['series']))


if __name__ == '__main__':
    main()
