# Site design audit: why it reads "not premium"

Branch `feat/site-content-v2` at `ffb9305a`. Read-only audit of `public-site/index.html` (Read), `explore.html` and `method.html` against the redesign-skill and soft-skill checklists, with the approved talk deck (`deck/deck.css`) as the target family. Nothing in `public-site/` was edited.

Where the soft-skill conflicts with Adam's recorded taste, Adam wins. The soft-skill asks for eyebrow pills, pill badges and staggered entry on everything. Adam has asked for no kickers, no pills, no source footers, and every block complete on entry with motion under two seconds. The direction below follows Adam.

## How this was captured

- Pages served by the static server in `deck/verify/lib.mjs`, which serves the same `public-site/` folder. The Python server would not start in this sandbox.
- Each page was scrolled top to bottom to fire every reveal, then captured at 1440x900 and 390x844.
- Files in `docs/site-pass/design/`: `<page>-<desktop|mobile>-fold.png` is the first screen at load. `<page>-<desktop|mobile>-partNN.png` is the full page in 3,600px (desktop) or 4,200px (mobile) slices.
- Computed styles of every visible element were tallied in the browser. The script is outside the repo; the numbers are below.

## What the numbers say

| Measure, computed in the browser | Read | Explore | Method | Deck |
|---|---|---|---|---|
| Stylesheets loaded | 6 | 15 | 4 | 1 |
| Distinct font sizes on text | 26 | 69 | 11 | 7 size tokens |
| Text elements at 9 to 11px | 139 | 3,239 | 3 | none |
| Distinct background colours | 27 | 76 | 4 | not measured |
| Distinct border colours | 14 | 36 | 2 | not measured |
| Distinct border radii | 12 | 15 | 5 | 5 in deck.css |
| Eyebrows plus part marks | 16 | 43 | 2 | slide eyebrows only |
| Source or "computed by" lines | 25 | 15 | 1 | per slide, approved there |
| Paragraphs wider than about 75 characters (estimate) | 32 of 79 | 131 of 248 | 5 of 17 | not applicable |
| Page height at 390px wide | 28,656px | 50,855px | 3,128px | not applicable |
| Horizontal page overflow at 390px | none | none | none | not applicable |
| Console errors or failed requests | none | none | none | not applicable |

The ten panel stylesheets alone hard-code 101 distinct hex colours. They fall into about ten hue families: royal blue, the deck orange, terracotta, teal, forest green, gold, plus the sky, purple, red and amber ladder rungs. The deck has one accent: orange means "differs from the reference". No panel script writes a colour, so every colour fix below is CSS-only.

The paragraph-width figure is an estimate from rendered width divided by font size at about 1.95 characters per em. Treat it as a ranking, not a count.

## The diagnosis in five lines

1. The shell (`site/site.css`, `site/read.css`) is close to the deck. The ten panel stylesheets and the three legacy sheets underneath it are a different design language: 2px corners, offset block shadows, teal and terracotta, 10 to 11px labels and native form controls.
2. Every section wears three labels before its headline: a part mark, a mono eyebrow, then the headline. Then it ends in a mono "Sources" line. That scaffolding is the strongest "report template" signal on the site.
3. The spectrum ladder appears in at least nine places, so it stops meaning anything.
4. Explore is twenty white plates on navy, each with its own coloured rail and drop shadow. It reads as pasted documents, not one product.
5. Type has no scale. Headlines run from Archivo 400 to 850 at 21 to 66px with no fixed steps. Body text drops to 9 to 11px inside panels.

## Findings

Scope key. **Shared CSS** means `site/site.css` or `site/read.css` only. **Panel CSS** means one or more of the ten panel stylesheets, or `deep-insights.css`. **HTML/JS** means markup in a page or a panel module has to change.

### Priority 1

| # | Page | Component or selector | What is generic or cheap | Fix | Scope |
|---|---|---|---|---|---|
| 1 | All | Stylesheet cascade: `styles.css`, `reader.css` and `presentation.css` under `site.css`, plus ten panel files on Explore | `site.css` re-skins legacy rules after the fact, and every panel file keeps its own palette. That produces 69 font sizes and 76 backgrounds on Explore. | Define the tokens below once in `site.css`. Replace every hex in the ten panel files with a token. Panel files may set layout only. | Panel CSS |
| 2 | Explore, Read | Panel colours: teal `#075d79`, `#116b58`, `#176f5d`, `#075642`; terracotta `#a34830`, `#a24430`, `#bd704c`, `#bf7049`, `#965414`; gold `#c6a452`, `#f0ddaa`, `#f2b239` | About ten hue families against the deck's single orange. Teal means "accepted" in one panel and nothing in the next. | Two semantic colours only. Blue means match, primary or link. Orange (`--diff`) means differs from the reference. Everything else uses the neutral ramp. Map teal to blue and terracotta to `--diff`. Remove gold. | Panel CSS |
| 3 | All | Spectrum ladder: header scroll rail, footer rail, `.part-mark` rungs, plate rails (`inset 0 4px 0 var(--rail)`), `.decision-strip li::after` tabs, `.example-decisions` bars, deep-insights card rails, `.story-chapter::before`, `.story-nav-track` | Rainbow as decoration in nine places. The four decisions get sky, amber, red and green tabs that carry no meaning anywhere else. | Keep the ladder in two places only: the header reading rail (the deck's progress bar) and the logo. Number the decisions 1 to 4 in plain text. Plates and cards get no top rail. | Shared CSS, Panel CSS (`deep-insights.css`) |
| 4 | All | `.part-mark` (4 on Read, 3 on Explore), `.eyebrow` (12 on Read, 40 on Explore, 2 on Method), `.analysis-library-kicker` | Three labels stacked above every headline. Breadcrumb eyebrows such as "Results / Format and agreement" and "01 / Paired prompt comparisons" are filing labels, not design. | Delete both. A fast pass is `display: none` in `site.css`. The follow-up removes them from the HTML. The sticky section nav already says where you are. | Shared CSS now, HTML later |
| 5 | Read, Explore | `.source-line` after each Read section; "Computed by s0x_*.py from …" footers in each deep-insights card; per-panel source footnotes | Mono source footers on every block. Adam has asked for none. They also add a second hairline 60px above each section's bottom rule. | Provenance stays on hover: `.num` already carries `data-source`. Add one collapsed "Sources and scripts" list at the end of each page, and list per-claim scripts on Method. | Shared CSS (hide) plus HTML and `deep-insights.js` (move) |
| 6 | Read | `.num` in prose (`read.css`: `text-decoration: underline dotted`) | Nine dotted underlines in the hero lede alone. It reads as spellcheck marks. | `.num { text-decoration: none; }` and `.num:hover, .num:focus-visible { text-decoration: underline dotted; }`. Keep the `title` and `cursor: help`. | Shared CSS |
| 7 | Read | Hero scene (`site/hero.js`, `.hero-stage`, `.hero-key`) | At 1.5s the scene is scattered white dots with no orange and no ring. The settle takes `SETTLE 1.7 + STAGGER 0.7`, about 2.4s, which is over the two-second rule. Points touch the frame edge and clip on the right. The key card below describes marks the viewer cannot yet see, and also explains the nine-cell grid that only appears in Finding 1. | Set `SETTLE` to about 1.0 and `STAGGER` to about 0.4. Inset the grid by one point-spacing so nothing clips. Render the static lattice already settled so first paint shows the answer. Cut the key to the two lines about orange and the ring, and move the nine-cell explanation to Finding 1. | HTML/JS (`hero.js`, `index.html`) |
| 8 | Explore | `main > [data-surface="paper"].section` plates, about twenty, each `1px #d3dce7`, radius 14, `0 30px 70px -44px rgba(0,0,0,.8)` | Full-width white sheets alternating with navy seams. Each brings its own rail colour, and inside each the legacy look returns. | Make Explore one continuous paper canvas: navy header, then one light reading surface, then navy footer. Remove plate radius, shadow, rail and side gutters. Separate sections with 96px of space and one `--p-rule` hairline. | Shared CSS |
| 9 | Explore | Offset block shadows: `cohort-reviews.css` (`8px 8px 0 #e6edf0`, `5px 5px 0`), `cross-category.css` (`10px 10px 0`, `5px 5px 0`), `agreement-policy.css` (`10px 10px 0 #e2ece8`, `5px 5px 0`) | A neo-brutalist card style foreign to the deck. It is the clearest "different family" signal on Explore. | Delete every offset shadow. Use one 1px `--p-rule` border at radius 14. | Panel CSS |
| 10 | Explore, Read | Text below 12px: 1,333 elements at 10px, 1,880 at 11px and 26 at 9px on Explore; 46 at 10.3px and 8 at 9px on Read | Cramped, unreadable on a laptop, and cheap-looking. 283 of these are 10px uppercase sans with little or no tracking. | Set a 13px floor for labels and 15px for table body. The only exception is chart axis ticks at 12px mono. Apply the scale below. | Panel CSS, Shared CSS |
| 11 | All | Headings | Read h2 is Archivo 800 at 44.6px. Explore h2 is Archivo 700 at 43, 46, 54, 54.7 and 63px. Explore h3 and h4 drop to Archivo 400 at 36 and 29px (`jev-1.13.0`, "Scores and resource use"). Panel heads use `--quote`, which is sans 400, at 23 to 35px. The weight jumps from 800 to 400 inside one panel. | One scale for all three pages (below). Add a `:where()` override in `site.css` for `h2`, `h3` and `h4` inside panels, and delete the font rules from the panel files. | Shared CSS plus Panel CSS |
| 12 | Read | Deep insights, `#deep-insights` (`deep-insights.css`, `deep-insights.js`) | Three equal columns of uneven cards leave 300 to 500px of dead space under the short ones. Headlines are four- and five-line sentences. "SOLID" and "DESCRIPTIVE ONLY" are outlined pills. Each card has a "Computed by" footer. 60-plus boxed DEV-id chips sit in the routing table. The calibration chart uses green and amber. It is the densest and least finished block on the page that should be the most finished. | One column. Each finding is a two-column row: a claim of 12 words or fewer on the left, with three or four stat rows on the right. Status words become plain text after the claim. Review ids become plain mono text. The calibration chart uses blue for Jev and a dashed neutral for Clef Flash. | HTML/JS plus Panel CSS |

### Priority 2

| # | Page | Component or selector | What is generic or cheap | Fix | Scope |
|---|---|---|---|---|---|
| 13 | Read, Explore | Review-id chips: deep-insights routing table, `agreement-policy` deferred list with green borders, `cohort-reviews` | Dozens of bordered mono boxes. It reads as chip soup. | Plain mono 13px text in `--n300` or `--p-muted`, separated by thin spaces. Underline on hover. No border, no fill. | Panel CSS |
| 14 | Explore | Tables: zebra `rgba(21,101,192,.035)` on 1,343 cells, 805 borders in `#d3dce7`, header fills, peach "Differs" cell fills in `disputed-reviews` | Every rule turned on at once. In the disputed-reviews table, snake_case values break mid-word ("insufficient_info / rmation"), which looks broken. | Use the table spec below. Render display labels such as "Can't tell" instead of raw keys, or set `overflow-wrap: normal; hyphens: none` on value cells. Mark "differs" with orange text and a 6px orange dot, not a cell fill. | Panel CSS, plus `disputed-reviews.js` for labels |
| 15 | Explore (mobile) | Wide tables at 390px: `cross-category` outcome table, pair tables, disputed-reviews matrix | Columns are clipped ("Exact IDs", "Unusa…") inside an inner scroller with no visible cue. | Wrap each in a scroller with a right-edge fade mask (`mask-image: linear-gradient(90deg, #000 85%, transparent)`). Below 640px, switch the pair and outcome tables to stacked rows. | Shared CSS (mask), HTML/JS (stacked rows) |
| 16 | Explore | `outcome-chart` scatter | All points pile against x = 60, so about 90% of the plot is empty. Five category colours (blue, teal, brown, black, grey) are unrelated to the deck. | Start the x domain at the data minimum rounded down, around 40. Encode category by shape, or by blue against neutral, not by five hues. | `outcome-chart.js` plus Panel CSS |
| 17 | Read | Calibration chart inside deep insights | Green and amber series bring in two more hues. | Blue for Jev, dashed `--n300` for Clef Flash, and a diagonal reference line in `--n600`. | Panel CSS |
| 18 | Read | `.rule-pair` > `.rule-stats div`, `.rule-queue`; Explore cream `#fffdf7` sub-panel inside a plate | Cards inside cards inside sections, three surface levels deep. | Stat tiles get no box (see the stat tile spec). One raised surface level at most. Remove the cream panel. | Shared CSS, Panel CSS (`extended-cases.css`, legacy rules) |
| 19 | All | Header: `.brand` 11px/600 two-line text; `.main-nav a[aria-current]` uses both a background and an inset underline; `.layer-nav a[aria-current]` is a filled royal pill | The brand lockup is too small to register. Two active indicators compete. The filled blue layer pill outshouts the primary call to action. On mobile the header is two rows (about 95px) and the section nav clips mid-word ("8 Octo") with no cue. | Use the horizontal AEA logo at 24px tall as the one lockup, with the benchmark name in 13px beside it. Active section link: paper text plus a 2px `--blue-300` underline, no background. Layer switch: text links with the same underline, no fill. Mobile: one row with logo and layer links. The section nav gets an edge fade or becomes a "Sections" select. | Shared CSS, HTML for the logo |
| 20 | Method, Explore, Read | `summary` disclosures: Method FAQ, Explore "Decision models", Read "Three more recomputed patterns" | Default browser triangles. | `summary { list-style: none; }` plus a 12px chevron (inline SVG background) that rotates 90° when open, 44px row height and a hover fill of `--n800` or `--p1`. | Shared CSS |
| 21 | Method | Two-column `#method` layout | The left column ends about 330px above the FAQ, leaving a dead hole. The reference-review and tooling blocks sit as orphans with large gaps. | One 68ch column for the method text. The FAQ goes full width below it as a two-column grid of questions. | Shared CSS, small HTML change |
| 22 | Explore | Native `select` and `input` in panels: radius 2px, `#94abb6` borders, 13px | Default form controls inside an otherwise designed page. | One shared rule: `:where(main) select, :where(main) input` with height 44, radius 8, 1px `--p-rule`, 15px text, a custom chevron, and a focus ring of 2px `--blue` at 2px offset. | Shared CSS |
| 23 | Explore, Read | Paragraph measure | An estimated 131 of 248 paragraphs on Explore and 32 of 79 on Read run past 75 characters, up to about 220. | `max-width: 68ch` on `p` and `li` in every section and panel intro. Tables and figures stay full width. | Shared CSS |
| 24 | All | Vertical rhythm: section padding `clamp(48..96)`, part-mark margins `clamp(56..104)`, plate margins `clamp(12..20)`; double hairlines (source-line top border plus finding bottom border) | No fixed spacing steps, so gaps vary from 12 to 230px between sections. | Use the spacing scale below: 96px between sections (64 on mobile), 16px from h2 to dek, 32px from dek to component. One hairline between findings. | Shared CSS |
| 25 | Explore | Uppercase labels: 13 distinct uppercase styles, including 10px sans with no tracking (×163) | No single label style. | Drop uppercase for table heads and form labels and use sentence case at 13px/500. If any uppercase survives, use exactly one style: mono 12px/500 with 0.12em tracking. | Panel CSS |
| 26 | Explore | Loading text as headline: "Loading paired prompt results…", "Loading Jev decision profile…", "Loading observed costs…", "Loading difficult comments…" in `h2` | The headline slot shows a status message before the data arrives, and shows it forever if a script fails. | Put the real headline in the HTML and let the script fill numbers only. While a panel loads, show a skeleton bar of the same height in `--p1`. | HTML/JS (`app.js`, `findings.js`) |
| 27 | Read | Count-ups (`site/motion.js`, `[data-countup]`, 1.4s) | Numbers spin up instead of being there. Adam's rule is that information is complete on entry. | Delete the count-ups. Keep the opacity and 28px rise reveals, which are 0.7s with a 0.08s stagger and stay under two seconds. | HTML/JS (`motion.js`) |

### Priority 3

| # | Page | Component or selector | What is generic or cheap | Fix | Scope |
|---|---|---|---|---|---|
| 28 | Read | `.action` primary button: `0 12px 28px -14px rgba(21,101,192,.9)` glow and the magnetic pull in `motion.js` | A blue glow where the deck says no glow. The magnetic effect is decoration. | Remove the glow shadow. Keep the pill, since it is the only primary action. Remove the magnetic pull. | Shared CSS, `motion.js` |
| 29 | Explore | Resource-use panel shows "Unavailable" at 36px as if it were a stat | The empty state is styled as a headline. | In the stat slot, put an en dash in `--p-muted`. Below it, a 15px line saying why the value is missing. | Panel CSS, `app.js` |
| 30 | Read | `.hard-tag` chips ("Off-topic", "Disputed label", "Jev missed") on each hard-review row | Three bordered chips per row. | Show one muted text label. "Jev missed" becomes an orange 8px dot before the id. | Shared CSS |
| 31 | All | Footer: card on `--n800` with a full-width ladder rail | A boxed footer plus one more rainbow. | Flat footer on the ground colour with a top hairline. Remove the rail. | Shared CSS |
| 32 | Read | `.decisions .hero-example`: a white paper card with blue inset rail and heavy shadow on navy | The one light card in a dark section looks pasted in. | Keep the paper card, since it stands for the document under test. Remove the inset rail and drop the shadow to the paper elevation token. | Shared CSS |

What already passes: visible focus rings (3px `--blue-200`), a skip link, `prefers-reduced-motion` handling, tabular numbers in tables, no horizontal page overflow at 390px, no console errors, one display face and one body face, and a hero scene whose motion carries information (60 reviews, the six that differ).

Not verified: in the full-page slice of the Read page, the hero appeared dimmed after the page had been scrolled down and back to the top (`index-desktop-part01.png`). The load-time capture (`index-desktop-fold.png`) is at full brightness. This may be the scroll-linked hero exit in `motion.js` not restoring, or an artefact of Playwright's full-page capture. Check it by hand.

## Proposed direction: "the deck, printed well"

The deck is the reference: flat Ink Navy, paper text, one orange that means "differs", Archivo for display, IBM Plex Sans for body, IBM Plex Mono for numbers and ids, and generous space. The site should feel like the printed companion to that deck. Read stays on ink, like the talk. Explore becomes one long paper document, because dense tables read better dark-on-light. Method stays on ink. No labels above headlines, no rainbow, no boxes inside boxes.

### Tokens (replace the `:root` block in `site/site.css`)

```css
:root {
  /* Type: one scale, three faces. Mono is for numbers, ids and code only. */
  --f-display: 'Archivo', ui-sans-serif, system-ui, sans-serif;
  --f-sans: 'IBM Plex Sans', ui-sans-serif, system-ui, sans-serif;
  --f-mono: 'IBM Plex Mono', ui-monospace, Menlo, monospace;
  --t-h1:    850 clamp(44px, 5vw, 76px)/.98 var(--f-display);   /* tracking -.035em */
  --t-h2:    800 clamp(30px, 3vw, 46px)/1.05 var(--f-display);  /* tracking -.03em, max 22ch */
  --t-h3:    700 clamp(20px, 1.6vw, 24px)/1.25 var(--f-display);/* tracking -.01em */
  --t-lede:  400 clamp(18px, 1.4vw, 21px)/1.55 var(--f-sans);   /* max 60ch */
  --t-body:  400 17px/1.65 var(--f-sans);                       /* max 68ch */
  --t-small: 400 15px/1.55 var(--f-sans);                       /* captions, table body */
  --t-label: 500 13px/1.35 var(--f-sans);                       /* table heads, form labels, sentence case */
  --t-stat:  800 clamp(36px, 3.4vw, 56px)/1 var(--f-display);   /* tabular-nums, tracking -.02em */
  --t-big:   900 clamp(72px, 8vw, 128px)/.9 var(--f-display);   /* one per page at most */
  --t-tick:  500 12px/1.2 var(--f-mono);                        /* chart axes only; the only text under 13px */

  /* Space: 4px base. Sections 96 (64 on mobile); h2 to dek 16; dek to component 32; component gap 24. */
  --s-1: 4px; --s-2: 8px; --s-3: 12px; --s-4: 16px; --s-5: 24px; --s-6: 32px;
  --s-7: 48px; --s-8: 64px; --s-9: 96px; --s-10: 128px;

  /* Ink (Read, Method, header, footer). */
  --n950: #0f1626; --n900: #1a2332; --n800: #20293c; --n700: #2b3650; --n600: #3a4763;
  --n500: #51607f; --n300: #93a0bb; --n200: #c2cad9; --paper: #fbfcfe;
  /* Paper (Explore canvas). */
  --p0: #fbfcfe; --p1: #f1f4f8; --p-rule: #dde3ec; --p-text: #1a2332; --p-muted: #4b586b;
  /* Meaning. Two colours, nothing else carries hue. */
  --blue: #1565c0; --blue-300: #5e9ce8;     /* match, primary, link (300 on ink) */
  --diff: #f57c00; --diff-text: #b85a00;    /* differs from the reference; text variant for paper (check it clears 4.5:1) */
  /* Sequential data: blue mixed into the neutral, as the nine-cell glyph already does. */
  --seq: color-mix(in oklab, var(--blue) calc(var(--v) * 1%), var(--n700));
  /* The ladder survives only as the header reading rail and in the logo. */

  /* Shape. Three radii, two elevations. */
  --r-1: 4px; --r-2: 8px; --r-3: 14px;      /* bars and dots / controls / frames */
  --e-ink: none;                            /* on ink, separate with --n800 plus a 1px --n700 rule */
  --e-paper: 0 1px 2px rgba(15, 22, 38, .06), 0 8px 24px -12px rgba(15, 22, 38, .14); /* floating things only */
  --ease: cubic-bezier(.215, .61, .355, 1); /* entrances 0.7s; nothing on the page takes over 2s */
}
```

### Component treatments

- **Section header.** An h2 (`--t-h2`, at most 22ch) and one dek sentence (`--t-lede`, at most 60ch). No eyebrow, no part mark, no number. Spacing is 96px above, 16px between, and 32px before the content.
- **Stat tile.** No box. The number is in `--t-stat` with tabular figures. The denominator ("/60") is at 0.45em, weight 600, in `--n300`. Below it sits a 15px sentence-case label in `--n300` or `--p-muted`. Tiles in a row are divided by 1px vertical hairlines, never by cards. One `--t-big` hero number per page at most.
- **Table.** Body is 15px Plex Sans. Numbers are mono, tabular and right-aligned. Ids are mono 13px plain text. Head cells are `--t-label` in `--n300` or `--p-muted`, sentence case, with a 1px bottom rule in `--n500` or `--p-rule`. Rows are 44px with 1px hairlines: no zebra, no cell fills, no vertical rules. "Differs" is `--diff-text` with a 6px orange dot. The sticky head sits on the surface colour with `--e-paper`. Below 640px, wide tables either fade at the right edge or stack.
- **Chart frame.** A `figure` with no box on paper. On ink it is one `--n800` frame at `--r-3` with 32px padding. It starts with an h3 title, then one caption line that says what to look at, with the legend inline as coloured words. Axes are `--t-tick` in `--n300` or `--p-muted`. Gridlines are 1px at 50% opacity. At most two data colours (blue and orange) plus neutrals. The plotted domain is fitted to the data.
- **Callout (implication).** A 3px `--blue` left rule, no background, text at 18px/600 in paper or ink. At most one per section.
- **Hard-review card.** Mono 13px id in `--n300` on top, then the quote at 20px/500. To the right, a seven-segment bar where orange segments mark the decision models that differ, with "5 of 7" in `--t-stat` at 0.6 scale. If Jev missed it, an 8px orange dot sits before the id. No tag chips.
- **Navigation.** One 56px bar on `--n900` with a 1px `--n700` bottom rule and the 2px ladder reading rail. Left: the AEA horizontal logo at 24px tall plus the benchmark name in 13px `--n200`. Middle: section links in 14px/500 `--n200`, with the active one in `--paper` and a 2px `--blue-300` underline. Right: Read, Explore and Method as text links with the same active treatment, set off by a 1px rule. On mobile the bar keeps the logo and the three layer links. Sections become an edge-faded scroller or a "Sections" select.

### Delete

- `.part-mark` everywhere, and the rule-draw animation in `motion.js` that goes with it.
- `.eyebrow` everywhere, including the hero's "A talk companion · AI Enablement Academy". The logo already carries that.
- `.source-line`, the deep-insights "Computed by" footers and per-panel source footnotes. Provenance moves to number hover and one sources list per page.
- Rainbow uses: part-mark rungs, plate and card top rails, `.decision-strip` tabs, `.example-decisions` bars, deep-insights card rails, `.story-chapter::before`, `.story-nav-track`, the footer rail and ladder eyebrow ticks. Keep the header reading rail and the logo.
- "SOLID" and "DESCRIPTIVE ONLY" pills, review-id chip boxes, `.hard-tag` chips.
- Offset block shadows, the plate drop shadows, the cream `#fffdf7` and peach cell fills, and the teal, terracotta and gold hex values.
- Dotted underlines on `.num`, count-ups, the magnetic pull and the call-to-action glow.

## Which fixes are CSS-only

| Change | Where | Findings |
|---|---|---|
| Tokens, type scale, spacing, measure, headings, disclosures, form controls, header styling, footer, CTA glow, `.num` underline, hard-tag chips | Shared CSS: `site/site.css`, `site/read.css` | 6, 11, 19, 20, 22, 23, 24, 28, 30, 31, 32 |
| Hide eyebrows, part marks and source lines as a fast pass | Shared CSS (`display: none`) | 4, 5 |
| Rainbow removal on the shell; Explore as one paper canvas; table edge fade | Shared CSS | 3, 8, 15 |
| Panel colours to tokens, offset shadows out, font floor, label style, id chips, cream and peach fills, calibration chart colours | Panel CSS (ten files plus `deep-insights.css`, `extended-cases.css`) | 1, 2, 9, 10, 13, 14, 17, 18, 25 |
| Hero settle timing, edge inset and key copy | HTML/JS: `site/hero.js`, `index.html` | 7 |
| Deep-insights rebuild as a one-column findings list; sources moved to one list | HTML/JS: `deep-insights.js`, `deep-insights-section.html`, `index.html` | 5, 12 |
| Value labels instead of snake_case keys | HTML/JS: `disputed-reviews.js` | 14 |
| Stacked tables on mobile | HTML/JS: panel modules or `navigation.js` | 15 |
| Scatter domain and category encoding | HTML/JS: `outcome-chart.js` | 16 |
| Real headlines in HTML instead of "Loading…"; empty-state copy | HTML/JS: `explore.html`, `app.js`, `findings.js` | 26, 29 |
| Count-ups and magnetic pull removed | HTML/JS: `site/motion.js` | 27, 28 |
| Method single column; logo lockup in header | HTML: `method.html`, all three headers | 19, 21 |

Fix 1 is the root of findings 2, 9, 10, 11 and 25. Do it first, so later fixes land in one token layer instead of in fifteen files.

## Five highest-impact fixes

1. **Strip the label scaffolding.** Hide every eyebrow, part mark, source line and dotted number underline. This is about 20 lines of CSS in `site.css` and `read.css`, and it changes the feel of all three pages at once.
2. **Cut colour to blue, orange and neutrals.** Keep the ladder only in the header rail and the logo. Map the 101 panel hex values to tokens. Delete the offset block shadows. This is CSS only.
3. **One type scale with a 13px floor**, applied to the shell and the panels through `:where()` overrides. This takes Explore from 69 font sizes to about 10. CSS only.
4. **Make Explore one paper canvas instead of twenty plates.** Restyle native controls and tables to the table spec. CSS only.
5. **Rebuild the two weakest Read blocks.** Deep insights becomes a one-column findings list. The hero settles in under two seconds, already showing its orange marks, with a two-line key. This needs JS and HTML.
