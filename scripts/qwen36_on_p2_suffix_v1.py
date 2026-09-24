#!/usr/bin/env python3
"""Reviewed DEV-034–060 suffix after on/P2 stopped at a preserved DEV-033 HTTP429."""
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
CONTRACT = 'qwen36-on-p2-never-sent-suffix-v1'
MODE = 'on'
VARIANT = 'P2'
CID = 'openrouter-paid-qwen36-35b-a3b-on'
SOURCE = RESULT / 'on-p2-development.jsonl'
JOURNAL = Path(str(SOURCE) + '.attempts.jsonl')
PLAN = RESULT / 'on-p2-dev034-060-suffix-plan.json'
CAP = Decimal('0.81')
RESERVE = smoke.RESERVE
BOUND = RESERVE * 27


def stopped_prefix(result_binding, journal_binding, frozen_requests):
    result = smoke.source(result_binding)
    journal = smoke.source(journal_binding)
    rows = [json.loads(line) for line in result.read_text().splitlines() if line.strip()]
    events = [json.loads(line) for line in journal.read_text().splitlines() if line.strip()]
    if len(rows) != 33 or [r.get('id') for r in rows] != [f'DEV-{i:03}' for i in range(1, 34)]:
        raise ValueError('Original on/P2 result is not the 33-attempt prefix')
    if not events or events[-1].get('event') != 'terminal' or events[-1].get('completed') is not False or events[-1].get('attempted_records') != 33:
        raise ValueError('Original on/P2 prefix did not stop at DEV-033')
    for row, expected in zip(rows, frozen_requests[:33]):
        request = json.loads(smoke.source(expected['client_request']).read_text())['request']
        if row.get('request') != request or row.get('reference_labels_read') is not False or row.get('reasoning_effort') != MODE:
            raise ValueError('Original on/P2 prefix request differs from frozen input')
    if any(r.get('status') != 'ok' or r.get('billing_ok') is not True or r.get('cost_unknown') is not False for r in rows[:32]):
        raise ValueError('Original on/P2 first 32 are not known-billing successes')
    failed = rows[-1]
    if any((failed.get('status') != 'service_error', failed.get('http_status') != 429,
            failed.get('billing_ok') is not False, failed.get('cost_unknown') is not True,
            failed.get('reserved_cost_usd') != str(RESERVE),
            failed.get('error_type') != 'HTTPError')):
        raise ValueError('Preserved DEV-033 failure differs')
    metadata = (failed.get('raw_error_response') or {}).get('error', {}).get('metadata', {})
    if metadata.get('provider_name') != NAME or metadata.get('limit_source') != 'upstream_provider_shared_pool':
        raise ValueError('DEV-033 provider error evidence differs')
    return {'attempted': 33, 'successful': 32, 'failed_id': 'DEV-033',
            'failed_status': 'HTTP429_unknown_billing',
            'raw_result_sha256': result_binding['sha256'],
            'journal_sha256': journal_binding['sha256'],
            'retry_failed_record': False}


def verify(plan_path, expected_sha=None):
    plan_path = Path(plan_path).resolve()
    if expected_sha is not None and smoke.sha(plan_path) != expected_sha:
        raise ValueError('Suffix plan hash mismatch')
    plan = json.loads(plan_path.read_text())
    if plan.get('contract') != CONTRACT or plan.get('offline_only') is not True or plan.get('inference_performed') is not False or plan.get('reference_labels_read') is not False:
        raise ValueError('Invalid suffix contract')
    if plan.get('configuration_id') != CID or plan.get('reasoning') != MODE or plan.get('condition') != VARIANT or plan.get('phase') != 'development_suffix':
        raise ValueError('Suffix condition differs')
    if plan.get('record_ids') != [f'DEV-{i:03}' for i in range(34, 61)] or plan.get('excluded_failed_id') != 'DEV-033' or plan.get('original_timing_preserved') is not False:
        raise ValueError('Suffix must be exactly never-sent DEV-034 through DEV-060')
    if smoke.source(plan['frozen_execution']) != FROZEN or smoke.source(plan['route_audit']) != ROUTE:
        raise ValueError('Frozen source binding differs')
    frozen = json.loads(FROZEN.read_text())
    config, _, evidence, inputs, schema, instruction, _ = admission._checked(frozen, ROOT, CID, VARIANT)
    if config['controls']['effort'] != MODE or evidence['adapter'] != 'openrouter_paid_v1':
        raise ValueError('Frozen on/P2 controls differ')
    prefix = stopped_prefix(plan['original_result'], plan['original_journal'], evidence['requests'][3:])
    if plan.get('original_prefix') != prefix:
        raise ValueError('Preserved prefix audit differs')
    requests = evidence['requests'][3+33:]
    if len(requests) != 27 or [r['record_ids'] for r in requests] != [[f'DEV-{i:03}'] for i in range(34, 61)]:
        raise ValueError('Frozen suffix request order differs')
    if plan.get('requests') != [r['client_request'] for r in requests]:
        raise ValueError('Suffix request bindings differ')
    for index, binding in enumerate(plan['requests'], start=33):
        envelope = json.loads(smoke.source(binding).read_text())
        if envelope['adapter_controls'] != config['controls']['adapter_controls'] or envelope['request']['messages'][1]['content'] != json.dumps({'feedback': inputs[index]['feedback']}):
            raise ValueError('Suffix request controls or input differs')
    endpoint = smoke.endpoint_from_audit(ROUTE)
    reserve = paid.reservation(endpoint, 4096, Decimal('0.1'), Decimal('0.9'))
    if reserve != RESERVE or plan.get('per_call_reserve_usd') != str(reserve) or plan.get('twentyseven_call_bound_usd') != str(reserve * 27) or plan.get('proposed_partition_cap_usd') != str(CAP) or reserve * 27 > CAP:
        raise ValueError('Suffix reserve or partition cap differs')
    output = (ROOT / plan['new_output']).resolve()
    output.relative_to(RESULT)
    if output.exists() or Path(str(output) + '.attempts.jsonl').exists():
        raise FileExistsError('Suffix output already exists')
    return {'records': 27, 'record_ids': plan['record_ids'], 'preserved_prefix': prefix,
            'twentyseven_call_bound_usd': str(BOUND), 'proposed_partition_cap_usd': str(CAP)}


def build():
    if PLAN.exists():
        raise FileExistsError('Suffix plan already exists')
    frozen = json.loads(FROZEN.read_text())
    _, _, evidence, *_ = admission._checked(frozen, ROOT, CID, VARIANT)
    result_binding, journal_binding = smoke.bind(SOURCE), smoke.bind(JOURNAL)
    prefix = stopped_prefix(result_binding, journal_binding, evidence['requests'][3:])
    plan = {'contract': CONTRACT, 'offline_only': True, 'inference_performed': False,
            'reference_labels_read': False, 'configuration_id': CID, 'reasoning': MODE,
            'condition': VARIANT, 'phase': 'development_suffix',
            'record_ids': [f'DEV-{i:03}' for i in range(34, 61)],
            'excluded_failed_id': 'DEV-033', 'original_timing_preserved': False,
            'timing_note': 'New never-sent suffix after original HTTP429; DEV-033 remains failed and no original counterbalanced timing is claimed.',
            'frozen_execution': smoke.bind(FROZEN), 'route_audit': smoke.bind(ROUTE),
            'original_result': result_binding, 'original_journal': journal_binding,
            'original_prefix': prefix,
            'requests': [r['client_request'] for r in evidence['requests'][3+33:]],
            'per_call_reserve_usd': str(RESERVE), 'twentyseven_call_bound_usd': str(BOUND),
            'proposed_partition_cap_usd': str(CAP),
            'new_output': str((RESULT / 'on-p2-dev034-060-suffix.jsonl').relative_to(ROOT))}
    with PLAN.open('x') as stream:
        json.dump(plan, stream, indent=2)
        stream.write('\n')
    verify(PLAN)
    print(PLAN.relative_to(ROOT), smoke.sha(PLAN))


def review_execution(plan_path, plan_sha, budget_path, partition_id, review_path):
    summary = verify(plan_path, plan_sha)
    Path(plan_path).resolve().relative_to(RESULT)
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
            receipt.get('preserved_original_result_sha256') != summary['preserved_prefix']['raw_result_sha256'],
            receipt.get('continue_on_known_billing_intrinsic_invalid') is not True)):
        raise ValueError('Missing exact suffix root review')
    budget = json.loads(budget_path.read_text())
    if budget.get('version') != 'paid-partitions-v1' or budget.get('master_ledger') != str((ROOT / 'results/openrouter-paid-budget.jsonl').resolve()):
        raise ValueError('Budget manifest is not v2 master allocation')
    entries = [e for e in budget.get('partitions', []) if e.get('id') == partition_id]
    if len(entries) != 1:
        raise ValueError('Missing unique suffix partition')
    entry = entries[0]
    if (entry.get('model'), entry.get('provider'), entry.get('reasoning')) != (MODEL, PROVIDER, MODE):
        raise ValueError('Suffix partition route differs')
    if not BOUND <= paid.number(entry.get('cap_usd')) <= CAP:
        raise ValueError('Suffix partition cap differs')
    if not str(Path(entry['child_ledger']).resolve()).startswith(str(ROOT / 'results') + '/'):
        raise ValueError('Suffix child ledger outside results')
    return json.loads(Path(plan_path).read_text()), summary


def execute(plan_path, plan_sha, budget_path, partition_id, review_path, env_file=None, timeout=300):
    plan, _ = review_execution(plan_path, plan_sha, budget_path, partition_id, review_path)
    if timeout != 300:
        raise ValueError('Frozen 300-second controller timeout required')
    frozen = json.loads(FROZEN.read_text())
    config, _, _, inputs, schema, instruction, _ = admission._checked(frozen, ROOT, CID, VARIANT)
    composed = compose_instruction((ROOT / config['baseline_instruction']['file']).read_text(),
                                   VARIANT, role='system', parent_baseline_id=config['parent_baseline_id'], root=ROOT)
    if composed['instruction'] != instruction:
        raise ValueError('Frozen instruction differs')
    requests = [json.loads(smoke.source(binding).read_text())['request'] for binding in plan['requests']]
    output = (ROOT / plan['new_output']).resolve()
    journal = Path(str(output) + '.attempts.jsonl')
    if output.exists() or journal.exists():
        raise FileExistsError('Suffix output already exists')
    token = load_key(env_file)
    catalog = fetch('/models', timeout=timeout)
    endpoint_response = fetch('/models/' + quote(MODEL, safe='/') + '/endpoints', timeout=timeout)
    audited = smoke.endpoint_from_audit(ROUTE)
    model, endpoint = smoke.live_endpoint(catalog, endpoint_response, audited)
    controls = config['controls']['adapter_controls']
    args = SimpleNamespace(model=MODEL, reasoning=MODE)
    for index, request in enumerate(requests, start=33):
        expected = paid.make_payload(MODEL, endpoint, inputs[index]['feedback'], instruction,
                                     schema, MODE, 4096, Decimal('0.1'), Decimal('0.9'), model)
        if request != expected or paid.paid_adapter_controls(args, endpoint, request) != controls:
            raise ValueError('Live suffix request differs from frozen exact bytes')
    reserve = paid.reservation(endpoint, 4096, Decimal('0.1'), Decimal('0.9'))
    if reserve != RESERVE:
        raise ValueError('Live suffix reserve differs')
    ledger = partitions.open_partition(ROOT / 'results/openrouter-paid-budget.jsonl',
                                       budget_path, partition_id, MODEL, PROVIDER, MODE)
    attempted = 0
    completed = False
    terminal_status = None
    try:
        with output.open('x') as out, journal.open('x') as audit:
            for index, request in enumerate(requests, start=33):
                row = inputs[index]
                attempt = ledger.reserve(reserve, row['id'])
                attempted += 1
                record = {'id': row['id'], 'phase': 'development_suffix', 'attempt_id': attempt,
                          'requested_model': MODEL, 'reasoning_effort': MODE,
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
                                              'original_result_sha256': plan['original_result']['sha256'],
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
                                 'planned_records': 27, 'completed': completed,
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
        build()
    elif args.execute and all((args.plan, args.sha256, args.budget_manifest, args.partition_id, args.review)) and not args.build:
        execute(args.plan, args.sha256, args.budget_manifest, args.partition_id, args.review, args.env_file, args.timeout)
    elif args.plan and args.sha256 and not any((args.build, args.execute, args.budget_manifest, args.partition_id, args.review)):
        print(json.dumps(verify(args.plan, args.sha256), sort_keys=True))
    else:
        parser.error('Use --build, offline --plan PATH --sha256 HASH, or full reviewed --execute arguments')


if __name__ == '__main__':
    main()
