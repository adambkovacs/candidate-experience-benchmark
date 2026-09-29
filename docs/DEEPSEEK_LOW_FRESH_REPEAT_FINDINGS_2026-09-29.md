# DeepSeek low: first P0 and P1 phases

Fresh pass one now has closed P0 and P1 development phases on the same 60 synthetic reviews. P0 returned 59 valid classifications and matched all four provisional reference labels on 58/60 reviews. P1 returned 60 valid classifications and matched all four on 57/60. The within-pass all-four difference is **-1/60** for P1 relative to P0. Two conditions in one pass cannot establish a prompt effect or repeat stability; seven planned condition/pass combinations remain unclosed in this report.

| Closed phase | Valid outputs | All four labels | Field matches in order: sentiment, follow-up, serious concern, testimonial |
| --- | ---: | ---: | --- |
| Fresh 1 P0 | 59/60 | 58/60 | 59, 58, 58, 59 |
| Fresh 1 P1 | 60/60 | 57/60 | 59, 59, 59, 59 |

P0's DEV-030 reached the 4,096-token output limit without a valid classification. It remains invalid in the fixed 60-review denominator. Among the 59 records valid in both phases, one four-label prediction changed, DEV-014; the paired flip denominator excludes DEV-030. The [source-bound report](../public-site/additional-hosted-fresh-repeats.json) gives the per-field confusion counts, case-level flip IDs and unfinished phases. Its references are provisional AI-reviewed labels, not independent adjudication.

P0 development recorded 85,717 prompt tokens, 32,176 completion tokens and $0.01743459 in provider-reported charges. P1 recorded 96,337 prompt tokens, 21,134 completion tokens and $0.01165805. Both phases have known charges for all 60 requests. The summed client HTTP durations were 4,095.35 and 2,946.78 seconds respectively. Those durations include transport and service time; they are not pure inference measurements. Smoke usage is separate.

The route stayed `deepseek/deepseek-v4.1-flash` through OpenInference `open-inference/fp4` with low reasoning. Before P1 development, the [reviewed lower-price successor](../scripts/deepseek_low_price_successor_v1.py) and its [stage-specific supplemental receipt](../results/repeatability-v1/deepseek-low-fresh3-v2/phase-02-development.price-amendment.root-review.json) admitted the endpoint's lower observed prompt price: $0.03 rather than $0.10 per million tokens. The original request price ceiling and full $0.1069056 per-call reservation stayed in force. The closed report binds that price amendment and both stages' raw, attempt, journal and immutable budget-prefix evidence. Different observed prices and output-token totals limit cost comparisons across P0 and P1.

The public JSON reports only closed phase scores. It leaves P2 and both later passes unscored until their evidence closes. No historical attempt is used as a fresh pass.
