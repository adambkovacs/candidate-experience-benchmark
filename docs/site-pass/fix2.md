# Fix round 2 on the public site

Started 11:55 CEST, hard stop 13:25 CEST, report written 12:58. Worktree `/Users/adamkovacs/lanes/cxb-talk`, branch `feat/site-content-v2` on top of 11788f7d. Nothing committed.

**Commit note for the lead.** `public-site/site/labels.js` is a new, untracked file that every page now loads before its panel scripts. Add it to the commit. Someone has already staged everything under `public-site/`. That includes five JSON feeds and the two presentation pages, which neither I nor my helpers touched: `cross-category-v1.json`, `deep-insights-v1.json`, `extended-cases-v1.json`, `extended-run-catalog-v1.json`, `reference-sensitivity-v1.json`, `presentation.html` and `presentation-offline.html`. They look like another lane's work ("catalog-fix" showed up in my agent inbox).

## What I found on Clef cost (ruling 1)

There is no data error. Both Clef figures are the same amount because both routes sent the same 132,694 input tokens, and Cloudflare charges $0.24 per million input tokens for Clef and $0.09 for Clef Flash.

| Route | Model | All four, of 60 | Cost of the pass | What the cost is |
|---|---|---|---|---|
| OpenRouter, first P0 pass | Clef | 54 | $0.0318 | Charge reported by OpenRouter, exact |
| OpenRouter, first P0 pass | Clef Flash | 45 | $0.0119 | Charge reported by OpenRouter, exact |
| Cloudflare direct (Workers AI), first pass | Clef | 53 | $0.0318† | No bill on this route; published price × the same tokens |
| Cloudflare direct (Workers AI), first pass | Clef Flash | 45 | $0.0119† | No bill on this route; published price × the same tokens |

The nine-pass OpenRouter series cost $0.3113 for Clef and $0.1165 for Clef Flash. Those totals average out to more than $0.0318 a pass because P1 and P2 send longer prompts ($0.0347 and $0.0372 per pass for Clef). So the cold reader's "about $0.0346 a pass" is the average across all three prompts, and it doesn't contradict the P0 figure.

Feeds checked:
- `public-site/supplemental-decision-runs-v1.json`: `runs[id=clef-openrouter-native-fresh{1,2,3}-p{0,1,2}].cost.knownUsd` and the matching `clef-flash-openrouter-…` rows. P0 is 0.03184656 with all four at 54, and Clef Flash P0 is 0.01194246 at 45.
- `public-site/clef-findings.json`: `models.clef.publishedInputPriceEstimateUsd` 0.03184656, `providerBilledUsd` null and `allFourCorrect` 53. Clef Flash reads 0.01194246, null and 45. This is the direct route.
- `public-site/clef-p0-repeat-findings.json` and `clef-p0-third-checkpoint.json`: route `@cf/cloudflare/clef`, same price figure, no provider bill.
- `docs/talk/06-cost-check.md`, lines 8, 26, 30, 31, 46, 47 and 126: OpenRouter's generation records report exactly $0.03184656 and $0.01194246, which makes them known charges. The direct runs are a rate-based upper bound, not a charge.
- `analysis-refresh.json` and `extended-run-catalog-v1.json`: Clef appears there only through the catalog's direct-route rows, and none of those figures conflict.

Where the route is now stated once:
- **Read leaderboard:** Clef costs $0.0318 and Clef Flash $0.0119. The column is the cost of one pass, and the leaderboard has no † on these rows.
- **Explore `#cost-ledger`:** the same values, with one footnote: "Every pass here ran through OpenRouter except Opus".
- **Explore `#results`:** the readable label is "Clef, OpenRouter".
- **Explore `#run-ranking`:** readable label and four-decimal cost.
- **Explore `#clef-first-pass`:** the cards show $0.0318† and $0.0119†, followed by one sentence: "Both ran one plain-prompt pass on Cloudflare's direct route, which sends no bill, so these costs are the published price for the same 132,694 input tokens. OpenRouter charged exactly that for the passes in the results table, where Clef matched 54."

## DONE / NOT DONE against the rulings

| Ruling | Status | What changed |
|---|---|---|
| 1. Clef and Clef Flash cost | DONE | See above. Jev is also fixed: "no bill" on the TypeSafe row, and $0.0059 through OpenRouter everywhere. |
| 2. One money rule | DONE | Four-decimal dollars everywhere through `BM_LABEL.usd`, one † with its note once per page, and thousands separators. Headers read "1,004 saved passes". The 929 count is gone and the 381 count is now a plain plotted count. Method `#study-cost` says $12.65 is the whole study and the seven-model series ($1.2013) is part of it. The 979 and 242 counts survive as filter counts inside the closed Earlier analyses ("Showing 979 runs.", "8 of 242 complete P0 setups shown"). |
| 3. Explore restructure | DONE | The ten kept blocks come first, in the ruled order, then Downloads. The fourteen others sit in one closed `<details id="earlier-analyses">` with the requested intro sentence. Every id is kept, LINK-MAP.md is updated, and a link into the closed block opens it. The footer hedge is deleted. Names read "Opus 5.5, high effort, Claude subscription" with the slug in mono on a second line. Pickers use commas. `#outcome-chart` is rebuilt (details below). `#reference-sensitivity` defaults to Jev at 54; Solar Decide is not in that panel's run list. |
| 4. Read | DONE, except one column | `#team` is headed "What should you do", in second person, numbered once. `#deep-insights` is four findings in sentences. Items 1 to 22 are done. The leaderboard has DeepSeek V4.1 Flash (54 for $0.0027) and Gemini 3.1 Pro, three P0 passes for Gemma (59, 59, 56) and a line that says Qwen low ran once. The hero has a sentence on the cheapest strong result. `#hard-reviews` gained Opus 5.5 and Gemma 4 26B columns. **NOT DONE: a Sonnet 5.5 column.** Its per-review answers exist only as raw provider logs, not in any feed. The thinking headline is gone along with the collapsed block. |
| 5. Method | DONE | A roster table of 31 rows, a one-row class balance, P0, P1 and P2 prompt links (P0 is `docs/LABELING_GUIDE.md` up to "Simulated routing", hash-checked against the manifest), and "classification-bench is not public yet. Ask Adam for access." Items 53 to 56 are trimmed. |
| 6. Tests | DONE | Regexes were updated with their intent kept. Details under Verification. |
| 7. Verify | DONE | Output and captures below. An independent verifier (separate agent, adversarial brief) checked eight claims on the final tree at 13:00 and all eight HOLD: ids kept on all three pages (169, 26 and 21, none lost); block order and the closed Earlier analyses, which opens for `explore.html#run-ranking`; zero errors, failed requests and overflow at both widths; word counts; the Clef figures in the feeds and on both pages; the leaderboard rows and sort; the hard-review columns fitting at 1440; tests 264 of 264. It resolved 790 of the 837 `data-source` numbers on Read and Explore against their feeds and found no mismatch beyond the declared four-decimal rounding. 47 paths with quoted keys were not resolved. It flagged one thing for a skim reader: Clef shows 54 on Read and 53 in `#clef-first-pass`, which the page explains as two routes. site-verify and the codex gate ran on 11788f7d, not this tree. |

### Cold-read-2 item numbers

| Items | Status |
|---|---|
| Read 1 to 22 | DONE. Item 20 keeps "Every number on this site describes these 60 reviews." once, in Read's About block, as the charter allows. |
| Explore 23 to 41 | DONE |
| Explore 42 to 46 (library, inside Earlier analyses) | DONE for JS-rendered text. PARTLY for the static library notes: "historical-first" still appears once in a run-detail stratum label. |
| Explore 47 to 52 | DONE. `#source-links` now renders nothing. |
| Method 53 to 56 | DONE. Method's corrections log still says "235 of 373 strong run-passes", verbatim from the corrections feed. |
| Contradictions 1 to 4 | DONE |
| Section 4, wants 1 and 3 to 9 | DONE, except Sonnet 5.5 in want 4 |
| Section 4, want 2 | DONE on Explore. NOT DONE: the small copy under the Read leaderboard. |
| Section 5, defects 1 to 8 and 11 | DONE. Explore ships at 38,818 px, down from 57,541. |
| Section 5, defects 9 and 10 | NOT DONE. The theme split and the hero lattice jitter were not in the rulings. |

### `#outcome-chart`, rebuilt
- **Axes:** cost of one pass on a log x axis from $0.001 to $10, against all four matched out of 60.
- **Points:** round points on a fixed pixel grid, so none overlap or leave the plot. The inline legend uses blue for decision models and orange for general models.
- **Default:** Solar Decide, OpenRouter, 55 of 60, $0.0221.
- **Count line:** "205 passes plotted. 176 more have no recorded cost, 107 of them local runs, and are not plotted." The 162 Codex subscription passes carry no cost in the feeds.

## Verification output

All Node and Python output below was run at 12:53 or later on the final tree, except `test_reader_story` and `test_deep_insights_v1` runs noted.

```
node --check: all 21 touched modules OK (site/labels.js, site/benchmarks.js, app.js, extended-cases.js, report-navigation.js,
  outcome-chart.js, deep-insights.js, analysis-refresh.js, reference-sensitivity.js, cross-category.js, cohort-reviews.js,
  agreement-policy.js, disputed-reviews.js, clef-repeat-chart.js, repeats.js, findings.js, reader.js, jev-prompts.js, kev-prompts.js)
node --test, the 45 test files in .github/workflows/pages.yml's check block: tests 236, pass 236, fail 0
node --test tests/test_*_ui.cjs (all 54 UI test files): tests 264, pass 264, fail 0
python3 scripts/build_reader_story.py --check: exit 0
python3 -m unittest tests.test_reader_story -q: OK
python3 -m unittest tests.test_deep_insights_v1 -q: OK
```

Browser: public-site served with `serve()` from `deck/verify/lib.mjs`, headless Chromium, every `<details>` opened, scripts settled.

| Page at width | Console errors | Failed requests | scrollWidth / innerWidth | Hover | provisional | Sources | Computed by | SOLID | DESCRIPTIVE | estimate | same 60 | Implication | · |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Read 1440 | 0 | 0 | 1440 / 1440 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| Read 390 | 0 | 0 | 390 / 390 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| Explore 1440 | 0 | 0 | 1440 / 1440 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Explore 390 | 0 | 0 | 390 / 390 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Method 1440 | 0 | 0 | 1440 / 1440 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Method 390 | 0 | 0 | 390 / 390 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

- **Read, "same 60":** it is the setup phrase in the hero lede.
- **Method, "Sources":** it is the downloads heading.
- **Money:** no dollar figure with more than four decimals renders on any page.
- **Hard-review table:** 1,240 px wide inside a 1,240 px box at 1440. At 390 it scrolls inside its own wrapper.

**Test changes (mine):**
- `test_report_navigation_ui.cjs`: the count pins now read "Showing N runs". The markup test now checks the new block order, that one closed Earlier analyses block exists, and the quick-link anchors.
- `test_jev_prompt_ui.cjs`, `test_kev_prompt_ui.cjs`: the script version pins move to `20261013-fix2`.
- `test_clef_public_ui.cjs`: pins the new Clef intro sentence.
- `test_public_specialist_ui.cjs`: pins "One row per setup, best pass first." in place of the cut caution line.

The helpers' test changes are listed in their own reports. All of them keep the score, id and charge checks.

## Screenshots (docs/site-pass/fix2/)

- **Folds:** `index-1440-fold.png`, `index-390-fold.png`, `explore-1440-fold.png`, `explore-390-fold.png`, `method-1440-fold.png`, `method-390-fold.png`
- **Rebuilt outcome chart:** `explore-outcome-chart-1440.png`, `outcome-chart-1440.png`, `outcome-chart-390.png`, `outcome-chart-1440-all.png`
- **Panels:** `read-leaderboard-1440.png`, `read-hard-reviews-1440.png`, `read-deep-insights-1440.png`, `read-team-1440.png`, `explore-results-1440.png`, `explore-cost-ledger-1440.png`, `method-roster-1440.png`, `method-study-cost-1440.png`
- **Raw probe output:** `verify-all.json`

Section captures taken with `elementHandle.screenshot` show the sticky header painted mid-image. That comes from the capture method, not the page.

## Who changed what

- **Me:**
  - `site/labels.js` (new): readable names and the money and count rules.
  - `site/benchmarks.js`: leaderboards, the Sonnet 5.5 fill, hard-review columns, cost ledger, header alignment, and the details opener.
  - `site/benchmarks.css`, `site/read.css`, `index.html`, `explore.html`, `site/LINK-MAP.md`, `report-navigation.js`.
  - Two small fixes in `app.js` and `extended-cases.js`, and the five tests named above.
- **Helpers I ran, one file set each:**
  - Outcome chart: `outcome-chart.js`, `outcome-chart.css` and their test.
  - Method: `method.html`.
  - Read findings: `deep-insights.js` and `deep-insights.css`.
  - Explore copy, part one: `app.js`, `repeats.js`, `extended-cases.js`, `findings.js`, `reader.js`, `jev-prompts.js`, `kev-prompts.js` and their tests.
  - Explore copy, part two: `analysis-refresh.js`, `reference-sensitivity.js`, `cross-category.js`, `cohort-reviews.js`, `agreement-policy.js`, `disputed-reviews.js`, `clef-repeat-chart.js` and their tests.
