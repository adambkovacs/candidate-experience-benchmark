/* Each configuration is one separate 60-record repeat series. */
(() => {
  const root = document.getElementById('repeat-results');
  if (!root) return;
  const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const passName = {original:'Pass 1', repeat2:'Pass 2', repeat3:'Pass 3', pass1:'Pass 1', pass2:'Pass 2', pass3:'Pass 3', fresh1:'Fresh pass 1', fresh2:'Fresh pass 2', fresh3:'Fresh pass 3'};
  const conditions = {P0:'Base task', P1:'Classifier instructions', P2:'Instructions and decision tree'};
  const fields = {allFour:'All four decisions', sentiment:'Sentiment', follow_up_needed:'Follow-up needed', serious_concern_reported:'Serious concern', testimonial_potential:'Testimonial potential'};
  const valueOf = (score, field) => field === 'allFour' ? score.allFour : score.fields[field];
  const signed = n => n > 0 ? `+${n}` : String(n);
  const number = n => n == null ? 'Unavailable' : n.toLocaleString('en-US');
  const money = n => n == null || !Number.isFinite(Number(n)) ? 'Unavailable' : '$' + Number(n).toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 8});

  const hostedV2Ids = {'openrouter-paid-gemma4-26b-a4b-on': 'gemma26-on-fresh-matched3-v2', 'openrouter-paid-qwen3.8-27b-medium': 'qwen27-fresh-matched3-v2-medium', 'openrouter-paid-qwen3.8-27b-xhigh': 'qwen27-fresh-matched3-v2-xhigh'};
  const feedUrls = ['./typesafe-repeats.json', './hosted-v2-repeats.json', './kev-native-repeats.json', './repeats.json', './hosted-repeats.json', './claude-repeats.json', './claude-roster-repeats.json', './gemini-repeats.json', './haiku-fresh-matched3.json', './laya-repeats.json', './semif-repeats.json', './semif-generated-repeats.json', './small-local-repeats.json', './anyjev-raw-repeats.json', './anyjev-l0-repeats.json', './anyjev-l1-repeats.json', './anyjev-l2-repeats.json', './anyjev-generated-repeats.json', './openjev-native-repeats.json', './openjev-generated-repeats.json', './alex-native-repeats.json', './codex-fresh-repeats.json', './deepseek-fresh-repeats.json', './additional-hosted-fresh-repeats.json', './qwen36-off-second-interruption-findings.json', './deepseek-low-continuation-repeats.json'];
  const qwenContinuationSchema = 'qwen36-off-v2-second-interruption-findings-v1';
  const qwenContinuationId = 'openrouter-paid-qwen36-35b-a3b-off-descriptive-two-interruptions-v1';
  const deepseekLowContinuationSchema = 'deepseek-low-descriptive-interruption-findings-v1';
  const deepseekLowContinuationId = 'openrouter-paid-deepseek-v41-flash-low-descriptive-continuation-v1';
  const qwenDispatchOrder = [['fresh1','P0'], ['fresh1','P1'], ['fresh1','P2'],
    ['fresh2','P2'], ['fresh2','P0'], ['fresh2','P1'], ['fresh3','P1'], ['fresh3','P2'], ['fresh3','P0']];
  const additionalHostedIds = {
    'openrouter-paid-qwen36-35b-a3b-off': 'openrouter-paid-qwen36-35b-a3b-off-fresh-matched3-v2',
    'openrouter-paid-deepseek-v41-flash-low': 'openrouter-paid-deepseek-v41-flash-low-fresh-matched3-v2'
  };
  Promise.all(feedUrls.map(url => fetch(url).then(r => {
    if (!r.ok && (url === './hosted-v2-repeats.json' || url === './kev-native-repeats.json' || url === './semif-generated-repeats.json' || url === './small-local-repeats.json' || url === './anyjev-raw-repeats.json' || url === './anyjev-l0-repeats.json' || url === './anyjev-l1-repeats.json' || url === './anyjev-l2-repeats.json' || url === './anyjev-generated-repeats.json' || url === './openjev-native-repeats.json' || url === './openjev-generated-repeats.json' || url === './alex-native-repeats.json' || url === './codex-fresh-repeats.json' || url === './deepseek-fresh-repeats.json' || url === './additional-hosted-fresh-repeats.json' || url === './qwen36-off-second-interruption-findings.json' || url === './deepseek-low-continuation-repeats.json') && r.status === 404) return {series: []};
    if (!r.ok) throw Error('Missing repeat results');
    return r.json().then(payload => {
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
      return payload;
    });
  }))).then(payloads => {
    const loadedSeries = payloads.flatMap(payload => payload?.series || (payload ? [payload] : []));
    const hasDeepseekLowContinuation = loadedSeries.some(s => s?.seriesId === deepseekLowContinuationId);
    const series = loadedSeries.filter(s => !(hasDeepseekLowContinuation &&
      s?.schema === 'additional-hosted-fresh-repeat-findings-v1' &&
      s?.configuration === 'openrouter-paid-deepseek-v41-flash-low'));
    if (!series.length) throw Error('No repeat series');
    const isFreshCodex = s => s.schema === 'codex-fresh-repeat-findings-v1' && s.method === 'fresh-matched-three';
    const isFreshHosted = s => (s.schema === 'deepseek-fresh-repeat-findings-v1' ||
      s.schema === 'additional-hosted-fresh-repeat-findings-v1' || s.schema === 'hosted-v2-fresh-repeat-findings-v1') && s.method === 'fresh-matched-three';
    const isQwenContinuation = s => s.schema === qwenContinuationSchema &&
      s.method === 'descriptive-continuation-after-two-service-errors';
    const isDeepseekLowContinuation = s => s.schema === deepseekLowContinuationSchema &&
      s.method === 'descriptive-continuation-after-service-error';
    const isNativeOpenJev = s => s.schema === 'openjev-native-fresh-three-report-v1' &&
      s.method === 'native-output-stability';
    const isGeneratedOpenJev = s => s.schema === 'openjev-generated-fresh-three-report-v2' &&
      s.method === 'fresh-generated-output-stability';
    const isGeneratedSemIf = s => s.schema === 'semif-generated-fresh-repeat-findings-v1' &&
      s.method === 'fresh-native-generated-repeat';
    const isGeneratedAnyJev = s => s.schema === 'anyjev-generated-repeat-findings-v1' &&
      s.method === 'generated-json-control';
    const seriesKey = s => isFreshCodex(s) || isFreshHosted(s) || isQwenContinuation(s) || isDeepseekLowContinuation(s) || isNativeOpenJev(s) || isGeneratedOpenJev(s) ? s.seriesId : s.configuration;
    root.innerHTML = `<label class="repeat-control">Model and test setup <select id="repeat-config">${series.map(s => `<option value="${esc(seriesKey(s))}">${esc(s.displayName || s.configuration)}${isFreshCodex(s) ? ' · three new passes' : ''}</option>`).join('')}</select></label>
      <p class="repeat-summary" id="repeat-summary"></p><details class="repeat-usage"><summary>Study details and measurement limits</summary><p class="repeat-lead" id="repeat-lead"></p></details><div id="repeat-interpretation"></div>
      <label class="repeat-control">Compare agreement for <select id="repeat-field">${Object.entries(fields).map(([k,v]) => `<option value="${k}">${v}</option>`).join('')}</select></label>
      <div id="repeat-chart" aria-live="polite"></div>
      <div class="repeat-detail-grid"><div><h3 id="repeat-delta-title">How did prompt scores change across passes?</h3><p id="repeat-delta-intro">Change in matching answers compared with P0 in the same pass. Positive means more matches; negative means fewer.</p><div id="repeat-deltas"></div></div>
      <div><h3>Which answers changed?</h3><label class="repeat-control"><span id="repeat-condition-label">Prompt condition</span> <select id="repeat-condition">${Object.entries(conditions).map(([k,v]) => `<option value="${k}">${k}: ${v}</option>`).join('')}</select></label><div id="repeat-flips" aria-live="polite"></div></div></div>
      <details class="repeat-usage"><summary>Requests, tokens and reported costs</summary><p>Each completed row covers 60 comments. Request counts depend on whether the configuration uses individual comments or batches. Smoke tests are separate. Input and cache counts follow each provider's definitions and must not be added without checking them. Reported API charges appear when available; Token-price and CLI list-price estimates are shown separately and are not verified invoices or subscription charges. Subscription costs and pure inference time remain unavailable. Request durations include client and service overhead.</p><div class="table-wrap"><table><caption>Recorded development usage</caption><thead><tr><th>Condition</th><th>Pass</th><th>Requests</th><th>Input tokens</th><th>Output tokens</th><th>Reported cost (USD)</th><th>Price-based estimate (USD)</th><th>Sum of request seconds</th></tr></thead><tbody id="repeat-usage-body"></tbody></table></div></details>`;
    const configControl = document.getElementById('repeat-config');
    const fieldControl = document.getElementById('repeat-field');
    const conditionControl = document.getElementById('repeat-condition');

    function render() {
      const data = series.find(s => seriesKey(s) === configControl.value);
      if (!data) throw Error('Unknown repeat configuration');
      const freshCodex = isFreshCodex(data);
      const freshHosted = isFreshHosted(data);
      const qwenContinuation = isQwenContinuation(data);
      const deepseekLowContinuation = isDeepseekLowContinuation(data);
      const nativeOpenJev = isNativeOpenJev(data);
      const generatedOpenJev = isGeneratedOpenJev(data);
      const generatedSemIf = isGeneratedSemIf(data);
      const generatedAnyJev = isGeneratedAnyJev(data);
      const localFresh = data.method === 'fresh-matched-local-output-stability';
      const passes = data.passOrder || (localFresh ? ['fresh1', 'fresh2', 'fresh3'] : ['original', 'repeat2', 'repeat3']);
      const conditionOrder = data.conditionOrder || ['P0', 'P1', 'P2'];
      const nativeP0 = data.method === 'native-output-stability';
      const nativeL0 = data.schema === 'anyjev-l0-native-repeat-findings-v1';
      const nativeL1 = data.schema === 'anyjev-l1-direct-native-repeat-findings-v1';
      const nativeL2 = data.schema === 'anyjev-l2-native-repeat-findings-v1';
      const nativeKev = data.schema === 'kev-native-repeat-findings-v1';
      const nativeAlex = data.schema === 'alex-native-repeat-findings-v1';
      const displayPass = pass => nativeL2 ? ({original: 'Historical pass', repeat2: 'Repeat 2', repeat3: 'Repeat 3'}[pass] || pass) : passName[pass];
      const closed = phase => qwenContinuation || deepseekLowContinuation ? phase?.status === 'completed' || phase?.status === 'closed_with_service_error'
        : freshCodex || freshHosted ? phase?.status === 'completed'
        : generatedOpenJev || generatedSemIf || generatedAnyJev ? phase?.completionStatus === 'complete'
        : (localFresh || nativeP0) ? phase?.completionStatus === 'complete'
          : Boolean(phase) && phase.completionStatus !== 'partial';
      const freshSeries = data.schema === 'hosted-v2-fresh-repeat-findings-v1' || data.schema === 'additional-hosted-fresh-repeat-findings-v1' || qwenContinuation || deepseekLowContinuation || nativeOpenJev || generatedOpenJev || generatedSemIf || generatedAnyJev || nativeKev;
      const qwenUnknownFor = (pass, condition) => qwenContinuation
        ? data.secondInterruption.retainedOldUnknownBounds.find(item => item.phase === `${pass}/${condition}`)?.upperBoundUsd
        : null;
      const closedSlot = (pass, condition) => closed(data.passes[pass]?.[condition]);
      const nativeLabel = nativeL0 ? 'Native L0 readout' : nativeL1 ? 'Native L1 calibration' : nativeL2 ? 'Native L2 calibration' : nativeOpenJev ? 'Native OpenJev P0' : nativeKev ? 'Native Choice' : nativeAlex ? 'Native NLI output' : 'Native output';
      document.getElementById('repeat-condition-label').textContent = nativeP0 ? 'Native condition' : 'Prompt condition';
      if (!conditionOrder.includes(conditionControl.value)) conditionControl.value = conditionOrder[0];
      conditionControl.innerHTML = conditionOrder.map(c => `<option value="${esc(c)}"${c === conditionControl.value ? ' selected' : ''}>${c}: ${esc(nativeP0 && c === 'P0' ? nativeLabel : conditions[c] || c)}</option>`).join('');
      const field = fieldControl.value;
      document.getElementById('repeat-interpretation').innerHTML = generatedAnyJev
        ? `<details><summary>Protocol and measurement limits</summary><p>This generated JSON control is separate from AnyJev native readouts. The strict parser does not repair fenced JSON. Answer-change comparisons use only comments with answers in the required format in both phases. When none qualify, stability cannot be assessed.</p>${(data.interpretation || []).map(text => `<p>${esc(text)}</p>`).join('')}</details>`
        : (qwenContinuation
        ? '<p class="analysis-caveat"><strong>Descriptive continuation after two service errors:</strong> Fresh pass 1 P0 retains DEV-006 and fresh pass 3 P1 retains DEV-031. Each phase has 59 valid outputs and one HTTP 429 service error among 60 comments. The unsent requests ran later without replaying either failed request. This is not a clean matched-three series. Scores keep all 60 comments; answer-change rates use only comments with answers in the required format in both passes.</p>'
        : deepseekLowContinuation
        ? '<p class="analysis-caveat"><strong>Interrupted descriptive continuation:</strong> Fresh pass 1 P2 stopped at DEV-049 after an earlier stop at DEV-040. DEV-039 was billed but invalid; DEV-040 and DEV-049 were service errors. P2 has no score because 11 of its 60 comments remain unsent. The later passes have not run. This is not a clean matched-three series.</p>'
        : '') + (data.interpretation || []).map(text => `<p>${esc(text)}</p>`).join('');
      const generatedAnyJevValidity = generatedAnyJev ? conditionOrder.map(condition =>
        `${condition} ${passes.map(pass => closedSlot(pass, condition)
          ? data.passes[pass][condition].score.valid : 'pending').join(' / ')}`) : [];
      const readerSummary = document.getElementById('repeat-summary');
      if (readerSummary) readerSummary.textContent = `${data.completedConditions} of ${data.plannedConditions} planned tests have final results for the same ${data.denominator} fictional comments. Finished tests can include failed or unusable answers. ${data.displayName || data.configuration}. Open study details for costs and measurement limits.`;
      document.getElementById('repeat-lead').textContent = generatedAnyJev
        ? `${data.displayName || data.configuration}. ${data.completedConditions} of ${data.plannedConditions} full phases closed; separate from native AnyJev. Valid responses by pass 1/2/3: ${generatedAnyJevValidity.join('; ')}${data.completedConditions < data.plannedConditions ? ' (pending means no full score)' : ''}. Counts and scores use all ${data.denominator} reviews, including invalid outputs.`
        : `${data.displayName || data.configuration}. ${data.completedConditions} of ${data.plannedConditions} planned ${nativeP0 ? 'native P0 passes' : 'prompt/pass combinations'} have complete evidence on the same ${data.denominator} development comments. Incomplete passes are not zero scores.` + Object.entries(data.passes).flatMap(([pass, conditions]) => Object.entries(conditions).filter(([, phase]) => phase.completionStatus === 'partial').map(([condition, phase]) => { const o = phase.score.outcomes; return ` ${condition} ${displayPass(pass)} stopped with ${o.valid} valid responses, ${o.service_error || 0} service errors and ${o.never_sent || 0} reviews not sent.`; })).join('');
      if (localFresh) document.getElementById('repeat-lead').textContent += ` These are three fresh local passes. Earlier local results are observational and are not counted here. Only terminal phases have scores. Reference labels are provisional and were used only for offline scoring. Client request time includes runtime overhead; loaded engine version, model load time and local cost are unknown.`;
      if (freshCodex) document.getElementById('repeat-lead').textContent += ' Each series schedules three fresh Codex subscription passes. Earlier results remain separate and are not pass one. Only closed development phases are scored. The requested model and CLI version are recorded; the served model identity and revision, effective seed and attributable subscription cost are unavailable. Request time includes client overhead.';
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
          const kevStop = nativeKev && phase?.completionStatus === 'interrupted';
          const nativeStop = nativeOpenJev && data.missingPasses.some(item => item.pass === p && item.status === 'stopped');
          const generatedStop = generatedOpenJev && data.missingPasses.some(item => item.pass === p && item.condition === c && item.status === 'stopped_unknown');
          return `<div class="repeat-bar-row"><span>${displayPass(p)}</span>${n == null ? (kevStop ? '<span>Interrupted; unscored</span>' : stopped ? '<span>Stopped: 46 valid, 1 invalid, 2 service errors, 11 unsent; no score</span>' : nativeStop || generatedStop ? '<span>Stopped; unscored</span>' : partial ? '<span>Partial run</span>' : '<span>Not completed</span>') : `<meter min="0" max="${data.denominator}" value="${n}" aria-label="${c} ${displayPass(p)} ${esc(fields[field])}: ${n} out of ${data.denominator}">${n}</meter><strong>${n}<small> / ${data.denominator}</small></strong>`}</div>`;
        }).join('')}<p class="repeat-range">${stats?.range ? `Three-pass range: <strong>${stats.range[0]}–${stats.range[1]}</strong> out of ${data.denominator}` : 'Three-pass range unavailable until all passes finish.'}</p></article>`;
      }).join('')}</div><p class="analysis-caveat">Bars start at zero. Agreement is measured against provisional references, separately from valid response format. Repeated comments are not independent cases.</p>`;
      document.getElementById('repeat-delta-title').textContent = nativeP0 ? 'One native decision procedure' : 'How did prompt scores change across passes?';
      document.getElementById('repeat-delta-intro').textContent = nativeKev ? 'Native P1 and P2 variants remain pending. This comparison covers the P0 Choice procedure only.' : nativeL0 ? 'This native L0 readout has only P0. P1 and P2 chat prompt variants do not apply.' : nativeL2 ? 'This native L2 calibration has only P0. P1 and P2 chat prompt variants do not apply.' : nativeP0 ? 'This native option-scoring setup has only P0. P1 and P2 chat prompt variants do not apply.' : 'Change in answers matching the provisional reference compared with P0 in the same pass. Positive means more matches; negative means fewer.';
      document.getElementById('repeat-deltas').innerHTML = nativeP0 ? '' : `<div class="table-wrap"><table><caption>${esc(fields[field])}: change from P0, out of ${data.denominator}</caption><thead><tr><th>Prompt</th>${passes.map(p => `<th>${passName[p]}</th>`).join('')}</tr></thead><tbody>${conditionOrder.filter(c => c !== 'P0').map(c => `<tr><th scope="row">${esc(c)}</th>${passes.map(p => {
        const d = (!freshSeries || (closedSlot(p, 'P0') && closedSlot(p, c)))
          ? data.withinPassPromptDeltas?.find(x => x.pass === p && x.to === c) : null;
        const localDelta = localFresh && data.passes[p]?.[c]?.completionStatus === 'complete' && data.passes[p]?.P0?.completionStatus === 'complete'
          ? valueOf(data.passes[p][c].score, field) - valueOf(data.passes[p].P0.score, field) : null;
        return `<td>${d ? signed(valueOf(d,field)) : localDelta == null ? 'Not completed' : signed(localDelta)}</td>`;
      }).join('')}</tr>`).join('')}</tbody></table></div>${qwenContinuation || generatedOpenJev || generatedSemIf || generatedAnyJev ? `<p class="analysis-caveat">Answer-change comparisons use only comments with answers in the required format in both conditions: ${(data.withinPassPromptFlips || []).filter(x => closedSlot(x.pass, 'P0') && closedSlot(x.pass, x.to)).map(x => `${esc(passName[x.pass])} P0 to ${esc(x.to)}: ${generatedAnyJev && x.denominator === 0 ? 'unavailable; none had answers in the required format in both conditions; ' : generatedOpenJev || generatedSemIf || generatedAnyJev ? `${(field === 'allFour' ? x.fourFieldVector : x[field]).changed} / ${x.denominator} changed; ` : ''}${x.denominator} of 60 comparable; ${x.excludedIds.length} excluded`).join('; ') || 'no paired conditions completed yet'}.</p>` : ''}`;
      const c = conditionControl.value;
      const changes = (!freshSeries || passes.every(p => closedSlot(p, c)))
        ? data.changesAcrossThreePasses?.[c] : null;
      const ids = changes ? (field === 'allFour' ? changes.fourFieldVector : changes.fields[field]) : null;
      const pairs = (data.pairwiseFlips || []).filter(x => x.condition === c &&
        (!freshSeries || (closedSlot(x.from, c) && closedSlot(x.to, c))));
      document.getElementById('repeat-flips').innerHTML = `${generatedAnyJev && changes?.denominator === 0 ? '<p>No comments had answers in the required format in all three passes; change comparisons are unavailable.</p>' : ids ? `<p><strong>${ids.length} / ${changes.denominator}</strong> comparable comments changed ${field === 'allFour' ? 'at least one decision' : esc(fields[field].toLowerCase())} across the three passes.</p><p class="repeat-case-ids">${ids.length ? ids.map(id => localFresh || data.passOrder ? esc(id) : `<a href="?experiment=${encodeURIComponent(data.configuration)}&amp;run=${encodeURIComponent(data.configuration + (c === 'P0' ? '' : '--' + c.toLowerCase()))}&amp;case=${encodeURIComponent(id)}#inspect">${esc(id)}</a>`).join(' · ') : 'No changed comments.'}</p><p>Comparable means answers met the required format in all three passes. ${changes.excludedIds.length} ${changes.excludedIds.length === 1 ? 'comment was' : 'comments were'} excluded because at least one pass did not.</p>` : '<p>Three-pass changes are unavailable until all passes finish.</p>'}<ul>${pairs.map(x => {if (generatedAnyJev && x.denominator === 0) return `<li>${displayPass(x.from)} to ${displayPass(x.to)}: unavailable (0 comments with answers in the required format in both passes)</li>`; const f = field === 'allFour' ? x.fourFieldVector : nativeL1 ? x.fields[field] : x[field]; const changed = Array.isArray(f) ? f.length : f.changed; return `<li>${displayPass(x.from)} to ${displayPass(x.to)}: ${changed} / ${x.denominator} changed</li>`;}).join('')}</ul>`;
      document.getElementById('repeat-usage-body').innerHTML = conditionOrder.flatMap(c => passes.map(p => {
        if (nativeKev && data.kevSource.passes[p]?.completionStatus === 'interrupted') {
          const phase = data.kevSource.passes[p], u = phase.usage;
          return `<tr><th scope="row">P0</th><td>${displayPass(p)} (interrupted, unscored)</td><td>${phase.outcomes.valid + phase.outcomes.transportErrorUnknownOutcome} attempted<br><small>${phase.outcomes.valid} known responses</small></td><td>${number(u?.inputTokens)}<br><small>Known responses only</small></td><td>${number(u?.outputTokens)}<br><small>Known responses only</small></td><td>${money(phase.knownActualProviderCostUsd)} known<br><small>Unknown charge up to ${money(phase.unknownCostReservationUsd)}; not an observed charge</small></td><td>Unavailable</td><td>${u?.clientRequestSeconds?.total == null ? 'Unavailable' : u.clientRequestSeconds.total.toFixed(1) + ' known responses'}<br><small>${u?.clientRequestSeconds?.unknownAttempt == null ? 'Timeout duration unavailable' : u.clientRequestSeconds.unknownAttempt.toFixed(1) + ' timeout; outcome unknown'}</small></td></tr>`;
        }
        const interrupted = deepseekLowContinuation && p === 'fresh1' && c === 'P2';
        const nativeStop = nativeOpenJev && data.missingPasses.some(item => item.pass === p && item.status === 'stopped');
        const generatedStop = generatedOpenJev && data.missingPasses.some(item => item.pass === p && item.condition === c && item.status === 'stopped_unknown');
        const u = (localFresh || nativeP0 || freshCodex || freshHosted || qwenContinuation || deepseekLowContinuation) && !closed(data.passes[p]?.[c]) ? null : data.passes[p]?.[c]?.usage;
        const elapsed = u?.requestSecondsTotal ?? u?.clientHttpCallSecondsTotal ?? u?.clientRequestSecondsTotal ?? u?.clientPredictionSeconds;
        const nativePositions = nativeL1 && u?.tokens?.input_token_positions != null ? `<br><small>Native input positions: ${number(u.tokens.input_token_positions)} (not billed tokens)</small>` : nativeAlex && u?.nativeNliInputTokenPositions != null ? `<br><small>Native NLI input positions: ${number(u.nativeNliInputTokenPositions)}</small>` : '';
        return `<tr><th scope="row">${c}</th><td>${displayPass(p)}${interrupted || nativeStop || generatedStop ? ' (stopped, unscored)' : data.passes[p]?.[c]?.completionStatus === 'partial' ? ' (partial)' : ''}</td><td>${interrupted ? '49 attempted' : number(u?.startedRequestCount ?? u?.requestCount)}</td><td>${number(u?.tokens?.input_tokens ?? u?.tokens?.prompt_tokens)}${nativePositions}<br><small>Cache read: ${number(u?.tokens?.cache_read_input_tokens ?? u?.tokens?.cached_input_tokens)}<br>Cache write: ${number(u?.tokens?.cache_creation_input_tokens ?? u?.tokens?.cache_write_input_tokens)}</small></td><td>${number(u?.tokens?.output_tokens ?? u?.tokens?.completion_tokens)}<br><small>Reasoning: ${number(u?.tokens?.thinking_tokens ?? u?.tokens?.reasoning_output_tokens)}${u?.providerReasoningTokensAboveCompletionCount ? `<br>Provider reasoning count exceeds output count in ${number(u.providerReasoningTokensAboveCompletionCount)} responses; retained as reported.` : ''}</small></td><td>${interrupted ? 'Partial; see accounting note above' : money(u?.actualCostUsd ?? u?.knownCostUsd)}${qwenUnknownFor(p, c) ? `<br><small>Unknown charge up to ${money(qwenUnknownFor(p, c))}</small>` : u?.unknownCostCount ? ` (${u.unknownCostCount} unknown)` : ''}</td><td>${money(u?.estimatedTokenPriceCostUsd ?? u?.cliListPriceEstimateUsd)}${u?.estimatedTokenPriceCostUsd != null ? '<br><small>Reported input tokens × published price</small>' : u?.cliListPriceEstimateUsd != null ? '<br><small>CLI list-price estimate</small>' : ''}</td><td>${elapsed == null ? (data.passes[p]?.[c] ? 'Unavailable' : 'Not completed') : elapsed.toFixed(1)}</td></tr>`;
      })).join('');
    }
    configControl.addEventListener('change', render);
    fieldControl.addEventListener('change', render);
    conditionControl.addEventListener('change', render);
    render();
  }).catch(() => {root.innerHTML = '<p>Repeat results could not be loaded. <a href="https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/REPEAT_FINDINGS.md">Read the saved repeat report</a>.</p>';});
})();
