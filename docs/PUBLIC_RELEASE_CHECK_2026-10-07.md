# Deployed report and presentation check

This checks the public release required by [the goal](APP_GOAL.md). Record the deployed commit, URL, checker, date and observed result for each item. A passing source test or matching asset hash does not establish rendered behavior. Current status: **passed on the deployed edition on 8 October 2026**, as recorded below. The earlier browser-policy rejection is an access limitation, not evidence of a UI defect; do not bypass it.

1. Open the report on desktop and at a 390 px viewport. Check headings, legends, tables, model selectors and navigation for clipping or overlap. Read one finding without opening technical details and explain its denominator.
2. Select Decision models, General-purpose LLMs and All models. Confirm the overview, explorer and cohort-review panel follow the choice. Historical and fresh general cohorts must stay separately selectable; the seven-native panel must identify its fixed scope.
3. Search for a testimonial and an off-topic comment. Confirm the full text, reference, saved answers, disagreement count and unusable count are visible. Filtering must not imply that whole-cohort totals describe only displayed comments.
4. In the run inspector, compare a base run with an extended repeat and then a supplemental native run. Open a copied run/case/compare link in a fresh page and confirm the same exact selections. Inspect one failure: it must retain its status rather than display an invented answer.
5. Expand per-field results. Check horizontal table scrolling with keyboard focus; arrow keys must scroll the focused table without triggering other navigation. Precision and recall must name their denominators and preserve unanswered reference-positive cases.
6. Open the presentation. Use Next, Previous, Space, arrow keys, Home/End and the slide chooser. A reveal should advance before moving to another slide. Keyboard use inside controls and scrollable tables must remain native. Copy a slide/reveal URL and reopen it.
7. Enable reduced motion and inspect the report and presentation. Repeat on mobile. Confirm text and navigation remain readable and usable without animation. In print preview, all presentation reveals must remain available.
8. Follow source links from a difficult review, a prompt comparison, a repeat example and a cost example. Confirm the selected run and review resolve, the displayed values match their stated source and unavailable inference measurements are not presented as observed speed.

Save pass/fail observations and exact reproduction steps. Fix reachable feature failures before final publication sign-off. Do not remove the presentation preview label or declare visual verification complete until the required checks have evidence.

## Published preview checkpoint

Deployment [37663310311](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/37663310311) succeeded for `1a92880f`. Root verified the live presentation HTML, JavaScript and CSS against that commit. Nine automated presentation tests and independent factual/code review passed. These checks do not complete the rendered checklist above. A human check was requested on 7 October because the browser tool rejected navigation and prohibited alternate-browser workarounds.

Final report deployment [37663741601](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/37663741601) succeeded for `6387eb19`. Root verified ten live assets against that commit: report HTML; presentation HTML, JS and CSS; app and unified inspector JS; cohort-review JS/CSS; cross-category JS/CSS. All ten matched. Publication is verified; the eight rendered checks above remain open.

## Rendered acceptance, 8 October 2026

Checker: root agent using the Codex in-app browser through `cua_repl`, after the user's explicit browser permission. Tested the live GitHub Pages report and presentation from reviewed release `6387eb19`. The prior navigation rejection did not recur. No alternate-browser workaround was used.

| Check | Observed result |
| --- | --- |
| Desktop and mobile layout | PASS. Inspected report overview, cohort controls, field tables and presentation at desktop sizes and 390 × 844. Text and controls remained readable. No page-wide horizontal overflow in the measured mobile views; wide tables scroll within their panels. |
| Category and cohort selection | PASS. Top-level decision/general/all selections synchronize the review cohort. Verified 7 decision, 32 fresh general and 39 combined configurations; historical general remains a separate 117-row selection, or 124 combined. |
| Review filters and exact answers | PASS. The testimonial filter shows 9/60 reviews. Off-topic plus “soup” shows DEV-029 alone while preserving clearly labelled whole-cohort totals. Text, reference labels, saved answers and unusable counts are accessible. |
| All-source run comparison and reload | PASS. Compared base TypeSafe Jev with the extended Fable high repeat2/P0, inspected DEV-029, and reloaded the exact URL: both runs and the open review restored. Changed comparison to supplemental Clef Flash fresh3/P2 and inspected DEV-039; its provider-failure/unknown-cost outcome stays explicit in all four fields. |
| Per-field results and keyboard tables | PASS. Expanded testimonial confusion tables. Reference totals remain 60; yes precision and valid-subset recall state their denominators and omitted unanswered positives. In the 390 px table test, ArrowRight moved the focused 246 px container across its 500 px content. |
| Presentation navigation | PASS. Right arrow advances to the task, Space reveals its answer before advancing, Previous hides the reveal, PageDown/PageUp advance/reverse reveals, Home/End reach first/last slide, and the chooser selects the requested slide. Reloading `#repeatability/1` restores that slide and revealed content. ArrowRight inside the answer table does not advance slides. |
| Reduced motion and print | PASS. Tested `prefers-reduced-motion: reduce` in report and deck, with usable controls and mobile layout. Print-media inspection exposes all 10 slide sections and all 9 reveal blocks with visible computed styles. Temporary viewport/media overrides were cleared. |
| Evidence and measurements | PASS. Followed cost and P2 prompt links into the exact Gemma 31B run selections; the P2 view reports 55/60 matches and 60/60 valid. Compared repeated answers and inspected an explicit provider failure. Client duration, provider generation duration and missing inference measures retain distinct labels. No browser-console errors were captured during these checks. |

This is a bounded release acceptance check, not an exhaustive cross-browser accessibility certification. The “development preview” badge describes the exploratory 60-review study; it no longer means rendered verification is pending. No benchmark request was sent and no measurement or reference label changed.

Screenshots: [desktop field tables](release-evidence-2026-10-08/report-fields.jpg) and [presentation repeat example](release-evidence-2026-10-08/presentation-repeat.jpg).
