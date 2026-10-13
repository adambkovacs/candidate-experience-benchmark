const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

const root=path.resolve(__dirname,'..');
const taxonomy=fs.readFileSync(path.join(root,'public-site/model-categories.js'),'utf8');
const navigation=fs.readFileSync(path.join(root,'public-site/report-navigation.js'),'utf8');

function mount(href='https://example.test/report?run=liquid-d1-native-fresh1-p0#inspect'){
  const callbacks=new Map(),historyUrls=[];
  const controls={};
  for(const id of ['category-filter','outcome-category','report-lens-count','report-lens-note']){
    controls[id]={value:'',textContent:'',callbacks:new Map(),addEventListener(type,callback){this.callbacks.set(type,callback);},dispatchEvent(event){this.callbacks.get(event.type)?.({target:this});}};
  }
  const buttons=['decision','general','all'].map(cohort=>({dataset:{cohort},attributes:{},addEventListener(type,callback){this.click=callback;},setAttribute(name,value){this.attributes[name]=value;}}));
  const context={URL,Event,CustomEvent:class {constructor(type,options){this.type=type;this.detail=options.detail;}},location:{href},history:{replaceState(_a,_b,url){historyUrls.push(url);}},
    document:{getElementById:id=>controls[id],querySelectorAll:()=>buttons},
    addEventListener(type,callback){callbacks.set(type,callback);},dispatchEvent(event){callbacks.get(event.type)?.(event);}};
  context.globalThis=context;
  vm.runInNewContext(taxonomy,context);
  vm.runInNewContext(navigation,context);
  return {context,controls,buttons,historyUrls};
}

test('deep-linked run opens all-model view and switching synchronizes both explorers',()=>{
  const ui=mount();
  const runs=[
    {id:'liquid-d1-native-fresh1-p0',model:'liquid/d1',complete:true,records:60,metrics:{all_four:43}},
    {id:'gpt-example',model:'gpt-6',complete:true,records:60,metrics:{all_four:42}},
    {id:'partial',model:'gpt-6',complete:false,records:59,metrics:{all_four:40}},
  ];
  ui.context.dispatchEvent({type:'benchmark:saved-runs-ready',detail:{runs}});
  assert.equal(ui.context.BenchmarkReportNavigation.getCohort(),'all');
  assert.equal(ui.controls['category-filter'].value,'');
  assert.equal(ui.controls['outcome-category'].value,'');
  assert.match(ui.controls['report-lens-count'].textContent,/Showing 2 runs\./);
  ui.buttons[0].click();
  assert.equal(ui.controls['category-filter'].value,'decision');
  assert.equal(ui.controls['outcome-category'].value,'decision');
  assert.equal(ui.buttons[0].attributes['aria-pressed'],'true');
  assert.match(ui.controls['report-lens-count'].textContent,/Showing 1 run\./);
  assert.ok(ui.historyUrls.at(-1).includes('run=liquid-d1-native-fresh1-p0#inspect'));
  ui.buttons[1].click();
  assert.equal(ui.controls['outcome-category'].value,'general');
  assert.ok(ui.historyUrls.at(-1).includes('cohort=general'));
});

test('default view is all models; explicit cohorts are preserved',()=>{
  assert.equal(mount('https://example.test/report').context.BenchmarkReportNavigation.getCohort(),'all');
  assert.equal(mount('https://example.test/report?cohort=decision').context.BenchmarkReportNavigation.getCohort(),'decision');
  assert.equal(mount('https://example.test/report?cohort=all&run=example').context.BenchmarkReportNavigation.getCohort(),'all');
});

test('advanced category changes keep chart, explorer and overview choice coherent',()=>{
  const ui=mount('https://example.test/report');
  const runs=[
    {id:'alex-openjev08-native-p0-v1',model:'AlexWortega/openjev',complete:true,records:60,metrics:{all_four:3}},
    {id:'gpt-example',model:'gpt-6',complete:true,records:60,metrics:{all_four:42}},
  ];
  ui.context.dispatchEvent({type:'benchmark:saved-runs-ready',detail:{runs}});
  ui.controls['category-filter'].value='tuned';
  ui.controls['category-filter'].dispatchEvent({type:'change'});
  assert.equal(ui.controls['outcome-category'].value,'tuned');
  assert.equal(ui.controls['category-filter'].value,'tuned');
  assert.ok(ui.buttons.every(button=>button.attributes['aria-pressed']==='false'));
  assert.match(ui.controls['report-lens-note'].textContent,/Custom category: Task-fine-tuned LLM/);
  assert.match(ui.controls['report-lens-count'].textContent,/Showing 1 run in this category\./);
  assert.ok(ui.historyUrls.at(-1).includes('category=tuned'));
  ui.buttons[2].click();
  assert.equal(ui.controls['category-filter'].value,'');
  assert.equal(ui.controls['outcome-category'].value,'');
  assert.equal(ui.buttons[2].attributes['aria-pressed'],'true');
});

test('markup routes readers to source evidence and does not call all reports a single cohort',()=>{
  const html=fs.readFileSync(path.join(root,'public-site/explore.html'),'utf8');
  assert.match(html,/id="report-cohort"/);
  for(const anchor of ['results','outcome-chart','hard-matrix','review-evidence','inspect','agreement-policy']) assert.match(html,new RegExp(`href="#${anchor}"`));
  // Benchmarks first; the older panels sit in one closed Earlier analyses block at the end, every id kept.
  const order=['results','decision-matrix','stability','cost-ledger','outcome-chart','hard-matrix','review-evidence','inspect','agreement-policy','reference-sensitivity','sources','earlier-analyses','report-lens','run-ranking','jev','models','usage','explore','story','cross-category','cohort-reviews','clef-first-pass','analysis-update','analysis-library','scores','how-it-works'];
  const at=order.map(id=>html.indexOf(`id="${id}"`));
  assert.ok(at.every(i=>i>0),order.filter((id,k)=>at[k]<0).join(','));
  assert.deepEqual([...at].sort((a,b)=>a-b),at);
  assert.match(html,/<details class="section earlier-analyses" id="earlier-analyses"[^>]*>(?![^]*<details class="section earlier-analyses")/);
  assert.doesNotMatch(html,/<details class="section earlier-analyses"[^>]*\bopen\b/);
});
