(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const state = {data:null,selectedId:null,experiments:new Map(),pairSelection:new Map(),overviewAll:false};
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const n = value => value === null || value === undefined || value === '' || !Number.isFinite(Number(value)) ? null : Number(value);
  const count = value => n(value) === null ? 'Unavailable' : Math.round(n(value)).toLocaleString();
  const money = value => n(value) === null ? 'Unavailable' : '$' + n(value).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:9});
  const duration = value => n(value) === null ? 'Unavailable' : n(value) >= 60 ? (n(value)/60).toLocaleString(undefined,{maximumFractionDigits:1})+' min' : n(value).toLocaleString(undefined,{maximumFractionDigits:1})+' sec';
  const url = value => {try {const parsed = new URL(value);return ['https:','http:'].includes(parsed.protocol) ? parsed.href : null;} catch {return null;}};
  const has = value => n(value) !== null;
  const complete = run => run.complete === true && n(run.records) === 60;
  const metricName = {all_four:'All four match',sentiment:'Sentiment matches',follow_up_needed:'Follow-up matches',serious_concern_reported:'Serious concern matches',testimonial_potential:'Testimonial matches',valid:'Valid responses'};
  const score = run => $('#metric').value === 'valid' ? run.valid : run.metrics?.[$('#metric').value];
  const inferenceTime = timing => n(timing?.inferenceSeconds) !== null && n(timing?.inferenceReportedRequests) > 0 ? duration(timing.inferenceSeconds) : 'Unavailable';
  const observedCost = cost => n(cost?.actualUsd) !== null ? money(cost.actualUsd) : n(cost?.knownUsd) !== null ? money(cost.knownUsd) : 'Unavailable';
  const costSummary = cost => `${n(cost?.actualUsd) !== null ? 'Observed charge ' + money(cost.actualUsd) : n(cost?.knownUsd) !== null ? 'Known charge ' + money(cost.knownUsd) : 'Observed charge unavailable'}${n(cost?.estimatedUsd) !== null ? ' · Estimate ' + money(cost.estimatedUsd) : ''}`;
  const providerGenerationTime = timing => n(timing?.providerGenerationSeconds) !== null && n(timing?.providerGenerationReportedRequests) > 0 ? duration(timing.providerGenerationSeconds) : null;
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
  function renderModelSelect() {
    const select=$('#compare-run-select');
    const query=$('#compare-search').value.trim().toLowerCase();
    const matches=state.data.runs.filter(r=>complete(r) && r.id !== 'typesafe-jev113-v2' && (!query || `${r.model} ${r.id} ${r.effort} ${r.surface}`.toLowerCase().includes(query))).sort((a,b)=>label(a).localeCompare(label(b)) || a.condition.localeCompare(b.condition));
    select.innerHTML='<option value="">Choose another run</option>'+matches.map(r=>`<option value="${esc(r.id)}">${esc(label(r))} · ${esc(r.condition)} · ${esc(r.id)}</option>`).join('');
    select.value=matches.some(r=>r.id===state.selectedId) ? state.selectedId : '';
  }
  function missingCondition(id,condition) {
    if (id === 'typesafe-jev113-v2') return {label:'NO SAVED RESULT',reason:'No public saved result for this native Jev instruction version yet.'};
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
  function renderOverview() {
    const condition=$('#overview-condition').value;
    const hostedOnly=$('#overview-hosted').checked;
    const runs=state.data.runs.filter(r=>r.condition===condition && complete(r) && n(r.metrics?.all_four)!==null && (!hostedOnly || r.surface!=='Local / specialist')).sort((a,b)=>n(b.metrics.all_four)-n(a.metrics.all_four) || label(a).localeCompare(label(b)) || a.id.localeCompare(b.id));
    const visible=state.overviewAll ? runs : runs.slice(0,8);
    const jev=runs.find(r=>r.id==='typesafe-jev113-v2' || r.nativeInstructionComparison === true);
    const fallback=state.data.runs.find(r=>r.id==='typesafe-jev113-v2');
    const reference=!state.overviewAll && jev && !visible.includes(jev) ? jev : !state.overviewAll && !jev && fallback ? fallback : null;
    const row=(run,referenceRow=false)=>`<button type="button" class="overview-row${run.id===state.selectedId?' selected':''}${referenceRow?' reference':''}" data-overview-run="${esc(run.id)}" aria-label="Inspect ${esc(label(run))}, ${esc(run.condition)}, ${esc(run.metrics?.all_four)} of 60 matches"><span class="overview-row-name"><strong>${esc(run.model)}</strong><small>${esc([run.effort,run.surface,run.condition,run.id].filter(Boolean).join(' · '))}</small>${referenceRow ? `<em>${run.condition === condition ? 'Jev reference outside the first eight shown' : 'Jev P0 reference · different prompt version'}</em>` : ''}</span><span class="overview-row-track" aria-hidden="true"><span style="width:${Math.max(0,Math.min(100,n(run.metrics.all_four)/60*100))}%"></span></span><strong class="overview-row-score">${esc(run.metrics.all_four)} / 60</strong><small class="overview-row-cost">${esc(costSummary(run.cost))}</small></button>`;
    const extra=reference && !visible.includes(reference) ? row(reference,true) : '';
    $('#overview-count').textContent=`${state.overviewAll ? runs.length : Math.min(8,runs.length)} of ${runs.length} complete ${hostedOnly?'hosted ':''}${condition} runs shown${extra ? reference.condition === condition ? ', plus Jev reference' : ', plus Jev P0 for context' : ''}.`;
    $('#overview-rows').innerHTML=visible.map(r=>row(r)).join('')+extra || '<p class="empty-state">No complete runs match these settings.</p>';
    $('#overview-rows').querySelectorAll('[data-overview-run]').forEach(button=>button.addEventListener('click',()=>selectRun(button.dataset.overviewRun,true)));
    const toggle=$('#overview-toggle');toggle.hidden=runs.length<=8;toggle.textContent=state.overviewAll?'Show first eight':'Show all complete runs';toggle.setAttribute('aria-expanded',String(state.overviewAll));
  }
  function renderExperiment() {
    const id = $('#experiment-select').value;
    if(state.selectedId)syncUrl();
    const runs = state.experiments.get(id) || [];
    const lead = runs.find(r => r.condition === 'P0') || runs[0];
    $('#experiment-title').textContent = lead ? label(lead) : 'No saved result for this setup';
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
    $('#experiment-note').textContent = id === 'typesafe-jev113-v2' ? `${runs.length} saved ${runs.length === 1 ? 'run' : 'runs'} for Jev. Its instruction versions change native Choice questions, not chat system prompts. The P0 run was made earlier in a single pass.` : `${runs.length} saved ${runs.length === 1 ? 'run' : 'runs'} for this setup. ${nonpaired ? 'Some runs cannot be compared record by record; check their notes.' : 'Read the run notes before treating a score change as a prompt effect.'}`;
    renderAuditedComparison(id);
  }
  function renderAuditedComparison(id) {
    let panel = $('#audited-comparison');
    if (!panel) {
      panel = document.createElement('section');
      panel.id = 'audited-comparison';
      panel.className = 'audited-comparison';
      panel.setAttribute('aria-label','Recorded prompt comparison');
      $('#experiment-note').after(panel);
      panel.addEventListener('change',event => {
        const experiment = $('#experiment-select').value;
        const selection = state.pairSelection.get(experiment) || {};
        if (event.target.id === 'pair-select') state.pairSelection.set(experiment,{pair:event.target.value,caseIndex:0});
        else if (event.target.id === 'pair-case-select') state.pairSelection.set(experiment,{...selection,caseIndex:Number(event.target.value)});
        else return;
        renderAuditedComparison(experiment);
        panel.querySelector(`#${event.target.id}`)?.focus();
      });
    }
    const strict=(state.data.promptComparisons || []).find(item => item.id === id && item.eligible === true);
    const native=!strict && (state.data.nativeInstructionComparisons || []).find(item => item.id === id);
    const report=strict || native;
    if (!report) {panel.hidden = true;panel.innerHTML = '';return;}
    panel.hidden = false;
    panel.setAttribute('aria-label',native ? 'Jev instruction comparison' : 'Recorded prompt comparison');
    const names = {P0_to_P1:'P0 → P1',P0_to_P2:'P0 → P2',P1_to_P2:'P1 → P2'};
    const available = Object.keys(names).filter(key => report.comparisons?.[key]);
    const selection = state.pairSelection.get(id) || {};
    const pairKey = available.includes(selection.pair) ? selection.pair : available[0];
    if (!pairKey) {panel.hidden = true;panel.innerHTML = '';return;}
    const pair = report.comparisons[pairKey];
    const cases = Array.isArray(pair.cases) ? pair.cases : [];
    const caseIndex = Number.isInteger(selection.caseIndex) && selection.caseIndex >= 0 && selection.caseIndex < cases.length ? selection.caseIndex : 0;
    const item = cases[caseIndex];
    const [before,after] = pairKey.split('_to_');
    const evidence = url(report.evidenceUrl);
    const allFourGain = Array.isArray(pair.allFourWrongToCorrect) ? pair.allFourWrongToCorrect.length : 0;
    const allFourLoss = Array.isArray(pair.allFourCorrectToWrong) ? pair.allFourCorrectToWrong.length : 0;
    panel.innerHTML = `<div class="audited-heading"><div><p class="eyebrow">${native ? 'Jev instruction comparison' : 'Recorded prompt comparison'}</p><h4>Compare the saved answers</h4></div>${evidence ? `<a href="${esc(evidence)}" target="_blank" rel="noopener noreferrer">Read the comparison report ↗</a>` : ''}</div><p class="audited-method">The same 60 fictional comments were used. These counts describe the saved answers. ${native ? 'Jev P1 and P2 change native Choice questions, not chat system prompts. Its P0 was run earlier in one pass. ' : ''}${esc(report.comparisonLimit || report.historicalP0Limitation || '')}</p><label class="audited-pair-control"><span>Choose two prompt versions</span><select id="pair-select">${available.map(key => `<option value="${key}"${key === pairKey ? ' selected' : ''}>${names[key]}</option>`).join('')}</select></label><div class="audited-counts" role="status" aria-live="polite" aria-atomic="true"><div><strong>${esc(count(pair.bothValid))} / 60</strong><span>valid in both runs</span></div><div><strong>${esc(count(pair.changedRecordCount))}</strong><span>reviews with changed outputs</span></div><div><strong>${esc(count(allFourGain))} / ${esc(count(allFourLoss))}</strong><span>gained / lost matches on all four</span></div></div>${item ? `<div class="audited-record"><label><span>Comment with a changed answer</span><select id="pair-case-select">${cases.map((entry,index) => `<option value="${index}"${index === caseIndex ? ' selected' : ''}>${esc(entry.id)}</option>`).join('')}</select></label><article class="case-card"><div class="case-head"><span>REVIEW ${esc(item.id)}</span><span>${esc(readableValue(item.from_state))} → ${esc(readableValue(item.to_state))}</span></div><blockquote>${esc(item.feedback || 'Comment unavailable')}</blockquote><div class="audited-predictions"><div><strong>BEFORE · ${before}</strong><span>${esc(caseValue(item.from_prediction))}</span></div><div><strong>AFTER · ${after}</strong><span>${esc(caseValue(item.to_prediction))}</span></div><div><strong>REFERENCE</strong><span>${esc(caseValue(item.reference))}</span></div></div></article></div>` : '<p class="note">No changed review is listed for this pair.</p>'}${report.referenceStatus ? `<p class="note">Reference status: ${esc(report.referenceStatus)}</p>` : ''}`;
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
    $('#result-count').textContent = `${runs.length} shown / ${state.data.runs.length} saved runs`;
    $('#score-heading').textContent = `${metricName[$('#metric').value].toUpperCase()} / 60`;
    $('#comparison-list').innerHTML = runs.length ? runs.map(r => `<button type="button" class="comparison-row${r.id === state.selectedId ? ' selected' : ''}" data-run="${esc(r.id)}" aria-label="Inspect ${esc(label(r))}, ${esc(r.condition)}"><span class="run-name">${esc(r.model)}<span class="run-meta">${esc([r.effort,r.surface,complete(r)?null:`partial · ${count(r.records)} / 60`].filter(Boolean).join(' · '))}</span><span class="run-id">${esc(r.id)}</span></span><span>${esc(r.condition)}</span><span class="metric-value"><strong>${has(r.valid) ? esc(r.valid) : '—'}</strong><small> / 60</small></span><span class="metric-value"><strong>${has(score(r)) ? esc(score(r)) : '—'}</strong><small> / 60</small></span><span class="run-runtime"><span>In ${esc(count(r.tokens?.input))} · Out ${esc(count(r.tokens?.output))}</span><small>Reasoning ${esc(count(r.tokens?.reasoning))} · ${esc(costSummary(r.cost))}</small>${n(r.cost?.unknownUpperBoundUsd) > 0 ? `<small>Possible extra charge ≤ ${esc(money(r.cost.unknownUpperBoundUsd))}</small>` : ''}<small>Inference ${esc(inferenceTime(r.timing))}${providerGenerationTime(r.timing) ? ` · Provider generation ${esc(providerGenerationTime(r.timing))}` : ''}</small></span></button>`).join('') : '<p class="empty-state">No runs match these filters. Clear the search or show runs with missing records.</p>';
    $('#comparison-list').querySelectorAll('[data-run]').forEach(button => button.addEventListener('click',() => selectRun(button.dataset.run,true)));
  }
  const decisionLabels = {sentiment:'Sentiment',follow_up_needed:'Follow-up needed',serious_concern_reported:'Serious concern reported',testimonial_potential:'Testimonial potential'};
  const readableValue = value => String(value ?? '').replaceAll('_',' ');
  function caseValue(value) {
    if (value === null || value === undefined || value === '') return 'Unavailable';
    if (typeof value === 'object') return Object.entries(value).map(([key,v]) => `${decisionLabels[key] || readableValue(key)}: ${typeof v === 'object' ? JSON.stringify(v) : readableValue(v)}`).join(' · ');
    return String(value);
  }
  function caseCard(item) {
    return `<article class="case-card"><div class="case-head"><span>RECORD ${esc(item.id || '—')}</span><span>${esc(readableValue(item.status || ''))}</span></div><blockquote>${esc(item.feedback || 'Comment unavailable')}</blockquote><div class="case-result"><div><strong>REFERENCE</strong><span>${esc(caseValue(item.reference))}</span></div><div><strong>MODEL OUTPUT</strong><span>${esc(caseValue(item.prediction))}</span></div></div>${Array.isArray(item.different_fields) && item.different_fields.length ? `<p class="note">Decisions that differ: ${esc(item.different_fields.map(key => decisionLabels[key] || readableValue(key)).join(', '))}</p>` : ''}</article>`;
  }
  function renderCases(run) {
    const all = state.data.cases.filter(item => item.configuration === run.id);
    const panel = $('#case-panel');
    if (!all.length) {panel.innerHTML = '<p class="empty-state">No individual comments are available for this run.</p>';return;}
    panel.innerHTML = `<div class="case-controls"><label><span>Find a comment</span><input type="search" id="case-search" placeholder="Search ID or comment"></label><label><span>Comment</span><select id="case-select"></select></label><label class="case-check"><input type="checkbox" id="case-disagreements"> Show disagreements only</label></div><p class="case-counter" id="case-counter"></p><div id="case-current"></div>`;
    let matches=[];
    const update = () => {
      const query = $('#case-search').value.toLowerCase().trim();
      matches=all.filter(item => (!$('#case-disagreements').checked || item.different_fields?.length) && (!query || `${item.id} ${item.feedback}`.toLowerCase().includes(query)));
      $('#case-select').innerHTML=matches.map((item,index) => `<option value="${index}">${esc(item.id || `Record ${index+1}`)}${item.different_fields?.length ? ' · differs' : ''}</option>`).join('');
      $('#case-counter').textContent=`${matches.length} of ${all.length} saved comments`;
      $('#case-current').innerHTML=matches.length ? caseCard(matches[0]) : '<p class="empty-state">No comments match this search.</p>';
    };
    $('#case-search').addEventListener('input',update);
    $('#case-disagreements').addEventListener('change',update);
    $('#case-select').addEventListener('change',() => {$('#case-current').innerHTML=matches[Number($('#case-select').value)] ? caseCard(matches[Number($('#case-select').value)]) : '';});
    update();
  }
  function resourceSection(title,rows,note) {return `<section class="resource-group"><h5>${esc(title)}</h5><dl class="data-list">${rows.join('')}</dl>${note ? `<p class="note">${esc(note)}</p>` : ''}</section>`;}
  function timingRows(timing,run) {
    const basis=timing.kind === 'batch' ? 'One request could include several comments' : timing.kind === 'record' ? 'One request per comment or retry' : 'Request size unavailable';
    const caution=run.surface === 'Local / specialist' ? 'Local timing reflects this machine and workflow. ' : timing.kind === 'batch' ? 'A batch request may cover several comments; its duration is not time per comment. ' : '';
    const rows=[dataRow('Median client request duration',duration(timing.medianSeconds)),dataRow('Request size',basis),dataRow('Sum of recorded request durations',duration(timing.totalSeconds)),dataRow('95th percentile request duration',duration(timing.p95Seconds)),dataRow('Requests timed',count(timing.requests))];
    if(providerGenerationTime(timing))rows.push(dataRow('Median provider generation duration',providerGenerationTime(timing)));
    return resourceSection('Technical timing',rows,caution+(timing.note || (timing.complete === false ? 'Timing is incomplete.' : 'The sum is not the elapsed time for concurrent work.')));
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
    if (n(cost.unknownUpperBoundUsd) > 0) rows.push(dataRow('Possible additional charge, upper bound',money(cost.unknownUpperBoundUsd)));
    return resourceSection('Cost in USD',rows,cost.note || 'Subscription fees are not allocated per run.');
  }
  function renderUsage(run) {
    const timing=run.timing || {},tokens=run.tokens || {},cost=run.cost || {};
    const coverage=n(tokens.reportedRequests) === null ? 'Usage coverage unavailable' : `${count(tokens.reportedRequests)} of ${count(tokens.totalRequests)} requests reported token use`;
    const actualLabel=n(cost.actualUsd) !== null ? 'Observed API charge' : n(cost.knownUsd) !== null ? 'Known API charge' : 'Observed API charge';
    const inferred=inferenceTime(timing);
    const generation=providerGenerationTime(timing);
    const inferenceNote=inferred === 'Unavailable' ? 'No server inference duration was reported for this run. Client request timing appears in the technical details below.' : `${count(timing.inferenceReportedRequests)} requests reported server inference time. ${timing.inferenceBasis || ''}`;
    const evidence=url(run.evidenceUrl);
    $('#usage-summary').innerHTML=`<div class="usage-heading"><h3>${esc(run.model)} <small>${esc(run.condition)} · ${esc(run.id)}</small></h3>${evidence ? `<a href="${esc(evidence)}" target="_blank" rel="noopener noreferrer">Source report ↗</a>` : ''}</div><div class="usage-grid"><article><span class="usage-label">Server inference time</span><strong>${esc(inferred)}</strong><p>${esc(inferenceNote)}</p>${generation ? `<dl><div><dt>Provider generation median</dt><dd>${esc(generation)}</dd></div><div><dt>Requests with generation time</dt><dd>${esc(count(timing.providerGenerationReportedRequests))} / ${esc(count(timing.providerGenerationTotalRequests))}</dd></div></dl><p>${esc(timing.providerGenerationBasis || 'Provider generation duration is not pure inference time.')}</p>` : ''}</article><article><span class="usage-label">Token use</span><dl><div><dt>Input</dt><dd>${esc(count(tokens.input))}</dd></div><div><dt>Output</dt><dd>${esc(count(tokens.output))}</dd></div><div><dt>Reasoning</dt><dd>${esc(count(tokens.reasoning))}</dd></div></dl><p>${esc(coverage)}. ${tokens.complete === false ? 'Totals cover only requests with usage data.' : ''}</p></article><article><span class="usage-label">API cost</span><dl><div><dt>${esc(actualLabel)}</dt><dd>${esc(observedCost(cost))}</dd></div><div><dt>Price estimate</dt><dd>${esc(money(cost.estimatedUsd))}</dd></div>${n(cost.unknownUpperBoundUsd) > 0 ? `<div><dt>Possible extra charge, upper bound</dt><dd>${esc(money(cost.unknownUpperBoundUsd))}</dd></div>` : ''}</dl><p>Estimates and upper bounds are not provider bills.${run.id === 'typesafe-jev113-v2' ? ' The extra amount is a reservation ceiling for one failed request.' : ''}</p></article></div>`;
  }
  function selectRun(id,scroll) {
    const run=state.data.runs.find(r => r.id === id);if (!run)return;
    state.selectedId=id;
    $('#experiment-select').value=experimentId(run);
    syncUrl();
    const timing=run.timing || {},tokens=run.tokens || {},cost=run.cost || {},metrics=run.metrics || {};
    $('#compare-run-select').value=Array.from($('#compare-run-select').options).some(option=>option.value===id) ? id : '';
    const evidence=url(run.evidenceUrl);
    $('#run-detail').innerHTML=`<div class="detail-top"><div><h3>${esc(run.model)}</h3><p>${esc([run.effort,run.surface,run.condition].filter(Boolean).join(' · '))}</p><span class="detail-run-id">${esc(run.id)}</span></div><span class="detail-badge${complete(run)?'':' partial'}">${complete(run)?'COMPLETE':'PARTIAL'} · ${esc(count(run.records))} / 60 SAVED</span></div><div class="detail-stats"><div class="detail-stat"><span>VALID / 60</span><strong>${has(run.valid)?esc(run.valid):'—'}</strong><small>Responses in the required format</small></div><div class="detail-stat"><span>ALL FOUR MATCH / 60</span><strong>${has(metrics.all_four)?esc(metrics.all_four):'—'}</strong><small>All decisions match the reference</small></div><div class="detail-stat"><span>SENTIMENT MATCHES / 60</span><strong>${has(metrics.sentiment)?esc(metrics.sentiment):'—'}</strong><small>Matches the saved reference</small></div><div class="detail-stat"><span>INPUT TOKENS</span><strong>${esc(count(tokens.input))}</strong><small>${tokens.complete === false ? 'Known usage only' : 'Reported usage'}</small></div></div><div class="detail-lower"><div><h4>Scores and resource use</h4><dl class="data-list">${dataRow('Sentiment matches / 60',count(metrics.sentiment))}${dataRow('Follow-up matches / 60',count(metrics.follow_up_needed))}${dataRow('Serious concern matches / 60',count(metrics.serious_concern_reported))}${dataRow('Testimonial matches / 60',count(metrics.testimonial_potential))}</dl>${timingRows(timing,run)}${tokenRows(tokens)}${costRows(cost)}${run.resultStatus ? `<p class="note">Result status: ${esc(run.resultStatus)}</p>` : ''}${run.nativeInstructionComparison ? '<p class="note">Native Jev instruction comparison; P0 was run earlier in a single pass.</p>' : run.pairedEligible === false ? '<p class="note">This result is not part of the record-by-record prompt comparison.</p>' : ''}${evidence ? `<a class="detail-evidence" href="${esc(evidence)}" target="_blank" rel="noopener noreferrer">Read the source report ↗</a>` : ''}</div><div><h4>Individual comments</h4><div id="case-panel"></div></div></div>`;
    renderCases(run);renderFieldComparison(run);renderUsage(run);renderLedger();renderOverview();renderExperiment();
    if (scroll) $('#inspect').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
  }
  function renderFieldComparison(run) {
    const jev=state.data.runs.find(r => r.id === 'typesafe-jev113-v2');
    if(!jev){$('#field-comparison').hidden=true;return;}
    if(run.id === jev.id){$('#field-comparison').innerHTML='<p class="comparison-invite">Choose a second run above to compare its answers with Jev.</p>';return;}
    const fields=[['Valid responses','valid'],['All four match','all_four'],['Sentiment matches','sentiment'],['Follow-up matches','follow_up_needed'],['Serious concern matches','serious_concern_reported'],['Testimonial matches','testimonial_potential']];
    const get=(r,key)=>key==='valid'?r.valid:r.metrics?.[key];
    $('#field-comparison').innerHTML=`<h3>Jev and your selected run</h3><p>Each bar shows a count out of 60. These runs may use different prompts, settings or execution methods, so their scores alone do not show which model is better.</p>${fields.map(([name,key]) => { const a=get(jev,key),b=get(run,key);return `<div class="field-row"><span>${esc(name)}</span><div><span class="field-track"><span style="width:${has(a)?Math.max(0,Math.min(100,n(a)/60*100)):0}%"></span></span><span class="field-track selected"><span style="width:${has(b)?Math.max(0,Math.min(100,n(b)/60*100)):0}%"></span></span></div><strong>${has(a)?esc(a):'—'} vs ${has(b)?esc(b):'—'}</strong></div>`;}).join('')}<div class="field-key"><span></span>Jev (first number) <span></span>${esc(run.model)} (second number)</div>`;
  }
  function renderRoster() {
    const roster=state.data.roster;
    if(!roster.length){$('.availability').hidden=true;return;}
    const query=$('#roster-search').value.toLowerCase().trim();
    const entries=roster.filter(item => {const base=state.data.runs.find(r=>r.id===item.parentBaselineId);return !query || `${item.id} ${base?.model||''} ${item.disposition}`.toLowerCase().includes(query);});
    $('#roster-count').textContent=`${entries.length} of ${roster.length} setups`;
    $('#roster-list').innerHTML=entries.length ? entries.map(item => `<div class="roster-row"><strong>${esc(item.id)}</strong><span>${esc(item.disposition)}</span><p>${esc(item.reason)}</p></div>`).join('') : '<p class="empty-state">No model or setup matches this search.</p>';
  }
  function initSources() {
    $('#reference-note').textContent='The comments are fictional, and one AI assistant drafted and reviewed the reference answers. Some prompt comparisons have not passed full evidence checks. A score difference does not prove the prompt caused it.';
    const jev=url(state.data.runs.find(r=>r.id==='typesafe-jev113-v2')?.evidenceUrl);
    const paired=url((state.data.promptComparisons || []).find(item=>item.eligible && url(item.evidenceUrl))?.evidenceUrl);
    const links=[[jev,'Jev source records'],[paired,'Example prompt comparison report']].filter(([link])=>link);
    $('#source-links').innerHTML=links.map(([link,name])=>`<a href="${esc(link)}" target="_blank" rel="noopener noreferrer">${esc(name)} ↗</a>`).join('');
  }
  function initJev() {
    const jev=state.data.runs.find(r => r.id === 'typesafe-jev113-v2') || state.data.runs.find(r => /typesafe.*jev/i.test(r.id) && r.condition === 'P0');
    if (!jev) {$('#jev').hidden=true;return;}
    $('#jev-score').innerHTML=`${has(jev.metrics?.all_four) ? esc(jev.metrics.all_four) : '—'}<small>/ 60</small>`;
    const estimate=money(jev.cost?.estimatedUsd);
    $('#jev-note').textContent=`Jev P0: ${count(jev.valid)} valid responses out of 60. ${count(jev.tokens?.input)} input and ${count(jev.tokens?.output)} output tokens were reported for ${count(jev.tokens?.reportedRequests)} of ${count(jev.tokens?.totalRequests)} attempts. API price estimate for known usage: ${estimate}; provider bill and server inference time unavailable.`;
    $('#inspect-jev').addEventListener('click',() => selectRun(jev.id,true));
  }
  async function init() {
    try {
      const response=await fetch('./data.json',{cache:'no-store'});if(!response.ok)throw new Error(`HTTP ${response.status}`);
      const data=await response.json();if(!Array.isArray(data.runs)||n(data.denominator)!==60)throw new Error('Invalid public data');
      state.data={...data,runs:data.runs.filter(r => r?.id && ['P0','P1','P2'].includes(r.condition)),cases:Array.isArray(data.cases)?data.cases:[],roster:Array.isArray(data.roster)?data.roster:[]};
      const queryMetric=new URL(location.href).searchParams.get('metric');if(queryMetric && Object.prototype.hasOwnProperty.call(metricName,queryMetric))$('#metric').value=queryMetric;
      groups();renderExperimentSelect();renderModelSelect();
      ['#overview-condition','#overview-hosted'].forEach(selector=>$(selector).addEventListener('change',()=>{state.overviewAll=false;renderOverview();}));
      $('#overview-toggle').addEventListener('click',()=>{state.overviewAll=!state.overviewAll;renderOverview();});
      $('#compare-search').addEventListener('input',renderModelSelect);
      $('#compare-run-select').addEventListener('change',event=>{if(event.target.value)selectRun(event.target.value,false);});
      $('#surface-filter').innerHTML='<option value="">All surfaces</option>'+[...new Set(state.data.runs.map(r=>r.surface).filter(Boolean))].sort().map(s => `<option value="${esc(s)}">${esc(s)}</option>`).join('');
      $('#experiment-select').addEventListener('change',() => {const group=state.experiments.get($('#experiment-select').value)||[];const lead=group.find(r=>r.condition==='P0')||group[0];if(lead)selectRun(lead.id,false);else renderExperiment();});
      $('#metric').addEventListener('change',() => {renderExperiment();renderLedger();if(state.selectedId)selectRun(state.selectedId,false);});
      ['#search','#condition-filter','#surface-filter','#sort','#include-incomplete'].forEach(selector => $(selector).addEventListener(selector==='#search'?'input':'change',renderLedger));
      if (!state.data.runs.some(r => !complete(r))) $('#include-incomplete').closest('label').hidden=true;
      $('#roster-search').addEventListener('input',renderRoster);
      initSources();initJev();renderRoster();renderLedger();renderOverview();renderExperiment();
      const jev=state.data.runs.find(r => r.id === 'typesafe-jev113-v2');
      const queryRun=new URL(location.href).searchParams.get('run');
      const initial=state.data.runs.find(r => r.id===queryRun) || (state.experiments.get($('#experiment-select').value)||[]).find(r => r.condition==='P0') || jev || state.data.runs.find(complete) || state.data.runs[0];if(initial)selectRun(initial.id,false);
    } catch(error) {
      const message='Results could not be loaded. Please reload the page.';
      for (const selector of ['#comparison-list','#condition-grid','#run-detail']) $(selector).innerHTML=`<p class="empty-state">${message}</p>`;
      $('#experiment-title').textContent=message;$('#jev-note').textContent=message;
      console.error('Public explorer data error:',error);
    }
  }
  init();
})();
