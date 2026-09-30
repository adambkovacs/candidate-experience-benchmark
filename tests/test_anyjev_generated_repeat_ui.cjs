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
    field(value) { elements.get('repeat-field').value = value; elements.get('repeat-field').change(); },
    condition(value) { elements.get('repeat-condition').value = value; elements.get('repeat-condition').change(); }};
}

test('closed generated phases preserve invalid outcomes and fixed-60 scores', async () => {
  const ui = await render();
  assert.equal(ui.requested.filter(name => name === url).length, 1);
  const options = ui.get('repeat-results').innerHTML;
  assert.ok(options.indexOf('jev-fixture') < options.indexOf(feed.configuration));
  assert.match(options, /anyjev-native-fixture/);
  assert.match(options, /anyjev-qwen06-generated-fresh-three/);
  const lead = ui.get('repeat-lead').textContent;
  assert.match(lead, new RegExp(`${feed.completedConditions} of 9 full phases closed`));
  assert.match(lead, /Valid responses by pass 1\/2\/3/);
  for (const condition of feed.conditionOrder) {
    const counts = feed.passOrder.map(pass => feed.passes[pass][condition]?.completionStatus === 'complete'
      ? feed.passes[pass][condition].score.valid : 'pending');
    assert.ok(lead.includes(`${condition} ${counts.join(' / ')}`));
  }
  assert.doesNotMatch(lead, /pending/);
  assert.match(lead, /separate from native AnyJev/);
  assert.match(lead, /Counts and scores use all 60 reviews, including invalid outputs/);
  assert.doesNotMatch(lead, /parser|inference time|private tokenizer/);
  const limits = ui.get('repeat-interpretation').innerHTML;
  assert.match(limits, /^<details><summary>Protocol and measurement limits<\/summary>/);
  assert.doesNotMatch(limits, /^<details open/);
  assert.match(limits, /strict parser does not repair fenced JSON/);
  assert.match(limits, /When none qualify, stability cannot be assessed/);
  assert.match(limits, /historical generated observations are ineligible/);
  assert.match(limits, /private tokenizer/);
  assert.match(limits, /local hardware and electricity cost are unknown/);
  const chart = ui.get('repeat-chart').innerHTML;
  assert.match(chart, /value="0"[^>]*aria-label="P0 Fresh pass 1 All four decisions: 0 out of 60"/);
  assert.match(chart, /value="1"[^>]*aria-label="P2 Fresh pass 1 All four decisions: 1 out of 60"/);
  assert.match(chart, /<strong>0<small> \/ 60<\/small><\/strong>/);
  assert.equal((chart.match(/<meter/g) || []).length, feed.completedConditions);
  assert.match(chart, /Three-pass range: <strong>0–0<\/strong> out of 60/);
  assert.match(chart, /Three-pass range: <strong>1–1<\/strong> out of 60/);
  assert.doesNotMatch(chart, /Three-pass range unavailable/);
  assert.match(ui.get('repeat-deltas').innerHTML, /<td>0<\/td>/);
  assert.match(ui.get('repeat-deltas').innerHTML, /<td>\+1<\/td>/);
  assert.match(ui.get('repeat-deltas').innerHTML, /unavailable; none had answers in the required format in both conditions; 0 of 60 comparable; 60 excluded/);
  assert.match(ui.get('repeat-flips').innerHTML, /No comments had answers in the required format in all three passes/);
  assert.doesNotMatch(ui.get('repeat-flips').innerHTML, /0 \/ 0 changed/);
  ui.condition('P1');
  assert.match(ui.get('repeat-flips').innerHTML, /unavailable \(0 comments with answers in the required format in both passes\)/);
  ui.condition('P2');
  assert.match(ui.get('repeat-flips').innerHTML, /0 \/ 30 changed/);
  assert.match(ui.get('repeat-flips').innerHTML, /<strong>0 \/ 30<\/strong> comparable comments changed/);
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
  ui.field('sentiment');
  assert.match(ui.get('repeat-chart').innerHTML, /value="0"[^>]*aria-label="P0 Fresh pass 1 Sentiment: 0 out of 60"/);
});

test('an incomplete phase remains pending without a three-pass result', async () => {
  const payload = structuredClone(feed);
  delete payload.passes.fresh3.P0;
  payload.missingPasses.push({pass: 'fresh3', condition: 'P0', status: 'claimed_in_progress_or_interrupted'});
  payload.completedConditions -= 1;
  const ui = await render(payload);
  assert.match(ui.get('repeat-lead').textContent, /P0 0 \/ 0 \/ pending/);
  assert.match(ui.get('repeat-lead').textContent, /pending means no full score/);
  assert.match(ui.get('repeat-chart').innerHTML, /Three-pass range unavailable until all passes finish/);
  assert.match(ui.get('repeat-flips').innerHTML, /Three-pass changes are unavailable until all passes finish/);
  assert.match(ui.get('repeat-flips').innerHTML, /unavailable \(0 comments with answers in the required format in both passes\)/);
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
