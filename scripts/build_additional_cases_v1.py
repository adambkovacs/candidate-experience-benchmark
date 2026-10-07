#!/usr/bin/env python3
"""Publish only four decision labels and status for 77 source-bound saved runs."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = Path('public-site/additional-cases-v1.json')
SUPPLEMENTAL = Path('public-site/supplemental-decision-runs-v1.json')
SONNET = Path('public-site/sonnet55-fresh-matched3.json')
CLEF = Path('public-site/clef-findings.json')
INPUTS = Path('data/pilot/inputs.jsonl')
REFERENCES = Path('data/pilot/proposed_labels.jsonl')
BASE = 'https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/'
FIELDS = ('sentiment', 'follow_up_needed', 'serious_concern_reported', 'testimonial_potential')
CHOICES = {'sentiment': {'positive', 'negative', 'mixed', 'neutral', 'insufficient_information'},
           **{name: {'yes', 'no', 'insufficient_information'} for name in FIELDS[1:]}}
IDS = {f'DEV-{n:03d}' for n in range(1, 61)}
FAMILIES = {'solar-decide', 'liquid-d1', 'tev1-4b', 'clef-openrouter',
            'clef-flash-openrouter', 'luna-decisions-openrouter', 'perplexity-decider'}
MODEL_KEYS = {'clef-openrouter': 'clef', 'clef-flash-openrouter': 'clef-flash',
              'luna-decisions-openrouter': 'luna-decisions'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def by_id(rows, label):
    result = {}
    for row in rows:
        ident = row.get('id')
        require(ident in IDS and ident not in result, f'{label}: duplicate or unknown ID {ident}')
        result[ident] = row
    require(set(result) == IDS, f'{label}: IDs do not cover DEV-001..060')
    return result


def source(root, relative, expected, tracked):
    path = Path(relative)
    require(not path.is_absolute() and '..' not in path.parts and path.as_posix() in tracked,
            f'{relative}: source is not tracked public evidence')
    require((root / path).is_file(), f'{relative}: source file missing')
    require(sha(root / path) == expected, f'{relative}: source SHA-256 changed')
    return root / path


def score(cases, references):
    result = {'valid': 0, 'all_four': 0, **{field: 0 for field in FIELDS}}
    for row in cases:
        prediction = row['prediction']
        if prediction is None:
            continue
        result['valid'] += 1
        reference = references[row['id']]['proposed_labels']
        result['all_four'] += all(prediction[field] == reference[field] for field in FIELDS)
        for field in FIELDS:
            result[field] += prediction[field] == reference[field]
    return result


def project(run, rows, missing, references, record_path, record_hash, report_path, report_hash):
    seen = {}
    for row in rows:
        ident = row.get('id')
        require(ident in IDS and ident not in seen, f'{run["id"]}: duplicate or unknown case {ident}')
        seen[ident] = row
    require(set(seen) | set(missing) == IDS and not set(seen) & set(missing),
            f'{run["id"]}: source does not account for all 60 positions')
    cases = []
    for ident in sorted(IDS):
        if ident in missing:
            cases.append({'id': ident, 'status': missing[ident], 'prediction': None})
            continue
        row = seen[ident]
        status = row.get('status', 'ok')
        prediction = row.get('prediction')
        if prediction is None and isinstance(row.get('parsed'), dict):
            prediction = row['parsed'].get('prediction')
        require(status in ('ok', 'valid') and isinstance(prediction, dict) and set(prediction) == set(FIELDS),
                f'{run["id"]}/{ident}: saved prediction is not four valid labels')
        require(all(prediction[field] in CHOICES[field] for field in FIELDS),
                f'{run["id"]}/{ident}: label outside the declared choices')
        cases.append({'id': ident, 'status': status,
                      'prediction': {field: prediction[field] for field in FIELDS}})
    scores = score(cases, references)
    require(scores == {'valid': run['valid'], **run['metrics']},
            f'{run["id"]}: case-level score differs from saved run')
    return {'runId': run['id'], 'sourceStage': run['sourceStage'],
            'model': run['model'], 'condition': run['condition'],
            'repeatPass': run['repeatPass'], 'provider': run.get('provider'),
            'surface': run.get('surface'), 'effort': run.get('effort'),
            'referenceVersion': '0.2', 'sourceReportUrl': BASE + report_path,
            'sourceReportSha256': report_hash, 'sourceRecordUrl': BASE + record_path,
            'sourceRecordSha256': record_hash,
            'sourceRecordParts': [{'url': BASE + record_path, 'sha256': record_hash}],
            'scores': scores, 'cases': cases}


def build(root=ROOT):
    tracked = set(subprocess.check_output(['git', 'ls-files'], cwd=root, text=True).splitlines())
    input_rows = by_id(jsonl(root / INPUTS), 'inputs')
    references = by_id(jsonl(root / REFERENCES), 'references')
    require(all(row.get('review_version') == '0.2' and
                set(row.get('proposed_labels', {})) == set(FIELDS) and
                all(row['proposed_labels'][field] in CHOICES[field] for field in FIELDS)
                for row in references.values()), 'Reference version or labels changed')
    require(all(isinstance(row.get('feedback'), str) for row in input_rows.values()),
            'Input review text missing')
    documents = {p: json.loads((root / p).read_text()) for p in (SUPPLEMENTAL, SONNET, CLEF)}
    supplemental, sonnet, clef = (documents[p] for p in (SUPPLEMENTAL, SONNET, CLEF))
    require(supplemental.get('schema') == 'supplemental-decision-runs-v1' and
            len(supplemental['runs']) == 63 and sonnet.get('schema') ==
            'claude-sonnet55-fresh-matched3-findings-v1' and clef.get('schema') ==
            'clef-native-p0-findings-v1', 'Public run source schema or count changed')
    bindings = {item['path']: item['sha256'] for item in supplemental['sources']}
    require(len(bindings) == len(supplemental['sources']), 'Duplicate supplemental source binding')
    require(bindings.get(REFERENCES.as_posix()) == sha(root / REFERENCES),
            'Supplemental reference binding changed')
    cache = {}
    result = []
    for run in supplemental['runs']:
        match = re.fullmatch(r'(.+)-native-fresh([123])-p([012])', run['id'])
        require(match is not None and match[1] in FAMILIES and
                run['repeatPass'] == f'fresh{match[2]}' and run['condition'] == f'P{match[3]}' and
                run['sourceOnlyDetails'] is True and run['records'] == 60,
                f'{run["id"]}: unexpected supplemental identity')
        record_path = run['sourceRecordsUrl'].removeprefix(BASE)
        report_path = run['evidenceUrl'].removeprefix(BASE)
        require(BASE + record_path == run['sourceRecordsUrl'] and
                BASE + report_path == run['evidenceUrl'] and
                bindings.get(record_path) == run['sourceRecordSha256'],
                f'{run["id"]}: source URL or binding mismatch')
        record_file = source(root, record_path, run['sourceRecordSha256'], tracked)
        report_file = root / report_path
        require(report_path in tracked and report_file.is_file(),
                f'{run["id"]}: report is not tracked')
        require(bindings.get(report_path) == sha(report_file),
                f'{run["id"]}: report SHA-256 differs from supplemental binding')
        if record_path not in cache:
            cache[record_path] = json.loads(record_file.read_text())
        projection = cache[record_path]
        if match[1] == 'liquid-d1':
            config = projection['configuration']
            require((config['pass'], config['condition']) ==
                    (run['repeatPass'], run['condition']), f'{run["id"]}: liquid stage mismatch')
            rows = projection['records']
        else:
            stage = f'{run["repeatPass"]}/{run["condition"]}'
            candidates = [item for item in projection['stages'] if item.get('stage') == stage and
                          (match[1] not in MODEL_KEYS or
                           item.get('model_key') == MODEL_KEYS[match[1]])]
            require(len(candidates) == 1, f'{run["id"]}: stage not unique')
            rows = candidates[0]['records']
        missing = {}
        if run['id'] == 'solar-decide-native-fresh3-p2':
            report = json.loads(report_file.read_text())
            require(report['interrupted_stage'] == 'fresh3/P2' and
                    report['interrupted_record_id'] == 'DEV-009' and
                    report['unknown_cost_development_attempts'] == 1,
                    'Solar interrupted position changed')
            missing['DEV-009'] = 'unknown_cost_no_response'
        if run['id'] == 'clef-flash-openrouter-native-fresh3-p2':
            report = json.loads(report_file.read_text())
            stages = [item for item in report['stages'] if item.get('model_key') == 'clef-flash'
                      and item.get('stage') == 'fresh3/P2']
            require(len(stages) == 1 and stages[0]['provider_failure_ids'] == ['DEV-039']
                    and stages[0]['unknown_cost_ids'] == ['DEV-039'],
                    'Clef Flash failed position changed')
            missing['DEV-039'] = 'provider_failure_unknown_cost'
        scoped_run = {**run, 'sourceStage': f'{match[1]}/{run["repeatPass"]}/{run["condition"]}'}
        result.append(project(scoped_run, rows, missing, references, record_path,
                              run['sourceRecordSha256'], report_path, sha(report_file)))
    for effort in ('low', 'medium', 'high', 'xhigh'):
        for condition in ('P0', 'P1', 'P2'):
            cell = sonnet['cells'][effort]['pass1'][condition]['development']
            binding = cell['evidence']['records']
            record_path = 'public-site/sonnet55-fresh-matched3-evidence/evidence/' + binding['path']
            path = source(root, record_path, binding['sha256'], tracked)
            configuration = f'sonnet55-{effort}-fresh-matched3-batch10-v2'
            run = {'id': f'{configuration}--pass1-{condition.lower()}',
                   'sourceStage': f'{configuration}/pass1/{condition}',
                   'model': 'claude-sonnet-5-5', 'condition': condition,
                   'repeatPass': 'pass1', 'provider': 'Claude subscription',
                   'surface': 'Claude subscription', 'effort': effort,
                   'valid': cell['score']['valid'],
                   'metrics': {'all_four': cell['score']['allFour'], **cell['score']['fields']}}
            result.append(project(run, jsonl(path), {}, references, record_path,
                                  binding['sha256'], SONNET.as_posix(), sha(root / SONNET)))
    for name in ('clef', 'clef-flash'):
        record_path = f'results/clef-native-v1/{name}/fresh1/P0/development/records.jsonl'
        path = source(root, record_path, clef['sourceSha256'][record_path], tracked)
        model = clef['models'][name]
        run = {'id': f'{name}-native-fresh1-p0', 'sourceStage': f'{name}/fresh1/P0',
               'model': 'Cloudflare Clef' if name == 'clef' else 'Cloudflare Clef Flash',
               'condition': 'P0', 'repeatPass': 'fresh1', 'provider': 'Cloudflare',
               'surface': 'Cloudflare Workers AI', 'effort': 'not applicable',
               'valid': model['valid'], 'metrics': {'all_four': model['allFourCorrect'],
                   **{field: model['fields'][field]['correct'] for field in FIELDS}}}
        result.append(project(run, jsonl(path), {}, references, record_path,
                              clef['sourceSha256'][record_path], CLEF.as_posix(), sha(root / CLEF)))
    require(len(result) == 77 and len({row['runId'] for row in result}) == 77,
            'Expected 77 distinct added case runs')
    return {'schema': 'additional-cases-v1', 'sourceSha256': {
                path.as_posix(): sha(root / path)
                for path in (SUPPLEMENTAL, SONNET, CLEF, INPUTS, REFERENCES)},
            'referenceStatus': 'Frozen proposed labels v0.2, owner-confirmed human checked on 2026-10-02; still provisional with disputed cases. Agreement is not truth.',
            'cases': [{'id': ident, 'feedback': input_rows[ident]['feedback'],
                       'reference': {field: references[ident]['proposed_labels'][field]
                                     for field in FIELDS}} for ident in sorted(IDS)],
            'runs': result, 'coverage': {'catalogRuns': 77, 'caseRuns': 77,
                                        'reportOnlyRuns': 0, 'gaps': []}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Fail if the committed feed is stale')
    args = parser.parse_args()
    content = json.dumps(build(), ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n'
    if args.check:
        require(OUTPUT.read_text() == content, f'{OUTPUT}: regenerate the feed')
        print('Additional case feed matches its 77 source-bound runs')
    else:
        OUTPUT.write_text(content)
        print(f'Wrote {OUTPUT}')


if __name__ == '__main__':
    main()
