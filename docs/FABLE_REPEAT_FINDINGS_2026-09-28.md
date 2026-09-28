# Fable 5.1 repeat findings

All four effort settings have three completed passes for each of P0, P1 and P2. Every condition/pass combination produced 60 valid outputs. The two new passes across four efforts contain 1,440 development responses; smoke tests are separate. The same 60 reviews are reused, so these are not 1,440 independent cases.

Scores below count reviews where all four classifications agree with the provisional v0.2 reference labels, out of 60. P0 is the baseline prompt, P1 adds classifier instructions, and P2 adds an operating procedure and decision tree. The labels were reviewed by AI and still contain unresolved human-adjudication questions.

| Effort | P0: three scores | P1: three scores | P2: three scores | Reviews that changed across passes: P0 / P1 / P2 |
| --- | --- | --- | --- | --- |
| Low | 56, 58, 57 | 57, 57, 57 | 57, 55, 56 | 5 / 3 / 3 |
| Medium | 56, 57, 56 | 58, 56, 56 | 56, 57, 58 | 3 / 2 / 3 |
| High | 58, 56, 57 | 56, 57, 56 | 57, 56, 56 | 4 / 3 / 3 |
| Extra high | 57, 57, 56 | 58, 57, 57 | 56, 57, 56 | 1 / 1 / 2 |

A review counts as changed when at least one of its four classifications differs between passes under the same prompt condition. Each change count has a denominator of 60; it does not count how many individual fields changed.

## What the repeats show

**An unchanged score can conceal changed answers.** Low-effort P1 scored 57 in every pass, but three reviews changed classifications. Aggregate scores alone therefore do not describe repeatability.

**More detailed prompts did not produce a consistent improvement.** P1's change from P0 ranged from −1 to +1 reviews at low effort, −1 to +2 at medium, and −2 to +1 at high. Extra-high P1 matched or exceeded P0 by zero or one review in each pass. These small differences on a development set do not establish a general advantage.

**P2's effect depended on the effort setting.** At medium effort, P2 matched P0 twice and exceeded it by two reviews once. At high and extra-high effort it matched or fell below P0. At low effort its changes were +1, −3 and −1. The operating procedure should therefore be evaluated as an experimental condition, rather than assumed to help.

**Extra-high effort had fewer observed flips in this sample.** Its change counts were one, one and two reviews for P0, P1 and P2. This describes the observed three passes; it does not prove that higher effort causes more stable classifications or justify a wider ranking.

## Measurement limits and evidence

The historical first pass used Claude Code 2.1.280; the two new passes used pinned 2.1.282 through the Claude subscription. Model route, effort, prompt text, ordered batch membership and parser are checked against frozen evidence. Effective seed and hidden serving revision are unavailable. Separately dispatched requests do not prove statistical independence.

Token usage, client request duration, CLI-reported API duration and list-price estimates are retained where returned. Client or CLI duration is not pure model inference time. List-price estimates are not subscription charges; actual billed cost and quota attribution are unavailable.

The [machine-readable report](../public-site/claude-roster-repeats.json) includes per-field agreement, class counts, individual changed-review IDs, paired prompt differences and source hashes. The [report builder](../scripts/build_claude_roster_findings.py) validates raw captures, predictions, phase admissions and frozen requests. The [execution protocol](CLAUDE_REPEAT_ROSTER.md) documents the experiment controls.
