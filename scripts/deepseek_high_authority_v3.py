#!/usr/bin/env python3
"""Versioned DeepSeek high fresh series under the OpenRouter-only authority.

Preparation and verification are offline. Allocation and stage approval are
separate root actions; this controller never creates either one automatically.
"""
import argparse
import ast
import base64
from copy import deepcopy
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
from types import FunctionType
from urllib.parse import quote

import deepseek_high_fresh_repeat_execution as frozen
import openrouter_budget_amendment_v3 as amendment
import openrouter_paid_benchmark as paid
import paid_budget_partitions_v4 as partitions
import postapproval_authority_v3 as authority

study = frozen.study
SCHEMA = 'deepseek-high-authority-v3'
CONFIG = study.CONFIG + '-authority-v3-current-price'
BASE = study.ROOT / 'results/repeatability-v1/deepseek-high-authority-v3'
ROUTE = BASE / 'public-route.json'
EXECUTION = BASE / 'execution-manifest.json'
PARTITION_ID = 'deepseek-high-authority-v3-fresh123'
CAP = Decimal('0.90')
INPUT_CEILING = Decimal('0.0495')
OUTPUT_CEILING = Decimal('1.32')
RESERVE = Decimal('0.0573112320')
MASTER = amendment.MASTER
AUTHORITY = amendment.AUTHORITY
MODEL_FIELDS = ('id', 'canonical_slug', 'hugging_face_id', 'context_length', 'architecture', 'reasoning')
ENDPOINT_FIELDS = ('tag', 'provider_name', 'quantization', 'model_id', 'status',
                   'context_length', 'max_prompt_tokens', 'max_completion_tokens',
                   'supported_parameters')
sha = study.sha


def no_previous_dispatch():
    for path in study.BASE.rglob('*'):
        if path.is_file() and path.name not in ('manifest.json', 'execution-manifest.json'):
            raise ValueError('Original fresh series has admission or execution evidence: ' + str(path))


def route_snapshot():
    value = json.loads(ROUTE.read_text())
    if (value.get('schema') != SCHEMA + '-public-route' or
            value.get('source') != 'https://openrouter.ai/api/v1/models/' + study.MODEL + '/endpoints' or
            value.get('inference_sent') is not False):
        raise ValueError('Require exact public, inference-free route snapshot')
    check_route(value['model'], value['selected_endpoint'],
                value['model'], value['selected_endpoint'])
    return value


def check_route(model, endpoint, saved_model, saved_endpoint):
    live_pricing = endpoint['pricing']
    saved_pricing = saved_endpoint['pricing']
    prices_changed = set(live_pricing) != set(saved_pricing)
    if not prices_changed:
        prices_changed = any(
            paid.number(live_pricing[key]) > paid.number(saved_pricing[key])
            if key in ('prompt', 'completion')
            else paid.number(live_pricing[key]) != paid.number(saved_pricing[key])
            for key in live_pricing)
    if (any(model.get(k) != saved_model.get(k) for k in MODEL_FIELDS) or
            any(endpoint.get(k) != saved_endpoint.get(k) for k in ENDPOINT_FIELDS) or
            prices_changed or
            endpoint.get('status') != 0 or endpoint.get('tag') != study.PROVIDER or
            endpoint.get('model_id') != study.MODEL or
            endpoint.get('provider_name') != study.PROVIDER_NAME or
            endpoint.get('quantization') != study.QUANTIZATION or
            paid.reasoning(model, endpoint, study.EFFORT) !=
            {'enabled': True, 'effort': study.EFFORT} or
            paid.reservation(endpoint, study.MAX_TOKENS, INPUT_CEILING, OUTPUT_CEILING) != RESERVE):
        raise ValueError('DeepSeek model, route, price, reasoning or reserve changed')


def plan_data(repeat):
    no_previous_dispatch()
    original = study.BASE / repeat / 'manifest.json'
    value = deepcopy(study.verify(repeat, sha(original)))
    route = route_snapshot()
    model, endpoint = route['model'], route['selected_endpoint']
    inputs = {row['id']: row['feedback'] for row in study.input_rows()}
    for condition in study.CONDITIONS:
        for phase in ('smoke', 'development'):
            for request in value['conditions'][condition][phase]:
                old = request['payload']
                payload = paid.make_payload(study.MODEL, endpoint,
                    inputs[request['record_id']], old['messages'][0]['content'],
                    old['response_format']['json_schema']['schema'], study.EFFORT,
                    study.MAX_TOKENS, INPUT_CEILING, OUTPUT_CEILING, model)
                expected = deepcopy(old)
                expected['provider']['max_price'] = {
                    'prompt': float(INPUT_CEILING), 'completion': float(OUTPUT_CEILING),
                    'request': 0, 'image': 0}
                if payload != expected:
                    raise ValueError('New request differs beyond declared price ceilings')
                request['payload'] = payload
                request['request_sha256'] = study.digest(json.dumps(payload, sort_keys=True))
    value.update(schema=SCHEMA + '-plan', series_id=SCHEMA,
        configuration_id=CONFIG, original_configuration_id=study.CONFIG,
        original_plan_manifest_sha256=sha(original),
        public_route_sha256=sha(ROUTE), aggregate_openrouter_cap_usd='22.38',
        funding_pool='openrouter_additional', partition_id=PARTITION_ID,
        proposed_child_budget_usd=str(CAP),
        input_price_ceiling_usd_per_million=str(INPUT_CEILING),
        output_price_ceiling_usd_per_million=str(OUTPUT_CEILING),
        per_request_reserve_usd=str(RESERVE),
        all_567_request_maximum_usd=str(RESERVE * 567),
        full_series_completion_guaranteed=False,
        dispatch_gate='Independent root stage receipt, v4 child and OR-only v3 hold; '
            'exact live route and full reserve before every call; inspected smoke before development')
    return value


def verify_plan(repeat, expected_sha):
    path = BASE / repeat / 'manifest.json'
    if sha(path) != expected_sha or json.loads(path.read_text()) != plan_data(repeat):
        raise ValueError('Versioned DeepSeek plan or bound sources changed')
    return json.loads(path.read_text())


def execution_plan():
    frozen.runner.verify_execution_manifest(sha(frozen.runner.EXECUTION_MANIFEST))
    plans = {repeat: sha(BASE / repeat / 'manifest.json') for repeat in study.ORDERS}
    for repeat, digest in plans.items():
        verify_plan(repeat, digest)
    names = ('deepseek_high_authority_v3.py', 'deepseek_high_fresh_repeat_execution.py',
             'deepseek_high_fresh_repeat_study.py', 'qwen27_fresh_repeat_execution.py',
             'openrouter_benchmark.py', 'openrouter_paid_benchmark.py', 'prompt_admission.py',
             'openrouter_budget_v4.py', 'paid_budget_partitions_v4.py',
             'paid_budget_partitions_v3.py', 'postapproval_authority_v3.py',
             'postapproval_authority_v2.py', 'openrouter_budget_amendment_v3.py')
    return {'schema': SCHEMA + '-execution', 'status': 'offline_prepared_unapproved',
            'configuration_id': CONFIG, 'original_configuration_id': study.CONFIG,
            'plans_sha256': plans, 'controller_sha256': sha(__file__),
            'source_code_sha256': {name: sha(study.ROOT / 'scripts' / name) for name in names},
            'test_sha256': sha(study.ROOT / 'tests/test_deepseek_high_authority_v3.py'),
            'public_route_sha256': sha(ROUTE), 'partition_id': PARTITION_ID,
            'child_cap_usd': str(CAP), 'funding_pool': 'openrouter_additional',
            'per_request_reserve_usd': str(RESERVE),
            'completion_guaranteed': False, 'reference_labels_read': False,
            'inference_authorized': False}


def prepare():
    if EXECUTION.exists():
        raise FileExistsError('Versioned execution proposal already exists')
    for repeat in study.ORDERS:
        path = BASE / repeat / 'manifest.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x') as out:
            json.dump(plan_data(repeat), out, indent=2, ensure_ascii=False)
            out.write('\n')
    with EXECUTION.open('x') as out:
        json.dump(execution_plan(), out, indent=2)
        out.write('\n')
    return sha(EXECUTION)


def verify():
    if json.loads(EXECUTION.read_text()) != execution_plan():
        raise ValueError('Versioned execution proposal changed')
    return json.loads(EXECUTION.read_text())


def live_controls(plan, condition):
    if plan['configuration_id'] != CONFIG or condition not in study.CONDITIONS:
        raise ValueError('Unknown DeepSeek configuration or condition')
    saved = route_snapshot()
    catalog = paid.fetch('/models', timeout=120)
    endpoints = paid.fetch('/models/' + quote(study.MODEL, safe='/') + '/endpoints', timeout=120)
    model, endpoint = paid.select_endpoint(study.MODEL, study.PROVIDER, catalog,
                                           endpoints, INPUT_CEILING, OUTPUT_CEILING)
    check_route(model, endpoint, saved['model'], saved['selected_endpoint'])
    inputs = {row['id']: row['feedback'] for row in study.input_rows()}
    for phase in ('smoke', 'development'):
        for request in plan['conditions'][condition][phase]:
            old = request['payload']
            rebuilt = paid.make_payload(study.MODEL, endpoint,
                inputs[request['record_id']], old['messages'][0]['content'],
                old['response_format']['json_schema']['schema'], study.EFFORT,
                study.MAX_TOKENS, INPUT_CEILING, OUTPUT_CEILING, model)
            if rebuilt != old or study.digest(json.dumps(rebuilt, sort_keys=True)) != request['request_sha256']:
                raise ValueError('Live request payload differs from versioned plan')
    return model, endpoint, RESERVE


def global_hold_source(budget_path):
    return study.digest(json.dumps({'execution_manifest_sha256': sha(EXECUTION),
        'budget_manifest_path': str(Path(budget_path).resolve()),
        'budget_manifest_sha256': sha(budget_path), 'partition_id': PARTITION_ID,
        'cap_usd': str(CAP), 'configuration_id': CONFIG, 'model': study.MODEL,
        'provider': study.PROVIDER, 'reasoning': study.EFFORT}, sort_keys=True))


def stage_receipt(repeat, condition, phase, budget_path):
    return {'schema': SCHEMA + '-root-review', 'approved': False,
        'independent_review': False, 'authorized_by_root': False, 'reviewer': None,
        'configuration_id': CONFIG, 'stage': f'{repeat}/{condition}/{phase}',
        'controller_sha256': sha(__file__), 'execution_manifest_sha256': sha(EXECUTION),
        'plan_sha256': sha(BASE / repeat / 'manifest.json'),
        'master_ledger': str(MASTER), 'budget_manifest_path': str(Path(budget_path).resolve()),
        'budget_manifest_sha256': sha(budget_path), 'partition_id': PARTITION_ID,
        'partition_cap_usd': str(CAP), 'funding_pool': 'openrouter_additional',
        'global_authority_head_sha256': authority.read_authority(AUTHORITY).head_sha256,
        'global_hold_source_sha256': global_hold_source(budget_path)}


def _private_runner():
    spec = importlib.util.spec_from_file_location('_deepseek_high_authority_private', frozen.SHARED_SOURCE)
    core = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(core)

    class BasePath:
        def __truediv__(self, config):
            if config != CONFIG:
                raise ValueError('Unknown versioned configuration path')
            return BASE

    class Study(frozen._Study):
        CONFIG = CONFIG
        BASE = BasePath()
        ROUTE_AUDIT = str(ROUTE.relative_to(study.ROOT))
        CONFIGS = {CONFIG: {'effort': study.EFFORT,
                            'historical_continue_on_invalid': True,
                            'proposed_child_budget': CAP}}

        @staticmethod
        def verify(config, repeat, digest):
            if config != CONFIG:
                raise ValueError('Unknown versioned DeepSeek configuration')
            return verify_plan(repeat, digest)

    core.study = Study
    core.__file__ = __file__
    core.partitions = partitions
    core.EXECUTION_MANIFEST = EXECUTION
    core.RECEIPT_SCHEMA = SCHEMA + '-root-review'
    core.CONTINUE_INTRINSIC_INVALID = True
    core.execution_plan = execution_plan
    core.live_controls = live_controls
    strict = core.verify_phase_closure
    closure_globals = dict(frozen.verify_phase_closure.__globals__,
                           study=Study, runner=core, _strict_closure=strict)
    core.verify_phase_closure = FunctionType(frozen.verify_phase_closure.__code__,
                                             closure_globals)

    def review(path, config, repeat, condition, phase, manifest_sha):
        expected_path = BASE / repeat / condition / (phase + '.root-review.json')
        if Path(path).resolve() != expected_path.resolve():
            raise ValueError('Exact root stage receipt path differs')
        receipt = json.loads(Path(path).read_text())
        budget = Path(receipt.get('budget_manifest_path', '')).resolve()
        if budget != (BASE / 'budget.json').resolve():
            raise ValueError('Exact shared child manifest path differs')
        expected = stage_receipt(repeat, condition, phase, budget)
        expected.update(approved=True, independent_review=True,
                        authorized_by_root=True, reviewer='root')
        if config != CONFIG or manifest_sha != expected['plan_sha256'] or receipt != expected:
            raise ValueError('Independent root stage receipt differs')
        verify()
        return receipt, budget

    def gate(receipt, budget_path, config):
        ledger = partitions.open_partition(MASTER, budget_path, PARTITION_ID,
                                           study.MODEL, study.PROVIDER, study.EFFORT)
        try:
            _, pending, blocked = ledger.state()
            if (ledger.cap != CAP or ledger.master_cap != Decimal('22.38') or
                    pending or blocked or ledger.closed):
                raise ValueError('Exact child is blocked, pending, closed or misbound')
            if ledger.accounted() + RESERVE > ledger.cap:
                raise ValueError('Insufficient child capacity before stage; no request sent')
            with authority.old._locked(AUTHORITY) as handle:
                snapshot, holds = authority._scan(handle.read())
            if snapshot.head_sha256 != receipt['global_authority_head_sha256']:
                raise ValueError('Authority head changed before child admission')
            source = global_hold_source(budget_path)
            if PARTITION_ID in holds:
                event = holds[PARTITION_ID]
                if (event.get('funding_pool') != 'openrouter_additional' or
                        event.get('usd') != str(CAP) or event.get('source_sha256') != source or
                        event.get('budget_manifest_sha256') != sha(budget_path)):
                    raise ValueError('Existing whole-series authority hold differs')
            else:
                authority.hold_authority(AUTHORITY, PARTITION_ID, str(CAP), source,
                    snapshot.head_sha256, stage_path=BASE/'fresh1/P0/smoke.claim.json',
                    funding_pool='openrouter_additional', budget_path=budget_path,
                    partition_id=PARTITION_ID)
            return ledger
        except BaseException:
            ledger.close()
            raise

    core.review_receipt = review
    core.budget_gate = gate
    tree = ast.parse(Path(frozen.SHARED_SOURCE).read_text())
    execute = next(node for node in tree.body
                   if isinstance(node, ast.FunctionDef) and node.name == 'execute')
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify', 'live-check',
                                           'smoke', 'development', 'inspect'))
    parser.add_argument('--fresh-pass', choices=tuple(study.ORDERS), default='fresh1')
    parser.add_argument('--condition', choices=study.CONDITIONS, default='P0')
    parser.add_argument('--review', type=Path)
    parser.add_argument('--env-file')
    parser.add_argument('--note')
    args = parser.parse_args()
    if args.action == 'prepare':
        print(prepare()); return
    verify()
    digest = sha(BASE / args.fresh_pass / 'manifest.json')
    if args.action == 'verify':
        print('verified'); return
    plan = verify_plan(args.fresh_pass, digest)
    if args.action == 'live-check':
        live_controls(plan, args.condition)
        print('live route passed; no inference'); return
    core = _private_runner()
    if args.action == 'inspect':
        if not args.note:
            parser.error('inspect requires a raw-outcome inspection note')
        print(core.inspect(CONFIG, args.fresh_pass, args.condition, digest, args.note))
    elif args.review:
        print(core.execute(CONFIG, args.fresh_pass, args.condition,
                           args.action, digest, args.review, args.env_file))
    else:
        parser.error('smoke/development require independent --review')


if __name__ == '__main__':
    main()
