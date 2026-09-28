# Hosted Gemini repeat waves: admission inventory

## Execution update, 28 September 2026

The four configurations proposed below have now completed and their allocations are closed. Their added repeats and smokes cost $1.928587 in returned charges. The master ledger accounts for $8.62592168150, leaving $1.37407831850 under $10. See the [verified Gemini findings](GEMINI_REPEAT_FINDINGS_2026-09-28.md). Gemini 3.8 medium retains its token-truncated batches; completion does not mean all outputs were valid.

The two remaining intact high-effort triples have a combined historical two-pass proxy of $2.305357, exceeding that headroom by $0.93127868150 before Qwen's never-sent suffix or Gemini 3.8 low. The Qwen suffix has a separate conservative bound of $0.5382144 and remains under controller review. An aggregate cap increase to $15 has been requested but is not yet authorized. The current cap remains $10.

The proposal and balance below are retained as the pre-wave planning snapshot. They are not the current dispatch status or balance.

This is a proposal, not an allocation or a dispatch receipt. The [current goals](CURRENT_GOALS.md) and [coverage matrix](REPEAT_COVERAGE_MATRIX.md) leave seven paid OpenRouter Gemini configurations unfinished: six intact first-pass triples and Gemini 3.8 Flash low, whose historical P0 needs review. The shared [paid ledger](../results/openrouter-paid-budget.jsonl) currently accounts for **$6.69733468150** under $10, leaving **$3.30266531850** with no active repeat partition. Re-read that ledger before any allocation.

The table uses each candidate's saved P0, P1 and P2 v3 manifests and seven attempts per condition: one smoke batch of three, then six development batches of ten. Their payloads pin `google-ai-studio`, disable fallback, tools, web and response healing, and request the listed reasoning effort. The first-pass cost is the sum of saved `observed_cost_usd` across all 21 batches. Twice that value is a **planning proxy** for repeat 2 and repeat 3, not a future charge or reservation guarantee. The client bound sums each frozen request's `reserve_usd` twice; it deliberately permits much more than historical usage. All amounts are USD.

| Remaining configuration | Exact model and effort | Saved first-pass cost | Two-pass cost proxy | Two-pass client reservation sum | Next wave |
| --- | --- | ---: | ---: | ---: | --- |
| `gemini31-pro-preview-low-p0-openrouter-v3` | `google/gemini-3.1-pro-preview`, low | 0.251636 | 0.503272 | 9.733652 | Include; proposed partition ceiling 0.80 |
| `gemini31-pro-preview-high-p0-openrouter-v3` | same model, high | 0.801008 | 1.602016 | 9.733736 | Queue; current cap cannot cover all seven at historical rates |
| `gemini36-flash-medium-p0-openrouter-v3` | `google/gemini-3.6-flash`, medium | 0.225333 | 0.450666 | 3.13396050 | Include; proposed partition ceiling 0.60 |
| `gemini37-flash-medium-p0-openrouter-v3` | `google/gemini-3.7-flash`, medium | 0.18794175 | 0.37588350 | 3.13396050 | Include; proposed partition ceiling 0.55 |
| `gemini37-flash-high-p0-openrouter-v3` | same model, high | 0.35167050 | 0.70334100 | 3.13389750 | Queue pending later ledger balance |
| `gemini38-flash-medium-p0-openrouter-v3` | `google/gemini-3.8-flash`, medium | 0.288873 | 0.577746 | 3.13396050 | Include; proposed partition ceiling 0.75 |
| `gemini38-low-p0-openrouter-v2` | `google/gemini-3.8-flash`, low | Not an admitted complete triple | Unknown | Unknown | Hold for first-attempt P0 review |

The four proposed ceilings sum to **$2.70**, below current headroom by **$0.60266531850**. Their measured two-pass proxy is **$1.90756750**. These ceilings are suggested *maximum child allocations*, not reservations already made. Sequential reservation and settlement can fit despite the much larger static sum of per-call bounds; if actual usage grows, the child partition must stop before its ceiling, preserve the stopped position, and avoid replay. Any unknown cost remains held at its reservation bound until explicit reconciliation. The historical proxy assumes the same price, usage and no route change; it gives no provider-side spending guarantee.

Across the six intact triples, the two-pass historical-cost proxy is **$4.21292450**, exceeding current headroom by **$0.91025918150** before the unresolved Gemini 3.8 low triple. Their full conservative client reservation sum is **$32.00316700**. The six therefore cannot all receive even historical-rate funding at once under this cap. Gemini 3.8 low's saved P1 and P2 smoke and development attempts cost $0.05323875 in their first pass, but no complete-series estimate is admitted until P0's interrupted first attempt, route identity, and continuation are reviewed. It remains in the roster; no failure or retry is silently recast as an ordinary success.

## Route and control check

On 2026-09-28, unauthenticated [OpenRouter model metadata](https://openrouter.ai/api/v1/models) listed all four exact model IDs and the required low, medium or high effort. The [3.1 Pro endpoint](https://openrouter.ai/api/v1/models/google/gemini-3.1-pro-preview/endpoints), [3.6 Flash endpoint](https://openrouter.ai/api/v1/models/google/gemini-3.6-flash/endpoints), [3.7 Flash endpoint](https://openrouter.ai/api/v1/models/google/gemini-3.7-flash/endpoints), and [3.8 Flash endpoint](https://openrouter.ai/api/v1/models/google/gemini-3.8-flash/endpoints) each returned one `google-ai-studio` endpoint with status `0`, the exact model ID, 1,048,576 context and 65,536 maximum completion tokens. Those endpoints still advertised the saved token rates: Pro $2/M input and $12/M completion and internal reasoning; Flash $0.75/M input and $3.75/M completion and internal reasoning. This read used no key and made no inference request. Recheck the complete endpoint controls, prices and returned identity at admission; catalog presence alone is not dispatch authorization.

## Implementation boundary before a wave

Extend the existing [Gemini low repeat controller](../scripts/gemini_repeat_study.py) through a **new parameterized roster wrapper** for these frozen v3 triples. Keep the existing low manifests and controller frozen. The wrapper should select an exact `(configuration ID, model, effort)` row, reconstruct each saved manifest/request/attempt hash with [v3 payload and bound functions](../scripts/gemini_openrouter_batch_v3.py), and reuse the established [repeat wave capture and budget controls](../scripts/openrouter_repeat_wave.py). The original P0 ID remains the parent for P1/P2. Preserve repeat 2 order P1→P2→P0 and repeat 3 order P2→P0→P1, smoke inspection before each development phase, batch 10, no retries, raw bytes before parse, no fallback, and separate frozen plan and phase-review receipts. Reserve from one reviewed child partition at a time under the shared master cap; do not silently spend the proposed ceilings.

Before a real run, review the new wrapper, each immutable plan and source hash, the selected partition ceiling and current ledger, fresh unauthenticated route/pricing metadata, and each phase's smoke and development evidence. Score offline with reference labels only after inference evidence is closed. This document creates no plan, key read, allocation, provider call, or result.
