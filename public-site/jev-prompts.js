/* Source-bound Jev native prompt results, including an interrupted pass. */
(() => {
  const target = document.getElementById('jev-prompt-results');
  if (!target) return;
  target.setAttribute?.('aria-live', 'polite');
  target.setAttribute?.('aria-busy', 'true');

  const fields = [
    ['sentiment', 'Sentiment'],
    ['follow_up_needed', 'Follow-up'],
    ['serious_concern_reported', 'Serious concern'],
    ['testimonial_potential', 'Testimonial']
  ];
  const esc = value => String(value).replace(/[&<>"']/g,
    character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
  const integer = value => Number(value).toLocaleString('en-US');
  const money = value => `$${Number(value).toFixed(9)}`;
  const noun = (value, singular, plural = `${singular}s`) => value === 1 ? singular : plural;
  const fail = () => {
    target.setAttribute?.('aria-busy', 'false');
    target.innerHTML = '<p class="analysis-caveat" role="alert"><strong>Jev prompt results could not be loaded.</strong> The source evidence is unavailable or incomplete.</p>';
  };

  const validatePass = (item, expectedStatus) => {
    const score = item?.score;
    if (item?.status !== expectedStatus || score?.denominator !== 60 ||
        !Number.isInteger(score.valid) || !Number.isInteger(score.allFour) ||
        score.valid < 0 || score.valid > 60 || score.allFour < 0 || score.allFour > score.valid) throw Error('Invalid pass');
    fields.forEach(([key]) => {
      if (!Number.isInteger(score.fields?.[key]) || score.fields[key] < 0 || score.fields[key] > score.valid) throw Error('Invalid field score');
    });
    const outcomes = Object.values(item.outcomes || {});
    if (!outcomes.length || outcomes.some(value => !Number.isInteger(value) || value < 0) ||
        outcomes.reduce((sum, value) => sum + value, 0) !== 60 || item.outcomes.valid !== score.valid ||
        !Number.isInteger(item.inputTokens) || item.inputTokens < 0 ||
        !Number.isInteger(item.outputTokens) || item.outputTokens < 0 ||
        !Number.isFinite(Number(item.knownCostUsd)) || Number(item.knownCostUsd) < 0 ||
        !Number.isFinite(Number(item.unknownUpperBoundUsd)) || Number(item.unknownUpperBoundUsd) < 0 ||
        !Number.isFinite(item.clientSeconds) || item.clientSeconds < 0) throw Error('Invalid pass accounting');
    if (expectedStatus === 'complete' && (item.outcomes.never_sent || item.outcomes.unknown_cost_http_429)) throw Error('Complete pass has unfinished outcomes');
    if (expectedStatus === 'stopped' && !item.outcomes.never_sent) throw Error('Stopped pass lacks unsent outcomes');
  };

  const validateComparison = (item, maximumDenominator) => {
    if (!item || !Number.isInteger(item.denominator) || item.denominator < 1 ||
        item.denominator > maximumDenominator || !Array.isArray(item.excludedIds) ||
        item.excludedIds.length !== 60 - item.denominator ||
        !Array.isArray(item.fourFieldVectorChangedIds) ||
        item.fourFieldVectorChangedIds.length > item.denominator) throw Error('Invalid comparison');
    fields.forEach(([key]) => {
      const values = item.fields?.[key];
      ['choiceChangedIds', 'probabilityChangedIds', 'confidenceChangedIds'].forEach(name => {
        if (!Array.isArray(values?.[name]) || values[name].length > item.denominator) throw Error('Invalid comparison field');
      });
    });
  };

  const validate = report => {
    if (!report || !Array.isArray(report.sourceBindings) || !report.sourceBindings.length ||
        report.sourceBindings.some(item => typeof item?.path !== 'string' || !/^[a-f0-9]{64}$/.test(item?.sha256)) ||
        Object.keys(report.passes || {}).sort().join(',') !== 'P1,P2') throw Error('Invalid report');
    validatePass(report.passes.P1?.fresh1, 'complete');
    validatePass(report.passes.P1?.fresh2, 'complete');
    validatePass(report.passes.P2?.fresh1, 'complete');
    validatePass(report.passes.P2?.fresh2, 'stopped');
    validateComparison(report.comparisons?.P1repeat,
      Math.min(report.passes.P1.fresh1.score.valid, report.passes.P1.fresh2.score.valid));
    validateComparison(report.comparisons?.P1P2fresh1, 60);
    validateComparison(report.comparisons?.P1P2fresh2shared,
      Math.min(report.passes.P1.fresh2.score.valid, report.passes.P2.fresh2.score.valid));
  };

  const uniqueCount = (comparison, name) => new Set(fields.flatMap(([key]) =>
    comparison.fields[key][name])).size;
  const scoreMeter = (label, value) =>
    `<meter min="0" max="60" value="${esc(value)}" aria-label="${esc(label)}: ${esc(value)} out of 60">${esc(value)} out of 60</meter>`;
  const scoreCard = (condition, pass, title) => {
    const score = pass.score;
    return `<article class="condition-card"><div class="condition-card-header"><span class="condition-code">${esc(condition)}</span>` +
      `<span class="condition-tag">${esc(title)}</span></div><strong class="condition-score">${esc(score.allFour)}<small> / 60</small></strong>` +
      `${scoreMeter(`${condition} ${title} all four fields`, score.allFour)}<dl class="data-list">` +
      fields.map(([key, label]) => `<div><dt>${esc(label)}</dt><dd><strong>${esc(score.fields[key])} / 60</strong>${scoreMeter(`${condition} ${title} ${label}`, score.fields[key])}</dd></div>`).join('') +
      `</dl><p class="small-note">${esc(score.valid)} valid responses; ${esc(60 - score.valid)} could not be scored.</p></article>`;
  };

  fetch('./jev-native-prompt-findings.json', {cache: 'no-store'}).then(response => {
    if (!response.ok) throw Error('Jev prompt evidence unavailable');
    return response.json();
  }).then(report => {
    validate(report);
    const p1First = report.passes.P1.fresh1;
    const p1Second = report.passes.P1.fresh2;
    const p2First = report.passes.P2.fresh1;
    const stopped = report.passes.P2.fresh2;
    const repeat = report.comparisons.P1repeat;
    const prompt = report.comparisons.P1P2fresh1;
    const repeatProbability = uniqueCount(repeat, 'probabilityChangedIds');
    const repeatConfidence = uniqueCount(repeat, 'confidenceChangedIds');
    const promptProbability = uniqueCount(prompt, 'probabilityChangedIds');
    const promptConfidence = uniqueCount(prompt, 'confidenceChangedIds');
    const invalid = p1Second.outcomes.invalid_native_distribution || 0;
    const unknown = stopped.outcomes.unknown_cost_http_429 || 0;
    const unsent = stopped.outcomes.never_sent || 0;
    const firstScoreText = p1First.score.allFour === p2First.score.allFour
      ? `both scored ${p1First.score.allFour}/${p1First.score.denominator}`
      : `scored ${p1First.score.allFour}/${p1First.score.denominator} for P1 and ${p2First.score.allFour}/${p2First.score.denominator} for P2`;
    const comparisonRows = fields.map(([key, label]) => `<tr><th scope="row">${esc(label)}</th>` +
      `<td>${esc(repeat.fields[key].choiceChangedIds.length)}</td>` +
      `<td>${esc(repeat.fields[key].probabilityChangedIds.length)}</td>` +
      `<td>${esc(repeat.fields[key].confidenceChangedIds.length)}</td></tr>`).join('');
    const usageRows = [
      ['P1', 'Pass 1', p1First], ['P1', 'Pass 2', p1Second],
      ['P2', 'Pass 1', p2First], ['P2', 'Stopped pass 2', stopped]
    ].map(([condition, stage, item]) => `<tr><th scope="row">${esc(condition)} ${esc(stage)}</th>` +
      `<td>${esc(integer(item.inputTokens))}</td><td>${esc(integer(item.outputTokens))}</td>` +
      `<td>${esc(money(item.knownCostUsd))}</td><td>${esc(money(item.unknownUpperBoundUsd))}</td>` +
      `<td>${esc(item.clientSeconds.toFixed(1))} seconds</td></tr>`).join('');

    target.setAttribute?.('aria-busy', 'false');
    target.innerHTML = `<div class="analysis-lead"><p><strong>The first complete P1 and P2 passes ${esc(firstScoreText)}.</strong> ` +
      `At least one answer changed on ${esc(prompt.fourFieldVectorChangedIds.length)} ${noun(prompt.fourFieldVectorChangedIds.length, 'review')}, while native probabilities changed on ${esc(promptProbability)} reviews and vendor confidence changed on ${esc(promptConfidence)}.</p></div>` +
      `<div class="detail-lower">${scoreCard('P1', p1First, 'Pass 1')}${scoreCard('P2', p2First, 'Pass 1')}</div>` +
      `<article class="analysis-caveat"><h3>P1 completed a second strict pass</h3><p>The second P1 pass scored <strong>${esc(p1Second.score.allFour)}/${esc(p1Second.score.denominator)}</strong> with ${esc(p1Second.score.valid)} valid responses. ` +
      `${esc(invalid)} ${noun(invalid, 'response')} had an invalid native probability distribution and remains in the 60-review denominator. This validation failure does not establish that the chosen labels were wrong. Among the ${esc(repeat.denominator)} reviews valid in both P1 passes, ` +
      `<strong>${esc(repeat.fourFieldVectorChangedIds.length)} ${noun(repeat.fourFieldVectorChangedIds.length, 'review')} had a changed answer</strong>. Probability values changed on ${esc(repeatProbability)} reviews and vendor confidence changed on ${esc(repeatConfidence)}.</p></article>` +
      `<article class="analysis-caveat"><h3>P2 pass 2 stopped before completion</h3><p>It saved ${esc(stopped.score.valid)} valid responses, then retained ${esc(unknown)} request with an unknown charge and left ${esc(unsent)} reviews unsent. ` +
      `This is coverage accounting, not a completed score or ranking result.</p></article>` +
      `<details><summary>Labels and distributions changed in different ways</summary>` +
      `<div class="table-wrap" tabindex="0" role="region" aria-label="Jev P1 repeat changes by field, scroll horizontally on small screens"><table>` +
      `<caption>Changes across ${esc(repeat.denominator)} reviews valid in both P1 passes</caption><thead><tr><th scope="col">Field</th><th scope="col">Answer changes</th><th scope="col">Probability changes</th><th scope="col">Confidence changes</th></tr></thead><tbody>${comparisonRows}</tbody></table></div>` +
      `<p>The same labels can come with different probability values. Vendor confidence is a separate provider value; neither measure is treated as a calibrated probability of correctness.</p></details>` +
      `<details><summary>Observed tokens, cost, and client time</summary><div class="table-wrap" tabindex="0" role="region" aria-label="Jev native prompt usage, scroll horizontally on small screens"><table>` +
      `<caption>Measured usage for each saved pass</caption><thead><tr><th scope="col">Pass</th><th scope="col">Input tokens</th><th scope="col">Output tokens</th><th scope="col">Known cost</th><th scope="col">Unknown-charge bound</th><th scope="col">Client time</th></tr></thead><tbody>${usageRows}</tbody></table></div>` +
      `<p class="small-note">Token totals are provider-reported. Client time includes network and local work; it is not pure inference time. The stopped pass has token counts only for its successful responses.</p></details>` +
      `<details><summary>Evidence and comparison limits</summary><p>The first-pass P1/P2 comparison shares the native route, parser, labels, policy, criteria, record order and feedback. The Choice question instructions differ. These are native prompt analogues, not byte-identical chat prompts.</p>` +
      `<p>${esc(report.sourceBindings.length)} source ${noun(report.sourceBindings.length, 'binding')} ${report.sourceBindings.length === 1 ? 'covers' : 'cover'} the frozen references, manifests, reviewed receipts, raw attempts, endpoint records and budget reconciliation. The test uses provisional development labels and does not measure performance on new candidate feedback.</p></details>` +
      `<p class="source-links"><a href="./jev-native-prompt-findings.json">Read the machine-readable evidence</a> · ` +
      `<a href="https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/JEV_NATIVE_PROMPT_FINDINGS_2026-10-06.md">Read the source-bound findings</a></p>`;
  }).catch(error => {
    console.error(error);
    fail();
  });
})();
