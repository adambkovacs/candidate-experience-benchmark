# Site shell (AEA edition)

The public report is three pages that share one shell:

| Page | For | Holds |
|---|---|---|
| `index.html` (Read) | Anyone, including non-engineers, in about two minutes | The answer, the four decisions, three findings, the agree-or-defer rule, the 8 October update (`deep-insights-section.html`), limits, and links onward |
| `explore.html` | Analysts | Every existing panel with its ids, markup and scripts unchanged, plus the old story chapters as worked examples |
| `method.html` | Anyone checking the work | Method, FAQ, the reference review and the tooling note |

## Why three pages

The Read page loads no analyst panel, so it doesn't download the 10 MB `data.json` or the other panel feeds. It
fetches only the two deep-insights feeds. Explore is the analyst app: all panels, its own sticky sub-nav, URL state
(`?run=`, `case`, `experiment`, `compareRun`, `cohort`, `category`) and the run inspector near the top. Each page has
one job and one h1.

## Old links

Every element id kept its name. A short inline script at the top of `index.html` forwards old links:

- `index.html#inspect` goes to `explore.html#inspect`.
- `index.html?run=...#inspect` goes to `explore.html?run=...#inspect`.
- `index.html#method` goes to `method.html#method`.

`LINK-MAP.md` has one row per old anchor, for the deck, README and docs to update their links.

`navigation.js` keeps a `#hash` target in place while panels grow the page after load. It stops when the reader
scrolls, taps or types, or after 12 seconds. Smooth scrolling switches on only after load, because a smooth
load-time jump fights that alignment.

## Look and motion

Tokens, easing and finish follow the talk deck (`public-site/deck/MOTION.md`, `brand.md`, `deck.css`):

- **Ground and type:** flat Ink Navy `#1a2332` with the deck's ink ramp. There is no grain and no glow. Archivo is
  used for display, IBM Plex Sans for body and IBM Plex Mono for eyebrows and numbers. All three are self-hosted
  in `fonts/`.
- **Panels and rails:** panels have a 14px radius, one rule and one soft shadow. Ladder rails are hard-stop rungs.
- **Orange:** `#f57c00` means one thing only, "differs from the reference".
- **Surfaces:** narrative sits on navy (`data-surface="ink"`). Every analyst panel sits on a paper plate
  (`data-surface="paper"`), so its charts keep the colours their scripts draw. `site.css` swaps the legacy tokens
  per surface, so older rules adapt unedited.
- **Nine-cell glyph:** three prompt versions down, three fresh passes across, each square shaded by its all-four
  score from 40 or fewer up to 60. The Read page draws it for Jev, Opus 5.5 and Sonnet 5.5. On Explore,
  `ninecell.js` shades the repeat chart that `repeats.js` already renders.
- **Motion runs on the Read page only.**
  - The headline rises from masks, in CSS, so it never waits for a script.
  - `hero.js` settles the 60 reviews into a 10 x 6 grid (three.js r185, lazy, pauses off screen). It marks the six
    reviews where Jev's direct P0 answers differed from the reference in orange.
  - Blocks rise 28px over 0.7s, 0.08s apart.
  - Nine-cell squares settle in, and the rule's numbers count up over 1.4s to their exact text.
  - The primary action has a small magnetic pull, with no overshoot.
  - Explore and Method get no decorative motion.

| File | Loaded by | Does |
|---|---|---|
| `site.css` | all pages, last stylesheet | Tokens, fonts, header with layer switch, surfaces, plates, tables, nine-cell shading on Explore, footer, print |
| `read.css` | Read | Hero, decisions, findings, nine-cell glyph, hard six, rule, limits, doors, entrance keyframes |
| `../navigation.js` | all pages | Current-section mark, reading rail, header height, sticky table heads, deep-link keeper |
| `motion.js` | Read, after `vendor/gsap/gsap.min.js` | Reveals, count-ups, nine-cell settle, hero exit, magnetic action |
| `hero.js`, `hero-lattice.svg` | Read | three.js lattice, and its static fallback |
| `ninecell.js` | Explore | Copies each repeat-chart score onto its row for shading |

Every number on the Read page carries `data-source="<feed>#<path>"` in the deck's path grammar, and a title that
shows it on hover. Each section ends with a line linking its feeds. Derived numbers, such as "five reviews" or the
cost ratios, carry `data-derived` with the computation instead.

## Turning motion off

- **Reduced motion.** With `prefers-reduced-motion: reduce` set, the hero shows `hero-lattice.svg`, three.js never
  loads, and nothing is hidden, counted or animated.
- **No WebGL 2.** The SVG stays in place.
- **Remove it.** Delete the `gsap.min.js`, `motion.js` and `hero.js` tags from `index.html`. The page reads the
  same; the verify script checks this case.

## Verifying

```bash
python3 -m http.server 8000 --directory public-site
node public-site/site/verify/verify-site.mjs http://127.0.0.1:8000/ docs/talk/screenshots/site
```

It checks all three pages at 1440 x 900 and 390 x 844, plus three extra runs:

- the Read page with reduced motion
- the Read page with its motion scripts blocked
- Explore with `ninecell.js` blocked

Each run asserts:

- no console errors or warnings, and no failed requests
- one h1 per page, and no horizontal scroll
- every block visible after scrolling through
- **Read page:** every bound number equals its feed value, and the count-ups land on their text
- **Explore:** all 92 ids the panel scripts query exist exactly once, all 19 panels render, and the cohort switch,
  explorer filter, compare picker, run inspector, study steps and sub-nav all work

Finally it opens 23 old and new deep links. It checks the page each one lands on and that the target sits below
the header. It exits non-zero on any failure.

On macOS it uses the GPU path (ANGLE Metal), like a visitor's browser. With `--software`, Chromium's SwiftShader
logs a driver note, "GPU stall due to ReadPixels", for any WebGL canvas. That note comes from software rendering,
not from these pages.

`verify/hero-lab.html` is a small fixture for working on the hero scene on its own.
