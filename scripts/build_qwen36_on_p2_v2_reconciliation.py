#!/usr/bin/env python3
"""Reconcile closed Qwen3.6 on/P2 DEV-040–060 suffix without replay or inference."""
import argparse
import json
import math
from collections import Counter
from decimal import Decimal
from pathlib import Path

from development_benchmark import read_rows, score
from build_hosted_final_suffix_reconciliation import bound, digest, lines, terminal_gate

ROOT = Path(__file__).resolve().parents[1]
PLAN = Path('results/qwen36-on-p2-final21-v2/plan.json')
OUTPUT = Path('results/qwen36-on-p2-final21-v2/development.jsonl')
BUDGET = Path('results/hosted-recovery-budget-v2/manifest.json')
PARTITION = 'qwen36-on-p2-final21-v2'
DEST = Path('results/hosted-final-suffix-reconciled-v2/qwen36-on-p2.json')
IDS = [f'DEV-{i:03}' for i in range(1, 61)]
EXPECTED_SUFFIX = IDS[39:]


def sealed_budget(root):
    manifest_path = root / BUDGET
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('version') != 'paid-partitions-v1':
        raise ValueError('Unsupported partition manifest')
    entries = [item for item in manifest['partitions'] if item['id'] == PARTITION]
    if len(entries) != 1:
        raise ValueError('Missing unique final21 partition')
    entry = entries[0]
    if (entry['model'], entry['provider'], entry['reasoning']) != ('qwen/qwen3.6-35b-a3b', 'akashml/fp8', 'on'):
        raise ValueError('Final21 budget route differs')
    child = Path(entry['child_ledger'])
    events = lines(child)
    if not events or events[-1].get('event') != 'partition_closed':
        raise ValueError('Final21 partition is not sealed')
    child_sha = digest(child)
    master = Path(manifest['master_ledger'])
    matching = [event for event in lines(master) if event.get('event') == 'partition_reconciled' and
                event.get('partition_id') == PARTITION and event.get('child_sha256') == child_sha]
    if len(matching) != 1:
        raise ValueError('Master has no matching final21 reconciliation')
    event = matching[0]
    return {'manifest': {'file': str(BUDGET), 'sha256': digest(manifest_path)},
            'child': {'file': str(child.resolve().relative_to(root.resolve())), 'sha256': child_sha},
            'partition_id': PARTITION, 'known_actual_usd': event['known_actual_usd'],
            'unknown_upper_bound_usd': event['unknown_upper_bound_usd']}


def reconcile(root=ROOT):
    root = Path(root).resolve()
    plan_path = root / PLAN
    plan = json.loads(plan_path.read_text())
    if (plan.get('contract') != 'qwen36-on-p2-never-sent-final21-v2' or
        plan.get('record_ids') != EXPECTED_SUFFIX or
        plan.get('excluded_failed_ids') != ['DEV-033', 'DEV-039'] or
        plan.get('new_output') != str(OUTPUT) or
        plan.get('original_timing_preserved') is not False):
        raise ValueError('Unsupported final21 plan')
    bindings = plan['sources']
    original = lines(bound(root, bindings['original_result']))
    original_journal = bound(root, bindings['original_journal'])
    v1 = lines(bound(root, bindings['v1_result']))
    v1_journal = bound(root, bindings['v1_journal'])
    prior = json.loads(bound(root, bindings['v1_report']).read_text())
    bound(root, bindings['smoke_review'])
    if ([r['id'] for r in original + v1] != IDS[:39] or
        prior.get('attempted') != 39 or prior.get('valid_outputs') != 37 or
        prior.get('never_sent_ids') != EXPECTED_SUFFIX or
        prior.get('status_counts', {}).get('service_error') != 2 or
        prior['sources']['original']['sha256'] != bindings['original_result']['sha256'] or
        prior['sources']['suffix']['sha256'] != bindings['v1_result']['sha256']):
        raise ValueError('Prior reconciled prefix differs')
    # The immutable plan also binds the original/v1 journals. No DEV-040+
    # started claim may have existed before this new suffix.
    started = [event.get('id') for path in (original_journal, v1_journal)
               for event in lines(path) if event.get('event') == 'started']
    if started != IDS[:39]:
        raise ValueError('Prior started claims differ from DEV-001–039')
    for row in (original[-1], v1[-1]):
        if row.get('id') not in ('DEV-033', 'DEV-039') or row.get('status') != 'service_error' or row.get('http_status') != 429 or row.get('cost_unknown') is not True:
            raise ValueError('Preserved HTTP429 failure differs')
    output_path = root / OUTPUT
    suffix = lines(output_path)
    suffix_ids = [row['id'] for row in suffix]
    journal_path, terminal = terminal_gate(output_path, EXPECTED_SUFFIX, suffix_ids)
    if terminal.get('terminal_status') != suffix[-1].get('status'):
        raise ValueError('Final21 terminal status differs from saved result')
    attempts = original + v1 + suffix
    if [row['id'] for row in attempts] != IDS[:len(attempts)]:
        raise ValueError('Canonical 60-prefix coverage differs')
    never_sent = IDS[len(attempts):]
    budget = sealed_budget(root)
    refs = read_rows(root / 'data/pilot/proposed_labels.jsonl')
    pairs = json.loads((root / 'data/pilot/pairs.json').read_text())
    evaluation = score(refs, attempts, pairs)
    truth = {row['id']: row['proposed_labels'] for row in refs}
    all_four = sum(row.get('status') == 'ok' and row.get('prediction') == truth[row['id']] for row in attempts)
    known = sum((Decimal(str(row['observed_cost_usd'])) for row in attempts if row.get('observed_cost_usd') is not None), Decimal(0))
    unknown = sum((Decimal(str(row.get('reserved_cost_usd') or 0)) for row in attempts if row.get('cost_unknown')), Decimal(0))
    elapsed = [value for row in attempts if isinstance((value := row.get('elapsed_seconds')), (int, float)) and math.isfinite(value) and value >= 0]
    return {'contract': 'qwen36-on-p2-final21-reconciliation-v2',
            'configuration_id': 'openrouter-paid-qwen36-35b-a3b-on', 'condition': 'P2',
            'denominator': 60, 'attempted': len(attempts), 'never_sent_ids': never_sent,
            'never_sent_count': len(never_sent), 'coverage_complete': not never_sent,
            'status_counts': dict(Counter(row['status'] for row in attempts)),
            'valid_outputs': evaluation['valid_outputs'], 'all_four_correct': all_four,
            'eligible_paired_comparison': False, 'original_timing_preserved': False,
            'timing': {'attempts': len(attempts), 'elapsed_available': len(elapsed),
                       'sum_reported_attempt_seconds': sum(elapsed),
                       'complete': len(elapsed) == len(attempts),
                       'note': 'Per-request elapsed only; original counterbalanced timing was not preserved.'},
            'cost': {'known_observed_usd': str(known), 'unknown_reserved_upper_bound_usd': str(unknown),
                     'actual_total_usd': str(known) if not unknown else None,
                     'note': 'Development attempts only; both earlier HTTP429 attempts and any new failures retained. Unknown reserves are not observed spend; smoke excluded.'},
            'evaluation': evaluation,
            'sources': {'plan': {'file': str(PLAN), 'sha256': digest(plan_path)},
                        'original': bindings['original_result'], 'original_journal': bindings['original_journal'],
                        'suffix_v1': bindings['v1_result'], 'suffix_v1_journal': bindings['v1_journal'],
                        'prior_report': bindings['v1_report'],
                        'suffix_v2': {'file': str(OUTPUT), 'sha256': digest(output_path)},
                        'suffix_v2_journal': {'file': str(journal_path.relative_to(root)), 'sha256': digest(journal_path)},
                        'budget': budget},
            'terminal': {key: terminal.get(key) for key in ('attempted_records', 'planned_records', 'completed', 'terminal_status')}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    report = reconcile()
    destination = ROOT / DEST
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise ValueError('Immutable v2 reconciliation already exists')
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(destination)


if __name__ == '__main__':
    main()
