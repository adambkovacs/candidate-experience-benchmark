// Content audit for presentation.html, complementing numbers.mjs (which checks data-source, data-review and replays).
// 1. Every other binding the content layer uses, live (each slide fully stepped) and in ?print-pdf:
//    data-deck-source (deck-local values, dates), data-count, data-answer (model labels), data-status-source,
//    data-doc ("docs/x.md|snippet": the snippet must be in the doc and contain the shown text).
// 2. Unbound digits: any digit on a slide outside a bound element and outside the label allowlist below fails.
// 3. Notes: the main deck's speaker notes, per beat, must equal docs/talk/05-session-outline.md section 2b verbatim.
// 4. Copy: words in [data-copy] per main slide (the outline's max-12 rule), reported; slides over 12 fail unless listed.
// 5. Source links: every link out of the deck targets a report page from site/LINK-MAP.md (index, explore, method)
//    and an id that exists on that page; links straight to a .json feed fail.
// Usage: node content-audit.mjs [--page presentation.html]
import { readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { SITE, REPO, arg, serve, launch, openDeck, listSlides, showFully, settle, table } from './lib.mjs';

const pagePath = arg('page', 'presentation.html');
const MAIN = 15;
const BEATS = [1, 1, 2, 3, 4, 4, 5, 5, 5, 6, 6, 7, 7, 8, 8]; // slide -> beat in outline section 2b
const COPY_EXCEPTIONS = { queue: 'outline S13 specifies five policy lines plus the closing question' };
const files = new Map();
const load = async path => {
  if (!files.has(path)) files.set(path, path.endsWith('.json') ? JSON.parse(await readFile(join(SITE, path), 'utf8')) : await readFile(join(REPO, path), 'utf8'));
  return files.get(path);
};
function resolvePath(root, path) {
  let node = root;
  for (const token of path.match(/\[[^\]]*\]|[^.[\]]+/g) ?? []) {
    if (node === null || node === undefined) return undefined;
    if (!token.startsWith('[')) { node = node[token]; continue; }
    const inner = token.slice(1, -1);
    if (/^\d+$/.test(inner)) { node = node[Number(inner)]; continue; }
    if (/^(["']).*\1$/.test(inner)) { node = node[inner.slice(1, -1)]; continue; }
    const want = inner.split(',').map(pair => pair.split('='));
    node = Array.isArray(node) ? node.find(item => want.every(([k, v]) => String(item?.[k]) === v)) : undefined;
  }
  return node;
}
const value = async spec => { const [p, path] = spec.split('#'); return resolvePath(await load(p), path); };
const say = v => (v === undefined || v === null ? 'no answer' : v === 'insufficient_information' ? "can't tell" : String(v).replace(/_/g, ' '));
const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const norm = s => s.replace(/\s+/g, ' ').trim();

async function check(item) {
  try {
    if (item.kind === 'deck') {
      const v = await value(item.spec);
      if (item.format === 'date' || item.format === 'date-short') {
        const [, y, m, d] = /^(\d{4})-(\d{2})-(\d{2})$/.exec(v) || [];
        const month = MONTHS[Number(m) - 1] ?? '?';
        return [v, item.text === `${Number(d)} ${item.format === 'date' ? month : month.slice(0, 3)}`];
      }
      const n = Number(v);
      const want = item.round === undefined ? n : Number(n.toFixed(Number(item.round)));
      return [String(v), Number(item.text.replace(/,/g, '')) === want];
    }
    if (item.kind === 'count') {
      const list = await value(item.spec);
      const where = (item.where || '').split(',').filter(Boolean).map(p => p.split('='));
      const n = Array.isArray(list) ? list.filter(x => where.every(([k, v]) => String(x?.[k]) === v)).length : NaN;
      return [String(n), Number(item.text) === n];
    }
    if (item.kind === 'answer') { const v = await value(item.spec); return [String(v), item.text === say(v)]; }
    if (item.kind === 'status') { const v = await value(item.spec); return [String(v), item.text === v]; }
    if (item.kind === 'doc') {
      const [path, snippet] = item.spec.split(/\|(.*)/s);
      const doc = norm(await load(path));
      return [snippet.length > 40 ? `${snippet.slice(0, 37)}...` : snippet, doc.includes(norm(snippet)) && norm(snippet).includes(item.text)];
    }
  } catch (e) { return [`error: ${e.message}`, false]; }
  return ['unknown kind', false];
}

// Runs in the page: bound items under a root, plus the visible digits that no binding explains.
function scan(index) {
  const slides = window.Reveal.getSlides();
  const root = index === null ? document : slides[index];
  const label = el => el.closest('section:not(.stack)')?.id || '?';
  const items = [];
  const push = (kind, sel, spec) => root.querySelectorAll(sel).forEach(el => items.push({ kind, slide: label(el), spec: spec(el), text: el.textContent.trim(),
    format: el.dataset.format, round: el.dataset.round, where: el.dataset.countWhere }));
  push('deck', '[data-deck-source]', el => el.dataset.deckSource);
  push('count', '[data-count]', el => el.dataset.count);
  push('answer', '[data-answer]', el => el.dataset.answer);
  push('status', '[data-status-source]', el => el.dataset.statusSource);
  push('doc', '[data-doc]', el => el.dataset.doc);
  if (index === null) return { items, loose: [] };
  const bound = '[data-source],[data-text-source],[data-deck-source],[data-count],[data-answer],[data-status-source],[data-doc],[data-review],.d-source,aside.notes,.c-replay-badge,.c-wtick,svg,.c-legend,.c-axis,.c-mx-grid > i,.c-index,.c-cell-note,.c-hbar small,.c-src,thead,.c-rv,.c-gate-readout';
  const loose = [];
  const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let n = walk.nextNode(); n; n = walk.nextNode()) {
    const el = n.parentElement;
    if (!/\d/.test(n.textContent) || el.closest(bound)) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    loose.push({ slide: label(el), text: n.textContent.trim() });
  }
  return { items, loose };
}

// Digits that are names, IDs, dates or versions, not quantities.
const LABELS = [/\bDEV-\d{3}\b/g, /\b[Pp][012]\b/g, /\bA\d{1,2}\b/g, /\bJev 1\.13\b/g, /\b(Opus|Sonnet) 5\.5\b/g, /\bGemma 4 26B\b/g, /\bGemma 26B\b/g, /\bGemma 4 31B\b/g, /\bGemma 31B\b/g,
  /\bQwen3\.8 27B\b/g, /\bQwen 27B\b/g, /\bQwen 35B\b/g, /\bA4B\b/g, /\bgpt-6-luna\b/g, /\bd1-3B\b/g, /\bKev [49]B\b/g, /\bTev1? ?1? ?4B\b/g, /\bTev 1 4B\b/g, /\bDecider 2B\b/g, /\bNimble 9B v2\b/g,
  /\bV1 27B\b/g, /\bv0\.2(\.1)?\b/g, /\bv1\b/g, /\bApache-2\.0\b/g, /\bRTX PRO 6000\b/g, /\b\d{1,2} (January|February|March|April|May|June|July|August|September|October|November|December|Sep|Oct)( \d{4})?\b/g,
  /\b20\d\d\b/g, /\bGemini 3\.1\b/g, /\bLiquid D1\b/g, /\bd1\b/g, /\bfresh1\b/g, /\bbatch 10\b/g, /\b[a-f0-9]{7,8}\b/g, /\bDecision Index v0\.2\.1\b/g, /\bfour-field\b/g, /\bpass [123]\b/gi, /\bProof [123]\b/g, /\baxis 44 to 60\b/g,
  /\b0\.[579](?= (gate|keeps))/g, /\bmore than 0\.2\b/g, /\bGemini 3\.1\b/g];
const residue = text => LABELS.reduce((t, re) => t.replace(re, ' '), text).match(/\d[\d.,]*/g) ?? [];

function beatsFromOutline(md) {
  const out = {};
  for (const [, n, body] of md.matchAll(/\[notes beat=(\d+)\]\n([\s\S]*?)\n\[\/notes\]/g)) out[n] = norm(body);
  return out;
}

const server = await serve();
const browser = await launch();
const rows = [];
const problems = [];
try {
  const live = await openDeck(browser, `${server.origin}/${pagePath}`);
  const slides = await listSlides(live.page);
  const loose = [];
  for (const [i, s] of slides.entries()) {
    await showFully(live.page, s);
    const found = await live.page.evaluate(scan, i);
    for (const it of found.items) rows.push(['live', ...await rowFor(it)]);
    loose.push(...found.loose);
  }
  // Notes and copy, from the live DOM.
  const deck = await live.page.evaluate(() => window.Reveal.getSlides().map(s => ({ id: s.id,
    notes: [...s.querySelectorAll('aside.notes p:not(.c-clicks):not(.c-direction)')].map(p => p.textContent).join(' '),
    copy: [...s.querySelectorAll('[data-copy]')].map(el => el.textContent).join(' ') })));
  problems.push(...live.problems.map(p => `live ${p}`));
  await live.context.close();

  const print = await openDeck(browser, `${server.origin}/${pagePath}?print-pdf`);
  await print.page.waitForFunction(() => document.querySelectorAll('.pdf-page').length > 0, null, { timeout: 20000 });
  await settle(print.page);
  for (const it of (await print.page.evaluate(scan, null)).items) rows.push(['print', ...await rowFor(it)]);
  problems.push(...print.problems.map(p => `print ${p}`));
  await print.context.close();

  console.log(`\ncontent-audit.mjs · ${pagePath} · ${slides.length} slides\n\n1. Bindings outside numbers.mjs`);
  console.log(table(['mode', 'slide', 'kind', 'source', 'shown', 'expected', 'result'], rows));

  const unbound = loose.map(l => ({ ...l, digits: residue(l.text) })).filter(l => l.digits.length);
  console.log(`\n2. Unbound digits on slides: ${unbound.length}`);
  for (const u of unbound) console.log(`  FAIL ${u.slide}: "${u.text}" -> ${u.digits.join(', ')}`);

  const outline = beatsFromOutline(await load('docs/talk/05-session-outline.md'));
  const byBeat = {};
  deck.slice(0, MAIN).forEach((s, i) => { byBeat[BEATS[i]] = norm(`${byBeat[BEATS[i]] ?? ''} ${s.notes}`); });
  const noteRows = Object.keys(outline).map(b => [b, outline[b].split(' ').length, (byBeat[b] ?? '').split(' ').length, outline[b] === byBeat[b] ? 'PASS' : 'FAIL']);
  console.log('\n3. Speaker notes against outline 2b (verbatim, whitespace-normalised)');
  console.log(table(['beat', 'outline words', 'deck words', 'result'], noteRows));
  for (const b of Object.keys(outline)) if (outline[b] !== byBeat[b]) {
    const a = outline[b], d = byBeat[b] ?? '';
    let k = 0; while (k < a.length && a[k] === d[k]) k++;
    console.log(`  beat ${b} differs at char ${k}: outline "${a.slice(k, k + 60)}" deck "${d.slice(k, k + 60)}"`);
  }

  const words = t => norm(t).split(' ').filter(Boolean).length;
  const copyRows = deck.slice(0, MAIN).map((s, i) => [`S${i + 1}`, s.id, words(s.copy), words(s.copy) <= 12 ? 'PASS' : COPY_EXCEPTIONS[s.id] ? `OVER (${COPY_EXCEPTIONS[s.id]})` : 'FAIL']);
  console.log('\n4. On-slide copy words per main slide ([data-copy]; eyebrows, data labels, review text and source lines excluded)');
  console.log(table(['slide', 'id', 'words', 'result'], copyRows));

  const deckHtml = await readFile(join(SITE, pagePath), 'utf8');
  const links = [...deckHtml.matchAll(/<a href="([^"#]*)(?:#([^"]*))?"/g)].filter(([, file]) => file && !file.startsWith('#'));
  const linkRows = new Map();
  for (const [, file, id] of links) {
    const page = file.replace(/^\.\//, '');
    const key = `${page}#${id ?? ''}`;
    if (linkRows.has(key)) { linkRows.get(key)[1]++; continue; }
    let ok = /^(index|explore|method)\.html$/.test(page);
    if (ok && id) ok = (await readFile(join(SITE, page), 'utf8')).includes(`id="${id}"`);
    linkRows.set(key, [key, 1, ok ? 'PASS' : 'FAIL']);
  }
  console.log('\n5. Source links out of the deck (target page and id must exist; raw .json links fail)');
  console.log(table(['target', 'links', 'result'], [...linkRows.values()]));

  for (const p of problems) console.log(`  FAIL ${p}`);
  const failed = rows.some(r => r[6] === 'FAIL') || unbound.length || noteRows.some(r => r[3] === 'FAIL') || copyRows.some(r => r[3] === 'FAIL') || [...linkRows.values()].some(r => r[2] === 'FAIL') || problems.length;
  console.log(failed ? '\nRESULT: FAIL' : '\nRESULT: PASS');
  process.exitCode = failed ? 1 : 0;
} finally {
  await browser.close();
  await server.close();
}

async function rowFor(it) {
  const [expected, ok] = await check(it);
  const src = it.spec.length > 70 ? `${it.spec.slice(0, 67)}...` : it.spec;
  return [it.slide, it.kind, src, it.text.length > 30 ? `${it.text.slice(0, 27)}...` : it.text, expected, ok ? 'PASS' : 'FAIL'];
}
