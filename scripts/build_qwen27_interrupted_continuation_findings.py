#!/usr/bin/env python3
"""Offline public account of the two interrupted Qwen27 P0 continuations.

The public build reads only an explicit archive root. Private original attempts,
raw responses, budget manifests and ledgers are verified by ``prepare_export``
before a separate human privacy review admits the sanitized export.
"""
import argparse
import base64
from collections import Counter
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/qwen27-fresh-matched3-v2')
CONT = BASE / 'interruption-continuation-v1'
LABELS = Path('data/pilot/proposed_labels.jsonl')
LABEL_SHA = '440fa16759473b6d4ff52fe7e7296e5f2dfca0a58f5df26f20aef0daafed1464'
SCHEMA = 'qwen27-v2-interrupted-continuation-findings-v1'
EXPORT_SCHEMA = SCHEMA + '-public-export'
REVIEW_SCHEMA = SCHEMA + '-privacy-review'
MANIFEST_SHA = {
    'medium': 'ebbe5883347cc7054173db783655451581081c7884e524c149733119d6a63684',
    'xhigh': '26d30b50626c203b6666cae49a3d2187b03a9b74bc76de01f091203bfaa4b080',
}
PLAN_SHA = {
    'medium': '99af3286e3b9d86297b4de681d5928bbdb11a9740122b72d8002cc360fae8464',
    'xhigh': '60ffa81000eb16a3e54ec2e649935cbc470de13f60e2447c48ae62f15cc3f74f',
}
REQUEST_SCHEDULE_SHA = {
    'medium': '4f0778d6ce43032144364318fdd1fa1beeb5653e7759f707c518355d611eb864',
    'xhigh': 'a2fadfd076b4ec5a43daf28f7c872413b293aec4caee84f6d070f1914a640fb4',
}
P1_REQUEST_SCHEDULE_SHA = {
    'medium': '180ac3578749979b5e03403a69f3418ebe877e0129b871c5c0372ebd0205edbd',
    'xhigh': '9b5b15a538d5e2709486c2be5e6bd74af84de58be067f30c61f5bb5932d55b1e',
}
PREFIX_PRIVATE_SHA = {
    'medium': {'attempts.jsonl': '67edc29634c5e8f2d66d8b572cc6854e00b79b0c7fbd2308780f4c6a935693bd',
               'responses.jsonl': '23810dfbe91b43e84d8b596291d9f1b0de2cb09fecb55274af662ea22ae6baaa'},
    'xhigh': {'attempts.jsonl': 'feb110ac9c5b94f503ec541f1e011d3787bf4c0f20cb45157fbd9e88164705e5',
              'responses.jsonl': '4ba3f1818685f5669f99b3242f2501d9f86d4fed6c84da9587b5db1c784112f3'},
}
FAILED = {'medium': ('DEV-022', 21), 'xhigh': ('DEV-037', 36)}
IDS = [f'DEV-{i:03d}' for i in range(1, 61)]
FIELDS = ('sentiment', 'follow_up_needed', 'serious_concern_reported', 'testimonial_potential')
ALLOWED = {key: ({'positive', 'negative', 'mixed', 'neutral', 'insufficient_information'}
                 if key == 'sentiment' else {'yes', 'no', 'insufficient_information'})
           for key in FIELDS}
POSITION_KEYS = ('id', 'attempt_id', 'status', 'prediction', 'request_sha256',
                 'input_sha256', 'instruction_sha256', 'reference_labels_read',
                 'observed_cost_usd', 'reserved_cost_usd', 'cost_unknown',
                 'billing_ok', 'elapsed_seconds', 'usage', 'returned_model',
                 'returned_provider', 'finish_reason', 'error_type')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def path_under(root, relative):
    relative = Path(relative)
    if relative.is_absolute() or '..' in relative.parts or not relative.parts:
        raise ValueError('Unsafe public source path')
    path = (root / relative).resolve()
    path.relative_to(root)
    return path


def bind(root, relative, bindings, expected=None):
    path = path_under(root, relative)
    if not path.is_file():
        raise ValueError('Public source is missing: ' + str(relative))
    digest = sha(path)
    if expected is not None and digest != expected:
        raise ValueError('Public source hash differs: ' + str(relative))
    item = {'path': str(Path(relative)), 'sha256': digest}
    if item not in bindings:
        bindings.append(item)
    return path


def rows(path):
    raw = Path(path).read_bytes()
    if not raw or not raw.endswith(b'\n') or any(not line for line in raw.splitlines()):
        raise ValueError('Incomplete public JSONL: ' + str(path))
    return [json.loads(line) for line in raw.splitlines()]


def valid(value):
    return isinstance(value, dict) and set(value) == set(FIELDS) and all(
        isinstance(value[key], str) and value[key] in ALLOWED[key] for key in FIELDS)


def amount(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError):
        raise ValueError('Invalid observed cost') from None
    if not result.is_finite() or result < 0:
        raise ValueError('Invalid observed cost')
    return result


def duration(value):
    import math
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('Invalid client duration')
    return value


def public_position(private):
    """Allow only reviewed, non-request, non-raw outcome fields."""
    row = {key: private[key] for key in POSITION_KEYS if key in private and key != 'usage'}
    usage = private.get('usage')
    if usage is not None:
        row['usage'] = {key: usage[key] for key in
                        ('cost', 'prompt_tokens', 'completion_tokens', 'total_tokens')
                        if key in usage}
        details = usage.get('completion_tokens_details') or {}
        if 'reasoning_tokens' in details:
            row['usage']['provider_reported_reasoning_tokens'] = details['reasoning_tokens']
    return row


def schedule_sha(requests):
    encoded = json.dumps(requests, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(encoded).hexdigest()


def verify_aborted_stage(execution, manifest, kind, condition, phase):
    """Verify only saved, known-billed responses in an aborted stage.

    The next request was never reserved or sent. This is deliberately not a
    phase-closure verifier and cannot produce a 60-position score.
    """
    config = 'openrouter-paid-qwen3.8-27b-' + kind
    if (condition, phase) not in (('P0', 'suffix'), ('P1', 'development')):
        raise ValueError('Unexpected aborted stage')
    files = execution.stage_files(config, 'fresh3', condition, phase)
    review = execution.review_path(config, 'fresh3', condition, phase)
    execution.verify_review(review, manifest, MANIFEST_SHA[kind], 'fresh3', condition, phase)
    stage = f'fresh3/{condition}/{phase}'
    claim = json.loads(files['claim'].read_text())
    if any(claim.get(key) != value for key, value in {
            'series_id': manifest['series_id'], 'configuration_id': config,
            'stage': stage, 'manifest_sha256': MANIFEST_SHA[kind],
            'root_review_sha256': sha(review)}.items()):
        raise ValueError('Aborted suffix claim differs')
    attempts, captured, journal = (execution.rows(files[key]) for key in
                                   ('attempts', 'responses', 'journal'))
    planned = execution.selected_requests(config, 'fresh3', condition, phase)
    count = len(attempts)
    if (not 0 < count < len(planned) or len(captured) != count or
            [a.get('id') for a in attempts] != [p['record_id'] for p in planned[:count]] or
            [w.get('id') for w in captured] != [p['record_id'] for p in planned[:count]] or
            len(journal) != 2 + 3 * count or
            journal[0].get('event') != 'phase_started' or
            journal[-1].get('event') != 'phase_aborted' or
            journal[-1].get('reason') != 'exception_or_interruption'):
        raise ValueError('Aborted suffix membership or terminal event differs')
    budget = execution.bound(manifest['source_bindings']['new_budget_manifest'])
    child = Path(execution.budget_entry(config, budget)['child_ledger'])
    charges = execution.rows(child)
    for index, (attempt, wire, request) in enumerate(zip(attempts, captured, planned)):
        aid = attempt.get('attempt_id')
        rid = request['record_id']
        intent, started, finished = journal[1 + 3*index:4 + 3*index]
        if (not isinstance(aid, str) or not aid or
                attempt.get('series_id') != manifest['series_id'] or
                attempt.get('configuration_id') != config or
                attempt.get('stage') != stage or
                attempt.get('manifest_sha256') != MANIFEST_SHA[kind] or
                attempt.get('request') != request['payload'] or
                attempt.get('request_sha256') != request['request_sha256'] or
                attempt.get('input_sha256') != request['input_sha256'] or
                attempt.get('instruction_sha256') != request['instruction_sha256'] or
                attempt.get('reference_labels_read') is not False or
                attempt.get('status') != 'ok' or
                attempt.get('billing_ok') is not True or
                attempt.get('cost_unknown') is not False or
                attempt.get('observed_cost_usd') is None or
                amount(attempt['observed_cost_usd']) > amount(attempt['reserved_cost_usd']) or
                [(event.get('event'), event.get('id'), event.get('attempt_id'))
                 for event in (intent, started, finished)] != [
                    ('request_intent', rid, None),
                    ('request_started', rid, aid),
                    ('request_finished', rid, aid)] or
                intent.get('request_sha256') != request['request_sha256'] or
                started.get('request_sha256') != request['request_sha256'] or
                finished.get('status') != 'ok' or
                finished.get('billing_ok') is not True or
                finished.get('cost_unknown') is not False or
                finished.get('observed_cost_usd') != attempt['observed_cost_usd'] or
                wire.get('attempt_id') != aid or
                wire.get('request_sha256') != request['request_sha256'] or
                wire.get('http_status') != 200 or
                wire.get('body_truncated_at_limit') is not False or
                wire.get('read_error') is not None or
                [e for e in charges if e.get('attempt_id') == aid] != [
                    {'event': 'reserve', 'attempt_id': aid, 'record_id': rid,
                     'usd': manifest['reserve_usd']},
                    {'event': 'settle', 'attempt_id': aid,
                     'usd': attempt['observed_cost_usd']}]):
            raise ValueError('Aborted suffix request or settlement differs at ' + rid)
        decoded = json.loads(base64.b64decode(wire['body_base64'], validate=True))
        if (decoded != attempt.get('raw_response') or
                amount((decoded.get('usage') or {}).get('cost')) !=
                    amount(attempt['observed_cost_usd']) or
                any(attempt.get(key) != value for key, value in
                    execution.original.classify(decoded, attempt['model_catalog_entry'],
                                                attempt['provider_endpoint']).items()) or
                attempt.get('response_diagnostic') !=
                    execution.prompt_admission.audit_response(
                        attempt, 'openrouter_paid_v1',
                        attempt['provider_endpoint']['context_length'] - 4096) or
                attempt['response_diagnostic'].get('passed') is not True):
            raise ValueError('Aborted suffix raw response differs at ' + rid)
    if len({a['attempt_id'] for a in attempts}) != count:
        raise ValueError('Duplicate aborted suffix attempt')
    return count


def verify_aborted_suffix(execution, manifest, kind):
    return verify_aborted_stage(execution, manifest, kind, 'P0', 'suffix')


def prepare_export(kind, destination=None):
    """Verify private closure, then create a new sanitized candidate export.

    This does not publish or approve it. The operator must inspect the files and
    write a separate exact-hash privacy review before ``build`` accepts them.
    """
    if kind not in MANIFEST_SHA:
        raise ValueError('Unknown continuation configuration')
    import build_qwen27_interruption_findings as stopped
    import qwen27_v2_interruption_continuation as execution

    config = 'openrouter-paid-qwen3.8-27b-' + kind
    old = stopped.build()['series'][kind]
    manifest = execution.verify_manifest(config, MANIFEST_SHA[kind])
    if (manifest.get('clean_matched_three_eligible') is not False or
            manifest.get('failed_attempted_id') != FAILED[kind][0] or
            manifest.get('reference_labels_read') is not False):
        raise ValueError('Interrupted continuation identity differs')
    current = ROOT / CONT / kind / 'fresh3/P0/suffix'
    journal = execution.rows(current / 'suffix.journal.jsonl')
    terminal = journal[-1].get('event')
    if terminal == 'phase_completed':
        execution.verify_stage_closure(manifest, MANIFEST_SHA[kind], 'fresh3', 'P0', 'suffix')
        verified_count = 60 - FAILED[kind][1] - 1
    elif terminal == 'phase_aborted':
        verified_count = verify_aborted_suffix(execution, manifest, kind)
    else:
        raise ValueError('Suffix has no verified terminal event')
    original = ROOT / BASE / config / 'fresh3/P0'
    old_rows = execution.rows(original / 'development.attempts.jsonl')
    suffix_rows = execution.rows(current / 'suffix.attempts.jsonl')
    failed_id, prefix_valid = FAILED[kind]
    if (len(old_rows) != prefix_valid + 1 or old_rows[-1]['id'] != failed_id or
            len(suffix_rows) != verified_count or
            [r['id'] for r in old_rows + suffix_rows] != IDS[:len(old_rows + suffix_rows)] or
            old['score'] is not None or old['valid'] != prefix_valid or
            old['unknownStageCostUpperBoundUsd'] != manifest['reserve_usd']):
        raise ValueError('Private prefix, suffix or unknown bound differs')
    plan_path = ROOT / BASE / config / 'fresh3/manifest.json'
    if sha(plan_path) != PLAN_SHA[kind]:
        raise ValueError('Original frozen plan changed')
    plan = json.loads(plan_path.read_text())
    requests = plan['conditions']['P0']['development']
    if any(r.get('request') != p['payload'] or
           r.get('request_sha256') != p['request_sha256']
           for r, p in zip(old_rows + suffix_rows, requests)):
        raise ValueError('Original and suffix requests differ from frozen plan')
    p1_dir = ROOT / CONT / kind / 'fresh3/P1/development'
    p1_claim = p1_dir / 'development.claim.json'
    p1_rows = []
    p1_terminal = 'not_dispatched'
    if p1_claim.exists():
        execution.require_order(manifest, MANIFEST_SHA[kind], 'fresh3', 'P1', 'development')
        p1_events = execution.rows(p1_dir / 'development.journal.jsonl')
        p1_terminal = p1_events[-1].get('event')
        if p1_terminal == 'phase_completed':
            execution.verify_stage_closure(manifest, MANIFEST_SHA[kind],
                                           'fresh3', 'P1', 'development')
        elif p1_terminal == 'phase_aborted':
            verify_aborted_stage(execution, manifest, kind, 'P1', 'development')
        else:
            raise ValueError('P1 has no verified terminal event')
        p1_rows = execution.rows(p1_dir / 'development.attempts.jsonl')
        p1_planned = plan['conditions']['P1']['development']
        if ([r['id'] for r in p1_rows] != IDS[:len(p1_rows)] or
                any(r.get('request') != p['payload'] or
                    r.get('request_sha256') != p['request_sha256']
                    for r, p in zip(p1_rows, p1_planned))):
            raise ValueError('P1 requests differ from frozen plan')
    elif p1_dir.exists() and any(p1_dir.iterdir()):
        raise ValueError('P1 evidence exists without a claim')
    target = Path(destination or ROOT / CONT / kind / 'public-evidence-v1').resolve()
    target.relative_to(ROOT.resolve())
    target.mkdir(parents=True, exist_ok=False)
    outputs = {}
    for label, source in (('prefix', old_rows), ('suffix', suffix_rows)):
        file = target / (label + '.positions.jsonl')
        with file.open('x') as out:
            for row in source:
                out.write(json.dumps(public_position(row), sort_keys=True) + '\n')
        outputs[label] = {'path': str(file.relative_to(ROOT)), 'sha256': sha(file)}
    if p1_rows:
        file = target / 'p1.positions.jsonl'
        with file.open('x') as out:
            for row in p1_rows:
                out.write(json.dumps(public_position(row), sort_keys=True) + '\n')
        outputs['p1'] = {'path': str(file.relative_to(ROOT)), 'sha256': sha(file)}
    projection = {'schema': EXPORT_SCHEMA + '-request-projection',
                  'configuration_id': config,
                  'original_plan_sha256': PLAN_SHA[kind],
                  'continuation_manifest_sha256': MANIFEST_SHA[kind],
                  'series_id': manifest['series_id'],
                  'clean_matched_three_eligible': False,
                  'reference_labels_read': False,
                  'failed_id': failed_id,
                  'reserve_usd': manifest['reserve_usd'],
                  'requests': [{'id': r['record_id'], 'request_sha256': r['request_sha256'],
                                'input_sha256': r['input_sha256'],
                                'instruction_sha256': r['instruction_sha256']}
                               for r in requests],
                  'p1_requests': [{'id': r['record_id'], 'request_sha256': r['request_sha256'],
                                   'input_sha256': r['input_sha256'],
                                   'instruction_sha256': r['instruction_sha256']}
                                  for r in plan['conditions']['P1']['development']]}
    if schedule_sha(projection['requests']) != REQUEST_SCHEDULE_SHA[kind]:
        raise ValueError('Original request schedule differs')
    if schedule_sha(projection['p1_requests']) != P1_REQUEST_SCHEDULE_SHA[kind]:
        raise ValueError('P1 request schedule differs')
    projected = target / 'request-projection.json'
    projected.write_text(json.dumps(projection, indent=2, sort_keys=True) + '\n')
    outputs['projection'] = {'path': str(projected.relative_to(ROOT)), 'sha256': sha(projected)}
    private = {}
    for label, base, stage in (('prefix', original, 'development'),
                               ('suffix', current, 'suffix')):
        private[label] = {name: sha(base / f'{stage}.{name}') for name in
                          ('claim.json', 'root-review.json', 'journal.jsonl',
                           'attempts.jsonl', 'responses.jsonl')}
    if p1_rows:
        private['p1'] = {name: sha(p1_dir / f'development.{name}') for name in
                         ('claim.json', 'root-review.json', 'journal.jsonl',
                          'attempts.jsonl', 'responses.jsonl')}
    export = {'schema': EXPORT_SCHEMA,
              'manual_privacy_review_required': True,
              'configuration_id': config,
              'original_plan_sha256': PLAN_SHA[kind],
              'continuation_manifest_sha256': MANIFEST_SHA[kind],
              'original_failed_id': failed_id,
              'original_prefix_valid': prefix_valid,
              'suffix_terminal': terminal,
              'suffix_saved': verified_count,
              'p1_terminal': p1_terminal,
              'p1_saved': len(p1_rows),
              'unknown_cost_upper_bound_usd': manifest['reserve_usd'],
              'private_source_sha256': private,
              'public': outputs}
    export_path = target / 'export-manifest.json'
    export_path.write_text(json.dumps(export, indent=2, sort_keys=True) + '\n')
    return {'export_manifest_sha256': sha(export_path),
            'privacy_review_schema': REVIEW_SCHEMA,
            'privacy_review_path': str((target / 'privacy-review.json').relative_to(ROOT))}


def verify_positions(kind, prefix, suffix, requests, bound_usd, terminal):
    failed_id, prefix_valid = FAILED[kind]
    count = len(prefix) + len(suffix)
    if (len(prefix) != prefix_valid + 1 or
            (terminal == 'phase_completed' and count != 60) or
            (terminal == 'phase_aborted' and not len(prefix) < count < 60) or
            [r.get('id') for r in prefix + suffix] != IDS[:count] or
            prefix[-1].get('id') != failed_id or
            any(set(r) - set(POSITION_KEYS) for r in prefix + suffix)):
        raise ValueError('Composite 60-position membership differs')
    costs = []
    tokens = Counter()
    token_counts = Counter()
    elapsed = 0.0
    for i, row in enumerate(prefix + suffix):
        expected = requests[i]
        if (row.get('request_sha256') != expected['request_sha256'] or
                row.get('input_sha256') != expected['input_sha256'] or
                row.get('instruction_sha256') != expected['instruction_sha256'] or
                row.get('reference_labels_read') is not False or
                not isinstance(row.get('attempt_id'), str) or not row['attempt_id']):
            raise ValueError('Sanitized position differs from frozen request')
        usage = row.get('usage')
        if usage is not None and (not isinstance(usage, dict) or
                set(usage) - {'cost', 'prompt_tokens', 'completion_tokens',
                              'total_tokens', 'provider_reported_reasoning_tokens'}):
            raise ValueError('Private or unexpected usage field in public position')
        elapsed += duration(row.get('elapsed_seconds'))
        if i == prefix_valid:
            if (row.get('status') != 'service_error' or
                    row.get('error_type') != 'TimeoutError' or
                    row.get('prediction') is not None or
                    row.get('observed_cost_usd') is not None or
                    row.get('cost_unknown') is not True or
                    row.get('billing_ok') is not False or
                    amount(row.get('reserved_cost_usd')) != bound_usd):
                raise ValueError('Original unknown failed attempt differs')
            continue
        if (row.get('status') != 'ok' or not valid(row.get('prediction')) or
                row.get('billing_ok') is not True or row.get('cost_unknown') is not False or
                row.get('observed_cost_usd') is None or
                amount(row['observed_cost_usd']) > amount(row.get('reserved_cost_usd')) or
                amount(row.get('reserved_cost_usd')) != bound_usd):
            raise ValueError('Known-billed valid position differs')
        costs.append(amount(row['observed_cost_usd']))
        usage = row.get('usage') or {}
        if amount(usage.get('cost')) != amount(row['observed_cost_usd']):
            raise ValueError('Provider usage cost differs from observed charge')
        for key in ('prompt_tokens', 'completion_tokens', 'total_tokens',
                    'provider_reported_reasoning_tokens'):
            value = usage.get(key)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError('Invalid provider-reported token count')
            if type(value) is int and value >= 0:
                tokens[key] += value
                token_counts[key] += 1
    if len({r['attempt_id'] for r in prefix + suffix}) != count:
        raise ValueError('Duplicate attempt identifier in composite')
    return costs, tokens, token_counts, elapsed


def score(rows_, labels):
    valid_rows = [r for r in rows_ if r['status'] == 'ok']
    fields = {key: sum(r['prediction'][key] == labels[r['id']][key]
                       for r in valid_rows) for key in FIELDS}
    all_four = sum(all(r['prediction'][key] == labels[r['id']][key]
                       for key in FIELDS) for r in valid_rows)
    return {'denominator': 60, 'valid': len(valid_rows), 'serviceErrors': 1,
            'invalidOutputs': 0, 'neverSent': 0, 'allFour': all_four,
            'fields': fields}


def verify_p1(rows_, requests, bound_usd, terminal):
    count = len(rows_)
    if (terminal == 'not_dispatched' and count == 0):
        return None
    if (terminal not in ('phase_aborted', 'phase_completed') or
            not 0 < count <= 60 or
            (terminal == 'phase_completed' and count != 60) or
            (terminal == 'phase_aborted' and count == 60) or
            [r.get('id') for r in rows_] != IDS[:count] or
            len({r.get('attempt_id') for r in rows_}) != count):
        raise ValueError('P1 saved membership or terminal state differs')
    charges = []
    seconds = 0.0
    for row, request in zip(rows_, requests):
        if (set(row) - set(POSITION_KEYS) or
                row.get('request_sha256') != request['request_sha256'] or
                row.get('input_sha256') != request['input_sha256'] or
                row.get('instruction_sha256') != request['instruction_sha256'] or
                row.get('reference_labels_read') is not False or
                row.get('status') != 'ok' or not valid(row.get('prediction')) or
                row.get('billing_ok') is not True or
                row.get('cost_unknown') is not False or
                amount(row.get('reserved_cost_usd')) != bound_usd or
                amount(row.get('observed_cost_usd')) > bound_usd):
            raise ValueError('P1 known-billed position differs')
        usage = row.get('usage') or {}
        if (not isinstance(usage, dict) or
                set(usage) - {'cost', 'prompt_tokens', 'completion_tokens',
                              'total_tokens', 'provider_reported_reasoning_tokens'} or
                amount(usage.get('cost')) != amount(row['observed_cost_usd'])):
            raise ValueError('P1 public usage or charge differs')
        seconds += duration(row.get('elapsed_seconds'))
        charges.append(amount(row['observed_cost_usd']))
    return {'status': ('completed_separate_stage' if terminal == 'phase_completed'
                       else 'aborted_unscored'),
            'saved': count, 'validSaved': count, 'neverSent': 60 - count,
            'neverSentIds': IDS[count:],
            'knownObservedDevelopmentCostUsd': str(sum(charges, Decimal(0))),
            'clientRequestToRecordSeconds': seconds,
            'score': None}


def build(root=ROOT):
    """Verify a manually reviewed public export from a clean snapshot root."""
    root = Path(root).resolve(strict=True)
    bindings = []
    parser = bind(root, Path('scripts') / Path(__file__).name, bindings)
    if sha(parser) != sha(__file__):
        raise ValueError('Snapshot reporter source differs from loaded parser')
    label_rows = rows(bind(root, LABELS, bindings, LABEL_SHA))
    if ([row.get('id') for row in label_rows] != IDS or
            any(row.get('review_version') != '0.2' or
                not valid(row.get('proposed_labels')) for row in label_rows)):
        raise ValueError('Provisional reference labels differ')
    labels = {row['id']: row['proposed_labels'] for row in label_rows}
    result = {}
    for kind in ('medium', 'xhigh'):
        directory = CONT / kind / 'public-evidence-v1'
        exported = bind(root, directory / 'export-manifest.json', bindings)
        export = json.loads(exported.read_text())
        review_file = bind(root, directory / 'privacy-review.json', bindings)
        review = json.loads(review_file.read_text())
        if (review.get('schema') != REVIEW_SCHEMA or review.get('approved') is not True or
                review.get('export_manifest_sha256') != sha(exported) or
                not isinstance(review.get('reviewer'), str) or not review['reviewer'].strip()):
            raise ValueError('Public privacy review is absent or unbound')
        failed_id, prefix_valid = FAILED[kind]
        p1_terminal = export.get('p1_terminal')
        expected_public = ({'prefix', 'suffix', 'projection', 'p1'}
                           if p1_terminal in ('phase_aborted', 'phase_completed')
                           else {'prefix', 'suffix', 'projection'})
        if (export.get('schema') != EXPORT_SCHEMA or
                export.get('manual_privacy_review_required') is not True or
                export.get('configuration_id') != 'openrouter-paid-qwen3.8-27b-' + kind or
                export.get('original_plan_sha256') != PLAN_SHA[kind] or
                export.get('continuation_manifest_sha256') != MANIFEST_SHA[kind] or
                export.get('original_failed_id') != failed_id or
                export.get('original_prefix_valid') != prefix_valid or
                export.get('unknown_cost_upper_bound_usd') != '0.047001600' or
                export.get('suffix_terminal') not in ('phase_completed', 'phase_aborted') or
                type(export.get('suffix_saved')) is not int or
                p1_terminal not in ('not_dispatched', 'phase_aborted', 'phase_completed') or
                type(export.get('p1_saved')) is not int or
                set(export.get('public', {})) != expected_public):
            raise ValueError('Public export identity differs')
        private = export.get('private_source_sha256') or {}
        expected_private = ({'prefix', 'suffix', 'p1'} if 'p1' in expected_public
                            else {'prefix', 'suffix'})
        if (set(private) != expected_private or
                set(private['prefix']) != {'claim.json', 'root-review.json',
                    'journal.jsonl', 'attempts.jsonl', 'responses.jsonl'} or
                set(private['suffix']) != set(private['prefix']) or
                ('p1' in private and set(private['p1']) != set(private['prefix'])) or
                any(private['prefix'].get(key) != value for key, value in
                    PREFIX_PRIVATE_SHA[kind].items()) or
                any(not isinstance(value, str) or len(value) != 64 or
                    any(char not in '0123456789abcdef' for char in value)
                    for part in private.values() for value in part.values())):
            raise ValueError('Private source attestation differs')
        sources = {}
        for name, descriptor in export['public'].items():
            expected_path = directory / (name + '.positions.jsonl' if name != 'projection'
                                         else 'request-projection.json')
            if descriptor.get('path') != str(expected_path):
                raise ValueError('Public export path differs')
            sources[name] = bind(root, expected_path, bindings, descriptor.get('sha256'))
        projection = json.loads(sources['projection'].read_text())
        requests = projection.get('requests')
        p1_requests = projection.get('p1_requests')
        if (projection.get('schema') != EXPORT_SCHEMA + '-request-projection' or
                projection.get('configuration_id') != export['configuration_id'] or
                projection.get('original_plan_sha256') != PLAN_SHA[kind] or
                projection.get('continuation_manifest_sha256') != MANIFEST_SHA[kind] or
                projection.get('series_id') != 'qwen27-v2-interrupted-continuation-v1-' + kind or
                projection.get('clean_matched_three_eligible') is not False or
                projection.get('reference_labels_read') is not False or
                projection.get('failed_id') != failed_id or
                projection.get('reserve_usd') != '0.047001600' or
                not isinstance(requests, list) or len(requests) != 60 or
                [r.get('id') for r in requests] != IDS or
                schedule_sha(requests) != REQUEST_SCHEDULE_SHA[kind] or
                not isinstance(p1_requests, list) or len(p1_requests) != 60 or
                [r.get('id') for r in p1_requests] != IDS or
                schedule_sha(p1_requests) != P1_REQUEST_SCHEDULE_SHA[kind]):
            raise ValueError('Public request projection differs')
        prefix, suffix = rows(sources['prefix']), rows(sources['suffix'])
        if len(suffix) != export['suffix_saved']:
            raise ValueError('Attested suffix count differs')
        costs, tokens, present, seconds = verify_positions(
            kind, prefix, suffix, requests, Decimal(projection['reserve_usd']),
            export['suffix_terminal'])
        completed = export['suffix_terminal'] == 'phase_completed'
        scored = score(prefix + suffix, labels) if completed else None
        p1_rows = rows(sources['p1']) if 'p1' in sources else []
        if len(p1_rows) != export['p1_saved']:
            raise ValueError('Attested P1 saved count differs')
        later_p1 = verify_p1(p1_rows, p1_requests,
                             Decimal(projection['reserve_usd']), p1_terminal)
        if later_p1 is None:
            later_p1 = {'status': 'not_dispatched', 'saved': 0,
                        'neverSent': 60, 'neverSentIds': IDS, 'score': None}
        elif p1_terminal == 'phase_completed':
            p1_score = score(p1_rows, labels)
            p1_score['serviceErrors'] = 0
            later_p1['score'] = p1_score
        result[kind] = {'configurationId': export['configuration_id'],
                        'condition': 'P0', 'freshPass': 'fresh3',
                        'status': ('completed_interrupted_prefix_plus_suffix' if completed
                                   else 'aborted_suffix_unscored'),
                        'cleanMatchedThreeEligible': False,
                        'originalFailedId': failed_id,
                        'originalNeverSentBeforeContinuation': IDS[prefix_valid + 1:],
                        'suffixSaved': len(suffix),
                        'validSaved': prefix_valid + len(suffix),
                        'neverSentAfterContinuation': IDS[len(prefix) + len(suffix):],
                        'score': scored,
                        'knownObservedDevelopmentCostUsd': str(sum(costs, Decimal(0))),
                        'unknownCostUpperBoundUsd': str(Decimal(projection['reserve_usd'])),
                        'clientRequestToRecordSeconds': seconds,
                        'timingKind': 'client_request_to_record_not_pure_inference',
                        'tokenAvailabilityScope': 'saved_attempts_only',
                        'tokens': {key: {'sum': tokens[key], 'reportedCount': present[key],
                                         'missingCount': len(prefix) + len(suffix) - present[key]}
                                   for key in ('prompt_tokens', 'completion_tokens', 'total_tokens',
                                               'provider_reported_reasoning_tokens')},
                        'laterP1': later_p1}
    return {'schema': SCHEMA, 'method': 'descriptive-interrupted-series-continuation',
            'denominator': 60, 'cleanMatchedThreeEligible': False,
            'referenceStatus': 'AI-authored provisional; not independently human-adjudicated',
            'series': result, 'sourceBindings': bindings,
            'limits': ['The original failed request was not retried.',
                       'The first P0 pass combines an interrupted prefix and a separately dispatched suffix.',
                       'The unknown original charge is a bound, not observed spending.',
                       'The time is client request-to-record, not isolated inference time.',
                       'P1 is not included until its smoke and full stages close separately.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--prepare-export', choices=('medium', 'xhigh'),
                        help='private read-only verification followed by a new sanitized candidate export')
    parser.add_argument('--export-destination', type=Path)
    args = parser.parse_args(argv)
    if args.prepare_export:
        if args.root.resolve() != ROOT.resolve() or args.output or args.check:
            raise ValueError('Private export requires the original checkout and no report output')
        print(json.dumps(prepare_export(args.prepare_export, args.export_destination),
                         sort_keys=True))
        return
    if args.export_destination:
        raise ValueError('Export destination requires --prepare-export')
    report = build(args.root)
    content = json.dumps(report, indent=2, sort_keys=True) + '\n'
    if args.check:
        if args.output is None or args.output.read_text() != content:
            raise ValueError('Public Qwen27 interruption report differs from bound evidence')
    elif args.output:
        args.output.write_text(content)
    else:
        print(content, end='')


if __name__ == '__main__':
    main()
