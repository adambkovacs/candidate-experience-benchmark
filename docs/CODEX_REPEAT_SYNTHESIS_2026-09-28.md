# Codex repeat findings, 28 September 2026

All 18 eligible Codex subscription configurations completed three passes of P0, P1 and P2. Every condition/pass contains 60 valid classifications. This closes these 162 combinations, not the wider benchmark roster.

Classifier instructions (P1) improved all-four agreement over P0 in every pass for **two of 18 configurations**: GPT-5.6 Luna low (+1, +4, +2 matches) and GPT-6 Luna extra-high (+1, +1, +1). Decision-tree instructions (P2) improved over P0 in every pass for **none of 18**. This is a descriptive criterion on three observed passes, not a significance test or proof that either prompt is generally ineffective.

For P1, five configurations switched between a gain and a loss against P0 across passes. Five also did so for P2; these groups overlap. A single saved pass could therefore support the opposite conclusion about a prompt change from another pass of the same configuration.

Aggregate scores also hide changed answers. In **12 of the 54 configuration/condition groups**, all-four agreement was identical across all three passes while at least one review changed classification. GPT-6 Sol high P0, for example, stayed at 57/60 but changed two reviews. For each prompt condition, 17 of 18 configurations changed at least one review; the unchanged configuration differs by condition.

## Scores and changed reviews

Each score triple lists passes 1, 2 and 3, each out of 60 reviews. The final column counts reviews whose four-field prediction changed at least once across all three passes, separately for P0/P1/P2. It does not count how many times each review changed.

| Configuration | P0 all-four matches | P1 all-four matches | P2 all-four matches | Changed reviews P0 / P1 / P2 |
| --- | --- | --- | --- | --- |
| GPT-6 Luna · medium effort | 50, 54, 51 | 52, 52, 53 | 51, 53, 51 | 10 / 8 / 9 |
| GPT-6 Sol · high effort | 57, 57, 57 | 57, 58, 58 | 57, 57, 58 | 2 / 3 / 3 |
| GPT-6 Sol · medium effort | 58, 57, 57 | 57, 57, 57 | 57, 57, 57 | 2 / 1 / 2 |
| GPT-5.6 Luna · high effort | 57, 59, 57 | 59, 59, 60 | 58, 57, 57 | 3 / 2 / 3 |
| GPT-5.6 Luna · low effort | 56, 54, 55 | 57, 58, 57 | 56, 54, 56 | 5 / 4 / 7 |
| GPT-5.6 Luna · medium effort | 54, 57, 55 | 57, 57, 55 | 55, 56, 56 | 7 / 3 / 5 |
| GPT-5.6 Sol · high effort | 58, 57, 57 | 58, 58, 58 | 57, 57, 57 | 2 / 2 / 2 |
| GPT-5.6 Sol · low effort | 58, 57, 57 | 57, 57, 58 | 57, 57, 56 | 1 / 1 / 1 |
| GPT-5.6 Sol · medium effort | 57, 57, 58 | 57, 57, 57 | 57, 57, 57 | 3 / 3 / 2 |
| GPT-5.6 Sol · xhigh effort | 57, 57, 57 | 57, 57, 57 | 56, 57, 56 | 0 / 1 / 3 |
| GPT-5.6 Terra · high effort | 57, 57, 57 | 59, 56, 58 | 57, 56, 58 | 3 / 4 / 3 |
| GPT-5.6 Terra · xhigh effort | 57, 58, 58 | 57, 58, 58 | 57, 58, 57 | 3 / 2 / 1 |
| GPT-6 Astra · high effort | 58, 57, 57 | 58, 58, 57 | 58, 57, 58 | 3 / 2 / 1 |
| GPT-6 Astra · low effort | 58, 58, 57 | 58, 58, 57 | 57, 57, 58 | 2 / 2 / 1 |
| GPT-6 Astra · xhigh effort | 58, 57, 57 | 57, 58, 57 | 57, 57, 57 | 1 / 1 / 0 |
| GPT-6 Luna · high effort | 56, 59, 57 | 57, 58, 59 | 56, 57, 57 | 4 / 3 / 4 |
| GPT-6 Luna · xhigh effort | 57, 57, 57 | 58, 58, 58 | 57, 57, 58 | 2 / 0 / 3 |
| GPT-6 Sol · xhigh effort | 57, 57, 57 | 58, 57, 57 | 57, 57, 57 | 1 / 3 / 1 |

## Interpretation and evidence

These are repeated answers to the same 60 fictional reviews. References remain AI-reviewed provisional labels; 9,720 condition/pass/review outputs are not 9,720 independently sampled test cases. No inference request contains reference labels or prior predictions. Smokes are separate from development scores.

Routes, message bytes, ordered batches of ten, parser and requested effort were frozen within each configuration. The report retains accepted CLI-version differences and unobservable provider behavior; comparisons are observational and do not isolate a causal effect of wording or reasoning effort. Subscription request cost and pure model inference duration remain unavailable. CLI token-price estimates are not subscription charges.

The [source-bound report](../public-site/repeats.json) includes per-field scores, class balance, changed-review IDs, source bindings and recorded usage. The [builder](../scripts/build_repeat_findings.py) and [detailed findings](REPEAT_FINDINGS.md) reproduce the per-configuration results. This synthesis used report SHA-256 `e6acc3e09d4a2d59042e08d268c64ab9ff5a9949810513547802965d3f447c4a`.
