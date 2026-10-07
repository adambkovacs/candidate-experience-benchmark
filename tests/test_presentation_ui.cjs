const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const site = path.resolve(__dirname,'../public-site');
const read = name => JSON.parse(fs.readFileSync(path.join(site,name),'utf8'));
const script = fs.readFileSync(path.join(site,'meetup-presentation.js'),'utf8');
const context = {};
vm.runInNewContext(script,context);
const deck = context.MeetupPresentation;
const feeds = deck.files.map(read);
const slides = deck.buildSlides(...feeds);

test('all exhibits reconcile to existing public evidence and exact denominators',() => {
  assert.equal(Object.keys(slides).length,10);
  const review = feeds[1].reviews.find(r => r.id==='DEV-027');
  assert.equal(review.models_with_any_mismatch,review.answers.filter(a => a.different_fields.length).length);
  assert.match(slides.disagreement,/4<small> \/ 7 models/);
  assert.match(slides.disagreement,/one fresh1\/P0 pass per model/i);
  assert.match(slides.boundary,/7<small> \/ 7/);
  const pair = feeds[0].promptComparisons.find(p => p.id==='openrouter-paid-gemma4-31b-off');
  for(const [key,label] of [['P0_to_P1','P0 → P1'],['P1_to_P2','P1 → P2']]) {
    const p=pair.comparisons[key];
    const gain=p.allFourWrongToCorrect.length,loss=p.allFourCorrectToWrong.length;
    assert.ok(slides.prompts.includes(label));
    assert.ok(slides.prompts.includes(`${gain} gained all-four matches, ${loss} lost, ${p.bothValid-gain-loss} unchanged match status`));
    assert.ok(slides.prompts.includes(`${p.bothValid}/60 shared-valid`));
  }
  assert.match(slides.repeatability,/3\/60 reviews changed/);
  assert.match(slides.repeatability,/DEV-054/);
  assert.match(slides.repeatability,/55<span> \/ 60/);
  assert.match(slides.cost,/\$0\.00555500/);
  assert.match(slides.cost,/\$0\.01303944/);
  assert.match(slides.cost,/end-to-end request durations, not pure inference time/);
  assert.match(slides.limits,/not real-world hiring accuracy/);
});

test('every explorer link resolves to an actual saved run and review',() => {
  const catalog=read('extended-run-catalog-v1.json');
  const native=read('supplemental-decision-runs-v1.json');
  const runs = new Set([...feeds[0].runs,...catalog.runs,...native.runs].map(r => r.id));
  const reviews = new Set(feeds[3].cases.map(c => c.id));
  const links=[...Object.values(slides).join('').matchAll(/href="(\.\/index\.html\?[^\"]+)"/g)];
  assert.ok(links.length>=20);
  for(const [,encoded] of links) {
    const url=new URL(encoded.replace(/&amp;/g,'&'),'https://example.test/presentation.html');
    assert.ok(runs.has(url.searchParams.get('run')),`Missing run ${url.searchParams.get('run')}`);
    if(url.searchParams.has('case'))assert.ok(reviews.has(url.searchParams.get('case')));
    assert.equal(url.hash,'#inspect');
  }
});

test('recorded projections must reconcile before hiding the readable fallback',() => {
  const invalid=structuredClone(feeds);
  invalid[0].denominator=59;
  assert.throws(() => deck.buildSlides(...invalid),/60-review/);
  const inconsistent=structuredClone(feeds);
  const run=inconsistent[3].runs.find(r=>r.runId==='extended-codex-gpt-5.6-luna-xhigh-fresh2-p0');
  run.cases.find(c=>c.id==='DEV-054').prediction.follow_up_needed='no';
  assert.throws(() => deck.buildSlides(...inconsistent),/does not reconcile/);
});

test('navigation reveals before advancing, reverses a reveal, clamps links and reaches the ending',() => {
  const navigation=deck.createNavigator([0,1,1,1,1,1,1,1,1,1]);
  assert.deepEqual({...navigation.next()},{slide:1,step:0});
  assert.deepEqual({...navigation.next()},{slide:1,step:1});
  assert.deepEqual({...navigation.previous()},{slide:1,step:0});
  assert.deepEqual({...navigation.previous()},{slide:0,step:0});
  assert.deepEqual({...navigation.jump(50,50)},{slide:9,step:1});
  assert.deepEqual({...navigation.next()},{slide:9,step:1});
  assert.deepEqual({...deck.parseHash('#repeatability/1')},{slide:6,step:1});
  assert.deepEqual({...deck.parseHash('#unknown/100')},{slide:0,step:100});
});

function runtimeMount(hash='#task/0') {
  const listeners={document:{},window:{}};
  const elements = new Map();
  function element(id) {
    const e={id,hidden:false,textContent:'',value:'',disabled:false,handlers:{},children:[],
      addEventListener(name,fn){this.handlers[name]=fn;},
      focus(){document.activeElement=this;},
      contains(target){return target===this || this.children.includes(target);},
      querySelectorAll(){return this.children;},
      closest(){return null;}};
    elements.set(id,e);return e;
  }
  const sections=deck.ids.map(id=>element(id));
  for(const id of deck.ids) {
    const content=element(`content-${id}`);
    Object.defineProperty(content,'innerHTML',{set(html){content.html=html;elements.get(id).children=[...html.matchAll(/data-reveal/g)].map((_,i)=>element(`${id}-reveal-${i}`));}});
  }
  for(const id of ['deck-stage','deck-previous','deck-next','deck-chapter','deck-progress','deck-load-status','controls'])element(id);
  const document={body:{classList:{add(value){this.value=value;}}},activeElement:null,
    getElementById(id){return id==='deck-stage' && !this.ready?null:elements.get(id);},
    querySelector(selector){if(selector==='.deck-controls')return elements.get('controls');return elements.get(`content-${/data-slide-content="([^"]+)"/.exec(selector)[1]}`);},
    addEventListener(name,fn){listeners.document[name]=fn;}};
  const ctx={document,location:{hash,pathname:'/presentation.html',search:''},history:{replaceState(a,b,url){this.url=url;}},window:{addEventListener(name,fn){listeners.window[name]=fn;},scrollTo(){}},console};
  vm.runInNewContext(script,ctx);
  document.ready=true;
  ctx.MeetupPresentation.mount(slides);
  return {ctx,elements,sections,listeners,key(key,target=elements.get('deck-stage')){const e={key,target,preventDefault(){this.prevented=true;}};listeners.document.keydown(e);return e;}};
}

test('mounted navigation supports keys, direct links, progressive reveals and interactive controls',() => {
  const {ctx,elements,sections,key,listeners}=runtimeMount();
  assert.equal(sections.filter(s=>!s.hidden).length,1);
  assert.equal(elements.get('task').hidden,false);
  assert.equal(elements.get('task-reveal-0').hidden,true);
  assert.equal(key('ArrowRight').prevented,true);
  assert.equal(elements.get('task-reveal-0').hidden,false);
  assert.match(ctx.history.url,/#task\/1$/);
  assert.equal(key(' ').prevented,true);
  assert.equal(elements.get('disagreement').hidden,false);
  assert.equal(key('ArrowLeft').prevented,true);
  assert.equal(elements.get('task').hidden,false);
  const interactive={closest(){return {};}};
  assert.equal(key('ArrowRight',interactive).prevented,undefined);
  assert.equal(elements.get('task').hidden,false);
  const scrollRegion={closest(selector){return selector.includes('.deck-table-wrap')?{}:null;}};
  assert.equal(key('ArrowRight',scrollRegion).prevented,undefined);
  assert.equal(elements.get('task').hidden,false);
  assert.match(ctx.history.url,/#task\/1$/);
  key('End');assert.equal(elements.get('limits').hidden,false);
  key('Home');assert.equal(elements.get('opening').hidden,false);
  assert.equal(elements.get('deck-previous').disabled,true);
  ctx.location.hash='#repeatability/1';listeners.window.hashchange();
  assert.equal(elements.get('repeatability').hidden,false);
  assert.equal(elements.get('repeatability-reveal-0').hidden,false);
  elements.get('deck-previous').handlers.click();
  assert.equal(elements.get('repeatability-reveal-0').hidden,true);
  elements.get('deck-chapter').value='4';elements.get('deck-chapter').handlers.change();
  assert.equal(elements.get('prompts').hidden,false);
  assert.equal(elements.get('deck-load-status').hidden,true);
});

test('latest decision cohort preserves every pass, Flash failure and within-prompt repeat scope',()=>{
  const html=slides['decision-cohort'];
  const supplemental=feeds[4],answers=feeds[5];
  const prefixes=['clef-openrouter-native','clef-flash-openrouter-native','luna-decisions-openrouter-native','perplexity-decider-native'];
  for(const prefix of prefixes)for(const pass of ['fresh1','fresh2','fresh3'])for(const c of ['p0','p1','p2']) {
    const run=supplemental.runs.find(r=>r.id===`${prefix}-${pass}-${c}`);
    assert.ok(html.includes(`run=${run.id}#inspect">${run.metrics.all_four}</a>`));
  }
  assert.match(html,/45\/60 matches, 59\/60 usable answers, 1 failed position/);
  assert.match(html,/DEV-039/);
  assert.match(html,/identical labels across its three repeats within each of 3 prompt conditions/);
  assert.match(html,/P0 → P1 still changed 1 review's labels/);
  const r0=answers.runs.find(r=>r.runId==='perplexity-decider-native-fresh1-p0');
  const r1=answers.runs.find(r=>r.runId==='perplexity-decider-native-fresh1-p1');
  const fields=['sentiment','follow_up_needed','serious_concern_reported','testimonial_potential'];
  const changed=r0.cases.filter(a=>!fields.every(f=>a.prediction[f]===r1.cases.find(b=>b.id===a.id).prediction[f]));
  assert.deepEqual(changed.map(c=>c.id),['DEV-029']);
  assert.match(html,/all through OpenRouter/);
  const per=supplemental.runs.find(r=>r.id==='perplexity-decider-native-fresh1-p0');
  assert.equal(per.provider,'Perplexity');
  assert.equal(per.surface,'OpenRouter native Choice');
  assert.ok(!html.includes('direct API'));
  const changedRoute=structuredClone(feeds);
  changedRoute[4].runs.find(r=>r.id===per.id).surface='Perplexity direct API';
  assert.throws(()=>deck.buildSlides(...changedRoute),/execution routes changed/);
});

test('a focused horizontal table keeps arrow keys for native scrolling',()=>{
  const {elements,key,ctx}=runtimeMount('#prompts/1');
  const region={closest(selector){return selector.includes('.deck-table-wrap')?{}:null;}};
  for(const direction of ['ArrowRight','ArrowLeft']) {
    assert.equal(key(direction,region).prevented,undefined);
    assert.equal(elements.get('prompts').hidden,false);
    assert.equal(elements.get('prompts-reveal-0').hidden,false);
    assert.equal(ctx.history.url,undefined);
  }
});

test('markup has source fallbacks and scoped mobile, motion and print styles',() => {
  const html=fs.readFileSync(path.join(site,'presentation.html'),'utf8');
  const css=fs.readFileSync(path.join(site,'meetup-presentation.css'),'utf8');
  for(const id of deck.ids)assert.ok(html.includes(`id="${id}"`));
  assert.match(html,/<noscript>/);
  assert.match(html,/aria-live="polite"/);
  assert.match(css,/@media\(prefers-reduced-motion:reduce\)/);
  assert.match(css,/@media\(max-width:760px\)/);
  assert.match(css,/@media print/);
  assert.match(css,/\.meetup-deck \[hidden\]/);
  assert.ok(!html.includes('href="./presentation.css"'));
});

test('a failed feed keeps the source fallback readable and reports the exact unavailable file',async () => {
  const status={hidden:false,textContent:''},stage={},controls={hidden:true};
  const errors=[];
  const ctx={document:{getElementById(id){return id==='deck-stage'?stage:status;},querySelector(){return controls;}},
    fetch:async url=>({ok:false,status:503,json:async()=>({})}),console:{error(e){errors.push(e.message);}}};
  vm.runInNewContext(script,ctx);
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(controls.hidden,true);
  assert.equal(status.hidden,false);
  assert.match(status.textContent,/data-provider-errors-v1\.json \(503\)/);
  assert.match(status.textContent,/source links remain available/);
  assert.equal(errors.length,1);
});
