# SemIf native repeat review, 28 September 2026

Verdict: **APPROVE for the frozen native P0 protocol**. This review does not admit a live stage. Each stage still requires its exact receipt, and all six Laya phases must close before SemIf loads the model.

Reviewed controller SHA-256: `e81805d1ac4730181795a80a32a12c6f03004136624faaf36f9e05ca80f3be9d`. Reviewed manifest SHA-256: `26cc75f1676ddf72bd9730e43b0e49cf5256427c4e1ec4549fc9ea513b7372c5`.

The direct, serial and shared calls match the native branches in the historical specialist runner. The backend sets the allocator cache limit and evaluation mode. Inputs contain only review IDs and text; the policy excludes simulated routing references. Asset, source, runtime, token-signature and option-order checks bind execution to the historical first pass. Exclusive stage claims, durable start markers, raw-before-projection writes and the common native lock prevent silent replay and overlapping native execution. Started but unfinished records remain uncertain.

Independent verification passed: manifest reconstruction and nine offline tests under the pinned specialist interpreter. System Python explicitly skips these integration checks when its native prerequisites are absent. The tests use fake scoring; this verification made no inference call.

- **RESIDUAL:** the distribution validator checks finiteness and normalization but does not separately require each probability to lie between zero and one. The frozen backend supplies softmax probabilities; this does not block that route, but a future backend must validate its probability contract.
- **RESIDUAL:** local client durations include runtime and host effects. These repeats measure categorical output stability and cannot establish isolated model inference speed.

No confirmed blocking finding remains. See the [admission plan](SEMIF_NATIVE_REPEAT_ADMISSION_2026-09-28.md) for execution gates and the [native eligibility audit](NATIVE_SPECIALIST_REPEAT_AUDIT_2026-09-28.md) for the separate specialist scope.
