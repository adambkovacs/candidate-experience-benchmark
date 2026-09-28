# Codex fresh repeat findings, 29 September 2026

All six new Codex configurations completed three fresh passes of P0, P1 and P2: 54 closed condition/pass results. Each result contains 60 valid classifications of the same fictional reviews.

No prompt variant increased all-four agreement over P0 in all three passes for any of the six configurations. P1 gained or tied in every pass for Astra medium (+1, +1, 0) and Terra low (+2, +1, 0), but the gain did not persist as a strict increase. P1 switched between a gain and a loss across passes for Luna xhigh, Terra medium, Sol low and Luna low. P2 lost all-four matches in every pass for Terra medium (-1, -1, -2) and Luna low (-3, -2, -2). These are observed score differences on 60 repeated reviews, not significance tests or estimates for new reviews.

The [source-bound fresh report](../public-site/codex-fresh-repeats.json) contains all 54 closed results, per-review changed IDs, confusion matrices, usage and source hashes. This analysis uses its SHA-256 `335d7676d2d81e2a9eb258d34acdc808a428a3faff2adaedde904ccdcf5631dd`.

## Scores and changes across passes

The short names below refer to GPT-5.6 Luna xhigh, GPT-6 Astra medium, GPT-5.6 Terra low/medium, and GPT-6 Sol/Luna low.

Each score triple follows fresh passes 1, 2 and 3. All scores and ranges are out of 60. S means sentiment, F follow-up needed, C serious concern reported, and T testimonial potential. The final column counts distinct reviews whose four-field prediction changed at least once across the three passes. It does not count every transition or assume that a score change identifies the same reviews.

| Configuration | Prompt | All-four, passes 1/2/3 | All-four range | S range | F range | C range | T range | Reviews changing across passes |
| --- | --- | --- | --- | --- | --- | --- | --- | ---: |
| Luna xhigh | P0 | 58 / 58 / 55 | 55–58 | 58–59 | 57–60 | 59–60 | 60–60 | 5/60 |
| Luna xhigh | P1 | 57 / 59 / 58 | 57–59 | 59–59 | 59–60 | 58–59 | 60–60 | 3/60 |
| Luna xhigh | P2 | 57 / 58 / 59 | 57–59 | 58–60 | 59–60 | 58–59 | 60–60 | 3/60 |
| Astra medium | P0 | 57 / 57 / 58 | 57–58 | 58–59 | 59–60 | 59–59 | 60–60 | 2/60 |
| Astra medium | P1 | 58 / 58 / 58 | 58–58 | 59–59 | 59–59 | 59–59 | 60–60 | 0/60 |
| Astra medium | P2 | 58 / 57 / 58 | 57–58 | 58–59 | 59–59 | 59–59 | 60–60 | 1/60 |
| Terra low | P0 | 56 / 56 / 56 | 56–56 | 57–58 | 59–60 | 58–60 | 60–60 | 5/60 |
| Terra low | P1 | 58 / 57 / 56 | 56–58 | 58–59 | 60–60 | 57–59 | 60–60 | 2/60 |
| Terra low | P2 | 57 / 56 / 56 | 56–57 | 58–59 | 59–60 | 57–58 | 60–60 | 3/60 |
| Terra medium | P0 | 58 / 56 / 58 | 56–58 | 58–59 | 59–60 | 57–59 | 60–60 | 5/60 |
| Terra medium | P1 | 57 / 57 / 56 | 56–57 | 57–59 | 60–60 | 58–59 | 60–60 | 3/60 |
| Terra medium | P2 | 57 / 55 / 56 | 55–57 | 57–59 | 59–60 | 57–58 | 60–60 | 5/60 |
| Sol low, batch 10 | P0 | 57 / 58 / 58 | 57–58 | 58–59 | 59–60 | 58–59 | 60–60 | 3/60 |
| Sol low, batch 10 | P1 | 58 / 56 / 58 | 56–58 | 57–59 | 59–60 | 58–59 | 60–60 | 4/60 |
| Sol low, batch 10 | P2 | 58 / 56 / 57 | 56–58 | 58–59 | 59–60 | 57–58 | 60–60 | 3/60 |
| Luna low, batch 10 | P0 | 53 / 53 / 52 | 52–53 | 55–58 | 57–58 | 58–59 | 58–59 | 8/60 |
| Luna low, batch 10 | P1 | 51 / 53 / 55 | 51–55 | 56–57 | 58–59 | 58–59 | 57–59 | 10/60 |
| Luna low, batch 10 | P2 | 50 / 51 / 50 | 50–51 | 56–58 | 57–58 | 58–59 | 56–57 | 9/60 |

The changed-review count comes from the feed's `changesAcrossThreePasses.fourFieldVector` case IDs. It is separate from agreement with the reference. Terra low P0 scored 56/60 in all three passes while changing predictions for DEV-006, DEV-030, DEV-056, DEV-059 and DEV-060. Astra medium P1 kept the same four-field prediction for every review across its three passes. Seventeen of the 18 configuration/prompt groups changed at least one review.

## Matched prompt comparisons

Each delta compares P1 or P2 with P0 in the *same* fresh pass. Positive values mean more matches to the provisional reference. The final column counts reviews whose four-field prediction changed between the two prompts, even when the all-four scores tied. Each column again follows passes 1, 2 and 3.

| Configuration | Prompt vs P0 | All-four delta | S delta | F delta | C delta | T delta | Reviews changing from P0 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Luna xhigh | P1 | -1 / +1 / +3 | 0 / +1 / +1 | +1 / 0 / +2 | -1 / -1 / -1 | 0 / 0 / 0 | 4 / 2 / 4 |
| Luna xhigh | P2 | -1 / 0 / +4 | -1 / +1 / +2 | 0 / 0 / +3 | -1 / -2 / 0 | 0 / 0 / 0 | 4 / 3 / 5 |
| Astra medium | P1 | +1 / +1 / 0 | +1 / +1 / 0 | 0 / 0 / -1 | 0 / 0 / 0 | 0 / 0 / 0 | 1 / 1 / 1 |
| Astra medium | P2 | +1 / 0 / 0 | +1 / 0 / 0 | 0 / 0 / -1 | 0 / 0 / 0 | 0 / 0 / 0 | 1 / 0 / 1 |
| Terra low | P1 | +2 / +1 / 0 | +1 / +2 / 0 | 0 / +1 / 0 | +1 / -2 / -1 | 0 / 0 / 0 | 2 / 3 / 3 |
| Terra low | P2 | +1 / 0 / 0 | +1 / +2 / 0 | -1 / +1 / 0 | 0 / -3 / 0 | 0 / 0 / 0 | 2 / 4 / 2 |
| Terra medium | P1 | -1 / +1 / -2 | -1 / 0 / -1 | 0 / +1 / 0 | 0 / +1 / -1 | 0 / 0 / 0 | 1 / 4 / 2 |
| Terra medium | P2 | -1 / -1 / -2 | 0 / -1 / -1 | -1 / +1 / -1 | -1 / 0 / -1 | 0 / 0 / 0 | 2 / 4 / 3 |
| Sol low, batch 10 | P1 | +1 / -2 / 0 | +1 / -2 / 0 | 0 / 0 / -1 | 0 / +1 / 0 | 0 / 0 / 0 | 1 / 3 / 1 |
| Sol low, batch 10 | P2 | +1 / -2 / -1 | +1 / -1 / 0 | 0 / 0 / 0 | -1 / -1 / -1 | 0 / 0 / 0 | 2 / 2 / 1 |
| Luna low, batch 10 | P1 | -2 / 0 / +3 | -1 / -1 / +2 | +1 / +1 / +1 | 0 / 0 / 0 | -1 / 0 / +1 | 7 / 3 / 6 |
| Luna low, batch 10 | P2 | -3 / -2 / -2 | -2 / +1 / +3 | +1 / +1 / -1 | 0 / 0 / 0 | -1 / -2 / -2 | 8 / 8 / 8 |

Luna low P1 illustrates why a field gain is not a vector gain. Follow-up agreement improved by one match in every pass, while all-four agreement moved from -2 to 0 to +3. The prompt changed seven, three and six individual review vectors against P0. The [source-bound report](../public-site/codex-fresh-repeats.json) retains the case IDs for every within-pass and between-pass flip; those counts are the number of IDs, not a count of independently sampled reviews.

## Reference classes and confusion

All six series use the same provisional v0.2 reference labels. The reference contains 31 negative and eight neutral sentiment labels, 35 "yes" follow-up labels, 25 "yes" serious-concern labels, and nine "yes" testimonial labels. The full distribution and a common mismatch from the recorded confusion matrices are below.

| Field | Reference classes among 60 reviews | Mismatches across 54 completed results | Most frequent recorded mismatch |
| --- | --- | ---: | --- |
| Sentiment | negative 31; positive 11; neutral 8; mixed 8; insufficient information 2 | 95 | neutral classified positive: 50 |
| Follow-up needed | yes 35; no 24; insufficient information 1 | 43 | yes classified insufficient information: 21 |
| Serious concern reported | no 29; yes 25; insufficient information 6 | 84 | insufficient information classified no: 84 |
| Testimonial potential | no 50; yes 9; insufficient information 1 | 20 | yes classified no: 20 |

These mismatch totals count classification events across 54 runs of the same 60 reviews, not distinct error cases. Five configurations matched all 60 testimonial labels in every condition and pass; Luna low did not. The strong "no" majority for testimonial potential means that high agreement on this field should be read alongside the class counts and confusion entries.

## Limits

Luna xhigh's P1-minus-P0 delta changed from -1 to +1 to +3, while its P2 delta changed from -1 to 0 to +4. Its final pass is included in the tables. The earlier incomplete snapshot is superseded by the 54-result source hash above.

The 60 reviews are synthetic and recur in every pass. The reference labels are AI-reviewed and provisional, without independent adjudication. Prompt wording, requested model and effort, and frozen requests support matched descriptive comparisons. All six fresh series used Codex CLI 0.156.1, but served-model revision, effective seed and other provider behavior remain unobservable. Subscription cost and pure model inference time are unavailable. The [fresh roster](CODEX_FRESH_ROSTER.md) gives the execution scope; the [source-bound report](../public-site/codex-fresh-repeats.json) retains the evidence bindings behind these figures.
