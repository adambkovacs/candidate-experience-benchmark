# Final pre-merge verification, PR #6

Head 1bf2dc67 on feat/site-content-v2. Worktree clean of tracked changes (only untracked files). Nothing was committed.
Scripts, raw results and the three 1440 fold captures are in `docs/site-pass/final/`.

**Verdict: REQUEST-CHANGES. Blocking 1, residual 6.** The one blocking item is a two-line doc fix (claim 7). Every live-page claim passed.

## Claims

| # | Claim | Result | Evidence |
|---|---|---|---|
| 1 | Pages "Check static public bundle" passes line by line | PASS, with the two documented environment failures only | 144 logical commands run one by one (`run-workflow.py`, `workflow-results.json`). 142 exit 0. Two non-zero: the symlink find (all 5 hits under gitignored `public-site/deck/verify/node_modules`, 0 elsewhere, 0 tracked) and `tests.test_subscription_price_estimates` (2 of 7 tests error with an absolute path into `/Users/adamkovacs/Documents/codebuild/...`, nothing else). The final tail block (git archive roots, tamper check, cmp) and `json.tool` exit 0. `node --test`: 18 invocations, **234 tests, 234 pass, 0 fail, 0 skipped, 0 cancelled**. |
| 2 | Every data-source and data-derived number matches its feed after render | PASS | Rendered at 1440 with all `<details>` open. See table below. 0 mismatches after accounting for display formatting. |
| 3 | Every LINK-MAP id exists once; shim forwards old links | PASS | 161 table rows plus the "new ids" and Explore-layout lists: 0 missing, 0 duplicated on the target page after render. 167 old links (161 ids plus 6 query-string forms) forwarded to the right page, same hash, target in the DOM and visible. Two targets (`reference-note`, `evidence-note-empty`) are `hidden` by design. Four links logged "Failed to fetch" in a bulk run while the machine was loaded; re-run singly after full load: 0 console errors, landed correctly. |
| 4 | Three pages at 1440x900 and 390x844, details open: 0 errors, 0 failed requests, 0 overflow | PASS | 6 of 6 combinations: 0 console errors, 0 page errors, 0 failed requests, 0 HTTP 4xx/5xx, horizontal overflow 0 (document and body). All details open (index 2, explore 106, method 1). Warnings: index at 1440 only, two copies of the headless GPU stall message ("GPU stall due to ReadPixels"), a SwiftShader driver note, not a page warning. |
| 5 | Rendered-text counts, at most one each, middle dot zero | PASS | See counts table below. |
| 6 | Deck still binds | PASS | `numbers.mjs --page presentation.html`: RESULT PASS, live 436 number + 15 review, print 450 + 21, 922 PASS rows, 0 FAIL. `content-audit.mjs`: RESULT PASS (every row PASS). `offline-check.mjs`: PASS. My own file:// load of `presentation-offline.html`: 31 slides, no "Failed to fetch" in the text, 0 console errors, 0 failed requests. |
| 7 | Pair counts 895, 446, 41, 25 replace 853, 423, 35, 23; no live page shows 853 | **PARTIAL, blocking item B1** | Feed `deep-insights-v1.json` holds 895 / 446 / 41 / 25. Live pages: Read says "25 of the 895 paid pairs..."; no live page, rendered or source, shows 853, 423 or the old 35 or 23. Outline and remedies carry 895 and 446 and 41 where they mention them. But `docs/talk/07-remedies.md` lines 130 and 137 still say "423 of 853". |
| 8 | Jev rows on Explore | PASS on the safety property; the blocked-request outcome differs from the claim as written | Normal load: the nine native-prompts rows read "Jev 1.13, OpenRouter", a charge ($0.0059, $0.0064, $0.0069, the partial pass shows "plus up to $0.0013 unrecorded"), no dagger, no marker. With the findings request aborted, the nine rows are unchanged (still OpenRouter with the charge) because the catalog now carries route and charge, so the guard in `app.js` is a no-op by design. To exercise the guard I served an older catalog that files those runs under TypeSafe with no charge: feed available gives OpenRouter with charge; feed blocked gives "route unknown" and "Cost unknown" on all nine. Never "TypeSafe" with a figure in either case. |

### Claim 2 detail (1440 wide, all details open)

| Page | Bound elements | Numeric `data-source` | Text `data-text-source` | `data-derived` | Mismatches |
|---|---|---|---|---|---|
| index.html | 396 | 300 (299 exact or rounded, 1 shown as the word "no" for 0) | 5 of 5 | 91 | 0 |
| explore.html | 1,285 | 537 | 0 | 748 | 0 |
| method.html | 83 | 65 | 18 of 18 | 0 | 0 |

How derived values were checked: 734 Explore labels and 84 Read labels resolved from their formula paths (display label of a feed answer, ratio of a feed cost to Jev's cost, "not in disagreementCaseIds so Jev matched the reference"). The 14 "app.js merge" Sonnet cells (58, 57, 58, 58, 58, 56, 58, 58, 58, and 59, 59, 59, 60) equal `sonnet55-fresh-matched3.json` `threePassSummary` values. The prose formulas on Read evaluated by hand: 3.59 shown as 3.6, 37.69 as 37.7, gap 5, Jev pass $0.00589092 ("six tenths of a cent"), Opus $0.222052 ("22 cents"), 6 misses minus 3 disputed minus DEV-029 equals 2, intersection with the 4-plus-mismatch set equals 5. Formatting accepted as a match: percent to one decimal, two-decimal gauges, number words, "8 October 2026", the dagger suffix, four-decimal money.

### Claim 5 counts (rendered text, details open; same at 1440 and 390)

| Term | index | explore | method |
|---|---|---|---|
| Hover | 0 | 0 | 0 |
| provisional | 0 | 0 | 0 |
| Sources | 0 | 0 | 1 |
| Computed by | 0 | 0 | 0 |
| SOLID | 0 | 0 | 0 |
| DESCRIPTIVE | 0 | 0 | 0 |
| estimate | 0 | 0 | 0 |
| same 60 | 1 | 0 | 0 |
| Implication | 0 | 0 | 0 |
| middle dot | 0 | 0 | 0 |

Case-insensitive, the only extra hits are "Sources" lowercase once on Explore and "descriptive" three times on Explore, still not the quoted uppercase labels. "Implication" renders 0 even though the `chapter-implication` class exists, so that label is not in the text.

## Findings

**BLOCKING (1)**

- **B1. Stale pair counts in the remedies doc.** `docs/talk/07-remedies.md:130` says "Compare 423 of 853 cross-model charged pairs" and `:137` says "423 of 853 charged pairs". Line 68 of the same file says "446 of 895 charged pairs", so the doc contradicts itself and the feed. Fix: 423 to 446 and 853 to 895 on both lines. Reachable by anyone rehearsing from the doc, and a speaker could say the old figure aloud.

**RESIDUAL (6)**

- **R1. Same stale figures elsewhere in docs/talk.** `01b-deep-analysis.md` lines 876, 878, 906, 943 ("35 of 853"), `13-deck-brief-review.md:341` ("853 costed pairs", "35 pairs"), `14-phrases.md:163` ("35 of 853"). The outline and remedies cite 01b section 11 as their source, so 01b should be updated with B1. `05r2-outline-review.md` and `09-site-verification.md` are dated review logs and can stay.
- **R2. Rounding differs between two code paths.** Calibration bins show 0.955 as "0.95" and 0.605 as "0.60" (binary rounding), while the cost table shows 1.19895 as "$1.1990" (half up). Each is within the displayed precision. One shared rounding helper would remove it.
- **R3. Forwarding aborts the old page's own requests.** An old `index.html#...` link loads the Read page, starts its scripts and fonts, then redirects, so each forwarded visit records about a dozen cancelled requests. Harmless to the visitor, no console error after the redirect.
- **R4. Leaving Explore mid-load logs "Failed to fetch".** Seen only when navigating away from a still-loading Explore on a loaded machine; not reproduced with a normal wait. Cosmetic.
- **R5. Direct TypeSafe repeat rows carry a dagger figure.** Jev 1.13 TypeSafe API variant rows show "$0.0064†" style API-rate estimates, while the one TypeSafe baseline row says "no bill plus up to $0.0021 unrecorded". The dagger discloses the basis, so this follows the one money rule, but a reader could take it as a charge.
- **R6. One unit test fails outside the primary checkout.** `test_subscription_price_estimates` resolves an absolute path into the primary checkout. Known and documented. I did not run it in the primary checkout, and a clean CI checkout was not tested here.

## Not verified

- A real CI run on ubuntu with Python 3.14 from a clean clone. The workflow was run locally in the lane instead.
- Real-GPU rendering. Chromium used software GL, which is the source of the only warnings.
- Ids inside any panel that appears only after a user interaction other than opening details.
