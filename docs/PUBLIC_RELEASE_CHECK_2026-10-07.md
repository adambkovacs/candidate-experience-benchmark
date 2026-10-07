# Deployed report and presentation check

This checks the public release required by [the goal](APP_GOAL.md). Record the deployed commit, URL, checker, date and observed result for each item. A passing source test or matching asset hash does not establish rendered behavior. Current status: **not performed for the final integrated edition**. The earlier browser-policy rejection is an access limitation, not evidence of a UI defect; do not bypass it.

1. Open the report on desktop and at a 390 px viewport. Check headings, legends, tables, model selectors and navigation for clipping or overlap. Read one finding without opening technical details and explain its denominator.
2. Select Decision models, General-purpose LLMs and All models. Confirm the overview, explorer and cohort-review panel follow the choice. Historical and fresh general cohorts must stay separately selectable; the seven-native panel must identify its fixed scope.
3. Search for a testimonial and an off-topic comment. Confirm the full text, reference, saved answers, disagreement count and unusable count are visible. Filtering must not imply that whole-cohort totals describe only displayed comments.
4. In the run inspector, compare a base run with an extended repeat and then a supplemental native run. Open a copied run/case/compare link in a fresh page and confirm the same exact selections. Inspect one failure: it must retain its status rather than display an invented answer.
5. Expand per-field results. Check horizontal table scrolling with keyboard focus; arrow keys must scroll the focused table without triggering other navigation. Precision and recall must name their denominators and preserve unanswered reference-positive cases.
6. Open the presentation. Use Next, Previous, Space, arrow keys, Home/End and the slide chooser. A reveal should advance before moving to another slide. Keyboard use inside controls and scrollable tables must remain native. Copy a slide/reveal URL and reopen it.
7. Enable reduced motion and inspect the report and presentation. Repeat on mobile. Confirm text and navigation remain readable and usable without animation. In print preview, all presentation reveals must remain available.
8. Follow source links from a difficult review, a prompt comparison, a repeat example and a cost example. Confirm the selected run and review resolve, the displayed values match their stated source and unavailable inference measurements are not presented as observed speed.

Save pass/fail observations and exact reproduction steps. Fix reachable feature failures before final publication sign-off. Do not remove the presentation preview label or declare visual verification complete until the required checks have evidence.
