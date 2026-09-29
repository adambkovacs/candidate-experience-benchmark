#!/usr/bin/env python3
"""Separate free-route Gemma executor. All attempt evidence stays outside Git."""
import argparse
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path
import time
from urllib.parse import quote
import uuid

import gemma26_free_fresh_study as study
import gemma26_on_fresh_repeat_execution as paid_execution
import openrouter_free_quota_v1 as free_quota
import openrouter_benchmark as transport
import openrouter_paid_benchmark as paid
from prompt_admission import audit_response

ROOT = study.ROOT
RECEIPT_SCHEMA = 'gemma26-free-fresh-root-review-v1'


def utc():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def durable(out, value):
    paid.durable(out, value)


def private_path(path, directory=False):
    target = Path(path).resolve()
    if target.is_relative_to(ROOT.resolve()):
        raise ValueError('Private admission/evidence must be outside the public repository')
    if not target.is_absolute() or not target.exists():
        raise ValueError('Private admission/evidence path missing')
    if target.stat().st_mode & 0o077:
        raise ValueError('Private admission/evidence permissions are too broad')
    if directory != target.is_dir():
        raise ValueError('Private admission/evidence type differs')
    return target


def review_receipt(path, fresh_pass, condition, phase, plan_sha):
    path = private_path(path)
    receipt = json.loads(path.read_text())
    if receipt.get('schema') != RECEIPT_SCHEMA or receipt.get('approved') is not True:
        raise ValueError('Root review approval missing')
    if (receipt.get('configuration_id'), receipt.get('stage'), receipt.get('controller_sha256'),
            receipt.get('tests_sha256')) != (
            study.CONFIG, f'{fresh_pass}/{condition}/{phase}', study.sha(__file__),
            study.sha(ROOT / 'tests/test_gemma26_free_fresh.py')):
        raise ValueError('Root review stage or code binding differs')
    expected = {name: study.sha(study.BASE / name / 'manifest.json') for name in study.ORDERS}
    for name, digest in expected.items():
        study.verify(name, digest)
    if receipt.get('plan_sha256') != expected or expected[fresh_pass] != plan_sha:
        raise ValueError('Root review plans differ')
    evidence = private_path(receipt.get('evidence_root'), directory=True)
    return receipt, evidence


def free_endpoint(catalog, endpoints):
    models = [x for x in catalog.get('data', []) if x.get('id') == study.MODEL]
    if len(models) != 1 or not transport.zero_price(models[0].get('pricing')):
        raise ValueError('Exactly one zero-priced :free model required')
    if models[0].get('reasoning') != {'mandatory': False, 'default_enabled': False}:
        raise ValueError('Free model reasoning metadata differs')
    if endpoints.get('data', {}).get('id') != study.MODEL:
        raise ValueError('Free endpoint model ID differs')
    candidates = [x for x in endpoints['data'].get('endpoints', []) if x.get('tag') == study.PROVIDER]
    if len(candidates) != 1:
        raise ValueError('Exactly one Google AI Studio free endpoint required')
    endpoint = candidates[0]
    if (endpoint.get('model_id'), endpoint.get('provider_name'), endpoint.get('quantization'),
            endpoint.get('status'), endpoint.get('context_length'),
            endpoint.get('max_completion_tokens')) != (
            study.MODEL, study.PROVIDER_NAME, 'unknown', 0, study.CONTEXT, 32768):
        raise ValueError('Free endpoint identity, capacity, or status differs')
    if not transport.zero_price(endpoint.get('pricing')):
        raise ValueError('Free endpoint has a nonzero or unknown listed price')
    # response_format is advertised; structured_outputs is not. This permits
    # only a separately inspected smoke, not an assumed strict-schema pass.
    required = {'reasoning', 'include_reasoning', 'response_format', 'max_tokens', 'temperature'}
    if not required <= set(endpoint.get('supported_parameters', [])):
        raise ValueError('Free endpoint lacks requested controls')
    if not study.MODEL.endswith(':free'):
        raise ValueError('Explicit free variant required')
    return models[0], endpoint


def live_controls(plan, condition):
    catalog = transport.fetch('/models', timeout=120)
    endpoints = transport.fetch('/models/' + quote(study.MODEL, safe='/') + '/endpoints', timeout=120)
    model, endpoint = free_endpoint(catalog, endpoints)
    for request in plan['conditions'][condition]['development']:
        payload = request['payload']
        if (payload.get('model') != study.MODEL or payload.get('provider') != {
                'only': [study.PROVIDER], 'allow_fallbacks': False,
                'require_parameters': True,
                'max_price': {'prompt': 0, 'completion': 0, 'request': 0, 'image': 0}} or
                payload.get('reasoning') != {'enabled': True} or
                payload.get('response_format', {}).get('type') != 'json_schema' or
                payload['response_format']['json_schema'].get('strict') is not True or
                payload.get('max_tokens') != study.MAX_TOKENS or payload.get('temperature') != 0):
            raise ValueError('Frozen payload lacks zero-price exact-route controls')
    return model, endpoint


def account_eligible(token):
    # Read-only endpoints. The private account values are never written to Git
    # or returned from this function. A remaining-request counter is unavailable.
    key = transport.fetch('/key', token=token, timeout=30).get('data', {})
    credits = transport.fetch('/credits', token=token, timeout=30).get('data', {})
    if key.get('is_free_tier') is not False or paid.number(credits.get('total_credits')) < Decimal(10):
        raise ValueError('Documented 1000/day free-model tier is not established')
    quota = key.get('free_model_daily_requests')
    if (not isinstance(quota, dict) or quota.get('limit') != 1000 or
            type(quota.get('remaining')) is not int or quota['remaining'] < 0):
        raise ValueError('Provider free-model remaining capacity unavailable')
    return quota['remaining']


def paths(evidence, fresh_pass, condition, phase):
    folder = evidence / fresh_pass / condition
    return folder, {name: folder / (phase + suffix) for name, suffix in {
        'claim': '.claim.json', 'journal': '.journal.jsonl',
        'attempts': '.attempts.jsonl', 'responses': '.responses.jsonl',
        'wire': '.wire.jsonl', 'completion': '.completion.json',
    }.items()}


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def verify_closed(evidence, fresh_pass, condition, phase):
    plan_file = study.BASE / fresh_pass / 'manifest.json'
    plan_sha = study.sha(plan_file)
    plan = study.verify(fresh_pass, plan_sha)
    expected = plan['conditions'][condition][phase]
    folder, files = paths(evidence, fresh_pass, condition, phase)
    if any(not x.is_file() for x in files.values()):
        raise ValueError('Closed phase evidence missing')
    claim = json.loads(files['claim'].read_text())
    events, attempts, raw, wire = [rows(files[k]) for k in ('journal', 'attempts', 'responses', 'wire')]
    completion = json.loads(files['completion'].read_text())
    ids = [x['record_id'] for x in expected]
    if (claim.get('plan_sha256'), claim.get('stage')) != (plan_sha, f'{fresh_pass}/{condition}/{phase}'):
        raise ValueError('Phase claim differs')
    if ([x.get('id') for x in attempts] != ids or [x.get('id') for x in raw] != ids or
            [x.get('id') for x in wire] != ids or len(set(x.get('attempt_id') for x in attempts)) != len(ids)):
        raise ValueError('Closed record membership or attempt identity differs')
    for request, record, response, captured in zip(expected, attempts, raw, wire):
        if (record.get('request_sha256') != request['request_sha256'] or
                study.historical.digest(json.dumps(record.get('request'), sort_keys=True)) != request['request_sha256'] or
                record.get('status') != 'ok' or record.get('returned_provider') != study.PROVIDER_NAME or
                record.get('cost_bound_usd') != '0' or record.get('observed_cost_usd') not in (None, '0') or
                response.get('raw_response') != record.get('raw_response') or
                response.get('attempt_id') != record.get('attempt_id') or
                captured.get('attempt_id') != record.get('attempt_id') or
                captured.get('http_status') != 200 or captured.get('body_truncated_at_limit') is not False or
                captured.get('read_error') is not None):
            raise ValueError('Closed raw/request/cost controls differ')
        import base64
        if json.loads(base64.b64decode(captured['body_base64'])) != response['raw_response']:
            raise ValueError('Raw wire bytes differ from parsed response')
    if events[0].get('event') != 'phase_started' or events[-1].get('event') != 'phase_completed':
        raise ValueError('Closed phase journal not terminal')
    if [x.get('event') for x in events] != (['phase_started'] +
            ['request_intent', 'request_started', 'request_finished'] * len(ids) + ['phase_completed']):
        raise ValueError('Closed phase lifecycle differs')
    for index, record in enumerate(attempts):
        finished = events[3 + 3 * index]
        if (events[1 + 3 * index].get('request_sha256') != expected[index]['request_sha256'] or
                events[2 + 3 * index].get('attempt_id') != record['attempt_id'] or
                finished.get('attempt_id') != record['attempt_id'] or finished.get('status') != 'ok'):
            raise ValueError('Closed lifecycle request binding differs')
    digest = {key + '_sha256': study.sha(files[key]) for key in ('journal', 'attempts', 'responses', 'wire')}
    if completion.get('plan_sha256') != plan_sha or completion.get('request_count') != len(ids) or any(
            completion.get(k) != v for k, v in digest.items()):
        raise ValueError('Completion hash or count differs')
    return digest


def require_order(evidence, plan, condition, phase):
    fresh_pass = plan['fresh_pass']
    if condition not in plan['condition_order']:
        raise ValueError('Condition outside frozen order')
    for previous_pass in list(study.ORDERS)[:list(study.ORDERS).index(fresh_pass)]:
        for previous_condition in study.ORDERS[previous_pass]:
            verify_closed(evidence, previous_pass, previous_condition, 'development')
    for previous_condition in plan['condition_order'][:plan['condition_order'].index(condition)]:
        verify_closed(evidence, fresh_pass, previous_condition, 'development')
    if phase == 'development':
        digest = verify_closed(evidence, fresh_pass, condition, 'smoke')
        folder, _ = paths(evidence, fresh_pass, condition, 'smoke')
        inspection_file = folder / 'smoke.inspection.json'
        if not inspection_file.is_file():
            raise ValueError('Inspected smoke required')
        inspection = json.loads(inspection_file.read_text())
        if inspection.get('decision') != 'accepted_unchanged' or any(
                inspection.get(k) != v for k, v in digest.items()):
            raise ValueError('Smoke inspection binding differs')


def classify(body, endpoint):
    choices = body.get('choices') if isinstance(body, dict) else None
    if not isinstance(choices, list) or len(choices) != 1:
        return {'status': 'control_violation', 'prediction': None}
    choice = choices[0]
    message = choice.get('message') or {}
    try:
        prediction = json.loads(message.get('content'))
    except (TypeError, ValueError):
        prediction = None
    status = 'ok' if (paid.valid(prediction) and choice.get('finish_reason') == 'stop' and
                      not any(message.get(k) for k in ('refusal', 'tool_calls', 'function_call')) and
                      not choice.get('error')) else 'invalid_output'
    if body.get('model') not in transport.allowed_returned_models(study.MODEL, endpoint):
        status = 'model_mismatch'
    if body.get('provider') != study.PROVIDER_NAME:
        status = 'provider_mismatch'
    return {'status': status, 'prediction': prediction, 'finish_reason': choice.get('finish_reason'),
            'returned_model': body.get('model'), 'returned_provider': body.get('provider'),
            'usage': body.get('usage')}


def inspect(evidence_root, fresh_pass, condition, plan_sha, note):
    evidence = private_path(evidence_root, directory=True)
    plan = study.verify(fresh_pass, plan_sha)
    require_order(evidence, plan, condition, 'smoke')
    digest = verify_closed(evidence, fresh_pass, condition, 'smoke')
    folder, _ = paths(evidence, fresh_pass, condition, 'smoke')
    target = folder / 'smoke.inspection.json'
    if target.exists() or not note.strip():
        raise ValueError('Fresh manual smoke inspection note required')
    with target.open('x') as out:
        json.dump({'decision': 'accepted_unchanged', 'note': note, **digest}, out)
        out.flush(); os.fsync(out.fileno())


def execute(fresh_pass, condition, phase, plan_sha, review_path, env_file=None):
    if phase not in ('smoke', 'development'):
        raise ValueError('Unknown stage')
    plan = study.verify(fresh_pass, plan_sha)
    receipt, evidence = review_receipt(review_path, fresh_pass, condition, phase, plan_sha)
    model, endpoint = live_controls(plan, condition)  # Public endpoint before credential access.
    token = transport.load_key(env_file)
    provider_remaining = account_eligible(token)  # Read-only; value stays outside saved evidence.
    old_umask = os.umask(0o077)
    try:
        lock_path = evidence / '.config.lock'
        with lock_path.open('a+') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            require_order(evidence, plan, condition, phase)
            folder, files = paths(evidence, fresh_pass, condition, phase)
            if any(path.exists() for path in files.values()):
                raise FileExistsError('Phase already claimed; no replay')
            stage_id = f'{study.SERIES}/{fresh_pass}/{condition}/{phase}'
            free_quota.admit_stage(stage_id, len(plan['conditions'][condition][phase]),
                                   provider_remaining=provider_remaining)
            folder.mkdir(parents=True, exist_ok=True, mode=0o700)
            with files['claim'].open('x') as out:
                json.dump({'stage': f'{fresh_pass}/{condition}/{phase}', 'plan_sha256': plan_sha,
                           'root_review_sha256': study.sha(review_path),
                           'controller_sha256': study.sha(__file__), 'claimed_utc': utc()}, out)
                out.flush(); os.fsync(out.fileno())
            requests = plan['conditions'][condition][phase]
            complete = True
            with files['journal'].open('x') as journal, files['attempts'].open('x') as attempts, \
                 files['responses'].open('x') as responses, files['wire'].open('x') as wire:
                durable(journal, {'event': 'phase_started', 'stage': f'{fresh_pass}/{condition}/{phase}', 'utc': utc()})
                for request in requests:
                    rid = request['record_id']
                    durable(journal, {'event': 'request_intent', 'id': rid,
                                      'request_sha256': request['request_sha256'], 'utc': utc()})
                    attempt_id = str(uuid.uuid4())
                    free_quota.start_call(stage_id, rid)
                    started = utc(); start = time.perf_counter()
                    durable(journal, {'event': 'request_started', 'id': rid, 'attempt_id': attempt_id,
                                      'request_sha256': request['request_sha256'], 'utc': started})
                    record = {'id': rid, 'attempt_id': attempt_id, 'request': request['payload'],
                              'request_sha256': request['request_sha256'], 'requested_model': study.MODEL,
                              'provider_endpoint': endpoint, 'model_catalog_entry': model,
                              'reference_labels_read': False, 'cost_bound_usd': '0',
                              'observed_cost_usd': None, 'cost_observation_status': 'not_returned',
                              'started_utc': started}
                    try:
                        body = paid_execution.fetch_captured(request['payload'], token, wire, rid,
                                                            attempt_id, request['request_sha256'])
                        record['raw_response'] = body
                        durable(responses, {'id': rid, 'attempt_id': attempt_id,
                                            'request_sha256': request['request_sha256'],
                                            'raw_response': body, 'received_utc': utc()})
                        record.update(classify(body, endpoint))
                        usage = body.get('usage') or {}
                        if usage.get('cost') is not None:
                            cost = paid.number(usage['cost'])
                            record['observed_cost_usd'] = str(cost)
                            record['cost_observation_status'] = 'returned_zero' if cost == 0 else 'returned_positive'
                            if cost != 0:
                                record['status'] = 'billing_violation'
                        diagnostic = audit_response(body, 'openrouter_paid_v1', study.CONTEXT - study.MAX_TOKENS)
                        record['response_diagnostic'] = diagnostic
                        if not diagnostic['passed']:
                            record['status'] = 'control_violation'
                    except Exception as exc:
                        record.update(status='service_error', error_type=type(exc).__name__)
                        if isinstance(exc, paid_execution.CapturedHTTPError):
                            record['http_status'] = exc.status
                    record['finished_utc'] = utc()
                    record['elapsed_seconds'] = time.perf_counter() - start
                    durable(attempts, record)
                    durable(journal, {'event': 'request_finished', 'id': rid, 'attempt_id': attempt_id,
                                      'status': record['status'], 'utc': utc()})
                    if record['status'] != 'ok':
                        complete = False
                        break
                durable(journal, {'event': 'phase_completed' if complete else 'phase_stopped',
                                  'request_count': len(rows(files['attempts'])), 'utc': utc()})
            if complete:
                digest = {key + '_sha256': study.sha(files[key]) for key in ('journal', 'attempts', 'responses', 'wire')}
                with files['completion'].open('x') as out:
                    json.dump({'stage': f'{fresh_pass}/{condition}/{phase}', 'plan_sha256': plan_sha,
                               'request_count': len(requests), **digest}, out)
                    out.flush(); os.fsync(out.fileno())
            return complete
    finally:
        os.umask(old_umask)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('run', 'inspect', 'verify-closed'))
    parser.add_argument('--pass-name', required=True, choices=tuple(study.ORDERS))
    parser.add_argument('--condition', required=True, choices=('P0', 'P1', 'P2'))
    parser.add_argument('--phase', choices=('smoke', 'development'))
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--review-receipt')
    parser.add_argument('--evidence-root')
    parser.add_argument('--env-file')
    parser.add_argument('--note')
    args = parser.parse_args()
    if args.action == 'run':
        if not args.phase or not args.review_receipt:
            parser.error('run requires --phase and --review-receipt')
        done = execute(args.pass_name, args.condition, args.phase, args.plan_sha256,
                       args.review_receipt, args.env_file)
        print('completed' if done else 'stopped')
    elif args.action == 'inspect':
        if not args.evidence_root or not args.note:
            parser.error('inspect requires --evidence-root and --note')
        inspect(args.evidence_root, args.pass_name, args.condition, args.plan_sha256, args.note)
        print('inspection recorded')
    else:
        if not args.evidence_root or not args.phase:
            parser.error('verify-closed requires --evidence-root and --phase')
        study.verify(args.pass_name, args.plan_sha256)
        verify_closed(private_path(args.evidence_root, directory=True), args.pass_name, args.condition, args.phase)
        print('closed evidence verified')


if __name__ == '__main__':
    main()
