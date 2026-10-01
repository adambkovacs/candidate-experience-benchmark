# Website presentation review, 1 October 2026

The public page now starts with the task, follows three findings, then opens into the result tools. This revision addresses repeated explanations, dense terminology and small text. It does not change model outputs or reference labels.

## Reading order

1. One fictional comment introduces the four decisions and explains why sentiment alone cannot determine follow-up, serious concerns or testimonial use.
2. Three chapters show Jev's disagreements, the instruction comparison, and a selected example of answers changing on a repeat. Clickable chapter navigation also follows scroll position.
3. A scoring explanation precedes the model results. The detailed explorer retains prompt comparisons, repeats, individual answers, tokens, costs, timing and source links.

The duplicate three-number introduction was removed. The later Jev feature became a compact link into the comparison tools. Jev's historical 54/60 API result is distinguished from the 52–54/60 base-task range in the fresh repeat study.

## Language and audience

We applied Academy voice and anti-slop guidance, with Fulcrum's HR, talent acquisition and transformation audiences in mind. The page explains experimental terms before using their codes. Practical implications sit beside each finding; builders can open the method and source records.

Examples of the changes:

- "Paired setups" becomes "model setups compared", with an explanation of what stays fixed.
- Costs are described as recorded charges for particular runs, not product prices.
- An unfinished local study says that three passes are planned, rather than implying they have all finished.
- A missing record is described as "without a saved response". This does not imply the request was never attempted.

The navy and blue palette, larger evidence text, spaced chapter layouts and progress indicators support the reading order. Motion respects the operating system's reduced-motion setting. There is no scroll hijacking or autoplay.

## Evidence and verification

The story's numbers remain tied to [saved findings](../public-site/findings-provider-errors-v1.json), the [selected repeat example](../public-site/reader-evidence.json), and [Jev repeats](../public-site/typesafe-repeats.json). The [reader tests](../tests/test_reader_story.py) verify those counts and the example comment against saved records.

Checks before publication: 87 UI tests and four story evidence tests passed. Root inspected 390px mobile and 1440px desktop layouts, fixed heading spacing, and checked keyboard chapter navigation, reduced-motion behavior, Jev repeat selection, overflow and browser errors. Independent review found no remaining blocking issue.

This is a presentation checkpoint. Required benchmark runs and recovery work remain tracked in [TODO](TODO.md).
