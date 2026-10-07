# Native decision model first-pass analysis

This is an offline comparison of six exact `fresh1/P0` OpenRouter native Choice configurations on the same 60 fictional development comments. Each record is counted once per configuration. The [normalized feed](../../public-site/supplemental-decision-runs-v1.json) names the runs and binds their [saved projections](../../results/); the [frozen proposed labels](../../data/pilot/proposed_labels.jsonl) supply the offline reference. `findings.json` records SHA-256 hashes for all inputs, per-field confusion tables, case errors and all 15 model pairs. No model was called for this analysis.

## What the first passes show

Solar Decide had the most four-field matches in this six-run set: 55/60. The six totals alone hide which fields and reviews differ. The "testimonial potential = yes" reference class has only 9/60 cases; its recall and precision need those denominators visible. The counts below describe agreement with the saved reference, not truth or hiring suitability.

| Configuration | All four match | Testimonial field matches | Testimonial yes recall | Testimonial yes precision | Known development charge |
| --- | ---: | ---: | ---: | ---: | ---: |
| Liquid D1 | 43/60 | 58/60 | 8/9 | 8/8 | $0.01568912 |
| Tev 1 4B | 45/60 | 56/60 | 9/9 | 9/12 | $0.016342872 |
| Solar Decide | 55/60 | 58/60 | 8/9 | 8/8 | $0.022067 |
| Clef | 54/60 | 58/60 | 8/9 | 8/8 | $0.03184656 |
| Clef Flash | 45/60 | 57/60 | 9/9 | 9/11 | $0.01194246 |
| Luna Decisions | 49/60 | 56/60 | 6/9 | 6/6 | $0.0133523 |

The per-field majority reference baseline is 6/60 on all four together. It repeats the modal reference label for each field and is a hindsight description of this sample, not a learned or deployable rule. The per-field choices and counts are in `findings.json`.

The hindsight oracle union is 58/60: for each review it selects a model *after seeing the reference* if any of the six matched all four fields. It cannot be deployed as an ensemble and is not a prediction of ensemble performance. All six configurations differed from the reference on DEV-029, DEV-030. `all_four_errors_by_case` shows every error and its field. Across 15 pairs, prediction vectors differed on 8 to 27 of 60 shared-valid reviews. Disagreement does not tell us which answer is right.

The [input comments](../../data/pilot/inputs.jsonl) and [labeling rubric](../../docs/LABELING_GUIDE.md) explain why those two reviews need care. DEV-029 is an off-topic restaurant review ("Great soup, tiny portions..."); its frozen reference uses `insufficient_information` for every recruitment decision. DEV-030 says an accessibility issue in an assessment may have been resolved, but the candidate does not know whether another assessment is available. Its reference asks for follow-up while leaving the serious-concern field unresolved. These shared misses can reflect task-boundary handling and disputed reference judgments; they are not six proven real-world model errors. The original scores are unchanged.

On known development charges and all-four matches, the nondominated runs in this six-run set are: Solar Decide, Clef Flash, Luna Decisions. This frontier excludes smoke calls, invoice uncertainty, latency and other operational qualities. Prices, providers, request controls and model behavior differ; no cost difference here is a causal model-efficiency claim. Charges are the saved known development amounts, not invoices.

## Limits and reproduction

The 60 synthetic comments are one development set, and the original reference remains disputed in some cases. These six routes have distinct models, providers, controls and prices; all use the same first P0 condition, but they are not matched interventions. Repeats are excluded rather than treated as more cases. Positive-class precision has no value when a run predicts zero positives. Confusion tables use reference labels as rows and model predictions as columns. All full-run scores use 60, including invalid outputs if any; these selected six each have 60 valid outputs.

Run `python3 scripts/analyze_native_decision_cohort_v1.py` from the repository root to regenerate the two outputs, then `python3 scripts/analyze_native_decision_cohort_v1.py --check` to compare bytes. The script verifies exact run IDs, source hashes, 60 unique review IDs, field totals, published scores and charges before writing. It does not read private raw responses or send references to a model.

Run `python3 -O scripts/analyze_native_decision_cohort_v1.py --self-test` to verify the same checks under optimized Python, including rejection of a deliberately altered projection in a temporary directory.
