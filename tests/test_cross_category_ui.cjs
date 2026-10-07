const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const feed = JSON.parse(fs.readFileSync(path.join(root, 'public-site/cross-category-v1.json'), 'utf8'));
const script = fs.readFileSync(path.join(root, 'public-site/cross-category.js'), 'utf8');
const context = {
  document: {getElementById: () => null},
  location: {href: 'https://example.test/?cohort=general'},
  URL,
  console,
};
context.globalThis = context;
vm.runInNewContext(script, context);
const ui = context.BenchmarkCrossCategory;
const clone = value => JSON.parse(JSON.stringify(value));
const digest = file => crypto.createHash('sha256').update(fs.readFileSync(path.join(root, file))).digest('hex');

test('compact feed binds to the reviewed dataset, plan and findings', () => {
  assert.equal(feed.schema, 'cross-category-public-v1');
  assert.equal(feed.runs.length, 156);
  assert.equal(feed.inferenceRequests, 0);
  for (const file of ['results/cross-category-v1/dataset.json',
                      'results/cross-category-v1/plan.json',
                      'results/cross-category-v1/findings.md']) {
    assert.equal(feed.sourceSha256[file], digest(file));
  }
  assert.equal(ui.validate(feed), feed);
  assert.equal(feed.cases.length, 60);
  assert.equal(feed.runs[0].cases.length, 60);
});

test('all 1043 source-order general/native pair partitions stay fixed at 60', () => {
  const natives = feed.runs.filter(run => run.category === 'dedicated-decision');
  const general = feed.runs.filter(run => run.category === 'general-llm');
  assert.equal(general.length, 149);
  assert.equal(natives.length, 7);
  let checked = 0;
  for (const row of general) {
    for (const native of natives) {
      const tally = ui.pairTally(row, native);
      assert.equal(Object.values(tally).reduce((count, values) => count + values.length, 0), 60);
      for (const [key, values] of Object.entries(tally)) {
        assert.equal(values.length, row.pairedWithNative[native.runId][key]);
      }
      checked++;
    }
  }
  assert.equal(checked, 1043);
});

test('invalid status, missing pair or changed source fails closed', () => {
  const wrongScore = clone(feed);
  wrongScore.runs[0].scores.all_four++;
  assert.throws(() => ui.validate(wrongScore), /run or fixed-60/);
  const wrongPair = clone(feed);
  const general = wrongPair.runs.find(run => run.category === 'general-llm');
  general.pairedWithNative[feed.runs[0].runId].both_match++;
  assert.throws(() => ui.validate(wrongPair), /paired outcomes/);
  const wrongSource = clone(feed);
  wrongSource.runs[0].sourceUrl = 'https://example.test/untrusted.json';
  assert.throws(() => ui.validate(wrongSource), /run or fixed-60/);
});

test('selected pair displays five outcomes, exact IDs and separate accounting bases', () => {
  const native = feed.runs.find(run => run.category === 'dedicated-decision');
  const general = feed.runs.find(run => run.runId === 'sonnet5-low-first-pass');
  const html = ui.renderPair(general, native);
  assert.match(html, /Of 60 reviews:/);
  assert.match(html, /Both miss reference/);
  assert.match(html, /General output unusable or absent/);
  assert.match(html, /Compare route, effort, batch and accounting/);
  assert.match(html, /Price-derived estimate/);
  assert.match(html, /Requests with recorded duration/);
  assert.match(html, /Possible extra-charge bound/);
  assert.match(html, /do not add those rows/);
  assert.match(html, /may cover only one probe or batch/);
  assert.match(html, /results\/cross-category-v1\/dataset\.json/);
  assert.match(html, /data-cross-case="DEV-001"/);
  assert.doesNotMatch(html, /href="\/?\?[^\"]*review=DEV-001/);
  const tally = ui.pairTally(general, native);
  for (const id of Object.values(tally).flat()) assert.match(html, new RegExp(id));
});

test('untimed Liquid run retains 60 valid outputs and a zero duration-record count', () => {
  const native = feed.runs.find(run => run.runId === 'liquid-d1-native-fresh1-p0');
  const general = feed.runs.find(run => run.runId === 'sonnet5-low-first-pass');
  assert.equal(native.scores.valid, 60);
  assert.equal(native.controls.observedRequestCount, 0);
  const html = ui.renderPair(general, native);
  assert.match(html, /Requests with recorded duration<\/th><td>[^<]*<\/td><td>0<\/td>/);
  assert.match(html, /No public client-duration series or server inference duration is available/);
});

test('an exact case shows both selected predictions and the reference inline', () => {
  const native = feed.runs.find(run => run.runId === 'liquid-d1-native-fresh1-p0');
  const general = feed.runs.find(run => run.runId === 'sonnet5-low-first-pass');
  const id = 'DEV-029';
  const html = ui.renderCase(feed, general, native, id);
  assert.match(html, /Exact saved answers \/ DEV-029/);
  assert.match(html, /Provisional reference/);
  assert.match(html, /General · claude-sonnet-5/);
  assert.match(html, /Native · liquid\/d1/);
  assert.match(html, /follow up needed/);
  assert.match(html, /serious concern reported/);
  assert.match(html, /results\/cross-category-v1\/dataset\.json/);
  assert.match(html, /Seven-native context for DEV-029/);
});

test('difficult-case table uses exact valid and eligible denominators', () => {
  const html = ui.renderDifficult(feed);
  assert.match(html, /DEV-029/);
  assert.match(html, /89\/113\/117/);
  assert.match(html, /13\/28\/32/);
  assert.match(html, /DEV-030/);
  assert.match(html, /19\/109\/117/);
  assert.match(html, /8\/28\/32/);
  assert.doesNotMatch(html, /DEV-001/);
});

test('review links clear seven-native filters while preserving unrelated context', () => {
  context.location.href = 'https://example.test/?cohort=general&crossCase=DEV-030&reviewSubset=disputed&reviewModel=liquid&reviewField=sentiment&reviewSearch=other';
  assert.equal(ui.reviewUrl('DEV-029'), '/?cohort=general&crossCase=DEV-030&review=DEV-029#review-evidence');
  context.location.href = 'https://example.test/?cohort=general';
});
