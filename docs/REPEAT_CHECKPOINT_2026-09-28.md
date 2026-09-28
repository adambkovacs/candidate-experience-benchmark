# What the latest repeats show

Checked 2026-09-28. Each entry below uses three separately dispatched passes on the same 60 synthetic reviews, scored against provisional v0.2 references. The numbers are all-four agreement counts, not hiring accuracy. These six completed series are a subset of the full study.

| Configuration | P0 scores | P1 scores | P2 scores | Comments changing any decision across passes, P0 / P1 / P2 |
| --- | --- | --- | --- | --- |
| Opus 5.5 medium | 58, 58, 57 | 58, 58, 58 | 56, 58, 56 | 1 / 1 / 2 |
| Gemini 3.6 Flash low | 55, 55, 54 | 55, 54, 56 | 54, 56, 56 | 5 / 6 / 4 |
| Gemini 3.7 Flash low | 57, 57, 56 | 55, 56, 56 | 57, 58, 56 | 2 / 2 / 3 |
| Gemma 26 off | 53, 52, 52 | 52, 52, 52 | 52, 51, 53 | 2 / 2 / 3 |
| Gemma 31 off | 56, 55, 55 | 56, 54, 54 | 55, 56, 54 | 2 / 5 / 4 |
| Gemma 31 on | 56, 56, 58 | 58, 57, 58 | 58, 58, 58 | 4 / 2 / 0 |

Sources: the [Opus report](../public-site/claude-repeats.json), [Gemini reports](../public-site/gemini-repeats.json), and [hosted reports](../public-site/hosted-repeats.json). Each includes source hashes, per-field counts, request usage, and paired changes. The [public repeat explorer](https://adambkovacs.github.io/candidate-experience-benchmark/#repeat-analysis) shows the individual conditions and changed comments.

## Stable totals can conceal changed answers

Opus P1 scores 58 each time, but one comment changes at least one decision. Gemma 26 P1 scores 52 each time, with two comments changing. A score alone cannot establish classification stability. The changed-comment count examines the four-label vector, including changes that leave all-four agreement unchanged.

## A small prompt advantage can change direction

For Gemini 3.6 low, P2 minus P0 is -1, +1 and +2 matches across the three passes. The first pass alone would suggest the decision-tree prompt hurt; later passes suggest the opposite. Gemini 3.7 low gives 0, +1 and 0. These results do not justify a general claim that more detailed instructions reliably improve this task.

Gemma 31 on P2 retains 58 matches and the same four-label vector for all 60 comments in all three passes. That is observed stability in this small series, not proof of deterministic serving or future stability. Its P0 and P1 still show changed decisions.

## Comparisons have limits

The same 60 reviews appear in every pass; there are not 180 independent reviews per condition. Serving revisions and effective seeds are not exposed, and the historical pass preceded the new passes. Some subscription CLI patch versions changed under the accepted protocol. Differences cannot be attributed solely to sampling randomness, and model-to-model rankings are not controlled causal comparisons.

Request durations remain client measurements unless the provider exposes inference time. Token fields can include provider-specific cache and reasoning categories. Subscription list-price estimates are not actual charges. Missing quantities stay unavailable rather than zero.

Mistral's second-pass P1 is excluded from clean three-pass summaries: it retains one HTTP 429 alongside 59 valid responses, with the final 17 obtained later. Its other phases do not erase that failure. See the [current checkpoint](CURRENT_GOALS.md) for completion and budget status across the full requested work.

## Additional Codex series completed on 28 September

The four GPT-5.6 series below now have all nine condition/pass combinations, each with 60 valid outputs. Values count matching all four reference labels out of 60, in historical, second-pass and third-pass order.

| Configuration | P0 scores | P1 scores | P2 scores | Reviews changing any decision, P0 / P1 / P2 |
| --- | --- | --- | --- | --- |
| GPT 5.6 luna high | 57, 59, 57 | 59, 59, 60 | 58, 57, 57 | 3 / 2 / 3 |
| GPT 5.6 luna low | 56, 54, 55 | 57, 58, 57 | 56, 54, 56 | 5 / 4 / 7 |
| GPT 5.6 luna medium | 54, 57, 55 | 57, 57, 55 | 55, 56, 56 | 7 / 3 / 5 |
| GPT 5.6 sol high | 58, 57, 57 | 58, 58, 58 | 57, 57, 57 | 2 / 2 / 2 |

Luna medium's P0 score ranges from 54 to 57, with seven reviews changing at least one decision across the three passes. Its P1 range is 55–57 and P2 range 55–56. These overlapping ranges caution against treating a single-pass prompt improvement as settled.

Sol high scores 58 in every P1 pass and 57 in every P2 pass, but two reviews change decisions within each condition. Its stable totals therefore do not imply identical outputs. The [Codex report](../public-site/repeats.json) lists the changed review IDs and field-level comparisons; all 12 report tests passed in a clean export of the committed sources. The accepted CLI patch difference and unobserved serving changes remain limits on attributing variation purely to sampling.

The [new Gemini analysis](GEMINI_REPEAT_FINDINGS_2026-09-28.md) adds four more completed series and separates token-truncated batches from classification changes.

## Further Sol and Terra repeats

GPT-5.6 Sol low, medium and extra-high, plus Terra high, now have all nine condition/pass combinations complete. Every combination produced 60 valid outputs. Scores below count agreement on all four fields against the provisional v0.2 references, out of 60.

| Configuration | P0 scores | P1 scores | P2 scores | Reviews changing at least one field: P0 / P1 / P2 |
| --- | --- | --- | --- | --- |
| Sol low | 58, 57, 57 | 57, 57, 58 | 57, 57, 56 | 1 / 1 / 1 |
| Sol medium | 57, 57, 58 | 57, 57, 57 | 57, 57, 57 | 3 / 3 / 2 |
| Sol extra-high | 57, 57, 57 | 57, 57, 57 | 56, 57, 56 | 0 / 1 / 3 |
| Terra high | 57, 57, 57 | 59, 56, 58 | 57, 56, 58 | 3 / 4 / 3 |

Sol extra-high P0 is the only condition in this four-configuration group with no observed classification changes across all three passes. Its identical P1 scores still conceal one changed review. Terra high also kept the same P0 score while changing three reviews, and its P1 score ranged from 56 to 59. Small differences between prompt conditions should be read alongside that repeat variation. These results describe the same 60 synthetic reviews, not independent samples or a general model ranking. See the [source-bound repeat report](../public-site/repeats.json).
