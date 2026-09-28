# Repeat checkpoint, 29 September 2026

Six additional Codex configurations have completed the first fresh P0/P1/P2 pass: GPT-5.6 Luna extra-high, GPT-6 Astra medium, GPT-5.6 Terra low and medium, and GPT-6 Sol low and Luna low. These are **18 of 54 planned full runs**, each with 60 reviews. The second passes have started; none of these six three-pass series is complete. The [source-bound report](../public-site/codex-fresh-repeats.json) separates them from historical observations.

Alex OpenJev 4B has completed its first native P0 pass with 60 valid outputs. It agrees with all four provisional reference labels on **39/60 reviews**. Individual agreement is 49/60 for sentiment, 57/60 for follow-up, 47/60 for serious concerns and 57/60 for testimonial potential. Alex 0.8B scored 3/60 all-field agreement in each of its three completed passes. The first 4B result is substantially different, but its remaining two passes are needed to measure within-model variation. Its second smoke has started. See the [native report](../public-site/alex-native-repeats.json). These local client durations are not measurements of pure inference time.

The evidence and reports were pushed in commit `17f2aa4`. Its commit subject says sixteen Codex passes; the committed report actually contains eighteen, three per configuration. This checkpoint corrects that descriptive count without rewriting published Git history.

The publication failure in the earlier fresh-Codex update was a Linux test-fixture path issue: the synthetic fixture attempted to use the macOS `/private/tmp` directory. Commit `6b6c06c` corrected the test fixture while preserving the frozen inference controller. Deployment `36492340673` succeeded and the live twelve-run feed was byte-verified before this newer eighteen-run update. Publication of the newer evidence must be verified separately.

The [small-Qwen hosted-route audit](../results/route-audits/legacy-six-local-20260929/README.md) preserves a 460-entry OpenRouter catalogue response. No exact Qwen3 0.6B, Qwen3 1.7B or Qwen3.5 4B listing was found. The raw hash and a punctuation-normalized family search were independently checked. This is a dated availability observation; local dispatch still requires current route and runtime checks. Offline preparation for the six missing local configurations is underway, with no new local Qwen inference launched.

The [full-scope audit](REPEAT_SCOPE_GAPS_2026-09-28.md) remains authoritative for work outside the original 55-series matrix. The native/calibration/generated specialist experiments, remaining small-model repeats and hosted repeats are still required. OpenRouter remains capped at $10 and TypeSafe at $1. The proposed $17 OpenRouter total is not yet authorized. No new paid hosted wave was dispatched in this checkpoint. The disputed reference labels remain unchanged, and classification-bench remains owned by the separate task.

## What the first two passes show

The six added Codex configurations now have two complete P0/P1/P2 passes: 36 full runs. The [immutable report snapshot](https://github.com/adambkovacs/candidate-experience-benchmark/blob/c8212df/public-site/codex-fresh-repeats.json) has SHA-256 `4bc773e90d3a8bbe656dbdb328d3c2ffd655aa446543ebe6e81746a0bf0d07fc`. Third passes remain required.

For three of the six configurations, the direction of the P1-versus-P0 score difference reverses between passes. GPT-5.6 Luna extra-high and Terra medium move from one fewer all-field match to one more; GPT-6 Sol low moves from one more to two fewer. A one- or two-review difference in a single pass therefore does not establish a consistent benefit from that prompt condition. This is a descriptive observation, not a significance test or a causal estimate.

| Configuration | P1 minus P0, pass one / pass two | Reviews with any label changed between passes, P0 / P1 / P2 |
| --- | --- | --- |
| GPT-5.6 Luna extra-high | -1 / +1 | 3 / 3 / 2 |
| GPT-6 Astra medium | +1 / +1 | 0 / 0 / 1 |
| GPT-5.6 Terra low | +2 / +1 | 4 / 1 / 2 |
| GPT-5.6 Terra medium | -1 / +1 | 5 / 1 / 3 |
| GPT-6 Sol low | +1 / -2 | 3 / 3 / 3 |
| GPT-6 Luna low | -2 / 0 | 4 / 8 / 7 |

Each comparison uses the same 60 reviews. A changed review means at least one of its four predicted labels differs; it does not necessarily mean the new answer is less accurate. The reference labels are provisional, including the disputed cases described in the reference-review document. These repeated responses do not add independent reviews, and serving revisions or caching are not fully observable. The third pass is needed before the declared three-pass ranges are complete.

DeepSeek Flash off has also passed its first smoke inspection and begun the first development phase under the bounded $0.46 child allocation. That allocation remains within the original $10 cap; it is not $0.46 of observed spending. Alex 4B's second native pass continues separately. See the [DeepSeek admission](DEEPSEEK_FRESH_REPEAT_ADMISSION.md) and [local-Qwen preparation](LEGACY_QWEN_FRESH3_ADMISSION.md).

## Fresh hosted results and subscription progress

The six additional Codex configurations have 50 of 54 planned full conditions closed in this publication. GPT-6 Luna low and Sol low each have all nine complete. The four remaining conditions belong to Luna 5.6 xhigh, Astra 6 medium, and Terra 5.6 low/medium. These counts describe this additional wave, not the entire repeat roster.

The fresh DeepSeek V4.1 Flash series has its first P0 and P1 conditions closed, each with 60 valid responses. All-four agreement is 48/60 for P0 and 47/60 for P1. P1 improves follow-up agreement from 59 to 60 and testimonial agreement from 55 to 57, while sentiment agreement falls from 52 to 50; serious-concern agreement stays at 57. A one-review aggregate difference from a single paired pass does not establish a prompt benefit or harm. Seven of the nine conditions remain unfinished at this checkpoint.

Provider-reported development charges are $0.00275230 for P0 and $0.00297068 for P1. Their input/output token counts are 84,217/2,793 and 94,837/2,558. Summed client HTTP durations are 389.88 and 344.31 seconds; these include network and service overhead and are not pure inference times. Smoke calls are excluded from these development totals.

The new public DeepSeek repeat view preserves the historical configuration separately. Each published phase is bound to an immutable prefix of its settled child budget, so later live ledger writes cannot change the evidence behind published results. Frozen manifest paths are resolved relative to their recorded original checkout and verified after relocation; the original manifest bytes are retained.
