#!/usr/bin/env python3
"""Separate, review-gated Venice continuation after repeat-2 P1's historical 429."""
import argparse
import base64
import binascii
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import time
import urllib.error

import mistral_p1_never_sent_suffix as suffix
import openrouter_repeat_wave as wave
import openrouter_paid_benchmark as paid

ROOT = Path(__file__).resolve().parents[1]
SPEC_ID = suffix.SPEC_ID
BASE = suffix.ORIGINAL
OUTPUT = BASE / 'later-phases-v1'
SCHEMA = 'mistral-later-phases-v1'
REVIEW_SCHEMA = 'mistral-later-phases-root-review-v1'
ORDER = (('repeat2', 'P0'), ('repeat3', 'P1'), ('repeat3', 'P0'), ('repeat3', 'P2'))
IDS = [f'DEV-{i:03}' for i in range(1, 61)]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def path(relative):
    value = (ROOT / relative).resolve()
    value.relative_to(ROOT.resolve())
    return value


def bind(relative):
    return {'path': str(relative), 'sha256': sha(path(relative).read_bytes())}


def read_bound(item):
    raw = path(item['path']).read_bytes()
    if sha(raw) != item['sha256']:
        raise ValueError('Bound source changed: ' + item['path'])
    return raw


def lines(raw):
    if raw and (not raw.endswith(b'\n') or any(not x.strip() for x in raw.splitlines())):
        raise ValueError('Incomplete JSONL evidence')
    return [json.loads(x) for x in raw.splitlines()]


def suffix_source():
    p2 = BASE / 'repeat2' / 'P2'
    return {'manifest': bind(suffix.SUFFIX / 'frozen-manifest.json'),
            'reconciliation': bind(suffix.SUFFIX / 'reconciliation.json'),
            'root_review': bind(BASE / 'root-review-v1.json'),
            'budget_manifest': bind(BASE / 'budget-partition-v1.json'),
            'original_p2_claim': bind(p2 / 'development.claim.json'),
            'original_p2_journal': bind(p2 / 'development.journal.jsonl'),
            'original_p2_attempts': bind(p2 / 'development.attempts.jsonl'),
            'original_p2_responses': bind(p2 / 'development.responses.jsonl'),
            'original_p2_smoke_inspection': bind(p2 / 'smoke-inspection.json')}


def verify_suffix(sources):
    frozen = read_bound(sources['manifest'])
    digest = sources['manifest']['sha256']
    manifest = suffix.validate_manifest(frozen, digest)
    actual = suffix.reconcile(path(sources['manifest']['path']), digest)
    saved = json.loads(read_bound(sources['reconciliation']))
    if saved != actual or actual['status_counts'] != {'ok': 59, 'service_error': 1} or (
            actual['coverage_status'] != 'closed_with_historical_service_error' or
            actual['strict_complete_pass'] is not False or
            actual['positions'][42]['id'] != 'DEV-043' or actual['positions'][42]['status'] != 'service_error'):
        raise ValueError('P1 composite is not reviewed 59 valid plus historical 429')
    if manifest['sources']['original_review'] != sources['root_review'] or (
            manifest['sources']['budget_manifest'] != sources['budget_manifest']):
        raise ValueError('P1 source review or budget differs')
    suffix.require_unknown_accounted(manifest)
    return manifest


def expected_manifest():
    spec = wave.SPECS[SPEC_ID]
    if spec.orders['repeat2'] != ('P2', 'P1', 'P0') or spec.orders['repeat3'] != ('P1', 'P0', 'P2'):
        raise ValueError('Frozen phase order changed')
    sources = suffix_source()
    verify_suffix(sources)
    plans = {repeat: bind(BASE / repeat / 'manifest.json') for repeat in ('repeat2', 'repeat3')}
    values = {repeat: wave.verify(spec, repeat, item['sha256']) for repeat, item in plans.items()}
    original_review = json.loads(read_bound(sources['root_review']))
    wave.review_receipt(spec, path(sources['root_review']['path']), 'repeat2', plans['repeat2']['sha256'])
    phases = []
    for repeat, condition in ORDER:
        phase = values[repeat]['conditions'][condition]
        if [r['record_id'] for r in phase['development']] != IDS or (
                [r['record_id'] for r in phase['smoke']] != IDS[:3]):
            raise ValueError('Frozen phase membership differs')
        phases.append({'repeat': repeat, 'condition': condition,
                       'smoke': phase['smoke'], 'development': phase['development']})
    return {'schema': SCHEMA, 'status': 'DRAFT', 'configuration_id': SPEC_ID,
            'controller': bind(Path('scripts') / Path(__file__).name),
            'sources': sources, 'plans': plans, 'root_partition_id': original_review['partition_id'],
            'order': [{'repeat': r, 'condition': c} for r, c in ORDER], 'phases': phases,
            'policy': {'historical_p1_strict_complete': False, 'historical_p1_status_counts': {'ok': 59, 'service_error': 1},
                       'historical_failed_id': 'DEV-043', 'retry_count': 0,
                       'continue_invalid_output': True, 'reference_labels_read': False,
                       'partition_cap_usd': spec.cap,
                       'timing_deviation': 'Later phases follow a separately completed P1 suffix after the historical 429'},
            'output_directory': str(OUTPUT)}


def validate_manifest(raw, digest=None, frozen=True):
    if digest is not None and sha(raw) != digest:
        raise ValueError('Continuation manifest hash differs')
    value = json.loads(raw)
    expected = expected_manifest()
    if frozen:
        expected['status'] = 'FROZEN'
    if value != expected:
        raise ValueError('Continuation manifest differs from frozen reconstruction')
    return value


def phase_paths(repeat, condition, phase):
    if (repeat, condition) not in ORDER or phase not in ('smoke', 'development'):
        raise ValueError('Unknown continuation phase')
    folder = path(OUTPUT / repeat / condition)
    return {key: folder / (phase + '.' + name) for key, name in (
        ('claim', 'claim.json'), ('journal', 'journal.jsonl'),
        ('attempts', 'attempts.jsonl'), ('responses', 'responses.jsonl'))}


def inspection_path(repeat, condition):
    return path(OUTPUT / repeat / condition / 'smoke-inspection.json')


def phase_plan(manifest, repeat, condition):
    return next(x for x in manifest['phases'] if (x['repeat'], x['condition']) == (repeat, condition))


def prior_complete(manifest, repeat, condition):
    position = ORDER.index((repeat, condition))
    if position == 0:
        # The original repeat-2 P2 phase precedes the composite P1; it remains untouched.
        spec = wave.SPECS[SPEC_ID]
        folder, _, journal, attempts = wave.phase_paths(spec, 'repeat2', 'P2', 'development')
        for kind in ('claim', 'journal', 'attempts', 'responses', 'smoke_inspection'):
            read_bound(manifest['sources']['original_p2_' + kind])
        original_rows = lines(attempts.read_bytes())
        if not wave.complete_journal(spec, 'repeat2', 'P2', 'development') or (
                len(original_rows) != 60 or [x.get('id') for x in original_rows] != IDS or
                any(x.get('status') != 'ok' for x in original_rows)):
            raise ValueError('Original repeat-2 P2 is not complete')
        return
    previous = ORDER[position - 1]
    if reconcile_phase(manifest, *previous)['completion_status'] not in ('complete', 'closed_with_failures'):
        raise ValueError('Prior continuation phase incomplete: ' + '/'.join(previous))


def validate_review(raw, manifest, digest, repeat, condition, phase):
    value = json.loads(raw)
    requested = {'repeat': repeat, 'condition': condition, 'phase': phase}
    if (value.get('schema') != REVIEW_SCHEMA or value.get('approved') is not True or
            value.get('manifest_sha256') != digest or
            value.get('controller_sha256') != manifest['controller']['sha256'] or
            value.get('suffix_reconciliation_sha256') != manifest['sources']['reconciliation']['sha256'] or
            value.get('original_review_sha256') != manifest['sources']['root_review']['sha256'] or
            value.get('budget_manifest_sha256') != manifest['sources']['budget_manifest']['sha256'] or
            value.get('partition_id') != manifest['root_partition_id'] or
            value.get('acknowledge_historical_p1_59_plus_1') is not True or
            value.get('acknowledge_timing_deviation') is not True or
            requested not in value.get('approved_phases', []) or
            not isinstance(value.get('review_note'), str) or not value['review_note'].strip()):
        raise ValueError('Explicit continuation root review missing or mismatched')
    return value


def require_inspected_smoke(manifest, digest, repeat, condition):
    report = reconcile_phase(manifest, repeat, condition, 'smoke')
    if report['completion_status'] != 'complete' or report['status_counts'] != {'ok': 3}:
        raise ValueError('Three valid completed smoke calls required')
    location = inspection_path(repeat, condition)
    proof = json.loads(location.read_text())
    paths = phase_paths(repeat, condition, 'smoke')
    if (proof.get('schema') != SCHEMA + '-smoke-inspection' or
            proof.get('decision') != 'accepted_unchanged' or proof.get('manifest_sha256') != digest or
            any(proof.get(kind + '_sha256') != sha(paths[kind].read_bytes()) for kind in ('journal', 'attempts', 'responses'))):
        raise ValueError('Inspected smoke binding changed')


def dispatch(manifest_path, digest, review_path, repeat, condition, phase, env_file=None):
    manifest = validate_manifest(Path(manifest_path).read_bytes(), digest)
    if (repeat, condition) not in ORDER or phase not in ('smoke', 'development'):
        raise ValueError('Phase outside continuation order')
    validate_review(Path(review_path).read_bytes(), manifest, digest, repeat, condition, phase)
    prior_complete(manifest, repeat, condition)
    if phase == 'development':
        require_inspected_smoke(manifest, digest, repeat, condition)
    paths = phase_paths(repeat, condition, phase)
    if any(x.exists() for x in paths.values()):
        raise FileExistsError('Phase already claimed; no replay')
    spec = wave.SPECS[SPEC_ID]
    plan = wave.verify(spec, repeat, manifest['plans'][repeat]['sha256'])
    model, endpoint, reserve = wave.live_controls(spec, plan, condition)
    receipt = json.loads(read_bound(manifest['sources']['root_review']))
    ledger = wave.budget_gate(spec, receipt, path(manifest['sources']['budget_manifest']['path']))
    try:
        _, pending, blocked = ledger.state()
        if pending or blocked:
            raise ValueError('Unresolved or blocked child budget')
        token = paid.load_key(env_file)
        selected = phase_plan(manifest, repeat, condition)[phase]
        paths['claim'].parent.mkdir(parents=True, exist_ok=True)
        with paths['claim'].open('x') as output:
            paid.durable(output, {'schema': SCHEMA + '-claim', 'repeat': repeat,
                                  'condition': condition, 'phase': phase, 'manifest_sha256': digest,
                                  'review_sha256': sha(Path(review_path).read_bytes()),
                                  'request_ids': [x['record_id'] for x in selected],
                                  'ledger_event_count': len(ledger.events), 'utc': wave.utc()})
        complete = True
        with paths['journal'].open('x') as audit, paths['attempts'].open('x') as output, paths['responses'].open('x') as raw_output:
            paid.durable(audit, {'event': 'phase_started', 'repeat': repeat, 'condition': condition,
                                 'phase': phase, 'manifest_sha256': digest, 'utc': wave.utc()})
            try:
                for request in selected:
                    rid = request['record_id']
                    paid.durable(audit, {'event': 'request_intent', 'id': rid,
                                         'request_sha256': request['request_sha256'], 'utc': wave.utc()})
                    attempt = ledger.reserve(reserve, rid)
                    paid.durable(audit, {'event': 'request_started', 'id': rid, 'attempt_id': attempt,
                                         'request_sha256': request['request_sha256'], 'utc': wave.utc()})
                    record = {'id': rid, 'repeat': repeat, 'condition': condition, 'phase': phase,
                              'attempt_id': attempt, 'request': request['payload'],
                              'request_sha256': request['request_sha256'], 'manifest_sha256': digest,
                              'provider_endpoint': endpoint, 'model_catalog_entry': model,
                              'requested_model': spec.model, 'reasoning_effort': spec.effort,
                              'reference_labels_read': False, 'reserved_cost_usd': str(reserve),
                              'request_timeout_seconds': spec.timeout, 'started_utc': wave.utc()}
                    actual = None
                    start = time.perf_counter()
                    try:
                        body = wave.fetch_recorded(request['payload'], token, spec.timeout, raw_output,
                                                   rid, attempt, request['request_sha256'])
                        body = json.loads(json.dumps(body).replace(token, '[REDACTED]'))
                        record['raw_response'] = body
                        if isinstance(body, dict):
                            usage = body.get('usage') or {}
                            if isinstance(usage, dict) and usage.get('cost') is not None:
                                actual = paid.number(usage['cost'])
                            record.update(wave.classify(spec, body, endpoint))
                        else:
                            record['status'] = 'control_violation'
                    except Exception as exc:
                        record.update(status='service_error', error_type=type(exc).__name__)
                        if isinstance(exc, urllib.error.HTTPError):
                            record.update(suffix.capture_http_error(exc, token, raw_output, rid,
                                                                     attempt, request['request_sha256']))
                    billing_ok = ledger.settle(attempt, actual)
                    record.update(elapsed_seconds=time.perf_counter() - start,
                                  observed_cost_usd=str(actual) if actual is not None else None,
                                  cost_unknown=actual is None, billing_ok=billing_ok)
                    if isinstance(record.get('raw_response'), dict):
                        diagnostic = wave.audit_response(record, 'openrouter_paid_v1', endpoint['context_length'] - 4096)
                        record['response_diagnostic'] = diagnostic
                        if not diagnostic['passed'] and record['status'] == 'ok':
                            record['status'] = 'prompt_admission_failure'
                    paid.durable(output, record)
                    paid.durable(audit, {'event': 'request_finished', 'id': rid, 'attempt_id': attempt,
                                         'status': record['status'], 'billing_ok': billing_ok,
                                         'cost_unknown': record['cost_unknown'], 'utc': wave.utc()})
                    if not wave.continue_record(spec, record, phase):
                        complete = False
                        paid.durable(audit, {'event': 'phase_stopped', 'id': rid,
                                             'reason': record['status'], 'ledger_event_count': len(ledger.events),
                                             'utc': wave.utc()})
                        break
                if complete:
                    paid.durable(audit, {'event': 'phase_completed', 'repeat': repeat,
                                         'condition': condition, 'phase': phase,
                                         'request_count': len(selected),
                                         'ledger_event_count': len(ledger.events), 'utc': wave.utc()})
            finally:
                events = lines(paths['journal'].read_bytes())
                if events and events[-1].get('event') not in ('phase_completed', 'phase_stopped', 'phase_aborted'):
                    paid.durable(audit, {'event': 'phase_aborted', 'reason': 'exception_or_interruption',
                                         'ledger_event_count': len(ledger.events), 'utc': wave.utc()})
        return complete
    finally:
        ledger.close()


def reconcile_phase(manifest, repeat, condition, phase='development'):
    paths = phase_paths(repeat, condition, phase)
    selected = phase_plan(manifest, repeat, condition)[phase]
    expected = [x['record_id'] for x in selected]
    if not paths['claim'].exists():
        if any(paths[x].exists() for x in ('journal', 'attempts', 'responses')):
            raise ValueError('Phase evidence exists without claim')
        return {'completion_status': 'not_started', 'status_counts': {}, 'finished_requests': 0,
                'never_sent_ids': expected, 'unknown_started_ids': [], 'unknown_reserved_ids': []}
    claim = json.loads(paths['claim'].read_text())
    if claim.get('manifest_sha256') != sha(path(OUTPUT / 'frozen-manifest.json').read_bytes()) or (
            claim.get('repeat'), claim.get('condition'), claim.get('phase'), claim.get('request_ids')) != (
            repeat, condition, phase, expected) or type(claim.get('ledger_event_count')) is not int:
        raise ValueError('Continuation claim differs')
    journal = lines(paths['journal'].read_bytes())
    attempts = lines(paths['attempts'].read_bytes())
    raw = lines(paths['responses'].read_bytes())
    starts = [x for x in journal if x.get('event') == 'request_started']
    finishes = [x for x in journal if x.get('event') == 'request_finished']
    if (not journal or journal[0].get('event') != 'phase_started' or
            [x.get('id') for x in starts] != expected[:len(starts)] or
            [x.get('id') for x in attempts] != expected[:len(attempts)] or
            len(starts) > len(attempts) + 1 or
            [(x.get('id'), x.get('attempt_id'), x.get('status')) for x in finishes] !=
            [(x.get('id'), x.get('attempt_id'), x.get('status')) for x in attempts]):
        raise ValueError('Continuation journal or attempt prefix differs')
    start_by_attempt = {x['attempt_id']: x for x in starts}
    if len(start_by_attempt) != len(starts):
        raise ValueError('Duplicate continuation attempt ID')
    raw_by_attempt = {x.get('attempt_id'): x for x in raw}
    if len(raw_by_attempt) != len(raw):
        raise ValueError('Duplicate raw sidecar')
    suffix_manifest = suffix.validate_manifest(read_bound(manifest['sources']['manifest']),
                                               manifest['sources']['manifest']['sha256'])
    all_events = lines(suffix.child_ledger_path(suffix_manifest).read_bytes())
    if claim['ledger_event_count'] < 0 or claim['ledger_event_count'] > len(all_events):
        raise ValueError('Claim ledger boundary differs')
    terminal_count = journal[-1].get('ledger_event_count')
    if journal[-1].get('event') in ('phase_completed', 'phase_stopped', 'phase_aborted'):
        if type(terminal_count) is not int or not claim['ledger_event_count'] <= terminal_count <= len(all_events):
            raise ValueError('Terminal ledger boundary differs')
    else:
        terminal_count = len(all_events)
    ledger_events = all_events[claim['ledger_event_count']:terminal_count]
    reservations = {x.get('attempt_id'): x for x in ledger_events if x.get('event') == 'reserve'}
    terminal = journal[-1].get('event')
    positions = []
    for index, request in enumerate(selected):
        rid = request['record_id']
        if index >= len(starts):
            positions.append({'id': rid, 'status': 'never_sent'})
            continue
        start_row = starts[index]
        attempt_id = start_row['attempt_id']
        if (start_row.get('request_sha256') != request['request_sha256'] or
                attempt_id not in reservations or reservations[attempt_id].get('record_id') != rid):
            raise ValueError('Started request differs from plan or reservation')
        if index >= len(attempts):
            positions.append({'id': rid, 'status': 'unknown_started', 'attempt_id': attempt_id})
            continue
        row = attempts[index]
        if (row.get('attempt_id') != attempt_id or row.get('request') != request['payload'] or
                row.get('request_sha256') != request['request_sha256'] or row.get('reference_labels_read') is not False or
                row.get('repeat') != repeat or row.get('condition') != condition or row.get('phase') != phase or
                row.get('manifest_sha256') != claim['manifest_sha256']):
            raise ValueError('Continuation attempt differs from plan')
        settlements = [x for x in ledger_events if x.get('attempt_id') == attempt_id and x.get('event') == 'settle']
        if row.get('cost_unknown') is False:
            if (len(settlements) != 1 or type(row.get('billing_ok')) is not bool or
                    paid.number(settlements[0]['usd']) != paid.number(row.get('observed_cost_usd'))):
                raise ValueError('Known continuation charge differs')
        elif row.get('cost_unknown') is True:
            if settlements or row.get('billing_ok') is not False or row.get('observed_cost_usd') is not None:
                raise ValueError('Unknown continuation charge was falsely settled')
        else:
            raise ValueError('Continuation cost state missing')
        sidecar = raw_by_attempt.get(attempt_id)
        if 'raw_response' in row or 'error_body' in row:
            if not sidecar or sidecar.get('id') != rid or sidecar.get('request_sha256') != request['request_sha256']:
                raise ValueError('Missing or unattributed raw sidecar')
        if 'raw_response' in row:
            if sidecar.get('body_truncated_at_limit') or sidecar.get('read_error') or 'body_base64' not in sidecar:
                raise ValueError('Incomplete successful response bytes')
            try:
                body = json.loads(base64.b64decode(sidecar['body_base64'], validate=True))
            except (ValueError, binascii.Error):
                raise ValueError('Malformed saved response bytes') from None
            if body != row['raw_response']:
                raise ValueError('Saved response differs from raw bytes')
        elif sidecar and any(key in row and sidecar.get(key) != row[key] for key in ('error_body', 'http_status', 'read_error')):
            raise ValueError('Saved HTTP error differs from raw bytes')
        positions.append({'id': rid, 'status': row['status'], 'attempt_id': attempt_id})
    if any(x.get('attempt_id') not in start_by_attempt for x in raw):
        raise ValueError('Raw response lacks started request')
    # A crash between reserve and request_started leaves the next position ambiguous too.
    unmatched = [x for x in ledger_events if x.get('event') == 'reserve' and
                 x.get('attempt_id') not in start_by_attempt and
                 x.get('record_id') in expected and
                 x.get('attempt_id') not in {y.get('attempt_id') for y in ledger_events if y.get('event') == 'settle'}]
    if unmatched:
        if len(starts) >= len(expected) or len(unmatched) != 1 or unmatched[0]['record_id'] != expected[len(starts)]:
            raise ValueError('Unmatched reservation outside next position')
        positions[len(starts)] = {'id': expected[len(starts)], 'status': 'unknown_reserved',
                                  'attempt_id': unmatched[0]['attempt_id']}
    counts = dict(sorted(Counter(x['status'] for x in positions).items()))
    if terminal == 'phase_completed' and (len(attempts) != len(selected) or len(starts) != len(selected) or
            any(x['status'] in ('never_sent', 'unknown_started', 'unknown_reserved', 'service_error') for x in positions)):
        raise ValueError('Claimed completion has unresolved positions')
    status = ('complete' if counts == {'ok': len(selected)} else 'closed_with_failures') if terminal == 'phase_completed' else 'partial'
    return {'completion_status': status, 'terminal_event': terminal, 'status_counts': counts,
            'finished_requests': len(attempts), 'positions': positions,
            'never_sent_ids': [x['id'] for x in positions if x['status'] == 'never_sent'],
            'unknown_started_ids': [x['id'] for x in positions if x['status'] == 'unknown_started'],
            'unknown_reserved_ids': [x['id'] for x in positions if x['status'] == 'unknown_reserved']}


def inspect_smoke(manifest_path, digest, repeat, condition, note):
    if not note.strip():
        raise ValueError('Inspection note required')
    manifest = validate_manifest(Path(manifest_path).read_bytes(), digest)
    prior_complete(manifest, repeat, condition)
    report = reconcile_phase(manifest, repeat, condition, 'smoke')
    if report['completion_status'] != 'complete' or report['status_counts'] != {'ok': 3}:
        raise ValueError('Three valid smoke attempts required')
    paths = phase_paths(repeat, condition, 'smoke')
    value = {'schema': SCHEMA + '-smoke-inspection', 'decision': 'accepted_unchanged',
             'repeat': repeat, 'condition': condition, 'manifest_sha256': digest,
             'note': note, **{kind + '_sha256': sha(paths[kind].read_bytes())
                             for kind in ('journal', 'attempts', 'responses')}}
    target = inspection_path(repeat, condition)
    with target.open('x') as out:
        json.dump(value, out, indent=2)
        out.write('\n')
        out.flush()
        os.fsync(out.fileno())
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('prepare')
    freeze = sub.add_parser('freeze')
    freeze.add_argument('--draft', required=True)
    for action in ('validate', 'reconcile', 'smoke', 'development', 'inspect-smoke'):
        command = sub.add_parser(action)
        command.add_argument('--manifest', required=True)
        command.add_argument('--sha256', required=True)
        if action in ('smoke', 'development', 'inspect-smoke'):
            command.add_argument('--repeat', required=True, choices=('repeat2', 'repeat3'))
            command.add_argument('--condition', required=True, choices=('P0', 'P1', 'P2'))
        if action in ('smoke', 'development'):
            command.add_argument('--review', required=True)
            command.add_argument('--env-file')
        if action == 'inspect-smoke':
            command.add_argument('--note', required=True)
        if action == 'reconcile':
            command.add_argument('--repeat', required=True, choices=('repeat2', 'repeat3'))
            command.add_argument('--condition', required=True, choices=('P0', 'P1', 'P2'))
    args = parser.parse_args()
    if args.action == 'prepare':
        target = path(OUTPUT / 'draft-manifest.json')
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('x') as out:
            json.dump(expected_manifest(), out, indent=2)
            out.write('\n')
        print(target)
    elif args.action == 'freeze':
        raw = Path(args.draft).read_bytes()
        manifest = validate_manifest(raw, frozen=False)
        manifest['status'] = 'FROZEN'
        target = path(OUTPUT / 'frozen-manifest.json')
        with target.open('x') as out:
            json.dump(manifest, out, indent=2)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
        print(target, sha(target.read_bytes()))
    elif args.action == 'validate':
        validate_manifest(Path(args.manifest).read_bytes(), args.sha256)
        print('validated')
    elif args.action == 'reconcile':
        manifest = validate_manifest(Path(args.manifest).read_bytes(), args.sha256)
        print(json.dumps(reconcile_phase(manifest, args.repeat, args.condition), indent=2))
    elif args.action == 'inspect-smoke':
        print(json.dumps(inspect_smoke(args.manifest, args.sha256, args.repeat, args.condition, args.note), indent=2))
    else:
        print('completed' if dispatch(args.manifest, args.sha256, args.review, args.repeat,
                                      args.condition, args.action, args.env_file) else 'stopped')


if __name__ == '__main__':
    main()
