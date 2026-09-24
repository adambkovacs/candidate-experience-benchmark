(() => {
  'use strict';
  const $ = (selector) => document.querySelector(selector);
  const state = { data: null, selectedId: null };
  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const num = value => Number.isFinite(Number(value)) && value !== null && value !== '' ? Number(value) : null;
  const label = value => value === null || value === undefined || value === '' ? 'Unavailable' : String(value);
  const safeUrl = value => { try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : null; } catch { return null; } };
  const formatSeconds = value => { const n = num(value); if (n === null) return 'Unavailable'; return n >= 60 ? `${(n / 60).toLocaleString(undefined, {maximumFractionDigits: 1})} min` : `${n.toLocaleString(undefined, {maximumFractionDigits: 1})} sec`; };
  const formatCount = value => { const n = num(value); return n === null ? 'Unavailable' : Math.round(n).toLocaleString(); };
  const formatMoney = value => { const n = num(value); return n === null ? null : `$${n.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 9})}`; };
  const hasCount = value => Number.isInteger(Number(value)) && value !== null && value !== '';
  const metricHtml = (value, coral = false) => `<div class="mini-metric"><strong>${hasCount(value) ? esc(value) : '—'}</strong><span class="mini-track"><span class="mini-fill${coral ? ' coral' : ''}" style="width:${hasCount(value) ? Math.max(0,Math.min(100,Number(value)/60*100)) : 0}%"></span></span></div>`;
  const displayName = run => [run.model, run.effort && run.effort !== 'n/a' ? run.effort : null].filter(Boolean).join(' · ');
  const metricLabels = {all_four:'ALL FOUR / 60',sentiment:'SENTIMENT / 60',follow_up_needed:'FOLLOW-UP / 60',serious_concern_reported:'SERIOUS CONCERN / 60',testimonial_potential:'TESTIMONIAL / 60',valid:'VALID / 60'};
  const scoreFor = run => $('#metric').value === 'valid' ? run.valid : run.metrics?.[$('#metric').value];
  const isComplete = run => run.complete === true && num(run.records) === 60;

  function filteredRuns() {
    if (!state.data) return [];
    const search = $('#search').value.trim().toLowerCase();
    const model = $('#model-filter').value;
    const effort = $('#effort-filter').value;
    const surface = $('#surface-filter').value;
    const includeIncomplete = $('#include-incomplete').checked;
    const runs = state.data.runs.filter(run =>
      (includeIncomplete || isComplete(run)) &&
      (!model || run.model === model) && (!effort || run.effort === effort) && (!surface || run.surface === surface) &&
      (!search || `${run.model} ${run.effort} ${run.surface} ${run.id}`.toLowerCase().includes(search))
    );
    switch ($('#sort').value) {
      case 'model-asc': runs.sort((a,b) => displayName(a).localeCompare(displayName(b))); break;
      case 'runtime-asc': runs.sort((a,b) => (num(a.timing?.totalSeconds) ?? Infinity) - (num(b.timing?.totalSeconds) ?? Infinity)); break;
      default: runs.sort((a,b) => (num(scoreFor(b)) ?? -1) - (num(scoreFor(a)) ?? -1) || displayName(a).localeCompare(displayName(b)));
    }
    return runs;
  }

  function renderCompare() {
    const runs = filteredRuns();
    $('#result-count').textContent = `${runs.length} saved ${runs.length === 1 ? 'view' : 'views'}`;
    $('#score-heading').textContent = metricLabels[$('#metric').value];
    $('#comparison-list').innerHTML = runs.length ? runs.map(run => `<button type="button" class="comparison-row${run.id === state.selectedId ? ' selected' : ''}" data-run="${esc(run.id)}" aria-label="Inspect ${esc(displayName(run))}"><span class="run-name">${esc(run.model)}<span class="run-meta">${esc([run.effort, run.surface, isComplete(run) ? null : `${formatCount(run.records)} / 60 records`].filter(Boolean).join(' · '))}</span><span class="run-id">${esc(run.id)}</span></span>${metricHtml(run.valid)}${metricHtml(scoreFor(run),true)}<span class="run-runtime" title="Summed request time; not elapsed wall time">${esc(formatSeconds(run.timing?.totalSeconds))}</span><span class="row-arrow" aria-hidden="true">↗</span></button>`).join('') : '<p class="empty-state">No saved views match these filters. Try another model or include partial runs.</p>';
    $('#comparison-list').querySelectorAll('[data-run]').forEach(button => button.addEventListener('click', () => selectRun(button.dataset.run, true)));
  }

  function renderStory() {
    const runs = state.data.runs.filter(isComplete).filter(run => hasCount(run.metrics?.all_four)).sort((a,b) => Number(b.metrics.all_four) - Number(a.metrics.all_four)).slice(0,8);
    $('#story-chart').innerHTML = runs.length ? runs.map(run => `<button type="button" class="story-row" data-run="${esc(run.id)}" aria-label="Inspect ${esc(displayName(run))}"><span class="story-label">${esc(run.model)}<small>${esc([run.effort,run.surface].filter(Boolean).join(' · '))}</small></span><span class="story-bar"><span class="story-bar-fill" style="width:${Math.max(0,Math.min(100,Number(run.metrics.all_four)/60*100))}%"></span><span class="story-bar-valid" style="left:${Math.max(0,Math.min(100,(num(run.valid)??0)/60*100))}%" title="${esc(label(run.valid))} valid responses"></span></span><span class="story-value">${esc(run.metrics.all_four)}<small>/ 60</small></span></button>`).join('') : '<p class="empty-state">No completed 60-record runs are available in this public snapshot.</p>';
    $('#story-chart-note').textContent = runs.length ? 'Showing up to eight completed saved views with reported all-four scores. Repeated model names may be alternate or retry views. Coral: all four fields correct. Teal marker: valid responses. The full set is below.' : '';
    $('#story-chart').querySelectorAll('[data-run]').forEach(button => button.addEventListener('click', () => selectRun(button.dataset.run, true)));
  }

  function dataRow(name, value) { return `<div><dt>${esc(name)}</dt><dd>${esc(label(value))}</dd></div>`; }
  const tokenRow = (name, value, partial) => dataRow(`${partial ? 'Known ' + name.toLowerCase() : name}`, value == null ? null : formatCount(value));
  const timingBasis = timing => timing.kind === 'batch' ? 'Summed batch request durations' : timing.kind === 'record' ? 'Summed per-record attempt durations' : 'Timing basis unavailable';
  const usageCoverage = tokens => {
    const reported = num(tokens.reportedRequests);
    const total = num(tokens.totalRequests);
    if (reported !== null && total !== null) return `${formatCount(reported)} of ${formatCount(total)} requests have token usage${tokens.complete === false ? '; totals exclude missing usage' : ''}.`;
    return tokens.complete === false ? 'Token usage is incomplete; shown totals cover only reported requests.' : '';
  };
  function stringifyValue(value) {
    if (value === null || value === undefined || value === '') return 'Unavailable';
    if (typeof value === 'object') return Object.entries(value).map(([key, v]) => `${key}: ${typeof v === 'object' ? JSON.stringify(v) : v}`).join(' · ');
    return String(value);
  }
  function caseCard(item) {
    return `<article class="case-card"><div class="case-head"><span>RECORD ${esc(item.id ?? '—')}</span><span>${esc(item.status ?? '')}</span></div><blockquote>${esc(item.feedback ?? 'Feedback unavailable')}</blockquote><div class="case-result"><div><strong>REFERENCE</strong><span>${esc(stringifyValue(item.reference))}</span></div><div><strong>MODEL OUTPUT</strong><span>${esc(stringifyValue(item.prediction))}</span></div></div>${Array.isArray(item.different_fields) && item.different_fields.length ? `<p class="note">Different fields: ${esc(item.different_fields.join(', '))}</p>` : ''}</article>`;
  }
  function renderCasePanel(run) {
    const all = state.data.cases.filter(item => item.configuration === run.id);
    const panel = $('#case-panel');
    if (!all.length) { panel.innerHTML = '<p class="note">No public examples are available for this configuration.</p>'; return; }
    panel.innerHTML = `<div class="case-controls"><label class="filter-field"><span>Find a record</span><input type="search" id="case-search" placeholder="Search ID or feedback"></label><label class="filter-field"><span>Record</span><select id="case-select"></select></label><label class="case-check"><input type="checkbox" id="case-disagreements"> Disagreements only</label></div><p class="case-counter" id="case-counter"></p><div id="case-current"></div>`;
    const update = (preserve) => {
      const query = $('#case-search').value.trim().toLowerCase();
      const disagreements = $('#case-disagreements').checked;
      const matches = all.filter(item => (!disagreements || (Array.isArray(item.different_fields) && item.different_fields.length > 0)) && (!query || `${item.id} ${item.feedback}`.toLowerCase().includes(query)));
      const select = $('#case-select');
      const previous = preserve ? select.value : null;
      select.innerHTML = matches.map((item,index) => `<option value="${index}">${esc(item.id ?? `Record ${index+1}`)}${item.different_fields?.length ? ' · differs' : ''}</option>`).join('');
      const selectedIndex = matches.findIndex(item => item.id === previous);
      if (selectedIndex >= 0) select.value = String(selectedIndex);
      $('#case-counter').textContent = `${matches.length} of ${all.length} records`;
      $('#case-current').innerHTML = matches.length ? caseCard(matches[Number(select.value) || 0]) : '<p class="empty-state">No records match. Try another search.</p>';
    };
    $('#case-search').addEventListener('input', () => update(false));
    $('#case-disagreements').addEventListener('change', () => update(false));
    $('#case-select').addEventListener('change', () => { const query = $('#case-search').value.trim().toLowerCase(); const disagreements = $('#case-disagreements').checked; const matches = all.filter(item => (!disagreements || (Array.isArray(item.different_fields) && item.different_fields.length > 0)) && (!query || `${item.id} ${item.feedback}`.toLowerCase().includes(query))); $('#case-current').innerHTML = matches[Number($('#case-select').value)] ? caseCard(matches[Number($('#case-select').value)]) : ''; });
    update(false);
  }
  function costRows(cost) {
    const actual = formatMoney(cost.actualUsd);
    const known = formatMoney(cost.knownUsd);
    const unknown = formatMoney(cost.unknownUpperBoundUsd);
    const costLabel = actual !== null ? 'Observed API cost (USD)' : known !== null ? 'Known API charges (USD)' : 'Observed API cost (USD)';
    const costValue = actual ?? known ?? 'Unavailable';
    return dataRow(costLabel, costValue) + (num(cost.unknownUpperBoundUsd) > 0 ? dataRow('Additional unknown-charge ceiling (USD)', unknown) : '');
  }
  function selectRun(id, scroll) {
    const run = state.data.runs.find(item => item.id === id);
    if (!run) return;
    state.selectedId = id;
    const timing = run.timing || {};
    const tokens = run.tokens || {};
    const cost = run.cost || {};
    const evidence = safeUrl(run.evidenceUrl);
    const metric = run.metrics || {};
    $('#run-detail').innerHTML = `<div class="detail-top"><div><h3>${esc(run.model)}</h3><p>${esc([run.effort,run.surface,run.condition].filter(Boolean).join(' · '))}</p><span class="detail-run-id">${esc(run.id)}</span></div><span class="detail-badge${isComplete(run) ? '' : ' partial'}">${isComplete(run) ? 'COMPLETE · 60 / 60' : `PARTIAL · ${esc(formatCount(run.records))} / 60`}</span></div><div class="detail-stats"><div class="detail-stat"><span>VALID / 60</span><strong>${hasCount(run.valid) ? esc(run.valid) : '—'}</strong><small>Scorable responses</small></div><div class="detail-stat"><span>CORRECT SENTIMENT / 60</span><strong>${hasCount(metric.sentiment) ? esc(metric.sentiment) : '—'}</strong><small>Matches the reference label</small></div><div class="detail-stat"><span>ALL FOUR / 60</span><strong>${hasCount(metric.all_four) ? esc(metric.all_four) : '—'}</strong><small>All four scored fields match</small></div><div class="detail-stat"><span>SUMMED REQUEST TIME</span><strong>${esc(formatSeconds(timing.totalSeconds))}</strong><small>${esc(timingBasis(timing))}${timing.complete === false ? ' · incomplete evidence' : ''}</small></div></div><div class="detail-lower"><div><h4>Recorded measures</h4><dl class="data-list">${dataRow('Follow-up needed / 60',metric.follow_up_needed)}${dataRow('Serious concern / 60',metric.serious_concern_reported)}${dataRow('Testimonial potential / 60',metric.testimonial_potential)}${dataRow('Median request time',formatSeconds(timing.medianSeconds))}${dataRow('95th percentile request time',formatSeconds(timing.p95Seconds))}${dataRow('Timed requests',timing.requests)}${tokenRow('Input tokens',tokens.input,tokens.complete === false)}${tokenRow('Output tokens',tokens.output,tokens.complete === false)}${tokenRow('Cached input tokens',tokens.cachedInput,tokens.complete === false)}${tokenRow('Cache-write tokens',tokens.cacheWrite,tokens.complete === false)}${tokenRow('Reasoning tokens',tokens.reasoning,tokens.complete === false)}${dataRow('Requests with token usage',tokens.reportedRequests == null ? null : `${formatCount(tokens.reportedRequests)} / ${tokens.totalRequests == null ? 'unknown' : formatCount(tokens.totalRequests)}`)}${costRows(cost)}</dl>${timing.note ? `<p class="note">Timing: ${esc(timing.note)}</p>` : ''}${usageCoverage(tokens) ? `<p class="note">${esc(usageCoverage(tokens))}</p>` : ''}${tokens.note ? `<p class="note">Tokens: ${esc(tokens.note)}</p>` : ''}${cost.note ? `<p class="note">Cost: ${esc(cost.note)}</p>` : ''}${cost.availability ? `<p class="note">Cost availability: ${esc(cost.availability)}</p>` : ''}${evidence ? `<a class="detail-evidence" href="${esc(evidence)}" target="_blank" rel="noopener noreferrer">Open source evidence ↗</a>` : ''}</div><div><h4>Records</h4><div id="case-panel"></div></div></div>`;
    renderCasePanel(run);
    renderCompare();
    if (scroll) $('#inspect').scrollIntoView({behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
  }

  function fillFilter(selector, values, firstLabel) {
    const select = $(selector);
    select.innerHTML = `<option value="">${esc(firstLabel)}</option>` + [...new Set(values.filter(Boolean))].sort((a,b) => String(a).localeCompare(String(b))).map(value => `<option value="${esc(value)}">${esc(value)}</option>`).join('');
  }
  function renderPrompts() {
    const comparisons = state.data.promptComparisons;
    const select = $('#prompt-model');
    if (!comparisons.length) {
      $('.prompt-section').hidden = true;
      return;
    }
    select.innerHTML = comparisons.map((item,index) => `<option value="${index}">${esc(item.model)}</option>`).join('');
    const update = () => {
      const item = comparisons[Number(select.value)] || comparisons[0];
      const evidence = safeUrl(item.evidenceUrl);
      const rows = ['P0','P1','P2'].map(condition => ({condition, value:item.conditions?.[condition]?.all_four}));
      $('#prompt-context').innerHTML = `All four fields match, out of 60.${evidence ? ` <a href="${esc(evidence)}" target="_blank" rel="noopener noreferrer">Source evidence ↗</a>` : ''}`;
      $('#prompt-chart').innerHTML = rows.map(({condition,value}) => `<div class="prompt-row"><strong>${condition}</strong><span class="prompt-track"><span class="prompt-fill" style="width:${hasCount(value) ? Math.max(0,Math.min(100,Number(value)/60*100)) : 0}%"></span></span><span>${hasCount(value) ? esc(value)+'/ 60' : '—'}</span></div>`).join('');
    };
    select.addEventListener('change', update);
    update();
  }
  function renderNative() {
    const native = state.data.nativeComparisons;
    const conditions = Array.isArray(native) ? native : native && Array.isArray(native.conditions) ? native.conditions : [];
    const section = $('.native-section');
    if (!conditions.length) { section.hidden = true; return; }
    const grouped = new Map();
    conditions.forEach(item => { if (item?.id && ['P0','P1','P2'].includes(item.condition)) { if (!grouped.has(item.id)) grouped.set(item.id, {}); grouped.get(item.id)[item.condition] = item; } });
    if (!grouped.size) { section.hidden = true; return; }
    const names = { 'anyjev-qwen06-generated-control':'AnyJev generated control', 'semif-generated-bf16':'SemIf generated BF16', 'openjev-generated-off':'OpenJev generated off', 'openjev-generated-on':'OpenJev generated on' };
    const select = $('#native-model');
    select.innerHTML = [...grouped.keys()].map(id => `<option value="${esc(id)}">${esc(names[id] || id)}</option>`).join('');
    const sourcePrefix = state.data.runs.map(run => safeUrl(run.evidenceUrl)).find(url => url && url.includes('/blob/main/'))?.split('/blob/main/')[0] + '/blob/main/';
    const sourceUrl = path => typeof path === 'string' && /^results\/[A-Za-z0-9_./-]+$/.test(path) && !path.includes('..') && sourcePrefix.startsWith('https://') ? sourcePrefix + path.split('/').map(encodeURIComponent).join('/') : null;
    const update = () => {
      const id = select.value;
      const group = grouped.get(id) || {};
      $('#native-chart').innerHTML = ['P0','P1','P2'].map(condition => {
        const item = group[condition];
        if (!item) return `<div class="native-row"><strong>${condition}</strong><span class="native-missing">No saved outcome</span></div>`;
        const score = item.correct?.all_four;
        const source = safeUrl(item.evidenceUrl) || sourceUrl(item.sourceBindings?.[0]?.file);
        const missing = Array.isArray(item.missingIds) ? item.missingIds : [];
        return `<div class="native-row"><div><strong>${condition}</strong><small>${esc(item.saved ?? '—')} / 60 saved · ${esc(item.valid ?? '—')} valid${missing.length ? ` · Missing ${esc(missing.join(', '))}` : ''}</small></div><span class="prompt-track"><span class="prompt-fill" style="width:${hasCount(score) ? Math.max(0,Math.min(100,Number(score)/60*100)) : 0}%"></span></span><div class="native-score"><span>${hasCount(score) ? esc(score) : '—'} / 60</span>${source ? `<a href="${esc(source)}" target="_blank" rel="noopener noreferrer">Evidence ↗</a>` : ''}</div></div>`;
      }).join('');
      const allLimitations = Array.isArray(native?.limitations) ? native.limitations : [];
      const key = id.startsWith('anyjev') ? /AnyJev/i : id.startsWith('semif') ? /SemIf/i : /OpenJev/i;
      const relevant = allLimitations.filter(value => key.test(value) || /synthetic references/i.test(value));
      const note = typeof native?.referenceNote === 'string' ? native.referenceNote : 'These outcomes are descriptive and have not passed the central paired-protocol audit.';
      $('#native-limitations').innerHTML = `<p class="native-caution">${esc(note)}</p>${relevant.length ? `<ul>${relevant.map(value => `<li>${esc(value)}</li>`).join('')}</ul>` : ''}`;
    };
    select.addEventListener('change', update);
    update();
  }
  function renderSources() {
    const urls = [...new Set([...state.data.runs.map(run => safeUrl(run.evidenceUrl)),...state.data.promptComparisons.map(item => safeUrl(item.evidenceUrl))].filter(Boolean))].slice(0,3);
    $('#source-links').innerHTML = urls.map((url,index) => `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">Source evidence ${index+1} ↗</a>`).join('');
    const referenceNote = state.data.referenceNote;
    if (referenceNote) $('#source-links').insertAdjacentHTML('beforebegin', `<p class="note">${esc(referenceNote)}</p>`);
  }
  async function init() {
    try {
      const response = await fetch('./data.json', {cache:'no-store'});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (!Array.isArray(data.runs) || Number(data.denominator) !== 60) throw new Error('Invalid public data shape');
      state.data = { ...data, runs:data.runs.filter(run => run && run.id), cases:Array.isArray(data.cases) ? data.cases : [], promptComparisons:Array.isArray(data.promptComparisons) ? data.promptComparisons : [], nativeComparisons:data.nativeComparisons ?? null };
      fillFilter('#model-filter',state.data.runs.map(run => run.model),'All models');
      fillFilter('#effort-filter',state.data.runs.map(run => run.effort),'All efforts');
      fillFilter('#surface-filter',state.data.runs.map(run => run.surface),'All surfaces');
      ['#search','#model-filter','#effort-filter','#surface-filter','#metric','#sort','#include-incomplete'].forEach(selector => $(selector).addEventListener(selector === '#search' ? 'input' : 'change',renderCompare));
      if (!state.data.runs.some(run => !isComplete(run))) $('#include-incomplete').closest('.toggle-row').hidden = true;
      renderStory();renderCompare();renderPrompts();renderNative();renderSources();
      const initial = state.data.runs.find(isComplete) || state.data.runs[0];
      if (initial) selectRun(initial.id,false);
    } catch(error) {
      const message = 'The public results could not be loaded. Please reload the page or check the data file.';
      $('#story-chart').innerHTML = `<p class="empty-state">${message}</p>`;
      $('#comparison-list').innerHTML = `<p class="empty-state">${message}</p>`;
      $('#run-detail').innerHTML = `<p class="empty-state">${message}</p>`;
      $('.prompt-section').hidden = true;
      $('.native-section').hidden = true;
      console.error('Public benchmark data error:', error);
    }
  }
  init();
})();
