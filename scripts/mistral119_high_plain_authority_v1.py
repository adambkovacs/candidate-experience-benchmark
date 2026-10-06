#!/usr/bin/env python3
"""Mistral Small 4 plain-provider high first smoke under reviewed authority.

Public route capture and proposal preparation are inference-free. Allocation,
authority hold, root stage review and dispatch remain separate root actions.
"""
import argparse
import ast
from copy import deepcopy
from decimal import Decimal
import importlib.util
import json
import os
from pathlib import Path
import time
from urllib.parse import quote

import mistral119_fresh_repeat_execution as frozen
import openrouter_budget_amendment_v3 as amendment
import openrouter_paid_benchmark as paid
import paid_budget_partitions_v4 as partitions
import postapproval_authority_v3 as authority

study = frozen.study
OLD_CONFIG = 'openrouter-paid-mistral-small4-119b-high'
CONFIG = OLD_CONFIG + '-mistral-authority-v1'
SCHEMA = 'mistral119-high-plain-authority-v1'
BASE = study.ROOT / 'results/repeatability-v1' / SCHEMA
ROUTE = BASE / 'public-route.json'
PARENT = study.ROOT / 'results/repeatability-v1/mistral119-high-hosted-authority-v3-v1'
PROVIDER = 'mistral'
PROVIDER_NAME = study.PROVIDER_NAME
PARENT_TERMINAL = PARENT / 'terminal-public.json'
PARENT_RECONCILIATION = PARENT / 'reconciliation.json'
EXECUTION = BASE / 'execution-manifest.json'
PARTITION_ID = 'mistral119-high-plain-authority-v1-fresh1-p0-smoke'
CAP = Decimal('0.75')
RESERVE = study.RESERVE
MASTER = amendment.MASTER
AUTHORITY = amendment.AUTHORITY
MODEL_FIELDS = ('id', 'canonical_slug', 'hugging_face_id', 'context_length',
                'architecture', 'reasoning')
ENDPOINT_FIELDS = ('tag', 'provider_name', 'quantization', 'model_id', 'status',
                   'context_length', 'max_prompt_tokens', 'max_completion_tokens',
                   'supported_parameters', 'pricing')
sha = study.sha


def parent_terminal():
    terminal = json.loads(PARENT_TERMINAL.read_text())
    reconciliation = json.loads(PARENT_RECONCILIATION.read_text())
    if (terminal.get('schema') != 'mistral119-high-zdr-terminal-public-v1' or
            terminal.get('configuration_id') != OLD_CONFIG + '-authority-v3-hosted-v1' or
            terminal.get('stage') != 'fresh1/P0/smoke' or
            terminal.get('provider') != 'mistral/zdr' or
            terminal.get('model') != study.MODEL or
            terminal.get('attempted_ids') != ['DEV-001'] or
            terminal.get('never_sent_smoke_ids') != ['DEV-002', 'DEV-003'] or
            terminal.get('http_status') != 429 or
            terminal.get('limit_source') != 'upstream_provider_shared_pool' or
            terminal.get('valid_count') != 0 or
            terminal.get('unknown_cost_upper_bound_usd') != str(RESERVE) or
            terminal.get('retry_sent') is not False or
            terminal.get('reconciliation_sha256') != sha(PARENT_RECONCILIATION) or
            reconciliation.get('event') != 'partition_reconciled' or
            reconciliation.get('partition_id') != 'mistral119-high-hosted-authority-v3-v1-fresh123' or
            reconciliation.get('unknown_upper_bound_usd') != str(RESERVE) or
            reconciliation.get('known_actual_usd') != '0'):
        raise ValueError('Terminal ZDR predecessor or conservative reconciliation differs')
    original = study.BASE / OLD_CONFIG
    for path in original.rglob('*'):
        if path.is_file() and path.name != 'manifest.json':
            raise ValueError('Original high series has unexpected dispatch evidence')
    source = original / 'fresh1/manifest.json'
    study.verify(OLD_CONFIG, 'fresh1', sha(source))
    return terminal


def check_route(model, endpoint, saved_model, saved_endpoint):
    if (any(model.get(key) != saved_model.get(key) for key in MODEL_FIELDS) or
            any(endpoint.get(key) != saved_endpoint.get(key) for key in ENDPOINT_FIELDS) or
            endpoint.get('status') != 0 or endpoint.get('tag') != PROVIDER or
            endpoint.get('provider_name') != PROVIDER_NAME or
            endpoint.get('model_id') != study.MODEL or
            endpoint.get('quantization') != study.QUANTIZATION or
            paid.reasoning(model, endpoint, 'high') != {'enabled': True, 'effort': 'high'} or
            paid.reservation(endpoint, study.MAX_TOKENS, study.INPUT_PRICE,
                             study.OUTPUT_PRICE) != RESERVE):
        raise ValueError('Exact Mistral high model, endpoint, price, reasoning or reserve changed')


def capture_route():
    parent_terminal()
    if ROUTE.exists():
        raise FileExistsError('Public route snapshot already exists')
    catalog = paid.fetch('/models', timeout=120)
    endpoint_source = '/models/' + quote(study.MODEL, safe='/') + '/endpoints'
    endpoints = paid.fetch(endpoint_source, timeout=120)
    model, endpoint = paid.select_endpoint(study.MODEL, PROVIDER, catalog,
                                           endpoints, study.INPUT_PRICE,
                                           study.OUTPUT_PRICE)
    old, _ = study.historical(OLD_CONFIG)
    expected_endpoint = {**old['provider_endpoint'], 'tag': PROVIDER}
    check_route(model, endpoint, old['model_catalog_entry'], expected_endpoint)
    value = {'schema': SCHEMA + '-public-route',
             'source': 'https://openrouter.ai/api/v1' + endpoint_source,
             'catalog_source': 'https://openrouter.ai/api/v1/models',
             'captured_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
             'model': model, 'selected_endpoint': endpoint,
             'requested_endpoint_count': len([x for x in endpoints.get('data', {}).get('endpoints', [])
                                               if x.get('tag') == PROVIDER]),
             'inference_sent': False}
    BASE.mkdir(parents=True, exist_ok=True)
    with ROUTE.open('x') as out:
        json.dump(value, out, indent=2)
        out.write('\n'); out.flush(); os.fsync(out.fileno())
    return sha(ROUTE)


def route_snapshot():
    data = json.loads(ROUTE.read_text())
    if (data.get('schema') != SCHEMA + '-public-route' or
            data.get('source') != 'https://openrouter.ai/api/v1/models/' + study.MODEL + '/endpoints' or
            data.get('inference_sent') is not False or
            data.get('requested_endpoint_count') != 1):
        raise ValueError('Exact inference-free public route snapshot required')
    old, _ = study.historical(OLD_CONFIG)
    expected_endpoint = {**old['provider_endpoint'], 'tag': PROVIDER}
    check_route(data['model'], data['selected_endpoint'],
                old['model_catalog_entry'], expected_endpoint)
    return data


def plan_data(repeat):
    if repeat != 'fresh1':
        raise ValueError('Only fresh1/P0 three-request smoke is proposed')
    parent_terminal()
    original_path = study.BASE / OLD_CONFIG / 'fresh1/manifest.json'
    original = deepcopy(study.verify(OLD_CONFIG, 'fresh1', sha(original_path)))
    snapshot = route_snapshot()
    inputs = {row['id']: row['feedback'] for row in study.input_rows()}
    smoke = []
    for request in original['conditions']['P0']['smoke']:
        before = request['payload']
        rebuilt = paid.make_payload(study.MODEL, snapshot['selected_endpoint'],
            inputs[request['record_id']], before['messages'][0]['content'],
            before['response_format']['json_schema']['schema'], 'high',
            study.MAX_TOKENS, study.INPUT_PRICE, study.OUTPUT_PRICE,
            snapshot['model'])
        expected = deepcopy(before)
        expected['provider']['only'] = [PROVIDER]
        if rebuilt != expected or request['request_sha256'] != study.digest(json.dumps(before, sort_keys=True)):
            raise ValueError('Plain route may change only frozen provider tag')
        changed = deepcopy(request)
        changed['payload'] = rebuilt
        changed['request_sha256'] = study.digest(json.dumps(rebuilt, sort_keys=True))
        smoke.append(changed)
    original['conditions'] = {'P0': {'instruction': original['conditions']['P0']['instruction'],
                                    'smoke': smoke, 'development': []}}
    original['budget_estimate'] = {
        'planned_smoke_calls': 3,
        'maximum_per_request_reserve_usd': str(RESERVE),
        'three_smoke_reservations_usd': str(RESERVE * 3),
        'proposed_child_cap_usd': str(CAP),
        'note': 'This allocation proposal admits only one three-request smoke; full high repeats require separate admission.',
    }
    original.update(schema=SCHEMA + '-plan', series_id=SCHEMA,
        configuration_id=CONFIG, original_configuration_id=OLD_CONFIG,
        provider_tag=PROVIDER, condition_order=['P0'],
        development_count_per_condition=0, planned_request_count=3,
        execution_status='offline_first_smoke_only',
        historical_status='Distinct prior ZDR high smoke stopped at DEV-001 HTTP 429; no result transfers',
        original_plan_manifest_sha256=sha(original_path), public_route_sha256=sha(ROUTE),
        parent_terminal_sha256=sha(PARENT_TERMINAL),
        parent_reconciliation_sha256=sha(PARENT_RECONCILIATION),
        aggregate_openrouter_cap_usd='22.38', funding_pool='openrouter_additional',
        partition_id=PARTITION_ID, proposed_child_budget_usd=str(CAP),
        per_request_reserve_usd=str(RESERVE),
        dispatch_gate='Independent root review for this single fresh1/P0 smoke only; exact plain Mistral route, privacy, distinct child and OR-only authority hold')
    return original


def verify_plan(repeat, digest):
    path = BASE / repeat / 'manifest.json'
    if repeat != 'fresh1' or sha(path) != digest or json.loads(path.read_text()) != plan_data(repeat):
        raise ValueError('Versioned high plan or frozen request source changed')
    return json.loads(path.read_text())


def execution_plan():
    frozen.runner.verify_execution_manifest(sha(frozen.runner.EXECUTION_MANIFEST))
    plans = {'fresh1': sha(BASE / 'fresh1/manifest.json')}
    for repeat, digest in plans.items():
        verify_plan(repeat, digest)
    names = ('mistral119_high_plain_authority_v1.py',
             'mistral119_fresh_repeat_execution.py',
             'mistral119_fresh_repeat_study.py',
             'qwen27_fresh_repeat_execution.py',
             'openrouter_benchmark.py', 'openrouter_paid_benchmark.py',
             'prompt_admission.py', 'openrouter_budget_v4.py',
             'paid_budget_partitions_v4.py', 'paid_budget_partitions_v3.py',
             'postapproval_authority_v3.py', 'postapproval_authority_v2.py',
             'openrouter_budget_amendment_v3.py')
    return {'schema': SCHEMA + '-execution', 'status': 'offline_proposal_unapproved',
            'configuration_id': CONFIG, 'original_configuration_id': OLD_CONFIG,
            'plans_sha256': plans, 'controller_sha256': sha(__file__),
            'source_code_sha256': {name: sha(study.ROOT / 'scripts' / name) for name in names},
            'test_sha256': sha(study.ROOT / 'tests/test_mistral119_high_plain_authority_v1.py'),
            'public_route_sha256': sha(ROUTE),
            'parent_terminal_sha256': sha(PARENT_TERMINAL),
            'parent_reconciliation_sha256': sha(PARENT_RECONCILIATION),
            'original_execution_sha256': sha(frozen.runner.EXECUTION_MANIFEST),
            'partition_id': PARTITION_ID, 'child_cap_usd': str(CAP),
            'funding_pool': 'openrouter_additional',
            'per_request_reserve_usd': str(RESERVE),
            'full_series_completion_guaranteed': False,
            'reference_labels_read': False, 'inference_authorized': False}


def prepare():
    if EXECUTION.exists():
        raise FileExistsError('High proposal already exists')
    route_snapshot()
    for repeat in ('fresh1',):
        path = BASE / repeat / 'manifest.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x') as out:
            json.dump(plan_data(repeat), out, indent=2)
            out.write('\n'); out.flush(); os.fsync(out.fileno())
    with EXECUTION.open('x') as out:
        json.dump(execution_plan(), out, indent=2)
        out.write('\n'); out.flush(); os.fsync(out.fileno())
    return sha(EXECUTION)


def verify():
    if json.loads(EXECUTION.read_text()) != execution_plan():
        raise ValueError('Versioned high proposal changed')
    return json.loads(EXECUTION.read_text())


def live_controls(plan, condition):
    if plan.get('configuration_id') != CONFIG or condition != 'P0':
        raise ValueError('Unknown high configuration or condition')
    saved = route_snapshot()
    catalog = paid.fetch('/models', timeout=120)
    endpoints = paid.fetch('/models/' + quote(study.MODEL, safe='/') + '/endpoints', timeout=120)
    model, endpoint = paid.select_endpoint(study.MODEL, PROVIDER, catalog,
                                           endpoints, study.INPUT_PRICE, study.OUTPUT_PRICE)
    check_route(model, endpoint, saved['model'], saved['selected_endpoint'])
    inputs = {row['id']: row['feedback'] for row in study.input_rows()}
    for phase in ('smoke',):
        for request in plan['conditions'][condition][phase]:
            payload = request['payload']
            rebuilt = paid.make_payload(study.MODEL, endpoint,
                inputs[request['record_id']], payload['messages'][0]['content'],
                payload['response_format']['json_schema']['schema'], 'high',
                study.MAX_TOKENS, study.INPUT_PRICE, study.OUTPUT_PRICE, model)
            if rebuilt != payload or study.digest(json.dumps(rebuilt, sort_keys=True)) != request['request_sha256']:
                raise ValueError('Live route would change frozen request bytes')
    return model, endpoint, RESERVE


def hold_source(budget_path):
    return study.digest(json.dumps({'execution_manifest_sha256': sha(EXECUTION),
        'budget_manifest_path': str(Path(budget_path).resolve()),
        'budget_manifest_sha256': sha(budget_path), 'partition_id': PARTITION_ID,
        'cap_usd': str(CAP), 'configuration_id': CONFIG,
        'model': study.MODEL, 'provider': PROVIDER, 'reasoning': 'high'}, sort_keys=True))


def stage_receipt(repeat, condition, phase, budget_path):
    if repeat != 'fresh1' or condition != 'P0' or phase != 'smoke':
        raise ValueError('Stage outside exact high series')
    return {'schema': SCHEMA + '-root-review', 'approved': False,
            'independent_review': False, 'authorized_by_root': False,
            'reviewer': None, 'configuration_id': CONFIG,
            'stage': f'{repeat}/{condition}/{phase}',
            'controller_sha256': sha(__file__),
            'execution_manifest_sha256': sha(EXECUTION),
            'plan_sha256': sha(BASE / repeat / 'manifest.json'),
            'master_ledger': str(MASTER),
            'budget_manifest_path': str(Path(budget_path).resolve()),
            'budget_manifest_sha256': sha(budget_path),
            'partition_id': PARTITION_ID, 'partition_cap_usd': str(CAP),
            'funding_pool': 'openrouter_additional',
            'authority_head_sha256': authority.read_authority(AUTHORITY).head_sha256,
            'authority_hold_source_sha256': hold_source(budget_path)}


def _private_runner():
    spec = importlib.util.spec_from_file_location('_mistral119_high_authority_private',
                                                  frozen.SHARED_SOURCE)
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)
    class BasePath:
        def __truediv__(self, config):
            if config != CONFIG:
                raise ValueError('Unknown high configuration path')
            return BASE
    class Study(frozen._Study):
        BASE = BasePath()
        PROVIDER = PROVIDER
        ORDERS = {'fresh1': ['P0']}
        CONFIGS = {CONFIG: {'effort': 'high', 'historical_continue_on_invalid': False,
                            'proposed_child_budget': CAP}}
        @staticmethod
        def verify(config, repeat, digest):
            if config != CONFIG:
                raise ValueError('Unknown versioned high configuration')
            return verify_plan(repeat, digest)
    core.study = Study
    core.__file__ = __file__
    core.partitions = partitions
    core.EXECUTION_MANIFEST = EXECUTION
    core.CONTINUE_INTRINSIC_INVALID = False
    core.live_controls = live_controls
    def review(path, config, repeat, condition, phase, plan_sha):
        expected_path = BASE / repeat / condition / (phase + '.root-review.json')
        if Path(path).resolve() != expected_path.resolve():
            raise ValueError('Exact high root stage receipt path differs')
        receipt = json.loads(Path(path).read_text())
        budget_path = Path(receipt.get('budget_manifest_path', '')).resolve()
        if budget_path != (BASE / 'budget.json').resolve():
            raise ValueError('Exact high child manifest path differs')
        expected = stage_receipt(repeat, condition, phase, budget_path)
        expected.update(approved=True, independent_review=True,
                        authorized_by_root=True, reviewer='root')
        if config != CONFIG or plan_sha != expected['plan_sha256'] or receipt != expected:
            raise ValueError('Independent high root stage receipt differs')
        verify()
        return receipt, budget_path
    def gate(receipt, budget_path, config):
        if config != CONFIG or Path(budget_path).resolve() != (BASE / 'budget.json').resolve():
            raise ValueError('Exact high child binding differs')
        ledger = partitions.open_partition(MASTER, budget_path, PARTITION_ID,
                                           study.MODEL, PROVIDER, 'high')
        try:
            _, pending, blocked = ledger.state()
            if (ledger.cap != CAP or ledger.master_cap != Decimal('22.38') or
                    pending or blocked or ledger.closed or
                    ledger.accounted() + RESERVE > ledger.cap):
                raise ValueError('High child unavailable before key read')
            with authority.old._locked(AUTHORITY) as handle:
                snapshot, holds = authority._scan(handle.read())
            if snapshot.head_sha256 != receipt['authority_head_sha256']:
                raise ValueError('Authority head changed before high stage')
            held = holds.get(PARTITION_ID)
            if (held is None or held.get('funding_pool') != 'openrouter_additional' or
                    held.get('usd') != str(CAP) or held.get('source_sha256') != hold_source(budget_path) or
                    held.get('budget_manifest_sha256') != sha(budget_path)):
                raise ValueError('Distinct high authority hold absent or mismatched')
            return ledger
        except BaseException:
            ledger.close(); raise
    core.review_receipt = review
    core.budget_gate = gate
    tree = ast.parse(Path(frozen.SHARED_SOURCE).read_text())
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
    p.add_argument('action', choices=('capture-route', 'prepare', 'verify', 'live-check',
                                      'hold-source', 'review-template', 'smoke',
                                      'inspect'))
    p.add_argument('--fresh-pass', choices=('fresh1',), default='fresh1')
    p.add_argument('--condition', choices=('P0',), default='P0')
    p.add_argument('--phase', choices=('smoke',), default='smoke')
    p.add_argument('--env-file')
    p.add_argument('--note')
    args = p.parse_args()
    if args.action == 'capture-route': print(capture_route()); return
    if args.action == 'prepare': print(prepare()); return
    verify()
    if args.action == 'verify': print('verified'); return
    plan = verify_plan(args.fresh_pass, sha(BASE / args.fresh_pass / 'manifest.json'))
    if args.action == 'live-check':
        live_controls(plan, args.condition)
        print('live route passed; no inference'); return
    if args.action == 'hold-source':
        print(hold_source(BASE / 'budget.json')); return
    if args.action == 'review-template':
        print(json.dumps(stage_receipt(args.fresh_pass, args.condition,
                                       args.phase, BASE / 'budget.json'), indent=2)); return
    core = _private_runner()
    digest = sha(BASE / args.fresh_pass / 'manifest.json')
    if args.action == 'inspect':
        if not args.note: p.error('inspect requires --note')
        print(core.inspect(CONFIG, args.fresh_pass, args.condition, digest, args.note)); return
    if args.action != args.phase:
        p.error('action/--phase mismatch')
    review = BASE / args.fresh_pass / args.condition / (args.action + '.root-review.json')
    print(core.execute(CONFIG, args.fresh_pass, args.condition, args.action,
                       digest, review, args.env_file))


if __name__ == '__main__': main()
