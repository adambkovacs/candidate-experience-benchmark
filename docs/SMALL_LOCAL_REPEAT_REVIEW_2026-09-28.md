# Small local fresh-series review, 28 September 2026

Verdict: **APPROVE for the frozen fresh-series protocol**. Live admission still requires the exact-route check, free common native host lock, loaded-model/cache evidence and a separately inspected three-record smoke before each development phase. No inference was performed by this review.

The root review verified controller SHA-256 `e2f62a336b9dd71c12cb94bea16624c4be6d5f9c7c4e087f5f5d6edb7e084375`, wrote and verified manifest SHA-256 `0cfc584a3a5f6f718354cdf5ca5e37170f80b23e96542e2ce79d9b69f55020ff`, and independently passed all eleven offline tests. The old unexecuted manifest remains preserved.

No confirmed BLOCKING findings remain in the reviewed controller. The earlier cache check accepted a declared setting without actual load evidence; the revised guard requires the current model instance, exact artifact path and observed enabled cache with an 8,192 MiB limit. Tests cover cache mismatch, stale instance linkage, receipt mismatch, failure preservation, smoke admission and exclusion by the common process lock.

**RESIDUAL — loaded engine version is unavailable:** the installed SDK/CLI exposes the selected backend but not a verified engine version tied to the loaded instance. The attestation records that distinction. All five configurations therefore use three new matched passes under the frozen observable settings; historical passes remain separate observations. The series cannot establish that hidden runtime behavior was identical.

**RESIDUAL — uncontrolled seed and timing:** sampling has no recorded deterministic seed. Client-observed request durations are not isolated inference time. Repeated outputs measure observed variation on the same 60 reviews, not independent test cases.

See the [eligibility audit](SMALL_LOCAL_REPEAT_ELIGIBILITY_2026-09-28.md), [controller](../scripts/small_local_repeat_admission.cjs), and [frozen manifest](../results/repeatability-v1/small-local-v1/manifest.json). This decision does not authorize hosted spending or a different model route.

## Pre-dispatch hashing correction

The first live preflight found a BLOCKING implementation defect before a request or phase claim: Node could not read the 3.43 GB GGUF into a single buffer. The helper now computes SHA-256 in 1 MiB chunks and closes its descriptor reliably. All thirteen tests passed, including hashing the actual installed 3,427,880,384-byte artifact to its pinned digest and comparing a multi-chunk fixture against direct hashing.

The corrected controller SHA-256 is `3076927fda41ca9922f2a56b401d55ffee2e67462d06af70c7cfecaf8c21a7e8`; the refrozen, still-unexecuted manifest is `48ff89983f1acb5b8450c0ed8698cae127ec6d533f324be904a3f01a0bdd3619`. The prior manifest is retained as `manifest.before-streaming-hash-review.json`. Verdict: **APPROVE** for this correction; inference still requires the existing stage gates. No model, prompt, sampling or scoring control changed.
