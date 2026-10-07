# Two-model agreement and human-review deferral

This is a retrospective simulation on the same 60 fictional development reviews. For every pair of the seven saved first-pass P0 native decision-model runs, the fixed rule accepts a four-field answer only when both models return the same complete vector. It defers every other review for human review. The rule compares predictions before looking at the frozen proposed labels. The labels are then used to count accepted matches and errors. No pair was selected or tuned as a preferred deployment choice, no new model call was made, and these results do not establish out-of-sample gains.

The [machine-readable findings](findings.json) report all 21 pairs, exact accepted and deferred IDs, accepted all-four errors, per-field error IDs and reference-by-prediction confusion tables. All scores use the fixed 60-review denominator for coverage. “Correct” here means agreement with the provisional v0.2 labels, not a final adjudication of a candidate's experience. The [seven-model review feed](../../public-site/disputed-reviews-v1.json), [original comments](../../data/pilot/inputs.jsonl), [proposed labels](../../data/pilot/proposed_labels.jsonl) and [labeling guide](../../docs/LABELING_GUIDE.md) provide the review-level context. The feed and its source projections are checked by SHA-256 before calculation.

| Pair | Accepted coverage | Accepted all-four matches | Accepted all-four errors | Deferred for review | Known two-run development charge |
| --- | ---: | ---: | ---: | ---: | ---: |
| Liquid D1 + Tev 1 4B | 33/60 | 33/33 | 0 | 27 | $0.032031992 |
| Liquid D1 + Solar Decide | 43/60 | 43/43 | 0 | 17 | $0.03775612 |
| Liquid D1 + Clef | 45/60 | 42/45 | 3 | 15 | $0.04753568 |
| Liquid D1 + Clef Flash | 40/60 | 36/40 | 4 | 20 | $0.02763158 |
| Liquid D1 + Luna Decisions | 38/60 | 37/38 | 1 | 22 | $0.02904142 |
| Liquid D1 + Perplexity Decider V1 27B | 46/60 | 42/46 | 4 | 14 | $0.03111648 |
| Tev 1 4B + Solar Decide | 45/60 | 44/45 | 1 | 15 | $0.038409872 |
| Tev 1 4B + Clef | 42/60 | 41/42 | 1 | 18 | $0.048189432 |
| Tev 1 4B + Clef Flash | 39/60 | 36/39 | 3 | 21 | $0.028285332 |
| Tev 1 4B + Luna Decisions | 42/60 | 40/42 | 2 | 18 | $0.029695172 |
| Tev 1 4B + Perplexity Decider V1 27B | 44/60 | 43/44 | 1 | 16 | $0.031770232 |
| Solar Decide + Clef | 52/60 | 52/52 | 0 | 8 | $0.05391356 |
| Solar Decide + Clef Flash | 44/60 | 44/44 | 0 | 16 | $0.03400946 |
| Solar Decide + Luna Decisions | 49/60 | 48/49 | 1 | 11 | $0.03541930 |
| Solar Decide + Perplexity Decider V1 27B | 53/60 | 53/53 | 0 | 7 | $0.03749436 |
| Clef + Clef Flash | 47/60 | 43/47 | 4 | 13 | $0.04378902 |
| Clef + Luna Decisions | 50/60 | 48/50 | 2 | 10 | $0.04519886 |
| Clef + Perplexity Decider V1 27B | 53/60 | 51/53 | 2 | 7 | $0.04727392 |
| Clef Flash + Luna Decisions | 40/60 | 38/40 | 2 | 20 | $0.02529476 |
| Clef Flash + Perplexity Decider V1 27B | 45/60 | 43/45 | 2 | 15 | $0.02736982 |
| Luna Decisions + Perplexity Decider V1 27B | 48/60 | 47/48 | 1 | 12 | $0.02877966 |

Every pair runs both models on all 60 reviews. The cost column sums their saved known development charges, including reviews later deferred. It excludes smoke calls, human review, deployment and any invoice difference; if either run lacks a reconciled charge, the pair cost is unavailable. The [normalized run feed](../../public-site/supplemental-decision-runs-v1.json) and each model's saved projection are the cost sources. Lower accepted-error counts can result from deferring more reviews, so interpret errors beside accepted coverage and the exact deferred IDs. The same review appears in many pairs; 21 rows are not 21 independent samples.

Run `python3 scripts/analyze_native_agreement_policy_v1.py` to rebuild the two files, or add `--check` to verify saved bytes. The script rebuilds the seven-model feed from its pinned sources, checks all 60 record charges where a cost is shown, and makes no inference request.
