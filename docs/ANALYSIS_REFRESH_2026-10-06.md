# Findings update, 6 October 2026

This update covers closed results added since the [2 October analysis](ANALYSIS_REFRESH_2026-10-02.md). Every score uses the same 60 synthetic reviews and frozen provisional reference answers. Repeated runs add observations of those reviews, not new test cases. The owner confirmed human checking of the answers; disputed references remain versioned separately.

## Equal totals can hide different answers

DeepSeek low's final P0, P1 and P2 passes matched all four reference fields on 58, 57 and 58 reviews. They returned 59, 59 and 60 valid answers respectively. P0 and P1 each truncated one response, on different reviews. Among the 59 reviews valid in both P0 and P2, each scored 58 matches, yet DEV-006 changed sentiment. The full-run scores retain all 60 positions; the smaller denominator applies only to that paired comparison. [Final scores and paired changes](../public-site/deepseek-low-fresh3-findings.json).

DeepSeek high's second and third classifier-instruction passes both scored 58/60, but one review changed a label. Its final base-task pass also scored 58/60 while returning only 58 valid answers. Score and output validity answer different questions. [Later high-effort results](../public-site/deepseek-high-remaining6-successor-findings.json).

## Consistency does not establish correctness

Tev returned valid answers for all nine full passes. Its P0/P1/P2 scores were 45/44/44 in every repeat, with no label changes within a prompt condition. P1 and P2 had equal scores but changed six reviews per pass. A stable classifier can repeatedly disagree with the reference. [Tev comparisons, field confusions and costs](../public-site/tev-native-full-findings.json).

Liquid also completed nine valid full passes. P0 scored 43/43/43, P1 scored 42/44/42 and P2 scored 41/41/41. Three reviews changed a P1 label across repeats; P0 and P2 stayed unchanged. The added prompts did not consistently improve the score. Comparing decision rules with the base task changed four reviews in each pass. Two reviews lost an all-four match each time, with no newly gained all-four matches. The classifier prompt changed two, two and one reviews versus the base task; its middle-pass gain was not repeated in the other passes. These paired results explain the score changes without treating repeated reviews as independent cases. [Liquid results](../public-site/liquid-d1-native-full-findings.json).

## Confidence trades coverage for agreement

In Liquid's first P0 pass, sentiment matched 49 of 60 references. A confidence threshold of 0.9 would keep 32 decisions, of which 31 match and one does not; the other 28 would need review. Raising the threshold to 0.99 would keep only 17 decisions, all matching in this sample. That is fewer automated decisions, not proof of error-free automation. These are retrospective thresholds on the same reviews, using the provider's confidence field; they have not been calibrated or validated on new data. [Per-field threshold counts](../public-site/liquid-d1-native-full-findings.json).

## Solar's first pass across the three prompts

Solar Decide returned 60 valid answers for each prompt: the base task matched 55/60 reviews, classifier instructions 53/60 and decision rules 53/60. The longer prompts did not improve this first-pass total. Equal P1/P2 totals do not establish that the individual answers stayed the same; paired analysis and the remaining repeats are still being prepared.

Reported development costs were $0.022067 for P0, $0.022655 for P1 and $0.023159 for P2, excluding smoke tests. These aggregates bind the saved private responses by hash; a public checkout cannot independently decode those private responses. [P0 evidence](../results/solar-decide-native-full-v1/execution-adapter-v2/fresh1/P0/development.public-score.json) · [P1 evidence](../results/solar-decide-native-full-v1/execution-adapter-v2/fresh1/P1/development.public-score.json) · [P2 evidence](../results/solar-decide-native-full-v1/execution-adapter-v2/fresh1/P2/development.public-score.json).

## What remains outside these findings

Solar's remaining repeats and Cloudflare continuations are unfinished. Their latest standalone reports still need integration into the combined website calculations. Local-only work removed from scope stays in the historical archive. Missing answers and unknown charges remain visible; no failed request is silently replaced. [Current coverage](REMAINING_ROSTER_2026-10-06.md) · [Combined calculations and source hashes](../public-site/analysis-refresh.json).
