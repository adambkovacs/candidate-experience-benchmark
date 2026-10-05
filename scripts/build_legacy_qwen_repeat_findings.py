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
        successor_used = False
        for scheduled in config['schedule']:
            repeat = scheduled['name']
            for condition in scheduled['conditions']:
                folder = BASE / config_id / repeat / condition
                completion_file = folder / 'development.completion.json'
                if not file_at(root, completion_file).exists():
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
                       'missingPasses': missing, 'partialPasses': [], 'passes': passes,
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
