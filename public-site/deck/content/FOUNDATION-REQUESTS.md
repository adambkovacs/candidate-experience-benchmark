# Foundation requests from the deck content layer

The content layer (`presentation.html`, `deck/content/*`) never edits `deck.css`, `data.js`, `motion.js`, `scene*.js` or `deck.js`. Each item below is a workaround in place today, and the change that would let it go.

## 1. `data.js` adds a combined footer to the appendix stack

`ensureFooters()` runs when `data.js` loads, before Reveal adds the `stack` class, so `section:not(.stack)` matches the vertical-stack wrapper `#appendix`. The wrapper has bound numbers below it and no direct `.d-source`, so it gets one footer listing every appendix feed, drawn over every appendix slide.

- **Workaround:** an empty `<footer class="d-source" hidden>` as a direct child of `#appendix`.
- **Request:** skip sections that contain sections, for example `section:not(:has(> section))`.

## 2. Answer labels: "can't tell" vs "Insufficient info"

`readable()` shows `insufficient_information` as "Insufficient info". The outline, the speaker notes and the S5 vocabulary strip all say "can't tell". The content layer builds its labels itself and tags each one with `data-answer="<feed>#<path>"`, which `verify/content-audit.mjs` checks against the feed.

- **Request:** an option on `data-text-source` (for example `data-say="cant-tell"`) so `numbers.mjs` can check these labels directly.

## 3. No hook for content builders before print layout

Components (matrices, review cards, sorter, gate) are built from feeds and must exist before Reveal lays out `?print-pdf`. `content.js` wraps `DeckMotion.prepare` so `deck.js` waits for them.

- **Request:** `DeckMotion.prepare` (or `DeckData.ready`) accepts registered builders, so nothing needs wrapping.

## 4. Grouping for 1,000 to 9,999

`display()` groups integers from 10,000 up, so 1004 shows as "1004". Elements with `data-group` are reformatted by `content.js` on `deck:bound` (`numbers.mjs` accepts grouped digits).

- **Request:** support `data-group` in `display()`.

## 5. Dates from feeds

`data-text-source` with `data-raw` shows an ISO date. S4 needs "15 September" and "1 Oct", so it uses `data-deck-source` with `data-format="date"` or `"date-short"`, checked by `content-audit.mjs`.

- **Request:** a `data-format` for dates on `data-text-source`.

## 6. Two GSAP traps worth a line in MOTION.md

- `clearProps: 'all'` removes the whole `style` attribute, including inline custom properties such as `--at` and `--y` that position shapes. The content layer clears only the properties GSAP owns.
- Handing GSAP an element on a hidden slide (`display: none`) for a transform makes it re-parent the node to measure it, then put it back before the next element sibling. A `<mark>` followed only by text ends up at the end of the paragraph. The content layer never passes marks to GSAP's transform parser.

## 7. Source links (remapped)

Resolved. Every source link now points at the report page that shows that evidence, using the targets in `public-site/site/LINK-MAP.md`. The link text still names the JSON feed. Map used: disputed reviews to `explore.html#review-evidence` (S9 to `index.html#hard-reviews`); deep insights to `index.html#controls` (calibration), `#rule` (agreement), `#limits` (A7) or `#deep-insights`; `findings.json` to `explore.html#jev`, `#cost-analysis` or `method.html#findings`; Jev prompt passes to `explore.html#jev-prompt-analysis`; Jev confidence to `index.html#controls`; repeat feeds to `index.html#gap` (S2) or `explore.html#repeat-analysis`; supplemental runs to `explore.html#clef-first-pass` or `#outcome-chart`; the rest to their named panels (`#agreement-policy`, `#reference-sensitivity`, `#cross-category`, `#outcome-chart`, `#explore`, `index.html#gap`).

Doc citations (`data-doc`, checked by `content-audit.mjs`) point at `docs/talk/*.md`, `docs/FINDINGS.md` and `docs/CLEF_OPENROUTER_FINDINGS.md`, which are not served by the site.
