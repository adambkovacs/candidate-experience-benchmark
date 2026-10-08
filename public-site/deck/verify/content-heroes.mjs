// Click-through of the hero sequences (S8 flips, S9 card wall, S10 gate, S12 sort) as a presenter would drive them.
// For each click: counts animation frames until motion settles, then asserts the final state from the DOM.
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
      below: dots.filter(d => Number(d.dataset.conf) < 0.95).length, line: getComputedStyle(s.querySelector('.c-gate-line')).opacity };
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

  await arrive(page, 'zero-of-seven');
  let r = await click(page); let st = await state.s8(page);
  ok(`${mode}: S8 click 1 flips all seven, ${r.frames} frames in ${r.seconds.toFixed(1)} s`, st.flipped === 7 && st.pips === 7 && st.tally === '1' && st.badge && st.extra === '0,0', JSON.stringify(st));
  await shoot(`${mode.replace(/ /g, '-')}-s8-step1`);
  r = await click(page); st = await state.s8(page);
  ok(`${mode}: S8 click 2 shows Jev and the general line, ${r.frames} frames`, st.extra === '1,1' && st.headline === '0 of 7 decision models.', JSON.stringify(st));

  await arrive(page, 'hard-six');
  let frames = 0, secs = 0;
  for (let i = 0; i < 6; i++) { r = await click(page); frames += r.frames; secs = Math.max(secs, r.seconds); }
  st = await state.s9(page);
  ok(`${mode}: S9 six clicks show six cards, longest click ${secs.toFixed(1)} s, ${frames} frames`, st.shown === 6 && st.textsExact && st.marksInPlace && secs < 3.6, JSON.stringify(st));

  await arrive(page, 'still-wrong');
  r = await click(page); st = await state.s10(page);
  ok(`${mode}: S10 gate sweeps to 0.95, ${r.frames} frames in ${r.seconds.toFixed(1)} s`, st.gate === '0.95' && st.held === st.below && st.heroKept && st.line === '1', JSON.stringify(st));
  await shoot(`${mode.replace(/ /g, '-')}-s10-step1`);

  await arrive(page, 'agree-or-defer');
  r = await click(page); st = await state.s12(page);
  ok(`${mode}: S12 click 1 sorts Solar + Perplexity, ${r.frames} frames in ${r.seconds.toFixed(1)} s`, st.person === 7 && st.split === 7 && st.a && st.pair === 'a', JSON.stringify(st));
  r = await click(page); st = await state.s12(page);
  ok(`${mode}: S12 click 2 re-sorts Qwen + Gemma, ${r.frames} frames in ${r.seconds.toFixed(1)} s`, st.person === 2 && st.split === 2 && st.b && st.pair === 'b', JSON.stringify(st));
  await shoot(`${mode.replace(/ /g, '-')}-s12-step2`);

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
