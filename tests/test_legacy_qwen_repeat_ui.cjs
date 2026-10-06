const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const site = path.join(__dirname, '..', 'public-site');

test('legacy Qwen feed exposes all six configurations and only closed scores', async () => {
  const payload = JSON.parse(fs.readFileSync(path.join(site, 'legacy-qwen-repeats.json')));
  assert.equal(payload.series.length, 6);
  const ids = ['repeat-search','repeat-coverage','repeat-filter-count','repeat-selected-results','repeat-results','repeat-config','repeat-field','repeat-condition',
    'repeat-condition-label','repeat-interpretation','repeat-lead','repeat-summary','repeat-chart',
    'repeat-delta-title','repeat-delta-intro','repeat-deltas','repeat-flips','repeat-usage-body'];
  const elements = new Map(ids.map(id => [id, {innerHTML:'', textContent:'', value:'',
    addEventListener(type, listener) { this[type] = listener; }}]));
  const target = payload.series.find(s => s.configuration === 'qwen3-0.6b-q4km-nonthinking');
  assert.ok(target);
  elements.get('repeat-config').value = target.configuration;
  elements.get('repeat-field').value = 'allFour';
  elements.get('repeat-condition').value = 'P0';
  const requested = [];
  const fetch = async (url, options) => {
    assert.equal(options?.cache, 'no-store', 'repeat data must bypass stale browser caches');
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
    const series = payload.series.find(row => row.configuration === configuration);
    assert.equal((elements.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, series.completedConditions);
    assert.equal(series.completedConditions, 9);
    assert.doesNotMatch(elements.get('repeat-chart').innerHTML, /Three-pass range unavailable/);
    assert.equal((elements.get('repeat-chart').innerHTML.match(/Three-pass range:/g) || []).length, 3);
    assert.equal(series.passes.fresh1.P0.score.denominator, 60);
    assert.ok(series.passes.fresh1.P0.score.outcomes.invalid_output > 0);
  }
  const qwen35 = payload.series.find(row => row.configuration === 'qwen3.5-4b-sdk-thinking-on');
  assert.equal(qwen35.completedConditions, 2);
  assert.equal(qwen35.partialPasses.length, 1);
  assert.equal(qwen35.passes.fresh1.P0, undefined);
  assert.equal(qwen35.passes.fresh1.P1.score.allFour, 47);
  assert.equal(qwen35.passes.fresh1.P1.score.valid, 51);
  assert.equal(qwen35.passes.fresh1.P2.score.allFour, 50);
  assert.equal(qwen35.passes.fresh1.P2.score.valid, 51);
  elements.get('repeat-config').value = qwen35.configuration;
  elements.get('repeat-config').change();
  assert.match(elements.get('repeat-chart').innerHTML,
    /aria-label="P2 Fresh pass 1 All four decisions: 50 out of 60"/);
  assert.match(elements.get('repeat-chart').innerHTML, /<strong>50<small> \/ 60<\/small><\/strong>/);
  if (qwen35.descriptiveComposites?.length) {
    const composite = qwen35.descriptiveComposites[0];
    assert.match(elements.get('repeat-chart').innerHTML, new RegExp(`Descriptive interrupted: ${composite.score.allFour}/60 matches`));
    assert.match(elements.get('repeat-lead').textContent, /DEV-052 remains unknown and no reviews remain unsent/);
    assert.match(elements.get('repeat-summary').textContent, /2\/9 clean phases are closed/);
    assert.doesNotMatch(elements.get('repeat-summary').textContent, /no final results/i);
    assert.match(elements.get('repeat-usage-body').innerHTML, /59 saved, 1 unknown, 0 unsent/);
    assert.doesNotMatch(elements.get('repeat-chart').innerHTML, /8 unsent/);
  } else {
    assert.match(elements.get('repeat-chart').innerHTML, /Stopped: 44 valid, 7 invalid, 1 unknown, 8 unsent; no score/);
    assert.match(elements.get('repeat-lead').textContent, /DEV-052 has an unknown outcome/);
    assert.match(elements.get('repeat-usage-body').innerHTML, /Host sleep overlaps the unknown request/);
  }
  assert.equal((elements.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 2);
  const qwen17 = payload.series.find(row => row.configuration === 'qwen3-1.7b-sdk-thinking-off');
  qwen17.passes.fresh1.P0.powerObservation = {source:'ac', basis:'matching_pre_post_checks'};
  qwen17.passes.fresh1.P1.powerObservation = {source:'ac', basis:'pre_stage_only'};
  qwen17.passes.fresh1.P2.powerObservation = {source:null, basis:'unverified_or_conflicting_checks'};
  qwen17.passes.fresh2.P1.powerObservation = {source:'battery', basis:'matching_pre_post_checks'};
  elements.get('repeat-config').value = qwen17.configuration;
  elements.get('repeat-config').change();
  const timing = elements.get('repeat-usage-body').innerHTML;
  assert.match(timing, /Power at matching pre\/post checks: AC/);
  assert.match(timing, /Power at matching pre\/post checks: battery/);
  assert.match(timing, /Power at pre-stage check: AC; end unverified/);
  assert.match(timing, /Power source unavailable from verified checks/);
  elements.get('repeat-config').value = 'qwen3-0.6b-sdk-thinking-off';
  elements.get('repeat-config').change();
  elements.get('repeat-search').value = 'no-such-model';
  elements.get('repeat-search').input();
  assert.equal(elements.get('repeat-config').disabled, true);
  assert.equal(elements.get('repeat-selected-results').hidden, true);
  assert.match(elements.get('repeat-filter-count').textContent, /No studies match/);
  elements.get('repeat-search').value = '';
  elements.get('repeat-coverage').value = 'complete';
  elements.get('repeat-coverage').change();
  assert.equal(elements.get('repeat-config').value, 'qwen3-0.6b-sdk-thinking-off');
  assert.equal(elements.get('repeat-selected-results').hidden, false);
  assert.equal(elements.get('repeat-config').disabled, false);
  assert.match(elements.get('repeat-filter-count').textContent, /5 of 6/);

});
