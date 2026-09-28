# OpenJev generated repeat admission

**Dispatch blocked, 2026-09-28:** subsequent offline review found that the v1
manifest serializes payload keys in sorted order, while the execution check
expects the original insertion-order wire hash. Reloading the saved manifest
therefore fails the request-byte check before HTTP dispatch. Do not execute
this v1 controller. No generated stage has run. The [reviewed v2 amendment](OPENJEV_GENERATED_V2_AMENDMENT_2026-09-28.md)
preserves the intended wire bytes and passes persisted-manifest regressions;
use its separate controller and manifest for future stage admission. Original
controller and manifest bytes remain preserved. This finding supersedes the
earlier v1 approval recorded below.

The generated-off and generated-on comparisons use a fresh matched three-pass
series. The historical P0/P1/P2 records remain observational: the original P0
wire body and rendered token IDs were not saved, so they cannot serve as a
verified first pass. Each fresh pass covers the same 60 input-only records in
the frozen P0/P1/P2 rotation. The manifest and smoke/development receipts bind
the exact request payloads, source checkout, model files, runtime versions and
historical offline token preflight. No reference labels or previous predictions
enter a request.

The historical offline preflight computed `rendered_token_ids_sha256` with the
pinned tokenizer and OpenJev prompt renderer. The fresh manifest and raw rows
call this `offline_rendered_token_ids_sha256`. The HTTP server does not return
its rendered token IDs. The controller checks the returned model name and
prompt-token count against the offline preflight; those checks do not measure
the live token sequence. The original unexecuted manifest is retained as
[the prequalification candidate](../results/repeatability-v1/openjev-generated-fresh-v1/manifest.candidate-before-attestation-qualification.json).

The controller launches the pinned OpenJev source with the native controller's
configured environment and observes `/health`. That environment omits
`OPENJEV_UPSTREAM_MODEL`, so pinned `Settings` defaults its internal
`upstream_model` to `dgemma`. The local MLX chat path builds its prompt from
messages and the thinking flag and labels its reply `diffusiongemma-26b`.
The stage's `server-attestation.json` records the configured environment,
source and artifact bindings, process ID and observed health. It does not
claim to have measured loaded settings, engine version, or live token IDs.
Historical generated execution used an explicit `diffusiongemma-26b` server
setting and a loaded-settings check; that distinction remains visible.

Admission remains one phase at a time under the shared GPU lock. A root-reviewed
stage receipt precedes a three-record smoke; development requires an inspection
of those saved raw responses. Each request gets one durable start event, then
bounded raw bytes before parsing. An ambiguous attempt stops the stage without
automatic replay. A complete HTTP response with `finish_reason: length` is
retained as `invalid_output` and the stage continues; an incomplete body or an
unsupported finish reason stops it as unknown. There are no live stages in this
admission update.

Source traces: [generated admission](../scripts/openjev_generated_repeat_admission.py),
[native launch settings](../scripts/openjev_native_repeat_admission.py),
[offline preflight](../scripts/openjev_prompt_preflight.py),
[historical generated execution](../scripts/openjev_prompt_execution.py),
and the pinned checkout's `openjev/config.py` and `openjev/chat.py`.

Root review: APPROVE, with no confirmed BLOCKING findings. Eight offline tests pass and pinned verification reproduces manifest SHA-256 `950727534e2105de2d42b501e23dabe98742d6010bd86e1a9d064a3dde8a17c1`. RESIDUAL: the server does not expose live rendered token IDs or independently measured loaded settings; offline token hashes and launch observations remain explicitly qualified. All eighteen development phases remain pending.
