# Provisional-reference sensitivity, without changing the key

The [dated reference review](../../docs/REFERENCE_REVIEW_V1.md) proposes changing DEV-006 serious concern from `insufficient_information` to `no`. Its [versioned proposal](../../data/pilot/reference-revisions/v0.3.json) also records two sentiment alternatives that still need human adjudication: DEV-013 `neutral` to `positive`, and DEV-030 `neutral` to `negative`. These are the only hypothetical labels used here. The frozen [v0.2 labels](../../data/pilot/proposed_labels.jsonl) and published benchmark scores remain unchanged.

The [machine-readable findings](findings.json) show each alternative alone and all four combinations of two or three, with exact affected IDs, saved and hypothetical scores, and per-run field and all-four deltas. Each run keeps its original 60-position denominator and invalid or unsent outputs. The 637-run extended cohort comes from the [source-bound public case feed](../../public-site/extended-cases-v1.json). The separate seven-model first P0 cohort comes from the [seven-native review feed](../../public-site/disputed-reviews-v1.json). A run appearing in both views is not a new observation. The same 60 fictional reviews appear across configurations and repeats; counts of improved runs are not independent samples.

| Hypothetical changes | Extended runs improved / declined / unchanged | Seven-native runs improved / declined / unchanged |
| --- | ---: | ---: |
| DEV-006 serious_concern_reported → no | 212 / 168 / 257 | 5 / 1 / 1 |
| DEV-013 sentiment → positive | 289 / 185 / 163 | 2 / 2 / 3 |
| DEV-030 sentiment → negative | 136 / 94 / 407 | 0 / 0 / 7 |
| DEV-006 serious_concern_reported → no, DEV-013 sentiment → positive | 259 / 163 / 215 | 3 / 1 / 3 |
| DEV-006 serious_concern_reported → no, DEV-030 sentiment → negative | 257 / 165 / 215 | 5 / 1 / 1 |
| DEV-013 sentiment → positive, DEV-030 sentiment → negative | 241 / 154 / 242 | 2 / 2 / 3 |
| DEV-006 serious_concern_reported → no, DEV-013 sentiment → positive, DEV-030 sentiment → negative | 265 / 153 / 219 | 3 / 1 / 3 |

The v0.3 DEV-006 proposal is an AI review, not a human-adjudicated replacement. DEV-013 and DEV-030 remain unresolved; the alternatives are plausible readings documented in that review, not recommended new labels. A positive delta means closer agreement with a hypothetical key on these saved predictions, not better performance on real candidates. Because these three alternatives affect distinct reviews, each combined run delta equals the sum of its single-review deltas. No model request was made and no reference file was edited.

Run `python3 scripts/analyze_reference_sensitivity_v1.py` to regenerate the outputs, or `python3 scripts/analyze_reference_sensitivity_v1.py --check` to verify saved bytes. The builder rechecks the extended and seven-native feeds against their SHA-bound public sources and refuses changed reference-proposal fields.
