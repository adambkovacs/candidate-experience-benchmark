import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import subscription_suffix_continuation_v2 as haiku
import prompt_execution_gates as gates

MANIFEST = ROOT / 'results/prompt-comparison-v1-2026-09-24/subscription-suffix-continuation-v2-haiku/manifest.json'
KEY = ('haiku45-not_applicable-phase2-batch10-p0', 'P1')


def frozen():
    return json.loads(MANIFEST.read_text())


def test_runtime_only_derivatives_preserve_original_requests_and_parent():
    manifest = frozen()
    context = haiku.validate(manifest)[KEY]
    entry = context['entry']
    amendment = entry['runtime_amendment']
    assert amendment['from_runtime'] == '2.1.280 (Claude Code)'
    assert amendment['to_runtime'] == '2.1.281 (Claude Code)'
    assert context['config']['controls']['runtime'] == amendment['from_runtime']
    assert entry['record_ids'] == [f'DEV-{i:03d}' for i in range(21, 61)]
    assert len(entry['request_bindings']) == len(amendment['amended_envelope_sha256']) == 4
    for request, expected_sha in zip(entry['request_bindings'], amendment['amended_envelope_sha256']):
        original = gates.json_bound(request['client_request'], ROOT)
        changed = copy.deepcopy(original)
        changed['adapter_controls']['cli_version'] = amendment['to_runtime']
        assert original['request'] == changed['request']
        assert gates.canonical(changed) == expected_sha


def test_amendment_rejects_control_and_derivative_tampering():
    changed = frozen()
    changed['conditions'][0]['runtime_amendment']['changed_fields'].append('request.system')
    with pytest.raises(ValueError, match='unsupported controls'):
        haiku.validate(changed)
    changed = frozen()
    changed['conditions'][0]['runtime_amendment']['amended_envelope_sha256'][0] = '0' * 64
    with pytest.raises(ValueError, match='derivation changed'):
        haiku.validate(changed)


def test_guard_uses_live_runtime_and_amended_envelope_without_model_call(tmp_path, monkeypatch):
    context = copy.deepcopy(haiku.validate(frozen())[KEY])
    original_root = haiku.ROOT
    expected = context['requests'][0]
    frozen_envelope = gates.json_bound(expected['client_request'], ROOT)
    for name in ('output', 'attempts', 'journal', 'admission'):
        context['entry'][name] = name + '.jsonl'
    monkeypatch.setattr(haiku, 'ROOT', tmp_path)
    guard = haiku.SuffixGuard(context, 'reviewed-hash')
    with pytest.raises(ValueError, match='runtime'):
        guard.begin('2.1.280 (Claude Code)')
    assert not (tmp_path / context['entry']['journal']).exists()
    guard.begin('2.1.281 (Claude Code)')
    monkeypatch.setattr(gates, 'json_bound', lambda spec, root: frozen_envelope)
    amended_controls = copy.deepcopy(frozen_envelope['adapter_controls'])
    amended_controls['cli_version'] = '2.1.281 (Claude Code)'
    guard.check_request(frozen_envelope['request'], expected['record_ids'], amended_controls)
    assert guard.index == 1
    guard.finish(completed=False)
    events = haiku.rows(tmp_path / context['entry']['journal'])
    assert events[-1]['status'] == 'stopped'
    assert events[0]['attempt_id'] == events[-1]['attempt_id']


def test_root_receipt_requires_billing_verification_before_claude_adapter(tmp_path, monkeypatch):
    manifest_sha = haiku.sha(MANIFEST)
    review = tmp_path / 'review.json'
    base = {'contract': 'subscription-suffix-haiku-root-review-v1', 'decision': 'approved',
            'manifest_sha256': manifest_sha, 'approved_conditions': ['/'.join(KEY)]}
    review.write_text(json.dumps(base))
    with pytest.raises(ValueError, match='extra-usage billing'):
        haiku.execute(MANIFEST, manifest_sha, review, KEY)
    review.write_text(json.dumps({**base, 'claude_extra_usage_disabled_operator_verified': True}))
    observed = {}
    monkeypatch.setattr(haiku, 'run_claude_suffix',
                        lambda args, guard: observed.update(limit=args.limit,
                                                            ids=guard.entry['record_ids'],
                                                            runtime=guard.controls['runtime']))
    haiku.execute(MANIFEST, manifest_sha, review, KEY)
    assert observed == {'limit': 40, 'ids': [f'DEV-{i:03d}' for i in range(21, 61)],
                        'runtime': '2.1.281 (Claude Code)'}
