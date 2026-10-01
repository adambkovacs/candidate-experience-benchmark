#!/usr/bin/env python3
"""Separate Qwen27 continuation after a pre-send rolling-route abort.

No request is made by importing or auditing this module. Both earlier stopped
stages and their sealed child budgets remain immutable.
"""
import argparse
import base64
from decimal import Decimal
import json
import os
from pathlib import Path
import time
import urllib.error
from urllib.parse import quote

from development_benchmark import ROOT
import build_qwen27_interruption_findings as interrupted
import qwen27_fresh_repeat_study_v2 as study
import qwen27_fresh_repeat_execution_v2 as original
import openrouter_paid_benchmark as paid
import openrouter_benchmark as transport
import openrouter_budget_v3 as master_budget
import paid_budget_partitions_v3 as partitions
import prompt_admission
import qwen27_v2_interruption_continuation as first

SCHEMA = 'qwen27-v2-second-interruption-continuation-v1'
BASE = study.BASE / 'interruption-continuation-v2'
MASTER = original.MASTER
RESERVE = interrupted.RESERVE
PLANS = interrupted.PLANS
STOP = interrupted.STOP
FIRST_MANIFEST = {
    'medium': 'ebbe5883347cc7054173db783655451581081c7884e524c149733119d6a63684',
    'xhigh': '26d30b50626c203b6666cae49a3d2187b03a9b74bc76de01f091203bfaa4b080',
}
FIRST_STOP = {
    'medium': {'stage': ('fresh3', 'P0', 'suffix'), 'first_id': 23, 'last_id': 38,
        'claim': '0acae968ea214f06615d2be2abd03905051980a8a53f183eb073c0b0899e2988',
        'review': '79738f060b1f228c76daa6e65054039d3d19e698b4d348b2f2f89466e311faf7',
        'journal': '5e99804cda0e5c1f63e7c53facfd3758d65cfccce200aefdd05339d856801628',
        'attempts': '19e2c55635c9a02a61358f24901ec02066802d00133b8f29c83f4c0ad17c2b05',
        'responses': 'b58bfc48892cd3a080d876e3ae93d27c02374c064f1795b4b265513e2e594126',
        'child': '13be448f5fbbc1d8ffd73673b55bbf4a89b6cb76167e5784e544e277e1817669',
        'reconciliation': 'f74287823e4dc070061ce1e8fa35d67c60787bb179b5e3a88e097242420d9c37'},
    'xhigh': {'stage': ('fresh3', 'P1', 'development'), 'first_id': 1, 'last_id': 8,
        'claim': 'e28c9dcf23571e8d60e47f672d0079a10b71275433a0b7d6430d9f1467b19908',
        'review': '8b0dd21b321eb53f7beff9614dfaad1f066a9fc91b98e60420b72c01c7ff9ef7',
        'journal': 'f9237167a38589b70850f5a20f229bc5df1cc4e87cbe99ce4c03b3e43a4a235d',
        'attempts': 'ebfaa35c351c8f12806157f01c9384853dcaa7fa2b16bfb8d6b0eade7f17eb7d',
        'responses': '9f0a0f576f22ce4311c7319d05568a3fa3401049828cd365dfcd167cbaa7b9c0',
        'child': '4e80113d95f7ca6226a5a994c83a74525039e865996f5b43abfe842144964e38',
        'reconciliation': 'd5bfa9aab747447ffe455f05f8a85607a98cf7d7e83eb332f0b3b39ee216b2ce'},
}
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
    'first_controller': first.__file__,
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
    return ([('fresh3', 'P0', 'suffix'), ('fresh3', 'P1', 'smoke'),
             ('fresh3', 'P1', 'development')] if suffix(config) == 'medium'
            else [('fresh3', 'P1', 'suffix')])


def stage_name(repeat, condition, phase):
    if (repeat, condition, phase) not in [('fresh3', 'P0', 'suffix'),
                                          ('fresh3', 'P1', 'smoke'),
                                          ('fresh3', 'P1', 'development'),
                                          ('fresh3', 'P1', 'suffix')]:
        raise ValueError('Stage outside interrupted continuation')
    return repeat + '/' + condition + '/' + phase


def selected_requests(config, repeat, condition, phase):
    if (repeat, condition, phase) not in stages(config):
        raise ValueError('Stage outside second continuation')
    plan = study.verify(config, 'fresh3', PLANS[suffix(config)])
    source = plan['conditions'][condition]['development' if phase == 'suffix' else phase]
    first_unsent = FIRST_STOP[suffix(config)]['last_id'] + 1
    chosen = source[first_unsent - 1:] if phase == 'suffix' else source
    expected = ([f'DEV-{i:03d}' for i in range(first_unsent, 61)]
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


CRITICAL_ENDPOINT = ('tag', 'provider_name', 'quantization', 'model_id',
                     'context_length', 'max_prompt_tokens',
                     'max_completion_tokens', 'supported_parameters', 'pricing')


def checked_live_controls(plan, condition, journal, rid):
    """Record public metadata before applying the unchanged wire-control gate."""
    config = plan['configuration_id']
    effort = study.CONFIGS[config]['effort']
    catalog = paid.fetch('/models', timeout=120)
    endpoints = paid.fetch('/models/' + quote(study.MODEL, safe='/') + '/endpoints',
                           timeout=120)
    models = [m for m in catalog.get('data', []) if m.get('id') == study.MODEL]
    candidates = [e for e in endpoints.get('data', {}).get('endpoints', [])
                  if e.get('tag') == study.PROVIDER]
    historical_audit, _ = study.historical_data(config)
    _, historical_rows, _ = study.source_rows(historical_audit, 'P0')
    frozen_endpoint = historical_rows['DEV-001']['provider_endpoint']
    changed = ([key for key in CRITICAL_ENDPOINT
                if candidates[0].get(key) != frozen_endpoint.get(key)]
               if len(candidates) == 1 else [])
    # These are public route descriptions, never credentials or feedback.
    paid.durable(journal, {'event': 'route_observed', 'id': rid,
                           'model_catalog_entries': models,
                           'provider_endpoints': candidates,
                           'changed_experimental_fields': changed,
                           'utc': original.utc()})
    try:
        model, endpoint = paid.select_endpoint(
            study.MODEL, study.PROVIDER, catalog, endpoints,
            study.INPUT_PRICE, study.OUTPUT_PRICE)
        if changed:
            raise ValueError('Live experimental endpoint fields differ: ' + ','.join(changed))
        if paid.reasoning(model, endpoint, effort) != {'enabled': True, 'effort': effort}:
            raise ValueError('Live reasoning support differs')
        reserve = paid.reservation(endpoint, study.MAX_TOKENS,
                                   study.INPUT_PRICE, study.OUTPUT_PRICE)
        if reserve != RESERVE or reserve > study.CONFIGS[config]['proposed_child_budget']:
            raise ValueError('Live reserve differs from reviewed amount')
        inputs = {x['id']: x['feedback'] for x in paid.read_rows(ROOT / 'data/pilot/inputs.jsonl')}
        for request in plan['conditions'][condition]['development']:
            payload = request['payload']
            rebuilt = paid.make_payload(
                study.MODEL, endpoint, inputs[request['record_id']],
                payload['messages'][0]['content'],
                payload['response_format']['json_schema']['schema'],
                effort, study.MAX_TOKENS, study.INPUT_PRICE,
                study.OUTPUT_PRICE, model)
            if rebuilt != payload:
                raise ValueError('Live adapter would change frozen payload')
        return model, endpoint, reserve
    except Exception as exc:
        paid.durable(journal, {'event': 'route_rejected', 'id': rid,
                               'error_type': type(exc).__name__,
                               'changed_experimental_fields': changed,
                               'utc': original.utc()})
        raise


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


def verify_first_stop(config):
    """Bind the attempted prefix and prove the next ID was never sent."""
    kind = suffix(config)
    spec = FIRST_STOP[kind]
    first_sha = FIRST_MANIFEST[kind]
    manifest = first.verify_manifest(config, first_sha)
    stage = spec['stage']
    first.require_order(manifest, first_sha, *stage)
    files = first.stage_files(config, *stage)
    review = first.review_path(config, *stage)
    paths = {**files, 'review': review}
    first_dir = first.folder(config)
    child = first_dir / ('budget-qwen27-' + kind + '-v2-interruption-v1.jsonl')
    reconciliation = first_dir / 'terminal-reconciliation-after-route-change.json'
    paths.update(child=child, reconciliation=reconciliation,
                 manifest=first_dir / 'manifest.json')
    for name in ('claim', 'review', 'journal', 'attempts', 'responses',
                 'child', 'reconciliation'):
        if study.sha(paths[name]) != spec[name]:
            raise ValueError('First stopped source changed: ' + name)
    if study.sha(paths['manifest']) != first_sha:
        raise ValueError('First continuation manifest changed')
    first.verify_review(review, manifest, first_sha, *stage)
    claim = json.loads(files['claim'].read_text())
    if any(claim.get(k) != v for k, v in {
            'series_id': manifest['series_id'], 'configuration_id': config,
            'stage': first.stage_name(*stage), 'manifest_sha256': first_sha,
            'root_review_sha256': spec['review']}.items()):
        raise ValueError('First stopped claim differs')
    attempts, raw, journal = (rows(files[k]) for k in ('attempts', 'responses', 'journal'))
    ids = [f'DEV-{i:03d}' for i in range(spec['first_id'], spec['last_id'] + 1)]
    requests = first.selected_requests(config, *stage)[:len(ids)]
    if ([r.get('id') for r in attempts] != ids or
            [r.get('id') for r in raw] != ids or
            [r['record_id'] for r in requests] != ids or
            len(journal) != 2 + 3 * len(ids) or
            journal[0].get('event') != 'phase_started' or
            journal[-1].get('event') != 'phase_aborted' or
            journal[-1].get('reason') != 'exception_or_interruption'):
        raise ValueError('First stopped membership or terminal differs')
    charges = rows(child)
    prior_count = 0 if kind == 'medium' else 26
    if (charges[0] != {'event': 'budget', 'cap_usd': manifest['child_cap_usd']} or
            charges[-1].get('event') != 'partition_closed' or
            len(charges) != 2 + 2 * (prior_count + len(ids)) or
            any(e.get('event') not in ('reserve', 'settle') for e in charges[1:-1])):
        raise ValueError('First child settlement count differs')
    for i, (request, attempt, response) in enumerate(zip(requests, attempts, raw)):
        rid = ids[i]
        intent, started, finished = journal[1 + 3*i:4 + 3*i]
        aid = attempt.get('attempt_id')
        if (attempt.get('status') != 'ok' or attempt.get('billing_ok') is not True or
                attempt.get('cost_unknown') is not False or
                attempt.get('observed_cost_usd') is None or
                attempt.get('reference_labels_read') is not False or
                attempt.get('request') != request['payload'] or
                attempt.get('request_sha256') != request['request_sha256'] or
                attempt.get('manifest_sha256') != first_sha or
                response.get('id') != rid or response.get('attempt_id') != aid or
                response.get('request_sha256') != request['request_sha256'] or
                response.get('http_status') != 200 or
                response.get('body_truncated_at_limit') is not False or
                response.get('read_error') is not None or
                [(x.get('event'), x.get('id')) for x in (intent, started, finished)] !=
                    [('request_intent', rid), ('request_started', rid), ('request_finished', rid)] or
                started.get('attempt_id') != aid or finished.get('attempt_id') != aid or
                finished.get('status') != 'ok' or
                charges[1 + 2*(prior_count+i):3 + 2*(prior_count+i)] != [
                    {'event': 'reserve', 'attempt_id': aid, 'record_id': rid,
                     'usd': str(RESERVE)},
                    {'event': 'settle', 'attempt_id': aid,
                     'usd': attempt['observed_cost_usd']}]):
            raise ValueError('First stopped attempt or settlement differs: ' + rid)
        decoded = json.loads(base64.b64decode(response['body_base64'], validate=True))
        if decoded != attempt.get('raw_response'):
            raise ValueError('First stopped captured response differs')
    known = sum((paid.number(e['usd']) for e in charges if e['event'] == 'settle'), Decimal(0))
    cap = paid.number(manifest['child_cap_usd'])
    expected = {'event': 'partition_reconciled',
                'partition_id': manifest['partition_id'],
                'known_actual_usd': str(known),
                'unknown_upper_bound_usd': '0',
                'unused_allocation_released_usd': str(cap - known),
                'child_ledger': str(child.resolve()),
                'child_sha256': study.sha(child)}
    if (json.loads(reconciliation.read_text()) != expected or
            [e for e in rows(MASTER) if e.get('event') == 'partition_reconciled'
             and e.get('partition_id') == manifest['partition_id']] != [expected]):
        raise ValueError('First child reconciliation differs')
    sources = {name: binding(file) for name, file in paths.items()}
    for prior in first.stages(config)[:first.stages(config).index(stage)]:
        first.verify_stage_closure(manifest, first_sha, *prior)
        prefix = 'closed_' + '_'.join(prior) + '_'
        for name, file in first.stage_files(config, *prior).items():
            sources[prefix + name] = binding(file)
        sources[prefix + 'review'] = binding(first.review_path(config, *prior))
    if kind == 'xhigh':
        sources['closed_fresh3_P1_smoke_inspection'] = binding(
            first.folder(config) / 'fresh3/P1/smoke-inspection.json')
    return sources


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
    pid = f'qwen27-{kind}-v2-interruption-v2'
    cap = paid.number(item.get('cap_usd'))
    child = folder(config) / ('budget-' + pid + '.jsonl')
    if (item.get('id') != pid or cap < RESERVE or cap > Decimal('12.38') or
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
    stopped = verify_first_stop(config)
    item = budget_entry(config, budget_path, require_fresh=require_fresh)
    kind = suffix(config)
    old = study.BASE / config / 'fresh3/P0'
    sources = {name: binding(file) for name, file in RUNTIME.items()}
    sources['execution_manifest'] = binding(original.EXECUTION_MANIFEST)
    sources['new_budget_manifest'] = binding(budget_path)
    for name, source in stopped.items():
        sources['first_' + name] = source
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
            'method': 'descriptive-separate-child-never-sent-continuation',
            'clean_matched_three_eligible': False,
            'failed_attempted_id': f'DEV-{STOP[kind][0]:03d}',
            'first_continuation_last_sent_id': f"DEV-{FIRST_STOP[kind]['last_id']:03d}",
            'first_continuation_abort': 'pre_send_route_metadata_check',
            'never_sent_ids': schedule[0]['ids'],
            'reference_labels_read': False,
            'retry_policy': 'No replay of any attempted record in the original or first continuation',
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


def verify_runtime_sources(manifest):
    """Reject a helper or plan edit before reserving another request."""
    for key in (*RUNTIME, 'execution_manifest', 'plan_fresh3'):
        bound(manifest['source_bindings'][key])


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
            'first_child_sha256': manifest['source_bindings']['first_child']['sha256'],
            'first_reconciliation_sha256': manifest['source_bindings']['first_reconciliation']['sha256'],
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
            len(journal) != 2 + 4 * len(ids) or
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
    for index, (request, record, wire) in enumerate(zip(requests, attempts, raw)):
        route, intent, started, finished = journal[1 + 4*index:5 + 4*index]
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
                route.get('event') != 'route_observed' or route.get('id') != record['id'] or
                route.get('model_catalog_entries') != [record.get('model_catalog_entry')] or
                route.get('provider_endpoints') != [record.get('provider_endpoint')] or
                record.get('status') != 'ok' or record.get('billing_ok') is not True or
                record.get('cost_unknown') is not False or
                record.get('reserved_cost_usd') != str(RESERVE) or
                record.get('observed_cost_usd') is None or
                paid.number(record['observed_cost_usd']) > RESERVE or
                any(record.get('provider_endpoint', {}).get(k) !=
                    original_attempt['provider_endpoint'].get(k) for k in CRITICAL_ENDPOINT) or
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
                verify_runtime_sources(manifest)
                # Log observed public metadata before any request intent or reserve.
                model, endpoint, current_reserve = checked_live_controls(
                    plan, condition, journal, rid)
                if current_reserve != RESERVE:
                    raise ValueError('Live full request reserve differs')
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
