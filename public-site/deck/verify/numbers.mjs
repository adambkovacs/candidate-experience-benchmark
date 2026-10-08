// Source-binding check: every element with data-source="<feed>.json#<path>" must show exactly the feed's value.
// Expected values are resolved here in Node from the JSON files on disk, independently of deck/data.js.
// Runs twice: live (each slide visited, fragments stepped, count-ups finished) and ?print-pdf (what the PDF shows).
// Usage: node numbers.mjs [--page presentation-v2.html]
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { SITE, arg, serve, launch, openDeck, listSlides, showFully, settle, table } from './lib.mjs';

const pagePath = arg('page', 'presentation-v2.html');
const feeds = new Map();
const feed = async name => {
  if (!/^[\w.-]+\.json$/.test(name)) throw new Error(`invalid feed name ${name}`);
  if (!feeds.has(name)) feeds.set(name, JSON.parse(await readFile(join(SITE, name), 'utf8')));
  return feeds.get(name);
};

// Same grammar as the deck, written separately: a.b[3].c["0.9"].d[key=value,key2=value2].
function resolvePath(root, path) {
  let node = root;
  for (const token of path.match(/\[[^\]]*\]|[^.[\]]+/g) ?? []) {
    if (node === null || node === undefined) return undefined;
    if (!token.startsWith('[')) { node = node[token]; continue; }
    const inner = token.slice(1, -1);
    if (/^\d+$/.test(inner)) { node = node[Number(inner)]; continue; }
    if (/^(["']).*\1$/.test(inner)) { node = node[inner.slice(1, -1)]; continue; }
    const want = Object.fromEntries(inner.split(',').map(pair => pair.split('=')));
    node = Array.isArray(node) ? node.find(item => Object.entries(want).every(([k, v]) => String(item?.[k]) === v)) : undefined;
  }
  return node;
}

async function expected(source, round) {
  const [name, path] = source.split('#');
  const value = resolvePath(await feed(name), path ?? '');
  const number = Number(value);
  if (value === undefined || value === null || typeof value === 'boolean' || value === '' || !Number.isFinite(number)) return { error: `feed value is ${JSON.stringify(value)}` };
  return { number: round === undefined ? number : Number(number.toFixed(Number(round))), raw: value };
}

const collect = page => page.evaluate(() => [...document.querySelectorAll('[data-source]')].map(el => ({
  source: el.dataset.source, round: el.dataset.round, text: el.textContent.trim(),
  slide: el.closest('section:not(.stack)')?.id || '(outside any slide)',
})));

const server = await serve();
const browser = await launch();
const rows = [];
const problems = [];
try {
  const live = await openDeck(browser, `${server.origin}/${pagePath}`);
  const seen = [];
  for (const slide of await listSlides(live.page)) {
    await showFully(live.page, slide);
    const here = await live.page.evaluate(id => [...document.getElementById(id).querySelectorAll('[data-source]')].length, slide.id);
    if (here) seen.push(...(await collect(live.page)).filter(item => item.slide === slide.id));
  }
  problems.push(...live.problems.map(p => `live ${p}`));
  await live.context.close();

  const print = await openDeck(browser, `${server.origin}/${pagePath}?print-pdf`);
  await print.page.waitForFunction(() => document.querySelectorAll('.pdf-page').length > 0, null, { timeout: 20000 });
  await settle(print.page);
  const printed = await collect(print.page);
  problems.push(...print.problems.map(p => `print ${p}`));
  await print.context.close();

  for (const [mode, items] of [['live', seen], ['print', printed]]) {
    for (const item of items) {
      const want = await expected(item.source, item.round);
      const shown = Number(item.text.replace(/[,  \s]/g, ''));
      const ok = !want.error && item.text !== '' && Number.isFinite(shown) && shown === want.number;
      rows.push([mode, item.slide, item.source, item.text, want.error ?? String(want.raw), ok ? 'PASS' : 'FAIL']);
    }
  }
  if (!seen.length) problems.push('no data-source elements found on any slide');

  console.log(`\nnumbers.mjs · ${pagePath} · ${seen.length} bound numbers live, ${printed.length} in print view\n`);
  console.log(table(['mode', 'slide', 'data-source', 'shown', 'feed value', 'result'], rows));
  for (const p of problems) console.log(`  FAIL ${p}`);
  const failed = rows.some(r => r[5] === 'FAIL') || problems.length;
  console.log(failed ? '\nRESULT: FAIL' : '\nRESULT: PASS');
  process.exitCode = failed ? 1 : 0;
} finally {
  await browser.close();
  await server.close();
}
