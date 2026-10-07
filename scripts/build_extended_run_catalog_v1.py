#!/usr/bin/env python3
"""Build public, report-backed rows absent from the original run explorer."""

import argparse
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path('public-site/extended-run-catalog-v1.json')
BASE = 'https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/'
FIELDS = ('sentiment', 'follow_up_needed', 'serious_concern_reported', 'testimonial_potential')

# Each entry is a named report lineage. Earlier continuation snapshots that repeat
# these same cells are intentionally absent; the coverage audit lists them.
STANDARD = (
    'typesafe-repeats', 'repeats', 'hosted-repeats', 'claude-repeats',
    'claude-roster-repeats', 'gemini-repeats', 'haiku-fresh-matched3',
    'laya-repeats', 'semif-repeats', 'semif-generated-repeats',
    'small-local-repeats', 'legacy-qwen-repeats', 'anyjev-raw-repeats',
    'anyjev-l0-repeats', 'anyjev-l1-repeats', 'anyjev-l2-repeats',
    'anyjev-generated-repeats', 'alex-native-repeats',
    'codex-fresh-repeats', 'deepseek-fresh-repeats',
    'additional-hosted-fresh-repeats', 'qwen36-off-second-interruption-findings',
    'qwen27-final-descriptive-findings',
)
SPECIAL = (
    'sonnet55-fresh-matched3', 'openjev-native-repeats',
    'openjev-generated-repeats', 'kev-native-repeats',
    'jev-native-prompt-findings', 'kev-native-prompt-findings',
    'clef-closed-repeat-findings', 'hosted-v2-repeats',
    'gemma26-continuation-findings', 'gemma26-second-continuation-findings',
    'gemma26-p2-repeat-findings',
    'gemma26-fresh3-p0-checkpoint', 'gemma26-fresh3-p1-interrupted-checkpoint',
    'clef-flash-p1-findings', 'clef-flash-p2-findings',
    'clef-p0-repeat-findings', 'deepseek-high-remaining6-successor-findings',
    'e4b-interruption-findings', 'deepseek-low-fresh3-findings',
    'deepseek-low-p1-successor-findings',
    'deepseek-low-remaining6-price-v2-findings',
    'deepseek-low-final-suffix-findings',
    'mistral119-fresh1-p0-findings',
)
FEEDS = STANDARD + SPECIAL
HISTORICAL_ORIGINAL = {
    'typesafe-repeats', 'repeats', 'hosted-repeats', 'claude-repeats',
    'claude-roster-repeats', 'gemini-repeats', 'laya-repeats',
    'semif-repeats', 'anyjev-raw-repeats', 'anyjev-l0-repeats',
    'anyjev-l2-repeats',
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def number(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        try:
            parsed = Decimal(value)
        except InvalidOperation:
            return None
        return float(parsed) if parsed.is_finite() else None
    if isinstance(value, dict) and isinstance(value.get('sum'), (int, float)):
        return value['sum']
    return None


def usage_value(usage, *keys):
    for key in keys:
        if key in usage:
            value = number(usage[key])
            if value is not None:
                return value
    return None


def normalize_usage(cell):
    usage = cell.get('usage') or {}
    if not isinstance(usage, dict):
        usage = {}
    raw_tokens = usage.get('tokens') or cell.get('tokens') or {}
    if not isinstance(raw_tokens, dict):
        raw_tokens = {}
    if not raw_tokens and any(key in usage for key in ('input_tokens', 'output_tokens')):
        raw_tokens = usage
    request_count = usage_value(usage, 'requestCount')
    token_data_available = any(usage_value(raw_tokens, key) is not None for key in (
        'input_tokens', 'prompt_tokens', 'knownSavedInputTokens',
        'output_tokens', 'completion_tokens', 'knownSavedOutputTokens'))
    token_coverage = []
    missing = usage.get('tokensMissingRequestCount') or {}
    if isinstance(missing, dict) and request_count is not None:
        token_coverage.extend(request_count - value for key, value in missing.items()
                              if key in ('prompt_tokens', 'completion_tokens', 'input_tokens', 'output_tokens')
                              and type(value) is int and 0 <= value <= request_count)
    availability = usage.get('tokenAvailability') or {}
    if isinstance(availability, dict):
        token_coverage.extend(value['reportedCount'] for key, value in availability.items()
                              if key in ('prompt_tokens', 'completion_tokens', 'input_tokens', 'output_tokens')
                              and isinstance(value, dict) and type(value.get('reportedCount')) is int)
    token_coverage.extend(value['reportedCount'] for key, value in raw_tokens.items()
                          if key in ('prompt_tokens', 'completion_tokens', 'input_tokens', 'output_tokens')
                          and isinstance(value, dict) and type(value.get('reportedCount')) is int)
    explicit_coverage = usage_value(usage, 'reportedRequests')
    if explicit_coverage is not None:
        token_coverage.append(explicit_coverage)
    reported_requests = (min(token_coverage) if token_coverage else request_count)
    if (request_count is not None and reported_requests is not None and
            not 0 <= reported_requests <= request_count):
        raise ValueError('Reported token coverage exceeds request count')
    tokens = {
        'input': usage_value(raw_tokens, 'input_tokens', 'prompt_tokens', 'knownSavedInputTokens'),
        'output': usage_value(raw_tokens, 'output_tokens', 'completion_tokens', 'knownSavedOutputTokens'),
        'cachedInput': usage_value(raw_tokens, 'cached_input_tokens', 'cache_read_input_tokens'),
        'cacheWrite': usage_value(raw_tokens, 'cache_write_input_tokens', 'cache_creation_input_tokens'),
        'reasoning': usage_value(raw_tokens, 'reasoning_output_tokens', 'provider_reported_reasoning_tokens', 'thinking_tokens'),
        'reportedRequests': reported_requests if token_data_available else None,
        'totalRequests': request_count,
        'complete': False,
        'note': 'Only values stated in the linked public report are shown; missing categories are unavailable.',
    }
    tokens['complete'] = (token_data_available and request_count is not None and
                          tokens['reportedRequests'] == request_count)
    total = usage_value(usage, 'requestSecondsTotal', 'clientRequestSecondsTotal',
                        'clientRequestToRecordSeconds', 'knownClientSecondsSubtotal')
    inference = usage_value(usage, 'inferenceSeconds')
    timing_count = usage_value(usage, 'timingReportedRequests', 'clientRequestTimingCount')
    if timing_count is None:
        request_series = usage.get('requestSeconds')
        timing_count = (sum(number(value) is not None for value in request_series)
                        if isinstance(request_series, list) else request_count)
    timing = {
        'kind': usage.get('requestTimeKind') or usage.get('timingKind') or usage.get('timeBasis') or 'unavailable',
        'requests': timing_count or 0,
        'totalRequests': request_count,
        'medianSeconds': None, 'p95Seconds': None,
        'totalSeconds': total, 'inferenceSeconds': inference,
        'inferenceReportedRequests': 0 if inference is None else tokens['reportedRequests'],
        'note': 'Client duration is not isolated inference time; unavailable values remain null.',
    }
    known = next((usage[key] for key in ('actualProviderCostUsd', 'actualCostUsd',
                                         'knownObservedCostUsd', 'knownCostUsd')
                  if usage.get(key) is not None), None)
    estimate = next((usage[key] for key in ('estimatedTokenPriceCostUsd',
                                            'cliListPriceEstimateUsd', 'estimatedCostUsd')
                     if usage.get(key) is not None), None)
    cost = {
        'actualUsd': None, 'knownUsd': number(known), 'estimatedUsd': number(estimate),
        'unknownUpperBoundUsd': number(usage.get('unknownCostUpperBoundUsd',
                                                 usage.get('unknownChargeUpperBoundUsd'))),
        'unknownCostCount': usage.get('unknownCostCount'),
        'note': usage.get('costNote') or 'Report-only accounting; null means unavailable, not zero.',
    }
    return timing, tokens, cost


def score_fields(score):
    if not isinstance(score, dict):
        raise ValueError('Missing score')
    denominator, valid, all_four = score.get('denominator'), score.get('valid'), score.get('allFour')
    fields = score.get('fields')
    if (denominator != 60 or type(valid) is not int or not 0 <= valid <= 60 or
            type(all_four) is not int or not 0 <= all_four <= valid or
            not isinstance(fields, dict) or set(fields) != set(FIELDS) or
            any(type(fields[field]) is not int or not 0 <= fields[field] <= valid for field in FIELDS)):
        raise ValueError('Invalid report score or denominator')
    return valid, {'all_four': all_four, **{field: fields[field] for field in FIELDS}}


def clean_part(value):
    value = str(value)
    if not value or any(ch not in 'abcdefghijklmnopqrstuvwxyz0123456789-._' for ch in value.lower()):
        raise ValueError(f'Unsafe stage identity: {value}')
    return value.lower()


def surface_for(family, configuration, provider):
    if family in ('repeats', 'codex-fresh-repeats'):
        return 'Codex CLI subscription'
    if family in ('small-local-repeats', 'legacy-qwen-repeats',
                  'openjev-native-repeats', 'openjev-generated-repeats'):
        return 'Local execution (see linked report)'
    if provider == 'google-ai-studio':
        return 'Google AI Studio'
    if provider in ('Cloudflare', 'Cloudflare connected app'):
        return 'Cloudflare connected app'
    if provider == 'TypeSafe':
        return 'TypeSafe native Choice API'
    if configuration.startswith('openrouter-paid-') and provider:
        return 'OpenRouter · ' + provider
    return provider or 'Route unavailable'


def add(rows, root, family, report, configuration, model, effort, provider,
        repeat, condition, cell, *, score=None, source_status=None, eligible=None):
    if condition not in ('P0', 'P1', 'P2') or repeat not in (
            'original', 'repeat2', 'repeat3', 'pass1', 'pass2', 'pass3',
            'fresh1', 'fresh2', 'fresh3'):
        raise ValueError(f'Unexpected stage {family}/{repeat}/{condition}')
    score = score if score is not None else cell.get('score')
    valid, metrics = score_fields(score)
    status = source_status or cell.get('completionStatus') or cell.get('status') or cell.get('state') or 'reported'
    outcomes = score.get('outcomes') or {}
    pending = int(outcomes.get('never_sent', 0)) + int(outcomes.get('unknown_started', 0))
    completed = status in ('complete', 'completed', 'completed_with_intrinsic_invalid', 'reported') and not pending
    if type(score.get('saved')) is int:
        saved_responses = score['saved']
    elif type(outcomes.get('invalid_output')) is int:
        saved_responses = valid + outcomes['invalid_output']
    elif type(score.get('invalidOutputs')) is int:
        saved_responses = valid + score['invalidOutputs']
    elif valid == 60:
        saved_responses = 60
    else:
        saved_responses = None  # A closed score does not establish response count.
    if saved_responses is not None and not valid <= saved_responses <= 60:
        raise ValueError(f'Invalid saved response count: {family}/{repeat}/{condition}')
    report_path = Path('public-site') / (report + '.json')
    report_sha = digest(root / report_path)
    timing, tokens, cost = normalize_usage(cell)
    ident = '-'.join(('extended', clean_part(configuration), clean_part(repeat), condition.lower()))
    row = {
        'id': ident, 'experimentId': '-'.join(('extended', clean_part(configuration), clean_part(repeat), 'p0')),
        'parentBaselineId': None if condition == 'P0' else '-'.join(('extended', clean_part(configuration), clean_part(repeat), 'p0')),
        'protocolId': 'report-only-' + clean_part(family) + '-v1',
        'repeatPass': repeat, 'model': model or configuration, 'effort': effort,
        'provider': provider, 'surface': surface_for(family, configuration, provider),
        'condition': condition, 'complete': completed, 'records': 60,
        'recordsMeaning': 'planned denominator',
        'savedResponses': saved_responses, 'valid': valid, 'metrics': metrics,
        'pairedEligible': completed and valid == 60 if eligible is None else eligible,
        'resultStatus': str(status), 'timing': timing, 'tokens': tokens, 'cost': cost,
        'sourceOnlyDetails': True, 'sourceRecordsUrl': BASE + str(report_path),
        'sourceRecordSha256': report_sha, 'evidenceUrl': BASE + str(report_path),
        'sourceFamily': family, 'sourceStage': f'{configuration}/{repeat}/{condition}',
    }
    rows.append(row)


def series_items(document):
    return document['series'] if isinstance(document.get('series'), list) else [document]


def standard_rows(rows, root, family, document):
    for series in series_items(document):
        passes = series.get('passes')
        if not isinstance(passes, dict):
            raise ValueError(f'No standard passes: {family}')
        config = series.get('configuration')
        if not config:
            raise ValueError(f'No configuration: {family}')
        for repeat, conditions in passes.items():
            if family in HISTORICAL_ORIGINAL and repeat == 'original':
                continue  # Explicit alias of the original base-feed stage.
            for condition, cell in conditions.items():
                if not isinstance(cell, dict) or 'score' not in cell:
                    continue  # Planned/unsent condition is not a saved result.
                add(rows, root, family, family, config, series.get('model'),
                    series.get('effort'), series.get('provider'), repeat, condition, cell)


def build(root=ROOT):
    root = Path(root)
    reports = {}
    for family in FEEDS:
        path = root / 'public-site' / (family + '.json')
        reports[family] = json.loads(path.read_text())
    rows = []
    for family in STANDARD:
        if family == 'qwen27-final-descriptive-findings':
            continue
        standard_rows(rows, root, family, reports[family])

    # This terminal descriptive report supersedes the earlier hosted-v2
    # Qwen 27 snapshots. The two configurations remain separate.
    family = 'qwen27-final-descriptive-findings'
    for series in reports[family]['series']:
        for repeat, conditions in series['passes'].items():
            for condition, cell in conditions.items():
                if 'score' in cell:
                    route = next(item for item in reports['hosted-v2-repeats']['series']
                                 if item['configuration'] == series['configuration'])
                    add(rows, root, family, family, series['configuration'],
                        route['model'], route['effort'], route['provider'],
                        repeat, condition, cell, eligible=False)

    family = 'hosted-v2-repeats'
    for series in reports[family]['series']:
        if series['configuration'] != 'openrouter-paid-gemma4-26b-a4b-on':
            continue  # Qwen 27 is covered by its terminal nine-cell report.
        standard_rows(rows, root, family, {'series': [series]})
    family = 'gemma26-continuation-findings'
    doc = reports[family]
    for repeat, conditions in doc['passes'].items():
        for condition, cell in conditions.items():
            if (repeat, condition) in {('fresh1', 'P0'), ('fresh1', 'P1')} or 'score' not in cell:
                continue  # Exact hosted-v2 aliases or no saved score.
            add(rows, root, family, family, doc['configuration'],
                'google/gemma-4-26b-a4b-it', 'on', 'deepinfra/fp8',
                repeat, condition, cell,
                eligible=False)

    family = 'gemma26-second-continuation-findings'
    doc = reports[family]
    composite = doc['compositeP0']
    if (composite.get('pass'), composite.get('condition')) != ('fresh2', 'P0'):
        raise ValueError('Gemma second continuation identity differs')
    add(rows, root, family, family, doc['configuration'],
        'google/gemma-4-26b-a4b-it', 'on', 'deepinfra/fp8',
        'fresh2', 'P0', {'score': composite['score'], 'status': composite['status']},
        eligible=False)

    # Later Gemma checkpoints report the same lineage, with three further
    # scored slots. Use the latest source that names each slot, once.
    for family, repeat, condition, score in (
        ('gemma26-p2-repeat-findings', 'fresh3', 'P2',
         reports['gemma26-p2-repeat-findings']['fixed60Scores']['fresh3']),
        ('gemma26-fresh3-p0-checkpoint', 'fresh3', 'P0',
         reports['gemma26-fresh3-p0-checkpoint']['conditions']['P0']['fixed60Scores']['fresh3']),
        ('gemma26-fresh3-p1-interrupted-checkpoint', 'fresh3', 'P1',
         reports['gemma26-fresh3-p1-interrupted-checkpoint']['conditions']['P1']['fixed60Scores']['fresh3']),
    ):
        doc = reports[family]
        add(rows, root, family, family, doc['configuration'],
            'google/gemma-4-26b-a4b-it', 'on', 'deepinfra/fp8',
            repeat, condition, {'score': score, 'status': 'completed_interrupted_composite'},
            eligible=False)

    family = 'sonnet55-fresh-matched3'
    doc = reports[family]
    for effort, passes in doc['cells'].items():
        for repeat, conditions in passes.items():
            if repeat == 'pass1':
                continue  # Existing app adapter contains all 12 first-pass cells.
            for condition, cell in conditions.items():
                add(rows, root, family, family, 'sonnet55-' + effort,
                    doc['model'], effort, doc.get('provider'), repeat,
                    condition, cell['development'])

    for family in ('openjev-native-repeats', 'openjev-generated-repeats'):
        doc = reports[family]
        for config, series in doc['configurations'].items():
            for repeat, value in series['freshPasses'].items():
                conditions = {'P0': value} if 'score' in value else value
                for condition, cell in conditions.items():
                    if 'score' in cell:
                        add(rows, root, family, family, 'openjev-' + config,
                            None, None, 'local', repeat, condition, cell)

    family = 'kev-native-repeats'
    doc = reports[family]
    for repeat, cell in doc['passes'].items():
        if not isinstance(cell.get('score'), dict):
            continue  # Interrupted without a scored saved phase.
        add(rows, root, family, family, doc['configuration'], doc.get('model'),
            None, doc.get('provider'), repeat, 'P0', cell)

    family = 'jev-native-prompt-findings'
    doc = reports[family]
    for condition, passes in doc['passes'].items():
        for repeat, cell in passes.items():
            if 'score' not in cell:
                continue
            mapped = dict(cell, usage={'cliListPriceEstimateUsd': cell.get('knownCostUsd'),
                                       'input_tokens': cell.get('inputTokens'),
                                       'output_tokens': cell.get('outputTokens'),
                                       'clientRequestSecondsTotal': cell.get('clientSeconds'),
                                       'unknownCostUpperBoundUsd': cell.get('unknownUpperBoundUsd')})
            add(rows, root, family, family, 'typesafe-jev113-native-prompts',
                'jev-1.13.0', None, 'TypeSafe', repeat, condition, mapped)

    family = 'kev-native-prompt-findings'
    doc = reports[family]
    for condition, item in doc['conditions'].items():
        for repeat, cell in item['passes'].items():
            if 'score' in cell:
                add(rows, root, family, family, 'kev-openrouter-native-prompts',
                    doc.get('model'), None, 'OpenRouter', repeat, condition, cell)

    family = 'clef-closed-repeat-findings'
    doc = reports[family]
    for cell in doc['cells']:
        repeat, condition = cell['repeat'], cell['condition']
        if (repeat, condition) == ('fresh1', 'P0'):
            continue  # Exact app adapter alias for direct Clef first P0.
        if cell['valid'] == 0:
            continue  # The one attempted request is unknown; no saved response exists.
        score = {'denominator': 60, 'valid': cell['valid'],
                 'allFour': cell['matchedAllFour'],
                 'fields': {field: cell['fieldMetrics'][field]['matchedAmongValid'] for field in FIELDS},
                 'outcomes': {'never_sent': cell.get('neverSent', 0),
                              'unknown_started': cell.get('unknownOutcome', 0)}}
        mapped = {'score': score, 'status': cell['status'],
                  'usage': {'tokens': {'input_tokens': cell.get('inputTokensObserved'),
                                      'output_tokens': cell.get('outputTokensObserved')},
                            'unknownCostUpperBoundUsd': cell.get('reservationUpperBoundUsd')}}
        add(rows, root, family, family, 'cloudflare-clef-direct', doc.get('model'),
            None, 'Cloudflare', repeat, condition, mapped, eligible=False)

    for condition in ('P1', 'P2'):
        family = 'clef-flash-' + condition.lower() + '-findings'
        doc = reports[family]
        if doc['configuration']['route'] != '@cf/cloudflare/clef-flash':
            raise ValueError('Direct Flash route differs')
        for repeat, cell in doc['phaseByPass'].items():
            counts = cell['counts']
            score = {'denominator': 60, 'valid': counts['valid'],
                     'allFour': cell['allFourCorrect'],
                     'fields': {field: cell['fields'][field]['correct'] for field in FIELDS},
                     'outcomes': {'invalid_output': counts.get('invalidOutput', 0),
                                  'never_sent': counts.get('neverSent', 0),
                                  'unknown_started': counts.get('unknownOutcome', 0)}}
            mapped = {'score': score, 'status': 'complete' if counts['valid'] == 60 else 'interrupted'}
            add(rows, root, family, family, 'cloudflare-clef-flash-direct',
                '@cf/cloudflare/clef-flash', None, 'Cloudflare connected app',
                repeat, condition, mapped, eligible=counts['valid'] == 60)

    family = 'clef-p0-repeat-findings'
    doc = reports[family]
    if doc['models']['clef-flash']['route'] != '@cf/cloudflare/clef-flash':
        raise ValueError('Direct Flash P0 route differs')
    cell = doc['models']['clef-flash']['fresh2']
    score = {'denominator': 60, 'valid': cell['valid'], 'allFour': cell['allFourCorrect'],
             'fields': {field: (cell['fields'][field]['correct'] if isinstance(cell['fields'][field], dict)
                                else cell['fields'][field]) for field in FIELDS}}
    mapped = {'score': score, 'status': 'complete',
              'usage': {'tokens': {'input_tokens': cell.get('observedInputTokens'),
                                  'output_tokens': cell.get('observedOutputTokens')},
                        'cliListPriceEstimateUsd': cell.get('publishedInputPriceEstimateUsd'),
                        'requestSecondsTotal': cell.get('clientElapsedSeconds')}}
    add(rows, root, family, family, 'cloudflare-clef-flash-direct',
        '@cf/cloudflare/clef-flash', None, 'Cloudflare connected app',
        'fresh2', 'P0', mapped)

    family = 'deepseek-high-remaining6-successor-findings'
    doc = reports[family]
    for stage, phase in doc['phases'].items():
        repeat, condition = stage.split('/')
        raw_score = phase['score']
        score = {'denominator': 60, 'valid': raw_score['valid'],
                 'allFour': raw_score['allFour'], 'fields': phase['fieldCorrect'],
                 'outcomes': raw_score.get('outcomes', {})}
        mapped = {'score': score, 'status': phase['status'],
                  'usage': {'actualCostUsd': phase.get('knownDevelopmentCostUsd'),
                            'unknownCostUpperBoundUsd': phase.get('unknownCostUpperBoundUsd')}}
        add(rows, root, family, family, doc['configuration'],
            'deepseek/deepseek-v4.1-flash', 'high', 'open-inference/fp4',
            repeat, condition, mapped, eligible=False)

    family = 'e4b-interruption-findings'
    doc = reports[family]
    if doc['phase'] != 'fresh2/P2' or doc['descriptiveScore']['valid'] != doc['savedValid']:
        raise ValueError('E4B interrupted stage identity differs')
    add(rows, root, family, family, doc['configurationId'],
        'gemma4-e4b-sdk-thinking-on', 'on', 'local', 'fresh2', 'P2',
        {'score': doc['descriptiveScore'], 'status': doc['status'],
         'usage': doc.get('usage') or {}}, eligible=False)

    family = 'deepseek-low-remaining6-price-v2-findings'
    doc = reports[family]
    if len(doc['series']) != 1:
        raise ValueError('DeepSeek low revised-price series differs')
    series = doc['series'][0]
    add(rows, root, family, family,
        'openrouter-paid-deepseek-v41-flash-low-remaining6-price-v2',
        series['model'], series['effort'], series['provider'],
        series['pass'], series['condition'],
        {'score': series['score'], 'status': 'interrupted_composite_descriptive_only',
         'usage': {'actualCostUsd': series.get('developmentKnownCostUsd'),
                   'unknownCostUpperBoundUsd': series.get('developmentUnknownCostUpperBoundUsd')}},
        eligible=False)

    family = 'deepseek-low-final-suffix-findings'
    doc = reports[family]
    if len(doc['series']) != 1:
        raise ValueError('DeepSeek low first-pass continuation differs')
    series = doc['series'][0]
    score = series['historicalFirstPass']['P2']
    observed = series['p2ObservedUsage']
    usage = {'tokens': {'prompt_tokens': observed['prompt_tokens']['observedSum'],
                        'completion_tokens': observed['completion_tokens']['observedSum']},
             'requestCount': 60, 'reportedRequests': observed['prompt_tokens']['observedCount'],
             'actualCostUsd': observed['observedCostUsd'],
             'clientRequestSecondsTotal': observed['clientRequestSecondsTotal']}
    add(rows, root, family, family, 'openrouter-paid-deepseek-v41-flash-low',
        series['model'], series['effort'], series['provider'],
        'fresh1', 'P2', {'score': score, 'status': 'completed_interrupted_composite',
                         'usage': usage}, eligible=False)

    family = 'deepseek-low-p1-successor-findings'
    doc = reports[family]
    if doc['stage'] != 'fresh2/P1':
        raise ValueError('DeepSeek low P1 stage differs')
    score = {'denominator': 60, 'valid': doc['valid'], 'allFour': doc['allFourCorrect'],
             'fields': doc['fieldCorrect'], 'outcomes': doc['outcomes']}
    add(rows, root, family, family, doc['configurationId'],
        'deepseek/deepseek-v4.1-flash', 'low', 'open-inference/fp4',
        'fresh2', 'P1', {'score': score, 'status': doc['status'],
                          'usage': {'actualCostUsd': doc['knownDevelopmentCostUsd'],
                                    'unknownCostUpperBoundUsd': doc['unknownCostUpperBoundUsd']}},
        eligible=False)

    family = 'deepseek-low-fresh3-findings'
    doc = reports[family]
    stages = {'fresh2/P0': doc['earlierClosedFresh2P0']}
    stages.update({f'fresh3/{condition}': item for condition, item in doc['stages'].items()})
    for stage, item in stages.items():
        repeat, condition = stage.split('/')
        score = {'denominator': 60, 'valid': item['valid'],
                 'allFour': item['allFourCorrect'], 'fields': item['fieldCorrect'],
                 'outcomes': item['outcomes']}
        add(rows, root, family, family, doc['configurationId'],
            'deepseek/deepseek-v4.1-flash', 'low', 'open-inference/fp4',
            repeat, condition, {'score': score, 'status': 'completed',
                                'usage': {'actualCostUsd': item['knownDevelopmentCostUsd']}},
            eligible=False)

    family = 'mistral119-fresh1-p0-findings'
    doc = reports[family]
    if (doc['freshPass'], doc['condition']) != ('fresh1', 'P0'):
        raise ValueError('Mistral 119 stage differs')
    score = {'denominator': 60, 'valid': doc['outcomes']['valid'],
             'allFour': doc['scoring']['allFourMatches'],
             'fields': doc['scoring']['fieldMatches'],
             'outcomes': {'invalid_output': 0}}
    usage = {'tokens': {'prompt_tokens': doc['usage']['promptTokens'],
                        'completion_tokens': doc['usage']['completionTokens']},
             'requestCount': 60, 'reportedRequests': doc['usage']['tokenObservedCount'],
             'timingReportedRequests': doc['timing']['finishedRequestsMeasured'],
             'actualCostUsd': doc['usage']['observedKnownCostUsd'],
             'unknownCostUpperBoundUsd': doc['usage']['unknownChargeUpperBoundUsd'],
             'requestSecondsTotal': doc['timing']['finishedRequestElapsedSeconds']['total']}
    add(rows, root, family, family, doc['configurationId'],
        'mistralai/mistral-small-2603', 'none', 'mistral/zdr',
        'fresh1', 'P0', {'score': score, 'status': doc['status'], 'usage': usage},
        eligible=False)

    ids = [row['id'] for row in rows]
    if len(ids) != len(set(ids)):
        duplicates = sorted({ident for ident in ids if ids.count(ident) > 1})
        raise ValueError(f'Duplicate extended stage IDs: {duplicates[:5]}')
    rows.sort(key=lambda row: row['id'])
    sources = {str(Path('public-site') / (family + '.json')):
               digest(root / 'public-site' / (family + '.json')) for family in FEEDS}
    return {'schema': 'extended-run-catalog-v1', 'sourceSha256': sources,
            'runs': rows, 'runCount': len(rows),
            'note': 'Report-backed saved stages absent from the original explorer. Historical original phases and exact restatements are excluded; remaining report families are enumerated in the coverage audit.'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('write', 'check'))
    args = parser.parse_args()
    expected = build()
    path = ROOT / OUT
    if args.action == 'write':
        path.write_text(json.dumps(expected, indent=2, ensure_ascii=False) + '\n')
    elif json.loads(path.read_text()) != expected:
        raise SystemExit('Extended run catalog differs from public reports')
    print(f'{args.action}: {len(expected["runs"])} report-backed stages')


if __name__ == '__main__':
    main()
