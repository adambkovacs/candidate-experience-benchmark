/* Source-bound first P0 answers for the selected seven native decision-model cohort. */
(() => {
  'use strict';
  const $=id=>document.getElementById(id);
  const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const fields=['sentiment','follow_up_needed','serious_concern_reported','testimonial_potential'];
  const fieldNames=['Experience','Follow-up','Serious concern','Testimonial'];
  const sourcePrefix='https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/';
  let source=null,selected=null;

  function validate(data){
    if(data?.schema!=='disputed-reviews-v1'||data.review_denominator!==60||data.model_denominator!==7||
      !Array.isArray(data.reviews)||data.reviews.length!==60||!Array.isArray(data.models)||data.models.length!==7||
      !['public-site/supplemental-decision-runs-v1.json','data/pilot/inputs.jsonl','data/pilot/proposed_labels.jsonl'].every(key=>/^[a-f0-9]{64}$/.test(data.source_sha256?.[key]||''))||
      ![data.inputs_url,data.references_url,data.rubric_url].every(value=>typeof value==='string'&&value.startsWith(sourcePrefix))) throw Error('Review source header is incomplete');
    const modelIds=new Set(data.models.map(model=>model.id));
    const reviewIds=new Set();
    if(modelIds.size!==7||data.models.some(model=>model.condition!=='P0'||model.repeat_pass!=='fresh1'||
      model.eligible_reviews!==60||typeof model.display_name!=='string'||!model.source_url?.startsWith(sourcePrefix)||
      !/^[a-f0-9]{64}$/.test(model.source_sha256||''))) throw Error('Review model identity is incomplete');
    for(const review of data.reviews){
      if(!/^DEV-\d{3}$/.test(review.id||'')||reviewIds.has(review.id)||typeof review.feedback!=='string'||
        review.eligible_model_count!==7||!Array.isArray(review.answers)||review.answers.length!==7||
        fields.some(field=>typeof review.reference?.[field]!=='string')) throw Error('Review row is incomplete');
      reviewIds.add(review.id);
      const answerIds=new Set();
      for(const answer of review.answers){
        if(!modelIds.has(answer.model_id)||answerIds.has(answer.model_id)||
          fields.some(field=>typeof answer.prediction?.[field]!=='string')||
          !Array.isArray(answer.different_fields)||
          fields.some(field=>answer.different_fields.includes(field)!==(answer.prediction[field]!==review.reference[field]))) throw Error('Review answer mismatch is inconsistent');
        answerIds.add(answer.model_id);
      }
      if(review.models_with_any_mismatch!==review.answers.filter(answer=>answer.different_fields.length).length||
        review.reference_testimonial_positive!==(review.reference.testimonial_potential==='yes')) throw Error('Review counts are inconsistent');
    }
    return data;
  }
  function filterReviews(data,{search='',subset='all',model='',field=''}={}){
    const needle=search.trim().toLocaleLowerCase();
    return data.reviews.filter(review=>{
      if(needle&&!`${review.id} ${review.feedback}`.toLocaleLowerCase().includes(needle)) return false;
      if(subset==='any'&&review.models_with_any_mismatch===0) return false;
      if(subset==='testimonial'&&!review.reference_testimonial_positive) return false;
      if(subset==='off-topic'&&!review.off_topic) return false;
      if(field){
        const answers=model?review.answers.filter(answer=>answer.model_id===model):review.answers;
        if(!answers.some(answer=>answer.different_fields.includes(field))) return false;
      }
      return true;
    });
  }
  function settings(){return {search:$('disputed-search').value,subset:$('disputed-subset').value,model:$('disputed-model').value,field:$('disputed-field').value};}
  function reviewUrl(id){const address=new URL(location.href);address.searchParams.set('review',id);address.hash='review-evidence';return address.pathname+address.search+address.hash;}
  function persistFilters(){
    const address=new URL(location.href),choice=settings();
    for(const [key,value] of [['reviewSubset',choice.subset==='all'?'':choice.subset],['reviewModel',choice.model],['reviewField',choice.field],['reviewSearch',choice.search]]){
      if(value) address.searchParams.set(key,value);
      else address.searchParams.delete(key);
    }
    if(selected) address.searchParams.set('review',selected);
    else address.searchParams.delete('review');
    history.replaceState(null,'',address.pathname+address.search+address.hash);
  }
  function renderDetail(review,focus){
    const modelById=new Map(source.models.map(model=>[model.id,model]));
    const referenceCells=fields.map(field=>`<td><code>${esc(review.reference[field])}</code></td>`).join('');
    const rows=review.answers.map(answer=>{
      const model=modelById.get(answer.model_id);
      return `<tr${focus===model.id?' class="focused"':''}><th scope="row"><a href="${esc(model.source_url)}" target="_blank" rel="noopener noreferrer">${esc(model.display_name)} ↗</a><small>${esc(model.id)} · <a href="?run=${encodeURIComponent(model.id)}#inspect">Run detail →</a></small></th>${fields.map(field=>`<td${answer.different_fields.includes(field)?' class="differs"':''}><code>${esc(answer.prediction[field])}</code>${answer.different_fields.includes(field)?'<span class="diff-word">Differs</span>':''}</td>`).join('')}</tr>`;
    }).join('');
    $('disputed-detail').innerHTML=`<div class="disputed-detail-head"><p class="eyebrow">${esc(review.id)} / Saved comment</p><a href="${esc(reviewUrl(review.id))}" class="disputed-share">Link to this review ↗</a></div><blockquote>${esc(review.feedback)}</blockquote><p class="disputed-case-note">${review.models_with_any_mismatch} of ${review.eligible_model_count} selected configurations differ on at least one answer.${review.off_topic?' The frozen reference treats this restaurant review as off-topic.':''}${review.id==='DEV-030'?' The reference resolution of this accessibility and assessment comment remains a judgment call.':''}</p><div class="disputed-answer-wrap"><table><caption>Exact saved answers; “Differs” means different from the frozen reference, not a proven model error.</caption><thead><tr><th scope="col">Source</th>${fieldNames.map(name=>`<th scope="col">${esc(name)}</th>`).join('')}</tr></thead><tbody><tr class="reference"><th scope="row">Frozen reference<small>Provisional answer key</small></th>${referenceCells}</tr>${rows}</tbody></table></div><details class="disputed-sources"><summary>Source records and hashes</summary><p><a href="${esc(source.inputs_url)}" target="_blank" rel="noopener noreferrer">Original comments ↗</a> · <a href="${esc(source.references_url)}" target="_blank" rel="noopener noreferrer">Frozen references ↗</a> · <a href="${esc(source.rubric_url)}" target="_blank" rel="noopener noreferrer">Review rubric ↗</a></p><ul><li>Original comments <code>SHA-256 ${esc(source.source_sha256['data/pilot/inputs.jsonl'])}</code></li><li>Frozen references <code>SHA-256 ${esc(source.source_sha256['data/pilot/proposed_labels.jsonl'])}</code></li>${source.models.map(model=>`<li><a href="${esc(model.source_url)}" target="_blank" rel="noopener noreferrer">${esc(model.display_name)} saved answers ↗</a> <code>SHA-256 ${esc(model.source_sha256)}</code></li>`).join('')}</ul></details>`;
  }
  function render(){
    if(!source) return;
    const choice=settings(),rows=filterReviews(source,choice);
    if(!rows.some(row=>row.id===selected)) selected=rows[0]?.id||null;
    $('disputed-count').textContent=`${rows.length} of 60 reviews shown · seven distinct P0 first-pass models per review${choice.model?' · focus model highlighted':''}.`;
    $('disputed-list').innerHTML=rows.length?rows.map(review=>`<button type="button" data-review="${esc(review.id)}" aria-pressed="${review.id===selected}"><span class="disputed-list-meta"><strong>${esc(review.id)}</strong><span>${review.models_with_any_mismatch} / 7 differ</span></span><span class="disputed-excerpt">${esc(review.feedback)}</span><small>${review.reference_testimonial_positive?'Testimonial: yes · ':''}${review.off_topic?'Off-topic in reference · ':''}${review.distinct_fields_with_mismatch} of 4 fields differ</small></button>`).join(''):'<p class="disputed-empty">No reviews match these controls. Change the search or filters to see more of the 60 saved comments.</p>';
    $('disputed-list').querySelectorAll('[data-review]').forEach(button=>button.addEventListener('click',()=>{selected=button.dataset.review;history.replaceState(null,'',reviewUrl(selected));render();}));
    const review=rows.find(row=>row.id===selected);
    if(review) renderDetail(review,choice.model);
    else $('disputed-detail').innerHTML='<p>Choose another filter to see the exact saved answers.</p>';
  }
  async function init(){
    try{
      const response=await fetch('./disputed-reviews-v1.json',{cache:'no-store'});
      if(!response.ok) throw Error(`HTTP ${response.status}`);
      source=validate(await response.json());
      $('disputed-model').innerHTML='<option value="">All seven models</option>'+source.models.map(model=>`<option value="${esc(model.id)}">${esc(model.display_name)}</option>`).join('');
      const query=new URL(location.href).searchParams;
      if(['all','any','testimonial','off-topic'].includes(query.get('reviewSubset'))) $('disputed-subset').value=query.get('reviewSubset');
      if(source.models.some(model=>model.id===query.get('reviewModel'))) $('disputed-model').value=query.get('reviewModel');
      if(fields.includes(query.get('reviewField'))) $('disputed-field').value=query.get('reviewField');
      if(query.get('reviewSearch')) $('disputed-search').value=query.get('reviewSearch').slice(0,200);
      const requested=query.get('review');
      selected=source.reviews.find(review=>review.id===requested)?.id||source.reviews[0].id;
      const update=()=>{render();persistFilters();};
      $('disputed-search').addEventListener('input',update);
      for(const id of ['disputed-subset','disputed-model','disputed-field']) $(id).addEventListener('change',update);
      render();
    }catch(error){
      $('disputed-count').textContent='Review comparison unavailable because its source could not be verified.';
      $('disputed-detail').innerHTML='<p>The saved-answer view could not load. Use the linked source reports below.</p>';
      console.error('Review comparison source error:',error);
    }
  }
  globalThis.BenchmarkDisputedReviews=Object.freeze({validate,filterReviews,reviewUrl});
  if($('review-evidence')) init();
})();
