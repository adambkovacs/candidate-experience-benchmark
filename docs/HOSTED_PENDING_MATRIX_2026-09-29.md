# Hosted repeat work pending review, 29 September 2026

## Current preparation and execution status

Updated after publication commit `cc7bc217` on 29 September. The historical 02:25 UTC snapshot below is retained for provenance; its preparation and endpoint statuses are superseded by this section.

| Remaining configuration | Verified progress | What prevents the next dispatch |
| --- | --- | --- |
| DeepSeek low | P0 and P1 are closed and published. P2 development is running after an inspected smoke, within the existing $0.25 child. | Each later stage still needs predecessor verification, smoke inspection where applicable, and a fresh exact-route check. The full nine-run series is unfinished. |
| Qwen27 medium and xhigh | Six fresh-pass plans and the execution controller are committed. Fourteen combined tests and independent review pass. | Proposed children of $1.00 and $0.80 are unfunded. Stage-specific review and live route checks remain required. |
| Gemma 26B reasoning-on | Three fresh-pass plans and the corrected controller are committed. Eleven combined tests and independent review pass. Raw response files are ignored. | Proposed $0.40 child is unfunded; no fresh inference has run. |
| Qwen 35B reasoning-on | Three fresh-pass plans and the reviewed executor are committed through `75595754`. | Proposed $1.50 child is unfunded; stage review and fresh route checks remain required. |
| DeepSeek high | Three fresh-pass plans and the reviewed executor are committed through `24d3e3e5`, with 26 combined tests passing. | Needs fresh live route checks, stage review and funding for the proposed $0.90 child. |
| Mistral 119B none and high | Historical failed smokes remain preserved; six offline plans are reviewed and committed in `9ba898d7`. | Execution admission, provider capacity evidence and funding remain outstanding. No observed whole-series cost proxy exists. |
| Gemini 3.1 Pro high | Reviewed wrapper and frozen plans exist. | Proposed $2 child is unfunded. |

No new allocation is made by this checkpoint. The aggregate cap remains $10. The [budget reconciliation](BUDGET_RECONCILIATION_CHECK_2026-09-29.md) leaves $0.04151065850 unallocated, separately from the already funded DeepSeek child. Unknown-charge bounds remain reserved. The requested increase to $17 total has not been approved.

For exact plan and cost evidence, see the admissions for [Qwen27](QWEN27_FRESH_REPEAT_ADMISSION_2026-09-29.md), [Gemma](GEMMA26_ON_FRESH_REPEAT_ADMISSION_2026-09-29.md), [Qwen reasoning-on](QWEN36_ON_FRESH_REPEAT_ADMISSION_2026-09-29.md), and [DeepSeek high](DEEPSEEK_HIGH_FRESH_REPEAT_ADMISSION_2026-09-29.md). Completed Qwen reasoning-off work remains preserved with its interruption limitations; it is not queued for a cleaner rerun.

## Historical snapshot at 02:25 UTC

The OpenRouter ledger was read at 02:25 UTC. Its $10 cap accounts for $9.95848934150, leaving $0.04151065850 unallocated. It has no pending attempt reservations or blocked flag. The only active partition is the existing $0.25 `deepseek-low-fresh3-20260929` child. This inventory makes no allocation and assumes no release from that child.

No new full hosted series is currently ready to dispatch within free capacity. DeepSeek low is already prepared and funded, but its exact `open-inference/fp4` endpoint was previously returned with status -2. Keep it stopped until a fresh read returns status 0 and all frozen route fields match. The other live routes below do not have fresh matched-series manifests/controllers in this inventory. Catalog presence is not admission.

## Later admission checkpoint

The table below is the 02:25 UTC snapshot. Subsequent work has changed preparation status:

- Gemma 26B reasoning-on now has reviewed fresh-three manifests and an execution controller, with ten offline tests passing. Its proposed $0.40 allocation remains unfunded. See [the admission](GEMMA26_ON_FRESH_REPEAT_ADMISSION_2026-09-29.md).
- Qwen27 medium and xhigh now have six reviewed fresh-pass manifests. Four tests and independent reconstruction checks pass. They still need execution controllers, fresh route checks and funded allocations; proposed allocations are $1.00 and $0.80. See [the admission](QWEN27_FRESH_REPEAT_ADMISSION_2026-09-29.md).
- DeepSeek low became reachable, but its endpoint input price dropped from $0.10 to $0.03 per million tokens. The unchanged runner rejected this metadata difference before dispatch. A versioned price-only admission is being prepared; no requests have been sent under changed pricing. See [the exact check](../results/repeatability-v1/deepseek-low-fresh3-v2/live-endpoint-check-2026-09-29.md).

These updates make no new budget allocation and do not change the $10 cap.

## Pending exact configurations

| Exact configuration | Current exact route | Prior evidence and cost bound | Current disposition |
| --- | --- | --- | --- |
| `openrouter-paid-qwen3.8-27b-medium` | `qwen/qwen3.8-27b` / `deepinfra/bf16`, medium; endpoint status 0 on 29 Sep | Historical P0 retains 59 valid and one transport failure with a $0.047001600 unknown bound. P0 known development-plus-smoke proxy for three passes is $0.068431875, excluding P1/P2 and smokes for those conditions. Full fresh-series estimate unknown. One-call reserve alone exceeds free headroom by $0.00549094150. | Needs a separate matched-three plan and reviewed child; not affordable at current headroom. Preserve DEV-048 and its bound. |
| `openrouter-paid-qwen3.8-27b-xhigh` | Same model/provider; xhigh; endpoint status 0 | Historical P0 retains 59 valid and one output failure. Three-pass P0-only known proxy is $0.064279050, before remaining prompts and smokes. Full estimate unknown. One-call reserve $0.047001600 exceeds headroom by $0.00549094150. | Needs separate plan/review and additional headroom. Preserve DEV-013. |
| `openrouter-paid-qwen36-35b-a3b-on` | `qwen/qwen3.6-35b-a3b` / `akashml/fp8`, on; endpoint status 0 | Existing P2 has six service failures and 54 valid records. Full fresh matched-three estimate not established. Conservative one-call bound $0.0299008 fits, but not proof that a full series fits. | First reconcile historical eligibility, then prepare a distinct matched-three plan and budget. Preserve all six failures. |
| `openrouter-paid-qwen36-35b-a3b-off` | Same model/provider, off; endpoint status 0 | Fresh v2 continuation is closed, but remains descriptive because of its interrupted/suffix schedule. Earlier three-set known-charge proxy plus one-call bound was $0.1126363; this is not a future upper bound. | All nine scheduled condition/pass combinations are accounted for. Preserve the two failures and descriptive limitation; do not automatically rerun completed requests to obtain a cleaner series. A further experiment would require a separate explicit decision. |
| `openrouter-paid-gemma4-26b-a4b-on` | `google/gemma-4-26b-a4b-it` / `deepinfra/fp8`, on; endpoint status 0 | Historical P0 known development plus smoke was $0.02201589; ×3 gives $0.06604767 before P1/P2 or their smokes. Full estimate unknown. The per-call bound is below free headroom, but the P0-only proxy alone exceeds it by $0.02453701150. | Cheapest endpoint-ready candidate by historical price, but not a dispatch option now. Prepare the new matched-three plan offline; dispatch requires additional verified capacity. Preserve DEV-022. |
| `openrouter-paid-deepseek-v41-flash-high` | `deepseek/deepseek-v4.1-flash` / `open-inference/fp4`, high; exact endpoint status -2 | Historical P0 known development-plus-smoke proxy for three passes is $0.05667546; full estimate unknown. One-call bound $0.1069056. | Blocked by endpoint status and current one-call reserve; keep stopped. |
| `openrouter-paid-deepseek-v41-flash-low` | Same model/provider, low; exact endpoint status -2 | Separate v2 fresh-three child of $0.25 is already active. Historical cost proxy plus one-call bound was $0.22438341, a planning margin only. | Next prepared dispatch if status returns 0 and frozen metadata matches. Do not relaunch, change route, or add budget while status is -2. |
| `openrouter-paid-mistral-small4-119b-none` | `mistralai/mistral-small-2603` / `mistral/zdr`, none; endpoint status 0 | Prior smoke attempts returned HTTP 429; full $0.04177920 bound retained as unknown for each relevant attempt. No development cost estimate exists. | Historical failure remains. One reserve alone exceeds free headroom by $0.00026854150. Recheck provider capacity only after a separately reviewed plan and sufficient headroom. |
| `openrouter-paid-mistral-small4-119b-high` | Same model/provider, high; endpoint status 0 | Prior smoke returned HTTP 429; full $0.04177920 bound retained. No development cost estimate exists. | Same status as none: not funded, prior failure preserved. |
| `gemini31-pro-preview-high-p0-openrouter-v3` | `google/gemini-3.1-pro-preview` / `google-ai-studio`, high; endpoint status 0 | Reviewed high-wave wrapper and frozen historical manifests exist. Two-pass historical cost proxy is $1.602016, excluding smoke and future usage variability. First planned batch reservation is well above current headroom. | Prepared but unaffordable; proposed $2 child is not allocated. No cap increase is authorized. |

## Budget and next admission

The closest candidate by historical unit cost is Gemma 26B on. Its route is present, but the three-pass P0-only proxy exceeds currently free capacity by $0.02453701150 and omits P1/P2, their smokes, and future usage variance. That difference is a minimum against this partial proxy, not a sufficient full-series cap request. A defensible full amount requires a separately reviewed matched-three plan with complete request reservations and a historical charge proxy.

The next already-prepared series remains DeepSeek low, conditional on exact endpoint status returning to 0 and all frozen model, provider, pricing, and control metadata matching. Its existing $0.25 child is active, so it needs no additional allocation if its controller admission succeeds. Until then, no other hosted exact configuration in this roster is both fully planned and fundable from the $0.04151065850 currently unallocated.

The live route check used unauthenticated model/endpoint metadata only; it made no inference calls. For direct verification, see the [OpenRouter model catalog](https://openrouter.ai/api/v1/models) and endpoint records for [Qwen 3.8 27B](https://openrouter.ai/api/v1/models/qwen/qwen3.8-27b/endpoints), [Qwen 3.6 35B A3B](https://openrouter.ai/api/v1/models/qwen/qwen3.6-35b-a3b/endpoints), [Gemma 4 26B A4B](https://openrouter.ai/api/v1/models/google/gemma-4-26b-a4b-it/endpoints), [DeepSeek V4.1 Flash](https://openrouter.ai/api/v1/models/deepseek/deepseek-v4.1-flash/endpoints), [Mistral Small 2603](https://openrouter.ai/api/v1/models/mistralai/mistral-small-2603/endpoints), and [Gemini 3.1 Pro Preview](https://openrouter.ai/api/v1/models/google/gemini-3.1-pro-preview/endpoints). The [dated scope gaps](REPEAT_SCOPE_GAPS_2026-09-28.md), [small hosted admission](SMALLER_HOSTED_CHILD_ADMISSION.md), and [Gemini high-wave review](GEMINI_HIGH_REPEAT_WAVE.md) retain the historical eligibility and planning evidence.

## Subsequent execution admission

The exact lower-price DeepSeek continuation was independently reviewed, committed in `0119258a`, and launched for the previously unsent phase-02 development stage within its existing funded child. The old availability/price blockers above describe earlier checks. This does not imply the new stage is finished. Qwen reasoning-on now also has reviewed offline fresh-three plans in `5d0a1c44`; its proposed $1.50 child remains unfunded and no fresh request has run.
