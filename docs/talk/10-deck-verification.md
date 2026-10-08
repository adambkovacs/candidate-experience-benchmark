# Deck verification: presentation.html at 6ee85f65

Independent adversarial check of `public-site/presentation.html` and `public-site/deck/**` on branch `feat/talk-presentation-v2`. I wrote my own checkers and did not run the deck's own `fit.mjs` or `numbers.mjs`. Nothing in the deck was edited. Date of run: 2026-10-08.

## Verdict: APPROVE

No BLOCKING finding. Every claim held except the literal "zero console warnings" claim in headless Chromium, which comes from the software GL driver and does not occur on a real GPU. There are nine RESIDUAL findings. Two are worth a one-line fix before the stage: a wrong confidence figure in the speaker notes (R1) and a loose "58 to 59" headline (R2).

### Blocking list

None.

### Residual list (fix when convenient, none stops the talk)

| ID | Where | Finding |
|---|---|---|
| R1 | notes, `still-wrong` | Notes say Jev "was still 0.96 confident that the cancelled-train review was negative and not a testimonial". The feed says 0.96 is the testimonial field only. Jev's sentiment confidence on DEV-027 was 0.71. The slide text is correct ("not a testimonial, at 0.96"). The same sentence is in `05-session-outline.md` line 88. Read aloud, the notes attach the wrong number to "negative". |
| R2 | slide `answer`, headline | "General models 58 to 59" holds for first P0 passes only (Opus 59, Sonnet 58, Gemma 59, Qwen 59). The `nine-runs` slide, three clicks later, shows Qwen at 56 and 53 and Gemma at 56 to 58. A listener can see a general model below Jev's 54. A5 and A6 also show Gemini 3.1 Pro at 56 and 55. Suggest "Opus and Sonnet 58 to 59" or "on the first pass". |
| R3 | slide `classification-bench`, A8 | "433 tests" is the collected count. `04-harness.md` line 21 says "433 tests, OK, 44 skipped", so 389 ran in that environment. The slide does not say so. The notes say "more than 400", which is safe. |
| R4 | slide `launch-wave` | Click order is 1 Oct, then Perplexity (7 Oct), then OpenAI (6 Oct). A later date is revealed before an earlier one. The notes also say Perplexity "landed that week", while the slide marker is 7 Oct. |
| R5 | keyboard | `End` jumps to the first appendix slide (A1), not to `monday`. `ArrowRight` on `monday` also enters the appendix at A1. Pressing Right once too often during the close puts a backup slide on the TV. |
| R6 | slide counter | The counter reads "9 / 34" on a 15-slide talk because the 19 appendix slides count. The audience sees 34. |
| R7 | legibility | Every visible text node is 16 px or larger at 1080p, so the stated bar holds. Many labels sit at 16 to 19 px. Counts of text nodes under 20 px in the final state: `hard-six` 532, `agree-or-defer` 201, `zero-of-seven` 158, `monday` 44 (the appendix index, 20 px tall rows, 25 px pitch). Over Zoom compression these may smear. |
| R8 | `file://` | Opening the HTML from disk shows the orange data alert on every bound number (documented in the README). Only an HTTP origin works. Not tested by me beyond reading the README and `data.js`. |
| R9 | A12 vs docs | Qwen 27B + Gemma 26B charge is 0.06854978 in the feed. The slide shows $0.0685 (A12) and $0.069 (S12), both correct roundings. `01b-deep-analysis.md` and the outline say "$0.0686", which is a rounding of the doc's own 0.06855. Cosmetic mismatch between the slide and the outline. |

## 1. Fit: PASS

Method: my own Playwright script served `public-site/` on a free port, opened `presentation.html` at four viewports, stepped `Reveal.next()` through every slide and every fragment (56 states over 34 slides: 15 main, 19 appendix), waited for GSAP to settle, then asserted on every state:

- `document.documentElement.scrollHeight - innerHeight <= 0`, and the same for `body`
- no visible descendant (all elements, SVG children included, notes excluded) outside the slide section rectangle (1.5 px tolerance)
- no text-bearing element with computed `font-size` under 16 px
- no `overflow` clip hiding content (scrollHeight over clientHeight) and no text overlapping the source footer

```
1920x1080: states=56 distinctSlides=34 failingStates=0
1366x768:  states=56 distinctSlides=34 failingStates=0
1280x720:  states=56 distinctSlides=34 failingStates=0
1440x900:  states=56 distinctSlides=34 failingStates=0
clip / footer-overlap scan, 56 states at 1920x1080: no hits
```

Sensitivity check: I injected a 300 px box at `top:1000px` into slide 2. The same bounding-box test flagged it (`o:true`), so the check can fail. Section rectangle is 1901 x 1069 at a 1920 x 1080 viewport (Reveal margin), and nothing exceeds it.

Console on these runs: only the four `GL Driver Message ... GPU stall due to ReadPixels` warnings per run. See section 3 for where they come from.

Per-slide failures: none.

## 2. Numbers: PASS

My checker (`numbers.mjs` in my scratch directory, not the deck's) visited every state, read every `[data-source]` element after count-ups finished, resolved `feed#path` from the JSON on disk with its own parser (dot keys, `[n]`, `["0.9"]`, `[k=v,k2=v2]`), and compared the number in the text, allowing thousands separators and `data-round`.

```
checked=457 match=457 mismatch=0
```

Also checked:

- `data-doc` bindings (hand-typed numbers tied to a doc quote): 52 checked, 52 quote found in the named doc and the shown number is inside the quote, 0 failures.
- Unbound numbers on the main slides: only `10` (queue), `433` (bench), `39`, `2,000` and the replay tally. All covered by `data-doc`. The `10` equals 35 minus 25 and sums with 25 accepted and 25 flagged to 60.

Hand cross-check of 12 headline numbers (slide value, feed value, outline or synthesis value):

| # | Claim | On slide | Feed | Doc | Match |
|---|---|---|---|---|---|
| 1 | Jev 54 | 54 | `findings.json` correct = 54, `score.allFour` = 54 | 05 §1, 01 §3 | yes |
| 2 | Opus 5.5 high 59 / 58 / 58 | 59, 58, 58 | `values[0..2]` | 05 §1 | yes |
| 3 | Sonnet 5.5 58 in nine cells | nine cells all 58 | `xhigh P0/P1/P2 values` all 58 | 01 §3 row 9 | yes |
| 4 | Jev $0.00589092 known charge via OpenRouter | $0.006, "known charge" | `knownCostUsd` 0.005890920 | 06-cost-check | yes |
| 5 | Opus $0.222052 estimate | 0.22, "estimate, API-equivalent, not a bill" | `estimateUsd` 0.222052 | 01 row 8 | yes |
| 6 | Solar + Perplexity 53 / 0 / 7, $0.03749436 | 53, 0, 7, $0.037 | `accepted_count` 53, errors 0, deferred 7, cost 0.03749436 | 01 row 16 | yes |
| 7 | Qwen 27B + Gemma 26B 58 / 0 / 2 | 58, 0, 2, $0.069 (A12: $0.0685) | 58, 0, 2, `two_run_charge_usd` 0.06854978 | 01b §11 says 0.06855 | yes (R9 on rounding) |
| 8 | 35 of 60 reach a person | 35 | `reaches_person` 35 | 05 line 302 | yes |
| 9 | ECE 0.011 vs 0.358 | 0.011, 0.358 | Jev 0.011, Clef Flash 0.358 | 01b §8 | yes |
| 10 | 0 of 7 on the soup | 0 of 7 | I recomputed from `reviews[].answers`: DEV-029 matched 0 of 7 | 05 S8 | yes |
| 11 | 433 tests | 433 | not a feed | `04-harness.md` line 21 | yes (R3: 44 skipped) |
| 12 | DEV-059 5 of 7 | 5 of 7 matched | recomputed: 5 of 7 matched, 2 missed, histogram bin 2 | 05 S9 | yes |

Extra claims in the notes that I re-derived from the feeds: Jev caught all 25 key-yes serious concerns (its three concern errors are on reviews whose key is "insufficient"); the 0.9 sentiment gate withholds 13 answers, 9 good and 4 bad; Solar + Perplexity defer exactly DEV-006, 013, 027, 028, 029, 030, 035; per-review matches for DEV-030, 029, 006, 013, 027 are 0, 0, 1, 2, 3 of 7. All hold. The one wrong spoken number is R1.

## 3. Delivery: PASS, with the console caveat

**Keyboard.** From `title`: ArrowRight, Space (fragment), ArrowRight, ArrowRight, ArrowLeft, End, Home, PageDown, PageUp, N, P all behaved.

```
[kbd] ArrowRight -> answer      [kbd] Space -> answer f0    [kbd] ArrowRight -> about
[kbd] ArrowRight -> launch-wave [kbd] ArrowLeft -> about    [kbd] End -> a1-hosted   (R5)
[kbd] Home -> title             [kbd] PageDown -> answer    [kbd] PageUp -> title
[kbd] ArrowRight-only walk from title: 32 presses to reach a1-hosted
```

**Hash URLs.** 34 of 34 slide ids land when set in-page. Cold loads of `#/answer`, `#/hard-six/3` (fragment 3), `#/a10-pairs`, `#/a19-blast-radius` and `#/monday` all landed on the right slide and fragment. The README's example `#/jev-all-four` does not exist, so it falls back to the title slide.

**Appendix index.** The last main slide (`monday`) has 19 hash links plus one repo link and one source link. All 19 appendix slides have a link. Real mouse clicks: 19 of 19 landed on the right slide.

**Speaker view.** Pressing `s` opened a popup titled "reveal.js - Speaker View" with a clock, a "00:00:02" elapsed timer with "click to reset", an "Upcoming" pane and the notes text. Every one of the 34 slides has exactly one `aside.notes` (word counts 26 to 232).

**Print.** `?print-pdf` rendered 56 `.pdf-page` elements (one per fragment state), 679 bound numbers, 0 alerts, 0 unrendered numbers, 56 notes. `page.pdf()` at 1920 x 1080 produced 56 pages, 3.3 MB.

**Reduced motion** (`prefers-reduced-motion: reduce`, with GL available). Walked all 56 states with only 120 ms of wait, so no settling:

```
[reduced-motion+GL] states=56 statesWithActiveTweens=0 staticSceneSlides=title,one-of-60 issues=0 consoleProblems=0
```

No active tweens, no partly transparent text, and every bound number already at its final value.

**No WebGL.** Two ways: Chromium with `--disable-gpu --disable-webgl --disable-3d-apis`, and a stubbed `getContext('webgl*')` returning null.

```
[no-webgl flags] env {"staticClass":true,"canvases":0}  staticSceneSlides=title,one-of-60  consoleProblems=0
[no-webgl stub]  env {"staticClass":true,"canvases":0}  staticSceneSlides=title,one-of-60  consoleProblems=0
```

Both scene slides get the static SVG, there is no canvas, and there are no console errors or warnings. (The "issues" my script printed in those two runs are animations still in flight, because that run was not reduced-motion.)

**Console on normal load.**

| Environment | Console errors or warnings |
|---|---|
| Headless Chromium, software GL (SwiftShader) | 4 warnings: `GL Driver Message (OpenGL, Performance, GL_CLOSE_PATH_NV, High): GPU stall due to ReadPixels` |
| Headed Chromium on this laptop, GPU `ANGLE (Apple, ANGLE Metal Renderer: Apple M4 Max)`, first six steps from the title including the WebGL title scene | 0 |

So the warning is a software-GL driver message and does not appear on the real GPU. I did not test other GPUs, Safari, Firefox or a Zoom share. The headed run covered the title scene but not `one-of-60`.

**Offline.** Static: no `http(s)://` in any `src`, `href`, `url()`, `@import`, `fetch(` or `import(` in `presentation.html` or `deck/**` outside `vendor/` and `node_modules/`. `presentation.html` contains no absolute URL at all, and non-vendor deck code contains only the SVG namespace string. Vendor files hold only licence, namespace and comment URLs. Runtime: with every non-local request aborted, I walked 60 steps, opened speaker view and `?print-pdf`:

```
[network] hosts contacted: http://127.0.0.1:54313 | external requests attempted: 0
```

No external dependency. The QR image `deck/assets/qr-benchmark.svg` is local. I decoded it from the rendered 1080p `monday` slide with macOS Vision: `https://github.com/adambkovacs/candidate-experience-benchmark`. That URL returns HTTP 200 (public).

## 4. Hero sequences: PASS

Each run used a fresh page, a forward jump to the slide, one key press per click, and a 33 ms state poll. Timings are from a software-GL headless run at 70 to 115 rAF frames per second, so real-GPU feel may differ. Times are from key press to the last visible change.

| Slide | Click | Result | Time |
|---|---|---|---|
| `zero-of-seven` | 1 | Seven flips auto-play, all seven pips on, headline reads "0 of 7 decision models." | 12.3 s (notes say about 13 s) |
| `zero-of-seven` | 2 | Jev card and the "89 of 113" line appear | 0.9 s |
| `hard-six` | 1 to 6 | One card per click, six cards shown after six clicks, order DEV-030, 006, 013, 029, 027, 059 (matches notes) | 2.7 to 3.2 s each, max 3.17 s |
| `agree-or-defer` | 1 | Solar + Perplexity pane: 53 accepted, 0 errors, 7 to a person, seven cards move to the person column | 4.1 s |
| `agree-or-defer` | 2 | Qwen + Gemma pane: 58, 0, 2, two cards in the person column | 3.8 s |
| `still-wrong` | 1 | Gate sweeps to 0.95. DEV-027 dot (0.96) has the red ring, DEV-029 (0.88) the orange ring, readout "gate 0.95", "0.9 gate keeps 54 of 60" | 3.8 s |

Impatient presenter: a second press 3 s into the soup auto-play jumps straight to the end state (7 pips, extra row at opacity 0.98 then 1.0, no stuck half state). Three presses within 0.5 s on the card wall showed exactly three cards and ended with no active tweens. Going back one step and forward again shows the final state with no replay.

Soup screenshot confirms the cards: Tev, Clef, Clef Flash and Luna say mixed, no, no, no; Solar says negative; Liquid and Perplexity say can't tell on sentiment, with Perplexity also can't tell on testimonial; key is can't tell on all four. This matches the spoken notes.

## 5. Offline: PASS

See section 3. Zero external requests, zero external URLs in code. Reveal's speaker popup also works offline.

## 6. Links: PASS

90 references on the page (68 anchors, 48 of them in source footers, plus images, scripts and styles). 59 unique targets checked. Every target file exists. 18 distinct `page.html#anchor` targets were opened in a browser and each anchor id exists after the page's scripts ran. 20 in-deck hash links, none dangling.

```
[links] unique refs checked 59, distinct html anchors checked 18, broken 0
[links] in-deck hash hrefs 20 dangling: []
```

Targets covered: `explore.html#review-evidence, #jev, #jev-prompt-analysis, #repeat-analysis, #outcome-chart, #explore, #cross-category, #clef-first-pass, #agreement-policy, #reference-sensitivity, #cost-analysis`; `index.html#gap, #controls, #hard-reviews, #deep-insights, #rule, #limits`; `method.html#findings`.

## 7. Voice: PASS

Dump: `presentation.html` with scripts, styles and comments removed, tags stripped, entities decoded.

```
static-full   (slides + notes, 6696 words)  Slop instances 2  NO-SLOP score 99.9%
static-slides (no notes, 3035 words)        Slop instances 2  NO-SLOP score 99.7%
SLOP FINDINGS: [FORBIDDEN_WORD] "harness" found 2x
```

The two hits are the file path `docs/talk/04-harness.md` in source footers. Tier 1: em dashes 0, double hyphens 0, curly quotes 0, emoji 0. The only non-ASCII character in the page text is the middle dot. The audit covers static HTML. Text built by JavaScript (review cards, replays) was scanned only through the rendered on-slide dump, which also shows only the middle dot.

## 8. Comprehension read

### 8a. Slides only, as a non-engineer, 15 main slides in order

1. The talk asks whether an AI labelling tool called Jev, which gives a typed answer in one pass, can be trusted on recruiting feedback when mistakes matter.
2. The opening review (a manager who kept asking someone out) lands hard. I understood the stakes straight away.
3. Jev matched the answer key on 54 of 60 reviews. Bigger general models matched 58 to 59. "Buy a rule" ends the slide. I did not know what the rule was yet, which is a good hook.
4. The launch-wave slide tells me many vendors shipped similar models within weeks. Easy to follow, though it is context rather than a claim.
5. Lost here: the grid of nine cells per model. I got that Jev is lower, but "P0 P1 P2", "pass", "batch 10", "xhigh", "A4B" and "native" mean nothing to me. The four question cards above the grid helped.
6. Cost slide is clear: under a cent against 22 cents. The words "known charge" against "estimate" are subtle but labelled.
7. The soup review is the best slide. One off-topic review, seven specialist models, none say "can't tell". "0 of 7" is memorable. The orange cards read at a glance.
8. Six reviews worth pausing on: I understood that hard reviews exist and that models miss the same ones. The tile bars and "144 of 1,004 run-passes" are unexplained.
9. Lost on the confidence slide. The dot chart works and "Still 0.96 on a wrong testimonial" is clear, but "close to its hit rate" and "gate" assume I know what calibration is. The "more instructions" slide lost me more: "plain, framing, tree" and "39 saved setups" are never defined.
10. I understood the end: do not trust one model's confidence. Run two cheap models. If they agree, accept. If they disagree, send it to a person. 53 accepted, 7 to a person, then 35 of 60 reach a person. The bench slide is a pipeline diagram I skimmed. Monday gives four steps and a QR code.

**Most text:** `hard-six` carries the most on-slide text: about 250 words once all six cards are shown, mostly at 16 to 19 px. Next are `agree-or-defer` (119 including 60 card number labels), `still-wrong` (119), the `monday` slide (118, mostly the appendix index) and `nine-runs` (115).

### 8b. Slides against speaker notes

They agree on structure, order and every number, with these exceptions:

- R1: the `still-wrong` notes put 0.96 on "negative" as well as "not a testimonial". The slide is right.
- R4: the `launch-wave` notes say Perplexity "landed that week by press reports". The slide shows its verified 7 Oct listing. The notes themselves flag the date as unverified.
- The click counts in the notes match the slides: soup 2 clicks, card wall 6, sorter 2, sweep 1, launch wave 3, answer 1, queue 1. The notes' stated timings (about 13 s, about 3 s per card, about 4 s sweep) match what I measured (12.3 s, up to 3.2 s, 3.8 s).
- The notes say "more than 400 tests" while the slide says 433. Consistent.
- Every claim I traced from the notes to a feed held (see section 2), apart from R1.

## What I could not verify

- A real Zoom share and a TV at the venue.
- Any GPU other than this laptop's Apple M4 Max, and any browser other than Chromium.
- The external statistics on A19 (Talent Board, Gartner, Pew, EEOC and others). I only confirmed that each quoted figure appears in `07-remedies.md`, not the original source.
- The `classification-bench` repo itself (433 tests, commit a1e9879). I relied on `04-harness.md`.

## How this was run

Scripts live in my session scratchpad, not in the repo. Playwright 1.61.1 from `public-site/deck/verify/node_modules`, Chromium, local static server on a random port, Python 3 for feed recomputation, macOS Vision for the QR decode. Order of checks: fit, numbers, delivery, heroes, offline, links, voice, comprehension.
