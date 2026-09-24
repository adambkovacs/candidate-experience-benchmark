import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import anyjev_l2_cv as l2
import anyjev_cached_l1 as l1


def test_frozen_protocol_and_smoke_fold_selection():
    protocol, folds, feedback, policy = l2.verify_protocol()
    assert protocol['contract'] == 'anyjev-l2-outer-cv5-protocol-v2'
    assert protocol['dtype'] == 'bfloat16'
    assert protocol['fit_controls']['kinds'] == ['lda', 'ridge']
    assert len(folds['folds']) == 5
    assert {i for fold in l2.folds_for(l2.SMOKE_IDS, folds) for i in fold['test_ids']} >= set(l2.SMOKE_IDS)
    assert len(feedback) == 60 and policy


def test_twenty_actual_fit_calls_get_only_outer_train_labels():
    _, folds, feedback, _ = l2.verify_protocol()
    labels = l1.load_labels()
    calls = []

    class GuardedLabels(dict):
        def __init__(self, allowed):
            super().__init__({i: labels[i] for i in allowed})
        def __getitem__(self, key):
            if key not in self:
                raise AssertionError('Held-out label accessed by fit caller')
            return super().__getitem__(key)

    class Question:
        def __init__(self, key):
            self.id = key

    class Decider:
        backend = object()
        def fit_head(self, question, states, y, **kwargs):
            assert len(states) == len(y) == 48
            assert all(set(state) == {'feedback'} for state in states)
            assert kwargs == l2.FIT_KWARGS
            calls.append((question.id, list(y), list(states)))
            return {'method': 'head:ridge', 'n_calib': 48}

    questions = [Question(q) for q in l2.QUESTIONS]
    for fold in folds['folds']:
        guarded = GuardedLabels(fold['train_ids'])
        training = l2.narrow_training_labels(fold, guarded)
        artifact = l2.fit_fold(Decider(), questions, fold,
                               {i: feedback[i] for i in fold['train_ids']}, training)
        assert artifact['fit_count'] == 4
        assert all(sum(s.values()) == 48 for s in artifact['train_class_support'].values())
    assert len(calls) == 20


def test_fit_rejects_deliberate_outer_leakage():
    _, folds, feedback, _ = l2.verify_protocol()
    fold = folds['folds'][0]
    labels = l1.load_labels()
    leaked = {i: labels[i] for i in fold['train_ids'] + fold['test_ids'][:1]}
    with pytest.raises(ValueError, match='no held-out labels'):
        l2.fit_fold(object(), [], fold, {i: feedback[i] for i in fold['train_ids']}, leaked)
    with pytest.raises(ValueError, match='48 train feedback'):
        l2.fit_fold(object(), [], fold, {i: feedback[i] for i in fold['train_ids'] + fold['test_ids'][:1]},
                    {i: labels[i] for i in fold['train_ids']})


def test_prompt_guard_rejects_interpolated_label():
    class Tokenizer:
        def encode(self, value, add_special_tokens=False):
            return list(value.encode())

    class Backend:
        tokenizer = Tokenizer()
        context_limit = 1000
        prompt_audit = []
        def hidden_states_to(self, prompts, *args, **kwargs):
            return ('features',)

    guarded = l2.guarded_backend(Backend)()
    guarded.expect_prompts(['State: fictional feedback only'])
    with pytest.raises(ValueError, match='Actual model prompts differ'):
        guarded.hidden_states_to(['State: fictional feedback only\nproposed_label: yes'], [1])
    assert guarded._expected is not None
    guarded.hidden_states_to(['State: fictional feedback only'], [1])
    guarded.assert_consumed()
    assert guarded.prompt_audit[-1]['reference_labels_in_prompt'] is False


def test_full_rejects_changed_smoke_head_bytes(tmp_path):
    artifact = tmp_path / 'fold-1-artifacts.json'
    artifact.write_text('{"head":"original"}\n')
    row = {'fold': 1, 'artifact_sha256': l2.sha(artifact)}
    l2.verify_smoke_artifacts([row], tmp_path)
    artifact.write_text('{"head":"changed"}\n')
    with pytest.raises(ValueError, match='changed before full'):
        l2.verify_smoke_artifacts([row], tmp_path)


@pytest.mark.parametrize('operation', ['fit_head', 'predict'])
def test_native_failure_preserves_started_finished_terminal_and_no_replay(tmp_path, operation):
    attempts = tmp_path / 'attempts.jsonl'
    journal = tmp_path / 'operations.jsonl'
    lock = tmp_path / 'local-gpu.lock'
    identity = {'stage': 'smoke', 'configuration': 'test',
                'run_manifest_sha256': 'frozen', 'gpu_lock': str(lock)}

    def fail(output, operations, state):
        def interrupted():
            raise RuntimeError('synthetic interrupted native call')
        l2.audited_call(operations, operation, {'fold': 1, 'question': 'sentiment'}, interrupted)

    with pytest.raises(RuntimeError, match='interrupted native call'):
        l2.run_journaled(attempts, journal, lock, identity, fail)
    events = l2.rows(journal)
    assert [(e['event'], e.get('operation'), e.get('status')) for e in events] == [
        ('run_started', None, None), ('started', operation, None),
        ('finished', operation, 'failed'), ('terminal', None, 'stopped')]
    assert events[-1]['error_type'] == 'RuntimeError'
    assert events[-1]['gpu_lock_preserved'] is True and lock.exists()
    with pytest.raises(FileExistsError, match='Never rerun'):
        l2.run_journaled(attempts, journal, lock, identity, fail)
    assert len(l2.rows(journal)) == 4
