// Render check for the recomputed-findings section. Run from the repo root:
//   node docs/talk/screenshots/site/deep-insights-render.mjs
// Writes public-site/deep-insights-test.html from the section snippet, serves public-site/ with
// python3 -m http.server, checks the panel in Chromium, screenshots it, then deletes the test page.
import { spawn } from 'node:child_process';
import { readFileSync, writeFileSync, rmSync } from 'node:fs';
import { createRequire } from 'node:module';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), '../../../..');
const SITE = resolve(REPO, 'public-site');
const require = createRequire(import.meta.url);
let chromium;
try { ({ chromium } = require('playwright')); } catch {
  ({ chromium } = require(resolve(SITE, 'deck/verify/node_modules/playwright'))); // ponytail: reuse the deck verifier's install
}
const PAGE = resolve(SITE, 'deep-insights-test.html');
const SHOT = resolve(REPO, 'docs/talk/screenshots/site/deep-insights.jpg');
const PORT = 8000 + Math.floor(Math.random() * 900);
const feeds = {
  'deep-insights-v1.json': JSON.parse(readFileSync(resolve(SITE, 'deep-insights-v1.json'), 'utf8')),
  'native-agreement-policy-v1.json': JSON.parse(readFileSync(resolve(SITE, 'native-agreement-policy-v1.json'), 'utf8')),
};
const get = (data, path) => path.replace(/\]/g, '').split(/[.[]/).reduce((n, k) => n == null ? undefined : n[Array.isArray(n) ? Number(k) : k], data);
const fail = message => { throw Error(message); };

writeFileSync(PAGE, `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Deep insights render check</title><link rel="stylesheet" href="./deep-insights.css"><script defer src="./deep-insights.js"></script>
<style>body{margin:0;background:#1a2332}</style></head><body>${readFileSync(resolve(SITE, 'deep-insights-section.html'), 'utf8')}</body></html>`);
const server = spawn('python3', ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1', '--directory', SITE], { stdio: 'ignore' });
const browser = await chromium.launch();
try {
  await new Promise(done => setTimeout(done, 700));
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const errors = [];
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push(String(e)));
  await page.goto(`http://127.0.0.1:${PORT}/deep-insights-test.html`, { waitUntil: 'networkidle' });
  await page.waitForSelector('#deep-insights .di-card');
  const r = await page.evaluate(() => {
    const q = s => document.querySelectorAll(`#deep-insights ${s}`);
    const routing = [...q('.di-routing tr')].map(tr => [...tr.cells].slice(0, 2).map(c => c.textContent.trim()).join(' | '));
    return {
      mainCards: q('[data-di-mount="cards"] > .di-card').length, moreCards: q('[data-di-mount="more"] .di-card').length,
      options: q('#di-pair option').length, selected: document.querySelector('#di-pair').selectedOptions[0].textContent,
      routing, circles: q('.di-chart circle').length, hardest: q('.di-hardest > li').length, corrections: q('.di-corrections > li').length,
      tables: q('table').length, busy: document.querySelector('[data-di-mount="changed"]').getAttribute('aria-busy'),
      bound: [...q('[data-source]')].map(el => ({ source: el.dataset.source, value: el.getAttribute('value') })),
    };
  });
  let audited = 0;
  for (const { source, value } of r.bound) {
    const [feed, path] = source.split('#');
    const actual = get(feeds[feed], path);
    if (actual === undefined) fail(`unresolved ${source}`);
    if (String(actual ?? '') !== value) fail(`${source}: page ${value} vs feed ${actual}`);
    audited++;
  }
  if (r.mainCards !== 5 || r.moreCards !== 3) fail(`cards ${r.mainCards}/${r.moreCards}`);
  if (r.options < 21 + 10 || !/Solar Decide \+ Perplexity/.test(r.selected)) fail(`explorer ${r.options} ${r.selected}`);
  if (!r.routing.includes('Reaches a person | 35')) fail(`routing ${r.routing.join(' | ')}`);
  if (r.circles < 8 || r.hardest !== 10 || r.corrections !== feeds['deep-insights-v1.json'].corrections.count) fail(`chart/hardest/corrections ${r.circles}/${r.hardest}/${r.corrections}`);
  if (r.busy !== 'false') fail('aria-busy not cleared');
  await page.selectOption('#di-pair', 'general:0');
  const general = await page.textContent('.di-pair caption');
  if (!/Qwen3\.8 27B/.test(general)) fail(`general pair not shown: ${general}`);
  await page.selectOption('#di-pair', { label: r.selected });
  await page.locator('#deep-insights').screenshot({ path: SHOT, type: 'jpeg', quality: 82 });
  await page.setViewportSize({ width: 390, height: 844 });
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  if (overflow > 0) fail(`horizontal overflow at 390px: ${overflow}px`);
  if (errors.length) fail(`console errors: ${errors.join(' | ')}`);
  console.log(JSON.stringify({ ok: true, mainCards: r.mainCards, moreCards: r.moreCards, explorerOptions: r.options, defaultPair: r.selected,
    routing: r.routing, chartCircles: r.circles, hardest: r.hardest, corrections: r.corrections, tables: r.tables,
    boundNumbersAudited: audited, consoleErrors: errors.length, mobileOverflowPx: overflow, screenshot: SHOT }, null, 1));
} finally {
  await browser.close();
  server.kill();
  rmSync(PAGE, { force: true });
}
