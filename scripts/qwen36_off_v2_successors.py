#!/usr/bin/env python3
"""Eight reviewed Qwen off v2 successor stages after a closed failed-first-pass suffix."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import openrouter_paid_benchmark as paid
import paid_budget_partitions_v2 as partitions
import qwen36_off_fresh_repeat_admission as admission
import qwen36_off_fresh_repeat_execution_v2 as original
import qwen36_off_v2_continuation as suffix
from development_benchmark import ROOT, digest, read_rows, valid
from openrouter_benchmark import allowed_returned_models

BASE = ROOT / 'results/repeatability-v1/qwen36-off-fresh3-v2'
OUTPUT = BASE / 'later-phases-v1'
SCHEMA = 'qwen36-off-v2-successors-v1'
FIRST = 1
LAST = 8
IDS = [f'DEV-{i:03d}' for i in range(1, 61)]
MAX_RAW = 16 * 1024 * 1024


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def binding(path):
    path = Path(path).resolve()
    return {'path': str(path.relative_to(ROOT.resolve())), 'sha256': sha(path)}


def read_bound(item):
    path = (ROOT / item['path']).resolve()
    path.relative_to(ROOT.resolve())
    if sha(path) != item['sha256']:
        raise ValueError('Successor source changed: ' + item['path'])
    return path


def source_context():
    original_path = BASE / 'manifest.json'
    original_manifest = original.load_manifest(original_path, sha(original_path))
    if (original_manifest.get('schema') != 'affordable-hosted-fresh3-execution-v2' or
            original_manifest.get('configuration_id') != admission.CONFIG or
            len(original_manifest.get('phases', [])) != 9):
        raise ValueError('Original nine-phase manifest differs')
    suffix_path = suffix.SUFFIX / 'manifest.json'
    suffix_sha = sha(suffix_path)
    suffix.validate_manifest(suffix_path, suffix_sha)
    computed = suffix.reconcile(suffix_path, suffix_sha)
    saved_path = suffix.SUFFIX / 'reconciliation.json'
    if not saved_path.is_file():
        raise ValueError('First-phase suffix lacks saved closed 59/60 reconciliation')
    saved = json.loads(saved_path.read_text())
    positions = computed.get('positions') or []
    if (saved != computed or computed.get('status') != 'closed_with_service_error' or
            computed.get('denominator') != 60 or computed.get('valid') != 59 or
            computed.get('status_counts') != {'ok': 59, 'service_error': 1} or
            computed.get('pending_unknown_reserve_usd') != '0' or
            computed.get('strict_complete_pass') is not False or
            [p.get('id') for p in positions] != IDS or
            positions[5].get('status') != 'service_error' or
            any(p.get('status') != 'ok' for p in positions[:5] + positions[6:])):
        raise ValueError('First-phase suffix is not the exact closed 59/60 composite')
    schedule = [(fresh, condition) for fresh, order in admission.ORDERS.items()
                for condition in order]
    if any((phase.get('repeat'), phase.get('condition')) != schedule[index] or
           phase.get('smoke_ids') != IDS[:3] or phase.get('development_ids') != IDS
           for index, phase in enumerate(original_manifest['phases'])):
        raise ValueError('Original counterbalanced phase order differs')
    budget_path = BASE / 'budget.json'
    budget = json.loads(budget_path.read_text())
    matches = [entry for entry in budget.get('partitions', []) if
               entry.get('id') == suffix.PARTITION]
    if (budget.get('version') != 'paid-partitions-v1' or
            budget.get('master_ledger') != str(admission.MASTER.resolve()) or
            len(matches) != 1 or
            (matches[0].get('model'), matches[0].get('provider'),
             matches[0].get('reasoning'), matches[0].get('cap_usd')) !=
            (admission.MODEL, admission.PROVIDER, 'off', '0.15') or
            Path(matches[0]['child_ledger']).resolve() !=
            (BASE / f'budget-{suffix.PARTITION}.jsonl').resolve()):
        raise ValueError('Exact active child budget manifest differs')
    return original_manifest, {
        'original_manifest': binding(original_path),
        'suffix_manifest': binding(suffix_path),
        'suffix_controller': binding(suffix.__file__),
        'suffix_reconciliation': binding(saved_path),
        'budget_manifest': binding(budget_path)}


def condition_requests(manifest):
    history, controls, endpoint, model = admission.source_state()
    inputs = read_rows(admission.INPUTS)
    if [row.get('id') for row in inputs] != IDS:
        raise ValueError('Original ordered 60 inputs differ')
    schema = controls['response_format']['json_schema']['schema']
    result = {}
    for condition in ('P0', 'P1', 'P2'):
        source = (history['baseline_instruction'] if condition == 'P0' else
                  history['conditions'][condition]['instruction'])
        policy = (ROOT / source['file']).read_text()
        frozen = manifest['requests_by_condition'][condition]
        if [item.get('id') for item in frozen] != IDS:
            raise ValueError('Frozen condition request membership differs')
        result[condition] = []
        for row, item in zip(inputs, frozen):
            payload = paid.make_payload(admission.MODEL, endpoint, row['feedback'],
                                        policy, schema, 'off', 4096,
                                        paid.number('0.1'), paid.number('0.9'), model)
            if (digest(json.dumps(payload, sort_keys=True)) != item['request_sha256'] or
                    digest(row['feedback']) != item['input_sha256'] or
                    digest(policy) != item['instruction_sha256']):
                raise ValueError('Original condition request bytes differ')
            result[condition].append({'id': row['id'], 'payload': payload,
                'request_sha256': item['request_sha256'],
                'input_sha256': item['input_sha256'],
                'instruction_sha256': item['instruction_sha256']})
    return result


def expected_manifest():
    original_manifest, sources = source_context()
    return {'schema': SCHEMA, 'status': 'FROZEN',
            'configuration': admission.CONFIG,
            'method': 'descriptive-continuation-after-service-error',
            'clean_matched_three_eligible': False,
            'first_phase': {'repeat': 'fresh1', 'condition': 'P0',
                            'status': 'closed_with_service_error', 'valid': 59,
                            'denominator': 60, 'failed_id': 'DEV-006'},
            'phases': original_manifest['phases'],
            'successor_phase_indices': list(range(FIRST, LAST + 1)),
            'requests_by_condition': condition_requests(original_manifest),
            'route': original_manifest['route'], 'sources': sources,
            'controller': binding(__file__),
            'output_directory': str(OUTPUT.resolve().relative_to(ROOT.resolve())),
            'partition_id': suffix.PARTITION, 'child_cap_usd': '0.15',
            'reserve_usd': str(admission.RESERVE)}


def freeze(path):
    if Path(path).resolve() != (OUTPUT / 'manifest.json').resolve():
        raise ValueError('Successor manifest must use its unique directory')
    manifest = expected_manifest()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    original.atomic_json(path, manifest)
    return manifest


def validate_manifest(path, expected_sha):
    path = Path(path).resolve()
    if path != (OUTPUT / 'manifest.json').resolve() or sha(path) != expected_sha:
        raise ValueError('Exact successor manifest path or hash differs')
    manifest = json.loads(path.read_text())
    if manifest != expected_manifest():
        raise ValueError('Successor manifest differs from bound closed sources')
    return manifest


def verify_static_sources(manifest):
    for item in manifest['sources'].values():
        read_bound(item)
    read_bound(manifest['controller'])
    original.verify_sources(json.loads(read_bound(manifest['sources']['original_manifest']).read_text()))


def stage_paths(index, stage):
    if type(index) is not int or not FIRST <= index <= LAST or stage not in ('smoke', 'development'):
        raise ValueError('Unknown successor stage')
    return original.paths(OUTPUT, index, stage)


def stage_review_path(index, stage):
    return OUTPUT / f'phase-{index + 1:02d}-{stage}.root-review.json'


def finished(manifest, manifest_sha, index, stage):
    return original.finished(manifest, OUTPUT, index, stage, manifest_sha,
                             manifest['sources']['budget_manifest']['sha256'],
                             manifest['partition_id'])


def verify_review(path, manifest, manifest_sha, index, stage):
    if Path(path).resolve() != stage_review_path(index, stage).resolve():
        raise ValueError('Stage review path differs')
    receipt = json.loads(Path(path).read_text())
    expected = {'schema': SCHEMA + '-stage-review', 'approved': True,
        'manifest_sha256': manifest_sha,
        'controller_sha256': manifest['controller']['sha256'],
        'original_manifest_sha256': manifest['sources']['original_manifest']['sha256'],
        'suffix_reconciliation_sha256': manifest['sources']['suffix_reconciliation']['sha256'],
        'budget_manifest_sha256': manifest['sources']['budget_manifest']['sha256'],
        'partition_id': manifest['partition_id'], 'phase_index': index,
        'stage': stage}
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError('Exact successor stage review differs')
    return receipt


def prepare(manifest_path, manifest_sha, budget_path, index, stage, review_path):
    manifest = validate_manifest(manifest_path, manifest_sha)
    if type(index) is not int or index not in manifest['successor_phase_indices']:
        raise ValueError('Successor phase index differs')
    phase = manifest['phases'][index]
    budget_path = Path(budget_path).resolve()
    if budget_path != read_bound(manifest['sources']['budget_manifest']):
        raise ValueError('Exact original child budget manifest required')
    receipt = verify_review(review_path, manifest, manifest_sha, index, stage)
    for predecessor in range(FIRST, index):
        if not (finished(manifest, manifest_sha, predecessor, 'smoke') and
                finished(manifest, manifest_sha, predecessor, 'development')):
            raise ValueError('Previous successor phase lacks strict closed evidence')
    if stage == 'development':
        smoke = stage_paths(index, 'smoke')
        inspection = receipt.get('smoke_inspection') or {}
        if (not finished(manifest, manifest_sha, index, 'smoke') or
                inspection.get('approved') is not True or
                inspection.get('statuses') != ['ok'] * 3 or
                any(inspection.get('smoke_' + key + '_sha256') != sha(smoke[key])
                    for key in ('records', 'journal', 'raw'))):
            raise ValueError('Exact inspected successor smoke required')
    target = stage_paths(index, stage)
    if any(path.exists() for path in target.values()):
        raise FileExistsError('Successor stage already claimed; no replay')
    return manifest, phase, target


def execute(manifest_path, manifest_sha, budget_path, index, stage, review_path,
            env_file=None):
    manifest, phase, target = prepare(manifest_path, manifest_sha, budget_path,
                                      index, stage, review_path)
    suffix_manifest = json.loads(read_bound(manifest['sources']['suffix_manifest']).read_text())
    model, endpoint = suffix.live_controls(suffix_manifest)
    selected = manifest['requests_by_condition'][phase['condition']]
    if stage == 'smoke':
        selected = selected[:3]
    ledger = partitions.open_partition(admission.MASTER, budget_path, manifest['partition_id'],
                                       admission.MODEL, admission.PROVIDER, 'off')
    try:
        _, pending, blocked = ledger.state()
        if pending or blocked or ledger.closed:
            raise ValueError('Original child budget has pending, blocked or closed state')
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
                    raise ValueError('Frozen successor request differs before call')
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
                       'condition': phase['condition'], 'phase': stage,
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    f = sub.add_parser('freeze'); f.add_argument('--manifest', required=True)
    v = sub.add_parser('validate'); v.add_argument('--manifest', required=True)
    v.add_argument('--sha256', required=True)
    e = sub.add_parser('execute-stage')
    for name in ('manifest', 'sha256', 'budget', 'review'):
        e.add_argument('--' + name, required=True)
    e.add_argument('--phase-index', required=True, type=int)
    e.add_argument('--stage', required=True, choices=('smoke', 'development'))
    e.add_argument('--env-file')
    args = parser.parse_args()
    if args.command == 'freeze':
        freeze(args.manifest)
        print(json.dumps({'manifest_sha256': sha(args.manifest), 'phases': 8}))
    elif args.command == 'validate':
        validate_manifest(args.manifest, args.sha256)
        print(json.dumps({'validated': True}))
    else:
        print(json.dumps(execute(args.manifest, args.sha256, args.budget,
            args.phase_index, args.stage, args.review, args.env_file)))


if __name__ == '__main__':
    main()
