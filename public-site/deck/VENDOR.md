# Vendored dependencies

Everything the deck needs at talk time is in this folder. Nothing loads from the network.
Versions are pinned and were at least two weeks old on 2026-10-08. Files came from jsDelivr with `curl --max-time 30 --connect-timeout 5`.
Each SHA-256 below matched the hash jsDelivr publishes for that file (`data.jsdelivr.com/v1/packages/npm/<pkg>@<version>?structure=flat`) at download time.

| Package | Version | Published | License |
|---|---|---|---|
| reveal.js | 6.0.2 | 2026-09-10 | MIT |
| gsap | 3.15.0 | 2026-04-13 | GreenSock standard no-charge license (https://gsap.com/standard-license) |
| three | 0.185.1 | 2026-07-01 | MIT |
| @fontsource-variable/archivo | 5.3.0 | 2026-07-19 | SIL OFL 1.1 |
| @fontsource-variable/ibm-plex-sans | 5.3.0 | 2026-07-19 | SIL OFL 1.1 |
| @fontsource/ibm-plex-mono | 5.3.0 | 2026-07-19 | SIL OFL 1.1 |

## Files and SHA-256

| File | Source | SHA-256 |
|---|---|---|
| `vendor/reveal/reveal.js` | https://cdn.jsdelivr.net/npm/reveal.js@6.0.2/dist/reveal.js | `aa1bbbf2617b23a623b23612cb3c5bdb63de512e652bf20fcfa832b045d37844` |
| `vendor/reveal/reveal.css` | https://cdn.jsdelivr.net/npm/reveal.js@6.0.2/dist/reveal.css | `615ee850cbbb98a0f688b60ed37b21819a3f54c9f3e6f20e33e63693ab74a0c0` |
| `vendor/reveal/reset.css` | https://cdn.jsdelivr.net/npm/reveal.js@6.0.2/dist/reset.css | `39413c3490fdcf826427c26ff4c1ee59ea961a0aa8507c18454e0c6dc96c12d8` |
| `vendor/reveal/plugin/notes.js` | https://cdn.jsdelivr.net/npm/reveal.js@6.0.2/dist/plugin/notes.js | `447c42f365876e41853de81453d0c53c580c5b2099132e8f61200de4a0ba2af3` |
| `vendor/reveal/LICENSE` | https://cdn.jsdelivr.net/npm/reveal.js@6.0.2/LICENSE | `b2883e4b610bfa1b4d8fff84c4d4b825cc7d553cbd9fec4777c04068a2859dc0` |
| `vendor/gsap/gsap.min.js` | https://cdn.jsdelivr.net/npm/gsap@3.15.0/dist/gsap.min.js | `92bb9a96476f983d212a2bc4f54c889039c1696dd4461d40a736860938570fbb` |
| `vendor/gsap/README.md` | https://cdn.jsdelivr.net/npm/gsap@3.15.0/README.md | `66a79667b0538b19634b5a000a9a3debe588c98d390424e73e5d4de847270828` |
| `vendor/three/three.module.min.js` | https://cdn.jsdelivr.net/npm/three@0.185.1/build/three.module.min.js | `86bcee248b64f44bcfc23c331ae74619061957d59cab040171dcb6fb5900beb6` |
| `vendor/three/three.core.min.js` | https://cdn.jsdelivr.net/npm/three@0.185.1/build/three.core.min.js | `05b2609338c76cd65daf74f3ac515bc9a5045e1b3b33edc07d8c9bd55250fa90` |
| `vendor/three/LICENSE` | https://cdn.jsdelivr.net/npm/three@0.185.1/LICENSE | `8b378ebe60e2fe500158cb0ac71cb5e8b7d92953c2abcc63a0eb90499653b5bc` |
| `fonts/archivo-latin-wght-normal.woff2` | https://cdn.jsdelivr.net/npm/@fontsource-variable/archivo@5.3.0/files/archivo-latin-wght-normal.woff2 | `8f704806dbedeaaeca334b11ec348bc3ac3a439d6431544b3afb54f534ee4967` |
| `fonts/LICENSE-archivo.txt` | https://cdn.jsdelivr.net/npm/@fontsource-variable/archivo@5.3.0/LICENSE | `c3c8402eec0e31dc9a76851235b1c02a0bb821488b2db8e35bcc2ab60ca8fc2b` |
| `fonts/ibm-plex-sans-latin-wght-normal.woff2` | https://cdn.jsdelivr.net/npm/@fontsource-variable/ibm-plex-sans@5.3.0/files/ibm-plex-sans-latin-wght-normal.woff2 | `e2291e842cf5af167122a22881a740c7f2dda7716f1e8cd76680264f4a859470` |
| `fonts/LICENSE-ibm-plex-sans.txt` | https://cdn.jsdelivr.net/npm/@fontsource-variable/ibm-plex-sans@5.3.0/LICENSE | `d0283623ef57e722fd0eb688a8041589670c608ab780cd3612d06ba6f153d3fd` |
| `fonts/ibm-plex-mono-latin-400-normal.woff2` | https://cdn.jsdelivr.net/npm/@fontsource/ibm-plex-mono@5.3.0/files/ibm-plex-mono-latin-400-normal.woff2 | `08949f728dc52d528e69b1667d15c89a5686a4ee9a296ff90983985f99c380f7` |
| `fonts/ibm-plex-mono-latin-500-normal.woff2` | https://cdn.jsdelivr.net/npm/@fontsource/ibm-plex-mono@5.3.0/files/ibm-plex-mono-latin-500-normal.woff2 | `01d285447409c8a588692162439a038b8cbd7871309ee20267b0d2d91c6e8e22` |
| `fonts/ibm-plex-mono-latin-600-normal.woff2` | https://cdn.jsdelivr.net/npm/@fontsource/ibm-plex-mono@5.3.0/files/ibm-plex-mono-latin-600-normal.woff2 | `0d1f0b8d0722224e32e9f28261bdc86c79115be73444ae5eceb73976a1bcdf83` |
| `fonts/LICENSE-ibm-plex-mono.txt` | https://cdn.jsdelivr.net/npm/@fontsource/ibm-plex-mono@5.3.0/LICENSE | `23b0a9d0c6d3f140a0b77e483c5cfa6bba574325ef5cb189ed9f2fec4884533f` |

## Why these versions

- **reveal.js 6.0.2** still ships a UMD build (`dist/reveal.js`), the speaker-notes plugin with its view inlined, and `?print-pdf`. Reveal rounds its stage scale to 0.01, so `deck.js` sets `margin: 0.01` to keep the rounded stage inside the viewport.
- **three 0.185.1**, not 0.186.x: the 0.186 npm packages no longer include `three.module.min.js` / `three.core.min.js`. The minified pair is 750 KB; the unminified 0.186 pair is 2.1 MB. The scene loads it with a dynamic `import()` after the deck is ready.
- **GSAP 3.15.0** core only. The split-text reveal is about 20 lines in `motion.js`, so the SplitText plugin is not vendored.
- **Fonts**: latin subsets only. Archivo and IBM Plex Sans are variable (one file each covers 100 to 900 and 100 to 700). Characters outside latin fall back to system fonts.

## Updating

Download the new file into the same path, recompute with `shasum -a 256 <file>`, compare it with the jsDelivr hash, update this table, then run `deck/verify` (see `deck/README.md`).
