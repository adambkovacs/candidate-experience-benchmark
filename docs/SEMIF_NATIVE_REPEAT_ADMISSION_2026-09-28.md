# SemIf native P0 repeat admission, 28 September 2026

This is an **offline frozen plan**, not authorization to dispatch. The [manifest](../results/repeatability-v1/semif-native-mlx-v1/manifest.json) has SHA-256 `26cc75f1676ddf72bd9730e43b0e49cf5256427c4e1ec4549fc9ea513b7372c5`; the [controller](../scripts/semif_repeat_admission.py) has SHA-256 `e81805d1ac4730181795a80a32a12c6f03004136624faaf36f9e05ca80f3be9d`. No weights were loaded, downloaded or used for inference during preparation. Root must review these exact bytes before any stage receipt is issued.

## First-pass eligibility and scope

`semif-direct`, `semif-serial` and `semif-shared` each have an eligible historical **native P0 output** pass. Each original [direct](../results/semif-direct-bf16-2026-09-23/development.jsonl), [serial](../results/semif-serial-bf16-2026-09-23/development.jsonl) and [shared](../results/semif-shared-bf16-2026-09-23/development.jsonl) development file contains 60 ordered, single-attempt valid records and retains its own three-record smoke. Offline reconstruction matched all 60 policy, feedback and official request hashes, four option orders, normalized raw probabilities, predictions, mode, runtime and checkpoint hashes. The manifest binds the three historical file pairs and, for each field of each record, its tokenized prompt hash, input-ID hash, answer-slot token IDs and input length. These modes have different score/cache operations and remain separate configurations. [Native specialist eligibility](NATIVE_SPECIALIST_REPEAT_AUDIT_2026-09-28.md) explains why generative P1/P2 prompts are inapplicable. The generated SemIf control, including P2's unknown DEV-033, is outside this schedule.

The historical runner source is reconstructed at Git commit `724efe57cdfb3fdbfedc161f24912a25450791b2`; the record does not itself report its process Git HEAD. Later runner changes add generated-control gates but do not alter the native scoring branch. Historical latency was observed under host load, including concurrent hosted HTTP work, and is not an isolated timing baseline. No explicit seed was set. The pinned backend uses `model.eval()` and conditional answer-slot logits without text generation; repeated output does not prove intrinsic determinism.

## Frozen operation

The source is clean at SemIf commit `ca3ba65f142967030ecb453346e94d6f476a69df`. The local Qwen3.5-4B checkpoint revision label is `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`; all 11 files, including both safetensors shards, matched the saved per-file SHA-256 map during preparation. Runtime: Python 3.12.12 in the pinned specialist venv, macOS 26.6 arm64, Apple M4 Max, native MLX Metal GPU, BF16 and FP32 parameters without quantization, MLX 0.32.2, MLX-LM 0.32.0, Transformers 5.17.0, PyTorch 2.10.0 and SemIf phase 1 0.1.0. Before any stage, the controller rehashes the exact assets and imported source files, checks the host/runtime, verifies all historical controls and confirms the [Laya plan](LAYA_NATIVE_P0_REPEAT_ADMISSION_2026-09-28.md) is unchanged.

The schedule is fixed in this order: repeat 2 direct, serial, shared; then repeat 3 direct, serial, shared. Every phase is P0 and has a separate DEV-001–003 smoke and DEV-001–060 development run. These six smokes add 18 native records and are excluded from scoring. Direct scores each of four questions from its full prompt; serial creates a fresh per-feedback prefix scorer and reuses state only across that feedback's four questions; shared scores four suffixes with a shared prefix. The new controller calls the same pinned `mlx_backend` primitives as the frozen [specialist runner](../scripts/specialist_benchmark.py). It writes a durable per-record start marker, scores, saves the raw four-decision object, then projects labels. It does not edit or invoke the frozen runner. It checks each new native prompt, input-ID and answer-slot signature against the eligible pass 1 for that exact mode. The 60 source records are input-only; no reference labels or prior predictions enter scoring.

Before model load, an exact root-reviewed receipt must bind `phase`, `stage`, manifest hash and `approved: true` under kind `root-reviewed-semif-native-p0-stage-v1`. The controller stores only the receipt SHA-256 in its durable claim. Development also requires a separate smoke inspection with phase, manifest hash, smoke output hash, the three inspected IDs and approval; its SHA-256 goes into the development receipt. A smoke with an invalid output cannot admit development. New raw and scored rows are flushed separately. An intrinsic invalid development distribution is retained as `invalid_output` and does not trigger a retry; a scoring, model-control or service failure stops the phase and retains the started intent. A crashed or incomplete stage cannot be automatically replayed. The next phase verifies every predecessor's 60 records and completion hash, not just a marker.

The controller takes the same nonblocking OS lock used by [Laya admission](../scripts/laya_repeat_admission.py) for an entire stage. It also checks that **all six Laya repeat phases** are verified complete before even the first SemIf stage. At preparation time this gate correctly reported Laya typed repeat 3 as unfinished. No SemIf stage has been admitted or started. Avoid other local benchmark inference while this schedule runs; MLX GPU and host contention would make time comparisons harder to interpret. The controller records client elapsed time, not pure model inference time. The historical output remains untouched.

## Review commands and stage sequence

Run these read-only checks from the repository root with the pinned interpreter. `command` prints an offline control preview and never loads weights. The six exact phase names appear in the manifest.

```sh
semif_python=/Users/adamkovacs/Documents/Codex/2026-09-21/continue-the-recruitment-feedback-benchmark-from/work/specialist-venv/bin/python
"$semif_python" scripts/semif_repeat_admission.py verify
"$semif_python" -m unittest tests.test_semif_repeat_admission -q
"$semif_python" scripts/semif_repeat_admission.py command --phase semif-direct/repeat2/P0 --stage smoke
```

After root reviews the frozen manifest, controller, test result, Laya closure and the exact stage, create a distinct stage receipt. A future admitted command has this shape; **do not execute it from this plan alone**:

```sh
"$semif_python" scripts/semif_repeat_admission.py run --phase semif-direct/repeat2/P0 --stage smoke --receipt /private/path/to/root-reviewed-stage.json
```

Inspect the three raw score objects, identities, option probabilities, actual runtime and token request signatures. Write `smoke-inspection.json` with the fields above, obtain a separate development receipt binding its hash, then run the same phase with `--stage development`. Repeat only in the manifest's order. Root admission is required for every smoke and development stage. The [nine offline tests](../tests/test_semif_repeat_admission.py) cover history/source/asset drift, exact mode calls, Laya and receipt gates before load, raw retention, invalid-smoke denial, changed token request rejection, real cross-process lock exclusion, and refusal to replay a stopped stage. They use fake scoring and make no model call.
