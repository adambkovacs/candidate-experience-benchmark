#!/usr/bin/env python3
"""Versioned billing-default amendment around the frozen Gemini v2 controller."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import gemini_prompt_execution_v2 as frozen
import gemini_batch_benchmark as native
import prompt_schedule

BASE = ROOT / 'results/prompt-comparison-v1-2026-09-24/gemini-exact-v2'
AMEND = BASE / 'billing-default-continuation-v1'
MANIFEST = AMEND / 'execution-manifest.draft.json'
PREFLIGHT = AMEND / 'preflight.json'
GLOBAL_JOURNAL = ROOT / 'results/prompt-comparison-v1-2026-09-24/execution-journal.jsonl'
CONTINUATION_JOURNAL = AMEND / 'execution-journal.jsonl'
FIRST = 'antigravity-gemini-3.1-pro-low-native-observed-batch10'
DEFAULT_SOURCE = 'https://www.antigravity.google/docs/cli/reference/'
GUIDE_SOURCE = 'https://www.antigravity.google/docs/cli/credits/'


def sha(raw): return hashlib.sha256(raw).hexdigest()
def utc(): return datetime.now(timezone.utc).isoformat()
def bind(path):
    path = Path(path).resolve()
    return {'file': str(path.relative_to(ROOT.resolve())), 'sha256': sha(path.read_bytes())}
def json_bound(spec):
    if set(spec) != {'file', 'sha256'} or bind(ROOT / spec['file']) != spec:
        raise ValueError('Amendment source binding changed')
    return json.loads((ROOT / spec['file']).read_text())
def load_hash(path, expected):
    if sha(Path(path).read_bytes()) != expected: raise ValueError('Frozen hash mismatch: ' + str(path))
    return json.loads(Path(path).read_text())
def write_exclusive(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(value, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())


def billing_state(home):
    """Official 1.2.10 default is false; any explicit non-false value stops."""
    path = Path(home) / '.gemini/antigravity-cli/settings.json'
    raw = path.read_bytes(); settings = json.loads(raw)
    if not isinstance(settings, dict) or settings.get('modelProvider') not in (None, '', 'antigravity'):
        raise RuntimeError('Native Antigravity subscription provider required')
    if 'useG1Credits' not in settings:
        observed = 'absent_documented_default_false'
    elif settings['useG1Credits'] is False:
        observed = 'explicit_false'
    else:
        raise RuntimeError('AI credit fallback setting is not effectively false')
    return {'useG1Credits': False, 'effective_credit_fallback': False,
        'observed_setting': observed, 'settings_sha256': sha(raw),
        'provider': settings.get('modelProvider') or 'antigravity',
        'default_source': DEFAULT_SOURCE}


class NativeProxy:
    def __getattr__(self, name): return getattr(native, name)
    @staticmethod
    def require_credits_off(home): return billing_state(home)


class ProcessProxy:
    """Audit CLI setting state before and after every native command, without prompts."""
    def __init__(self, executable, home, audit_stream, run=subprocess.run):
        self.executable = executable
        self.home = Path(home)
        self.audit_stream = audit_stream
        self.real_run = run
    def __getattr__(self, name): return getattr(subprocess, name)
    def _record(self, event):
        self.audit_stream.write(json.dumps(event) + '\n')
        self.audit_stream.flush(); os.fsync(self.audit_stream.fileno())
    def run(self, command, *args, **kwargs):
        if not command or command[0] != self.executable:
            return self.real_run(command, *args, **kwargs)
        kind = 'version' if command[1:] == ['--version'] else 'models' if command[1:] == ['models'] else 'inference'
        before = billing_state(self.home)
        event = {'kind': kind, 'started_utc': utc(), 'before': before,
            'command_argv_sha256': sha(json.dumps(command).encode()), 'prompt_saved_here': False}
        self._record({'event': 'cli_started', **event})
        outcome = {}
        try:
            response = self.real_run(command, *args, **kwargs)
            outcome['returncode'] = response.returncode
            return response
        except BaseException as exc:
            outcome['exception_type'] = type(exc).__name__
            raise
        finally:
            try:
                outcome['after'] = billing_state(self.home)
            except BaseException as exc:
                outcome['after_error_type'] = type(exc).__name__
                outcome['after_error'] = str(exc)[:200]
                self._record({'event': 'cli_finished', 'kind': kind, 'finished_utc': utc(), **outcome})
                raise
            self._record({'event': 'cli_finished', 'kind': kind, 'finished_utc': utc(), **outcome})


def verify_zero_request(manifest):
    continuation = manifest['continuation']
    expected_parent = {'file': 'results/prompt-comparison-v1-2026-09-24/gemini-exact-v2/execution-manifest.draft.json',
        'sha256': '11c198ae9d9ccc7a68c041743da086a662d6aec19c6771b152e40fbadb484022'}
    if continuation.get('parent_manifest') != expected_parent or continuation.get('original_attempt_id') != 'aa69d942-9527-490f-b98d-8c5ef10b7b4d':
        raise ValueError('Zero-request parent lineage changed')
    json_bound(expected_parent)
    terminal = json_bound(continuation['stopped_terminal'])
    if (terminal.get('status') != 'stopped' or terminal.get('records_saved') != 0
            or terminal.get('expected') != 3 or terminal.get('error_type') != 'RuntimeError'
            or terminal.get('error') != 'Explicit useG1Credits=false required before launch'
            or terminal.get('manifest') != expected_parent):
        raise ValueError('Original zero-request terminal changed')
    for key in ('empty_predictions', 'empty_attempts', 'empty_events'):
        spec = continuation[key]
        if bind(ROOT / spec['file']) != spec or (ROOT / spec['file']).stat().st_size != 0:
            raise ValueError('Original stopped smoke contains a request or output')
    events = [json.loads(line) for line in GLOBAL_JOURNAL.read_text().splitlines()]
    order = prompt_schedule._schedule(manifest['schedule'], ROOT)
    prompt_schedule._replay(events, manifest['schedule'], order, ROOT)
    matched = [e for e in events if e.get('attempt_id') == continuation['original_attempt_id']]
    if (len(matched) != 2 or matched[0].get('event') != 'claimed'
            or (matched[0].get('configuration_id'), matched[0].get('condition'), matched[0].get('stage')) != (FIRST, 'P1', 'smoke')
            or matched[1].get('event') != 'finished' or matched[1].get('status') != 'stopped'
            or continuation['stopped_terminal'] not in matched[1].get('evidence', [])):
        raise ValueError('Original global schedule does not prove zero-request stop')
    return matched[1]['event_sha256']


def route(manifest, configuration_id, condition):
    item = next((r for r in manifest['configurations'] if r['configuration_id'] == configuration_id), None)
    if item is None or condition not in item['conditions']:
        raise ValueError('Unscheduled Gemini condition')
    if configuration_id == FIRST and condition == 'P1':
        expected = AMEND / FIRST / 'P1'
        for stage in ('smoke', 'development'):
            if (ROOT / item['conditions']['P1'][stage + '_output']).resolve() != (expected / (stage + '.jsonl')).resolve():
                raise ValueError('First condition must use separate continuation outputs')
        return item, CONTINUATION_JOURNAL
    original = json_bound(manifest['continuation']['parent_manifest'])
    prior = next(r for r in original['configurations'] if r['configuration_id'] == configuration_id)
    if item['conditions'][condition] != prior['conditions'][condition]:
        raise ValueError('Other Gemini conditions must retain original outputs/previews')
    return item, GLOBAL_JOURNAL


def verify_manifest(manifest):
    if (manifest.get('contract') != 'gemini-billing-default-continuation-draft-v1'
            or manifest.get('status') != 'offline_preparation_review_required'
            or manifest.get('inference_authorized_by_this_manifest') is not False):
        raise ValueError('Unknown billing-amendment draft')
    original = json_bound(manifest['continuation']['parent_manifest'])
    underlying = {k: v for k, v in manifest.items() if k not in ('continuation', 'billing_amendment')}
    underlying['contract'] = 'gemini-exact-draft-v2'
    frozen.verify_manifest(underlying)
    verify_zero_request(manifest)
    policy = json_bound(manifest['billing_amendment'])
    if (policy.get('contract') != 'gemini-billing-default-policy-v1'
            or policy.get('default_source') != DEFAULT_SOURCE
            or policy.get('guide_source') != GUIDE_SOURCE
            or policy.get('accepted_observed') != ['absent_documented_default_false', 'explicit_false']
            or policy.get('rejected_observed') != ['true', 'null', 'other_nonboolean']):
        raise ValueError('Billing policy source or behavior changed')
    for item in manifest['configurations']:
        for condition in ('P1', 'P2'):
            route(manifest, item['configuration_id'], condition)
    if len(original['configurations']) != 7 or len(manifest['configurations']) != 7:
        raise ValueError('Configuration roster changed')


def preflight():
    manifest = json.loads(MANIFEST.read_text())
    verify_manifest(manifest)
    return {'contract': 'gemini-billing-default-offline-preflight-v1',
        'manifest': bind(MANIFEST), 'parent_preflight': manifest['continuation']['parent_preflight'],
        'original_stopped_terminal': manifest['continuation']['stopped_terminal'],
        'original_finished_event_sha256': verify_zero_request(manifest),
        'configuration_count': 7, 'condition_count': 14, 'special_zero_request_continuation': FIRST + '/P1',
        'other_conditions_global_schedule': 13, 'model_invoked': False, 'inference_performed': False,
        'reference_labels_read': False, 'review_required': True}


def review(manifest_sha, preflight_sha, receipt_path, receipt_sha):
    manifest = load_hash(MANIFEST, manifest_sha); verify_manifest(manifest)
    evidence = load_hash(PREFLIGHT, preflight_sha)
    if evidence != preflight(): raise ValueError('Billing-amendment preflight changed')
    receipt_path = Path(receipt_path).resolve()
    if receipt_path.parent != AMEND.resolve(): raise ValueError('Amendment review must live beside manifest')
    receipt = load_hash(receipt_path, receipt_sha)
    expected = {'contract': 'gemini-billing-default-root-review-v1',
        'decision': 'approved_zero_request_continuation_and_normal_remaining_conditions',
        'manifest': bind(MANIFEST), 'preflight': bind(PREFLIGHT),
        'original_stopped_terminal': manifest['continuation']['stopped_terminal'],
        'original_attempt_id': manifest['continuation']['original_attempt_id']}
    if any(receipt.get(k) != v for k, v in expected.items()) or not receipt.get('reviewer') or not receipt.get('reviewed_utc'):
        raise ValueError('Root review does not authorize the billing amendment')
    return manifest


def execute(manifest, configuration_id, condition, stage, inspection_path=None, inspection_sha=None):
    item, journal = route(manifest, configuration_id, condition)
    output = ROOT / item['conditions'][condition][stage + '_output']
    audit_path = output.with_name(stage + '-billing-audit.jsonl')
    if any(path.exists() for path in (output, output.with_name(stage + '-attempts.jsonl'),
            output.with_name(stage + '-attempts.events.jsonl'), output.with_name(stage + '.terminal.json'), audit_path)):
        raise FileExistsError('Exclusive continuation output and billing audit required')
    if configuration_id == FIRST and condition == 'P2':
        # The original global stop only permits P2 after the distinct P1
        # continuation reaches a terminal point; do not misuse its old stop.
        continuation_output = ROOT / manifest['configurations'][0]['conditions']['P1']['development_output']
        development_terminal = continuation_output.with_name('development.terminal.json')
        smoke_terminal = continuation_output.with_name('smoke.terminal.json')
        if not (development_terminal.exists() or smoke_terminal.exists() and json.loads(smoke_terminal.read_text()).get('status') == 'stopped'):
            raise ValueError('P1 continuation must become terminal before P2')
    home = Path(os.environ['HOME'])
    billing_state(home)
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open('x') as stream:
        old = (frozen.MANIFEST, frozen.PREFLIGHT, frozen.JOURNAL, frozen.native, frozen.subprocess)
        frozen.MANIFEST, frozen.PREFLIGHT, frozen.JOURNAL = MANIFEST, PREFLIGHT, journal
        frozen.native, frozen.subprocess = NativeProxy(), ProcessProxy(manifest['cli']['path'], home, stream)
        try:
            underlying = {k: v for k, v in manifest.items() if k not in ('continuation', 'billing_amendment')}
            underlying['contract'] = 'gemini-exact-draft-v2'
            frozen.run_stage(underlying, item, condition, stage, inspection_path, inspection_sha)
        finally:
            frozen.MANIFEST, frozen.PREFLIGHT, frozen.JOURNAL, frozen.native, frozen.subprocess = old


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--preflight', action='store_true')
    action.add_argument('--run-stage', choices=('smoke', 'development'))
    parser.add_argument('--manifest-sha256'); parser.add_argument('--preflight-sha256')
    parser.add_argument('--review-receipt'); parser.add_argument('--review-receipt-sha256')
    parser.add_argument('--configuration-id'); parser.add_argument('--condition', choices=('P1', 'P2'))
    parser.add_argument('--smoke-inspection'); parser.add_argument('--smoke-inspection-sha256')
    args = parser.parse_args()
    if args.preflight:
        if any((args.manifest_sha256, args.preflight_sha256, args.review_receipt, args.review_receipt_sha256,
                args.configuration_id, args.condition, args.smoke_inspection, args.smoke_inspection_sha256)):
            parser.error('Offline preflight takes no live execution arguments')
        write_exclusive(PREFLIGHT, preflight()); return
    if not all((args.manifest_sha256, args.preflight_sha256, args.review_receipt, args.review_receipt_sha256,
                args.configuration_id, args.condition)):
        parser.error('Frozen hashes, review and scheduled condition required')
    manifest = review(args.manifest_sha256, args.preflight_sha256, args.review_receipt, args.review_receipt_sha256)
    execute(manifest, args.configuration_id, args.condition, args.run_stage,
            args.smoke_inspection, args.smoke_inspection_sha256)


if __name__ == '__main__': main()
