# Voice and anti-slop audit

Lane: voice. Evidence SHA: 35cdc4c8 (worktree HEAD, deck as captured 2026-10-08). Read-only except this file and `voice/`.
Caveat: the director was editing deck files in the working tree while I worked (modified: charts.js, content.js, heroes.js, review-card.js, motion.js). The capture ran against the working tree at HEAD 35cdc4c8 and may include some of those edits. Re-run `review-capture.mjs` before folding any row below.
Claim tested: "the slide copy and speaker notes read like Adam and carry no AI tells."
Verdict: **refuted.** The scripts pass because they count banned words. The hand-read finds a deck that still reads like a research paper with a brand campaign on top. Most problems are jargon used before it is explained, and "not X, it's Y" lines.

## 1. Script scores

Text came from `review-capture.mjs` (all 34 slides at 1920x1080, last fragment step) and the per-slide notes in the same JSON. Files: `voice/slides.txt`, `voice/notes.txt`, `voice/cap.json`, `voice/cap/01.jpg` to `34.jpg`.

| File | audit-slop.ts | analyze-text.ts: formality / warmth / energy / directness / complexity | FK grade | nominalization | passive |
|-|-|-|-|-|-|
| slides.txt (4,581 words) | 100.0%, 0 instances | 3.5 / 2.4 / 2.0 / 3.1 / 2.2 | 9.5 | 2.64% | 5.29% |
| notes.txt (3,350 words) | 100.0%, 0 instances | 3.2 / 2.7 / 2.1 / 3.2 / 2.4 | 8.0 | 2.45% | 4.23% |
| Adam presentation profile | n/a | 2.1 / 4.7 / 2.2 / 3.5 / 1.9 | 8.6 | 1.33% | 3.03% |

What the numbers say. Slides run colder and denser than Adam: warmth is half his, nominalization is double, passive is nearly double. Notes are closer, but warmth is still 2.7 against 4.7.

Mechanical checks I added. Em dashes 0 and curly quotes 0 in both files. Slides carry 25 middle dots (all appendix) and one en dash in a range (a10). Sentence openers in the notes: "So" 10 of 195, "And" 9, "I" 10. Adam's profile has "So" at 8.4%, and the notes sit at 5%. On slides, 26 of 208 sentences run 35 words or more, but nearly all of those are table dumps.

## 2. The three worst, with rewrites

1. **Slide 10, the consequences slide.** Three problems on the slide that is meant to land hardest. "Typed output fixes the format. It doesn't fix the decision." is a binary contrast. "A deterministic wrong answer is wrong every single time, and there's no variance to warn you" is jargon plus a crutch ("every single time"), and it is repeated word for word on a9. And the sarcastic "Good luck with building your brilliant startup" is printed in 28-point bold at the room. That line is Adam's own (brief, line 51), and it works in his mouth. On a slide it reads as a dig at the people watching.
   Rewrite, on screen: "A typed answer always comes back in the right format. It can still be the wrong decision. A model that gives the same wrong answer every time never shows you it's wrong. Miss a harassment report and the candidate posts about it on X and Reddit. Hiring gets a lot harder after that." Keep the brilliant-startup line in the notes only.
2. **Slide 9, the general-models slide.** "On the soup, 89 of 113 general setups answered can't tell on all four fields" shows up two slides before anyone has seen the soup. "44 runs from 7 model families gave one identical answer set" and "31 of 50 decision groups never changed an answer, against 11 of 202 general groups" use "answer set" and "groups" without saying what they are.
   Rewrite: "More effort didn't buy more matches. Gemini 3.1 Pro matched 56 of 60 at low effort for $0.063, and 55 at high effort for $0.257. And the big models give each other's answers, wrong ones included: 44 runs from 7 model families gave exactly the same answers. Run a decision model three times and 31 of 50 setups never changed an answer. For the general models, 11 of 202 held still." Move the 89 of 113 line to slide 12 where the soup is on screen.
3. **Slide 14, the confidence slide.** Title "Proof 3: the number next to the answer" is a riddle. "Pooled gap between confidence and how often it was right" is the technical term for calibration error, with the label removed. "Descriptive only." is a stray caption. "The score can tell you a review is hard. It can't tell you which answer to distrust." is a binary contrast.
   Rewrite: title "Every answer comes with a confidence score. How far can you trust it?" Body: "A low score marks a hard review. A high score doesn't mean the answer is right. Jev was 0.96 confident on the cancelled-train review and wrong." Chart note: "How far each model's confidence sits from its real hit rate, smaller is better: Jev 0.011, Clef Flash 0.358. This describes these 60 reviews and doesn't predict the next 60."

## 3. Flagged phrases

Codes: **K** kicker or fragment, **R** rhetorical setup, **B** binary contrast, **T** rule of three, **C** throat-clearer, **P** condescending or snide to the room, **J** jargon used before it is explained, **H** price or claim hedge, **M** meta caption, pill, label or middle dot, **F** false agency or narrator distance, **X** notes defect. Rewrites keep the number.

### Main slides (1 to 19)

| # | Slide | Code | Phrase | Rewrite |
|-|-|-|-|-|
| 1 | 1 title | P | "You answered both in about two seconds." (notes: "Everyone here got both right in two seconds") | "You probably knew both answers by the second line." |
| 2 | 2 answer | R | Eyebrow "THE ANSWER: FOUR DECISIONS PER REVIEW" | Cut the eyebrow. The headline already says it. |
| 3 | 2 answer | H | "at four to forty times the estimated cost" | "at four to forty times the cost" |
| 4 | 2 answer | K | "buy a rule that hands the hard reviews to a person" | "put a rule in front of the model that sends the hard reviews to a person" |
| 5 | 2 answer | J | "first P0 pass", "our key" (both explained only on slide 6) | "first run on the plain prompt", and say "our answer key" once |
| 6 | 2 answer | B | "It doesn't mean right." | "Three of the key's labels are disputed, so it isn't gospel." |
| 7 | 3 about (notes) | X | "So I have read the pile of candidate feedback, vendors kept telling me their classifier was accurate, and Amazon taught me..." (comma splice, three ideas) | "I read a lot of candidate feedback at Amazon. Vendors kept telling me their classifier was accurate. Amazon taught me to build the measure before trusting the tool." |
| 8 | 4 decision-models | J | Column labels "System 1 calls" and "System 2 calls" | "System 1: the quick gut call" and "System 2: stopping to ask if it's the right question" |
| 9 | 4 decision-models | J | "suits closed labels and one factor per question" | "works when the answer is one of a short list and each question asks about one thing" |
| 10 | 4 decision-models | T | "reads literally, can't explain itself, and misses questions that don't apply" | "It takes your words literally and can't say why it answered. It won't tell you when the question doesn't fit." |
| 11 | 4 decision-models | M | "From our test" tags on both columns | Cut. Put the example in the sentence: "Of the 25 reviews the key marks as a serious concern, Jev caught all 25." |
| 12 | 5 launch-wave | K | Title "The launch wave" | "Four more vendors shipped a decision model within three weeks of Jev." |
| 13 | 5 launch-wave | M | "Each small tick is another launch in those three weeks, among them Upstage's Solar Decide, Kev, Bespoke's Nimble, AnyJev, Ollama support and Liquid's d1 models." | "More small launches filled the gaps, Solar Decide and Liquid's d1 among them." |
| 14 | 5 launch-wave | J | "mostly through the same API shape" | "and most of them work the same way" |
| 15 | 5 launch-wave | C | "almost nobody does that" | "Most vendors don't." |
| 16 | 6 what-we-did | J | "P1 adds classifier framing and P2 adds a decision tree" | "P0 is the plain task. P1 tells the model it's a classifier. P2 adds step-by-step instructions for deciding." |
| 17 | 6 what-we-did | J | "39 hosted and subscription setups ran all three, most in three fresh passes, beside seven decision models and Jev" | "39 general models and settings ran all three prompts, most of them three times from scratch, next to the seven decision models and Jev." |
| 18 | 7 nine-runs | R | "Proof 1: the gap is five reviews" | "Jev and Opus differ on five reviews out of 60." |
| 19 | 7 nine-runs | F | "The gap held in every run that exists" | "Every run shows the same gap: Jev matched 52 to 54 of 60, Opus 5.5 matched 58 or 59." |
| 20 | 7 nine-runs | J | "via OpenRouter, native 54", "both open-weight" | "54 on the direct API", "both free-to-download models" |
| 21 | 8 pass-cost | R | "Proof 1: one pass over 60 reviews" | "A Jev pass over 60 reviews costs $0.006. An Opus pass costs about $0.22." |
| 22 | 8 pass-cost | B | "Opus matched five more reviews, so cost isn't the constraint here." (does not follow from the line before it) | "Opus matched five more reviews for about 21 cents more. At 60 reviews that's pocket change, so the question is which five." |
| 23 | 8 pass-cost | C | "Credit where it's due:" (also in notes 8) | Cut. "Jev caught all 25 reviews the key flags as a serious concern." |
| 24 | 8 pass-cost (notes) | H | "a known provider charge from the OpenRouter pass ... an API-equivalent estimate" | "Jev's price comes from the provider's invoice. Opus's is worked out from list price." Say it once, in plain words. |
| 25 | 9 general-models | F | "Proof 1: what the general models taught us" | "More effort didn't buy more matches." |
| 26 | 9 general-models | J | "On the soup" (soup not shown until 11), "one identical answer set", "decision groups" | See worst-three item 2. |
| 27 | 10 consequences | B | "Typed output fixes the format. It doesn't fix the decision." | "A typed answer always comes back in the right format. It can still be the wrong decision." |
| 28 | 10 consequences | J | "A deterministic wrong answer is wrong every single time, and there's no variance to warn you." (repeats on a9) | "A model that gives the same wrong answer every time never shows you it's wrong." |
| 29 | 10 consequences | P | "Good luck with building your brilliant startup without being able to hire good people willing to work for you." on screen | Notes only. Screen: "Miss a harassment report and the candidate posts about it on X and Reddit. Hiring gets a lot harder after that." |
| 30 | 10 consequences | R | Eyebrow "WHY FIVE REVIEWS MATTER" | "Five reviews is a small gap until one of them goes public." |
| 31 | 11 one-of-60 | C | "Seven purpose-built decision models" (notes too) | "Seven decision models read this review." Add one line: "This is a soup review in a pile of interview feedback." |
| 32 | 11 one-of-60 | M | "Shout it out" label box | Make it a sentence on the slide: "Shout it out: how many of the seven flagged it as off-topic?" |
| 33 | 12 zero-of-seven | M | "Proof 2: seven decision models, one review", "Tev saved answer", "first P0 pass" | "Seven decision models, one review", "Tev said:", "first run" |
| 34 | 13 hard-six | K | "Each one is hard for a reason you can name." | "Each of these is hard for a plain reason, and the reason is on the card." |
| 35 | 13 hard-six | J | Card tags "kindness during a logistics failure", "serious concern without a complaint", "uncertain resolution", "vague recurrence", "second-hand rumour" | "kind words about a cancelled train", "a serious concern, but no formal complaint", "'I think' it was fixed", "'that thing happened again'", "a friend heard a rumour" |
| 36 | 13 hard-six | J | "144 of 1,004 saved passes" on every card (no sentence says what it counts) | Say what it counts ("the general models matched this review 144 times out of 1,004 tries") or cut it. I inferred that meaning, so check it. |
| 37 | 13 hard-six (notes) | C | "And the soup has company." and "a second, AI review of our key" | "Five more reviews trip these models up, each in a different way." and "a second review, done by AI, disputes three of our labels" |
| 38 | 14 still-wrong | K | "Proof 3: the number next to the answer" (notes: "So, proof three. The number next to the answer.") | "Every answer comes with a confidence score. How far can you trust it?" |
| 39 | 14 still-wrong | B | "The score can tell you a review is hard. It can't tell you which answer to distrust." | "A low score marks a hard review. A high score doesn't mean the answer is right." |
| 40 | 14 still-wrong | J | "Pooled gap between confidence and how often it was right" | "How far each model's confidence sits from its real hit rate, smaller is better: Jev 0.011, Clef Flash 0.358." |
| 41 | 14 still-wrong | K | "Descriptive only." | "This describes these 60 reviews and doesn't predict the next 60." |
| 42 | 14 still-wrong | J | "gate" for the confidence cutoff (chart, caption, notes) | "cutoff". "A 0.9 cutoff keeps only answers at 0.9 or above." |
| 43 | 14 still-wrong (notes) | X | One sentence carries 0.9, nine, four, 0.96 and testimonial. Another carries ten, seven, ten, 0.84 and 0.91. Hard to follow by ear. | Split each into three short sentences. One number per sentence. |
| 44 | 15 more-instructions | K | Eyebrow "the fixes I'd reach for first" repeated as the headline | "The obvious fixes didn't reliably help. A longer prompt and a majority vote barely moved the score, and fine-tuning needs more labels than we have." |
| 45 | 15 more-instructions | J | "0.14 more matches per 60" | "0.14 more matches out of 60. That's nothing, so ask a different model instead." |
| 46 | 15 more-instructions | J | "Clef route may read only about 2,000 state tokens, so the tree may have been cut off" (double hedge, jargon) | "Cloudflare's Clef may only read the first 2,000 tokens, roughly 1,500 words, so it might never have seen the whole decision tree." |
| 47 | 16 agree-or-defer | K | Eyebrow "THE RULE: AGREE OR DEFER" and headline "Agree or defer." say it twice. "two cheap models that fail differently" | "Run two cheap models that make different mistakes. Accept a review only when both give the same four answers. Send the rest to a person." |
| 48 | 16 agree-or-defer | K | "Accepted 58, 0 disagreed with the key" and "A person 2" | "58 accepted, and none of them disagreed with the key." and "2 go to a person" |
| 49 | 16 agree-or-defer | J | "Q + G, Qwen 27B low + Gemma 26B thinking on, $0.069 observed, one draw, other Gemma passes let one error through" | "Qwen 27B and Gemma 26B, $0.069 for all 60. That was one run. Other Gemma runs let one error through." |
| 50 | 16 agree-or-defer | J | "Five of the 21 pairs" (21 pairs never introduced on the slide) | "We tried every pair of the seven decision models, 21 pairs. Five let zero errors through. Six accepted the soup with the same wrong answer." |
| 51 | 17 queue | J | Eyebrow "The rule: the policy and the queue", "two typed models", "don't gate on it" | "What a person has to read", "two decision models", "keep the confidence score for the record, but don't use it to decide" |
| 52 | 17 queue | J | "the set is concern-heavy by design" | "We built this set with 25 serious concerns in 60 on purpose. A normal pile probably has fewer, so the queue would be shorter." |
| 53 | 17 queue | J | Vote line "One model at 0.96, or two cheap models that agree?" (0.96 means nothing to the room) | "One model that's 96% sure, or two cheap models that agree?" |
| 54 | 18 classification-bench | M | Legend "dashed: wired", "live", plus step labels "budget held per request", "flips" | "dashed means built but not run live yet", "stays inside your budget", "how often an answer changes between repeats" |
| 55 | 18 classification-bench | J | "reference sensitivity" | "how much the score moves if a disputed label changes" |
| 56 | 18 classification-bench | X | Slide says Claude Code and Codex "are wired". Notes say "built but untested live". | Say it the way the notes do: "Claude Code and Codex are built, and I haven't run them live yet." |
| 57 | 19 monday | J | "Reuven's @ruvector/typesafe is a free local classifier, and a candidate relevance check in front of the four questions." (no surname, no accuracy caveat) | "Reuven Cohen's free local classifier, @ruvector/typesafe, could be the off-topic filter in front of the four questions. I haven't measured how accurate it is." |
| 58 | 19 monday | M | "Appendix for questions, press down or pick one" | Cut from the slide. Navigation hints belong in the notes. |

### Appendix (20 to 34)

| # | Slide | Code | Phrase | Rewrite |
|-|-|-|-|-|
| 59 | a2 (21) | J | "frozen Qwen or Gemma backbone with a small head or adapter"; ten middle dots in card captions | "Each one is a Qwen or Gemma model with a small add-on that scores your options." Replace dots with commas. |
| 60 | a3, a5, a9 (22, 24, 27) | M | Middle dots in headers and captions (7, 1 and 1) | Commas or "to". |
| 61 | a13 to a18 (29 to 34) | M | Title "A13 · hard review DEV-030: uncertain resolution" and five siblings | "DEV-030, a hard review: someone said it was fixed, I think." |
| 62 | a4 (23) | J | "Hardest 10 among its least-confident 10", "All retrospective. No abstention was executed; withheld answers are counterfactual." | "Of Jev's 10 least-confident reviews, 7 are among the 10 hardest." and "These are calculated afterwards. No answer was actually withheld." |
| 63 | a7 (25) | B | "It isn't a leaderboard, because runs differ in route, batch size, effort and prompt." | "Runs differ in route, batch size, effort and prompt, so read this as a set of saved runs, not a ranking." |
| 64 | a9 (27) | K | Repeats slide 10's "deterministic wrong answer" line word for word | Use the slide 10 rewrite, or cut it here. |
| 65 | a10 (28) | M | En dash in "32 – 42 of 60 reach a person" | "32 to 42 of 60" |

### Notes defects

| # | Where | Code | Defect | Fix |
|-|-|-|-|-|
| 66 | Notes on 11, 13, 14, 16, 17 | X | Stage directions point at old slide numbers: "[S10 shows only the text]", "[S12 Six reviews...]", "[S13, replay badge]", "[S15 sorts]", "[S16]". Real slides are 11, 13, 14, 16 and 17. | Renumber, or name the slide by its title so it never drifts. |
| 67 | Notes on 2 | X | The notes for the answer slide never say the answer. They hold two bracketed lines and the hands-up question. Nothing in them states 54, 59 or the five-review gap. | Add the two sentences that read the headline and the bars aloud. |
| 68 | Notes on 16, 17 | X | The rule is stated three times in a row ("Agree or defer. Two cheap models...", "The rule is two cheap models that agree", then again in the queue notes). | Say it once at the start of 16, then lean on the numbers. |

Total flagged: 68 rows (58 main slides, 7 appendix, 3 notes).

## 4. Patterns, not single phrases

- **Every slide carries an eyebrow.** Fifteen of the nineteen main slides open with a small all-caps label (e.g. THE ANSWER, WHY FIVE REVIEWS MATTER, THE RULE). Adam's rule is no kickers. Most of the eyebrows repeat the headline or announce it, so delete them rather than reword them.
- **"Proof 1 / 2 / 3" labels.** They sit on seven slides (7, 8, 9, 12, 13, 14, 15). "Proof 1" covers three slides, and "Proof 3" covers both the confidence slide and the longer-prompt slide, which have little to do with each other. A viewer cannot use the labels. Replace each with a headline that states the finding.
- **Binary contrasts.** Slides 2, 10, 14, 25 (a7) and the matching notes use "isn't X, it's Y" or "can X, can't Y". Rewrites above state the positive half.
- **Jargon used raw.** Terms that appear before any explanation: P0, key, provisional, setups, passes, groups, gate, route, native, flips, wired, answer set, concern-heavy. Each gets a plain-word fix in section 3. Adam's profile asks for no jargon without explanation.
- **Cold register.** Warmth 2.4 on slides against 4.7 for Adam, and zero sentences open with "So", "And" or "But". That is normal for slides. The fix is in the notes, which have the "So" openers but few "I" stories. Slide 3 and the closing are the only places a person shows up.

## 5. What already sounds like Adam, keep it

- Slide 1: "Is this a serious concern? Does someone need to follow up?" followed by the real review. Concrete and it pulls the room in.
- Slide 6: "Every model got the same 60 fictional reviews and four questions about each."
- Slide 15: "Fine-tuning starts paying off around 200 labels, and we have 9 testimonials."
- Slide 16: "Zero errors on these 60 isn't zero on the next 60." (the one contrast that carries real information)
- Slide 19: "I'd pull 60 of my own cases and label them myself, before any model sees them."
- Notes throughout: contractions everywhere, first person, no em dashes, no banned words.
