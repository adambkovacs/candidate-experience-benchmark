#!/usr/bin/env python3
"""Offline sensitivity to three explicitly documented provisional-label alternatives."""

from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path

import build_disputed_reviews_v1 as disputed_builder
import build_extended_cases_v1 as extended_builder


ROOT = Path(__file__).resolve().parents[1]
EXTENDED = Path('public-site/extended-cases-v1.json')
NATIVE = Path('public-site/disputed-reviews-v1.json')
REVISION = Path('data/pilot/reference-revisions/v0.3.json')
REVIEW = Path('docs/REFERENCE_REVIEW_V1.md')
GUIDE = Path('docs/LABELING_GUIDE.md')
REFERENCES = Path('data/pilot/proposed_labels.jsonl')
OUTPUT = Path('results/reference-sensitivity-v1')
FIELDS = disputed_builder.FIELDS
ALTERNATIVES = (
    ('DEV-006', 'serious_concern_reported', 'insufficient_information', 'no', 'proposed_revision'),
    ('DEV-013', 'sentiment', 'neutral', 'positive', 'needs_human'),
    ('DEV-030', 'sentiment', 'neutral', 'negative', 'needs_human'),
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def reviewed_alternatives(root: Path = ROOT, revision_path: Path = REVISION) -> list[dict]:
    revision = json.loads((root / revision_path).read_text())
    require(revision.get('schema_version') == 'reference-revision-proposal-v1' and
            revision.get('revision') == 'v0.3' and revision.get('status') == 'proposed_not_applied' and
            revision.get('base_reference_path') == str(REFERENCES) and
            revision.get('base_reference_sha256') == digest(root / REFERENCES) and
            revision.get('guide_path') == str(GUIDE) and
            revision.get('guide_sha256') == digest(root / GUIDE) and
            revision.get('source_review') == str(REVIEW),
            'Reference proposal source or status changed')
    raw = revision.get('changes')
    human = revision.get('unchanged_needs_human')
    require(isinstance(raw, list) and len(raw) == 1 and isinstance(human, list) and len(human) == 2,
            'Reference alternative set changed')
    extracted = [
        (raw[0].get('id'), raw[0].get('field'), raw[0].get('from'), raw[0].get('to'),
         'proposed_revision' if raw[0].get('decision') == 'definitive_under_current_guide' else None),
        *[(item.get('id'), item.get('field'), item.get('saved'), item.get('alternative'),
           'needs_human') for item in human],
    ]
    require(tuple(extracted) == ALTERNATIVES,
            'Documented alternative labels changed; do not invent replacements')
    require((root / REVIEW).is_file(), 'Dated reference review missing')
    return [{'id': case, 'field': field, 'saved': saved, 'alternative': alternative,
             'decision_status': status} for case, field, saved, alternative, status in ALTERNATIVES]


def case_effect(case: str, prediction: dict | None, reference: dict,
                hypothetical: dict, status: str) -> dict:
    if prediction is None:
        return {'id': case, 'status': status, 'prediction': None,
                'saved_all_four_match': False, 'hypothetical_all_four_match': False,
                'all_four_delta': 0, 'field_effects': {}}
    saved_match = prediction == reference
    new_match = prediction == hypothetical
    fields = {field: {'saved_reference': reference[field],
                      'hypothetical_reference': hypothetical[field],
                      'prediction': prediction[field],
                      'saved_match': prediction[field] == reference[field],
                      'hypothetical_match': prediction[field] == hypothetical[field]}
              for field in FIELDS if reference[field] != hypothetical[field]}
    return {'id': case, 'status': status, 'prediction': prediction,
            'saved_all_four_match': saved_match,
            'hypothetical_all_four_match': new_match,
            'all_four_delta': int(new_match) - int(saved_match),
            'field_effects': fields}


def score_run(run_id: str, cases: dict[str, dict], references: dict[str, dict],
              changes: dict[str, dict]) -> dict:
    require(set(cases) == set(references) == {f'DEV-{number:03d}' for number in range(1, 61)},
            f'{run_id}: fixed 60-case set changed')
    saved = {'all_four': 0, **{field: 0 for field in FIELDS}}
    hypothetical = {'all_four': 0, **{field: 0 for field in FIELDS}}
    changed = []
    valid = 0
    for case in sorted(references):
        answer = cases[case]
        prediction = answer['prediction']
        if prediction is None:
            continue
        require(isinstance(prediction, dict) and set(prediction) == set(FIELDS),
                f'{run_id}/{case}: incomplete saved prediction')
        valid += 1
        reference = references[case]
        revised = dict(reference)
        revised.update(changes.get(case, {}))
        saved['all_four'] += prediction == reference
        hypothetical['all_four'] += prediction == revised
        for field in FIELDS:
            saved[field] += prediction[field] == reference[field]
            hypothetical[field] += prediction[field] == revised[field]
    for case, fields in sorted(changes.items()):
        reference = references[case]
        revised = {**reference, **fields}
        answer = cases[case]
        changed.append(case_effect(case, answer['prediction'], reference, revised, answer['status']))
    return {
        'id': run_id, 'denominator': 60, 'valid': valid,
        'saved_scores': saved, 'hypothetical_scores': hypothetical,
        'score_deltas': {field: hypothetical[field] - saved[field] for field in saved},
        'changed_case_effects': changed,
    }


def extended_scores(runs: list[dict], references: dict[str, dict],
                    changes: dict[str, dict]) -> list[dict]:
    results = []
    for run in runs:
        answers = {row['id']: row for row in run['cases']}
        scored = score_run(run['runId'], answers, references, changes)
        require(scored['saved_scores'] == {**{'all_four': run['scores']['all_four']},
                 **{field: run['scores'][field] for field in FIELDS}} and
                scored['valid'] == run['scores']['valid'],
                f"{run['runId']}: frozen extended score changed")
        results.append(scored)
    return results


def native_scores(models: list[dict], reviews: list[dict], references: dict[str, dict],
                  changes: dict[str, dict]) -> list[dict]:
    output = []
    for model in models:
        answers = {review['id']: {'prediction': next(answer['prediction'] for answer in review['answers']
                                                      if answer['model_id'] == model['id']),
                                  'status': 'valid'} for review in reviews}
        scored = score_run(model['id'], answers, references, changes)
        require(scored['saved_scores']['all_four'] == model['all_four_matches'] and
                scored['valid'] == 60, f"{model['id']}: frozen native score changed")
        output.append(scored)
    return output


def summary(rows: list[dict]) -> dict:
    deltas = Counter(row['score_deltas']['all_four'] for row in rows)
    return {
        'run_count': len(rows),
        'all_four_delta_distribution': {str(delta): deltas[delta] for delta in sorted(deltas)},
        'improved_runs': sum(row['score_deltas']['all_four'] > 0 for row in rows),
        'declined_runs': sum(row['score_deltas']['all_four'] < 0 for row in rows),
        'unchanged_runs': deltas[0],
    }


def analysis(root: Path = ROOT) -> dict:
    alternatives = reviewed_alternatives(root)
    extended = json.loads((root / EXTENDED).read_text())
    native = json.loads((root / NATIVE).read_text())
    require(extended == extended_builder.build(root),
            'Extended cases differ from SHA-bound public-source rebuild')
    require(native == disputed_builder.build(root),
            'Seven native cases differ from SHA-bound public-source rebuild')
    references = {row['id']: row['reference'] for row in extended['cases']}
    require(len(references) == 60 and
            references == {row['id']: row['reference'] for row in native['reviews']},
            'Cohorts do not share the frozen 60 reference vectors')
    for alternative in alternatives:
        require(references[alternative['id']][alternative['field']] == alternative['saved'],
                'Documented saved label differs from frozen source')
    scenarios = []
    for count in range(1, len(alternatives) + 1):
        for selected in combinations(alternatives, count):
            changes = {item['id']: {item['field']: item['alternative']} for item in selected}
            extended_runs = extended_scores(extended['runs'], references, changes)
            native_runs = native_scores(native['models'], native['reviews'], references, changes)
            scenarios.append({
                'id': '+'.join(item['id'].lower().replace('-', '') for item in selected),
                'status': 'hypothetical_not_applied',
                'changed_labels': selected,
                'changed_ids': [item['id'] for item in selected],
                'extended_summary': summary(extended_runs),
                'native_seven_summary': summary(native_runs),
                'extended_run_deltas': extended_runs,
                'native_seven_run_deltas': native_runs,
            })
    require(len(scenarios) == 7 and len(extended['runs']) == 637 and
            len(native['models']) == 7, 'Sensitivity cohort coverage changed')
    return {
        'schema': 'reference-sensitivity-v1',
        'reference_status': 'frozen_v0.2_provisional_unchanged',
        'meaning': 'Retrospective agreement sensitivity to documented alternative labels, not corrected scores or out-of-sample accuracy.',
        'source_sha256': {str(path): digest(root / path) for path in
                          (EXTENDED, NATIVE, REVISION, REVIEW, GUIDE, REFERENCES)},
        'extended_source_sha256': extended['sourceSha256'],
        'native_source_sha256': native['source_sha256'],
        'denominator_per_run': 60,
        'extended_run_count': len(extended['runs']),
        'native_seven_run_count': len(native['models']),
        'extended_run_sources': [
            {'id': run['runId'], 'source_report_url': run['sourceReportUrl'],
             'source_report_sha256': run['sourceReportSha256'],
             'source_record_parts': run['sourceRecordParts']}
            for run in extended['runs']
        ],
        'native_seven_run_sources': [
            {'id': model['id'], 'source_path': model['source_path'],
             'source_sha256': model['source_sha256']}
            for model in native['models']
        ],
        'alternatives': alternatives,
        'scenarios': scenarios,
    }


def readme(result: dict) -> str:
    rows = '\n'.join(
        f"| {', '.join(item['id'] + ' ' + item['field'] + ' → ' + item['alternative'] for item in scenario['changed_labels'])} | "
        f"{scenario['extended_summary']['improved_runs']} / {scenario['extended_summary']['declined_runs']} / {scenario['extended_summary']['unchanged_runs']} | "
        f"{scenario['native_seven_summary']['improved_runs']} / {scenario['native_seven_summary']['declined_runs']} / {scenario['native_seven_summary']['unchanged_runs']} |"
        for scenario in result['scenarios']
    )
    return f"""# Provisional-reference sensitivity, without changing the key

The [dated reference review](../../docs/REFERENCE_REVIEW_V1.md) proposes changing DEV-006 serious concern from `insufficient_information` to `no`. Its [versioned proposal](../../data/pilot/reference-revisions/v0.3.json) also records two sentiment alternatives that still need human adjudication: DEV-013 `neutral` to `positive`, and DEV-030 `neutral` to `negative`. These are the only hypothetical labels used here. The frozen [v0.2 labels](../../data/pilot/proposed_labels.jsonl) and published benchmark scores remain unchanged.

The [machine-readable findings](findings.json) show each alternative alone and all four combinations of two or three, with exact affected IDs, saved and hypothetical scores, and per-run field and all-four deltas. Each run keeps its original 60-position denominator and invalid or unsent outputs. The 637-run extended cohort comes from the [source-bound public case feed](../../public-site/extended-cases-v1.json). The separate seven-model first P0 cohort comes from the [seven-native review feed](../../public-site/disputed-reviews-v1.json). A run appearing in both views is not a new observation. The same 60 fictional reviews appear across configurations and repeats; counts of improved runs are not independent samples.

| Hypothetical changes | Extended runs improved / declined / unchanged | Seven-native runs improved / declined / unchanged |
| --- | ---: | ---: |
{rows}

The v0.3 DEV-006 proposal is an AI review, not a human-adjudicated replacement. DEV-013 and DEV-030 remain unresolved; the alternatives are plausible readings documented in that review, not recommended new labels. A positive delta means closer agreement with a hypothetical key on these saved predictions, not better performance on real candidates. Because these three alternatives affect distinct reviews, each combined run delta equals the sum of its single-review deltas. No model request was made and no reference file was edited.

Run `python3 scripts/analyze_reference_sensitivity_v1.py` to regenerate the outputs, or `python3 scripts/analyze_reference_sensitivity_v1.py --check` to verify saved bytes. The builder rechecks the extended and seven-native feeds against their SHA-bound public sources and refuses changed reference-proposal fields.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Compare generated bytes without writing')
    args = parser.parse_args()
    result = analysis()
    files = {ROOT / OUTPUT / 'findings.json': json.dumps(result, indent=2, ensure_ascii=False) + '\n',
             ROOT / OUTPUT / 'README.md': readme(result)}
    if args.check:
        for path, content in files.items():
            require(path.read_text() == content, f'Generated sensitivity output differs: {path}')
    else:
        (ROOT / OUTPUT).mkdir(parents=True, exist_ok=True)
        for path, content in files.items():
            path.write_text(content)
    print('Verified seven documented-reference sensitivity scenarios')


if __name__ == '__main__':
    main()
