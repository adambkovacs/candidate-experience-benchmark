# Website story review: candidate feedback benchmark

Editorial recommendations recorded before the 30 September redesign. The implemented opening uses Jev, prompt comparisons and a selected two-pass Gemma example; the suggestions below remain a record of the review. The two stale FINDINGS.md table counts noted at the end were corrected.

The page should help a talent or AI leader ask a practical question: which candidate comments would an AI workflow flag, miss or handle differently the next time? The current explorer already lets readers inspect saved answers. Its opening should explain why those checks matter before presenting model names, prompt codes and charts.

This is a development experiment on [60 fictional comments](../data/pilot/inputs.jsonl). Four decisions are compared with [provisional answers](../data/pilot/proposed_labels.jsonl) drafted and reviewed by the same AI assistant. The page cannot establish accuracy on real candidate feedback, a safe hiring use or the best model to buy. Keep that limit beside the first score, not only in the method section. The [labeling guide](LABELING_GUIDE.md), [pilot audit](PILOT_AUDIT.md) and [reference review](REFERENCE_REVIEW_V1.md) explain why.

## Suggested opening

**Headline:** The same score can hide different candidate feedback decisions.

**Lead:** We gave AI systems the same 60 fictional candidate comments and asked for four judgments: sentiment, whether someone needs a reply, whether a serious concern appears, and whether the comment could support a testimonial. See where answers match our provisional reference, where they change on repeat, and where a response cannot be scored. Open any result to inspect the saved evidence.

**First actions:** "See the findings" (`#findings`), "Check repeated answers" (`#repeat-analysis`) and "Explore a comment" (`#inspect`). The current opening in [index.html](../public-site/index.html) starts with the benchmark title and routes readers straight to rankings. Its labels are accurate, but they ask a new reader to interpret a score before learning what the four decisions mean.

The Academy voice guidance calls for a reason, concrete evidence and active language. Here the reason is clear: a team should inspect individual answers because a total score can conceal a missed request or changed decision. Use the audience needs in Fulcrum's ICP messaging as an editorial lens, not its training-product promises or testimonials. This page reports an experiment; it does not sell an AI adoption outcome.

## Three findings to explain first

### Added instructions

Suggested copy: "Adding a decision procedure produced fewer matches in 21 of 39 audited setups, compared with the classifier instructions alone. Four gained matches and 14 kept the same total." The [source-bound prompt comparison](../public-site/findings.json), `charts.promptDeltas.groups[id=strict].comparisons.P1_to_P2`, and the [analysis](FINDINGS.md#more-instructions-did-not-consistently-improve-agreement) describe the cohort. These are first recorded passes on the same 60 comments. They do not isolate a prompt effect or describe every model. Lead to `#prompt-analysis` and its paired reports.

### Repeated answers

Suggested copy: "Gemma E2B matched all four provisional answers on 35 of 60 comments in each of three base-prompt passes. Nine comments received at least one different decision across those passes." The [fresh local repeat findings](GEMMA_E2B_FRESH_REPEAT_FINDINGS_2026-09-28.md) and [source-bound feed](../public-site/small-local-repeats.json) describe repeated answers to the same comments, not 180 independent comments. Lead to `#repeat-analysis` and put the changed-review count beside the score range.

### Unusable output

Suggested copy: "In one generated-output control, none of the 60 P0 answers followed the required JSON format in any of three passes. Its 0/60 agreement score reflects invalid output, so it cannot tell us how its valid classifications would have compared." The [AnyJev generated findings](ANYJEV_GENERATED_REPEAT_FINDINGS_2026-09-30.md) and [source-bound feed](../public-site/anyjev-generated-repeats.json) show that all 180 P0 answers were invalid under the declared strict parser; P1 behaved the same way. This generated control is separate from AnyJev's native procedures. Lead to `#repeat-analysis` and keep valid responses and all-four matches visible as separate numbers.

The first two cards address a leader's investment question and a practitioner's review question. The third gives builders a concrete integration lesson without claiming that output repair or a different parser was tested. A short case can bring the four decisions to life: in [DEV-059](FINDINGS.md#jevs-six-disagreements-need-different-explanations), Jev recognized a serious concern but missed the candidate's request to stop repeated contact. That example has a saved answer and a clear reference under the current guide; it is one fictional case, not a measured real-world miss rate.

## Reader paths

Talent and transformation leaders need to see what could go wrong when AI sorts feedback. Show the four decisions, one missed follow-up, the provisional-reference warning and then the findings. A model leaderboard would invite an unsupported buying decision.

Recruiters and feedback practitioners need to find comments that deserve another look. Start with review-level examples, invalid responses and changed answers, then show how to inspect a comment's four decisions.

Builders and evaluators need measures for their own pilot. Show format validity, the fixed 60-comment score denominator, changed answers on repeat, the shared-valid denominator for paired comparisons, source records and measurement coverage. Keep technical controls in expandable evidence notes.

These paths are editorial, not separate claims about customer outcomes. The ICP guidance identifies talent-acquisition owners' concern about AI replacing recruiters, leaders' need to assess investment risk, and builders' need for practical evidence. The site should answer those needs with the saved experiment, without borrowing Fulcrum course claims.

## Plain-language definitions to place near charts

- **All four match / 60:** One comment counts only when all four decisions match the provisional reference. Invalid answers remain in the 60-comment denominator. This measures agreement with this saved key, not independently established accuracy. [Scoring method](FINDINGS.md#scope-and-interpretation).
- **Valid response:** The output followed the required format and could be scored. It can still disagree with the reference. The current [method FAQ](../public-site/index.html) states this, but readers need it near the ranking and repeat charts.
- **P0, P1, P2:** The base task, added classifier framing, and added decision procedure. TypeSafe Jev changes native Choice-question instructions; its comparison is separate from chat-prompt comparisons. [Prompt analysis](FINDINGS.md#more-instructions-did-not-consistently-improve-agreement) and [native Jev protocol](JEV_REPEAT_ADMISSION.md).
- **Pass:** A separately dispatched attempt using the same 60 comments and prompt condition. Three passes do not create 180 independent examples. A tied score can still contain changed decisions. [Fresh local repeat findings](GEMMA_E2B_FRESH_REPEAT_FINDINGS_2026-09-28.md).
- **Changed answers:** Count a review once when at least one of its four decisions differs. Field-change counts can overlap. When a pass has invalid answers, compare classifications only among reviews valid in both passes; keep the fixed 60-comment score alongside that smaller denominator. [AnyJev generated findings](ANYJEV_GENERATED_REPEAT_FINDINGS_2026-09-30.md).
- **Cost and time:** A recorded API charge, a price estimate and an unknown charge are different facts. Client request duration includes workflow or network overhead; it is not isolated model thinking time. Local hardware and electricity cost were not measured. [Cost and timing limits](FINDINGS.md#scope-and-interpretation).

## Short FAQ for the main page

**Can these results tell us which AI to use with candidates?** No. The comments are fictional, the answer key is provisional, and the configurations differ. Use the saved cases to design a human-reviewed pilot on an appropriate dataset. [Method and limits](FINDINGS.md#scope-and-interpretation).

**Why does a result say 60 saved but fewer than 60 valid?** A request can return text that does not meet the required output format. The result remains in the fixed 60-comment score denominator, while the valid count reports how many answers could be evaluated. [AnyJev example](ANYJEV_GENERATED_REPEAT_FINDINGS_2026-09-30.md).

**Why inspect a comment when two scores match?** Two passes can agree on the total and differ on which reviews they classify correctly. Gemma E2B's base prompt scored 35/60 in all three passes while changing decisions on nine reviews. [Saved repeat analysis](GEMMA_E2B_FRESH_REPEAT_FINDINGS_2026-09-28.md).

**Did the prompt change cause the score change?** The saved comparisons show what happened under their recorded settings. Time, serving details, invalid outputs and incomplete repeats can also matter. The charts distinguish audited pairs, hosted observations and native Jev questions. [Paired analysis](FINDINGS.md#more-instructions-did-not-consistently-improve-agreement).

**Why is a price or time missing?** A missing bill is unknown, not free. A request duration is a client measurement; pure inference time appears only when separately reported. [Measurement limits](FINDINGS.md#scope-and-interpretation).

## Current copy to revise as the page is rebuilt

The ranking in [index.html](../public-site/index.html) introduces "all-four agreement" before it explains the four decisions or the provisional key. [app.js](../public-site/app.js) correctly shows valid responses beside all-four matches, but the Jev-first comparison can read like an endorsement unless the page says why Jev is a worked example. The "Better / Same / Worse" legend in [findings.js](../public-site/findings.js) should say "More / Same / Fewer matches" because the measure is agreement with a provisional key. Its 21/39 headline needs the comparison baseline, cohort and first-pass limit in the same view.

The repeated-result controls in [repeats.js](../public-site/repeats.js) preserve crucial distinctions among native, generated, hosted and local studies. Keep them. Lead with model, valid answers, score denominator and one changed-answer takeaway; put route, parser, token and timing qualifications in accessible details beside their chart. The current "Does the prompt advantage persist?" heading assumes an advantage before the data shows one. "How did the prompt scores change across passes?" fits both gains and losses.

The existing [method section](../public-site/index.html) and FAQ already explain important limits. Move a one-sentence version of the reference and validity caveats close to the first chart, then retain the full method below. Keep record links, source hashes, invalid outcomes, unknown charges and missing phases available to the reader. Do not collapse them into a claim of reliability or model quality.

**RESIDUAL, one-line reason:** The summary table in [FINDINGS.md](FINDINGS.md#more-instructions-did-not-consistently-improve-agreement) gives P0-to-P1 as 15/15/8 and P0-to-P2 as 7/16/15, while the [source-bound JSON](../public-site/findings.json) has 15/15/9 and 7/16/16 across 39 rows; the current site uses the JSON, but the linked markdown table can mislead readers and should be corrected separately. The P1-to-P2 4/14/21 count used above agrees with the JSON and page.
