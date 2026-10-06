#!/usr/bin/env python3
"""Reviewed-entrypoint candidate for the exact unsent DeepSeek low successor."""
import argparse
from copy import deepcopy
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile

import deepseek_low_remaining6_successor_v1 as successor
import deepseek_low_remaining6_execution_v1 as prior
import paid_budget_partitions_v4 as partitions
import postapproval_authority_v3 as authority

ROOT = prior.ROOT
SCHEMA = 'deepseek-low-remaining6-successor-execution-v1'
BASE = successor.BASE / 'execution-adapter-v1'
MANIFEST = BASE / 'manifest.json'
REVIEW = BASE / 'root-review.json'
LOCK = successor.BASE / '.execution-adapter-v1.lock'
BUDGET = successor.BASE / 'budget.json'
PARTITION_ID = 'deepseek-low-remaining6-successor-v1'
CHILD_CAP = Decimal('0.35')
CHILD_LEDGER = successor.BASE / ('budget-' + PARTITION_ID + '.jsonl')
MASTER = prior.MASTER
AUTHORITY = prior.AUTHORITY
PHASES = prior.PHASES
PASSES = prior.PASSES


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def binding(path):
    path = Path(path).resolve()
    return {'path': str(path.relative_to(ROOT.resolve())), 'sha256': sha(path)}


def plan_data(repeat):
    successor.verify()
    if repeat not in PASSES:
        raise ValueError('Unknown low successor pass')
    source = deepcopy(prior.plan_data(repeat))
    if repeat == 'fresh2':
        original = source['conditions']['P2']['development']
        suffix = deepcopy(original[5:])
        if ([row['record_id'] for row in suffix] != successor.proposal_data()['development_suffix_ids'] or
                [row['request_sha256'] for row in suffix] !=
                successor.proposal_data()['development_suffix_request_sha256']):
            raise ValueError('Low successor would replay or omit a frozen request')
        for index, request in enumerate(suffix):
            request['position'] = index
        smoke = deepcopy(suffix[:3])
        source['conditions']['P2'] = {'smoke': smoke, 'development': suffix}
    source.update(schema=SCHEMA + '-plan',
        series_id=successor.SCHEMA,
        continuation_id=successor.SCHEMA,
        source_successor_sha256=sha(successor.MANIFEST),
        original_execution_sha256=sha(prior.MANIFEST),
        partition_id=PARTITION_ID,
        proposed_child_budget_usd=str(CHILD_CAP),
        per_request_reserve_usd=str(prior.proposal.RESERVE),
        dispatch_gate='Separate root-reviewed adapter and stage receipt, exact new $0.35 '
            'OpenRouter-only child, live route/request check, inspected smoke, sequential reserve')
    if repeat == 'fresh2':
        source['conditions']['P2']['clean_full_phase'] = False
        source['conditions']['P2']['suffix_completion_descriptive_only'] = True
    return source


def verify_plan(repeat, digest):
    target = BASE / repeat / 'manifest.json'
    if sha(target) != digest or json.loads(target.read_text()) != plan_data(repeat):
        raise ValueError('Low successor runtime plan differs')
    return json.loads(target.read_text())


def manifest_data(plans, plan_bindings):
    successor.verify()
    paths = (successor.MANIFEST, successor.RECONCILIATION,
             successor.CHILD, prior.MANIFEST, prior.proposal.ROUTE,
             ROOT / 'scripts/deepseek_low_remaining6_successor_execution_v1.py',
             ROOT / 'tests/test_deepseek_low_remaining6_successor_execution_v1.py',
             ROOT / 'scripts/deepseek_low_remaining6_execution_v1.py',
             ROOT / 'scripts/qwen27_fresh_repeat_execution.py',
             ROOT / 'scripts/deepseek_high_fresh_repeat_execution.py',
             ROOT / 'scripts/paid_budget_partitions_v4.py',
             ROOT / 'scripts/postapproval_authority_v3.py')
    sources = {str(path.relative_to(ROOT)): binding(path) for path in paths}
    sources.update(plan_bindings)
    return {'schema': SCHEMA + '-manifest',
        'status': 'offline_prepared_unapproved',
        'configuration_id': prior.proposal.CONFIG,
        'continuation_id': successor.SCHEMA,
        'source_successor_sha256': sha(successor.MANIFEST),
        'controller_sha256': sha(__file__),
        'plans_sha256': plans, 'partition_id': PARTITION_ID,
        'proposed_child_cap_usd': str(CHILD_CAP),
        'funding_pool': 'openrouter_additional',
        'per_request_reserve_usd': str(prior.proposal.RESERVE),
        'source_bindings': sources,
        'allocation_authorized': False, 'inference_authorized': False}


def expected_manifest():
    plans = {repeat: sha(BASE / repeat / 'manifest.json') for repeat in PASSES}
    for repeat, digest in plans.items():
        verify_plan(repeat, digest)
    bindings = {str((BASE / repeat / 'manifest.json').relative_to(ROOT)):
                binding(BASE / repeat / 'manifest.json') for repeat in PASSES}
    return manifest_data(plans, bindings)


def review_template(digest=None):
    return {'schema': SCHEMA + '-root-review', 'approved': False,
        'independent_review': False, 'authorized_by_root': False,
        'reviewer': None, 'manifest_sha256': digest or sha(MANIFEST),
        'controller_sha256': sha(__file__),
        'source_successor_sha256': sha(successor.MANIFEST)}


def require_review():
    expected = review_template()
    expected.update(approved=True, independent_review=True,
                    authorized_by_root=True, reviewer='root')
    if json.loads(REVIEW.read_text()) != expected:
        raise ValueError('Independent low successor adapter review missing')


def prepare():
    serialized = {repeat: (json.dumps(plan_data(repeat), indent=2,
                                      ensure_ascii=False) + '\n').encode()
                  for repeat in PASSES}
    plans = {repeat: hashlib.sha256(raw).hexdigest() for repeat, raw in serialized.items()}
    bindings = {}
    for repeat, digest in plans.items():
        name = str((BASE / repeat / 'manifest.json').relative_to(ROOT))
        bindings[name] = {'path': name, 'sha256': digest}
    manifest_bytes = (json.dumps(manifest_data(plans, bindings), indent=2) + '\n').encode()
    manifest_sha = hashlib.sha256(manifest_bytes).hexdigest()
    review_bytes = (json.dumps(review_template(manifest_sha), indent=2) + '\n').encode()
    successor.BASE.mkdir(parents=True, exist_ok=True)
    with LOCK.open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if BASE.exists():
            raise FileExistsError('Low successor adapter already prepared')
        with tempfile.TemporaryDirectory(dir=successor.BASE,
                                         prefix='.execution-adapter-v1-') as temp:
            stage = Path(temp)
            for repeat, raw in serialized.items():
                path = stage / repeat / 'manifest.json'
                path.parent.mkdir(parents=True)
                path.write_bytes(raw)
            (stage / 'manifest.json').write_bytes(manifest_bytes)
            (stage / 'root-review.json').write_bytes(review_bytes)
            os.rename(stage, BASE)
    verify()
    return manifest_sha


def verify():
    saved = json.loads(MANIFEST.read_text())
    for item in saved['source_bindings'].values():
        path = (ROOT / item['path']).resolve()
        path.relative_to(ROOT.resolve())
        if sha(path) != item['sha256']:
            raise ValueError('Bound low successor source changed: ' + item['path'])
    if saved != expected_manifest():
        raise ValueError('Low successor adapter manifest differs')
    return sha(MANIFEST)


def live_controls(plan, condition):
    model, endpoint, reserve = prior.live_controls(plan, condition)
    if reserve != prior.proposal.RESERVE or reserve > CHILD_CAP:
        raise ValueError('Low successor reserve exceeds new child cap')
    return model, endpoint, reserve


def global_hold_source(budget_path):
    return prior.proposal.digest(json.dumps({
        'execution_manifest_sha256': sha(MANIFEST),
        'budget_manifest_path': str(Path(budget_path).resolve()),
        'budget_manifest_sha256': sha(budget_path),
        'partition_id': PARTITION_ID, 'cap_usd': str(CHILD_CAP),
        'configuration_id': prior.proposal.CONFIG,
        'continuation_id': successor.SCHEMA,
        'model': prior.proposal.old.MODEL,
        'provider': prior.proposal.old.PROVIDER,
        'reasoning': 'low'}, sort_keys=True))


def exact_budget_entry():
    budget = json.loads(BUDGET.read_text())
    entries = budget.get('partitions')
    if (budget.get('version') != 'paid-partitions-v1' or
            budget.get('master_ledger') != str(MASTER) or
            not isinstance(entries, list) or len(entries) != 1):
        raise ValueError('Exact low successor budget manifest differs')
    entry = entries[0]
    if (entry.get('id') != PARTITION_ID or
            entry.get('cap_usd') != str(CHILD_CAP) or
            entry.get('model') != prior.proposal.old.MODEL or
            entry.get('provider') != prior.proposal.old.PROVIDER or
            entry.get('reasoning') != 'low' or
            entry.get('child_ledger') != str(CHILD_LEDGER)):
        raise ValueError('Exact low successor child binding differs')
    return entry


def stage_receipt(repeat, condition, phase):
    verify(); require_review(); exact_budget_entry()
    if (repeat, condition) not in PHASES or phase not in ('smoke', 'development'):
        raise ValueError('Stage outside low successor order')
    plan = verify_plan(repeat, sha(BASE / repeat / 'manifest.json'))
    if condition not in plan['conditions']:
        raise ValueError('Condition outside low successor plan')
    return {'schema': SCHEMA + '-stage-root-review',
        'approved': False, 'independent_review': False,
        'authorized_by_root': False, 'reviewer': None,
        'configuration_id': prior.proposal.CONFIG,
        'continuation_id': successor.SCHEMA,
        'stage': f'{repeat}/{condition}/{phase}',
        'controller_sha256': sha(__file__),
        'execution_manifest_sha256': sha(MANIFEST),
        'plan_sha256': sha(BASE / repeat / 'manifest.json'),
        'source_successor_sha256': sha(successor.MANIFEST),
        'old_child_reconciliation_sha256': sha(successor.RECONCILIATION),
        'master_ledger': str(MASTER),
        'budget_manifest_path': str(BUDGET.resolve()),
        'budget_manifest_sha256': sha(BUDGET),
        'partition_id': PARTITION_ID,
        'partition_cap_usd': str(CHILD_CAP),
        'funding_pool': 'openrouter_additional',
        'global_authority_head_sha256': authority.read_authority(AUTHORITY).head_sha256,
        'global_hold_source_sha256': global_hold_source(BUDGET)}


def stage_template(repeat, condition, phase):
    plan = verify_plan(repeat, sha(BASE / repeat / 'manifest.json'))
    repaired_core().require_order(plan, condition, phase)
    return stage_receipt(repeat, condition, phase)


def repaired_core():
    core = prior.repaired_core()
    class DualBase:
        def __truediv__(self, child):
            if child == prior.proposal.CONFIG:
                return BASE
            if child in PASSES:
                return BASE / child
            raise ValueError('Unknown low successor path')
    core.study.BASE = DualBase()
    core.study.ORDERS = {'fresh2': ('P2', 'P0', 'P1'),
                         'fresh3': ('P1', 'P2', 'P0')}
    core.study.CONFIGS = {prior.proposal.CONFIG: {
        'effort': 'low', 'historical_continue_on_invalid': True,
        'proposed_child_budget': CHILD_CAP}}
    def study_verify(*args):
        if len(args) == 3:
            config, repeat, digest = args
            if config != prior.proposal.CONFIG:
                raise ValueError('Unknown low successor configuration')
        elif len(args) == 2:
            repeat, digest = args
        else:
            raise TypeError('Expected successor pass and SHA')
        return verify_plan(repeat, digest)
    core.study.verify = staticmethod(study_verify)
    core.__file__ = __file__
    core.EXECUTION_MANIFEST = MANIFEST
    core.RECEIPT_SCHEMA = SCHEMA + '-stage-root-review'
    core.live_controls = live_controls

    def require_order(plan, condition, phase):
        successor.verify()
        stage = (plan['fresh_pass'], condition)
        if stage not in PHASES or phase not in ('smoke', 'development'):
            raise ValueError('Stage outside low successor order')
        for prev_repeat, prev_condition in PHASES[:PHASES.index(stage)]:
            previous = verify_plan(prev_repeat, sha(BASE / prev_repeat / 'manifest.json'))
            core.verify_phase_closure(previous, prev_condition, 'development')
        if phase == 'development':
            folder, _, journal, attempts = core.phase_paths(
                prior.proposal.CONFIG, plan['fresh_pass'], condition, 'smoke')
            inspection = json.loads((folder / 'smoke-inspection.json').read_text())
            bindings = core.verify_phase_closure(plan, condition, 'smoke')
            if (inspection.get('decision') != 'accepted_unchanged' or
                    inspection.get('configuration_id') != prior.proposal.CONFIG or
                    inspection.get('manifest_sha256') != bindings['manifest_sha256'] or
                    inspection.get('journal_sha256') != sha(journal) or
                    inspection.get('attempts_sha256') != sha(attempts) or
                    inspection.get('responses_sha256') != sha(folder / 'smoke.responses.jsonl')):
                raise ValueError('Low successor smoke inspection differs')
    core.require_order = require_order

    def inspect(config, repeat, condition, digest, note):
        plan = study_verify(config, repeat, digest)
        require_order(plan, condition, 'smoke')
        folder, _, journal, attempts = core.phase_paths(config, repeat, condition, 'smoke')
        inspection_path = folder / 'smoke-inspection.json'
        if inspection_path.exists():
            raise ValueError('Smoke already inspected')
        bindings = core.verify_phase_closure(plan, condition, 'smoke')
        records = core.jsonl(attempts)
        expected = [r['record_id'] for r in plan['conditions'][condition]['smoke']]
        if (not note.strip() or len(expected) != 3 or
                [r.get('id') for r in records] != expected or
                any(r.get('status') != 'ok' or r.get('billing_ok') is not True or
                    r.get('cost_unknown') is not False for r in records)):
            raise ValueError('Three reviewed valid low successor smoke calls required')
        value = {'schema': 'openrouter-repeat-smoke-inspection-v1',
            'configuration_id': config, 'fresh_pass': repeat,
            'condition': condition, 'decision': 'accepted_unchanged',
            'note': note, **bindings}
        with inspection_path.open('x') as handle:
            json.dump(value, handle, indent=2)
            handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
        return value
    core.inspect = inspect

    def review_receipt(path, config, repeat, condition, phase, manifest_sha):
        expected_path = BASE / repeat / condition / (phase + '.root-review.json')
        if Path(path).resolve() != expected_path.resolve():
            raise ValueError('Exact low successor stage receipt path differs')
        actual = json.loads(Path(path).read_text())
        expected = stage_receipt(repeat, condition, phase)
        expected.update(approved=True, independent_review=True,
                        authorized_by_root=True, reviewer='root')
        if (config != prior.proposal.CONFIG or
                manifest_sha != expected['plan_sha256'] or actual != expected):
            raise ValueError('Independent low successor stage review differs')
        return actual, BUDGET
    core.review_receipt = review_receipt

    def budget_gate(receipt, budget_path, config):
        exact_budget_entry()
        ledger = partitions.open_partition(MASTER, budget_path,
            PARTITION_ID, prior.proposal.old.MODEL, prior.proposal.old.PROVIDER, 'low')
        try:
            _, pending, blocked = ledger.state()
            if (config != prior.proposal.CONFIG or ledger.cap != CHILD_CAP or
                    ledger.master_cap != Decimal('22.38') or pending or blocked or
                    ledger.closed or ledger.accounted() + prior.proposal.RESERVE > CHILD_CAP):
                raise ValueError('Low successor child lacks exact capacity or binding')
            with authority.old._locked(AUTHORITY) as handle:
                snapshot, holds = authority._scan(handle.read())
            if snapshot.head_sha256 != receipt['global_authority_head_sha256']:
                raise ValueError('Authority head changed before successor admission')
            source = global_hold_source(budget_path)
            if PARTITION_ID in holds:
                event = holds[PARTITION_ID]
                if (event.get('funding_pool') != 'openrouter_additional' or
                        event.get('usd') != str(CHILD_CAP) or
                        event.get('source_sha256') != source or
                        event.get('budget_manifest_sha256') != sha(budget_path)):
                    raise ValueError('Existing low successor authority hold differs')
            else:
                authority.hold_authority(AUTHORITY, PARTITION_ID,
                    str(CHILD_CAP), source, snapshot.head_sha256,
                    stage_path=BASE / 'fresh2/P2/smoke.claim.json',
                    funding_pool='openrouter_additional',
                    budget_path=budget_path, partition_id=PARTITION_ID)
            return ledger
        except BaseException:
            ledger.close()
            raise
    core.budget_gate = budget_gate
    return core


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('prepare', 'verify', 'live-check',
                                      'review-template', 'stage-template',
                                      'inspect', 'smoke', 'development'))
    p.add_argument('--fresh-pass', choices=PASSES, default='fresh2')
    p.add_argument('--condition', choices=('P0', 'P1', 'P2'), default='P2')
    p.add_argument('--phase', choices=('smoke', 'development'), default='smoke')
    p.add_argument('--review', type=Path)
    p.add_argument('--env-file')
    p.add_argument('--note')
    args = p.parse_args()
    if args.action == 'prepare': print(prepare()); return
    print(verify())
    if args.action == 'verify': return
    if args.action == 'review-template':
        print(json.dumps(review_template(), indent=2)); return
    if args.action == 'live-check':
        plan = verify_plan(args.fresh_pass, sha(BASE / args.fresh_pass / 'manifest.json'))
        _, endpoint, reserve = live_controls(plan, args.condition)
        print(json.dumps({'inference_sent': False, 'pricing': endpoint['pricing'],
                          'reserve_usd': str(reserve)})); return
    require_review()
    if args.action == 'stage-template':
        print(json.dumps(stage_template(args.fresh_pass, args.condition,
                                        args.phase), indent=2)); return
    core = repaired_core()
    digest = sha(BASE / args.fresh_pass / 'manifest.json')
    if args.action == 'inspect':
        if not args.note: p.error('inspect requires --note')
        print(core.inspect(prior.proposal.CONFIG, args.fresh_pass,
                           args.condition, digest, args.note)); return
    if not args.review: p.error('smoke/development require exact stage --review')
    print(core.execute(prior.proposal.CONFIG, args.fresh_pass,
                       args.condition, args.action, digest, args.review, args.env_file))


if __name__ == '__main__': main()
