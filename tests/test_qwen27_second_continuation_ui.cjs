const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const site = path.join(__dirname, '..', 'public-site');
const source = fs.readFileSync(path.join(site, 'repeats.js'), 'utf8');
const url = './qwen27-second-continuation-findings.json';
const latest = JSON.parse(fs.readFileSync(path.join(site, url.slice(2)), 'utf8'));
const earlier = JSON.parse(fs.readFileSync(path.join(site,
  'qwen27-interrupted-continuation-findings.json'), 'utf8'));
const medium = 'openrouter-paid-qwen3.8-27b-medium-interrupted-composite-v2';
const xhigh = 'openrouter-paid-qwen3.8-27b-xhigh-interrupted-composite-v2';
const ids = ['repeat-results', 'repeat-config', 'repeat-field', 'repeat-condition',
  'repeat-condition-label', 'repeat-interpretation', 'repeat-summary',
  'repeat-lead', 'repeat-chart', 'repeat-delta-title', 'repeat-delta-intro',
  'repeat-deltas', 'repeat-flips', 'repeat-usage-body'];

async function render({selected = medium, report = latest, responseStatus = 200} = {}) {
  const ui = new Map(ids.map(id => [id, {innerHTML: '', textContent: '', value: '',
    addEventListener(type, callback) { this[type] = callback; }}]));
  ui.get('repeat-config').value = selected;
  ui.get('repeat-field').value = 'allFour';
  ui.get('repeat-condition').value = 'P0';
  const fetch = async target => {
    if (target === url && responseStatus !== 200)
      return {ok: false, status: responseStatus};
    const payload = target === url ? report :
      target === './qwen27-interrupted-continuation-findings.json' ? earlier :
      {series: []};
    return {ok: true, status: 200, json: async () => payload};
  };
  vm.runInNewContext(source,
    {document: {getElementById: id => ui.get(id)}, fetch, console},
    {filename: 'repeats.js'});
  await new Promise(resolve => setImmediate(resolve));
  return {get: id => ui.get(id), select(id) {
    ui.get('repeat-config').value = id;
    ui.get('repeat-config').change();
  }};
}

test('both new Qwen composites stay separate from historical interrupted cutoffs', async () => {
  const ui = await render();
  const html = ui.get('repeat-results').innerHTML;
  assert.match(html, new RegExp(`value="${medium}"`));
  assert.match(html, new RegExp(`value="${xhigh}"`));
  assert.match(html, /value="openrouter-paid-qwen3.8-27b-medium-interrupted-cutoff-v1"/);
  assert.match(html, /value="openrouter-paid-qwen3.8-27b-xhigh-interrupted-cutoff-v1"/);
  assert.match(ui.get('repeat-summary').textContent, /P0 matched all four.*57 of 60.*P1.*56 of 60/);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 2);
  assert.match(ui.get('repeat-chart').innerHTML, /57<small> \/ 60<\/small>/);
  assert.match(ui.get('repeat-chart').innerHTML, /56<small> \/ 60<\/small>/);
  assert.match(ui.get('repeat-deltas').innerHTML, />-1<\/td>/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /59 valid, 1 preserved service error/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /Unknown original charge up to/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /Unavailable overall/);
  assert.match(ui.get('repeat-interpretation').innerHTML, /<details><summary>How these runs were completed/);
  ui.select(xhigh);
  assert.match(ui.get('repeat-summary').textContent, /P0 matched all four.*58 of 60.*P1.*58 of 60/);
  assert.match(ui.get('repeat-deltas').innerHTML, />0<\/td>/);
  assert.match(ui.get('repeat-interpretation').innerHTML, /DEV-037/);
});

test('malformed new evidence fails visibly while optional 404 retains the first cutoff', async () => {
  for (const mutate of [
    item => { item.series.medium.conditions.P0.score.allFour = 60; },
    item => { item.series.xhigh.conditions.P1.usage.unknownCostCount = 1; },
    item => { item.sourceBindings.pop(); },
  ]) {
    const bad = structuredClone(latest);
    mutate(bad);
    const ui = await render({report: bad});
    assert.match(ui.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  }
  const missing = await render({selected:
    'openrouter-paid-qwen3.8-27b-medium-interrupted-cutoff-v1', responseStatus: 404});
  assert.match(missing.get('repeat-results').innerHTML,
    /value="openrouter-paid-qwen3.8-27b-medium-interrupted-cutoff-v1"/);
  const failed = await render({responseStatus: 500});
  assert.match(failed.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
});
