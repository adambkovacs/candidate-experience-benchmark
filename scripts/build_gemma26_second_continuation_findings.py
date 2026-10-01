#!/usr/bin/env python3
"""Report the separately admitted Gemma26 continuation from saved evidence only.

The public report contains structured judgments and numeric usage, never raw
provider bodies, account identifiers, quota headers, or a moving budget ledger.
Closed stages need a controller-verified public summary and manual privacy review.
"""
import argparse
import base64
from decimal import Decimal, InvalidOperation
import json
import math
import os
from pathlib import Path

from development_benchmark import valid
import build_gemma26_continuation_findings as first_report
import gemma26_v2_second_continuation as controller

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/gemma26-on-fresh-matched3-v2')
SECOND = BASE / 'second-interruption-continuation-v1'
FIRST = BASE / 'interruption-continuation-v1'
SCHEMA = 'gemma26-on-v2-second-interruption-findings-v1'
CONTROLLER_SCHEMA = 'gemma26-on-v2-second-interruption-continuation-v1'
IDS = first_report.IDS
STAGES = [('fresh2', 'P0', 'suffix'),
          ('fresh3', 'P2', 'smoke'), ('fresh3', 'P2', 'development'),
          ('fresh3', 'P0', 'smoke'), ('fresh3', 'P0', 'development'),
          ('fresh3', 'P1', 'smoke'), ('fresh3', 'P1', 'development')]
PUBLIC_KEYS = {'id', 'requestSha256', 'prediction', 'status', 'observedCostUsd',
               'clientSeconds', 'tokens'}
TOKEN_KEYS = ('prompt_tokens', 'completion_tokens', 'total_tokens',
              'reasoning_tokens')


def bind(root, relative, bindings, expected=None, public=True):
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts:
        raise ValueError('Unsafe evidence path')
    file = (root / relative).resolve()
    file.relative_to(root.resolve())
    if not file.is_file():
        raise ValueError('Missing evidence: ' + str(relative))
    actual = first_report.digest(file)
    if expected is not None and actual != expected:
        raise ValueError('Evidence hash differs: ' + str(relative))
    item = {'path': relative.as_posix(), 'sha256': actual}
    if public and item not in bindings:
        bindings.append(item)
    return file


def stage_base(fresh, condition, phase):
    return SECOND / fresh / condition / phase


def files_for(root, fresh, condition, phase, bindings, public_summary=None):
    stem = stage_base(fresh, condition, phase)
    files = {}
    for kind, extension in (('claim', 'claim.json'), ('review', 'root-review.json'),
                            ('journal', 'journal.jsonl'), ('attempts', 'attempts.jsonl'),
                            ('responses', 'responses.jsonl'), ('wire', 'wire.jsonl')):
        relative = (stem.parent / (phase + '.' + extension))
        if public_summary is not None and kind in ('attempts', 'responses', 'wire') \
                and not (root / relative).is_file():
            files[kind] = None
        else:
            files[kind] = bind(root, relative, bindings,
                               public=kind in ('claim', 'review', 'journal'))
    if public_summary is not None:
        files['summary'] = bind(root, stem.parent / (phase + '.public-summary.json'),
                                bindings)
        files['public_review'] = bind(root, stem.parent / (phase + '.public-review.json'),
                                      bindings)
    return files


def selected_plan(root, manifest, fresh, condition, phase, bindings):
    source = manifest['source_bindings']['original_plan_' + fresh]
    plan_file = bind(root, source['path'], bindings, source['sha256'])
    plan = json.loads(plan_file.read_text())
    requests = plan['conditions'][condition]['development' if phase == 'suffix' else phase]
    return requests[2:] if phase == 'suffix' else requests


def public_row(record):
    """Allowlist only structured judgments and numeric request metadata."""
    if record.get('status') != 'ok' or not valid(record.get('prediction')):
        raise ValueError('Public stage includes a non-scorable response')
    try:
        price = Decimal(str(record.get('observed_cost_usd')))
    except (InvalidOperation, TypeError):
        raise ValueError('Public stage cost is unknown or invalid') from None
    if not price.is_finite() or price < 0 or record.get('cost_unknown') is not False:
        raise ValueError('Public stage cost is unknown or invalid')
    duration = record.get('elapsed_seconds')
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration < 0:
        raise ValueError('Client duration is invalid')
    usage = record.get('usage') or {}
    details = usage.get('completion_tokens_details') or {}
    tokens = {key: (details.get('reasoning_tokens') if key == 'reasoning_tokens'
                    else usage.get(key)) for key in TOKEN_KEYS}
    if any(value is not None and (type(value) is not int or value < 0)
           for value in tokens.values()):
        raise ValueError('Provider token count is invalid')
    return {'id': record['id'], 'requestSha256': record['request_sha256'],
            'prediction': record['prediction'], 'status': 'ok',
            'observedCostUsd': str(price), 'clientSeconds': duration,
            'tokens': tokens}


def public_usage(rows):
    tokens = {}
    for key in TOKEN_KEYS:
        values = [r['tokens'][key] for r in rows]
        present = [value for value in values if value is not None]
        tokens[key] = {'sum': sum(present) if len(present) == len(values) else None,
                       'reportedCount': len(present),
                       'missingCount': len(values) - len(present)}
    return {'requestCount': len(rows),
            'knownCostUsd': str(sum((Decimal(r['observedCostUsd']) for r in rows),
                                    Decimal(0))),
            'clientSecondsTotal': sum(r['clientSeconds'] for r in rows),
            'timingKind': 'client_request_to_record_not_provider_inference',
            'tokenAvailability': tokens}


def validate_public_row(row, request, reserve):
    if (not isinstance(row, dict) or set(row) != PUBLIC_KEYS or
            row.get('id') != request['record_id'] or
            row.get('requestSha256') != request['request_sha256'] or
            row.get('status') != 'ok' or not valid(row.get('prediction')) or
            not isinstance(row.get('tokens'), dict) or
            set(row['tokens']) != set(TOKEN_KEYS)):
        raise ValueError('Public stage response differs from frozen request')
    try:
        cost = Decimal(str(row.get('observedCostUsd')))
    except (InvalidOperation, TypeError):
        raise ValueError('Public stage cost is invalid') from None
    duration = row.get('clientSeconds')
    if (not cost.is_finite() or not Decimal(0) <= cost <= reserve or
            type(duration) not in (int, float) or not math.isfinite(duration) or
            duration < 0 or
            any(value is not None and (type(value) is not int or value < 0)
                for value in row['tokens'].values())):
        raise ValueError('Public stage cost, timing or tokens differ')


def verify_public_stage(root, manifest, manifest_sha, spec, bindings):
    fresh, condition, phase = (spec[k] for k in ('fresh_pass', 'condition', 'stage'))
    files = files_for(root, fresh, condition, phase, bindings, public_summary=True)
    summary = json.loads(files['summary'].read_text())
    public_review = json.loads(files['public_review'].read_text())
    source_sha = summary.get('privateSourceSha256')
    if (set(summary) != {'schema', 'stage', 'manifestSha256',
                        'manualPrivacyReviewRequired', 'privateSourceSha256',
                        'responses'} or
            summary.get('schema') != SCHEMA + '-public-stage-v1' or
            summary.get('stage') != f'{fresh}/{condition}/{phase}' or
            summary.get('manifestSha256') != manifest_sha or
            summary.get('manualPrivacyReviewRequired') is not True or
            not isinstance(source_sha, dict) or
            set(source_sha) != {'claim', 'review', 'journal', 'attempts', 'responses', 'wire'} or
            any(not isinstance(value, str) or len(value) != 64 or
                any(char not in '0123456789abcdef' for char in value)
                for value in source_sha.values()) or
            any(source_sha[k] != first_report.digest(files[k])
                for k in ('claim', 'review', 'journal')) or
            public_review != {'schema': SCHEMA + '-public-review-v1',
                              'approved': True,
                              'summarySha256': first_report.digest(files['summary']),
                              'stage': f'{fresh}/{condition}/{phase}'}):
        raise ValueError('Public stage attestation differs from closed evidence')
    review, claim = (json.loads(files[k].read_text()) for k in ('review', 'claim'))
    if (review.get('approved') is not True or
            review.get('schema') != CONTROLLER_SCHEMA + '-stage-review' or
            review.get('manifest_sha256') != manifest_sha or
            review.get('stage') != f'{fresh}/{condition}/{phase}' or
            review.get('ids') != spec['ids'] or
            review.get('request_sha256') != spec['request_sha256'] or
            claim.get('series_id') != CONTROLLER_SCHEMA or
            claim.get('fresh_pass') != fresh or
            claim.get('condition') != condition or
            claim.get('phase') != phase or
            claim.get('manifest_sha256') != manifest_sha or
            claim.get('root_review_sha256') != first_report.digest(files['review'])):
        raise ValueError('Closed stage review or claim differs')
    selected = selected_plan(root, manifest, fresh, condition, phase, bindings)
    expected_ids = spec['ids']
    projected = summary.get('responses')
    journal = first_report.rows(files['journal'])
    if (not isinstance(projected, list) or len(projected) != len(expected_ids) or
            [r['record_id'] for r in selected] != expected_ids or
            [r['request_sha256'] for r in selected] != spec['request_sha256'] or
            len(journal) != 2 + 3 * len(expected_ids) or
            journal[0].get('event') != 'phase_started' or
            (journal[0].get('fresh_pass'), journal[0].get('condition'),
             journal[0].get('phase')) != (fresh, condition, phase) or
            journal[-1].get('event') != 'phase_completed' or
            (journal[-1].get('fresh_pass'), journal[-1].get('condition'),
             journal[-1].get('phase')) != (fresh, condition, phase) or
            journal[-1].get('request_count') != len(expected_ids)):
        raise ValueError('Public stage does not cover the frozen closed plan')
    attempt_ids = []
    for i, (request, row) in enumerate(zip(selected, projected)):
        validate_public_row(row, request, Decimal(manifest['reserve_usd']))
        intent, started, finished = journal[1 + 3*i:4 + 3*i]
        rid = request['record_id']
        attempt_id = started.get('attempt_id')
        if (not isinstance(attempt_id, str) or not attempt_id or
                [(e.get('event'), e.get('id'), e.get('request_sha256'))
                 for e in (intent, started, finished)] != [
                    ('request_intent', rid, request['request_sha256']),
                    ('request_started', rid, request['request_sha256']),
                    ('request_finished', rid, None)] or
                intent.get('attempt_id') is not None or
                finished.get('attempt_id') != attempt_id or
                finished.get('status') != 'ok' or
                finished.get('billing_ok') is not True or
                finished.get('cost_unknown') is not False or
                Decimal(str(finished.get('observed_cost_usd'))) !=
                    Decimal(row['observedCostUsd'])):
            raise ValueError('Public stage journal differs at ' + rid)
        attempt_ids.append(attempt_id)
    if (len(set(attempt_ids)) != len(expected_ids) or
            journal[-1].get('attempt_ids') != attempt_ids):
        raise ValueError('Public stage attempt membership differs')
    private = [files[k] for k in ('attempts', 'responses', 'wire')]
    if not any(private):
        # Export was controller-verified before the manual summary review. A
        # public archive can verify that attestation, but cannot reparse bytes
        # it does not contain.
        return projected
    if not all(private):
        raise ValueError('Partial private stage evidence in archive')
    if any(source_sha[k] != first_report.digest(files[k])
           for k in ('attempts', 'responses', 'wire')):
        raise ValueError('Public stage private evidence hash differs')
    attempts, responses, wire, journal = (first_report.rows(files[k]) for k in
                                          ('attempts', 'responses', 'wire', 'journal'))
    if ([r['record_id'] for r in selected] != expected_ids or
            [r['request_sha256'] for r in selected] != spec['request_sha256'] or
            [r.get('id') for r in attempts] != expected_ids or
            [r.get('id') for r in responses] != expected_ids or
            [r.get('id') for r in wire] != expected_ids or
            len({r.get('attempt_id') for r in attempts}) != len(expected_ids) or
            len(journal) != 2 + 3 * len(expected_ids) or
            journal[0].get('event') != 'phase_started' or
            journal[-1].get('event') != 'phase_completed' or
            journal[-1].get('request_count') != len(expected_ids) or
            journal[-1].get('attempt_ids') != [r.get('attempt_id') for r in attempts]):
        raise ValueError('Stage is not exactly closed in frozen order')
    for i, (request, attempt, response, captured) in enumerate(
            zip(selected, attempts, responses, wire)):
        rid, attempt_id = request['record_id'], attempt.get('attempt_id')
        events = journal[1 + 3*i:4 + 3*i]
        if (attempt.get('request') != request['payload'] or
                attempt.get('request_sha256') != request['request_sha256'] or
                attempt.get('manifest_sha256') != manifest_sha or
                attempt.get('reference_labels_read') is not False or
                not isinstance(attempt_id, str) or not attempt_id or
                response.get('id') != rid or
                response.get('attempt_id') != attempt_id or
                response.get('request_sha256') != request['request_sha256'] or
                response.get('raw_response') != attempt.get('raw_response') or
                captured.get('id') != rid or
                captured.get('attempt_id') != attempt_id or
                captured.get('request_sha256') != request['request_sha256'] or
                captured.get('http_status') != 200 or
                captured.get('body_truncated_at_limit') is not False or
                captured.get('read_error') is not None or
                json.loads(base64.b64decode(captured['body_base64'], validate=True)) !=
                    attempt.get('raw_response') or
                [x.get('event') for x in events] !=
                    ['request_intent', 'request_started', 'request_finished'] or
                events[0].get('id') != rid or
                events[0].get('request_sha256') != request['request_sha256'] or
                events[1].get('id') != rid or
                events[1].get('request_sha256') != request['request_sha256'] or
                events[1].get('attempt_id') != attempt_id or
                events[2].get('id') != rid or
                events[2].get('attempt_id') != attempt_id or
                events[2].get('status') != 'ok' or
                events[2].get('billing_ok') is not True or
                events[2].get('cost_unknown') is not False or
                events[2].get('observed_cost_usd') != attempt.get('observed_cost_usd')):
            raise ValueError('Closed stage request or raw response differs at ' + rid)
        classified = controller.original.classify(
            attempt['raw_response'], attempt['model_catalog_entry'],
            attempt['provider_endpoint'])
        observed = Decimal(str(attempt.get('observed_cost_usd')))
        response_cost = Decimal(str((attempt['raw_response'].get('usage') or {}).get('cost')))
        if (any(attempt.get(key) != value for key, value in classified.items()) or
                observed != response_cost or
                not Decimal(0) <= observed <= Decimal(manifest['reserve_usd']) or
                attempt.get('billing_ok') is not True or
                attempt.get('cost_unknown') is not False or
                attempt.get('response_diagnostic', {}).get('passed') is not True):
            raise ValueError('Closed stage classification or charge differs at ' + rid)
    projected = [public_row(record) for record in attempts]
    if (summary.get('responses') != projected or
            any(set(row) != PUBLIC_KEYS for row in summary['responses'])):
        raise ValueError('Public stage projection differs from private evidence')
    return projected


def export_closed_stage(config, fresh, condition, phase, manifest_sha):
    """Make an exclusive public projection after controller closure; do not dispatch."""
    if (fresh, condition, phase) not in STAGES:
        raise ValueError('Unknown continuation stage')
    if config != controller.study.CONFIG:
        raise ValueError('Wrong Gemma configuration')
    manifest = controller.verify_manifest(manifest_sha)
    controller.verify_stage_closure(manifest, manifest_sha, fresh, condition, phase)
    source = controller.stage_paths(fresh, condition, phase)
    source['review'] = controller.review_path(fresh, condition, phase)
    records = first_report.rows(source['attempts'])
    projected = [public_row(record) for record in records]
    output = ROOT / stage_base(fresh, condition, phase).parent / (phase + '.public-summary.json')
    value = {'schema': SCHEMA + '-public-stage-v1',
             'stage': f'{fresh}/{condition}/{phase}',
             'manifestSha256': manifest_sha,
             'manualPrivacyReviewRequired': True,
             'privateSourceSha256': {key: first_report.digest(path)
                                    for key, path in source.items()},
             'responses': projected}
    with output.open('x') as out:
        json.dump(value, out, indent=2, ensure_ascii=False)
        out.write('\n')
        out.flush()
        os.fsync(out.fileno())
    return output


def composite_p0(original, suffix, labels, unknown_bound):
    """A fixed-60 tally exists only after the complete 58-position suffix."""
    if ([r.get('id') for r in original] != IDS[:2] or
            original[0].get('status') != 'ok' or
            original[1].get('status') != 'service_error' or
            [r.get('id') for r in suffix] != IDS[2:]):
        raise ValueError('Composite P0 does not cover the stopped 60-position plan')
    combined = original + [
        {'id': r['id'], 'status': r['status'], 'prediction': r['prediction']}
        for r in suffix]
    return {'pass': 'fresh2', 'condition': 'P0',
            'status': 'completed_composite_interrupted',
            'cleanMatchedThreeEligible': False,
            'score': first_report.score(combined, labels),
            'originalFailedId': 'DEV-002',
            'suffixSaved': len(suffix),
            'unknownCostUpperBoundUsd': unknown_bound}


def build(root=ROOT):
    root = Path(root).resolve()
    previous = first_report.build(root)
    bindings = list(previous['sourceBindings'])
    bind(root, 'scripts/build_gemma26_second_continuation_findings.py', bindings)
    manifest_file = bind(root, SECOND / 'manifest.json', bindings)
    manifest_sha = first_report.digest(manifest_file)
    manifest = json.loads(manifest_file.read_text())
    if (manifest.get('schema') != CONTROLLER_SCHEMA or
            manifest.get('status') != 'FROZEN' or
            manifest.get('configuration_id') != previous['configuration'] or
            manifest.get('clean_matched_three_eligible') is not False or
            manifest.get('original_failed_id') != 'DEV-007' or
            manifest.get('first_suffix_failed_id') != 'DEV-002' or
            manifest.get('original_never_sent_ids') != IDS[2:] or
            manifest.get('reference_labels_read') is not False or
            [(s.get('fresh_pass'), s.get('condition'), s.get('stage'))
             for s in manifest.get('stages', [])] != STAGES):
        raise ValueError('Second continuation identity or schedule differs')
    for source in manifest['source_bindings'].values():
        bind(root, source['path'], bindings, source['sha256'], public=False)
    stage_status = []
    stage_usage = {}
    closed = {}
    gap = False
    for spec in manifest['stages']:
        fresh, condition, phase = (spec[k] for k in ('fresh_pass', 'condition', 'stage'))
        stem = stage_base(fresh, condition, phase)
        journal = root / stem.parent / (phase + '.journal.jsonl')
        summary = root / stem.parent / (phase + '.public-summary.json')
        public_review = root / stem.parent / (phase + '.public-review.json')
        if public_review.is_file():
            if not summary.is_file():
                raise ValueError('Public review exists without its stage summary')
            if gap:
                raise ValueError('Closed stage follows an incomplete predecessor')
            closed[(fresh, condition, phase)] = verify_public_stage(
                root, manifest, manifest_sha, spec, bindings)
            status = 'closed_public_verified'
            stage_usage[f'{fresh}/{condition}/{phase}'] = public_usage(
                closed[(fresh, condition, phase)])
        else:
            gap = True
            stopped_detail = None
            if summary.is_file():
                status = 'awaiting_public_review'
            elif journal.is_file():
                events = first_report.rows(journal) if journal.stat().st_size else []
                terminal = events[-1] if events else {}
                if terminal.get('event') == 'phase_completed':
                    status = 'awaiting_public_review'
                elif terminal.get('event') == 'phase_stopped':
                    finished = [event for event in events
                                if event.get('event') == 'request_finished']
                    if (not finished or
                            [event.get('id') for event in finished] != spec['ids'][:len(finished)] or
                            terminal.get('id') != finished[-1].get('id') or
                            len(finished) > len(spec['ids']) or
                            finished[-1].get('status') == 'ok'):
                        raise ValueError('Stopped stage journal differs from frozen order')
                    bind(root, journal.relative_to(root), bindings)
                    status = 'stopped_unscored'
                    stopped_detail = {'stoppedAtId': terminal['id'],
                                      'attempted': len(finished),
                                      'neverSent': len(spec['ids']) - len(finished),
                                      'score': None}
                else:
                    status = 'incomplete_unscored'
            else:
                status = 'not_started_in_cutoff'
        stage_row = {'stage': f'{fresh}/{condition}/{phase}',
                     'status': status,
                     'count': len(closed.get((fresh, condition, phase), []))}
        if status == 'stopped_unscored':
            stage_row.update(stopped_detail)
        stage_status.append(stage_row)
    composite = None
    later_scores = {}
    labels = None
    if ('fresh2', 'P0', 'suffix') in closed:
        old_path = bind(root, FIRST / 'fresh2/P0/development.attempts.jsonl',
                        bindings, public=False)
        original = first_report.rows(old_path)
        if ([r.get('id') for r in original] != IDS[:2] or
                previous['stoppedPhases'][0]['failedId'] != 'DEV-002'):
            raise ValueError('First DEV-002 prefix differs')
        suffix = closed[('fresh2', 'P0', 'suffix')]
        label_file = bind(root, first_report.LABELS, bindings, first_report.LABEL_SHA)
        labels = {r['id']: r['proposed_labels'] for r in first_report.rows(label_file)}
        composite = composite_p0(original, suffix, labels,
                                 previous['stoppedPhases'][0]['usage'][
                                     'unknownCostUpperBoundUsd'])
    for condition in ('P2', 'P0', 'P1'):
        key = ('fresh3', condition, 'development')
        if key not in closed:
            continue
        if labels is None:
            raise ValueError('Later completed stage lacks the closed P0 predecessor')
        responses = closed[key]
        if [r['id'] for r in responses] != IDS:
            raise ValueError('Later development phase lacks all 60 positions')
        later_scores[condition] = {
            'status': 'completed',
            'score': first_report.score([
                {'id': r['id'], 'status': r['status'], 'prediction': r['prediction']}
                for r in responses], labels),
            'cleanMatchedThreeEligible': False}
    return {'schema': SCHEMA, 'seriesId': CONTROLLER_SCHEMA,
            'configuration': manifest['configuration_id'],
            'method': 'descriptive-second-interruption-continuation',
            'cleanMatchedThreeEligible': False,
            'denominator': 60, 'plannedConditions': 9,
            'originalInterruption': {'failedId': 'DEV-007',
                                     'status': 'service_error',
                                     'preservedScore': previous['passes']['fresh1']['P2']['score']},
            'secondInterruption': {'failedId': 'DEV-002',
                                   'status': 'service_error',
                                   'saved': previous['stoppedPhases'][0]['attempted'],
                                   'unknownCostUpperBoundUsd': previous['stoppedPhases'][0][
                                       'usage']['unknownCostUpperBoundUsd']},
            'priorCompletedConditions': previous['completedConditions'],
            'completedConditions': previous['completedConditions'] +
                                   (1 if composite else 0) + len(later_scores),
            'stageStatus': stage_status,
            'closedStageUsage': stage_usage,
            'compositeP0': composite,
            'laterPassScores': {'fresh3': later_scores},
            'publicCompositeP0Available': composite is not None,
            'sourceBindings': bindings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--export-closed-stage', nargs=3,
                        metavar=('FRESH_PASS', 'CONDITION', 'STAGE'))
    parser.add_argument('--manifest-sha256')
    args = parser.parse_args()
    if args.export_closed_stage:
        if args.root != ROOT or not args.manifest_sha256 or args.output or args.check:
            raise ValueError('Public export requires exact live controller and manifest SHA')
        print(export_closed_stage(controller.study.CONFIG, *args.export_closed_stage,
                                  args.manifest_sha256))
        return
    result = build(args.root)
    if args.output or args.check:
        if not result['publicCompositeP0Available']:
            raise ValueError('No public final while 58-record suffix remains unfinished')
        content = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
        if args.check:
            if args.output is None or args.output.read_text() != content:
                raise ValueError('Public second-continuation report differs')
        elif args.output:
            args.output.write_text(content)
    print('Gemma26 second continuation:', result['stageStatus'][0]['status'])


if __name__ == '__main__':
    main()
