// Entry and click-through of the hero sequences (S12 flips, S13 card wall, S14 gate, S16 sort) as a presenter would see them.
// v4: every hero is complete on entry (information before animation); only the S16 re-sort keeps a click. For each entry or
// click: counts animation frames until motion settles, asserts the final state from the DOM, and requires entry motion to land
// in under about two seconds.
// Modes: default (motion), --reduced-motion (final states must land with no animation),
//        --no-webgl (Chromium with WebGL disabled: scene slides must show the static SVG composition).
// Usage: node content-heroes.mjs [--reduced-motion] [--no-webgl] [--shots <dir>]
import { mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import { chromium } from 'playwright';
import { arg, serve, launch, openDeck, settle, table } from './lib.mjs';

const reduced = process.argv.includes('--reduced-motion');
const noWebgl = process.argv.includes('--no-webgl');
const shots = arg('shots', '');
const server = await serve();
const browser = noWebgl ? await chromium.launch({ args: ['--disable-webgl', '--disable-webgl2', '--disable-3d-apis'] }) : await launch();
const rows = [];
let failed = false;
const ok = (name, pass, detail = '') => { rows.push([name, pass ? 'PASS' : 'FAIL', detail]); if (!pass) failed = true; };

// Go to the slide before `id`, then step forward onto it, so entry animations run as in the talk.
async function arrive(page, id) {
  await page.evaluate(id => { const s = document.getElementById(id); const { h, v } = window.Reveal.getIndices(s); window.Reveal.slide(h, v, -1); }, id);
  await idle(page);
}
// Enter `id` from the slide before it with a frame counter running; returns frames and seconds until motion ended.
async function enter(page, id) {
  await page.evaluate(id => { const s = document.getElementById(id); const { h, v } = window.Reveal.getIndices(s); window.Reveal.slide(h - 1, 0); }, id);
  await idle(page);
  await page.evaluate(() => {
    const chain = (window.__chain = (window.__chain ?? 0) + 1);
    window.__frames = 0; window.__t0 = performance.now();
    const tick = () => { if (window.__chain !== chain) return; window.__frames++; requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
    window.Reveal.next();
  });
  await idle(page);
  return page.evaluate(() => { window.__chain++; return { frames: window.__frames, seconds: (performance.now() - window.__t0) / 1000 }; });
}
const ENTRY_MAX = 4.6; // seconds as the runner measures them: the GSAP timelines are under 2.2 s, the rest is Reveal's slide transition and SwiftShader frame time

// Stricter than lib.mjs settle(): also waits for GSAP timelines (an auto-play sequence is a timeline), up to 20 s.
async function idle(page) {
  await page.waitForFunction(() => !window.gsap.globalTimeline.getChildren(true, true, true).some(t => t.isActive())
    && !document.getAnimations().some(a => a.playState === 'running'), null, { timeout: 20000, polling: 50 });
  await settle(page);
}

// One click with a frame counter (one rAF chain per click); returns frames rendered and seconds until motion ended.
async function click(page) {
  await page.evaluate(() => {
    const id = (window.__chain = (window.__chain ?? 0) + 1);
    window.__frames = 0; window.__t0 = performance.now();
    const tick = () => { if (window.__chain !== id) return; window.__frames++; requestAnimationFrame(tick); };
    requestAnimationFrame(tick);
    window.Reveal.nextFragment();
  });
  await idle(page);
  return page.evaluate(() => { window.__chain++; return { frames: window.__frames, seconds: (performance.now() - window.__t0) / 1000 }; });
}

const state = {
  s8: page => page.evaluate(() => {
    const s = document.getElementById('zero-of-seven');
    return { flipped: [...s.querySelectorAll('.c-flip-in')].filter(c => Math.round(window.gsap.getProperty(c, 'rotationY')) === 180).length,
      pips: s.querySelectorAll('.c-pip.is-on').length, tally: getComputedStyle(s.querySelector('.c-flagged')).opacity,
      extra: [...s.querySelectorAll('.c-flip-extra')].map(e => getComputedStyle(e).opacity).join(','), badge: s.querySelector('.c-replay-badge').classList.contains('is-on'),
      headline: s.querySelector('.c-flagged').textContent.replace(/\s+/g, ' ').trim() };
  }),
  s9: page => page.evaluate(async () => {
    const s = document.getElementById('hard-six');
    const texts = await Promise.all([...s.querySelectorAll('.c-hard-text')].map(async p => (await window.DeckData.review(p.dataset.review)).feedback === p.textContent));
    const inPlace = [...s.querySelectorAll('.c-hard-text')].every(p => { const m = p.querySelector('.c-mark'); return !m || p.textContent.indexOf(m.textContent) === [...p.childNodes].slice(0, [...p.childNodes].indexOf(m)).map(n => n.textContent).join('').length; });
    return { shown: s.querySelectorAll('.c-hard.is-shown').length, textsExact: texts.every(Boolean), marksInPlace: inPlace };
  }),
  s10: page => page.evaluate(() => {
    const s = document.getElementById('still-wrong');
    const dots = [...s.querySelectorAll('.c-dot')];
    return { gate: s.querySelector('.c-gate-value').textContent, held: dots.filter(d => d.classList.contains('is-held')).length,
      heroKept: !s.querySelector('.c-dot.is-hero').classList.contains('is-held'), heroConf: s.querySelector('.c-dot.is-hero').dataset.conf,
      below: dots.filter(d => Number(d.dataset.conf) < 0.9).length, line: getComputedStyle(s.querySelector('.c-gate-line')).opacity };
  }),
  s12: page => page.evaluate(() => {
    const s = document.getElementById('agree-or-defer');
    const vis = sel => [...s.querySelectorAll(sel)].every(n => getComputedStyle(n).opacity === '1' && getComputedStyle(n).visibility === 'visible');
    return { person: s.querySelectorAll('.c-rv.is-person').length, split: s.querySelectorAll('.c-rv.is-split').length, a: vis('.c-when-a'), b: vis('.c-when-b'), pair: s.querySelector('.c-sorter').dataset.pair };
  }),
};

try {
  const deck = await openDeck(browser, `${server.origin}/presentation.html`, { reducedMotion: reduced ? 'reduce' : 'no-preference' });
  const { page } = deck;
  const mode = reduced ? 'reduced motion' : noWebgl ? 'no WebGL' : 'motion';
  if (shots) await mkdir(shots, { recursive: true });
  // Hero final states are saved as PNG: they double as the outline's static fallbacks for S8, S10 and S12.
  const shoot = async name => { if (shots) await page.screenshot({ path: join(shots, `${name}.png`), type: 'png' }); };

  const scene = await page.evaluate(() => ({ canvas: Boolean(document.querySelector('#deck-scene canvas')), static: document.documentElement.classList.contains('scene-static'),
    svgs: [...document.querySelectorAll('section[data-scene]')].map(s => `${s.id}:${s.querySelector(':scope > .d-scene-static') ? 'svg' : 'none'}`).join(' ') }));
  if (noWebgl || reduced) ok(`${mode}: scene falls back to static SVG on every scene slide`, scene.static && !scene.canvas && !scene.svgs.includes('none'), scene.svgs);
  else ok('motion: WebGL scene canvas present', scene.canvas, scene.svgs);
  for (const id of ['title', 'one-of-60']) { await arrive(page, id); await shoot(`${noWebgl ? 'nowebgl' : reduced ? 'reduced' : 'motion'}-${id}`); }

  let r = await enter(page, 'zero-of-seven'); let st = await state.s8(page);
  ok(`${mode}: S12 entry flips all seven and shows Jev and the general line, ${r.frames} frames in ${r.seconds.toFixed(1)} s`,
    st.flipped === 7 && st.pips === 7 && st.tally === '1' && st.badge && st.extra === '1,1,1' && st.headline === '0 of 7 decision models matched the key.' && r.seconds < ENTRY_MAX, JSON.stringify(st));
  await shoot(`${mode.replace(/ /g, '-')}-s12-entry`);

  r = await enter(page, 'hard-six'); st = await state.s9(page);
  ok(`${mode}: S13 entry shows six cards, ${r.frames} frames in ${r.seconds.toFixed(1)} s`, st.shown === 6 && st.textsExact && st.marksInPlace && r.seconds < ENTRY_MAX, JSON.stringify(st));

  r = await enter(page, 'still-wrong'); st = await state.s10(page);
  ok(`${mode}: S14 entry lands the cutoff at 0.90, ${r.frames} frames in ${r.seconds.toFixed(1)} s`, st.gate === '0.90' && st.held === st.below && st.heroKept && st.line === '1' && r.seconds < ENTRY_MAX, JSON.stringify(st));
  await shoot(`${mode.replace(/ /g, '-')}-s14-entry`);

  r = await enter(page, 'agree-or-defer'); st = await state.s12(page);
  ok(`${mode}: S16 entry is sorted by Solar + Perplexity, ${r.frames} frames in ${r.seconds.toFixed(1)} s`, st.person === 7 && st.split === 7 && st.a && st.pair === 'a' && r.seconds < ENTRY_MAX, JSON.stringify(st));
  r = await click(page); st = await state.s12(page);
  ok(`${mode}: S16 click 1 re-sorts Qwen + Gemma, ${r.frames} frames in ${r.seconds.toFixed(1)} s`, st.person === 2 && st.split === 2 && st.b && st.pair === 'b', JSON.stringify(st));
  await shoot(`${mode.replace(/ /g, '-')}-s16-step1`);

  for (const p of deck.problems) ok(`${mode}: console`, false, p);
  console.log(`\ncontent-heroes.mjs · ${mode}${deck.ignored.readPixels ? ` · ignored ${deck.ignored.readPixels} SwiftShader ReadPixels messages` : ''}\n`);
  console.log(table(['check', 'result', 'state'], rows.map(([a, b, c]) => [a, b, c.length > 150 ? `${c.slice(0, 147)}...` : c])));
  console.log(failed ? '\nRESULT: FAIL' : '\nRESULT: PASS');
  process.exitCode = failed ? 1 : 0;
  await deck.context.close();
} finally {
  await browser.close();
  await server.close();
}
