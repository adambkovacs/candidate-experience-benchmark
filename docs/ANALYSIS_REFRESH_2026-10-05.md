# Analysis refresh, 5 October 2026

## Addendum, 6 October: interrupted Qwen3.5 pass

The first new P0 pass and its completed eight-review continuation have 51 valid answers, eight invalid answers and one unknown outcome. The descriptive all-four score is 47/60, or 47/51 among valid answers. The unknown and invalid positions stay in the fixed denominator; this result supplies no clean-repeat estimate or paired prompt effect. Earlier completed comparisons remain unchanged. The [interruption report](QWEN35_P0_INTERRUPTION_2026-10-06.md) binds the saved evidence; the combined report exposes this partial coverage separately. Hibernation during the unknown request makes its client timeout unsuitable as inference latency.

The combined [analysis feed](../public-site/analysis-refresh.json) now includes four source-bound checkpoints: three Clef Flash P1 passes, three P2 passes, an interrupted Mistral 119B fresh1 P0 run and Clef's first P1 pass. It binds the public projection and its reviewed source files by SHA-256. Earlier cohort cutoffs remain separate.

## Clef Flash P1

Three separately dispatched passes each returned 60 valid answers and matched all four frozen provisional reference fields on 47/60 reviews. Across the 60 shared reviews, the parsed predictions, native probability distributions and vendor confidence values were identical in all three passes. This is observed repeat stability for this model, prompt, route and sample; it does not establish stability on other reviews or future serving revisions.

The matched fresh1 comparison scored 47/60 for P1 and 45/60 for P0 on the same records, route, native Choice interface and connected-app transport. DEV-027 and DEV-044 became all-four matches; no previously all-four-correct record became incorrect. Native probability distributions and vendor confidence changed on all 60 records. Since the prompt condition changed, this is a descriptive comparison of one P0-to-P1 contrast, not a causal estimate.

Each P1 pass reported 144,694 input tokens and zero output tokens. At the saved $0.09 per million input-token rate, the estimate is $0.01302246 per pass. The provider-billed amount is unavailable. Client elapsed time includes connected-app handoff, so pure inference latency is unavailable. The public [P1 projection](../public-site/clef-flash-p1-findings.json) matches the saved [reviewed evidence](../results/clef-native-v1/clef-flash-p1-findings-public.json); the [full findings note](CLEF_FLASH_P1_FINDINGS_2026-10-05.md) gives field scores and confidence caveats.

## Mistral 119B fresh1 P0

This pass returned 55 valid answers and retained five failed requests in the fixed 60-review denominator. It matched all four reference fields on 40/60 records (66.7%); among the 55 valid answers, the count was 40/55 (72.7%). The valid-subset score does not replace the fixed-denominator result. This is an interrupted single pass and is not a completed repeat result. The observed known cost is $0.005084835; failed requests retain a $0.20889600 unknown-charge upper bound. See the source-bound [partial findings](../public-site/mistral119-fresh1-p0-findings.json).

The later P1 smoke stopped at DEV-001 with an upstream shared-pool HTTP 429 and no reported charge. Its two remaining smoke reviews were never sent, and no full P1 pass was admitted. The failed smoke has no accuracy score or measured token total; it does not change the P0 result above. Its $0.04177920 retained reservation is an unknown-charge upper bound, not an observed bill. The [terminal record](../results/repeatability-v1/mistral119-fresh-matched3-v1/p1-successor-v1/smoke.terminal-public.json) preserves this boundary without publishing private account information.

## Scope and status

These additions update the combined analysis and public explorer. They do not close the full Clef or Mistral repeat matrices. Clef P0's three-pass checkpoint and Clef Flash's interrupted third P0 pass remain as previously reported. Clef Flash P2 has three closed passes; Clef P1 has one closed pass and Clef P2 remains unexecuted. The project still requires the full roster, condition-specific repeats where eligible, and publication of later source-bound evidence.

The analysis feed retains prior sources and historical cohorts. Its `sources` list records 115 SHA-256 bindings at this cutoff. Rebuild and verify it offline with:

```sh
python3 scripts/build_analysis_refresh.py
python3 scripts/build_analysis_refresh.py --check
```

## Clef Flash P2

[Three P2 passes](CLEF_FLASH_P2_FINDINGS_2026-10-05.md) each returned 60 valid answers and 46/60 all-four matches. All three pairwise comparisons found no changed labels, probability distributions or vendor confidence values. In the matched first-pass comparison, P0 scored 45, P1 scored 47 and P2 scored 46. P2 gained DEV-058 against P1 but lost DEV-027 and DEV-032. These different mistakes matter more than the one-point net change alone.

Each P2 pass reported 154,954 input tokens and zero output tokens. The published input-price estimate is $0.01394586 per pass; the bill and pure inference time remain unavailable. Repeated identical outputs do not establish calibration or correctness. Flash's third P0 pass remains interrupted.

## Clef P1 first-pass addition

The combined feed now recomputes Clef fresh1/P1 and matched P0 directly from completion-bound records. P1 scored 52/60 versus P0 53/60: DEV-056 gained an all-four match, DEV-013 and DEV-014 lost one, and DEV-053 changed an answer without changing all-four agreement. All responses were valid. Two more P1 passes remain required; the single contrast does not establish a repeatable prompt effect. Input usage was 144,694 tokens, with a published-price estimate of $0.03472656 and no observed bill or pure inference duration. [Evidence and per-field counts](CLEF_P1_FIRST_PASS_2026-10-05.md).

This addition raises the combined source inventory from 105 to 115 bindings. The builder rejects changed completion-bound source bytes. Earlier cohort cutoffs and failures remain intact.

## Later Flash P0 interruption

The 5 October continuation adds no predictions. Its closed receipt leaves the third P0 pass with two unknown outcomes, zero valid responses and 58 never-sent reviews. The combined feed now binds 127 source files and shows this later state separately from the historical 2 October checkpoint. All published scores and repeat comparisons are unchanged. See the [continuation checkpoint](CLEF_FLASH_P0_SUFFIX_CHECKPOINT_2026-10-05.md).

## Later Qwen1.7B first-pass prompt results

The local SDK thinking-on configuration now has one closed P0, P1 and P2 pass. Scores are 24/60, 12/60 and 8/60 all-four matches respectively. P0 and P1 each returned 60 valid answers; P2 returned 59 and retained the DEV-012 format failure. Added instructions scored lower in this first pass, but six repeat passes remain, so consistency of that difference is not established. The combined feed derives these scores from the source-bound legacy Qwen report. See the [field-level findings and usage](LEGACY_QWEN_REPEAT_FINDINGS_2026-10-02.md).


## Qwen1.7B second decision-tree pass

The first two P2 passes score 8/60 and 9/60 all-four matches. Both have 59 valid outputs, but their format failures affect different reviews: DEV-012 and DEV-033. Among the 58 reviews with valid answers in both passes, 30 changed at least one label. Field changes are 12 sentiment, 4 follow-up, 12 serious-concern and 13 testimonial decisions; these overlap within reviews. Similar aggregate scores therefore hide substantial changes in individual answers. This is a two-pass observation under the frozen local SDK protocol, not a completed three-pass study. Five of this configuration's nine planned phases remain. [Exact source-bound comparisons](../public-site/legacy-qwen-repeats.json).


## Qwen1.7B second classifier-instruction pass

P1 scores 12/60 and 11/60 across its first two passes, both with 60 valid answers. Labels changed on 23 of those 60 reviews: 8 sentiment, 3 follow-up, 10 serious-concern and 8 testimonial decisions, with overlap between fields. The second pass used 119,213 tokens and 195.24 seconds of client-observed request time; pure inference duration and local running costs remain unavailable. Alongside P2's 30/58 changed-review result, this reinforces the distinction between stable aggregate scores and stable individual decisions. The third passes remain pending; four of the nine planned phases for this setup are unfinished. [Exact source-bound comparisons](../public-site/legacy-qwen-repeats.json).


## Qwen1.7B second base-task pass

P0 scores 24/60 and 23/60 across its first two passes, both with 60 valid answers. Labels changed on 11/60 reviews: 2 sentiment, 1 follow-up, 4 serious-concern and 6 testimonial decisions, with overlap between fields. The second pass used 98,024 tokens and 71.68 seconds of client-observed request time. Pure inference duration and local running costs remain unavailable. The observed changed-review counts are lower for P0 than P1 (23/60) or P2 (30/58 jointly valid), but these two-pass observations do not establish a general effect of prompt detail. All three final passes remain required. [Exact source-bound comparisons](../public-site/legacy-qwen-repeats.json).


## Qwen1.7B classifier instructions: three passes complete

All three P1 passes returned 60 valid answers, with all-four scores of 12/60, 11/60 and 16/60. The observed score range is 11–16, not a confidence interval. Across all three passes, 30 of 60 reviews changed at least one label; field changes affected 9 sentiment, 5 follow-up, 16 serious-concern and 15 testimonial decisions, with overlap within reviews. Pairwise changed-review counts were 23, 20 and 24 out of 60. The third pass used 118,013 tokens and 198.84 seconds of client-observed request time. Pure inference duration and local cost remain unavailable. P1 execution is complete for this setup; P0 and P2 third passes remain. [Source-bound report](../public-site/legacy-qwen-repeats.json).


## Qwen1.7B base task: three passes complete

P0 scores 24/60, 23/60 and 24/60, with all 60 answers valid in every pass. Across the three passes, 19 of 60 reviews changed at least one label: 6 sentiment, 1 follow-up, 7 serious-concern and 10 testimonial decisions, with overlap. Pairwise changed-review counts are 11, 12 and 17. The third pass used 99,549 tokens and 87.48 seconds of client-observed request time. P1 scores below P0 in all three matched passes, by 12, 12 and 8 full matches. This describes the frozen local Qwen1.7B setup on these 60 reviews, not a general effect of classifier instructions. Only third P2 remains for this configuration. [Source-bound report](../public-site/legacy-qwen-repeats.json).


## Qwen1.7B thinking-on: all nine runs complete

The final P2 pass returned 60 valid outputs and 8/60 all-four matches. Its field matches were sentiment 41, follow-up 52, serious concern 42 and testimonial 14, each out of 60. P2's three scores are 8/9/8, but 40 of the 58 reviews valid in all three passes changed at least one label. The changed-review counts by field are 18/8/15/16, with overlap. DEV-012 and DEV-033 are excluded only from the shared-valid flip calculation; their earlier invalid outputs remain in the fixed score denominators.

P0 ranges from 23–24 full matches, P1 from 11–16 and P2 from 8–9. Both instruction variants score below P0 in all three matched passes. P2 trails by 16, 14 and 16 full matches. The final P2 pass predicts testimonial “yes” for 44 of the 50 reference “no” reviews. This repeated over-selection explains much of its poor all-four agreement; it is not a general claim that detailed instructions hurt other models. These remain repeated measurements of the same 60 synthetic inputs.

The final pass recorded 157,770 input and 21,946 output tokens, 179,716 total, and 333.19 seconds of summed client-observed request duration. Neither pure inference duration nor local running cost is available. The exact Q4_K_M artifact, runtime and hardware remain bound in the [source report](../public-site/legacy-qwen-repeats.json). This closes one configuration, not the wider benchmark.


## Qwen1.7B thinking-off: first P0 pass

Qwen3 1.7B with thinking disabled has closed its first P0 pass: 60 valid answers and 28/60 all-four matches. Field matches are 51 sentiment, 55 follow-up, 45 serious-concern and 43 testimonial, each out of 60. It recorded 95,628 tokens and 30.13 seconds of client-observed request time. Pure inference duration and local cost are unavailable. At that first-pass checkpoint, this configuration was 1/9 complete. The full repeat findings below supersede that coverage status. On testimonial decisions it returned “yes” for 13 of 50 reference “no” reviews. One pass does not establish a repeatability range or a general advantage from disabling thinking. [Source-bound report](../public-site/legacy-qwen-repeats.json).


## Qwen1.7B thinking-off: first prompt comparison

Qwen3 1.7B with thinking disabled has closed its first P0/P1/P2 passes, scoring 28/25/32 all-four matches out of 60, with 60/59/57 valid answers. P1 preserves one strict-JSON failure (DEV-029); P2 preserves three (DEV-002, DEV-005 and DEV-018). All four failures were JSON answers wrapped in Markdown code fences. The protocol requires bare JSON; outputs were not repaired. Decision rules improved the first-pass all-four total over P0 while reducing format validity. This differs from thinking-on, where P2 scored below P0 in all three passes. These are observations of the exact settings, not a general effect of reasoning or prompt detail. That checkpoint covered the first three phases; all nine are now closed, as described below.

P1 matches sentiment/follow-up/serious-concern/testimonial on 48/56/43/44 reviews; P2 matches 49/51/37/54, all on the fixed 60-review denominator. P2 improves testimonial agreement while losing serious-concern agreement against P0 (43 and 45 respectively). The single all-four total hides that tradeoff. P1 records 106,130 tokens and 39.76 seconds of client request time; P2 records 160,446 tokens and 44.71 seconds. Pure inference time and local cost remain unavailable. [Source-bound report](../public-site/legacy-qwen-repeats.json).


## Which thinking-off reviews changed with the prompt?

The first-pass prompt comparison now reads the three saved record files, verifies their hashes against the closed legacy report, checks all 60 ordered IDs and reference isolation, and recomputes valid and all-four counts before pairing reviews. The combined report binds 130 sources.

| Comparison | Valid in both | All-four matches on those reviews | Gained a match | Lost a match | Changed any label | Became invalid |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| P0 → P1 | 59 | 28 → 25 | 4 | 7 | 17 | 1 |
| P0 → P2 | 57 | 28 → 32 | 9 | 5 | 20 | 3 |

The invalidated reviews were not all-four matches in P0. They therefore do not explain the net score changes, though they still count as failures on the fixed 60-review denominator. Shared-valid comparisons answer a narrower question about label changes; they do not replace that denominator. The [analysis feed](../public-site/analysis-refresh.json) includes gained, lost, changed and invalidated IDs under `newerCohorts.legacyQwen.qwen17OffFirstPass.matchedP0`. A second deterministic calculation independently reproduced all counts and IDs. These are prompt comparisons within one pass, not repeatability results.


## Qwen1.7B thinking-off: all nine runs complete

All three passes of each prompt condition are closed. All-four matches out of 60 are P0: 28/26/26, P1: 25/26/25, and P2: 32/30/30. P2 gains four matches over P0 in every corresponding pass. That improvement comes with more unusable outputs: P2 returns 57/56/55 valid answers, while P0 returns 60 in every pass. P1 returns 59/60/60 valid answers. The invalid answers remain in each 60-review score.

Across all three passes, at least one label changes on 10/60 shared-valid reviews for P0, 12/59 for P1 and 7/48 for P2. P2's smaller shared-valid denominator matters: its 7/48 result does not establish better stability across the full dataset. The repeat results support a limited finding: these decision-rule prompts improve all-four agreement for this exact thinking-off configuration, while reducing output validity. Thinking-on shows the opposite score direction. Neither result establishes a general advantage for a prompt or reasoning setting.

The original third-P2 smoke stopped on a code-fenced answer. Its responses remain unchanged; a separately reviewed admission allowed the development pass with the same frozen requests and parser. The final pass returned five invalid answers and 30/60 matches. See the [source-bound findings](LEGACY_QWEN_REPEAT_FINDINGS_2026-10-02.md) and [repeat report](../public-site/legacy-qwen-repeats.json) for individual outcomes, usage and power-source observations.
