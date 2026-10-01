# Qwen 27B: repeat scores and changed answers

Similar scores hid changed answers. Across three passes of the base prompt, Qwen 27B medium matched all four provisional reference decisions for 56 to 59 of 60 comments; xhigh matched 57 to 58. Each setting has scores for all three prompts in all three passes. Fresh pass 3 P0 combined separately sent responses after a failure; xhigh P1 also combined separate sends, while medium P1 ran as a complete stage. This is a [descriptive analysis](../public-site/qwen27-final-descriptive-findings.json), not a clean matched three-pass result.

| Setting and prompt | Pass 1 | Pass 2 | Pass 3 | Range, out of 60 |
| --- | ---: | ---: | ---: | ---: |
| Medium P0, base task | 56 | 59 | 57 | 56–59 |
| Medium P1, classifier instructions | 54 | 58 | 56 | 54–58 |
| Medium P2, instructions and decision tree | 57 | 56 | 57 | 56–57 |
| Xhigh P0, base task | 58 | 57 | 58 | 57–58 |
| Xhigh P1, classifier instructions | 57 | 57 | 58 | 57–58 |
| Xhigh P2, instructions and decision tree | 57 | 58 | 57 | 57–58 |

Scores keep all 60 comments in the denominator. Medium P0 pass 3 retains the original service error at DEV-022; xhigh P0 pass 3 retains DEV-037. Neither failed request was retried. The [second-continuation findings](QWEN27_V2_SECOND_CONTINUATION_FINDINGS_2026-10-01.md) explain which unsent requests were completed later. Those two P0 scores have 59 valid responses and one service error. Both P1 pass 3 scores have 60 valid responses.

Answer-change counts use a different denominator: only comments with valid answers in every compared phase. Across all three passes, medium changed at least one of four answers on 3 of 59 comparable P0 comments, 4 of 60 P1 comments, and 3 of 60 P2 comments. Xhigh changed 4 of 59 for P0, 3 of 60 for P1, and 4 of 60 for P2. The failed P0 comment is excluded from each P0 answer-change rate, but remains in its fixed-60 score. The [source-bound report](../public-site/qwen27-final-descriptive-findings.json) lists the changed IDs and each pair of passes separately.

Prompt comparisons also vary by pass. Medium P2 matched one more all-four reference than P0 in pass 1, three fewer in pass 2, and the same number in pass 3. Xhigh P2 matched one fewer, one more, and one fewer respectively. In pass 3, the P0-to-P1 complete answer changed on 2 of 59 shared-valid comments for medium and 1 of 59 for xhigh. These are observed differences among repeated model requests, not evidence that the prompt alone caused a change.

The original failed P0 request in each setting retains a possible charge bounded at $0.047001600. A bound is not a reported charge. The [medium](../results/repeatability-v1/qwen27-fresh-matched3-v2/interruption-continuation-v2/medium/terminal-reconciliation-after-completion.json) and [xhigh](../results/repeatability-v1/qwen27-fresh-matched3-v2/interruption-continuation-v2/xhigh/terminal-reconciliation-after-completion.json) second child budgets closed with known charges of $0.089620125 and $0.047987850 and no new unknown charge. Request durations include transport and service overhead; provider-reported reasoning-token counts are kept separate from completion tokens. The [reference labels](../data/pilot/proposed_labels.jsonl) are AI-authored and have not been independently adjudicated.

The seven uninterrupted phases remain in the [original hosted report](../public-site/hosted-v2-repeats.json). The first [interruption cutoff](../public-site/qwen27-interrupted-continuation-findings.json) and later [second cutoff](../public-site/qwen27-second-continuation-findings.json) remain separate snapshots. The [nine-phase reporter](../scripts/build_qwen27_final_descriptive_findings.py) checks those sources and marks the two combined phases as interrupted composites.
