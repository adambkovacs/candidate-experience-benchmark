#!/usr/bin/env python3
"""Offline proposal and separately gated 60-record Jev OpenRouter native P0 passes.

The historical P0 observation covers only three records. The proposed context
accounting is an estimate, not a tokenizer guarantee or dispatch approval.
"""
import argparse
import json
from pathlib import Path

from development_benchmark import ROOT, read_rows
import openrouter_decision_smoke as decision
import openrouter_jev_native_full_v1 as jev
import openrouter_native_variants_full_v1 as full
import openrouter_native_variants_plan as variants
import openrouter_native_variants_v2 as smoke_v2
from openrouter_paid_benchmark import validate_rows

BASE = ROOT / 'results/route-audits/jev-native-p0-full-v1-20261006'
CONFIG = 'jev-openrouter-native-p0-choice-v1'
IDS = full.IDS


def paths(base, config=CONFIG, stage=None):
    if config != CONFIG:
        raise ValueError('Only the frozen Jev OpenRouter native P0 is supported')
    return full.paths(base, config, stage)


def build_plan(root=ROOT):
    root = Path(root)
    source = root / 'results/route-audits/decision-smoke-20260930/manifest.json'
    saved = json.loads(source.read_text())
    input_path = root / 'data/pilot/inputs.jsonl'
    policy_path = root / 'docs/LABELING_GUIDE.md'
    policy_file = policy_path.read_text()
    if '## Simulated routing' not in policy_file:
        raise ValueError('Frozen policy cutoff missing')
    policy = policy_file.split('## Simulated routing')[0]
    route = decision.ROUTES['jev']
    if (saved.get('kind') != 'openrouter-native-decisions-smoke-preparation-v1' or
            saved.get('input_file_sha256') != decision.sha(input_path.read_bytes()) or
            saved.get('policy_sha256') != decision.sha(policy.encode()) or
            saved.get('reference_labels_read') is not False):
        raise ValueError('Historical Jev P0 smoke source differs')
    historical = saved['routes']['jev']
    if (historical.get('model') != route['model'] or
            historical.get('expected_returned_model') != route['version'] or
            historical.get('provider_tag') != route['tag'] or
            historical.get('expected_returned_provider') != route['provider'] or
            historical.get('context_tokens') != route['context'] or
            len(historical.get('requests', [])) != 3):
        raise ValueError('Historical Jev P0 route/manifest differs')
    rows = validate_rows(read_rows(input_path))
    if [x['id'] for x in rows] != IDS:
        raise ValueError('Development ID order differs')
    requests = []
    for row in rows:
        payload = decision.request_payload(row['feedback'], policy, route)
        variants._check_input_only(payload, row['feedback'], policy, route)
        request_hash = decision.sha(decision.canonical(payload))
        requests.append({'id': row['id'], 'feedback_sha256': decision.sha(row['feedback'].encode()),
                         'p0_payload_sha256': request_hash,
                         'payload_sha256': request_hash, 'payload': payload})
    for item, old in zip(requests[:3], historical['requests']):
        if (item['id'] != old.get('id') or
                item['feedback_sha256'] != old.get('input_sha256') or
                item['payload_sha256'] != old.get('payload_sha256') or
                item['payload'] != old.get('payload')):
            raise ValueError('Rebuilt Jev P0 differs from historical smoke request')
    return {CONFIG: {'configuration_id': CONFIG, 'route': 'jev', 'condition': 'P0',
                     'requests': requests,
                     'requests_sha256': decision.sha(decision.canonical(requests)),
                     'input_file_sha256': decision.sha(input_path.read_bytes()),
                     'policy_sha256': decision.sha(policy.encode()),
                     'historical_smoke_manifest_sha256': smoke_v2.file_sha(source)}}


def p0_context_estimate(original, *, root=ROOT):
    p0 = jev._p0_smoke(original, root=root)
    per_record = []
    for item in original['requests']:
        request = decision.canonical(item['payload'])
        if (decision.sha(request) != item['payload_sha256'] or
                item['payload_sha256'] != item['p0_payload_sha256']):
            raise ValueError('Exact Jev P0 request bytes differ')
        estimate = 2 * len(request) + jev.CONTEXT_MARGIN
        if estimate > decision.ROUTES['jev']['context']:
            raise ValueError('Jev P0 context estimate exceeds OpenRouter 32K')
        per_record.append({'id': item['id'], 'request_sha256': item['payload_sha256'],
                           'canonical_utf8_bytes': len(request),
                           'estimated_input_token_upper_bound': estimate})
    for i, sample in enumerate(p0['observed']):
        if sample['p0_provider_input_tokens'] > per_record[i]['estimated_input_token_upper_bound']:
            raise ValueError('Observed Jev P0 usage exceeds proposed estimate')
    return {'schema': full.SCHEMA + '-conservative-context-estimate',
            'status': 'proposed_for_review', 'route': 'jev',
            'configuration_id': CONFIG, 'condition': 'P0',
            'request_set_sha256': original['requests_sha256'], 'context_limit': 32000,
            'method': '2x_complete_canonical_UTF8_request_bytes_plus_4096',
            'method_rationale': ('Complete request bytes include state and all four questions; '
                'the 2x multiplier and 4096-token allowance cover unverified tokenization and '
                'provider wrapping. They are assumptions, not a provider or mathematical guarantee.'),
            'provider_guarantee': False,
            'openrouter_p0_full_pass_status': 'absent; historical three-record smoke only',
            'context_rejection_policy': 'stop_without_retry_and_preserve_raw',
            'p0_smoke_attempts_sha256': p0['attempts_sha256'],
            'p0_smoke_manifest_sha256': p0['manifest_sha256'],
            'smoke_observed_input_tokens': p0['observed'],
            'per_record': per_record,
            'max_canonical_utf8_bytes': max(x['canonical_utf8_bytes'] for x in per_record),
            'max_estimated_input_token_upper_bound': max(x['estimated_input_token_upper_bound'] for x in per_record),
            'source_links': ['https://docs.typesafe.ai/models',
                             'https://docs.typesafe.ai/concepts/state',
                             'https://openrouter.ai/typesafe/jev-1.13/']}


def build_manifest(config=CONFIG, *, root=ROOT, smoke_base=None):
    if config != CONFIG:
        raise ValueError('Only the frozen Jev OpenRouter native P0 is supported')
    original = build_plan(root)[CONFIG]
    estimate = p0_context_estimate(original, root=root)
    route = decision.ROUTES['jev']
    p0 = jev._p0_smoke(original, root=root)
    return {'schema': full.SCHEMA + '-offline-plan', 'status': 'proposed_not_admitted',
            'inference_performed': False, 'reference_labels_read': False,
            'configuration_id': CONFIG, 'route': 'jev', 'condition': 'P0',
            'model': route['model'], 'provider': route['provider'],
            'provider_tag': route['tag'], 'returned_model': route['version'],
            'context_tokens': route['context'], 'input_file_sha256': original['input_file_sha256'],
            'policy_sha256': original['policy_sha256'],
            'historical_smoke_manifest_sha256': original['historical_smoke_manifest_sha256'],
            'smoke_proof': {'p0_smoke_manifest_sha256': p0['manifest_sha256'],
                            'p0_smoke_attempts_sha256': p0['attempts_sha256'],
                            'observed_input_tokens': p0['observed'],
                            'scope': 'three_records_only_no_full_P0'},
            'context_estimate_sha256': smoke_v2.sha(decision.canonical(estimate)),
            'context_review_mode': 'reviewed_conservative_estimate',
            'request_set_sha256': original['requests_sha256'], 'ids': IDS,
            'request_sha256': [x['payload_sha256'] for x in original['requests']],
            'per_request_full_context_bound_usd': str(decision.bound(route)),
            'whole_pass_bound_usd': str(60 * decision.bound(route)),
            'budget_master_cap_usd': '12.38',
            'global_authority_cap_usd': str(smoke_v2.AUTHORITY_CAP),
            'execution_core_sha256': smoke_v2.file_sha(full.__file__),
            'p0_adapter_sha256': smoke_v2.file_sha(__file__),
            'jev_evidence_helper_sha256': smoke_v2.file_sha(jev.__file__),
            'passes': [{'stage': stage, 'pass_id': CONFIG + '-' + stage,
                        'partition_id': CONFIG + '-' + stage + '-full-v1',
                        'status': 'proposed_not_admitted'} for stage in full.PASSES],
            'admission': {'reviewed_all60_context_rationale_required': True,
                          'reviewed_smoke_inspection_required': True,
                          'separate_review_and_budget_per_pass': True,
                          'new_P0_full_pass_required': True}}


def prepare(config=CONFIG, base=BASE, *, root=ROOT):
    value = build_manifest(config, root=root)
    estimate = p0_context_estimate(build_plan(root)[CONFIG], root=root)
    p = paths(base, config)
    p['estimate'].parent.mkdir(parents=True, exist_ok=True)
    with p['manifest'].open('x') as handle:
        handle.write(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    with p['estimate'].open('x') as handle:
        handle.write(json.dumps(estimate, indent=2, ensure_ascii=False) + '\n')
    return smoke_v2.file_sha(p['manifest'])


def verify(config=CONFIG, base=BASE, *, root=ROOT, smoke_base=None):
    value = build_manifest(config, root=root)
    estimate = p0_context_estimate(build_plan(root)[CONFIG], root=root)
    p = paths(base, config)
    if p['manifest'].read_bytes() != (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode():
        raise ValueError('Proposed Jev P0 manifest differs from frozen source or code')
    if p['estimate'].read_bytes() != (json.dumps(estimate, indent=2, ensure_ascii=False) + '\n').encode():
        raise ValueError('Proposed Jev P0 estimate differs from frozen source')
    return value


def smoke_inspection(config, manifest, *, base=BASE):
    p = paths(base, config)['inspection']
    value = json.loads(p.read_text())
    if value != {'schema': full.SCHEMA + '-p0-smoke-inspection', 'reviewer': 'root',
                 'configuration_id': config,
                 'p0_smoke_manifest_sha256': manifest['smoke_proof']['p0_smoke_manifest_sha256'],
                 'p0_smoke_attempts_sha256': manifest['smoke_proof']['p0_smoke_attempts_sha256'],
                 'all_three_raw_distributions_inspected': True,
                 'approved_for_full_pass_review': True}:
        raise ValueError('Reviewed historical P0 smoke inspection differs')
    return smoke_v2.file_sha(p)


def predecessor(config, stage, manifest, *, base=BASE):
    if stage not in full.PASSES:
        raise ValueError('Unknown declared P0 pass')
    result = {'p0_smoke_manifest_sha256': manifest['smoke_proof']['p0_smoke_manifest_sha256'],
              'p0_smoke_attempts_sha256': manifest['smoke_proof']['p0_smoke_attempts_sha256']}
    if stage == 'fresh1':
        return result
    previous = full.PASSES[full.PASSES.index(stage) - 1]
    prior_path = paths(base, config, previous)['stage'] / 'completion.json'
    completed = json.loads(prior_path.read_text())
    attempts_path = prior_path.parent / 'attempts.jsonl'
    if (completed.get('schema') != full.SCHEMA + '-completion' or
            completed.get('configuration_id') != config or completed.get('stage') != previous or
            completed.get('ids') != IDS or
            type(completed.get('valid_count')) is not int or
            type(completed.get('invalid_count')) is not int or
            completed['valid_count'] + completed['invalid_count'] != 60 or
            completed.get('manifest_sha256') != smoke_v2.file_sha(paths(base, config)['manifest']) or
            completed.get('attempts_sha256') != smoke_v2.file_sha(attempts_path)):
        raise ValueError('Previous Jev P0 full pass lacks exact completion')
    result['previous_completion_sha256'] = smoke_v2.file_sha(prior_path)
    result['previous_attempts_sha256'] = completed['attempts_sha256']
    return result


def expected_receipt(config, stage, manifest, budget_path, context_sha, inspection_sha,
                     predecessor_proof, hold_source, *, base=BASE):
    receipt = full.expected_receipt(config, stage, manifest, budget_path, context_sha,
                                    inspection_sha, predecessor_proof, hold_source, base=base)
    receipt['p0_adapter_sha256'] = smoke_v2.file_sha(__file__)
    receipt['jev_evidence_helper_sha256'] = smoke_v2.file_sha(jev.__file__)
    return receipt


class _P0Plan:
    @staticmethod
    def build_plan(root=ROOT):
        return build_plan(root)


def _execution_core():
    core = jev._execution_core()
    core.verify = verify
    core.smoke_inspection = smoke_inspection
    core.predecessor = predecessor
    core.expected_receipt = expected_receipt
    core.frozen = _P0Plan
    return core


def execute(config, stage, receipt_path, budget_path, *, base=BASE, **kwargs):
    if config != CONFIG:
        raise ValueError('Only the frozen Jev OpenRouter native P0 is supported')
    return _execution_core().execute(config, stage, receipt_path, budget_path,
                                     base=base, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify', 'run'))
    parser.add_argument('--stage', choices=full.PASSES)
    parser.add_argument('--review-receipt', type=Path)
    parser.add_argument('--budget-manifest', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare':
        print(prepare())
    elif args.action == 'verify':
        print(json.dumps(verify()['admission'], indent=2))
    else:
        if args.stage is None or args.review_receipt is None or args.budget_manifest is None:
            parser.error('run needs stage, review receipt and budget manifest')
        print(json.dumps(execute(CONFIG, args.stage, args.review_receipt,
                                 args.budget_manifest), indent=2))


if __name__ == '__main__':
    main()
