# Published report browser checks, 6 October 2026

Checked the [public report](https://adambkovacs.github.io/candidate-experience-benchmark/) in Chrome while the next report update was still being prepared. This check applies to the deployed page, not unpublished results.

- The main navigation exposes findings, results, prompt comparison, repeatability, reviews and method.
- With browser emulation set to `prefers-reduced-motion: reduce`, the page reports the preference as active and the root element's computed scroll behavior is `auto`.
- The resource-use section contains `usage-run-select`, labelled "Choose a run for resource use". Readers can select a run within that section.
- The browser reported no console errors during this check.
- Reduced-motion emulation was cleared afterward.

These are bounded checks. The browser's read-only DOM interface did not expose `document.getAnimations()`, so this check does not establish that every animation stops. Full keyboard navigation, visual focus, all responsive breakpoints and motion across every interactive chart remain to be checked. Earlier 390-by-844 viewport checks are recorded in [the checklist](TODO.md).

## Later analysis publication check

The publication repair in `67e5356a` passed GitHub Pages run [37522399801](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/37522399801). The live DeepSeek high continuation feed, combined analysis JSON and analysis JavaScript matched that commit byte for byte. This verifies the repaired three-stage high report; the newer five-stage report and low P1 update were still awaiting deployment when checked.

In the in-app browser, the rendered analysis showed Liquid's nine complete runs, P0/P1/P2 scores of 43/43/43, 42/44/42 and 41/41/41, and zero/three/zero reviews with changed labels. It also showed 3,637,332 development input tokens and $0.14549328 in development charges, excluding smoke tests. The high continuation retained its provider failure and truncated-answer qualifications. No console errors were captured during this check.

This was a content and loading check. It does not replace the remaining keyboard, responsive-layout and motion checks above. The detailed cohort list is long; verifying its numbers does not establish that its navigation or presentation meets the final design goal.

## Grouped findings check, 6 October 2026

The long analysis list now uses three native disclosure groups: seven decision-model entries, eleven hosted-language-model entries and nine historical-local entries. Independent review confirmed that all 27 entries, calculations and source links remain present. Fifteen focused UI tests pass. Both JavaScript and presentation stylesheet cache versions changed.

Local browser checks showed the grouped layout on desktop and at a 390-pixel viewport. The findings container measured about 320 pixels wide on mobile, with no document horizontal overflow. Enter opened the decision and hosted groups and retained keyboard focus. The browser captured no console errors. These controls add no custom animation or scroll behavior. The existing broader reduced-motion checks remain separate; this checkpoint is not a full-site accessibility audit.
