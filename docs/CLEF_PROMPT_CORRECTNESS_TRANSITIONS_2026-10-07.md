# Clef prompt changes and four-answer correctness

The [source-bound Clef repeat report](../public-site/clef-closed-repeat-findings.json) now records, for each matched clean prompt pair, the review IDs that became a full four-answer match with the frozen provisional reference and those that stopped matching. Every pair below compares the **same 60 reviews with 60 valid answers in both runs**. A changed answer need not change whether all four answers match.

| Matched pass | Prompt comparison | Changed reviews | Became full matches | Lost full matches | Full matches before → after |
| --- | --- | ---: | --- | --- | ---: |
| Fresh 1 | P0 → P1 | 4 | DEV-056 | DEV-013, DEV-014 | 53 → 52 |
| Fresh 2 | P0 → P1 | 5 | DEV-056 | DEV-013, DEV-014, DEV-035 | 53 → 51 |
| Fresh 2 | P0 → P2 | 6 | None | DEV-013, DEV-014, DEV-018, DEV-035 | 53 → 49 |
| Fresh 2 | P1 → P2 | 3 | None | DEV-018, DEV-056 | 51 → 49 |
| Fresh 3 | P0 → P1 | 5 | DEV-056 | DEV-013, DEV-014, DEV-035 | 53 → 51 |

The P2 runs in fresh 1 and fresh 3 are interrupted. Fresh 1 has 59 valid answers and one unknown outcome after its exact never-sent continuation. Fresh 3 has one unknown outcome and 59 reviews never sent. The report lists all four affected P0/P2 and P1/P2 pairs under `promptComparisonExclusions`, with **no paired comparison denominator or gain/loss claim** for them. The one clean P2 run is fresh 2; its comparisons above do not imply a three-pass P2 repeat result.

These are observed differences under frozen prompts on the same 60 synthetic reviews, not a causal estimate for future reviews. The [v0.2 label key](../data/pilot/proposed_labels.jsonl) was kept out of inference requests and used offline; the project owner confirmed human checks of all 60 reviews on 2 October. Its provisional status and review history are documented in the [reference review](REFERENCE_REVIEW_V1.md). No inference, reference-label change, or repair of interrupted responses was made for this analysis.
