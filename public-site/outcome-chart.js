/* One point is one coordinate shared by one or more closed saved runs. */
(() => {
  'use strict';
  const root=document.getElementById('outcome-chart');
  if(!root) return;
  const $=id=>document.getElementById(id);
  const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const categoryApi=globalThis.BenchmarkCategories;
  const sourcePrefix='https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/';
  let all=[],excluded=0,selectedId=null;

  function prepare(feed){
    if(feed?.denominator!==60 || !Array.isArray(feed.runs) || !categoryApi?.classify) throw Error('Saved-run source unavailable');
    const seen=new Set(),closed=[];
    let omitted=0;
    for(const run of feed.runs){
      if(!run || typeof run.id!=='string' || !run.id || seen.has(run.id)) throw Error('Duplicate or missing run ID');
      seen.add(run.id);
      if(run.complete!==true || run.records!==60){omitted++;continue;}
      const x=run.valid,y=run.metrics?.all_four;
      const source=run.sourceOnlyDetails ? run.sourceRecordsUrl : run.sourceRecordsUrl || run.evidenceUrl;
      if(!['P0','P1','P2'].includes(run.condition) || !Number.isInteger(x) || !Number.isInteger(y) || x<0 || x>60 || y<0 || y>x ||
        typeof source!=='string' || !source.startsWith(sourcePrefix)) throw Error('Closed run lacks a verifiable chart measure or source');
      closed.push({...run,chartSourceUrl:source,category:categoryApi.classify(run)});
    }
    return {closed,excluded:omitted};
  }
  function group(rows){
    const points=new Map();
    for(const run of rows){
      const key=`${run.valid}:${run.metrics.all_four}`;
      if(!points.has(key)) points.set(key,{key,valid:run.valid,matches:run.metrics.all_four,runs:[]});
      points.get(key).runs.push(run);
    }
    return [...points.values()].sort((a,b)=>b.matches-a.matches || b.valid-a.valid);
  }
  function filtered(){
    const condition=$('outcome-condition').value,category=$('outcome-category').value;
    return all.filter(run=>(condition==='all'||run.condition===condition) && (!category||(run.category.categories || [run.category.category]).includes(category)));
  }
  function showRun(point){
    const select=$('outcome-run');
    const chosen=point.runs.find(run=>run.id===select.value) || point.runs[0];
    if(!chosen) return;
    selectedId=chosen.id;
    const type=chosen.category;
    $('outcome-run-detail').innerHTML=`<p class="outcome-run-title"><strong>${esc(chosen.model)}</strong><span>${esc(chosen.condition)} · ${esc(chosen.surface||'Route unavailable')}</span></p><dl><div><dt>Valid answers</dt><dd>${chosen.valid} / 60</dd></div><div><dt>All four match</dt><dd>${chosen.metrics.all_four} / 60</dd></div><div><dt>Model category</dt><dd>${esc(type.categoryLabel)}</dd></div><div><dt>Output interface</dt><dd>${esc(type.interfaceLabel)}</dd></div></dl><p class="outcome-run-id">Exact run: ${esc(chosen.id)}</p><div class="outcome-links"><a href="${esc(chosen.chartSourceUrl)}" target="_blank" rel="noopener noreferrer">Open this run's saved source ↗</a><a href="?run=${encodeURIComponent(chosen.id)}#inspect">Inspect this run's comments →</a><a href="#review-evidence">Compare seven native P0 case answers →</a></div>`;
  }
  function selectPoint(point){
    $('outcome-point-title').textContent=`${point.valid}/60 valid · ${point.matches}/60 all four match`;
    $('outcome-point-count').textContent=`${point.runs.length} ${point.runs.length===1?'run':'runs'} at this point. Choose a run to see its source.`;
    const sorted=[...point.runs].sort((a,b)=>String(a.model).localeCompare(String(b.model))||a.id.localeCompare(b.id));
    $('outcome-run').innerHTML=sorted.map(run=>`<option value="${esc(run.id)}">${esc(run.model)} · ${esc(run.condition)} · ${esc(run.id)}</option>`).join('');
    $('outcome-run').value=sorted.some(run=>run.id===selectedId)?selectedId:sorted[0].id;
    $('outcome-coordinate').value=point.key;
    $('outcome-plot').querySelectorAll('[data-point]').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.point===point.key)));
    showRun(point);
  }
  function render(){
    const rows=filtered(),points=group(rows);
    $('outcome-count').textContent=`${rows.length} closed runs shown at ${points.length} plotted points. ${excluded} partial ${excluded===1?'run is':'runs are'} excluded.`;
    $('outcome-coordinate').innerHTML=points.length
      ?points.map(point=>`<option value="${esc(point.key)}">${point.valid}/60 valid · ${point.matches}/60 match · ${point.runs.length} ${point.runs.length===1?'run':'runs'}</option>`).join('')
      :'<option value="">No matching points</option>';
    $('outcome-plot').innerHTML=points.map(point=>{
      const categories=[...new Set(point.runs.flatMap(run=>run.category.categories || [run.category.category]))];
      const type=categories.length===1?categories[0]:'mixed';
      return `<button type="button" class="outcome-point" data-point="${esc(point.key)}" data-category="${esc(type)}" style="left:${(point.valid/60*100).toFixed(4)}%;bottom:${(point.matches/60*100).toFixed(4)}%" aria-label="${point.valid} of 60 valid; ${point.matches} of 60 all four match; ${point.runs.length} ${point.runs.length===1?'run':'runs'}" aria-pressed="false">${point.runs.length>1?`<span aria-hidden="true">${point.runs.length}</span>`:''}</button>`;
    }).join('');
    $('outcome-plot').querySelectorAll('[data-point]').forEach(button=>button.addEventListener('click',()=>{
      const point=points.find(item=>item.key===button.dataset.point);
      if(point) selectPoint(point);
    }));
    if(!points.length){
      selectedId=null;
      $('outcome-point-title').textContent='No closed runs match these filters.';
      $('outcome-point-count').textContent='Choose another prompt or category.';
      $('outcome-run').innerHTML='';$('outcome-run-detail').innerHTML='';return;
    }
    const selected=points.find(point=>point.runs.some(run=>run.id===selectedId)) || points.find(point=>point.key==='60:0') || points[0];
    selectPoint(selected);
  }
  function init(feed){
    try{
      const prepared=prepare(feed);
      all=prepared.closed;excluded=prepared.excluded;
      const categories=categoryApi.categories;
      $('outcome-category').innerHTML='<option value="">All categories</option>'+Object.entries(categories).map(([key,name])=>`<option value="${esc(key)}">${esc(name)}</option>`).join('');
      $('outcome-category').addEventListener('change',render);
      $('outcome-condition').addEventListener('change',render);
      $('outcome-coordinate').addEventListener('change',()=>{
        const point=group(filtered()).find(item=>item.key===$('outcome-coordinate').value);
        if(point) selectPoint(point);
      });
      $('outcome-run').addEventListener('change',()=>{
        const run=all.find(item=>item.id===$('outcome-run').value);
        if(run){const point=group(filtered()).find(item=>item.runs.some(value=>value.id===run.id));if(point)showRun(point);}
      });
      render();
    }catch{
      $('outcome-count').textContent='Chart unavailable because its saved-run source could not be verified.';
      $('outcome-point-title').textContent='Chart unavailable';
      $('outcome-point-count').textContent='Use the saved-run explorer below to inspect the source records.';
    }
  }
  globalThis.OutcomeChart=Object.freeze({prepare,group});
  globalThis.addEventListener('benchmark:saved-runs-ready',event=>init(event.detail),{once:true});
  globalThis.addEventListener('benchmark:saved-runs-error',()=>{
    $('outcome-count').textContent='Chart unavailable because the saved-run explorer could not load its source.';
    $('outcome-point-title').textContent='Chart unavailable';
  },{once:true});
})();
