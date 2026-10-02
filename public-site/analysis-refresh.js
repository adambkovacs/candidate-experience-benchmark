/* Current synthesis stays separate from the archived first-pass charts. */
(() => {
  const target = document.getElementById('analysis-refresh-table');
  if (!target) return;
  const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const price = value => value == null ? 'Unavailable' : '$' + Number(value).toFixed(3);
  fetch('./analysis-refresh.json', {cache:'no-store'}).then(response => {
    if (!response.ok) throw Error('Analysis unavailable');
    return response.json();
  }).then(report => {
    const rows = ['low','medium','high','xhigh'].map(effort => {
      const item = report.sonnet55.byEffort[effort];
      const cells = ['P0','P1','P2'].map(condition => {
        const result = item.conditions[condition];
        if (result.scores.length !== 3 || result.range.length !== 2 || !Array.isArray(result.changedReviewIds)) throw Error('Incomplete analysis');
        const range = result.range[0] === result.range[1] ? result.range[0] : result.range.join('–');
        return `<td><strong>${esc(range)} / 60</strong><small>${result.changedReviewIds.length} ${result.changedReviewIds.length === 1 ? 'comment' : 'comments'} changed an answer</small></td>`;
      }).join('');
      return `<tr><th scope="row">${esc(effort)}</th>${cells}<td>${esc(Number(item.usage.outputTokens).toLocaleString('en-US'))}</td><td>${esc(price(item.usage.developmentApiEquivalentUsd))}</td></tr>`;
    }).join('');
    target.innerHTML = `<table><caption>Sonnet 5.5: score ranges and changed answers across three passes</caption><thead><tr><th>Effort</th><th>Base task (P0)</th><th>Classifier instructions (P1)</th><th>Decision rules (P2)</th><th>Output tokens, nine runs</th><th>API equivalent, nine runs</th></tr></thead><tbody>${rows}</tbody></table>`;
    const summary = document.getElementById('analysis-refresh-summary');
    if (summary && report.claude) {
      const c = report.claude, total = c.historicalCount + c.newSonnetCount;
      summary.innerHTML = `<p>Across these <strong>${esc(total)} Claude setups</strong>, neither longer prompt improved the all-four score in every pass for any setup. This extends the earlier review of ${esc(c.historicalCount)} setups with ${esc(c.newSonnetCount)} Sonnet effort settings. We compared each setup with itself; the result is not a ranking across models or independent samples.</p>`;
    }
    const cutoffs = document.getElementById('analysis-refresh-cutoffs');
    if (cutoffs && report.newerCohorts) {
      const {gemma26:gemma, clefNativeP0:clef, legacyQwen:qwen, deepseekLow:deepseek, mistral119:mistral} = report.newerCohorts;
      if (!gemma?.fresh3P2 || gemma?.p2RepeatSource !== 'public-site/gemma26-p2-repeat-findings.json' ||
          gemma?.p2Repeat?.sharedValidDenominator !== 57 ||
          gemma.p2Repeat.changedFourFieldVectorIds?.length !== 2 ||
          !clef?.models || clef?.repeatSource !== 'public-site/clef-p0-repeat-findings.json' ||
          clef?.repeat?.sharedValidDenominator !== 60 ||
          !qwen?.sdkFinalP2 || !deepseek || !mistral) throw Error('Incomplete cohort analysis');
      const on=qwen.sdkFinalP2.thinkingOn, off=qwen.sdkFinalP2.thinkingOff;
      cutoffs.innerHTML = `<p><strong>Other saved cohorts use different routes and completion rules.</strong></p><ul>
        <li><strong>Gemma 26B:</strong> ${esc(gemma.completedConditions)}/${esc(gemma.plannedConditions)} conditions scored. P2 all-four agreement across its interrupted three-pass series is ${['fresh1','fresh2','fresh3'].map(p=>esc(gemma.p2Repeat.fixed60AllFourByPass[p])).join(', ')} out of 60; ${esc(gemma.p2Repeat.changedFourFieldVectorIds.length)} of ${esc(gemma.p2Repeat.sharedValidDenominator)} shared-valid comments changed a decision. Fresh3 P2 has ${esc(gemma.fresh3P2.valid)} valid answers and preserved ${esc(gemma.fresh3P2.failedIds.join(' and '))} failures. This is descriptive, not a clean matched-three experiment. Fresh3 P0 and P1 were never sent. <a href="./gemma26-p2-repeat-findings.json">Read the P2 comparison</a>.</li>
        <li><strong>Clef native P0:</strong> this cutoff has two full passes per model. Clef has ${esc(clef.repeat.models.clef.fresh1AllFour)}/60 and ${esc(clef.repeat.models.clef.fresh2AllFour)}/60 all-four agreement; Clef Flash has ${esc(clef.repeat.models['clef-flash'].fresh1AllFour)}/60 and ${esc(clef.repeat.models['clef-flash'].fresh2AllFour)}/60. Neither model changed a four-field answer among ${esc(clef.repeat.sharedValidDenominator)} paired comments. This comparison covers the first two P0 passes; later passes are outside this cutoff. Provider-billed dollars are unavailable. <a href="./clef-p0-repeat-findings.json">Read the paired P0 comparison</a>.</li>
        <li><strong>Small Qwen SDK:</strong> the final thinking-on P2 run has ${esc(on.valid)} valid and ${esc(on.invalid)} invalid answers (${esc(on.allFour)}/60 all-four); thinking-off has ${esc(off.valid)} valid and ${esc(off.invalid)} invalid (${esc(off.allFour)}/60). These local settings are separate from hosted Qwen 27B.</li>
        <li><strong>Still incomplete:</strong> DeepSeek low and Mistral 119B retain failed and unsent positions without a full score.</li>
      </ul>`;
    }
  }).catch(() => {
    target.innerHTML = '<p>The comparison could not be loaded. <a href="https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/ANALYSIS_REFRESH_2026-10-02.md">Read the dated analysis and source tables.</a></p>';
  });
})();
