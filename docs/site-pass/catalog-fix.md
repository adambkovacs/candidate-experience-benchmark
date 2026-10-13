# Catalog fix: Jev native-prompt route and charge (codex finding S1)

Date: 2026-10-13. Branch `feat/site-content-v2`, head 11788f7d plus uncommitted lane edits. Nothing committed.

## Outcome

The nine Jev 1.13 native-prompt passes in `public-site/extended-run-catalog-v1.json` now carry the route they actually ran on, OpenRouter native Choice, and the known OpenRouter charge in place of an estimate. The six `typesafe-jev113-v2` repeat2/repeat3 rows did run on the direct TypeSafe API, have no recorded charge, and stay as estimates. No other catalog row changed: a row-by-row diff of the old and new catalog shows exactly nine changed rows out of 637.

## Evidence: which rows ran on OpenRouter

Each Jev prompt pass has its own run directory with `attempts.jsonl` (saved raw OpenRouter responses) and `budget-reconciliation.json` (the closed budget partition). In every saved response body, OpenRouter names the upstream provider `TypeSafe` and the model `typesafe/jev-1.13-20260917`, and reports a per-request `usage.cost`. The sum of `usage.cost`, the sum of `actual_cost_usd` in the attempts, the partition's `known_actual_usd`, and the findings feed's `knownCostUsd` agree to the last digit for all nine passes.

| Prompt | Pass | Run directory | Responses | Known charge USD | Unknown bound USD |
|---|---|---|---:|---:|---:|
| P0 | fresh1 | `results/route-audits/jev-authority-v2-20261006/jev-openrouter-native-p0-choice-v1/fresh1` | 60 | 0.005890920 | 0 |
| P0 | fresh2 | same parent, `fresh2` | 60 | 0.005890920 | 0 |
| P0 | fresh3 | same parent, `fresh3` | 60 | 0.005890920 | 0 |
| P1 | fresh1 | `results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p1-choice-v1/fresh1` | 60 | 0.006405000 | 0 |
| P1 | fresh2 | same parent, `fresh2` | 60 | 0.006405000 | 0 |
| P1 | fresh3 | `results/route-audits/jev-authority-v2-20261006/jev-openrouter-native-p1-choice-v1/fresh3` | 60 | 0.006405000 | 0 |
| P2 | fresh1 | `results/route-audits/jev-native-full-v1-20261006/jev-openrouter-native-p2-choice-v1/fresh1` | 60 | 0.006851040 | 0 |
| P2 | fresh2 | same parent, `fresh2` (stopped: 17 parsed, one HTTP 429 with no recorded charge, 42 never sent) | 17 | 0.001940694 | 0.001344000 |
| P2 | fresh3 | `results/route-audits/jev-authority-v2-20261006/jev-openrouter-native-p2-choice-v1/fresh3` | 60 | 0.006851040 | 0 |

The endpoint catalog saved with each run (`endpoint-catalog.json`) is OpenRouter's endpoint list for `typesafe/jev-1.13`, provider `TypeSafe`, prompt price $0.000000042 per token. P0 scores stay 54, 53 and 52 all-four matches across the three passes.

`docs/talk/06-cost-check.md` confirms the three P0 passes against OpenRouter's generation API. Its unresolved item 5 says the P1 and P2 fresh1 and fresh2 attempt files were "not at the expected path". They are under `results/route-audits/jev-native-full-v1-20261006`, and their in-response `usage.cost` sums match the feed. This fix did not re-query the generation API for those four passes. The basis for them is the provider-reported `usage.cost` in the saved responses plus the closed budget partition, which is the same basis the project ledger uses for every other known OpenRouter charge.

## Evidence: the v2 repeats ran direct

`results/repeatability-v1/typesafe-jev113-v2/frozen-plan.json` names the endpoint `https://api.typesafe.ai/v1/systemone`. The saved raw responses under `repeat2/` and `repeat3/` carry only `model`, `answers` and `usage` token counts, with no charge field. Every attempt row records `actual_charge_usd: null` and `cost_basis: "Estimated from reported input tokens; provider invoice unavailable."`. Section 3 of the cost check says TypeSafe has no usage or billing API. Those six rows keep surface `TypeSafe native Choice API` and their estimate, and the new test pins that.

## What changed

**Builder, `scripts/build_extended_run_catalog_v1.py`.**

- The surface function at line 192 now returns `OpenRouter native Choice` for the `jev-native-prompt-findings` family. The old code keyed the TypeSafe API label on the provider name, which both Jev families share, so the OpenRouter passes inherited the direct-API label.
- The Jev block at line 371 maps the feed's `knownCostUsd` to a known charge. It used to map it to `cliListPriceEstimateUsd`, which demoted it to an estimate. The rows also get a cost note stating the basis.

Provider stays `TypeSafe`. That is the upstream provider OpenRouter reports, and it matches how `supplemental-decision-runs-v1.json` records the other OpenRouter native Choice runs, for example Solar as `Upstage` and Clef as `Cloudflare`. Row IDs and the model string `jev-1.13.0` are unchanged because several pages key on those IDs.

**Changed records, all in `public-site/extended-run-catalog-v1.json`.** For each of the nine rows `extended-typesafe-jev113-native-prompts-{fresh1,fresh2,fresh3}-{p0,p1,p2}`:

- `surface` changed from `TypeSafe native Choice API` to `OpenRouter native Choice`.
- `cost.knownUsd` changed from null to the charge in the table above.
- `cost.estimatedUsd` changed from that same figure to null.
- `cost.note` now states the known-charge basis. `cost.unknownUpperBoundUsd` was already right and is unchanged.

Catalog sha256 went from `9ff0cf652d8504fc978fe69c193c70b0be822a3f2d4aef16be552d197e045412` to `685ebd0fa946dab9b0005180a22a61fa119804eca0c7992296909c194f132fe9`.

**Test, `tests/test_extended_run_catalog_v1.py`.** The existing pricing-basis test asserted the defect, with known null and estimate $0.00589092. It now asserts the known charge and a null estimate. The new test `test_jev_prompt_passes_are_openrouter_known_charges` pins all nine rows' surface, provider, known charge and unknown bound to the values in the run directories above, independent of the findings feed. It also pins the P0 scores 54, 53 and 52 and checks that the six direct v2 repeat rows stay estimates on the TypeSafe API surface.

## Test results

| Command | Result |
|---|---|
| `python3 scripts/build_extended_run_catalog_v1.py check` | pass, 637 stages |
| `python3 -m unittest tests.test_extended_run_catalog_v1 -q` | 9 tests OK |
| `node --test tests/test_extended_run_catalog_ui.cjs` | 4 of 4 pass, no wording failures |
| Other node tests that read the catalog or Jev rows (additional cases, cohort reviews, extended cases, model categories, pairing, repeat, specialist) | 48 of 48 pass |
| `python3 -m unittest tests.test_extended_cases_v1` | 4 tests OK |
| `python3 -m unittest tests.test_public_explorer` | 9 errors, unrelated and pre-existing: a hash mismatch on `results/prompt-comparison-v1-2026-09-24/paired-reports/fable51-high-phase2-batch10-p0/evaluation.json`. It fails the same way with the old catalog restored. |

## Follow-ups outside this lane's files

**Downstream feeds now need a rebuild.** Three feeds record the catalog's hash. Each one passed its `--check` against the old catalog and fails it now. Rebuild them in this order, because each check reads the previous output:

```
python3 scripts/build_extended_cases_v1.py
python3 scripts/analyze_cross_category_v1.py
python3 scripts/build_deep_insights_v1.py
```

- An in-memory rebuild of `public-site/extended-cases-v1.json` changes the catalog hash and the nine Jev `surface` strings, and nothing else.
- `public-site/cross-category-v1.json` and its `results/` outputs contain no Jev rows, so only the hash chain moves.
- `public-site/deep-insights-v1.json` only re-hashes.
- `public-site/presentation-offline.html` embeds the catalog and the extended-cases feed inline. It needs a re-bake with `public-site/deck/verify/bake-offline.mjs` after the rebuilds.

**Client-side workarounds are now redundant.** `public-site/app.js` (`applyJevFindings`) and `public-site/site/benchmarks.js` (around line 81) patch these rows in the browser because of this defect. Both are idempotent with the fixed catalog, so nothing breaks. The app.js patch also overwrites `provider` with `OpenRouter`, which differs from the catalog's `TypeSafe`. The UI lane owns the call on deleting both patches.

**Cost-check item 5 can close.** `docs/talk/06-cost-check.md` item 5 can point at `results/route-audits/jev-native-full-v1-20261006` for the P1 and P2 fresh1 and fresh2 passes.

## Downstream chain, second pass (stopped at deep insights)

The lead extended scope to the downstream chain. Each feed was rebuilt only after an in-memory diff showed that it changed nothing but hashes and the nine Jev rows' route. The chain stopped at deep insights, which would change real figures.

| Step | Changes beyond hashes | Write | `--check` |
|---|---|---|---|
| `scripts/build_extended_cases_v1.py` | the nine Jev `surface` strings | done | exit 0 |
| `scripts/analyze_cross_category_v1.py` (`public-site/cross-category-v1.json`, `results/cross-category-v1/{dataset,plan}.json`) | none, `findings.md` unchanged | done | exit 0 |
| `scripts/analyze_reference_sensitivity_v1.py` (`public-site/reference-sensitivity-v1.json`, `results/reference-sensitivity-v1/findings.json`) | the nine Jev `surface` strings, README unchanged | done | exit 0 |
| `scripts/build_deep_insights_v1.py` | real figures, listed below | **held** | exit 1 (stale) |
| `public-site/deck/verify/bake-offline.mjs` | not run, waits on deep insights | held | n/a |

Reference sensitivity was not on the lead's list. It reads `extended-cases-v1.json`, pages.yml checks it, and it went stale with the extended-cases rebuild, so it was rebuilt under the same diff rule.

### Why deep insights was held

Rebuilding `public-site/deep-insights-v1.json` changes 32 values. Two causes:

**1. The agreement rule now counts Jev P0 fresh1 as a charged run.** This corrects the earlier output, which left Jev out because the catalog filed its charge as an estimate.

| Field under `agreement_rule` | Before | After |
|---|---|---|
| `budget_answers[0]` "Cheapest pair with 0 accepted errors and at least 50 accepted" | DeepSeek V4.1 Flash off + DeepSeek V4.1 Flash low, 54 accepted, 6 deferred, $0.01781653 | DeepSeek V4.1 Flash off + Jev 1.13 fresh1 P0, 51 accepted, 9 deferred, $0.00857206 |
| `explorer_pairs[13]` | same pair as above | same new pair as above |
| `charged_runs` (decision) | 42 (8) | 43 (9) |
| `charged_cross_pairs` | 853 | 895 |
| `charged_zero_error_pairs` | 423 | 446 |
| `pairs_beating_solar_perplexity` | 35 | 41 |
| `pairs_more_and_cheaper` | 23 | 25 |

`best_beating`, `solar_perplexity`, `native_routing` and the other three budget answers do not change.

**2. The cost frontier gains the stopped Jev P2 fresh2 pass.** It would become the cheapest frontier point: 17 valid answers, 15 all-four matches, $0.001940694, with 42 reviews never sent. `docs/talk/scripts/s10_cost.py` (function `cost`, line 18) already forced the eight complete Jev passes to known as a workaround for this defect. It skipped this pass on purpose because its status is not `complete`, so the pass fell through to the catalog estimate and sat in the estimate table. Now that the catalog records it as known, the shared helper `run_cost` in `docs/talk/scripts/common.py` puts it in the known-charge table. The `frontier()` function has no completeness filter, so a partial pass heads a table whose column is "usd per 60-review pass". `cost_frontier.run_passes` also moves from 262 estimate and 303 known to 261 and 304. The gate and key numbers do not change.

Cause 2 looks unintended. The smallest fix is in `s10_cost.py`: return a non-frontier kind for Jev native-prompt passes whose status is not `complete`, instead of falling through to the catalog value. Whether that kind is estimate or unknown changes `run_passes` differently, so it is the owner's call. The Jev override itself is now redundant.

**Who reads the changed paths.** The deck binds none of them. `node public-site/deck/verify/numbers.mjs --page presentation.html` passes against the current files: 436 live and 450 print numbers bound. The Explore page renders `agreement_rule.explorer_pairs` through `public-site/deep-insights.js`, so the new pair would appear there.

### pages.yml Python checks at the stop point

pages.yml has no deep-insights check. The Python lines in its static-bundle block that touch this chain, run at the stop point:

```
exit=0 :: python3 scripts/build_extended_run_catalog_v1.py check
exit=0 :: python3 scripts/build_extended_cases_v1.py --check
exit=0 :: python3 scripts/build_additional_cases_v1.py --check
exit=0 :: python3 -m unittest tests.test_additional_cases_v1 -q
exit=0 :: python3 scripts/analyze_native_agreement_policy_v1.py --check
exit=0 :: python3 -m unittest tests.test_extended_cases_v1 tests.test_analyze_native_agreement_policy_v1 -q
exit=0 :: python3 scripts/analyze_cross_category_v1.py --check
exit=0 :: python3 -m unittest tests.test_cross_category_v1 -q
exit=0 :: python3 scripts/analyze_reference_sensitivity_v1.py --check
exit=0 :: python3 -m unittest tests.test_reference_sensitivity_v1 -q
exit=0 :: python3 -m unittest tests.test_disputed_reviews_v1 tests.test_extended_run_catalog_v1 -q
exit=1 :: python3 scripts/build_deep_insights_v1.py --check   (not in pages.yml; held)
```

These node tests also pass: reference sensitivity, extended cases, agreement policy, cross-category, cohort reviews and extended run catalog, 47 of 47.

## Third pass: ruling (a) applied, chain finished

The lead ruled that the agreement-rule change is a correction, to be accepted. The frontier gets a completeness filter in `frontier()`, which is not specific to Jev, and the Jev workaround in s10 goes.

**`docs/talk/scripts/s10_cost.py`**
- `frontier()` keeps only passes with 60 valid answers.
- Both Jev overrides in `cost()` are removed, along with the `JEV` feed load they used. The first forced the eight complete passes to known. The second was a fallback for a Jev row with no catalog cost, which no row hits now that the catalog carries the charge.
- The stopped P2 fresh2 pass stays classed as known. `run_passes` is 304 known, 261 estimate and 439 unknown.
- The `__main__` self-check now also asserts that every frontier point has 60 valid answers and that the stopped Jev pass is still known.

**`tests/test_deep_insights_v1.py`** pinned the superseded agreement counts. They are updated to the accepted values: 41 pairs beating Solar plus Perplexity, 895 cross pairs, 25 more-and-cheaper. Two new assertions pin the frontier's completeness and the 304 known run passes. No dedicated s10 unit test exists. Its self-check is the script's `__main__` block.

### Final deep-insights-v1.json diff

38 source hashes now, down from 39. `jev-native-prompt-findings.json` left the source list because no section reads it any more.

| Field | Old | New |
|---|---|---|
| `agreement_rule.budget_answers[0]` (cheapest pair, 0 errors, 50 or more accepted): run_b | DeepSeek V4.1 Flash low effort original | Jev 1.13 fresh1 P0 (decision model) |
| same: accepted / deferred | 54 / 6 | 51 / 9 |
| same: two-run charge | $0.01781653 | $0.00857206 |
| `agreement_rule.explorer_pairs[13]` | same pair and values as the old budget answer | same pair and values as the new budget answer |
| `agreement_rule.charged_runs` | 42 | 43 |
| `agreement_rule.charged_runs_by_category.decision` | 8 | 9 |
| `agreement_rule.charged_cross_pairs` | 853 | 895 |
| `agreement_rule.charged_zero_error_pairs` | 423 | 446 |
| `agreement_rule.pairs_beating_solar_perplexity` | 35 | 41 |
| `agreement_rule.pairs_more_and_cheaper` | 23 | 25 |
| `cost_frontier.frontier[4]` (the 57 all-four point) | `openrouter-paid-deepseek-v41-flash-low--p1`, original pass, 58 valid, observed, $0.00981391 | `extended-openrouter-paid-deepseek-v41-flash-low-fresh1-p1`, fresh1, 60 valid, known, $0.01165805 |
| `cost_frontier.frontier_points` | 7 | 7 |
| `cost_frontier.run_passes.observed_or_known` | 303 | 304 |
| `cost_frontier.run_passes.estimate` | 262 | 261 |

Unchanged:
- `best_beating`
- `solar_perplexity`, at 53 accepted, 0 errors, $0.03749436
- the other three budget answers
- `native_routing` and `full_policy_routing`
- the gate, with $0.00268114 at 54 all-four
- every key-number path

The completeness filter removed one point besides the stopped Jev pass: the 58-valid DeepSeek V4.1 Flash low P1 pass. All six new beating pairs include Jev P0 fresh1. Two of them accept 54, which accounts for the rise in more-and-cheaper. Four accept 53. Of the 41 beating pairs, 13 include a decision model. Seven of those are Solar or Perplexity pairs that were already in the old 35.

### Prose that quotes the old numbers (for the page lane)

- `public-site/presentation.html:427`, a speaker note: "Across 853 costed pairs". Now 895.
- `docs/talk/05-session-outline.md`, lines 108, 172 and 247: "853 costed pairs", "35 pa…", "853-pair analysis".
- `docs/talk/07-remedies.md:68`: "423 of 853 charged pairs". Now 446 of 895.
- `docs/talk/07-remedies.md:203`: plans to "pair Jev … with the 853 charged general runs". Jev P0 fresh1 is now in that charged pool.
- Historical review records that quote 35, 23 or 853: `docs/talk/05r2-outline-review.md:96` and `docs/site-pass/cold-read-2.md:140`.

### Final checks

| Command | Exit |
|---|---|
| `python3 scripts/build_deep_insights_v1.py --check` | 0, 38 source hashes |
| `python3 -I docs/talk/scripts/s10_cost.py`, with the self-check | 0 |
| `python3 -m unittest tests.test_deep_insights_v1 -q` | 0, 7 tests |
| `node public-site/deck/verify/bake-offline.mjs` | 0, 20 feeds inlined |
| `node public-site/deck/verify/numbers.mjs --page presentation.html` | 0, PASS: 436 live and 450 print numbers bound |
| `node public-site/deck/verify/offline-check.mjs` | 0, PASS: 31 slides, 0 unbound, 0 console errors |
| All 11 pages.yml Python lines listed in the second pass | 0 |

The bake changed only the four embedded feeds that were rebuilt: the catalog, extended cases, cross-category and deep insights. Each one equals its file on disk, and `presentation-offline.html` is byte-identical to HEAD outside those feed blocks.

**Independent verification.** A separate Sonnet verifier, working read-only, re-ran HEAD's and the current `cost()` over all 1004 runs against today's data. The (kind, usd) results are identical for every run, so removing the Jev overrides changed no cost. The stopped Jev P2 pass became known through the catalog fix, not through the s10 edit. The verifier also re-derived the frontier with and without the filter and diffed deep insights and the offline deck against HEAD. It confirmed the table above and found no other changed paths and no blocking findings.
