# First-P0 general and native decision comparisons

This is a retrospective join of saved predictions on the same 60 fictional development reviews. The rule selected runs by source cohort, P0/pass identity and declared category, before looking at scores. It made no inference request. The [dataset](dataset.json) keeps every selected configuration, exact output status, four-field answer, paired native tally, source link and controls ledger. The [selection plan](plan.json) lists each excluded P0 row.

For historical rows, the exact 60 case vectors are keyed by `sourceCaseKey` in the hash-checked [public case projection](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/data.json). The original run evidence URL is kept as a lead only; it can point to one probe or batch and is not claimed to contain all 60 answers. Declared fresh1/pass1 rows carry their separately hash-checked report and record parts.

The joined set has **117 historical first-P0 general configurations**, **32 declared fresh1/pass1 general configurations** and **7 native decision first-P0 configurations**. There are **211 excluded P0 rows** across both source feeds (202 catalog, 9 historical), with exact reasons in the plan. The two general strata are not merged into one model estimate; a later fresh1 pass of a historical model is a separate observation. The native comparator is the seven-model OpenRouter Choice panel, not the full specialist roster: historical TypeSafe Jev, Laya, Kev, tuned Alex, direct Cloudflare routes and rules are outside this matched panel. Their saved evidence remains in the cited source feeds and the exclusions.

The AnyJev L1 and L2 systems use development-fold fitted calibration or heads; they are excluded from the unadapted general-checkpoint cohort even though their backbone is a general LLM. [L1 evidence](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/ANYJEV_L1_REPEAT_FINDINGS_2026-09-29.md) · [L2 evidence](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/ANYJEV_CALIBRATION_NEXT_ADMISSION_2026-09-28.md).

| Stratum | Configuration-pass rows | 60 usable answers | Incomplete phases | All-four match range / 60 |
| --- | ---: | ---: | ---: | ---: |
| Historical P0 | 117 | 101 | 0 | 0–59 |
| Declared fresh1/pass1 P0 | 32 | 22 | 2 | 0–59 |
| Native decision fresh1 P0 | 7 | 7 | 0 | 43–55 |

These ranges describe configuration-pass rows, not independent samples, model-family averages or a matched causal comparison. A row with invalid outputs can have a low all-four count for that reason; consult validity and outcome status.

| Native first P0 run | Usable / 60 | All four match / 60 | Saved source |
| --- | ---: | ---: | --- |
| liquid/d1 | 60 | 43 | [projection](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/results/liquid-d1-native-v1/full-v1/fresh1/P0/development.public.json) |
| togethercomputer/tev1-4b-experimental | 60 | 45 | [projection](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/results/tev-native-v1/full-v1/public-projection.json) |
| upstage/solar-decide | 60 | 55 | [projection](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/results/solar-decide-native-full-v1/execution-adapter-v2/first-pass.public-projection.json) |
| cloudflare/clef | 60 | 54 | [projection](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/results/clef-openrouter-v1/findings-v1/public-projection.json) |
| cloudflare/clef-flash | 60 | 45 | [projection](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/results/clef-openrouter-v1/findings-v1/public-projection.json) |
| openai/gpt-6-luna-decisions | 60 | 49 | [projection](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/results/clef-openrouter-v1/findings-v1/public-projection.json) |
| perplexity/pplx-decider-v1-27b | 60 | 54 | [projection](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/results/perplexity-decider-v1/full-v2/public-projection.json) |

### Paired saved outcomes

Each cell compares a general configuration with the named native configuration on the same fixed 60 IDs. “General higher” means more all-four reference matches in this saved pass; it is not a model-family estimate. Invalid or failed general outputs remain nonmatches, and later repeats are excluded.

| Native run | General stratum | General higher | Equal | Native higher |
| --- | --- | ---: | ---: | ---: |
| liquid/d1 | Historical P0 | 98 | 0 | 19 |
| liquid/d1 | Declared fresh1/pass1 P0 | 20 | 0 | 12 |
| togethercomputer/tev1-4b-experimental | Historical P0 | 98 | 0 | 19 |
| togethercomputer/tev1-4b-experimental | Declared fresh1/pass1 P0 | 20 | 0 | 12 |
| upstage/solar-decide | Historical P0 | 71 | 5 | 41 |
| upstage/solar-decide | Declared fresh1/pass1 P0 | 10 | 1 | 21 |
| cloudflare/clef | Historical P0 | 76 | 7 | 34 |
| cloudflare/clef | Declared fresh1/pass1 P0 | 11 | 2 | 19 |
| cloudflare/clef-flash | Historical P0 | 98 | 0 | 19 |
| cloudflare/clef-flash | Declared fresh1/pass1 P0 | 20 | 0 | 12 |
| openai/gpt-6-luna-decisions | Historical P0 | 91 | 1 | 25 |
| openai/gpt-6-luna-decisions | Declared fresh1/pass1 P0 | 17 | 0 | 15 |
| perplexity/pplx-decider-v1-27b | Historical P0 | 76 | 7 | 34 |
| perplexity/pplx-decider-v1-27b | Declared fresh1/pass1 P0 | 11 | 2 | 19 |

The table counts configurations, not independent test sets. Several rows share a checkpoint while changing effort, route, prompt implementation or pass identity; counting them does not weight a model family fairly.

### Cases missed by all seven native runs

The following rule includes every review on which all seven native first-P0 answers missed the complete provisional reference. The general columns show matches among valid outputs and the exact number of eligible configuration rows. Invalid or failed outputs remain in the eligible denominator.

| Review | Native matches | Historical general matches / valid / rows | Declared general matches / valid / rows |
| --- | ---: | ---: | ---: |
| [DEV-029](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/disputed-reviews-v1.json) | 0/7 | 89/113/117 | 13/28/32 |
| [DEV-030](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/disputed-reviews-v1.json) | 0/7 | 19/109/117 | 8/28/32 |

DEV-029 is off-topic under the frozen guide, and DEV-030 has an unresolved sentiment boundary. These reference caveats affect interpretation of apparent misses; the source review has not been silently relabeled. [Reference review](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/REFERENCE_REVIEW_V1.md) · [Per-review answers](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/disputed-reviews-v1.json).

### Equal totals can hide different decisions

The first equal-total but different-case pair in fixed source order is [qwen3.5-4b-sdk-thinking-on](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/data.json) and [luna-decisions-openrouter-native-fresh1-p0](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/results/clef-openrouter-v1/findings-v1/public-projection.json). Both match all four fields on 49/60. The general run alone matches 6 reviews (DEV-001, DEV-014, DEV-029, DEV-041, DEV-053, DEV-056); the native run alone matches 6 (DEV-005, DEV-020, DEV-021, DEV-048, DEV-054, DEV-060), including 4 where the general run had no usable answer. The recorded surfaces are Local / specialist and OpenRouter native Choice, respectively. Equal totals therefore do not imply interchangeable case decisions.

Every selected general run is in the dataset, with invalid and failed positions retained and any never-sent positions shown if present. For each general/native pair, the five outcome counts partition the fixed 60 IDs: both match, only the general run matches, only the native run matches, neither matches, or the general run has no valid output. A lower all-four match count can also reflect missing outputs, so validity remains separate.

Controls differ. The saved rows span local execution, subscriptions, OpenRouter and other hosted APIs; some send one review per request and others batch reviews. The dataset retains exact surface, recorded provider, interface classification, effort, request pattern and count, cost provenance and time basis for each run. Unrecorded batch size, prompt text, prices and inference-only time remain null. Do not compare client timings as a common inference-speed measure or treat subscription/local costs as zero.

The proposed v0.2 labels remain provisional, including disputed DEV-006, DEV-013 and DEV-030. These joined results do not show that a model family, checkpoint architecture or combined workflow causes better results on new reviews. Repeats are not pooled, and every case has one reference row regardless of run count. [Reference provenance](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/data/pilot/proposed_labels.jsonl) · [Category rule](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/REPORT_CATEGORY_REVIEW_2026-10-02.md) · [Historical feed](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/data-provider-errors-v1.json) · [Extended case feed](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/extended-cases-v1.json) · [Seven-native feed](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/disputed-reviews-v1.json).
