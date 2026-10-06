/* Source-bound Kev native prompt comparison. */
(() => {
  const target = document.getElementById('kev-prompt-results');
  if (!target) return;
  target.setAttribute?.('aria-live', 'polite');
  target.setAttribute?.('aria-busy', 'true');

  const fields = [
    ['sentiment', 'Sentiment'],
    ['follow_up_needed', 'Follow-up'],
    ['serious_concern_reported', 'Serious concern'],
    ['testimonial_potential', 'Testimonial']
  ];
  const passes = ['fresh1', 'fresh2', 'fresh3'];
  const names = {P1: 'Classifier instructions (P1)', P2: 'Decision rules (P2)'};
  const esc = value => String(value).replace(/[&<>"']/g,
    character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
  const integer = value => Number(value).toLocaleString('en-US');
  const signed = value => value > 0 ? `+${value}` : value < 0 ? `−${Math.abs(value)}` : '0';
  const passName = value => `Pass ${passes.indexOf(value) + 1}`;
  const fail = () => {
    target.setAttribute?.('aria-busy', 'false');
    target.innerHTML = '<p class="analysis-caveat" role="alert"><strong>Kev prompt results could not be loaded.</strong> The source evidence is unavailable or incomplete.</p>';
  };

  const validateScore = score => {
    if (!score || score.denominator !== 60 || score.valid !== 60 ||
        !Number.isInteger(score.allFour) || score.allFour < 0 || score.allFour > 60) throw Error('Invalid score');
    fields.forEach(([key]) => {
      if (!Number.isInteger(score.fields?.[key]) || score.fields[key] < 0 || score.fields[key] > 60) throw Error('Invalid field score');
    });
  };

  const validate = report => {
    if (report?.schema !== 'kev-native-prompt-findings-v1' || report.denominator !== 60 ||
        report.conditionOrder?.join(',') !== 'P1,P2' || report.nativePromptEquivalence?.verified !== true ||
        !Array.isArray(report.sourceBindings) || !report.sourceBindings.length ||
        !Array.isArray(report.pairedP1P2) || report.pairedP1P2.length !== 3) throw Error('Invalid report');
    if (report.sourceBindings.some(item => typeof item?.path !== 'string' ||
        !/^[a-f0-9]{64}$/.test(item?.sha256))) throw Error('Invalid source binding');
    ['P1', 'P2'].forEach(condition => {
      const item = report.conditions?.[condition];
      if (!item || item.completedPasses !== 3 || item.plannedPasses !== 3 ||
          item.passOrder?.join(',') !== passes.join(',') || item.repeatComparisons?.length !== 3 ||
          item.repeatVariation?.available !== true) throw Error('Incomplete condition');
      passes.forEach(pass => {
        const result = item.passes?.[pass];
        validateScore(result?.score);
        if (result.completionStatus !== 'complete' || !result.usage ||
            !Number.isInteger(result.usage.inputTokens) || !Number.isInteger(result.usage.outputTokens) ||
            !Number.isFinite(Number(result.usage.actualProviderCostUsd)) ||
            !Number.isFinite(result.usage.clientRequestSeconds?.total)) throw Error('Invalid completed pass');
      });
      const allFour = passes.map(pass => item.passes[pass].score.allFour);
      if (item.repeatVariation.allFourRange?.[0] !== Math.min(...allFour) ||
          item.repeatVariation.allFourRange?.[1] !== Math.max(...allFour)) throw Error('Score range mismatch');
      item.repeatComparisons.forEach(pair => {
        if (pair.denominator !== 60 || pair.fourFieldVectorChanges !== 0 ||
            pair.nativeProbabilityDictionaryChanges !== 0 || pair.vendorConfidenceChanges !== 0) throw Error('Repeat summary mismatch');
      });
    });
    report.pairedP1P2.forEach((pair, index) => {
      if (pair.stage !== passes[index] || pair.denominator !== 60 ||
          !Array.isArray(pair.fourFieldVectorChangedIds) ||
          !Number.isInteger(pair.fourFieldVectorChanges) ||
          pair.fourFieldVectorChanges < 0 || pair.fourFieldVectorChanges > 60 ||
          pair.fourFieldVectorChangedIds.length !== pair.fourFieldVectorChanges ||
          pair.scoreDeltaP2MinusP1?.allFour !==
            report.conditions.P2.passes[pair.stage].score.allFour - report.conditions.P1.passes[pair.stage].score.allFour ||
          fields.some(([key]) => pair.scoreDeltaP2MinusP1?.fields?.[key] !==
            report.conditions.P2.passes[pair.stage].score.fields[key] -
              report.conditions.P1.passes[pair.stage].score.fields[key])) throw Error('Pair mismatch');
    });
  };

  const scoreMeter = (condition, label, value) =>
    `<meter min="0" max="60" value="${esc(value)}" aria-label="${esc(condition)} ${esc(label)}: ${esc(value)} out of 60">${esc(value)} out of 60</meter>`;

  const totals = condition => {
    const runs = passes.map(pass => condition.passes[pass].usage);
    const durations = runs.map(item => item.clientRequestSeconds.total);
    return {
      input: runs.reduce((sum, item) => sum + item.inputTokens, 0),
      output: runs.reduce((sum, item) => sum + item.outputTokens, 0),
      cost: runs.reduce((sum, item) => sum + Number(item.actualProviderCostUsd), 0),
      low: Math.min(...durations), high: Math.max(...durations)
    };
  };

  fetch('./kev-native-prompt-findings.json', {cache: 'no-store'}).then(response => {
    if (!response.ok) throw Error('Kev prompt evidence unavailable');
    return response.json();
  }).then(report => {
    validate(report);
    const firstPair = report.pairedP1P2[0];
    const p1Score = report.conditions.P1.passes.fresh1.score;
    const p2Score = report.conditions.P2.passes.fresh1.score;
    const [largestField, largestLabel] = fields.reduce((largest, field) =>
      Math.abs(firstPair.scoreDeltaP2MinusP1.fields[field[0]]) >
      Math.abs(firstPair.scoreDeltaP2MinusP1.fields[largest[0]]) ? field : largest);
    const largestDelta = firstPair.scoreDeltaP2MinusP1.fields[largestField];
    const fieldRows = fields.map(([key, label]) => {
      const p1 = report.conditions.P1.passes.fresh1.score.fields[key];
      const p2 = report.conditions.P2.passes.fresh1.score.fields[key];
      const delta = firstPair.scoreDeltaP2MinusP1.fields[key];
      return `<tr><th scope="row">${esc(label)}</th><td>${esc(p1)} / 60</td><td>${esc(p2)} / 60</td><td>${esc(signed(delta))}</td></tr>`;
    }).join('');
    const scoreCards = ['P1', 'P2'].map(condition => {
      const item = report.conditions[condition];
      const score = item.passes.fresh1.score;
      return `<article class="condition-card"><div class="condition-card-header"><span class="condition-code">${esc(condition)}</span>` +
        `<span class="condition-tag">${esc(names[condition])}</span></div>` +
        `<strong class="condition-score">${esc(score.allFour)}<small> / 60</small></strong>` +
        `${scoreMeter(condition, 'All four fields', score.allFour)}<dl class="data-list">` +
        fields.map(([key, label]) => `<div><dt>${esc(label)}</dt><dd><strong>${esc(score.fields[key])} / 60</strong>${scoreMeter(condition, label, score.fields[key])}</dd></div>`).join('') +
        `</dl><p class="small-note">Three passes returned the same score and the same answers.</p></article>`;
    }).join('');
    const changedIds = firstPair.fourFieldVectorChangedIds.map(esc).join(', ');
    const usage = Object.fromEntries(['P1', 'P2'].map(condition => [condition, totals(report.conditions[condition])]));
    const usageRows = ['P1', 'P2'].map(condition => `<tr><th scope="row">${esc(condition)}</th>` +
      `<td>${esc(integer(usage[condition].input))}</td><td>${esc(integer(usage[condition].output))}</td>` +
      `<td>$${esc(usage[condition].cost.toFixed(9))}</td>` +
      `<td>${esc(usage[condition].low.toFixed(1))} to ${esc(usage[condition].high.toFixed(1))} seconds</td></tr>`).join('');
    const passRows = passes.map(pass => `<tr><th scope="row">${esc(passName(pass))}</th>` +
      `<td>${esc(report.conditions.P1.passes[pass].score.allFour)} / 60</td>` +
      `<td>${esc(report.conditions.P2.passes[pass].score.allFour)} / 60</td>` +
      `<td>${esc(report.pairedP1P2.find(pair => pair.stage === pass).fourFieldVectorChanges)} / 60</td></tr>`).join('');

    target.setAttribute?.('aria-busy', 'false');
    target.innerHTML = `<div class="analysis-lead"><p><strong>P1 scored ${esc(p1Score.allFour)}/${esc(report.denominator)}; P2 scored ${esc(p2Score.allFour)}/${esc(report.denominator)}.</strong> ` +
      `${esc(firstPair.fourFieldVectorChanges)} of ${esc(report.denominator)} reviews changed at least one answer. ` +
      `The largest field tradeoff was ${esc(largestLabel.toLowerCase())}: ` +
      `P1 matched ${esc(p1Score.fields[largestField])} references and P2 matched ${esc(p2Score.fields[largestField])}, ` +
      `a change of ${esc(signed(largestDelta))}.</p></div>` +
      `<div class="detail-lower">${scoreCards}</div>` +
      `<div class="table-wrap" tabindex="0" role="region" aria-label="Kev field score comparison, scroll horizontally on small screens">` +
      `<table><caption>Field agreement in every pass</caption><thead><tr><th scope="col">Field</th><th scope="col">P1</th><th scope="col">P2</th><th scope="col">P2 minus P1</th></tr></thead><tbody>${fieldRows}</tbody></table></div>` +
      `<p class="analysis-caveat"><strong>Repeat check:</strong> Within P1 and within P2, all three pass pairs had zero answer, probability-dictionary, and vendor-confidence changes across the same 60 reviews.</p>` +
      `<details><summary>Which seven reviews changed between P1 and P2?</summary><p>${changedIds}</p>` +
      `<div class="table-wrap" tabindex="0" role="region" aria-label="Kev paired prompt results, scroll horizontally on small screens">` +
      `<table><caption>Paired prompt comparison by pass</caption><thead><tr><th scope="col">Pass</th><th scope="col">P1 all four</th><th scope="col">P2 all four</th><th scope="col">Changed reviews</th></tr></thead><tbody>${passRows}</tbody></table></div>` +
      `<p>The paired passes list the reviews changed under each prompt condition. Native probability dictionaries and vendor confidence are reported separately; neither is treated as a calibrated correctness probability.</p></details>` +
      `<details><summary>Observed usage, cost, and request time</summary>` +
      `<div class="table-wrap" tabindex="0" role="region" aria-label="Kev prompt usage and cost, scroll horizontally on small screens">` +
      `<table><caption>Totals across three passes</caption><thead><tr><th scope="col">Condition</th><th scope="col">Input tokens</th><th scope="col">Output tokens</th><th scope="col">Observed cost</th><th scope="col">Client time per pass</th></tr></thead><tbody>${usageRows}</tbody></table></div>` +
      `<p class="small-note">Request time is client-observed and includes network and local work. It is not provider inference time.</p></details>` +
      `<details><summary>What was held constant?</summary><p>${esc(report.nativePromptEquivalence.meaning)} ${esc(report.nativePromptEquivalence.wireEquivalence)}</p>` +
      `<p>The 60 reference labels are provisional development labels. These results describe the saved requests and do not estimate performance on new candidate feedback.</p></details>` +
      `<p class="source-links"><a href="./kev-native-prompt-findings.json">Read the machine-readable evidence</a> · ` +
      `<a href="https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/KEV_NATIVE_PROMPT_FINDINGS_2026-10-06.md">Read the source-bound findings</a></p>`;
  }).catch(error => {
    console.error(error);
    fail();
  });
})();
