#!/usr/bin/env python3
"""Offline, unadmitted eight-stage plain-Mistral high repeat proposal."""
import argparse
from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import tempfile

import mistral119_high_plain_authority_v1 as old
import mistral119_high_plain_unsent_v4 as diagnostic
import openrouter_paid_benchmark as paid
import openrouter_authority_release_v4 as authority

ROOT = old.study.ROOT
SCHEMA = 'mistral119-high-plain-remaining8-v4'
CONFIG = old.CONFIG + '-remaining8-v4'
BASE = old.BASE / 'remaining8-v4'
MANIFEST = BASE / 'proposal.json'
PROOF = BASE / 'source-proof.json'
PASSES = ('fresh1', 'fresh2', 'fresh3')
PHASES = (('fresh1', 'P1'), ('fresh1', 'P2'),
          ('fresh2', 'P1'), ('fresh2', 'P2'), ('fresh2', 'P0'),
          ('fresh3', 'P2'), ('fresh3', 'P0'), ('fresh3', 'P1'))
ORDERS = {repeat: [condition for r, condition in PHASES if r == repeat]
          for repeat in PASSES}
PARTITION_ID = SCHEMA
CHILD_CAP = Decimal('0.75')
RESERVE = old.RESERVE


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relative(path):
    return str(Path(path).resolve().relative_to(ROOT.resolve()))


def original_path(repeat):
    return old.study.BASE / old.OLD_CONFIG / repeat / 'manifest.json'


def source_proof_data():
    """Prepare-only receipt: all private historical bytes are present here."""
    diagnostic.verify()
    old.route_snapshot()
    plans = {}
    missing_sources = {}
    historical = set(old.study.CONFIGS[old.OLD_CONFIG]['historical_smokes'])
    for repeat in PASSES:
        source = original_path(repeat)
        original = old.study.verify(old.OLD_CONFIG, repeat, sha(source))
        bindings = {b['path']: b['sha256'] for b in original['source_bindings']}
        if not historical <= bindings.keys():
            raise ValueError('Historical Mistral source bindings differ')
        plans[repeat] = sha(source)
        missing_sources[repeat] = {name: bindings[name] for name in sorted(historical)}
    return {'schema': SCHEMA + '-full-source-proof',
        'full_local_verification_passed': True,
        'verification_boundary': 'Historical smoke bytes checked during prepare; '
            'clean checkout verifies their archived hashes, not absent raw bytes.',
        'original_plans_sha256': plans,
        'historical_smoke_sha256': missing_sources,
        'plain_route_sha256': sha(old.ROUTE),
        'plain_execution_sha256': sha(old.EXECUTION),
        'diagnostic_proposal_sha256': sha(diagnostic.PROPOSAL),
        'diagnostic_plan_sha256': sha(diagnostic.PLAN),
        'parent_terminal_sha256': sha(old.BASE / 'terminal-public.json'),
        'parent_reconciliation_sha256': sha(old.BASE / 'reconciliation.json')}


def portable_sources():
    proof = json.loads(PROOF.read_text())
    if (proof.get('schema') != SCHEMA + '-full-source-proof' or
            proof.get('full_local_verification_passed') is not True or
            set(proof.get('original_plans_sha256', {})) != set(PASSES) or
            proof.get('plain_route_sha256') != sha(old.ROUTE) or
            proof.get('plain_execution_sha256') != sha(old.EXECUTION) or
            proof.get('diagnostic_proposal_sha256') != sha(diagnostic.PROPOSAL) or
            proof.get('diagnostic_plan_sha256') != sha(diagnostic.PLAN) or
            proof.get('parent_terminal_sha256') != sha(old.BASE / 'terminal-public.json') or
            proof.get('parent_reconciliation_sha256') != sha(old.BASE / 'reconciliation.json')):
        raise ValueError('Archived full-source proof or tracked evidence differs')
    terminal = json.loads((old.BASE / 'terminal-public.json').read_text())
    reconciliation = json.loads((old.BASE / 'reconciliation.json').read_text())
    if (terminal.get('stage') != 'fresh1/P0/smoke' or
            terminal.get('attempted_ids') != ['DEV-001'] or
            terminal.get('never_sent_smoke_ids') != ['DEV-002', 'DEV-003'] or
            terminal.get('http_status') != 429 or terminal.get('valid_count') != 0 or
            terminal.get('unknown_cost_upper_bound_usd') != str(RESERVE) or
            reconciliation.get('event') != 'partition_reconciled' or
            reconciliation.get('unknown_upper_bound_usd') != str(RESERVE)):
        raise ValueError('Interrupted plain Mistral predecessor differs')
    suffix = json.loads(diagnostic.PROPOSAL.read_text())
    suffix_plan = json.loads(diagnostic.PLAN.read_text())
    if (suffix.get('status') != 'offline_unadmitted' or
            suffix.get('no_retry_ids') != ['DEV-001'] or
            suffix.get('never_sent_ids') != ['DEV-002', 'DEV-003'] or
            suffix.get('plan_sha256') != sha(diagnostic.PLAN) or
            [x.get('record_id') for x in suffix_plan.get('smoke_requests', [])] !=
            ['DEV-002', 'DEV-003'] or
            suffix.get('allocation_authorized') is not False or
            suffix.get('dispatch_authorized') is not False):
        raise ValueError('Separate two-request diagnostic differs')
    for name, digest in suffix.get('source_bindings', {}).items():
        path = (ROOT / name).resolve()
        path.relative_to(ROOT.resolve())
        if path.is_file() and sha(path) != digest:
            raise ValueError('Present diagnostic source differs: ' + name)
    return proof


def portable_original(repeat, proof):
    source = original_path(repeat)
    if proof['original_plans_sha256'][repeat] != sha(source):
        raise ValueError('Archived original Mistral plan differs')
    original = json.loads(source.read_text())
    if (original.get('schema') != 'hosted-fresh-matched-three-plan-v1' or
            original.get('configuration_id') != old.OLD_CONFIG or
            original.get('fresh_pass') != repeat or
            original.get('condition_order') != old.study.ORDERS[repeat] or
            original.get('model') != old.study.MODEL or
            original.get('provider_tag') != old.study.PROVIDER or
            original.get('reasoning_effort') != 'high'):
        raise ValueError('Archived original Mistral plan controls differ')
    bindings = {b['path']: b['sha256'] for b in original['source_bindings']}
    if len(bindings) != len(original['source_bindings']):
        raise ValueError('Duplicate original Mistral source binding')
    historical = set(old.study.CONFIGS[old.OLD_CONFIG]['historical_smokes'])
    if {name: bindings.get(name) for name in sorted(historical)} != \
            proof['historical_smoke_sha256'][repeat]:
        raise ValueError('Archived private historical hash proof differs')
    for name, digest in bindings.items():
        path = (ROOT / name).resolve()
        path.relative_to(ROOT.resolve())
        if path.is_file():
            if sha(path) != digest:
                raise ValueError('Present original Mistral source differs: ' + name)
        elif name not in historical:
            raise ValueError('Required archived original source absent: ' + name)
    return original


def portable_route(proof):
    route = json.loads(old.ROUTE.read_text())
    if (proof['plain_route_sha256'] != sha(old.ROUTE) or
            route.get('schema') != old.SCHEMA + '-public-route' or
            route.get('inference_sent') is not False or
            route.get('requested_endpoint_count') != 1 or
            route.get('source') != 'https://openrouter.ai/api/v1/models/' +
            old.study.MODEL + '/endpoints'):
        raise ValueError('Archived plain Mistral public route differs')
    old.check_route(route['model'], route['selected_endpoint'],
                    route['model'], route['selected_endpoint'])
    return route


def request_copy(request, endpoint, model, inputs):
    before = request['payload']
    rebuilt = paid.make_payload(old.study.MODEL, endpoint,
        inputs[request['record_id']], before['messages'][0]['content'],
        before['response_format']['json_schema']['schema'], 'high',
        old.study.MAX_TOKENS, old.study.INPUT_PRICE, old.study.OUTPUT_PRICE, model)
    expected = deepcopy(before)
    expected['provider']['only'] = [old.PROVIDER]
    if (rebuilt != expected or request['request_sha256'] !=
            old.study.digest(json.dumps(before, sort_keys=True))):
        raise ValueError('Plain route may change only frozen provider tag')
    changed = deepcopy(request)
    changed['payload'] = rebuilt
    changed['request_sha256'] = old.study.digest(json.dumps(rebuilt, sort_keys=True))
    return changed


def plan_data(repeat):
    if repeat not in PASSES:
        raise ValueError('Unknown plain Mistral repeat')
    proof = portable_sources()
    source = original_path(repeat)
    original = deepcopy(portable_original(repeat, proof))
    route = portable_route(proof)
    inputs = {row['id']: row['feedback'] for row in old.study.input_rows()}
    if original['condition_order'] != old.study.ORDERS[repeat]:
        raise ValueError('Original Mistral condition order differs')
    conditions = {}
    for condition in ORDERS[repeat]:
        entry = deepcopy(original['conditions'][condition])
        for phase, count in (('smoke', 3), ('development', 60)):
            if len(entry[phase]) != count:
                raise ValueError('Original Mistral stage count differs')
            entry[phase] = [request_copy(row, route['selected_endpoint'],
                                         route['model'], inputs) for row in entry[phase]]
            if [row['record_id'] for row in entry[phase]] != [
                    f'DEV-{i:03}' for i in range(1, count + 1)]:
                raise ValueError('Original Mistral stage IDs differ')
        conditions[condition] = entry
    original.update(schema=SCHEMA + '-plan', series_id=SCHEMA,
        configuration_id=CONFIG, original_configuration_id=old.OLD_CONFIG,
        provider_tag=old.PROVIDER, condition_order=ORDERS[repeat],
        conditions=conditions, development_count_per_condition=60,
        planned_request_count=len(ORDERS[repeat]) * 63,
        execution_status='offline_eight_unopened_stages_unadmitted',
        interrupted_predecessor='fresh1/P0 plain-route smoke DEV-001 HTTP 429; '
            'DEV-002/003 are a separate diagnostic proposal; no outcome transfers',
        original_plan_manifest_sha256=sha(source),
        public_route_sha256=sha(old.ROUTE),
        parent_terminal_sha256=sha(old.BASE / 'terminal-public.json'),
        parent_reconciliation_sha256=sha(old.BASE / 'reconciliation.json'),
        diagnostic_proposal_sha256=sha(diagnostic.PROPOSAL),
        aggregate_openrouter_cap_usd='22.38',
        funding_pool='openrouter_additional',
        partition_id=PARTITION_ID,
        proposed_child_budget_usd=str(CHILD_CAP),
        per_request_reserve_usd=str(RESERVE),
        full_series_completion_guaranteed=False,
        dispatch_gate='Each new stage needs root review, exact v4 child and hold, '
            'live plain route check, strict three-call smoke inspection, then '
            'sequential reserve for up to 60 development calls; stop at capacity')
    original['budget_estimate'] = {
        'maximum_per_request_reserve_usd': str(RESERVE),
        'proposed_child_cap_usd': str(CHILD_CAP),
        'planned_stage_count': 8,
        'planned_request_count': 8 * 63,
        'simultaneous_worst_case_reservation_usd': str(RESERVE * 8 * 63),
        'allocation_policy': 'One child; sequential reservations only; no top-up'}
    return original


def verify_plan(repeat, digest):
    target = BASE / repeat / 'manifest.json'
    if sha(target) != digest or json.loads(target.read_text()) != plan_data(repeat):
        raise ValueError('Plain Mistral remaining-stage plan differs')
    return json.loads(target.read_text())


def source_paths():
    names = ('mistral119_high_plain_remaining8_v4.py',
             'mistral119_high_plain_remaining8_v4_execution.py',
             'mistral119_high_plain_authority_v1.py',
             'mistral119_high_plain_unsent_v4.py',
             'mistral119_fresh_repeat_execution.py',
             'mistral119_fresh_repeat_study.py',
             'qwen27_fresh_repeat_execution.py',
             'openrouter_benchmark.py', 'openrouter_paid_benchmark.py',
             'prompt_admission.py', 'development_benchmark.py',
             'frozen_prompt_variants.py',
             'openrouter_authority_release_v4.py',
             'postapproval_authority_v3.py', 'postapproval_authority_v2.py',
             'openrouter_budget_amendment_v3.py',
             'openrouter_budget_v4.py', 'openrouter_budget_v3.py',
             'paid_budget_partitions_v4.py', 'paid_budget_partitions_v3.py')
    paths = [ROOT / 'scripts' / name for name in names]
    paths += [ROOT / 'tests/test_mistral119_high_plain_remaining8_v4.py',
              old.ROUTE, old.EXECUTION, diagnostic.PROPOSAL,
              old.BASE / 'terminal-public.json', old.BASE / 'reconciliation.json',
             old.BASE / ('budget-' + old.PARTITION_ID + '.jsonl'), PROOF,
             diagnostic.PLAN]
    paths += [original_path(repeat) for repeat in PASSES]
    return paths


def proposal_data(plans):
    portable_sources()
    for repeat, digest in plans.items():
        verify_plan(repeat, digest)
    return {'schema': SCHEMA + '-proposal',
        'status': 'offline_unadmitted',
        'configuration_id': CONFIG,
        'original_configuration_id': old.OLD_CONFIG,
        'provider': old.PROVIDER,
        'model': old.study.MODEL,
        'reasoning_effort': 'high',
        'stages': [f'{repeat}/{condition}' for repeat, condition in PHASES],
        'excluded_interrupted_stage': 'fresh1/P0',
        'separate_diagnostic_proposal_sha256': sha(diagnostic.PROPOSAL),
        'full_source_proof_sha256': sha(PROOF),
        'previous_unknown_cost_upper_bound_usd': str(RESERVE),
        'plans_sha256': plans,
        'partition_id': PARTITION_ID,
        'proposed_child_cap_usd': str(CHILD_CAP),
        'per_request_reserve_usd': str(RESERVE),
        'funding_pool': 'openrouter_additional',
        'authority_reader': authority.SCHEMA,
        'full_series_completion_guaranteed': False,
        'allocation_authorized': False,
        'dispatch_authorized': False,
        'source_bindings': {relative(path): sha(path) for path in source_paths()}}


def prepare():
    if BASE.exists():
        raise FileExistsError('Plain Mistral remaining-stage proposal already prepared')
    # Full reconstruction is deliberately confined to preparation on the host
    # that still has the private historical files. The proof is then archived.
    proof_data = source_proof_data()
    BASE.mkdir(parents=True)
    with PROOF.open('x') as out:
        json.dump(proof_data, out, indent=2)
        out.write('\n'); out.flush(); os.fsync(out.fileno())
    serialized = {repeat: (json.dumps(plan_data(repeat), indent=2,
                    ensure_ascii=False) + '\n').encode() for repeat in PASSES}
    plans = {repeat: hashlib.sha256(raw).hexdigest() for repeat, raw in serialized.items()}
    with tempfile.TemporaryDirectory(dir=BASE.parent, prefix='.remaining8-v4-') as tmp:
        stage = Path(tmp)
        for repeat, raw in serialized.items():
            target = stage / repeat / 'manifest.json'
            target.parent.mkdir(parents=True)
            target.write_bytes(raw)
        # The reviewed proposal remains absent until every plan is present.
        try:
            for repeat in PASSES:
                target = BASE / repeat / 'manifest.json'
                target.parent.mkdir(parents=True)
                os.link(stage / repeat / 'manifest.json', target)
            proposal = proposal_data(plans)
            with MANIFEST.open('x') as out:
                json.dump(proposal, out, indent=2)
                out.write('\n'); out.flush(); os.fsync(out.fileno())
        except BaseException:
            # An incomplete proposal cannot be mistaken for an admitted one.
            raise
    return sha(MANIFEST)


def verify():
    saved = json.loads(MANIFEST.read_text())
    plans = {repeat: sha(BASE / repeat / 'manifest.json') for repeat in PASSES}
    for name, digest in saved['source_bindings'].items():
        path = (ROOT / name).resolve()
        path.relative_to(ROOT.resolve())
        if sha(path) != digest:
            raise ValueError('Bound plain Mistral source changed: ' + name)
    if saved != proposal_data(plans):
        raise ValueError('Plain Mistral remaining-stage proposal differs')
    return sha(MANIFEST)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('prepare', 'verify'))
    args = p.parse_args()
    print({'prepare': prepare, 'verify': verify}[args.action]())


if __name__ == '__main__':
    main()
