const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const site = path.join(__dirname, '../public-site');
const source = fs.readFileSync(path.join(site, 'analysis-refresh.js'), 'utf8');
async function renderState(payload, ok=true) {
  const target = {innerHTML:''};
  const summary = {innerHTML:''};
  const cutoffs = {innerHTML:''};
  vm.runInNewContext(source, {document:{getElementById:id=>({
    'analysis-refresh-table':target,
    'analysis-refresh-summary':summary,
    'analysis-refresh-cutoffs':cutoffs,
  }[id] || null)},fetch:async()=>({ok,json:async()=>payload})});
  await new Promise(resolve=>setImmediate(resolve));
  return {table:target.innerHTML,summary:summary.innerHTML,cutoffs:cutoffs.innerHTML};
}
async function render(payload, ok=true) { return (await renderState(payload,ok)).table; }
function isolateQwen35P0History(q35) {
  q35.completedConditions = 0;
  for (const condition of Object.values(q35.conditions)) {
    condition.completedPasses = 0;
    condition.passes = [];
    condition.pairwiseFlips = [];
    condition.changesAcrossThreePasses = null;
  }
  q35.matchedP0AllFourDeltas = {};
}
test('latest effort table uses source ranges, changed-review counts and nine-run costs', async()=>{
  const report = JSON.parse(fs.readFileSync(path.join(site, 'analysis-refresh.json'), 'utf8'));
  const html = await render(report);
  assert.match(html,/Sonnet 5.5/);
  assert.equal(report.claude.allThreePassPromptGainCount.P1,0);
  assert.equal(report.claude.allThreePassPromptGainCount.P2,0);
  for(const effort of ['low','medium','high','xhigh']) {
    assert.match(html,new RegExp(`<th scope="row">${effort}</th>`));
    const row=report.sonnet55.byEffort[effort];
    assert.ok(html.includes('$'+Number(row.usage.developmentApiEquivalentUsd).toFixed(3)));
  }
  // Current editorial claims must be reviewed if the source cohort changes.
  assert.ok(Object.values(report.sonnet55.byEffort.xhigh.conditions).every(c=>c.scores.length===3&&c.scores.every(n=>n===58)));
  const page=fs.readFileSync(path.join(site,'index.html'),'utf8');
  assert.match(page,/estimates are not subscription charges/);
  assert.match(page,/same 60 reviews/);
});
test('Gemini authority summary shows closed scores and record changes', async()=>{
  const report = JSON.parse(fs.readFileSync(path.join(site, 'analysis-refresh.json'), 'utf8'));
  const view = await renderState(report);
  assert.match(view.cutoffs,/Gemini 3\.1 Pro Preview, high effort/);
  assert.match(view.cutoffs,/9\/9 condition and pass combinations are closed/);
  assert.match(view.cutoffs,/P0: 55, 56, 56 of 60; P1: 56, 56, 56 of 60; P2: 55, 56, 56 of 60/);
  assert.match(view.cutoffs,/P0 2\/60, P1 1\/60, P2 2\/60 reviews/);
  assert.match(view.cutoffs,/P1 1, 0, 0; P2 0, 0, 0 full matches/);
  assert.match(view.cutoffs,/no consistent score gain/);
  const incomplete = structuredClone(report);
  incomplete.newerCohorts.geminiAuthority.completedConditions = 8;
  const broken = await renderState(incomplete);
  assert.equal(broken.cutoffs, '');
  assert.match(broken.table,/comparison could not be loaded/);
});
test('analysis page shows Gemma composite, Clef and local Qwen as separate cohorts', async()=>{
  const report = JSON.parse(fs.readFileSync(path.join(site, 'analysis-refresh.json'), 'utf8'));
  const view = await renderState(report);
  assert.match(view.summary,/21 Claude setups/);
  assert.match(view.cutoffs,/Gemma 26B/);
  assert.match(view.cutoffs,/All 9 planned runs now have results, including failed requests in the 60-review totals/);
  assert.match(view.cutoffs,/57, 56, 56 of 60/);
  assert.match(view.cutoffs,/P0 scores are 59, 56, 58 of 60/);
  assert.match(view.cutoffs,/P1 scores are 58, 58, 57 of 60/);
  assert.match(view.cutoffs,/Fresh3 has 59 valid answers and preserves DEV-059/);
  assert.match(view.cutoffs,/On the 59 reviews with valid answers in all three P1 passes/);
  assert.match(view.cutoffs,/each pass matched all four fields on 57, 57, 57/);
  assert.match(view.cutoffs,/lower 60-review score reflects the unavailable DEV-059 answer/);
  assert.doesNotMatch(view.cutoffs,/full fresh3 P0 and P1 results are absent/);
  assert.match(view.cutoffs,/2 of 57 shared-valid reviews changed a decision/);
  assert.match(view.cutoffs,/DEV-005 and DEV-006/);
  assert.match(view.cutoffs,/The series remains interrupted/);
  assert.match(view.cutoffs,/Clef native P0/);
  assert.match(view.cutoffs,/third pass has 2 unknown outcomes and 58 reviews that have not been sent/);
  assert.match(view.cutoffs,/Neither attempt returned a usable answer/);
  assert.match(view.cutoffs,/CLEF_FLASH_P0_SUFFIX_CHECKPOINT_2026-10-05.md/);
  assert.match(view.cutoffs,/53\/60/);
  assert.match(view.cutoffs,/45\/60/);
  assert.match(view.cutoffs,/At the P0 checkpoint, Clef had 3\/9 planned runs scored/);
  assert.match(view.cutoffs,/At the P0 checkpoint, Clef Flash had two completed P0 passes, scoring 45\/60 and 45\/60/);
  assert.match(view.cutoffs,/59 reviews were never sent/);
  assert.match(view.cutoffs,/so it has no third P0 score/);
  assert.match(view.cutoffs,/no changed four-field answer, native probability dictionary or vendor confidence value/);
  assert.match(view.cutoffs,/Clef P1, first pass/);
  assert.match(view.cutoffs,/52\/60 versus 53\/60/);
  assert.match(view.cutoffs,/0\.03472656/);
  assert.match(view.cutoffs,/Clef Flash P1/);
  assert.match(view.cutoffs,/All three passes returned 60 valid answers and scored 47\/60/);
  assert.match(view.cutoffs,/Two reviews became all-four matches \(DEV-027 and DEV-044\) and none lost one/);
  assert.match(view.cutoffs,/P1 passes describe repeat variation/);
  assert.match(view.cutoffs,/Clef Flash P2/);
  assert.match(view.cutoffs,/46, 46, 46 out of 60/);
  assert.match(view.cutoffs,/P2 gained a full match on DEV-058 versus P1, but lost matches on DEV-027 and DEV-032/);
  assert.match(view.cutoffs,/Mistral 119B fresh1 P0/);
  assert.match(view.cutoffs,/40\/60 records, or 40\/55 among valid answers/);
  assert.match(view.cutoffs,/five failures remain in the denominator/);
  assert.match(view.cutoffs,/interrupted single pass, not a completed repeat result/);
  assert.match(view.cutoffs,/Mistral 119B fresh1 P0 attempted all 60 reviews: 55 were valid and 5 failed/);
  assert.match(view.cutoffs,/Its other required conditions remain unfinished/);
  assert.match(view.cutoffs,/DeepSeek: failures change the comparison/);
  assert.match(view.cutoffs,/58\/60.*57\/60.*53\/60/);
  assert.match(view.cutoffs,/56 valid/);
  assert.match(view.cutoffs,/DEEPSEEK_LOW_FINAL_SUFFIX_FINDINGS_2026-10-06\.md/);
  assert.match(view.cutoffs,/href="\.\/gemma26-p2-repeat-findings\.json"/);
  assert.match(view.cutoffs,/href="\.\/gemma26-fresh3-p1-interrupted-checkpoint\.json"/);
  assert.match(view.cutoffs,/href="\.\/clef-p0-repeat-findings\.json"/);
  assert.match(view.cutoffs,/href="\.\/clef-p0-third-checkpoint\.json"/);
  assert.match(view.cutoffs,/href="\.\/clef-flash-p1-findings\.json"/);
  assert.match(view.cutoffs,/href="\.\/mistral119-fresh1-p0-findings\.json"/);
  assert.doesNotMatch(view.cutoffs,/href="public-site\//);
  assert.match(view.cutoffs,/Qwen1.7B with thinking disabled, current repeats/);
  assert.match(view.cutoffs,/9\/9 full phases are closed/);
  assert.match(view.cutoffs,/P0: 28, 26, 26 all-four matches out of 60; 60, 60, 60 valid answers/);
  assert.match(view.cutoffs,/P1: 25, 26, 25 all-four matches out of 60; 59, 60, 60 valid answers/);
  assert.match(view.cutoffs,/P2: 32, 30, 30 all-four matches out of 60; 57, 56, 55 valid answers/);
  assert.match(view.cutoffs,/10\/60 shared-valid reviews changed at least one label across three passes/);
  assert.match(view.cutoffs,/12\/59 shared-valid reviews changed at least one label across three passes/);
  assert.match(view.cutoffs,/7\/48 shared-valid reviews changed at least one label across three passes/);
  assert.match(view.cutoffs,/All three P2 full passes are complete/);
  assert.match(view.cutoffs,/Qwen1.7B with thinking disabled, historical first prompt comparison/);
  assert.match(view.cutoffs,/matched all four labels on 28\/25\/32 of 60 reviews/);
  assert.match(view.cutoffs,/gained an all-four match on 4 reviews but lost one on 7, among 59/);
  assert.match(view.cutoffs,/Decision rules gained 9 and lost 5, among 57/);
  assert.match(view.cutoffs,/Qwen1.7B, first pass/);
  assert.match(view.cutoffs,/base task scored 24\/60, classifier instructions 12\/60, and decision rules 8\/60/);
  assert.match(view.cutoffs,/P0, P1 and P2 now each have three complete passes/);
  assert.match(view.cutoffs,/30 of the 58 reviews/);
  assert.match(view.cutoffs,/30 of 60 reviews changed at least one label/);
  assert.match(view.cutoffs,/19 of 60 reviews changed at least one label/);
  assert.match(view.cutoffs,/Across all three P2 passes, scores were 8, 9, 8 out of 60/);
  assert.match(view.cutoffs,/58 reviews valid in all three, 40 changed/);
  assert.match(view.cutoffs,/Small Qwen SDK/);
  assert.match(view.cutoffs,/58 valid and 2 invalid/);
  assert.match(view.cutoffs,/5 valid and 55 invalid/);
  assert.match(view.cutoffs,/separate from hosted Qwen 27B/);
  assert.match(view.cutoffs,/Qwen3\.5 4B SDK, thinking on:<\/strong> 3\/9 full phases are closed/);
  assert.match(view.cutoffs,/fresh1 P1: 47\/60 all-four matches, 51\/60 valid answers, 9 invalid or failed/);
  assert.match(view.cutoffs,/fresh1 P2: 50\/60 all-four matches, 51\/60 valid answers, 9 invalid or failed/);
  assert.match(view.cutoffs,/descriptive interrupted result: 47\/60 all-four matches/);
  assert.doesNotMatch(view.cutoffs,/latest Gemma and DeepSeek continuations remain unscored/);
});
test('Qwen current repeat narrative distinguishes a stopped smoke from a closed full pass', async()=>{
  const report = JSON.parse(fs.readFileSync(path.join(site, 'analysis-refresh.json'), 'utf8'));
  const current = report.newerCohorts.legacyQwen.qwen17OffRepeat;
  const ninth = current.conditions.P2.passes.pop();
  const allPairs = current.conditions.P2.pairwiseFlips;
  const threePass = current.conditions.P2.changesAcrossThreePasses;
  current.conditions.P2.pairwiseFlips = allPairs.filter(pair=>pair.to!=='fresh3');
  current.conditions.P2.changesAcrossThreePasses = null;
  current.completedConditions = 8;
  current.conditions.P2.completedPasses = 2;
  current.conditions.P2.allFourRange = [30,32];
  current.missingPasses = [{pass:'fresh3',condition:'P2',status:'smoke_blocked',saved:3,valid:2,invalid:1}];
  const partial = await renderState(report);
  assert.match(partial.cutoffs,/8\/9 full phases are closed/);
  assert.match(partial.cutoffs,/P2: 32, 30 all-four matches out of 60; 57, 56 valid answers/);
  assert.match(partial.cutoffs,/Fresh3 P2 stopped at smoke after 3 saved responses \(2 valid, 1 invalid\); it has no full 60-review score/);
  current.conditions.P2.passes.push(ninth);
  current.conditions.P2.pairwiseFlips = allPairs;
  current.conditions.P2.changesAcrossThreePasses = threePass;
  current.completedConditions = 9;
  current.conditions.P2.completedPasses = 3;
  current.missingPasses = [];
  const complete = await renderState(report);
  assert.match(complete.cutoffs,/9\/9 full phases are closed/);
  assert.match(complete.cutoffs,/P2: 32, 30, 30 all-four matches out of 60; 57, 56, 55 valid answers/);
  assert.match(complete.cutoffs,/All three P2 full passes are complete/);
  assert.doesNotMatch(complete.cutoffs,/Fresh3 P2 stopped at smoke/);
});
test('Qwen3.5 summary shows only closed phases and supported comparisons', async()=>{
  const report = JSON.parse(fs.readFileSync(path.join(site, 'analysis-refresh.json'), 'utf8'));
  const q35 = {completedConditions:0,plannedConditions:9,missingPasses:[],matchedP0AllFourDeltas:{},
    conditions:Object.fromEntries(['P0','P1','P2'].map(c=>[c,{completedPasses:0,passes:[],pairwiseFlips:[],changesAcrossThreePasses:null}]))};
  report.newerCohorts.legacyQwen.qwen35Repeat=q35;
  let view=await renderState(report);
  assert.match(view.cutoffs,/Qwen3.5 4B SDK, thinking on:<\/strong> 0\/9 full phases are closed/);
  assert.match(view.cutoffs,/No full 60-review phase is closed yet/);
  assert.doesNotMatch(view.cutoffs,/Qwen3.5 4B SDK[\s\S]*fresh1 P0:/);
  q35.conditions.P0.passes.push({pass:'fresh1',score:{allFour:22,valid:59},
    usage:{clientRequestSecondsTotal:120.49,tokens:{input_tokens:83190,output_tokens:2498,total_tokens:85688,reasoning_output_tokens:500}}});
  q35.conditions.P0.completedPasses=1;
  q35.completedConditions=1;
  q35.matchedP0AllFourDeltas={fresh1:{}};
  view=await renderState(report);
  assert.match(view.cutoffs,/fresh1 P0: 22\/60 all-four matches, 59\/60 valid answers, 1 invalid or failed; 83,190 input tokens, 2,498 output tokens, 85,688 total \(500 reasoning tokens within output\); 120.5 seconds/);
  assert.doesNotMatch(view.cutoffs,/fresh1 P1 versus P0/);
  q35.conditions.P1.passes.push({pass:'fresh1',score:{allFour:25,valid:60},
    usage:{clientRequestSecondsTotal:100,tokens:{input_tokens:null,output_tokens:2000,total_tokens:null,reasoning_output_tokens:null}}});
  q35.conditions.P1.completedPasses=1;
  q35.completedConditions=2;
  q35.matchedP0AllFourDeltas.fresh1.P1=3;
  view=await renderState(report);
  assert.match(view.cutoffs,/fresh1 P1 versus P0: \+3 all-four matches out of 60/);
  assert.match(view.cutoffs,/unavailable input tokens, 2,000 output tokens, unavailable total/);
  q35.conditions.P0.passes.push({pass:'fresh2',score:{allFour:23,valid:60},
    usage:{clientRequestSecondsTotal:110,tokens:{input_tokens:80000,output_tokens:2400,total_tokens:82400,reasoning_output_tokens:400}}});
  q35.conditions.P0.completedPasses=2;
  q35.completedConditions=3;
  q35.conditions.P0.pairwiseFlips.push({from:'fresh1',to:'fresh2',denominator:59,
    fourFieldVector:{changed:7}});
  view=await renderState(report);
  assert.match(view.cutoffs,/P0 fresh1 to fresh2: 7\/59 shared-valid reviews changed at least one label/);
  assert.doesNotMatch(view.cutoffs,/P0 across three passes:/);
  q35.conditions.P0.passes.push({pass:'fresh3',score:{allFour:24,valid:60},
    usage:{clientRequestSecondsTotal:105,tokens:{input_tokens:81000,output_tokens:2600,total_tokens:83600,reasoning_output_tokens:450}}});
  q35.conditions.P0.completedPasses=3;
  q35.completedConditions=4;
  q35.conditions.P0.pairwiseFlips.push({from:'fresh1',to:'fresh3',denominator:59,fourFieldVector:{changed:8}});
  q35.conditions.P0.pairwiseFlips.push({from:'fresh2',to:'fresh3',denominator:60,fourFieldVector:{changed:6}});
  q35.conditions.P0.changesAcrossThreePasses={denominator:59,fourFieldVector:Array(9).fill('synthetic-review')};
  view=await renderState(report);
  assert.match(view.cutoffs,/P0 across three passes: 9\/59 reviews valid in all three changed at least one label/);
  assert.match(view.cutoffs,/local hardware and electricity cost and pure inference time were not measured/);
});
test('Qwen3.5 interrupted P0 remains a separate unscored partial in analysis', async()=>{
  const report = JSON.parse(fs.readFileSync(path.join(site, 'analysis-refresh.json'), 'utf8'));
  const q35 = report.newerCohorts.legacyQwen.qwen35Repeat;
  isolateQwen35P0History(q35);
  assert.equal(q35.completedConditions, 0);
  assert.equal(q35.partialPasses.length, 1);
  delete q35.descriptiveComposites;
  const view = await renderState(report);
  assert.match(view.cutoffs,/Qwen3.5 4B SDK, thinking on:<\/strong> 0\/9 full phases are closed/);
  assert.match(view.cutoffs,/Fresh1 P0 stopped after 52 attempts: 51 saved responses \(44 valid, 7 invalid\), DEV-052 with an unknown outcome, and 8 reviews never sent/);
  assert.match(view.cutoffs,/It has no full-pass score/);
  assert.match(view.cutoffs,/host slept during the unknown request/);
  assert.match(view.cutoffs,/QWEN35_P0_INTERRUPTION_2026-10-06.md/);
  assert.doesNotMatch(view.cutoffs,/fresh1 P0: \d+\/60 all-four matches/);
});
test('Qwen3.5 descriptive composite shows fixed-60 result without clean credit', async()=>{
  const report = JSON.parse(fs.readFileSync(path.join(site, 'analysis-refresh.json'), 'utf8'));
  const q35 = report.newerCohorts.legacyQwen.qwen35Repeat;
  isolateQwen35P0History(q35);
  const composite = q35.descriptiveComposites?.[0] || {
    pass:'fresh1',condition:'P0',status:'completed_interrupted_composite',
    score:{denominator:60,allFour:47,valid:51,outcomes:{invalid_output:8,unknown_started:1,never_sent:0}}
  };
  q35.descriptiveComposites=[composite];
  const view = await renderState(report);
  assert.match(view.cutoffs,/Qwen3.5 4B SDK, thinking on:<\/strong> 0\/9 full phases are closed/);
  assert.match(view.cutoffs,/descriptive interrupted result: 47\/60 all-four matches, 51 valid responses, 8 invalid responses and one unknown outcome at DEV-052/);
  assert.match(view.cutoffs,/none remain unsent/);
  assert.match(view.cutoffs,/not a clean repeat pass/);
  assert.doesNotMatch(view.cutoffs,/8 reviews never sent/);
});
test('unavailable or malformed analysis links the report instead of showing invented results', async()=>{
  assert.match(await render(null,false),/could not be loaded/);
  assert.match(await render({}),/could not be loaded/);
  const report = JSON.parse(fs.readFileSync(path.join(site, 'analysis-refresh.json'), 'utf8'));
  delete report.newerCohorts.clefNativeP0;
  assert.match(await render(report),/could not be loaded/);
});

// Closed hosted phases must remain visible as more phases are published.
test('hosted findings compare Qwen prompts and retain different DeepSeek invalid reviews', async()=>{
  const report=JSON.parse(fs.readFileSync(path.join(site,'analysis-refresh.json'),'utf8'));
  const view=await renderState(report);
  assert.match(view.cutoffs,/Hosted Qwen3\.6 with thinking enabled/);
  assert.match(view.cutoffs,/54\/60/);
  assert.match(view.cutoffs,/56\/60/);
  assert.match(view.cutoffs,/first classifier-instruction run was interrupted and is excluded/);
  assert.match(view.cutoffs,/DeepSeek V4\.1 Flash, high effort/);
  assert.match(view.cutoffs,/57\/60/);
  assert.match(view.cutoffs,/DEV-030/);
  assert.match(view.cutoffs,/DEV-006/);
  assert.match(view.cutoffs,/Equal totals do not mean the same reviews had usable answers/);
});

test('low continuation keeps unknown outcome and smoke costs separate', async()=>{
  const report=JSON.parse(fs.readFileSync(path.join(site,'analysis-refresh.json'),'utf8'));
  const view=await renderState(report);
  assert.match(view.cutoffs,/57\/60 reviews matched all four reference labels/);
  assert.match(view.cutoffs,/59 valid answers and one provider failure at DEV-005, whose cost is unknown/);
  assert.match(view.cutoffs,/0\.030564226637/);
  assert.match(view.cutoffs,/Smoke costs are excluded/);
  report.newerCohorts.deepseekLowRevisedPrice.cleanMatchedRepeatEligible=true;
  assert.match(await render(report),/could not be loaded/);
});

test('Liquid findings show repeat counts without claiming confidence calibration', async()=>{
  const report=JSON.parse(fs.readFileSync(path.join(site,'analysis-refresh.json'),'utf8'));
  const view=await renderState(report);
  assert.match(view.cutoffs,/Liquid d1, native decision interface/);
  assert.match(view.cutoffs,/reviews changed at least one label/);
  assert.match(view.cutoffs,/not proven probabilities of being correct/);
  assert.match(view.cutoffs,/liquid-d1-native-full-findings.json/);
});

test('DeepSeek high later results retain provider and intrinsic failures', async()=>{
  const report=JSON.parse(fs.readFileSync(path.join(site,'analysis-refresh.json'),'utf8'));
  const view=await renderState(report);
  assert.match(view.cutoffs,/DeepSeek high, later passes/);
  assert.match(view.cutoffs,/fresh2\/P2: 56\/60 full matches, 59\/60 valid answers/);
  assert.match(view.cutoffs,/fresh2\/P1: 58\/60 full matches, 60\/60 valid answers/);
  assert.match(view.cutoffs,/deepseek-high-remaining6-successor-findings.json/);
  assert.match(view.cutoffs,/1\/60 reviews changed a label \(DEV-030\)/);
  assert.match(view.cutoffs,/classifier instructions and decision rules differed on 1\/60 reviews/);
});
