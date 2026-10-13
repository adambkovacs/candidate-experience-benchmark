/* Hypothetical reference changes; the frozen key and published scores stay in force. */
(() => {
  'use strict';
  const mount = document.getElementById('reference-sensitivity');
  const sourceRoot = 'https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/';
  const cases = ['DEV-006', 'DEV-013', 'DEV-030'];
  const fields = ['sentiment', 'follow_up_needed', 'serious_concern_reported', 'testimonial_potential'];
  const scenarioIds = ['dev006', 'dev013', 'dev030', 'dev006+dev013', 'dev006+dev030', 'dev013+dev030', 'dev006+dev013+dev030'];
  const sha = value => typeof value === 'string' && /^[a-f0-9]{64}$/.test(value);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, character =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character]));
  const count = value => Number.isInteger(value) && value >= 0 && value <= 60;
  const delta = value => Number.isInteger(value) && value >= -1 && value <= 1;
  const selectedId = selected => selected.map(id => id.toLowerCase().replace('-', '')).join('+');
  const sum = (items, fn) => items.reduce((total, item) => total + fn(item), 0);
  const runDelta = (run, selected, field) => sum(selected, id => run.single_case_deltas[id][field] || 0);
  const allFourDelta = (run, selected) => sum(selected, id => run.single_case_deltas[id].all_four);
  const sign = value => value > 0 ? `+${value}` : String(value);
  // Readable run names come from site/labels.js; the fallback keeps node tests working without it.
  const runName = run => globalThis.BM_LABEL ? globalThis.BM_LABEL.run(run) : String(run.model);
  const passName = pass => String(pass).replace(/^fresh(\d)$/, 'fresh pass $1').replace(/^repeat(\d)$/, 'repeat $1').replace(/^pass(\d)$/, 'pass $1');
  const runLabel = run => `${runName(run)}, ${run.condition}, ${passName(run.repeat_pass)}`;
  // A strong decision-model run opens the panel: Jev 1.13 on TypeSafe, first pass with the plain prompt, 54 of 60.
  const defaultRun = 'extended-typesafe-jev113-native-prompts-fresh1-p0';

  function validate(data) {
    if (data?.schema !== 'reference-sensitivity-public-v1' ||
        data.reference_status !== 'frozen_v0.2_provisional_unchanged' ||
        data.denominator_per_run !== 60 || !sha(data.findings_sha256) ||
        data.findings_path !== 'results/reference-sensitivity-v1/findings.json' ||
        !Array.isArray(data.alternatives) || data.alternatives.length !== 3 ||
        !Array.isArray(data.scenario_summaries) || data.scenario_summaries.length !== 7 ||
        !Array.isArray(data.extended_runs) || data.extended_runs.length !== 637 ||
        !Array.isArray(data.native_seven_runs) || data.native_seven_runs.length !== 7 ||
        !['public-site/extended-cases-v1.json', 'public-site/disputed-reviews-v1.json',
          'data/pilot/reference-revisions/v0.3.json', 'docs/REFERENCE_REVIEW_V1.md',
          'docs/LABELING_GUIDE.md', 'data/pilot/proposed_labels.jsonl']
          .every(path => sha(data.source_sha256?.[path]))) {
      throw Error('Reference sensitivity source header changed');
    }
    const exactAlternatives = [
      ['DEV-006', 'serious_concern_reported', 'insufficient_information', 'no', 'proposed_revision'],
      ['DEV-013', 'sentiment', 'neutral', 'positive', 'needs_human'],
      ['DEV-030', 'sentiment', 'neutral', 'negative', 'needs_human'],
    ];
    if (!data.alternatives.every((row, index) =>
      [row.id, row.field, row.saved, row.alternative, row.decision_status]
        .every((value, position) => value === exactAlternatives[index][position]))) {
      throw Error('Documented alternatives changed');
    }
    const runIds = new Set();
    for (const run of data.extended_runs) {
      if (!/^[a-z0-9.-]+$/.test(run.id || '') || runIds.has(run.id) ||
          typeof run.model !== 'string' || !run.model ||
          !['P0', 'P1', 'P2'].includes(run.condition) ||
          !/^(?:fresh|repeat|pass)[123]$/.test(run.repeat_pass || '') ||
          typeof run.surface !== 'string' || !run.surface ||
          !count(run.valid) || !count(run.saved_all_four) || run.saved_all_four > run.valid ||
          !fields.every(field => count(run.saved_field_scores?.[field]) &&
            run.saved_field_scores[field] <= run.valid) ||
          !run.source_report_url?.startsWith(sourceRoot + 'public-site/') ||
          !sha(run.source_report_sha256)) throw Error('Extended run source or score changed');
      runIds.add(run.id);
      for (const alternative of data.alternatives) {
        const id = alternative.id;
        const effect = run.case_effects?.[id];
        const single = run.single_case_deltas?.[id];
        if (!effect || typeof effect.status !== 'string' || !effect.status ||
            (effect.prediction !== null && typeof effect.prediction !== 'string') ||
            !delta(effect.all_four_delta) || !single || !delta(single.all_four) ||
            !delta(single[alternative.field]) ||
            single.all_four !== effect.all_four_delta ||
            (effect.saved_match !== null && typeof effect.saved_match !== 'boolean') ||
            (effect.hypothetical_match !== null && typeof effect.hypothetical_match !== 'boolean') ||
            ((effect.saved_match === null) !== (effect.hypothetical_match === null)) ||
            (effect.saved_match !== null &&
              single[alternative.field] !== Number(effect.hypothetical_match) - Number(effect.saved_match))) {
          throw Error('Per-case sensitivity changed');
        }
      }
    }
    const nativeIds = new Set();
    for (const run of data.native_seven_runs) {
      if (!/^[a-z0-9-]+$/.test(run.id || '') || nativeIds.has(run.id) ||
          typeof run.display_name !== 'string' || !run.display_name ||
          !count(run.saved_all_four) ||
          !/^results\/[a-zA-Z0-9/_-]+(?:\.[a-zA-Z0-9_-]+)*\.json$/.test(run.source_path || '') ||
          !sha(run.source_sha256) ||
          !cases.every(id => delta(run.single_case_deltas?.[id]))) {
        throw Error('Seven-native run source or score changed');
      }
      nativeIds.add(run.id);
    }
    data.scenario_summaries.forEach((scenario, index) => {
      const expectedCases = cases.filter(id => scenarioIds[index].includes(id.toLowerCase().replace('-', '')));
      if (scenario.id !== scenarioIds[index] ||
          JSON.stringify(scenario.changed_ids) !== JSON.stringify(expectedCases)) {
        throw Error('Sensitivity scenario identity changed');
      }
      for (const [runs, key] of [[data.extended_runs, 'extended_summary'],
                                 [data.native_seven_runs, 'native_seven_summary']]) {
        const totals = {positive: 0, negative: 0, zero: 0};
        for (const run of runs) {
          const value = key === 'extended_summary' ? allFourDelta(run, expectedCases) :
            sum(expectedCases, id => run.single_case_deltas[id]);
          totals[value > 0 ? 'positive' : value < 0 ? 'negative' : 'zero']++;
        }
        const summary = scenario[key];
        if (summary?.run_count !== runs.length ||
            summary.improved_runs !== totals.positive ||
            summary.declined_runs !== totals.negative ||
            summary.unchanged_runs !== totals.zero) {
          throw Error('Sensitivity scenario totals changed');
        }
      }
    });
    return data;
  }

  function reviewUrl(id) {
    const address = new URL(location.href);
    for (const filter of ['reviewSubset', 'reviewModel', 'reviewField', 'reviewSearch']) {
      address.searchParams.delete(filter);
    }
    address.searchParams.set('review', id);
    address.hash = 'review-evidence';
    return address.pathname + address.search + address.hash;
  }

  function runCaseUrl(runId, id) {
    const address = new URL(location.href);
    address.searchParams.set('run', runId);
    address.searchParams.set('case', id);
    address.searchParams.delete('compareRun');
    address.hash = 'inspect';
    return address.pathname + address.search + address.hash;
  }

  function detail(run, selected, alternatives) {
    const allFour = allFourDelta(run, selected);
    const fieldRows = fields.map(field => {
      const change = runDelta(run, selected, field);
      return `<tr><th scope="row">${esc(field.replaceAll('_', ' '))}</th><td>${run.saved_field_scores[field]}/60</td><td>${run.saved_field_scores[field] + change}/60</td><td>${sign(change)}</td></tr>`;
    }).join('');
    const affected = selected.map(id => {
      const alternative = alternatives.find(item => item.id === id);
      const effect = run.case_effects[id];
      const fieldDelta = run.single_case_deltas[id][alternative.field];
      return `<li><a href="${esc(runCaseUrl(run.id, id))}">${id} in this run</a>: ${esc(alternative.field.replaceAll('_', ' '))} ${esc(alternative.saved)} → ${esc(alternative.alternative)}. Saved answer: ${esc(effect.prediction ?? `none (${String(effect.status).replaceAll('_', ' ')})`)}. Decision change ${sign(fieldDelta)}; all-four change ${sign(effect.all_four_delta)}.</li>`;
    }).join('');
    return `<p class="sensitivity-run-name"><strong>${esc(runLabel(run))}</strong><br><code>${esc(run.model)}</code></p>
      <div class="sensitivity-score"><strong>${run.saved_all_four}/60 → ${run.saved_all_four + allFour}/60</strong><span>All four decisions, ${sign(allFour)} under the alternative key, ${run.valid}/60 valid answers</span></div>
      <div class="sensitivity-table-wrap"><table><caption>Published score and score under the alternative key</caption><thead><tr><th scope="col">Decision</th><th scope="col">Published</th><th scope="col">Alternative key</th><th scope="col">Delta</th></tr></thead><tbody>${fieldRows}</tbody></table></div>
      ${selected.length ? `<h4>Affected reviews</h4><ul class="sensitivity-cases">${affected}</ul>` : ''}
      <p class="sensitivity-source"><a href="${esc(run.source_report_url)}" target="_blank" rel="noopener noreferrer">Run report ↗</a></p>`;
  }

  function nativeTable(runs, selected) {
    const rows = runs.map(run => {
      const change = sum(selected, id => run.single_case_deltas[id]);
      return `<tr><th scope="row">${esc(run.display_name)}</th><td>${run.saved_all_four}/60</td><td>${run.saved_all_four + change}/60</td><td>${sign(change)}</td><td><a href="${esc(sourceRoot + run.source_path)}" target="_blank" rel="noopener noreferrer">Source ↗</a></td></tr>`;
    }).join('');
    return `<div class="sensitivity-table-wrap"><table><caption>The seven decision models, first base-prompt pass</caption><thead><tr><th scope="col">Model</th><th scope="col">Published all-four</th><th scope="col">Alternative key</th><th scope="col">Delta</th><th scope="col">Run</th></tr></thead><tbody>${rows}</tbody></table></div>`;
  }

  async function init() {
    if (!mount) return;
    try {
      const response = await fetch('./reference-sensitivity-v1.json', {cache: 'no-store'});
      if (!response.ok) throw Error(`HTTP ${response.status}`);
      const data = validate(await response.json());
      mount.innerHTML = `<div class="section-intro"><h2 id="reference-sensitivity-title">What if three disputed labels changed?</h2><p>Three reference labels are disputed: DEV-006, DEV-013 and DEV-030.</p></div>
        <div class="sensitivity-shell"><fieldset class="sensitivity-controls"><legend>Alternative labels</legend>${data.alternatives.map(item => `<label><input type="checkbox" value="${item.id}"><span><strong>${item.id}</strong>, ${esc(item.field.replaceAll('_', ' '))}: ${esc(item.saved.replaceAll('_', ' '))} → ${esc(item.alternative.replaceAll('_', ' '))} <small>${item.decision_status === 'needs_human' ? 'Open, needs a person to decide' : 'Proposed revision, not adopted'}</small></span></label>`).join('')}</fieldset>
        <p id="sensitivity-status" class="sensitivity-status" role="status" aria-live="polite"></p>
        <div class="sensitivity-columns"><div><h3>One saved run</h3><label for="sensitivity-search">Model or run</label><input id="sensitivity-search" type="search" placeholder="Search 637 runs" autocomplete="off"><label for="sensitivity-run">Saved run</label><select id="sensitivity-run"></select><div id="sensitivity-run-detail" aria-live="polite"></div></div>
        <div><h3>The seven decision models</h3><div id="sensitivity-native"></div></div></div></div>
        <p class="sensitivity-method">Invalid or unsent answers stay misses under every key.</p>`;
      const checks = [...mount.querySelectorAll('input[type="checkbox"]')];
      const search = mount.querySelector('#sensitivity-search');
      const selector = mount.querySelector('#sensitivity-run');
      const status = mount.querySelector('#sensitivity-status');
      const runDetail = mount.querySelector('#sensitivity-run-detail');
      const native = mount.querySelector('#sensitivity-native');
      let selectedRun = (data.extended_runs.find(run => run.id === defaultRun) || data.extended_runs[0]).id;
      function render() {
        const selected = checks.filter(input => input.checked).map(input => input.value);
        const query = search.value.trim().toLowerCase();
        const visible = data.extended_runs.filter(run =>
          `${run.id} ${run.model} ${runLabel(run)} ${run.condition} ${run.repeat_pass} ${run.surface}`.toLowerCase().includes(query));
        if (!visible.some(run => run.id === selectedRun)) selectedRun = visible[0]?.id || '';
        selector.innerHTML = visible.map(run => `<option value="${esc(run.id)}">${esc(runLabel(run))}</option>`).join('');
        selector.disabled = visible.length === 0;
        selector.value = selectedRun;
        const scenario = data.scenario_summaries.find(item => item.id === selectedId(selected));
        status.textContent = selected.length ?
          `Across ${scenario.extended_summary.run_count} saved runs, ${scenario.extended_summary.improved_runs} score higher on all four under this key, ${scenario.extended_summary.declined_runs} lower and ${scenario.extended_summary.unchanged_runs} the same.` :
          '';
        const run = data.extended_runs.find(item => item.id === selectedRun);
        runDetail.innerHTML = run ? detail(run, selected, data.alternatives) : '<p>No run matches this search.</p>';
        native.innerHTML = nativeTable(data.native_seven_runs, selected);
      }
      checks.forEach(input => input.addEventListener('change', render));
      search.addEventListener('input', render);
      selector.addEventListener('change', () => { selectedRun = selector.value; render(); });
      render();
    } catch (error) {
      mount.innerHTML = '<div class="section-intro"><h2 id="reference-sensitivity-title">What if three disputed labels changed?</h2><p>The rescoring data did not load. <a href="./reference-sensitivity-v1.json">Rescoring index (JSON)</a></p></div>';
      console.error('Reference sensitivity source error:', error);
    }
  }

  globalThis.BenchmarkReferenceSensitivity = Object.freeze({validate, selectedId, runDelta, allFourDelta, detail, nativeTable, reviewUrl, runCaseUrl});
  init();
})();
