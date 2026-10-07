#!/usr/bin/env python3
"""Join saved first-P0 general runs with seven native decision runs, offline."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path('results/cross-category-v1')
PUBLIC_OUTPUT = Path('public-site/cross-category-v1.json')
BASE = Path('public-site/data-provider-errors-v1.json')
BASE_SOURCE = Path('public-site/data.json')
EXTENDED = Path('public-site/extended-cases-v1.json')
CATALOG = Path('public-site/extended-run-catalog-v1.json')
NATIVE = Path('public-site/disputed-reviews-v1.json')
NATIVE_RUNS = Path('public-site/supplemental-decision-runs-v1.json')
INPUTS = Path('data/pilot/inputs.jsonl')
REFERENCES = Path('data/pilot/proposed_labels.jsonl')
CATEGORY_RULE = Path('docs/REPORT_CATEGORY_REVIEW_2026-10-02.md')
L1_CATEGORY = Path('docs/ANYJEV_L1_REPEAT_FINDINGS_2026-09-29.md')
L2_CATEGORY = Path('docs/ANYJEV_CALIBRATION_NEXT_ADMISSION_2026-09-28.md')
FIELDS = ('sentiment', 'follow_up_needed', 'serious_concern_reported', 'testimonial_potential')
GENERAL_TOKENS = ('qwen', 'gemma', 'deepseek', 'mistral', 'claude', 'sonnet', 'opus',
                  'haiku', 'fable', 'gpt-', 'codex', 'gemini', 'openjev', 'semif', 'anyjev')
GITHUB = 'https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/'


def require(test: bool, message: str) -> None:
    if not test:
        raise ValueError(message)


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def read_json(root: Path, path: Path) -> dict:
    return json.loads((root / path).read_text())


def read_jsonl(root: Path, path: Path) -> dict[str, dict]:
    rows = [json.loads(line) for line in (root / path).read_text().splitlines() if line.strip()]
    result = {row['id']: row for row in rows}
    require(len(rows) == len(result) == 60, f'{path}: duplicate or missing IDs')
    return result


def category(run: dict) -> str:
    """Pinned source taxonomy, independent of score and output validity."""
    value = f"{run['id']} {run.get('model', '')}".lower()
    if 'rules-v1' in value:
        return 'rules'
    if 'alex-openjev' in value:
        return 'task-fine-tuned'
    if 'anyjev-qwen06-l2' in value or 'anyjev-qwen06-l1' in value:
        return 'development-fold-fitted-adapter'
    if any(token in value for token in ('laya', 'kev-', 'kev-4b', 'jev-1.13',
                                       'liquid-d1', 'tev1-4b', 'solar-decide',
                                       'clef', 'luna-decisions', 'perplexity-decider')):
        return 'dedicated-decision'
    if any(token in value for token in GENERAL_TOKENS):
        return 'general-llm'
    raise ValueError(f"No declared category for {run['id']}")


def interface(run: dict) -> str:
    name = run['id'].lower()
    if 'openjev' in name and 'generated' not in name:
        return 'native option scoring over a general backbone'
    if 'semif' in name and 'generated' not in name:
        return 'native option scoring over a general backbone'
    if 'anyjev' in name and 'generated' not in name:
        return 'option scoring / adapter over a general backbone'
    return 'generated answer'


def case_rows(rows: list[dict], references: dict[str, dict], valid_statuses: set[str]) -> tuple[list[dict], dict, dict]:
    expected = set(references)
    require(len(rows) == 60 and {row['id'] for row in rows} == expected,
            'Run does not cover exactly 60 distinct review positions')
    counts = Counter()
    scores = Counter()
    output = []
    for row in sorted(rows, key=lambda item: item['id']):
        ident = row['id']
        status = row['status']
        prediction = row.get('prediction')
        reference = references[ident]['proposed_labels']
        valid = status in valid_statuses
        require(not valid or (isinstance(prediction, dict) and set(prediction) == set(FIELDS)),
                f'{ident}: valid prediction has the wrong field set')
        differences = [field for field in FIELDS if valid and prediction[field] != reference[field]]
        if valid:
            scores['valid'] += 1
            for field in FIELDS:
                scores[field] += prediction[field] == reference[field]
            scores['all_four'] += not differences
        counts[status] += 1
        output.append({'id': ident, 'status': status, 'prediction': prediction if valid else None,
                       'unusableSourcePredictionPresent': not valid and prediction is not None,
                       'differentFields': differences if valid else None,
                       'allFourMatch': not differences if valid else None})
    return output, {'valid': scores['valid'], 'all_four': scores['all_four'],
                    **{field: scores[field] for field in FIELDS}}, dict(sorted(counts.items()))


def source_path(url: str) -> Path:
    require(isinstance(url, str) and url.startswith(GITHUB), f'Noncanonical source URL: {url}')
    path = Path(url.removeprefix(GITHUB))
    require(not path.is_absolute() and '..' not in path.parts, f'Unsafe source path: {path}')
    return path


def costs(value: dict | None) -> dict:
    cost = value or {}
    return {'observedUsd': cost.get('actualUsd'), 'knownUsd': cost.get('knownUsd'),
            'estimatedUsd': cost.get('estimatedUsd'),
            'unknownUpperBoundUsd': cost.get('unknownUpperBoundUsd'),
            'basis': cost.get('note') or 'Not available in the normalized source.'}


def timing(value: dict | None) -> dict:
    source = value or {}
    return {'kind': source.get('kind'), 'requests': source.get('requests'),
            'medianSeconds': source.get('medianSeconds'),
            'p95Seconds': source.get('p95Seconds'),
            'totalSeconds': source.get('totalSeconds'),
            'inferenceSeconds': source.get('inferenceSeconds'),
            'basis': source.get('note') or 'Comparable inference time unavailable.'}


def controls(run: dict, source: str) -> dict:
    clock = run.get('timing') or {}
    return {'route': run.get('surface'), 'routeBasis': 'normalized source surface; provider variant may be unavailable',
            'surface': run.get('surface'), 'provider': run.get('provider'),
            'interface': interface(run) if source != 'native' else 'native Choice',
            'interfaceBasis': str(CATEGORY_RULE) if source != 'native' else str(NATIVE_RUNS),
            'condition': 'P0', 'effort': run.get('effort'),
            'protocolId': run.get('protocolId'),
            'sourceFamily': run.get('sourceFamily'),
            'requestPattern': clock.get('kind'),
            'observedRequestCount': clock.get('requests'),
            'declaredBatchSize': 1 if source == 'native' else None,
            'batchNote': ('One review per native request.' if source == 'native'
                          else 'Batch size is unavailable in the normalized row; request count is retained.'),
            'promptText': None,
            'promptNote': 'P0 is recorded, but exact prompt text is not copied into this dataset.',
            'cost': costs(run.get('cost')), 'timing': timing(clock)}


def paired(general: list[dict], native: list[dict]) -> dict:
    by_id = {row['id']: row for row in native}
    result = Counter()
    for row in general:
        if row['allFourMatch'] is None:
            result['general_no_valid_output'] += 1
        elif row['allFourMatch'] and by_id[row['id']]['allFourMatch']:
            result['both_match'] += 1
        elif row['allFourMatch']:
            result['general_only_match'] += 1
        elif by_id[row['id']]['allFourMatch']:
            result['native_only_match'] += 1
        else:
            result['neither_match'] += 1
    require(sum(result.values()) == 60, 'Paired denominator changed')
    return {key: result[key] for key in ('both_match', 'general_only_match',
                                        'native_only_match', 'neither_match',
                                        'general_no_valid_output')}


def build(root: Path = ROOT) -> tuple[dict, str, dict]:
    inputs = read_jsonl(root, INPUTS)
    references = read_jsonl(root, REFERENCES)
    expected = {f'DEV-{index:03d}' for index in range(1, 61)}
    require(set(inputs) == set(references) == expected, 'Frozen review IDs changed')
    require(all(row['review_version'] == '0.2' and set(row['proposed_labels']) == set(FIELDS)
                for row in references.values()), 'Reference version or fields changed')
    base, base_source = read_json(root, BASE), read_json(root, BASE_SOURCE)
    ext, catalog = read_json(root, EXTENDED), read_json(root, CATALOG)
    native, native_runs = read_json(root, NATIVE), read_json(root, NATIVE_RUNS)
    require(base['publicEvidenceProjection']['sourceDataSha256'] == digest(root / BASE_SOURCE)
            and base['publicEvidenceProjection']['sourceDataPath'] == str(BASE_SOURCE)
            and base['cases'] == base_source['cases'], 'Historical source projection changed')
    require(ext['schema'] == 'extended-cases-v1'
            and ext['sourceSha256'][str(CATALOG)] == digest(root / CATALOG)
            and ext['sourceSha256'][str(INPUTS)] == digest(root / INPUTS)
            and ext['sourceSha256'][str(REFERENCES)] == digest(root / REFERENCES)
            and len(ext['runs']) == catalog['runCount'], 'Extended source projection changed')
    require(native['schema'] == 'disputed-reviews-v1' and native['review_denominator'] == 60
            and native['model_denominator'] == 7
            and native['source_sha256'][str(NATIVE_RUNS)] == digest(root / NATIVE_RUNS)
            and native['source_sha256'][str(INPUTS)] == digest(root / INPUTS)
            and native['source_sha256'][str(REFERENCES)] == digest(root / REFERENCES),
            'Seven-native source projection changed')
    require(catalog['schema'] == 'extended-run-catalog-v1', 'Extended catalog schema changed')
    require(len({r['id'] for r in base['runs']}) == len(base['runs'])
            and len({r['id'] for r in catalog['runs']}) == len(catalog['runs']),
            'Duplicate normalized run ID')
    base_cases = defaultdict(list)
    for row in base['cases']:
        base_cases[row['configuration']].append(row)
    catalog_rows = {run['id']: run for run in catalog['runs']}
    ext_rows = {run['runId']: run for run in ext['runs']}
    require(set(catalog_rows) == set(ext_rows), 'Extended case/catalog run set changed')
    native_rows = {row['id']: row for row in native['models']}
    normalized_natives = {row['id']: row for row in native_runs['runs']}
    native_answers = defaultdict(list)
    for review in native['reviews']:
        require(review['reference'] == references[review['id']]['proposed_labels'],
                f"{review['id']}: native reference changed")
        for answer in review['answers']:
            native_answers[answer['model_id']].append(
                {'id': review['id'], 'status': 'ok', 'prediction': answer['prediction']})
    require(set(native_answers) == set(native_rows) and len(native_rows) == 7,
            'Seven-native model set changed')

    selected = []
    excluded = []
    for row in base['runs']:
        if row['condition'] != 'P0':
            continue
        kind = category(row)
        if row['id'] == 'sonnet5-low-with-retry':
            excluded.append({'source': str(BASE), 'runId': row['id'], 'reason':
                             'recovery composite of sonnet5-low-first-pass; original failure retained'})
            continue
        if kind != 'general-llm':
            excluded.append({'source': str(BASE), 'runId': row['id'], 'reason': f'category: {kind}'})
            continue
        cases, score, outcomes = case_rows(base_cases[row['experimentId']], references, {'ok'})
        require(score['valid'] == row['valid'] and all(score[key] == row['metrics'][key]
                for key in ('all_four', *FIELDS)), f"{row['id']}: historical score drift")
        record_path = source_path(row['evidenceUrl'])
        require((root / record_path).is_file(), f"{row['id']}: historical record source absent")
        selected.append({'runId': row['id'], 'category': kind,
                         'stratum': 'historical-first-P0', 'repeatPass': 'historical-first',
                         'complete': row['complete'], 'savedResponses': None,
                         'model': row['model'], 'sourceUrl': GITHUB + str(BASE_SOURCE),
                         'sourceSha256': digest(root / BASE_SOURCE),
                         'sourceCaseKey': row['experimentId'],
                         'runEvidenceLeadUrl': row['evidenceUrl'],
                         'runEvidenceLeadSha256': digest(root / record_path),
                         'runEvidenceLeadCompleteness': 'not asserted; may cover only a probe or batch',
                         'sourceFeedPath': str(BASE),
                         'sourceReportUrl': None, 'sourceReportSha256': None,
                         'controls': controls(row, 'base'), 'scores': score,
                         'outcomes': outcomes, 'cases': cases})
    for row in catalog['runs']:
        if row['condition'] != 'P0':
            continue
        kind = category(row)
        if row['repeatPass'] not in ('fresh1', 'pass1'):
            excluded.append({'source': str(CATALOG), 'runId': row['id'],
                             'reason': 'later repeat pass; not a first P0 pass'})
            continue
        if kind != 'general-llm':
            excluded.append({'source': str(CATALOG), 'runId': row['id'],
                             'reason': f'category: {kind}'})
            continue
        ext_row = ext_rows[row['id']]
        require(ext_row['condition'] == 'P0' and ext_row['repeatPass'] == row['repeatPass']
                and ext_row['sourceReportSha256'] == row['sourceRecordSha256']
                and ext_row['sourceReportUrl'] == row['sourceRecordsUrl'],
                f"{row['id']}: extended metadata changed")
        report_path = source_path(ext_row['sourceReportUrl'])
        require(digest(root / report_path) == ext_row['sourceReportSha256'],
                f"{row['id']}: extended report hash changed")
        record_path = source_path(ext_row['sourceRecordUrl'])
        require(digest(root / record_path) == ext_row['sourceRecordSha256'],
                f"{row['id']}: extended record hash changed")
        for part in ext_row['sourceRecordParts']:
            require(digest(root / source_path(part['url'])) == part['sha256'],
                    f"{row['id']}: extended record part hash changed")
        cases, score, outcomes = case_rows(ext_row['cases'], references, {'ok', 'valid'})
        require(score == ext_row['scores']
                and score['valid'] == row['valid']
                and all(score[key] == row['metrics'][key] for key in ('all_four', *FIELDS)),
                f"{row['id']}: extended score drift")
        selected.append({'runId': row['id'], 'category': kind,
                         'stratum': 'declared-fresh1-P0', 'repeatPass': row['repeatPass'],
                         'complete': row['complete'], 'savedResponses': row['savedResponses'],
                         'model': row['model'], 'sourceUrl': ext_row['sourceRecordUrl'],
                         'sourceSha256': ext_row['sourceRecordSha256'],
                         'sourceFeedPath': str(EXTENDED),
                         'sourceReportUrl': ext_row['sourceReportUrl'],
                         'sourceReportSha256': ext_row['sourceReportSha256'],
                         'sourceRecordParts': ext_row['sourceRecordParts'],
                         'controls': controls(row, 'extended'), 'scores': score,
                         'outcomes': outcomes, 'cases': cases})
    require(len({row['runId'] for row in selected}) == len(selected), 'Selected run IDs collide')
    native_selected = []
    for ident, model in native_rows.items():
        run = normalized_natives[ident]
        require(run['condition'] == model['condition'] == 'P0'
                and run['repeatPass'] == model['repeat_pass'] == 'fresh1'
                and model['source_sha256'] == run['sourceRecordSha256']
                and model['source_url'] == run['sourceRecordsUrl'],
                f'{ident}: native controls/source changed')
        source = source_path(model['source_url'])
        require(digest(root / source) == model['source_sha256'],
                f'{ident}: native source hash changed')
        cases, score, outcomes = case_rows(native_answers[ident], references, {'ok'})
        require(score['valid'] == run['valid'] == 60 and score['all_four'] == model['all_four_matches']
                and all(score[key] == run['metrics'][key] for key in ('all_four', *FIELDS)),
                f'{ident}: native score drift')
        native_selected.append({'runId': ident, 'category': 'dedicated-decision',
                                'stratum': 'native-first-P0', 'repeatPass': 'fresh1',
                                'complete': run['complete'], 'savedResponses': run['savedResponses'],
                                'model': model['model'], 'sourceUrl': model['source_url'],
                                'sourceSha256': model['source_sha256'],
                                'sourceFeedPath': str(NATIVE),
                                'sourceReportUrl': None, 'sourceReportSha256': None,
                                'controls': controls(run, 'native'), 'scores': score,
                                'outcomes': outcomes, 'cases': cases})
    native_selected.sort(key=lambda row: list(native_rows).index(row['runId']))
    for row in selected:
        row['pairedWithNative'] = {other['runId']: paired(row['cases'], other['cases'])
                                   for other in native_selected}
    all_runs = native_selected + selected
    require(len({row['runId'] for row in all_runs}) == len(all_runs), 'Cross-category IDs collide')
    case_summaries = []
    for ident in sorted(expected):
        by_stratum = {}
        for stratum in ('historical-first-P0', 'declared-fresh1-P0', 'native-first-P0'):
            relevant = [next(case for case in run['cases'] if case['id'] == ident)
                        for run in all_runs if run['stratum'] == stratum]
            by_stratum[stratum] = {'configurationRows': len(relevant),
                                   'validOutputs': sum(case['allFourMatch'] is not None for case in relevant),
                                   'allFourMatches': sum(case['allFourMatch'] is True for case in relevant),
                                   'outcomes': dict(sorted(Counter(case['status'] for case in relevant).items()))}
        case_summaries.append({'id': ident, 'byStratum': by_stratum})
    source_hashes = {str(path): digest(root / path) for path in
                     (BASE, BASE_SOURCE, EXTENDED, CATALOG, NATIVE, NATIVE_RUNS,
                      INPUTS, REFERENCES, CATEGORY_RULE, L1_CATEGORY, L2_CATEGORY)}
    output = {'schema': 'cross-category-v1', 'scope':
              'Retrospective first-P0 configuration-pass comparison on the same 60 synthetic reviews; no repeats pooled',
              'inferenceRequests': 0,
              'referenceStatus': native['reference_status'],
              'selectionRule': {'historical': 'All P0 general-LLM rows in data-provider-errors-v1, except the explicit Sonnet recovery composite',
                                'declared': 'All general-LLM P0 rows with repeatPass fresh1 or pass1 in extended-run-catalog-v1',
                                'native': 'All seven fresh1/P0 runs in disputed-reviews-v1',
                                'categoryEvidence': str(CATEGORY_RULE),
                                'adaptedExceptionEvidence': [str(L1_CATEGORY), str(L2_CATEGORY)],
                                'noScoreSelection': True},
              'sourceSha256': source_hashes,
              'counts': {'historicalGeneral': sum(r['stratum'] == 'historical-first-P0' for r in selected),
                         'declaredGeneral': sum(r['stratum'] == 'declared-fresh1-P0' for r in selected),
                         'native': len(native_selected), 'excludedP0Rows': len(excluded),
                         'excludedHistorical': sum(row['source'] == str(BASE) for row in excluded),
                         'excludedCatalog': sum(row['source'] == str(CATALOG) for row in excluded)},
              'exclusions': excluded,
              'cases': [{'id': ident, 'feedback': inputs[ident]['feedback'],
                         'reference': references[ident]['proposed_labels']}
                        for ident in sorted(expected)],
              'caseSummaries': case_summaries,
              'runs': all_runs,
              'limits': ['These are configuration-pass observations, not independent reviews or model-family estimates.',
                         'Historical first passes and declared fresh1/pass1 runs are separate strata.',
                         'Partial and invalid outcomes keep the fixed 60-position denominator.',
                         'Route, prompt implementation, batch pattern and effort are not controlled across models.',
                         'Cost fields retain observed, estimated, and unknown-bound distinctions; human review is unpriced.',
                         'Client/request timings are not a common pure inference-time measure.',
                         'Proposed v0.2 references remain disputed on some reviews.']}
    plan = {'schema': 'cross-category-plan-v1', 'sourceSha256': source_hashes,
            'selectionRule': output['selectionRule'], 'counts': output['counts'],
            'exclusions': excluded, 'controlsFields': list(all_runs[0]['controls']),
            'analysis': 'Exact per-case vectors, fixed-60 outcomes, and seven paired native comparisons for every eligible general configuration. No pooled family score.'}
    return output, findings(output), plan


def findings(data: dict) -> str:
    counts = data['counts']
    general = [run for run in data['runs'] if run['category'] == 'general-llm']
    native = [run for run in data['runs'] if run['category'] == 'dedicated-decision']
    lines = [
        '# First-P0 general and native decision comparisons', '',
        'This is a retrospective join of saved predictions on the same 60 fictional development reviews. '
        'The rule selected runs by source cohort, P0/pass identity and declared category, before looking at scores. '
        'It made no inference request. The [dataset](dataset.json) keeps every selected configuration, exact output status, '
        'four-field answer, paired native tally, source link and controls ledger. The [selection plan](plan.json) '
        'lists each excluded P0 row.', '',
        'For historical rows, the exact 60 case vectors are keyed by `sourceCaseKey` in the hash-checked '
        f"[public case projection]({GITHUB}{BASE_SOURCE}). The original run evidence URL is kept as a lead only; "
        'it can point to one probe or batch and is not claimed to contain all 60 answers. Declared fresh1/pass1 rows '
        'carry their separately hash-checked report and record parts.', '',
        f"The joined set has **{counts['historicalGeneral']} historical first-P0 general configurations**, "
        f"**{counts['declaredGeneral']} declared fresh1/pass1 general configurations** and "
        f"**{counts['native']} native decision first-P0 configurations**. "
        f"There are **{counts['excludedP0Rows']} excluded P0 rows** across both source feeds "
        f"({counts['excludedCatalog']} catalog, {counts['excludedHistorical']} historical), "
        'with exact reasons in the plan. '
        'The two general strata are not merged into one model estimate; a later fresh1 pass of a historical model is a separate observation. '
        'The native comparator is the seven-model OpenRouter Choice panel, not the full specialist roster: '
        'historical TypeSafe Jev, Laya, Kev, tuned Alex, direct Cloudflare routes and rules are outside this matched panel. '
        'Their saved evidence remains in the cited source feeds and the exclusions.', '',
        'The AnyJev L1 and L2 systems use development-fold fitted calibration or heads; they are excluded from the '
        'unadapted general-checkpoint cohort even though their backbone is a general LLM. '
        f"[L1 evidence]({GITHUB}{L1_CATEGORY}) · [L2 evidence]({GITHUB}{L2_CATEGORY}).", '',
        '| Stratum | Configuration-pass rows | 60 usable answers | Incomplete phases | All-four match range / 60 |',
        '| --- | ---: | ---: | ---: | ---: |',
    ]
    for key, label in (('historical-first-P0', 'Historical P0'),
                       ('declared-fresh1-P0', 'Declared fresh1/pass1 P0'),
                       ('native-first-P0', 'Native decision fresh1 P0')):
        rows = [row for row in data['runs'] if row['stratum'] == key]
        values = [row['scores']['all_four'] for row in rows]
        lines.append(f"| {label} | {len(rows)} | {sum(row['scores']['valid'] == 60 for row in rows)} | "
                     f"{sum(not row['complete'] for row in rows)} | {min(values)}–{max(values)} |")
    lines.extend(['',
        'These ranges describe configuration-pass rows, not independent samples, model-family averages or a matched causal comparison. '
        'A row with invalid outputs can have a low all-four count for that reason; consult validity and outcome status.', '',
        '| Native first P0 run | Usable / 60 | All four match / 60 | Saved source |',
        '| --- | ---: | ---: | --- |',
    ])
    for run in native:
        lines.append(f"| {run['model']} | {run['scores']['valid']} | {run['scores']['all_four']} | [projection]({run['sourceUrl']}) |")
    lines.extend(['',
        '### Paired saved outcomes', '',
        'Each cell compares a general configuration with the named native configuration on the same fixed 60 IDs. '
        '“General higher” means more all-four reference matches in this saved pass; it is not a model-family estimate. '
        'Invalid or failed general outputs remain nonmatches, and later repeats are excluded.', '',
        '| Native run | General stratum | General higher | Equal | Native higher |',
        '| --- | --- | ---: | ---: | ---: |',
    ])
    for other in native:
        for stratum, label in (('historical-first-P0', 'Historical P0'),
                               ('declared-fresh1-P0', 'Declared fresh1/pass1 P0')):
            rows = [row for row in general if row['stratum'] == stratum]
            higher = sum(row['scores']['all_four'] > other['scores']['all_four'] for row in rows)
            equal = sum(row['scores']['all_four'] == other['scores']['all_four'] for row in rows)
            lower = len(rows) - higher - equal
            lines.append(f"| {other['model']} | {label} | {higher} | {equal} | {lower} |")
    lines.extend(['',
        'The table counts configurations, not independent test sets. Several rows share a checkpoint while changing effort, '
        'route, prompt implementation or pass identity; counting them does not weight a model family fairly.', '',
        '### Cases missed by all seven native runs', '',
        'The following rule includes every review on which all seven native first-P0 answers missed the complete provisional reference. '
        'The general columns show matches among valid outputs and the exact number of eligible configuration rows. '
        'Invalid or failed outputs remain in the eligible denominator.', '',
        '| Review | Native matches | Historical general matches / valid / rows | Declared general matches / valid / rows |',
        '| --- | ---: | ---: | ---: |',
    ])
    unanimous = [row for row in data['caseSummaries']
                 if row['byStratum']['native-first-P0']['allFourMatches'] == 0]
    for row in unanimous:
        historical = row['byStratum']['historical-first-P0']
        declared = row['byStratum']['declared-fresh1-P0']
        lines.append(f"| [{row['id']}]({GITHUB}{NATIVE}) | 0/7 | "
                     f"{historical['allFourMatches']}/{historical['validOutputs']}/{historical['configurationRows']} | "
                     f"{declared['allFourMatches']}/{declared['validOutputs']}/{declared['configurationRows']} |")
    lines.extend(['',
        'DEV-029 is off-topic under the frozen guide, and DEV-030 has an unresolved sentiment boundary. '
        'These reference caveats affect interpretation of apparent misses; the source review has not been silently relabeled. '
        f"[Reference review]({GITHUB}docs/REFERENCE_REVIEW_V1.md) · "
        f"[Per-review answers]({GITHUB}{NATIVE}).", '',
    ])
    equal_pair = next(((row, other) for row in general for other in native
                       if row['scores']['all_four'] == other['scores']['all_four']
                       and row['pairedWithNative'][other['runId']]['general_only_match'] > 0), None)
    require(equal_pair is not None, 'Expected equal-score, different-case example absent')
    general_run, native_run = equal_pair
    comparison = general_run['pairedWithNative'][native_run['runId']]
    general_by_id = {case['id']: case for case in general_run['cases']}
    native_by_id = {case['id']: case for case in native_run['cases']}
    general_only = [ident for ident in sorted(general_by_id)
                    if general_by_id[ident]['allFourMatch'] is True
                    and native_by_id[ident]['allFourMatch'] is not True]
    native_only = [ident for ident in sorted(native_by_id)
                   if native_by_id[ident]['allFourMatch'] is True
                   and general_by_id[ident]['allFourMatch'] is not True]
    native_when_general_invalid = sum(general_by_id[ident]['allFourMatch'] is None
                                      for ident in native_only)
    require(len(general_only) == comparison['general_only_match']
            and len(native_only) == comparison['native_only_match'] + native_when_general_invalid,
            'Equal-score example drift')
    lines.extend([
        '### Equal totals can hide different decisions', '',
        f"The first equal-total but different-case pair in fixed source order is "
        f"[{general_run['runId']}]({general_run['sourceUrl']}) and "
        f"[{native_run['runId']}]({native_run['sourceUrl']}). Both match all four fields on "
        f"{general_run['scores']['all_four']}/60. The general run alone matches "
        f"{len(general_only)} reviews ({', '.join(general_only)}); the native run alone matches "
        f"{len(native_only)} ({', '.join(native_only)}), including {native_when_general_invalid} "
        'where the general run had no usable answer. The recorded surfaces are '
        f"{general_run['controls']['route']} and {native_run['controls']['route']}, respectively. "
        'Equal totals therefore do not imply interchangeable case decisions.', '',
    ])
    lines.extend([
        'Every selected general run is in the dataset, with invalid and failed positions retained and any never-sent positions shown if present. '
        'For each general/native pair, the five outcome counts partition the fixed 60 IDs: both match, only the general run matches, '
        'only the native run matches, neither matches, or the general run has no valid output. '
        'A lower all-four match count can also reflect missing outputs, so validity remains separate.', '',
        'Controls differ. The saved rows span local execution, subscriptions, OpenRouter and other hosted APIs; '
        'some send one review per request and others batch reviews. The dataset retains exact surface, recorded provider, '
        'interface classification, effort, request pattern and count, cost provenance and time basis for each run. '
        'Unrecorded batch size, prompt text, prices and inference-only time remain null. '
        'Do not compare client timings as a common inference-speed measure or treat subscription/local costs as zero.', '',
        'The proposed v0.2 labels remain provisional, including disputed DEV-006, DEV-013 and DEV-030. '
        'These joined results do not show that a model family, checkpoint architecture or combined workflow causes better results '
        'on new reviews. Repeats are not pooled, and every case has one reference row regardless of run count. '
        f"[Reference provenance]({GITHUB}{REFERENCES}) · [Category rule]({GITHUB}{CATEGORY_RULE}) · "
        f"[Historical feed]({GITHUB}{BASE}) · [Extended case feed]({GITHUB}{EXTENDED}) · "
        f"[Seven-native feed]({GITHUB}{NATIVE}).", '',
    ])
    require(len(general) == counts['historicalGeneral'] + counts['declaredGeneral'],
            'Findings general denominator changed')
    return '\n'.join(lines)


def public_projection(data: dict, dataset_sha: str, plan_sha: str, findings_sha: str) -> dict:
    """Small public selector input; the reviewed dataset remains the full record."""
    projected = []
    for row in data['runs']:
        projected.append({key: row[key] for key in (
            'runId', 'category', 'stratum', 'repeatPass', 'complete', 'savedResponses',
            'model', 'sourceUrl', 'sourceSha256', 'sourceCaseKey', 'runEvidenceLeadUrl',
            'sourceReportUrl', 'sourceReportSha256', 'controls', 'scores', 'outcomes',
            'pairedWithNative',
        ) if key in row} | {'cases': [{key: case[key] for key in
                                    ('id', 'status', 'prediction', 'differentFields', 'allFourMatch')}
                                   for case in row['cases']]})
    return {'schema': 'cross-category-public-v1', 'scope': data['scope'],
            'inferenceRequests': 0, 'counts': data['counts'],
            'selectionRule': data['selectionRule'],
            'sourceSha256': {**data['sourceSha256'], str(OUT / 'dataset.json'): dataset_sha,
                             str(OUT / 'plan.json'): plan_sha,
                             str(OUT / 'findings.md'): findings_sha},
            'cases': data['cases'], 'caseSummaries': data['caseSummaries'], 'runs': projected,
            'limits': data['limits']}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true', help='Verify saved output bytes')
    args = parser.parse_args()
    dataset, report, plan = build()
    dataset_text = json.dumps(dataset, indent=2, ensure_ascii=False) + '\n'
    plan_text = json.dumps(plan, indent=2, ensure_ascii=False) + '\n'
    projection = public_projection(dataset, sha256(dataset_text.encode()).hexdigest(),
                                   sha256(plan_text.encode()).hexdigest(),
                                   sha256(report.encode()).hexdigest())
    files = {ROOT / OUT / 'dataset.json': dataset_text,
             ROOT / OUT / 'plan.json': plan_text,
             ROOT / OUT / 'findings.md': report,
             ROOT / PUBLIC_OUTPUT: json.dumps(projection, separators=(',', ':'), ensure_ascii=False) + '\n'}
    for path, content in files.items():
        if args.check:
            require(path.is_file() and path.read_text() == content, f'Stale or absent: {path}')
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    print('Verified cross-category first-P0 analysis' if args.check else 'Wrote cross-category first-P0 analysis')


if __name__ == '__main__':
    main()
