# Independent site verification

Verifier: independent, no stake in the build. Read-only on product files. Nothing committed.

**Tree tested.** `b9287eb5` plus the dagger fix. The worktree had uncommitted edits to `public-site/app.js` and `tests/test_subscription_price_ui.cjs` when I started. Another lane committed them as `11788f7d` at 11:42 while I worked. `app.js` was last written at 11:38. I re-ran claims 1, 2, 3, 4 and 6 on the final tree, and claim 5 ran on it too. The "HEAD b9287eb5" label printed by the claim 3 script is hard-coded and wrong. The tree is `11788f7d`.

**Verdict: APPROVE.** No BLOCKING findings. Five RESIDUAL findings.

## Claims

| # | Claim | Result |
|---|---|---|
| 1 | Every data-source or data-derived number matches its feed | PASS |
| 2 | Every id in LINK-MAP.md exists exactly once, and the shim forwards every old link | PASS |
| 3 | Both viewports, zero console errors, zero failed requests, no horizontal overflow, details open | PASS |
| 4 | No heading level skips, every aria-labelledby resolves | PARTIAL. aria-labelledby PASS. Heading order FAIL on explore.html (2 skips, RESIDUAL) |
| 5 | Pages workflow "Check static public bundle" passes | FAIL on 1 command, environment-caused (see below). 200 of 202 pass, 1 environment-only symlink hit |
| 6 | Rendered-text counts at most one each | PASS on index.html and method.html. FAIL on explore.html for "estimate" (9) and middle dot (26,456), RESIDUAL |
| 7 | No Tier 1 hits (em dashes, curly quotes) | PASS. 0 em dashes, 0 curly quotes on all three pages. The tool scores explore.html 61.3% only because of run ids containing `--` (RESIDUAL) |

## Findings

### RESIDUAL

1. **explore.html, heading skip, `#clef-first-pass-results`.** A heading "Cloudflare Clef" is an h4 straight under the section h2. It comes from the template at `public-site/app.js:289`. The base commit did not have this skip, so it is new. Fix: emit h3.
2. **explore.html, heading skip, `#finding-prompts`.** "39 model setups compared" is an h4 under an h2 (`public-site/findings.js:27`). Present on the base commit too.
3. **explore.html, middle dot count 26,456.** Target was zero. The dots are separators in run labels. They sit mostly in the `<option>` text of `#comparison-list`, `#inspect-run-select`, `#usage-run-select`, `#compare-run-select`, `#sensitivity-run` and `#experiment-select`, plus `#case-panel` and `#outcome-coordinate`. Base had 21,400 on explore.html and 72 on index.html. Index is now 0 and method is 0. Only the legacy panels remain.
4. **explore.html, "estimate" appears 9 times.** Target was at most one. These are the "API-rate estimate" column heads and basis notes in `#usage-summary`, `#cross-pair`, `#analysis-refresh-table` and `#repeat-selected-results`, and prose in `#jev-note` and `#findings-decision`. Base had 22 case-sensitive. "provisional" fell from 41 to 1 and "same 60" from 95 to 0.
5. **explore.html, run ids in the dropdown labels contain `--`, 962 times** (for example `fable51-high-phase2-batch10-p0--p1`). The anti-slop tool counts each as a double-hyphen hard ban, so explore.html scores 61.3%. These are identifiers, not prose. They are still shown to visitors when a select is opened.

### Noted, not findings

- **Pages workflow command 3, symlink find.** It hits 5 links, all under gitignored `public-site/deck/verify/node_modules`. Environment-only, as predicted.
- **Pages workflow command 52, `python3 -m unittest tests.test_subscription_price_estimates -q`: FAILED (errors=2).** Cause: `scripts/build_subscription_price_estimates.py:192` calls `relative_to(ROOT)` on an absolute path to the primary checkout's `results/` folder. That path exists on this Mac, and this worktree is not at that path. On CI the absolute path does not exist, so the candidate is skipped. I ran the same test file in the primary checkout and it passes (7 tests, OK). Neither file changed between the base commit and now. I could not prove CI behaviour here, so this is an inference from the code plus the primary-checkout pass.
- **Console warning on index.html desktop.** Two Chromium software-GL messages, "GPU stall due to ReadPixels". The base commit prints the same two. Not from the site code.
- **Mobile nav links extend past 390px.** They sit in `nav.main-nav` with `overflow-x: auto`, so the page itself does not scroll. The base commit's explore.html overflowed horizontally on mobile with details open (scrollWidth 820 on 390). The current tree does not.
- **Two cells render a null feed value as the words "not recorded"** (clef-flash reliability bin 5 on index.html). Intended.

## Raw results

### Claim 1: `node docs/site-pass/verify/claim1.mjs`

My own checker. Loads each page at 1440x900, scrolls through, waits for panels, opens every details, then reads every element with `data-source`, `data-text-source` or `data-derived`. Resolves each path against the JSON on disk. Allows formatting only ($, +, %, x, commas, rounding to the shown decimals, ISO date to long date).

```
index.html:   source-bound=439 derived=33  (machine-checked 31) mismatches=0 null-rendered-as-label=2
explore.html: source-bound=517 derived=271 (machine-checked 270) mismatches=0
method.html:  source-bound=62  derived=0                          mismatches=0
TOTAL source-bound checked=1018; derived total=304, machine-checked=301; mismatches=0
```

Derived formulas checked: display labels against the findings feed, "DEV-nnn not in disagreementCaseIds", ratios such as 3.6x and 37.7x, "five" as 59 - 54, the Sonnet 5.5 run metrics and API-rate estimates read from `sonnet55-fresh-matched3.json`. Three derived formulas I checked by hand:

- "Two" = 6 misses - 3 disputed labels - 1 off-topic = 2. Correct.
- "Five" = intersection of Jev's 6 disagreement ids with the hard-case list = DEV-006, 013, 027, 029, 030 = 5. Correct.
- "39" = better 4 + same 14 + worse 21 = 39. Correct.

I did not run the existing `public-site/site/verify/verify-site.mjs`. The checker above is the only evidence for this claim.

### Claim 2: `node docs/site-pass/verify/claim2.mjs`

```
rows parsed: 161 (grep confirms 161 table rows)  new-id groups: index 8, explore 4, method 1
2a ids checked=174 failures=0     (exactly one element per id after render)
2b shim links checked=181 failures=0
   (161 anchors, 14 query-string forms with and without #inspect, 5 negative controls that must stay on index.html, 1 live hashchange)
2c shim id lists vs map: explore: none missing, none extra. method: none missing, none extra.
```

### Claim 3: `node docs/site-pass/verify/claim3.mjs` and `... base`

```
page          vp       details  errors pageerr failedReq http>=400 warnings  overflow(closed/opened)
index.html    desktop  4        0      0       0         0        2 (GL)    false/false
index.html    mobile   4        0      0       0         0        0         false/false
explore.html  desktop  105      0      0       0         0        0         false/false
explore.html  mobile   105      0      0       0         0        0         false/false
method.html   desktop  1        0      0       0         0        0         false/false
method.html   mobile   1        0      0       0         0        0         false/false
```

Base `ffb9305a` (extracted with `git archive` into a scratch folder, since removed): same two GL warnings on index desktop, zero errors everywhere, and explore mobile overflowed with details open (sw 820/cw 390).

### Claim 4 and 6: `node docs/site-pass/verify/claim467.mjs`

```
index.html    headings=31 h1=1 skips=0   aria-labelledby=21 missing=0
explore.html  headings=99 h1=1 skips=2   aria-labelledby=42 missing=0
   SKIP h2 -> h4 "Cloudflare Clef"
   SKIP h2 -> h4 "39 model setups compared"
method.html   headings=11 h1=1 skips=0   aria-labelledby=8  missing=0
```

Counts in rendered text (innerText, details open, case-sensitive as listed):

| Term | index | explore | method |
|---|---|---|---|
| Hover | 0 | 0 | 0 |
| provisional | 0 | 1 | 0 |
| Sources | 1 | 0 (1 case-insensitive) | 1 |
| Computed by | 0 | 0 | 0 |
| SOLID | 0 | 0 | 0 |
| DESCRIPTIVE | 0 | 0 (3 case-insensitive, rendered as "Descriptive") | 0 |
| estimate | 1 | 9 | 0 |
| same 60 | 1 | 0 | 0 |
| Implication | 0 | 0 | 0 |
| · | 0 | 26,456 | 0 |

For comparison, base commit explore.html: provisional 41, estimate 22, same 60 95, middle dot 21,400. Base index.html: Hover 1, provisional 5, Computed by 9, SOLID 7, Implication 8, middle dot 72.

### Claim 5: `python3 docs/site-pass/verify/claim5.py` (and `claim5b.py`, `claim5tail.py`)

The runner extracts the block, runs each line with `bash -ec` from the repo root, records the exit code, and stops at the first failure. It replaces `/tmp/` with the session scratch folder so the mistral cmp does not write outside it. The block has 202 lines, two of them comments.

```
[003] exit=1  test -z "$(find public-site -type l -print)"
      symlink find: 5 total, 5 under node_modules, 0 elsewhere   -> environment-only
[052] exit=1  python3 -m unittest tests.test_subscription_price_estimates -q   Ran 7 tests | FAILED (errors=2)
```

Full traceback for [052]:

```
ValueError: '/Users/adamkovacs/Documents/codebuild/recruitment-feedback-demo/results/prompt-comparison-v1-2026-09-24/runs/codex-gpt-5.6-luna-high/P1/development-attempts.jsonl' is not in the subpath of '/Users/adamkovacs/lanes/cxb-talk'
  File "scripts/build_subscription_price_estimates.py", line 192, in codex_sidecar
    candidate.relative_to(ROOT).as_posix())
```

I then continued past [052] to see the rest. Lines 144 onward are multi-line shell (backslash continuations, a heredoc, `mktemp`, `git archive`), so line-by-line execution is wrong for them. I ran lines 144 to 202 as one script with `bash -e -x`: exit 0. That includes the three `git archive` rebuilds with cmp and the Gemma tamper check.

Totals: 200 of 202 lines exit 0, 1 environment-only symlink hit, 1 environment-caused unit-test failure.

| Suite | Tests | Pass | Fail |
|---|---|---|---|
| `node --test` (all `_ui.cjs` named in the block, 29 files) | 235 | 235 | 0 |
| Python `unittest` (sum of "Ran N" lines) | about 490 | all but 2 | 2 errors, both in the command 52 file |

The Python figure is a sum of the "Ran N tests" lines. The 29-file count comes from a pattern match on the block.

### Claim 7: `bun run /Users/adamkovacs/.claude/skills/anti-slop/scripts/audit-slop.ts <page>.visible.txt`

Input is each page's rendered innerText, details open.

| Page | Words | Slop instances | Score |
|---|---|---|---|
| index.html | 4,555 | 0 | 100.0% |
| method.html | 1,365 | 0 | 100.0% |
| explore.html | 124,335 | 9,620 (962 double-hyphen hits, each penalised 10) | 61.3% |

Direct counts with grep on the same files: em dash `—` 0, curly quotes 0 on all three pages. Every `--` on explore.html is inside a run id.

## Could not verify

- CI behaviour for command 52 (no CI run available here).
- Rendering on a real GPU. The browser used software GL.
- Interactions after load, such as changing selects. The checks read the settled DOM only.

## Files

Scripts and raw outputs are in `docs/site-pass/verify/`: `claim1.mjs`, `claim2.mjs`, `claim3.mjs`, `claim467.mjs`, `claim5.py`, `claim5b.py`, `claim5tail.py`, `claim5c.py`, `lib.mjs`, `probe.mjs`, `offender.mjs`, with matching `.out` files and the three `*.visible.txt` page dumps.
