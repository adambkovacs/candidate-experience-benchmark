# Expanded CPU Laya P0 repeat admission, 28 September 2026

This is an **offline frozen plan**, not permission to run the six scheduled phases. The [manifest](../results/repeatability-v1/laya-expanded-cpu-v1/manifest.json) SHA-256 is `1a5a1eea3c18db98c81297bb1f775b9de59936cb06fc486f9b4c5f0d00094261`. Its [superseded, unexecuted predecessor](../results/repeatability-v1/laya-expanded-cpu-v1/manifest-superseded-unexecuted-v1.json) is retained at SHA-256 `7c03b9aa1ae75a9a31dd5c3f090d0d0a91646c623a45ba7bbb752a4c77043221`; no receipt or model run used it. The [admission helper](../scripts/laya_repeat_admission.py) verifies the current manifest against source bytes, historical records, installed runtime, machine identity and local checkpoint assets before it can call the unchanged [specialist runner](../scripts/specialist_benchmark.py). The [native specialist audit](NATIVE_SPECIALIST_REPEAT_AUDIT_2026-09-28.md) explains why the original nonexpanded English, typed and multilingual configurations remain 60/60 `unsupported_length` with **no inference**. These expanded CPU variants are three different configurations; only their native P0 interface is scheduled. No generative P1/P2 prompt was added, and no policy or feedback was shortened.

## First-pass decision

The saved expanded-context English, typed and multilingual [first-pass reconciliations](../results/laya-english-expanded-cpu-2026-09-23/reconciliation.json), [typed reconciliation](../results/laya-typed-expanded-cpu-2026-09-23/reconciliation.json), and [multilingual reconciliation](../results/laya-multilingual-expanded-cpu-2026-09-24/reconciliation.json) qualify as historical pass 1 for **output stability**. Each has an ordered three-record smoke and an ordered 60-record development file. An independent offline reconstruction checked every ID, input and policy hash, official-request hash, raw-answer-to-prediction mapping, one-attempt record, CPU/FP32/no-quantization metadata, expanded `max_len=4096` and `head_max_len=512`, and saved full-token coverage metadata. The current local checkpoint files still match their pinned hashes. The original runner versions are recoverable at Git commits `91b646d`, `adc1fb8`, and `e147bac`; their SHA-256 values and the saved smoke/development file hashes are in the manifest. Thus a fresh matched-three series is **not required for categorical output repeats**. This does not turn the English pass's contended latency into an uncontended timing baseline.

The historical files do not prove an effective random seed, OS cache state or identical CPU load. No explicit seed is set in the original runner or the new passes; upstream Laya loads a model in evaluation mode. Treat an observed flip as a result under these recorded controls, not proof of intrinsic stochasticity. English pass 1 explicitly records concurrent GPU inference/download contention; the typed and multilingual notes have different background conditions. Report client elapsed time as observed, without a controlled-latency comparison. All three historical files record the same macOS host and six package versions as the pinned repeat interpreter; the manifest checks and explicitly records `runtime_matches_repeat: true` for each.

## Frozen controls and boundaries

The manifest pins all 60 input-only records in DEV-001–DEV-060 order, policy prefix SHA-256 `81e5f843de69c1c54ca4f17b70df51886405ad3a7606d5644ac24aeb29f839a5`, each official request and input hash, the full input file and runner/adapter source hashes, all imported Laya package modules, five files for each checkpoint, historical file hashes, and the local runtime. The entire historical [English](../results/laya-english-expanded-cpu-2026-09-23/development.jsonl), [typed](../results/laya-typed-expanded-cpu-2026-09-23/development.jsonl), and [multilingual](../results/laya-multilingual-expanded-cpu-2026-09-24/development.jsonl) raw records remain untouched. The new six phase identities are three configurations × `repeat2`/`repeat3`, P0 only. Each phase has a DEV-001–003 smoke followed, after inspection, by a separate DEV-001–060 development run. The smoke is an extra inspection call, not part of the 60-position scored pass.

| Checkpoint | Model weight SHA-256 | Native encoder | Historical 60-record SHA-256 |
| --- | --- | --- | --- |
| English expanded CPU | `891102d372688fc2a094dac56a384bc537b87c63f21f9f3dac0be2b7cbc8d86c` | `answerdotai/ModernBERT-large` | `a5999c03f1537670e2007764fa61fe47c4ccb35149d52b42c5e942e257addc30` |
| Typed expanded CPU | `4fa56de72383a9d3efa9cfa78955733c81b9fc8067a587ca4beb82c78107a24e` | `answerdotai/ModernBERT-large` | `d0c5f85c1f3f942971d3edf5b99b1431dba6d043815554859bdea9591bcba678` |
| Multilingual expanded CPU | `9d628fd971b700382ac6f65920a86f149777b2e748e0c955fb3b19695aa8f204` | `jhu-clsp/mmBERT-base` | `6b3cbb3f1333a8d3ddc9635353d26b6eb02c94afd739656b8e9f6e73a1ce454f` |

The pinned interpreter is `/Users/adamkovacs/Documents/Codex/2026-09-21/continue-the-recruitment-feedback-benchmark-from/work/specialist-venv/bin/python` on macOS 26.6 arm64. The read-only hardware probe records `Mac16,5`, Apple M4 Max, 128 GB physical memory and 16 CPU cores; a missing probe field would be recorded as null rather than guessed and would change the frozen plan. Pinned versions: PyTorch 2.10.0, Transformers 5.17.0, Laya 0.3.4, MLX 0.32.2, MLX-LM 0.32.0, SemIf phase 1 0.1.0. Each new subprocess uses `OMP_NUM_THREADS=4`, `MKL_NUM_THREADS=4`, `HF_HUB_OFFLINE=1`, and `TRANSFORMERS_OFFLINE=1`; it loads only the pinned local checkpoint with `--device cpu --mode expanded`. The unchanged runner checks exact untruncated native sequences and option markers before `predict()`, rejects device fallback, and records raw Laya answers and actual effective configuration. Cache warming, thermal state and other host load are not controlled by this plan. The helper takes a nonblocking OS-wide file lock across each stage and verifies all prior phases' 60 raw records and completion hashes before admitting the next declared phase. Avoid other local benchmark inference if a timing comparison is desired.

## Reviewed execution sequence

From the repository root, first run the offline checks. The `command` action prints the exact runner argv for inspection and **does not execute it**. The example phase below is English repeat 2; substitute one of the six frozen phase IDs printed in the manifest. Execute phases in the declared manifest order: repeat 2 English, typed, multilingual; then repeat 3 English, typed, multilingual.

```sh
laya_python=/Users/adamkovacs/Documents/Codex/2026-09-21/continue-the-recruitment-feedback-benchmark-from/work/specialist-venv/bin/python
"$laya_python" scripts/laya_repeat_admission.py verify
"$laya_python" -m unittest tests.test_laya_repeat_admission -q
"$laya_python" scripts/laya_repeat_admission.py command --phase laya-english-expanded-cpu/repeat2/P0 --stage smoke
```

Only after root review, create an individual `root-reviewed-laya-p0-stage-v1` receipt for that exact phase and `smoke` stage with `approved: true` and the manifest SHA-256. The helper does not create or infer that approval. Launch the admitted smoke through the helper:

```sh
"$laya_python" scripts/laya_repeat_admission.py run --phase laya-english-expanded-cpu/repeat2/P0 --stage smoke --receipt /path/to/root-reviewed-smoke.json
```

Inspect all three saved records and raw answer/probability distributions, model identity, requested/actual CPU and FP32, artifact and policy/request hashes, coverage lengths, and the smoke completion hash. Save `smoke-inspection.json` beside the smoke file with the exact `phase`, `plan_sha256`, `smoke_sha256`, `inspected_ids` `['DEV-001','DEV-002','DEV-003']` as JSON strings, and `approved: true`. A separate root-reviewed `development` receipt must bind the SHA-256 of that inspection. Only then run:

```sh
"$laya_python" scripts/laya_repeat_admission.py command --phase laya-english-expanded-cpu/repeat2/P0 --stage development
"$laya_python" scripts/laya_repeat_admission.py run --phase laya-english-expanded-cpu/repeat2/P0 --stage development --receipt /path/to/root-reviewed-development.json
```

The helper writes an exclusive durable intent before invoking the frozen runner. A concurrent phase fails on the global lock; a repeated stage cannot acquire the same intent. It verifies all 3 or 60 output records before writing a completion sidecar, and the next phase checks that prior evidence again rather than trusting the sidecar count. A nonzero exit, incomplete file, failed coverage or invalid response leaves the intent and available raw file in place; **do not automatically replay** an uncertain call or relabel unsent positions as completed. The frozen runner flushes each JSONL record but does not retain a raw response if its parser fails before record assembly; such an event is an unknown/intrinsic failure to report, not a reason to invent a prediction. The wrapper does not make the historical runner crash-atomic per request. Any later adjudication or fresh-series decision needs its own recorded plan, preserving this attempt.

The [eight offline guard tests](../tests/test_laya_repeat_admission.py) cover plan, asset and hardware drift, excluded variants, exact command controls, receipt gates, smoke-inspection binding, full output and predecessor validation, a real OS lock conflict, exclusive replay refusal and interrupted-run intent preservation. They do not load weights or call an inference API.
