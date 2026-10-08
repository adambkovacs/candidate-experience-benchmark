// Review capture: walks every slide and fragment, records the on-screen text at each step,
// and saves one 1920x1080 jpeg per slide (fully revealed) to docs/talk/screenshots/review/NN.jpg.
// Usage: node review-capture.mjs --out ../../../docs/talk/screenshots/review --json /tmp/review-text.json
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { serve, launch, openDeck, settle, listSlides, arg, REPO } from './lib.mjs';

const out = resolve(arg('out', resolve(REPO, 'docs/talk/screenshots/review')));
const jsonOut = arg('json', '/tmp/review-text.json');
await mkdir(out, { recursive: true });

const server = await serve();
const browser = await launch();
const { page, problems } = await openDeck(browser, `${server.origin}/presentation.html`);
const slides = await listSlides(page);

const visibleText = () => page.evaluate(() => {
  const slide = window.Reveal.getCurrentSlide();
  const walker = document.createTreeWalker(slide, NodeFilter.SHOW_TEXT);
  const lines = [];
  let node;
  while ((node = walker.nextNode())) {
    const el = node.parentElement;
    if (!el || el.closest('aside.notes, script, style')) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) continue;
    const frag = el.closest('.fragment');
    if (frag && !frag.classList.contains('visible')) continue;
    // any ancestor with opacity 0 hides it
    let a = el, hidden = false;
    while (a && a !== slide) { const s = getComputedStyle(a); if (parseFloat(s.opacity) === 0 || s.visibility === 'hidden' || s.display === 'none') { hidden = true; break; } a = a.parentElement; }
    if (hidden) continue;
    const t = node.textContent.replace(/\s+/g, ' ').trim();
    if (t) lines.push(t);
  }
  const notes = slide.querySelector('aside.notes')?.innerText?.trim() ?? '';
  return { text: lines.join(' | '), notes };
});

const results = [];
for (let i = 0; i < slides.length; i++) {
  const s = slides[i];
  await page.evaluate(([h, v]) => { window.Reveal.slide(h, v, -1); }, [s.h, s.v]);
  await settle(page);
  const steps = [];
  let step = await visibleText();
  steps.push({ step: 0, text: step.text });
  let n = 0;
  while (await page.evaluate(() => window.Reveal.nextFragment())) {
    await settle(page);
    n++;
    const t = await visibleText();
    steps.push({ step: n, text: t.text });
  }
  await settle(page);
  await page.waitForTimeout(400);
  const nn = String(i + 1).padStart(2, '0');
  const file = resolve(out, `${nn}.jpg`);
  await page.screenshot({ path: file, type: 'jpeg', quality: 60, fullPage: false });
  results.push({ n: i + 1, id: s.id, h: s.h, v: s.v, fragments: s.fragments, steps, notes: step.notes });
  console.log(`${nn} ${s.id} fragments=${s.fragments} steps=${steps.length}`);
}
await writeFile(jsonOut, JSON.stringify(results, null, 2));
console.log('problems:', problems.length ? problems : 'none');
await browser.close();
await server.close();
