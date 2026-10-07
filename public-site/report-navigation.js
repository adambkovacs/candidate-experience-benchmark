/* A shared category choice for the public saved-run views. */
(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  const values=new Set(['decision','general','all']);
  const search=new URL(location.href).searchParams;
  let cohort=values.has(search.get('cohort')) ? search.get('cohort') : search.has('run') ? 'all' : 'decision';
  const advanced=new Set(['tuned','rules','unknown']);
  let customCategory=advanced.has(search.get('category')) ? search.get('category') : '';
  if(customCategory) cohort='all';
  let ready=false;
  let runs=[];
  let syncing=false;

  function savedCount(rows,choice){
    if(!globalThis.BenchmarkCategories?.classify) return 0;
    return rows.filter(run=>run.complete===true && run.records===60 && Number.isInteger(run.metrics?.all_four) &&
      (choice==='all'||globalThis.BenchmarkCategories.classify(run).categories.includes(choice))).length;
  }
  function updateUrl(){
    const address=new URL(location.href);
    if(cohort==='decision') address.searchParams.delete('cohort');
    else address.searchParams.set('cohort',cohort);
    if(customCategory) address.searchParams.set('category',customCategory);
    else address.searchParams.delete('category');
    history.replaceState(null,'',address.pathname+address.search+address.hash);
  }
  function paint(){
    document.querySelectorAll('#report-cohort [data-cohort]').forEach(button=>button.setAttribute('aria-pressed',String(!customCategory&&button.dataset.cohort===cohort)));
    if(ready){
      const count=savedCount(runs,customCategory||cohort);
      $('report-lens-count').textContent=`${count} closed saved ${count===1?'run':'runs'} ${customCategory?'in this custom category':'in this view'} · the same 60 reviews per run`;
    }
    $('report-lens-note').textContent=customCategory
      ? `Custom category: ${globalThis.BenchmarkCategories?.categories?.[customCategory]||customCategory}. The chart, ranking and run explorer use this same filter. Choose a view above to reset it.`
      : cohort==='all'
      ? 'All models here means the merged saved-run explorer. Prompt, repeat and other report-only evidence remains in the detailed sections below. Each repeat reuses the same 60 reviews.'
      : 'A model can appear in more than one category. Each run appears once within a view; repeat passes reuse the same 60 reviews.';
  }
  function syncControls(){
    if(!ready) return;
    syncing=true;
    for(const id of ['category-filter','outcome-category']){
      const control=$(id);
      if(control){control.value=customCategory||(cohort==='all'?'':cohort);control.dispatchEvent(new Event('change',{bubbles:true}));}
    }
    syncing=false;
  }
  function setCohort(next,{fromControl=false}={}){
    if(!values.has(next)) return false;
    cohort=next;customCategory='';
    paint();updateUrl();
    if(!fromControl) syncControls();
    globalThis.dispatchEvent(new CustomEvent('benchmark:cohortchange',{detail:{cohort,category:customCategory}}));
    return true;
  }
  function reflectControl(event){
    if(syncing) return;
    const value=event.target.value;
    if(value==='decision'||value==='general'||value===''){
      setCohort(value||'all');
    }else if(advanced.has(value)){
      cohort='all';customCategory=value;paint();updateUrl();syncControls();
      globalThis.dispatchEvent(new CustomEvent('benchmark:cohortchange',{detail:{cohort,category:customCategory}}));
    }
  }
  document.querySelectorAll('#report-cohort [data-cohort]').forEach(button=>button.addEventListener('click',()=>setCohort(button.dataset.cohort)));
  globalThis.addEventListener('benchmark:saved-runs-ready',event=>{
    runs=event.detail.runs;ready=true;
    for(const id of ['category-filter','outcome-category']) $(id)?.addEventListener('change',reflectControl);
    paint();syncControls();
    globalThis.dispatchEvent(new CustomEvent('benchmark:cohortchange',{detail:{cohort,category:customCategory,initial:true}}));
  },{once:true});
  globalThis.addEventListener('benchmark:saved-runs-error',()=>{$('report-lens-count').textContent='The saved-run view could not load. Source reports remain linked below.';},{once:true});
  globalThis.BenchmarkReportNavigation=Object.freeze({getCohort:()=>cohort,setCohort,savedCount});
  paint();
})();
