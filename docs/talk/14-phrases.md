# 14 Phrases worth putting on slides

Adam said there were good phrases on the previous site and the current one. This is the harvest. Read-only pass over the old site and deck at commit 6243eb3d, the current public site, the deep-insights feed, `docs/FINDINGS.md`, `01-findings-synthesis.md` (called 01 below) and `01b-deep-analysis.md` (01b).

How to read it:

- The phrase column is verbatim. Where a sentence is long, only the quoted part is the candidate headline.
- Source "old" means the file at 6243eb3d. "Now" means the current branch. A phrase found in both is listed once with both.
- Slide slots use the 18-slide plan in `13-deck-brief-review.md` section 5: S1 title, S2 answer, S3 bio, S4 decision models and System 1/2, S5 launch wave, S6 what we did, S7 proof 1 the gap, S8 cost, S9 consequences, S10 soup, S11 zero of seven, S12 the hard six, S13 confidence, S14 fixes that did not work (prompts, voting, fine-tuning), S15 the rule, S16 the queue, S17 the tool (harness), S18 Monday (close).
- "Fact" says what the phrase states and where the number lives. If the phrase needs a number, the number is in that cell. Every score is agreement with the provisional v0.2 reference on the same 60 synthetic reviews, never accuracy.
- ★ marks the ten strongest.

## 1. The phrases

| # | Phrase (verbatim) | From | Fact it states, with number and feed or doc | Slot |
|-|-|-|-|-|
| 1 ★ | The gap is five reviews. | Now: index.html Read page, finding 01 | Jev 54, 53, 52 of 60 over three passes; Opus 5.5 high 59, 58, 58; Sonnet 5.5 xhigh 58 in all nine cells. `deck/data/answer.json`, `deep-insights-v1.json`, `claude-roster-repeats.json`, `sonnet55-fresh-matched3.json`. | S7 |
| 2 ★ | The reviews that split the models are the ones a person pauses on. | Now: index.html, finding 02 | Six reviews split four or more of the seven decision models; three carry disputed labels; five of Jev's six misses are among them. `deck/data/hard-cases.json`, `disputed-reviews-v1.json`. | S12 |
| 3 ★ | Agree or defer. | Now: index.html, "What to do about it" | Accept a review only when two cheap models return the same four answers; else a person. Solar + Perplexity: 53 accepted, 0 accepted errors, 7 deferred, $0.03749436 known charge. `native-agreement-policy-v1.json`. | S15 |
| 4 ★ | A positive comment can still need follow-up. A polite comment can describe harassment. | Old: index.html hero lede | DEV-059 "Nice staff... kept asking me out": reference mixed / yes / yes / no. Jev marked follow-up no at 0.49 confidence. `disputed-reviews-v1.json`, `jev-confidence-findings.json`. | S1 or S9 |
| 5 ★ | Neither confidence nor a longer prompt works as a gate. | Now: index.html, finding 03 | Jev pooled calibration gap 0.011 (Clef Flash 0.358), still 0.96 on a wrong testimonial; P1 to P2 raised 4 of 39 setups, 14 unchanged, 21 lower. `deep-insights-v1.json`, `findings.json`. | S13 |
| 6 ★ | Equal scores can hide different answers. | Old: meetup deck, slide "Repeatability" | Sonnet 5.5 xhigh 58/60 in all nine cells yet changed DEV-006 and DEV-030 between passes; Jev P2 passes 1 and 3 both 54 and differ on DEV-030. `sonnet55-fresh-matched3.json`, `docs/JEV_NATIVE_PROMPT_FINDINGS_2026-10-06.md`. | S9 |
| 7 ★ | In the first pass, 21 of 39 setups scored lower with decision rules. | Old and now: index.html, explore.html | P1 to P2 over 39 audited setups: 4 higher, 14 unchanged, 21 lower. `findings.json`, `docs/FINDINGS.md`. | S14 |
| 8 ★ | That queue is the price of zero accepted errors on this set. | Now: index.html, "What to do about it" | 35 of 60 reach a person under the full policy: 7 deferred, 24 escalated for a concern, 4 for clarification. `docs/talk/scripts/s12_escalation_queue.py`, `deep-insights-v1.json`. | S16 |
| 9 ★ | If the decision matters, buy a rule that hands the hard reviews to a person. | Now: index.html hero | The whole talk in one line; answer slide. 54 vs 58 to 59 at roughly 4x to 40x the estimated cost. `deck/data/answer.json`. | S2 |
| 10 ★ | One comment. Four decisions. | Old: presentation.html h1; now: "One comment, four decisions" card | Each of 60 reviews gets sentiment, follow-up, serious concern, testimonial. Review DEV-003 is the worked example. `disputed-reviews-v1.json`. | S6 |
| 11 | Can we trust a model to read candidate feedback the same way twice? | Old: presentation.html lede | The repeatability question. Decision models: 31 of 50 three-pass groups changed nothing; general LLMs 11 of 202. `deep-insights-v1.json` (determinism), 01b 12.4. | S6 or S9 |
| 12 | Read the comment before the answer. | Old: presentation.html, "The task" | Show the review text first, then reveal the four reference answers. No number. | S10 |
| 13 | A helpful interview can still split the models. | Old: presentation.html, "Model disagreement" | DEV-027, the cancelled-train review, reference positive / no / no / yes; 3 of 7 decision models matched fully. Jev said not a testimonial at 0.96. `disputed-reviews-v1.json`. | S12 |
| 14 | The task's scope changes the answer. | Old: presentation.html, "Reference boundaries" | DEV-029, the soup review: 0 of 7 decision models matched "can't tell" on all four. `disputed-reviews-v1.json`. | S10 or S11 |
| 15 | The comment mentions a restaurant. Should a candidate-feedback classifier infer hiring labels from it? | Old: meetup-presentation.js, boundary slide | The soup review as a question to the room, before the reveal. No number. | S10 |
| 16 | A prompt can gain matches and lose others. | Old: presentation.html, "Prompt changes" | 39-setup tally: plain to framing 15 higher, 15 same, 9 lower; framing to tree 4, 14, 21. `findings.json`, `prompt-levels.json`. | S14 |
| 17 | Stable repeats can still disagree with the reference. | Old: presentation.html, "Latest decision models" | Perplexity Decider 54/60 in all nine runs, 540 of 540 valid, same errors every time. `results/perplexity-decider-v1/full-v2/findings.json`. | S9 |
| 18 | Equal totals can hide different field-level mistakes. | Old: index.html cost note | Perplexity Decider and Clef both 54/60 on the first P0 run, with different field errors; $0.01542736 and $0.03184656 known charges. `docs/talk/06-cost-check.md`. | S8 |
| 19 | Compare the bill alongside the answers. | Old: presentation.html, "Cost and quality" | Jev $0.00589092 known pass vs Opus $0.222052 API-equivalent estimate (about 38x). `answer.json`. | S8 |
| 20 | The higher observed charge produced the same all-four score in these two saved runs. | Old: meetup-presentation.js, cost slide | Gemma 4 31B thinking off vs on: both 56/60, $0.0056 vs $0.0130 (2.35x). 01b 4.1. | S8 |
| 21 | Test the decisions your team will act on. | Old: presentation.html, "Practical implications" | The Monday close. Sits with the recipe: label 60, add can't tell, run two, count the queue. | S18 |
| 22 | Agree on the labels. Inspect disagreements. Repeat the same inputs. Price the complete workflow. | Old: presentation.html | Four-step version of the Monday recipe. No number. | S18 |
| 23 | A label becomes useful when the team agrees what to do with it. | Old: meetup-presentation.js, implications lede | The reason for routing rules over scores. No number. | S15 or S18 |
| 24 | Keep a person responsible for contested labels and workflow decisions. | Old: meetup-presentation.js | Three disputed labels (DEV-006, DEV-013, DEV-030) are the contested ones. `docs/REFERENCE_REVIEW_V1.md`. | S16 |
| 25 | Repeat the same inputs before relying on a small score difference. | Old: meetup-presentation.js | A three-point swing: Gemma E2B thinking-on P1 36 then 39 of 60, 11 reviews changed. `reader-evidence.json` (old). | S9 |
| 26 | These 60 reviews are a development test. | Old: presentation.html, limits | 60 synthetic reviews; 340 planned records never generated. `docs/PILOT_AUDIT.md`. | S6 |
| 27 | Reference agreement is not real-world hiring accuracy. | Old: meetup-presentation.js, limits | The safety line under every score. | S6 |
| 28 | Repeated passes evaluate the same reviews, not new candidates. | Old: presentation.html, limits | 1,004 saved run entries reuse the same 60 reviews. | S6 or limits |
| 29 | Which candidate feedback needs action? | Old: index.html h1 | The task in five words. | S1 or S6 |
| 30 | We asked four questions about the same 60 comments. | Old: index.html | 60 reviews, 4 questions. Now reads "Every review gets four decisions." | S6 |
| 31 | Every review gets four decisions. | Now: index.html | Sentiment, follow-up, serious concern, testimonial. A review counts as matched only when all four agree. | S6 |
| 32 | A bad experience alone does not count. | Now: index.html, serious-concern definition | Serious concern means harassment, discrimination or a privacy breach. 25 of 60 reference reviews say yes. | S6 |
| 33 | A small, fictional test. AI wrote the reviews and drafted the reference. A person checked every label, and three remain disputed. | Now: index.html | Provenance in three sentences. Checked 2 October 2026. `docs/REFERENCE_REVIEW_V1.md`. | S6 |
| 34 | Great soup, tiny portions, wouldn't eat there again. | Now: index.html (DEV-029 text) | The off-topic review. Reference is "can't tell" on all four. | S10 |
| 35 | None of the seven decision models matched the reference on this review: 0 of 7. | Now: index.html, finding 02 | DEV-029. `disputed-reviews-v1.json`. | S11 |
| 36 | Among general-model configurations with valid answers, 89 of 113 did. | Now: index.html, finding 02 | 89 of 113 valid general configurations matched "can't tell" on all four. `results/cross-category-v1/findings.md`. | S11 |
| 37 | A confidence score that tracks its hit rate | Now: index.html, finding 03 | Heading for the calibration half. Jev gap 0.011 vs Clef Flash 0.358. 01b section 8. | S13 |
| 38 | so the score flags hard reviews, though not on the fields you act on. | Now: index.html, finding 03 (mid-sentence clause) | Jev's ten least-confident reviews include 7 of the 10 hardest, through sentiment only. 01b section 8. | S13 |
| 39 | Run two cheap models that fail differently. | Now: index.html | The rule. Disagreement only helps when the failures differ: 6 of 21 pairs accepted the soup with the same wrong answer. | S15 |
| 40 | Jev's answers differed on six comments. | Old and now: explore.html | 54 of 60 on all four; 11 field disagreements in six reviews. `findings.json`. | S7 |
| 41 | Jev matched all 25 references labeled serious concern = yes. | Old: FINDINGS.md | Credit line before the miss. 25 of 25. `docs/FINDINGS.md`. | S8 |
| 42 | Jev recognized the serious concern but missed the open request. | Old: FINDINGS.md, DEV-059 row | The harassment review: concern yes, follow-up no. | S9 |
| 43 | Missing a request for clarification and dismissing a concrete serious report call for different investigation. | Old: FINDINGS.md | Jev's 3 misses on concern were "can't tell" references answered no; the DEV-059 miss was a concrete report. | S12 |
| 44 | Higher scores can hide different failure patterns | Old: FINDINGS.md heading | Opus 5.5 high matched five of Jev's six misses and kept all 54 of Jev's matches. | S7 |
| 45 | More instructions did not consistently improve agreement | Old: FINDINGS.md heading | The 39-setup tally. | S14 |
| 46 | Disagreements cluster around three ambiguous reviews | Old: FINDINGS.md heading | DEV-013 drew 30 disagreements, DEV-030 28, DEV-006 26, each of 39 configurations. | S12 |
| 47 | Frequent disagreement can identify a weak reference as well as a weak classifier | Old: FINDINGS.md | Flipping DEV-006 alone moves 212 runs up, 168 down, 257 unchanged of 637. `reference-sensitivity-v1.json`. | S12 |
| 48 | A classifier that always says no to testimonial potential already matches 50 of 60 references. | Old: FINDINGS.md | Testimonial 9 yes / 50 no / 1 insufficient. | S13 or S14 |
| 49 | A tied score can conceal changed answers | Old: FINDINGS.md | Same point as phrase 6, shorter. | S9 |
| 50 | Higher effort can cost more without adding matches | Old: FINDINGS.md heading | Gemini 3.1 Pro low 56/60 $0.063458 vs high 55/60 $0.256826. | S8 or S14 |
| 51 | Do not count missing costs as free inference. | Old: FINDINGS.md | Unknown cost stays unknown. Gemini, Claude and Codex estimates are not bills. `06-cost-check.md`. | S8 |
| 52 | A usable answer can still miss the reference. | Old and now: explore.html | Valid vs all-four: Qwen3 0.6B returned 60 valid answers and matched 0. | S9 |
| 53 | Similar scores can hide changed answers. | Old and now: explore.html | Same fact as phrase 6. | S9 |
| 54 | The same review can produce different decisions. | Old and now: explore.html | Seven decision models, one review, up to four different answers. | S12 |
| 55 | A repeated miss may reveal an ambiguous comment or reference answer. | Old and now: explore.html | DEV-006 was missed by 6 of 7 decision models; the reviewer proposes the models may be right. | S12 |
| 56 | Which comments should a person review first? | Old and now: explore.html | The queue. Hardest: DEV-030 matched by 144 of 1,004 run-passes. 01b 1.1. | S16 |
| 57 | Qwen 0.6B repeated the same mistakes. | Old and now: explore.html | Qwen3 0.6B: 0 of 60, all 60 marked testimonial yes, identical across three passes. | S9 |
| 58 | The newer runs change the cost comparison. | Old and now: explore.html | Seven decision models cost $0.0119 to $0.0318 per 60-review pass. `06-cost-check.md`. | S8 |
| 59 | Decision models repeated their answers across passes; most general LLM configurations changed some | Now: deep-insights-v1.json, determinism title | 31 of 50 decision groups changed nothing; 11 of 202 general groups. | S9 |
| 60 | A decision model gives a fixed wrong list you can audit once; a general LLM gives a different wrong list each batch | Now: deep-insights-v1.json, determinism implication | Same numbers as phrase 59. Strongest single sentence for the "same wrong answer at scale" point. | S9 |
| 61 | The strongest runs often return identical answer sets | Now: deep-insights-v1.json, frontier convergence | 44 run-passes from seven families share one answer set; 101 distinct sets among 373 strong run-passes. | S15 |
| 62 | Pick a second model that fails on different reviews | Now: deep-insights-v1.json, frontier convergence | Why a second frontier model is a weak check. | S15 |
| 63 | agreement still cannot catch a blind spot both models share. | Now: deep-insights-v1.json, agreement implication | All seven decision models missed the soup. 6 of 21 pairs accepted it. | S15 |
| 64 | Some cheap general LLM pairs accepted more reviews than Solar + Perplexity at a lower charge | Now: deep-insights-v1.json, agreement title | Qwen3.8 27B low + Gemma 4 26B on: 58 accepted, 0 errors, 2 deferred, $0.0685 observed, pass-sensitive. | S15 |
| 65 | The cheapest gate-clearing pass failed the insufficient-information gate when its configuration ran again | Now: deep-insights-v1.json, cost frontier | DeepSeek Flash off: 54/60 at $0.002681, then 48, 49, 48 on fresh passes. | S14 |
| 66 | Select a configuration only after the gate holds across three passes. | Now: deep-insights-v1.json | Voting and one-pass selection both fail the same way. | S14 |
| 67 | After a prompt change, regression-test the label distribution as well as the score. | Now: deep-insights-v1.json, prompt direction | P1 to P2: 127 worse, 78 better, 94 same of 299 triplets. 01b 12.6. | S14 |
| 68 | The thinking switch is model- and size-specific; test it per configuration instead of assuming more reasoning helps. | Now: deep-insights-v1.json, size and thinking | Qwen 1.7B hurt in 12 of 12 pairs; Gemma helped at every size. | S14 |
| 69 | Treat insufficient information as its own detection task with its own recall | Now: deep-insights-v1.json | Decision runs match the 10 "can't tell" cells at 19% to 45%, general at 71% to 84%. 01b 12.1. | S13 |
| 70 | If a vendor exposes two numbers, threshold on the option probability | Now: deep-insights-v1.json, calibration | Clef Flash confidence and option probability differ by more than 0.2 on 55% of answers. | S13 |
| 71 | The hardest reviews are the disputed, off-topic and boundary cases, so the human queue should cover them first. | Now: deep-insights-v1.json | Ten hardest reviews; Solar + Perplexity deferred set covers five of Jev's six misses. | S16 |
| 72 | What this test does not show. | Now: index.html limits | Not a leaderboard, not causal, not real-world accuracy; the reference is provisional. | S6 or A7 |
| 73 | It is not a leaderboard. | Now: index.html limits | Runs differ in route, interface, batch size, effort and prompt. | S6 |
| 74 | A missing cost means unknown. | Now: index.html limits | Known charges, observed charges, estimates are kept apart. | S8 |
| 75 | A high score on fictional examples is an early test, not deployment approval. | Now: index.html, "For leaders approving a pilot" | The Monday caution. | S18 |
| 76 | Ask who checked the expected answers, whether repeat tests changed the result, and what a mistake would cost the team. | Now: index.html | Three questions for a leader. | S18 |
| 77 | Choose real examples your team understands. Agree on what each label means and who should act on it. | Now: index.html | Monday step one. | S18 |
| 78 | Record the exact model, hosting service, settings and inputs. Keep failed requests in the results. | Now: index.html, "For people building the workflow" | What a runner has to do; the harness slide. | S17 |
| 79 | classification-bench, the tool that ran these tests, is being open-sourced. Ask Adam for early access. | Now: index.html and method.html | Status line for the tool. 433 tests collected. `04-harness.md`. | S17 |
| 80 | Do models like Jev get it right when correctness is business-critical? | Now: index.html title | The talk title. | S1 |

Notes on the table:

- Rows 11 and 22 to 25 are phrases from the old deck that had no number. They are good as lead lines under a number the new deck already carries.
- Row 38 is a clause from a longer sentence, kept verbatim.
- Row 69 says decision models "answered most" insufficient cells with a definite label in the feed title. The recomputed figure is a definite label on 25% to 31% of reference-insufficient answers across all models, and decision runs match those cells only 19% to 45% of the time. Quote the percentages, not the word "most", if the slide shows a number.
- Row 36 and the brief wording differ. The source says 89 of 113 matched the reference "can't tell" on all four. Brief shorthand is "said not about recruitment". Use the source wording on a slide.

## 2. Ten strongest

1. The gap is five reviews.
2. The reviews that split the models are the ones a person pauses on.
3. Agree or defer.
4. A positive comment can still need follow-up. A polite comment can describe harassment.
5. Neither confidence nor a longer prompt works as a gate.
6. Equal scores can hide different answers.
7. In the first pass, 21 of 39 setups scored lower with decision rules.
8. That queue is the price of zero accepted errors on this set.
9. If the decision matters, buy a rule that hands the hard reviews to a person.
10. One comment. Four decisions.

Next in line if one of these is replaced: "Stable repeats can still disagree with the reference." and the determinism sentence in row 60.

## 3. What the general LLMs taught us

Adam asked for a general-LLM comparison. These findings are about general models, not decision models. Each has the exact numbers and where they live. All are saved-run observations on the 60 reviews, none causal, none a ranking.

**Effort ladders**

1. **Gemini 3.1 Pro, more effort cost more and matched one fewer.** Low 56/60, 3,417 output tokens, $0.063458. High 55/60, 19,531 output tokens, $0.256826, about 4.05x. Same 11,227 input tokens. High matched fewer in 7 of 10 pairs. `docs/FINDINGS.md`, 01 insight 14, 01b 4.1 and 4.3.
2. **Gemini Flash high effort lost to batch failures, not judgment.** 3.7 Flash low 57 at $0.02167275, medium 56 at $0.0559665, high 47 with 50 valid, 5.28x cost. 3.8 Flash medium 47 with 50 valid. The lost matches are ten-review batches, always the same block of ten (DEV-011 to DEV-020). 01b 4.1 and 9 Q6.
3. **Claude effort mostly changed nothing.** Opus 5.5 batch of 10 at P0: low 59, medium 58, high 59, xhigh 58; across 9 pairs it never gained a match (4 lower, 5 equal). Low to xhigh 59 to 58 at 0.76x estimated cost. Sonnet 5.5 never hurt (0 lower, 4 equal, 5 higher). Fable 5.1 single: 58 at low, 58 at max, 2.22x estimated cost. 01b 4.1 to 4.3.
4. **Codex effort was model-specific.** gpt-5.6 sol low 58 to xhigh 57, never gained in 9 pairs. gpt-6 luna batch of 10: 54, 50, 56, 57, helped in all 9 pairs. gpt-6 sol never helped (1 lower, 8 equal). 01b 4.1 and 4.3.
5. **Frontier effort moved the total by at most two points.** Effort changed the answer vector on 1 to 6 of 60 reviews while multiplying output tokens 1.3x to 6x. Exception: Sonnet 5 single low to max 54 to 59, and gpt-6 luna batch of 10 51 to 57. 01b 4.3.
6. **"Low effort" is not a cost control.** 97 run-passes report reasoning tokens above zero at effort off, low or not applicable. Haiku 4.5 spent 18,435 to 45,302 reasoning tokens per pass, DeepSeek Flash low 18,127 to 25,005, Qwen3.8 27B low 19,817 to 20,324. Output-token ratio from lowest to highest effort runs from 1.4x (gpt-5.6 sol) to 49x (Qwen 4B). 01b 9 Q5.
7. **Qwen3.8 27B xhigh was cheaper and better than medium.** 0.81x output tokens, 0.84x cost, 56 to 58 on fresh pass 1. 01b 4.2.
8. **Thinking paid for itself in two families only.** Gemma 4 26B: 53 to 59 for $0.0069 to $0.0211, about $0.0024 per extra match. DeepSeek Flash: plus 9 to 10 matches over three fresh passes at about $0.0033 per extra match, but zero gain in the original pass at 6.91x. 01b 4.3 and 12.7.
9. **The cheapest gate-clearing pass was a lucky draw.** DeepSeek Flash thinking off, original P0: 54/60, 25 of 25 serious concerns at precision 1.0, 10 of 10 "can't tell" cells, $0.002681. The three fresh passes of the same configuration scored 48, 49, 48. `deep-insights-v1.json` (cost frontier), 01b 12.8.
10. **Haiku and Opus 5 gave no stable prompt gain.** Haiku's classifier-instruction score ranged 53 to 59 over three fresh passes, its edge over the base prompt swinging from two fewer to two more. Opus 5 high gained two matches from decision-tree instructions in two passes, then lost two. Old explore.html notes.

**Thinking on and off**

11. **Qwen3 1.7B thinking hurt in 12 of 12 pairs.** Losses of 2 to 24 matches, growing with prompt length (P0 minus 2 to minus 5, P1 minus 9 to minus 15, P2 minus 21 to minus 24), almost all on testimonial. 01b 5.3 and 12.7, `deep-insights-v1.json` (size and thinking).
12. **Qwen 4B and Gemma helped at every size.** Qwen3.5 4B helped in 3 of 3 pairs (plus 7 to 16 but 5 to 9 fewer valid). Gemma E2B 12 of 12, E4B 8 of 8, 26B 3 of 3, 31B 8 of 9. Overall 49 off-versus-on comparisons: on won 42, off won 7, 3 tied. 01b 5.3 and 9 Q3.
13. **When no-thinking wins, check validity first.** Hosted Qwen3 8B thinking-on in JSON-object mode returned 14 valid answers of 60 (off scored 39 to 43 against on 11 to 14). 01b 9 Q3.

**Frontier convergence**

14. **The strongest runs answer alike.** 373 run-passes had 60 valid answers and 57 or more matches; they hold only 101 distinct answer sets. One set is shared by 44 run-passes from seven families and misses exactly DEV-006, DEV-013, DEV-030. 270 of the 373 miss nothing outside the three disputed labels. 01b 9 Q7 and 12.2, `deep-insights-v1.json`.
15. **Frontier models are stochastic, decision models are not.** 31 of 50 decision groups changed no answer across three passes, against 11 of 202 general groups. Fully identical vectors across passes: Sonnet 5.5 4 of 12, Opus 5.5 3 of 12, gpt-5.6 luna 0 of 12, gpt-5.6 terra 0 of 12, DeepSeek 0 of 9. General models flip 5 to 9 reviews across passes, and 8 of the 10 most unstable are among the 10 hardest. The seven perfectly stable configurations at 55 or better are all general LLMs. 01b 9 Q2 and 12.4.
16. **Sonnet 5.5 scored 58 in all nine cells and still changed answers.** It changed DEV-006 between P1 passes and DEV-030 between P2 passes. Fable 5.1 low scored 57/60 under P1 in all three passes while changing three reviews. 01 insight 5, `sonnet55-fresh-matched3.json`.
17. **Voting did not rescue general models.** Across 145 clean general-model groups a three-pass majority added 0.14 matched reviews per 60 (63 groups better, 43 tied, 39 worse). Accepting only answers given three times running still let 211 errors through. `07-remedies.md` section 3, `docs/talk/scripts/s13_majority_vote.py`.

**Small local models and invalid output**

18. **Qwen3 0.6B scored 0 of 60.** The HTTP configuration returned 60 valid answers, marked all 60 reviews as testimonial yes against 9 in the reference, and gave identical answers in three passes. The SDK thinking-off configuration returned 0 valid of 60. `docs/LEGACY_QWEN_REPEAT_FINDINGS_2026-10-02.md`, 01b 5.1.
19. **Small models learn follow-up first and serious concern last.** Follow-up reaches 50 of 60 at 0.6B (a majority-label artefact: concern 13, testimonial 9 in the same run). Serious concern is the field that keeps Qwen 8B and Gemma E4B below 48 matches. All four fields together first appear at Qwen3.8 27B and Gemma 4 26B-A4B. 01b 5.2.
20. **Invalid output is a real failure class on generated JSON.** AnyJev generated-JSON control: all 360 P0 and P1 responses opened with a code fence, 0 valid. SemIf generated: 8, 22 and 2 invalid per pass. OpenJev generated off: 7, 7, 4. Hosted Qwen3 8B thinking-on JSON-object mode: 14 valid, 46 invalid. Native choice heads and the Claude and Codex runs: 60 of 60 valid in essentially every pass. Overall 2,234 non-ok positions of 60,240, 2,066 of them invalid output. 01 insight 11, 01b 9 Q4.
21. **Failures land on the hard reviews, not the long ones.** Failure count against text length: Spearman minus 0.07. The soup is the second-shortest text and the fourth most failed. 01b 12.9.
22. **Batching changes which review is wrong.** Batch of 10 versus single: DEV-010 missed by batch runs in 10 of 15 pairs, DEV-013 in 8 of 15, DEV-006 the reverse in 6. Means are within 1 to 4 points. 01b 9 Q6.

**Noticing the soup, cost, and the best pair**

23. **General models noticed the off-topic review.** 89 of 113 general configurations with valid answers matched "can't tell" on all four fields; 13 of 28 declared fresh configurations did. Decision models: 0 of 7. `results/cross-category-v1/findings.md`, 01 insight 10.
24. **General models handle "can't tell" better in general.** Reference-insufficient cells matched at 71% to 84% by general runs against 19% to 45% by decision runs. On follow-up, 86.5% against 25.0%. A prompt P2 tree pushes general LLMs from negative to mixed (minus 0.81 and plus 0.90 per triplet over 299 triplets). 01b 12.1 and 12.6.
25. **Cost: 4x to 40x.** Per 60-review pass against Jev's $0.00589092: Gemma 4 26B thinking-on $0.02114858 (3.6x, 59/60), Qwen3.8 27B low $0.0492372 (8.4x, 59/60), Opus 5.5 high $0.222052 (37.7x, estimate). Observed charges and API-equivalent estimates are not the same quantity. 01 insight 1 and 14, `answer.json`.
26. **The best cheap pair is two general models.** Qwen3.8 27B low + Gemma 4 26B thinking-on accepted 58, 0 errors, 2 deferred (DEV-005, DEV-013), $0.0685 observed. Gemma 31B off + DeepSeek Flash low: 55 accepted, 0 errors, 5 deferred, $0.0207. 35 of 853 costed pairs dominate Solar + Perplexity (53, 0, 7, $0.0375), none containing a native decision model. `deep-insights-v1.json`, 01b 11 and 12.3.
27. **That pair is one draw.** The same Qwen run paired with Gemma 26B fresh2 gives 57 accepted with 1 error, with fresh3 gives 59 with 1 error. The same model twice is not a second opinion: Qwen 35B off agrees with itself on 9 wrong answers. 01b 12.3.

Count: 27 general-LLM findings collected.

Two items touch decision-model clones and are kept out of the count: AnyJev raw 0 of 60 with a Qwen3 0.6B backbone, and the rules baseline at 10 of 60 with five learned configurations below it.

Open points for whoever builds the slides:

- The table's S-numbers follow the 18-slide plan in `13-deck-brief-review.md`. The working-tree `05-session-outline.md` still lists 15 slides, so check the slot before wiring a phrase.
- Rows 61 to 71 come from a feed whose strings are built from templates. The slide should carry the sentence, not the template pieces.
- Numbers drift when the feeds are refreshed. Re-read `deep-insights-v1.json` at deck export.
