// Delivery aids for presentation.html: clicker keys, hash URLs (with a fragment step), the S15 appendix index links,
// and the speaker view (S) showing notes and a timer.
// Usage: node content-delivery.mjs
import { serve, launch, openDeck, settle, table } from './lib.mjs';

const server = await serve();
const browser = await launch();
const rows = [];
const ok = (name, pass, detail = '') => rows.push([name, pass ? 'PASS' : 'FAIL', detail]);
const where = page => page.evaluate(() => `${window.Reveal.getCurrentSlide().id}/${window.Reveal.getIndices().f ?? -1}`);
try {
  const deck = await openDeck(browser, `${server.origin}/presentation.html`);
  const { page } = deck;
  await page.locator('.reveal').click({ position: { x: 900, y: 500 } }).catch(() => {});

  // Clicker keys: remotes send PageDown / PageUp; keyboards use Space and the arrows.
  for (const [key, want] of [['PageDown', 'about/-1'], ['PageDown', 'decision-models/-1'], ['PageUp', 'about/-1'], ['Space', 'decision-models/-1'], ['ArrowRight', 'launch-wave/-1'], ['ArrowLeft', 'decision-models/-1']]) {
    await page.keyboard.press(key); await settle(page);
    const at = await where(page);
    ok(`key ${key} -> ${want}`, at === want, at);
  }
  // End jumps to the last slide: the thank-you slide closes the deck after the appendix stack.
  await page.keyboard.press('End'); await settle(page);
  const last = await page.evaluate(() => `${window.Reveal.getCurrentSlide().id} ${window.Reveal.getSlidePastCount() + 1}/${window.Reveal.getTotalSlides()}`);
  ok('key End -> thanks, slide 31 of 31', last === 'thanks 31/31', last);

  // Hash jumps: an appendix slide, and the sorter at its one click (Qwen + Gemma, restored after the data loads).
  for (const [hash, want] of [['#/a10-pairs', 'a10-pairs/-1'], ['#/agree-or-defer/1', 'agree-or-defer/0']]) {
    const p2 = await openDeck(browser, `${server.origin}/presentation.html${hash}`);
    await settle(p2.page);
    const at = await where(p2.page);
    const extra = hash.includes('agree') ? await p2.page.evaluate(() => document.querySelectorAll('#agree-or-defer .c-rv.is-person').length) : '';
    ok(`hash ${hash}`, at === want && (extra === '' || extra === 2), `${at}${extra === '' ? '' : ` person cards ${extra}`}`);
    await p2.context.close();
  }

  // S15 appendix index: every link resolves to a slide, and clicking one jumps there.
  await page.evaluate(() => { const s = document.getElementById('monday'); const { h, v } = window.Reveal.getIndices(s); window.Reveal.slide(h, v); });
  await settle(page);
  const links = await page.evaluate(() => [...document.querySelectorAll('#monday .c-index a')].map(a => a.getAttribute('href').slice(2)).filter(id => !document.getElementById(id)));
  ok('S20 index: all 10 links resolve to slides', links.length === 0 && (await page.locator('#monday .c-index a').count()) === 10, links.join(', ') || '10 of 10');
  await page.locator('#monday .c-index a[href="#/a13-dev-030"]').click();
  await settle(page);
  ok('S15 index: clicking A13 jumps to it', (await where(page)).startsWith('a13-dev-030'), await where(page));

  // Speaker view: S opens the notes window with the current slide's notes and a timer.
  await page.evaluate(() => { const s = document.getElementById('agree-or-defer'); const { h, v } = window.Reveal.getIndices(s); window.Reveal.slide(h, v); });
  await settle(page);
  const [popup] = await Promise.all([page.context().waitForEvent('page', { timeout: 10000 }), page.keyboard.press('s')]);
  await popup.waitForLoadState('load');
  await popup.waitForFunction(() => /The rule is agree or defer/.test(document.querySelector('.speaker-controls-notes')?.textContent ?? ''), null, { timeout: 15000 }).catch(() => {});
  const view = await popup.evaluate(() => {
    const text = (document.querySelector('.speaker-controls-notes')?.textContent ?? '').replace(/\s+/g, ' ').trim();
    return { spoken: /The rule is agree or defer\. Two cheap models/.test(text), clicks: /\[Clicks: 1\./.test(text), timer: (document.querySelector('.speaker-controls-time')?.textContent ?? '').trim().slice(0, 40) };
  });
  ok('speaker view: notes for S16 with click count, and a timer', view.spoken && view.clicks && Boolean(view.timer), JSON.stringify(view));
  await popup.close();

  for (const p of deck.problems) ok('console', false, p);
  console.log('\ncontent-delivery.mjs\n');
  console.log(table(['check', 'result', 'detail'], rows));
  const failed = rows.some(r => r[1] === 'FAIL');
  console.log(failed ? '\nRESULT: FAIL' : '\nRESULT: PASS');
  process.exitCode = failed ? 1 : 0;
  await deck.context.close();
} finally {
  await browser.close();
  await server.close();
}
