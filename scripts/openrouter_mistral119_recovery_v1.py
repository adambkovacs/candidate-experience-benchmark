#!/usr/bin/env python3
"""Bounded P0 Mistral119 smoke recovery through the unchanged paid runner."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import openrouter_paid_benchmark as paid
import paid_budget_partitions_v2 as partitions_v2

ROOT = Path(__file__).resolve().parents[1]
MODEL = 'mistralai/mistral-small-2603'
PROVIDER = 'mistral/zdr'
CAP = paid.Decimal('0.15')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bound(binding):
    path = (ROOT / binding['file']).resolve()
    path.relative_to(ROOT)
    if sha(path) != binding['sha256']:
        raise ValueError('Frozen source hash mismatch: ' + binding['file'])
    return path


def prepare(manifest_path, expected_sha, budget_path=None, partition_id=None, receipt_path=None):
    manifest_path = Path(manifest_path).resolve()
    manifest_path.relative_to(ROOT)
    if sha(manifest_path) != expected_sha:
        raise ValueError('Recovery manifest hash mismatch')
    m = json.loads(manifest_path.read_text())
    if m.get('schema') != 'mistral119-smoke-recovery-v1' or m.get('phase') != 'smoke' or m.get('record_ids') != ['DEV-001', 'DEV-002', 'DEV-003']:
        raise ValueError('Invalid smoke manifest')
    effort = m.get('reasoning')
    if effort not in ('none', 'high') or m.get('model') != MODEL or m.get('provider') != PROVIDER:
        raise ValueError('Model, provider or effort drift')
    if m.get('max_tokens') != 4096 or m.get('timeout_seconds') != 300 or m.get('max_input_price') != '0.15' or m.get('max_output_price') != '0.6':
        raise ValueError('Frozen request controls drift')
    if m.get('reference_labels_read') is not False or m.get('retry_policy') != 'new smoke after preserved HTTP429; no automatic retry':
        raise ValueError('Recovery protocol drift')
    required = ('openrouter_paid_benchmark', 'openrouter_budget_v2', 'paid_budget_partitions_v2', 'inputs', 'policy', 'schema', 'historical_attempt', 'endpoint_audit')
    paths = {name: bound(m['sources'][name]) for name in required}
    original = json.loads(paths['historical_attempt'].read_text().splitlines()[0])
    if original.get('id') != 'DEV-001' or original.get('status') != 'service_error' or original.get('http_status') != 429 or original.get('reasoning_effort') != effort:
        raise ValueError('Historical source is not the specified failed smoke')
    request = original['request']
    if request['model'] != MODEL or request['provider'] != {'only': [PROVIDER], 'allow_fallbacks': False, 'require_parameters': True, 'max_price': {'prompt': 0.15, 'completion': 0.6, 'request': 0, 'image': 0}}:
        raise ValueError('Historical routing differs')
    if request['max_tokens'] != 4096 or request['temperature'] != 0 or request['stream'] is not False or request.get('reasoning') != ({'enabled': False, 'effort': 'none'} if effort == 'none' else {'enabled': True, 'effort': 'high'}):
        raise ValueError('Historical request differs')
    if sha(paths['policy']) != m['sources']['policy']['sha256'] or sha(paths['schema']) != m['sources']['schema']['sha256']:
        raise ValueError('Source drift')
    rows = paid.select_rows(paid.read_rows(paths['inputs']), 'smoke', 1)
    policy = paid.baseline_instruction()
    schema = json.loads(paths['schema'].read_text())
    if policy != request['messages'][0]['content'] or schema != request['response_format']['json_schema']['schema']:
        raise ValueError('Policy or schema differs from original')
    expected = [paid.make_payload(MODEL, original['provider_endpoint'], row['feedback'], policy, schema, effort, 4096, paid.Decimal('0.15'), paid.Decimal('0.6'), original['model_catalog_entry']) for row in rows]
    if expected[0] != request or [hashlib.sha256(json.dumps(p, sort_keys=True).encode()).hexdigest() for p in expected] != m['request_sha256']:
        raise ValueError('Expected request differs from frozen smoke')
    output = (ROOT / m['output']).resolve()
    output.relative_to(ROOT)
    if any(path.exists() for path in (output, Path(str(output) + '.attempts.jsonl'))):
        raise FileExistsError('Recovery output already exists; no replay')
    worst = paid.reservation(original['provider_endpoint'], 4096, '0.15', '0.6')
    if worst * 3 > CAP or m['per_request_reserve_usd'] != str(worst) or m['three_request_bound_usd'] != str(worst * 3):
        raise ValueError('Three-request reserve exceeds approved partition proposal')
    if budget_path is None and partition_id is None and receipt_path is None:
        return m, expected, None
    if not budget_path or not partition_id or not receipt_path:
        raise ValueError('Execute requires budget manifest, partition ID and review receipt')
    budget_path = Path(budget_path).resolve()
    budget_path.relative_to(ROOT)
    receipt_path = Path(receipt_path).resolve()
    receipt_path.relative_to(ROOT)
    receipt = json.loads(receipt_path.read_text())
    if receipt.get('approved') is not True or receipt.get('recovery_manifest_sha256') != expected_sha or receipt.get('wrapper_sha256') != sha(__file__) or receipt.get('budget_manifest_sha256') != sha(budget_path) or receipt.get('partition_id') != partition_id:
        raise ValueError('Missing exact root review')
    budget = json.loads(budget_path.read_text())
    entries = [p for p in budget.get('partitions', []) if p.get('id') == partition_id]
    if len(entries) != 1 or entries[0].get('model') != MODEL or entries[0].get('provider') != PROVIDER or entries[0].get('reasoning') != effort or paid.number(entries[0].get('cap_usd')) > CAP or paid.number(entries[0].get('cap_usd')) < worst * 3:
        raise ValueError('Budget partition does not bind this recovery')
    return m, expected, (budget_path, partition_id)


def execute(m, expected, budget):
    budget_path, partition_id = budget
    output = ROOT / m['output']
    args = SimpleNamespace(model=MODEL, provider=PROVIDER, reasoning=m['reasoning'], max_input_price=paid.Decimal('0.15'), max_output_price=paid.Decimal('0.6'), max_tokens=4096, phase='smoke', start=1, output=str(output), env_file=m['env_file'], timeout=300, budget_partition_manifest=str(budget_path), budget_partition_id=partition_id, continue_on_invalid_output=False, prompt_variant=None, parent_baseline_id=None)
    original_make = paid.make_payload
    original_partition = sys.modules.get('paid_budget_partitions')
    count = 0
    def checked_payload(*a, **kw):
        nonlocal count
        payload = original_make(*a, **kw)
        if count >= 3 or payload != expected[count]:
            raise ValueError('Live request differs from frozen smoke')
        count += 1
        return payload
    try:
        paid.make_payload = checked_payload
        sys.modules['paid_budget_partitions'] = partitions_v2
        paid.run(args)
    finally:
        paid.make_payload = original_make
        if original_partition is None:
            sys.modules.pop('paid_budget_partitions', None)
        else:
            sys.modules['paid_budget_partitions'] = original_partition


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', required=True)
    p.add_argument('--sha256', required=True)
    p.add_argument('--execute', action='store_true')
    p.add_argument('--budget-partition-manifest')
    p.add_argument('--budget-partition-id')
    p.add_argument('--review')
    a = p.parse_args()
    m, expected, budget = prepare(a.manifest, a.sha256, a.budget_partition_manifest if a.execute else None, a.budget_partition_id if a.execute else None, a.review if a.execute else None)
    if a.execute:
        execute(m, expected, budget)
    else:
        print(json.dumps({'preflight': 'ok', 'reasoning': m['reasoning'], 'records': m['record_ids'], 'three_request_bound_usd': m['three_request_bound_usd']}))

if __name__ == '__main__':
    main()
