#!/usr/bin/env python3
"""Verify and summarize the two stopped E4B thinking-on P2 attempts."""
import argparse
import hashlib
import json
import math
from pathlib import Path

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


def build(root=ROOT):
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
