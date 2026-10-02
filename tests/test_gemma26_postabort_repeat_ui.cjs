const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const site = path.join(__dirname, '..', 'public-site');
const source = fs.readFileSync(path.join(site, 'repeats.js'), 'utf8');
const read = name => JSON.parse(fs.readFileSync(path.join(site, name), 'utf8'));
const first = read('gemma26-continuation-findings.json');
const second = read('gemma26-second-continuation-findings.json');
const latest = read('gemma26-postabort-findings.json');
const p2Repeat = read('gemma26-p2-repeat-findings.json');
const latestId = latest.seriesId;
const secondId = second.seriesId;
const firstId = first.seriesId;
const ids = ['repeat-results', 'repeat-config', 'repeat-field', 'repeat-condition',
  'repeat-condition-label', 'repeat-interpretation', 'repeat-summary', 'repeat-lead',
  'repeat-chart', 'repeat-delta-title', 'repeat-delta-intro', 'repeat-deltas',
  'repeat-flips', 'repeat-usage-body'];

async function render(postabort = latest, status = 200, selected = latestId,
  comparison = p2Repeat, comparisonStatus = 200) {
  const elements = new Map(ids.map(id => [id, {innerHTML: '', textContent: '', value: '',
    addEventListener(type, fn) { this[type] = fn; }}]));
  const document = {getElementById(id) { return elements.get(id); }};
  const fetch = async url => {
    const feed = {
      './gemma26-continuation-findings.json': first,
      './gemma26-second-continuation-findings.json': second,
      './gemma26-postabort-findings.json': postabort,
      './gemma26-p2-repeat-findings.json': comparison,
    }[url];
    if (url === './gemma26-postabort-findings.json')
      return {ok: status === 200, status, json: async () => feed};
    if (url === './gemma26-p2-repeat-findings.json')
      return {ok: comparisonStatus === 200, status: comparisonStatus, json: async () => feed};
    return feed ? {ok: true, status: 200, json: async () => feed}
      : {ok: true, status: 200, json: async () => ({series: []})};
  };
  elements.get('repeat-config').value = selected;
  elements.get('repeat-field').value = 'allFour';
  elements.get('repeat-condition').value = 'P2';
  vm.runInNewContext(source, {document, fetch, console}, {filename: 'repeats.js'});
  await new Promise(resolve => setImmediate(resolve));
  return {get: id => elements.get(id), select(value) {
    elements.get('repeat-config').value = value;
    elements.get('repeat-config').change();
  }};
}

test('latest Gemma composite has seven fixed-60 scores while older cutoffs remain selectable', async () => {
  const ui = await render();
  const options = ui.get('repeat-results').innerHTML;
  for (const id of [firstId, secondId, latestId])
    assert.ok(options.includes(`value="${id}"`));
  assert.match(options, /latest interrupted composite \(7 of 9\)/);
  assert.match(ui.get('repeat-summary').textContent, /7 of 9 phases/);
  assert.match(ui.get('repeat-summary').textContent, /56 of 60/);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter/g) || []).length, 7);
  assert.match(ui.get('repeat-chart').innerHTML, /56<small> \/ 60<\/small>/);
  assert.match(ui.get('repeat-chart').innerHTML, /Three-pass range: <strong>56–57<\/strong>/);
  assert.match(ui.get('repeat-flips').innerHTML, /2 \/ 57/);
  assert.match(ui.get('repeat-flips').innerHTML, /DEV-013/);
  assert.match(ui.get('repeat-flips').innerHTML, /DEV-059/);
  assert.match(ui.get('repeat-flips').innerHTML, /3 comments lack a valid answer/);
  assert.match(ui.get('repeat-summary').textContent, /57, 56 and 56/);
  assert.match(ui.get('repeat-interpretation').innerHTML, /gemma26-p2-repeat-findings\.json/);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/Not sent/g) || []).length, 2);
  assert.match(ui.get('repeat-lead').textContent, /DEV-005 and DEV-006/);
  assert.match(ui.get('repeat-lead').textContent, /never sent and have no scores/);
  assert.match(ui.get('repeat-interpretation').innerHTML, /gemma26-postabort-findings\.json/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /60 attempted<br><small>58 valid, 2 preserved service failures/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /\$0\.02230691 known/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /2 requests have unknown cost/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /149,117 reported/);
  ui.get('repeat-field').value = 'sentiment';
  ui.get('repeat-field').change();
  assert.match(ui.get('repeat-flips').innerHTML, /1 \/ 57/);
  assert.match(ui.get('repeat-flips').innerHTML, /DEV-013/);
  assert.doesNotMatch(ui.get('repeat-flips').innerHTML, /class="repeat-case-ids">DEV-059/);
  ui.get('repeat-field').value = 'allFour';
  ui.get('repeat-field').change();
  ui.select(secondId);
  assert.match(ui.get('repeat-summary').textContent, /6 of 9 phases/);
  assert.match(ui.get('repeat-chart').innerHTML, /55 unsent; no score/);
  ui.select(firstId);
  assert.match(ui.get('repeat-summary').textContent, /5 of 9 phases/);
});

test('optional missing feed preserves cutoff; malformed or failed latest feed fails visibly', async () => {
  const missingComparison = await render(latest, 200, latestId, null, 404);
  assert.match(missingComparison.get('repeat-flips').innerHTML, /comparison is unavailable/);
  const malformedComparison = await render(latest, 200, latestId,
    {...p2Repeat, allThreeSharedValid: {...p2Repeat.allThreeSharedValid, denominator: 60}});
  assert.match(malformedComparison.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  const absent = await render(null, 404, secondId);
  assert.match(absent.get('repeat-summary').textContent, /6 of 9 phases/);
  const failed = await render(null, 500, secondId);
  assert.match(failed.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  for (const payload of [
    {...latest, completedConditions: 8},
    {...latest, fresh3P2: {...latest.fresh3P2, score: {...latest.fresh3P2.score,
      outcomes: {...latest.fresh3P2.score.outcomes, service_error: 0}}}},
    {...latest, fresh3P0: {status: 'never_sent', score: {allFour: 60}}},
    {...latest, sourceBindings: [{path: 'private/ledger.json', sha256: 'a'.repeat(64)}]},
  ]) {
    const malformed = await render(payload);
    assert.match(malformed.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
  }
});
