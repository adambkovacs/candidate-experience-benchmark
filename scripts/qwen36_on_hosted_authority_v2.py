#!/usr/bin/env python3
"""Separate Qwen3.6 ON matched-three bridge to the reviewed OR-only authority.

$1.50 is a sequential child, not a guarantee that all 567 requests fit.
No automatic allocation, review, replenishment, retries or authority release.
"""
import argparse
import ast
from copy import deepcopy
from decimal import Decimal
import importlib.util
import json
from pathlib import Path
from urllib.parse import quote
import qwen36_on_fresh_repeat_execution as frozen
import openrouter_paid_benchmark as paid
import openrouter_budget_amendment_v3 as amendment
import paid_budget_partitions_v4 as partitions
import postapproval_authority_v3 as authority

study = frozen.study
SCHEMA = 'qwen36-on-hosted-authority-v2'
CONFIG = study.CONFIG + '-authority-v3-hosted-v2'
BASE = study.ROOT / 'results/repeatability-v1/qwen36-on-hosted-authority-v3-v2'
EXECUTION = BASE / 'execution-manifest.json'
ROUTE = BASE / 'public-route.json'
PARTITION_ID = 'qwen36-on-hosted-authority-v2-fresh123'
CAP = Decimal('1.50')
RESERVE = Decimal('0.0299008')
MASTER = amendment.MASTER
AUTHORITY = amendment.AUTHORITY
MODEL_FIELDS = ('id', 'canonical_slug', 'hugging_face_id', 'context_length', 'architecture', 'reasoning')
ENDPOINT_FIELDS = ('tag', 'provider_name', 'quantization', 'model_id', 'context_length',
                   'max_prompt_tokens', 'max_completion_tokens', 'supported_parameters')
sha = study.sha


def no_previous_dispatch():
    # The predecessor is a plan, never a source of fresh results.
    for path in study.BASE.rglob('*'):
        if path.is_file() and path.name != 'manifest.json' and path.name != 'execution-manifest.json':
            raise ValueError('Original planned series has new admission/execution evidence: ' + str(path))


def plan_data(repeat):
    no_previous_dispatch()
    original = study.BASE / repeat / 'manifest.json'
    value = deepcopy(study.verify(repeat, sha(original)))
    value.update(schema=SCHEMA + '-plan', series_id=SCHEMA, configuration_id=CONFIG,
        original_configuration_id=study.CONFIG, original_plan_manifest_sha256=sha(original),
        aggregate_openrouter_cap_usd='22.38', global_shared_cap_usd='10.00',
        global_openrouter_additional_cap_usd='10.00', funding_pool='openrouter_additional',
        partition_id=PARTITION_ID, proposed_child_budget_usd=str(CAP),
        full_series_completion_guaranteed=False,
        dispatch_gate='Root stage review, exact live route, allocated v4 child and OR-only v3 hold; '
            'sequential full reserve/known settle; explicit insufficient-capacity stop; inspect smoke before development')
    return value


def verify_plan(repeat, expected_sha):
    path = BASE / repeat / 'manifest.json'
    if sha(path) != expected_sha or json.loads(path.read_text()) != plan_data(repeat):
        raise ValueError('Hosted authority plan or frozen historical sources changed')
    return json.loads(path.read_text())


def route_snapshot():
    value = json.loads(ROUTE.read_text())
    if value.get('inference_sent') is not False or value.get('source') != 'https://openrouter.ai/api/v1/models/' + study.MODEL + '/endpoints':
        raise ValueError('Require exact public read-only route snapshot')
    old = study.source_rows('P0')['DEV-001']
    check_route(value['model'], value['endpoint'], old['model_catalog_entry'], old['provider_endpoint'])
    return value


def check_route(model, endpoint, saved_model, saved):
    if (any(model.get(k) != saved_model.get(k) for k in MODEL_FIELDS) or
            any(endpoint.get(k) != saved.get(k) for k in ENDPOINT_FIELDS) or endpoint.get('status') != 0 or
            set(endpoint['pricing']) != set(saved['pricing']) or
            any(paid.number(endpoint['pricing'][k]) != paid.number(saved['pricing'][k]) for k in saved['pricing']) or
            paid.reasoning(model, endpoint, 'on') != {'enabled': True} or
            paid.reservation(endpoint, study.MAX_TOKENS, study.INPUT_PRICE, study.OUTPUT_PRICE) != RESERVE):
        raise ValueError('Exact Qwen model, route, interface, reasoning, price or reserve changed')


def execution_plan():
    # Validate the complete frozen planner/executor/test chain before bridging it.
    frozen.runner.verify_execution_manifest(sha(frozen.runner.EXECUTION_MANIFEST))
    plans = {r: sha(BASE / r / 'manifest.json') for r in study.ORDERS}
    for repeat, digest in plans.items(): verify_plan(repeat, digest)
    route_snapshot()
    names = ('qwen36_on_hosted_authority_v2.py', 'qwen36_on_fresh_repeat_execution.py',
        'qwen36_on_fresh_repeat_study.py', 'qwen27_fresh_repeat_execution.py',
        'openrouter_benchmark.py', 'openrouter_paid_benchmark.py', 'prompt_admission.py',
        'openrouter_budget_v4.py', 'paid_budget_partitions_v4.py', 'paid_budget_partitions_v3.py',
        'postapproval_authority_v3.py', 'postapproval_authority_v2.py', 'openrouter_budget_amendment_v3.py')
    return {'schema': SCHEMA + '-execution', 'status': 'offline_prepared_unapproved',
        'configuration_id': CONFIG, 'original_configuration_id': study.CONFIG,
        'plans_sha256': plans, 'controller_sha256': sha(__file__),
        'source_code_sha256': {n: sha(study.ROOT / 'scripts' / n) for n in names},
        'test_sha256': sha(study.ROOT / 'tests/test_qwen36_on_hosted_authority_v2.py'),
        'public_route_sha256': sha(ROUTE), 'authority_amendment_proposal_sha256': sha(amendment.BASE / 'proposal.json'),
        'partition_id': PARTITION_ID, 'child_cap_usd': str(CAP), 'funding_pool': 'openrouter_additional',
        'per_request_reserve_usd': str(RESERVE), 'all_calls_maximum_usd': '16.9537536',
        'historical_proxy_plus_unknown_sensitivity_usd': '1.2408645',
        'completion_guaranteed': False, 'capacity_policy': 'Before each request, accounted + full reserve <= child cap; otherwise stop before dispatch',
        'invalid_output_policy': 'Stop and preserve; frozen ON plans do not permit continuation',
        'reference_labels_read': False, 'inference_authorized': False}


def prepare():
    if EXECUTION.exists(): raise FileExistsError('Execution proposal already exists')
    for repeat in study.ORDERS:
        path = BASE / repeat / 'manifest.json'; path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('x') as f: json.dump(plan_data(repeat), f, indent=2); f.write('\n')
    with EXECUTION.open('x') as f: json.dump(execution_plan(), f, indent=2); f.write('\n')
    with (BASE / 'root-review-candidate.json').open('x') as f:
        json.dump({'schema': SCHEMA + '-design-root-review', 'approved': False,
            'independent_review': False, 'authorized_by_root': False, 'reviewer': None,
            'execution_manifest_sha256': sha(EXECUTION), 'controller_sha256': sha(__file__),
            'inference_authorized': False}, f, indent=2); f.write('\n')
    return sha(EXECUTION)


def verify():
    if json.loads(EXECUTION.read_text()) != execution_plan(): raise ValueError('Execution proposal changed')
    return json.loads(EXECUTION.read_text())


def live_controls(plan, condition):
    if plan['configuration_id'] != CONFIG or condition not in study.CONDITIONS:
        raise ValueError('Unknown configuration or condition')
    snapshot = route_snapshot()
    catalog = paid.fetch('/models', timeout=120)
    endpoints = paid.fetch('/models/' + quote(study.MODEL, safe='/') + '/endpoints', timeout=120)
    model, endpoint = paid.select_endpoint(study.MODEL, study.PROVIDER, catalog, endpoints,
                                           study.INPUT_PRICE, study.OUTPUT_PRICE)
    check_route(model, endpoint, snapshot['model'], snapshot['endpoint'])
    inputs = {r['id']: r['feedback'] for r in study.input_rows()}
    for request in plan['conditions'][condition]['development']:
        payload = request['payload']
        rebuilt = paid.make_payload(study.MODEL, endpoint, inputs[request['record_id']],
            payload['messages'][0]['content'], payload['response_format']['json_schema']['schema'],
            'on', study.MAX_TOKENS, study.INPUT_PRICE, study.OUTPUT_PRICE, model)
        if rebuilt != payload or study.digest(json.dumps(rebuilt, sort_keys=True)) != request['request_sha256']:
            raise ValueError('Live request payload changed')
    return model, endpoint, RESERVE


def global_hold_source(budget_path):
    return study.digest(json.dumps({'execution_manifest_sha256': sha(EXECUTION),
        'budget_manifest_path': str(Path(budget_path).resolve()), 'budget_manifest_sha256': sha(budget_path),
        'partition_id': PARTITION_ID, 'cap_usd': str(CAP), 'configuration_id': CONFIG,
        'model': study.MODEL, 'provider': study.PROVIDER, 'reasoning': 'on'}, sort_keys=True))


def stage_receipt(repeat, condition, phase, budget_path):
    return {'schema': SCHEMA + '-root-review', 'approved': False, 'independent_review': False,
        'authorized_by_root': False, 'reviewer': None, 'configuration_id': CONFIG,
        'stage': f'{repeat}/{condition}/{phase}', 'controller_sha256': sha(__file__),
        'execution_manifest_sha256': sha(EXECUTION), 'plan_sha256': sha(BASE / repeat / 'manifest.json'),
        'master_ledger': str(MASTER), 'budget_manifest_path': str(Path(budget_path).resolve()),
        'budget_manifest_sha256': sha(budget_path), 'partition_id': PARTITION_ID,
        'partition_cap_usd': str(CAP), 'funding_pool': 'openrouter_additional',
        'global_authority_head_sha256': authority.read_authority(AUTHORITY).head_sha256,
        'global_hold_source_sha256': global_hold_source(budget_path)}


def _private_runner():
    spec = importlib.util.spec_from_file_location('_qwen36_authority_private', frozen.SHARED_SOURCE)
    core = importlib.util.module_from_spec(spec); spec.loader.exec_module(core)
    class BasePath:
        def __truediv__(self, config):
            if config != CONFIG: raise ValueError('Unknown configuration path')
            return BASE
    class Study(frozen._Study):
        BASE = BasePath()
        CONFIGS = {CONFIG: {'effort': 'on', 'historical_continue_on_invalid': False,
                            'proposed_child_budget': CAP}}
        @staticmethod
        def verify(config, repeat, digest):
            if config != CONFIG: raise ValueError('Unknown configuration')
            return verify_plan(repeat, digest)
    core.study = Study; core.__file__ = __file__; core.partitions = partitions
    core.EXECUTION_MANIFEST = EXECUTION; core.live_controls = live_controls

    def review(path, config, repeat, condition, phase, manifest_sha):
        expected_path = BASE / repeat / condition / (phase + '.root-review.json')
        if Path(path).resolve() != expected_path.resolve(): raise ValueError('Exact root stage receipt path differs')
        receipt = json.loads(Path(path).read_text())
        budget = Path(receipt.get('budget_manifest_path', '')).resolve()
        if budget != (BASE / 'budget.json').resolve(): raise ValueError('Exact shared child manifest path differs')
        expected = stage_receipt(repeat, condition, phase, budget)
        expected.update(approved=True, independent_review=True, authorized_by_root=True, reviewer='root')
        if config != CONFIG or manifest_sha != expected['plan_sha256'] or receipt != expected:
            raise ValueError('Independent root stage receipt differs')
        verify()
        return receipt, budget

    def gate(receipt, budget_path, config):
        ledger = partitions.open_partition(MASTER, budget_path, PARTITION_ID, study.MODEL, study.PROVIDER, 'on')
        try:
            _, pending, blocked = ledger.state()
            if ledger.cap != CAP or ledger.master_cap != Decimal('22.38') or pending or blocked or ledger.closed:
                raise ValueError('Exact child is blocked, pending, closed or misbound')
            if ledger.accounted() + RESERVE > ledger.cap:
                raise ValueError('Insufficient child capacity before stage; no key or request loaded')
            with authority.old._locked(AUTHORITY) as handle:
                snapshot, holds = authority._scan(handle.read())
            if snapshot.head_sha256 != receipt['global_authority_head_sha256']:
                raise ValueError('Authority head changed before child admission')
            source = global_hold_source(budget_path)
            if PARTITION_ID in holds:
                event = holds[PARTITION_ID]
                if (event.get('funding_pool') != 'openrouter_additional' or event.get('usd') != str(CAP) or
                        event.get('source_sha256') != source or event.get('budget_manifest_sha256') != sha(budget_path)):
                    raise ValueError('Existing whole-series hold differs')
            else:
                authority.hold_authority(AUTHORITY, PARTITION_ID, str(CAP), source, snapshot.head_sha256,
                    stage_path=BASE/'fresh1/P0/smoke.claim.json', funding_pool='openrouter_additional',
                    budget_path=budget_path, partition_id=PARTITION_ID)
            return ledger
        except BaseException:
            ledger.close(); raise
    core.review_receipt = review; core.budget_gate = gate
    # Preserve the frozen execution function except for the explicit pre-reserve
    # capacity terminal. A child reservation remains the final money guard.
    tree = ast.parse(Path(frozen.SHARED_SOURCE).read_text())
    execute = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'execute')
    needle = ast.dump(ast.parse('attempt_id = ledger.reserve(reserve, rid)').body[0])
    count = 0
    class CapacityGate(ast.NodeTransformer):
        def visit_Assign(self, node):
            nonlocal count
            if ast.dump(node) != needle: return node
            count += 1
            check = ast.parse("if ledger.accounted() + reserve > ledger.cap:\n"
                "    durable(audit, {'event': 'phase_stopped', 'next_unsent_id': rid, 'reason': 'insufficient_capacity', 'utc': utc()})\n"
                "    return False\n").body[0]
            return [check, node]
    execute = CapacityGate().visit(execute)
    if count != 1: raise ValueError('Frozen sequential reserve control changed')
    isolated = ast.Module(body=[execute], type_ignores=[]); ast.fix_missing_locations(isolated)
    exec(compile(isolated, __file__, 'exec'), core.__dict__)
    return core


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify', 'live-check', 'smoke', 'development', 'inspect'))
    parser.add_argument('--fresh-pass', choices=tuple(study.ORDERS), default='fresh1')
    parser.add_argument('--condition', choices=study.CONDITIONS, default='P0')
    parser.add_argument('--review', type=Path); parser.add_argument('--env-file'); parser.add_argument('--note')
    args = parser.parse_args()
    if args.action == 'prepare': print(prepare()); return
    verify(); plan_path = BASE / args.fresh_pass / 'manifest.json'; digest = sha(plan_path)
    if args.action == 'verify': print('verified'); return
    plan = verify_plan(args.fresh_pass, digest)
    if args.action == 'live-check': live_controls(plan, args.condition); print('live route passed; no inference'); return
    core = _private_runner()
    if args.action == 'inspect':
        if not args.note: parser.error('inspect requires a raw-outcome inspection note')
        print(core.inspect(CONFIG, args.fresh_pass, args.condition, digest, args.note))
    elif args.review:
        print(core.execute(CONFIG, args.fresh_pass, args.condition, args.action, digest, args.review, args.env_file))
    else: parser.error('smoke/development require independent --review')


if __name__ == '__main__': main()
