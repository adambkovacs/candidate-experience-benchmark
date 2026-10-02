/* Presentation taxonomy. Run scores remain in their source-bound feeds. */
(() => {
  'use strict';
  const categories = {
    general: 'General LLM',
    tuned: 'Task-fine-tuned LLM',
    decision: 'Dedicated classification / decision',
    rules: 'Rules baseline',
    unknown: 'Classification pending source'
  };
  const interfaces = {
    generated: 'Generated answer',
    native: 'Native choices / probabilities',
    nli: 'NLI option scoring',
    adapted: 'Fitted decision head',
    rules: 'Rules',
    unknown: 'Interface pending source'
  };
  const evidence = {
    general: 'https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/REPORT_CATEGORY_REVIEW_2026-10-02.md',
    tuned: 'https://huggingface.co/AlexWortega/openjev',
    decision: 'https://typesafe.ai/blog/introducing-system-one-models-and-jev'
  };
  function classify(item) {
    const id = String(item?.configuration || item?.seriesId || item?.id || '').toLowerCase();
    const model = String(item?.model || '').toLowerCase();
    const combined = `${id} ${model} ${String(item?.displayName || '').toLowerCase()}`;
    let category = 'unknown', interfaceKind = 'unknown', source = null;
    if (/\brules-v1\b|\bfixed regex heuristics\b/.test(combined)) {
      category = 'rules'; interfaceKind = 'rules';
    } else if (/alex-openjev|alexwortega\/openjev/.test(combined)) {
      category = 'tuned'; interfaceKind = 'nli'; source = 'https://huggingface.co/AlexWortega/openjev';
    } else if (/\bkev(?:-|\b)|jaredpalmer\/kev/.test(combined)) {
      category = 'decision'; interfaceKind = 'native'; source = 'https://huggingface.co/jaredpalmer/kev-4b';
    } else if (/\blaya|convaiinnovations\/laya/.test(combined)) {
      category = 'decision'; interfaceKind = 'native'; source = 'https://huggingface.co/convaiinnovations/laya';
    } else if (/typesafe.*jev|\bjev-1\.13|\bjev native/.test(combined)) {
      category = 'decision'; interfaceKind = 'native'; source = 'https://typesafe.ai/blog/introducing-system-one-models-and-jev';
    } else if (/\bclef(?:-|\b)/.test(combined)) {
      category = 'decision'; interfaceKind = 'native'; source = 'https://blog.cloudflare.com/clef-decision-models/';
    } else if (/\bopenjev|\bsemif|\banyjev/.test(combined)) {
      category = 'general';
      interfaceKind = /generated/.test(combined) ? 'generated' : /anyjev.*l2/.test(combined) ? 'adapted' : 'native';
      source = /\bopenjev/.test(combined) ? 'https://github.com/razorback16/openjev' : /\bsemif/.test(combined) ? 'https://github.com/TheoLeeCJ/SemIf' : evidence.general;
    } else if (/\bclaude|\bsonnet|\bopus|\bhaiku|\bfable|\bgpt-|\bcodex|\bgemini|\bqwen|\bgemma|\bdiffusiongemma|\bdeepseek|\bmistral/.test(combined)) {
      category = 'general'; interfaceKind = 'generated';
    }
    return {category, categoryLabel: categories[category], interfaceKind,
      interfaceLabel: interfaces[interfaceKind], source};
  }
  globalThis.BenchmarkCategories = Object.freeze({classify, categories, interfaces, evidence});
})();
