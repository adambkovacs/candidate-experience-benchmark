const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'public-site', 'app.js'), 'utf8');

test('a pending optional price fetch resolves without delaying core data', async () => {
  const instrumented = source.replace('  init();\n})();',
    '  globalThis.__optionalPricing = optionalPricing;\n})();');
  const context = {document: {}, fetch: () => new Promise(() => {}),
    setTimeout: callback => {setImmediate(callback); return 1;}, clearTimeout() {}};
  vm.runInNewContext(instrumented, context);
  assert.equal(await context.__optionalPricing(), null);
});

test('historical subscription detail keeps charge unknown and links public rate', () => {
  const summary = {innerHTML: ''};
  const document = {querySelector(selector) {
    return selector === '#usage-summary' ? summary : null;
  }};
  const instrumented = source.replace('  init();\n})();',
    '  globalThis.__prices = {state,renderUsage,costRows,costSummary};\n})();');
  assert.notEqual(instrumented, source);
  const context = {document, URL};
  vm.runInNewContext(instrumented, context);
  const run = {id: 'fable51-high-phase2-batch10-p0', model: 'claude-fable-5-1',
    surface: 'Claude subscription', condition: 'P0', tokens: {reportedRequests: 6, totalRequests: 6},
    cost: {actualUsd: null, estimatedUsd: null}, timing: {inferenceSeconds: null}};
  const entry = {model: run.model, tokens: {input: 12, cacheRead: 19680,
    cacheWrite: 6451, output: 9454, reasoningOutput: 5705}, usageStatus: 'complete',
    estimateUsd: '0.60676', estimateStatus: 'complete',
    rate: {checkedDate: '2026-10-02',
      sourceUrl: 'https://platform.claude.com/docs/en/models/fable-5-1/overview'}};
  context.__prices.state.pricing = {runs: {[run.id]: entry}};
  context.__prices.renderUsage(run);
  assert.match(summary.innerHTML, /Cache read.*19,680/s);
  assert.match(summary.innerHTML, /Cache write.*6,451/s);
  assert.match(summary.innerHTML, /Reasoning.*5,705/s);
  assert.match(summary.innerHTML, /At API rates.*\$0\.6068†/s);
  assert.doesNotMatch(summary.innerHTML, /Actual subscription charge and quota use are unknown/);
  assert.match(summary.innerHTML, /https:\/\/platform\.claude\.com\/docs\/en\/models\/fable-5-1\/overview/);
  assert.equal(context.__prices.costSummary(run), '$0.6068†');
});

test('unpriced subscription run shows missing estimate reason', () => {
  const context = {document: {querySelector() { return null; }}, URL};
  vm.runInNewContext(source.replace('  init();\n})();',
    '  globalThis.__prices = {state,costRows};\n})();'), context);
  const run = {id: 'missing', model: 'gpt-6-sol', surface: 'Codex subscription',
    cost: {actualUsd: null}};
  context.__prices.state.pricing = {runs: {missing: {model: run.model,
    estimateUsd: null, estimateStatus: 'cache_write_tokens_unreported',
    rate: {checkedDate: '2026-10-02',
      sourceUrl: 'https://developers.openai.com/api/docs/models/gpt-6-sol'}}}};
  const html = context.__prices.costRows(run.cost, run);
  assert.match(html, /At API rates.*Unknown<\/dd>/s);
  assert.match(html, /cache write tokens unreported/);
  assert.match(html, /Model price source/);
});

test('cost markers follow the feed: charge plain, estimate with a dagger, missing figure says so without one', () => {
  const context = {document: {querySelector() { return null; }}, URL};
  vm.runInNewContext(source.replace('  init();\n})();',
    '  globalThis.__prices = {state,costSummary,applyJevFindings};\n})();'), context);
  const {state, costSummary, applyJevFindings} = context.__prices;
  state.pricing = {runs: {'priced-missing': {model: 'gpt-6-sol', estimateUsd: null, estimateStatus: 'cache_write_tokens_unreported'}}};
  assert.equal(costSummary({id: 'charged', model: 'upstage/solar-decide', cost: {knownUsd: 0.022067}}), '$0.0221');
  // Standalone estimate branch: an API-rate figure carried by the feed itself keeps its dagger.
  assert.equal(costSummary({id: 'estimated', model: 'jev-1.13.0', cost: {estimatedUsd: 0.00589092}}), '$0.0059†');
  assert.equal(costSummary({id: 'priced-missing', model: 'gpt-6-sol', surface: 'Codex subscription', cost: {}}), 'Cost unknown');
  assert.equal(costSummary({id: 'bare', model: 'x', cost: {}}), 'Cost unknown');
  // The Jev guard: a fixed catalog row is left alone; a failed findings feed gives route and cost unknown, never the catalog label.
  const fixed = {id: 'extended-typesafe-jev113-native-prompts-fresh1-p0', surface: 'OpenRouter native Choice', provider: 'TypeSafe', cost: {knownUsd: 0.00589092, estimatedUsd: null}};
  const stale = {id: 'extended-typesafe-jev113-native-prompts-fresh2-p0', surface: 'TypeSafe native Choice API', provider: 'TypeSafe', cost: {knownUsd: null, estimatedUsd: 0.0058}};
  applyJevFindings([fixed, stale], null);
  assert.equal(fixed.surface, 'OpenRouter native Choice');
  assert.equal(fixed.provider, 'TypeSafe');
  assert.equal(costSummary(fixed), '$0.0059');
  assert.equal(stale.surface, 'route unknown');
  assert.equal(costSummary(stale), 'Cost unknown');
});
