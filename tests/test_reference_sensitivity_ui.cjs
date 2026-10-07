const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'public-site/reference-sensitivity.js'), 'utf8');
const publicBytes = fs.readFileSync(path.join(root, 'public-site/reference-sensitivity-v1.json'));
const findingsBytes = fs.readFileSync(path.join(root, 'results/reference-sensitivity-v1/findings.json'));
const data = JSON.parse(publicBytes);
const context = {
  document: {getElementById: () => null},
  location: {href: 'https://example.test/?cohort=decision&reviewSubset=testimonial&reviewField=sentiment&reviewSearch=other&reviewModel=abc#reference-sensitivity'},
  URL, console,
};
context.globalThis = context;
vm.runInNewContext(source, context);
const ui = context.BenchmarkReferenceSensitivity;

test('public index is compact and bound to saved full findings', () => {
  assert.ok(publicBytes.length < 750_000);
  assert.ok(findingsBytes.length > 10_000_000);
  assert.equal(data.findings_sha256, crypto.createHash('sha256').update(findingsBytes).digest('hex'));
  assert.equal(ui.validate(data), data);
  assert.equal(data.extended_runs.length, 637);
  assert.equal(data.native_seven_runs.length, 7);
});

test('exact documented alternatives and seven scenario totals are required', () => {
  const changedLabel = structuredClone(data);
  changedLabel.alternatives[1].alternative = 'negative';
  assert.throws(() => ui.validate(changedLabel), /alternatives changed/);
  const missingScenario = structuredClone(data);
  missingScenario.scenario_summaries.pop();
  assert.throws(() => ui.validate(missingScenario), /header changed/);
  const changedCount = structuredClone(data);
  changedCount.scenario_summaries[0].extended_summary.improved_runs++;
  assert.throws(() => ui.validate(changedCount), /totals changed/);
});

test('malformed run scores, source identity and case effects fail closed', () => {
  const wrongScore = structuredClone(data);
  wrongScore.extended_runs[0].saved_all_four = 61;
  assert.throws(() => ui.validate(wrongScore), /source or score changed/);
  const wrongSource = structuredClone(data);
  wrongSource.extended_runs[0].source_report_url = 'https://elsewhere.test/result.json';
  assert.throws(() => ui.validate(wrongSource), /source or score changed/);
  const wrongEffect = structuredClone(data);
  wrongEffect.extended_runs[0].single_case_deltas['DEV-006'].all_four = 1;
  assert.throws(() => ui.validate(wrongEffect), /Per-case sensitivity changed/);
});

test('combined per-run and native deltas are sums of the three fixed case effects', () => {
  const selected = ['DEV-006', 'DEV-013', 'DEV-030'];
  assert.equal(ui.selectedId(selected), 'dev006+dev013+dev030');
  for (const run of data.extended_runs) {
    assert.equal(ui.allFourDelta(run, selected),
      selected.reduce((value, id) => value + run.single_case_deltas[id].all_four, 0));
    assert.equal(ui.runDelta(run, selected, 'sentiment'),
      run.single_case_deltas['DEV-013'].sentiment + run.single_case_deltas['DEV-030'].sentiment);
    assert.equal(ui.runDelta(run, selected, 'follow_up_needed'), 0);
  }
  const table = ui.nativeTable(data.native_seven_runs, selected);
  assert.equal((table.match(/<tbody><tr>|<\/tr><tr>/g) || []).length, 7);
  assert.match(table, /same 60 reviews/);
});

test('run detail marks hypothetical scores and retains review and source links', () => {
  const run = data.extended_runs[0];
  const detail = ui.detail(run, ['DEV-006', 'DEV-013'], data.alternatives);
  assert.match(detail, /hypothetical key/);
  assert.match(detail, /published score remains the saved score/);
  assert.ok(detail.includes(`${run.valid}/60 valid answers`));
  assert.ok(detail.includes(`run=${run.id}&amp;case=DEV-006#inspect`));
  assert.ok(detail.includes(`run=${run.id}&amp;case=DEV-013#inspect`));
  assert.ok(detail.includes(run.source_report_url));
});

test('review links clear filters that would hide the exact target', () => {
  const url = ui.reviewUrl('DEV-030');
  assert.equal(url, '/?cohort=decision&review=DEV-030#review-evidence');
});

test('affected case drilldown targets the selected extended run, not the seven-native review', () => {
  const run = data.extended_runs.find(item => item.id.includes('jev') && item.valid < 60);
  assert.ok(run);
  const url = ui.runCaseUrl(run.id, 'DEV-030');
  const parsed = new URL(url, 'https://example.test');
  assert.equal(parsed.searchParams.get('run'), run.id);
  assert.equal(parsed.searchParams.get('case'), 'DEV-030');
  assert.equal(parsed.searchParams.get('compareRun'), null);
  assert.equal(parsed.hash, '#inspect');
});
