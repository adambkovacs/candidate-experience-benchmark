#!/usr/bin/env python3
"""Versioned Qwen8 recovery smoke gate using the unchanged JSON-object adapter."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import qwen8_hosted_adapter as adapter
import paid_budget_partitions_v2 as partitions_v2
from openrouter_paid_benchmark import number, reservation

ROOT = Path(__file__).resolve().parents[1]
CAP = number('0.06')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(binding):
    path = (ROOT / binding['file']).resolve()
    path.relative_to(ROOT)
    if sha(path) != binding['sha256']:
        raise ValueError('Recovery source hash mismatch: ' + binding['file'])
    return path


def prepare(manifest_path, manifest_sha, budget_path=None, partition_id=None, review_path=None):
    path = Path(manifest_path).resolve()
    path.relative_to(ROOT)
    if sha(path) != manifest_sha:
        raise ValueError('Recovery manifest hash mismatch')
    m = json.loads(path.read_text())
    mode = m.get('reasoning')
    if m.get('schema') != 'qwen8-hosted-recovery-v1' or mode not in ('off', 'on') or m.get('record_ids') != ['DEV-001', 'DEV-002', 'DEV-003'] or m.get('phase') != 'smoke3' or m.get('variant') != 'P0':
        raise ValueError('Invalid recovery condition')
    if m.get('model') != adapter.MODEL or m.get('provider') != adapter.PROVIDER or m.get('response_format') != 'json_object' or m.get('reference_labels_read') is not False or m.get('automatic_retries') is not False:
        raise ValueError('Model, output mode or protocol drift')
    bindings = m['sources']
    paths = {key: source(value) for key, value in bindings.items()}
    if paths['adapter'] != Path(adapter.__file__).resolve() or paths['partition_v2'] != Path(partitions_v2.__file__).resolve():
        raise ValueError('Bound source path differs from loaded code')
    rows, config, preview_manifest, old_receipt, _, _ = adapter.reviewed_preview(paths['preview'], paths['original_review'])
    if config['reasoning'] != mode or config['variant'] != 'P0' or config['phase'] != 'smoke3' or [r['id'] for r in rows] != m['record_ids'] or not old_receipt['continue_on_invalid_output']:
        raise ValueError('Original reviewed smoke differs')
    prior = [json.loads(line) for line in paths['historical_result'].read_text().splitlines() if line.strip()]
    expected_prior = (['ok', 'ok', 'service_error'] if mode == 'off' else ['invalid_output', 'service_error'])
    if [r.get('status') for r in prior] != expected_prior or [r.get('id') for r in prior] != m['record_ids'][:len(prior)] or prior[-1].get('http_status') != 429 or any(r.get('reasoning_effort') != mode for r in prior):
        raise ValueError('Historical outcomes differ; do not replay completed work silently')
    if any(r.get('request_sha256') != rows[i]['request_sha256'] for i, r in enumerate(prior)):
        raise ValueError('Historical request differs from recovery request')
    journal = [json.loads(line) for line in paths['historical_journal'].read_text().splitlines() if line.strip()]
    if not journal or journal[-1].get('event') != 'terminal' or journal[-1].get('completed') is not False:
        raise ValueError('Historical smoke is not terminal stopped')
    model, endpoint, _ = adapter.load_saved()
    reserve = reservation(endpoint, adapter.MAX_TOKENS, adapter.INPUT_CEILING, adapter.OUTPUT_CEILING)
    if reserve * 3 > CAP or m.get('per_call_reserve_usd') != str(reserve) or m.get('three_call_bound_usd') != str(reserve * 3) or m.get('proposed_partition_cap_usd') != str(CAP):
        raise ValueError('Three-call bound exceeds proposed partition')
    output = (ROOT / m['output']).resolve()
    output.relative_to(ROOT)
    if output.exists() or Path(str(output) + '.attempts.jsonl').exists():
        raise FileExistsError('Recovery output already exists; no replay')
    if budget_path is None and partition_id is None and review_path is None:
        return m, paths, None
    if not budget_path or not partition_id or not review_path:
        raise ValueError('Execution requires budget, partition and root review')
    budget_path = Path(budget_path).resolve()
    review_path = Path(review_path).resolve()
    budget_path.relative_to(ROOT)
    review_path.relative_to(ROOT)
    receipt = json.loads(review_path.read_text())
    if receipt.get('approved') is not True or receipt.get('recovery_manifest_sha256') != manifest_sha or receipt.get('wrapper_sha256') != sha(__file__) or receipt.get('budget_manifest_sha256') != sha(budget_path) or receipt.get('partition_id') != partition_id:
        raise ValueError('Missing exact root review')
    budget = json.loads(budget_path.read_text())
    entries = [e for e in budget.get('partitions', []) if e.get('id') == partition_id]
    if len(entries) != 1 or any(entries[0].get(k) != v for k, v in (('model', adapter.MODEL), ('provider', adapter.PROVIDER), ('reasoning', mode))) or not reserve * 3 <= number(entries[0].get('cap_usd')) <= CAP:
        raise ValueError('Budget partition differs from frozen recovery')
    return m, paths, (budget_path, partition_id)


def execute(m, paths, budget):
    budget_path, partition_id = budget
    args = SimpleNamespace(preview_file=str(paths['preview']), review_receipt=str(paths['original_review']), partition_manifest=str(budget_path), partition_id=partition_id, output=str(ROOT / m['output']), env_file=m['env_file'], timeout=300)
    original = sys.modules.get('paid_budget_partitions')
    try:
        sys.modules['paid_budget_partitions'] = partitions_v2
        adapter.execute(args)
    finally:
        if original is None:
            sys.modules.pop('paid_budget_partitions', None)
        else:
            sys.modules['paid_budget_partitions'] = original


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest', required=True)
    p.add_argument('--sha256', required=True)
    p.add_argument('--execute', action='store_true')
    p.add_argument('--budget-partition-manifest')
    p.add_argument('--budget-partition-id')
    p.add_argument('--review')
    a = p.parse_args()
    if not a.execute and any((a.budget_partition_manifest, a.budget_partition_id, a.review)):
        raise ValueError('Budget arguments require --execute')
    m, paths, budget = prepare(a.manifest, a.sha256, a.budget_partition_manifest, a.budget_partition_id, a.review)
    if a.execute:
        execute(m, paths, budget)
    else:
        print(json.dumps({'preflight':'ok','reasoning':m['reasoning'],'ids':m['record_ids'],'three_call_bound_usd':m['three_call_bound_usd']}))

if __name__ == '__main__':
    main()
