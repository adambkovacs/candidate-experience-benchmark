#!/usr/bin/env python3
"""Project source-bound public case answers for selected extended report rows."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
CATALOG = Path('public-site/extended-run-catalog-v1.json')
INPUTS = Path('data/pilot/inputs.jsonl')
REFERENCES = Path('data/pilot/proposed_labels.jsonl')
OUTPUT = Path('public-site/extended-cases-v1.json')
BASE = 'https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/'
FIELDS = ('sentiment', 'follow_up_needed', 'serious_concern_reported', 'testimonial_potential')
STANDARD_FAMILIES = frozenset({
    'repeats', 'claude-repeats', 'claude-roster-repeats',
    'codex-fresh-repeats', 'gemini-repeats', 'haiku-fresh-matched3',
    'deepseek-fresh-repeats', 'additional-hosted-fresh-repeats',
    'qwen36-off-second-interruption-findings',
    'small-local-repeats', 'legacy-qwen-repeats', 'semif-repeats',
    'semif-generated-repeats', 'laya-repeats', 'anyjev-raw-repeats',
    'anyjev-l0-repeats', 'anyjev-l1-repeats', 'anyjev-l2-repeats',
    'anyjev-generated-repeats',
    'alex-native-repeats',
    'hosted-repeats', 'typesafe-repeats',
    'qwen27-final-descriptive-findings', 'hosted-v2-repeats',
})
SONNET_FAMILY = 'sonnet55-fresh-matched3'
OPENJEV_FAMILIES = frozenset({'openjev-native-repeats', 'openjev-generated-repeats'})
CLEF_FAMILIES = frozenset({'clef-closed-repeat-findings', 'clef-flash-p1-findings',
                           'clef-flash-p2-findings', 'clef-p0-repeat-findings'})
CHOICE_FAMILIES = frozenset({'jev-native-prompt-findings', 'kev-native-prompt-findings',
                             'kev-native-repeats'})
DEEPSEEK_HIGH_FAMILY = 'deepseek-high-remaining6-successor-findings'
DEEPSEEK_LOW_FAMILIES = frozenset({'deepseek-low-fresh3-findings',
    'deepseek-low-p1-successor-findings', 'deepseek-low-remaining6-price-v2-findings',
    'deepseek-low-final-suffix-findings'})
GEMMA_FAMILIES = frozenset({'gemma26-continuation-findings',
    'gemma26-second-continuation-findings', 'gemma26-p2-repeat-findings',
    'gemma26-fresh3-p0-checkpoint', 'gemma26-fresh3-p1-interrupted-checkpoint'})
E4B_FAMILY = 'e4b-interruption-findings'
MISTRAL_FAMILY = 'mistral119-fresh1-p0-findings'
REVIEWED_GEMMA_PROJECTIONS = {
    'fresh2/P0': '624161800e3444ed9efe42e373cd362b049c8cd226242f93a03338aa0d4bbae6',
    'fresh3/P0': '0f9b9ecda16f00f398c8d5bd67076c48160acb95c94deb04a05d70625d974b32',
    'fresh3/P1': 'dabd6464e01ef30043e322bd036a0973e331a66ad038758fabbda15f9499d031',
    'fresh3/P2': '55ddc3390b2b5afc360793a86114b1cb91523a0bd7e90a15b76ee8e681ea5b67',
}
SONNET_MIRROR = Path('public-site/sonnet55-fresh-matched3-evidence/evidence')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def unique_by_id(rows, expected_ids, label):
    result = {}
    for row in rows:
        ident = row.get('id')
        require(ident in expected_ids and ident not in result, f'{label}: duplicate or unknown case ID {ident}')
        result[ident] = row
    require(set(result) == expected_ids, f'{label}: missing case IDs')
    return result


def report_cell(document, run):
    family = run['sourceFamily']
    configuration, repeat, condition = run['sourceStage'].rsplit('/', 2)
    if family == SONNET_FAMILY:
        require(configuration.startswith('sonnet55-'), f'{run["id"]}: unknown Sonnet configuration')
        return document['cells'][configuration.removeprefix('sonnet55-')][repeat][condition]['development']
    if family in OPENJEV_FAMILIES:
        matches = [item for key, item in document['configurations'].items()
                   if item.get('configuration', 'openjev-' + key) == configuration]
        require(len(matches) == 1, f'{run["id"]}: OpenJev configuration not unique')
        stage = matches[0]['freshPasses'][repeat]
        return stage[condition] if family == 'openjev-generated-repeats' else stage
    if family in CLEF_FAMILIES:
        if family == 'clef-closed-repeat-findings':
            cells = [row for row in document['cells']
                     if row['repeat'] == repeat and row['condition'] == condition]
            require(len(cells) == 1, f'{run["id"]}: Clef stage absent')
        elif family in ('clef-flash-p1-findings', 'clef-flash-p2-findings'):
            require(document['phaseByPass'][repeat]['stage'] ==
                    f'clef-flash/{repeat}/{condition}/development',
                    f'{run["id"]}: Flash stage absent')
        else:
            require(configuration == 'cloudflare-clef-flash-direct' and repeat == 'fresh2'
                    and condition == 'P0', f'{run["id"]}: P0 stage absent')
        model_dir = 'clef-flash' if 'flash' in configuration else 'clef'
        path = f'results/clef-native-v1/{model_dir}/{repeat}/{condition}/development/records.jsonl'
        bindings = document.get('sourceBindings') or document.get('sourceSha256')
        require(isinstance(bindings, dict) and path in bindings, f'{run["id"]}: Clef record binding absent')
        extras = []
        if family == 'clef-closed-repeat-findings' and cells[0].get('suffixCompletionSource'):
            suffix = cells[0]['suffixCompletionSource'].replace('completion.json', 'records.jsonl')
            require(suffix in bindings, f'{run["id"]}: Clef suffix binding absent')
            extras.append({'path': suffix, 'sha256': bindings[suffix]})
        return {'evidence': {'records': {'path': path, 'sha256': bindings[path]},
                             'extraRecords': extras}}
    if family in CHOICE_FAMILIES:
        if family == 'kev-native-repeats':
            require(condition == 'P0', f'{run["id"]}: unexpected Kev condition')
            cell = document['passes'][repeat]
            bindings = cell['sourceBindings']
            attempts = [item for item in bindings if item['path'].endswith('attempts.jsonl')]
            require(attempts, f'{run["id"]}: no Kev attempts binding')
            return {'evidence': {'records': attempts[0], 'extraRecords': attempts[1:]}}
        if family == 'jev-native-prompt-findings':
            require(repeat in document['passes'][condition], f'{run["id"]}: Jev stage absent')
            prefix = f'jev-openrouter-native-{condition.lower()}-choice-v1/{repeat}/attempts.jsonl'
        else:
            require(repeat in document['conditions'][condition]['passes'],
                    f'{run["id"]}: Kev prompt stage absent')
            prefix = f'kev-openrouter-native-{condition.lower()}-choice-v1/{repeat}/attempts.jsonl'
        matches = [item for item in document['sourceBindings'] if item['path'].endswith(prefix)]
        require(len(matches) == 1, f'{run["id"]}: prompt attempt binding not unique')
        if family == 'jev-native-prompt-findings' and repeat == 'fresh2' and condition == 'P2':
            outcomes = document['passes'][condition][repeat]['outcomes']
            require(outcomes == {'valid': 17, 'unknown_cost_http_429': 1, 'never_sent': 42},
                    f'{run["id"]}: stopped-stage outcomes changed')
            return {'evidence': {'records': matches[0]},
                    'missingStatuses': {**{f'DEV-{number:03d}': 'never_sent'
                                           for number in range(19, 61)},
                                        'DEV-018': 'unknown_cost_http_429'}}
        return {'evidence': {'records': matches[0]}}
    if family == DEEPSEEK_HIGH_FAMILY:
        require(f'{repeat}/{condition}' in document['phases'], f'{run["id"]}: high stage absent')
        suffix = f'/{repeat}/{condition}/development.attempts.jsonl'
        matches = [item for item in document['sourceBindings'] if item['path'].endswith(suffix)]
        require(len(matches) == 1, f'{run["id"]}: high stage binding not unique')
        extras = []
        if repeat == 'fresh2' and condition == 'P2':
            extras = [item for item in document['sourceBindings']
                      if item['path'].endswith('/fresh2/P2/development.public.json')]
            require(len(extras) == 1, f'{run["id"]}: high parent projection absent')
        return {'evidence': {'records': matches[0], 'extraRecords': extras}}
    if family in DEEPSEEK_LOW_FAMILIES:
        if family == 'deepseek-low-fresh3-findings':
            suffix = f'/{repeat}/{condition}/public-projection.json'
        elif family == 'deepseek-low-p1-successor-findings':
            suffix = '/fresh2-p1-public-projection.json'
        elif family == 'deepseek-low-remaining6-price-v2-findings':
            suffix = '/fresh2-p2-sanitized-projection-v1.json'
        else:
            suffix = '/phase-03-suffix.public.json'
        matches = [item for item in document['sourceBindings'] if item['path'].endswith(suffix)]
        require(len(matches) == 1, f'{run["id"]}: low projection binding not unique')
        extras = []
        if family == 'deepseek-low-final-suffix-findings':
            extras = [item for item in document['sourceBindings']
                      if item['path'].endswith('/suffix.records.jsonl')]
            require(len(extras) == 1, f'{run["id"]}: final suffix binding absent')
        return {'evidence': {'records': matches[0], 'extraRecords': extras}}
    if family in GEMMA_FAMILIES:
        bindings = document['sourceBindings']
        if family == 'gemma26-continuation-findings':
            if repeat == 'fresh1' and condition == 'P2':
                suffixes = ['/public-prefix-v1/development.attempts.jsonl',
                            '/fresh1/P2/suffix.attempts.jsonl']
            else:
                suffixes = [f'/{repeat}/{condition}/development.attempts.jsonl']
        elif family == 'gemma26-second-continuation-findings':
            suffixes = ['/interruption-continuation-v1/fresh2/P0/development.attempts.jsonl',
                        '/second-interruption-continuation-v1/fresh2/P0/suffix.public-summary.json']
        elif family in ('gemma26-fresh3-p0-checkpoint', 'gemma26-fresh3-p1-interrupted-checkpoint'):
            suffixes = ['/public-projection.json']
        elif family == 'gemma26-p2-repeat-findings':
            require(repeat == 'fresh3' and condition == 'P2', f'{run["id"]}: P2 stage changed')
            suffixes = ['/public-composite-projection.json']
        else:
            return {'evidence': {}}
        selected = []
        for suffix in suffixes:
            matches = [item for item in bindings if item['path'].endswith(suffix)]
            require(len(matches) == 1, f'{run["id"]}: Gemma binding not unique for {suffix}')
            selected.append(matches[0])
        reviewed = REVIEWED_GEMMA_PROJECTIONS.get(f'{repeat}/{condition}')
        if reviewed and selected[-1]['path'].endswith('.json'):
            require(selected[-1]['sha256'] == reviewed,
                    f'{run["id"]}: reviewed projection hash changed')
        return {'evidence': {'records': selected[0], 'extraRecords': selected[1:]}}
    if family == 'qwen36-off-second-interruption-findings' and (repeat, condition) in (
            ('fresh1', 'P0'), ('fresh3', 'P1')):
        suffix = ('/never-sent-suffix-v1/reconciliation.json' if repeat == 'fresh1'
                  else '/second-interruption-v1/suffix-reconciliation.json')
        matches = [item for item in document['sourceBindings'] if item['path'].endswith(suffix)]
        require(len(matches) == 1, f'{run["id"]}: Qwen OFF reconciliation binding absent')
        return {'evidence': {'records': matches[0]}}
    if family == E4B_FAMILY:
        require(repeat == 'fresh2' and condition == 'P2', f'{run["id"]}: E4B stage changed')
        suffixes = ['/fresh2/P2/development.records.jsonl',
                    '/interruption-continuation-v1/fresh2/P2/suffix.records.jsonl',
                    '/p2-unsent-suffix-v1/suffix.records.jsonl']
        selected = []
        for suffix in suffixes:
            matches = [item for item in document['sourceBindings'] if item['path'].endswith(suffix)]
            require(len(matches) == 1, f'{run["id"]}: E4B binding not unique')
            selected.append(matches[0])
        missing_statuses = {ident: 'unknown_started' for ident in document['unknownIds']}
        missing_statuses.update({ident: 'never_sent' for ident in document['neverSentIds']})
        return {'evidence': {'records': selected[0], 'extraRecords': selected[1:]},
                'missingStatuses': missing_statuses}
    if family == MISTRAL_FAMILY:
        require(repeat == 'fresh1' and condition == 'P0', f'{run["id"]}: Mistral stage changed')
        bindings = document['lineage']['sourceBindings']
        parsed = [item for item in bindings if item['path'].endswith('.parsed.jsonl')]
        attempts = [item for item in bindings if item['path'].endswith(
                    ('development.attempts.jsonl', 'suffix.attempts.jsonl'))]
        require(len(parsed) == 5 and len(attempts) == 5,
                f'{run["id"]}: Mistral source parts changed')
        return {'evidence': {'records': parsed[0], 'extraRecords': parsed[1:],
                             'statusRecords': attempts},
                'missingStatuses': {ident: 'failed_in_report'
                                    for ident in document['outcomes']['failedIds']}}
    series = document.get('series', [document])
    matches = [item for item in series if item.get('configuration') == configuration]
    require(len(matches) == 1, f'{run["id"]}: report configuration not unique')
    cell = matches[0]['passes'][repeat][condition]
    if (family == 'hosted-repeats' and configuration ==
            'openrouter-paid-mistral-small32-24b-venice-not-applicable'
            and repeat == 'repeat2' and condition == 'P1'):
        suffix = '/repeat2/P1/never-sent-suffix-v1/development.attempts.jsonl'
        bindings = [item for item in matches[0]['sourceBindings']
                    if item['path'].endswith(suffix)]
        require(len(bindings) == 1, f'{run["id"]}: hosted suffix binding absent')
        cell = {**cell, 'evidence': {**cell['evidence'], 'extraRecords': bindings}}
    if (family == 'qwen27-final-descriptive-findings' and not cell.get('evidence')
            and repeat == 'fresh3' and condition in ('P0', 'P1')):
        effort = 'medium' if configuration.endswith('-medium') else 'xhigh'
        v1 = f'/interruption-continuation-v1/{effort}/public-evidence-v1/'
        v2 = f'/interruption-continuation-v2/{effort}/fresh3/{condition}/'
        suffixes = ({('medium', 'P0'): [v1 + 'prefix.positions.jsonl',
                                         v1 + 'suffix.positions.jsonl', v2 + 'suffix/suffix.attempts.jsonl'],
                     ('medium', 'P1'): [v2 + 'development/development.attempts.jsonl'],
                     ('xhigh', 'P0'): [v1 + 'prefix.positions.jsonl', v1 + 'suffix.positions.jsonl'],
                     ('xhigh', 'P1'): [v1 + 'p1.positions.jsonl', v2 + 'suffix/suffix.attempts.jsonl']})[(effort, condition)]
        selected = []
        for suffix in suffixes:
            bindings = [item for item in document['sourceBindings'] if item['path'].endswith(suffix)]
            require(len(bindings) == 1, f'{run["id"]}: Qwen composite binding not unique')
            selected.append(bindings[0])
        return {'evidence': {'records': selected[0], 'extraRecords': selected[1:]}}
    return cell


def binding_by_digest(document, sha256, suffix='attempts.jsonl'):
    bindings = document.get('sourceBindings') or []
    if isinstance(bindings, dict):
        bindings = [{'path': path, 'sha256': digest} for path, digest in bindings.items()]
    matches = [item for item in bindings if item.get('sha256') == sha256
               and item.get('path', '').endswith(suffix)]
    return sorted(matches, key=lambda item: item['path'])[0] if matches else None


def score_from_cases(rows, references):
    valid = 0
    all_four = 0
    fields = {field: 0 for field in FIELDS}
    for row in rows:
        prediction = row['prediction']
        if prediction is None:
            continue
        valid += 1
        reference = references[row['id']]['proposed_labels']
        if all(prediction[field] == reference[field] for field in FIELDS):
            all_four += 1
        for field in FIELDS:
            fields[field] += prediction[field] == reference[field]
    return {'valid': valid, 'all_four': all_four, **fields}


def build(root=ROOT):
    catalog_path = root / CATALOG
    catalog = json.loads(catalog_path.read_text())
    require(catalog.get('schema') == 'extended-run-catalog-v1', 'Unexpected catalog schema')
    runs = catalog['runs']
    require(len(runs) == catalog['runCount'], 'Catalog run count changed')
    input_rows = read_jsonl(root / INPUTS)
    reference_rows = read_jsonl(root / REFERENCES)
    expected_ids = {f'DEV-{number:03d}' for number in range(1, 61)}
    inputs = unique_by_id(input_rows, expected_ids, 'inputs')
    references = unique_by_id(reference_rows, expected_ids, 'references')
    require(all(row.get('review_version') == '0.2' for row in references.values()), 'Reference version changed')
    require(all(set(row['proposed_labels']) == set(FIELDS) for row in references.values()), 'Reference fields changed')
    require(all(isinstance(inputs[ident].get('feedback'), str) for ident in expected_ids), 'Missing review text')
    tracked = set(subprocess.check_output(['git', 'ls-files'], cwd=root, text=True).splitlines())
    report_cache = {}
    projected = []
    gaps = []
    for run in runs:
        family = run['sourceFamily']
        if (family not in STANDARD_FAMILIES and family != SONNET_FAMILY
                and family not in OPENJEV_FAMILIES and family not in CLEF_FAMILIES
                and family not in CHOICE_FAMILIES and family != DEEPSEEK_HIGH_FAMILY
                and family not in DEEPSEEK_LOW_FAMILIES and family not in GEMMA_FAMILIES
                and family != E4B_FAMILY and family != MISTRAL_FAMILY):
            gaps.append({'runId': run['id'], 'sourceFamily': family,
                         'sourceReportUrl': run['sourceRecordsUrl'],
                         'reason': 'source-specific adapter not implemented'})
            continue
        report_relative = Path('public-site') / (family + '.json')
        require(run['sourceRecordsUrl'] == BASE + report_relative.as_posix(), f'{run["id"]}: report URL changed')
        if family not in report_cache:
            report_cache[family] = json.loads((root / report_relative).read_text())
        report = report_cache[family]
        report_sha = digest(root / report_relative)
        require(report_sha == run['sourceRecordSha256'], f'{run["id"]}: report SHA mismatch')
        cell = report_cell(report, run)
        evidence = cell.get('evidence', {})
        record_binding = evidence.get('records') or (evidence.get('development') or {}).get('records')
        if family == 'hosted-repeats':
            record_binding = evidence.get('attempts')
        elif family == 'typesafe-repeats':
            record_binding = evidence.get('developmentStage0attempts.jsonl')
        elif family in ('qwen27-final-descriptive-findings', 'hosted-v2-repeats'):
            if evidence.get('attempts_sha256'):
                record_binding = binding_by_digest(report, evidence['attempts_sha256'])
        elif family == 'anyjev-l2-repeats':
            record_binding = (evidence.get('full') or {}).get('full.jsonl')
        elif family == 'additional-hosted-fresh-repeats' and not record_binding:
            configuration, repeat, condition = run['sourceStage'].rsplit('/', 2)
            suffix = f'/{configuration}/{repeat}/{condition}/development.attempts.jsonl'
            matches = [item for item in report['sourceBindings'] if item['path'].endswith(suffix)]
            if not matches and configuration == 'openrouter-paid-qwen36-35b-a3b-on-authority-v3-hosted-v2' and repeat == 'fresh1' and condition in ('P0', 'P1'):
                suffix = f'/qwen36-on-hosted-authority-v3-v2/fresh1/{condition}/development.attempts.jsonl'
                matches = [item for item in report['sourceBindings'] if item['path'].endswith(suffix)]
                require(len(matches) == 1, f'{run["id"]}: Qwen ON primary binding absent')
                if condition == 'P1':
                    continuation = [item for item in report['sourceBindings'] if item['path'].endswith(
                        '/p1-unsent-continuation-v1/fresh1/P1/development.attempts.jsonl')]
                    require(len(continuation) == 1, f'{run["id"]}: Qwen ON continuation binding absent')
                    cell = {**cell, 'evidence': {**evidence, 'extraRecords': continuation}}
                    evidence = cell['evidence']
            if not matches and configuration.endswith('-high-authority-v3-current-price'):
                suffix = f'/deepseek-high-authority-v3/{repeat}/{condition}/development.attempts.jsonl'
                matches = [item for item in report['sourceBindings'] if item['path'].endswith(suffix)]
            if not matches and configuration.endswith('-high-authority-v3-current-price-remaining7-price-v1'):
                suffix = f'/deepseek-high-remaining7-price-v1/execution-adapter-v1/{repeat}/{condition}/development.attempts.jsonl'
                matches = [item for item in report['sourceBindings'] if item['path'].endswith(suffix)]
            require(len(matches) <= 1, f'{run["id"]}: ambiguous hosted attempt binding')
            record_binding = matches[0] if matches else None
        if not isinstance(record_binding, dict):
            gaps.append({'runId': run['id'], 'sourceFamily': family,
                         'sourceReportUrl': run['sourceRecordsUrl'],
                         'reason': 'report has no bound normalized record file'})
            continue
        def read_binding(binding):
            original_path = Path(binding['path'])
            require(not original_path.is_absolute() and '..' not in original_path.parts,
                    f'{run["id"]}: unsafe record path')
            record_path = SONNET_MIRROR / original_path if family == SONNET_FAMILY else original_path
            if record_path.as_posix() not in tracked or not (root / record_path).is_file():
                return None
            require(digest(root / record_path) == binding['sha256'],
                    f'{run["id"]}: record SHA mismatch')
            if record_path.name == 'development.public.json':
                public_projection = json.loads((root / record_path).read_text())
                require(public_projection.get('schema') == 'deepseek-high-parent-public-projection-v1'
                        and isinstance(public_projection.get('attempts'), list),
                        f'{run["id"]}: unexpected public projection')
                return record_path, public_projection['attempts']
            if family in DEEPSEEK_LOW_FAMILIES and record_path.suffix == '.json':
                projection = json.loads((root / record_path).read_text())
                require(isinstance(projection.get('positions'), list),
                        f'{run["id"]}: low projection positions absent')
                return record_path, projection['positions']
            if family in GEMMA_FAMILIES and record_path.suffix == '.json':
                projection = json.loads((root / record_path).read_text())
                require(isinstance(projection.get('responses'), list),
                        f'{run["id"]}: Gemma response projection absent')
                return record_path, projection['responses']
            if family == 'qwen36-off-second-interruption-findings' and record_path.suffix == '.json':
                projection = json.loads((root / record_path).read_text())
                require(isinstance(projection.get('positions'), list),
                        f'{run["id"]}: Qwen OFF reconciliation positions absent')
                return record_path, projection['positions']
            return record_path, read_jsonl(root / record_path)

        primary = read_binding(record_binding)
        if primary is None:
            gaps.append({'runId': run['id'], 'sourceFamily': family,
                         'sourceReportUrl': run['sourceRecordsUrl'],
                         'reason': 'bound record file is not in committed public evidence'})
            continue
        record_path, source_rows = primary
        if family in CHOICE_FAMILIES:
            if family == 'jev-native-prompt-findings' and run['repeatPass'] == 'fresh2' and run['condition'] == 'P2':
                parsed_ids = {row['id'] for row in source_rows if row.get('stage') == 'parsed'}
                started_ids = {row['id'] for row in source_rows if row.get('stage') == 'started'}
                require(parsed_ids == {f'DEV-{number:03d}' for number in range(1, 18)}
                        and 'DEV-018' in started_ids and 'DEV-018' not in parsed_ids,
                        f'{run["id"]}: stopped-stage IDs changed')
            terminal_stage = 'validated' if family == 'kev-native-repeats' else 'parsed'
            source_rows = [row for row in source_rows if row.get('stage') == terminal_stage]
        source_parts = [{'url': BASE + record_path.as_posix(), 'sha256': record_binding['sha256']}]
        raw_rows = {}
        for raw in source_rows:
            ident = raw.get('id')
            require(ident in expected_ids and ident not in raw_rows,
                    f'{run["id"]}: duplicate or unknown case ID {ident}')
            raw_rows[ident] = raw
        if len(raw_rows) < 60:
            smoke_binding = (evidence.get('smoke') or {}).get('records')
            if isinstance(smoke_binding, dict):
                smoke = read_binding(smoke_binding)
                if smoke is not None:
                    smoke_path, smoke_rows = smoke
                    for raw in smoke_rows:
                        ident = raw.get('id')
                        require(ident in expected_ids, f'{run["id"]}: unknown smoke case {ident}')
                        if ident not in raw_rows:
                            raw_rows[ident] = raw
                    source_parts.append({'url': BASE + smoke_path.as_posix(),
                                         'sha256': smoke_binding['sha256']})
        for extra_binding in evidence.get('extraRecords', []):
            extra = read_binding(extra_binding)
            if extra is None:
                continue
            extra_path, extra_rows = extra
            for raw in extra_rows:
                ident = raw.get('id')
                if (raw.get('stage') == 'parsed' or extra_path.name == 'development.public.json') and ident not in raw_rows:
                    raw_rows[ident] = raw
                elif family in GEMMA_FAMILIES.union({E4B_FAMILY, 'hosted-repeats',
                        'additional-hosted-fresh-repeats'}).union(CLEF_FAMILIES).union(
                        {'qwen27-final-descriptive-findings'}) and ident not in raw_rows:
                    raw_rows[ident] = raw
                elif family == MISTRAL_FAMILY and ident not in raw_rows:
                    raw_rows[ident] = raw
                elif extra_path.name == 'suffix.records.jsonl' and ident in raw_rows:
                    require(raw_rows[ident].get('status') == 'never_sent',
                            f'{run["id"]}: suffix overwrites a saved outcome')
                    raw_rows[ident] = raw
            source_parts.append({'url': BASE + extra_path.as_posix(),
                                 'sha256': extra_binding['sha256']})
        status_rows = {}
        for status_binding in evidence.get('statusRecords', []):
            part = read_binding(status_binding)
            if part is None:
                continue  # Private attempt file: never republish it in the case feed.
            status_path, rows = part
            for row in rows:
                ident = row.get('id')
                require(ident in expected_ids and ident not in status_rows,
                        f'{run["id"]}: Mistral attempt IDs repeat or drift')
                status_rows[ident] = row['status']
            source_parts.append({'url': BASE + status_path.as_posix(),
                                 'sha256': status_binding['sha256']})
        cases = []
        for ident in sorted(expected_ids):
            raw = raw_rows.get(ident)
            if raw is None:
                status = status_rows.get(ident, cell.get('missingStatuses', {}).get(ident,
                                             'not_in_bound_evidence'))
                cases.append({'id': ident, 'status': status, 'prediction': None})
                continue
            decision = raw.get('decision', raw)
            require(isinstance(decision, dict), f'{run["id"]}/{ident}: malformed decision')
            status = raw.get('status') or decision.get('status')
            if family == MISTRAL_FAMILY:
                status = status_rows.get(ident, 'ok')
            if raw.get('stage') == 'parsed':
                require(type(raw.get('valid')) is bool, f'{run["id"]}/{ident}: parsed validity missing')
                status = 'ok' if raw['valid'] else 'invalid_output'
            elif raw.get('stage') == 'validated' and family == 'kev-native-repeats':
                status = 'ok'
            require(isinstance(status, str) and status, f'{run["id"]}/{ident}: missing status')
            prediction = decision.get('prediction')
            if prediction is None and isinstance(raw.get('parsed'), dict):
                prediction = raw['parsed'].get('prediction')
            if status in ('ok', 'valid'):
                require(isinstance(prediction, dict) and set(prediction) == set(FIELDS),
                        f'{run["id"]}/{ident}: invalid prediction')
                prediction = {field: prediction[field] for field in FIELDS}
                require(all(isinstance(value, str) and value for value in prediction.values()),
                        f'{run["id"]}/{ident}: invalid answer')
            else:
                # An invalid output can contain JSON that is not a valid four-field
                # answer. Keep its saved status; do not turn that JSON into labels.
                prediction = None
            cases.append({'id': ident, 'status': status, 'prediction': prediction})
        scores = score_from_cases(cases, references)
        if scores != {'valid': run['valid'], **run['metrics']} and len(raw_rows) < 60:
            gaps.append({'runId': run['id'], 'sourceFamily': family,
                         'sourceReportUrl': run['sourceRecordsUrl'],
                         'reason': 'bound public files do not reproduce the complete report score'})
            continue
        require(scores == {'valid': run['valid'], **run['metrics']}, f'{run["id"]}: case scores do not match catalog')
        projected.append({
            'runId': run['id'], 'sourceStage': run['sourceStage'],
            'model': run['model'], 'condition': run['condition'],
            'repeatPass': run['repeatPass'], 'provider': run.get('provider'),
            'surface': run.get('surface'), 'effort': run.get('effort'),
            'referenceVersion': '0.2', 'sourceReportUrl': run['sourceRecordsUrl'],
            'sourceReportSha256': report_sha,
            'sourceRecordUrl': BASE + record_path.as_posix(),
            'sourceRecordSha256': record_binding['sha256'],
            'sourceRecordParts': source_parts,
            'projectionReview': ('Field whitelist applied on 2026-10-07: only case ID, '
                                 'saved status, and four label values are projected from the '
                                 'SHA-256-bound public source; other metadata is not republished.'
                                 if family in GEMMA_FAMILIES and f'{run["repeatPass"]}/{run["condition"]}'
                                 in REVIEWED_GEMMA_PROJECTIONS else None),
            'scores': scores, 'cases': cases,
        })
    require(len(projected) + len(gaps) == len(runs), 'Coverage does not reconcile')
    require(len({row['runId'] for row in projected}) == len(projected), 'Repeated run ID')
    coverage_by_family = {}
    for run in projected:
        family = run['sourceReportUrl'].split('/')[-1].removesuffix('.json')
        coverage_by_family.setdefault(family, {'caseRuns': 0, 'reportOnlyRuns': 0})['caseRuns'] += 1
    for gap in gaps:
        coverage_by_family.setdefault(gap['sourceFamily'], {'caseRuns': 0, 'reportOnlyRuns': 0})['reportOnlyRuns'] += 1
    return {
        'schema': 'extended-cases-v1',
        'sourceSha256': {str(path): digest(root / path) for path in (CATALOG, INPUTS, REFERENCES)},
        'referenceStatus': 'Frozen proposed labels v0.2, owner-confirmed human checked on 2026-10-02; still provisional with disputed cases. Agreement is not truth.',
        'cases': [{'id': ident, 'feedback': inputs[ident]['feedback'],
                   'reference': {field: references[ident]['proposed_labels'][field] for field in FIELDS}}
                  for ident in sorted(expected_ids)],
        'runs': projected,
        'coverage': {'catalogRuns': len(runs), 'caseRuns': len(projected),
                     'reportOnlyRuns': len(gaps),
                     'byFamily': dict(sorted(coverage_by_family.items())),
                     'gaps': gaps},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='verify output is current')
    args = parser.parse_args()
    content = json.dumps(build(), ensure_ascii=False, separators=(',', ':')) + '\n'
    if args.check:
        require((ROOT / OUTPUT).read_text() == content, 'Extended case feed is stale')
    else:
        (ROOT / OUTPUT).write_text(content)
    print('Extended case feed verified' if args.check else 'Extended case feed written')


if __name__ == '__main__':
    main()
