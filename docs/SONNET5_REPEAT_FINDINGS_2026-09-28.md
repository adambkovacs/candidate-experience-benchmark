# Sonnet 5: repeated prompt comparisons

All four Sonnet 5 effort settings have nine closed condition/pass combinations, each with 60 valid predictions. The two new passes add 1,440 development responses; smoke requests are separate. Agreement is measured against the unchanged provisional v0.2 references.

| Effort | P0 matches, passes 1/2/3 | P1 matches, passes 1/2/3 | P2 matches, passes 1/2/3 | Reviews changing at least one decision: P0/P1/P2 |
| --- | --- | --- | --- | --- |
| low | 58 / 57 / 54 | 58 / 56 / 56 | 57 / 54 / 57 | 6 / 6 / 9 |
| medium | 56 / 55 / 57 | 58 / 56 / 53 | 57 / 56 / 55 | 7 / 7 / 7 |
| high | 58 / 57 / 57 | 57 / 56 / 57 | 57 / 57 / 56 | 5 / 5 / 4 |
| xhigh | 58 / 57 / 56 | 58 / 56 / 55 | 58 / 57 / 57 | 4 / 5 / 3 |

Every score and changed-review count has a denominator of 60. A changed review can disagree on one or several judgments; it is counted once in the final column.

At medium effort, classifier instructions added two matches in pass one and one in pass two, then lost four in pass three. Decision-tree instructions similarly changed from +1 and +1 to -2. Low effort shows a larger reversal for the decision tree: -1, -3 and +3 matches against P0. These observations do not support treating a small single-pass improvement as a stable prompt advantage.

Extra-high effort did not consistently beat lower effort. Its P1 totals declined from 58 to 56 to 55, while high effort returned 57, 56 and 57. This is a comparison of these saved configurations on one small development set, not an estimate of general model quality or a controlled experiment on the effect of thinking effort alone.

The initial pass used the saved Claude 2.1.280 runtime; new passes used pinned 2.1.282, with exact model `claude-sonnet-5`, batch size ten, the frozen prompt and batch membership, fresh request contexts and no controller retries. The user accepted this CLI-version difference; it remains an experimental limitation. Effective seed, hidden serving revision and provider cache behavior are not fully observable. Separate requests do not establish statistical independence.

The [report builder](../scripts/build_claude_roster_findings.py) validates the raw captures, request/response membership, model and isolation controls, admission hashes, smoke inspections and terminal journals before scoring. New public raw evidence is held while the [privacy export boundary](PUBLIC_EVIDENCE_PRIVACY.md) is verified. Original captures are preserved unchanged; this report does not claim that the pending export is already available.

Client request durations and CLI list-price estimates remain distinct from inference time and subscription charges. No pure inference-time or actual per-run subscription-price measurement is available. These results retain all repeated reviews; they do not create a larger independent test set.
