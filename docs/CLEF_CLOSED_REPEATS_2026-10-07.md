# Clef native repeat findings, 7 October 2026

The [source-bound findings](../results/clef-native-v1/clef-closed-repeat-findings-public.json) cover all nine declared Clef P0/P1/P2 repeat cells on the same 60 synthetic development reviews. Seven full cells contain 60 valid responses. Two P2 cells were interrupted and have no clean 60-response score. The public [website copy](../public-site/clef-closed-repeat-findings.json) is byte-identical to the verified findings file.

| Condition | Clean full-run agreement with the frozen four-label key | Interrupted evidence |
| --- | --- | --- |
| P0 | Fresh 1, 2 and 3: **53/60** each. All three clean pairs produced identical predictions on all 60 records. | None. |
| P1 | Fresh 1: **52/60**; fresh 2 and 3: **51/60** each. Fresh 1 differs from each later pass on one record; fresh 2 and 3 are identical. | None. |
| P2 | Fresh 2: **49/60**. | Fresh 1 has **59 valid, one unknown**, and **48 known four-label matches** after an exact never-sent suffix. Fresh 3 has **one unknown and 59 never sent**. Neither is a clean matched repeat or receives a 60-record agreement score. |

Across clean runs in the same repeat, changing prompts altered at least one predicted field on four records in fresh 1 (P0–P1), three to six records across the three fresh 2 condition pairs, and five records in fresh 3 (P0–P1). These are paired prediction differences, not causal estimates of prompt benefit. The findings file gives every per-field confusion matrix, class balance, pairwise change count and observed token total.

The frozen [v0.2 proposed label key](../data/pilot/proposed_labels.jsonl) was applied offline, never sent in inference requests. The owner confirmed human checks of all 60 reviews on 2 October; the key remains provisional, as described in the [reference review](REFERENCE_REVIEW_V1.md). All agreement figures refer to that key. The reported input-price estimates use saved response token counts and [Cloudflare's Clef rate](https://developers.cloudflare.com/workers-ai/models/clef/). Full-context reservations are separate conservative bounds; neither is a provider invoice or verified charge.
