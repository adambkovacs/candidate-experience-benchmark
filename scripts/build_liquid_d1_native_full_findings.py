#!/usr/bin/env python3
"""Publish closed Liquid native Choice phases without request text."""
import argparse
import base64
from decimal import Decimal
import json
import math
from pathlib import Path

from development_benchmark import ROOT, KEYS, VALUES, read_rows
import liquid_d1_full_execution_v1 as full
import openrouter_decision_smoke as native

STAGE = 'fresh1/P0'
FOLDER = full.BASE / STAGE
OUTPUT = ROOT / 'results/liquid-d1-native-v1/full-v1/fresh1/P0/development.public.json'
THRESHOLDS = (0.9, 0.99)


def field_audit(rows, field):
    """Threshold counts describe this sample; confidence is not calibrated."""
    confusion = {truth: {choice: 0 for choice in VALUES[field]}
                 for truth in VALUES[field]}
    for row in rows:
        confusion[row['reference'][field]][row['answers'][field]['choice']] += 1
    thresholds = {}
    for threshold in THRESHOLDS:
        retained = [row for row in rows if row['answers'][field]['confidence'] >= threshold]
        correct = sum(row['answers'][field]['choice'] == row['reference'][field]
                      for row in retained)
        thresholds[str(threshold)] = {
            'threshold': threshold, 'retained': len(retained),
            'abstained': len(rows) - len(retained), 'coverage': len(retained) / len(rows),
            'correct_retained': correct, 'confidently_wrong': len(retained) - correct,
            'conditional_agreement': correct / len(retained) if retained else None}
    return {'confusion_reference_by_choice': confusion,
            'correct': sum(confusion[value][value] for value in VALUES[field]),
            'denominator': len(rows), 'provider_confidence_thresholds': thresholds}


def build(stage=STAGE):
    if stage not in full.PHASES:
        raise ValueError('Unknown Liquid report stage')
    folder = full.BASE / stage
    fresh, condition = stage.split('/')
    snapshot = folder / 'development.closure-ledger-snapshot.jsonl'
    # The shared child can hold an in-flight reservation for a later phase.
    # Verify this phase against its immutable terminal prefix, not the live child.
    active_child = full.CHILD
    try:
        full.CHILD = snapshot
        closure = full.verify_phase_closure(stage, 'development')
    finally:
        full.CHILD = active_child
    receipt = json.loads((folder / 'development.closure-audit.json').read_text())
    saved_score = json.loads((folder / 'development.score.json').read_text())
    if (receipt.get('runtime_closure') != closure or
            receipt.get('child_ledger_snapshot_sha256') != full.sha(snapshot) or
            receipt.get('score_file_sha256') != full.sha(folder / 'development.score.json') or
            saved_score.get('parsed_sha256') != closure['parsed_sha256'] or
            saved_score.get('references_sha256') != full.sha(ROOT / 'data/pilot/proposed_labels.jsonl') or
            saved_score.get('pairs_sha256') != full.sha(ROOT / 'data/pilot/pairs.json')):
        raise ValueError('Liquid closure or offline score binding differs')
    refs = read_rows(ROOT / 'data/pilot/proposed_labels.jsonl')
    truth = {row['id']: row['proposed_labels'] for row in refs}
    raw = full.jsonl(folder / 'development.raw.jsonl')
    parsed = full.jsonl(folder / 'development.parsed.jsonl')
    attempts = full.jsonl(folder / 'development.attempts.jsonl')
    if len(raw) != len(parsed) or len(raw) != len(attempts) or len(raw) != 60:
        raise ValueError('Liquid development records missing')
    rows = []
    for record, prediction, attempt in zip(raw, parsed, attempts):
        wire = base64.b64decode(record['response_base64'], validate=True)
        body = json.loads(wire)
        ident = record['id']
        answers = body['answers']
        if (record['response_sha256'] != native.sha(wire) or
                prediction['id'] != ident or attempt['id'] != ident or
                prediction['prediction'] != {key: answers[key]['choice'] for key in KEYS} or
                attempt.get('status') != 'ok' or ident not in truth):
            raise ValueError('Liquid raw/projection identity differs')
        rows.append({'id': ident, 'prediction': prediction['prediction'],
                     'answers': {key: {'choice': answers[key]['choice'],
                                       'probabilities': answers[key]['probabilities'],
                                       'confidence': answers[key]['confidence']}
                                 for key in KEYS},
                     'usage': body['usage'], 'actual_cost_usd': prediction['actual_cost_usd'],
                     'request_sha256': record['payload_sha256'],
                     'response_sha256': record['response_sha256']})
    audited = [{**row, 'reference': truth[row['id']]} for row in rows]
    fields = {key: field_audit(audited, key) for key in KEYS}
    if (sum(all(row['prediction'][key] == truth[row['id']][key] for key in KEYS)
            for row in rows) != saved_score['all_four_correct'] or
            {key: fields[key]['correct'] for key in KEYS} != saved_score['fields_correct']):
        raise ValueError('Liquid aggregate score differs')
    return {'kind': f'liquid-d1-native-full-{condition.lower()}-public-v1', 'status': 'closed_60_valid',
            'configuration': {'model': full.liquid.MODEL,
                              'returned_model': full.liquid.VERSION,
                              'provider': full.liquid.PROVIDER, 'pass': fresh,
                              'condition': condition, 'interface': 'native four Choice questions'},
            'record_count': 60, 'valid_outputs': 60, 'intrinsic_invalid_count': 0,
            'known_actual_usd': receipt['known_actual_usd'],
            'unknown_upper_bound_usd': receipt['unknown_upper_bound_usd'],
            'all_four_correct': saved_score['all_four_correct'],
            'fields': fields, 'records': rows,
            'reference_status': 'Frozen provisional v0.2 development labels. The project owner confirmed human checks of all 60 on 2026-10-02; there was no independent adjudication.',
            'reference_context_source': {'path': 'docs/CLEF_FINDINGS_2026-10-02.md',
                                         'sha256': full.sha(ROOT / 'docs/CLEF_FINDINGS_2026-10-02.md')},
            'confidence_note': 'Provider-reported confidence differs from chosen-label probability. Thresholds 0.9 and 0.99 describe this same sample; no calibration or threshold tuning claim.',
            'portable_verification_limit': 'The public checker verifies source hashes, Choice probabilities, usage, and offline scoring against the frozen reference. It cannot independently reparse private raw response bytes when those files are absent.',
            'source_bindings': {'manifest_sha256': closure['manifest_sha256'],
                                'raw_sha256': closure['raw_sha256'],
                                'parsed_sha256': closure['parsed_sha256'],
                                'closure_receipt_sha256': full.sha(folder / 'development.closure-audit.json'),
                                'score_sha256': full.sha(folder / 'development.score.json'),
                                'reference_sha256': saved_score['references_sha256'],
                                'pairs_sha256': saved_score['pairs_sha256']}}


def portable_check(value=None, stage=STAGE, root=ROOT):
    """Verify public evidence and scoring without opening private raw responses."""
    if stage not in full.PHASES:
        raise ValueError('Unknown Liquid report stage')
    root = Path(root).resolve()
    folder = root / 'results/liquid-d1-native-v1/full-v1' / stage
    output = folder / 'development.public.json'
    value = value if value is not None else json.loads(output.read_text())
    bindings = value['source_bindings']
    receipt_path = folder / 'development.closure-audit.json'
    score_path = folder / 'development.score.json'
    manifest_path = root / 'results/liquid-d1-native-v1/full-v1/manifest.json'
    paths = {'manifest_sha256': manifest_path, 'closure_receipt_sha256': receipt_path,
             'score_sha256': score_path,
             'reference_sha256': root / 'data/pilot/proposed_labels.jsonl',
             'pairs_sha256': root / 'data/pilot/pairs.json'}
    if any(bindings.get(key) != full.sha(path) for key, path in paths.items()):
        raise ValueError('Liquid portable source binding differs')
    receipt = json.loads(receipt_path.read_text())
    saved_score = json.loads(score_path.read_text())
    if (receipt.get('source_sha256') !=
            {name: full.sha(root / name) for name in full.SOURCES}):
        raise ValueError('Liquid archived controller source differs')
    if (receipt.get('runtime_closure', {}).get('raw_sha256') != bindings.get('raw_sha256') or
            receipt['runtime_closure'].get('parsed_sha256') != bindings.get('parsed_sha256') or
            receipt.get('child_ledger_snapshot_sha256') != full.sha(folder / 'development.closure-ledger-snapshot.jsonl') or
            saved_score.get('parsed_sha256') != bindings.get('parsed_sha256') or
            saved_score.get('scoring_source_sha256') != full.sha(root / 'scripts/development_benchmark.py') or
            receipt.get('score_file_sha256') != bindings.get('score_sha256')):
        raise ValueError('Liquid archived receipt differs')
    context = value.get('reference_context_source') or {}
    if (context.get('path') != 'docs/CLEF_FINDINGS_2026-10-02.md' or
            context.get('sha256') != full.sha(root / context['path'])):
        raise ValueError('Liquid reference context differs')
    refs = read_rows(paths['reference_sha256'])
    truth = {row['id']: row['proposed_labels'] for row in refs}
    rows = value['records']
    fresh, condition = stage.split('/')
    if (value.get('kind') != f'liquid-d1-native-full-{condition.lower()}-public-v1' or
            value.get('configuration') != {'model': full.liquid.MODEL,
                                           'returned_model': full.liquid.VERSION,
                                           'provider': full.liquid.PROVIDER, 'pass': fresh,
                                           'condition': condition,
                                           'interface': 'native four Choice questions'} or
            len(rows) != 60 or [row['id'] for row in rows] != [row['id'] for row in refs] or
            value.get('record_count') != 60 or value.get('valid_outputs') != 60 or
            value.get('status') != 'closed_60_valid'):
        raise ValueError('Liquid public record set differs')
    total = Decimal(0)
    for row in rows:
        if (set(row) != {'id', 'prediction', 'answers', 'usage', 'actual_cost_usd',
                         'request_sha256', 'response_sha256'} or
                set(row['answers']) != set(KEYS) or
                row['prediction'] != {key: row['answers'][key]['choice'] for key in KEYS} or
                not all(isinstance(row[key], str) and len(row[key]) == 64 and
                        all(c in '0123456789abcdef' for c in row[key])
                        for key in ('request_sha256', 'response_sha256'))):
            raise ValueError('Liquid public prediction or hash differs')
        for key in KEYS:
            answer = row['answers'][key]
            probs = answer['probabilities']
            if (set(answer) != {'choice', 'probabilities', 'confidence'} or
                    set(probs) != set(VALUES[key]) or answer['choice'] not in probs or
                    any(type(p) not in (float, int) or not math.isfinite(p) or p < 0 or p > 1
                        for p in probs.values()) or
                    abs(sum(probs.values()) - 1) > 0.00001 or
                    type(answer['confidence']) not in (float, int) or
                    not math.isfinite(answer['confidence']) or
                    not 0 <= answer['confidence'] <= 1):
                raise ValueError('Liquid public Choice distribution differs')
        usage = row['usage']
        cost = Decimal(row['actual_cost_usd'])
        if (type(usage.get('input_tokens')) is not int or
                not 0 <= usage['input_tokens'] <= full.liquid.QUESTION_COUNT * full.liquid.CONTEXT or
                usage.get('output_tokens') != 0 or
                cost != Decimal(usage['input_tokens']) * full.liquid.RATE):
            raise ValueError('Liquid public usage or price differs')
        total += cost
    if (str(total) != value.get('known_actual_usd') or
            value.get('unknown_upper_bound_usd') != '0' or
            str(total) != receipt['known_actual_usd']):
        raise ValueError('Liquid public cost differs')
    audited = [{**row, 'reference': truth[row['id']]} for row in rows]
    fields = {key: field_audit(audited, key) for key in KEYS}
    all_four = sum(all(row['prediction'][key] == truth[row['id']][key] for key in KEYS)
                   for row in rows)
    if (fields != value['fields'] or all_four != value['all_four_correct'] or
            all_four != saved_score['all_four_correct'] or
            {key: fields[key]['correct'] for key in KEYS} != saved_score['fields_correct']):
        raise ValueError('Liquid public offline score differs')
    return full.sha(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'check'))
    parser.add_argument('--stage', choices=full.PHASES, default=STAGE)
    args = parser.parse_args()
    folder = full.BASE / args.stage
    output = folder / 'development.public.json'
    if args.action == 'prepare':
        expected = build(args.stage)
        with output.open('x') as out:
            out.write(json.dumps(expected, indent=2, ensure_ascii=False) + '\n')
    elif (folder / 'development.raw.jsonl').exists() and json.loads(output.read_text()) != build(args.stage):
        raise ValueError('Liquid public projection differs from closed raw evidence')
    print(portable_check(stage=args.stage))


if __name__ == '__main__':
    main()
