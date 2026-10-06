#!/usr/bin/env python3
"""Offline proposal and gated runner for Qwen3.6 ON remaining hosted phases.

Fresh1/P1 stays a descriptive interrupted composite. All requests in this
successor come from the original three frozen hosted plans.
"""
import argparse
from copy import deepcopy
from decimal import Decimal
import json
import os
from pathlib import Path

import openrouter_budget_v4 as budget
import paid_budget_partitions_v4 as partitions
import postapproval_authority_v3 as authority
import qwen36_on_hosted_authority_v2 as parent
import qwen36_on_p1_unsent_continuation_v1 as suffix

study = parent.study
ROOT = study.ROOT
BASE = parent.BASE / 'remaining-hosted-v1'
EXECUTION = BASE / 'execution-manifest.json'
BUDGET = BASE / 'budget.json'
PARTITION_ID = 'qwen36-on-remaining-hosted-v1'
CAP = Decimal('1.00')
SCHEMA = 'qwen36-on-remaining-hosted-v1'
STAGES = (('fresh1', 'P2'), ('fresh2', 'P1'), ('fresh2', 'P2'),
          ('fresh2', 'P0'), ('fresh3', 'P2'), ('fresh3', 'P0'),
          ('fresh3', 'P1'))
SOURCES = ('qwen36_on_remaining_hosted_v1.py',
           'qwen36_on_hosted_authority_v2.py',
           'qwen36_on_p1_unsent_continuation_v1.py',
           'qwen36_on_fresh_repeat_execution.py',
           'qwen36_on_fresh_repeat_study.py',
           'qwen27_fresh_repeat_execution.py',
           'openrouter_paid_benchmark.py', 'openrouter_benchmark.py',
           'paid_budget_partitions_v4.py', 'openrouter_budget_v4.py',
           'postapproval_authority_v3.py', 'prompt_admission.py')
PREDECESSOR = {
    'parent_p0_claim': parent.BASE / 'fresh1/P0/development.claim.json',
    'parent_p0_journal': parent.BASE / 'fresh1/P0/development.journal.jsonl',
    'parent_p0_attempts': parent.BASE / 'fresh1/P0/development.attempts.jsonl',
    'parent_p0_responses': parent.BASE / 'fresh1/P0/development.responses.jsonl',
    'parent_p1_claim': parent.BASE / 'fresh1/P1/development.claim.json',
    'parent_p1_journal': parent.BASE / 'fresh1/P1/development.journal.jsonl',
    'parent_p1_attempts': parent.BASE / 'fresh1/P1/development.attempts.jsonl',
    'parent_p1_responses': parent.BASE / 'fresh1/P1/development.responses.jsonl',
    'parent_child': parent.BASE / ('budget-' + parent.PARTITION_ID + '.jsonl'),
    'suffix_manifest': suffix.MANIFEST,
    'suffix_closure_review': suffix.BASE / 'closure.review.json',
    'suffix_claim': suffix.BASE / 'fresh1/P1/development.claim.json',
    'suffix_journal': suffix.BASE / 'fresh1/P1/development.journal.jsonl',
    'suffix_attempts': suffix.BASE / 'fresh1/P1/development.attempts.jsonl',
    'suffix_responses': suffix.BASE / 'fresh1/P1/development.responses.jsonl',
    'suffix_child': suffix.BASE / ('budget-' + suffix.PARTITION_ID + '.jsonl'),
    'suffix_reconciliation': suffix.BASE / 'reconciliation.json',
}


def rows(path):
    raw = Path(path).read_bytes()
    if raw and not raw.endswith(b'\n'):
        raise ValueError('Incomplete JSONL: ' + str(path))
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def binding(path):
    path = Path(path).resolve()
    path.relative_to(ROOT.resolve())
    return {'path': str(path.relative_to(ROOT.resolve())), 'sha256': study.sha(path)}


def bound(item):
    path = (ROOT / item['path']).resolve()
    path.relative_to(ROOT.resolve())
    if study.sha(path) != item['sha256']:
        raise ValueError('Bound predecessor/source changed: ' + item['path'])
    return path


def verify_predecessor():
    parent.verify()
    parent_plan = parent.verify_plan('fresh1', study.sha(parent.BASE / 'fresh1/manifest.json'))
    core = parent._private_runner()
    core.verify_phase_closure(parent_plan, 'P0', 'development')
    suffix.audit_parent()  # includes original P1 smoke and interrupted 49-attempt proof.
    suffix.finalized_parent()
    suffix_manifest_sha = study.sha(suffix.MANIFEST)
    suffix.verify(suffix_manifest_sha)
    review = json.loads((suffix.BASE / 'closure.review.json').read_text())
    expected_ids = [f'DEV-{i:03}' for i in range(50, 61)]
    if (review.get('schema') != 'qwen36-on-p1-unsent-closure-review-v1' or
            review.get('verdict') != 'CLOSED_11_VALID' or
            review.get('manifest_sha256') != suffix_manifest_sha or
            review.get('suffix_ids') != expected_ids or
            review.get('suffix_attempted') != 11 or review.get('suffix_valid') != 11 or
            review.get('parent_valid') != 48 or review.get('parent_unknown_attempted_id') != 'DEV-049' or
            review.get('composite_valid') != 59 or review.get('composite_denominator') != 60 or
            review.get('composite_unknown_ids') != ['DEV-049'] or
            review.get('clean_full_phase') is not False):
        raise ValueError('Interrupted P1 composite closure differs')
    for source in review['source_bindings'].values():
        bound(source)
    suffix_attempts = rows(PREDECESSOR['suffix_attempts'])
    suffix_journal = rows(PREDECESSOR['suffix_journal'])
    if ([r.get('id') for r in suffix_attempts] != expected_ids or
            any(r.get('status') != 'ok' or r.get('cost_unknown') is not False for r in suffix_attempts) or
            suffix_journal[-1].get('event') != 'phase_completed' or
            suffix_journal[-1].get('request_count') != 11 or
            suffix_journal[-1].get('attempt_ids') != [r['attempt_id'] for r in suffix_attempts] or
            sum((Decimal(r['observed_cost_usd']) for r in suffix_attempts), Decimal(0)) != Decimal('0.0134064')):
        raise ValueError('Completed P1 suffix evidence differs')
    child = budget.BudgetLedger(PREDECESSOR['suffix_child'], cap_limit=suffix.CAP)
    try:
        _, pending, blocked = child.state()
        if pending or blocked or not child.closed or child.accounted() != Decimal('0.0134064'):
            raise ValueError('P1 suffix child is not closed at known cost')
    finally:
        child.close()
    reconciliation = json.loads(PREDECESSOR['suffix_reconciliation'].read_text())
    if (reconciliation.get('event') != 'partition_reconciled' or
            reconciliation.get('partition_id') != suffix.PARTITION_ID or
            Decimal(reconciliation.get('known_actual_usd', '-1')) != Decimal('0.0134064') or
            Decimal(reconciliation.get('unknown_upper_bound_usd', '-1')) != 0 or
            reconciliation.get('child_sha256') != study.sha(PREDECESSOR['suffix_child'])):
        raise ValueError('P1 suffix reconciliation differs')
    master = budget.BudgetLedger(parent.MASTER)
    try:
        master.state()
        if master.partitions[suffix.PARTITION_ID]['active'] or not any(
                e == reconciliation for e in master.events if e.get('event') == 'partition_reconciled'
                and e.get('partition_id') == suffix.PARTITION_ID):
            raise ValueError('P1 suffix master reconciliation differs')
    finally:
        master.close()
    return {'parent_p0': 'closed_60_valid', 'parent_p1': 'interrupted_48_valid_1_unknown',
            'p1_suffix': 'closed_11_valid', 'p1_composite': 'descriptive_59_valid_1_unknown'}


def plan_path(repeat):
    if repeat not in study.ORDERS:
        raise ValueError('Unknown fresh pass')
    return BASE / parent.CONFIG / repeat / 'manifest.json'


def expected_plan(repeat):
    original_path = parent.BASE / repeat / 'manifest.json'
    original = deepcopy(parent.verify_plan(repeat, study.sha(original_path)))
    original.update(series_id=SCHEMA, execution_status='offline_proposal_unapproved',
        original_plan_sha256=study.sha(original_path),
        successor_scope='fresh1/P2 and all fresh2/fresh3 P0/P1/P2; original requests unchanged',
        predecessor_p1_status='descriptive_59_valid_1_unknown',
        successor_partition_id=PARTITION_ID, successor_child_cap_usd=str(CAP),
        full_series_completion_guaranteed=False,
        dispatch_gate='Sequential phase root review; three valid inspected smoke outputs before each development; full reserve before each call; stop on invalid or insufficient capacity')
    return original


def expected_execution():
    predecessor = verify_predecessor()
    plans = {repeat: study.sha(plan_path(repeat)) for repeat in study.ORDERS}
    for repeat, digest in plans.items():
        if json.loads(plan_path(repeat).read_text()) != expected_plan(repeat):
            raise ValueError('Successor plan or original request bytes changed')
    sources = {name: binding(path) for name, path in PREDECESSOR.items()}
    sources.update({'parent_execution': binding(parent.EXECUTION),
                    'parent_public_route': binding(parent.ROUTE)})
    sources.update({'original_plan_' + repeat: binding(parent.BASE / repeat / 'manifest.json')
                    for repeat in study.ORDERS})
    sources.update({'code_' + name: binding(ROOT / 'scripts' / name) for name in SOURCES})
    return {'schema': SCHEMA + '-execution', 'status': 'offline_proposal_unapproved',
            'configuration_id': parent.CONFIG, 'original_configuration_id': study.CONFIG,
            'method': 'separate_same_route_sequential_remaining_phases',
            'clean_matched_three_eligible': False, 'predecessor': predecessor,
            'plans_sha256': plans, 'schedule': [{'fresh_pass': repeat, 'condition': condition,
                'smoke_ids': [r['record_id'] for r in expected_plan(repeat)['conditions'][condition]['smoke']],
                'development_ids': [r['record_id'] for r in expected_plan(repeat)['conditions'][condition]['development']]}
                for repeat, condition in STAGES],
            'partition_id': PARTITION_ID, 'child_cap_usd': str(CAP),
            'funding_pool': 'openrouter_additional',
            'per_request_reserve_usd': str(parent.RESERVE),
            'full_reserve_total_usd': str(parent.RESERVE * Decimal(len(STAGES) * 63)),
            'capacity_policy': 'Before each request, accounted plus full reserve must fit the child cap; otherwise stop without sending',
            'invalid_output_policy': 'Stop and preserve; no automatic retry',
            'reference_labels_read': False, 'inference_authorized': False,
            'test_sha256': study.sha(ROOT / 'tests/test_qwen36_on_remaining_hosted_v1.py'),
            'source_bindings': sources}


def freeze():
    verify_predecessor()
    if EXECUTION.exists() or any(plan_path(r).exists() for r in study.ORDERS):
        raise FileExistsError('Successor proposal already exists')
    for repeat in study.ORDERS:
        path = plan_path(repeat)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x') as out:
            json.dump(expected_plan(repeat), out, indent=2)
            out.write('\n'); out.flush(); os.fsync(out.fileno())
    with EXECUTION.open('x') as out:
        json.dump(expected_execution(), out, indent=2)
        out.write('\n'); out.flush(); os.fsync(out.fileno())
    return study.sha(EXECUTION)


def verify(execution_sha=None):
    if execution_sha and study.sha(EXECUTION) != execution_sha:
        raise ValueError('Successor execution SHA differs')
    saved = json.loads(EXECUTION.read_text())
    for source in saved['source_bindings'].values():
        bound(source)
    if saved != expected_execution():
        raise ValueError('Successor execution or predecessor changed')
    return saved


def ordered_prior_stages(core, repeat, condition, phase):
    stage = (repeat, condition)
    if stage not in STAGES or phase not in ('smoke', 'development'):
        raise ValueError('Stage outside seven-phase successor')
    verify()
    for prior_repeat, prior_condition in STAGES[:STAGES.index(stage)]:
        prior_plan = core.study.verify(parent.CONFIG, prior_repeat, study.sha(plan_path(prior_repeat)))
        core.verify_phase_closure(prior_plan, prior_condition, 'development')
    if phase == 'development':
        plan = core.study.verify(parent.CONFIG, repeat, study.sha(plan_path(repeat)))
        checked = core.verify_phase_closure(plan, condition, 'smoke')
        receipt = BASE / parent.CONFIG / repeat / condition / 'smoke-inspection.json'
        inspected = json.loads(receipt.read_text())
        expected = {'schema': 'openrouter-repeat-smoke-inspection-v1',
                    'configuration_id': parent.CONFIG, 'fresh_pass': repeat,
                    'condition': condition, 'decision': 'accepted_unchanged',
                    'manifest_sha256': checked['manifest_sha256'],
                    'journal_sha256': checked['journal_sha256'],
                    'attempts_sha256': checked['attempts_sha256'],
                    'responses_sha256': checked['responses_sha256']}
        if (not isinstance(inspected.get('note'), str) or not inspected['note'].strip() or
                {k: inspected.get(k) for k in expected} != expected or
                set(inspected) != set(expected) | {'note'}):
            raise ValueError('Inspected successor smoke differs')


def budget_binding():
    data = json.loads(BUDGET.read_text())
    entries = data.get('partitions')
    if data.get('version') != 'paid-partitions-v1' or data.get('master_ledger') != str(parent.MASTER) or not isinstance(entries, list) or len(entries) != 1:
        raise ValueError('Separate successor child manifest differs')
    entry = entries[0]
    child = BASE / (BUDGET.stem + '-' + PARTITION_ID + '.jsonl')
    if (entry.get('id') != PARTITION_ID or entry.get('cap_usd') != str(CAP) or
            entry.get('model') != study.MODEL or entry.get('provider') != study.PROVIDER or
            entry.get('reasoning') != 'on' or
            Path(entry.get('child_ledger', '')).resolve() != child.resolve()):
        raise ValueError('Separate successor child route or cap differs')
    return entry


def hold_source(execution_sha):
    verify(execution_sha)
    budget_binding()
    return study.digest(json.dumps({'execution_manifest_sha256': execution_sha,
        'budget_manifest_sha256': study.sha(BUDGET), 'partition_id': PARTITION_ID,
        'cap_usd': str(CAP), 'configuration_id': parent.CONFIG,
        'predecessor_review_sha256': study.sha(PREDECESSOR['suffix_closure_review']),
        'model': study.MODEL, 'provider': study.PROVIDER, 'reasoning': 'on'}, sort_keys=True))


def review_template(repeat, condition, phase, execution_sha):
    verify(execution_sha)
    if (repeat, condition) not in STAGES or phase not in ('smoke', 'development'):
        raise ValueError('Stage outside successor')
    budget_binding()
    with authority.old._locked(parent.AUTHORITY) as handle:
        snapshot, holds = authority._scan(handle.read())
    hold = holds.get(PARTITION_ID)
    if (hold is None or hold.get('funding_pool') != 'openrouter_additional' or
            hold.get('usd') != str(CAP) or hold.get('budget_manifest_sha256') != study.sha(BUDGET) or
            hold.get('partition_id') != PARTITION_ID or
            hold.get('source_sha256') != hold_source(execution_sha)):
        raise ValueError('Separate successor OpenRouter authority hold absent or mismatched')
    return {'schema': SCHEMA + '-root-review', 'approved': False,
            'independent_review': False, 'authorized_by_root': False,
            'reviewer': None, 'configuration_id': parent.CONFIG,
            'stage': f'{repeat}/{condition}/{phase}',
            'controller_sha256': study.sha(__file__),
            'execution_manifest_sha256': execution_sha,
            'plan_sha256': study.sha(plan_path(repeat)),
            'master_ledger': str(parent.MASTER),
            'budget_manifest_path': str(BUDGET.resolve()),
            'budget_manifest_sha256': study.sha(BUDGET),
            'partition_id': PARTITION_ID, 'partition_cap_usd': str(CAP),
            'funding_pool': 'openrouter_additional',
            'predecessor_review_sha256': study.sha(PREDECESSOR['suffix_closure_review']),
            'authority_head_sha256': snapshot.head_sha256,
            'authority_hold_source_sha256': hold['source_sha256']}


def private_runner():
    core = parent._private_runner()
    class BasePath:
        def __truediv__(self, config):
            if config != parent.CONFIG:
                raise ValueError('Unknown configuration')
            return BASE / config
    class Study(parent.frozen._Study):
        BASE = BasePath()
        CONFIGS = {parent.CONFIG: {'effort': 'on', 'historical_continue_on_invalid': False,
                                   'proposed_child_budget': CAP}}
        @staticmethod
        def verify(config, repeat, digest):
            if config != parent.CONFIG or repeat not in study.ORDERS or digest != study.sha(plan_path(repeat)):
                raise ValueError('Unknown successor plan')
            verify()
            return json.loads(plan_path(repeat).read_text())
    core.study = Study
    core.live_controls = parent.live_controls
    core.require_order = lambda plan, condition, phase: ordered_prior_stages(core, plan['fresh_pass'], condition, phase)
    def reviewed(path, config, repeat, condition, phase, plan_sha):
        expected_path = BASE / config / repeat / condition / (phase + '.root-review.json')
        if Path(path).resolve() != expected_path.resolve():
            raise ValueError('Exact successor stage review path differs')
        template = review_template(repeat, condition, phase, study.sha(EXECUTION))
        expected = {**template, 'approved': True, 'independent_review': True,
                    'authorized_by_root': True, 'reviewer': 'root'}
        if config != parent.CONFIG or plan_sha != template['plan_sha256'] or json.loads(expected_path.read_text()) != expected:
            raise ValueError('Independent root stage receipt differs')
        return expected, BUDGET
    def gated(receipt, budget_path, config):
        if config != parent.CONFIG or Path(budget_path).resolve() != BUDGET.resolve() or receipt['authority_head_sha256'] != authority.read_authority(parent.AUTHORITY).head_sha256:
            raise ValueError('Authority or child binding changed')
        ledger = partitions.open_partition(parent.MASTER, BUDGET, PARTITION_ID,
                                            study.MODEL, study.PROVIDER, 'on')
        try:
            _, pending, blocked = ledger.state()
            if ledger.cap != CAP or ledger.master_cap != Decimal('22.38') or pending or blocked or ledger.closed or ledger.accounted() + parent.RESERVE > CAP:
                raise ValueError('Separate successor child unavailable before key read')
            return ledger
        except BaseException:
            ledger.close(); raise
    core.review_receipt = reviewed
    core.budget_gate = gated
    return core


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('audit-predecessor', 'freeze', 'verify', 'hold-source',
                                      'review-template', 'live-check', 'smoke', 'inspect', 'development'))
    p.add_argument('--execution-sha256')
    p.add_argument('--fresh-pass', choices=tuple(study.ORDERS), default='fresh1')
    p.add_argument('--condition', choices=study.CONDITIONS, default='P2')
    p.add_argument('--phase', choices=('smoke', 'development'), default='smoke')
    p.add_argument('--note')
    p.add_argument('--env-file')
    args = p.parse_args()
    if args.action == 'audit-predecessor':
        print(json.dumps(verify_predecessor())); return
    if args.action == 'freeze': print(freeze()); return
    if not args.execution_sha256: p.error('Exact --execution-sha256 required')
    verify(args.execution_sha256)
    if args.action == 'verify': print('verified'); return
    if args.action == 'hold-source': print(hold_source(args.execution_sha256)); return
    if args.action == 'review-template':
        print(json.dumps(review_template(args.fresh_pass, args.condition, args.phase,
                                         args.execution_sha256), indent=2)); return
    plan = json.loads(plan_path(args.fresh_pass).read_text())
    if args.action == 'live-check':
        if (args.fresh_pass, args.condition) not in STAGES: raise ValueError('Stage outside successor')
        parent.live_controls(plan, args.condition)
        print('live route passed; no inference'); return
    core = private_runner()
    digest = study.sha(plan_path(args.fresh_pass))
    if args.action == 'inspect':
        if not args.note: p.error('inspect requires --note')
        print(core.inspect(parent.CONFIG, args.fresh_pass, args.condition, digest, args.note)); return
    if args.action != args.phase:
        p.error('action/--phase mismatch')
    review = BASE / parent.CONFIG / args.fresh_pass / args.condition / (args.action + '.root-review.json')
    print(core.execute(parent.CONFIG, args.fresh_pass, args.condition, args.action,
                       digest, review, args.env_file))


if __name__ == '__main__': main()
