#!/usr/bin/env python3
"""Source-bound execution candidate for the distinct low remaining-six plan.

Preparation is offline. A separate root adapter receipt, exact allocation,
and an independently reviewed receipt are required for every stage.
"""
import argparse
import ast
from copy import deepcopy
from decimal import Decimal
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import FunctionType
from urllib.parse import quote

import deepseek_low_remaining6_price_v2 as proposal
import deepseek_high_fresh_repeat_execution as high_verifier
import openrouter_paid_benchmark as paid
import paid_budget_partitions_v4 as partitions
import postapproval_authority_v3 as authority
import openrouter_budget_amendment_v3 as amendment

SCHEMA = 'deepseek-low-remaining6-execution-v1'
ROOT = proposal.ROOT
BASE = proposal.BASE / 'execution-adapter-v1'
MANIFEST = BASE / 'manifest.json'
REVIEW = BASE / 'root-review.json'
LOCK = proposal.BASE / '.execution-adapter-v1.lock'
BUDGET = proposal.BASE / 'budget.json'
CHILD_LEDGER = proposal.BASE / ('budget-' + proposal.PARTITION_ID + '.jsonl')
MASTER = amendment.MASTER
AUTHORITY = amendment.AUTHORITY
SHARED_SOURCE = ROOT / 'scripts/qwen27_fresh_repeat_execution.py'
PHASES = proposal.PHASES
PASSES = ('fresh2', 'fresh3')


def sha(path):
    return proposal.sha(path)


def binding(path):
    path = Path(path).resolve()
    path.relative_to(ROOT.resolve())
    return {'path': str(path.relative_to(ROOT.resolve())), 'sha256': sha(path)}


def plan_data(repeat):
    source = json.loads(proposal.MANIFEST.read_text())
    proposal.verify()
    original, _ = proposal.sealed_sources()
    if repeat not in PASSES:
        raise ValueError('Unknown low remaining pass')
    conditions = [condition for name, condition in PHASES if name == repeat]
    planned = {}
    for condition in conditions:
        templates = source['requests_by_condition'][condition]
        old_rows = original['requests_by_condition'][condition]
        if ([x['id'] for x in templates] != proposal.IDS or
                [x['id'] for x in old_rows] != proposal.IDS or
                any(x['original_request_sha256'] != y['request_sha256']
                    for x, y in zip(templates, old_rows))):
            raise ValueError('Low condition template membership differs')
        planned[condition] = {}
        for stage, selected, frozen in (
                ('smoke', templates[:3], old_rows[:3]),
                ('development', templates, old_rows)):
            planned[condition][stage] = [{
                'position': position, 'record_id': item['id'],
                'payload': item['payload'],
                'request_sha256': item['request_sha256'],
                'input_sha256': old_item['input_sha256'],
                'instruction_sha256': old_item['instruction_sha256']}
                for position, (item, old_item) in enumerate(zip(selected, frozen))]
    return {'schema': SCHEMA + '-plan', 'series_id': proposal.SCHEMA,
            'configuration_id': proposal.CONFIG,
            'original_configuration_id': proposal.old.CONFIG,
            'fresh_pass': repeat, 'condition_order': conditions,
            'model': proposal.old.MODEL,
            'provider_tag': proposal.old.PROVIDER,
            'provider_name': 'OpenInference', 'quantization': 'fp4',
            'reasoning_effort': 'low', 'temperature': 0,
            'max_tokens': proposal.MAX_TOKENS,
            'timeout_seconds': 300.0,
            'continue_on_invalid_output': True,
            'retry_policy': 'no_implicit_retry',
            'reference_labels_read': False,
            'conditions': planned,
            'source_proposal_sha256': sha(proposal.MANIFEST),
            'public_route_sha256': sha(proposal.ROUTE),
            'partition_id': proposal.PARTITION_ID,
            'proposed_child_budget_usd': str(proposal.CHILD_CAP),
            'per_request_reserve_usd': str(proposal.RESERVE)}


def verify_plan(repeat, expected_sha):
    target = BASE / repeat / 'manifest.json'
    if sha(target) != expected_sha or json.loads(target.read_text()) != plan_data(repeat):
        raise ValueError('Remaining low runtime plan differs from source-bound proposal')
    return json.loads(target.read_text())


def manifest_data(plans, plan_bindings):
    proposal.verify()
    paths = (proposal.MANIFEST, proposal.ROUTE,
             ROOT / 'scripts/deepseek_low_remaining6_execution_v1.py',
             ROOT / 'tests/test_deepseek_low_remaining6_execution_v1.py',
             SHARED_SOURCE,
             ROOT / 'scripts/deepseek_high_fresh_repeat_execution.py',
             ROOT / 'scripts/openrouter_paid_benchmark.py',
             ROOT / 'scripts/paid_budget_partitions_v4.py',
             ROOT / 'scripts/postapproval_authority_v3.py',
             ROOT / 'scripts/openrouter_budget_v4.py')
    sources = {str(path.relative_to(ROOT)): binding(path) for path in paths}
    sources.update(plan_bindings)
    return {'schema': SCHEMA + '-manifest',
            'status': 'offline_prepared_unapproved',
            'configuration_id': proposal.CONFIG,
            'proposal_sha256': sha(proposal.MANIFEST),
            'controller_sha256': sha(__file__),
            'plans_sha256': plans,
            'partition_id': proposal.PARTITION_ID,
            'proposed_child_cap_usd': str(proposal.CHILD_CAP),
            'funding_pool': 'openrouter_additional',
            'per_request_reserve_usd': str(proposal.RESERVE),
            'source_bindings': sources,
            'inference_authorized': False,
            'allocation_authorized': False}


def expected_manifest():
    plans = {repeat: sha(BASE / repeat / 'manifest.json') for repeat in PASSES}
    for repeat, digest in plans.items():
        verify_plan(repeat, digest)
    bindings = {str((BASE / repeat / 'manifest.json').relative_to(ROOT)):
                binding(BASE / repeat / 'manifest.json') for repeat in PASSES}
    return manifest_data(plans, bindings)


def review_template(manifest_hash=None):
    return {'schema': SCHEMA + '-root-review',
            'approved': False, 'independent_review': False,
            'authorized_by_root': False, 'reviewer': None,
            'manifest_sha256': manifest_hash or sha(MANIFEST),
            'controller_sha256': sha(__file__),
            'proposal_sha256': sha(proposal.MANIFEST)}


def require_review():
    expected = review_template()
    expected.update(approved=True, independent_review=True,
                    authorized_by_root=True, reviewer='root')
    if json.loads(REVIEW.read_text()) != expected:
        raise ValueError('Independent low execution review missing or mismatched')


def prepare():
    serialized = {repeat: (json.dumps(plan_data(repeat), indent=2,
                                      ensure_ascii=False) + '\n').encode()
                  for repeat in PASSES}
    plans = {repeat: hashlib.sha256(raw).hexdigest()
             for repeat, raw in serialized.items()}
    bindings = {}
    for repeat, digest in plans.items():
        path = BASE / repeat / 'manifest.json'
        bindings[str(path.relative_to(ROOT))] = {
            'path': str(path.relative_to(ROOT)), 'sha256': digest}
    manifest_bytes = (json.dumps(manifest_data(plans, bindings),
                                 indent=2, ensure_ascii=False) + '\n').encode()
    manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
    review_bytes = (json.dumps(review_template(manifest_hash), indent=2) + '\n').encode()
    proposal.BASE.mkdir(parents=True, exist_ok=True)
    with LOCK.open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if BASE.exists():
            raise FileExistsError('Low execution adapter already prepared')
        with tempfile.TemporaryDirectory(dir=proposal.BASE,
                                         prefix='.execution-adapter-v1-') as temp:
            stage = Path(temp)
            for repeat, raw in serialized.items():
                target = stage / repeat / 'manifest.json'
                target.parent.mkdir(parents=True)
                target.write_bytes(raw)
            (stage / 'manifest.json').write_bytes(manifest_bytes)
            (stage / 'root-review.json').write_bytes(review_bytes)
            os.rename(stage, BASE)
    verify()
    return manifest_hash


def verify():
    value = json.loads(MANIFEST.read_text())
    for item in value['source_bindings'].values():
        path = (ROOT / item['path']).resolve()
        path.relative_to(ROOT.resolve())
        if sha(path) != item['sha256']:
            raise ValueError('Bound low execution source changed: ' + item['path'])
    if value != expected_manifest():
        raise ValueError('Remaining low execution adapter manifest differs')
    return sha(MANIFEST)


def live_controls(plan, condition):
    if plan.get('configuration_id') != proposal.CONFIG or condition not in plan['conditions']:
        raise ValueError('Wrong remaining low configuration or condition')
    catalog = paid.fetch('/models', timeout=120)
    endpoints = paid.fetch('/models/' + quote(proposal.old.MODEL, safe='/') + '/endpoints',
                           timeout=120)
    model, endpoint = paid.select_endpoint(proposal.old.MODEL,
        proposal.old.PROVIDER, catalog, endpoints,
        proposal.INPUT_CEILING, proposal.OUTPUT_CEILING)
    saved = json.loads(proposal.ROUTE.read_text())
    proposal.check_route(model, endpoint, saved['model'], saved['endpoint'])
    inputs = {row['id']: row['feedback'] for row in
              proposal.read_rows(proposal.old.INPUTS)}
    for phase in ('smoke', 'development'):
        for request in plan['conditions'][condition][phase]:
            frozen = request['payload']
            rebuilt = paid.make_payload(proposal.old.MODEL, endpoint,
                inputs[request['record_id']], frozen['messages'][0]['content'],
                frozen['response_format']['json_schema']['schema'], 'low',
                proposal.MAX_TOKENS, proposal.INPUT_CEILING,
                proposal.OUTPUT_CEILING, model)
            if (rebuilt != frozen or
                    proposal.digest(json.dumps(rebuilt, sort_keys=True)) !=
                    request['request_sha256']):
                raise ValueError('Live low request differs from frozen successor')
    return model, endpoint, proposal.RESERVE


def global_hold_source(budget_path):
    return proposal.digest(json.dumps({
        'execution_manifest_sha256': sha(MANIFEST),
        'budget_manifest_path': str(Path(budget_path).resolve()),
        'budget_manifest_sha256': sha(budget_path),
        'partition_id': proposal.PARTITION_ID,
        'cap_usd': str(proposal.CHILD_CAP),
        'configuration_id': proposal.CONFIG,
        'model': proposal.old.MODEL,
        'provider': proposal.old.PROVIDER,
        'reasoning': 'low'}, sort_keys=True))


def exact_budget_entry():
    budget = json.loads(BUDGET.read_text())
    entries = budget.get('partitions')
    if (budget.get('version') != 'paid-partitions-v1' or
            budget.get('master_ledger') != str(MASTER) or
            not isinstance(entries, list) or len(entries) != 1):
        raise ValueError('Exact remaining low budget manifest differs')
    entry = entries[0]
    if (entry.get('id') != proposal.PARTITION_ID or
            entry.get('cap_usd') != str(proposal.CHILD_CAP) or
            entry.get('model') != proposal.old.MODEL or
            entry.get('provider') != proposal.old.PROVIDER or
            entry.get('reasoning') != 'low' or
            entry.get('child_ledger') != str(CHILD_LEDGER)):
        raise ValueError('Exact remaining low child ledger binding differs')
    return entry


def stage_receipt(repeat, condition, phase):
    verify(); require_review(); exact_budget_entry()
    if (repeat, condition) not in PHASES or phase not in ('smoke', 'development'):
        raise ValueError('Unknown remaining low stage')
    plan = verify_plan(repeat, sha(BASE / repeat / 'manifest.json'))
    if condition not in plan['conditions']:
        raise ValueError('Condition outside remaining low pass')
    return {'schema': SCHEMA + '-stage-root-review',
        'approved': False, 'independent_review': False,
        'authorized_by_root': False, 'reviewer': None,
        'configuration_id': proposal.CONFIG,
        'stage': f'{repeat}/{condition}/{phase}',
        'controller_sha256': sha(__file__),
        'execution_manifest_sha256': sha(MANIFEST),
        'plan_sha256': sha(BASE / repeat / 'manifest.json'),
        'proposal_sha256': sha(proposal.MANIFEST),
        'master_ledger': str(MASTER),
        'budget_manifest_path': str(BUDGET.resolve()),
        'budget_manifest_sha256': sha(BUDGET),
        'partition_id': proposal.PARTITION_ID,
        'partition_cap_usd': str(proposal.CHILD_CAP),
        'funding_pool': 'openrouter_additional',
        'global_authority_head_sha256': authority.read_authority(AUTHORITY).head_sha256,
        'global_hold_source_sha256': global_hold_source(BUDGET)}


def stage_template(repeat, condition, phase):
    plan = verify_plan(repeat, sha(BASE / repeat / 'manifest.json'))
    repaired_core().require_order(plan, condition, phase)
    return stage_receipt(repeat, condition, phase)


def repaired_core():
    spec = importlib.util.spec_from_file_location('_deepseek_low_remaining6_shared',
                                                 SHARED_SOURCE)
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    class DualBase:
        def __truediv__(self, child):
            if child == proposal.CONFIG:
                return BASE
            if child in PASSES:
                return BASE / child
            raise ValueError('Unknown remaining low path')
    class RuntimeStudy:
        CONFIG = proposal.CONFIG
        EFFORT = 'low'
        ROOT = ROOT
        BASE = DualBase()
        ROUTE_AUDIT = str(proposal.ROUTE.relative_to(ROOT))
        CONFIGS = {proposal.CONFIG: {'effort': 'low',
            'historical_continue_on_invalid': True,
            'proposed_child_budget': proposal.CHILD_CAP}}
        ORDERS = {'fresh2': ('P2', 'P0', 'P1'),
                  'fresh3': ('P1', 'P2', 'P0')}
        MODEL = proposal.old.MODEL
        PROVIDER = proposal.old.PROVIDER
        PROVIDER_NAME = 'OpenInference'
        MAX_TOKENS = proposal.MAX_TOKENS
        TIMEOUT = 300.0
        sha = staticmethod(sha)
        digest = staticmethod(proposal.digest)
        @staticmethod
        def verify(*args):
            if len(args) == 2:
                repeat, digest = args
            elif len(args) == 3:
                config, repeat, digest = args
                if config != proposal.CONFIG:
                    raise ValueError('Unknown remaining low configuration')
            else:
                raise TypeError('Expected repeat, SHA or config, repeat, SHA')
            return verify_plan(repeat, digest)
    core.study = RuntimeStudy
    core.__file__ = __file__
    core.MASTER = MASTER
    core.EXECUTION_MANIFEST = MANIFEST
    core.RECEIPT_SCHEMA = SCHEMA + '-stage-root-review'
    core.CONTINUE_INTRINSIC_INVALID = True
    core.partitions = partitions
    core.live_controls = live_controls

    strict = core.verify_phase_closure
    source = Path(high_verifier.__file__).read_text()
    tree = ast.parse(source)
    function = next(node for node in tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == 'verify_phase_closure')
    changes = {'critical': 0, 'route': 0, 'route_key': 0}
    class ClosureRepair(ast.NodeTransformer):
        def visit_Subscript(self, node):
            node = self.generic_visit(node)
            expected = ast.parse(
                "json.loads((study.ROOT / study.ROUTE_AUDIT).read_text())",
                mode='eval').body
            if (isinstance(node.slice, ast.Constant) and
                    node.slice.value == 'selected_endpoint' and
                    ast.dump(node.value) == ast.dump(expected)):
                node.slice = ast.Constant(value='endpoint')
                changes['route_key'] += 1
            return node
        def visit_Assign(self, node):
            node = self.generic_visit(node)
            if any(isinstance(t, ast.Name) and t.id == 'critical' for t in node.targets):
                fields = ast.literal_eval(node.value)
                if fields[-1] != 'pricing' or fields.count('pricing') != 1:
                    raise ValueError('Frozen closure route comparison differs')
                node.value = ast.Constant(value=fields[:-1])
                changes['critical'] += 1
            if any(isinstance(t, ast.Name) and t.id == 'recalculated' for t in node.targets):
                changes['route'] += 1
                return [ast.parse('route_check(model, endpoint)').body[0], node]
            return node
    function = ClosureRepair().visit(function)
    if changes != {'critical': 1, 'route': 1, 'route_key': 1}:
        raise ValueError('Frozen closure structure differs')
    isolated = ast.Module(body=[function], type_ignores=[])
    ast.fix_missing_locations(isolated)
    def route_check(model, endpoint):
        saved = json.loads(proposal.ROUTE.read_text())
        return proposal.check_route(model, endpoint,
                                    saved['model'], saved['endpoint'])
    namespace = dict(high_verifier.verify_phase_closure.__globals__,
                     study=RuntimeStudy, runner=core, _strict_closure=strict,
                     route_check=route_check)
    exec(compile(isolated, __file__, 'exec'), namespace)
    core.verify_phase_closure = namespace['verify_phase_closure']

    def require_order(plan, condition, phase):
        proposal.verify()
        stage = (plan['fresh_pass'], condition)
        if stage not in PHASES or phase not in ('smoke', 'development'):
            raise ValueError('Stage outside remaining low order')
        for previous_repeat, previous_condition in PHASES[:PHASES.index(stage)]:
            previous = verify_plan(previous_repeat,
                sha(BASE / previous_repeat / 'manifest.json'))
            core.verify_phase_closure(previous, previous_condition, 'development')
        if phase == 'development':
            folder, _, journal, attempts = core.phase_paths(
                proposal.CONFIG, plan['fresh_pass'], condition, 'smoke')
            inspection_path = folder / 'smoke-inspection.json'
            if not inspection_path.exists():
                raise ValueError('Inspected smoke required')
            inspection = json.loads(inspection_path.read_text())
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
            raise ValueError('Exact remaining low stage receipt path differs')
        actual = json.loads(Path(path).read_text())
        expected = stage_receipt(repeat, condition, phase)
        expected.update(approved=True, independent_review=True,
                        authorized_by_root=True, reviewer='root')
        if (config != proposal.CONFIG or manifest_sha != expected['plan_sha256'] or
                actual != expected):
            raise ValueError('Independent remaining low stage receipt differs')
        return actual, BUDGET
    core.review_receipt = review_receipt

    def budget_gate(receipt, budget_path, config):
        exact_budget_entry()
        ledger = partitions.open_partition(MASTER, budget_path,
            proposal.PARTITION_ID, proposal.old.MODEL, proposal.old.PROVIDER, 'low')
        try:
            _, pending, blocked = ledger.state()
            if (config != proposal.CONFIG or
                    ledger.cap != proposal.CHILD_CAP or
                    ledger.master_cap != Decimal('22.38') or
                    pending or blocked or ledger.closed or
                    ledger.accounted() + proposal.RESERVE > ledger.cap):
                raise ValueError('Exact remaining low child lacks capacity or binding')
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
                    stage_path=BASE / 'fresh2/P2/smoke.claim.json',
                    funding_pool='openrouter_additional',
                    budget_path=budget_path,
                    partition_id=proposal.PARTITION_ID)
            return ledger
        except BaseException:
            ledger.close()
            raise
    core.budget_gate = budget_gate

    tree = ast.parse(SHARED_SOURCE.read_text())
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
        raise ValueError('Frozen sequential reserve control changed')
    isolated = ast.Module(body=[execute], type_ignores=[])
    ast.fix_missing_locations(isolated)
    exec(compile(isolated, __file__, 'exec'), core.__dict__)
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
        print(core.inspect(proposal.CONFIG, args.fresh_pass, args.condition,
                           digest, args.note)); return
    if not args.review: p.error('smoke/development require exact stage --review')
    print(core.execute(proposal.CONFIG, args.fresh_pass, args.condition,
                       args.action, digest, args.review, args.env_file))


if __name__ == '__main__': main()
