# Opus 5.5: repeated prompt comparisons

All four effort settings have nine closed condition/pass combinations, each with 60 valid outputs. Medium effort was completed earlier under its separate controller. The newly completed low, high and extra-high series preserve their own historical first passes and add two full passes per condition.

| Effort | P0 matches, passes 1/2/3 | P1 matches, passes 1/2/3 | P2 matches, passes 1/2/3 | Reviews changing at least one decision: P0/P1/P2 |
| --- | --- | --- | --- | --- |
| low | 59 / 58 / 57 | 58 / 59 / 59 | 57 / 58 / 58 | 4 / 2 / 3 |
| medium | 58 / 58 / 57 | 58 / 58 / 58 | 56 / 58 / 56 | 1 / 1 / 2 |
| high | 59 / 58 / 58 | 59 / 59 / 58 | 59 / 58 / 58 | 2 / 1 / 2 |
| xhigh | 58 / 57 / 57 | 58 / 58 / 57 | 57 / 58 / 58 | 1 / 1 / 1 |

Every score and change count is out of the same 60 synthetic reviews. Scores count agreement on all four judgments with the unchanged provisional v0.2 reference. Changes count reviews whose four-field answer differed at least once across passes.

High effort returned the same P0 and P2 totals in each paired pass: 59 versus 59, then 58 versus 58 twice. This is no observed aggregate gain from the decision tree in these three comparisons. It is not evidence that the predictions are identical or that the prompts are equivalent on other reviews.

At low effort, P1 changed from one fewer match than P0 to one more and then two more. P2 changed from two fewer to equal and then one more. Extra-high P2 also crossed from one fewer to one more. These small, changing differences argue against choosing a prompt from one pass alone.

Medium P1 stayed at 58/60 in all three passes while one review changed classification. Equal aggregate scores can hide different decisions. The per-record flip lists remain part of the report.

The new low/high/extra-high runs used exact model `claude-opus-5-5`, pinned Claude CLI 2.1.282, batch size ten, frozen prompts and ordered membership, with separately inspected three-record smokes. Historical first passes used CLI 2.1.280. The earlier medium series retains its separate recorded runtime and admission contract. No controller retry, model substitution or repaired prediction was introduced. Seed, provider caching and hidden serving revisions remain limitations.

These scores are development observations against AI-reviewed references, not independent human ground truth or a general ranking of thinking effort. Request durations include client and service overhead. CLI list-price estimates are not actual subscription charges; pure inference time and per-run billed subscription cost are unavailable.

The new roster evidence passed private raw-capture and source-binding checks. Its public export is pending the [privacy boundary](PUBLIC_EVIDENCE_PRIVACY.md); original evidence remains unchanged. The previously published [medium-effort report](../public-site/claude-repeats.json) stays separate from the new three-series evidence.
