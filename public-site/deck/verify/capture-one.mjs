// Captures one slide at a given viewport. Usage: node capture-one.mjs <slide-id> <width> <height> <out.png>
import { serve, launch, openDeck, listSlides, showFully } from './lib.mjs';
const [id, w, h, out] = process.argv.slice(2);
const server = await serve();
const browser = await launch();
try {
  const deck = await openDeck(browser, `${server.origin}/presentation.html`, { width: Number(w), height: Number(h) });
  const slide = (await listSlides(deck.page)).find(s => s.id === id);
  await showFully(deck.page, slide);
  await deck.page.screenshot({ path: out });
  console.log('saved', out);
  await deck.context.close();
} finally { await browser.close(); await server.close(); }
