// Browser check for the three report pages. Serve public-site/ first, then:
//   node public-site/site/verify/verify-site.mjs http://127.0.0.1:8000/ [screenshot-dir] [--quick] [--software]
// Playwright is resolved from public-site/deck/verify/node_modules (or any install on NODE_PATH).
// Exit 0 means every check passed; the JSON report lists each check and the console it saw.
import { createRequire } from 'node:module';
import { mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const load = name => { try { return createRequire(resolve(here, '../../deck/verify/package.json'))(name); } catch { return createRequire(import.meta.url)(name); } };
const { chromium } = load('playwright');
const [base = 'http://127.0.0.1:8000/', shots = '', ...flags] = process.argv.slice(2);
const root = base.replace(/index\.html$/, '').replace(/\/?$/, '/');
const quick = flags.includes('--quick');
// The GPU path is what a visitor's browser uses. Chromium's SwiftShader logs a driver note for any WebGL canvas.
const args = flags.includes('--software') || process.platform !== 'darwin' ? [] : ['--use-angle=metal', '--enable-gpu'];
if (shots) mkdirSync(shots, { recursive: true });

// Ids the panel scripts query. They all live on explore.html now.
const PROTECTED = ["agreement-policy","analysis-library","analysis-refresh-cutoffs","analysis-refresh-summary","analysis-refresh-table","category-filter","clear-run-filters","clef-first-pass-results","clef-repeat-chart","cohort-reviews","compare-run-select","compare-search","comparison-list","condition-filter","condition-grid","cross-category","disputed-count","disputed-detail","disputed-field","disputed-list","disputed-model","disputed-search","disputed-subset","effort-filter","evidence-note-empty","evidence-note-search","evidence-note-status","experiment-context","experiment-note","experiment-select","experiment-title","extended-run-status","family-filter","field-comparison","finding-cost","finding-hard","finding-jev","finding-prompts","include-incomplete","inspect","inspect-jev","interface-filter","jev","jev-note","jev-prompt-results","jev-score","kev-prompt-results","liquid-prompt-chart","metric","outcome-category","outcome-chart","outcome-condition","outcome-coordinate","outcome-count","outcome-plot","outcome-point-count","outcome-point-title","outcome-run","outcome-run-detail","overview-condition","overview-count","overview-rows","overview-specialists","overview-surface","overview-toggle","reference-note","reference-sensitivity","repeat-results","report-cohort","report-lens-count","report-lens-note","result-count","review-evidence","roster-count","roster-list","roster-search","run-detail","score-heading","search","sort","source-links","story","story-change-answers","story-change-select","story-change-text","story-jev-grid","story-prompt-change","story-prompt-chart-title","study-explanation","surface-filter","training-filter","usage-summary"];
const PANELS = {
  'overview rows': '#overview-rows .overview-row', 'run detail': '#run-detail *', 'cross-category table': '#cross-category table',
  'agreement-policy table': '#agreement-policy table', 'outcome plot': '#outcome-plot *', 'reference sensitivity': '#reference-sensitivity select',
  'cohort reviews': '#cohort-reviews select', 'disputed reviews list': '#disputed-list *', 'repeat results': '#repeat-results *',
  'prompt comparison (kev)': '#kev-prompt-results *', 'prompt comparison (jev)': '#jev-prompt-results *', 'clef repeat chart': '#clef-repeat-chart *',
  'liquid prompt chart': '#liquid-prompt-chart *', 'analysis refresh table': '#analysis-refresh-table table', 'explorer condition grid': '#condition-grid *',
  'model comparison': '#field-comparison *', 'usage summary': '#usage-summary *', 'story jev grid': '#story-jev-grid > *', 'source links': '#source-links a'
};
// Old links (single page, reader.js, report-navigation.js, the deck's source links) and where they must land.
const LINKS = [
  ['index.html#inspect', 'explore.html', 'inspect'], ['index.html?run=typesafe-jev113-v2&case=DEV-003#inspect', 'explore.html', 'inspect'],
  ['index.html?run=perplexity-decider-native-fresh1-p0#inspect', 'explore.html', 'inspect'], ['index.html?cohort=general#report-lens', 'explore.html', 'report-lens'],
  ['index.html#review-evidence', 'explore.html', 'review-evidence'], ['index.html#agreement-policy', 'explore.html', 'agreement-policy'],
  ['index.html#explore', 'explore.html', 'explore'], ['index.html#repeat-analysis', 'explore.html', 'repeat-analysis'], ['index.html#reference-sensitivity', 'explore.html', 'reference-sensitivity'],
  ['index.html#analysis-update', 'explore.html', 'analysis-update'], ['index.html#models', 'explore.html', 'models'], ['index.html#usage', 'explore.html', 'usage'],
  ['index.html#story', 'explore.html', 'story'], ['index.html#prompt-analysis', 'explore.html', 'prompt-analysis'], ['index.html#run-ranking', 'explore.html', 'run-ranking'],
  ['index.html#method', 'method.html', 'method'], ['index.html#findings', 'method.html', 'findings'], ['index.html#deep-insights', 'index.html', 'deep-insights'],
  ['index.html#overview', 'index.html', 'overview'], ['index.html#rule', 'index.html', 'rule'], ['explore.html#cross-category', 'explore.html', 'cross-category'],
  ['explore.html?run=typesafe-jev113-v2&case=DEV-059#inspect', 'explore.html', 'inspect'], ['method.html#harness', 'method.html', 'harness']
];

const report = { root, renderer: args.length ? 'gpu (ANGLE Metal)' : 'default headless', runs: [], links: [], ok: true };
const fail = (entry, name, detail) => { entry.failures.push({ name, detail }); report.ok = false; };

async function open(context, entry, path) {
  const page = await context.newPage();
  const say = phase => msg => { if (['error', 'warning'].includes(msg.type())) entry.console.push(`${phase} ${msg.type()}: ${msg.text()}`); };
  entry.phase = 'load';
  page.on('console', msg => say(entry.phase)(msg));
  page.on('pageerror', err => entry.console.push(`${entry.phase} pageerror: ${err.message}`));
  page.on('response', res => { if (res.status() >= 400) entry.console.push(`${entry.phase} http ${res.status()}: ${res.url()}`); });
  await page.goto(root + path, { waitUntil: 'load', timeout: 120000 });
  return page;
}

const scrollThrough = page => page.evaluate(async () => {
  // The page uses CSS smooth scrolling, so every programmatic scroll asks for an instant jump.
  for (let y = 0; y < document.documentElement.scrollHeight; y += innerHeight * 0.75) { scrollTo({ top: y, behavior: 'instant' }); await new Promise(r => setTimeout(r, 90)); }
  for (let i = 0; i < 3; i++) { scrollTo({ top: document.documentElement.scrollHeight, behavior: 'instant' }); await new Promise(r => setTimeout(r, 400)); }
});

// Every Read-page number resolves from its feed with the deck's path grammar and must equal its text.
const checkBindings = page => page.evaluate(async () => {
  const cache = new Map();
  const get = name => { if (!cache.has(name)) cache.set(name, fetch(name).then(r => r.json())); return cache.get(name); };
  const walk = (node, path) => {
    for (const [, bracket, key] of path.matchAll(/\[([^\]]*)\]|([^.[\]]+)/g)) {
      if (node == null) break;
      if (key !== undefined) node = node[key];
      else if (/^\d+$/.test(bracket)) node = node[Number(bracket)];
      else if (/^(["']).*\1$/.test(bracket)) node = node[bracket.slice(1, -1)];
      else { const pairs = bracket.split(',').map(p => p.split('=')); node = node.find(i => pairs.every(([k, v]) => String(i?.[k]) === v)); }
    }
    return node;
  };
  const out = { checked: 0, mismatches: [] };
  for (const el of document.querySelectorAll('main [data-source], main [data-text-source]')) {
    if (el.closest('#deep-insights')) continue;
    const ref = el.dataset.source || el.dataset.textSource;
    const [name, path] = ref.split('#');
    const value = walk(await get(name), path);
    const text = el.textContent.trim();
    const ok = el.dataset.source ? Math.abs(Number(String(value)) - Number(text.replace(/[,$]/g, ''))) < 1e-9 : String(value) === text;
    out.checked++;
    if (!ok) out.mismatches.push({ ref, value, text });
  }
  return out;
});

async function run(name, { path, width, height, reducedMotion = 'no-preference', blockMotion = false, screenshots = false, interactions = false }) {
  const entry = { name, path, width, reducedMotion, blockMotion, failures: [], console: [], checks: {} };
  report.runs.push(entry);
  const browser = await chromium.launch({ args });
  const context = await browser.newContext({ viewport: { width, height }, reducedMotion });
  if (blockMotion) await context.route(/\/site\/(motion|hero|ninecell)\.js|\/site\/vendor\//, r => r.abort());
  const page = await open(context, entry, path);
  if (path === 'explore.html') {
    await page.waitForFunction(sel => Object.values(sel).every(s => document.querySelector(s)), PANELS, { timeout: 90000 }).catch(() => {});
    entry.checks.panels = await page.evaluate(sel => Object.fromEntries(Object.entries(sel).map(([k, s]) => [k, document.querySelectorAll(s).length])), PANELS);
    for (const [k, n] of Object.entries(entry.checks.panels)) if (!n) fail(entry, 'panel empty', k);
    const missing = await page.evaluate(ids => ids.filter(id => document.querySelectorAll(`[id="${id}"]`).length !== 1), PROTECTED);
    entry.checks.protectedIds = `${PROTECTED.length - missing.length}/${PROTECTED.length}`;
    if (missing.length) fail(entry, 'protected ids missing or duplicated', missing);
  }
  await page.waitForTimeout(2000);
  const loadConsole = entry.console.filter(line => !(blockMotion && /ERR_FAILED/.test(line)));
  if (loadConsole.length) fail(entry, 'console on load', loadConsole);
  entry.checks.state = await page.evaluate(() => ({
    title: document.title, h1: document.querySelectorAll('h1').length, overflowX: document.documentElement.scrollWidth - innerWidth,
    heroLive: !!document.querySelector('.hero-stage.is-live canvas'), layerCurrent: document.querySelector('.layer-nav [aria-current="page"]')?.textContent
  }));
  if (entry.checks.state.overflowX > 0) fail(entry, 'horizontal scroll', entry.checks.state.overflowX);
  if (entry.checks.state.h1 !== 1) fail(entry, 'expected one h1', entry.checks.state.h1);
  if (path === 'index.html') {
    entry.checks.bindings = await checkBindings(page);
    if (entry.checks.bindings.mismatches.length || entry.checks.bindings.checked < 40) fail(entry, 'bindings', entry.checks.bindings);
    if (reducedMotion === 'reduce' && entry.checks.state.heroLive) fail(entry, 'WebGL ran under reduced motion', true);
  }
  entry.phase = 'scroll';
  await scrollThrough(page);
  entry.checks.afterScroll = await page.evaluate(() => ({
    stillHidden: document.querySelectorAll('.js-reveal').length,
    faint: [...document.querySelectorAll('main > *, body > footer')].filter(el => +getComputedStyle(el).opacity < 0.99).map(el => el.id || el.className),
    countups: [...document.querySelectorAll('[data-countup]')].map(el => el.textContent.trim()).join(' '),
    stickyHeads: document.querySelectorAll('table.has-sticky-head').length
  }));
  if (entry.checks.afterScroll.stillHidden || entry.checks.afterScroll.faint.length) fail(entry, 'blocks not fully visible after scrolling', entry.checks.afterScroll);
  if (path === 'index.html' && entry.checks.afterScroll.countups !== '53 0 7 58 0 2 35') fail(entry, 'count-ups did not land on their text', entry.checks.afterScroll.countups);
  if (screenshots && shots) {
    entry.phase = 'screenshots';
    const tag = path.replace('.html', '');
    await page.evaluate(() => scrollTo({ top: 0, behavior: 'instant' }));
    await page.waitForTimeout(2600);
    await page.screenshot({ path: `${shots}/${tag}-${width}-00-viewport.jpg`, type: 'jpeg', quality: 70 });
    const blocks = await page.evaluate(() => [...document.querySelectorAll('main > section, main > details, body > footer')].map((el, i) => ({ i, key: el.id || el.tagName.toLowerCase() })));
    for (const { i, key } of blocks) {
      const box = await page.evaluate(n => {
        const el = document.querySelectorAll('main > section, main > details, body > footer')[n];
        el.scrollIntoView({ block: 'start', behavior: 'instant' });
        const r = el.getBoundingClientRect();
        return { y: r.top + scrollY, h: r.height };
      }, i);
      await page.waitForTimeout(500);
      if (box.h < 4) continue;
      await page.screenshot({ path: `${shots}/${tag}-${width}-${String(i + 1).padStart(2, '0')}-${key}.jpg`, type: 'jpeg', quality: 70, fullPage: true, clip: { x: 0, y: Math.max(0, box.y - 12), width, height: Math.min(box.h + 24, 3200) } });
    }
  }
  if (interactions) {
    entry.phase = 'interactions';
    entry.checks.interactions = await interact(page, entry).catch(err => { fail(entry, 'interaction step threw', err.message.split('\n')[0]); return null; });
  }
  entry.passed = !entry.failures.length;
  await browser.close();
}

async function interact(page, entry) {
  const text = sel => page.$eval(sel, el => el.innerText.trim());
  const pick = async (sel, index) => {
    // The first non-empty option at or after `index` that differs from the current one (inspector and compare share a selection).
    const value = await page.$eval(sel, (el, i) => [...el.options].slice(i).concat([...el.options]).find(o => o.value && o.value !== el.value)?.value ?? el.value, index);
    await page.selectOption(sel, value);
    await page.waitForTimeout(500);
  };
  const out = {};
  const check = (k, ok, detail) => { out[k] = ok ? 'ok' : detail; if (!ok) fail(entry, `interaction: ${k}`, detail); };
  let before = await text('#report-lens-count');
  await page.click('#report-cohort [data-cohort="general"]');
  await page.waitForTimeout(700);
  check('cohort switch', (await text('#report-lens-count')) !== before, before);
  await page.$eval('details.all-runs', el => { el.open = true; });
  before = await text('#result-count');
  await pick('#family-filter', 2);
  check('explorer filter', (await text('#result-count')) !== before, before);
  await page.click('#clear-run-filters').catch(() => {});
  before = await text('#field-comparison');
  await pick('#compare-run-select', 3);
  check('compare picker', (await text('#field-comparison')) !== before, 'comparison did not change');
  before = await text('#run-detail');
  await pick('#inspect-run-select', 3);
  check('run inspector', (await text('#run-detail')) !== before, 'run detail did not change');
  before = await text('#study-explanation');
  await page.click('[data-study-step="decisions"]');
  await page.waitForTimeout(300);
  check('study steps', (await text('#study-explanation')) !== before, before.slice(0, 60));
  await page.click('.main-nav a[href="#review-evidence"]');
  await page.waitForTimeout(1800);
  const nav = await page.evaluate(() => ({ hash: location.hash, current: document.querySelector('.main-nav a[aria-current]')?.hash, top: Math.round(document.getElementById('review-evidence').getBoundingClientRect().top) }));
  check('nav jump', nav.hash === '#review-evidence' && nav.current === '#review-evidence' && nav.top >= 0 && nav.top < 260, nav);
  return out;
}

async function links() {
  const browser = await chromium.launch({ args });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  for (const [from, page, id] of LINKS) {
    const entry = { failures: [], console: [] };
    const tab = await open(context, entry, from);
    await tab.waitForTimeout(5000);
    const got = await tab.evaluate(target => ({ url: location.pathname.split('/').pop() + location.search + location.hash, top: Math.round(document.getElementById(target)?.getBoundingClientRect().top ?? -1e6) }), id);
    const ok = got.url.startsWith(page) && got.top >= 0 && got.top <= 260 && !entry.console.length;
    report.links.push({ from, landed: got.url, targetTop: got.top, ok, console: entry.console });
    if (!ok) report.ok = false;
    await tab.close();
  }
  await browser.close();
}

for (const path of ['index.html', 'explore.html', 'method.html']) {
  await run(`${path} desktop`, { path, width: 1440, height: 900, screenshots: true, interactions: path === 'explore.html' });
  await run(`${path} phone`, { path, width: 390, height: 844, screenshots: true });
}
if (!quick) {
  await run('index.html reduced motion', { path: 'index.html', width: 1440, height: 900, reducedMotion: 'reduce' });
  await run('index.html motion blocked', { path: 'index.html', width: 1440, height: 900, blockMotion: true });
  await run('explore.html glue blocked', { path: 'explore.html', width: 1440, height: 900, blockMotion: true, interactions: true });
  await links();
}
console.log(JSON.stringify(report, null, 1));
process.exit(report.ok ? 0 : 1);
