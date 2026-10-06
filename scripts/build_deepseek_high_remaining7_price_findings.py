#!/usr/bin/env python3
"""Audit and report closed DeepSeek high price-v1 phases without old-pass credit."""
import argparse
from collections import Counter
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path

import build_deepseek_high_authority_v3_findings as previous
import deepseek_high_remaining7_execution_v1 as adapter

ROOT = adapter.study.ROOT
BASE = adapter.BASE
CONFIG = adapter.proposal.CONFIG
IDS = [f'DEV-{n:03}' for n in range(1, 61)]
LABELS = ROOT / 'data/pilot/proposed_labels.jsonl'
SCHEMA = 'deepseek-high-remaining7-price-v1-phase-closure-v1'
OUTPUT = ROOT / 'public-site/additional-hosted-fresh-repeats.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relative(path):
    path = Path(path).resolve()
    path.relative_to(ROOT.resolve())
    return str(path.relative_to(ROOT.resolve()))


def rows(path):
    raw = Path(path).read_bytes()
    if not raw or not raw.endswith(b'\n'):
        raise ValueError('Missing or incomplete evidence: ' + str(path))
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def folder_for(repeat, condition):
    if (repeat, condition) not in adapter.proposal.PHASES:
        raise ValueError('Stage outside remaining price-v1 plan')
    return BASE / repeat / condition


def required_sources(repeat, condition):
    folder = folder_for(repeat, condition)
    plan = BASE / repeat / 'manifest.json'
    paths = (
        adapter.proposal.MANIFEST, adapter.proposal.ROUTE,
        adapter.MANIFEST, adapter.REVIEW, plan, adapter.BUDGET,
        ROOT / 'scripts/deepseek_high_remaining7_price_v1.py',
        ROOT / 'scripts/deepseek_high_remaining7_execution_v1.py',
        ROOT / 'scripts/deepseek_high_fresh_repeat_execution.py',
        ROOT / 'scripts/deepseek_high_v3_closure_bridge.py',
        LABELS,
        *(folder / (phase + suffix) for phase in ('smoke', 'development')
          for suffix in ('.claim.json', '.root-review.json', '.journal.jsonl',
                         '.attempts.jsonl', '.responses.jsonl')),
        folder / 'smoke-inspection.json',
        folder / 'closure-ledger-snapshot.jsonl',
    )
    return {relative(path): path for path in paths}


def ledger_evidence(raw, attempts):
    if not raw.endswith(b'\n'):
        raise ValueError('Incomplete child-ledger snapshot')
    events = [json.loads(line) for line in raw.splitlines()]
    if not events or events[0] != {'event': 'budget', 'cap_usd': str(adapter.proposal.CHILD_CAP)} or \
            len(events) != 1 + 2 * len(attempts):
        raise ValueError('Child-ledger prefix or event count differs')
    seen = set()
    cost = Decimal(0)
    for n, attempt in enumerate(attempts):
        attempt_id = attempt.get('attempt_id')
        if not isinstance(attempt_id, str) or not attempt_id or attempt_id in seen:
            raise ValueError('Duplicate or missing attempt identity in child ledger')
        seen.add(attempt_id)
        reserve, settle = events[1 + 2*n:3 + 2*n]
        if (reserve != {'event': 'reserve', 'attempt_id': attempt_id,
                        'record_id': attempt.get('id'),
                        'usd': attempt.get('reserved_cost_usd')} or
                settle != {'event': 'settle', 'attempt_id': attempt_id,
                           'usd': attempt.get('observed_cost_usd')} or
                attempt.get('billing_ok') is not True or
                attempt.get('cost_unknown') is not False):
            raise ValueError('Child-ledger reserve or settlement differs')
        cost += Decimal(attempt['observed_cost_usd'])
    return len(attempts), cost


def inspected_smoke(folder, bindings):
    saved = json.loads((folder / 'smoke-inspection.json').read_text())
    expected = {'manifest_sha256': bindings['manifest_sha256'],
                'journal_sha256': bindings['journal_sha256'],
                'attempts_sha256': bindings['attempts_sha256'],
                'responses_sha256': bindings['responses_sha256']}
    if saved.get('decision') != 'accepted_unchanged' or \
            saved.get('configuration_id') != CONFIG or \
            any(saved.get(key) != value for key, value in expected.items()):
        raise ValueError('Smoke inspection is absent or source binding changed')


def admission_reviews(folder, repeat, condition, plan_sha):
    adapter.require_review()
    budget_sha = sha(adapter.BUDGET)
    for phase in ('smoke', 'development'):
        saved = json.loads((folder / (phase + '.root-review.json')).read_text())
        expected = {
            'schema': adapter.SCHEMA + '-stage-root-review',
            'approved': True, 'independent_review': True,
            'authorized_by_root': True, 'reviewer': 'root',
            'configuration_id': CONFIG,
            'stage': f'{repeat}/{condition}/{phase}',
            'controller_sha256': sha(ROOT / 'scripts/deepseek_high_remaining7_execution_v1.py'),
            'execution_manifest_sha256': sha(adapter.MANIFEST),
            'plan_sha256': plan_sha,
            'proposal_sha256': sha(adapter.proposal.MANIFEST),
            'budget_manifest_sha256': budget_sha,
            'partition_id': adapter.proposal.PARTITION_ID,
            'partition_cap_usd': str(adapter.proposal.CHILD_CAP),
            'funding_pool': 'openrouter_additional',
        }
        if any(saved.get(key) != value for key, value in expected.items()):
            raise ValueError('Independent stage admission review differs: ' + phase)


def evidence(repeat, condition, snapshot_bytes):
    folder = folder_for(repeat, condition)
    plan = adapter.verify_plan(repeat, sha(BASE / repeat / 'manifest.json'))
    admission_reviews(folder, repeat, condition, sha(BASE / repeat / 'manifest.json'))
    core = adapter.repaired_core()
    smoke_bindings = core.verify_phase_closure(plan, condition, 'smoke')
    inspected_smoke(folder, smoke_bindings)
    core.verify_phase_closure(plan, condition, 'development')
    smoke = rows(folder / 'smoke.attempts.jsonl')
    development = rows(folder / 'development.attempts.jsonl')
    if ([row.get('id') for row in smoke] != IDS[:3] or
            [row.get('id') for row in development] != IDS or
            any(row.get('status') != 'ok' for row in smoke) or
            any(row.get('status') not in ('ok', 'invalid_output') for row in development)):
        raise ValueError('Phase contains missing, failed or reordered attempts')
    labels = {row['id']: row['proposed_labels'] for row in rows(LABELS)}
    if set(labels) != set(IDS):
        raise ValueError('Reference membership differs')
    score = previous.existing.existing.score(development, labels, IDS)
    if score['denominator'] != 60:
        raise ValueError('Wrong fixed score denominator')
    statuses = dict(Counter(row['status'] for row in development))
    invalid = [row['id'] for row in development if row['status'] == 'invalid_output']
    known = sum((Decimal(row['observed_cost_usd']) for row in development), Decimal(0))
    smoke_known = sum((Decimal(row['observed_cost_usd']) for row in smoke), Decimal(0))
    return {'plan': plan, 'smoke': smoke, 'development': development, 'score': score,
            'status_counts': statuses, 'intrinsic_invalid_ids': invalid,
            'known_development_cost_usd': str(known),
            'smoke_known_cost_usd': str(smoke_known)}


def closure_data(repeat, condition, snapshot_bytes, prior_attempts):
    result = evidence(repeat, condition, snapshot_bytes)
    attempts = [*prior_attempts, *result['smoke'], *result['development']]
    settled, cumulative = ledger_evidence(snapshot_bytes, attempts)
    folder = folder_for(repeat, condition)
    snapshot_path = folder / 'closure-ledger-snapshot.jsonl'
    sources = required_sources(repeat, condition)
    bindings = {name: (hashlib.sha256(snapshot_bytes).hexdigest()
                       if path == snapshot_path else sha(path))
                for name, path in sources.items()}
    return {'schema': SCHEMA, 'verdict': 'APPROVE',
        'independent_review': True, 'reviewer': 'qwen_recovery',
        'configuration_id': CONFIG,
        'original_configuration_id': adapter.prior.CONFIG,
        'stage': f'{repeat}/{condition}/development',
        'model': adapter.study.MODEL, 'provider': adapter.study.PROVIDER,
        'price_control_configuration': True,
        'record_count': 60,
        'valid_count': result['score']['valid'],
        'status_counts': result['status_counts'],
        'intrinsic_invalid_ids': result['intrinsic_invalid_ids'],
        'all_four_correct_fixed_denominator': result['score']['allFour'],
        'field_correct_against_provisional_references': result['score']['fields'],
        'reference_status': 'provisional_v0.2_not_independent_accuracy',
        'known_development_cost_usd': result['known_development_cost_usd'],
        'smoke_known_cost_usd': result['smoke_known_cost_usd'],
        'unknown_cost_count': 0,
        'child_ledger_at_review': {
            'snapshot_path': relative(snapshot_path),
            'sha256': hashlib.sha256(snapshot_bytes).hexdigest(),
            'settled_attempt_count': settled,
            'pending_count': 0,
            'accounted_usd': str(cumulative)},
        'source_bindings': bindings}


def close_phase(repeat, condition):
    """Create immutable review artifacts only after the terminal stage is verified."""
    folder = folder_for(repeat, condition)
    receipt_path = folder / 'closure.review.json'
    snapshot_path = folder / 'closure-ledger-snapshot.jsonl'
    if receipt_path.exists() or snapshot_path.exists():
        raise FileExistsError('Closure already claimed')
    index = adapter.proposal.PHASES.index((repeat, condition))
    prior_attempts = []
    for earlier_repeat, earlier_condition in adapter.proposal.PHASES[:index]:
        prior = verified_closure(earlier_repeat, earlier_condition, prior_attempts)
        prior_attempts.extend(prior['smoke'] + prior['development'])
    with adapter.CHILD_LEDGER.open('rb') as handle:
        fcntl.flock(handle, fcntl.LOCK_SH)
        snapshot = handle.read()
        fcntl.flock(handle, fcntl.LOCK_UN)
    # Verify the terminal phase and exact cumulative ledger before writing either file.
    result = evidence(repeat, condition, snapshot)
    ledger_evidence(snapshot, prior_attempts + result['smoke'] + result['development'])
    value = closure_data(repeat, condition, snapshot, prior_attempts)
    with snapshot_path.open('xb') as handle:
        handle.write(snapshot); handle.flush(); os.fsync(handle.fileno())
    with receipt_path.open('x') as handle:
        json.dump(value, handle, indent=2)
        handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
    verified_closure(repeat, condition, prior_attempts)
    return sha(receipt_path)


def verified_closure(repeat, condition, prior_attempts):
    folder = folder_for(repeat, condition)
    receipt_path = folder / 'closure.review.json'
    if not receipt_path.is_file():
        raise ValueError('Completed phase lacks independent closure receipt')
    actual = json.loads(receipt_path.read_text())
    if set(actual.get('source_bindings', ())) != set(required_sources(repeat, condition)):
        raise ValueError('Closure source set differs')
    for name, path in required_sources(repeat, condition).items():
        if sha(path) != actual['source_bindings'][name]:
            raise ValueError('Closure source binding differs: ' + name)
    snapshot = (folder / 'closure-ledger-snapshot.jsonl').read_bytes()
    expected = closure_data(repeat, condition, snapshot, prior_attempts)
    if actual != expected:
        raise ValueError('Closure receipt differs from frozen evidence')
    return evidence(repeat, condition, snapshot)


def build():
    report = previous.build(ROOT)
    if any(item.get('configuration') == CONFIG for item in report['series']):
        raise ValueError('Price-control configuration duplicates prior series')
    phases = {}
    bindings = []
    prior_attempts = []
    found_gap = False
    for repeat, condition in adapter.proposal.PHASES:
        folder = folder_for(repeat, condition)
        if not (folder / 'closure.review.json').exists():
            found_gap = True
            continue
        if found_gap:
            raise ValueError('Price-v1 closure skips an earlier phase')
        result = verified_closure(repeat, condition, prior_attempts)
        prior_attempts.extend(result['smoke'] + result['development'])
        score = result['score']
        development = result['development']
        phase = {'status': 'completed_with_intrinsic_invalid'
                 if result['intrinsic_invalid_ids'] else 'completed',
                 'score': score,
                 'usage': {'requestCount': 60, 'startedRequestCount': 60,
                           'tokens': {key: sum(row['usage'][key] for row in development)
                                      for key in ('prompt_tokens', 'completion_tokens')},
                           'knownCostUsd': result['known_development_cost_usd'],
                           'actualCostUsd': result['known_development_cost_usd'],
                           'unknownCostCount': 0, 'requestSecondsTotal': None}}
        phases.setdefault(repeat, {})[condition] = phase
        receipt = folder / 'closure.review.json'
        bindings.append({'path': relative(receipt), 'sha256': sha(receipt)})
        for name, digest in json.loads(receipt.read_text())['source_bindings'].items():
            item = {'path': name, 'sha256': digest}
            if item not in bindings:
                bindings.append(item)
    if not prior_attempts:
        return report
    for path in (ROOT / 'scripts/build_deepseek_high_remaining7_price_findings.py',
                 ROOT / 'tests/test_build_deepseek_high_remaining7_price_findings.py'):
        bindings.append({'path': relative(path), 'sha256': sha(path)})
    complete = len(prior_attempts) // 63
    series = {'schema': 'additional-hosted-fresh-repeat-findings-v1',
        'configuration': CONFIG,
        'originalConfiguration': adapter.prior.CONFIG,
        'seriesId': CONFIG + '-fresh-repeat',
        'displayName': 'DeepSeek V4.1 Flash · OpenInference fp4 · high · revised price controls',
        'method': 'separate-price-control-continuation',
        'model': adapter.study.MODEL, 'effort': adapter.study.EFFORT,
        'provider': adapter.study.PROVIDER,
        'denominator': 60, 'plannedConditions': len(adapter.proposal.PHASES),
        'completedConditions': complete,
        'cleanMatchedThreeEligible': False,
        'cleanCompletedConditions': sum(cell['status'] == 'completed'
            for conditions in phases.values() for cell in conditions.values()),
        'conditionOrder': ['P0', 'P1', 'P2'],
        'passOrder': ['fresh1', 'fresh2', 'fresh3'],
        'passes': phases,
        'missingPasses': [{'pass': repeat, 'condition': condition,
                           'status': 'not_published'}
                          for repeat, condition in adapter.proposal.PHASES
                          if condition not in phases.get(repeat, {})],
        'threePassSummary': {}, 'pairwiseFlips': [],
        'changesAcrossThreePasses': {}, 'withinPassPromptDeltas': [],
        'pairedDeltaSpread': {},
        'historicalPassUsed': False,
        'sourceBindings': bindings,
        'limitations': ['This price-control configuration begins with fresh1/P2; old current-price P0/P1 remain a separate series.',
                        'The same 60 synthetic development reviews recur in each pass.',
                        'Provisional v0.2 references are not independent accuracy evidence.',
                        'Only independently closed phases with immutable child-ledger snapshots appear.']}
    report['series'].append(series)
    report['availableConfigurations'].append(CONFIG)
    for item in bindings:
        if item not in report['sourceBindings']:
            report['sourceBindings'].append(item)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('build', 'check', 'close-phase'))
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--fresh-pass', choices=tuple(adapter.study.ORDERS))
    parser.add_argument('--condition', choices=adapter.study.CONDITIONS)
    args = parser.parse_args()
    if args.action == 'close-phase':
        if not args.fresh_pass or not args.condition:
            parser.error('close-phase requires --fresh-pass and --condition')
        print(close_phase(args.fresh_pass, args.condition)); return
    value = json.dumps(build(), indent=2, ensure_ascii=False) + '\n'
    if args.action == 'check':
        if not args.output.exists() or args.output.read_text() != value:
            raise ValueError('Stale DeepSeek high price-v1 hosted report')
    else:
        args.output.write_text(value)
    print('verified' if args.action == 'check' else 'written')


if __name__ == '__main__':
    main()
