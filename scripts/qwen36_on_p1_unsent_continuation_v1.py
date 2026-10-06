#!/usr/bin/env python3
"""Proposed separate Qwen3.6 ON P1 continuation for DEV-050 through DEV-060.

The original DEV-049 attempt and unknown-charge reserve remain with the parent.
Preparing and verifying this proposal never allocate a child or send inference.
"""
import argparse
import base64
from copy import deepcopy
from decimal import Decimal
import json
import os
from pathlib import Path

import openrouter_budget_v4 as budget
import paid_budget_partitions_v4 as partitions
import postapproval_authority_v3 as authority
import qwen36_on_hosted_authority_v2 as parent

study = parent.study
ROOT = study.ROOT
OLD = parent.BASE / 'fresh1/P1'
BASE = parent.BASE / 'p1-unsent-continuation-v1'
MANIFEST = BASE / 'manifest.json'
BUDGET = BASE / 'budget.json'
PARTITION_ID = 'qwen36-on-hosted-p1-unsent-v1'
CAP = Decimal('0.3289088')  # Eleven full per-request reserves.
SCHEMA = 'qwen36-on-p1-unsent-continuation-v1'
FIRST, LAST = 50, 60
OLD_FILES = ('development.claim.json', 'development.root-review.json',
             'development.journal.jsonl', 'development.attempts.jsonl',
             'development.responses.jsonl', 'smoke.claim.json',
             'smoke.journal.jsonl', 'smoke.attempts.jsonl',
             'smoke.responses.jsonl', 'smoke-inspection.json')
RUNTIME = ('qwen36_on_p1_unsent_continuation_v1.py',
           'qwen36_on_hosted_authority_v2.py',
           'qwen36_on_fresh_repeat_execution.py',
           'qwen36_on_fresh_repeat_study.py',
           'qwen27_fresh_repeat_execution.py',
           'openrouter_paid_benchmark.py', 'openrouter_benchmark.py',
           'paid_budget_partitions_v4.py', 'openrouter_budget_v4.py',
           'postapproval_authority_v3.py', 'prompt_admission.py')


def rows(path):
    raw = Path(path).read_bytes()
    if raw and not raw.endswith(b'\n'):
        raise ValueError('Incomplete parent JSONL: ' + str(path))
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def binding(path):
    path = Path(path).resolve()
    path.relative_to(ROOT.resolve())
    return {'path': str(path.relative_to(ROOT.resolve())), 'sha256': study.sha(path)}


def bound(item):
    path = (ROOT / item['path']).resolve()
    path.relative_to(ROOT.resolve())
    if study.sha(path) != item['sha256']:
        raise ValueError('Bound source changed: ' + item['path'])
    return path


def verify_parent_smoke(original):
    # The suffix has no smoke of its own. Verify the inspected parent smoke
    # against its original plan and original output folder.
    core = parent._private_runner()
    checked = core.verify_phase_closure(original, 'P1', 'smoke')
    inspection = json.loads((OLD / 'smoke-inspection.json').read_text())
    expected = {
        'schema': 'openrouter-repeat-smoke-inspection-v1',
        'configuration_id': parent.CONFIG, 'fresh_pass': 'fresh1',
        'condition': 'P1', 'decision': 'accepted_unchanged',
        'manifest_sha256': checked['manifest_sha256'],
        'journal_sha256': checked['journal_sha256'],
        'attempts_sha256': checked['attempts_sha256'],
        'responses_sha256': checked['responses_sha256'],
    }
    if (not isinstance(inspection.get('note'), str) or not inspection['note'].strip() or
            {k: inspection.get(k) for k in expected} != expected or
            set(inspection) != set(expected) | {'note'}):
        raise ValueError('Inspected parent P1 smoke differs')
    return checked


def audit_parent():
    parent.verify()
    original_path = parent.BASE / 'fresh1/manifest.json'
    original = parent.verify_plan('fresh1', study.sha(original_path))
    verify_parent_smoke(original)
    requests = original['conditions']['P1']['development']
    if [r['record_id'] for r in requests] != [f'DEV-{n:03}' for n in range(1, 61)]:
        raise ValueError('Original P1 request membership changed')
    attempts = rows(OLD / 'development.attempts.jsonl')
    responses = rows(OLD / 'development.responses.jsonl')
    journal = rows(OLD / 'development.journal.jsonl')
    ids = [f'DEV-{n:03}' for n in range(1, 50)]
    if len(attempts) != 49 or [r.get('id') for r in attempts] != ids:
        raise ValueError('Parent attempted membership differs')
    if len(responses) != 48 or [r.get('id') for r in responses] != ids[:48]:
        raise ValueError('Parent raw-response membership differs')
    if len(journal) != 149 or journal[0].get('event') != 'phase_started' or journal[-1].get('event') != 'phase_stopped' or journal[-1].get('id') != 'DEV-049' or journal[-1].get('reason') != 'service_error':
        raise ValueError('Parent journal terminal differs')
    for i, (attempt, request) in enumerate(zip(attempts, requests), 1):
        rid = request['record_id']
        if (attempt.get('request_sha256') != request['request_sha256'] or
                attempt.get('request') != request['payload'] or
                attempt.get('manifest_sha256') != study.sha(original_path) or
                attempt.get('attempt_id') != journal[3*i-1].get('attempt_id') or
                journal[3*i-2].get('event') != 'request_intent' or
                journal[3*i-1].get('event') != 'request_started' or
                journal[3*i].get('event') != 'request_finished' or
                any(journal[j].get('id') != rid for j in (3*i-2, 3*i-1, 3*i))):
            raise ValueError('Parent request, attempt or journal binding differs')
        if i < 49:
            raw = responses[i-1]
            if (attempt.get('status') != 'ok' or attempt.get('cost_unknown') is not False or
                    attempt.get('billing_ok') is not True or
                    raw.get('attempt_id') != attempt.get('attempt_id') or
                    raw.get('request_sha256') != request['request_sha256']):
                raise ValueError('Parent valid response binding differs')
            captured = json.loads(base64.b64decode(raw['body_base64'], validate=True))
            if (raw.get('http_status') != 200 or
                    raw.get('body_truncated_at_limit') is not False or
                    captured != attempt.get('raw_response')):
                raise ValueError('Parent raw response bytes differ from attempt')
    known = sum((Decimal(x['observed_cost_usd']) for x in attempts[:48]), Decimal(0))
    if known != Decimal('0.0562018'):
        raise ValueError('Parent P1 known cost differs')
    failed = attempts[-1]
    if (failed.get('status'), failed.get('error_type'), failed.get('cost_unknown'),
            failed.get('observed_cost_usd'), failed.get('http_status'),
            failed.get('reserved_cost_usd'), failed.get('raw_response')) != (
            'service_error', 'TimeoutError', True, None, None,
            str(parent.RESERVE), None):
        raise ValueError('DEV-049 is no longer the preserved unknown timeout')
    if [x['event'] for x in journal].count('request_intent') != 49:
        raise ValueError('Parent request-intent count differs')
    child = rows(parent.BASE / ('budget-' + parent.PARTITION_ID + '.jsonl'))
    reserves = [e for e in child if e.get('event') == 'reserve']
    if len(reserves) < 49 or reserves[-1].get('attempt_id') != failed['attempt_id']:
        raise ValueError('Parent unknown reserve is absent from child')
    return original, requests[FIRST-1:]


def expected_manifest():
    original, requests = audit_parent()
    sources = {name: binding(OLD / name) for name in OLD_FILES}
    sources.update({
        'original_plan': binding(parent.BASE / 'fresh1/manifest.json'),
        'original_execution': binding(parent.EXECUTION),
        'public_route': binding(parent.ROUTE),
    })
    sources.update({'code_' + name: binding(ROOT / 'scripts' / name) for name in RUNTIME})
    return {'schema': SCHEMA, 'status': 'offline_proposal_unapproved',
            'configuration_id': parent.CONFIG, 'fresh_pass': 'fresh1',
            'condition': 'P1', 'phase': 'development',
            'method': 'separate_same_route_never_sent_suffix',
            'clean_full_phase': False, 'parent_valid': 48,
            'parent_unknown_attempted_id': 'DEV-049',
            'parent_unknown_charge_upper_bound_usd': str(parent.RESERVE),
            'parent_known_p1_usd': '0.0562018',
            'never_sent_ids': [r['record_id'] for r in requests],
            'requests': deepcopy(requests), 'per_request_reserve_usd': str(parent.RESERVE),
            'proposed_new_child_cap_usd': str(CAP),
            'new_partition_id': PARTITION_ID, 'funding_pool': 'openrouter_additional',
            'parent_finalization_required': True,
            'independent_root_review_required': True,
            'reference_labels_read': False, 'inference_authorized': False,
            'source_bindings': sources}


def freeze():
    value = expected_manifest()
    BASE.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open('x') as out:
        json.dump(value, out, indent=2)
        out.write('\n'); out.flush(); os.fsync(out.fileno())
    return study.sha(MANIFEST)


def verify(expected_sha=None):
    if expected_sha and study.sha(MANIFEST) != expected_sha:
        raise ValueError('Continuation manifest SHA differs')
    saved = json.loads(MANIFEST.read_text())
    for item in saved['source_bindings'].values():
        bound(item)
    if saved != expected_manifest():
        raise ValueError('Continuation proposal or source evidence changed')
    return saved


def finalized_parent():
    child_path = parent.BASE / ('budget-' + parent.PARTITION_ID + '.jsonl')
    if not child_path.is_file():
        raise ValueError('Parent child ledger missing')
    child = budget.BudgetLedger(child_path, cap_limit=parent.CAP)
    try:
        _, pending, blocked = child.state()
        if pending or blocked or not child.closed:
            raise ValueError('Parent child is not conservatively closed')
        events = child.events
        unknown = [e for e in events if e.get('event') == 'unknown_cost_accounted_as_upper_bound']
        failed_id = rows(OLD / 'development.attempts.jsonl')[-1]['attempt_id']
        if len(unknown) != 1 or unknown[0].get('attempt_id') != failed_id or Decimal(unknown[0].get('usd', '-1')) != parent.RESERVE:
            raise ValueError('DEV-049 unknown reserve was not fully accounted')
        evidence = Path(unknown[0]['evidence_path'])
        if evidence.resolve() != (OLD / 'development.attempts.jsonl').resolve() or study.sha(evidence) != unknown[0]['evidence_sha256']:
            raise ValueError('Unknown-charge evidence binding differs')
    finally:
        child.close()
    master = budget.BudgetLedger(parent.MASTER)
    try:
        _, pending, blocked = master.state()
        if pending or blocked:
            raise ValueError('Master has pending or blocked accounting')
        part = master.partitions[parent.PARTITION_ID]
        reconciled = [e for e in master.events if e.get('event') == 'partition_reconciled' and e.get('partition_id') == parent.PARTITION_ID]
        if part['active'] or len(reconciled) != 1 or reconciled[0].get('child_sha256') != study.sha(child_path) or Decimal(reconciled[0]['unknown_upper_bound_usd']) != parent.RESERVE:
            raise ValueError('Parent allocation remains active')
    finally:
        master.close()


def hold_source(manifest_sha):
    verify(manifest_sha)
    return study.digest(json.dumps({
        'continuation_manifest_sha256': manifest_sha,
        'budget_manifest_sha256': study.sha(BUDGET),
        'parent_child_sha256': study.sha(parent.BASE / ('budget-' + parent.PARTITION_ID + '.jsonl')),
        'partition_id': PARTITION_ID, 'cap_usd': str(CAP),
        'model': study.MODEL, 'provider': study.PROVIDER, 'reasoning': 'on',
    }, sort_keys=True))


def review_template(manifest_sha):
    verify(manifest_sha)
    finalized_parent()
    manifest = json.loads(BUDGET.read_text())
    entries = manifest.get('partitions')
    if (manifest.get('version') != 'paid-partitions-v1' or
            manifest.get('master_ledger') != str(parent.MASTER) or
            not isinstance(entries, list) or len(entries) != 1):
        raise ValueError('Separate child manifest differs')
    item = entries[0]
    if (item.get('id') != PARTITION_ID or item.get('cap_usd') != str(CAP) or
            item.get('model') != study.MODEL or item.get('provider') != study.PROVIDER or
            item.get('reasoning') != 'on' or
            Path(item.get('child_ledger', '')).resolve() !=
                (BASE / (BUDGET.stem + '-' + PARTITION_ID + '.jsonl')).resolve()):
        raise ValueError('Separate child route or cap differs')
    with authority.old._locked(parent.AUTHORITY) as handle:
        snapshot, holds = authority._scan(handle.read())
    hold = holds.get(PARTITION_ID)
    if (hold is None or hold.get('funding_pool') != 'openrouter_additional' or
            hold.get('usd') != str(CAP) or hold.get('budget_manifest_sha256') != study.sha(BUDGET) or
            hold.get('partition_id') != PARTITION_ID or hold.get('source_sha256') != hold_source(manifest_sha)):
        raise ValueError('Separate OpenRouter authority hold absent or mismatched')
    return {'schema': SCHEMA + '-root-review', 'approved': False,
            'independent_review': False, 'authorized_by_root': False,
            'reviewer': None, 'manifest_sha256': manifest_sha,
            'controller_sha256': study.sha(__file__),
            'stage': 'fresh1/P1/development', 'parent_partition_id': parent.PARTITION_ID,
            'parent_child_sha256': study.sha(parent.BASE / ('budget-' + parent.PARTITION_ID + '.jsonl')),
            'new_budget_manifest_sha256': study.sha(BUDGET),
            'new_partition_id': PARTITION_ID, 'authority_head_sha256': snapshot.head_sha256,
            'authority_hold_source_sha256': hold['source_sha256']}


def private_runner(manifest_sha):
    core = parent._private_runner()
    class BasePath:
        def __truediv__(self, config):
            if config != parent.CONFIG:
                raise ValueError('Unknown configuration')
            return BASE
    class Study(parent.frozen._Study):
        BASE = BasePath()
        CONFIGS = {parent.CONFIG: {'effort': 'on', 'historical_continue_on_invalid': False,
                                   'proposed_child_budget': CAP}}
        @staticmethod
        def verify(config, repeat, digest):
            if (config, repeat, digest) != (parent.CONFIG, 'fresh1', manifest_sha):
                raise ValueError('Unknown continuation plan')
            saved = verify(digest)
            original = parent.verify_plan('fresh1', saved['source_bindings']['original_plan']['sha256'])
            plan = deepcopy(original)
            plan['conditions']['P1']['development'] = saved['requests']
            plan['condition_order'] = ['P1']
            return plan
    core.study = Study
    core.live_controls = parent.live_controls
    def require_order(plan, condition, phase):
        if (condition, phase) != ('P1', 'development'):
            raise ValueError('Only P1 development suffix allowed')
        verify(manifest_sha)
        original = parent.verify_plan('fresh1', study.sha(parent.BASE / 'fresh1/manifest.json'))
        verify_parent_smoke(original)
        finalized_parent()
    core.require_order = require_order
    def reviewed(path, config, repeat, condition, phase, digest):
        expected_path = BASE / 'fresh1/P1/development.root-review.json'
        if Path(path).resolve() != expected_path.resolve():
            raise ValueError('Separate review path differs')
        template = review_template(manifest_sha)
        approved = {**template, 'approved': True, 'independent_review': True,
                    'authorized_by_root': True, 'reviewer': 'root'}
        if (config, repeat, condition, phase, digest) != (parent.CONFIG, 'fresh1', 'P1', 'development', manifest_sha) or json.loads(expected_path.read_text()) != approved:
            raise ValueError('Independent root review differs')
        return approved, BUDGET
    def gated(receipt, budget_path, config):
        if config != parent.CONFIG or receipt['authority_head_sha256'] != authority.read_authority(parent.AUTHORITY).head_sha256:
            raise ValueError('Authority head changed')
        ledger = partitions.open_partition(parent.MASTER, BUDGET, PARTITION_ID,
                                            study.MODEL, study.PROVIDER, 'on')
        try:
            _, pending, blocked = ledger.state()
            if ledger.cap != CAP or pending or blocked or ledger.closed or ledger.accounted() + parent.RESERVE > CAP:
                raise ValueError('Separate child unavailable before key read')
            return ledger
        except BaseException:
            ledger.close(); raise
    core.review_receipt = reviewed
    core.budget_gate = gated
    return core


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=('audit-parent', 'freeze', 'verify', 'hold-source', 'review-template', 'run'))
    p.add_argument('--manifest-sha256')
    p.add_argument('--env-file')
    args = p.parse_args()
    if args.action == 'audit-parent':
        _, requests = audit_parent(); print(json.dumps({'attempted': 49, 'valid': 48,
            'unknown_attempted': 'DEV-049', 'never_sent': [r['record_id'] for r in requests]})); return
    if args.action == 'freeze': print(freeze()); return
    if not args.manifest_sha256: p.error('Exact --manifest-sha256 required')
    verify(args.manifest_sha256)
    if args.action == 'verify': print('verified'); return
    if args.action == 'hold-source':
        finalized_parent(); print(hold_source(args.manifest_sha256)); return
    if args.action == 'review-template':
        print(json.dumps(review_template(args.manifest_sha256), indent=2)); return
    core = private_runner(args.manifest_sha256)
    print(core.execute(parent.CONFIG, 'fresh1', 'P1', 'development',
        args.manifest_sha256, BASE / 'fresh1/P1/development.root-review.json', args.env_file))


if __name__ == '__main__':
    main()
