# Findings from the 60-review development experiment

This analysis asks what the saved responses reveal about classification, instructions and cost. Every score measures agreement with provisional reference labels on the same 60 synthetic candidate reviews. No new model requests or reference changes were made for this analysis.

[Open the visual findings](https://adambkovacs.github.io/candidate-experience-benchmark/#findings) · [Download the calculations](../public-site/findings.json) · [Read the labeling guide](LABELING_GUIDE.md)

## More instructions did not consistently improve agreement

Across **38 audited hosted and subscription prompt setups**, classifier framing (P1) improved all-four agreement over the original rubric (P0) in 15 setups, tied in 15, and worsened it in 8. Adding the SOP and decision tree (P2) to P1 improved 4, tied 13, and worsened 21.

| Comparison | More matches | Same score | Fewer matches |
| --- | ---: | ---: | ---: |
| Original rubric → classifier framing | 15 | 15 | 8 |
| Original rubric → decision tree | 7 | 16 | 15 |
| Classifier framing → decision tree | 4 | 13 | 21 |

Five additional eligible comparisons use local SDK models with historical baselines: Gemma E2B and E4B with thinking off/on, and Qwen 3.5 4B with thinking off. Including them gives 43 setups and a P1→P2 tally of 8 improvements, 13 ties and 22 declines. We show those five separately so that local execution and historical-baseline evidence remain visible.

Each setup uses the same 60 reviews. A tied score can conceal changed answers, so the explorer also exposes record-by-record transitions. P0 already contains the rubric and output schema: this compares additional instructions with an already instructed classifier.

These observations provide no reason to adopt P2 as the default for every model. They support testing instructions per configuration and repeating the comparison before claiming a reliable improvement. Audited eligibility verifies the recorded pairing requirements, not randomization or a causal effect.

The nine hosted Gemini comparisons and the native Jev comparison are separate. In Gemini, P2 gains nine net matches over P0 across nine setups, but the 3.7 Flash high-effort run alone accounts for a nine-match gain while its valid-response count rises from 50 to 60. Removing that setup leaves zero net change across the other eight. The apparent aggregate improvement therefore needs the output-validity explanation beside it.

## Jev's six disagreements need different explanations

TypeSafe Jev 1.13 P0 returned 60 valid responses and matched all four judgments on 54 reviews. Its 11 field disagreements were concentrated in six reviews:

| Review | Difference from the saved reference | Interpretation |
| --- | --- | --- |
| DEV-006 | Serious concern: no instead of insufficient information | The text mentions an unresolved "thing" without saying what happened. The reference boundary needs adjudication. |
| DEV-013 | Sentiment: positive instead of neutral | "Straightforward" and "no complaint" sit near the neutral/positive boundary. |
| DEV-027 | Sentiment: negative instead of positive; testimonial: no instead of yes | The review explicitly praises a switch to video after a cancelled train. This is a clear disagreement with the stated rubric. |
| DEV-029 | All four fields | A restaurant review should be treated as off-topic. Jev classified the food experience instead. |
| DEV-030 | Sentiment: negative instead of neutral; serious concern: no instead of insufficient information | The review leaves an accessibility issue and possible reassessment unclear. |
| DEV-059 | Follow-up: no instead of yes | The candidate asks the recruiter to stop repeated unwanted contact. Jev recognized the serious concern but missed the open request. |

Jev matched **all 25 references labeled serious concern = yes**. Its three disagreements on that field were references marked insufficient information that it labeled no. This distinction matters: missing a request for clarification and dismissing a concrete serious report call for different investigation. These 25 synthetic examples cannot establish real-world sensitivity.

The paired style example exposes a problem hidden by the total score. DEV-026 and DEV-027 describe equivalent helpful accommodations in different wording. Jev matched DEV-026 but changed both sentiment and testimonial judgments for DEV-027. It preserved the expected change pattern in the other five [controlled pairs](../data/pilot/pairs.json). One contrast does not establish general style sensitivity or demographic fairness.

The native instruction variants did not repair the six baseline disagreements. P1 and P2 each matched all four fields on 53 reviews, with 59 valid responses. Each lost one otherwise matching review to a probability distribution summing to 0.99, which the unchanged validator rejected. P2 corrected one field on the off-topic review, but its other three fields still disagreed. See the [saved native comparison](../results/jev-native-prompt-variants-v1/report.json).

## Higher scores can hide different failure patterns

Comparing the exact reviews is more useful than subtracting two totals. Claude Opus 5.5 high-effort P0 matched 59 reviews: it matched five of Jev's six misses and retained all 54 of Jev's matches. The two runs shared one missed review.

OpenJev's thinking configuration matched 57 reviews, but the difference was not simply three repaired Jev cases: it matched four of Jev's misses while losing one review Jev had matched. Both missed two reviews. Gemma 4 26B A4B with thinking on matched all six Jev misses, but had one invalid response on a review Jev matched; its result was 59 valid and 59 all-four matches.

| Illustrative saved P0 configuration | Valid / 60 | All four / 60 |
| --- | ---: | ---: |
| Claude Opus 5.5, high effort, batch of 10 | 60 | 59 |
| Gemma 4 26B A4B, thinking on, OpenRouter | 59 | 59 |
| OpenJev, thinking configuration | 60 | 57 |
| TypeSafe Jev 1.13 | 60 | 54 |
| OpenJev, fixed configuration | 60 | 52 |
| SemIf, direct configuration | 60 | 36 |
| AnyJev Qwen 0.6B, L2 calibration | 60 | 13 |
| Fixed regex rules | 60 | 10 |
| Laya English, expanded CPU configuration | 60 | 0 |

These named examples illustrate methods and overlapping errors; they are not a representative sample or a ranking of architectures. Native options, generated JSON, model sizes, calibration, runtimes and batch context differ. A low score identifies a saved configuration to investigate, not a demonstrated limit of that model family. The [machine-readable analysis](../public-site/findings.json) includes the complete 101-comparator overlap table and exact run IDs, including historical configurations. None are pooled into independent-model statistics.

## Disagreements cluster around three ambiguous reviews

In the P0 runs of the 38 audited hosted/subscription configurations, DEV-013 drew 30 valid disagreements, DEV-030 drew 27, and DEV-006 drew 25. Each denominator is 38 configurations answering the same review, not 38 independently sampled reviews. The website shows all 60 reviews, separates invalid responses, and links to the wording and labels.

All three cases involve interpretation rather than a simple explicit category: mild praise versus neutrality, uncertain resolution, and an unspecified recurring problem. They should be early targets for independent reference review. Frequent disagreement can identify a weak reference as well as a weak classifier.

## Some reference labels need independent review

DEV-006 is the clearest adjudication priority. The [guide](LABELING_GUIDE.md) requires a specifically alleged but underspecified serious issue for insufficient information; generic unease or an unreported qualifying concern gives no. "That thing happened again" establishes an unresolved issue, but does not establish its seriousness. The saved reference may be too strong on this field.

DEV-013 needs a clearer neutral/positive boundary for "straightforward" and "no complaint." DEV-030 needs review of whether its unresolved uncertainty expresses negative sentiment. Keep the current labels unchanged for this experiment, then document any independent adjudication before interpreting future scores. Model agreement with one another cannot settle these questions.

## Higher effort can cost more without adding matches

The hosted Gemini P0 runs provide a concrete comparison with the same input-token count (11,227) and batch size:

| Model | Effort | Valid / 60 | All four / 60 | Output tokens | Observed charge |
| --- | --- | ---: | ---: | ---: | ---: |
| Gemini 3.1 Pro Preview | Low | 60 | 56 | 3,417 | $0.063458 |
| Gemini 3.1 Pro Preview | High | 60 | 55 | 19,531 | $0.256826 |
| Gemini 3.7 Flash | Low | 60 | 57 | 3,534 | $0.02167275 |
| Gemini 3.7 Flash | Medium | 60 | 56 | 12,679 | $0.0559665 |

In these two comparisons, higher effort produced more output tokens and a larger charge, with one fewer all-four match. These are illustrative saved observations, not proof that lower effort is generally better. The full cost plot includes the other qualifying P0 runs, and the exact-value table preserves settings and sources. [Gemini report](../results/gemini-openrouter-prep-v3/report-v2.json).

Jev's P0 estimate is $0.00589092 for reported usage, with 54 matches. Its provider-confirmed charge is unavailable, so it is shown separately from the observed-cost plot. Subscription access and local execution also lack comparable per-run bills. Do not count either as free inference or substitute API list-price estimates for observed charges.

## The four fields have different class balances

| Field | Reference distribution | Most-common-label baseline |
| --- | --- | --- |
| Sentiment | 31 negative, 11 positive, 8 neutral, 8 mixed, 2 insufficient information | 31 / 60 |
| Follow-up | 35 yes, 24 no, 1 insufficient information | 35 / 60 |
| Serious concern | 25 yes, 29 no, 6 insufficient information | 29 / 60 |
| Testimonial | 9 yes, 50 no, 1 insufficient information | 50 / 60 |

A classifier that always says no to testimonial potential already matches 50 of 60 references. High agreement on that field alone therefore says little about finding the nine suitable testimonials. The concern-enriched development set also differs from the likely mix of ordinary candidate feedback. See the [pilot audit](PILOT_AUDIT.md).

## Scope and interpretation

The reference labels were drafted and reviewed by the same AI assistant, without independent human adjudication. The archive contains repeated conditions, effort settings, routes and historical continuations of the same models. Neither its run count nor its response count represents independent models or independent reviews.

Prompt comparisons hold visible settings constant where the saved audit permits it, but each condition was run once. Time, sampling and hidden provider behavior can still explain differences. Findings describe these saved runs; they do not establish causal prompt effects, statistical significance or a stable leaderboard.

Observed API charges, token-price estimates and subscription access are different accounting categories. Missing cost is unknown. Pure server inference time is unavailable in the current public export; client request duration and provider generation duration cannot supply that measurement. No inference-speed ranking is warranted.
