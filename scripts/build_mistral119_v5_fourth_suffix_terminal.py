#!/usr/bin/env python3
"""Read-only terminal proposal for Mistral119 DEV-059..060.

Prints a source-bound proposal. It never writes a report, changes a ledger, or
dispatches inference. Root review must precede unknown-cost accounting/seal.
"""
import base64
from decimal import Decimal
import json

import mistral119_v5_fourth_suffix as stage
import mistral119_v3_remaining_phases as prior
import mistral119_fresh_repeat_study as study
import mistral119_fresh_repeat_execution as frozen
import mistral119_v3_smoke as smoke
import openrouter_paid_benchmark as paid
from prompt_admission import audit_response

SCHEMA = 'mistral119-none-v5-fourth-suffix-terminal-proposal-v1'


def build():
    base = stage.BASE
    manifest, manifest_sha = stage.verify()
    binding = stage.gate('fresh1', 'P0', 'suffix', manifest, manifest_sha)
    budget_path = base / 'suffix.budget-manifest.json'
    receipt_path = base / 'suffix.root-review.json'
    receipt = stage.check_review(receipt_path, budget_path)
    claim_path = base / 'suffix.claim.json'
    claim = stage.saved(claim_path)
    files = prior.phase_files(base, 'suffix')
    ids = list(stage.IDS)
    if (claim.get('schema') != stage.SCHEMA + '-claim' or
            claim.get('manifest_sha256') != manifest_sha or
            claim.get('root_review_sha256') != smoke.sha(receipt_path) or
            claim.get('budget_manifest_sha256') != smoke.sha(budget_path) or
            claim.get('gate_sha256') != smoke.digest_bytes(smoke.canonical(binding)) or
            claim.get('ids') != ids):
        raise ValueError('Fourth suffix claim differs from review or manifest')
    attempts, raw, parsed, journal = (
        prior.rows(files[name]) for name in
        ('attempts.jsonl', 'raw.jsonl', 'parsed.jsonl', 'journal.jsonl'))
    if ([x.get('id') for x in attempts] != ids or
            [x.get('id') for x in raw] != ids or
            [x.get('id') for x in parsed] != ids[:1] or
            [x.get('event') for x in journal] !=
            ['stage_started', 'request_intent', 'request_started',
             'request_finished', 'request_intent', 'request_started',
             'stage_stopped', 'stage_aborted'] or
            [x.get('id') for x in journal[1:]] !=
            ['DEV-059'] * 3 + ['DEV-060'] * 4 or
            journal[0].get('count') != 2 or
            journal[-2].get('reason') != 'unknown_cost' or
            journal[-1].get('error_type') != 'ValueError'):
        raise ValueError('Fourth suffix has not stopped at exact DEV-060 boundary')
    aids = [x.get('attempt_id') for x in attempts]
    if any(not isinstance(x, str) or not x for x in aids) or len(set(aids)) != 2:
        raise ValueError('Missing or duplicate attempt IDs')
    for i, request in enumerate(manifest['suffix_requests']):
        rid = ids[i]
        intent, started = (journal[1], journal[2]) if i == 0 else (journal[4], journal[5])
        if (intent.get('id') != rid or started.get('id') != rid or
                intent.get('request_sha256') != request['request_sha256'] or
                started.get('request_sha256') != request['request_sha256'] or
                started.get('attempt_id') != aids[i] or
                raw[i].get('attempt_id') != aids[i] or
                raw[i].get('request_sha256') != request['request_sha256'] or
                raw[i].get('body_truncated_at_limit') is not False):
            raise ValueError('Fourth suffix request or attempt binding differs')
    if (journal[3].get('attempt_id') != aids[0] or
            parsed[0].get('attempt_id') != aids[0]):
        raise ValueError('Successful request completion binding differs')
    wires = [base64.b64decode(x['body_base64'], validate=True) for x in raw]
    if any(smoke.digest_bytes(wire) != row.get('body_sha256')
           for wire, row in zip(wires, raw)):
        raise ValueError('Saved raw response hash differs')
    bodies = [json.loads(wire) for wire in wires]
    original, _ = study.historical(smoke.CONFIG)
    model, endpoint = original['model_catalog_entry'], original['provider_endpoint']
    classified = frozen.runner.classify(bodies[0], model, endpoint)
    diagnostic = audit_response(bodies[0], 'openrouter_paid_v1',
                                study.CONTEXT - study.MAX_TOKENS)
    cost = paid.number(attempts[0].get('actual_cost_usd'))
    if (attempts[0].get('status') != 'ok' or
            attempts[0].get('cost_unknown') is not False or
            raw[0].get('http_status') != 200 or
            attempts[0].get('body_sha256') != raw[0].get('body_sha256') or
            parsed[0].get('body_sha256') != raw[0].get('body_sha256') or
            classified.get('status') != 'ok' or diagnostic.get('passed') is not True or
            parsed[0].get('prediction') != classified.get('prediction') or
            parsed[0].get('returned_model') != bodies[0].get('model') or
            parsed[0].get('returned_provider') != bodies[0].get('provider') or
            parsed[0].get('usage') != bodies[0].get('usage') or
            paid.number(bodies[0]['usage']['cost']) != cost or cost > study.RESERVE):
        raise ValueError('DEV-059 parsed result or observed charge differs')
    failure = bodies[1].get('error', {})
    metadata = failure.get('metadata', {})
    if (attempts[1].get('status') != 'unknown_cost' or
            attempts[1].get('cost_unknown') is not True or
            attempts[1].get('reserved_cost_usd') != str(study.RESERVE) or
            attempts[1].get('http_status') != 429 or
            raw[1].get('http_status') != 429 or
            bodies[1].get('usage') is not None or
            failure.get('code') != 429 or
            metadata.get('provider_name') != study.PROVIDER_NAME or
            metadata.get('limit_source') != 'upstream_provider_shared_pool'):
        raise ValueError('DEV-060 unknown-charge HTTP 429 differs')
    budget = stage.saved(budget_path)
    child_path = budget['partitions'][0]['child_ledger']
    master_before = smoke.sha(smoke.MASTER)
    master_events = prior.rows(smoke.MASTER)
    allocations = [x for x in master_events if x.get('partition_id') == stage.PID]
    if (allocations != [{'event': 'budget_partition', 'partition_id': stage.PID,
            'allocated_usd': str(stage.CAP),
            'manifest_path': str(budget_path.resolve()),
            'manifest_sha256': smoke.sha(budget_path),
            'child_ledger': child_path, 'model': study.MODEL,
            'provider': study.PROVIDER, 'reasoning': 'none'}]):
        raise ValueError('Master allocation differs or fourth suffix is already reconciled')
    child_before = smoke.sha(child_path)
    child_events = prior.rows(child_path)
    if (len(child_events) != 4 or
            child_events[0] != {'event': 'budget', 'cap_usd': str(stage.CAP)} or
            child_events[1] != {'event': 'reserve', 'attempt_id': aids[0],
                                'record_id': ids[0], 'usd': str(study.RESERVE)} or
            child_events[2] != {'event': 'settle', 'attempt_id': aids[0],
                                'usd': str(cost)} or
            child_events[3] != {'event': 'reserve', 'attempt_id': aids[1],
                                'record_id': ids[1], 'usd': str(study.RESERVE)}):
        raise ValueError('Fourth suffix child ledger does not match attempts')
    authority_before = smoke.sha(stage.AUTHORITY)
    authority = prior.rows(stage.AUTHORITY)
    desired_hold = {'event': 'hold', 'id': stage.AUTHORITY_ID,
                    'source_sha256': receipt['global_hold_source_sha256'],
                    'usd': str(stage.CAP)}
    if ([x for x in authority if x.get('id') == stage.AUTHORITY_ID] != [desired_hold] or
            receipt['global_hold_source_sha256'] != stage.global_hold_source(budget_path)):
        raise ValueError('Fourth suffix global hold differs')
    previous = binding['prior']
    composite_valid = previous['composite_valid'] + 1
    failed_ids = previous['failed_ids_preserved'] + ['DEV-060']
    if (composite_valid != 55 or len(failed_ids) != 5 or
            composite_valid + len(failed_ids) != 60):
        raise ValueError('Composite accounting differs')
    known = cost
    unknown = study.RESERVE
    unused = stage.CAP - known - unknown
    sources = {name: smoke.sha(path) for name, path in files.items()}
    sources.update({'manifest.json': smoke.sha(base / 'manifest.json'),
                    'suffix.budget-manifest.json': smoke.sha(budget_path),
                    'suffix.root-review.json': smoke.sha(receipt_path),
                    'child_ledger': child_before,
                    'master_ledger': master_before,
                    'global_authority': authority_before,
                    'mistral119_v5_fourth_suffix.py': smoke.sha(stage.__file__)})
    result = {'schema': SCHEMA, 'status': 'stopped_pending_reconciliation',
              'approved': False, 'fresh_pass': 'fresh1', 'condition': 'P0',
              'configuration_id': smoke.CONFIG, 'ids': ids,
              'valid_ids': ['DEV-059'], 'failed_id': 'DEV-060',
              'http_status': 429, 'limit_source': 'upstream_provider_shared_pool',
              'failed_attempt_id': aids[1], 'retry_allowed': False,
              'known_actual_usd': str(known),
              'unknown_upper_bound_usd': str(unknown),
              'proposed_unused_allocation_release_usd': str(unused),
              'child_cap_usd': str(stage.CAP),
              'child_sealed': False, 'reference_labels_sent': False,
              'composite': {'denominator': 60, 'valid': composite_valid,
                            'failed': len(failed_ids),
                            'never_sent': 0,
                            'failed_ids': failed_ids, 'score': None},
              'source_sha256': sources}
    # Detect a concurrent append while building the read-only proposal.
    if (smoke.sha(child_path) != sources['child_ledger'] or
            smoke.sha(smoke.MASTER) != sources['master_ledger'] or
            smoke.sha(files['journal.jsonl']) != sources['journal.jsonl'] or
            smoke.sha(stage.AUTHORITY) != sources['global_authority']):
        raise ValueError('Terminal sources changed during audit')
    return result


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True, indent=2))
