#!/usr/bin/env python3
"""Explicit, non-replayable fresh3 Qwen3.6 35B A3B execution from a frozen admission plan.

Freeze is offline. Execution needs a separate exact review receipt for each stage.
A crash, failed response, invalid output, or unknown cost ends that stage; there
is deliberately no resume command. The operator may inspect/reconcile evidence,
but this runner will never send the same scheduled stage again.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import time
from urllib.parse import quote

import qwen36_off_fresh_repeat_admission as admission
from development_benchmark import ROOT, digest, read_rows, valid
import openrouter_paid_benchmark as paid
from openrouter_benchmark import allowed_returned_models
import paid_budget_partitions_v2 as partitions

CODE = ('qwen36_off_fresh_repeat_admission.py', 'qwen36_off_fresh_repeat_execution_v2.py',
        'openrouter_paid_benchmark.py', 'openrouter_benchmark.py',
        'openrouter_budget_v2.py', 'paid_budget_partitions_v2.py', 'development_benchmark.py')
MUTABLE = {'results/openrouter-paid-budget.jsonl'}
OUTPUT_DIR = ROOT / 'results/repeatability-v1/qwen36-off-fresh3-v2'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_json(path, value):
    path = Path(path)
    with path.open('x') as out:
        out.write(json.dumps(value, indent=2) + '\n')
        out.flush()
        import os
        os.fsync(out.fileno())


def jsonl(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def checked_path(value):
    path = Path(value).resolve()
    path.relative_to(ROOT)
    return path


def verify_sources(manifest):
    for source in manifest['source_bindings']:
        if source['path'] in MUTABLE:
            continue  # Original master snapshot remains admission provenance.
        path = checked_path(ROOT / source['path'])
        if sha(path) != source['sha256']:
            raise ValueError('Source drift: ' + source['path'])
    for source in manifest['code_bindings']:
        path = checked_path(ROOT / source['path'])
        if sha(path) != source['sha256']:
            raise ValueError('Execution code drift: ' + source['path'])


def freeze(plan_path, manifest_path):
    """Bind a reviewed admission plan and executing code, without touching a key or ledger."""
    plan_path, manifest_path = checked_path(plan_path), checked_path(manifest_path)
    if manifest_path.exists():
        raise FileExistsError(manifest_path)
    plan = json.loads(plan_path.read_text())
    if (plan.get('schema') != 'affordable-hosted-repeat-admission-v1' or
        plan.get('configuration_id') != admission.CONFIG or plan.get('series') != 'fresh-matched3' or
        plan.get('historical_first_pass_eligible') is not False or
        plan.get('request_count') != 567 or len(plan.get('phases', [])) != 9 or
        plan.get('budget', {}).get('proposed_child_cap_usd') != str(admission.CAP) or
        plan['budget'].get('per_call_reserve_usd') != str(admission.RESERVE) or
        plan.get('orders') != {k: list(v) for k, v in admission.ORDERS.items()}):
        raise ValueError('Admission plan contract differs')
    # Planner recomputation is permitted only at freeze: its live ledger snapshot
    # will naturally change after partition allocation.
    expected = admission.plan_data()
    if plan != expected:
        raise ValueError('Admission plan differs from current frozen sources/ledger')
    manifest = {'schema': 'affordable-hosted-fresh3-execution-v2',
                'admission_plan': str(plan_path.relative_to(ROOT)),
                'admission_plan_sha256': sha(plan_path),
                'configuration_id': admission.CONFIG, 'series': 'fresh-matched3',
                'phases': plan['phases'], 'requests_by_condition': plan['requests_by_condition'],
                'budget': plan['budget'], 'route': plan['route'],
                'source_bindings': plan['source_bindings'],
                'code_bindings': [{'path': 'scripts/' + name,
                                   'sha256': sha(ROOT / 'scripts' / name)} for name in CODE]}
    atomic_json(manifest_path, manifest)
    return manifest


def load_manifest(path, expected_sha):
    path = checked_path(path)
    if sha(path) != expected_sha:
        raise ValueError('Manifest hash mismatch')
    manifest = json.loads(path.read_text())
    if manifest.get('schema') != 'affordable-hosted-fresh3-execution-v2' or manifest.get('configuration_id') != admission.CONFIG:
        raise ValueError('Manifest contract differs')
    plan = checked_path(ROOT / manifest['admission_plan'])
    if sha(plan) != manifest['admission_plan_sha256']:
        raise ValueError('Admission plan drift')
    verify_sources(manifest)
    return manifest


def paths(directory, index, stage):
    base = checked_path(directory) / ('phase-%02d-%s' % (index + 1, stage))
    return {name: Path(str(base) + suffix) for name, suffix in
            (('claim', '.claim.json'), ('journal', '.journal.jsonl'),
             ('raw', '.raw.jsonl'), ('records', '.records.jsonl'))}


def finished(manifest, directory, index, stage, manifest_sha, budget_sha, partition_id):
    """Admit only a complete stage whose four artifacts describe the same calls."""
    p = paths(directory, index, stage)
    if not all(path.exists() for path in p.values()):
        return False
    try:
        phase = manifest['phases'][index]
        ids = phase['smoke_ids'] if stage == 'smoke' else phase['development_ids']
        frozen = manifest['requests_by_condition'][phase['condition']]
        by_id = {item['id']: item for item in frozen}
        if len(by_id) != len(frozen) or [item['id'] for item in frozen[:len(ids)]] != ids:
            return False
        claim = json.loads(p['claim'].read_text())
        expected_claim = {'schema': 'affordable-hosted-stage-claim-v1',
                          'manifest_sha256': manifest_sha,
                          'budget_manifest_sha256': budget_sha,
                          'partition_id': partition_id, 'phase_index': index,
                          'repeat': phase['repeat'], 'condition': phase['condition'],
                          'stage': stage, 'ids': ids}
        if any(claim.get(key) != value for key, value in expected_claim.items()):
            return False
        if (not isinstance(claim.get('review_sha256'), str) or
            len(claim['review_sha256']) != 64 or
            any(ch not in '0123456789abcdef' for ch in claim['review_sha256'])):
            return False
        events, rows = jsonl(p['journal']), jsonl(p['records'])
        raw_bytes = p['raw'].read_bytes()
        raw_lines = raw_bytes.splitlines(keepends=True)
        raw_rows = [json.loads(line) for line in raw_lines]
        if (len(rows) != len(ids) or len(raw_rows) != len(ids) or
            len(events) != 2 + 3 * len(ids) or
            events[0] != {'event': 'stage_claimed', 'claim_sha256': sha(p['claim'])} or
            events[-1] != {'event': 'stage_completed', 'count': len(ids)}):
            return False
        seen_attempts = set()
        for position, (record_id, row, raw) in enumerate(zip(ids, rows, raw_rows)):
            started, saved, ended = events[1 + 3 * position:4 + 3 * position]
            attempt = row['attempt_id']
            frozen_item = by_id[record_id]
            request_sha = frozen_item['request_sha256']
            if (not isinstance(attempt, str) or not attempt or attempt in seen_attempts or
                started != {'event': 'request_started', 'attempt_id': attempt,
                            'id': record_id, 'request_sha256': request_sha,
                            'reserved_cost_usd': str(admission.RESERVE)} or
                saved != {'event': 'raw_saved', 'attempt_id': attempt,
                          'raw_sha256': hashlib.sha256(b''.join(raw_lines[:position + 1])).hexdigest()} or
                ended != {'event': 'request_finished', 'attempt_id': attempt,
                          'id': record_id, 'status': 'ok', 'billing_ok': True} or
                raw != {'attempt_id': attempt, 'id': record_id, 'body': row['raw_response']}):
                return False
            seen_attempts.add(attempt)
            request_start = datetime.fromisoformat(row['client_request_started_utc'])
            request_end = datetime.fromisoformat(row['client_request_finished_utc'])
            duration = row['client_http_duration_seconds']
            if (request_start.utcoffset() != timezone.utc.utcoffset(None) or
                request_end.utcoffset() != timezone.utc.utcoffset(None) or
                request_end < request_start or type(duration) not in (int, float) or
                not math.isfinite(duration) or duration < 0):
                return False
            body = raw['body']
            choice = body['choices'][0]
            message = choice['message']
            prediction = json.loads(message['content'])
            if (len(body['choices']) != 1 or not valid(prediction) or
                choice.get('finish_reason') != 'stop' or choice.get('error') or
                message.get('refusal') or message.get('tool_calls') or message.get('function_call') or
                row.get('id') != record_id or row.get('repeat') != phase['repeat'] or
                row.get('condition') != phase['condition'] or row.get('phase') != stage or
                row.get('budget_partition_id') != partition_id or
                row.get('request_sha256') != request_sha or
                digest(json.dumps(row['request'], sort_keys=True)) != request_sha or
                row.get('input_sha256') != frozen_item['input_sha256'] or
                row.get('policy_sha256') != frozen_item['instruction_sha256'] or
                row.get('reserved_cost_usd') != str(admission.RESERVE) or
                row.get('requested_model') != admission.MODEL or
                row.get('reasoning_effort') != 'off' or
                row['provider_endpoint'].get('tag') != admission.PROVIDER or
                row['provider_endpoint'].get('provider_name') != manifest['route']['provider_name'] or
                row['provider_endpoint'].get('quantization') != manifest['route']['quantization'] or
                row.get('reference_labels_read') is not False or
                row.get('prediction') != prediction or row.get('usage') != body.get('usage') or
                row.get('returned_model') != body.get('model') or
                row.get('returned_provider') != body.get('provider') or
                row.get('finish_reason') != choice.get('finish_reason') or
                body.get('provider') != row['provider_endpoint']['provider_name'] or
                body.get('model') not in allowed_returned_models(admission.MODEL, row['provider_endpoint']) or
                row.get('status') != 'ok' or row.get('billing_ok') is not True or
                row.get('cost_unknown') is not False or
                row.get('observed_cost_usd') != str(paid.number(body['usage']['cost']))):
                return False
        return True
    except (ValueError, TypeError, KeyError, IndexError, AttributeError, OSError):
        return False


def inspect_predecessors(manifest, directory, index, stage, review, manifest_sha, budget_sha, partition_id):
    phases = manifest['phases']
    for previous in range(index):
        p = phases[previous]
        if (not finished(manifest, directory, previous, 'smoke', manifest_sha, budget_sha, partition_id) or
            not finished(manifest, directory, previous, 'development', manifest_sha, budget_sha, partition_id)):
            raise ValueError('Previous phase is not terminal complete')
    if stage == 'development':
        smoke = paths(directory, index, 'smoke')
        if not finished(manifest, directory, index, 'smoke', manifest_sha, budget_sha, partition_id):
            raise ValueError('Smoke is not terminal complete and clean')
        inspection = review.get('smoke_inspection')
        if (not isinstance(inspection, dict) or inspection.get('approved') is not True or
            inspection.get('smoke_records_sha256') != sha(smoke['records']) or
            inspection.get('smoke_journal_sha256') != sha(smoke['journal']) or
            inspection.get('smoke_raw_sha256') != sha(smoke['raw']) or
            inspection.get('statuses') != ['ok'] * 3):
            raise ValueError('Missing exact inspected smoke receipt')


def verify_receipt(receipt_path, manifest_path, manifest_sha, budget_path, partition_id, index, stage):
    receipt = json.loads(checked_path(receipt_path).read_text())
    expected = {'approved': True, 'manifest_sha256': manifest_sha,
                'budget_manifest_sha256': sha(budget_path), 'partition_id': partition_id,
                'phase_index': index, 'stage': stage,
                'runner_sha256': sha(__file__)}
    if any(receipt.get(k) != v for k, v in expected.items()):
        raise ValueError('Missing exact phase/stage review receipt')
    return receipt


def prepare(manifest_path, manifest_sha, budget_path, partition_id, index, stage, review_path, directory):
    manifest = load_manifest(manifest_path, manifest_sha)
    if checked_path(directory) != OUTPUT_DIR:
        raise ValueError('Execution output must use the unique Qwen series directory')
    if type(index) is not int or not 0 <= index < 9 or stage not in ('smoke', 'development'):
        raise ValueError('Invalid stage')
    phase = manifest['phases'][index]
    if (phase['repeat'], phase['condition']) != tuple((r, c) for r, order in admission.ORDERS.items() for c in order)[index]:
        raise ValueError('Schedule drift')
    budget_path = checked_path(budget_path)
    review = verify_receipt(review_path, manifest_path, manifest_sha, budget_path, partition_id, index, stage)
    inspect_predecessors(manifest, directory, index, stage, review,
                         manifest_sha, sha(budget_path), partition_id)
    p = paths(directory, index, stage)
    if any(path.exists() for path in p.values()):
        raise FileExistsError('Stage already claimed; no replay')
    budget = json.loads(budget_path.read_text())
    entries = [e for e in budget.get('partitions', []) if e.get('id') == partition_id]
    if (len(entries) != 1 or budget.get('master_ledger') != str(admission.MASTER.resolve()) or
        (entries[0]['model'], entries[0]['provider'], entries[0]['reasoning']) !=
        (admission.MODEL, admission.PROVIDER, 'off') or
        not admission.RESERVE <= paid.number(entries[0]['cap_usd']) <= admission.CAP):
        raise ValueError('Exact child partition differs')
    return manifest, phase, p


def execute(manifest_path, manifest_sha, budget_path, partition_id, index, stage, review_path, directory, env_file=None):
    manifest, phase, p = prepare(manifest_path, manifest_sha, budget_path, partition_id, index, stage, review_path, directory)
    history, controls, historical_endpoint, historical_model = admission.source_state()
    rows = read_rows(admission.INPUTS)
    ids = phase['smoke_ids'] if stage == 'smoke' else phase['development_ids']
    selected = rows[:len(ids)]
    policy_source = history['baseline_instruction'] if phase['condition'] == 'P0' else history['conditions'][phase['condition']]['instruction']
    policy = (ROOT / policy_source['file']).read_text()
    schema = controls['response_format']['json_schema']['schema']
    payloads = [paid.make_payload(admission.MODEL, historical_endpoint, row['feedback'], policy, schema,
                                  'off', 4096, paid.number('0.1'), paid.number('0.9'), historical_model)
                for row in selected]
    frozen = manifest['requests_by_condition'][phase['condition']]
    for row, payload, item in zip(selected, payloads, frozen):
        if (row['id'] != item['id'] or digest(json.dumps(payload, sort_keys=True)) != item['request_sha256'] or
            digest(row['feedback']) != item['input_sha256'] or digest(policy) != item['instruction_sha256']):
            raise ValueError('Frozen exact request differs')
    # Catalog check precedes claim, key access, and any reservation.
    catalog = paid.fetch('/models', timeout=300)
    endpoints = paid.fetch('/models/' + quote(admission.MODEL, safe='/') + '/endpoints', timeout=300)
    live_model, live_endpoint = paid.select_endpoint(admission.MODEL, admission.PROVIDER, catalog, endpoints,
                                                       paid.number('0.1'), paid.number('0.9'))
    critical_endpoint = ('tag', 'provider_name', 'quantization', 'model_id',
                         'context_length', 'pricing', 'supported_parameters')
    if (any(live_endpoint.get(key) != historical_endpoint.get(key) for key in critical_endpoint) or
        paid.reasoning(live_model, live_endpoint, 'off') != {'enabled': False}):
        raise ValueError('Live route, price or reasoning support differs from frozen snapshot')
    if paid.reservation(live_endpoint, 4096, paid.number('0.1'), paid.number('0.9')) != admission.RESERVE:
        raise ValueError('Live reserve differs')
    verify_sources(manifest)
    token = paid.load_key(env_file)
    ledger = partitions.open_partition(admission.MASTER, budget_path, partition_id,
                                       admission.MODEL, admission.PROVIDER, 'off')
    try:
        claim = {'schema': 'affordable-hosted-stage-claim-v1', 'manifest_sha256': manifest_sha,
                 'review_sha256': sha(review_path), 'budget_manifest_sha256': sha(budget_path),
                 'partition_id': partition_id, 'phase_index': index, 'repeat': phase['repeat'],
                 'condition': phase['condition'], 'stage': stage, 'ids': ids}
        atomic_json(p['claim'], claim)
        with p['journal'].open('x') as journal, p['raw'].open('x') as raw, p['records'].open('x') as records:
            paid.durable(journal, {'event': 'stage_claimed', 'claim_sha256': sha(p['claim'])})
            for row, payload in zip(selected, payloads):
                verify_sources(manifest)
                request_sha = digest(json.dumps(payload, sort_keys=True))
                if request_sha != frozen[int(row['id'][4:]) - 1]['request_sha256']:
                    raise ValueError('Request changed before call')
                attempt = ledger.reserve(admission.RESERVE, row['id'])
                started = {'event': 'request_started', 'attempt_id': attempt, 'id': row['id'],
                           'request_sha256': request_sha, 'reserved_cost_usd': str(admission.RESERVE)}
                paid.durable(journal, started)
                result = {'id': row['id'], 'repeat': phase['repeat'], 'condition': phase['condition'],
                          'phase': stage, 'attempt_id': attempt, 'request': payload,
                          'request_sha256': request_sha, 'input_sha256': digest(row['feedback']),
                          'policy_sha256': digest(policy), 'requested_model': admission.MODEL,
                          'provider_endpoint': live_endpoint, 'model_catalog_entry': live_model,
                          'reference_labels_read': False, 'reserved_cost_usd': str(admission.RESERVE),
                          'budget_partition_id': partition_id, 'reasoning_effort': 'off',
                          'continue_on_invalid_output': False, 'retry_policy': 'none'}
                actual = None
                try:
                    # This measures the client HTTP call, not provider inference time.
                    result['client_request_started_utc'] = datetime.now(timezone.utc).isoformat()
                    request_start = time.monotonic()
                    try:
                        body = paid.fetch('/chat/completions', token, payload, 300)
                    finally:
                        result['client_http_duration_seconds'] = time.monotonic() - request_start
                        result['client_request_finished_utc'] = datetime.now(timezone.utc).isoformat()
                    body = json.loads(json.dumps(body).replace(token, '[REDACTED]'))
                    # Persist complete provider result before parsing or accounting.
                    paid.durable(raw, {'attempt_id': attempt, 'id': row['id'], 'body': body})
                    paid.durable(journal, {'event': 'raw_saved', 'attempt_id': attempt, 'raw_sha256': sha(p['raw'])})
                    result['raw_response'] = body
                    usage = body.get('usage') or {}
                    result['usage'] = usage
                    if usage.get('cost') is not None:
                        actual = paid.number(usage['cost'])
                    choices = body['choices']
                    if not isinstance(choices, list) or len(choices) != 1:
                        raise ValueError('Expected exactly one choice')
                    choice = choices[0]
                    message = choice['message']
                    result.update(returned_model=body.get('model'), returned_provider=body.get('provider'),
                                  finish_reason=choice.get('finish_reason'))
                    try: prediction = json.loads(message.get('content'))
                    except (ValueError, TypeError): prediction = None
                    result['prediction'] = prediction
                    result['status'] = ('ok' if valid(prediction) and choice.get('finish_reason') == 'stop'
                                        and not choice.get('error') and not message.get('refusal')
                                        and not message.get('tool_calls') and not message.get('function_call')
                                        else 'invalid_output')
                    if body.get('model') not in allowed_returned_models(admission.MODEL, live_endpoint):
                        result['status'] = 'model_mismatch'
                    if body.get('provider') != live_endpoint['provider_name']:
                        result['status'] = 'provider_mismatch'
                except Exception as exc:
                    if 'status' not in result:
                        result.update(status='service_error', error_type=type(exc).__name__)
                        if hasattr(exc, 'code'):
                            result['http_status'] = exc.code
                        if hasattr(exc, 'read'):
                            try:
                                raw_error = exc.read(1000000).decode(errors='replace').replace(token, '[REDACTED]')
                                paid.durable(raw, {'attempt_id': attempt, 'id': row['id'],
                                                   'error_body': raw_error})
                                result['raw_error_response'] = raw_error
                            except Exception:
                                pass
                billing_ok = ledger.settle(attempt, actual)
                result.update(observed_cost_usd=str(actual) if actual is not None else None,
                              cost_unknown=actual is None, billing_ok=billing_ok)
                paid.durable(records, result)
                paid.durable(journal, {'event': 'request_finished', 'attempt_id': attempt,
                                       'id': row['id'], 'status': result['status'], 'billing_ok': billing_ok})
                if result['status'] != 'ok' or not billing_ok or actual is None:
                    return result
            paid.durable(journal, {'event': 'stage_completed', 'count': len(ids)})
    finally:
        ledger.close()
    return {'completed': True, 'count': len(ids)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    f = sub.add_parser('freeze')
    f.add_argument('--plan', required=True); f.add_argument('--manifest', required=True)
    e = sub.add_parser('execute-stage')
    for flag in ('manifest', 'sha256', 'budget', 'partition-id', 'review', 'output-dir'):
        e.add_argument('--' + flag, required=True)
    e.add_argument('--phase-index', type=int, required=True, help='Zero-based phase in frozen schedule')
    e.add_argument('--stage', choices=('smoke', 'development'), required=True)
    e.add_argument('--env-file')
    args = parser.parse_args()
    if args.command == 'freeze':
        result = freeze(args.plan, args.manifest)
        print(json.dumps({'manifest_sha256': sha(args.manifest), 'phases': len(result['phases'])}))
    else:
        result = execute(args.manifest, args.sha256, args.budget, args.partition_id,
                         args.phase_index, args.stage, args.review, args.output_dir, args.env_file)
        print(json.dumps(result))


if __name__ == '__main__':
    main()
