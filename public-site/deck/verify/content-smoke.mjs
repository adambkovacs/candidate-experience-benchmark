// Quick health check for presentation.html: loads once, lists console problems, data alerts and per-slide fragment counts.
// Usage: node content-smoke.mjs [--page presentation.html] [--shots <dir>]   (--shots saves each slide fully stepped at 1920x1080, jpeg q70)
import { mkdir } from 'node:fs/promises';
import { join } from 'node:path';
import { arg, serve, launch, openDeck, listSlides, showFully } from './lib.mjs';

const pagePath = arg('page', 'presentation.html');
const shots = arg('shots', '');
const server = await serve();
const browser = await launch();
try {
  const deck = await openDeck(browser, `${server.origin}/${pagePath}`);
  const slides = await listSlides(deck.page);
  const status = await deck.page.evaluate(() => ({ data: document.documentElement.dataset.deckData, alert: document.getElementById('deck-data-status')?.textContent ?? '' }));
  console.log(`slides: ${slides.length} · data: ${status.data} ${status.alert}`);
  if (shots) await mkdir(shots, { recursive: true });
  for (const [i, s] of slides.entries()) {
    if (shots) {
      await showFully(deck.page, s);
      // showFully's settle() watches tweens only; wait for auto-play timelines (S8 runs about 13 s) to finish too.
      await deck.page.waitForFunction(() => !window.gsap.globalTimeline.getChildren(true, true, true).some(t => t.isActive()), null, { timeout: 20000, polling: 100 });
      await deck.page.screenshot({ path: join(shots, `${String(i + 1).padStart(2, '0')}-${s.id}.jpg`), type: 'jpeg', quality: 70 });
    }
    console.log(`${String(i + 1).padStart(2)} ${s.id} fragments=${s.fragments}`);
  }
  for (const p of deck.problems) console.log(`PROBLEM ${p}`);
  await deck.context.close();
} finally {
  await browser.close();
  await server.close();
}
