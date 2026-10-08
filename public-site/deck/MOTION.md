# MOTION

Read this in full before designing, generating or animating anything for this deck. Every colour, font, timing and motion value comes from here. The file sets the look, not the ambition: when asked to go all out, go all out. If something is not covered, ask rather than choosing. When finished, check your frames against this file (run `deck/verify/fit.mjs` and `numbers.mjs`), fix what fails, and only then show it.

Delivery shapes everything below. Adam presents from his laptop in Chrome, screen-shared over Zoom to a TV at 1920x1080 or larger. Zoom sends roughly 30 frames per second and compresses hard: fine detail smears, thin lines shimmer, small type turns to mush. Design every move to read at 30fps through compression. 1920x1080 is the primary check; 1366x768 and 1280x720 are secondary.

## 1. Colours

| Role | Hex | Use |
|---|---|---|
| Ground | `#1a2332` | Every slide. Flat, never a gradient (navy gradients band into visible rings on screens) |
| Surface | `#20293c` | Panels such as the live replay, cards (`rgba(251,252,254,.035)` over ground) |
| Rule | `#2b3650`, `#3a4763` | Table rules, tracks, meter backgrounds |
| Ink | `#fbfcfe` | Headlines, body, numbers, scene points |
| Muted | `#c2cad9`, `#93a0bb` | Ledes and captions; eyebrows, labels, source lines |
| Accent | `#1565c0` | Primary Royal Blue: eyebrow ticks, quote rails, bars. Too dark for text on navy |
| Accent text | `#9cc3f2`, `#5e9ce8` | Emphasis words in headlines (`em`), links, the typing caret, latency track |
| Second accent | `#f57c00` | Means one thing only: differs from the reference (`--diff`). Misses in the scene, flipped cells, wrong answers |
| Key | `#fbc02d` | Rare highlights: the "Replay of saved answers" badge, a key timeline event |
| Spectrum ladder | `#7e57c2` `#5c6bc0` `#29b6f6` `#66bb6a` `#fbc02d` `#f57c00` `#e53935` | Top rails (6px hard-stop rungs), card rails, the progress bar, the ladder mark. Never a background |

## 2. Type

| Use | Font | Size at 1080 | Notes |
|---|---|---|---|
| Title (`h1`) | Archivo 850 | 108px | Tracking -0.035em, line height 0.98 |
| Slide headline (`h2`) | Archivo 800 | 76px | Tracking -0.03em, max 22ch |
| Statement | Archivo 800 | 104px | One line of thought, max 17ch |
| Hero number | Archivo 900 | 340px | Tabular figures; unit at 120px in muted |
| Lede | IBM Plex Sans 400 | 40px | Muted `#c2cad9` |
| Body | IBM Plex Sans 400 | 30px | Never below 28px for reading text |
| Review quote | IBM Plex Sans 400 | 52px (34px in the live panel) | |
| Eyebrow | IBM Plex Mono 500 | 18px | Uppercase, tracked 0.18em, blue tick |
| Source line | IBM Plex Mono 400 | 17px | Every slide with a number |
| Floor | | 16px | Nothing on a slide is smaller; `fit.mjs` fails it |

## 3. Timing

The presenter's clicker sets the pace. Every move finishes before the next click is likely, and every slide holds as long as the speaker talks.

| Moment | Duration | Detail |
|---|---|---|
| Slide change | 0.4s fade | Reveal "fast"; backward navigation shows final states instantly |
| Headline words rise | 1.0s each, 0.055s apart | Out of masks; never a fade |
| Masked line (`data-split="line"`) | 1.0s | Rises from behind a clean cut |
| Staggered settle (lists, cards, stats) | 0.7s each, 0.08s apart | 28px rise |
| Count-up | 1.4s | Ends on the exact feed string |
| Split-flap flip | 0.2s over, 0.45s land | Lands in `#f57c00` |
| Timeline line | 0.9s per step | Event text drops in 0.25s later |
| Scene settle | 1.7s per point, staggered left to right over 0.7s plus seeded jitter | Field, lattice, figure, mark |
| Title fly-in | 3.2s camera dolly | Points arrive through depth into the lattice |
| Typing (live replay) | about 38 characters a second, 0.14s pause after punctuation | Starts 0.35s after the slide lands |
| Latency tick | the saved median request time, clamped to 0.6 to 1.6s | Then one field every 0.42s |

The hold is never frozen: scene points drift or breathe (highlighted points pulse ±8% at about 0.35Hz), and the caret blinks once a second until the request is sent.

## 4. How things move

- One object changing shape beats a cut. Points become a lattice, the lattice becomes the score, the score's points become the mark. Cells flip from the reference to the answer.
- Easing, one family: `power3.out` for entrances, `power4.out` for type masks, `power2.out` for numbers and bars (never overshoot), `power2.inOut` for lines, cubic ease-out for scene points, linear only for typing and the latency track.
- Stagger by a beat: rows, words, cards and points each start a little after the last. Everything at once reads as a slide transition.
- For 30fps: no move shorter than 0.2s (six frames), travel at least 18px, anything that carries meaning at least 10px thick (meters 14px, the latency track 10px), points 18 to 34px at 1080. Thinner things (6px rails, 1px rules) are decoration only, never the thing that carries meaning.
- Handmade where it helps: typing pauses at punctuation; the scene's stagger has seeded jitter, so it is identical on every run.
- Reduced motion, print (`?print-pdf`) and speaker view show the final state, with a static SVG of each scene.

## 5. Texture and finish

Flat Ink Navy, no grain, no noise. Depth comes from the three.js scene: points near the camera soften like a lens, nothing else blurs. Panels have a 14px radius, one 1px rule and one soft shadow. Rails are 6px hard-stop ladder rungs. No glow on type.

## 6. Never

1. Bounce, elastic, overshoot, confetti or sparkle bursts.
2. A flat or gradient background in spectrum colours, or a navy radial gradient (it bands on screens).
3. Hairlines, fine particle dust or tiny type carrying meaning: they smear over Zoom.
4. A number that is rounded, invented, or not bound to a feed; or a target shown as a result.
5. A replay that pretends to be live: the "Replay of saved answers" badge is always on screen.

No sound by default: the speaker is the soundtrack. ASK ME before adding any.

## 7. Done right, shot by shot: the soup review

1. The slide fades in on the request panel. "Replay of saved answers" sits top right in amber; the model line reads "Jev 1.13 · TypeSafe direct API · prompt P0".
2. After 0.35s the review types itself into the quote: "Great soup, tiny portions, wouldn't eat there again." It pauses a beat at each comma. The quote box is already at its final height, so nothing below moves.
3. Click. The caret stops. A blue latency track fills while the counter runs to the saved 1.32s median.
4. The four fields land one by one, 0.42s apart: mixed, no, no, no. Each probability bar fills and its number counts up: 0.57, 0.89, 0.94, 0.92.
5. Click. The reference column rises in, "Insufficient info" four times. Every answer turns orange with a rail, and so does every bar. The point lands without a word: confident, and wrong on all four.
6. The hold stays alive only through the speaker. Nothing else moves until the next click.
