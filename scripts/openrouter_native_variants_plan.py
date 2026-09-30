#!/usr/bin/env python3
"""Offline, input-only OpenRouter Kev/Jev native P1/P2 preparation.

This module has no inference or admission path. Its dated catalog snapshots are
historical evidence, never a live endpoint or budget check.
"""
import argparse
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path

from development_benchmark import ROOT, KEYS, VALUES, read_rows
from openrouter_paid_benchmark import validate_rows
import jev_native_prompt_variants_v1 as variants
import openrouter_decision_smoke as smoke

SNAPSHOTS = Path('results/route-audits/decision-smoke-20260930')
KEV_PARENT = Path('results/route-audits/decision-kev-development-20260930/manifest.json')
KEV_HISTORY = Path('results/route-audits/kev-fresh3-continuation-20260930/terminal-reconciliation.json')
SOURCE_PATHS = (
    'scripts/jev_native_prompt_variants_v1.py',
    'scripts/jev_benchmark.py',
    'scripts/openrouter_decision_smoke.py',
    'scripts/openrouter_budget_v2.py',
    'scripts/openrouter_paid_benchmark.py',
    'scripts/development_benchmark.py',
    'scripts/openrouter_native_variants_plan.py',
)
EXPECTED_SUFFIX_SHA = '48ba1ad98ac7c085de87e1ddfb1b15f8083bb3d6a57786d708915c6d4981ccd7'
CONDITIONS = ('P1', 'P2')
PASS_NAMES = ('fresh1', 'fresh2', 'fresh3')


def source_hashes(root):
    return {name: smoke.sha((root / name).read_bytes()) for name in SOURCE_PATHS}


def _check_input_only(payload, feedback, policy, route):
    if set(payload) != {'model', 'provider', 'state', 'questions'}:
        raise ValueError('Native request envelope contains unexpected fields')
    if payload['model'] != route['model'] or payload['state'] != {'feedback': feedback, 'policy': policy}:
        raise ValueError('State/model differs from input-only P0')
    if list(payload['questions']) != list(KEYS):
        raise ValueError('Question order or keys differ')
    for key in KEYS:
        question = payload['questions'][key]
        if set(question) != {'type', 'instructions', 'criteria'} or question['type'] != 'choice':
            raise ValueError('Choice question schema differs')
        if list(question['criteria']) != list(VALUES[key]):
            raise ValueError('Choice label order differs')
    if payload['provider'] != smoke.request_payload(feedback, policy, route)['provider']:
        raise ValueError('Provider routing differs')


def variant_payload(parent, condition):
    if condition not in CONDITIONS:
        raise ValueError('Unknown native condition')
    candidate = deepcopy(parent)
    if list(candidate.get('questions', {})) != list(KEYS):
        raise ValueError('P0 question order differs')
    for key in KEYS:
        candidate['questions'][key]['instructions'] += variants.P1
        if condition == 'P2':
            candidate['questions'][key]['instructions'] += variants.P2[key]
    verify_instruction_delta(parent, candidate, condition)
    return candidate


def verify_instruction_delta(parent, candidate, condition):
    if condition not in CONDITIONS or list(candidate.get('questions', {})) != list(KEYS):
        raise ValueError('Unknown condition or changed question order')
    stripped = deepcopy(candidate)
    for key in KEYS:
        question = parent['questions'][key]
        expected = question['instructions'] + variants.P1 + (variants.P2[key] if condition == 'P2' else '')
        if candidate['questions'][key]['instructions'] != expected:
            raise ValueError('Native instruction suffix differs')
        stripped['questions'][key]['instructions'] = question['instructions']
    if smoke.canonical(stripped) != smoke.canonical(parent):
        raise ValueError('Native payload changed outside Choice instructions')


def _parent_evidence(root, route_name, rows, policy):
    if route_name == 'kev':
        path = root / KEV_PARENT
        saved = json.loads(path.read_text())
        if (saved.get('pass_id') != 'kev-openrouter-native-p0-fresh1' or
                saved.get('record_count') != 60 or len(saved.get('requests', [])) != 60):
            raise ValueError('Kev P0 parent manifest changed')
        expected = [smoke.request_payload(r['feedback'], policy, smoke.ROUTES['kev']) for r in rows]
        for item, row, payload in zip(saved['requests'], rows, expected):
            if (item.get('id') != row['id'] or item.get('payload_sha256') != smoke.sha(smoke.canonical(payload)) or
                    item.get('payload') != payload):
                raise ValueError('Kev P0 parent payload drift')
        history_path = root / KEV_HISTORY
        history = json.loads(history_path.read_text())
        if (history.get('pass_id') != 'kev-openrouter-native-p0-fresh3-tail-DEV027-060' or
                history.get('combined_observed_valid_count') != 59 or
                history.get('clean_full_third_pass_complete') is not False):
            raise ValueError('Kev interrupted P0 history changed')
        return {'scope': 'full_60_P0_fresh1', 'path': str(KEV_PARENT), 'sha256': smoke.sha(path.read_bytes()),
                'interrupted_fresh3_reconciliation_path': str(KEV_HISTORY),
                'interrupted_fresh3_reconciliation_sha256': smoke.sha(history_path.read_bytes()),
                'fresh3_status': '59_observed_valid_plus_one_unknown_not_clean'}
    path = root / SNAPSHOTS / 'manifest.json'
    saved = json.loads(path.read_text())
    items = saved.get('routes', {}).get('jev', {}).get('requests')
    if saved.get('kind') != 'openrouter-native-decisions-smoke-preparation-v1' or not isinstance(items, list) or len(items) != 3:
        raise ValueError('Jev P0 smoke manifest changed')
    for item, row in zip(items, rows[:3]):
        payload = smoke.request_payload(row['feedback'], policy, smoke.ROUTES['jev'])
        if (item.get('id') != row['id'] or item.get('payload_sha256') != smoke.sha(smoke.canonical(payload)) or
                item.get('payload') != payload):
            raise ValueError('Jev P0 smoke payload drift')
    return {'scope': 'three_record_P0_smoke_only', 'path': str(SNAPSHOTS / 'manifest.json'),
            'sha256': smoke.sha(path.read_bytes()), 'full_P0_status': 'no_full_openrouter_jev_P0_parent'}


def build_plan(root=ROOT):
    root = Path(root)
    hashes = source_hashes(root)
    if hashes['scripts/jev_native_prompt_variants_v1.py'] != EXPECTED_SUFFIX_SHA:
        raise ValueError('Frozen native suffix source changed')
    rows = validate_rows(read_rows(root / 'data/pilot/inputs.jsonl'))
    budget_path = root / KEV_HISTORY
    budget_snapshot = json.loads(budget_path.read_text())
    if (budget_snapshot.get('kind') != 'kev-interrupted-fresh3-tail-terminal-reconciliation-v1' or
            budget_snapshot.get('master_cap_usd') != '10' or
            budget_snapshot.get('master_headroom_usd') is None or
            Decimal(budget_snapshot['master_headroom_usd']) < 0):
        raise ValueError('Saved master-budget reconciliation changed')
    policy = (root / 'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    if not policy or '## Simulated routing' not in (root / 'docs/LABELING_GUIDE.md').read_text():
        raise ValueError('Policy cutoff missing')
    common = {'kind': 'openrouter-native-choice-variants-offline-plan-v1', 'status': 'prepared_not_admitted',
              'inference_performed': False, 'reference_labels_read': False,
              'input_file_sha256': smoke.sha((root / 'data/pilot/inputs.jsonl').read_bytes()),
              'policy_sha256': smoke.sha(policy.encode()), 'source_sha256': hashes,
              'api_url': smoke.DECISIONS_URL, 'question_order': list(KEYS),
              'parser': {'name': 'openrouter_decision_smoke.validate_response',
                         'implementation_sha256': hashes['scripts/openrouter_decision_smoke.py'],
                         'choice_parser_sha256': hashes['scripts/jev_benchmark.py']},
              'seed_policy': 'no_seed_parameter; provider randomness and caching unknown',
              'master_budget_snapshot': {'captured_as': '2026-09-30 saved reconciliation; not current headroom',
                                         'path': str(KEV_HISTORY), 'sha256': smoke.sha(budget_path.read_bytes()),
                                         'cap_usd': budget_snapshot['master_cap_usd'],
                                         'headroom_usd': budget_snapshot['master_headroom_usd']},
              'smoke_ids': [r['id'] for r in rows[:3]],
              'admission': {'endpoint_refresh_required': True, 'provider_context_accounting_required': True,
                            'smoke_review_required': True, 'whole_pass_budget_review_required': True,
                            'execution_authorized': False}}
    result = {}
    for name, route in smoke.ROUTES.items():
        snapshot_path = root / SNAPSHOTS / (name + '-endpoint.json')
        snapshot = json.loads(snapshot_path.read_text())
        endpoint = smoke.validate_endpoint(snapshot, route)
        parent = _parent_evidence(root, name, rows, policy)
        for condition in CONDITIONS:
            requests = []
            for row in rows:
                p0 = smoke.request_payload(row['feedback'], policy, route)
                _check_input_only(p0, row['feedback'], policy, route)
                payload = variant_payload(p0, condition)
                _check_input_only(payload, row['feedback'], policy, route)
                requests.append({'id': row['id'], 'feedback_sha256': smoke.sha(row['feedback'].encode()),
                                 'p0_payload_sha256': smoke.sha(smoke.canonical(p0)),
                                 'payload_sha256': smoke.sha(smoke.canonical(payload)), 'payload': payload})
            config_id = f'{name}-openrouter-native-{condition.lower()}-choice-v1'
            request_sha = smoke.sha(smoke.canonical(requests))
            manifest = dict(common, configuration_id=config_id, route=name, condition=condition,
                model=route['model'], expected_returned_model=route['version'], provider_tag=route['tag'],
                expected_returned_provider=route['provider'], context_tokens=route['context'],
                catalog_snapshot={'captured_as': '2026-09-30 saved endpoint; not current availability',
                                  'path': str(SNAPSHOTS / (name + '-endpoint.json')),
                                  'sha256': smoke.sha(snapshot_path.read_bytes()),
                                  'canonical_sha256': smoke.sha(smoke.canonical(snapshot)),
                                  'endpoint': endpoint},
                p0_parent=parent, changed_wire_fields=['questions.*.instructions'],
                suffix_source_sha256=EXPECTED_SUFFIX_SHA, p1_suffix=variants.P1,
                p2_suffixes=variants.P2 if condition == 'P2' else None,
                request_count=60, requests_sha256=request_sha, requests=requests,
                per_request_catalog_bound_usd=str(smoke.bound(route)),
                three_record_smoke_catalog_bound_usd=str(3 * smoke.bound(route)),
                full_pass_catalog_bound_usd=str(60 * smoke.bound(route)),
                three_pass_catalog_bound_usd=str(3 * 60 * smoke.bound(route)),
                last_saved_headroom_covers_full_pass=(Decimal(budget_snapshot['master_headroom_usd'])
                                                       >= 60 * smoke.bound(route)),
                passes=[{'pass_id': f'{config_id}-{p}', 'ordinal': i, 'stage': 'full_60',
                         'request_set_sha256': request_sha, 'status': 'planned_not_admitted'}
                        for i, p in enumerate(PASS_NAMES, 1)])
            result[config_id] = manifest
    return result


def prepare(output_dir, root=ROOT):
    directory = Path(output_dir)
    plans = build_plan(root)
    directory.mkdir(parents=True, exist_ok=True)
    if any(directory.iterdir()):
        raise ValueError('Preparation directory must be empty; outputs are immutable')
    for name, plan in plans.items():
        with (directory / (name + '.json')).open('x') as output:
            output.write(json.dumps(plan, indent=2, ensure_ascii=False) + '\n')
    return {name: smoke.sha(smoke.canonical(plan)) for name, plan in plans.items()}


def verify(output_dir, root=ROOT):
    expected = build_plan(root)
    directory = Path(output_dir)
    if {p.name for p in directory.iterdir()} != {name + '.json' for name in expected}:
        raise ValueError('Prepared manifest file set changed')
    for name, plan in expected.items():
        path = directory / (name + '.json')
        if path.read_bytes() != (json.dumps(plan, indent=2, ensure_ascii=False) + '\n').encode():
            raise ValueError('Prepared manifest differs from source: ' + name)
    return {name: smoke.sha(smoke.canonical(plan)) for name, plan in expected.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('prepare', 'verify'))
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    hashes = prepare(args.directory) if args.operation == 'prepare' else verify(args.directory)
    print(json.dumps(hashes, indent=2))


if __name__ == '__main__':
    main()
