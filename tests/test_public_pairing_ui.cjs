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
  const ledger = {innerHTML: '', querySelectorAll() { return []; }};
  const usagePicker = {innerHTML: '', value: ''};
  const inspectPicker = {innerHTML: '', value: ''};
  const ledgerControls = {
    '#search': {value: ''}, '#condition-filter': {value: ''},
    '#surface-filter': {value: ''}, '#include-incomplete': {checked: true},
    '#sort': {value: 'score-desc'}, '#result-count': {textContent: ''},
    '#score-heading': {textContent: ''}, '#comparison-list': ledger,
  };
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
      if (selector === '#usage-run-select') return usagePicker;
      if (selector === '#inspect-run-select') return inspectPicker;
      if (Object.prototype.hasOwnProperty.call(ledgerControls, selector)) return ledgerControls[selector];
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
  const instrumented = source.replace('  init();\n})();', '  globalThis.__pairUi = {state,renderAuditedComparison,renderExperiment,renderLedger,renderSectionRunPickers,comparisonNote};\n})();');
  assert.notEqual(instrumented, source, 'test hook must replace only the init call');
  const context = {document, URL};
  vm.runInNewContext(instrumented, context, {filename: 'app.js'});
  return {ui: context.__pairUi, experiment, panel: () => panel, note: () => note.textContent,
    conditionGrid: () => conditionGrid.innerHTML, ledger: () => ledger.innerHTML,
    usagePicker, inspectPicker, focused: () => focused};
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

test('incomplete run keeps its fixed-denominator count as an explicit partial tally', () => {
  const {ui, conditionGrid, ledger} = fixture();
  const partial = {id: 'model-a', condition: 'P0', model: 'SemIf', surface: 'Local / specialist',
    complete: false, records: 59, valid: 57, metrics: {all_four: 42}};
  ui.state.data = {runs: [partial], promptComparisons: [], roster: []};
  ui.state.experiments = new Map([['model-a', [partial]]]);
  ui.renderExperiment();
  assert.match(conditionGrid(), /PARTIAL TALLY · 59 \/ 60 SAVED · 1 WITHOUT A SAVED RESPONSE/);
  assert.match(conditionGrid(), /42<small> \/ 60<\/small>/);
  assert.match(conditionGrid(), /All four match · NOT A FINAL SCORE/);
  ui.renderLedger();
  assert.match(ledger(), /42<\/strong><small> \/ 60 · partial tally, not final<\/small>/);
  assert.match(ledger(), /59 \/ 60 saved · 1 without a saved response/);
});

test('resource and individual-run pickers contain the same saved runs and selection', () => {
  const {ui, usagePicker, inspectPicker} = fixture();
  ui.state.data = {runs: [
    {id: 'model-a', condition: 'P0', model: 'Fable', effort: 'high', surface: 'Claude subscription', complete: true, records: 60},
    {id: 'model-b', condition: 'P1', model: 'Gemma', effort: 'low', surface: 'Local / specialist', complete: false, records: 42},
  ]};
  ui.state.selectedId = 'model-b';
  ui.renderSectionRunPickers();
  assert.equal(usagePicker.innerHTML, inspectPicker.innerHTML);
  assert.match(usagePicker.innerHTML, /model-a/);
  assert.match(usagePicker.innerHTML, /model-b · partial/);
  assert.equal(usagePicker.value, 'model-b');
  assert.equal(inspectPicker.value, 'model-b');
});

test('historical Fable card links its separate matched batch series', () => {
  const {ui, experiment, conditionGrid} = fixture();
  const historical = {id: 'fable51-high', condition: 'P0', model: 'Fable', effort: 'high', surface: 'Claude subscription', complete: true, records: 60, metrics: {all_four: 57}};
  const related = {...historical, id: 'fable51-high-phase2-batch10-p0', metrics: {all_four: 58}};
  ui.state.data = {runs: [historical, related], promptComparisons: [], roster: []};
  ui.state.experiments = new Map([['fable51-high', [historical]]]);
  experiment.value = 'fable51-high';
  ui.renderExperiment();
  assert.match(conditionGrid(), /NO MATCHED RUN/);
  assert.match(conditionGrid(), /one comment per request/);
  assert.match(conditionGrid(), /batch-of-10 prompt series/);
  assert.match(conditionGrid(), /fable51-high-phase2-batch10-p0/);
  assert.doesNotMatch(conditionGrid(), /NOT APPLICABLE/);
});

test('each verified historical Claude and Codex counterpart links its own later series', () => {
  const pairs = {
    'sonnet5-low-first-pass':'sonnet5-low-first-pass-phase2-batch10-p0',
    'sonnet5-low-with-retry':'sonnet5-low-first-pass-phase2-batch10-p0',
    'sonnet5-medium':'sonnet5-medium-phase2-batch10-p0',
    'sonnet5-high':'sonnet5-high-phase2-batch10-p0',
    'sonnet5-xhigh':'sonnet5-xhigh-phase2-batch10-p0',
    'opus5-low':'opus5-low-phase2-batch10-p0',
    'opus5-medium':'opus5-medium-phase2-batch10-p0',
    'opus5-high':'opus5-high-phase2-batch10-p0',
    'opus5-xhigh':'opus5-xhigh-phase2-batch10-p0',
    'fable51-low':'fable51-low-phase2-batch10-p0',
    'fable51-medium':'fable51-medium-phase2-batch10-p0',
    'fable51-high':'fable51-high-phase2-batch10-p0',
    'fable51-xhigh':'fable51-xhigh-phase2-batch10-p0',
    'codex-gpt-5.6-luna-low':'codex-gpt-5.6-luna-low-phase2-batch10-p0',
    'codex-gpt-6-astra-low':'codex-gpt-6-astra-low-phase2-batch10-p0',
  };
  for (const [id, relatedId] of Object.entries(pairs)) {
    const {ui, experiment, conditionGrid} = fixture();
    const historical = {id, condition:'P0', model:'Historical', effort:'low', surface:'Subscription', complete:true, records:60, metrics:{all_four:55}};
    const related = {...historical, id:relatedId};
    ui.state.data = {runs:[historical,related], promptComparisons:[], roster:[]};
    ui.state.experiments = new Map([[id,[historical]]]);
    experiment.value = id;
    ui.renderExperiment();
    assert.match(conditionGrid(), new RegExp(relatedId), id);
    assert.match(conditionGrid(), /NO MATCHED RUN/, id);
    assert.match(conditionGrid(), /separate P0, P1 and P2 runs/, id);
  }
});

test('Haiku points to the fresh series without counting the old failed batch P1 as complete', () => {
  const {ui, experiment, conditionGrid} = fixture();
  const historical = {id:'haiku45-not_applicable', condition:'P0', model:'Haiku', effort:'not_applicable', surface:'Claude subscription', complete:true, records:60, metrics:{all_four:55}};
  ui.state.data = {runs:[historical], promptComparisons:[], roster:[]};
  ui.state.experiments = new Map([[historical.id,[historical]]]);
  experiment.value = historical.id;
  ui.renderExperiment();
  assert.match(conditionGrid(), /ten P1 transport failures/);
  assert.match(conditionGrid(), /separate fresh matched-three/);
  assert.match(conditionGrid(), /haiku-fresh-matched3\.json/);
  assert.doesNotMatch(conditionGrid(), /later batch-of-10 setup has separate P0, P1 and P2 runs/);
});

test('scheduled Antigravity P0-only rows display their blocked state and partial P1 limit', () => {
  const {ui, experiment, conditionGrid} = fixture();
  const id='antigravity-gemini-3.1-pro-low-native-observed-batch10';
  const historical = {id, condition:'P0', model:'Gemini', effort:'low', surface:'Antigravity', complete:true, records:60, metrics:{all_four:55}};
  ui.state.data = {runs:[historical], promptComparisons:[], roster:[{id,disposition:'scheduled',reason:'Selected for prompt evaluation.'}]};
  ui.state.experiments = new Map([[id,[historical]]]);
  experiment.value = id;
  ui.renderExperiment();
  assert.match(conditionGrid(), /BLOCKED AFTER P0/);
  assert.match(conditionGrid(), /40 valid responses, 10 service errors and 10 unattempted comments/);
  assert.match(conditionGrid(), /There is no complete public P1 run/);
  assert.match(conditionGrid(), /No complete public P2 run/);
  assert.match(conditionGrid(), /PROMPT_COVERAGE_AUDIT_2026-10-02\.md/);
});
