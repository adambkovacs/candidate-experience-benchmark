# Cold read of the deck (stranger, no speaker)

Evidence: SHA 35cdc4c8, captured at 1920x1080 with review-capture.mjs (34 slides, "problems: none"). JPGs and text are in docs/talk/sprint/cold/ (01.jpg to 34.jpg, text.json). I looked at slides 1 to 19 and 20, 21, 23, 29 as images. The other appendix slides (22, 24 to 28, 30 to 34) I read as text only. I judged final (fully revealed) states from stills, so I cannot say anything about motion. Contrast is judged by eye, not computed (the mechanics lane owns ratios).

Verdict on the claim "a smart stranger can follow every slide without the speaker": refuted. 9 of 19 main slides I followed, 9 I half followed, 1 I did not. The setup slides (3, 6, 7, 8, 11, 12) are good. The failures cluster in three places: the answer slide that comes before the setup, the general-models slide, and the jump from the agree-or-defer rule to the queue.

Counts: slides FOLLOW 9 / PARTIAL 9 / LOST 1 (main slides 1 to 19). Adam's 34 points: DONE 20 / STILL THERE 11 / N/A 3.

## 1. Main slides, three lines each

**1 title. FOLLOW.**
- Says: "Do models like Jev get it right when correctness is business-critical?", a harassment-style review, a prompt to judge it fast, Kahneman's System 1, 60 dots with one orange.
- Trying: hook the room with a gut-call review, then name the question.
- Followed: yes. Jev is not defined here, but the hook carries. "Each dot is one of the 60 reviews, and the orange one is this review" is still a meta sentence, though it explains the visual.

**2 answer. PARTIAL.**
- Says: Jev matched the key on all four decisions for 54 of 60, Opus and Sonnet 58 or 59 "at four to forty times the estimated cost". Then "buy a rule that hands the hard reviews to a person."
- Trying: give the verdict first, then the recommendation.
- Followed: the bar chart, hatched gap and 0 to "all 60 reviews" axis are readable. But "Jev", "key", "four decisions", "P0 pass", "OpenRouter repeats", "batch 10" and "rule" are all used before anything explains them (setup is slide 6). "Estimated cost" is price hedging. "Buy a rule" is still the phrase Adam called out.

**3 about. FOLLOW.**
- Says: Adam, Chief AI Strategist at the Academy, Agentics Foundation ambassador, OPEN Talent Society, six years recruiting at Amazon, github.
- Trying: credibility in ten seconds.
- Followed: yes. Orange-backdrop photo, no logo, no talent-intelligence talk.

**4 decision-models. PARTIAL.**
- Says: a decision model takes text and a typed question and returns one of your options with a probability in one pass. Two cards: "System 1 calls" and "System 2 calls".
- Trying: define the category, then split what it is good and bad at.
- Followed: the headline yes. The cards no. "System 2 calls: It reads literally, can't explain itself, and misses questions that don't apply" describes the model's weakness, but the card title reads as if it describes a kind of call. "Typed question" is not shown. System 2 is not defined until slide 12. The bottom third is empty.

**5 launch-wave. PARTIAL.**
- Says: Jev shipped 15 Sep, by 7 Oct Cloudflare, AWS, Perplexity and OpenAI had shipped their own. Timeline with four named launches and unnamed small ticks. 13% of Vercel AI Gateway paid teams.
- Trying: show the category exploded in three weeks.
- Followed: the headline yes. The unnamed ticks are still unnamed: the sentence "Each small tick is another launch... among them Upstage's Solar Decide, Kev..." sits in a mono footnote and does not map names to ticks. Adam's complaint about lines that don't say what was released is still there. Grey mono footnote is a meta caption.

**6 what-we-did. FOLLOW.**
- Says: every model got the same 60 fictional reviews and four questions; matched means all four agree with the key; who wrote the key; P0, P1, P2 defined; 39 setups beside seven decision models and Jev.
- Trying: explain the experiment before showing results.
- Followed: yes. Four question cards with their options is the best setup in the deck. Small flaws: the option lists are tiny mono and run the field name into the options ("concern, harassment, discrimination or a privacy breach; ..., yes, no, can't tell"). "Setups" and "fresh passes" are never defined, and the last sentence is dense.

**7 nine-runs. FOLLOW.**
- Says: Jev matched 52 to 54 of 60, Opus 58 or 59. Five 3x3 grids (P0/P1/P2 columns, three passes as rows), legend for colour, blank and interruption.
- Trying: prove the gap holds in every run.
- Followed: yes. The one unexplained cell is "stopped" in Jev's grid. "A4B, thinking on" is jargon.

**8 pass-cost. FOLLOW.**
- Says: a Jev pass over 60 reviews cost $0.006, an Opus pass about $0.22, so cost is not the constraint. Credit to Jev: it caught all 25 concern reviews, but missed the opening one at 0.49 confidence.
- Trying: cost is cheap either way, the issue is accuracy.
- Followed: yes. "Pass" is only defined here, one slide after it was used four times. Eyebrow says "Proof 1" but cost does not prove the five-review gap.

**9 general-models. LOST.**
- Says: four number lines: Gemini 3.1 Pro 56 and 55 of 60; "On the soup, 89 of 113 general setups answered can't tell on all four fields"; "44 runs from 7 model families gave one identical answer set"; "31 of 50 decision groups never changed an answer, against 11 of 202 general groups".
- Trying: general LLMs agree with each other, effort does not help, and they notice when a review does not apply.
- Followed: only line 1. "The soup" has not been shown yet (slide 11). It is never said that "can't tell" is the correct answer, so 89 of 113 reads as a failure. "Identical to what?" and "groups" are undefined. Line 4 seems to say general models are less stable, which contradicts the headline. Text only, bottom half empty.

**10 consequences. PARTIAL.**
- Says: "Typed output fixes the format. It doesn't fix the decision." Perplexity Decider matched 54 of 60 in all nine runs with the same six misses. Quote about X, Reddit and hiring.
- Trying: a deterministic wrong answer repeats forever, and the cost is employer brand.
- Followed: the point lands. But eyebrow "Why five reviews matter" sits above "six misses", and Perplexity Decider has barely been introduced. The first line is a binary-contrast kicker. No visual for the consequence.

**11 one-of-60. FOLLOW.**
- Says: "Great soup, tiny portions, wouldn't eat there again." Shout it out: seven decision models read this, how many flagged it as off-topic?
- Trying: an audience prediction before the reveal.
- Followed: yes. The orange dot has no label, and here it is a different review than slide 1's orange dot.

**12 zero-of-seven. FOLLOW.**
- Says: 0 of 7 decision models matched the key. Key row is can't tell on all four. Seven cards with answers, Jev's same wrong answer at 0.91, 89 of 113 general setups said can't tell on all four. "Asking 'is this even the right question?' is System 2, and it isn't in the model."
- Trying: show that models answer the form, not the situation.
- Followed: yes, and this is where System 2 finally lands. Problems: every value is orange (match or not), so orange means nothing here; seven unlabelled white dashes top right; "saved answer" on every card; the model makers (Tev, Solar, Liquid) are never introduced on a main slide.

**13 hard-six. PARTIAL.**
- Says: six hard reviews, each with a named reason, key answers under named questions, one tile per model, "x of 7 matched", "y of 1,004 saved passes", plus a miss histogram.
- Trying: the misses are explainable, so a person can be routed to them.
- Followed: the cards are the best "question with every answer" in the deck. But "saved passes" is undefined, which tile is which model is not labelled, tile type is small at 1080p, the "three carry labels a second review of our key disputes" sentence is a knot, and "THE ONE WE OPENED WITH" is a pill.

**14 still-wrong. PARTIAL.**
- Says: Jev's confidence tracked how often it was right, but it was 0.96 confident on a wrong testimonial. Dot chart sorted by confidence with a gate line.
- Trying: confidence cannot tell you which answer to distrust.
- Followed: the headline yes. The chart shows "GATE 0.95" while the labels and paragraph say "0.9 gate keeps 54", and "gate" is only explained in the paragraph under the chart. Axes have tick values but no titles. The legend says orange ring is a wrong answer and red is DEV-027, which is also a wrong answer. "Pooled gap... Descriptive only." is a meta caption. The 0.49 harassment case is referenced but not drawn.

**15 more-instructions. PARTIAL.**
- Says: "The fixes I'd reach for first didn't reliably help." Longer prompt (P0 to P2 stepping down, 15/15/9 and 4/14/21), majority vote, fine-tuning.
- Trying: the usual remedies do not fix it.
- Followed: prompt column yes. Vote column ends on a non sequitur ("so ask a different model instead"). Fine-tuning column ("starts paying off around 200 labels, and we have 9 testimonials") has no evidence on the slide and was not tested, so the headline overclaims. "Clef route may read only about 2,000 state tokens" is an unexplained mono caveat.

**16 agree-or-defer. PARTIAL.**
- Says: run two cheap models that fail differently, accept only when both return the same four answers, send the rest to a person. 58 accepted tiles with Q and G badges, two deferred.
- Trying: show the rule working: zero accepted errors for $0.069.
- Followed: the rule sentence yes. Q and G are explained only in a small mono box ("Qwen 27B low + Gemma 26B thinking on, observed, one draw, other Gemma passes let one error through"). The last sentence talks about 21 pairs, which means the decision-model pairs in appendix A9, not this Qwen and Gemma pair. "A person 2" reads oddly. Headline opens with the fragment "Agree or defer."

**17 queue. PARTIAL.**
- Says: five policy lines, then Solar + Perplexity: 35 of 60 reach a person (25 concern, 10 disagreement or can't tell), 25 auto-accepted. "One model at 0.96, or two cheap models that agree?"
- Trying: show the human cost of the rule.
- Followed: the policy list is clear. The switch from slide 16 is not: slide 16 sends 2 to a person with two general LLMs, slide 17 sends 35 with two decision models, and the text says "two cheap models" then "two typed models". A stranger will ask which is the rule. Solar and Perplexity are not introduced. "Gate on it" is jargon. The show-of-hands question is not answerable from the slide (0.96 is the wrong testimonial from slide 14).

**18 classification-bench. FOLLOW.**
- Says: the tool runs this test on your own cases, labels and questions. Five-step flow, route chips (live vs wired), "being open-sourced", 433 tests, early access.
- Trying: the call to action.
- Followed: yes. "Flips" and "budget held per request" are jargon, the legend ("live", "dashed: wired") is tiny, and "being open-sourced" next to "ask me for early access" is slightly mixed.

**19 monday. FOLLOW.**
- Says: four "I'd" steps, QR to the repo, Reuven's typesafe as a free local classifier, appendix index.
- Trying: close on what to do.
- Followed: yes, best voice in the deck. "A candidate relevance check in front of the four questions" is cryptic. Appendix index lists A1 to A15 but the appendix is labelled A1 to A10 then A13 to A18 (A11 and A12 do not exist, A16 to A18 are not in the list).

Appendix 20 to 34: not scored. Issues are in the flag lists below.

## 2. Flags with slide id

**Terms used before they are explained**
- P0/P1/P2, "pass", "key", "four decisions", OpenRouter, batch 10: slide 2. Defined slide 6 (pass only implicitly on 8, never as "one run through all 60").
- Jev: never given a one-line definition (who made it, what it is) on a main slide.
- System 1 card: slide 4 uses it, slide 1 gives the gut-call idea. System 2: card on slide 4, defined slide 12.
- Soup: used on slide 9 before the review appears on slide 11.
- Gate: label on slide 14 chart before the paragraph; "gate on it" slide 17.
- "Decision groups", "general groups", "identical answer set": slide 9, never defined.
- "Setups", "configurations", "saved passes": slides 6, 9, 12, 13, 15.
- "21 pairs": slide 16 footer, only defined in appendix A9.
- Solar, Tev, Liquid, Luna: named on slide 12 without saying who they are.
- "Flips", "budget held per request", "state tokens", "pooled gap": slides 18, 15, 14.
- Blast radius: not used. ECE: not used on main slides. Good.

**Source footers, feed paths, meta captions, middle dots, replay pills, price hedging**
- Source footers and feed paths: none on slides 1 to 19. Clean.
- Meta captions still there: slide 5 footnote on ticks, slide 14 "Pooled gap... Descriptive only.", slide 15 state-tokens line, slide 16 green box, slide 18 legend, slide 23 "All retrospective...", slide 28 "The rule was fixed before any pair was computed. No pair is selected. Green rail...".
- Meta sentences about the visual: slide 1 "the orange one is this review", slide 8 "the one we opened with", slide 13 pill "THE ONE WE OPENED WITH".
- Middle dots: none on slides 1 to 19. Present in appendix 21 (several), 22, 24, 27, and all hard-review eyebrows 29 to 34 ("A13 · hard review").
- Replay pill: the word is gone. Its twin remains: "saved answer" tag on all seven cards and Jev's panel on slide 12, "saved passes" on 13, "Saved answer, first P0 pass" on 29 to 34.
- Price hedging: slide 2 "estimated cost", slide 8 "about $0.22", slide 16 "$0.069 observed, one draw", slide 20 "Price unverified" and "Price per blog methodology", slide 21 "their price there is unverified".

**Brand motif**
- Logo lockup only on slides 1 and 19. No logo on cards. Good.
- The seven-colour ladder progress bar (purple through red) runs along the bottom of every slide. It is the rainbow again, small. Adam said "overuse of the rainbows". Judgement call for the director.

**Chart ticks and bars without a label**
- Slide 5: the small ticks on the timeline are not named; names are in a footnote.
- Slide 12: seven white dashes top right have no meaning given. All answer values are orange.
- Slide 13: per-model tiles do not say which model is which.
- Slide 14: axes have no titles; gate label 0.95 vs text 0.9.
- Slide 16: Q and G badges explained only in a small box; the orange G on the two deferred rows is not explained.
- Slide 2: white tick marks at bar ends are explained only by the caption line below each bar.

**Answer shown without its question**
- Slide 9 (can't tell on all four fields, soup not shown, correct answer not stated). Everywhere else the question or field label sits with the answer. Slides 12, 13 and 29 to 34 are good.

**Blue on navy or low contrast (by eye)**
- Small grey-blue mono text: option lists on slide 6, footnotes on 5, 14, 15, 16, 18, legend on 7, tile labels on 13, tick labels on 14.
- Medium blue numerals 1 to 5 on slides 17 and 19 are readable but dim.
- No blue-on-dark-blue body text. Headlines and body are white or light grey.

**Kicker fragments that are not full sentences**
- Eyebrow labels on every slide are fragments ("The test", "Proof 3: the number next to the answer", "Why five reviews matter"). Adam's rule is about kickers, so these count.
- Headline fragments: slide 19 "What I'd do on Monday.", slide 16 opens "Agree or defer.", slide 16 "A person 2".
- Binary contrast: slide 10 "Typed output fixes the format. It doesn't fix the decision."
- Voice lane owns the rewrite.

**Other problems a stranger hits**
- Five vs six: eyebrow "the gap is five reviews" (7), "Why five reviews matter" (10), "six misses" (10), "six reviews Jev's first pass missed" (13). Both numbers are right but the room will hear them as one number.
- Slide 16 vs 17 contradiction (2 or 35 to a person, general LLM pair vs decision-model pair).
- Slides 4, 9, 10 leave the bottom third to half empty while slide 13 is packed.
- Slide 28 shows Solar + Perplexity as 24 concern, 4 can't tell, 7 deferred; slide 17 says 25 concern and 10 other. Both add to 35, the split differs. For the consistency lane.

## 3. Adam's 34 points (docs/talk/00-adam-brief.md)

Numbering is mine. 1 to 22 are his slide-by-slide bullets in order. 23 to 34 are the other asks. His old slide numbers do not map one to one to this deck, so where I could not map one I say so.

| # | Point | Status | Slide, note |
|---|---|---|---|
| 1 | Remove source footers everywhere | DONE | none on 1 to 19 |
| 2 | No triangle logo by his name | DONE | 3 |
| 3 | Out-of-context meta comments, "one of 60, the orange point", dots | STILL THERE | 1, 8, 13 pill |
| 4 | "Buy a rule." unclear, sources at bottom | STILL THERE | 2 "buy a rule that hands the hard reviews to a person"; sources gone |
| 5 | Orange image, fuller bio, Chief AI Strategist, Agentics ambassador, no talent intelligence, no rainbows | DONE | 3. Photo has orange backdrop, slide is navy. Ladder bar is a small rainbow |
| 6 | Launch wave: no meta, no sources, explain the lines | STILL THERE | 5 ticks unnamed, footnote caption |
| 7 | Explain experiment, System 1, passes before results; readable colours | STILL THERE | 6 and 4 do it, but 2 shows P0 results first |
| 8 | Price comments not needed | STILL THERE | 2 "estimated", 16 "observed, one draw" |
| 9 | "DEV-029 · one of the 60 · the orange point" | DONE | 11, 30 |
| 10 | Rainbow logo on cards | DONE | no logo on cards |
| 11 | Keys without questions; orange bars mean nothing | DONE | 12, 13 label every field. Slide 12 all-orange values still mean nothing |
| 12 | Lots of slop metacomments | STILL THERE | mono captions on 5, 14, 15, 16, 18. Old slide 10 not mappable |
| 13 | "Agree: accept. Disagree: a person." | DONE | 16 now full sentences |
| 14 | Cringe, mansplaining, not treating audience as adults | DONE | none found on 1 to 19 |
| 15 | Price metacomments ("published when the landscape was checked") | STILL THERE | appendix 20, 21; main slides clean except item 8 |
| 16 | "Makes no sense" (old 17) | N/A | cannot map; nearest still-unclear slides are 9, 16, 17 |
| 17 | "Gap between confidence and hit rate", what gates | STILL THERE | 14 explains gate under the chart, shows 0.95 vs 0.9, keeps "Pooled gap" caption |
| 18 | Pricing section not needed | DONE | cut from main flow; A1 and A2 keep price cards with hedges |
| 19 | Bench is not WIP, already updated | DONE | 18 and 26: 433 tests, being open-sourced |
| 20 | Unclear what 25 to 27 achieve | N/A | cannot map |
| 21 | Metacomments and "replay of saved answers" pills | STILL THERE | no "replay", but "saved answer" tags on 12, 13, 29 to 34 |
| 22 | Interview and hiring-decision stats slide | DONE | no such slide |
| 23 | General-LLM comparison | DONE | 7, 9 (9 is LOST) |
| 24 | Reuse phrases from the old and current site | DONE | "Good luck with building your brilliant startup", "Credit to TypeSafe", soup, "isn't zero on the next 60". Sampled, not checked against 14-phrases.md line by line |
| 25 | Adam voice and anti-slop, no drift | STILL THERE | fragments, binary contrast on 10, 16, 19. Voice lane has the full list |
| 26 | Slides carry the talking points explicitly, information first | STILL THERE | slide 2 before setup, slide 9 cryptic |
| 27 | Animation must not hurt information | N/A | stills only |
| 28 | Engagement questions | DONE | 2, 11, 17 |
| 29 | Fits the screen, no scroll | DONE | nothing clipped at 1920x1080 in all 34. 1366x768 not tested here |
| 30 | Three passes per P0, P1, P2 shown as nine runs | DONE | 7, 22, 27 |
| 31 | Not hallucinating is not deterministic, wider blast radius | DONE | 10. The "at scale" part is implied, not stated |
| 32 | Tricky example questions with explanation | DONE | 13, 29 to 34 |
| 33 | Conclusions, fixes, voting, fine-tuning, ruvector | DONE | 15, 16, 17, 19. Voting only at three passes, fine-tuning has no evidence on slide |
| 34 | Harness near the end, open-sourced, others can run it | DONE | 18, 26, 19 QR |

## 4. What I did not do

- I did not play the deck with fragments or motion; stills of the final reveal state only.
- I did not view appendix slides 22, 24 to 28, 30 to 34 as images.
- I did not compute contrast ratios or test 1366x768.
- I did not verify any number against the site or docs.
