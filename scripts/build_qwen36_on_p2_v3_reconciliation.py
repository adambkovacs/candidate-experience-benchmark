#!/usr/bin/env python3
"""Reconcile a sealed Qwen3.6 on/P2 final-20 continuation without inference."""
import argparse
import hashlib
import json
import math
from collections import Counter
from decimal import Decimal
from pathlib import Path

from development_benchmark import read_rows, score
from build_hosted_final_suffix_reconciliation import bound, digest, lines, terminal_gate

ROOT = Path(__file__).resolve().parents[1]
PLAN = Path('results/qwen36-on-p2-final20-v3/plan.json')
OUTPUT = Path('results/qwen36-on-p2-final20-v3/development.jsonl')
DEST = Path('results/hosted-final-suffix-reconciled-v3/qwen36-on-p2.json')
CONTROLLER = Path('scripts/qwen36_on_p2_suffix_v3.py')
IDS = [f'DEV-{i:03}' for i in range(1, 61)]
FINAL = IDS[40:]
RESERVE = Decimal('0.0299008')
CAP = Decimal('0.64')


def relative(root, path):
    path = Path(path).resolve()
    return str(path.relative_to(root.resolve()))


def sealed_budget(root, manifest_path, partition_id):
    manifest_path = Path(manifest_path).resolve()
    relative(root, manifest_path)
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('version') != 'paid-partitions-v1':
        raise ValueError('Unsupported partition manifest')
    master = Path(manifest['master_ledger']).resolve()
    if master != root / 'results/openrouter-paid-budget.jsonl':
        raise ValueError('Wrong master ledger')
    entries = [item for item in manifest['partitions'] if item.get('id') == partition_id]
    if len(entries) != 1:
        raise ValueError('Missing unique final20 partition')
    entry = entries[0]
    if (entry.get('model'), entry.get('provider'), entry.get('reasoning')) != (
        'qwen/qwen3.6-35b-a3b', 'akashml/fp8', 'on'
    ) or not RESERVE * 20 <= Decimal(str(entry.get('cap_usd'))) <= CAP:
        raise ValueError('Final20 budget route or cap differs')
    child = Path(entry['child_ledger']).resolve()
    relative(root, child)
    events = lines(child)
    if not events or events[-1].get('event') != 'partition_closed':
        raise ValueError('Final20 partition is not sealed')
    child_sha = digest(child)
    matches = [event for event in lines(master) if event.get('event') == 'partition_reconciled'
               and event.get('partition_id') == partition_id and event.get('child_sha256') == child_sha]
    if len(matches) != 1:
        raise ValueError('Master has no matching final20 reconciliation')
    event = matches[0]
    return {'manifest': {'file': relative(root, manifest_path), 'sha256': digest(manifest_path)},
            'child': {'file': relative(root, child), 'sha256': child_sha},
            'partition_id': partition_id, 'known_actual_usd': event['known_actual_usd'],
            'unknown_upper_bound_usd': event['unknown_upper_bound_usd']}


def reconcile(root=ROOT, budget_manifest=None, partition_id=None, review_path=None):
    root = Path(root).resolve()
    if not all((budget_manifest, partition_id, review_path)):
        raise ValueError('Sealed budget manifest, partition ID, and review receipt required')
    plan_path = root / PLAN
    plan = json.loads(plan_path.read_text())
    if (plan.get('contract') != 'qwen36-on-p2-never-sent-final20-v3' or
        plan.get('configuration_id') != 'openrouter-paid-qwen36-35b-a3b-on' or
        plan.get('condition') != 'P2' or plan.get('reasoning') != 'on' or
        plan.get('record_ids') != FINAL or
        plan.get('excluded_failed_ids') != ['DEV-033', 'DEV-039', 'DEV-040'] or
        plan.get('new_output') != str(OUTPUT) or
        plan.get('original_timing_preserved') is not False or
        plan.get('per_call_reserve_usd') != str(RESERVE) or
        Decimal(plan.get('call_bound_usd', '-1')) != RESERVE * 20 or
        plan.get('proposed_partition_cap_usd') != str(CAP) or
        len(plan.get('requests', [])) != 20):
        raise ValueError('Unsupported final20 plan')
    sources = plan['sources']
    original = lines(bound(root, sources['original_result']))
    original_journal = lines(bound(root, sources['original_journal']))
    v1 = lines(bound(root, sources['v1_result']))
    v1_journal = lines(bound(root, sources['v1_journal']))
    v2 = lines(bound(root, sources['v2_result']))
    v2_journal = lines(bound(root, sources['v2_journal']))
    bound(root, sources['v2_plan'])
    bound(root, sources['v1_report'])
    bound(root, sources['smoke_review'])
    bound(root, plan['frozen_execution'])
    bound(root, plan['route_audit'])
    prior = json.loads(bound(root, sources['v2_report']).read_text())
    if ([r.get('id') for r in original + v1 + v2] != IDS[:40] or
        [r.get('id') for r in v2] != ['DEV-040'] or
        [e.get('id') for e in original_journal + v1_journal + v2_journal
         if e.get('event') == 'started'] != IDS[:40] or
        not v2_journal or v2_journal[-1].get('event') != 'terminal' or
        v2_journal[-1].get('attempted_records') != 1 or
        v2_journal[-1].get('planned_records') != 21 or
        v2_journal[-1].get('terminal_status') != 'service_error' or
        v2_journal[-1].get('completed') is not False or
        prior.get('contract') != 'qwen36-on-p2-final21-reconciliation-v2' or
        prior.get('attempted') != 40 or prior.get('valid_outputs') != 37 or
        prior.get('never_sent_ids') != FINAL or
        prior.get('status_counts', {}).get('service_error') != 3 or
        prior.get('eligible_paired_comparison') is not False or
        prior.get('sources', {}).get('prior_report', {}).get('sha256') != sources['v1_report']['sha256'] or
        prior.get('sources', {}).get('suffix_v2', {}).get('sha256') != sources['v2_result']['sha256'] or
        prior.get('sources', {}).get('suffix_v2_journal', {}).get('sha256') != sources['v2_journal']['sha256']):
        raise ValueError('Prior 40-position evidence differs')
    for row, ident in ((original[-1], 'DEV-033'), (v1[-1], 'DEV-039'), (v2[-1], 'DEV-040')):
        if (row.get('id') != ident or row.get('status') != 'service_error' or
            row.get('http_status') != 429 or row.get('cost_unknown') is not True):
            raise ValueError('Preserved HTTP429 failure differs')
    plan_sha = digest(plan_path)
    review_path = Path(review_path).resolve()
    relative(root, review_path)
    review = json.loads(review_path.read_text())
    budget_path = Path(budget_manifest).resolve()
    if (review.get('approved') is not True or review.get('suffix_plan_sha256') != plan_sha or
        review.get('wrapper_sha256') != digest(root / CONTROLLER) or
        review.get('budget_manifest_sha256') != digest(budget_path) or
        review.get('partition_id') != partition_id or
        review.get('preserved_v2_report_sha256') != sources['v2_report']['sha256'] or
        review.get('continue_on_known_billing_intrinsic_invalid') is not True):
        raise ValueError('Final20 root review binding differs')
    budget = sealed_budget(root, budget_path, partition_id)
    output_path = root / OUTPUT
    suffix = lines(output_path)
    actual_ids = [row.get('id') for row in suffix]
    journal_path, terminal = terminal_gate(output_path, FINAL, actual_ids)
    events = lines(journal_path)
    started = [event for event in events if event.get('event') == 'started']
    finished = [event for event in events if event.get('event') == 'finished']
    if (len(events) != 2 * len(suffix) + 1 or len(started) != len(suffix) or
        len(finished) != len(suffix) or
        [event.get('id') for event in started] != actual_ids or
        [event.get('id') for event in finished] != actual_ids or
        terminal.get('plan_sha256') != plan_sha or
        terminal.get('condition') != 'P2' or terminal.get('reasoning') != 'on' or
        terminal.get('terminal_status') != suffix[-1].get('status')):
        raise ValueError('Final20 journal linkage differs')
    for index, row in enumerate(suffix):
        start, finish = events[2 * index:2 * index + 2]
        envelope = json.loads(bound(root, plan['requests'][index]).read_text())
        request = envelope['request']
        request_sha = hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()
        recovery = row.get('prompt_recovery') or {}
        if (start.get('event') != 'started' or finish.get('event') != 'finished' or
            row.get('attempt_id') != start.get('attempt_id') or
            row.get('attempt_id') != finish.get('attempt_id') or
            row.get('request') != request or row.get('request_sha256') != request_sha or
            start.get('request_sha256') != request_sha or
            finish.get('status') != row.get('status') or
            row.get('budget_partition_id') != partition_id or
            row.get('requested_model') != 'qwen/qwen3.6-35b-a3b' or
            row.get('reasoning_effort') != 'on' or
            row.get('quantization') != 'fp8' or
            row.get('reference_labels_read') is not False or
            recovery.get('contract') != plan['contract'] or
            recovery.get('plan_sha256') != plan_sha or
            recovery.get('prior_report_sha256') != sources['v2_report']['sha256'] or
            recovery.get('review_receipt_sha256') != digest(review_path)):
            raise ValueError('Final20 row request, review, or attempt linkage differs')
    suffix_known = sum((Decimal(str(row['observed_cost_usd'])) for row in suffix
                        if row.get('observed_cost_usd') is not None), Decimal(0))
    suffix_unknown = sum((Decimal(str(row.get('reserved_cost_usd') or 0)) for row in suffix
                          if row.get('cost_unknown')), Decimal(0))
    if (suffix_known != Decimal(str(budget['known_actual_usd'])) or
        suffix_unknown != Decimal(str(budget['unknown_upper_bound_usd']))):
        raise ValueError('Final20 saved billing and sealed partition differ')
    if any(row.get('cost_unknown') or row.get('status') in
           ('service_error', 'control_violation', 'model_mismatch', 'provider_mismatch')
           for row in suffix[:-1]):
        raise ValueError('Final20 continued past a terminal service or billing failure')
    attempts = original + v1 + v2 + suffix
    if [row['id'] for row in attempts] != IDS[:len(attempts)]:
        raise ValueError('Canonical 60-prefix coverage differs')
    never_sent = IDS[len(attempts):]
    refs = read_rows(root / 'data/pilot/proposed_labels.jsonl')
    pairs = json.loads((root / 'data/pilot/pairs.json').read_text())
    evaluation = score(refs, attempts, pairs)
    truth = {row['id']: row['proposed_labels'] for row in refs}
    all_four = sum(row.get('status') == 'ok' and row.get('prediction') == truth[row['id']] for row in attempts)
    known = sum((Decimal(str(row['observed_cost_usd'])) for row in attempts
                 if row.get('observed_cost_usd') is not None), Decimal(0))
    unknown = sum((Decimal(str(row.get('reserved_cost_usd') or 0)) for row in attempts
                   if row.get('cost_unknown')), Decimal(0))
    elapsed = [value for row in attempts if isinstance((value := row.get('elapsed_seconds')), (int, float))
               and math.isfinite(value) and value >= 0]
    return {'contract': 'qwen36-on-p2-final20-reconciliation-v3',
            'configuration_id': plan['configuration_id'], 'condition': 'P2',
            'denominator': 60, 'attempted': len(attempts), 'never_sent_ids': never_sent,
            'never_sent_count': len(never_sent), 'coverage_complete': not never_sent,
            'status_counts': dict(Counter(row['status'] for row in attempts)),
            'valid_outputs': evaluation['valid_outputs'], 'all_four_correct': all_four,
            'eligible_paired_comparison': False, 'original_timing_preserved': False,
            'timing': {'attempts': len(attempts), 'elapsed_available': len(elapsed),
                       'sum_reported_attempt_seconds': sum(elapsed),
                       'complete': len(elapsed) == len(attempts),
                       'note': 'Per-request elapsed only; original counterbalanced timing was not preserved.'},
            'cost': {'known_observed_usd': str(known),
                     'unknown_reserved_upper_bound_usd': str(unknown),
                     'actual_total_usd': str(known) if not unknown else None,
                     'note': 'Development attempts only; retained HTTP429 failures included. Unknown reserves are not observed spend; smoke excluded.'},
            'evaluation': evaluation,
            'sources': {'plan': {'file': str(PLAN), 'sha256': plan_sha},
                        'controller': {'file': str(CONTROLLER), 'sha256': digest(root / CONTROLLER)},
                        'original': sources['original_result'],
                        'original_journal': sources['original_journal'],
                        'suffix_v1': sources['v1_result'], 'suffix_v1_journal': sources['v1_journal'],
                        'suffix_v2': sources['v2_result'], 'suffix_v2_journal': sources['v2_journal'],
                        'prior_report': sources['v2_report'],
                        'suffix_v3': {'file': str(OUTPUT), 'sha256': digest(output_path)},
                        'suffix_v3_journal': {'file': relative(root, journal_path), 'sha256': digest(journal_path)},
                        'review': {'file': relative(root, review_path), 'sha256': digest(review_path)},
                        'budget': budget},
            'terminal': {key: terminal.get(key) for key in
                         ('attempted_records', 'planned_records', 'completed', 'terminal_status')}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--budget-manifest', required=True)
    parser.add_argument('--partition-id', required=True)
    parser.add_argument('--review', required=True)
    args = parser.parse_args()
    report = reconcile(ROOT, args.budget_manifest, args.partition_id, args.review)
    destination = ROOT / DEST
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise ValueError('Immutable v3 reconciliation already exists')
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(destination)


if __name__ == '__main__':
    main()
