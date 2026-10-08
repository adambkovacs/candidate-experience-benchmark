# 05r3 Outline review: final diff-check of v2.2

Reviewer: independent reviewer agent, the same one that wrote 05r and 05r2. Date: 2026-10-08.

Reviewed: `05-session-outline.md` v2.2 at `c3aad25e`, the writer's commit. The check covers everything that changed from `f269fda6`:
- N1, N2 and N3 from 05r2
- the four late additions: the blast-radius paragraph and Q&A 18, the S9 hard-six card wall, A11's two ranges, and A13 to A18
- the v2.2 cost wording, checked against `06-cost-check.md` (`0bd7b0fd`)

Method:
- Re-derived every S5 cell, S9 counter and A13 to A18 answer from `common.load_all()` and `public-site/disputed-reviews-v1.json`.
- Checked every cost figure against 06.
- Ran `scripts/count-notes.ts` and `audit-slop.ts`.

**(rc)** marks a reviewer-computed number.

Process note: before the lead changed the instruction, my commit `aeaa84ee` had already edited the outline. It added the cost figures and fixed the two blocking items below. Per the lead's instruction, this commit restores the outline to the writer's v2.2 byte for byte. My edits stay in history at `aeaa84ee` if anyone wants to reuse them. Only the review file is new.

---

## Verdict: REVISE

v2.2 has two blocking items. Each is a one-sentence wording fix in the spoken notes, plus a matching caption change on S5. Nothing else blocks:
- N1, N2 and N3 are fixed in the text.
- Every number in the late additions reproduces.
- The cost wording matches 06.
- The spoken total is 1,560 words, under 1,600, and the anti-slop audit finds 0 instances.

With the two edits below, the outline is fit for stage. The edits add about 20 words, for a total of about 1,580.

## Blocking items

**F1. "Nine runs per model" is false for one of the five models on S5.**
- Beat 4 says: "Each model ran three prompt versions and three fresh passes, nine runs per model."
- The S5 title says "Five reviews, nine runs each". The caption says "three prompt versions, three fresh passes, nine runs per model". The intended feeling is "it held across nine runs".

Qwen3.8 27B low, one of the five matrices, has only three runs: one pass per prompt, scoring 59, 56 and 53 **(rc)**. The slide would show six blank cells under a caption claiming nine runs, and Qwen did not "hold". It fell to 53 under the decision tree. The other four models do have nine-cell series:

| Model | Runs |
|-|-|
| Opus 5.5 high | 59, 58, 58 / 59, 59, 58 / 59, 58, 58 |
| Sonnet 5.5 xhigh | 58 in all nine |
| Gemma 26B on, fresh passes | 59, 56, 58 / 58, 58, 57 / 57, 56, 56 |
| Jev via OpenRouter | P2 fresh2 was stopped at 15 of 17 valid answers, which S5 shows as "blank" |

Edits:
- Beat 4: "Most of these models ran three prompt versions with three fresh passes each, nine runs, and where a cell on the slide is blank, that run doesn't exist."
- S5 title and run-of-show line: "up to nine runs".
- S5 caption: "three prompt versions, three fresh passes, up to nine runs per model; blank means no run".
- S5 brief: label Qwen "one pass per prompt only: 59, 56, 53, so six cells blank". Write out Gemma's fresh cells, and mark Jev's stopped cell "interrupted".
- Feeling: "it mostly held across the runs that exist".
- Feed pointer: use `extended-cases-v1.json` for the Gemma fresh passes. `codex-fresh-repeats.json`, the current pointer, holds Codex runs.

**F2. The beat 5 card wall switches polarity, so the soup line contradicts the S8 reveal.**
- The first card is framed as misses: "all seven decision models missed it".
- The next cards give bare counts: "one of seven", "two of seven", then "Great soup: off-topic, zero of seven".
- In the "missed" frame a listener hears "zero of seven missed the soup", 30 seconds after S8 showed that none of them got it right. The S9 counters themselves count matches.

Edit: "uncertain resolution, and none of the seven decision models got it right. 'That thing happened again': vague recurrence, one of seven got it right." The remaining counts then read in the same frame.

## N1, N2 and N3 from 05r2

| Item | Status | Text in v2.2 |
|-|-|-|
| N1 confidence and the soup | Fixed | Beat 6: "Jev's ten least-confident reviews include seven of the ten hardest, the soup among them, but only through the sentiment field. On follow-up, concern and testimonial, the fields where you'd act, it said no at 0.84 to 0.91." §1 proof 3 matches. |
| N2 "calibrated" | Fixed | Beat 6: "On these 60 reviews, Jev's confidence tracked how often it was right". S10 headline: "Close to its hit rate here." The footnote says "60 reviews, descriptive". A4 says descriptive-only. |
| N3 escalation wording | Fixed | Beat 7: "any review either model flags as a serious concern goes to a person, whatever else the two agree on. Here every pair's flags together caught all 25, though Tev alone missed two and Clef flagged a 26th." S13, A10 and Q&A 14 match. Q&A 14 says 6 by disagreement and 4 by "can't tell". |

## The four late additions

| Addition | Check | Result |
|-|-|-|
| Blast-radius paragraph (beat 4) and Q&A 18 | 31 of 50 decision groups unchanged over three passes (01b §12.4, recounted from `s07`); Perplexity 54 of 60 in all nine runs with identical errors (01 insight 6) | Numbers hold. Tone is a residual |
| S9 hard-six card wall | Decision-model matches, from `disputed-reviews-v1.json` **(rc)**: DEV-030 0, DEV-029 0, DEV-006 1, DEV-013 2, DEV-027 3, DEV-059 5 of 7. Run-passes matched, from `common.load_all()` **(rc)**: 144, 661, 262, 287, 800, 713 of 1,004. General cohort: 128, 646, 231, 231, n/a, 633 as 01b states. My category split gives 645 for DEV-029, which is immaterial. Trigger phrases are verbatim from the review texts | All reproduce. The brief calls the order "01b difficulty order", but it is ordered by decision-model matches; that is a residual |
| A11 two ranges | "Some definite label 25% to 31%; the nearest label, no, 21% to 26%" | Matches corrected 01b (`be88acc0`) and `s02` |
| A13 to A18 | All 42 per-model answer vectors and their miss flags, compared with `disputed-reviews-v1.json` **(rc)** | All match |

## v2.2 cost wording against 06-cost-check.md

| Where | v2.2 says | 06 says | Match |
|-|-|-|-|
| Header | Every OpenRouter-routed run on a slide is a known provider charge, Clef and Jev via OpenRouter included; Jev direct on TypeSafe is an estimate (no billing API); subscription runs are API-equivalent estimates | Verdict bullets and slide-label table | yes |
| S6, §1 | Jev $0.006 known provider charge (OpenRouter pass); Opus $0.22 API-equivalent estimate | Jev via OpenRouter $0.00589092 known (§1); Claude subscription runs are estimates | yes |
| S12 | Solar + Perplexity $0.037 known; Qwen + Gemma $0.069 observed | Both runs exact matches (§1, §2) | yes |
| A6 | All seven known charges through OpenRouter, Clef $0.032 included; nine-run series $1.2013 known plus up to $0.13 of unknown bounds | §1 tables; Solar and Clef Flash bounds $0.1048576 + $0.02359296 | yes |
| Q&A 19 | OpenRouter $12.65 across 15,135 saved generations plus up to $3.88 unknown; Cloudflare direct under $0.26; TypeSafe direct an estimate; subscriptions API-equivalent | $12.653729, 15,135 generations, $3.883743 (§4); $0.259584 upper bound (§5); §3 | yes |

## Words and timing

The count-notes output for v2.2:

| Beat | Words |
|-|-:|
| 1 | 121 |
| 2 | 61 |
| 3 | 64 |
| 4 | 308 |
| 5 | 264 |
| 6 | 268 |
| 7 | 296 |
| 8 | 178 |
| **Total** | **1,560** |

Timing estimate, using the 05r2 rates plus about 20 seconds for the S9 card wall's per-click animation:

| Pace | Estimate | Buffer |
|-|-:|-:|
| Mixed: 140 wpm narrative, 130 to 135 for number-dense beats | about 14:10 | about 0:50 |
| Uniform 130 wpm | about 14:30 | about 0:30 |
| Uniform 150 wpm | about 12:55 | about 2:05 |

Beat 4, at about 2:25 against a 2:05 slot, and beat 5, at about 3:10 against 2:35, carry the overrun. The section 6 cut order frees about 60 seconds. The F1 and F2 edits add about 10 seconds.

## Residual items, not blocking

- **R1. Blast-radius tone.** "Good luck building your brilliant startup without being able to hire people willing to work for you" reads as sarcasm aimed at founders in the room, TypeSafe included. "It trends" is a guess, not data. Softer version: "and it spreads, and then you're trying to hire people who've read it." This is Adam's call.
- **R2. Dangling reference in beat 4.** "Jev caught all 25 reviews where the key flags a serious concern. But on that same review..." has no single review for "that same review" to point at. Add "including the one I read you" to the first sentence.
- **R3. Card-wall timing.** Cap each S9 card's auto-play at about 3 seconds so the six clicks don't add 40 seconds. Also describe the order as decision-model matches, not "01b difficulty order".
- **R4. Q&A 19's Gemini wording.** "Claude, Codex and Gemini ran on subscriptions" is true of the subscription Gemini runs only. The OpenRouter Gemini runs are known charges and sit inside the $12.65. Say "the Claude, Codex and Gemini subscription runs".
- **R5. Small wording mismatches.** A12 still says "44 run-passes from seven families", where beat 7 says "seven models from three vendors". A7 says "person-checked", where everywhere else says "people".
- **R6. Unqualified wording outside the outline.** The 01 change in `ea8d2494`, which the site panel draws on, says Jev's confidence "is calibrated on average" without the "on these 60 reviews, descriptive-only" qualifier the outline now carries. 01 §6 says "calibrated on average ... but not on these reviews", but the 0.011 was measured on these reviews. 01 insight 14 and its corrections line still call Clef's $0.3113 a list-price estimate, which 06 shows is a known charge.
