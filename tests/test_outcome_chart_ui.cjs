const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const feed = JSON.parse(fs.readFileSync(path.join(root, 'public-site/data-provider-errors-v1.json'), 'utf8'));
const script = fs.readFileSync(path.join(root, 'public-site/outcome-chart.js'), 'utf8');
const taxonomy = fs.readFileSync(path.join(root, 'public-site/model-categories.js'), 'utf8');
const app = fs.readFileSync(path.join(root, 'public-site/app.js'), 'utf8');
const report = JSON.parse(fs.readFileSync(path.join(root, 'public-site/sonnet55-fresh-matched3.json'), 'utf8'));
const clefReport = JSON.parse(fs.readFileSync(path.join(root, 'public-site/clef-findings.json'), 'utf8'));
const adapterSource = app.replace('  init();\n})();', '  globalThis.__firstPass = {sonnet55FirstPassRuns,clefFirstPassRuns};\n})();');
assert.notEqual(adapterSource, app);
const adapterContext = { document: {}, URL };
vm.runInNewContext(adapterSource, adapterContext);
const merged = { ...feed, runs: [...feed.runs, ...adapterContext.__firstPass.sonnet55FirstPassRuns(report), ...adapterContext.__firstPass.clefFirstPassRuns(clefReport)] };

function element(value = '') {
  return {
    value, innerHTML: '', textContent: '', handlers: {},
    addEventListener(type, callback) { this.handlers[type] = callback; },
    setAttribute(name, value) { this[name] = value; },
  };
}

function mount(source = merged) {
  const ids = ['outcome-chart', 'outcome-condition', 'outcome-category', 'outcome-coordinate', 'outcome-run', 'outcome-run-detail',
    'outcome-plot', 'outcome-count', 'outcome-point-title', 'outcome-point-count'];
  const elements = Object.fromEntries(ids.map(id => [id, element()]));
  elements['outcome-condition'].value = 'P0';
  const plot = elements['outcome-plot'];
  Object.defineProperty(plot, 'innerHTML', {
    get() { return this.html || ''; },
    set(value) {
      this.html = value;
      this.buttons = [...value.matchAll(/<button\b[^>]*data-point="([^"]+)"[^>]*>/g)].map(match => ({
        dataset: { point: match[1] }, handlers: {},
        addEventListener(type, callback) { this.handlers[type] = callback; },
        setAttribute(name, value) { this[name] = value; },
      }));
    },
  });
  plot.querySelectorAll = () => plot.buttons || [];
  const listeners = new Map();
  const context = { document: { getElementById: id => elements[id] || null }, console, globalThis: null,
    addEventListener(type, callback) { listeners.set(type, callback); },
    dispatchEvent(event) { listeners.get(event.type)?.(event); },
  };
  context.globalThis = context;
  vm.runInNewContext(taxonomy, context);
  vm.runInNewContext(script, context);
  context.dispatchEvent({ type: 'benchmark:saved-runs-ready', detail: source });
  return { elements, chart: context.OutcomeChart };
}

test('chart source binding admits only full 60-record saved runs', async () => {
  const { elements, chart } = mount();
  await new Promise(resolve => setImmediate(resolve));
  const prepared = chart.prepare(merged);
  assert.equal(prepared.closed.length, 302);
  assert.equal(prepared.excluded, 2);
  assert.ok(chart.group(prepared.closed).length >= 73);
  assert.match(elements['outcome-count'].textContent, /^132 closed runs shown/);
  assert.match(elements['outcome-count'].textContent, /2 partial runs are excluded/);
  assert.ok(elements['outcome-plot'].buttons.length > 0);
  assert.match(elements['outcome-run-detail'].innerHTML, /Open this run's saved source/);
  assert.equal(prepared.closed.filter(run => run.sourceOnlyDetails).length, 14);
  assert.equal(prepared.closed.filter(run => run.chartSourceUrl.includes('/sonnet55-fresh-matched3-evidence/evidence/')).length, 12);
  assert.equal(prepared.closed.filter(run => run.id.startsWith('clef') && run.chartSourceUrl.endsWith('/development/records.jsonl')).length, 2);
});

test('prompt and category filters select exact source-bound runs', async () => {
  const { elements } = mount();
  await new Promise(resolve => setImmediate(resolve));
  elements['outcome-condition'].value = 'P2';
  elements['outcome-condition'].handlers.change();
  assert.match(elements['outcome-count'].textContent, /^84 closed runs shown/);
  elements['outcome-category'].value = 'decision';
  elements['outcome-category'].handlers.change();
  assert.ok(elements['outcome-plot'].buttons.length > 0);
  const first = elements['outcome-plot'].buttons[0];
  first.handlers.click();
  assert.equal(first['aria-pressed'], 'true');
  assert.match(elements['outcome-run-detail'].innerHTML, /Open this run's saved source/);
  assert.match(elements['outcome-run-detail'].innerHTML, /\?run=[^" ]+#inspect/);
  assert.ok(elements['outcome-coordinate'].innerHTML.includes('valid'));
  elements['outcome-coordinate'].value = elements['outcome-plot'].buttons.at(-1).dataset.point;
  elements['outcome-coordinate'].handlers.change();
  assert.equal(elements['outcome-coordinate'].value, elements['outcome-plot'].buttons.at(-1).dataset.point);
});

test('partial rows never contribute scores, and malformed closed rows fail closed', () => {
  const { chart } = mount();
  const partial = feed.runs.find(run => run.complete !== true);
  const supplied = { denominator: 60, runs: [{ ...partial, valid: 60, metrics: { all_four: 60 } }] };
  assert.equal(chart.prepare(supplied).closed.length, 0);
  const closed = feed.runs.find(run => run.complete === true);
  assert.throws(() => chart.prepare({ denominator: 60, runs: [{ ...closed, metrics: { all_four: closed.valid + 1 } }] }));
  assert.throws(() => chart.prepare({ denominator: 60, runs: [{ ...closed, evidenceUrl: 'https://example.com/fake' }] }));
});

test('markup has accessible controls, axes, source caveat, and reduced-motion rule', () => {
  const html = fs.readFileSync(path.join(root, 'public-site/index.html'), 'utf8');
  const css = fs.readFileSync(path.join(root, 'public-site/outcome-chart.css'), 'utf8');
  for (const id of ['outcome-chart', 'outcome-condition', 'outcome-category', 'outcome-coordinate', 'outcome-run', 'outcome-plot', 'outcome-run-detail']) {
    assert.match(html, new RegExp(`id="${id}"`));
  }
  assert.match(html, /Only closed 60-record runs/);
  assert.match(html, /prefers-reduced-motion|outcome-chart\.css/);
  assert.match(css, /@media \(prefers-reduced-motion:reduce\)/);
  assert.match(css, /@media \(max-width:480px\)/);
  assert.match(app, /CustomEvent\('benchmark:saved-runs-ready'/);
});
