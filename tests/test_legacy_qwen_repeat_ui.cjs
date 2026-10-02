const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const site = path.join(__dirname, '..', 'public-site');

test('legacy Qwen feed exposes all six configurations and only closed scores', async () => {
  const payload = JSON.parse(fs.readFileSync(path.join(site, 'legacy-qwen-repeats.json')));
  assert.equal(payload.series.length, 6);
  const ids = ['repeat-results','repeat-config','repeat-field','repeat-condition',
    'repeat-condition-label','repeat-interpretation','repeat-lead','repeat-chart',
    'repeat-delta-title','repeat-delta-intro','repeat-deltas','repeat-flips','repeat-usage-body'];
  const elements = new Map(ids.map(id => [id, {innerHTML:'', textContent:'', value:'',
    addEventListener(type, listener) { this[type] = listener; }}]));
  const target = payload.series.find(s => s.configuration === 'qwen3-0.6b-q4km-nonthinking');
  assert.ok(target);
  elements.get('repeat-config').value = target.configuration;
  elements.get('repeat-field').value = 'allFour';
  elements.get('repeat-condition').value = 'P0';
  const requested = [];
  const fetch = async url => {
    requested.push(url);
    return {ok:true,status:200,json:async () => url === './legacy-qwen-repeats.json' ? payload : {series:[]}};
  };
  vm.runInNewContext(fs.readFileSync(path.join(site, 'repeats.js'),'utf8'),
    {document:{getElementById:id => elements.get(id)},fetch,console});
  await new Promise(resolve => setImmediate(resolve));
  assert.ok(requested.includes('./legacy-qwen-repeats.json'));
  for (const row of payload.series) assert.ok(elements.get('repeat-results').innerHTML.includes(row.configuration));
  assert.match(elements.get('repeat-lead').textContent, new RegExp(`${target.completedConditions} of 9`));
  assert.equal((elements.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, target.completedConditions);
  assert.doesNotMatch(elements.get('repeat-usage-body').innerHTML, /\$0\.00/);
  for (const configuration of ['qwen3-0.6b-sdk-thinking-on','qwen3-0.6b-sdk-thinking-off']) {
    elements.get('repeat-config').value = configuration;
    elements.get('repeat-config').change();
    assert.match(elements.get('repeat-chart').innerHTML, /Smoke returned invalid format; full run not started/);
    assert.doesNotMatch(elements.get('repeat-chart').innerHTML, /<meter/);
  }
});
