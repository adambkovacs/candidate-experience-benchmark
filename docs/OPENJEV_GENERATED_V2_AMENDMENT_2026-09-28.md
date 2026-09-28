# OpenJev generated request-byte amendment

The v2 controller corrects a pre-dispatch serialization error. No v1 generated
smoke or development stage ran, and no completed request is being repeated.

The v1 manifest writer sorted JSON object keys. Its saved wire hash described
the original insertion order, but execution serialized the reloaded object.
All 360 saved requests therefore failed the execution hash check before HTTP.
The controller would have recorded a started attempt before finding that error.

V2 stores the exact intended request body as a string. It verifies the string's
hash, its parsed payload, and the sorted-payload request hash for the entire
selected stage before creating a claim or starting the server. It repeats the
check at each request boundary and sends those exact bytes.

All 360 intended v1 wire hashes are preserved. Model, route, prompts, controls,
input order, schedule, historical eligibility and runtime declarations are
unchanged. The original v1 controller and manifest remain in Git. Future fresh
stages use the separate v2 directory and receipt kind.

Verified artifacts:

- [Controller](../scripts/openjev_generated_repeat_admission_v2.py): SHA-256 `85b4674a1c70d709dae07fe6a0207b5f7b1c716a1c2990ebbbebbcb70b9bf35e`.
- [Manifest](../results/repeatability-v1/openjev-generated-fresh-v2/manifest.json): SHA-256 `1f0ac6d4ed4ccc31ed1b2fa4b9c570f716e202075512f78e5f212427efaa7216`.
- [Regression tests](../tests/test_openjev_generated_repeat_v2_wire.py): four passing tests cover all request bodies, persisted-manifest validation, rejection before a claim/server start, and exact transport bytes.

Root pinned-runtime verification rebuilt the manifest exactly. Independent
review: **APPROVE**, with no confirmed BLOCKING finding. **RESIDUAL:** the
server does not independently expose live rendered token IDs or loaded
settings; offline preflight and launch observations remain qualified.

This amendment prepares execution. All eighteen development phases remain
pending. Each stage still requires its own root review, the shared GPU lock,
and inspection of the smoke before development. The report builder is reviewed
separately and cannot turn an unexecuted or partial stage into a completed score.
