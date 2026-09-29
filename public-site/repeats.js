/* Each configuration is one separate 60-record repeat series. */
(() => {
  const root = document.getElementById('repeat-results');
  if (!root) return;
  const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const passName = {original:'Pass 1', repeat2:'Pass 2', repeat3:'Pass 3', pass1:'Pass 1', pass2:'Pass 2', pass3:'Pass 3', fresh1:'Fresh pass 1', fresh2:'Fresh pass 2', fresh3:'Fresh pass 3'};
  const conditions = {P0:'Base task', P1:'Classifier instructions', P2:'Instructions and decision tree'};
  const fields = {allFour:'All four decisions', sentiment:'Sentiment', follow_up_needed:'Follow-up needed', serious_concern_reported:'Serious concern', testimonial_potential:'Testimonial potential'};
  const valueOf = (score, field) => field === 'allFour' ? score.allFour : score.fields[field];
  const signed = n => n > 0 ? `+${n}` : String(n);
  const number = n => n == null ? 'Unavailable' : n.toLocaleString('en-US');
  const money = n => n == null || !Number.isFinite(Number(n)) ? 'Unavailable' : '$' + Number(n).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 8});

  const feedUrls = ['./typesafe-repeats.json', './repeats.json', './hosted-repeats.json', './claude-repeats.json', './claude-roster-repeats.json', './gemini-repeats.json', './haiku-fresh-matched3.json', './laya-repeats.json', './semif-repeats.json', './small-local-repeats.json', './anyjev-raw-repeats.json', './anyjev-l0-repeats.json', './anyjev-l1-repeats.json', './alex-native-repeats.json', './codex-fresh-repeats.json', './deepseek-fresh-repeats.json', './additional-hosted-fresh-repeats.json', './qwen36-off-continuation-findings.json'];
  const qwenContinuationSchema = 'qwen36-off-v2-descriptive-continuation-findings-v1';
  const qwenContinuationId = 'openrouter-paid-qwen36-35b-a3b-off-descriptive-continuation-v1';
  const qwenDispatchOrder = [['fresh1','P0'], ['fresh1','P1'], ['fresh1','P2'],
    ['fresh2','P2'], ['fresh2','P0'], ['fresh2','P1'], ['fresh3','P1'], ['fresh3','P2'], ['fresh3','P0']];
  const additionalHostedIds = {
    'openrouter-paid-qwen36-35b-a3b-off': 'openrouter-paid-qwen36-35b-a3b-off-fresh-matched3-v2',
    'openrouter-paid-deepseek-v41-flash-low': 'openrouter-paid-deepseek-v41-flash-low-fresh-matched3-v2'
  };
  Promise.all(feedUrls.map(url => fetch(url).then(r => {
    if (!r.ok && (url === './small-local-repeats.json' || url === './anyjev-raw-repeats.json' || url === './anyjev-l0-repeats.json' || url === './anyjev-l1-repeats.json' || url === './alex-native-repeats.json' || url === './codex-fresh-repeats.json' || url === './deepseek-fresh-repeats.json' || url === './additional-hosted-fresh-repeats.json' || url === './qwen36-off-continuation-findings.json') && r.status === 404) return {series: []};
    if (!r.ok) throw Error('Missing repeat results');
    return r.json().then(payload => {
      if (url === './additional-hosted-fresh-repeats.json' && payload === undefined) return {series: []};
      if (url === './codex-fresh-repeats.json' && (payload?.schema || payload?.series?.length) &&
          (payload?.schema !== 'codex-fresh-repeat-findings-v1' || !Array.isArray(payload.series) ||
           payload.series.some(s => s?.schema !== 'codex-fresh-repeat-findings-v1' || s.method !== 'fresh-matched-three' ||
             s.seriesId !== `${s.configuration}-fresh-matched3`))) throw Error('Invalid Codex fresh repeat results');
      if (url === './deepseek-fresh-repeats.json' && (payload?.schema || payload?.series?.length) &&
          (payload?.schema !== 'deepseek-fresh-repeat-findings-v1' || !Array.isArray(payload.series) ||
           payload.series.some(s => s?.schema !== 'deepseek-fresh-repeat-findings-v1' || s.method !== 'fresh-matched-three' ||
             s.seriesId !== `${s.configuration}-fresh-matched3`))) throw Error('Invalid DeepSeek fresh repeat results');
      if (url === './additional-hosted-fresh-repeats.json' &&
          !(payload && !payload.schema && Array.isArray(payload.series) && payload.series.length === 0) &&
          (payload?.schema !== 'additional-hosted-fresh-repeat-findings-v1' || !Array.isArray(payload.series) ||
           payload.series.some(s => s?.schema !== 'additional-hosted-fresh-repeat-findings-v1' ||
             s.method !== 'fresh-matched-three' || additionalHostedIds[s.configuration] !== s.seriesId) ||
           new Set(payload.series.map(s => s.seriesId)).size !== payload.series.length))
        throw Error('Invalid additional hosted fresh repeat results');
      if (url === './qwen36-off-continuation-findings.json') {
        if (payload === undefined) return {series: []};
        if (payload && !payload.schema && Array.isArray(payload.series) && payload.series.length === 0) return {series: []};
        const only = payload?.series?.[0];
        const first = only?.passes?.fresh1?.P0;
        const score = first?.score;
        const later = Object.entries(only?.passes || {}).flatMap(([pass, conditions]) =>
          Object.entries(conditions || {}).filter(([condition]) => !(pass === 'fresh1' && condition === 'P0'))
            .map(([, phase]) => phase));
        const closed = Object.values(only?.passes || {}).flatMap(pass => Object.values(pass || {}))
          .filter(phase => phase?.status === 'completed' || phase?.status === 'closed_with_service_error');
        const flips = [...(only?.pairwiseFlips || []), ...(only?.withinPassPromptFlips || [])];
        if (payload?.schema !== qwenContinuationSchema || !Array.isArray(payload.series) || payload.series.length !== 1 ||
            only?.schema !== qwenContinuationSchema || only?.seriesId !== qwenContinuationId ||
            only?.configuration !== 'openrouter-paid-qwen36-35b-a3b-off' ||
            only?.method !== 'descriptive-continuation-after-service-error' ||
            only?.cleanMatchedThreeEligible !== false || only?.denominator !== 60 ||
            only?.plannedConditions !== 9 || only?.completedConditions !== closed.length ||
            JSON.stringify(only?.passOrder) !== JSON.stringify(['fresh1', 'fresh2', 'fresh3']) ||
            JSON.stringify(only?.conditionOrder) !== JSON.stringify(['P0', 'P1', 'P2']) ||
            first?.status !== 'closed_with_service_error' || score?.denominator !== 60 ||
            score?.valid !== 59 || score?.outcomes?.ok !== 59 || score?.outcomes?.service_error !== 1 ||
            JSON.stringify(score?.invalidIds) !== JSON.stringify(['DEV-006']) ||
            first?.usage?.unknownChargeUpperBoundUsd !== '0.0299008' ||
            typeof first?.usage?.knownCostUsd !== 'string' ||
            !Number.isFinite(Number(first.usage.knownCostUsd)) ||
            Number(first.usage.knownCostUsd) < 0 ||
            later.some(phase => phase?.status === 'closed_with_service_error') ||
            closed.some(phase => phase?.score?.denominator !== 60 ||
              !Number.isInteger(phase?.score?.valid) || phase.score.valid < 0 || phase.score.valid > 60 ||
              (phase !== first && (phase?.status !== 'completed' ||
                phase?.budgetAccountingCumulative?.unknownChargeUpperBoundUsd !== '0.0299008' ||
                !Number.isFinite(Number(phase?.budgetAccountingCumulative?.knownAllAttemptCostUsd))))) ||
            flips.some(flip => !Number.isInteger(flip?.denominator) || flip.denominator < 0 ||
              flip.denominator > 60 || !Array.isArray(flip?.excludedIds) ||
              flip.excludedIds.length !== 60 - flip.denominator ||
              ((flip.pass === 'fresh1' && flip.from === 'P0') ||
               (flip.condition === 'P0' && (flip.from === 'fresh1' || flip.to === 'fresh1')))
                && !flip.excludedIds.includes('DEV-006')))
          throw Error('Invalid Qwen descriptive continuation results');
      }
      return payload;
    });
  }))).then(payloads => {
    const series = payloads.flatMap(payload => payload?.series || (payload ? [payload] : []));
    if (!series.length) throw Error('No repeat series');
    const isFreshCodex = s => s.schema === 'codex-fresh-repeat-findings-v1' && s.method === 'fresh-matched-three';
    const isFreshHosted = s => (s.schema === 'deepseek-fresh-repeat-findings-v1' ||
      s.schema === 'additional-hosted-fresh-repeat-findings-v1') && s.method === 'fresh-matched-three';
    const isQwenContinuation = s => s.schema === qwenContinuationSchema &&
      s.method === 'descriptive-continuation-after-service-error';
    const seriesKey = s => isFreshCodex(s) || isFreshHosted(s) || isQwenContinuation(s) ? s.seriesId : s.configuration;
    root.innerHTML = `<label class="repeat-control">Configuration <select id="repeat-config">${series.map(s => `<option value="${esc(seriesKey(s))}">${esc(s.displayName || s.configuration)}${isFreshCodex(s) ? ' · fresh matched three' : ''}</option>`).join('')}</select></label>
      <p class="repeat-lead" id="repeat-lead"></p><div id="repeat-interpretation"></div>
      <label class="repeat-control">Compare agreement for <select id="repeat-field">${Object.entries(fields).map(([k,v]) => `<option value="${k}">${v}</option>`).join('')}</select></label>
      <div id="repeat-chart" aria-live="polite"></div>
      <div class="repeat-detail-grid"><div><h3 id="repeat-delta-title">Does the prompt advantage persist?</h3><p id="repeat-delta-intro">Change in matching answers compared with P0 in the same pass. Positive means more matches; negative means fewer.</p><div id="repeat-deltas"></div></div>
      <div><h3>Which answers changed?</h3><label class="repeat-control"><span id="repeat-condition-label">Prompt condition</span> <select id="repeat-condition">${Object.entries(conditions).map(([k,v]) => `<option value="${k}">${k}: ${v}</option>`).join('')}</select></label><div id="repeat-flips" aria-live="polite"></div></div></div>
      <details class="repeat-usage"><summary>Requests, tokens and reported costs</summary><p>Each completed row covers 60 comments. Request counts depend on whether the configuration uses individual comments or batches. Smoke tests are separate. Input and cache counts follow each provider's definitions and must not be added without checking them. Reported API charges appear when available; Token-price and CLI list-price estimates are shown separately and are not verified invoices or subscription charges. Subscription costs and pure inference time remain unavailable. Request durations include client and service overhead.</p><div class="table-wrap"><table><caption>Recorded development usage</caption><thead><tr><th>Condition</th><th>Pass</th><th>Requests</th><th>Input tokens</th><th>Output tokens</th><th>Reported cost (USD)</th><th>Price-based estimate (USD)</th><th>Sum of request seconds</th></tr></thead><tbody id="repeat-usage-body"></tbody></table></div></details>`;
    const configControl = document.getElementById('repeat-config');
    const fieldControl = document.getElementById('repeat-field');
    const conditionControl = document.getElementById('repeat-condition');

    function render() {
      const data = series.find(s => seriesKey(s) === configControl.value);
      if (!data) throw Error('Unknown repeat configuration');
      const freshCodex = isFreshCodex(data);
      const freshHosted = isFreshHosted(data);
      const qwenContinuation = isQwenContinuation(data);
      const localFresh = data.method === 'fresh-matched-local-output-stability';
      const passes = data.passOrder || (localFresh ? ['fresh1', 'fresh2', 'fresh3'] : ['original', 'repeat2', 'repeat3']);
      const conditionOrder = data.conditionOrder || ['P0', 'P1', 'P2'];
      const nativeP0 = data.method === 'native-output-stability';
      const nativeL0 = data.schema === 'anyjev-l0-native-repeat-findings-v1';
      const nativeL1 = data.schema === 'anyjev-l1-direct-native-repeat-findings-v1';
      const nativeAlex = data.schema === 'alex-native-repeat-findings-v1';
      const closed = phase => qwenContinuation ? phase?.status === 'completed' || phase?.status === 'closed_with_service_error'
        : freshCodex || freshHosted ? phase?.status === 'completed'
        : (localFresh || nativeP0) ? phase?.completionStatus === 'complete'
          : Boolean(phase) && phase.completionStatus !== 'partial';
      const freshSeries = data.schema === 'additional-hosted-fresh-repeat-findings-v1' || qwenContinuation;
      const closedSlot = (pass, condition) => closed(data.passes[pass]?.[condition]);
      const nativeLabel = nativeL0 ? 'Native L0 readout' : nativeL1 ? 'Native L1 calibration' : nativeAlex ? 'Native NLI output' : 'Native output';
      document.getElementById('repeat-condition-label').textContent = nativeP0 ? 'Native condition' : 'Prompt condition';
      if (!conditionOrder.includes(conditionControl.value)) conditionControl.value = conditionOrder[0];
      conditionControl.innerHTML = conditionOrder.map(c => `<option value="${esc(c)}"${c === conditionControl.value ? ' selected' : ''}>${c}: ${esc(nativeP0 && c === 'P0' ? nativeLabel : conditions[c] || c)}</option>`).join('');
      const field = fieldControl.value;
      document.getElementById('repeat-interpretation').innerHTML = (qwenContinuation
        ? '<p class="analysis-caveat"><strong>Descriptive continuation:</strong> First-pass P0 includes 59 valid outputs and one DEV-006 HTTP 429 service error out of 60. The remaining P0 requests ran later. This is not a clean matched-three series. Scores retain all 60 comments; flip rates use only comments valid in both passes.</p>'
        : '') + (data.interpretation || []).map(text => `<p>${esc(text)}</p>`).join('');
      document.getElementById('repeat-lead').textContent = `${data.displayName || data.configuration}. ${data.completedConditions} of ${data.plannedConditions} planned ${nativeP0 ? 'native P0 passes' : 'prompt/pass combinations'} have complete evidence on the same ${data.denominator} development comments. Incomplete passes are not zero scores.` + Object.entries(data.passes).flatMap(([pass, conditions]) => Object.entries(conditions).filter(([, phase]) => phase.completionStatus === 'partial').map(([condition, phase]) => { const o = phase.score.outcomes; return ` ${condition} ${passName[pass]} stopped with ${o.valid} valid responses, ${o.service_error || 0} service errors and ${o.never_sent || 0} reviews not sent.`; })).join('');
      if (localFresh) document.getElementById('repeat-lead').textContent += ` These are three fresh local passes. Earlier local results are observational and are not counted here. Only terminal phases have scores. Reference labels are provisional and were used only for offline scoring. Client request time includes runtime overhead; loaded engine version, model load time and local cost are unknown.`;
      if (freshCodex) document.getElementById('repeat-lead').textContent += ' Each series schedules three fresh Codex subscription passes. Earlier results remain separate and are not pass one. Only closed development phases are scored. The requested model and CLI version are recorded; the served model identity and revision, effective seed and attributable subscription cost are unavailable. Request time includes client overhead.';
      if (freshHosted) document.getElementById('repeat-lead').textContent += ' This series schedules three fresh hosted passes. Earlier results remain separate and are not pass one. Only closed development phases are scored. Costs are provider-reported charges; request durations include network and service overhead, not pure inference time. Smoke usage is separate.';
      if (qwenContinuation) {
        const accounting = qwenDispatchOrder.map(([pass, condition]) => data.passes[pass]?.[condition])
          .filter(phase => closed(phase) && phase.budgetAccountingCumulative).pop()?.budgetAccountingCumulative;
        const known = accounting?.knownAllAttemptCostUsd ?? data.passes.fresh1.P0.usage.knownAllAttemptCostUsd;
        const unknown = accounting?.unknownChargeUpperBoundUsd ?? data.passes.fresh1.P0.usage.unknownChargeUpperBoundUsd;
        document.getElementById('repeat-lead').textContent += ` Known provider charges through the latest reported phase: ${money(known)}. The separate ${money(unknown)} unknown-charge upper bound for DEV-006 is not an invoice charge. Request durations include transport and service overhead, not pure inference time.`;
      }
      if (nativeL0) document.getElementById('repeat-lead').textContent += ' AnyJev L0 combines cyclic option shifts with a content-free prior. It has one native P0 procedure, not P1/P2 chat prompts. Agreement uses all 60 comments and provisional references; valid output is counted separately. Only completed passes are scored. Client request time includes overhead; pure inference time and local cost are unavailable.';
      if (nativeL1) document.getElementById('repeat-lead').textContent += ' AnyJev L1 fits calibration separately in five folds. Each review is classified with a fit trained on the other 48 reviews; its own reference labels are excluded. Training uses provisional labels, so this is supervised calibration. Historical cached-score results remain separate. Client and pure inference times were not recorded; local cost is unavailable.';
      if (nativeAlex) document.getElementById('repeat-lead').textContent += ' Alex uses one native NLI procedure. Earlier results are observational and excluded from the fresh-pass comparison. Client prediction time includes local overhead; isolated inference time and local cost are unavailable. Native NLI input positions are not billed API tokens.';
      const validity = Object.entries(data.passes).flatMap(([pass, entries]) => Object.entries(entries).filter(([, phase]) => closed(phase) && phase.score.valid < data.denominator).map(([condition, phase]) => `${condition} ${passName[pass]}: ${phase.score.valid}/${data.denominator} valid responses`));
      if (validity.length) document.getElementById('repeat-lead').textContent += ' Failed or invalid answers remain in the score denominator. ' + validity.join('; ') + '.';
      if (data.historicalContext?.firstPassEligible === false) document.getElementById('repeat-lead').textContent += ' These are three new passes. The earlier run with transport failures remains separate.';
      if (data.method === 'native-choice') document.getElementById('repeat-lead').textContent += ' Jev uses native Choice instruction variants. Pass 1 preserves the original failed request rather than its later successful retry.';
      document.getElementById('repeat-chart').innerHTML = `<div class="repeat-score-grid">${conditionOrder.map(c => {
        const label = nativeP0 && c === 'P0' ? nativeLabel : conditions[c] || c;
        const summary = data.threePassSummary?.[c];
        const completeThree = !freshSeries || passes.every(p => closedSlot(p, c));
        const stats = completeThree ? (field === 'allFour' ? summary?.allFour : summary?.fields?.[field]) : null;
        return `<article><h3>${c} <span>${esc(label)}</span></h3>${passes.map(p => {
          const phase = data.passes[p]?.[c];
          const partial = phase?.completionStatus === 'partial';
          const score = partial || !closed(phase) ? null : phase.score;
          const n = score ? valueOf(score,field) : null;
          return `<div class="repeat-bar-row"><span>${passName[p]}</span>${n == null ? (partial ? '<span>Partial run</span>' : '<span>Not completed</span>') : `<meter min="0" max="${data.denominator}" value="${n}" aria-label="${c} ${passName[p]} ${esc(fields[field])}: ${n} out of ${data.denominator}">${n}</meter><strong>${n}<small> / ${data.denominator}</small></strong>`}</div>`;
        }).join('')}<p class="repeat-range">${stats?.range ? `Three-pass range: <strong>${stats.range[0]}–${stats.range[1]}</strong> out of ${data.denominator}` : 'Three-pass range unavailable until all passes finish.'}</p></article>`;
      }).join('')}</div><p class="analysis-caveat">Bars start at zero. Agreement is measured against provisional references, separately from valid response format. Repeated comments are not independent cases.</p>`;
      document.getElementById('repeat-delta-title').textContent = nativeP0 ? 'One native decision procedure' : 'Does the prompt advantage persist?';
      document.getElementById('repeat-delta-intro').textContent = nativeL0 ? 'This native L0 readout has only P0. P1 and P2 chat prompt variants do not apply.' : nativeP0 ? 'This native option-scoring setup has only P0. P1 and P2 chat prompt variants do not apply.' : 'Change in answers matching the provisional reference compared with P0 in the same pass. Positive means more matches; negative means fewer.';
      document.getElementById('repeat-deltas').innerHTML = nativeP0 ? '' : `<div class="table-wrap"><table><caption>${esc(fields[field])}: change from P0, out of ${data.denominator}</caption><thead><tr><th>Prompt</th>${passes.map(p => `<th>${passName[p]}</th>`).join('')}</tr></thead><tbody>${conditionOrder.filter(c => c !== 'P0').map(c => `<tr><th scope="row">${esc(c)}</th>${passes.map(p => {
        const d = (!freshSeries || (closedSlot(p, 'P0') && closedSlot(p, c)))
          ? data.withinPassPromptDeltas?.find(x => x.pass === p && x.to === c) : null;
        const localDelta = localFresh && data.passes[p]?.[c]?.completionStatus === 'complete' && data.passes[p]?.P0?.completionStatus === 'complete'
          ? valueOf(data.passes[p][c].score, field) - valueOf(data.passes[p].P0.score, field) : null;
        return `<td>${d ? signed(valueOf(d,field)) : localDelta == null ? 'Not completed' : signed(localDelta)}</td>`;
      }).join('')}</tr>`).join('')}</tbody></table></div>${qwenContinuation ? `<p class="analysis-caveat">Prompt flip comparisons use only comments valid in both conditions: ${(data.withinPassPromptFlips || []).filter(x => closedSlot(x.pass, 'P0') && closedSlot(x.pass, x.to)).map(x => `${esc(passName[x.pass])} P0 to ${esc(x.to)}: ${x.denominator} shared valid of 60; ${x.excludedIds.length} excluded`).join('; ') || 'no paired conditions completed yet'}.</p>` : ''}`;
      const c = conditionControl.value;
      const changes = (!freshSeries || passes.every(p => closedSlot(p, c)))
        ? data.changesAcrossThreePasses?.[c] : null;
      const ids = changes ? (field === 'allFour' ? changes.fourFieldVector : changes.fields[field]) : null;
      const pairs = (data.pairwiseFlips || []).filter(x => x.condition === c &&
        (!freshSeries || (closedSlot(x.from, c) && closedSlot(x.to, c))));
      document.getElementById('repeat-flips').innerHTML = `${ids ? `<p><strong>${ids.length} / ${changes.denominator}</strong> comparable comments changed ${field === 'allFour' ? 'at least one decision' : esc(fields[field].toLowerCase())} across the three passes.</p><p class="repeat-case-ids">${ids.length ? ids.map(id => localFresh || data.passOrder ? esc(id) : `<a href="?experiment=${encodeURIComponent(data.configuration)}&amp;run=${encodeURIComponent(data.configuration + (c === 'P0' ? '' : '--' + c.toLowerCase()))}&amp;case=${encodeURIComponent(id)}#inspect">${esc(id)}</a>`).join(' · ') : 'No changed comments.'}</p><p>${changes.excludedIds.length} comments excluded because not all passes had valid answers.</p>` : '<p>Three-pass changes are unavailable until all passes finish.</p>'}<ul>${pairs.map(x => {const f = field === 'allFour' ? x.fourFieldVector : nativeL1 ? x.fields[field] : x[field]; const changed = Array.isArray(f) ? f.length : f.changed; return `<li>${passName[x.from]} to ${passName[x.to]}: ${changed} / ${x.denominator} changed</li>`;}).join('')}</ul>`;
      document.getElementById('repeat-usage-body').innerHTML = conditionOrder.flatMap(c => passes.map(p => {
        const u = (localFresh || nativeP0 || freshCodex || freshHosted || qwenContinuation) && !closed(data.passes[p]?.[c]) ? null : data.passes[p]?.[c]?.usage;
        const elapsed = u?.requestSecondsTotal ?? u?.clientHttpCallSecondsTotal ?? u?.clientRequestSecondsTotal ?? u?.clientPredictionSeconds;
        const nativePositions = nativeL1 && u?.tokens?.input_token_positions != null ? `<br><small>Native input positions: ${number(u.tokens.input_token_positions)} (not billed tokens)</small>` : nativeAlex && u?.nativeNliInputTokenPositions != null ? `<br><small>Native NLI input positions: ${number(u.nativeNliInputTokenPositions)}</small>` : '';
        return `<tr><th scope="row">${c}</th><td>${passName[p]}${data.passes[p]?.[c]?.completionStatus === 'partial' ? ' (partial)' : ''}</td><td>${number(u?.startedRequestCount ?? u?.requestCount)}</td><td>${number(u?.tokens?.input_tokens ?? u?.tokens?.prompt_tokens)}${nativePositions}<br><small>Cache read: ${number(u?.tokens?.cache_read_input_tokens ?? u?.tokens?.cached_input_tokens)}<br>Cache write: ${number(u?.tokens?.cache_creation_input_tokens ?? u?.tokens?.cache_write_input_tokens)}</small></td><td>${number(u?.tokens?.output_tokens ?? u?.tokens?.completion_tokens)}<br><small>Reasoning: ${number(u?.tokens?.thinking_tokens ?? u?.tokens?.reasoning_output_tokens)}</small></td><td>${money(u?.actualCostUsd ?? u?.knownCostUsd)}${qwenContinuation && u?.unknownChargeUpperBoundUsd && Number(u.unknownChargeUpperBoundUsd) > 0 ? `<br><small>Unknown charge up to ${money(u.unknownChargeUpperBoundUsd)}</small>` : u?.unknownCostCount ? ` (${u.unknownCostCount} unknown)` : ''}</td><td>${money(u?.estimatedTokenPriceCostUsd ?? u?.cliListPriceEstimateUsd)}${u?.estimatedTokenPriceCostUsd != null ? '<br><small>Reported input tokens × published price</small>' : u?.cliListPriceEstimateUsd != null ? '<br><small>CLI list-price estimate</small>' : ''}</td><td>${elapsed == null ? (data.passes[p]?.[c] ? 'Unavailable' : 'Not completed') : elapsed.toFixed(1)}</td></tr>`;
      })).join('');
    }
    configControl.addEventListener('change', render);
    fieldControl.addEventListener('change', render);
    conditionControl.addEventListener('change', render);
    render();
  }).catch(() => {root.innerHTML = '<p>Repeat results could not be loaded. <a href="https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/REPEAT_FINDINGS.md">Read the saved repeat report</a>.</p>';});
})();
