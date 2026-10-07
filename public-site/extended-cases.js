(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.BenchmarkExtendedCases = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';

  const FIELDS = ['sentiment', 'follow_up_needed', 'serious_concern_reported', 'testimonial_potential'];
  const LABELS = {
    sentiment: 'Sentiment', follow_up_needed: 'Follow-up needed',
    serious_concern_reported: 'Serious concern', testimonial_potential: 'Testimonial potential'
  };
  const CHOICES = {sentiment: ['positive', 'negative', 'mixed', 'neutral', 'insufficient_information'],
    follow_up_needed: ['yes', 'no', 'insufficient_information'],
    serious_concern_reported: ['yes', 'no', 'insufficient_information'],
    testimonial_potential: ['yes', 'no', 'insufficient_information']};
  const BASE_URL = 'https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/';
  const cachedFeeds = new Map();

  function validate(data) {
    if (!data || !['extended-cases-v1', 'additional-cases-v1', 'unified-cases-v1'].includes(data.schema) || !Array.isArray(data.cases) ||
        data.cases.length !== 60 || !Array.isArray(data.runs) || !data.coverage) {
      throw new Error('Case feed has an unexpected format');
    }
    return data;
  }

  function sameReference(a, b) {
    return a.id === b.id && a.feedback === b.feedback &&
      FIELDS.every(field => a.reference?.[field] === b.reference?.[field]);
  }

  function checkedCases(runId, rows, canonical, expected, allowInvalidRaw = false) {
    if (!Array.isArray(rows) || rows.length !== 60) throw new Error(`${runId}: expected 60 case positions`);
    const byId = new Map();
    const scores = {valid:0, all_four:0, ...Object.fromEntries(FIELDS.map(field => [field, 0]))};
    rows.forEach(row => {
      if (byId.has(row.id) || !canonical.has(row.id) || typeof row.status !== 'string' || !row.status) {
        throw new Error(`${runId}: duplicate, unknown, or unlabelled case position`);
      }
      const valid = row.status === 'ok' || row.status === 'valid';
      const prediction = valid ? row.prediction : null;
      if (valid && (!prediction || typeof prediction !== 'object' || Array.isArray(prediction) ||
          Object.keys(prediction).length !== FIELDS.length ||
          FIELDS.some(field => !CHOICES[field].includes(prediction[field])))) {
        throw new Error(`${runId}/${row.id}: invalid four-field answer`);
      }
      if (valid) {
        scores.valid += 1;
        const reference = canonical.get(row.id).reference;
        scores.all_four += Number(FIELDS.every(field => prediction[field] === reference[field]));
        FIELDS.forEach(field => { scores[field] += Number(prediction[field] === reference[field]); });
      } else if (!allowInvalidRaw && row.prediction !== null) {
        throw new Error(`${runId}/${row.id}: invalid outcome has a projected answer`);
      }
      byId.set(row.id, {id:row.id, status:row.status,
        prediction:prediction ? Object.fromEntries(FIELDS.map(field => [field, prediction[field]])) : null});
    });
    if (byId.size !== 60 || FIELDS.concat(['valid', 'all_four']).some(field =>
        scores[field] !== expected[field])) throw new Error(`${runId}: case score differs from saved run`);
    return Array.from(canonical.keys(), id => byId.get(id));
  }

  function combine(base, extended, additional) {
    validate(extended); validate(additional);
    if (base?.denominator !== 60 || !Array.isArray(base.runs) || !Array.isArray(base.cases)) {
      throw new Error('Main saved-run feed has an unexpected format');
    }
    const cases = extended.cases;
    const canonical = new Map(cases.map(item => [item.id, item]));
    if (canonical.size !== 60 || additional.cases.length !== 60 ||
        new Set(additional.cases.map(item => item.id)).size !== 60 ||
        additional.cases.some(item => !canonical.has(item.id) || !sameReference(item, canonical.get(item.id)))) {
      throw new Error('Case feeds disagree on the 60 reviews or provisional references');
    }
    const baseRows = new Map();
    base.cases.forEach(item => {
      const reference = canonical.get(item.id);
      if (!reference || item.feedback !== reference.feedback ||
          FIELDS.some(field => item.reference?.[field] !== reference.reference[field])) {
        throw new Error('Main feed review or reference differs from case feeds');
      }
      if (!baseRows.has(item.configuration)) baseRows.set(item.configuration, []);
      baseRows.get(item.configuration).push(item);
    });
    const baseRuns = base.runs.filter(run => baseRows.has(run.id));
    if (baseRuns.length !== 290 || baseRows.size !== 290) {
      throw new Error('Main saved-run identities do not reconcile');
    }
    const mainUrl = BASE_URL + 'public-site/data-provider-errors-v1.json';
    const normalizedBase = baseRuns.map(run => {
      if (!run.evidenceUrl?.startsWith(BASE_URL)) throw new Error(`${run.id}: source link unavailable`);
      return {runId:run.id, sourceStage:run.id, model:run.model, effort:run.effort,
        condition:run.condition, repeatPass:null, provider:run.provider || null,
        surface:run.surface, referenceVersion:'0.2', sourceReportUrl:mainUrl,
        sourceReportLabel:'public run feed', sourceReportSha256:null,
        sourceRecordUrl:run.evidenceUrl, sourceRecordSha256:null,
        sourceRecordParts:[{url:run.evidenceUrl, sha256:null}],
        scores:{valid:run.valid, ...run.metrics},
        cases:checkedCases(run.id, baseRows.get(run.id), canonical,
          {valid:run.valid, ...run.metrics}, true)};
    });
    const joined = [...normalizedBase, ...extended.runs, ...additional.runs].map(run =>
      ({...run, cases:checkedCases(run.runId, run.cases, canonical, run.scores)}));
    const ids = new Set();
    joined.forEach(run => {
      if (!run.runId || ids.has(run.runId)) throw new Error('Case feeds contain a repeated run identity');
      ids.add(run.runId);
      if (!run.sourceReportUrl?.startsWith(BASE_URL) || !run.sourceRecordUrl?.startsWith(BASE_URL)) {
        throw new Error(`${run.runId}: public evidence link unavailable`);
      }
    });
    if (joined.length !== 1004) throw new Error('Saved-run case coverage is incomplete');
    return {schema:'unified-cases-v1', cases, runs:joined,
      coverage:{catalogRuns:1004, caseRuns:1004, reportOnlyRuns:0, gaps:[]}};
  }

  function load(url = 'extended-cases-v1.json') {
    if (!cachedFeeds.has(url)) {
      const pending = fetch(url).then(response => {
        if (!response.ok) throw new Error(`Case feed request failed (${response.status})`);
        return response.json();
      }).then(validate).catch(error => {
        cachedFeeds.delete(url);
        throw error;
      });
      cachedFeeds.set(url, pending);
    }
    return cachedFeeds.get(url);
  }

  function runLabel(run) {
    return [...new Set([run.model, run.effort, run.condition, run.repeatPass, run.surface,
      run.sourceStage, run.runId].filter(Boolean))].join(' · ');
  }

  function statusLabel(status) {
    const names = {
      unknown_cost_http_429: 'HTTP 429; cost unknown',
      unknown_started: 'started; outcome unknown',
      unknown_outcome: 'outcome unknown',
      unknown_cost: 'cost unknown',
      failed_in_report: 'failed in report'
    };
    return names[status] || String(status || 'unavailable').replaceAll('_', ' ');
  }

  function differenceLabel(count, prefix = '') {
    return `${count} ${prefix}field${count === 1 ? '' : 's'} differ${count === 1 ? 's' : ''}`;
  }

  function comparisonOptions(data, runId, selectedRunId = '', search = '') {
    const needle = search.trim().toLocaleLowerCase();
    return data.runs.filter(item => item.runId !== runId &&
      (!needle || runLabel(item).toLocaleLowerCase().includes(needle) || item.runId === selectedRunId))
      .sort((a, b) => runLabel(a).localeCompare(runLabel(b)));
  }

  function view(data, runId, { query = '', mode = 'all', field = 'all', compareRunId = '' } = {}) {
    validate(data);
    const run = data.runs.find(item => item.runId === runId);
    if (!run) {
      const gap = data.coverage.gaps.find(item => item.runId === runId);
      return { run: null, compareRun: null, gap: gap || null, cases: [], total: 0 };
    }
    const answers = new Map(run.cases.map(item => [item.id, item]));
    const compareRun = compareRunId && compareRunId !== runId
      ? data.runs.find(item => item.runId === compareRunId) : null;
    const compareAnswers = compareRun ? new Map(compareRun.cases.map(item => [item.id, item])) : null;
    const search = query.trim().toLocaleLowerCase();
    const cases = data.cases.map(item => {
      const answer = answers.get(item.id);
      if (!answer) throw new Error(`Missing saved case ${item.id} for ${runId}`);
      const other = compareAnswers ? compareAnswers.get(item.id) : null;
      if (compareAnswers && !other) throw new Error(`Missing comparison case ${item.id} for ${compareRunId}`);
      const differingFields = answer.prediction
        ? FIELDS.filter(name => answer.prediction[name] !== item.reference[name]) : [];
      const betweenFields = other && answer.prediction && other.prediction
        ? FIELDS.filter(name => answer.prediction[name] !== other.prediction[name]) : [];
      const outcomeDiffers = Boolean(other && (
        betweenFields.length || Boolean(answer.prediction) !== Boolean(other.prediction) ||
        (!answer.prediction && !other.prediction && answer.status !== other.status)));
      return { ...item, status: answer.status, prediction: answer.prediction,
        differingFields, betweenFields, outcomeDiffers,
        comparisonStatus: other ? other.status : null,
        comparisonPrediction: other ? other.prediction : null };
    }).filter(item => {
      if (search && !`${item.id} ${item.feedback}`.toLocaleLowerCase().includes(search)) return false;
      if (mode === 'disagreements' && item.differingFields.length === 0) return false;
      if (mode === 'between' && !item.outcomeDiffers) return false;
      if (mode === 'unanswered' && item.prediction !== null) return false;
      if (field !== 'all' && !(mode === 'between' ? item.betweenFields : item.differingFields).includes(field)) return false;
      return true;
    });
    return { run, compareRun, gap: null, cases, total: data.cases.length };
  }

  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  function labelled(text, control) {
    const label = element('label');
    label.append(element('span', text), control);
    return label;
  }

  function render(container, data, runId) {
    if (!container) throw new Error('Case container is required');
    validate(data);
    container.replaceChildren();
    const initial = view(data, runId);
    if (!initial.run) {
      container.append(element('p', initial.gap
        ? `Individual answers are not available in this case feed: ${initial.gap.reason}.`
        : 'This saved run is not in the extended case feed.'));
      if (initial.gap && initial.gap.sourceReportUrl) {
        const link = element('a', 'Open the public run report');
        link.href = initial.gap.sourceReportUrl;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        container.append(link);
      }
      return;
    }
    const run = initial.run;
    const comparisonScope = data.schema === 'unified-cases-v1'
      ? `The comparison chooser includes all ${data.runs.length} saved runs.`
      : data.schema === 'additional-cases-v1'
      ? `The comparison chooser includes ${data.runs.length} first-pass and native runs.`
      : `The comparison chooser includes ${data.runs.length} report-backed repeat and continuation runs.`;
    const header = element('p', `The same 60 development reviews · human-checked provisional labels v0.2. Each choice is one saved run, including its prompt, pass, and route. ${comparisonScope} Different routes and controls are separate configurations; an A/B difference does not establish a causal model effect.`);
    const runNames = element('p', undefined, 'extended-case-run-names');
    const sourceLinks = element('div', undefined, 'extended-case-sources');
    container.append(header, runNames, sourceLinks);
    const controls = element('div', undefined, 'extended-case-controls');
    const search = element('input');
    search.type = 'search';
    search.placeholder = 'Search review ID or text';
    search.setAttribute('aria-label', 'Search review ID or text');
    const mode = element('select');
    mode.setAttribute('aria-label', 'Filter case outcomes');
    [['all', 'All reviews'], ['disagreements', 'Different from reference'],
      ['between', 'Different between A and B'], ['unanswered', 'A has no valid answer']].forEach(([value, label]) => {
      const option = element('option', label); option.value = value; mode.append(option);
    });
    const field = element('select');
    field.setAttribute('aria-label', 'Filter differing field');
    [['all', 'Any field'], ...FIELDS.map(name => [name, LABELS[name]])].forEach(([value, label]) => {
      const option = element('option', label); option.value = value; field.append(option);
    });
    const compareSearch = element('input');
    compareSearch.type = 'search';
    compareSearch.placeholder = 'Find model, pass, or route';
    compareSearch.setAttribute('aria-label', 'Find a comparison run');
    const compare = element('select');
    compare.setAttribute('aria-label', 'Compare with another saved run');
    const requestedCompare = typeof location !== 'undefined' && typeof URL !== 'undefined'
      ? new URL(location.href).searchParams.get('compareRun') : null;
    let selectedCompare = requestedCompare || '';
    function fillCompareOptions() {
      compare.replaceChildren();
      const none = element('option', 'No second run'); none.value = ''; compare.append(none);
      comparisonOptions(data, runId, selectedCompare, compareSearch.value).forEach(item => {
          const option = element('option', runLabel(item));
          option.value = item.runId;
          compare.append(option);
        });
      if (!data.runs.some(item => item.runId === selectedCompare && item.runId !== runId)) selectedCompare = '';
      compare.value = selectedCompare;
    }
    fillCompareOptions();
    compareSearch.addEventListener('input', fillCompareOptions);
    controls.append(labelled('Find a review', search), labelled('Show', mode),
      labelled('Field that differs', field), labelled('Find a second run', compareSearch),
      labelled('Compare A with B', compare));
    const count = element('p');
    count.setAttribute('role', 'status');
    const list = element('div', undefined, 'extended-case-list');
    container.append(controls, count, list);
    function appendSources(label, selectedRun) {
      const report = element('a', `${label} ${selectedRun.sourceReportLabel || 'run report'}`);
      report.href = selectedRun.sourceReportUrl;
      report.target = '_blank';
      report.rel = 'noopener noreferrer';
      sourceLinks.append(report);
      (selectedRun.sourceRecordParts || [{url: selectedRun.sourceRecordUrl}]).forEach((part, index) => {
        const link = element('a', `${label} source ${index + 1}`);
        link.href = part.url;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        sourceLinks.append(link);
      });
    }
    function update() {
      const betweenOption = Array.from(mode.options).find(option => option.value === 'between');
      betweenOption.disabled = !compare.value;
      if (!compare.value && mode.value === 'between') mode.value = 'all';
      const selected = view(data, runId, { query: search.value, mode: mode.value,
        field: field.value, compareRunId: compare.value });
      runNames.textContent = `A · ${runLabel(run)}${selected.compareRun ? `\nB · ${runLabel(selected.compareRun)}` : ''}`;
      count.textContent = `${selected.cases.length} of ${selected.total} reviews shown${selected.compareRun
        ? ' · A and B are separate saved runs, not pooled evidence' : ''}`;
      sourceLinks.replaceChildren();
      appendSources('A', run);
      if (selected.compareRun) appendSources('B', selected.compareRun);
      list.replaceChildren();
      const requestedCase = typeof location !== 'undefined' && typeof URL !== 'undefined'
        ? new URL(location.href).searchParams.get('case') : null;
      selected.cases.forEach(item => {
        const card = element('details', undefined, 'extended-case');
        const summary = element('summary', `${item.id} · ${selected.compareRun && item.outcomeDiffers
          ? item.betweenFields.length ? differenceLabel(item.betweenFields.length, 'A/B ')
            : Boolean(item.prediction) !== Boolean(item.comparisonPrediction)
              ? 'A/B answer availability differs' : 'A/B saved statuses differ'
          : item.prediction === null
          ? `no valid answer (${statusLabel(item.status)})`
          : item.differingFields.length
            ? differenceLabel(item.differingFields.length)
            : 'matches reference'}`);
        if (item.id === requestedCase) card.open = true;
        card.addEventListener('toggle', () => {
          if (!card.open || typeof history === 'undefined' || typeof URL === 'undefined' || typeof location === 'undefined') return;
          const next = new URL(location.href);
          next.searchParams.set('case', item.id);
          history.replaceState(null, '', next);
        });
        const review = element('p', item.feedback);
        const table = element('table');
        const head = element('thead');
        const headerRow = element('tr');
        ['Field', 'Proposed reference', 'A · saved answer',
          ...(selected.compareRun ? ['B · saved answer'] : [])].forEach(label => headerRow.append(element('th', label)));
        head.append(headerRow);
        const body = element('tbody');
        FIELDS.forEach(name => {
          const row = element('tr');
          row.append(element('th', LABELS[name]), element('td', item.reference[name]),
            element('td', item.prediction ? item.prediction[name] : `No valid answer (${statusLabel(item.status)})`));
          if (selected.compareRun) row.append(element('td', item.comparisonPrediction
            ? item.comparisonPrediction[name] : `No valid answer (${statusLabel(item.comparisonStatus)})`));
          body.append(row);
        });
        table.append(head, body);
        card.append(summary, review, table);
        list.append(card);
      });
    }
    [search, mode, field].forEach(control => control.addEventListener('input', update));
    compare.addEventListener('change', () => {
      selectedCompare = compare.value;
      update();
      if (typeof history === 'undefined' || typeof URL === 'undefined' || typeof location === 'undefined') return;
      const next = new URL(location.href);
      if (compare.value) next.searchParams.set('compareRun', compare.value);
      else next.searchParams.delete('compareRun');
      history.replaceState(null, '', next);
    });
    update();
  }

  return { FIELDS, validate, load, combine, view, runLabel, comparisonOptions, render };
});
