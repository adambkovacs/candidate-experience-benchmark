const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const site = file => path.join(root, 'public-site', file);
const feed = JSON.parse(fs.readFileSync(site('data-provider-errors-v1.json'), 'utf8'));
const pricing = JSON.parse(fs.readFileSync(site('subscription-price-estimates.json'), 'utf8'));
const script = fs.readFileSync(site('outcome-chart.js'), 'utf8');
const taxonomy = fs.readFileSync(site('model-categories.js'), 'utf8');
const labels = fs.readFileSync(site('site/labels.js'), 'utf8');
const app = fs.readFileSync(site('app.js'), 'utf8');
const report = JSON.parse(fs.readFileSync(site('sonnet55-fresh-matched3.json'), 'utf8'));
const clefReport = JSON.parse(fs.readFileSync(site('clef-findings.json'), 'utf8'));
const adapterSource = app.replace('  init();\n})();', '  globalThis.__firstPass = {sonnet55FirstPassRuns,clefFirstPassRuns};\n})();');
assert.notEqual(adapterSource, app);
const adapterContext = { document: {}, URL };
vm.runInNewContext(adapterSource, adapterContext);
const merged = { ...feed, runs: [...feed.runs, ...adapterContext.__firstPass.sonnet55FirstPassRuns(report), ...adapterContext.__firstPass.clefFirstPassRuns(clefReport)] };
const complete = merged.runs.filter(run => run.complete === true && run.records === 60);

// Independent restatement of the cost rule: provider charge, else the API-rate equivalent.
const num = v => v === null || v === undefined || v === '' || !Number.isFinite(Number(v)) ? null : Number(v);
function expectedCost(run) {
  const charge = num(run.cost?.knownUsd) ?? num(run.cost?.actualUsd);
  if (charge !== null) return charge > 0 ? charge : null;
  const entry = run.cost?.estimateKind !== 'published_input_rate' && pricing.runs[run.id]?.model === run.model ? pricing.runs[run.id] : null;
  const usd = entry ? num(entry.estimateUsd) : num(run.cost?.estimatedUsd);
  return usd > 0 ? usd : null;
}

function element(value = '') {
  return {
    value, innerHTML: '', textContent: '', handlers: {},
    addEventListener(type, callback) { this.handlers[type] = callback; },
    setAttribute(name, value) { this[name] = value; },
  };
}

async function mount(source = merged) {
  const ids = ['outcome-chart', 'outcome-condition', 'outcome-category', 'outcome-coordinate', 'outcome-run', 'outcome-run-detail',
    'outcome-plot', 'outcome-count', 'outcome-point-title', 'outcome-point-count'];
  const elements = Object.fromEntries(ids.map(id => [id, element()]));
  elements['outcome-condition'].value = 'P0';
  const plot = elements['outcome-plot'];
  Object.defineProperty(plot, 'innerHTML', {
    get() { return this.html || ''; },
    set(value) {
      this.html = value;
      this.points = [...value.matchAll(/<g class="outcome-point" data-point="([^"]+)"[^>]*>/g)].map(match => ({
        dataset: { point: match[1] }, handlers: {},
        addEventListener(type, callback) { this.handlers[type] = callback; },
        setAttribute(name, value) { this[name] = value; },
        getAttribute(name) { return name === 'data-point' ? match[1] : this[name]; },
      }));
    },
  });
  plot.querySelectorAll = () => plot.points || [];
  const listeners = new Map();
  const context = { document: { getElementById: id => elements[id] || null }, console, globalThis: null,
    fetch: async () => ({ ok: true, json: async () => pricing }),
    addEventListener(type, callback) { listeners.set(type, callback); },
    dispatchEvent(event) { listeners.get(event.type)?.(event); },
  };
  context.globalThis = context;
  context.window = context;
  vm.runInNewContext(labels, context);
  vm.runInNewContext(taxonomy, context);
  vm.runInNewContext(script, context);
  context.dispatchEvent({ type: 'benchmark:saved-runs-ready', detail: source });
  await new Promise(resolve => setImmediate(resolve));
  return { elements, chart: context.OutcomeChart, label: context.BM_LABEL, plot };
}
const runsOnChart = chart => chart.points().flatMap(point => point.runs);
const change = (elements, id, value) => { elements[id].value = value; elements[id].handlers.change(); };

test('only complete 60-review runs with a cost are plotted, at their own score and cost', async () => {
  const { chart } = await mount();
  const prepared = chart.prepare(merged);
  const priced = complete.filter(run => expectedCost(run) !== null);
  assert.equal(prepared.plotted.length + prepared.unpriced.length, complete.length);
  assert.equal(prepared.excluded, merged.runs.length - complete.length);
  assert.equal(prepared.plotted.length, priced.length);
  assert.ok(prepared.plotted.length > 100 && prepared.unpriced.length > 0);
  for (const run of prepared.plotted) {
    const source = complete.find(item => item.id === run.id);
    assert.equal(run.matches, source.metrics.all_four, run.id);
    assert.equal(run.usd, expectedCost(source), run.id);
    assert.equal(run.apiRate, (num(source.cost?.knownUsd) ?? num(source.cost?.actualUsd)) === null, run.id);
  }
  const opus = prepared.plotted.find(run => run.id === 'opus55-high-batch10');
  assert.equal(opus.usd, Number(pricing.runs['opus55-high-batch10'].estimateUsd));
  assert.equal(opus.apiRate, true);
});

test('default view: P0 count sentence and the best decision-model pass selected', async () => {
  const { elements, chart, label } = await mount();
  const prepared = chart.prepare(merged);
  const p0 = prepared.plotted.filter(run => run.condition === 'P0');
  const p0Missing = prepared.unpriced.filter(run => run.condition === 'P0');
  const local = p0Missing.filter(run => /local/i.test(run.surface || '')).length;
  assert.equal(elements['outcome-count'].textContent,
    `${p0.length} passes plotted. ${p0Missing.length} more have no recorded cost, ${local} of them local runs, and are not plotted.`);
  assert.equal(runsOnChart(chart).length, p0.length);
  const best = p0.filter(run => run.category.category === 'decision').sort((a, b) => b.matches - a.matches || a.usd - b.usd)[0];
  assert.ok(best.matches > 0);
  assert.equal(elements['outcome-run'].value, best.id);
  assert.equal(elements['outcome-point-title'].textContent, label.run(best));
  const detail = elements['outcome-run-detail'].innerHTML;
  assert.match(detail, new RegExp(`Matched ${best.matches} of 60, prompt P0`));
  assert.ok(detail.includes(`Cost of the pass: ${label.usd(best.usd)}`));
  assert.ok(detail.includes(`<code>${best.id}</code>`));
  assert.doesNotMatch(detail, /Saved source|Run ID|·/);
  const selected = chart.points().find(point => point.key === elements['outcome-coordinate'].value);
  assert.ok(selected.runs.some(run => run.id === best.id));
  assert.equal(elements['outcome-plot'].points.find(p => p.dataset.point === selected.key)['aria-pressed'], 'true');
});

test('prompt and category filters plot exactly the matching priced runs', async () => {
  const { elements, chart } = await mount();
  const prepared = chart.prepare(merged);
  const expect = (condition, category) => prepared.plotted.filter(run => (condition === 'all' || run.condition === condition) &&
    (!category || (run.category.categories || [run.category.category]).includes(category))).map(run => run.id).sort();
  for (const [condition, category] of [['P0', 'decision'], ['P2', ''], ['P2', 'general'], ['all', ''], ['P1', 'tuned']]) {
    change(elements, 'outcome-condition', condition);
    change(elements, 'outcome-category', category);
    assert.deepEqual(runsOnChart(chart).map(run => run.id).sort(), expect(condition, category), `${condition} ${category}`);
    assert.match(elements['outcome-count'].textContent, new RegExp(`^${expect(condition, category).length.toLocaleString('en-US')} pass`));
  }
  change(elements, 'outcome-condition', 'P0');
  change(elements, 'outcome-category', '');
  const last = elements['outcome-plot'].points.at(-1);
  last.handlers.click();
  assert.equal(last['aria-pressed'], 'true');
  assert.equal(elements['outcome-coordinate'].value, last.dataset.point);
  const point = chart.points().find(item => item.key === last.dataset.point);
  assert.equal(elements['outcome-run'].value, point.runs[0].id);
  elements['outcome-coordinate'].value = elements['outcome-plot'].points[0].dataset.point;
  elements['outcome-coordinate'].handlers.change();
  assert.equal(elements['outcome-plot'].points[0]['aria-pressed'], 'true');
  for (const id of ['outcome-coordinate', 'outcome-run']) {
    assert.doesNotMatch(elements[id].innerHTML, /·/);
    assert.match(elements[id].innerHTML, /<option value="[^"]+">[^<]+, [^<]+<\/option>/);
  }
});

test('log x ticks, fitted y range', async () => {
  const { chart } = await mount();
  assert.deepEqual([...chart.xDomain([{ usd: 0.00265654 }, { usd: 2.36471 }])], [0.001, 10]);
  assert.deepEqual([...chart.xDomain([{ usd: 0.02 }])], [0.01, 0.1]);
  assert.deepEqual([...chart.ticks(0.001, 10, true)], [0.001, 0.01, 0.1, 1, 10]);
  assert.deepEqual([...chart.yDomain([{ matches: 11 }, { matches: 59 }])], [10, 60]);
  assert.deepEqual([...chart.yDomain([{ matches: 53 }])], [50, 60]);
  assert.deepEqual([...chart.ticks(10, 60)], [10, 20, 30, 40, 50, 60]);
  assert.deepEqual([...chart.ticks(50, 60)], [50, 55, 60]);
});

test('markers are round, never overlap, and stay inside the plot area', async () => {
  const { elements } = await mount();
  for (const condition of ['P0', 'all']) {
    change(elements, 'outcome-condition', condition);
    const html = elements['outcome-plot'].innerHTML;
    assert.match(html, /<svg class="outcome-svg" viewBox="0 0 \d+ \d+"[^>]*preserveAspectRatio="xMidYMid meet"/);
    assert.match(html, />All four matched, of 60</);
    assert.match(html, />Cost of one pass, log scale</);
    assert.match(html, />\$0\.01</);
    assert.match(html, />Decision models</);
    const [, ax, ay, aw, ah] = html.match(/class="outcome-area" x="([\d.]+)" y="([\d.]+)" width="([\d.]+)" height="([\d.]+)"/).map(Number);
    const circles = [...html.matchAll(/<g class="outcome-point"[^>]*><circle cx="([\d.]+)" cy="([\d.]+)" r="([\d.]+)"/g)].map(m => m.slice(1).map(Number));
    assert.ok(circles.length > 10);
    for (const [i, [x, y, r]] of circles.entries()) {
      assert.ok(x - r >= ax && x + r <= ax + aw && y - r >= ay && y + r <= ay + ah, `marker ${i} spills`);
      for (const [x2, y2, r2] of circles.slice(i + 1)) assert.ok(Math.hypot(x - x2, y - y2) >= r + r2 - 0.11, `markers overlap at ${x},${y}`);
    }
  }
});

test('partial rows never contribute scores, and malformed complete rows fail closed', async () => {
  const { chart } = await mount();
  const partial = feed.runs.find(run => run.complete !== true);
  const supplied = { denominator: 60, runs: [{ ...partial, valid: 60, metrics: { all_four: 60 } }] };
  assert.equal(chart.prepare(supplied).plotted.length + chart.prepare(supplied).unpriced.length, 0);
  const closed = feed.runs.find(run => run.complete === true);
  assert.throws(() => chart.prepare({ denominator: 60, runs: [{ ...closed, metrics: { all_four: closed.valid + 1 } }] }));
  assert.throws(() => chart.prepare({ denominator: 60, runs: [closed, closed] }));
});

test('markup keeps the ids, the plot label, and the responsive and reduced-motion rules', () => {
  const html = fs.readFileSync(site('explore.html'), 'utf8');
  const css = fs.readFileSync(site('outcome-chart.css'), 'utf8');
  for (const id of ['outcome-chart', 'outcome-condition', 'outcome-category', 'outcome-coordinate', 'outcome-count', 'outcome-plot',
    'outcome-point-title', 'outcome-point-count', 'outcome-run', 'outcome-run-detail']) {
    assert.match(html, new RegExp(`id="${id}"`));
  }
  assert.match(html, /id="outcome-plot" role="group" aria-label="Cost of one pass against all-four matches out of 60"/);
  assert.match(css, /@media \(prefers-reduced-motion:reduce\)/);
  assert.match(css, /@media \(max-width:480px\)/);
  assert.match(app, /CustomEvent\('benchmark:saved-runs-ready'/);
});
