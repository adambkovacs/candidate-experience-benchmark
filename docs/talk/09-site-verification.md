# Site verification: Read, Explore and Method pages

Verifier: independent agent, no stake in the build. Target: `public-site/` at HEAD `4ca83853` (site commits `dab297bc` and `4bc7b14e`), branch `feat/talk-presentation-v2`. Run on 2026-10-08 against `python3 -m http.server` on a fresh port, Chromium via the Playwright install under `public-site/deck/verify/`. No site file was edited. My own scripts live in the session scratchpad, not in the repo.

## Verdict: APPROVE

No BLOCKING finding. Nothing was found that breaks a feature in normal use, loses data or exposes something. Seven RESIDUAL findings follow, two of which the lead should read before the talk: the console warning on the Read page without a GPU (R1) and the failing presentation test caused by the deck commit (R6).

| Claim | Result |
|---|---|
| 1. Three pages load clean, no horizontal scroll | PASS on the GPU path. The Read page logs a Chromium driver warning in default and `--disable-gpu` headless at 1440 (R1). |
| 2. 92 ids exist once, panels render | PASS |
| 3. Legacy-link shim forwards | PASS for 171 links, with 1 id missing at runtime (R2) |
| 4. Read-page numbers match feeds | PASS, 0 real mismatches |
| 5. Contradiction audit | PASS for the nine corrected facts. One internal inconsistency in a JSON string (R5). |
| 6. Voice gate | Read 100.0%, Method 100.0%. Explore 95.6% with Tier 1 hits (R4). |
| 7. Accessibility basics | PASS, with heading-order skips on two pages (R3) |
| 8. Tests | 10 failures over two invocations: 9 missing fixture, 1 caused by the deck commit (R6) |

## Findings

All RESIDUAL. A finding is BLOCKING only if reachable in normal use and it breaks a feature, loses data or exposes something.

**R1. Driver warning on the Read page without a GPU.** In default headless Chromium and with `--disable-gpu`, `index.html` at 1440 wide logs two console warnings, "GPU stall due to ReadPixels". The page is not at fault: `hero.js` calls no read-back, and the note comes from Chromium's software GL path. With the GPU path (`--use-angle=metal --enable-gpu`) all 6 loads are clean. At 390 wide the hero scene does not run and the page is clean. `site/README.md` already says this. The claim as worded ("zero warnings and errors in Chromium") is false in those two modes. Optional fix: skip WebGL when the renderer string names SwiftShader.

**R2. `#cohort-reviews-title` disappears at runtime.** `cohort-reviews.js` replaces the inner HTML of the `#cohort-reviews` section, so the h2 with this id is removed. `LINK-MAP.md` lists the anchor as working, and the section keeps `aria-labelledby="cohort-reviews-title"`, which now points at nothing. The link still lands on the section, so no one is stranded. `cohort-reviews.js` was not touched by the redesign (last change `0bf03b9f`), so the defect pre-dates it. It is the only dangling aria reference on any of the three pages after render.

**R3. Heading levels skip.** `explore.html` goes from an h2 to an h4 ("39 model setups compared"). `method.html` goes from the h1 straight to an h3 ("How the test was scored"). `index.html` is in order across 30 headings.

**R4. Voice gate fails on Explore.** The static text of `explore.html` has one em dash (the empty value of the Jev score tile, replaced by script) and curly quotes in the category and training-history copy: 3 opening, 3 closing and 1 apostrophe. Score 95.6% against 100.0% for Read and Method. This is analyst copy carried over from the old page. The Read and Method pages have no Tier 1 hit and no Title Case heading (the one near match, "Solar Decide + Perplexity Decider", is a pair of model names).

**R5. A JSON string defines the wrong "beating" rule.** `deep-insights-v1.json` field `agreement_rule.beat_definition` reads "0 accepted errors, at least as many accepted as Solar + Perplexity (53), and a lower two-run charge than $0.03749436". That rule gives 35 pairs, which is the sibling field `pairs_beating_solar_perplexity`. The page shows "23 of 853", which is the strict "accept more" rule in `pairs_more_and_cheaper`. I re-ran `docs/talk/scripts/s11_agreement_general.py` with a strict comparison and got 23 strictly more, 35 at least as many, 12 ties, 853 charged cross pairs. So the page is right and the page text matches. The string is not rendered anywhere, so no reader sees it. Fix the string or drop the field.

**R6. `test_presentation_ui.cjs` fails because the deck commit replaced `presentation.html`.** The test expects ten slide ids such as `opening` and `task`. Commit `4ca83853` (the deck work) rewrote `public-site/presentation.html`, and none of those ids remain. The file before that commit still had `id="opening"`. This is not a site-redesign regression, but the suite is red until the deck lane retires or updates the test. `presentation.html` also shows as modified in the working tree right now, so another agent is still editing it.

**R7. Count mismatch in the brief, not in the site.** The Read page has 85 `data-source` numbers and 5 `data-text-source` values, 90 in total over 72 distinct refs. The brief said 88. All 90 pass.

Note on FINDINGS.md: its table lists Opus 5.5 high at 59 as a single pass and does not mention the other two passes (58, 58). That is incomplete, not contradictory. It is out of scope for the contradiction list.

## 1. Console and horizontal scroll

Method: Playwright Chromium, each page loaded, waited 6 s, scrolled top to bottom, all `error` and `warning` console messages, page errors, failed requests and HTTP 4xx/5xx collected. Explore loaded with `?run=typesafe-jev113-v2&case=DEV-003`.

```
default            1440 index.html    2 x warning: GL Driver Message ... GPU stall due to ReadPixels
default            1440 explore.html  CLEAN        default 1440 method.html  CLEAN
default            390  index/explore/method  CLEAN
--disable-gpu      1440 index.html    2 x warning: GL Driver Message ... GPU stall due to ReadPixels
--disable-gpu      1440 explore.html  CLEAN        --disable-gpu 1440 method.html  CLEAN
--disable-gpu      390  index/explore/method  CLEAN
--use-angle=metal --enable-gpu  1440 and 390, all three pages  CLEAN
```

Horizontal scroll, measured after a 7 s wait, a full scroll through and a return to top. `scrollWidth` equals `innerWidth` on all 15 combinations (widths 320, 390, 700, 1180, 1440, three pages). I also looked for any element wider than the viewport that no ancestor clips: none at any width.

```
320 index.html {"sw":320,"iw":320,"unclippedOverflowers":[]}      (same for explore, method)
390 / 700 / 1180 / 1440 : sw == iw, unclippedOverflowers [] on all three pages
```

## 2. Panel ids and rendering

I derived the ids from `getElementById` and `querySelector` strings in every `public-site/*.js` (excluding `deck/` and `site/`). That gave 158 candidate strings. 97 are static ids in `explore.html`, 61 are ids built at run time, colour codes, or belong to the deck or meetup scripts. Result on `explore.html` after render:

```
static ids queried by scripts: 97, each present exactly once: 97
lane's PROTECTED list: 92 ids, unique 92, each exactly once: yes
ids in my set not in the lane list (5): explore, inspect-run-select, main, repeat-analysis, usage-run-select, each present once
run-time ids (agreement-pair, cohort-review-*, cross-*, repeat-*, sensitivity-*) all present once after render
duplicate ids on any of the three pages: none
```

Panels, `explore.html?run=typesafe-jev113-v2&case=DEV-003`, 1440 wide:

```
overview rows (#overview-rows .overview-row)   9
run detail descendants                         2695   text begins "jev-1.13.0 ... typesafe-jev113-v2 COMPLETE · 60 / 60 SAVED · 60 / 60 VALID ... ALL FOUR MATCH / 60  54"
run detail mentions DEV-003                    true
inspector select value                         typesafe-jev113-v2
cross-category tables                          11
agreement-policy tables                        1
repeat chart (#clef-repeat-chart *)            127
repeat results (#repeat-results *)             545
reference-sensitivity select                   1
cohort reviews (#cohort-reviews select / *)    3 / 1041
```

## 3. Legacy-link shim

Source of truth: every `index.html#id` row in `site/LINK-MAP.md` that maps to another page (161 rows), plus 10 extra links: three with `?run=`, `compareRun`, `case`, `cohort=general`, `category`, `experiment`, a URL-encoded hash (`#%69nspect`), an encoded hyphen (`#review%2Devidence`), `#method-title` and `#findings-title`. Each was opened at 1440x900, waited 4.5 s, then checked for: final page, target element exists, is rendered, sits at or below the header bottom, and is inside the viewport.

```
rows from LINK-MAP 161, extras 10, total 171, ok 167, not ok 4
```

The four exceptions, all explained:

| Link | Observed | Verdict |
|---|---|---|
| `index.html#top` | lands on `index.html`, target is the page wrapper at y=0 | not a defect, the target is the whole page |
| `index.html#cohort-reviews-title` | lands on `explore.html`, id missing at runtime | R2 |
| `index.html#evidence-note-empty` | lands on `explore.html`, element exists but is a hidden empty state | not a defect |
| `index.html?cohort=general` (no hash) | lands on `explore.html` at the top, `#report-lens` is 1659 px down | correct, my expectation wrongly assumed a hash |

All named links in the brief pass: `#inspect`, `#explore`, `#review-evidence`, `#agreement-policy`, `#method`, `#findings`, `#story`, `?run=typesafe-jev113-v2&compareRun=perplexity-decider-native-fresh1-p0#inspect`, `?cohort=general#report-lens`, and both encoded hashes.

## 4. Read-page numbers against feeds

I wrote a separate checker (`c4.py`, scratchpad) that parses `index.html`, reads each `data-source` and `data-text-source` attribute, resolves `feed.json#path` with its own path walker (dotted keys, `[0]`, `["key"]`, `[field=value]` filters, `.length`), and compares to the element text. It handles thousands separators, `$`, `%` of a fraction, sign prefixes, ISO dates shown as "8 October 2026", and null shown as "unavailable".

```
static HTML source:            90 bound elements, 90 checked, 0 mismatches
rendered, normal motion:       401 bound elements (includes deep-insights mounts), 401 checked, 3 flagged
rendered, reduced motion:      401 bound elements, 401 checked, 3 flagged
```

The 3 flagged rows are artifacts of my parser, checked by hand: "+0.90" against 0.9, "+0.44" against 0.44, and "$0.03749" against the string "0.03749436" rounded to five places. Real mismatches: none. The count-ups land on exact text in both motion modes.

## 5. Contradiction audit

Sources searched: rendered text of the three pages (details opened), the static text of `explore.html`, 240 narrative strings of `deep-insights-v1.json`, `deep-insights-section.html`, `deep-insights.js`, `README.md`, `docs/FINDINGS.md`. For each corrected fact I searched for the stale wording and for the correct wording.

| Corrected fact | Where it appears | Contradiction |
|---|---|---|
| Four of seven native decision models said "mixed" on DEV-029 | `index.html` corrections block: "SAID Five decision models ... CORRECTED 4 of 7" | none. "Five" appears only as the quoted old claim. |
| Five zero-error agreement pairs | `index.html`: "SAID Four of 21 ... CORRECTED 5 of 21"; the pairs feed has 5 pairs with 0 all-four errors | none. README says "0 to 4 retained disagreements" and "33 to 53 retained", both match the feed. |
| Clef's charge is a known provider charge | `index.html`: "Clef's $0.3113 included" in known charges; Explore: "Recorded development charges were $0.01542736 and $0.03184656" | none. No sentence calls a Clef charge an estimate. |
| Opus 5.5 high has three passes (59, 58, 58) | `index.html` finding 1 and the corrections block | none. `docs/FINDINGS.md` lists only the 59 pass, see note above R7. |
| Jev calibrated on average, descriptive-only, 0.96 on a wrong testimonial | `index.html` lines for ECE 0.011 over 720 answers and "still 0.96 confident on a wrong testimonial" | none. The old "not calibrated" appears only as the quoted SAID. |
| Seven-model study: $1.2013 known plus up to $0.13 unknown | `index.html` corrections | none. "Under $1.20" appears only as the quoted SAID. |
| Solar + Perplexity 53/0/7 | `index.html`: accepted 53, with error 0, deferred 7, deferred ids DEV-006 DEV-013 DEV-027 DEV-028 DEV-029 DEV-030 DEV-035 | none |
| 35 of 60 reach a person | `index.html` route table 7 + 24 + 4 = 35, and the "Reaches a person" row lists 35 ids | none |
| 23 of 853 strictly accept more at a lower charge | `index.html` "23 of 853" | page correct, JSON string disagrees: R5 |

Extra checks I ran on the Read page narrative: Jev's six misses (DEV-006, 013, 027, 029, 030, 059) against "Five of Jev's six misses are in this set" (hard six: 006, 013, 027, 029, 030, 056): five overlap, DEV-059 does not. Correct. The 16 error-retaining pairs equal 21 minus 5. Correct.

## 6. Voice gate

Command (one run per file): `bun run /Users/adamkovacs/.claude/skills/anti-slop/scripts/audit-slop.ts <file>`. Tag-stripped static HTML text, and rendered `main` text after scripts ran.

```
index.html   static   1757 words   Slop 0    NO-SLOP 100.0%
index.html   rendered 4741 words   Slop 0    NO-SLOP 100.0%
method.html  static    689 words   Slop 0    NO-SLOP 100.0%
method.html  rendered  635 words   Slop 0    NO-SLOP 100.0%
explore.html static   5159 words   Slop 45   NO-SLOP 95.6%
   [HARD BAN] emDash 1x, curlyQuoteOpen 3x, curlyQuoteClose 3x, curlyAposClose 1x
```

Emoji bullets: none on any page. Title Case headings: none beyond model names. Details in R4.

## 7. Accessibility

```
skip link        first Tab focus = "Skip to content" (on screen, 3 px outline). Enter moves to #main.
                 The next Tab lands on the first link inside main on all three pages.
images           index 3, explore 2, method 2: every one has alt. Unnamed svg: 0. Unnamed links or buttons: 0. Unlabelled inputs: 0.
headings         one h1 per page. index: 30 headings, no skips. explore: 86, one skip (h2 to h4). method: 5, one skip (h1 to h3).
focus visible    16 Tab stops per page through header, sub-nav, buttons, summaries: all have a 3 px solid outline, none without. Focus-visible matched on all.
JS disabled      index: 10,352 chars of text, 45 links, h1 intact, no zero-opacity blocks. explore: 21,140 chars, 141 links, 3 noscript notes naming the missing panels. method: 2,537 chars, 16 links.
reduced motion   0 running animations on all three pages, 0 canvas elements, scroll-behavior auto, 0 zero-opacity elements after scrolling.
                 Read page requests hero.js and hero-lattice.svg and does not load three.js.
```

## 8. Tests

Node v26.10.0. `node --test tests/` picks up only the 10 `*.test.cjs` files. The 67 `test_*.cjs` files need an explicit glob. I ran both.

```
node --test tests/               tests 65    pass 60    fail 5
node --test tests/test_*.cjs     tests 366   pass 361   fail 5
```

| Failing test | File | Cause |
|---|---|---|
| 5 tests (stopped attempts, manifest, injected timeout, changed suffix, eight completions) | `tests/e4b_p2_unsent_suffix_v1.test.cjs` | ENOENT opening `results/repeatability-v1/small-local-v1/gemma4-e4b-sdk-thinking-on/fresh2/P2/smoke.journal.jsonl`. The file is not tracked in git and not in the main checkout path either. |
| 4 tests (stopped prefix, versioned schedule, absent suffix, offline injected failure) | `tests/test_small_local_e4b_on_interruption_continuation_v1.cjs` | Same ENOENT, same missing file |
| `markup has source fallbacks and scoped mobile, motion and print styles` | `tests/test_presentation_ui.cjs:175` | `presentation.html` no longer has the slide ids (R6) |

That is 10 failures across the two invocations: 9 from the one missing fixture and 1 from the deck page. The lane reported 5. No failure touches the three site pages. The site-facing tests that passed include report navigation, cross-category, cohort reviews, agreement policy, reference sensitivity, disputed reviews, findings, extended cases and the outcome chart.

## What I could not verify

- WebKit and Firefox, and real mobile hardware. Only Chromium was run.
- The Python tests under `tests/test_*.py`. They were out of scope for the brief.
- Whether the 9 missing-fixture failures pass in the checkout that holds `smoke.journal.jsonl`. I found the file in neither place.
- Rendered Explore text against the voice gate. The scores above use its static text only, because the rendered text is 775,000 characters of generated data.
