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

BASE = ROOT / 'results/route-audits/jev-native-full-v1-20261006'
REFERENCES = ROOT / 'data/pilot/proposed_labels.jsonl'
REFERENCE_SHA256 = '440fa16759473b6d4ff52fe7e7296e5f2dfca0a58f5df26f20aef0daafed1464'
CONFIGS = {'P1': 'jev-openrouter-native-p1-choice-v1',
           'P2': 'jev-openrouter-native-p2-choice-v1'}
STAGES = ('fresh1', 'fresh2')
OUTPUT = ROOT / 'docs/JEV_NATIVE_PROMPT_FINDINGS_2026-10-06.md'
BASE_RELATIVE = BASE.relative_to(ROOT)
MASTER_RELATIVE = Path('results/openrouter-paid-budget.jsonl')


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


def parse_attempts(manifest, stage_dir, expected_count, invalid_id=None, unknown_id=None):
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
        require([x.get('stage') for x in group] ==
                (['reserved', 'started', 'response'] if unknown else
                 ['reserved', 'started', 'response', 'parsed']),
                'Attempt lifecycle differs: ' + ident)
        reserve, started, response = group[:3]
        attempt_id = reserve.get('attempt_id')
        require(isinstance(attempt_id, str) and bool(attempt_id) and
                all(x.get('id') == ident and x.get('attempt_id') == attempt_id for x in group) and
                reserve.get('request_sha256') == manifest['request_sha256'][index] and
                reserve.get('cost_unknown') is True and started.get('cost_unknown') is True and
                response.get('reserved_cost_usd') == reserve.get('reserved_cost_usd'),
                'Attempt identity differs: ' + ident)
        request = base64.b64decode(started.get('request_base64', ''), validate=True)
        require(hashlib.sha256(request).hexdigest() == manifest['request_sha256'][index],
                'Saved request bytes differ: ' + ident)
        raw = base64.b64decode(response.get('raw_response_base64', ''), validate=True)
        require(hashlib.sha256(raw).hexdigest() == response.get('raw_response_sha256') and
                len(raw) == response.get('raw_response_size_bytes') and
                json.loads(raw) == response.get('body'), 'Raw response differs: ' + ident)
        body = response['body']
        require(type(response.get('client_request_elapsed_ns')) is int and
                response['client_request_elapsed_ns'] >= 0, 'Client timing differs: ' + ident)
        elapsed.append(response['client_request_elapsed_ns'] / 1e9)
        ledger_events.append(('reserve', attempt_id, ident, Decimal(reserve['reserved_cost_usd'])))
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
                reconciliation, unknown_path=None):
    events = rows(child)
    cap = Decimal(events[0].get('cap_usd', '-1')) if events else Decimal(-1)
    require(events[0].get('event') == 'budget' and cap == Decimal('0.080640000') and
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
            relative = (BASE_RELATIVE / CONFIGS['P2'] / 'fresh2' /
                        'unknown-cost-evidence.jsonl')
            require(unknown_path is not None and
                    event.get('evidence_sha256') == sha(unknown_path) and
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
    result['comparisons']['P1repeat'] = compare(private['P1']['fresh1'], private['P1']['fresh2'], ids)
    result['comparisons']['P1P2fresh1'] = compare(private['P1']['fresh1'], private['P2']['fresh1'], ids)
    result['comparisons']['P1P2fresh2shared'] = compare(private['P1']['fresh2'], private['P2']['fresh2'], ids)
    result['sourceBindings'] = list({item['path']: item for item in result['sourceBindings']}.values())
    return result


def render(report):
    passes = report['passes']
    p1, p2 = passes['P1'], passes['P2']
    paired = report['comparisons']['P1P2fresh1']
    repeat = report['comparisons']['P1repeat']
    shared = report['comparisons']['P1P2fresh2shared']
    def counts(item):
        s = item['score']
        return f"{s['allFour']}/60 all-four; " + ', '.join(f"{k}: {s['fields'][k]}/60" for k in KEYS)
    def changes(item, key):
        return len(item['fields'][key]['choiceChangedIds'])
    lines = [
        '# Jev native Choice P1/P2 findings', '', 'Date: 2026-10-06', '',
        'These are standalone OpenRouter native Choice runs of the Jev 1.13 model. They are a separate route and prompt surface, not a distinct Jev model. The 60 development references are provisional and were read only for offline scoring.', '',
        '## Saved pass status', '',
        '| Condition | Pass | Valid | Invalid | Unknown cost | Never sent | All-four matches |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: |',
    ]
    for condition in ('P1', 'P2'):
        for stage in STAGES:
            item = passes[condition][stage]
            outcome = item['outcomes']
            lines.append(f"| {condition} | {stage} | {item['score']['valid']} | "
                         f"{outcome.get('invalid_native_distribution', 0)} | "
                         f"{outcome.get('unknown_cost_http_429', 0)} | "
                         f"{outcome.get('never_sent', 0)} | {item['score']['allFour']}/60 |")
    lines += ['', 'P1 fresh1: ' + counts(p1['fresh1']) + '.',
              'P1 fresh2: ' + counts(p1['fresh2']) + '. DEV-056 returned HTTP 200 and a native probability distribution that does not sum to one. Its known provider cost remains counted; it is excluded from answer scoring.',
              'P2 fresh1: ' + counts(p2['fresh1']) + '.',
              'P2 fresh2 has 17 valid responses and 15 all-four matches among those 17. DEV-018 received HTTP 429 with an unknown charge bounded at $0.001344000. DEV-019 through DEV-060 were never sent. The 15/60 entry above is a partial-denominator accounting value, not a completed 60-record score.', '',
              '## Prompt comparison and repeat variation', '',
              'The frozen P1 and P2 native requests share record order, feedback, policy, criteria, labels, route, and parser. Only the four Choice question instructions differ. They are native analogues of P1 and P2, not byte-identical chat prompts.', '',
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
              f"The fresh2 cross-condition comparison is restricted to {shared['denominator']} shared valid records. It does not stand in for a 60-record P2 repeat or a full P1/P2 comparison.", '',
              '## Cost and timing', '',
    ]
    for condition in ('P1', 'P2'):
        for stage in STAGES:
            item = passes[condition][stage]
            lines.append(f"- {condition} {stage}: known provider cost ${item['knownCostUsd']}; "
                         f"unknown-charge bound ${item['unknownUpperBoundUsd']}; "
                         f"provider-reported input/output tokens {item['inputTokens']}/{item['outputTokens']}; "
                         f"client-observed request time {item['clientSeconds']:.3f} seconds.")
    lines += ['', 'Client time includes network and local work. The stopped P2 fresh2 token totals include only the 17 successful responses because the HTTP 429 has no provider usage.', '',
              '## Evidence and limits', '',
              'The offline builder verifies frozen requests, the provisional reference SHA, proposed manifests, archived root receipts, context and smoke reviews, saved request and raw response hashes, completion or terminal status, child-ledger events, and reconciled known and unknown costs. It reconstructs receipt identity from archived budget files and never reads or changes the live master budget.', '',
              'P1 fresh3, P2 fresh3, and the remaining 42 P2 fresh2 records have no scored full-pass evidence here. This report does not call the repeatability matrix complete. The saved Jev P0 evidence is a three-record OpenRouter smoke, not a full P0 pass.', '',
              '## Sources', '',
              '- [Offline verifier and renderer](../scripts/build_jev_native_prompt_findings.py)',
              '- [Verifier tests](../tests/test_build_jev_native_prompt_findings.py)',
              '- [P1 frozen manifest](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p1-choice-v1.json)',
              '- [P2 frozen manifest](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1.json)',
              '- [P1 fresh1 raw attempts](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p1-choice-v1/fresh1/attempts.jsonl)',
              '- [P1 fresh2 raw attempts](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p1-choice-v1/fresh2/attempts.jsonl)',
              '- [P2 fresh1 raw attempts](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1/fresh1/attempts.jsonl)',
              '- [P2 fresh2 raw attempts](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1/fresh2/attempts.jsonl)',
              '- [P2 fresh2 terminal record](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1/fresh2/terminal-public.json)',
              '- [P2 fresh2 cost reconciliation](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1/fresh2/budget-reconciliation.json)',
              '- [P2 fresh2 unknown-cost raw evidence](../results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1/fresh2/unknown-cost-evidence.jsonl)',
              '- [Frozen provisional references](../data/pilot/proposed_labels.jsonl)', '']
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
    print('Jev native P1/P2 offline findings verified')


if __name__ == '__main__':
    main()
