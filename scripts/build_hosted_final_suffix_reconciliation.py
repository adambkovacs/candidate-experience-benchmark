#!/usr/bin/env python3
"""Offline, hash-bound reconciliation of three explicitly authorized hosted suffixes."""
import argparse
import hashlib
import json
import math
from collections import Counter
from decimal import Decimal
from pathlib import Path

from development_benchmark import score, read_rows

ROOT = Path(__file__).resolve().parents[1]
OUT = Path('results/hosted-final-suffix-reconciled-v1')
SPECS = {
    'qwen36-off-p2': {
        'plan': 'results/qwen36-prompt-recovery-v1/off-p2-dev054-060-suffix-plan.json',
        'output': 'results/qwen36-prompt-recovery-v1/off-p2-dev054-060-suffix.jsonl',
        'partition': 'qwen36-off-p2-suffix-v1',
        'parent': 'openrouter-paid-qwen36-35b-a3b-off',
        'failed': 'DEV-053',
    },
    'qwen36-on-p2': {
        'plan': 'results/qwen36-prompt-recovery-v1/on-p2-dev034-060-suffix-plan.json',
        'output': 'results/qwen36-prompt-recovery-v1/on-p2-dev034-060-suffix.jsonl',
        'partition': 'qwen36-on-p2-suffix-v1',
        'parent': 'openrouter-paid-qwen36-35b-a3b-on',
        'failed': 'DEV-033',
    },
    'qwen8-on-p2': {
        'plan': 'results/qwen8-hosted-on-p2-suffix-v1/plan.json',
        'output': 'results/qwen8-hosted-on-p2-suffix-v1/dev028-060-results.jsonl',
        'interruption': 'results/qwen8-hosted-on-p2-suffix-v1/dev027-interruption-evidence.jsonl',
        'partition': 'qwen8-on-p2-suffix-v1',
        'parent': 'openrouter-qwen3-8b-on-json-object-p0',
        'failed': 'DEV-027',
    },
}
BUDGET = Path('results/hosted-final-suffix-budget-v1/manifest.json')
IDS = [f'DEV-{i:03}' for i in range(1, 61)]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def bound(root, binding):
    path = (root / binding['file']).resolve()
    path.relative_to(root.resolve())
    if digest(path) != binding['sha256']:
        raise ValueError('Source hash mismatch: ' + binding['file'])
    return path


def budget_gate(root, partition):
    manifest_path = root / BUDGET
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('version') != 'paid-partitions-v1':
        raise ValueError('Unsupported budget manifest')
    entries = [entry for entry in manifest['partitions'] if entry['id'] == partition]
    if len(entries) != 1:
        raise ValueError('Missing unique budget partition')
    entry = entries[0]
    child = Path(entry['child_ledger'])
    master = Path(manifest['master_ledger'])
    child_events = lines(child)
    if not child_events or child_events[-1].get('event') != 'partition_closed':
        raise ValueError('Budget partition is not sealed')
    child_sha = digest(child)
    matching = [event for event in lines(master) if event.get('event') == 'partition_reconciled' and
                event.get('partition_id') == partition and event.get('child_sha256') == child_sha]
    if len(matching) != 1:
        raise ValueError('Master ledger lacks matching partition reconciliation')
    event = matching[0]
    return {'manifest': {'file': str(BUDGET), 'sha256': digest(manifest_path)},
            'child': {'file': str(child.resolve().relative_to(root.resolve())), 'sha256': child_sha},
            'partition_id': partition, 'known_actual_usd': event['known_actual_usd'],
            'unknown_upper_bound_usd': event['unknown_upper_bound_usd']}


def terminal_gate(path, expected_ids, actual_ids):
    journal = Path(str(path) + '.attempts.jsonl')
    events = lines(journal)
    if not events or events[-1].get('event') != 'terminal':
        raise ValueError('Suffix is not terminal')
    event = events[-1]
    if actual_ids != expected_ids[:len(actual_ids)] or not actual_ids:
        raise ValueError('Suffix results are not the exact planned prefix')
    if event.get('attempted_records') != len(actual_ids) or event.get('planned_records') != len(expected_ids) or event.get('completed') is not (len(actual_ids) == len(expected_ids)):
        raise ValueError('Suffix terminal disagrees with saved prefix')
    return journal, event


def reconcile(key, root=ROOT):
    root = Path(root).resolve()
    spec = SPECS[key]
    plan_path = root / spec['plan']
    plan = json.loads(plan_path.read_text())
    qwen8 = 'interruption' in spec
    expected = plan['ids'] if qwen8 else plan['record_ids']
    if expected != [ident for ident in IDS if ident > spec['failed']]:
        raise ValueError('Suffix plan is not the exact never-sent suffix')
    if (plan['excluded_ambiguous_id'] if qwen8 else plan['excluded_failed_id']) != spec['failed']:
        raise ValueError('Original failed ID changed')
    original_binding = plan['sources']['original'] if qwen8 else plan['original_result']
    journal_binding = plan['sources']['journal'] if qwen8 else plan['original_journal']
    original_path = bound(root, original_binding)
    bound(root, journal_binding)
    suffix_path = root / spec['output']
    suffix = lines(suffix_path)
    suffix_ids = [row['id'] for row in suffix]
    journal_path, terminal = terminal_gate(suffix_path, expected, suffix_ids)
    if terminal.get('terminal_status') != suffix[-1].get('status'):
        raise ValueError('Suffix terminal status differs from last saved attempt')
    original = lines(original_path)
    if qwen8:
        interruption_path = root / spec['interruption']
        interruption = lines(interruption_path)
        if len(interruption) != 1 or interruption[0]['id'] != spec['failed'] or interruption[0]['status'] != 'interrupted_no_provider_result' or interruption[0]['source_result_sha256'] != original_binding['sha256'] or interruption[0]['source_journal_sha256'] != journal_binding['sha256']:
            raise ValueError('Qwen8 interruption receipt does not bind original attempt')
        if [row['id'] for row in original] != IDS[:26]:
            raise ValueError('Qwen8 original prefix is not exactly 26 saved outcomes')
        attempts = original + interruption + suffix
        interruption_binding = {'file': spec['interruption'], 'sha256': digest(interruption_path)}
    else:
        if [row['id'] for row in original] != IDS[:IDS.index(spec['failed']) + 1] or original[-1]['status'] != 'service_error':
            raise ValueError('Qwen36 original failed prefix changed')
        attempts = original + suffix
        interruption_binding = None
    if [row['id'] for row in attempts] != IDS[:len(attempts)]:
        raise ValueError('Reconciled IDs must be the canonical prefix without overlap')
    never_sent = IDS[len(attempts):]
    budget = budget_gate(root, spec['partition'])
    refs = read_rows(root / 'data/pilot/proposed_labels.jsonl')
    pairs = json.loads((root / 'data/pilot/pairs.json').read_text())
    evaluation = score(refs, attempts, pairs)
    truth = {row['id']: row['proposed_labels'] for row in refs}
    all_four = sum(row.get('status') == 'ok' and row.get('prediction') == truth[row['id']] for row in attempts)
    known = sum((Decimal(str(row['observed_cost_usd'])) for row in attempts if row.get('observed_cost_usd') is not None), Decimal(0))
    unknown = sum((Decimal(str(row.get('reserved_cost_usd') or 0)) for row in attempts if row.get('cost_unknown')), Decimal(0))
    elapsed = [row.get('elapsed_seconds') for row in attempts]
    elapsed_values = [v for v in elapsed if isinstance(v, (int, float)) and math.isfinite(v) and v >= 0]
    report = {
        'contract': 'hosted-final-suffix-reconciliation-v1', 'configuration_id': spec['parent'],
        'condition': 'P2', 'denominator': 60, 'status_counts': dict(Counter(row['status'] for row in attempts)),
        'attempted': len(attempts), 'never_sent_ids': never_sent, 'never_sent_count': len(never_sent),
        'coverage_complete': not never_sent, 'valid_outputs': evaluation['valid_outputs'], 'all_four_correct': all_four,
        'eligible_paired_comparison': False, 'original_timing_preserved': False,
        'timing': {'attempts': len(attempts), 'elapsed_available': len(elapsed_values),
                   'sum_reported_attempt_seconds': sum(elapsed_values),
                   'complete': len(elapsed_values) == len(attempts),
                   'note': 'Per-request elapsed values only; unknown interruption time is not zero and original counterbalanced timing is not reconstructed.'},
        'cost': {'known_observed_usd': str(known), 'unknown_reserved_upper_bound_usd': str(unknown),
                 'actual_total_usd': str(known) if not unknown else None,
                 'note': 'Development attempts only, including retained failed or interrupted claim; smoke excluded. Unknown reserve is not observed spend.'},
        'evaluation': evaluation,
        'sources': {'plan': {'file': spec['plan'], 'sha256': digest(plan_path)},
                    'original': original_binding, 'original_journal': journal_binding,
                    'interruption': interruption_binding,
                    'suffix': {'file': spec['output'], 'sha256': digest(suffix_path)},
                    'suffix_journal': {'file': str(journal_path.relative_to(root)), 'sha256': digest(journal_path)},
                    'budget': budget},
        'terminal': {k: terminal.get(k) for k in ('attempted_records', 'planned_records', 'completed', 'terminal_status')},
    }
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('condition', choices=tuple(SPECS))
    args = parser.parse_args()
    value = reconcile(args.condition)
    destination = ROOT / OUT / (args.condition + '.json')
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise ValueError('Immutable reconciliation report already exists')
    destination.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    print(destination)


if __name__ == '__main__':
    main()
