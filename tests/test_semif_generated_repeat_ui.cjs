const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'public-site', 'repeats.js'), 'utf8');
const feed = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'public-site', 'semif-generated-repeats.json'), 'utf8'));
const url = './semif-generated-repeats.json';
const ids = ['repeat-results', 'repeat-config', 'repeat-field', 'repeat-condition',
  'repeat-condition-label', 'repeat-interpretation', 'repeat-lead', 'repeat-chart',
  'repeat-delta-title', 'repeat-delta-intro', 'repeat-deltas', 'repeat-flips', 'repeat-usage-body'];

async function render(payload = feed, status = 200, selected = 'semif-generated-fresh-v1') {
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
      : {series: []}};
  };
  elements.get('repeat-config').value = selected;
  elements.get('repeat-field').value = 'allFour';
  elements.get('repeat-condition').value = 'P0';
  const document = {getElementById(id) { return elements.get(id); }};
  vm.runInNewContext(source, {document, fetch, console}, {filename: 'repeats.js'});
  await new Promise(resolve => setImmediate(resolve));
  return {get: id => elements.get(id), requested,
    field(value) { elements.get('repeat-field').value = value; elements.get('repeat-field').change(); },
    condition(value) { elements.get('repeat-condition').value = value; elements.get('repeat-condition').change(); }};
}

test('SemIf generated six closed phases display two-pass scores, flips and usage', async () => {
  const ui = await render();
  assert.equal(ui.requested.filter(name => name === url).length, 1);
  assert.match(ui.get('repeat-results').innerHTML, /<option value="jev-fixture">Jev<\/option>/);
  assert.ok(ui.get('repeat-results').innerHTML.indexOf('jev-fixture') <
    ui.get('repeat-results').innerHTML.indexOf('semif-generated-fresh-v1'));
  assert.match(ui.get('repeat-lead').textContent,
    new RegExp(`${feed.series[0].completedConditions} of 9 planned prompt/pass combinations`));
  assert.match(ui.get('repeat-lead').textContent, /P0 Fresh pass 1: 52\/60 valid responses/);
  assert.match(ui.get('repeat-lead').textContent, /P1 Fresh pass 1: 38\/60 valid responses/);
  assert.match(ui.get('repeat-lead').textContent, /P2 Fresh pass 1: 58\/60 valid responses/);
  assert.match(ui.get('repeat-lead').textContent, /P0 Fresh pass 2: 52\/60 valid responses/);
  assert.match(ui.get('repeat-lead').textContent, /P1 Fresh pass 2: 38\/60 valid responses/);
  assert.match(ui.get('repeat-lead').textContent, /P2 Fresh pass 2: 58\/60 valid responses/);
  assert.match(ui.get('repeat-lead').textContent, /client-observed elapsed time, not isolated inference time/);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length,
    feed.series[0].completedConditions);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/value="35"[^>]*>35<\/meter>/g) || []).length, 2);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/value="26"[^>]*>26<\/meter>/g) || []).length, 2);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/value="43"[^>]*>43<\/meter>/g) || []).length, 2);
  assert.match(ui.get('repeat-chart').innerHTML, /Three-pass range unavailable until all passes finish/);
  assert.match(ui.get('repeat-deltas').innerHTML, /\+8/);
  assert.match(ui.get('repeat-deltas').innerHTML, /-9/);
  assert.match(ui.get('repeat-deltas').innerHTML, /2 \/ 37 changed; 37 shared valid of 60; 23 excluded/);
  assert.match(ui.get('repeat-deltas').innerHTML, /6 \/ 52 changed; 52 shared valid of 60; 8 excluded/);
  assert.match(ui.get('repeat-flips').innerHTML, /Three-pass changes are unavailable/);
  for (const [condition, denominator] of [['P0', 52], ['P1', 38], ['P2', 58]]) {
    ui.condition(condition);
    assert.match(ui.get('repeat-flips').innerHTML,
      new RegExp(`Fresh pass 1 to Fresh pass 2: 0 / ${denominator} changed`));
    assert.match(ui.get('repeat-flips').innerHTML, /Three-pass changes are unavailable/);
  }
  const usage = ui.get('repeat-usage-body').innerHTML;
  assert.match(usage, /96,930/);
  assert.match(usage, /4,680/);
  assert.match(usage, /616\.3/);
  assert.match(usage, /427\.3/);
  assert.match(usage, /107,550/);
  assert.match(usage, /8,070/);
  assert.match(usage, /742\.8/);
  assert.match(usage, /876\.3/);
  assert.match(usage, /162,930/);
  assert.match(usage, /3,204/);
  assert.match(usage, /506\.2/);
  assert.match(usage, /389\.9/);
  assert.match(usage, /Unavailable/);
  assert.doesNotMatch(usage, /\$0\.00/);
  ui.field('sentiment');
  assert.match(ui.get('repeat-chart').innerHTML, /value="46"[^>]*>46<\/meter>/);
  assert.match(ui.get('repeat-chart').innerHTML, /value="33"[^>]*>33<\/meter>/);
  assert.match(ui.get('repeat-chart').innerHTML, /value="51"[^>]*>51<\/meter>/);
});

test('an absent optional feed leaves the Jev default available', async () => {
  const ui = await render(null, 404, 'jev-fixture');
  assert.match(ui.get('repeat-results').innerHTML, /jev-fixture/);
  assert.doesNotMatch(ui.get('repeat-results').innerHTML, /semif-generated-fresh-v1/);
  assert.doesNotMatch(ui.get('repeat-results').innerHTML, /could not be loaded/);
});

test('malformed or server-failed SemIf feed fails visibly', async () => {
  const variants = [
    [{schema: 'wrong', series: feed.series}, 200],
    [{...feed, series: [{...feed.series[0], configuration: 'wrong'}]}, 200],
    [{...feed, series: [{...feed.series[0], completedConditions: feed.series[0].completedConditions + 1}]}, 200],
    [{...feed, series: [{...feed.series[0], passes: {
      ...feed.series[0].passes, fresh1: {P0: {...feed.series[0].passes.fresh1.P0,
        score: {...feed.series[0].passes.fresh1.P0.score, denominator: 59}}}}}]}, 200],
    [null, 500]
  ];
  for (const [payload, status] of variants) {
    const ui = await render(payload, status);
    assert.match(ui.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  }
});
