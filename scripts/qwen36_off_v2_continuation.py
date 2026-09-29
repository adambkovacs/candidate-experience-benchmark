#!/usr/bin/env python3
"""Reviewed, non-replayable DEV-007..060 continuation of Qwen off v2 fresh1/P0."""
import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import time
from urllib.parse import quote

import openrouter_paid_benchmark as paid
import paid_budget_partitions_v2 as partitions
import qwen36_off_fresh_repeat_admission as admission
import qwen36_off_fresh_repeat_execution_v2 as original
from development_benchmark import ROOT, digest, read_rows, valid
from openrouter_benchmark import allowed_returned_models

BASE = ROOT / 'results/repeatability-v1/qwen36-off-fresh3-v2'
SUFFIX = BASE / 'never-sent-suffix-v1'
IDS = [f'DEV-{i:03d}' for i in range(7, 61)]
ALL_IDS = [f'DEV-{i:03d}' for i in range(1, 61)]
PARTITION = 'qwen36-off-fresh3-20260929'
SCHEMA = 'qwen36-off-v2-never-sent-suffix-v1'
MAX_RAW = 16 * 1024 * 1024


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    data = Path(path).read_bytes()
    if data and not data.endswith(b'\n'):
        raise ValueError('Incomplete JSONL tail')
    return [json.loads(line) for line in data.splitlines() if line.strip()]


def relative(path):
    return str(Path(path).resolve().relative_to(ROOT.resolve()))


def binding(path):
    return {'path': relative(path), 'sha256': sha(path)}


def read_bound(item):
    path = (ROOT / item['path']).resolve()
    path.relative_to(ROOT.resolve())
    if sha(path) != item['sha256']:
        raise ValueError('Bound evidence changed: ' + item['path'])
    return path


def files():
    return {part: SUFFIX / ('development.' + suffix) for part, suffix in
            (('claim', 'claim.json'), ('journal', 'journal.jsonl'),
             ('raw', 'raw.jsonl'), ('records', 'records.jsonl'))}


def source_paths():
    manifest_path = BASE / 'manifest.json'
    admission_path = ROOT / json.loads(manifest_path.read_text())['admission_plan']
    result = {'manifest': manifest_path, 'admission_plan': admission_path,
              'budget_manifest': BASE / 'budget.json'}
    for stage in ('smoke', 'development'):
        for part, suffix in (('claim', 'claim.json'), ('journal', 'journal.jsonl'),
                             ('raw', 'raw.jsonl'), ('records', 'records.jsonl'),
                             ('review', 'root-review.json')):
            result[stage + '_' + part] = BASE / ('phase-01-' + stage + '.' + suffix)
    return result


def frozen_requests(manifest):
    history, controls, endpoint, model = admission.source_state()
    inputs = read_rows(admission.INPUTS)
    if [item.get('id') for item in inputs] != ALL_IDS:
        raise ValueError('Frozen input order differs')
    policy = (ROOT / history['baseline_instruction']['file']).read_text()
    schema = controls['response_format']['json_schema']['schema']
    frozen = manifest['requests_by_condition']['P0']
    if [item.get('id') for item in frozen] != ALL_IDS:
        raise ValueError('Frozen P0 membership differs')
    result = []
    for item, saved in zip(inputs, frozen):
        payload = paid.make_payload(admission.MODEL, endpoint, item['feedback'], policy, schema,
                                    'off', 4096, paid.number('0.1'), paid.number('0.9'), model)
        if (digest(json.dumps(payload, sort_keys=True)) != saved['request_sha256'] or
                digest(item['feedback']) != saved['input_sha256'] or
                digest(policy) != saved['instruction_sha256']):
            raise ValueError('Frozen P0 request differs')
        result.append({'id': item['id'], 'request_sha256': saved['request_sha256'],
                       'input_sha256': saved['input_sha256'],
                       'instruction_sha256': saved['instruction_sha256'], 'payload': payload})
    return result, endpoint, model


def verify_original(manifest, requests, sources):
    manifest_sha = sources['manifest']['sha256']
    budget_sha = sources['budget_manifest']['sha256']
    if (manifest.get('schema') != 'affordable-hosted-fresh3-execution-v2' or
            manifest.get('configuration_id') != admission.CONFIG or
            (manifest['phases'][0]['repeat'], manifest['phases'][0]['condition']) != ('fresh1', 'P0') or
            manifest['phases'][0]['development_ids'] != ALL_IDS or
            manifest['phases'][0]['smoke_ids'] != ALL_IDS[:3]):
        raise ValueError('Original frozen series differs')
    for stage, expected_ids in (('smoke', ALL_IDS[:3]), ('development', ALL_IDS[:6])):
        claim = json.loads(read_bound(sources[stage + '_claim']).read_text())
        review = json.loads(read_bound(sources[stage + '_review']).read_text())
        journal = rows(read_bound(sources[stage + '_journal']))
        raw = rows(read_bound(sources[stage + '_raw']))
        records = rows(read_bound(sources[stage + '_records']))
        if (claim.get('schema') != 'affordable-hosted-stage-claim-v1' or
                claim.get('manifest_sha256') != manifest_sha or
                claim.get('budget_manifest_sha256') != budget_sha or
                claim.get('partition_id') != PARTITION or claim.get('phase_index') != 0 or
                claim.get('repeat') != 'fresh1' or claim.get('condition') != 'P0' or
                claim.get('stage') != stage or claim.get('ids') != manifest['phases'][0][stage + '_ids'] or
                claim.get('review_sha256') != sources[stage + '_review']['sha256'] or
                review.get('approved') is not True or review.get('manifest_sha256') != manifest_sha or
                review.get('budget_manifest_sha256') != budget_sha or
                review.get('partition_id') != PARTITION or review.get('phase_index') != 0 or
                review.get('stage') != stage or
                review.get('runner_sha256') != sha(original.__file__) or
                [x.get('id') for x in records] != expected_ids or
                [x.get('id') for x in raw] != expected_ids or
                len(journal) != 1 + (3 * 3 if stage == 'smoke' else 5 * 3 + 2) + (stage == 'smoke') or
                journal[0] != {'event': 'stage_claimed', 'claim_sha256': sources[stage + '_claim']['sha256']}):
            raise ValueError('Original claim, review, journal or membership differs')
        if stage == 'development':
            inspection = review.get('smoke_inspection') or {}
            if (inspection.get('approved') is not True or inspection.get('statuses') != ['ok'] * 3 or
                    any(inspection.get('smoke_' + key + '_sha256') != sources['smoke_' + key]['sha256']
                        for key in ('records', 'journal', 'raw'))):
                raise ValueError('Original smoke inspection differs')
        if stage == 'smoke' and journal[-1] != {'event': 'stage_completed', 'count': 3}:
            raise ValueError('Original smoke is not closed')
        if stage == 'development' and journal[-1].get('event') == 'stage_completed':
            raise ValueError('Original failed development was rewritten complete')
        cursor = 1
        raw_bytes = read_bound(sources[stage + '_raw']).read_bytes().splitlines(keepends=True)
        seen = set()
        for index, (rid, sidecar, row) in enumerate(zip(expected_ids, raw, records)):
            request = requests[index]
            attempt = row.get('attempt_id')
            if (not isinstance(attempt, str) or not attempt or attempt in seen or
                    sidecar.get('attempt_id') != attempt or row.get('id') != rid or
                    row.get('request') != request['payload'] or
                    row.get('request_sha256') != request['request_sha256'] or
                    row.get('input_sha256') != request['input_sha256'] or
                    row.get('policy_sha256') != request['instruction_sha256'] or
                    row.get('requested_model') != admission.MODEL or
                    row.get('reasoning_effort') != 'off' or
                    row.get('provider_endpoint', {}).get('tag') != admission.PROVIDER or
                    row.get('budget_partition_id') != PARTITION or
                    row.get('reserved_cost_usd') != str(admission.RESERVE) or
                    row.get('reference_labels_read') is not False or
                    journal[cursor] != {'event': 'request_started', 'attempt_id': attempt,
                                        'id': rid, 'request_sha256': request['request_sha256'],
                                        'reserved_cost_usd': str(admission.RESERVE)}):
                raise ValueError('Original request or start differs')
            seen.add(attempt)
            cursor += 1
            is_failed = stage == 'development' and index == 5
            if is_failed:
                if (row.get('status') != 'service_error' or row.get('http_status') != 429 or
                        row.get('cost_unknown') is not True or row.get('billing_ok') is not False or
                        row.get('observed_cost_usd') is not None or
                        sidecar.get('error_body') != row.get('raw_error_response') or
                        not isinstance(sidecar.get('error_body'), str)):
                    raise ValueError('Original DEV-006 failure differs')
            else:
                body = sidecar.get('body')
                if (not isinstance(body, dict) or row.get('raw_response') != body or
                        row.get('status') != 'ok' or row.get('cost_unknown') is not False or
                        row.get('billing_ok') is not True or
                        row.get('observed_cost_usd') != str(paid.number(body['usage']['cost'])) or
                        not valid(row.get('prediction')) or
                        row.get('prediction') != json.loads(body['choices'][0]['message']['content']) or
                        row.get('usage') != body.get('usage') or
                        body.get('provider') != 'AkashML' or
                        body.get('model') not in allowed_returned_models(admission.MODEL, row['provider_endpoint'])):
                    raise ValueError('Original valid response differs')
                expected_raw_event = {'event': 'raw_saved', 'attempt_id': attempt,
                                      'raw_sha256': hashlib.sha256(b''.join(raw_bytes[:index + 1])).hexdigest()}
                if journal[cursor] != expected_raw_event:
                    raise ValueError('Original raw attribution differs')
                cursor += 1
            if journal[cursor] != {'event': 'request_finished', 'attempt_id': attempt,
                                   'id': rid, 'status': row['status'], 'billing_ok': row['billing_ok']}:
                raise ValueError('Original finish differs')
            cursor += 1
        if cursor != len(journal) - (stage == 'smoke'):
            raise ValueError('Original journal has extra or missing events')
    return rows(read_bound(sources['smoke_records'])), rows(read_bound(sources['development_records']))


def budget_prefix(sources, smoke, development):
    budget = json.loads(read_bound(sources['budget_manifest']).read_text())
    if (budget.get('version') != 'paid-partitions-v1' or
            budget.get('master_ledger') != str(admission.MASTER.resolve())):
        raise ValueError('Original budget manifest differs')
    matches = [x for x in budget.get('partitions', []) if x.get('id') == PARTITION]
    if (len(matches) != 1 or (matches[0].get('model'), matches[0].get('provider'),
             matches[0].get('reasoning'), matches[0].get('cap_usd')) !=
            (admission.MODEL, admission.PROVIDER, 'off', '0.15')):
        raise ValueError('Original child allocation differs')
    ledger = Path(matches[0]['child_ledger']).resolve()
    if ledger != (BASE / f'budget-{PARTITION}.jsonl').resolve():
        raise ValueError('Child ledger path differs')
    events = rows(ledger)
    expected = [{'event': 'budget', 'cap_usd': '0.15'}]
    for record in smoke + development:
        attempt = record['attempt_id']
        expected.append({'event': 'reserve', 'attempt_id': attempt,
                         'record_id': record['id'], 'usd': str(admission.RESERVE)})
        if record['id'] == 'DEV-006' and record['phase'] == 'development':
            if len(events) <= len(expected):
                raise ValueError('DEV-006 full-bound accounting absent')
            event = events[len(expected)]
            if (event.get('event') != 'unknown_cost_accounted_as_upper_bound' or
                    event.get('attempt_id') != attempt or event.get('usd') != str(admission.RESERVE) or
                    event.get('actual_cost_usd') is not None or
                    event.get('evidence_sha256') != sources['development_records']['sha256'] or
                    Path(event.get('evidence_path', '')).resolve() != read_bound(sources['development_records']) or
                    not event.get('reason')):
                raise ValueError('DEV-006 full-bound accounting differs')
            expected.append(event)
        else:
            expected.append({'event': 'settle', 'attempt_id': attempt,
                             'usd': record['observed_cost_usd']})
    if events[:len(expected)] != expected:
        raise ValueError('Original child ledger prefix differs')
    # Hash the original bytes, not reserialized JSON, to bind the append-only prefix.
    raw_lines = ledger.read_bytes().splitlines(keepends=True)
    prefix = b''.join(raw_lines[:len(expected)])
    return {'path': relative(ledger), 'event_count': len(expected),
            'sha256': hashlib.sha256(prefix).hexdigest()}


def expected_manifest():
    sources = {key: binding(path) for key, path in source_paths().items()}
    manifest = original.load_manifest(read_bound(sources['manifest']), sources['manifest']['sha256'])
    requests, endpoint, _ = frozen_requests(manifest)
    smoke, development = verify_original(manifest, requests, sources)
    prefix = budget_prefix(sources, smoke, development)
    return {'schema': SCHEMA, 'status': 'FROZEN', 'configuration': admission.CONFIG,
            'phase': 'fresh1/P0/development_suffix', 'request_ids': IDS,
            'failed_id_retained': 'DEV-006', 'retry_count': 0,
            'denominator': 60, 'partition_id': PARTITION,
            'child_cap_usd': '0.15', 'reserve_usd': str(admission.RESERVE),
            'route': manifest['route'], 'requests': requests[6:],
            'sources': sources, 'child_ledger_prefix': prefix,
            'controller': binding(__file__), 'output_directory': relative(SUFFIX)}


def freeze(path):
    result = expected_manifest()
    if Path(path).resolve() != (SUFFIX / 'manifest.json').resolve():
        raise ValueError('Suffix manifest must use its unique directory')
    SUFFIX.mkdir(parents=True, exist_ok=True)
    original.atomic_json(path, result)
    return result


def validate_manifest(path, expected_sha):
    path = Path(path).resolve()
    if path != (SUFFIX / 'manifest.json').resolve():
        raise ValueError('Suffix manifest path differs')
    if sha(path) != expected_sha:
        raise ValueError('Suffix manifest hash differs')
    result = json.loads(path.read_text())
    if result != expected_manifest():
        raise ValueError('Suffix manifest differs from current bound evidence')
    return result


def validate_review(path, manifest_sha, manifest, budget_path):
    review = json.loads(Path(path).read_text())
    expected = {'schema': SCHEMA + '-root-review', 'approved': True,
                'manifest_sha256': manifest_sha,
                'controller_sha256': manifest['controller']['sha256'],
                'budget_manifest_sha256': sha(budget_path),
                'original_review_sha256': manifest['sources']['development_review']['sha256'],
                'partition_id': PARTITION, 'request_ids': IDS, 'failed_id_retained': 'DEV-006'}
    if any(review.get(key) != value for key, value in expected.items()):
        raise ValueError('Exact suffix root review differs')
    if not isinstance(review.get('cooldown_note'), str) or not review['cooldown_note'].strip():
        raise ValueError('Explicit cooldown decision absent')
    when = datetime.fromisoformat(str(review.get('cooldown_not_before_utc', '')).replace('Z', '+00:00'))
    if when.utcoffset() != timezone.utc.utcoffset(None) or datetime.now(timezone.utc) < when:
        raise ValueError('Cooldown gate not reached')
    return review


def live_controls(manifest):
    catalog = paid.fetch('/models', timeout=300)
    endpoints = paid.fetch('/models/' + quote(admission.MODEL, safe='/') + '/endpoints', timeout=300)
    model, endpoint = paid.select_endpoint(admission.MODEL, admission.PROVIDER, catalog, endpoints,
                                            paid.number('0.1'), paid.number('0.9'))
    historical = json.loads((ROOT / manifest['sources']['manifest']['path']).read_text())['route']
    _, _, old_endpoint, _ = admission.source_state()
    critical = ('tag', 'provider_name', 'quantization', 'model_id', 'context_length',
                'pricing', 'supported_parameters')
    if (any(endpoint.get(key) != old_endpoint.get(key) for key in critical) or
            paid.reasoning(model, endpoint, 'off') != {'enabled': False} or
            paid.reservation(endpoint, 4096, paid.number('0.1'), paid.number('0.9')) != admission.RESERVE or
            historical != manifest['route']):
        raise ValueError('Live route or reservation differs from frozen AkashML controls')
    return model, endpoint


def execute(manifest_path, manifest_sha, review_path, budget_path, env_file=None):
    manifest = validate_manifest(manifest_path, manifest_sha)
    budget_path = Path(budget_path).resolve()
    if Path(review_path).resolve() != (SUFFIX / 'root-review.json').resolve():
        raise ValueError('Suffix review path differs')
    if budget_path != read_bound(manifest['sources']['budget_manifest']):
        raise ValueError('Exact child budget manifest required')
    validate_review(review_path, manifest_sha, manifest, budget_path)
    target = files()
    if any(path.exists() for path in target.values()):
        raise FileExistsError('Suffix already claimed; no replay')
    model, endpoint = live_controls(manifest)
    ledger = partitions.open_partition(admission.MASTER, budget_path, PARTITION,
                                       admission.MODEL, admission.PROVIDER, 'off')
    try:
        _, pending, blocked = ledger.state()
        if pending or blocked or ledger.closed:
            raise ValueError('Child budget has pending, blocked or closed state')
        token = paid.load_key(env_file)
        SUFFIX.mkdir(parents=True, exist_ok=True)
        original.atomic_json(target['claim'], {'schema': SCHEMA + '-claim',
            'manifest_sha256': manifest_sha, 'review_sha256': sha(review_path),
            'budget_manifest_sha256': sha(budget_path), 'partition_id': PARTITION,
            'request_ids': IDS})
        with target['journal'].open('x') as journal, target['raw'].open('x') as raw, target['records'].open('x') as records:
            paid.durable(journal, {'event': 'suffix_claimed', 'claim_sha256': sha(target['claim'])})
            for item in manifest['requests']:
                rid, payload = item['id'], item['payload']
                if rid not in IDS or digest(json.dumps(payload, sort_keys=True)) != item['request_sha256']:
                    raise ValueError('Suffix request changed before call')
                try:
                    attempt = ledger.reserve(admission.RESERVE, rid)
                except ValueError as exc:
                    if 'cap reached' not in str(exc):
                        raise
                    paid.durable(journal, {'event': 'admission_stopped',
                                           'next_unsent_id': rid, 'reason': 'child_cap'})
                    return {'completed': False, 'next_unsent_id': rid,
                            'status': 'child_cap'}
                paid.durable(journal, {'event': 'request_started', 'attempt_id': attempt, 'id': rid,
                    'request_sha256': item['request_sha256'], 'reserved_cost_usd': str(admission.RESERVE)})
                row = {'id': rid, 'attempt_id': attempt, 'request_sha256': item['request_sha256'],
                       'input_sha256': item['input_sha256'],
                       'policy_sha256': item['instruction_sha256'], 'request': payload,
                       'reference_labels_read': False, 'requested_model': admission.MODEL,
                       'reasoning_effort': 'off', 'provider_endpoint': endpoint,
                       'model_catalog_entry': model, 'budget_partition_id': PARTITION,
                       'reserved_cost_usd': str(admission.RESERVE), 'retry_policy': 'none'}
                actual = None
                raw_written = False
                try:
                    row['client_request_started_utc'] = datetime.now(timezone.utc).isoformat()
                    started = time.monotonic()
                    try:
                        body = paid.fetch('/chat/completions', token, payload, 300)
                    finally:
                        row['client_http_duration_seconds'] = time.monotonic() - started
                        row['client_request_finished_utc'] = datetime.now(timezone.utc).isoformat()
                    encoded = json.dumps(body).replace(token, '[REDACTED]')
                    if len(encoded.encode()) > MAX_RAW:
                        raise ValueError('Response exceeds raw capture bound')
                    body = json.loads(encoded)
                    paid.durable(raw, {'attempt_id': attempt, 'id': rid, 'body': body})
                    raw_written = True
                    paid.durable(journal, {'event': 'raw_saved', 'attempt_id': attempt,
                                           'raw_sha256': sha(target['raw'])})
                    row['raw_response'] = body
                    usage = body.get('usage') or {}
                    row['usage'] = usage
                    if usage.get('cost') is not None:
                        actual = paid.number(usage['cost'])
                    choices = body.get('choices') or []
                    choice = choices[0] if len(choices) == 1 else {}
                    message = choice.get('message') or {}
                    try:
                        prediction = json.loads(message.get('content'))
                    except (TypeError, ValueError):
                        prediction = None
                    row.update(prediction=prediction, returned_model=body.get('model'),
                               returned_provider=body.get('provider'),
                               finish_reason=choice.get('finish_reason'))
                    row['status'] = ('ok' if valid(prediction) and len(choices) == 1 and
                                     choice.get('finish_reason') == 'stop' and
                                     not body.get('error') and not choice.get('error') and
                                     not message.get('refusal') and not message.get('tool_calls') and
                                     not message.get('function_call') else 'invalid_output')
                    if body.get('model') not in allowed_returned_models(admission.MODEL, endpoint):
                        row['status'] = 'model_mismatch'
                    if body.get('provider') != endpoint['provider_name']:
                        row['status'] = 'provider_mismatch'
                except Exception as exc:
                    if 'status' not in row:
                        row.update(status='service_error', error_type=type(exc).__name__)
                        if hasattr(exc, 'code'):
                            row['http_status'] = exc.code
                        if not raw_written:
                            sidecar = {'attempt_id': attempt, 'id': rid,
                                       'transport_error': type(exc).__name__}
                            if hasattr(exc, 'read'):
                                try:
                                    error_bytes = exc.read(1_000_001)
                                    sidecar['error_body'] = error_bytes[:1_000_000].decode(errors='replace').replace(token, '[REDACTED]')
                                    sidecar['body_truncated_at_limit'] = len(error_bytes) > 1_000_000
                                    row['raw_error_response'] = sidecar['error_body']
                                except Exception:
                                    sidecar['read_error'] = 'error_body_unavailable'
                            if hasattr(exc, 'code'):
                                sidecar['http_status'] = exc.code
                            paid.durable(raw, sidecar)
                            raw_written = True
                            paid.durable(journal, {'event': 'raw_saved', 'attempt_id': attempt,
                                                   'raw_sha256': sha(target['raw'])})
                billing_ok = ledger.settle(attempt, actual)
                if actual is not None and not billing_ok:
                    row['status'] = 'billing_blocked'
                row.update(observed_cost_usd=str(actual) if actual is not None else None,
                           cost_unknown=actual is None, billing_ok=billing_ok)
                paid.durable(records, row)
                paid.durable(journal, {'event': 'request_finished', 'attempt_id': attempt,
                    'id': rid, 'status': row['status'], 'billing_ok': billing_ok})
                if row['status'] != 'ok' or actual is None or not billing_ok:
                    paid.durable(journal, {'event': 'suffix_stopped', 'id': rid, 'reason': row['status']})
                    return {'completed': False, 'stopped_id': rid, 'status': row['status']}
            paid.durable(journal, {'event': 'suffix_completed', 'count': len(IDS)})
            return {'completed': True, 'count': len(IDS)}
    finally:
        ledger.close()


def project(row):
    """Allowlist fields only; neither provider bodies nor error text can escape."""
    result = {key: row.get(key) for key in ('id', 'status', 'request_sha256',
            'prediction', 'observed_cost_usd', 'cost_unknown', 'billing_ok',
            'client_http_duration_seconds', 'client_request_started_utc',
            'client_request_finished_utc')}
    if type(row.get('http_status')) is int and 100 <= row['http_status'] <= 599:
        result['http_status'] = row['http_status']
    result['unknown_charge_upper_bound_usd'] = (row.get('reserved_cost_usd')
        if row.get('cost_unknown') is True else None)
    usage = row.get('usage') or {}
    if isinstance(usage, dict):
        result['usage'] = {key: value for key in ('prompt_tokens', 'completion_tokens',
            'total_tokens', 'cached_tokens', 'reasoning_tokens')
            if (value := usage.get(key)) is not None and type(value) in (int, float)
            and math.isfinite(value) and value >= 0}
    return result


def expected_body_status(body, endpoint):
    if not isinstance(body, dict):
        return 'service_error', None, None
    usage = body.get('usage') or {}
    if not isinstance(usage, dict):
        return 'service_error', None, None
    try:
        actual = str(paid.number(usage['cost'])) if usage.get('cost') is not None else None
    except ValueError:
        return 'service_error', None, None
    choices = body.get('choices') or []
    choice = choices[0] if isinstance(choices, list) and len(choices) == 1 else {}
    message = choice.get('message') or {}
    try:
        prediction = json.loads(message.get('content'))
    except (TypeError, ValueError):
        prediction = None
    status = ('ok' if valid(prediction) and len(choices) == 1 and
              choice.get('finish_reason') == 'stop' and not body.get('error') and
              not choice.get('error') and not message.get('refusal') and
              not message.get('tool_calls') and not message.get('function_call')
              else 'invalid_output')
    if body.get('model') not in allowed_returned_models(admission.MODEL, endpoint):
        status = 'model_mismatch'
    if body.get('provider') != endpoint['provider_name']:
        status = 'provider_mismatch'
    return status, prediction, actual


def reconcile(manifest_path, manifest_sha):
    manifest = validate_manifest(manifest_path, manifest_sha)
    source = manifest['sources']
    original_rows = rows(read_bound(source['development_records']))
    target = files()
    evidence = {name: value for name, value in source.items() if name.startswith(('smoke_', 'development_'))}
    ledger_path = BASE / f'budget-{PARTITION}.jsonl'
    ledger = rows(ledger_path)
    prefix = manifest['child_ledger_prefix']
    raw_lines = ledger_path.read_bytes().splitlines(keepends=True)
    if (len(ledger) < prefix['event_count'] or
            hashlib.sha256(b''.join(raw_lines[:prefix['event_count']])).hexdigest() != prefix['sha256']):
        raise ValueError('Original budget prefix changed')
    original_known = sum((paid.number(row['observed_cost_usd']) for row in
                          rows(read_bound(source['smoke_records'])) + original_rows
                          if row.get('observed_cost_usd') is not None), paid.number('0'))
    known, unknown, pending_bound = original_known, admission.RESERVE, paid.number('0')
    if not target['claim'].exists():
        if any(target[name].exists() for name in ('journal', 'raw', 'records')):
            raise ValueError('Suffix evidence without claim')
        suffix_rows, status = [], 'not_started'
    else:
        if not all(path.exists() for path in target.values()):
            raise ValueError('Suffix claim with missing evidence')
        claim = json.loads(target['claim'].read_text())
        review_path = SUFFIX / 'root-review.json'
        if (not review_path.exists() or
                claim.get('schema') != SCHEMA + '-claim' or
                claim.get('manifest_sha256') != manifest_sha or
                claim.get('budget_manifest_sha256') != source['budget_manifest']['sha256'] or
                claim.get('partition_id') != PARTITION or claim.get('request_ids') != IDS or
                claim.get('review_sha256') != sha(review_path)):
            raise ValueError('Suffix claim differs')
        validate_review(review_path, manifest_sha, manifest,
                        read_bound(source['budget_manifest']))
        journal, raw, suffix_rows = [rows(target[part]) for part in ('journal', 'raw', 'records')]
        if (not journal or journal[0] !=
                {'event': 'suffix_claimed', 'claim_sha256': sha(target['claim'])}):
            raise ValueError('Suffix journal claim differs')
        if ([row.get('id') for row in suffix_rows] != IDS[:len(suffix_rows)] or
                len(raw) != len(suffix_rows) or
                len(journal) != 3 * len(suffix_rows) + 2):
            raise ValueError('Suffix attempts or raw evidence incomplete')
        raw_bytes = target['raw'].read_bytes().splitlines(keepends=True)
        seen = set()
        for index, row in enumerate(suffix_rows):
            item = manifest['requests'][index]
            attempt = row.get('attempt_id')
            started, saved, ended = journal[1 + 3 * index:4 + 3 * index]
            sidecar = raw[index]
            if (not isinstance(attempt, str) or not attempt or attempt in seen or
                    row.get('id') != item['id'] or row.get('request') != item['payload'] or
                    row.get('request_sha256') != item['request_sha256'] or
                    row.get('input_sha256') != item['input_sha256'] or
                    row.get('policy_sha256') != item['instruction_sha256'] or
                    row.get('reference_labels_read') is not False or
                    row.get('requested_model') != admission.MODEL or
                    row.get('reasoning_effort') != 'off' or
                    row.get('provider_endpoint', {}).get('tag') != admission.PROVIDER or
                    row.get('budget_partition_id') != PARTITION or
                    row.get('reserved_cost_usd') != str(admission.RESERVE) or
                    started != {'event': 'request_started', 'attempt_id': attempt,
                                'id': item['id'], 'request_sha256': item['request_sha256'],
                                'reserved_cost_usd': str(admission.RESERVE)} or
                    saved != {'event': 'raw_saved', 'attempt_id': attempt,
                              'raw_sha256': hashlib.sha256(b''.join(raw_bytes[:index + 1])).hexdigest()} or
                    ended != {'event': 'request_finished', 'attempt_id': attempt,
                              'id': item['id'], 'status': row.get('status'),
                              'billing_ok': row.get('billing_ok')} or
                    sidecar.get('attempt_id') != attempt or sidecar.get('id') != item['id']):
                raise ValueError('Suffix request, journal or raw attribution differs')
            seen.add(attempt)
            try:
                start = datetime.fromisoformat(row['client_request_started_utc'])
                end = datetime.fromisoformat(row['client_request_finished_utc'])
                elapsed = row['client_http_duration_seconds']
                if (start.utcoffset() != timezone.utc.utcoffset(None) or
                        end.utcoffset() != timezone.utc.utcoffset(None) or end < start or
                        type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0):
                    raise ValueError('Suffix client timing differs')
            except (KeyError, TypeError):
                raise ValueError('Suffix client timing absent') from None
            if 'body' in sidecar:
                body = sidecar['body']
                expected_status, prediction, actual = expected_body_status(body, row['provider_endpoint'])
                expected_record_status = ('billing_blocked' if actual is not None and
                                          row.get('billing_ok') is False else expected_status)
                if (row.get('raw_response') != body or
                        row.get('usage') != (body.get('usage') if isinstance(body, dict) else None) or
                        row.get('status') != expected_record_status or
                        row.get('prediction') != prediction or
                        row.get('returned_model') != (body.get('model') if isinstance(body, dict) else None) or
                        row.get('returned_provider') != (body.get('provider') if isinstance(body, dict) else None) or
                        row.get('observed_cost_usd') != actual):
                    raise ValueError('Suffix parsed result differs from saved body')
            else:
                actual = None
                if (row.get('status') != 'service_error' or
                        row.get('observed_cost_usd') is not None or
                        sidecar.get('error_body') != row.get('raw_error_response') or
                        not sidecar.get('transport_error')):
                    raise ValueError('Suffix service error differs from saved raw evidence')
                if (sidecar.get('http_status') != row.get('http_status') or
                        (row.get('http_status') is not None and
                         (type(row['http_status']) is not int or
                          not 400 <= row['http_status'] <= 599))):
                    raise ValueError('Suffix HTTP status differs')
            if (row.get('cost_unknown') is not (actual is None) or
                    (actual is None and row.get('billing_ok') is not False) or
                    (actual is not None and type(row.get('billing_ok')) is not bool)):
                raise ValueError('Suffix billing state differs')
            charges = [event for event in ledger[prefix['event_count']:] if event.get('attempt_id') == attempt]
            reserve = {'event': 'reserve', 'attempt_id': attempt, 'record_id': item['id'],
                       'usd': str(admission.RESERVE)}
            if actual is not None:
                if charges != [reserve, {'event': 'settle', 'attempt_id': attempt, 'usd': actual}]:
                    raise ValueError('Suffix known settlement differs')
                settlement_index = next(i for i, event in enumerate(ledger)
                    if event.get('event') == 'settle' and event.get('attempt_id') == attempt)
                blocked_after = (settlement_index + 1 < len(ledger) and
                    ledger[settlement_index + 1].get('event') == 'blocked' and
                    ledger[settlement_index + 1].get('reason') == 'Actual cost exceeds reserved bound')
                if row['billing_ok'] is blocked_after:
                    raise ValueError('Suffix billing block differs from ledger')
                known += paid.number(actual)
            elif len(charges) == 1 and charges[0] == reserve:
                pending_bound += admission.RESERVE
            elif (len(charges) == 2 and charges[0] == reserve and
                  charges[1].get('event') == 'unknown_cost_accounted_as_upper_bound' and
                  charges[1].get('attempt_id') == attempt and
                  charges[1].get('usd') == str(admission.RESERVE) and
                  charges[1].get('actual_cost_usd') is None and
                  charges[1].get('evidence_sha256') == sha(target['records']) and
                  Path(charges[1].get('evidence_path', '')).resolve() == target['records'].resolve()):
                unknown += admission.RESERVE
            else:
                raise ValueError('Suffix unknown charge or reserve differs')
        if (journal[-1] == {'event': 'suffix_completed', 'count': len(IDS)} and
                len(suffix_rows) == len(IDS) and
                all(row['status'] == 'ok' and row['billing_ok'] for row in suffix_rows)):
            status = 'closed_with_service_error'
        elif (len(suffix_rows) < len(IDS) and
              journal[-1] == {'event': 'admission_stopped',
                  'next_unsent_id': IDS[len(suffix_rows)], 'reason': 'child_cap'} and
              all(row['status'] == 'ok' and row['billing_ok'] for row in suffix_rows)):
            status = 'admission_stopped'
        elif (suffix_rows and journal[-1] == {'event': 'suffix_stopped',
                'id': suffix_rows[-1]['id'], 'reason': suffix_rows[-1]['status']} and
              all(row['status'] == 'ok' and row['billing_ok'] for row in suffix_rows[:-1])):
            status = 'stopped'
        else:
            raise ValueError('Suffix terminal journal differs or delivery is ambiguous')
        evidence.update({name: binding(path) for name, path in target.items()})
        evidence['review'] = binding(review_path)
    indexed = {row['id']: row for row in original_rows + suffix_rows}
    positions = [project(indexed[rid]) if rid in indexed else {'id': rid, 'status': 'never_sent'}
                 for rid in ALL_IDS]
    if [p['status'] for p in positions[:6]] != ['ok'] * 5 + ['service_error']:
        raise ValueError('Original failed position changed')
    observed_valid = sum(p['status'] == 'ok' for p in positions)
    return {'schema': SCHEMA + '-reconciliation', 'configuration': admission.CONFIG,
            'phase': 'fresh1/P0', 'status': status, 'denominator': 60,
            'valid': observed_valid if status == 'closed_with_service_error' else None,
            'observed_valid_positions': observed_valid,
            'status_counts': {name: sum(p['status'] == name for p in positions)
                              for name in sorted({p['status'] for p in positions})},
            'positions': positions, 'original_manifest_sha256': source['manifest']['sha256'],
            'suffix_manifest_sha256': manifest_sha, 'evidence': evidence,
            'known_actual_usd': str(known), 'unknown_charge_upper_bound_usd': str(unknown),
            'pending_unknown_reserve_usd': str(pending_bound),
            'private_evidence_note': 'Raw and original records remain local; hashes bind them but this projection cannot independently reproduce private bytes.',
            'strict_complete_pass': False, 'historical_failed_id': 'DEV-006'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    f = sub.add_parser('freeze')
    f.add_argument('--manifest', required=True)
    v = sub.add_parser('validate')
    v.add_argument('--manifest', required=True); v.add_argument('--sha256', required=True)
    e = sub.add_parser('execute')
    for flag in ('manifest', 'sha256', 'review', 'budget'):
        e.add_argument('--' + flag, required=True)
    e.add_argument('--env-file')
    r = sub.add_parser('reconcile')
    r.add_argument('--manifest', required=True); r.add_argument('--sha256', required=True)
    r.add_argument('--output')
    args = parser.parse_args()
    if args.command == 'freeze':
        freeze(args.manifest)
        print(json.dumps({'manifest_sha256': sha(args.manifest), 'request_count': len(IDS)}))
    elif args.command == 'validate':
        validate_manifest(args.manifest, args.sha256)
        print(json.dumps({'validated': True}))
    elif args.command == 'execute':
        print(json.dumps(execute(args.manifest, args.sha256, args.review, args.budget, args.env_file)))
    else:
        result = reconcile(args.manifest, args.sha256)
        if args.output:
            original.atomic_json(args.output, result)
        print(json.dumps({'status': result['status'], 'valid': result['valid'],
                          'denominator': result['denominator']}))


if __name__ == '__main__':
    main()
