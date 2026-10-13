# Codex gate: site content pass

Branch feat/site-content-v2, base ffb9305a, head b9287eb5. Tier: standard (codex-verify.sh). Charter: docs/site-pass/codex-charter.md. Raw artifacts: .claude/verify/site-gate/ (gitignored scratch).

**Verdict: REQUEST-CHANGES. BLOCKING 2, RESIDUAL 3.**

The script's own verdict was REQUEST-CHANGES on one blocking finding (S1). My triage adds a second blocking finding (S3) that the script left AMBIGUOUS because its test could not find the Solar row. Details below.

## Pipeline result

| Stage | Model | Result |
|---|---|---|
| A define | gpt-6-sol high | 3 falsifiable claims (S1, S2, S3), 337 s |
| B write | gpt-6-luna medium | 3 tests written at the pinned head |
| C run | bash | S1, S2, S3 all exit 1 (S3 failed on test setup, not on the claim) |
| D1 triage | gpt-6-luna high | S1 REFUTED, S2 REFUTED, S3 AMBIGUOUS |
| D2 adjudicate | gpt-6-sol high | S1 blocking, S2 residual, S3 not listed |

Cost: 0.7036 USD API-equivalent total (A 0.6164, B 0.0069, D1 0.0025, D2 0.0778). Exit code 1.

Coverage caveat: stage A only produced three claims, so charter items (a) partly, (b), (d), (e), (f), (g) and (h) were not independently tested by codex. My Claude-only passes on those are listed after the findings table.

## Findings

| ID | Claim | Location | Scenario | Label | Reason |
|---|---|---|---|---|---|
| S1 | (c) | public-site/app.js:57 | `applyJevFindings` returns early when the findings feed is null, malformed or slow (the loader resolves null after 3000 ms). The nine Jev OpenRouter native runs then keep the catalog's wrong route and estimate: surface "TypeSafe native Choice API", estimate 0.00589092 for P0 fresh1 instead of OpenRouter native with a known charge. Codex test reproduced it. | BLOCKING | Route and price basis is a money figure. A timeout on a slow connection is a normal user path, and the correction is the override's only job. The defect also exists at base, so it is not a regression, but the fix is incomplete. Fix at the source: make `build_extended_run_catalog_v1.py` emit route and known charge, then delete the runtime override. |
| S3 | (a) | public-site/app.js:203-204 | New note above the overview and comparison lists says charges are provider bills. The cross-category and supplemental feeds say the opposite for known charges: "Known development inference charge covers returned answers only; smoke tests excluded ... no invoice amount is asserted." Solar's 0.022067 USD renders under that note. Confirmed by reading the feed (cross-category-v1.json); codex's test failed on setup so D1 marked it AMBIGUOUS. The working tree already reworded the note to "Costs are provider bills", which keeps the same claim. | BLOCKING | The charge basis changed meaning in the rewrite, which is charter claim (a) verbatim, and it is a published financial figure. Fix: say known provider charge for returned answers, smoke tests and unknown charges excluded, and † marks the API-rate equivalent. |
| S2 | (c) | public-site/app.js:62 | A findings payload with P1 fresh1 data in the P0 fresh1 slot overwrites the P0 run with 0.006405. The override trusts slot names and any binding whose path matches `jev-openrouter-native`, with no check that the pass belongs to the run. | RESIDUAL | Needs a mismatched feed that we write ourselves. Not reachable in normal operation. Moot if S1 is fixed at the source. |
| R1 | (f) | tests/test_liquid_prompt_chart_ui.cjs, tests/test_reference_sensitivity_ui.cjs, tests/test_analysis_refresh_ui.cjs | Caveat assertions were inverted. "not calibrated probabilities", "not validated on new reviews", "not 180 independent cases", "descriptive" and "provisional" now sit under `doesNotMatch`. Numeric assertions were preserved: a script comparing removed against added assertion tokens lost only 540, 180, 60 and two date fragments, all tied to deleted caveat wording. The Liquid confidence-threshold panel no longer carries any calibration caveat, and the only remaining "provisional" is the explore.html footer. | RESIDUAL | Not a data regression. It is a claim-strength decision that is Adam's to confirm: confidence thresholds are shown without saying they are unvalidated. |
| R2 | (h) | CI block in .github/workflows/pages.yml | Not verified at the pinned head. See below. | RESIDUAL | Unverified, not a confirmed defect. |

## Claude-only passes (not codex)

- **(d) factLines:** ran the splitter over every `interpretation` and `publicVerificationLimit` string in the feeds. Ten digit-bearing sentences are dropped, all hedges whose only digits are "60 records" or a run id such as P1. No result figure is hidden. No finding.
- **(e) outcome-chart domain:** traced `xDomain` and `ticks` by hand. Lower bound is floor((min-2)/5)*5 clamped at 0, so every point has valid >= lo and is plotted inside 0 to 100 percent. Empty data falls back to 0 to 60. Zero, single-run and equal-valid cases are fine. No finding.
- **(f) tests:** see R1. No assertion on a feed-derived number was deleted without an equivalent added.
- **(g) innerHTML:** codex was not asked to enumerate this and I did not finish the audit. The changed interpolations I sampled use `esc()` or build from static strings and numbers. Not verified end to end.
- **(a), (b):** only S3 was examined. Panel-id and legacy shim resolution were not independently checked. The site-verify lane's browser run is the right owner.
- **(h) CI block:** I ran all 193 lines of the workflow's check block, but against the working tree, not a pinned checkout. The tree is dirty with in-flight edits from other lanes (about 50 modified files, including app.js and 30 tests), so failures cannot be attributed to b9287eb5. Observed failures: test_analysis_refresh_ui (expected 0.14295744), test_subscription_price_ui and test_public_pairing_ui (expected "API-rate estimate ... Unknown"), test_gemma26_fresh3_p1_interrupted_ui (expected 0.01941923, page now shows 0.0193), and `tests.test_subscription_price_estimates` (an absolute-path error reading results/, an environment issue). The `find public-site -type l` check fails locally only because untracked node_modules symlinks sit under public-site/deck/verify; confirm they are never committed. **Action: re-run the CI block on a clean checkout of the final head before merge.** The gemma26 and analysis-refresh failures are the ones to look at first, since a rounded charge (0.0193) replacing the exact figure would be a precision loss, not just wording.

## Residual bead titles

- S2: Validate Jev findings pass ids against catalog run ids before overriding cost (or delete the override once the catalog builder carries the route).
- R1: Decide whether to restore calibration and validation caveats on the Liquid confidence-threshold panel.
- R2: Re-run the pages.yml check block on a clean checkout of the final site head and attribute any failures.

## To clear the gate

1. Fix S1 in `build_extended_run_catalog_v1.py` so the catalog carries route and known charge, regenerate with its check command, remove `applyJevFindings`.
2. Fix S3 note wording in app.js and update the tests that assert it.
3. Re-run codex-verify.sh against the new head.

---

# Second pass: head 11788f7d (delta from b9287eb5)

Delta: dagger on API-rate figures and one basis note per list in app.js, one assertion in test_subscription_price_ui.cjs. Charter updated to pin 11788f7d with delta claims D1 to D4. Cost 0.4082 USD API-equivalent. Script exit 1. Artifacts: .claude/verify/site-gate2/.

**Verdict at 11788f7d: REQUEST-CHANGES. Open BLOCKING 2, RESIDUAL 5 (cumulative).**

| ID | Location | Scenario | Label | Reason |
|---|---|---|---|---|
| P2-1 (same defect as S3) | public-site/app.js:204 | The note now reads "Costs are provider bills. A † marks the API-rate equivalent ...". Solar's known charge still renders under it, and its feed says "covers returned answers only; smoke tests excluded ... no invoice amount is asserted". The dagger fixes estimates but not the claim about known charges. Codex test reproduced it. | BLOCKING | Money figure with a charge basis the source disclaims. Fix wording: "Known provider charge for returned answers; smoke tests and unknown charges are excluded. † marks the API-rate equivalent." |
| P2-2 | public-site/app.js:197 | A subscription row whose pricing entry has `estimateUsd` null and no charge renders "Unknown†", marking a missing figure as an API-rate equivalent. Reproduced against entries in subscription-price-estimates.json. | RESIDUAL (my triage; codex labelled it blocking) | No wrong number is shown. The figure reads Unknown, and only the dagger is superfluous. Guard with `n(price.estimateUsd) !== null` before adding the dagger. |
| P2-3 | tests/test_subscription_price_ui.cjs:44 | The edited assertion covers only the `price` branch. Dropping the dagger from the `cost.estimatedUsd` branch leaves the suite green. | RESIDUAL | Coverage gap, no runtime failure. Codex's own test errored on `$1.00` vs `$1`, so the gap is reasoned, not run. |

Still open from the first pass: S1 (Jev override falls back to wrong labels when the findings feed is missing) is unchanged by this delta and remains BLOCKING. D4 (note inserted once, static text) held: no finding.

## Residual bead titles (additions)

- P2-2: Show the dagger only when the API-rate estimate is a number.
- P2-3: Add a test for the dagger on the standalone `cost.estimatedUsd` branch.

## To clear the gate

1. S1: fix route and known charge in the catalog builder, drop `applyJevFindings`.
2. P2-1: reword the cost note to the known-charge basis.
3. Re-run against the new head.
