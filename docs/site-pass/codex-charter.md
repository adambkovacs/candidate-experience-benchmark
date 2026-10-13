# Codex review charter: site content pass

Repo: /Users/adamkovacs/lanes/cxb-talk (github adambkovacs/candidate-experience-benchmark)
Base: ffb9305a
Head (pinned): 11788f7d (branch feat/site-content-v2). Full diff: `git diff ffb9305a 11788f7d`. A first pass already ran on b9287eb5 (see codex-gate.md: S1 blocking, S3 blocking, S2 residual).
**This second pass reviews only `git diff b9287eb5 11788f7d`** (public-site/app.js cost lines 193-205 and tests/test_subscription_price_ui.cjs). Ignore uncommitted working-tree edits.

Delta claims to refute:
- D1. A dagger now marks every API-rate figure (`price.estimateUsd` and `cost.estimatedUsd`) and no known or actual charge, in every list and detail view that calls `costSummary`; no estimate renders without the dagger and no charge renders with it.
- D2. The one-line note above each list ("Costs are provider bills. A † marks the API-rate equivalent ...") is true for every known charge shown, including Solar and other rows whose feed `cost.basis` says "covers returned answers only; smoke tests excluded ... no invoice amount is asserted". If it is false for any row, that is a charge-basis change.
- D3. The updated test still fails if the dagger or the figure regresses.
- D4. `costBasis` inserts the note once per list, also after re-render, and the text is not injected from feed data.

Earlier S1 (applyJevFindings falls back to wrong labels when the findings feed is missing) is still open by design; do not re-report it unless the delta changed it.

The diff rewrites copy, markup and CSS of public-site/index.html, explore.html and method.html, plus the JS panels that render feed data, and retargets about 70 tests. Treat any pre-existing defect outside the diff as out of scope.

You are an adversarial reviewer. Try to REFUTE each claim below by running or reading code (node/python available; tests live in tests/, run with `node tests/<file>.cjs` or `python3 -m pytest`). For every finding give file:line, a concrete failure scenario, and a BLOCKING or RESIDUAL label with a one-line reason.

## Claims to refute

a. The three pages render every data-source number correctly from the feeds, and no number changed meaning (route, charge basis, run count, price basis) in the rewrite. Compare hard-coded copy numbers in the HTML and JS against the feeds they describe.
b. The legacy link shim and the LINK-MAP ids still resolve. Every old anchor or panel id still lands on a real element on the right page.
c. `public-site/app.js` `applyJevFindings` override is correct and falls back safely when the findings feed is missing, malformed or mismatched to the run catalog (no throw, no NaN, no blank panel, no wrong run overwritten).
d. `public-site/repeats.js` `factLines` hides only hedge sentences and never a number-bearing fact. Check the sentence-split regex against decimals, abbreviations, "e.g.", "vs.", prices like "$1.20." and run ids.
e. `public-site/outcome-chart.js` data-driven domain never hides or clips a plotted run (including zero, negative, equal min/max, a single run, and empty data).
f. The updated tests still verify data, not just the new wording. Look for assertions weakened, deleted, loosened from exact values to regexes, or changed to match new copy while no longer checking the feed-derived number.
g. No XSS or injection path was opened where feed strings are now written to innerHTML. Check every changed `innerHTML`, `insertAdjacentHTML` and template literal that interpolates feed text without escaping.
h. Nothing in the CI check block regresses. Find the CI workflow and any check script it calls, and run the commands it runs against the head.

## Blocking rubric (verbatim from scripts/lib/codex-review-rubric.md)

Every finding carries a `blocking: true|false` label and a one-line reason, from the stage
that first raises it through the final adjudication.

- **BLOCKING** = reachable in *normal* operation (a real git/OS/tool, a real user, real
  concurrent sessions — no hostile binary on PATH, no hand-corrupted or NUL-injected file,
  no adversarial shim-timed race) **and** causes data loss or corruption, a security
  exposure, the change's own feature failing, or a regression.
- **RESIDUAL** = everything else that is confirmed. File it as a follow-up; it does not
  block approval.
- Security, auth and money findings still block whenever they are realistically reachable
  — "security-relevant" is not automatically RESIDUAL just because it required some setup.

Verdict rule: REQUEST-CHANGES only when at least one CONFIRMED finding is `blocking: true`.
Otherwise APPROVE, and list every other confirmed finding as a residual (`blocking: false`,
with its one-line reason).

## Output demands

Per finding: id, CONFIRMED/RESOLVED/INCONCLUSIVE, file:line, concrete failure scenario, blocking true/false with reason. A feed string is only an XSS risk if the feed is not under our control; say which feed and who writes it. Do not report style nits or copy-quality opinions. Do not edit files.
