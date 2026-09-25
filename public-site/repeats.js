/* Each configuration is one separate 60-record repeat series. */
(() => {
  const root = document.getElementById('repeat-results');
  if (!root) return;
  const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const passes = ['original', 'repeat2', 'repeat3'];
  const passName = {original:'Pass 1', repeat2:'Pass 2', repeat3:'Pass 3'};
  const conditions = {P0:'Base task', P1:'Classifier instructions', P2:'Instructions and decision tree'};
  const fields = {allFour:'All four decisions', sentiment:'Sentiment', follow_up_needed:'Follow-up needed', serious_concern_reported:'Serious concern', testimonial_potential:'Testimonial potential'};
  const valueOf = (score, field) => field === 'allFour' ? score.allFour : score.fields[field];
  const signed = n => n > 0 ? `+${n}` : String(n);
  const number = n => n == null ? 'Unavailable' : n.toLocaleString('en-US');
  const money = n => n == null || !Number.isFinite(Number(n)) ? 'Unavailable' : '$' + Number(n).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 8});

  Promise.all(['./repeats.json', './hosted-repeats.json', './claude-repeats.json'].map(url => fetch(url).then(r => {if (!r.ok) throw Error('Missing repeat results'); return r.json();}))).then(payloads => {
    const series = payloads.flatMap(payload => payload.series || [payload]);
    if (!series.length) throw Error('No repeat series');
    root.innerHTML = `<label class="repeat-control">Configuration <select id="repeat-config">${series.map(s => `<option value="${esc(s.configuration)}">${esc(s.displayName || s.configuration)}</option>`).join('')}</select></label>
      <p class="repeat-lead" id="repeat-lead"></p><div id="repeat-interpretation"></div>
      <label class="repeat-control">Compare agreement for <select id="repeat-field">${Object.entries(fields).map(([k,v]) => `<option value="${k}">${v}</option>`).join('')}</select></label>
      <div id="repeat-chart" aria-live="polite"></div>
      <div class="repeat-detail-grid"><div><h3>Does the prompt advantage persist?</h3><p>Change in matching answers compared with P0 in the same pass. Positive means more matches; negative means fewer.</p><div id="repeat-deltas"></div></div>
      <div><h3>Which answers changed?</h3><label class="repeat-control">Prompt condition <select id="repeat-condition">${Object.entries(conditions).map(([k,v]) => `<option value="${k}">${k}: ${v}</option>`).join('')}</select></label><div id="repeat-flips" aria-live="polite"></div></div></div>
      <details class="repeat-usage"><summary>Requests, tokens and reported costs</summary><p>Each completed row covers 60 comments. Request counts depend on whether the configuration uses individual comments or batches. Smoke tests are separate. Input and cache counts follow each provider's definitions and must not be added without checking them. Reported API charges appear when available; CLI list-price estimates are shown separately and are not subscription charges. Subscription costs and pure inference time remain unavailable. Request durations include client and service overhead.</p><div class="table-wrap"><table><caption>Recorded development usage</caption><thead><tr><th>Prompt</th><th>Pass</th><th>Requests</th><th>Input tokens</th><th>Output tokens</th><th>Reported cost (USD)</th><th>CLI list-price estimate</th><th>Sum of request seconds</th></tr></thead><tbody id="repeat-usage-body"></tbody></table></div></details>`;
    const configControl = document.getElementById('repeat-config');
    const fieldControl = document.getElementById('repeat-field');
    const conditionControl = document.getElementById('repeat-condition');

    function render() {
      const data = series.find(s => s.configuration === configControl.value);
      if (!data) throw Error('Unknown repeat configuration');
      const field = fieldControl.value;
      document.getElementById('repeat-interpretation').innerHTML = (data.interpretation || []).map(text => `<p>${esc(text)}</p>`).join('');
      document.getElementById('repeat-lead').textContent = `${data.displayName || data.configuration}. ${data.completedConditions} of ${data.plannedConditions} planned prompt/pass combinations have complete evidence on the same ${data.denominator} development comments. Incomplete passes are not zero scores.` + Object.entries(data.passes).flatMap(([pass, conditions]) => Object.entries(conditions).filter(([, phase]) => phase.completionStatus === 'partial').map(([condition, phase]) => { const o = phase.score.outcomes; return ` ${condition} ${passName[pass]} stopped with ${o.valid} valid responses, ${o.service_error || 0} service errors and ${o.never_sent || 0} reviews not sent.`; })).join('');
      document.getElementById('repeat-chart').innerHTML = `<div class="repeat-score-grid">${Object.entries(conditions).map(([c,label]) => {
        const stats = field === 'allFour' ? data.threePassSummary[c].allFour : data.threePassSummary[c].fields[field];
        return `<article><h3>${c} <span>${label}</span></h3>${passes.map(p => {
          const phase = data.passes[p]?.[c];
          const partial = phase?.completionStatus === 'partial';
          const score = partial ? null : phase?.score;
          const n = score ? valueOf(score,field) : null;
          return `<div class="repeat-bar-row"><span>${passName[p]}</span>${n == null ? (partial ? '<span>Partial run</span>' : '<span>Not completed</span>') : `<meter min="0" max="${data.denominator}" value="${n}" aria-label="${c} ${passName[p]} ${esc(fields[field])}: ${n} out of ${data.denominator}">${n}</meter><strong>${n}<small> / ${data.denominator}</small></strong>`}</div>`;
        }).join('')}<p class="repeat-range">${stats.range ? `Three-pass range: <strong>${stats.range[0]}–${stats.range[1]}</strong> out of ${data.denominator}` : 'Three-pass range unavailable until all passes finish.'}</p></article>`;
      }).join('')}</div><p class="analysis-caveat">Bars start at zero. Agreement is measured against provisional references, separately from valid response format. Repeated comments are not independent cases.</p>`;
      document.getElementById('repeat-deltas').innerHTML = `<div class="table-wrap"><table><caption>${esc(fields[field])}: change from P0, out of ${data.denominator}</caption><thead><tr><th>Prompt</th>${passes.map(p => `<th>${passName[p]}</th>`).join('')}</tr></thead><tbody>${['P1','P2'].map(c => `<tr><th scope="row">${c}</th>${passes.map(p => {
        const d = data.withinPassPromptDeltas.find(x => x.pass === p && x.to === c);
        return `<td>${d ? signed(valueOf(d,field)) : 'Not completed'}</td>`;
      }).join('')}</tr>`).join('')}</tbody></table></div>`;
      const c = conditionControl.value;
      const changes = data.changesAcrossThreePasses[c];
      const ids = changes ? (field === 'allFour' ? changes.fourFieldVector : changes.fields[field]) : null;
      const pairs = data.pairwiseFlips.filter(x => x.condition === c);
      document.getElementById('repeat-flips').innerHTML = `${ids ? `<p><strong>${ids.length} / ${changes.denominator}</strong> comparable comments changed ${field === 'allFour' ? 'at least one decision' : esc(fields[field].toLowerCase())} across the three passes.</p><p class="repeat-case-ids">${ids.length ? ids.map(id => `<a href="?experiment=${encodeURIComponent(data.configuration)}&amp;run=${encodeURIComponent(data.configuration + (c === 'P0' ? '' : '--' + c.toLowerCase()))}&amp;case=${encodeURIComponent(id)}#inspect">${esc(id)}</a>`).join(' · ') : 'No changed comments.'}</p><p>${changes.excludedIds.length} comments excluded because not all passes had valid answers.</p>` : '<p>Three-pass changes are unavailable until all passes finish.</p>'}<ul>${pairs.map(x => {const f = field === 'allFour' ? x.fourFieldVector : x[field]; return `<li>${passName[x.from]} to ${passName[x.to]}: ${f.changed} / ${x.denominator} changed</li>`;}).join('')}</ul>`;
      document.getElementById('repeat-usage-body').innerHTML = Object.keys(conditions).flatMap(c => passes.map(p => {
        const u = data.passes[p]?.[c]?.usage;
        return `<tr><th scope="row">${c}</th><td>${passName[p]}${data.passes[p]?.[c]?.completionStatus === 'partial' ? ' (partial)' : ''}</td><td>${number(u?.startedRequestCount ?? u?.requestCount)}</td><td>${number(u?.tokens?.input_tokens)}<br><small>Cache read: ${number(u?.tokens?.cache_read_input_tokens ?? u?.tokens?.cached_input_tokens)}<br>Cache write: ${number(u?.tokens?.cache_creation_input_tokens ?? u?.tokens?.cache_write_input_tokens)}</small></td><td>${number(u?.tokens?.output_tokens)}<br><small>Reasoning: ${number(u?.tokens?.thinking_tokens ?? u?.tokens?.reasoning_output_tokens)}</small></td><td>${money(u?.actualCostUsd)}${u?.unknownCostCount ? ` (${u.unknownCostCount} unknown)` : ''}</td><td>${money(u?.cliListPriceEstimateUsd)}</td><td>${u?.requestSecondsTotal == null ? (data.passes[p]?.[c] ? 'Unavailable' : 'Not completed') : u.requestSecondsTotal.toFixed(1)}</td></tr>`;
      })).join('');
    }
    configControl.addEventListener('change', render);
    fieldControl.addEventListener('change', render);
    conditionControl.addEventListener('change', render);
    render();
  }).catch(() => {root.innerHTML = '<p>Repeat results could not be loaded. <a href="https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/REPEAT_FINDINGS.md">Read the saved repeat report</a>.</p>';});
})();
