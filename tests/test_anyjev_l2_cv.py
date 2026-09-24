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
    assert protocol['contract'] == 'anyjev-l2-outer-cv5-protocol-v3'
    assert protocol['failed_v2_smoke']['completed_prediction_records'] == 0
    assert protocol['compatibility']['transformers_version'] == '5.17.0'
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


def test_adapter_mask_matches_installed_qwen3_no_cache_prefill():
    import torch
    from types import SimpleNamespace
    from transformers import Qwen3Config
    from transformers.masking_utils import create_causal_mask
    from anyjev_hf_517_adapter import make_517_backend

    config = Qwen3Config(num_hidden_layers=1, hidden_size=8, num_attention_heads=2,
                         num_key_value_heads=1, head_dim=4, intermediate_size=16,
                         use_sliding_window=False)
    config._attn_implementation = 'eager'
    embeddings = torch.nn.Embedding(16, 8)
    inner = SimpleNamespace(layers=[object()], embed_tokens=embeddings,
                            rotary_emb=lambda embeds, pos: ('cos', 'sin'),
                            has_sliding_layers=False)
    backend = make_517_backend(object)()
    backend.model = SimpleNamespace(model=inner, config=config)
    enc = {'input_ids': torch.tensor([[0, 3, 4]]),
           'attention_mask': torch.tensor([[0, 1, 1]])}
    pos = torch.tensor([[0, 0, 1]])
    expected_embeds = embeddings(enc['input_ids'])
    expected_mask = create_causal_mask(config=config, inputs_embeds=expected_embeds,
                                       attention_mask=enc['attention_mask'],
                                       past_key_values=None, position_ids=pos)
    ctx = backend._prepare(enc, pos)
    torch.testing.assert_close(ctx['hidden'], expected_embeds)
    torch.testing.assert_close(ctx['masks']['full_attention'], expected_mask)
    assert ctx['rope'] == ('cos', 'sin')
    assert 'cache_position' not in ctx

    config.model_type = 'not-qwen3'
    with pytest.raises(ValueError, match='only pinned Qwen3'):
        backend._prepare(enc, pos)


def test_adapter_decoder_calls_match_installed_no_cache_kwargs():
    import torch
    from types import SimpleNamespace
    from anyjev_hf_517_adapter import make_517_backend

    calls = []
    class Layer:
        def __call__(self, hidden, **kwargs):
            assert set(kwargs) == {'attention_mask', 'position_embeddings',
                                   'position_ids', 'past_key_values', 'use_cache'}
            assert kwargs['past_key_values'] is None
            assert kwargs['use_cache'] is False
            assert kwargs['attention_mask'] is mask
            assert kwargs['position_embeddings'] is rope
            assert kwargs['position_ids'] is pos
            calls.append(kwargs)
            return hidden + 1

    mask = object()
    rope = object()
    pos = object()
    backend = make_517_backend(object)()
    backend.model = SimpleNamespace(model=SimpleNamespace(layers=[Layer(), Layer()]))
    ctx = {'hidden': torch.zeros(1), 'masks': {'full_attention': mask},
           'position_ids': pos, 'rope': rope}
    captured = []
    backend._run_layers(ctx, 0, 2, lambda index, hidden: captured.append((index, hidden.item())))
    assert len(calls) == 2
    assert captured == [(1, 1.0), (2, 2.0)]
    assert ctx['layer'] == 2 and ctx['hidden'].item() == 2.0


def test_compatibility_is_source_and_signature_bound():
    from anyjev_hf_517_adapter import compatibility_evidence
    protocol, _, _, _ = l2.verify_protocol()
    assert compatibility_evidence() == protocol['compatibility']
    assert protocol['supersedes']['sha256'] == l2.sha(
        ROOT / 'results/anyjev-l2-protocol-2026-09-24/protocol-v2.json')
    assert protocol['failed_v2_smoke']['operations_sha256'] == l2.sha(
        ROOT / 'results/anyjev-l2-cv5-2026-09-24/smoke.operations.jsonl')


def test_adapter_synthetic_qwen3_block_loop_equals_installed_forward():
    # Random, tiny CPU model and synthetic token IDs: no benchmark data or model artifact.
    import torch
    from types import SimpleNamespace
    from transformers import Qwen3Config
    from transformers.models.qwen3.modeling_qwen3 import Qwen3Model
    from anyjev_hf_517_adapter import make_517_backend

    config = Qwen3Config(vocab_size=32, num_hidden_layers=2, hidden_size=16,
                         num_attention_heads=2, num_key_value_heads=1, head_dim=8,
                         intermediate_size=32, use_sliding_window=False)
    config._attn_implementation = 'eager'
    torch.manual_seed(0)
    model = Qwen3Model(config).eval()
    backend = make_517_backend(object)()
    backend.model = SimpleNamespace(model=model, config=config)
    enc = {'input_ids': torch.tensor([[0, 3, 4], [5, 6, 7]]),
           'attention_mask': torch.tensor([[0, 1, 1], [1, 1, 1]])}
    pos = (enc['attention_mask'].cumsum(-1) - 1).clamp(min=0)
    with torch.no_grad():
        reference = model(**enc, position_ids=pos, use_cache=False).last_hidden_state
        ctx = backend._prepare(enc, pos)
        backend._run_layers(ctx, 0, config.num_hidden_layers)
        actual = model.norm(ctx['hidden'])
    torch.testing.assert_close(actual, reference, atol=0, rtol=0)


def test_manifest_binds_adapter_and_new_output_directory(tmp_path):
    from types import SimpleNamespace

    manifest = ROOT / 'results/anyjev-l2-protocol-2026-09-24/run-manifest-v2.json'
    args = SimpleNamespace(
        model_revision='c1899de289a04d12100db370d81485cdf75e47ca',
        model_path=Path('/Users/adamkovacs/Documents/Codex/2026-09-21/continue-the-recruitment-feedback-benchmark-from/work/anyjev-qwen06-model'),
        output_dir=ROOT / 'results/anyjev-l2-cv5-hf517-v1-2026-09-24',
        batch_size=4, max_context=4096)
    assert l2.verify_run_manifest(manifest, args)['contract'] == 'anyjev-l2-native-run-manifest-v2'
    args.output_dir = ROOT / 'results/anyjev-l2-cv5-2026-09-24'
    with pytest.raises(ValueError, match='output_dir changed'):
        l2.verify_run_manifest(manifest, args)
    args.output_dir = ROOT / 'results/anyjev-l2-cv5-hf517-v1-2026-09-24'
    tampered = json.loads(manifest.read_text())
    tampered['compatibility']['transformers_version'] = 'other'
    changed = tmp_path / 'tampered-manifest.json'
    changed.write_text(json.dumps(tampered))
    with pytest.raises(ValueError, match='compatibility changed'):
        l2.verify_run_manifest(changed, args)
