const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const site = path.join(__dirname, '..', 'public-site');
const report = JSON.parse(fs.readFileSync(path.join(site, 'sonnet55-fresh-matched3.json'), 'utf8'));
const appSource = fs.readFileSync(path.join(site, 'app.js'), 'utf8');
const repeatSource = fs.readFileSync(path.join(site, 'repeats.js'), 'utf8');

function appAdapter(payload) {
  const source = appSource.replace('  init();\n})();', '  globalThis.__sonnet = {sonnet55FirstPassRuns};\n})();');
  assert.notEqual(source, appSource);
  const context = {document: {}, URL};
  vm.runInNewContext(source, context, {filename: 'app.js'});
  return context.__sonnet.sonnet55FirstPassRuns(payload);
}

test('main explorer admits only closed 60-record Sonnet pass-one development cells', () => {
  const runs = appAdapter(report);
  const expected = report.efforts.flatMap(effort => report.conditionOrder.filter(condition => {
    const dev = report.cells[effort].pass1[condition].development;
    return dev.state === 'complete' && dev.recordCount === 60 && dev.score?.denominator === 60;
  }));
  assert.equal(runs.length, expected.length);
  assert.equal(runs.length, 12);
  assert.ok(runs.every(run => run.complete && run.records === 60 && run.valid === 60));
  assert.ok(runs.every(run => run.evidenceUrl.endsWith('sonnet55-fresh-matched3.json')));
  const low = runs.find(run => run.id === 'sonnet55-low-fresh-matched3-batch10-v2--pass1-p0');
  assert.equal(low.metrics.all_four, report.cells.low.pass1.P0.development.score.allFour);
  assert.equal(low.timing.requests, 6);
  assert.equal(low.tokens.cacheWrite, report.cells.low.pass1.P0.development.usage.tokens.cache_creation_input_tokens);
  assert.match(low.sourceRecordsUrl, /public-site\/sonnet55-fresh-matched3-evidence\/evidence\/results\/repeatability-v1/);
  assert.equal(low.cost.estimateKind, 'calculated_api_equivalent');
  assert.match(low.cost.sourceUrl, /^https:\/\//);

  const changed = structuredClone(report);
  changed.cells.low.pass1.P1.development.state = 'running_or_ambiguous';
  assert.equal(appAdapter(changed).length, runs.length - 1);
  changed.cells.low.pass1.P1.development.state = 'complete';
  changed.cells.low.pass1.P1.development.score.valid = 59;
  changed.cells.low.pass1.P1.development.score.outcomes.valid = 59;
  changed.cells.low.pass1.P1.development.score.outcomes.invalid_output = 1;
  assert.equal(appAdapter(changed).length, runs.length);
  assert.equal(appAdapter(changed).find(run => run.condition === 'P1' && run.effort === 'low').valid, 59);
});

test('source-only Sonnet detail links recorded outputs without claiming comments are absent', () => {
  const panel = {innerHTML:''};
  const document = {querySelector(selector) {return selector === '#case-panel' ? panel : null;}};
  const source = appSource.replace('  init();\n})();', '  globalThis.__sonnet = {state,renderCases,sonnet55FirstPassRuns};\n})();');
  const context = {document, URL};
  vm.runInNewContext(source, context, {filename:'app.js'});
  context.__sonnet.state.data = {cases:[]};
  context.__sonnet.renderCases(context.__sonnet.sonnet55FirstPassRuns(report)[0]);
  assert.match(panel.innerHTML, /has not loaded individual predictions/);
  assert.match(panel.innerHTML, /Read the individual source records/);
  assert.doesNotMatch(panel.innerHTML, /No individual comments are available/);
});

test('Antigravity roster display explains the blocked route without changing the feed', () => {
  const list={innerHTML:''},count={textContent:''},search={value:''};
  const document={querySelector(selector) {
    return {'#roster-list':list,'#roster-count':count,'#roster-search':search}[selector] || null;
  }};
  const source=appSource.replace('  init();\n})();', '  globalThis.__roster = {state,renderRoster};\n})();');
  const context={document,URL};
  vm.runInNewContext(source,context,{filename:'app.js'});
  const item={id:'antigravity-gemini-3.7-flash-low-native-observed-batch10',
    parentBaselineId:'antigravity-gemini-3.7-flash-low-native-observed-batch10',
    disposition:'scheduled',reason:'Selected for prompt evaluation.'};
  context.__roster.state.data={runs:[],roster:[item]};
  context.__roster.renderRoster();
  assert.match(list.innerHTML,/blocked after P0/);
  assert.match(list.innerHTML,/Coverage audit/);
  assert.doesNotMatch(list.innerHTML,/Selected for prompt evaluation/);
  assert.equal(item.disposition,'scheduled');
});

async function renderRepeats(sonnetPayload, status = 200) {
  const ids = ['repeat-results', 'repeat-config', 'repeat-field', 'repeat-condition',
    'repeat-condition-label', 'repeat-interpretation', 'repeat-lead', 'repeat-chart',
    'repeat-delta-title', 'repeat-delta-intro', 'repeat-deltas', 'repeat-flips',
    'repeat-usage-body', 'repeat-summary'];
  const elements = new Map(ids.map(id => [id, {innerHTML: '', textContent: '', value: '',
    addEventListener(type, fn) { this[type] = fn; }}]));
  const document = {getElementById(id) { return elements.get(id); }};
  const fallback = {configuration:'existing',displayName:'Existing repeat result',method:'native-output-stability',
    conditionOrder:['P0'],passOrder:['original','repeat2','repeat3'],denominator:60,
    plannedConditions:3,completedConditions:1,passes:{original:{P0:{completionStatus:'complete',
      score:{allFour:50,valid:60,fields:{sentiment:50}},usage:{requestCount:60}}},repeat2:{},repeat3:{}},
    threePassSummary:{},pairwiseFlips:[],withinPassPromptDeltas:[],missingPasses:[]};
  const fetch = async url => url === './sonnet55-fresh-matched3.json'
    ? {ok: status === 200, status, json: async () => sonnetPayload}
    : {ok: true, status: 200, json: async () => url === './typesafe-repeats.json' && status === 404 ? {series:[fallback]} : {series: []}};
  elements.get('repeat-config').value = status === 404 ? 'existing' : 'sonnet55-low-fresh-matched3-batch10-v2';
  elements.get('repeat-field').value = 'allFour';
  elements.get('repeat-condition').value = 'P0';
  vm.runInNewContext(repeatSource, {document, fetch, console}, {filename:'repeats.js'});
  await new Promise(resolve => setImmediate(resolve));
  return {get: id => elements.get(id), select: effort => {
    elements.get('repeat-config').value = `sonnet55-${effort}-fresh-matched3-batch10-v2`;
    elements.get('repeat-config').change();
  }};
}

test('repeat explorer shows all four efforts and nine cells per effort without scoring unfinished work', async () => {
  assert.equal(report.completedCells, 36);
  const ui = await renderRepeats(report);
  for (const effort of report.efforts) {
    assert.match(ui.get('repeat-results').innerHTML, new RegExp(`sonnet55-${effort}-fresh-matched3-batch10-v2`));
    ui.select(effort);
    assert.equal((ui.get('repeat-chart').innerHTML.match(/class="repeat-bar-row"/g) || []).length, 9);
    const complete = report.passOrder.flatMap(pass => report.conditionOrder.filter(condition =>
      report.cells[effort][pass][condition].development.state === 'complete')).length;
    assert.match(ui.get('repeat-summary').textContent, new RegExp(`${complete} of 9`));
    assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter /g) || []).length, complete);
    assert.match(ui.get('repeat-interpretation').innerHTML, /36 planned development phases/);
  }
  ui.select('low');
  assert.match(ui.get('repeat-lead').textContent, /not replayed/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /API-equivalent calculation from saved usage/);
  assert.match(ui.get('repeat-usage-body').innerHTML, /Public rate ↗/);
  assert.match(ui.get('repeat-flips').innerHTML, /Pairwise changes between completed passes are listed below/);
  assert.match(ui.get('repeat-flips').innerHTML, /Pass 1 to Pass 2/);
  assert.doesNotMatch(ui.get('repeat-flips').innerHTML, /unavailable until all passes finish/);
});

test('closed Sonnet scores retain missing usage without claiming complete tokens or price', async () => {
  const partial = structuredClone(report);
  const one = partial.cells.low.pass1.P0.development;
  one.usage.unpricedRequests = 1;
  one.usage.calculatedApiEquivalentUsd = null;
  one.usage.cliListPriceEstimateUsd = null;
  const all = partial.cells.low.pass1.P1.development;
  all.usage.unpricedRequests = all.usage.requestCount;
  all.usage.calculatedApiEquivalentUsd = null;
  all.usage.cliListPriceEstimateUsd = null;
  all.usage.tokens = {input_tokens:0,output_tokens:0};
  const runs = appAdapter(partial);
  const p0 = runs.find(run => run.effort === 'low' && run.condition === 'P0');
  const p1 = runs.find(run => run.effort === 'low' && run.condition === 'P1');
  assert.equal(p0.complete, true);
  assert.equal(p0.tokens.reportedRequests, p0.tokens.totalRequests - 1);
  assert.equal(p0.tokens.complete, false);
  assert.equal(p0.cost.estimatedUsd, null);
  assert.equal(p1.complete, true);
  assert.equal(p1.tokens.reportedRequests, 0);
  assert.equal(p1.tokens.input, null);
  assert.equal(p1.cost.estimatedUsd, null);
  const ui = await renderRepeats(partial);
  const usage = ui.get('repeat-usage-body').innerHTML;
  assert.match(usage, /Known usage for 5 of 6 requests/);
  assert.match(usage, /1 request without priced usage; full estimate unknown/);
  assert.match(usage, /6 requests without priced usage; full estimate unknown/);
  assert.equal((ui.get('repeat-chart').innerHTML.match(/<meter /g) || []).length, 9);
});

test('unfinished Sonnet cells keep stopped, running and untouched states distinct', async () => {
  const partial = structuredClone(report);
  const stopped = partial.cells.low.pass1.P0.development;
  stopped.state = 'stopped';
  stopped.score = null;
  stopped.recordCount = 37;
  stopped.requestCount = 4;
  stopped.usage = {requestCount:4,unpricedRequests:0,tokens:{input_tokens:1200,output_tokens:300},requestSecondsTotal:8.2,
    calculatedApiEquivalentUsd:0.04};
  const running = partial.cells.low.pass2.P0.development;
  running.state = 'running_or_ambiguous';
  running.score = null;
  const untouched = partial.cells.low.pass3.P0.development;
  untouched.state = 'not_started';
  untouched.score = null;
  const ui = await renderRepeats(partial);
  const chart = ui.get('repeat-chart').innerHTML;
  const usage = ui.get('repeat-usage-body').innerHTML;
  assert.match(chart, /Stopped; unscored; 37 saved of 60/);
  assert.match(chart, /In progress or outcome unknown; no score/);
  assert.match(chart, /Not started/);
  assert.equal((chart.match(/<meter /g) || []).length, 6);
  assert.match(usage, /Pass 1 \(stopped; unscored\)/);
  assert.match(usage, /37 saved records of 60/);
  assert.match(usage, /Known partial usage for 4 priced requests; not a subscription charge/);
  assert.match(usage, /Pass 3 \(not started\)/);
});

test('first-request timeout has unknown cost even when the report sums priced usage as zero', async () => {
  const timeout = structuredClone(report);
  const dev = timeout.cells.low.pass1.P0.development;
  dev.state = 'stopped';
  dev.score = null;
  dev.recordCount = 0;
  dev.requestCount = 1;
  dev.usage = {requestCount:1,unpricedRequests:1,calculatedApiEquivalentUsd:'0',
    tokens:{input_tokens:0,output_tokens:0}};
  const ui = await renderRepeats(timeout);
  const row = ui.get('repeat-usage-body').innerHTML.match(/<tr><th scope="row">P0<\/th><td>Pass 1 \(stopped; unscored\)<\/td>[\s\S]*?<\/tr>/)?.[0];
  assert.ok(row);
  assert.match(row, /No priced request usage; attempted cost unknown/);
  assert.doesNotMatch(row, /\$0\.00/);
});

test('missing optional Sonnet report preserves previously available repeat explorer series', async () => {
  const ui = await renderRepeats(null, 404);
  assert.doesNotMatch(ui.get('repeat-results').innerHTML, /Repeat results could not be loaded/);
});
