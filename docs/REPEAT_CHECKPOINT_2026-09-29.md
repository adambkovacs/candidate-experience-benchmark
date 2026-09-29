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

## Final six-series Codex milestone

The six additional Codex configurations now have all **54 of 54** planned fresh condition/pass results closed, nine per configuration. Each result has 60 valid classifications of the same synthetic reviews. The [final source-bound feed](../public-site/codex-fresh-repeats.json) has SHA-256 `335d7676d2d81e2a9eb258d34acdc808a428a3faff2adaedde904ccdcf5631dd`. This closes the additional wave described above; the earlier 18/54, 36/54 and 50/54 counts remain dated progress snapshots.

The [six-series findings](CODEX_FRESH_REPEAT_FINDINGS_2026-09-29.md) give per-field ranges, matched P1/P2 deltas, changed-review counts and reference-class confusion. Neither P1 nor P2 strictly beat P0 on all-four agreement in all three passes for any of the six configurations. P1 switched between gains and losses in four of six. These comparisons are descriptive observations on repeated reviews with provisional labels; they do not establish statistical significance or a general prompt effect. Commit and live-site publication of this final feed require separate verification.

## Alex 4B second native pass

Alex OpenJev 4B has two closed 60-review native passes. Both match all four provisional reference fields on 39/60 reviews, with field agreement of 49/60 sentiment, 57/60 follow-up, 47/60 serious concern and 57/60 testimonial potential. No review changed any classification between these two passes. The third pass is still required; two unchanged passes are not a completed three-pass study.

The second pass recorded 4,422.31 seconds of client prediction time and 1,251,194 native NLI input token positions across the 14 hypotheses per review. Those positions are not billed API tokens, and the duration includes local runtime overhead. Isolated inference time and attributable local cost remain unavailable.

## DeepSeek five-condition checkpoint

Five of nine fresh DeepSeek conditions are closed. Pass one scored 48/60, 47/60 and 43/60 all-four agreement for P0, P1 and P2. Pass two has P0 at 49/60 and P2 at 45/60; P1 is still running at this checkpoint. P2 changed two reviews between passes: sentiment on DEV-009 and testimonial potential on DEV-020. The two-review score increase between identical prompts is another reason to wait for all three passes before interpreting small prompt differences. These are the same 60 reviews, with unchanged provisional references.

## DeepSeek eight-condition checkpoint

Eight of nine fresh DeepSeek Flash off conditions are closed, each with 60 valid outputs. P1 now has all three passes: 47/60, 47/60 and 45/60 all-four agreement, with three reviews changing at least one label across passes. P2 scores 43/60, 45/60 and 46/60, with four reviews changing. The three-review P2 range occurred with unchanged prompts and controls; it is observed repeat variation, not an improvement caused by a prompt change. The final P0 pass remains outstanding. The [source-bound report](../public-site/deepseek-fresh-repeats.json) preserves per-field counts and changed review IDs.

The independently reviewed [smaller hosted allocations](SMALLER_HOSTED_CHILD_ADMISSION.md) are committed in `def54761`; their focused admission tests pass. Separate Qwen off and DeepSeek low v2 plans and manifests are frozen without inference or allocation. Their proposed $0.15 and $0.25 children may start only after terminal reconciliation releases enough actual capacity under the existing $10 cap. The original v1 plans remain preserved and unexecuted.

## DeepSeek off complete; next hosted wave admitted

All nine DeepSeek off conditions are verified closed, with 540 valid development responses. See the [three-pass analysis](DEEPSEEK_FRESH_REPEAT_FINDINGS_2026-09-29.md). Total observed charges including smokes are $0.02913576; terminal reconciliation released $0.43086424. Actual remaining master capacity was $0.43170055850 before the next allocations. Qwen off v2 received $0.15 and DeepSeek low v2 received $0.25, leaving $0.03170055850 unallocated under the existing $10 cap. These are reservations, not new observed charges. Both configurations are admitted independently; Alex 4B remains active on the native route. The wider roster is unfinished.

## Qwen fresh-series provider interruption

Qwen off v2 passed its three-record smoke, then saved five successful development responses before DEV-006 returned an AkashML upstream HTTP 429 queue timeout. The stage exited and was not replayed. Actual cost for that failed request is unavailable; its full $0.0299008 reservation is retained as an unknown-charge upper bound. The child allocation remains active at $0.15, with $0.0310951 accounted including successful smoke/development charges and that bound. DEV-007–060 were never sent; the other eight full phases remain pending. See the [sanitized failure summary](../results/repeatability-v1/qwen36-off-fresh3-v2/phase-01-failure-summary.json). Raw error evidence remains local because it includes a private provider account identifier. A separately reviewed continuation is required; the failed request cannot be replayed or silently replaced. DeepSeek low and Alex native execution are independent.

## Qwen never-sent suffix admitted

The versioned continuation in `4b2b9b9a` passed ten offline tests and root verification against the saved original attempts. Its manifest SHA-256 is `b88db7e535c4f4bbdbc4466ad8a43c49ba01e7bfe5d2680d8e9528fa79597809`; the controller SHA-256 is `ec110b20365a45893d7456c1b436711dccef1e4ad8e3e8f30d307cec5907bb52`. An exact review receipt admits only DEV-007–060 after the elapsed provider cooldown and fresh route checks. The suffix is running under the existing $0.15 child; DEV-006 remains failed with its full unknown-charge bound. The remaining eight phases still need the reviewed successor gate. No composite score is published before suffix closure.

## Qwen first P0 continuation closed

The separately admitted suffix completed all 54 never-sent positions. Strict reconciliation preserves the original DEV-006 HTTP 429: the combined first P0 pass has 59 valid outputs and one service error out of 60. All-four agreement is 48/60; sentiment, follow-up, serious concern and testimonial agreement are 54/60, 58/60, 56/60 and 54/60. Known development charges total $0.0078992, with the separate $0.0299008 unknown-charge bound retained. Smoke charges are excluded from those development totals. The [sanitized reconciliation](../results/repeatability-v1/qwen36-off-fresh3-v2/never-sent-suffix-v1/reconciliation.json) contains all 60 positions and source hashes, but cannot independently reproduce omitted private error bytes. This continuation is not a clean uninterrupted matched pass. Eight later phases remain pending their explicit successor gate.

## Qwen successor phases admitted

The successor controller in `32cee551` passed five offline tests, including persisted-manifest smoke/development/predecessor verification, and root checks against the actual closed suffix. Manifest SHA-256 `efc025c5d185835aff6734030c5613cac402909fe10ec4b34a6ae09d32bf045f` freezes the remaining eight phases, their original request settings, the closed 59/60 first pass and the same $0.15 child. The series is explicitly descriptive after a service interruption, not a clean matched-three comparison. A single execution agent owns the Qwen and DeepSeek-low lanes with separate process handles and budgets; each lane retains its own phase order and smoke inspections. No additional spending authority was granted.
