(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const count = value => Number.isFinite(Number(value)) ? Number(value) : 0;
  const base = 'https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/';
  const url = path => /^https?:\/\//.test(String(path || '')) ? path : base + String(path || '').replace(/^\//, '');
  const link = (path, label) => path ? `<a href="${esc(url(path))}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>` : '';
  const runLink = (id, label, caseId) => `<a href="?run=${encodeURIComponent(id)}${caseId ? `&case=${encodeURIComponent(caseId)}` : ''}#inspect">${esc(label || id)}</a>`;
  const pct = (a, b) => b ? Math.max(0, Math.min(100, 100 * count(a) / count(b))) : 0;
  const text = (id, value) => { if ($(id)) $(id).textContent = value; };
  const fieldName = name => ({sentiment:'Sentiment',follow_up_needed:'Follow-up needed',serious_concern_reported:'Serious concern',testimonial_potential:'Testimonial potential',all_four:'All four decisions'})[name] || String(name).replaceAll('_',' ');
  const categoryName = name => String(name || 'Other').replaceAll('_',' ');

  function renderPrompt(groups) {
    const target = $('finding-prompts');
    if (!groups?.length) { target.innerHTML = '<p class="finding-empty">No paired prompt analysis is available.</p>'; return; }
    const names = {strict:'Audited hosted and subscription pairs',hosted_observational:'Gemini hosted observations',local_historical_baseline:'Local historical-baseline pairs'};
    function groupBody(group) {
      const comparisons = Object.entries(group.comparisons || {}).map(([key,c]) => ({...c,from:key.slice(0,2),to:key.slice(-2)}));
      const rows = comparisons.map(c => {
        const total = count(c.improved)+count(c.tied)+count(c.worsened);
        const net = (c.rows || []).reduce((sum,r)=>sum+count(r.delta),0);
        return `<tr><th scope="row">${esc(c.from)} to ${esc(c.to)}</th><td><div class="delta-stack" role="img" aria-label="${esc(`${c.improved} improved, ${c.tied} tied, ${c.worsened} worsened among ${total} paired setups`)}"><span class="delta-gain" style="width:${pct(c.improved,total)}%"></span><span class="delta-tie" style="width:${pct(c.tied,total)}%"></span><span class="delta-loss" style="width:${pct(c.worsened,total)}%"></span></div></td><td class="num">${count(c.improved)} / ${count(c.tied)} / ${count(c.worsened)}</td><td class="num">${net>0?'+':''}${net}</td></tr>`;
      }).join('');
      const detail = comparisons.map(c => `<details class="finding-detail"><summary>${esc(c.from)} to ${esc(c.to)}: inspect ${count(c.rows?.length)} pairs</summary><div class="table-wrap"><table><caption>Change in all-four agreement, out of 60 comments</caption><thead><tr><th scope="col">Setup</th><th scope="col">Before</th><th scope="col">After</th><th scope="col">Change</th><th scope="col">Source</th></tr></thead><tbody>${(c.rows || []).map(r => `<tr><th scope="row">${runLink(r.fromRunId, r.model || r.id)}<small>${esc(r.fromRunId)} to ${esc(r.toRunId)}</small></th><td class="num">${esc(r.fromCorrect)}</td><td class="num">${esc(r.toCorrect)}</td><td class="num">${count(r.delta)>0?'+':''}${esc(r.delta)}</td><td>${link(r.evidenceUrl, 'Pair report')}</td></tr>`).join('')}</tbody></table></div></details>`).join('');
      return `<div class="finding-group-head"><div><p class="finding-label">${esc(names[group.id] || categoryName(group.id))}</p><h4>${count(group.configurations)} paired ${count(group.configurations)===1?'setup':'setups'}</h4></div><span class="finding-legend"><i class="gain"></i> Better <i class="tie"></i> Same <i class="loss"></i> Worse</span></div><div class="table-wrap"><table class="delta-table"><caption>Change in all-four reference agreement by prompt version</caption><thead><tr><th scope="col">Change</th><th scope="col">Paired outcomes</th><th scope="col">Better / same / worse</th><th scope="col">Net score points</th></tr></thead><tbody>${rows}</tbody></table></div>${detail}`;
    }
    target.innerHTML = groups.map((group,index)=> index===0 ? `<article class="finding-group">${groupBody(group)}</article>` : `<details class="finding-detail secondary-cohort"><summary>${esc(names[group.id] || categoryName(group.id))}: ${count(group.configurations)} setups, separate comparison</summary><div class="finding-group">${groupBody(group)}</div></details>`).join('');
    const strict=groups.find(g=>g.id==='strict');
    const p2=strict?.comparisons?.P1_to_P2;
    if (p2) {
      const net=(p2.rows || []).reduce((sum,r)=>sum+count(r.delta),0);
      text('prompt-headline', `Decision-tree instructions lost ground in ${count(p2.worsened)} of ${count(strict.configurations)} setups`);
      text('prompt-deck', `Adding the decision tree in P2, compared with P1, improved ${count(p2.improved)}, tied ${count(p2.tied)} and worsened ${count(p2.worsened)} audited comparisons. The net change was ${net>0?'+':''}${net} all-four matches across those runs. These comparisons use the first recorded pass; repeat results below assess variation.`);
    }
  }

  function renderJev(jev) {
    const target = $('finding-jev');
    if (!jev?.fieldErrors?.length) { target.innerHTML = '<p class="finding-empty">Jev field analysis is unavailable.</p>'; return; }
    const fields = jev.fieldErrors;
    const max = Math.max(1,...fields.map(f => count(f.wrong)+count(f.invalid)));
    target.innerHTML = `<div class="jev-chart" role="group" aria-label="Jev disagreement count by decision">${fields.map(f => `<div class="jev-bar-row"><span>${esc(fieldName(f.field))}</span><div class="jev-track" role="img" aria-label="${esc(`${f.wrong} wrong, ${f.invalid} invalid, out of ${f.denominator}`)}"><i class="jev-wrong" style="width:${pct(f.wrong,max)}%"></i><i class="jev-invalid" style="width:${pct(f.invalid,max)}%"></i></div><strong>${count(f.wrong)}${count(f.invalid)?` + ${count(f.invalid)} invalid`:''}</strong></div>`).join('')}</div><p class="chart-foot">Counts are per decision. One comment can disagree on more than one decision. Scale runs from zero to ${max} disagreements; bar labels give exact counts. ${runLink(jev.runId, 'Inspect Jev records')}.</p>`;
    if (jev.comparators?.length) target.innerHTML += `<details class="finding-detail"><summary>Compare Jev's exact missed reviews with other P0 runs</summary><div class="table-wrap"><table class="overlap-table"><caption>Where Jev and selected runs disagreed with the reference</caption><thead><tr><th scope="col">Compared run</th><th scope="col">Jev only missed</th><th scope="col">Other only missed</th><th scope="col">Both missed</th><th scope="col">Both matched</th><th scope="col">Evidence</th></tr></thead><tbody>${jev.comparators.map(o => `<tr><th scope="row">${runLink(o.id, o.model || o.id)}<small>${esc(o.id)}</small></th><td class="num">${count(o.overlap?.jevOnlyWrong)}</td><td class="num">${count(o.overlap?.comparatorOnlyWrong)}</td><td class="num">${count(o.overlap?.bothWrong)}</td><td class="num">${count(o.overlap?.bothCorrect)}</td><td>${link(o.evidenceUrl,'Run source')}</td></tr>`).join('')}</tbody></table></div></details>`;
    const gemma=jev.comparators?.find(r=>r.id==='openrouter-paid-gemma4-26b-a4b-on');
    const opus=jev.comparators?.find(r=>r.id==='opus55-high-batch10');
    if (gemma && opus) target.innerHTML += `<p class="overlap-insight">The ${runLink(gemma.id, 'Gemma 26B run')} matched all ${count(gemma.overlap.jevOnlyWrong)} comments Jev missed, but missed one different comment because its response was invalid. The ${runLink(opus.id, 'Opus 5.5 high run')} repaired ${count(opus.overlap.jevOnlyWrong)} of Jev's six misses and shared one. The aggregate 59 / 60 score hides those differences.</p>`;
    const cases = [{id:'DEV-006',note:'The unresolved "thing" may not meet the guide\'s threshold for a serious concern. The reference needs adjudication.'},{id:'DEV-013',note:'"Straightforward" and "no complaint" sit near the neutral/positive boundary.'},{id:'DEV-027',note:'A helpful switch to video drew negative sentiment and no testimonial from Jev despite explicit praise.'},{id:'DEV-029',note:'A restaurant review was off-topic. Jev classified the food experience across all four fields.'},{id:'DEV-030',note:'An unresolved accessibility issue leaves sentiment and concern unclear.'},{id:'DEV-059',note:'The candidate asked for repeated contact to stop. Jev missed the follow-up request.'}];
    target.innerHTML += `<div class="jev-case-head"><h3>Six comments behind the 54 / 60</h3><p>These are different error types. Three reference boundaries also need independent review.</p></div><div class="jev-case-grid">${cases.map(item => { const record=(jev.cases || []).find(r=>r.id===item.id); return `<article><span>${item.id}</span>${record?.feedback ? `<blockquote>${esc(record.feedback)}</blockquote>` : ''}<p>${esc(item.note)}</p>${runLink(jev.runId, 'Open this review', item.id)}</article>`; }).join('')}</div><p class="chart-foot">Jev matched all 25 reference answers labeled serious concern = yes. Its three misses on that decision were references labeled insufficient information that it answered no. The overlap table treats invalid output as a miss. <a href="https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/FINDINGS.md">Read the review-by-review interpretation</a>.</p>`;
    text('jev-headline', 'Jev\'s six misses have different causes');
    text('jev-deck', 'Eleven decision disagreements occur in six reviews. One off-topic restaurant comment accounts for four; a praised accommodation accounts for two. Several saved reference answers also need a second human judgment.');
  }

  function renderCost(rows) {
    const target = $('finding-cost');
    const observed = (rows || []).filter(r => r.condition === 'P0' && count(r.denominator) === 60 && r.costAvailability === 'observed' && r.actualUsd !== null && Number.isFinite(Number(r.actualUsd)) && Number(r.actualUsd) >= 0 && Number.isFinite(Number(r.correct)));
    if (!observed.length) { target.innerHTML = '<p class="finding-empty">No runs have both an observed charge and an agreement score.</p>'; return; }
    const maxCost = Math.max(...observed.map(r => Number(r.actualUsd)),.001);
    const W=720,H=320,pad={l:54,r:30,t:24,b:47};
    const x = v => pad.l + (W-pad.l-pad.r)*v/maxCost;
    const y = v => H-pad.b - (H-pad.t-pad.b)*v/60;
    const ticks=[0,15,30,45,60].map(v=>`<line x1="${pad.l}" y1="${y(v)}" x2="${W-pad.r}" y2="${y(v)}" stroke="#d1d7ce"/><text x="${pad.l-12}" y="${y(v)+4}" text-anchor="end">${v}</text>`).join('');
    const points=observed.map((r,i)=>`<a href="?run=${encodeURIComponent(r.id)}#inspect"><circle cx="${x(Number(r.actualUsd)).toFixed(2)}" cy="${y(count(r.correct)).toFixed(2)}" r="6" fill="${r.cohort==='hosted_observational_gemini'?'#176b5f':'#b75f43'}" stroke="#fff9f0" stroke-width="2"><title>${esc(`${r.model || r.id}: ${r.correct}/60 matches, $${r.actualUsd} observed`)}</title></circle></a>`).join('');
    target.innerHTML = `<div class="cost-example"><p class="finding-label">Two saved effort comparisons</p><p>Gemini 3.1 Pro low matched 56 / 60 at $0.063458; high matched 55 / 60 at $0.256826. Gemini 3.7 Flash low matched 57 / 60 at $0.021673; medium matched 56 / 60 at $0.055967. All four runs had 60 valid responses. <a href="https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/FINDINGS.md">Source and limits</a>.</p></div><p class="plot-legend"><i class="baseline-dot"></i> Baseline P0 API runs <i class="gemini-dot"></i> Gemini hosted batch P0 runs</p><div class="plot-shell"><svg class="cost-plot" viewBox="0 0 ${W} ${H}" role="img" aria-labelledby="cost-svg-title cost-svg-desc"><title id="cost-svg-title">Observed charge versus all-four agreement</title><desc id="cost-svg-desc">${observed.length} saved runs, each plotted by observed charge in US dollars and matches out of 60. Exact values appear in the table below.</desc>${ticks}<line x1="${pad.l}" y1="${H-pad.b}" x2="${W-pad.r}" y2="${H-pad.b}" stroke="#607268"/><text x="${W/2}" y="${H-8}" text-anchor="middle">Observed run charge, USD</text><text x="${pad.l}" y="${H-pad.b+20}">$0</text><text x="${W-pad.r}" y="${H-pad.b+20}" text-anchor="end">$${maxCost.toFixed(maxCost<.1?3:2)}</text><text transform="translate(15 ${H/2}) rotate(-90)" text-anchor="middle">All four match / 60</text>${points}</svg></div><details class="finding-detail"><summary>Exact values and source records (${observed.length} runs)</summary><div class="table-wrap"><table><caption>Observed charge and agreement for plotted runs</caption><thead><tr><th scope="col">Run</th><th scope="col">Prompt</th><th scope="col">Matches / 60</th><th scope="col">Observed USD</th><th scope="col">Evidence</th></tr></thead><tbody>${observed.sort((a,b)=>count(a.actualUsd)-count(b.actualUsd)).map(r=>`<tr><th scope="row">${runLink(r.id,r.model || r.id)}<small>${esc(r.id)}</small></th><td>${esc(r.condition)}</td><td class="num">${count(r.correct)} / ${count(r.denominator)||60}</td><td class="num">$${esc(r.actualUsd)}</td><td>${link(r.evidenceUrl,'Run source')}</td></tr>`).join('')}</tbody></table></div></details><p class="chart-foot">Only observed charges are plotted. Estimates and unknown charges are excluded; Jev's API price is an estimate and does not appear as a point.</p>`;
    text('cost-headline', 'Higher spend did not add matches in these two effort pairs');
    text('cost-deck', 'Both examples cost more at higher effort and matched one fewer reference answer. The chart shows complete P0 runs with fully observed charges; mixed request patterns limit cross-run comparisons.');
  }

  function renderHard(rows, runIds) {
    const target=$('finding-hard');
    if (!rows?.length) { target.innerHTML='<p class="finding-empty">No hard-review grouping is available.</p>'; return; }
    const sorted=[...rows].sort((a,b)=>count(b.wrongValid)+count(b.invalid)-count(a.wrongValid)-count(a.invalid));
    const max=Math.max(1,...sorted.map(r=>count(r.wrongValid)+count(r.invalid)));
    target.innerHTML=`<div class="hard-context"><strong>Check the reference before treating every miss as a model error.</strong><p>DEV-006 has an unresolved "thing" whose seriousness is not stated. DEV-013 is near the neutral/positive sentiment boundary. DEV-030 leaves an accessibility issue and possible reassessment unclear. These three reference labels need independent adjudication. <a href="https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/FINDINGS.md">Read the label audit</a>.</p></div><div class="table-wrap"><table class="hard-table"><caption>Comments most often missed across the analyzed runs</caption><thead><tr><th scope="col">Review</th><th scope="col">Category</th><th scope="col">Wrong / invalid</th><th scope="col">Misses</th><th scope="col">Records</th></tr></thead><tbody>${sorted.slice(0,15).map(r=>`<tr><th scope="row">${esc(r.id)}${r.feedback || r.excerpt ? `<small class="hard-excerpt">${esc(r.feedback || r.excerpt)}</small>` : ''}</th><td>${esc((r.challengeTags?.length ? r.challengeTags.join(', ') : 'Unmarked'))}</td><td><div class="hard-heat" role="img" aria-label="${esc(`${r.wrongValid} wrong and ${r.invalid} invalid, out of ${r.denominator}`)}"><span style="width:${pct(count(r.wrongValid)+count(r.invalid),max)}%"></span></div></td><td class="num">${count(r.wrongValid)} + ${count(r.invalid)} / ${count(r.denominator)}</td><td>${link(r.sourceUrl,'Source')}${(runIds || []).length ? ` · ${runLink(runIds[0], 'Open review', r.id)}` : ''}</td></tr>`).join('')}</tbody></table></div><details class="finding-detail"><summary>All ${sorted.length} reviews with subgroup counts</summary><div class="table-wrap"><table><caption>Hard-review counts across all analyzed comments</caption><thead><tr><th scope="col">Review</th><th scope="col">Category</th><th scope="col">Wrong</th><th scope="col">Invalid</th><th scope="col">Total scored</th><th scope="col">Source</th></tr></thead><tbody>${sorted.map(r=>`<tr><th scope="row">${esc(r.id)}</th><td>${esc((r.challengeTags?.length ? r.challengeTags.join(', ') : 'Unmarked'))}</td><td class="num">${count(r.wrongValid)}</td><td class="num">${count(r.invalid)}</td><td class="num">${count(r.denominator)}</td><td>${link(r.sourceUrl,'Record')}</td></tr>`).join('')}</tbody></table></div></details>`;
    text('hard-headline', `${sorted[0].id} drew ${count(sorted[0].wrongValid)+count(sorted[0].invalid)} recorded misses`);
    text('hard-deck', 'Repeated disagreements point to comments worth reading closely. The strongest count is not automatically the clearest model error: some reference boundaries remain unresolved.');
  }

  async function boot() {
    try {
      const response=await fetch('./findings.json');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data=await response.json();
      renderPrompt(data.charts?.promptDeltas?.groups);
      renderJev(data.charts?.jev);
      renderCost(data.charts?.costAgreement?.rows);
      renderHard(data.charts?.hardCases?.rows, data.charts?.hardCases?.runIds);
      text('analysis-source', data.meta?.sourceSha256 ? `Computed from saved records · source SHA-256 ${data.meta.sourceSha256.slice(0,12)}` : 'Computed from saved benchmark records');
    } catch (error) {
      ['finding-prompts','finding-jev','finding-cost','finding-hard'].forEach(id => {$(id).innerHTML='<p class="finding-empty">The analysis file could not be loaded. The run explorer below remains available.</p>';});
      console.error('Findings could not load',error);
    }
  }
  document.addEventListener('DOMContentLoaded',boot);
})();
