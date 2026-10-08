# Codex gate: talk and site work

- Tier: standard (`scripts/codex-verify.sh`, DEFINE/WRITE/RUN/ADJUDICATE)
- Base: 6243eb3d. Head: 82fb8384cfd55ecd26fce58f9ecfbfb4ec34e502 (origin/main tip)
- Charter: docs/talk/codex-charter.md
- Exit code: 1 (REQUEST-CHANGES). Score 55/100.

## Verdict

REQUEST-CHANGES on three BLOCKING findings and one RESIDUAL. The falsification test for each of S1 to S4 failed on the pinned commit (stage C rc=1). Test logs are in the uncommitted run directory `.claude/verify/gate-1/`.

## Findings

| Id | Label | Location | Summary |
|----|-------|----------|---------|
| S1 | BLOCKING | public-site/navigation.js:74 | Opening index.html#inspect leaves a visitor on the Read page without an inspect target. Claim 2 (legacy anchor forwarding) is partly refuted. |
| S2 | BLOCKING | public-site/index.html:218, public-site/explore.html:243 | "Method and limits" links follow #method on the same page, where the section no longer exists. Claim 2 refuted. |
| S3 | BLOCKING | public-site/presentation.html:600 | The visible $1.2013 and $0.13 appendix figures carry data-doc but no JSON data-source binding, so the feed-binding check cannot verify them. Claim 1 refuted. |
| S4 | RESIDUAL | tests/test_presentation_ui.cjs:8 | Tests execute meetup-presentation.js, which the rebuilt presentation page does not load. A navigation regression in the loaded deck scripts could pass. Coverage gap. Claim 5 partly refuted. |

Claims 3, 4 and 6 produced no confirmed finding.

## Cost (API equivalent)

| Stage | Model | Effort | Input tokens | Output tokens | Wall s | USD |
|-------|-------|--------|--------------|---------------|--------|-----|
| A | gpt-6-sol | high | 1094633 | 10755 | 322 | 0.6103 |
| B | gpt-6-luna | medium | 231393 | 3222 | 58 | 0.0078 |
| D1 | gpt-6-luna | high | 24290 | 314 | 12 | 0.0026 |
| D2 | gpt-6-sol | high | 81587 | 2479 | 64 | 0.0999 |
| Total | | | | | | 0.7207 |

## Raw verdict text

```
- S1: CONFIRMED | public-site/navigation.js:74 | Opening index.html#inspect leaves a visitor on the Read page without an inspect target. The cited navigation code only aligns targets present on the current page. (blocking: BLOCKING: a normal visitor's existing deep link fails after the page split.)
- S2: CONFIRMED | public-site/index.html:218; public-site/explore.html:243 | Clicking "Method and limits" on either page follows #method on that same page, where the section no longer exists. (blocking: BLOCKING: visible links fail to reach their promised section in normal use.)
- S3: CONFIRMED | public-site/presentation.html:600 | The visible $1.2013 and $0.13 appendix figures have data-doc attributes but no JSON data-source binding, so the deck's feed binding check cannot verify them. (blocking: BLOCKING: the change's promised feed-bound number feature fails for visible figures.)

Residuals (non-blocking, file as follow-up):
- S4: CONFIRMED | tests/test_presentation_ui.cjs:8 | The presentation tests execute meetup-presentation.js, which the rebuilt presentation page does not load. A navigation regression in the loaded deck scripts could therefore pass these tests. (not blocking: RESIDUAL: this is a coverage gap; the evidence does not show a deck navigation failure.)

FINAL VERDICT: REQUEST-CHANGES
Score: 55/100
```
