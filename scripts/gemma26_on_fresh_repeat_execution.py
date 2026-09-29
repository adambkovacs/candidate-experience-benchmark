#!/usr/bin/env python3
"""Reviewed-entrypoint candidate for the distinct Gemma 26 on fresh matched-three plans."""
import argparse
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.error
from urllib.parse import quote

import gemma26_on_fresh_repeat_study as study
import openrouter_paid_benchmark as paid
import paid_budget_partitions_v2 as partitions
from prompt_admission import audit_response

ROOT = study.ROOT
MASTER = ROOT / 'results/openrouter-paid-budget.jsonl'
HOSTED_EXECUTION = ROOT / 'results/prompt-comparison-v1-2026-09-24/hosted-execution.json'
RECEIPT_SCHEMA = 'gemma26-on-fresh-matched3-root-review-v1'
# The saved Gemma 26 configuration has continue_on_invalid_output=false.
# Every intrinsic invalid remains recorded, and this lane stops before the
# next record. Other lanes may need a different explicitly frozen policy.
CONTINUE_INTRINSIC_INVALID = False


def utc():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def durable(file, value):
    paid.durable(file, value)


def bound_file(spec):
    path = (ROOT / spec['path']).resolve()
    path.relative_to(ROOT.resolve())
    if study.sha(path) != spec['sha256']:
        raise ValueError('Bound file changed: ' + spec['path'])
    return path


def review_receipt(path, repeat, condition, phase, manifest_sha):
    receipt = json.loads(Path(path).read_text())
    if receipt.get('schema') != RECEIPT_SCHEMA or receipt.get('approved') is not True:
        raise ValueError('Root review receipt missing approval')
    if receipt.get('configuration_id') != study.CONFIG or receipt.get('partition_cap_usd') != str(study.PROPOSED_CHILD_USD):
        raise ValueError('Root review configuration or cap differs')
    if receipt.get('stage') != f'{repeat}/{condition}/{phase}':
        raise ValueError('Root review stage differs')
    if receipt.get('controller_sha256') != study.sha(__file__):
        raise ValueError('Root review controller hash differs')
    if receipt.get('hosted_execution_sha256') != study.sha(HOSTED_EXECUTION):
        raise ValueError('Root review historical execution policy hash differs')
    historical = json.loads(HOSTED_EXECUTION.read_text())
    policies = [x for x in historical['configurations'] if x['id'] == study.CONFIG]
    if len(policies) != 1 or policies[0]['continue_on_invalid_output'] is not CONTINUE_INTRINSIC_INVALID:
        raise ValueError('Frozen invalid-output continuation policy changed')
    expected = {}
    for fresh_pass in study.ORDERS:
        manifest_path = study.BASE / fresh_pass / 'manifest.json'
        digest = study.sha(manifest_path)
        study.verify(fresh_pass, digest)
        expected[fresh_pass] = digest
    if receipt.get('plan_sha256') != expected or expected[repeat] != manifest_sha:
        raise ValueError('Root review plan hashes differ')
    if receipt.get('master_ledger') != str(MASTER):
        raise ValueError('Root review master ledger differs')
    partition = receipt.get('budget_manifest')
    if not isinstance(partition, dict):
        raise ValueError('Root review budget manifest missing')
    path = bound_file(partition)
    if not receipt.get('partition_id'):
        raise ValueError('Root review partition ID missing')
    return receipt, path


def phase_paths(repeat, condition, phase):
    folder = study.BASE / repeat / condition
    return folder, folder / (phase + '.claim.json'), folder / (phase + '.journal.jsonl'), folder / (phase + '.attempts.jsonl')


def jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def verify_phase_closure(plan, condition, phase):
    fresh_pass = plan['fresh_pass']
    manifest_path = study.BASE / fresh_pass / 'manifest.json'
    manifest_sha = study.sha(manifest_path)
    study.verify(fresh_pass, manifest_sha)
    requests = plan['conditions'][condition][phase]
    folder, claim, journal_path, attempts_path = phase_paths(fresh_pass, condition, phase)
    raw_path = folder / (phase + '.responses.jsonl')
    for path in (claim, journal_path, attempts_path, raw_path):
        if not path.is_file():
            raise ValueError('Phase closure evidence missing: ' + path.name)
    claim_data = json.loads(claim.read_text())
    if (claim_data.get('fresh_pass'), claim_data.get('condition'), claim_data.get('phase'),
            claim_data.get('manifest_sha256')) != (fresh_pass, condition, phase, manifest_sha):
        raise ValueError('Phase claim does not bind frozen predecessor manifest')
    attempts, raw, events = jsonl(attempts_path), jsonl(raw_path), jsonl(journal_path)
    expected_ids = [r['record_id'] for r in requests]
    if [r.get('id') for r in attempts] != expected_ids or len(attempts) != len(requests):
        raise ValueError('Attempt rows do not match exact ordered frozen request list')
    if [r.get('id') for r in raw] != expected_ids or len(raw) != len(requests):
        raise ValueError('Raw response rows do not match exact ordered frozen request list')
    attempt_ids = [r.get('attempt_id') for r in attempts]
    if any(not isinstance(x, str) or not x for x in attempt_ids) or len(set(attempt_ids)) != len(attempt_ids):
        raise ValueError('Attempt IDs are missing or duplicated')
    for request, record, raw_record in zip(requests, attempts, raw):
        if (record.get('fresh_pass'), record.get('condition'), record.get('phase'),
                record.get('manifest_sha256'), record.get('request_sha256')) != (
                fresh_pass, condition, phase, manifest_sha, request['request_sha256']):
            raise ValueError('Attempt row differs from frozen request or manifest')
        if (study.digest(json.dumps(record.get('request'), sort_keys=True)) != request['request_sha256'] or
                record.get('status') != 'ok' or record.get('billing_ok') is not True or
                record.get('cost_unknown') is not False or record.get('observed_cost_usd') is None):
            raise ValueError('Attempt is not a known-billed valid outcome')
        if not isinstance(record.get('raw_response'), dict):
            raise ValueError('Successful attempt is missing its raw response object')
        if not isinstance(record.get('raw_response'), dict):
            raise ValueError('Successful attempt is missing its raw response object')
        actual_cost = paid.number(record['observed_cost_usd'])
        reserved_cost = paid.number(record.get('reserved_cost_usd'))
        if actual_cost < 0 or actual_cost > reserved_cost:
            raise ValueError('Observed charge exceeds or violates its recorded reservation')
        if (raw_record.get('attempt_id'), raw_record.get('request_sha256'), raw_record.get('raw_response')) != (
                record['attempt_id'], request['request_sha256'], record.get('raw_response')):
            raise ValueError('Raw response evidence differs from attempt row')
    expected_events = [{'event': 'phase_started', 'fresh_pass': fresh_pass,
                        'condition': condition, 'phase': phase}]
    for request, record in zip(requests, attempts):
        expected_events.extend([
            {'event': 'request_intent', 'id': request['record_id'],
             'request_sha256': request['request_sha256']},
            {'event': 'request_started', 'id': request['record_id'],
             'attempt_id': record['attempt_id'], 'request_sha256': request['request_sha256']},
            {'event': 'request_finished', 'id': request['record_id'],
             'attempt_id': record['attempt_id'], 'status': 'ok',
             'billing_ok': True, 'cost_unknown': False,
             'observed_cost_usd': record['observed_cost_usd']},
        ])
    expected_events.append({'event': 'phase_completed', 'fresh_pass': fresh_pass,
                            'condition': condition, 'phase': phase,
                            'request_count': len(requests), 'attempt_ids': attempt_ids})
    if len(events) != len(expected_events):
        raise ValueError('Journal event count differs from exact phase lifecycle')
    for actual, expected in zip(events, expected_events):
        if any(actual.get(key) != value for key, value in expected.items()):
            raise ValueError('Journal order, attempt binding, or terminal receipt differs')
    return {'manifest_sha256': manifest_sha, 'journal_sha256': study.sha(journal_path),
            'attempts_sha256': study.sha(attempts_path), 'responses_sha256': study.sha(raw_path)}


def require_order(plan, condition, phase):
    if condition not in plan['condition_order']:
        raise ValueError('Condition outside frozen order')
    pass_index = list(study.ORDERS).index(plan['fresh_pass'])
    for earlier in list(study.ORDERS)[:pass_index]:
        earlier_path = study.BASE / earlier / 'manifest.json'
        try:
            earlier_sha = study.sha(earlier_path)
            earlier_plan = study.verify(earlier, earlier_sha)
            for prior_condition in study.ORDERS[earlier]:
                verify_phase_closure(earlier_plan, prior_condition, 'development')
        except (OSError, ValueError) as exc:
            raise ValueError('Earlier fresh pass incomplete: ' + earlier) from exc
    for prior in plan['condition_order'][:plan['condition_order'].index(condition)]:
        verify_phase_closure(plan, prior, 'development')
    if phase == 'development':
        folder, _, _, _ = phase_paths(plan['fresh_pass'], condition, 'smoke')
        receipt = folder / 'smoke-inspection.json'
        if not receipt.exists():
            raise ValueError('Inspected smoke required')
        inspection = json.loads(receipt.read_text())
        _, _, journal, attempts = phase_paths(plan['fresh_pass'], condition, 'smoke')
        bindings = verify_phase_closure(plan, condition, 'smoke')
        if (inspection.get('decision') != 'accepted_unchanged' or
                inspection.get('manifest_sha256') != bindings['manifest_sha256'] or
                inspection.get('journal_sha256') != study.sha(journal) or
                inspection.get('attempts_sha256') != study.sha(attempts) or
                inspection.get('responses_sha256') != study.sha(folder / 'smoke.responses.jsonl')):
            raise ValueError('Smoke inspection binding changed')


def live_controls(plan, condition):
    catalog = paid.fetch('/models', timeout=120)
    endpoints = paid.fetch('/models/' + quote(study.MODEL, safe='/') + '/endpoints', timeout=120)
    model, endpoint = paid.select_endpoint(study.MODEL, study.PROVIDER, catalog, endpoints,
                                           study.INPUT_PRICE, study.OUTPUT_PRICE)
    if endpoint.get('quantization') != 'fp8' or endpoint.get('provider_name') != 'DeepInfra':
        raise ValueError('Live endpoint identity differs')
    if endpoint['context_length'] != study.CONTEXT:
        raise ValueError('Live endpoint context differs from reviewed reserve')
    for key, rate in (('prompt', study.INPUT_PRICE), ('completion', study.OUTPUT_PRICE)):
        if paid.number(endpoint['pricing'][key]) != rate / paid.MILLION:
            raise ValueError('Live endpoint price differs from reviewed rate')
    reserve = paid.reservation(endpoint, 4096, study.INPUT_PRICE, study.OUTPUT_PRICE)
    if reserve != Decimal('0.01974272') or reserve > study.PROPOSED_CHILD_USD:
        raise ValueError('Live reserve differs from reviewed amount')
    inputs = {x['id']: x['feedback'] for x in paid.read_rows(ROOT / 'data/pilot/inputs.jsonl')}
    for request in plan['conditions'][condition]['development']:
        payload = request['payload']
        rebuilt = paid.make_payload(study.MODEL, endpoint, inputs[request['record_id']],
                                    payload['messages'][0]['content'],
                                    payload['response_format']['json_schema']['schema'],
                                    study.EFFORT, 4096, study.INPUT_PRICE, study.OUTPUT_PRICE, model)
        if rebuilt != payload:
            raise ValueError('Live adapter would change frozen payload')
    return model, endpoint, reserve


def budget_gate(receipt, budget_path):
    ledger = partitions.open_partition(MASTER, budget_path, receipt['partition_id'],
                                       study.MODEL, study.PROVIDER, study.EFFORT)
    if ledger.cap != paid.number(str(study.PROPOSED_CHILD_USD)):
        ledger.close()
        raise ValueError('Child partition cap differs')
    return ledger


def classify(body, model, endpoint):
    record = {'raw_response': body, 'returned_model': body.get('model'),
              'returned_provider': body.get('provider'), 'usage': body.get('usage') or {}}
    choices = body.get('choices')
    if not isinstance(choices, list) or len(choices) != 1:
        record.update(status='control_violation', prediction=None)
        return record
    choice = choices[0]
    message = choice.get('message') or {}
    record['finish_reason'] = choice.get('finish_reason')
    try:
        prediction = json.loads(message.get('content'))
    except (ValueError, TypeError):
        prediction = None
    record['prediction'] = prediction
    record['status'] = ('ok' if paid.valid(prediction) and choice.get('finish_reason') == 'stop'
                        and not message.get('refusal') and not message.get('tool_calls')
                        and not message.get('function_call') and not choice.get('error') else 'invalid_output')
    if body.get('model') not in paid.allowed_returned_models(study.MODEL, endpoint):
        record['status'] = 'model_mismatch'
    if body.get('provider') != endpoint['provider_name']:
        record['status'] = 'provider_mismatch'
    return record


def continue_record(record, phase):
    """Continue known-billing intrinsic invalids only during development."""
    if not record.get('billing_ok') or record.get('cost_unknown'):
        return False
    if record['status'] == 'ok':
        return record.get('response_diagnostic', {}).get('passed') is True
    if phase != 'development' or not CONTINUE_INTRINSIC_INVALID or record['status'] != 'invalid_output':
        return False
    choices = (record.get('raw_response') or {}).get('choices') or []
    if len(choices) != 1:
        return False
    choice = choices[0]
    message = choice.get('message') or {}
    blockers = set(record.get('response_diagnostic', {}).get('blockers', []))
    return (choice.get('finish_reason') in ('stop', 'length') and not choice.get('error')
            and not any(message.get(k) for k in ('refusal', 'tool_calls', 'function_call'))
            and blockers <= {'truncation:length'})


def inspect(repeat, condition, manifest_sha, note):
    plan = study.verify(repeat, manifest_sha)
    require_order(plan, condition, 'smoke')
    folder, _, journal, attempts = phase_paths(repeat, condition, 'smoke')
    raw_path = folder / 'smoke.responses.jsonl'
    receipt = folder / 'smoke-inspection.json'
    if receipt.exists():
        raise ValueError('Fresh completed smoke required')
    bindings = verify_phase_closure(plan, condition, 'smoke')
    rows = jsonl(attempts)
    raw_rows = jsonl(raw_path)
    if len(rows) != 3 or [r['id'] for r in rows] != ['DEV-001', 'DEV-002', 'DEV-003']:
        raise ValueError('Smoke must contain exactly three ordered calls')
    if not all(r['status'] == 'ok' and r['billing_ok'] and not r['cost_unknown'] for r in rows):
        raise ValueError('Three valid, billed smoke calls required')
    if len({r['attempt_id'] for r in rows}) != 3 or [r['attempt_id'] for r in raw_rows] != [r['attempt_id'] for r in rows]:
        raise ValueError('Smoke raw responses do not bind three distinct attempts')
    if not note.strip():
        raise ValueError('Inspection note required')
    value = {'schema': 'openrouter-repeat-smoke-inspection-v1', 'fresh_pass': repeat,
             'condition': condition, 'decision': 'accepted_unchanged', 'note': note,
             'manifest_sha256': bindings['manifest_sha256'],
             'journal_sha256': study.sha(journal), 'attempts_sha256': study.sha(attempts),
             'responses_sha256': study.sha(raw_path)}
    with receipt.open('x') as out:
        json.dump(value, out, indent=2)
        out.write('\n')
        out.flush(); os.fsync(out.fileno())
    return value


def execute(repeat, condition, phase, manifest_sha, review_path, env_file=None):
    if phase not in ('smoke', 'development'):
        raise ValueError('Unknown phase')
    plan = study.verify(repeat, manifest_sha)
    require_order(plan, condition, phase)
    folder, claim, journal, attempts = phase_paths(repeat, condition, phase)
    responses = folder / (phase + '.responses.jsonl')
    if any(p.exists() for p in (claim, journal, attempts, responses)):
        raise FileExistsError('Phase already claimed; no implicit retry')
    receipt, budget_path = review_receipt(review_path, repeat, condition, phase, manifest_sha)
    model, endpoint, reserve = live_controls(plan, condition)
    ledger = budget_gate(receipt, budget_path)
    try:
        token = paid.load_key(env_file)
        folder.mkdir(parents=True, exist_ok=True)
        with claim.open('x') as out:
            durable(out, {'fresh_pass': repeat, 'condition': condition, 'phase': phase,
                          'manifest_sha256': manifest_sha, 'root_review_sha256': study.sha(review_path),
                          'claimed_utc': utc()})
        requests = plan['conditions'][condition][phase]
        complete = True
        with journal.open('x') as audit, attempts.open('x') as output, responses.open('x') as raw_output:
            durable(audit, {'event': 'phase_started', 'fresh_pass': repeat,
                            'condition': condition, 'phase': phase, 'utc': utc()})
            for request in requests:
                rid = request['record_id']
                payload = request['payload']
                durable(audit, {'event': 'request_intent', 'id': rid,
                                'request_sha256': request['request_sha256'], 'utc': utc()})
                attempt_id = ledger.reserve(reserve, rid)
                start = time.perf_counter()
                record = {'id': rid, 'fresh_pass': repeat, 'condition': condition, 'phase': phase,
                          'attempt_id': attempt_id, 'request': payload,
                          'request_sha256': request['request_sha256'],
                          'manifest_sha256': manifest_sha, 'requested_model': study.MODEL,
                          'reasoning_effort': study.EFFORT, 'provider_endpoint': endpoint,
                          'model_catalog_entry': model, 'reference_labels_read': False,
                          'reserved_cost_usd': str(reserve), 'started_utc': utc()}
                durable(audit, {'event': 'request_started', 'id': rid, 'attempt_id': attempt_id,
                                'request_sha256': request['request_sha256'], 'utc': utc()})
                actual = None
                try:
                    body = paid.fetch('/chat/completions', token, payload, 300)
                    body = json.loads(json.dumps(body).replace(token, '[REDACTED]'))
                    record['raw_response'] = body
                    durable(raw_output, {'id': rid, 'attempt_id': attempt_id,
                                         'request_sha256': request['request_sha256'],
                                         'raw_response': body, 'received_utc': utc()})
                    if isinstance(body, dict):
                        usage = body.get('usage') or {}
                        if usage.get('cost') is not None:
                            actual = paid.number(usage['cost'])
                    record.update(classify(body, model, endpoint))
                except Exception as exc:
                    record.update(status='service_error', error_type=type(exc).__name__)
                    if isinstance(exc, urllib.error.HTTPError):
                        record['http_status'] = exc.code
                        record['error_body'] = exc.read().decode('utf-8', errors='replace').replace(token, '[REDACTED]')
                        record['error_headers'] = {key: str(exc.headers[key]).replace(token, '[REDACTED]')
                                                   for key in ('x-request-id', 'request-id', 'retry-after', 'cf-ray')
                                                   if exc.headers is not None and exc.headers.get(key) is not None}
                        durable(raw_output, {'id': rid, 'attempt_id': attempt_id,
                                             'request_sha256': request['request_sha256'],
                                             'http_status': exc.code, 'error_body': record['error_body'],
                                             'error_headers': record['error_headers'], 'received_utc': utc()})
                billing_ok = ledger.settle(attempt_id, actual)
                record.update(elapsed_seconds=time.perf_counter() - start,
                              timing_boundary='Request-to-record duration includes request-start journal fsync, provider call, raw-response fsync, billing settlement and response audit; it ends before attempt-row and request-finished journal fsync.',
                              observed_cost_usd=str(actual) if actual is not None else None,
                              cost_unknown=actual is None, billing_ok=billing_ok)
                if record.get('raw_response') is not None:
                    diagnostic = audit_response(record, 'openrouter_paid_v1', endpoint['context_length'] - 4096)
                    record['response_diagnostic'] = diagnostic
                    if not diagnostic['passed'] and record['status'] == 'ok':
                        record['status'] = 'prompt_admission_failure'
                durable(output, record)
                durable(audit, {'event': 'request_finished', 'id': rid, 'attempt_id': attempt_id,
                                'status': record['status'], 'billing_ok': billing_ok,
                                'cost_unknown': record['cost_unknown'],
                                'observed_cost_usd': record['observed_cost_usd'],
                                'utc': utc()})
                if not continue_record(record, phase):
                    complete = False
                    durable(audit, {'event': 'phase_stopped', 'id': rid,
                                    'reason': record['status'], 'utc': utc()})
                    break
            if complete:
                durable(audit, {'event': 'phase_completed', 'fresh_pass': repeat,
                                'condition': condition, 'phase': phase,
                                'request_count': len(requests),
                                'attempt_ids': [json.loads(line)['attempt_id'] for line in attempts.read_text().splitlines()],
                                'utc': utc()})
        return complete
    finally:
        if journal.exists():
            lines = journal.read_text().splitlines()
            terminal = json.loads(lines[-1]).get('event') if lines else None
            if terminal not in ('phase_completed', 'phase_stopped', 'phase_aborted'):
                with journal.open('a') as audit:
                    durable(audit, {'event': 'phase_aborted', 'reason': 'exception_or_interruption',
                                    'utc': utc()})
        ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    for action in ('smoke', 'development', 'inspect'):
        p = sub.add_parser(action)
        p.add_argument('--fresh-pass', required=True, choices=tuple(study.ORDERS))
        p.add_argument('--condition', required=True, choices=('P0', 'P1', 'P2'))
        p.add_argument('--manifest-sha256', required=True)
        if action == 'inspect':
            p.add_argument('--note', required=True)
        else:
            p.add_argument('--root-review-receipt', required=True)
            p.add_argument('--env-file')
    args = parser.parse_args()
    if args.action == 'inspect':
        inspect(args.fresh_pass, args.condition, args.manifest_sha256, args.note)
    else:
        execute(args.fresh_pass, args.condition, args.action, args.manifest_sha256,
                args.root_review_receipt, args.env_file)


if __name__ == '__main__':
    main()
