const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const casesUi = require('../public-site/extended-cases.js');

const site = path.resolve(__dirname, '../public-site');
const additional = JSON.parse(fs.readFileSync(path.join(site, 'additional-cases-v1.json')));
const extended = JSON.parse(fs.readFileSync(path.join(site, 'extended-cases-v1.json')));
const base = JSON.parse(fs.readFileSync(path.join(site, 'data-provider-errors-v1.json')));

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

test('unified comparison reconciles all 1,004 runs without mutating saved feeds', () => {
  const firstExtended = extended.runs[0];
  const firstAdditional = additional.runs[0];
  const unified = casesUi.combine(base, extended, additional);
  assert.equal(unified.runs.length, 1004);
  assert.equal(unified.coverage.caseRuns, 1004);
  assert.equal(new Set(unified.runs.map(run => run.runId)).size, 1004);
  assert.equal(unified.runs.every(run => run.cases.length === 60), true);
  assert.equal(extended.runs[0], firstExtended);
  assert.equal(additional.runs[0], firstAdditional);
  const baseRun = base.runs.find(run => run.id === 'qwen3-0.6b-sdk-thinking-on');
  const invalid = casesUi.view(unified, baseRun.id, {query:'DEV-001'}).cases[0];
  assert.equal(invalid.status, 'invalid_output');
  assert.equal(invalid.prediction, null);
  assert.equal(unified.runs.find(run => run.runId === baseRun.id).sourceRecordUrl, baseRun.evidenceUrl);
  for (const [a,b] of [
    [base.runs[0].id, extended.runs[0].runId],
    [extended.runs[0].runId, additional.runs[0].runId],
    [additional.runs[0].runId, base.runs[0].id]
  ]) {
    const result = casesUi.view(unified, a, {compareRunId:b, query:'DEV-029'});
    assert.equal(result.cases.length, 1);
    assert.equal(result.compareRun.runId, b);
    assert.equal(result.cases[0].id, 'DEV-029');
    assert.ok(result.cases[0].reference);
    assert.ok(result.run.sourceRecordUrl.startsWith('https://github.com/'));
    assert.ok(result.compareRun.sourceRecordUrl.startsWith('https://github.com/'));
  }
});

test('unified comparison fails closed on reference drift or repeated run identity', () => {
  const changed = structuredClone(additional);
  changed.cases[0].reference.sentiment = 'negative';
  assert.throws(() => casesUi.combine(base, extended, changed), /disagree/);
  const repeated = structuredClone(additional);
  repeated.runs[0].runId = extended.runs[0].runId;
  assert.throws(() => casesUi.combine(base, extended, repeated), /repeated run identity/);
  const sourceDrift = structuredClone(base);
  sourceDrift.cases[0].prediction = {sentiment:'positive'};
  assert.throws(() => casesUi.combine(sourceDrift, extended, additional), /invalid four-field answer/);
});

test('A/B names distinct saved failures as status differences', () => {
  const a = 'qwen3-0.6b-sdk-thinking-on';
  const b = 'extended-cloudflare-clef-direct-fresh1-p2';
  const unified = casesUi.combine(base, extended, additional);
  const pair = {...unified, runs:unified.runs.filter(run => run.runId === a || run.runId === b)};
  const row = casesUi.view(pair, a, {compareRunId:b, query:'DEV-001'}).cases[0];
  assert.equal(row.status, 'invalid_output');
  assert.equal(row.comparisonStatus, 'unknown_outcome');
  assert.equal(row.outcomeDiffers, true);
  class Node {
    constructor(tag) {this.tag = tag; this.children = []; this.value = ''; this.textContent = '';}
    append(...children) {
      this.children.push(...children);
      if (this.tag === 'select' && children.length && this.children.length === children.length) this.value = children[0].value;
    }
    replaceChildren(...children) {this.children = []; this.value = ''; this.append(...children);}
    get options() {return this.children.filter(child => child.tag === 'option');}
    setAttribute() {}
    addEventListener() {}
  }
  const originalDocument = global.document;
  const originalLocation = global.location;
  try {
    global.document = {createElement:tag => new Node(tag)};
    global.location = {href:`https://example.test/?compareRun=${encodeURIComponent(b)}&case=DEV-001`};
    const panel = new Node('div');
    casesUi.render(panel, pair, a);
    const summaries = [];
    const walk = node => {if (node.tag === 'summary') summaries.push(node.textContent);
      node.children.forEach(walk);};
    walk(panel);
    assert.ok(summaries.includes('DEV-001 · A/B saved statuses differ'));
  } finally {
    global.document = originalDocument;
    global.location = originalLocation;
  }
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

test('run inspector loads both bound feeds once for any saved run', async () => {
  const app = fs.readFileSync(path.join(site, 'app.js'), 'utf8').replace(
    '  init();\n})();', '  globalThis.__inspect = {state,renderCases};\n})();');
  const calls = [];
  const panel = {innerHTML:''};
  const context = {document:{querySelector:selector => selector === '#case-panel' ? panel : null}, URL,
    BenchmarkExtendedCases:{load:async url => {calls.push(['load',url]);
      return url.includes('additional') ? additional : extended;},
      combine:() => {calls.push(['combine']); return {schema:'unified-cases-v1'};},
      render:(target,feed,id) => calls.push(['render',feed.schema,id])}};
  vm.runInNewContext(app, context);
  const run = JSON.parse(fs.readFileSync(path.join(site, 'supplemental-decision-runs-v1.json')))
    .runs.find(item => item.id === 'perplexity-decider-native-fresh2-p1');
  context.__inspect.state.data = {cases:[]};
  context.__inspect.state.selectedId = run.id;
  context.__inspect.renderCases(run);
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(calls, [['load','./extended-cases-v1.json'],
    ['load','./additional-cases-v1.json'], ['combine'],
    ['render','unified-cases-v1',run.id]]);
});

test('a failed companion feed leaves the selected run’s own saved cases available', async () => {
  const app = fs.readFileSync(path.join(site, 'app.js'), 'utf8').replace(
    '  init();\n})();', '  globalThis.__inspect = {state,renderCases};\n})();');
  const calls = [];
  const panel = {innerHTML:''};
  const context = {document:{querySelector:selector => selector === '#case-panel' ? panel : null},
    URL, console:{error:()=>{}}, BenchmarkExtendedCases:{
      load:url => {
        calls.push(['load',url]);
        return url.includes('extended') ? Promise.reject(new Error('request failed')) : Promise.resolve(additional);
      },
      combine:() => {throw new Error('unreachable');},
      render:(target,feed,id) => calls.push(['render',feed.schema,id])
    }};
  vm.runInNewContext(app, context);
  const run = JSON.parse(fs.readFileSync(path.join(site, 'supplemental-decision-runs-v1.json')))
    .runs.find(item => item.id === 'perplexity-decider-native-fresh2-p1');
  context.__inspect.state.data = {cases:[]};
  context.__inspect.state.selectedId = run.id;
  context.__inspect.renderCases(run);
  await new Promise(resolve => setImmediate(resolve));
  assert.deepEqual(calls, [['load','./extended-cases-v1.json'],
    ['load','./additional-cases-v1.json'], ['load','./additional-cases-v1.json'],
    ['render','additional-cases-v1',run.id]]);
});
