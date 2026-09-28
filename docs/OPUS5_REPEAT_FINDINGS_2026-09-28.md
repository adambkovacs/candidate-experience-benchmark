# Opus 5 repeat findings

All four effort settings have three closed passes for P0, P1 and P2. Every combination produced 60 valid outputs. The two new passes add 1,440 development responses across four configurations; smoke tests are separate. These are repeated measurements of the same 60 synthetic reviews.

Scores count agreement with provisional v0.2 references on all four fields, out of 60. P0 is the baseline prompt, P1 adds classifier instructions, and P2 adds an operating procedure and decision tree. The references are AI-reviewed and still have unresolved human-adjudication questions.

| Effort | P0 scores | P1 scores | P2 scores | Reviews changing at least one classification: P0 / P1 / P2 |
| --- | --- | --- | --- | --- |
| Low | 56, 55, 57 | 55, 55, 56 | 56, 55, 55 | 3 / 1 / 4 |
| Medium | 55, 56, 56 | 55, 56, 55 | 55, 58, 55 | 3 / 5 / 4 |
| High | 55, 56, 58 | 55, 56, 57 | 57, 58, 56 | 4 / 3 / 3 |
| Extra high | 57, 58, 57 | 58, 58, 58 | 57, 56, 57 | 3 / 1 / 1 |

Change counts use a denominator of 60 and count each review once if any field differs across the three passes under that prompt. They are not counts of individual field changes.

## Findings

**A prompt advantage can reverse between passes.** At high effort, P2 exceeded P0 by two all-four matches in the first two passes, then fell below it by two in the third. That pattern does not support treating the first-pass gain as a reliable improvement.

**The highest stable aggregate score still contained a changed answer.** Extra-high P1 scored 58/60 every time, but one review changed classification. The score and the per-review comparison answer different questions.

**Extra instructions were not uniformly beneficial.** Low-effort P1 matched or fell below P0 in each pass. Medium-effort P2 changes were zero, +2 and −1. Extra-high P1 matched or exceeded P0 by zero or one, while P2 matched or fell below it. These are small development-set differences, not evidence of a general model or prompt ranking.

## Controls and limits

Model, effort, prompt bytes, ordered batches and parser were checked against the frozen manifests and raw responses. Historical Claude Code was 2.1.280; the repeat runtime was pinned to 2.1.282. Effective seed and hidden serving revision are unavailable. Separate requests do not prove statistical independence.

Reported request time is client elapsed time. CLI API duration is a separate returned measurement, not pure model inference time. Token usage and list-price estimates are retained where available; those estimates are not Claude subscription charges. Actual billed cost and per-run quota consumption remain unavailable.

See the [machine-readable report](../public-site/claude-roster-repeats.json), [execution protocol](CLAUDE_REPEAT_ROSTER.md), and [source-validation code](../scripts/build_claude_roster_findings.py). The original Fable series remain unchanged in the same report.
