/* Presentation taxonomy. Run scores remain in their source-bound feeds. */
(() => {
  'use strict';
  const categories = {
    general: 'General-purpose LLM',
    tuned: 'Task-fine-tuned LLM',
    decision: 'Dedicated classification / decision model',
    rules: 'Rules baseline',
    unknown: 'Classification pending source'
  };
  const training = {
    frozen: 'Frozen general-model weights',
    task_finetuned: 'Task-fine-tuned LLM weights',
    fitted_head: 'Trained adapter or decision head',
    rules: 'Rules, no learned model weights',
    unknown: 'Training lineage not verified'
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
    let category = 'unknown', categoriesForRun = ['unknown'];
    let trainingLineage = 'unknown', interfaceKind = 'unknown', source = null, trainingSource = null;
    if (/\brules-v1\b|\bfixed regex heuristics\b/.test(combined)) {
      category = 'rules'; categoriesForRun = ['rules']; trainingLineage = 'rules'; interfaceKind = 'rules';
    } else if (/alex-openjev|alexwortega\/openjev/.test(combined)) {
      category = 'tuned'; categoriesForRun = ['tuned','decision']; trainingLineage = 'task_finetuned';
      interfaceKind = 'nli'; source = 'https://huggingface.co/AlexWortega/openjev'; trainingSource = source;
    } else if (/\bkev(?:-|\b)|jaredpalmer\/kev/.test(combined)) {
      category = 'decision'; categoriesForRun = ['decision']; trainingLineage = 'fitted_head';
      interfaceKind = 'native'; source = 'https://huggingface.co/jaredpalmer/kev-4b'; trainingSource = source;
    } else if (/\blaya|convaiinnovations\/laya/.test(combined)) {
      category = 'decision'; categoriesForRun = ['decision']; interfaceKind = 'native'; source = 'https://huggingface.co/convaiinnovations/laya';
    } else if (/typesafe.*jev|\bjev-1\.13|\bjev native/.test(combined)) {
      category = 'decision'; categoriesForRun = ['decision']; interfaceKind = 'native'; source = 'https://typesafe.ai/blog/introducing-system-one-models-and-jev';
    } else if (/\bclef(?:-|\b)/.test(combined)) {
      category = 'decision'; categoriesForRun = ['decision']; interfaceKind = 'native'; source = 'https://blog.cloudflare.com/clef-decision-models/';
    } else if (/solar-decide|liquid-d1|tev1-4b/.test(combined)) {
      category = 'decision'; categoriesForRun = ['decision']; interfaceKind = 'native';
      source = /solar-decide/.test(combined)
        ? 'https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/solar-decide-first-pass-findings.json'
        : /liquid-d1/.test(combined)
          ? 'https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/liquid-d1-native-full-findings.json'
          : 'https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/tev-native-full-findings.json';
    } else if (/\bopenjev|\bsemif|\banyjev/.test(combined)) {
      category = 'general'; categoriesForRun = ['general'];
      interfaceKind = /generated/.test(combined) ? 'generated' : /anyjev.*l2/.test(combined) ? 'adapted' : 'native';
      source = /\bopenjev/.test(combined) ? 'https://github.com/razorback16/openjev' : /\bsemif/.test(combined) ? 'https://github.com/TheoLeeCJ/SemIf' : evidence.general;
      if (/semif|anyjev.*l0/.test(combined)) {
        trainingLineage = 'frozen';
        trainingSource = /semif/.test(combined) ? source : 'https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/ANYJEV_L0_NATIVE_P0_REPEAT_ADMISSION_2026-09-28.md';
      } else if (/anyjev.*l2/.test(combined)) {
        category = 'decision'; categoriesForRun = ['general','decision']; trainingLineage = 'fitted_head';
        trainingSource = 'https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/ANYJEV_CALIBRATION_NEXT_ADMISSION_2026-09-28.md';
      }
    } else if (/\bclaude|\bsonnet|\bopus|\bhaiku|\bfable|\bgpt-|\bcodex|\bgemini|\bqwen|\bgemma|\bdiffusiongemma|\bdeepseek|\bmistral/.test(combined)) {
      category = 'general'; categoriesForRun = ['general']; interfaceKind = 'generated';
      source = evidence.general;
    }
    const categoryLabels = categoriesForRun.map(value => categories[value]);
    return {category, categories:categoriesForRun, categoryLabel:categoryLabels.join(' + '), categoryLabels,
      trainingLineage, trainingLabel:training[trainingLineage], trainingSource,
      interfaceKind, interfaceLabel:interfaces[interfaceKind], source};
  }
  globalThis.BenchmarkCategories = Object.freeze({classify, categories, training, interfaces, evidence});
})();
