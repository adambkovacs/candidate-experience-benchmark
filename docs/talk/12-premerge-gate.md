# Pre-merge gate: PR 3 (branch feat/talk-presentation-v2)

Head `835bee452c0b8167b744685b745100e480f9e178`, compared with deployed main `82fb8384`. Run on 2026-10-08. No product file was edited.

**Recommendation: DO NOT MERGE.** The codex standard-tier gate returned REQUEST-CHANGES with three confirmed BLOCKING findings (section 3). CI replay and deck checks are clean apart from one known environment-only failure.

## 1. CI replay of "Check static public bundle"

Method: the 202 commands of the run block in `pages.yml` were extracted unchanged and run in a clean detached checkout of 835bee45, python3 3.14.6, node v26.10.0. The block runs as one script with no early exit and an ERR trap that logs every failing command.

A first attempt used a plain `git archive` copy and is discarded. An archive has no `.git`, and the block calls `git ls-files` and `git archive <old sha>`, so it cannot pass there. That attempt also split multi-line shell constructs, which produced false failures. The checkout below is the authoritative run (a detached worktree under the session scratchpad, removed afterwards).

Result: 1 failing command out of 202.

```
##FAIL line=55 cmd=python3 -m unittest tests.test_subscription_price_estimates -q
ValueError: '/Users/adamkovacs/Documents/codebuild/recruitment-feedback-demo/results/prompt-comparison-v1-2026-09-24/runs/codex-gpt-5.6-luna-high/P1/development-attempts.jsonl' is not in the subpath of '<checkout root>'
FAILED (errors=2)
```

| Failing command | First error line | Class |
|---|---|---|
| `tests.test_subscription_price_estimates` | `ValueError: ... results/... is not in the subpath of <checkout root>` | environment-only (known): `results/` resolves to the primary checkout |

Branch-caused failures: none. Every `node --test` summary in the run reports `fail 0`, including `tests/test_presentation_ui.cjs`.

## 2. Deck fit and bound numbers after 76e2d7e7 and 12e749e1

Served from the clean copy. The verify scripts start their own static server on a free port rooted at `public-site/` of the copy they live in (same job as `python3 -m http.server`). Playwright 1.61.1 came from the worktree `node_modules` via symlink. Both deck pages were run, at 1920x1080, 1366x768, 1280x720 and 1440x900.

| Page | fit.mjs | numbers.mjs |
|---|---|---|
| `presentation.html` (the 34-slide deck) | `RESULT: PASS`, 34 slides x 4 viewports all PASS, `a6-cost` PASS at all four, print PDF 56 pages, unbound numbers 0 | `RESULT: PASS`, live 459 number and 15 review items, print 681 number and 59 review items |
| `presentation-v2.html` (4-slide template) | `RESULT: PASS`, 4 slides x 4 viewports all PASS | `RESULT: PASS`, 6 numbers live and print |

`numbers.mjs` only audits elements that carry a `data-source`. It cannot see a number that has no binding, which is why it passes while finding S3 below stands.

## 3. Codex delta gate

Command, from `/Users/adamkovacs/Documents/codebuild`:

```
scripts/codex-verify.sh --tier standard --repo /Users/adamkovacs/lanes/cxb-talk --base 82fb8384 --head 835bee45 --charter /Users/adamkovacs/lanes/cxb-talk/docs/talk/codex-charter-delta.md
```

Charter: `docs/talk/codex-charter-delta.md` (pins 835bee45, claims S1 to S4, rubric pasted verbatim from `scripts/lib/codex-review-rubric.md`).

**Exit code 1. FINAL VERDICT: REQUEST-CHANGES (score 25/100).** Codex ran: A (gpt-6-sol high), B (gpt-6-luna), C (three falsification tests, all failed on the pinned commit), D1, D2. Raw output is in `.claude/verify/20261008-110731-835bee4-32455/` (untracked).

| Claim | Codex | Label | Finding |
|---|---|---|---|
| S1 same-document anchors | REFUTED | BLOCKING | `public-site/index.html:9`. `index.html?run=abc#method` forwards to `explore.html?run=abc#method`, which has no `method` anchor. The query test runs before the method-hash test. Falsification test output: `actual: 'explore.html?run=abc#method'`, `expected: /^method\.html.../`. Plain `index.html#inspect` and `hashchange` forwarding were not refuted. |
| S2 no dangling `#id` | HELD | none | No confirmed finding. |
| S3 a6-cost numbers bound | REFUTED | BLOCKING | `public-site/presentation.html:588`. The table header "All four, of 60" has a hard-coded 60 with no feed binding. The two cost totals and every table cell resolve. Test output: `the displayed 60 must be in an element with a feed binding`. |
| S4 test covers loaded scripts | REFUTED | BLOCKING | `tests/test_presentation_ui.cjs:18`. The loop only parses each script with `new vm.Script`; it executes only `deck/deck.js`. A runtime throw in a loaded script goes unnoticed. |

I reproduced S4 independently: prepending `throw new Error("injected");` to `public-site/deck/content/charts.js` in the clean copy leaves `tests/test_presentation_ui.cjs` at 5 tests, 5 pass, 0 fail. The codex C-stage test for S4 was only a source-text regex, so this reproduction is the stronger evidence.

Cost (`cost.json`, api-equivalent USD):

| Stage | Model | Effort | Input | Cached | Output | Wall s | USD |
|---|---|---|---|---|---|---|---|
| A | gpt-6-sol | high | 742061 | 659456 | 9741 | 265 | 0.3945 |
| B | gpt-6-luna | medium | 144993 | 108544 | 2297 | 50 | 0.0059 |
| D1 | gpt-6-luna | high | 22255 | 0 | 249 | 15 | 0.0024 |
| D2 | gpt-6-sol | high | 51196 | 23424 | 2263 | 62 | 0.0829 |
| Total | | | | | | | 0.4856 |

Triage note for the lead (not codex's label): S1 needs a legacy link that carries both a run-style query and a `#method` hash, which is unlikely in real use, and S3 is a correct number that is only unbound. By the rubric either could be downgraded to RESIDUAL. S4 is a real gap in the test's stated purpose. If the lead keeps codex's labels, all three are small fixes: test the method hash before the query in the shim, bind the 60 to `findings.json#charts.costAgreement.rows[...].denominator`, and execute each loaded script in a stubbed context in the test.
