# 05r3 Outline review: final pass on v2.1 and v2.2

Reviewer: independent reviewer agent, the same one that wrote 05r and 05r2. Date: 2026-10-08.

Scope, per the lead's brief:
- the N1, N2 and N3 fixes from 05r2
- the four late additions: the blast-radius paragraph and Q&A 18, the S9 hard-six card wall, A11's two ranges, and A13 to A18
- two cost edits from `06-cost-check.md` (`0bd7b0fd`)

Commits reviewed:
- `3450c5cc` (v2.1), which the lead froze
- `c3aad25e` (v2.2), which the writer committed after the freeze. v2.2 only relabels costs, adds Q&A 19 and trims beats 6 and 7. It does not touch any of the problems below.

Method:
- Re-derived every S5 cell, S9 counter and A13 to A18 answer from `common.load_all()` and `public-site/disputed-reviews-v1.json`.
- Checked each cost figure against `06-cost-check.md`.
- Recounted words with `scripts/count-notes.ts` and re-ran `audit-slop.ts`.

---

## Verdict: APPROVE, with the reviewer's edits in this commit

The text as frozen at `3450c5cc` and as committed at `c3aad25e` would have been **REVISE**, on two blocking items. I own the file now, so I fixed both in this commit with minimal edits. Both fixes are listed below and in the new last rows of section 9.

With those edits, the outline is fit for stage. N1, N2 and N3 are fixed in the text. The late additions' numbers all reproduce. The spoken total is 1,585 words, under the 1,600 ceiling. The anti-slop audit finds 0 slop instances.

I wrote the fixes myself, so I am grading my own work here. A two-minute independent read of this commit's diff to `05-session-outline.md` (22 lines in, 18 out) is worth doing before deck export.

## Blocking items found, and fixed in this commit

**F1. "Nine runs per model" is false for one of the five models on S5.**
- Beat 4 said: "Each model ran three prompt versions and three fresh passes, nine runs per model."
- The S5 caption and run-of-show line repeated it, and the brief's intended feeling was "it held across nine runs".

Qwen3.8 27B low, one of the five matrices, has only three runs: one pass per prompt, scoring 59, 56 and 53 **(rc)**. The slide would show six blank cells under a caption claiming nine runs. "It held" is also untrue for Qwen, which fell to 53 under the decision tree. The other four models do have nine-cell series:

| Model | Runs |
|-|-|
| Opus 5.5 high | 59, 58, 58 / 59, 59, 58 / 59, 58, 58 |
| Sonnet 5.5 xhigh | 58 in all nine |
| Gemma 26B on, fresh passes | 59, 56, 58 / 58, 58, 57 / 57, 56, 56 |
| Jev via OpenRouter | one P2 fresh2 pass was stopped at 15 of 17 valid |

Edits:
- Beat 4: "Most of these models ran three prompt versions with three fresh passes each, nine runs, and where a cell on the slide is blank, that run doesn't exist."
- S5 title and run-of-show line: "up to nine runs".
- S5 caption: "... up to nine runs per model; blank means no run".
- The Qwen matrix is labelled "one pass per prompt only: 59, 56, 53, so six cells blank". Gemma's fresh cells are written out, and Jev's stopped cell reads "interrupted".
- Feeling: "it mostly held across the runs that exist".
- Feed pointer: `extended-cases-v1.json`, replacing `codex-fresh-repeats.json`, which holds Codex runs, not the Gemma passes.

**F2. The beat 5 card wall switched polarity mid-list, so the soup line contradicted the S8 reveal.**
- The first card was framed as misses: "all seven decision models missed it".
- Every later card gave a count with no verb: "one of seven", "two of seven", then "Great soup: off-topic, zero of seven".
- In the "missed" frame a listener hears "zero of seven missed the soup", 30 seconds after S8 showed that none got it right. The S9 counters themselves count matches.

Edit: "none of the seven decision models got it right", then "one of seven got it right". The remaining counts now read in the same frame.

## N1, N2 and N3 from 05r2

| Item | Status | Text now |
|-|-|-|
| N1 confidence and the soup | Fixed | Beat 6: "Jev's ten least-confident reviews include seven of the ten hardest, the soup among them, but only through the sentiment field. On follow-up, concern and testimonial, the fields where you'd act, it said no at 0.84 to 0.91." §1 proof 3 matches. |
| N2 "calibrated" | Fixed | Beat 6: "On these 60 reviews, Jev's confidence tracked how often it was right". S10 headline: "Close to its hit rate here." The footnote says "60 reviews, descriptive". A4 says descriptive-only. |
| N3 escalation wording | Fixed | Beat 7: "any review either model flags as a serious concern goes to a person, whatever else the two agree on. Here every pair's flags together caught all 25, though Tev alone missed two and Clef flagged a 26th." S13, A10 and Q&A 14 match. Q&A 14 says 6 by disagreement and 4 by "can't tell". |

## The four late additions

| Addition | Check | Result |
|-|-|-|
| Blast-radius paragraph (beat 4) and Q&A 18 | 31 of 50 decision groups unchanged over three passes (01b §12.4; recounted earlier from `s07`); Perplexity 54 of 60 in all nine runs with identical errors (01 insight 6) | Numbers hold. Tone is a residual |
| S9 hard-six card wall | Decision-model matches, from `disputed-reviews-v1.json` **(rc)**: DEV-030 0, DEV-029 0, DEV-006 1, DEV-013 2, DEV-027 3, DEV-059 5 of 7. Run-passes matched, from `common.load_all()` **(rc)**: 144, 661, 262, 287, 800, 713 of 1,004. General cohort: 128, 646, 231, 231, n/a, 633 as stated in 01b. My category split gives 645 for DEV-029, which is immaterial. Trigger phrases are verbatim from the review texts | All reproduce. The order is by decision-model matches, not 01b's all-run order, so the brief now says so |
| A11 two ranges | "Some definite label 25% to 31%; the nearest label, no, 21% to 26%" | Matches corrected 01b (`be88acc0`) and `s02` |
| A13 to A18 | All 42 per-model answer vectors and their miss flags, compared with `disputed-reviews-v1.json` **(rc)** | All match |

## Cost edits

v2.2 had already rewritten the header note, A6, the cost risk row and the open item from 06, and had added Q&A 19. I added the two pieces the lead asked for that were still missing:
- **Header.** It now names the figures: Clef at $0.03184656, which earlier notes called an estimate, and Jev via OpenRouter at $0.00589092 per pass. Both are known provider charges. Jev direct on TypeSafe stays an estimate.
- **Q&A 19.** It now ends: "The seven decision models' nine-run series came to $1.2013 in known charges, plus up to $0.13 of unknown-charge bounds."

| Figure in the outline | 06-cost-check.md | Match |
|-|-|-|
| OpenRouter $12.65 across 15,135 saved generations | $12.653729, 15,135 generations (§4) | yes |
| Up to $3.88 of unknown-cost reservations | $3.883743 (§4) | yes |
| Cloudflare direct under a $0.26 upper bound | $0.259584; billing endpoint returned authentication error 10000 (§5) | yes |
| Clef $0.03184656, known | §1, exact match; nine-run series $0.31128624, known | yes |
| Jev via OpenRouter $0.00589092, known; direct an estimate | §1, §3 | yes |
| Seven-model nine-run total $1.2013 known plus up to $0.13 unknown | §1 series table; Solar and Clef Flash bounds $0.1048576 + $0.02359296 | yes |

## Words and timing

The count-notes output, pasted into section 10:

| Beat | Words |
|-|-:|
| 1 | 121 |
| 2 | 61 |
| 3 | 64 |
| 4 | 327 |
| 5 | 270 |
| 6 | 268 |
| 7 | 296 |
| 8 | 178 |
| **Total** | **1,585** |

The total is under the 1,600 ceiling.

Timing estimate, using the 05r2 rates plus about 20 seconds for the S9 card wall's per-click animation:

| Pace | Estimate | Buffer |
|-|-:|-:|
| Mixed: 140 wpm narrative, 130 to 135 for number-dense beats | about 14:20 | about 0:40 |
| Uniform 130 wpm | about 14:45 | about 0:15 |
| Uniform 150 wpm | about 13:05 | about 1:55 |

Beat 4, at about 2:35 against a 2:05 slot, and beat 5, at about 3:10 against 2:35, carry the overrun. The section 6 cut order frees about 60 seconds if a rehearsal runs long.

## Residual items, not blocking

- **R1. Blast-radius tone.** "Good luck building your brilliant startup without being able to hire people willing to work for you" reads as sarcasm aimed at founders in the room, TypeSafe included. "It trends" is a guess, not data. Softer version: "and it spreads, and then you're trying to hire people who've read it." This is Adam's call.
- **R2. Card-wall timing.** Cap each S9 card's auto-play at about 3 seconds so the six clicks don't add 40 seconds.
- **R3. 01 still calls Clef an estimate.** Insight 14 and the 01 corrections line describe Clef's $0.3113 as a list-price estimate, but 06 shows it is a known charge. The worktree has an uncommitted 3-line change to `01-findings-synthesis.md` that I did not make. It may be this fix, so I did not touch it or commit it.
- **R4. Freeze discipline.** The writer committed v2.2 after the lead froze v2.1. This commit, v2.3, is the reviewer's last edit. Re-run `count-notes.ts`, `audit-slop.ts` and `s12_escalation_queue.py` if anything else lands before export.
