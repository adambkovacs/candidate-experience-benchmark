#!/usr/bin/env python3
"""Build the offline Jev native-Choice three-pass findings from saved evidence."""
import argparse
import base64
from collections import Counter
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path

import build_repeat_findings as shared
from development_benchmark import ROOT, KEYS, digest
from jev_benchmark import PRICE_MODEL, PRICE_PER_MILLION_INPUT, parse_response, usage_cost
import jev_native_prompt_variants_v1 as native
import typesafe_repeat_execution as execution
import typesafe_repeat_study as study

BASE = Path('results/repeatability-v1/typesafe-jev113-v2')
LABELS = Path('data/pilot/proposed_labels.jsonl')
PASSES = ('original', 'repeat2', 'repeat3')
CONDITIONS = ('P0', 'P1', 'P2')
FIELDS = shared.FIELDS


def checked(relative):
    path = (ROOT / relative).resolve()
    path.relative_to(ROOT.resolve())
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    raw = Path(path).read_bytes()
    if raw and (not raw.endswith(b'\n') or any(not line.strip() for line in raw.splitlines())):
        raise ValueError('Incomplete Jev evidence: ' + str(path))
    return [json.loads(line) for line in raw.splitlines()]


def evidence_binder():
    bindings = []
    def bind(relative, expected=None):
        path = checked(relative)
        actual = sha(path)
        if expected is not None and actual != expected:
            raise ValueError('Jev source hash changed: ' + str(relative))
        item = {'path': str(path.relative_to(ROOT)), 'sha256': actual}
        if item not in bindings:
            bindings.append(item)
        return item
    return bind, bindings


def frozen_context(bind):
    frozen_path = checked(BASE / 'frozen-plan.json')
    frozen = execution.load_frozen(frozen_path)
    bind(BASE / 'frozen-plan.json')
    bind(BASE / 'admission-draft.json', frozen['draft_sha256'])
    review = json.loads(checked(BASE / 'freeze-review.json').read_text())
    if review != {'kind': 'typesafe-repeat-freeze-review-v1',
                  'draft_sha256': frozen['draft_sha256'],
                  'controller_sha256': frozen['controller_sha256'], 'reviewed': True}:
        raise ValueError('Jev freeze review differs')
    bind(BASE / 'freeze-review.json', frozen['freeze_review_sha256'])
    for item in frozen['plan']['source_bindings']:
        bind(item['path'], item['sha256'])
    bind('scripts/typesafe_repeat_execution.py', frozen['controller_sha256'])
    return frozen


def ledger_context(frozen, bind):
    events = rows(native.LEDGER)
    if not events or events[0] != {'event': 'budget', 'cap_usd': '1'}:
        raise ValueError('Shared Jev ledger cap changed')
    reserves, settlements = {}, {}
    for event in events[1:]:
        attempt = event.get('attempt_id')
        if event['event'] == 'reserve':
            if attempt in reserves:
                raise ValueError('Duplicate Jev reservation')
            value = Decimal(event['usd'])
            if not value.is_finite() or value <= 0:
                raise ValueError('Invalid Jev reservation')
            reserves[attempt] = value
        elif event['event'] == 'settle':
            if attempt not in reserves or attempt in settlements:
                raise ValueError('Invalid Jev settlement')
            value = Decimal(event['usd'])
            if not value.is_finite() or value < 0:
                raise ValueError('Invalid Jev settlement')
            settlements[attempt] = value
        else:
            raise ValueError('Unexpected Jev ledger event')
    pending = set(reserves) - set(settlements)
    historical_unknown = frozen['plan']['historical_selection']['P0']['failed_attempt_id']
    if pending != {historical_unknown}:
        raise ValueError('Unreviewed Jev pending charge')
    accounted = sum((settlements.get(key, bound) for key, bound in reserves.items()), Decimal(0))
    if accounted > Decimal(1):
        raise ValueError('Jev ledger exceeds $1 cap')
    binding = bind(native.LEDGER.relative_to(ROOT))
    return reserves, settlements, {'capUsd': '1', 'accountedUsd': str(accounted),
                                   'remainingUsd': str(Decimal(1) - accounted),
                                   'historicalUnknownReservationUsd': str(reserves[historical_unknown]),
                                   'pendingAttemptCount': 1, 'evidence': binding}


def usage(attempts):
    values = []
    for row in attempts:
        raw = row.get('raw_response')
        item = raw.get('usage') if isinstance(raw, dict) else None
        values.append(item if isinstance(item, dict) else {})
    tokens = {}
    for name, key in (('input_tokens', 'input_tokens'), ('output_tokens', 'output_tokens'),
                      ('reasoning_output_tokens', 'reasoning_tokens')):
        items = [x.get(key) for x in values]
        tokens[name] = sum(items) if items and all(type(x) is int and x >= 0 for x in items) else None
    estimated = [usage_cost(row['raw_response']) if isinstance(row.get('raw_response'), dict) else None
                 for row in attempts]
    client = [row.get('client_http_call_seconds') for row in attempts]
    return {'requestCount': len(attempts), 'startedRequestCount': len(attempts),
            'clientHttpCallSeconds': client,
            'clientHttpCallSecondsTotal': sum(client) if client and all(type(x) in (int, float) and x >= 0 for x in client) else None,
            'inferenceSeconds': None, 'tokens': tokens,
            'estimatedTokenPriceCostUsd': str(sum((x for x in estimated if x is not None), Decimal(0))),
            'unknownCostCount': sum(x is None for x in estimated),
            'actualCostUsd': None,
            'costNote': 'Reported input tokens at the saved $0.042/M rate; actual provider invoice and server inference time unavailable. Unknown charges are not zero.'}


def historical(frozen, reserves, settlements, bind):
    manifest, manifest_sha = native.read_frozen_manifest(study.BASE / 'input-only-manifest.json')
    if manifest_sha != frozen['plan']['source_bindings'][0]['sha256']:
        raise ValueError('Historical Jev manifest changed')
    first_p0, all_p0 = study.historical_p0(manifest)
    variants = study.historical_variants(manifest, manifest_sha)
    study.historical_p0_smoke(manifest)
    all_rows = [*all_p0, *(r for pair in variants.values() for phase in pair for r in phase),
                *study.lines(study.P0_SMOKE)]
    # Reuse the original audit's strict reserve/settlement comparison without its
    # initial single-pending-only condition, which would reject new settled calls.
    study.ledger_snapshot(all_rows)
    indexed = {'P0': first_p0, 'P1': variants['P1'][1], 'P2': variants['P2'][1]}
    result = {}
    for condition, selected in indexed.items():
        if [r['id'] for r in selected] != study.IDS:
            raise ValueError('Historical Jev first-attempt coverage differs')
        for row in selected:
            attempt = row['budget_attempt_id']
            if reserves[attempt] != Decimal(row['reserved_cost_usd']):
                raise ValueError('Historical Jev reserve differs')
            cost = row.get('estimated_usage_cost_usd')
            if cost is None:
                if attempt in settlements:
                    raise ValueError('Historical unknown Jev charge was settled')
            elif settlements.get(attempt) != Decimal(cost):
                raise ValueError('Historical Jev settlement differs')
        evidence = {}
        paths = ([study.P0_PREFIX, study.P0_CONTINUATION] if condition == 'P0' else
                 [study.BASE / f'{condition}-development.jsonl', study.BASE / f'{condition}-development.attempts.jsonl'])
        for index, path in enumerate(paths):
            evidence['source' + str(index + 1)] = bind(path.relative_to(ROOT))
        result[condition] = (selected, evidence)
    return result, {row['budget_attempt_id'] for row in all_rows}


def phase_status(repeat, condition, phase):
    folder = checked(BASE / repeat / condition)
    claims = sorted(folder.glob(f'{phase}-*.claim.json')) if folder.exists() else []
    if not claims:
        return 'missing'
    for claim in claims:
        journal = claim.with_name(claim.name.replace('.claim.json', '.journal.jsonl'))
        if not journal.exists():
            return 'open'
        try:
            events = rows(journal)
        except (ValueError, OSError):
            return 'open'
        if not events or events[-1].get('event') != 'terminal':
            return 'open'
    return 'terminal'


def repeat_phase(frozen, repeat, condition, phase, reserves, settlements, bind):
    if phase_status(repeat, condition, phase) != 'terminal':
        return None
    ids = study.SMOKE_IDS if phase == 'smoke' else study.IDS
    observed, claims = execution.stage_history(execution.BASE, repeat, condition, phase)
    if observed != ids:
        return None
    data, all_attempts, evidence = [], [], {}
    manifest, manifest_sha = native.read_frozen_manifest(study.BASE / 'input-only-manifest.json')
    input_rows, policy = native.load_inputs(), native.load_policy()
    for stage, claim_path in enumerate(claims):
        paths = execution.stage_paths(execution.BASE, repeat, condition, phase, stage)
        claim = json.loads(claim_path.read_text())
        if (claim.get('kind') != 'typesafe-repeat-stage-claim-v1' or
                claim.get('frozen_sha256') != sha(checked(BASE / 'frozen-plan.json')) or
                (claim.get('repeat'), claim.get('condition'), claim.get('phase'), claim.get('stage')) !=
                (repeat, condition, phase, stage)):
            raise ValueError('Jev phase claim differs from frozen identity')
        review_path = claim_path.with_name(f'{phase}-{stage:03}.review.json')
        review = json.loads(review_path.read_text())
        expected = {'kind': 'typesafe-repeat-phase-review-v1',
                    'frozen_sha256': claim['frozen_sha256'],
                    'controller_sha256': frozen['controller_sha256'], 'repeat': repeat,
                    'condition': condition, 'phase': phase, 'stage': stage,
                    'start_index': claim['start_index'],
                    'price_page_sha256': review.get('price_page_sha256'), 'reviewed': True}
        if (review != expected or not isinstance(review['price_page_sha256'], str) or
                len(review['price_page_sha256']) != 64 or sha(review_path) != claim['review_sha256']):
            raise ValueError('Jev reviewed pricing admission differs')
        for key in ('claim.json', 'journal.jsonl', 'attempts.jsonl'):
            evidence[f'{phase}Stage{stage}{key}'] = bind(paths[key].relative_to(ROOT))
        evidence[f'{phase}Stage{stage}Review'] = bind(review_path.relative_to(ROOT))
        for row in rows(paths['attempts.jsonl']):
            rid = row['id']
            index = int(rid[4:]) - 1
            payload = native.payload(input_rows[index]['feedback'], policy, condition)
            expected_request = manifest['requests'][condition][index]
            frozen_request = frozen['plan']['future_passes'][0 if repeat == 'repeat2' else 1]['conditions'][condition]['requests'][index]
            request_sha = digest(json.dumps(payload, sort_keys=True))
            if (row.get('request') != payload or expected_request != frozen_request or
                    expected_request != {'id': rid, 'request_sha256': request_sha,
                                         'reserve_usd': str(execution.reserve_cost(payload))} or
                    row.get('request_sha256') != request_sha or row.get('manifest_sha256') != manifest_sha or
                    (row.get('repeat'), row.get('condition'), row.get('phase'), row.get('stage')) !=
                    (repeat, condition, phase, stage) or
                    row.get('requested_model') != PRICE_MODEL or row.get('reference_labels_read') is not False or
                    row.get('request_timeout_seconds') != 120 or row.get('retry_policy') != 'none' or
                    row.get('price_per_million_input_usd') != str(PRICE_PER_MILLION_INPUT) or
                    row.get('question_order') != list(KEYS) or
                    row.get('question_version') != frozen['plan']['controls']['question_version'] or
                    row.get('input_sha256') != digest(input_rows[index]['feedback']) or
                    row.get('policy_sha256') != digest(policy)):
                raise ValueError('Jev repeat attempt request controls differ')
            attempt = row['budget_attempt_id']
            cost = row.get('estimated_usage_cost_usd')
            if (reserves.get(attempt) != Decimal(row['reserved_cost_usd']) or
                    (cost is not None and settlements.get(attempt) != Decimal(cost)) or
                    (cost is None and attempt in settlements)):
                raise ValueError('Jev repeat budget evidence differs')
            raw_path = claim_path.parent / row['raw_path']
            raw_record = json.loads(raw_path.read_text())
            raw = base64.b64decode(raw_record['raw_base64'], validate=True)
            if (sha_bytes(raw) != row['raw_sha256'] or raw_record['attempt_id'] != attempt or
                    raw_record['request_sha256'] != request_sha or
                    raw_record.get('token_redacted') != row.get('token_redacted')):
                raise ValueError('Jev repeat raw attribution differs')
            evidence[f'{phase}Raw{stage}-{rid}'] = bind(raw_path.relative_to(ROOT))
            body = None
            if row.get('http_status') == 200 and not row.get('transport_error') and not row.get('read_error'):
                try:
                    body = json.loads(raw)
                except (ValueError, UnicodeDecodeError):
                    pass
            if body != row.get('raw_response'):
                raise ValueError('Jev parsed response differs from raw bytes')
            observed_cost = usage_cost(body) if isinstance(body, dict) else None
            if row.get('estimated_usage_cost_usd') != (str(observed_cost) if observed_cost is not None else None):
                raise ValueError('Jev reported usage cost differs')
            if row.get('returned_model') != (body.get('model') if isinstance(body, dict) else None):
                raise ValueError('Jev returned model differs')
            raw_usage = body.get('usage') if isinstance(body, dict) else None
            if (row.get('usage') != raw_usage or
                    row.get('reported_input_tokens') != (raw_usage.get('input_tokens') if isinstance(raw_usage, dict) else None) or
                    row.get('reported_output_tokens') != (raw_usage.get('output_tokens') if isinstance(raw_usage, dict) else None) or
                    row.get('reported_reasoning_tokens') != (raw_usage.get('reasoning_tokens') if isinstance(raw_usage, dict) else None)):
                raise ValueError('Jev usage fields differ from raw response')
            duration = row.get('client_http_call_seconds')
            if type(duration) not in (int, float) or not math.isfinite(duration) or duration < 0:
                raise ValueError('Jev client timing is invalid')
            if isinstance(body, dict) and body.get('model') != PRICE_MODEL:
                expected_status, prediction = 'identity_violation', None
            elif row.get('http_status') != 200 or row.get('transport_error') or row.get('read_error'):
                expected_status, prediction = 'service_error', None
            else:
                try:
                    prediction = parse_response(body, PRICE_MODEL)
                except (ValueError, TypeError, KeyError, IndexError):
                    expected_status, prediction = 'invalid_output', None
                else:
                    expected_status = 'ok'
            if row.get('status') != expected_status or row.get('prediction') != prediction:
                raise ValueError('Jev outcome differs from saved raw response')
            if row.get('cost_unknown') is not (observed_cost is None) or row.get('actual_charge_usd') is not None or row.get('provider_inference_seconds') is not None:
                raise ValueError('Jev billing or timing truth changed')
            data.append(row)
            all_attempts.append(attempt)
    if len(set(all_attempts)) != len(all_attempts):
        raise ValueError('Reused Jev repeat attempt identity')
    return data, evidence


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def stats(values):
    return {'completedPasses': len(values), 'values': values,
            'mean': sum(values) / len(values) if len(values) == 3 else None,
            'range': [min(values), max(values)] if len(values) == 3 else None}


def build():
    bind, sources = evidence_binder()
    bind('scripts/build_typesafe_repeat_findings.py')
    bind('scripts/build_repeat_findings.py')
    bind(LABELS, shared.PINNED_SHA[str(LABELS)])
    label_rows = rows(checked(LABELS))
    ids = [x['id'] for x in label_rows]
    if ids != study.IDS or any(x.get('review_version') != '0.2' for x in label_rows):
        raise ValueError('Expected exact 60 provisional Jev references')
    labels = {x['id']: x['proposed_labels'] for x in label_rows}
    frozen = frozen_context(bind)
    reserves, settlements, budget = ledger_context(frozen, bind)
    history, historical_attempt_ids = historical(frozen, reserves, settlements, bind)
    indexed, data = {name: {} for name in PASSES}, {name: {} for name in PASSES}
    repeat_attempt_ids = set()
    for condition in CONDITIONS:
        selected, evidence = history[condition]
        indexed['original'][condition] = {x['id']: x for x in selected}
        data['original'][condition] = {'completionStatus': 'complete',
                                       'score': shared.score(indexed['original'][condition], labels, ids),
                                       'usage': usage(selected), 'evidence': evidence}
    missing = []
    for repeat in ('repeat2', 'repeat3'):
        for condition in CONDITIONS:
            smoke = repeat_phase(frozen, repeat, condition, 'smoke', reserves, settlements, bind)
            if smoke is None or len(smoke[0]) != 3 or any(x['status'] != 'ok' for x in smoke[0]):
                missing.append({'pass': repeat, 'condition': condition, 'status': 'smoke_open_or_incomplete'})
                continue
            inspection_path = BASE / repeat / condition / 'smoke-inspection.json'
            inspection = json.loads(checked(inspection_path).read_text())
            if inspection != {'kind': 'typesafe-repeat-smoke-inspection-v1',
                              'smoke_attempts_sha256': sha(checked(BASE / repeat / condition / 'smoke-000.attempts.jsonl')),
                              'reviewed': True}:
                raise ValueError('Jev smoke inspection differs')
            bind(inspection_path)
            phase = repeat_phase(frozen, repeat, condition, 'development', reserves, settlements, bind)
            if phase is None or len(phase[0]) != 60:
                missing.append({'pass': repeat, 'condition': condition, 'status': 'development_open_or_incomplete'})
                continue
            attempts, evidence = phase
            for row in (*smoke[0], *attempts):
                attempt = row['budget_attempt_id']
                if attempt in historical_attempt_ids or attempt in repeat_attempt_ids:
                    raise ValueError('Jev attempt reused across historical or repeat phases')
                repeat_attempt_ids.add(attempt)
            indexed[repeat][condition] = {x['id']: x for x in attempts}
            data[repeat][condition] = {'completionStatus': 'complete',
                                       'score': shared.score(indexed[repeat][condition], labels, ids),
                                       'usage': usage(attempts),
                                       'evidence': {**smoke[1], **evidence, 'smokeInspection': bind(inspection_path)}}
    def full(name, condition):
        return condition in data[name]
    if all(full(name, condition) for name in PASSES for condition in CONDITIONS):
        prefix = native.LEDGER.read_bytes()[:frozen['ledger_prefix_length']]
        prefix_ids = {x['attempt_id'] for x in (json.loads(line) for line in prefix.splitlines())
                      if x.get('event') == 'reserve'}
        if set(reserves) - prefix_ids != repeat_attempt_ids:
            raise ValueError('Jev ledger has an unreported post-freeze reservation')
    deltas = []
    for name in PASSES:
        for target in ('P1', 'P2'):
            if full(name, 'P0') and full(name, target):
                a, b = data[name]['P0']['score'], data[name][target]['score']
                deltas.append({'pass': name, 'from': 'P0', 'to': target, 'denominator': 60,
                               'allFour': b['allFour'] - a['allFour'],
                               'fields': {f: b['fields'][f] - a['fields'][f] for f in FIELDS}})
    spread = {}
    for target in ('P1', 'P2'):
        entries = [x for x in deltas if x['to'] == target]
        spread[target] = {'completedPairs': len(entries), 'allFourValues': [x['allFour'] for x in entries],
                          'allFourRange': [min(x['allFour'] for x in entries), max(x['allFour'] for x in entries)] if len(entries) == 3 else None,
                          'fieldRanges': {f: [min(x['fields'][f] for x in entries), max(x['fields'][f] for x in entries)] if len(entries) == 3 else None for f in FIELDS}}
    flips, ranges, across = [], {}, {}
    for condition in CONDITIONS:
        for i, left in enumerate(PASSES):
            for right in PASSES[i+1:]:
                if full(left, condition) and full(right, condition):
                    flips.append({'condition': condition, 'from': left, 'to': right,
                                  **shared.flip(indexed[left][condition], indexed[right][condition], ids)})
        scores = [data[name][condition]['score'] for name in PASSES if full(name, condition)]
        ranges[condition] = {'allFour': stats([x['allFour'] for x in scores]),
                             'fields': {f: stats([x['fields'][f] for x in scores]) for f in FIELDS}}
        if all(full(name, condition) for name in PASSES):
            eligible = [rid for rid in ids if all(shared.outcome(indexed[name][condition][rid]) == 'valid' for name in PASSES)]
            across[condition] = {'denominator': len(eligible), 'excludedIds': [rid for rid in ids if rid not in eligible],
                                 'fields': {f: [rid for rid in eligible if len({indexed[name][condition][rid]['prediction'][f] for name in PASSES}) > 1] for f in FIELDS},
                                 'fourFieldVector': [rid for rid in eligible if len({tuple(indexed[name][condition][rid]['prediction'][f] for f in FIELDS) for name in PASSES}) > 1]}
    return {'schema': 'typesafe-repeat-series-v1', 'series': [{
        'schema': 'typesafe-repeat-findings-v1', 'configuration': 'typesafe-jev113-v2',
        'displayName': 'TypeSafe Jev 1.13.0 · native four-Choice API', 'model': PRICE_MODEL,
        'provider': 'TypeSafe', 'method': 'native-choice',
        'referenceVersion': '0.2', 'referenceStatus': 'AI reviewed provisional, not independent adjudication',
        'referenceClassCounts': {f: dict(sorted(Counter(labels[rid][f] for rid in ids).items())) for f in FIELDS},
        'denominator': 60, 'completedConditions': sum(full(name, c) for name in PASSES for c in CONDITIONS),
        'plannedConditions': 9, 'missingPasses': missing, 'passes': data,
        'threePassSummary': ranges, 'pairwiseFlips': flips, 'changesAcrossThreePasses': across,
        'withinPassPromptDeltas': deltas, 'pairedDeltaSpread': spread,
        'budget': budget, 'sourceBindings': sources,
        'limitations': ['Jev uses four typed Choice questions; these are native instruction variants, not chat-message prompts.',
                        'The original P0 pass retains the failed first DEV-046 attempt. Its later manual success is excluded.',
                        'Invalid distributions and service errors remain in the 60-record denominator; flips use only records valid in both compared passes.',
                        'Provider invoice, server inference duration, serving revision and seed are unavailable.',
                        'Estimated cost uses reported input tokens and saved published price; the historical unknown charge retains its reserved upper bound.']
    }]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    content = json.dumps(build(), indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if not args.output.exists() or args.output.read_text() != content:
            raise ValueError('Stale Jev repeat report: ' + str(args.output))
    else:
        with args.output.open('x') as out:
            out.write(content)
    print(args.output)


if __name__ == '__main__':
    main()
