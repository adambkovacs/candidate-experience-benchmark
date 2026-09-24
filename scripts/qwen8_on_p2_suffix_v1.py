#!/usr/bin/env python3
"""Offline gate and reviewed execution of never-sent Qwen8 on/P2 DEV-028–060."""
import argparse
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

import qwen8_hosted_adapter as adapter
import paid_budget_partitions_v2 as partitions
from openrouter_paid_benchmark import number, reservation

ROOT = Path(__file__).resolve().parents[1]
RESULT = ROOT / 'results/qwen8-hosted-on-p2-suffix-v1'
PLAN = RESULT / 'plan.json'
ORIGINAL = ROOT / 'results/qwen8-hosted-prompt-full60-prep-v1/on-p2-full60-results.jsonl'
JOURNAL = Path(str(ORIGINAL) + '.attempts.jsonl')
CHILD = ROOT / 'results/qwen8-hosted-prompt-full60-budget-v1/manifest-qwen8-prompt-full60-v1-on-p2.jsonl'
PREVIEW = ROOT / 'results/openrouter-qwen3-8b-hosted-plan-2026-09-24/preview-v1/on-p2-full60.jsonl'
ORIGINAL_REVIEW = ROOT / 'results/qwen8-hosted-prompt-full60-prep-v1/on-p2-root-review.json'
ORIGINAL_PLAN = ROOT / 'results/qwen8-hosted-prompt-full60-prep-v1/on-p2-full60-plan.json'
OUTPUT = RESULT / 'dev028-060-results.jsonl'
IDS = [f'DEV-{i:03}' for i in range(28, 61)]
RESERVE = Decimal('0.017199104')
CAP = Decimal('0.57')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind(path):
    return {'file': str(path.relative_to(ROOT)), 'sha256': sha(path)}


def bound(binding):
    path = (ROOT / binding['file']).resolve()
    path.relative_to(ROOT)
    if sha(path) != binding['sha256']:
        raise ValueError('Source hash mismatch: ' + binding['file'])
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def prefix(result, journal, child, preview):
    saved, events, ledger, requests = rows(result), rows(journal), rows(child), rows(preview)
    if len(saved) != 26 or [r.get('id') for r in saved] != [f'DEV-{i:03}' for i in range(1, 27)]:
        raise ValueError('Original results are not exact DEV001-026 prefix')
    if len(requests) != 60 or [r.get('id') for r in requests] != [f'DEV-{i:03}' for i in range(1, 61)]:
        raise ValueError('Original preview is not canonical60')
    expected = []
    for i in range(1, 27):
        expected += [('started', f'DEV-{i:03}'), ('finished', f'DEV-{i:03}')]
    expected.append(('started', 'DEV-027'))
    if [(e.get('event'), e.get('id')) for e in events] != expected:
        raise ValueError('Original attempts are not 26 finished plus ambiguous DEV027')
    started = {e['id']: e for e in events if e['event'] == 'started'}
    finished = {e['id']: e for e in events if e['event'] == 'finished'}
    for saved_row, request in zip(saved, requests):
        rid = saved_row['id']
        if (saved_row.get('status') not in ('ok', 'invalid_output') or
            saved_row.get('billing_ok') is not True or saved_row.get('cost_unknown') is not False or
            saved_row.get('request') != request['request'] or
            saved_row.get('request_sha256') != request['request_sha256'] or
            saved_row.get('input_sha256') != request['input_sha256'] or
            saved_row.get('reference_labels_read') is not False or
            saved_row.get('reasoning_effort') != 'on' or
            saved_row.get('attempt_id') != started[rid].get('attempt_id') or
            saved_row.get('attempt_id') != finished[rid].get('attempt_id')):
            raise ValueError('Original completed record or exact request differs')
    if started['DEV-027'].get('request') != requests[26]['request'] or started['DEV-027'].get('request_sha256') != requests[26]['request_sha256']:
        raise ValueError('Ambiguous DEV027 request differs')
    if len([e for e in ledger if e.get('event') == 'reserve']) != 27 or len([e for e in ledger if e.get('event') == 'settle']) != 26:
        raise ValueError('Original child ledger attempt counts differ')
    reserves = [e for e in ledger if e.get('event') == 'reserve']
    if [e.get('record_id') for e in reserves] != [f'DEV-{i:03}' for i in range(1, 28)]:
        raise ValueError('Original child ledger IDs differ')
    if reserves[-1].get('attempt_id') != started['DEV-027'].get('attempt_id') or number(reserves[-1].get('usd')) != RESERVE:
        raise ValueError('Ambiguous DEV027 reservation differs')
    return {'completed_ids': [r['id'] for r in saved], 'ambiguous_id': 'DEV-027',
            'never_sent_ids': IDS, 'original_result_sha256': sha(result),
            'original_journal_sha256': sha(journal), 'original_child_ledger_sha256_at_preparation': sha(child)}


def verify(plan_path, plan_sha=None):
    plan_path = Path(plan_path).resolve()
    plan_path.relative_to(RESULT)
    if plan_sha and sha(plan_path) != plan_sha:
        raise ValueError('Suffix plan SHA mismatch')
    plan = json.loads(plan_path.read_text())
    if (plan.get('schema') != 'qwen8-on-p2-never-sent-suffix-v1' or
        plan.get('model') != adapter.MODEL or plan.get('provider') != adapter.PROVIDER or
        plan.get('reasoning') != 'on' or plan.get('variant') != 'P2' or
        plan.get('phase') != 'development_suffix' or plan.get('ids') != IDS or
        plan.get('excluded_ambiguous_id') != 'DEV-027' or
        plan.get('reference_labels_read') is not False or
        plan.get('automatic_retries') is not False or
        plan.get('continue_on_invalid_output') is not True or
        plan.get('per_call_reserve_usd') != str(RESERVE) or
        plan.get('bound_usd') != str(RESERVE * 33) or
        plan.get('max_partition_usd') != str(CAP) or
        plan.get('output') != str(OUTPUT.relative_to(ROOT))):
        raise ValueError('Suffix protocol drift')
    sources = {name: bound(binding) for name, binding in plan['sources'].items()}
    expected_sources = {'original': ORIGINAL, 'journal': JOURNAL, 'preview': PREVIEW,
                        'original_review': ORIGINAL_REVIEW, 'original_plan': ORIGINAL_PLAN,
                        'adapter': Path(adapter.__file__).resolve(),
                        'partitions': Path(partitions.__file__).resolve()}
    if any(sources.get(key) != path for key, path in expected_sources.items()) or set(sources) != set(expected_sources):
        raise ValueError('Suffix source path drift')
    audited = prefix(ORIGINAL, JOURNAL, CHILD, PREVIEW)
    if {k: audited[k] for k in ('completed_ids', 'ambiguous_id', 'never_sent_ids', 'original_result_sha256', 'original_journal_sha256')} != plan.get('prefix'):
        raise ValueError('Frozen original prefix differs')
    original_receipt = json.loads(ORIGINAL_REVIEW.read_text())
    preview_rows, config, manifest, _, _, _ = adapter.reviewed_preview(PREVIEW, ORIGINAL_REVIEW)
    if (original_receipt.get('approved') is not True or
        original_receipt.get('full60_plan_sha256') != sha(ORIGINAL_PLAN) or
        config.get('reasoning') != 'on' or config.get('variant') != 'P2' or
        config.get('phase') != 'full60' or len(preview_rows) != 60 or
        [r['id'] for r in preview_rows[27:]] != IDS):
        raise ValueError('Original reviewed full60 preview differs')
    _, endpoint, _ = adapter.load_saved()
    if reservation(endpoint, adapter.MAX_TOKENS, adapter.INPUT_CEILING, adapter.OUTPUT_CEILING) != RESERVE:
        raise ValueError('Frozen per-call reserve differs')
    if OUTPUT.exists() or Path(str(OUTPUT) + '.attempts.jsonl').exists():
        raise FileExistsError('Suffix output already exists; no replay')
    return plan, preview_rows, config, manifest


def build():
    if PLAN.exists():
        raise FileExistsError('Suffix plan already exists')
    RESULT.mkdir(parents=True, exist_ok=True)
    audited = prefix(ORIGINAL, JOURNAL, CHILD, PREVIEW)
    source_paths = {'original': ORIGINAL, 'journal': JOURNAL, 'preview': PREVIEW,
                    'original_review': ORIGINAL_REVIEW, 'original_plan': ORIGINAL_PLAN,
                    'adapter': Path(adapter.__file__).resolve(),
                    'partitions': Path(partitions.__file__).resolve()}
    plan = {'schema': 'qwen8-on-p2-never-sent-suffix-v1', 'model': adapter.MODEL,
            'provider': adapter.PROVIDER, 'reasoning': 'on', 'variant': 'P2',
            'phase': 'development_suffix', 'ids': IDS,
            'excluded_ambiguous_id': 'DEV-027', 'reference_labels_read': False,
            'automatic_retries': False, 'continue_on_invalid_output': True,
            'original_timing_preserved': False,
            'per_call_reserve_usd': str(RESERVE), 'bound_usd': str(RESERVE * 33),
            'max_partition_usd': str(CAP), 'output': str(OUTPUT.relative_to(ROOT)),
            'prefix': {k: audited[k] for k in ('completed_ids', 'ambiguous_id', 'never_sent_ids', 'original_result_sha256', 'original_journal_sha256')},
            'sources': {name: bind(path) for name, path in source_paths.items()}}
    with PLAN.open('x') as stream:
        json.dump(plan, stream, indent=2)
        stream.write('\n')
    verify(PLAN)
    return PLAN


def execute(plan_path, plan_sha, budget_path, partition_id, review_path, env_file, timeout):
    plan, full_rows, config, manifest = verify(plan_path, plan_sha)
    if timeout != 300:
        raise ValueError('Frozen 300-second timeout required')
    budget_path = Path(budget_path).resolve(); budget_path.relative_to(ROOT)
    review_path = Path(review_path).resolve(); review_path.relative_to(RESULT)
    receipt = json.loads(review_path.read_text())
    if (receipt.get('approved') is not True or receipt.get('plan_sha256') != plan_sha or
        receipt.get('script_sha256') != sha(__file__) or
        receipt.get('budget_manifest_sha256') != sha(budget_path) or
        receipt.get('partition_id') != partition_id or
        receipt.get('ambiguous_id') != 'DEV-027' or
        receipt.get('continue_on_invalid_output') is not True):
        raise ValueError('Missing exact root suffix review')
    budget = json.loads(budget_path.read_text())
    if budget.get('version') != 'paid-partitions-v1' or budget.get('master_ledger') != str(adapter.MASTER_LEDGER):
        raise ValueError('Budget manifest differs')
    matches = [entry for entry in budget.get('partitions', []) if entry.get('id') == partition_id]
    if len(matches) != 1 or any(matches[0].get(k) != v for k, v in
                               (('model', adapter.MODEL), ('provider', adapter.PROVIDER), ('reasoning', 'on'))):
        raise ValueError('Exact suffix partition differs')
    if not RESERVE * 33 <= number(matches[0].get('cap_usd')) <= CAP:
        raise ValueError('Insufficient or excessive suffix partition')
    child_events = rows(CHILD)
    unknown = [e for e in child_events if e.get('event') == 'unknown_cost_accounted_as_upper_bound']
    if (len(unknown) != 1 or unknown[0].get('attempt_id') !=
        next(e['attempt_id'] for e in child_events if e.get('event') == 'reserve' and e.get('record_id') == 'DEV-027') or
        number(unknown[0].get('usd')) != RESERVE or
        child_events[-1].get('event') != 'partition_closed'):
        raise ValueError('Original DEV027 unknown bound is not sealed')
    # The reviewed adapter keeps all live routing, price, auth, billing and stop controls.
    # Only its already-verified canonical preview is narrowed to never-sent IDs.
    original = adapter.reviewed_preview(PREVIEW, ORIGINAL_REVIEW)
    subset_config = dict(config, phase='development_suffix', rows=33, ids=IDS)
    selected = (full_rows[27:], subset_config, manifest, dict(original[3], continue_on_invalid_output=True),
                original[4], sha(review_path))
    from types import SimpleNamespace
    args = SimpleNamespace(preview_file=str(PREVIEW), review_receipt=str(review_path),
                           partition_manifest=str(budget_path), partition_id=partition_id,
                           output=str(OUTPUT), env_file=env_file, timeout=timeout)
    old = sys.modules.get('paid_budget_partitions')
    try:
        sys.modules['paid_budget_partitions'] = partitions
        with patch.object(adapter, 'reviewed_preview', return_value=selected):
            adapter.execute(args)
    finally:
        if old is None: sys.modules.pop('paid_budget_partitions', None)
        else: sys.modules['paid_budget_partitions'] = old


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--plan', type=Path, default=PLAN)
    parser.add_argument('--sha256')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--budget-manifest')
    parser.add_argument('--partition-id')
    parser.add_argument('--review')
    parser.add_argument('--env-file')
    parser.add_argument('--timeout', type=float, default=300)
    args = parser.parse_args()
    if args.build:
        print(build(), sha(PLAN))
    elif args.execute:
        if not all((args.sha256, args.budget_manifest, args.partition_id, args.review, args.env_file)):
            raise ValueError('Execute requires exact plan, budget, partition, review and env')
        execute(args.plan, args.sha256, args.budget_manifest, args.partition_id,
                args.review, args.env_file, args.timeout)
    else:
        if not args.sha256:
            raise ValueError('Preflight requires --sha256')
        plan, *_ = verify(args.plan, args.sha256)
        print(json.dumps({'preflight': 'ok', 'ids': len(plan['ids']),
                          'never_sent_first': plan['ids'][0], 'never_sent_last': plan['ids'][-1],
                          'bound_usd': plan['bound_usd']}))


if __name__ == '__main__': main()
