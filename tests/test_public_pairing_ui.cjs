const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'public-site', 'app.js'), 'utf8');

function fixture() {
  let panel = null;
  const experiment = {value: 'model-a'};
  const note = {textContent: '', after(node) { panel = node; }};
  const title = {textContent: ''};
  const contextLabel = {textContent: ''};
  const conditionGrid = {innerHTML: '', querySelectorAll() { return []; }};
  const metric = {value: 'all_four'};
  let focused = null;
  const document = {
    querySelector(selector) {
      if (selector === '#audited-comparison') return panel;
      if (selector === '#experiment-note') return note;
      if (selector === '#experiment-select') return experiment;
      if (selector === '#experiment-title') return title;
      if (selector === '#experiment-context') return contextLabel;
      if (selector === '#condition-grid') return conditionGrid;
      if (selector === '#metric') return metric;
      return null;
    },
    createElement() {
      return {
        innerHTML: '', hidden: false,
        setAttribute() {},
        addEventListener(type, handler) { this[type] = handler; },
        querySelector(selector) { return {focus() { focused = selector; }}; },
      };
    },
  };
  const instrumented = source.replace('  init();\n})();', '  globalThis.__pairUi = {state,renderAuditedComparison,renderExperiment,comparisonNote};\n})();');
  assert.notEqual(instrumented, source, 'test hook must replace only the init call');
  const context = {document, URL};
  vm.runInNewContext(instrumented, context, {filename: 'app.js'});
  return {ui: context.__pairUi, panel: () => panel, note: () => note.textContent, focused: () => focused};
}

function report() {
  const record = {
    id: 'DEV-006', from_state: 'valid', to_state: 'valid',
    from_prediction: {sentiment: 'negative'}, to_prediction: {sentiment: 'positive'},
    reference: {sentiment: 'negative'}, feedback: '<script>alert(1)</script>',
  };
  return {
    id: 'model-a', eligible: true,
    evidenceUrl: 'https://example.org/audit.json',
    historicalP0Limitation: 'P0 ran earlier than P1/P2; time and cache were not controlled.',
    referenceStatus: 'Provisional references',
    comparisons: {
      P0_to_P1: {bothValid: 58, changedRecordCount: 2, allFourWrongToCorrect: ['DEV-001'], allFourCorrectToWrong: [], cases: [record, {...record, id: 'DEV-010', feedback: 'Second feedback'}]},
      P0_to_P2: {bothValid: 56, changedRecordCount: 1, allFourWrongToCorrect: [], allFourCorrectToWrong: ['DEV-006'], cases: [{...record, id: 'DEV-009'}]},
      P1_to_P2: {bothValid: 59, changedRecordCount: 0, allFourWrongToCorrect: [], allFourCorrectToWrong: [], cases: []},
    },
  };
}

test('audited view exposes pair counts, changed feedback, evidence, and temporal limit', () => {
  const {ui, panel} = fixture();
  ui.state.data = {promptComparisons: [report()]};
  ui.renderAuditedComparison('model-a');
  const html = panel().innerHTML;
  assert.equal(panel().hidden, false);
  assert.match(html, /58 \/ 60/);
  assert.match(html, /role="status" aria-live="polite" aria-atomic="true"/);
  assert.match(html, /reviews with changed outputs/);
  assert.match(html, /BEFORE · P0/);
  assert.match(html, /AFTER · P1/);
  assert.match(html, /negative/);
  assert.match(html, /positive/);
  assert.match(html, /href="https:\/\/example\.org\/audit\.json"/);
  assert.match(html, /time and cache were not controlled/);
  assert.match(html, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);
  assert.doesNotMatch(html, /<script>/);
});

test('pair and changed-review selectors navigate without changing experiment or claims', () => {
  const {ui, panel, focused} = fixture();
  ui.state.data = {promptComparisons: [report()]};
  ui.renderAuditedComparison('model-a');
  panel().change({target: {id: 'pair-case-select', value: '1'}});
  assert.match(panel().innerHTML, /Second feedback/);
  assert.equal(focused(), '#pair-case-select');
  panel().change({target: {id: 'pair-select', value: 'P0_to_P2'}});
  assert.match(panel().innerHTML, /56 \/ 60/);
  assert.match(panel().innerHTML, /REVIEW DEV-009/);
  assert.match(panel().innerHTML, /AFTER · P2/);
  assert.equal(focused(), '#pair-select');
  panel().change({target: {id: 'pair-select', value: 'P1_to_P2'}});
  assert.match(panel().innerHTML, /No changed review is listed/);
  assert.doesNotMatch(panel().innerHTML, /id="pair-case-select"/);
});

test('an experiment without an eligible audited report has no comparison panel', () => {
  const {ui, panel} = fixture();
  ui.state.data = {promptComparisons: [{...report(), eligible: false}]};
  ui.renderAuditedComparison('model-a');
  assert.equal(panel().hidden, true);
  assert.equal(panel().innerHTML, '');
  ui.state.data = {promptComparisons: [report()]};
  ui.renderAuditedComparison('model-a');
  ui.renderAuditedComparison('another-model');
  assert.equal(panel().hidden, true);
  assert.equal(panel().innerHTML, '');
});

test('native Jev comparison is shown separately without treating it as an eligible chat prompt pair', () => {
  const {ui, panel} = fixture();
  const native = {...report(), id: 'typesafe-jev113-v2', eligible: false,
    comparisonLimit: 'Historical P0 and one pass per condition do not isolate time or stochastic effects.'};
  ui.state.data = {promptComparisons: [], nativeInstructionComparisons: [native]};
  ui.renderAuditedComparison('typesafe-jev113-v2');
  assert.equal(panel().hidden, false);
  assert.match(panel().innerHTML, /Jev instruction comparison/);
  assert.match(panel().innerHTML, /native Choice questions, not chat system prompts/);
  assert.match(panel().innerHTML, /Historical P0 and one pass/);
  assert.match(panel().innerHTML, /58 \/ 60/);
});

function hostedReport() {
  return {...report(), eligible: false, kind: 'hosted-observational',
    comparisonLimit: 'One pass per condition; prompt variant effects remain observational.'};
}

test('marked hosted Gemini pairs show changed cases with an observational limit', () => {
  const {ui, panel, note, focused} = fixture();
  const runs = ['P0', 'P1', 'P2'].map((condition, index) => ({
    id: index ? `model-a-${condition.toLowerCase()}` : 'model-a',
    parentBaselineId: index ? 'model-a' : null,
    model: 'Gemini 3.8 Flash', effort: 'low', surface: 'OpenRouter Gemini hosted batch10',
    condition, complete: true, records: 60, valid: 60,
    metrics: {all_four: 50}, pairedEligible: false,
  }));
  ui.state.data = {promptComparisons: [hostedReport()], runs};
  ui.state.experiments = new Map([['model-a', runs]]);
  ui.renderExperiment();
  assert.match(note(), /Compare changed answers by record below/);
  assert.match(note(), /Each prompt version was run once/);
  assert.equal(panel().hidden, false);
  assert.match(panel().innerHTML, /Hosted prompt comparison/);
  assert.match(panel().innerHTML, /One pass per condition/);
  assert.match(panel().innerHTML, /58 \/ 60/);
  assert.match(panel().innerHTML, /REVIEW DEV-006/);
  assert.match(ui.comparisonNote(runs[1]), /Part of the hosted prompt comparison/);
  assert.doesNotMatch(ui.comparisonNote(runs[1]), /not part of the record-by-record/);
  panel().change({target: {id: 'pair-case-select', value: '1'}});
  assert.match(panel().innerHTML, /Second feedback/);
  assert.equal(focused(), '#pair-case-select');
  panel().change({target: {id: 'pair-select', value: 'P0_to_P2'}});
  assert.match(panel().innerHTML, /REVIEW DEV-009/);
  assert.match(panel().innerHTML, /56 \/ 60/);
});

test('unmarked ineligible pairs stay hidden and native Jev detail copy stays native', () => {
  const {ui, panel} = fixture();
  ui.state.data = {promptComparisons: [{...report(), eligible: false, kind: 'other-observation'}]};
  ui.renderAuditedComparison('model-a');
  assert.equal(panel().hidden, true);
  const jev = {id: 'typesafe-jev113-v2', nativeInstructionComparison: true, pairedEligible: false};
  assert.match(ui.comparisonNote(jev), /Native Jev instruction comparison/);
  assert.doesNotMatch(ui.comparisonNote(jev), /hosted prompt comparison/);
});
