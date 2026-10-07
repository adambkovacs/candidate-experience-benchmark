#!/usr/bin/env python3
"""Build explorer run rows from closed public native-decision reports."""

import argparse
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path

from development_benchmark import ROOT, VALUES
import build_liquid_d1_native_full_aggregate as liquid_builder
import build_solar_decide_native_first_pass_findings as solar_builder
import build_solar_decide_native_full_findings as solar_full_builder
import build_tev_native_full_findings as tev_builder
import build_clef_openrouter_findings as clef_builder


OUTPUT = Path('public-site/supplemental-decision-runs-v1.json')
SOLAR = Path('public-site/solar-decide-first-pass-findings.json')
SOLAR_FULL = Path('public-site/solar-decide-full-findings.json')
LIQUID = Path('public-site/liquid-d1-native-full-findings.json')
TEV = Path('public-site/tev-native-full-findings.json')
CLEF_OPENROUTER = clef_builder.OUTPUT
PERPLEXITY_PROJECTION = Path('results/perplexity-decider-v1/full-v2/public-projection.json')
PERPLEXITY_FINDINGS = Path('results/perplexity-decider-v1/full-v2/findings.json')
PERPLEXITY_ROUTE_PLAN = Path('results/perplexity-decider-v1/plan.json')
PERPLEXITY_FULL_PLAN = Path('results/perplexity-decider-v1/full-v2/plan.json')
PERPLEXITY_LABELS = Path('data/pilot/proposed_labels.jsonl')
PERPLEXITY_MODEL = 'perplexity/pplx-decider-v1-27b'
PERPLEXITY_RETURNED = 'perplexity/pplx-decider-v1-27b-20261001'
BASE_URL = 'https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/'
FIELDS = ('sentiment', 'follow_up_needed', 'serious_concern_reported', 'testimonial_potential')
PASSES = ('fresh1', 'fresh2', 'fresh3')
CONDITIONS = ('P0', 'P1', 'P2')
NINE = tuple(f'{repeat}/{condition}' for repeat in PASSES for condition in CONDITIONS)
THREE = NINE[:3]
PRIVATE_NAMES = ('raw', 'parsed', 'attempts', 'journal', 'budget', 'private')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(root, path):
    return json.loads((root / path).read_text())


def bounded_count(value, label):
    if type(value) is not int or not 0 <= value <= 60:
        raise ValueError(f'{label} must be an integer out of 60')
    return value


def amount(value, label):
    try:
        result = Decimal(value)
    except (InvalidOperation, TypeError):
        raise ValueError(f'{label} is not decimal') from None
    if not result.is_finite() or result < 0:
        raise ValueError(f'{label} is not a nonnegative finite charge')
    return float(result)


def usage(input_tokens, output_tokens, reported_requests=60):
    if any(type(value) is not int or value < 0 for value in (input_tokens, output_tokens)):
        raise ValueError('Native token count differs')
    if type(reported_requests) is not int or not 0 <= reported_requests <= 60:
        raise ValueError('Native usage request count differs')
    return {'input': input_tokens, 'output': output_tokens,
            'cachedInput': None, 'cacheWrite': None, 'reasoning': None,
            'reportedRequests': reported_requests, 'totalRequests': 60,
            'complete': reported_requests == 60,
            'note': 'Provider-reported development usage covers the returned answers only. Missing token categories are unavailable, not zero.'}


def row(family, model, returned_model, provider, stages, stage, scores, input_tokens,
        output_tokens, charge, projection_path, projection_sha, report_path, *,
        valid=60, unknown_upper_bound='0', result_status=None,
        client_elapsed_available=None, client_elapsed_ns_sum=None):
    if stage not in stages or len(stage.split('/')) != 2:
        raise ValueError('Unexpected native stage')
    repeat, condition = stage.split('/')
    if repeat not in PASSES or condition not in CONDITIONS:
        raise ValueError('Unexpected prompt or pass')
    prefix = f'{family}-native-{repeat}'
    ident = f'{prefix}-{condition.lower()}'
    fields = {key: bounded_count(scores[key], stage + '/' + key) for key in FIELDS}
    all_four = bounded_count(scores['all_four'], stage + '/all_four')
    valid = bounded_count(valid, stage + '/valid')
    if any(score > valid for score in (all_four, *fields.values())):
        raise ValueError('Native score exceeds usable answers')
    unknown = amount(unknown_upper_bound, stage + '/unknown bound')
    if valid == 60 and unknown:
        raise ValueError('Complete native run has unknown-cost attempt')
    if valid < 60 and not unknown:
        raise ValueError('Interrupted native run lacks retained unknown bound')
    if (client_elapsed_available is None) != (client_elapsed_ns_sum is None):
        raise ValueError('Partial native client timing differs')
    if client_elapsed_available is not None:
        if (type(client_elapsed_available) is not int or
                client_elapsed_available != valid or
                type(client_elapsed_ns_sum) is not int or client_elapsed_ns_sum < 0):
            raise ValueError('Native client timing coverage differs')
    client_seconds = (None if client_elapsed_ns_sum is None else
                      float(Decimal(client_elapsed_ns_sum) / Decimal(1_000_000_000)))
    if not projection_path.parts or any(part in PRIVATE_NAMES for part in projection_path.parts):
        raise ValueError('Private source path cannot be published')
    if len(projection_sha) != 64 or any(ch not in '0123456789abcdef' for ch in projection_sha):
        raise ValueError('Public projection digest differs')
    return {
        'id': ident, 'experimentId': f'{family}-native-{repeat}-p0',
        'parentBaselineId': None if condition == 'P0' else f'{prefix}-p0',
        'protocolId': f'{family}-native-choice-v1', 'repeatPass': repeat,
        'model': model, 'returnedModel': returned_model, 'provider': provider,
        'interface': 'four native Choice questions', 'effort': 'not applicable',
        'surface': 'OpenRouter native Choice', 'condition': condition,
        'complete': valid == 60, 'records': 60,
        'savedResponses': valid, 'valid': valid,
        'metrics': {'all_four': all_four, **fields}, 'pairedEligible': valid == 60,
        'resultStatus': result_status or ('First pass only; later Solar repeats are separate. '
                         'The linked report has source-backed paired changes.' if family == 'solar-decide'
                         else 'Closed native-choice repeat. The linked report has source-backed paired and repeat comparisons.'),
        'timing': {'kind': 'record', 'requests': client_elapsed_available or 0,
                   'totalRequests': 60, 'medianSeconds': None, 'p95Seconds': None,
                   'totalSeconds': client_seconds,
                   'inferenceSeconds': None, 'inferenceReportedRequests': 0,
                   'note': ('Client request elapsed sum covers returned answers only. It includes transport and service time, not isolated inference time; per-request percentiles are unavailable.'
                            if client_elapsed_available is not None else
                            'No public client-duration series or server inference duration is available for this run.')},
        'tokens': usage(input_tokens, output_tokens, valid),
        'cost': {'actualUsd': None, 'knownUsd': amount(charge, stage + '/cost'),
                 'estimatedUsd': None, 'unknownUpperBoundUsd': unknown,
                 'note': 'Known development inference charge covers returned answers only; smoke tests excluded. Unknown-cost bounds are retained separately, and no invoice amount is asserted.'},
        'sourceOnlyDetails': True, 'sourceRecordsUrl': BASE_URL + str(projection_path),
        'sourceRecordSha256': projection_sha, 'evidenceUrl': BASE_URL + str(report_path),
    }


def verify_report(root, path, expected):
    saved = load(root, path)
    if saved != expected:
        raise ValueError(f'Published native report differs from closed sources: {path}')
    return saved


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False).encode()).hexdigest()


def perplexity_runs(root, source=None):
    """Use only committed public artifacts; private raw remains outside Git."""
    root = Path(root).resolve()
    if source is None:
        def source(path, expected):
            actual = sha(root / path)
            if actual != expected:
                raise ValueError(f'Perplexity public source differs: {path}')
            return actual
    projection = load(root, PERPLEXITY_PROJECTION)
    findings = load(root, PERPLEXITY_FINDINGS)
    route_plan = load(root, PERPLEXITY_ROUTE_PLAN)
    full_plan = load(root, PERPLEXITY_FULL_PLAN)
    labels_path = root / PERPLEXITY_LABELS
    labels = [json.loads(line) for line in labels_path.read_text().splitlines() if line.strip()]
    ids = [f'DEV-{index:03}' for index in range(1, 61)]
    if ([item.get('id') for item in labels] != ids or
            findings.get('schema') != 'perplexity-decider-native-findings-v1' or
            projection.get('schema') != 'perplexity-decider-native-public-projection-v1' or
            projection.get('model') != PERPLEXITY_MODEL or
            projection.get('returned_model') != PERPLEXITY_RETURNED or
            projection.get('provider') != 'Perplexity' or
            projection.get('reference_labels_sent') is not False or
            projection.get('private_raw_checked_at_prepare') is not True or
            findings.get('reference_status') != 'proposed_labels_not_final_adjudication' or
            findings.get('reference_sha256') != {str(PERPLEXITY_LABELS): sha(labels_path)} or
            findings.get('projection_sha256') != source(PERPLEXITY_PROJECTION,
                                                        findings.get('projection_sha256')) or
            projection.get('route_plan_sha256') != canonical_sha(route_plan) or
            projection.get('full_plan_sha256') != canonical_sha(full_plan) or
            route_plan.get('models', {}).get('decider', {}).get('model') != PERPLEXITY_MODEL or
            route_plan['models']['decider'].get('expected_returned_model') != PERPLEXITY_RETURNED or
            full_plan.get('models', {}).get('decider', {}).get('stages') != list(NINE) or
            findings.get('development_stages_closed') != 9 or
            findings.get('development_valid') != 540 or findings.get('development_planned') != 540 or
            findings.get('smoke_valid') != 27 or
            findings.get('unknown_cost_upper_bound_usd') != '0' or
            len(projection.get('stages', [])) != 9 or len(findings.get('scores', [])) != 9 or
            findings.get('repeat_identical_by_condition') != {condition: True for condition in CONDITIONS}):
        raise ValueError('Perplexity public source identity or coverage differs')
    source(PERPLEXITY_FINDINGS, sha(root / PERPLEXITY_FINDINGS))
    source(PERPLEXITY_ROUTE_PLAN, sha(root / PERPLEXITY_ROUTE_PLAN))
    source(PERPLEXITY_FULL_PLAN, sha(root / PERPLEXITY_FULL_PLAN))
    source(PERPLEXITY_LABELS, sha(labels_path))
    refs = {item['id']: item['proposed_labels'] for item in labels}
    charges = Decimal(0)
    smokes = Decimal(0)
    runs = []
    predictions = {}
    for stage, item, score in zip(NINE, projection['stages'], findings['scores']):
        condition = stage.split('/')[1]
        expected_requests = route_plan['models']['decider']['requests'][condition]
        records = item.get('records')
        if (item.get('stage') != stage or item.get('status') != 'closed' or
                item.get('development_count') != 60 or item.get('smoke_count') != 3 or
                not isinstance(records, list) or [record.get('id') for record in records] != ids or
                score.get('stage') != stage or score.get('denominator') != 60 or
                score.get('valid') != 60 or
                [request.get('id') for request in expected_requests] != ids or
                item.get('smoke_inspection_sha256') !=
                item.get('source_sha256', {}).get(
                    str((Path('results/perplexity-decider-v1/decider/fresh1/P0') if stage == 'fresh1/P0'
                         else Path('results/perplexity-decider-v1/full-v2/decider') / stage) /
                        'smoke.root-inspection.json'))):
            raise ValueError(f'Perplexity closed stage differs: {stage}')
        stage_cost = Decimal(0)
        input_tokens = output_tokens = 0
        predictions[stage] = {}
        for record, request in zip(records, expected_requests):
            prediction = record.get('prediction')
            if (set(record) != {'id', 'prediction', 'input_tokens', 'output_tokens',
                                'actual_cost_usd', 'request_sha256', 'response_sha256'} or
                    record.get('request_sha256') != request['payload_sha256'] or
                    not isinstance(prediction, dict) or set(prediction) != set(FIELDS) or
                    any(prediction[field] not in VALUES[field] for field in FIELDS) or
                    type(record.get('input_tokens')) is not int or record['input_tokens'] < 0 or
                    type(record.get('output_tokens')) is not int or record['output_tokens'] < 0 or
                    not isinstance(record.get('response_sha256'), str) or
                    len(record['response_sha256']) != 64 or
                    any(ch not in '0123456789abcdef' for ch in record['response_sha256'])):
                raise ValueError(f'Perplexity public record differs: {stage}/{record.get("id")}')
            charge = Decimal(str(record['actual_cost_usd']))
            if charge != Decimal(record['input_tokens']) * Decimal('0.00000004'):
                raise ValueError(f'Perplexity known cost differs: {stage}/{record["id"]}')
            stage_cost += charge
            input_tokens += record['input_tokens']
            output_tokens += record['output_tokens']
            predictions[stage][record['id']] = prediction
        fields = {field: sum(predictions[stage][ident][field] == refs[ident][field]
                             for ident in ids) for field in FIELDS}
        all_four = sum(all(predictions[stage][ident][field] == refs[ident][field]
                           for field in FIELDS) for ident in ids)
        mismatches = [ident for ident in ids if any(predictions[stage][ident][field] != refs[ident][field]
                                                    for field in FIELDS)]
        if (score.get('field_correct') != fields or score.get('all_four_correct') != all_four or
                score.get('mismatch_ids') != mismatches or
                Decimal(str(item.get('known_development_cost_usd'))) != stage_cost):
            raise ValueError(f'Perplexity public score or stage cost differs: {stage}')
        smoke_cost = Decimal(str(item.get('known_smoke_cost_usd')))
        if smoke_cost <= 0:
            raise ValueError(f'Perplexity smoke charge differs: {stage}')
        charges += stage_cost
        smokes += smoke_cost
        scores = {'all_four': all_four, **fields}
        runs.append(row('perplexity-decider', PERPLEXITY_MODEL, PERPLEXITY_RETURNED,
                        'Perplexity', NINE, stage, scores, input_tokens, output_tokens,
                        str(stage_cost), PERPLEXITY_PROJECTION,
                        findings['projection_sha256'], PERPLEXITY_FINDINGS,
                        result_status='Closed Perplexity native Choice run. Scores compare with provisional reference labels; linked records support prompt and repeat comparisons.'))
    if (any(predictions[f'fresh1/{condition}'] != predictions[f'{repeat}/{condition}']
            for condition in CONDITIONS for repeat in PASSES[1:]) or
            Decimal(str(findings.get('known_development_cost_usd'))) != charges or
            Decimal(str(findings.get('known_smoke_cost_usd'))) != smokes or
            Decimal(str(findings.get('known_total_cost_usd'))) != charges + smokes):
        raise ValueError('Perplexity repeat or cost totals differ')
    sealed = projection.get('sealed_budget_children', {})
    if (Decimal(str(sealed.get('initial_smoke', {}).get('known_actual_usd'))) !=
            Decimal(str(projection['stages'][0]['known_smoke_cost_usd'])) or
            Decimal(str(sealed.get('full_v2', {}).get('known_actual_usd'))) !=
            charges + smokes - Decimal(str(projection['stages'][0]['known_smoke_cost_usd'])) or
            sealed['initial_smoke'].get('unknown_upper_bound_usd') != '0' or
            sealed['full_v2'].get('unknown_upper_bound_usd') != '0'):
        raise ValueError('Perplexity sealed budget attestation differs')
    return runs


def build(root=ROOT):
    root = Path(root).resolve()
    solar = verify_report(root, SOLAR, solar_builder.build(root))
    solar_full = verify_report(root, SOLAR_FULL, solar_full_builder.build(root))
    liquid = verify_report(root, LIQUID, liquid_builder.build(root))
    tev = verify_report(root, TEV, tev_builder.build(root))
    clef = verify_report(root, CLEF_OPENROUTER, clef_builder.check(root))
    sources = {str(path): sha(root / path) for path in
               (SOLAR, SOLAR_FULL, LIQUID, TEV, CLEF_OPENROUTER,
                Path('public-site/data-provider-errors-v1.json'),
                Path('scripts/build_supplemental_decision_runs_v1.py'))}
    runs = []

    def source(path, digest):
        actual = sha(root / path)
        if actual != digest:
            raise ValueError(f'Public projection differs from report: {path}')
        sources[str(path)] = actual
        return actual

    if (solar.get('schema') != 'solar-decide-first-pass-findings-v1' or
            solar.get('status') != 'three_closed_first_pass_runs' or
            solar.get('stage_order') != list(THREE) or
            solar.get('development_records') != 180 or solar.get('valid_development_answers') != 180 or
            solar.get('unknown_cost_attempts') != 0 or len(solar.get('stages', [])) != 3):
        raise ValueError('Solar first-pass coverage differs')
    solar_projection = solar_builder.PROJECTION
    solar_digest = source(solar_projection, solar['source_bindings']['projection_sha256'])
    sources[str(solar_builder.RECEIPT)] = sha(root / solar_builder.RECEIPT)
    for expected_stage, item in zip(THREE, solar['stages']):
        if item.get('stage') != expected_stage or item.get('records') != 60 or item.get('valid_answers') != 60:
            raise ValueError('Solar closed stage differs')
        full_item = solar_full['stages'][THREE.index(expected_stage)]
        if full_item.get('stage') != expected_stage:
            raise ValueError('Solar first-pass timing stage differs')
        scores = {'all_four': item['all_four_correct'],
                  **{key: item['fields'][key]['correct'] for key in FIELDS}}
        runs.append(row('solar-decide', solar['configuration']['model'],
                        solar['configuration']['returned_model'], solar['configuration']['provider'],
                        THREE, expected_stage, scores, item['input_tokens'], item['output_tokens'],
                        item['known_development_cost_usd'], solar_projection, solar_digest, SOLAR,
                        client_elapsed_available=full_item['client_elapsed_available'],
                        client_elapsed_ns_sum=full_item['client_elapsed_ns_sum_known_responses']))

    if (solar_full.get('schema') != 'solar-decide-native-full-findings-v1' or
            solar_full.get('status') != 'eight_closed_runs_one_interrupted_with_exact_unsent_suffix' or
            solar_full.get('stage_order') != list(NINE) or
            solar_full.get('development_records') != 540 or
            solar_full.get('valid_development_answers') != 539 or
            solar_full.get('unknown_cost_development_attempts') != 1 or
            solar_full.get('interrupted_stage') != 'fresh3/P2' or
            solar_full.get('interrupted_record_id') != 'DEV-009' or
            len(solar_full.get('stages', [])) != 9 or
            solar_full.get('child_all_requests', {}).get('original_unknown_upper_bound_usd') != '0.10485760'):
        raise ValueError('Solar nine-stage coverage differs')
    if solar_full['configuration'] != {
            'model': solar['configuration']['model'],
            'returned_model': solar['configuration']['returned_model'],
            'provider': solar['configuration']['provider'],
            'interface': 'four native Choice questions'}:
        raise ValueError('Solar configuration differs across reports')
    for kind, rows in (('repeat', solar_full.get('repeat_comparisons')),
                       ('prompt', solar_full.get('matched_prompt_comparisons'))):
        if not isinstance(rows, list) or len(rows) != 9:
            raise ValueError('Solar matched comparison coverage differs')
        for pair in rows:
            final_pair = 'fresh3/P2' in (pair.get('left'), pair.get('right'))
            if (pair.get('kind') != kind or
                    pair.get('paired_records') != (59 if final_pair else 60) or
                    pair.get('excluded_unusable_ids') != (['DEV-009'] if final_pair else [])):
                raise ValueError('Solar matched comparison denominator differs')
    full_projection = solar_full_builder.PROJECTION
    full_digest = source(full_projection, solar_full['source_bindings']['projection_sha256'])
    source(solar_full_builder.RECEIPT,
           solar_full['source_bindings']['projection_receipt_sha256'])
    public_stages = load(root, full_projection)['stages']
    if [item.get('stage') for item in public_stages] != list(NINE):
        raise ValueError('Solar public stage order differs')
    for expected_stage, item, projected in zip(NINE, solar_full['stages'], public_stages):
        final = expected_stage == 'fresh3/P2'
        valid = 59 if final else 60
        expected_ids = [f'DEV-{number:03}' for number in range(1, 61)
                        if not (final and number == 9)]
        if (item.get('stage') != expected_stage or item.get('records') != 60 or
                item.get('valid_answers') != valid or
                item.get('status') != ('interrupted_with_exact_unsent_suffix' if final else 'closed') or
                item.get('unknown_cost_attempts') != int(final) or
                item.get('unusable_ids') != (['DEV-009'] if final else []) or
                projected.get('stage') != expected_stage or
                projected.get('status') != item['status'] or
                projected.get('unknown_cost_attempts') != int(final) or
                [record.get('id') for record in projected.get('records', [])] != expected_ids):
            raise ValueError('Solar full-stage usable answers differ')
        if expected_stage in THREE:
            first = solar['stages'][THREE.index(expected_stage)]
            if (item['all_four_correct'] != first['all_four_correct'] or
                    item['known_development_cost_usd'] != first['known_development_cost_usd']):
                raise ValueError('Solar first-pass score changed in full report')
            continue
        scores = {'all_four': item['all_four_correct'],
                  **{key: item['fields'][key]['correct'] for key in FIELDS}}
        runs.append(row('solar-decide', solar_full['configuration']['model'],
                        solar_full['configuration']['returned_model'],
                        solar_full['configuration']['provider'], NINE, expected_stage,
                        scores, item['input_tokens'], item['output_tokens'],
                        item['known_development_cost_usd'], full_projection,
                        full_digest, SOLAR_FULL, valid=valid,
                        unknown_upper_bound='0.10485760' if final else '0',
                        client_elapsed_available=item['client_elapsed_available'],
                        client_elapsed_ns_sum=item['client_elapsed_ns_sum_known_responses'],
                        result_status=('The original run and its continuation returned 59 usable answers. DEV-009 has no returned answer and retains a separate unknown-cost bound. This is not a clean 60-answer repeat.'
                                       if final else 'Closed native-choice repeat. The linked report has source-backed paired and repeat comparisons.')))

    if (liquid.get('kind') != 'liquid-d1-native-full-findings-v1' or
            liquid.get('closed_development_stages') != list(NINE) or
            liquid.get('closed_stage_count') != 9 or liquid.get('unpublished_development_stages') != [] or
            set(liquid.get('phases', {})) != set(NINE)):
        raise ValueError('Liquid nine-stage coverage differs')
    for stage in NINE:
        item = liquid['phases'][stage]
        path = Path('results/liquid-d1-native-v1/full-v1') / stage / 'development.public.json'
        digest = source(path, item['public_projection_sha256'])
        public = load(root, path)
        if (public.get('record_count') != 60 or public.get('valid_outputs') != 60 or
                len(public.get('records', [])) != 60 or public.get('intrinsic_invalid_count') != 0 or
                public.get('unknown_upper_bound_usd') != '0'):
            raise ValueError('Liquid public record coverage differs')
        scores = {'all_four': item['all_four_correct'], **item['fields_correct']}
        runs.append(row('liquid-d1', liquid['configuration']['model'],
                        liquid['configuration']['returned_model'], liquid['configuration']['provider'],
                        NINE, stage, scores, item['usage']['input_tokens'], item['usage']['output_tokens'],
                        item['known_actual_usd'], path, digest, LIQUID))

    if (tev.get('schema') != 'tev-native-full-findings-v1' or
            tev.get('status') != 'nine_closed_development_runs' or
            tev.get('stage_order') != list(NINE) or tev.get('development_records') != 540 or
            tev.get('development_valid_answers') != 540 or len(tev.get('stages', [])) != 9):
        raise ValueError('Tev nine-stage coverage differs')
    tev_projection = tev_builder.PROJECTION
    tev_digest = source(tev_projection, tev['source_bindings']['projection_sha256'])
    sources[str(tev_builder.RECEIPT)] = sha(root / tev_builder.RECEIPT)
    for stage, item in zip(NINE, tev['stages']):
        if item.get('stage') != stage or item.get('records') != 60 or item.get('valid_answers') != 60:
            raise ValueError('Tev closed stage differs')
        scores = {'all_four': item['all_four_correct'],
                  **{key: item['fields'][key]['correct'] for key in FIELDS}}
        runs.append(row('tev1-4b', tev['configuration']['model'],
                        tev['configuration']['returned_model'], tev['configuration']['provider'],
                        NINE, stage, scores, item['input_tokens'], item['output_tokens'],
                        item['known_actual_usd'], tev_projection, tev_digest, TEV))

    if (clef.get('schema') != 'clef-openrouter-closed-stage-findings-v1' or
            clef.get('route') != 'OpenRouter native Decisions' or
            clef.get('distinct_from') != 'Cloudflare direct native route' or
            len(clef.get('stages', [])) != len(clef.get('included_stages', [])) or
            not clef['stages']):
        raise ValueError('OpenRouter Clef closed-stage report differs')
    clef_projection = clef_builder.PROJECTION
    clef_receipt = clef_builder.RECEIPT
    projected = load(root, clef_projection)
    receipt = load(root, clef_receipt)
    if (receipt.get('projection_sha256') != clef_builder.sha(clef_builder.canonical(projected)) or
            clef['evidence']['projection_receipt_sha256'] !=
            clef_builder.sha(clef_builder.canonical(receipt)) or
            projected.get('schema') != 'clef-openrouter-public-projection-v1' or
            len(projected.get('stages', [])) != len(clef['stages'])):
        raise ValueError('OpenRouter Clef public projection differs')
    sources[str(clef_projection)] = sha(root / clef_projection)
    sources[str(clef_receipt)] = sha(root / clef_receipt)
    families = {'clef': 'clef-openrouter',
                'clef-flash': 'clef-flash-openrouter',
                'luna-decisions': 'luna-decisions-openrouter'}
    for chosen, item, public in zip(clef['included_stages'], clef['stages'], projected['stages']):
        key, stage = chosen['model_key'], chosen['stage']
        interrupted = key == 'clef-flash' and stage == 'fresh3/P2'
        valid = 59 if interrupted else 60
        if (key not in families or item.get('model_key') != key or item.get('stage') != stage or
                public.get('model_key') != key or public.get('stage') != stage or
                item.get('status') != ('interrupted_with_exact_unsent_suffix_59' if interrupted else 'closed_60') or
                public.get('status') != item.get('status') or
                item.get('attempted') != 60 or
                item.get('valid_answers') != valid or item.get('unsent') != 0 or
                item.get('invalid_answers') != 0 or
                item.get('provider_failures') != (1 if interrupted else 0) or
                item.get('unknown_cost_attempts') != (1 if interrupted else 0) or
                item.get('unknown_cost_upper_bound_usd') != ('0.02359296' if interrupted else '0') or
                [record.get('id') for record in public.get('records', [])] !=
                ([f'DEV-{index:03}' for index in range(1, 39)] +
                 [f'DEV-{index:03}' for index in range(40, 61)] if interrupted else
                 [f'DEV-{index:03}' for index in range(1, 61)]) or
                item.get('client_request_elapsed_ns_count') != valid):
            raise ValueError('OpenRouter Clef stage coverage differs')
        if interrupted and (item.get('provider_failure_ids') != ['DEV-039'] or
                            item.get('unknown_cost_ids') != ['DEV-039'] or
                            item.get('original_unsent_ids') != [f'DEV-{index:03}' for index in range(40, 61)]):
            raise ValueError('OpenRouter Flash interruption differs')
        spec = clef_builder.route.MODELS[key]
        scores = {'all_four': item['all_four_correct'],
                  **{field: item['fields'][field]['correct'] for field in FIELDS}}
        runs.append(row(families[key], spec['model'],
                        clef_builder.full.RETURNED_MODEL[key], spec['provider'],
                        NINE, stage, scores, item['observed_input_tokens'],
                        item['observed_output_tokens'], item['observed_known_cost_usd'],
                        clef_projection, sources[str(clef_projection)], CLEF_OPENROUTER,
                        valid=valid, unknown_upper_bound=item['unknown_cost_upper_bound_usd'],
                        client_elapsed_available=valid,
                        client_elapsed_ns_sum=item['client_request_elapsed_ns_sum'],
                        result_status=('Final prompt run combines 38 original answers with 21 exact never-sent continuation answers. DEV039 remains a provider failure with unknown cost; 59 of 60 positions have usable answers.'
                                       if interrupted else
                                       'Closed OpenRouter native Choice run. The linked report shows its exact source evidence and available paired or repeat comparisons.')))

    runs.extend(perplexity_runs(root, source))

    ids = [item['id'] for item in runs]
    existing_ids = {item['id'] for item in load(root, Path('public-site/data-provider-errors-v1.json'))['runs']}
    if len(ids) != 36 + len(clef['stages']) or len(set(ids)) != len(ids) or set(ids) & existing_ids:
        raise ValueError('Supplemental native run ID collision or missing run')
    if sum(1 for item in runs if item['repeatPass'] == 'fresh1') != (
            12 + sum(item['stage'].startswith('fresh1/') for item in clef['stages'])):
        raise ValueError('First-pass coverage differs')
    return {'schema': 'supplemental-decision-runs-v1', 'denominator': 60,
            'runs': runs, 'sources': [{'path': path, 'sha256': digest}
                                     for path, digest in sorted(sources.items())],
            'scope': 'Closed public native Choice development runs only. Individual predictions stay in linked public projections; no private responses or reference labels are embedded.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('write', 'check'))
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    result = build(args.root)
    path = args.root / OUTPUT
    rendered = json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + '\n'
    if args.action == 'write':
        path.write_text(rendered)
        print(f'Wrote {OUTPUT} with {len(result["runs"])} run views')
    elif not path.exists() or path.read_text() != rendered:
        raise SystemExit('Supplemental native run feed is stale')
    else:
        print(f'Verified {OUTPUT} with {len(result["runs"])} run views')


if __name__ == '__main__':
    main()
