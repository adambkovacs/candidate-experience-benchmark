#!/usr/bin/env python3
"""Bounded second Qwen-off continuation; never replay DEV-006 or DEV-031."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import time

import openrouter_paid_benchmark as paid
import paid_budget_partitions_v2 as partitions
import qwen36_off_fresh_repeat_admission as admission
import qwen36_off_fresh_repeat_execution_v2 as original
import qwen36_off_v2_continuation as first_suffix
import qwen36_off_v2_successors as previous
from development_benchmark import ROOT, digest, valid
from openrouter_benchmark import allowed_returned_models

BASE = ROOT / 'results/repeatability-v1/qwen36-off-fresh3-v2'
OUTPUT = BASE / 'second-interruption-v1'
OLD = previous.OUTPUT
SCHEMA = 'qwen36-off-v2-second-interruption-v1'
PARTITION = 'qwen36-off-second-interruption-20260929'
CAP = paid.number('0.06')
RESERVE = admission.RESERVE
IDS = [f'DEV-{i:03d}' for i in range(1, 61)]
REMAINING = IDS[31:]
SEQUENCE = ((6, 'suffix'), (7, 'smoke'), (7, 'development'),
            (8, 'smoke'), (8, 'development'))
MAX_RAW = 16 * 1024 * 1024
OLD_LEDGER_SHA = '6113a30b7e73b354e229845f9553d54d657dddae51d2b2c36aed4c370f71771e'
OLD_MANIFEST_SHA = 'efc025c5d185835aff6734030c5613cac402909fe10ec4b34a6ae09d32bf045f'
OLD_RECONCILIATION_SHA = '95b4ce0da5672b30856313510684318608ab3456f829eed61a53c0043e29188c'
OLD_RECONCILIATION = BASE / 'terminal-reconciliation-after-second429.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    data = Path(path).read_bytes()
    if data and not data.endswith(b'\n'):
        raise ValueError('Incomplete JSONL evidence')
    return [json.loads(line) for line in data.splitlines() if line.strip()]


def binding(path):
    path = Path(path).resolve()
    return {'path': str(path.relative_to(ROOT.resolve())), 'sha256': sha(path)}


def read_bound(item):
    path = (ROOT / item['path']).resolve()
    path.relative_to(ROOT.resolve())
    if sha(path) != item['sha256']:
        raise ValueError('Bound evidence changed: ' + item['path'])
    return path


def old_context():
    path = OLD / 'manifest.json'
    if sha(path) != OLD_MANIFEST_SHA:
        raise ValueError('Frozen successor manifest changed')
    manifest = previous.validate_manifest(path, OLD_MANIFEST_SHA)
    for index in range(1, 6):
        if not (previous.finished(manifest, OLD_MANIFEST_SHA, index, 'smoke') and
                previous.finished(manifest, OLD_MANIFEST_SHA, index, 'development')):
            raise ValueError('Predecessor phase is not strictly closed')
    if not previous.finished(manifest, OLD_MANIFEST_SHA, 6, 'smoke'):
        raise ValueError('Failed phase smoke is not strictly closed')
    p = previous.stage_paths(6, 'development')
    if not all(x.is_file() for x in p.values()):
        raise ValueError('Failed phase evidence absent')
    claim, events, raw, records = (json.loads(p['claim'].read_text()),
        rows(p['journal']), rows(p['raw']), rows(p['records']))
    expected_claim = {'schema': 'affordable-hosted-stage-claim-v1',
        'manifest_sha256': OLD_MANIFEST_SHA,
        'budget_manifest_sha256': manifest['sources']['budget_manifest']['sha256'],
        'partition_id': manifest['partition_id'], 'phase_index': 6,
        'repeat': 'fresh3', 'condition': 'P1', 'stage': 'development', 'ids': IDS}
    if any(claim.get(k) != v for k, v in expected_claim.items()):
        raise ValueError('Failed stage claim changed')
    review = previous.stage_review_path(6, 'development')
    receipt = previous.verify_review(review, manifest, OLD_MANIFEST_SHA, 6, 'development')
    smoke = previous.stage_paths(6, 'smoke')
    inspection = receipt.get('smoke_inspection') or {}
    if (inspection.get('approved') is not True or
            inspection.get('statuses') != ['ok'] * 3 or
            any(inspection.get('smoke_' + name + '_sha256') != sha(smoke[name])
                for name in ('records', 'journal', 'raw'))):
        raise ValueError('Failed phase actual smoke inspection changed')
    if claim.get('review_sha256') != sha(review):
        raise ValueError('Failed stage review changed')
    if (len(records) != 31 or len(raw) != 31 or len(events) != 95 or
            events[0] != {'event': 'stage_claimed', 'claim_sha256': sha(p['claim'])} or
            events[-1] != {'event': 'stage_stopped', 'id': IDS[30], 'reason': 'service_error'}):
        raise ValueError('Failed phase must stop exactly at DEV-031')
    raw_lines = p['raw'].read_bytes().splitlines(keepends=True)
    for i, (row, sidecar) in enumerate(zip(records, raw)):
        item = manifest['requests_by_condition']['P1'][i]
        attempt = row.get('attempt_id')
        started, saved, ended = events[1 + i * 3:4 + i * 3]
        if (row.get('id') != IDS[i] or row.get('request_sha256') != item['request_sha256'] or
                row.get('request') != item['payload'] or
                row.get('input_sha256') != item['input_sha256'] or
                row.get('policy_sha256') != item['instruction_sha256'] or
                row.get('budget_partition_id') != manifest['partition_id'] or
                row.get('reference_labels_read') is not False or
                row.get('reserved_cost_usd') != str(RESERVE) or
                row.get('provider_endpoint', {}).get('tag') != admission.PROVIDER or
                row.get('reasoning_effort') != 'off' or
                started != {'event': 'request_started', 'attempt_id': attempt,
                    'id': IDS[i], 'request_sha256': item['request_sha256'],
                    'reserved_cost_usd': str(RESERVE)} or
                saved != {'event': 'raw_saved', 'attempt_id': attempt,
                    'raw_sha256': hashlib.sha256(b''.join(raw_lines[:i + 1])).hexdigest()} or
                ended != {'event': 'request_finished', 'attempt_id': attempt,
                    'id': IDS[i], 'status': row.get('status'),
                    'billing_ok': row.get('billing_ok')} or
                sidecar.get('id') != IDS[i] or sidecar.get('attempt_id') != attempt):
            raise ValueError('Failed phase request evidence changed')
        if i < 30:
            status, prediction, actual = first_suffix.expected_body_status(
                sidecar.get('body'), row['provider_endpoint'])
            if (status != 'ok' or row.get('status') != 'ok' or
                    row.get('raw_response') != sidecar['body'] or
                    row.get('prediction') != prediction or
                    row.get('observed_cost_usd') != actual or
                    row.get('billing_ok') is not True):
                raise ValueError('Failed phase successful prefix changed')
        elif (row.get('status') != 'service_error' or row.get('http_status') != 429 or
              row.get('cost_unknown') is not True or row.get('billing_ok') is not False or
              row.get('observed_cost_usd') is not None or
              sidecar.get('http_status') != 429 or
              sidecar.get('error_body') != row.get('raw_error_response')):
            raise ValueError('Failed DEV-031 evidence changed')
    old_ledger = BASE / f'budget-{first_suffix.PARTITION}.jsonl'
    if sha(old_ledger) != OLD_LEDGER_SHA:
        raise ValueError('Old child ledger seal changed')
    ledger = rows(old_ledger)
    if ledger[-1].get('event') != 'partition_closed':
        raise ValueError('Old child not closed')
    failed_attempt = records[-1]['attempt_id']
    charges = [e for e in ledger if e.get('attempt_id') == failed_attempt]
    if (len(charges) != 2 or charges[0] != {'event': 'reserve',
            'attempt_id': failed_attempt, 'record_id': 'DEV-031', 'usd': str(RESERVE)} or
            charges[1].get('event') != 'unknown_cost_accounted_as_upper_bound' or
            charges[1].get('usd') != str(RESERVE) or
            charges[1].get('evidence_sha256') != sha(p['records']) or
            Path(charges[1].get('evidence_path', '')).resolve() != p['records'].resolve()):
        raise ValueError('DEV-031 unknown bound differs')
    if sha(OLD_RECONCILIATION) != OLD_RECONCILIATION_SHA:
        raise ValueError('Terminal reconciliation byte hash changed')
    recon = json.loads(OLD_RECONCILIATION.read_text())
    if (recon.get('event') != 'partition_reconciled' or
            recon.get('partition_id') != first_suffix.PARTITION or
            recon.get('child_sha256') != OLD_LEDGER_SHA or
            recon.get('known_actual_usd') != '0.0575207' or
            recon.get('unknown_upper_bound_usd') != '0.0598016' or
            recon.get('unused_allocation_released_usd') != '0.0326777' or
            Path(recon.get('child_ledger', '')).resolve() != old_ledger.resolve()):
        raise ValueError('Terminal reconciliation differs')
    master_events = rows(admission.MASTER)
    if not any(e == recon for e in master_events):
        raise ValueError('Master lacks exact old reconciliation event')
    sources = {'successor_manifest': binding(path),
        'successor_controller': binding(previous.__file__),
        'failed_claim': binding(p['claim']), 'failed_journal': binding(p['journal']),
        'failed_raw': binding(p['raw']), 'failed_records': binding(p['records']),
        'failed_review': binding(review), 'old_child_ledger': binding(old_ledger),
        'old_terminal_reconciliation': binding(OLD_RECONCILIATION)}
    for index in range(1, 7):
        for stage in ('smoke', 'development'):
            if index == 6 and stage == 'development':
                continue
            for part, artifact in previous.stage_paths(index, stage).items():
                sources[f'phase_{index + 1:02d}_{stage}_{part}'] = binding(artifact)
    return manifest, sources


def budget_entry(path):
    path = Path(path).resolve()
    if path != (OUTPUT / 'budget.json').resolve():
        raise ValueError('New budget must live in new output directory')
    data = json.loads(path.read_text())
    if data.get('version') != 'paid-partitions-v1' or data.get('master_ledger') != str(admission.MASTER.resolve()):
        raise ValueError('New budget master differs')
    entries = data.get('partitions')
    if not isinstance(entries, list) or len(entries) != 1:
        raise ValueError('New partition must be singular')
    entry = entries[0]
    if ((entry.get('id'), entry.get('model'), entry.get('provider'),
            entry.get('reasoning'), entry.get('cap_usd')) != (
            PARTITION, admission.MODEL, admission.PROVIDER, 'off', str(CAP)) or
            Path(entry.get('child_ledger', '')).resolve() !=
            (OUTPUT / f'budget-{PARTITION}.jsonl').resolve()):
        raise ValueError('Exact new child allocation differs')
    return entry


def expected_manifest(budget_path):
    previous_manifest, sources = old_context()
    budget_entry(budget_path)
    sources['new_budget_manifest'] = binding(budget_path)
    requests = previous.condition_requests(json.loads((BASE / 'manifest.json').read_text()))
    if requests != previous_manifest['requests_by_condition']:
        raise ValueError('Previous frozen requests changed')
    return {'schema': SCHEMA, 'status': 'FROZEN',
        'configuration': admission.CONFIG,
        'method': 'descriptive-continuation-after-two-service-errors',
        'clean_matched_three_eligible': False,
        'old_unknown_charge_upper_bound_usd': '0.0598016',
        'old_failed_ids': ['DEV-006', 'DEV-031'],
        'schedule': [{'phase_index': i, 'stage': s} for i, s in SEQUENCE],
        'phases': previous_manifest['phases'],
        'requests_by_condition': requests,
        'route': previous_manifest['route'],
        'sources': sources, 'controller': binding(__file__),
        'output_directory': str(OUTPUT.resolve().relative_to(ROOT.resolve())),
        'partition_id': PARTITION, 'child_cap_usd': str(CAP),
        'reserve_usd': str(RESERVE)}


def freeze(path, budget_path):
    if Path(path).resolve() != (OUTPUT / 'manifest.json').resolve():
        raise ValueError('New manifest path differs')
    manifest = expected_manifest(budget_path)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    original.atomic_json(path, manifest)
    return manifest


def validate_manifest(path, expected_sha):
    path = Path(path).resolve()
    if path != (OUTPUT / 'manifest.json').resolve() or sha(path) != expected_sha:
        raise ValueError('New manifest path or hash differs')
    manifest = json.loads(path.read_text())
    if manifest != expected_manifest(read_bound(manifest['sources']['new_budget_manifest'])):
        raise ValueError('Second interruption manifest differs from sources')
    return manifest


def stage_paths(index, stage):
    if (index, stage) not in SEQUENCE:
        raise ValueError('Unknown continuation stage')
    return original.paths(OUTPUT, index, 'development' if stage == 'suffix' else stage)


def review_path(index, stage):
    return OUTPUT / f'phase-{index + 1:02d}-{stage}.root-review.json'


def selected_items(manifest, index, stage):
    phase = manifest['phases'][index]
    selected = manifest['requests_by_condition'][phase['condition']]
    if stage == 'suffix':
        return selected[31:]
    return selected[:3] if stage == 'smoke' else selected


def verify_review(path, manifest, manifest_sha, index, stage):
    if Path(path).resolve() != review_path(index, stage).resolve():
        raise ValueError('Exact review path differs')
    receipt = json.loads(Path(path).read_text())
    expected = {'schema': SCHEMA + '-stage-review', 'approved': True,
        'manifest_sha256': manifest_sha,
        'controller_sha256': manifest['controller']['sha256'],
        'old_child_ledger_sha256': OLD_LEDGER_SHA,
        'old_terminal_reconciliation_sha256': manifest['sources']['old_terminal_reconciliation']['sha256'],
        'new_budget_manifest_sha256': manifest['sources']['new_budget_manifest']['sha256'],
        'partition_id': PARTITION, 'phase_index': index, 'stage': stage,
        'ids': [item['id'] for item in selected_items(manifest, index, stage)]}
    if any(receipt.get(k) != v for k, v in expected.items()):
        raise ValueError('Stage review differs')
    return receipt


def strict_finished(manifest, manifest_sha, index, stage):
    return original.finished(manifest, OUTPUT, index, stage, manifest_sha,
        manifest['sources']['new_budget_manifest']['sha256'], PARTITION)


def prepare(manifest_path, manifest_sha, budget_path, index, stage, review):
    manifest = validate_manifest(manifest_path, manifest_sha)
    if (index, stage) not in SEQUENCE:
        raise ValueError('Stage outside remaining ordered schedule')
    if Path(budget_path).resolve() != read_bound(manifest['sources']['new_budget_manifest']):
        raise ValueError('New child budget binding differs')
    verify_review(review, manifest, manifest_sha, index, stage)
    position = SEQUENCE.index((index, stage))
    for prior_index, prior_stage in SEQUENCE[:position]:
        if prior_stage == 'suffix':
            if reconcile_suffix(manifest_path, manifest_sha)['status'] != 'closed_with_service_error':
                raise ValueError('DEV032-060 suffix lacks exact closure')
        elif not strict_finished(manifest, manifest_sha, prior_index, prior_stage):
            raise ValueError('Previous stage lacks exact strict closure')
    if stage == 'development':
        receipt = json.loads(Path(review).read_text())
        inspection = receipt.get('smoke_inspection') or {}
        smoke = stage_paths(index, 'smoke')
        if (inspection.get('approved') is not True or
                inspection.get('statuses') != ['ok'] * 3 or
                any(inspection.get('smoke_' + k + '_sha256') != sha(smoke[k])
                    for k in ('records', 'journal', 'raw'))):
            raise ValueError('Actual smoke inspection differs')
    target = stage_paths(index, stage)
    if any(p.exists() for p in target.values()):
        raise FileExistsError('Stage already claimed; no replay')
    return manifest, manifest['phases'][index], target


def verify_static_sources(manifest):
    for item in manifest['sources'].values():
        read_bound(item)
    read_bound(manifest['controller'])
    original.verify_sources(json.loads((BASE / 'manifest.json').read_text()))


def execute(manifest_path, manifest_sha, budget_path, index, stage, review_path,
            env_file=None):
    manifest, phase, target = prepare(manifest_path, manifest_sha, budget_path,
                                      index, stage, review_path)
    suffix_manifest = json.loads((first_suffix.SUFFIX / 'manifest.json').read_text())
    model, endpoint = first_suffix.live_controls(suffix_manifest)
    selected = selected_items(manifest, index, stage)
    ledger = partitions.open_partition(admission.MASTER, budget_path, manifest['partition_id'],
                                       admission.MODEL, admission.PROVIDER, 'off')
    try:
        _, pending, blocked = ledger.state()
        if pending or blocked or ledger.closed:
            raise ValueError('New child budget has pending, blocked or closed state')
        token = paid.load_key(env_file)
        claim = {'schema': 'affordable-hosted-stage-claim-v1',
            'manifest_sha256': manifest_sha, 'review_sha256': sha(review_path),
            'budget_manifest_sha256': sha(budget_path),
            'partition_id': manifest['partition_id'], 'phase_index': index,
            'repeat': phase['repeat'], 'condition': phase['condition'],
            'stage': stage, 'ids': [item['id'] for item in selected]}
        original.atomic_json(target['claim'], claim)
        with (target['journal'].open('x') as journal,
              target['raw'].open('x') as raw,
              target['records'].open('x') as records):
            paid.durable(journal, {'event': 'stage_claimed',
                                   'claim_sha256': sha(target['claim'])})
            for item in selected:
                verify_static_sources(manifest)
                rid, payload = item['id'], item['payload']
                if digest(json.dumps(payload, sort_keys=True)) != item['request_sha256']:
                    raise ValueError('Frozen remaining request differs before call')
                try:
                    attempt = ledger.reserve(admission.RESERVE, rid)
                except ValueError as exc:
                    if 'cap reached' not in str(exc):
                        raise
                    paid.durable(journal, {'event': 'admission_stopped',
                        'next_unsent_id': rid, 'reason': 'child_cap'})
                    return {'completed': False, 'status': 'child_cap',
                            'next_unsent_id': rid}
                paid.durable(journal, {'event': 'request_started', 'attempt_id': attempt,
                    'id': rid, 'request_sha256': item['request_sha256'],
                    'reserved_cost_usd': str(admission.RESERVE)})
                row = {'id': rid, 'repeat': phase['repeat'],
                       'condition': phase['condition'], 'phase': 'development' if stage == 'suffix' else stage,
                       'attempt_id': attempt, 'request': payload,
                       'request_sha256': item['request_sha256'],
                       'input_sha256': item['input_sha256'],
                       'policy_sha256': item['instruction_sha256'],
                       'requested_model': admission.MODEL,
                       'provider_endpoint': endpoint, 'model_catalog_entry': model,
                       'reference_labels_read': False,
                       'reserved_cost_usd': str(admission.RESERVE),
                       'budget_partition_id': manifest['partition_id'],
                       'reasoning_effort': 'off', 'continue_on_invalid_output': False,
                       'retry_policy': 'none'}
                actual = None
                raw_saved = False
                try:
                    row['client_request_started_utc'] = datetime.now(timezone.utc).isoformat()
                    started = time.monotonic()
                    try:
                        body = paid.fetch('/chat/completions', token, payload, 300)
                    finally:
                        row['client_http_duration_seconds'] = time.monotonic() - started
                        row['client_request_finished_utc'] = datetime.now(timezone.utc).isoformat()
                    encoded = json.dumps(body).replace(token, '[REDACTED]')
                    if len(encoded.encode()) > MAX_RAW:
                        raise ValueError('Response exceeds raw capture bound')
                    body = json.loads(encoded)
                    paid.durable(raw, {'attempt_id': attempt, 'id': rid, 'body': body})
                    raw_saved = True
                    paid.durable(journal, {'event': 'raw_saved', 'attempt_id': attempt,
                                           'raw_sha256': sha(target['raw'])})
                    row['raw_response'] = body
                    usage = body.get('usage') or {}
                    row['usage'] = usage
                    if usage.get('cost') is not None:
                        actual = paid.number(usage['cost'])
                    choices = body.get('choices') or []
                    choice = choices[0] if len(choices) == 1 else {}
                    message = choice.get('message') or {}
                    try:
                        prediction = json.loads(message.get('content'))
                    except (ValueError, TypeError):
                        prediction = None
                    row.update(prediction=prediction, returned_model=body.get('model'),
                               returned_provider=body.get('provider'),
                               finish_reason=choice.get('finish_reason'))
                    row['status'] = ('ok' if valid(prediction) and len(choices) == 1 and
                        choice.get('finish_reason') == 'stop' and not body.get('error') and
                        not choice.get('error') and not message.get('refusal') and
                        not message.get('tool_calls') and not message.get('function_call')
                        else 'invalid_output')
                    if body.get('model') not in allowed_returned_models(admission.MODEL, endpoint):
                        row['status'] = 'model_mismatch'
                    if body.get('provider') != endpoint['provider_name']:
                        row['status'] = 'provider_mismatch'
                except Exception as exc:
                    if 'status' not in row:
                        row.update(status='service_error', error_type=type(exc).__name__)
                        if hasattr(exc, 'code'):
                            row['http_status'] = exc.code
                        if not raw_saved:
                            sidecar = {'attempt_id': attempt, 'id': rid,
                                       'transport_error': type(exc).__name__}
                            if hasattr(exc, 'read'):
                                try:
                                    error_bytes = exc.read(1_000_001)
                                    sidecar['error_body'] = error_bytes[:1_000_000].decode(errors='replace').replace(token, '[REDACTED]')
                                    sidecar['body_truncated_at_limit'] = len(error_bytes) > 1_000_000
                                    row['raw_error_response'] = sidecar['error_body']
                                except Exception:
                                    sidecar['read_error'] = 'error_body_unavailable'
                            if hasattr(exc, 'code'):
                                sidecar['http_status'] = exc.code
                            paid.durable(raw, sidecar)
                            paid.durable(journal, {'event': 'raw_saved',
                                'attempt_id': attempt, 'raw_sha256': sha(target['raw'])})
                billing_ok = ledger.settle(attempt, actual)
                if actual is not None and not billing_ok:
                    row['status'] = 'billing_blocked'
                row.update(observed_cost_usd=str(actual) if actual is not None else None,
                           cost_unknown=actual is None, billing_ok=billing_ok)
                paid.durable(records, row)
                paid.durable(journal, {'event': 'request_finished', 'attempt_id': attempt,
                    'id': rid, 'status': row['status'], 'billing_ok': billing_ok})
                if row['status'] != 'ok' or actual is None or not billing_ok:
                    paid.durable(journal, {'event': 'stage_stopped', 'id': rid,
                                           'reason': row['status']})
                    return {'completed': False, 'status': row['status'], 'stopped_id': rid}
            paid.durable(journal, {'event': 'stage_completed', 'count': len(selected)})
            return {'completed': True, 'count': len(selected)}
    finally:
        ledger.close()


def reconcile_suffix(manifest_path, manifest_sha):
    """Verify the original 31 plus this child's immutable attempted prefix."""
    manifest = validate_manifest(manifest_path, manifest_sha)
    target = stage_paths(6, 'suffix')
    old = rows(read_bound(manifest['sources']['failed_records']))
    if [r.get('id') for r in old] != IDS[:31]:
        raise ValueError('Original stopped prefix changed')
    budget = read_bound(manifest['sources']['new_budget_manifest'])
    entry = budget_entry(budget)
    ledger_path = Path(entry['child_ledger'])
    ledger = rows(ledger_path)
    if not ledger or ledger[0] != {'event': 'budget', 'cap_usd': str(CAP)}:
        raise ValueError('New child ledger differs')
    evidence = {k: v for k, v in manifest['sources'].items() if
                k.startswith('failed_') or k in ('old_child_ledger', 'old_terminal_reconciliation')}
    known = paid.number('0')
    unknown = paid.number('0')
    pending = paid.number('0')
    if not target['claim'].exists():
        if any(target[k].exists() for k in ('journal', 'raw', 'records')):
            raise ValueError('Suffix evidence without claim')
        fresh, status = [], 'not_started'
    else:
        if not all(path.exists() for path in target.values()):
            raise ValueError('Claimed suffix lacks evidence')
        claim = json.loads(target['claim'].read_text())
        review = review_path(6, 'suffix')
        verify_review(review, manifest, manifest_sha, 6, 'suffix')
        phase = manifest['phases'][6]
        expect_claim = {'schema': 'affordable-hosted-stage-claim-v1',
            'manifest_sha256': manifest_sha, 'review_sha256': sha(review),
            'budget_manifest_sha256': sha(budget), 'partition_id': PARTITION,
            'phase_index': 6, 'repeat': phase['repeat'], 'condition': phase['condition'],
            'stage': 'suffix', 'ids': REMAINING}
        if any(claim.get(k) != v for k, v in expect_claim.items()):
            raise ValueError('Suffix claim differs')
        events, raw, fresh = (rows(target['journal']), rows(target['raw']), rows(target['records']))
        if (not events or events[0] != {'event': 'stage_claimed',
                'claim_sha256': sha(target['claim'])} or
                len(fresh) != len(raw) or len(fresh) > len(REMAINING) or
                [r.get('id') for r in fresh] != REMAINING[:len(fresh)] or
                len(events) != 2 + 3 * len(fresh)):
            raise ValueError('Suffix event count or ordered membership differs')
        raw_lines = target['raw'].read_bytes().splitlines(keepends=True)
        attempts = set()
        for i, (row, sidecar) in enumerate(zip(fresh, raw)):
            item = selected_items(manifest, 6, 'suffix')[i]
            attempt = row.get('attempt_id')
            started, saved, ended = events[1 + 3 * i:4 + 3 * i]
            if (not isinstance(attempt, str) or not attempt or attempt in attempts or
                    row.get('id') != item['id'] or row.get('repeat') != 'fresh3' or
                    row.get('condition') != 'P1' or row.get('phase') != 'development' or
                    row.get('request') != item['payload'] or
                    row.get('request_sha256') != item['request_sha256'] or
                    row.get('input_sha256') != item['input_sha256'] or
                    row.get('policy_sha256') != item['instruction_sha256'] or
                    row.get('reference_labels_read') is not False or
                    row.get('requested_model') != admission.MODEL or
                    row.get('reasoning_effort') != 'off' or
                    row.get('provider_endpoint', {}).get('tag') != admission.PROVIDER or
                    row.get('budget_partition_id') != PARTITION or
                    row.get('reserved_cost_usd') != str(RESERVE) or
                    started != {'event': 'request_started', 'attempt_id': attempt,
                        'id': item['id'], 'request_sha256': item['request_sha256'],
                        'reserved_cost_usd': str(RESERVE)} or
                    saved != {'event': 'raw_saved', 'attempt_id': attempt,
                        'raw_sha256': hashlib.sha256(b''.join(raw_lines[:i + 1])).hexdigest()} or
                    ended != {'event': 'request_finished', 'attempt_id': attempt,
                        'id': item['id'], 'status': row.get('status'),
                        'billing_ok': row.get('billing_ok')} or
                    sidecar.get('attempt_id') != attempt or sidecar.get('id') != item['id']):
                raise ValueError('Suffix request or journal differs')
            attempts.add(attempt)
            start = datetime.fromisoformat(row['client_request_started_utc'])
            end = datetime.fromisoformat(row['client_request_finished_utc'])
            duration = row['client_http_duration_seconds']
            if (start.utcoffset() != timezone.utc.utcoffset(None) or
                    end.utcoffset() != timezone.utc.utcoffset(None) or end < start or
                    type(duration) not in (int, float) or not math.isfinite(duration) or duration < 0):
                raise ValueError('Suffix timing differs')
            if 'body' in sidecar:
                body = sidecar['body']
                expected_status, prediction, actual = first_suffix.expected_body_status(
                    body, row['provider_endpoint'])
                billed_status = ('billing_blocked' if actual is not None and
                                 row.get('billing_ok') is False else expected_status)
                if (row.get('raw_response') != body or
                        row.get('usage') != body.get('usage') or
                        row.get('prediction') != prediction or
                        row.get('returned_model') != body.get('model') or
                        row.get('returned_provider') != body.get('provider') or
                        row.get('observed_cost_usd') != actual or
                        row.get('status') != billed_status):
                    raise ValueError('Suffix parsed body differs')
            else:
                actual = None
                if (row.get('status') != 'service_error' or
                        row.get('raw_error_response') != sidecar.get('error_body') or
                        row.get('http_status') != sidecar.get('http_status') or
                        not sidecar.get('transport_error') or
                        row.get('observed_cost_usd') is not None):
                    raise ValueError('Suffix transport error differs')
            if row.get('cost_unknown') is not (actual is None):
                raise ValueError('Suffix cost certainty differs')
            charges = [e for e in ledger if e.get('attempt_id') == attempt]
            reserve = {'event': 'reserve', 'attempt_id': attempt,
                       'record_id': item['id'], 'usd': str(RESERVE)}
            if actual is not None:
                if charges != [reserve, {'event': 'settle', 'attempt_id': attempt,
                                         'usd': actual}]:
                    raise ValueError('Suffix settlement differs')
                settle_idx = next(j for j, e in enumerate(ledger) if
                                  e.get('event') == 'settle' and e.get('attempt_id') == attempt)
                blocked_after = (settle_idx + 1 < len(ledger) and
                    ledger[settle_idx + 1].get('event') == 'blocked' and
                    ledger[settle_idx + 1].get('reason') == 'Actual cost exceeds reserved bound')
                if row.get('billing_ok') is blocked_after:
                    raise ValueError('Suffix billing block differs')
                known += paid.number(actual)
            elif len(charges) == 1 and charges[0] == reserve:
                if row.get('billing_ok') is not False:
                    raise ValueError('Pending unknown billing differs')
                pending += RESERVE
            elif (len(charges) == 2 and charges[0] == reserve and
                  charges[1].get('event') == 'unknown_cost_accounted_as_upper_bound' and
                  charges[1].get('usd') == str(RESERVE) and
                  charges[1].get('actual_cost_usd') is None and
                  charges[1].get('evidence_sha256') == sha(target['records']) and
                  Path(charges[1].get('evidence_path', '')).resolve() == target['records'].resolve()):
                if row.get('billing_ok') is not False:
                    raise ValueError('Accounted unknown billing differs')
                unknown += RESERVE
            else:
                raise ValueError('Suffix unknown charge differs')
        last = events[-1]
        if (len(fresh) == len(REMAINING) and
                last == {'event': 'stage_completed', 'count': len(REMAINING)} and
                all(r.get('status') == 'ok' and r.get('billing_ok') is True for r in fresh)):
            status = 'closed_with_service_error'
        elif (len(fresh) < len(REMAINING) and
              last == {'event': 'admission_stopped',
                  'next_unsent_id': REMAINING[len(fresh)], 'reason': 'child_cap'} and
              all(r.get('status') == 'ok' and r.get('billing_ok') is True for r in fresh)):
            status = 'admission_stopped'
        elif (fresh and last == {'event': 'stage_stopped', 'id': fresh[-1]['id'],
                                 'reason': fresh[-1]['status']} and
              all(r.get('status') == 'ok' and r.get('billing_ok') is True for r in fresh[:-1])):
            status = 'stopped'
        else:
            raise ValueError('Suffix terminal event differs')
        evidence.update({k: binding(v) for k, v in target.items()})
        evidence['suffix_review'] = binding(review)
    projected = [first_suffix.project(r) for r in old + fresh]
    for position in projected:
        if position.get('status') != 'ok':
            position['prediction'] = None
    projected += [{'id': rid, 'status': 'never_sent'} for rid in REMAINING[len(fresh):]]
    if len(projected) != 60 or projected[30]['status'] != 'service_error':
        raise ValueError('Composite 60-position evidence differs')
    return {'schema': SCHEMA + '-suffix-reconciliation',
        'method': manifest['method'], 'status': status, 'denominator': 60,
        'strict_complete_pass': False,
        'valid': 59 if status == 'closed_with_service_error' else None,
        'observed_valid_positions': sum(p['status'] == 'ok' for p in projected),
        'status_counts': {k: sum(p['status'] == k for p in projected)
                          for k in sorted({p['status'] for p in projected})},
        'positions': projected, 'old_failed_ids': ['DEV-006', 'DEV-031'],
        'old_unknown_charge_upper_bound_usd': '0.0598016',
        'new_known_actual_usd': str(known),
        'new_unknown_charge_upper_bound_usd': str(unknown),
        'new_pending_unknown_reserve_usd': str(pending),
        'manifest_sha256': manifest_sha, 'evidence': evidence,
        'private_evidence_note': 'Original failed raw bytes remain private; source hashes bind them. This sanitized projection cannot independently reproduce private bytes.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    f = sub.add_parser('freeze')
    f.add_argument('--manifest', required=True); f.add_argument('--budget', required=True)
    v = sub.add_parser('validate')
    v.add_argument('--manifest', required=True); v.add_argument('--sha256', required=True)
    r = sub.add_parser('reconcile-suffix')
    r.add_argument('--manifest', required=True); r.add_argument('--sha256', required=True)
    e = sub.add_parser('execute-stage')
    for name in ('manifest', 'sha256', 'budget', 'review'):
        e.add_argument('--' + name, required=True)
    e.add_argument('--phase-index', required=True, type=int)
    e.add_argument('--stage', required=True, choices=('suffix', 'smoke', 'development'))
    e.add_argument('--env-file')
    args = parser.parse_args()
    if args.command == 'freeze':
        freeze(args.manifest, args.budget)
        print(json.dumps({'manifest_sha256': sha(args.manifest), 'stages': len(SEQUENCE)}))
    elif args.command == 'validate':
        validate_manifest(args.manifest, args.sha256)
        print(json.dumps({'validated': True}))
    elif args.command == 'reconcile-suffix':
        print(json.dumps(reconcile_suffix(args.manifest, args.sha256), indent=2))
    else:
        print(json.dumps(execute(args.manifest, args.sha256, args.budget,
            args.phase_index, args.stage, args.review, args.env_file)))


if __name__ == '__main__':
    main()
