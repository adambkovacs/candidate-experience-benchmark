# 13 Deck review against Adam's brief

Reviewer: Fable, 2026-10-08, with no stake in the deck. Yardstick: `docs/talk/00-adam-brief.md`, Adam's requirements in his own words. Evidence: `public-site/presentation.html` served locally and walked in headless Chromium with every fragment stepped (`public-site/deck/verify/review-capture.mjs`, new). One 1920x1080 jpeg per slide, fully revealed, is in `docs/talk/screenshots/review/01.jpg` to `34.jpg`. The on-screen text quoted below is what the capture read from the DOM in reading order, not what the HTML intends. The deck loaded with zero console errors and every fragment fired.

Also read: the speaker notes inside the deck, `05-session-outline.md` (run of show, slide briefs, notes), the text of `public-site/index.html`, `01-findings-synthesis.md` section 3, `07-remedies.md` section 6, `02-landscape.md` Parts A and E, `03-speaker.md` section 5, and the anti-slop skill, Tier 4 in particular.

## 1. Verdict

The deck does not meet the brief. The numbers, bindings, motion, replay badges, branding and 1080p fit are all in place, but a viewer who is not Adam cannot follow it: fourteen of the fifteen main slides carry a headline that only makes sense once you have read the speaker notes, and the four things Adam asked for most explicitly (what these classifiers are and why they matter, System 1 against System 2, what we did in the benchmark in plain words, and the consequences plus remedies) live only in the notes or in the appendix. The root cause of "wtf do you mean?" is the outline's self-imposed twelve-word cap, which is enforced as a FAIL by `deck/verify/content-audit.mjs` check 4; under that cap the copy was written as advertising kickers ("Buy a rule.", "Jev, 15 September.", "Label 60. Add can't tell. Run two. Count the queue.") instead of sentences with a subject, a verb and a qualifier, so every slide became a cue card for the speaker and a riddle for the room.

Both of the lead's hypotheses hold, and they compound. The cap stripped the context: S2 says "Jev 54 of 60" before any slide has said what the 60 are, what the four questions are, or what "matched" means. The kicker habit then removed the verb: S8 says "0 of 7 decision models." and never says what zero of seven did. The site already has the sentences the slides need (its hero paragraph is the whole answer in 70 words), and the notes already have the talking points in Adam's voice, so this is a content pass, not a rebuild.

## 2. Requirement coverage

Where is from the slide numbers in `screenshots/review/NN.jpg` (NN equals the deck's own 1 to 34). "What a viewer sees" is the captured on-screen text, trimmed.

| Requirement, from 00-adam-brief.md | Where | How well | What a viewer sees there |
|-|-|-|-|
| What classifiers like Jev are (Jev, Decisions API, Clef, Liquid d1, OpenJev, Laya, the launch wave) and why they matter | S4, A1, A2 | Partial, name-dropped | S4: "Jev, 15 September. About two weeks later, everyone shipped one." plus four timeline labels. A1: five price cards. A2: nine Decision Index scores. No slide says what a decision model takes in, what it returns, or what it cannot do. |
| What decisions they are good for: System 1 against System 2, open questions, ambiguity | none on a slide | Missing | The words "System 1", "System 2" and "Kahneman" appear only in the S1 and S8 speaker notes. The site's blurb says the talk is about this. |
| What we did in the benchmark and what we learned | S5, S8, S9, S10, S11 | Partial | S5: "Three prompt versions, three fresh passes, up to nine runs per model." plus the four-question strip and five matrices. No slide says 60 fictional reviews written by AI, checked by people, three disputed, what P0/P1/P2 are, or how many models ran. The site's "The test" section says all of it in four sentences. |
| The tricky examples with explanations | S7, S8, S9, A13 to A18 | Met | S9 shows six reviews with the trigger phrase underlined, a one-line cause, the key and two counters. A13 to A18 show each model's answer. These are the clearest slides in the deck. |
| Consequences: not hallucinating is not deterministic-and-right, blast radius, employer brand | A19 only | Missing from the main deck | The blast-radius evidence is backup slide 34. The "typed output fixes the format, not the decision" and "same wrong answer at scale" lines are in the S6 notes and nowhere on screen. Adam's "good luck building your brilliant startup" line is spoken only. |
| Remedies: majority voting, fine-tuning, multiple runs, alternatives | A12 notes, S11 | Missing from the main deck | S11 covers the longer prompt only. Voting lives in a Q&A answer in the A12 notes. Fine-tuning is not in the deck at all. 07-remedies.md section 6 has the slide-safe lines. |
| The tool at the end, for people to run their own cases with an OpenRouter key or Claude Code / Codex | S14, A8 | Partial | "Runs offline, 433 tests. Two live routes. Being open-sourced." plus a pipeline diagram and five route pills. It never says what the tool does for the viewer ("your inputs, your labels" is a 10px caption) or that it takes an OpenRouter token and coding harnesses. |
| Bio at the start, with Agentics Foundation, OPEN Talent Society, GitHub, what he builds | S3 | Partial | "Adam Kovacs. AI Enablement Academy. Six years Amazon and AWS talent intelligence." The brief's bio names three roles; the slide shows one and no GitHub handle. |
| Engagement questions (raise your hand, shout) | S2 notes, S7 notes, S13 | Partial | Only S13 shows a question on screen ("One model at 0.96, or two cheap models that agree?"). The hands-up on S2 and the shout on S7 are spoken only, which matters on Zoom where half the room is on mute and reading. |
| Fits on the screen, no scrolling, multiple pages | all | Met | Every capture fits 1920x1080 with the source footer visible; fit.mjs covers 1280x720 up. |
| Motion that supports meaning (three.js, GSAP, "do your best") | S1, S2, S4, S5, S8, S9, S10, S12, S13 | Met | The dot field, the flips on S8, the card wall on S9, the gate sweep on S10 and the sorter on S12 each carry one idea. Nothing in this review asks to change them. |
| Replay that feels live | S8, S9, S10, A13 to A18 | Met | Yellow "Replay of saved answers, 2026-10" badge; answers land one at a time. |
| AEA branding | S1, S15, spectrum rail | Met | Logo top-left on the first and last slide, spectrum bar, ladder glyph. |
| Adam's voice | notes yes, slides no | Partial | The notes read like Adam. The slides read like a brand campaign: "Buy a rule.", "Monday:". |
| No slop | Tier 1 and 2 clean; Tier 4 fails | Partial | audit-slop.ts scores 100% because it counts words. Twelve main slides use dramatic fragmentation (pattern 27), and four use rhetorical set-ups or false agency. Section 3 names them per slide. |

## 3. Slide-by-slide audit

Format per slide: on-screen text as captured (trimmed, fragment steps marked +), the intended takeaway from the notes or outline, the gap, the slop patterns by Tier 4 number, a rewrite of the on-slide text in Adam's spoken register, and the lines that should move onto the slide. Bound numbers in the rewrites must keep their existing `data-source` spans; section 6 says how.

### S1 Title (01.jpg)

On screen: "Do models like Jev get it right when correctness is business-critical?" The DEV-059 review card. Caption: "DEV-059 · one of 60 synthetic reviews · the orange point". Byline. Source line.

Takeaway (notes): this is one of 60 candidate reviews; you answered "serious concern" and "follow up" in two seconds; that gut call is what Kahneman calls System 1 and what TypeSafe sells.

Gap: the viewer sees a harassment review and 60 dots, with "the orange point" as the only explanation. Nobody has said what the dots are or why this review is on the title slide. The System 1 framing, which the outline calls the spine of the talk, is not on screen.

Slop: narrator distance (30): "the orange point" asks the viewer to decode a visual instead of being told what it is.

Rewrite (under the title, replacing the caption line): "One of the 60 fictional candidate reviews in this test. Is it a serious concern? Does someone need to follow up? You answered both in about two seconds. That gut call is what the model vendors are selling, and this talk is about how far it carries. Each dot on the right is one review; the orange one is this review."

Move onto the slide: the first three sentences of the S1 notes, condensed as above.

### S2 The answer (02.jpg)

On screen: "THE ANSWER · ALL FOUR DECISIONS MATCHED THE KEY". "Jev 54 of 60. Opus and Sonnet 58 to 59." Bars: "Jev 1.13 DIRECT API, P0 ... 54 ... three OpenRouter passes · 54 · 53 · 52"; "Opus 5.5 HIGH EFFORT, BATCH 10 ... 59 ... three passes · 59 · 58 · 58"; "5 reviews Opus matched and Jev missed". + "Buy a rule."

Takeaway: the whole talk in one frame: the gap is five reviews, cost is 4 to 40 times, most misses were hard reviews, two were plain errors, so buy a rule that hands hard reviews to a person.

Gap: "54 of 60" of what? "The key" has not been defined. "Buy a rule" means nothing until slide 12. The bar label says "direct API" while the passes line says "OpenRouter"; a careful viewer sees a contradiction. Sonnet is in the headline and not in the chart. The hands-up question is spoken only.

Slop: dramatic fragmentation (27) in the headline and the punch; rhetorical set-up (28) in "The answer" as an eyebrow before any question has been posed.

Rewrite. Headline: "On 60 test reviews, Jev matched our reference on all four decisions for 54. Opus and Sonnet matched 58 or 59, at roughly 4 to 40 times the estimated cost." Under the bars: "Matched means all four answers agreed with our provisional reference. It does not mean accurate." Punch line (the fragment): "If the decision matters, buy a rule that hands the hard reviews to a person." Bar labels: "Jev 1.13 · first pass, direct API" and "OpenRouter repeats 54 · 53 · 52". Engagement line, small, bottom: "Hands up if you've shipped an LLM classifier to production. Keep it up if a second model checks it."

Move onto the slide: the site's hero paragraph ("On 60 test reviews, Jev matched our provisional reference on all four decisions for 54. General models, from Gemma 4 26B up to Opus 5.5, matched 58 or 59, for roughly 4 to 40 times the estimated cost of a Jev pass.") and its call-out ("If the decision matters, buy a rule that hands the hard reviews to a person.").

### S3 About me (03.jpg)

On screen: "Adam Kovacs." "AI Enablement Academy." "Six years Amazon and AWS talent intelligence." Footer: repo URL.

Takeaway: this person has read the pile of candidate feedback and was taught to build the measure before trusting the tool.

Gap: the brief's bio has three roles (co-founder and Chief AI Strategist of AEA; co-founding member and International Ambassador of the Agentics Foundation; Executive Director of OPEN Talent Society), the GitHub handle and what he builds. The slide has one role and none of the rest. "Six years Amazon and AWS talent intelligence" is a telegram.

Slop: fragmentation (27): three full-stop fragments.

Rewrite: "I'm Adam Kovacs. Co-founder and Chief AI Strategist at the AI Enablement Academy. Co-founding member of the Agentics Foundation and Executive Director of OPEN Talent Society. Before that, six years at Amazon in recruiting, where I started the talent intelligence service for AWS. I build hands-on AI training for teams, and open benchmarks on recruiting problems. github.com/adambkovacs"

Move onto the slide: 03-speaker.md section 5, all six lines.

### S4 The launch wave (04.jpg)

On screen: "THE LAUNCH WAVE". "Jev, 15 September." "About two weeks later, everyone shipped one." Timeline: "15 Sep Jev 1.13 TypeSafe" + "1 Oct Clef · Strands Decider, Cloudflare and AWS, same day" + "7 Oct Perplexity Decider, listed on OpenRouter" + "6 Oct OpenAI Decisions, public beta". Footnote about grey ticks.

Takeaway: this moved fast and is still moving; credit TypeSafe for publishing a failure-mode page.

Gap: "one" has no antecedent; the viewer does not know what Jev is or what everyone shipped. "Everyone" is hyperbole the footnote then walks back. The credit to TypeSafe, which the outline flags as collegial and important if vendors are in the room, is spoken only.

Slop: fragmentation (27); promotional overstatement (4) in "everyone".

Rewrite. Headline: "Jev shipped on 15 September. Within three weeks Cloudflare, AWS, Perplexity and OpenAI had each shipped a decision model of their own." Lede: "Same idea, and mostly the same wire format: state plus typed questions in, one option out. Credit to TypeSafe: they published a page listing where Jev fails, and almost nobody does that."

Move onto the slide: S4 notes, sentences 2 and 4. The timeline stays as it is.

### S5 Five reviews, up to nine runs each (05.jpg)

On screen: "PROOF 1 · THE GAP IS FIVE REVIEWS". "Three prompt versions, three fresh passes, up to nine runs per model." Four question cards with their label vocabularies. Five matrices (Jev 54, Opus 59, Sonnet 58, Gemma 59, Qwen 59) with the nine cells each. Legend. Source line.

Takeaway: every model got the same 60 reviews and the same four questions; AI drafted the reviews and the key, people checked them, three labels disputed; Jev 54, 53, 52; Opus 59, 58, 58; Sonnet 58 nine times; Gemma and Qwen 59.

Gap: this is the deck's "what we did" slide and it never says what was done. The headline is the design of the experiment with no subject. "P0 P1 P2" and "fresh pass" are undefined. The provenance of the 60 reviews and the key (AI-drafted, people-checked, three disputed), which pre-empts the hostile question the outline worries about, is in the notes only. The four question cards are good and should stay.

Slop: none lexically; the headline is a noun phrase, which is fragmentation (27) in a quieter form.

Rewrite. Headline: "Every model got the same 60 reviews and the same four questions. Most ran three prompt versions, three fresh passes each: nine runs. A blank cell means that run doesn't exist." Caption above the matrices: "P0 is the plain question. P1 adds classifier framing. P2 adds a full decision tree. Rows are fresh passes." Under the matrices: "Jev matched all four on 54, 53 and 52 of 60. Opus 5.5 matched 59, 58, 58. Sonnet 58 nine times. A 26B open-weight Gemma and a 27B Qwen each matched 59 on their first pass." If section 4's new "what we did" slide is added, the provenance line moves there; otherwise add here: "An AI assistant drafted the reviews and the answer key. People checked all 60. Three labels are still disputed, so I call the key provisional."

Move onto the slide: S5 notes paragraphs 2 and 3; the site's "A review counts as matched only when all four answers agree with the reference."

### S6 What a pass cost (06.jpg)

On screen: "WHAT A PASS COST · 60 REVIEWS, ONE PASS". Two cards: "Jev · OPENROUTER P0 PASS $0.006 known charge, billed by the provider" and "Opus 5.5 high · BATCH 10 $0.22 estimate, API-equivalent, not a bill".

Takeaway (notes, the longest paragraph in the deck): 4 to 40 times the spend for five more matches; Jev caught all 25 serious concerns and still said no follow-up on the harassment review at 0.49; typed output means no made-up labels but the same wrong answer at scale with no variance to warn you; the candidate tells X and Reddit; good luck hiring.

Gap: the slide shows two prices and nothing else, while the notes carry four of the talk's most important claims, including the whole consequences argument Adam asked about. Half the slide is empty.

Slop: wh- fragment (32) as the eyebrow. Otherwise the slide has too little text to be slop.

Rewrite. Headline: "A Jev pass over all 60 reviews cost about six tenths of a cent, billed by the provider. The Opus pass cost about 22 cents, an API-equivalent estimate. Four to forty times the spend for five more matches. Cost is not the constraint." Under the cards, two lines: "Credit where it's due: Jev caught all 25 reviews the key flags as a serious concern." "On the one we opened with, it said nobody needed to follow up, at 0.49 confidence." The deterministic-wrong and blast-radius claims go to the new consequences slide (section 4).

Move onto the slide: S6 notes paragraph 1 and the first two sentences of paragraph 2; the site's finding 1 cost sentences.

### S7 One of the 60 (07.jpg)

On screen: "Great soup, tiny portions, wouldn't eat there again." "DEV-029 · ONE OF THE 60 · THE ORANGE POINT". Dot field with one orange dot.

Takeaway: another one of the 60; seven purpose-built decision models saw it; shout how many flagged it as off-topic.

Gap: the slide holds while the room shouts, which is right, but the question is spoken only. Over Zoom the muted half of the room needs it on screen. "The orange point" again.

Slop: narrator distance (30) in the caption.

Rewrite. Keep the quote at full size. Replace the caption with: "Another one of the 60. Seven purpose-built decision models read it. Shout: how many of the seven flagged it as off-topic?"

Move onto the slide: S7 notes, sentence 3.

### S8 Zero of seven (08.jpg)

On screen: "PROOF 2 · SEVEN DECISION MODELS, ONE REVIEW". The soup text. Key row: can't tell on all four. Seven cards, each with four answers, orange where they differ. + replay badge + "0 of 7 decision models." + "JEV 1.13 · NOT IN THE SEVEN · SAVED P0 ANSWER mixed no no no. No serious concern, at 0.91 confidence." + "89 of 113 general configurations: can't tell."

Takeaway: zero of seven matched; four said mixed, Solar negative, Liquid and Perplexity can't tell on sentiment but still "no" on the others; Jev the same at 0.91; 89 of 113 general configurations said can't tell on all four; the classifier answered the question on the form and did not notice the form did not apply, which is the System 2 move.

Gap: "0 of 7 decision models." has no verb. The System 2 line, which is the point of proof 2 and of the talk's blurb, is spoken only. "89 of 113 general configurations: can't tell" reads as if the general models failed; the viewer needs "answered can't tell, which the key wanted".

Slop: fragmentation (27) in the headline.

Rewrite. Headline: "0 of 7 noticed the review wasn't about hiring. The key wanted can't tell on all four." Jev box: "Jev isn't one of the seven. Its saved answer was the same: mixed, no, no, no. It said no serious concern at 0.91 confidence." General line: "89 of the 113 general-model configurations with a valid answer said can't tell on all four. The bigger models noticed." Bottom line, after the second click: "The model answered the question on the form. It didn't notice the form didn't apply. That slower check, 'wait, is this even the right question?', is what Kahneman calls System 2, and it isn't in the model."

Move onto the slide: S8 notes paragraph 2 in full; 07-remedies.md section 6 line 7 ("Ask 'is this even about hiring?' before you ask the four questions.") fits as the bottom line's second sentence.

### S9 Six reviews worth pausing on (09.jpg)

On screen: "PROOF 2 · THE SOUP HAS COMPANY". "Six reviews worth pausing on." Histogram inset "All 60 reviews by how many of the 7 decision models missed". Six cards (DEV-030, 029, 006, 013, 027, 059) with the trigger phrase underlined, a cause label, the key, seven tiles, and the two counters. "THE ONE WE OPENED WITH" tag on DEV-059.

Takeaway: the misses were not random; each hard review is hard for a nameable reason; three carry disputed labels; you can route reviews like these to a person.

Gap: this is the best slide in the deck and needs the least. The headline is still a fragment, and the conclusion ("the misses weren't random, so you can route them") is spoken only. The "of 1,004 run-passes" counter is unexplained on screen (it is the number of all saved passes across all models that matched this review).

Slop: false agency (29) in the eyebrow ("the soup has company"); fragmentation (27) in the headline.

Rewrite. Eyebrow: "Proof 2 · the soup is not alone". Headline: "The misses weren't random. Six reviews a person would pause on, and the reason each one is hard." Under the histogram or as a footer line: "Three of the six carry labels a second review of our key disputes. Five of Jev's six misses are in this set. That's good news: reviews like these can be routed to a person." Counter label: "of 1,004 saved passes, all models" instead of "run-passes".

Move onto the slide: the site's finding 2 sentence "Six reviews split four or more of the seven decision models. Three of them carry disputed reference labels. Five of Jev's six misses are in this set." and the last sentence of the S9 notes.

### S10 0.96 and still wrong (10.jpg)

On screen: replay badge. "PROOF 3 · THE NUMBER NEXT TO THE ANSWER". "Close to its hit rate here. Still 0.96 on a wrong testimonial." Chart label "JEV 1.13 P0 · TESTIMONIAL FIELD · 60 ANSWERS SORTED BY CONFIDENCE", gate 0.95, dots, "0.9 gate keeps 54 of 60", "0.7 keeps 58", "0.5 keeps 58", call-outs for DEV-027 (0.96, key says testimonial) and DEV-029 (0.88, key can't tell), legend, footnote "Pooled gap between confidence and hit rate on these 60 reviews, 720 answers: Jev 0.011, Clef Flash 0.358. Descriptive only."

Takeaway: Jev's confidence tracks how often it is right on average (gap 0.011 against Clef Flash 0.358), it was still 0.96 on a wrong testimonial, a 0.9 gate on sentiment threw away nine good answers to catch four bad ones, the gate would have caught the 0.49 harassment miss, seven of its ten least-confident reviews are among the ten hardest, so the number says "hard", not "which answer to distrust".

Gap: "its hit rate" has no antecedent on screen, and "hit rate" is jargon for "how often it was right". The chart is strong but the conclusion (the number flags hard reviews, not wrong answers; calibrated on average is not right on this review) is spoken only. The fairness point (the gate would catch the 0.49 miss) is spoken only.

Slop: fragmentation (27); dangling pronoun.

Rewrite. Headline: "On these 60 reviews Jev's confidence tracked how often it was right. It was still 0.96 confident on a wrong testimonial." Under the chart: "A 0.9 gate keeps 54 of 60 on this field and keeps the wrong one. The same gate would have caught the harassment follow-up miss at 0.49. The score can tell you a review is hard. It can't tell you which answer to distrust." Footnote stays, with "hit rate" changed to "how often it was right".

Move onto the slide: the site's finding 3 paragraph; 07-remedies.md section 6 line 8 ("Calibrated on average doesn't mean right on this review.").

### S11 More instructions, no reliable gain (11.jpg)

On screen: "PROOF 3 · THE OTHER FIX". "More instructions, no reliable gain." Clef stairs 54 plain, 51 framing, 49 tree. "39 SAVED SETUPS · IN THESE SAVED RUNS". "Plain to framing 15 up · 15 same · 9 down". "Framing to tree 4 up · 14 same · 21 down". Clef 2,000-token footnote.

Takeaway: the longer prompt was the fix Adam would reach for first and it was the one to trust least.

Gap: "plain", "framing" and "tree" are undefined; the viewer does not know these are prompt versions P0, P1, P2. "The other fix" implies a first fix that no slide named. Majority voting and fine-tuning, which Adam explicitly asked for, are missing. This slide is where they belong.

Slop: fragmentation (27); rhetorical set-up (28) in the eyebrow.

Rewrite (extend to three columns, see section 4). Headline: "The fixes I'd reach for first didn't reliably help." Column 1, longer prompt: "P0 is the plain question, P1 adds classifier framing, P2 adds a full decision tree. Across 39 saved setups, framing scored higher in 15, the same in 15, lower in 9. The tree on top: higher in 4, the same in 14, lower in 21. Clef went 54, 51, 49 in every pass." Column 2, majority vote: "I voted Jev's three passes. The majority never beat its best single pass: 54 in five conditions, 53 in one. Across 145 clean general-model groups a vote of three added 0.14 matched reviews per 60." Column 3, fine-tuning and a second opinion: "Fine-tuning starts paying off around 200 labels per class in the published work. We have 9 testimonials. And when two models are both wrong they pick the same wrong answer about 60% of the time, so the second call goes to a different model, not a second sample of the same one."

Move onto the slide: S11 notes; A12 notes (the voting answer, Q&A 20); 07-remedies.md section 6 lines 5 and 6 and the held-for-Q&A fine-tuning line (Bucher and Martini 2024). The voting numbers are in `docs/talk/scripts/s13_majority_vote.py` and need a feed or a `data-doc` binding before they go on screen.

### S12 Agree or defer (12.jpg)

On screen: "THE RULE · AGREE OR DEFER". "Two cheap models. Agree: accept. Disagree: a person." Sixty cards. + "Accepted 53 · 0 disagreed with the key", "A person 7", "S + P · Solar Decide + Perplexity Decider · $0.037 known charge, both runs", tags (soup, train testimonial, disputed key). + "Accepted 58 · 0 disagreed with the key", "A person 2", "Q + G · Qwen 27B low + Gemma 26B thinking on · $0.069 observed, one draw".

Takeaway: the rule in one sentence; Solar + Perplexity is an example picked after seeing all 21 pairs; five pairs had zero errors; six pairs accepted the soup with the same wrong answer; agreement only helps when the models fail differently; Qwen + Gemma did it with general models.

Gap: the headline is the textbook Tier 4 fragment and still does not say what "agree" is about (four identical answers). "Disagreed with the key" uses "the key" with no definition on the slide. The two caveats that keep this honest (example not winner; zero on these 60 is not zero on the next 60; six pairs agreed on the wrong soup answer) are spoken only.

Slop: dramatic fragmentation (27), in its purest form in the deck.

Rewrite. Headline: "Agree or defer. Run two cheap models that fail differently. Accept a review only when both give the same four answers. Send the rest to a person." State A caption: "Solar Decide + Perplexity Decider: 53 accepted, 0 of them wrong against the key, 7 to a person, $0.037 for both runs. An example, not a winner: I picked it after seeing all 21 pairs, and five of them let zero errors through." State B caption: "Qwen 27B low + Gemma 26B thinking on: 58 accepted, 0 wrong, 2 to a person, about 7 cents observed, from one draw. Other Gemma passes let one error through." Footer line: "Zero errors on these 60 is not zero on the next 60. Six of the 21 pairs accepted the soup with the same wrong answer, so pick two models that fail differently."

Move onto the slide: the site's rule paragraph ("Agree or defer. Run two cheap models that fail differently. Accept a review only when both return the same four answers. Send the rest to a person.") and its caveat ("None of these pairs is a recommended production setup."); S12 notes paragraphs 2 to 4.

### S13 The policy and the queue (13.jpg)

On screen: "THE RULE · THE POLICY AND THE QUEUE". Five lines: "Two typed models on every review." "Accept only identical four-field answers." "Serious concern from either model: a person." "Can't tell from either model: a person." "Log confidence; don't gate on it." Right: "SOLAR + PERPLEXITY, ALL 60 REVIEWS · 35 REACH A PERSON", bands 25 / 25 / 10. + "One model at 0.96, or two cheap models that agree?"

Takeaway: the rule decides what a model may auto-accept; the escalation lines are the workflow; 35 of 60 reach a person on this set; the set is concern-heavy by design.

Gap: smallest gap in the main deck. The policy lines are clipped but readable. What is missing is the sentence that stops a CTO reading "35 of 60 go to a person" as a failure: that queue is the price of zero accepted errors, and the set is concern-heavy by design. The closing question is the one engagement prompt on screen, and it works.

Slop: light fragmentation (27) in lines 3 and 4 (colon pairs).

Rewrite. Policy: "1 Run two typed models on every review. 2 Auto-accept only when all four answers are identical. 3 If either model flags a serious concern, a person reads it, whatever else the two agree on. 4 If either says can't tell, a person reads it. 5 Log the confidence score. Don't gate on it." Queue caption: "Solar + Perplexity on all 60: 35 reach a person. 25 for a flagged concern, 10 for disagreement or can't tell. That queue is the price of zero accepted errors on this set, and the set is concern-heavy by design." Question stays.

Move onto the slide: the site's "35 of 60 reviews reach a person under the full policy" paragraph.

### S14 classification-bench (14.jpg)

On screen: "THE TOOL · CLASSIFICATION-BENCH". "Runs offline, 433 tests. Two live routes. Being open-sourced." Pipeline: Bring data (your inputs, your labels), Plan, Run (budget held per request), Evaluate (agreement, flips), Report. Routes: OpenRouter, Cloudflare Clef (green), Claude Code, Codex, Liquid / Solar / Qwen (amber). Legend. "BEING OPEN-SOURCED" badge.

Takeaway: this benchmark taught me what a runner has to do; classification-bench does that for your inputs and your labels; where it stands honestly; ask for early access.

Gap: the headline is a status report with no subject; "433 tests" means nothing to the room. The brief's own description of the tool (give it an OpenRouter API token for any model, or Claude Code or Codex for Anthropic and OpenAI models, bring your own inputs and the decisions you want made, same functionality as the demo) is not on the slide. The pipeline labels are 10px captions.

Slop: fragmentation (27).

Rewrite. Headline: "classification-bench: run this test on your own cases. Your inputs, your labels, your questions. Any model through an OpenRouter key, or Claude Code and Codex on the subscription you already have." Under the pipeline: "It counts missing answers, rejects broken formats, keeps your labels away from the model, records what every request cost, and runs each setup more than once, then reports agreement and how often an answer flips between repeats." Status line: "Today it runs offline with 433 tests and has made small live calls through OpenRouter and Cloudflare's Clef. The Claude Code and Codex routes are built, not yet run live. Being open-sourced. Ask me for early access."

Move onto the slide: S14 notes in full; the brief's own sentence about the tool; the site's "classification-bench, the tool that ran these tests, is being open-sourced. Ask Adam for early access."

### S15 Monday (15.jpg)

On screen: logo. "Monday:" "Label 60." "Add can't tell." "Run two." "Count the queue." QR code and URL. Appendix index A1 to A19. Source line.

Takeaway: a four-step recipe you can do on Monday; star the repo; every scored answer is public.

Gap: the four lines are unreadable without the notes. "Label 60" (sixty what, labelled by whom, before what?), "Run two" (two what?), "Count the queue" (which queue?). This is the slide the audience photographs, and it carries the least information in the deck. The appendix index is useful for Adam and noise for the room; it can shrink to one line.

Slop: dramatic fragmentation (27), the deck's worst case.

Rewrite. Headline: "What I'd do on Monday." Steps: "1 Pull 60 of your own cases and label them yourself, before any model sees them. 2 Give every question a can't-tell option. 3 Run two cheap models and keep only the answers they agree on. 4 Count how many land in the human queue, and whether the rare cases you care about got through." Footer: "Every scored answer is in the public repo. Star it, and ask me for early access to classification-bench." Appendix index: keep as one grey line "Appendix A1 to A19 for questions: press down."

Move onto the slide: S15 notes, sentences 2 to 6, verbatim.

### A1 Hosted decision models (16.jpg)

On screen: five cards with per-million prices and bullets (Jev $0.042, Decisions on gpt-6-luna $0.10, Perplexity Decider $0.02, Liquid d1 $0.04, Solar Decide beta). Footnote on pricing.

Takeaway: the hosted landscape at a glance.

Gap: nothing explains what a hosted decision model is; the slide assumes S4 did, and S4 did not. Half the slide is empty.

Slop: none.

Rewrite. Add a lede under the headline: "All five take the same input: a state (your text) plus typed questions with the options you supply. All five return one option per question with a probability, in one pass, with no text to parse. Output tokens are free because there are none." Keep the cards.

Move onto the slide: 02-landscape.md A1, first paragraph, and the "No output tokens" bullet.

### A2 Open-weight decision models (17.jpg)

On screen: nine bars with Decision Index scores, Jev at 57.91 for reference, self-reported flags. Footnote.

Takeaway: the open-weight followers, on one shared yardstick, labelled where self-reported.

Gap: no sentence says what the Decision Index is or that every follower is a frozen Qwen or Gemma backbone with a small head. The brief asked "what are these". Fine as a backup once that sentence exists.

Slop: none.

Rewrite. Lede: "Every open follower is a frozen Qwen or Gemma backbone with a small head or adapter that scores the option logits in one pass. Together trained Tev1 for about $17. The Decision Index is a community benchmark; scores marked self-reported are the vendor's own." Keep the bars.

Move onto the slide: 02-landscape.md A4, point 2.

### A3 Prompt levels (18.jpg)

On screen: five matrices (Jev, Clef, Luna, Clef Flash, Solar), legend, three tally rows (15/15/9, 7/16/16, 4/14/21), footnote on the tree pushing decision models to can't tell and the Clef 2,000-token limit.

Gap: "P0, P1, P2" undefined here too. Add the one-line definition from the S5 rewrite. Otherwise stands.

Slop: none.

### A4 Confidence and calibration (19.jpg)

On screen: calibration gap table for seven models, the Jev gate table per field, "7 of Jev's 10 least-confident reviews are among the 10 hardest", the Clef Flash 1,192 of 2,156 line, "All retrospective" footnote.

Gap: none for a backup; the table's "Hard 10 in least-confident 10" column is dense but a Q&A slide may be. The HTML defaults that column to 0 for every row and the data layer binds it to 7, 2, 4, 5, 3, 4, 4; the capture and the screenshot show the bound values.

Slop: none. Stands.

### A5 Who wrote the key (20.jpg)

On screen: four facts (OpenAI assistant drafted the 60 and the key; people checked all 60 on 2 October 2026; a separate AI review disputes DEV-006, DEV-013, DEV-030; frozen v0.2, provisional), two histograms (flip DEV-006 alone: 168 down, 257 same, 212 up; flip all three: minus 3 to plus 3).

Gap: none. This is explicit and honest. Stands.

### A6 Cost, seven decision models (21.jpg)

On screen: table of seven known charges, $1.2013 for all nine runs, up to $0.13 unknown, Gemini low 56 at $0.063 against high 55 at $0.257.

Gap: none. Stands.

### A7 Limits (22.jpg)

On screen: seven limits as bold lead-ins ("Not a leaderboard.", "Not causal." ...).

Gap: none in content. The form is negative listing (26) and bold-lead-in bullets (15), which the anti-slop skill flags; for a limits slide the negative form is the honest one and I would leave it. Optional softening: "This is not a leaderboard, because runs differ in route, batch size, effort and prompt."

### A8 classification-bench detail (23.jpg)

On screen: three cards (Works, Wired not live, Not built), "being open-sourced", "Release date not set."

Gap: none. This is the honest status Adam's brief asked for ("the repo is still work in progress"). Stands.

### A9 Equal scores hide different answers (24.jpg)

On screen: Sonnet and Perplexity matrices (58 and 54 in every cell), three stats (58 in every cell yet changed DEV-006 and DEV-030; 31 of 50 decision groups changed nothing; 11 of 202 general groups).

Gap: the sentence that turns this into the consequence Adam asked about ("a deterministic wrong answer is wrong every single time, and there's no variance to warn you") is in the notes. Put it on the slide; it also feeds the new consequences slide.

Slop: mild false agency (29) in the headline; acceptable.

Rewrite. Add under the stats: "Perplexity Decider matched 54 of 60 in all nine runs with the same six misses every time. A deterministic wrong answer is wrong every single time, and there's no variance to warn you."

### A10 All 21 pairs (25.jpg)

On screen: the full table, five zero-error pairs with a green rail, six "soup accepted" tags, the 32 to 42 range, the Solar + Perplexity routing line, the caveat footer.

Gap: none. Stands. The best Q&A slide in the deck.

### A11 Rare classes (26.jpg)

On screen: testimonial 9 yes / 50 no / 1 can't tell; all-no scores 50 of 60; Tev 9 of 9 recall and 12 called; Luna 6 of 9 with no false calls; the three percentage ranges for reference can't-tell cells.

Gap: "the can't-tell collapse" in the headline is in-house jargon. Rewrite headline: "Rare classes, and what happens to can't tell." Otherwise stands.

### A12 General-model agreement (27.jpg)

On screen: 853 costed pairs; 58/0/2 Qwen + Gemma at $0.0685; 55/0 Gemma 31B + DeepSeek Flash at $0.0207; 35 pairs matched or beat Solar + Perplexity; 9 wrong answers Qwen 35B agreed on with itself; 44 run-passes from 7 models share one answer set; 3 reviews where it differs.

Gap: "frontier convergence" in the headline is jargon. Rewrite headline: "The same rule with general models, and why a second frontier model is a weak check." Otherwise stands.

### A13 to A18 Hard reviews (28.jpg to 33.jpg)

On screen: the review with the trigger phrase underlined, the key row, seven model rows with each field, orange where it differs, a MISS or match tag, the "N of 7 matched all four" footer, replay badge.

Gap: none. These six are the model for how the main deck should read: a full sentence of context, the exact data, the key, and the verdict. One nit: the footer text before the replay lands reads "0 of 7" on every one of the six (the DOM default) and then binds to the right count; A15 binds to 1, A16 to 2, A17 to 3, A18 to 5, as the screenshots confirm.

### A19 Blast radius (34.jpg)

On screen: six evidence cards (14% resent, 25% in tech; £4.4M Virgin Media; 26% trust AI; 71% oppose AI final call; $365,000 EEOC; 30 s AI interviewer loop, two million TikTok views), each with its source.

Gap: this is the consequences evidence Adam asked for, parked in the appendix behind the Q&A. Two of the cards (14% / 25% and 26%) should also appear on the new main-deck consequences slide with Adam's line. The full slide stays as backup.

## 4. Structure verdict

The 15 plus 19 split is right in shape: one answer, three proofs, one rule, one call to action, with the detail behind. The problem is what the 15 carry, not how many there are. Two slides are missing and two beats are under-served.

Missing slide, after S3: what a decision model is, and System 1 against System 2. The talk's blurb promises it, the outline calls it the spine, and no slide shows it. Content from 02-landscape.md Part A: a decision model takes your text plus typed questions, returns one of your options with a probability in one pass, cannot invent a label, cannot explain, reads literally; two columns of what suits System 1 (closed label set, clear rubric, one factor per question, high volume) against what needs System 2 (ambiguity, off-topic input, several factors at once, anything that needs an explanation). About 50 spoken words, 20 seconds.

Missing slide, before proof 1: what we did, in plain words. The site's "The test" section is the copy: 60 short fictional reviews, four questions with their meaning (the "serious concern" definition matters: harassment, discrimination or a privacy breach, not every bad experience), matched means all four agree, AI drafted the reviews and the key, people checked, three disputed, three prompt versions P0/P1/P2 and three fresh passes, seven purpose-built decision models plus general LLMs from a 0.6B local model to Opus 5.5, every saved answer public. The brief's "about 40 models" needs a bound count before it goes on a slide; the deck has no feed for it, and the outline never states one. The spoken words already exist in beat 4 (the "Every model got the same 60 reviews" paragraph) and move here, so this slide costs no time.

Under-served beat: consequences. Add one main slide after the cost slide: "Typed output fixes the format. It doesn't fix the decision." with the deterministic-wrong line from A9, Adam's blast-radius line, and two cards lifted from A19 (14% resentment, 25% in tech; 26% trust AI to evaluate them fairly). The spoken words already exist in beat 4 paragraph 2, so this is a reallocation, about 10 seconds for the build.

Under-served beat: remedies. Extend S11 to three columns (longer prompt, majority vote, fine-tuning and a second opinion) as written in section 3. About 40 new spoken words.

Merges: none required. The cost slide (S6) could fold into proof 1 as a strip under the matrices, but S5 is already the densest slide in the deck and the two-card motion is clean; leave it and give it sentences.

Landscape: name-dropped, not explained. S4 shows four names on a line; A1 and A2 show prices and scores. The brief asked "what are these, why this matters, what are they good for". The new decision-model slide covers "what" and "good for"; one lede sentence on A1 and A2 covers the rest. The "OpenJev, Senf, Laya, Kev" roll-call Adam listed is in 02-landscape.md B8 to B14 and does not need a main slide; the "why it matters" is the launch wave plus the Vercel adoption number (13% of paid AI Gateway teams within 24 hours, 02-landscape A4), which is a strong one-liner for S4 if a `data-doc` binding is added.

Resulting main deck: 17 slides. S1 title, S2 answer, S3 bio, S4 decision models and System 1/2 (new), S5 launch wave, S6 what we did (new), S7 proof 1 matrices, S8 cost, S9 consequences (new, replaces nothing), S10 soup, S11 zero of seven, S12 six reviews, S13 confidence, S14 fixes that didn't (extended), S15 rule, S16 queue, S17 tool and Monday merged, or keep S17 the tool and S18 Monday for 18. Time: about 90 new spoken words plus three builds, roughly 50 seconds, against a measured buffer of 1:10. The hard-stop line at the rule slide stays.

## 5. Explicit talking points per main slide, in Adam's voice

One or two sentences each, derived from the notes, written to sit on the slide as the line the viewer reads while Adam says the rest.

S1 Title: "This is one of 60 candidate reviews. You answered 'serious concern, follow up' in two seconds. That gut call is what these models sell, and I wanted to know how far it carries."

S2 The answer: "On 60 reviews Jev matched our reference on 54. Opus and Sonnet matched 58 or 59 for four to forty times the money. If the decision matters, buy a rule that hands the hard ones to a person."

S3 About me: "I've read the pile of candidate feedback. Vendors kept telling me their classifier was accurate, and Amazon taught me to build the measure before trusting the tool."

S4 What a decision model is (new): "You give it text and a typed question with your options. It gives you one option back, with a probability, in one pass. It can't invent a label and it can't explain itself. That's System 1. The 'wait, is this even the right question?' check is System 2, and you still have to build it."

S5 Launch wave: "Jev shipped on 15 September. Three weeks later Cloudflare, AWS, Perplexity and OpenAI had each shipped one. Credit to TypeSafe for publishing where Jev fails; almost nobody does."

S6 What we did (new): "Sixty fictional reviews, four questions each, three prompt versions, three fresh passes, seven purpose-built decision models and general LLMs up to Opus. AI drafted the reviews and the key, people checked all 60, three labels are still disputed. Every saved answer is public."

S7 Proof 1: "The gap is five reviews, and it held across the runs that exist: Jev 54, 53, 52; Opus 59, 58, 58; Sonnet 58 nine times."

S8 Cost: "Six tenths of a cent a pass against twenty-two cents. Cost isn't the constraint. And credit where it's due: Jev caught all 25 serious concerns, then said nobody needed to follow up on the one I read you."

S9 Consequences (new): "Typed output fixes the format. It doesn't fix the decision. These models give the same answer every time, so a wrong answer is the same wrong answer at scale with no variance to warn you. Miss that report and the candidate tells X and Reddit. Good luck hiring after that."

S10 Soup: "Seven purpose-built decision models read this. Shout how many flagged it as off-topic."

S11 Zero of seven: "None. They answered the question on the form and didn't notice the form didn't apply. The bigger general models mostly did: 89 of 113 said can't tell."

S12 Six reviews: "The misses weren't random. Each of these is hard for a reason you can name, and three of them are labels our own second review disputes. That's good news, because you can route them."

S13 Confidence: "Jev's confidence tracks how often it's right on average, and it was still 0.96 on a wrong testimonial. The number tells you a review is hard. It can't tell you which answer to distrust."

S14 Fixes that didn't: "A longer prompt made 21 of 39 setups worse. Voting Jev three times never beat its best pass. Fine-tuning wants about 200 labels per class and we have nine testimonials. The second opinion has to come from a different model."

S15 Rule: "Two cheap models that fail differently. Accept only when all four answers match. Send the rest to a person. Solar plus Perplexity: 53 accepted, zero wrong, seven to a person, under four cents for both."

S16 Queue: "Thirty-five of sixty reach a person on this set, 25 of them because a concern was flagged. That queue is the price of zero accepted errors. Hands up for one model at 0.96. Hands up for two cheap models that agree."

S17 The tool: "classification-bench runs this test on your cases: your inputs, your labels, any model through an OpenRouter key or Claude Code and Codex. It runs offline today, two routes have gone live, and we're open-sourcing it."

S18 Monday: "Label 60 of your own cases yourself. Give every question a can't-tell option. Run two cheap models and keep what they agree on. Count the queue, and check the rare cases got through."

## 6. Rework plan for the Opus content pass

Ordered by impact. Target ids are the current `section id` values in `presentation.html`. "Keep" means the motion component, its `data-c` hook and every `data-source`, `data-count`, `data-deck-source` and `data-doc` binding stay exactly as they are; new text wraps the existing bound span rather than replacing it.

1. Revoke the twelve-word rule in `public-site/deck/verify/content-audit.mjs` check 4: raise the `[data-copy]` cap to 70 words per main slide, keep the report. Update the comment at line 7. Without this the audit fails every rewrite below. Also note check 3: the main deck's notes must equal `05-session-outline.md` section 2b verbatim, so every notes change below lands in the outline first.

2. `#answer` (S2): replace the h2 with the two-sentence headline from section 3, keeping the four `d-num` spans. Replace "Buy a rule." with the site's call-out sentence. Add the "Matched means..." line as a `c-foot`. Fix the Jev bar label and passes line so both say which route they are. Add the hands-up prompt as a small line. Quote to use: "On 60 test reviews, Jev matched our provisional reference on all four decisions for 54." and "If the decision matters, buy a rule that hands the hard reviews to a person."

3. New slide after `#about`: `#decision-models`. Static two-column layout, no new motion; reuse `c-grid2` and `c-list`. Text from section 3 (S4 rewrite in section 4's description) and 02-landscape.md A1 and A3. Add notes (about 50 words) to the outline as a new beat 2b and to the deck. Add the slide to `BEATS` in content-audit.mjs and bump `MAIN`.

4. New slide before `#nine-runs`: `#what-we-did`. Reuse the four question cards from S5 (move them here, they are static) and add the site's "The test" sentences. Bind 60 to `disputed-reviews-v1.json#review_denominator`, 7 to `model_denominator`, 25 to the serious-concern count already bound on `#queue`. Do not write "about 40 models" unless a feed gives the count; `data.json` or `extended-run-catalog-v1.json` may, otherwise say "seven purpose-built decision models and general LLMs from a 0.6B local build up to Opus 5.5". Move beat 4 paragraph 2 of the notes here.

5. `#nine-runs` (S5, proof 1): new headline and the P0/P1/P2 caption from section 3. Keep all five matrices and the legend. If the question cards moved to the new slide, the freed height takes the three-line result sentence.

6. `#pass-cost` (S6): headline sentence and the two credit lines from section 3. Keep the two cards and the stagger. Bind 25 to the same source as `#queue`'s concern count and 0.49 to `jev-confidence-findings.json` (DEV-059 follow-up confidence; the outline cites it, the deck does not yet bind it).

7. New slide after `#pass-cost`: `#consequences`. Headline "Typed output fixes the format. It doesn't fix the decision." Two evidence cards copied from `#a19-blast-radius` with their `data-doc` bindings (14% / 25%, 26%), the A9 deterministic line with its Perplexity 54-in-nine binding, and Adam's blast-radius line verbatim from 07-remedies.md section 6 line 4. Notes: beat 4 paragraph 2, sentences 3 to 6, move here.

8. `#one-of-60` (S7): replace the cite with the shout prompt. Keep the quote and the scene.

9. `#zero-of-seven` (S8): headline, Jev box text, general line and the System 2 bottom line from section 3. Keep the flip component, the pips and both fragments. The bottom line reveals on the second click.

10. `#hard-six` (S9): eyebrow, headline, footer sentence and counter label from section 3. Keep the wall, the histogram and the six fragments.

11. `#still-wrong` (S10): headline and the four-sentence conclusion under the chart; change "hit rate" to "how often it was right" in the footnote. Keep the gate component, callouts and the fragment. Bind 0.49 as in item 6.

12. `#more-instructions` (S11): headline and three columns. Column 2 and 3 numbers (54 in five conditions, 53 in one; 0.14 per 60 over 145 groups; about 200 labels; about 60%) need `data-doc` bindings to 07-remedies.md section 3 and section 6, or a small feed written from `s13_majority_vote.py`. Keep the stairs and tally components in column 1. Notes: add the voting and fine-tuning sentences to beat 6 in the outline (about 40 words).

13. `#agree-or-defer` (S12): headline, both state captions and the footer line from section 3. Keep the sorter and both fragments. The captions already carry the bound numbers; wrap them.

14. `#queue` (S13): the five policy lines and the queue caption from section 3. Keep the queue component and the question fragment.

15. `#classification-bench` (S14): headline, pipeline sentence and status line from section 3. Keep the pipeline component and the route pills.

16. `#monday` (S15): headline, four full-sentence steps, footer line; shrink the appendix index to one line. Keep the QR.

17. `#about` (S3): the six-line bio from 03-speaker.md section 5. Keep the portrait.

18. `#launch-wave` (S4): headline and lede from section 3. Keep the timeline and its three fragments. Optional: the Vercel 13% adoption line with a `data-doc` binding to 02-landscape.md A4.

19. Appendix: ledes on `#a1-hosted` and `#a2-open-weight`; P0/P1/P2 definition line on `#a3-prompt-levels`; the deterministic sentence on `#a9-equal-scores`; headline rewrites on `#a11-rare-classes` and `#a12-general-pairs`. A4 to A8, A10, A13 to A19 unchanged.

20. After the pass: run `fit.mjs` at 1920x1080, 1440x900, 1366x768 and 1280x720 for every slide, `numbers.mjs`, `content-audit.mjs` with the new cap, `count-notes.ts` on the outline (target stays under 1,700 words with the two new beats), and `audit-slop.ts`. Then re-run `review-capture.mjs` and read every screenshot as a viewer, not as the author.

What must not change: every `data-source`, `data-count`, `data-deck-source`, `data-doc` and `data-review` attribute and its value; the `data-c` motion hooks (bars, wave, matrix, flip, wall, histo, gate, stairs, tally, sorter, queue, pipeline, replay, hbars); the fragment counts on S4, S8, S9, S10, S12, S13 and the six hard-review slides; the replay badges; the scene attributes on S1 and S7; the 1080p fit; the frozen-commit SHA in the S15 and A7 footers; the AEA logo placement.

## 7. Anti-slop pass on the rewrites

Checked every rewrite in sections 3 and 5 against Tier 1, 2 and 4 of the anti-slop skill.

Tier 1: no em dashes, no double hyphens, no curly quotes, no emoji, no title case in headings. Headings in this document are sentence case. The one bold-lead-in list left in place is A7's limits slide, which I chose not to rewrite; it is pre-existing.

Tier 2: scanned the rewrites for the buzzword, inflated-verb, modifier and filler lists. None present. "really" does not appear; "very" does not appear. "Credit where it's due" is Adam's own phrase from the notes and stays.

Tier 4, pattern by pattern:

Dramatic fragmentation (27): every new headline has a subject and a verb. Two deliberate short sentences remain because they carry the talk's rule and are Adam's: "Cost is not the constraint." and "Typed output fixes the format. It doesn't fix the decision." Both are complete sentences, not fragments.

Binary contrasts (25): "It can't invent a label and it can't explain itself" is two parallel negatives, not a "not X but Y" set-up; kept. "Typed output fixes the format. It doesn't fix the decision." is a contrast but each half is a direct claim; kept. No "not because X, because Y" constructions.

Rhetorical set-ups (28): "The answer" eyebrow on S2 was flagged; the rewrite keeps the eyebrow text because the slide now delivers the answer in full on the same screen. "The fixes I'd reach for first didn't reliably help" announces nothing it does not then show. No "what if", "here's what I mean", "think about it".

False agency (29): "the soup has company" replaced with "the soup is not alone". "The score can tell you a review is hard" gives a score a verb; it is Adam's spoken line and the actor (the score) is the thing the sentence is about, so it stays. "The misses weren't random" names no actor and needs none.

Narrator distance (30): "the orange point" captions replaced with "the orange one is this review" and "each dot on the right is one review". The rewrites use "you" and "I" on S1, S2, S3, S8, S10, S14, S15.

Wh- openers (32): "What I'd do on Monday." is the one wh- opener kept, as a heading that names the slide's content; the four steps under it lead with verbs. "What a pass cost" was removed. No sentence in the rewrites starts with "What makes", "Why this", "How this".

Passive hiding the actor (31): "AI drafted the reviews and the key. People checked all 60." names both actors. "Being open-sourced" is a status badge from the site and the brief; kept.

Rule of three (10): the classification-bench sentence lists five things the runner does because there are five. The Monday recipe has four steps because the outline has four.

Voice check (the skill's "personality and soul" section): the rewrites use contractions, first person, and Adam's own lines ("good luck hiring after that", "credit where it's due", "the fix I'd reach for first was the one I'd trust least"). They vary length: a 30-word headline next to a four-word sentence. Read aloud, they are what the notes already say.

Residual: 20 to 60 words on a slide is more than this deck's typography was tuned for. Some h2 sizes will need to drop one step (the deck.css scale already has one) and the fit script will say where. That is a layout residual for the Opus pass, not a writing one.
