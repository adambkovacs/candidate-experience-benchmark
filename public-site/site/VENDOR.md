# Vendored files

Everything the site shell needs is served from this folder, so GitHub Pages needs no CDN at runtime.
Each file below was taken unmodified from the named npm tarball (`registry.npmjs.org`) and checked
with `shasum -a 256` on 2026-10-08.

## Libraries

| File | Package | Published | SHA-256 |
|---|---|---|---|
| `vendor/gsap/gsap.min.js` | `gsap@3.15.0` `dist/gsap.min.js` | 2026-04-13 | `92bb9a96476f983d212a2bc4f54c889039c1696dd4461d40a736860938570fbb` |
| `vendor/three/three.module.min.js` | `three@0.185.0` `build/three.module.min.js` | 2026-06-25 | `86bcee248b64f44bcfc23c331ae74619061957d59cab040171dcb6fb5900beb6` |
| `vendor/three/three.core.min.js` | `three@0.185.0` `build/three.core.min.js` | 2026-06-25 | `0e9dd2793e01d0d9eb4f2ab00b4ffcdd4488275ebebee5c31fa8d347bc29f0bf` |

Tarball integrity as reported by `npm view`:

- `gsap@3.15.0`: `sha512-dMW4CWBTUK1AEEDeZc1g4xpPGIrSf9fJF960qbTZmN/QwZIWY5wgliS6JWl9/25fpTGJrMRtSjGtOmPnfjZB+A==`
- `three@0.185.0`: `sha512-+yRrcRO2iZa8uzvNNl0d7cL4huhgKgBvVJ0njcTe8xFqZ6DMAFZdCKDP91SEAuj25bNAj7k1QQdf+srZywVK6w==`

ScrollTrigger (`gsap@3.15.0` `dist/ScrollTrigger.min.js`, SHA-256
`b0b14d67b55b0c43c756ac0b106cfcb09d0879945f6ead64451065b0672916a2`) was vendored, then removed on 2026-10-08.
Its `refresh()` saves and restores scroll positions. Called while the data panels were still rendering, that
sent deep links such as `#inspect` and `#method` thousands of pixels off target. With only ScrollTrigger
blocked, the same links landed correctly. The one scrubbed effect it drove now uses a passive scroll listener.

Licenses: GSAP ships under the GreenSock standard license (https://gsap.com/standard-license, named in the
file header). three.js is MIT (`vendor/three/LICENSE`).

`three.module.min.js` imports `./three.core.min.js`, so the two files must stay side by side.
three.js is loaded only by `hero.js`, through a dynamic `import()`, after the hero is on screen.

## Fonts

| File | Package | Published | SHA-256 |
|---|---|---|---|
| `fonts/archivo-latin-wght-normal.woff2` | `@fontsource-variable/archivo@5.3.0` | 2026-07-19 | `8f704806dbedeaaeca334b11ec348bc3ac3a439d6431544b3afb54f534ee4967` |
| `fonts/ibm-plex-sans-latin-wght-normal.woff2` | `@fontsource-variable/ibm-plex-sans@5.3.0` | 2026-07-19 | `e2291e842cf5af167122a22881a740c7f2dda7716f1e8cd76680264f4a859470` |
| `fonts/ibm-plex-mono-latin-400-normal.woff2` | `@fontsource/ibm-plex-mono@5.3.0` | 2026-07-19 | `08949f728dc52d528e69b1667d15c89a5686a4ee9a296ff90983985f99c380f7` |
| `fonts/ibm-plex-mono-latin-500-normal.woff2` | `@fontsource/ibm-plex-mono@5.3.0` | 2026-07-19 | `01d285447409c8a588692162439a038b8cbd7871309ee20267b0d2d91c6e8e22` |
| `fonts/ibm-plex-mono-latin-600-normal.woff2` | `@fontsource/ibm-plex-mono@5.3.0` | 2026-07-19 | `0d1f0b8d0722224e32e9f28261bdc86c79115be73444ae5eceb73976a1bcdf83` |

All three families are SIL Open Font License 1.1; the license texts sit next to the files.

## Brand marks

| File | Source | SHA-256 |
|---|---|---|
| `aea-icon-transparent.svg` | copy of `public-site/deck/assets/aea-icon-transparent.svg` | `39c294ec2d101a129f8a66e5145d2e3d848b94a389da3146e9db87db00e2914b` |
| `aea-logo-horizontal-transparent-white.svg` | copy of `public-site/deck/assets/aea-logo-horizontal-transparent-white.svg` | `b1ce5e4f5d1bab353b9f4c604eb19162713c95646f5ceae184291c21abd552e5` |

## Re-checking

```bash
cd public-site/site
shasum -a 256 vendor/gsap/*.js vendor/three/*.js fonts/*.woff2 aea-*.svg
```
