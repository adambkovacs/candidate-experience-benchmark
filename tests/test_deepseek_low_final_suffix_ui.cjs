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
  'deepseek-low-final-suffix-findings.json',
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

async function render({selected = deepseekLatest, override = {}, status = {}} = {}) {
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

const finalUrl = './deepseek-low-final-suffix-findings.json';

test('final suffix replaces the same DeepSeek series ID with three descriptive scores', async () => {
  const ui = await render();
  assert.equal(ui.get('repeat-config').value, deepseekLatest);
  assert.equal((ui.get('repeat-results').innerHTML.match(new RegExp(`value="${deepseekLatest}"`, 'g')) || []).length, 1);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 3);
  for (const score of [58, 57, 53]) assert.match(ui.get('repeat-chart').innerHTML, new RegExp(`${score}<small> / 60`));
  assert.match(ui.get('repeat-summary').textContent, /three scored descriptive phases/);
  assert.match(ui.get('repeat-summary').textContent, /clean completion remains 2 of 9/);
  assert.match(ui.get('repeat-interpretation').innerHTML, /56 valid responses, one invalid response, three preserved service failures and zero unsent/);
  assert.match(ui.get('repeat-interpretation').innerHTML, /a002196e/);
  assert.doesNotMatch(ui.get('repeat-interpretation').innerHTML, /No P2 score exists|ten comments not sent/);
  assert.match(ui.get('repeat-deltas').innerHTML, />-5<\/td>/);
  assert.match(ui.get('repeat-flips').innerHTML, /unavailable until all passes finish/);
  const usage = ui.get('repeat-usage-body').innerHTML;
  assert.match(usage, /144,657 observed/);
  assert.match(usage, /25,527 observed/);
  assert.match(usage, /57\/60 reported; 3 missing/);
  assert.match(usage, /10\/60 reported; 50 missing/);
  assert.match(usage, /3 unknown charges; not a complete bill/);
  assert.match(usage, /4176.7/);
  assert.match(usage, /60\/60 client HTTP durations; not provider inference time/);
  assert.doesNotMatch(usage, /50 attempted|10 unsent|NaN|undefined/);
  ui.get('repeat-field').value = 'sentiment'; ui.get('repeat-field').change();
  assert.match(ui.get('repeat-chart').innerHTML, /P2 Fresh pass 1 Sentiment: 56 out of 60/);
  ui.select('openrouter-paid-deepseek-v41-flash-low-descriptive-continuation-v1');
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 2);
  assert.match(ui.get('repeat-chart').innerHTML, /11 unsent; no score/);
});

test('missing, unavailable, malformed and unbound final evidence leaves the DEV-050 cutoff intact', async () => {
  const badScore = copy(feeds[finalUrl]); badScore.series[0].historicalFirstPass.P2.valid = 60;
  const badHash = copy(feeds[finalUrl]); badHash.sourceBindings[0].sha256 = 'bad';
  const unbound = copy(feeds[finalUrl]); unbound.sourceBindings = unbound.sourceBindings.filter(item => !item.path.endsWith('suffix.raw.jsonl'));
  const wrongPrior = copy(feeds[finalUrl]); wrongPrior.series[0].historicalFirstPass.P0.valid = 60;
  const missingUsage = copy(feeds[finalUrl]); delete missingUsage.series[0].p2ObservedUsage;
  for (const options of [{status: {[finalUrl]: 404}}, {status: {[finalUrl]: 500}},
    ...[badScore, badHash, unbound, wrongPrior, missingUsage].map(payload => ({override: {[finalUrl]: payload}}))]) {
    const ui = await render(options);
    assert.doesNotMatch(ui.get('repeat-results').innerHTML, /could not be loaded/);
    assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 2);
    assert.match(ui.get('repeat-chart').innerHTML, /10 unsent; no score/);
    assert.match(ui.get('repeat-summary').textContent, /2 of 9 phases/);
  }
});
