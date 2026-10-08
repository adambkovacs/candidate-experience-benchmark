// Debug loader: prints every console message and page error while presentation.html boots.
import { arg, serve, launch } from './lib.mjs';

const pagePath = arg('page', 'presentation.html');
const server = await serve();
const browser = await launch();
try {
  const page = await (await browser.newContext({ viewport: { width: 1920, height: 1080 } })).newPage();
  page.on('console', m => console.log(`console.${m.type()}: ${m.text()}`));
  page.on('pageerror', e => console.log(`pageerror: ${e.message}\n${e.stack}`));
  page.on('requestfailed', r => console.log(`requestfailed: ${r.url()}`));
  await page.goto(`${server.origin}/${pagePath}${arg('query', '')}`, { waitUntil: 'load' });
  await page.waitForTimeout(Number(arg('wait', '6000')));
  if (arg('eval', '')) console.log(await page.evaluate(arg('eval', '')));
  console.log(await page.evaluate(() => JSON.stringify({ ready: Boolean(window.DeckReady), data: document.documentElement.dataset.deckData,
    alert: document.getElementById('deck-data-status')?.textContent, built: document.querySelectorAll('[data-c-built]').length, comps: document.querySelectorAll('[data-c]').length })));
} finally {
  await browser.close();
  await server.close();
}
