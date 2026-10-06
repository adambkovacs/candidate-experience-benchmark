#!/usr/bin/env python3
"""Proposed full-pass successor for OpenRouter native Kev/Jev Choice variants.

Offline preparation makes no request. Dispatch requires a reviewed all-60
context rationale (explicit estimate for Kev), an inspected terminal smoke, a separate pass
receipt, an exact $12.38 child allocation and a locked cross-provider hold.
No context proof or full-pass admission is supplied by this module.
"""
import argparse
import base64
from decimal import Decimal
import fcntl
import json
import os
from pathlib import Path
import time

from development_benchmark import ROOT
import openrouter_decision_smoke as decision
import openrouter_native_variants_plan as frozen
import openrouter_native_variants_v2 as smoke_v2
import openrouter_paid_benchmark as paid
import paid_budget_partitions_v3 as partitions

BASE = ROOT / 'results/route-audits/native-variants-full-v1-20261006'
MASTER = paid.LEDGER_PATH
AUTHORITY = smoke_v2.AUTHORITY
SCHEMA = 'openrouter-native-choice-full-v1'
PASSES = ('fresh1', 'fresh2', 'fresh3')
IDS = [f'DEV-{i:03d}' for i in range(1, 61)]


def paths(base, config, stage=None):
    base = Path(base)
    root = base / config
    result = {'manifest': base / (config + '.json'),
              'estimate': root / 'context-estimate.proposed.json',
              'context': root / 'provider-context-proof.json',
              'inspection': root / 'smoke-inspection.json'}
    if stage is not None:
        result.update({'budget': root / (stage + '.budget.json'),
                       'receipt': root / (stage + '.root-review.json'),
                       'stage': root / stage,
                       'lock': root / (stage + '.admission.lock')})
    return result


def kev_context_estimate(config, original, *, root=ROOT, smoke_base=smoke_v2.BASE):
    """Conservative admission estimate from 120 actual P0 provider usages.

    The multiplier and 256-token margin are deliberately generous, but not a
    theorem about SiliconFlow tokenization. Root must review this as an
    estimate, and any provider context rejection stops the pass unchanged.
    """
    if original['route'] != 'kev':
        raise ValueError('Kev P0 usage estimate does not apply to another route')
    sources = ('results/route-audits/decision-kev-development-20260930/attempts.jsonl',
               'results/route-audits/decision-kev-repeats-20260930/fresh2/attempts.jsonl')
    usage_passes = []
    for name in sources:
        path = Path(root) / name
        rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
        completion_path = path.with_name('completion.json')
        completion = json.loads(completion_path.read_text())
        if (completion.get('record_count') != 60 or completion.get('valid_count') != 60 or
                completion.get('attempts_sha256') != smoke_v2.file_sha(path) or
                completion.get('reference_labels_read') is not False):
            raise ValueError('Kev P0 provider usage source lacks terminal completion')
        if len(rows) != 180:
            raise ValueError('Kev P0 source lacks 60 terminal three-event attempts')
        counts = []
        for i, item in enumerate(original['requests']):
            reserved, response, validated = rows[3*i:3*i+3]
            body = response.get('body') or {}
            usage = body.get('usage') or {}
            count = usage.get('input_tokens')
            raw = base64.b64decode(response.get('raw_response_base64', ''), validate=True)
            if ([x.get('stage') for x in (reserved, response, validated)] !=
                    ['reserved', 'response', 'validated'] or
                    any(x.get('id') != item['id'] for x in (reserved, response, validated)) or
                    reserved.get('payload_sha256') != item['p0_payload_sha256'] or
                    response.get('http_status') != 200 or
                    response.get('cost_unknown') is not False or
                    smoke_v2.sha(raw) != response.get('raw_response_sha256') or
                    len(raw) != response.get('raw_response_size_bytes') or
                    json.loads(raw) != body or
                    not isinstance(validated.get('prediction'), dict) or
                    body.get('model') != decision.ROUTES['kev']['version'] or
                    body.get('provider') != decision.ROUTES['kev']['provider'] or
                    type(count) is not int or not 0 <= count <= 8192):
                raise ValueError('Kev P0 provider usage source differs')
            counts.append(count)
        usage_passes.append(counts)
    if usage_passes[0] != usage_passes[1]:
        raise ValueError('Two Kev P0 passes disagree on provider token accounting')
    estimated = []
    for item, p0_tokens in zip(original['requests'], usage_passes[0]):
        payload = item['payload']
        parent = decision.request_payload(payload['state']['feedback'],
                                          payload['state']['policy'], decision.ROUTES['kev'])
        if smoke_v2.sha(decision.canonical(parent)) != item['p0_payload_sha256']:
            raise ValueError('Kev P0 parent request differs')
        added = sum(len(payload['questions'][key]['instructions'].encode('utf-8')) -
                    len(parent['questions'][key]['instructions'].encode('utf-8'))
                    for key in payload['questions'])
        if added <= 0:
            raise ValueError('Native variant added no instruction bytes')
        bound = p0_tokens + 2 * added + 256
        if bound > 8192:
            raise ValueError('Conservative Kev context estimate exceeds listed limit')
        estimated.append({'id': item['id'], 'p0_provider_input_tokens': p0_tokens,
                          'added_instruction_utf8_bytes': added,
                          'estimated_input_token_upper_bound': bound})
    smoke_rows = [json.loads(x) for x in
                  (smoke_v2.paths(smoke_base, config)['stage'] / 'attempts.jsonl').read_text().splitlines()
                  if x.strip()]
    observed = []
    for i in range(3):
        response = smoke_rows[4*i+2]
        count = response['body']['usage']['input_tokens']
        if (type(count) is not int or count > estimated[i]['estimated_input_token_upper_bound'] or
                response['id'] != estimated[i]['id']):
            raise ValueError('Variant smoke provider usage exceeds context estimate')
        observed.append({'id': response['id'],
                         'variant_provider_input_tokens': count,
                         'observed_added_tokens': count - usage_passes[0][i]})
    return {'schema': SCHEMA + '-conservative-context-estimate',
            'status': 'proposed_for_review', 'route': 'kev',
            'configuration_id': config, 'condition': original['condition'],
            'request_set_sha256': original['requests_sha256'],
            'context_limit': 8192, 'method': 'P0_provider_usage_plus_2x_added_UTF8_bytes_plus_256',
            'provider_guarantee': False,
            'context_rejection_policy': 'stop_without_retry_and_preserve_raw',
            'p0_attempt_sources': [{'path': name,
                                    'sha256': smoke_v2.file_sha(Path(root) / name),
                                    'completion_sha256': smoke_v2.file_sha((Path(root) / name).with_name('completion.json'))}
                                   for name in sources],
            'smoke_attempts_sha256': smoke_v2.file_sha(smoke_v2.paths(smoke_base, config)['stage'] / 'attempts.jsonl'),
            'smoke_observed_input_tokens': observed,
            'per_record': estimated,
            'max_p0_provider_input_tokens': max(usage_passes[0]),
            'max_estimated_input_token_upper_bound': max(x['estimated_input_token_upper_bound'] for x in estimated),
            'source_links': ['https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request',
                             'https://github.com/jaredpalmer/kev/blob/main/kev/model.py']}


def _smoke_proof(config, *, smoke_base=smoke_v2.BASE):
    p = smoke_v2.paths(smoke_base, config)
    completion_path = p['stage'] / 'completion.json'
    attempts_path = p['stage'] / 'attempts.jsonl'
    if not completion_path.is_file() or not attempts_path.is_file():
        raise ValueError('Three-record native smoke has no terminal evidence')
    completion = json.loads(completion_path.read_text())
    rows = [json.loads(line) for line in attempts_path.read_text().splitlines() if line.strip()]
    if (completion.get('schema') != smoke_v2.SCHEMA + '-completion' or
            completion.get('configuration_id') != config or completion.get('stage') != 'smoke' or
            completion.get('ids') != list(smoke_v2.IDS) or completion.get('valid_count') != 3 or
            completion.get('manifest_sha256') != smoke_v2.file_sha(p['manifest']) or
            completion.get('attempts_sha256') != smoke_v2.file_sha(attempts_path) or
            completion.get('endpoint_catalog_sha256') != smoke_v2.file_sha(p['stage'] / 'endpoint-catalog.json') or
            completion.get('reference_labels_read') is not False or len(rows) != 12):
        raise ValueError('Native smoke completion binding differs')
    for i, rid in enumerate(smoke_v2.IDS):
        part = rows[4*i:4*i+4]
        if ([x.get('stage') for x in part] != ['reserved', 'started', 'response', 'parsed'] or
                any(x.get('id') != rid for x in part) or
                part[2].get('http_status') != 200 or part[2].get('cost_unknown') is not False or
                (part[2].get('body') or {}).get('truncated') is True or
                part[3].get('valid') is not True):
            raise ValueError('Native smoke has failed or missing output')
    return {'completion_sha256': smoke_v2.file_sha(completion_path),
            'attempts_sha256': smoke_v2.file_sha(attempts_path),
            'endpoint_sha256': completion['endpoint_catalog_sha256'],
            'known_actual_cost_usd': completion['known_actual_cost_usd']}


def build_manifest(config, *, root=ROOT, smoke_base=smoke_v2.BASE):
    smoke_plan = smoke_v2.verify(config, smoke_base, root=root)
    original = frozen.build_plan(root)[config]
    if (original['requests_sha256'] != smoke_plan['frozen_requests_sha256'] or
            smoke_v2.sha(decision.canonical(original['requests'])) != original['requests_sha256'] or
            [x['id'] for x in original['requests']] != IDS):
        raise ValueError('Full native request set differs from frozen smoke source')
    for item in original['requests']:
        if smoke_v2.sha(decision.canonical(item['payload'])) != item['payload_sha256']:
            raise ValueError('Full native request bytes differ')
    route = decision.ROUTES[original['route']]
    estimate = (kev_context_estimate(config, original, root=root, smoke_base=smoke_base)
                if original['route'] == 'kev' else None)
    return {'schema': SCHEMA + '-offline-plan', 'status': 'proposed_not_admitted',
            'inference_performed': False, 'reference_labels_read': False,
            'configuration_id': config, 'route': original['route'],
            'condition': original['condition'], 'model': route['model'],
            'provider': route['provider'], 'provider_tag': route['tag'],
            'returned_model': route['version'], 'context_tokens': route['context'],
            'frozen_manifest_sha256': smoke_plan['frozen_manifest_sha256'],
            'smoke_v2_manifest_sha256': smoke_v2.file_sha(smoke_v2.paths(smoke_base, config)['manifest']),
            'smoke_proof': _smoke_proof(config, smoke_base=smoke_base),
            'context_estimate_sha256': smoke_v2.sha(decision.canonical(estimate)) if estimate else None,
            'context_review_mode': ('reviewed_conservative_estimate' if estimate else
                                    'exact_provider_accounting_required'),
            'request_set_sha256': original['requests_sha256'],
            'ids': IDS, 'request_sha256': [x['payload_sha256'] for x in original['requests']],
            'per_request_full_context_bound_usd': str(decision.bound(route)),
            'whole_pass_bound_usd': str(60 * decision.bound(route)),
            'budget_master_cap_usd': '12.38',
            'global_authority_cap_usd': str(smoke_v2.AUTHORITY_CAP),
            'passes': [{'stage': stage, 'pass_id': config + '-' + stage,
                        'partition_id': config + '-' + stage + '-full-v1',
                        'status': 'proposed_not_admitted'} for stage in PASSES],
            'admission': {'reviewed_all60_context_rationale_required': True,
                          'reviewed_smoke_inspection_required': True,
                          'separate_review_and_budget_per_pass': True}}


def prepare(config, base=BASE, *, root=ROOT, smoke_base=smoke_v2.BASE):
    value = build_manifest(config, root=root, smoke_base=smoke_base)
    p = paths(base, config)
    path = p['manifest']
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as handle:
        handle.write(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    if value['context_review_mode'] == 'reviewed_conservative_estimate':
        original = frozen.build_plan(root)[config]
        estimate = kev_context_estimate(config, original, root=root, smoke_base=smoke_base)
        p['estimate'].parent.mkdir(parents=True, exist_ok=True)
        with p['estimate'].open('x') as handle:
            handle.write(json.dumps(estimate, indent=2, ensure_ascii=False) + '\n')
    return smoke_v2.file_sha(path)


def verify(config, base=BASE, *, root=ROOT, smoke_base=smoke_v2.BASE):
    value = build_manifest(config, root=root, smoke_base=smoke_base)
    path = paths(base, config)['manifest']
    if path.read_bytes() != (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode():
        raise ValueError('Proposed full native manifest differs from closed source')
    if value['context_review_mode'] == 'reviewed_conservative_estimate':
        original = frozen.build_plan(root)[config]
        estimate = kev_context_estimate(config, original, root=root, smoke_base=smoke_base)
        if paths(base, config)['estimate'].read_bytes() != (json.dumps(estimate, indent=2, ensure_ascii=False) + '\n').encode():
            raise ValueError('Proposed conservative context estimate differs')
    return value


def context_proof(config, manifest, *, base=BASE):
    """Require root review of exact accounting or the source-bound Kev estimate."""
    p = paths(base, config)['context']
    proof = json.loads(p.read_text())
    if manifest['context_review_mode'] == 'reviewed_conservative_estimate':
        estimate_path = paths(base, config)['estimate']
        estimate = json.loads(estimate_path.read_text())
        if (smoke_v2.sha(decision.canonical(estimate)) != manifest['context_estimate_sha256'] or
                estimate['request_set_sha256'] != manifest['request_set_sha256'] or
                estimate['max_estimated_input_token_upper_bound'] > manifest['context_tokens'] or
                proof != {'schema': SCHEMA + '-context-estimate-review',
                          'approved': True, 'reviewer': 'root',
                          'configuration_id': config,
                          'estimate_sha256': smoke_v2.file_sha(estimate_path),
                          'request_set_sha256': manifest['request_set_sha256'],
                          'method': 'reviewed_conservative_estimate',
                          'provider_guarantee_claimed': False,
                          'full_context_money_reservation': True,
                          'context_rejection_policy': 'stop_without_retry_and_preserve_raw'}):
            raise ValueError('Reviewed all-60 Kev context estimate differs')
        return smoke_v2.file_sha(p)
    evidence_path = Path(proof.get('evidence_path', ''))
    if not evidence_path.is_absolute() or not evidence_path.is_file():
        raise ValueError('Provider token-accounting evidence file absent')
    if (proof.get('schema') != SCHEMA + '-provider-context-proof' or
            proof.get('provider_accepted') is not True or
            proof.get('method') not in ('exact_provider_tokenizer', 'provider_preflight_endpoint') or
            proof.get('model') != manifest['model'] or
            proof.get('provider_tag') != manifest['provider_tag'] or
            proof.get('returned_model') != manifest['returned_model'] or
            proof.get('request_set_sha256') != manifest['request_set_sha256'] or
            proof.get('ids') != IDS or proof.get('request_sha256') != manifest['request_sha256'] or
            proof.get('context_limit') != manifest['context_tokens'] or
            proof.get('evidence_sha256') != smoke_v2.file_sha(evidence_path) or
            not isinstance(proof.get('accounted_input_tokens'), list) or
            len(proof['accounted_input_tokens']) != 60 or
            any(type(n) is not int or not 0 <= n <= manifest['context_tokens']
                for n in proof['accounted_input_tokens']) or
            proof.get('truncation') is not False or
            not isinstance(proof.get('reviewer'), str) or not proof['reviewer'].strip()):
        raise ValueError('Provider-accepted all-60 context proof differs')
    return smoke_v2.file_sha(p)


def smoke_inspection(config, manifest, *, base=BASE):
    p = paths(base, config)['inspection']
    value = json.loads(p.read_text())
    if value != {'schema': SCHEMA + '-smoke-inspection', 'reviewer': 'root',
                 'configuration_id': config,
                 'smoke_completion_sha256': manifest['smoke_proof']['completion_sha256'],
                 'smoke_attempts_sha256': manifest['smoke_proof']['attempts_sha256'],
                 'all_three_raw_distributions_inspected': True,
                 'approved_for_full_pass_review': True}:
        raise ValueError('Reviewed raw smoke inspection differs')
    return smoke_v2.file_sha(p)


def predecessor(config, stage, manifest, *, base=BASE):
    if stage == 'fresh1':
        return {'smoke_completion_sha256': manifest['smoke_proof']['completion_sha256']}
    previous = PASSES[PASSES.index(stage) - 1]
    previous_path = paths(base, config, previous)['stage'] / 'completion.json'
    completed = json.loads(previous_path.read_text())
    attempts_path = previous_path.parent / 'attempts.jsonl'
    if (completed.get('schema') != SCHEMA + '-completion' or
            completed.get('configuration_id') != config or completed.get('stage') != previous or
            completed.get('ids') != IDS or
            type(completed.get('valid_count')) is not int or
            type(completed.get('invalid_count')) is not int or
            completed['valid_count'] + completed['invalid_count'] != 60 or
            completed.get('attempts_sha256') != smoke_v2.file_sha(attempts_path)):
        raise ValueError('Previous full native pass lacks exact completion')
    return {'smoke_completion_sha256': manifest['smoke_proof']['completion_sha256'],
            'previous_completion_sha256': smoke_v2.file_sha(previous_path),
            'previous_attempts_sha256': completed['attempts_sha256']}


def budget_identity(config, stage, manifest, budget_path, *, base=BASE, master=MASTER):
    p = paths(base, config, stage)
    if Path(budget_path).resolve() != p['budget'].resolve():
        raise ValueError('Wrong full-pass budget path')
    budget = json.loads(Path(budget_path).read_text())
    pid = manifest['passes'][PASSES.index(stage)]['partition_id']
    child = p['budget'].parent / (p['budget'].stem + '-' + pid + '.jsonl')
    entry = {'id': pid, 'cap_usd': manifest['whole_pass_bound_usd'],
             'child_ledger': str(child.resolve()), 'model': manifest['model'],
             'provider': manifest['provider_tag'], 'reasoning': 'none'}
    if (budget.get('version') != 'paid-partitions-v1' or
            budget.get('master_ledger') != str(Path(master).resolve()) or
            budget.get('partitions') != [entry] or not child.is_file() or not child.stat().st_size):
        raise ValueError('Exact full-pass child allocation differs')
    identity = {'manifest_sha256': smoke_v2.file_sha(p['manifest']),
                'budget_manifest_sha256': smoke_v2.file_sha(budget_path),
                'partition_id': pid, 'child_ledger': str(child.resolve()),
                'cap_usd': entry['cap_usd']}
    return smoke_v2.sha(decision.canonical(identity))


def expected_receipt(config, stage, manifest, budget_path, context_sha, inspection_sha,
                     predecessor_proof, hold_source, *, base=BASE):
    p = paths(base, config, stage)
    return {'schema': SCHEMA + '-root-review', 'approved': True, 'reviewer': 'root',
            'configuration_id': config, 'stage': stage,
            'manifest_sha256': smoke_v2.file_sha(p['manifest']),
            'runner_sha256': smoke_v2.file_sha(__file__),
            'context_proof_sha256': context_sha, 'smoke_inspection_sha256': inspection_sha,
            'predecessor_proof': predecessor_proof,
            'budget_manifest_sha256': smoke_v2.file_sha(budget_path),
            'partition_id': manifest['passes'][PASSES.index(stage)]['partition_id'],
            'child_cap_usd': manifest['whole_pass_bound_usd'],
            'global_hold_id': manifest['passes'][PASSES.index(stage)]['partition_id'],
            'global_hold_usd': manifest['whole_pass_bound_usd'],
            'global_hold_source_sha256': hold_source,
            'global_authority_cap_usd': str(smoke_v2.AUTHORITY_CAP),
            'global_authority_approval_sha256': smoke_v2.AUTHORITY_APPROVAL_SHA,
            'ids': IDS, 'request_sha256': manifest['request_sha256'],
            'reference_labels_sent': False}


def validate_receipt(config, stage, manifest, receipt_path, budget_path, context_sha,
                     inspection_sha, predecessor_proof, hold_source, *, base=BASE):
    p = paths(base, config, stage)
    if Path(receipt_path).resolve() != p['receipt'].resolve():
        raise ValueError('Wrong full-pass receipt path')
    receipt = json.loads(Path(receipt_path).read_text())
    head = receipt.get('global_authority_head_sha256')
    if (not isinstance(head, str) or len(head) != 64 or
            any(c not in '0123456789abcdef' for c in head) or
            receipt != {**expected_receipt(config, stage, manifest, budget_path, context_sha,
                         inspection_sha, predecessor_proof, hold_source, base=base),
                        'global_authority_head_sha256': head}):
        raise ValueError('Independent full-pass receipt differs')
    return receipt


def execute(config, stage, receipt_path, budget_path, *, base=BASE, root=ROOT,
            smoke_base=smoke_v2.BASE, master=MASTER, authority=AUTHORITY,
            catalog_fetch=decision.fetch_catalog, transport=decision.post,
            open_child=partitions.open_partition, token=None):
    if stage not in PASSES:
        raise ValueError('Unknown declared full-pass stage')
    manifest = verify(config, base, root=root, smoke_base=smoke_base)
    context_sha = context_proof(config, manifest, base=base)
    inspection_sha = smoke_inspection(config, manifest, base=base)
    prior = predecessor(config, stage, manifest, base=base)
    source = budget_identity(config, stage, manifest, budget_path, base=base, master=master)
    receipt = validate_receipt(config, stage, manifest, receipt_path, budget_path,
                               context_sha, inspection_sha, prior, source, base=base)
    p = paths(base, config, stage)
    if p['stage'].exists():
        raise FileExistsError('Full native pass already claimed; no replay')
    route = decision.ROUTES[manifest['route']]
    catalog = catalog_fetch(route)
    decision.validate_endpoint(catalog, route)
    token = os.environ.get('OPENROUTER_API_KEY') if token is None else token
    if not token:
        raise ValueError('OPENROUTER_API_KEY required')
    p['lock'].parent.mkdir(parents=True, exist_ok=True)
    with p['lock'].open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if p['stage'].exists():
            raise FileExistsError('Full native pass already claimed; no replay')
        if (context_proof(config, manifest, base=base) != context_sha or
                smoke_inspection(config, manifest, base=base) != inspection_sha or
                predecessor(config, stage, manifest, base=base) != prior or
                budget_identity(config, stage, manifest, budget_path, base=base, master=master) != source or
                smoke_v2.file_sha(p['manifest']) != receipt['manifest_sha256']):
            raise ValueError('Reviewed full-pass evidence changed before admission')
        # Source edits after initial manifest verification stop before hold.
        current = frozen.build_plan(root)[config]
        if (current['requests_sha256'] != manifest['request_set_sha256'] or
                smoke_v2.sha(decision.canonical(current['requests'])) != manifest['request_set_sha256'] or
                [x['id'] for x in current['requests']] != IDS or
                [x['payload_sha256'] for x in current['requests']] != manifest['request_sha256']):
            raise ValueError('Current full request set differs from reviewed manifest')
        approved = []
        for item in current['requests']:
            request = decision.canonical(item['payload'])
            if smoke_v2.sha(request) != item['payload_sha256']:
                raise ValueError('Current full request bytes differ')
            approved.append((item['id'], item['payload_sha256'], request))
        pid = manifest['passes'][PASSES.index(stage)]['partition_id']
        ledger = open_child(master, budget_path, pid, manifest['model'], manifest['provider_tag'], 'none')
        try:
            amount = Decimal(manifest['per_request_full_context_bound_usd'])
            cap = Decimal(manifest['whole_pass_bound_usd'])
            _, pending, blocked = ledger.state()
            if (ledger.master_cap != Decimal('12.38') or ledger.cap != cap or
                    pending or blocked or ledger.closed or ledger.accounted() + cap > ledger.cap):
                raise ValueError('Exact child cannot cover whole full pass')
            smoke_v2.hold_authority(authority, pid, cap, source,
                                    receipt['global_authority_head_sha256'], stage_path=p['stage'])
            p['stage'].mkdir(exist_ok=False)
            (p['stage'] / 'review-receipt.json').write_bytes(Path(receipt_path).read_bytes())
            (p['stage'] / 'endpoint-catalog.json').write_bytes(decision.canonical(catalog))
            known = Decimal(0)
            valid_ids, invalid_ids = [], []
            with (p['stage'] / 'attempts.jsonl').open('x') as attempts:
                for rid, request_sha, request in approved:
                    if smoke_v2.sha(request) != request_sha:
                        raise ValueError('Approved full request changed before reservation')
                    attempt = ledger.reserve(amount, pid + ':' + rid)
                    paid.durable(attempts, {'stage': 'reserved', 'id': rid, 'attempt_id': attempt,
                        'request_sha256': request_sha, 'reserved_cost_usd': str(amount),
                        'cost_unknown': True})
                    started = decision.utc_now()
                    paid.durable(attempts, {'stage': 'started', 'id': rid, 'attempt_id': attempt,
                        'request_start_utc': started,
                        'request_base64': base64.b64encode(request).decode(), 'cost_unknown': True})
                    start_ns = time.monotonic_ns()
                    try:
                        status, raw = transport(json.loads(request), token)
                    except BaseException as error:
                        paid.durable(attempts, {'stage': 'transport_error', 'id': rid,
                            'attempt_id': attempt, 'error_type': type(error).__name__,
                            'request_end_utc': decision.utc_now(),
                            'client_request_elapsed_ns': time.monotonic_ns() - start_ns,
                            'reserved_cost_usd': str(amount), 'cost_unknown': True})
                        raise
                    try:
                        body, parse_error = json.loads(raw), None
                    except (ValueError, UnicodeDecodeError) as error:
                        body, parse_error = None, type(error).__name__
                    actual = decision.response_cost(body)
                    paid.durable(attempts, {'stage': 'response', 'id': rid, 'attempt_id': attempt,
                        'http_status': status, 'body': body, 'parse_error_type': parse_error,
                        'raw_response_base64': base64.b64encode(raw).decode(),
                        'raw_response_sha256': smoke_v2.sha(raw), 'raw_response_size_bytes': len(raw),
                        'request_start_utc': started, 'request_end_utc': decision.utc_now(),
                        'client_request_elapsed_ns': time.monotonic_ns() - start_ns,
                        'reserved_cost_usd': str(amount), 'cost_unknown': actual is None,
                        'actual_cost_usd': str(actual) if actual is not None else None})
                    if actual is None:
                        raise ValueError('Unknown provider cost; reservation remains pending')
                    if not ledger.settle(attempt, actual):
                        raise ValueError('Actual cost exceeded reserve; child blocked')
                    known += actual
                    if status != 200:
                        paid.durable(attempts, {'stage': 'parsed', 'id': rid,
                            'attempt_id': attempt, 'valid': False, 'reason': 'non_200_http'})
                        raise ValueError('Provider returned non-200; no retry')
                    usage = body.get('usage') if isinstance(body, dict) else None
                    if (not isinstance(body, dict) or body.get('model') != route['version'] or
                            body.get('provider') != route['provider'] or
                            not isinstance(usage, dict) or
                            type(usage.get('input_tokens')) is not int or
                            not 0 <= usage['input_tokens'] <= route['context'] or
                            type(usage.get('output_tokens')) is not int or
                            usage['output_tokens'] < 0):
                        paid.durable(attempts, {'stage': 'parsed', 'id': rid,
                            'attempt_id': attempt, 'valid': False,
                            'reason': 'route_or_usage_control_failure'})
                        raise ValueError('Returned model, provider or usage differs; no retry')
                    try:
                        if (body.get('truncated') is True or
                                (isinstance(body.get('usage'), dict) and
                                 body['usage'].get('state_tokens') is not None and
                                 body['usage'].get('state_tokens_used') is not None and
                                 body['usage']['state_tokens_used'] < body['usage']['state_tokens'])):
                            raise ValueError('provider_truncated_native_state')
                        prediction = decision.validate_response(body, route)
                    except ValueError as error:
                        paid.durable(attempts, {'stage': 'parsed', 'id': rid,
                            'attempt_id': attempt, 'valid': False, 'reason': str(error)})
                        if str(error) == 'provider_truncated_native_state':
                            raise
                        invalid_ids.append(rid)
                        continue
                    paid.durable(attempts, {'stage': 'parsed', 'id': rid,
                        'attempt_id': attempt, 'valid': True, 'prediction': prediction})
                    valid_ids.append(rid)
            completion = {'schema': SCHEMA + '-completion', 'configuration_id': config,
                'stage': stage, 'ids': IDS, 'valid_count': len(valid_ids),
                'invalid_count': len(invalid_ids), 'invalid_ids': invalid_ids,
                'manifest_sha256': smoke_v2.file_sha(p['manifest']),
                'context_proof_sha256': context_sha, 'smoke_inspection_sha256': inspection_sha,
                'predecessor_proof': prior,
                'receipt_sha256': smoke_v2.file_sha(receipt_path),
                'budget_manifest_sha256': smoke_v2.file_sha(budget_path),
                'endpoint_catalog_sha256': smoke_v2.file_sha(p['stage'] / 'endpoint-catalog.json'),
                'attempts_sha256': smoke_v2.file_sha(p['stage'] / 'attempts.jsonl'),
                'known_actual_cost_usd': str(known), 'reference_labels_read': False}
            (p['stage'] / 'completion.json').write_text(json.dumps(completion, indent=2) + '\n')
            return completion
        finally:
            ledger.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'verify', 'run'))
    parser.add_argument('--configuration', required=True)
    parser.add_argument('--stage', choices=PASSES)
    parser.add_argument('--review-receipt', type=Path)
    parser.add_argument('--budget-manifest', type=Path)
    args = parser.parse_args()
    if args.action == 'prepare':
        print(prepare(args.configuration))
    elif args.action == 'verify':
        print(json.dumps(verify(args.configuration)['admission'], indent=2))
    else:
        if args.stage is None or args.review_receipt is None or args.budget_manifest is None:
            parser.error('run needs stage, review receipt and budget manifest')
        print(json.dumps(execute(args.configuration, args.stage, args.review_receipt,
                                 args.budget_manifest), indent=2))


if __name__ == '__main__':
    main()
