# Reader presentation revision, 1 October 2026

The public page now opens with the practical task: deciding which candidate feedback needs action. The score explanation and model comparison appear before the longer findings. Existing result, prompt, repeat and individual-comment links remain available.

A four-step explainer covers the fictional comments, the four decisions, the instruction sets and the repeat study. Readers can select a step without leaving the page. The prompt finding now lets readers compare P0 to P1, P1 to P2 and P0 to P2. Counts come from the existing source-bound findings file; the fixed chart scale remains zero to 21 setups across all three selections.

The copy follows Fulcrum's Academy voice and anti-slop guidance: concrete examples, short explanations and clear qualifications. The page distinguishes candidate experience feedback from interviewers' assessments. It also explains that testimonial potential is not permission to publish a comment. The Jev figure keeps draft-reference agreement separate from verified accuracy, and the selected Gemma example explicitly covers two passes rather than the full repeat result.

The reading layout uses larger body text, shorter lines, quieter surfaces and a consistent color palette. Prompt bars animate between selections. Comment cells appear in record order as their chapter enters view. All new controls are native buttons; motion is disabled when the reader requests reduced motion. No benchmark evidence or labels changed.

## Verification

- Independent source and code review: APPROVE, no confirmed blocking or residual findings.
- All 95 previous HTML IDs and existing links retained; no duplicate IDs or broken local fragment targets in the review.
- Four reader-story tests, 12 pairing/repeat/specialist UI tests and the findings UI integration check pass.
- Source counts checked: P0 to P1 has 15 higher, 15 equal and 9 lower scores; P1 to P2 has 4, 14 and 21; P0 to P2 has 7, 16 and 16. Each comparison contains 39 setups.
- Browser checks: desktop view, 390px mobile layout without horizontal overflow, keyboard step selection, chart selections and reduced-motion mode. Reduced-motion computed animation is `none` and transition duration is `0s`.
- A three-frame browser screencast captured the prompt-chart transition; local verification artifacts are not public benchmark evidence.
- Academy anti-slop script checked the extracted static page copy. Its only flagged punctuation was the pre-existing em-dash score-loading placeholder, not a prose sentence. Manual review covered the new explanations and chart wording.

Sources: [published findings data](../public-site/findings-provider-errors-v1.json), [reader evidence](../public-site/reader-evidence.json), [reference review](REFERENCE_REVIEW_V1.md), [reader tests](../tests/test_reader_story.py). Publication is verified separately against the deployed commit.
