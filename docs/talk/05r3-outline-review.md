# 05r3 Outline review: final pass, v2.3

Reviewer: independent reviewer agent, the same one that wrote 05r and 05r2. Date: 2026-10-08.

How we got here:
1. The writer committed v2.2 at `c3aad25e`.
2. I fixed two blocking items in `aeaa84ee`.
3. On the lead's instruction, `17726b16` restored v2.2 and recorded a REVISE verdict.
4. A separate diff-reader checked every changed line of `aeaa84ee` against the feeds and confirmed them. The lead then restored that version as v2.3 in `bc0a9216`.
5. This commit is the last pass: the residuals, re-run counts and audit, and the final verdict.

The diff-reader confirmed these items independently:
- Qwen 59/56/53, one pass per prompt
- Gemma's fresh cells
- Jev's interrupted cell
- card-wall counts 0/0/1/2/3/5
- cost figures
- 1,585 words
- clean audit

**(rc)** marks a reviewer-computed number.

---

## Verdict: APPROVE

The outline at this commit is fit for stage:
- There are no blocking items. F1 and F2 from the v2.2 review are fixed and independently verified.
- N1, N2 and N3 from 05r2 are fixed in the text.
- Every number in the late additions reproduces from the feeds.
- The cost wording matches `06-cost-check.md`.
- The spoken total is 1,585 words, under the 1,600 ceiling, and the anti-slop audit finds 0 instances.

The "brilliant startup" line stays unless Adam says otherwise.

## Final residuals applied in this commit

| Residual | Status |
|-|-|
| Beat 4 "that same review" has no antecedent | Already in v2.3: "including the one I read you. But on that review..." |
| Q&A 19 "Claude, Codex and Gemini ran on subscriptions" | Fixed: "The Claude, Codex and Gemini subscription runs carry API-equivalent estimates only; the Gemini runs through OpenRouter are known charges inside the $12.65." |
| A12 "seven families", A7 "person-checked" | Already in v2.3: "seven models across three vendors", "checked by people" |
| S9 auto-play length | Fixed: the S9 brief and the deck motion rule both say "each card's auto-play capped at about 3 seconds" |
| Q&A 20, majority voting (lead request) | Added from 07 §3 and `s13_majority_vote.py`, re-run here. Jev's 2-of-3 majority is 54 in five conditions and 53 in one (OpenRouter P0: 54, 53, 52), never above its best pass **(rc)**. 13 of the 15 decision groups where the vote beat the average pass had a pass with fewer than 60 valid answers **(rc)**. The 145 clean general groups gain +0.14 reviews per 60. Self-unanimity lets 211 errors through, 154 of them on DEV-013, DEV-030 and DEV-006. The 10-to-20-sample plateau is stated as a reasoning-task result (Wang et al.), and the 60% figure is Kim et al., both as cited in 07 §3.1 |
| S5 feed pointer `extended-cases-v1.json` | Confirmed. All nine Gemma 4 26B thinking-on fresh cells (fresh1 to fresh3, P0 to P2) are in `public-site/extended-cases-v1.json`, the file `common.py` loads for the 637 extended runs. Run metadata sits in `extended-run-catalog-v1.json` |

## Checks carried forward

| Item | Result |
|-|-|
| N1 confidence and the soup | Beat 6 and §1: the soup is among Jev's ten least-confident reviews through sentiment only. The action fields said no at 0.84 to 0.91 |
| N2 calibration wording | "On these 60 reviews", descriptive-only; S10 headline "Close to its hit rate here" |
| N3 escalation wording | Either model's concern flag sends a review to a person. Every pair's flags caught all 25 on this set; Tev alone missed two. Q&A 14 says 6 by disagreement and 4 by "can't tell" |
| F1 nine runs | "Up to nine runs; blank means no run". Qwen labelled with one pass per prompt (59, 56, 53) |
| F2 card-wall polarity | "Got it right" throughout |
| S9 counters | Decision models matched 0, 0, 1, 2, 3, 5 of 7; run-passes matched 144, 661, 262, 287, 800, 713 of 1,004 **(rc)** |
| A13 to A18 | All 42 per-model answer vectors match `disputed-reviews-v1.json` **(rc)** |
| A11 | Some definite label 25% to 31%; the nearest label, no, 21% to 26% |
| Costs | OpenRouter $12.65 across 15,135 generations plus up to $3.88 unknown; Cloudflare direct under $0.26; Clef $0.03184656 and Jev via OpenRouter $0.00589092 known; Jev direct an estimate; seven-model series $1.2013 known plus up to $0.13 unknown. All match 06 |

## Final numbers

`count-notes.ts` output:

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

`audit-slop.ts`: 10,322 total words, 0 slop instances, NO-SLOP score 100.0%. Q&A 20 adds no spoken words.

Timing estimate, with the three audience moments and about 20 seconds of card-wall animation at the 3-second cap:

| Pace | Estimate | Buffer |
|-|-:|-:|
| Mixed: 140 wpm narrative, 130 to 135 for number-dense beats | about 14:20 | about 0:40 |
| Uniform 130 wpm | about 14:45 | about 0:15 |
| Uniform 150 wpm | about 13:05 | about 1:55 |

Beats 4 and 5 run long against their slots. The section 6 cut order frees about 60 seconds, and the hard-stop line at S12 is in place.

## Outside the outline

`scripts/build_deep_insights_v1.py`, and the `public-site/deep-insights-v1.json` it builds, still say "Clef's list-price estimate" (line 416, including a `clef_list_price_estimate_usd` key). They also say "calibrated on average" without the 60-review qualifier (lines 425 and 478). 01 was corrected in `2383f38f`. The site feed needs the same wording and a rebuild with `--check`. That belongs to the site lane.
