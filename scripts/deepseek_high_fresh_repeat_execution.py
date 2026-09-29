#!/usr/bin/env python3
"""Offline execution candidate for the frozen DeepSeek V4.1 Flash high fresh plans.

This isolates the reviewed Qwen27 transport/lifecycle implementation in a
private module. Nothing in the Qwen27 runner or its global planner is changed.
"""
import argparse
import base64
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
from urllib.parse import quote

import deepseek_high_fresh_repeat_study as study
import openrouter_paid_benchmark as paid


SHARED_SOURCE = study.ROOT / 'scripts/qwen27_fresh_repeat_execution.py'


class _BasePath:
    """Translate the shared runner's config/repeat layout to this one-config series."""

    def __init__(self, path):
        self.path = Path(path)

    def __truediv__(self, child):
        if child != study.CONFIG:
            raise ValueError('Unsupported exact configuration path')
        return self.path


class _Study:
    __file__ = study.__file__
    ROOT = study.ROOT
    BASE = _BasePath(study.BASE)
    CONFIGS = {study.CONFIG: {'effort': study.EFFORT, 'historical_continue_on_invalid': True,
                              'proposed_child_budget': study.PROPOSED_CHILD}}
    ORDERS = study.ORDERS
    MODEL = study.MODEL
    PROVIDER = study.PROVIDER
    PROVIDER_NAME = study.PROVIDER_NAME
    INPUT_PRICE = Decimal('0.10')
    OUTPUT_PRICE = Decimal('0.50')
    MAX_TOKENS = study.MAX_TOKENS
    TIMEOUT = study.TIMEOUT
    sha = staticmethod(study.sha)
    digest = staticmethod(study.digest)

    @staticmethod
    def verify(config, fresh_pass, expected_sha):
        if config != study.CONFIG:
            raise ValueError('Unsupported exact configuration')
        return study.verify(fresh_pass, expected_sha)


_spec = importlib.util.spec_from_file_location('_deepseek_high_private_transport', SHARED_SOURCE)
if _spec is None or _spec.loader is None:
    raise RuntimeError('Reviewed shared executor unavailable')
runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runner)
runner.study = _Study
runner.__file__ = __file__
runner.RECEIPT_SCHEMA = 'deepseek-high-fresh-matched3-root-review-v1'
runner.EXECUTION_SCHEMA = 'deepseek-high-fresh-matched3-execution-v1'
runner.EXECUTION_MANIFEST = study.BASE / 'execution-manifest.json'
runner.CONTINUE_INTRINSIC_INVALID = True


def execution_plan():
    plans = {}
    for fresh_pass in study.ORDERS:
        target = study.BASE / fresh_pass / 'manifest.json'
        digest = study.sha(target)
        study.verify(fresh_pass, digest)
        plans[fresh_pass] = digest
    sources = ('deepseek_high_fresh_repeat_study.py',
               'qwen27_fresh_repeat_execution.py',
               'openrouter_benchmark.py', 'openrouter_paid_benchmark.py',
               'paid_budget_partitions_v2.py', 'openrouter_budget_v2.py',
               'prompt_admission.py')
    return {
        'schema': runner.EXECUTION_SCHEMA,
        'status': 'offline_frozen_not_approved',
        'controller_sha256': study.sha(__file__),
        'planner_sha256': study.sha(study.__file__),
        'plans_sha256': {study.CONFIG: plans},
        'source_code_sha256': {name: study.sha(study.ROOT / 'scripts' / name)
                               for name in sources},
        'test_sha256': study.sha(study.ROOT / 'tests/test_deepseek_high_fresh_repeat_execution.py'),
    }


def live_controls(plan, condition):
    if plan.get('configuration_id') != study.CONFIG or condition not in study.CONDITIONS:
        raise ValueError('Unsupported configuration or condition')
    frozen = json.loads((study.ROOT / study.ROUTE_AUDIT).read_text())['selected_endpoint']
    catalog = paid.fetch('/models', timeout=120)
    endpoints = paid.fetch('/models/' + quote(study.MODEL, safe='/') + '/endpoints', timeout=120)
    model, endpoint = paid.select_endpoint(study.MODEL, study.PROVIDER, catalog, endpoints,
                                           Decimal('0.10'), Decimal('0.50'))
    critical = ('tag', 'provider_name', 'quantization', 'model_id', 'status',
                'context_length', 'max_prompt_tokens', 'max_completion_tokens',
                'supported_parameters', 'pricing')
    if any(endpoint.get(key) != frozen.get(key) for key in critical):
        raise ValueError('Live endpoint route, limits or price differs')
    if paid.reasoning(model, endpoint, study.EFFORT) != {'enabled': True, 'effort': study.EFFORT}:
        raise ValueError('Live reasoning control differs')
    reserve = paid.reservation(endpoint, study.MAX_TOKENS,
                               Decimal('0.10'), Decimal('0.50'))
    if reserve != study.RESERVE or reserve > study.PROPOSED_CHILD:
        raise ValueError('Live reserve differs from reviewed amount')
    inputs = {r['id']: r['feedback'] for r in study.input_rows()}
    for request in plan['conditions'][condition]['development']:
        payload = request['payload']
        rebuilt = paid.make_payload(study.MODEL, endpoint, inputs[request['record_id']],
                                    payload['messages'][0]['content'],
                                    payload['response_format']['json_schema']['schema'],
                                    study.EFFORT, study.MAX_TOKENS, Decimal('0.10'),
                                    Decimal('0.50'), model)
        if rebuilt != payload:
            raise ValueError('Live adapter would change frozen payload')
    return model, endpoint, reserve


_strict_closure = runner.verify_phase_closure


def verify_phase_closure(plan, condition, phase):
    """Accept a completed development with known, intrinsic invalids only.

    Smokes retain the reviewed all-valid verifier. This verifier reads no open
    stage as a predecessor and checks each retained invalid against its raw
    response, known charge and the execution continuation policy.
    """
    if phase == 'smoke':
        return _strict_closure(plan, condition, phase)
    if phase != 'development' or plan.get('configuration_id') != study.CONFIG:
        raise ValueError('Unsupported phase or configuration')
    fresh_pass = plan['fresh_pass']
    manifest = study.BASE / fresh_pass / 'manifest.json'
    manifest_sha = study.sha(manifest)
    study.verify(fresh_pass, manifest_sha)
    requests = plan['conditions'][condition][phase]
    folder, claim, journal_path, attempts_path = runner.phase_paths(
        study.CONFIG, fresh_pass, condition, phase)
    raw_path = folder / (phase + '.responses.jsonl')
    for path in (claim, journal_path, attempts_path, raw_path):
        if not path.is_file():
            raise ValueError('Phase closure evidence missing: ' + path.name)
    claim_data = json.loads(claim.read_text())
    if (claim_data.get('configuration_id'), claim_data.get('fresh_pass'),
            claim_data.get('condition'), claim_data.get('phase'),
            claim_data.get('manifest_sha256')) != (
            study.CONFIG, fresh_pass, condition, phase, manifest_sha):
        raise ValueError('Phase claim differs from frozen plan')
    attempts = runner.jsonl(attempts_path)
    raw = runner.jsonl(raw_path)
    events = runner.jsonl(journal_path)
    frozen_endpoint = json.loads((study.ROOT / study.ROUTE_AUDIT).read_text())['selected_endpoint']
    critical = ('tag', 'provider_name', 'quantization', 'model_id', 'status',
                'context_length', 'max_prompt_tokens', 'max_completion_tokens',
                'supported_parameters', 'pricing')
    ids = [x['record_id'] for x in requests]
    if (len(attempts) != len(ids) or len(raw) != len(ids) or
            [x.get('id') for x in attempts] != ids or
            [x.get('id') for x in raw] != ids):
        raise ValueError('Completed phase lacks exact ordered attempts and raw bodies')
    attempt_ids = [x.get('attempt_id') for x in attempts]
    if any(not isinstance(x, str) or not x for x in attempt_ids) or len(set(attempt_ids)) != len(ids):
        raise ValueError('Attempt identities missing or duplicated')
    expected_events = [{'event': 'phase_started', 'configuration_id': study.CONFIG,
                        'fresh_pass': fresh_pass, 'condition': condition, 'phase': phase}]
    for request, record, captured in zip(requests, attempts, raw):
        if (record.get('configuration_id'), record.get('fresh_pass'),
                record.get('condition'), record.get('phase'),
                record.get('manifest_sha256'), record.get('request_sha256'),
                record.get('input_sha256'), record.get('instruction_sha256')) != (
                study.CONFIG, fresh_pass, condition, phase, manifest_sha,
                request['request_sha256'], request['input_sha256'],
                request['instruction_sha256']):
            raise ValueError('Attempt differs from frozen request identity')
        if (record.get('request') != request['payload'] or
                study.digest(json.dumps(record['request'], sort_keys=True)) != request['request_sha256'] or
                record.get('reference_labels_read') is not False or
                record.get('reasoning_effort') != study.EFFORT or
                record.get('requested_model') != study.MODEL):
            raise ValueError('Attempt request or label isolation differs')
        if (record.get('billing_ok') is not True or record.get('cost_unknown') is not False or
                record.get('observed_cost_usd') is None or
                record.get('response_diagnostic', {}).get('passed') is not True and
                record.get('status') == 'ok'):
            raise ValueError('Completed attempt lacks known billing or response admission')
        actual = paid.number(record['observed_cost_usd'])
        reserved = paid.number(record.get('reserved_cost_usd'))
        if actual < 0 or actual > reserved:
            raise ValueError('Observed charge exceeds reservation')
        body = record.get('raw_response')
        if not isinstance(body, dict):
            raise ValueError('Completed attempt lacks parsed raw response')
        endpoint = record.get('provider_endpoint')
        model = record.get('model_catalog_entry')
        if not isinstance(endpoint, dict) or not isinstance(model, dict):
            raise ValueError('Completed attempt lacks route source')
        if (any(endpoint.get(key) != frozen_endpoint.get(key) for key in critical) or
                model.get('id') != study.MODEL or
                paid.reasoning(model, endpoint, study.EFFORT) !=
                {'enabled': True, 'effort': study.EFFORT}):
            raise ValueError('Completed attempt route differs from reviewed current route')
        recalculated = runner.classify(body, model, endpoint)
        for key in ('status', 'prediction', 'returned_model', 'returned_provider',
                    'usage', 'finish_reason'):
            if record.get(key) != recalculated.get(key):
                raise ValueError('Attempt classification differs from raw response')
        if (record.get('usage') != body.get('usage') or
                paid.number((body.get('usage') or {}).get('cost')) != actual or
                body.get('provider') != study.PROVIDER_NAME or
                body.get('model') not in paid.allowed_returned_models(study.MODEL, endpoint) or
                endpoint.get('tag') != study.PROVIDER or
                not runner.continue_record(record, phase)):
            raise ValueError('Completed response violates route, cost or continuation policy')
        try:
            body_bytes = base64.b64decode(captured.get('body_base64', ''), validate=True)
            parsed = json.loads(body_bytes)
        except (ValueError, TypeError):
            raise ValueError('Captured raw body cannot be parsed') from None
        if (captured.get('attempt_id'), captured.get('request_sha256'),
                captured.get('http_status'), captured.get('body_truncated_at_limit'),
                captured.get('read_error'), parsed) != (
                record['attempt_id'], request['request_sha256'], 200, False, None, body):
            raise ValueError('Captured raw response differs from attempt')
        expected_events.extend([
            {'event': 'request_intent', 'id': request['record_id'],
             'request_sha256': request['request_sha256']},
            {'event': 'request_started', 'id': request['record_id'],
             'attempt_id': record['attempt_id'], 'request_sha256': request['request_sha256']},
            {'event': 'request_finished', 'id': request['record_id'],
             'attempt_id': record['attempt_id'], 'status': record['status'],
             'billing_ok': True, 'cost_unknown': False,
             'observed_cost_usd': record['observed_cost_usd']},
        ])
    expected_events.append({'event': 'phase_completed', 'configuration_id': study.CONFIG,
                            'fresh_pass': fresh_pass, 'condition': condition, 'phase': phase,
                            'request_count': len(requests), 'attempt_ids': attempt_ids})
    if len(events) != len(expected_events):
        raise ValueError('Completed lifecycle event count differs')
    for actual, expected in zip(events, expected_events):
        if any(actual.get(key) != value for key, value in expected.items()):
            raise ValueError('Completed lifecycle ordering or binding differs')
    return {'manifest_sha256': manifest_sha, 'journal_sha256': study.sha(journal_path),
            'attempts_sha256': study.sha(attempts_path),
            'responses_sha256': study.sha(raw_path)}


runner.execution_plan = execution_plan
runner.live_controls = live_controls
runner.verify_phase_closure = verify_phase_closure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('freeze')
    verify = sub.add_parser('verify')
    verify.add_argument('--execution-manifest-sha256', required=True)
    for action in ('smoke', 'development', 'inspect'):
        p = sub.add_parser(action)
        p.add_argument('--fresh-pass', required=True, choices=tuple(study.ORDERS))
        p.add_argument('--condition', required=True, choices=study.CONDITIONS)
        p.add_argument('--manifest-sha256', required=True)
        if action == 'inspect':
            p.add_argument('--note', required=True)
        else:
            p.add_argument('--root-review-receipt', required=True)
            p.add_argument('--env-file')
    args = parser.parse_args()
    if args.action == 'freeze':
        print(runner.freeze())
    elif args.action == 'verify':
        runner.verify_execution_manifest(args.execution_manifest_sha256)
        print('verified execution manifest')
    elif args.action == 'inspect':
        runner.inspect(study.CONFIG, args.fresh_pass, args.condition,
                       args.manifest_sha256, args.note)
    else:
        runner.execute(study.CONFIG, args.fresh_pass, args.condition,
                       args.action, args.manifest_sha256,
                       args.root_review_receipt, args.env_file)


if __name__ == '__main__':
    main()
