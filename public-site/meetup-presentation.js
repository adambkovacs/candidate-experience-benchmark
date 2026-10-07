/* The deck reads the same source-bound public projections as the report. */
(() => {
  'use strict';
  const ids = ['opening','task','disagreement','boundary','prompts','decision-cohort','repeatability','cost','implications','limits'];
  const titles = ['One comment, four decisions','Read the comment','Model disagreement','Reference boundaries','Prompt changes','Latest decision models','Repeatability','Cost and quality','Practical implications','Limits and next steps'];
  const fields = ['sentiment','follow_up_needed','serious_concern_reported','testimonial_potential'];
  const labels = ['Sentiment','Follow-up needed','Serious concern reported','Testimonial potential'];
  const files = ['data-provider-errors-v1.json','disputed-reviews-v1.json','codex-fresh-repeats.json','extended-cases-v1.json','supplemental-decision-runs-v1.json','additional-cases-v1.json'];
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const readable = value => value === 'insufficient_information' ? 'Insufficient information' : String(value ?? 'Unavailable').replace(/_/g,' ');
  const explorer = (id, review) => `./index.html?run=${encodeURIComponent(id)}${review ? `&case=${encodeURIComponent(review)}` : ''}#inspect`;
  const source = (href, label) => `<a href="${esc(href)}">${esc(label)}</a>`;
  const sourceLine = content => `<p class="deck-source">${content}</p>`;
  const reveal = content => `<div class="deck-reveal" data-reveal>${content}</div>`;
  const quote = review => `<p class="deck-scope">${esc(review.id)} · Synthetic review</p><blockquote>${esc(review.feedback)}</blockquote>`;
  const fieldList = prediction => `<dl class="deck-fields">${fields.map((f,i) => `<div><dt>${labels[i]}</dt><dd>${esc(readable(prediction[f]))}</dd></div>`).join('')}</dl>`;
  const wrapTable = table => `<div class="deck-table-wrap" tabindex="0" aria-label="Scrollable answer table">${table}</div>`;
  const agrees = (prediction, reference) => fields.every(f => prediction?.[f] === reference[f]);
  const answersTable = (caption, rows, selectedFields = fields) => wrapTable(`<table><caption>${esc(caption)}</caption><thead><tr><th scope="col">Saved answer</th>${selectedFields.map(f => `<th scope="col">${labels[fields.indexOf(f)]}</th>`).join('')}</tr></thead><tbody>${rows.map(row => `<tr><td>${row.url ? source(row.url,row.name) : esc(row.name)}</td>${selectedFields.map(f => `<td${row.different?.includes(f) ? ' class="deck-difference"' : ''}>${esc(readable(row.prediction[f]))}</td>`).join('')}</tr>`).join('')}</tbody></table>`);
  function required(value, message) { if (!value) throw new Error(message); return value; }
  function buildSlides(data, disputed, fresh, extended, native, additional) {
    required(data.denominator === 60 && disputed.review_denominator === 60,'Expected the frozen 60-review dataset.');
    const testimonial = required(disputed.reviews.find(r => r.id === 'DEV-027'),'Missing DEV-027.');
    const offTopic = required(disputed.reviews.find(r => r.id === 'DEV-029'),'Missing DEV-029.');
    const models = new Map(disputed.models.map(m => [m.id,m]));
    const comparison = required(data.promptComparisons.find(p => p.id === 'openrouter-paid-gemma4-31b-off' && p.eligible),'Missing matched Gemma prompt comparison.');
    const repeat = required(fresh.series.find(s => s.configuration === 'codex-gpt-5.6-luna-xhigh' && s.method === 'fresh-matched-three'),'Missing fresh repeat study.');
    const repeatRuns = ['fresh1','fresh2','fresh3'].map(pass => required(extended.runs.find(r => r.runId === `extended-${repeat.configuration}-${pass}-p0`),'Missing source-bound repeat answers.'));
    const base = required(data.runs.find(r => r.id === comparison.id),'Missing prompt base run.');
    const thinking = required(data.runs.find(r => r.id === 'openrouter-paid-gemma4-31b-on'),'Missing cost pair.');
    required([base,thinking].every(r => r.complete && r.records === 60 && r.cost.actualUsd !== null),'Cost pair must have observed charges.');
    const selectedPromptCase = required(comparison.comparisons.P0_to_P1.cases.find(c => c.id === 'DEV-053'),'Missing changed prompt review.');
    const repeatPair = required(repeat.pairwiseFlips.find(p => p.condition === 'P0' && p.from === 'fresh1' && p.to === 'fresh2'),'Missing repeat pair.');
    const repeatCase = required(extended.cases.find(c => c.id === 'DEV-054'),'Missing repeated review.');
    const repeatAnswers = repeatRuns.slice(0,2).map((run,i) => ({name:`Fresh pass ${i+1}`,url:explorer(run.runId,repeatCase.id),prediction:required(run.cases.find(c => c.id === repeatCase.id),'Missing repeat prediction.').prediction}));
    const validShared = repeatRuns[0].cases.filter(c => c.status === 'ok' && repeatRuns[1].cases.some(other => other.id === c.id && other.status === 'ok'));
    const recomputedFlips = validShared.filter(c => !fields.every(f => c.prediction[f] === repeatRuns[1].cases.find(other => other.id === c.id).prediction[f]));
    required(validShared.length === repeatPair.denominator && recomputedFlips.length === repeatPair.fourFieldVector.changed,'Repeat projection does not reconcile.');
    const promptBars = ['P0_to_P1','P1_to_P2'].map(key => {
      const pair = comparison.comparisons[key];
      const gain = pair.allFourWrongToCorrect.length, loss = pair.allFourCorrectToWrong.length;
      const unchangedScore = pair.bothValid - gain - loss;
      return `<div class="deck-transfer"><div class="deck-transfer-label">${key.replace('_to_',' → ')}</div><div><div class="deck-bar" role="img" aria-label="${gain} gained all-four matches, ${loss} lost, ${unchangedScore} unchanged match status; ${pair.bothValid} shared-valid reviews"><span class="gain" style="width:${gain/pair.bothValid*100}%"></span><span class="loss" style="width:${loss/pair.bothValid*100}%"></span></div><p class="deck-key"><span class="gain-label">${gain} gained</span> · <span class="loss-label">${loss} lost</span> · ${unchangedScore} unchanged match status<br>${pair.changedRecordCount} reviews changed at least one label · ${pair.bothValid}/60 shared-valid</p></div></div>`;
    }).join('');
    const costMax = Math.max(Number(base.cost.actualUsd),Number(thinking.cost.actualUsd));
    const dollars = number => `$${Number(number).toFixed(8)}`;
    const conditions=['P0','P1','P2'],passes=['fresh1','fresh2','fresh3'];
    const selectedNative=[['Clef','clef-openrouter-native'],['Clef Flash','clef-flash-openrouter-native'],['Luna Decisions','luna-decisions-openrouter-native'],['Perplexity Decider','perplexity-decider-native']];
    const nativeRun=(prefix,pass,condition)=>required(native.runs.find(r=>r.id===`${prefix}-${pass}-${condition.toLowerCase()}`),'Missing selected native run.');
    required(selectedNative.every(([,prefix])=>conditions.every(c=>passes.every(pass=>nativeRun(prefix,pass,c).surface==='OpenRouter native Choice'))),'Selected native execution routes changed; review the slide claim.');
    const nativeTable=wrapTable(`<table><caption>All-four reference matches / 60. Each cell lists passes 1, 2 and 3 separately.</caption><thead><tr><th scope="col">Native model</th>${conditions.map(c=>`<th scope="col">${c}</th>`).join('')}</tr></thead><tbody>${selectedNative.map(([name,prefix])=>`<tr><th scope="row">${name}</th>${conditions.map(c=>`<td>${passes.map(pass=>{const r=nativeRun(prefix,pass,c);return source(explorer(r.id),String(r.metrics.all_four));}).join(' · ')}</td>`).join('')}</tr>`).join('')}</tbody></table>`);
    const flashFinal=nativeRun('clef-flash-openrouter-native','fresh3','P2');
    required(selectedNative.every(([,prefix])=>conditions.every(c=>passes.every(pass=>{const r=nativeRun(prefix,pass,c);return r.records===60&&(r.id===flashFinal.id||r.valid===60);}))), 'Selected native run denominators changed; review the slide claim.');
    const flashCases=required(additional.runs.find(r=>r.runId===flashFinal.id),'Missing Flash final answers.');
    const failures=flashCases.cases.filter(c=>c.status!=='ok');
    required(flashCases.cases.filter(c=>c.status==='ok').length===flashFinal.valid,'Flash usable-answer count does not reconcile.');
    const perRun=(pass,c)=>required(additional.runs.find(r=>r.runId===nativeRun('perplexity-decider-native',pass,c).id),'Missing Perplexity answers.');
    const stableConditions=conditions.filter(c=>passes.slice(1).every(pass=>perRun('fresh1',c).cases.every(answer=>{const other=perRun(pass,c).cases.find(a=>a.id===answer.id);return other&&other.status===answer.status&&fields.every(f=>other.prediction?.[f]===answer.prediction?.[f]);})));
    required(stableConditions.length===conditions.length,'Perplexity repeat stability changed; review the slide claim.');
    const changedPer=perRun('fresh1','P0').cases.filter(answer=>{const other=perRun('fresh1','P1').cases.find(a=>a.id===answer.id);return !fields.every(f=>other.prediction?.[f]===answer.prediction?.[f]);});
    const perReview=required(changedPer.find(c=>c.id==='DEV-029'),'Missing Perplexity prompt-change example.');
    const nativeStableNote=`Perplexity returned identical labels across its three repeats within each of ${stableConditions.length} prompt conditions. P0 → P1 still changed ${changedPer.length} review's labels.`;
    return {
      opening: `<div class="deck-actions">${source('./index.html#explore','Explore the saved runs')}${source('./index.html#review-evidence','Read individual reviews')}</div>`,
      task: `${quote(testimonial)}<p>Choose a sentiment. Decide whether someone should follow up, whether a serious concern was reported, and whether this could be a testimonial.</p>${reveal(`<p class="deck-scope">Frozen provisional reference v0.2 · Human-checked, with disputed cases</p>${fieldList(testimonial.reference)}<p class="deck-scope">The models received the comment and task instructions. Reference answers were used only for offline scoring.</p>`)}${sourceLine(`${source('./disputed-reviews-v1.json','Review text and reference')} · ${source(disputed.references_url,'Frozen labels')} · ${source(disputed.rubric_url,'Task rubric')}`)}`,
      disagreement: `<div class="deck-two-column"><div>${quote(testimonial)}<p class="deck-metric">${testimonial.models_with_any_mismatch}<small> / ${testimonial.eligible_model_count} models</small></p><p>Disagreed with the reference on at least one field.</p><p class="deck-scope">Seven distinct native Choice configurations. One fresh1/P0 pass per model, all using the same 60 reviews through OpenRouter. This is a selected cohort, not the whole benchmark.</p></div><div>${reveal(answersTable('Sentiment and testimonial decisions; orange text differs from the reference',[{name:'Provisional reference',prediction:testimonial.reference},...testimonial.answers.map(a => ({name:models.get(a.model_id).display_name,prediction:a.prediction,different:a.different_fields,url:explorer(a.model_id,testimonial.id)}))],['sentiment','testimonial_potential']))}</div></div>${sourceLine(`${source('./disputed-reviews-v1.json','Seven-model comparison and exact run sources')} · ${source('./index.html#review-evidence','Explore all four fields')}`)}`,
      boundary: `${quote(offTopic)}<p>The comment mentions a restaurant. Should a candidate-feedback classifier infer hiring labels from it?</p>${reveal(`<div class="deck-two-column"><div>${fieldList(offTopic.reference)}</div><div><p class="deck-metric">${offTopic.models_with_any_mismatch}<small> / ${offTopic.eligible_model_count}</small></p><p>Models disagreed with at least one reference field.</p><p class="deck-scope">The frozen reference uses insufficient information for all four fields. This disagreement also tests the task boundary. A different reference policy could change the scores.</p></div></div>`)}${sourceLine(`${source('./index.html#review-evidence','Inspect DEV-029 across the selected cohort')} · ${source('./disputed-reviews-v1.json','Saved predictions')} · ${source('./index.html#reference-sensitivity','Hypothetical reference sensitivity')}`)}`,
      prompts: `<p class="deck-scope">Gemma 4 31B · thinking off · OpenRouter · one matched saved pass per prompt · all-four reference matches / 60</p><div class="deck-score-row">${['P0','P1','P2'].map((c,i) => `<div>${source(explorer(base.id+(i ? `--${c.toLowerCase()}` : '')),c)}<strong>${comparison.conditions[c].all_four}<span> / 60</span></strong><span>${['Base task','Classifier instructions','Decision rules'][i]}</span></div>`).join('')}</div>${promptBars}${reveal(`${quote(selectedPromptCase)}${answersTable('A gained match elsewhere came with this lost match',[{name:'Reference',prediction:selectedPromptCase.reference},{name:'P0',prediction:selectedPromptCase.from_prediction,url:explorer(base.id,selectedPromptCase.id)},{name:'P1',prediction:selectedPromptCase.to_prediction,url:explorer(`${base.id}--p1`,selectedPromptCase.id)}],['sentiment','testimonial_potential'])}<p class="deck-scope">One pass does not establish a dependable prompt gain. Changed labels and changed match status are different counts.</p>`)}${sourceLine(`${source(comparison.evidenceUrl,'Matched prompt report and changed reviews')} · ${source('./data-provider-errors-v1.json','Same public calculations as the report')}`)}`,
      'decision-cohort': `<p class="deck-scope">Four selected native Choice configurations, all through OpenRouter. Model providers and prompt questions differ; each run retains its exact settings.</p>${nativeTable}<p class="deck-scope">Clef Flash's third P2 pass: ${flashFinal.metrics.all_four}/60 matches, ${flashFinal.valid}/60 usable answers, ${failures.length} failed position (${failures.map(c=>source(explorer(flashFinal.id,c.id),c.id)).join(', ')}). Its unresolved charge remains reserved. All other displayed runs have 60/60 usable answers.</p><p>Added instructions lowered Clef's agreement and raised Luna's P1 agreement. These directions belong to the selected configurations.</p>${reveal(`<p>${nativeStableNote} Stable repeats do not establish reference agreement.</p>${answersTable('Perplexity DEV-029: equal all-four totals, different field answers',conditions.slice(0,2).map(c=>({name:c,prediction:perRun('fresh1',c).cases.find(a=>a.id===perReview.id).prediction,url:explorer(nativeRun('perplexity-decider-native','fresh1',c).id,perReview.id)})),['sentiment','follow_up_needed'])}`)}${sourceLine(`${source('./supplemental-decision-runs-v1.json','Exact scores, outcomes and source reports')} · ${source('./additional-cases-v1.json','Saved answers for every displayed native run')}`)}`,
      repeatability: `<p class="deck-scope">GPT-5.6 Luna · xhigh effort · Codex subscription · three fresh matched P0 passes · all-four reference matches / 60</p><div class="deck-score-row">${repeatRuns.map((r,i) => `<div>${source(explorer(r.runId),`Pass ${i+1}`)}<strong>${r.scores.all_four}<span> / 60</span></strong><span>${r.scores.valid}/60 valid</span></div>`).join('')}</div><p class="deck-lede">Passes 1 and 2 have equal totals. ${repeatPair.fourFieldVector.changed}/${repeatPair.denominator} reviews changed at least one label.</p>${reveal(`${quote(repeatCase)}${answersTable('One repeated input, two saved follow-up decisions',[{name:'Reference',prediction:repeatCase.reference},...repeatAnswers],['follow_up_needed'])}<p class="deck-scope">Changed reviews: ${repeatPair.fourFieldVector.caseIds.map(id => source(explorer(repeatRuns[1].runId,id),id)).join(', ')}. Across all three P0 passes, ${repeat.changesAcrossThreePasses.P0.fourFieldVector.length}/${repeat.denominator} reviews changed labels. These are repeated observations of the same reviews.</p>`)}${sourceLine(`${source('./codex-fresh-repeats.json','Fresh study, pairwise flips and source hashes')} · ${repeatRuns.slice(0,2).map((r,i) => source(r.sourceRecordUrl,`Pass ${i+1} source records`)).join(' · ')} · ${source('./extended-cases-v1.json','Individual answers')}`)}`,
      cost: `<p class="deck-scope">Gemma 4 31B · OpenRouter · P0 · two saved thinking settings · observational comparison</p><div class="deck-cost-bars">${[base,thinking].map(r => `<div><p>${source(explorer(r.id),`Thinking ${r.effort}`)} · <strong>${r.metrics.all_four}/60</strong> all-four matches · ${r.valid}/60 valid<br><strong>${dollars(r.cost.actualUsd)}</strong> observed development charge</p><div class="deck-cost-bar" style="width:${Number(r.cost.actualUsd)/costMax*100}%" role="img" aria-label="Observed charge ${dollars(r.cost.actualUsd)}"></div></div>`).join('')}</div>${reveal(`<p>The higher observed charge produced the same all-four score in these two saved runs. The per-field answers still differed.</p><p class="deck-scope">Charges cover development attempts, excluding smoke. They are not a price forecast. Estimates, subscription price equivalents and unknown-charge reservations remain separate in the explorer.</p><p class="deck-scope">Median client request time: thinking off ${base.timing.medianSeconds.toFixed(2)}s; on ${thinking.timing.medianSeconds.toFixed(2)}s. These are end-to-end request durations, not pure inference time. Token counts and provider generation timing are in each run's detail.</p>`)}${sourceLine(`${source(base.evidenceUrl,'Thinking-off source')} · ${source(thinking.evidenceUrl,'Thinking-on source')} · ${source('./index.html#inspect','Cost, token and timing details')}`)}`,
      implications: `<p class="deck-lede">A label becomes useful when the team agrees what to do with it.</p><ol class="deck-practice"><li>Write down when to follow up and when to escalate a serious concern.</li><li>Review missed positive cases and false alarms field by field.</li><li>Repeat the same inputs before relying on a small score difference.</li><li>Keep a person responsible for contested labels and workflow decisions.</li></ol>${reveal(`<p>Then test representative real feedback with consent and a versioned reference. Measure the workflow's outcomes and costs.</p>`)}${sourceLine(`${source('./index.html#method','Task and evaluation method')} · ${source('./index.html#repeat-analysis','Repeat evidence')} · ${source('./index.html#explore','Per-field comparisons')}`)}`,
      limits: `<div class="deck-two-column"><div><p class="deck-metric">60<small> synthetic reviews</small></p><p>No independent new cases were added by repeating the study.</p><p class="deck-scope">The project owner confirmed human checking of the frozen v0.2 reference. Some labels remain disputed. Reference agreement is not real-world hiring accuracy.</p></div><div><p>Model routes, prompts, interfaces and runtime settings can differ. Compare exact configurations before drawing conclusions.</p><p>Invalid answers, provider failures, unavailable models and unknown charges remain visible in the report.</p>${reveal(`<p>Use these examples to choose what to test next. Validate with real feedback before using labels to guide candidate follow-up.</p>`)}</div></div><div class="deck-actions">${source('./index.html#explore','Open the full explorer')}${source('./index.html#review-evidence','Read the difficult reviews')}</div>${sourceLine(`${source('./index.html#method','Method and scope')} · ${source('https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/docs/REFERENCE_REVIEW_V1.md','Reference review history')} · ${files.map(f => source(`./${f}`,f)).join(' · ')}`)}`,
    };
  }
  function createNavigator(revealCounts, initial = {slide:0,step:0}) {
    let slide = Math.max(0,Math.min(ids.length-1,initial.slide || 0));
    let step = Math.max(0,Math.min(revealCounts[slide],initial.step || 0));
    const current = () => ({slide,step});
    return {current, next() { if (step < revealCounts[slide]) step++; else if (slide < ids.length-1) {slide++;step=0;} return current(); }, previous() {if(step>0)step--;else if(slide>0){slide--;step=revealCounts[slide];}return current();}, jump(index, at = 0) {slide=Math.max(0,Math.min(ids.length-1,index));step=Math.max(0,Math.min(revealCounts[slide],at));return current();}};
  }
  function parseHash(hash) { const match = /^#([^/]+)(?:\/(\d+))?$/.exec(hash || ''); const slide = match ? ids.indexOf(match[1]) : -1; return {slide:slide<0?0:slide,step:match ? Number(match[2] || 0) : 0}; }
  function mount(slideHTML) {
    const sections = ids.map(id => document.getElementById(id));
    ids.forEach(id => {document.querySelector(`[data-slide-content="${id}"]`).innerHTML=slideHTML[id];});
    const reveals = sections.map(s => [...s.querySelectorAll('[data-reveal]')]);
    const navigation = createNavigator(reveals.map(r => r.length),parseHash(location.hash));
    const previous = document.getElementById('deck-previous'), next = document.getElementById('deck-next'), chapter = document.getElementById('deck-chapter');
    chapter.innerHTML=titles.map((t,i) => `<option value="${i}">${i+1}. ${esc(t)}</option>`).join('');
    const paint = (writeUrl = true, focus = false) => {
      const {slide,step} = navigation.current();
      if(document.activeElement && sections.some((s,i) => i!==slide && s.contains(document.activeElement))) document.getElementById('deck-stage').focus({preventScroll:true});
      sections.forEach((section,i) => {section.hidden=i!==slide;reveals[i].forEach((item,j) => {item.hidden=j>=step;});});
      previous.disabled=slide===0&&step===0;
      next.disabled=slide===ids.length-1&&step===reveals[slide].length;
      next.textContent=step<reveals[slide].length?'Reveal →':'Next →';
      chapter.value=String(slide);
      document.getElementById('deck-progress').textContent=`${slide+1} / ${ids.length} · ${titles[slide]} · ${step<reveals[slide].length?'Answer hidden':'All shown'}`;
      if(writeUrl) history.replaceState(null,'',`${location.pathname}${location.search}#${ids[slide]}/${step}`);
      if(focus) {document.getElementById('deck-stage').focus({preventScroll:true});window.scrollTo({top:0,behavior:'instant'});}
    };
    previous.addEventListener('click',() => {navigation.previous();paint(true,true);});
    next.addEventListener('click',() => {navigation.next();paint(true,true);});
    chapter.addEventListener('change',() => {navigation.jump(Number(chapter.value));paint(true,true);});
    document.addEventListener('keydown',event => {
      if(event.altKey||event.ctrlKey||event.metaKey||event.target.closest('input,select,textarea,button,a,[contenteditable="true"],.deck-table-wrap'))return;
      if(['ArrowRight','ArrowDown','PageDown',' ','ArrowLeft','ArrowUp','PageUp','Home','End'].includes(event.key)) {
        event.preventDefault();
        if(['ArrowRight','ArrowDown','PageDown',' '].includes(event.key))navigation.next();
        else if(['ArrowLeft','ArrowUp','PageUp'].includes(event.key))navigation.previous();
        else navigation.jump(event.key==='Home'?0:ids.length-1);
        paint(true,true);
      }
    });
    window.addEventListener('hashchange',() => {const state=parseHash(location.hash);navigation.jump(state.slide,state.step);paint(false,true);});
    document.body.classList.add('deck-enhanced');
    document.querySelector('.deck-controls').hidden=false;
    document.getElementById('deck-load-status').hidden=true;
    paint(false);
    return navigation;
  }
  async function init() {
    try {
      const feeds = await Promise.all(files.map(async file => {const response=await fetch(`./${file}`);if(!response.ok)throw new Error(`Could not load ${file} (${response.status}).`);return response.json();}));
      mount(buildSlides(...feeds));
    } catch(error) {
      document.getElementById('deck-load-status').textContent=`The presentation could not load all its evidence. ${error.message} The questions and source links remain available.`;
      console.error(error);
    }
  }
  globalThis.MeetupPresentation = {buildSlides,createNavigator,parseHash,ids,files,mount};
  if(typeof document!=='undefined' && document.getElementById('deck-stage'))init();
})();
