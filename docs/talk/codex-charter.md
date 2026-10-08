# Codex review charter: talk and site work

Repo: /Users/adamkovacs/lanes/cxb-talk (github adambkovacs/candidate-experience-benchmark)
Base: 6243eb3d (main before the work)
Head (pinned): 82fb8384cfd55ecd26fce58f9ecfbfb4ec34e502 (origin/main tip at charter time). Review only `git diff 6243eb3d 82fb8384cfd55ecd26fce58f9ecfbfb4ec34e502`.

You are an adversarial reviewer. Try to REFUTE each claim below by running or reading code. For every finding give file:line, a concrete failure scenario, and a BLOCKING or RESIDUAL label with a one-line reason.

## Claims to refute

1. `public-site/presentation.html` and `public-site/deck/**` present every number bound to a feed path that resolves (data-source attributes), and load no network resource (no http(s) URL fetched, no CDN, no remote font or script).
2. `public-site/index.html`, `explore.html` and `method.html` preserve every panel id the panel JS queries, and the legacy-link shim forwards old anchors to the right page.
3. `scripts/build_deep_insights_v1.py --check` and `tests/test_deep_insights_v1.py` reproduce `public-site/deep-insights-v1.json` from source hashes.
4. No secret, API key, private candidate data or absolute local path is committed under `public-site/` or `docs/talk/`.
5. The retargeted tests (`tests/test_presentation_ui.cjs`, `tests/test_clef_public_ui.cjs` and the ten tests moved to explore.html) still assert behaviour rather than being weakened.
6. Nothing in the diff mutates frozen reference labels or `results/` evidence.

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

Per finding: id, CONFIRMED/RESOLVED/INCONCLUSIVE, file:line, concrete failure scenario, blocking true/false with reason. Do not report style nits. Do not edit files.
