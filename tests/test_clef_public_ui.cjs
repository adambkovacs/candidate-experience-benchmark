const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const site = path.resolve(__dirname, '../public-site');
const app = fs.readFileSync(path.join(site, 'app.js'), 'utf8');
const report = JSON.parse(fs.readFileSync(path.join(site, 'clef-findings.json'), 'utf8'));
const source = app.replace('  init();\n})();', '  globalThis.__clef = {clefFirstPassRuns,renderClefFirstPass};\n})();');
assert.notEqual(source, app);

function adapter(payload) {
  const panel = { innerHTML: '' };
  const context = { document: { querySelector: id => id === '#clef-first-pass-results' ? panel : null }, URL };
  vm.runInNewContext(source, context, { filename: 'app.js' });
  const runs = context.__clef.clefFirstPassRuns(payload);
  context.__clef.renderClefFirstPass(runs, payload);
  return { runs, html: panel.innerHTML };
}

test('two closed native P0 rows keep exact counts, records and source links', () => {
  const { runs, html } = adapter(report);
  assert.equal(runs.length, 2);
  assert.deepEqual(Array.from(runs, run => run.metrics.all_four), [53, 45]);
  assert.deepEqual(Array.from(runs, run => run.metrics.sentiment), [55, 50]);
  assert.ok(runs.every(run => run.condition === 'P0' && run.complete && run.records === 60 && run.valid === 60));
  assert.ok(runs.every(run => run.sourceOnlyDetails && run.sourceRecordsUrl.endsWith('/development/records.jsonl')));
  assert.ok(runs.every(run => /^[0-9a-f]{64}$/.test(run.sourceRecordSha256)));
  assert.match(html, /53<small>\/60/);
  assert.match(html, /45<small>\/60/);
  assert.match(html, /At least one label differed between the models on <strong>12<\/strong> of the same 60 comments/);
});

test('price estimates, unknown bounds, tokens and timing remain distinct', () => {
  const { runs, html } = adapter(report);
  assert.deepEqual(Array.from(runs, run => run.tokens.input), [132694, 132694]);
  assert.deepEqual(Array.from(runs, run => run.tokens.output), [0, 0]);
  assert.deepEqual(Array.from(runs, run => run.cost.estimatedUsd), [0.03184656, 0.01194246]);
  assert.deepEqual(Array.from(runs, run => run.cost.unknownUpperBoundUsd), [0.94374, 0.35394]);
  assert.ok(runs.every(run => run.cost.actualUsd === null && run.timing.inferenceSeconds === null));
  assert.match(html, /Observed charge unavailable/);
  assert.doesNotMatch(html, /inference speed|provider billed/);
});

test('partial or changed source evidence cannot become a scored Clef row', () => {
  const changed = structuredClone(report);
  changed.models.clef.records = 59;
  assert.equal(adapter(changed).runs.length, 0);
  assert.match(adapter(changed).html, /unavailable from the saved evidence/);
  const changedHash = structuredClone(report);
  changedHash.sourceSha256['results/clef-native-v1/clef/fresh1/P0/development/records.jsonl'] = 'bad';
  assert.equal(adapter(changedHash).runs.length, 0);
  const changedPaired = structuredClone(report);
  changedPaired.paired.allFour.correct_correct = 42;
  assert.equal(adapter(changedPaired).runs.length, 0);
});

test('public section links source, describes one pass, and separates provider confidence', () => {
  const html = fs.readFileSync(path.join(site, 'explore.html'), 'utf8');
  assert.match(html, /id="clef-first-pass-results"/);
  assert.match(html, /one closed P0 pass/);
  assert.match(html, /provider's separate "confidence" field/);
  assert.match(html, /clef-findings\.json/);
  assert.match(html, /CLEF_FINDINGS_2026-10-02\.md/);
});
