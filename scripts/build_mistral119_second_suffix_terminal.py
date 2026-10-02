#!/usr/bin/env python3
"""Read and verify the sealed Mistral DEV-051..060 suffix; emit public JSON.

The builder never opens a writable ledger or contacts a model. It refuses a
live, unsealed, or changed child. --write creates a new report after closure.
"""
import argparse
import base64
from decimal import Decimal
import json
from pathlib import Path

import mistral119_v3_second_suffix as stage
import mistral119_v3_remaining_phases as prior
import mistral119_fresh_repeat_study as study
import mistral119_fresh_repeat_execution as frozen
import mistral119_v3_smoke as smoke
import openrouter_paid_benchmark as paid
from prompt_admission import audit_response

SCHEMA = 'mistral119-none-v3-second-suffix-terminal-public-v1'
REPORT = stage.BASE / 'suffix.terminal-public.json'


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def build(base=stage.BASE):
    base = Path(base)
    if base != stage.BASE:
        raise ValueError('Only the exact admitted stage can be reported')
    manifest, manifest_sha = stage.verify()
    binding = stage.gate('fresh1', 'P0', 'suffix', manifest, manifest_sha)
    budget_path = base / 'suffix.budget-manifest.json'
    receipt_path = base / 'suffix.root-review.json'
    claim_path = base / 'suffix.claim.json'
    receipt = json.loads(receipt_path.read_text())
    expected = stage.expected_receipt('fresh1', 'P0', 'suffix', manifest,
                                      manifest_sha, budget_path, binding)
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError('Root receipt does not bind this stage')
    claim = json.loads(claim_path.read_text())
    ids = list(stage.IDS)
    if (claim.get('schema') != stage.SCHEMA + '-claim' or
            claim.get('manifest_sha256') != manifest_sha or
            claim.get('root_review_sha256') != smoke.sha(receipt_path) or
            claim.get('budget_manifest_sha256') != smoke.sha(budget_path) or
            claim.get('gate_sha256') != receipt['gate_sha256'] or
            claim.get('ids') != ids):
        raise ValueError('Stage claim differs from review and manifest')
    paths = prior.phase_files(base, 'suffix')
    journal = rows(paths['journal.jsonl'])
    attempts = rows(paths['attempts.jsonl'])
    raw = rows(paths['raw.jsonl'])
    parsed = rows(paths['parsed.jsonl'])
    expected_attempted = ids[:3]
    if ([x.get('id') for x in attempts] != expected_attempted or
            [x.get('id') for x in raw] != expected_attempted or
            [x.get('id') for x in parsed] != expected_attempted[:2] or
            len(journal) != 11 or journal[0].get('event') != 'stage_started' or
            [x.get('event') for x in journal[-2:]] != ['stage_stopped', 'stage_aborted'] or
            [x.get('id') for x in journal[-2:]] != ['DEV-053', 'DEV-053']):
        raise ValueError('Stage has not ended at the recorded DEV-053 boundary')
    original, _ = study.historical(smoke.CONFIG)
    model, endpoint = original['model_catalog_entry'], original['provider_endpoint']
    known = Decimal(0)
    for index in range(2):
        request = manifest['suffix_requests'][index]
        attempt, wire_row, result = attempts[index], raw[index], parsed[index]
        rid, aid = expected_attempted[index], attempt.get('attempt_id')
        events = journal[1+3*index:4+3*index]
        if (not isinstance(aid, str) or not aid or
                attempt.get('status') != 'ok' or attempt.get('cost_unknown') is not False or
                any(x.get('attempt_id') != aid for x in (wire_row, result)) or
                [(x.get('event'), x.get('id')) for x in events] !=
                [('request_intent', rid), ('request_started', rid), ('request_finished', rid)] or
                events[0].get('request_sha256') != request['request_sha256'] or
                events[1].get('request_sha256') != request['request_sha256'] or
                wire_row.get('request_sha256') != request['request_sha256'] or
                wire_row.get('http_status') != 200 or
                wire_row.get('body_truncated_at_limit') is not False):
            raise ValueError('Successful attempt differs from frozen request')
        wire = base64.b64decode(wire_row['body_base64'], validate=True)
        body = json.loads(wire)
        classified = frozen.runner.classify(body, model, endpoint)
        diagnostic = audit_response(body, 'openrouter_paid_v1',
                                    study.CONTEXT-study.MAX_TOKENS)
        actual = paid.number(attempt['actual_cost_usd'])
        if (smoke.digest_bytes(wire) != wire_row.get('body_sha256') or
                wire_row.get('body_sha256') != attempt.get('body_sha256') or
                result.get('body_sha256') != wire_row.get('body_sha256') or
                classified.get('status') != 'ok' or diagnostic.get('passed') is not True or
                classified['prediction'] != result.get('prediction') or
                result.get('returned_model') != body.get('model') or
                result.get('returned_provider') != body.get('provider') or
                result.get('usage') != body.get('usage') or
                paid.number(body['usage']['cost']) != actual or actual > study.RESERVE):
            raise ValueError('Saved successful response or billing differs')
        known += actual
    failed = attempts[2]
    failed_raw = raw[2]
    failure_request = manifest['suffix_requests'][2]
    failure_events = journal[7:11]
    failure_wire = base64.b64decode(failed_raw['body_base64'], validate=True)
    failure = json.loads(failure_wire)
    metadata = failure.get('error', {}).get('metadata', {})
    if (failed.get('id') != 'DEV-053' or
            failed.get('status') != 'unknown_cost' or
            failed.get('http_status') != 429 or
            failed.get('cost_unknown') is not True or
            failed.get('reserved_cost_usd') != str(study.RESERVE) or
            failed_raw.get('attempt_id') != failed.get('attempt_id') or
            failed_raw.get('http_status') != 429 or
            failed_raw.get('request_sha256') != failure_request['request_sha256'] or
            failed_raw.get('body_truncated_at_limit') is not False or
            failed_raw.get('body_sha256') != smoke.digest_bytes(failure_wire) or
            [(x.get('event'), x.get('id')) for x in failure_events] !=
            [('request_intent', 'DEV-053'), ('request_started', 'DEV-053'),
             ('stage_stopped', 'DEV-053'), ('stage_aborted', 'DEV-053')] or
            failure_events[0].get('request_sha256') != failure_request['request_sha256'] or
            failure_events[1].get('request_sha256') != failure_request['request_sha256'] or
            failure_events[2].get('reason') != 'unknown_cost' or
            failure.get('error', {}).get('code') != 429 or
            metadata.get('provider_name') != study.PROVIDER_NAME or
            metadata.get('limit_source') != 'upstream_provider_shared_pool'):
        raise ValueError('DEV-053 upstream failure differs')
    reconciliation_path = base / 'suffix.budget-reconciliation.json'
    reconciliation = json.loads(reconciliation_path.read_text())
    if (reconciliation.get('event') != 'partition_reconciled' or
            reconciliation.get('partition_id') != stage.PID or
            paid.number(reconciliation.get('known_actual_usd')) != known or
            paid.number(reconciliation.get('unknown_upper_bound_usd')) != study.RESERVE or
            paid.number(reconciliation.get('unused_allocation_released_usd')) !=
            stage.CAP-known-study.RESERVE or
            smoke.sha(reconciliation['child_ledger']) != reconciliation.get('child_sha256')):
        raise ValueError('Child has not been sealed with exact known and unknown costs')
    first = json.loads((prior.FIRST_BASE / 'development.terminal-public.json').read_text())
    second = json.loads((prior.SUFFIX_BASE / 'suffix.terminal-public.json').read_text())
    composite_valid = first['valid_count'] + len(second['valid_ids']) + 2
    composite_failed = 1 + 1 + 1
    composite_unsent = len(ids[3:])
    if (composite_valid, composite_failed, composite_unsent) != (50, 3, 7) or \
            composite_valid + composite_failed + composite_unsent != 60:
        raise ValueError('Composite fixed-60 accounting differs')
    source_paths = {path.name: path for path in paths.values()}
    source_paths['suffix.root-review.json'] = receipt_path
    source_paths['suffix.budget-reconciliation.json'] = reconciliation_path
    source_paths['build_mistral119_second_suffix_terminal.py'] = (
        study.ROOT / 'scripts/build_mistral119_second_suffix_terminal.py')
    source_paths['test_build_mistral119_second_suffix_terminal.py'] = (
        study.ROOT / 'tests/test_build_mistral119_second_suffix_terminal.py')
    return {'schema': SCHEMA, 'status': 'interrupted_unscored',
            'configuration_id': smoke.CONFIG, 'fresh_pass': 'fresh1',
            'condition': 'P0', 'phase': 'suffix', 'manifest_sha256': manifest_sha,
            'source_sha256': {name: smoke.sha(path) for name, path in source_paths.items()},
            'valid_ids': expected_attempted[:2], 'failed_id': 'DEV-053',
            'http_status': 429, 'limit_source': 'upstream_provider_shared_pool',
            'unsent_ids': ids[3:], 'known_cost_usd': str(known),
            'unknown_cost_upper_bound_usd': str(study.RESERVE),
            'unused_allocation_released_usd':
                str(stage.CAP-known-study.RESERVE),
            'sealed_child_sha256': reconciliation['child_sha256'],
            'earlier_failed_ids_preserved': ['DEV-048', 'DEV-050'],
            'composite_valid_count': composite_valid,
            'composite_failed_count': composite_failed,
            'composite_never_sent_count': composite_unsent,
            'composite_score': None,
            'reference_labels_sent': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true')
    args = parser.parse_args()
    report = build()
    if args.write:
        with REPORT.open('x') as out:
            paid.durable(out, report)
        print(REPORT)
    else:
        print(json.dumps(report, sort_keys=True, indent=2))


if __name__ == '__main__': main()
