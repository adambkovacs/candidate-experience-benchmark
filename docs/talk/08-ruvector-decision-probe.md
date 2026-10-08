# ruvector decision / typesafe probe

Probed 2026-10-08 against the live repo (ruvnet/ruvector, pushed 2026-10-07), npm, and the local classification-bench docs.

## 1. What exists

The module Adam remembers is **`@ruvector/typesafe`**. It is a local, offline re-implementation of Jev (typesafe.ai) "System One", built inside the ruvector monorepo. Nothing named jev, decide or decision exists as a separate crate or package. Other hits for "decision" are unrelated: `ruvector-robotics/src/cognitive/decision_engine.rs` (a weighted utility scorer for robot actions), `daa-ai/src/decisions.rs` (a mock that returns "mock_action"), and SAFLA delta-evaluation docs.

| Item | Value |
| --- | --- |
| npm package | `@ruvector/typesafe`, latest 0.2.0 (modified 2026-09-29), MIT, about 136 MB unpacked (native binaries) |
| Source | `npm/packages/typesafe/` in ruvnet/ruvector (TypeScript client, CLI, bench, ADR-001 to 008) |
| Rust crates | `crates/ruvector-typesafe-core` (engine, heads, calibration, receipts), `ruvector-typesafe-ffi` (napi-rs), `ruvector-typesafe-wasm`, `ruvector-embed-core` (ort / tract embedders) |
| npm description | "Local typed decisions (choice / score / noul) over sentence embeddings ... alternative to typesafe.ai's System One API. Native (napi-rs) with a WASM fallback; no network, no per-token cost." |
| Runs | Node 18+, native napi binary or WASM, a local CLI, and `typesafe serve` (Jev-compatible `POST /v1/systemone`). No network and no subprocess in the decision path (ADR-005). |

**Backbone.** A frozen sentence embedder (bge-small-en-v1.5 or all-MiniLM-L6-v2, ONNX, 384-d, hash-pinned in `models/manifest.json`) feeds small heads in Rust. There is no LLM and no logits. The head is chosen per question by how many labels exist (ADR-003):

- No examples: nearest-prototype over option text, with `not_for` text as a hard negative.
- 4 or more examples per option: an L2 logistic-regression probe on the frozen embeddings.
- Calibration: temperature scaling on a held-out slice; `noul` gets a Platt layer.

**API shape.** One `state` string plus a map of questions. Question types:

- `choice`: up to 255 options, each a string or `{what, not_for, examples}`. Returns `{choice, probabilities, confidence, abstain, calibrated, head, model, temperature}`.
- `score`: an ordinal legend.
- `noul`: a 0 to 1 predicate.

A batch of questions is one call with a receipt. `train`, `eval`, `optimize` (a governed self-tuning loop) and `serve` are included.

**Catches, from the package's own README.**

- The published npm 0.2.0 binary ships only the **hash test embedder**, which the README says carries no meaning on real text. Real embeddings need a source build with `--features native-onnx`, downloaded weights, and `ort` fetching onnxruntime at build time.
- 0.2.0 was published with a maintainer override of its own release gates. On its tickets suite, accuracy was 0.807 against a 0.823 gate and calibration error was 0.080 against a 0.05 gate.
- Zero-shot `choice` is weak. ADR-003 cites 35 to 48% at 1-shot and 75 to 87% at 5 to 10 shots on intent benchmarks.
- Untrained `noul` and `score` run near chance. The README reports urgency AUROC 0.51 and 33% exact on a 3-bucket severity question.
- Embeddings barely separate negation ("needs a response soon" 0.84 against "does NOT need" 0.81).
- `choice` ignores `instructions` unless `choiceInstructions: true` is set.
- `confidence` is calibrated only after about 100 labels per question, or about 20 with `crossfitCalibration`.

**Closest other things, and why they do not fit.**

| Candidate | Verdict |
| --- | --- |
| `@ruvector/router` 0.1.32 (semantic routing, HNSW) | Intent matching with no typed multi-field output or abstain. The typesafe bench records a recall defect in its kNN path. Not a fit. |
| `@ruvector/tiny-dancer` 0.1.22 (FastGRNN router) | Routes agent requests. Not a text classifier. Not a fit. |
| `@metaharness/router`, `ruvector-nervous-system` | Not examined in depth. No sign of a typed classifier. |

## 2. Fit against our task

Task: four typed fields per review (sentiment with 5 labels, plus three fields with yes / no / insufficient_information), 60 labelled reviews. Gold counts for `insufficient_information` are 2, 1, 6 and 1 items across the four fields.

| Question | Answer |
| --- | --- |
| Four typed fields with a label vocabulary? | Yes. Each field is a `choice` question whose option ids are our labels. This is the same shape the native Jev-style adapters in NATIVE_DECISIONS.md already use. |
| An "insufficient information" or "off-topic" option? | An ordinary option is weak (README: 17% of off-topic caught, 24% false alarms). The engine-level `catchAll` option plus a threshold is better (78% caught at 14% false alarms on CLINC150), but the threshold must be tuned per question and does not transfer. The `abstain` mass ranks off-topic input well (AUROC 0.90 to 0.97). |
| Needs training data? | Zero-shot is weak and uncalibrated. A probe needs 4 or more labels per option. Our 60 reviews hold 1 to 6 `insufficient_information` examples per field, so that class cannot be learned or calibrated. Cross-validation on 60 items would be very noisy. |
| Deterministic? | Yes. Frozen embedder and closed-form heads, no sampling. |
| Calibrated? | Not at our scale. `calibrated: false` until the held-out slice reaches 20 items. |
| Cost per decision? | No money. The README gives native p95 of about 24 ms. Needs about 130 MB of weights and a local build. |
| Reads meaning? | Only through embedding similarity. It cannot handle negation or the resolved-versus-unresolved logic behind follow_up_needed. Expect it to be weakest on exactly our hard cases. |

**Adapter effort.** NATIVE_DECISIONS.md defines the contract: one input record per request, one typed choice question per categorical field, option ids and descriptions from the task, reference labels kept outside the capsule. A local adapter maps a record to `ts.decide(state, questions)` and stores `probabilities` per field. Work needed:

- A new local adapter kind with no network, no credential and no billing snapshot.
- Label descriptions, which current task files lack. The docs say adapters do not invent them, so reviewed rubric text must be supplied.
- A rule that any `catchAll` threshold is tuned on the development split only.
- A report group of `decision`.

Estimate: about one day to wire and test, plus the one-off ONNX build.

## 3. Feasibility smoke

SMOKE_PLACEHOLDER

## 4. Verdict

VERDICT_PLACEHOLDER
