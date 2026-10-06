#!/usr/bin/env python3
"""Verify saved Jev native Choice evidence and render an offline findings report."""
import argparse
import base64
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path

from development_benchmark import ROOT, KEYS, read_rows, valid
import openrouter_decision_smoke as decision
import openrouter_jev_native_full_v1 as jev
import openrouter_native_variants_full_v1 as full
import openrouter_native_variants_plan as frozen
import openrouter_native_variants_v2 as smoke
import openrouter_jev_authority_v2 as bridge

BASE = ROOT / 'results/route-audits/jev-native-full-v1-20261006'
REFERENCES = ROOT / 'data/pilot/proposed_labels.jsonl'
REFERENCE_SHA256 = '440fa16759473b6d4ff52fe7e7296e5f2dfca0a58f5df26f20aef0daafed1464'
CONFIGS = {'P1': 'jev-openrouter-native-p1-choice-v1',
           'P2': 'jev-openrouter-native-p2-choice-v1'}
STAGES = ('fresh1', 'fresh2')
OUTPUT = ROOT / 'docs/JEV_NATIVE_PROMPT_FINDINGS_2026-10-06.md'
BASE_RELATIVE = BASE.relative_to(ROOT)
MASTER_RELATIVE = Path('results/openrouter-paid-budget.jsonl')
TAIL_BASE = bridge.TAIL_BASE
TAIL_RELATIVE = TAIL_BASE.relative_to(ROOT)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def source(path):
    path = Path(path)
    return {'path': str(path.relative_to(ROOT)), 'sha256': sha(path)}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def archived_root(path_value, relative, label):
    """Check a signed absolute path's repository suffix without opening it."""
    path = Path(path_value) if isinstance(path_value, str) else Path()
    relative = Path(relative)
    require(path.is_absolute() and len(path.parts) > len(relative.parts) and
            path.parts[-len(relative.parts):] == relative.parts,
            label + ' archived path differs')
    return path.parts[:-len(relative.parts)]


def archived_receipt(config, stage, manifest, base):
    """Retain signed archived paths while reading relocated local evidence."""
    p = full.paths(base, config, stage)
    budget = json.loads(p['budget'].read_text())
    partition = manifest['passes'][full.PASSES.index(stage)]['partition_id']
    child = p['budget'].parent / (p['budget'].stem + '-' + partition + '.jsonl')
    partitions = budget.get('partitions')
    require(budget.get('version') == 'paid-partitions-v1' and
            isinstance(partitions, list) and len(partitions) == 1 and
            child.is_file() and child.stat().st_size > 0,
            'Archived child allocation differs')
    archived_child = partitions[0].get('child_ledger')
    expected_partition = {'id': partition, 'cap_usd': manifest['whole_pass_bound_usd'],
                          'child_ledger': archived_child, 'model': manifest['model'],
                          'provider': manifest['provider_tag'], 'reasoning': 'none'}
    require(partitions == [expected_partition],
            'Archived child allocation differs')
    old_root = archived_root(budget.get('master_ledger'), MASTER_RELATIVE,
                             'Budget master ledger')
    child_relative = BASE_RELATIVE / config / child.name
    require(archived_root(archived_child, child_relative, 'Budget child ledger') == old_root,
            'Archived budget paths use different checkout roots')
    identity = {'manifest_sha256': sha(p['manifest']), 'budget_manifest_sha256': sha(p['budget']),
                'partition_id': partition, 'child_ledger': archived_child,
                'cap_usd': expected_partition['cap_usd']}
    hold_source = smoke.sha(decision.canonical(identity))
    context_sha = full.context_proof(config, manifest, base=base)
    inspection_sha = full.smoke_inspection(config, manifest, base=base)
    prior = full.predecessor(config, stage, manifest, base=base)
    expected = jev.expected_receipt(config, stage, manifest, p['budget'], context_sha,
                                    inspection_sha, prior, hold_source, base=base)
    receipt = json.loads(p['receipt'].read_text())
    head = receipt.get('global_authority_head_sha256')
    require(isinstance(head, str) and len(head) == 64 and
            all(c in '0123456789abcdef' for c in head) and
            receipt == {**expected, 'global_authority_head_sha256': head} and
            sha(p['stage'] / 'review-receipt.json') == sha(p['receipt']),
            'Archived root receipt differs')
    return p, child, archived_child, old_root, context_sha, inspection_sha, prior


def parse_attempts(manifest, stage_dir, expected_count, invalid_id=None, unknown_id=None,
                   unknown_kind='http_429', expected_requests=None):
    """Reparse exact saved requests and raw responses, preserving every outcome."""
    events = rows(stage_dir / 'attempts.jsonl')
    require(len(events) == expected_count * 4 - (1 if unknown_id else 0),
            'Attempt event count differs')
    predictions, native, statuses, costs = {}, {}, {}, {}
    tokens = {'input': 0, 'output': 0}
    elapsed = []
    ledger_events = []
    cursor = 0
    for index in range(expected_count):
        ident = manifest['ids'][index]
        unknown = ident == unknown_id
        group = events[cursor:cursor + (3 if unknown else 4)]
        cursor += len(group)
        last_stage = 'transport_error' if unknown and unknown_kind == 'transport_timeout' else 'response'
        require([x.get('stage') for x in group] ==
                (['reserved', 'started', last_stage] if unknown else
                 ['reserved', 'started', 'response', 'parsed']),
                'Attempt lifecycle differs: ' + ident)
        reserve, started, outcome = group[:3]
        attempt_id = reserve.get('attempt_id')
        require(isinstance(attempt_id, str) and bool(attempt_id) and
                all(x.get('id') == ident and x.get('attempt_id') == attempt_id for x in group) and
                reserve.get('request_sha256') == manifest['request_sha256'][index] and
                reserve.get('cost_unknown') is True and started.get('cost_unknown') is True and
                outcome.get('reserved_cost_usd') == reserve.get('reserved_cost_usd'),
                'Attempt identity differs: ' + ident)
        request = base64.b64decode(started.get('request_base64', ''), validate=True)
        require(hashlib.sha256(request).hexdigest() == manifest['request_sha256'][index] and
                (expected_requests is None or
                 (expected_requests[index]['id'] == ident and
                  request == decision.canonical(expected_requests[index]['payload']))),
                'Saved request bytes differ: ' + ident)
        ledger_events.append(('reserve', attempt_id, ident, Decimal(reserve['reserved_cost_usd'])))
        if unknown and unknown_kind == 'transport_timeout':
            require(outcome.get('error_type') == 'TimeoutError' and
                    outcome.get('cost_unknown') is True and
                    type(outcome.get('client_request_elapsed_ns')) is int and
                    outcome['client_request_elapsed_ns'] >= 0 and
                    isinstance(outcome.get('request_end_utc'), str),
                    'Stopped transport outcome differs: ' + ident)
            elapsed.append(outcome['client_request_elapsed_ns'] / 1e9)
            statuses[ident] = 'unknown_cost_transport_timeout'
            ledger_events.append(('unknown_cost_accounted_as_upper_bound', attempt_id, ident,
                                  Decimal(reserve['reserved_cost_usd'])))
            continue
        response = outcome
        raw = base64.b64decode(response.get('raw_response_base64', ''), validate=True)
        require(hashlib.sha256(raw).hexdigest() == response.get('raw_response_sha256') and
                len(raw) == response.get('raw_response_size_bytes') and
                json.loads(raw) == response.get('body'), 'Raw response differs: ' + ident)
        body = response['body']
        require(type(response.get('client_request_elapsed_ns')) is int and
                response['client_request_elapsed_ns'] >= 0, 'Client timing differs: ' + ident)
        elapsed.append(response['client_request_elapsed_ns'] / 1e9)
        if unknown:
            require(response.get('http_status') == 429 and response.get('cost_unknown') is True and
                    response.get('actual_cost_usd') is None and body.get('error', {}).get('code') == 429,
                    'Stopped provider outcome differs: ' + ident)
            statuses[ident] = 'unknown_cost_http_429'
            ledger_events.append(('unknown_cost_accounted_as_upper_bound', attempt_id, ident,
                                  Decimal(reserve['reserved_cost_usd'])))
            continue
        parsed = group[3]
        require(response.get('http_status') == 200 and response.get('cost_unknown') is False and
                response.get('parse_error_type') is None and
                body.get('model') == manifest['returned_model'] and
                body.get('provider') == manifest['provider'] and
                body.get('truncated') is not True,
                'Provider route or response differs: ' + ident)
        actual = decision.response_cost(body)
        require(actual is not None and actual == Decimal(str(response.get('actual_cost_usd'))),
                'Provider cost differs: ' + ident)
        costs[ident] = actual
        ledger_events.append(('settle', attempt_id, ident, actual))
        usage = body.get('usage') or {}
        require(type(usage.get('input_tokens')) is int and type(usage.get('output_tokens')) is int,
                'Provider usage differs: ' + ident)
        tokens['input'] += usage['input_tokens']
        tokens['output'] += usage['output_tokens']
        if ident == invalid_id:
            require(parsed.get('valid') is False and
                    parsed.get('reason') == 'Probabilities do not sum to one' and
                    body['answers']['sentiment']['probabilities'] and
                    abs(sum(body['answers']['sentiment']['probabilities'].values()) - 1) > .001,
                    'Intrinsic invalid outcome differs: ' + ident)
            statuses[ident] = 'invalid_native_distribution'
            continue
        prediction = decision.validate_response(body, decision.ROUTES['jev'])
        require(parsed.get('valid') is True and parsed.get('prediction') == prediction and
                valid(prediction), 'Raw prediction differs: ' + ident)
        statuses[ident] = 'valid'
        predictions[ident] = prediction
        native[ident] = {key: {'probabilities': body['answers'][key]['probabilities'],
                               'confidence': body['answers'][key]['confidence']} for key in KEYS}
    require(cursor == len(events), 'Unaccounted attempt events')
    return {'predictions': predictions, 'native': native, 'statuses': statuses,
            'costs': costs, 'tokens': tokens, 'elapsed': elapsed,
            'ledger_events': ledger_events}


def check_child(child, archived_child, archived_checkout_root, partition, parsed,
                reconciliation, unknown_path=None, *, cap_usd='0.080640000',
                unknown_relative=None):
    events = rows(child)
    cap = Decimal(events[0].get('cap_usd', '-1')) if events else Decimal(-1)
    require(events[0].get('event') == 'budget' and cap == Decimal(cap_usd) and
            events[-1].get('event') == 'partition_closed' and
            len(events) == len(parsed['ledger_events']) + 2,
            'Archived child ledger shape differs')
    for event, expected in zip(events[1:-1], parsed['ledger_events']):
        kind, attempt_id, ident, amount = expected
        require(event.get('event') == kind and event.get('attempt_id') == attempt_id and
                Decimal(event.get('usd', '-1')) == amount and
                (kind != 'reserve' or event.get('record_id') == partition + ':' + ident),
                'Archived child ledger event differs: ' + ident)
        if kind == 'unknown_cost_accounted_as_upper_bound':
            relative = unknown_relative or (BASE_RELATIVE / CONFIGS['P2'] / 'fresh2' /
                                            'unknown-cost-evidence.jsonl')
            require(unknown_path is not None and
                    event.get('evidence_sha256') == sha(unknown_path) and
                    event.get('actual_cost_usd') is None and
                    archived_root(event.get('evidence_path'), relative,
                                  'Unknown-cost evidence') == archived_checkout_root and
                    rows(unknown_path) == [rows(unknown_path.parent / 'attempts.jsonl')[-1]],
                    'Unknown-cost raw evidence differs')
    known = sum(parsed['costs'].values(), Decimal(0))
    unknown = sum((x[3] for x in parsed['ledger_events']
                   if x[0] == 'unknown_cost_accounted_as_upper_bound'), Decimal(0))
    require(reconciliation.get('event') == 'partition_reconciled' and
            reconciliation.get('partition_id') == partition and
            reconciliation.get('child_ledger') == archived_child and
            reconciliation.get('child_sha256') == sha(child) and
            Decimal(reconciliation['known_actual_usd']) == known and
            Decimal(reconciliation['unknown_upper_bound_usd']) == unknown and
            Decimal(reconciliation['unused_allocation_released_usd']) == cap - known - unknown,
            'Child reconciliation differs')
    return known, unknown


def score(parsed, truth, ids):
    valid_ids = list(parsed['predictions'])
    return {'denominator': len(ids), 'valid': len(valid_ids),
            'allFour': sum(all(parsed['predictions'][ident][k] == truth[ident][k] for k in KEYS)
                           for ident in valid_ids),
            'fields': {key: sum(parsed['predictions'][ident][key] == truth[ident][key]
                                for ident in valid_ids) for key in KEYS}}


def compare(left, right, ids):
    shared = [ident for ident in ids if ident in left['predictions'] and ident in right['predictions']]
    return {'denominator': len(shared), 'excludedIds': [ident for ident in ids if ident not in shared],
            'fourFieldVectorChangedIds': [ident for ident in shared if
                                          left['predictions'][ident] != right['predictions'][ident]],
            'fields': {key: {'choiceChangedIds': [ident for ident in shared if
                                                left['predictions'][ident][key] != right['predictions'][ident][key]],
                             'probabilityChangedIds': [ident for ident in shared if
                                                       left['native'][ident][key]['probabilities'] !=
                                                       right['native'][ident][key]['probabilities']],
                             'confidenceChangedIds': [ident for ident in shared if
                                                      left['native'][ident][key]['confidence'] !=
                                                      right['native'][ident][key]['confidence']]}
                       for key in KEYS}}


def verify_prompt_delta(plans):
    left, right = (plans[CONFIGS[c]]['requests'] for c in ('P1', 'P2'))
    require(len(left) == len(right) == 60, 'Frozen prompt record count differs')
    for one, two in zip(left, right):
        require(one['id'] == two['id'] and one['feedback_sha256'] == two['feedback_sha256'] and
                one['p0_payload_sha256'] == two['p0_payload_sha256'],
                'Prompt source identity differs')
        a, b = json.loads(json.dumps(one['payload'])), json.loads(json.dumps(two['payload']))
        for key in KEYS:
            require(a['questions'][key]['instructions'] != b['questions'][key]['instructions'],
                    'Prompt instructions did not differ')
            del a['questions'][key]['instructions']
            del b['questions'][key]['instructions']
        require(a == b, 'Native prompt non-instruction controls differ')


def verify_p0_prompt_delta(p0_requests, plans):
    require(len(p0_requests) == 60, 'P0 prompt record count differs')
    for condition in ('P1', 'P2'):
        for baseline, variant in zip(p0_requests, plans[CONFIGS[condition]]['requests']):
            require(baseline['id'] == variant['id'] and
                    baseline['feedback_sha256'] == variant['feedback_sha256'] and
                    baseline['payload_sha256'] == variant['p0_payload_sha256'],
                    'P0 and ' + condition + ' prompt source identity differs')
            a = json.loads(json.dumps(baseline['payload']))
            b = json.loads(json.dumps(variant['payload']))
            for key in KEYS:
                require(a['questions'][key]['instructions'] != b['questions'][key]['instructions'],
                        'P0 and ' + condition + ' prompt instructions did not differ')
                del a['questions'][key]['instructions']
                del b['questions'][key]['instructions']
            require(a == b, 'P0 and ' + condition + ' prompt controls differ')


def tail_receipt(manifest):
    """Rebuild the v2 root receipt from saved paths, without opening master."""
    config = CONFIGS['P2']
    p = full.paths(TAIL_BASE, config, bridge.TAIL_STAGE)
    budget = json.loads(p['budget'].read_text())
    partition = bridge.TAIL_PARTITION
    child = p['budget'].parent / (p['budget'].stem + '-' + partition + '.jsonl')
    entries = budget.get('partitions')
    require(budget.get('version') == 'paid-partitions-v1' and
            isinstance(entries, list) and len(entries) == 1 and child.is_file(),
            'Tail child allocation differs')
    archived_child = entries[0].get('child_ledger')
    require(entries == [{'id': partition, 'cap_usd': manifest['whole_pass_bound_usd'],
                         'child_ledger': archived_child, 'model': manifest['model'],
                         'provider': manifest['provider_tag'], 'reasoning': 'none'}],
            'Tail child allocation differs')
    old_root = archived_root(budget.get('master_ledger'), MASTER_RELATIVE,
                             'Tail budget master ledger')
    require(archived_root(archived_child, TAIL_RELATIVE / config / child.name,
                          'Tail budget child ledger') == old_root,
            'Tail budget paths use different checkout roots')
    identity = {'manifest_sha256': sha(p['manifest']), 'budget_manifest_sha256': sha(p['budget']),
                'partition_id': partition, 'child_ledger': archived_child,
                'cap_usd': manifest['whole_pass_bound_usd']}
    hold_source = smoke.sha(decision.canonical(identity))
    core = bridge._tail_core()
    context_sha = core.context_proof(config, manifest, base=TAIL_BASE)
    inspection_sha = core.smoke_inspection(config, manifest, base=TAIL_BASE)
    prior = core.predecessor(config, bridge.TAIL_STAGE, manifest, base=TAIL_BASE)
    expected = core.expected_receipt(config, bridge.TAIL_STAGE, manifest, p['budget'],
                                     context_sha, inspection_sha, prior, hold_source,
                                     base=TAIL_BASE)
    receipt = json.loads(p['receipt'].read_text())
    head = receipt.get('global_authority_head_sha256')
    require(isinstance(head, str) and len(head) == 64 and
            all(c in '0123456789abcdef' for c in head) and
            receipt == {**expected, 'global_authority_head_sha256': head} and
            sha(p['stage'] / 'review-receipt.json') == sha(p['receipt']),
            'Tail root receipt differs')
    return p, child, archived_child, old_root, receipt


def verified_tail(truth, plans):
    """Project the attempted 42 only after validating source and billing chain."""
    config = CONFIGS['P2']
    manifest = bridge.verify_tail()
    original = plans[config]
    expected_requests = original['requests'][18:]
    require(manifest['ids'] == [x['id'] for x in expected_requests] == full.IDS[18:] and
            manifest['request_sha256'] == [x['payload_sha256'] for x in expected_requests] and
            manifest['original_request_set_sha256'] == original['requests_sha256'] and
            manifest['original_request_sha256'] == [x['payload_sha256'] for x in original['requests']] and
            manifest['attempted_unknown_id'] == 'DEV-018' and
            manifest['continuation_is_clean_repeat'] is False and
            manifest['whole_pass_bound_usd'] == '0.056448000',
            'Exact tail request/proposal boundary differs')
    p, child, archived_child, old_root, receipt = tail_receipt(manifest)
    directory = p['stage']
    require(not (directory / 'completion.json').exists(), 'Interrupted tail has completion')
    parsed = parse_attempts(manifest, directory, 42, invalid_id='DEV-040',
                            unknown_id='DEV-060', unknown_kind='transport_timeout',
                            expected_requests=expected_requests)
    reconciliation = json.loads((directory / 'budget-reconciliation.json').read_text())
    known, unknown = check_child(child, archived_child, old_root, bridge.TAIL_PARTITION,
                                 parsed, reconciliation, directory / 'unknown-cost-evidence.jsonl',
                                 cap_usd=manifest['whole_pass_bound_usd'],
                                 unknown_relative=TAIL_RELATIVE / config / bridge.TAIL_STAGE /
                                                  'unknown-cost-evidence.jsonl')
    outcomes = Counter(parsed['statuses'].values())
    require(outcomes == Counter({'valid': 40, 'invalid_native_distribution': 1,
                                'unknown_cost_transport_timeout': 1}),
            'Tail raw outcome counts differ')
    public = json.loads((directory / 'terminal-public.json').read_text())
    require(public == {'schema': 'jev-native-tail-interruption-v2',
                       'configuration_id': config, 'stage': bridge.TAIL_STAGE,
                       'status': 'stopped_transport_timeout', 'attempted': 42,
                       'saved_responses': 41, 'valid_count': 40,
                       'invalid_ids': ['DEV-040'], 'unknown_ids': ['DEV-060'],
                       'never_sent_ids': [], 'known_actual_cost_usd': str(known),
                       'unknown_charge_upper_bound_usd': str(unknown),
                       'attempts_sha256': sha(directory / 'attempts.jsonl'),
                       'reference_labels_read': False, 'replayed_failed_request': False,
                       'clean_repeat_credit': False},
            'Tail terminal record differs')
    saved_catalog = json.loads((directory / 'endpoint-catalog.json').read_text())
    decision.validate_endpoint(saved_catalog, decision.ROUTES['jev'])
    require(receipt['partition_id'] == reconciliation['partition_id'] and
            receipt['global_hold_source_sha256'] == smoke.sha(decision.canonical({
                'manifest_sha256': sha(p['manifest']), 'budget_manifest_sha256': sha(p['budget']),
                'partition_id': bridge.TAIL_PARTITION, 'child_ledger': archived_child,
                'cap_usd': manifest['whole_pass_bound_usd']})),
            'Tail receipt and reconciliation differ')
    files = [p['manifest'], p['receipt'], p['budget'], child,
             directory / 'review-receipt.json', directory / 'attempts.jsonl',
             directory / 'endpoint-catalog.json', directory / 'terminal-public.json',
             directory / 'unknown-cost-evidence.jsonl', directory / 'budget-reconciliation.json',
             Path(bridge.__file__), Path(bridge.authority_v2.__file__),
             Path(bridge.suffix.__file__)]
    item = {'status': 'interrupted', 'score': score(parsed, truth, manifest['ids']),
            'outcomes': dict(outcomes), 'knownCostUsd': str(known),
            'unknownUpperBoundUsd': str(unknown),
            'inputTokens': parsed['tokens']['input'],
            'outputTokens': parsed['tokens']['output'],
            'clientSeconds': sum(parsed['elapsed']),
            'cleanRepeatCredit': False}
    return item, parsed, [source(path) for path in files]


def verified_v2_full(config, stage, requests, truth, invalid_id=None):
    """Verify one closed v2 full pass from immutable inputs through reconciliation."""
    manifest, original_manifest_sha = bridge._source_bound(config)
    request_set_sha = decision.sha(decision.canonical(requests))
    require(manifest['request_set_sha256'] == request_set_sha and
            manifest['ids'] == full.IDS and
            manifest['request_sha256'] == [x['payload_sha256'] for x in requests],
            config + ' ' + stage + ' request source differs')
    p = full.paths(bridge.BASE, config, stage)
    budget = json.loads(p['budget'].read_text())
    partition = manifest['passes'][full.PASSES.index(stage)]['partition_id']
    child = p['budget'].parent / (p['budget'].stem + '-' + partition + '.jsonl')
    entries = budget.get('partitions')
    require(budget.get('version') == 'paid-partitions-v1' and
            isinstance(entries, list) and len(entries) == 1 and child.is_file(),
            config + ' ' + stage + ' child allocation differs')
    archived_child = entries[0].get('child_ledger')
    require(entries == [{'id': partition, 'cap_usd': manifest['whole_pass_bound_usd'],
                         'child_ledger': archived_child, 'model': manifest['model'],
                         'provider': manifest['provider_tag'], 'reasoning': 'none'}],
            config + ' ' + stage + ' child allocation differs')
    old_root = archived_root(budget.get('master_ledger'), MASTER_RELATIVE,
                             config + ' ' + stage + ' master ledger')
    require(archived_root(archived_child, bridge.BASE.relative_to(ROOT) / config / child.name,
                          config + ' ' + stage + ' child ledger') == old_root,
            config + ' ' + stage + ' budget paths use different checkout roots')
    identity = {'manifest_sha256': sha(p['manifest']), 'budget_manifest_sha256': sha(p['budget']),
                'partition_id': partition, 'child_ledger': archived_child,
                'cap_usd': manifest['whole_pass_bound_usd']}
    hold_source = smoke.sha(decision.canonical(identity))
    core = bridge._full_core(config)
    context_sha = core.context_proof(config, manifest, base=bridge.BASE)
    inspection_sha = core.smoke_inspection(config, manifest, base=bridge.BASE)
    prior = core.predecessor(config, stage, manifest, base=bridge.BASE)
    expected = core.expected_receipt(config, stage, manifest, p['budget'],
                                     context_sha, inspection_sha, prior, hold_source,
                                     base=bridge.BASE)
    receipt = json.loads(p['receipt'].read_text())
    head = receipt.get('global_authority_head_sha256')
    require(isinstance(head, str) and len(head) == 64 and
            all(c in '0123456789abcdef' for c in head) and
            receipt == {**expected, 'global_authority_head_sha256': head} and
            receipt['original_manifest_sha256'] == original_manifest_sha and
            sha(p['stage'] / 'review-receipt.json') == sha(p['receipt']),
            config + ' ' + stage + ' v2 receipt differs')
    directory = p['stage']
    parsed = parse_attempts(manifest, directory, 60, invalid_id=invalid_id,
                            expected_requests=requests)
    reconciliation = json.loads((directory / 'budget-reconciliation.json').read_text())
    known, unknown = check_child(child, archived_child, old_root, partition,
                                 parsed, reconciliation)
    expected_outcomes = Counter({'valid': 60 - int(invalid_id is not None)})
    if invalid_id:
        expected_outcomes['invalid_native_distribution'] = 1
    require(unknown == 0 and Counter(parsed['statuses'].values()) == expected_outcomes,
            config + ' ' + stage + ' raw and cost totals differ')
    decision.validate_endpoint(json.loads((directory / 'endpoint-catalog.json').read_text()),
                               decision.ROUTES['jev'])
    completion = json.loads((directory / 'completion.json').read_text())
    require(completion == {'schema': full.SCHEMA + '-completion',
                           'configuration_id': config, 'stage': stage, 'ids': full.IDS,
                           'valid_count': 60 - int(invalid_id is not None),
                           'invalid_count': int(invalid_id is not None),
                           'invalid_ids': [invalid_id] if invalid_id else [],
                           'manifest_sha256': sha(p['manifest']),
                           'context_proof_sha256': context_sha,
                           'smoke_inspection_sha256': inspection_sha,
                           'predecessor_proof': prior, 'receipt_sha256': sha(p['receipt']),
                           'budget_manifest_sha256': sha(p['budget']),
                           'endpoint_catalog_sha256': sha(directory / 'endpoint-catalog.json'),
                           'attempts_sha256': sha(directory / 'attempts.jsonl'),
                           'known_actual_cost_usd': str(known),
                           'reference_labels_read': False},
            config + ' ' + stage + ' completion differs')
    item = {'status': 'complete', 'score': score(parsed, truth, full.IDS),
            'outcomes': dict(Counter(parsed['statuses'].values())),
            'knownCostUsd': str(known), 'unknownUpperBoundUsd': str(unknown),
            'inputTokens': parsed['tokens']['input'],
            'outputTokens': parsed['tokens']['output'],
            'clientSeconds': sum(parsed['elapsed'])}
    original_manifest = full.paths(bridge._original_base(config), config)['manifest']
    files = [original_manifest, p['manifest'], p['estimate'], p['context'], p['inspection'], p['receipt'],
             p['budget'], child, directory / 'review-receipt.json',
             directory / 'attempts.jsonl', directory / 'endpoint-catalog.json',
             directory / 'completion.json', directory / 'budget-reconciliation.json']
    return item, parsed, [source(path) for path in files]


def build(base=BASE, refs_path=REFERENCES):
    require(sha(refs_path) == REFERENCE_SHA256, 'Frozen reference SHA differs')
    reference_rows = read_rows(refs_path)
    ids = [item['id'] for item in reference_rows]
    require(ids == full.IDS and len(set(ids)) == 60 and
            all(item.get('split') == 'development' and valid(item.get('proposed_labels'))
                for item in reference_rows), 'Frozen reference membership differs')
    truth = {item['id']: item['proposed_labels'] for item in reference_rows}
    plans = frozen.build_plan(ROOT)
    verify_prompt_delta(plans)
    result = {'sourceBindings': [source(refs_path)], 'passes': {}, 'comparisons': {}}
    private = {}
    for condition, config in CONFIGS.items():
        manifest = jev.verify(config, base=base)
        require(manifest['route'] == 'jev' and manifest['condition'] == condition and
                manifest['ids'] == ids and manifest['reference_labels_read'] is False and
                manifest['request_set_sha256'] == plans[config]['requests_sha256'],
                'Frozen Jev full-pass manifest differs')
        result['sourceBindings'].append(source(full.paths(base, config)['manifest']))
        result['passes'][condition], private[condition] = {}, {}
        for stage in STAGES:
            p, child, archived_child, archived_checkout_root, context_sha, inspection_sha, prior = \
                archived_receipt(config, stage, manifest, base)
            directory = p['stage']
            terminal = condition == 'P2' and stage == 'fresh2'
            parsed = parse_attempts(manifest, directory, 18 if terminal else 60,
                                    'DEV-056' if condition == 'P1' and stage == 'fresh2' else None,
                                    'DEV-018' if terminal else None)
            reconciliation = json.loads((directory / 'budget-reconciliation.json').read_text())
            known, unknown = check_child(child, archived_child, archived_checkout_root,
                                         manifest['passes'][full.PASSES.index(stage)]['partition_id'],
                                         parsed, reconciliation,
                                         directory / 'unknown-cost-evidence.jsonl' if terminal else None)
            status = 'stopped' if terminal else 'complete'
            if terminal:
                require(not (directory / 'completion.json').exists(), 'Stopped pass has completion')
                public = json.loads((directory / 'terminal-public.json').read_text())
                require(public == {'schema': 'jev-native-full-interruption-v1',
                                   'configuration_id': config, 'stage': stage,
                                   'status': 'stopped_http_429', 'valid_count': 17,
                                   'failed_ids': ['DEV-018'], 'never_sent_ids': ids[18:],
                                   'known_actual_cost_usd': str(known),
                                   'unknown_charge_upper_bound_usd': str(unknown),
                                   'attempts_sha256': sha(directory / 'attempts.jsonl'),
                                   'reference_labels_read': False, 'replayed_failed_request': False},
                        'Stopped terminal record differs')
            else:
                completion = json.loads((directory / 'completion.json').read_text())
                invalid = ['DEV-056'] if condition == 'P1' and stage == 'fresh2' else []
                require(completion == {'schema': full.SCHEMA + '-completion',
                                       'configuration_id': config, 'stage': stage, 'ids': ids,
                                       'valid_count': 60 - len(invalid), 'invalid_count': len(invalid),
                                       'invalid_ids': invalid, 'manifest_sha256': sha(p['manifest']),
                                       'context_proof_sha256': context_sha,
                                       'smoke_inspection_sha256': inspection_sha,
                                       'predecessor_proof': prior, 'receipt_sha256': sha(p['receipt']),
                                       'budget_manifest_sha256': sha(p['budget']),
                                       'endpoint_catalog_sha256': sha(directory / 'endpoint-catalog.json'),
                                       'attempts_sha256': sha(directory / 'attempts.jsonl'),
                                       'known_actual_cost_usd': str(known),
                                       'reference_labels_read': False}, 'Closed completion differs')
            scored = score(parsed, truth, ids)
            result['passes'][condition][stage] = {'status': status, 'score': scored,
                'outcomes': dict(Counter(parsed['statuses'].values()) |
                                 Counter({'never_sent': 42}) if terminal else Counter(parsed['statuses'].values())),
                'knownCostUsd': str(known), 'unknownUpperBoundUsd': str(unknown),
                'inputTokens': parsed['tokens']['input'], 'outputTokens': parsed['tokens']['output'],
                'clientSeconds': sum(parsed['elapsed'])}
            private[condition][stage] = parsed
            names = ['review-receipt.json', 'attempts.jsonl', 'budget-reconciliation.json',
                     'endpoint-catalog.json'] + (['terminal-public.json', 'unknown-cost-evidence.jsonl']
                                                 if terminal else ['completion.json'])
            result['sourceBindings'].extend(source(directory / name) for name in names)
            result['sourceBindings'].extend(source(item) for item in (p['context'], p['inspection'],
                                                                      p['receipt'], p['budget'], child))
    p0_plan = bridge.p0.build_plan(ROOT)[bridge.p0.CONFIG]
    verify_p0_prompt_delta(p0_plan['requests'], plans)
    result['passes']['P0'], private['P0'] = {}, {}
    for stage in full.PASSES:
        item, parsed, sources = verified_v2_full(
            bridge.p0.CONFIG, stage, p0_plan['requests'], truth,
            invalid_id='DEV-040' if stage == 'fresh3' else None)
        result['passes']['P0'][stage] = item
        private['P0'][stage] = parsed
        result['sourceBindings'].extend(sources)
    result['comparisons']['P0fresh1fresh2'] = compare(
        private['P0']['fresh1'], private['P0']['fresh2'], ids)
    result['comparisons']['P0fresh2fresh3'] = compare(
        private['P0']['fresh2'], private['P0']['fresh3'], ids)
    result['comparisons']['P0fresh1fresh3'] = compare(
        private['P0']['fresh1'], private['P0']['fresh3'], ids)
    result['comparisons']['P0P1fresh1'] = compare(
        private['P0']['fresh1'], private['P1']['fresh1'], ids)
    p1_third, p1_third_parsed, p1_third_sources = verified_v2_full(
        CONFIGS['P1'], 'fresh3', plans[CONFIGS['P1']]['requests'], truth)
    require(p1_third['knownCostUsd'] == '0.006405000',
            'P1 fresh3 verified provider cost differs')
    result['passes']['P1']['fresh3'] = p1_third
    private['P1']['fresh3'] = p1_third_parsed
    result['sourceBindings'].extend(p1_third_sources)
    result['comparisons']['P1repeat'] = compare(private['P1']['fresh1'], private['P1']['fresh2'], ids)
    result['comparisons']['P1fresh2fresh3'] = compare(
        private['P1']['fresh2'], private['P1']['fresh3'], ids)
    result['comparisons']['P1fresh1fresh3'] = compare(
        private['P1']['fresh1'], private['P1']['fresh3'], ids)
    result['comparisons']['P1P2fresh1'] = compare(private['P1']['fresh1'], private['P2']['fresh1'], ids)
    result['comparisons']['P1P2fresh2shared'] = compare(private['P1']['fresh2'], private['P2']['fresh2'], ids)
    tail_item, tail_parsed, tail_sources = verified_tail(truth, plans)
    result['continuations'] = {'P2fresh2tail': tail_item}
    result['sourceBindings'].extend(tail_sources)
    parent = private['P2']['fresh2']
    require(set(parent['statuses']) == set(ids[:18]) and
            set(tail_parsed['statuses']) == set(ids[18:]) and
            not (set(parent['statuses']) & set(tail_parsed['statuses'])),
            'Parent and continuation do not partition the original 60')
    combined = {'predictions': {**parent['predictions'], **tail_parsed['predictions']},
                'native': {**parent['native'], **tail_parsed['native']},
                'statuses': {**parent['statuses'], **tail_parsed['statuses']}}
    outcomes = Counter(combined['statuses'].values())
    require(outcomes == Counter({'valid': 57, 'invalid_native_distribution': 1,
                                'unknown_cost_http_429': 1,
                                'unknown_cost_transport_timeout': 1}),
            'Combined interrupted outcome counts differ')
    result['composites'] = {'P2fresh2': {
        'status': 'interrupted_parent_with_stopped_continuation',
        'cleanRepeatCredit': False, 'score': score(combined, truth, ids),
        'outcomes': dict(outcomes), 'neverSent': 0,
        'parentOriginal': result['passes']['P2']['fresh2'],
        'knownCostUsd': str(Decimal(result['passes']['P2']['fresh2']['knownCostUsd']) +
                            Decimal(tail_item['knownCostUsd'])),
        'unknownUpperBoundUsd': str(Decimal(result['passes']['P2']['fresh2']['unknownUpperBoundUsd']) +
                                    Decimal(tail_item['unknownUpperBoundUsd'])),
        'inputTokens': result['passes']['P2']['fresh2']['inputTokens'] + tail_item['inputTokens'],
        'outputTokens': result['passes']['P2']['fresh2']['outputTokens'] + tail_item['outputTokens'],
        'clientSeconds': result['passes']['P2']['fresh2']['clientSeconds'] + tail_item['clientSeconds']}}
    result['comparisons']['P1P2fresh2CompositeShared'] = compare(
        private['P1']['fresh2'], combined, ids)
    result['sourceBindings'] = list({item['path']: item for item in result['sourceBindings']}.values())
    return result


def render(report):
    passes = report['passes']
    p0, p1, p2 = passes['P0'], passes['P1'], passes['P2']
    tail = report['continuations']['P2fresh2tail']
    composite = report['composites']['P2fresh2']
    paired = report['comparisons']['P1P2fresh1']
    repeat = report['comparisons']['P1repeat']
    second_to_third = report['comparisons']['P1fresh2fresh3']
    shared = report['comparisons']['P1P2fresh2shared']
    composite_shared = report['comparisons']['P1P2fresh2CompositeShared']
    p0_repeat12 = report['comparisons']['P0fresh1fresh2']
    p0_repeat23 = report['comparisons']['P0fresh2fresh3']
    p0_p1 = report['comparisons']['P0P1fresh1']
    def counts(item):
        s = item['score']
        return f"{s['allFour']}/60 all-four; " + ', '.join(f"{k}: {s['fields'][k]}/60" for k in KEYS)
    def changes(item, key):
        return len(item['fields'][key]['choiceChangedIds'])
    lines = [
        '# Jev native Choice P0/P1/P2 findings', '', 'Date: 2026-10-06', '',
        'These are standalone OpenRouter native Choice runs of the Jev 1.13 model. They are a separate route and prompt surface, not a distinct Jev model. The 60 development references are provisional and were read only for offline scoring.', '',
        '## Saved pass status', '',
        '| Condition | Pass | Valid | Invalid | Unknown cost | Never sent | All-four matches |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: |',
    ]
    for condition in ('P0', 'P1', 'P2'):
        for stage in full.PASSES if condition in ('P0', 'P1') else STAGES:
            item = passes[condition][stage]
            outcome = item['outcomes']
            lines.append(f"| {condition} | {stage} | {item['score']['valid']} | "
                         f"{outcome.get('invalid_native_distribution', 0)} | "
                         f"{outcome.get('unknown_cost_http_429', 0)} | "
                         f"{outcome.get('never_sent', 0)} | {item['score']['allFour']}/60 |")
    lines += [f"| P2 | fresh2 tail continuation | {tail['score']['valid']} | "
              f"{tail['outcomes'].get('invalid_native_distribution', 0)} | "
              f"{tail['outcomes'].get('unknown_cost_transport_timeout', 0)} | 0 | "
              f"{tail['score']['allFour']}/42 |",
              f"| P2 | fresh2 combined interrupted | {composite['score']['valid']} | "
              f"{composite['outcomes'].get('invalid_native_distribution', 0)} | "
              f"{composite['outcomes'].get('unknown_cost_http_429', 0) + composite['outcomes'].get('unknown_cost_transport_timeout', 0)} | "
              f"{composite['neverSent']} | {composite['score']['allFour']}/60 |"]
    lines += ['', 'P0 fresh1: ' + counts(p0['fresh1']) + '.',
              'P0 fresh2: ' + counts(p0['fresh2']) + '.',
              'P0 fresh3: ' + counts(p0['fresh3']) + '. DEV-040 returned HTTP 200 with a native probability distribution that does not sum to one. Its known provider cost remains counted; it is excluded from answer scoring.',
              'P1 fresh1: ' + counts(p1['fresh1']) + '.',
              'P1 fresh2: ' + counts(p1['fresh2']) + '. DEV-056 returned HTTP 200 and a native probability distribution that does not sum to one. Its known provider cost remains counted; it is excluded from answer scoring.',
              'P1 fresh3: ' + counts(p1['fresh3']) + '. All 60 responses were valid and the child allocation was reconciled.',
              'P2 fresh1: ' + counts(p2['fresh1']) + '.',
              'The original P2 fresh2 stage has 17 valid responses and 15 all-four matches among those 17. DEV-018 received HTTP 429 with an unknown charge bounded at $0.001344000. At that stage, DEV-019 through DEV-060 were never sent. Its original terminal record and 17-valid/42-unsent counters remain intact.',
              f"The separate DEV-019 through DEV-060 continuation attempted all 42 positions: {tail['score']['valid']} valid, one invalid, and one timeout with unknown cost. DEV-040 returned HTTP 200, but its native sentiment probabilities sum to 0.99. DEV-060 timed out without a response; its full $0.001344000 reserve remains an unknown-charge upper bound. The continuation has {tail['score']['allFour']}/42 all-four matches, with only its 40 valid answers scored.",
              f"Together, the stopped parent and stopped continuation cover all 60 original positions: {composite['score']['valid']} valid, one invalid, two unknown-cost attempts, and no never-sent positions. The {composite['score']['allFour']}/60 all-four figure is an interrupted composite accounting value. It is not a clean P2 fresh2 repeat or a repaired DEV-018/DEV-060 observation.", '',
              '## Prompt comparison and repeat variation', '',
              'The frozen P0, P1, and P2 native requests share record order, feedback, policy, criteria, labels, route, and parser. The four Choice question instructions distinguish the conditions. They are native analogues of the three prompts, not byte-identical chat prompts.', '',
              f"Across P0 fresh1 and fresh2, {len(p0_repeat12['fourFieldVectorChangedIds'])}/60 answer vectors changed ({', '.join(p0_repeat12['fourFieldVectorChangedIds'])}). Fresh2 and fresh3 changed {len(p0_repeat23['fourFieldVectorChangedIds'])}/{p0_repeat23['denominator']} shared valid vectors ({', '.join(p0_repeat23['fourFieldVectorChangedIds'])}); DEV-040 is excluded from that pair. P0 fresh1 and P1 fresh1 changed {len(p0_p1['fourFieldVectorChangedIds'])}/60 vectors ({', '.join(p0_p1['fourFieldVectorChangedIds'])}). These are observed pairwise differences, not a causal estimate of prompt effect.",
              f"In fresh1, P1 and P2 differ on {len(paired['fourFieldVectorChangedIds'])}/60 four-field answer vectors: " +
              (', '.join(paired['fourFieldVectorChangedIds']) or 'none') + '. Field answer changes: ' +
              ', '.join(f"{key} {changes(paired, key)}" for key in KEYS) +
              f". P1 and P2 have {p1['fresh1']['score']['allFour']}/60 and {p2['fresh1']['score']['allFour']}/60 all-four matches respectively. " +
              'Native probability dictionary changes by field: ' +
              ', '.join(f"{key} {len(paired['fields'][key]['probabilityChangedIds'])}/60" for key in KEYS) +
              '. Vendor confidence changes: ' +
              ', '.join(f"{key} {len(paired['fields'][key]['confidenceChangedIds'])}/60" for key in KEYS) + '.',
              f"Across P1 fresh1 and fresh2, {len(repeat['fourFieldVectorChangedIds'])}/{repeat['denominator']} shared valid records changed a four-field answer vector. DEV-056 is excluded from this paired repeat comparison because fresh2 is invalid. Native probability dictionaries and vendor confidence are compared separately; neither is a calibrated correctness probability.",
              'P1 repeat probability dictionary changes by field: ' +
              ', '.join(f"{key} {len(repeat['fields'][key]['probabilityChangedIds'])}/59" for key in KEYS) +
              '. Vendor confidence changes: ' +
              ', '.join(f"{key} {len(repeat['fields'][key]['confidenceChangedIds'])}/59" for key in KEYS) + '.',
              f"P1 fresh3 is the third attempted full pass. Across fresh2 and fresh3, {len(second_to_third['fourFieldVectorChangedIds'])}/{second_to_third['denominator']} shared valid answer vectors changed ({', '.join(second_to_third['fourFieldVectorChangedIds'])}); DEV-056 remains excluded because fresh2 was invalid. Fresh1 and fresh3 differ at DEV-013 across 60 shared valid records. The three P1 passes have 60, 59, and 60 valid outcomes respectively.",
              f"The original fresh2 parent cross-condition comparison is restricted to {shared['denominator']} shared valid records. With the stopped continuation included, P1 fresh2 and the interrupted P2 composite share {composite_shared['denominator']} valid positions; {len(composite_shared['fourFieldVectorChangedIds'])} four-field vectors differ ({', '.join(composite_shared['fourFieldVectorChangedIds'])}). DEV-018, DEV-040, DEV-056, and DEV-060 are excluded. This comparison remains conditional on the two interrupted P2 stages.", '',
              '## Cost and timing', '',
    ]
    for condition in ('P0', 'P1', 'P2'):
        for stage in full.PASSES if condition in ('P0', 'P1') else STAGES:
            item = passes[condition][stage]
            lines.append(f"- {condition} {stage}: known provider cost ${item['knownCostUsd']}; "
                         f"unknown-charge bound ${item['unknownUpperBoundUsd']}; "
                         f"provider-reported input/output tokens {item['inputTokens']}/{item['outputTokens']}; "
                         f"client-observed request time {item['clientSeconds']:.3f} seconds.")
    for label, item in [('P2 fresh2 tail continuation', tail),
                        ('P2 fresh2 interrupted composite', composite)]:
        lines.append(f"- {label}: known provider cost ${item['knownCostUsd']}; "
                     f"unknown-charge bound ${item['unknownUpperBoundUsd']}; "
                     f"provider-reported input/output tokens {item['inputTokens']}/{item['outputTokens']}; "
                     f"client-observed request time {item['clientSeconds']:.3f} seconds.")
    lines += ['', 'Client time includes network and local work. Provider token totals exclude DEV-018 and DEV-060 because neither attempt returned usage. Client time includes the DEV-060 timeout.', '',
              '## Evidence and limits', '',
              'The offline builder verifies frozen requests, the provisional reference SHA, proposed manifests, archived and v2 root receipts, context and smoke reviews, exact saved request bytes, raw responses, terminal records, child-ledger events, and reconciled known and unknown costs. The tail receipt binds the original 60 requests, stopped parent, versioned bridge, and authority module. The builder reconstructs receipt identity from saved budget files and does not read or change the live master budget.', '',
              'The P2 fresh2 composite combines two interrupted stages and preserves both unknown-charge bounds. P0 and P1 each have three attempted full passes. P2 fresh3 is outside this report, so the native repeatability matrix remains incomplete. The earlier three-record Jev P0 smoke remains separate from these new full passes.', '',
              '## Sources', '',
              '- [Offline verifier and renderer](../scripts/build_jev_native_prompt_findings.py)',
              '- [Verifier tests](../tests/test_build_jev_native_prompt_findings.py)',
              '- [P0 frozen manifest](../results/route-audits/jev-native-p0-full-v1-20261006/jev-openrouter-native-p0-choice-v1.json)',
              '- [P0 v2 proposal](../results/route-audits/jev-authority-v2-20261006/jev-openrouter-native-p0-choice-v1.json)',
              '- [P1 frozen manifest](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p1-choice-v1.json)',
              '- [P2 frozen manifest](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1.json)',
              '- [P1 fresh1 raw attempts](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p1-choice-v1/fresh1/attempts.jsonl)',
              '- [P1 fresh2 raw attempts](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p1-choice-v1/fresh2/attempts.jsonl)',
              '- [P1 fresh3 v2 receipt](../results/route-audits/jev-authority-v2-20261006/jev-openrouter-native-p1-choice-v1/fresh3.root-review.json)',
              '- [P1 fresh3 raw attempts](../results/route-audits/jev-authority-v2-20261006/jev-openrouter-native-p1-choice-v1/fresh3/attempts.jsonl)',
              '- [P1 fresh3 completion](../results/route-audits/jev-authority-v2-20261006/jev-openrouter-native-p1-choice-v1/fresh3/completion.json)',
              '- [P1 fresh3 cost reconciliation](../results/route-audits/jev-authority-v2-20261006/jev-openrouter-native-p1-choice-v1/fresh3/budget-reconciliation.json)',
              '- [P2 fresh1 raw attempts](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1/fresh1/attempts.jsonl)',
              '- [P2 fresh2 raw attempts](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1/fresh2/attempts.jsonl)',
              '- [P2 fresh2 terminal record](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1/fresh2/terminal-public.json)',
              '- [P2 fresh2 cost reconciliation](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1/fresh2/budget-reconciliation.json)',
              '- [P2 fresh2 unknown-cost raw evidence](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1/fresh2/unknown-cost-evidence.jsonl)',
              '- [Versioned tail proposal](../results/route-audits/jev-authority-v2-20261006/p2-fresh2-unsent-continuation/jev-openrouter-native-p2-choice-v1.json)',
              '- [Tail root receipt](../results/route-audits/jev-authority-v2-20261006/p2-fresh2-unsent-continuation/jev-openrouter-native-p2-choice-v1/tail.root-review.json)',
              '- [Tail raw attempts](../results/route-audits/jev-authority-v2-20261006/p2-fresh2-unsent-continuation/jev-openrouter-native-p2-choice-v1/tail/attempts.jsonl)',
              '- [Tail terminal record](../results/route-audits/jev-authority-v2-20261006/p2-fresh2-unsent-continuation/jev-openrouter-native-p2-choice-v1/tail/terminal-public.json)',
              '- [Tail cost reconciliation](../results/route-audits/jev-authority-v2-20261006/p2-fresh2-unsent-continuation/jev-openrouter-native-p2-choice-v1/tail/budget-reconciliation.json)',
              '- [Tail timeout evidence](../results/route-audits/jev-authority-v2-20261006/p2-fresh2-unsent-continuation/jev-openrouter-native-p2-choice-v1/tail/unknown-cost-evidence.jsonl)',
              '- [Versioned bridge](../scripts/openrouter_jev_authority_v2.py)',
              '- [Frozen provisional references](../data/pilot/proposed_labels.jsonl)']
    for stage in full.PASSES:
        root = ('../results/route-audits/jev-authority-v2-20261006/'
                'jev-openrouter-native-p0-choice-v1/')
        lines.extend([
            f'- [P0 {stage} v2 receipt]({root}{stage}.root-review.json)',
            f'- [P0 {stage} raw attempts]({root}{stage}/attempts.jsonl)',
            f'- [P0 {stage} completion]({root}{stage}/completion.json)',
            f'- [P0 {stage} cost reconciliation]({root}{stage}/budget-reconciliation.json)',
        ])
    lines.append('')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--json-output', type=Path, help='Write the verified machine-readable findings to this path')
    args = parser.parse_args()
    report = build()
    rendered = render(report)
    if args.json_output:
        payload = json.dumps(report, indent=2, ensure_ascii=False) + '\n'
        if args.check:
            require(args.json_output.read_text() == payload, 'Saved Jev JSON differs from verified evidence')
        else:
            args.json_output.write_text(payload)
    if args.check:
        require(OUTPUT.read_text() == rendered, 'Saved Jev findings report differs from verified evidence')
    else:
        OUTPUT.write_text(rendered)
    print('Jev native P0/P1/P2 offline findings verified')


if __name__ == '__main__':
    main()
