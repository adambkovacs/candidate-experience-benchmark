#!/usr/bin/env python3
"""Audit and report closed DeepSeek high price-v1 phases without old-pass credit."""
import argparse
from collections import Counter
from copy import deepcopy
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
from types import FunctionType

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


def portable_plan(repeat, expected_sha):
    """Rebuild the frozen request plan from archived sources, without a live ledger."""
    if repeat not in adapter.study.ORDERS:
        raise ValueError('Unknown revised-price fresh pass')
    proposal = json.loads(adapter.proposal.MANIFEST.read_text())
    execution = json.loads(adapter.MANIFEST.read_text())
    for sources in (proposal['source_bindings'], execution['source_bindings']):
        for name, item in sources.items():
            digest = item if isinstance(item, str) else item['sha256']
            if not isinstance(item, str) and item.get('path') != name:
                raise ValueError('Portable source path differs: ' + name)
            path = (ROOT / name).resolve()
            path.relative_to(ROOT.resolve())
            if sha(path) != digest:
                raise ValueError('Portable frozen source differs: ' + name)
    if (proposal.get('schema') != adapter.proposal.SCHEMA + '-execution-plan' or
            proposal.get('configuration_id') != CONFIG or
            execution.get('schema') != adapter.SCHEMA + '-manifest' or
            execution.get('configuration_id') != CONFIG or
            execution.get('proposal_sha256') != sha(adapter.proposal.MANIFEST) or
            execution.get('old_child_reconciliation_sha256') != sha(adapter.OLD_RECONCILIATION)):
        raise ValueError('Portable proposal or execution manifest differs')
    old_receipt = json.loads(adapter.OLD_RECONCILIATION.read_text())
    if (old_receipt.get('event') != 'partition_reconciled' or
            old_receipt.get('partition_id') != adapter.prior.PARTITION_ID or
            old_receipt.get('child_sha256') != sha(adapter.OLD_LEDGER) or
            Decimal(old_receipt.get('unknown_upper_bound_usd', '-1')) != 0):
        raise ValueError('Archived old child reconciliation differs')
    path = BASE / repeat / 'manifest.json'
    if sha(path) != expected_sha or execution['plans_sha256'].get(repeat) != expected_sha:
        raise ValueError('Portable revised-price plan hash differs')
    plan = json.loads(path.read_text())
    old_path = adapter.prior.BASE / repeat / 'manifest.json'
    old = json.loads(old_path.read_text())
    selected = [condition for name, condition in adapter.proposal.PHASES if name == repeat]
    expected = deepcopy(old)
    expected['conditions'] = {condition: expected['conditions'][condition]
                              for condition in selected}
    expected['condition_order'] = selected
    for condition in selected:
        for phase in ('smoke', 'development'):
            rows = proposal['requests_by_stage'][f'{repeat}/{condition}/{phase}']
            old_rows = expected['conditions'][condition][phase]
            if (len(rows) != len(old_rows) or
                    [row['id'] for row in rows] != [row['record_id'] for row in old_rows]):
                raise ValueError('Portable request order differs')
            for request, saved in zip(old_rows, rows):
                if (saved['original_request_sha256'] != request['request_sha256'] or
                        saved['input_sha256'] != request['input_sha256'] or
                        saved['instruction_sha256'] != request['instruction_sha256'] or
                        adapter.study.digest(json.dumps(saved['payload'], sort_keys=True)) !=
                        saved['request_sha256']):
                    raise ValueError('Portable frozen request identity differs')
                only_price = deepcopy(request['payload'])
                only_price['provider']['max_price'] = saved['payload']['provider']['max_price']
                if only_price != saved['payload']:
                    raise ValueError('Portable request changed beyond price ceilings')
                request.update(payload=saved['payload'], request_sha256=saved['request_sha256'])
    expected.update(schema=adapter.SCHEMA + '-plan', series_id=adapter.proposal.SCHEMA,
        configuration_id=CONFIG, original_configuration_id=adapter.prior.CONFIG,
        source_proposal_sha256=sha(adapter.proposal.MANIFEST),
        public_route_sha256=sha(adapter.proposal.ROUTE),
        partition_id=adapter.proposal.PARTITION_ID,
        proposed_child_budget_usd=str(adapter.proposal.CHILD_CAP),
        input_price_ceiling_usd_per_million=str(adapter.proposal.INPUT_CEILING),
        output_price_ceiling_usd_per_million=str(adapter.proposal.OUTPUT_CEILING),
        cache_read_price_ceiling_usd_per_million=str(adapter.proposal.CACHE_CEILING),
        per_request_reserve_usd=str(adapter.proposal.RESERVE),
        dispatch_gate='Separate adapter review, exact stage receipt, $1 OpenRouter-only hold, '
            'closed old child, live route and reserve, sequential capacity, inspected smoke')
    if plan != expected:
        raise ValueError('Portable revised-price plan differs from frozen requests')
    return plan


def portable_phase_verifier():
    core = adapter.repaired_core()
    class PortableStudy(core.study):
        @staticmethod
        def verify(*args):
            if len(args) == 2:
                repeat, digest = args
            elif len(args) == 3 and args[0] == CONFIG:
                _, repeat, digest = args
            else:
                raise ValueError('Portable verifier configuration differs')
            return portable_plan(repeat, digest)
    core.study = PortableStudy
    outer = dict(core.verify_phase_closure.__globals__, study=PortableStudy)
    strict = outer['_strict_closure']
    outer['_strict_closure'] = FunctionType(strict.__code__,
        dict(strict.__globals__, study=PortableStudy))
    core.verify_phase_closure = FunctionType(core.verify_phase_closure.__code__, outer)
    return core


def evidence(repeat, condition, snapshot_bytes):
    folder = folder_for(repeat, condition)
    plan = portable_plan(repeat, sha(BASE / repeat / 'manifest.json'))
    admission_reviews(folder, repeat, condition, sha(BASE / repeat / 'manifest.json'))
    core = portable_phase_verifier()
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


def verified_closure_in_root(root, repeat, condition, prior_attempts):
    """Verify a copied tree by byte identity with the fully audited closure."""
    folder = folder_for(repeat, condition)
    copied_receipt = root / relative(folder / 'closure.review.json')
    original_receipt = folder / 'closure.review.json'
    if not copied_receipt.is_file() or not original_receipt.is_file() or \
            sha(copied_receipt) != sha(original_receipt):
        raise ValueError('Copied price-v1 closure receipt differs')
    receipt = json.loads(copied_receipt.read_text())
    sources = required_sources(repeat, condition)
    if set(receipt.get('source_bindings', ())) != set(sources):
        raise ValueError('Copied price-v1 closure source set differs')
    for name in sources:
        copied = root / name
        if not copied.is_file() or sha(copied) != receipt['source_bindings'][name]:
            raise ValueError('Copied price-v1 closure source differs: ' + name)
    return verified_closure(repeat, condition, prior_attempts)


def reporter_bindings(root):
    items = []
    for path in (ROOT / 'scripts/build_deepseek_high_remaining7_price_findings.py',
                 ROOT / 'tests/test_build_deepseek_high_remaining7_price_findings.py'):
        name = relative(path)
        digest = sha(path)
        if sha(root / name) != digest:
            raise ValueError('Copied price-v1 reporter source differs: ' + name)
        items.append({'path': name, 'sha256': digest})
    return items


def build(root=ROOT):
    root = Path(root).resolve()
    report = previous.build(root)
    if any(item.get('configuration') == CONFIG for item in report['series']):
        raise ValueError('Price-control configuration duplicates prior series')
    phases = {}
    bindings = []
    prior_attempts = []
    found_gap = False
    for repeat, condition in adapter.proposal.PHASES:
        folder = root / relative(folder_for(repeat, condition))
        if not (folder / 'closure.review.json').exists():
            found_gap = True
            continue
        if found_gap:
            raise ValueError('Price-v1 closure skips an earlier phase')
        result = (verified_closure(repeat, condition, prior_attempts)
                  if root == ROOT.resolve() else
                  verified_closure_in_root(root, repeat, condition, prior_attempts))
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
        bindings.append({'path': str(receipt.relative_to(root)), 'sha256': sha(receipt)})
        for name, digest in json.loads(receipt.read_text())['source_bindings'].items():
            item = {'path': name, 'sha256': digest}
            if item not in bindings:
                bindings.append(item)
    if not prior_attempts:
        return report
    bindings.extend(reporter_bindings(root))
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
