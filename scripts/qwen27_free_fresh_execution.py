#!/usr/bin/env python3
"""Isolated free-route Qwen27 adapter over the reviewed private-evidence lifecycle."""
import argparse
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote

from development_benchmark import digest
import gemma26_free_fresh_execution as gemma
import openrouter_benchmark as transport
import qwen27_free_fresh_study as study

RECEIPT_SCHEMA = 'qwen27-free-fresh-root-review-v1'
MAX_COMPLETION = 235929


def endpoint_check(catalog, endpoints, effort):
    models = [x for x in catalog.get('data', []) if x.get('id') == study.MODEL]
    if len(models) != 1 or not transport.zero_price(models[0].get('pricing')):
        raise ValueError('Exactly one zero-priced free Qwen model required')
    reasoning = models[0].get('reasoning') or {}
    if reasoning.get('mandatory') is not False or effort not in reasoning.get('supported_efforts', []):
        raise ValueError('Requested reasoning effort unsupported by free model')
    if endpoints.get('data', {}).get('id') != study.MODEL:
        raise ValueError('Free endpoint model ID differs')
    matches = [x for x in endpoints['data'].get('endpoints', []) if x.get('tag') == study.PROVIDER]
    if len(matches) != 1:
        raise ValueError('Exactly one ModelRun free endpoint required')
    endpoint = matches[0]
    if (endpoint.get('model_id'), endpoint.get('provider_name'), endpoint.get('quantization'),
            endpoint.get('status'), endpoint.get('context_length'), endpoint.get('max_completion_tokens')) != (
            study.MODEL, study.PROVIDER_NAME, 'fp4', 0, study.CONTEXT, MAX_COMPLETION):
        raise ValueError('Free Qwen route identity, capacity, or status differs')
    if not transport.zero_price(endpoint.get('pricing')):
        raise ValueError('Free Qwen endpoint has a nonzero or unknown listed price')
    required = {'structured_outputs', 'reasoning', 'reasoning_effort', 'max_tokens', 'temperature'}
    if not required <= set(endpoint.get('supported_parameters', [])):
        raise ValueError('Free Qwen endpoint lacks requested controls')
    return models[0], endpoint


def engine(config):
    if config not in study.CONFIGS:
        raise ValueError('Unknown free Qwen configuration')
    effort = study.CONFIGS[config][1]
    source = Path(gemma.__file__)
    spec = importlib.util.spec_from_file_location('private_qwen_free_lifecycle_' + effort, source)
    lifecycle = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lifecycle)
    view = SimpleNamespace(ROOT=study.ROOT if hasattr(study, 'ROOT') else study.paid_study.ROOT,
                           BASE=study.BASE / config, CONFIG=config, MODEL=study.MODEL,
                           PROVIDER=study.PROVIDER, PROVIDER_NAME=study.PROVIDER_NAME,
                           CONTEXT=study.CONTEXT, MAX_TOKENS=study.MAX_TOKENS,
                           SERIES=study.SERIES + '/' + config, ORDERS=study.ORDERS,
                           historical=SimpleNamespace(digest=digest), sha=study.sha,
                           verify=lambda fresh_pass, sha: study.verify(config, fresh_pass, sha))
    lifecycle.study = view
    lifecycle.RECEIPT_SCHEMA = RECEIPT_SCHEMA

    def review_receipt(path, fresh_pass, condition, phase, plan_sha):
        private = lifecycle.private_path(path)
        receipt = json.loads(private.read_text())
        if receipt.get('schema') != RECEIPT_SCHEMA or receipt.get('approved') is not True:
            raise ValueError('Free Qwen root review missing approval')
        if (receipt.get('configuration_id'), receipt.get('stage'), receipt.get('controller_sha256'),
                receipt.get('tests_sha256'), receipt.get('lifecycle_sha256')) != (
                config, f'{fresh_pass}/{condition}/{phase}', study.sha(__file__),
                study.sha(study.ROOT / 'tests/test_qwen27_free_fresh.py'), study.sha(source)):
            raise ValueError('Free Qwen review binding differs')
        expected = {name: study.sha(study.BASE / config / name / 'manifest.json') for name in study.ORDERS}
        for name, value in expected.items():
            study.verify(config, name, value)
        if receipt.get('plan_sha256') != expected or expected[fresh_pass] != plan_sha:
            raise ValueError('Free Qwen reviewed plans differ')
        evidence = lifecycle.private_path(receipt.get('evidence_root'), directory=True)
        if evidence.name != config:
            raise ValueError('Free Qwen evidence root must be configuration-specific')
        return receipt, evidence

    def live_controls(plan, condition):
        catalog = transport.fetch('/models', timeout=120)
        endpoints = transport.fetch('/models/' + quote(study.MODEL, safe='/') + '/endpoints', timeout=120)
        model, endpoint = endpoint_check(catalog, endpoints, effort)
        for request in plan['conditions'][condition]['development']:
            payload = request['payload']
            if (payload.get('model') != study.MODEL or payload.get('provider') != {
                    'only': [study.PROVIDER], 'allow_fallbacks': False,
                    'require_parameters': True,
                    'max_price': {'prompt': 0, 'completion': 0, 'request': 0, 'image': 0}} or
                    payload.get('reasoning') != {'enabled': True, 'effort': effort} or
                    payload.get('response_format', {}).get('type') != 'json_schema' or
                    payload['response_format']['json_schema'].get('strict') is not True or
                    payload.get('max_tokens') != study.MAX_TOKENS or payload.get('temperature') != 0 or
                    payload.get('stream') is not False):
                raise ValueError('Frozen free Qwen payload controls differ')
        return model, endpoint

    lifecycle.review_receipt = review_receipt
    lifecycle.live_controls = live_controls
    return lifecycle


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('run', 'inspect', 'verify-closed'))
    parser.add_argument('--configuration-id', required=True, choices=tuple(study.CONFIGS))
    parser.add_argument('--pass-name', required=True, choices=tuple(study.ORDERS))
    parser.add_argument('--condition', required=True, choices=('P0', 'P1', 'P2'))
    parser.add_argument('--phase', choices=('smoke', 'development'))
    parser.add_argument('--plan-sha256', required=True)
    parser.add_argument('--review-receipt')
    parser.add_argument('--evidence-root')
    parser.add_argument('--env-file')
    parser.add_argument('--note')
    args = parser.parse_args()
    lifecycle = engine(args.configuration_id)
    if args.action == 'run':
        if not args.phase or not args.review_receipt:
            parser.error('run requires --phase and --review-receipt')
        done = lifecycle.execute(args.pass_name, args.condition, args.phase, args.plan_sha256,
                                 args.review_receipt, args.env_file)
        print('completed' if done else 'stopped')
    elif args.action == 'inspect':
        if not args.evidence_root or not args.note:
            parser.error('inspect requires --evidence-root and --note')
        lifecycle.inspect(args.evidence_root, args.pass_name, args.condition, args.plan_sha256, args.note)
        print('inspection recorded')
    else:
        if not args.evidence_root or not args.phase:
            parser.error('verify-closed requires --evidence-root and --phase')
        study.verify(args.configuration_id, args.pass_name, args.plan_sha256)
        lifecycle.verify_closed(lifecycle.private_path(args.evidence_root, directory=True),
                                args.pass_name, args.condition, args.phase)
        print('closed evidence verified')


if __name__ == '__main__':
    main()
