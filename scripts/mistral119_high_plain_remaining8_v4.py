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
    diagnostic.verify()
    source = original_path(repeat)
    original = deepcopy(old.study.verify(old.OLD_CONFIG, repeat, sha(source)))
    route = old.route_snapshot()
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
              old.BASE / ('budget-' + old.PARTITION_ID + '.jsonl')]
    paths += [original_path(repeat) for repeat in PASSES]
    return paths


def proposal_data(plans):
    diagnostic.verify()
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
    serialized = {repeat: (json.dumps(plan_data(repeat), indent=2,
                    ensure_ascii=False) + '\n').encode() for repeat in PASSES}
    plans = {repeat: hashlib.sha256(raw).hexdigest() for repeat, raw in serialized.items()}
    BASE.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=BASE.parent, prefix='.remaining8-v4-') as tmp:
        stage = Path(tmp)
        for repeat, raw in serialized.items():
            target = stage / repeat / 'manifest.json'
            target.parent.mkdir(parents=True)
            target.write_bytes(raw)
        # proposal_data resolves the staged plans through BASE, so publish
        # plans with exclusive links before calculating its source bindings.
        BASE.mkdir()
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
