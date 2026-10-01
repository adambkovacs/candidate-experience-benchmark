# Website editorial revision, 1 October 2026

The page now presents the findings before the model rankings. Readers see a fictional candidate comment, the four questions, and three examples of what the saved answers reveal. The detailed analysis opens on demand. Existing links still take readers directly to the requested section.

This follows the user's request for Academy voice, everyday language, clearer findings and a more deliberate visual presentation. We used Fulcrum's Academy voice and ICP references, the unified anti-slop guidance, and the existing-project redesign skill. The relevant audiences are recruiting and HR teams, leaders approving a pilot, and people building the workflow.

## Reading and exploration

- The opening example distinguishes candidate experience feedback from assessments of candidates. It explains that the reference answers are provisional and AI-generated.
- The story covers Jev's six disagreements in one historical run, the first-pass prompt comparison, and an example of changed answers in two Gemma runs. Each example links to its detailed comparison or saved responses.
- Advice for each audience follows the examples: agree on labels and follow-up actions, examine repeat results, and test the intended workflow on its own examples. The study does not recommend a production model.
- Five detailed analyses sit within a native disclosure. Fragment links open it automatically, including on a direct visit and browser history navigation. Without JavaScript, the disclosure starts open.
- The model ranking, P0/P1/P2 explorer, saved responses, tokens, costs and measurement explanations remain available. No benchmark outputs or reference labels changed.

## Language and visual changes

Academy blue and navy, Archivo headings and Plex body text replace the previous green reading theme. The story has a sticky chapter navigation, visible reading progress and interactive prompt charts. Native keyboard controls, focus indicators and reduced-motion behavior remain available. The mobile header uses a scrollable navigation row to leave more room for content.

The copy now identifies the 21-of-39 finding as a first-pass comparison. The Jev overlap table correctly says it covers all 60 comments. Reference review wording distinguishes the proposed DEV-006 correction from the two sentiment labels awaiting human review. A changed answer is explained separately from a changed score. Native P0 repeats are named separately from prompt-and-pass runs.

## Verification

- Four source-bound reader tests passed. Numerical checks still use saved input, reference and response files.
- The 95 UI cases were checked. Two old text assertions needed the new repeat wording; both passed after that update. No measurement assertions were removed.
- Desktop rendering at 1440 by 1000 and mobile at 390 by 844 were inspected. The mobile document fits the viewport without horizontal overflow. Before and after screenshots are local verification artifacts, not benchmark evidence.
- In the desktop check, the main story moved from approximately 3,125px to 1,513px down the page. The default page height fell from 23,862px to 15,200px with the detailed analysis closed. These are layout observations at that viewport, not performance measurements.
- Browser checks covered opening the detailed prompt comparison, a direct repeat-analysis link, history navigation, chart selections and keyboard activation. The chart showed 15/15/9 for P0 to P1 and 4/14/21 for P1 to P2. A local browser video records the interactions.
- Reduced-motion emulation reported no comment-cell animation and zero chart transition duration. The browser error log was empty during the checked flow.
- The Academy anti-slop script found zero markers in 3,939 words of extracted static headings, paragraphs and summaries. This is a phrase scan, not proof of editorial quality. A separate manual review covered dynamic findings copy.

Sources: [public findings data](../public-site/findings-provider-errors-v1.json), [reader example data](../public-site/reader-evidence.json), [reader tests](../tests/test_reader_story.py), [reference review](REFERENCE_REVIEW_V1.md). The earlier [reader revision](WEBSITE_READER_REVISION_2026-10-01.md) remains a historical checkpoint.
