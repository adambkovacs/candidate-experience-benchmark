# Codex delta charter: PR 3, talk presentation follow-up

Pinned head: `835bee452c0b8167b744685b745100e480f9e178` (branch `feat/talk-presentation-v2`).
Base (deployed main): `82fb8384`. Review only the diff `82fb8384..835bee45` and the code it touches.
Repo: `/Users/adamkovacs/lanes/cxb-talk`. Do not edit anything. You may run read-only commands and write tests under the verify-tests directory.

## Claims to refute

Try to make each claim FAIL. A claim holds only if you could not break it.

- **S1. Same-document legacy anchors forward.** The inline shim in `public-site/index.html` re-runs on `hashchange`, so a same-document change such as `#inspect` forwards to `explore.html#inspect`. A fresh load of `index.html#inspect` lands on `explore.html#inspect`. Method ids (`method`, `method-title`, `findings`, `findings-title`) land on `method.html`. Query strings with `run=`, `case=`, `experiment=`, `compareRun=`, `cohort=` or `category=` survive the forward with their hash. Look for ids that should forward but do not, ids that forward to the wrong page, and loops.
- **S2. No dangling in-page anchors.** No page carries an `href="#id"` whose id is absent from that same page. Pages: `public-site/index.html`, `public-site/explore.html`, `public-site/method.html`, plus every string emitted by `public-site/*.js` that builds an `href="#..."` or sets `location.hash` for those pages. Hash-router links of the form `#/slide` inside `presentation.html` are out of scope for this claim.
- **S3. Slide `a6-cost` numbers are bound.** Every number on `public-site/presentation.html` slide `a6-cost` (the two cost totals included) is bound to a feed path in `public-site/deck/data/answer.json` or the other deck feeds that resolves to the same value. A hard-coded number with no binding, a binding that does not resolve, or a bound path whose value differs from the rendered text is a failure.
- **S4. The presentation test exercises what the page loads.** `tests/test_presentation_ui.cjs` exercises the scripts `public-site/presentation.html` loads (the `<script src>` list at the bottom of the file), not a stale or different page. A script the page loads that the test never touches, or a test that targets another HTML file, is a failure.

## Required output format

For every finding give: `file:line`, a concrete failure scenario a real user or reviewer could hit, and a label `BLOCKING` or `RESIDUAL` with a one-line reason, using the rubric below. State per claim: HELD or REFUTED. End with one line `VERDICT: APPROVE` or `VERDICT: REQUEST-CHANGES`.

## Severity rubric (verbatim from scripts/lib/codex-review-rubric.md)

# Codex review severity rubric

Global rule: applies to every codex adversarial review, in every project, in both tiers
(`--tier standard` and `--tier two-key`). A hand-written two-key charter must `cat` this
file into itself rather than paste a copy of the wording — this file is the only copy.

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
