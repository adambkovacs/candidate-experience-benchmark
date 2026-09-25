#!/usr/bin/env python3
"""Frozen Qwen 27B off repeat lane; preparation is offline, dispatch is gated."""
import argparse
from decimal import Decimal
import json
import os
from pathlib import Path
import time
import urllib.error
from urllib.parse import quote

from development_benchmark import ROOT, read_rows
import openrouter_paid_benchmark as paid
import openrouter_repeat_wave as wave
import paid_budget_partitions_v2 as partitions
from prompt_admission import audit_response

SPEC = wave.Spec('openrouter-paid-qwen3.8-27b-off', 'qwen/qwen3.8-27b',
                 'deepinfra/bf16', 'DeepInfra', 'bf16', 'off', '0.15', '1.875',
                 262144, 300.0, '0.20', ('P0', 'P2', 'P1'), False)
PREFLIGHT = f'results/repeatability-v1/{SPEC.id}/public-route-preflight.json'
RECEIPT_SCHEMA = 'openrouter-qwen27-repeat-root-review-v1'


def _source_state():
    pair = json.loads((ROOT / SPEC.pair).read_text())
    coverage = json.loads((ROOT / wave.COVERAGE).read_text())
    old_wave = json.loads((ROOT / wave.WAVE).read_text())
    hosted = json.loads((ROOT / wave.HOSTED).read_text())
    preflight = json.loads((ROOT / PREFLIGHT).read_text())
    one = lambda rows: next((x for x in rows if x['id'] == SPEC.id), None)
    group = one(coverage['groups'])
    proposal = one(old_wave['configurations'])
    history = one(hosted['configurations'])
    if not all((group, proposal, history)):
        raise ValueError('Qwen source coverage incomplete')
    if (group['historical_triple_status'] != 'eligible_first_pass' or
            tuple(group['observed_condition_order']) != SPEC.historical_order or
            tuple(proposal['historical_order']) != SPEC.historical_order or
            proposal['paired_manifest'] != wave.bind(SPEC.pair) or
            proposal['proposed_partition_cap_usd'] != SPEC.cap):
        raise ValueError('Historical eligibility, order, pairing or cap changed')
    if (history['continue_on_invalid_output'] is not SPEC.continue_invalid or
            history['controller_timeout_seconds'] != SPEC.timeout or
            history['controls']['adapter_controls'] != pair['controls']):
        raise ValueError('Historical controller policy changed')
    controls = pair['controls']
    if (controls['requested_model'], controls['provider_tag'], controls['provider_name'],
            controls['quantization'], controls['reasoning_effort'], controls['workflow']) != (
            SPEC.model, SPEC.provider, SPEC.provider_name, SPEC.quantization, SPEC.effort, 'single_record'):
        raise ValueError('Historical route controls changed')
    request = controls['request_controls']
    if (request['model'], request['temperature'], request['max_tokens'], request['stream'],
            request['reasoning']) != (SPEC.model, 0, 4096, False, {'enabled': False}):
        raise ValueError('Historical request controls changed')
    if request['provider'] != {'only': [SPEC.provider], 'allow_fallbacks': False,
                               'require_parameters': True,
                               'max_price': {'prompt': 0.15, 'completion': 1.875,
                                             'request': 0, 'image': 0}}:
        raise ValueError('Historical provider control changed')
    if (request['response_format']['type'] != 'json_schema' or
            request['response_format']['json_schema']['strict'] is not True):
        raise ValueError('Historical parser control changed')
    if (preflight['schema'] != 'openrouter-qwen27-public-route-preflight-v1' or
            preflight['configuration_id'] != SPEC.id or
            preflight['proposed_partition_cap_usd'] != SPEC.cap or
            preflight['per_call_reserve_usd'] != '0.047001600' or
            preflight['max_concurrent_requests_for_configuration'] != 1):
        raise ValueError('Reviewed Qwen preflight changed')
    route = preflight['exact_route']
    if (route['model_id'], route['tag'], route['provider_name'], route['quantization'],
            route['status'], route['context_length'], route['reasoning_mandatory']) != (
            SPEC.model, SPEC.provider, SPEC.provider_name, SPEC.quantization, 0,
            SPEC.context, False):
        raise ValueError('Reviewed exact Qwen route changed')
    if (paid.number(route['pricing_usd_per_token']['prompt']) != Decimal('0.00000015') or
            paid.number(route['pricing_usd_per_token']['completion']) != Decimal('0.000001875')):
        raise ValueError('Reviewed endpoint pricing changed')
    for condition in ('P0', 'P1', 'P2'):
        if proposal['historical_request_evidence'][condition] != pair['conditions'][condition]['request_evidence']:
            raise ValueError('Historical source binding changed')
    return pair, preflight


def plan_data(repeat):
    if repeat not in SPEC.orders:
        raise ValueError('Unknown repeat')
    pair, _ = _source_state()
    inputs = read_rows(ROOT / 'data/pilot/inputs.jsonl')
    if len(inputs) != 60 or any(set(x) != {'id', 'feedback'} for x in inputs):
        raise ValueError('Input isolation failed')
    paths = [SPEC.pair, wave.COVERAGE, wave.WAVE, wave.HOSTED, PREFLIGHT,
             'data/pilot/inputs.jsonl', 'schemas/judgments.schema.json',
             'docs/REPEATABILITY_PLAN.md', 'scripts/openrouter_qwen27_repeat.py',
             'scripts/openrouter_repeat_wave.py', 'scripts/openrouter_paid_benchmark.py',
             'scripts/openrouter_benchmark.py', 'scripts/paid_budget_partitions_v2.py',
             'scripts/openrouter_budget_v2.py', 'scripts/prompt_admission.py']
    conditions = {}
    for condition in ('P0', 'P1', 'P2'):
        requests, source = wave.source_requests(SPEC, condition, pair, inputs)
        paths.append(source)
        conditions[condition] = {'historical_attempts': wave.bind(source),
                                 'smoke': requests[:3], 'development': requests}
    return {'schema': 'openrouter-qwen27-repeat-plan-v1', 'configuration_id': SPEC.id,
            'repeat': repeat, 'historical_pass_order': list(SPEC.historical_order),
            'condition_order': list(SPEC.orders[repeat]), 'model': SPEC.model,
            'provider_tag': SPEC.provider, 'reasoning_effort': SPEC.effort,
            'request_timeout_seconds': SPEC.timeout,
            'continue_on_invalid_output': SPEC.continue_invalid,
            'partition_cap_usd': SPEC.cap, 'per_call_reserve_usd': '0.047001600',
            'input_count': 60, 'request_unit': 'single_record_fresh_context',
            'smoke_count_per_condition': 3, 'max_tokens': 4096,
            'seed_policy': 'No explicit seed in historical payload; effective seed unavailable',
            'reference_labels_read': False, 'repeat_status': 'offline_prepared_no_inference',
            'dispatch_gate': 'Root review receipt, live endpoint and child budget partition required',
            'source_bindings': [wave.bind(p) for p in dict.fromkeys(paths)],
            'conditions': conditions}


def prepare():
    for repeat in SPEC.orders:
        folder = SPEC.base / repeat
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / 'manifest.json'
        with path.open('x') as output:
            output.write(json.dumps(plan_data(repeat), indent=2, ensure_ascii=False) + '\n')
            output.flush()
            os.fsync(output.fileno())
        print(repeat, wave.sha(path), path)


def verify(repeat, expected_sha):
    path = SPEC.base / repeat / 'manifest.json'
    if wave.sha(path) != expected_sha:
        raise ValueError('Manifest hash mismatch')
    value = json.loads(path.read_text())
    for binding in value['source_bindings']:
        wave.read_bound(binding)
    if value != plan_data(repeat):
        raise ValueError('Manifest differs from frozen reconstruction')
    return value


def review_receipt(path, repeat, manifest_sha):
    receipt = json.loads(Path(path).read_text())
    if (receipt.get('schema') != RECEIPT_SCHEMA or receipt.get('approved') is not True or
            receipt.get('configuration_id') != SPEC.id or
            receipt.get('partition_cap_usd') != SPEC.cap or
            receipt.get('controller_sha256') != wave.sha(__file__) or
            receipt.get('hosted_execution_sha256') != wave.sha(ROOT / wave.HOSTED) or
            receipt.get('preflight_sha256') != wave.sha(ROOT / PREFLIGHT)):
        raise ValueError('Root review receipt does not bind approved Qwen controls')
    plans = {r: wave.sha(SPEC.base / r / 'manifest.json') for r in SPEC.orders}
    if (receipt.get('plan_sha256') != plans or plans[repeat] != manifest_sha or
            receipt.get('master_ledger') != str(wave.MASTER)):
        raise ValueError('Root review plan or master ledger differs')
    budget = receipt.get('budget_manifest')
    if not isinstance(budget, dict) or not receipt.get('partition_id'):
        raise ValueError('Root review budget binding missing')
    return receipt, wave.read_bound(budget)


def live_controls(plan, condition):
    preflight = json.loads((ROOT / PREFLIGHT).read_text())
    catalog = paid.fetch('/models', timeout=120)
    endpoints = paid.fetch('/models/' + quote(SPEC.model, safe='/') + '/endpoints', timeout=120)
    model, endpoint = paid.select_endpoint(SPEC.model, SPEC.provider, catalog, endpoints,
                                           Decimal(SPEC.prompt_price), Decimal(SPEC.completion_price))
    route = preflight['exact_route']
    if (endpoint.get('model_id'), endpoint.get('tag'), endpoint.get('provider_name'),
            endpoint.get('quantization'), endpoint.get('status'),
            endpoint.get('context_length')) != (
            SPEC.model, SPEC.provider, SPEC.provider_name, SPEC.quantization, 0, SPEC.context):
        raise ValueError('Live exact route differs')
    for key in ('prompt', 'completion'):
        if paid.number(endpoint['pricing'][key]) != paid.number(route['pricing_usd_per_token'][key]):
            raise ValueError('Live route price differs')
    if model.get('reasoning', {}).get('mandatory') is not False:
        raise ValueError('Live model cannot disable reasoning')
    if not set(route['required_supported_parameters']) <= set(endpoint.get('supported_parameters', [])):
        raise ValueError('Live endpoint lacks a reviewed parameter')
    reserve = paid.reservation(endpoint, 4096, Decimal(SPEC.prompt_price),
                               Decimal(SPEC.completion_price))
    if reserve != paid.number(preflight['per_call_reserve_usd']) or reserve > paid.number(SPEC.cap):
        raise ValueError('Live reserve differs from reviewed maximum')
    inputs = {x['id']: x['feedback'] for x in read_rows(ROOT / 'data/pilot/inputs.jsonl')}
    for request in plan['conditions'][condition]['development']:
        payload = request['payload']
        rebuilt = paid.make_payload(SPEC.model, endpoint, inputs[request['record_id']],
                                    payload['messages'][0]['content'],
                                    payload['response_format']['json_schema']['schema'],
                                    SPEC.effort, 4096, Decimal(SPEC.prompt_price),
                                    Decimal(SPEC.completion_price), model)
        if rebuilt != payload:
            raise ValueError('Live adapter would change frozen payload')
    return model, endpoint, reserve


def inspect(repeat, condition, manifest_sha, note):
    plan = verify(repeat, manifest_sha)
    wave.require_order(SPEC, plan, condition, 'smoke')
    folder, _, journal, attempts = wave.phase_paths(SPEC, repeat, condition, 'smoke')
    receipt = folder / 'smoke-inspection.json'
    if receipt.exists() or not wave.complete_journal(SPEC, repeat, condition, 'smoke'):
        raise ValueError('Fresh completed smoke required')
    rows = [json.loads(x) for x in attempts.read_text().splitlines()]
    responses = folder / 'smoke.responses.jsonl'
    raw = [json.loads(x) for x in responses.read_text().splitlines()]
    if (len(rows) != 3 or [r['id'] for r in rows] != ['DEV-001', 'DEV-002', 'DEV-003'] or
            len(raw) != 3 or [r['id'] for r in raw] != [r['id'] for r in rows] or
            [r['attempt_id'] for r in raw] != [r['attempt_id'] for r in rows] or
            any('body_base64' not in r or r.get('body_truncated_at_limit') or r.get('read_error') for r in raw) or
            not all(r['status'] == 'ok' and r['billing_ok'] and not r['cost_unknown'] for r in rows) or
            not note.strip()):
        raise ValueError('Three valid, billed, raw-inspected smoke calls required')
    value = {'schema': 'openrouter-repeat-smoke-inspection-v1', 'repeat': repeat,
             'condition': condition, 'decision': 'accepted_unchanged', 'note': note,
             'journal_sha256': wave.sha(journal), 'attempts_sha256': wave.sha(attempts),
             'responses_sha256': wave.sha(responses)}
    with receipt.open('x') as out:
        json.dump(value, out, indent=2)
        out.write('\n')
        out.flush()
        os.fsync(out.fileno())
    return value


def execute(repeat, condition, phase, manifest_sha, review_path, env_file=None):
    if phase not in ('smoke', 'development'):
        raise ValueError('Unknown phase')
    plan = verify(repeat, manifest_sha)
    wave.require_order(SPEC, plan, condition, phase)
    folder, claim, journal, attempts = wave.phase_paths(SPEC, repeat, condition, phase)
    responses = folder / (phase + '.responses.jsonl')
    if any(p.exists() for p in (claim, journal, attempts, responses)):
        raise FileExistsError('Phase already claimed; no implicit retry')
    receipt, budget_path = review_receipt(review_path, repeat, manifest_sha)
    model, endpoint, reserve = live_controls(plan, condition)
    ledger = partitions.open_partition(wave.MASTER, budget_path, receipt['partition_id'],
                                       SPEC.model, SPEC.provider, SPEC.effort)
    if ledger.cap != paid.number(SPEC.cap):
        ledger.close()
        raise ValueError('Child partition cap differs')
    try:
        token = paid.load_key(env_file)
        folder.mkdir(parents=True, exist_ok=True)
        with claim.open('x') as out:
            paid.durable(out, {'repeat': repeat, 'condition': condition, 'phase': phase,
                               'manifest_sha256': manifest_sha,
                               'root_review_sha256': wave.sha(review_path),
                               'claimed_utc': wave.utc()})
        requests = plan['conditions'][condition][phase]
        complete = True
        with journal.open('x') as audit, attempts.open('x') as output, responses.open('x') as raw_output:
            paid.durable(audit, {'event': 'phase_started', 'repeat': repeat,
                                 'condition': condition, 'phase': phase, 'utc': wave.utc()})
            for request in requests:
                rid, payload = request['record_id'], request['payload']
                paid.durable(audit, {'event': 'request_intent', 'id': rid,
                                     'request_sha256': request['request_sha256'], 'utc': wave.utc()})
                attempt_id = ledger.reserve(reserve, rid)
                start = time.perf_counter()
                record = {'id': rid, 'repeat': repeat, 'condition': condition, 'phase': phase,
                          'attempt_id': attempt_id, 'request': payload,
                          'request_sha256': request['request_sha256'],
                          'manifest_sha256': manifest_sha, 'requested_model': SPEC.model,
                          'reasoning_effort': SPEC.effort, 'request_timeout_seconds': SPEC.timeout,
                          'provider_endpoint': endpoint, 'model_catalog_entry': model,
                          'reference_labels_read': False, 'reserved_cost_usd': str(reserve),
                          'started_utc': wave.utc()}
                paid.durable(audit, {'event': 'request_started', 'id': rid,
                                     'attempt_id': attempt_id,
                                     'request_sha256': request['request_sha256'], 'utc': wave.utc()})
                actual = None
                try:
                    body = wave.fetch_recorded(payload, token, SPEC.timeout, raw_output,
                                               rid, attempt_id, request['request_sha256'])
                    body = json.loads(json.dumps(body).replace(token, '[REDACTED]'))
                    record['raw_response'] = body
                    if isinstance(body, dict):
                        usage = body.get('usage') or {}
                        if usage.get('cost') is not None:
                            actual = paid.number(usage['cost'])
                        record.update(wave.classify(SPEC, body, endpoint))
                    else:
                        record.update(status='control_violation')
                except Exception as exc:
                    record.update(status='service_error', error_type=type(exc).__name__)
                    if isinstance(exc, urllib.error.HTTPError):
                        record['http_status'] = exc.code
                        record['error_body'] = exc.read().decode('utf-8', errors='replace').replace(token, '[REDACTED]')
                        record['error_headers'] = {k: str(exc.headers[k]).replace(token, '[REDACTED]')
                                                   for k in ('x-request-id', 'request-id', 'retry-after', 'cf-ray')
                                                   if exc.headers is not None and exc.headers.get(k) is not None}
                        paid.durable(raw_output, {'id': rid, 'attempt_id': attempt_id,
                                                  'request_sha256': request['request_sha256'],
                                                  'http_status': exc.code, 'error_body': record['error_body'],
                                                  'error_headers': record['error_headers'], 'received_utc': wave.utc()})
                billing_ok = ledger.settle(attempt_id, actual)
                record.update(elapsed_seconds=time.perf_counter() - start,
                              observed_cost_usd=str(actual) if actual is not None else None,
                              cost_unknown=actual is None, billing_ok=billing_ok)
                if isinstance(record.get('raw_response'), dict):
                    diagnostic = audit_response(record, 'openrouter_paid_v1',
                                                endpoint['context_length'] - 4096)
                    record['response_diagnostic'] = diagnostic
                    if not diagnostic['passed'] and record['status'] == 'ok':
                        record['status'] = 'prompt_admission_failure'
                paid.durable(output, record)
                paid.durable(audit, {'event': 'request_finished', 'id': rid,
                                     'attempt_id': attempt_id, 'status': record['status'],
                                     'billing_ok': billing_ok, 'cost_unknown': record['cost_unknown'],
                                     'utc': wave.utc()})
                if not wave.continue_record(SPEC, record, phase):
                    complete = False
                    paid.durable(audit, {'event': 'phase_stopped', 'id': rid,
                                         'reason': record['status'], 'utc': wave.utc()})
                    break
            if complete:
                paid.durable(audit, {'event': 'phase_completed', 'repeat': repeat,
                                     'condition': condition, 'phase': phase,
                                     'request_count': len(requests), 'utc': wave.utc()})
        return complete
    finally:
        if journal.exists():
            lines = journal.read_text().splitlines()
            terminal = json.loads(lines[-1]).get('event') if lines else None
            if terminal not in ('phase_completed', 'phase_stopped', 'phase_aborted'):
                with journal.open('a') as audit:
                    paid.durable(audit, {'event': 'phase_aborted',
                                         'reason': 'exception_or_interruption', 'utc': wave.utc()})
        ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify', 'smoke', 'development', 'inspect'))
    parser.add_argument('--repeat', choices=SPEC.orders)
    parser.add_argument('--condition', choices=('P0', 'P1', 'P2'))
    parser.add_argument('--manifest-sha')
    parser.add_argument('--root-review')
    parser.add_argument('--env-file')
    parser.add_argument('--inspection-note')
    args = parser.parse_args()
    if args.action == 'prepare':
        prepare()
        return
    if not args.repeat or not args.manifest_sha:
        parser.error('--repeat and --manifest-sha required')
    if args.action == 'verify':
        verify(args.repeat, args.manifest_sha)
        print('verified')
    elif args.action == 'inspect':
        if not args.condition or not args.inspection_note:
            parser.error('--condition and --inspection-note required')
        print(inspect(args.repeat, args.condition, args.manifest_sha, args.inspection_note))
    else:
        if not args.condition or not args.root_review:
            parser.error('--condition and --root-review required')
        print('phase_completed' if execute(args.repeat, args.condition, args.action,
                                           args.manifest_sha, args.root_review, args.env_file)
              else 'phase_stopped')


if __name__ == '__main__':
    main()
