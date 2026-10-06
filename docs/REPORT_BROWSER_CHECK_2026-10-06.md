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


## Grouped findings publication verified

Pages run [37527766678](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/37527766678) succeeded for `a079b01b`. Live `index.html`, `presentation.css` and `analysis-refresh.js` match that commit byte for byte. The Tev and DeepSeek high reports also match their integrated `07ca8c45` versions. This verifies deployment of the previously checked interface; it does not claim a new full-site UX audit.


## Resource selector and subscription estimate check

On the live page, the resource-use section exposes 304 saved run choices. Selecting `fable51-high` changed the section to that run and displayed 120 input tokens, 186,000 cache-read tokens, 28,275 cache-write tokens, 11,715 output tokens and 3,312 reasoning tokens. Its API-equivalent estimate is $1.19895, with a dated public pricing link and explicit separation from unknown subscription charges. This checks display against the selected published feed, not a new independent pricing audit.

At a 390-by-844 viewport, document width was 375 pixels and the selector was about 320 pixels wide; the screenshot showed readable content and a visible focus outline. The temporary viewport was reset. No console errors were captured before this interaction. Automated ArrowDown/Enter left the selected value unchanged, so keyboard selection is not claimed verified. The prior disclosure-keyboard checks remain separate.

## Historical snapshot labels

A live browser check confirmed that the final DeepSeek low findings render in the hosted-model disclosure, including P0/P1/P2 scores of 58/57/58 and the separate paired-comparison denominators. The page captured no console errors. Two older high-effort entries still sounded like current incomplete totals; commit `755969c2` labels them as historical checkpoints and points to the later results. All 15 analysis UI tests pass. Deployment verification is pending.

Keyboard selection of the native resource dropdown remains unverified: locator Home/Enter left the selected value unchanged, and the browser tool does not support raw CDP key dispatch. This is a test limitation, not evidence that the website's native select is broken. Programmatic selection and displayed pricing were verified in the earlier check.

## Liquid paired chart integration check

The integrated chart in `7b308d14` was checked on the local site in the in-app browser. All nine comparisons render, with changed-answer counts separate from gained/lost full matches and an explicit 60-review denominator. Desktop shows three pass columns. At a 390-by-844 viewport, the chart is about 320 pixels wide and stacks the pass groups; document scroll width equals client width (375 pixels). The visible mobile rows and labels do not clip. No console errors were captured. The temporary viewport was reset.

This is local rendering evidence, not deployment verification. The chart has no interactive control beyond its source link. Its stylesheet disables animations and transitions under reduced motion; the broader site's keyboard and motion checks remain open.

## Liquid paired findings publication

[Pages run 37534957568](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/37534957568) succeeded for `26dfa073`. The live Liquid findings feed, combined analysis JSON and analysis JavaScript matched that commit byte for byte. This publishes the nine paired calculations and their explanation. The chart integration in the following commit was still deploying at this check.

## Resource selector keyboard check resolved

On the local integrated page, the browser's native keyboard events (Space, Down, Return) changed `usage-run-select` from `typesafe-jev113-v2` to `typesafe-jev113-v2--p1`. The section updated to P1, showing 152,500 input tokens, 11,176 output tokens and a $0.006405 estimate. Focus remained on the selector with a visible solid outline. This resolves the earlier selector-specific keyboard test limitation; synthetic locator key presses alone did not change the value. It does not establish full-site keyboard coverage.

## Published Liquid chart and keyboard navigation verified

Pages run [37535467966](https://github.com/adambkovacs/candidate-experience-benchmark/actions/runs/37535467966) succeeded for `7b308d14`. Root compared live chart JavaScript, stylesheet and index bytes with that commit; all matched.

On the live page, reduced-motion emulation applied to 140 chart descendants. Every checked element had no animation and a zero-second transition; the root scroll behavior was `auto`. The override was cleared afterward. This verifies the Liquid chart, not every animation elsewhere on the site.

Native keyboard input focused “Skip to content” on the first Tab. Return moved to `#main`, and the next Tab focused “See what we found” inside the main content. The earlier resource selector check remains separate.

## Decision-model controls and Clef update, 7 October

On the local integrated page, a Solar first-pass deep link selected the correct run in the comparison, resource and individual-run controls. The resource panel showed 441,340 input tokens, 240 output tokens and $0.022067 in known development charges. Unmeasured request and server durations remained unavailable. Selecting Liquid's second pass in the prompt control displayed P0/P1/P2 scores of 43/44/41 out of 60, with all three linked to that same pass. These checks verify the new controls; they do not add desktop-wide or mobile-wide coverage.

The rendered decision-model findings also include the updated Clef evidence: seven full runs, unchanged P0 labels, one changed P1 follow-up decision, and two interrupted P2 runs shown separately. The source-backed JSON link remains available. This was a local rendering check after `a5f9b9b5`; publication verification for that edition is pending.

## Clef repeat grid

The integrated local Clef grid renders seven scored runs and two visibly interrupted runs, with explicit 60-review denominators. At a 390-by-844 viewport, the table remains inside a 284-pixel horizontal scroll region; the document width remains equal to its 375-pixel client width. The region has a keyboard focus target. No browser console errors were captured, and the temporary viewport was reset. Three component tests cover score/interruption separation, changed-data fallback, and scoped mobile/reduced-motion rules. Native Right-arrow input moved the focused table scroll region horizontally. Under reduced-motion emulation, all 94 chart elements had no animation and zero-second transitions. The media override was cleared afterward.
