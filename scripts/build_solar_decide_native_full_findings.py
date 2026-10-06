#!/usr/bin/env python3
"""Build a portable Solar report that retains the final interrupted attempt."""
import argparse
import base64
from decimal import Decimal
import json
import math
from pathlib import Path
from unittest.mock import patch

from development_benchmark import ROOT, KEYS, VALUES
import build_solar_decide_native_first_pass_findings as first
import solar_decide_native_full_execution_v2 as execution
import solar_decide_final_p2_unsent_v1 as suffix_run

BASE = first.BASE
STAGES = tuple(execution.PHASES)
PROJECTION = BASE / 'all-nine.public-projection.json'
RECEIPT = BASE / 'all-nine.public-projection.receipt.json'
OUTPUT = Path('public-site/solar-decide-full-findings.json')
TERMINAL = BASE / 'terminal-reconciliation.json'
SNAPSHOT = BASE / 'terminal-child-snapshot.jsonl'
SUFFIX = suffix_run.BASE.relative_to(ROOT)
SUFFIX_TERMINAL = SUFFIX / 'terminal-reconciliation.json'
SUFFIX_SNAPSHOT = SUFFIX / 'terminal-child-snapshot.jsonl'
FINAL = 'fresh3/P2'
FINAL_IDS = [f'DEV-{i:03}' for i in (*range(1, 9), *range(10, 61))]
THRESHOLDS = (0.9, 0.99)


def source_paths():
    names = ['scripts/build_solar_decide_native_full_findings.py',
             'tests/test_build_solar_decide_native_full_findings.py',
             'scripts/build_solar_decide_native_first_pass_findings.py',
             'scripts/solar_decide_final_p2_unsent_v1.py',
             'scripts/solar_decide_native_full_execution_v2.py',
             'scripts/solar_decide_native_full_v1.py',
             'scripts/solar_decide_offline_plan.py',
             'scripts/openrouter_decision_smoke.py',
             'scripts/jev_benchmark.py',
             'scripts/development_benchmark.py',
             'results/solar-decide-native-full-v1/plan.json',
             str(BASE / 'manifest.json'), str(TERMINAL), str(SNAPSHOT),
             str(BASE / FINAL / 'development.interruption-audit.json'),
             str(BASE / FINAL / 'interrupted-child-pre-reconciliation.jsonl'),
             str(SUFFIX / 'manifest.json'), str(SUFFIX / 'terminal-closure.json'),
             str(SUFFIX_TERMINAL), str(SUFFIX_SNAPSHOT),
             'data/pilot/proposed_labels.jsonl',
             'docs/CLEF_FINDINGS_2026-10-02.md']
    for stage in STAGES:
        folder = BASE / stage
        names.extend(str(folder / name) for name in (
            'development.root-review.json', 'smoke.root-review.json',
            'smoke-inspection.json', 'development.claim.json', 'development.raw.jsonl',
            'development.parsed.jsonl', 'development.attempts.jsonl',
            'development.journal.jsonl', 'smoke.raw.jsonl',
            'smoke.parsed.jsonl', 'smoke.attempts.jsonl', 'smoke.journal.jsonl',
            'smoke.claim.json'))
    names.extend(str(SUFFIX / FINAL / name) for name in (
        'development.claim.json', 'development.root-review.json',
        'development.raw.jsonl', 'development.parsed.jsonl',
        'development.attempts.jsonl', 'development.journal.jsonl'))
    return names


def terminal_check(root):
    old = json.loads((root / TERMINAL).read_text())
    new = json.loads((root / SUFFIX_TERMINAL).read_text())
    if (old.get('event') != 'partition_reconciled' or
            old.get('partition_id') != execution.PARTITION_ID or
            old.get('known_actual_usd') != '0.19373795' or
            old.get('unknown_upper_bound_usd') != '0.10485760' or
            old.get('unused_allocation_released_usd') != '0.70140445' or
            old.get('child_sha256') != first.digest(root / SNAPSHOT) or
            new.get('event') != 'partition_reconciled' or
            new.get('partition_id') != suffix_run.PARTITION_ID or
            new.get('known_actual_usd') != '0.01968815' or
            new.get('unknown_upper_bound_usd') != '0' or
            new.get('unused_allocation_released_usd') != '0.48031185' or
            new.get('child_sha256') != first.digest(root / SUFFIX_SNAPSHOT)):
        raise ValueError('Solar original or suffix sealed child differs')
    return old, new


def original_settlements(root):
    old, _ = terminal_check(root)
    events = first.rows(root / SNAPSHOT)
    if (events[0] != {'event': 'budget', 'cap_usd': str(execution.CAP)} or
            events[-1].get('event') != 'partition_closed' or
            events[-2].get('event') != 'unknown_cost_accounted_as_upper_bound' or
            events[-3].get('event') != 'reserve' or
            events[-3].get('record_id') != FINAL + ':development:DEV-009' or
            events[-3].get('attempt_id') != events[-2].get('attempt_id') or
            events[-3].get('usd') != old['unknown_upper_bound_usd'] or
            events[-2].get('usd') != old['unknown_upper_bound_usd'] or
            len(events[1:-3]) % 2):
        raise ValueError('Solar original sealed ledger structure differs')
    settled = {}
    total = Decimal(0)
    for reserve, settle in zip(events[1:-3:2], events[2:-3:2]):
        aid = reserve.get('attempt_id')
        if (reserve.get('event') != 'reserve' or settle.get('event') != 'settle' or
                settle.get('attempt_id') != aid or aid in settled or
                Decimal(reserve['usd']) != execution.BOUND):
            raise ValueError('Solar original sealed settlement differs')
        cost = Decimal(settle['usd'])
        if not 0 <= cost <= execution.BOUND:
            raise ValueError('Solar original cost outside reserve')
        settled[aid] = (reserve, cost)
        total += cost
    if total != Decimal(old['known_actual_usd']):
        raise ValueError('Solar original known child cost differs')
    return settled


def suffix_settlements(root):
    _, terminal = terminal_check(root)
    events = first.rows(root / SUFFIX_SNAPSHOT)
    if (events[0] != {'event': 'budget', 'cap_usd': str(suffix_run.CAP)} or
            events[-1].get('event') != 'partition_closed' or
            len(events[1:-1]) != 102):
        raise ValueError('Solar suffix sealed ledger structure differs')
    settled = {}
    total = Decimal(0)
    for reserve, paid in zip(events[1:-1:2], events[2:-1:2]):
        aid = reserve.get('attempt_id')
        if (reserve.get('event') != 'reserve' or paid.get('event') != 'settle' or
                paid.get('attempt_id') != aid or aid in settled or
                Decimal(reserve['usd']) != suffix_run.BOUND):
            raise ValueError('Solar suffix sealed settlement differs')
        cost = Decimal(paid['usd'])
        if not 0 <= cost <= suffix_run.BOUND:
            raise ValueError('Solar suffix cost outside reserve')
        settled[aid] = (reserve, cost)
        total += cost
    if total != Decimal(terminal['known_actual_usd']):
        raise ValueError('Solar suffix known child cost differs')
    return settled


def verified_original_phase(stage, mode, settled):
    # The frozen runtime verifier expects only reserve/settle pairs. The sealed
    # child also has one documented unknown-cost event; supply its checked pairs.
    with patch.object(execution, 'settlement_map', return_value=settled):
        closure = execution.verify_phase_closure(stage, mode)
        if mode == 'smoke':
            execution.require_inspection(stage)
    return closure


def optional_answers(body, prediction):
    answers = body.get('answers')
    if not isinstance(answers, dict) or set(answers) != set(KEYS):
        raise ValueError('Solar native Choice answers differ')
    result = {}
    for key in KEYS:
        answer = answers[key]
        if not isinstance(answer, dict) or answer.get('type') != 'choice' or answer.get('choice') != prediction[key]:
            raise ValueError('Solar native choice differs from parsed answer')
        confidence = answer.get('confidence')
        if confidence is not None and (type(confidence) not in (float, int) or
                                       not math.isfinite(confidence) or not 0 <= confidence <= 1):
            raise ValueError('Solar native confidence differs')
        probabilities = answer.get('probabilities')
        if probabilities is not None and (not isinstance(probabilities, dict) or
                set(probabilities) != set(VALUES[key]) or
                any(type(value) not in (float, int) or not math.isfinite(value) or
                    not 0 <= value <= 1 for value in probabilities.values()) or
                abs(sum(probabilities.values()) - 1) > .001):
            raise ValueError('Solar native Choice probabilities differ')
        result[key] = {'confidence': confidence, 'probabilities': probabilities}
    return result


def decode_segment(folder, requests, settled, record_prefix):
    raw = first.rows(folder / 'development.raw.jsonl')
    parsed = first.rows(folder / 'development.parsed.jsonl')
    attempts = first.rows(folder / 'development.attempts.jsonl')
    if record_prefix == FINAL + ':development:' and len(requests) == 8:
        failed = attempts[-1]
        if (len(attempts) != 9 or failed.get('id') != 'DEV-009' or
                failed.get('status') != 'transport_error' or
                failed.get('cost_unknown') is not True):
            raise ValueError('Solar original DEV-009 failure differs')
        attempts = attempts[:-1]
    if len(raw) != len(parsed) or len(raw) != len(attempts) or len(raw) != len(requests):
        raise ValueError('Solar development segment length differs')
    records = []
    for record, output, attempt, request in zip(raw, parsed, attempts, requests):
        wire = base64.b64decode(record['response_base64'], validate=True)
        body = json.loads(wire)
        usage, cost = execution.checked_body(body)
        prediction = execution.parse_response(body, execution.solar.VERSION)
        aid = record.get('attempt_id')
        saved = settled.get(aid)
        if (record.get('id') != request['id'] or output.get('id') != request['id'] or
                attempt.get('id') != request['id'] or output.get('attempt_id') != aid or
                attempt.get('attempt_id') != aid or
                record.get('payload_sha256') != request['payload_sha256'] or
                record.get('response_sha256') != first.digest_bytes(wire) or
                record.get('http_status') != 200 or attempt.get('status') != 'ok' or
                attempt.get('cost_unknown') is not False or
                output.get('prediction') != prediction or output.get('usage') != usage or
                Decimal(output['actual_cost_usd']) != cost or
                Decimal(attempt['actual_cost_usd']) != cost or
                not saved or saved[0].get('record_id') != record_prefix + request['id'] or
                saved[1] != cost):
            raise ValueError('Solar development response or settlement differs')
        records.append({'id': request['id'], 'prediction': prediction,
            'optional': optional_answers(body, prediction),
            'input_tokens': usage['input_tokens'], 'output_tokens': usage['output_tokens'],
            'actual_cost_usd': str(cost), 'request_sha256': request['payload_sha256'],
            'response_sha256': record['response_sha256'],
            'client_request_elapsed_ns': record.get('client_request_elapsed_ns')})
    return records


def private_stage(stage, original_settled, suffix_settled):
    folder = ROOT / BASE / stage
    plan = execution.phase(stage)['requests']
    smoke = verified_original_phase(stage, 'smoke', original_settled)
    smokes = first.rows(folder / 'smoke.parsed.jsonl')
    if len(smokes) != 3 or smoke['known_valid_count'] != 3:
        raise ValueError('Solar accepted smoke differs')
    smoke_cost = sum((Decimal(row['actual_cost_usd']) for row in smokes), Decimal(0))
    if stage == FINAL:
        suffix_run.original_proof()
        suffix_closure = suffix_run.verify_phase_closure()
        if suffix_closure['request_count'] != 51 or suffix_closure['known_valid_count'] != 51:
            raise ValueError('Solar final suffix closure differs')
        early = decode_segment(folder, plan[:8], original_settled, stage + ':development:')
        later = decode_segment(ROOT / SUFFIX / stage, plan[9:], suffix_settled,
                               stage + ':development_suffix:')
        records = early + later
        if [item['id'] for item in records] != FINAL_IDS:
            raise ValueError('Solar final unknown-position gap differs')
        status = 'interrupted_with_exact_unsent_suffix'
        unknown = 1
    else:
        development = verified_original_phase(stage, 'development', original_settled)
        if development['known_valid_count'] != 60 or development['intrinsic_invalid_count'] != 0:
            raise ValueError('Solar clean stage outcome differs')
        records = decode_segment(folder, plan, original_settled, stage + ':development:')
        status = 'closed'
        unknown = 0
    return {'stage': stage, 'status': status, 'records': records,
            'known_development_cost_usd': str(sum((Decimal(row['actual_cost_usd'])
                                                  for row in records), Decimal(0))),
            'known_smoke_cost_usd': str(smoke_cost),
            'unknown_cost_attempts': unknown}


def prepare(root=ROOT):
    root = Path(root).resolve()
    if root != ROOT.resolve():
        raise ValueError('Private Solar preparation requires the execution checkout')
    terminal_check(root)
    old_settled = original_settlements(root)
    suffix_settled = suffix_settlements(root)
    stages = [private_stage(stage, old_settled, suffix_settled) for stage in STAGES]
    projection = {'schema': 'solar-decide-all-nine-public-projection-v1',
                  'stages': stages, 'reference_labels_sent': False,
                  'private_raw_checked_at_prepare': True}
    first.write_new(root / PROJECTION, projection)
    receipt = {'schema': 'solar-decide-all-nine-public-projection-receipt-v1',
               'projection_sha256': first.digest(root / PROJECTION),
               'source_sha256': {name: first.digest(root / name) for name in source_paths()},
               'private_raw_checked_at_prepare': True,
               'portable_limit': 'Absent private raw bytes are checked by archived hash, not decoded again.'}
    first.write_new(root / RECEIPT, receipt)
    first.write_new(root / OUTPUT, build(root))
    return first.digest(root / OUTPUT)


def portable_projection(root):
    projection = json.loads((root / PROJECTION).read_text())
    receipt = json.loads((root / RECEIPT).read_text())
    if (projection.get('schema') != 'solar-decide-all-nine-public-projection-v1' or
            projection.get('reference_labels_sent') is not False or
            projection.get('private_raw_checked_at_prepare') is not True or
            [item['stage'] for item in projection['stages']] != list(STAGES) or
            receipt.get('schema') != 'solar-decide-all-nine-public-projection-receipt-v1' or
            receipt.get('projection_sha256') != first.digest(root / PROJECTION) or
            receipt.get('private_raw_checked_at_prepare') is not True or
            set(receipt.get('source_sha256', {})) != set(source_paths())):
        raise ValueError('Solar all-nine projection receipt differs')
    for name, expected in receipt['source_sha256'].items():
        path = root / name
        if path.is_file():
            if first.digest(path) != expected:
                raise ValueError('Solar all-nine source changed: ' + name)
        elif not name.endswith(('development.raw.jsonl', 'development.parsed.jsonl',
                                'development.attempts.jsonl', 'development.journal.jsonl',
                                'smoke.raw.jsonl', 'smoke.parsed.jsonl',
                                'smoke.attempts.jsonl', 'smoke.journal.jsonl')):
            raise ValueError('Required Solar all-nine source missing: ' + name)
    terminal_check(root)
    original_settlements(root)
    suffix_settlements(root)
    labels = first.truth(root)
    plan = json.loads((root / 'results/solar-decide-native-full-v1/plan.json').read_text())
    by_stage = {item['id']: item for item in plan['phases']}
    for stage in projection['stages']:
        name = stage['stage']
        records = stage['records']
        expected_ids = FINAL_IDS if name == FINAL else list(labels)
        if (len(records) != len(expected_ids) or [row['id'] for row in records] != expected_ids or
                stage['status'] != ('interrupted_with_exact_unsent_suffix'
                                    if name == FINAL else 'closed') or
                stage['unknown_cost_attempts'] != (1 if name == FINAL else 0)):
            raise ValueError('Solar all-nine denominator or status differs')
        total = Decimal(0)
        requests = {item['id']: item for item in by_stage[name]['requests']}
        for row in records:
            request = requests[row['id']]
            if (set(row) != {'id', 'prediction', 'optional', 'input_tokens', 'output_tokens',
                             'actual_cost_usd', 'request_sha256', 'response_sha256',
                             'client_request_elapsed_ns'} or
                    row['id'] != request['id'] or row['request_sha256'] != request['payload_sha256'] or
                    set(row['prediction']) != set(KEYS) or set(row['optional']) != set(KEYS) or
                    any(row['prediction'][key] not in VALUES[key] for key in KEYS) or
                    type(row['input_tokens']) is not int or
                    not 0 <= row['input_tokens'] <= 4 * execution.solar.CONTEXT or
                    type(row['output_tokens']) is not int or row['output_tokens'] < 0 or
                    (row['client_request_elapsed_ns'] is not None and
                     (type(row['client_request_elapsed_ns']) is not int or
                      row['client_request_elapsed_ns'] < 0)) or
                    not isinstance(row['response_sha256'], str) or len(row['response_sha256']) != 64):
                raise ValueError('Solar all-nine projected answer differs')
            for key in KEYS:
                option = row['optional'][key]
                if set(option) != {'confidence', 'probabilities'}:
                    raise ValueError('Solar projected Choice option differs')
            # The same check is used when decoding private raw responses.
            optional_answers({'answers': {key: {'type': 'choice', 'choice': row['prediction'][key],
                **row['optional'][key]} for key in KEYS}}, row['prediction'])
            amount = Decimal(row['actual_cost_usd'])
            if amount != Decimal(row['input_tokens']) * execution.solar.PROMPT_RATE:
                raise ValueError('Solar projected token charge differs')
            total += amount
        if total != Decimal(stage['known_development_cost_usd']):
            raise ValueError('Solar all-nine score or source differs')
    old, new = terminal_check(root)
    known = sum((Decimal(item['known_development_cost_usd']) +
                 Decimal(item['known_smoke_cost_usd']) for item in projection['stages']), Decimal(0))
    if known != Decimal(old['known_actual_usd']) + Decimal(new['known_actual_usd']):
        raise ValueError('Solar all-nine known cost differs from sealed children')
    return projection


def comparison(left, right, labels, kind):
    a = {row['id']: row['prediction'] for row in left['records']}
    b = {row['id']: row['prediction'] for row in right['records']}
    shared = [ident for ident in labels if ident in a and ident in b]
    if (len(a) not in (59, 60) or len(b) not in (59, 60) or
            len(shared) != (59 if FINAL in (left['stage'], right['stage']) else 60)):
        raise ValueError('Solar all-nine paired records differ')
    changed = [ident for ident in shared if a[ident] != b[ident]]
    gained = [ident for ident in shared if not all(a[ident][key] == labels[ident][key] for key in KEYS)
              and all(b[ident][key] == labels[ident][key] for key in KEYS)]
    lost = [ident for ident in shared if all(a[ident][key] == labels[ident][key] for key in KEYS)
            and not all(b[ident][key] == labels[ident][key] for key in KEYS)]
    return {'kind': kind, 'left': left['stage'], 'right': right['stage'],
            'paired_records': len(shared),
            'excluded_unusable_ids': [ident for ident in labels if ident not in shared],
            'records_with_any_changed_answer': len(changed),
            'changed_record_ids': changed,
            'changed_fields': {key: sum(a[ident][key] != b[ident][key] for ident in shared)
                               for key in KEYS},
            'all_four_gained_ids': gained, 'all_four_lost_ids': lost,
            'all_four_net_change': len(gained) - len(lost)}


def repeat_control_check(root, left, right):
    plan = json.loads((root / 'results/solar-decide-native-full-v1/plan.json').read_text())
    by_stage = {item['id']: item for item in plan['phases']}
    a, b = (by_stage[name]['requests'] for name in (left, right))
    if len(a) != len(b) or len(a) != 60 or any(x['id'] != y['id'] or
            x['payload_sha256'] != y['payload_sha256'] or x['payload'] != y['payload']
            for x, y in zip(a, b)):
        raise ValueError('Solar repeat request controls differ')


def field_summary(records, labels, key):
    confusion = {ref: {choice: 0 for choice in VALUES[key]} for ref in VALUES[key]}
    for row in records:
        confusion[labels[row['id']][key]][row['prediction'][key]] += 1
    thresholds = {}
    for threshold in THRESHOLDS:
        kept = [row for row in records if row['optional'][key]['confidence'] is not None and
                row['optional'][key]['confidence'] >= threshold]
        correct = sum(row['prediction'][key] == labels[row['id']][key] for row in kept)
        thresholds[str(threshold)] = {'retained': len(kept), 'correct_retained': correct,
                                      'confidently_wrong': len(kept) - correct,
                                      'confidently_wrong_ids': [row['id'] for row in kept
                                        if row['prediction'][key] != labels[row['id']][key]]}
    return {'correct': sum(confusion[value][value] for value in VALUES[key]),
            'confusion_reference_by_choice': confusion,
            'confidence_available': sum(row['optional'][key]['confidence'] is not None
                                        for row in records),
            'probabilities_available': sum(row['optional'][key]['probabilities'] is not None
                                           for row in records),
            'native_confidence_thresholds': thresholds}


def build(root=ROOT):
    root = Path(root).resolve()
    projection = portable_projection(root)
    labels = first.truth(root)
    by_stage = {item['stage']: item for item in projection['stages']}
    stages = []
    for item in projection['stages']:
        records = item['records']
        stages.append({'stage': item['stage'], 'status': item['status'],
            'records': 60, 'valid_answers': len(records),
            'unknown_cost_attempts': item['unknown_cost_attempts'],
            'unusable_ids': ['DEV-009'] if item['stage'] == FINAL else [],
            'all_four_correct': sum(all(row['prediction'][key] == labels[row['id']][key]
                                        for key in KEYS) for row in records),
            'fields': {key: field_summary(records, labels, key) for key in KEYS},
            'input_tokens': sum(row['input_tokens'] for row in records),
            'output_tokens': sum(row['output_tokens'] for row in records),
            'client_elapsed_available': sum(row['client_request_elapsed_ns'] is not None
                                            for row in records),
            'client_elapsed_ns_sum_known_responses': sum(row['client_request_elapsed_ns'] or 0
                                                         for row in records),
            'known_development_cost_usd': item['known_development_cost_usd'],
            'known_smoke_cost_usd': item['known_smoke_cost_usd']})
    repeats = []
    for condition in ('P0', 'P1', 'P2'):
        for a, b in ((1, 2), (2, 3), (1, 3)):
            left, right = f'fresh{a}/{condition}', f'fresh{b}/{condition}'
            repeat_control_check(root, left, right)
            repeats.append(comparison(by_stage[left], by_stage[right], labels, 'repeat'))
    prompts = []
    for number in (1, 2, 3):
        for left_condition, right_condition in (('P0','P1'),('P1','P2'),('P0','P2')):
            left, right = f'fresh{number}/{left_condition}', f'fresh{number}/{right_condition}'
            first.prompt_control_check(root, left, right)
            prompts.append(comparison(by_stage[left], by_stage[right], labels, 'prompt'))
    old, new = terminal_check(root)
    return {'schema': 'solar-decide-native-full-findings-v1',
            'status': 'eight_closed_runs_one_interrupted_with_exact_unsent_suffix',
            'configuration': {'model': execution.solar.MODEL,
                              'returned_model': execution.solar.VERSION,
                              'provider': execution.solar.PROVIDER,
                              'interface': 'four native Choice questions'},
            'stage_order': list(STAGES), 'stages': stages,
            'repeat_comparisons': repeats, 'matched_prompt_comparisons': prompts,
            'development_records': 540, 'valid_development_answers': 539,
            'unknown_cost_development_attempts': 1,
            'interrupted_stage': FINAL, 'interrupted_record_id': 'DEV-009',
            'exact_unsent_successor_record_count': 51,
            'known_development_cost_usd': str(sum((Decimal(s['known_development_cost_usd'])
                                                   for s in stages), Decimal(0))),
            'known_smoke_cost_usd': str(sum((Decimal(s['known_smoke_cost_usd'])
                                             for s in stages), Decimal(0))),
            'child_all_requests': {
                'original_known_actual_usd': old['known_actual_usd'],
                'original_unknown_upper_bound_usd': old['unknown_upper_bound_usd'],
                'suffix_known_actual_usd': new['known_actual_usd'],
                'suffix_unknown_upper_bound_usd': new['unknown_upper_bound_usd']},
            'cost_scope': 'Known model inference charges come from provider usage. DEV-009 has no known charge, and its $0.10485760 upper bound remains reserved separately. Development and three-record smoke charges are separate; local client time is excluded.',
            'timing_scope': 'Client elapsed time is reported only for captured responses. DEV-009 timed out without a returned response or end-to-end timing; these figures are not model latency.',
            'confidence_note': 'Native confidence and probabilities describe these answers. Threshold counts cover usable answers only; they are not calibrated or externally validated.',
            'comparison_scope': 'Pairs involving final P2 share 59 usable records; DEV-009 is excluded. The final stage is not a clean 60-answer repeat.',
            'reference_status': 'Frozen provisional v0.2 development labels; the project owner confirmed human checks of all 60 reviews on 2026-10-02. Scores measure agreement with that key.',
            'verification_boundary': 'Private raw responses were decoded when the public projection was prepared. A copy without them verifies archived hashes, scores, and prices, but cannot decode those responses again.',
            'source_bindings': {'projection_sha256': first.digest(root / PROJECTION),
                                'projection_receipt_sha256': first.digest(root / RECEIPT),
                                'terminal_sha256': first.digest(root / TERMINAL),
                                'child_snapshot_sha256': first.digest(root / SNAPSHOT),
                                'suffix_terminal_sha256': first.digest(root / SUFFIX_TERMINAL),
                                'suffix_child_snapshot_sha256': first.digest(root / SUFFIX_SNAPSHOT),
                                'reference_sha256': first.digest(root / 'data/pilot/proposed_labels.jsonl')}}


def check(root=ROOT):
    root = Path(root).resolve()
    if json.loads((root / OUTPUT).read_text()) != build(root):
        raise ValueError('Published Solar all-nine findings differ')
    return first.digest(root / OUTPUT)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'check'))
    args = parser.parse_args()
    print(prepare() if args.action == 'prepare' else check())


if __name__ == '__main__':
    main()
