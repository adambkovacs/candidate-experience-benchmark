#!/usr/bin/env python3
"""Audited subscription continuation for six never-sent batch10 suffixes.

No model request occurs during import or preflight. Execute requires a separate
root receipt bound to this immutable manifest. Original stopped batches remain
ambiguous and are never replayed. This controller reuses the original CLI batch
implementations with a continuation-aware guard and independent journal.
"""
import argparse
import copy
import hashlib
import json
import os
import shutil
import uuid
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/prompt-comparison-v1-2026-09-24')
CONTRACT = 'subscription-suffix-haiku-runtime-amendment-v1'
EXPECTED = {
    ('haiku45-not_applicable-phase2-batch10-p0', 'P1'): (20, 40, 'claude'),
}
INVENTORY_NAMES = {
    ('codex-gpt-5.6-luna-xhigh', 'P1'),
    ('codex-gpt-5.6-luna-xhigh', 'P2'),
    ('codex-gpt-6-astra-medium', 'P2'),
    ('codex-gpt-5.6-terra-low', 'P1'),
    ('codex-gpt-5.6-terra-low', 'P2'),
    ('codex-gpt-5.6-terra-medium', 'P2'),
    ('haiku45-not_applicable-phase2-batch10-p0', 'P1'),
}
LIVE_CONTROLS = [
    'Existing Claude adapter requires claude.ai subscription auth before each run.',
    'Root receipt must verify extra usage disabled; native isolation_ok rejects observed overage and identity/tool drift.',
    'Controller stops after first non-ok batch; failed original batch is never replayed.',
]



def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bound(spec):
    if set(spec) != {'file', 'sha256'}:
        raise ValueError('Exact file/hash binding required')
    path = (ROOT / spec['file']).resolve()
    path.relative_to(ROOT.resolve())
    if sha(path) != spec['sha256']:
        raise ValueError('Bound source changed: ' + spec['file'])
    return path


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def binding(path):
    path = Path(path).resolve()
    return {'file': str(path.relative_to(ROOT.resolve())), 'sha256': sha(path)}


def durable(handle, value):
    handle.write(json.dumps(value, sort_keys=True) + '\n')
    handle.flush()
    os.fsync(handle.fileno())


def now():
    return datetime.now(timezone.utc).isoformat()


def eligible_inventory(inventory):
    if inventory.get('schema') != 'subscription-stopped-inventory-v1':
        raise ValueError('Wrong stopped inventory contract')
    items = inventory.get('conditions')
    if not isinstance(items, list) or len(items) != 7:
        raise ValueError('Inventory must retain all seven stopped conditions')
    names = [(c['configuration_id'], c['condition']) for c in items]
    if len(set(names)) != 7 or set(names) != INVENTORY_NAMES:
        raise ValueError('Stopped condition inventory changed')
    zero = next(c for c in items if (c['configuration_id'], c['condition']) == ('codex-gpt-5.6-terra-low', 'P2'))
    if zero['never_sent_ids'] or zero['continuation_candidate'] is not None:
        raise ValueError('Terra low P2 is not a suffix candidate')
    for item in items:
        key = (item['configuration_id'], item['condition'])
        if key not in EXPECTED:
            continue
        offset, limit, adapter = EXPECTED[key]
        candidate = item['continuation_candidate']
        expected_ids = [f'DEV-{i:03d}' for i in range(offset + 1, 61)]
        attempted = item['valid_ids'] + item['ambiguous_attempted_ids']
        if item['adapter'] != adapter or candidate is None or candidate['offset'] != offset or candidate['limit'] != limit or candidate['batch_size'] != 10:
            raise ValueError('Wrong suffix controls: ' + str(key))
        if item['never_sent_ids'] != expected_ids or candidate['record_ids'] != expected_ids or attempted != [f'DEV-{i:03d}' for i in range(1, offset + 1)]:
            raise ValueError('Suffix overlaps an attempted or ambiguous batch')
        if len(item['valid_ids']) + len(item['ambiguous_attempted_ids']) + len(expected_ids) != 60:
            raise ValueError('Canonical sixty denominator changed')
    return items


def validate(manifest):
    """Reconstruct every old/new boundary and exact request without labels."""
    import prompt_admission as admission
    import prompt_execution_gates as gates
    import prompt_schedule as schedule

    if manifest.get('contract') != CONTRACT or manifest.get('status') != 'FROZEN_ROOT_REVIEW_REQUIRED':
        raise ValueError('Only frozen review-gated suffix manifest is supported')
    if manifest.get('live_controls') != LIVE_CONTROLS:
        raise ValueError('Live subscription/billing controls changed')
    prior = json.loads(bound(manifest['prior_suffix_manifest']).read_text())
    if prior.get('contract') != 'subscription-suffix-continuation-v1' or prior.get('status') != 'FROZEN_ROOT_REVIEW_REQUIRED':
        raise ValueError('Original suffix protocol binding changed')
    if bound(manifest['controller']) != Path(__file__).resolve():
        raise ValueError('Continuation controller source changed')
    for source in manifest['dependencies']:
        bound(source)
    inventory = json.loads(bound(manifest['inventory']).read_text())
    items = eligible_inventory(inventory)
    snapshot = bound(manifest['original_journal_snapshot'])
    if manifest['original_journal_snapshot']['sha256'] != inventory['source_journal']['sha256']:
        raise ValueError('Original journal snapshot differs from inventory freeze')
    events = rows(snapshot)
    if len(events) != inventory['source_journal']['line_count']:
        raise ValueError('Original journal snapshot length changed')
    inputs = rows(bound({'file': inventory['source_input']['path'], 'sha256': inventory['source_input']['sha256']}))
    if [r.get('id') for r in inputs] != inventory['source_input']['ordered_ids'] or any(set(r) != {'id', 'feedback'} for r in inputs):
        raise ValueError('Input-only canonical sixty changed')
    entries = manifest['conditions']
    if [(e['configuration_id'], e['condition']) for e in entries] != [k for k in EXPECTED]:
        raise ValueError('Frozen six-condition order changed')
    contexts = {}
    for entry in entries:
        key = (entry['configuration_id'], entry['condition'])
        item = next(c for c in items if (c['configuration_id'], c['condition']) == key)
        offset, limit, adapter = EXPECTED[key]
        if (entry['offset'], entry['limit'], entry['batch_size'], entry['adapter']) != (offset, limit, 10, adapter):
            raise ValueError('Frozen suffix offset/limit/adapter changed')
        if entry['record_ids'] != item['never_sent_ids']:
            raise ValueError('Manifest IDs differ from never-sent inventory')
        for evidence in item['evidence_files']:
            bound({'file': evidence['path'], 'sha256': evidence['sha256']})
        parent_binding = {'file': item['manifest']['path'], 'sha256': item['manifest']['sha256']}
        if entry['parent_manifest'] != parent_binding:
            raise ValueError('Parent manifest binding changed')
        parent = json.loads(bound(parent_binding).read_text())
        config = next(c for c in parent['configurations'] if c['id'] == key[0])
        if entry['original_controller'] != config['controller']:
            raise ValueError('Original controller binding changed')
        bound(config['controller'])
        supplement = json.loads(bound(entry['smoke_supplement']).read_text())
        if supplement.get('configuration_id') != key[0] or supplement.get('condition') != key[1] or supplement.get('execution_manifest_sha256') != parent_binding['sha256']:
            raise ValueError('Original inspected smoke supplement changed')
        config['conditions'][key[1]]['smoke_evidence'] = supplement['smoke_evidence']
        config['conditions'][key[1]]['development_not_before'] = supplement['development_not_before']
        admitted = admission.admit_development(parent, ROOT, *key)
        if not admitted['admitted'] or admitted.get('reference_labels_read') is not False:
            raise ValueError('Original smoke/development admission failed')
        evidence = gates.json_bound(config['conditions'][key[1]]['observational_evidence'], ROOT)
        suffix_requests = evidence['requests'][1 + offset // 10:]
        if [r['record_ids'] for r in suffix_requests] != [entry['record_ids'][i:i + 10] for i in range(0, limit, 10)]:
            raise ValueError('Original exact request envelopes do not match suffix')
        if entry['request_bindings'] != suffix_requests:
            raise ValueError('Manifest request bindings changed')
        amendment = entry.get('runtime_amendment')
        if adapter == 'claude':
            if not isinstance(amendment, dict) or amendment.get('contract') != 'subscription-suffix-runtime-amendment-v1':
                raise ValueError('Haiku runtime amendment missing')
            old = config['controls']['runtime']
            new = amendment.get('to_runtime')
            if amendment.get('from_runtime') != old or amendment.get('changed_fields') != ['controls.runtime', 'adapter_controls.cli_version'] or not isinstance(new, str) or new == old:
                raise ValueError('Haiku amendment changes unsupported controls')
            observation = json.loads(bound(amendment['runtime_observation']).read_text())
            if observation.get('observed_version') != new or observation.get('executable_sha256') != amendment.get('executable_sha256'):
                raise ValueError('Haiku runtime observation differs')
            derived = []
            for request in suffix_requests:
                envelope = copy.deepcopy(gates.json_bound(request['client_request'], ROOT))
                if envelope['adapter_controls'].get('cli_version') != old:
                    raise ValueError('Original Haiku request runtime differs')
                envelope['adapter_controls']['cli_version'] = new
                derived.append(gates.canonical(envelope))
            if amendment.get('amended_envelope_sha256') != derived:
                raise ValueError('Haiku amended envelope derivation changed')
        elif amendment is not None:
            raise ValueError('Codex suffix cannot silently change runtime')
        original_attempts = rows(bound(entry['original_attempts']))
        if len(original_attempts) != len(item['attempted_batch_order']):
            raise ValueError('Original batch count changed')
        for actual, declared in zip(original_attempts, item['attempted_batch_order']):
            ids = actual.get('record_order') if adapter == 'codex' else actual.get('ids')
            if ids != declared['record_ids'] or actual.get('status') != declared['status']:
                raise ValueError('Original attempted batch membership/status changed')
        if [r['status'] for r in original_attempts[:-1]] != ['ok'] * (len(original_attempts) - 1) or original_attempts[-1]['status'] == 'ok':
            raise ValueError('Original stop is not a proper attempted prefix')
        journal_key = parent['schedule']['sha256']
        if journal_key not in contexts:
            state, _ = schedule._replay(events, parent['schedule'], schedule._schedule(parent['schedule'], ROOT), ROOT)
            contexts[journal_key] = state
        claims = [e for e in events if e.get('event') == 'claimed' and e.get('configuration_id') == key[0] and e.get('condition') == key[1] and e.get('stage') == 'development']
        finishes = [e for e in events if e.get('event') == 'finished' and claims and e.get('attempt_id') == claims[0]['attempt_id']]
        if len(claims) != 1 or len(finishes) != 1 or finishes[0]['status'] != 'stopped':
            raise ValueError('Original development condition is not uniquely stopped')
        if entry['original_claim_sha256'] != claims[0]['event_sha256'] or entry['original_terminal_sha256'] != finishes[0]['event_sha256']:
            raise ValueError('Original claim/terminal hash changed')
        if entry['original_attempts'] not in finishes[0]['evidence']:
            raise ValueError('Original attempts were not terminal evidence')
        for name in ('output', 'attempts', 'journal', 'admission'):
            destination = (ROOT / entry[name]).resolve()
            destination.relative_to((ROOT / BASE / 'subscription-suffix-continuation-v2-haiku').resolve())
        contexts[key] = {'config': config, 'requests': suffix_requests, 'admission': admitted,
                         'parent': parent, 'entry': entry}
    return contexts


class SuffixGuard:
    def __init__(self, context, manifest_sha):
        self.context = context
        self.entry = context['entry']
        self.controls = copy.deepcopy(context['config']['controls'])
        amendment = self.entry.get('runtime_amendment')
        if amendment is not None:
            self.controls['runtime'] = amendment['to_runtime']
            self.controls['adapter_controls']['cli_version'] = amendment['to_runtime']
        self.adapter = 'codex_batch_v1' if self.entry['adapter'] == 'codex' else 'claude_batch_v1'
        self.requests = context['requests']
        self.manifest_sha = manifest_sha
        self.index = self.responses = 0
        self.failed = False
        self.claimed = False
        self.attempt_id = None

    def begin(self, version):
        if version != self.controls['runtime'] or self.claimed:
            raise ValueError('Live CLI runtime differs from frozen original controls')
        amendment = self.entry.get('runtime_amendment')
        if amendment is not None:
            executable = shutil.which('claude')
            if not executable or sha(executable) != amendment['executable_sha256']:
                raise ValueError('Amended Claude CLI binary changed')
        paths = [ROOT / self.entry[k] for k in ('output', 'attempts', 'journal', 'admission')]
        extra = [Path(str(paths[1]) + '.journal.jsonl')] if self.entry['adapter'] == 'codex' else [Path(str(paths[0]) + '.batches.jsonl'), Path(str(paths[0]) + '.attempts.jsonl')]
        if any(path.exists() for path in paths + extra):
            raise FileExistsError('Continuation output/journal already exists; no replay')
        admission = ROOT / self.entry['admission']
        with admission.open('x') as handle:
            json.dump({**self.context['admission'], 'continuation_manifest_sha256': self.manifest_sha,
                       'phase': 'development_suffix', 'record_ids': self.entry['record_ids'],
                       'runtime_amendment': amendment}, handle, indent=2)
            handle.write('\n'); handle.flush(); os.fsync(handle.fileno())
        with (ROOT / self.entry['journal']).open('x') as handle:
            self.attempt_id = str(uuid.uuid4())
            durable(handle, {'event': 'claimed', 'phase': 'development_suffix', 'utc': now(),
                             'attempt_id': self.attempt_id,
                             'configuration_id': self.entry['configuration_id'],
                             'condition': self.entry['condition'],
                             'manifest_sha256': self.manifest_sha,
                             'original_claim_sha256': self.entry['original_claim_sha256'],
                             'original_terminal_sha256': self.entry['original_terminal_sha256'],
                             'record_ids': self.entry['record_ids'], 'admission': binding(admission)})
        self.claimed = True

    def check_request(self, request, record_ids, adapter_controls):
        import prompt_execution_gates as gates
        if not self.claimed or self.index >= len(self.requests):
            raise ValueError('Request outside claimed suffix')
        expected = self.requests[self.index]
        frozen = gates.json_bound(expected['client_request'], ROOT)
        amendment = self.entry.get('runtime_amendment')
        if amendment is not None:
            frozen = copy.deepcopy(frozen)
            frozen['adapter_controls']['cli_version'] = amendment['to_runtime']
            if gates.canonical(frozen) != amendment['amended_envelope_sha256'][self.index]:
                raise ValueError('Amended request fingerprint changed')
        if record_ids != expected['record_ids'] or {'request': request, 'adapter_controls': adapter_controls} != frozen:
            raise ValueError('Live request differs from frozen suffix envelope')
        self.index += 1

    def check_response(self, record):
        import prompt_admission as admission
        if self.responses >= self.index:
            raise ValueError('Response without checked suffix request')
        limit = self.controls['context_tokens']
        if limit is not None:
            limit -= self.controls['output_reserve_tokens'] or 0
        result = admission.audit_response(record, self.adapter, limit)
        self.responses += 1
        if not result['passed'] or record.get('status') != 'ok':
            self.failed = True
        return result

    def finish(self, completed):
        if not self.claimed:
            return
        path = ROOT / self.entry['journal']
        success = completed and not self.failed and self.index == self.responses == len(self.requests)
        output = ROOT / self.entry['output']
        attempts = ROOT / self.entry['attempts']
        with path.open('a') as handle:
            durable(handle, {'event': 'finished', 'phase': 'development_suffix', 'utc': now(),
                             'attempt_id': self.attempt_id,
                             'status': 'completed' if success else 'stopped',
                             'requests_checked': self.index, 'responses_checked': self.responses,
                             'expected_requests': len(self.requests), 'failed': self.failed,
                             'manifest_sha256': self.manifest_sha,
                             'evidence': [binding(p) for p in (ROOT / self.entry['admission'], output, attempts) if p.exists()]})
        self.claimed = False


def run_claude_suffix(args, guard):
    """Select a verified suffix while preserving the original native CLI loop."""
    import claude_batch_benchmark as batch
    original = batch.read_rows
    expected = guard.entry['record_ids']
    offset = guard.entry['offset']

    def selected(path):
        if Path(path).resolve() != (ROOT / 'data/pilot/inputs.jsonl').resolve():
            raise ValueError('Claude suffix wrapper saw unexpected input source')
        all_rows = original(path)
        if [r['id'] for r in all_rows] != [f'DEV-{i:03d}' for i in range(1, 61)] or any(set(r) != {'id', 'feedback'} for r in all_rows):
            raise ValueError('Claude input-only canonical sixty changed')
        result = all_rows[offset:offset + len(expected)]
        if [r['id'] for r in result] != expected:
            raise ValueError('Claude suffix selection changed')
        return result

    batch.read_rows = selected
    try:
        batch._run(args, guard)
    finally:
        batch.read_rows = original


def execute(manifest, manifest_sha, review, key):
    if sha(manifest) != manifest_sha:
        raise ValueError('Manifest SHA differs from reviewed bytes')
    contexts = validate(json.loads(Path(manifest).read_text()))
    receipt = json.loads(Path(review).read_text())
    if receipt.get('contract') != 'subscription-suffix-haiku-root-review-v1' or receipt.get('decision') != 'approved' or receipt.get('manifest_sha256') != manifest_sha or '/'.join(key) not in receipt.get('approved_conditions', []):
        raise ValueError('Root receipt does not approve exact suffix manifest/condition')
    entry = contexts[key]['entry']
    if entry['adapter'] == 'claude' and receipt.get('claude_extra_usage_disabled_operator_verified') is not True:
        raise ValueError('Claude extra-usage billing control needs explicit root receipt')
    for name in ('output', 'attempts', 'journal', 'admission'):
        if (ROOT / entry[name]).exists():
            raise FileExistsError('Continuation condition already attempted; no replay')
    controls = contexts[key]['config']['controls']
    guard = SuffixGuard(contexts[key], manifest_sha)
    error = None
    try:
        if entry['adapter'] == 'codex':
            import codex_batch_benchmark as batch
            args = SimpleNamespace(codex=controls['adapter_controls']['cli_executable'],
                model=controls['model'], effort=controls['effort'], limit=entry['limit'],
                offset=entry['offset'], batch_size=10,
                timeout=contexts[key]['config']['controller_timeout_seconds'], phase='development',
                output=str(ROOT / entry['output']), attempts=str(ROOT / entry['attempts']),
                prompt_variant=entry['condition'], parent_baseline_id=contexts[key]['config']['parent_baseline_id'])
            batch._run(args, guard)
        else:
            args = SimpleNamespace(model=controls['model'], effort=controls['effort'],
                limit=entry['limit'], timeout=contexts[key]['config']['controller_timeout_seconds'],
                phase='development', output=str(ROOT / entry['output']),
                extra_usage_disabled=True, prompt_variant=entry['condition'],
                parent_baseline_id=contexts[key]['config']['parent_baseline_id'])
            run_claude_suffix(args, guard)
    except BaseException as exc:
        error = exc
        raise
    finally:
        try:
            guard.finish(completed=error is None)
        except Exception as closing:
            if error is None:
                raise
            error.add_note('Continuation terminal journal also failed: ' + str(closing))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    parser.add_argument('--sha256', required=True)
    parser.add_argument('--preflight', action='store_true')
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--review', type=Path)
    parser.add_argument('--configuration-id')
    parser.add_argument('--condition', choices=('P1', 'P2'))
    args = parser.parse_args()
    if args.preflight == args.execute:
        parser.error('Choose exactly one of --preflight or --execute')
    if args.preflight:
        if sha(args.manifest) != args.sha256:
            raise ValueError('Manifest SHA differs')
        contexts = validate(json.loads(args.manifest.read_text()))
        print(json.dumps({'contract': CONTRACT, 'preflight_ok': True,
                          'conditions': [{'id': '/'.join(key), 'never_sent': len(context['entry']['record_ids'])}
                                         for key, context in contexts.items() if isinstance(key, tuple)],
                          'inference_performed': False, 'reference_labels_read': False}))
    else:
        if not args.review or not args.configuration_id or not args.condition:
            parser.error('Execute needs --review --configuration-id --condition')
        execute(args.manifest, args.sha256, args.review, (args.configuration_id, args.condition))


if __name__ == '__main__':
    main()
