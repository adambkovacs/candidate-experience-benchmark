#!/usr/bin/env python3
"""Build the Gemma26 interrupted fresh3/P2 composite from saved evidence only."""
import argparse
import base64
from decimal import Decimal
import hashlib
import json
import math
import os
from pathlib import Path

from development_benchmark import valid
import build_gemma26_continuation_findings as first_report
import build_gemma26_second_continuation_findings as second_report
import gemma26_v2_postabort_054_060 as successor

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/gemma26-on-fresh-matched3-v2')
SCHEMA = 'gemma26-on-v2-postabort-findings-v1'
OUTPUT = Path('public-site/gemma26-postabort-findings.json')
PROJECTION = BASE / 'postabort-suffix-054-060-v1/public-composite-projection.json'
PUBLIC_REVIEW = BASE / 'postabort-suffix-054-060-v1/public-composite-review.json'
TERMINAL = BASE / 'postabort-suffix-054-060-v1/terminal-reconciliation-after-dev060.json'
AUDIT = BASE / 'postabort-suffix-054-060-v1/preflight-abort-after-dev053.json'
FOURTH_TERMINAL = BASE / 'fourth-suffix-007-016-v1/terminal-reconciliation-after-dev016.json'
FIFTH_TERMINAL = BASE / 'fifth-suffix-017-046-v1/terminal-reconciliation-after-dev046.json'
THIRD_PUBLIC = BASE / 'third-interruption-continuation-v1/terminal-public-after-dev006.json'
STAGES = (
    ('second-interruption-continuation-v1/fresh3/P2', 'development', 1, 5),
    ('third-interruption-continuation-v1/fresh3/P2', 'suffix', 6, 6),
    ('fourth-suffix-007-016-v1/fresh3/P2', 'suffix', 7, 16),
    ('fifth-suffix-017-046-v1/fresh3/P2', 'suffix', 17, 46),
    ('final-suffix-047-060-v1/fresh3/P2', 'suffix', 47, 53),
    ('postabort-suffix-054-060-v1/fresh3/P2', 'suffix', 54, 60),
)
IDS = [f'DEV-{i:03d}' for i in range(1, 61)]
PUBLIC_KEYS = {'id', 'requestSha256', 'status', 'prediction',
               'observedCostUsd', 'clientSeconds', 'tokens'}
TOKEN_KEYS = ('prompt_tokens', 'completion_tokens', 'total_tokens', 'reasoning_tokens')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind(root, relative, bindings, expected=None):
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Unsafe evidence path')
    path = (root / relative).resolve()
    path.relative_to(root.resolve())
    if not path.is_file():
        raise ValueError('Missing evidence: ' + str(relative))
    actual = sha(path)
    if expected is not None and actual != expected:
        raise ValueError('Evidence hash differs: ' + str(relative))
    item = {'path': relative.as_posix(), 'sha256': actual}
    if item not in bindings:
        bindings.append(item)
    return path


def stage_paths(root, stage):
    folder, phase, _, _ = stage
    base = root / BASE / folder
    return {key: base / (phase + '.' + extension) for key, extension in (
        ('claim', 'claim.json'), ('review', 'root-review.json'),
        ('journal', 'journal.jsonl'), ('attempts', 'attempts.jsonl'),
        ('responses', 'responses.jsonl'), ('wire', 'wire.jsonl'))}


def terminal_gate(root, bindings):
    """Require a sealed child and complete successor before any projection."""
    if root == ROOT:
        successor.prior_gate()  # Recheck the inherited failed attempts and abort.
    audit = json.loads(bind(root, AUDIT, bindings, successor.AUDIT_SHA).read_text())
    terminal = json.loads(bind(root, TERMINAL, bindings).read_text())
    fourth = json.loads(bind(root, FOURTH_TERMINAL, bindings).read_text())
    fifth = json.loads(bind(root, FIFTH_TERMINAL, bindings).read_text())
    third = json.loads(bind(root, THIRD_PUBLIC, bindings).read_text())
    if (third.get('new_failed_id') != 'DEV-006' or
            fourth.get('attempted_ids') != IDS[6:16] or
            fifth.get('attempted_ids') != IDS[16:46] or
            audit.get('attempted_ids') != IDS[46:53] or
            audit.get('next_never_sent_ids') != IDS[53:60] or
            terminal.get('schema') !=
                'gemma26-on-v2-postabort-suffix-terminal-reconciliation-v1' or
            terminal.get('status') not in (
                'terminal_completed_composite_phase_unscored',
                'terminal_stopped_all_positions_accounted_unscored') or
            terminal.get('attempted_ids') != IDS[53:60] or
            not isinstance(terminal.get('counts'), dict) or
            terminal['counts'].get('never_sent_stage') != 0 or
            terminal['counts'].get('valid', -1) + terminal['counts'].get('failed', -1) != 7 or
            terminal.get('score') is not None or
            terminal.get('reference_labels_read') is not False or
            terminal.get('manifest_sha256') != sha(bind(root, successor.BASE.relative_to(ROOT) / 'manifest.json', bindings)) or
            terminal.get('partition_id') != successor.PARTITION_ID):
        raise ValueError('Final Gemma 60-position terminal chain is incomplete')
    event = terminal.get('budget_reconciliation') or {}
    if (event.get('event') != 'partition_reconciled' or
            event.get('partition_id') != successor.PARTITION_ID or
            Decimal(str(event.get('unknown_upper_bound_usd'))) < 0 or
            Decimal(str(event.get('known_actual_usd'))) < Decimal(audit['known_actual_usd']) or
            not isinstance(event.get('child_sha256'), str) or
            len(event['child_sha256']) != 64):
        raise ValueError('Final child is not reconciled with known billing')
    bind(root, successor.CHILD.relative_to(ROOT), bindings, event['child_sha256'])
    return terminal


def projection_row(record, request):
    rid = request['record_id']
    if (record.get('id') != rid or
            record.get('request_sha256') != request['request_sha256'] or
            record.get('request') != request['payload'] or
            record.get('reference_labels_read') is not False):
        raise ValueError('Private attempt differs from frozen request: ' + rid)
    if record.get('status') == 'ok':
        if record.get('billing_ok') is not True:
            raise ValueError('Valid attempt lacks settled billing: ' + rid)
        row = second_report.public_row(record)
        return {**row, 'prediction': row['prediction']}
    status = record.get('status')
    if (rid not in ('DEV-005', 'DEV-006') and rid not in IDS[53:60]) or \
            status not in ('service_error', 'invalid_output', 'prompt_admission_failure'):
        raise ValueError('Unexpected failed or missing attempt: ' + rid)
    duration = record.get('elapsed_seconds')
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration < 0:
        raise ValueError('Invalid failed-call client duration')
    cost = record.get('observed_cost_usd')
    if cost is not None:
        amount = Decimal(str(cost))
        if not amount.is_finite() or amount < 0 or amount > successor.RESERVE:
            raise ValueError('Invalid failed-call observed cost')
        cost = str(amount)
    return {'id': rid, 'requestSha256': request['request_sha256'],
            'status': status, 'prediction': None,
            'observedCostUsd': cost,
            'clientSeconds': duration, 'tokens': {key: None for key in TOKEN_KEYS}}


def export_projection(root=ROOT):
    root = Path(root).resolve()
    if root != ROOT:
        raise ValueError('Private export requires the live repository root')
    bindings = []
    terminal = terminal_gate(root, bindings)
    manifest = successor.verify()[0]
    plan = successor.study.verify('fresh3', successor.first.PLAN_SHAS['fresh3'])
    requests = plan['conditions']['P2']['development']
    if [r['record_id'] for r in requests] != IDS:
        raise ValueError('Frozen plan is not 60 development requests')
    private = {}
    projected = []
    attempt_ids = set()
    for stage in STAGES:
        paths = stage_paths(root, stage)
        folder, phase, first, last = stage
        key = f'{first:03d}-{last:03d}'
        private[key] = {name: sha(path) for name, path in paths.items()}
        rows = first_report.rows(paths['attempts'])
        responses = first_report.rows(paths['responses'])
        wires = first_report.rows(paths['wire'])
        journal = first_report.rows(paths['journal'])
        ids = IDS[first - 1:last]
        response_by_id = {r.get('id'): r for r in responses}
        wire_by_id = {r.get('id'): r for r in wires}
        if ([r.get('id') for r in rows] != ids or
                len(response_by_id) != len(responses) or
                len(wire_by_id) != len(wires) or
                not set(response_by_id).issubset(ids) or
                not set(wire_by_id).issubset(ids) or
                len(journal) != 2 + 3 * len(ids) or
                [e.get('event') for e in journal[1:-1]] !=
                [e for _ in ids for e in ('request_intent', 'request_started', 'request_finished')] or
                journal[-1].get('event') not in (
                    ('phase_aborted',) if first == 47 else
                    ('phase_stopped',) if first in (1, 6) else
                    ('phase_completed', 'phase_stopped') if first == 54 else
                    ('phase_completed',))):
            raise ValueError('Stage lifecycle differs: ' + key)
        for record, request in zip(rows, requests[first - 1:last]):
            rid = request['record_id']
            aid = record.get('attempt_id')
            response = response_by_id.get(rid)
            wire = wire_by_id.get(rid)
            if (not isinstance(aid, str) or not aid or aid in attempt_ids or
                    (response is not None and response.get('attempt_id') != aid) or
                    (wire is not None and wire.get('attempt_id') != aid)):
                raise ValueError('Duplicate or mismatched attempt: ' + rid)
            attempt_ids.add(aid)
            if record.get('status') == 'ok':
                if (response is None or wire is None or
                        response.get('raw_response') != record.get('raw_response') or
                        wire.get('http_status') != 200 or
                        json.loads(base64.b64decode(wire['body_base64'], validate=True)) !=
                        record['raw_response']):
                    raise ValueError('Raw capture differs: ' + rid)
            projected.append(projection_row(record, request))
    failures = [r['id'] for r in projected if r['status'] != 'ok']
    if (len(projected) != 60 or [r['id'] for r in projected] != IDS or
            failures[:2] != ['DEV-005', 'DEV-006'] or
            any(rid not in ('DEV-005', 'DEV-006') and rid not in IDS[53:60]
                for rid in failures) or
            len([r for r in projected[53:] if r['status'] == 'ok']) !=
                terminal['counts']['valid']):
        raise ValueError('Incomplete or altered fixed-60 composite')
    expected = terminal.get('source_sha256') or {}
    for key in ('claim', 'journal', 'attempts', 'responses', 'wire'):
        if expected.get(key) != private['054-060'][key]:
            raise ValueError('Successor terminal source binding differs: ' + key)
    if terminal['budget_reconciliation']['child_sha256'] != sha(successor.CHILD):
        raise ValueError('Final child settlement differs')
    value = {'schema': SCHEMA + '-projection-v1',
             'status': 'awaiting_manual_public_review',
             'frozenPlanSha256': successor.first.PLAN_SHAS['fresh3'],
             'successorManifestSha256': sha(successor.BASE / 'manifest.json'),
             'terminalSha256': sha(root / TERMINAL),
             'privateSourceSha256': private,
             'manualPrivacyReviewRequired': True,
             'responses': projected}
    path = root / PROJECTION
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as out:
        json.dump(value, out, indent=2, ensure_ascii=False)
        out.write('\n')
        out.flush(); os.fsync(out.fileno())
    return path


def build(root=ROOT):
    root = Path(root).resolve()
    previous = second_report.build(root)
    if previous['completedConditions'] != 6:
        raise ValueError('Prior Gemma cutoff no longer has six scored cells')
    bindings = list(previous['sourceBindings'])
    bind(root, 'scripts/build_gemma26_postabort_findings.py', bindings)
    terminal = terminal_gate(root, bindings)
    projection_path = bind(root, PROJECTION, bindings)
    review_path = bind(root, PUBLIC_REVIEW, bindings)
    projection, review = (json.loads(p.read_text()) for p in
                          (projection_path, review_path))
    if (review != {'schema': SCHEMA + '-public-review-v1', 'approved': True,
                   'projectionSha256': sha(projection_path)} or
            projection.get('schema') != SCHEMA + '-projection-v1' or
            projection.get('status') != 'awaiting_manual_public_review' or
            projection.get('manualPrivacyReviewRequired') is not True or
            projection.get('frozenPlanSha256') != successor.first.PLAN_SHAS['fresh3'] or
            projection.get('terminalSha256') != sha(root / TERMINAL) or
            projection.get('successorManifestSha256') !=
                sha(root / successor.BASE.relative_to(ROOT) / 'manifest.json')):
        raise ValueError('Gemma public projection lacks its exact manual review')
    private = projection.get('privateSourceSha256')
    if (not isinstance(private, dict) or
            set(private) != {f'{a:03d}-{b:03d}' for _, _, a, b in STAGES} or
            any(not isinstance(v, dict) or
                set(v) != {'claim', 'review', 'journal', 'attempts',
                           'responses', 'wire'} or
                any(not isinstance(h, str) or len(h) != 64 or
                    any(c not in '0123456789abcdef' for c in h)
                    for h in v.values()) for v in private.values())):
        raise ValueError('Public projection lacks six source-bound stages')
    receipts = {
        '006-006': json.loads((root / THIRD_PUBLIC).read_text())['source_sha256'],
        '007-016': json.loads((root / FOURTH_TERMINAL).read_text())['source_sha256'],
        '017-046': json.loads((root / FIFTH_TERMINAL).read_text())['source_sha256'],
        '047-053': json.loads((root / AUDIT).read_text())['source_sha256'],
        '054-060': terminal['source_sha256'],
    }
    for range_id, expected in receipts.items():
        for name in ('claim', 'journal', 'attempts', 'responses', 'wire'):
            if private[range_id][name] != expected.get(name):
                raise ValueError('Public projection source binding differs: ' + range_id)
    plan_path = bind(root, successor.study.BASE.relative_to(ROOT) /
                     'fresh3/manifest.json', bindings,
                     successor.first.PLAN_SHAS['fresh3'])
    requests = json.loads(plan_path.read_text())['conditions']['P2']['development']
    rows = projection.get('responses')
    if not isinstance(rows, list) or len(rows) != 60:
        raise ValueError('Public composite lacks 60 rows')
    for row, request in zip(rows, requests):
        if (not isinstance(row, dict) or set(row) != PUBLIC_KEYS or
                row.get('id') != request['record_id'] or
                row.get('requestSha256') != request['request_sha256'] or
                row.get('status') not in ('ok', 'service_error', 'invalid_output',
                                          'prompt_admission_failure') or
                not isinstance(row.get('tokens'), dict) or
                set(row['tokens']) != set(TOKEN_KEYS) or
                type(row.get('clientSeconds')) not in (int, float) or
                not math.isfinite(row['clientSeconds']) or row['clientSeconds'] < 0):
            raise ValueError('Public row differs from frozen plan')
        if row['status'] == 'ok':
            second_report.validate_public_row(row, request, successor.RESERVE)
        elif ((row['id'] not in ('DEV-005', 'DEV-006') and
               row['id'] not in IDS[53:60]) or
              row['prediction'] is not None or
              any(v is not None for v in row['tokens'].values())):
            raise ValueError('Unexpected failed public row')
        elif row['observedCostUsd'] is not None:
            amount = Decimal(str(row['observedCostUsd']))
            if not amount.is_finite() or amount < 0 or amount > successor.RESERVE:
                raise ValueError('Invalid failed public cost')
    failed_ids = [r['id'] for r in rows if r['status'] != 'ok']
    if (failed_ids[:2] != ['DEV-005', 'DEV-006'] or
            sum(r['status'] == 'ok' for r in rows[53:]) !=
            terminal['counts']['valid']):
        raise ValueError('Public composite failure membership differs')
    labels_path = bind(root, first_report.LABELS, bindings, first_report.LABEL_SHA)
    labels = {r['id']: r['proposed_labels'] for r in first_report.rows(labels_path)}
    score = first_report.score([{'id': r['id'], 'status': r['status'],
        'prediction': r['prediction']} for r in rows], labels)
    if score['saved'] != 60 or score['scoreKind'] != 'fixed_60':
        raise ValueError('Fixed-60 scoring prerequisite differs')
    return {'schema': SCHEMA, 'seriesId': successor.SCHEMA,
            'configuration': previous['configuration'],
            'method': 'descriptive-interrupted-composite',
            'cleanMatchedThreeEligible': False,
            'denominator': 60, 'plannedConditions': 9,
            'completedConditions': 7,
            'priorCompletedConditions': 6,
            'fresh3P2': {'status': 'completed_composite_interrupted',
                'score': score, 'valid': score['valid'], 'failedIds': failed_ids,
                'stageRanges': [f'DEV-{a:03d}..DEV-{b:03d}' for _, _, a, b in STAGES]},
            'fresh3P0': {'status': 'never_sent', 'score': None},
            'fresh3P1': {'status': 'never_sent', 'score': None},
            'referenceStatus': 'frozen_provisional_v0.2_human_checked_2026-10-02',
            'timingKind': 'client_request_to_record_not_provider_inference',
            'billing': {'finalChildKnownActualUsd': terminal['budget_reconciliation']['known_actual_usd'],
                        'finalChildUnknownUpperBoundUsd':
                            terminal['budget_reconciliation']['unknown_upper_bound_usd'],
                        'isProviderInvoice': False},
            'sourceBindings': bindings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--export-public-projection', action='store_true')
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.export_public_projection:
        if args.check or args.root.resolve() != ROOT or args.output != OUTPUT:
            raise ValueError('Private export requires the current repository root')
        print(export_projection(args.root))
        return
    value = json.dumps(build(args.root), indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if args.output.read_text() != value:
            raise ValueError('Gemma postabort findings differ')
    else:
        args.output.write_text(value)
    print('Gemma postabort findings:', 'checked' if args.check else 'written')


if __name__ == '__main__':
    main()
