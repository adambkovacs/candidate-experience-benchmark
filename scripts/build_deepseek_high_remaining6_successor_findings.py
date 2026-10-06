#!/usr/bin/env python3
"""Publish only source-bound, archived DeepSeek high successor closures."""
import argparse
import base64
from collections import Counter
from decimal import Decimal
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/deepseek-high-remaining7-price-v1')
SUCCESSOR = BASE / 'unsent-continuation-v1'
EXECUTION = SUCCESSOR / 'execution-adapter-v1'
PARENT = BASE / 'execution-adapter-v1/fresh2/P2'
LABELS = Path('data/pilot/proposed_labels.jsonl')
OUTPUT = Path('public-site/deepseek-high-remaining6-successor-findings.json')
STAGES = (('fresh2', 'P2', 33), ('fresh2', 'P0', 60), ('fresh2', 'P1', 60),
          ('fresh3', 'P1', 60), ('fresh3', 'P2', 60))
FIELDS = ('sentiment', 'follow_up_needed', 'serious_concern_reported',
          'testimonial_potential')
IDS = [f'DEV-{number:03d}' for number in range(1, 61)]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    raw = Path(path).read_bytes()
    if not raw or not raw.endswith(b'\n'):
        raise ValueError('Incomplete archived high evidence: ' + str(path))
    return [json.loads(line) for line in raw.splitlines()]


def binding(root, relative, expected=None):
    path = root / relative
    if not path.is_file():
        raise ValueError('Missing archived high source: ' + str(relative))
    digest = sha(path)
    if expected is not None and digest != expected:
        raise ValueError('Archived high source hash differs: ' + str(relative))
    return {'path': str(relative), 'sha256': digest}


def score(attempts, labels):
    if [row['id'] for row in attempts] != IDS:
        raise ValueError('High score has missing, repeated or reordered records')
    valid = [row for row in attempts if row['status'] == 'ok']
    if any(row['prediction'] is None for row in valid):
        raise ValueError('Valid high answer lacks a prediction')
    return {'denominator': 60, 'valid': len(valid),
            'allFour': sum(all(row['prediction'][field] == labels[row['id']][field]
                               for field in FIELDS) for row in valid),
            'invalidIds': [row['id'] for row in attempts if row['status'] != 'ok'],
            'outcomes': dict(Counter(row['status'] for row in attempts))}


def verify_receipt(root, relative, schema, required, bindings):
    receipt = json.loads((root / relative).read_text())
    if receipt.get('schema') != schema or set(receipt.get('source_sha256', {})) != set(required):
        raise ValueError('High closure schema or source set differs: ' + str(relative))
    for name, digest in receipt['source_sha256'].items():
        bindings[name] = binding(root, Path(name), digest)['sha256']
    bindings[str(relative)] = sha(root / relative)
    return receipt


def stage_sources(stage, snapshot, interrupted=False):
    folder = EXECUTION / stage
    names = {str(path) for path in
             (SUCCESSOR / 'proposal.json', EXECUTION / 'manifest.json',
              EXECUTION / 'root-review.json', EXECUTION / stage.split('/')[0] / 'manifest.json',
              Path('scripts/deepseek_high_remaining6_successor_execution_v1.py'),
              folder / 'smoke-inspection.json', snapshot)}
    if not interrupted:
        names.update((str(SUCCESSOR / 'budget.json'), str(LABELS)))
    for phase in ('smoke', 'development'):
        names.update(str(folder / (phase + suffix)) for suffix in
                     ('.claim.json', '.root-review.json', '.journal.jsonl',
                      '.attempts.jsonl', '.responses.jsonl'))
    return names


def raw_phase(root, stage, phase, expected, plan):
    folder = root / EXECUTION / stage
    attempts = rows(folder / (phase + '.attempts.jsonl'))
    raw = rows(folder / (phase + '.responses.jsonl'))
    if len(attempts) != len(expected) or len(raw) != len(expected):
        raise ValueError('High phase attempt or raw count differs: ' + stage)
    for attempt, response, rid, frozen in zip(attempts, raw, expected, plan):
        if (attempt.get('id') != rid or response.get('id') != rid or
                attempt.get('attempt_id') != response.get('attempt_id') or
                attempt.get('request_sha256') != frozen['request_sha256'] or
                response.get('request_sha256') != frozen['request_sha256'] or
                attempt.get('billing_ok') is not True or
                attempt.get('cost_unknown') is not False or
                attempt.get('status') not in ('ok', 'invalid_output') or
                response.get('http_status') != 200 or
                response.get('read_error') is not None or
                response.get('body_truncated_at_limit') is not False):
            raise ValueError('High phase raw or frozen request differs: ' + rid)
        wire = json.loads(base64.b64decode(response['body_base64'], validate=True))
        choice = wire['choices'][0]
        if (choice.get('finish_reason') != attempt.get('finish_reason') or
                attempt.get('raw_response') != wire or
                wire.get('model') != 'deepseek/deepseek-v4.1-flash' or
                wire.get('provider') != 'OpenInference' or
                attempt.get('returned_model') != 'deepseek/deepseek-v4.1-flash' or
                attempt.get('returned_provider') != 'OpenInference'):
            raise ValueError('High model, provider or finish reason differs: ' + rid)
        if attempt['status'] == 'ok' and json.loads(choice['message']['content']) != attempt['prediction']:
            raise ValueError('High raw choice differs from parsed answer: ' + rid)
    return attempts


def ledger_prefix(root, snapshot, attempts):
    raw = (root / snapshot).read_bytes()
    if not raw.endswith(b'\n'):
        raise ValueError('High child prefix is incomplete')
    events = [json.loads(line) for line in raw.splitlines()]
    if events[0] != {'event': 'budget', 'cap_usd': '0.75'} or len(events) != 1 + 2 * len(attempts):
        raise ValueError('High child prefix or event count differs')
    seen = set()
    for index, attempt in enumerate(attempts):
        ident = attempt['attempt_id']
        if ident in seen:
            raise ValueError('High child repeated an attempt')
        seen.add(ident)
        if (events[1 + 2*index] != {'event': 'reserve', 'attempt_id': ident,
                                    'record_id': attempt['id'],
                                    'usd': attempt['reserved_cost_usd']} or
                events[2 + 2*index] != {'event': 'settle', 'attempt_id': ident,
                                        'usd': attempt['observed_cost_usd']}):
            raise ValueError('High child reserve or settlement differs')
    return sha(root / snapshot)


def build(root=ROOT):
    root = Path(root).resolve()
    own = Path('scripts/build_deepseek_high_remaining6_successor_findings.py')
    test = Path('tests/test_build_deepseek_high_remaining6_successor_findings.py')
    if sha(root / own) != sha(__file__) or sha(root / test) != sha(ROOT / test):
        raise ValueError('Loaded high successor reporter differs from selected root')
    bindings = {str(own): sha(root / own), str(test): sha(root / test)}
    label_rows = rows(root / LABELS)
    if [row['id'] for row in label_rows] != IDS or any(row['review_version'] != '0.2' for row in label_rows):
        raise ValueError('Frozen high references differ')
    labels = {row['id']: row['proposed_labels'] for row in label_rows}
    bindings[str(LABELS)] = sha(root / LABELS)
    parent_audit_path = PARENT / 'interruption.audit.json'
    parent_audit = json.loads((root / parent_audit_path).read_text())
    if (parent_audit.get('schema') != 'deepseek-high-remaining7-fresh2-p2-interruption-audit-v1' or
            parent_audit.get('attempted') != 27 or parent_audit.get('planned') != 60 or
            parent_audit.get('child_open_unknown_reserve_usd') != '0.06905856' or
            parent_audit.get('stage_known_cost_usd') != '0.012422496185'):
        raise ValueError('Retained high parent interruption differs')
    bindings[str(parent_audit_path)] = sha(root / parent_audit_path)
    parent_sources = parent_audit['source_sha256']
    expected_parent = {phase + suffix for phase in ('development',)
                       for suffix in ('.attempts.jsonl', '.claim.json', '.journal.jsonl',
                                      '.responses.jsonl', '.root-review.json')} | {'manifest.json'}
    if set(parent_sources) != expected_parent:
        raise ValueError('Retained high parent source set differs')
    parent_unknown = PARENT / 'interruption-unknown-cost-evidence.jsonl'
    parent_snapshot = PARENT / 'interruption-child-ledger-snapshot.jsonl'
    bindings[str(parent_unknown)] = binding(root, parent_unknown,
        parent_audit['unknown_cost_evidence_sha256'])['sha256']
    bindings[str(parent_snapshot)] = binding(root, parent_snapshot,
        parent_audit['child_ledger_snapshot_sha256'])['sha256']
    unknown = rows(root / parent_unknown)
    if (len(unknown) != 1 or unknown[0].get('id') != 'DEV-027' or
            unknown[0].get('cost_unknown') is not True or
            unknown[0].get('reserved_cost_usd') != '0.06905856' or
            unknown[0].get('source_attempts_sha256') !=
            parent_sources['development.attempts.jsonl']):
        raise ValueError('Retained high unknown-cost evidence differs')
    for name, digest in parent_sources.items():
        relative = (BASE / 'execution-adapter-v1/fresh2/manifest.json' if name == 'manifest.json'
                    else PARENT / name)
        # Raw provider errors contain private account identifiers. Keep their
        # audited hashes, verify private bytes when present, and publish only
        # the bounded scoring projection below.
        if name == 'manifest.json':
            bindings[str(relative)] = binding(root, relative, digest)['sha256']
        elif (root / relative).exists():
            binding(root, relative, digest)
    projection_path = PARENT / 'development.public.json'
    projection = json.loads((root / projection_path).read_text())
    if (projection.get('schema') != 'deepseek-high-parent-public-projection-v1' or
            projection.get('source_sha256') != parent_sources):
        raise ValueError('High parent public projection provenance differs')
    projection_receipt_path = PARENT / 'development.public.receipt.json'
    projection_receipt = json.loads((root / projection_receipt_path).read_text())
    if (projection_receipt.get('schema') != 'deepseek-high-parent-public-projection-receipt-v1' or
            projection_receipt.get('projection_sha256') != sha(root / projection_path) or
            projection_receipt.get('source_attempts_sha256') !=
            parent_sources['development.attempts.jsonl'] or
            projection_receipt.get('parent_audit_sha256') != sha(root / parent_audit_path) or
            projection_receipt.get('verified_against_private_originals') is not True or
            projection_receipt.get('projected_attempts') != 27 or
            projection_receipt.get('valid') != 26 or
            projection_receipt.get('unknown_ids') != ['DEV-027']):
        raise ValueError('High parent public projection receipt differs')
    bindings[str(projection_receipt_path)] = sha(root / projection_receipt_path)
    parent = projection['attempts']
    public_keys = {'id', 'status', 'prediction', 'cost_unknown', 'observed_cost_usd'}
    if any(set(row) != public_keys for row in parent):
        raise ValueError('High parent public projection fields differ')
    private_attempts = root / PARENT / 'development.attempts.jsonl'
    if private_attempts.exists():
        expected = [{key: row.get(key) for key in public_keys}
                    for row in rows(private_attempts)]
        if parent != expected:
            raise ValueError('High parent projection differs from private attempts')
    bindings[str(projection_path)] = sha(root / projection_path)
    if ([row['id'] for row in parent] != IDS[:27] or
            [row['status'] for row in parent] != ['ok'] * 26 + ['service_error'] or
            parent[-1].get('cost_unknown') is not True or
            parent[-1].get('observed_cost_usd') is not None):
        raise ValueError('High parent attempted IDs or unknown outcome differ')
    all_attempts = []
    phases = {}
    stage_predictions = {}
    stage_requests = {}
    stage_controls = {}
    for repeat, condition, length in STAGES:
        stage = repeat + '/' + condition
        folder = EXECUTION / stage
        interrupted = stage == 'fresh2/P2'
        snapshot = SUCCESSOR / ('budget-at-fresh2-p2-suffix-closure.jsonl'
            if interrupted else f'budget-at-{repeat}-{condition.lower()}-closure.jsonl')
        receipt_path = (SUCCESSOR / 'fresh2-p2-suffix-closure.review.json' if interrupted
                        else folder / 'closure.review.json')
        required = stage_sources(stage, snapshot, interrupted)
        if interrupted:
            required.update(str(path) for path in (parent_audit_path,
                BASE / 'reconciliation-after-dev027.json'))
        receipt = verify_receipt(root, receipt_path,
            ('deepseek-high-remaining6-fresh2-p2-suffix-closure-v1' if interrupted
             else 'deepseek-high-remaining6-successor-phase-closure-v1'), required, bindings)
        plan = json.loads((root / EXECUTION / repeat / 'manifest.json').read_text())
        frozen = plan['conditions'][condition]
        expected = IDS[27:] if interrupted else IDS
        if [item['record_id'] for item in frozen['development']] != expected:
            raise ValueError('High successor plan IDs differ: ' + stage)
        smoke = raw_phase(root, stage, 'smoke', expected[:3], frozen['smoke'])
        development = raw_phase(root, stage, 'development', expected, frozen['development'])
        if len(development) != length or any(row['status'] != 'ok' for row in smoke):
            raise ValueError('High successor phase length or smoke differs')
        all_attempts.extend(smoke + development)
        stage_predictions[stage] = {row['id']: row['prediction'] for row in development if row['status'] == 'ok'}
        stage_requests[stage] = [row['request_sha256'] for row in frozen['development']]
        controls = json.loads(json.dumps([row['payload'] for row in frozen['development']]))
        for payload in controls:
            if payload['messages'][0]['role'] != 'system':
                raise ValueError('Expected a separate system prompt')
            payload['messages'][0]['content'] = '<declared prompt condition>'
        stage_controls[stage] = controls
        if ledger_prefix(root, snapshot, all_attempts) != receipt['snapshot_sha256']:
            raise ValueError('High child snapshot receipt differs')
        scored = score(parent + development if interrupted else development, labels)
        known = sum((Decimal(row['observed_cost_usd']) for row in development), Decimal(0))
        if interrupted:
            if (scored['valid'] != 59 or scored['invalidIds'] != ['DEV-027'] or
                    receipt.get('clean_full_phase') is not False or
                    receipt.get('full_60_clean_score') is not None or
                    receipt.get('descriptive_combined_development_known_cost_usd') !=
                    str(Decimal(parent_audit['stage_known_cost_usd']) + known)):
                raise ValueError('Interrupted high composite was promoted or miscosted')
            status = 'interrupted_composite_descriptive_only'
            known = Decimal(parent_audit['stage_known_cost_usd']) + known
        else:
            if (receipt.get('status') != 'closed' or receipt.get('score') !=
                    {**receipt['score'], 'denominator': scored['denominator'],
                     'valid': scored['valid'], 'allFour': scored['allFour'],
                     'invalidIds': scored['invalidIds'], 'outcomes': scored['outcomes']} or
                    receipt.get('development_known_cost_usd') != str(known)):
                raise ValueError('Clean high successor closure score differs')
            status = 'completed_with_intrinsic_invalid' if scored['invalidIds'] else 'completed'
        phases[stage] = {'status': status, 'score': scored,
                         'knownDevelopmentCostUsd': str(known),
                         'unknownCostUpperBoundUsd': '0.06905856' if interrupted else '0',
                         'smokeCostExcluded': True,
                         'fieldCorrect': {field: sum(row['prediction'][field] == labels[row['id']][field]
                            for row in (parent + development if interrupted else development)
                            if row['status'] == 'ok') for field in FIELDS},
                         'closureReceiptSha256': bindings[str(receipt_path)]}
    p1_before, p1_after = stage_predictions['fresh2/P1'], stage_predictions['fresh3/P1']
    if stage_requests['fresh2/P1'] != stage_requests['fresh3/P1']:
        raise ValueError('P1 repeat request bytes differ')
    p1_changed = [rid for rid in IDS if p1_before[rid] != p1_after[rid]]
    if stage_controls['fresh3/P1'] != stage_controls['fresh3/P2']:
        raise ValueError('Prompt comparison differs beyond system instructions')
    prompt_changed = [rid for rid in IDS if
        stage_predictions['fresh3/P1'][rid] != stage_predictions['fresh3/P2'][rid]]
    return {'schema': 'deepseek-high-remaining6-successor-findings-v1',
            'configuration': 'openrouter-paid-deepseek-v41-flash-high-authority-v3-current-price-remaining7-price-v1',
            'continuation': 'exact-unsent DEV-028–DEV-060, then later full stages',
            'publishedClosedStages': [repeat + '/' + condition for repeat, condition, _ in STAGES],
            'plannedRemainingStages': ['fresh2/P2', 'fresh2/P0', 'fresh2/P1',
                                       'fresh3/P1', 'fresh3/P2', 'fresh3/P0'],
            'phases': phases,
            'matchedCleanRepeatEligible': False,
            'p1TwoPassRepeat': {'passes': ['fresh2/P1', 'fresh3/P1'], 'denominator': 60,
                'changedRecordIds': p1_changed, 'changedRecords': len(p1_changed),
                'allFourScores': [phases[stage]['score']['allFour'] for stage in ('fresh2/P1','fresh3/P1')]},
            'fresh3PromptChange': {'conditions': ['P1','P2'], 'denominator': 60,
                'changedRecordIds': prompt_changed, 'changedRecords': len(prompt_changed),
                'allFourScores': [phases['fresh3/'+c]['score']['allFour'] for c in ('P1','P2')]},
            'referenceStatus': 'Frozen provisional v0.2 development labels; owner-confirmed human checks on 2026-10-02, without independent adjudication.',
            'limitations': ['The interrupted P2 composite retains DEV-027 as a provider failure with unknown cost.',
                            'All phases reuse the same 60 synthetic reviews.',
                            'The interrupted parent uses a receipt-bound public projection; private provider errors are not re-decoded in clean checkouts.',
                            'The interrupted P2 and intrinsic-invalid P0 do not form a clean matched prompt comparison.'],
            'sourceBindings': [{'path': name, 'sha256': digest}
                               for name, digest in sorted(bindings.items())]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    content = json.dumps(build(), indent=2, ensure_ascii=False) + '\n'
    target = ROOT / OUTPUT
    if args.check:
        if target.read_text() != content:
            raise ValueError('High successor public report is stale')
    else:
        target.write_text(content)
    print(sha(target))


if __name__ == '__main__':
    main()
