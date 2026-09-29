#!/usr/bin/env python3
"""Offline execution candidate for the frozen Qwen3.6 reasoning-on fresh plans.

This isolates the reviewed Qwen27 transport/lifecycle implementation in a
private module. Nothing in the Qwen27 runner or its global planner is changed.
"""
import argparse
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
from urllib.parse import quote

import qwen36_on_fresh_repeat_study as study
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
    CONFIGS = {study.CONFIG: {'effort': 'on', 'historical_continue_on_invalid': False,
                              'proposed_child_budget': study.PROPOSED_CHILD_USD}}
    ORDERS = study.ORDERS
    MODEL = study.MODEL
    PROVIDER = study.PROVIDER
    PROVIDER_NAME = study.PROVIDER_NAME
    INPUT_PRICE = study.INPUT_PRICE
    OUTPUT_PRICE = study.OUTPUT_PRICE
    MAX_TOKENS = study.MAX_TOKENS
    TIMEOUT = study.TIMEOUT
    sha = staticmethod(study.sha)
    digest = staticmethod(study.digest)

    @staticmethod
    def verify(config, fresh_pass, expected_sha):
        if config != study.CONFIG:
            raise ValueError('Unsupported exact configuration')
        return study.verify(fresh_pass, expected_sha)


_spec = importlib.util.spec_from_file_location('_qwen36_on_private_transport', SHARED_SOURCE)
if _spec is None or _spec.loader is None:
    raise RuntimeError('Reviewed shared executor unavailable')
runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runner)
runner.study = _Study
runner.__file__ = __file__
runner.RECEIPT_SCHEMA = 'qwen36-on-fresh-matched3-root-review-v1'
runner.EXECUTION_SCHEMA = 'qwen36-on-fresh-matched3-execution-v1'
runner.EXECUTION_MANIFEST = study.BASE / 'execution-manifest.json'
runner.CONTINUE_INTRINSIC_INVALID = False


def execution_plan():
    plans = {}
    for fresh_pass in study.ORDERS:
        target = study.BASE / fresh_pass / 'manifest.json'
        digest = study.sha(target)
        study.verify(fresh_pass, digest)
        plans[fresh_pass] = digest
    sources = ('qwen36_on_fresh_repeat_study.py',
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
        'test_sha256': study.sha(study.ROOT / 'tests/test_qwen36_on_fresh_repeat_execution.py'),
    }


def live_controls(plan, condition):
    if plan.get('configuration_id') != study.CONFIG or condition not in study.CONDITIONS:
        raise ValueError('Unsupported configuration or condition')
    frozen = study.source_rows('P0')['DEV-001']['provider_endpoint']
    catalog = paid.fetch('/models', timeout=120)
    endpoints = paid.fetch('/models/' + quote(study.MODEL, safe='/') + '/endpoints', timeout=120)
    model, endpoint = paid.select_endpoint(study.MODEL, study.PROVIDER, catalog, endpoints,
                                           study.INPUT_PRICE, study.OUTPUT_PRICE)
    critical = ('tag', 'provider_name', 'quantization', 'model_id', 'status',
                'context_length', 'max_prompt_tokens', 'max_completion_tokens',
                'supported_parameters', 'pricing')
    if any(endpoint.get(key) != frozen.get(key) for key in critical):
        raise ValueError('Live endpoint route, limits or price differs')
    if paid.reasoning(model, endpoint, 'on') != {'enabled': True}:
        raise ValueError('Live reasoning control differs')
    reserve = paid.reservation(endpoint, study.MAX_TOKENS,
                               study.INPUT_PRICE, study.OUTPUT_PRICE)
    if reserve != Decimal('0.0299008') or reserve > study.PROPOSED_CHILD_USD:
        raise ValueError('Live reserve differs from reviewed amount')
    inputs = {r['id']: r['feedback'] for r in study.input_rows()}
    for request in plan['conditions'][condition]['development']:
        payload = request['payload']
        rebuilt = paid.make_payload(study.MODEL, endpoint, inputs[request['record_id']],
                                    payload['messages'][0]['content'],
                                    payload['response_format']['json_schema']['schema'],
                                    'on', study.MAX_TOKENS, study.INPUT_PRICE,
                                    study.OUTPUT_PRICE, model)
        if rebuilt != payload:
            raise ValueError('Live adapter would change frozen payload')
    return model, endpoint, reserve


runner.execution_plan = execution_plan
runner.live_controls = live_controls


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
