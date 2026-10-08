// Opens presentation-offline.html from file:// and reports data-feed problems, unbound numbers and console errors.
// Usage: node offline-check.mjs
import { pathToFileURL } from 'node:url';
import { join } from 'node:path';
import { chromium } from 'playwright';
import { SITE } from './lib.mjs';

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
const errors = [];
page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', e => errors.push(String(e)));
await page.goto(pathToFileURL(join(SITE, 'presentation-offline.html')).href);
await page.waitForFunction(() => window.Reveal?.isReady?.(), null, { timeout: 30000 });
await page.waitForTimeout(2500);
const state = await page.evaluate(() => ({
  status: document.getElementById('deck-data-status')?.textContent ?? '',
  unbound: document.querySelectorAll('.is-unbound').length,
  slides: window.Reveal.getTotalSlides(),
  ticks: document.querySelectorAll('.c-wtick').length,
}));
const fetchFails = errors.filter(e => /Failed to fetch|fetch/i.test(e));
console.log(JSON.stringify({ ...state, consoleErrors: errors.length, fetchErrors: fetchFails.length }, null, 2));
for (const e of errors.slice(0, 10)) console.log('  console:', e.slice(0, 200));
const ok = !state.status && state.unbound === 0 && fetchFails.length === 0 && state.ticks > 0;
console.log(ok ? 'RESULT: PASS' : 'RESULT: FAIL');
process.exitCode = ok ? 0 : 1;
await browser.close();
