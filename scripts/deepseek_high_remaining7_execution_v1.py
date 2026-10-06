#!/usr/bin/env python3
"""Reviewed-entrypoint candidate for the distinct remaining-seven high plan.

Preparation/verification are offline. Allocation and every stage require
separate root action. The shared, source-bound runner retains durable attempt
and raw-response capture, sequential reserves, and no implicit retry.
"""
import argparse
from copy import deepcopy
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from urllib.parse import quote

import deepseek_high_remaining7_price_v1 as proposal
import deepseek_high_v3_closure_bridge as closure
import deepseek_high_authority_v3 as prior
import openrouter_paid_benchmark as paid
import paid_budget_partitions_v4 as partitions
import postapproval_authority_v3 as authority
import openrouter_budget_amendment_v3 as amendment
import openrouter_budget_v4 as budget_v4

study = prior.study
BASE = proposal.BASE / 'execution-adapter-v1'
MANIFEST = BASE / 'manifest.json'
REVIEW = BASE / 'root-review.json'
PREPARE_LOCK = proposal.BASE / '.execution-adapter-v1.lock'
SCHEMA = 'deepseek-high-remaining7-execution-v1'
MASTER = amendment.MASTER
AUTHORITY = amendment.AUTHORITY
BUDGET = proposal.BASE / 'budget.json'
CHILD_LEDGER = proposal.BASE / ('budget-' + proposal.PARTITION_ID + '.jsonl')
OLD_RECONCILIATION = prior.BASE / 'reconciliation.json'
OLD_LEDGER = prior.BASE / ('budget-' + prior.PARTITION_ID + '.jsonl')


def sha(path):
    return study.sha(path)


def binding(path):
    path = Path(path).resolve()
    path.relative_to(study.ROOT.resolve())
    return {'path': str(path.relative_to(study.ROOT.resolve())), 'sha256': sha(path)}


def old_child_closed():
    receipt = json.loads(OLD_RECONCILIATION.read_text())
    if (receipt.get('event') != 'partition_reconciled' or
            receipt.get('partition_id') != prior.PARTITION_ID or
            receipt.get('child_ledger') != str(OLD_LEDGER) or
            receipt.get('child_sha256') != sha(OLD_LEDGER) or
            Decimal(receipt.get('unknown_upper_bound_usd', '-1')) != 0):
        raise ValueError('Old DeepSeek high child not exactly reconciled')
    raw = MASTER.read_bytes()
    ledger = object.__new__(budget_v4.BudgetLedger)
    ledger.events = [json.loads(x) for x in raw.splitlines() if x.strip()]
    ledger.cap_limit = budget_v4.CAP
    ledger.is_master = True
    ledger.file = SimpleNamespace(name=str(MASTER))
    ledger.state()
    old = ledger.partitions.get(prior.PARTITION_ID)
    if not old or old.get('active') is not False:
        raise ValueError('Old DeepSeek high child is still active')
    return receipt


def source_plan():
    proposal.verify()
    old_child_closed()
    return json.loads(proposal.MANIFEST.read_text())


def plan_data(repeat):
    source = source_plan()
    original = deepcopy(prior.verify_plan(repeat,
                                         sha(prior.BASE / repeat / 'manifest.json')))
    selected = [condition for name, condition in proposal.PHASES if name == repeat]
    if not selected:
        raise ValueError('No remaining phases in fresh pass')
    original['conditions'] = {condition: original['conditions'][condition]
                              for condition in selected}
    original['condition_order'] = selected
    for condition in selected:
        for stage in ('smoke', 'development'):
            rows = source['requests_by_stage'][f'{repeat}/{condition}/{stage}']
            old_rows = original['conditions'][condition][stage]
            if ([x['record_id'] for x in old_rows] != [x['id'] for x in rows] or
                    any(x['request_sha256'] != y['original_request_sha256']
                        for x, y in zip(old_rows, rows))):
                raise ValueError('Remaining stage differs from original frozen order')
            for request, new in zip(old_rows, rows):
                request.update(payload=new['payload'],
                               request_sha256=new['request_sha256'])
                if (request['input_sha256'] != new['input_sha256'] or
                        request['instruction_sha256'] != new['instruction_sha256']):
                    raise ValueError('Original high input or instruction changed')
    original.update(schema=SCHEMA + '-plan', series_id=proposal.SCHEMA,
        configuration_id=proposal.CONFIG,
        original_configuration_id=prior.CONFIG,
        source_proposal_sha256=sha(proposal.MANIFEST),
        public_route_sha256=sha(proposal.ROUTE),
        partition_id=proposal.PARTITION_ID,
        proposed_child_budget_usd=str(proposal.CHILD_CAP),
        input_price_ceiling_usd_per_million=str(proposal.INPUT_CEILING),
        output_price_ceiling_usd_per_million=str(proposal.OUTPUT_CEILING),
        cache_read_price_ceiling_usd_per_million=str(proposal.CACHE_CEILING),
        per_request_reserve_usd=str(proposal.RESERVE),
        dispatch_gate='Separate adapter review, exact stage receipt, $1 OpenRouter-only hold, '
            'closed old child, live route and reserve, sequential capacity, inspected smoke')
    return original


def verify_plan(repeat, expected_sha):
    path = BASE / repeat / 'manifest.json'
    if sha(path) != expected_sha or json.loads(path.read_text()) != plan_data(repeat):
        raise ValueError('Remaining high runtime plan differs from bound proposal')
    return json.loads(path.read_text())


def manifest_data(plans, plan_bindings):
    proposal.verify()
    old_child_closed()
    paths = (proposal.MANIFEST, proposal.ROUTE, OLD_RECONCILIATION,
             OLD_LEDGER, closure.MANIFEST, closure.REVIEW,
             study.ROOT / 'scripts/deepseek_high_remaining7_execution_v1.py',
             study.ROOT / 'tests/test_deepseek_high_remaining7_execution_v1.py')
    sources = {str(path.relative_to(study.ROOT)): binding(path) for path in paths}
    sources.update(plan_bindings)
    return {'schema': SCHEMA + '-manifest', 'status': 'offline_prepared_unapproved',
            'configuration_id': proposal.CONFIG,
            'proposal_sha256': sha(proposal.MANIFEST),
            'controller_sha256': sha(__file__),
            'plans_sha256': plans,
            'old_child_reconciliation_sha256': sha(OLD_RECONCILIATION),
            'partition_id': proposal.PARTITION_ID,
            'proposed_child_cap_usd': str(proposal.CHILD_CAP),
            'funding_pool': 'openrouter_additional',
            'per_request_reserve_usd': str(proposal.RESERVE),
            'source_bindings': sources,
            'inference_authorized': False, 'allocation_authorized': False}


def expected_manifest():
    plans = {repeat: sha(BASE / repeat / 'manifest.json')
             for repeat in study.ORDERS}
    for repeat, digest in plans.items():
        verify_plan(repeat, digest)
    plan_bindings = {str((BASE / repeat / 'manifest.json').relative_to(study.ROOT)):
                     binding(BASE / repeat / 'manifest.json') for repeat in study.ORDERS}
    return manifest_data(plans, plan_bindings)


def review_template(manifest_hash=None):
    return {'schema': SCHEMA + '-root-review', 'approved': False,
            'independent_review': False, 'authorized_by_root': False,
            'reviewer': None, 'manifest_sha256': manifest_hash or sha(MANIFEST),
            'controller_sha256': sha(__file__),
            'proposal_sha256': sha(proposal.MANIFEST)}


def require_review():
    expected = review_template()
    expected.update(approved=True, independent_review=True,
                    authorized_by_root=True, reviewer='root')
    if json.loads(REVIEW.read_text()) != expected:
        raise ValueError('Independent execution adapter review missing or mismatched')


def prepare():
    # Build every byte before claiming the final directory. Only a complete
    # directory is published; a failed validation leaves no partial adapter.
    serialized = {}
    for repeat in study.ORDERS:
        serialized[repeat] = (json.dumps(plan_data(repeat), indent=2,
                                         ensure_ascii=False) + '\n').encode()
    plans = {repeat: hashlib.sha256(raw).hexdigest()
             for repeat, raw in serialized.items()}
    plan_bindings = {}
    for repeat, digest in plans.items():
        path = BASE / repeat / 'manifest.json'
        plan_bindings[str(path.relative_to(study.ROOT))] = {
            'path': str(path.relative_to(study.ROOT)), 'sha256': digest}
    manifest_bytes = (json.dumps(manifest_data(plans, plan_bindings),
                                 indent=2, ensure_ascii=False) + '\n').encode()
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    review_bytes = (json.dumps(review_template(manifest_hash), indent=2) + '\n').encode()
    proposal.BASE.mkdir(parents=True, exist_ok=True)
    with PREPARE_LOCK.open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if BASE.exists():
            raise FileExistsError('High remaining7 execution adapter already prepared')
        with tempfile.TemporaryDirectory(dir=proposal.BASE,
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
    return manifest_hash


def verify():
    value = json.loads(MANIFEST.read_text())
    for item in value['source_bindings'].values():
        path = (study.ROOT / item['path']).resolve()
        path.relative_to(study.ROOT.resolve())
        if sha(path) != item['sha256']:
            raise ValueError('Bound execution source changed: ' + item['path'])
    if value != expected_manifest():
        raise ValueError('Remaining high execution adapter manifest differs')
    return sha(MANIFEST)


def live_controls(plan, condition):
    if plan.get('configuration_id') != proposal.CONFIG or condition not in plan['conditions']:
        raise ValueError('Wrong remaining high configuration or condition')
    catalog = paid.fetch('/models', timeout=120)
    endpoints = paid.fetch('/models/' + quote(study.MODEL, safe='/') + '/endpoints', timeout=120)
    model, endpoint = paid.select_endpoint(study.MODEL, study.PROVIDER, catalog,
                                            endpoints, proposal.INPUT_CEILING,
                                            proposal.OUTPUT_CEILING)
    saved = prior.route_snapshot()
    proposal.check_route(model, endpoint, saved['model'], saved['selected_endpoint'])
    inputs = {row['id']: row['feedback'] for row in study.input_rows()}
    for phase in ('smoke', 'development'):
        for request in plan['conditions'][condition][phase]:
            old = request['payload']
            rebuilt = paid.make_payload(study.MODEL, endpoint,
                inputs[request['record_id']], old['messages'][0]['content'],
                old['response_format']['json_schema']['schema'], study.EFFORT,
                study.MAX_TOKENS, proposal.INPUT_CEILING,
                proposal.OUTPUT_CEILING, model)
            if (rebuilt != old or
                    study.digest(json.dumps(rebuilt, sort_keys=True)) != request['request_sha256']):
                raise ValueError('Live high request differs from versioned plan')
    return model, endpoint, proposal.RESERVE


def global_hold_source(budget_path):
    return study.digest(json.dumps({'execution_manifest_sha256': sha(MANIFEST),
        'budget_manifest_path': str(Path(budget_path).resolve()),
        'budget_manifest_sha256': sha(budget_path),
        'partition_id': proposal.PARTITION_ID,
        'cap_usd': str(proposal.CHILD_CAP),
        'configuration_id': proposal.CONFIG, 'model': study.MODEL,
        'provider': study.PROVIDER, 'reasoning': study.EFFORT}, sort_keys=True))


def exact_budget_entry():
    budget = json.loads(BUDGET.read_text())
    entries = budget.get('partitions')
    if (budget.get('version') != 'paid-partitions-v1' or
            budget.get('master_ledger') != str(MASTER) or
            not isinstance(entries, list) or len(entries) != 1):
        raise ValueError('Exact remaining high budget manifest differs')
    entry = entries[0]
    if (entry.get('id') != proposal.PARTITION_ID or
            entry.get('cap_usd') != str(proposal.CHILD_CAP) or
            entry.get('model') != study.MODEL or
            entry.get('provider') != study.PROVIDER or
            entry.get('reasoning') != study.EFFORT or
            entry.get('child_ledger') != str(CHILD_LEDGER)):
        raise ValueError('Exact remaining high child ledger binding differs')
    return entry


def stage_receipt(repeat, condition, phase):
    verify(); require_review()
    exact_budget_entry()
    if (repeat, condition) not in proposal.PHASES or phase not in ('smoke', 'development'):
        raise ValueError('Unknown remaining high stage')
    plan = verify_plan(repeat, sha(BASE / repeat / 'manifest.json'))
    if condition not in plan['conditions']:
        raise ValueError('Condition outside remaining high plan')
    return {'schema': SCHEMA + '-stage-root-review',
        'approved': False, 'independent_review': False,
        'authorized_by_root': False, 'reviewer': None,
        'configuration_id': proposal.CONFIG,
        'stage': f'{repeat}/{condition}/{phase}',
        'controller_sha256': sha(__file__),
        'execution_manifest_sha256': sha(MANIFEST),
        'plan_sha256': sha(BASE / repeat / 'manifest.json'),
        'proposal_sha256': sha(proposal.MANIFEST),
        'old_child_reconciliation_sha256': sha(OLD_RECONCILIATION),
        'master_ledger': str(MASTER),
        'budget_manifest_path': str(BUDGET.resolve()),
        'budget_manifest_sha256': sha(BUDGET),
        'partition_id': proposal.PARTITION_ID,
        'partition_cap_usd': str(proposal.CHILD_CAP),
        'funding_pool': 'openrouter_additional',
        'global_authority_head_sha256': authority.read_authority(AUTHORITY).head_sha256,
        'global_hold_source_sha256': global_hold_source(BUDGET)}


def stage_template(repeat, condition, phase):
    """Offer a stage receipt only when the predecessor and smoke gates pass."""
    plan = verify_plan(repeat, sha(BASE / repeat / 'manifest.json'))
    repaired_core().require_order(plan, condition, phase)
    return stage_receipt(repeat, condition, phase)


def repaired_core():
    core = closure.repaired_core()
    parent_study = core.study
    class DualBase:
        def __truediv__(self, child):
            if child == proposal.CONFIG:
                return BASE
            if child in study.ORDERS:
                return BASE / child
            raise ValueError('Unknown remaining high path')
    class RuntimeStudy(parent_study):
        CONFIG = proposal.CONFIG
        BASE = DualBase()
        ROUTE_AUDIT = str(proposal.ROUTE.relative_to(study.ROOT))
        CONFIGS = {proposal.CONFIG: {'effort': study.EFFORT,
            'historical_continue_on_invalid': True,
            'proposed_child_budget': proposal.CHILD_CAP}}
        @staticmethod
        def verify(*args):
            if len(args) == 2:
                repeat, digest = args
            elif len(args) == 3:
                config, repeat, digest = args
                if config != proposal.CONFIG:
                    raise ValueError('Unknown remaining high configuration')
            else:
                raise TypeError('Expected repeat, SHA or config, repeat, SHA')
            return verify_plan(repeat, digest)
    core.study = RuntimeStudy
    core.EXECUTION_MANIFEST = MANIFEST
    core.RECEIPT_SCHEMA = SCHEMA + '-stage-root-review'
    core.CONTINUE_INTRINSIC_INVALID = True
    core.live_controls = live_controls

    original = core.verify_phase_closure
    def route_check(model, endpoint):
        saved = prior.route_snapshot()
        return proposal.check_route(model, endpoint,
                                    saved['model'], saved['selected_endpoint'])
    from types import FunctionType
    core.verify_phase_closure = FunctionType(original.__code__,
        dict(original.__globals__, study=RuntimeStudy, runner=core,
             route_check=route_check))

    def require_order(plan, condition, phase):
        stage = (plan['fresh_pass'], condition)
        if stage not in proposal.PHASES or phase not in ('smoke', 'development'):
            raise ValueError('Stage outside remaining high order')
        prior_plan = prior.verify_plan('fresh1', sha(prior.BASE / 'fresh1/manifest.json'))
        old_core = closure.repaired_core()
        for previous in ('P0', 'P1'):
            old_core.verify_phase_closure(prior_plan, previous, 'development')
        for previous_repeat, previous_condition in proposal.PHASES[:proposal.PHASES.index(stage)]:
            previous_plan = verify_plan(previous_repeat,
                sha(BASE / previous_repeat / 'manifest.json'))
            core.verify_phase_closure(previous_plan, previous_condition, 'development')
        if phase == 'development':
            folder, _, journal, attempts = core.phase_paths(
                proposal.CONFIG, plan['fresh_pass'], condition, 'smoke')
            receipt = folder / 'smoke-inspection.json'
            if not receipt.exists():
                raise ValueError('Inspected smoke required')
            inspection = json.loads(receipt.read_text())
            bindings = core.verify_phase_closure(plan, condition, 'smoke')
            if (inspection.get('decision') != 'accepted_unchanged' or
                    inspection.get('configuration_id') != proposal.CONFIG or
                    inspection.get('manifest_sha256') != bindings['manifest_sha256'] or
                    inspection.get('journal_sha256') != sha(journal) or
                    inspection.get('attempts_sha256') != sha(attempts) or
                    inspection.get('responses_sha256') != sha(folder / 'smoke.responses.jsonl')):
                raise ValueError('Smoke inspection binding changed')
    core.require_order = require_order

    def review_receipt(path, config, repeat, condition, phase, manifest_sha):
        expected_path = BASE / repeat / condition / (phase + '.root-review.json')
        if Path(path).resolve() != expected_path.resolve():
            raise ValueError('Exact remaining high stage receipt path differs')
        actual = json.loads(Path(path).read_text())
        expected = stage_receipt(repeat, condition, phase)
        expected.update(approved=True, independent_review=True,
                        authorized_by_root=True, reviewer='root')
        if (config != proposal.CONFIG or manifest_sha != expected['plan_sha256'] or
                actual != expected):
            raise ValueError('Independent remaining high stage receipt differs')
        return actual, BUDGET
    core.review_receipt = review_receipt

    def budget_gate(receipt, budget_path, config):
        exact_budget_entry()
        ledger = partitions.open_partition(MASTER, budget_path,
            proposal.PARTITION_ID, study.MODEL, study.PROVIDER, study.EFFORT)
        try:
            _, pending, blocked = ledger.state()
            if (config != proposal.CONFIG or
                    ledger.cap != proposal.CHILD_CAP or
                    ledger.master_cap != Decimal('22.38') or
                    pending or blocked or ledger.closed or
                    ledger.accounted() + proposal.RESERVE > ledger.cap):
                raise ValueError('Exact remaining high child lacks capacity or binding')
            with authority.old._locked(AUTHORITY) as handle:
                snapshot, holds = authority._scan(handle.read())
            if snapshot.head_sha256 != receipt['global_authority_head_sha256']:
                raise ValueError('Authority head changed before child admission')
            source = global_hold_source(budget_path)
            if proposal.PARTITION_ID in holds:
                event = holds[proposal.PARTITION_ID]
                if (event.get('funding_pool') != 'openrouter_additional' or
                        event.get('usd') != str(proposal.CHILD_CAP) or
                        event.get('source_sha256') != source or
                        event.get('budget_manifest_sha256') != sha(budget_path)):
                    raise ValueError('Existing whole-series authority hold differs')
            else:
                authority.hold_authority(AUTHORITY, proposal.PARTITION_ID,
                    str(proposal.CHILD_CAP), source, snapshot.head_sha256,
                    stage_path=BASE / 'fresh1/P2/smoke.claim.json',
                    funding_pool='openrouter_additional',
                    budget_path=budget_path,
                    partition_id=proposal.PARTITION_ID)
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
    p.add_argument('--fresh-pass', choices=tuple(study.ORDERS), default='fresh1')
    p.add_argument('--condition', choices=study.CONDITIONS, default='P2')
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
        print(core.inspect(proposal.CONFIG, args.fresh_pass, args.condition,
                           digest, args.note)); return
    if not args.review: p.error('smoke/development require exact stage --review')
    print(core.execute(proposal.CONFIG, args.fresh_pass, args.condition,
                       args.action, digest, args.review, args.env_file))


if __name__ == '__main__': main()
