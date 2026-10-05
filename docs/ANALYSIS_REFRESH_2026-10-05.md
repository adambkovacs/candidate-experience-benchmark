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
