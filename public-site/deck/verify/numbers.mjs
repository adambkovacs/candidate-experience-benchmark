// Source-binding check: every element with data-source="<feed>.json#<path>" must show exactly the feed's value.
// Expected values are resolved here in Node from the JSON files on disk, independently of deck/data.js.
// Also checks review text bound with data-review and every cell of replays built from disputed-reviews-v1.json.
// Runs twice: live (each slide visited, fragments stepped, count-ups finished) and ?print-pdf (what the PDF shows).
// Usage: node numbers.mjs [--page presentation-v2.html]
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { SITE, arg, serve, launch, openDeck, listSlides, showFully, settle, table } from './lib.mjs';

const pagePath = arg('page', 'presentation-v2.html');
const NUMBER_TEXT = /^-?(\d{1,3}(,\d{3})+|\d+)(\.\d+)?$/; // "54", "140,260", "0.03749436"; never "5,4"
const feeds = new Map();
const feed = async name => {
  if (!/^(?:[\w-]+\/)*[\w.-]+\.json$/.test(name)) throw new Error(`invalid feed name ${name}`);
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

const say = value => value === undefined || value === null ? 'No answer'
  : value === 'insufficient_information' ? 'Insufficient info' : String(value).replace(/_/g, ' ');
const short = text => (text.length > 44 ? `${text.slice(0, 41)}...` : text);

async function checkNumber(item) {
  const [name, path] = item.source.split('#');
  const value = resolvePath(await feed(name), path ?? '');
  const number = Number(value);
  if (value === undefined || value === null || typeof value === 'boolean' || value === '' || !Number.isFinite(number)) return [String(JSON.stringify(value)), false];
  const want = item.round === undefined ? number : Number(number.toFixed(Number(item.round)));
  return [String(value), NUMBER_TEXT.test(item.text) && Number(item.text.replace(/,/g, '')) === want];
}

async function checkText(item) {
  const [name, path] = item.source.split('#');
  const value = resolvePath(await feed(name), path ?? '');
  if (typeof value !== 'string' && typeof value !== 'number') return [String(JSON.stringify(value)), false];
  return [String(value), item.text === (item.raw ? String(value) : say(value))];
}

// The figure the background points form (data-scene-number) must equal its feed value.
async function checkScene(item) {
  const [name, path] = item.source.split('#');
  const value = resolvePath(await feed(name), path ?? '');
  return [String(value), Number.isFinite(Number(value)) && Number(item.text) === Number(value)];
}

async function checkReview(item) {
  const found = resolvePath(await feed('disputed-reviews-v1.json'), `reviews[id=${item.review}]`);
  return [short(found?.feedback ?? 'missing'), Boolean(found) && item.text === found.feedback.trim()];
}

async function checkReplay(item) {
  const data = await feed(item.feed);
  if (data.schema !== 'disputed-reviews-v1') return ['not checked: only disputed-reviews-v1 replays are verified', null];
  const found = resolvePath(data, `reviews[id=${item.review}]`);
  if (!found) return ['review missing', false];
  const fields = item.fields.split(',');
  const names = new Map(data.models.map(m => [m.id, m.display_name]));
  const want = [['Reference', ...fields.map(f => say(found.reference[f]))],
    ...found.answers.map(a => [names.get(a.model_id) ?? a.model_id, ...fields.map(f => say(a.prediction?.[f]))])];
  return [`${want.length} rows x ${fields.length + 1} cells`, JSON.stringify(want) === JSON.stringify(item.rows)];
}

// Runs in the page: everything source-bound inside one root (a slide, or the whole print document).
function collect(index) {
  const root = index === null ? document : window.Reveal.getSlides()[index];
  const label = el => {
    const s = el.closest('section:not(.stack)');
    if (!s) return '(outside any slide)';
    if (s.id) return s.id;
    const { h, v } = window.Reveal.getIndices(s);
    return `slide-${h}-${v ?? 0}`;
  };
  return [
    ...[...root.querySelectorAll('[data-source]')].map(el => ({ kind: 'number', slide: label(el), source: el.dataset.source, round: el.dataset.round, text: el.textContent.trim() })),
    ...[...root.querySelectorAll('[data-text-source]')].map(el => ({ kind: 'text', slide: label(el), source: el.dataset.textSource, raw: el.hasAttribute('data-raw'), text: el.textContent.trim() })),
    // The scene attributes sit on the slide itself, which querySelectorAll on that slide would skip.
    ...[root, ...root.querySelectorAll('[data-scene-number-source]')].filter(el => el.matches?.('[data-scene-number-source]'))
      .map(el => ({ kind: 'scene', slide: label(el), source: el.dataset.sceneNumberSource, text: el.dataset.sceneNumber })),
    ...[...root.querySelectorAll('[data-review]:not(.d-replay):not(.d-live)')].map(el => ({ kind: 'review', slide: label(el),
      source: `disputed-reviews-v1.json#reviews[id=${el.dataset.review}].feedback`, review: el.dataset.review, text: el.textContent.trim() })),
    ...[...root.querySelectorAll('.d-replay')].map(el => ({ kind: 'replay', slide: label(el), source: `${el.dataset.replay}#reviews[id=${el.dataset.review}] replay`,
      feed: el.dataset.replay, review: el.dataset.review, fields: el.dataset.fields || 'sentiment,follow_up_needed,serious_concern_reported,testimonial_potential',
      rows: [...el.querySelectorAll('tbody tr')].map(tr => [...tr.cells].map(c => c.textContent.trim())), text: `${el.querySelectorAll('tbody tr').length} rows` })),
  ];
}

const server = await serve();
const browser = await launch();
const rows = [];
const problems = [];
try {
  const live = await openDeck(browser, `${server.origin}/${pagePath}`);
  const seen = [];
  for (const [index, slide] of (await listSlides(live.page)).entries()) {
    await showFully(live.page, slide);
    seen.push(...await live.page.evaluate(collect, index));
  }
  problems.push(...live.problems.map(p => `live ${p}`));
  await live.context.close();

  const print = await openDeck(browser, `${server.origin}/${pagePath}?print-pdf`);
  await print.page.waitForFunction(() => document.querySelectorAll('.pdf-page').length > 0, null, { timeout: 20000 });
  await settle(print.page);
  const printed = await print.page.evaluate(collect, null);
  problems.push(...print.problems.map(p => `print ${p}`));
  await print.context.close();

  const check = { number: checkNumber, text: checkText, scene: checkScene, review: checkReview, replay: checkReplay };
  for (const [mode, items] of [['live', seen], ['print', printed]]) {
    for (const item of items) {
      const [expected, ok] = await check[item.kind](item);
      rows.push([mode, item.slide, item.source, short(item.text), expected, ok === null ? 'UNCHECKED' : ok ? 'PASS' : 'FAIL']);
    }
  }
  if (!seen.some(item => item.kind === 'number')) problems.push('no data-source elements found on any slide');

  const count = (items, kind) => items.filter(item => item.kind === kind).length;
  const summary = items => ['number', 'text', 'scene', 'review', 'replay'].map(kind => `${count(items, kind)} ${kind}`).join(', ');
  console.log(`\nnumbers.mjs · ${pagePath} · live: ${summary(seen)} · print: ${summary(printed)}\n`);
  console.log(table(['mode', 'slide', 'source', 'shown', 'feed value', 'result'], rows));
  for (const p of problems) console.log(`  FAIL ${p}`);
  const failed = rows.some(r => r[5] === 'FAIL') || problems.length;
  console.log(failed ? '\nRESULT: FAIL' : '\nRESULT: PASS');
  process.exitCode = failed ? 1 : 0;
} finally {
  await browser.close();
  await server.close();
}
