#!/usr/bin/env python3
"""Offline reconciliation of the stopped Gemini billing-default continuation."""
import hashlib
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import gemini_billing_continuation as amended
import gemini_prompt_execution_v2 as frozen
from development_benchmark import read_rows

BASE = amended.AMEND
FIRST = amended.FIRST
CONDITION = 'P1'


def bound(path):
    path = Path(path).resolve()
    return {'file': str(path.relative_to(ROOT.resolve())), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def lines(path): return [json.loads(x) for x in path.read_text().splitlines()]


def stage(manifest, item, name):
    directory = ROOT / item['conditions'][CONDITION][name + '_output']
    directory = directory.parent
    paths = {key: directory / filename for key, filename in {
        'predictions': name + '.jsonl', 'attempts': name + '-attempts.jsonl',
        'events': name + '-attempts.events.jsonl', 'terminal': name + '.terminal.json',
        'billing_audit': name + '-billing-audit.jsonl'}.items()}
    attempts, predictions, events, billing = (lines(paths[k]) for k in ('attempts', 'predictions', 'events', 'billing_audit'))
    terminal = json.loads(paths['terminal'].read_text())
    preview = json.loads((ROOT / item['conditions'][CONDITION][name + '_preview']['file']).read_text())
    selected = read_rows(ROOT / manifest['inputs']['file'])[:3 if name == 'smoke' else 60]
    assert [r['id'] for r in selected] == [f'DEV-{i:03}' for i in range(1, len(selected) + 1)]
    assert len(attempts) == (1 if name == 'smoke' else 5)
    assert len(preview['requests']) == (1 if name == 'smoke' else 6)
    assert len(predictions) == sum(len(a['record_order']) for a in attempts)
    assert len(events) == 2 * len(attempts)
    for i, (attempt, request) in enumerate(zip(attempts, preview['requests'])):
        group = selected[10*i:10*i+10]
        assert attempt['record_order'] == request['record_ids'] == [r['id'] for r in group]
        assert attempt['request'] == request['request']
        assert attempt['request_sha256'] == request['request_sha256']
        assert attempt['schema_sha256'] == request['schema_sha256']
        assert attempt['prompt_variant'] == request['prompt_variant']
        assert attempt['requested_model'] == item['model']
        assert attempt['cli_version'] == '1.2.10'
        assert attempt['cli_binary_sha256'] == manifest['cli']['sha256']
        assert attempt['reference_labels_read'] is False
        assert attempt['billing_audit']['useG1Credits'] is False
        strict = frozen.strict_response(attempt['raw_stdout'], attempt['raw_stderr'],
            attempt['returncode'], item['model'], group)
        assert strict['status'] == attempt['status']
        assert strict['predictions'] == attempt['predictions']
        assert not attempt['observed_tool_items']
        for position, source in enumerate(group):
            row = predictions[10*i+position]
            assert row['id'] == source['id']
            assert row['status'] == attempt['status']
            assert row['prediction'] == strict['predictions'].get(source['id'])
            assert row['request_sha256'] == request['request_sha256']
            assert row['reference_labels_read'] is False
        assert events[2*i]['event'] == 'request_started'
        assert events[2*i+1]['event'] == 'request_completed'
        assert events[2*i+1]['status'] == attempt['status']
    expected_kinds = ['version', 'models'] + ['inference']*len(attempts)
    assert len(billing) == 2*len(expected_kinds)
    for i, kind in enumerate(expected_kinds):
        before, after = billing[2*i:2*i+2]
        assert before['event'] == 'cli_started' and after['event'] == 'cli_finished'
        assert before['kind'] == after['kind'] == kind
        assert before['before']['useG1Credits'] is False and after['after']['useG1Credits'] is False
        assert before['before']['observed_setting'] == after['after']['observed_setting'] == 'absent_documented_default_false'
        assert len(before['before']['settings_sha256']) == len(after['after']['settings_sha256']) == 64
        assert 'after_error_type' not in after
    assert terminal['manifest'] == bound(amended.MANIFEST)
    assert terminal['records_saved'] == len(predictions)
    assert terminal['expected'] == len(selected)
    return paths, attempts, predictions, terminal


def build():
    manifest = json.loads(amended.MANIFEST.read_text())
    amended.verify_manifest(manifest)
    item = manifest['configurations'][0]
    smoke_paths, smoke_attempts, smoke_rows, smoke_terminal = stage(manifest, item, 'smoke')
    development_paths, attempts, rows, terminal = stage(manifest, item, 'development')
    assert (smoke_terminal['status'], len(smoke_attempts), len(smoke_rows)) == ('completed', 1, 3)
    assert all(r['status'] == 'ok' for r in smoke_rows)
    assert (terminal['status'], len(attempts), len(rows)) == ('stopped', 5, 50)
    assert [a['status'] for a in attempts] == ['ok']*4 + ['service_error']
    assert [r['id'] for r in rows] == [f'DEV-{i:03}' for i in range(1, 51)]
    assert all(r['status'] == 'ok' for r in rows[:40])
    assert all(r['status'] == 'service_error' and r['prediction'] is None for r in rows[40:])
    failed = attempts[-1]
    assert failed['returncode'] == 3
    assert any(e.get('event') == 'result' and e.get('result', {}).get('status') == 'ERROR' for e in failed['raw_events'])
    assert 'RESOURCE_EXHAUSTED' in failed['raw_stderr'] and 'Individual quota reached' in failed['raw_stderr']
    reset = re.search(r'Resets in (\d+)h(\d+)m(\d+)s', failed['raw_stderr'])
    assert reset and reset.groups() == ('143', '52', '47')
    finished = datetime.fromisoformat(failed['finished_utc'])
    estimate = finished + timedelta(hours=143, minutes=52, seconds=47)
    continuation_events = lines(amended.CONTINUATION_JOURNAL)
    order = amended.prompt_schedule._schedule(manifest['schedule'], ROOT)
    amended.prompt_schedule._replay(continuation_events, manifest['schedule'], order, ROOT)
    claims = [e for e in continuation_events if e['event'] == 'claimed']
    finishes = [e for e in continuation_events if e['event'] == 'finished']
    assert [e['stage'] for e in claims] == ['smoke', 'inspected_admission', 'development']
    assert [e['status'] for e in finishes] == ['completed', 'completed', 'stopped']
    original_finish = amended.verify_zero_request(manifest)
    global_events = lines(amended.GLOBAL_JOURNAL)
    other = []
    for config in manifest['configurations']:
        for condition in ('P1','P2'):
            if (config['configuration_id'],condition) == (FIRST,CONDITION):continue
            _, journal = amended.route(manifest, config['configuration_id'], condition)
            assert journal == amended.GLOBAL_JOURNAL
            outputs = config['conditions'][condition]
            assert all(not (ROOT/outputs[phase+'_output']).exists() for phase in ('smoke','development'))
            assert not any(e.get('event')=='claimed' and e.get('configuration_id')==config['configuration_id'] and e.get('condition')==condition for e in global_events)
            other.append(config['configuration_id']+'/'+condition)
    assert len(other)==13
    inspection = smoke_paths['predictions'].with_name('smoke-inspection.json')
    assert inspection.exists()
    underlying = {k:v for k,v in manifest.items() if k not in ('continuation','billing_amendment')}
    underlying['contract']='gemini-exact-draft-v2'
    prior = frozen.MANIFEST
    try:
        frozen.MANIFEST = amended.MANIFEST
        frozen.inspect_smoke(underlying,item,CONDITION,inspection,bound(inspection)['sha256'])
    finally:frozen.MANIFEST=prior
    usage_fields=('input_tokens','output_tokens','thinking_tokens','cache_read_tokens','total_tokens')
    development_usage={k:sum(a.get('usage',{}).get(k,0) for a in attempts if a['status']=='ok') for k in usage_fields}
    source_paths=[amended.MANIFEST,amended.PREFLIGHT,BASE/'root-review.json',inspection,
        amended.CONTINUATION_JOURNAL,ROOT/'scripts/gemini_billing_continuation.py',
        ROOT/'scripts/gemini_prompt_execution_v2.py',ROOT/'scripts/reconcile_gemini_billing_partial.py',
        ROOT/manifest['continuation']['stopped_terminal']['file']]
    source_paths.extend(smoke_paths.values());source_paths.extend(development_paths.values())
    artifact={'contract':'gemini-billing-default-partial-reconciliation-v1',
        'created_utc':datetime.now(timezone.utc).isoformat(),
        'configuration_id':FIRST,'condition':'P1','canonical_development_denominator':60,
        'development':{'valid_ok':40,'service_error':10,'unattempted':10,'last_attempted_id':'DEV-050',
            'first_unattempted_id':'DEV-051','attempted_batches':5,'planned_batches':6,
            'stage_terminal':'stopped','successful_batch_usage':development_usage,
            'failed_batch_reported_usage':failed.get('usage'),
            'failed_batch_backend_charge':'not_exposed'},
        'smoke':{'records':3,'status':'completed','all_ok':True,'excluded_from_development_denominator':True,
            'reported_usage':smoke_attempts[0].get('usage'),'inspection':bound(inspection)},
        'failure':{'class':'service_error','provider_status':'RESOURCE_EXHAUSTED','http_code':429,
            'native_cli_returncode':3,'native_reset_hint':'143h52m47s',
            'native_attempt_finished_utc':failed['finished_utc'],
            'estimated_reset_utc_from_finish_time':estimate.isoformat(),
            'reset_estimate_limit':'Provider hint is relative and may have been emitted before saved finish time; not a guaranteed reset time.',
            'controller_retry_count':0,'native_internal_retry_count':'not_exposed'},
        'billing':{'credit_fallback_observed':'absent_documented_default_false before and after every CLI call',
            'default_source':amended.DEFAULT_SOURCE,'backend_billing_receipts':'not_exposed',
            'smoke_audited_cli_calls':3,'development_audited_cli_calls':7},
        'workflow':{'native_cli_version':'1.2.10','observed_external_tool_or_delegation_calls':0,
            'available_builtin_tools':len(attempts[0].get('available_tools') or []),
            'effective_tool_restriction':'unverified','model_revision':'not_exposed'},
        'schedule':{'original_zero_request_finished_event_sha256':original_finish,
            'continuation_stages':['smoke:completed','inspected_admission:completed','development:stopped'],
            'other_scheduled_conditions_unattempted':other},
        'reference_labels_read':False,
        'source_bindings':[bound(p) for p in source_paths]}
    return artifact


if __name__ == '__main__':
    path=BASE/'partial-reconciliation.json'
    with path.open('x') as stream:
        json.dump(build(),stream,indent=2);stream.write('\n')
    print(path)
