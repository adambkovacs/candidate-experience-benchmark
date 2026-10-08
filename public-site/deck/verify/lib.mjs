// Shared by fit.mjs and numbers.mjs: a static server for public-site/ and a deck page that reports its own errors.
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

export const SITE = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
export const REPO = resolve(SITE, '..');
const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.json': 'application/json',
  '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.png': 'image/png', '.jpg': 'image/jpeg' };

export function arg(name, fallback) {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
}

export async function serve() {
  const server = createServer(async (req, res) => {
    const path = normalize(decodeURIComponent(new URL(req.url, 'http://x').pathname)).replace(/^([/\\])+/, '');
    const file = join(SITE, path || 'index.html');
    if (!file.startsWith(SITE)) { res.writeHead(403).end(); return; }
    try {
      const body = await readFile(file);
      res.writeHead(200, { 'content-type': TYPES[extname(file)] ?? 'application/octet-stream', 'cache-control': 'no-store' }).end(body);
    } catch { res.writeHead(404).end('not found'); }
  });
  await new Promise(done => server.listen(0, '127.0.0.1', done));
  return { origin: `http://127.0.0.1:${server.address().port}`, close: () => new Promise(done => server.close(done)) };
}

// ponytail: SwiftShader flags let headless Chromium run the WebGL scene; without them the deck uses its static fallback.
export const launch = () => chromium.launch({ args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader'] });

export async function openDeck(browser, url, { width = 1920, height = 1080, reducedMotion = 'no-preference' } = {}) {
  const context = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1, reducedMotion });
  const page = await context.newPage();
  const problems = [];
  const ignored = { readPixels: 0 };
  page.on('console', msg => {
    if (msg.type() !== 'error' && msg.type() !== 'warning') return;
    // Headless Chromium's software GL (SwiftShader) logs a readback stall for any WebGL canvas it composites or screenshots.
    // It is a GL driver diagnostic, not a deck error. Not verified on a real GPU.
    if (/GL Driver Message .*GPU stall due to ReadPixels/.test(msg.text())) { ignored.readPixels++; return; }
    problems.push(`console.${msg.type()}: ${msg.text()}`);
  });
  page.on('pageerror', error => problems.push(`pageerror: ${error.message}`));
  page.on('requestfailed', req => problems.push(`requestfailed: ${req.url()} ${req.failure()?.errorText}`));
  page.on('response', res => { if (res.status() >= 400) problems.push(`HTTP ${res.status()}: ${res.url()}`); });
  await page.goto(url, { waitUntil: 'load' });
  await page.waitForFunction(() => window.DeckReady, null, { timeout: 30000 });
  await page.evaluate(async () => { await window.DeckReady; await document.fonts.ready; });
  return { page, context, problems, ignored };
}

// Wait until GSAP tweens, CSS transitions and the scene's settle have finished (max 6 s), so checks see final states.
export async function settle(page) {
  await page.waitForFunction(() => {
    const tweening = window.gsap?.globalTimeline.getChildren(true, true, false).some(t => t.isActive());
    // Infinite loops (the live-replay caret blink) never finish, so they do not count as motion still settling.
    const css = document.getAnimations().some(a => a.playState === 'running' && a.effect?.getTiming().iterations !== Infinity);
    return !tweening && !css && window.DeckScene?.settled !== false;
  }, null, { timeout: 6000, polling: 100 }).catch(() => {});
  await page.waitForTimeout(50);
}

// Every leaf slide as {h, v, id, fragments}, in presentation order.
export const listSlides = page => page.evaluate(() => window.Reveal.getSlides().map(slide => {
  const { h, v } = window.Reveal.getIndices(slide);
  return { h, v: v ?? 0, id: slide.id || `slide-${h}-${v ?? 0}`, fragments: slide.querySelectorAll('.fragment').length };
}));

// Go to a slide and step through every fragment, firing the same events a presenter would.
export async function showFully(page, { h, v }) {
  await page.evaluate(([h, v]) => { window.Reveal.slide(h, v, -1); }, [h, v]);
  await settle(page);
  while (await page.evaluate(() => window.Reveal.nextFragment())) await settle(page);
  await settle(page);
}

export function table(headers, rows) {
  const widths = headers.map((h, i) => Math.max(h.length, ...rows.map(r => String(r[i]).length)));
  const line = cells => `| ${cells.map((c, i) => String(c).padEnd(widths[i])).join(' | ')} |`;
  return [line(headers), `|${widths.map(w => '-'.repeat(w + 2)).join('|')}|`, ...rows.map(line)].join('\n');
}
