#!/usr/bin/env python3
"""Build source-bound, offline findings for the legacy Qwen fresh-three plan."""

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import re

import build_repeat_findings as shared
from development_benchmark import valid

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/legacy-qwen-fresh3-v1')
QWEN35_SUFFIX = BASE / 'qwen35-p0-unsent-suffix-v1'
QWEN35_COMPOSITE_REVIEW = QWEN35_SUFFIX / 'composite.root-review.json'
QWEN35_SUCCESSOR = BASE / 'qwen35-remaining-phases-v1'
QWEN35_SUCCESSOR_MANIFEST = QWEN35_SUCCESSOR / 'manifest.json'
QWEN35_SUCCESSOR_MANIFEST_SHA = '5b74a42cfa922219813c4e83037f05cbe4f769094c3776e5a9a48f24ed8423ae'
QWEN35_SUCCESSOR_CONTROLLER = Path('scripts/qwen35_remaining_phases_v1.cjs')
QWEN35_SUCCESSOR_CONTROLLER_SHA = '25628fb191433c83991b31de34db67760f184d7f973bb8825d4dedfc36447e33'
QWEN35_CONTINUATION = BASE / 'qwen35-after-smoke-failure-v1'
QWEN35_CONTINUATION_PROPOSAL = QWEN35_CONTINUATION / 'proposal.json'
QWEN35_CONTINUATION_PROPOSAL_SHA = '36dfc88704064b8317c8901326b002c2d5605911ee423e742b2c39860f455e3d'
QWEN35_CONTINUATION_REVIEW = QWEN35_CONTINUATION / 'design.root-review.json'
QWEN35_CONTINUATION_REVIEW_SHA = '170f82217ba5742d4004a1d20918d5a966093033c4c16d32e5206eba11ce54e1'
QWEN35_CONTINUATION_CONTROLLER = Path('scripts/qwen35_after_smoke_failure_v1.cjs')
QWEN35_CONTINUATION_CONTROLLER_SHA = '6978090d25ed4d5b8d98a88c85f4fb053aa7bc423caa45ab474daa5c32c99370'
MANIFEST = BASE / 'manifest.json'
MANIFEST_SHA = '7ef8c42a5fd66308e46c0dd885d92373bdbe3ba0e4aa7bdecf58298b82dd80c0'
LABELS = Path('data/pilot/proposed_labels.jsonl')
LABELS_SHA = '440fa16759473b6d4ff52fe7e7296e5f2dfca0a58f5df26f20aef0daafed1464'
SUCCESSOR_MANIFEST = Path('results/repeatability-v1/legacy-qwen-sdk-format-successor-v1/manifest.json')
SUCCESSOR_MANIFEST_SHA = '7538dacb509f670e95182aae60d381daba96777c9a0fcca3a4124203012ed057'
SUCCESSOR_CONTROLLER = Path('scripts/legacy_qwen_sdk_format_successor_v1.cjs')
SUCCESSOR_CONTROLLER_SHA = '88890d4d981f74df38f09c05529a017e1929bbb3574d856777b1fa6613dedbc5'
SUCCESSOR17_MANIFEST = Path('results/repeatability-v1/legacy-qwen-17off-format-successor-v1/manifest.json')
SUCCESSOR17_CONTROLLER = Path('scripts/legacy_qwen_17off_format_successor_v1.cjs')
SUCCESSOR17_INSPECTION = SUCCESSOR17_MANIFEST.parent / 'smoke-inspection.json'
OUTPUT = Path('public-site/legacy-qwen-repeats.json')
TARGET = 'qwen3-0.6b-q4km-nonthinking'
PASSES = ('fresh1', 'fresh2', 'fresh3')
CONDITIONS = ('P0', 'P1', 'P2')
IDS = tuple(f'DEV-{i:03d}' for i in range(1, 61))
CONFIGS = (TARGET, 'qwen3-0.6b-sdk-thinking-on', 'qwen3-0.6b-sdk-thinking-off',
           'qwen3-1.7b-sdk-thinking-on', 'qwen3-1.7b-sdk-thinking-off',
           'qwen3.5-4b-sdk-thinking-on')
DISPLAY_NAMES = {
    TARGET: 'Qwen3 0.6B · HTTP · thinking off',
    'qwen3-0.6b-sdk-thinking-on': 'Qwen3 0.6B · SDK · thinking on',
    'qwen3-0.6b-sdk-thinking-off': 'Qwen3 0.6B · SDK · thinking off',
    'qwen3-1.7b-sdk-thinking-on': 'Qwen3 1.7B · SDK · thinking on',
    'qwen3-1.7b-sdk-thinking-off': 'Qwen3 1.7B · SDK · thinking off',
    'qwen3.5-4b-sdk-thinking-on': 'Qwen3.5 4B · SDK · thinking on',
}
FIELDS = shared.FIELDS


def file_at(root, relative):
    path = (root / relative).resolve()
    path.relative_to(root.resolve())
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(root, relative):
    payload = file_at(root, relative).read_bytes()
    if not payload.endswith(b'\n') or any(not line.strip() for line in payload.splitlines()):
        raise ValueError(f'Incomplete JSONL source: {relative}')
    return [json.loads(line) for line in payload.splitlines()]


def binder(root):
    bindings = {}

    def bind(relative, expected=None):
        name = str(relative)
        actual = sha(file_at(root, relative))
        if expected is not None and actual != expected:
            raise ValueError(f'Source hash differs: {name}')
        bindings[name] = actual
        return actual

    return bind, bindings


def load_context(root):
    bind, bindings = binder(root)
    bind(MANIFEST, MANIFEST_SHA)
    plan = json.loads(file_at(root, MANIFEST).read_text())
    if (plan.get('schema') != 'legacy-qwen-fresh3-admission-v1' or
            plan.get('status') != 'offline_prepared_unapproved' or
            set(plan.get('configurations', {})) != set(CONFIGS) or
            plan.get('reference_labels_used_for_requests') is not False or
            plan.get('historical_predictions_used_for_requests') is not False or
            plan.get('policy', {}).get('denominator') != 60 or
            plan['policy'].get('smoke_ids') != list(IDS[:3])):
        raise ValueError('Frozen legacy Qwen plan differs')
    bind('scripts/legacy_qwen_repeat_admission.cjs', plan['controller_sha256'])
    for name, expected in plan['source_sha256'].items():
        bind(name, expected)
    bind(LABELS, LABELS_SHA)
    label_rows = read_rows(root, LABELS)
    if ([row.get('id') for row in label_rows] != list(IDS) or
            any(row.get('review_version') != '0.2' or not valid(row.get('proposed_labels'))
                for row in label_rows)):
        raise ValueError('Frozen v0.2 reference membership differs')
    labels = {row['id']: row['proposed_labels'] for row in label_rows}
    for name in CONFIGS:
        config = plan['configurations'][name]
        schedule = config.get('schedule', [])
        expected_order = ([['P0', 'P1', 'P2'], ['P1', 'P2', 'P0'], ['P2', 'P0', 'P1']]
                          if name == TARGET else
                          [['P0', 'P2', 'P1'], ['P2', 'P1', 'P0'], ['P1', 'P0', 'P2']])
        if ([item.get('name') for item in schedule] != list(PASSES) or
                [item.get('conditions') for item in schedule] != expected_order or
                set(config.get('conditions', {})) != set(CONDITIONS)):
            raise ValueError(f'Legacy Qwen schedule differs: {name}')
        historical = config['historical_manifest']
        bind(historical['file'], historical['sha256'])
        for condition in CONDITIONS:
            planned = config['conditions'][condition]['requests']
            if [row.get('id') for row in planned] != list(IDS):
                raise ValueError(f'Frozen request membership differs: {name}/{condition}')
    return plan, labels, bind, bindings


def classify_http(raw, config, request):
    response = raw.get('result')
    if not isinstance(response, dict) or response.get('httpStatus') != 200:
        return {'status': 'service_failure', 'reason': 'http_response'}
    body = response.get('body')
    if not isinstance(body, dict) or json.loads(response.get('rawBody', 'null')) != body:
        return {'status': 'service_failure', 'reason': 'malformed_http_result'}
    if body.get('model') != config['model_identifier']:
        return {'status': 'control_failure', 'reason': 'returned_model'}
    if body.get('usage', {}).get('prompt_tokens') != request['prompt_tokens']:
        return {'status': 'control_failure', 'reason': 'prompt_token_count'}
    choices = body.get('choices')
    if (not isinstance(choices, list) or len(choices) != 1 or
            not isinstance(choices[0].get('message'), dict) or
            not isinstance(choices[0]['message'].get('content'), str)):
        return {'status': 'service_failure', 'reason': 'malformed_http_result'}
    try:
        prediction = json.loads(choices[0]['message']['content'])
    except json.JSONDecodeError:
        return {'status': 'invalid_output', 'reason': 'non_json'}
    if not valid(prediction):
        return {'status': 'invalid_output', 'reason': 'schema'}
    if choices[0].get('finish_reason') != 'stop' or choices[0]['message'].get('refusal'):
        return {'status': 'invalid_output', 'reason': 'finish_or_refusal'}
    return {'status': 'ok', 'prediction': prediction}


def normalized_fields(value):
    if not isinstance(value, dict) or not isinstance(value.get('fields'), list):
        raise ValueError('Malformed SDK control fields')
    fields = value['fields']
    if any(not isinstance(field, dict) or not isinstance(field.get('key'), str)
           or 'value' not in field for field in fields):
        raise ValueError('Malformed SDK control field')
    return {field['key']: field['value'] for field in fields}


def classify_sdk(raw, config, request):
    """Mirror the frozen local_prompt_execution_v1 classifySdk contract."""
    result = raw.get('result')
    info = result.get('modelInfo') if isinstance(result, dict) else None
    if (not isinstance(info, dict) or
            info.get('identifier') != config['model_identifier'] or
            info.get('path') != config['artifact_path'] or
            info.get('sizeBytes') != config['artifact_bytes'] or
            info.get('contextLength') != 8192 or
            not isinstance(info.get('quantization'), dict) or
            info['quantization'].get('name') != 'Q4_K_M'):
        return {'status': 'control_failure', 'reason': 'model_identity'}
    controls = config['controls']
    if normalized_fields(result.get('predictionConfig')) != normalized_fields(controls['prediction_config']):
        return {'status': 'control_failure', 'reason': 'prediction_config'}
    if normalized_fields(result.get('loadConfig')) != normalized_fields(controls['load_config']):
        return {'status': 'control_failure', 'reason': 'load_config'}
    stats = result.get('stats')
    if not isinstance(stats, dict) or stats.get('promptTokensCount') != request['prompt_tokens']:
        return {'status': 'control_failure', 'reason': 'prompt_token_count'}
    if not isinstance(result.get('content'), str) or not isinstance(result.get('nonReasoningContent'), str):
        return {'status': 'service_failure', 'reason': 'malformed_sdk_result'}
    try:
        prediction = json.loads(result['nonReasoningContent'])
    except json.JSONDecodeError:
        return {'status': 'invalid_output', 'reason': 'non_json'}
    if not valid(prediction):
        return {'status': 'invalid_output', 'reason': 'schema'}
    if stats.get('stopReason') not in ('eosFound', 'stopStringFound'):
        return {'status': 'invalid_output', 'reason': 'stop_reason'}
    return {'status': 'ok', 'prediction': prediction}


def closed_stage(root, plan, config_id, repeat, condition, name, bind, review_name=None):
    phase = f'{config_id}/{repeat}/{condition}'
    folder = BASE / phase
    files = {key: folder / f'{name}.{suffix}' for key, suffix in
             (('review', 'root-review.json'), ('claim', 'claim.json'),
              ('raw', 'raw.jsonl'), ('records', 'records.jsonl'),
              ('journal', 'journal.jsonl'), ('completion', 'completion.json'))}
    if review_name is not None:
        files['review'] = folder / review_name
    evidence = {key: {'path': str(path), 'sha256': bind(path)} for key, path in files.items()}
    review = json.loads(file_at(root, files['review']).read_text())
    claim = json.loads(file_at(root, files['claim']).read_text())
    completion = json.loads(file_at(root, files['completion']).read_text())
    route = review.get('route_catalog_file')
    evidence['routeAudit'] = {'path': route, 'sha256': bind(route, review.get('route_catalog_sha256'))}
    config = plan['configurations'][config_id]
    count = 3 if name == 'smoke' else 60
    if (review.get('kind') != 'root-reviewed-legacy-qwen-stage-v1' or
            review.get('approved') is not True or review.get('phase') != phase or
            review.get('stage') != name or review.get('plan_sha256') != MANIFEST_SHA or
            review.get('controller_sha256') != plan['controller_sha256'] or
            review.get('model_identifier') != config['model_identifier'] or
            review.get('artifact_sha256') != config['artifact_sha256'] or
            review.get('reference_labels_read') is not False or
            claim.get('phase') != phase or claim.get('stage') != name or
            claim.get('plan_sha256') != MANIFEST_SHA or
            claim.get('controller_sha256') != plan['controller_sha256'] or
            claim.get('receipt_sha256') != evidence['review']['sha256'] or
            claim.get('runtime_attestation', {}).get('artifact_sha256') != config['artifact_sha256'] or
            claim['runtime_attestation'].get('load_evidence', {}).get('cache') != plan['policy']['cache_policy'] or
            completion.get('phase') != phase or completion.get('stage') != name or
            completion.get('status') != 'completed' or completion.get('reason') is not None or
            completion.get('attempted') != count or completion.get('saved') != count or
            completion.get('raw_sha256') != evidence['raw']['sha256'] or
            completion.get('records_sha256') != evidence['records']['sha256'] or
            completion.get('journal_sha256') != evidence['journal']['sha256']):
        raise ValueError(f'Closed stage evidence differs: {phase}/{name}')
    raw = read_rows(root, files['raw'])
    records = read_rows(root, files['records'])
    journal = read_rows(root, files['journal'])
    if len(raw) != count or len(records) != count or len(journal) != 2 * count:
        raise ValueError(f'Closed stage membership differs: {phase}/{name}')
    planned = config['conditions'][condition]['requests']
    ids = IDS[:3] if name == 'smoke' else IDS
    invalid = 0
    for index, rid in enumerate(ids):
        wire, saved = raw[index], records[index]
        started, finished = journal[2 * index:2 * index + 2]
        request = planned[index]
        elapsed = wire.get('elapsed_seconds')
        if (wire.get('id') != rid or saved.get('id') != rid or
                not isinstance(wire.get('attempt_id'), str) or not wire['attempt_id'] or
                saved.get('attempt_id') != wire['attempt_id'] or
                started.get('event') != 'started' or finished.get('event') != 'finished' or
                started.get('id') != rid or finished.get('id') != rid or
                started.get('attempt_id') != wire['attempt_id'] or
                finished.get('attempt_id') != wire['attempt_id'] or
                started.get('request_sha256') != request['sha256'] or
                saved.get('request_sha256') != request['sha256'] or
                saved.get('reference_labels_read') is not False or
                type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0):
            raise ValueError(f'Raw/record/journal identity differs: {phase}/{rid}')
        decision = (classify_http(wire, config, request) if config['surface'] == 'local_http'
                    else classify_sdk(wire, config, request))
        if saved.get('decision') != decision or finished.get('status') != decision['status']:
            raise ValueError(f'Parsed decision differs from raw: {phase}/{rid}')
        if decision['status'] == 'invalid_output':
            invalid += 1
        elif decision['status'] != 'ok':
            raise ValueError(f'Closed stage has service or control failure: {phase}/{rid}')
    if completion.get('invalid') != invalid or (name == 'smoke' and invalid):
        raise ValueError(f'Invalid count differs: {phase}/{name}')
    return records, raw, evidence


def qwen35_continuation_context(root, plan, bind):
    """Verify the approved post-smoke-failure authority and its retained failure."""
    proposal_hash = bind(QWEN35_CONTINUATION_PROPOSAL, QWEN35_CONTINUATION_PROPOSAL_SHA)
    review_hash = bind(QWEN35_CONTINUATION_REVIEW, QWEN35_CONTINUATION_REVIEW_SHA)
    controller_hash = bind(QWEN35_CONTINUATION_CONTROLLER,
                           QWEN35_CONTINUATION_CONTROLLER_SHA)
    proposal = json.loads(file_at(root, QWEN35_CONTINUATION_PROPOSAL).read_text())
    design_review = json.loads(file_at(root, QWEN35_CONTINUATION_REVIEW).read_text())
    frozen = proposal.get('frozen', {})
    for name, item in frozen.items():
        items = item.values() if name == 'completed_predecessors' else (item,)
        for binding in items:
            if (not isinstance(binding, dict) or not binding.get('file') or
                    not binding.get('sha256')):
                raise ValueError('Qwen3.5 continuation frozen binding differs')
            bind(binding['file'], binding['sha256'])
    blocked = proposal.get('scope', {}).get('blocked_phase', {})
    blocked_evidence = {}
    for name, item in blocked.get('bindings', {}).items():
        if not isinstance(item, dict) or not item.get('file') or not item.get('sha256'):
            raise ValueError('Qwen3.5 blocked-smoke binding differs')
        blocked_evidence[name] = {'path': item['file'],
                                  'sha256': bind(item['file'], item['sha256'])}
    normalized = dict(proposal)
    normalized.update(status='offline_prepared_unapproved', approval=None)
    normalized_hash = hashlib.sha256(
        (json.dumps(normalized, indent=2) + '\n').encode()).hexdigest()
    config_id = 'qwen3.5-4b-sdk-thinking-on'
    config = plan['configurations'][config_id]
    phases = proposal.get('scope', {}).get('phases', [])
    expected_phases = [('fresh2', 'P1'), ('fresh2', 'P0'), ('fresh3', 'P1'),
                       ('fresh3', 'P0'), ('fresh3', 'P2')]
    phase_pairs = [(item.get('pass'), item.get('condition')) for item in phases]
    if (proposal.get('schema') != 'qwen35-after-smoke-failure-v1' or
            proposal.get('status') != 'approved' or
            (proposal.get('approval') or {}).get('authorized_by_root') is not True or
            proposal['approval'].get('independent_review') is not True or
            proposal['approval'].get('reviewer') != 'root' or
            proposal.get('inference_authorized') is not False or
            proposal.get('reference_labels_read') is not False or
            proposal.get('scope', {}).get('configuration') != config_id or
            phase_pairs != expected_phases or
            any(item.get('ids') != list(IDS) or
                item.get('request_sha256') != [row['sha256'] for row in
                    config['conditions'][item['condition']]['requests']]
                for item in phases) or
            frozen.get('plan') != {'file': str(MANIFEST), 'sha256': MANIFEST_SHA} or
            frozen.get('prior_manifest') !=
                {'file': str(QWEN35_SUCCESSOR_MANIFEST),
                 'sha256': QWEN35_SUCCESSOR_MANIFEST_SHA} or
            frozen.get('continuation_controller') !=
                {'file': str(QWEN35_CONTINUATION_CONTROLLER),
                 'sha256': QWEN35_CONTINUATION_CONTROLLER_SHA} or
            blocked.get('phase') != f'{config_id}/fresh2/P2' or
            blocked.get('status') != 'smoke_blocked' or
            blocked.get('development_admitted') is not False or
            blocked.get('replay_authorized') is not False or
            (blocked.get('attempted'), blocked.get('saved'), blocked.get('valid'),
             blocked.get('invalid')) != (3, 3, 2, 1) or
            blocked.get('invalid_reason_ids') != {'non_json': ['DEV-001']} or
            proposal.get('policy', {}).get('blocked_smoke_replay') is not False or
            proposal['policy'].get('blocked_phase_development_admission') is not False or
            proposal['policy'].get('output_repair') is not False or
            proposal['policy'].get('controls_unchanged') is not True or
            design_review.get('kind') != 'qwen35-after-smoke-failure-v1-design-root-review' or
            design_review.get('approved') is not True or
            design_review.get('authorized_by_root') is not True or
            design_review.get('independent_review') is not True or
            design_review.get('reviewer') != 'root' or
            design_review.get('proposal_sha256') != normalized_hash or
            design_review.get('controller_sha256') != controller_hash or
            design_review.get('prior_manifest_sha256') != QWEN35_SUCCESSOR_MANIFEST_SHA or
            design_review.get('blocked_completion_sha256') !=
                blocked['bindings']['completion']['sha256'] or
            design_review.get('blocked_status') != 'smoke_blocked' or
            design_review.get('blocked_smoke_replay') is not False or
            design_review.get('blocked_development_admission') is not False or
            design_review.get('phases') != [list(item) for item in expected_phases]):
        raise ValueError('Qwen3.5 continuation proposal differs')
    return {'proposal': proposal, 'proposalHash': proposal_hash,
            'controllerHash': controller_hash, 'designReviewHash': review_hash,
            'blockedEvidence': blocked_evidence, 'blocked': blocked}


def qwen35_continuation_stopped_smoke(root, plan, bind):
    """Bind the terminal host-sleep smoke without treating it as intrinsic failure."""
    context = qwen35_continuation_context(root, plan, bind)
    repeat, condition = 'fresh2', 'P1'
    config_id = 'qwen3.5-4b-sdk-thinking-on'
    phase = f'{config_id}/{repeat}/{condition}'
    folder = QWEN35_CONTINUATION / repeat / condition
    files = {key: folder / f'smoke.{suffix}' for key, suffix in
             (('review', 'root-review.json'), ('claim', 'claim.json'),
              ('raw', 'raw.jsonl'), ('records', 'records.jsonl'),
              ('journal', 'journal.jsonl'), ('completion', 'completion.json'),
              ('hostAudit', 'host-audit.json'))}
    if not all(file_at(root, path).exists() for path in files.values()):
        return None
    evidence = {key: {'path': str(path), 'sha256': bind(path)}
                for key, path in files.items()}
    review = json.loads(file_at(root, files['review']).read_text())
    claim = json.loads(file_at(root, files['claim']).read_text())
    completion = json.loads(file_at(root, files['completion']).read_text())
    audit = json.loads(file_at(root, files['hostAudit']).read_text())
    candidate_path = Path(review.get('candidate_file', ''))
    candidate_hash = bind(candidate_path, review.get('candidate_sha256'))
    candidate = json.loads(file_at(root, candidate_path).read_text())
    evidence['candidate'] = {'path': str(candidate_path), 'sha256': candidate_hash}
    normalized = dict(review)
    normalized.update(approved=False, authorized_by_root=False, reviewer=None,
                      reviewed_utc=None)
    normalized.pop('candidate_sha256', None)
    config = plan['configurations'][config_id]
    requests = config['conditions'][condition]['requests'][:3]
    if (review.get('kind') != 'qwen35-after-smoke-failure-v1-stage-root-review' or
            review.get('approved') is not True or
            review.get('authorized_by_root') is not True or
            review.get('reviewer') != 'root' or normalized != candidate or
            review.get('proposal_sha256') != context['proposalHash'] or
            review.get('controller_sha256') != context['controllerHash'] or
            review.get('prior_manifest_sha256') != QWEN35_SUCCESSOR_MANIFEST_SHA or
            review.get('blocked_completion_sha256') !=
                context['blocked']['bindings']['completion']['sha256'] or
            review.get('phase') != phase or review.get('stage') != 'smoke' or
            review.get('ids') != list(IDS[:3]) or
            review.get('request_sha256') != [item['sha256'] for item in requests] or
            review.get('reference_labels_read') is not False or
            review.get('blocked_phase_clean_credit') is not False or
            review.get('individually_clean_phase') is not True or
            claim.get('phase') != phase or claim.get('stage') != 'smoke' or
            claim.get('plan_sha256') != MANIFEST_SHA or
            claim.get('controller_sha256') != plan['controller_sha256'] or
            claim.get('receipt_sha256') != evidence['review']['sha256'] or
            completion.get('phase') != phase or completion.get('stage') != 'smoke' or
            completion.get('status') != 'stopped' or
            completion.get('reason') != 'Prediction exceeded 600000ms; cancellation requested' or
            (completion.get('attempted'), completion.get('saved'), completion.get('invalid')) !=
                (3, 2, 0) or
            completion.get('raw_sha256') != evidence['raw']['sha256'] or
            completion.get('records_sha256') != evidence['records']['sha256'] or
            completion.get('journal_sha256') != evidence['journal']['sha256'] or
            audit.get('schema') != 'qwen35-after-smoke-failure-v1-host-audit' or
            audit.get('status') != 'failed' or audit.get('phase') != phase or
            audit.get('stage') != 'smoke' or audit.get('host_check') is not None or
            'Host slept during stage' not in (audit.get('error') or '') or
            audit.get('before', {}).get('sleep_wakes') != 93 or
            audit.get('after', {}).get('sleep_wakes') != 94 or
            audit.get('completion_sha256') != evidence['completion']['sha256'] or
            audit.get('reviewed_receipt_sha256') != evidence['review']['sha256']):
        raise ValueError('Qwen3.5 continuation stopped smoke differs')
    raw, records, journal = (read_rows(root, files[name])
                             for name in ('raw', 'records', 'journal'))
    if len(raw) != 3 or len(records) != 2 or len(journal) != 6:
        raise ValueError('Qwen3.5 continuation stopped smoke membership differs')
    for index, rid in enumerate(IDS[:2]):
        request, wire, saved = requests[index], raw[index], records[index]
        started, finished = journal[2 * index:2 * index + 2]
        decision = classify_sdk(wire, config, request)
        if (wire.get('id') != rid or saved.get('id') != rid or
                saved.get('attempt_id') != wire.get('attempt_id') or
                saved.get('request_sha256') != request['sha256'] or
                saved.get('reference_labels_read') is not False or
                saved.get('decision') != decision or decision.get('status') != 'ok' or
                started.get('event') != 'started' or finished.get('event') != 'finished' or
                finished.get('status') != 'ok'):
            raise ValueError(f'Qwen3.5 continuation stopped decision differs: {rid}')
    third_started, third_finished = journal[4:6]
    if (raw[2].get('id') != 'DEV-003' or
            raw[2].get('error') != 'Prediction exceeded 600000ms; cancellation requested' or
            raw[2].get('code') != 'PREDICTION_TIMEOUT' or
            raw[2].get('cancellationAcknowledged') is not True or
            third_started.get('event') != 'started' or
            third_finished.get('event') != 'stopped_unknown' or
            third_started.get('request_sha256') != requests[2]['sha256']):
        raise ValueError('Qwen3.5 continuation unknown attempt differs: DEV-003')
    authority = {'proposal': {'path': str(QWEN35_CONTINUATION_PROPOSAL),
                              'sha256': context['proposalHash']},
                 'designReview': {'path': str(QWEN35_CONTINUATION_REVIEW),
                                  'sha256': context['designReviewHash']},
                 'controller': {'path': str(QWEN35_CONTINUATION_CONTROLLER),
                                'sha256': context['controllerHash']},
                 'blockedSmoke': context['blockedEvidence']}
    return {'pass': repeat, 'condition': condition, 'status': 'stopped_unknown',
            'stage': 'smoke', 'attempted': 3, 'saved': 2, 'valid': 2, 'invalid': 0,
            'unknownStartedIds': ['DEV-003'], 'neverSentIds': [],
            'cleanRepeatEligible': False, 'failureClass': 'host_sleep_during_timeout',
            'intrinsicModelFailure': False, 'developmentAdmitted': False,
            'source': 'qwen35_after_smoke_failure_v1',
            'sourcePath': str(folder),
            'evidence': {'authority': authority, 'smoke': evidence}}


def qwen35_successor_phase(root, plan, repeat, condition, bind, labels=None):
    """Read one independently closed Qwen3.5 successor phase, if it is terminal."""
    folder = QWEN35_SUCCESSOR / repeat / condition
    required_terminal = (folder / 'development.completion.json',
                         folder / 'development.host-audit.json')
    if not all(file_at(root, path).exists() for path in required_terminal):
        return None

    manifest_hash = bind(QWEN35_SUCCESSOR_MANIFEST, QWEN35_SUCCESSOR_MANIFEST_SHA)
    controller_hash = bind(QWEN35_SUCCESSOR_CONTROLLER, QWEN35_SUCCESSOR_CONTROLLER_SHA)
    manifest = json.loads(file_at(root, QWEN35_SUCCESSOR_MANIFEST).read_text())
    composite = manifest.get('composite', {})
    composite_hash = bind(composite.get('file', ''), composite.get('sha256'))
    frozen = manifest.get('frozen', {})
    for item in frozen.values():
        if not isinstance(item, dict) or not item.get('file') or not item.get('sha256'):
            raise ValueError('Qwen3.5 successor frozen binding differs')
        bind(item['file'], item['sha256'])
    scheduled = next((row for row in manifest.get('scope', {}).get('phases', [])
                      if row.get('pass') == repeat and row.get('condition') == condition), None)
    config_id = 'qwen3.5-4b-sdk-thinking-on'
    config = plan['configurations'][config_id]
    if (manifest.get('schema') != 'qwen35-remaining-phases-v1' or
            manifest.get('status') != 'approved' or
            (manifest.get('approval') or {}).get('authorized_by_root') is not True or
            manifest['approval'].get('independent_review') is not True or
            manifest['approval'].get('reviewer') != 'root' or
            manifest.get('method') != 'descriptive-p0-successor' or
            manifest.get('reference_labels_read') is not False or
            manifest.get('clean_repeat_eligible') is not False or
            manifest.get('scope', {}).get('configuration') != config_id or
            scheduled is None or scheduled.get('ids') != list(IDS) or
            scheduled.get('request_sha256') !=
                [row['sha256'] for row in config['conditions'][condition]['requests']] or
            frozen.get('plan') != {'file': str(MANIFEST), 'sha256': MANIFEST_SHA} or
            frozen.get('successor_controller') !=
                {'file': str(QWEN35_SUCCESSOR_CONTROLLER),
                 'sha256': QWEN35_SUCCESSOR_CONTROLLER_SHA} or
            composite_hash != composite.get('sha256') or
            composite.get('file') != str(QWEN35_COMPOSITE_REVIEW) or
            composite.get('clean_repeat_eligible') is not False or
            manifest.get('policy', {}).get('output_repair') is not False or
            manifest['policy'].get('successor_stage_replay') is not False or
            manifest['policy'].get('continuation_does_not_restore_clean_repeat_credit') is not True):
        raise ValueError('Qwen3.5 successor manifest differs')

    phase = f'{config_id}/{repeat}/{condition}'

    def validate_stage(stage):
        count = 3 if stage == 'smoke' else 60
        paths = {key: folder / f'{stage}.{suffix}' for key, suffix in
                 (('review', 'root-review.json'), ('claim', 'claim.json'),
                  ('raw', 'raw.jsonl'), ('records', 'records.jsonl'),
                  ('journal', 'journal.jsonl'), ('completion', 'completion.json'),
                  ('hostAudit', 'host-audit.json'))}
        if not all(file_at(root, path).exists() for path in paths.values()):
            return None
        evidence = {key: {'path': str(path), 'sha256': bind(path)}
                    for key, path in paths.items()}
        review = json.loads(file_at(root, paths['review']).read_text())
        claim = json.loads(file_at(root, paths['claim']).read_text())
        completion = json.loads(file_at(root, paths['completion']).read_text())
        host_audit = json.loads(file_at(root, paths['hostAudit']).read_text())
        candidate_path = Path(review.get('candidate_file', ''))
        candidate_hash = bind(candidate_path, review.get('candidate_sha256'))
        candidate = json.loads(file_at(root, candidate_path).read_text())
        evidence['candidate'] = {'path': str(candidate_path), 'sha256': candidate_hash}
        normalized = dict(review)
        for key, value in (('approved', False), ('authorized_by_root', False),
                           ('reviewer', None), ('reviewed_utc', None)):
            normalized[key] = value
        normalized.pop('candidate_sha256', None)
        expected_ids = list(IDS[:count])
        expected_requests = config['conditions'][condition]['requests'][:count]
        if (review.get('kind') != 'qwen35-remaining-phases-v1-stage-root-review' or
                review.get('approved') is not True or
                review.get('authorized_by_root') is not True or
                review.get('reviewer') != 'root' or normalized != candidate or
                review.get('manifest_sha256') != manifest_hash or
                review.get('controller_sha256') != controller_hash or
                review.get('composite_sha256') != composite_hash or
                review.get('phase') != phase or review.get('stage') != stage or
                review.get('ids') != expected_ids or
                review.get('request_sha256') != [row['sha256'] for row in expected_requests] or
                review.get('model_identifier') != config['model_identifier'] or
                review.get('artifact_sha256') != config['artifact_sha256'] or
                review.get('artifact_bytes') != config['artifact_bytes'] or
                review.get('surface') != 'lmstudio_sdk' or
                review.get('request_config_sha256') != manifest['runtime']['request_config_sha256'] or
                review.get('load_config_sha256') != manifest['runtime']['load_config_sha256'] or
                review.get('prediction_config_sha256') != manifest['runtime']['prediction_config_sha256'] or
                review.get('cache_policy') != manifest['runtime']['cache_policy'] or
                review.get('reference_labels_read') is not False or
                review.get('clean_repeat_credit') is not False or
                claim.get('phase') != phase or claim.get('stage') != stage or
                claim.get('plan_sha256') != MANIFEST_SHA or
                claim.get('controller_sha256') != frozen['legacy_controller']['sha256'] or
                claim.get('receipt_sha256') != evidence['review']['sha256'] or
                claim.get('runtime_attestation', {}).get('artifact_sha256') != config['artifact_sha256'] or
                claim['runtime_attestation'].get('load_evidence', {}).get('cache') !=
                    manifest['runtime']['cache_policy'] or
                completion.get('phase') != phase or completion.get('stage') != stage or
                completion.get('status') != 'completed' or completion.get('reason') is not None or
                completion.get('attempted') != count or completion.get('saved') != count or
                completion.get('raw_sha256') != evidence['raw']['sha256'] or
                completion.get('records_sha256') != evidence['records']['sha256'] or
                completion.get('journal_sha256') != evidence['journal']['sha256'] or
                host_audit.get('schema') != 'qwen35-remaining-phases-v1-host-audit' or
                host_audit.get('status') != 'passed' or host_audit.get('error') is not None or
                host_audit.get('phase') != phase or host_audit.get('stage') != stage or
                host_audit.get('completion_sha256') != evidence['completion']['sha256'] or
                host_audit.get('reviewed_receipt_sha256') != evidence['review']['sha256'] or
                host_audit.get('host_check', {}).get('host_unchanged') is not True):
            raise ValueError(f'Qwen3.5 successor receipt differs: {phase}/{stage}')
        raw = read_rows(root, paths['raw'])
        records = read_rows(root, paths['records'])
        journal = read_rows(root, paths['journal'])
        if len(raw) != count or len(records) != count or len(journal) != 2 * count:
            raise ValueError(f'Qwen3.5 successor membership differs: {phase}/{stage}')
        invalid = 0
        for index, (rid, request) in enumerate(zip(expected_ids, expected_requests)):
            wire, saved = raw[index], records[index]
            started, finished = journal[2 * index:2 * index + 2]
            decision = classify_sdk(wire, config, request)
            elapsed = wire.get('elapsed_seconds')
            if (wire.get('id') != rid or saved.get('id') != rid or
                    not isinstance(wire.get('attempt_id'), str) or not wire['attempt_id'] or
                    saved.get('attempt_id') != wire['attempt_id'] or
                    saved.get('request_sha256') != request['sha256'] or
                    saved.get('reference_labels_read') is not False or
                    started.get('event') != 'started' or finished.get('event') != 'finished' or
                    started.get('id') != rid or finished.get('id') != rid or
                    started.get('attempt_id') != wire['attempt_id'] or
                    finished.get('attempt_id') != wire['attempt_id'] or
                    started.get('request_sha256') != request['sha256'] or
                    finished.get('status') != decision['status'] or
                    saved.get('decision') != decision or
                    decision['status'] not in ('ok', 'invalid_output') or
                    type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0):
                raise ValueError(f'Qwen3.5 successor raw classifier differs: {phase}/{stage}/{rid}')
            invalid += decision['status'] == 'invalid_output'
        if completion.get('invalid') != invalid or (stage == 'smoke' and invalid):
            raise ValueError(f'Qwen3.5 successor invalid count differs: {phase}/{stage}')
        return records, raw, evidence, host_audit

    smoke_result = validate_stage('smoke')
    development_result = validate_stage('development')
    if smoke_result is None or development_result is None:
        return None
    smoke, _, smoke_evidence, _ = smoke_result
    development, raw, development_evidence, audit = development_result
    inspection_path = folder / 'smoke-inspection.json'
    inspection_hash = bind(inspection_path)
    inspection = json.loads(file_at(root, inspection_path).read_text())
    if (inspection.get('kind') != 'legacy-qwen-three-record-smoke-inspection-v1' or
            inspection.get('approved') is not True or inspection.get('reviewer') != 'root' or
            inspection.get('completion_sha256') != smoke_evidence['completion']['sha256'] or
            inspection.get('raw_sha256') != smoke_evidence['raw']['sha256'] or
            inspection.get('records_sha256') != smoke_evidence['records']['sha256'] or
            inspection.get('reference_labels_sent') is not False or
            inspection.get('ids') != list(IDS[:3]) or
            any(row['decision']['status'] != 'ok' for row in smoke)):
        raise ValueError(f'Qwen3.5 successor smoke inspection differs: {phase}')
    if labels is None:
        label_rows = read_rows(root, LABELS)
        labels = {row['id']: row['proposed_labels'] for row in label_rows}
    predictions = {row['id']: {'status': row['decision']['status'],
                               'prediction': row['decision'].get('prediction')}
                   for row in development}
    invalid_reason_ids = {}
    for row in development:
        decision = row['decision']
        if decision['status'] != 'ok':
            invalid_reason_ids.setdefault(decision.get('reason', 'unknown'), []).append(row['id'])
    score = shared.score(predictions, labels, IDS)
    score['invalidReasonIds'] = invalid_reason_ids
    predicted_counts, confusion = class_counts(predictions, labels)
    before, after = audit.get('before'), audit.get('after')
    before_source, after_source = host_power_source(before), host_power_source(after)
    power = {'source': before_source if before_source == after_source else None,
             'basis': ('matching_pre_post_checks' if before_source == after_source and before_source
                       else 'unverified_or_conflicting_checks')}
    successor_evidence = {
        'manifest': {'path': str(QWEN35_SUCCESSOR_MANIFEST), 'sha256': manifest_hash},
        'controller': {'path': str(QWEN35_SUCCESSOR_CONTROLLER), 'sha256': controller_hash},
        'composite': {'path': composite['file'], 'sha256': composite_hash},
    }
    entry = {'completionStatus': 'complete', 'source': 'qwen35_remaining_phases_v1',
             'sourcePath': str(folder), 'cleanRepeatCredit': True,
             'predecessorP0CleanRepeatCredit': False,
             'score': score,
             'predictedClassCounts': predicted_counts, 'classConfusion': confusion,
             'usage': usage(raw, config['surface']), 'powerObservation': power,
             'evidence': {'successor': successor_evidence,
                          'smoke': smoke_evidence,
                          'smokeInspection': {'path': str(inspection_path),
                                              'sha256': inspection_hash},
                          'development': development_evidence}}
    return {'pass': repeat, 'condition': condition,
            'source': 'qwen35_remaining_phases_v1',
            'entry': entry, 'predictions': predictions}


def qwen35_continuation_phase(root, plan, repeat, condition, bind, labels=None):
    """Read one terminal phase governed by the approved post-failure proposal."""
    folder = QWEN35_CONTINUATION / repeat / condition
    terminal = (folder / 'development.completion.json',
                folder / 'development.host-audit.json')
    if not all(file_at(root, path).exists() for path in terminal):
        return None
    context = qwen35_continuation_context(root, plan, bind)
    proposal = context['proposal']
    scheduled = next((item for item in proposal['scope']['phases']
                      if item.get('pass') == repeat and item.get('condition') == condition), None)
    if scheduled is None:
        raise ValueError('Qwen3.5 continuation phase is outside approved scope')
    config_id = 'qwen3.5-4b-sdk-thinking-on'
    config = plan['configurations'][config_id]
    phase = f'{config_id}/{repeat}/{condition}'

    def validate_stage(stage):
        count = 3 if stage == 'smoke' else 60
        paths = {key: folder / f'{stage}.{suffix}' for key, suffix in
                 (('review', 'root-review.json'), ('claim', 'claim.json'),
                  ('raw', 'raw.jsonl'), ('records', 'records.jsonl'),
                  ('journal', 'journal.jsonl'), ('completion', 'completion.json'),
                  ('hostAudit', 'host-audit.json'))}
        if not all(file_at(root, path).exists() for path in paths.values()):
            return None
        evidence = {key: {'path': str(path), 'sha256': bind(path)}
                    for key, path in paths.items()}
        review = json.loads(file_at(root, paths['review']).read_text())
        claim = json.loads(file_at(root, paths['claim']).read_text())
        completion = json.loads(file_at(root, paths['completion']).read_text())
        audit = json.loads(file_at(root, paths['hostAudit']).read_text())
        candidate_path = Path(review.get('candidate_file', ''))
        candidate_hash = bind(candidate_path, review.get('candidate_sha256'))
        candidate = json.loads(file_at(root, candidate_path).read_text())
        evidence['candidate'] = {'path': str(candidate_path), 'sha256': candidate_hash}
        normalized = dict(review)
        normalized.update(approved=False, authorized_by_root=False, reviewer=None,
                          reviewed_utc=None)
        normalized.pop('candidate_sha256', None)
        expected_ids = list(IDS[:count])
        expected_requests = config['conditions'][condition]['requests'][:count]
        if (review.get('kind') != 'qwen35-after-smoke-failure-v1-stage-root-review' or
                review.get('approved') is not True or
                review.get('authorized_by_root') is not True or
                review.get('reviewer') != 'root' or normalized != candidate or
                review.get('proposal_sha256') != context['proposalHash'] or
                review.get('controller_sha256') != context['controllerHash'] or
                review.get('prior_manifest_sha256') != QWEN35_SUCCESSOR_MANIFEST_SHA or
                review.get('blocked_completion_sha256') !=
                    context['blocked']['bindings']['completion']['sha256'] or
                review.get('phase') != phase or review.get('stage') != stage or
                review.get('ids') != expected_ids or
                review.get('request_sha256') != [row['sha256'] for row in expected_requests] or
                review.get('model_identifier') != config['model_identifier'] or
                review.get('artifact_sha256') != config['artifact_sha256'] or
                review.get('artifact_bytes') != config['artifact_bytes'] or
                review.get('surface') != 'lmstudio_sdk' or
                review.get('request_config_sha256') != proposal['runtime']['request_config_sha256'] or
                review.get('load_config_sha256') != proposal['runtime']['load_config_sha256'] or
                review.get('prediction_config_sha256') != proposal['runtime']['prediction_config_sha256'] or
                review.get('cache_policy') != proposal['runtime']['cache_policy'] or
                review.get('reference_labels_read') is not False or
                review.get('blocked_phase_clean_credit') is not False or
                review.get('individually_clean_phase') is not True or
                claim.get('phase') != phase or claim.get('stage') != stage or
                claim.get('plan_sha256') != MANIFEST_SHA or
                claim.get('controller_sha256') != plan['controller_sha256'] or
                claim.get('receipt_sha256') != evidence['review']['sha256'] or
                claim.get('runtime_attestation', {}).get('artifact_sha256') != config['artifact_sha256'] or
                claim['runtime_attestation'].get('load_evidence', {}).get('cache') !=
                    proposal['runtime']['cache_policy'] or
                completion.get('phase') != phase or completion.get('stage') != stage or
                completion.get('status') != 'completed' or completion.get('reason') is not None or
                completion.get('attempted') != count or completion.get('saved') != count or
                completion.get('raw_sha256') != evidence['raw']['sha256'] or
                completion.get('records_sha256') != evidence['records']['sha256'] or
                completion.get('journal_sha256') != evidence['journal']['sha256'] or
                audit.get('schema') != 'qwen35-after-smoke-failure-v1-host-audit' or
                audit.get('status') != 'passed' or audit.get('error') is not None or
                audit.get('phase') != phase or audit.get('stage') != stage or
                audit.get('completion_sha256') != evidence['completion']['sha256'] or
                audit.get('reviewed_receipt_sha256') != evidence['review']['sha256'] or
                audit.get('host_check', {}).get('host_unchanged') is not True):
            raise ValueError(f'Qwen3.5 continuation receipt differs: {phase}/{stage}')
        raw, records, journal = (read_rows(root, paths[name])
                                 for name in ('raw', 'records', 'journal'))
        if len(raw) != count or len(records) != count or len(journal) != 2 * count:
            raise ValueError(f'Qwen3.5 continuation membership differs: {phase}/{stage}')
        invalid = 0
        for index, (rid, request) in enumerate(zip(expected_ids, expected_requests)):
            wire, saved = raw[index], records[index]
            started, finished = journal[2 * index:2 * index + 2]
            decision = classify_sdk(wire, config, request)
            elapsed = wire.get('elapsed_seconds')
            if (wire.get('id') != rid or saved.get('id') != rid or
                    not isinstance(wire.get('attempt_id'), str) or not wire['attempt_id'] or
                    saved.get('attempt_id') != wire['attempt_id'] or
                    saved.get('request_sha256') != request['sha256'] or
                    saved.get('reference_labels_read') is not False or
                    started.get('event') != 'started' or finished.get('event') != 'finished' or
                    started.get('id') != rid or finished.get('id') != rid or
                    started.get('attempt_id') != wire['attempt_id'] or
                    finished.get('attempt_id') != wire['attempt_id'] or
                    started.get('request_sha256') != request['sha256'] or
                    finished.get('status') != decision['status'] or
                    saved.get('decision') != decision or
                    decision['status'] not in ('ok', 'invalid_output') or
                    type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0):
                raise ValueError(f'Qwen3.5 continuation classifier differs: {phase}/{stage}/{rid}')
            invalid += decision['status'] == 'invalid_output'
        if completion.get('invalid') != invalid or (stage == 'smoke' and invalid):
            raise ValueError(f'Qwen3.5 continuation invalid count differs: {phase}/{stage}')
        return records, raw, evidence, audit

    smoke_result, development_result = validate_stage('smoke'), validate_stage('development')
    if smoke_result is None or development_result is None:
        return None
    smoke, _, smoke_evidence, _ = smoke_result
    development, raw, development_evidence, audit = development_result
    inspection_path = folder / 'smoke-inspection.json'
    inspection_hash = bind(inspection_path)
    inspection = json.loads(file_at(root, inspection_path).read_text())
    if (inspection.get('kind') != 'legacy-qwen-three-record-smoke-inspection-v1' or
            inspection.get('approved') is not True or inspection.get('reviewer') != 'root' or
            inspection.get('completion_sha256') != smoke_evidence['completion']['sha256'] or
            inspection.get('raw_sha256') != smoke_evidence['raw']['sha256'] or
            inspection.get('records_sha256') != smoke_evidence['records']['sha256'] or
            inspection.get('reference_labels_sent') is not False or
            inspection.get('ids') != list(IDS[:3]) or
            any(row['decision']['status'] != 'ok' for row in smoke)):
        raise ValueError(f'Qwen3.5 continuation smoke inspection differs: {phase}')
    if labels is None:
        labels = {row['id']: row['proposed_labels'] for row in read_rows(root, LABELS)}
    predictions = {row['id']: {'status': row['decision']['status'],
                               'prediction': row['decision'].get('prediction')}
                   for row in development}
    invalid_reason_ids = {}
    for row in development:
        if row['decision']['status'] != 'ok':
            invalid_reason_ids.setdefault(row['decision'].get('reason', 'unknown'), []).append(row['id'])
    score = shared.score(predictions, labels, IDS)
    score['invalidReasonIds'] = invalid_reason_ids
    predicted_counts, confusion = class_counts(predictions, labels)
    before_source, after_source = host_power_source(audit.get('before')), host_power_source(audit.get('after'))
    power = {'source': before_source if before_source == after_source else None,
             'basis': ('matching_pre_post_checks' if before_source == after_source and before_source
                       else 'unverified_or_conflicting_checks')}
    authority = {'proposal': {'path': str(QWEN35_CONTINUATION_PROPOSAL),
                              'sha256': context['proposalHash']},
                 'designReview': {'path': str(QWEN35_CONTINUATION_REVIEW),
                                  'sha256': context['designReviewHash']},
                 'controller': {'path': str(QWEN35_CONTINUATION_CONTROLLER),
                                'sha256': context['controllerHash']},
                 'blockedSmoke': context['blockedEvidence']}
    entry = {'completionStatus': 'complete', 'source': 'qwen35_after_smoke_failure_v1',
             'sourcePath': str(folder), 'cleanRepeatCredit': True,
             'predecessorP0CleanRepeatCredit': False,
             'blockedPredecessor': {key: context['blocked'][key] for key in
                 ('phase', 'status', 'development_admitted', 'replay_authorized',
                  'attempted', 'saved', 'valid', 'invalid', 'invalid_reason_ids')},
             'score': score, 'predictedClassCounts': predicted_counts,
             'classConfusion': confusion, 'usage': usage(raw, config['surface']),
             'powerObservation': power,
             'evidence': {'successor': authority, 'smoke': smoke_evidence,
                          'smokeInspection': {'path': str(inspection_path),
                                              'sha256': inspection_hash},
                          'development': development_evidence}}
    return {'pass': repeat, 'condition': condition,
            'source': 'qwen35_after_smoke_failure_v1',
            'entry': entry, 'predictions': predictions}


def qwen35_interruption(root, plan, bind):
    """Reconcile the stopped first P0 stage without giving it a full-pass score."""
    config_id, repeat, condition = 'qwen3.5-4b-sdk-thinking-on', 'fresh1', 'P0'
    phase = f'{config_id}/{repeat}/{condition}'
    folder = BASE / phase
    files = {key: folder / name for key, name in {
        'admission': 'development.root-review.json',
        'claim': 'development.claim.json',
        'completion': 'development.completion.json',
        'raw': 'development.raw.jsonl',
        'records': 'development.records.jsonl',
        'journal': 'development.journal.jsonl',
        'hostAudit': 'interruption.host-audit.json',
        'rootReview': 'interruption.root-review.json',
    }.items()}
    evidence = {key: {'path': str(path), 'sha256': bind(path)} for key, path in files.items()}
    admission = json.loads(file_at(root, files['admission']).read_text())
    claim = json.loads(file_at(root, files['claim']).read_text())
    completion = json.loads(file_at(root, files['completion']).read_text())
    host = json.loads(file_at(root, files['hostAudit']).read_text())
    review = json.loads(file_at(root, files['rootReview']).read_text())
    config = plan['configurations'][config_id]
    never_sent = list(IDS[52:])
    if (admission.get('kind') != 'root-reviewed-legacy-qwen-stage-v1' or
            admission.get('approved') is not True or admission.get('phase') != phase or
            admission.get('stage') != 'development' or
            admission.get('reference_labels_read') is not False or
            claim.get('phase') != phase or claim.get('stage') != 'development' or
            claim.get('receipt_sha256') != evidence['admission']['sha256'] or
            claim.get('plan_sha256') != MANIFEST_SHA or
            claim.get('controller_sha256') != plan['controller_sha256'] or
            completion.get('phase') != phase or completion.get('stage') != 'development' or
            completion.get('status') != 'stopped' or
            completion.get('reason') != 'Prediction exceeded 600000ms; cancellation requested' or
            completion.get('attempted') != 52 or completion.get('saved') != 51 or
            completion.get('invalid') != 7 or
            completion.get('raw_sha256') != evidence['raw']['sha256'] or
            completion.get('records_sha256') != evidence['records']['sha256'] or
            completion.get('journal_sha256') != evidence['journal']['sha256'] or
            host.get('schema') != 'qwen35-interruption-host-audit-v1' or
            host.get('same_boot') is not True or
            host.get('sleep_count_changed') is not True or
            host.get('before', {}).get('boot') != host.get('after', {}).get('boot') or
            host.get('after', {}).get('sleep_wakes') !=
                host.get('before', {}).get('sleep_wakes', -1) + 1 or
            not any('Low Power Sleep' in event for event in host.get('stage_events', [])) or
            review.get('schema') != 'qwen35-interruption-root-review-v1' or
            review.get('terminal_exit_code') != 1 or
            review.get('completion_sha256') != evidence['completion']['sha256'] or
            review.get('host_audit_sha256') != evidence['hostAudit']['sha256'] or
            review.get('saved') != 51 or review.get('valid') != 44 or
            review.get('invalid') != 7 or
            review.get('unknown_ids') != ['DEV-052'] or
            review.get('never_sent_ids') != never_sent or
            review.get('reference_labels_read') is not False or
            review.get('clean_repeat_eligible') is not False or
            review.get('replay_authorized') is not False):
        raise ValueError('Qwen3.5 interruption receipt differs')
    raw = read_rows(root, files['raw'])
    records = read_rows(root, files['records'])
    journal = read_rows(root, files['journal'])
    if len(raw) != 52 or len(records) != 51 or len(journal) != 104:
        raise ValueError('Qwen3.5 interruption membership differs')
    requests = config['conditions'][condition]['requests']
    invalid = 0
    for index, rid in enumerate(IDS[:51]):
        wire, saved = raw[index], records[index]
        started, finished = journal[2 * index:2 * index + 2]
        request = requests[index]
        if (wire.get('id') != rid or saved.get('id') != rid or
                wire.get('attempt_id') != saved.get('attempt_id') or
                started.get('event') != 'started' or finished.get('event') != 'finished' or
                started.get('id') != rid or finished.get('id') != rid or
                started.get('attempt_id') != wire.get('attempt_id') or
                finished.get('attempt_id') != wire.get('attempt_id') or
                started.get('request_sha256') != request['sha256'] or
                saved.get('request_sha256') != request['sha256'] or
                saved.get('reference_labels_read') is not False):
            raise ValueError(f'Qwen3.5 saved identity differs: {rid}')
        decision = classify_sdk(wire, config, request)
        if saved.get('decision') != decision or finished.get('status') != decision['status']:
            raise ValueError(f'Qwen3.5 saved decision differs: {rid}')
        invalid += decision['status'] == 'invalid_output'
        if decision['status'] not in ('ok', 'invalid_output'):
            raise ValueError(f'Qwen3.5 saved outcome differs: {rid}')
    unknown_start, unknown_end = journal[102:]
    if (invalid != 7 or raw[51].get('id') != 'DEV-052' or
            unknown_start.get('event') != 'started' or
            unknown_end.get('event') != 'stopped_unknown' or
            unknown_start.get('id') != 'DEV-052' or
            unknown_end.get('id') != 'DEV-052' or
            raw[51].get('attempt_id') != unknown_start.get('attempt_id') or
            unknown_end.get('attempt_id') != unknown_start.get('attempt_id') or
            unknown_start.get('request_sha256') != requests[51]['sha256'] or
            raw[51].get('code') != 'PREDICTION_TIMEOUT'):
        raise ValueError('Qwen3.5 unknown attempt differs')
    return {'pass': repeat, 'condition': condition, 'status': 'stopped_unknown',
            'attempted': 52, 'saved': 51, 'valid': 44, 'invalid': 7,
            'unknownStartedIds': ['DEV-052'], 'neverSentIds': never_sent,
            'cleanRepeatEligible': False, 'evidence': evidence}


def qwen35_descriptive_composite(root, plan, labels, bind, partial):
    """Combine the retained prefix with a separately closed eight-record suffix."""
    phase = 'qwen3.5-4b-sdk-thinking-on/fresh1/P0'
    config = plan['configurations']['qwen3.5-4b-sdk-thinking-on']
    receipt_sha = bind(QWEN35_COMPOSITE_REVIEW)
    receipt = json.loads(file_at(root, QWEN35_COMPOSITE_REVIEW).read_text())
    bindings = receipt.get('bindings')
    if (receipt.get('schema') != 'qwen35-p0-descriptive-composite-root-review-v1' or
            receipt.get('approved') is not True or receipt.get('reviewer') != 'root' or
            receipt.get('phase') != phase or receipt.get('saved') != 59 or
            receipt.get('unknown_ids') != ['DEV-052'] or
            receipt.get('never_sent_ids') != [] or
            receipt.get('clean_repeat_eligible') is not False or
            receipt.get('reference_labels_read') is not False or
            not isinstance(bindings, dict)):
        raise ValueError('Qwen3.5 composite review differs')
    manifest_path = QWEN35_SUFFIX / 'manifest.json'
    controller_path = Path('scripts/qwen35_p0_unsent_suffix_v1.cjs')
    needed = {str(manifest_path), str(controller_path),
              *(item['path'] for item in partial['evidence'].values())}
    manifest = json.loads(file_at(root, manifest_path).read_text())
    suffix_files = manifest.get('suffix', {}).get('output_files', {})
    if set(suffix_files) != {'claim', 'journal', 'raw', 'records', 'completion'}:
        raise ValueError('Qwen3.5 suffix output plan differs')
    needed.update(suffix_files.values())
    needed.add(str(QWEN35_SUFFIX / 'suffix.root-review.json'))
    if not needed <= set(bindings):
        raise ValueError('Qwen3.5 composite source bindings incomplete')
    for name, digest in bindings.items():
        if (not isinstance(name, str) or not isinstance(digest, str) or
                not re.fullmatch('[0-9a-f]{64}', digest)):
            raise ValueError('Qwen3.5 composite source binding malformed')
        bind(name, digest)
    suffix_evidence = {key: {'path': name, 'sha256': bindings[name]}
                       for key, name in suffix_files.items()}
    review_path = QWEN35_SUFFIX / 'suffix.root-review.json'
    suffix_evidence['review'] = {'path': str(review_path), 'sha256': bindings[str(review_path)]}
    suffix_evidence['manifest'] = {'path': str(manifest_path), 'sha256': bindings[str(manifest_path)]}
    suffix_evidence['controller'] = {'path': str(controller_path), 'sha256': bindings[str(controller_path)]}
    suffix_evidence['compositeReview'] = {'path': str(QWEN35_COMPOSITE_REVIEW), 'sha256': receipt_sha}
    planned = config['conditions']['P0']['requests']
    suffix_ids = list(IDS[52:])
    if (manifest.get('schema') != 'qwen35-p0-unsent-suffix-v1' or
            manifest.get('status') != 'approved' or
            manifest.get('clean_repeat_eligible') is not False or
            manifest.get('reference_labels_read') is not False or
            manifest.get('scope') != {'configuration': 'qwen3.5-4b-sdk-thinking-on',
                                      'pass': 'fresh1', 'condition': 'P0',
                                      'stage': 'development_suffix'} or
            manifest.get('controller') != {'file': str(controller_path),
                                           'sha256': bindings[str(controller_path)]} or
            manifest['suffix'].get('ids') != suffix_ids or
            [item.get('sha256') for item in manifest['suffix'].get('requests', [])] !=
                [item['sha256'] for item in planned[52:]] or
            manifest.get('original', {}).get('unknown_ids') != ['DEV-052'] or
            manifest['original'].get('never_sent_ids') != suffix_ids):
        raise ValueError('Qwen3.5 frozen suffix manifest differs')
    for item in manifest['original']['bindings'].values():
        if bindings.get(item['file']) != item['sha256']:
            raise ValueError('Qwen3.5 original source differs from suffix plan')
    review = json.loads(file_at(root, review_path).read_text())
    claim = json.loads(file_at(root, suffix_files['claim']).read_text())
    completion = json.loads(file_at(root, suffix_files['completion']).read_text())
    if (review.get('kind') != 'qwen35-p0-unsent-suffix-v1-execution-root-review' or
            review.get('approved') is not True or review.get('phase') != phase or
            review.get('stage') != 'development_suffix' or
            review.get('ids') != suffix_ids or
            review.get('reference_labels_read') is not False or
            review.get('clean_repeat_credit') is not False or
            claim.get('schema') != 'qwen35-p0-unsent-suffix-v1-atomic-claim' or
            claim.get('phase') != phase or claim.get('stage') != 'development_suffix' or
            claim.get('ids') != suffix_ids or
            claim.get('manifest_sha256') != bindings[str(manifest_path)] or
            claim.get('controller_sha256') != bindings[str(controller_path)] or
            claim.get('receipt_sha256') != bindings[str(review_path)] or
            completion.get('schema') != 'qwen35-p0-unsent-suffix-v1-completion' or
            completion.get('phase') != phase or completion.get('stage') != 'development_suffix' or
            completion.get('status') != 'completed' or completion.get('reason') is not None or
            completion.get('attempted') != 8 or completion.get('saved') != 8 or
            completion.get('unknown_ids') != [] or
            completion.get('original_unknown_ids') != ['DEV-052'] or
            completion.get('clean_repeat_eligible') is not False or
            completion.get('host_check', {}).get('host_unchanged') is not True or
            completion.get('host_after', {}).get('boot') != claim.get('host_baseline', {}).get('boot') or
            completion.get('host_after', {}).get('sleep_wakes') !=
                claim.get('host_baseline', {}).get('sleep_wakes') or
            any(completion.get(key + '_sha256') != bindings[suffix_files[key]]
                for key in ('journal', 'raw', 'records'))):
        raise ValueError('Qwen3.5 suffix terminal differs')
    raw = read_rows(root, suffix_files['raw'])
    records = read_rows(root, suffix_files['records'])
    journal = read_rows(root, suffix_files['journal'])
    if len(raw) != 8 or len(records) != 8 or len(journal) != 16:
        raise ValueError('Qwen3.5 suffix membership differs')
    original_records = read_rows(root, partial['evidence']['records']['path'])
    original_raw = read_rows(root, partial['evidence']['raw']['path'])
    predictions = {item['id']: {'status': item['decision']['status'],
                                'prediction': item['decision'].get('prediction')}
                   for item in original_records}
    predictions['DEV-052'] = {'status': 'unknown_started', 'prediction': None}
    invalid = 0
    for index, rid in enumerate(suffix_ids):
        wire, saved = raw[index], records[index]
        started, finished = journal[index * 2:index * 2 + 2]
        request = planned[index + 52]
        if (wire.get('id') != rid or saved.get('id') != rid or
                wire.get('attempt_id') != saved.get('attempt_id') or
                started.get('event') != 'started' or finished.get('event') != 'finished' or
                started.get('id') != rid or finished.get('id') != rid or
                started.get('attempt_id') != wire.get('attempt_id') or
                finished.get('attempt_id') != wire.get('attempt_id') or
                started.get('request_sha256') != request['sha256'] or
                saved.get('request_sha256') != request['sha256'] or
                saved.get('reference_labels_read') is not False):
            raise ValueError(f'Qwen3.5 suffix identity differs: {rid}')
        decision = classify_sdk(wire, config, request)
        if saved.get('decision') != decision or finished.get('status') != decision['status']:
            raise ValueError(f'Qwen3.5 suffix decision differs: {rid}')
        if decision['status'] not in ('ok', 'invalid_output'):
            raise ValueError(f'Qwen3.5 suffix outcome differs: {rid}')
        invalid += decision['status'] == 'invalid_output'
        predictions[rid] = {'status': decision['status'],
                            'prediction': decision.get('prediction')}
    if (len(predictions) != 60 or invalid != completion.get('invalid') or
            set(predictions) != set(IDS)):
        raise ValueError('Qwen3.5 composite denominator differs')
    score = shared.score(predictions, labels, IDS)
    if (receipt.get('valid') != score['valid'] or
            receipt.get('invalid') != score['outcomes']['invalid_output'] or
            score['outcomes']['unknown_started'] != 1 or
            score['outcomes']['never_sent'] != 0):
        raise ValueError('Qwen3.5 composite score review differs')
    return {'pass': 'fresh1', 'condition': 'P0',
            'status': 'completed_interrupted_composite',
            'completionStatus': 'descriptive_interrupted',
            'cleanRepeatEligible': False, 'score': score,
            'originalInterruption': partial,
            'knownResponseUsage': usage(original_raw[:51] + raw, config['surface']),
            'evidence': suffix_evidence}


def successor_smoke(root, plan, config_id, repeat, condition, bind,
                    require_development_review=True):
    """Bind a terminal SDK smoke and its separately approved successor admission."""
    phase = f'{config_id}/{repeat}/{condition}'
    folder = BASE / phase
    smoke_completion = json.loads(file_at(root, folder / 'smoke.completion.json').read_text())
    if smoke_completion.get('status') == 'stopped':
        original = stopped_smoke(root, plan, config_id, repeat, condition, bind,
                                 require_original_inspection=False)
        original_evidence = original['evidence']
    elif smoke_completion.get('status') == 'completed':
        smoke_records, _, original_evidence = closed_stage(
            root, plan, config_id, repeat, condition, 'smoke', bind)
        original = {'status': 'smoke_complete', 'attempted': 3, 'saved': 3,
                    'valid': len(smoke_records), 'invalid': 0, 'evidence': original_evidence}
    else:
        raise ValueError(f'Unrecognized SDK smoke terminal status: {phase}')
    manifest_hash = bind(SUCCESSOR_MANIFEST, SUCCESSOR_MANIFEST_SHA)
    controller_hash = bind(SUCCESSOR_CONTROLLER, SUCCESSOR_CONTROLLER_SHA)
    manifest = json.loads(file_at(root, SUCCESSOR_MANIFEST).read_text())
    inspection_path = folder / 'smoke-format-successor-inspection.json'
    inspection_hash = bind(inspection_path)
    inspection = json.loads(file_at(root, inspection_path).read_text())
    review_path = folder / 'development.successor-root-review.json'
    review_hash = bind(review_path) if require_development_review else None
    review = (json.loads(file_at(root, review_path).read_text())
              if require_development_review else None)
    smoke_raw = read_rows(root, original_evidence['raw']['path'])
    smoke_records = read_rows(root, original_evidence['records']['path'])
    config = plan['configurations'][config_id]
    requests = config['conditions'][condition]['requests'][:3]
    expected_details = []
    for wire, saved, request in zip(smoke_raw, smoke_records, requests):
        result = wire['result']
        stats = result['stats']
        decision = classify_sdk(wire, config, request)
        expected_details.append({'id': wire['id'], 'status': decision['status'],
                                 'reason': decision.get('reason'),
                                 'prompt_tokens': stats['promptTokensCount'],
                                 'stop_reason': stats['stopReason'],
                                 'model_instance': result['modelInfo']['instanceReference']})
        if saved['decision'] != decision:
            raise ValueError(f'SDK successor raw decision differs: {phase}/{wire["id"]}')
    original_inspection = folder / 'smoke-inspection.json'
    original_inspection_sha = (bind(original_inspection) if file_at(root, original_inspection).exists()
                               else None)
    if (manifest.get('schema') != 'legacy-qwen-sdk-format-successor-v1' or
            manifest.get('status') != 'approved' or
            (manifest.get('approval') or {}).get('independent_review') is not True or
            manifest['approval'].get('authorized_by_root') is not True or
            manifest.get('frozen_plan') != {'file': str(MANIFEST), 'sha256': MANIFEST_SHA} or
            manifest.get('frozen_controller', {}).get('sha256') != plan['controller_sha256'] or
            manifest.get('frozen_classifier', {}).get('sha256') !=
                bind(manifest['frozen_classifier']['file'], manifest['frozen_classifier']['sha256']) or
            manifest.get('policy', {}).get('accepted_smoke_decisions') != ['ok', 'invalid_output'] or
            manifest['policy'].get('smoke_replay') is not False or
            manifest['policy'].get('output_repair') is not False or
            manifest['policy'].get('references_in_requests') is not False or
            inspection.get('kind') != 'legacy-qwen-sdk-format-successor-inspection-v1' or
            inspection.get('approved') is not True or
            inspection.get('independent_review') is not True or
            inspection.get('authorized_by_root') is not True or
            inspection.get('phase') != phase or inspection.get('stage') != 'smoke' or
            inspection.get('intrinsic_invalid_count') != original['invalid'] or
            inspection.get('details') != expected_details or
            inspection.get('reference_labels_read') is not False or
            inspection.get('semantic_correctness_claimed') is not False or
            inspection.get('output_repaired') is not False or
            inspection.get('smoke_replayed') is not False or
            inspection.get('control_and_transport_verified') is not True or
            any(inspection.get(key + '_sha256') != original_evidence[key]['sha256']
                for key in ('completion', 'claim', 'journal', 'raw', 'records')) or
            inspection.get('original_inspection_sha256') != original_inspection_sha or
            (require_development_review and (
                review.get('successor_manifest_sha256') != manifest_hash or
                review.get('successor_controller_sha256') != controller_hash or
                review.get('successor_admission_policy') != 'legacy-qwen-sdk-format-successor-v1' or
                review.get('smoke_inspection_sha256') != inspection_hash or
                review.get('authorized_by_root') is not True))):
        raise ValueError(f'SDK successor admission differs: {phase}')
    evidence = {'manifest': {'path': str(SUCCESSOR_MANIFEST), 'sha256': manifest_hash},
                'controller': {'path': str(SUCCESSOR_CONTROLLER), 'sha256': controller_hash},
                'inspection': {'path': str(inspection_path), 'sha256': inspection_hash}}
    if require_development_review:
        evidence['review'] = {'path': str(review_path), 'sha256': review_hash}
    return original, evidence


def successor_17off_smoke(root, plan, bind, require_development_review=True):
    """Bind the exact Qwen1.7B thinking-off fresh3/P2 successor, if approved."""
    config_id, repeat, condition = 'qwen3-1.7b-sdk-thinking-off', 'fresh3', 'P2'
    phase = f'{config_id}/{repeat}/{condition}'
    folder = BASE / phase
    original = stopped_smoke(root, plan, config_id, repeat, condition, bind,
                             require_original_inspection=False)
    original_evidence = original['evidence']
    manifest_hash = bind(SUCCESSOR17_MANIFEST)
    controller_hash = bind(SUCCESSOR17_CONTROLLER)
    manifest = json.loads(file_at(root, SUCCESSOR17_MANIFEST).read_text())
    inspection_hash = bind(SUCCESSOR17_INSPECTION)
    inspection = json.loads(file_at(root, SUCCESSOR17_INSPECTION).read_text())
    review_path = folder / 'development.successor-root-review.json'
    review_hash = bind(review_path) if require_development_review else None
    review = (json.loads(file_at(root, review_path).read_text())
              if require_development_review else None)
    candidate_path = None
    candidate_hash = None
    candidate = None
    if require_development_review:
        candidate_path = Path(review.get('successor_candidate_file', ''))
        if (candidate_path.parent != SUCCESSOR17_MANIFEST.parent or
                not re.fullmatch(r'development-receipt-candidate-\d{8}T\d{9}Z\.json',
                                 candidate_path.name)):
            raise ValueError(f'Qwen1.7B thinking-off successor candidate path differs: {phase}')
        candidate_hash = bind(candidate_path)
        candidate = json.loads(file_at(root, candidate_path).read_text())
    config = plan['configurations'][config_id]
    smoke_raw = read_rows(root, original_evidence['raw']['path'])
    expected_details = []
    for wire, request in zip(smoke_raw, config['conditions'][condition]['requests'][:3]):
        result = wire['result']
        decision = classify_sdk(wire, config, request)
        expected_details.append({'id': wire['id'], 'status': decision['status'],
                                 'reason': decision.get('reason'),
                                 'prompt_tokens': result['stats']['promptTokensCount'],
                                 'stop_reason': result['stats']['stopReason'],
                                 'model_instance': result['modelInfo']['instanceReference']})
    prediction_config = json.dumps(config['controls']['prediction_config'],
                                   separators=(',', ':'), ensure_ascii=False).encode()
    if (manifest.get('schema') != 'legacy-qwen-17off-format-successor-v1' or
            manifest.get('status') != 'approved' or
            manifest.get('approval', {}).get('independent_review') is not True or
            manifest['approval'].get('authorized_by_root') is not True or
            manifest.get('scope') != {'configuration': config_id, 'pass': repeat,
                                      'condition': condition, 'stage': 'development'} or
            manifest.get('frozen_plan') != {'file': str(MANIFEST), 'sha256': MANIFEST_SHA} or
            manifest.get('frozen_controller') != {'file': 'scripts/legacy_qwen_repeat_admission.cjs',
                                                  'sha256': plan['controller_sha256']} or
            manifest.get('frozen_classifier', {}).get('sha256') !=
                bind(manifest['frozen_classifier']['file'], manifest['frozen_classifier']['sha256']) or
            manifest.get('artifact_sha256') != config['artifact_sha256'] or
            manifest.get('prediction_config_sha256') != hashlib.sha256(prediction_config).hexdigest() or
            manifest.get('initial_smoke_bindings') !=
                {key: original_evidence[key]['sha256'] for key in
                 ('review', 'claim', 'journal', 'raw', 'records', 'completion')} or
            manifest.get('policy') != {'accepted_smoke_decisions': ['ok', 'invalid_output'],
                                       'accepted_invalid_reasons': ['non_json', 'schema'],
                                       'smoke_replay': False, 'output_repair': False,
                                       'references_in_requests': False,
                                       'native_lock': plan['policy']['lock_path']} or
            inspection.get('kind') != 'legacy-qwen-17off-format-successor-inspection-v1' or
            inspection.get('phase') != phase or inspection.get('stage') != 'smoke' or
            inspection.get('approved') is not True or
            inspection.get('independent_review') is not True or
            inspection.get('authorized_by_root') is not True or
            inspection.get('reference_labels_read') is not False or
            inspection.get('semantic_correctness_claimed') is not False or
            inspection.get('output_repaired') is not False or
            inspection.get('smoke_replayed') is not False or
            inspection.get('control_and_transport_verified') is not True or
            inspection.get('intrinsic_invalid_count') != original['invalid'] or
            inspection.get('details') != expected_details or
            any(inspection.get(key + '_sha256') != original_evidence[key]['sha256']
                for key in ('review', 'claim', 'journal', 'raw', 'records', 'completion')) or
            (require_development_review and (
                not isinstance(review.get('reviewer'), str) or not review['reviewer'] or
                review.get('approved') is not True or
                review.get('reviewed_utc') is None or
                review.get('successor_manifest_sha256') != manifest_hash or
                review.get('successor_controller_sha256') != controller_hash or
                review.get('successor_admission_policy') != 'legacy-qwen-17off-format-successor-v1' or
                review.get('smoke_inspection_sha256') != inspection_hash or
                review.get('authorized_by_root') is not True or
                {**review, 'approved': False, 'reviewer': None,
                 'reviewed_utc': None, 'authorized_by_root': False} != candidate))):
        raise ValueError(f'Qwen1.7B thinking-off successor admission differs: {phase}')
    evidence = {'manifest': {'path': str(SUCCESSOR17_MANIFEST), 'sha256': manifest_hash},
                'controller': {'path': str(SUCCESSOR17_CONTROLLER), 'sha256': controller_hash},
                'inspection': {'path': str(SUCCESSOR17_INSPECTION), 'sha256': inspection_hash}}
    if require_development_review:
        evidence['review'] = {'path': str(review_path), 'sha256': review_hash}
        evidence['candidate'] = {'path': str(candidate_path), 'sha256': candidate_hash}
    return original, evidence


def stopped_smoke(root, plan, config_id, repeat, condition, bind,
                  require_original_inspection=True):
    """Bind a terminal smoke rejection without creating a development score."""
    phase = f'{config_id}/{repeat}/{condition}'
    folder = BASE / phase
    files = {key: folder / f'smoke.{suffix}' for key, suffix in
             (('review', 'root-review.json'), ('claim', 'claim.json'),
              ('raw', 'raw.jsonl'), ('records', 'records.jsonl'),
              ('journal', 'journal.jsonl'), ('completion', 'completion.json'))}
    inspection_file = folder / 'smoke-inspection.json'
    evidence = {key: {'path': str(path), 'sha256': bind(path)} for key, path in files.items()}
    has_inspection = file_at(root, inspection_file).exists()
    if require_original_inspection and not has_inspection:
        raise ValueError(f'Original smoke inspection missing: {phase}')
    if has_inspection:
        evidence['inspection'] = {'path': str(inspection_file), 'sha256': bind(inspection_file)}
    review = json.loads(file_at(root, files['review']).read_text())
    claim = json.loads(file_at(root, files['claim']).read_text())
    terminal = json.loads(file_at(root, files['completion']).read_text())
    inspection = json.loads(file_at(root, inspection_file).read_text()) if has_inspection else None
    route = review.get('route_catalog_file')
    evidence['routeAudit'] = {'path': route, 'sha256': bind(route, review.get('route_catalog_sha256'))}
    config = plan['configurations'][config_id]
    if (review.get('kind') != 'root-reviewed-legacy-qwen-stage-v1' or
            review.get('approved') is not True or review.get('phase') != phase or
            review.get('stage') != 'smoke' or review.get('plan_sha256') != MANIFEST_SHA or
            review.get('controller_sha256') != plan['controller_sha256'] or
            review.get('model_identifier') != config['model_identifier'] or
            review.get('artifact_sha256') != config['artifact_sha256'] or
            review.get('reference_labels_read') is not False or
            claim.get('phase') != phase or claim.get('stage') != 'smoke' or
            claim.get('plan_sha256') != MANIFEST_SHA or
            claim.get('controller_sha256') != plan['controller_sha256'] or
            claim.get('receipt_sha256') != evidence['review']['sha256'] or
            claim.get('runtime_attestation', {}).get('artifact_sha256') != config['artifact_sha256'] or
            claim['runtime_attestation'].get('load_evidence', {}).get('cache') != plan['policy']['cache_policy'] or
            terminal.get('phase') != phase or terminal.get('stage') != 'smoke' or
            terminal.get('status') != 'stopped' or
            terminal.get('reason') != 'Smoke has invalid output; development admission refused' or
            terminal.get('attempted') != 3 or terminal.get('saved') != 3 or
            terminal.get('raw_sha256') != evidence['raw']['sha256'] or
            terminal.get('records_sha256') != evidence['records']['sha256'] or
            terminal.get('journal_sha256') != evidence['journal']['sha256'] or
            (inspection is not None and (
                inspection.get('kind') != 'legacy-qwen-three-record-smoke-inspection-v1' or
                inspection.get('approved') is not False or
                inspection.get('phase') != phase or inspection.get('stage') != 'smoke' or
                inspection.get('reference_labels_sent') is not False or
                inspection.get('completion_sha256') != evidence['completion']['sha256'] or
                inspection.get('claim_sha256') != evidence['claim']['sha256'] or
                inspection.get('review_sha256') != evidence['review']['sha256'] or
                inspection.get('raw_sha256') != evidence['raw']['sha256'] or
                inspection.get('records_sha256') != evidence['records']['sha256'] or
                inspection.get('journal_sha256') != evidence['journal']['sha256']))):
        raise ValueError(f'Stopped smoke evidence differs: {phase}')
    raw = read_rows(root, files['raw'])
    records = read_rows(root, files['records'])
    journal = read_rows(root, files['journal'])
    details = inspection.get('details') if inspection else [None] * 3
    if len(raw) != 3 or len(records) != 3 or len(journal) != 6 or not isinstance(details, list) or len(details) != 3:
        raise ValueError(f'Stopped smoke membership differs: {phase}')
    counts = Counter()
    planned = config['conditions'][condition]['requests']
    for index, rid in enumerate(IDS[:3]):
        wire, saved, detail = raw[index], records[index], details[index]
        started, finished = journal[2 * index:2 * index + 2]
        request = planned[index]
        elapsed = wire.get('elapsed_seconds')
        if (wire.get('id') != rid or saved.get('id') != rid or
                (detail is not None and detail.get('id') != rid) or
                not isinstance(wire.get('attempt_id'), str) or not wire['attempt_id'] or
                saved.get('attempt_id') != wire['attempt_id'] or
                started.get('event') != 'started' or finished.get('event') != 'finished' or
                started.get('id') != rid or finished.get('id') != rid or
                started.get('attempt_id') != wire['attempt_id'] or
                finished.get('attempt_id') != wire['attempt_id'] or
                started.get('request_sha256') != request['sha256'] or
                saved.get('request_sha256') != request['sha256'] or
                saved.get('reference_labels_read') is not False or
                type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0):
            raise ValueError(f'Stopped smoke identity differs: {phase}/{rid}')
        decision = (classify_http(wire, config, request) if config['surface'] == 'local_http'
                    else classify_sdk(wire, config, request))
        if (saved.get('decision') != decision or finished.get('status') != decision['status'] or
                (detail is not None and (detail.get('decision') != decision['status'] or
                                         detail.get('reason') != decision.get('reason'))) or
                decision['status'] not in ('ok', 'invalid_output')):
            raise ValueError(f'Stopped smoke decision differs: {phase}/{rid}')
        counts[decision['status']] += 1
    if terminal.get('invalid') != counts['invalid_output'] or not counts['invalid_output']:
        raise ValueError(f'Stopped smoke invalid count differs: {phase}')
    return {'pass': repeat, 'condition': condition, 'status': 'smoke_blocked',
            'stage': 'smoke', 'attempted': 3, 'saved': 3,
            'valid': counts['ok'], 'invalid': counts['invalid_output'],
            'reason': terminal['reason'], 'evidence': evidence}


def usage(raw, surface='local_http'):
    elapsed = [row['elapsed_seconds'] for row in raw]
    bodies = ([row['result']['body'] for row in raw] if surface == 'local_http'
              else [row['result']['stats'] for row in raw])
    def total(*keys):
        values = []
        for body in bodies:
            value = body['usage'] if surface == 'local_http' else body
            for key in keys:
                value = value.get(key) if isinstance(value, dict) else None
            if type(value) is not int or value < 0:
                return None
            values.append(value)
        return sum(values)
    if surface == 'local_http':
        tokens = {'input_tokens': total('prompt_tokens'),
                  'output_tokens': total('completion_tokens'),
                  'total_tokens': total('total_tokens'),
                  'reasoning_output_tokens': total('completion_tokens_details', 'reasoning_tokens')}
    else:
        tokens = {'input_tokens': total('promptTokensCount'),
                  'output_tokens': total('predictedTokensCount'),
                  'total_tokens': total('totalTokensCount'),
                  'reasoning_output_tokens': total('reasoningPredictedTokensCount')}
    return {'requestCount': len(raw), 'clientRequestSecondsTotal': sum(elapsed),
            'timeBasis': 'client_observed_wall_clock', 'inferenceSeconds': None,
            'modelLoadSeconds': None, 'actualCostUsd': None, 'tokens': tokens}


def host_power_source(host):
    if not isinstance(host, dict):
        return None
    source = host.get('power_source')
    ac_power = host.get('ac_power')
    if source in ('ac', 'battery'):
        if type(ac_power) is bool and (source == 'ac') != ac_power:
            return None
        return source
    if source is not None:
        return None
    if type(ac_power) is bool:
        return 'ac' if ac_power else 'battery'
    return None


def power_observation(root, development_evidence, bind):
    """Report power at recorded checks, without inferring uninterrupted power."""
    review_path = Path(development_evidence['review']['path'])
    review = json.loads(file_at(root, review_path).read_text())
    before = review.get('capacity_evidence')
    before_source = host_power_source(before)
    post_path = review_path.parent / 'development.post-stage-verification.json'
    if not file_at(root, post_path).exists():
        return {'source': before_source,
                'basis': 'pre_stage_only' if before_source else 'unavailable'}
    post_sha = bind(post_path)
    development_evidence['postStageVerification'] = {'path': str(post_path), 'sha256': post_sha}
    post = json.loads(file_at(root, post_path).read_text())
    if (post.get('kind') != 'root-closed-phase-verification-v1' or
            post.get('phase') != review.get('phase') or
            post.get('completion_sha256') != development_evidence['completion']['sha256']):
        raise ValueError(f'Post-stage verification differs: {post_path}')
    after = post.get('host')
    after_source = host_power_source(after)
    if (before_source and before_source == after_source and
            post.get('host_unchanged') is True and
            isinstance(before, dict) and isinstance(after, dict) and
            isinstance(before.get('boot'), str) and before['boot'] and
            type(before.get('sleep_wakes')) is int and
            before.get('boot') == after.get('boot') and
            before.get('sleep_wakes') == after.get('sleep_wakes')):
        return {'source': before_source, 'basis': 'matching_pre_post_checks'}
    return {'source': None, 'basis': 'unverified_or_conflicting_checks'}


def class_counts(predictions, labels):
    """Count valid predictions and their frozen-reference confusion by field."""
    eligible = [rid for rid in IDS if shared.outcome(predictions[rid]) == 'valid']
    predicted = {field: dict(sorted(Counter(
        predictions[rid]['prediction'][field] for rid in eligible).items()))
        for field in FIELDS}
    confusion = {field: {reference: dict(sorted(Counter(
        predictions[rid]['prediction'][field] for rid in eligible
        if labels[rid][field] == reference).items()))
        for reference in sorted({labels[rid][field] for rid in IDS})}
        for field in FIELDS}
    return predicted, confusion


def summary(passes, parsed):
    by_condition = {}
    flips = []
    across = {}
    for condition in CONDITIONS:
        complete = [repeat for repeat in PASSES if condition in passes[repeat]]
        scores = [passes[repeat][condition]['score'] for repeat in complete]
        def stats(values):
            return {'completedPasses': len(values), 'values': values,
                    'range': [min(values), max(values)] if len(values) == 3 else None}
        by_condition[condition] = {'allFour': stats([score['allFour'] for score in scores]),
                                   'fields': {field: stats([score['fields'][field] for score in scores])
                                              for field in FIELDS}}
        for i, left in enumerate(complete):
            for right in complete[i + 1:]:
                flips.append({'condition': condition, 'from': left, 'to': right,
                              **shared.flip(parsed[left, condition], parsed[right, condition], IDS)})
        if len(complete) == 3:
            eligible = [rid for rid in IDS if all(shared.outcome(parsed[repeat, condition][rid]) == 'valid'
                                                  for repeat in PASSES)]
            across[condition] = {'denominator': len(eligible),
                                 'excludedIds': [rid for rid in IDS if rid not in eligible],
                                 'fields': {field: [rid for rid in eligible if len({
                                     parsed[repeat, condition][rid]['prediction'][field]
                                     for repeat in PASSES}) > 1] for field in FIELDS},
                                 'fourFieldVector': [rid for rid in eligible if len({tuple(
                                     parsed[repeat, condition][rid]['prediction'][field]
                                     for field in FIELDS) for repeat in PASSES}) > 1]}
    return by_condition, flips, across


def build(root=ROOT):
    root = Path(root)
    plan, labels, bind, bindings = load_context(root)
    context_bindings = dict(bindings)
    series = []
    for config_id in CONFIGS:
        prior_bindings = set(bindings)
        config = plan['configurations'][config_id]
        passes = {repeat: {} for repeat in PASSES}
        parsed = {}
        missing = []
        partial = []
        descriptive = []
        successor_used = False
        for scheduled in config['schedule']:
            repeat = scheduled['name']
            for condition in scheduled['conditions']:
                if (config_id == 'qwen3.5-4b-sdk-thinking-on' and
                        (repeat, condition) != ('fresh1', 'P0')):
                    successor_phase = qwen35_successor_phase(
                        root, plan, repeat, condition, bind, labels)
                    if successor_phase is None:
                        successor_phase = qwen35_continuation_phase(
                            root, plan, repeat, condition, bind, labels)
                    if successor_phase is not None:
                        passes[repeat][condition] = successor_phase['entry']
                        parsed[repeat, condition] = successor_phase['predictions']
                        continue
                folder = BASE / config_id / repeat / condition
                completion_file = folder / 'development.completion.json'
                if not file_at(root, completion_file).exists():
                    if (config_id == 'qwen3.5-4b-sdk-thinking-on' and
                            repeat == 'fresh2' and condition == 'P2' and
                            file_at(root, QWEN35_CONTINUATION_PROPOSAL).exists()):
                        context = qwen35_continuation_context(root, plan, bind)
                        blocked = context['blocked']
                        missing.append({'pass': repeat, 'condition': condition,
                            'status': 'smoke_blocked', 'stage': 'smoke',
                            'attempted': blocked['attempted'], 'saved': blocked['saved'],
                            'valid': blocked['valid'], 'invalid': blocked['invalid'],
                            'invalidReasonIds': blocked['invalid_reason_ids'],
                            'cleanRepeatEligible': False, 'intrinsicModelFailure': True,
                            'developmentAdmitted': False,
                            'source': 'qwen35_after_smoke_failure_v1',
                            'sourcePath': str(QWEN35_SUCCESSOR / repeat / condition),
                            'evidence': {'proposal': {
                                'path': str(QWEN35_CONTINUATION_PROPOSAL),
                                'sha256': context['proposalHash']},
                                'designReview': {'path': str(QWEN35_CONTINUATION_REVIEW),
                                    'sha256': context['designReviewHash']},
                                'controller': {'path': str(QWEN35_CONTINUATION_CONTROLLER),
                                    'sha256': context['controllerHash']},
                                'smoke': context['blockedEvidence']}})
                        continue
                    if (config_id == 'qwen3.5-4b-sdk-thinking-on' and
                            repeat == 'fresh2' and condition == 'P1'):
                        stopped_continuation = qwen35_continuation_stopped_smoke(
                            root, plan, bind)
                        if stopped_continuation is not None:
                            missing.append(stopped_continuation)
                            continue
                    smoke_terminal_file = folder / 'smoke.completion.json'
                    if file_at(root, smoke_terminal_file).exists():
                        smoke_terminal = json.loads(file_at(root, smoke_terminal_file).read_text())
                        if smoke_terminal.get('status') == 'stopped':
                            if (config_id == 'qwen3-1.7b-sdk-thinking-off' and
                                    repeat == 'fresh3' and condition == 'P2'):
                                if file_at(root, SUCCESSOR17_INSPECTION).exists():
                                    stopped, successor_evidence = successor_17off_smoke(
                                        root, plan, bind, require_development_review=False)
                                    stopped['evidence']['smokeSuccessor'] = successor_evidence
                                else:
                                    stopped = stopped_smoke(root, plan, config_id, repeat,
                                                            condition, bind,
                                                            require_original_inspection=False)
                                missing.append(stopped)
                                continue
                            successor_inspection = folder / 'smoke-format-successor-inspection.json'
                            if (config_id in ('qwen3-0.6b-sdk-thinking-on',
                                              'qwen3-0.6b-sdk-thinking-off') and
                                    file_at(root, successor_inspection).exists()):
                                stopped, successor_evidence = successor_smoke(
                                    root, plan, config_id, repeat, condition, bind,
                                    require_development_review=False)
                                stopped['evidence']['smokeSuccessor'] = successor_evidence
                                missing.append(stopped)
                                continue
                            if file_at(root, folder / 'smoke-inspection.json').exists():
                                missing.append(stopped_smoke(root, plan, config_id,
                                                             repeat, condition, bind))
                                continue
                    missing.append({'pass': repeat, 'condition': condition,
                                    'status': 'not_in_closed_snapshot'})
                    continue
                completion = json.loads(file_at(root, completion_file).read_text())
                if completion.get('status') != 'completed':
                    if (config_id == 'qwen3.5-4b-sdk-thinking-on' and
                            repeat == 'fresh1' and condition == 'P0' and
                            completion.get('status') == 'stopped'):
                        interrupted = qwen35_interruption(root, plan, bind)
                        partial.append(interrupted)
                        if file_at(root, QWEN35_COMPOSITE_REVIEW).exists():
                            composite = qwen35_descriptive_composite(
                                root, plan, labels, bind, interrupted)
                            missing.append(composite)
                            descriptive.append(composite)
                        else:
                            missing.append(interrupted)
                        continue
                    missing.append({'pass': repeat, 'condition': condition,
                                    'status': 'not_in_closed_snapshot'})
                    continue
                successor17 = (config_id == 'qwen3-1.7b-sdk-thinking-off' and
                               repeat == 'fresh3' and condition == 'P2')
                successor06 = (config_id in ('qwen3-0.6b-sdk-thinking-on',
                                             'qwen3-0.6b-sdk-thinking-off') and
                               file_at(root, folder / 'development.successor-root-review.json').exists())
                successor = successor06 or successor17
                if successor17:
                    if not file_at(root, folder / 'development.successor-root-review.json').exists():
                        raise ValueError(f'Qwen1.7B thinking-off successor review missing: {config_id}/{repeat}/{condition}')
                    original_smoke, successor_evidence = successor_17off_smoke(root, plan, bind)
                    smoke_evidence = original_smoke['evidence']
                    development, raw, dev_evidence = closed_stage(
                        root, plan, config_id, repeat, condition, 'development', bind,
                        review_name='development.successor-root-review.json')
                elif successor06:
                    successor_used = True
                    original_smoke, successor_evidence = successor_smoke(
                        root, plan, config_id, repeat, condition, bind)
                    smoke_evidence = original_smoke['evidence']
                    development, raw, dev_evidence = closed_stage(
                        root, plan, config_id, repeat, condition, 'development', bind,
                        review_name='development.successor-root-review.json')
                else:
                    smoke, _, smoke_evidence = closed_stage(root, plan, config_id, repeat,
                                                             condition, 'smoke', bind)
                    development, raw, dev_evidence = closed_stage(root, plan, config_id, repeat,
                                                                   condition, 'development', bind)
                    inspection_file = folder / 'smoke-inspection.json'
                    inspection = json.loads(file_at(root, inspection_file).read_text())
                    inspection_sha = bind(inspection_file)
                    review = json.loads(file_at(root, folder / 'development.root-review.json').read_text())
                    if (inspection.get('kind') != 'legacy-qwen-three-record-smoke-inspection-v1' or
                            inspection.get('approved') is not True or
                            inspection.get('raw_sha256') != smoke_evidence['raw']['sha256'] or
                            inspection.get('records_sha256') != smoke_evidence['records']['sha256'] or
                            inspection.get('reference_labels_sent') is not False or
                            review.get('smoke_inspection_sha256') != inspection_sha or
                            any(row['decision']['status'] != 'ok' for row in smoke)):
                        raise ValueError(f'Development smoke admission differs: {config_id}/{repeat}/{condition}')
                predictions = {row['id']: {'status': row['decision']['status'],
                                           'prediction': row['decision'].get('prediction')}
                               for row in development}
                predicted_counts, confusion = class_counts(predictions, labels)
                entry = {'completionStatus': 'complete',
                         'score': shared.score(predictions, labels, IDS),
                         'predictedClassCounts': predicted_counts,
                         'classConfusion': confusion,
                         'usage': usage(raw, config['surface']),
                         'powerObservation': power_observation(root, dev_evidence, bind),
                         'evidence': ({'smoke': smoke_evidence,
                                       'smokeSuccessor': successor_evidence,
                                       'development': dev_evidence} if successor else
                                      {'smoke': smoke_evidence,
                                       'smokeInspection': {'path': str(inspection_file), 'sha256': inspection_sha},
                                       'development': dev_evidence})}
                if successor:
                    entry['originalSmoke'] = {key: original_smoke[key] for key in
                                              ('status', 'attempted', 'saved', 'valid', 'invalid')}
                passes[repeat][condition] = entry
                parsed[repeat, condition] = predictions
        by_condition, flips, across = summary(passes, parsed)
        config_bindings = dict(context_bindings)
        config_bindings.update({name: digest for name, digest in bindings.items()
                                if name not in prior_bindings})
        if successor_used:
            for name in (str(SUCCESSOR_MANIFEST), str(SUCCESSOR_CONTROLLER),
                         'scripts/local_prompt_execution_v1.cjs'):
                config_bindings[name] = bindings[name]
        series.append({'schema': 'legacy-qwen-closed-phase-findings-v1',
                       'configuration': config_id, 'displayName': DISPLAY_NAMES[config_id],
                       'method': 'fresh-matched-local-output-stability',
                       'referenceVersion': '0.2', 'referenceStatus': 'provisional_human_checked',
                       'referenceClassCounts': {field: dict(sorted(Counter(
                           labels[rid][field] for rid in IDS).items())) for field in FIELDS},
                       'denominator': 60, 'plannedConditions': 9,
                       'completedConditions': sum(len(group) for group in passes.values()),
                       'missingPasses': missing, 'partialPasses': partial, 'passes': passes,
                       'threePassSummary': by_condition, 'pairwiseFlips': flips,
                       'changesAcrossThreePasses': across,
                       'historicalStatus': 'observational_not_part_of_fresh_matched_three',
                       'sourceBindings': [{'path': name, 'sha256': digest}
                                          for name, digest in sorted(config_bindings.items())],
                       'artifactSha256': config['artifact_sha256'],
                       'executionControls': {'surface': config['surface'],
                           'modelIdentifier': config['model_identifier'],
                           'context': config['context'], 'outputReserve': config['output_reserve'],
                           'timeoutMs': config['timeout_ms'], 'sampling': config['controls'].get('sampling'),
                           'seedPolicy': plan['policy']['seed_policy'],
                           'cachePolicy': plan['policy']['cache_policy']},
                       'limitations': ['The same 60 synthetic reviews are repeated, not new independent cases.',
                           'Reference v0.2 labels were applied offline after model requests.',
                           'Client request durations include runtime and transport overhead; pure inference time is unavailable.',
                           'Local hardware and electricity cost were not measured; unknown is not zero.']})
        if descriptive:
            series[-1]['descriptiveComposites'] = descriptive
    return {'schema': 'legacy-qwen-closed-phase-report-v1', 'series': series}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=OUTPUT)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    content = json.dumps(build(), indent=2, ensure_ascii=False) + '\n'
    output = file_at(ROOT, args.output)
    if args.check:
        if not output.exists() or output.read_text() != content:
            raise ValueError(f'Stale legacy Qwen report: {output}')
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(content)
    print(f'Legacy Qwen report: {output}')


if __name__ == '__main__':
    main()
