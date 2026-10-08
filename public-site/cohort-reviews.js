/* Source-bound difficult reviews from the selected first-P0 comparison strata. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (root) root.BenchmarkCohortReviews = api;
  if (typeof document !== 'undefined' && document.getElementById('cohort-reviews')) api.init();
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';

  const FIELDS = ['sentiment', 'follow_up_needed', 'serious_concern_reported', 'testimonial_potential'];
  const LABELS = ['Sentiment', 'Follow-up needed', 'Serious concern', 'Testimonial potential'];
  const CHOICES = {
    sentiment: ['positive', 'negative', 'mixed', 'neutral', 'insufficient_information'],
    follow_up_needed: ['yes', 'no', 'insufficient_information'],
    serious_concern_reported: ['yes', 'no', 'insufficient_information'],
    testimonial_potential: ['yes', 'no', 'insufficient_information']
  };
  const GITHUB = 'https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/';
  const STRATA = {decision: 'native-first-P0', fresh: 'declared-fresh1-P0', historical: 'historical-first-P0'};
  const EXPECTED = {'native-first-P0': 7, 'declared-fresh1-P0': 32, 'historical-first-P0': 117};
  const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, character =>
    ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[character]));
  const isHash = value => /^[a-f0-9]{64}$/.test(value || '');
  const isSource = value => typeof value === 'string' && value.startsWith(GITHUB) &&
    !/[?#]/.test(value.slice(GITHUB.length));
  const reviewIds = Array.from({length: 60}, (_, index) => `DEV-${String(index + 1).padStart(3, '0')}`);

  function validate(data) {
    if (data?.schema !== 'cross-category-public-v1' || data.inferenceRequests !== 0 ||
        !Array.isArray(data.cases) || data.cases.length !== 60 ||
        !Array.isArray(data.runs) || data.runs.length !== 156 ||
        data.counts?.native !== 7 || data.counts?.declaredGeneral !== 32 ||
        data.counts?.historicalGeneral !== 117 ||
        !isHash(data.sourceSha256?.['results/cross-category-v1/dataset.json'])) {
      throw Error('Review comparison header changed');
    }
    data.cases.forEach((review, index) => {
      if (review.id !== reviewIds[index] || typeof review.feedback !== 'string' ||
          !review.feedback || FIELDS.some(field => !CHOICES[field].includes(review.reference?.[field]))) {
        throw Error('Review or frozen reference changed');
      }
    });
    const byStratum = {'native-first-P0': 0, 'declared-fresh1-P0': 0, 'historical-first-P0': 0};
    const seen = new Set();
    for (const run of data.runs) {
      if (typeof run.runId !== 'string' || !run.runId || seen.has(run.runId) ||
          !Object.hasOwn(byStratum, run.stratum) || run.controls?.condition !== 'P0' ||
          (run.stratum === STRATA.decision) !== (run.category === 'dedicated-decision') ||
          !isSource(run.sourceUrl) || !isHash(run.sourceSha256) ||
          !Array.isArray(run.cases) || run.cases.length !== 60) {
        throw Error('First-P0 run identity or source changed');
      }
      seen.add(run.runId);
      byStratum[run.stratum]++;
      run.cases.forEach((answer, index) => {
        const reference = data.cases[index].reference;
        const valid = answer.prediction !== null;
        if (answer.id !== reviewIds[index] || typeof answer.status !== 'string' || !answer.status ||
            (answer.status === 'ok') !== valid ||
            answer.allFourMatch !== (valid ? FIELDS.every(field => answer.prediction?.[field] === reference[field]) : null) ||
            (valid ? FIELDS.some(field => !CHOICES[field].includes(answer.prediction?.[field])) ||
              JSON.stringify(answer.differentFields) !== JSON.stringify(FIELDS.filter(field =>
                answer.prediction[field] !== reference[field])) : answer.differentFields !== null)) {
          throw Error('Saved answer or status changed');
        }
      });
    }
    if (Object.keys(EXPECTED).some(stratum => byStratum[stratum] !== EXPECTED[stratum])) {
      throw Error('First-P0 strata changed');
    }
    return data;
  }

  function selectedRuns(data, cohort = 'decision', generalStratum = 'fresh') {
    if (!['decision', 'general', 'all'].includes(cohort) || !['fresh', 'historical'].includes(generalStratum)) {
      throw Error('Unknown review cohort');
    }
    const allowed = cohort === 'decision' ? [STRATA.decision] :
      cohort === 'general' ? [STRATA[generalStratum]] : [STRATA[generalStratum], STRATA.decision];
    return data.runs.filter(run => allowed.includes(run.stratum));
  }

  function summarize(data, cohort = 'decision', generalStratum = 'fresh') {
    const runs = selectedRuns(data, cohort, generalStratum);
    const reviews = data.cases.map((review, index) => {
      const answers = runs.map(run => ({run, answer: run.cases[index]}));
      const disagree = answers.filter(({answer}) => answer.prediction !== null &&
        FIELDS.some(field => answer.prediction[field] !== review.reference[field])).length;
      const unusable = answers.filter(({answer}) => answer.prediction === null).length;
      return {review, answers, disagree, unusable, match: runs.length - disagree - unusable,
        denominator: runs.length, testimonial: review.reference.testimonial_potential === 'yes',
        offTopic: FIELDS.every(field => review.reference[field] === 'insufficient_information')};
    }).sort((a, b) => b.disagree - a.disagree || b.unusable - a.unusable ||
      a.review.id.localeCompare(b.review.id));
    return {runs, reviews, denominator: runs.length, positions: runs.length * data.cases.length,
      disagree: reviews.reduce((sum, row) => sum + row.disagree, 0),
      unusable: reviews.reduce((sum, row) => sum + row.unusable, 0)};
  }

  function filterReviews(summary, {search = '', subset = 'all'} = {}) {
    const query = search.trim().toLocaleLowerCase();
    return summary.reviews.filter(row =>
      (!query || `${row.review.id} ${row.review.feedback}`.toLocaleLowerCase().includes(query)) &&
      (subset === 'all' || subset === 'disagree' && row.disagree > 0 ||
        subset === 'testimonial' && row.testimonial || subset === 'off-topic' && row.offTopic));
  }

  function explorerUrl(runId, reviewId, cohort = 'all', baseUrl) {
    if (!reviewIds.includes(reviewId) || typeof runId !== 'string' || !runId) {
      throw Error('Unknown case link');
    }
    const address = new URL(baseUrl || (typeof location !== 'undefined' ? location.href : 'https://example.invalid/'));
    address.search = '';
    address.searchParams.set('cohort', cohort === 'decision' || cohort === 'general' ? cohort : 'all');
    address.searchParams.set('run', runId);
    address.searchParams.set('case', reviewId);
    address.hash = 'inspect';
    return address.pathname + address.search + address.hash;
  }

  function detailMarkup(row, cohort, baseUrl) {
    const review = row.review;
    const caveat = review.id === 'DEV-006' ? 'A serious-concern reference correction was proposed, but the frozen key remains in use.' :
      ['DEV-013', 'DEV-030'].includes(review.id) ? 'The sentiment reference still needs human adjudication.' :
      row.offTopic ? 'The frozen reference marks this comment off-topic for recruitment.' : '';
    const referenceCells = FIELDS.map(field => `<td><code>${escapeHtml(review.reference[field])}</code></td>`).join('');
    const answerRows = row.answers.map(({run, answer}) => {
      const cells = answer.prediction === null
        ? '<td colspan="4">No usable four-field answer saved for this position.</td>'
        : FIELDS.map(field => `<td${answer.prediction[field] !== review.reference[field] ? ' class="cohort-diff"' : ''}><code>${escapeHtml(answer.prediction[field])}</code></td>`).join('');
      return `<tr><th scope="row">${escapeHtml(run.model)}<small>${escapeHtml(run.runId)}</small><a href="${escapeHtml(explorerUrl(run.runId, review.id, cohort, baseUrl))}">Open this run and review ↗</a><a href="${escapeHtml(run.sourceUrl)}" target="_blank" rel="noopener noreferrer">Saved source ↗</a><small>SHA-256 ${escapeHtml(run.sourceSha256)}</small></th><td><code>${escapeHtml(answer.status)}</code></td>${cells}</tr>`;
    }).join('');
    return `<article class="cohort-review-detail"><p class="eyebrow">${escapeHtml(review.id)} / Frozen development review</p><blockquote>${escapeHtml(review.feedback)}</blockquote><p class="cohort-review-tally"><strong>${row.disagree} / ${row.denominator}</strong> usable answers differ on at least one field · ${row.unusable} / ${row.denominator} unusable or absent · ${row.match} / ${row.denominator} match all four.</p>${caveat ? `<p class="cohort-review-caveat">${escapeHtml(caveat)} <a href="${GITHUB}docs/REFERENCE_REVIEW_V1.md" target="_blank" rel="noopener noreferrer">Read the reference review ↗</a></p>` : ''}<div class="cohort-reference"><p>Frozen proposed reference</p><dl>${FIELDS.map((field,index) => `<div><dt>${LABELS[index]}</dt><dd>${escapeHtml(review.reference[field])}</dd></div>`).join('')}</dl></div><details class="cohort-answer-details"><summary>Read ${row.denominator} exact saved answers and source records</summary><p>A difference is measured against the frozen proposed reference. An unusable position has no fabricated answer.</p><div class="cohort-answer-scroll" tabindex="0"><table><caption>One row per distinct selected first-P0 configuration; each row is this same comment.</caption><thead><tr><th scope="col">Model and source</th><th scope="col">Saved status</th>${LABELS.map(label => `<th scope="col">${label}</th>`).join('')}</tr></thead><tbody><tr class="cohort-reference-row"><th scope="row">Frozen proposed reference</th><td>Reference</td>${referenceCells}</tr>${answerRows}</tbody></table></div></details><p class="cohort-review-source">Original comment and references: <a href="${GITHUB}data/pilot/inputs.jsonl" target="_blank" rel="noopener noreferrer">input records ↗</a> · <a href="${GITHUB}data/pilot/proposed_labels.jsonl" target="_blank" rel="noopener noreferrer">frozen reference records ↗</a>.</p></article>`;
  }

  async function init() {
    const mount = document.getElementById('cohort-reviews');
    if (!mount) return;
    try {
      const response = await fetch('./cross-category-v1.json', {cache: 'no-store'});
      if (!response.ok) throw Error(`HTTP ${response.status}`);
      const data = validate(await response.json());
      const params = new URL(location.href).searchParams;
      const navigation = globalThis.BenchmarkReportNavigation;
      const customCategory = ['tuned', 'rules', 'unknown'].includes(params.get('category'));
      const requestedCohort = params.get('reviewCohort') ||
        (customCategory ? null : navigation?.getCohort?.() || params.get('cohort'));
      let cohort = ['decision', 'general', 'all'].includes(requestedCohort) ? requestedCohort : 'decision';
      let stratum = params.get('reviewGeneralStratum') === 'historical' ? 'historical' : 'fresh';
      let subset = ['all', 'disagree', 'testimonial', 'off-topic'].includes(params.get('reviewCohortSubset'))
        ? params.get('reviewCohortSubset') : 'all';
      let search = (params.get('reviewCohortSearch') || '').slice(0, 200);
      let selected = reviewIds.includes(params.get('reviewCohortCase')) ? params.get('reviewCohortCase') : null;
      mount.innerHTML = `<div class="cohort-reviews-shell"><div class="cohort-reviews-head"><p class="eyebrow">First P0 / the same 60 comments</p><h3 id="cohort-reviews-title">Difficult reviews across selected runs</h3><p>Choose a first-pass cohort. General LLMs use the declared fresh1/pass1 set by default; historical first P0 runs are a separate choice. The combined view adds seven native decision runs to the chosen general set. Other specialist setups and later repeats are outside this panel. <a href="./cross-category-v1.json">Download the saved comparison data ↗</a></p></div><div class="cohort-review-controls"><label><span>Compare</span><select id="cohort-review-cohort"><option value="decision">Decision models · 7</option><option value="general">General LLMs</option><option value="all">Selected general + decision</option></select></label><label><span>General set</span><select id="cohort-review-stratum"><option value="fresh">Declared fresh1/pass1 · 32</option><option value="historical">Historical first P0 · 117</option></select></label><label><span>Find a comment</span><input id="cohort-review-search" type="search" placeholder="Review ID or comment text" autocomplete="off"></label><label><span>Show reviews</span><select id="cohort-review-subset"><option value="all">All 60</option><option value="disagree">At least one difference</option><option value="testimonial">Reference testimonial: yes</option><option value="off-topic">Off-topic under reference</option></select></label></div><p class="cohort-review-count" id="cohort-review-count" role="status" aria-live="polite"></p><div class="cohort-review-body"><div class="cohort-review-list" id="cohort-review-list" role="group" aria-label="Choose a review"></div><div id="cohort-review-selected" aria-live="polite"></div></div><p class="cohort-review-method">Each count uses distinct selected first-P0 configurations as its denominator. The same 60 comments recur in every run. Unusable outcomes are counted separately from answer differences. Routes, prompts and interfaces vary, so these counts do not isolate a model-family effect. <a href="${GITHUB}results/cross-category-v1/findings.md" target="_blank" rel="noopener noreferrer">Read methods and limitations ↗</a></p></div>`;
      const $ = id => mount.querySelector(`#${id}`);
      $('cohort-review-cohort').value = cohort;
      $('cohort-review-stratum').value = stratum;
      $('cohort-review-subset').value = subset;
      $('cohort-review-search').value = search;
      function paint(writeUrl = false) {
        cohort = $('cohort-review-cohort').value;
        stratum = $('cohort-review-stratum').value;
        subset = $('cohort-review-subset').value;
        search = $('cohort-review-search').value;
        $('cohort-review-stratum').disabled = cohort === 'decision';
        const summary = summarize(data, cohort, stratum);
        const rows = filterReviews(summary, {search, subset});
        if (!rows.some(row => row.review.id === selected)) selected = rows[0]?.review.id || null;
        $('cohort-review-count').textContent = `${rows.length} of 60 reviews shown · Across all 60 reviews: ${summary.denominator} distinct first-P0 configurations · ${summary.positions} run-review positions · ${summary.disagree} differ · ${summary.unusable} unusable.`;
        $('cohort-review-list').innerHTML = rows.length ? rows.map(row =>
          `<button type="button" data-review="${row.review.id}" aria-pressed="${row.review.id === selected}"><span class="cohort-review-list-meta"><strong>${row.review.id}</strong><span>${row.disagree} / ${row.denominator} differ</span></span><span class="cohort-review-excerpt">${escapeHtml(row.review.feedback)}</span><small>${row.unusable} unusable · ${row.testimonial ? 'testimonial reference: yes · ' : ''}${row.offTopic ? 'off-topic reference' : 'same 60-comment set'}</small></button>`).join('') : '<p class="cohort-review-empty">No saved reviews match these controls.</p>';
        $('cohort-review-selected').innerHTML = selected ? detailMarkup(rows.find(row => row.review.id === selected), cohort) : '<p class="cohort-review-empty">Change the search or filter to see a review.</p>';
        $('cohort-review-list').querySelectorAll('[data-review]').forEach(button => button.addEventListener('click', () => {
          selected = button.dataset.review;
          paint(true);
          $('cohort-review-list').querySelector(`[data-review="${selected}"]`)?.focus();
        }));
        if (writeUrl) {
          const address = new URL(location.href);
          address.searchParams.set('reviewCohort', cohort);
          address.searchParams.set('reviewGeneralStratum', stratum);
          address.searchParams.set('reviewCohortSubset', subset);
          if (search) address.searchParams.set('reviewCohortSearch', search);
          else address.searchParams.delete('reviewCohortSearch');
          if (selected) address.searchParams.set('reviewCohortCase', selected);
          else address.searchParams.delete('reviewCohortCase');
          history.replaceState(null, '', address.pathname + address.search + address.hash);
        }
      }
      $('cohort-review-cohort').addEventListener('change', () => {
        paint(true);
        navigation?.setCohort?.(cohort);
      });
      for (const id of ['cohort-review-stratum', 'cohort-review-subset'])
        $(id).addEventListener('change', () => paint(true));
      $('cohort-review-search').addEventListener('input', () => paint(true));
      globalThis.addEventListener?.('benchmark:cohortchange', event => {
        // Advanced categories have no matching stratum in this declared comparison.
        const next = event.detail?.cohort;
        if (event.detail?.category || !['decision', 'general', 'all'].includes(next) ||
            $('cohort-review-cohort').value === next) return;
        $('cohort-review-cohort').value = next;
        paint(true);
      });
      paint();
      if (!customCategory && ['decision', 'general', 'all'].includes(params.get('reviewCohort')))
        navigation?.setCohort?.(cohort);
    } catch (error) {
      mount.innerHTML = `<p class="cohort-review-empty">The saved comparison could not be verified. <a href="${GITHUB}results/cross-category-v1/findings.md">Read the source findings ↗</a>.</p>`;
      console.error('Cohort review source error:', error);
    }
  }

  return Object.freeze({validate, selectedRuns, summarize, filterReviews, explorerUrl, detailMarkup, init});
});
