#!/usr/bin/env python3
"""Versioned admission for Gemma fresh3 P0/P1 after the interrupted P2 composite.

This module changes only the predecessor gate. Requests, transport, parser,
invalid-output policy, phase files, and per-call budget execution remain in the
frozen v2 runner. Preparation and verification make no provider calls.
"""

import argparse
from contextlib import contextmanager
from decimal import Decimal
import fcntl
import hashlib
import json
from pathlib import Path

import build_gemma26_postabort_findings as composite
import gemma26_on_fresh_repeat_execution_v2 as frozen
import gemma26_on_fresh_repeat_study_v2 as study

ROOT = study.ROOT
BASE = study.BASE / 'fresh3-p0-p1-composite-successor-v1'
MANIFEST = BASE / 'manifest.json'
AUTHORITY = ROOT / 'results/postapproval-paid-work-2026-10-02.jsonl'
AUTHORITY_ID = 'openrouter-gemma26-fresh3-p0-p1-v1'
AUTHORITY_APPROVAL_SHA = '57d5ff76acd14f85d5e600c6527c310fc08f4eb66d45b1c25b9d778d770aaf8f'
AUTHORITY_DECISION_KEY = 'candidate-experience-benchmark/user-ten-dollar-tests-20261002'
AUTHORITY_CAP = Decimal('10.00')
CHILD_CAP = Decimal('0.40')
SCHEMA = 'gemma26-fresh3-p0-p1-composite-successor-v1'
PROJECTION = ROOT / composite.PROJECTION
PUBLIC_REVIEW = ROOT / composite.PUBLIC_REVIEW
TERMINAL = ROOT / composite.TERMINAL
PUBLIC_FEED = ROOT / composite.OUTPUT


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def saved_json(path):
    return json.loads(Path(path).read_text())


def composite_gate():
    """Verify the six predecessor stages and exact 58/2 P2 public composite."""
    report = composite.build(ROOT)
    saved = saved_json(PUBLIC_FEED)
    if report != saved or report.get('fresh3P2', {}).get('status') != 'completed_composite_interrupted' or \
            report['fresh3P2'].get('valid') != 58 or \
            report['fresh3P2'].get('failedIds') != ['DEV-005', 'DEV-006'] or \
            report.get('cleanMatchedThreeEligible') is not False:
        raise ValueError('P2 composite or saved public finding changed')
    projection = saved_json(PROJECTION)
    review = saved_json(PUBLIC_REVIEW)
    terminal = saved_json(TERMINAL)
    if (review != {'schema': composite.SCHEMA + '-public-review-v1',
                   'approved': True, 'projectionSha256': sha(PROJECTION)} or
            projection.get('terminalSha256') != sha(TERMINAL) or
            terminal.get('status') != 'terminal_completed_composite_phase_unscored'):
        raise ValueError('P2 terminal review binding changed')
    return report


def manifest_value():
    composite_gate()
    plans = {}
    for repeat in study.ORDERS:
        path = study.BASE / repeat / 'manifest.json'
        digest = sha(path)
        study.verify(repeat, digest)
        plans[repeat] = digest
    if list(study.ORDERS['fresh3']) != ['P2', 'P0', 'P1']:
        raise ValueError('Frozen fresh3 order changed')
    return {'schema': SCHEMA, 'series_id': study.SERIES,
            'configuration_id': study.CONFIG, 'model': study.MODEL,
            'provider': study.PROVIDER, 'reasoning_effort': study.EFFORT,
            'stages': ['fresh3/P0/smoke', 'fresh3/P0/development',
                       'fresh3/P1/smoke', 'fresh3/P1/development'],
            'predecessor': 'P2 has 60 attempted positions, 58 valid and two preserved service errors; descriptive composite, not a clean full phase',
            'preserved_failed_ids': ['DEV-005', 'DEV-006'],
            'frozen_plan_sha256': plans,
            'frozen_runner_sha256': sha(ROOT / 'scripts/gemma26_on_fresh_repeat_execution_v2.py'),
            'composite_builder_sha256': sha(ROOT / 'scripts/build_gemma26_postabort_findings.py'),
            'composite_terminal_sha256': sha(TERMINAL),
            'composite_projection_sha256': sha(PROJECTION),
            'composite_review_sha256': sha(PUBLIC_REVIEW),
            'composite_feed_sha256': sha(PUBLIC_FEED),
            'per_request_reserve_usd': '0.01974272',
            'proposed_child_cap_usd': str(CHILD_CAP),
            'global_hold_id': AUTHORITY_ID,
            'global_hold_usd': str(CHILD_CAP),
            'global_hold_scope': 'one reviewed child partition and ledger identity for all admitted stages',
            'admission': 'independent review and root stage receipt; fresh exact route, child and global hold checks before inference'}


def verify():
    value = manifest_value()
    if saved_json(MANIFEST) != value:
        raise ValueError('Versioned admission manifest differs from frozen evidence')
    return value


def prepare():
    value = manifest_value()
    BASE.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open('x') as file:
        json.dump(value, file, indent=2)
        file.write('\n')
    return sha(MANIFEST)


def require_order(plan, condition, phase):
    if plan.get('fresh_pass') != 'fresh3' or condition not in ('P0', 'P1') or \
            phase not in ('smoke', 'development'):
        raise ValueError('Successor admits only fresh3 P0/P1 smoke/development')
    verify()
    if condition == 'P1':
        frozen.verify_phase_closure(plan, 'P0', 'development')
    if phase == 'development':
        folder, _, journal, attempts = frozen.phase_paths('fresh3', condition, 'smoke')
        inspection_path = folder / 'smoke-inspection.json'
        if not inspection_path.exists():
            raise ValueError('Inspected smoke required')
        inspection = saved_json(inspection_path)
        bindings = frozen.verify_phase_closure(plan, condition, 'smoke')
        if (inspection.get('schema') != 'openrouter-repeat-smoke-inspection-v2' or
                inspection.get('series_id') != study.SERIES or
                inspection.get('decision') != 'accepted_unchanged' or
                inspection.get('manifest_sha256') != bindings['manifest_sha256'] or
                inspection.get('journal_sha256') != sha(journal) or
                inspection.get('attempts_sha256') != sha(attempts) or
                inspection.get('responses_sha256') != sha(folder / 'smoke.responses.jsonl') or
                inspection.get('wire_sha256') != sha(folder / 'smoke.wire.jsonl')):
            raise ValueError('Smoke inspection binding changed')


@contextmanager
def successor_order_gate():
    original = frozen.require_order
    frozen.require_order = require_order
    try:
        yield
    finally:
        frozen.require_order = original


def global_hold_source(budget_manifest, partition_id):
    """Hash the immutable identity that the fixed global hold pays for."""
    path = Path(budget_manifest).resolve()
    root = ROOT.resolve()
    path.relative_to(root)
    budget = saved_json(path)
    if budget.get('version') != 'paid-partitions-v1' or \
            budget.get('master_ledger') != str(frozen.MASTER.resolve()):
        raise ValueError('Global hold budget manifest differs')
    entries = [entry for entry in budget.get('partitions', [])
               if entry.get('id') == partition_id]
    if len(entries) != 1:
        raise ValueError('Global hold partition identity differs')
    entry = entries[0]
    if (entry.get('cap_usd') != str(CHILD_CAP) or
            entry.get('model') != study.MODEL or
            entry.get('provider') != study.PROVIDER or
            entry.get('reasoning') != study.EFFORT):
        raise ValueError('Global hold partition controls differ')
    child = Path(entry['child_ledger']).resolve()
    child.relative_to(root)
    identity = {'successor_manifest_sha256': sha(MANIFEST),
                'budget_manifest_path': str(path),
                'budget_manifest_sha256': sha(path),
                'partition_id': partition_id,
                'child_ledger_path': str(child)}
    return hashlib.sha256(json.dumps(identity, sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()


def expected_review(repeat, condition, phase, budget_manifest, partition_id):
    if repeat != 'fresh3' or condition not in ('P0', 'P1') or phase not in ('smoke', 'development'):
        raise ValueError('Stage outside successor')
    manifest = verify()
    original = {'schema': frozen.RECEIPT_SCHEMA, 'approved': True,
                'series_id': study.SERIES, 'configuration_id': study.CONFIG,
                'stage': f'{repeat}/{condition}/{phase}',
                'controller_sha256': manifest['frozen_runner_sha256'],
                'hosted_execution_sha256': sha(frozen.HOSTED_EXECUTION),
                'plan_sha256': manifest['frozen_plan_sha256'],
                'master_ledger': str(frozen.MASTER),
                'partition_cap_usd': str(CHILD_CAP),
                'budget_manifest': {'path': str(Path(budget_manifest).relative_to(ROOT)),
                                    'sha256': sha(budget_manifest)},
                'partition_id': partition_id}
    original.update(successor_schema=SCHEMA, successor_manifest_sha256=sha(MANIFEST),
                    successor_controller_sha256=sha(__file__),
                    composite_terminal_sha256=manifest['composite_terminal_sha256'],
                    composite_projection_sha256=manifest['composite_projection_sha256'],
                    composite_review_sha256=manifest['composite_review_sha256'],
                    global_authority_head_sha256=sha(AUTHORITY),
                    global_hold_id=AUTHORITY_ID,
                    global_hold_source_sha256=global_hold_source(budget_manifest, partition_id),
                    reviewer=None)
    return original


def check_review(path, repeat, condition, phase):
    value = saved_json(path)
    budget = value.get('budget_manifest')
    if not isinstance(budget, dict) or not isinstance(value.get('partition_id'), str) or \
            not value['partition_id'] or not isinstance(value.get('reviewer'), str) or \
            not value['reviewer'].strip():
        raise ValueError('Independent root stage receipt required')
    expected = expected_review(repeat, condition, phase,
                               ROOT / budget['path'], value['partition_id'])
    expected['reviewer'] = value['reviewer']
    if value != expected:
        raise ValueError('Successor stage receipt differs from reviewed evidence')
    frozen.review_receipt(path, repeat, condition, phase,
                          verify()['frozen_plan_sha256']['fresh3'])
    return value


def hold_authority(expected_head, budget_manifest, partition_id, expected_source):
    """Bind one $0.40 global hold to one child; never release token estimates."""
    source = global_hold_source(budget_manifest, partition_id)
    if source != expected_source:
        raise ValueError('Reviewed global hold source differs')
    with AUTHORITY.open('r+') as file:
        fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        file.seek(0)
        raw = file.read().encode()
        if hashlib.sha256(raw).hexdigest() != expected_head:
            raise ValueError('Global authority head changed')
        events = [json.loads(line) for line in raw.splitlines() if line.strip()]
        if not events or events[0] != {'event': 'authority', 'kind': 'postapproval-paid-work-v1',
                                      'cap_usd': str(AUTHORITY_CAP),
                                      'decision_key': AUTHORITY_DECISION_KEY,
                                      'approval_sha256': AUTHORITY_APPROVAL_SHA}:
            raise ValueError('Global paid-work authority differs')
        holds = [e for e in events[1:] if e.get('event') == 'hold']
        if len(holds) != len(events) - 1 or len({e.get('id') for e in holds}) != len(holds):
            raise ValueError('Global authority event structure differs')
        total = sum((Decimal(e['usd']) for e in holds), Decimal(0))
        if total > AUTHORITY_CAP:
            raise ValueError('Global paid-work cap exceeded')
        existing = [e for e in holds if e['id'] == AUTHORITY_ID]
        desired = {'event': 'hold', 'id': AUTHORITY_ID,
                   'source_sha256': source, 'usd': str(CHILD_CAP)}
        if existing:
            if existing != [desired]:
                raise ValueError('Global Gemma hold differs')
        else:
            if total + CHILD_CAP > AUTHORITY_CAP:
                raise ValueError('Global paid-work cap cannot fit Gemma hold')
            file.seek(0, 2)
            frozen.durable(file, desired)


def run(condition, phase, receipt_path, env_file=None):
    manifest = verify()
    plan = study.verify('fresh3', manifest['frozen_plan_sha256']['fresh3'])
    require_order(plan, condition, phase)
    receipt = check_review(receipt_path, 'fresh3', condition, phase)
    folder, claim, journal, attempts = frozen.phase_paths('fresh3', condition, phase)
    if any(path.exists() for path in (claim, journal, attempts,
                                      folder / (phase + '.responses.jsonl'),
                                      folder / (phase + '.wire.jsonl'))):
        raise FileExistsError('Phase already claimed; no replay')
    # The frozen runner repeats these live endpoint and partition checks.
    frozen.live_controls(plan, condition)
    ledger = frozen.budget_gate(receipt, ROOT / receipt['budget_manifest']['path'])
    ledger.close()
    hold_authority(receipt['global_authority_head_sha256'],
                   ROOT / receipt['budget_manifest']['path'],
                   receipt['partition_id'], receipt['global_hold_source_sha256'])
    with successor_order_gate():
        return frozen.execute('fresh3', condition, phase,
                              manifest['frozen_plan_sha256']['fresh3'],
                              receipt_path, env_file)


def inspect(condition, note):
    manifest = verify()
    plan = study.verify('fresh3', manifest['frozen_plan_sha256']['fresh3'])
    require_order(plan, condition, 'smoke')
    with successor_order_gate():
        return frozen.inspect('fresh3', condition,
                              manifest['frozen_plan_sha256']['fresh3'], note)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('prepare')
    sub.add_parser('verify')
    for action in ('smoke', 'development', 'inspect'):
        p = sub.add_parser(action)
        p.add_argument('--condition', choices=('P0', 'P1'), required=True)
        if action == 'inspect':
            p.add_argument('--note', required=True)
        else:
            p.add_argument('--root-review-receipt', required=True)
            p.add_argument('--env-file')
    args = parser.parse_args()
    if args.action == 'prepare':
        print(prepare())
    elif args.action == 'verify':
        print(sha(MANIFEST) if verify() else '')
    elif args.action == 'inspect':
        print(json.dumps(inspect(args.condition, args.note)))
    else:
        print(run(args.condition, args.action, args.root_review_receipt, args.env_file))


if __name__ == '__main__':
    main()
