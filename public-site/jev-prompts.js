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
    if (expectedStatus === 'complete' && (item.outcomes.never_sent || item.outcomes.unknown_cost_http_429 || item.outcomes.unknown_cost_transport_timeout)) throw Error('Complete pass has unfinished outcomes');
    if (expectedStatus === 'stopped' && !item.outcomes.never_sent) throw Error('Stopped pass lacks unsent outcomes');
  };

  const validateInterrupted = report => {
    const parent = report.passes.P2.fresh2;
    const tail = report.continuations?.P2fresh2tail;
    const combined = report.composites?.P2fresh2;
    if (tail?.status !== 'interrupted' || tail?.score?.denominator !== 42 ||
        tail.score.valid !== tail.outcomes?.valid ||
        Object.values(tail.outcomes).reduce((sum, value) => sum + value, 0) !== 42 ||
        combined?.status !== 'interrupted_parent_with_stopped_continuation' ||
        combined.cleanRepeatCredit !== false || combined.neverSent !== 0 ||
        JSON.stringify(combined.parentOriginal) !== JSON.stringify(parent) ||
        combined.score?.denominator !== 60 || combined.score.valid !== parent.score.valid + tail.score.valid ||
        combined.score.allFour !== parent.score.allFour + tail.score.allFour ||
        combined.outcomes?.valid !== combined.score.valid ||
        Object.values(combined.outcomes).reduce((sum, value) => sum + value, 0) !== 60 ||
        combined.outcomes.unknown_cost_http_429 !== parent.outcomes.unknown_cost_http_429 ||
        combined.outcomes.unknown_cost_transport_timeout !== tail.outcomes.unknown_cost_transport_timeout ||
        combined.outcomes.invalid_native_distribution !== tail.outcomes.invalid_native_distribution ||
        Math.abs(Number(combined.knownCostUsd) - Number(parent.knownCostUsd) - Number(tail.knownCostUsd)) > 1e-9 ||
        Math.abs(Number(combined.unknownUpperBoundUsd) - Number(parent.unknownUpperBoundUsd) - Number(tail.unknownUpperBoundUsd)) > 1e-9) throw Error('Invalid interrupted composite');
    fields.forEach(([key]) => {
      if (combined.score.fields?.[key] !== parent.score.fields[key] + tail.score.fields?.[key]) throw Error('Invalid composite field');
    });
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
        Object.keys(report.passes || {}).sort().join(',') !== 'P0,P1,P2') throw Error('Invalid report');
    ['P0', 'P1'].forEach(condition => ['fresh1', 'fresh2', 'fresh3'].forEach(stage =>
      validatePass(report.passes[condition]?.[stage], 'complete')));
    validatePass(report.passes.P2?.fresh1, 'complete');
    validatePass(report.passes.P2?.fresh2, 'stopped');
    validatePass(report.passes.P2?.fresh3, 'complete');
    validateInterrupted(report);
    validateComparison(report.comparisons?.P0fresh1fresh2, 60);
    validateComparison(report.comparisons?.P0fresh2fresh3, 59);
    validateComparison(report.comparisons?.P0P1fresh1, 60);
    validateComparison(report.comparisons?.P1repeat,
      Math.min(report.passes.P1.fresh1.score.valid, report.passes.P1.fresh2.score.valid));
    validateComparison(report.comparisons?.P1P2fresh1, 60);
    validateComparison(report.comparisons?.P1P2fresh2shared,
      Math.min(report.passes.P1.fresh2.score.valid, report.passes.P2.fresh2.score.valid));
    validateComparison(report.comparisons?.P2fresh1fresh3, 60);
    validateComparison(report.comparisons?.P1P2fresh3, 60);
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
    const p0 = report.passes.P0;
    const p1First = report.passes.P1.fresh1;
    const p1Second = report.passes.P1.fresh2;
    const p1Third = report.passes.P1.fresh3;
    const p2First = report.passes.P2.fresh1;
    const p2Third = report.passes.P2.fresh3;
    const stopped = report.passes.P2.fresh2;
    const tail = report.continuations.P2fresh2tail;
    const combined = report.composites.P2fresh2;
    const p0Repeat = report.comparisons.P0fresh1fresh2;
    const p0Third = report.comparisons.P0fresh2fresh3;
    const repeat = report.comparisons.P1repeat;
    const prompt = report.comparisons.P1P2fresh1;
    const p2Repeat = report.comparisons.P2fresh1fresh3;
    const thirdMatched = report.comparisons.P1P2fresh3;
    const repeatProbability = uniqueCount(repeat, 'probabilityChangedIds');
    const repeatConfidence = uniqueCount(repeat, 'confidenceChangedIds');
    const promptProbability = uniqueCount(prompt, 'probabilityChangedIds');
    const promptConfidence = uniqueCount(prompt, 'confidenceChangedIds');
    const firstScores = [p0.fresh1, p1First, p2First].map(item => item.score.allFour);
    const firstScoreText = firstScores.every(value => value === firstScores[0])
      ? `P0, P1, and P2 each matched ${firstScores[0]}/60 on all four answers`
      : `P0 matched ${firstScores[0]}/60, P1 ${firstScores[1]}/60, and P2 ${firstScores[2]}/60`;
    const comparisonRows = fields.map(([key, label]) => `<tr><th scope="row">${esc(label)}</th>` +
      `<td>${esc(repeat.fields[key].choiceChangedIds.length)}</td>` +
      `<td>${esc(repeat.fields[key].probabilityChangedIds.length)}</td>` +
      `<td>${esc(repeat.fields[key].confidenceChangedIds.length)}</td></tr>`).join('');
    const usageRows = [
      ['P0', 'Pass 1', p0.fresh1], ['P0', 'Pass 2', p0.fresh2], ['P0', 'Pass 3', p0.fresh3],
      ['P1', 'Pass 1', p1First], ['P1', 'Pass 2', p1Second], ['P1', 'Pass 3', p1Third],
      ['P2', 'Pass 1', p2First], ['P2', 'Stopped pass 2 parent', stopped],
      ['P2', 'Stopped pass 2 tail', tail], ['P2', 'Interrupted pass 2 composite', combined],
      ['P2', 'Pass 3', p2Third]
    ].map(([condition, stage, item]) => `<tr><th scope="row">${esc(condition)} ${esc(stage)}</th>` +
      `<td>${esc(integer(item.inputTokens))}</td><td>${esc(integer(item.outputTokens))}</td>` +
      `<td>${esc(money(item.knownCostUsd))}</td><td>${esc(money(item.unknownUpperBoundUsd))}</td>` +
      `<td>${esc(item.clientSeconds.toFixed(1))} seconds</td></tr>`).join('');

    target.setAttribute?.('aria-busy', 'false');
    target.innerHTML = `<div class="analysis-lead"><p><strong>In their first complete passes, ${esc(firstScoreText)}.</strong> ` +
      `P1 and P2 differed on ${esc(prompt.fourFieldVectorChangedIds.length)} ${noun(prompt.fourFieldVectorChangedIds.length, 'review')}; native probabilities changed on ${esc(promptProbability)} reviews and vendor confidence on ${esc(promptConfidence)}.</p></div>` +
      `<div class="detail-lower">${scoreCard('P0', p0.fresh1, 'Pass 1')}${scoreCard('P1', p1First, 'Pass 1')}${scoreCard('P2', p2First, 'Pass 1')}</div>` +
      `<article class="analysis-caveat"><h3>P0 completed three full passes</h3><p>All-four matches were ${esc(p0.fresh1.score.allFour)}/60, ${esc(p0.fresh2.score.allFour)}/60, and ${esc(p0.fresh3.score.allFour)}/60. ` +
      `The third pass had ${esc(p0.fresh3.score.valid)} valid responses; DEV-040 had an invalid native distribution. The provider cost for that response remains counted. ` +
      `Across the first two passes, ${esc(p0Repeat.fourFieldVectorChangedIds.length)}/60 valid answer vectors changed. Across passes 2 and 3, ${esc(p0Third.fourFieldVectorChangedIds.length)}/${esc(p0Third.denominator)} shared valid vectors changed.</p></article>` +
      `<article class="analysis-caveat"><h3>P1 completed three full passes</h3><p>All-four matches were ${esc(p1First.score.allFour)}/60, ${esc(p1Second.score.allFour)}/60, and ${esc(p1Third.score.allFour)}/60. ` +
      `Pass 2 had ${esc(p1Second.score.valid)} valid responses; DEV-056 had an invalid native distribution and its provider cost remains counted. ` +
      `Among ${esc(repeat.denominator)} reviews valid in both first passes, ${esc(repeat.fourFieldVectorChangedIds.length)} ${noun(repeat.fourFieldVectorChangedIds.length, 'answer vector')} changed. Probability values changed on ${esc(repeatProbability)} reviews and vendor confidence on ${esc(repeatConfidence)}.</p></article>` +
      `<article class="analysis-caveat"><h3>P2 pass 2 remains interrupted</h3><p>The original parent saved ${esc(stopped.score.valid)} valid responses, retained ${esc(stopped.outcomes.unknown_cost_http_429)} HTTP 429 attempt with an unknown charge, and left ${esc(stopped.outcomes.never_sent)} positions unsent. ` +
      `A separate continuation attempted those 42 positions: ${esc(tail.score.valid)} valid, ${esc(tail.outcomes.invalid_native_distribution)} invalid DEV-040, and ${esc(tail.outcomes.unknown_cost_transport_timeout)} timed-out DEV-060 with an unknown charge. ` +
      `The combined accounting covers all 60 positions: ${esc(combined.score.valid)} valid, ${esc(combined.outcomes.invalid_native_distribution)} invalid, ${esc(combined.outcomes.unknown_cost_http_429 + combined.outcomes.unknown_cost_transport_timeout)} unknown-cost attempts, and ${esc(combined.neverSent)} unsent. Its ${esc(combined.score.allFour)}/60 all-four figure is interrupted coverage, not a clean repeat or ranking result. The parent counts remain preserved.</p></article>` +
      `<article class="analysis-caveat"><h3>P2 pass 3 completed separately</h3><p>All ${esc(p2Third.score.valid)} responses were valid, with ${esc(p2Third.score.allFour)}/60 all-four matches. ` +
      `Against completed P2 pass 1, ${esc(p2Repeat.fourFieldVectorChangedIds.length)}/${esc(p2Repeat.denominator)} answer vectors changed (${esc(p2Repeat.fourFieldVectorChangedIds.join(', ') || 'none')}). ` +
      `Matched P1 and P2 pass 3 results differed on ${esc(thirdMatched.fourFieldVectorChangedIds.length)}/${esc(thirdMatched.denominator)} answer vectors (${esc(thirdMatched.fourFieldVectorChangedIds.join(', ') || 'none')}). ` +
      `The interrupted P2 pass 2 remains ineligible as a clean repeat.</p></article>` +
      `<details><summary>Labels and distributions changed in different ways</summary>` +
      `<div class="table-wrap" tabindex="0" role="region" aria-label="Jev P1 repeat changes by field, scroll horizontally on small screens"><table>` +
      `<caption>Changes across ${esc(repeat.denominator)} reviews valid in both P1 passes</caption><thead><tr><th scope="col">Field</th><th scope="col">Answer changes</th><th scope="col">Probability changes</th><th scope="col">Confidence changes</th></tr></thead><tbody>${comparisonRows}</tbody></table></div>` +
      `<p>The same labels can come with different probability values. Vendor confidence is a separate provider value; neither measure is treated as a calibrated probability of correctness.</p></details>` +
      `<details><summary>Observed tokens, cost, and client time</summary><div class="table-wrap" tabindex="0" role="region" aria-label="Jev native prompt usage, scroll horizontally on small screens"><table>` +
      `<caption>Measured usage for each saved pass</caption><thead><tr><th scope="col">Pass</th><th scope="col">Input tokens</th><th scope="col">Output tokens</th><th scope="col">Known cost</th><th scope="col">Unknown-charge bound</th><th scope="col">Client time</th></tr></thead><tbody>${usageRows}</tbody></table></div>` +
      `<p class="small-note">Token totals are provider-reported. Client time includes network and local work; it is not pure inference time. DEV-018 and DEV-060 returned no usage and retain separate unknown-charge bounds.</p></details>` +
      `<details><summary>Evidence and comparison limits</summary><p>The P0/P1/P2 comparison shares the native route, parser, labels, policy, criteria, record order and feedback. The Choice question instructions differ. These are native prompt analogues, not byte-identical chat prompts.</p>` +
      `<p>${esc(report.sourceBindings.length)} source ${noun(report.sourceBindings.length, 'binding')} ${report.sourceBindings.length === 1 ? 'covers' : 'cover'} the frozen references, manifests, reviewed receipts, raw attempts, endpoint records and budget reconciliation. The test uses provisional development labels and does not measure performance on new candidate feedback.</p></details>` +
      `<p class="source-links"><a href="./jev-native-prompt-findings.json">Read the machine-readable evidence</a> · ` +
      `<a href="https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/JEV_NATIVE_PROMPT_FINDINGS_2026-10-06.md">Read the source-bound findings</a></p>`;
  }).catch(error => {
    console.error(error);
    fail();
  });
})();
