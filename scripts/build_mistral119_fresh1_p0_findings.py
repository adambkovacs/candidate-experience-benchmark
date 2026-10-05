#!/usr/bin/env python3
"""Build the public, offline Mistral119 fresh1/P0 partial findings projection."""
from collections import Counter
from decimal import Decimal
from datetime import datetime
import hashlib
import json
from pathlib import Path

import build_repeat_findings as shared
from development_benchmark import valid
import mistral119_fresh_repeat_study as study
import mistral119_fresh_repeat_execution as execution
import mistral119_v3_smoke as smoke

ROOT = Path(__file__).resolve().parents[1]
SERIES = Path('results/repeatability-v1/mistral119-fresh-matched3-v1')
BASE = SERIES / 'v3-development-none-v1/fresh1/P0'
FOURTH = SERIES / 'v5-fourth-suffix-none-v1/fresh1/P0'
OUT = Path('public-site/mistral119-fresh1-p0-findings.json')
SCHEMA = 'mistral119-fresh1-p0-partial-findings-v1'
IDS = [f'DEV-{i:03d}' for i in range(1, 61)]
FIELDS = ('sentiment', 'follow_up_needed', 'serious_concern_reported',
          'testimonial_potential')
LABELS_PATH = Path('data/pilot/proposed_labels.jsonl')
PLAN_STARTS = (0, 48, 50, 53, 58)

STAGES = (
    (BASE, 'development', IDS[:48], ['DEV-048']),
    (SERIES / 'v3-remaining-none-v1/fresh1/P0-suffix-049-060', 'suffix',
     IDS[48:50], ['DEV-050']),
    (SERIES / 'v3-second-suffix-none-v1/fresh1/P0', 'suffix',
     IDS[50:53], ['DEV-053']),
    (SERIES / 'v3-third-suffix-none-v1/fresh1/P0', 'suffix',
     IDS[53:58], ['DEV-058']),
    (FOURTH, 'suffix', IDS[58:60], ['DEV-060']),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    return json.loads((ROOT / path).read_text())


def read_rows(path):
    return [json.loads(line) for line in (ROOT / path).read_text().splitlines()
            if line.strip()]


def bind(path):
    return {'path': path.as_posix(), 'sha256': sha(ROOT / path)}


def portable_source_path(value):
    """Resolve archived absolute references inside the current repository."""
    path = Path(value)
    if not path.is_absolute():
        return ROOT / path
    try:
        return ROOT / path.resolve().relative_to(ROOT.resolve())
    except ValueError:
        anchors = {'results', 'scripts', 'tests', 'data', 'docs', 'public-site'}
        for index, part in enumerate(path.parts):
            if part in anchors:
                return ROOT.joinpath(*path.parts[index:])
    raise ValueError(f'Absolute evidence path has no portable repository suffix: {value}')


def verify_reconciled_child(base, reconciliation, budget_manifest_name):
    """Verify a sealed ledger via its stage-local basename, never its old host path."""
    budget = read_json(base / budget_manifest_name)
    partitions = budget.get('partitions')
    if not isinstance(partitions, list) or len(partitions) != 1:
        raise ValueError('Expected one exact child partition')
    partition = partitions[0]
    child_name = Path(partition.get('child_ledger', '')).name
    expected_name = f'{Path(budget_manifest_name).stem}-{partition.get("id")}.jsonl'
    if (not child_name or child_name != expected_name or
            Path(reconciliation.get('child_ledger', '')).name != expected_name):
        raise ValueError('Reconciliation child name differs from reviewed stage manifest')
    local_child = ROOT / base / child_name
    if not local_child.is_file() or sha(local_child) != reconciliation.get('child_sha256'):
        raise ValueError('Stage-local reconciled child hash differs')
    return local_child


def verify_named_sources(base, terminal):
    """Check every portable source entry carried by the reviewed terminals."""
    hashes = terminal.get('sourceSha256', terminal.get('source_sha256', {}))
    for name, value in hashes.items():
        if (name in ('child_ledger', 'master_ledger', 'global_authority') or
                name.startswith('suffix.budget-manifest-') and name.endswith('.jsonl')):
            continue
        if isinstance(value, dict):
            digest = value['sha256']
            path = portable_source_path(value['path'])
        else:
            digest = value
            if name.startswith('mistral119_'):
                path = ROOT / 'scripts' / name
            elif name.startswith('build_mistral119_') or name.startswith('test_build_mistral119_'):
                path = ROOT / ('scripts' if name.startswith('build_') else 'tests') / name
            else:
                path = ROOT / base / name
                if not path.is_file() and (ROOT / base / ('suffix.' + name)).is_file():
                    path = ROOT / base / ('suffix.' + name)
        if not path.is_file() or sha(path) != digest:
            raise ValueError(f'Sealed terminal source changed: {name}')


def build():
    """Read only sealed stage data; never invokes a terminal proposal builder."""
    outcomes = {}
    predictions = {}
    attempts_all = []
    bindings = []
    stage_counts = []

    for index, (base, phase, expected_attempted, expected_failed) in enumerate(STAGES):
        terminal_path = (base / ('development.terminal-public.json' if index == 0 else
                                 'suffix.terminal-public.json'))
        if index == 3:
            terminal_path = base / 'suffix.third-terminal-pending-review.json'
        if index == 4:
            terminal_path = base / 'suffix.fourth-terminal-pending-review.json'
        terminal = read_json(terminal_path)
        verify_named_sources(base, terminal)
        manifest_path = base / 'manifest.json'
        manifest = read_json(manifest_path)
        plan = study.verify(smoke.CONFIG, 'fresh1', smoke.PLAN_SHA)
        execution.runner.verify_execution_manifest(smoke.EXECUTION_SHA)
        plan_requests = plan['conditions']['P0']['development']
        start = PLAN_STARTS[index]
        manifest_requests = manifest.get('requests', manifest.get('suffix_requests'))
        expected_manifest_requests = plan_requests[start:]
        if (manifest.get('configuration_id') != smoke.CONFIG or
                manifest.get('fresh_pass') != 'fresh1' or
                manifest.get('condition') != 'P0' or
                manifest.get('phase') != phase or
                manifest.get('reference_labels_read') is not False or
                manifest.get('frozen_plan_sha256') != smoke.PLAN_SHA or
                manifest.get('frozen_execution_manifest_sha256') != smoke.EXECUTION_SHA or
                manifest.get('input_file_sha256') != study.sha(ROOT / study.INPUTS) or
                manifest_requests != expected_manifest_requests):
            raise ValueError(f'Frozen stage manifest differs from admitted P0 plan: {manifest_path}')
        for source, digest in manifest.get('source_sha256', {}).items():
            if sha(ROOT / source) != digest:
                raise ValueError(f'Stage manifest source changed: {source}')
        if index == 0 and (manifest.get('schema') != 'mistral119-none-v3-fresh1-p0-development-v1' or
                           manifest.get('ids') != IDS or manifest.get('request_count') != len(IDS)):
            raise ValueError('Initial development manifest roster differs')
        manifest_ids = [row.get('record_id') for row in manifest_requests]
        if manifest_ids != IDS[start:]:
            raise ValueError(f'Stage manifest has wrong frozen suffix positions: {manifest_path}')
        terminal_bindings = terminal.get('source_sha256', terminal.get('sourceSha256', {}))

        source_names = {
            f'{phase}.attempts.jsonl': base / f'{phase}.attempts.jsonl',
            f'{phase}.parsed.jsonl': base / f'{phase}.parsed.jsonl',
            f'{phase}.journal.jsonl': base / f'{phase}.journal.jsonl',
        }
        for name, path in source_names.items():
            short_name = name.removeprefix(phase + '.')
            entry = terminal_bindings.get(name, terminal_bindings.get(short_name))
            if isinstance(entry, dict):
                entry = entry.get('sha256')
            if entry != sha(ROOT / path):
                raise ValueError(f'Terminal does not bind {path}')
            bindings.append(bind(path))
        attempts = read_rows(source_names[f'{phase}.attempts.jsonl'])
        parsed = read_rows(source_names[f'{phase}.parsed.jsonl'])
        journal = read_rows(source_names[f'{phase}.journal.jsonl'])
        frozen_hashes = {row['record_id']: row['request_sha256']
                         for row in manifest_requests}
        started_hashes = {row.get('id'): row.get('request_sha256') for row in journal
                          if row.get('event') == 'request_started'}
        if any(started_hashes.get(rid) != frozen_hashes.get(rid)
               for rid in [row['id'] for row in attempts]):
            raise ValueError(f'Attempted request differs from frozen manifest: {base}')
        attempted_ids = [row.get('id') for row in attempts]
        failed_ids = expected_failed
        valid_ids = [rid for rid in attempted_ids if rid not in failed_ids]
        if (attempted_ids != expected_attempted or
                [row.get('id') for row in parsed] != valid_ids):
            raise ValueError(f'Unexpected ordered attempts or valid output in {base}')
        if (any(row.get('status') != 'ok' or row.get('cost_unknown') is not False
                for row in attempts if row.get('id') in valid_ids) or
                any(row.get('status') not in ('unknown_cost', 'transport_error') or
                    row.get('cost_unknown') is not True or
                    (row.get('http_status') not in (None, 429))
                    for row in attempts if row.get('id') in failed_ids)):
            raise ValueError(f'Attempt status or unknown billing differs in {base}')
        if index == 0:
            if (terminal.get('valid_count') != 47 or terminal.get('unknown_id') != 'DEV-048' or
                    terminal.get('status') != 'interrupted_unscored'):
                raise ValueError('Initial development terminal differs')
        elif index == 3:
            root_review = read_json(base / 'suffix.third-terminal-root-review.json')
            if (terminal.get('approved') is not False or
                    terminal.get('stage', {}).get('valid_ids') != valid_ids or
                    terminal.get('stage', {}).get('failed_id') != 'DEV-058' or
                    root_review.get('approved') is not True or
                    root_review.get('proposal_sha256') != sha(ROOT / terminal_path)):
                raise ValueError('Third suffix reviewed boundary differs')
            recon = read_json(base / 'suffix.third-budget-reconciliation.json')
            if (recon.get('event') != 'partition_reconciled' or
                    recon.get('unknown_upper_bound_usd') != '0.04177920' or
                    'do not replay' not in root_review.get('decision', '').lower() or
                    not verify_reconciled_child(base, recon,
                                                'suffix.budget-manifest.json')):
                raise ValueError('Third suffix reconciliation differs')
            bindings.extend(bind(base / name) for name in
                            ('suffix.third-terminal-pending-review.json',
                             'suffix.third-terminal-root-review.json',
                             'suffix.third-budget-reconciliation.json',
                             'suffix.budget-manifest.json'))
        elif index == 4:
            root_review = read_json(base / 'suffix.fourth-terminal-root-review.json')
            recon = read_json(base / 'suffix.fourth-budget-reconciliation.json')
            if (terminal.get('status') != 'stopped_pending_reconciliation' or
                    terminal.get('composite', {}).get('valid') != 55 or
                    terminal.get('composite', {}).get('failed_ids') !=
                    ['DEV-048', 'DEV-050', 'DEV-053', 'DEV-058', 'DEV-060'] or
                    terminal.get('child_sealed') is not False or
                    root_review.get('approved') is not True or
                    root_review.get('verdict') != 'APPROVE' or
                    root_review.get('proposal_sha256') != sha(ROOT / terminal_path) or
                    root_review.get('retain_unknown_usd') != '0.04177920' or
                    root_review.get('retry_allowed') is not False or
                    recon.get('event') != 'partition_reconciled' or
                    recon.get('known_actual_usd') != '0.00023835' or
                    recon.get('unknown_upper_bound_usd') != '0.04177920' or
                    recon.get('unused_allocation_released_usd') != '0.04798245' or
                    not verify_reconciled_child(base, recon,
                                                'suffix.budget-manifest.json')):
                raise ValueError('Fourth suffix review or reconciliation differs')
            for name in ('suffix.fourth-terminal-pending-review.json',
                         'suffix.fourth-terminal-root-review.json',
                         'suffix.fourth-budget-reconciliation.json',
                         'suffix.budget-manifest.json'):
                bindings.append(bind(base / name))
        else:
            if terminal.get('valid_ids') != valid_ids or terminal.get('failed_id') != failed_ids[0]:
                raise ValueError(f'Sealed suffix terminal differs in {base}')
            reconciliation = base / 'suffix.budget-reconciliation.json'
            if reconciliation.is_file():
                bindings.append(bind(reconciliation))

        for row in attempts:
            rid = row['id']
            if rid in failed_ids:
                outcomes[rid] = 'failed_unknown_cost'
                attempts_all.append(row)
            else:
                outcomes[rid] = 'valid'
                attempts_all.append(row)
        for row in parsed:
            prediction = row.get('prediction')
            if not valid(prediction):
                raise ValueError(f'Invalid stored classification: {row["id"]}')
            predictions[row['id']] = prediction
        stage_counts.append({'phase': phase, 'path': base.as_posix(),
                             'attempted': len(attempts), 'valid': len(parsed),
                             'failed': len(failed_ids)})
        bindings.append(bind(terminal_path))
        bindings.append(bind(manifest_path))

    if (len(outcomes) != 60 or len(predictions) != 55 or
            [rid for rid in IDS if rid in outcomes] != IDS):
        raise ValueError('Composite fixed-60 accounting differs')
    failed_ids = [rid for rid in IDS if outcomes[rid] != 'valid']
    if failed_ids != ['DEV-048', 'DEV-050', 'DEV-053', 'DEV-058', 'DEV-060']:
        raise ValueError('Failure membership changed')

    labels_rows = read_rows(LABELS_PATH)
    if (sha(ROOT / LABELS_PATH) != shared.PINNED_SHA[str(LABELS_PATH)] or
            [row.get('id') for row in labels_rows] != IDS):
        raise ValueError('Frozen review v0.2 roster differs')
    if any(row.get('review_version') != '0.2' or
           row.get('review_status') != 'ai_reviewed_provisional' or
           row.get('reviewer_labels') is not None for row in labels_rows):
        raise ValueError('Frozen proposed-label review version differs')
    labels = {row['id']: row['proposed_labels'] for row in labels_rows}
    if any(not valid(labels[rid]) for rid in IDS):
        raise ValueError('Frozen review labels are invalid')

    field_matches = Counter()
    confusion = {field: Counter() for field in FIELDS}
    all_four = 0
    for rid, prediction in predictions.items():
        matched = 0
        for field in FIELDS:
            expected, observed = labels[rid][field], prediction[field]
            confusion[field][(expected, observed)] += 1
            if expected == observed:
                field_matches[field] += 1
                matched += 1
        all_four += matched == len(FIELDS)

    costs = [Decimal(str(row['actual_cost_usd'])) for row in attempts_all
             if row.get('status') == 'ok' and row.get('actual_cost_usd') is not None]
    unknown_bound = sum((Decimal(str(row['reserved_cost_usd'])) for row in attempts_all
                         if row.get('cost_unknown') is True), Decimal(0))
    prompt_tokens = sum(int(row['usage']['prompt_tokens']) for row in
                        [r for base, phase, ids, fails in STAGES
                         for r in read_rows(base / f'{phase}.parsed.jsonl')])
    completion_tokens = sum(int(row['usage']['completion_tokens']) for row in
                            [r for base, phase, ids, fails in STAGES
                             for r in read_rows(base / f'{phase}.parsed.jsonl')])
    total_tokens = sum(int(row['usage']['total_tokens']) for row in
                       [r for base, phase, ids, fails in STAGES
                        for r in read_rows(base / f'{phase}.parsed.jsonl')])
    latencies = []
    for base, phase, attempted, failed in STAGES:
        journal = read_rows(base / f'{phase}.journal.jsonl')
        starts = {row.get('id'): row['utc'] for row in journal
                  if row.get('event') == 'request_started' and row.get('utc')}
        ends = {row.get('id'): row['utc'] for row in journal
                if row.get('event') == 'request_finished' and row.get('utc')}
        for rid in attempted:
            if rid in starts and rid in ends:
                elapsed = (datetime.fromisoformat(ends[rid].replace('Z', '+00:00')) -
                           datetime.fromisoformat(starts[rid].replace('Z', '+00:00')))
                latencies.append(elapsed.total_seconds())
    if len(latencies) != 55:
        raise ValueError('Expected one finished-request timing for each valid output')
    ordered_latency = sorted(latencies)
    for path in (LABELS_PATH, Path('data/pilot/inputs.jsonl')):
        bindings.append(bind(path))

    public = {
        'schema': SCHEMA,
        'status': 'partial_unscored_as_repeat',
        'configurationId': 'openrouter-paid-mistral-small4-119b-none',
        'freshPass': 'fresh1', 'condition': 'P0',
        'denominator': 60,
        'outcomes': {'valid': 55, 'failed': 5, 'neverSent': 0,
                     'failedIds': failed_ids},
        'scoring': {
            'reference': 'proposed_labels.jsonl review_version 0.2, offline only',
            'referenceStatus': 'Frozen v0.2 labels remain provisional. Project owner confirmed human review of all 60 labels on 2026-10-02. This report applies no label corrections.',
            'scoredValidCount': 55,
            'allFourMatches': all_four,
            'allFourDenominator': 60,
            'allFourMatchRate': round(all_four / 60, 6),
            'allFourAmongValid': round(all_four / len(predictions), 6),
            'fieldMatches': {field: field_matches[field] for field in FIELDS},
            'confusionMatrices': {
                field: {expected: {observed: confusion[field][(expected, observed)]
                                   for observed in sorted({v for e, v in confusion[field]})}
                        for expected in sorted({e for e, v in confusion[field]})}
                for field in FIELDS},
            'failedPositionsExcludedFromScoring': failed_ids,
        },
        'usage': {'validOutputs': len(predictions),
                  'promptTokens': prompt_tokens,
                  'completionTokens': completion_tokens,
                  'totalTokens': total_tokens,
                  'observedKnownCostUsd': str(sum(costs, Decimal(0))),
                  'unknownChargeUpperBoundUsd': str(unknown_bound),
                  'unknownChargeFailedIds': failed_ids,
                  'tokenObservedCount': len(predictions),
                  'tokenMissingFailedIds': failed_ids,
                  'knownCostObservedCount': len(costs),
                  'knownCostMissingFailedIds': failed_ids},
        'timing': {'finishedRequestsMeasured': len(latencies),
                   'failedRequestsWithoutFinishedTiming': len(failed_ids),
                   'finishedRequestElapsedSeconds': {
                       'total': round(sum(latencies), 3),
                       'median': round(ordered_latency[len(ordered_latency) // 2], 3),
                       'min': round(ordered_latency[0], 3),
                       'max': round(ordered_latency[-1], 3)},
                   'interpretation': 'Wall time from request_started to request_finished in saved journals; host sleep overlap is not removed.'},
        'lineage': {'stages': stage_counts,
                    'referenceLabelsSent': False,
                    'cleanRepeatabilityClaim': False,
                    'sourceBindings': sorted(bindings, key=lambda item: item['path'])},
    }
    return public


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True, indent=2))
