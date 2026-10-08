# 05r Outline review: independent adversarial pass on 05-session-outline.md v1

Reviewer: independent reviewer agent, no stake in the outline. Date: 2026-10-08.

Reviewed: `05-session-outline.md` v1 (244 lines, 1,709 counted words of speaker notes).

Checked against: `01-findings-synthesis.md`, `02-landscape.md`, `03-speaker.md`, `04-harness.md`, the Adam presentation voice profile, the anti-slop skill. I also opened the JSON feeds under `public-site/` with `python3 -I`, plus these files: `docs/FINDINGS.md`, `docs/REFERENCE_REVIEW_V1.md`, `docs/PILOT_AUDIT.md`, `README.md`, `results/cross-category-v1/findings.md`, `docs/CLEF_OPENROUTER_FINDINGS.md` and `docs/JEV_NATIVE_PROMPT_FINDINGS_2026-10-06.md`.

Numbers marked **(rc)** are reviewer-computed from public feeds. Re-verify them before they go on a slide.

---

## Verdict: REVISE

The skeleton is right: one answer, three proofs, one rule, one call to action. The soup review is a great centrepiece. The rule is concrete enough to build on Monday, and the tone toward TypeSafe is mostly collegial.

The outline cannot go on stage as written, for four reasons:
- Four numbers are wrong as spoken, and several more are mislabelled.
- Three claims break the "must NOT make" list in 01 §4.
- One spoken sentence misdescribes who made and disputed the answer key.
- The thesis line contradicts 01's own analysis, the rule beat contradicts itself, and the run of show has no real buffer.

All of this is fixable in a day with no new inference.

Several errors were inherited from 01 and 02, so those notes need the same corrections. The inherited errors are:
- "Twenty-two days" should be sixteen days.
- "Four zero-error pairs" should be five.
- "Five said mixed" should be four.
- "Under $1.20" is wrong.

---

## Blocking findings

**B1. Jev's soup answer is reversed.** Beat 6 says: "It called the soup review a serious concern at 0.91." Jev answered *no* serious concern at 0.91. The reference is `insufficient_information`. Source: `public-site/findings.json` `charts.jev.fieldErrors`, where serious concern has 3 confusions, all `insufficient_information` to `no`. Also `jev-confidence-findings.json` P0 serious-concern wrongCases DEV-029 0.91. Beat 5 already says Jev answered "mixed / no / no / no", so the room hears two different answers.
Edit: "It said the soup review had no serious concern, at 0.91 confidence, when the honest answer was 'can't tell'."

**B2. The prompt tally is mislabelled and one-sided.** Beat 6, S12 and §1 proof 3 say "level one to level two: 4 better, 14 the same, 21 worse", with plain as level one. 4/14/21 is the *second* step, from classifier framing to decision tree. The first step, from plain to framing, was 15 better, 15 same, 9 worse. Plain to full decision tree was 7 better, 16 same, 16 worse (`docs/FINDINGS.md` lines 18 to 24). "A longer prompt made 21 of 39 setups worse" is also causal wording, which 01 §4 bans. There is a second problem: Cloudflare's route warns that Clef may read only about the first 2,000 state tokens (`docs/CLEF_OPENROUTER_FINDINGS.md` line 21). So the poster child, Clef 54/51/49, may be a truncation effect.
Edit: "Adding classifier framing helped about as often as it hurt. Adding the full decision tree on top of that scored lower in 21 of 39 setups and higher in 4." S12 label: "Framing to decision tree: 4 up, 14 same, 21 down". Either add the caveat "Clef may not read the whole policy" or swap Clef for Solar: 55, 53, 53 on first passes.

**B3. The launch-wave date math is wrong.** Beat 3 and S4 say "Jev launched on 15 September. Twenty-two days later, on 1 October..." The gap from 15 September to 1 October is **16 days**. OpenAI's 6 October beta is 21 days. 02 Part C carries the same error. Perplexity's 1 October date is secondary-sourced and "UNVERIFIED from Perplexity" (02 B5), which breaks S4's own rule to show only primary-sourced entries.
Edit: "Sixteen days later, on 1 October, Cloudflare and AWS shipped decision models on the same day, and Perplexity's landed that week." Fix 02 Part C too.

**B4. The talk misdescribes who made and disputed the answer key.** Beat 4 says "a reference that two humans checked". Beat 5 says "the three reviews where our own human reviewers disagreed with each other." Both statements fail against the sources:
- `docs/REFERENCE_REVIEW_V1.md` line 3: the three disputes come from "a separate Codex AI review of the development key. This is not human adjudication."
- `docs/PILOT_AUDIT.md` line 3: the 60 reviews and the key were authored by an OpenAI assistant.
- `README.md` line 171: the key was "drafted and reviewed with AI assistance; the project owner confirmed people checked all 60 reviews on 2 October 2026." Nothing says "two".

This is the most dangerous error in the outline. It is false, and it hides the strongest sceptical question: frontier LLMs scoring higher against an LLM-drafted key.
Edits:
- Beat 4: "a reference an AI drafted and people then checked, review by review".
- Beat 5: "three of those are the reviews where a second, AI review of our key said the key itself might be wrong."
- Add Q&A on authorship. A draft answer is in section 7.

**B5. The thesis line contradicts the ground truth.** §1 and beat 1 say "every one of Jev's misses was a System Two moment." 01 insight 2 says DEV-027 and DEV-059 "are clear errors under the guide." DEV-059 is a harassment report: "the manager kept asking me out even after I said no twice". Jev marked it serious concern = yes, which is right, and follow-up = no at 0.49 confidence, which is wrong. Beat 4 also contradicts itself. It first says Jev caught all 25 serious concerns, "if your workflow is about never missing the harassment report, that's the number you care about". It then says "in a workflow that escalates harassment reports, those five reviews are the whole product."
Edit: "Every one of Jev's misses landed on a review that other models also tripped on." That is the defensible version from 01 insight 2. Then use DEV-059 honestly in proof 1, as in change 3 below. Delete the "whole product" sentence.

**B6. "You get speed and price" is a forbidden speed claim.** Beat 4 says: "And that's the System One trade. You get speed and price." 01 §4 says never claim speed. Q&A 4 then answers "I can't say", which contradicts beat 4.
Edit: "You get a typed answer at a fraction of a cent. You give up the last few percent."

**B7. Slide S5's "can say the form doesn't apply: no, no, yes" row is false.** Beat 3 says "Only one of them can write back and say the form doesn't apply." Every decision model in the study had `insufficient_information` as an option. On the soup, Liquid used it on sentiment and Perplexity on sentiment and testimonial (`disputed-reviews-v1.json` DEV-029 answers). The difference was behaviour on this set, not capability. The framing is also the "dedicated vs general" dichotomy and architecture claim that 01 §4 bans. The README says outright that the soup "does not establish a model-family advantage". A TypeSafe engineer will correct this in Q&A.
Edit: cut S5 and the taxonomy paragraph. That also saves about 105 words. If something must stay: "All three can answer 'can't tell' if you give them that option. On the soup, the general models used it far more often."

**B8. The rule beat has four holes a sceptic will find within a minute.**
- (a) "The best pair was Solar Decide plus Perplexity Decider." The pair was chosen after seeing all 21 results on the same 60 reviews. That is selection, and "best" is ranking language (01 §4).
- (b) "I fixed that rule before I looked at any numbers." This overclaims. Adam had seen every single-model result. The source says the rule was "fixed before calculation" of the pairs.
- (c) "When both models share a blind spot, like all seven did on the soup, agreement doesn't catch it." The previous paragraph says this pair *deferred* the soup. The right example is Clef plus Luna: same wrong answer, accepted. Six of 21 pairs accepted the soup wrongly **(rc)**. Also, five pairs, not four, had zero accepted errors (`native-agreement-policy-v1.json`): Liquid + Tev, Liquid + Solar at 43/0/17, Solar + Clef, Solar + Clef Flash, Solar + Perplexity. 01 §6 omits Liquid + Solar. Solar sits in four of the five, which is worth one sentence.
- (d) S13 says 7 go to a person. S14's policy also sends every serious concern and every "insufficient information" to people. On this set, the Solar + Perplexity queue becomes **35 of 60 (rc)**: 7 deferred, plus 24 accepted serious concerns, plus 4 accepted "can't tell" answers. A CTO can do the 25-concerns arithmetic in their head.

Edit: replacement paragraph in top change 2.

**B9. "Nobody's confidence number was calibrated" asserts a measurement that was not made.** Beat 6 says "We did, and nobody's confidence number was calibrated." The study ran no calibration analysis (01 §7: "not reliability curves on held-out data"). The feed says "Neither is calibrated correctness probability", which is a statement about what the number *means*, not a measured result. Said in front of a vendor that trains for calibration, this invites "how did you measure that?"
Edit: "We did, on 60 reviews, and the threshold didn't separate right from wrong well enough to trust it as the gate. I haven't run a proper calibration study, so that's as far as I'd go."

**B10. Smaller spoken number errors, bundled.**
- "Five of them said sentiment mixed" (beat 5). Four said mixed, two said `insufficient_information` and Solar said negative **(rc)**. 01 insight 10 has the same error.
- "Four of the 21 pairs kept zero errors" (beat 7). It is five. See B8.
- "'Someone said it was fixed, I think.'" (beat 5, S10). This is a spliced quote. The verbatim DEV-030 text reads: "The accessibility issue from the assessment has been dealt with, I think. Someone said it was fixed, but I don't know whether..." Quote marks must hold verbatim text.
- "I ran Jev against about forty other setups" (beat 1) versus "89 of 113 general LLM setups" (beat 5). The room hears forty, then 113. The 39 is one audited cohort. The historical general cohort is 117 configurations.
- "Frontier LLMs got 58 to 59" (§1, beat 1, S2). Two of the four 59s are Gemma 4 26B A4B and Qwen3.8 27B, mid-size open models. Say "general LLMs, from a 26B open model up to Opus".

**B11. The run of show has no real buffer.** See section 3. My estimate is about 14:50 at 140 words per minute, with interaction and build costs. That is 15:10 at 130 wpm. Beat 1 alone runs about 1:34 against a 1:05 slot. The 0:35 buffer exists only on paper.
Edit: cut about 250 words. The list is in section 3.

---

## Residual findings

- **R1. Data-feed pointers are wrong on S2, S6 and S10.** `findings.json` `charts.costAgreement` has no Jev, Opus or Sonnet row, and its note says "No Jev estimate, subscription fee... is plotted". Use these sources instead:
  - S2 and S6: Jev 54 is `charts.jev`. Opus 5.5 high 59 is `charts.jev.comparators` `opus55-high-batch10`. Sonnet 5.5 is `sonnet55-fresh-matched3.json` `threePassSummary.xhigh`.
  - S10: `charts.hardCases` is the 39-configuration ranking. The 26/15/12 histogram is `disputed-reviews-v1.json` `mismatch_count_histogram`.
- **R2. S6 says "seven horizontal bars" but names five.** Specify all bars. Label configurations: Gemma 26B is thinking-on, and thinking-off scored 53. Qwen3.8 27B is low effort, and its off, medium and xhigh settings scored 54, 56 and 56. Showing each model's best setting reads as a leaderboard.
- **R3. Opus 5.5 high has three P0 passes, 59, 58 and 58** (`claude-roster-repeats.json` series `opus55-high-batch10`). 01 calls it single-pass, and Q&A 5 says "the 59 is one pass". Use "58 to 59 over three passes" against Jev's 54, 53 and 52. This strengthens the gap.
- **R4. S7 has two problems.** The "$0.006 known" charge is from the OpenRouter P0 pass, which also scored 54. The direct run that S6 uses is a token-price estimate. Separately, two circles drawn at different scales are a size comparison, which contradicts "never on one axis". Use two cards with no size encoding.
- **R5. S9 per-model answers.** The brief's "mixed / no / no / no or similar" will be drawn wrong. Exact answers, from `disputed-reviews-v1.json` DEV-029:

  | Models | Sentiment | Follow-up | Serious concern | Testimonial |
  |-|-|-|-|-|
  | Tev, Clef, Clef Flash, Luna | mixed | no | no | no |
  | Solar | negative | no | no | no |
  | Liquid | insufficient | no | no | no |
  | Perplexity | insufficient | no | no | insufficient |

  Two more fixes on S9:
  - Say "89 of 113 general setups answered 'can't tell' on all four" rather than "said not about recruitment". The README's own headline is the stricter declared first-pass cohort, 13 of 32. Have it ready.
  - Make clear Jev is not one of the seven.
- **R6. S11 moves two fields on one slide**, which breaks the deck's own one-idea-per-slide rule. It also uses green alone, which the risk table says not to do. For fairness to TypeSafe, a 0.9 gate *would* have caught Jev's worst miss, the DEV-059 follow-up at 0.49. Say so. It makes the 0.96 point more credible, not less.
- **R7. "Two one-cent models" is imprecise** (S13, moment 3). Solar costs 2.2 cents and Perplexity 1.5 cents per 60 reviews. The pair costs 3.7 cents, about 6 times a Jev pass **(rc)**. Say "two models, under four cents together for all 60".
- **R8. Appendix A6 has two wrong totals.**
  - "Whole seven-model study under $1.20" is wrong. Nine-run charges including Clef's estimate sum to $1.2013 **(rc)**. Unknown-charge bounds of $0.1285 are left out, which treats missing cost as zero, a 01 §4 violation. Say "about $1.20, including one estimate, plus up to $0.13 unknown". 01 insight 14 needs the same fix.
  - A5 pairs the DEV-006 counts with the minus 3 to plus 3 delta range. That range belongs to the all-three-flips scenario.
- **R9. "Together trained theirs for seventeen dollars."** 02 B10 only shows the README linking a tutorial titled "train your own classifier for $17". Cut the line or attribute it to the tutorial. "About fifteen others" is vague. Use "a dozen or more".
- **R10. "Jev stayed flat at 54"** is true for the first pass at each level only. P0 repeats were 54, 53 and 52. Say "Jev's first pass held at 54 on all three levels."
- **R11. "The worst pair sent 27 of 60 to a person."** That pair, Liquid + Tev, had zero errors, and "worst" is ranking language. Say "the lowest-coverage pair".
- **R12. Moment 3 is open-ended at 12:30**, with the CTA still to come. Make it a two-option show of hands, which takes about 10 seconds.
- **R13. Jev is not in the agreement panel.** The talk is about Jev, but the rule pairs only the seven. Jev's saved OpenRouter answers are public, so pairing Jev with each of the seven is an offline analysis with no new inference. If it is run, label it post hoc and descriptive. If not, have the Q&A answer in section 7 ready.
- **R14. 01b integration (§8)** will change words and timing after this review. Re-run the count script and this number audit after integration, and freeze a commit SHA for the deck.
- **R15. "Every saved answer is in the repo"** (beat 8). Some evidence is stored as public normalised copies of private originals (`privateOriginalSha256` in `claude-roster-repeats.json`). Say "every scored answer is in the repo", or check first.
- **R16. Two bio items need Adam to confirm.** "Thousands of lines of candidate feedback" is not in 03. The 03 open items, such as 1,300 versus 850, are unresolved. The bio slide does not use them, which is fine.

---

## 1. Number audit

| # | Outline number | Where | Source | Status |
|-|-|-|-|-|
| 1 | Jev 54/60 | §1, b1, S2, S6 | `findings.json` `charts.jev` (typesafe-jev113-v2) | OK |
| 2 | Jev about $0.006, "known" | b4, S7 | `JEV_NATIVE_PROMPT_FINDINGS` line 50: $0.005890920 is the OpenRouter P0 charge | Value OK. Label it as the OpenRouter pass, not the direct run |
| 3 | Opus 5.5 high 59 | b4, S2, S6 | `charts.jev.comparators`; three P0 passes 59/58/58 | OK. Repeats exist (R3) |
| 4 | Opus about $0.22 estimate | b4, S7 | `subscription-price-estimates.json` `runs.opus55-high-batch10` 0.222052 | OK |
| 5 | Sonnet 5.5 58 in all nine cells | b4 | `sonnet55-fresh-matched3.json` xhigh | OK. Feed pointer wrong (R1) |
| 6 | Gemma 4 26B 59 | b4, S6 | costAgreement `gemma4-26b-a4b-on` 59 | OK. Needs config label (R2) |
| 7 | Qwen3.8 27B 59 | b4, S6 | `openrouter-qwen27-low-darkbloom-fp4` 59 | OK. Needs config label (R2) |
| 8 | "Four to forty times the spend" | §1, b1, b4, Q&A 5 | Against $0.00589: Gemma 3.6x, Qwen 8.4x, Sonnet 5.5 20.9x per cell, Opus 37.7x **(rc)** | The range mixes observed charges with API-equivalent estimates. Q&A 5 applies the range to Opus, which is about 38x |
| 9 | "Frontier LLMs 58 to 59" | §1, b1, S2 | The 59s include Gemma 26B and Qwen 27B | MISLABEL (B10) |
| 10 | 25 of 25 serious concerns | b4 | `docs/FINDINGS.md` line 48 | OK |
| 11 | 90% vs 98% | b4 | 54/60 is 90.0%, 59/60 is 98.3% | OK. Say "agreement" |
| 12 | "About forty other setups" | b1 | 39 audited P0 setups; 117 historical general | INCONSISTENT with 113 (B10) |
| 13 | 0 of 7 decision models on soup | b5, S9 | `disputed-reviews-v1.json` DEV-029 | OK. Jev is not in the seven |
| 14 | 89 of 113 | b5, S9 | `cross-category-v1/findings.md` line 58: 89/113/117 | OK. Declared fresh is 13/28/32 |
| 15 | "Five of them said mixed" | b5 | Four mixed, two insufficient, one negative **(rc)** | WRONG (B10; 01 insight 10 too) |
| 16 | Perplexity insufficient on two fields | b5 | DEV-029 answers | OK. Liquid used it on one |
| 17 | Histogram 26/15/12/1/2/1/1/2 | b5, S10 | `disputed-reviews-v1.json` `mismatch_count_histogram` | OK. Feed pointer wrong (R1) |
| 18 | Quoted DEV-030 text | b5, S10 | `disputed-reviews-v1.json` | SPLICED (B10) |
| 19 | 0.96 testimonial, DEV-027 | b6, S11 | `jev-confidence-findings.json` | OK. Spoken line attaches 0.96 to the sentiment answer too, which was 0.71 |
| 20 | "Called the soup a serious concern at 0.91" | b6 | Confusion `insufficient_information` to `no` | WRONG (B1) |
| 21 | Sentiment at 0.9: 13 withheld, 9 right, 4 errors removed | b6, S11 | 01 §3 row 7 | OK |
| 22 | "Level 1 to 2: 4/14/21" | b6, S12, §1 | `FINDINGS.md`: P1 to P2 is 4/14/21; P0 to P1 is 15/15/9; P0 to P2 is 7/16/16 | MISLABELLED (B2) |
| 23 | Clef 54/51/49 every pass | b6, S12 | Reconciliation line 41 | OK. Truncation caveat (B2) |
| 24 | "Jev stayed flat at 54" | b6 | fresh1 54/54/54; P0 repeats 54/53/52 | Partly true (R10) |
| 25 | Solar + Perplexity: 53 accepted, 0 errors, 7 deferred, $0.0375 | b7, S13 | `native-agreement-policy-v1.json` | OK |
| 26 | "Four of 21 pairs zero errors" | b7 | Five **(rc)** | WRONG (B8, B10) |
| 27 | "Worst pair 27 of 60" | b7 | Liquid + Tev: 27 deferred, 0 errors | Value OK, wording (R11) |
| 28 | Five of Jev's six misses deferred | b7 | Deferred set covers 006, 013, 027, 029, 030 | OK |
| 29 | "Two one-cent models" | S13, M3 | 2.2 and 1.5 cents per 60 | IMPRECISE (R7) |
| 30 | Seven deferred under policy | S13, S14 | Full S14 policy gives 35 of 60 **(rc)** | MISSING (B8d) |
| 31 | 16 days, Jev to 1 October | b3, S4 | Calendar | WRONG as "twenty-two" (B3) |
| 32 | $17 Together | b3 | 02 B10: tutorial title | OVERSTATED (R9) |
| 33 | 272 tests, two live routes | b8, S15 | 04 §2, §3 | OK |
| 34 | Under $1.20 for the seven-model study | A6 | $1.2013 including the Clef estimate; plus $0.1285 unknown **(rc)** | WRONG (R8) |
| 35 | 212 up, 168 down, 257 same of 637 | Q&A 3, A5 | 01 §3 row 20 | OK |
| 36 | 20 choices drifted in 12 days | Q&A extra | 02 B1 | OK. Add "scores unchanged" |
| 37 | "A reference that two humans checked" | b4 | README line 171; PILOT_AUDIT line 3 | UNSOURCED "two"; omits AI drafting (B4) |
| 38 | "Our own human reviewers disagreed" | b5 | REFERENCE_REVIEW_V1 line 3 (Codex AI review) | WRONG (B4) |
| 39 | 1,709 words | §7 | Reviewer recount: 1,709 | OK |

## 2. Claim audit against 01 §4

| 01 §4 rule | Violation in the outline | Fix |
|-|-|-|
| Not a leaderboard | "The best pair" (b7); "the worst pair" (b7); best-setting-per-model bars (S6) | B8, R2, R11 |
| Not causal | "A longer prompt made 21 of 39 setups worse" (§1, b6, S12 title "Longer prompt, worse answers"); S5's architecture claim | B2, B7. S12 title: "More instructions, no reliable gain" |
| Not real-world accuracy | Clean. "Matched" is used throughout. "90 percent" needs the word "agreement" | Number audit #11 |
| Reference is provisional | Beat 4 and beat 5 misstate its provenance | B4 |
| Missing cost is unknown, not zero | A6 "under $1.20" | R8 |
| No speed claims | "You get speed and price" (b4) | B6 |
| No pooling | Clean. "About forty setups" and "113" are different cohorts; name them | B10 |
| Do not count invalid out | Clean | none |
| Thresholds are retrospective | "Nobody's confidence number was calibrated" | B9 |
| Hindsight oracle is not an ensemble | Clean | none |
| No pair recommended | "The best pair", plus the pair selected after seeing results | B8 |
| Decision models overlap general LLMs | S5 "no, no, yes"; the soup framed as a category property | B7 |
| Do not say models beat the key on DEV-006 | Clean | none |

## 3. Time

The 1,709-word count is correct; I recounted it independently. The estimate below uses 140 words per minute for narrative, 125 to 135 for number-dense beats, and real costs for interactions and builds.

| Beat | Words | Interaction and motion cost | Estimate | Slot | Over or under |
|-|-:|-|-:|-:|-:|
| 1 Cold open | 160 | Moment 1, two hand raises: 25 s | 1:34 | 1:05 | +0:29 |
| 2 Bio | 85 | none | 0:40 | 0:40 | 0 |
| 3 Field | 202 | S4 silence and ticks: 8 s | 1:35 | 1:30 | +0:05 |
| 4 Proof 1 | 258 (19 numerals) | builds: 4 s | 2:08 | 2:10 | -0:02 |
| 5 Proof 2 | 276 | Moment 2, two or three shouted answers repeated for the mic: 35 s; S9 flips: 8 s | 2:46 | 2:35 | +0:11 |
| 6 Proof 3 | 264 (13 numerals) | builds: 4 s | 2:11 | 2:15 | -0:04 |
| 7 Rule | 269 (13 numerals) | S13: 8 s; Moment 3: 20 s | 2:32 | 2:20 | +0:12 |
| 8 Tool and CTA | 195 | applause: 5 s | 1:29 | 1:50 | -0:21 |
| Total | 1,709 | about 2:00 non-speech | **about 14:55** | 14:25 plus 0:35 | buffer gone |

At a uniform 130 wpm, the total is about 15:10. At 150 wpm it is about 13:25. The deck carries 59 spoken numerals, roughly four a minute. Numbers slow delivery, and the counting script scores "0.96" as one word.

**Cut list, about 250 words, target 1,450 to 1,500:**
1. Remove S5 and the beat 3 taxonomy paragraph: about 105 words. This also removes B7.
2. Fold the bio into the cold open as a story, about 40 words, and drop the separate beat: saves about 45.
3. Beat 3 timeline: replace the "about fifteen others... base URL change" sentences with one line: saves about 25.
4. Beat 6: compress the prompt half to two sentences after the B2 fix: saves about 50.
5. Beat 4: drop the spoken Gemma and Qwen roll-call, since the bars carry it: saves about 12.
6. Beat 1: drop "Fast, typed, one forward pass, no text to parse", since the System 1 gloss replaces it: saves about 10.

The B8 caveats add about 40 words back. Moment 3 as a show of hands saves about 10 seconds. The result is about 1:30 of real buffer at 140 wpm.

## 4. Structure

**Skeleton.** The one-answer, three-proofs, one-rule, one-CTA shape works. Each proof answers a different clause of the blurb, and the rule is earned by proof 3. Keep it.

**Non-engineers.** Three things lose them:
- "System Two moment" arrives in the first minute but is defined only at 6:30, in beat 5. Add one sentence in beat 1: "Kahneman's System One is the fast gut answer. System Two is the slower 'wait, is this even the right question?'"
- The 1:30 "field" beat delays the first evidence to 3:15. Its taxonomy is the most jargon-heavy minute of the talk.
- Fifty-nine numerals is a lot for a mixed room. Each proof should land one number, not five.

**Spine.** The spine is carried, not just mentioned: beats 1, 5, 6 and 7 use it. But its most quotable use, "every miss was a System Two moment", is the claim that fails B5, and proof 1 uses it only for the forbidden speed line. After the fixes it still holds: the soup, the 0.96 testimonial, and the rule as "System Two built from two System One models plus a comparison". Be careful with that last line, because six of 21 pairs accepted the soup wrongly. Tell it as "it works when the models fail differently".

**Cold open.** It is not strong enough. The hand raise is for engineers only, and the room's non-engineers sit out the first 30 seconds. A stronger and fairer open: put DEV-059 on S1 and read it aloud. "Nice staff. After the trial shift the manager kept asking me out even after I said no twice. I've asked the recruiter to stop him contacting me." Then ask: "Is it a serious concern? Does someone need to follow up? Everyone here got both right in two seconds." This gives three payoffs:
- Proof 1: Jev flagged the concern and said no follow-up was needed.
- Proof 3: that miss was at 0.49, so a threshold *would* catch it, which is fair to TypeSafe.
- The rule: Solar and Perplexity both got it right, so the miss is overruled.

That is one thread through the whole talk, with stakes from the first slide.

**Close.** "Star the repo, ask me for early access" is not a Monday action. Starring is a vanity click, and early access to a private repo needs authorisation (04 §6, AGENTS.md). Replace it with the four-step Monday recipe in top change 5.

## 5. Voice and anti-slop

| Metric | Notes | Adam's spoken profile |
|-|-:|-:|
| Average sentence length | 10.1 words | 22.5 |
| Flesch-Kincaid grade (heuristic) | about 5.5 | 8.6 |
| Sentences opening with "So" | 10.6% | 8.4% |
| Sentences opening with "And" | 10.6% | 5.6% |
| Sentences opening with "I" | 4.7% | 4.4% |

The openers are on target. The rhythm is not: the notes are staccato slide copy, while Adam talks in longer, joined, warm sentences. There is almost no "we" or community language until "We're building this together", and no gratitude. A cheap, true and collegial addition: "TypeSafe publishes a page listing where Jev fails, and almost nobody does that." Source: 02 A3, the jaggedness page.

**Lines that sound off, with replacements:**
1. "So on this data the threshold buys coverage loss faster than it buys error removal, and it leaves the most embarrassing errors in." This reads like a report, with nominalised false agency. Replacement: "So on this set, the 0.9 gate threw away nine good answers to catch four bad ones, and it still let the testimonial through at 0.96."
2. "That's a System Two handoff built out of two System One models and one comparison." This is a slogan. Replacement: "So I got the 'hang on, let me check' moment without a slow model. Two fast ones, and one question: do you two agree?"
3. "So the failure surface is predictable. Off-topic, insufficient information, disputed boundaries." This is jargon plus a fragment list. Replacement: "So the misses weren't random. They landed on reviews that weren't about hiring, reviews too vague to call, and reviews where our own key wasn't sure."
4. "So more instructions were the least reliable lever in the whole study." This uses corporate "lever" and a causal claim. Replacement: "So the fix I'd reach for first, a longer prompt, was the one I'd trust least."
5. "And I want to be fair to Jev, because TypeSafe may be in the room." This makes fairness sound performative and calls people out. Replacement: "And credit where it's due."

**Anti-slop scan:**
- Clean: zero em dashes, zero double hyphens, zero curly quotes, zero emoji. Headings are in sentence case, and no Tier 2 words appear in spoken text.
- Flagged:
  - "Two honest caveats" announces honesty. Use "Two caveats".
  - "Every one." and "Vague recurrence. Uncertain resolution." are dramatic fragments. "Zero. Zero of seven." is an earned stage reveal; keep it.
  - "Not with a score" in §1 and the S11 title "Confidence is not the gate" are binary contrasts. Use "0.96 and still wrong".

## 6. Slide briefs

| Slide | Buildable from the brief? | Problem | Fix |
|-|-|-|-|
| S1 | Mostly | "Slightly blurred" soup text may be legible and spoil S8 | Specify unreadable blur, or swap in DEV-059 (section 4) |
| S2 | No | Feed pointer wrong (R1); "frontier" label | Opus 5.5 high bar, "58 to 59 over three passes" |
| S3 | Yes | none | Merge into S1 or S2 if the bio beat goes |
| S4 | No | Date math (B3); secondary dates; "smaller entries" unlisted | List each tick with date and source tier; drop UNVERIFIED rows |
| S5 | Yes, but false | B7 | Cut |
| S6 | No | Seven bars, five named; feed wrong; configs unlabelled | R1, R2 |
| S7 | Yes, but misleading | Circle scaling is a size comparison; known-charge pass mismatch | R4 |
| S8 | Yes | none | none |
| S9 | No | "Or similar" answers; Jev's role unclear; 89/113 wording | R5, exact table supplied |
| S10 | Mostly | Feed wrong; spliced quote | R1, B10 |
| S11 | Mostly | Two fields, colour only | R6. Testimonial field only: 54 kept, 1 wrong kept at 0.96 |
| S12 | No | Mislabelled tally; Clef caveat; causal title | B2 |
| S13 | Mostly | "0 errors" wording; queue size under the full policy | "0 disagreed with the key"; one line on escalation (B8d) |
| S14 | Yes | Contradicts S13's 7 without a note | B8d |
| S15 | Yes | none | none |
| S16 | Yes | CTA (section 4) | Monday recipe plus QR |

**Heroes.** S9 and S13 are the right hero moments. S4 is not: it is context, its central number is wrong, and it leans on secondary dates. Make S4 a simple build. Spend the hero budget on S11: the single red 0.96 dot that stays lit while the threshold sweeps is the most memorable evidence for builders.

## 7. Q&A

**Fixes to the existing ten answers:**
- **Answer 1.** It names only Opus and Gemma. Qwen3.8 27B, Opus 5.5 low and Sonnet 5 max also hit 59. Say "several setups reached 59, including a 26B open model."
- **Answer 2.** Add authorship: "An OpenAI assistant wrote the 60 reviews and drafted the key. People checked all 60 on 2 October."
- **Answer 3.** "Human-checked, with three disputed labels" should say the disputes came from an AI review of the key.
- **Answer 5.** "The 59 is one pass" is wrong (R3). "Four to forty times" for Opus alone should be "about 38 times, on an estimate."
- **Answer 7.** It omits Kev-4B at 46 to 49. Say "Alex 4B at 39, SemIf at 35 to 36, several at zero."
- **Answer 9.** It is a non-sequitur, and the question's premise is wrong: Jev's serious-concern *field* score was 57, while its recall on the 25 positives was perfect. Better answer: "It found all 25. Its three misses on that field were 'can't tell' reviews it called no. The testimonial miss was the train review, where 'cancelled' outweighed 'really helpful'. TypeSafe's own docs list literal reading as failure mode one."

**Missing questions, with draft answers:**
1. **TypeSafe engineer: "Did you ask a separate relevance question first? Our docs say to split judgments."** "No, and that's a fair hit. Every model got the same four questions with a 'can't tell' option. A relevance check up front is cheap, and I'd expect it to help on the soup. That's the next run."
2. **Sceptic: "Your key was written by an OpenAI model. Aren't you measuring who thinks like GPT?"** "Possibly in part. People checked all 60, and if GPT-style models had a home advantage, OpenAI's own decision model didn't get it: Luna Decisions matched 49. I can't rule out that LLM-written text suits LLMs, which is why the key is provisional."
3. **"Jev isn't in your seven or your pairs. Why?"** "The seven were a matched first-pass panel through one route. Jev's runs sit outside it. The answers are public, so pairing Jev offline is a small analysis, not new inference, and I haven't done it yet." Better still, do it before the talk (R13).
4. **CTO: "With your full policy, how big is the human queue?"** "On this set, 35 of 60 (rc): the 7 deferred, plus every serious concern going to escalation, plus four 'can't tell' answers. The set is concern-heavy by design, 25 of 60. On real feedback the share depends on how often concerns happen, which this can't tell you."
5. **"Is 54 versus 59 real on 60 reviews?"** "It held across three passes each: Jev 54, 53, 52 and Opus 59, 58, 58. On first passes, Opus matched five reviews Jev missed and missed none Jev matched. It's still one set of 60 synthetic reviews and a provisional key, so read it as a direction."
6. **"Opus ran ten reviews per request and Jev one. Fair?"** "Not identical. Batch, route and effort all differ, which is why I don't rank. It's on the limits slide."
7. **Cloudflare: "Clef reads about 2,000 tokens of state. Was your long prompt truncated?"** "Possibly. Your route warning says so, and our notes treat truncation as a constraint, not a cause."

## 8. Risks the outline misses

- **Hostile question on AI-authored data and key.** Prepare missing answer 2 and put authorship on A7.
- **Numbers moving.** The repo was last pushed 7 October and 01b is pending. Freeze a commit, print the short SHA on A7 and S16, and re-run this audit after any integration.
- **Inherited errors.** Fix 01 (insight 10 "five mixed", §6 "four zero-error pairs", insight 14 "under $1.20") and 02 Part C ("twenty-two days") so the deck, notes and site agree.
- **Other vendors in the room.** Cloudflare (Clef truncation), Perplexity (secondary launch date), OpenAI (Luna at 49), Together (the $17 line) and AWS may attend. The same collegial rules apply to all of them.
- **Saying "TypeSafe may be in the room" aloud.** Cut it.
- **Recording and stream.** Shouted answers don't reach the mic, so repeat them.
- **QR code.** Test it from the back row on the venue projector. The handle is `adambkovacs`, which is easy to mistype.
- **Early-access promise.** classification-bench is private, and AGENTS.md forbids publishing without authorisation. Confirm Adam can grant access before saying "ask me".
- **Name soup.** Jev, Kev, Tev, Clef, Luna and Laya sound alike. Say at most Jev, Opus, Solar, Perplexity and Clef aloud.
- **Hard stop.** Prepare a landing line at S13 in case the chair signals at 13:00: "That's the rule. The repo has everything else."
- **Click counts.** S9 needs either one click for seven flips or seven clicks; specify which, and rehearse S13's timing.

---

## 9. Top five changes, ranked by impact

**1. Correct every spoken number and attribution (B1, B2, B3, B4, B10).** Concrete edits:
- Beat 6: "It said the soup had no serious concern, at 0.91, when the honest answer was 'can't tell'."
- Beat 6 and S12: "Adding classifier framing helped about as often as it hurt. Adding the decision tree on top scored lower in 21 of 39 setups and higher in 4."
- Beat 3 and S4: "Sixteen days later, on 1 October, Cloudflare and AWS shipped the same day, and Perplexity that week."
- Beat 4: "a reference an AI drafted and people then checked, review by review."
- Beat 5: "three of those are the reviews where a second, AI review of our key said the key itself might be wrong."
- Beat 5: "Four of them said mixed, no, no, no."
- Beat 7: "Five of the 21 pairs let zero errors through."
- Beat 5 and S10: quote DEV-030 verbatim.
- Beat 1: "against more than a hundred other configurations".
- §1 and S2: replace "frontier" with "general".

**2. Rewrite the rule beat so it survives a sceptic (B8, R7, R11).** Replace the middle of beat 7 with:
> "I wrote that rule down before I computed a single pair, then ran it on all 21 pairs of the seven decision models. Five pairs let zero errors through. The one on the slide, Solar Decide plus Perplexity Decider, agreed on 53 and sent 7 to a person, for under four cents for both. I picked it after seeing all 21, so it's an example, not a winner. Two caveats. Zero errors on these 60 is not zero errors on the next 60. And agreement only helps when the models fail differently: six pairs gave the soup the same wrong answer and accepted it. If you also send every serious concern to your escalation team, which you should, more of this concern-heavy set reaches a person, and on your data that share depends on how often concerns really happen."

**3. Fix the thesis and proof 1 (B5, B6, B9).**
- §1 and beat 1: "So on 60 test reviews, Jev matched our provisional key on 54, general models matched 58 or 59 for roughly four to forty times the estimated spend, and every Jev miss landed on a review other models also tripped on. So if the decision matters, what you buy is a rule that hands the hard ones to a person."
- Beat 4, replacing the harassment and speed lines: "And here's the miss I'd worry about. A candidate wrote that a manager kept asking them out after they said no twice. Jev flagged it as a serious concern, which is right, and said nobody needed to follow up, which is not. It was only 0.49 confident, so hold that number for proof three. You get a typed answer at a fraction of a cent, and you give up the last few percent."
- Beat 6: use the B9 calibration wording.

**4. Cut about 250 words and the false slide (B7, B11, R12).**
- Delete S5 and the taxonomy paragraph.
- Fold the bio into the cold open, ideally the DEV-059 open from section 4.
- Compress beat 6's prompt half to the two sentences in change 1.
- Make moment 3 a show of hands: "Hands up for one model at 0.96. Hands up for two models that agree."
- Re-run the counting script and aim for 1,450 to 1,500 words.

**5. Give builders a Monday action and arm the Q&A (section 4, section 7).**
- Replace the end of beat 8: "So here's what I'd do on Monday. Pull 60 of your own cases and label them yourself, before any model sees them. Give every question a 'can't tell' option. Run two cheap decision models and keep only the answers they agree on. Then count two things: how many land in the human queue, and whether the rare cases you care about made it through. Everything I used is in the public repo, and if you find a review that fools all seven, send it to me. We're building this together. Thank you."
- S16: "Monday: label 60, add 'can't tell', run two, count the queue." Add the QR code.
- Add the seven missing Q&A answers from section 7, led by AI authorship of the key and the relevance-question challenge.
