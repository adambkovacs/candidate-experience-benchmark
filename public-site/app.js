(() => {
  'use strict';
  const $ = selector => document.querySelector(selector);
  const query=typeof location==='undefined'||typeof URL==='undefined' ? {get:()=>null,has:()=>false} : new URL(location.href).searchParams;
  const requestedCohort=query.get('cohort');
  const initialCohort=['decision','general','all'].includes(requestedCohort) ? requestedCohort : query.has('run') ? 'all' : 'decision';
  const state = {data:null,pricing:null,selectedId:null,experiments:new Map(),pairSelection:new Map(),overviewAll:false,cohort:initialCohort,customCategory:''};
  const optionalPricing = () => {
    const load=Promise.resolve().then(() => fetch('./subscription-price-estimates.json',{cache:'no-store'}))
      .then(response => response.ok ? response.json() : null).catch(() => null);
    if (typeof setTimeout !== 'function') return load;
    let timer;
    const timeout=new Promise(resolve => {timer=setTimeout(() => resolve(null),3000);});
    return Promise.race([load,timeout]).finally(() => clearTimeout(timer));
  };
  const optionalSonnet55 = () => {
    const load=Promise.resolve().then(() => fetch('./sonnet55-fresh-matched3.json',{cache:'no-store'}))
      .then(response => response.ok ? response.json() : null).catch(() => null);
    if (typeof setTimeout !== 'function') return load;
    let timer;
    const timeout=new Promise(resolve => {timer=setTimeout(() => resolve(null),3000);});
    return Promise.race([load,timeout]).finally(() => clearTimeout(timer));
  };
  const optionalClef = () => {
    const load=Promise.resolve().then(() => fetch('./clef-findings.json',{cache:'no-store'}))
      .then(response => response.status===404 ? null : response.ok ? response.json() : {invalidSource:true}).catch(() => ({invalidSource:true}));
    if (typeof setTimeout !== 'function') return load;
    let timer;
    const timeout=new Promise(resolve => {timer=setTimeout(() => resolve({invalidSource:true}),3000);});
    return Promise.race([load,timeout]).finally(() => clearTimeout(timer));
  };
  const optionalDecisionRuns = () => {
    const load = Promise.resolve().then(() => fetch('./supplemental-decision-runs-v1.json', {cache:'no-store'}))
      .then(response => response.ok ? response.json() : null).catch(() => null);
    if (typeof setTimeout !== 'function') return load;
    let timer;
    return Promise.race([load, new Promise(resolve => {timer=setTimeout(() => resolve(null),3000);})])
      .finally(() => clearTimeout(timer));
  };
  const optionalExtendedRuns = () => {
    const load=Promise.resolve().then(()=>fetch('./extended-run-catalog-v1.json',{cache:'no-store'}))
      .then(response=>response.ok ? response.json() : null).catch(()=>null);
    if(typeof setTimeout!=='function') return load;
    let timer;
    return Promise.race([load,new Promise(resolve=>{timer=setTimeout(()=>resolve(null),8000);})])
      .finally(()=>clearTimeout(timer));
  };
  // Required, no timeout: a slow feed must never fall back to a wrong route or cost label.
  const optionalJevFindings = () => Promise.resolve().then(()=>fetch('./jev-native-prompt-findings.json',{cache:'no-store'}))
    .then(response=>response.ok ? response.json() : null).catch(()=>null);
  // Guard for Jev's nine OpenRouter prompt passes. The catalog now carries the OpenRouter surface and the known charge,
  // so this is a no-op; an older catalog gets the route and charge from the findings feed, and if that feed failed,
  // the rows say route and cost unknown rather than repeat a wrong label. Provider stays TypeSafe; the route is the surface.
  function applyJevFindings(runs,findings){
    const usable=findings?.passes&&Array.isArray(findings.sourceBindings)&&
      findings.sourceBindings.some(binding=>/jev-openrouter-native/.test(binding?.path||''));
    for(const run of runs){
      const match=/^extended-typesafe-jev113-native-prompts-(fresh[123])-p([012])$/.exec(run?.id||'');
      if(!match) continue;
      if(n(run.cost?.knownUsd)!==null&&/openrouter/i.test(run.surface||'')) continue;
      const pass=usable ? findings.passes[`P${match[2]}`]?.[match[1]] : null;
      if(n(pass?.knownCostUsd)!==null){
        run.surface='OpenRouter native Choice';
        run.cost={...run.cost,knownUsd:n(pass.knownCostUsd),actualUsd:null,estimatedUsd:null,
          unknownUpperBoundUsd:n(pass.unknownUpperBoundUsd) ?? run.cost?.unknownUpperBoundUsd ?? null};
      } else {
        run.surface='route unknown';
        run.cost={...run.cost,knownUsd:null,actualUsd:null,estimatedUsd:null};
      }
    }
  }
  function extendedCatalogRuns(report,existing=[]){
    const prefix='https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/';
    if(report?.schema!=='extended-run-catalog-v1'||!Number.isInteger(report.runCount)||
      !Array.isArray(report.runs)||report.runs.length!==report.runCount||report.runs.length<1||report.runs.length>2000||
      !report.sourceSha256||typeof report.sourceSha256!=='object'||
      Object.entries(report.sourceSha256).some(([path,hash])=>!path.startsWith('public-site/')||!/^[a-f0-9]{64}$/.test(hash))) return [];
    const seen=new Set(existing.map(run=>run.id));
    const fields=['all_four','sentiment','follow_up_needed','serious_concern_reported','testimonial_potential'];
    for(const run of report.runs){
      const source=typeof run?.sourceRecordsUrl==='string'&&run.sourceRecordsUrl.startsWith(prefix)
        ? run.sourceRecordsUrl.slice(prefix.length) : null;
      if(typeof run?.id!=='string'||!run.id.startsWith('extended-')||seen.has(run.id)||
        typeof run.model!=='string'||!run.model||!['P0','P1','P2'].includes(run.condition)||
        typeof run.experimentId!=='string'||!run.experimentId||
        typeof run.repeatPass!=='string'||!run.repeatPass||
        typeof run.sourceFamily!=='string'||!run.sourceFamily||
        typeof run.sourceStage!=='string'||!run.sourceStage||
        run.sourceOnlyDetails!==true||run.records!==60||
        !Number.isInteger(run.valid)||run.valid<0||run.valid>60||
        (run.savedResponses!==null&&(!Number.isInteger(run.savedResponses)||run.savedResponses<run.valid||run.savedResponses>60))||
        typeof run.complete!=='boolean'||
        fields.some(field=>!Number.isInteger(run.metrics?.[field])||run.metrics[field]<0||run.metrics[field]>run.valid)||
        !source||report.sourceSha256[source]!==run.sourceRecordSha256||
        typeof run.evidenceUrl!=='string'||!run.evidenceUrl.startsWith(prefix)||
        !run.timing||!run.tokens||!run.cost) return [];
      seen.add(run.id);
    }
    return report.runs;
  }
  function supplementalDecisionRuns(report, existing = []) {
    if (report?.schema !== 'supplemental-decision-runs-v1' || report.denominator !== 60 ||
        !Array.isArray(report.runs) || report.runs.length < 27 || report.runs.length > 63 ||
        !Array.isArray(report.sources) || !report.sources.length ||
        report.sources.some(s => typeof s.path !== 'string' || !/^[a-f0-9]{64}$/.test(s.sha256 || ''))) return [];
    const seen = new Set(existing.map(r => r.id));
    const fields = ['all_four','sentiment','follow_up_needed','serious_concern_reported','testimonial_potential'];
    const historical = ['solar-decide','liquid-d1','tev1-4b'];
    const openRouterModels = {'clef-openrouter':['cloudflare/clef','cloudflare/clef','Cloudflare'],
      'clef-flash-openrouter':['cloudflare/clef-flash','cloudflare/clef-flash','Cloudflare'],
      'luna-decisions-openrouter':['openai/gpt-6-luna-decisions','openai/gpt-6-luna-decisions-20261006','OpenAI'],
      'perplexity-decider':['perplexity/pplx-decider-v1-27b','perplexity/pplx-decider-v1-27b-20261001','Perplexity']};
    for (const run of report.runs) {
      const match = /^(solar-decide|liquid-d1|tev1-4b|clef-openrouter|clef-flash-openrouter|luna-decisions-openrouter|perplexity-decider)-native-fresh([123])-p([012])$/.exec(run?.id || '');
      const interrupted = run.id === 'solar-decide-native-fresh3-p2' ||
        run.id === 'clef-flash-openrouter-native-fresh3-p2';
      const expectedValid = run.id === 'solar-decide-native-fresh3-p2' ? 59 :
        run.id === 'clef-flash-openrouter-native-fresh3-p2' ? 59 : 60;
      if (!match || seen.has(run.id) || run.condition !== `P${match[3]}` ||
          run.repeatPass !== `fresh${match[2]}` ||
          run.experimentId !== `${match[1]}-native-fresh${match[2]}-p0` ||
          run.parentBaselineId !== (match[3] === '0' ? null : run.experimentId) ||
          run.complete !== !interrupted || run.records !== 60 || run.valid !== expectedValid || run.savedResponses !== expectedValid ||
          run.pairedEligible !== !interrupted ||
          run.tokens?.reportedRequests !== run.valid || run.tokens?.totalRequests !== 60 ||
          run.tokens?.complete !== !interrupted ||
          typeof run.model !== 'string' || !run.model || typeof run.surface !== 'string' ||
          fields.some(f => !Number.isInteger(run.metrics?.[f]) || run.metrics[f] < 0 || run.metrics[f] > 60) ||
          !Number.isInteger(run.tokens?.input) || run.tokens.input < 0 ||
          !Number.isInteger(run.tokens?.output) || run.tokens.output < 0 ||
          !Number.isFinite(run.cost?.knownUsd) || run.cost.knownUsd < 0 ||
          run.timing?.inferenceSeconds !== null || run.sourceOnlyDetails !== true ||
          !url(run.sourceRecordsUrl) || !url(run.evidenceUrl) ||
          !/^[a-f0-9]{64}$/.test(run.sourceRecordSha256 || '')) return [];
      if (openRouterModels[match[1]]) {
        const [model, returned, provider] = openRouterModels[match[1]];
        const noPublicTiming = match[1] === 'perplexity-decider';
        if (run.model !== model || run.returnedModel !== returned || run.provider !== provider ||
            run.surface !== 'OpenRouter native Choice' ||
            run.protocolId !== `${match[1]}-native-choice-v1` ||
            run.cost?.unknownUpperBoundUsd !== (interrupted ? 0.02359296 : 0) ||
            run.cost?.actualUsd !== null ||
            (noPublicTiming ? run.timing?.requests !== 0 || run.timing?.totalSeconds !== null :
              run.timing?.requests !== expectedValid || !Number.isFinite(run.timing?.totalSeconds))) return [];
      }
      seen.add(run.id);
    }
    for (const family of historical) for (const pass of [1,2,3]) for (const prompt of [0,1,2]) {
      if (!seen.has(`${family}-native-fresh${pass}-p${prompt}`)) return [];
    }
    if (report.runs.some(run => run.id.startsWith('perplexity-decider-native-'))) {
      for (const pass of [1,2,3]) for (const prompt of [0,1,2]) {
        if (!seen.has(`perplexity-decider-native-fresh${pass}-p${prompt}`)) return [];
      }
    }
    return report.runs;
  }
  const esc = value => String(value ?? '').replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const n = value => value === null || value === undefined || value === '' || !Number.isFinite(Number(value)) ? null : Number(value);
  const count = value => n(value) === null ? 'Unknown' : Math.round(n(value)).toLocaleString('en-US');
  // ponytail: site/labels.js owns readable names and money; this fallback only runs in node tests that skip it.
  const usd4 = value => `$${Number(value).toLocaleString('en-US',{minimumFractionDigits:4,maximumFractionDigits:4})}`;
  const LBL = () => globalThis.BM_LABEL || {run:r => [r?.model,r?.effort,r?.surface].filter(Boolean).join(', '),usd:usd4};
  const money = value => n(value) === null ? 'Unknown' : LBL().usd(n(value));
  const duration = value => n(value) === null ? 'Unknown' : n(value) >= 60 ? (n(value)/60).toLocaleString(undefined,{maximumFractionDigits:1})+' min' : n(value).toLocaleString(undefined,{maximumFractionDigits:1})+' sec';
  const url = value => {try {const parsed = new URL(value);return ['https:','http:'].includes(parsed.protocol) ? parsed.href : null;} catch {return null;}};
  const has = value => n(value) !== null;
  const complete = run => run.complete === true && n(run.records) === 60;
  const localRun = run => run.surface === 'Local / specialist' || /^Local\b/i.test(run.surface || '') || run.provider === 'local';
  const savedResponses = run => run.sourceFamily ? run.savedResponses : run.savedResponses ?? run.records;
  const missing = run => n(savedResponses(run)) === null ? 'Unknown' : count(Math.max(0, 60 - n(savedResponses(run))));
  const savedSummary = run => has(savedResponses(run)) ? `${count(savedResponses(run))} / 60 saved` : 'saved count not recorded';
  const missingSummary = run => has(savedResponses(run)) ? `, ${missing(run)} without a saved response` : '';
  const savedTag = run => has(savedResponses(run)) ? `${count(savedResponses(run))} of 60 saved` : 'Saved count not recorded';
  const missingTag = run => has(savedResponses(run)) ? `, ${missing(run)} without a saved answer` : '';
  const tallyNote = run => complete(run) ? '' : has(savedResponses(run))
    ? `Partial tally: ${count(savedResponses(run))} of 60 saved, ${missing(run)} without a saved response; not a final score.`
    : 'Partial tally with no saved count; not a final score.';
  const metricName = {all_four:'All four match',sentiment:'Sentiment matches',follow_up_needed:'Follow-up matches',serious_concern_reported:'Serious concern matches',testimonial_potential:'Testimonial matches',valid:'Valid responses'};
  const score = run => $('#metric').value === 'valid' ? run.valid : run.metrics?.[$('#metric').value];
  const inferenceTime = timing => n(timing?.inferenceSeconds) !== null && n(timing?.inferenceReportedRequests) > 0 ? duration(timing.inferenceSeconds) : 'Unknown';
  const observedCost = cost => n(cost?.actualUsd) !== null ? money(cost.actualUsd) : n(cost?.knownUsd) !== null ? money(cost.knownUsd) : 'Unknown';
  const priceEntry = run => {
    if (run.cost?.estimateKind === 'published_input_rate') return null;
    const entry=state.pricing?.runs?.[run.id];
    return entry?.model === run.model ? entry : null;
  };
  const runCost = run => priceEntry(run) ? {...run.cost,estimatedUsd:priceEntry(run).estimateUsd} : run.cost || {};
  const runTokens = run => {
    const entry=priceEntry(run),tokens=run.tokens || {};
    if (!entry?.tokens) return tokens;
    return {...tokens,input:entry.tokens.input,output:entry.tokens.output,
      cachedInput:entry.tokens.cacheRead,cacheWrite:entry.tokens.cacheWrite,
      reasoning:entry.tokens.reasoningOutput,complete:entry.usageStatus === 'complete'};
  };
  const costSummary = run => {
    const cost=runCost(run),price=priceEntry(run);
    // ponytail: the figure only; the page states the † basis once.
    const charge=n(cost?.actualUsd) ?? n(cost?.knownUsd);
    if (charge !== null) return money(charge);
    // Jev's TypeSafe route sends no bill; its OpenRouter price belongs to the OpenRouter row.
    if (run.id === 'typesafe-jev113-v2') return 'no bill';
    if (n(price?.estimateUsd) !== null) return money(price.estimateUsd)+'†';
    if (n(cost?.estimatedUsd) !== null) return money(cost.estimatedUsd)+'†'+(cost.estimateKind === 'known_usage_only' ? ' for known usage' : '');
    return 'Cost unknown';
  };
  const providerGenerationTime = timing => n(timing?.providerGenerationSeconds) !== null && n(timing?.providerGenerationReportedRequests) > 0 ? duration(timing.providerGenerationSeconds) : null;
  const experimentId = run => run.parentBaselineId || run.id.replace(/--p[12]$/i,'');
  const effortText = run => run.effort && run.effort !== 'not applicable' ? run.effort : null;
  const passText = run => {const pass=/(?:fresh|pass)(\d)/.exec(run.repeatPass || '');return pass ? `pass ${pass[1]}` : null;};
  const label = run => LBL().run(run);
  const runOptionText = run => [label(run),[run.condition,passText(run)].filter(Boolean).join(' '),complete(run) ? null : 'partial'].filter(Boolean).join(', ');
  // ponytail: the run id only disambiguates option texts that would otherwise repeat
  const runOptions = runs => {
    // Repeated labels get a plain variant number, never the run id.
    const texts=runs.map(runOptionText),seen=texts.reduce((m,t) => m.set(t,(m.get(t) || 0)+1),new Map()),nth=new Map();
    return runs.map((run,i) => {
      const t=texts[i],k=(nth.get(t) || 0)+1;
      nth.set(t,k);
      return `<option value="${esc(run.id)}">${esc(seen.get(t) > 1 ? `${t}, variant ${k}` : t)}</option>`;
    }).join('');
  };
  const modelType = item => globalThis.BenchmarkCategories?.classify(item) || {category:'unknown',categories:['unknown'],categoryLabel:'Category not verified',trainingLineage:'unknown',trainingLabel:'Training not verified',interfaceKind:'unknown',interfaceLabel:'Interface not verified'};
  const hostedPair = id => (state.data.promptComparisons || []).find(item => item.id === id && item.kind === 'hosted-observational' && item.eligible === false);
  const comparisonNote = run => run.id === 'solar-decide-native-fresh3-p2' ? '<p class="note">Prompt comparisons for this run use 59 shared answers, leaving out DEV-009. Its score still counts all 60 reviews.</p>' : run.nativeInstructionComparison ? '<p class="note">Native Jev instruction comparison. P0 ran earlier, in one pass.</p>' : hostedPair(experimentId(run)) ? '<p class="note">Part of the hosted prompt comparison, one pass per prompt version.</p>' : run.pairedEligible === false ? '<p class="note">This run sits outside the record-by-record prompt comparison.</p>' : '';
  const dataRow = (name,value) => `<div><dt>${esc(name)}</dt><dd>${esc(value === null || value === undefined || value === '' ? 'Not recorded' : value)}</dd></div>`;
  function sonnet55FirstPassRuns(report) {
    const efforts=['low','medium','high','xhigh'],conditions=['P0','P1','P2'];
    if (report?.schema !== 'claude-sonnet55-fresh-matched3-findings-v1' || report.model !== 'claude-sonnet-5-5' || report.plannedCells !== 36 || report.denominatorPerCell !== 60 ||
        JSON.stringify(report.efforts) !== JSON.stringify(efforts) || JSON.stringify(report.passOrder) !== JSON.stringify(['pass1','pass2','pass3']) || JSON.stringify(report.conditionOrder) !== JSON.stringify(conditions)) return [];
    const evidenceUrl='https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/sonnet55-fresh-matched3.json';
    return efforts.flatMap(effort => conditions.flatMap(condition => {
      const dev=report.cells?.[effort]?.pass1?.[condition]?.development;
      const score=dev?.score,usage=dev?.usage;
      if (dev?.state !== 'complete' || dev.recordCount !== 60 || score?.denominator !== 60 || !Number.isInteger(score.valid) || score.valid < 0 || score.valid > 60 || score.outcomes?.valid !== score.valid ||
          Object.values(score.outcomes).reduce((total,value)=>total+value,0) !== 60 ||
          !usage || !dev.evidence?.records?.path || !/^[0-9a-f]{64}$/.test(dev.evidence.records.sha256 || '')) return [];
      const times=Array.isArray(usage.requestSeconds) ? usage.requestSeconds.filter(value=>typeof value==='number' && Number.isFinite(value)).sort((a,b)=>a-b) : [];
      const median=times.length ? (times[Math.floor((times.length-1)/2)]+times[Math.ceil((times.length-1)/2)])/2 : null;
      const p95=times.length ? times[Math.ceil(times.length*.95)-1] : null;
      const totalRequests=Number.isInteger(usage.requestCount) && usage.requestCount >= 0 ? usage.requestCount : null;
      const unpricedRequests=Number.isInteger(usage.unpricedRequests) && usage.unpricedRequests >= 0 && usage.unpricedRequests <= totalRequests ? usage.unpricedRequests : null;
      const pricedRequests=totalRequests === null || unpricedRequests === null ? null : totalRequests-unpricedRequests;
      const partialUsage=pricedRequests !== null && pricedRequests < totalRequests;
      const estimate=partialUsage || pricedRequests === null ? null : usage.calculatedApiEquivalentUsd ?? usage.cliListPriceEstimateUsd ?? null;
      const configuration=`sonnet55-${effort}-fresh-matched3-batch10-v2`;
      const id=`${configuration}--pass1-${condition.toLowerCase()}`;
      const recordPath=`results/repeatability-v1/claude-sonnet55-fresh-matched3-v2/${effort}/pass1/${condition}/development.records.jsonl`;
      const exportedPath=`public-site/sonnet55-fresh-matched3-evidence/evidence/${recordPath}`;
      const sourceRecordsUrl=[recordPath,exportedPath,exportedPath.slice('public-site/'.length)].includes(dev.evidence.records.path)
        ? `https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/${exportedPath}` : null;
      return [{id,parentBaselineId:condition==='P0' ? null : `${configuration}--pass1-p0`,model:'claude-sonnet-5-5',effort,surface:'Claude subscription',condition,
        complete:true,records:60,valid:score.valid,metrics:{all_four:score.allFour,...score.fields},pairedEligible:true,
        resultStatus:'Pass 1 of a three-pass study at this effort.',
        timing:{kind:'batch',requests:usage.requestCount,medianSeconds:median,p95Seconds:p95,totalSeconds:usage.requestSecondsTotal,inferenceSeconds:null,line:''},
        tokens:{input:pricedRequests > 0 ? usage.tokens?.input_tokens ?? null : null,cachedInput:pricedRequests > 0 ? usage.tokens?.cache_read_input_tokens ?? null : null,cacheWrite:pricedRequests > 0 ? usage.tokens?.cache_creation_input_tokens ?? null : null,output:pricedRequests > 0 ? usage.tokens?.output_tokens ?? null : null,reasoning:pricedRequests > 0 ? usage.tokens?.thinking_tokens ?? null : null,reportedRequests:pricedRequests,totalRequests,complete:pricedRequests !== null && pricedRequests === totalRequests},
        cost:{actualUsd:null,estimatedUsd:estimate,
          estimateKind:partialUsage || pricedRequests === null ? 'usage_unavailable' : usage.calculatedApiEquivalentUsd != null ? 'calculated_api_equivalent' : 'cli_list_price',sourceUrl:usage.priceSource || report.pricing?.source || null,
          line:partialUsage ? `${pricedRequests} of ${totalRequests} requests reported usage, so the run has no full API-rate price.` : ''},
        sourceOnlyDetails:true,sourceRecordsUrl,evidenceUrl}];
    }));
  }
  function clefFirstPassRuns(report) {
    const names=['clef','clef-flash'],fields=['sentiment','follow_up_needed','serious_concern_reported','testimonial_potential'];
    const paired=report?.paired?.allFour;
    if (report?.schema!=='clef-native-p0-findings-v1' || report.cohort?.records!==60 || report.cohort?.pass!=='fresh1' || report.cohort?.condition!=='P0' ||
        report.cohort?.configurationCount!==2 || report.cohort?.fullPassesPerModelCompleted!==1 || !report.models || !report.sourceSha256 ||
        names.some(name=>!report.models[name]) || !Number.isInteger(report.paired?.predictionVectorDisagreementCount) ||
        report.paired.predictionVectorDisagreementCount<0 || report.paired.predictionVectorDisagreementCount>60 ||
        !paired || Object.values(paired).length!==4 || Object.values(paired).some(value=>!Number.isInteger(value) || value<0) ||
        Object.values(paired).reduce((sum,value)=>sum+value,0)!==60 ||
        report.models.clef.allFourCorrect!==paired.correct_correct+paired.correct_incorrect ||
        report.models['clef-flash'].allFourCorrect!==paired.correct_correct+paired.incorrect_correct) return [];
    const source='https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/';
    const runs=[];
    for (const name of names) {
      const item=report.models[name],path=`results/clef-native-v1/${name}/fresh1/P0/development/records.jsonl`;
      const completion=`results/clef-native-v1/${name}/fresh1/P0/development/completion.json`;
      const price=item.publishedInputPriceEstimateUsd,hold=item.unknownCostReservedUsd;
      if (item.stage!=='fresh1/P0/development' || item.records!==60 || item.valid!==60 || item.failed!==0 || item.neverSent!==0 ||
          !Number.isInteger(item.allFourCorrect) || item.allFourCorrect<0 || item.allFourCorrect>60 ||
          fields.some(field=>!Number.isInteger(item.fields?.[field]?.correct) || item.fields[field].correct<0 || item.fields[field].correct>60) ||
          !Number.isInteger(item.observedInputTokens) || item.observedInputTokens<0 || !Number.isInteger(item.observedOutputTokens) || item.observedOutputTokens<0 ||
          !/^\d+(?:\.\d+)?$/.test(price) || !/^\d+(?:\.\d+)?$/.test(hold) || item.providerBilledUsd!==null ||
          !/^[0-9a-f]{64}$/.test(report.sourceSha256[path] || '') || !/^[0-9a-f]{64}$/.test(report.sourceSha256[completion] || '')) return [];
      runs.push({id:`${name}-native-fresh1-p0`,model:name==='clef'?'Cloudflare Clef':'Cloudflare Clef Flash',effort:'not applicable',surface:'Cloudflare Workers AI',condition:'P0',
        complete:true,records:60,valid:item.valid,metrics:{all_four:item.allFourCorrect,...Object.fromEntries(fields.map(field=>[field,item.fields[field].correct]))},
        pairedEligible:false,resultStatus:'First P0 pass on the direct Cloudflare Workers AI route, run before the OpenRouter passes.',
        timing:{kind:'connected-app',requests:60,inferenceSeconds:null,inferenceReportedRequests:0,line:'Elapsed time includes an operator passing requests through a connected app.'},
        tokens:{input:item.observedInputTokens,output:item.observedOutputTokens,reportedRequests:60,totalRequests:60,complete:true},
        cost:{actualUsd:null,knownUsd:null,estimatedUsd:Number(price),estimateKind:'published_input_rate',unknownUpperBoundUsd:Number(hold),
          sourceUrl:`https://developers.cloudflare.com/workers-ai/models/${name}/`,line:''},
        sourceOnlyDetails:true,sourceRecordsUrl:source+path,evidenceUrl:source+'public-site/clef-findings.json',sourceRecordSha256:report.sourceSha256[path]});
    }
    return runs;
  }
  function renderClefFirstPass(runs,report,openRouterScore) {
    const target=$('#clef-first-pass-results');if(!target)return;
    if (runs.length!==2) {target.innerHTML='<p class="empty-state">The Clef first-pass results did not load.</p>';return;}
    const fields=[['Sentiment','sentiment'],['Follow-up','follow_up_needed'],['Serious concern','serious_concern_reported'],['Testimonial','testimonial_potential']];
    target.innerHTML=`<div class="clef-comparison">${runs.map(run=>`<article class="clef-model-card"><h3>${esc(run.model)}</h3><p class="clef-major"><strong>${run.metrics.all_four}<small>/60</small></strong><span>reviews with all four decisions matching the reference</span></p><p>${run.valid} of 60 answers in the required format, ${count(run.tokens.input)} input and ${count(run.tokens.output)} output tokens.</p><dl>${fields.map(([label,key])=>`<div><dt>${label}</dt><dd><meter min="0" max="60" value="${run.metrics[key]}" aria-label="${esc(run.model)} ${label}: ${run.metrics[key]} of 60 match">${run.metrics[key]} of 60</meter><strong>${run.metrics[key]}/60</strong></dd></div>`).join('')}</dl><p class="clef-cost"><strong data-source="clef-findings.json#models.${run.id.startsWith('clef-flash') ? 'clef-flash' : 'clef'}.publishedInputPriceEstimateUsd">${money(run.cost.estimatedUsd)}†</strong> for the pass.</p></article>`).join('')}</div><p class="clef-paired">The two models disagreed on at least one label for <strong data-source="clef-findings.json#paired.predictionVectorDisagreementCount">${esc(report.paired.predictionVectorDisagreementCount)}</strong> of 60 reviews. Both ran one plain-prompt pass on Cloudflare's direct route, which sends no bill, so these costs are the published price for the same ${runs[0].tokens.input === runs[1].tokens.input ? `<span data-source="clef-findings.json#models.clef.observedInputTokens">${esc(count(runs[0].tokens.input))}</span> ` : ''}input tokens. OpenRouter charged exactly that for the passes in the results table${Number.isInteger(openRouterScore) ? `, where Clef matched <span data-source="supplemental-decision-runs-v1.json#runs[id=clef-openrouter-native-fresh1-p0].metrics.all_four">${openRouterScore}</span>` : ''}.</p>`;
  }
  function groups() {
    state.experiments = new Map();
    for (const run of state.data.runs) {
      const id = experimentId(run);
      if (!state.experiments.has(id)) state.experiments.set(id,[]);
      state.experiments.get(id).push(run);
    }
  }
  function renderExperimentSelect() {
    const select = $('#experiment-select');
    const entries = [...state.experiments.entries()].sort((a,b) => {
      const aj = a[0].includes('typesafe-jev113') ? 0 : 1;
      const bj = b[0].includes('typesafe-jev113') ? 0 : 1;
      return aj-bj || label(a[1][0]).localeCompare(label(b[1][0]));
    });
    const optionText = ([,runs]) => {const lead=runs.find(r => r.condition === 'P0') || runs[0];return [label(lead),[lead.condition,passText(lead)].filter(Boolean).join(' ')].filter(Boolean).join(', ');};
    const seen = entries.reduce((m,e) => m.set(optionText(e),(m.get(optionText(e)) || 0)+1),new Map());
    // ponytail: the raw id only disambiguates labels that would otherwise repeat
    select.innerHTML = entries.map(([id,runs]) => `<option value="${esc(id)}">${esc(optionText([id,runs]))}${seen.get(optionText([id,runs])) > 1 ? ` (${esc(id)})` : ''}</option>`).join('');
    const queryExperiment=new URL(location.href).searchParams.get('experiment');
    select.value = queryExperiment && state.experiments.has(queryExperiment) ? queryExperiment : entries[0]?.[0] || '';
  }
  function renderModelSelect() {
    const select=$('#compare-run-select');
    const query=$('#compare-search').value.trim().toLowerCase();
    const matches=state.data.runs.filter(r=>complete(r) && r.id !== 'typesafe-jev113-v2' && (!query || `${r.model} ${r.id} ${r.effort} ${r.surface}`.toLowerCase().includes(query))).sort((a,b)=>label(a).localeCompare(label(b)) || a.condition.localeCompare(b.condition));
    select.innerHTML='<option value="">Second run</option>'+runOptions(matches);
    select.value=matches.some(r=>r.id===state.selectedId) ? state.selectedId : '';
  }
  function renderSectionRunPickers() {
    const runs=[...state.data.runs].sort((a,b)=>label(a).localeCompare(label(b)) || a.condition.localeCompare(b.condition) || a.id.localeCompare(b.id));
    const options=runOptions(runs);
    for(const selector of ['#usage-run-select','#inspect-run-select']) {
      const select=$(selector);
      if(!select)continue;
      select.innerHTML=options;
      select.value=state.selectedId || '';
    }
  }
  function missingCondition(id,condition) {
    if (id === 'typesafe-jev113-v2') return {label:'NO SAVED RESULT',reason:'No saved result for this native Jev instruction version.'};
    const historicalPairs={
      'sonnet5-low-first-pass':'sonnet5-low-first-pass-phase2-batch10-p0',
      'sonnet5-low-with-retry':'sonnet5-low-first-pass-phase2-batch10-p0',
      'sonnet5-medium':'sonnet5-medium-phase2-batch10-p0',
      'sonnet5-high':'sonnet5-high-phase2-batch10-p0',
      'sonnet5-xhigh':'sonnet5-xhigh-phase2-batch10-p0',
      'opus5-low':'opus5-low-phase2-batch10-p0',
      'opus5-medium':'opus5-medium-phase2-batch10-p0',
      'opus5-high':'opus5-high-phase2-batch10-p0',
      'opus5-xhigh':'opus5-xhigh-phase2-batch10-p0',
      'fable51-low':'fable51-low-phase2-batch10-p0',
      'fable51-medium':'fable51-medium-phase2-batch10-p0',
      'fable51-high':'fable51-high-phase2-batch10-p0',
      'fable51-xhigh':'fable51-xhigh-phase2-batch10-p0',
      'codex-gpt-5.6-luna-low':'codex-gpt-5.6-luna-low-phase2-batch10-p0',
      'codex-gpt-6-astra-low':'codex-gpt-6-astra-low-phase2-batch10-p0'
    };
    const pairedId=historicalPairs[id];
    if (pairedId && state.data.runs.some(run=>run.id===pairedId && run.condition==='P0')) {
      const repeatDoc=id.startsWith('codex-') ? 'CODEX_REPEAT_SYNTHESIS_2026-09-28.md' : id.startsWith('fable51-') ? 'FABLE_REPEAT_FINDINGS_2026-09-28.md' : id.startsWith('opus5-') ? 'OPUS5_REPEAT_FINDINGS_2026-09-28.md' : 'SONNET5_REPEAT_FINDINGS_2026-09-28.md';
      return {label:'NO MATCHED RUN',reason:`This earlier P0 classified one comment per request. It has no ${condition} run with the same controls. A later batch-of-10 setup has separate P0, P1 and P2 runs, with three passes per version.`,links:[
        {href:`?experiment=${encodeURIComponent(pairedId)}&run=${encodeURIComponent(pairedId)}#explore`,text:'The batch-of-10 prompt series →'},
        {href:`https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/${repeatDoc}`,text:'Repeat findings ↗'}
      ]};
    }
    if (id === 'haiku45-not_applicable') return {label:'NO MATCHED RUN',reason:`This earlier P0 classified one comment per request. It has no ${condition} run with the same controls. The later batch attempt retained ten P1 transport failures; a separate fresh matched-three P0/P1/P2 series is complete.`,links:[
      {href:'https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/CLAUDE_HAIKU_MATCHED3.md',text:'Haiku three-pass study ↗'},
      {href:'https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/public-site/haiku-fresh-matched3.json',text:'Its nine completed passes ↗'}
    ]};
    const blockedAfterP0=new Set([
      'antigravity-gemini-3.1-pro-low-native-observed-batch10',
      'antigravity-gemini-3.1-pro-high-native-observed-batch10',
      'antigravity-gemini-3.6-flash-low-native-observed-batch10',
      'antigravity-gemini-3.6-flash-medium-native-observed-batch10',
      'antigravity-gemini-3.7-flash-low-native-observed-batch10',
      'antigravity-gemini-3.7-flash-medium-native-observed-batch10',
      'antigravity-gemini-3.7-flash-high-native-observed-batch10'
    ]);
    if (blockedAfterP0.has(id)) return {label:'Blocked after P0',reason:id.includes('3.1-pro-low') && condition==='P1' ? 'P1 has a separate partial attempt: 40 valid responses, 10 service errors and 10 unattempted comments. There is no complete public P1 run.' : `No complete public ${condition} run followed this Antigravity P0. The native route was blocked; OpenRouter results are separate configurations.`,links:[
      {href:'https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/PROMPT_COVERAGE_AUDIT_2026-10-02.md',text:'Coverage audit ↗'}
    ]};
    const roster=state.data.roster || [];
    const item=roster.find(r => r.id===id || r.parentBaselineId===id);
    if (item) return {label:item.disposition==='excluded' ? 'Not applicable' : (item.disposition ? String(item.disposition).replace(/_/g,' ').replace(/^./,c=>c.toUpperCase()) : 'No saved outcome'),reason:item.reason || 'No saved outcome.'};
    return {label:'No saved outcome',reason:'No saved result for this prompt.'};
  }
  function syncUrl() {
    const params=new URL(location.href).searchParams;
    const experiment=$('#experiment-select').value,metric=$('#metric').value;
    if(experiment)params.set('experiment',experiment);else params.delete('experiment');
    if(state.selectedId)params.set('run',state.selectedId);else params.delete('run');
    if(metric!=='all_four')params.set('metric',metric);else params.delete('metric');
    history.replaceState(null,'',location.pathname+(params.size?'?'+params.toString():'')+location.hash);
  }
  function renderOverview() {
    const condition=$('#overview-condition').value;
    const route=$('#overview-surface').value;
    const category=state.customCategory || (state.cohort==='all' ? '' : state.cohort);
    const runs=state.data.runs.filter(r=>r.condition===condition && complete(r) && n(r.metrics?.all_four)!==null && (!category || modelType(r).categories.includes(category)) && (route==='all' || (route==='local' ? localRun(r) : !localRun(r)))).sort((a,b)=>n(b.metrics.all_four)-n(a.metrics.all_four) || label(a).localeCompare(label(b)) || a.id.localeCompare(b.id));
    // ponytail: repeat passes of one setup differ only by the fresh/pass/repeat digit in the run id
    const setupKey=run=>run.id.replace(/(fresh|pass|repeat)\d/i,'$1N');
    const passNo=run=>Number(/(?:fresh|pass|repeat)(\d)/i.exec(run.repeatPass || run.id)?.[1] || 0);
    const setups=[...runs.reduce((map,run)=>map.set(setupKey(run),[...(map.get(setupKey(run)) || []),run]),new Map()).values()]
      .map(setup=>setup.sort((a,b)=>passNo(a)-passNo(b)))
      .sort((a,b)=>n(b[0].metrics.all_four)-n(a[0].metrics.all_four) || label(a[0]).localeCompare(label(b[0])) || a[0].id.localeCompare(b[0].id));
    const visible=state.overviewAll ? setups : setups.slice(0,8);
    const jev=setups.find(setup=>setup.some(r=>r.id==='typesafe-jev113-v2' || r.nativeInstructionComparison === true));
    const fallback=state.data.runs.find(r=>r.id==='typesafe-jev113-v2');
    const reference=route==='local' ? null : !state.overviewAll && jev && !visible.includes(jev) ? jev : !state.overviewAll && !jev && fallback && (!category || modelType(fallback).categories.includes(category)) ? [fallback] : null;
    const row=(setup,referenceRow=false)=>{
      const run=setup[0];
      const passes=setup.length>1 ? `${setup.length} passes: ${setup.map(r=>r.metrics.all_four).join(', ')}` : passText(run);
      const validText=has(run.valid) ? `${count(run.valid)} / 60 answers in the required format` : 'Format count not recorded';
      return `<button type="button" class="overview-row${run.id===state.selectedId?' selected':''}${referenceRow?' reference':''}" data-overview-run="${esc(run.id)}" aria-label="Inspect ${esc(label(run))}, ${esc(run.condition)}, ${esc(run.metrics?.all_four)} of 60 matches, ${esc(validText)}"><span class="overview-row-name"><strong>${esc(label(run))}</strong><code>${esc(run.model)}</code><small>${esc([run.condition,passes].filter(Boolean).join(setup.length>1 ? ', ' : ' '))}</small></span><span class="overview-row-track" aria-hidden="true"><span style="width:${Math.max(0,Math.min(100,n(run.metrics.all_four)/60*100))}%"></span></span><strong class="overview-row-score">${esc(run.metrics.all_four)} / 60</strong><small class="overview-row-cost">${esc(validText)}, ${esc(costSummary(run))}</small></button>`;
    };
    const extra=reference && !visible.includes(reference) ? row(reference,true) : '';
    const routeLabel=route==='local' ? 'local ' : route==='hosted' ? 'hosted / API ' : '';
    const cohortLabel=category ? `${String(globalThis.BenchmarkCategories?.categories?.[category]||category).toLowerCase()} ` : '';
    $('#overview-count').textContent=`${visible.length} of ${setups.length} complete ${routeLabel}${cohortLabel}${condition} setups shown${extra ? reference[0].condition === condition ? ', plus Jev' : ', plus Jev P0' : ''}.`;
    $('#overview-rows').innerHTML=visible.map(setup=>row(setup)).join('')+extra || '<p class="empty-state">No complete runs match these settings.</p>';
    $('#overview-rows').querySelectorAll('[data-overview-run]').forEach(button=>button.addEventListener('click',()=>selectRun(button.dataset.overviewRun,true)));
    const toggle=$('#overview-toggle');toggle.hidden=setups.length<=8;toggle.textContent=state.overviewAll?'Show first eight':'Show all setups';toggle.setAttribute('aria-expanded',String(state.overviewAll));
  }
  function renderExperiment() {
    const id = $('#experiment-select').value;
    if(state.selectedId)syncUrl();
    const runs = state.experiments.get(id) || [];
    const lead = runs.find(r => r.condition === 'P0') || runs[0];
    $('#experiment-title').textContent = lead ? label(lead) : 'No saved result for this setup';
    $('#experiment-context').textContent = lead ? [lead.condition,passText(lead)].filter(Boolean).join(' ') : '';
    const chosen = $('#metric').value;
    $('#condition-grid').innerHTML = ['P0','P1','P2'].map(condition => {
      const candidates = runs.filter(r => r.condition === condition);
      const run = candidates.find(complete) || candidates[0];
      if (!run) {
        const disposition=missingCondition(id,condition);
        const links=(disposition.links || []).map(link=>`<a class="condition-related-link" href="${esc(link.href)}"${link.href.startsWith('http') ? ' target="_blank" rel="noopener noreferrer"' : ''}>${esc(link.text)}</a>`).join('');
        return `<div class="condition-card empty"><div class="condition-card-header"><span class="condition-code">${condition}</span><span class="condition-tag">${esc(disposition.label)}</span></div><p class="condition-meta">${esc(disposition.reason)}</p>${links}</div>`;
      }
      const value = score(run);
      const status = complete(run) ? 'Complete' : 'Partial';
      return `<button type="button" class="condition-card" data-condition-run="${esc(run.id)}" aria-pressed="${run.id === state.selectedId}"><span class="condition-card-header"><span class="condition-code">${condition}</span><span class="condition-tag">${status}, ${esc(savedTag(run))}${complete(run) ? '' : esc(missingTag(run))}</span></span><span class="condition-score">${has(value) ? esc(value) : '—'}<small> / 60</small></span><span class="condition-track" aria-hidden="true"><span style="width:${has(value) ? Math.max(0,Math.min(100,n(value)/60*100)) : 0}%"></span></span><span class="condition-meta">${esc(metricName[chosen])}${complete(run) ? '' : ', no final score'}${passText(run) ? `, ${esc(passText(run))}` : ''}</span></button>`;
    }).join('');
    $('#condition-grid').querySelectorAll('[data-condition-run]').forEach(button => button.addEventListener('click',() => selectRun(button.dataset.conditionRun,true)));
    const nonpaired = runs.some(r => r.pairedEligible === false);
    $('#experiment-note').textContent = id === 'typesafe-jev113-v2' ? `${runs.length} saved ${runs.length === 1 ? 'run' : 'runs'} for Jev. Its instruction versions rewrite the native Choice questions. P0 ran earlier, in one pass.` : hostedPair(id) ? `${runs.length} saved ${runs.length === 1 ? 'run' : 'runs'}, one per prompt version.` : `${runs.length} saved ${runs.length === 1 ? 'run' : 'runs'} for this setup.${nonpaired ? ' Some sit outside the record-by-record prompt comparison.' : ''}`;
    renderAuditedComparison(id);
  }
  function renderAuditedComparison(id) {
    let panel = $('#audited-comparison');
    if (!panel) {
      panel = document.createElement('section');
      panel.id = 'audited-comparison';
      panel.className = 'audited-comparison';
      panel.setAttribute('aria-label','Recorded prompt comparison');
      $('#experiment-note').after(panel);
      panel.addEventListener('change',event => {
        const experiment = $('#experiment-select').value;
        const selection = state.pairSelection.get(experiment) || {};
        if (event.target.id === 'pair-select') state.pairSelection.set(experiment,{pair:event.target.value,caseIndex:0});
        else if (event.target.id === 'pair-case-select') state.pairSelection.set(experiment,{...selection,caseIndex:Number(event.target.value)});
        else return;
        renderAuditedComparison(experiment);
        panel.querySelector(`#${event.target.id}`)?.focus();
      });
    }
    const strict=(state.data.promptComparisons || []).find(item => item.id === id && item.eligible === true);
    const native=!strict && (state.data.nativeInstructionComparisons || []).find(item => item.id === id);
    const hosted=!strict && !native && hostedPair(id);
    const report=strict || native || hosted;
    if (!report) {panel.hidden = true;panel.innerHTML = '';return;}
    panel.hidden = false;
    panel.setAttribute('aria-label',native ? 'Jev instruction comparison' : hosted ? 'Hosted prompt comparison' : 'Recorded prompt comparison');
    const names = {P0_to_P1:'P0 → P1',P0_to_P2:'P0 → P2',P1_to_P2:'P1 → P2'};
    const available = Object.keys(names).filter(key => report.comparisons?.[key]);
    const selection = state.pairSelection.get(id) || {};
    const pairKey = available.includes(selection.pair) ? selection.pair : available[0];
    if (!pairKey) {panel.hidden = true;panel.innerHTML = '';return;}
    const pair = report.comparisons[pairKey];
    const cases = Array.isArray(pair.cases) ? pair.cases : [];
    const caseIndex = Number.isInteger(selection.caseIndex) && selection.caseIndex >= 0 && selection.caseIndex < cases.length ? selection.caseIndex : 0;
    const item = cases[caseIndex];
    const [before,after] = pairKey.split('_to_');
    const evidence = url(report.evidenceUrl);
    const allFourGain = Array.isArray(pair.allFourWrongToCorrect) ? pair.allFourWrongToCorrect.length : 0;
    const allFourLoss = Array.isArray(pair.allFourCorrectToWrong) ? pair.allFourCorrectToWrong.length : 0;
    panel.innerHTML = `<div class="audited-heading"><div><h4>${native ? 'Jev instruction comparison' : hosted ? 'Hosted prompt comparison' : 'Recorded prompt comparison'}</h4></div>${evidence ? `<a href="${esc(evidence)}" target="_blank" rel="noopener noreferrer">Comparison report ↗</a>` : ''}</div><p class="audited-method">${native ? 'Jev P1 and P2 rewrite the native Choice questions. P0 ran earlier, in one pass. ' : ''}${esc(report.comparisonLimit || report.historicalP0Limitation || '')}</p><label class="audited-pair-control"><span>Prompt versions</span><select id="pair-select">${available.map(key => `<option value="${key}"${key === pairKey ? ' selected' : ''}>${names[key]}</option>`).join('')}</select></label><div class="audited-counts" role="status" aria-live="polite" aria-atomic="true"><div><strong>${esc(count(pair.bothValid))} / 60</strong><span>comments with answers in the required format in both runs</span></div><div><strong>${esc(count(pair.changedRecordCount))}</strong><span>reviews with changed outputs</span></div><div><strong>${esc(count(allFourGain))} / ${esc(count(allFourLoss))}</strong><span>gained / lost matches on all four</span></div></div>${item ? `<div class="audited-record"><label><span>Comment with a changed answer</span><select id="pair-case-select">${cases.map((entry,index) => `<option value="${index}"${index === caseIndex ? ' selected' : ''}>${esc(entry.id)}</option>`).join('')}</select></label><article class="case-card"><div class="case-head"><span>REVIEW ${esc(item.id)}</span><span>${esc(readableValue(item.from_state))} → ${esc(readableValue(item.to_state))}</span></div><blockquote>${esc(item.feedback || 'Comment unavailable')}</blockquote><div class="audited-predictions"><div><strong>BEFORE, ${before}</strong><span>${esc(caseValue(item.from_prediction))}</span></div><div><strong>AFTER, ${after}</strong><span>${esc(caseValue(item.to_prediction))}</span></div><div><strong>REFERENCE</strong><span>${esc(caseValue(item.reference))}</span></div></div></article></div>` : '<p class="note">No changed review is listed for this pair.</p>'}${report.referenceStatus ? `<p class="note">Reference status: ${esc(report.referenceStatus)}</p>` : ''}`;
  }
  function modelFamily(run) {
    const name = `${run.id} ${run.model}`.toLowerCase();
    for (const [pattern, family] of [[/solar-decide/, 'Solar'], [/liquid|lfm.*d1/, 'Liquid'], [/tev1/, 'Tev'], [/anyjev/, 'AnyJev'], [/openjev/, 'OpenJev'], [/typesafe|\bjev\b/, 'Jev'], [/clef/, 'Clef'], [/laya/, 'Laya'], [/semif/, 'Semif'], [/kev/, 'Kev'], [/qwen/, 'Qwen'], [/gemma/, 'Gemma'], [/deepseek/, 'DeepSeek'], [/mistral/, 'Mistral'], [/gemini/, 'Gemini'], [/claude|sonnet|opus|haiku|fable/, 'Claude'], [/gpt|codex/, 'GPT'], [/rules|regex/, 'Rules baseline']]) {
      if (pattern.test(name)) return family;
    }
    return 'Other';
  }
  function visibleRuns() {
    const query = $('#search').value.trim().toLowerCase();
    const condition = $('#condition-filter').value;
    const surface = $('#surface-filter').value;
    const include = $('#include-incomplete').checked;
    const family = $('#family-filter')?.value || '';
    const effort = $('#effort-filter')?.value || '';
    const category = $('#category-filter')?.value || '';
    const trainingLineage = $('#training-filter')?.value || '';
    const interfaceKind = $('#interface-filter')?.value || '';
    const runs = state.data.runs.filter(r => {const type=modelType(r);return (include || complete(r)) && (!family || modelFamily(r) === family) && (!effort || r.effort === effort) && (!category || (type.categories || [type.category]).includes(category)) && (!trainingLineage || type.trainingLineage === trainingLineage) && (!interfaceKind || type.interfaceKind === interfaceKind) && (!condition || r.condition === condition) && (!surface || r.surface === surface) && (!query || `${r.id} ${r.model} ${r.effort} ${r.surface} ${experimentId(r)}`.toLowerCase().includes(query));});
    if ($('#sort').value === 'model-asc') runs.sort((a,b) => label(a).localeCompare(label(b)) || a.condition.localeCompare(b.condition));
    else runs.sort((a,b) => (n(score(b)) ?? -1)-(n(score(a)) ?? -1) || label(a).localeCompare(label(b)));
    return runs;
  }
  function renderLedger() {
    const runs = visibleRuns();
    $('#result-count').textContent = `${runs.length.toLocaleString('en-US')} shown of ${state.data.runs.length.toLocaleString('en-US')} saved runs`;
    $('#score-heading').textContent = `${metricName[$('#metric').value]}, of 60`;
    $('#comparison-list').innerHTML = runs.length ? runs.map(r => `<button type="button" class="comparison-row${r.id === state.selectedId ? ' selected' : ''}" data-run="${esc(r.id)}" aria-label="Inspect ${esc(label(r))}, ${esc(r.condition)}"><span class="run-name">${esc(label(r))}<span class="run-meta">${esc([modelType(r).categoryLabel,modelType(r).trainingLabel,modelType(r).interfaceLabel,passText(r),complete(r)?null:`partial tally, ${savedSummary(r)}${missingSummary(r)}`].filter(Boolean).join(', '))}</span><code class="run-id">${esc(r.model)}</code></span><span>${esc(r.condition)}</span><span class="metric-value"><strong>${has(r.valid) ? esc(r.valid) : '—'}</strong><small> / 60${complete(r) ? '' : ', partial tally'}</small></span><span class="metric-value"><strong>${has(score(r)) ? esc(score(r)) : '—'}</strong><small> / 60${complete(r) ? '' : ', partial tally, not final'}</small></span><span class="run-runtime"><span>In ${esc(count(runTokens(r).input))}, Out ${esc(count(runTokens(r).output))}</span><small>${has(runTokens(r).reasoning) ? `Reasoning ${esc(count(runTokens(r).reasoning))}, ` : ''}${esc(costSummary(r))}</small>${n(r.cost?.unknownUpperBoundUsd) > 0 ? `<small>plus up to ${esc(money(r.cost.unknownUpperBoundUsd))} unrecorded</small>` : ''}${inferenceTime(r.timing) !== 'Unknown' || providerGenerationTime(r.timing) ? `<small>${esc([inferenceTime(r.timing) !== 'Unknown' ? `Inference ${inferenceTime(r.timing)}` : null,providerGenerationTime(r.timing) ? `Provider generation ${providerGenerationTime(r.timing)}` : null].filter(Boolean).join(', '))}</small>` : ''}</span></button>`).join('') : '<p class="empty-state">No runs match these filters.</p>';
    $('#comparison-list').querySelectorAll('[data-run]').forEach(button => button.addEventListener('click',() => selectRun(button.dataset.run,true)));
  }
  const decisionLabels = {sentiment:'Sentiment',follow_up_needed:'Follow-up needed',serious_concern_reported:'Serious concern reported',testimonial_potential:'Testimonial potential'};
  const readableValue = value => String(value ?? '').replaceAll('_',' ');
  function caseValue(value) {
    if (value === null || value === undefined || value === '') return 'Unknown';
    if (typeof value === 'object') return Object.entries(value).map(([key,v]) => `${decisionLabels[key] || readableValue(key)}: ${typeof v === 'object' ? JSON.stringify(v) : readableValue(v)}`).join(', ');
    return String(value);
  }
  function caseCard(item) {
    return `<article class="case-card"><div class="case-head"><span>${esc(item.id || '')}</span><span>${esc(readableValue(item.status || ''))}</span></div><blockquote>${esc(item.feedback || 'Comment unavailable')}</blockquote><div class="case-result"><div><strong>REFERENCE</strong><span>${esc(caseValue(item.reference))}</span></div><div><strong>MODEL OUTPUT</strong><span>${esc(caseValue(item.prediction))}</span></div></div>${Array.isArray(item.different_fields) && item.different_fields.length ? `<p class="note">Decisions that differ: ${esc(item.different_fields.map(key => decisionLabels[key] || readableValue(key)).join(', '))}</p>` : ''}</article>`;
  }
  function renderCasesLegacy(run) {
    const all = state.data.cases.filter(item => item.configuration === run.id);
    const panel = $('#case-panel');
    if (!all.length) {
      const source=url(run.sourceRecordsUrl);
      panel.innerHTML=run.sourceFamily
        ? `<p class="empty-state">Answers for this stage are in its report.</p>${source ? `<a class="detail-evidence" href="${esc(source)}" target="_blank" rel="noopener noreferrer">Stage report ↗</a>` : ''}`
        : run.sourceOnlyDetails
        ? `<p class="empty-state">The ${esc(count(savedResponses(run)))} saved answers for this run are in its source file.</p>${source ? `<a class="detail-evidence" href="${esc(source)}" target="_blank" rel="noopener noreferrer">Source records ↗</a>` : '<p class="note">This run has no public record link.</p>'}`
        : '<p class="empty-state">No individual comments are available for this run.</p>';
      return;
    }
    panel.innerHTML = `<div class="case-controls"><label><span>Find a comment</span><input type="search" id="case-search" placeholder="Search ID or comment"></label><label><span>Comment</span><select id="case-select"></select></label><label class="case-check"><input type="checkbox" id="case-disagreements"> Show disagreements only</label></div><p class="case-counter" id="case-counter"></p><div id="case-current"></div>`;
    let matches=[];
    const update = () => {
      const query = $('#case-search').value.toLowerCase().trim();
      matches=all.filter(item => (!$('#case-disagreements').checked || item.different_fields?.length) && (!query || `${item.id} ${item.feedback}`.toLowerCase().includes(query)));
      $('#case-select').innerHTML=matches.map((item,index) => `<option value="${index}">${esc(item.id || `Record ${index+1}`)}${item.different_fields?.length ? ', differs' : ''}</option>`).join('');
      $('#case-counter').textContent=`${matches.length} of ${all.length} saved comments`;
      $('#case-current').innerHTML=matches.length ? caseCard(matches[0]) : '<p class="empty-state">No comments match this search.</p>';
    };
    $('#case-search').addEventListener('input',update);
    $('#case-disagreements').addEventListener('change',update);
    $('#case-select').addEventListener('change',() => {$('#case-current').innerHTML=matches[Number($('#case-select').value)] ? caseCard(matches[Number($('#case-select').value)]) : '';});
    update();
    const requestedCase = new URL(location.href).searchParams.get('case');
    const requestedIndex = matches.findIndex(item => item.id === requestedCase);
    if (requestedIndex >= 0) {
      $('#case-select').value=String(requestedIndex);
      $('#case-current').innerHTML=caseCard(matches[requestedIndex]);
    }
  }
  let unifiedCasePromise;
  function unifiedCaseFeed() {
    if (!unifiedCasePromise) {
      unifiedCasePromise=Promise.all([
        globalThis.BenchmarkExtendedCases.load('./extended-cases-v1.json'),
        globalThis.BenchmarkExtendedCases.load('./additional-cases-v1.json')
      ]).then(([extended,additional]) => globalThis.BenchmarkExtendedCases.combine(state.data,extended,additional))
        .catch(error => {unifiedCasePromise=null;throw error;});
    }
    return unifiedCasePromise;
  }
  function renderCases(run) {
    if (!globalThis.BenchmarkExtendedCases) return renderCasesLegacy(run);
    const panel=$('#case-panel'),requestedRun=run.id;
    panel.innerHTML='<p class="loading">Loading saved answers</p>';
    unifiedCaseFeed().then(feed => {
      if (state.selectedId === requestedRun) globalThis.BenchmarkExtendedCases.render(panel,feed,requestedRun);
    }).catch(error => {
      if (state.selectedId !== requestedRun) return;
      if (state.data.cases.some(item => item.configuration === requestedRun)) renderCasesLegacy(run);
      else {
        const ownFeed=run.sourceFamily ? './extended-cases-v1.json'
          : run.sourceOnlyDetails ? './additional-cases-v1.json' : null;
        const showSource=() => {
          if (state.selectedId !== requestedRun) return;
          const source=url(run.sourceRecordsUrl);
          panel.innerHTML=`<p class="empty-state">The saved answers did not load.</p>${source ? `<a class="detail-evidence" href="${esc(source)}" target="_blank" rel="noopener noreferrer">Run records ↗</a>` : ''}`;
        };
        if (ownFeed) globalThis.BenchmarkExtendedCases.load(ownFeed)
          .then(feed => {
            if (state.selectedId === requestedRun) globalThis.BenchmarkExtendedCases.render(panel,feed,requestedRun);
          }).catch(showSource);
        else showSource();
      }
      console.error('Unified case feed error:',error);
    });
  }
  function resourceSection(title,rows,note) {return `<section class="resource-group"><h5>${esc(title)}</h5><dl class="data-list">${rows.join('')}</dl>${note ? `<p class="note">${esc(note)}</p>` : ''}</section>`;}
  function timingRows(timing,run) {
    const basis=timing.kind === 'batch' ? 'One request could include several comments' : timing.kind === 'record' ? 'One request per comment or retry' : 'Request size unavailable';
    const caution=localRun(run) ? 'Timed on our own machine. ' : timing.kind === 'batch' ? 'One batch request covers several comments. ' : '';
    const rows=[dataRow('Median client request duration',duration(timing.medianSeconds)),dataRow('Request size',basis),dataRow('Sum of recorded request durations',duration(timing.totalSeconds)),dataRow('95th percentile request duration',duration(timing.p95Seconds)),dataRow('Requests timed',count(timing.requests))];
    if(providerGenerationTime(timing))rows.push(dataRow('Median provider generation duration',providerGenerationTime(timing)));
    return resourceSection('Technical timing',rows,caution+(timing.line || (timing.complete === false ? 'Timing is incomplete.' : '')));
  }
  function tokenRows(tokens,run) {
    const partial=tokens.complete === false;
    const prefix=partial ? 'Known ' : '';
    const rows=[['Input tokens','input'],['Output tokens','output'],['Cached input tokens','cachedInput'],['Cache-write tokens','cacheWrite'],['Reasoning tokens','reasoning']].map(([name,key]) => dataRow(partial ? prefix+name.toLowerCase() : name,count(tokens[key])));
    rows.push(dataRow('Requests with token usage',n(tokens.reportedRequests) === null ? 'Unknown' : `${count(tokens.reportedRequests)} / ${count(tokens.totalRequests)}`));
    const coverage=partial ? 'Totals leave out requests that returned no usage. ' : '';
    const definition=priceEntry(run) ? (run.surface === 'Claude subscription' ? 'Claude input excludes separately reported cache reads and writes. ' : 'Codex input includes cached input. ') : '';
    return resourceSection('Tokens',rows,definition+coverage);
  }
  function costRows(cost,run) {
    const price=priceEntry(run);
    const rows=[];
    if (n(cost.actualUsd) !== null) rows.push(dataRow('Charge',money(cost.actualUsd)));
    else if (n(cost.knownUsd) !== null) rows.push(dataRow('Charge',money(cost.knownUsd)));
    else rows.push(dataRow('Charge',localRun(run) ? 'None, run locally' : 'Unknown'));
    const dagger=value => n(value) === null ? money(value) : money(value)+'†';
    if (price) rows.push(dataRow('At API rates',dagger(price.estimateUsd)));
    else if (n(cost.estimatedUsd) !== null) rows.push(dataRow(cost.estimateKind === 'known_usage_only' ? 'At API rates, known usage' : 'At API rates',dagger(cost.estimatedUsd)));
    if (n(cost.unknownUpperBoundUsd) > 0) rows.push(dataRow('Unrecorded charge, up to',money(cost.unknownUpperBoundUsd)));
    const source=price && url(price.rate?.sourceUrl) ? `<p class="note">Public rate checked ${esc(price.rate.checkedDate)}, <a href="${esc(url(price.rate.sourceUrl))}" target="_blank" rel="noopener noreferrer">Model price source ↗</a>.${price.estimateUsd === null ? ' No API-rate price: '+esc(price.estimateStatus.replace(/_/g,' '))+'.' : ''}</p>` : url(cost.sourceUrl) ? `<p class="note"><a href="${esc(url(cost.sourceUrl))}" target="_blank" rel="noopener noreferrer">Model price source ↗</a></p>` : '';
    return resourceSection('Cost in USD',rows,cost.line || '')+source;
  }
  function renderUsage(run) {
    const timing=run.timing || {},tokens=runTokens(run),cost=runCost(run),price=priceEntry(run);
    const coverage=n(tokens.reportedRequests) === null ? 'Usage coverage not recorded' : `${count(tokens.reportedRequests)} of ${count(tokens.totalRequests)} requests reported token use`;
    const actualLabel='Charge';
    const inferred=inferenceTime(timing);
    const generation=providerGenerationTime(timing);
    const inferenceNote=inferred === 'Unknown' ? (n(timing.requests) > 0 ? 'The provider reported no inference time for this run.' : 'No inference or request time was recorded for this run.') : `${count(timing.inferenceReportedRequests)} requests reported server inference time. ${timing.inferenceBasis || ''}`;
    const evidence=url(run.evidenceUrl);
    $('#usage-summary').innerHTML=`<div class="usage-heading"><h3>${esc(label(run))} <small>${esc([run.condition,passText(run)].filter(Boolean).join(' '))}</small></h3><code>${esc(run.model)}</code>${evidence ? `<a href="${esc(evidence)}" target="_blank" rel="noopener noreferrer">Source report ↗</a>` : ''}</div><div class="usage-grid"><article><span class="usage-label">Server inference time</span><strong>${esc(inferred)}</strong><p>${esc(inferenceNote)}</p>${generation ? `<dl><div><dt>Provider generation median</dt><dd>${esc(generation)}</dd></div><div><dt>Requests with generation time</dt><dd>${esc(count(timing.providerGenerationReportedRequests))} / ${esc(count(timing.providerGenerationTotalRequests))}</dd></div></dl>${timing.providerGenerationBasis ? `<p>${esc(timing.providerGenerationBasis)}</p>` : ''}` : ''}</article><article><span class="usage-label">Token use</span><dl><div><dt>Input</dt><dd>${esc(count(tokens.input))}</dd></div><div><dt>Cache read</dt><dd>${esc(count(tokens.cachedInput))}</dd></div><div><dt>Cache write</dt><dd>${esc(count(tokens.cacheWrite))}</dd></div><div><dt>Output</dt><dd>${esc(count(tokens.output))}</dd></div><div><dt>Reasoning</dt><dd>${esc(count(tokens.reasoning))}</dd></div></dl><p>${esc(coverage)}. ${tokens.complete === false ? 'Totals cover only requests with usage data.' : ''}</p></article><article><span class="usage-label">Cost</span><dl><div><dt>${esc(actualLabel)}</dt><dd>${esc(observedCost(cost))}</dd></div><div><dt>${cost.estimateKind === 'known_usage_only' ? 'At API rates, known usage' : 'At API rates'}</dt><dd>${esc(money(cost.estimatedUsd))}${n(cost.estimatedUsd) === null ? '' : '†'}</dd></div>${n(cost.unknownUpperBoundUsd) > 0 ? `<div><dt>Unrecorded charge, up to</dt><dd>${esc(money(cost.unknownUpperBoundUsd))}</dd></div>` : ''}</dl><p>${price ? 'Reasoning tokens count as output.' : ''}${price && url(price.rate?.sourceUrl) ? ` <a href="${esc(url(price.rate.sourceUrl))}" target="_blank" rel="noopener noreferrer">Public model price ↗</a> (${esc(price.rate.checkedDate)}).` : url(cost.sourceUrl) ? ` <a href="${esc(url(cost.sourceUrl))}" target="_blank" rel="noopener noreferrer">Public model price ↗</a>.` : ''}${price?.estimateUsd === null ? ` No API-rate price: ${esc(price.estimateStatus.replace(/_/g,' '))}.` : ''}${run.id === 'typesafe-jev113-v2' ? ' The unrecorded amount is the reservation held for one failed request.' : ''}</p></article></div>`;
  }
  function selectRun(id,scroll) {
    const run=state.data.runs.find(r => r.id === id);if (!run)return;
    state.selectedId=id;
    $('#experiment-select').value=experimentId(run);
    for(const selector of ['#usage-run-select','#inspect-run-select']) {const picker=$(selector);if(picker)picker.value=id;}
    syncUrl();
    const timing=run.timing || {},tokens=runTokens(run),cost=runCost(run),metrics=run.metrics || {};
    $('#compare-run-select').value=Array.from($('#compare-run-select').options).some(option=>option.value===id) ? id : '';
    const evidence=url(run.evidenceUrl);
    const trainingEvidence=url(modelType(run).trainingSource);
    $('#run-detail').innerHTML=`<div class="detail-top"><div><h3>${esc(label(run))}</h3><p>${esc([run.condition,passText(run)].filter(Boolean).join(' '))}</p><code class="detail-run-id">${esc(run.model)}</code></div><span class="detail-badge${complete(run)?'':' partial'}">${complete(run)?'Complete':'Partial'}, ${esc(savedTag(run))}${complete(run) ? '' : `${esc(missingTag(run))}, not final`}, ${has(run.valid) ? `${esc(count(run.valid))} of 60 valid` : 'Valid count not recorded'}</span></div><div class="detail-stats"><div class="detail-stat"><span>${complete(run) ? 'Valid, of 60' : 'Partial: valid, of 60'}</span><strong>${has(run.valid)?esc(run.valid):'—'}</strong><small>Responses in the required format</small></div><div class="detail-stat"><span>${complete(run) ? 'All four match, of 60' : 'Partial: all four match, of 60'}</span><strong>${has(metrics.all_four)?esc(metrics.all_four):'—'}</strong><small>All decisions match the reference</small></div><div class="detail-stat"><span>${complete(run) ? 'Sentiment matches, of 60' : 'Partial: sentiment matches, of 60'}</span><strong>${has(metrics.sentiment)?esc(metrics.sentiment):'—'}</strong><small>Matches the reference</small></div><div class="detail-stat"><span>Input tokens</span><strong>${esc(count(tokens.input))}</strong><small>${tokens.complete === false ? 'Known usage only' : 'Reported usage'}</small></div></div><div class="detail-lower"><div><h4>${complete(run) ? 'Scores and resource use' : 'Recorded tallies and resource use'}</h4>${complete(run) ? '' : `<p class="note">${esc(tallyNote(run))}</p>`}<dl class="data-list">${dataRow(`${complete(run) ? '' : 'Partial tally: '}Sentiment matches / 60`,count(metrics.sentiment))}${dataRow(`${complete(run) ? '' : 'Partial tally: '}Follow-up matches / 60`,count(metrics.follow_up_needed))}${dataRow(`${complete(run) ? '' : 'Partial tally: '}Serious concern matches / 60`,count(metrics.serious_concern_reported))}${dataRow(`${complete(run) ? '' : 'Partial tally: '}Testimonial matches / 60`,count(metrics.testimonial_potential))}</dl>${timingRows(timing,run)}${tokenRows(tokens,run)}${costRows(cost,run)}${run.resultStatus ? `<p class="note">${esc(run.resultStatus)}</p>` : ''}${comparisonNote(run)}${trainingEvidence ? `<a class="detail-evidence" href="${esc(trainingEvidence)}" target="_blank" rel="noopener noreferrer">Training source ↗</a>` : ''}${evidence ? `<a class="detail-evidence" href="${esc(evidence)}" target="_blank" rel="noopener noreferrer">Source report ↗</a>` : ''}</div><div><h4>Answers by comment</h4><div id="case-panel"></div></div></div>`;
    renderCases(run);renderFieldComparison(run);renderUsage(run);renderLedger();renderOverview();renderExperiment();
    if (scroll) $('#inspect').scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});
  }
  function renderFieldComparison(run) {
    const jev=state.data.runs.find(r => r.id === 'typesafe-jev113-v2');
    if(!jev){$('#field-comparison').hidden=true;return;}
    if(run.id === jev.id){$('#field-comparison').innerHTML='<p class="comparison-invite">Jev is the selected run.</p>';return;}
    const fields=[['Valid responses','valid'],['All four match','all_four'],['Sentiment matches','sentiment'],['Follow-up matches','follow_up_needed'],['Serious concern matches','serious_concern_reported'],['Testimonial matches','testimonial_potential']];
    const get=(r,key)=>key==='valid'?r.valid:r.metrics?.[key];
    $('#field-comparison').innerHTML=`<h3>Jev and ${esc(run.model)}</h3><p>Each bar is a count out of 60.${complete(run) ? '' : ` ${esc(tallyNote(run))}`}</p>${fields.map(([name,key]) => { const a=get(jev,key),b=get(run,key);return `<div class="field-row"><span>${esc(name)}</span><div><span class="field-track"><span style="width:${has(a)?Math.max(0,Math.min(100,n(a)/60*100)):0}%"></span></span><span class="field-track selected"><span style="width:${has(b)?Math.max(0,Math.min(100,n(b)/60*100)):0}%"></span></span></div><strong>${has(a)?esc(a):'—'} vs ${has(b)?esc(b):'—'}</strong></div>`;}).join('')}<div class="field-key"><span></span>Jev (first number) <span></span>${esc(run.model)} (second number)</div>`;
  }
  function renderRoster() {
    const roster=state.data.roster;
    if(!roster.length){$('.availability').hidden=true;return;}
    const query=$('#roster-search').value.toLowerCase().trim();
    const display=item => {
      const missing=missingCondition(item.id,'P1');
      return missing.label==='Blocked after P0' ? {status:'blocked after P0',reason:'The native Antigravity route stopped after P0. P1 and P2 have no complete public run.',audit:missing.links?.[0]?.href} : {status:item.disposition,reason:item.reason};
    };
    const entries=roster.filter(item => {const base=state.data.runs.find(r=>r.id===item.parentBaselineId);return !query || `${item.id} ${base?.model||''} ${display(item).status}`.toLowerCase().includes(query);});
    $('#roster-count').textContent=`${entries.length} of ${roster.length} setups`;
    $('#roster-list').innerHTML=entries.length ? entries.map(item => {const shown=display(item);return `<div class="roster-row"><strong>${esc(item.id)}</strong><span>${esc(shown.status)}</span><p>${esc(shown.reason)}${shown.audit ? ` <a href="${esc(shown.audit)}" target="_blank" rel="noopener noreferrer">Coverage audit ↗</a>` : ''}</p></div>`;}).join('') : '<p class="empty-state">No model or setup matches this search.</p>';
  }
  function initSources() {
    const referenceNote=$('#reference-note');
    if (referenceNote) referenceNote.textContent='AI wrote the 60 fictional comments and drafted the reference answers. A person checked all 60, and three labels are still disputed.';
    // The Downloads list links the repository; #source-links stays empty and keeps its id.
  }
  function initJev() {
    const jev=state.data.runs.find(r => r.id === 'typesafe-jev113-v2') || state.data.runs.find(r => /typesafe.*jev/i.test(r.id) && r.condition === 'P0');
    if (!jev) {$('#jev').hidden=true;return;}
    $('#jev-score').innerHTML=`${has(jev.metrics?.all_four) ? esc(jev.metrics.all_four) : '—'}<small>/ 60</small>`;
    $('#jev-note').textContent=`${count(jev.valid)} of 60 answers came back in the required format, using ${count(jev.tokens?.input)} input and ${count(jev.tokens?.output)} output tokens.`;
    $('#inspect-jev').addEventListener('click',() => selectRun(jev.id,true));
  }
  async function init() {
    try {
      const response=await fetch('./data-provider-errors-v1.json',{cache:'no-store'});if(!response.ok)throw new Error(`HTTP ${response.status}`);
      const data=await response.json();if(!Array.isArray(data.runs)||n(data.denominator)!==60)throw new Error('Invalid public data');
      state.data={...data,runs:data.runs.filter(r => r?.id && ['P0','P1','P2'].includes(r.condition)),cases:Array.isArray(data.cases)?data.cases:[],roster:Array.isArray(data.roster)?data.roster:[]};
      const [pricing,sonnet55,clef,decisionRuns,extendedRuns,jevFindings]=await Promise.all([optionalPricing(),optionalSonnet55(),optionalClef(),optionalDecisionRuns(),optionalExtendedRuns(),optionalJevFindings()]);
      if (pricing?.schema === 'subscription-price-estimates-v1' && pricing.runs && typeof pricing.runs === 'object') state.pricing=pricing;
      state.data.runs.push(...sonnet55FirstPassRuns(sonnet55).filter(run=>!state.data.runs.some(existing=>existing.id===run.id)));
      const clefRuns=clefFirstPassRuns(clef);
      state.data.runs.push(...clefRuns.filter(run=>!state.data.runs.some(existing=>existing.id===run.id)));
      renderClefFirstPass(clefRuns,clef,(decisionRuns?.runs || []).find(run=>run?.id==='clef-openrouter-native-fresh1-p0')?.metrics?.all_four);
      state.data.runs.push(...supplementalDecisionRuns(decisionRuns,state.data.runs));
      const catalogRuns=extendedCatalogRuns(extendedRuns,state.data.runs);
      applyJevFindings(catalogRuns,jevFindings);
      state.data.runs.push(...catalogRuns);
      const catalogStatus=$('#extended-run-status');
      if(catalogStatus) catalogStatus.textContent=catalogRuns.length ? '' : 'The repeat passes did not load, so the chart and run list leave them out.';
      const queryMetric=new URL(location.href).searchParams.get('metric');if(queryMetric && Object.prototype.hasOwnProperty.call(metricName,queryMetric))$('#metric').value=queryMetric;
      groups();renderExperimentSelect();renderModelSelect();renderSectionRunPickers();
      ['#overview-condition','#overview-surface'].forEach(selector=>$(selector).addEventListener('change',()=>{state.overviewAll=false;renderOverview();}));
      $('#overview-specialists').addEventListener('click',()=>{$('#overview-surface').value='local';globalThis.BenchmarkReportNavigation?.setCohort('all');state.overviewAll=true;renderOverview();});
      $('#overview-toggle').addEventListener('click',()=>{state.overviewAll=!state.overviewAll;renderOverview();});
      $('#compare-search').addEventListener('input',renderModelSelect);
      $('#compare-run-select').addEventListener('change',event=>{if(event.target.value)selectRun(event.target.value,false);});
      for(const selector of ['#usage-run-select','#inspect-run-select']) $(selector).addEventListener('change',event=>selectRun(event.target.value,false));
      $('#surface-filter').innerHTML='<option value="">All execution methods</option>'+[...new Set(state.data.runs.map(r=>r.surface).filter(Boolean))].sort().map(s => `<option value="${esc(s)}">${esc(s.replaceAll(' · ', ', '))}</option>`).join('');
      for (const [selector, values, all] of [
        ['#family-filter', state.data.runs.map(modelFamily), 'All model families'],
        ['#effort-filter', state.data.runs.map(r => r.effort).filter(Boolean), 'All reasoning settings']
      ]) {
        const control = $(selector);
        if (control) { control.innerHTML = `<option value="">${all}</option>` + [...new Set(values)].sort().map(value => `<option value="${esc(value)}">${esc(value === 'not applicable' ? 'No effort setting' : value)}</option>`).join(''); control.addEventListener('change', renderLedger); }
      }
      for (const [selector, entries, all] of [
        ['#category-filter', globalThis.BenchmarkCategories?.categories || {unknown:'Category not verified'}, 'All model categories'],
        ['#training-filter', globalThis.BenchmarkCategories?.training || {unknown:'Training not verified'}, 'All training lineages'],
        ['#interface-filter', globalThis.BenchmarkCategories?.interfaces || {unknown:'Interface not verified'}, 'All output interfaces']
      ]) {
        const control=$(selector);
        if (control) {control.innerHTML=`<option value="">${all}</option>`+Object.entries(entries).map(([key,value])=>`<option value="${esc(key)}">${esc(value)}</option>`).join('');control.addEventListener('change',renderLedger);}
      }
      $('#clear-run-filters')?.addEventListener('click', () => {
        for (const id of ['#search','#condition-filter','#surface-filter','#family-filter','#effort-filter','#category-filter','#training-filter','#interface-filter']) { const control=$(id); if(control) control.value=''; }
        $('#include-incomplete').checked=false; globalThis.BenchmarkReportNavigation?.setCohort('all'); renderLedger();
      });
      globalThis.addEventListener('benchmark:cohortchange',event=>{
        state.cohort=event.detail.cohort;state.customCategory=event.detail.category||'';state.overviewAll=false;
        const chosen=state.data.runs.find(run=>run.id===state.selectedId);
        const category=state.customCategory || (state.cohort==='all' ? '' : state.cohort);
        if(!event.detail.initial && chosen && category && !modelType(chosen).categories.includes(category)){
          const replacement=state.data.runs.find(run=>run.condition===chosen.condition && complete(run) && modelType(run).categories.includes(category)) ||
            state.data.runs.find(run=>complete(run) && modelType(run).categories.includes(category));
          if(replacement){selectRun(replacement.id,false);return;}
        }
        renderOverview();
      });
      $('#experiment-select').addEventListener('change',() => {const group=state.experiments.get($('#experiment-select').value)||[];const lead=group.find(r=>r.condition==='P0')||group[0];if(lead)selectRun(lead.id,false);else renderExperiment();});
      $('#metric').addEventListener('change',() => {renderExperiment();renderLedger();if(state.selectedId)selectRun(state.selectedId,false);});
      ['#search','#condition-filter','#surface-filter','#sort','#include-incomplete'].forEach(selector => $(selector).addEventListener(selector==='#search'?'input':'change',renderLedger));
      if (!state.data.runs.some(r => !complete(r))) $('#include-incomplete').closest('label').hidden=true;
      $('#roster-search').addEventListener('input',renderRoster);
      initSources();initJev();renderRoster();renderLedger();renderOverview();renderExperiment();
      const jev=state.data.runs.find(r => r.id === 'typesafe-jev113-v2');
      const queryRun=new URL(location.href).searchParams.get('run');
      const initial=state.data.runs.find(r => r.id===queryRun) || (state.experiments.get($('#experiment-select').value)||[]).find(r => r.condition==='P0') || jev || state.data.runs.find(complete) || state.data.runs[0];if(initial)selectRun(initial.id,false);
      // Other views can use the final merged runs without receiving mutable explorer state.
      if (typeof globalThis.dispatchEvent === 'function' && typeof globalThis.CustomEvent === 'function') {
        const snapshot=JSON.parse(JSON.stringify({denominator:state.data.denominator,runs:state.data.runs}));
        globalThis.dispatchEvent(new CustomEvent('benchmark:saved-runs-ready',{detail:snapshot}));
      }
    } catch(error) {
      if (typeof globalThis.dispatchEvent === 'function' && typeof globalThis.Event === 'function') globalThis.dispatchEvent(new Event('benchmark:saved-runs-error'));
      const message='The results did not load.';
      for (const selector of ['#comparison-list','#condition-grid','#run-detail']) $(selector).innerHTML=`<p class="empty-state">${message}</p>`;
      $('#experiment-title').textContent=message;$('#jev-note').textContent=message;
      console.error('Public explorer data error:',error);
    }
  }
  init();
})();
