(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const state = {data:null,selectedId:null,experiments:new Map()};
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const n = value => value === null || value === undefined || value === '' || !Number.isFinite(Number(value)) ? null : Number(value);
  const count = value => n(value) === null ? 'Unavailable' : Math.round(n(value)).toLocaleString();
  const money = value => n(value) === null ? 'Unavailable' : '$' + n(value).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:9});
  const duration = value => n(value) === null ? 'Unavailable' : n(value) >= 60 ? (n(value)/60).toLocaleString(undefined,{maximumFractionDigits:1})+' min' : n(value).toLocaleString(undefined,{maximumFractionDigits:1})+' sec';
  const url = value => {try {const parsed = new URL(value);return ['https:','http:'].includes(parsed.protocol) ? parsed.href : null;} catch {return null;}};
  const has = value => n(value) !== null;
  const complete = run => run.complete === true && n(run.records) === 60;
  const metricName = {all_four:'All four correct',sentiment:'Sentiment correct',follow_up_needed:'Follow-up correct',serious_concern_reported:'Serious concern correct',testimonial_potential:'Testimonial correct',valid:'Valid responses'};
  const score = run => $('#metric').value === 'valid' ? run.valid : run.metrics?.[$('#metric').value];
  const experimentId = run => run.parentBaselineId || run.id.replace(/--p[12]$/i,'');
  const label = run => [run.model,run.effort && run.effort !== 'not applicable' ? run.effort : null,run.surface].filter(Boolean).join(' · ');
  const dataRow = (name,value) => `<div><dt>${esc(name)}</dt><dd>${esc(value === null || value === undefined || value === '' ? 'Unavailable' : value)}</dd></div>`;
  function groups() {
    state.experiments = new Map();
    for (const run of state.data.runs) {
      const id = experimentId(run);
      if (!state.experiments.has(id)) state.experiments.set(id,[]);
      state.experiments.get(id).push(run);
    }
  }
  function renderExperimentSelect() {
    const select = $('#experiment-select');
    const entries = [...state.experiments.entries()].sort((a,b) => {
      const aj = a[0].includes('typesafe-jev113') ? 0 : 1;
      const bj = b[0].includes('typesafe-jev113') ? 0 : 1;
      return aj-bj || label(a[1][0]).localeCompare(label(b[1][0]));
    });
    select.innerHTML = entries.map(([id,runs]) => `<option value="${esc(id)}">${esc(label(runs.find(r => r.condition === 'P0') || runs[0]))} · ${esc(id)}</option>`).join('');
    const queryExperiment=new URL(location.href).searchParams.get('experiment');
    select.value = queryExperiment && state.experiments.has(queryExperiment) ? queryExperiment : entries[0]?.[0] || '';
  }
  function missingCondition(id,condition) {
    if (id === 'typesafe-jev113-v2') return {label:'NOT APPLICABLE',reason:'The TypeSafe four-choice Jev workflow has no P1/P2 prompt variant.'};
    const roster=state.data.roster || [];
    const item=roster.find(r => r.id===id || r.parentBaselineId===id);
    if (item) return {label:item.disposition==='excluded' ? 'NOT APPLICABLE' : String(item.disposition || 'NO SAVED OUTCOME').toUpperCase(),reason:item.reason || 'No public saved outcome is available.'};
    return {label:'NO SAVED OUTCOME',reason:'No public result is available for this condition.'};
  }
  function syncUrl() {
    const params=new URL(location.href).searchParams;
    const experiment=$('#experiment-select').value,metric=$('#metric').value;
    if(experiment)params.set('experiment',experiment);else params.delete('experiment');
    if(state.selectedId)params.set('run',state.selectedId);else params.delete('run');
    if(metric!=='all_four')params.set('metric',metric);else params.delete('metric');
    history.replaceState(null,'',location.pathname+(params.size?'?'+params.toString():'')+location.hash);
  }
  function renderExperiment() {
    const id = $('#experiment-select').value;
    if(state.selectedId)syncUrl();
    const runs = state.experiments.get(id) || [];
    const lead = runs.find(r => r.condition === 'P0') || runs[0];
    $('#experiment-title').textContent = lead ? label(lead) : 'No saved experiment';
    $('#experiment-context').textContent = id || '';
    const chosen = $('#metric').value;
    $('#condition-grid').innerHTML = ['P0','P1','P2'].map(condition => {
      const candidates = runs.filter(r => r.condition === condition);
      const run = candidates.find(complete) || candidates[0];
      if (!run) { const disposition=missingCondition(id,condition); return `<div class="condition-card empty"><div class="condition-card-header"><span class="condition-code">${condition}</span><span class="condition-tag">${esc(disposition.label)}</span></div><p class="condition-meta">${esc(disposition.reason)}</p></div>`; }
      const value = score(run);
      const status = complete(run) ? 'COMPLETE' : 'PARTIAL';
      return `<button type="button" class="condition-card" data-condition-run="${esc(run.id)}" aria-pressed="${run.id === state.selectedId}"><span class="condition-card-header"><span class="condition-code">${condition}</span><span class="condition-tag">${status} · ${esc(count(run.records))} / 60 SAVED</span></span><span class="condition-score">${has(value) ? esc(value) : '—'}<small> / 60</small></span><span class="condition-track" aria-hidden="true"><span style="width:${has(value) ? Math.max(0,Math.min(100,n(value)/60*100)) : 0}%"></span></span><span class="condition-meta">${esc(metricName[chosen])} · ${esc(run.id)}</span></button>`;
    }).join('');
    $('#condition-grid').querySelectorAll('[data-condition-run]').forEach(button => button.addEventListener('click',() => selectRun(button.dataset.conditionRun,true)));
    const nonpaired = runs.some(r => r.pairedEligible === false);
    $('#experiment-note').textContent = `${runs.length} saved condition ${runs.length === 1 ? 'view' : 'views'} for this experiment. ${nonpaired ? 'At least one outcome is descriptive and outside the strict paired comparison.' : 'Check each run’s evidence and execution notes before comparing conditions.'}`;
  }
  function visibleRuns() {
    const query = $('#search').value.trim().toLowerCase();
    const condition = $('#condition-filter').value;
    const surface = $('#surface-filter').value;
    const include = $('#include-incomplete').checked;
    const runs = state.data.runs.filter(r => (include || complete(r)) && (!condition || r.condition === condition) && (!surface || r.surface === surface) && (!query || `${r.id} ${r.model} ${r.effort} ${r.surface} ${experimentId(r)}`.toLowerCase().includes(query)));
    if ($('#sort').value === 'model-asc') runs.sort((a,b) => label(a).localeCompare(label(b)) || a.condition.localeCompare(b.condition));
    else runs.sort((a,b) => (n(score(b)) ?? -1)-(n(score(a)) ?? -1) || label(a).localeCompare(label(b)));
    return runs;
  }
  function renderLedger() {
    const runs = visibleRuns();
    $('#result-count').textContent = `${runs.length} visible / ${state.data.runs.length} saved views`;
    $('#score-heading').textContent = `${metricName[$('#metric').value].toUpperCase()} / 60`;
    $('#comparison-list').innerHTML = runs.length ? runs.map(r => `<button type="button" class="comparison-row${r.id === state.selectedId ? ' selected' : ''}" data-run="${esc(r.id)}" aria-label="Inspect ${esc(label(r))}, ${esc(r.condition)}"><span class="run-name">${esc(r.model)}<span class="run-meta">${esc([r.effort,r.surface,complete(r)?null:`partial · ${count(r.records)} / 60`].filter(Boolean).join(' · '))}</span><span class="run-id">${esc(r.id)}</span></span><span>${esc(r.condition)}</span><span class="metric-value"><strong>${has(r.valid) ? esc(r.valid) : '—'}</strong><small> / 60</small></span><span class="metric-value"><strong>${has(score(r)) ? esc(score(r)) : '—'}</strong><small> / 60</small></span><span class="run-runtime">${esc(duration(r.timing?.totalSeconds))}</span></button>`).join('') : '<p class="empty-state">No saved outcomes match these filters. Clear the search or include partial outcomes.</p>';
    $('#comparison-list').querySelectorAll('[data-run]').forEach(button => button.addEventListener('click',() => selectRun(button.dataset.run,true)));
  }
  function caseValue(value) {
    if (value === null || value === undefined || value === '') return 'Unavailable';
    if (typeof value === 'object') return Object.entries(value).map(([key,v]) => `${key}: ${typeof v === 'object' ? JSON.stringify(v) : v}`).join(' · ');
    return String(value);
  }
  function caseCard(item) {
    return `<article class="case-card"><div class="case-head"><span>RECORD ${esc(item.id || '—')}</span><span>${esc(item.status || '')}</span></div><blockquote>${esc(item.feedback || 'Feedback unavailable')}</blockquote><div class="case-result"><div><strong>REFERENCE</strong><span>${esc(caseValue(item.reference))}</span></div><div><strong>MODEL OUTPUT</strong><span>${esc(caseValue(item.prediction))}</span></div></div>${Array.isArray(item.different_fields) && item.different_fields.length ? `<p class="note">Different fields: ${esc(item.different_fields.join(', '))}</p>` : ''}</article>`;
  }
  function renderCases(run) {
    const all = state.data.cases.filter(item => item.configuration === run.id);
    const panel = $('#case-panel');
    if (!all.length) {panel.innerHTML = '<p class="empty-state">No public record examples are saved for this run.</p>';return;}
    panel.innerHTML = `<div class="case-controls"><label><span>Find a record</span><input type="search" id="case-search" placeholder="Search ID or feedback"></label><label><span>Record</span><select id="case-select"></select></label><label class="case-check"><input type="checkbox" id="case-disagreements"> Disagreements only</label></div><p class="case-counter" id="case-counter"></p><div id="case-current"></div>`;
    let matches=[];
    const update = () => {
      const query = $('#case-search').value.toLowerCase().trim();
      matches=all.filter(item => (!$('#case-disagreements').checked || item.different_fields?.length) && (!query || `${item.id} ${item.feedback}`.toLowerCase().includes(query)));
      $('#case-select').innerHTML=matches.map((item,index) => `<option value="${index}">${esc(item.id || `Record ${index+1}`)}${item.different_fields?.length ? ' · differs' : ''}</option>`).join('');
      $('#case-counter').textContent=`${matches.length} of ${all.length} saved records`;
      $('#case-current').innerHTML=matches.length ? caseCard(matches[0]) : '<p class="empty-state">No records match this search.</p>';
    };
    $('#case-search').addEventListener('input',update);
    $('#case-disagreements').addEventListener('change',update);
    $('#case-select').addEventListener('change',() => {$('#case-current').innerHTML=matches[Number($('#case-select').value)] ? caseCard(matches[Number($('#case-select').value)]) : '';});
    update();
  }
  function resourceSection(title,rows,note) {return `<section class="resource-group"><h5>${esc(title)}</h5><dl class="data-list">${rows.join('')}</dl>${note ? `<p class="note">${esc(note)}</p>` : ''}</section>`;}
  function timingRows(timing,run) {
    const basis=timing.kind === 'batch' ? 'Summed batch request durations' : timing.kind === 'record' ? 'Summed per-record attempt durations' : 'Timing basis unavailable';
    const caution=run.surface === 'Local / specialist' ? 'Local time is a workflow diagnostic on the test machine, not a hosted-speed ranking. ' : timing.kind === 'batch' ? 'Batch request time is not per-record latency or concurrent wall time. ' : '';
    return resourceSection('Time',[dataRow('Summed request time',duration(timing.totalSeconds)),dataRow('Basis',basis),dataRow('Median request time',duration(timing.medianSeconds)),dataRow('95th percentile request time',duration(timing.p95Seconds)),dataRow('Timed requests',count(timing.requests))],caution+(timing.note || (timing.complete === false ? 'Timing is incomplete.' : 'Request durations are not concurrent wall time.')));
  }
  function tokenRows(tokens) {
    const partial=tokens.complete === false;
    const prefix=partial ? 'Known ' : '';
    const rows=[['Input tokens','input'],['Output tokens','output'],['Cached input tokens','cachedInput'],['Cache-write tokens','cacheWrite'],['Reasoning tokens','reasoning']].map(([name,key]) => dataRow(partial ? prefix+name.toLowerCase() : name,count(tokens[key])));
    rows.push(dataRow('Requests with token usage',n(tokens.reportedRequests) === null ? 'Unavailable' : `${count(tokens.reportedRequests)} / ${count(tokens.totalRequests)}`));
    const coverage=partial ? 'Totals exclude requests with missing usage. ' : '';
    return resourceSection('Tokens',rows,coverage+(tokens.note || ''));
  }
  function costRows(cost) {
    const rows=[];
    if (n(cost.actualUsd) !== null) rows.push(dataRow('Observed API charges',money(cost.actualUsd)));
    else if (n(cost.knownUsd) !== null) rows.push(dataRow('Known API charges',money(cost.knownUsd)));
    else rows.push(dataRow('Observed API charges','Unavailable'));
    if (n(cost.estimatedUsd) !== null) rows.push(dataRow('API price estimate, not billed',money(cost.estimatedUsd)));
    if (n(cost.unknownUpperBoundUsd) > 0) rows.push(dataRow('Additional unknown-charge ceiling',money(cost.unknownUpperBoundUsd)));
    return resourceSection('Money · USD',rows,cost.note || 'Subscription fees are not allocated per run.');
  }
  function selectRun(id,scroll) {
    const run=state.data.runs.find(r => r.id === id);if (!run)return;
    state.selectedId=id;
    $('#experiment-select').value=experimentId(run);
    syncUrl();
    const timing=run.timing || {},tokens=run.tokens || {},cost=run.cost || {},metrics=run.metrics || {};
    const evidence=url(run.evidenceUrl);
    $('#run-detail').innerHTML=`<div class="detail-top"><div><h3>${esc(run.model)}</h3><p>${esc([run.effort,run.surface,run.condition].filter(Boolean).join(' · '))}</p><span class="detail-run-id">${esc(run.id)}</span></div><span class="detail-badge${complete(run)?'':' partial'}">${complete(run)?'COMPLETE':'PARTIAL'} · ${esc(count(run.records))} / 60 SAVED</span></div><div class="detail-stats"><div class="detail-stat"><span>VALID / 60</span><strong>${has(run.valid)?esc(run.valid):'—'}</strong><small>Scorable responses</small></div><div class="detail-stat"><span>ALL FOUR / 60</span><strong>${has(metrics.all_four)?esc(metrics.all_four):'—'}</strong><small>Every field matches</small></div><div class="detail-stat"><span>CORRECT SENTIMENT / 60</span><strong>${has(metrics.sentiment)?esc(metrics.sentiment):'—'}</strong><small>Reference agreement</small></div><div class="detail-stat"><span>SUMMED REQUEST TIME</span><strong>${esc(duration(timing.totalSeconds))}</strong><small>Not elapsed batch wall time</small></div></div><div class="detail-lower"><div><h4>Recorded measures</h4><dl class="data-list">${dataRow('Sentiment correct / 60',count(metrics.sentiment))}${dataRow('Follow-up correct / 60',count(metrics.follow_up_needed))}${dataRow('Serious concern correct / 60',count(metrics.serious_concern_reported))}${dataRow('Testimonial correct / 60',count(metrics.testimonial_potential))}</dl>${timingRows(timing,run)}${tokenRows(tokens)}${costRows(cost)}${run.resultStatus ? `<p class="note">Result status: ${esc(run.resultStatus)}</p>` : ''}${run.pairedEligible === false ? '<p class="note">Descriptive outcome; outside the strict paired comparison.</p>' : ''}${evidence ? `<a class="detail-evidence" href="${esc(evidence)}" target="_blank" rel="noopener noreferrer">Open source evidence ↗</a>` : ''}</div><div><h4>Record examples</h4><div id="case-panel"></div></div></div>`;
    renderCases(run);renderFieldComparison(run);renderLedger();renderExperiment();
    if (scroll) $('#inspect').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
  }
  function renderFieldComparison(run) {
    const jev=state.data.runs.find(r => r.id === 'typesafe-jev113-v2');
    if(!jev){$('#field-comparison').hidden=true;return;}
    const fields=[['Valid responses','valid'],['All four correct','all_four'],['Sentiment correct','sentiment'],['Follow-up correct','follow_up_needed'],['Serious concern correct','serious_concern_reported'],['Testimonial correct','testimonial_potential']];
    const get=(r,key)=>key==='valid'?r.valid:r.metrics?.[key];
    $('#field-comparison').innerHTML=`<h3>Jev and selected run, field by field.</h3><p>Each bar is a count out of 60. These saved views can differ in prompt, effort and execution surface; read the run notes before drawing comparisons.</p>${fields.map(([name,key]) => { const a=get(jev,key),b=get(run,key);return `<div class="field-row"><span>${esc(name)}</span><div><span class="field-track"><span style="width:${has(a)?Math.max(0,Math.min(100,n(a)/60*100)):0}%"></span></span><span class="field-track selected"><span style="width:${has(b)?Math.max(0,Math.min(100,n(b)/60*100)):0}%"></span></span></div><strong>${has(a)?esc(a):'—'} vs ${has(b)?esc(b):'—'}</strong></div>`;}).join('')}<div class="field-key"><span></span>Jev (first number) <span></span>${esc(run.model)} (second number)</div>`;
  }
  function renderRoster() {
    const roster=state.data.roster;
    if(!roster.length){$('.availability').hidden=true;return;}
    const query=$('#roster-search').value.toLowerCase().trim();
    const entries=roster.filter(item => {const base=state.data.runs.find(r=>r.id===item.parentBaselineId);return !query || `${item.id} ${base?.model||''} ${item.disposition}`.toLowerCase().includes(query);});
    $('#roster-count').textContent=`${entries.length} of ${roster.length} setup dispositions`;
    $('#roster-list').innerHTML=entries.length ? entries.map(item => `<div class="roster-row"><strong>${esc(item.id)}</strong><span>${esc(item.disposition)}</span><p>${esc(item.reason)}</p></div>`).join('') : '<p class="empty-state">No setup matches this search.</p>';
  }
  function initSources() {
    $('#reference-note').textContent=state.data.referenceNote || $('#reference-note').textContent;
    const links=[...new Set(state.data.runs.map(r => url(r.evidenceUrl)).filter(Boolean))].slice(0,3);
    $('#source-links').innerHTML=links.map((link,index) => `<a href="${esc(link)}" target="_blank" rel="noopener noreferrer">Run evidence ${index+1} ↗</a>`).join('');
  }
  function initJev() {
    const jev=state.data.runs.find(r => r.id === 'typesafe-jev113-v2') || state.data.runs.find(r => /typesafe.*jev/i.test(r.id) && r.condition === 'P0');
    if (!jev) {$('#jev').hidden=true;return;}
    $('#jev-score').innerHTML=`${has(jev.metrics?.all_four) ? esc(jev.metrics.all_four) : '—'}<small>/ 60</small>`;
    const estimate=money(jev.cost?.estimatedUsd);
    $('#jev-note').textContent=`${jev.id} · P0 · ${count(jev.valid)} valid / 60 · development API price estimate ${estimate}; actual provider charges unavailable. The summed request time includes recorded attempts, including the failed attempt.`;
    $('#inspect-jev').addEventListener('click',() => selectRun(jev.id,true));
  }
  async function init() {
    try {
      const response=await fetch('./data.json',{cache:'no-store'});if(!response.ok)throw new Error(`HTTP ${response.status}`);
      const data=await response.json();if(!Array.isArray(data.runs)||n(data.denominator)!==60)throw new Error('Invalid public data');
      state.data={...data,runs:data.runs.filter(r => r?.id && ['P0','P1','P2'].includes(r.condition)),cases:Array.isArray(data.cases)?data.cases:[],roster:Array.isArray(data.roster)?data.roster:[]};
      const queryMetric=new URL(location.href).searchParams.get('metric');if(queryMetric && Object.prototype.hasOwnProperty.call(metricName,queryMetric))$('#metric').value=queryMetric;
      groups();renderExperimentSelect();
      $('#surface-filter').innerHTML='<option value="">All surfaces</option>'+[...new Set(state.data.runs.map(r=>r.surface).filter(Boolean))].sort().map(s => `<option value="${esc(s)}">${esc(s)}</option>`).join('');
      $('#experiment-select').addEventListener('change',() => {const group=state.experiments.get($('#experiment-select').value)||[];const lead=group.find(r=>r.condition==='P0')||group[0];if(lead)selectRun(lead.id,false);else renderExperiment();});
      $('#metric').addEventListener('change',() => {renderExperiment();renderLedger();if(state.selectedId)selectRun(state.selectedId,false);});
      ['#search','#condition-filter','#surface-filter','#sort','#include-incomplete'].forEach(selector => $(selector).addEventListener(selector==='#search'?'input':'change',renderLedger));
      if (!state.data.runs.some(r => !complete(r))) $('#include-incomplete').closest('label').hidden=true;
      $('#roster-search').addEventListener('input',renderRoster);
      initSources();initJev();renderRoster();renderLedger();renderExperiment();
      const jev=state.data.runs.find(r => r.id === 'typesafe-jev113-v2');
      const queryRun=new URL(location.href).searchParams.get('run');
      const initial=state.data.runs.find(r => r.id===queryRun) || (state.experiments.get($('#experiment-select').value)||[]).find(r => r.condition==='P0') || jev || state.data.runs.find(complete) || state.data.runs[0];if(initial)selectRun(initial.id,false);
    } catch(error) {
      const message='Public results could not be loaded. Reload the page or check the data file.';
      for (const selector of ['#comparison-list','#condition-grid','#run-detail']) $(selector).innerHTML=`<p class="empty-state">${message}</p>`;
      $('#experiment-title').textContent=message;$('#jev-note').textContent=message;
      console.error('Public explorer data error:',error);
    }
  }
  init();
})();
