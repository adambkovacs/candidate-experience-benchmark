#!/usr/bin/env python3
"""Check and summarize the two stopped Qwen27 fresh3/P0 phases offline."""
import argparse
import base64
from collections import Counter
from contextlib import contextmanager
from decimal import Decimal
import hashlib
import json
import math
from pathlib import Path
import sys
from threading import RLock

import development_benchmark
import openrouter_paid_benchmark as paid
import openrouter_benchmark as transport
import openrouter_budget_v3 as budget_runtime
import paid_budget_partitions_v3 as partitions
import qwen27_fresh_repeat_execution_v2 as execution
import qwen27_fresh_repeat_study_v2 as study
import prompt_admission
import prompt_execution_gates
import frozen_prompt_variants
from prompt_admission import audit_response

ROOT = study.ROOT
BASE = study.BASE
ORIGIN = Path('/Users/adamkovacs/Documents/codebuild/recruitment-feedback-demo')
HOST_NOTE = Path('docs/HOST_INTERRUPTION_2026-10-01.md')
SCHEMA = 'qwen27-v2-fresh3-p0-interruption-findings-v1'
RESERVE = Decimal('0.047001600')
PLANS = {
    'medium': '99af3286e3b9d86297b4de681d5928bbdb11a9740122b72d8002cc360fae8464',
    'xhigh': '60ffa81000eb16a3e54ec2e649935cbc470de13f60e2447c48ae62f15cc3f74f',
}
STOP = {'medium': (22, 21, 38), 'xhigh': (37, 36, 23)}
_BUILD_LOCK = RLock()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind(path, root=None):
    path = Path(path).resolve()
    return {'path': str(path.relative_to(Path(root or ROOT).resolve())), 'sha256': sha(path)}


@contextmanager
def snapshot(root):
    """Read a relocated snapshot with trusted local parser code, restoring globals."""
    target = Path(root or ROOT).resolve(strict=True)
    source_files = {'reporter': Path(__file__), 'planner': Path(study.__file__),
                    'controller': Path(execution.__file__), 'paid_adapter': Path(paid.__file__),
                    'transport': Path(transport.__file__),
                    'master_budget': Path(budget_runtime.__file__),
                    'partitions': Path(partitions.__file__),
                    'response_audit': Path(prompt_admission.__file__),
                    'response_gate': Path(prompt_execution_gates.__file__),
                    'frozen_instructions': Path(frozen_prompt_variants.__file__),
                    'development_benchmark': Path(development_benchmark.__file__)}
    for name, current in source_files.items():
        candidate = target / 'scripts' / current.name
        if sha(candidate) != sha(current):
            raise ValueError('Snapshot parser source differs: ' + name)
    changes = ((study, 'ROOT', target),
               (study, 'BASE', target / 'results/repeatability-v1' / study.SERIES),
               (study, 'ORIGINAL_BASE', target / 'results/repeatability-v1' / study.ORIGINAL_SERIES),
               (execution, 'ROOT', target),
               (execution, 'MASTER', ORIGIN / 'results/openrouter-paid-budget.jsonl'),
               (execution, 'HOSTED_EXECUTION', target / study.HOSTED),
               (execution, 'EXECUTION_MANIFEST', target / 'results/repeatability-v1' / study.SERIES / 'execution-manifest.json'),
               (sys.modules[__name__], 'ROOT', target),
               (sys.modules[__name__], 'BASE', target / 'results/repeatability-v1' / study.SERIES))
    saved = [(module, name, getattr(module, name)) for module, name, _ in changes]
    try:
        for module, name, value in changes:
            setattr(module, name, value)
        yield target
    finally:
        for module, name, value in reversed(saved):
            setattr(module, name, value)


def jsonl(path):
    data = Path(path).read_bytes()
    if data and not data.endswith(b'\n'):
        raise ValueError('Incomplete JSONL: ' + str(path))
    return [json.loads(line) for line in data.splitlines() if line.strip()]


def strict_duration(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError('Invalid client duration')
    return value


def verify_prior(plan):
    config = plan['configuration_id']
    fresh1 = study.verify(config, 'fresh1', sha(BASE / config / 'fresh1/manifest.json'))
    fresh2 = study.verify(config, 'fresh2', sha(BASE / config / 'fresh2/manifest.json'))
    for condition in study.ORDERS['fresh1']:
        execution.verify_phase_closure(fresh1, condition, 'development')
    for condition in study.ORDERS['fresh2']:
        execution.verify_phase_closure(fresh2, condition, 'development')
    execution.verify_phase_closure(plan, 'P2', 'development')
    execution.verify_phase_closure(plan, 'P0', 'smoke')


def verify_journal(journal, attempts, planned, config):
    expected = [
        ('phase_started', None, None),
    ]
    for request, record in zip(planned, attempts):
        expected.extend((('request_intent', request['record_id'], None),
                         ('request_started', request['record_id'], record['attempt_id']),
                         ('request_finished', request['record_id'], record['attempt_id'])))
    expected.append(('phase_stopped', attempts[-1]['id'], None))
    if [(e.get('event'), e.get('id'), e.get('attempt_id')) for e in journal] != expected:
        raise ValueError('Stopped journal lifecycle or request order differs')
    if (journal[0].get('configuration_id'), journal[0].get('fresh_pass'),
            journal[0].get('condition'), journal[0].get('phase')) != (
            config, 'fresh3', 'P0', 'development'):
        raise ValueError('Stopped journal identity differs')
    for index, (request, record) in enumerate(zip(planned, attempts)):
        intent, started, finished = journal[1 + 3*index:4 + 3*index]
        if (intent.get('request_sha256') != request['request_sha256'] or
                started.get('request_sha256') != request['request_sha256'] or
                finished.get('status') != record['status'] or
                finished.get('billing_ok') != record['billing_ok'] or
                finished.get('cost_unknown') != record['cost_unknown'] or
                finished.get('observed_cost_usd') != record['observed_cost_usd']):
            raise ValueError('Stopped journal attempt binding differs')
    if journal[-1].get('reason') != 'service_error':
        raise ValueError('Stopped journal terminal reason differs')


def verify_success(record, wire, request):
    if (record.get('status') != 'ok' or record.get('billing_ok') is not True or
            record.get('cost_unknown') is not False or
            record.get('reference_labels_read') is not False or
            record.get('reserved_cost_usd') != str(RESERVE) or
            record.get('response_diagnostic', {}).get('passed') is not True):
        raise ValueError('Valid prefix outcome differs')
    body = record.get('raw_response')
    if not isinstance(body, dict) or record.get('prediction') is None:
        raise ValueError('Valid prefix raw response missing')
    try:
        decoded = json.loads(base64.b64decode(wire['body_base64'], validate=True))
    except (KeyError, ValueError, TypeError):
        raise ValueError('Captured response cannot be decoded') from None
    if (wire.get('id') != record['id'] or wire.get('attempt_id') != record['attempt_id'] or
            wire.get('request_sha256') != request['request_sha256'] or
            wire.get('http_status') != 200 or
            wire.get('body_truncated_at_limit') is not False or
            wire.get('read_error') is not None or decoded != body):
        raise ValueError('Captured response differs from attempt')
    classified = execution.classify(body, record['model_catalog_entry'],
                                    record['provider_endpoint'])
    if any(record.get(key) != value for key, value in classified.items()):
        raise ValueError('Saved prediction differs from reparsed raw response')
    actual = paid.number(record.get('observed_cost_usd'))
    if (actual > RESERVE or paid.number((body.get('usage') or {}).get('cost')) != actual or
            record['response_diagnostic'] != audit_response(
                record, 'openrouter_paid_v1',
                record['provider_endpoint']['context_length'] - 4096)):
        raise ValueError('Valid response charge or diagnostics differ')
    usage = body['usage']
    counts = {}
    for key in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
        value = usage.get(key)
        if type(value) is not int or value < 0:
            raise ValueError('Valid response token count differs')
        counts[key] = value
    return actual, counts, strict_duration(record.get('elapsed_seconds'))


def verify_child(config, folder, attempts, reconciliation, sources):
    partition = 'qwen27-' + config.rsplit('-', 1)[-1] + '-v2'
    budget_path = BASE / 'budget-partitions-v1.json'
    budget = json.loads(budget_path.read_text())
    original_master = ORIGIN / 'results/openrouter-paid-budget.jsonl'
    if budget.get('master_ledger') != str(original_master):
        raise ValueError('Frozen original master ledger identity differs')
    entries = [entry for entry in budget.get('partitions', []) if entry.get('id') == partition]
    if len(entries) != 1:
        raise ValueError('Missing exact child budget partition')
    entry = entries[0]
    relative_child = Path('results/repeatability-v1') / study.SERIES / (
        'budget-partitions-v1-' + partition + '.jsonl')
    original_child = ORIGIN / relative_child
    if entry.get('child_ledger') != str(original_child):
        raise ValueError('Frozen original child ledger identity differs')
    child = ROOT / relative_child
    events = jsonl(child)
    sources['child_ledger'] = bind(child)
    sources['budget_manifest'] = bind(budget_path)
    sources['terminal_reconciliation'] = bind(folder / 'terminal-reconciliation.json')
    if (entry.get('model'), entry.get('provider'), entry.get('reasoning')) != (
            study.MODEL, study.PROVIDER, study.CONFIGS[config]['effort']):
        raise ValueError('Child route or reasoning differs')
    if (not events or events[0] != {'event': 'budget', 'cap_usd': entry['cap_usd']} or
            events[-1].get('event') != 'partition_closed'):
        raise ValueError('Child budget not sealed')
    reserves = [event for event in events if event.get('event') == 'reserve']
    if len(reserves) < len(attempts):
        raise ValueError('Child reservations omit stopped stage')
    tail = reserves[-len(attempts):]
    if [(e.get('attempt_id'), e.get('record_id'), e.get('usd')) for e in tail] != [
            (r['attempt_id'], r['id'], str(RESERVE)) for r in attempts]:
        raise ValueError('Stopped attempts differ from child reservations')
    by_attempt = {}
    for event in events:
        attempt = event.get('attempt_id')
        if attempt:
            by_attempt.setdefault(attempt, []).append(event)
    for record in attempts[:-1]:
        matched = by_attempt[record['attempt_id']]
        if len(matched) != 2 or matched[1] != {
                'event': 'settle', 'attempt_id': record['attempt_id'],
                'usd': record['observed_cost_usd']}:
            raise ValueError('Valid attempt child settlement differs')
    failed = attempts[-1]
    matched = by_attempt[failed['attempt_id']]
    if (len(matched) != 2 or matched[1].get('event') !=
            'unknown_cost_accounted_as_upper_bound' or
            paid.number(matched[1].get('usd')) != RESERVE or
            matched[1].get('actual_cost_usd') is not None or
            matched[1].get('evidence_sha256') != sources['development_attempts']['sha256'] or
            matched[1].get('evidence_path') != str(
                ORIGIN / Path('results/repeatability-v1') / study.SERIES /
                config / 'fresh3/P0/development.attempts.jsonl')):
        raise ValueError('Unknown failed charge was not retained at full bound')
    known = sum((paid.number(e['usd']) for e in events if e.get('event') == 'settle'), Decimal(0))
    unknown = sum((paid.number(e['usd']) for e in events if
                   e.get('event') == 'unknown_cost_accounted_as_upper_bound'), Decimal(0))
    cap = paid.number(entry['cap_usd'])
    expected = {'event': 'partition_reconciled', 'partition_id': partition,
                'known_actual_usd': str(known), 'unknown_upper_bound_usd': str(unknown),
                'unused_allocation_released_usd': str(cap - known - unknown),
                'child_ledger': str(original_child), 'child_sha256': sha(child)}
    if (known + unknown > cap or reconciliation != expected):
        raise ValueError('Terminal reconciliation differs from sealed child')
    master = jsonl(ROOT / 'results/openrouter-paid-budget.jsonl')
    if expected not in master:
        raise ValueError('Master reconciliation event missing')
    return {'capUsd': str(cap), 'knownActualAllStagesUsd': str(known),
            'unknownUpperBoundAllStagesUsd': str(unknown),
            'unusedAllocationReleasedUsd': str(cap - known - unknown)}


def _build():
    sources = {}
    for key, path in {'planner': ROOT / 'scripts' / Path(study.__file__).name,
                      'controller': ROOT / 'scripts' / Path(execution.__file__).name,
                      'reporter': ROOT / 'scripts' / Path(__file__).name,
                      'host_note': ROOT / HOST_NOTE}.items():
        sources[key] = bind(path)
    result = {}
    for suffix, plan_sha in PLANS.items():
        config = 'openrouter-paid-qwen3.8-27b-' + suffix
        plan = study.verify(config, 'fresh3', plan_sha)
        verify_prior(plan)
        folder = BASE / config / 'fresh3/P0'
        files = {'plan': BASE / config / 'fresh3/manifest.json',
                 'smoke_review': folder / 'smoke.root-review.json',
                 'smoke_claim': folder / 'smoke.claim.json',
                 'smoke_journal': folder / 'smoke.journal.jsonl',
                 'smoke_attempts': folder / 'smoke.attempts.jsonl',
                 'smoke_responses': folder / 'smoke.responses.jsonl',
                 'smoke_inspection': folder / 'smoke-inspection.json',
                 'development_review': folder / 'development.root-review.json',
                 'development_claim': folder / 'development.claim.json',
                 'development_journal': folder / 'development.journal.jsonl',
                 'development_attempts': folder / 'development.attempts.jsonl',
                 'development_responses': folder / 'development.responses.jsonl'}
        bound = {name: bind(path) for name, path in files.items()}
        for name, item in bound.items():
            sources[suffix + '_' + name] = item
        receipt, _ = execution.review_receipt(files['development_review'], config,
                'fresh3', 'P0', 'development', plan_sha)
        if receipt.get('stage') != 'fresh3/P0/development':
            raise ValueError('Development review stage differs')
        claim = json.loads(files['development_claim'].read_text())
        if (claim.get('series_id'), claim.get('configuration_id'),
                claim.get('fresh_pass'), claim.get('condition'), claim.get('phase'),
                claim.get('manifest_sha256'), claim.get('root_review_sha256')) != (
                plan['series_id'], config, 'fresh3', 'P0', 'development', plan_sha,
                bound['development_review']['sha256']):
            raise ValueError('Stopped phase claim differs')
        attempts = jsonl(files['development_attempts'])
        raw = jsonl(files['development_responses'])
        journal = jsonl(files['development_journal'])
        failed_number, valid_count, unsent_count = STOP[suffix]
        requests = plan['conditions']['P0']['development']
        if ([x.get('id') for x in attempts] != [r['record_id'] for r in requests[:failed_number]] or
                [x.get('id') for x in raw] != [r['record_id'] for r in requests[:valid_count]] or
                len(requests) != 60 or valid_count + 1 + unsent_count != 60 or
                len({x.get('attempt_id') for x in attempts}) != failed_number or
                any(x.get('reference_labels_read') is not False for x in attempts)):
            raise ValueError('Stopped phase attempted, raw or unsent membership differs')
        audit, _ = study.historical_data(config)
        _, historical, _ = study.source_rows(audit, 'P0')
        frozen_endpoint = historical['DEV-001']['provider_endpoint']
        frozen_model_entry = historical['DEV-001']['model_catalog_entry']
        route_keys = ('tag', 'provider_name', 'quantization', 'model_id',
                      'context_length', 'max_prompt_tokens',
                      'max_completion_tokens', 'supported_parameters', 'pricing')
        for request, record in zip(requests, attempts):
            if (record.get('request') != request['payload'] or
                    record.get('request_sha256') != request['request_sha256'] or
                    record.get('input_sha256') != request['input_sha256'] or
                    record.get('instruction_sha256') != request['instruction_sha256'] or
                    record.get('manifest_sha256') != plan_sha or
                    record.get('configuration_id') != config or
                    record.get('fresh_pass') != 'fresh3' or
                    record.get('condition') != 'P0' or
                    record.get('phase') != 'development' or
                    any(record.get('provider_endpoint', {}).get(key) != frozen_endpoint.get(key)
                        for key in route_keys) or
                    record.get('model_catalog_entry') != frozen_model_entry):
                raise ValueError('Attempt differs from frozen P0 request')
        verify_journal(journal, attempts, requests[:failed_number], config)
        costs, durations = [], []
        tokens = Counter()
        for record, wire, request in zip(attempts[:-1], raw, requests):
            actual, counts, elapsed = verify_success(record, wire, request)
            costs.append(actual); durations.append(elapsed); tokens.update(counts)
        failed = attempts[-1]
        if (failed.get('id') != f'DEV-{failed_number:03d}' or
                failed.get('status') != 'service_error' or
                failed.get('error_type') != 'TimeoutError' or
                failed.get('billing_ok') is not False or
                failed.get('cost_unknown') is not True or
                failed.get('observed_cost_usd') is not None or
                failed.get('reserved_cost_usd') != str(RESERVE) or
                'raw_response' in failed or 'prediction' in failed):
            raise ValueError('Failed attempt outcome or unknown cost differs')
        stopped_seconds = strict_duration(failed.get('elapsed_seconds'))
        accounting = verify_child(config, folder, attempts,
                                  json.loads((folder / 'terminal-reconciliation.json').read_text()),
                                  bound)
        sources.update({suffix + '_' + k: v for k, v in bound.items()
                        if k in ('budget_manifest', 'child_ledger', 'terminal_reconciliation')})
        result[suffix] = {
            'configurationId': config, 'freshPass': 'fresh3', 'condition': 'P0',
            'status': 'stopped_transport_unknown', 'strictCompletePass': False,
            'denominator': 60, 'valid': valid_count, 'attemptedUnknown': 1,
            'neverSent': unsent_count, 'failedId': failed['id'],
            'neverSentIds': [r['record_id'] for r in requests[failed_number:]],
            'score': None, 'knownObservedStageCostUsd': str(sum(costs, Decimal(0))),
            'unknownStageCostUpperBoundUsd': str(RESERVE),
            'budget': accounting,
            'tokens': {'promptKnownValid': tokens['prompt_tokens'],
                       'completionKnownValid': tokens['completion_tokens'],
                       'totalKnownValid': tokens['total_tokens'],
                       'failedRequestUsage': None},
            'timing': {'validClientRequestToRecordSeconds': {
                'sum': sum(durations), 'min': min(durations), 'max': max(durations)},
                'failedClientRequestToRecordSeconds': stopped_seconds,
                'pureInferenceSeconds': None},
        }
    return {'schema': SCHEMA, 'series': result, 'sourceBindings': sources,
            'interpretation': 'Two stopped fresh3/P0 passes; no 60-record score or clean matched-three result.',
            'hostRelation': 'Cause of hosted timeouts is undetermined; see bound host note.'}


def build(snapshot_root=None):
    """Authoritative internal verification, including private partition accounting."""
    with _BUILD_LOCK:
        with snapshot(snapshot_root):
            return _build()


def build_public(snapshot_root=None):
    """Verified public summary; omit child allocation and released quota figures."""
    report = build(snapshot_root)
    for series in report['series'].values():
        series.pop('budget')
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, help='Committed snapshot root to verify')
    format_group = parser.add_mutually_exclusive_group()
    format_group.add_argument('--public', action='store_true',
                              help='public summary (the default)')
    format_group.add_argument('--internal', action='store_true',
                              help='include private partition cap and released quota')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    content = json.dumps((build if args.internal else build_public)(args.root),
                         indent=2, sort_keys=True) + '\n'
    if args.output is None:
        print(content, end='')
    elif args.check:
        if not args.output.exists() or args.output.read_text() != content:
            raise ValueError('Stale Qwen27 interruption report: ' + str(args.output))
    else:
        args.output.write_text(content)


if __name__ == '__main__':
    main()
