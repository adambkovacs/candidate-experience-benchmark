#!/usr/bin/env python3
"""Reviewed-entrypoint candidate for eight never-started plain Mistral stages."""
import argparse
import ast
from decimal import Decimal
import importlib.util
import json
import os
from pathlib import Path
from types import FunctionType
from urllib.parse import quote

import mistral119_high_plain_remaining8_v4 as proposal
import mistral119_high_plain_authority_v1 as old
import openrouter_paid_benchmark as paid
import openrouter_authority_release_v4 as authority
import paid_budget_partitions_v4 as partitions

ROOT = proposal.ROOT
BASE = proposal.BASE
CONFIG = proposal.CONFIG
REVIEW = BASE / 'root-review.json'
BUDGET = BASE / 'budget.json'
CHILD_LEDGER = BASE / ('budget-' + proposal.PARTITION_ID + '.jsonl')
SCHEMA = proposal.SCHEMA + '-execution'
MASTER = old.MASTER
AUTHORITY = old.AUTHORITY


def sha(path):
    return proposal.sha(path)


def review_template():
    return {'schema': SCHEMA + '-root-review',
        'approved': False, 'independent_review': False,
        'authorized_by_root': False, 'reviewer': None,
        'proposal_sha256': sha(proposal.MANIFEST),
        'controller_sha256': sha(__file__)}


def require_review():
    expected = review_template()
    expected.update(approved=True, independent_review=True,
                    authorized_by_root=True, reviewer='root')
    if json.loads(REVIEW.read_text()) != expected:
        raise ValueError('Independent plain Mistral eight-stage review missing')


def exact_budget_entry():
    budget = json.loads(BUDGET.read_text())
    entries = budget.get('partitions')
    if (budget.get('version') != 'paid-partitions-v1' or
            budget.get('master_ledger') != str(MASTER) or
            not isinstance(entries, list) or len(entries) != 1):
        raise ValueError('Exact plain Mistral child budget manifest differs')
    entry = entries[0]
    if (entry.get('id') != proposal.PARTITION_ID or
            entry.get('cap_usd') != str(proposal.CHILD_CAP) or
            entry.get('model') != old.study.MODEL or
            entry.get('provider') != old.PROVIDER or
            entry.get('reasoning') != 'high' or
            entry.get('child_ledger') != str(CHILD_LEDGER)):
        raise ValueError('Exact plain Mistral child binding differs')
    return entry


def live_controls(plan, condition):
    proposal.verify()
    if (plan.get('configuration_id') != CONFIG or
            (plan.get('fresh_pass'), condition) not in proposal.PHASES):
        raise ValueError('Stage outside eight unopened plain Mistral stages')
    saved = proposal.portable_route(proposal.portable_sources())
    catalog = paid.fetch('/models', timeout=120)
    endpoint_path = '/models/' + quote(old.study.MODEL, safe='/') + '/endpoints'
    endpoints = paid.fetch(endpoint_path, timeout=120)
    model, endpoint = paid.select_endpoint(old.study.MODEL, old.PROVIDER,
        catalog, endpoints, old.study.INPUT_PRICE, old.study.OUTPUT_PRICE)
    old.check_route(model, endpoint, saved['model'], saved['selected_endpoint'])
    inputs = {row['id']: row['feedback'] for row in old.study.input_rows()}
    for phase in ('smoke', 'development'):
        for request in plan['conditions'][condition][phase]:
            payload = request['payload']
            rebuilt = paid.make_payload(old.study.MODEL, endpoint,
                inputs[request['record_id']], payload['messages'][0]['content'],
                payload['response_format']['json_schema']['schema'], 'high',
                old.study.MAX_TOKENS, old.study.INPUT_PRICE,
                old.study.OUTPUT_PRICE, model)
            if (rebuilt != payload or request['request_sha256'] !=
                    old.study.digest(json.dumps(rebuilt, sort_keys=True))):
                raise ValueError('Live plain route would change frozen request')
    if proposal.RESERVE != paid.reservation(endpoint, old.study.MAX_TOKENS,
            old.study.INPUT_PRICE, old.study.OUTPUT_PRICE):
        raise ValueError('Plain Mistral reserve changed')
    return model, endpoint, proposal.RESERVE


def hold_source(budget_path=BUDGET):
    return old.study.digest(json.dumps({
        'proposal_sha256': sha(proposal.MANIFEST),
        'budget_manifest_path': str(Path(budget_path).resolve()),
        'budget_manifest_sha256': sha(budget_path),
        'partition_id': proposal.PARTITION_ID,
        'cap_usd': str(proposal.CHILD_CAP),
        'configuration_id': CONFIG,
        'model': old.study.MODEL,
        'provider': old.PROVIDER,
        'reasoning': 'high'}, sort_keys=True))


def stage_receipt(repeat, condition, phase):
    proposal.verify(); require_review(); exact_budget_entry()
    if (repeat, condition) not in proposal.PHASES or phase not in ('smoke', 'development'):
        raise ValueError('Stage outside eight unopened plain Mistral stages')
    plan = proposal.verify_plan(repeat, sha(BASE / repeat / 'manifest.json'))
    if condition not in plan['conditions']:
        raise ValueError('Stage omitted from exact plan')
    snapshot = authority.read_authority(AUTHORITY)
    return {'schema': SCHEMA + '-stage-root-review',
        'approved': False, 'independent_review': False,
        'authorized_by_root': False, 'reviewer': None,
        'configuration_id': CONFIG,
        'stage': f'{repeat}/{condition}/{phase}',
        'controller_sha256': sha(__file__),
        'proposal_sha256': sha(proposal.MANIFEST),
        'plan_sha256': sha(BASE / repeat / 'manifest.json'),
        'parent_terminal_sha256': sha(old.BASE / 'terminal-public.json'),
        'parent_reconciliation_sha256': sha(old.BASE / 'reconciliation.json'),
        'master_ledger': str(MASTER),
        'budget_manifest_path': str(BUDGET.resolve()),
        'budget_manifest_sha256': sha(BUDGET),
        'partition_id': proposal.PARTITION_ID,
        'partition_cap_usd': str(proposal.CHILD_CAP),
        'funding_pool': 'openrouter_additional',
        'global_authority_head_sha256': snapshot.head_sha256,
        'global_hold_source_sha256': hold_source(BUDGET)}


def stage_template(repeat, condition, phase):
    plan = proposal.verify_plan(repeat, sha(BASE / repeat / 'manifest.json'))
    private_core().require_order(plan, condition, phase)
    return stage_receipt(repeat, condition, phase)


def private_core():
    """Load the bound shared lifecycle with the new plan and v4 money gates."""
    proposal.verify()
    spec = importlib.util.spec_from_file_location('_mistral119_remaining8_private',
                                                    old.frozen.SHARED_SOURCE)
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)

    class BasePath:
        def __truediv__(self, config):
            if config != CONFIG:
                raise ValueError('Unknown plain Mistral configuration path')
            return BASE

    class RuntimeStudy(old.frozen._Study):
        BASE = BasePath()
        PROVIDER = old.PROVIDER
        ORDERS = proposal.ORDERS
        CONFIGS = {CONFIG: {'effort': 'high',
            'historical_continue_on_invalid': False,
            'proposed_child_budget': proposal.CHILD_CAP}}

        @staticmethod
        def verify(config, repeat, digest):
            if config != CONFIG:
                raise ValueError('Unknown plain Mistral configuration')
            return proposal.verify_plan(repeat, digest)

    core.study = RuntimeStudy
    core.__file__ = __file__
    core.partitions = partitions
    core.EXECUTION_MANIFEST = proposal.MANIFEST
    core.RECEIPT_SCHEMA = SCHEMA + '-stage-root-review'
    core.CONTINUE_INTRINSIC_INVALID = False
    core.live_controls = live_controls
    closure = core.verify_phase_closure
    core.verify_phase_closure = FunctionType(closure.__code__,
        dict(closure.__globals__, study=RuntimeStudy))

    def require_order(plan, condition, phase):
        proposal.verify()
        stage = (plan['fresh_pass'], condition)
        if stage not in proposal.PHASES or phase not in ('smoke', 'development'):
            raise ValueError('Stage outside eight unopened plain Mistral stages')
        for earlier_repeat, earlier_condition in proposal.PHASES[:proposal.PHASES.index(stage)]:
            previous = proposal.verify_plan(earlier_repeat,
                sha(BASE / earlier_repeat / 'manifest.json'))
            core.verify_phase_closure(previous, earlier_condition, 'development')
        if phase == 'development':
            folder, _, journal, attempts = core.phase_paths(
                CONFIG, plan['fresh_pass'], condition, 'smoke')
            inspection = json.loads((folder / 'smoke-inspection.json').read_text())
            bindings = core.verify_phase_closure(plan, condition, 'smoke')
            if (inspection.get('decision') != 'accepted_unchanged' or
                    inspection.get('configuration_id') != CONFIG or
                    inspection.get('manifest_sha256') != bindings['manifest_sha256'] or
                    inspection.get('journal_sha256') != sha(journal) or
                    inspection.get('attempts_sha256') != sha(attempts) or
                    inspection.get('responses_sha256') !=
                    sha(folder / 'smoke.responses.jsonl')):
                raise ValueError('Plain Mistral three-call smoke inspection differs')
    core.require_order = require_order

    def review_receipt(path, config, repeat, condition, phase, manifest_sha):
        expected_path = BASE / repeat / condition / (phase + '.root-review.json')
        if Path(path).resolve() != expected_path.resolve():
            raise ValueError('Exact plain Mistral stage receipt path differs')
        actual = json.loads(Path(path).read_text())
        expected = stage_receipt(repeat, condition, phase)
        expected.update(approved=True, independent_review=True,
                        authorized_by_root=True, reviewer='root')
        if (config != CONFIG or manifest_sha != expected['plan_sha256'] or
                actual != expected):
            raise ValueError('Independent plain Mistral stage review differs')
        return actual, BUDGET
    core.review_receipt = review_receipt

    def budget_gate(receipt, budget_path, config):
        exact_budget_entry()
        def checked_child():
            ledger = partitions.open_partition(MASTER, budget_path,
                proposal.PARTITION_ID, old.study.MODEL, old.PROVIDER, 'high')
            try:
                _, pending, blocked = ledger.state()
                if (config != CONFIG or ledger.cap != proposal.CHILD_CAP or
                        ledger.master_cap != Decimal('22.38') or pending or blocked or
                        ledger.closed or ledger.accounted() + proposal.RESERVE > ledger.cap):
                    raise ValueError('Plain Mistral child lacks sequential capacity')
                return ledger
            except BaseException:
                ledger.close(); raise
        inspected = checked_child()
        inspected.close()
        with authority.old._locked(AUTHORITY) as handle:
            snapshot, holds, released = authority._scan(handle.read())
        if not released or snapshot.head_sha256 != receipt['global_authority_head_sha256']:
            raise ValueError('V4 transition or authority head differs')
        source = hold_source(budget_path)
        if proposal.PARTITION_ID in holds:
            event = holds[proposal.PARTITION_ID]
            if (event.get('funding_pool') != 'openrouter_additional' or
                    event.get('usd') != str(proposal.CHILD_CAP) or
                    event.get('source_sha256') != source or
                    event.get('budget_manifest_sha256') != sha(budget_path)):
                raise ValueError('Existing plain Mistral v4 hold differs')
        else:
            authority.hold_authority(AUTHORITY, proposal.PARTITION_ID,
                str(proposal.CHILD_CAP), source, snapshot.head_sha256,
                stage_path=BASE / 'fresh1/P1/smoke.claim.json',
                funding_pool='openrouter_additional', budget_path=budget_path,
                partition_id=proposal.PARTITION_ID)
        return checked_child()
    core.budget_gate = budget_gate

    tree = ast.parse(Path(old.frozen.SHARED_SOURCE).read_text())
    execute = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                   and node.name == 'execute')
    needle = ast.dump(ast.parse('attempt_id = ledger.reserve(reserve, rid)').body[0])
    count = 0
    class CapacityGate(ast.NodeTransformer):
        def visit_Assign(self, node):
            nonlocal count
            if ast.dump(node) != needle:
                return node
            count += 1
            check = ast.parse("if ledger.accounted() + reserve > ledger.cap:\n"
                "    durable(audit, {'event': 'phase_stopped', 'next_unsent_id': rid, "
                "'reason': 'insufficient_capacity', 'utc': utc()})\n"
                "    return False\n").body[0]
            return [check, node]
    execute = CapacityGate().visit(execute)
    if count != 1:
        raise ValueError('Bound sequential reserve call changed')
    isolated = ast.Module(body=[execute], type_ignores=[])
    ast.fix_missing_locations(isolated)
    exec(compile(isolated, __file__, 'exec'), core.__dict__)
    return core


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('verify', 'live-check', 'review-template',
        'hold-source', 'stage-template', 'smoke', 'inspect', 'development'))
    p.add_argument('--fresh-pass', choices=proposal.PASSES, default='fresh1')
    p.add_argument('--condition', choices=('P0', 'P1', 'P2'), default='P1')
    p.add_argument('--phase', choices=('smoke', 'development'), default='smoke')
    p.add_argument('--review', type=Path)
    p.add_argument('--env-file')
    p.add_argument('--note')
    args = p.parse_args()
    print(proposal.verify())
    if args.action == 'verify': return
    if args.action == 'review-template':
        print(json.dumps(review_template(), indent=2)); return
    if args.action == 'hold-source':
        print(hold_source()); return
    plan = proposal.verify_plan(args.fresh_pass,
        sha(BASE / args.fresh_pass / 'manifest.json'))
    if args.action == 'live-check':
        _, endpoint, reserve = live_controls(plan, args.condition)
        print(json.dumps({'inference_sent': False,
            'pricing': endpoint['pricing'], 'reserve_usd': str(reserve)})); return
    require_review()
    if args.action == 'stage-template':
        print(json.dumps(stage_template(args.fresh_pass,
            args.condition, args.phase), indent=2)); return
    core = private_core()
    digest = sha(BASE / args.fresh_pass / 'manifest.json')
    if args.action == 'inspect':
        if not args.note: p.error('inspect requires --note')
        print(core.inspect(CONFIG, args.fresh_pass,
            args.condition, digest, args.note)); return
    if not args.review: p.error('smoke/development require exact stage --review')
    print(core.execute(CONFIG, args.fresh_pass, args.condition,
                       args.action, digest, args.review, args.env_file))


if __name__ == '__main__':
    main()
