#!/usr/bin/env python3
"""Build a portable, public-only DeepSeek-low third interruption view."""

import argparse
from collections import Counter
import copy
from decimal import Decimal
import hashlib
import json
from pathlib import Path

import build_deepseek_low_interruption_findings as prior

ROOT = Path(__file__).resolve().parents[1]
NEW = prior.BASE / 'second-interruption-continuation-v1'
MANIFEST_SHA = 'd1f051e73960ee936d645989105caf6a8e0c1c5a4461958fc7b9a3d1e51f2e98'
SNAPSHOT_SHA = '8d2814c5c58f695f7741897fdbf7db2308e4344d5b95c8bfe5b25dbf283f5346'
STAGE_SHA = {
    'phase-03-suffix.root-review.json': 'eee40e63d99a7e56f7abea4450a925e153b641c3ca0d89e359ec9cf4766c6545',
    'phase-03-suffix.claim.json': 'c7252b56b5ec726a1120bcd1ecc93572f51906f2fd470618dc09b2bba662a515',
    'phase-03-suffix.journal.jsonl': '578416709022651b60b2bf13489dde53087bb4dcb04b021120459d63d39be3d2',
    'phase-03-suffix.records.jsonl': '0323e2d38b9e89c43651fd174d8c9a784f8fda39a2d4be78f78f8c12a9c8067f',
    'terminal-reconciliation-after-dev050.json': 'afebe495074a2af03da0e2516d921fb40c04f4a32c359fa117443884a688af30',
}
PRIVATE_SOURCES = {'first_suffix_journal', 'first_suffix_raw', 'first_suffix_records',
                   'original_failed_claim', 'original_failed_journal',
                   'original_failed_raw', 'original_failed_records'}
SCHEMA = 'deepseek-low-third-interruption-findings-v1'
SERIES = 'openrouter-paid-deepseek-v41-flash-low-descriptive-continuation-v2'
RESERVE = '0.1069056'
IDS = [f'DEV-{i:03d}' for i in range(1, 61)]


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bound(root, relative, expected, bindings):
    path = prior.file(root, relative)
    if _sha(path) != expected:
        raise ValueError(f'Source hash differs: {relative}')
    item = {'path': str(relative), 'sha256': expected}
    if item not in bindings:
        bindings.append(item)
    return json.loads(path.read_text()) if path.suffix == '.json' else path


def _jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def _public_projection(row):
    result = {key: row[key] for key in ('id', 'status', 'prediction', 'observed_cost_usd',
            'cost_unknown', 'unknown_upper_bound_usd', 'usage',
            'client_http_duration_seconds', 'http_status') if key in row}
    usage = result.get('usage') or {}
    result['usage'] = {key: usage[key] for key in ('prompt_tokens', 'completion_tokens')
                       if key in usage}
    return result


def build(root=ROOT):
    root = Path(root).resolve()
    result = copy.deepcopy(prior.build(root))
    if len(result['series']) != 1:
        raise ValueError('Prior public series differs')
    series = result['series'][0]
    prior_checkpoint = series.get('secondInterruptionCheckpoint')
    if (series.get('continuationStatus') != 'suffix_stopped_at_DEV-049_unscored' or
            not isinstance(prior_checkpoint, dict) or
            prior_checkpoint.get('attemptedAtSecondInterruption') != 49 or
            series.get('completedConditions') != 2 or
            'P2' in series.get('passes', {}).get('fresh1', {})):
        raise ValueError('Prior interruption history differs')
    bindings = result['sourceBindings']
    manifest = _bound(root, NEW / 'manifest.json', MANIFEST_SHA, bindings)
    old_manifest = json.loads(prior.file(root, prior.NEW / 'manifest.json').read_text())
    if (manifest.get('schema') != 'deepseek-low-second-interruption-v1' or
            manifest.get('status') != 'FROZEN' or
            manifest.get('method') != 'descriptive-second-interruption-continuation' or
            manifest.get('configuration_id') != series['configuration'] or
            manifest.get('clean_matched_three_eligible') is not False or
            manifest.get('reference_labels_read') is not False or
            manifest.get('requests_by_condition') != old_manifest['requests_by_condition'] or
            manifest.get('phases') != old_manifest['phases'] or
            manifest.get('route') != old_manifest['route'] or
            manifest.get('original_failed_id') != 'DEV-040' or
            manifest.get('first_suffix_failed_id') != 'DEV-049' or
            manifest.get('original_invalid_id') != 'DEV-039' or
            manifest.get('reserve_usd') != RESERVE or
            manifest.get('output_directory') != str(NEW)):
        raise ValueError('Frozen third-interruption plan differs')
    sources = manifest.get('source_bindings')
    if not isinstance(sources, dict) or set(sources) != set(EXPECTED_SOURCES):
        raise ValueError('Third-interruption source inventory differs')
    for name, source in sources.items():
        if (not isinstance(source, dict) or set(source) != {'path', 'sha256'} or
                source['path'] != EXPECTED_SOURCES[name] or
                not isinstance(source['sha256'], str) or len(source['sha256']) != 64):
            raise ValueError(f'Third-interruption source binding differs: {name}')
        if name not in PRIVATE_SOURCES:
            _bound(root, source['path'], source['sha256'], bindings)
    controller = manifest.get('controller')
    if controller != {'path': 'scripts/deepseek_low_second_interruption.py',
                       'sha256': '21c7f6c665019f80fa72699abc3af3e3df50e56c643082fa81f585dfb87f4737'}:
        raise ValueError('Third-interruption controller differs')
    _bound(root, controller['path'], controller['sha256'], bindings)
    snapshot = _bound(root, NEW / 'phase-03-suffix.public.json', SNAPSHOT_SHA, bindings)
    if (snapshot.get('schema') != 'deepseek-low-second-interruption-v1-suffix-projection' or
            snapshot.get('status') != 'stopped' or
            snapshot.get('method') != manifest['method'] or
            snapshot.get('denominator') != 60 or
            snapshot.get('clean_matched_three_eligible') is not False or
            snapshot.get('manifest_sha256') != MANIFEST_SHA or
            snapshot.get('source_hashes') != {k: v['sha256'] for k, v in sources.items()} or
            snapshot.get('attempted_count') != 50 or
            snapshot.get('never_sent_count') != 10 or
            snapshot.get('status_counts') != {'ok': 46, 'invalid_output': 1,
                                             'service_error': 3, 'never_sent': 10} or
            snapshot.get('new_known_actual_usd') != '0' or
            snapshot.get('new_unknown_charge_upper_bound_usd') != RESERVE or
            snapshot.get('new_pending_unknown_reserve_usd') != '0'):
        raise ValueError('Third-interruption projection differs')
    positions = snapshot.get('positions')
    if (not isinstance(positions, list) or len(positions) != 60 or
            [p.get('id') for p in positions] != IDS or
            dict(Counter(p.get('status') for p in positions)) != snapshot['status_counts'] or
            [p['id'] for p in positions if p['status'] == 'invalid_output'] != ['DEV-039'] or
            [p['id'] for p in positions if p['status'] == 'service_error'] !=
                ['DEV-040', 'DEV-049', 'DEV-050'] or
            any(p != {'id': IDS[i], 'status': 'never_sent'} for i, p in enumerate(positions)
                if i >= 50)):
        raise ValueError('Third-interruption positions differ')
    first = json.loads(prior.file(root, prior.NEW / 'phase-03-suffix.public.json').read_text())
    if [_public_projection(p) for p in positions[:49]] != [
            _public_projection(p) for p in first['positions'][:49]]:
        raise ValueError('Earlier public positions changed')
    last = positions[49]
    if (last != {'id': 'DEV-050', 'status': 'service_error',
                 'observed_cost_usd': None, 'cost_unknown': True,
                 'unknown_upper_bound_usd': RESERVE, 'usage': {},
                 'client_http_duration_seconds': 1.0913627079571597,
                 'http_status': 429}):
        raise ValueError('DEV-050 public outcome differs')
    review = _bound(root, NEW / 'phase-03-suffix.root-review.json',
                    STAGE_SHA['phase-03-suffix.root-review.json'], bindings)
    claim = _bound(root, NEW / 'phase-03-suffix.claim.json',
                   STAGE_SHA['phase-03-suffix.claim.json'], bindings)
    journal = _jsonl(_bound(root, NEW / 'phase-03-suffix.journal.jsonl',
                    STAGE_SHA['phase-03-suffix.journal.jsonl'], bindings))
    records = _jsonl(_bound(root, NEW / 'phase-03-suffix.records.jsonl',
                    STAGE_SHA['phase-03-suffix.records.jsonl'], bindings))
    budget_path = NEW / ('budget-' + manifest['partition_id'] + '.jsonl')
    budget = _jsonl(_bound(root, budget_path, _sha(prior.file(root, budget_path)), bindings))
    terminal = _bound(root, NEW / 'terminal-reconciliation-after-dev050.json',
            STAGE_SHA['terminal-reconciliation-after-dev050.json'], bindings)
    budget_manifest = json.loads(prior.file(root, sources['new_budget_manifest']['path']).read_text())
    original_origin = Path(budget_manifest.get('master_ledger', '')).parent.parent
    expected_child = str(original_origin / budget_path)
    if (not original_origin.is_absolute() or
            budget_manifest.get('master_ledger') != str(original_origin / 'results/openrouter-paid-budget.jsonl') or
            budget_manifest.get('version') != 'paid-partitions-v1' or
            budget_manifest.get('partitions') != [{
                'id': manifest['partition_id'], 'cap_usd': manifest['child_cap_usd'],
                'model': series['model'], 'provider': series['provider'],
                'reasoning': 'low', 'child_ledger': expected_child}] or
            terminal.get('child_ledger') != expected_child or
            budget[2].get('evidence_path') != str(original_origin / NEW / 'phase-03-suffix.records.jsonl') or
            budget[0].get('cap_usd') != manifest['child_cap_usd'] or
            Decimal(str(terminal.get('unused_allocation_released_usd'))) !=
                Decimal(manifest['child_cap_usd']) - Decimal(RESERVE)):
        raise ValueError('Third-interruption original budget metadata differs')
    expected_request = manifest['requests_by_condition']['P2'][49]
    if (review.get('schema') != 'deepseek-low-second-interruption-v1-stage-review' or
            review.get('approved') is not True or review.get('manifest_sha256') != MANIFEST_SHA or
            review.get('controller_sha256') != controller['sha256'] or
            review.get('first_terminal_reconciliation_sha256') !=
                sources['first_terminal_reconciliation']['sha256'] or
            review.get('new_budget_manifest_sha256') != sources['new_budget_manifest']['sha256'] or
            review.get('ids') != IDS[49:] or
            review.get('partition_id') != manifest['partition_id'] or
            claim.get('schema') != 'deepseek-low-second-interruption-v1-stage-claim' or
            claim.get('review_sha256') != STAGE_SHA['phase-03-suffix.root-review.json'] or
            claim.get('manifest_sha256') != MANIFEST_SHA or
            claim.get('ids') != IDS[49:] or
            claim.get('partition_id') != manifest['partition_id'] or
            [e.get('event') for e in journal] != ['stage_claimed', 'request_started',
                'raw_saved', 'request_finished', 'stage_stopped'] or
            journal[0].get('claim_sha256') != STAGE_SHA['phase-03-suffix.claim.json'] or
            journal[1].get('id') != 'DEV-050' or
            journal[1].get('request_sha256') != expected_request['request_sha256'] or
            journal[3].get('status') != 'service_error' or
            journal[4].get('id') != 'DEV-050' or
            len(records) != 1 or records[0].get('id') != 'DEV-050' or
            records[0].get('request_sha256') != expected_request['request_sha256'] or
            records[0].get('input_sha256') != expected_request['input_sha256'] or
            records[0].get('policy_sha256') != expected_request['instruction_sha256'] or
            records[0].get('reference_labels_read') is not False or
            records[0].get('status') != 'service_error' or
            records[0].get('http_status') != 429 or
            records[0].get('cost_unknown') is not True or
            records[0].get('observed_cost_usd') is not None or
            records[0].get('billing_ok') is not False):
        raise ValueError('Third-interruption stage evidence differs')
    attempt = records[0]['attempt_id']
    if (any(e.get('attempt_id') != attempt for e in journal[1:4]) or
            [e.get('event') for e in budget] != ['budget', 'reserve',
                'unknown_cost_accounted_as_upper_bound', 'partition_closed'] or
            budget[1].get('attempt_id') != attempt or budget[1].get('record_id') != 'DEV-050' or
            budget[1].get('usd') != RESERVE or
            budget[2].get('attempt_id') != attempt or
            budget[2].get('evidence_sha256') != STAGE_SHA['phase-03-suffix.records.jsonl'] or
            budget[2].get('usd') != RESERVE or
            budget[2].get('actual_cost_usd') is not None or
            terminal.get('event') != 'partition_reconciled' or
            terminal.get('partition_id') != manifest['partition_id'] or
            terminal.get('known_actual_usd') != '0' or
            terminal.get('unknown_upper_bound_usd') != RESERVE or
            terminal.get('child_sha256') != _sha(prior.file(root, budget_path))):
        raise ValueError('Third-interruption budget disposition differs')
    duration = last['client_http_duration_seconds']
    if not isinstance(duration, (int, float)) or not 0 <= duration < 3600:
        raise ValueError('DEV-050 client duration differs')
    series.pop('budgetAccountingCumulative', None)
    prior_checkpoint.pop('sealedChild', None)
    series.update(schema=SCHEMA, seriesId=SERIES,
                  continuationStatus='suffix_stopped_at_DEV-050_unscored',
                  thirdInterruptionCheckpoint={
                      'phase': 'fresh1/P2', 'status': 'terminal_stopped_at_DEV-050',
                      'attemptedAtThirdInterruption': 50,
                      'neverSentAtThirdInterruption': 10,
                      'outcomes': snapshot['status_counts'],
                      'invalidIds': ['DEV-039'],
                      'serviceErrorIds': ['DEV-040', 'DEV-049', 'DEV-050'],
                      'clientHttpDurationSecondsAtDev050': duration,
                      'timingKind': 'client_http_duration_not_provider_inference',
                      'publicSnapshot': {'path': str(NEW / 'phase-03-suffix.public.json'),
                                         'sha256': SNAPSHOT_SHA},
                      'score': None})
    series['missingPasses'][0] = {'pass': 'fresh1', 'condition': 'P2',
                                  'status': 'stopped_at_DEV-050_unscored'}
    series['limitations'].append(
        'DEV-050 stopped the second continuation. DEV-051 through DEV-060 were never sent; no fresh1/P2 score exists.')
    series['limitations'].append(
        'The DEV-050 duration measures the client HTTP call and durable raw capture, not pure model inference.')
    result['schema'] = SCHEMA
    result['publicVerificationLimit'] = (
        'Private provider error bytes and historical source files remain hash-bound; '
        'a public archive can verify the committed projection and stage record, not reconstruct those bytes.')
    _assert_public(result)
    return result


def _assert_public(value):
    forbidden = {'request', 'feedback', 'raw_response', 'raw_error_response', 'error_body',
                 'authorization', 'api_key', 'child_cap_usd', 'unused_allocation_released_usd',
                 'budgetAccountingCumulative', 'sealedChild'}
    if isinstance(value, dict):
        if forbidden.intersection(value):
            raise ValueError('Private field in public feed')
        for child in value.values():
            _assert_public(child)
    elif isinstance(value, list):
        for child in value:
            _assert_public(child)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = json.dumps(build(args.root), indent=2, ensure_ascii=False) + '\n'
    if args.output:
        if args.output.exists():
            raise SystemExit('Refusing to overwrite an existing public feed')
        args.output.write_text(output)
    else:
        print(output, end='')


# Exact tracked source inventory in the frozen third-continuation plan.
EXPECTED_SOURCES = {
    'original_manifest': str(prior.BASE / 'manifest.json'),
    'original_controller': 'scripts/deepseek_low_fresh_repeat_execution_v2.py',
    'first_controller': 'scripts/deepseek_low_interruption_continuation.py',
    'first_manifest': str(prior.NEW / 'manifest.json'),
    'first_review': str(prior.NEW / 'phase-03-suffix.root-review.json'),
    'lower_price_controller': 'scripts/deepseek_low_price_successor_v1.py',
    'second_price_controller': 'scripts/deepseek_low_price_successor_v2.py',
    'bounded_byte_transport': 'scripts/qwen27_fresh_repeat_execution.py',
    'lower_price_route_audit': str(prior.BASE / 'lower-price-endpoint-audit-v1.json'),
    'second_price_route_audit': 'results/route-audits/deepseek-low-second-price-20261001T014436Z/audit.json',
    'second_price_raw_models': 'results/route-audits/deepseek-low-second-price-20261001T014436Z/models.json',
    'second_price_raw_endpoints': 'results/route-audits/deepseek-low-second-price-20261001T014436Z/endpoints.json',
    'v3_partition_controller': 'scripts/paid_budget_partitions_v3.py',
    'v3_budget_controller': 'scripts/openrouter_budget_v3.py',
    'new_budget_manifest': str(NEW / 'budget.json'),
    'first_child_ledger': str(prior.NEW / 'budget-deepseek-low-interruption-20260929.jsonl'),
    'first_terminal_reconciliation': str(prior.NEW / 'terminal-reconciliation-after-dev049.json'),
    'first_suffix_claim': str(prior.NEW / 'phase-03-suffix.claim.json'),
    'first_suffix_journal': str(prior.NEW / 'phase-03-suffix.journal.jsonl'),
    'first_suffix_raw': str(prior.NEW / 'phase-03-suffix.raw.jsonl'),
    'first_suffix_records': str(prior.NEW / 'phase-03-suffix.records.jsonl'),
    'original_failed_claim': str(prior.BASE / 'phase-03-development.claim.json'),
    'original_failed_journal': str(prior.BASE / 'phase-03-development.journal.jsonl'),
    'original_failed_raw': str(prior.BASE / 'phase-03-development.raw.jsonl'),
    'original_failed_records': str(prior.BASE / 'phase-03-development.records.jsonl'),
    'original_terminal_reconciliation': str(prior.BASE / 'terminal-reconciliation-after-dev040.json'),
}
for _phase in ('01', '02', '03'):
    for _stage in (('smoke',) if _phase == '03' else ('smoke', 'development')):
        for _part in ('claim', 'journal', 'raw', 'records'):
            EXPECTED_SOURCES[f'phase_{_phase}_{_stage}_{_part}'] = str(
                prior.BASE / f'phase-{_phase}-{_stage}.{_part}.jsonl')
            if _part == 'claim':
                EXPECTED_SOURCES[f'phase_{_phase}_{_stage}_{_part}'] = str(
                    prior.BASE / f'phase-{_phase}-{_stage}.claim.json')


if __name__ == '__main__':
    main()
