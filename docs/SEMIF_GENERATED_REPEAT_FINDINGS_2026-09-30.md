# SemIf generated repeat: first P0 and P2 phases closed

The [fresh generated plan](../results/repeatability-v1/semif-generated-fresh-v1/manifest.json) schedules three P0/P1/P2 passes, nine 60-review development phases in total. [Fresh1/P0](../results/repeatability-v1/semif-generated-fresh-v1/fresh1/P0/development.completion.json) and [fresh1/P2](../results/repeatability-v1/semif-generated-fresh-v1/fresh1/P2/development.completion.json) are the two closed development phases in this [source-bound report](../public-site/semif-generated-repeats.json). Both saved 60 responses. P0 had **52 valid, eight invalid, and 35/60 all-four-field matches** against the provisional references; P2 had **58 valid, two invalid, and 43/60 matches**. Later phases have no score in this publication snapshot. No prompt condition has a repeat pass yet, so repeat stability is unmeasured.

| Fresh1 measure | P0 out of 60 | P2 out of 60 |
| --- | ---: | ---: |
| Valid output | 52 | 58 |
| All four fields agree | 35 | 43 |
| Sentiment agrees | 46 | 51 |
| Follow-up agrees | 51 | 57 |
| Serious concern agrees | 47 | 53 |
| Testimonial potential agrees | 46 | 53 |

P0's eight invalid responses were DEV-002, DEV-020, DEV-029, DEV-040, DEV-044, DEV-051, DEV-055 and DEV-060. P2's two invalid responses were DEV-029 and DEV-055. Each ended with a `stop` finish reason and returned the same JSON schema text instead of four classification values. The [P0 raw responses](../results/repeatability-v1/semif-generated-fresh-v1/fresh1/P0/development.raw.jsonl), [P2 raw responses](../results/repeatability-v1/semif-generated-fresh-v1/fresh1/P2/development.raw.jsonl) and parsed records in the source-bound feed retain those outcomes. They remain in every fixed 60-review score denominator. Validity describes response format; agreement describes a match to the reference.

P2 scored eight more fixed-denominator all-field matches than P0. Six P0-invalid reviews became valid in P2, and none moved from valid to invalid. Among the **52 reviews valid in both**, six changed at least one classification: DEV-001, DEV-006, DEV-013, DEV-018, DEV-049 and DEV-054. All-field agreement on that shared-valid set rose from **35/52 to 39/52**. Four of the six newly valid reviews also matched all four reference fields in P2. The score gain therefore combines validity turnover and changed classifications. It does not isolate an effect of the added instructions.

The 60 P0 development requests recorded **616.33 seconds** in summed client-observed elapsed time and returned **96,930 input** and **4,680 output tokens**. P2 recorded **506.19 seconds**, **162,930 input** and **3,204 output tokens**. These sums are not isolated model inference time, and local hardware and electricity cost were not measured. The frozen plan specifies local MLX, temperature zero, thinking disabled, one attempt per review, and a fresh process and model load for each stage. It binds the intended requests without sending reference labels to the model.

The [earlier SemIf generated P0/P1/P2 observations](SEMIF_GENERATED_FRESH_REPEAT_ADMISSION_2026-09-28.md) are excluded from this fresh series. Their P2 run has 59 saved responses and an unknown started outcome at DEV-033; it cannot supply a fresh pass or be silently replayed. The [native SemIf study](SEMIF_REPEAT_FINDINGS_2026-09-28.md) uses the same verified weights but scores options through a different interface. Its three native modes each produced 60 valid classifications per pass, with 35/60 or 36/60 all-field matches. Matching one of those scores here does not make the methods interchangeable.

All references are version 0.2, AI reviewed and provisional. The same 60 synthetic reviews recur across planned passes, so later responses will not be independent cases. The [offline reporter](../scripts/build_semif_generated_repeat_findings.py) verifies stage receipts, saved stream events, raw responses, parser outcomes, completion hashes and source bindings before reporting a closed phase.
