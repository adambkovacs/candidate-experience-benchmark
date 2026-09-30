const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'public-site', 'repeats.js'), 'utf8');
const feed = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'public-site', 'anyjev-generated-repeats.json'), 'utf8'));
const url = './anyjev-generated-repeats.json';
const ids = ['repeat-results', 'repeat-config', 'repeat-field', 'repeat-condition',
  'repeat-condition-label', 'repeat-interpretation', 'repeat-lead', 'repeat-chart',
  'repeat-delta-title', 'repeat-delta-intro', 'repeat-deltas', 'repeat-flips', 'repeat-usage-body'];

async function render(payload = feed, status = 200, selected = feed.configuration) {
  const elements = new Map(ids.map(id => [id, {innerHTML: '', textContent: '', value: '',
    addEventListener(type, listener) { this[type] = listener; }}]));
  const requested = [];
  const fetch = async name => {
    requested.push(name);
    if (name === url) return {ok: status === 200, status, json: async () => payload};
    return {ok: true, status: 200, json: async () => name === './typesafe-repeats.json'
      ? {series: [{configuration: 'jev-fixture', displayName: 'Jev',
        passes: {original: {}, repeat2: {}, repeat3: {}}, denominator: 60,
        completedConditions: 0, plannedConditions: 9}]}
      : name === './anyjev-raw-repeats.json'
        ? {series: [{configuration: 'anyjev-native-fixture', displayName: 'AnyJev native readout',
          passes: {original: {}, repeat2: {}, repeat3: {}}, denominator: 60,
          completedConditions: 0, plannedConditions: 3}]}
        : {series: []}};
  };
  elements.get('repeat-config').value = selected;
  elements.get('repeat-field').value = 'allFour';
  elements.get('repeat-condition').value = 'P0';
  const document = {getElementById(id) { return elements.get(id); }};
  vm.runInNewContext(source, {document, fetch, console}, {filename: 'repeats.js'});
  await new Promise(resolve => setImmediate(resolve));
  return {get: id => elements.get(id), requested,
    field(value) { elements.get('repeat-field').value = value; elements.get('repeat-field').change(); }};
}

test('first generated P0/P1/P2 pass preserves invalid outcomes and fixed-60 scores', async () => {
  const ui = await render();
  assert.equal(ui.requested.filter(name => name === url).length, 1);
  const options = ui.get('repeat-results').innerHTML;
  assert.ok(options.indexOf('jev-fixture') < options.indexOf(feed.configuration));
  assert.match(options, /anyjev-native-fixture/);
  assert.match(options, /anyjev-qwen06-generated-fresh-three/);
  const lead = ui.get('repeat-lead').textContent;
  assert.match(lead, new RegExp(`${feed.completedConditions} of 9 planned prompt/pass combinations`));
  assert.match(lead, /P0 Fresh pass 1: 0\/60 valid responses/);
  assert.match(lead, /P1 Fresh pass 1: 0\/60 valid responses/);
  assert.match(lead, /P2 Fresh pass 1: 30\/60 valid responses/);
  assert.match(lead, /generated JSON control is separate from AnyJev native readouts/);
  assert.match(lead, /strict parser does not repair fenced JSON/);
  assert.match(lead, /zero shared-valid reviews cannot show stability/);
  const chart = ui.get('repeat-chart').innerHTML;
  assert.match(chart, /value="0"[^>]*aria-label="P0 Fresh pass 1 All four decisions: 0 out of 60"/);
  assert.match(chart, /value="1"[^>]*aria-label="P2 Fresh pass 1 All four decisions: 1 out of 60"/);
  assert.match(chart, /<strong>0<small> \/ 60<\/small><\/strong>/);
  assert.equal((chart.match(/<meter/g) || []).length, feed.completedConditions);
  assert.match(chart, /Three-pass range unavailable until all passes finish/);
  assert.match(ui.get('repeat-deltas').innerHTML, /<td>0<\/td>/);
  assert.match(ui.get('repeat-deltas').innerHTML, /<td>\+1<\/td>/);
  assert.match(ui.get('repeat-deltas').innerHTML, /unavailable; no shared-valid reviews; 0 shared valid of 60; 60 excluded/);
  assert.match(ui.get('repeat-flips').innerHTML, /Three-pass changes are unavailable/);
  assert.doesNotMatch(ui.get('repeat-flips').innerHTML, /0 \/ 0 changed/);
  const usage = ui.get('repeat-usage-body').innerHTML;
  assert.match(usage, /94,350/);
  assert.match(usage, /2,726/);
  assert.match(usage, /155\.9/);
  assert.match(usage, /104,850/);
  assert.match(usage, /2,734/);
  assert.match(usage, /172\.9/);
  assert.match(usage, /159,150/);
  assert.match(usage, /2,664/);
  assert.match(usage, /263\.6/);
  assert.match(usage, /Unavailable/);
  assert.doesNotMatch(usage, /\$0\.00/);
  assert.match(ui.get('repeat-interpretation').innerHTML, /historical generated observations are ineligible/);
  ui.field('sentiment');
  assert.match(ui.get('repeat-chart').innerHTML, /value="0"[^>]*aria-label="P0 Fresh pass 1 Sentiment: 0 out of 60"/);
});

test('zero shared-valid denominator remains unavailable when more invalid passes close', async () => {
  const phase = feed.passes.fresh1.P0;
  const payload = structuredClone(feed);
  payload.passes.fresh2.P0 = phase;
  payload.passes.fresh3.P0 = phase;
  payload.missingPasses = payload.missingPasses.filter(item => item.condition !== 'P0');
  payload.completedConditions = 9 - payload.missingPasses.length;
  payload.threePassSummary.P0.allFour = {completedPasses: 3, values: [0, 0, 0], mean: 0, range: [0, 0]};
  payload.changesAcrossThreePasses.P0 = {denominator: 0, excludedIds: phase.score.invalidIds,
    fourFieldVector: [], fields: {sentiment: [], follow_up_needed: [],
      serious_concern_reported: [], testimonial_potential: []}};
  payload.pairwiseFlips = [['fresh1', 'fresh2'], ['fresh1', 'fresh3'], ['fresh2', 'fresh3']]
    .map(([from, to]) => ({condition: 'P0', from, to, denominator: 0, excludedIds: phase.score.invalidIds,
      fourFieldVector: {changed: 0}, sentiment: {changed: 0}, follow_up_needed: {changed: 0},
      serious_concern_reported: {changed: 0}, testimonial_potential: {changed: 0}}));
  const ui = await render(payload);
  assert.match(ui.get('repeat-chart').innerHTML, /Three-pass range: <strong>0–0<\/strong> out of 60/);
  assert.match(ui.get('repeat-flips').innerHTML, /No reviews had valid answers in all three passes/);
  assert.match(ui.get('repeat-flips').innerHTML, /unavailable \(0 shared-valid reviews\)/);
  assert.doesNotMatch(ui.get('repeat-flips').innerHTML, /0 \/ 0 changed/);
});

test('optional absence preserves Jev while malformed or failed feeds fail visibly', async () => {
  const absent = await render(null, 404, 'jev-fixture');
  assert.match(absent.get('repeat-results').innerHTML, /jev-fixture/);
  assert.doesNotMatch(absent.get('repeat-results').innerHTML, /anyjev-qwen06-generated-fresh-three/);
  assert.doesNotMatch(absent.get('repeat-results').innerHTML, /could not be loaded/);
  const variants = [
    [{...feed, schema: 'wrong'}, 200],
    [{...feed, configuration: 'anyjev-native-fixture'}, 200],
    [{...feed, completedConditions: 0}, 200],
    [{...feed, passes: {...feed.passes, fresh1: {P0: {...feed.passes.fresh1.P0,
      score: {...feed.passes.fresh1.P0.score, denominator: 59}}}}}, 200],
    [null, 500]
  ];
  for (const [payload, status] of variants) {
    const ui = await render(payload, status);
    assert.match(ui.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  }
});
