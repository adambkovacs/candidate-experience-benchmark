# Mechanics lane report

Claim tested: every slide fits at 1920x1080 and 1366x768 with no scroll, every number is bound and matches its feed, every link resolves, notes match the outline.

**Evidence base.** HEAD was 35cdc4c8 throughout. The director began editing the working tree at 14:46:42 (presentation.html, content.css, heroes.js, motion.js, charts.js, and others). My first runs ran 14:38 to 14:44 on the clean tree. To be safe I exported 35cdc4c8 with `git archive` into the scratchpad and re-ran audit, numbers, delivery, heroes, fit and contrast there. The pinned results match the first runs line for line. Everything below is true of 35cdc4c8, not of whatever the director pushes next.

Note on defaults: `fit.mjs` and `numbers.mjs` default to `presentation-v2.html`, the old deck. Running them bare checks the wrong file. I passed `--page presentation.html`. The director's step 5 must do the same.

Logs: `/private/tmp/claude-501/-Users-adamkovacs-Documents-codebuild-recruitment-feedback-demo/af4509f9-362d-47d0-8b37-8a6d24717409/scratchpad/mech/` (live runs) and `pin-*.log` (pinned runs).

## Scorecard

| Script | Exit | Verdict |
|---|---|---|
| fit.mjs, four viewports, motion | 0 | PASS |
| fit.mjs, four viewports, `--reduced-motion` | 0 | PASS |
| numbers.mjs | 0 | PASS |
| content-audit.mjs | 0 | PASS |
| content-smoke.mjs | 0 | PASS (34 slides, no failure) |
| content-heroes.mjs | 1 | FAIL, 3 checks |
| content-delivery.mjs | 1 | FAIL, 1 check |
| `node --check public-site/meetup-presentation.js` | 0 | PASS |
| `node --test tests/test_presentation_ui.cjs` | 0 | PASS, 5 of 5 |
| Contrast pairs under 4.5:1 | n/a | 2 |

## Pasted results

**fit.mjs** (34 slides x 1920x1080, 1366x768, 1280x720, 1440x900, WebGL canvas present)

```
PDF (?print-pdf): 56 pages (expected up to 56 with fragment steps), unbound numbers: 0
RESULT: PASS        EXIT 0
```

No FAIL lines. Every one of the 136 slide-viewport cells is PASS. The `--reduced-motion` run is also `RESULT: PASS`, 56 PDF pages.

**numbers.mjs**

```
live: 459 number, 0 text, 0 scene, 15 review, 0 replay · print: 689 number, 0 text, 0 scene, 59 review, 0 replay
RESULT: PASS        EXIT 0
```

1222 PASS rows, zero non-PASS rows.

**content-audit.mjs**

```
2. Unbound digits on slides: 0
3. Speaker notes against outline 2b: beats 1 to 8 all PASS (125/56/146/377/298/273/271/184 words, deck equals outline)
4. Copy words per slide, max 75: S1..S18 PASS, S19 monday = 85 -> "OVER (closing slide also carries the @ruvector/typesafe line ...)"
5. Source links out of the deck: 19 targets, all PASS
RESULT: PASS        EXIT 0
```

The S19 word-count overrun is waved through by an exception hard-coded in the script, so it does not fail. It is 10 words over Adam's cap. The director should decide whether to cut it.

**content-delivery.mjs** (EXIT 1)

```
| S15 index: all 19 links resolve to slides | FAIL | 19 of 19 |
RESULT: FAIL
```

This is a stale test, not a broken deck. The check asserts exactly 19 links in the appendix index. The index now holds 15 links (A1 to A5, A7 to A10, A13 to A18). Zero of them are broken: the "unresolved ids" list is empty, which is why the detail text still reads "19 of 19". Fix is changing `19` to `15` in content-delivery.mjs line 37. Every other delivery check passes: PageDown, PageUp, Space, arrows, both hash deep links, click on A13, speaker view with notes, click count and timer.

**content-heroes.mjs, motion mode** (EXIT 1)

```
motion: S8 click 1 flips all seven, 760 frames in 13.1 s | FAIL | {"flipped":7,"pips":7,"tally":"1","extra":"0,0,0","badge":true,"headline":"0 of 7 decision models matched the key."}
motion: S8 click 2 shows Jev and the general line        | FAIL | {"flipped":7,"pips":7,"tally":"1","extra":"1,1,1","badge":true,"headline":"0 of 7 decision models matched the key."}
motion: S9 six clicks show six cards, longest click 4.8 s | FAIL | {"shown":6,"textsExact":true,"marksInPlace":true}
S10 gate sweep: PASS   S12 click 1: PASS   S12 click 2: PASS   WebGL canvas present: PASS
```

- **S8 (zero-of-seven), two FAILs, both stale expectations.** The test expects two "extra" elements (`'0,0'`, `'1,1'`) and the headline `0 of 7 decision models.` The deck now has three extras and the headline reads `0 of 7 decision models matched the key.` Behaviour is right: seven cards flip, seven pips light, tally shows. The test needs updating, not the deck.
- **S9 (hard-six), one FAIL, a timing budget.** All six cards show, text matches the feed exactly, marks sit in place. The failure is only the budget of 3.6 s per click: the longest click took 4.8 s (5.5 s on my first run). Reduced-motion and no-WebGL runs of the same slide take 0.9 to 1.2 s, so the time is the WebGL scene under headless software rendering. I did not verify this on a real GPU. If the venue laptop has one, this is probably fine. Flag it for a rehearsal check.
- **S8 click 1 takes 13 to 14.5 s of animation** in headless motion mode (no budget is asserted in the script). Reduced motion is 1.3 s. If this is real on stage, it is a long wait on the slide that carries the headline result. Worth one rehearsal look.

**content-heroes.mjs, reduced-motion and no-WebGL** (both EXIT 1, run on the clean tree at about 14:44)

Both fail the same two S8 stale-expectation checks. Both also fail **S12 click 1**:

```
reduced motion: S12 click 1 sorts Solar + Perplexity | FAIL | {"person":2,"split":2,"a":false,"b":true,"pair":"b"}
no WebGL:       S12 click 1 sorts Solar + Perplexity | FAIL | {"person":2,"split":2,"a":false,"b":true,"pair":"b"}
```

After the first click the slide is already on pair b (Qwen + Gemma), not pair a (Solar + Perplexity). In motion mode the same click correctly lands on pair a. So with reduced motion or without WebGL, the presenter appears to lose the first sorting step. S9, S10 and S12 click 2 pass in both modes. I did not find the cause. It could be a real step-skip in `heroes.js` or a race in the test harness; I did not isolate which. Treat as a real risk if the venue machine falls back to the static scene.

## Links

- Appendix index: 15 of 15 resolve to a slide id. Clicking A13 jumps correctly.
- Static scan of every `href` and `src` in presentation.html: 40 local targets, 0 missing. No external http links.
- All 18 `explore.html#`, `index.html#`, `method.html#` anchors exist as ids in their target pages.
- One link is `index.html#` with an empty anchor (content-audit lists it as PASS). It opens the top of the page.

## Contrast

Method: `docs/talk/sprint/mechanics/contrast.mjs`. It drives the deck, shows every slide fully, and for each visible text node takes the computed colour, composites ancestor backgrounds and opacity, and applies the WCAG ratio. This catches the `!important` overrides in content.css that a static read of the two files would miss. 1609 text nodes, 136 distinct selector, colour and background pairs, screen media at 1920x1080.

**Pairs under 4.5:1: 2.** Both are the same selector.

| Ratio | Selector | Text | Background | Where |
|---|---|---|---|---|
| 2.93 | `span.c-cell-n` | #fbfcfe, 30px/800 | #6298d7 | a3-prompt-levels, cell "55" |
| 3.62 | `span.c-cell-n` | #fbfcfe, 30px/800 | #4987cf | nine-runs, a3-prompt-levels, a9-equal-scores, cell "54" |

Cause: matrix.js (`is-light`) switches the cell number to dark ink only at 56 or above, but the heat scale is already pale mid-blue at 54 and 55. Cells 54 and 55 get white text on light blue. At 30px bold both would pass the 3:1 large-text bar except the 2.93 one. Fix: lower the `is-light` threshold from 56 to about 53, which gives dark ink on those cells (about 6:1 on #6298d7 by my arithmetic, not re-measured). The nine-runs matrix is on the main path, so the 54 cell is visible in the talk.

Lowest passing pairs: #fbfcfe on #2f76c8 at exactly 4.50, then orange #f57c00 on #28303e at 4.91. Nothing else is close to failing.

**Limits of this pass.**
- 16 text nodes sit under a gradient or background image and use an approximated background.
- Text laid over the WebGL scene canvas is measured against flat ink, not the rendered pixels.
- A print-media emulation run reported 51 failures, but that is an artifact. It strips the dark slide background that `?print-pdf` mode keeps, so I discarded it. The real print path is covered by the `?print-pdf` check in fit.mjs (56 pages, 0 unbound numbers). Plain browser print without `?print-pdf` will give light text on white; I did not test that and do not consider it a supported path.
- Measured at 1920x1080 only. Colours do not change by viewport.

## Other things I noticed (not failures)

- The replay pill (`c-replay-badge`) markup is still on 9 slides. CSS hides it (`display: none !important`, content.css line 531), and numbers.mjs still counts it as "on". It is invisible, so the pill is gone for the audience. Same for the `.d-source` footers: hidden by CSS, still in the DOM. If Adam's check is "no footer on screen", it holds. If someone greps the HTML, it will find them.
- content-audit check 4 treats S19 (85 words) as acceptable by a script-level exception, and the audit counts that as PASS.

## What I could not verify

- Behaviour on a real GPU. Headless Chromium used SwiftShader.
- 1920x1080 and 1366x768 passes are scroll-and-overflow geometry checks. They do not judge whether text is legible at projector distance.
- The offline copy `presentation-offline.html`. Not in scope; the lead re-bakes it after the push.
- Anything the director changed after 14:46:42.

## Files I created

- `docs/talk/sprint/mechanics.md` (this report)
- `docs/talk/sprint/mechanics/contrast.mjs` (reusable; run from `public-site/deck/verify` with `node ../../../docs/talk/sprint/mechanics/contrast.mjs`)
