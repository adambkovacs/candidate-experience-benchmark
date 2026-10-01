#!/usr/bin/env python3
"""Receipt-gated, same-route Qwen27 continuation after fresh3/P0 timeouts."""
import argparse
import base64
from decimal import Decimal
import json
import os
from pathlib import Path
import time
import urllib.error

from development_benchmark import ROOT
import build_qwen27_interruption_findings as interrupted
import qwen27_fresh_repeat_study_v2 as study
import qwen27_fresh_repeat_execution_v2 as original
import openrouter_paid_benchmark as paid
import openrouter_benchmark as transport
import openrouter_budget_v3 as master_budget
import paid_budget_partitions_v3 as partitions
import prompt_admission

SCHEMA = 'qwen27-v2-interrupted-continuation-v1'
BASE = study.BASE / 'interruption-continuation-v1'
MASTER = original.MASTER
RESERVE = interrupted.RESERVE
PLANS = interrupted.PLANS
STOP = interrupted.STOP
OLD = {
    'medium': {
        'development.claim.json': '083541633420ba803a63c3e1b37374351f93cb10f086f5bede6081c7a3294a89',
        'development.root-review.json': '6be24c1262e9acdf62f17c88bae085bb836902d964fe4173589c7916b3018dd8',
        'development.journal.jsonl': '8cdc54ab6b36cd48d00131f17f3fdc7052a6902d82a3bd198f39e7e89593e503',
        'development.attempts.jsonl': '67edc29634c5e8f2d66d8b572cc6854e00b79b0c7fbd2308780f4c6a935693bd',
        'development.responses.jsonl': '23810dfbe91b43e84d8b596291d9f1b0de2cb09fecb55274af662ea22ae6baaa',
        'terminal-reconciliation.json': '22a14d83fde985ea30ff0150eac4a5636e145fa4db6584152e2550372239af43',
        'child': 'b519e4d70a7ca77e95b2b5b139adb97230c8509f94176144d1b25aecacd37c81',
    },
    'xhigh': {
        'development.claim.json': '4aa048b2de3aad3b28b6f6b221440cba20481a1a73f173a6f5843250c085769e',
        'development.root-review.json': '39e6f491b8bbd966f98ecb368af0df78053c04fc56ab503bd0ea0182b0de9476',
        'development.journal.jsonl': 'c351529d171be96db3d1dcec24ab763784975394144e30b80275755f4e13eff9',
        'development.attempts.jsonl': 'feb110ac9c5b94f503ec541f1e011d3787bf4c0f20cb45157fbd9e88164705e5',
        'development.responses.jsonl': '4ba3f1818685f5669f99b3242f2501d9f86d4fed6c84da9587b5db1c784112f3',
        'terminal-reconciliation.json': 'd5b6aa580d1f280f413b79dd6e9cde4ee0d8836f778199d8d9c030ed425df922',
        'child': '40ca60ce9970b80585af4aaee04d67bb6d5e9f430756c6f44f5ee7c94c9d8f8d',
    },
}
RUNTIME = {
    'controller': __file__, 'reporter': interrupted.__file__,
    'planner': study.__file__, 'original_controller': original.__file__,
    'paid_adapter': paid.__file__, 'transport': transport.__file__,
    'master_budget': master_budget.__file__, 'partitions': partitions.__file__,
    'response_audit': prompt_admission.__file__,
    'development_benchmark': ROOT / 'scripts/development_benchmark.py',
}


def suffix(config):
    if config not in study.CONFIGS:
        raise ValueError('Unknown Qwen27 configuration')
    return config.rsplit('-', 1)[-1]


def folder(config):
    return BASE / suffix(config)


def path(config, stage, name):
    return folder(config) / stage / name


def stages(config):
    suffix(config)
    return [('fresh3', 'P0', 'suffix'), ('fresh3', 'P1', 'smoke'),
            ('fresh3', 'P1', 'development')]


def stage_name(repeat, condition, phase):
    if (repeat, condition, phase) not in [('fresh3', 'P0', 'suffix'),
                                          ('fresh3', 'P1', 'smoke'),
                                          ('fresh3', 'P1', 'development')]:
        raise ValueError('Stage outside interrupted continuation')
    return repeat + '/' + condition + '/' + phase


def selected_requests(config, repeat, condition, phase):
    stage_name(repeat, condition, phase)
    plan = study.verify(config, 'fresh3', PLANS[suffix(config)])
    source = plan['conditions'][condition]['development' if phase == 'suffix' else phase]
    chosen = source[STOP[suffix(config)][0]:] if phase == 'suffix' else source
    expected = ([f'DEV-{i:03d}' for i in range(STOP[suffix(config)][0] + 1, 61)]
                if phase == 'suffix' else
                [f'DEV-{i:03d}' for i in range(1, 4 if phase == 'smoke' else 61)])
    if [r['record_id'] for r in chosen] != expected:
        raise ValueError('Never-sent or later request membership differs')
    return chosen


def binding(file):
    file = Path(file).resolve()
    return {'path': str(file.relative_to(ROOT.resolve())), 'sha256': study.sha(file)}


def bound(item):
    file = (ROOT / item['path']).resolve()
    file.relative_to(ROOT.resolve())
    if study.sha(file) != item['sha256']:
        raise ValueError('Frozen source changed: ' + item['path'])
    return file


def rows(file):
    raw = Path(file).read_bytes()
    if raw and not raw.endswith(b'\n'):
        raise ValueError('Incomplete JSONL: ' + str(file))
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def verify_old(config):
    kind = suffix(config)
    checked = interrupted.build()
    report = checked['series'][kind]
    failed_number, valid, unsent = STOP[kind]
    if (report['valid'], report['failedId'], report['neverSent'], report['score'],
            report['strictCompletePass'], report['unknownStageCostUpperBoundUsd']) != (
            valid, f'DEV-{failed_number:03d}', unsent, None, False, str(RESERVE)):
        raise ValueError('Interrupted source accounting differs')
    old_folder = study.BASE / config / 'fresh3/P0'
    for name, expected in OLD[kind].items():
        file = (study.BASE / f'budget-partitions-v1-qwen27-{kind}-v2.jsonl'
                if name == 'child' else old_folder / name)
        if study.sha(file) != expected:
            raise ValueError('Stopped or sealed evidence changed: ' + name)
    old_attempts = rows(old_folder / 'development.attempts.jsonl')
    if (len(old_attempts) != failed_number or
            old_attempts[-1].get('status') != 'service_error' or
            old_attempts[-1].get('cost_unknown') is not True or
            old_attempts[-1].get('error_type') != 'TimeoutError'):
        raise ValueError('Unknown attempted position differs')
    return report, {name: source for name, source in checked['sourceBindings'].items()
                    if name.startswith(kind + '_')}


def budget_entry(config, budget_path, require_fresh=False):
    budget_path = Path(budget_path).resolve()
    if budget_path != (folder(config) / 'budget.json').resolve():
        raise ValueError('Distinct new budget manifest path required')
    manifest = json.loads(budget_path.read_text())
    items = manifest.get('partitions')
    if (manifest.get('version') != 'paid-partitions-v1' or
            manifest.get('master_ledger') != str(MASTER.resolve()) or
            not isinstance(items, list) or len(items) != 1):
        raise ValueError('New child budget manifest differs')
    item = items[0]
    kind = suffix(config)
    pid = f'qwen27-{kind}-v2-interruption-v1'
    cap = paid.number(item.get('cap_usd'))
    child = folder(config) / ('budget-' + pid + '.jsonl')
    if (item.get('id') != pid or cap < RESERVE or
            (item.get('model'), item.get('provider'), item.get('reasoning')) != (
                study.MODEL, study.PROVIDER, study.CONFIGS[config]['effort']) or
            Path(item.get('child_ledger', '')).resolve() != child.resolve()):
        raise ValueError('New child route, cap or identity differs')
    events = rows(child)
    if not events or events[0] != {'event': 'budget', 'cap_usd': item['cap_usd']}:
        raise ValueError('New child opening differs')
    master = rows(MASTER)
    allocated = [e for e in master if e.get('event') == 'budget_partition' and
                 e.get('partition_id') == pid]
    reconciled = [e for e in master if e.get('event') == 'partition_reconciled' and
                  e.get('partition_id') == pid]
    if len(allocated) != 1 or allocated[0] != {
            'event': 'budget_partition', 'partition_id': pid,
            'allocated_usd': item['cap_usd'], 'manifest_path': str(budget_path),
            'manifest_sha256': study.sha(budget_path), 'child_ledger': str(child.resolve()),
            'model': study.MODEL, 'provider': study.PROVIDER,
            'reasoning': study.CONFIGS[config]['effort']}:
        raise ValueError('Distinct child allocation differs')
    if require_fresh and (len(events) != 1 or reconciled):
        raise ValueError('New child is spent or reconciled')
    if bool(reconciled) != (events[-1].get('event') == 'partition_closed'):
        raise ValueError('New child closure and master reconciliation differ')
    return item


def expected_manifest(config, budget_path, require_fresh=False):
    _, old_sources = verify_old(config)
    item = budget_entry(config, budget_path, require_fresh=require_fresh)
    kind = suffix(config)
    old = study.BASE / config / 'fresh3/P0'
    sources = {name: binding(file) for name, file in RUNTIME.items()}
    sources['execution_manifest'] = binding(original.EXECUTION_MANIFEST)
    sources['new_budget_manifest'] = binding(budget_path)
    for name, source in old_sources.items():
        sources['verified_' + name] = source
    for repeat in study.ORDERS:
        sources['plan_' + repeat] = binding(study.BASE / config / repeat / 'manifest.json')
    for name in OLD[kind]:
        file = (study.BASE / f'budget-partitions-v1-qwen27-{kind}-v2.jsonl'
                if name == 'child' else old / name)
        sources['old_' + name.replace('.', '_')] = binding(file)
    schedule = []
    for repeat, condition, phase in stages(config):
        selected = selected_requests(config, repeat, condition, phase)
        schedule.append({'stage': stage_name(repeat, condition, phase),
                         'ids': [r['record_id'] for r in selected],
                         'request_sha256': [r['request_sha256'] for r in selected]})
    return {'schema': SCHEMA, 'status': 'FROZEN', 'configuration_id': config,
            'series_id': SCHEMA + '-' + kind,
            'method': 'descriptive-same-route-never-sent-continuation',
            'clean_matched_three_eligible': False,
            'failed_attempted_id': f'DEV-{STOP[kind][0]:03d}',
            'never_sent_ids': schedule[0]['ids'],
            'reference_labels_read': False,
            'retry_policy': 'No retry of any attempted fresh3/P0 record',
            'reserve_usd': str(RESERVE), 'schedule': schedule,
            'partition_id': item['id'], 'child_cap_usd': item['cap_usd'],
            'source_bindings': sources}


def freeze(config, budget_path):
    target = folder(config) / 'manifest.json'
    if target.exists():
        raise FileExistsError('Continuation already frozen')
    value = expected_manifest(config, budget_path, require_fresh=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x') as out:
        json.dump(value, out, indent=2)
        out.write('\n'); out.flush(); os.fsync(out.fileno())
    return study.sha(target)


def verify_manifest(config, expected_sha):
    target = folder(config) / 'manifest.json'
    if study.sha(target) != expected_sha:
        raise ValueError('Continuation manifest SHA differs')
    saved = json.loads(target.read_text())
    for source in saved['source_bindings'].values():
        bound(source)
    if saved != expected_manifest(config, bound(saved['source_bindings']['new_budget_manifest'])):
        raise ValueError('Continuation source, schedule or budget differs')
    return saved


def stage_files(config, repeat, condition, phase):
    name = stage_name(repeat, condition, phase)
    directory = folder(config) / name
    return {key: directory / (phase + '.' + extension) for key, extension in (
        ('claim', 'claim.json'), ('journal', 'journal.jsonl'),
        ('attempts', 'attempts.jsonl'), ('responses', 'responses.jsonl'))}


def review_path(config, repeat, condition, phase):
    return folder(config) / stage_name(repeat, condition, phase) / (phase + '.root-review.json')


def expected_review(manifest, manifest_sha, repeat, condition, phase):
    stage = stage_name(repeat, condition, phase)
    entry = next(x for x in manifest['schedule'] if x['stage'] == stage)
    return {'schema': SCHEMA + '-stage-review', 'approved': True,
            'configuration_id': manifest['configuration_id'],
            'series_id': manifest['series_id'], 'manifest_sha256': manifest_sha,
            'controller_sha256': manifest['source_bindings']['controller']['sha256'],
            'new_budget_manifest_sha256': manifest['source_bindings']['new_budget_manifest']['sha256'],
            'old_child_sha256': manifest['source_bindings']['old_child']['sha256'],
            'partition_id': manifest['partition_id'],
            'child_cap_usd': manifest['child_cap_usd'],
            'stage': stage, 'ids': entry['ids'], 'request_sha256': entry['request_sha256']}


def verify_review(file, manifest, manifest_sha, repeat, condition, phase):
    file = Path(file).resolve()
    if file != review_path(manifest['configuration_id'], repeat, condition, phase).resolve():
        raise ValueError('Exact root review path required')
    saved = json.loads(file.read_text())
    if any(saved.get(k) != v for k, v in expected_review(
            manifest, manifest_sha, repeat, condition, phase).items()):
        raise ValueError('Root stage review differs')
    return saved


def verify_stage_closure(manifest, manifest_sha, repeat, condition, phase):
    config = manifest['configuration_id']
    files = stage_files(config, repeat, condition, phase)
    if not all(file.is_file() for file in files.values()):
        raise ValueError('Continuation stage evidence missing')
    review = review_path(config, repeat, condition, phase)
    verify_review(review, manifest, manifest_sha, repeat, condition, phase)
    claim = json.loads(files['claim'].read_text())
    if any(claim.get(k) != v for k, v in {
            'series_id': manifest['series_id'], 'configuration_id': config,
            'stage': stage_name(repeat, condition, phase),
            'manifest_sha256': manifest_sha, 'root_review_sha256': study.sha(review)}.items()):
        raise ValueError('Continuation claim differs')
    requests = selected_requests(config, repeat, condition, phase)
    attempts, raw, journal = (rows(files[k]) for k in ('attempts', 'responses', 'journal'))
    ids = [r['record_id'] for r in requests]
    if ([r.get('id') for r in attempts] != ids or [r.get('id') for r in raw] != ids or
            len(journal) != 2 + 3 * len(ids) or
            len({r.get('attempt_id') for r in attempts}) != len(ids) or
            journal[0].get('event') != 'phase_started' or
            journal[-1].get('event') != 'phase_completed' or
            journal[-1].get('request_count') != len(ids) or
            journal[-1].get('attempt_ids') != [r['attempt_id'] for r in attempts]):
        raise ValueError('Continuation completion membership differs')
    budget = bound(manifest['source_bindings']['new_budget_manifest'])
    item = budget_entry(config, budget)
    charges = rows(item['child_ledger'])
    original_attempt = rows(study.BASE / config / 'fresh3/P0/development.attempts.jsonl')[0]
    critical = ('tag', 'provider_name', 'quantization', 'model_id', 'context_length',
                'max_prompt_tokens', 'max_completion_tokens', 'supported_parameters', 'pricing')
    for index, (request, record, wire) in enumerate(zip(requests, attempts, raw)):
        intent, started, finished = journal[1 + 3*index:4 + 3*index]
        attempt = record.get('attempt_id')
        if (record.get('series_id') != manifest['series_id'] or
                record.get('configuration_id') != config or
                record.get('stage') != stage_name(repeat, condition, phase) or
                record.get('manifest_sha256') != manifest_sha or
                record.get('request') != request['payload'] or
                record.get('request_sha256') != request['request_sha256'] or
                record.get('input_sha256') != request['input_sha256'] or
                record.get('instruction_sha256') != request['instruction_sha256'] or
                record.get('reference_labels_read') is not False or
                record.get('model_catalog_entry') != original_attempt['model_catalog_entry'] or
                record.get('status') != 'ok' or record.get('billing_ok') is not True or
                record.get('cost_unknown') is not False or
                record.get('reserved_cost_usd') != str(RESERVE) or
                record.get('observed_cost_usd') is None or
                paid.number(record['observed_cost_usd']) > RESERVE or
                any(record.get('provider_endpoint', {}).get(k) !=
                    original_attempt['provider_endpoint'].get(k) for k in critical) or
                wire.get('attempt_id') != attempt or wire.get('id') != record['id'] or
                wire.get('request_sha256') != request['request_sha256'] or
                wire.get('http_status') != 200 or
                wire.get('body_truncated_at_limit') is not False or
                wire.get('read_error') is not None or
                [(e.get('event'), e.get('id'), e.get('attempt_id')) for e in
                 (intent, started, finished)] != [
                    ('request_intent', record['id'], None),
                    ('request_started', record['id'], attempt),
                    ('request_finished', record['id'], attempt)] or
                intent.get('request_sha256') != request['request_sha256'] or
                started.get('request_sha256') != request['request_sha256'] or
                finished.get('status') != 'ok' or
                finished.get('billing_ok') is not True or
                finished.get('cost_unknown') is not False or
                finished.get('observed_cost_usd') != record['observed_cost_usd'] or
                [e for e in charges if e.get('attempt_id') == attempt] != [
                    {'event': 'reserve', 'attempt_id': attempt,
                     'record_id': record['id'], 'usd': str(RESERVE)},
                    {'event': 'settle', 'attempt_id': attempt,
                     'usd': record['observed_cost_usd']}]):
            raise ValueError('Continuation attempt or child settlement differs')
        try:
            decoded = json.loads(base64.b64decode(wire['body_base64'], validate=True))
        except (ValueError, TypeError):
            raise ValueError('Continuation wire capture cannot be decoded') from None
        if decoded != record.get('raw_response'):
            raise ValueError('Continuation raw response differs')
        classified = original.classify(decoded, record['model_catalog_entry'],
                                       record['provider_endpoint'])
        if (any(record.get(k) != v for k, v in classified.items()) or
                paid.number((decoded.get('usage') or {}).get('cost')) !=
                    paid.number(record['observed_cost_usd']) or
                record.get('response_diagnostic') != prompt_admission.audit_response(
                    record, 'openrouter_paid_v1',
                    record['provider_endpoint']['context_length'] - 4096) or
                record['response_diagnostic'].get('passed') is not True):
            raise ValueError('Continuation parsed response differs')
    return {name + '_sha256': study.sha(file) for name, file in files.items()}


def require_order(manifest, manifest_sha, repeat, condition, phase):
    config = manifest['configuration_id']
    target = (repeat, condition, phase)
    if target not in stages(config):
        raise ValueError('Unknown continuation stage')
    for prior in stages(config)[:stages(config).index(target)]:
        verify_stage_closure(manifest, manifest_sha, *prior)
    if phase == 'development':
        closed = verify_stage_closure(manifest, manifest_sha, repeat, condition, 'smoke')
        inspection = folder(config) / repeat / condition / 'smoke-inspection.json'
        saved = json.loads(inspection.read_text())
        if any(saved.get(k) != v for k, v in {
                'schema': SCHEMA + '-smoke-inspection', 'decision': 'accepted_unchanged',
                'configuration_id': config, 'manifest_sha256': manifest_sha,
                'attempts_sha256': closed['attempts_sha256'],
                'responses_sha256': closed['responses_sha256'],
                'journal_sha256': closed['journal_sha256']}.items()):
            raise ValueError('Root smoke inspection differs')


def execute(config, manifest_sha, repeat, condition, phase, review, env_file=None):
    manifest = verify_manifest(config, manifest_sha)
    require_order(manifest, manifest_sha, repeat, condition, phase)
    verify_review(review, manifest, manifest_sha, repeat, condition, phase)
    files = stage_files(config, repeat, condition, phase)
    if any(file.exists() for file in files.values()):
        raise FileExistsError('Continuation stage already claimed; no retry')
    plan = study.verify(config, 'fresh3', PLANS[suffix(config)])
    route_model, route_endpoint, reserve = original.live_controls(plan, condition)
    if reserve != RESERVE:
        raise ValueError('Live full request reserve differs')
    budget = bound(manifest['source_bindings']['new_budget_manifest'])
    budget_entry(config, budget)
    ledger = partitions.open_partition(MASTER, budget, manifest['partition_id'],
                                       study.MODEL, study.PROVIDER, study.CONFIGS[config]['effort'])
    try:
        if ledger.cap != paid.number(manifest['child_cap_usd']) or ledger.master_cap != Decimal('12.38'):
            raise ValueError('Master or new child cap differs')
        _, pending, blocked = ledger.state()
        if pending or blocked or ledger.closed or ledger.accounted() + RESERVE > ledger.cap:
            raise ValueError('New child cannot reserve next request')
        token = paid.load_key(env_file)
        files['claim'].parent.mkdir(parents=True, exist_ok=True)
        with files['claim'].open('x') as out:
            paid.durable(out, {'series_id': manifest['series_id'],
                               'configuration_id': config,
                               'stage': stage_name(repeat, condition, phase),
                               'manifest_sha256': manifest_sha,
                               'root_review_sha256': study.sha(review),
                               'claimed_utc': original.utc()})
        complete = True
        requests = selected_requests(config, repeat, condition, phase)
        with files['journal'].open('x') as journal, files['attempts'].open('x') as attempts, \
                files['responses'].open('x') as responses:
            paid.durable(journal, {'event': 'phase_started',
                                   'stage': stage_name(repeat, condition, phase),
                                   'utc': original.utc()})
            for request in requests:
                rid = request['record_id']
                # Repeat the public route, price, context and payload check before every request.
                model, endpoint, current_reserve = original.live_controls(plan, condition)
                if (model != route_model or endpoint != route_endpoint or
                        current_reserve != RESERVE):
                    raise ValueError('Live route changed within continuation stage')
                if ledger.accounted() + RESERVE > ledger.cap:
                    complete = False
                    paid.durable(journal, {'event': 'phase_stopped', 'id': rid,
                                           'reason': 'child_cap_before_send',
                                           'utc': original.utc()})
                    break
                paid.durable(journal, {'event': 'request_intent', 'id': rid,
                                       'request_sha256': request['request_sha256'],
                                       'utc': original.utc()})
                attempt_id = ledger.reserve(RESERVE, rid)
                start = time.perf_counter()
                record = {'id': rid, 'series_id': manifest['series_id'],
                          'configuration_id': config,
                          'stage': stage_name(repeat, condition, phase),
                          'attempt_id': attempt_id, 'request': request['payload'],
                          'request_sha256': request['request_sha256'],
                          'input_sha256': request['input_sha256'],
                          'instruction_sha256': request['instruction_sha256'],
                          'manifest_sha256': manifest_sha, 'requested_model': study.MODEL,
                          'reasoning_effort': study.CONFIGS[config]['effort'],
                          'provider_endpoint': endpoint, 'model_catalog_entry': model,
                          'reference_labels_read': False,
                          'reserved_cost_usd': str(RESERVE), 'started_utc': original.utc()}
                paid.durable(journal, {'event': 'request_started', 'id': rid,
                                       'attempt_id': attempt_id,
                                       'request_sha256': request['request_sha256'],
                                       'utc': original.utc()})
                actual = None
                try:
                    body = original.fetch_recorded(request['payload'], token, study.TIMEOUT,
                                                   responses, rid, attempt_id,
                                                   request['request_sha256'])
                    body = json.loads(json.dumps(body).replace(token, '[REDACTED]'))
                    record['raw_response'] = body
                    if isinstance(body, dict):
                        usage = body.get('usage') or {}
                        if usage.get('cost') is not None:
                            actual = paid.number(usage['cost'])
                        record.update(original.classify(body, model, endpoint))
                    else:
                        record['status'] = 'control_violation'
                except Exception as exc:
                    record.update(status='service_error', error_type=type(exc).__name__)
                    if isinstance(exc, urllib.error.HTTPError):
                        data, length, oversized, redacted, read_error = original.response_bytes(exc, token)
                        headers = original.safe_headers(exc, token)
                        record.update(http_status=exc.code,
                                      error_body=data.decode('utf-8', errors='replace'),
                                      error_headers=headers,
                                      error_body_truncated_at_limit=oversized,
                                      error_read_error=read_error)
                        paid.durable(responses, {'id': rid, 'attempt_id': attempt_id,
                            'request_sha256': request['request_sha256'],
                            'http_status': exc.code, 'response_headers': headers,
                            'body_base64': base64.b64encode(data).decode('ascii'),
                            'body_bytes_captured': length,
                            'body_truncated_at_limit': oversized,
                            'body_token_redacted': redacted,
                            'read_error': read_error, 'received_utc': original.utc()})
                billing_ok = ledger.settle(attempt_id, actual)
                record.update(elapsed_seconds=time.perf_counter() - start,
                              timing_boundary='Client request through capture, settlement and audit; not pure inference time.',
                              observed_cost_usd=str(actual) if actual is not None else None,
                              cost_unknown=actual is None, billing_ok=billing_ok)
                if record.get('raw_response') is not None:
                    diagnostic = prompt_admission.audit_response(
                        record, 'openrouter_paid_v1', endpoint['context_length'] - 4096)
                    record['response_diagnostic'] = diagnostic
                    if not diagnostic['passed'] and record['status'] == 'ok':
                        record['status'] = 'prompt_admission_failure'
                paid.durable(attempts, record)
                paid.durable(journal, {'event': 'request_finished', 'id': rid,
                    'attempt_id': attempt_id, 'status': record['status'],
                    'billing_ok': billing_ok, 'cost_unknown': record['cost_unknown'],
                    'observed_cost_usd': record['observed_cost_usd'], 'utc': original.utc()})
                if not original.continue_record(record, 'development' if phase == 'suffix' else phase):
                    complete = False
                    paid.durable(journal, {'event': 'phase_stopped', 'id': rid,
                                           'reason': record['status'], 'utc': original.utc()})
                    break
            if complete:
                paid.durable(journal, {'event': 'phase_completed',
                                       'stage': stage_name(repeat, condition, phase),
                                       'request_count': len(requests),
                                       'attempt_ids': [x['attempt_id'] for x in rows(files['attempts'])],
                                       'utc': original.utc()})
        return complete
    finally:
        if files['journal'].exists():
            journal_rows = rows(files['journal'])
            if journal_rows and journal_rows[-1].get('event') not in (
                    'phase_completed', 'phase_stopped', 'phase_aborted'):
                with files['journal'].open('a') as out:
                    paid.durable(out, {'event': 'phase_aborted',
                                       'reason': 'exception_or_interruption',
                                       'utc': original.utc()})
        ledger.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    audit = sub.add_parser('audit-prefix')
    audit.add_argument('--configuration-id', required=True, choices=tuple(study.CONFIGS))
    freeze_cmd = sub.add_parser('freeze')
    freeze_cmd.add_argument('--configuration-id', required=True, choices=tuple(study.CONFIGS))
    freeze_cmd.add_argument('--budget-manifest', required=True, type=Path)
    verify = sub.add_parser('verify')
    verify.add_argument('--configuration-id', required=True, choices=tuple(study.CONFIGS))
    verify.add_argument('--manifest-sha256', required=True)
    run = sub.add_parser('run')
    run.add_argument('--configuration-id', required=True, choices=tuple(study.CONFIGS))
    run.add_argument('--manifest-sha256', required=True)
    run.add_argument('--fresh-pass', required=True)
    run.add_argument('--condition', required=True)
    run.add_argument('--phase', required=True)
    run.add_argument('--root-review-receipt', required=True, type=Path)
    run.add_argument('--env-file', type=Path)
    args = parser.parse_args(argv)
    if args.action == 'audit-prefix':
        report, _ = verify_old(args.configuration_id)
        print(json.dumps({'configuration_id': args.configuration_id,
                          'failed_id': report['failedId'],
                          'never_sent_ids': report['neverSentIds'],
                          'unknown_bound_usd': report['unknownStageCostUpperBoundUsd']}))
    elif args.action == 'freeze':
        print(freeze(args.configuration_id, args.budget_manifest))
    elif args.action == 'verify':
        verify_manifest(args.configuration_id, args.manifest_sha256)
        print(args.manifest_sha256)
    else:
        print(json.dumps({'completed': execute(args.configuration_id,
            args.manifest_sha256, args.fresh_pass, args.condition, args.phase,
            args.root_review_receipt, args.env_file)}))


if __name__ == '__main__':
    main()
