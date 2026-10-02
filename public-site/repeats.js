/* Each configuration is one separate 60-record repeat series. */
(() => {
  const root = document.getElementById('repeat-results');
  const modelType = item => globalThis.BenchmarkCategories?.classify(item) || {category:'unknown',categoryLabel:'Classification pending source',interfaceKind:'unknown',interfaceLabel:'Interface pending source'};
  if (!root) return;
  const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const passName = {original:'Pass 1', repeat2:'Pass 2', repeat3:'Pass 3', pass1:'Pass 1', pass2:'Pass 2', pass3:'Pass 3', fresh1:'Fresh pass 1', fresh2:'Fresh pass 2', fresh3:'Fresh pass 3'};
  const conditions = {P0:'Base task', P1:'Classifier instructions', P2:'Instructions and decision tree'};
  const fields = {allFour:'All four decisions', sentiment:'Sentiment', follow_up_needed:'Follow-up needed', serious_concern_reported:'Serious concern', testimonial_potential:'Testimonial potential'};
  const valueOf = (score, field) => field === 'allFour' ? score.allFour : score.fields[field];
  const signed = n => n > 0 ? `+${n}` : String(n);
  const number = n => n == null ? 'Unavailable' : n.toLocaleString('en-US');
  const money = n => n == null || !Number.isFinite(Number(n)) ? 'Unavailable' : '$' + Number(n).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 8});
  const sonnetMissingLabel = item => {
    if (!item || item.status === 'not_started') return 'Not started';
    if (item.status === 'running_or_ambiguous') return 'In progress or outcome unknown; no score';
    if (item.status === 'stopped' || item.status === 'stopped_unknown') return 'Stopped; unscored';
    return `Unscored (${item.status})`;
  };
  const sonnetSavedLabel = item => item?.savedRecords == null ? '' : `; ${item.savedRecords} saved of 60`;

  const hostedV2Ids = {'openrouter-paid-gemma4-26b-a4b-on': 'gemma26-on-fresh-matched3-v2', 'openrouter-paid-qwen3.8-27b-medium': 'qwen27-fresh-matched3-v2-medium', 'openrouter-paid-qwen3.8-27b-xhigh': 'qwen27-fresh-matched3-v2-xhigh'};
  const priceUrl = './subscription-price-estimates.json';
  const optionalPricing = () => {
    const load=Promise.resolve().then(() => fetch(priceUrl))
      .then(response => response.ok ? response.json() : null).catch(() => null);
    if (typeof setTimeout !== 'function') return load;
    let timer;
    const timeout=new Promise(resolve => {timer=setTimeout(() => resolve(null),3000);});
    return Promise.race([load,timeout]).finally(() => clearTimeout(timer));
  };
  const sonnet55Url = './sonnet55-fresh-matched3.json';
  const feedUrls = ['./typesafe-repeats.json', './hosted-v2-repeats.json', './gemma26-continuation-findings.json', './gemma26-second-continuation-findings.json', './kev-native-repeats.json', './repeats.json', './hosted-repeats.json', './claude-repeats.json', './claude-roster-repeats.json', './gemini-repeats.json', './haiku-fresh-matched3.json', './laya-repeats.json', './semif-repeats.json', './semif-generated-repeats.json', './small-local-repeats.json', './legacy-qwen-repeats.json', './e4b-interruption-findings.json', './anyjev-raw-repeats.json', './anyjev-l0-repeats.json', './anyjev-l1-repeats.json', './anyjev-l2-repeats.json', './anyjev-generated-repeats.json', './openjev-native-repeats.json', './openjev-generated-repeats.json', './alex-native-repeats.json', './codex-fresh-repeats.json', './deepseek-fresh-repeats.json', './additional-hosted-fresh-repeats.json', './qwen36-off-second-interruption-findings.json', './qwen27-interrupted-continuation-findings.json', './qwen27-second-continuation-findings.json', './qwen27-final-descriptive-findings.json', './deepseek-low-continuation-repeats.json', './deepseek-low-third-interruption-findings.json', sonnet55Url];
  const sonnet55Series = report => {
    const efforts=['low','medium','high','xhigh'],passes=['pass1','pass2','pass3'],conditions=['P0','P1','P2'];
    if (report?.schema !== 'claude-sonnet55-fresh-matched3-findings-v1' || report.model !== 'claude-sonnet-5-5' || report.plannedCells !== 36 || report.denominatorPerCell !== 60 ||
        JSON.stringify(report.efforts) !== JSON.stringify(efforts) || JSON.stringify(report.passOrder) !== JSON.stringify(passes) || JSON.stringify(report.conditionOrder) !== JSON.stringify(conditions)) return [];
    const closed=(effort,pass,condition) => {
      const dev=report.cells?.[effort]?.[pass]?.[condition]?.development;
      return dev?.state === 'complete' && dev.recordCount === 60 && dev.score?.denominator === 60 && Number.isInteger(dev.score?.valid) && dev.score.valid >= 0 && dev.score.valid <= 60 &&
        dev.score.outcomes?.valid === dev.score.valid && Object.values(dev.score.outcomes).reduce((total,value)=>total+value,0) === 60 &&
        dev.evidence?.records?.path && /^[0-9a-f]{64}$/.test(dev.evidence.records.sha256 || '');
    };
    return efforts.map(effort => {
      const completed=passes.flatMap(pass=>conditions.filter(condition=>closed(effort,pass,condition)).map(condition=>[pass,condition]));
      const missing=passes.flatMap(pass=>conditions.filter(condition=>!closed(effort,pass,condition)).map(condition=>{
        const dev=report.cells?.[effort]?.[pass]?.[condition]?.development || {};
        return {pass,condition,status:dev.state || 'not_started',
          savedRecords:Number.isInteger(dev.recordCount) && dev.recordCount >= 0 ? dev.recordCount : null,
          attemptedRequests:Number.isInteger(dev.requestCount) && dev.requestCount >= 0 ? dev.requestCount :
            Number.isInteger(dev.usage?.startedRequestCount) && dev.usage.startedRequestCount >= 0 ? dev.usage.startedRequestCount : null,
          usage:dev.usage || null};
      }));
      return {schema:'claude-sonnet55-fresh-matched3-series-v1',method:'fresh-matched-three',configuration:`sonnet55-${effort}-fresh-matched3-batch10-v2`,
        displayName:`Claude Sonnet 5.5 · ${effort} effort · fresh matched three`,model:report.model,effort,
        passOrder:passes,conditionOrder:conditions,denominator:60,plannedConditions:9,completedConditions:completed.length,missingPasses:missing,
        passes:Object.fromEntries(passes.map(pass=>[pass,Object.fromEntries(conditions.filter(condition=>closed(effort,pass,condition)).map(condition=>{
          const dev=report.cells[effort][pass][condition].development;
          return [condition,{completionStatus:'complete',score:dev.score,usage:dev.usage,evidence:dev.evidence}];
        }))])),
        threePassSummary:report.threePassSummary?.[effort] || {},
        pairwiseFlips:(report.pairwiseFlips || []).filter(item=>item.effort===effort),
        withinPassPromptDeltas:(report.withinPassPromptDeltas || []).filter(item=>item.effort===effort),
        pairedDeltaSpread:report.pairedDeltaSpread?.[effort] || {},
        interpretation:[`Across four efforts, ${report.completedCells} of 36 planned development phases have complete 60-comment results in this report. This effort has ${completed.length} of 9. Smoke phases and unclosed attempts are not scores.`,...(report.limitations || [])]};
    });
  };
  const e4bInterruptionUrl = './e4b-interruption-findings.json';
  const e4bInterruptionId = 'gemma4-e4b-sdk-thinking-on';
  const gemmaContinuationSchema = 'gemma26-on-v2-interrupted-continuation-findings-v1';
  const gemmaContinuationId = 'gemma26-on-v2-interruption-continuation-v1';
  const qwenContinuationSchema = 'qwen36-off-v2-second-interruption-findings-v1';
  const qwenContinuationId = 'openrouter-paid-qwen36-35b-a3b-off-descriptive-two-interruptions-v1';
  const deepseekLowContinuationSchema = 'deepseek-low-descriptive-interruption-findings-v1';
  const deepseekLowContinuationId = 'openrouter-paid-deepseek-v41-flash-low-descriptive-continuation-v1';
  const qwen27CutoffUrl = './qwen27-interrupted-continuation-findings.json';
  const qwen27CutoffSchema = 'qwen27-v2-interrupted-continuation-findings-v1';
  const qwen27SecondUrl = './qwen27-second-continuation-findings.json';
  const qwen27SecondSchema = 'qwen27-v2-second-continuation-findings-v1';
  const qwen27FinalUrl = './qwen27-final-descriptive-findings.json';
  const qwen27FinalSchema = 'qwen27-v2-final-descriptive-nine-findings-v1';
  const gemmaSecondUrl = './gemma26-second-continuation-findings.json';
  const gemmaSecondSchema = 'gemma26-on-v2-second-interruption-findings-v1';
  const deepseekThirdUrl = './deepseek-low-third-interruption-findings.json';
  const deepseekThirdSchema = 'deepseek-low-third-interruption-findings-v1';
  const validBindings = bindings => Array.isArray(bindings) && bindings.length > 0 &&
    bindings.every(item => typeof item?.path === 'string' && !/private|account|secret|ledger/i.test(item.path) &&
      /^[0-9a-f]{64}$/.test(item?.sha256));
  const idsFrom = start => Array.from({length: 61 - start}, (_, index) =>
    `DEV-${String(start + index).padStart(3, '0')}`);
  const qwenDispatchOrder = [['fresh1','P0'], ['fresh1','P1'], ['fresh1','P2'],
    ['fresh2','P2'], ['fresh2','P0'], ['fresh2','P1'], ['fresh3','P1'], ['fresh3','P2'], ['fresh3','P0']];
  const additionalHostedIds = {
    'openrouter-paid-qwen36-35b-a3b-off': 'openrouter-paid-qwen36-35b-a3b-off-fresh-matched3-v2',
    'openrouter-paid-deepseek-v41-flash-low': 'openrouter-paid-deepseek-v41-flash-low-fresh-matched3-v2'
  };
  Promise.all([...feedUrls.map(url => {
    const load=Promise.resolve().then(() => fetch(url)).then(r => {
    if (!r.ok && (url === './hosted-v2-repeats.json' || url === './gemma26-continuation-findings.json' || url === gemmaSecondUrl || url === './kev-native-repeats.json' || url === './semif-generated-repeats.json' || url === './small-local-repeats.json' || url === './legacy-qwen-repeats.json' || url === e4bInterruptionUrl || url === './anyjev-raw-repeats.json' || url === './anyjev-l0-repeats.json' || url === './anyjev-l1-repeats.json' || url === './anyjev-l2-repeats.json' || url === './anyjev-generated-repeats.json' || url === './openjev-native-repeats.json' || url === './openjev-generated-repeats.json' || url === './alex-native-repeats.json' || url === './codex-fresh-repeats.json' || url === './deepseek-fresh-repeats.json' || url === './additional-hosted-fresh-repeats.json' || url === './qwen36-off-second-interruption-findings.json' || url === qwen27CutoffUrl || url === qwen27SecondUrl || url === qwen27FinalUrl || url === './deepseek-low-continuation-repeats.json' || url === deepseekThirdUrl || url === sonnet55Url) && r.status === 404) return {series: []};
    if (!r.ok) throw Error('Missing repeat results');
    return r.json().then(payload => {
      if (url === sonnet55Url) return {series:sonnet55Series(payload)};
      if (url === './kev-native-repeats.json') {
        if (payload && !payload.schema && Array.isArray(payload.series) && !payload.series.length) return payload;
        const order = ['fresh1', 'fresh2', 'fresh3'];
        const complete = order.filter(p => payload?.passes?.[p]?.completionStatus === 'complete');
        if (payload?.schema !== 'kev-native-repeat-findings-v1' ||
            payload.configuration !== 'kev-openrouter-native-p0' || payload.denominator !== 60 ||
            payload.plannedPasses !== 3 || payload.completedPasses !== complete.length ||
            JSON.stringify(payload.passOrder) !== JSON.stringify(order) ||
            order.some(p => !['complete', 'interrupted', 'running', 'pending'].includes(payload.passes?.[p]?.completionStatus)) ||
            complete.some(p => payload.passes[p].score?.denominator !== 60 || payload.passes[p].score?.valid !== 60))
          throw Error('Invalid Kev native repeat results');
        return {series: [{...payload, plannedConditions: 3, completedConditions: complete.length,
          interpretation: [], kevSource: payload,
          passes: Object.fromEntries(order.map(p => {
            const phase = payload.passes[p];
            const u = phase.usage;
            return [p, {P0: {...phase, usage: phase.completionStatus === 'complete' ? {
              requestCount: 60, tokens: {input_tokens: u.inputTokens, output_tokens: u.outputTokens},
              actualCostUsd: u.actualProviderCostUsd, clientRequestSecondsTotal: u.clientRequestSeconds.total
            } : null}}];
          })),
          pairwiseFlips: Object.entries(payload.repeatComparisons || {}).map(([pair, comparison]) => {
            const [from, to] = pair.split('_to_');
            return {condition: 'P0', from, to, denominator: comparison.denominator,
              fourFieldVector: {changed: comparison.denominator - comparison.recordsWithIdenticalFourFields},
              ...Object.fromEntries(Object.entries(comparison.fieldAgreement).map(([field, count]) =>
                [field, {changed: comparison.denominator - count}]))};
          })}]};
      }
      if (url === './anyjev-l2-repeats.json') {
        if (payload === undefined) return {series: []};
        if (payload && !payload.schema && Array.isArray(payload.series) && payload.series.length === 0) return payload;
        const item = payload?.series?.[0] || (!payload?.series ? payload : null);
        const passOrder = ['original', 'repeat2', 'repeat3'];
        const complete = passOrder.filter(pass => item?.passes?.[pass]?.P0?.completionStatus === 'complete');
        if (payload?.series && (!Array.isArray(payload.series) || payload.series.length !== 1) ||
            item?.schema !== 'anyjev-l2-native-repeat-findings-v1' ||
            item?.configuration !== 'anyjev-qwen06-native-l2-outer-cv5-hf517-adapter-v1' ||
            item?.method !== 'native-output-stability' || item?.denominator !== 60 ||
            item?.plannedConditions !== 3 || item?.completedConditions !== complete.length ||
            JSON.stringify(item?.conditionOrder) !== JSON.stringify(['P0']) ||
            JSON.stringify(item?.passOrder) !== JSON.stringify(passOrder) ||
            !item?.passes || complete.some(pass => item.passes[pass].P0.score?.denominator !== 60) ||
            passOrder.some(pass => item?.passes?.[pass]?.P0 &&
              item.passes[pass].P0.completionStatus !== 'complete'))
          throw Error('Invalid AnyJev L2 repeat results');
      }
      if (url === './openjev-native-repeats.json') {
        if (payload === undefined) return {series: []};
        if (payload && !payload.schema && Array.isArray(payload.series) && payload.series.length === 0) return payload;
        const modes = ['fixed', 'adaptive', 'thinking'];
        const order = ['fresh1', 'fresh2', 'fresh3'];
        if (payload?.schema !== 'openjev-native-fresh-three-report-v1' ||
            !payload.configurations ||
            JSON.stringify(Object.keys(payload.configurations).sort()) !== JSON.stringify(modes.slice().sort()) ||
            modes.some(mode => {
              const item = payload.configurations[mode];
              const completed = Object.keys(item?.freshPasses || {});
              const missing = item?.missingPasses;
              return item?.configuration !== `openjev-${mode}` ||
                item?.historicalObservation?.status !== 'historical_observation_excluded_from_fresh_triplet' ||
                !Array.isArray(missing) || completed.length + missing.length !== 3 ||
                completed.some(pass => !order.includes(pass) ||
                  item.freshPasses[pass]?.completionStatus !== 'complete' ||
                  item.freshPasses[pass]?.score?.denominator !== 60) ||
                missing.some(entry => !order.includes(entry?.pass) || entry?.condition !== 'P0' ||
                  !['not_completed', 'stopped'].includes(entry?.status) || completed.includes(entry.pass)) ||
                new Set([...completed, ...missing.map(entry => entry.pass)]).size !== 3;
            })) throw Error('Invalid OpenJev native repeat results');
        return {series: modes.map(mode => {
          const item = payload.configurations[mode];
          return {schema: payload.schema, configuration: item.configuration,
            seriesId: `${item.configuration}-fresh-native-p0`,
            displayName: `OpenJev ${mode} · fresh native P0`, method: 'native-output-stability',
            passOrder: order, conditionOrder: ['P0'], denominator: 60,
            plannedConditions: 3, completedConditions: Object.keys(item.freshPasses).length,
            passes: Object.fromEntries(order.map(pass => [pass,
              item.freshPasses[pass] ? {P0: item.freshPasses[pass]} : {}])),
            missingPasses: item.missingPasses,
            pairwiseFlips: item.pairwiseFlips.map(flip => ({condition: 'P0', ...flip})),
            threePassSummary: item.threePassSummary,
            changesAcrossThreePasses: item.changesAcrossThreePasses
              ? {P0: item.changesAcrossThreePasses} : {},
            interpretation: payload.limitations};
        })};
      }
      if (url === './openjev-generated-repeats.json') {
        if (payload && !payload.schema && Array.isArray(payload.series) && payload.series.length === 0) return payload;
        const modes = ['generated-off', 'generated-on'];
        const passes = ['fresh1', 'fresh2', 'fresh3'];
        const prompts = ['P0', 'P1', 'P2'];
        const slots = passes.flatMap(pass => prompts.map(condition => `${pass}/${condition}`));
        if (payload?.schema !== 'openjev-generated-fresh-three-report-v2' ||
            !payload.configurations ||
            JSON.stringify(Object.keys(payload.configurations).sort()) !== JSON.stringify(modes.slice().sort()) ||
            modes.some(mode => {
              const item = payload.configurations[mode];
              const completed = passes.flatMap(pass => prompts.filter(condition =>
                item?.freshPasses?.[pass]?.[condition]).map(condition => `${pass}/${condition}`));
              const missing = item?.missingPhases;
              return item?.historicalObservation?.status !== 'historical_observation_excluded_from_fresh_triplet' ||
                !Array.isArray(missing) || !passes.every(pass => item?.freshPasses?.[pass] &&
                  typeof item.freshPasses[pass] === 'object') ||
                completed.some(slot => {
                  const [pass, condition] = slot.split('/');
                  const phase = item.freshPasses[pass][condition];
                  return phase.completionStatus !== 'complete' || phase.score?.denominator !== 60 ||
                    !Number.isInteger(phase.score?.valid) || phase.score.valid < 0 || phase.score.valid > 60;
                }) ||
                missing.some(entry => !slots.includes(`${entry?.pass}/${entry?.condition}`) ||
                  !['not_started', 'claimed_in_progress_or_interrupted', 'smoke_complete_development_pending',
                    'stopped_unknown', 'not_completed'].includes(entry?.status) ||
                  completed.includes(`${entry.pass}/${entry.condition}`)) ||
                completed.length + missing.length !== 9 ||
                new Set([...completed, ...missing.map(entry => `${entry.pass}/${entry.condition}`)]).size !== 9;
            })) throw Error('Invalid OpenJev generated repeat results');
        return {series: modes.map(mode => {
          const item = payload.configurations[mode];
          const passesByName = item.freshPasses;
          const completeCount = passes.reduce((sum, pass) => sum + Object.keys(passesByName[pass]).length, 0);
          const summary = {};
          for (const condition of prompts) {
            if (passes.every(pass => passesByName[pass][condition])) {
              const scores = passes.map(pass => passesByName[pass][condition].score);
              summary[condition] = {allFour: {range: [Math.min(...scores.map(s => s.allFour)),
                Math.max(...scores.map(s => s.allFour))]}, fields: Object.fromEntries(
                Object.keys(fields).filter(field => field !== 'allFour').map(field => [field, {range: [
                  Math.min(...scores.map(s => s.fields[field])), Math.max(...scores.map(s => s.fields[field]))]}]))};
            }
          }
          return {schema: payload.schema, configuration: `openjev-${mode}`,
            seriesId: `openjev-${mode}-fresh-generated-p0p1p2`,
            displayName: `OpenJev ${mode === 'generated-on' ? 'generated requested-on' : 'generated off'} · fresh prompts`,
            method: 'fresh-generated-output-stability', passOrder: passes, conditionOrder: prompts,
            denominator: 60, plannedConditions: 9, completedConditions: completeCount,
            passes: passesByName, missingPasses: item.missingPhases,
            pairwiseFlips: prompts.flatMap(condition => (item.pairwiseFlips?.[condition] || []).map(flip =>
              ({condition, ...flip}))),
            withinPassPromptDeltas: passes.flatMap(pass => (item.withinPassPromptDifferences?.[pass] || []).map(change =>
              ({pass, from: change.from, to: change.to, allFour: change.netScoreDelta.allFour,
                fields: change.netScoreDelta.fields}))),
            withinPassPromptFlips: passes.flatMap(pass => (item.withinPassPromptDifferences?.[pass] || []).map(change =>
              ({pass, from: change.from, to: change.to, denominator: change.denominator,
                excludedIds: change.excludedIds, fourFieldVector: change.fourFieldVector,
                ...Object.fromEntries(Object.keys(fields).filter(field => field !== 'allFour')
                  .map(field => [field, change[field]]))}))),
            threePassSummary: summary, changesAcrossThreePasses: item.changesAcrossThreePasses || {},
            interpretation: payload.limitations};
        })};
      }
      if (url === './semif-generated-repeats.json') {
        if (payload && !payload.schema && Array.isArray(payload.series) && payload.series.length === 0) return payload;
        const item = payload?.series?.[0];
        const passes = ['fresh1', 'fresh2', 'fresh3'];
        const prompts = ['P0', 'P1', 'P2'];
        const slots = passes.flatMap(pass => prompts.map(condition => `${pass}/${condition}`));
        const completed = passes.flatMap(pass => prompts.filter(condition =>
          item?.passes?.[pass]?.[condition]).map(condition => `${pass}/${condition}`));
        const missing = item?.missingPasses;
        const scoreFields = Object.keys(fields).filter(field => field !== 'allFour');
        if (payload?.schema !== 'semif-generated-fresh-repeat-report-v1' ||
            !Array.isArray(payload.series) || payload.series.length !== 1 ||
            item?.schema !== 'semif-generated-fresh-repeat-findings-v1' ||
            item?.configuration !== 'semif-generated-fresh-v1' ||
            item?.method !== 'fresh-native-generated-repeat' ||
            item?.denominator !== 60 || item?.plannedConditions !== 9 ||
            item?.completedConditions !== completed.length ||
            item?.historicalObservationalOnly?.eligibleAsFirstPass !== false ||
            JSON.stringify(item?.passOrder) !== JSON.stringify(passes) ||
            JSON.stringify(item?.conditionOrder) !== JSON.stringify(prompts) ||
            !passes.every(pass => item?.passes?.[pass] && typeof item.passes[pass] === 'object') ||
            !Array.isArray(missing) || completed.length + missing.length !== 9 ||
            new Set([...completed, ...missing.map(entry => `${entry.pass}/${entry.condition}`)]).size !== 9 ||
            missing.some(entry => !slots.includes(`${entry?.pass}/${entry?.condition}`) ||
              !['not_started', 'claimed_in_progress_or_interrupted'].includes(entry?.status)) ||
            completed.some(slot => {
              const [pass, condition] = slot.split('/');
              const phase = item.passes[pass][condition];
              const score = phase.score;
              return phase.completionStatus !== 'complete' || score?.denominator !== 60 ||
                !Number.isInteger(score.valid) || score.valid < 0 || score.valid > 60 ||
                !Number.isInteger(score.allFour) || score.allFour < 0 || score.allFour > score.valid ||
                scoreFields.some(field => !Number.isInteger(score.fields?.[field]) ||
                  score.fields[field] < 0 || score.fields[field] > score.valid) ||
                phase.usage?.requestCount !== 60 || phase.usage?.actualCostUsd !== null;
            })) throw Error('Invalid SemIf generated repeat results');
      }
      if (url === './anyjev-generated-repeats.json') {
        if (payload && !payload.schema && Array.isArray(payload.series) && payload.series.length === 0) return payload;
        const passes = ['fresh1', 'fresh2', 'fresh3'];
        const prompts = ['P0', 'P1', 'P2'];
        const slots = passes.flatMap(pass => prompts.map(condition => `${pass}/${condition}`));
        const completed = passes.flatMap(pass => prompts.filter(condition =>
          payload?.passes?.[pass]?.[condition]).map(condition => `${pass}/${condition}`));
        const missing = payload?.missingPasses;
        const scoreFields = Object.keys(fields).filter(field => field !== 'allFour');
        if (payload?.schema !== 'anyjev-generated-repeat-findings-v1' ||
            payload?.configuration !== 'anyjev-qwen06-generated-fresh-three' ||
            payload?.method !== 'generated-json-control' || payload?.denominator !== 60 ||
            payload?.plannedConditions !== 9 || payload?.completedConditions !== completed.length ||
            payload?.historicalObservation?.eligibleAsFreshPass !== false ||
            JSON.stringify(payload?.passOrder) !== JSON.stringify(passes) ||
            JSON.stringify(payload?.conditionOrder) !== JSON.stringify(prompts) ||
            !passes.every(pass => payload?.passes?.[pass] && typeof payload.passes[pass] === 'object') ||
            !Array.isArray(missing) || !Array.isArray(payload.partialPasses) ||
            completed.length + missing.length !== 9 ||
            new Set([...completed, ...missing.map(entry => `${entry.pass}/${entry.condition}`)]).size !== 9 ||
            missing.some(entry => !slots.includes(`${entry?.pass}/${entry?.condition}`) ||
              !['not_started', 'claimed_in_progress_or_interrupted'].includes(entry?.status)) ||
            completed.some(slot => {
              const [pass, condition] = slot.split('/');
              const phase = payload.passes[pass][condition];
              const score = phase.score;
              const outcomes = score?.outcomes;
              const usage = phase.usage;
              return phase.completionStatus !== 'complete' || score?.denominator !== 60 ||
                !Number.isInteger(score.valid) || score.valid < 0 || score.valid > 60 ||
                !Number.isInteger(score.allFour) || score.allFour < 0 || score.allFour > score.valid ||
                scoreFields.some(field => !Number.isInteger(score.fields?.[field]) ||
                  score.fields[field] < 0 || score.fields[field] > score.valid) ||
                !outcomes || outcomes.valid !== score.valid ||
                Object.values(outcomes).some(value => !Number.isInteger(value) || value < 0) ||
                Object.values(outcomes).reduce((sum, value) => sum + value, 0) !== 60 ||
                !Array.isArray(score.invalidIds) || score.invalidIds.length !== outcomes.invalid_output ||
                usage?.requestCount !== 60 || !Number.isFinite(usage.requestSecondsTotal) ||
                usage.requestSecondsTotal < 0 ||
                !Number.isInteger(usage.tokens?.input_tokens) || usage.tokens.input_tokens < 0 ||
                !Number.isInteger(usage.tokens?.output_tokens) || usage.tokens.output_tokens < 0 ||
                usage.actualCostUsd !== null;
            }) || !Array.isArray(payload.sourceBindings) || !payload.sourceBindings.length ||
            !Array.isArray(payload.limitations))
          throw Error('Invalid AnyJev generated repeat results');
        return {series: [{...payload, interpretation: payload.limitations}]};
      }
      if (url === './hosted-v2-repeats.json' &&
          !(payload && !payload.schema && Array.isArray(payload.series) && payload.series.length === 0) &&
          (payload?.schema !== 'hosted-v2-fresh-repeat-findings-v1' || !Array.isArray(payload.series) ||
           payload.series.some(s => s?.schema !== 'hosted-v2-fresh-repeat-findings-v1' ||
             s.method !== 'fresh-matched-three' || hostedV2Ids[s.configuration] !== s.seriesId ||
             s.denominator !== 60 || s.plannedConditions !== 9) ||
           new Set(payload.series.map(s => s.seriesId)).size !== payload.series.length))
        throw Error('Invalid hosted v2 repeat results');
      if (url === './hosted-v2-repeats.json') return {...payload, series: payload.series.map(s => ({...s, interpretation: s.limitations || []}))};
      if (url === './additional-hosted-fresh-repeats.json' && payload === undefined) return {series: []};
      if (url === './codex-fresh-repeats.json' && (payload?.schema || payload?.series?.length) &&
          (payload?.schema !== 'codex-fresh-repeat-findings-v1' || !Array.isArray(payload.series) ||
           payload.series.some(s => s?.schema !== 'codex-fresh-repeat-findings-v1' || s.method !== 'fresh-matched-three' ||
             s.seriesId !== `${s.configuration}-fresh-matched3`))) throw Error('Invalid Codex fresh repeat results');
      if (url === './deepseek-fresh-repeats.json' && (payload?.schema || payload?.series?.length) &&
          (payload?.schema !== 'deepseek-fresh-repeat-findings-v1' || !Array.isArray(payload.series) ||
           payload.series.some(s => s?.schema !== 'deepseek-fresh-repeat-findings-v1' || s.method !== 'fresh-matched-three' ||
             s.seriesId !== `${s.configuration}-fresh-matched3`))) throw Error('Invalid DeepSeek fresh repeat results');
      if (url === './additional-hosted-fresh-repeats.json' &&
          !(payload && !payload.schema && Array.isArray(payload.series) && payload.series.length === 0) &&
          (payload?.schema !== 'additional-hosted-fresh-repeat-findings-v1' || !Array.isArray(payload.series) ||
           payload.series.some(s => s?.schema !== 'additional-hosted-fresh-repeat-findings-v1' ||
             s.method !== 'fresh-matched-three' || additionalHostedIds[s.configuration] !== s.seriesId) ||
           new Set(payload.series.map(s => s.seriesId)).size !== payload.series.length))
        throw Error('Invalid additional hosted fresh repeat results');
      if (url === './qwen36-off-second-interruption-findings.json') {
        if (payload === undefined) return {series: []};
        if (payload && !payload.schema && Array.isArray(payload.series) && payload.series.length === 0) return {series: []};
        const only = payload?.series?.[0];
        const first = only?.passes?.fresh1?.P0;
        const second = only?.passes?.fresh3?.P1;
        const phases = qwenDispatchOrder.map(([pass, condition]) => only?.passes?.[pass]?.[condition]);
        const expectedBounds = [
          {phase: 'fresh1/P0', id: 'DEV-006', status: 'service_error', upperBoundUsd: '0.0299008'},
          {phase: 'fresh3/P1', id: 'DEV-031', status: 'service_error', upperBoundUsd: '0.0299008'}
        ];
        const flips = [...(only?.pairwiseFlips || []), ...(only?.withinPassPromptFlips || [])];
        if (payload?.schema !== qwenContinuationSchema || !Array.isArray(payload.series) || payload.series.length !== 1 ||
            only?.schema !== qwenContinuationSchema || only?.seriesId !== qwenContinuationId ||
            only?.configuration !== 'openrouter-paid-qwen36-35b-a3b-off' ||
            only?.method !== 'descriptive-continuation-after-two-service-errors' ||
            only?.cleanMatchedThreeEligible !== false || only?.denominator !== 60 ||
            only?.plannedConditions !== 9 || only?.completedConditions !== 9 ||
            JSON.stringify(only?.passOrder) !== JSON.stringify(['fresh1', 'fresh2', 'fresh3']) ||
            JSON.stringify(only?.conditionOrder) !== JSON.stringify(['P0', 'P1', 'P2']) ||
            only?.missingPasses?.length !== 0 || phases.length !== 9 ||
            phases.some((phase, index) => !phase ||
              phase.status !== (index === 0 || index === 6 ? 'closed_with_service_error' : 'completed') ||
              phase.score?.denominator !== 60 ||
              phase.score?.valid !== (index === 0 || index === 6 ? 59 : 60) ||
              phase.score?.outcomes?.ok !== (index === 0 || index === 6 ? 59 : 60) ||
              (phase.score?.outcomes?.service_error || 0) !== (index === 0 || index === 6 ? 1 : 0) ||
              JSON.stringify(phase.score?.invalidIds) !== JSON.stringify(index === 0 ? ['DEV-006'] : index === 6 ? ['DEV-031'] : [])) ||
            first?.usage?.unknownChargeUpperBoundUsd !== '0.0299008' ||
            typeof first?.usage?.knownCostUsd !== 'string' ||
            !Number.isFinite(Number(first.usage.knownCostUsd)) ||
            Number(first.usage.knownCostUsd) < 0 ||
            second?.budgetAccountingCumulative?.oldUnknownChargeUpperBoundUsd !== '0.0598016' ||
            second?.budgetAccountingCumulative?.combinedUnknownChargeUpperBoundUsd !== '0.0598016' ||
            only?.passes?.fresh3?.P0?.budgetAccountingCumulative?.combinedUnknownChargeUpperBoundUsd !== '0.0598016' ||
            !Number.isFinite(Number(only?.passes?.fresh3?.P0?.budgetAccountingCumulative?.combinedKnownAllAttemptCostUsd)) ||
            Number(only.passes.fresh3.P0.budgetAccountingCumulative.combinedKnownAllAttemptCostUsd) < 0 ||
            JSON.stringify(only?.secondInterruption?.oldFailedIds) !== JSON.stringify(['DEV-006', 'DEV-031']) ||
            JSON.stringify(only?.secondInterruption?.retainedOldUnknownBounds) !== JSON.stringify(expectedBounds) ||
            only?.secondInterruption?.oldUnknownChargeUpperBoundUsd !== '0.0598016' ||
            flips.some(flip => !Number.isInteger(flip?.denominator) || flip.denominator < 0 ||
              flip.denominator > 60 || !Array.isArray(flip?.excludedIds) ||
              flip.excludedIds.length !== 60 - flip.denominator ||
              ((flip.pass === 'fresh1' && flip.from === 'P0') ||
               (flip.condition === 'P0' && (flip.from === 'fresh1' || flip.to === 'fresh1')))
                && !flip.excludedIds.includes('DEV-006') ||
              ((flip.pass === 'fresh3' && flip.to === 'P1') ||
               (flip.condition === 'P1' && (flip.from === 'fresh3' || flip.to === 'fresh3')))
                && !flip.excludedIds.includes('DEV-031')))
          throw Error('Invalid Qwen two-interruption continuation results');
      }
      if (url === './deepseek-low-continuation-repeats.json') {
        if (payload === undefined) return {series: []};
        if (payload && !payload.schema && Array.isArray(payload.series) && payload.series.length === 0) return {series: []};
        const only = payload?.series?.[0];
        const first = only?.originalInterruptionCheckpoint;
        const second = only?.secondInterruptionCheckpoint;
        const accounting = only?.budgetAccountingCumulative;
        const moneyValue = value => typeof value === 'string' && /^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(value) && Number.isFinite(Number(value));
        const hash = value => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value);
        const missing = [['fresh1','P2'], ['fresh2','P2'], ['fresh2','P0'], ['fresh2','P1'],
          ['fresh3','P1'], ['fresh3','P2'], ['fresh3','P0']];
        const p0 = only?.passes?.fresh1?.P0;
        const p1 = only?.passes?.fresh1?.P1;
        const snapshot = second?.publicSnapshot;
        if (payload?.schema !== deepseekLowContinuationSchema || !Array.isArray(payload.series) || payload.series.length !== 1 ||
            only?.schema !== deepseekLowContinuationSchema || only?.seriesId !== deepseekLowContinuationId ||
            only?.configuration !== 'openrouter-paid-deepseek-v41-flash-low' ||
            only?.method !== 'descriptive-continuation-after-service-error' ||
            only?.cleanMatchedThreeEligible !== false || only?.denominator !== 60 ||
            only?.plannedConditions !== 9 || only?.completedConditions !== 2 ||
            only?.continuationStatus !== 'suffix_stopped_at_DEV-049_unscored' ||
            JSON.stringify(only?.passOrder) !== JSON.stringify(['fresh1','fresh2','fresh3']) ||
            JSON.stringify(only?.conditionOrder) !== JSON.stringify(['P0','P1','P2']) ||
            JSON.stringify(Object.keys(only?.passes?.fresh1 || {}).sort()) !== JSON.stringify(['P0','P1']) ||
            Object.keys(only?.passes?.fresh2 || {}).length !== 0 || Object.keys(only?.passes?.fresh3 || {}).length !== 0 ||
            !Array.isArray(only?.missingPasses) || only.missingPasses.length !== 7 ||
            only.missingPasses.some((item, index) => item.pass !== missing[index][0] ||
              item.condition !== missing[index][1] ||
              item.status !== (index === 0 ? 'stopped_at_DEV-049_unscored' : 'terminal_public_snapshot_pending')) ||
            p0?.status !== 'completed' || p0?.score?.denominator !== 60 || p0?.score?.valid !== 59 ||
            p0?.score?.outcomes?.ok !== 59 || p0?.score?.outcomes?.invalid_output !== 1 ||
            JSON.stringify(p0?.score?.invalidIds) !== JSON.stringify(['DEV-030']) ||
            p1?.status !== 'completed' || p1?.score?.denominator !== 60 || p1?.score?.valid !== 60 ||
            p1?.score?.outcomes?.ok !== 60 ||
            first?.phase !== 'fresh1/P2' || first?.status !== 'interrupted_at_DEV-040' ||
            first?.attemptedAtInterruption !== 40 || first?.neverSentAtInterruption !== 20 ||
            first?.invalidId !== 'DEV-039' || first?.serviceErrorId !== 'DEV-040' ||
            JSON.stringify(first?.outcomesAtInterruption) !== JSON.stringify({ok:38, invalid_output:1, service_error:1, never_sent:20}) ||
            first?.unknownChargeUpperBoundUsd !== '0.1069056' || !moneyValue(first?.knownAllAttemptCostUsd) ||
            second?.phase !== 'fresh1/P2' || second?.status !== 'terminal_stopped_at_DEV-049' ||
            second?.attemptedAtSecondInterruption !== 49 || second?.neverSentAtSecondInterruption !== 11 ||
            JSON.stringify(second?.invalidIds) !== JSON.stringify(['DEV-039']) ||
            JSON.stringify(second?.serviceErrorIds) !== JSON.stringify(['DEV-040','DEV-049']) ||
            JSON.stringify(second?.outcomes) !== JSON.stringify({ok:46, invalid_output:1, service_error:2, never_sent:11}) ||
            second?.score !== null || second?.newUnknownChargeUpperBoundUsd !== '0.1069056' ||
            !moneyValue(second?.newKnownAllAttemptCostUsd) ||
            second?.sealedChild?.unknown_upper_bound_usd !== '0.1069056' ||
            second?.sealedChild?.known_actual_usd !== second.newKnownAllAttemptCostUsd ||
            !hash(second?.sealedChild?.child_sha256) || !hash(second?.sealedChild?.reconciliation_sha256) ||
            snapshot?.path !== 'results/repeatability-v1/deepseek-low-fresh3-v2/interruption-continuation-v1/phase-03-suffix.public.json' ||
            !hash(snapshot?.sha256) || !Array.isArray(payload.sourceBindings) ||
            !payload.sourceBindings.some(item => item.path === snapshot.path && item.sha256 === snapshot.sha256) ||
            accounting?.oldKnownAllAttemptCostUsd !== first.knownAllAttemptCostUsd ||
            accounting?.oldUnknownChargeUpperBoundUsd !== '0.1069056' ||
            accounting?.newKnownAllAttemptCostUsd !== second.newKnownAllAttemptCostUsd ||
            accounting?.newUnknownChargeUpperBoundUsd !== '0.1069056' ||
            !moneyValue(accounting?.combinedKnownAllAttemptCostUsd) ||
            Number(accounting.combinedKnownAllAttemptCostUsd) !==
              Number(first.knownAllAttemptCostUsd) + Number(second.newKnownAllAttemptCostUsd) ||
            accounting?.combinedUnknownChargeUpperBoundUsd !== '0.2138112')
          throw Error('Invalid DeepSeek-low descriptive continuation results');
      }
      if (url === './gemma26-continuation-findings.json') {
        if (payload === undefined) return {series: []};
        if (payload && !payload.schema && Array.isArray(payload.series) && payload.series.length === 0) return payload;
        const passes = ['fresh1', 'fresh2', 'fresh3'];
        const prompts = ['P0', 'P1', 'P2'];
        const completed = passes.flatMap(pass => prompts.filter(condition =>
          payload?.passes?.[pass]?.[condition]).map(condition => `${pass}/${condition}`));
        const stopped = payload?.stoppedPhases?.[0];
        const missing = payload?.missingPasses;
        const scoreFields = Object.keys(fields).filter(field => field !== 'allFour');
        const moneyValue = value => typeof value === 'string' && /^(?:0|[1-9]\d*)(?:\.\d+)?$/.test(value) &&
          Number.isFinite(Number(value));
        if (payload?.schema !== gemmaContinuationSchema || payload?.seriesId !== gemmaContinuationId ||
            payload?.configuration !== 'openrouter-paid-gemma4-26b-a4b-on' ||
            payload?.method !== 'descriptive-interrupted-series-continuation' ||
            payload?.cleanMatchedThreeEligible !== false || payload?.denominator !== 60 ||
            payload?.plannedConditions !== 9 || payload?.completedConditions !== 5 ||
            JSON.stringify(completed) !== JSON.stringify(['fresh1/P0', 'fresh1/P1', 'fresh1/P2', 'fresh2/P1', 'fresh2/P2']) ||
            !passes.every(pass => payload?.passes?.[pass] && typeof payload.passes[pass] === 'object') ||
            !Array.isArray(missing) || JSON.stringify(missing) !== JSON.stringify([
              {pass: 'fresh2', condition: 'P0', status: 'stopped_unscored'},
              ...prompts.map(condition => ({pass: 'fresh3', condition, status: 'not_completed_in_public_cutoff'}))]) ||
            !Array.isArray(payload.stoppedPhases) || payload.stoppedPhases.length !== 1 ||
            stopped?.pass !== 'fresh2' || stopped?.condition !== 'P0' || stopped?.status !== 'stopped_unscored' ||
            stopped?.score !== null || stopped?.attempted !== 2 || stopped?.validOutputCount !== 1 ||
            stopped?.serviceErrorCount !== 1 || stopped?.failedId !== 'DEV-002' ||
            stopped?.neverSentCount !== 58 || !Array.isArray(stopped?.neverSentIds) ||
            stopped.neverSentIds.length !== 58 || stopped.neverSentIds[0] !== 'DEV-003' ||
            stopped.neverSentIds.at(-1) !== 'DEV-060' ||
            stopped?.usage?.requestCount !== 2 || stopped.usage.actualCostUsd !== null ||
            stopped.usage.unknownCostCount !== 1 ||
            stopped.usage.unknownCostUpperBoundUsd !== '0.01974272' ||
            !moneyValue(stopped.usage.knownCostUsd) ||
            completed.some(slot => {
              const [pass, condition] = slot.split('/');
              const phase = payload.passes[pass][condition];
              const score = phase.score, outcomes = score?.outcomes, usage = phase.usage;
              const interrupted = slot === 'fresh1/P2';
              const valid = interrupted ? 59 : 60;
              return phase.status !== (interrupted ? 'completed_interrupted' : 'completed') ||
                score?.denominator !== 60 || score?.saved !== 60 || score?.valid !== valid ||
                !Number.isInteger(score?.allFour) || score.allFour < 0 || score.allFour > valid ||
                scoreFields.some(field => !Number.isInteger(score.fields?.[field]) ||
                  score.fields[field] < 0 || score.fields[field] > valid) ||
                outcomes?.valid !== valid || outcomes?.service_error !== (interrupted ? 1 : 0) ||
                outcomes?.invalid_output !== 0 || outcomes?.never_sent !== 0 ||
                usage?.requestCount !== 60 || usage?.unknownCostCount !== (interrupted ? 1 : 0) ||
                !moneyValue(usage?.knownCostUsd) ||
                (interrupted ? usage.actualCostUsd !== null ||
                  usage.unknownCostUpperBoundUsd !== '0.01974272' :
                  !moneyValue(usage.actualCostUsd) || usage.unknownCostUpperBoundUsd !== '0');
            }) || !Array.isArray(payload?.sourceBindings) || !payload.sourceBindings.length ||
            payload.sourceBindings.some(item => typeof item?.path !== 'string' ||
              /ledger|private|account|secret/i.test(item.path) ||
              typeof item?.sha256 !== 'string' || !/^[0-9a-f]{64}$/.test(item.sha256)) ||
            !Array.isArray(payload?.limitations))
          throw Error('Invalid Gemma26 interrupted continuation results');
        return {series: [{...payload,
          displayName: 'Gemma 26B thinking-on · interrupted continuation',
          passOrder: passes, conditionOrder: prompts, interpretation: payload.limitations}]};
      }
      if (url === e4bInterruptionUrl) {
        if (payload && !payload.schema && Array.isArray(payload.series) && payload.series.length === 0) return payload;
        const expectedUnknown = ['DEV-039', 'DEV-052'];
        const expectedUnsent = Array.from({length: 8}, (_, index) => `DEV-${String(index + 53).padStart(3, '0')}`);
        const bound = path => payload?.sourceBindings?.some(item => item.path === path && /^[0-9a-f]{64}$/.test(item.sha256));
        const stages = payload?.stages;
        const usage = payload?.usage;
        const host = payload?.hostInterruption;
        if (payload?.schema !== 'e4b-interrupted-descriptive-findings-v1' ||
            payload?.configurationId !== e4bInterruptionId || payload?.phase !== 'fresh2/P2' ||
            payload?.status !== 'stopped_incomplete' || payload?.denominator !== 60 ||
            payload?.savedValid !== 50 || payload?.invalid !== 0 ||
            JSON.stringify(payload.unknownIds) !== JSON.stringify(expectedUnknown) ||
            JSON.stringify(payload.neverSentIds) !== JSON.stringify(expectedUnsent) ||
            payload?.finalScore !== null ||
            payload?.scoreStatus !== 'unavailable_while_planned_requests_remain_unsent' ||
            payload?.seriesStatus !== 'descriptive_interrupted_not_clean_matched_three' ||
            host?.observation !== 'both_timeout_intervals_overlap_recorded_host_sleep' ||
            host?.inferenceTimeConclusion !== 'unavailable' ||
            host?.source?.path !== 'docs/HOST_INTERRUPTION_2026-10-01.md' ||
            host?.source?.sha256 !== payload?.sourceBindings?.find(item => item.path === host.source.path)?.sha256 ||
            !['original', 'suffix'].every(key => ['claim', 'review', 'journal', 'raw', 'records', 'completion', 'routeAudit']
              .every(part => bound(stages?.[key]?.[part]?.path) &&
                stages[key][part].sha256 === payload.sourceBindings.find(item => item.path === stages[key][part].path).sha256)) ||
            !bound('results/repeatability-v1/small-local-v1/gemma4-e4b-sdk-thinking-on/fresh2/P2/development.completion.json') ||
            !bound('results/repeatability-v1/small-local-v1/gemma4-e4b-sdk-thinking-on/interruption-continuation-v1/fresh2/P2/suffix.completion.json') ||
            !Array.isArray(payload?.sourceBindings) || payload.sourceBindings.length !== 40 ||
            payload.sourceBindings.some(item => typeof item?.path !== 'string' ||
              /private|account|secret|ledger/i.test(item.path) ||
              typeof item?.sha256 !== 'string' || !/^[0-9a-f]{64}$/.test(item.sha256)) ||
            usage?.timeBasis !== 'client_observed_wall_clock_for_attempts_only' ||
            !Number.isFinite(usage?.observedClientRequestSeconds) ||
            !Number.isFinite(usage?.savedResponseClientSeconds) ||
            expectedUnknown.some(id => !Number.isFinite(usage?.timeoutClientSeconds?.[id])) ||
            usage?.tokens?.coverage !== '50_saved_responses_only_timeout_usage_unknown' ||
            !Number.isInteger(usage?.tokens?.input) || !Number.isInteger(usage?.tokens?.output) ||
            usage?.actualCostUsd !== null || usage?.modelLoadSeconds !== null)
          throw Error('Invalid E4B interrupted results');
        return {series: [], interruption: payload};
      }
      if (url === qwen27CutoffUrl) {
        if (payload && !payload.schema && Array.isArray(payload.series) && payload.series.length === 0) return payload;
        const medium = payload?.series?.medium;
        const xhigh = payload?.series?.xhigh;
        const valid = (item, mode, failed, validSaved, suffixSaved, unsent, p1Saved, p1Unsent) =>
          item?.configurationId === `openrouter-paid-qwen3.8-27b-${mode}` &&
          item?.freshPass === 'fresh3' && item?.condition === 'P0' &&
          item?.cleanMatchedThreeEligible === false && item?.originalFailedId === failed &&
          item?.validSaved === validSaved && item?.suffixSaved === suffixSaved &&
          JSON.stringify(item?.neverSentAfterContinuation) === JSON.stringify(idsFrom(61 - unsent)) &&
          item?.laterP1?.saved === p1Saved &&
          (mode === 'medium' || item.laterP1.validSaved === p1Saved) &&
          item.laterP1.neverSent === p1Unsent && item.laterP1.score === null &&
          JSON.stringify(item.laterP1.neverSentIds) === JSON.stringify(idsFrom(61 - p1Unsent)) &&
          item?.unknownCostUpperBoundUsd === '0.047001600';
        if (payload?.schema !== qwen27CutoffSchema || payload?.method !== 'descriptive-interrupted-series-continuation' ||
            payload?.denominator !== 60 || payload?.cleanMatchedThreeEligible !== false ||
            !validBindings(payload?.sourceBindings) || payload.sourceBindings.length !== 13 ||
            !valid(medium, 'medium', 'DEV-022', 37, 16, 22, 0, 60) ||
            medium?.status !== 'aborted_suffix_unscored' || medium.score !== null ||
            medium.laterP1.status !== 'not_dispatched' ||
            !valid(xhigh, 'xhigh', 'DEV-037', 59, 23, 0, 8, 52) ||
            xhigh?.status !== 'completed_interrupted_prefix_plus_suffix' ||
            xhigh.score?.denominator !== 60 || xhigh.score.valid !== 59 ||
            xhigh.score.serviceErrors !== 1 || xhigh.score.neverSent !== 0 ||
            xhigh.score.allFour !== 58 || xhigh.laterP1.status !== 'aborted_unscored')
          throw Error('Invalid Qwen27 continuation cutoff');
        return {series: ['medium', 'xhigh'].map(mode => {
          const item = payload.series[mode];
          return {schema: qwen27CutoffSchema, seriesId: `${item.configurationId}-interrupted-cutoff-v1`,
            configuration: item.configurationId,
            displayName: `Qwen 27B ${mode} · interrupted fresh pass 3 cutoff`,
            method: payload.method, cleanMatchedThreeEligible: false, denominator: 60,
            plannedConditions: 2, completedConditions: item.score ? 1 : 0,
            passOrder: ['fresh3'], conditionOrder: ['P0','P1'],
            passes: {fresh3: item.score ? {P0: {status: 'closed_with_service_error', score: item.score}} : {}},
            cutoffDetail: item, sourceBindings: payload.sourceBindings,
            interpretation: []};
        })};
      }
      if (url === qwen27SecondUrl) {
        if (payload && !payload.schema && Array.isArray(payload.series) && payload.series.length === 0) return payload;
        const expected = {medium: {P0: 57, P1: 56}, xhigh: {P0: 58, P1: 58}};
        const validScore = (score, allFour, failures) => score?.denominator === 60 &&
          score?.allFour === allFour && score?.valid === 60 - failures &&
          score?.serviceErrors === failures && score?.invalidOutputs === 0 &&
          score?.neverSent === 0 && Object.keys(fields).filter(key => key !== 'allFour')
            .every(key => Number.isInteger(score?.fields?.[key]) &&
              score.fields[key] >= 0 && score.fields[key] <= score.valid);
        const validMode = mode => {
          const item = payload?.series?.[mode];
          const p0 = item?.conditions?.P0, p1 = item?.conditions?.P1;
          return item?.configurationId === `openrouter-paid-qwen3.8-27b-${mode}` &&
            item?.cleanMatchedThreeEligible === false &&
            item?.originalP0FailedId === (mode === 'medium' ? 'DEV-022' : 'DEV-037') &&
            item?.originalP0UnknownCostUpperBoundUsd === '0.047001600' &&
            item?.secondChildUnknownCostUpperBoundUsd === '0' &&
            p0?.status === 'completed_interrupted_composite' &&
            p1?.status === 'completed_interrupted_composite' &&
            validScore(p0.score, expected[mode].P0, 1) &&
            validScore(p1.score, expected[mode].P1, 0) &&
            p0.usage?.unknownCostCount === 1 && p1.usage?.unknownCostCount === 0 &&
            Number.isFinite(p0.usage?.clientRequestToRecordSeconds) &&
            Number.isFinite(p1.usage?.clientRequestToRecordSeconds);
        };
        if (payload?.schema !== qwen27SecondSchema ||
            payload?.method !== 'descriptive_interrupted_composites' ||
            payload?.denominator !== 60 || payload?.cleanMatchedThreeEligible !== false ||
            !validBindings(payload?.sourceBindings) || payload.sourceBindings.length !== 45 ||
            !payload.sourceBindings.some(item => item.path ===
              'results/repeatability-v1/qwen27-fresh-matched3-v2/interruption-continuation-v2/medium/terminal-reconciliation-after-completion.json') ||
            !payload.sourceBindings.some(item => item.path ===
              'results/repeatability-v1/qwen27-fresh-matched3-v2/interruption-continuation-v2/xhigh/terminal-reconciliation-after-completion.json') ||
            !validMode('medium') || !validMode('xhigh'))
          throw Error('Invalid Qwen27 second continuation results');
        return {series: ['medium', 'xhigh'].map(mode => {
          const item = payload.series[mode];
          return {schema: qwen27SecondSchema,
            seriesId: `${item.configurationId}-interrupted-composite-v2`,
            configuration: item.configurationId,
            displayName: `Qwen 27B ${mode} · completed interrupted pass 3`,
            method: payload.method, cleanMatchedThreeEligible: false,
            denominator: 60, plannedConditions: 2, completedConditions: 2,
            passOrder: ['fresh3'], conditionOrder: ['P0', 'P1'],
            passes: {fresh3: {
              P0: {status: 'closed_with_service_error', score: item.conditions.P0.score},
              P1: {status: 'completed', score: item.conditions.P1.score}}},
            cutoffDetail: item, sourceBindings: payload.sourceBindings,
            interpretation: payload.limits};
        })};
      }
      if (url === qwen27FinalUrl) {
        if (payload && !payload.schema && Array.isArray(payload.series) && payload.series.length === 0) return payload;
        const expected = {medium: {P0: [56, 59, 57], P1: [54, 58, 56], P2: [57, 56, 57]},
          xhigh: {P0: [58, 57, 58], P1: [57, 57, 58], P2: [57, 58, 57]}};
        const modes = ['medium', 'xhigh'];
        const validMode = (item, mode) => item?.configuration === `openrouter-paid-qwen3.8-27b-${mode}` &&
          item?.seriesId === `openrouter-paid-qwen3.8-27b-${mode}-descriptive-nine-v1` &&
          item?.cleanMatchedThreeEligible === false && item?.denominator === 60 &&
          item?.plannedConditions === 9 && item?.scoredConditions === 9 &&
          item?.originalUninterruptedConditions === 7 &&
          JSON.stringify(item?.interruptedCompositeSlots) === JSON.stringify(['fresh3/P0', 'fresh3/P1']) &&
          item?.originalP0FailedId === (mode === 'medium' ? 'DEV-022' : 'DEV-037') &&
          item?.originalP0UnknownCostUpperBoundUsd === '0.047001600' &&
          ['P0', 'P1', 'P2'].every(condition => {
            const values = ['fresh1', 'fresh2', 'fresh3'].map(pass => item?.passes?.[pass]?.[condition]?.score?.allFour);
            const changes = item?.changesAcrossThreePasses?.[condition];
            return JSON.stringify(values) === JSON.stringify(expected[mode][condition]) &&
              JSON.stringify(item?.threePassSummary?.[condition]?.allFour?.values) === JSON.stringify(values) &&
              changes?.denominator === (condition === 'P0' ? 59 : 60) &&
              JSON.stringify(changes?.excludedIds) === JSON.stringify(condition === 'P0' ? [item.originalP0FailedId] : []) &&
              Number.isInteger(changes?.fourFieldVector?.changed) &&
              changes.fourFieldVector.changed === changes.fourFieldVector.caseIds?.length;
          }) &&
          item?.passes?.fresh3?.P0?.status === 'completed_interrupted_composite' &&
          item?.passes?.fresh3?.P1?.status === 'completed_interrupted_composite' &&
          item?.passes?.fresh3?.P0?.score?.valid === 59 &&
          item?.passes?.fresh3?.P0?.score?.serviceErrors === 1 &&
          item?.passes?.fresh3?.P1?.score?.valid === 60 &&
          item?.passes?.fresh3?.P1?.score?.serviceErrors === 0 &&
          item?.pairwiseFlips?.length === 9 && item?.withinPassPromptDeltas?.length === 6 &&
          item?.withinPassPromptFlips?.length === 6;
        if (payload?.schema !== qwen27FinalSchema ||
            payload?.method !== 'descriptive-nine-with-interrupted-composites' ||
            payload?.denominator !== 60 || payload?.cleanMatchedThreeEligible !== false ||
            !validBindings(payload?.sourceBindings) || payload.sourceBindings.length !== 266 ||
            !Array.isArray(payload?.series) || payload.series.length !== 2 ||
            !modes.every((mode, index) => validMode(payload.series[index], mode)))
          throw Error('Invalid Qwen27 nine-phase results');
        return {series: payload.series.map(item => ({...item, schema: qwen27FinalSchema,
          displayName: `Qwen 27B ${item.configuration.endsWith('medium') ? 'medium' : 'xhigh'} · three-pass descriptive comparison`,
          interpretation: [], changesAcrossThreePasses: Object.fromEntries(
            Object.entries(item.changesAcrossThreePasses).map(([condition, changes]) =>
              [condition, {...changes, fourFieldVector: changes.fourFieldVector.caseIds,
                fields: Object.fromEntries(Object.keys(fields).filter(key => key !== 'allFour')
                  .map(key => [key, changes[key].caseIds]))}]))}))};
      }
      if (url === gemmaSecondUrl) {
        if (payload && !payload.schema && Array.isArray(payload.series) && payload.series.length === 0) return payload;
        const composite = payload?.compositeP0;
        const stop = payload?.stageStatus?.find(stage => stage.stage === 'fresh3/P2/development');
        if (payload?.schema !== gemmaSecondSchema ||
            payload?.seriesId !== 'gemma26-on-v2-second-interruption-continuation-v1' ||
            payload?.configuration !== 'openrouter-paid-gemma4-26b-a4b-on' ||
            payload?.method !== 'descriptive-second-interruption-continuation' ||
            payload?.cleanMatchedThreeEligible !== false || payload?.denominator !== 60 ||
            payload?.plannedConditions !== 9 || payload?.priorCompletedConditions !== 5 ||
            payload?.completedConditions !== 6 || payload?.publicCompositeP0Available !== true ||
            composite?.pass !== 'fresh2' || composite?.condition !== 'P0' ||
            composite?.status !== 'completed_composite_interrupted' ||
            composite?.cleanMatchedThreeEligible !== false ||
            composite?.originalFailedId !== 'DEV-002' || composite?.suffixSaved !== 58 ||
            composite?.score?.denominator !== 60 || composite.score.saved !== 60 ||
            composite.score.valid !== 59 || composite.score.allFour !== 56 ||
            JSON.stringify(composite.score.outcomes) !== JSON.stringify({valid:59, invalid_output:0, service_error:1, never_sent:0}) ||
            stop?.status !== 'stopped_unscored' || stop?.stoppedAtId !== 'DEV-005' ||
            stop?.attempted !== 5 || stop?.neverSent !== 55 || stop?.score !== null ||
            JSON.stringify(payload?.laterPassScores) !== JSON.stringify({fresh3:{}}) ||
            !validBindings(payload?.sourceBindings) || payload.sourceBindings.length !== 97)
          throw Error('Invalid Gemma26 second continuation cutoff');
        return {series: [], gemmaSecond: payload};
      }
      if (url === deepseekThirdUrl) {
        if (payload && !payload.schema && Array.isArray(payload.series) && payload.series.length === 0) return payload;
        const only = payload?.series?.[0];
        const checkpoint = only?.thirdInterruptionCheckpoint;
        const missing = only?.missingPasses?.[0];
        if (payload?.schema !== deepseekThirdSchema || !Array.isArray(payload?.series) ||
            payload.series.length !== 1 || only?.schema !== deepseekThirdSchema ||
            only?.seriesId !== 'openrouter-paid-deepseek-v41-flash-low-descriptive-continuation-v2' ||
            only?.configuration !== 'openrouter-paid-deepseek-v41-flash-low' ||
            only?.method !== 'descriptive-continuation-after-service-error' ||
            only?.cleanMatchedThreeEligible !== false || only?.denominator !== 60 ||
            only?.plannedConditions !== 9 || only?.completedConditions !== 2 ||
            only?.continuationStatus !== 'suffix_stopped_at_DEV-050_unscored' ||
            JSON.stringify(Object.keys(only?.passes?.fresh1 || {}).sort()) !== JSON.stringify(['P0','P1']) ||
            checkpoint?.phase !== 'fresh1/P2' || checkpoint?.status !== 'terminal_stopped_at_DEV-050' ||
            checkpoint?.attemptedAtThirdInterruption !== 50 || checkpoint?.neverSentAtThirdInterruption !== 10 ||
            JSON.stringify(checkpoint?.outcomes) !== JSON.stringify({invalid_output:1, never_sent:10, ok:46, service_error:3}) ||
            JSON.stringify(checkpoint?.invalidIds) !== JSON.stringify(['DEV-039']) ||
            JSON.stringify(checkpoint?.serviceErrorIds) !== JSON.stringify(['DEV-040','DEV-049','DEV-050']) ||
            checkpoint?.score !== null || missing?.pass !== 'fresh1' || missing?.condition !== 'P2' ||
            missing?.status !== 'stopped_at_DEV-050_unscored' ||
            only.passes.fresh1.P0?.score?.denominator !== 60 ||
            only.passes.fresh1.P0.score.valid !== 59 ||
            only.passes.fresh1.P1?.score?.denominator !== 60 ||
            only.passes.fresh1.P1.score.valid !== 60 ||
            !validBindings(payload?.sourceBindings) || payload.sourceBindings.length !== 87 ||
            !payload.sourceBindings.some(item => item.path === checkpoint?.publicSnapshot?.path &&
              item.sha256 === checkpoint.publicSnapshot.sha256))
          throw Error('Invalid DeepSeek third interruption cutoff');
        return {series: [{...only,
          displayName: 'DeepSeek low · third interruption at DEV-050'}]};
      }
      return payload;
    });
    }).catch(error => url === sonnet55Url ? {series: []} : Promise.reject(error));
    if (url !== sonnet55Url || typeof setTimeout !== 'function') return load;
    let timer;
    const timeout=new Promise(resolve => {timer=setTimeout(() => resolve({series: []}),3000);});
    return Promise.race([load,timeout]).finally(() => clearTimeout(timer));
  }), optionalPricing()]).then(results => {
    const candidate=results.pop();
    const subscriptionPricing=candidate?.schema === 'subscription-price-estimates-v1' ? candidate : null;
    const payloads=results;
    const e4bInterruption = payloads.find(payload => payload?.interruption)?.interruption || null;
    const loadedSeries = payloads.flatMap(payload => payload?.series || (payload ? [payload] : []));
    const gemmaSecondReport = payloads.find(payload => payload?.gemmaSecond)?.gemmaSecond || null;
    if (gemmaSecondReport) {
      const prior = loadedSeries.find(item => item?.seriesId === gemmaContinuationId);
      if (!prior || prior.completedConditions !== gemmaSecondReport.priorCompletedConditions ||
          prior.passes?.fresh2?.P0 || prior.stoppedPhases?.[0]?.failedId !== 'DEV-002')
        throw Error('Gemma second cutoff lacks its first public cutoff');
      const composite = gemmaSecondReport.compositeP0;
      loadedSeries.push({...prior, schema: gemmaSecondSchema,
        seriesId: gemmaSecondReport.seriesId,
        displayName: 'Gemma 26B thinking-on · second continuation cutoff',
        method: gemmaSecondReport.method,
        completedConditions: gemmaSecondReport.completedConditions,
        passes: {...prior.passes, fresh2: {...prior.passes.fresh2,
          P0: {status: 'completed_interrupted', score: composite.score}}},
        cutoffDetail: gemmaSecondReport,
        sourceBindings: gemmaSecondReport.sourceBindings,
        interpretation: [...prior.limitations,
          'Fresh pass 2 P0 combines the original DEV-001 response, preserved DEV-002 service error, and 58 later saved responses.',
          'Fresh pass 3 P2 stopped after DEV-005. Its 55 remaining comments were not sent, so it has no score.']});
    }
    const hasDeepseekLowContinuation = loadedSeries.some(s => s?.seriesId === deepseekLowContinuationId);
    const series = loadedSeries.filter(s => !(hasDeepseekLowContinuation &&
      s?.schema === 'additional-hosted-fresh-repeat-findings-v1' &&
      s?.configuration === 'openrouter-paid-deepseek-v41-flash-low'));
    if (!series.length) throw Error('No repeat series');
    const subscriptionPrice = (item, pass, condition) => {
      const entry=subscriptionPricing?.repeatPhases?.[`${item.configuration}:${pass}:${condition}`];
      return entry?.model === item.model && entry?.scope === 'repeat_development_phase' ? entry : null;
    };
    const priceSource = entry => /^https:\/\/(platform\.claude\.com|developers\.openai\.com)\//.test(entry?.rate?.sourceUrl || '')
      ? `<a href="${esc(entry.rate.sourceUrl)}" target="_blank" rel="noopener noreferrer">Public rate ↗</a>` : '';
    const isFreshCodex = s => s.schema === 'codex-fresh-repeat-findings-v1' && s.method === 'fresh-matched-three';
    const isFreshSonnet = s => s.schema === 'claude-sonnet55-fresh-matched3-series-v1' && s.method === 'fresh-matched-three';
    const isFreshHosted = s => (s.schema === 'deepseek-fresh-repeat-findings-v1' ||
      s.schema === 'additional-hosted-fresh-repeat-findings-v1' || s.schema === 'hosted-v2-fresh-repeat-findings-v1') && s.method === 'fresh-matched-three';
    const isQwenContinuation = s => s.schema === qwenContinuationSchema &&
      s.method === 'descriptive-continuation-after-two-service-errors';
    const isDeepseekLowContinuation = s => s.schema === deepseekLowContinuationSchema &&
      s.method === 'descriptive-continuation-after-service-error';
    const isGemmaContinuation = s => s.schema === gemmaContinuationSchema &&
      s.method === 'descriptive-interrupted-series-continuation';
    const isQwen27Cutoff = s => s.schema === qwen27CutoffSchema &&
      s.method === 'descriptive-interrupted-series-continuation';
    const isQwen27Second = s => s.schema === qwen27SecondSchema &&
      s.method === 'descriptive_interrupted_composites';
    const isQwen27Final = s => s.schema === qwen27FinalSchema &&
      s.method === 'descriptive-nine-with-interrupted-composites';
    const isGemmaSecond = s => s.schema === gemmaSecondSchema &&
      s.method === 'descriptive-second-interruption-continuation';
    const isDeepseekThird = s => s.schema === deepseekThirdSchema &&
      s.method === 'descriptive-continuation-after-service-error';
    const isNativeOpenJev = s => s.schema === 'openjev-native-fresh-three-report-v1' &&
      s.method === 'native-output-stability';
    const isGeneratedOpenJev = s => s.schema === 'openjev-generated-fresh-three-report-v2' &&
      s.method === 'fresh-generated-output-stability';
    const isGeneratedSemIf = s => s.schema === 'semif-generated-fresh-repeat-findings-v1' &&
      s.method === 'fresh-native-generated-repeat';
    const isGeneratedAnyJev = s => s.schema === 'anyjev-generated-repeat-findings-v1' &&
      s.method === 'generated-json-control';
    const seriesKey = s => isFreshCodex(s) || isFreshHosted(s) || isQwenContinuation(s) || isDeepseekLowContinuation(s) || isGemmaContinuation(s) || isQwen27Cutoff(s) || isQwen27Second(s) || isQwen27Final(s) || isGemmaSecond(s) || isDeepseekThird(s) || isNativeOpenJev(s) || isGeneratedOpenJev(s) ? s.seriesId : s.configuration;
    root.innerHTML = `<div class="filter-grid"><label><span>Find a repeat study</span><input id="repeat-search" type="search" placeholder="Model, route or setting"></label><label><span>Study coverage</span><select id="repeat-coverage"><option value="">All studies</option><option value="complete">All planned runs recorded</option><option value="pending">Runs still missing</option></select></label><label><span>Model category</span><select id="repeat-category"><option value="">All model categories</option>${Object.entries(globalThis.BenchmarkCategories?.categories || {unknown:'Classification pending source'}).map(([key,value])=>`<option value="${esc(key)}">${esc(value)}</option>`).join('')}</select></label><label><span>Output interface</span><select id="repeat-interface"><option value="">All output interfaces</option>${Object.entries(globalThis.BenchmarkCategories?.interfaces || {unknown:'Interface pending source'}).map(([key,value])=>`<option value="${esc(key)}">${esc(value)}</option>`).join('')}</select></label></div><p class="category-explainer">Model category describes what the model was trained to do. Output interface describes how it returns an answer: generated text, direct choices, or scores. A general LLM can also return choice scores. <a href="https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/REPORT_CATEGORY_REVIEW_2026-10-02.md">Read the source mapping</a>.</p><p id="repeat-filter-count" role="status" aria-live="polite"></p><label class="repeat-control">Model and test setup <select id="repeat-config">${series.map(s => `<option value="${esc(seriesKey(s))}">${esc(s.displayName || s.configuration)}${isFreshCodex(s) ? ' · three new passes' : ''}</option>`).join('')}</select></label>
      <div id="repeat-selected-results"><p class="category-selected" id="repeat-category-note"></p><p class="repeat-summary" id="repeat-summary"></p><details class="repeat-usage"><summary>Study details and measurement limits</summary><p class="repeat-lead" id="repeat-lead"></p></details><div id="repeat-interpretation"></div>
      <label class="repeat-control">Compare agreement for <select id="repeat-field">${Object.entries(fields).map(([k,v]) => `<option value="${k}">${v}</option>`).join('')}</select></label>
      <div id="repeat-chart" aria-live="polite"></div>
      <div class="repeat-detail-grid"><div><h3 id="repeat-delta-title">How did prompt scores change across passes?</h3><p id="repeat-delta-intro">Change in matching answers compared with P0 in the same pass. Positive means more matches; negative means fewer.</p><div id="repeat-deltas"></div></div>
      <div><h3>Which answers changed?</h3><label class="repeat-control"><span id="repeat-condition-label">Prompt condition</span> <select id="repeat-condition">${Object.entries(conditions).map(([k,v]) => `<option value="${k}">${k}: ${v}</option>`).join('')}</select></label><div id="repeat-flips" aria-live="polite"></div></div></div>
      <details class="repeat-usage"><summary>Requests, tokens and reported costs</summary><p>Each completed row covers 60 comments. Request counts depend on whether the configuration uses individual comments or batches. Smoke tests are separate. Claude input excludes cache reads and writes; Codex input includes cached tokens. Reasoning tokens are already in output and are not counted twice. Some providers report a charge. API-equivalent estimates use public rates and are not subscription bills. Subscription charge and quota use per run remain unknown. Request durations include client and service overhead.</p><div class="table-wrap"><table><caption>Recorded development usage</caption><thead><tr><th>Condition</th><th>Pass</th><th>Requests</th><th>Input tokens</th><th>Output tokens</th><th>Reported cost (USD)</th><th>Price-based estimate (USD)</th><th>Sum of request seconds</th></tr></thead><tbody id="repeat-usage-body"></tbody></table></div></details></div>`;
    const configControl = document.getElementById('repeat-config');
    const fieldControl = document.getElementById('repeat-field');
    const conditionControl = document.getElementById('repeat-condition');

    function render() {
      const data = series.find(s => seriesKey(s) === configControl.value);
      if (!data) throw Error('Unknown repeat configuration');
      const categoryNote=document.getElementById('repeat-category-note');
      if (categoryNote) {const type=modelType(data);categoryNote.textContent=`${type.categoryLabel} · ${type.interfaceLabel}${type.interfaceKind==='adapted' ? ' · fitted head on general model weights' : ''}`;}
      const freshCodex = isFreshCodex(data);
      const freshSonnet = isFreshSonnet(data);
      const freshHosted = isFreshHosted(data);
      const qwenContinuation = isQwenContinuation(data);
      const deepseekLowContinuation = isDeepseekLowContinuation(data);
      const gemmaContinuation = isGemmaContinuation(data);
      const qwen27Cutoff = isQwen27Cutoff(data);
      const qwen27Second = isQwen27Second(data);
      const qwen27Final = isQwen27Final(data);
      const gemmaSecond = isGemmaSecond(data);
      const deepseekThird = isDeepseekThird(data);
      const nativeOpenJev = isNativeOpenJev(data);
      const generatedOpenJev = isGeneratedOpenJev(data);
      const generatedSemIf = isGeneratedSemIf(data);
      const generatedAnyJev = isGeneratedAnyJev(data);
      const localFresh = data.method === 'fresh-matched-local-output-stability';
      const interruptedE4b = localFresh && data.configuration === e4bInterruptionId ? e4bInterruption : null;
      const passes = data.passOrder || (localFresh ? ['fresh1', 'fresh2', 'fresh3'] : ['original', 'repeat2', 'repeat3']);
      const conditionOrder = data.conditionOrder || ['P0', 'P1', 'P2'];
      const nativeP0 = data.method === 'native-output-stability';
      const nativeL0 = data.schema === 'anyjev-l0-native-repeat-findings-v1';
      const nativeL1 = data.schema === 'anyjev-l1-direct-native-repeat-findings-v1';
      const nativeL2 = data.schema === 'anyjev-l2-native-repeat-findings-v1';
      const nativeKev = data.schema === 'kev-native-repeat-findings-v1';
      const nativeAlex = data.schema === 'alex-native-repeat-findings-v1';
      const displayPass = pass => nativeL2 ? ({original: 'Historical pass', repeat2: 'Repeat 2', repeat3: 'Repeat 3'}[pass] || pass) : passName[pass];
      const closed = phase => gemmaContinuation || gemmaSecond ? phase?.status === 'completed' || phase?.status === 'completed_interrupted'
        : qwenContinuation || deepseekLowContinuation || qwen27Cutoff || qwen27Second || qwen27Final || deepseekThird ? phase?.status === 'completed' || phase?.status === 'closed_with_service_error' || phase?.status === 'completed_interrupted_composite'
        : freshCodex || freshHosted ? phase?.status === 'completed'
        : freshSonnet ? phase?.completionStatus === 'complete'
        : generatedOpenJev || generatedSemIf || generatedAnyJev ? phase?.completionStatus === 'complete'
        : (localFresh || nativeP0) ? phase?.completionStatus === 'complete'
          : Boolean(phase) && phase.completionStatus !== 'partial';
      const freshSeries = freshSonnet || data.schema === 'hosted-v2-fresh-repeat-findings-v1' || data.schema === 'additional-hosted-fresh-repeat-findings-v1' || qwenContinuation || deepseekLowContinuation || gemmaContinuation || qwen27Cutoff || qwen27Second || qwen27Final || gemmaSecond || deepseekThird || nativeOpenJev || generatedOpenJev || generatedSemIf || generatedAnyJev || nativeKev;
      const qwenUnknownFor = (pass, condition) => qwenContinuation
        ? data.secondInterruption.retainedOldUnknownBounds.find(item => item.phase === `${pass}/${condition}`)?.upperBoundUsd
        : null;
      const closedSlot = (pass, condition) => closed(data.passes[pass]?.[condition]);
      const nativeLabel = nativeL0 ? 'Native L0 readout' : nativeL1 ? 'Native L1 calibration' : nativeL2 ? 'Native L2 calibration' : nativeOpenJev ? 'Native OpenJev P0' : nativeKev ? 'Native Choice' : nativeAlex ? 'Native NLI output' : 'Native output';
      document.getElementById('repeat-condition-label').textContent = nativeP0 ? 'Native condition' : 'Prompt condition';
      if (!conditionOrder.includes(conditionControl.value)) conditionControl.value = conditionOrder[0];
      conditionControl.innerHTML = conditionOrder.map(c => `<option value="${esc(c)}"${c === conditionControl.value ? ' selected' : ''}>${c}: ${esc(nativeP0 && c === 'P0' ? nativeLabel : conditions[c] || c)}</option>`).join('');
      const field = fieldControl.value;
      document.getElementById('repeat-interpretation').innerHTML = gemmaContinuation || gemmaSecond
        ? `<details><summary>Why this series has limits</summary>${(data.interpretation || []).map(text => `<p>${esc(text)}</p>`).join('')}</details>`
        : generatedAnyJev
        ? `<details><summary>Protocol and measurement limits</summary><p>This generated JSON control is separate from AnyJev native readouts. The strict parser does not repair fenced JSON. Answer-change comparisons use only comments with answers in the required format in both phases. When none qualify, stability cannot be assessed.</p>${(data.interpretation || []).map(text => `<p>${esc(text)}</p>`).join('')}</details>`
        : (qwenContinuation
        ? '<p class="analysis-caveat"><strong>Descriptive continuation after two service errors:</strong> Fresh pass 1 P0 retains DEV-006 and fresh pass 3 P1 retains DEV-031. Each phase has 59 valid outputs and one HTTP 429 service error among 60 comments. The unsent requests ran later without replaying either failed request. This is not a clean matched-three series. Scores keep all 60 comments; answer-change rates use only comments with answers in the required format in both passes.</p>'
        : deepseekLowContinuation
        ? '<p class="analysis-caveat"><strong>Interrupted descriptive continuation:</strong> Fresh pass 1 P2 stopped at DEV-049 after an earlier stop at DEV-040. DEV-039 was billed but invalid; DEV-040 and DEV-049 were service errors. P2 has no score because 11 of its 60 comments remain unsent. The later passes have not run. This is not a clean matched-three series.</p>'
        : qwen27Cutoff
        ? `<p class="analysis-caveat">This cutoff covers fresh pass 3 only. P0 preserves the original service error at ${esc(data.cutoffDetail.originalFailedId)}; the failed request was not replayed. P1 remains unscored. The earlier hosted matched-run evidence is a separate selectable entry.</p><p><a href="${qwen27CutoffUrl}">Read this public cutoff and its source hashes</a></p>`
        : qwen27Second
        ? `<p class="analysis-caveat">Fresh pass 3 P0 and P1 now have fixed-60 scores. P0 still includes one failed request; the later requests were sent separately. These combined results describe interrupted runs, not two new uninterrupted passes.</p><p><a href="${qwen27SecondUrl}">Read the source-bound results</a> · <a href="https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/QWEN27_V2_SECOND_CONTINUATION_FINDINGS_2026-10-01.md">Read what changed</a></p><details><summary>How these runs were completed</summary><p>The original P0 failure at ${esc(data.cutoffDetail.originalP0FailedId)} was not retried. The P1 result combines separate sends only for xhigh; medium P1 ran as its own full stage. Each original failure retains a ${money(data.cutoffDetail.originalP0UnknownCostUpperBoundUsd)} possible charge, which is not a reported charge. Request times include transport and service overhead.</p></details>`
        : qwen27Final
        ? `<p class="analysis-caveat">The scores compare each 60-comment run with provisional reference labels. Answer-change counts use only comments with valid answers in every compared pass. Fresh pass 3 P0 combined separate sends; xhigh P1 did too. Medium P1 ran as a full stage after the interruption. This is a descriptive comparison, not a clean three-pass test.</p><p><a href="${qwen27FinalUrl}">Read the source-bound results</a> · <a href="https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/QWEN27_V2_FINAL_DESCRIPTIVE_FINDINGS_2026-10-01.md">Read the findings</a></p><details><summary>Why fresh pass 3 was interrupted</summary><p>The original P0 service error at ${esc(data.originalP0FailedId)} was not retried. Later unsent comments were completed separately. Its possible charge is bounded at ${money(data.originalP0UnknownCostUpperBoundUsd)}, which is not an observed charge. Request durations include client and service overhead; provider-reported reasoning tokens are a separate diagnostic.</p></details>`
        : deepseekThird
        ? `<p class="analysis-caveat">Fresh pass 1 P2 stopped at DEV-050. It has 46 valid responses, one invalid response, three service errors and ten comments not sent. No P2 score exists. Earlier interruption cutoffs remain separate entries; this is not a clean matched-three series.</p><p><a href="${deepseekThirdUrl}">Read this public cutoff and its source hashes</a></p>`
        : '') + (data.interpretation || []).map(text => `<p>${esc(text)}</p>`).join('');
      if (gemmaSecond) document.getElementById('repeat-interpretation').innerHTML +=
        `<p><a href="${gemmaSecondUrl}">Read this public cutoff and its source hashes</a></p>`;
      if (freshSonnet) document.getElementById('repeat-interpretation').innerHTML +=
        `<p><a href="${sonnet55Url}">Read the Sonnet 5.5 source report and evidence hashes</a></p>`;
      if (interruptedE4b) {
        const u = interruptedE4b.usage;
        const sourceBase = 'https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/';
        const hostSource = sourceBase + interruptedE4b.hostInterruption.source.path;
        const originalSource = sourceBase + interruptedE4b.stages.original.completion.path;
        const suffixSource = sourceBase + interruptedE4b.stages.suffix.completion.path;
        document.getElementById('repeat-interpretation').innerHTML =
          `<p class="analysis-caveat">Fresh pass 2 P2 stopped: <strong>50 valid saved responses, 2 unknown timeouts, and 8 comments never sent</strong> out of 60. It has no final score and is separate from the clean repeat series.</p>` +
          `<details><summary>What happened to this pass?</summary><p>The original attempt saved DEV-001 to DEV-038, then stopped at DEV-039. A separate continuation saved DEV-040 to DEV-051, then stopped at DEV-052. DEV-053 to DEV-060 were never sent. Neither timed-out request has a known answer.</p>` +
          `<p>Across the 50 saved responses, the SDK reported ${number(u.tokens.input)} input tokens and ${number(u.tokens.output)} output tokens. Token use for the two timeouts is unknown. Client-observed request time totaled ${u.observedClientRequestSeconds.toFixed(1)} seconds across 52 attempts, including the two timeouts. Both timeout intervals overlapped recorded host sleep, so this is not a measure of model inference time. Model-load time and local dollar cost are unavailable.</p>` +
          `<p><a href="${esc(originalSource)}">Original completion</a> · <a href="${esc(suffixSource)}">Continuation completion</a> · <a href="${esc(hostSource)}">Host interruption record</a></p></details>` +
          document.getElementById('repeat-interpretation').innerHTML;
      }
      const generatedAnyJevValidity = generatedAnyJev ? conditionOrder.map(condition =>
        `${condition} ${passes.map(pass => closedSlot(pass, condition)
          ? data.passes[pass][condition].score.valid : 'pending').join(' / ')}`) : [];
      const readerSummary = document.getElementById('repeat-summary');
      if (readerSummary) readerSummary.textContent = gemmaSecond
        ? 'Gemma 26B thinking-on: 6 of 9 phases have final scores at the second continuation cutoff. Fresh pass 2 P0 has a fixed-60 composite score. Fresh pass 3 P2 has 4 valid responses, one service error and 55 unsent comments; it has no score.'
        : qwen27Final
        ? `Qwen 27B ${data.configuration.endsWith('medium') ? 'medium' : 'xhigh'}: all three passes of P0, P1 and P2 have scores. P0 ranges from ${data.threePassSummary.P0.allFour.range.join(' to ')} matches out of 60. Similar scores can hide changed answers; see the comparisons below. Pass 3 followed an interrupted schedule.`
        : qwen27Second
        ? `Qwen 27B ${data.cutoffDetail.configurationId.endsWith('medium') ? 'medium' : 'xhigh'}: fresh pass 3 P0 matched all four reference decisions for ${data.cutoffDetail.conditions.P0.score.allFour} of 60 comments, and P1 for ${data.cutoffDetail.conditions.P1.score.allFour} of 60. P0 has one preserved service error. These are completed interrupted runs; the earlier matched-run results remain separate.`
        : qwen27Cutoff
        ? `Qwen 27B ${data.cutoffDetail.configurationId.endsWith('medium') ? 'medium' : 'xhigh'}: ${data.completedConditions} of 2 fresh pass 3 phases have final scores at this cutoff. P0 has ${data.cutoffDetail.validSaved} valid saved responses and ${data.cutoffDetail.neverSentAfterContinuation.length} unsent comments. P1 has ${data.cutoffDetail.laterP1.saved} saved responses and ${data.cutoffDetail.laterP1.neverSent} unsent comments; it has no score.`
        : deepseekThird
        ? 'DeepSeek low: 2 of 9 phases have final scores at the third interruption cutoff. Fresh pass 1 P2 has 46 valid responses, one invalid response, three service errors and ten unsent comments; it has no score.'
        : gemmaContinuation
        ? `Gemma 26B thinking-on: 5 of 9 phases have final scores. Fresh pass 2 P0 stopped without a score; three later phases were not sent. Scores use all 60 fictional comments, including failed answers.`
        : `${data.completedConditions} of ${data.plannedConditions} planned ${nativeP0 ? 'native P0 passes' : 'prompt-and-pass runs'} have final results for the same ${data.denominator} fictional comments. Finished runs can include failed or unusable answers. ${data.displayName || data.configuration}. Open study details for costs and measurement limits.`;
      if (readerSummary && interruptedE4b) readerSummary.textContent +=
        ' Fresh pass 2 P2 has 50 valid saved responses, two unknown timeouts and eight unsent comments; it has no final score.';
      const seriesPrice=subscriptionPricing?.repeatSeries?.[data.configuration];
      if (readerSummary && seriesPrice && seriesPrice.model === data.model && seriesPrice.fullSeriesEstimateUsd !== null) {
        readerSummary.textContent += ` API-equivalent estimate across ${seriesPrice.totalPhases} phases: ${money(seriesPrice.fullSeriesEstimateUsd)}. Subscription charge and quota use are unknown.`;
      }
      document.getElementById('repeat-lead').textContent = gemmaSecond
        ? 'This is the second Gemma 26B interruption cutoff. Fresh pass 2 P0 combines DEV-001, the preserved DEV-002 service error and a separately dispatched suffix of 58 saved responses. Its fixed-60 score includes the failed request. Fresh pass 3 P2 stopped after DEV-005: four valid, one service error and 55 not sent. That phase has no score. The first cutoff and historical hosted evidence remain separate.'
        : qwen27Final
        ? `Both Qwen 27B effort settings have nine scored prompt-and-pass runs. Scores count all 60 comments, including the service error in fresh pass 3 P0. Changes in individual answers are counted only for comments with valid answers across the compared runs. Fresh pass 3 P0 combines separately sent attempts; xhigh P1 does too, while medium P1 ran as a full stage. Earlier public snapshots remain selectable. This does not establish that prompt wording caused the differences.`
        : qwen27Second
        ? `This entry covers only fresh pass 3 P0 and P1. P0 preserves the original service error at ${data.cutoffDetail.originalP0FailedId}. The other P0 responses and P1 responses fill all planned comment positions across separate dispatches. No failed request was replayed. The earlier clean hosted phases and the first interruption cutoff remain separate. Scores compare with provisional references. Request durations include client and service overhead.`
        : qwen27Cutoff
        ? `Fresh pass 3 P0: ${data.cutoffDetail.validSaved} valid saved responses, one preserved service error at ${data.cutoffDetail.originalFailedId}, and ${data.cutoffDetail.neverSentAfterContinuation.length} not sent. Fresh pass 3 P1: ${data.cutoffDetail.laterP1.saved} saved and ${data.cutoffDetail.laterP1.neverSent} not sent; no score. This is an interrupted cutoff, separate from earlier hosted repeat evidence.`
        : deepseekThird
        ? 'Fresh pass 1 P2 stopped after DEV-050: 46 valid saved responses, one invalid answer at DEV-039, service errors at DEV-040, DEV-049 and DEV-050, and DEV-051 to DEV-060 not sent. It has no score. DEV-050 timing is a client HTTP duration, not pure model inference time. Private provider error bytes cannot be rechecked from the public feed.'
        : gemmaContinuation
        ? 'This is a descriptive interrupted series, separate from the clean Gemma 26B study. Fresh pass 1 P2 combines the original attempts and a separately sent suffix; DEV-007 was not retried. Fresh pass 2 P0 stopped after one valid response and one service error at DEV-002. Its other 58 comments were not sent. The three later phases have no saved requests in this cutoff. The reference labels are provisional. Request time includes transport and service overhead.'
        : generatedAnyJev
        ? `${data.displayName || data.configuration}. ${data.completedConditions} of ${data.plannedConditions} full phases closed; separate from native AnyJev. Valid responses by pass 1/2/3: ${generatedAnyJevValidity.join('; ')}${data.completedConditions < data.plannedConditions ? ' (pending means no full score)' : ''}. Counts and scores use all ${data.denominator} reviews, including invalid outputs.`
        : `${data.displayName || data.configuration}. ${data.completedConditions} of ${data.plannedConditions} planned ${nativeP0 ? 'native P0 passes' : 'prompt/pass combinations'} have complete evidence on the same ${data.denominator} development comments. Incomplete passes are not zero scores.` + Object.entries(data.passes).flatMap(([pass, conditions]) => Object.entries(conditions).filter(([, phase]) => phase.completionStatus === 'partial').map(([condition, phase]) => { const o = phase.score.outcomes; return ` ${condition} ${displayPass(pass)} stopped with ${o.valid} valid responses, ${o.service_error || 0} service errors and ${o.never_sent || 0} reviews not sent.`; })).join('');
      if (localFresh) document.getElementById('repeat-lead').textContent += ` This study plans three fresh local passes. Only completed phases have scores. Earlier local results are observational and are not counted here. Only terminal phases have scores. Reference labels are provisional and were used only for offline scoring. Client request time includes runtime overhead; loaded engine version, model load time and local cost are unknown.`;
      if (freshCodex) document.getElementById('repeat-lead').textContent += ' Each series schedules three fresh Codex subscription passes. Earlier results remain separate and are not pass one. Only closed development phases are scored. The requested model and CLI version are recorded; the served model identity and revision, effective seed and attributable subscription cost are unavailable. Request time includes client overhead.';
      if (freshSonnet) document.getElementById('repeat-lead').textContent += ' This separate Sonnet 5.5 study plans three passes per prompt version. Only closed 60-comment development phases have scores; smoke results and unfinished attempts are excluded. The original low-effort pass 1 P0 guard failure was retained and admitted offline, not replayed. Client request duration includes overhead; pure inference time and actual subscription cost are unavailable.';
      if (freshHosted) document.getElementById('repeat-lead').textContent += ' This series schedules three fresh hosted passes. Earlier results remain separate and are not pass one. Only closed development phases are scored. Costs are provider-reported charges; request durations include network and service overhead, not pure inference time. Smoke usage is separate.';
      if (qwenContinuation) {
        const accounting = qwenDispatchOrder.map(([pass, condition]) => data.passes[pass]?.[condition])
          .filter(phase => closed(phase) && phase.budgetAccountingCumulative).pop()?.budgetAccountingCumulative;
        const known = accounting?.combinedKnownAllAttemptCostUsd;
        const unknown = accounting?.combinedUnknownChargeUpperBoundUsd;
        const bounds = data.secondInterruption.retainedOldUnknownBounds;
        document.getElementById('repeat-lead').textContent += ` Known provider charges through the latest reported phase: ${money(known)}. DEV-006 and DEV-031 each retain a separate unknown-charge upper bound of ${money(bounds[0].upperBoundUsd)}; together they are ${money(unknown)}. These bounds are not invoice charges. Request durations include transport and service overhead, not pure inference time.`;
      }
      if (deepseekLowContinuation) {
        const second = data.secondInterruptionCheckpoint;
        const accounting = data.budgetAccountingCumulative;
        document.getElementById('repeat-lead').textContent += ` Fresh pass 1 P2 has ${second.outcomes.ok} valid, ${second.outcomes.invalid_output} invalid and ${second.outcomes.service_error} service-error outcomes; ${second.outcomes.never_sent} comments were not sent. It is unscored. Known charges across the two children total ${money(accounting.combinedKnownAllAttemptCostUsd)}. DEV-040 and DEV-049 each retain a separate unknown-charge upper bound of ${money(accounting.oldUnknownChargeUpperBoundUsd)}; together they are ${money(accounting.combinedUnknownChargeUpperBoundUsd)}. These bounds are not invoice charges. Public evidence contains hashes and an allowlisted projection; private provider bytes cannot be rechecked here.`;
      }
      if (gemmaContinuation) {
        const first = data.passes.fresh1.P2.usage;
        const stopped = data.stoppedPhases[0].usage;
        document.getElementById('repeat-lead').textContent += ` In fresh pass 1 P2, known provider charges were ${money(first.knownCostUsd)} and one unknown charge is bounded at ${money(first.unknownCostUpperBoundUsd)}. Fresh pass 2 P0 has ${money(stopped.knownCostUsd)} in known charges and a separate unknown bound of ${money(stopped.unknownCostUpperBoundUsd)}. Neither bound is an observed charge.`;
      }
      if (gemmaSecond) document.getElementById('repeat-lead').textContent +=
        ` The suffix saved 58 responses with ${money(data.cutoffDetail.closedStageUsage['fresh2/P0/suffix'].knownCostUsd)} known provider charges. The original DEV-002 unknown charge remains bounded at ${money(data.cutoffDetail.secondInterruption.unknownCostUpperBoundUsd)}; this is not an observed charge. The fresh pass 3 P2 cost cannot be fully reconciled from this public cutoff.`;
      if (qwen27Cutoff) document.getElementById('repeat-lead').textContent +=
        ` Known P0 charges across saved attempts: ${money(data.cutoffDetail.knownObservedDevelopmentCostUsd)}. The preserved service error has a separate unknown-charge upper bound of ${money(data.cutoffDetail.unknownCostUpperBoundUsd)}. It is not an observed charge. Request time includes transport and recording.`;
      if (qwen27Second) document.getElementById('repeat-lead').textContent +=
        ` Known provider charges in the second child were ${money(data.cutoffDetail.secondChildKnownCostUsd)}. The earlier failed P0 request has a separate unknown-charge upper bound of ${money(data.cutoffDetail.originalP0UnknownCostUpperBoundUsd)}. This bound is not observed spending. Provider-reported reasoning tokens are kept separate from completion tokens.`;
      if (qwen27Final) document.getElementById('repeat-lead').textContent +=
        ' The provider reports token use and known charges where available. A missing token count is not zero. Client request-to-record durations include network and service time; they are not model-only inference time.';
      if (nativeL0) document.getElementById('repeat-lead').textContent += ' AnyJev L0 combines cyclic option shifts with a content-free prior. It has one native P0 procedure, not P1/P2 chat prompts. Agreement uses all 60 comments and provisional references; valid output is counted separately. Only completed passes are scored. Client request time includes overhead; pure inference time and local cost are unavailable.';
      if (nativeL1) document.getElementById('repeat-lead').textContent += ' AnyJev L1 fits calibration separately in five folds. Each review is classified with a fit trained on the other 48 reviews; its own reference labels are excluded. Training uses provisional labels, so this is supervised calibration. Historical cached-score results remain separate. Client and pure inference times were not recorded; local cost is unavailable.';
      if (nativeL2) document.getElementById('repeat-lead').textContent += ' AnyJev L2 fits a native decision head on 48 training reviews in each of five folds. Each held-out review is scored once. The historical pass used the staged procedure; repeats add raw capture and completion records. Training uses provisional labels. Client time includes local overhead; isolated inference time, token totals and local cost were not measured.';
      if (nativeOpenJev) {
        document.getElementById('repeat-lead').textContent += ' Fixed, adaptive and thinking are separate native request modes. Historical observations are excluded from these three fresh passes. Only completed development stages have scores. Client HTTP time includes server and transport overhead; local cost and isolated inference time are unavailable. Response token totals appear only when reported.';
        for (const missing of data.missingPasses.filter(item => item.status === 'stopped'))
          document.getElementById('repeat-lead').textContent += ` ${displayPass(missing.pass)} stopped during ${missing.stage} after ${missing.attempted} attempts and ${missing.saved} saved responses. ${missing.unknownStartedIds.length} started requests have unknown outcomes; this pass has no score.`;
      }
      if (generatedOpenJev) {
        document.getElementById('repeat-lead').textContent += ' Generated off and requested-on are separate fresh studies. Earlier generated observations are excluded. Requested-on effective reasoning is not measured. Scores retain invalid responses in the 60-comment denominator. Client HTTP time includes server and transport overhead; local cost and isolated inference time are unavailable.';
        for (const missing of data.missingPasses.filter(item => item.status === 'stopped_unknown'))
          document.getElementById('repeat-lead').textContent += ` ${displayPass(missing.pass)} ${missing.condition} stopped during ${missing.stage}: ${missing.startedIds.length} started, ${missing.savedIds.length} saved, ${missing.unknownStartedIds.length} unknown, ${missing.neverSentIds.length} not sent. This condition has no score.`;
      }
      if (generatedSemIf) document.getElementById('repeat-lead').textContent += ' This local MLX generated series plans three fresh P0/P1/P2 passes. Historical generated outputs and native option-scoring passes are separate. Invalid responses stay in each 60-comment score. Request seconds are summed client-observed elapsed time, not isolated inference time; local cost is unmeasured.';
      if (nativeKev) {
        const interrupted = data.kevSource.passes.fresh3;
        if (interrupted.completionStatus === 'interrupted') {
          const o = interrupted.outcomes;
          document.getElementById('repeat-lead').textContent += ` Third pass: ${o.valid} valid responses, ${o.transportErrorUnknownOutcome} unknown outcome and ${o.neverSent} comments not sent. DEV-026 timed out. This interrupted series is separate from the two complete passes.`;
        }
        document.getElementById('repeat-lead').textContent += ' Native P1 and P2 variants remain pending. Request time includes network and service overhead; pure inference time is unavailable.';
        const first = data.kevSource.passes.fresh1;
        document.getElementById('repeat-interpretation').innerHTML = `<details><summary>Reported confidence: coverage and mistakes</summary><p>First pass only. These confidence values are not calibrated probabilities of correctness. The table counts field decisions meeting a 0.7 threshold; no abstention was performed.</p><div class="table-wrap"><table><caption>First-pass confidence threshold of 0.7</caption><thead><tr><th>Decision</th><th>Covered out of 60</th><th>Matching references</th><th>Mismatches</th></tr></thead><tbody>${Object.entries(first.reportedConfidenceThresholds).map(([key, thresholds]) => {const t=thresholds['0.7'];return `<tr><th scope="row">${esc(fields[key])}</th><td>${t.covered} / 60</td><td>${t.correct}</td><td>${t.wrong}</td></tr>`;}).join('')}</tbody></table></div><p><a href="https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/KEV_NATIVE_FINDINGS_2026-09-30.md">Read the Kev findings and evidence</a></p></details>`;
      }
      if (nativeAlex) document.getElementById('repeat-lead').textContent += ' Alex uses one native NLI procedure. Earlier results are observational and excluded from the fresh-pass comparison. Client prediction time includes local overhead; isolated inference time and local cost are unavailable. Native NLI input positions are not billed API tokens.';
      const validity = Object.entries(data.passes).flatMap(([pass, entries]) => Object.entries(entries).filter(([, phase]) => closed(phase) && phase.score.valid < data.denominator).map(([condition, phase]) => `${condition} ${displayPass(pass)}: ${phase.score.valid}/${data.denominator} valid responses`));
      if (validity.length && !generatedAnyJev) document.getElementById('repeat-lead').textContent += ' Failed or invalid answers remain in the score denominator. ' + validity.join('; ') + '.';
      if (data.historicalContext?.firstPassEligible === false) document.getElementById('repeat-lead').textContent += ' These are three new passes. The earlier run with transport failures remains separate.';
      if (data.method === 'native-choice') document.getElementById('repeat-lead').textContent += ' Jev uses native Choice instruction variants. Pass 1 preserves the original failed request rather than its later successful retry.';
      document.getElementById('repeat-chart').innerHTML = `<div class="repeat-score-grid">${conditionOrder.map(c => {
        const label = nativeP0 && c === 'P0' ? nativeLabel : conditions[c] || c;
        const summary = data.threePassSummary?.[c];
        const completeThree = !freshSeries || passes.every(p => closedSlot(p, c));
        const stats = completeThree ? (field === 'allFour' ? summary?.allFour : summary?.fields?.[field]) : null;
        return `<article><h3>${c} <span>${esc(label)}</span></h3>${passes.map(p => {
          const phase = data.passes[p]?.[c];
          const partial = phase?.completionStatus === 'partial';
          const score = partial || !closed(phase) ? null : phase.score;
          const n = score ? valueOf(score,field) : null;
          const stopped = deepseekLowContinuation && p === 'fresh1' && c === 'P2';
          const thirdStop = deepseekThird && p === 'fresh1' && c === 'P2';
          const qwen27P0Stop = qwen27Cutoff && c === 'P0' && !data.cutoffDetail.score;
          const qwen27P1Stop = qwen27Cutoff && c === 'P1';
          const gemmaStop = gemmaContinuation && p === 'fresh2' && c === 'P0';
          const gemmaSecondStop = gemmaSecond && p === 'fresh3' && c === 'P2';
          const gemmaUnsent = (gemmaContinuation && p === 'fresh3') ||
            (gemmaSecond && p === 'fresh3' && c !== 'P2');
          const e4bStop = interruptedE4b && p === 'fresh2' && c === 'P2';
          const kevStop = nativeKev && phase?.completionStatus === 'interrupted';
          const nativeStop = nativeOpenJev && data.missingPasses.some(item => item.pass === p && item.status === 'stopped');
          const generatedStop = generatedOpenJev && data.missingPasses.some(item => item.pass === p && item.condition === c && item.status === 'stopped_unknown');
          const sonnetMissing = freshSonnet ? data.missingPasses.find(item => item.pass === p && item.condition === c) : null;
          const localSmokeBlocked = localFresh && data.missingPasses.some(item => item.pass === p && item.condition === c && item.status === 'smoke_blocked');
          return `<div class="repeat-bar-row"><span>${displayPass(p)}</span>${n == null ? (kevStop ? '<span>Interrupted; unscored</span>' : stopped ? '<span>Stopped: 46 valid, 1 invalid, 2 service errors, 11 unsent; no score</span>' : thirdStop ? '<span>Stopped: 46 valid, 1 invalid, 3 service errors, 10 unsent; no score</span>' : qwen27P0Stop ? '<span>Stopped: 37 valid, 1 service error, 22 unsent; no score</span>' : qwen27P1Stop ? `<span>${data.cutoffDetail.laterP1.saved} saved, ${data.cutoffDetail.laterP1.neverSent} unsent; no score</span>` : gemmaStop ? '<span>Stopped: 1 valid, 1 service error, 58 unsent; no score</span>' : gemmaSecondStop ? '<span>Stopped: 4 valid, 1 service error, 55 unsent; no score</span>' : e4bStop ? '<span>Stopped: 50 valid, 2 unknown, 8 unsent; no score</span>' : gemmaUnsent ? '<span>Not sent</span>' : nativeStop || generatedStop ? '<span>Stopped; unscored</span>' : freshSonnet ? `<span>${esc(sonnetMissingLabel(sonnetMissing) + sonnetSavedLabel(sonnetMissing))}</span>` : localSmokeBlocked ? '<span>Smoke returned invalid format; full run not started</span>' : partial ? '<span>Partial run</span>' : '<span>Not completed</span>') : `<meter min="0" max="${data.denominator}" value="${n}" aria-label="${c} ${displayPass(p)} ${esc(fields[field])}: ${n} out of ${data.denominator}">${n}</meter><strong>${n}<small> / ${data.denominator}</small></strong>`}</div>`;
        }).join('')}<p class="repeat-range">${stats?.range ? `Three-pass range: <strong>${stats.range[0]}–${stats.range[1]}</strong> out of ${data.denominator}` : qwen27Cutoff || qwen27Second ? 'This entry covers fresh pass 3 only; select the hosted series for earlier passes.' : 'Three-pass range unavailable until all passes finish.'}</p></article>`;
      }).join('')}</div><p class="analysis-caveat">Bars start at zero. Agreement is measured against provisional references, separately from valid response format. Repeated comments are not independent cases.</p>`;
      document.getElementById('repeat-delta-title').textContent = nativeP0 ? 'One native decision procedure' : 'How did prompt scores change across passes?';
      document.getElementById('repeat-delta-intro').textContent = nativeKev ? 'Native P1 and P2 variants remain pending. This comparison covers the P0 Choice procedure only.' : nativeL0 ? 'This native L0 readout has only P0. P1 and P2 chat prompt variants do not apply.' : nativeL2 ? 'This native L2 calibration has only P0. P1 and P2 chat prompt variants do not apply.' : nativeP0 ? 'This native option-scoring setup has only P0. P1 and P2 chat prompt variants do not apply.' : 'Change in answers matching the provisional reference compared with P0 in the same pass. Positive means more matches; negative means fewer.';
      document.getElementById('repeat-deltas').innerHTML = nativeP0 ? '' : `<div class="table-wrap"><table><caption>${esc(fields[field])}: change from P0, out of ${data.denominator}</caption><thead><tr><th>Prompt</th>${passes.map(p => `<th>${passName[p]}</th>`).join('')}</tr></thead><tbody>${conditionOrder.filter(c => c !== 'P0').map(c => `<tr><th scope="row">${esc(c)}</th>${passes.map(p => {
        const d = (!freshSeries || (closedSlot(p, 'P0') && closedSlot(p, c)))
          ? data.withinPassPromptDeltas?.find(x => x.pass === p && x.to === c) : null;
        const localDelta = ((localFresh && data.passes[p]?.[c]?.completionStatus === 'complete' && data.passes[p]?.P0?.completionStatus === 'complete') ||
          ((gemmaContinuation || gemmaSecond || qwen27Second) && closedSlot(p, c) && closedSlot(p, 'P0')))
          ? valueOf(data.passes[p][c].score, field) - valueOf(data.passes[p].P0.score, field) : null;
        return `<td>${d ? signed(valueOf(d,field)) : localDelta == null ? 'Not completed' : signed(localDelta)}</td>`;
      }).join('')}</tr>`).join('')}</tbody></table></div>${qwenContinuation || generatedOpenJev || generatedSemIf || generatedAnyJev ? `<p class="analysis-caveat">Answer-change comparisons use only comments with answers in the required format in both conditions: ${(data.withinPassPromptFlips || []).filter(x => closedSlot(x.pass, 'P0') && closedSlot(x.pass, x.to)).map(x => `${esc(passName[x.pass])} P0 to ${esc(x.to)}: ${generatedAnyJev && x.denominator === 0 ? 'unavailable; none had answers in the required format in both conditions; ' : generatedOpenJev || generatedSemIf || generatedAnyJev ? `${(field === 'allFour' ? x.fourFieldVector : x[field]).changed} / ${x.denominator} changed; ` : ''}${x.denominator} of 60 comparable; ${x.excludedIds.length} excluded`).join('; ') || 'no paired conditions completed yet'}.</p>` : ''}`;
      const c = conditionControl.value;
      const changes = (!freshSeries || passes.every(p => closedSlot(p, c)))
        ? data.changesAcrossThreePasses?.[c] : null;
      const ids = changes ? (field === 'allFour' ? changes.fourFieldVector : changes.fields[field]) : null;
      const pairs = (data.pairwiseFlips || []).filter(x => x.condition === c &&
        (!freshSeries || (closedSlot(x.from, c) && closedSlot(x.to, c))));
      document.getElementById('repeat-flips').innerHTML = `${generatedAnyJev && changes?.denominator === 0 ? '<p>No comments had answers in the required format in all three passes; change comparisons are unavailable.</p>' : ids ? `<p><strong>${ids.length} / ${changes.denominator}</strong> comparable comments changed ${field === 'allFour' ? 'at least one decision' : esc(fields[field].toLowerCase())} across the three passes.</p><p class="repeat-case-ids">${ids.length ? ids.map(id => localFresh || data.passOrder ? esc(id) : `<a href="?experiment=${encodeURIComponent(data.configuration)}&amp;run=${encodeURIComponent(data.configuration + (c === 'P0' ? '' : '--' + c.toLowerCase()))}&amp;case=${encodeURIComponent(id)}#inspect">${esc(id)}</a>`).join(' · ') : 'No changed comments.'}</p><p>Comparable means answers met the required format in all three passes. ${changes.excludedIds.length} ${changes.excludedIds.length === 1 ? 'comment was' : 'comments were'} excluded because at least one pass did not.</p>` : freshSonnet && passes.every(p => closedSlot(p,c)) ? '<p>Pairwise changes between completed passes are listed below.</p>' : '<p>Three-pass changes are unavailable until all passes finish.</p>'}<ul>${pairs.map(x => {if (generatedAnyJev && x.denominator === 0) return `<li>${displayPass(x.from)} to ${displayPass(x.to)}: unavailable (0 comments with answers in the required format in both passes)</li>`; const f = field === 'allFour' ? x.fourFieldVector : nativeL1 ? x.fields[field] : x[field]; const changed = Array.isArray(f) ? f.length : f.changed; return `<li>${displayPass(x.from)} to ${displayPass(x.to)}: ${changed} / ${x.denominator} changed</li>`;}).join('')}</ul>`;
      if (qwen27Cutoff) document.getElementById('repeat-flips').innerHTML =
        '<p>Cross-pass answer changes are outside this fresh pass 3 cutoff. Select the earlier hosted series for its completed comparisons.</p>';
      if (qwen27Second) document.getElementById('repeat-flips').innerHTML =
        '<p>Cross-pass answer changes for these completed interrupted runs have not yet been calculated. Earlier hosted passes are available separately. <a href="https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/QWEN27_V2_SECOND_CONTINUATION_FINDINGS_2026-10-01.md">See the fresh pass 3 P0 to P1 changes on comments with valid answers in both.</a></p>';
      document.getElementById('repeat-usage-body').innerHTML = conditionOrder.flatMap(c => passes.map(p => {
        if (freshSonnet && !closed(data.passes[p]?.[c])) {
          const item=data.missingPasses.find(entry => entry.pass === p && entry.condition === c);
          const u=item?.usage;
          const saved=item?.savedRecords == null ? '' : `<br><small>${item.savedRecords} saved records of 60</small>`;
          const elapsed=u?.requestSecondsTotal;
          const requests=u?.requestCount ?? item?.attemptedRequests;
          const pricedRequests=Number.isInteger(requests) && requests > 0 && Number.isInteger(u?.unpricedRequests) && u.unpricedRequests >= 0 && u.unpricedRequests <= requests
            ? requests - u.unpricedRequests : null;
          const partialPrice=pricedRequests > 0 && u?.calculatedApiEquivalentUsd != null
            ? `${money(u.calculatedApiEquivalentUsd)}<br><small>Known partial usage for ${pricedRequests} priced ${pricedRequests === 1 ? 'request' : 'requests'}${u.unpricedRequests ? `; ${u.unpricedRequests} unpriced` : ''}; not a subscription charge</small>`
            : `Unavailable${pricedRequests === 0 ? '<br><small>No priced request usage; attempted cost unknown</small>' : ''}`;
          return `<tr><th scope="row">${c}</th><td>${displayPass(p)} (${esc(sonnetMissingLabel(item).toLowerCase())})</td><td>${number(item?.attemptedRequests)}${saved}</td><td>${number(u?.tokens?.input_tokens)}${u?.tokens?.input_tokens != null ? '<br><small>Saved partial usage</small>' : ''}</td><td>${number(u?.tokens?.output_tokens)}${u?.tokens?.output_tokens != null ? '<br><small>Saved partial usage</small>' : ''}</td><td>Unavailable</td><td>${partialPrice}</td><td>${elapsed == null ? 'Unavailable' : `${Number(elapsed).toFixed(1)}<br><small>Saved partial usage</small>`}</td></tr>`;
        }
        if (qwen27Final && p === 'fresh3' && (c === 'P0' || c === 'P1')) {
          const phase = data.passes[p][c], u = phase.usage;
          const tokens = key => {
            const metric = u.tokens[key];
            return metric.sum == null ? `Unavailable overall<br><small>${metric.reportedCount} of 60 reported</small>` : number(metric.sum);
          };
          return `<tr><th scope="row">${c}</th><td>Fresh pass 3 (interrupted composite)</td><td>60 attempted<br><small>${phase.score.valid} valid${phase.score.serviceErrors ? ', 1 preserved service error' : ''}</small></td><td>${tokens('prompt_tokens')}</td><td>${tokens('completion_tokens')}<br><small>Provider-reported reasoning: ${tokens('provider_reported_reasoning_tokens')}</small></td><td>${money(u.knownObservedCostUsd)} known${u.unknownCostCount ? `<br><small>Unknown original charge up to ${money(data.originalP0UnknownCostUpperBoundUsd)}; not observed</small>` : ''}</td><td>Unavailable</td><td>${u.clientRequestToRecordSeconds.toFixed(1)}<br><small>Client request-to-record</small></td></tr>`;
        }
        if (qwen27Second) {
          const phase = data.cutoffDetail.conditions[c];
          const u = phase.usage;
          const tokens = key => {
            const metric = u.tokens[key];
            return metric.sum == null ? `Unavailable overall<br><small>${metric.reportedCount} of 60 reported</small>`
              : number(metric.sum);
          };
          return `<tr><th scope="row">${c}</th><td>Fresh pass 3 (closed interrupted composite)</td><td>60 attempted<br><small>${phase.score.valid} valid${phase.score.serviceErrors ? ', 1 preserved service error' : ''}</small></td><td>${tokens('prompt_tokens')}</td><td>${tokens('completion_tokens')}<br><small>Provider-reported reasoning: ${tokens('provider_reported_reasoning_tokens')}</small></td><td>${money(u.knownObservedCostUsd)} known${u.unknownCostCount ? `<br><small>Unknown original charge up to ${money(data.cutoffDetail.originalP0UnknownCostUpperBoundUsd)}; not observed</small>` : ''}</td><td>Unavailable</td><td>${u.clientRequestToRecordSeconds.toFixed(1)}<br><small>Client request-to-record</small></td></tr>`;
        }
        if (qwen27Cutoff) {
          const item = data.cutoffDetail;
          if (c === 'P0') return `<tr><th scope="row">P0</th><td>Fresh pass 3${item.score ? ' (closed composite)' : ' (stopped, unscored)'}</td><td>${item.validSaved + 1} attempted<br><small>${item.validSaved} valid, 1 service error, ${item.neverSentAfterContinuation.length} unsent</small></td><td>${number(item.tokens.prompt_tokens.sum)}<br><small>${item.tokens.prompt_tokens.reportedCount} saved responses</small></td><td>${number(item.tokens.completion_tokens.sum)}<br><small>${item.tokens.completion_tokens.reportedCount} saved responses</small></td><td>${money(item.knownObservedDevelopmentCostUsd)} known<br><small>Unknown charge up to ${money(item.unknownCostUpperBoundUsd)}; not observed</small></td><td>Unavailable</td><td>${item.clientRequestToRecordSeconds.toFixed(1)}<br><small>Client request-to-record</small></td></tr>`;
          const later = item.laterP1;
          return `<tr><th scope="row">P1</th><td>Fresh pass 3 (unscored)</td><td>${later.saved} attempted<br><small>${later.neverSent} unsent</small></td><td>Unavailable</td><td>Unavailable</td><td>${money(later.knownObservedDevelopmentCostUsd)} known</td><td>Unavailable</td><td>${later.clientRequestToRecordSeconds == null ? 'Unavailable' : later.clientRequestToRecordSeconds.toFixed(1) + ' client seconds'}</td></tr>`;
        }
        if (gemmaSecond && p === 'fresh2' && c === 'P0') {
          const original = data.stoppedPhases[0].usage;
          const suffix = data.cutoffDetail.closedStageUsage['fresh2/P0/suffix'];
          return `<tr><th scope="row">P0</th><td>Fresh pass 2 (closed composite)</td><td>60 attempted<br><small>59 valid, 1 preserved service error</small></td><td>Unavailable overall<br><small>58 suffix responses: ${number(suffix.tokenAvailability.prompt_tokens.sum)}</small></td><td>Unavailable overall<br><small>58 suffix responses: ${number(suffix.tokenAvailability.completion_tokens.sum)}</small></td><td>${money(Number(original.knownCostUsd) + Number(suffix.knownCostUsd))} known<br><small>Unknown charge up to ${money(data.cutoffDetail.secondInterruption.unknownCostUpperBoundUsd)}; not observed</small></td><td>Unavailable</td><td>${(original.requestSecondsTotal + suffix.clientSecondsTotal).toFixed(1)}<br><small>Client request-to-record</small></td></tr>`;
        }
        if (gemmaSecond && p === 'fresh3' && c === 'P2')
          return '<tr><th scope="row">P2</th><td>Fresh pass 3 (stopped, unscored)</td><td>5 attempted<br><small>4 valid, 1 service error, 55 unsent</small></td><td>Unavailable</td><td>Unavailable</td><td>Unavailable</td><td>Unavailable</td><td>Unavailable</td></tr>';
        if (deepseekThird && p === 'fresh1' && c === 'P2')
          return '<tr><th scope="row">P2</th><td>Fresh pass 1 (stopped, unscored)</td><td>50 attempted<br><small>46 valid, 1 invalid, 3 service errors, 10 unsent</small></td><td>Unavailable</td><td>Unavailable</td><td>Unavailable in this cutoff</td><td>Unavailable</td><td>Client HTTP time only for DEV-050; see public cutoff</td></tr>';
        if (interruptedE4b && p === 'fresh2' && c === 'P2') {
          const u = interruptedE4b.usage;
          return `<tr><th scope="row">P2</th><td>Fresh pass 2 (stopped, unscored)</td><td>52 attempted<br><small>50 saved, 2 unknown, 8 unsent</small></td><td>${number(u.tokens.input)}<br><small>50 saved responses only</small></td><td>${number(u.tokens.output)}<br><small>50 saved responses only</small></td><td>Unavailable</td><td>Unavailable</td><td>${u.observedClientRequestSeconds.toFixed(1)}<br><small>Includes host sleep; not model inference time</small></td></tr>`;
        }
        if (gemmaContinuation || gemmaSecond) {
          const stopped = p === 'fresh2' && c === 'P0';
          const u = stopped ? data.stoppedPhases[0].usage : data.passes[p]?.[c]?.usage;
          if (!u) return `<tr><th scope="row">${c}</th><td>${displayPass(p)} (not sent)</td><td>Not sent</td><td>Unavailable</td><td>Unavailable</td><td>Unavailable</td><td>Unavailable</td><td>Not sent</td></tr>`;
          const token = key => {
            const metric = u.tokenAvailability[key];
            return metric.sum == null ? `Unavailable<br><small>${metric.reportedCount} of ${u.requestCount} reported</small>`
              : number(metric.sum);
          };
          const cost = u.unknownCostCount
            ? `${money(u.knownCostUsd)} known<br><small>Unknown charge up to ${money(u.unknownCostUpperBoundUsd)}; not observed</small>`
            : money(u.actualCostUsd);
          return `<tr><th scope="row">${c}</th><td>${displayPass(p)}${stopped ? ' (stopped, unscored)' : ''}</td><td>${u.requestCount} attempted</td><td>${token('prompt_tokens')}</td><td>${token('completion_tokens')}<br><small>Provider-reported reasoning: ${token('providerReportedReasoningTokens')}</small></td><td>${cost}</td><td>Unavailable</td><td>${u.requestSecondsTotal.toFixed(1)}</td></tr>`;
        }
        if (nativeKev && data.kevSource.passes[p]?.completionStatus === 'interrupted') {
          const phase = data.kevSource.passes[p], u = phase.usage;
          return `<tr><th scope="row">P0</th><td>${displayPass(p)} (interrupted, unscored)</td><td>${phase.outcomes.valid + phase.outcomes.transportErrorUnknownOutcome} attempted<br><small>${phase.outcomes.valid} known responses</small></td><td>${number(u?.inputTokens)}<br><small>Known responses only</small></td><td>${number(u?.outputTokens)}<br><small>Known responses only</small></td><td>${money(phase.knownActualProviderCostUsd)} known<br><small>Unknown charge up to ${money(phase.unknownCostReservationUsd)}; not an observed charge</small></td><td>Unavailable</td><td>${u?.clientRequestSeconds?.total == null ? 'Unavailable' : u.clientRequestSeconds.total.toFixed(1) + ' known responses'}<br><small>${u?.clientRequestSeconds?.unknownAttempt == null ? 'Timeout duration unavailable' : u.clientRequestSeconds.unknownAttempt.toFixed(1) + ' timeout; outcome unknown'}</small></td></tr>`;
        }
        const interrupted = deepseekLowContinuation && p === 'fresh1' && c === 'P2';
        const nativeStop = nativeOpenJev && data.missingPasses.some(item => item.pass === p && item.status === 'stopped');
        const generatedStop = generatedOpenJev && data.missingPasses.some(item => item.pass === p && item.condition === c && item.status === 'stopped_unknown');
        const u = (localFresh || nativeP0 || freshCodex || freshSonnet || freshHosted || qwenContinuation || deepseekLowContinuation || deepseekThird) && !closed(data.passes[p]?.[c]) ? null : data.passes[p]?.[c]?.usage;
        const elapsed = u?.requestSecondsTotal ?? u?.clientHttpCallSecondsTotal ?? u?.clientRequestSecondsTotal ?? u?.clientPredictionSeconds;
        const sonnetCoverage=freshSonnet && Number.isInteger(u?.requestCount) && Number.isInteger(u?.unpricedRequests) && u.unpricedRequests >= 0 && u.unpricedRequests <= u.requestCount
          ? u.requestCount-u.unpricedRequests : null;
        const sonnetTokenNote=freshSonnet && sonnetCoverage !== null && u.unpricedRequests > 0 ? `<br><small>Known usage for ${sonnetCoverage} of ${u.requestCount} requests</small>` : '';
        const nativePositions = nativeL1 && u?.tokens?.input_token_positions != null ? `<br><small>Native input positions: ${number(u.tokens.input_token_positions)} (not billed tokens)</small>` : nativeAlex && u?.nativeNliInputTokenPositions != null ? `<br><small>Native NLI input positions: ${number(u.nativeNliInputTokenPositions)}</small>` : '';
        const subscription=subscriptionPrice(data,p,c);
        const priceCell=subscription
          ? `${money(subscription.estimateUsd)}<br><small>Current public-rate estimate, ${esc(subscription.rate.checkedDate)} · ${priceSource(subscription)}${subscription.estimateUsd === null ? ` · ${esc(subscription.estimateStatus.replace(/_/g,' '))}` : subscription.estimateStatus === 'known_usage_only' ? ' · known usage only' : ''}</small>${subscription.estimateUsd === null && u?.cliListPriceEstimateUsd != null ? `<br><small>Saved CLI API-equivalent estimate: ${money(u.cliListPriceEstimateUsd)}. Cache lifetime was not resolved for the current-rate calculation.</small>` : ''}`
          : freshSonnet
          ? sonnetCoverage === u?.requestCount && u?.calculatedApiEquivalentUsd != null
            ? `${money(u.calculatedApiEquivalentUsd)}<br><small>API-equivalent calculation from saved usage${/^https:\/\//.test(u.priceSource || '') ? ` · <a href="${esc(u.priceSource)}" target="_blank" rel="noopener noreferrer">Public rate ↗</a>` : ''}; not a subscription charge</small>`
            : `Unavailable${sonnetCoverage !== null && u.unpricedRequests > 0 ? `<br><small>${u.unpricedRequests} ${u.unpricedRequests === 1 ? 'request' : 'requests'} without priced usage; full estimate unknown</small>` : ''}`
          : `${money(u?.estimatedTokenPriceCostUsd ?? u?.cliListPriceEstimateUsd)}${u?.estimatedTokenPriceCostUsd != null ? '<br><small>Reported input tokens × published price</small>' : u?.cliListPriceEstimateUsd != null ? '<br><small>CLI list-price estimate</small>' : ''}`;
        return `<tr><th scope="row">${c}</th><td>${displayPass(p)}${interrupted || nativeStop || generatedStop ? ' (stopped, unscored)' : data.passes[p]?.[c]?.completionStatus === 'partial' ? ' (partial)' : ''}</td><td>${interrupted ? '49 attempted' : number(u?.startedRequestCount ?? u?.requestCount)}</td><td>${freshSonnet && sonnetCoverage === 0 ? 'Unavailable' : number(u?.tokens?.input_tokens ?? u?.tokens?.prompt_tokens)}${sonnetTokenNote}${nativePositions}<br><small>Cache read: ${freshSonnet && sonnetCoverage === 0 ? 'Unavailable' : number(u?.tokens?.cache_read_input_tokens ?? u?.tokens?.cached_input_tokens)}<br>Cache write: ${freshSonnet && sonnetCoverage === 0 ? 'Unavailable' : number(u?.tokens?.cache_creation_input_tokens ?? u?.tokens?.cache_write_input_tokens)}</small></td><td>${freshSonnet && sonnetCoverage === 0 ? 'Unavailable' : number(u?.tokens?.output_tokens ?? u?.tokens?.completion_tokens)}${sonnetTokenNote}<br><small>Reasoning: ${freshSonnet && sonnetCoverage === 0 ? 'Unavailable' : number(u?.tokens?.thinking_tokens ?? u?.tokens?.reasoning_output_tokens)}${u?.providerReasoningTokensAboveCompletionCount ? `<br>Provider reasoning count exceeds output count in ${number(u.providerReasoningTokensAboveCompletionCount)} responses; retained as reported.` : ''}</small></td><td>${interrupted ? 'Partial; see accounting note above' : money(u?.actualCostUsd ?? u?.knownCostUsd)}${qwenUnknownFor(p, c) ? `<br><small>Unknown charge up to ${money(qwenUnknownFor(p, c))}</small>` : u?.unknownCostCount ? ` (${u.unknownCostCount} unknown)` : ''}</td><td>${priceCell}</td><td>${elapsed == null ? (data.passes[p]?.[c] ? 'Unavailable' : 'Not completed') : elapsed.toFixed(1)}</td></tr>`;
      })).join('');
    }
    const searchControl = document.getElementById('repeat-search');
    const coverageControl = document.getElementById('repeat-coverage');
    const categoryControl = document.getElementById('repeat-category');
    const interfaceControl = document.getElementById('repeat-interface');
    function filterStudies() {
      const query = (searchControl?.value || '').trim().toLowerCase();
      const coverage = coverageControl?.value || '';
      const category = categoryControl?.value || '';
      const interfaceKind = interfaceControl?.value || '';
      const matches = series.filter(s => {
        const recorded = isQwen27Final(s) ? s.scoredConditions : s.completedConditions;
        const allRecorded = Number.isFinite(s.plannedConditions) && s.plannedConditions > 0 && recorded === s.plannedConditions;
        return (!query || `${s.displayName || ''} ${s.configuration || ''} ${s.method || ''}`.toLowerCase().includes(query)) &&
          (!coverage || (coverage === 'complete' ? allRecorded : !allRecorded)) &&
          (!category || modelType(s).category === category) && (!interfaceKind || modelType(s).interfaceKind === interfaceKind);
      });
      const previous = configControl.value;
      configControl.innerHTML = matches.map(s => `<option value="${esc(seriesKey(s))}">${esc(s.displayName || s.configuration)}</option>`).join('');
      configControl.disabled = !matches.length;
      const panel=document.getElementById('repeat-selected-results'); if(panel) panel.hidden=!matches.length;
      const count=document.getElementById('repeat-filter-count'); if(count) count.textContent=matches.length ? `${matches.length} of ${series.length} studies match. Recorded runs can include failed answers.` : 'No studies match. Clear the filters to see all studies.';
      if(matches.length) {configControl.value=matches.some(s=>seriesKey(s)===previous)?previous:seriesKey(matches[0]);render();}
    }
    searchControl?.addEventListener('input', filterStudies);
    coverageControl?.addEventListener('change', filterStudies);
    categoryControl?.addEventListener('change', filterStudies);
    interfaceControl?.addEventListener('change', filterStudies);
    configControl.addEventListener('change', render);
    fieldControl.addEventListener('change', render);
    conditionControl.addEventListener('change', render);
    filterStudies();
  }).catch(() => {root.innerHTML = '<p>Repeat results could not be loaded. <a href="https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/REPEAT_FINDINGS.md">Read the saved repeat report</a>.</p>';});
})();
