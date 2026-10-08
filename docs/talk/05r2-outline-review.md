# 05r2 Outline review: delta re-review of 05-session-outline.md v2

Reviewer: independent reviewer agent, the same one that wrote 05r. Date: 2026-10-08. Reviewed: `05-session-outline.md` v2 at commit `3b00c31e`.

Scope:
- the 11 blocking findings from 05r, checked in the text itself, not in the changelog
- every number that is new in v2, mostly from 01b
- timing with the three audience moments
- voice and anti-slop on the rewritten notes

Method: I re-ran `s02_confusion.py`, `s07_repeatability.py`, `s08_confidence.py`, `s09_quirks.py`, `s11_agreement_general.py` and `s12_escalation_queue.py` with `python3 -I`. I also read `public-site/deck/data/*.json` and `jev-confidence-findings.json`, and recomputed the pass sensitivity and the Jev pairs directly from `common.load_all()`. **(rc)** marks a reviewer-computed number.

The inherited errors in 01 and 02 are already fixed in `05528718`, `0bbe06f6` and `29b5712f`. v2's section 6 and section 8 still list them as open; see R1.

---

## Verdict: REVISE

Two blocking items remain. Both sit in proof 3, beat 6 and slide S10, and each is a one- or two-sentence fix. Once those lines change, v2 is fit for stage. A diff check of beat 6, §1 proof 3 and S10 is enough; it does not need another full review.

All 11 v1 blocking findings are fixed in the text. Every other new number reproduces from the scripts and feeds, except one small appendix slip (R6).

## Blocking items

**N1. Beat 6 says Jev's confidence does not flag the soup review. The data says it does, and this is a finding in Jev's favour.**
- v2 beat 6: "Jev's ten least-confident reviews include seven of the ten hardest in the whole study, so it knows 'hard'. It does not know 'off-topic', because on the soup it said no serious concern at 0.91."
- §1 proof 3: "so the number knows 'hard', not 'off-topic'."

The soup review is one of those seven. `s08_confidence.py` lists Jev's ten least-confident reviews at first P0 as 013, 056, 010, 029, 053, 057, 059, 030, 022, 005. DEV-029 is there, ranked 4 of 60 through its sentiment confidence of 0.46. 01b §8 says Jev is "the only one that would have flagged the off-topic review by rank".

As written, the talk contradicts its own previous sentence, and it undersells Jev on exactly the point TypeSafe would correct from the floor. The accurate finding (01b §8) is narrower: confidence did not flag the soup *on the three fields that drive a business decision*. Jev said no at 0.84, 0.91 and 0.88 on follow-up, concern and testimonial.

Edit beat 6: "Jev's ten least-confident reviews include seven of the ten hardest in the whole study, and the soup is one of them, but only because of the sentiment field. On follow-up, concern and testimonial, the fields where you'd act, it said no at 0.84 to 0.91. So the number can tell you a review is hard. It can't tell you which answer to distrust."

Edit §1 proof 3 to match: "so the number flags 'hard', but not on the fields you act on."

**N2. "Calibrated on average" is an unqualified general claim, shown on screen.**
- v2 beat 6: "on average it is calibrated."
- S10 headline: "Calibrated on average."

What the data actually holds:
- The ECE of 0.011 is descriptive. It pools 720 answers from the same 60 synthetic texts across three prompts that barely change Jev's answers.
- 01b tags it **descriptive-only**, and 01b §8's own opening says "no model's confidence is calibrated".
- 01 §7 says no model "has demonstrated calibration".

v1's B9 asserted the opposite without a measurement. v2 now overclaims in the other direction. An independent benchmark's slide reading "Calibrated on average" is easy to quote out of context.

Edits:
- Beat 6: "On these 60 reviews, Jev's confidence tracked how often it was right: pooled over 720 answers the average gap was 0.011, while Clef Flash's was 0.358."
- S10 headline: "Close to its hit rate here. Still 0.96 on a wrong testimonial."
- Last line of beat 6: "A confidence that tracks its hit rate on average is still not a per-review gate."

---

## The 11 v1 blocking findings, checked in the text

| 05r finding | Status in v2 text | Evidence |
|-|-|-|
| B1 soup answer reversed | Fixed | Beat 5: "it said no serious concern at 0.91 confidence when the honest answer was 'can't tell'"; beat 6 agrees |
| B2 prompt tally mislabelled, causal, Clef | Fixed | Beat 6 states the 15/15/9 and 4/14/21 steps "in these saved runs", with no causal verbs and a 2,000-token Clef caveat; S11 and A3 match `prompt-levels.json` `tally_39_setups` |
| B3 date math | Fixed | "About two weeks later, on 1 October" (16 days). See R3 on Perplexity's unverified row |
| B4 key provenance | Fixed | Beat 4 says an AI assistant drafted the reviews and key and people checked them. Beat 5 says the disputes came from "a second, AI review of our key". Small wording residual in R2 |
| B5 thesis contradiction | Fixed | §1 says "most of Jev's six misses sat on reviews a person would pause on, but two were plain errors". "Whole product" is gone. DEV-059 threads through cleanly |
| B6 speed claim | Fixed | No speed or "faster" claim in the notes; Q&A 4 says speed was not measured |
| B7 false S5 taxonomy | Fixed | S5 and the taxonomy paragraph are cut |
| B8 rule beat (a to d) | Fixed | Beat 7 says the rule was written "before computing a single pair". It says the example was "picked after seeing all 21", "five pairs let zero errors through" and "six of the 21 pairs gave the soup the same wrong answer". It gives the queue as "from 7 to 35 of 60". `s12_escalation_queue.py` and `s12_full_policy_routing.py` agree at 35 |
| B9 unmeasured calibration claim | Replaced, but the replacement introduces N1 and N2 | See above |
| B10 small spoken errors | Fixed | "Four of them said the sentiment was mixed"; five zero-error pairs; DEV-030 quoted verbatim; "forty setups" removed, so only 113 is spoken; "frontier" applies only to Claude, GPT and Gemini |
| B11 no buffer | Fixed | See the timing section: about 13:55 at mixed rates, 1:05 buffer |

## New numbers in v2, audited

| Number in v2 | Where | Check | Status |
|-|-|-|-|
| Jev ECE 0.011, Clef Flash 0.358, 720 answers | §1, beat 6, S10, A4 | `s08_confidence.py` ECE table | Reproduces. Wording is N2 |
| A4 ECE row: Liquid 0.035, Tev 0.047, Luna 0.074, Solar 0.145, Clef 0.217 | A4 | same | Reproduces |
| Seven of ten hardest in Jev's least-confident ten | beat 6 | `s08` low-confidence table, overlap 005, 010, 013, 022, 029, 030, 059 | Reproduces. Conclusion drawn is N1 |
| Confidence vs probability: Jev +0.016, over 0.2 on 0.6%; Clef Flash 55% | Q&A extra, A4 | `s08` | Reproduces |
| DEV-059 follow-up at 0.49 | beat 4, beat 6, S10 note | `jev-confidence-findings.json` P0 follow-up wrongCases | Reproduces (probability 0.65) |
| 44 run-passes, one identical answer set, missing exactly DEV-006, 013, 030 | beat 7, A12 | `s09_quirks.py` Q7b | Reproduces. "Seven families" overstates spread (R4) |
| Qwen3.8 27B low + Gemma 26B on: 58 accepted, 0 errors, 2 deferred, $0.0686 observed | §1, beat 7, S12, A12 | `s11` Table A row 1, $0.06855 | Reproduces |
| "On other Gemma passes that pair let one error through" | beat 7 | **(rc)** from `common.load_all()`: Gemma fresh2 gives 57 with 1 error, fresh3 gives 59 with 1 error, both DEV-013; original and fresh1 give 58 with 0 | Reproduces |
| 35 of 853 pairs dominate Solar + Perplexity, none with a decision model | beat 7, A12 | `s11` line 49: 35; top ten all general | Reproduces. Wording is R5 |
| Gemma 31B off + DeepSeek Flash low: 55, 0, 5, $0.0207 | A12 | `s11` | Reproduces |
| Qwen 35B off agrees with itself on 9 wrong answers | A12 | `s11` self-repeat line | Reproduces |
| 89 of 113 general configurations said "can't tell" on all four | beat 5, S8 | `cross-category-v1/findings.md` line 58 | Reproduces. The changelog says "117" is used, but 117 is never spoken, which is fine |
| 31 of 50 decision groups vs 11 of 202 general groups unchanged over three passes | A9 | **(rc)** recount of `s07` table: 31/50 and 11/202 | Reproduces |
| "Insufficient" answered as a definite label 22% to 26% | A11 | `s02`: insufficient to no is 22.0%, 25.9% and 21.3% | Should be 21% to 26%, as 01b states (R6) |
| Decision runs 19% to 45%, general 71% to 84% on reference-insufficient cells | A11 | 01b §12.1 | As stated in 01b; not re-derived |
| Jev 54, 53, 52 and Opus 59, 58, 58 | beat 4, S2, S5 | `jev-native-prompt-findings.json`; `claude-roster-repeats.json` | Reproduces |
| About 38 times for Opus | Q&A 5 | 0.222052 / 0.00589092 = 37.7 | Reproduces |
| Queue 35 of 60; Clef + Perplexity 33; range 32 to 42 | beat 7, S13, A10, Q&A 14 | both `s12` scripts | Reproduces |
| Deck feeds | S2, S4, S5, S9, S11 | `public-site/deck/data/` | Values match. The pointer `prompt-levels.json` `jev_openrouter.P0` should be `models.jev_openrouter.P0`. Perplexity's 1 October row is `verified: false` (R3) |

## Timing

My counter gives 1,569 words; the project counter gives 1,558. The 11-word difference is all in beat 7 and does not matter. The estimate uses 140 wpm for narrative and 130 to 135 for number-dense beats, plus non-speech costs:
- moment 1: 25 s
- moment 2: 35 s
- moment 3: 15 s
- S8 flips: 18 s for nine clicks
- S10: 10 s
- S12: 12 s
- builds: 12 s
- applause: 5 s

| Beat | Words | Estimate | Slot | Over or under |
|-|-:|-:|-:|-:|
| 1 | 121 | 1:17 | 1:10 | +0:07 |
| 2 | 61 | 0:28 | 0:25 | +0:03 |
| 3 | 94 | 0:44 | 1:00 | -0:16 |
| 4 | 243 | 1:56 | 2:05 | -0:09 |
| 5 | 263 | 2:50 | 2:35 | +0:15 |
| 6 | 268 | 2:14 | 2:20 | -0:06 |
| 7 | 337 | 3:03 | 2:35 | +0:28 |
| 8 | 182 | 1:23 | 1:40 | -0:17 |
| Total | 1,569 | **about 13:55** | 13:50 + 1:10 | about 1:05 buffer |

At a uniform 130 wpm the total is about 14:15. At 150 wpm it is about 12:40. That is deliverable.

Beat 7 is the pressure point: 337 words, 20 numerals, two hero clicks and moment 3, running about 30 seconds over its slot. The cut order in section 6 already names the Qwen + Gemma re-sort as the second cut. If rehearsal runs long, move it to A12 entirely.

## Voice and anti-slop

| Metric | v1 | v2 | Adam spoken profile |
|-|-:|-:|-:|
| Average sentence length | 10.1 | 17.2 | 22.5 |
| Flesch-Kincaid (heuristic) | about 5.5 | about 8.2 | 8.6 |
| "So" openers | 10.6% | 15.4% | 8.4% |
| "And" openers | 10.6% | 6.6% | 5.6% |
| "I" openers | 4.7% | 5.5% | 4.4% |
| Spoken numerals | 59 | 70 | none |

The rhythm is much closer to Adam: joined sentences, warmer, with credit to TypeSafe for its failure-mode page and a community close. Two things to watch:
- "So" now opens 14 of 91 sentences. Drop it from three or four, for example the second "So" in beat 5 and the "So this is what I'd do on Monday" opener.
- Number density went up even as words went down. Beat 4, beat 6 and beat 7 each carry 18 to 20 numerals.

The anti-slop scan is clean: no em dashes, curly quotes or emoji, and no Tier 2 words in the notes. Every match on "honest" is an "honest answer" or the "honest replay badge", not an announcement of honesty. The only binary contrast is the N1 line, which the fix removes.

## Residual items, not blocking

- **R1. Stale rows.** Section 6 "Inherited errors in 01 and 02" and section 8's "Fix the inherited errors" are already done. Delete the risk row and the open item, and cite `05528718`, `0bbe06f6` and `29b5712f`.
- **R2. Key-checker wording.** Beat 4 and A5 say "a person checked all 60", and beat 4 adds "review by review". Q&A 2 and 12 say "people". The source (`README.md` line 171) says the owner "confirmed people checked all 60 reviews". Use "people checked all 60" everywhere.
- **R3. Perplexity's 1 October date.** `timeline.json` marks it `verified: false`, so under S4's own "verified entries only" rule the "Perplexity ticks in the same week" build cannot be drawn. The verified Perplexity row is the 7 October OpenRouter listing. Say "Perplexity's within the week, by press reports", or drop Perplexity from the spoken line.
- **R4. "44 run-passes from seven families"** (beat 7). They are seven models from three vendors, and 34 of the 44 are OpenAI GPT models (`s09` Q7b). They also agree on the three reviews where our key is in doubt. Say "seven models from three vendors gave one identical answer set, and it differs from our key only on the three labels we're not sure of."
- **R5. "35 pairs beat Solar plus Perplexity on coverage and cost."** "Beat" is ranking language, which the risk table itself bans. The sentence also follows the Qwen + Gemma pair, which is *not* one of the 35: at $0.069 it costs more than Solar + Perplexity's $0.037. Say "and 35 other pairs had more coverage at lower cost, the cheapest accepting 55 for about two cents; none had a decision model in it."
- **R6. A11 range.** "22% to 26%" should be "21% to 26%". The values are 21.3%, 22.0% and 25.9% (`s02`).
- **R7. Perplexity's soup answer.** Beat 5 says "Liquid and Perplexity said 'can't tell' on the sentiment, and still answered no on the business fields." Perplexity also said "can't tell" on testimonial, and the S8 card behind Adam shows it. Say "and still answered no on follow-up and concern".
- **R8. Gate field.** Beat 6 says "On sentiment, a 0.9 gate threw away nine good answers to catch four bad ones, and it still let that testimonial through." The testimonial passes the gate on the testimonial field. Say "and on the testimonial field the same gate still let it through."
- **R9. Q&A 13 is stale.** 01b's `s11` pool already includes both Jev runs, in Table B. Jev's OpenRouter fresh1 run is classed there as an estimate, although the Jev findings doc records a known charge. **(rc)** pairs from that pool, all retrospective and post hoc:

  | Pair | Accepted | Errors | Deferred | Error IDs |
  |-|-:|-:|-:|-|
  | Jev + Solar | 55 | 1 | 5 | DEV-013 |
  | Jev + Perplexity | 53 | 1 | 7 | DEV-006 |
  | Jev + Clef | 53 | 2 | 7 | DEV-006, DEV-029 |

  No Jev pair with a native decision model kept zero errors. The best zero-error Jev pairs use general models, for example Jev + DeepSeek V4.1 Flash low at 54 accepted, 0 errors, 6 deferred, $0.021. Replace "I haven't done it yet" with these numbers, labelled post hoc.
- **R10. S10 dot encoding contradicts itself.** "Dots below it turn hollow" and "one red hollow-ringed dot at 0.96 stays lit" cannot both hold, because the 0.96 dot stays above the line and should stay filled. Make kept dots filled and withheld dots hollow, and draw the DEV-027 dot filled with a red ring.
- **R11. Feed pointer.** In S2 and S5, `prompt-levels.json` `jev_openrouter.P0` should be `models.jev_openrouter.P0`.
- **R12. Bio line.** "Every vendor told me their classifier was accurate" is broader than 03 supports. v1's "vendors kept telling me" was safer.
