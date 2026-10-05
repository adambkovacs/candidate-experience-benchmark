# Analysis refresh, 5 October 2026

The combined [analysis feed](../public-site/analysis-refresh.json) now includes four source-bound checkpoints: three Clef Flash P1 passes, three P2 passes, an interrupted Mistral 119B fresh1 P0 run and Clef's first P1 pass. It binds the public projection and its reviewed source files by SHA-256. Earlier cohort cutoffs remain separate.

## Clef Flash P1

Three separately dispatched passes each returned 60 valid answers and matched all four frozen provisional reference fields on 47/60 reviews. Across the 60 shared reviews, the parsed predictions, native probability distributions and vendor confidence values were identical in all three passes. This is observed repeat stability for this model, prompt, route and sample; it does not establish stability on other reviews or future serving revisions.

The matched fresh1 comparison scored 47/60 for P1 and 45/60 for P0 on the same records, route, native Choice interface and connected-app transport. DEV-027 and DEV-044 became all-four matches; no previously all-four-correct record became incorrect. Native probability distributions and vendor confidence changed on all 60 records. Since the prompt condition changed, this is a descriptive comparison of one P0-to-P1 contrast, not a causal estimate.

Each P1 pass reported 144,694 input tokens and zero output tokens. At the saved $0.09 per million input-token rate, the estimate is $0.01302246 per pass. The provider-billed amount is unavailable. Client elapsed time includes connected-app handoff, so pure inference latency is unavailable. The public [P1 projection](../public-site/clef-flash-p1-findings.json) matches the saved [reviewed evidence](../results/clef-native-v1/clef-flash-p1-findings-public.json); the [full findings note](CLEF_FLASH_P1_FINDINGS_2026-10-05.md) gives field scores and confidence caveats.

## Mistral 119B fresh1 P0

This pass returned 55 valid answers and retained five failed requests in the fixed 60-review denominator. It matched all four reference fields on 40/60 records (66.7%); among the 55 valid answers, the count was 40/55 (72.7%). The valid-subset score does not replace the fixed-denominator result. This is an interrupted single pass and is not a completed repeat result. The observed known cost is $0.005084835; failed requests retain a $0.20889600 unknown-charge upper bound. See the source-bound [partial findings](../public-site/mistral119-fresh1-p0-findings.json).

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
