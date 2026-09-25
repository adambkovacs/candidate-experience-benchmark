#!/usr/bin/env python3
"""Reviewed-entrypoint candidate for the frozen Gemma 26 paid repeat plans."""
import argparse
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.error
from urllib.parse import quote

import openrouter_repeat_study as study
import openrouter_paid_benchmark as paid
import paid_budget_partitions_v2 as partitions
from prompt_admission import audit_response

ROOT = study.ROOT
MASTER = ROOT / 'results/openrouter-paid-budget.jsonl'
HOSTED_EXECUTION = ROOT / 'results/prompt-comparison-v1-2026-09-24/hosted-execution.json'
RECEIPT_SCHEMA = 'openrouter-repeat-root-review-v1'
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


def review_receipt(path, repeat, manifest_sha):
    receipt = json.loads(Path(path).read_text())
    if receipt.get('schema') != RECEIPT_SCHEMA or receipt.get('approved') is not True:
        raise ValueError('Root review receipt missing approval')
    if receipt.get('configuration_id') != study.CONFIG or receipt.get('partition_cap_usd') != study.CAP_USD:
        raise ValueError('Root review configuration or cap differs')
    if receipt.get('controller_sha256') != study.sha(__file__):
        raise ValueError('Root review controller hash differs')
    if receipt.get('hosted_execution_sha256') != study.sha(HOSTED_EXECUTION):
        raise ValueError('Root review original execution policy hash differs')
    historical = json.loads(HOSTED_EXECUTION.read_text())
    policies = [x for x in historical['configurations'] if x['id'] == study.CONFIG]
    if len(policies) != 1 or policies[0]['continue_on_invalid_output'] is not CONTINUE_INTRINSIC_INVALID:
        raise ValueError('Frozen invalid-output continuation policy changed')
    expected = {r: study.sha(study.BASE / r / 'manifest.json') for r in study.ORDERS}
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


def complete_journal(repeat, condition, phase):
    _, _, journal, _ = phase_paths(repeat, condition, phase)
    if not journal.exists():
        return False
    lines = journal.read_text().splitlines()
    return bool(lines) and json.loads(lines[-1]).get('event') == 'phase_completed'


def require_order(plan, condition, phase):
    if condition not in plan['condition_order']:
        raise ValueError('Condition outside frozen order')
    if plan['repeat'] == 'repeat3' and not all(complete_journal('repeat2', c, 'development') for c in study.ORDERS['repeat2']):
        raise ValueError('Repeat two incomplete')
    for prior in plan['condition_order'][:plan['condition_order'].index(condition)]:
        if not complete_journal(plan['repeat'], prior, 'development'):
            raise ValueError('Prior condition incomplete: ' + prior)
    if phase == 'development':
        folder, _, _, _ = phase_paths(plan['repeat'], condition, 'smoke')
        receipt = folder / 'smoke-inspection.json'
        if not receipt.exists():
            raise ValueError('Inspected smoke required')
        inspection = json.loads(receipt.read_text())
        _, _, journal, attempts = phase_paths(plan['repeat'], condition, 'smoke')
        if (inspection.get('decision') != 'accepted_unchanged' or
                inspection.get('journal_sha256') != study.sha(journal) or
                inspection.get('attempts_sha256') != study.sha(attempts)):
            raise ValueError('Smoke inspection binding changed')


def live_controls(plan, condition):
    catalog = paid.fetch('/models', timeout=120)
    endpoints = paid.fetch('/models/' + quote(study.MODEL, safe='/') + '/endpoints', timeout=120)
    model, endpoint = paid.select_endpoint(study.MODEL, study.PROVIDER, catalog, endpoints,
                                           Decimal('0.07'), Decimal('0.34'))
    if endpoint.get('quantization') != 'fp8' or endpoint.get('provider_name') != 'DeepInfra':
        raise ValueError('Live endpoint identity differs')
    wave = json.loads((ROOT / study.WAVE).read_text())
    entry = next(x for x in wave['configurations'] if x['id'] == study.CONFIG)
    public = entry['public_route']
    if endpoint['context_length'] != public['context_tokens_for_reservation']:
        raise ValueError('Live endpoint context differs from reviewed reserve')
    for key in ('prompt', 'completion'):
        if paid.number(endpoint['pricing'][key]) != paid.number(public['pricing_usd_per_million'][key]) / paid.MILLION:
            raise ValueError('Live endpoint price differs from reviewed rate')
    reserve = paid.reservation(endpoint, 4096, Decimal('0.07'), Decimal('0.34'))
    if reserve != paid.number(entry['per_call_reserve_usd']) or reserve > paid.number(study.CAP_USD):
        raise ValueError('Live reserve differs from reviewed amount')
    inputs = {x['id']: x['feedback'] for x in paid.read_rows(ROOT / 'data/pilot/inputs.jsonl')}
    for request in plan['conditions'][condition]['development']:
        payload = request['payload']
        rebuilt = paid.make_payload(study.MODEL, endpoint, inputs[request['record_id']],
                                    payload['messages'][0]['content'],
                                    payload['response_format']['json_schema']['schema'],
                                    study.EFFORT, 4096, Decimal('0.07'), Decimal('0.34'), model)
        if rebuilt != payload:
            raise ValueError('Live adapter would change frozen payload')
    return model, endpoint, reserve


def budget_gate(receipt, budget_path):
    ledger = partitions.open_partition(MASTER, budget_path, receipt['partition_id'],
                                       study.MODEL, study.PROVIDER, study.EFFORT)
    if ledger.cap != paid.number(study.CAP_USD):
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
    receipt = folder / 'smoke-inspection.json'
    if receipt.exists() or not complete_journal(repeat, condition, 'smoke'):
        raise ValueError('Fresh completed smoke required')
    rows = [json.loads(line) for line in attempts.read_text().splitlines()]
    if len(rows) != 3 or [r['id'] for r in rows] != ['DEV-001', 'DEV-002', 'DEV-003']:
        raise ValueError('Smoke must contain exactly three ordered calls')
    if not all(r['status'] == 'ok' and r['billing_ok'] and not r['cost_unknown'] for r in rows):
        raise ValueError('Three valid, billed smoke calls required')
    if not note.strip():
        raise ValueError('Inspection note required')
    value = {'schema': 'openrouter-repeat-smoke-inspection-v1', 'repeat': repeat,
             'condition': condition, 'decision': 'accepted_unchanged', 'note': note,
             'journal_sha256': study.sha(journal), 'attempts_sha256': study.sha(attempts)}
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
    receipt, budget_path = review_receipt(review_path, repeat, manifest_sha)
    model, endpoint, reserve = live_controls(plan, condition)
    ledger = budget_gate(receipt, budget_path)
    try:
        token = paid.load_key(env_file)
        folder.mkdir(parents=True, exist_ok=True)
        with claim.open('x') as out:
            durable(out, {'repeat': repeat, 'condition': condition, 'phase': phase,
                          'manifest_sha256': manifest_sha, 'root_review_sha256': study.sha(review_path),
                          'claimed_utc': utc()})
        requests = plan['conditions'][condition][phase]
        complete = True
        with journal.open('x') as audit, attempts.open('x') as output, responses.open('x') as raw_output:
            durable(audit, {'event': 'phase_started', 'repeat': repeat,
                            'condition': condition, 'phase': phase, 'utc': utc()})
            for request in requests:
                rid = request['record_id']
                payload = request['payload']
                durable(audit, {'event': 'request_intent', 'id': rid,
                                'request_sha256': request['request_sha256'], 'utc': utc()})
                attempt_id = ledger.reserve(reserve, rid)
                start = time.perf_counter()
                record = {'id': rid, 'repeat': repeat, 'condition': condition, 'phase': phase,
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
                                'cost_unknown': record['cost_unknown'], 'utc': utc()})
                if not continue_record(record, phase):
                    complete = False
                    durable(audit, {'event': 'phase_stopped', 'id': rid,
                                    'reason': record['status'], 'utc': utc()})
                    break
            if complete:
                durable(audit, {'event': 'phase_completed', 'repeat': repeat,
                                'condition': condition, 'phase': phase,
                                'request_count': len(requests), 'utc': utc()})
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
        p.add_argument('--repeat', required=True, choices=tuple(study.ORDERS))
        p.add_argument('--condition', required=True, choices=('P0', 'P1', 'P2'))
        p.add_argument('--manifest-sha256', required=True)
        if action == 'inspect':
            p.add_argument('--note', required=True)
        else:
            p.add_argument('--root-review-receipt', required=True)
            p.add_argument('--env-file')
    args = parser.parse_args()
    if args.action == 'inspect':
        inspect(args.repeat, args.condition, args.manifest_sha256, args.note)
    else:
        execute(args.repeat, args.condition, args.action, args.manifest_sha256,
                args.root_review_receipt, args.env_file)


if __name__ == '__main__':
    main()
