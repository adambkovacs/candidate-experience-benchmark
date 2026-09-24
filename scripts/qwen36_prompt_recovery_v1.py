#!/usr/bin/env python3
"""Freeze and verify Qwen3.6 recovery plans; execute only with exact root review.

Original attempts and the original schedule remain immutable.
"""
import argparse
import hashlib
import json
import time
import urllib.error
from types import SimpleNamespace
from urllib.parse import quote
from decimal import Decimal
from pathlib import Path

import openrouter_paid_benchmark as paid
import paid_budget_partitions_v2 as partitions
from development_benchmark import valid
from frozen_prompt_variants import compose_instruction
from openrouter_benchmark import allowed_returned_models, fetch, load_key
import prompt_admission as admission
import prompt_execution_gates as gates

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / 'results/qwen36-prompt-recovery-v1'
ORIGINAL = ROOT / 'results/prompt-comparison-v1-2026-09-24'
FROZEN = ORIGINAL / 'hosted-execution.json'
ROUTE = ROOT / 'results/hosted-qwen-recovery-route-audit-2026-09-24.json'
MODEL = 'qwen/qwen3.6-35b-a3b'
PROVIDER = 'akashml/fp8'
NAME = 'AkashML'
CAP = Decimal('0.09')
RESERVE = Decimal('0.0299008')
CONTRACT = 'qwen36-prompt-recovery-smoke-v1'
ORDER = (('on', 'P1'), ('on', 'P2'), ('off', 'P2'), ('off', 'P1'))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind(path):
    path = Path(path).resolve()
    return {'file': str(path.relative_to(ROOT)), 'sha256': sha(path)}


def source(binding):
    path = (ROOT / binding['file']).resolve()
    path.relative_to(ROOT)
    if sha(path) != binding['sha256']:
        raise ValueError('Changed source: ' + binding['file'])
    return path


def endpoint_from_audit(path):
    audit = json.loads(path.read_text())
    response = audit['responses'][MODEL]
    if response['status'] != 200:
        raise ValueError('Route audit did not succeed')
    endpoints = response['parsed_response']['data']['endpoints']
    matches = [e for e in endpoints if e.get('tag') == PROVIDER]
    if len(matches) != 1:
        raise ValueError('Exact AkashML endpoint absent or ambiguous')
    endpoint = matches[0]
    if any((endpoint.get('model_id') != MODEL,
            endpoint.get('provider_name') != NAME,
            endpoint.get('quantization') != 'fp8',
            endpoint.get('status') != 0,
            endpoint.get('context_length') != 262144,
            endpoint.get('pricing', {}).get('prompt') != '0.0000001',
            endpoint.get('pricing', {}).get('completion') != '0.0000009')):
        raise ValueError('AkashML route or price changed')
    if not {'reasoning', 'max_tokens', 'temperature', 'structured_outputs'} <= set(endpoint['supported_parameters']):
        raise ValueError('Required AkashML controls absent')
    return endpoint


def original_state(mode, variant, paths):
    folder = ORIGINAL / 'runs' / f'openrouter-paid-qwen36-35b-a3b-{mode}'
    result = folder / variant / 'smoke.jsonl'
    development = folder / variant / 'development.jsonl'
    if development.exists():
        raise ValueError('Original development already started')
    if (mode, variant) == ('on', 'P1'):
        if result != paths['historical_result']:
            raise ValueError('Original result binding differs')
        rows = [json.loads(x) for x in result.read_text().splitlines() if x.strip()]
        if len(rows) != 1 or any((rows[0].get('id') != 'DEV-001',
                                  rows[0].get('status') != 'service_error',
                                  rows[0].get('http_status') != 429,
                                  rows[0].get('cost_unknown') is not True,
                                  rows[0].get('billing_ok') is not False,
                                  rows[0].get('reserved_cost_usd') != str(RESERVE))):
            raise ValueError('Historical HTTP429 outcome differs')
    else:
        if result.exists():
            raise ValueError('Original smoke result unexpectedly exists')
        if (mode, variant) == ('off', 'P2'):
            log = paths['historical_log'].read_text()
            if 'Schedule journal is locked by another operation' not in log or '/chat/completions' in log:
                raise ValueError('Original schedule-lock evidence differs')
    block = json.loads(paths['provider_block'].read_text())
    expected = {('on', 'P1'): 'blocked_after_http429',
                ('on', 'P2'): 'blocked_same_provider_pool',
                ('off', 'P2'): 'blocked_same_provider_pool_before_inference',
                ('off', 'P1'): 'blocked_same_provider_pool_before_inference'}[(mode, variant)]
    if block['conditions'][variant] != expected:
        raise ValueError('Original provider block differs')


def verify(path, expected_sha=None):
    path = Path(path).resolve()
    if expected_sha is not None and sha(path) != expected_sha:
        raise ValueError('Recovery plan hash mismatch')
    plan = json.loads(path.read_text())
    if plan.get('contract') != CONTRACT or plan.get('offline_only') is not True or plan.get('inference_performed') is not False or plan.get('reference_labels_read') is not False:
        raise ValueError('Invalid offline recovery contract')
    mode, variant = plan.get('reasoning'), plan.get('condition')
    if (mode, variant) not in ORDER or plan.get('configuration_id') != f'openrouter-paid-qwen36-35b-a3b-{mode}':
        raise ValueError('Invalid recovery condition')
    if plan.get('phase') != 'smoke3' or plan.get('record_ids') != ['DEV-001', 'DEV-002', 'DEV-003']:
        raise ValueError('Recovery smoke membership changed')
    if plan.get('recovery_order') != [f'{m}/{v}' for m, v in ORDER] or plan.get('original_timing_preserved') is not False:
        raise ValueError('Recovery timing disclosure changed')
    paths = {key: source(value) for key, value in plan['sources'].items()}
    if paths['frozen_execution'] != FROZEN or paths['route_audit'] != ROUTE:
        raise ValueError('Original source path differs')
    endpoint = endpoint_from_audit(paths['route_audit'])
    frozen = json.loads(paths['frozen_execution'].read_text())
    config, _, evidence, inputs, _, _, _ = admission._checked(frozen, ROOT, plan['configuration_id'], variant)
    controls = config['controls']
    adapter = controls['adapter_controls']
    if evidence['adapter'] != 'openrouter_paid_v1' or controls['model'] != MODEL or controls['effort'] != mode or controls['quantization'] != 'fp8' or controls['output_reserve_tokens'] != 4096 or controls['context_tokens'] != 262144:
        raise ValueError('Frozen paid controls differ')
    if adapter['provider_tag'] != PROVIDER or adapter['provider_name'] != NAME or adapter['reasoning_effort'] != mode:
        raise ValueError('Frozen route differs')
    rows = evidence['requests'][:3]
    if [r['record_ids'] for r in rows] != [[f'DEV-{i:03}'] for i in range(1, 4)]:
        raise ValueError('Smoke must use DEV-001 through DEV-003')
    expected_requests = [r['client_request'] for r in rows]
    if plan['requests'] != expected_requests:
        raise ValueError('Recovery request bindings differ from frozen smoke')
    for index, binding in enumerate(plan['requests']):
        envelope = json.loads(source(binding).read_text())
        if envelope['adapter_controls'] != adapter or envelope['request'] != gates.json_bound(expected_requests[index], ROOT)['request']:
            raise ValueError('Recovery request drift')
        request = envelope['request']
        if any((request.get('model') != MODEL,
                request.get('reasoning') != {'enabled': mode == 'on'},
                request.get('max_tokens') != 4096,
                request.get('temperature') != 0,
                request.get('stream') is not False,
                request.get('provider') != {'only': [PROVIDER], 'allow_fallbacks': False, 'require_parameters': True,
                                            'max_price': {'prompt': 0.1, 'completion': 0.9, 'request': 0, 'image': 0}},
                request.get('response_format', {}).get('type') != 'json_schema',
                set(json.loads(request['messages'][1]['content'])) != {'feedback'},
                json.loads(request['messages'][1]['content'])['feedback'] != inputs[index]['feedback'])):
            raise ValueError('Request controls, input, or label isolation changed')
    original_state(mode, variant, paths)
    if (mode, variant) == ('on', 'P1'):
        historical = json.loads(paths['historical_result'].read_text().splitlines()[0])
        first = json.loads(source(plan['requests'][0]).read_text())['request']
        if historical.get('request') != first:
            raise ValueError('Historical HTTP429 request differs from recovery request')
    reserve = paid.reservation(endpoint, 4096, Decimal('0.1'), Decimal('0.9'))
    if reserve != RESERVE or plan.get('per_call_reserve_usd') != str(reserve) or plan.get('three_call_bound_usd') != str(3 * reserve) or plan.get('proposed_partition_cap_usd') != str(CAP) or 3 * reserve > CAP:
        raise ValueError('Smoke reserve or cap changed')
    output = (ROOT / plan['new_output']).resolve()
    output.relative_to(RESULT)
    if output.exists() or Path(str(output) + '.attempts.jsonl').exists():
        raise FileExistsError('Recovery output already exists')
    return {'condition': f'{mode}/{variant}', 'requests': 3, 'per_call_reserve_usd': str(reserve),
            'three_call_bound_usd': str(3 * reserve), 'proposed_partition_cap_usd': str(CAP),
            'historical_status': 'HTTP429 unknown cost' if (mode, variant) == ('on', 'P1') else
                                 'schedule lock before inference' if (mode, variant) == ('off', 'P2') else 'provider-pool block before inference'}


def build():
    if RESULT.exists():
        raise FileExistsError('Versioned recovery folder already exists')
    frozen = json.loads(FROZEN.read_text())
    endpoint_from_audit(ROUTE)
    RESULT.mkdir()
    for mode, variant in ORDER:
        cid = f'openrouter-paid-qwen36-35b-a3b-{mode}'
        _, _, evidence, *_ = admission._checked(frozen, ROOT, cid, variant)
        folder = ORIGINAL / 'runs' / cid
        sources = {'frozen_execution': bind(FROZEN), 'route_audit': bind(ROUTE),
                   'provider_block': bind(folder / 'provider-block.json')}
        if (mode, variant) == ('on', 'P1'):
            sources['historical_result'] = bind(folder / variant / 'smoke.jsonl')
        if (mode, variant) == ('off', 'P2'):
            sources['historical_log'] = bind(folder / variant / 'pre-inference-controller.log')
        plan = {'contract': CONTRACT, 'offline_only': True, 'inference_performed': False,
                'reference_labels_read': False, 'configuration_id': cid, 'reasoning': mode,
                'condition': variant, 'phase': 'smoke3', 'record_ids': ['DEV-001', 'DEV-002', 'DEV-003'],
                'recovery_order': [f'{m}/{v}' for m, v in ORDER], 'original_timing_preserved': False,
                'timing_note': 'New sequential recovery occurs after the original stopped schedule; original counterbalanced timing is not recovered.',
                'sources': sources, 'requests': [r['client_request'] for r in evidence['requests'][:3]],
                'per_call_reserve_usd': str(RESERVE), 'three_call_bound_usd': str(RESERVE * 3),
                'proposed_partition_cap_usd': str(CAP),
                'new_output': str((RESULT / f'{mode}-{variant.lower()}-smoke.jsonl').relative_to(ROOT))}
        destination = RESULT / f'{mode}-{variant.lower()}-smoke-plan.json'
        with destination.open('x') as stream:
            json.dump(plan, stream, indent=2)
            stream.write('\n')
        verify(destination)
        print(destination.relative_to(ROOT), sha(destination))


def review_execution(plan_path, plan_sha, budget_path, partition_id, review_path):
    """Check every approval binding before reading a key or making a request."""
    status = verify(plan_path, plan_sha)
    plan_path = Path(plan_path).resolve()
    plan_path.relative_to(RESULT)
    budget_path = Path(budget_path).resolve()
    budget_path.relative_to(ROOT)
    review_path = Path(review_path).resolve()
    review_path.relative_to(ROOT)
    review = json.loads(review_path.read_text())
    if any((review.get('approved') is not True,
            review.get('recovery_plan_sha256') != plan_sha,
            review.get('wrapper_sha256') != sha(__file__),
            review.get('budget_manifest_sha256') != sha(budget_path),
            review.get('partition_id') != partition_id,
            review.get('continue_on_known_billing_intrinsic_invalid') is not True)):
        raise ValueError('Missing exact root review')
    plan = json.loads(plan_path.read_text())
    position = ORDER.index((plan['reasoning'], plan['condition']))
    if position:
        prior_mode, prior_variant = ORDER[position - 1]
        prior_plan_path = RESULT / f'{prior_mode}-{prior_variant.lower()}-smoke-plan.json'
        prior_plan = json.loads(prior_plan_path.read_text())
        prior_journal = ROOT / (prior_plan['new_output'] + '.attempts.jsonl')
        if not prior_journal.is_file():
            raise ValueError('Prior recovery smoke lacks a terminal journal')
        events = [json.loads(line) for line in prior_journal.read_text().splitlines() if line.strip()]
        if not events or events[-1].get('event') != 'terminal' or events[-1].get('plan_sha256') != sha(prior_plan_path):
            raise ValueError('Prior recovery smoke lacks a bound terminal event')
    budget = json.loads(budget_path.read_text())
    if budget.get('version') != 'paid-partitions-v1' or budget.get('master_ledger') != str((ROOT / 'results/openrouter-paid-budget.jsonl').resolve()):
        raise ValueError('Budget manifest is not v2 master allocation')
    entries = [e for e in budget.get('partitions', []) if e.get('id') == partition_id]
    if len(entries) != 1:
        raise ValueError('Missing unique recovery partition')
    entry = entries[0]
    if (entry.get('model'), entry.get('provider'), entry.get('reasoning')) != (MODEL, PROVIDER, plan['reasoning']):
        raise ValueError('Recovery partition route differs')
    if not Decimal(status['three_call_bound_usd']) <= paid.number(entry.get('cap_usd')) <= CAP:
        raise ValueError('Recovery partition cap differs')
    if not str(Path(entry['child_ledger']).resolve()).startswith(str(ROOT / 'results') + '/'):
        raise ValueError('Recovery child ledger is outside results')
    return plan, status


def live_endpoint(catalog, endpoint_response, audited):
    model, endpoint = paid.select_endpoint(MODEL, PROVIDER, catalog, endpoint_response,
                                            Decimal('0.1'), Decimal('0.9'))
    stable = ('name', 'model_id', 'provider_name', 'tag', 'quantization', 'context_length',
              'max_completion_tokens', 'pricing')
    if any(endpoint.get(key) != audited.get(key) for key in stable):
        raise ValueError('Live AkashML route or price differs from reviewed audit')
    if endpoint.get('status') != 0 or paid.reasoning(model, endpoint, 'off') != {'enabled': False}:
        raise ValueError('Live route or reasoning controls differ')
    return model, endpoint


def continue_smoke(record):
    """Continue only known-billing intrinsic invalid outputs with a normal finish."""
    if not record.get('billing_ok') or record.get('cost_unknown') or record.get('prompt_response_diagnostics', {}).get('blockers'):
        return False
    if record.get('status') == 'ok':
        return True
    if record.get('status') != 'invalid_output':
        return False
    body = record.get('raw_response') or {}
    choices = body.get('choices') or []
    if len(choices) != 1 or choices[0].get('finish_reason') != 'stop':
        return False
    message = choices[0].get('message') or {}
    return not (choices[0].get('error') or message.get('refusal') or
                message.get('tool_calls') or message.get('function_call') or
                record.get('prompt_response_diagnostics', {}).get('blockers'))


def execute(plan_path, plan_sha, budget_path, partition_id, review_path, env_file=None, timeout=300):
    plan, _ = review_execution(plan_path, plan_sha, budget_path, partition_id, review_path)
    if timeout != 300:
        raise ValueError('Frozen 300-second controller timeout required')
    mode, variant = plan['reasoning'], plan['condition']
    frozen = json.loads(FROZEN.read_text())
    config, _, _, inputs, schema, instruction, _ = admission._checked(
        frozen, ROOT, plan['configuration_id'], variant)
    composed = compose_instruction((ROOT / config['baseline_instruction']['file']).read_text(),
                                   variant, role='system', parent_baseline_id=config['parent_baseline_id'], root=ROOT)
    if composed['instruction'] != instruction:
        raise ValueError('Frozen instruction audit differs')
    requests = [json.loads(source(binding).read_text())['request'] for binding in plan['requests']]
    output = (ROOT / plan['new_output']).resolve()
    journal = Path(str(output) + '.attempts.jsonl')
    if output.exists() or journal.exists():
        raise FileExistsError('Recovery output already exists')
    token = load_key(env_file)
    catalog = fetch('/models', timeout=timeout)
    endpoint_response = fetch('/models/' + quote(MODEL, safe='/') + '/endpoints', timeout=timeout)
    audited = endpoint_from_audit(ROUTE)
    model, endpoint = live_endpoint(catalog, endpoint_response, audited)
    controls = config['controls']['adapter_controls']
    args = SimpleNamespace(model=MODEL, reasoning=mode)
    for index, request in enumerate(requests):
        expected = paid.make_payload(MODEL, endpoint, inputs[index]['feedback'], instruction,
                                     schema, mode, 4096, Decimal('0.1'), Decimal('0.9'), model)
        if request != expected or paid.paid_adapter_controls(args, endpoint, request) != controls:
            raise ValueError('Live generated request differs from frozen exact bytes')
    reserve = paid.reservation(endpoint, 4096, Decimal('0.1'), Decimal('0.9'))
    if reserve != RESERVE:
        raise ValueError('Live reservation differs from reviewed bound')
    ledger = partitions.open_partition(ROOT / 'results/openrouter-paid-budget.jsonl',
                                       budget_path, partition_id, MODEL, PROVIDER, mode)
    completed = False
    attempted = 0
    terminal_status = None
    try:
        with output.open('x') as out, journal.open('x') as audit:
            for index, request in enumerate(requests):
                row = inputs[index]
                attempt = ledger.reserve(reserve, row['id'])
                attempted += 1
                record = {'id': row['id'], 'phase': 'smoke', 'attempt_id': attempt,
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
                          'budget_partition_id': partition_id, 'budget_ledger': str(Path(ledger.file.name).relative_to(ROOT)),
                          'aggregate_cap_usd': str(ledger.master_cap),
                          'continue_on_invalid_output': True,
                          'prompt_recovery': {'contract': CONTRACT, 'plan_sha256': plan_sha,
                                              'review_receipt_sha256': sha(review_path),
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
                    if not isinstance(choices, list) or len(choices) != 1:
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
                if not continue_smoke(record):
                    break
            else:
                completed = True
            paid.durable(audit, {'event': 'terminal', 'attempted_records': attempted,
                                 'planned_records': 3, 'completed': completed,
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
