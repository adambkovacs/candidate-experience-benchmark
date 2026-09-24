#!/usr/bin/env python3
"""Separately reviewed Qwen3.6 P1/P2 full60 recovery after three-record smokes."""
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
RESULT = smoke.RESULT
FROZEN = smoke.FROZEN
ROUTE = smoke.ROUTE
MODEL = smoke.MODEL
PROVIDER = smoke.PROVIDER
NAME = smoke.NAME
CONTRACT = 'qwen36-prompt-recovery-full60-v1'
CAP = Decimal('1.80')
RESERVE = smoke.RESERVE
BOUND = RESERVE * 60


def smoke_evidence(mode, variant, result_binding, journal_binding, frozen_requests):
    result = smoke.source(result_binding)
    journal = smoke.source(journal_binding)
    rows = [json.loads(line) for line in result.read_text().splitlines() if line.strip()]
    events = [json.loads(line) for line in journal.read_text().splitlines() if line.strip()]
    if len(rows) != 3 or [r.get('id') for r in rows] != [f'DEV-{i:03}' for i in range(1, 4)]:
        raise ValueError('Smoke did not cover exactly DEV-001 through DEV-003')
    if not events or events[-1].get('event') != 'terminal' or events[-1].get('completed') is not True or events[-1].get('attempted_records') != 3:
        raise ValueError('Smoke did not complete three attempted records')
    for row, expected in zip(rows, frozen_requests):
        request = json.loads(smoke.source(expected['client_request']).read_text())['request']
        body = row.get('raw_response') or {}
        choices = body.get('choices') or []
        choice = choices[0] if len(choices) == 1 else {}
        message = choice.get('message') or {}
        try:
            prediction = json.loads(message.get('content'))
        except (ValueError, TypeError):
            prediction = None
        usage = body.get('usage') or {}
        diagnostic = admission.audit_response(row, 'openrouter_paid_v1', 262144-4096)
        if any((body.get('error'), choice.get('error'), message.get('refusal'),
                message.get('tool_calls'), message.get('function_call'),
                body.get('model') != row.get('returned_model'),
                body.get('provider') != row.get('returned_provider'),
                choice.get('finish_reason') != row.get('finish_reason'),
                prediction != row.get('prediction'), not valid(prediction),
                str(usage.get('cost')) != row.get('observed_cost_usd'),
                diagnostic['blockers'])):
            raise ValueError('Smoke raw response or billing fails inspection')
        if any((row.get('request') != request,
                row.get('status') != 'ok',
                row.get('reasoning_effort') != mode,
                row.get('reference_labels_read') is not False,
                row.get('billing_ok') is not True,
                row.get('cost_unknown') is not False,
                row.get('returned_model') not in allowed_returned_models(MODEL, row['provider_endpoint']),
                row.get('returned_provider') != NAME,
                row.get('finish_reason') != 'stop',
                row.get('prompt_response_diagnostics', {}).get('passed') is not True,
                row.get('prompt_response_diagnostics', {}).get('blockers') != [],
                len(choices) != 1)):
            raise ValueError('Smoke response fails full60 admission')
    return {'records': 3, 'status': 'passed', 'raw_smoke_sha256': result_binding['sha256'],
            'journal_sha256': journal_binding['sha256']}


def verify(plan_path, expected_sha=None):
    plan_path = Path(plan_path).resolve()
    if expected_sha is not None and smoke.sha(plan_path) != expected_sha:
        raise ValueError('Full60 plan hash mismatch')
    plan = json.loads(plan_path.read_text())
    mode, variant = plan.get('reasoning'), plan.get('condition')
    if (mode, variant) not in smoke.ORDER or plan.get('contract') != CONTRACT or plan.get('offline_only') is not True or plan.get('inference_performed') is not False or plan.get('reference_labels_read') is not False:
        raise ValueError('Invalid full60 recovery plan')
    if plan.get('configuration_id') != f'openrouter-paid-qwen36-35b-a3b-{mode}' or plan.get('phase') != 'development60' or plan.get('record_ids') != [f'DEV-{i:03}' for i in range(1, 61)]:
        raise ValueError('Full60 membership differs')
    if plan.get('original_timing_preserved') is not False or plan.get('recovery_execution') != 'independent_conditions_may_overlap':
        raise ValueError('Full60 recovery timing disclosure differs')
    if smoke.source(plan['frozen_execution']) != FROZEN or smoke.source(plan['route_audit']) != ROUTE:
        raise ValueError('Frozen source binding differs')
    frozen = json.loads(FROZEN.read_text())
    config, _, evidence, inputs, schema, instruction, _ = admission._checked(frozen, ROOT, plan['configuration_id'], variant)
    controls = config['controls']
    if evidence['adapter'] != 'openrouter_paid_v1' or controls['model'] != MODEL or controls['effort'] != mode or controls['quantization'] != 'fp8' or controls['output_reserve_tokens'] != 4096:
        raise ValueError('Frozen full60 controls differ')
    if plan['requests'] != [r['client_request'] for r in evidence['requests'][3:]] or [r['record_ids'] for r in evidence['requests'][3:]] != [[f'DEV-{i:03}'] for i in range(1, 61)]:
        raise ValueError('Full60 requests differ from exact frozen 60')
    for index, binding in enumerate(plan['requests']):
        request = json.loads(smoke.source(binding).read_text())
        if request['adapter_controls'] != controls['adapter_controls'] or request['request']['messages'][1]['content'] != json.dumps({'feedback': inputs[index]['feedback']}):
            raise ValueError('Full60 request controls or input differs')
    inspection = smoke_evidence(mode, variant, plan['smoke_result'], plan['smoke_journal'], evidence['requests'][:3])
    if plan['smoke_inspection'] != inspection:
        raise ValueError('Smoke inspection differs')
    endpoint = smoke.endpoint_from_audit(ROUTE)
    reserve = paid.reservation(endpoint, 4096, Decimal('0.1'), Decimal('0.9'))
    if reserve != RESERVE or plan.get('per_call_reserve_usd') != str(reserve) or plan.get('sixty_call_bound_usd') != str(reserve * 60) or plan.get('proposed_partition_cap_usd') != str(CAP) or reserve * 60 > CAP:
        raise ValueError('Full60 reserve or partition cap differs')
    output = (ROOT / plan['new_output']).resolve()
    output.relative_to(RESULT)
    if output.exists() or Path(str(output) + '.attempts.jsonl').exists():
        raise FileExistsError('Full60 recovery output already exists')
    return {'condition': f'{mode}/{variant}', 'records': 60, 'smoke_inspection': inspection,
            'per_call_reserve_usd': str(reserve), 'sixty_call_bound_usd': str(reserve * 60),
            'proposed_partition_cap_usd': str(CAP)}


def build():
    frozen = json.loads(FROZEN.read_text())
    for mode, variant in smoke.ORDER:
        cid = f'openrouter-paid-qwen36-35b-a3b-{mode}'
        _, _, evidence, *_ = admission._checked(frozen, ROOT, cid, variant)
        result = RESULT / f'{mode}-{variant.lower()}-smoke.jsonl'
        journal = Path(str(result) + '.attempts.jsonl')
        result_binding, journal_binding = smoke.bind(result), smoke.bind(journal)
        inspection = smoke_evidence(mode, variant, result_binding, journal_binding, evidence['requests'][:3])
        plan = {'contract': CONTRACT, 'offline_only': True, 'inference_performed': False,
                'reference_labels_read': False, 'configuration_id': cid, 'reasoning': mode,
                'condition': variant, 'phase': 'development60',
                'record_ids': [f'DEV-{i:03}' for i in range(1, 61)],
                'original_timing_preserved': False,
                'recovery_execution': 'independent_conditions_may_overlap',
                'timing_note': 'These full60 calls occur after original attempts and recovery smokes; conditions may run in parallel. Original counterbalanced timing is not restored.',
                'frozen_execution': smoke.bind(FROZEN), 'route_audit': smoke.bind(ROUTE),
                'smoke_result': result_binding, 'smoke_journal': journal_binding,
                'smoke_inspection': inspection,
                'requests': [r['client_request'] for r in evidence['requests'][3:]],
                'per_call_reserve_usd': str(RESERVE), 'sixty_call_bound_usd': str(BOUND),
                'proposed_partition_cap_usd': str(CAP),
                'new_output': str((RESULT / f'{mode}-{variant.lower()}-development.jsonl').relative_to(ROOT))}
        destination = RESULT / f'{mode}-{variant.lower()}-full60-plan.json'
        with destination.open('x') as stream:
            json.dump(plan, stream, indent=2)
            stream.write('\n')
        verify(destination)
        print(destination.relative_to(ROOT), smoke.sha(destination))


def review_execution(plan_path, plan_sha, budget_path, partition_id, review_path):
    summary = verify(plan_path, plan_sha)
    Path(plan_path).resolve().relative_to(RESULT)
    budget_path = Path(budget_path).resolve()
    budget_path.relative_to(ROOT)
    review_path = Path(review_path).resolve()
    review_path.relative_to(ROOT)
    receipt = json.loads(review_path.read_text())
    if any((receipt.get('approved') is not True,
            receipt.get('full60_plan_sha256') != plan_sha,
            receipt.get('wrapper_sha256') != smoke.sha(__file__),
            receipt.get('budget_manifest_sha256') != smoke.sha(budget_path),
            receipt.get('partition_id') != partition_id,
            receipt.get('smoke_result_sha256') != summary['smoke_inspection']['raw_smoke_sha256'],
            receipt.get('continue_on_known_billing_intrinsic_invalid') is not True)):
        raise ValueError('Missing exact full60 root review')
    plan = json.loads(Path(plan_path).read_text())
    budget = json.loads(budget_path.read_text())
    if budget.get('version') != 'paid-partitions-v1' or budget.get('master_ledger') != str((ROOT / 'results/openrouter-paid-budget.jsonl').resolve()):
        raise ValueError('Budget manifest is not v2 master allocation')
    entries = [e for e in budget.get('partitions', []) if e.get('id') == partition_id]
    if len(entries) != 1:
        raise ValueError('Missing unique full60 partition')
    entry = entries[0]
    if (entry.get('model'), entry.get('provider'), entry.get('reasoning')) != (MODEL, PROVIDER, plan['reasoning']):
        raise ValueError('Full60 partition route differs')
    if not BOUND <= paid.number(entry.get('cap_usd')) <= CAP:
        raise ValueError('Full60 partition cap differs')
    if not str(Path(entry['child_ledger']).resolve()).startswith(str(ROOT / 'results') + '/'):
        raise ValueError('Full60 child ledger outside results')
    return plan, summary


def execute(plan_path, plan_sha, budget_path, partition_id, review_path, env_file=None, timeout=300):
    plan, _ = review_execution(plan_path, plan_sha, budget_path, partition_id, review_path)
    if timeout != 300:
        raise ValueError('Frozen 300-second controller timeout required')
    mode, variant = plan['reasoning'], plan['condition']
    frozen = json.loads(FROZEN.read_text())
    config, _, _, inputs, schema, instruction, _ = admission._checked(frozen, ROOT, plan['configuration_id'], variant)
    composed = compose_instruction((ROOT / config['baseline_instruction']['file']).read_text(),
                                   variant, role='system', parent_baseline_id=config['parent_baseline_id'], root=ROOT)
    if composed['instruction'] != instruction:
        raise ValueError('Frozen instruction differs')
    requests = [json.loads(smoke.source(binding).read_text())['request'] for binding in plan['requests']]
    output = (ROOT / plan['new_output']).resolve()
    journal = Path(str(output) + '.attempts.jsonl')
    if output.exists() or journal.exists():
        raise FileExistsError('Full60 output already exists')
    token = load_key(env_file)
    catalog = fetch('/models', timeout=timeout)
    endpoint_response = fetch('/models/' + quote(MODEL, safe='/') + '/endpoints', timeout=timeout)
    audited = smoke.endpoint_from_audit(ROUTE)
    model, endpoint = smoke.live_endpoint(catalog, endpoint_response, audited)
    controls = config['controls']['adapter_controls']
    args = SimpleNamespace(model=MODEL, reasoning=mode)
    for index, request in enumerate(requests):
        expected = paid.make_payload(MODEL, endpoint, inputs[index]['feedback'], instruction,
                                     schema, mode, 4096, Decimal('0.1'), Decimal('0.9'), model)
        if request != expected or paid.paid_adapter_controls(args, endpoint, request) != controls:
            raise ValueError('Live full60 request differs from frozen exact bytes')
    reserve = paid.reservation(endpoint, 4096, Decimal('0.1'), Decimal('0.9'))
    if reserve != RESERVE:
        raise ValueError('Live full60 reserve differs')
    ledger = partitions.open_partition(ROOT / 'results/openrouter-paid-budget.jsonl',
                                       budget_path, partition_id, MODEL, PROVIDER, mode)
    attempted = 0
    completed = False
    terminal_status = None
    try:
        with output.open('x') as out, journal.open('x') as audit:
            for index, request in enumerate(requests):
                row = inputs[index]
                attempt = ledger.reserve(reserve, row['id'])
                attempted += 1
                record = {'id': row['id'], 'phase': 'development', 'attempt_id': attempt,
                          'requested_model': MODEL, 'reasoning_effort': mode,
                          'provider_endpoint': endpoint, 'model_catalog_entry': model,
                          'request': request, 'request_sha256': paid.digest(json.dumps(request, sort_keys=True)),
                          'policy_sha256': paid.digest(instruction),
                          'schema_sha256': paid.digest(json.dumps(schema, sort_keys=True)),
                          'input_sha256': paid.digest(row['feedback']),
                          'reference_labels_read': False, 'prompt_variant': composed['audit'],
                          'parent_baseline_id': config['parent_baseline_id'],
                          'surface': 'OpenRouter paid HTTP', 'runtime': 'OpenRouter HTTP v1',
                          'hardware': 'Remote provider undisclosed', 'quantization': 'fp8',
                          'retry_policy': 'none; exclusive files; every attempt reserves against shared cap',
                          'request_timeout_seconds': timeout, 'reserved_cost_usd': str(reserve),
                          'budget_partition_id': partition_id,
                          'budget_ledger': str(Path(ledger.file.name).relative_to(ROOT)),
                          'aggregate_cap_usd': str(ledger.master_cap),
                          'continue_on_invalid_output': True,
                          'prompt_recovery': {'contract': CONTRACT, 'plan_sha256': plan_sha,
                                              'smoke_result_sha256': plan['smoke_result']['sha256'],
                                              'review_receipt_sha256': smoke.sha(review_path),
                                              'original_timing_preserved': False},
                          'started_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}
                paid.durable(audit, dict(record, event='started'))
                start = time.perf_counter()
                actual = None
                try:
                    body = fetch('/chat/completions', token, request, timeout)
                    body = json.loads(json.dumps(body).replace(token, '[REDACTED]'))
                    record['raw_response'] = body
                    record['returned_model'] = body.get('model')
                    record['returned_provider'] = body.get('provider')
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
                                 'planned_records': 60, 'completed': completed,
                                 'terminal_status': terminal_status, 'reasoning': mode,
                                 'condition': variant, 'plan_sha256': plan_sha})
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
        build()
    elif args.execute and all((args.plan, args.sha256, args.budget_manifest, args.partition_id, args.review)) and not args.build:
        execute(args.plan, args.sha256, args.budget_manifest, args.partition_id, args.review, args.env_file, args.timeout)
    elif args.plan and args.sha256 and not any((args.build, args.execute, args.budget_manifest, args.partition_id, args.review)):
        print(json.dumps(verify(args.plan, args.sha256), sort_keys=True))
    else:
        parser.error('Use --build, offline --plan PATH --sha256 HASH, or full reviewed --execute arguments')


if __name__ == '__main__':
    main()
