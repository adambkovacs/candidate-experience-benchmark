#!/usr/bin/env python3
"""Separate source-bound closure adapter for DeepSeek high authority v3.

Repairs path/signature compatibility and uses the v3 admitted price ceiling.
The frozen v3 controller and saved attempts are never edited or replayed.
"""
import argparse
import ast
from copy import deepcopy
import json
import os
from pathlib import Path

import deepseek_high_authority_v3 as bridge

study = bridge.study
BASE = bridge.BASE / 'closure-bridge-v1'
MANIFEST = BASE / 'manifest.json'
REVIEW = BASE / 'root-review.json'
SCHEMA = 'deepseek-high-v3-closure-bridge-v1'
P0 = bridge.BASE / 'fresh1/P0'
SOURCES = ('deepseek_high_v3_closure_bridge.py', 'deepseek_high_authority_v3.py',
           'deepseek_high_fresh_repeat_execution.py', 'qwen27_fresh_repeat_execution.py',
           'openrouter_paid_benchmark.py', 'prompt_admission.py')
EVIDENCE = ('development.claim.json', 'development.journal.jsonl',
            'development.attempts.jsonl', 'development.responses.jsonl',
            'smoke.claim.json', 'smoke.journal.jsonl', 'smoke.attempts.jsonl',
            'smoke.responses.jsonl', 'smoke-inspection.json')


def binding(path):
    path = Path(path).resolve()
    path.relative_to(study.ROOT.resolve())
    return {'path': str(path.relative_to(study.ROOT.resolve())), 'sha256': study.sha(path)}


def bound(item):
    path = (study.ROOT / item['path']).resolve()
    path.relative_to(study.ROOT.resolve())
    if study.sha(path) != item['sha256']:
        raise ValueError('Closure source changed: ' + item['path'])
    return path


def repaired_core():
    core = bridge._private_runner()
    original_study = core.study
    class DualBase:
        def __truediv__(self, child):
            if child == bridge.CONFIG:
                return bridge.BASE
            if child in study.ORDERS:
                return bridge.BASE / child
            raise ValueError('Unknown closure path')
    class DualStudy(original_study):
        BASE = DualBase()
        EFFORT = study.EFFORT
        @staticmethod
        def verify(*args):
            if len(args) == 2:
                repeat, digest = args
            elif len(args) == 3:
                config, repeat, digest = args
                if config != bridge.CONFIG:
                    raise ValueError('Unknown closure configuration')
            else:
                raise TypeError('Expected repeat, SHA or config, repeat, SHA')
            return bridge.verify_plan(repeat, digest)
    core.study = DualStudy
    strict = core.verify_phase_closure.__globals__['_strict_closure']
    source = Path(bridge.frozen.__file__).read_text()
    tree = ast.parse(source)
    function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                    and n.name == 'verify_phase_closure')
    changes = {'critical': 0, 'route': 0}
    class Repair(ast.NodeTransformer):
        def visit_Assign(self, node):
            node = self.generic_visit(node)
            if any(isinstance(t, ast.Name) and t.id == 'critical' for t in node.targets):
                values = ast.literal_eval(node.value)
                if values[-1] != 'pricing' or values.count('pricing') != 1:
                    raise ValueError('Frozen route comparison changed')
                node.value = ast.Constant(value=values[:-1])
                changes['critical'] += 1
            if any(isinstance(t, ast.Name) and t.id == 'recalculated' for t in node.targets):
                changes['route'] += 1
                return [ast.parse('route_check(model, endpoint)').body[0], node]
            return node
    function = Repair().visit(function)
    if changes != {'critical': 1, 'route': 1}:
        raise ValueError('Frozen closure structure changed')
    isolated = ast.Module(body=[function], type_ignores=[])
    ast.fix_missing_locations(isolated)
    namespace = dict(bridge.frozen.verify_phase_closure.__globals__,
                     study=DualStudy, runner=core, _strict_closure=strict,
                     route_check=lambda model, endpoint: bridge.check_route(
                         model, endpoint, bridge.route_snapshot()['model'],
                         bridge.route_snapshot()['selected_endpoint']))
    exec(compile(isolated, __file__, 'exec'), namespace)
    core.verify_phase_closure = namespace['verify_phase_closure']
    return core


def verify_p0():
    bridge.verify()
    plan = bridge.verify_plan('fresh1', bridge.sha(bridge.BASE / 'fresh1/manifest.json'))
    core = repaired_core()
    core.verify_phase_closure(plan, 'P0', 'smoke')
    result = core.verify_phase_closure(plan, 'P0', 'development')
    attempts = [json.loads(x) for x in (P0 / 'development.attempts.jsonl').read_text().splitlines() if x.strip()]
    counts = {'ok': 0, 'invalid_output': 0}
    for record in attempts:
        status = record.get('status')
        if status not in counts:
            raise ValueError('Unexpected completed P0 status')
        counts[status] += 1
    if len(attempts) != 60 or counts != {'ok': 59, 'invalid_output': 1} or attempts[29]['id'] != 'DEV-030' or attempts[29]['status'] != 'invalid_output':
        raise ValueError('P0 retained invalid outcome differs')
    return result, counts


def expected_manifest():
    p0, counts = verify_p0()
    sources = {'execution': binding(bridge.EXECUTION),
               'route': binding(bridge.ROUTE),
               'plan_fresh1': binding(bridge.BASE / 'fresh1/manifest.json')}
    sources.update({'p0_' + name: binding(P0 / name) for name in EVIDENCE})
    sources.update({'code_' + name: binding(study.ROOT / 'scripts' / name) for name in SOURCES})
    return {'schema': SCHEMA, 'status': 'offline_verified_unapproved',
            'configuration_id': bridge.CONFIG,
            'original_execution_sha256': bridge.sha(bridge.EXECUTION),
            'p0_development_closure': p0, 'p0_status_counts': counts,
            'retained_intrinsic_invalid_id': 'DEV-030',
            'route_policy': 'v3 identity and reasoning unchanged; live token prices may decrease below saved rates; frozen request ceilings remain unchanged',
            'test_sha256': study.sha(study.ROOT / 'tests/test_deepseek_high_v3_closure_bridge.py'),
            'source_bindings': sources, 'inference_authorized': False}


def prepare():
    value = expected_manifest()
    BASE.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open('x') as out:
        json.dump(value, out, indent=2)
        out.write('\n'); out.flush(); os.fsync(out.fileno())
    with REVIEW.open('x') as out:
        json.dump(review_template(), out, indent=2)
        out.write('\n'); out.flush(); os.fsync(out.fileno())
    return study.sha(MANIFEST)


def verify(expected_sha=None):
    if expected_sha and study.sha(MANIFEST) != expected_sha:
        raise ValueError('Bridge manifest SHA differs')
    value = json.loads(MANIFEST.read_text())
    for item in value['source_bindings'].values():
        bound(item)
    if value != expected_manifest():
        raise ValueError('Bridge or frozen P0 evidence changed')
    return value


def review_template():
    return {'schema': SCHEMA + '-root-review', 'approved': False,
            'independent_review': False, 'authorized_by_root': False,
            'reviewer': None, 'manifest_sha256': study.sha(MANIFEST),
            'controller_sha256': study.sha(__file__),
            'original_execution_sha256': bridge.sha(bridge.EXECUTION),
            'p0_attempts_sha256': study.sha(P0 / 'development.attempts.jsonl')}


def require_review():
    expected = review_template()
    expected.update(approved=True, independent_review=True,
                    authorized_by_root=True, reviewer='root')
    if json.loads(REVIEW.read_text()) != expected:
        raise ValueError('Independent closure bridge review missing or mismatched')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('audit-p0', 'prepare', 'verify', 'review-template',
                                      'inspect', 'smoke', 'development'))
    p.add_argument('--bridge-sha256')
    p.add_argument('--fresh-pass', choices=tuple(study.ORDERS), default='fresh1')
    p.add_argument('--condition', choices=study.CONDITIONS, default='P1')
    p.add_argument('--review', type=Path)
    p.add_argument('--env-file')
    p.add_argument('--note')
    args = p.parse_args()
    if args.action == 'audit-p0':
        result, counts = verify_p0()
        print(json.dumps({'closure': result, 'statuses': counts})); return
    if args.action == 'prepare': print(prepare()); return
    if not args.bridge_sha256: p.error('Exact --bridge-sha256 required')
    verify(args.bridge_sha256)
    if args.action == 'verify': print('verified'); return
    if args.action == 'review-template':
        print(json.dumps(review_template(), indent=2)); return
    require_review()
    core = repaired_core()
    digest = bridge.sha(bridge.BASE / args.fresh_pass / 'manifest.json')
    if args.action == 'inspect':
        if not args.note: p.error('inspect requires --note')
        print(core.inspect(bridge.CONFIG, args.fresh_pass, args.condition, digest, args.note)); return
    if not args.review: p.error('smoke/development require original v3 --review receipt')
    print(core.execute(bridge.CONFIG, args.fresh_pass, args.condition, args.action,
                       digest, args.review, args.env_file))


if __name__ == '__main__': main()
