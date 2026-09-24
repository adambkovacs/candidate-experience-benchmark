#!/usr/bin/env python3
"""Reviewed never-sent DEV-040–060 on/P2 suffix after preserved DEV-039 HTTP429."""
import argparse
from decimal import Decimal
import json
from pathlib import Path
import time
import urllib.error
from types import SimpleNamespace
from urllib.parse import quote

import openrouter_paid_benchmark as paid
import paid_budget_partitions_v2 as partitions
import prompt_admission as admission
import qwen36_prompt_recovery_v1 as smoke
from development_benchmark import valid
from frozen_prompt_variants import compose_instruction
from openrouter_benchmark import allowed_returned_models, fetch, load_key

ROOT = smoke.ROOT
RESULT = ROOT / 'results/qwen36-on-p2-final21-v2'
PLAN = RESULT / 'plan.json'
OUTPUT = RESULT / 'development.jsonl'
FROZEN, ROUTE = smoke.FROZEN, smoke.ROUTE
MODEL, PROVIDER, NAME = smoke.MODEL, smoke.PROVIDER, smoke.NAME
CID, MODE, VARIANT = 'openrouter-paid-qwen36-35b-a3b-on', 'on', 'P2'
CONTRACT = 'qwen36-on-p2-never-sent-final21-v2'
ORIGINAL = smoke.RESULT / 'on-p2-development.jsonl'
ORIGINAL_JOURNAL = Path(str(ORIGINAL) + '.attempts.jsonl')
V1 = smoke.RESULT / 'on-p2-dev034-060-suffix.jsonl'
V1_JOURNAL = Path(str(V1) + '.attempts.jsonl')
V1_REPORT = ROOT / 'results/hosted-final-suffix-reconciled-v1/qwen36-on-p2.json'
SMOKE_REVIEW = smoke.RESULT / 'on-p2-root-review.json'
RESERVE = smoke.RESERVE
CAP = Decimal('0.64')
IDS = [f'DEV-{i:03}' for i in range(40, 61)]
BOUND = RESERVE * len(IDS)


def read_lines(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def prior_state(bindings):
    original = read_lines(smoke.source(bindings['original_result']))
    first_journal = read_lines(smoke.source(bindings['original_journal']))
    suffix = read_lines(smoke.source(bindings['v1_result']))
    second_journal = read_lines(smoke.source(bindings['v1_journal']))
    report = json.loads(smoke.source(bindings['v1_report']).read_text())
    if ([r.get('id') for r in original] != [f'DEV-{i:03}' for i in range(1, 34)] or
        [r.get('id') for r in suffix] != [f'DEV-{i:03}' for i in range(34, 40)] or
        report.get('configuration_id') != CID or report.get('condition') != VARIANT or
        report.get('attempted') != 39 or report.get('valid_outputs') != 37 or
        report.get('never_sent_ids') != IDS or report.get('status_counts', {}).get('service_error') != 2):
        raise ValueError('Prior reconciled on/P2 coverage differs')
    if (not first_journal or first_journal[-1].get('event') != 'terminal' or
        first_journal[-1].get('attempted_records') != 33 or
        not second_journal or second_journal[-1].get('event') != 'terminal' or
        second_journal[-1].get('attempted_records') != 6 or
        second_journal[-1].get('planned_records') != 27 or
        second_journal[-1].get('completed') is not False):
        raise ValueError('Prior terminal evidence differs')
    started = [e.get('id') for e in first_journal + second_journal if e.get('event') == 'started']
    if started != [f'DEV-{i:03}' for i in range(1, 40)]:
        raise ValueError('Prior started claims include an unexpected ID')
    for row in (original[-1], suffix[-1]):
        meta = (row.get('raw_error_response') or {}).get('error', {}).get('metadata', {})
        if (row.get('status') != 'service_error' or row.get('http_status') != 429 or
            row.get('cost_unknown') is not True or row.get('reserved_cost_usd') != str(RESERVE) or
            meta.get('provider_name') != NAME or meta.get('limit_source') != 'upstream_provider_shared_pool'):
            raise ValueError('Preserved HTTP429 failure changed')
    if suffix[-1]['id'] != 'DEV-039' or (suffix[-1]['raw_error_response']['error']['metadata'].get('provider_error_code') != 'queue_timeout' or suffix[-1]['raw_error_response']['error']['metadata'].get('retry_after_seconds') != 1):
        raise ValueError('DEV-039 queue timeout evidence changed')
    review = json.loads(smoke.source(bindings['smoke_review']).read_text())
    if review.get('approved') is not True:
        raise ValueError('Original smoke review missing')
    return {'attempted': 39, 'valid': 37, 'failed_ids': ['DEV-033', 'DEV-039'],
            'never_sent_ids': IDS, 'original_result_sha256': bindings['original_result']['sha256'],
            'v1_result_sha256': bindings['v1_result']['sha256'],
            'v1_report_sha256': bindings['v1_report']['sha256'], 'retry_failed_records': False}


def frozen_context():
    frozen = json.loads(FROZEN.read_text())
    config, _, evidence, inputs, schema, instruction, _ = admission._checked(frozen, ROOT, CID, VARIANT)
    if config['controls']['effort'] != MODE or evidence['adapter'] != 'openrouter_paid_v1':
        raise ValueError('Frozen on/P2 controls differ')
    requests = evidence['requests'][3+39:]
    if [r['record_ids'] for r in requests] != [[ident] for ident in IDS]:
        raise ValueError('Frozen request suffix differs')
    return config, inputs, schema, instruction, requests


def verify(path, expected_sha=None):
    path = Path(path).resolve()
    path.relative_to(RESULT)
    if expected_sha is not None and smoke.sha(path) != expected_sha:
        raise ValueError('Final21 plan hash mismatch')
    plan = json.loads(path.read_text())
    if (plan.get('contract') != CONTRACT or plan.get('offline_only') is not True or
        plan.get('inference_performed') is not False or plan.get('reference_labels_read') is not False or
        plan.get('configuration_id') != CID or plan.get('reasoning') != MODE or
        plan.get('condition') != VARIANT or plan.get('phase') != 'development_suffix' or
        plan.get('record_ids') != IDS or plan.get('excluded_failed_ids') != ['DEV-033', 'DEV-039'] or
        plan.get('original_timing_preserved') is not False):
        raise ValueError('Final21 protocol differs')
    if smoke.source(plan['frozen_execution']) != FROZEN or smoke.source(plan['route_audit']) != ROUTE:
        raise ValueError('Frozen route or execution binding differs')
    state = prior_state(plan['sources'])
    if plan.get('prior_state') != state:
        raise ValueError('Final21 prior-state binding differs')
    config, inputs, _, _, requests = frozen_context()
    if plan.get('requests') != [r['client_request'] for r in requests]:
        raise ValueError('Exact frozen suffix request bindings differ')
    for offset, binding in enumerate(plan['requests'], start=39):
        envelope = json.loads(smoke.source(binding).read_text())
        if (envelope['adapter_controls'] != config['controls']['adapter_controls'] or
            envelope['request']['messages'][1]['content'] != json.dumps({'feedback': inputs[offset]['feedback']})):
            raise ValueError('Final21 request controls or input differs')
    endpoint = smoke.endpoint_from_audit(ROUTE)
    reserve = paid.reservation(endpoint, 4096, Decimal('0.1'), Decimal('0.9'))
    if (reserve != RESERVE or plan.get('per_call_reserve_usd') != str(RESERVE) or
        plan.get('call_bound_usd') != str(BOUND) or plan.get('proposed_partition_cap_usd') != str(CAP) or BOUND > CAP):
        raise ValueError('Final21 reserve or partition cap differs')
    output = (ROOT / plan['new_output']).resolve()
    output.relative_to(RESULT)
    if output != OUTPUT or output.exists() or Path(str(output) + '.attempts.jsonl').exists():
        raise FileExistsError('Final21 output is reused or differs')
    return {'records': len(IDS), 'record_ids': IDS, 'prior_state': state,
            'call_bound_usd': str(BOUND), 'proposed_partition_cap_usd': str(CAP)}


def build():
    if PLAN.exists():
        raise FileExistsError('Final21 plan already exists')
    RESULT.mkdir(parents=True, exist_ok=True)
    bindings = {'original_result': smoke.bind(ORIGINAL), 'original_journal': smoke.bind(ORIGINAL_JOURNAL),
                'v1_result': smoke.bind(V1), 'v1_journal': smoke.bind(V1_JOURNAL),
                'v1_report': smoke.bind(V1_REPORT), 'smoke_review': smoke.bind(SMOKE_REVIEW)}
    prior = prior_state(bindings)
    _, _, _, _, requests = frozen_context()
    plan = {'contract': CONTRACT, 'offline_only': True, 'inference_performed': False,
            'reference_labels_read': False, 'configuration_id': CID, 'reasoning': MODE,
            'condition': VARIANT, 'phase': 'development_suffix', 'record_ids': IDS,
            'excluded_failed_ids': ['DEV-033', 'DEV-039'], 'original_timing_preserved': False,
            'timing_note': 'Never-sent DEV-040–060 only; DEV-033 and DEV-039 remain failed. New timing is not the original counterbalanced schedule.',
            'frozen_execution': smoke.bind(FROZEN), 'route_audit': smoke.bind(ROUTE),
            'sources': bindings, 'prior_state': prior,
            'requests': [r['client_request'] for r in requests],
            'per_call_reserve_usd': str(RESERVE), 'call_bound_usd': str(BOUND),
            'proposed_partition_cap_usd': str(CAP), 'new_output': str(OUTPUT.relative_to(ROOT))}
    with PLAN.open('x') as stream:
        json.dump(plan, stream, indent=2)
        stream.write('\n')
    return verify(PLAN)


def review_execution(plan_path, plan_sha, budget_path, partition_id, review_path):
    summary = verify(plan_path, plan_sha)
    budget_path = Path(budget_path).resolve()
    budget_path.relative_to(ROOT)
    review_path = Path(review_path).resolve()
    review_path.relative_to(ROOT)
    receipt = json.loads(review_path.read_text())
    if any((receipt.get('approved') is not True,
            receipt.get('suffix_plan_sha256') != plan_sha,
            receipt.get('wrapper_sha256') != smoke.sha(__file__),
            receipt.get('budget_manifest_sha256') != smoke.sha(budget_path),
            receipt.get('partition_id') != partition_id,
            receipt.get('preserved_v1_report_sha256') != summary['prior_state']['v1_report_sha256'],
            receipt.get('continue_on_known_billing_intrinsic_invalid') is not True)):
        raise ValueError('Missing exact final21 root review')
    budget = json.loads(budget_path.read_text())
    if budget.get('version') != 'paid-partitions-v1' or budget.get('master_ledger') != str((ROOT / 'results/openrouter-paid-budget.jsonl').resolve()):
        raise ValueError('Final21 budget is not v2 master allocation')
    entries = [entry for entry in budget.get('partitions', []) if entry.get('id') == partition_id]
    if len(entries) != 1 or (entries[0].get('model'), entries[0].get('provider'), entries[0].get('reasoning')) != (MODEL, PROVIDER, MODE):
        raise ValueError('Final21 partition route differs')
    if not BOUND <= paid.number(entries[0].get('cap_usd')) <= CAP:
        raise ValueError('Final21 partition cap differs')
    Path(entries[0]['child_ledger']).resolve().relative_to(ROOT / 'results')
    return json.loads(Path(plan_path).read_text()), summary


def execute(plan_path, plan_sha, budget_path, partition_id, review_path, env_file=None, timeout=300):
    plan, _ = review_execution(plan_path, plan_sha, budget_path, partition_id, review_path)
    if timeout != 300:
        raise ValueError('Frozen 300-second controller timeout required')
    config, inputs, schema, instruction, _ = frozen_context()
    composed = compose_instruction((ROOT / config['baseline_instruction']['file']).read_text(),
                                   VARIANT, role='system', parent_baseline_id=config['parent_baseline_id'], root=ROOT)
    if composed['instruction'] != instruction:
        raise ValueError('Frozen instruction differs')
    requests = [json.loads(smoke.source(binding).read_text())['request'] for binding in plan['requests']]
    token = load_key(env_file)
    catalog = fetch('/models', timeout=timeout)
    endpoints = fetch('/models/' + quote(MODEL, safe='/') + '/endpoints', timeout=timeout)
    audited = smoke.endpoint_from_audit(ROUTE)
    model, endpoint = smoke.live_endpoint(catalog, endpoints, audited)
    controls = config['controls']['adapter_controls']
    args = SimpleNamespace(model=MODEL, reasoning=MODE)
    for offset, request in enumerate(requests, start=39):
        expected = paid.make_payload(MODEL, endpoint, inputs[offset]['feedback'], instruction,
                                     schema, MODE, 4096, Decimal('0.1'), Decimal('0.9'), model)
        if request != expected or paid.paid_adapter_controls(args, endpoint, request) != controls:
            raise ValueError('Live final21 request differs from frozen exact bytes')
    if paid.reservation(endpoint, 4096, Decimal('0.1'), Decimal('0.9')) != RESERVE:
        raise ValueError('Live final21 reserve differs')
    output = (ROOT / plan['new_output']).resolve()
    journal = Path(str(output) + '.attempts.jsonl')
    if output.exists() or journal.exists():
        raise FileExistsError('Final21 output already exists')
    ledger = partitions.open_partition(ROOT / 'results/openrouter-paid-budget.jsonl',
                                       budget_path, partition_id, MODEL, PROVIDER, MODE)
    attempted, completed, terminal_status = 0, False, None
    try:
        with output.open('x') as out, journal.open('x') as audit:
            for offset, request in enumerate(requests, start=39):
                row = inputs[offset]
                attempt = ledger.reserve(RESERVE, row['id'])
                attempted += 1
                record = {'id': row['id'], 'phase': 'development_suffix', 'attempt_id': attempt,
                          'requested_model': MODEL, 'reasoning_effort': MODE,
                          'provider_endpoint': endpoint, 'model_catalog_entry': model,
                          'request': request, 'request_sha256': paid.digest(json.dumps(request, sort_keys=True)),
                          'policy_sha256': paid.digest(instruction), 'schema_sha256': paid.digest(json.dumps(schema, sort_keys=True)),
                          'input_sha256': paid.digest(row['feedback']), 'reference_labels_read': False,
                          'prompt_variant': composed['audit'], 'parent_baseline_id': config['parent_baseline_id'],
                          'surface': 'OpenRouter paid HTTP', 'runtime': 'OpenRouter HTTP v1',
                          'hardware': 'Remote provider undisclosed', 'quantization': 'fp8',
                          'retry_policy': 'none; exclusive files; every attempt reserves against shared cap',
                          'request_timeout_seconds': timeout, 'reserved_cost_usd': str(RESERVE),
                          'budget_partition_id': partition_id,
                          'budget_ledger': str(Path(ledger.file.name).relative_to(ROOT)),
                          'aggregate_cap_usd': str(ledger.master_cap), 'continue_on_invalid_output': True,
                          'prompt_recovery': {'contract': CONTRACT, 'plan_sha256': plan_sha,
                                              'prior_report_sha256': plan['sources']['v1_report']['sha256'],
                                              'review_receipt_sha256': smoke.sha(review_path),
                                              'original_timing_preserved': False},
                          'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
                paid.durable(audit, dict(record, event='started'))
                start = time.perf_counter()
                actual = None
                try:
                    body = fetch('/chat/completions', token, request, timeout)
                    body = json.loads(json.dumps(body).replace(token, '[REDACTED]'))
                    record.update(raw_response=body, returned_model=body.get('model'), returned_provider=body.get('provider'))
                    usage = body.get('usage') or {}
                    record['usage'] = usage
                    if usage.get('cost') is not None:
                        actual = paid.number(usage['cost'])
                    choices = body.get('choices')
                    if body.get('error') or not isinstance(choices, list) or len(choices) != 1:
                        record.update(status='control_violation', control_violation=True, prediction=None)
                    else:
                        choice = choices[0]
                        message = choice.get('message') or {}
                        record['finish_reason'] = choice.get('finish_reason')
                        if choice.get('error') or message.get('tool_calls') or message.get('function_call'):
                            record.update(status='control_violation', control_violation=True, prediction=None)
                        else:
                            try:
                                prediction = json.loads(message.get('content'))
                            except (ValueError, TypeError):
                                prediction = None
                            record['prediction'] = prediction
                            record['status'] = ('ok' if valid(prediction) and choice.get('finish_reason') == 'stop'
                                                and not message.get('refusal') else 'invalid_output')
                    record['allowed_returned_models'] = sorted(allowed_returned_models(MODEL, endpoint))
                    if body.get('model') not in record['allowed_returned_models']:
                        record['status'] = 'model_mismatch'
                    if body.get('provider') != NAME:
                        record['status'] = 'provider_mismatch'
                except Exception as exc:
                    record.update(status='service_error', error_type=type(exc).__name__)
                    if isinstance(exc, urllib.error.HTTPError):
                        record['http_status'] = exc.code
                        try:
                            record['raw_error_response'] = json.loads(exc.read(1000000).decode().replace(token, '[REDACTED]'))
                        except (ValueError, UnicodeError):
                            pass
                billing_ok = ledger.settle(attempt, actual)
                record.update(elapsed_seconds=time.perf_counter()-start,
                              observed_cost_usd=str(actual) if actual is not None else None,
                              cost_unknown=actual is None, billing_ok=billing_ok,
                              **paid.budget_fields(ledger))
                record['prompt_response_diagnostics'] = admission.audit_response(record, 'openrouter_paid_v1', 262144-4096)
                paid.durable(out, record)
                paid.durable(audit, {'event': 'finished', 'attempt_id': attempt, 'id': row['id'],
                                     'status': record['status'], 'billing_ok': billing_ok})
                terminal_status = record['status']
                if not smoke.continue_smoke(record):
                    break
            else:
                completed = True
            paid.durable(audit, {'event': 'terminal', 'attempted_records': attempted,
                                 'planned_records': len(IDS), 'completed': completed,
                                 'terminal_status': terminal_status, 'reasoning': MODE,
                                 'condition': VARIANT, 'plan_sha256': plan_sha})
    finally:
        ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--plan')
    parser.add_argument('--sha256')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--budget-manifest')
    parser.add_argument('--partition-id')
    parser.add_argument('--review')
    parser.add_argument('--env-file')
    parser.add_argument('--timeout', type=float, default=300)
    args = parser.parse_args()
    if args.build and not any((args.plan, args.sha256, args.execute, args.budget_manifest, args.partition_id, args.review)):
        summary = build()
        print(PLAN.relative_to(ROOT), smoke.sha(PLAN), json.dumps(summary, sort_keys=True))
    elif args.execute and all((args.plan, args.sha256, args.budget_manifest, args.partition_id, args.review)) and not args.build:
        execute(args.plan, args.sha256, args.budget_manifest, args.partition_id,
                args.review, args.env_file, args.timeout)
    elif args.plan and args.sha256 and not any((args.build, args.execute, args.budget_manifest, args.partition_id, args.review)):
        print(json.dumps(verify(args.plan, args.sha256), sort_keys=True))
    else:
        parser.error('Use --build, offline --plan PATH --sha256 HASH, or full reviewed --execute arguments')


if __name__ == '__main__':
    main()
