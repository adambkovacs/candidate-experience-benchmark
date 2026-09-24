# AnyJev cached-score L1 cross-validation

This exploratory run fitted [AnyJev's pinned `TemperatureScaler.fit/apply`](https://github.com/nokia-applied-research/AnyJev/blob/3cd8c6fcd9e90fc04214575ade6779da1e3f3704/anyjev/calibrate/posthoc.py#L27-L57) to the 60 saved Qwen3-0.6B L0 score vectors. It made no model request, download, or GPU call. The [review receipt](root-review-receipt.json) records the approved hashes and protocol before fitting. The separate configuration is `anyjev-qwen06-cached-score-l1-cv5`.

The [frozen fold map](folds-v1.json) assigns five 12-record evaluation folds from IDs and the six contrast-pair memberships, without reading labels. Each fit used the other 48 labels for one question. All six pairs stayed together. The [evaluation](evaluation.json) contains one held-out prediction for every record and question, 20 fold-specific temperatures, per-fold training class support, fixed-bin metrics, and runtime provenance. NLL is mean negative log probability of the true class; Brier is mean sum of squared class errors; ECE uses 10 equal-width bins of top-class confidence, fixed before fitting. Lower values are better.

| Question | NLL L0 → L1 | Brier L0 → L1 | ECE L0 → L1 | Accuracy, both |
| --- | ---: | ---: | ---: | ---: |
| Sentiment | 1.2077 → 1.1221 | 0.6223 → 0.5686 | 0.2617 → 0.1591 | 37/60 |
| Follow-up needed | 1.1961 → 1.1020 | 0.7334 → 0.6689 | 0.2140 → 0.1214 | 13/60 |
| Serious concern reported | 1.0118 → 0.9957 | 0.6093 → 0.5872 | 0.1742 → 0.0897 | 34/60 |
| Testimonial potential | 0.8126 → 0.6280 | 0.4885 → 0.3714 | 0.2564 → 0.1246 | 44/60 |

All 240 saved decision rankings and argmax choices were preserved. The scores and labels are development data; the labels are AI-reviewed and provisional. Each fit had 48 labels, below [AnyJev's stated 100–500 L1 calibration range](https://github.com/nokia-applied-research/AnyJev/blob/3cd8c6fcd9e90fc04214575ade6779da1e3f3704/docs/levels.md#L73-L104). This grouped cross-validation estimates out-of-fold behavior on the existing score surface. It does not create a separately validated deployment calibrator or show that fresh `Decider` calls reproduce these cached scores.

The fold 4 training sets had no `insufficient_information` labels for follow-up or testimonial. The fixed option vectors and folds were retained. Four of five follow-up temperatures reached the upper search limit, `exp(3) ≈ 20.0855`, so their fitted optima may lie outside [the pinned search range](https://github.com/nokia-applied-research/AnyJev/blob/3cd8c6fcd9e90fc04214575ade6779da1e3f3704/anyjev/calibrate/posthoc.py#L34-L57). These sparse classes and boundary fits limit how much the improved confidence metrics can be trusted beyond these 60 records.

Pinned evidence: [L0 scores](../anyjev-qwen06-l0-mps-2026-09-23/development.jsonl) SHA-256 `fba96b08c10f8d85b2ab7e510902689dee302369f33e4f91baf152102cb524a1`; fold map SHA-256 `7be25f9bcd9dfbde383bccefe4ad9e4c5a8d6a664b4964789c532dac299dff0c`; evaluation SHA-256 `50e3450c484c2e5587b726fea4e79ca31de4149350ea55de92b95bd202218ee2`. The runner and its seven focused tests are [here](../../scripts/anyjev_cached_l1.py) and [here](../../tests/test_anyjev_cached_l1.py).
