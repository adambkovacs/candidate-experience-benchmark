#!/usr/bin/env python3
"""Separate, offline-proposed Jev full-pass admission using the frozen full-v1 core.

The Jev context calculation is an estimate, not provider token accounting or
an authorization to run. Execute requires root-reviewed evidence and a distinct
receipt binding both this adapter and the unchanged full-v1 execution core.
"""
import argparse
import base64
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

from development_benchmark import ROOT
import openrouter_decision_smoke as decision
import openrouter_native_variants_full_v1 as full
import openrouter_native_variants_plan as frozen
import openrouter_native_variants_v2 as smoke_v2

BASE = ROOT / 'results/route-audits/jev-native-full-v1-20261006'
CONFIGS = ('jev-openrouter-native-p1-choice-v1',
           'jev-openrouter-native-p2-choice-v1')
P0_ATTEMPTS = ROOT / 'results/route-audits/decision-smoke-20260930/jev-attempts.jsonl'
P0_MANIFEST = ROOT / 'results/route-audits/decision-smoke-20260930/manifest.json'
CONTEXT_MARGIN = 4096


def paths(base, config, stage=None):
    return full.paths(base, config, stage)


def _p0_smoke(original, *, root=ROOT):
    """Verify three actual OpenRouter Jev P0 responses and their frozen inputs."""
    attempts_path = Path(root) / P0_ATTEMPTS.relative_to(ROOT)
    manifest_path = Path(root) / P0_MANIFEST.relative_to(ROOT)
    saved = json.loads(manifest_path.read_text())
    requests = saved['routes']['jev']['requests']
    rows = [json.loads(x) for x in attempts_path.read_text().splitlines() if x.strip()]
    if len(requests) != 3 or len(rows) != 9:
        raise ValueError('OpenRouter Jev P0 source lacks three complete attempts')
    observed = []
    for i, item in enumerate(original['requests'][:3]):
        req = requests[i]
        reserve, response, validated = rows[3*i:3*i+3]
        body = response.get('body') or {}
        raw = base64.b64decode(response.get('raw_response_base64', ''), validate=True)
        usage = body.get('usage') or {}
        count = usage.get('input_tokens')
        if (req.get('id') != item['id'] or req.get('payload_sha256') != item['p0_payload_sha256'] or
                decision.sha(decision.canonical(req.get('payload'))) != item['p0_payload_sha256'] or
                [x.get('stage') for x in (reserve, response, validated)] !=
                ['reserved', 'response', 'validated'] or
                any(x.get('id') != item['id'] for x in (reserve, response, validated)) or
                reserve.get('payload_sha256') != item['p0_payload_sha256'] or
                response.get('http_status') != 200 or response.get('cost_unknown') is not False or
                smoke_v2.sha(raw) != response.get('raw_response_sha256') or
                len(raw) != response.get('raw_response_size_bytes') or json.loads(raw) != body or
                body.get('model') != decision.ROUTES['jev']['version'] or
                body.get('provider') != decision.ROUTES['jev']['provider'] or
                type(count) is not int or not 0 <= count <= 32000 or
                not isinstance(validated.get('prediction'), dict)):
            raise ValueError('OpenRouter Jev P0 raw/provider/accounting evidence differs')
        observed.append({'id': item['id'], 'p0_provider_input_tokens': count,
                         'p0_request_sha256': item['p0_payload_sha256']})
    return {'attempts_sha256': smoke_v2.file_sha(attempts_path),
            'manifest_sha256': smoke_v2.file_sha(manifest_path),
            'observed': observed}


def jev_context_estimate(config, original, *, root=ROOT, smoke_base=smoke_v2.BASE):
    if (config not in CONFIGS or original['route'] != 'jev' or
            original['requests_sha256'] != smoke_v2.sha(decision.canonical(original['requests']))):
        raise ValueError('Frozen Jev request set differs')
    p0 = _p0_smoke(original, root=root)
    observed = []
    smoke_path = smoke_v2.paths(smoke_base, config)['stage'] / 'attempts.jsonl'
    rows = [json.loads(x) for x in smoke_path.read_text().splitlines() if x.strip()]
    if len(rows) != 12:
        raise ValueError('Jev native smoke lacks three complete attempts')
    per_record = []
    for i, item in enumerate(original['requests']):
        payload = item['payload']
        parent = decision.request_payload(payload['state']['feedback'],
                                          payload['state']['policy'], decision.ROUTES['jev'])
        frozen.verify_instruction_delta(parent, payload, original['condition'])
        parent_bytes, variant_bytes = decision.canonical(parent), decision.canonical(payload)
        if (smoke_v2.sha(parent_bytes) != item['p0_payload_sha256'] or
                smoke_v2.sha(variant_bytes) != item['payload_sha256']):
            raise ValueError('Exact Jev parent/variant request bytes differ')
        added = sum(len(payload['questions'][key]['instructions'].encode('utf-8')) -
                    len(parent['questions'][key]['instructions'].encode('utf-8'))
                    for key in payload['questions'])
        if added <= 0 or len(variant_bytes) - len(parent_bytes) != added:
            raise ValueError('Jev instruction delta accounting differs')
        estimate = 2 * len(variant_bytes) + CONTEXT_MARGIN
        if estimate > 32000:
            raise ValueError('Jev context estimate exceeds OpenRouter 32K')
        per_record.append({'id': item['id'], 'p0_request_sha256': item['p0_payload_sha256'],
                           'variant_request_sha256': item['payload_sha256'],
                           'p0_canonical_utf8_bytes': len(parent_bytes),
                           'added_instruction_utf8_bytes': added,
                           'variant_canonical_utf8_bytes': len(variant_bytes),
                           'estimated_input_token_upper_bound': estimate})
        if i < 3:
            reserve, started, response, parsed = rows[4*i:4*i+4]
            body = response.get('body') or {}
            raw = base64.b64decode(response.get('raw_response_base64', ''), validate=True)
            count = (body.get('usage') or {}).get('input_tokens')
            if (reserve.get('id') != item['id'] or started.get('id') != item['id'] or
                    response.get('id') != item['id'] or parsed.get('id') != item['id'] or
                    reserve.get('request_sha256') != item['payload_sha256'] or
                    response.get('http_status') != 200 or response.get('cost_unknown') is not False or
                    smoke_v2.sha(raw) != response.get('raw_response_sha256') or
                    json.loads(raw) != body or
                    body.get('model') != decision.ROUTES['jev']['version'] or
                    body.get('provider') != decision.ROUTES['jev']['provider'] or
                    type(count) is not int or count > estimate or parsed.get('valid') is not True):
                raise ValueError('Jev variant raw/provider/accounting smoke differs')
            observed.append({'id': item['id'],
                             'p0_provider_input_tokens': p0['observed'][i]['p0_provider_input_tokens'],
                             'variant_provider_input_tokens': count,
                             'observed_added_tokens': count - p0['observed'][i]['p0_provider_input_tokens']})
    return {'schema': full.SCHEMA + '-conservative-context-estimate',
            'status': 'proposed_for_review', 'route': 'jev', 'configuration_id': config,
            'condition': original['condition'], 'request_set_sha256': original['requests_sha256'],
            'context_limit': 32000,
            'method': '2x_complete_canonical_UTF8_request_bytes_plus_4096',
            'method_rationale': ('Complete JSON bytes include the state and all four questions; '
                'the 2x multiplier and 4096-token allowance cover unverified tokenization and '
                'provider wrapping. They are conservative assumptions, not a mathematical or provider guarantee.'),
            'provider_guarantee': False,
            'openrouter_p0_full_pass_status': 'absent; three-record P0 smoke only',
            'context_rejection_policy': 'stop_without_retry_and_preserve_raw',
            'p0_smoke_attempts_sha256': p0['attempts_sha256'],
            'p0_smoke_manifest_sha256': p0['manifest_sha256'],
            'variant_smoke_attempts_sha256': smoke_v2.file_sha(smoke_path),
            'smoke_observed_input_tokens': observed, 'per_record': per_record,
            'max_variant_canonical_utf8_bytes': max(x['variant_canonical_utf8_bytes'] for x in per_record),
            'max_estimated_input_token_upper_bound': max(x['estimated_input_token_upper_bound'] for x in per_record),
            'source_links': ['https://docs.typesafe.ai/models',
                             'https://docs.typesafe.ai/concepts/state',
                             'https://openrouter.ai/typesafe/jev-1.13/']}


def build_manifest(config, *, root=ROOT, smoke_base=smoke_v2.BASE):
    if config not in CONFIGS:
        raise ValueError('Only frozen OpenRouter Jev P1/P2 are supported')
    plan = full.build_manifest(config, root=root, smoke_base=smoke_base)
    original = frozen.build_plan(root)[config]
    estimate = jev_context_estimate(config, original, root=root, smoke_base=smoke_base)
    result = deepcopy(plan)
    result['context_estimate_sha256'] = smoke_v2.sha(decision.canonical(estimate))
    result['context_review_mode'] = 'reviewed_conservative_estimate'
    result['openrouter_p0_full_pass_status'] = estimate['openrouter_p0_full_pass_status']
    result['admission']['reviewed_all60_context_rationale_required'] = True
    result['execution_adapter_sha256'] = smoke_v2.file_sha(__file__)
    return result


def prepare(config, base=BASE, *, root=ROOT, smoke_base=smoke_v2.BASE):
    value = build_manifest(config, root=root, smoke_base=smoke_base)
    estimate = jev_context_estimate(config, frozen.build_plan(root)[config],
                                    root=root, smoke_base=smoke_base)
    p = paths(base, config)
    p['estimate'].parent.mkdir(parents=True, exist_ok=True)
    with p['manifest'].open('x') as handle:
        handle.write(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    with p['estimate'].open('x') as handle:
        handle.write(json.dumps(estimate, indent=2, ensure_ascii=False) + '\n')
    return smoke_v2.file_sha(p['manifest'])


def verify(config, base=BASE, *, root=ROOT, smoke_base=smoke_v2.BASE):
    value = build_manifest(config, root=root, smoke_base=smoke_base)
    estimate = jev_context_estimate(config, frozen.build_plan(root)[config],
                                    root=root, smoke_base=smoke_base)
    p = paths(base, config)
    if p['manifest'].read_bytes() != (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode():
        raise ValueError('Proposed Jev manifest differs from frozen source or adapter')
    if p['estimate'].read_bytes() != (json.dumps(estimate, indent=2, ensure_ascii=False) + '\n').encode():
        raise ValueError('Proposed Jev estimate differs from frozen source')
    return value


def expected_receipt(config, stage, manifest, budget_path, context_sha, inspection_sha,
                     predecessor_proof, hold_source, *, base=BASE):
    receipt = full.expected_receipt(config, stage, manifest, budget_path, context_sha,
                                    inspection_sha, predecessor_proof, hold_source, base=base)
    receipt['execution_adapter_sha256'] = smoke_v2.file_sha(__file__)
    return receipt


def _execution_core():
    """Load the immutable full-v1 source into a private namespace for Jev gates.

    No mutation of the imported module or a live Kev process occurs. Its
    transport, ledger and stop semantics run byte-for-byte from full-v1.
    """
    spec = importlib.util.spec_from_file_location('_openrouter_jev_full_v1_core', full.__file__)
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    core.verify = verify
    core.expected_receipt = expected_receipt
    return core


def execute(config, stage, receipt_path, budget_path, *, base=BASE, **kwargs):
    if config not in CONFIGS:
        raise ValueError('Only frozen OpenRouter Jev P1/P2 are supported')
    return _execution_core().execute(config, stage, receipt_path, budget_path,
                                     base=base, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify', 'run'))
    parser.add_argument('--configuration', choices=CONFIGS, required=True)
    parser.add_argument('--stage', choices=full.PASSES)
    parser.add_argument('--review-receipt', type=Path)
    parser.add_argument('--budget-manifest', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare':
        print(prepare(args.configuration))
    elif args.action == 'verify':
        print(json.dumps(verify(args.configuration)['admission'], indent=2))
    else:
        if args.stage is None or args.review_receipt is None or args.budget_manifest is None:
            parser.error('run needs stage, review receipt and budget manifest')
        print(json.dumps(execute(args.configuration, args.stage, args.review_receipt,
                                 args.budget_manifest), indent=2))


if __name__ == '__main__':
    main()
