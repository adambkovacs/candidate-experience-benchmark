const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const site = path.join(__dirname, '..', 'public-site');
const source = fs.readFileSync(path.join(site, 'repeats.js'), 'utf8');
const url = './qwen27-final-descriptive-findings.json';
const report = JSON.parse(fs.readFileSync(path.join(site, url.slice(2)), 'utf8'));
const earlier = JSON.parse(fs.readFileSync(path.join(site, 'qwen27-second-continuation-findings.json'), 'utf8'));
const ids = ['repeat-results', 'repeat-config', 'repeat-field', 'repeat-condition',
  'repeat-condition-label', 'repeat-interpretation', 'repeat-summary',
  'repeat-lead', 'repeat-chart', 'repeat-delta-title', 'repeat-delta-intro',
  'repeat-deltas', 'repeat-flips', 'repeat-usage-body'];
const medium = 'openrouter-paid-qwen3.8-27b-medium-descriptive-nine-v1';
const xhigh = 'openrouter-paid-qwen3.8-27b-xhigh-descriptive-nine-v1';

async function render({selected = medium, payload = report, status = 200} = {}) {
  const ui = new Map(ids.map(id => [id, {innerHTML: '', textContent: '', value: '',
    addEventListener(type, callback) { this[type] = callback; }}]));
  ui.get('repeat-config').value = selected;
  ui.get('repeat-field').value = 'allFour';
  ui.get('repeat-condition').value = 'P0';
  const fetch = async target => {
    if (target === url && status !== 200) return {ok: false, status};
    return {ok: true, status: 200, json: async () => target === url ? payload :
      target === './qwen27-second-continuation-findings.json' ? earlier : {series: []}};
  };
  vm.runInNewContext(source, {document: {getElementById: id => ui.get(id)}, fetch, console},
    {filename: 'repeats.js'});
  await new Promise(resolve => setImmediate(resolve));
  return {get: id => ui.get(id), select(id) {ui.get('repeat-config').value = id; ui.get('repeat-config').change();}};
}

test('nine scored phases show ranges and shared-valid changes without hiding interruptions', async () => {
  const ui = await render();
  assert.match(ui.get('repeat-results').innerHTML, new RegExp(`value="${medium}"`));
  assert.match(ui.get('repeat-results').innerHTML, new RegExp(`value="${xhigh}"`));
  assert.match(ui.get('repeat-summary').textContent, /56 to 59 matches out of 60/);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 9);
  assert.match(ui.get('repeat-chart').innerHTML, /Three-pass range: <strong>56–59/);
  assert.match(ui.get('repeat-flips').innerHTML, /3 \/ 59/);
  assert.match(ui.get('repeat-flips').innerHTML, /DEV-006/);
  assert.match(ui.get('repeat-flips').innerHTML, /1 comment was excluded/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /Unknown original charge up to/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /Unavailable overall/);
  assert.match(ui.get('repeat-interpretation').innerHTML, /not a clean three-pass test/);
  ui.select(xhigh);
  assert.match(ui.get('repeat-summary').textContent, /57 to 58 matches out of 60/);
  assert.match(ui.get('repeat-flips').innerHTML, /4 \/ 59/);
  assert.match(ui.get('repeat-interpretation').innerHTML, /DEV-037/);
  ui.get('repeat-condition').value = 'P2';
  ui.get('repeat-condition').change();
  assert.match(ui.get('repeat-flips').innerHTML, /4 \/ 60/);
  ui.get('repeat-field').value = 'sentiment';
  ui.get('repeat-field').change();
  assert.match(ui.get('repeat-chart').innerHTML, /Three-pass range: <strong>59–60/);
});

test('malformed report fails visibly; optional absence does not erase other series', async () => {
  for (const mutate of [
    item => {item.series[0].passes.fresh3.P0.score.allFour = 60;},
    item => {item.series[1].changesAcrossThreePasses.P0.denominator = 60;},
    item => {item.sourceBindings.pop();},
  ]) {
    const bad = structuredClone(report);
    mutate(bad);
    assert.match((await render({payload: bad})).get('repeat-results').innerHTML,
      /Repeat results could not be loaded/);
  }
  const missing = await render({status: 404,
    selected: 'openrouter-paid-qwen3.8-27b-medium-interrupted-composite-v2'});
  assert.doesNotMatch(missing.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  assert.match((await render({status: 500})).get('repeat-results').innerHTML,
    /Repeat results could not be loaded/);
});
