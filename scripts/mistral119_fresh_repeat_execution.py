#!/usr/bin/env python3
"""Unfunded offline execution candidate for exact Mistral119 none/high fresh plans.

The reviewed Qwen27 lifecycle is loaded into an isolated module and bound to
these six plans. No stage has an implicit budget or dispatch authorization.
"""
import argparse
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
from urllib.parse import quote

import mistral119_fresh_repeat_study as study
import openrouter_paid_benchmark as paid

SHARED_SOURCE = study.ROOT / 'scripts/qwen27_fresh_repeat_execution.py'
RECEIPT_SCHEMA = 'mistral119-fresh-matched3-stage-review-v1'
EXECUTION_SCHEMA = 'mistral119-fresh-matched3-execution-v1'


class _Study:
    __file__ = study.__file__
    ROOT = study.ROOT
    BASE = study.BASE
    CONFIGS = {config: {'effort': spec['effort']} for config, spec in study.CONFIGS.items()}
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
    def verify(config, repeat, expected_sha):
        return study.verify(config, repeat, expected_sha)


_spec = importlib.util.spec_from_file_location('_mistral119_private_transport', SHARED_SOURCE)
if _spec is None or _spec.loader is None:
    raise RuntimeError('Reviewed shared executor unavailable')
runner = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(runner)
runner.study = _Study
runner.__file__ = __file__
runner.RECEIPT_SCHEMA = RECEIPT_SCHEMA
runner.EXECUTION_SCHEMA = EXECUTION_SCHEMA
runner.EXECUTION_MANIFEST = study.BASE / 'execution-manifest.json'
runner.CONTINUE_INTRINSIC_INVALID = False


def execution_plan():
    plans = {}
    for config in study.CONFIGS:
        plans[config] = {}
        for repeat in study.ORDERS:
            path = study.BASE / config / repeat / 'manifest.json'
            digest = study.sha(path)
            study.verify(config, repeat, digest)
            plans[config][repeat] = digest
    sources = ('mistral119_fresh_repeat_study.py',
               'qwen27_fresh_repeat_execution.py',
               'openrouter_benchmark.py', 'openrouter_paid_benchmark.py',
               'paid_budget_partitions_v2.py', 'openrouter_budget_v2.py',
               'prompt_admission.py', 'development_benchmark.py',
               'frozen_prompt_variants.py')
    return {
        'schema': EXECUTION_SCHEMA, 'status': 'offline_frozen_not_approved',
        'funding_status': 'unfunded_no_whole_series_cap_proposed',
        'controller_sha256': study.sha(__file__),
        'planner_sha256': study.sha(study.__file__),
        'plans_sha256': plans,
        'source_code_sha256': {name: study.sha(study.ROOT / 'scripts' / name)
                               for name in sources},
        'test_sha256': study.sha(study.ROOT / 'tests/test_mistral119_fresh_repeat_execution.py'),
    }


def review_receipt(path, config, repeat, condition, phase, manifest_sha):
    if config not in study.CONFIGS or repeat not in study.ORDERS or condition not in study.CONDITIONS:
        raise ValueError('Unsupported exact Mistral119 stage')
    receipt = json.loads(Path(path).read_text())
    if receipt.get('schema') != RECEIPT_SCHEMA or receipt.get('approved') is not True:
        raise ValueError('Exact root stage approval missing')
    if receipt.get('configuration_id') != config or receipt.get('stage') != f'{repeat}/{condition}/{phase}':
        raise ValueError('Root stage or configuration differs')
    if receipt.get('controller_sha256') != study.sha(__file__):
        raise ValueError('Root review controller hash differs')
    execution = runner.verify_execution_manifest(receipt.get('execution_manifest_sha256'))
    expected = execution['plans_sha256'][config]
    if receipt.get('plan_sha256') != expected or expected[repeat] != manifest_sha:
        raise ValueError('Root review frozen plan hashes differ')
    if receipt.get('master_ledger') != str(Path(runner.MASTER).resolve()):
        raise ValueError('Root review master ledger differs')
    binding = receipt.get('budget_manifest')
    if not isinstance(binding, dict) or set(binding) != {'path', 'sha256'}:
        raise ValueError('Bound budget manifest required')
    budget_path = runner.bound_file(binding)
    manifest = json.loads(budget_path.read_text())
    pid = receipt.get('partition_id')
    entries = [item for item in manifest.get('partitions', []) if item.get('id') == pid]
    if manifest.get('version') != 'paid-partitions-v1' or \
            manifest.get('master_ledger') != str(Path(runner.MASTER).resolve()) or len(entries) != 1:
        raise ValueError('Budget partition manifest or master differs')
    entry = entries[0]
    effort = study.CONFIGS[config]['effort']
    if (entry.get('model'), entry.get('provider'), entry.get('reasoning')) != (
            study.MODEL, study.PROVIDER, effort):
        raise ValueError('Budget partition route or effort differs')
    cap = paid.number(receipt.get('partition_cap_usd'))
    if cap < study.RESERVE or cap != paid.number(entry.get('cap_usd')):
        raise ValueError('Root reviewed cap must exactly match funded child and fit one reserve')
    return receipt, budget_path


def budget_gate(receipt, budget_path, config):
    effort = study.CONFIGS[config]['effort']
    ledger = runner.partitions.open_partition(runner.MASTER, budget_path,
                                              receipt['partition_id'],
                                              study.MODEL, study.PROVIDER, effort)
    if ledger.cap != paid.number(receipt['partition_cap_usd']):
        ledger.close()
        raise ValueError('Active child ledger cap differs from root receipt')
    return ledger


def live_controls(plan, condition):
    config = plan.get('configuration_id')
    if config not in study.CONFIGS or condition not in study.CONDITIONS:
        raise ValueError('Unsupported exact Mistral119 condition')
    original, _ = study.historical(config)
    frozen = original['provider_endpoint']
    effort = study.CONFIGS[config]['effort']
    catalog = paid.fetch('/models', timeout=120)
    endpoints = paid.fetch('/models/' + quote(study.MODEL, safe='/') + '/endpoints', timeout=120)
    model, endpoint = paid.select_endpoint(study.MODEL, study.PROVIDER, catalog, endpoints,
                                           study.INPUT_PRICE, study.OUTPUT_PRICE)
    critical = ('tag', 'provider_name', 'quantization', 'model_id', 'status',
                'context_length', 'max_prompt_tokens', 'max_completion_tokens',
                'supported_parameters', 'pricing')
    if any(endpoint.get(key) != frozen.get(key) for key in critical):
        raise ValueError('Live endpoint route, limits or price differs')
    expected_reasoning = ({'enabled': False, 'effort': 'none'} if effort == 'none'
                          else {'enabled': True, 'effort': 'high'})
    if paid.reasoning(model, endpoint, effort) != expected_reasoning:
        raise ValueError('Live reasoning support differs')
    reserve = paid.reservation(endpoint, study.MAX_TOKENS,
                               study.INPUT_PRICE, study.OUTPUT_PRICE)
    if reserve != study.RESERVE:
        raise ValueError('Live full-context reserve differs')
    inputs = {row['id']: row['feedback'] for row in study.input_rows()}
    for request in plan['conditions'][condition]['development']:
        payload = request['payload']
        rebuilt = paid.make_payload(study.MODEL, endpoint, inputs[request['record_id']],
                                    payload['messages'][0]['content'],
                                    payload['response_format']['json_schema']['schema'],
                                    effort, study.MAX_TOKENS, study.INPUT_PRICE,
                                    study.OUTPUT_PRICE, model)
        if rebuilt != payload:
            raise ValueError('Live adapter would change a frozen request body')
    return model, endpoint, reserve


runner.execution_plan = execution_plan
runner.review_receipt = review_receipt
runner.budget_gate = budget_gate
runner.live_controls = live_controls


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('freeze')
    check = sub.add_parser('verify')
    check.add_argument('--execution-manifest-sha256', required=True)
    for action in ('smoke', 'development', 'inspect'):
        p = sub.add_parser(action)
        p.add_argument('--configuration-id', required=True, choices=tuple(study.CONFIGS))
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
        runner.inspect(args.configuration_id, args.fresh_pass, args.condition,
                       args.manifest_sha256, args.note)
    else:
        runner.execute(args.configuration_id, args.fresh_pass, args.condition,
                       args.action, args.manifest_sha256,
                       args.root_review_receipt, args.env_file)


if __name__ == '__main__':
    main()
