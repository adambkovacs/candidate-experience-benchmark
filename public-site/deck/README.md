# Talk deck (presentation-v2)

`public-site/presentation-v2.html` is a Reveal.js deck on a 1920x1080 stage. Reveal scales the stage to any screen; a slide never scrolls. Every number on a slide is bound to a public-site JSON feed and checked by a script.

Read `brand.md` and `MOTION.md` before designing or animating anything. They hold the colours, type, timing, easing and the never-list in the motion-skill-pack format. The delivery target is Adam's laptop in Chrome, screen-shared over Zoom (about 30fps, heavily compressed) to a 1920x1080 TV, so motion uses big bold shapes and nothing fine carries meaning.

## Run it

Serve `public-site/` over HTTP. Chrome blocks `fetch()` from `file://`, so the deck loads there but every bound number shows the orange data alert.

```bash
cd public-site && python3 -m http.server 8080
# open http://localhost:8080/presentation-v2.html
```

**Present with no server (file://):** open `public-site/presentation-offline.html` directly from disk. It is `presentation.html` plus every data feed inlined as `<script type="application/json" data-feed="...">` blocks, which `data.js` reads before it tries `fetch()`. The 3D background falls back to the static SVG scene there, because Chrome also blocks ES-module imports on `file://`. It is a generated artifact: rebuild it after any deck change, and before the talk.

```bash
node public-site/deck/verify/bake-offline.mjs
```

Everything is vendored, so this works offline. See `VENDOR.md` for versions and SHA-256 hashes.

| Key | Action |
|---|---|
| Right, Space, Page Down, N | Next fragment or slide (remote clickers send Page Up/Down) |
| Left, Page Up, P | Previous |
| Down / Up | Into and out of a vertical stack, such as the appendix |
| S | Speaker view with notes, timer and next slide (opens a window) |
| B or . | Black screen |
| F | Fullscreen |
| Esc or O | Overview |

Each slide has a hash URL from its `id`, for example `#/jev-all-four`. Fragment steps appear as `#/jev-all-four/2`.

**PDF:** open `presentation-v2.html?print-pdf`, wait for the slides to render, then print to PDF with background graphics on. Each fragment step becomes its own page. Print mode waits for the data feeds before laying out, so the PDF carries the real numbers. `verify/fit.mjs` writes a test PDF on every run.

## Files

| File | Role |
|---|---|
| `deck.css` | Brand tokens, type scale, layout primitives, Reveal chrome |
| `data.js` | Loads feeds, binds `[data-source]` and `[data-text-source]`, helpers (`window.DeckData`) |
| `motion.js` | GSAP motion toolkit wired to Reveal events, including the live replay (`window.DeckMotion`) |
| `scene-shapes.js` | Seeded formations for the 60 points: field, lattice, title, number, mark (`window.DeckShapes`) |
| `scene.js` | three.js engine that moves the points between formations, plus the static SVG fallback (`window.DeckScene`) |
| `deck.js` | Reveal config and boot order |
| `brand.md`, `MOTION.md` | Brand and motion rules for anyone (or any skill) animating this deck |
| `verify/` | `fit.mjs`, `numbers.mjs`, `lab.html` (a fixture showing every primitive) |

`assets/` (logos, photo, QR) and `data/` (curated deck feeds) belong to the deck-data-prep work; this foundation reads them and never writes them.

## Writing slides

A slide is a `<section>` with an `id` and one layout class. Put speaker notes in `<aside class="notes">`. Put the slide's sources in `<footer class="d-source"><b>Source</b>...</footer>`. If a slide binds numbers and has no footer, `data.js` adds one listing the feeds.

Common pieces: `<p class="d-eyebrow">` (mono kicker with a blue tick), `<h2>`, `<p class="d-lede">`, `.d-muted`, `.d-num` (tabular figures), `<div class="d-rail">` (ladder rail across the slide top, for title and section breaks only), `<img class="d-logo" src="./deck/assets/aea-logo-horizontal-transparent-white.svg" alt="AI Enablement Academy">` (the real lockup; 96px on most slides, 128px in `d-closing`), `<span class="d-ladder">` with seven `<i>` (a CSS ladder motif), `.d-badge` (set `--rail` for its colour).

| Class | Use | Key children |
|---|---|---|
| `d-title` | Opening | `h1`, `.d-byline` |
| `d-statement` | One big line | `p.d-line`, optional `.d-lede` |
| `d-two-column` | Two ideas side by side | `h2`, `.d-cols` with two children |
| `d-big-number` | One hero number | `.d-body` > (`p.d-figure` > `.d-num` + `.d-unit`, `p.d-caption`), optional `dl.d-stats` > `.d-stat` > `dt` + `dd` |
| `d-quote` | Review text with its ID | `blockquote data-review="DEV-027"`, `cite` |
| `d-table` | Saved answers | `table.d-data`; mark differing cells `td.is-diff`, the reference row `tr.is-reference` |
| `d-timeline` | Dated events | `ol.d-track` > `li.d-event` with `style="--at:.4"` (0 to 1), optional `data-side="above"`, `.is-key`, `.fragment` |
| `d-grid-3` | Three cards | `.d-cards` > `article.d-card` with `style="--rail: var(--s-sky)"` |
| `d-chart-frame` | A chart | `figure.d-frame` > `.d-frame-head`, `.d-plot` (put an `svg` or `canvas` inside), `figcaption` |
| `d-closing` | Last slide | `h2`, `.d-contact` |

The type scale is set for a projector: body 30px, captions 28px, h2 76px, h1 108px, eyebrows 18px mono at the 1080 design size. Spectrum colours (`--s-purple` through `--s-red`) are for rails, badges and the ladder only, never for backgrounds. `--diff` (orange) marks an answer that differs from the reference.

## Binding numbers to feeds

```html
<span class="d-num" data-source="findings.json#charts.jev.correct" data-countup>–</span>
```

`data-source` is `<feed path under public-site>#<path>`, for example `findings.json#...` or `deck/data/answer.json#jev_all_four.value`. Path grammar:

| Form | Meaning | Example |
|---|---|---|
| `a.b` | object keys | `charts.jev.correct` |
| `[3]` | array index | `pairs[14]` |
| `["0.9"]` | key containing dots | `thresholds["0.9"].retained` (write `&quot;` inside an HTML attribute) |
| `[k=v,k2=v2]` | first array item where every key matches | `pairs[left=solar-decide-native-fresh1-p0,right=perplexity-decider-native-fresh1-p0].accepted_count` |

One number per element. The element shows the feed value exactly; decimal strings such as costs stay exact. Add `data-round="2"` to display a rounded value, and `numbers.mjs` will round the same way. Integers of 10,000 or more get thousands separators. A missing feed or path shows `?`, outlines the element in orange, and raises a `role="alert"` status line.

Other bindings:
- `data-text-source="<feed>#<path>"` shows a label from a feed, such as a model's answer, made readable ("insufficient_information" becomes "Insufficient info"). Add `data-raw` to show it unchanged.
- `data-review="DEV-027"` on any element fills the review text from `disputed-reviews-v1.json`.
- `data-scene-highlight="@findings.json#charts.jev.disagreementCaseIds"` lights those reviews in the background scene.
- `data-scene-number="@findings.json#charts.jev.correct"` sets the figure the points form.

`numbers.mjs` checks all of these against the feeds.

Helpers for custom slide code (all async): `DeckData.get(source)`, `feed(name)`, `review(id)`, `answers(id, {feed, runs})`, `jevConfidence(field, condition)`, `agreementPair(left, right)`, `agreementPairs()`. Feeds load only when referenced.

## Motion

Motion follows the brand rule: confident ease-outs, nothing bouncy. Reduced motion, print view and backward navigation all show the final state instantly.

| Attribute | Effect |
|---|---|
| `data-countup` | Counts up to the bound value. Width is locked first, so digits never shift. |
| `data-stagger` | Children rise in, 80 ms apart. `data-stagger="tbody tr"` targets a selector. |
| `data-split` | Headline words rise out of masks. The heading keeps its full text as its accessible name. |
| `data-split="line"` | The whole element rises from behind a clean cut as one unit (for ledes and second lines). |
| `.d-event.fragment` | On each step the timeline line draws to that event and the event drops in. |
| `td[data-from]` | Split-flap flip: the cell shows `data-from` (the reference), flips, and lands on its own text in orange. |
| `.d-replay` | Replays one review across models, one row per click. See below. |

Anything inside a `.fragment` animates when the fragment appears.

```html
<div class="d-replay" data-replay="disputed-reviews-v1.json" data-review="DEV-027"
     data-fields="sentiment,testimonial_potential"></div>
```

The replay builds a table: the reference row, then one fragment row per saved answer. Differing cells flip, and a tally counts the models that disagree. `disputed-reviews-v1.json` holds the seven native fresh1/P0 models. For `extended-cases-v1.json`, pass runs explicitly with `data-runs="runId=Label|runId=Label"`. Seven rows fit under a two-line `h2`; for more, drop the `h2` or split the replay.

### Live replay

A request/response panel that looks like a live call and only replays saved answers. It always shows a "Replay of saved answers" badge. Use one per slide; it owns that slide's two fragment steps.

```html
<div class="d-live" data-review="DEV-029" data-model="Jev 1.13" data-route="TypeSafe direct API · prompt P0"
     data-answer="findings.json#charts.jev.cases[id=DEV-029].prediction"
     data-probability="jev-confidence-findings.json#conditions.P0.fields.{field}.wrongCases[id=DEV-029].selectedChoiceProbability"
     data-probability-label="p(chosen)"
     data-latency="data-provider-errors-v1.json#runs[id=typesafe-jev113-v2].timing.medianSeconds"
     data-latency-label="median request in this run, client-observed" data-compare></div>
```

On arrival the review types itself in. Click 1 sends: a latency track fills to the saved time, then each field lands with its probability bar. Click 2, when `data-compare` is set, brings in the reference column; answers that differ turn orange. `{field}` in `data-probability` is replaced per field. A field with no saved probability shows "not saved", never a made-up number. In the public feeds, Jev's probabilities are saved only for its wrong answers (`jev-confidence-findings.json` `wrongCases`), so the soup review DEV-029 has all four and DEV-027 has two. Every answer, probability, latency and reference in the panel is bound to its feed and checked by `numbers.mjs`. `verify/lab.html` has both examples.

## Background scene

Put `data-scene` on a section. The scene runs only on those slides, pauses when the tab is hidden, and never blocks navigation. Every move is an overshoot-free staggered settle: each point leaves on its own beat, left to right.

| `data-scene` | What the 60 points do | Options |
|---|---|---|
| `field` | Drift loosely, right of centre | `data-scene-at="x,y"` |
| `lattice` | Settle into a 12x5 grid, one point per review | `data-scene-highlight`, `data-scene-at` |
| `title` | Fly in through depth (camera dolly, near points soft like a lens), then settle into the lattice | `data-scene-highlight` |
| `number` | Matches form the figure as dotted numerals; highlighted reviews line up underneath in orange | `data-scene-number`, `data-scene-highlight`, `data-scene-at` (default `960,470`) |
| `mark` | Assemble into an image, each point taking the image's colour at its spot | `data-scene-image` (for example `./deck/assets/aea-icon-transparent.svg`), `data-scene-at` |

Points are 18 to 34px at the 1080 design size so they survive a compressed screen share. With reduced motion, no WebGL, print view, speaker view or `file://`, each scene slide gets a static SVG of the same formation. Under `file://` both the number and the mark formation fall back to the lattice: the number because feeds cannot load there, the mark because the browser blocks reading the image's pixels. Keep text clear of the formation: the field and lattice sit right of centre, and the number defaults to the middle.

## Appendix pattern

Backup slides for questions sit in a vertical stack after the last main slide:

```html
<section id="appendix">
  <section id="appendix-divider" class="d-statement">...</section>
  <section id="backup-costs" class="d-two-column">...</section>
</section>
```

Right skips the whole stack; Down steps through it. Jump during Q&A with the hash, for example `#/backup-costs`.

## Verify

```bash
cd public-site/deck/verify
pnpm install          # once; Playwright 1.61.1 reuses the cached Chromium build
node fit.mjs          # every slide x 1920x1080, 1366x768, 1280x720, 1440x900, plus ?print-pdf
node numbers.mjs      # every data-source value against the feed, live and in print view
node fit.mjs --page deck/verify/lab.html   # the toolkit fixture
node fit.mjs --reduced-motion              # the reduced-motion path
```

`fit.mjs` steps every fragment, waits for motion and the scene to finish, then fails on: document scroll, anything outside its slide, in-flow content entering the slide padding (the footer's space), clipped overflow, text under the controls or slide number, text over the source footer, any text below 16px at the design size, console errors or warnings, failed requests, and a PDF view with unrendered numbers. 1920x1080 is the primary target. It saves one JPEG per slide per viewport and the test PDF to `docs/talk/screenshots/`. It ignores one message, "GPU stall due to ReadPixels", which headless Chromium's software GL logs for any WebGL canvas, and reports how many it ignored. Whether a real GPU logs it was not tested.

`numbers.mjs` resolves each `data-source` in Node from the JSON on disk, separately from `data.js`, and compares it with the text on screen after count-ups finish. The shown text must be a plain number (optional thousands commas and decimals). It also checks labels bound with `data-text-source`, the scene figure from `data-scene-number`, review text bound with `data-review`, and every cell of each replay built from `disputed-reviews-v1.json`. Replays from `extended-cases-v1.json` are listed as unchecked. Both scripts exit non-zero on failure.
