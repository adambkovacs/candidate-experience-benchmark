/* Fixed first-P0 comparison of saved general and native decision outcomes. */
(() => {
  'use strict';
  const mount = document.getElementById('cross-category');
  const github = 'https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/';
  const ids = Array.from({length: 60}, (_, index) => `DEV-${String(index + 1).padStart(3, '0')}`);
  const sha = value => /^[a-f0-9]{64}$/.test(value || '');
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
  const sourceUrl = value => typeof value === 'string' && value.startsWith(github) &&
    !/[?#]/.test(value.slice(github.length));
  const stratumLabel = value => value === 'historical-first-P0' ? 'Historical first P0' :
    value === 'declared-fresh1-P0' ? 'Declared fresh1/pass1 P0' : 'Native fresh1 P0';
  const outcomeLabels = {
    both_match: 'Both match reference',
    general_only_match: 'Only general matches',
    native_only_match: 'Only native matches',
    neither_match: 'Both miss reference',
    general_no_valid_output: 'General output unusable or absent',
  };
  const fields = ['sentiment', 'follow_up_needed', 'serious_concern_reported', 'testimonial_potential'];
  const fieldLabels = {sentiment:'Sentiment', follow_up_needed:'Follow-up needed',
    serious_concern_reported:'Serious concern reported', testimonial_potential:'Testimonial potential'};
  const fieldChoices = {sentiment:['positive', 'negative', 'mixed', 'neutral', 'insufficient_information'],
    follow_up_needed:['yes', 'no', 'insufficient_information'],
    serious_concern_reported:['yes', 'no', 'insufficient_information'],
    testimonial_potential:['yes', 'no', 'insufficient_information']};
  const choiceLabel = value => value === 'insufficient_information' ? 'Insufficient information' :
    value === 'no_valid_output' ? 'No valid output' : value[0].toUpperCase() + value.slice(1);

  function pairTally(general, native) {
    const byId = new Map(native.cases.map(row => [row.id, row]));
    const tally = Object.fromEntries(Object.keys(outcomeLabels).map(key => [key, []]));
    for (const row of general.cases) {
      const other = byId.get(row.id);
      const key = row.allFourMatch === null ? 'general_no_valid_output' :
        row.allFourMatch && other.allFourMatch ? 'both_match' :
        row.allFourMatch ? 'general_only_match' :
        other.allFourMatch ? 'native_only_match' : 'neither_match';
      tally[key].push(row.id);
    }
    return tally;
  }

  function fieldSummary(references, run, field) {
    const choices = fieldChoices[field];
    if (!choices || references.length !== run.cases.length) throw Error('Field comparison positions changed');
    const columns = [...choices, 'no_valid_output'];
    const matrix = Object.fromEntries(choices.map(reference =>
      [reference, Object.fromEntries(columns.map(prediction => [prediction, 0]))]));
    const statuses = {};
    let matches = 0, valid = 0;
    references.forEach((reference, index) => {
      const actual = reference.reference[field];
      const answer = run.cases[index];
      const prediction = answer.prediction === null ? 'no_valid_output' : answer.prediction?.[field];
      if (!Object.hasOwn(matrix, actual) || !columns.includes(prediction)) {
        throw Error('Field comparison label changed');
      }
      matrix[actual][prediction]++;
      if (prediction === 'no_valid_output') statuses[answer.status] = (statuses[answer.status] || 0) + 1;
      else { valid++; matches += Number(actual === prediction); }
    });
    const positive = field === 'sentiment' ? null : {
      truePositive: matrix.yes.yes,
      predictedYes: choices.reduce((count,reference) => count + matrix[reference].yes, 0),
      referenceYesValid: columns.filter(value => value !== 'no_valid_output')
        .reduce((count,prediction) => count + matrix.yes[prediction], 0),
      referenceYesUnusable: matrix.yes.no_valid_output,
    };
    return {field, choices, columns, matrix, statuses, matches, valid,
      total:references.length, positive};
  }

  function validate(data) {
    if (data?.schema !== 'cross-category-public-v1' || data.inferenceRequests !== 0 ||
        data.counts?.historicalGeneral !== 117 || data.counts?.declaredGeneral !== 32 ||
        data.counts?.native !== 7 || !Array.isArray(data.runs) || data.runs.length !== 156 ||
        !Array.isArray(data.cases) || data.cases.length !== 60 ||
        !Array.isArray(data.caseSummaries) || data.caseSummaries.length !== 60 ||
        !sha(data.sourceSha256?.['results/cross-category-v1/dataset.json']) ||
        !sha(data.sourceSha256?.['results/cross-category-v1/plan.json']) ||
        !sha(data.sourceSha256?.['results/cross-category-v1/findings.md'])) {
      throw Error('Cross-category source header changed');
    }
    if (!data.cases.every((row, index) => row.id === ids[index] &&
        typeof row.feedback === 'string' && row.feedback &&
        row.reference && fields.every(field => fieldChoices[field].includes(row.reference[field])))) {
      throw Error('Cross-category reference cases changed');
    }
    const seen = new Set();
    const strata = {'historical-first-P0': 0, 'declared-fresh1-P0': 0, 'native-first-P0': 0};
    for (const run of data.runs) {
      if (!run.runId || seen.has(run.runId) || !sourceUrl(run.sourceUrl) || !sha(run.sourceSha256) ||
          !Object.hasOwn(strata, run.stratum) || !Array.isArray(run.cases) || run.cases.length !== 60 ||
          !run.controls || !run.scores || !run.outcomes ||
          run.controls.condition !== 'P0' ||
          (run.category === 'dedicated-decision') !== (run.stratum === 'native-first-P0') ||
          !run.cases.every((row, index) => row.id === ids[index] &&
            (typeof row.allFourMatch === 'boolean' || row.allFourMatch === null) &&
            (row.allFourMatch === null ? row.differentFields === null && row.prediction === null :
              Array.isArray(row.differentFields) && row.prediction &&
              fields.every(field => fieldChoices[field].includes(row.prediction[field])) &&
              JSON.stringify(row.differentFields) === JSON.stringify(fields.filter(field =>
                row.prediction[field] !== data.cases[index].reference[field])) &&
              row.allFourMatch === (row.differentFields.length === 0))) ||
          run.scores.valid !== run.cases.filter(row => row.allFourMatch !== null).length ||
          run.scores.all_four !== run.cases.filter(row => row.allFourMatch === true).length ||
          fields.some(field => run.scores[field] !== fieldSummary(data.cases, run, field).matches) ||
          Object.values(run.outcomes).reduce((sum, value) => sum + value, 0) !== 60) {
        throw Error('Cross-category run or fixed-60 status changed');
      }
      seen.add(run.runId);
      strata[run.stratum]++;
    }
    if (strata['historical-first-P0'] !== 117 || strata['declared-fresh1-P0'] !== 32 ||
        strata['native-first-P0'] !== 7 ||
        data.caseSummaries.some((row, index) => row.id !== ids[index])) {
      throw Error('Cross-category source selection changed');
    }
    const native = data.runs.filter(run => run.stratum === 'native-first-P0');
    for (const general of data.runs.filter(run => run.category === 'general-llm')) {
      if (Object.keys(general.pairedWithNative || {}).length !== 7) throw Error('Native pair set changed');
      for (const comparator of native) {
        const tally = pairTally(general, comparator);
        const saved = general.pairedWithNative[comparator.runId];
        if (!saved || Object.keys(outcomeLabels).some(key => saved[key] !== tally[key].length)) {
          throw Error('Cross-category paired outcomes changed');
        }
      }
    }
    return data;
  }

  function reviewUrl(id) {
    const address = new URL(location.href);
    for (const key of ['reviewSubset', 'reviewModel', 'reviewField', 'reviewSearch']) address.searchParams.delete(key);
    address.searchParams.set('review', id);
    address.hash = 'review-evidence';
    return address.pathname + address.search + address.hash;
  }

  function linkedIds(values) {
    return values.length ? values.map(id => `<button type="button" data-cross-case="${esc(id)}" aria-label="Inspect ${esc(id)} in both selected runs">${esc(id)}</button>`).join(' ') :
      '<span>None in these 60 reviews.</span>';
  }

  function renderCase(data, general, native, id) {
    const review = data.cases.find(row => row.id === id);
    const generalCase = general.cases.find(row => row.id === id);
    const nativeCase = native.cases.find(row => row.id === id);
    const answer = (label, row) => `<div class="cross-case-answer"><h5>${esc(label)} <span>${esc(row.status)}</span></h5>${row.prediction ? `<dl>${fields.map(field => `<div><dt>${esc(field.replaceAll('_', ' '))}</dt><dd>${esc(row.prediction[field])}${row.differentFields.includes(field) ? ' <em>differs</em>' : ''}</dd></div>`).join('')}</dl>` : '<p>No usable four-field answer in this saved run.</p>'}</div>`;
    return `<div class="cross-case-heading"><p class="eyebrow">Exact saved answers / ${esc(id)}</p><h4>${esc(review.feedback)}</h4><p>The provisional reference and both selected outputs are shown field by field. “Differs” means differs from that reference, not a final adjudication.</p></div><div class="cross-case-grid">${answer('Provisional reference', {status:'v0.2', prediction:review.reference, differentFields:[]})}${answer(`General · ${general.model}`, generalCase)}${answer(`Native · ${native.model}`, nativeCase)}</div><p class="cross-case-source">Source keys: <code>${esc(general.runId)}</code> and <code>${esc(native.runId)}</code> in the <a href="${github}results/cross-category-v1/dataset.json">full dataset ↗</a>. <a href="${esc(reviewUrl(id))}">Seven-native context for ${esc(id)} ↗</a>.</p>`;
  }

  function number(value) {
    return value === null || value === undefined ? 'Unavailable' : String(value);
  }

  function money(value) {
    return value === null || value === undefined ? 'Unavailable' : `$${value}`;
  }

  function controlsTable(general, native) {
    const rows = [
      ['Checkpoint', general.model, native.model],
      ['Saved pass', `${stratumLabel(general.stratum)} · ${general.repeatPass}`, 'Native fresh1 P0'],
      ['Prompt condition', 'P0', 'P0'],
      ['Exact prompt text in this projection', 'Unavailable', 'Unavailable'],
      ['Route', general.controls.route || 'Unavailable', native.controls.route || 'Unavailable'],
      ['Interface', general.controls.interface, native.controls.interface],
      ['Effort', number(general.controls.effort), number(native.controls.effort)],
      ['Request pattern', general.controls.requestPattern || 'Unavailable', native.controls.requestPattern || 'Unavailable'],
      ['Requests with recorded duration', number(general.controls.observedRequestCount), number(native.controls.observedRequestCount)],
      ['Declared batch size', number(general.controls.declaredBatchSize), number(native.controls.declaredBatchSize)],
      ['Provider-reported development charge', money(general.controls.cost.observedUsd), money(native.controls.cost.observedUsd)],
      ['Reconciled known charge', money(general.controls.cost.knownUsd), money(native.controls.cost.knownUsd)],
      ['Price-derived estimate', money(general.controls.cost.estimatedUsd), money(native.controls.cost.estimatedUsd)],
      ['Possible extra-charge bound', money(general.controls.cost.unknownUpperBoundUsd), money(native.controls.cost.unknownUpperBoundUsd)],
      ['Client timing kind', general.controls.timing.kind || 'Unavailable', native.controls.timing.kind || 'Unavailable'],
      ['Client median seconds', number(general.controls.timing.medianSeconds), number(native.controls.timing.medianSeconds)],
    ];
    return `<div class="cross-controls-wrap"><table><caption>Recorded controls and accounting for the selected pair. Unavailable is not zero.</caption>
      <thead><tr><th scope="col">Control</th><th scope="col">General run</th><th scope="col">Native run</th></tr></thead>
      <tbody>${rows.map(([label, left, right]) => `<tr><th scope="row">${esc(label)}</th><td>${esc(left)}</td><td>${esc(right)}</td></tr>`).join('')}</tbody></table></div>
      <p class="cross-basis">Reported and reconciled known charges can describe the same requests; do not add those rows. General cost basis: ${esc(general.controls.cost.basis)} Native cost basis: ${esc(native.controls.cost.basis)} General timing basis: ${esc(general.controls.timing.basis)} Native timing basis: ${esc(native.controls.timing.basis)} Historical route labels can be broad. Client times use different request patterns and are not a shared inference-speed measure.</p>`;
  }

  function rate(numerator, denominator, reason) {
    return denominator ? `${(numerator / denominator * 100).toFixed(1)}% (${numerator}/${denominator})` :
      `Unavailable (${reason})`;
  }

  function renderFieldRun(summary, run, role) {
    const totals = Object.fromEntries(summary.columns.map(column => [column,
      summary.choices.reduce((count, reference) => count + summary.matrix[reference][column], 0)]));
    const unusable = summary.total - summary.valid;
    const statuses = Object.entries(summary.statuses).map(([status,count]) =>
      `${count} ${status.replaceAll('_', ' ')}`).join(', ');
    const positive = summary.positive;
    return `<section class="cross-field-run"><h5>${esc(role)} · ${esc(run.model)}</h5>
      <p class="cross-field-coverage"><strong>${summary.matches}/${summary.total}</strong> match the provisional reference · ${summary.valid}/${summary.total} usable · ${unusable}/${summary.total} no valid output${unusable ? ` (${esc(statuses)})` : ''}.</p>
      <div class="cross-matrix-wrap" role="region" aria-label="${esc(role)} ${esc(fieldLabels[summary.field])} confusion table" tabindex="0"><table>
      <caption>${esc(role)} ${esc(fieldLabels[summary.field])}: provisional reference by saved answer, all ${summary.total} reviews.</caption>
      <thead><tr><th scope="col">Reference</th>${summary.columns.map(column => `<th scope="col">${esc(choiceLabel(column))}</th>`).join('')}<th scope="col">Total</th></tr></thead>
      <tbody>${summary.choices.map(reference => `<tr><th scope="row">${esc(choiceLabel(reference))}</th>${summary.columns.map(column => `<td>${summary.matrix[reference][column]}</td>`).join('')}<td>${summary.columns.reduce((count,column) => count + summary.matrix[reference][column], 0)}</td></tr>`).join('')}</tbody>
      <tfoot><tr><th scope="row">All references</th>${summary.columns.map(column => `<td>${totals[column]}</td>`).join('')}<td>${summary.total}</td></tr></tfoot></table></div>
      ${positive ? `<dl class="cross-positive"><div><dt>Yes precision</dt><dd>${rate(positive.truePositive, positive.predictedYes, 'no saved yes predictions')}</dd></div><div><dt>Yes recall, valid subset</dt><dd>${rate(positive.truePositive, positive.referenceYesValid, 'no reference yes with valid output')}</dd></div></dl>
      <p class="cross-field-note">Recall uses ${positive.referenceYesValid} reference-yes reviews with a valid output. Another ${positive.referenceYesUnusable} reference-yes reviews had no valid output and are excluded from that rate. Precision uses all ${positive.predictedYes} saved yes predictions, including any against an insufficient-information reference.</p>` : ''}</section>`;
  }

  function renderFields(references, general, native) {
    return `<details class="cross-fields"><summary>Field matches and confusion tables</summary>
      <div class="cross-fields-inner"><p>Counts use all 60 reviews. Rows are provisional reference labels; columns are saved answers. Insufficient information stays separate from no, and unusable outputs have their own column.</p>
      ${fields.map(field => {
        const left = fieldSummary(references, general, field);
        const right = fieldSummary(references, native, field);
        return `<details class="cross-field"><summary><span>${esc(fieldLabels[field])}</span><span>General ${left.matches}/60 · Native ${right.matches}/60</span></summary>
          <div class="cross-field-grid">${renderFieldRun(left, general, 'General')}${renderFieldRun(right, native, 'Native')}</div></details>`;
      }).join('')}</div></details>`;
  }

  function renderPair(general, native, references) {
    const tally = pairTally(general, native);
    const pieces = Object.entries(outcomeLabels).map(([key, label]) =>
      `<span class="cross-segment cross-${key}" style="width:${tally[key].length / 60 * 100}%" title="${esc(label)}: ${tally[key].length}"></span>`).join('');
    const aria = Object.entries(outcomeLabels).map(([key, label]) => `${label}: ${tally[key].length}`).join('; ');
    return `<div class="cross-pair-head"><p class="eyebrow">Selected saved runs / P0</p><h3>${esc(general.model)} <span>with</span> ${esc(native.model)}</h3><p>${esc(general.runId)} · ${esc(native.runId)}</p></div>
      <div class="cross-score"><p><strong>${general.scores.all_four}<span>/60</span></strong>General all-four matches <small>${general.scores.valid}/60 usable</small></p><p><strong>${native.scores.all_four}<span>/60</span></strong>Native all-four matches <small>${native.scores.valid}/60 usable</small></p></div>
      <div class="cross-bar" role="img" aria-label="Of 60 reviews: ${esc(aria)}">${pieces}</div>
      <div class="cross-legend">${Object.entries(outcomeLabels).map(([key, label]) => `<span><i class="cross-key cross-${key}"></i>${esc(label)}</span>`).join('')}</div>
      <div class="cross-outcome-wrap"><table><caption>Exact paired outcomes on the same 60 review IDs. Unusable general outputs have their own row.</caption><thead><tr><th scope="col">Outcome</th><th scope="col">Reviews</th><th scope="col">Exact IDs</th></tr></thead><tbody>${Object.entries(outcomeLabels).map(([key, label]) => `<tr><th scope="row">${esc(label)}</th><td>${tally[key].length}</td><td class="cross-ids">${linkedIds(tally[key])}</td></tr>`).join('')}</tbody></table></div>
      <div id="cross-case-detail" class="cross-case-detail" aria-live="polite"></div>
      ${renderFields(references, general, native)}
      <div class="cross-provenance"><p>Saved answer sources: <a href="${esc(general.sourceUrl)}" target="_blank" rel="noopener noreferrer">general case projection ↗</a> · <a href="${esc(native.sourceUrl)}" target="_blank" rel="noopener noreferrer">native projection ↗</a>.</p>${general.runEvidenceLeadUrl ? `<p>The general run's <a href="${esc(general.runEvidenceLeadUrl)}" target="_blank" rel="noopener noreferrer">record lead ↗</a> may cover only one probe or batch; the complete 60-vector source is keyed by <code>${esc(general.sourceCaseKey)}</code> in the public case projection.</p>` : ''}<p><a href="${github}results/cross-category-v1/dataset.json">Full source-bound dataset and four-field predictions ↗</a> · <a href="${github}results/cross-category-v1/plan.json">selection and exclusions ↗</a>.</p></div>
      <details class="cross-controls"><summary>Compare route, effort, batch and accounting</summary>${controlsTable(general, native)}</details>`;
  }

  function renderDifficult(data) {
    const native = data.caseSummaries.filter(row => row.byStratum['native-first-P0'].allFourMatches === 0);
    return `<div class="cross-difficult"><h3>Cases missed by all seven native runs</h3><p>Every ID meeting that rule is shown. General counts use their own 117-row historical and 32-row declared first-pass strata; invalid outputs stay in the row denominator. These ID links open the separate seven-native context.</p><div class="cross-controls-wrap"><table><caption>All-seven-native misses, with general matches, valid outputs and eligible configuration rows.</caption><thead><tr><th scope="col">Review</th><th scope="col">Native matches</th><th scope="col">Historical general match / valid / rows</th><th scope="col">Declared general match / valid / rows</th></tr></thead><tbody>${native.map(row => {const h = row.byStratum['historical-first-P0']; const d = row.byStratum['declared-fresh1-P0']; return `<tr><th scope="row"><a href="${esc(reviewUrl(row.id))}" aria-label="View ${esc(row.id)} in the seven-native review panel">${esc(row.id)}</a></th><td>0/7</td><td>${h.allFourMatches}/${h.validOutputs}/${h.configurationRows}</td><td>${d.allFourMatches}/${d.validOutputs}/${d.configurationRows}</td></tr>`;}).join('')}</tbody></table></div><p>DEV-029 is off-topic under the frozen guide. DEV-030 has an unresolved sentiment boundary. <a href="${github}docs/REFERENCE_REVIEW_V1.md">Read the reference review ↗</a>.</p></div>`;
  }

  async function init() {
    if (!mount) return;
    try {
      const response = await fetch('./cross-category-v1.json', {cache: 'no-store'});
      if (!response.ok) throw Error(`HTTP ${response.status}`);
      const data = validate(await response.json());
      const natives = data.runs.filter(run => run.stratum === 'native-first-P0');
      const strata = {'historical-first-P0': data.runs.filter(run => run.stratum === 'historical-first-P0'),
                      'declared-fresh1-P0': data.runs.filter(run => run.stratum === 'declared-fresh1-P0')};
      const params = new URL(location.href).searchParams;
      let cohort = Object.hasOwn(strata, params.get('crossCohort')) ? params.get('crossCohort') : 'historical-first-P0';
      let general = strata[cohort].find(row => row.runId === params.get('crossGeneral')) || strata[cohort][0];
      let native = natives.find(row => row.runId === params.get('crossNative')) || natives[0];
      let selectedCase = ids.includes(params.get('crossCase')) ? params.get('crossCase') : ids[0];
      mount.innerHTML = `<div class="section-intro"><p class="eyebrow">Analysis / Joined saved answers</p><h2 id="cross-category-title">Compare the same reviews across model roles.</h2><p>This retrospective P0 view joins 149 general-model configuration passes with seven OpenRouter native decision-model passes on the same 60 fictional comments. Choose saved runs to see where both match the provisional reference, where only one matches, and where an output is unusable. The selected pair is a view of the full declared cohort, not a recommended deployment choice.</p></div>
        <div class="cross-shell"><div class="cross-selectors"><label for="cross-cohort">General cohort<select id="cross-cohort"><option value="historical-first-P0">Historical first P0 · 117 runs</option><option value="declared-fresh1-P0">Declared fresh1/pass1 P0 · 32 runs</option></select></label><label for="cross-general">General run<select id="cross-general"></select></label><label for="cross-native">Native decision run<select id="cross-native">${natives.map(row => `<option value="${esc(row.runId)}">${esc(row.model)}</option>`).join('')}</select></label></div><div id="cross-pair" aria-live="polite"></div>${renderDifficult(data)}</div>
        <p class="cross-method">All rows use the fixed 60-review denominator; the same comments recur across configurations and repeats are separate. Routes, prompts, interfaces, batch patterns and effort differ, so score changes cannot establish a model-family effect. The seven native runs exclude historical Jev, Kev, Laya and direct Cloudflare configurations. Costs exclude human review; client timings are not pure inference time. <a href="${github}results/cross-category-v1/findings.md">Read findings and limitations ↗</a>.</p>`;
      const cohortInput = mount.querySelector('#cross-cohort');
      const generalInput = mount.querySelector('#cross-general');
      const nativeInput = mount.querySelector('#cross-native');
      const pair = mount.querySelector('#cross-pair');
      function update(writeUrl) {
        cohortInput.value = cohort;
        generalInput.innerHTML = strata[cohort].map(row => `<option value="${esc(row.runId)}">${esc(row.model)} · ${esc(row.runId)}</option>`).join('');
        generalInput.value = general.runId;
        nativeInput.value = native.runId;
        pair.innerHTML = renderPair(general, native, data.cases);
        pair.querySelector('#cross-case-detail').innerHTML = renderCase(data, general, native, selectedCase);
        if (writeUrl) {
          const url = new URL(location.href);
          url.searchParams.set('crossCohort', cohort);
          url.searchParams.set('crossGeneral', general.runId);
          url.searchParams.set('crossNative', native.runId);
          url.searchParams.set('crossCase', selectedCase);
          history.replaceState(null, '', url.pathname + url.search + url.hash);
        }
      }
      cohortInput.addEventListener('change', () => {cohort = cohortInput.value; general = strata[cohort][0]; update(true);});
      generalInput.addEventListener('change', () => {general = strata[cohort].find(row => row.runId === generalInput.value); update(true);});
      nativeInput.addEventListener('change', () => {native = natives.find(row => row.runId === nativeInput.value); update(true);});
      pair.addEventListener('click', event => {
        const button = event.target.closest('[data-cross-case]');
        if (!button) return;
        selectedCase = button.dataset.crossCase;
        pair.querySelector('#cross-case-detail').innerHTML = renderCase(data, general, native, selectedCase);
        const reducedMotion = globalThis.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
        pair.querySelector('#cross-case-detail').scrollIntoView({block: 'nearest', behavior: reducedMotion ? 'auto' : 'smooth'});
        const url = new URL(location.href);
        url.searchParams.set('crossCase', selectedCase);
        history.replaceState(null, '', url.pathname + url.search + url.hash);
      });
      update(false);
    } catch (error) {
      mount.innerHTML = '<div class="section-intro"><p class="eyebrow">Analysis / Joined saved answers</p><h2 id="cross-category-title">Comparison unavailable</h2><p>The saved comparison could not be checked here. <a href="./cross-category-v1.json">Open the public data</a>.</p></div>';
      console.error('Cross-category source error:', error);
    }
  }

  globalThis.BenchmarkCrossCategory = Object.freeze({validate, pairTally, fieldSummary,
    renderFields, reviewUrl, renderPair, renderCase, renderDifficult});
  init();
})();
