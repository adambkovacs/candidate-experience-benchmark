#!/usr/bin/env python3
"""Audit selected closed OpenRouter native Choice runs and build a safe report.

Preparation reads private responses. Check needs only the projection, its receipt,
tracked reference labels, and frozen plans; present private files are rechecked.
Stages are selected explicitly so a concurrently running stage cannot enter a report.
"""
import argparse
import base64
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path

from development_benchmark import ROOT, KEYS, VALUES, read_rows
from jev_benchmark import parse_response
import clef_openrouter_native_v1 as route
import clef_openrouter_full_v1 as full
import clef_openrouter_smoke_v1 as smoke
import openrouter_decision_smoke as native

BASE = route.BASE / 'findings-v1'
PROJECTION = BASE / 'public-projection.json'
RECEIPT = BASE / 'public-projection.receipt.json'
OUTPUT = BASE / 'findings.json'
LABELS = Path('data/pilot/proposed_labels.jsonl')
STAGES = tuple(f'{p}/{c}' for p in route.PASSES for c in route.CONDITIONS)
DEVELOPMENT_FILES = ('claim.json', 'journal.jsonl', 'raw.jsonl', 'attempts.jsonl', 'parsed.jsonl')
SOURCE_FILES = ('scripts/build_clef_openrouter_findings.py',
                'tests/test_build_clef_openrouter_findings.py',
                'docs/CLEF_OPENROUTER_FINDINGS.md',
                'scripts/clef_openrouter_full_v1.py',
                'scripts/clef_openrouter_native_v1.py', 'scripts/clef_openrouter_smoke_v1.py',
                'scripts/jev_benchmark.py',
                'scripts/development_benchmark.py', 'scripts/openrouter_decision_smoke.py',
                str(route.PLAN), str(full.PLAN), str(full.REVIEW), str(LABELS))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()


def read_json(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + '\n')


def stage_paths(key, stage):
    if key not in ('clef', 'clef-flash', 'luna-decisions') or stage not in STAGES:
        raise ValueError('Undeclared model or stage')
    folder = full.BASE / key / stage
    return {name: folder / ('development.' + name) for name in DEVELOPMENT_FILES}


def smoke_inspection_path(root, key, stage):
    newer = full.stage_dir(root, key, stage)
    folder = newer if (newer / 'smoke.claim.json').exists() else smoke.stage_dir(root, key, stage)
    return folder.relative_to(root) / 'smoke.root-inspection.json'


def labels(root):
    refs = read_rows(root / LABELS)
    if len(refs) != 60 or [r['id'] for r in refs] != list(route.IDS) or any(
            not isinstance(r.get('proposed_labels'), dict) or
            set(r['proposed_labels']) != set(KEYS) or
            any(r['proposed_labels'][k] not in VALUES[k] for k in KEYS) for r in refs):
        raise ValueError('Frozen 60-label reference differs')
    return {r['id']: r['proposed_labels'] for r in refs}


def optional_answers(body, prediction):
    result = {}
    for key in KEYS:
        answer = body['answers'][key]
        confidence = answer.get('confidence')
        probs = answer.get('probabilities')
        if (type(confidence) not in (int, float) or not math.isfinite(confidence) or
                not 0 <= confidence <= 1 or not isinstance(probs, dict) or
                set(probs) != set(VALUES[key])):
            raise ValueError('Native confidence or probability differs')
        result[key] = {'confidence': confidence,
                       'chosen_probability': probs[prediction[key]]}
    return result


def private_stage(root, plan, full_sha, route_sha, key, stage):
    paths = stage_paths(key, stage)
    claim = read_json(root / paths['claim.json'])
    journal = rows(root / paths['journal.jsonl'])
    raw = rows(root / paths['raw.jsonl'])
    attempts = rows(root / paths['attempts.jsonl'])
    parsed = rows(root / paths['parsed.jsonl'])
    expected = {'kind': 'clef-openrouter-native-full-phase-claim-v1',
                'full_plan_sha256': full_sha, 'route_plan_sha256': route_sha,
                'root_review_sha256': sha((root / full.REVIEW).read_bytes()),
                'phase': 'development', 'model_key': key, 'stage': stage,
                'reference_labels_sent': False}
    if any(claim.get(k) != v for k, v in expected.items()):
        raise ValueError('Development claim differs from frozen plan')
    if claim.get('smoke_inspection_sha256') != full.verify_smoke_inspection(
            root, key, stage, route_sha, full_sha):
        raise ValueError('Development claim does not bind inspected smoke')
    # A completed journal has one opening event, two events per request and one close.
    ids = list(route.IDS)
    if (len(journal) != 122 or journal[0].get('event') != 'stage_started' or
            journal[0].get('full_plan_sha256') != full_sha or
            journal[-1].get('event') != 'stage_completed' or journal[-1].get('count') != 60 or
            len(raw) != 60 or len(attempts) != 60 or len(parsed) != 60):
        raise ValueError('Development phase is not a closed 60-record run')
    for i, rid in enumerate(ids):
        intent, started = journal[1 + 2*i:3 + 2*i]
        if (intent.get('event') != 'request_intent' or intent.get('id') != rid or
                started.get('event') != 'request_started' or started.get('id') != rid or
                started.get('attempt_id') is None):
            raise ValueError('Development journal sequence differs')
    requests = plan['models'][key]['requests'][stage.split('/')[1]]
    records = []
    for i, (rid, request, original, attempt, saved, started) in enumerate(zip(
            ids, requests, raw, attempts, parsed, journal[2:-1:2])):
        wire = base64.b64decode(original['response_base64'], validate=True)
        body = json.loads(wire)
        prediction = full.validate_returned(key, body)
        cost = native.response_cost(body)
        aid = started['attempt_id']
        if (cost is None or cost < 0 or cost > route.bound(key, 1) or
                original.get('id') != rid or request['id'] != rid or
                attempt.get('id') != rid or saved.get('id') != rid or
                any(x.get('attempt_id') != aid for x in (original, attempt, saved)) or
                original.get('payload_sha256') != request['payload_sha256'] or
                journal[1 + 2*i].get('payload_sha256') != request['payload_sha256'] or
                original.get('response_sha256') != sha(wire) or original.get('http_status') != 200 or
                attempt.get('status') != 'ok' or attempt.get('cost_unknown') is not False or
                saved.get('prediction') != prediction or
                saved.get('input_tokens') != body['usage']['input_tokens'] or
                saved.get('output_tokens') != body['usage']['output_tokens'] or
                Decimal(saved['actual_cost_usd']) != cost or
                Decimal(attempt['actual_cost_usd']) != cost):
            raise ValueError('Saved response, strict parse, or cost differs')
        elapsed = original.get('client_request_elapsed_ns')
        if type(elapsed) is not int or elapsed < 0:
            raise ValueError('Missing client request timing')
        records.append({'id': rid, 'prediction': prediction,
                        'confidence': optional_answers(body, prediction),
                        'input_tokens': saved['input_tokens'],
                        'output_tokens': saved['output_tokens'],
                        'actual_cost_usd': str(cost),
                        'client_request_elapsed_ns': elapsed,
                        'request_sha256': request['payload_sha256'],
                        'response_sha256': original['response_sha256']})
    return {'model_key': key, 'stage': stage, 'status': 'closed_60', 'records': records}


def summarize_stage(stage, truth):
    records = stage['records']
    if len(records) != 60 or [r['id'] for r in records] != list(route.IDS):
        raise ValueError('Public projection does not contain 60 ordered answers')
    fields = {}
    for key in KEYS:
        confusion = {reference: {predicted: 0 for predicted in VALUES[key]}
                     for reference in VALUES[key]}
        high_wrong = []
        high_probability_wrong = []
        confidences = []
        chosen_probabilities = []
        incorrect_confidences = []
        for record in records:
            rid = record['id']
            choice = record['prediction'][key]
            conf = record['confidence'][key]['confidence']
            probability = record['confidence'][key]['chosen_probability']
            if (choice not in VALUES[key] or type(conf) not in (int, float) or
                    not math.isfinite(conf) or not 0 <= conf <= 1 or
                    type(probability) not in (int, float) or
                    not math.isfinite(probability) or not 0 <= probability <= 1):
                raise ValueError('Public projection has invalid label or confidence')
            reference = truth[rid][key]
            confusion[reference][choice] += 1
            confidences.append(conf)
            chosen_probabilities.append(probability)
            if choice != reference:
                incorrect_confidences.append(conf)
            if choice != reference and conf >= .9:
                high_wrong.append(rid)
            if choice != reference and probability >= .9:
                high_probability_wrong.append(rid)
        fields[key] = {'correct': sum(confusion[v][v] for v in VALUES[key]),
                       'denominator': 60, 'confusion_reference_by_predicted': confusion,
                       'reported_confidence_mean': sum(confidences) / 60,
                       'chosen_probability_mean': sum(chosen_probabilities) / 60,
                       'reported_confidence_mean_when_wrong': (
                           sum(incorrect_confidences) / len(incorrect_confidences)
                           if incorrect_confidences else None),
                       'wrong_with_reported_confidence_at_least_0_9_ids': high_wrong,
                       'wrong_with_chosen_probability_at_least_0_9_ids': high_probability_wrong}
    all_four = [r['id'] for r in records if r['prediction'] == truth[r['id']]]
    return {'model_key': stage['model_key'], 'stage': stage['stage'], 'status': stage['status'],
            'attempted': 60, 'valid_answers': 60, 'invalid_answers': 0,
            'provider_failures': 0, 'unknown_cost_attempts': 0,
            'all_four_correct': len(all_four), 'denominator': 60,
            'all_four_correct_ids': all_four, 'fields': fields,
            'observed_input_tokens': sum(r['input_tokens'] for r in records),
            'observed_output_tokens': sum(r['output_tokens'] for r in records),
            'observed_known_cost_usd': str(sum((Decimal(r['actual_cost_usd']) for r in records), Decimal(0))),
            'client_request_elapsed_ns_sum': sum(r['client_request_elapsed_ns'] for r in records),
            'client_request_elapsed_ns_count': 60,
            'confidence_note': 'Provider-reported confidence and chosen-label probability are separate values; 60 development records do not establish calibration.'}


def comparisons(stages, truth):
    by = {(s['model_key'], s['stage']): s for s in stages}
    result = []
    for key in dict.fromkeys(s['model_key'] for s in stages):
        for pass_name in route.PASSES:
            for a, b in (('P0', 'P1'), ('P1', 'P2'), ('P0', 'P2')):
                x, y = by.get((key, f'{pass_name}/{a}')), by.get((key, f'{pass_name}/{b}'))
                if x and y:
                    result.append(compare(x, y, truth, 'paired_prompt'))
        for cond in route.CONDITIONS:
            for a, b in (('fresh1', 'fresh2'), ('fresh2', 'fresh3'), ('fresh1', 'fresh3')):
                x, y = by.get((key, f'{a}/{cond}')), by.get((key, f'{b}/{cond}'))
                if x and y:
                    result.append(compare(x, y, truth, 'repeat'))
    return result


def compare(a, b, truth, kind):
    ra = {r['id']: r for r in a['records']}
    rb = {r['id']: r for r in b['records']}
    ids = [rid for rid in route.IDS if rid in ra and rid in rb]
    changed = [rid for rid in ids if ra[rid]['prediction'] != rb[rid]['prediction']]
    gained = [rid for rid in ids if ra[rid]['prediction'] != truth[rid] and rb[rid]['prediction'] == truth[rid]]
    lost = [rid for rid in ids if ra[rid]['prediction'] == truth[rid] and rb[rid]['prediction'] != truth[rid]]
    field_changes = {k: [rid for rid in ids if ra[rid]['prediction'][k] != rb[rid]['prediction'][k]] for k in KEYS}
    return {'kind': kind, 'model_key': a['model_key'], 'from_stage': a['stage'],
            'to_stage': b['stage'], 'shared_valid_denominator': len(ids),
            'changed_prediction_ids': changed, 'field_changed_ids': field_changes,
            'all_four_gained_ids': gained, 'all_four_lost_ids': lost}


def report(projection, truth, receipt_sha):
    stages = projection['stages']
    return {'schema': 'clef-openrouter-closed-stage-findings-v1',
            'route': 'OpenRouter native Decisions',
            'distinct_from': 'Cloudflare direct native route',
            'reference_status': 'Frozen provisional v0.2 labels, owner-confirmed human review on 2026-10-02; no versioned correction.',
            'included_stages': [{'model_key': s['model_key'], 'stage': s['stage']} for s in stages],
            'stages': [summarize_stage(s, truth) for s in stages],
            'comparisons': comparisons(stages, truth),
            'evidence': {'projection_receipt_sha256': receipt_sha,
                         'private_raw_validation': 'Performed during preparation; a clean checkout can verify archived hashes and the public projection but cannot independently decode absent private responses.',
                         'timing': 'Sum of measured client request elapsed time, not provider processing time or whole-stage wall time.',
                         'cost': 'Observed response cost for included development attempts only; smoke and child allocation are separate.'}}


def source_hashes(root, selected):
    names = list(SOURCE_FILES)
    for key, stage in selected:
        names.extend(str(path) for path in stage_paths(key, stage).values())
        names.append(str(smoke_inspection_path(root, key, stage)))
    return {name: sha((root / name).read_bytes()) for name in names}


def prepare(root, selected):
    root = Path(root)
    if not selected or len(selected) != len(set(selected)):
        raise ValueError('Select distinct closed stages explicitly')
    selected = sorted(selected, key=lambda pair: (pair[0], STAGES.index(pair[1])))
    route_plan, route_sha = route.verify(root)
    _, full_sha = full.verify(root)
    truth = labels(root)
    stages = [private_stage(root, route_plan, full_sha, route_sha, key, stage)
              for key, stage in selected]
    projection = {'schema': 'clef-openrouter-public-projection-v1', 'stages': stages}
    receipt = {'kind': 'clef-openrouter-public-projection-receipt-v1',
               'projection_sha256': sha(canonical(projection)),
               'source_sha256': source_hashes(root, selected),
               'included_stages': [{'model_key': k, 'stage': s} for k, s in selected],
               'private_raw_checked_at_prepare': True}
    result = report(projection, truth, sha(canonical(receipt)))
    write_json(root / PROJECTION, projection)
    write_json(root / RECEIPT, receipt)
    write_json(root / OUTPUT, result)
    return result


def check(root):
    root = Path(root)
    projection, receipt = read_json(root / PROJECTION), read_json(root / RECEIPT)
    if (projection.get('schema') != 'clef-openrouter-public-projection-v1' or
            receipt.get('kind') != 'clef-openrouter-public-projection-receipt-v1' or
            receipt.get('projection_sha256') != sha(canonical(projection)) or
            receipt.get('private_raw_checked_at_prepare') is not True):
        raise ValueError('Projection receipt differs')
    selected = [(s['model_key'], s['stage']) for s in receipt['included_stages']]
    if (len(selected) != len(set(selected)) or
            [{'model_key': s['model_key'], 'stage': s['stage']} for s in projection['stages']] != receipt['included_stages']):
        raise ValueError('Receipt stage selection differs')
    expected = set(SOURCE_FILES)
    for key, stage in selected:
        expected.update(str(p) for p in stage_paths(key, stage).values())
        # The selected inspection location is recorded in the receipt because
        # historical first-pass smokes live outside full-v1.
        candidates = [str((full.BASE / key / stage / 'smoke.root-inspection.json')),
                      str((route.BASE / key / stage / 'smoke.root-inspection.json'))]
        included = [name for name in candidates if name in receipt['source_sha256']]
        if len(included) != 1:
            raise ValueError('Exactly one bound smoke inspection required')
        expected.add(included[0])
    if set(receipt['source_sha256']) != expected:
        raise ValueError('Receipt source list differs')
    for name, value in receipt['source_sha256'].items():
        path = root / name
        if path.exists() and sha(path.read_bytes()) != value:
            raise ValueError('Bound source changed: ' + name)
        if (name in SOURCE_FILES or name.endswith('smoke.root-inspection.json')) and not path.exists():
            raise ValueError('Required public source absent: ' + name)
    truth = labels(root)
    result = report(projection, truth, sha(canonical(receipt)))
    if read_json(root / OUTPUT) != result:
        raise ValueError('Published findings differ from checked projection')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'check'))
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--stage', action='append', default=[], metavar='MODEL:FRESH/CONDITION')
    args = parser.parse_args()
    if args.action == 'prepare':
        selected = []
        for value in args.stage:
            key, sep, stage = value.partition(':')
            if not sep:
                parser.error('--stage requires MODEL:FRESH/CONDITION')
            selected.append((key, stage))
        result = prepare(args.root, selected)
    else:
        result = check(args.root)
    print(json.dumps({'included_stages': len(result['stages']),
                      'findings_sha256': sha(canonical(result))}, sort_keys=True))


if __name__ == '__main__':
    main()
