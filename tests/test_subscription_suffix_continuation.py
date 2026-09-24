import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import subscription_suffix_continuation as suffix

MANIFEST = ROOT / 'results/prompt-comparison-v1-2026-09-24/subscription-suffix-continuation-v1/manifest.json'


def frozen():
    return json.loads(MANIFEST.read_text())


def test_exact_six_never_sent_suffixes_and_original_admission():
    contexts = suffix.validate(frozen())
    selected = {k: v for k, v in contexts.items() if isinstance(k, tuple)}
    assert len(selected) == 6
    assert sum(len(v['entry']['record_ids']) for v in selected.values()) == 190
    for key, context in selected.items():
        entry = context['entry']
        assert context['admission']['admitted'] is True
        assert entry['record_ids'][0] == f'DEV-{entry["offset"] + 1:03d}'
        assert entry['record_ids'][-1] == 'DEV-060'
        assert all(len(r['record_ids']) == 10 for r in context['requests'])


def test_attempted_batch_or_request_cannot_enter_suffix():
    changed = frozen()
    entry = changed['conditions'][0]
    entry['record_ids'][0] = 'DEV-030'
    with pytest.raises(ValueError, match='never-sent'):
        suffix.validate(changed)
    changed = frozen()
    changed['conditions'][0]['request_bindings'][0]['record_ids'][0] = 'DEV-030'
    with pytest.raises(ValueError, match='request bindings'):
        suffix.validate(changed)


def test_exact_client_request_and_runtime_guard(tmp_path, monkeypatch):
    contexts = suffix.validate(frozen())
    key = ('codex-gpt-5.6-luna-xhigh', 'P1')
    context = copy.deepcopy(contexts[key])
    original = suffix.ROOT
    monkeypatch.setattr(suffix, 'ROOT', tmp_path)
    entry = context['entry']
    for name in ('output', 'attempts', 'journal', 'admission'):
        entry[name] = name + '.jsonl'
    guard = suffix.SuffixGuard(context, 'frozen-hash')
    with pytest.raises(ValueError, match='runtime'):
        guard.begin('wrong-cli-version')
    assert not (tmp_path / entry['journal']).exists()
    # The real frozen request is read from the repository, but output stays in tmp.
    monkeypatch.setattr(suffix, 'ROOT', original)
    expected = context['requests'][0]
    envelope = json.loads((original / expected['client_request']['file']).read_text())
    monkeypatch.setattr(suffix, 'ROOT', tmp_path)
    guard.begin(context['config']['controls']['runtime'])
    import prompt_execution_gates as gates
    monkeypatch.setattr(gates, 'json_bound', lambda spec, root: envelope)
    with pytest.raises(ValueError, match='Live request differs'):
        guard.check_request({'changed': True}, expected['record_ids'], envelope['adapter_controls'])
    assert guard.index == 0
    # No model call: retain a stopped terminal and prevent a second claim.
    guard.finish(completed=False)
    journal = suffix.rows(tmp_path / entry['journal'])
    assert [r['event'] for r in journal] == ['claimed', 'finished']
    assert journal[0]['attempt_id'] == journal[1]['attempt_id']
    assert journal[1]['status'] == 'stopped'
    with pytest.raises(FileExistsError, match='already exists'):
        guard.begin(context['config']['controls']['runtime'])


def test_claude_selection_is_exact_suffix_and_restores_reader(monkeypatch):
    import claude_batch_benchmark as batch
    contexts = suffix.validate(frozen())
    context = contexts[('haiku45-not_applicable-phase2-batch10-p0', 'P1')]
    original = batch.read_rows
    observed = {}

    def fake_run(args, guard):
        selected = batch.read_rows(ROOT / 'data/pilot/inputs.jsonl')[:args.limit]
        observed['ids'] = [r['id'] for r in selected]
        with pytest.raises(ValueError, match='unexpected input'):
            batch.read_rows(ROOT / 'data/pilot/proposed_labels.jsonl')

    monkeypatch.setattr(batch, '_run', fake_run)
    suffix.run_claude_suffix(SimpleNamespace(limit=40), SimpleNamespace(entry=context['entry']))
    assert observed['ids'] == context['entry']['record_ids']
    assert batch.read_rows is original


def test_execute_rejects_unapproved_receipt_before_cli(tmp_path, monkeypatch):
    manifest_sha = suffix.sha(MANIFEST)
    review = tmp_path / 'review.json'
    review.write_text(json.dumps({'contract': 'subscription-suffix-root-review-v1',
                                  'decision': 'not_approved', 'manifest_sha256': manifest_sha,
                                  'approved_conditions': []}))
    with pytest.raises(ValueError, match='Root receipt'):
        suffix.execute(MANIFEST, manifest_sha, review, ('codex-gpt-5.6-luna-xhigh', 'P1'))


def test_approved_receipt_selects_only_frozen_codex_suffix_without_cli(tmp_path, monkeypatch):
    import codex_batch_benchmark as batch
    manifest_sha = suffix.sha(MANIFEST)
    key = ('codex-gpt-5.6-luna-xhigh', 'P1')
    review = tmp_path / 'approved.json'
    review.write_text(json.dumps({'contract': 'subscription-suffix-root-review-v1',
                                  'decision': 'approved', 'manifest_sha256': manifest_sha,
                                  'approved_conditions': ['/'.join(key)]}))
    observed = {}
    contexts = copy.deepcopy(suffix.validate(frozen()))
    for name in ('output', 'attempts', 'journal', 'admission'):
        contexts[key]['entry'][name] = str(tmp_path / name)
    monkeypatch.setattr(suffix, 'validate', lambda manifest: contexts)

    def fake_run(args, guard):
        observed['offset_limit'] = (args.offset, args.limit, args.batch_size)
        observed['ids'] = guard.entry['record_ids']

    monkeypatch.setattr(batch, '_run', fake_run)
    suffix.execute(MANIFEST, manifest_sha, review, key)
    assert observed['offset_limit'] == (30, 30, 10)
    assert observed['ids'] == [f'DEV-{i:03d}' for i in range(31, 61)]


def test_claude_requires_billing_control_receipt(tmp_path):
    manifest_sha = suffix.sha(MANIFEST)
    key = ('haiku45-not_applicable-phase2-batch10-p0', 'P1')
    review = tmp_path / 'approved.json'
    review.write_text(json.dumps({'contract': 'subscription-suffix-root-review-v1',
                                  'decision': 'approved', 'manifest_sha256': manifest_sha,
                                  'approved_conditions': ['/'.join(key)]}))
    with pytest.raises(ValueError, match='extra-usage billing'):
        suffix.execute(MANIFEST, manifest_sha, review, key)
