#!/usr/bin/env python3
"""Versioned DEV-051..060 continuation after the sealed DeepSeek low DEV-050 failure.

Only the provider output-price ceiling and its conservative reserve change.
Preparation and verification are offline. Dispatch needs a separate reviewed
receipt, an allocated child and a fixed shared paid-work hold.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
import fcntl
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.error
from urllib.parse import quote

from development_benchmark import ROOT, digest, read_rows
import deepseek_low_fresh_repeat_admission as admission
import deepseek_low_second_interruption as prior
import deepseek_low_fresh_repeat_execution_v2 as frozen
import openrouter_paid_benchmark as paid
import paid_budget_partitions_v3 as partitions
import qwen27_fresh_repeat_execution as transport

SCHEMA = 'deepseek-low-third-suffix-051-060-v1'
BASE = prior.BASE / 'third-interruption-suffix-051-060-v1'
MANIFEST = BASE / 'manifest.json'
AUDIT = BASE / 'route-audit.json'
RAW_MODELS = BASE / 'models.json'
RAW_ENDPOINTS = BASE / 'endpoints.json'
PARTITION_ID = 'deepseek-low-third-suffix-051-060-v1'
CHILD_CAP = Decimal('0.25')
INPUT_CEILING = Decimal('0.1')
OUTPUT_CEILING = Decimal('1.2')
RESERVE = Decimal('0.1097728')
IDS = [f'DEV-{n:03d}' for n in range(51, 61)]
PRIOR_MANIFEST_SHA = 'd1f051e73960ee936d645989105caf6a8e0c1c5a4461958fc7b9a3d1e51f2e98'
PRIOR_TERMINAL_SHA = 'afebe495074a2af03da0e2516d921fb40c04f4a32c359fa117443884a688af30'
PRIOR_CHILD_SHA = '3fc303be7d6bf61e0919be0220ca80f8c97fd39eb2862a87cf6a6066b0c4d5b3'
AUTHORITY = ROOT / 'results/postapproval-paid-work-2026-10-02.jsonl'
AUTHORITY_ID = PARTITION_ID
AUTHORITY_CAP = Decimal('10.00')
AUTHORITY_DECISION_KEY = 'candidate-experience-benchmark/user-ten-dollar-tests-20261002'
AUTHORITY_APPROVAL_SHA = '57d5ff76acd14f85d5e600c6527c310fc08f4eb66d45b1c25b9d778d770aaf8f'
ROUTE_FIELDS = ('tag', 'provider_name', 'quantization', 'model_id',
                'context_length', 'max_prompt_tokens', 'max_completion_tokens',
                'supported_parameters')
SOURCES = ('scripts/deepseek_low_third_suffix_v1.py',
           'scripts/deepseek_low_second_interruption.py',
           'scripts/deepseek_low_fresh_repeat_execution_v2.py',
           'scripts/openrouter_paid_benchmark.py',
           'scripts/paid_budget_partitions_v3.py',
           'scripts/openrouter_budget_v3.py',
           'scripts/qwen27_fresh_repeat_execution.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    raw = Path(path).read_bytes()
    if raw and not raw.endswith(b'\n'):
        raise ValueError('Incomplete JSONL source')
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def bound(path):
    path = Path(path).resolve()
    return {'path': str(path.relative_to(ROOT.resolve())), 'sha256': sha(path)}


def prior_gate():
    """Rebuild the original, first and second prefixes without accepting replay."""
    path = prior.OUTPUT / 'manifest.json'
    manifest = prior.validate_manifest(path, PRIOR_MANIFEST_SHA)
    projection = prior.reconcile_suffix(manifest, PRIOR_MANIFEST_SHA)
    terminal = prior.OUTPUT / 'terminal-reconciliation-after-dev050.json'
    child = prior.OUTPUT / f'budget-{prior.PARTITION_ID}.jsonl'
    saved_projection = prior.OUTPUT / 'phase-03-suffix.public.json'
    saved = json.loads(saved_projection.read_text())
    event = json.loads(terminal.read_text())
    if (projection != saved or sha(terminal) != PRIOR_TERMINAL_SHA or
            sha(child) != PRIOR_CHILD_SHA or
            event not in rows(admission.MASTER) or
            event.get('partition_id') != prior.PARTITION_ID or
            event.get('unknown_upper_bound_usd') != str(prior.RESERVE) or
            projection.get('status') != 'stopped' or
            projection.get('status_counts') != {'ok': 46, 'invalid_output': 1,
                'service_error': 3, 'never_sent': 10} or
            [p['id'] for p in projection['positions'] if p['status'] == 'never_sent'] != IDS or
            [(p['id'], p['status']) for p in projection['positions'] if
             p['status'] in ('invalid_output', 'service_error')] != [
                ('DEV-039', 'invalid_output'), ('DEV-040', 'service_error'),
                ('DEV-049', 'service_error'), ('DEV-050', 'service_error')]):
        raise ValueError('Sealed DEV-050 prefix differs')
    evidence = {name: bound(path) for name, path in {
        'prior_manifest': path, 'prior_terminal': terminal, 'prior_child': child,
        'prior_projection': saved_projection,
        **{f'prior_suffix_{key}': value for key, value in
           prior.stage_paths(2, 'suffix').items()},
        'prior_review': prior.review_path(2, 'suffix')}.items()}
    return manifest, evidence


def route_audit():
    """Bind a dated, uncredentialed public catalog snapshot."""
    catalog, endpoints = (json.loads(path.read_text()) for path in
                          (RAW_MODELS, RAW_ENDPOINTS))
    model, endpoint = paid.select_endpoint(admission.MODEL, admission.PROVIDER,
        catalog, endpoints, INPUT_CEILING, OUTPUT_CEILING)
    old_endpoint = admission.source_state()[2]
    if (any(endpoint.get(key) != old_endpoint.get(key) for key in ROUTE_FIELDS) or
            paid.reasoning(model, endpoint, 'low') != {'enabled': True, 'effort': 'low'} or
            paid.reservation(endpoint, 4096, INPUT_CEILING, OUTPUT_CEILING) != RESERVE):
        raise ValueError('Public endpoint identity, controls or reserve differ')
    for key, value in endpoint['pricing'].items():
        if key not in ('prompt', 'completion', 'input_cache_read') and \
                value != old_endpoint['pricing'].get(key):
            raise ValueError('Unreviewed endpoint price field changed')
    expected = {'schema': SCHEMA + '-public-route-audit',
        'scope': 'Uncredentialed public catalog metadata; no inference',
        'sources': [dict(bound(path), url=url) for path, url in (
            (RAW_MODELS, 'https://openrouter.ai/api/v1/models'),
            (RAW_ENDPOINTS, 'https://openrouter.ai/api/v1/models/' +
             admission.MODEL + '/endpoints'))],
        'model_id': admission.MODEL, 'provider_tag': admission.PROVIDER,
        'selected_model': model, 'selected_endpoint': endpoint,
        'old_output_ceiling_usd_per_million': '0.5',
        'new_output_ceiling_usd_per_million': str(OUTPUT_CEILING),
        'per_request_reserve_usd': str(RESERVE)}
    if json.loads(AUDIT.read_text()) != expected:
        raise ValueError('Public route audit differs')
    return expected


def requests(endpoint=None, model=None):
    plan = frozen.load_manifest(prior.BASE / 'manifest.json',
                               prior.lower_price.MANIFEST_SHA)
    history, controls, old_endpoint, old_model = admission.source_state()
    if endpoint is None or model is None:
        audit = route_audit()
        endpoint, model = audit['selected_endpoint'], audit['selected_model']
    phase = plan['phases'][2]
    if phase['repeat'] != 'fresh1' or phase['condition'] != 'P2':
        raise ValueError('Frozen phase identity changed')
    policy_source = history['conditions']['P2']['instruction']
    policy = (ROOT / policy_source['file']).read_text()
    schema = controls['response_format']['json_schema']['schema']
    inputs = read_rows(admission.INPUTS)
    if [row['id'] for row in inputs] != [f'DEV-{n:03d}' for n in range(1, 61)]:
        raise ValueError('Development roster changed')
    selected = []
    for row, item in zip(inputs[50:], plan['requests_by_condition']['P2'][50:]):
        old = paid.make_payload(admission.MODEL, old_endpoint, row['feedback'],
            policy, schema, 'low', 4096, INPUT_CEILING, Decimal('0.5'), old_model)
        new = paid.make_payload(admission.MODEL, endpoint, row['feedback'],
            policy, schema, 'low', 4096, INPUT_CEILING, OUTPUT_CEILING, model)
        sole_change = deepcopy(old)
        sole_change['provider']['max_price']['completion'] = float(OUTPUT_CEILING)
        if (item['id'] != row['id'] or digest(json.dumps(old, sort_keys=True)) !=
                item['request_sha256'] or new != sole_change or
                digest(row['feedback']) != item['input_sha256'] or
                digest(policy) != item['instruction_sha256']):
            raise ValueError('Suffix request changes beyond reviewed price ceiling')
        selected.append({'id': row['id'], 'old_request_sha256': item['request_sha256'],
            'request_sha256': digest(json.dumps(new, sort_keys=True)),
            'input_sha256': item['input_sha256'],
            'instruction_sha256': item['instruction_sha256']})
    if [item['id'] for item in selected] != IDS:
        raise ValueError('Suffix membership changed')
    return selected


def manifest_value():
    _, prior_sources = prior_gate()
    route_audit()
    return {'schema': SCHEMA, 'status': 'offline_prepared_no_allocation_or_dispatch',
        'configuration_id': admission.CONFIG + '-output-price-ceiling-1.2-v1',
        'original_configuration_id': admission.CONFIG,
        'method': 'descriptive_continuation_not_clean_matched_three',
        'fresh_pass': 'fresh1', 'condition': 'P2', 'stage': 'suffix',
        'ids': IDS, 'preserved_status_counts': {'ok': 46, 'invalid_output': 1,
            'service_error': 3, 'never_sent': 10},
        'preserved_failed_ids': ['DEV-040', 'DEV-049', 'DEV-050'],
        'preserved_invalid_ids': ['DEV-039'],
        'sources': {**prior_sources, 'route_audit': bound(AUDIT),
            'route_models': bound(RAW_MODELS), 'route_endpoints': bound(RAW_ENDPOINTS),
            **{name: bound(ROOT / name) for name in SOURCES}},
        'requests': requests(), 'partition_id': PARTITION_ID,
        'child_cap_usd': str(CHILD_CAP), 'per_request_reserve_usd': str(RESERVE),
        'global_hold_id': AUTHORITY_ID, 'global_hold_usd': str(CHILD_CAP),
        'reference_labels_read': False,
        'price_control_change': {'provider.max_price.completion_usd_per_million':
                                 ['0.5', str(OUTPUT_CEILING)]},
        'admission': 'independent review, fresh live route, allocated exact child, root stage receipt and fixed shared hold'}


def prepare():
    value = manifest_value()
    with MANIFEST.open('x') as file:
        json.dump(value, file, indent=2)
        file.write('\n'); file.flush(); os.fsync(file.fileno())
    return sha(MANIFEST)


def verify():
    value = manifest_value()
    if json.loads(MANIFEST.read_text()) != value:
        raise ValueError('Versioned suffix manifest changed')
    return value


def budget_entry(path):
    path = Path(path).resolve()
    if path != (BASE / 'budget.json').resolve():
        raise ValueError('Exact child budget path differs')
    budget = json.loads(path.read_text())
    entries = budget.get('partitions')
    child = BASE / f'budget-{PARTITION_ID}.jsonl'
    if (budget.get('version') != 'paid-partitions-v1' or
            budget.get('master_ledger') != str(admission.MASTER.resolve()) or
            not isinstance(entries, list) or len(entries) != 1):
        raise ValueError('Child budget manifest differs')
    entry = entries[0]
    if (entry.get('id') != PARTITION_ID or entry.get('cap_usd') != str(CHILD_CAP) or
            (entry.get('model'), entry.get('provider'), entry.get('reasoning')) !=
            (admission.MODEL, admission.PROVIDER, 'low') or
            Path(entry.get('child_ledger', '')).resolve() != child.resolve()):
        raise ValueError('Exact child identity or cap differs')
    return entry


def global_hold_source(budget_path):
    entry = budget_entry(budget_path)
    return hashlib.sha256(json.dumps({'successor_manifest_sha256': sha(MANIFEST),
        'budget_manifest_path': str(Path(budget_path).resolve()),
        'budget_manifest_sha256': sha(budget_path),
        'partition_id': PARTITION_ID, 'child_ledger': entry['child_ledger'],
        'model': entry['model'], 'provider': entry['provider'],
        'reasoning': entry['reasoning'], 'cap_usd': entry['cap_usd']},
        sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def hold_authority(expected_head, budget_path, expected_source):
    source = global_hold_source(budget_path)
    if source != expected_source:
        raise ValueError('Reviewed shared hold source differs')
    with AUTHORITY.open('r+') as file:
        fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        file.seek(0)
        raw = file.read().encode()
        if hashlib.sha256(raw).hexdigest() != expected_head:
            raise ValueError('Shared authority head changed')
        events = [json.loads(line) for line in raw.splitlines() if line.strip()]
        if not events or events[0] != {'event': 'authority',
                'kind': 'postapproval-paid-work-v1', 'cap_usd': str(AUTHORITY_CAP),
                'decision_key': AUTHORITY_DECISION_KEY,
                'approval_sha256': AUTHORITY_APPROVAL_SHA}:
            raise ValueError('Shared paid-work authority differs')
        holds = [e for e in events[1:] if e.get('event') == 'hold']
        if len(holds) != len(events) - 1 or len({e.get('id') for e in holds}) != len(holds):
            raise ValueError('Shared hold structure differs')
        desired = {'event': 'hold', 'id': AUTHORITY_ID,
                   'source_sha256': source, 'usd': str(CHILD_CAP)}
        existing = [e for e in holds if e['id'] == AUTHORITY_ID]
        total = sum((Decimal(e['usd']) for e in holds), Decimal(0))
        if total > AUTHORITY_CAP or (existing and existing != [desired]):
            raise ValueError('Shared hold conflicts or exceeds cap')
        if not existing:
            if total + CHILD_CAP > AUTHORITY_CAP:
                raise ValueError('Shared paid-work cap cannot fit child hold')
            file.seek(0, 2)
            paid.durable(file, desired)


def live_controls():
    """Permit only bounded selected-endpoint price drift from the public audit."""
    audit = route_audit()
    catalog = paid.fetch('/models', timeout=300)
    endpoints = paid.fetch('/models/' + quote(admission.MODEL, safe='/') +
                           '/endpoints', timeout=300)
    model, endpoint = paid.select_endpoint(admission.MODEL, admission.PROVIDER,
        catalog, endpoints, INPUT_CEILING, OUTPUT_CEILING)
    recorded = audit['selected_endpoint']
    if (any(endpoint.get(key) != recorded.get(key) for key in ROUTE_FIELDS) or
            set(endpoint.get('pricing', {})) != set(recorded['pricing']) or
            any(endpoint['pricing'][key] != recorded['pricing'][key] for key in
                recorded['pricing'] if key not in ('prompt', 'completion', 'input_cache_read')) or
            paid.reasoning(model, endpoint, 'low') != {'enabled': True, 'effort': 'low'} or
            paid.reservation(endpoint, 4096, INPUT_CEILING, OUTPUT_CEILING) != RESERVE):
        raise ValueError('Live route, reasoning or reserve changed')
    selected = requests(endpoint, model)
    if selected != verify()['requests']:
        raise ValueError('Live request hash changed')
    return model, endpoint


def stage_paths():
    return {kind: BASE / ('suffix.' + suffix) for kind, suffix in {
        'claim': 'claim.json', 'journal': 'journal.jsonl',
        'raw': 'raw.jsonl', 'records': 'records.jsonl'}.items()}


def run(receipt_path, budget_path, env_file=None):
    manifest = verify()
    receipt_path = Path(receipt_path).resolve()
    if receipt_path != (BASE / 'suffix.root-review.json').resolve():
        raise ValueError('Exact stage review path differs')
    receipt = json.loads(receipt_path.read_text())
    budget_path = Path(budget_path).resolve()
    expected = {'schema': SCHEMA + '-root-review', 'approved': True,
        'reviewer': receipt.get('reviewer'),
        'manifest_sha256': sha(MANIFEST),
        'controller_sha256': sha(__file__),
        'prior_terminal_sha256': PRIOR_TERMINAL_SHA,
        'budget_manifest_sha256': sha(budget_path),
        'partition_id': PARTITION_ID, 'child_cap_usd': str(CHILD_CAP),
        'ids': IDS, 'request_sha256': [r['request_sha256'] for r in manifest['requests']],
        'global_authority_head_sha256': receipt.get('global_authority_head_sha256'),
        'global_hold_source_sha256': global_hold_source(budget_path)}
    if (not isinstance(receipt.get('reviewer'), str) or
            not receipt['reviewer'].strip() or
            not receipt.get('global_authority_head_sha256') or
            receipt != expected):
        raise ValueError('Independent root stage review differs')
    paths = stage_paths()
    if any(path.exists() for path in paths.values()):
        raise FileExistsError('Suffix already claimed; no replay')
    if transport.MAX_RESPONSE_BYTES != prior.MAX_RESPONSE_BYTES:
        raise ValueError('Bounded transport changed')
    model, endpoint = live_controls()
    ledger = partitions.open_partition(admission.MASTER, budget_path,
        PARTITION_ID, admission.MODEL, admission.PROVIDER, 'low')
    try:
        _, pending, blocked = ledger.state()
        if (ledger.cap != CHILD_CAP or ledger.master_cap != Decimal('12.38') or
                pending or blocked or ledger.closed or ledger.accounted() + RESERVE > CHILD_CAP):
            raise ValueError('Exact child cannot reserve a call')
        hold_authority(receipt['global_authority_head_sha256'], budget_path,
                       receipt['global_hold_source_sha256'])
        token = paid.load_key(env_file)
        claim = {'schema': SCHEMA + '-stage-claim',
            'manifest_sha256': sha(MANIFEST), 'review_sha256': sha(receipt_path),
            'budget_manifest_sha256': sha(budget_path),
            'partition_id': PARTITION_ID, 'ids': IDS}
        frozen.atomic_json(paths['claim'], claim)
        plan = frozen.load_manifest(prior.BASE / 'manifest.json',
                                   prior.lower_price.MANIFEST_SHA)
        history, controls, _, _ = admission.source_state()
        policy = (ROOT / history['conditions']['P2']['instruction']['file']).read_text()
        schema = controls['response_format']['json_schema']['schema']
        inputs = read_rows(admission.INPUTS)[50:]
        with (paths['journal'].open('x') as journal,
              paths['raw'].open('x') as raw,
              paths['records'].open('x') as records):
            paid.durable(journal, {'event': 'stage_claimed',
                                   'claim_sha256': sha(paths['claim'])})
            for input_row, item in zip(inputs, manifest['requests']):
                verify()
                rid = item['id']
                payload = paid.make_payload(admission.MODEL, endpoint,
                    input_row['feedback'], policy, schema, 'low', 4096,
                    INPUT_CEILING, OUTPUT_CEILING, model)
                if digest(json.dumps(payload, sort_keys=True)) != item['request_sha256']:
                    raise ValueError('Request changed before reservation')
                try:
                    attempt = ledger.reserve(RESERVE, rid)
                except ValueError as exc:
                    if 'cap reached' not in str(exc):
                        raise
                    paid.durable(journal, {'event': 'admission_stopped',
                        'next_unsent_id': rid, 'reason': 'child_cap'})
                    return {'completed': False, 'status': 'child_cap', 'next_unsent_id': rid}
                paid.durable(journal, {'event': 'request_started', 'attempt_id': attempt,
                    'id': rid, 'request_sha256': item['request_sha256'],
                    'reserved_cost_usd': str(RESERVE)})
                row = {'id': rid, 'repeat': 'fresh1', 'condition': 'P2',
                    'phase': 'development', 'attempt_id': attempt, 'request': payload,
                    'request_sha256': item['request_sha256'],
                    'input_sha256': item['input_sha256'],
                    'policy_sha256': item['instruction_sha256'],
                    'requested_model': admission.MODEL, 'provider_endpoint': endpoint,
                    'model_catalog_entry': model, 'reference_labels_read': False,
                    'reserved_cost_usd': str(RESERVE),
                    'budget_partition_id': PARTITION_ID, 'reasoning_effort': 'low',
                    'continue_on_invalid_output': True, 'retry_policy': 'none'}
                actual = None
                before = raw.tell()
                row['client_request_started_utc'] = datetime.now(timezone.utc).isoformat()
                started = time.monotonic()
                try:
                    body = transport.fetch_recorded(payload, token, 300, raw,
                        rid, attempt, item['request_sha256'])
                    if not isinstance(body, dict):
                        raise ValueError('Response JSON root is not an object')
                    row['raw_response'] = body
                    usage = body.get('usage') or {}
                    row['usage'] = usage
                    if usage.get('cost') is not None:
                        actual = paid.number(usage['cost'])
                    status, prediction, _, finish = prior._body_result(body, endpoint)
                    row.update(status=status, prediction=prediction,
                        returned_model=body.get('model'),
                        returned_provider=body.get('provider'), finish_reason=finish)
                except Exception as exc:
                    if raw.tell() == before:
                        prior._capture_error(raw, rid, attempt, item['request_sha256'],
                                             exc, token)
                    row.update(status='service_error', error_type=type(exc).__name__)
                    if isinstance(exc, urllib.error.HTTPError):
                        row['http_status'] = exc.code
                finally:
                    row['client_http_duration_seconds'] = time.monotonic() - started
                    row['client_request_finished_utc'] = datetime.now(timezone.utc).isoformat()
                    row['timing_boundary'] = ('Client request through durable raw capture; '
                        'includes local I/O and excludes later billing and record writes.')
                paid.durable(journal, {'event': 'raw_saved', 'attempt_id': attempt,
                    'raw_sha256': sha(paths['raw'])})
                billing_ok = ledger.settle(attempt, actual)
                if actual is not None and not billing_ok:
                    row['status'] = 'billing_blocked'
                row.update(observed_cost_usd=str(actual) if actual is not None else None,
                           cost_unknown=actual is None, billing_ok=billing_ok)
                paid.durable(records, row)
                paid.durable(journal, {'event': 'request_finished', 'attempt_id': attempt,
                    'id': rid, 'status': row['status'], 'billing_ok': billing_ok})
                if (row['status'] not in ('ok', 'invalid_output') or actual is None or
                        not billing_ok):
                    stop_reason = ('unknown_cost' if actual is None else
                                   'billing_blocked' if not billing_ok else row['status'])
                    paid.durable(journal, {'event': 'stage_stopped',
                        'id': rid, 'reason': stop_reason})
                    return {'completed': False, 'status': stop_reason, 'stopped_id': rid}
            paid.durable(journal, {'event': 'stage_completed', 'count': len(IDS)})
            return {'completed': True, 'count': len(IDS)}
    finally:
        ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify', 'execute-stage'))
    parser.add_argument('--review', type=Path)
    parser.add_argument('--budget', type=Path)
    parser.add_argument('--env-file')
    args = parser.parse_args()
    if args.action == 'prepare':
        print(prepare())
    elif args.action == 'verify':
        verify(); print(sha(MANIFEST))
    else:
        if not args.review or not args.budget:
            parser.error('execute-stage requires --review and --budget')
        print(json.dumps(run(args.review, args.budget, args.env_file)))


if __name__ == '__main__':
    main()
