const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const casesUi = require('../public-site/extended-cases.js');

const data = JSON.parse(fs.readFileSync(path.join(__dirname, '../public-site/extended-cases-v1.json')));

test('feed has reconciled run and case coverage', () => {
  assert.equal(casesUi.validate(data), data);
  assert.equal(data.coverage.catalogRuns, data.coverage.caseRuns + data.coverage.reportOnlyRuns);
  assert.equal(data.cases.length, 60);
  assert.equal(new Set(data.runs.map(run => run.runId)).size, data.coverage.caseRuns);
});

test('one run exposes all 60 saved case answers, searchable by ID and review text', () => {
  const runId = data.runs[0].runId;
  const all = casesUi.view(data, runId);
  assert.equal(all.cases.length, 60);
  assert.equal(casesUi.view(data, runId, {query: 'DEV-029'}).cases.length, 1);
  assert.equal(casesUi.view(data, runId, {query: 'Great soup'}).cases[0].id, 'DEV-029');
  assert.match(all.run.sourceRecordUrl, /^https:\/\//);
  assert.equal(all.run.sourceRecordParts[0].sha256, all.run.sourceRecordSha256);
});

test('disagreement filters use only a selected run and frozen reference', () => {
  const run = data.runs.find(item => item.scores.all_four < 60 && item.scores.valid === 60);
  const differences = casesUi.view(data, run.runId, {mode: 'disagreements'});
  assert.equal(differences.cases.length, 60 - run.scores.all_four);
  assert.ok(differences.cases.every(item => item.differingFields.length));
  const sentiment = casesUi.view(data, run.runId, {field: 'sentiment'});
  assert.equal(sentiment.cases.length, 60 - run.scores.sentiment);
});

test('nonvalid output retains its saved status and no fabricated answer', () => {
  const run = data.runs.find(item => item.cases.some(row => row.status !== 'ok'));
  assert.ok(run);
  const unanswered = casesUi.view(data, run.runId, {mode: 'unanswered'});
  assert.ok(unanswered.cases.length > 0);
  assert.ok(unanswered.cases.every(item => item.prediction === null && item.status !== 'ok'));
});

test('unknown catalog row does not present another run’s answers', () => {
  assert.equal(data.coverage.reportOnlyRuns, 0);
  const result = casesUi.view(data, 'extended-nonexistent-run');
  assert.equal(result.run, null);
  assert.equal(result.gap, null);
  assert.deepEqual(result.cases, []);
});

test('A/B differences are distinct from differences against the provisional reference', () => {
  const [a, b] = data.runs.filter(run => run.scores.valid === 60).slice(0, 2);
  const compared = casesUi.view(data, a.runId, {compareRunId: b.runId});
  assert.equal(compared.compareRun.runId, b.runId);
  const between = casesUi.view(data, a.runId, {compareRunId: b.runId, mode: 'between'});
  assert.equal(between.cases.length,
    compared.cases.filter(item => item.betweenFields.length || item.outcomeDiffers).length);
  assert.ok(between.cases.every(item => item.outcomeDiffers));
  assert.equal(casesUi.view(data, a.runId, {compareRunId: a.runId, mode: 'between'}).cases.length, 0);
});

test('cleared deep-link comparison stays cleared while searching another run', () => {
  const [a, b] = data.runs;
  const noMatch = 'this search matches no saved run';
  assert.deepEqual(casesUi.comparisonOptions(data, a.runId, b.runId, noMatch).map(run => run.runId), [b.runId]);
  assert.deepEqual(casesUi.comparisonOptions(data, a.runId, '', noMatch), []);
  assert.equal(casesUi.view(data, a.runId, {compareRunId: ''}).compareRun, null);
});

test('unexpected feed and missing case answer fail closed', () => {
  assert.throws(() => casesUi.validate({schema: 'extended-cases-v1', cases: []}), /unexpected format/);
  const run = data.runs[0];
  const broken = {...data, runs: [{...run, cases: run.cases.slice(1)}]};
  assert.throws(() => casesUi.view(broken, run.runId), /Missing saved case/);
});
