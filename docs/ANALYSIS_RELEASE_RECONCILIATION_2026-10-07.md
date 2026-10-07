# Analysis release reconciliation, 7 October 2026

The saved evidence supports the requested descriptive analysis on the complete current dataset of 60 synthetic reviews. The current website source integrates the general/native comparison, broader difficult-review view, selected-pair field tables, agreement/deferral policy and hypothetical reference sensitivity. Root has added a concise latest-cohort deck conclusion; its independent factual and implementation review passed with nine tests. Rendered verification remains pending. The report should preserve the updated Clef, Flash and Perplexity interpretation below. Publication and rendered verification are separate gates; this audit does not declare the goal complete.

## Scope and denominator reconciliation

[APP_GOAL.md](APP_GOAL.md) supplies the release scope. The existing DEV-001 through DEV-060 records are the whole current dataset. Further direct Cloudflare Jev/Clef/Flash, remaining Mistral execution, further local inference and the cancelled DeepSeek download are excluded. Their saved evidence and charge reservations remain in the history. Exact unavailable requested models retain their zero-attempt status in the [route recheck](ROUTE_RECHECK_LATEST_2026-10-07.md) and [execution dispositions](EXECUTION_DISPOSITIONS_2026-10-07.md); this audit does not resolve an execution scope decision by treating absence as a successful test.

The frozen reference is proposed v0.2. The owner confirmed human checking on 2 October; unresolved labels remain provisional, and no v0.3 correction has been adopted. The original historical feed retains its historical provenance text. Current interpretation must use the [reference review](REFERENCE_REVIEW_V1.md) and the owner-confirmed provenance in the newer feeds, without rewriting frozen outcomes.

| Evidence view | Exact included run entries | Review positions | Usable classifications | Source and identity manifest |
| --- | ---: | ---: | ---: | --- |
| Original explorer | 290 | 17,400 | 16,640 | [data.json](../public-site/data.json), each `runs[].id` and its inline case vectors |
| Extended report-backed entries | 637 | 38,220 | 36,748 | [extended catalog](../public-site/extended-run-catalog-v1.json), each `runs[].id`; [case vectors](../public-site/extended-cases-v1.json) |
| Additional case entries | 77 | 4,620 | 4,618 | [additional cases](../public-site/additional-cases-v1.json), each `runs[].runId` |
| Combined selectable inventory | 1,004 distinct IDs | 60,240 | 58,006 | Union of those three disjoint manifests, one vector position per ID and review |

These are saved run views, including composites and different configurations. They are not 1,004 independent experiments or 60,240 independent reviews. Do not sum their displayed costs into a provider bill: a composite or report restatement can refer to the same underlying attempts. The original catalog's `records` sum is 17,398 because two entries report fewer saved records; its explicit case grid still has 17,400 planned positions. Fixed-denominator scoring uses the latter. There are 25 entries whose `complete` flag is false: two original, 21 extended and two additional; a true flag does not imply every answer was valid.

The 77 additional entries comprise 12 Sonnet cells not in the extended catalog, two historical direct Clef/Flash P0 entries and 63 later native decision stages. The latter are nine stages each for Liquid, Tev, Solar and Perplexity plus 27 for OpenRouter Clef/Flash/Luna. The 24 Sonnet extended entries and 12 additional entries together cover all 36 Sonnet cells; do not count the full report again as a second cohort.

| Analytical selection | Configuration rows | Fixed review positions | Usable answers | Boundary |
| --- | ---: | ---: | ---: | --- |
| Historical general first P0 | 117 | 7,020 | 6,769 | 101 rows have 60 usable answers; 249 invalid outputs and two service errors remain |
| Declared fresh1/pass1 general P0 | 32 | 1,920 | 1,744 | 22 rows have 60 usable answers; 170 invalid outputs and six other unusable outcomes remain |
| Native decision fresh1/P0 | 7 | 420 | 420 | Liquid, Tev, Solar, Clef, Flash, Luna Decisions and Perplexity through OpenRouter |
| Cross-category total | 156 | 9,360 | 8,933 | Separate strata; 1,043 general/native pair joins, each on the same 60 IDs |
| Native agreement/deferral policy | All 21 unordered pairs of the seven native runs | 60 per pair | Both component answers available on all 60 | Prediction agreement determines acceptance before reference scoring |
| Reference sensitivity | 637 extended entries and a separate seven-native cohort | 60 per run per scenario | Original usability unchanged | Seven combinations of three documented label alternatives; hypothetical only |

The [cross-category selection plan](../results/cross-category-v1/plan.json) retains 211 excluded P0 rows: 202 catalog and nine historical rows. Category membership follows checkpoint/adaptation evidence rather than output interface. A native readout of general weights is not automatically a dedicated model. The AnyJev fitted L1/L2 systems remain separate from the unadapted general selection. This selected first-P0 panel is not the full specialist roster; TypeSafe Jev, Laya, Kev, tuned Alex, direct Cloudflare and rules retain their separate reports.

## Latest decision-model and Sonnet findings

Each number below is an all-four reference match count out of the fixed 60 reviews. The three numbers in a cell are fresh1, fresh2 and fresh3, not a pooled score.

| Exact latest configuration | P0 | P1 | P2 | Development outcome coverage |
| --- | --- | --- | --- | --- |
| OpenRouter Clef | 54, 54, 54 | 51, 51, 51 | 49, 49, 49 | 540/540 usable |
| OpenRouter Clef Flash | 45, 45, 45 | 47, 47, 47 | 46, 46, 45 | 539/540 usable; final P2 retains one provider failure |
| OpenRouter Luna Decisions | 49, 49, 49 | 51, 51, 51 | 49, 49, 49 | 540/540 usable |
| Perplexity Decider | 54, 54, 54 | 54, 54, 54 | 54, 54, 54 | 540/540 usable |
| Liquid d1 | 43, 43, 43 | 42, 44, 42 | 41, 41, 41 | Nine closed stages, 540/540 usable |
| Tev 1 4B experimental | 45, 45, 45 | 44, 44, 44 | 44, 44, 44 | 540/540 usable |
| Solar Decide | 55, 53, 54 | 53, 52, 51 | 53, 52, 52 | 539/540 usable; final P2 is an interrupted composite |

Sources: [OpenRouter report](../results/clef-openrouter-v1/findings-v1/findings.json), [Perplexity](../results/perplexity-decider-v1/full-v2/findings.json), [Liquid](../public-site/liquid-d1-native-full-findings.json), [Tev](../public-site/tev-native-full-findings.json), [Solar](../public-site/solar-decide-full-findings.json). The seven full series account for 3,780 development positions and 3,778 usable answers. Flash's failure and Solar's unknown response remain distinct outcomes.

Clef, Flash and Luna have zero categorical prediction flips on shared usable reviews between same-prompt repeat passes. Flash's final P2 has 59 shared usable reviews; the lost answer explains its 46 to 45 score change. Perplexity has identical same-prompt repeat predictions and identical P0/P2 predictions. Its P1 changes follow-up and sentiment on DEV-029, gaining one field match and losing another while preserving the 54/60 all-four total. Stable answers can therefore preserve errors, and equal scores can conceal changed decisions.

First-pass P0 to P2 all-four gains/losses are Clef 0/5, Flash 2/1, Luna 3/3 and Solar 0/2. More instructions have no consistent benefit across these configurations. These within-route pairs keep exact prompts and source IDs; native policy placement and Clef's possible policy truncation limit causal interpretation. [Paired source results](../results/clef-openrouter-v1/findings-v1/findings.json) and [native interface limits](CLEF_OPENROUTER_FINDINGS.md).

Sonnet 5.5 has all 36 cells and 2,160/2,160 usable development classifications: four effort settings, three prompts, three passes, 60 reviews each. High P0 scores 58/60 in every pass; xhigh scores 58/60 in every P0/P1/P2 cell. Across its nine cells xhigh records 83,131 output tokens versus low's 33,653, about 2.47 times, without a consistent score gain. Low P0 varies 58, 56, 58; high P1 varies 57, 58, 58. This shows setting-specific saved outcomes, not a model-size law or a controlled model-family comparison. Its ten-review subscription CLI requests differ from one-review native calls. [Full Sonnet report](../public-site/sonnet55-fresh-matched3.json).

## Strongest supported cross-model and case findings

The first-P0 native subset ranges from 43/60 to 55/60, while selected general configuration scores can exceed that range. Sonnet high's 58/60 P0 results provide a specific later example. No blanket dedicated-model advantage follows from these saved scores. Distinct routes, interfaces, effort, batches and adaptation remain confounded; configuration counts do not estimate a family effect. [Cross-category results](../results/cross-category-v1/findings.md).

All seven native first-P0 models match the complete reference on 26/60 reviews; at least one differs on 34. Every one misses DEV-029 and DEV-030. The hindsight oracle reaches 58/60, which is an upper bound after reading the reference, not a working selection rule. DEV-029 is off-topic under the guide. DEV-030 has disputed sentiment; DEV-006 and DEV-013 also have documented alternatives. [Disputed cases](../public-site/disputed-reviews-v1.json), [reference history](REFERENCE_REVIEW_V1.md).

The broad first-P0 comparison preserves different case patterns: DEV-029 matches in 89/117 historical general rows (113 usable) and 13/32 declared general rows (28 usable), versus 0/7 native rows. DEV-030 matches in 19/117 (109 usable) and 8/32 (28 usable), versus 0/7 native. These are exact configuration counts on two synthetic reviews. They do not establish population prevalence or explain which training architecture caused the differences. [All case-stratum counts](../public-site/cross-category-v1.json).

The testimonial example DEV-027 says the train was cancelled, the interviewers switched to video and gave the candidate time to recover. Four of seven native first-P0 configurations differ from its complete reference vector. The [difficult-review panel](../public-site/cohort-reviews.js) now includes actual text, all four reference fields, each selected configuration's answers and source links, with disagreements and unusable outcomes counted separately. The same panel can select general, decision or combined rows while keeping the two general strata separate.

Reference class balance is highly uneven: sentiment has 31 negative, 11 positive, eight mixed, eight neutral and two insufficient-information labels; follow-up has 35 yes, 24 no and one insufficient; serious concern has 25 yes, 29 no and six insufficient; testimonial has nine yes, 50 no and one insufficient. An all-no testimonial rule already matches 50/60. Field totals alone can hide poor positive recall. The selected-pair [field tables](../public-site/cross-category.js) show full reference-by-prediction counts, a separate no-valid-output column, yes precision and yes recall on the valid subset, with unusable reference-positive counts explicit. Their score denominator remains 60. [Reference distribution](../public-site/analysis-refresh.json).

## Confidence, abstention, cost and timing

Native provider confidence and chosen-option probability are different recorded values. Clef's first P0 misses DEV-029 in follow-up, serious concern and testimonial even with provider confidence at least 0.9. Tev first-P0 sentiment retains 41/60 reviews at the 0.9 threshold, including four errors. Solar first-P0 sentiment retains 16/60 at 0.99, including two errors. Thresholds evaluated retrospectively on these same development reviews are not a calibrated deployed abstention policy. Generated interfaces without recorded comparable confidence should not receive fabricated threshold results. [OpenRouter field evidence](../results/clef-openrouter-v1/findings-v1/findings.json), [Tev thresholds](../public-site/tev-native-full-findings.json), [Solar thresholds](../public-site/solar-decide-full-findings.json).

The fixed two-model policy reports every one of the 21 pairs, accepting only identical valid four-field predictions and deferring the rest. Accepted coverage ranges from 33/60 to 53/60 and retained all-four errors from zero to four. All costs include both saved development runs on all 60 reviews, including deferred cases; human review cost is unavailable. A zero-error accepted subset on this development set is not proof of safe deployment or out-of-sample improvement. [Policy and all pairs](../public-site/native-agreement-policy-v1.json).

| Native fresh1/P0 component | All-four / 60 | Known development charge, USD |
| --- | ---: | ---: |
| Liquid d1 | 43 | 0.01568912 |
| Tev | 45 | 0.016342872 |
| Solar Decide | 55 | 0.02206700 |
| Clef | 54 | 0.03184656 |
| Clef Flash | 45 | 0.01194246 |
| Luna Decisions | 49 | 0.01335230 |
| Perplexity Decider | 54 | 0.01542736 |

These exact charges reconcile in the [policy component table](../public-site/native-agreement-policy-v1.json). On only these two metrics, the seven-component P0 frontier is Flash, Luna, Perplexity and Solar. Deterministic dominance means another component costs no more and has at least as many all-four matches, with at least one strict improvement. The older three-component frontier remains historical: Perplexity's 54/60 at $0.01542736 removes Clef's 54/60 at $0.03184656 from the expanded frontier. Field mistakes differ even at equal totals. This is neither an architecture claim nor a full workflow price forecast.

Keep observed provider charge, price-derived tariff estimate, subscription API-equivalent estimate and unknown-charge bound distinct. Sonnet's $3.5429424 development API equivalent is not a subscription invoice. Solar's DEV-009 retains a $0.10485760 unknown-charge bound; Flash's final P2 retains its unknown-cost provider failure. Smoke, staff review, local electricity and hosting are not part of the component frontier. Missing cost is unavailable, never zero. Spending ceilings remain OpenRouter $22.38, Cloudflare $10 and TypeSafe $1; ledger reconciliation determines remaining authority. [Accounting limits](APP_GOAL.md), [Solar charge boundary](../public-site/solar-decide-full-findings.json), [OpenRouter failure accounting](../results/clef-openrouter-v1/findings-v1/findings.json).

No common pure inference-time measure exists. Client request duration, CLI/provider-reported API duration, batch shares and whole-stage time are separate measures. Native one-review requests and ten-review CLI batches cannot form a common speed ranking. Token categories and their coverage remain source-specific. [Combined measurement coverage](../public-site/analysis-refresh.json), [analysis definitions](ANALYSIS_REFRESH_2026-10-02.md).

## Required-angle map and actual remaining integration

| Required analysis angle | Current public section | Exact source or calculation |
| --- | --- | --- |
| Validity, all-four and per-field agreement | `#report-lens`, `#outcome-chart`, `#inspect`, `#analysis-update` | Three inventory feeds; [combined synthesis](../public-site/analysis-refresh.json); exact run metrics and case vectors |
| Class balance, confusion, positive precision/recall | `#cross-category`, `#method` and linked class-level reports | [cross-category field calculation](../public-site/cross-category.js), 156 selected rows; [reference counts](../public-site/analysis-refresh.json) |
| Prompt gains/losses and changed IDs | `#prompt-analysis`, `#analysis-update`, native prompt panels | Original `promptComparisons`; model-specific matched-pair sources; [latest native report](../results/clef-openrouter-v1/findings-v1/findings.json) |
| Repeat ranges and individual label flips | `#repeat-analysis`, `#analysis-update` | Each linked series report; latest native comparisons; [Sonnet](../public-site/sonnet55-fresh-matched3.json); fixed score and shared-valid flip denominators |
| Model disagreements, difficult testimonials and off-topic text | `#cross-category`, `#cohort-reviews`, `#review-evidence`, `#inspect` | [cross-category dataset](../public-site/cross-category-v1.json), [seven-native exact cases](../public-site/disputed-reviews-v1.json), all-run A/B case feeds |
| Defined combined workflow and deferral | `#agreement-policy` | [All 21 fixed agreement pairs](../public-site/native-agreement-policy-v1.json); no oracle advertised as an ensemble |
| Reference uncertainty and hypothetical changes | `#reference-sensitivity`, `#method` | [Seven scenarios](../public-site/reference-sensitivity-v1.json), frozen v0.2 scores retained |
| Confidence and errors | `#analysis-update` native details and linked native reports | Provider confidence/probability sources and field-specific retrospective threshold tables |
| Tokens, costs and timing | `#usage`, `#inspect`, `#cross-category` controls, `#analysis-update` | Source-specific cost fields, token categories and timing kind; unavailable measurements explicit |
| Checkpoint, category, adaptation and route controls | Run filters and `#cross-category` controls | Per-run configuration IDs; [selection plan](../results/cross-category-v1/plan.json); category evidence and exclusions |

The coverage review's old statements that the joined comparison, policy and sensitivity panels are "in preparation" or awaiting integration are superseded by the current mounted source. Root should refresh those status sentences, preserving historical publication evidence. The current index has mounts and script links for the broader cohort panel and selected-pair fields; this source presence does not verify the deployed edition.

The analytical communication task is bounded: preserve the current native prompt/repeat conclusion and explain that Perplexity changes the expanded P0 charge/agreement frontier. At initial inspection, the deck used a correctly named Gemma prompt/cost example, a Codex Luna repeat example and the seven-native case grid, but no latest full-series synthesis. Root reports that a concise latest-cohort deck addition is now implemented and undergoing independent review. The illustrative examples remain valid; no slide-by-slide experiment inventory is required. Verify the final text against the exact results above before publication.

There is no identified missing experiment needed to calculate the mapped descriptive findings. Broad ideas such as a new validation set, deployed policy testing, probability calibration or pure inference instrumentation belong to future studies. Exact unavailable-model scope, publication and allowed rendered verification remain separate release gates. This audit covers factual readiness, not completion.

## Verification and retained outcomes

The audit ran these deterministic source checks successfully:

```bash
python3 scripts/build_analysis_refresh.py --check
python3 scripts/analyze_cross_category_v1.py --check
python3 scripts/build_disputed_reviews_v1.py --check
python3 scripts/analyze_native_agreement_policy_v1.py --check
python3 scripts/analyze_reference_sensitivity_v1.py --check
```

The combined check verified 1,368 source hashes; the other checks reconciled the selected first-P0 analysis, 60 reviews against seven exact native configurations, all 21 pair policies and seven sensitivity scenarios. Additional deterministic reads reconciled the 1,004 identity union, fixed-60 case grids, native stage scores, latest outcomes, class counts and the two-metric frontier. Private raw projections retain their stated preparation-time decoding/hash boundaries; a public checkout does not independently re-decode absent private response bytes. No inference, browser action, git mutation or live publication verification was performed for this audit.

The combined case inventory preserves the following exact saved statuses. The two usable status names are `ok` and `valid`; all other positions remain unusable with their original distinction.

| Saved status | Positions |
| --- | ---: |
| `ambiguous_no_saved_output` | 1 |
| `failed_in_report` | 2 |
| `interrupted_no_provider_result` | 1 |
| `invalid_output` | 2066 |
| `missing` | 1 |
| `never_sent` | 42 |
| `ok` | 57047 |
| `prompt_admission_failure` | 4 |
| `provider_failure_unknown_cost` | 1 |
| `service_error` | 108 |
| `transport_error` | 1 |
| `unknown_cost` | 2 |
| `unknown_cost_http_429` | 1 |
| `unknown_cost_no_response` | 1 |
| `unknown_outcome` | 1 |
| `unknown_started` | 2 |
| `valid` | 959 |

These status counts reconcile to 60,240 planned positions and 58,006 usable vectors. They count saved views, not distinct billable attempts. Unknown states, intrinsic invalid output, provider failure and never-sent status are not interchangeable classification errors.

## Extended-family inventory

The table below enumerates the 637 extended entries by their declared source family. The linked report and catalog preserve exact configuration, prompt, pass and source-stage identities; original phases/restatements excluded by the catalog are not added back here. Each entry has 60 planned positions.

| Source family | Catalog entries |
| --- | ---: |
| [additional-hosted-fresh-repeats](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/additional-hosted-fresh-repeats.json) | 14 |
| [alex-native-repeats](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/alex-native-repeats.json) | 6 |
| [anyjev-generated-repeats](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/anyjev-generated-repeats.json) | 9 |
| [anyjev-l0-repeats](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/anyjev-l0-repeats.json) | 2 |
| [anyjev-l1-repeats](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/anyjev-l1-repeats.json) | 3 |
| [anyjev-l2-repeats](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/anyjev-l2-repeats.json) | 2 |
| [anyjev-raw-repeats](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/anyjev-raw-repeats.json) | 2 |
| [claude-repeats](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/claude-repeats.json) | 6 |
| [claude-roster-repeats](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/claude-roster-repeats.json) | 90 |
| [clef-closed-repeat-findings](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/clef-closed-repeat-findings.json) | 7 |
| [clef-flash-p1-findings](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/clef-flash-p1-findings.json) | 3 |
| [clef-flash-p2-findings](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/clef-flash-p2-findings.json) | 3 |
| [clef-p0-repeat-findings](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/clef-p0-repeat-findings.json) | 1 |
| [codex-fresh-repeats](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/codex-fresh-repeats.json) | 54 |
| [deepseek-fresh-repeats](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/deepseek-fresh-repeats.json) | 9 |
| [deepseek-high-remaining6-successor-findings](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/deepseek-high-remaining6-successor-findings.json) | 6 |
| [deepseek-low-final-suffix-findings](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/deepseek-low-final-suffix-findings.json) | 1 |
| [deepseek-low-fresh3-findings](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/deepseek-low-fresh3-findings.json) | 4 |
| [deepseek-low-p1-successor-findings](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/deepseek-low-p1-successor-findings.json) | 1 |
| [deepseek-low-remaining6-price-v2-findings](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/deepseek-low-remaining6-price-v2-findings.json) | 1 |
| [e4b-interruption-findings](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/e4b-interruption-findings.json) | 1 |
| [gemini-repeats](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/gemini-repeats.json) | 54 |
| [gemma26-continuation-findings](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/gemma26-continuation-findings.json) | 3 |
| [gemma26-fresh3-p0-checkpoint](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/gemma26-fresh3-p0-checkpoint.json) | 1 |
| [gemma26-fresh3-p1-interrupted-checkpoint](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/gemma26-fresh3-p1-interrupted-checkpoint.json) | 1 |
| [gemma26-p2-repeat-findings](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/gemma26-p2-repeat-findings.json) | 1 |
| [gemma26-second-continuation-findings](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/gemma26-second-continuation-findings.json) | 1 |
| [haiku-fresh-matched3](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/haiku-fresh-matched3.json) | 9 |
| [hosted-repeats](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/hosted-repeats.json) | 30 |
| [hosted-v2-repeats](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/hosted-v2-repeats.json) | 2 |
| [jev-native-prompt-findings](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/jev-native-prompt-findings.json) | 9 |
| [kev-native-prompt-findings](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/kev-native-prompt-findings.json) | 6 |
| [kev-native-repeats](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/kev-native-repeats.json) | 2 |
| [laya-repeats](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/laya-repeats.json) | 6 |
| [legacy-qwen-repeats](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/legacy-qwen-repeats.json) | 48 |
| [mistral119-fresh1-p0-findings](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/mistral119-fresh1-p0-findings.json) | 1 |
| [openjev-generated-repeats](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/openjev-generated-repeats.json) | 18 |
| [openjev-native-repeats](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/openjev-native-repeats.json) | 9 |
| [qwen27-final-descriptive-findings](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/qwen27-final-descriptive-findings.json) | 18 |
| [qwen36-off-second-interruption-findings](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/qwen36-off-second-interruption-findings.json) | 9 |
| [repeats](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/repeats.json) | 108 |
| [semif-generated-repeats](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/semif-generated-repeats.json) | 9 |
| [semif-repeats](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/semif-repeats.json) | 6 |
| [small-local-repeats](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/small-local-repeats.json) | 31 |
| [sonnet55-fresh-matched3](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/sonnet55-fresh-matched3.json) | 24 |
| [typesafe-repeats](https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/typesafe-repeats.json) | 6 |
