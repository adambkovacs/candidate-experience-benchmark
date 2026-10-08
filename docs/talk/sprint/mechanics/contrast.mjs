// WCAG contrast pass over rendered slide text (computed colours, effective backgrounds, ancestor opacity).
// Usage (from public-site/deck/verify so playwright resolves): node ../../../docs/talk/sprint/mechanics/contrast.mjs [--page presentation.html] [--print]
import { arg, serve, launch, openDeck, listSlides, showFully } from '/Users/adamkovacs/lanes/cxb-talk/public-site/deck/verify/lib.mjs';

const pagePath = arg('page', 'presentation.html');
const print = process.argv.includes('--print');

function measure() {
  const parse = s => {
    let m = s.match(/rgba?\(([^)]+)\)/);
    if (m) { const p = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p[3] ?? 1]; }
    m = s.match(/color\(srgb ([^)]+)\)/);
    if (m) { const p = m[1].split(/[ \/]+/).filter(Boolean).map(Number); return [p[0] * 255, p[1] * 255, p[2] * 255, p[3] ?? 1]; }
    return null;
  };
  const over = (f, b) => { const a = f[3]; return [f[0] * a + b[0] * (1 - a), f[1] * a + b[1] * (1 - a), f[2] * a + b[2] * (1 - a), 1]; };
  const lum = c => { const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; }; return .2126 * f(c[0]) + .7152 * f(c[1]) + .0722 * f(c[2]); };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
  const root = parse(getComputedStyle(document.body).backgroundColor);
  const base = root && root[3] === 1 ? root : [26, 35, 50, 1]; // --ink
  const visible = el => { const cs = getComputedStyle(el); return cs.display !== 'none' && cs.visibility !== 'hidden' && el.getClientRects().length > 0; };
  const sel = el => `${el.tagName.toLowerCase()}${[...el.classList].filter(c => !/^(visible|present|past|future|fragment|is-visible)$/.test(c)).map(c => '.' + c).join('')}`;
  const out = [];
  const slide = window.Reveal.getCurrentSlide();
  for (const el of slide.querySelectorAll('*')) {
    if (el.closest('aside.notes, .d-scene-static')) continue;
    if (!visible(el)) continue;
    const text = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('').replace(/\s+/g, ' ').trim();
    if (!text) continue;
    const r = el.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    const cs = getComputedStyle(el);
    let fg = parse(cs.color);
    if (el.closest('svg') && parse(cs.fill)) fg = parse(cs.fill);
    if (!fg) continue;
    let op = 1, imageBg = false;
    for (let n = el; n && n !== document.documentElement; n = n.parentElement) op *= parseFloat(getComputedStyle(n).opacity);
    const layers = [];
    for (let n = el; n; n = n.parentElement) {
      const c = getComputedStyle(n);
      if (c.backgroundImage !== 'none' && n !== document.documentElement) imageBg = true;
      const bg = parse(c.backgroundColor);
      if (bg && bg[3] > 0) { layers.push(bg); if (bg[3] === 1) break; }
    }
    let bg = layers.length && layers[layers.length - 1][3] === 1 ? layers.pop() : base;
    while (layers.length) bg = over(layers.pop(), bg);
    const eff = fg[3] * op;
    const text2 = over([fg[0], fg[1], fg[2], eff], bg);
    out.push({ sel: sel(el), fg: text2.slice(0, 3).map(Math.round), bg: bg.slice(0, 3).map(Math.round), ratio: +ratio(text2, bg).toFixed(2), px: parseFloat(cs.fontSize), weight: +cs.fontWeight, opacity: +op.toFixed(2), imageBg, text: text.slice(0, 50) });
  }
  return out;
}

const hex = c => '#' + c.map(v => v.toString(16).padStart(2, '0')).join('');
const server = await serve();
const browser = await launch();
const groups = new Map();
let total = 0, imageBgCount = 0;
try {
  const { page, context } = await openDeck(browser, `${server.origin}/${pagePath}`, { width: 1920, height: 1080 });
  if (print) await page.emulateMedia({ media: 'print' });
  for (const slide of await listSlides(page)) {
    await showFully(page, slide);
    for (const m of await page.evaluate(measure)) {
      total++; if (m.imageBg) imageBgCount++;
      const large = m.px >= 24 || (m.px >= 18.66 && m.weight >= 700);
      const key = `${m.sel}|${hex(m.fg)}|${hex(m.bg)}`;
      const g = groups.get(key) ?? { ...m, large, slides: new Set(), n: 0 };
      g.slides.add(slide.id); g.n++; groups.set(key, g);
    }
  }
  await context.close();
} finally { await browser.close(); await server.close(); }

const all = [...groups.values()].sort((a, b) => a.ratio - b.ratio);
const bad = all.filter(g => g.ratio < 4.5);
console.log(`contrast.mjs · ${pagePath}${print ? ' (print media)' : ''} · ${total} text nodes · ${all.length} distinct selector/fg/bg pairs · ${bad.length} under 4.5:1 · ${bad.filter(g => g.ratio < 3).length} under 3:1 · ${imageBgCount} nodes sit under a background-image/gradient (bg approximated)`);
console.log('| ratio | selector | fg | bg | px/wt | opacity | slides | sample |');
console.log('|---|---|---|---|---|---|---|---|');
for (const g of bad) console.log(`| ${g.ratio} | ${g.sel} | ${hex(g.fg)} | ${hex(g.bg)} | ${g.px}/${g.weight}${g.large ? ' large' : ''} | ${g.opacity} | ${[...g.slides].slice(0, 6).join(', ')}${g.slides.size > 6 ? ` +${g.slides.size - 6}` : ''} | ${g.text.replace(/\|/g, '/')} |`);
console.log('\nLowest 5 passing pairs:');
for (const g of all.filter(g => g.ratio >= 4.5).slice(0, 5)) console.log(`  ${g.ratio} ${g.sel} ${hex(g.fg)} on ${hex(g.bg)}`);
