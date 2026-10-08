// Names the in-flow elements that sit outside a slide's content box at 1920x1080 (the check fit.mjs applies).
// Usage: node overflow-probe.mjs <slide-id> [<slide-id> ...]
import { serve, launch, openDeck, showFully, listSlides } from './lib.mjs';

const ids = process.argv.slice(2);
const server = await serve();
const browser = await launch();
try {
  const deck = await openDeck(browser, `${server.origin}/presentation.html`);
  const slides = await listSlides(deck.page);
  for (const id of ids) {
    const s = slides.find(x => x.id === id);
    await showFully(deck.page, s);
    const out = await deck.page.evaluate(id => {
      const slide = document.getElementById(id), r0 = slide.getBoundingClientRect(), pad = getComputedStyle(slide), k = r0.width / slide.offsetWidth;
      const box = { left: r0.left + parseFloat(pad.paddingLeft) * k, top: r0.top + parseFloat(pad.paddingTop) * k, right: r0.right - parseFloat(pad.paddingRight) * k, bottom: r0.bottom - parseFloat(pad.paddingBottom) * k };
      const visible = el => { const cs = getComputedStyle(el); return cs.display !== 'none' && cs.visibility !== 'hidden' && Number(cs.opacity) > 0; };
      const inFlow = el => { for (let n = el; n && n !== slide; n = n.parentElement) if (['absolute', 'fixed'].includes(getComputedStyle(n).position)) return false; return true; };
      const hits = [];
      for (const el of slide.querySelectorAll('*')) {
        if (!visible(el) || el.closest('.d-scene-static, aside.notes')) continue;
        const r = el.getBoundingClientRect();
        if ((r.width === 0 && r.height === 0) || !inFlow(el) || el.classList.contains('split-w')) continue;
        if (r.left < box.left - 1 || r.top < box.top - 1 || r.right > box.right + 1 || r.bottom > box.bottom + 1) hits.push(`${el.tagName.toLowerCase()}.${[...el.classList].join('.')} "${el.textContent.trim().slice(0, 40)}" rect ${[r.left, r.top, r.right, r.bottom].map(Math.round).join(',')} box ${Object.values(box).map(Math.round).join(',')}`);
      }
      return hits;
    }, id);
    console.log(id, out.length ? out : 'clean');
  }
  await deck.context.close();
} finally { await browser.close(); await server.close(); }
