// Fit-to-screen check: every slide, every fragment shown, at four projector viewports.
// Fails on document scroll, content outside its slide, clipped overflow, content under Reveal chrome,
// console errors or warnings, failed requests, and a broken ?print-pdf export.
// Usage: node fit.mjs [--page presentation-v2.html] [--out ../../../docs/talk/screenshots] [--reduced-motion]
import { mkdir } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { REPO, arg, serve, launch, openDeck, listSlides, showFully, settle, table } from './lib.mjs';

const VIEWPORTS = [[1920, 1080], [1366, 768], [1280, 720], [1440, 900]];
const reducedMotion = process.argv.includes('--reduced-motion') ? 'reduce' : 'no-preference';
const pagePath = arg('page', 'presentation-v2.html');
const out = resolve(arg('out', join(REPO, 'docs/talk/screenshots')));
const stem = pagePath.replace(/\.html$/, '').replace(/[/\\]/g, '-');

// Runs in the page: measure the current slide.
function inspect() {
  const slide = window.Reveal.getCurrentSlide();
  const s = slide.getBoundingClientRect(), tol = 1.5;
  const issues = [];
  const doc = document.scrollingElement;
  if (doc.scrollHeight > innerHeight || doc.scrollWidth > innerWidth) issues.push(`document scrolls (${doc.scrollWidth}x${doc.scrollHeight} > ${innerWidth}x${innerHeight})`);
  if (s.left < -tol || s.top < -tol || s.right > innerWidth + tol || s.bottom > innerHeight + tol) issues.push('slide extends past the viewport');
  const name = el => `${el.tagName.toLowerCase()}${el.id ? `#${el.id}` : ''}${el.classList.length ? `.${[...el.classList].join('.')}` : ''}`;
  const visible = el => { const cs = getComputedStyle(el); return cs.display !== 'none' && cs.visibility !== 'hidden' && el.getClientRects().length > 0; };
  const chrome = [...document.querySelectorAll('.reveal .controls, .reveal .slide-number')].filter(visible).map(el => el.getBoundingClientRect());
  const hits = (a, b) => a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top;
  // In-flow content must stay inside the slide's padding box: the bottom padding belongs to the source footer.
  const pad = getComputedStyle(slide), k = s.width / slide.offsetWidth;
  const box = { left: s.left + parseFloat(pad.paddingLeft) * k, top: s.top + parseFloat(pad.paddingTop) * k,
    right: s.right - parseFloat(pad.paddingRight) * k, bottom: s.bottom - parseFloat(pad.paddingBottom) * k };
  const footers = [...slide.querySelectorAll(':scope > .d-source')].filter(visible).map(f => f.getBoundingClientRect());
  const inFlow = el => { for (let n = el; n && n !== slide; n = n.parentElement) if (['absolute', 'fixed'].includes(getComputedStyle(n).position)) return false; return true; };
  for (const el of slide.querySelectorAll('*')) {
    if (!visible(el) || el.closest('.d-scene-static, aside.notes')) continue;
    const r = el.getBoundingClientRect();
    if (r.width === 0 && r.height === 0) continue;
    if (r.left < s.left - tol || r.top < s.top - tol || r.right > s.right + tol || r.bottom > s.bottom + tol) issues.push(`outside slide: ${name(el)}`);
    // .split-w is a mask with a deliberate 0.03em bleed for glyph overhang; the words inside it (.split-i) are still measured.
    else if (inFlow(el) && !el.classList.contains('split-w') && (r.left < box.left - tol || r.top < box.top - tol || r.right > box.right + tol || r.bottom > box.bottom + tol)) issues.push(`outside content box (into slide padding): ${name(el)}`);
    const text = [...el.childNodes].some(n => n.nodeType === Node.TEXT_NODE && n.textContent.trim());
    if (text && !el.closest('.d-source') && footers.some(f => hits(r, f))) issues.push(`text overlaps the source footer: ${name(el)}`);
    const cs = getComputedStyle(el);
    if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible') {
      if (!el.classList.contains('split-w') && (el.scrollWidth > el.clientWidth + 1 || el.scrollHeight > el.clientHeight + 1)) issues.push(`clipped overflow: ${name(el)}`);
    }
    if (text && chrome.some(c => hits(r, c))) issues.push(`under controls or slide number: ${name(el)}`);
  }
  return [...new Set(issues)];
}

const server = await serve();
const browser = await launch();
const results = new Map();
const problems = [];
await mkdir(out, { recursive: true });
let slides = [];
let scene = '';
let readPixels = 0;
try {
  for (const [width, height] of VIEWPORTS) {
    const deck = await openDeck(browser, `${server.origin}/${pagePath}`, { width, height, reducedMotion });
    slides = await listSlides(deck.page);
    for (const [n, slide] of slides.entries()) {
      await showFully(deck.page, slide);
      const issues = await deck.page.evaluate(inspect);
      const file = join(out, `${stem}-${String(n + 1).padStart(2, '0')}-${slide.id}-${width}x${height}.jpg`);
      await deck.page.screenshot({ path: file, type: 'jpeg', quality: 70 });
      results.set(`${slide.id}@${width}x${height}`, issues);
    }
    if (width === 1920) scene = await deck.page.evaluate(() => document.querySelector('#deck-scene canvas') ? 'WebGL canvas' : document.documentElement.classList.contains('scene-static') ? 'static SVG fallback' : 'none');
    problems.push(...deck.problems.map(p => `${width}x${height} ${p}`));
    readPixels += deck.ignored.readPixels;
    await deck.context.close();
  }

  // ?print-pdf: wait for Reveal's print layout, confirm bound numbers rendered, write the PDF.
  const print = await openDeck(browser, `${server.origin}/${pagePath}?print-pdf`, { width: 1920, height: 1080 });
  await print.page.waitForFunction(() => document.querySelectorAll('.pdf-page').length > 0, null, { timeout: 20000 });
  await settle(print.page);
  const pdfState = await print.page.evaluate(() => ({
    pages: document.querySelectorAll('.pdf-page').length,
    unbound: [...document.querySelectorAll('[data-source]')].filter(el => !el.dataset.display || el.textContent.trim() !== el.dataset.display).length,
  }));
  const pdfFile = join(out, `${stem}-print-check.pdf`);
  await print.page.pdf({ path: pdfFile, width: '1920px', height: '1080px', printBackground: true, preferCSSPageSize: true });
  problems.push(...print.problems.map(p => `print ${p}`));
  await print.context.close();
  const expectedPages = slides.reduce((sum, s) => sum + 1 + s.fragments, 0);
  if (pdfState.pages < slides.length) problems.push(`print: ${pdfState.pages} PDF pages for ${slides.length} slides`);
  if (pdfState.unbound) problems.push(`print: ${pdfState.unbound} bound numbers not rendered in the PDF view`);

  const header = ['#', 'slide', ...VIEWPORTS.map(([w, h]) => `${w}x${h}`)];
  const rows = slides.map((s, i) => [i + 1, s.id, ...VIEWPORTS.map(([w, h]) => { const n = results.get(`${s.id}@${w}x${h}`).length; return n ? `FAIL ${n}` : 'PASS'; })]);
  console.log(`\nfit.mjs · ${pagePath} · ${slides.length} slides x ${VIEWPORTS.length} viewports · scene at 1920x1080: ${scene}\n`);
  console.log(table(header, rows));
  console.log(`\nPDF (?print-pdf): ${pdfState.pages} pages (expected up to ${expectedPages} with fragment steps), unbound numbers: ${pdfState.unbound} -> ${pdfFile}`);
  console.log(`Screenshots: ${out}`);
  if (readPixels) console.log(`Ignored ${readPixels} headless SwiftShader 'GPU stall due to ReadPixels' messages (GL driver diagnostics, not deck errors).`);
  for (const [key, issues] of results) for (const issue of issues) console.log(`  FAIL ${key}: ${issue}`);
  for (const p of problems) console.log(`  FAIL ${p}`);
  const failed = [...results.values()].some(i => i.length) || problems.length;
  console.log(failed ? '\nRESULT: FAIL' : '\nRESULT: PASS');
  process.exitCode = failed ? 1 : 0;
} finally {
  await browser.close();
  await server.close();
}
