const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const casesUi = require('../public-site/extended-cases.js');

const site = path.resolve(__dirname, '../public-site');
const additional = JSON.parse(fs.readFileSync(path.join(site, 'additional-cases-v1.json')));
const extended = JSON.parse(fs.readFileSync(path.join(site, 'extended-cases-v1.json')));

test('77 additional identities have 60 positions each, separate from the frozen extension', () => {
  assert.equal(casesUi.validate(additional), additional);
  assert.equal(casesUi.validate(extended), extended);
  assert.equal(additional.runs.length, 77);
  assert.equal(extended.runs.length, 637);
  assert.equal(new Set(additional.runs.map(run => run.runId)).size, 77);
  assert.ok(additional.runs.every(run => run.cases.length === 60));
  assert.equal(casesUi.view(additional, 'sonnet55-low-fresh-matched3-batch10-v2--pass1-p0').cases.length, 60);
  assert.equal(casesUi.view(additional, 'clef-native-fresh1-p0').cases.length, 60);
  assert.equal(casesUi.view(additional, 'solar-decide-native-fresh3-p2', {mode:'unanswered'}).cases[0].id, 'DEV-009');
  assert.equal(casesUi.view(additional, 'clef-flash-openrouter-native-fresh3-p2', {mode:'unanswered'}).cases[0].id, 'DEV-039');
});

test('A/B comparison on additional runs uses exact saved answers and provisional reference', () => {
  const a = 'liquid-d1-native-fresh1-p0';
  const b = 'tev1-4b-native-fresh1-p0';
  const paired = casesUi.view(additional, a, {compareRunId:b});
  assert.equal(paired.compareRun.runId, b);
  assert.equal(paired.cases.length, 60);
  assert.ok(paired.cases.every(row => row.reference && row.prediction && row.comparisonPrediction));
  assert.equal(casesUi.view(additional, a, {compareRunId:b, mode:'between'}).cases.length,
    paired.cases.filter(row => row.outcomeDiffers).length);
});

test('case loader caches each source feed by URL without crossing run identities', async () => {
  const requested = [];
  const original = global.fetch;
  global.fetch = async url => {
    requested.push(url);
    return {ok:true,json:async () => url.includes('additional') ? additional : extended};
  };
  try {
    const [a,b,aAgain] = await Promise.all([
      casesUi.load('./additional-cases-v1.json'),
      casesUi.load('./extended-cases-v1.json'),
      casesUi.load('./additional-cases-v1.json')
    ]);
    assert.equal(a, additional);
    assert.equal(b, extended);
    assert.equal(aAgain, additional);
    assert.deepEqual(requested.sort(), ['./additional-cases-v1.json', './extended-cases-v1.json']);
  } finally {
    global.fetch = original;
  }
});

test('run inspector chooses the bound feed for a supplemental run', async () => {
  const app = fs.readFileSync(path.join(site, 'app.js'), 'utf8').replace(
    '  init();\n})();', '  globalThis.__inspect = {state,renderCases};\n})();');
  const calls = [];
  const panel = {innerHTML:''};
  const context = {document:{querySelector:selector => selector === '#case-panel' ? panel : null}, URL,
    BenchmarkExtendedCases:{load:async url => {calls.push(['load',url]);return additional;},
      render:(target,feed,id) => calls.push(['render',feed.schema,id])}};
  vm.runInNewContext(app, context);
  const run = JSON.parse(fs.readFileSync(path.join(site, 'supplemental-decision-runs-v1.json')))
    .runs.find(item => item.id === 'perplexity-decider-native-fresh2-p1');
  context.__inspect.state.data = {cases:[]};
  context.__inspect.state.selectedId = run.id;
  context.__inspect.renderCases(run);
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(calls, [['load','./additional-cases-v1.json'],
    ['render','additional-cases-v1',run.id]]);
});
