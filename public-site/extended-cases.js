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
  let cachedFeed;

  function validate(data) {
    if (!data || data.schema !== 'extended-cases-v1' || !Array.isArray(data.cases) ||
        data.cases.length !== 60 || !Array.isArray(data.runs) || !data.coverage) {
      throw new Error('Extended case feed has an unexpected format');
    }
    return data;
  }

  function load(url = 'extended-cases-v1.json') {
    if (!cachedFeed) {
      cachedFeed = fetch(url).then(response => {
        if (!response.ok) throw new Error(`Case feed request failed (${response.status})`);
        return response.json();
      }).then(validate).catch(error => {
        cachedFeed = undefined;
        throw error;
      });
    }
    return cachedFeed;
  }

  function runLabel(run) {
    return [run.model, run.effort, run.condition, run.repeatPass, run.surface,
      run.sourceStage].filter(Boolean).join(' · ');
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
    const header = element('p', 'The same 60 development reviews · human-checked provisional labels v0.2. Each choice is one saved run, including its prompt, pass, and route.');
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
      const report = element('a', `${label} run report`);
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
            : 'A/B answer availability differs'
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

  return { FIELDS, validate, load, view, runLabel, comparisonOptions, render };
});
