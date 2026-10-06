#!/usr/bin/env python3
"""Verify and summarize the two stopped E4B thinking-on P2 attempts."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re

import build_small_local_repeat_findings as local

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/small-local-v1/gemma4-e4b-sdk-thinking-on')
CONTINUATION = BASE / 'interruption-continuation-v1'
MANIFEST = CONTINUATION / 'manifest.json'
MANIFEST_SHA = '92f2ea31ce7a65a9b0463ba6d69e2aa8a9f8b19eadde29ca1f9633362c21266b'
HOST_NOTE = Path('docs/HOST_INTERRUPTION_2026-10-01.md')
IDS = [f'DEV-{i:03d}' for i in range(1, 61)]
PHASE = 'gemma4-e4b-sdk-thinking-on/fresh2/P2'


def load(root, relative):
    return json.loads(local.path(root, relative).read_text())


def verify_binding(root, binding, bind):
    if not isinstance(binding, dict) or set(binding) != {'file', 'sha256'}:
        raise ValueError('Malformed continuation source binding')
    return bind(binding['file'], binding['sha256'])


def nonnegative_seconds(value):
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def stage(root, plan, manifest, folder, name, expected_ids, bind):
    files = {key: folder / f'{name}.{suffix}' for key, suffix in (
        ('review', 'root-review.json'), ('claim', 'claim.json'),
        ('raw', 'raw.jsonl'), ('records', 'records.jsonl'),
        ('journal', 'journal.jsonl'), ('completion', 'completion.json'))}
    evidence = {key: bind(file) for key, file in files.items()}
    review, claim, done = (load(root, files[key]) for key in ('review', 'claim', 'completion'))
    evidence['routeAudit'] = local.bind_route(review, bind)
    route = load(root, review['route_catalog_file'])
    if (route.get('source') != 'https://openrouter.ai/api/v1/models'
            or route.get('matches') != []
            or 'gemma-4-e4b' not in route.get('searched_name_fragments', [])):
        raise ValueError('Bound hosted-route audit differs')
    raw = local.rows(root, files['raw'])
    records = local.rows(root, files['records'])
    journal = local.rows(root, files['journal'])
    config = plan['configurations']['gemma4-e4b-sdk-thinking-on']
    requests = config['conditions']['P2']['requests']
    controller = (plan['controller_sha256'] if name == 'development'
                  else manifest['controller']['sha256'])
    receipt_kind = ('root-reviewed-small-local-stage-v1' if name == 'development'
                    else manifest['schema'] + '-root-review')
    if (review.get('kind') != receipt_kind or review.get('approved') is not True
            or review.get('phase') != PHASE or review.get('stage') != name
            or review.get('controller_sha256') != controller
            or review.get('model_identifier') != config['model_identifier']
            or review.get('artifact_sha256') != config['artifact_sha256']
            or review.get('reference_labels_read') is not False
            or review.get('exact_openrouter_route_absent') is not True
            or claim.get('phase') != PHASE or claim.get('stage') != name
            or claim.get('controller_sha256') != controller
            or claim.get('receipt_sha256') != evidence['review']['sha256']
            or claim.get('runtime_attestation', {}).get('artifact_sha256') != config['artifact_sha256']
            or claim['runtime_attestation'].get('load_evidence', {}).get('cache') != plan['policy']['cache_policy']
            or done.get('phase') != PHASE or done.get('stage') != name
            or done.get('status') != 'stopped' or done.get('invalid') != 0
            or done.get('attempted') != len(expected_ids)
            or done.get('saved') != len(expected_ids) - 1
            or done.get('raw_sha256') != evidence['raw']['sha256']
            or done.get('records_sha256') != evidence['records']['sha256']
            or done.get('journal_sha256') != evidence['journal']['sha256']):
        raise ValueError(f'Stopped stage control or closure differs: {name}')
    if name == 'development':
        if (review.get('plan_sha256') != local.MANIFEST_SHA
                or claim.get('plan_sha256') != local.MANIFEST_SHA):
            raise ValueError('Original plan receipt differs')
    else:
        if (review.get('manifest_sha256') != MANIFEST_SHA
                or claim.get('manifest_sha256') != MANIFEST_SHA
                or claim.get('schema') != manifest['schema'] + '-stage-claim'
                or claim.get('ids') != manifest['schedule'][0]['ids']
                or review.get('ids') != manifest['schedule'][0]['ids']
                or review.get('request_sha256') != manifest['schedule'][0]['request_sha256']):
            raise ValueError('Continuation receipt differs')
    if (len(raw) != len(expected_ids) or len(records) != len(expected_ids) - 1
            or len(journal) != 2 * len(expected_ids)
            or [r.get('id') for r in raw] != expected_ids
            or [r.get('id') for r in records] != expected_ids[:-1]):
        raise ValueError(f'Stopped stage row membership differs: {name}')
    attempts = set()
    saved_raw = []
    for index, rid in enumerate(expected_ids):
        source = requests[int(rid[-3:]) - 1]
        sidecar, started, ended = raw[index], journal[2 * index], journal[2 * index + 1]
        attempt = sidecar.get('attempt_id')
        if (not isinstance(attempt, str) or not attempt or attempt in attempts
                or source['id'] != rid
                or started.get('event') != 'started' or started.get('id') != rid
                or started.get('attempt_id') != attempt
                or started.get('request_sha256') != source['sha256']
                or ended.get('id') != rid or ended.get('attempt_id') != attempt
                or not nonnegative_seconds(sidecar.get('elapsed_seconds'))):
            raise ValueError(f'Attempt identity or timing differs: {rid}')
        attempts.add(attempt)
        if index == len(expected_ids) - 1:
            if (ended.get('event') != 'stopped_unknown'
                    or sidecar.get('code') != 'PREDICTION_TIMEOUT'
                    or sidecar.get('cancellationAcknowledged') is not True
                    or sidecar.get('partialResult') is None
                    or sidecar.get('result') is not None):
                raise ValueError(f'Timeout evidence differs: {rid}')
            continue
        record = records[index]
        if (record.get('id') != rid or record.get('attempt_id') != attempt
                or record.get('request_sha256') != source['sha256']
                or record.get('reference_labels_read') is not False
                or ended.get('event') != 'finished' or ended.get('status') != 'ok'
                or not isinstance(sidecar.get('result'), dict)):
            raise ValueError(f'Saved response identity differs: {rid}')
        decision = local.classify(sidecar, config, source)
        if record.get('decision') != decision or decision.get('status') != 'ok':
            raise ValueError(f'Saved response differs from raw: {rid}')
        saved_raw.append(sidecar)
    return {'evidence': evidence, 'saved': len(records), 'unknownId': expected_ids[-1],
            'savedRaw': saved_raw, 'attemptedSeconds': sum(r['elapsed_seconds'] for r in raw),
            'completedSeconds': sum(r['elapsed_seconds'] for r in saved_raw),
            'unknownSeconds': raw[-1]['elapsed_seconds']}


def build_original(root=ROOT):
    root = Path(root)
    bind, bindings = local.binder(root)
    bind(local.MANIFEST, local.MANIFEST_SHA)
    bind(MANIFEST, MANIFEST_SHA)
    host_note = bind(HOST_NOTE)
    plan, manifest = load(root, local.MANIFEST), load(root, MANIFEST)
    if (plan.get('schema') != 'small-local-repeat-admission-v1'
            or plan.get('reference_labels_used_for_requests') is not False
            or manifest.get('schema') != 'small-local-e4b-on-interruption-continuation-v1'
            or manifest.get('status') != 'offline_prepared_unapproved'
            or manifest.get('clean_matched_three_eligible') is not False
            or manifest.get('reference_labels_read') is not False
            or manifest.get('configuration_id') != 'gemma4-e4b-sdk-thinking-on'
            or manifest.get('first_failed_id') != 'DEV-039'
            or manifest.get('original_never_sent_ids') != IDS[39:]
            or manifest.get('schedule', [{}])[0].get('ids') != IDS[39:]):
        raise ValueError('Frozen E4B interruption plans differ')
    for key in ('plan', 'original_controller', 'controller'):
        verify_binding(root, manifest[key], bind)
    if (manifest['plan']['sha256'] != local.MANIFEST_SHA
            or manifest['original_controller']['sha256'] != plan['controller_sha256']):
        raise ValueError('Controller or plan binding differs')
    stopped = manifest['stopped']
    for binding in stopped['bindings'].values():
        verify_binding(root, binding, bind)
    for previous in manifest['previous']:
        for key in ('completion', 'claim', 'journal', 'raw', 'records'):
            verify_binding(root, previous[key], bind)
    config = plan['configurations']['gemma4-e4b-sdk-thinking-on']
    source = config['conditions']['P2']['source']
    bind(source['file'], source['sha256'])
    frozen_rows = local.rows(root, source['file'])
    planned = config['conditions']['P2']['requests']
    if ([r.get('id') for r in frozen_rows] != IDS
            or [r.get('id') for r in planned] != IDS
            or any(r.get('reference_labels_read') is not False
                   or hashlib.sha256(json.dumps(r['request'], separators=(',', ':'),
                                               ensure_ascii=False).encode()).hexdigest() != p['sha256']
                   for r, p in zip(frozen_rows, planned))):
        raise ValueError('Frozen feedback-only request source differs')
    if (manifest['runtime']['artifact_sha256'] != config['artifact_sha256']
            or manifest['runtime']['model_identifier'] != config['model_identifier']
            or manifest['runtime']['timeout_ms'] != config['timeout_ms']
            or manifest['runtime']['cache_policy'] != plan['policy']['cache_policy']
            or manifest['runtime']['parent_runtime'] != plan['parent_runtime']):
        raise ValueError('Continuation runtime differs from frozen plan')
    original = stage(root, plan, manifest, BASE / 'fresh2/P2', 'development', IDS[:39], bind)
    suffix = stage(root, plan, manifest, CONTINUATION / 'fresh2/P2', 'suffix', IDS[39:52], bind)
    if (stopped.get('failed_id') != original['unknownId']
            or stopped.get('saved_count') != original['saved']
            or stopped.get('attempt_ids') is None
            or len(stopped['attempt_ids']) != 39):
        raise ValueError('Frozen stopped prefix differs')
    for key in ('claim', 'journal', 'raw', 'records', 'completion', 'review'):
        if stopped['bindings'][key]['sha256'] != original['evidence'][key]['sha256']:
            raise ValueError('Original prefix binding differs')
    saved_raw = original['savedRaw'] + suffix['savedRaw']
    def token_total(key):
        values = [r['result']['stats'].get(key) for r in saved_raw]
        return sum(values) if all(type(v) is int and v >= 0 for v in values) else None
    return {'schema': 'e4b-interrupted-descriptive-findings-v1',
            'configurationId': 'gemma4-e4b-sdk-thinking-on',
            'phase': 'fresh2/P2', 'status': 'stopped_incomplete',
            'denominator': 60, 'savedValid': 50, 'invalid': 0,
            'unknownIds': [original['unknownId'], suffix['unknownId']],
            'unknownCodes': {original['unknownId']: 'PREDICTION_TIMEOUT',
                             suffix['unknownId']: 'PREDICTION_TIMEOUT'},
            'neverSentIds': IDS[52:], 'finalScore': None,
            'scoreStatus': 'unavailable_while_planned_requests_remain_unsent',
            'seriesStatus': 'descriptive_interrupted_not_clean_matched_three',
            'stages': {'original': original['evidence'], 'suffix': suffix['evidence']},
            'hostInterruption': {
                'source': host_note,
                'observation': 'both_timeout_intervals_overlap_recorded_host_sleep',
                'inferenceTimeConclusion': 'unavailable'},
            'usage': {'observedClientRequestSeconds': original['attemptedSeconds'] + suffix['attemptedSeconds'],
                      'savedResponseClientSeconds': original['completedSeconds'] + suffix['completedSeconds'],
                      'timeoutClientSeconds': {original['unknownId']: original['unknownSeconds'],
                                               suffix['unknownId']: suffix['unknownSeconds']},
                      'timeBasis': 'client_observed_wall_clock_for_attempts_only',
                      'modelLoadSeconds': None,
                      'tokens': {'input': token_total('promptTokensCount'),
                                 'output': token_total('predictedTokensCount'),
                                 'total': token_total('totalTokensCount'),
                                 'coverage': '50_saved_responses_only_timeout_usage_unknown'},
                      'actualCostUsd': None},
            'sourceBindings': bindings,
            'limitations': ['The original and suffix attempts stopped at separate timeouts.',
                            'Eight requests were never sent. No 60-record P2 score is reported.',
                            'Both timeout wall-clock intervals overlap recorded host sleep; they do not measure model computation.',
                            'Timeout token use, model-load time and local dollar cost are unavailable.']}


FINAL_SUFFIX = BASE / 'p2-unsent-suffix-v1'
FINAL_IDS = IDS[52:]


def canonical(value):
    return json.dumps(value, separators=(',', ':'), ensure_ascii=False).encode()


def digest(value):
    return hashlib.sha256(value).hexdigest()


def final_suffix(root, plan, prior, bind):
    """Verify the eight saved responses using archived files, never live runtime state."""
    names = ('manifest.json', 'suffix.root-review.json', 'suffix.claim.json',
             'suffix.journal.jsonl', 'suffix.raw.jsonl', 'suffix.records.jsonl',
             'suffix.completion.json', 'suffix.closure-review.json')
    files = {name: FINAL_SUFFIX / name for name in names}
    evidence = {name: bind(path) for name, path in files.items()}
    manifest, review, claim, done, closure = (load(root, files[name]) for name in
        ('manifest.json', 'suffix.root-review.json', 'suffix.claim.json',
         'suffix.completion.json', 'suffix.closure-review.json'))
    config = plan['configurations']['gemma4-e4b-sdk-thinking-on']
    requests = config['conditions']['P2']['requests']
    if (manifest.get('schema') != 'e4b-p2-unsent-suffix-v1' or
            manifest.get('status') != 'approved' or
            manifest.get('approval', {}).get('independent_review') is not True or
            manifest['approval'].get('authorized_by_root') is not True or
            manifest.get('method') != 'descriptive-interrupted-series-unsent-suffix' or
            manifest.get('clean_repeat_eligible') is not False or
            manifest.get('reference_labels_read') is not False or
            manifest.get('phase') != PHASE or manifest.get('stage') != 'suffix' or
            manifest.get('suffix', {}).get('ids') != FINAL_IDS or
            manifest['suffix'].get('requests') != requests[52:] or
            manifest.get('policy', {}).get('unknown_ids') != prior['unknownIds'] or
            manifest['policy'].get('never_replay_ids') != IDS[:52] or
            manifest.get('history', {}).get('saved') != 50 or
            manifest['history'].get('original_unknown_ids') != prior['unknownIds'] or
            manifest['history'].get('never_sent_ids') != FINAL_IDS or
            manifest['history'].get('clean_repeat_eligible') is not False or
            manifest.get('controller', {}).get('file') != 'scripts/e4b_p2_unsent_suffix_v1.cjs'):
        raise ValueError('Final E4B suffix manifest or predecessor differs')
    for group in (manifest['frozen'], {'controller': manifest['controller']},
                  manifest['history']['original'], manifest['history']['continuation'],
                  manifest['history']['smoke']):
        for source in group.values():
            verify_binding(root, source, bind)
    expected_frozen_paths = {
        'plan': str(local.MANIFEST),
        'original_controller': 'scripts/small_local_repeat_admission.cjs',
        'continuation_controller': 'scripts/small_local_e4b_on_interruption_continuation_v1.cjs',
        'classifier': 'scripts/local_prompt_execution_v1.cjs',
        'predictor': 'scripts/lmstudio_reasoning_benchmark.cjs',
        'host_admission': 'scripts/local_host_admission.cjs'}
    if (set(manifest['frozen']) != set(expected_frozen_paths) or
            any(manifest['frozen'][key]['file'] != filename
                for key, filename in expected_frozen_paths.items())):
        raise ValueError('Final E4B suffix frozen code paths differ')
    prior_bindings = {item['path']: item['sha256'] for item in prior['sourceBindings']}
    if (manifest['frozen']['plan']['sha256'] != local.MANIFEST_SHA or
            manifest['frozen']['original_controller']['sha256'] != plan['controller_sha256'] or
            manifest['frozen']['continuation_controller']['sha256'] !=
                prior_bindings['scripts/small_local_e4b_on_interruption_continuation_v1.cjs'] or
            manifest['runtime'].get('artifact_sha256') != config['artifact_sha256'] or
            manifest['runtime'].get('model_identifier') != config['model_identifier'] or
            manifest['runtime'].get('timeout_ms') != config['timeout_ms'] or
            manifest['runtime'].get('cache_policy') != plan['policy']['cache_policy'] or
            manifest['runtime'].get('parent_runtime') != plan['parent_runtime']):
        raise ValueError('Final E4B suffix frozen runtime differs')
    for label, group in (('original', prior['stages']['original']),
                         ('continuation', prior['stages']['suffix'])):
        for key in ('claim', 'journal', 'raw', 'records', 'completion'):
            expected = manifest['history'][label][key]
            if expected['file'] != group[key]['path'] or expected['sha256'] != group[key]['sha256']:
                raise ValueError('Final E4B suffix historical binding differs')
    if (manifest['history']['original']['review']['sha256'] !=
            prior['stages']['original']['review']['sha256'] or
            manifest['history']['continuation']['review']['sha256'] !=
            prior['stages']['suffix']['review']['sha256'] or
            manifest['history']['continuation']['manifest']['sha256'] != MANIFEST_SHA):
        raise ValueError('Final E4B suffix historical receipt differs')
    smoke_folder = BASE / 'fresh2/P2'
    if (set(manifest['history']['smoke']) !=
            {'claim', 'completion', 'inspection', 'records'} or
            any(manifest['history']['smoke'][key]['file'] !=
                str(smoke_folder / filename) for key, filename in {
                    'claim': 'smoke.claim.json',
                    'completion': 'smoke.completion.json',
                    'inspection': 'smoke-inspection.json',
                    'records': 'smoke.records.jsonl'}.items())):
        raise ValueError('Final E4B suffix smoke history differs')
    output_files = manifest['suffix'].get('output_files', {})
    for key in ('claim', 'journal', 'raw', 'records', 'completion'):
        if output_files.get(key) != str(files['suffix.' + key + ('.json' if key in ('claim','completion') else '.jsonl')]):
            raise ValueError('Final E4B suffix output path differs')
    runtime = manifest['runtime']
    first = local.rows(root, config['conditions']['P2']['source']['file'])
    if (runtime.get('artifact_path') != config['artifact_path'] or
            runtime.get('artifact_bytes') != config['artifact_bytes'] or
            runtime.get('context') != 8192 or runtime.get('output_reserve') != 4096 or
            runtime.get('request_config_sha256') != digest(canonical(first[52]['request']['config'])) or
            runtime.get('load_config_sha256') != digest(canonical(config['controls']['load_config'])) or
            runtime.get('prediction_config_sha256') != digest(canonical(config['controls']['prediction_config']))):
        raise ValueError('Final E4B suffix request controls differ')
    if (review.get('kind') != 'e4b-p2-unsent-suffix-v1-root-review' or
            review.get('approved') is not True or review.get('authorized_by_root') is not True or
            review.get('manifest_sha256') != evidence['manifest.json']['sha256'] or
            review.get('controller_sha256') != manifest['controller']['sha256'] or
            review.get('phase') != PHASE or review.get('stage') != 'suffix' or
            review.get('ids') != FINAL_IDS or
            review.get('request_sha256') != [item['sha256'] for item in requests[52:]] or
            review.get('model_identifier') != config['model_identifier'] or
            review.get('artifact_sha256') != config['artifact_sha256'] or
            review.get('reference_labels_read') is not False or
            review.get('smoke_replayed') is not False or
            review.get('exact_openrouter_route_absent') is not True):
        raise ValueError('Final E4B suffix root receipt differs')
    bound = {}
    for name in ('host_baseline', 'runtime_preflight', 'route_catalog', 'route_raw'):
        relative = review.get(name + '_file')
        if not isinstance(relative, str) or not relative.startswith(str(FINAL_SUFFIX) + '/'):
            raise ValueError('Final E4B suffix reviewed source path differs')
        bound[name] = bind(relative, review.get(name + '_sha256'))
    baseline = load(root, review['host_baseline_file'])
    preflight = load(root, review['runtime_preflight_file'])
    route = load(root, review['route_catalog_file'])
    route_raw = local.path(root, review['route_raw_file']).read_bytes()
    catalog = json.loads(route_raw)
    models = catalog.get('data')
    hosted_e4b = [] if not isinstance(models, list) else [item for item in models
        if isinstance(item, dict) and any(isinstance(item.get(key), str) and
            re.search(r'gemma[\W_]*4[\W_]*e4b', item[key], re.I)
            for key in ('id', 'name', 'canonical_slug', 'hugging_face_id'))]
    if (baseline != review.get('host_baseline') or
            preflight.get('artifact_sha256') != config['artifact_sha256'] or
            preflight.get('instance_reference') != review.get('instance_reference') or
            preflight.get('request_count') != 60 or
            [row.get('id') for row in preflight.get('measurements', [])] != IDS or
            any(row.get('request_sha256') != requests[i]['sha256'] or
                    row.get('prompt_tokens') != requests[i]['prompt_tokens'] or
                    row.get('context') != 8192 or row.get('output_reserve') != 4096
                    for i, row in enumerate(preflight['measurements'])) or
            review.get('runtime_token_preflight') != {
                'request_count': 60,
                'requests_sha256': digest(canonical(requests)),
                'observed_sha256': digest(canonical(preflight['measurements'])),
                'context': 8192, 'output_reserve': 4096} or
            route.get('source') != 'https://openrouter.ai/api/v1/models' or
            route.get('http_status') != 200 or route.get('model_count', 0) < 100 or
            not isinstance(models, list) or route['model_count'] != len(models) or
            hosted_e4b or
            route.get('matches') != [] or route.get('raw_sha256') != digest(route_raw) or
            review.get('route_checked_utc') != route.get('retrieved_utc')):
        raise ValueError('Final E4B suffix host, route or runtime preflight differs')
    if (claim.get('schema') != 'e4b-p2-unsent-suffix-v1-claim' or
            claim.get('phase') != PHASE or claim.get('stage') != 'suffix' or
            claim.get('ids') != FINAL_IDS or
            claim.get('manifest_sha256') != evidence['manifest.json']['sha256'] or
            claim.get('controller_sha256') != manifest['controller']['sha256'] or
            claim.get('review_sha256') != evidence['suffix.root-review.json']['sha256'] or
            claim.get('runtime_attestation', {}).get('artifact_sha256') != config['artifact_sha256'] or
            claim.get('host_baseline') != baseline or
            claim.get('route_audit', {}).get('source') != route['source'] or
            claim['route_audit'].get('http_status') != 200 or
            claim.get('route_audit', {}).get('raw_sha256') != route['raw_sha256'] or
            claim['route_audit'].get('matches') != []):
        raise ValueError('Final E4B suffix claim differs')
    raw = local.rows(root, files['suffix.raw.jsonl'])
    records = local.rows(root, files['suffix.records.jsonl'])
    journal = local.rows(root, files['suffix.journal.jsonl'])
    if ([row.get('id') for row in raw] != FINAL_IDS or
            [row.get('id') for row in records] != FINAL_IDS or
            len(journal) != 16):
        raise ValueError('Final E4B suffix saved row membership differs')
    predictions = {}
    attempts = set()
    for i, rid in enumerate(FINAL_IDS):
        sidecar, record = raw[i], records[i]
        started, ended = journal[2*i:2*i+2]
        attempt = sidecar.get('attempt_id')
        request = requests[52+i]
        if (not isinstance(attempt, str) or not attempt or attempt in attempts or
                started.get('event') != 'started' or ended.get('event') != 'finished' or
                ended.get('status') != 'ok' or
                any(row.get('id') != rid or row.get('attempt_id') != attempt
                    for row in (started, ended, record)) or
                started.get('request_sha256') != request['sha256'] or
                record.get('request_sha256') != request['sha256'] or
                record.get('reference_labels_read') is not False or
                not nonnegative_seconds(sidecar.get('elapsed_seconds')) or
                not isinstance(sidecar.get('result'), dict)):
            raise ValueError(f'Final E4B suffix attempt differs: {rid}')
        attempts.add(attempt)
        decision = local.classify(sidecar, config, request)
        if decision.get('status') != 'ok' or record.get('decision') != decision:
            raise ValueError(f'Final E4B suffix raw classification differs: {rid}')
        predictions[rid] = decision['prediction']
    if (done.get('schema') != 'e4b-p2-unsent-suffix-v1-completion' or
            done.get('phase') != PHASE or done.get('stage') != 'suffix' or
            done.get('status') != 'completed' or done.get('attempted') != 8 or
            done.get('saved') != 8 or done.get('invalid') != 0 or
            done.get('unknown_ids') != [] or
            done.get('original_unknown_ids') != prior['unknownIds'] or
            done.get('clean_repeat_eligible') is not False or
            done.get('host_check', {}).get('host_unchanged') is not True or
            done.get('host_after', {}).get('boot') != baseline.get('boot') or
            done['host_after'].get('sleep_wakes') != baseline.get('sleep_wakes') or
            done['host_after'].get('lid_open') is not True or
            done['host_after'].get('power_source') != baseline.get('power_source') or
            done.get('raw_sha256') != evidence['suffix.raw.jsonl']['sha256'] or
            done.get('records_sha256') != evidence['suffix.records.jsonl']['sha256'] or
            done.get('journal_sha256') != evidence['suffix.journal.jsonl']['sha256'] or
            closure != {'schema': 'root-e4b-unsent-suffix-closure-review-v1',
                'verified': True, 'saved': 8, 'valid': 8, 'all_four_matches': 7,
                'denominator': 8, 'original_unknown_ids': prior['unknownIds'],
                'clean_repeat_credit': False,
                'request_and_raw_bindings_checked': True,
                'host_unchanged': True, 'power_source': 'battery',
                'completion_sha256': evidence['suffix.completion.json']['sha256']}):
        raise ValueError('Final E4B suffix terminal or root closure differs')
    def tokens(key):
        values = [row['result']['stats'].get(key) for row in raw]
        return sum(values) if all(type(v) is int and v >= 0 for v in values) else None
    return {'evidence': {**evidence, **bound}, 'predictions': predictions,
            'attemptedSeconds': sum(row['elapsed_seconds'] for row in raw),
            'tokens': {key: tokens(key) for key in
                ('promptTokensCount', 'predictedTokensCount', 'totalTokensCount')}}


def build(root=ROOT):
    root = Path(root)
    prior = build_original(root)
    bind, bindings = local.binder(root)
    for item in prior['sourceBindings']:
        bind(item['path'], item['sha256'])
    bind(local.LABELS, local.LABELS_SHA)
    labels = local.rows(root, local.LABELS)
    if ([row.get('id') for row in labels] != IDS or
            any(row.get('review_version') != '0.2' or
                not local.valid(row.get('proposed_labels')) for row in labels)):
        raise ValueError('Frozen E4B references differ')
    truth = {row['id']: row['proposed_labels'] for row in labels}
    plan = load(root, local.MANIFEST)
    suffix = final_suffix(root, plan, prior, bind)
    config = plan['configurations']['gemma4-e4b-sdk-thinking-on']
    requests = config['conditions']['P2']['requests']
    raw = (local.rows(root, BASE / 'fresh2/P2/development.raw.jsonl')[:-1] +
           local.rows(root, CONTINUATION / 'fresh2/P2/suffix.raw.jsonl')[:-1])
    predictions = {}
    for sidecar in raw:
        rid = sidecar['id']
        decision = local.classify(sidecar, config, requests[int(rid[-3:])-1])
        if decision.get('status') != 'ok' or rid in predictions:
            raise ValueError('Historical E4B valid response changed')
        predictions[rid] = decision['prediction']
    if (set(predictions) != set(IDS[:38] + IDS[39:51]) or
            set(predictions) & set(suffix['predictions'])):
        raise ValueError('E4B composite membership differs')
    predictions.update(suffix['predictions'])
    valid_ids = [rid for rid in IDS if rid in predictions]
    score = {'denominator': 60, 'valid': len(valid_ids),
             'allFour': sum(predictions[rid] == truth[rid] for rid in valid_ids),
             'fields': {key: sum(predictions[rid][key] == truth[rid][key]
                                 for rid in valid_ids) for key in local.FIELDS}}
    suffix_score = sum(suffix['predictions'][rid] == truth[rid] for rid in FINAL_IDS)
    if len(valid_ids) != 58 or suffix_score != 7 or set(IDS)-set(valid_ids) != set(prior['unknownIds']):
        raise ValueError('E4B descriptive score or unknown membership differs')
    def total_tokens(key, old):
        new = suffix['tokens'][key]
        return old + new if old is not None and new is not None else None
    old = prior['usage']['tokens']
    usage = {**prior['usage'],
        'observedClientRequestSeconds': prior['usage']['observedClientRequestSeconds'] + suffix['attemptedSeconds'],
        'savedResponseClientSeconds': prior['usage']['savedResponseClientSeconds'] + suffix['attemptedSeconds'],
        'tokens': {'input': total_tokens('promptTokensCount', old['input']),
                   'output': total_tokens('predictedTokensCount', old['output']),
                   'total': total_tokens('totalTokensCount', old['total']),
                   'coverage': '58_saved_responses_only_two_timeout_usages_unknown'}}
    return {**prior, 'schema': 'e4b-interrupted-descriptive-findings-v2',
        'status': 'completed_interrupted_composite', 'savedValid': 58,
        'neverSentIds': [], 'scoreStatus': 'descriptive_interrupted_composite',
        'descriptiveScore': score, 'finalScore': None,
        'finalSuffix': {'status': 'completed', 'attempted': 8, 'savedValid': 8,
                        'allFour': suffix_score, 'denominator': 8,
                        'unknownIds': [], 'cleanRepeatCredit': False},
        'stages': {**prior['stages'], 'finalSuffix': suffix['evidence']},
        'usage': usage, 'sourceBindings': bindings, 'originalCutoff': prior,
        'limitations': ['Two earlier attempted requests retain unknown outcomes; no clean fresh2/P2 repeat credit.',
                        'The 60-record score is descriptive and includes only 58 valid predictions.',
                        'Timeout token use, model-load time, and local dollar cost remain unavailable.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    content = json.dumps(build(), indent=2, ensure_ascii=False) + '\n'
    if args.check:
        if not args.output.exists() or args.output.read_text() != content:
            raise ValueError(f'Stale E4B interruption report: {args.output}')
    else:
        args.output.write_text(content)
    print('E4B interruption report checked')


if __name__ == '__main__':
    main()
