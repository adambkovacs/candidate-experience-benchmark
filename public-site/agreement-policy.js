/* One fixed agreement rule, applied to every pair in the saved seven-model cohort. */
(() => {
  'use strict';
  const mount = document.getElementById('agreement-policy');
  const sourceRoot = 'https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/';
  const ids = Array.from({length: 60}, (_, index) => `DEV-${String(index + 1).padStart(3, '0')}`);
  const fields = ['sentiment', 'follow_up_needed', 'serious_concern_reported', 'testimonial_potential'];
  const esc = value => String(value ?? '').replace(/[&<>"']/g, char =>
    ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[char]));
  const pairKey = pair => `${pair.left}::${pair.right}`;
  const sameIds = (actual, expected) => Array.isArray(actual) &&
    actual.length === expected.length && new Set(actual).size === actual.length &&
    actual.every((id, index) => id === expected[index]);
  const sortedIds = values => [...values].sort();

  function validate(data) {
    if (data?.schema !== 'native-agreement-policy-v1' || data.denominator !== 60 ||
        data.inference_requests !== 0 ||
        data.policy_origin !== 'fixed_before_calculation; all 21 pairs reported without pair selection' ||
        !Array.isArray(data.components) || data.components.length !== 7 ||
        !Array.isArray(data.pairs) || data.pairs.length !== 21 ||
        !/^[a-f0-9]{64}$/.test(data.source_sha256?.['public-site/disputed-reviews-v1.json'] || '')) {
      throw Error('Agreement policy source header changed');
    }
    const models = new Map();
    for (const model of data.components) {
      if (!/^[a-z0-9-]+$/.test(model.id || '') || models.has(model.id) ||
          typeof model.display_name !== 'string' || !model.display_name ||
          !/^results\/[a-zA-Z0-9/_-]+(?:\.[a-zA-Z0-9_-]+)*\.json$/.test(model.source_path || '') ||
          !/^[a-f0-9]{64}$/.test(model.source_sha256 || '') ||
          model.denominator !== 60) throw Error('Agreement model source changed');
      models.set(model.id, model);
    }
    const modelIds = [...models.keys()];
    const expectedPairs = [];
    for (let left = 0; left < modelIds.length; left++) {
      for (let right = left + 1; right < modelIds.length; right++) {
        expectedPairs.push(`${modelIds[left]}::${modelIds[right]}`);
      }
    }
    if (!data.pairs.every((pair, index) => pairKey(pair) === expectedPairs[index])) {
      throw Error('All 21 fixed pairs must appear in source order');
    }
    for (const pair of data.pairs) {
      const accepted = pair.accepted_ids;
      const correct = pair.accepted_all_four_correct_ids;
      const errors = pair.accepted_all_four_error_ids;
      const deferred = pair.deferred_ids;
      if (!Array.isArray(accepted) || !Array.isArray(correct) ||
          !Array.isArray(errors) || !Array.isArray(deferred) ||
          pair.accepted_count !== accepted.length ||
          pair.accepted_all_four_correct !== correct.length ||
          pair.accepted_all_four_error_count !== errors.length ||
          pair.deferred_count !== deferred.length ||
          !sameIds(sortedIds([...accepted, ...deferred]), ids) ||
          !sameIds(sortedIds([...correct, ...errors]), sortedIds(accepted)) ||
          !fields.every(field => Array.isArray(pair.accepted_field_error_ids?.[field]) &&
            pair.accepted_field_error_ids[field].every(id => errors.includes(id))) ||
          (pair.known_two_run_development_cost_usd !== null &&
            !/^\d+(?:\.\d+)?$/.test(pair.known_two_run_development_cost_usd || ''))) {
        throw Error('Agreement pair counts or review IDs changed');
      }
    }
    return data;
  }

  function reviewUrl(id) {
    const address = new URL(location.href);
    for (const key of ['reviewSubset', 'reviewModel', 'reviewField', 'reviewSearch']) {
      address.searchParams.delete(key);
    }
    address.searchParams.set('review', id);
    address.hash = 'review-evidence';
    return address.pathname + address.search + address.hash;
  }

  function idLinks(reviewIds) {
    return reviewIds.length ? reviewIds.map(id =>
      `<a href="${esc(reviewUrl(id))}">${esc(id)}</a>`).join(' ') :
      '<span>None in these 60 reviews.</span>';
  }

  function pairLabel(pair, models) {
    return `${models.get(pair.left).display_name} + ${models.get(pair.right).display_name}`;
  }

  function renderPair(pair, models) {
    const correct = pair.accepted_all_four_correct;
    const errors = pair.accepted_all_four_error_count;
    const deferred = pair.deferred_count;
    const bar = [
      ['correct', correct, 'Accepted, all four match the provisional reference'],
      ['error', errors, 'Accepted, at least one field differs from the provisional reference'],
      ['deferred', deferred, 'Deferred for human review'],
    ].map(([name, count]) => `<span class="agreement-segment agreement-${name}" style="width:${count / 60 * 100}%"></span>`).join('');
    const left = models.get(pair.left);
    const right = models.get(pair.right);
    const source = model => `${sourceRoot}${model.source_path}`;
    const cost = pair.known_two_run_development_cost_usd;
    return `<div class="agreement-pair-head"><p class="eyebrow">Selected pair / source order</p><h3>${esc(pairLabel(pair, models))}</h3></div>
      <div class="agreement-metrics" aria-label="Selected pair outcomes on 60 reviews">
        <p><strong>${pair.accepted_count}<span>/60</span></strong>Accepted</p>
        <p><strong>${correct}</strong>Accepted, all four match</p>
        <p><strong>${errors}</strong>Accepted with an error</p>
        <p><strong>${deferred}</strong>Deferred for review</p>
      </div>
      <div class="agreement-bar" role="img" aria-label="Of 60 reviews: ${correct} accepted and all four match the provisional reference; ${errors} accepted with at least one error; ${deferred} deferred for human review">${bar}</div>
      <p class="agreement-legend"><span class="agreement-key correct"></span>Accepted, reference match <span class="agreement-key error"></span>Accepted error <span class="agreement-key deferred"></span>Deferred</p>
      <div class="agreement-id-grid"><div><h4>Accepted errors <span>${errors}</span></h4><p>Both models gave the same four answers, but at least one differed from the provisional reference.</p><div class="agreement-id-list">${idLinks(pair.accepted_all_four_error_ids)}</div></div>
      <div><h4>Deferred reviews <span>${deferred}</span></h4><p>The two full answer vectors differed. This rule sends those comments to a person.</p><div class="agreement-id-list">${idLinks(pair.deferred_ids)}</div></div></div>
      <p class="agreement-cost">Known charge for both saved 60-review development runs: <strong>${cost === null ? 'unavailable' : `$${esc(cost)}`}</strong>. Both models ran on all 60 comments, including deferred ones. This excludes human review, smoke requests and any invoice difference.</p>
      <p class="agreement-source-links">Saved answers: <a href="${esc(source(left))}" target="_blank" rel="noopener noreferrer">${esc(left.display_name)} ↗</a> · <a href="${esc(source(right))}" target="_blank" rel="noopener noreferrer">${esc(right.display_name)} ↗</a>. <a href="./native-agreement-policy-v1.json">Download all pair outcomes and source hashes</a>.</p>`;
  }

  function renderTable(data, models, selectedKey) {
    return `<div class="agreement-table-wrap"><table><caption>All 21 pairs, in source order. Coverage and errors use the same 60 reviews; lower error counts can reflect more deferrals.</caption>
      <thead><tr><th scope="col">Pair</th><th scope="col">Accepted / 60</th><th scope="col">Accepted reference matches</th><th scope="col">Accepted errors</th><th scope="col">Deferred</th><th scope="col">Known two-run charge</th></tr></thead>
      <tbody>${data.pairs.map(pair => `<tr${pairKey(pair) === selectedKey ? ' class="selected"' : ''}><th scope="row"><button type="button" data-pair="${esc(pairKey(pair))}" aria-current="${pairKey(pair) === selectedKey ? 'true' : 'false'}">${esc(pairLabel(pair, models))}</button></th><td>${pair.accepted_count}</td><td>${pair.accepted_all_four_correct}</td><td>${pair.accepted_all_four_error_count}</td><td>${pair.deferred_count}</td><td>${pair.known_two_run_development_cost_usd === null ? 'Unavailable' : `$${esc(pair.known_two_run_development_cost_usd)}`}</td></tr>`).join('')}</tbody></table></div>`;
  }

  async function init() {
    if (!mount) return;
    try {
      const response = await fetch('./native-agreement-policy-v1.json', {cache: 'no-store'});
      if (!response.ok) throw Error(`HTTP ${response.status}`);
      const data = validate(await response.json());
      const models = new Map(data.components.map(model => [model.id, model]));
      const params = new URL(location.href).searchParams;
      let selected = data.pairs.find(pair => pairKey(pair) === params.get('agreementPair')) || data.pairs[0];
      mount.innerHTML = `<div class="section-intro"><p class="eyebrow">Analysis / Fixed agreement rule</p><h2 id="agreement-policy-title">Two models can agree and still be wrong.</h2><p>Retrospective test on the same 60 fictional comments and seven saved first-pass P0 native decision models. One fixed rule accepts a four-field answer only when both models agree on all four fields. It defers every other comment for human review. The provisional reference scores accepted answers after that choice; it does not decide which answers are accepted.</p></div>
        <div class="agreement-shell"><div class="agreement-controls"><label for="agreement-pair">Inspect a pair</label><select id="agreement-pair">${data.pairs.map(pair => `<option value="${esc(pairKey(pair))}">${esc(pairLabel(pair, models))}</option>`).join('')}</select><p>All 21 pairs are shown below in source order. No pair was selected or tuned as a deployment choice.</p></div><div id="agreement-detail" class="agreement-detail" aria-live="polite"></div><div id="agreement-all-pairs"></div></div>
        <p class="agreement-method">This is a retrospective 60-review study, not a measured deployment gain. The same comment appears in many pairs, and the 21 rows are not independent samples. A match means agreement with the human-checked provisional reference, which still has disputed cases. The rule does not price human review. <a href="./disputed-reviews-v1.json">Read the seven-model source answers</a> · <a href="#method">Read the benchmark method</a>.</p>`;
      const selector = mount.querySelector('#agreement-pair');
      const detail = mount.querySelector('#agreement-detail');
      const table = mount.querySelector('#agreement-all-pairs');
      function choose(pair, updateUrl) {
        selected = pair;
        selector.value = pairKey(pair);
        detail.innerHTML = renderPair(pair, models);
        table.innerHTML = renderTable(data, models, pairKey(pair));
        if (updateUrl) {
          const address = new URL(location.href);
          address.searchParams.set('agreementPair', pairKey(pair));
          history.replaceState(null, '', address.pathname + address.search + address.hash);
        }
      }
      selector.addEventListener('change', () => choose(data.pairs.find(pair => pairKey(pair) === selector.value), true));
      table.addEventListener('click', event => {
        const button = event.target.closest('[data-pair]');
        if (!button) return;
        const pair = data.pairs.find(row => pairKey(row) === button.dataset.pair);
        if (pair) choose(pair, true);
      });
      choose(selected, false);
    } catch (error) {
      mount.innerHTML = '<div class="section-intro"><p class="eyebrow">Analysis / Fixed agreement rule</p><h2 id="agreement-policy-title">Pair study unavailable</h2><p>The saved pair data could not be checked here. <a href="./native-agreement-policy-v1.json">Open the 21-pair findings</a> or <a href="./disputed-reviews-v1.json">read the source answers</a>.</p></div>';
      console.error('Agreement policy source error:', error);
    }
  }

  globalThis.BenchmarkAgreementPolicy = Object.freeze({validate, pairKey, reviewUrl, renderPair, renderTable});
  init();
})();
