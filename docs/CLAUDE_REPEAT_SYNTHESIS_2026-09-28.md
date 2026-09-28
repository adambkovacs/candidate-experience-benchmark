# Claude repeat comparison: prompt gains did not persist across all three passes

Across these 17 Claude configurations, neither classifier instructions (P1) nor instructions plus a decision tree (P2) improved all-four agreement over the base task (P0) in every observed pass. Seven configurations changed from a gain to a loss across passes for P1; seven did so for P2. The groups overlap and must not be added together.

Each score counts comments matching all four provisional reference labels, out of the same 60 fictional comments. All 153 condition/pass combinations have 60 valid classifications. Valid format and reference agreement remain separate measures.

The table shows the change in all-four matches relative to P0 within each pass. For example, `+2 / +1 / −4` means two more matches in pass one, one more in pass two, and four fewer in pass three. Zero means the totals tied; individual classifications can still differ.

| Configuration | P1 minus P0: passes 1 / 2 / 3 | P2 minus P0: passes 1 / 2 / 3 |
| --- | ---: | ---: |
| Claude Fable 5.1 · low effort · batch 10 | +1 / -1 / 0 | +1 / -3 / -1 |
| Claude Fable 5.1 · medium effort · batch 10 | +2 / -1 / 0 | 0 / 0 / +2 |
| Claude Fable 5.1 · high effort · batch 10 | -2 / +1 / -1 | -1 / 0 / -1 |
| Claude Fable 5.1 · xhigh effort · batch 10 | +1 / 0 / +1 | -1 / 0 / 0 |
| Claude Opus 5 · low effort · batch 10 | -1 / 0 / -1 | 0 / 0 / -2 |
| Claude Opus 5 · medium effort · batch 10 | 0 / 0 / -1 | 0 / +2 / -1 |
| Claude Opus 5 · high effort · batch 10 | 0 / 0 / -1 | +2 / +2 / -2 |
| Claude Opus 5 · xhigh effort · batch 10 | +1 / 0 / +1 | 0 / -2 / 0 |
| Claude Sonnet 5 · low effort · batch 10 | 0 / -1 / +2 | -1 / -3 / +3 |
| Claude Sonnet 5 · medium effort · batch 10 | +2 / +1 / -4 | +1 / +1 / -2 |
| Claude Sonnet 5 · high effort · batch 10 | -1 / -1 / 0 | -1 / 0 / -1 |
| Claude Sonnet 5 · xhigh effort · batch 10 | 0 / -1 / -1 | 0 / 0 / +1 |
| Claude Opus 5.5 · low effort · batch 10 | -1 / +1 / +2 | -2 / 0 / +1 |
| Claude Opus 5.5 · high effort · batch 10 | 0 / +1 / 0 | 0 / 0 / 0 |
| Claude Opus 5.5 · xhigh effort · batch 10 | 0 / +1 / 0 | -1 / +1 / +1 |
| Claude Opus 5.5 · medium effort · batch 10 | 0 / 0 / +1 | -2 / 0 / -1 |
| Claude Haiku 4.5 · fresh matched three · batch 10 | -2 / +1 / +2 | -1 / 0 / -1 |

## Interpretation limits

These are descriptive comparisons of saved configurations. They do not establish that detailed prompts are generally ineffective, or estimate how often a future run will improve. The same comments recur in every pass; configurations and responses are not independent samples. References remain provisional v0.2 labels, with human adjudication still pending.

Haiku uses three fresh passes because its historical transport failures did not qualify as the first pass. The other configurations use eligible historical first passes plus two new passes. Accepted CLI patch differences and unobserved serving behavior remain possible sources of variation. Read each configuration separately before comparing families or effort levels.

Use the [interactive repeat comparison](https://adambkovacs.github.io/candidate-experience-benchmark/#repeat-analysis) for per-field scores, score ranges, changed reviews, and reported usage. The public exports preserve explicit source mappings; [their verification boundary](PUBLIC_EVIDENCE_PRIVACY.md) distinguishes exported evidence from private originals.

## Reproducible sources

Computed from `withinPassPromptDeltas` in the following published report files. Count a sign reversal only when at least one of the three values is positive and another is negative; ties alone are not reversals.

- [claude-roster-repeats.json](../public-site/claude-roster-repeats.json): SHA-256 `11a44a7368695bb8f53961ba05b55b8eeca1701487ecd6036b9a110027af6a4d`.
- [claude-repeats.json](../public-site/claude-repeats.json): SHA-256 `e2da6c5e3dc75b1673d1682a62b5c8a7bbe9fad87ab53e47412b4c4c3f368feb`.
- [haiku-fresh-matched3.json](../public-site/haiku-fresh-matched3.json): SHA-256 `6b49805ec97c55401b85eec2bd5ede5d18b8fe60ad63f7f7daa4fe4a922313f2`.
