# v4.1 verification of Adam's 15:30 edit list

Commit dfeb42f9, read-only check. Capture: docs/talk/sprint/v41/*.jpg and v41-text.json (1920x1080, served). Slide numbers in the table are Adam's v4 numbers. The id column is the slide id in v4.1.

## 17-row table

| # | Item (Adam's v4 slide) | Slide id | Verdict | Evidence |
|---|---|---|---|---|
| 1 | Slide 2: "buy a rule" becomes "create a rule" | answer | DONE | "buy a rule" 0 in live and offline (2 in v4). "create a rule that hands the hard reviews to a person" present in both. v41/06.jpg text dump. |
| 2 | Slide 2 comes after slide 6 | answer | DONE | Order is what-we-did (5), answer (6). Same in the offline file. |
| 3 | Slide 9 rewrite | general-models | DONE | Verbatim present: "More effort didn't buy more matches. Bigger models didn't buy more matches either. The big models gave the same answers, wrong ones included. Multiple runs proved non-deterministic outcomes." Old sentence 0. |
| 4 | Slide 10: show what P0, P1, P2 each add | consequences | PARTIAL | The consequences slide (v41/10.jpg) is unchanged and shows no prompt-level explanation. The explanation sits on more-instructions (15), a3-prompt-levels (23) and what-we-did (5), as the conductor's note planned. Wording matches prompts/variants-v1/P1-classifier.txt and P2-classifier-sop.txt (P1 adds the classifier role and feedback-only evidence, P2 keeps P1 and adds the numbered procedure). If the ruling means literally on slide 10, this is NOT DONE. |
| 5 | Slide 13: orange explained, sentence cut, pill removed | hard-six | DONE | Title is exactly "Four of these are judgment calls and two are plain misses." (1 live, 1 offline, "and the reason is on each card" 0). Subtitle says "An orange square is an answer that differs from the key." No "the one we opened with" pill in v41/13.jpg. The histogram bars are grey-blue, not orange. |
| 6 | Slide 14: show the questions and key labels | still-wrong | DONE | v41/14.jpg: DEV-027 box lists all four questions with key and Jev answer (sentiment positive vs negative at 0.71, testimonial yes vs no at 0.96). DEV-029 box says "Key: can't tell". |
| 7 | Slide 16: trim two sentences, drop the 21-pair paragraph | agree-or-defer | DONE | Visible text ends "$0.037 for both runs" and "$0.069 for both runs. Other Gemma runs let one error through." Counts 0 for "an example I picked after seeing all 21 pairs", "and that was one run", "We tried every pair of the seven decision models". |
| 8 | Slide 17: drop the price-of-zero-errors sentence | queue | DONE | "That queue is the price of zero accepted errors" 0 live, 0 offline (1 in v4). The rest of the sentence is kept. |
| 9 | Slide 18: drop the status text, dashed legend, "being open-sourced" | classification-bench | DONE | "Today it runs offline with 433 tests" 0, "built, not yet run live" 0, "being open-sourced" 0 (3 in v4). Visible text has no "open-sourc". |
| 10 | Slide 19: "What should you do", drop repo and ruvector paragraph | monday | DONE | Title "What should you do" present. "What I'd do on Monday" 0 visible. "Every scored answer is in the public repo" 0 visible. No "@ruvector/typesafe" anywhere. |
| 11 | Slide 20: "It's cheap to experiment" | a1-hosted | DONE | Present 1 live, 1 offline. "Hosted decision models, one card each" 0. |
| 12 | Remove slide 21 (a2-open-weight) | gone | DONE | id absent from live and offline order. |
| 13 | Slide 22: drop tree sentence and legend; explain up/same/down denominators | a3-prompt-levels | DONE | "The tree pushed decision models" 0, interruption legend and "blank means no run" gone from this slide. v41/23.jpg: three rows each labelled "39 setups" (15+15+9, 7+16+16, 4+14+21 all equal 39) plus a sentence defining up, same, down. |
| 14 | Slide 23: no answers columns, drop the 1192 line, fix overlap | a4-calibration | DONE | "1192 of 2156" 0. v41/24.jpg: both tables clean, no answers column, nothing overlaps. |
| 15 | Remove slides 24, 25, 26 (a5-key, a7-limits, a8-bench) | gone | DONE | All three ids absent from live and offline. |
| 16 | Slide 28 (a10-pairs) after slide 17 | a10-pairs | DONE | Order is queue (17), a10-pairs (18), classification-bench (19). |
| 17 | Last slide: Thank you! and Questions? | thanks | DONE | v41/21.jpg shows "Thank you!" and "Questions?". Offline file renders the same slide. |

Totals: DONE 16, PARTIAL 1, NOT DONE 0.

## Slide-order check

Live and offline both have 32 sections: title, about, decision-models, launch-wave, what-we-did, answer, nine-runs, pass-cost, general-models, consequences, one-of-60, zero-of-seven, hard-six, still-wrong, more-instructions, agree-or-defer, queue, a10-pairs, classification-bench, monday, thanks, appendix divider, a1-hosted, a3-prompt-levels, a4-calibration, a9-equal-scores, then the six DEV backup slides. The answer slide follows the setup slide. a10-pairs follows queue. Slides a2, a5, a7, a8 are gone. The Thank you slide ends the main talk, but the appendix slides follow it in the deck.

## Offline check

- Visible-text grep counts match the live file for every removed and added string.
- The grep counts for "the one we opened with", "open-sourc", "Every scored answer" and the interruption legend are explained under residuals.
- Opened via file:// in Playwright at 1920x1080: 31 slides, zero console errors, zero page errors, zero failed requests, no "Failed to fetch" in the body. Slide 21 renders "Thank you! Questions?".
- Screenshot: scratchpad/offline-thanks.png.

## Script results

```
fit.mjs (1920x1080, 1366x768, 1280x720, 1440x900; 31 slides, all PASS; PDF 38 pages, unbound numbers 0)
RESULT: PASS
numbers.mjs
RESULT: PASS
content-audit.mjs
RESULT: PASS
```

## Residuals, none counted as NOT DONE

1. Hard-six slide, DEV-030 card (v41/13.jpg): the footer text "matched" and "runs" spills below the card edge. fit.mjs does not flag it.
2. The legend "run completed after an interruption / blank means no run / columns P0 P1 P2, rows fresh pass" is still visible on nine-runs (slide 7, partly) and a9-equal-scores. Adam asked for removal only on his slide 22, which is a3, so this is as specified.
3. Speaker notes still carry removed wording. The classification-bench notes say "open-sourcing it, so ask me for early access". The monday notes say "This is what I'd do on Monday" and "Every scored answer is in the public repo". Hidden from slides, but Adam will read them aloud.
4. "On the one we opened with" remains in the pass-cost slide body. Adam asked for removal of the pill on slide 13 only.
5. more-instructions (15) still says Clef "may only read the first 2,000 tokens". Adam asked for the matching sentence to go only from his slide 22.
