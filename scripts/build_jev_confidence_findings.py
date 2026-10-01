#!/usr/bin/env python3
"""Report saved TypeSafe Jev Choice confidence against offline development references."""

import argparse
import json
from pathlib import Path

from development_benchmark import KEYS, ROOT, read_rows
from jev_benchmark import PRICE_MODEL, parse_response
import build_jev_native_prompt_report_v1 as verified


OUTPUT = ROOT / 'public-site/jev-confidence-findings.json'
THRESHOLDS = (0.5, 0.7, 0.9)
CONDITIONS = ('P0', 'P1', 'P2')


def condition_summary(rows, references):
    """Count decisions on valid outputs only; leave invalid records visible."""
    expected_ids = [f'DEV-{index:03}' for index in range(1, 61)]
    if [row.get('id') for row in rows] != expected_ids:
        raise ValueError('Expected 60 ordered development records')
    if set(references) != set(expected_ids):
        raise ValueError('Reference IDs differ from development inputs')
    good = []
    invalid = []
    for row in rows:
        if row.get('status') == 'invalid_output':
            if row.get('prediction') is not None:
                raise ValueError('Invalid output has a prediction')
            invalid.append(row['id'])
            continue
        if row.get('status') != 'ok':
            raise ValueError('Unexpected development status: ' + str(row.get('status')))
        body = row.get('raw_response')
        if parse_response(body, PRICE_MODEL) != row.get('prediction'):
            raise ValueError('Prediction differs from strict raw Choice parse: ' + row['id'])
        good.append(row)

    fields = {}
    for field in KEYS:
        decisions = []
        for row in good:
            answer = row['raw_response']['answers'][field]
            probabilities = answer['probabilities']
            selected = probabilities[answer['choice']]
            decisions.append({
                'id': row['id'],
                'confidence': answer['confidence'],
                'selectedChoiceProbability': selected,
                'correct': row['prediction'][field] == references[row['id']][field],
            })
        wrong = [item for item in decisions if not item['correct']]
        thresholds = {}
        for threshold in THRESHOLDS:
            retained = [item for item in decisions if item['confidence'] >= threshold]
            withheld = [item for item in decisions if item['confidence'] < threshold]
            thresholds[str(threshold)] = {
                'retained': len(retained),
                'retainedCorrect': sum(item['correct'] for item in retained),
                'retainedWrong': sum(not item['correct'] for item in retained),
                'withheldValid': len(withheld),
                'withheldCorrect': sum(item['correct'] for item in withheld),
                'withheldWrong': sum(not item['correct'] for item in withheld),
                'unavailableInvalid': len(invalid),
                'fixedDenominator': 60,
                'confidentlyWrongIds': [item['id'] for item in retained if not item['correct']],
            }
        fields[field] = {
            'valid': len(decisions),
            'correct': len(decisions) - len(wrong),
            'wrong': len(wrong),
            'thresholds': thresholds,
            'wrongCases': [{key: item[key] for key in ('id', 'confidence', 'selectedChoiceProbability')}
                           for item in wrong],
        }
    return {'records': 60, 'valid': len(good), 'invalid': len(invalid),
            'invalidIds': invalid, 'fields': fields}


def build(directory=verified.DEFAULT_DIRECTORY):
    # The existing reporter checks original P0 attempt history, frozen P1/P2
    # request bytes, receipts, journals, raw parsing, usage and reference IDs.
    audit = verified.build(directory)
    refs_path = ROOT / 'data/pilot/proposed_labels.jsonl'
    references = {row['id']: row['proposed_labels'] for row in read_rows(refs_path)}
    if len(references) != 60:
        raise ValueError('Expected 60 unique provisional references')
    rows = {
        'P0': verified.lines(ROOT / 'results/openjev/typesafe-development-v2-reconciled.jsonl'),
        'P1': verified.lines(Path(directory) / 'P1-development.jsonl'),
        'P2': verified.lines(Path(directory) / 'P2-development.jsonl'),
    }
    conditions = {name: condition_summary(rows[name], references) for name in CONDITIONS}
    for name in CONDITIONS:
        if conditions[name]['valid'] != audit['summary'][name]['valid']:
            raise ValueError('Confidence validity differs from verified Jev report')
    sources = audit['source_bindings'] + [verified.binding(ROOT / 'scripts/build_jev_confidence_findings.py')]
    return {
        'kind': 'jev-native-confidence-findings-v1',
        'model': PRICE_MODEL,
        'protocol': 'historical TypeSafe Jev native Choice P0/P1/P2 instruction comparison',
        'manifestSha256': audit['manifest_sha256'],
        'referenceStatus': 'AI-reviewed provisional development labels; read offline only',
        'confidenceMeaning': 'Provider-reported Choice confidence; distinct from selected-choice probability. Neither is calibrated correctness probability.',
        'thresholdMeaning': 'Counterfactual withholding of valid field decisions below threshold; no abstention was executed. Invalid output is unavailable, not a wrong judgment.',
        'comparisonLimit': 'P0 is historical and P1/P2 are one pass each. Thresholds compare descriptions within this native interface, not causal prompt effects or other model interfaces.',
        'sourceBindings': sources,
        'conditions': conditions,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    args = parser.parse_args()
    rendered = json.dumps(build(), indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if args.output.read_text() != rendered:
            raise ValueError('Saved Jev confidence feed differs from source-bound evidence')
        print('Jev confidence feed matches verified sources')
    else:
        args.output.write_text(rendered)
        print(args.output)


if __name__ == '__main__':
    main()
