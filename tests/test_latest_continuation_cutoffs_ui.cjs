const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const site = path.join(__dirname, '..', 'public-site');
const source = fs.readFileSync(path.join(site, 'repeats.js'), 'utf8');
const filenames = ['qwen27-interrupted-continuation-findings.json',
  'gemma26-second-continuation-findings.json',
  'deepseek-low-third-interruption-findings.json',
  'hosted-v2-repeats.json',
  'gemma26-continuation-findings.json',
  'deepseek-low-continuation-repeats.json'];
const feeds = Object.fromEntries(filenames.map(file =>
  [`./${file}`, JSON.parse(fs.readFileSync(path.join(site, file), 'utf8'))]));
const ids = ['repeat-results', 'repeat-config', 'repeat-field', 'repeat-condition',
  'repeat-condition-label', 'repeat-interpretation', 'repeat-summary', 'repeat-lead',
  'repeat-chart', 'repeat-delta-title', 'repeat-delta-intro', 'repeat-deltas',
  'repeat-flips', 'repeat-usage-body'];
const qwenMedium = 'openrouter-paid-qwen3.8-27b-medium-interrupted-cutoff-v1';
const qwenXhigh = 'openrouter-paid-qwen3.8-27b-xhigh-interrupted-cutoff-v1';
const gemmaLatest = 'gemma26-on-v2-second-interruption-continuation-v1';
const deepseekLatest = 'openrouter-paid-deepseek-v41-flash-low-descriptive-continuation-v2';
const copy = value => JSON.parse(JSON.stringify(value));

async function render({selected = qwenMedium, override = {}, status = {}} = {}) {
  const ui = new Map(ids.map(name => [name, {innerHTML: '', textContent: '', value: '',
    addEventListener(type, fn) { this[type] = fn; }}]));
  const requested = [];
  const fetch = async url => {
    requested.push(url);
    if (status[url]) return {ok: false, status: status[url]};
    const payload = Object.hasOwn(override, url) ? override[url] : feeds[url];
    if (payload) return {ok: true, status: 200, json: async () => payload};
    return {ok: true, status: 200, json: async () => ({series: []})};
  };
  ui.get('repeat-config').value = selected;
  ui.get('repeat-field').value = 'allFour';
  ui.get('repeat-condition').value = 'P0';
  vm.runInNewContext(source,
    {document: {getElementById: name => ui.get(name)}, fetch, console},
    {filename: 'repeats.js'});
  await new Promise(resolve => setImmediate(resolve));
  return {get: name => ui.get(name), requested, select(value) {
    ui.get('repeat-config').value = value;
    ui.get('repeat-config').change();
  }};
}

test('Qwen cutoff retains both stages and scores only the closed xhigh P0 composite', async () => {
  const ui = await render();
  assert.match(ui.get('repeat-results').innerHTML, new RegExp(`value="${qwenMedium}"`));
  assert.match(ui.get('repeat-results').innerHTML, new RegExp(`value="${qwenXhigh}"`));
  assert.match(ui.get('repeat-results').innerHTML,
    /value="qwen27-fresh-matched3-v2-medium"/);
  assert.match(ui.get('repeat-results').innerHTML,
    /value="qwen27-fresh-matched3-v2-xhigh"/);
  assert.match(ui.get('repeat-summary').textContent, /0 of 2 fresh pass 3 phases/);
  assert.match(ui.get('repeat-chart').innerHTML, /37 valid, 1 service error, 22 unsent; no score/);
  assert.match(ui.get('repeat-chart').innerHTML, /0 saved, 60 unsent; no score/);
  assert.doesNotMatch(ui.get('repeat-chart').innerHTML, /<meter/);
  assert.match(ui.get('repeat-flips').innerHTML, /Cross-pass answer changes are outside/);
  ui.select(qwenXhigh);
  assert.match(ui.get('repeat-summary').textContent, /1 of 2 fresh pass 3 phases/);
  assert.match(ui.get('repeat-chart').innerHTML, /58<small> \/ 60<\/small>/);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 1);
  assert.match(ui.get('repeat-chart').innerHTML, /8 saved, 52 unsent; no score/);
  assert.match(ui.get('repeat-lead').textContent, /59\/60 valid responses/);
  assert.doesNotMatch(ui.get('repeat-deltas').innerHTML, />0<\/td>/);
});

test('Gemma second cutoff preserves first cutoff and historical scores', async () => {
  const ui = await render({selected: gemmaLatest});
  assert.match(ui.get('repeat-results').innerHTML,
    /value="gemma26-on-v2-interruption-continuation-v1"/);
  assert.match(ui.get('repeat-results').innerHTML,
    /value="gemma26-on-fresh-matched3-v2"/);
  assert.match(ui.get('repeat-summary').textContent, /6 of 9 phases have final scores/);
  assert.match(ui.get('repeat-chart').innerHTML, /56<small> \/ 60<\/small>/);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 6);
  assert.match(ui.get('repeat-chart').innerHTML, /4 valid, 1 service error, 55 unsent; no score/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /60 attempted/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /Unknown charge up to/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /Unavailable overall/);
  ui.select('gemma26-on-v2-interruption-continuation-v1');
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 5);
  assert.match(ui.get('repeat-chart').innerHTML, /1 valid, 1 service error, 58 unsent; no score/);
});

test('DeepSeek third cutoff retains prior cutoff and leaves P2 unscored', async () => {
  const ui = await render({selected: deepseekLatest});
  assert.match(ui.get('repeat-results').innerHTML,
    /value="openrouter-paid-deepseek-v41-flash-low-descriptive-continuation-v1"/);
  assert.match(ui.get('repeat-results').innerHTML,
    /DeepSeek low · third interruption at DEV-050/);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 2);
  assert.match(ui.get('repeat-chart').innerHTML,
    /46 valid, 1 invalid, 3 service errors, 10 unsent; no score/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /50 attempted/);
  assert.doesNotMatch(ui.get('repeat-usage-body').innerHTML, /combinedKnownAllAttemptCostUsd|NaN|undefined/);
  ui.select('openrouter-paid-deepseek-v41-flash-low-descriptive-continuation-v1');
  assert.match(ui.get('repeat-chart').innerHTML,
    /46 valid, 1 invalid, 2 service errors, 11 unsent; no score/);
});

test('malformed new cutoffs fail visibly and an optional 404 leaves earlier evidence usable', async () => {
  for (const [url, mutate] of [
    ['./qwen27-interrupted-continuation-findings.json', item => { item.series.medium.score = {allFour: 60}; }],
    ['./gemma26-second-continuation-findings.json', item => { item.compositeP0.score.outcomes.never_sent = 1; }],
    ['./deepseek-low-third-interruption-findings.json', item => { item.series[0].thirdInterruptionCheckpoint.score = {allFour: 46}; }],
  ]) {
    const bad = copy(feeds[url]); mutate(bad);
    const ui = await render({override: {[url]: bad}});
    assert.match(ui.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  }
  const missing = await render({selected: 'gemma26-on-v2-interruption-continuation-v1',
    status: {'./gemma26-second-continuation-findings.json': 404}});
  assert.match(missing.get('repeat-results').innerHTML,
    /value="gemma26-on-v2-interruption-continuation-v1"/);
  const failed = await render({status: {'./deepseek-low-third-interruption-findings.json': 500}});
  assert.match(failed.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
});
