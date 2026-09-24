const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '..', 'public-site', 'app.js'), 'utf8');

function fixture() {
  let panel = null;
  const experiment = {value: 'model-a'};
  const note = {after(node) { panel = node; }};
  let focused = null;
  const document = {
    querySelector(selector) {
      if (selector === '#audited-comparison') return panel;
      if (selector === '#experiment-note') return note;
      if (selector === '#experiment-select') return experiment;
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
  const instrumented = source.replace('  init();\n})();', '  globalThis.__pairUi = {state,renderAuditedComparison};\n})();');
  assert.notEqual(instrumented, source, 'test hook must replace only the init call');
  const context = {document, URL};
  vm.runInNewContext(instrumented, context, {filename: 'app.js'});
  return {ui: context.__pairUi, panel: () => panel, focused: () => focused};
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
