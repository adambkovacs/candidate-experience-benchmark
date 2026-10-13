/* Cost of one pass (log x) against all-four matches of 60 (y). A marker is one pass, or the passes that would otherwise overlap. */
(() => {
  'use strict';
  const root=document.getElementById('outcome-chart');
  if(!root) return;
  const $=id=>document.getElementById(id);
  const esc=value=>String(value??'').replace(/[&<>"']/g,ch=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const n=v=>v===null||v===undefined||v===''||!Number.isFinite(Number(v))?null:Number(v);
  const L=globalThis.BM_LABEL||globalThis.window?.BM_LABEL;
  const categoryApi=globalThis.BenchmarkCategories;
  const pricingLoad=typeof fetch==='function'
    ? Promise.resolve().then(()=>fetch('./subscription-price-estimates.json',{cache:'no-store'})).then(r=>r.ok?r.json():null).catch(()=>null)
    : Promise.resolve(null);
  let pricing=null,plotted=[],unpriced=[],selectedId=null,points=[],lastWidth=0;

  // Provider charge first; else the API-rate equivalent: the subscription price estimate, then the run's own figure (same rule as the run list).
  function passCost(run){
    const charge=n(run.cost?.knownUsd)??n(run.cost?.actualUsd);
    if(charge!==null) return charge>0?{usd:charge,apiRate:false,priced:false}:null;
    const entry=run.cost?.estimateKind!=='published_input_rate' && pricing?.runs?.[run.id]?.model===run.model ? pricing.runs[run.id] : null;
    const usd=entry?n(entry.estimateUsd):n(run.cost?.estimatedUsd);
    return usd>0?{usd,apiRate:true,priced:Boolean(entry)}:null;
  }
  function prepare(feed){
    if(feed?.denominator!==60 || !Array.isArray(feed.runs) || !categoryApi?.classify) throw Error('Saved-run source unavailable');
    const seen=new Set(),out={plotted:[],unpriced:[],excluded:0};
    for(const run of feed.runs){
      if(!run || typeof run.id!=='string' || !run.id || seen.has(run.id)) throw Error('Duplicate or missing run ID');
      seen.add(run.id);
      if(run.complete!==true || run.records!==60){out.excluded++;continue;}
      const matches=run.metrics?.all_four;
      if(!['P0','P1','P2'].includes(run.condition) || !Number.isInteger(run.valid) || !Number.isInteger(matches) || matches<0 || matches>run.valid || run.valid>60)
        throw Error('Complete run lacks a valid score');
      const category=categoryApi.classify(run),cost=passCost(run);
      const row={...run,category,matches,colour:category.category==='decision'||category.category==='general'?category.category:'other'};
      if(cost) out.plotted.push({...row,...cost}); else out.unpriced.push(row);
    }
    return out;
  }
  function filtered(rows){
    const condition=$('outcome-condition').value,category=$('outcome-category').value;
    return rows.filter(run=>(condition==='all'||run.condition===condition) && (!category||(run.category.categories||[run.category.category]).includes(category)));
  }
  // Whole decades that cover the costs: $0.001, $0.01, $0.1, $1 ...
  function xDomain(rows){
    if(!rows.length) return [0.001,1];
    const lo=10**Math.floor(Math.log10(Math.min(...rows.map(r=>r.usd)))),hi=10**Math.ceil(Math.log10(Math.max(...rows.map(r=>r.usd))));
    return [lo,hi>lo?hi:lo*10];
  }
  function yDomain(rows){
    if(!rows.length) return [0,60];
    return [Math.max(0,Math.min(50,Math.floor((Math.min(...rows.map(r=>r.matches))-1)/10)*10)),60];
  }
  function ticks(lo,hi,log){
    if(log){const out=[];for(let v=lo;v<=hi*1.0001;v*=10) out.push(Number(v.toPrecision(1)));return out;}
    const step=hi-lo<=20?5:10;return Array.from({length:(hi-lo)/step+1},(_,i)=>lo+i*step);
  }
  const money=v=>`$${v.toLocaleString('en-US',{maximumFractionDigits:6})}`;
  const radius=(k,s)=>Math.min(s/2-.5,5+1.2*Math.sqrt(k-1));
  // ponytail: a fixed grid of s-px cells. Passes in one cell share a marker at their mean position, kept inside the cell,
  // so no two markers overlap and a merge never spreads past one cell. Finer cells mean fewer merges and smaller markers.
  function cluster(rows,x,y,box,s){
    const cells=new Map();
    for(const run of rows){
      const px=x(run.usd),py=y(run.matches),i=Math.floor((px-box.l)/s),j=Math.floor((box.b-py)/s),key=`${i}:${j}`;
      if(!cells.has(key)) cells.set(key,{runs:[],sx:0,sy:0,i,j});
      const cell=cells.get(key);cell.runs.push(run);cell.sx+=px;cell.sy+=py;
    }
    const fit=(v,lo,hi,r)=>lo+r+.5>hi-r-.5?(lo+hi)/2:Math.min(hi-r-.5,Math.max(lo+r+.5,v));
    return [...cells.values()].map(c=>{
      const k=c.runs.length,r=radius(k,s),x0=box.l+c.i*s,y0=box.b-(c.j+1)*s;
      c.runs.sort((a,b)=>b.matches-a.matches||a.usd-b.usd||a.id.localeCompare(b.id));
      const colours=new Set(c.runs.map(run=>run.colour));
      return {runs:c.runs,key:c.runs[0].id,r,colour:colours.size===1?[...colours][0]:'mixed',
        cx:fit(c.sx/k,Math.max(x0,box.l),Math.min(x0+s,box.r),r),cy:fit(c.sy/k,Math.max(y0,box.t),Math.min(y0+s,box.b),r)};
    });
  }
  const passText=run=>{const m=/(?:fresh|pass|repeat)(\d)/.exec(run.repeatPass||'');return m?`pass ${m[1]}`:'';};
  const runLabel=run=>L?.run?L.run(run):String(run.model||run.id);
  const usd=v=>L?.usd?L.usd(v):`$${Number(v).toFixed(4)}`;
  const count=v=>L?.count?L.count(v):String(v);
  const span=(lo,hi,f)=>lo===hi?f(lo):`${f(lo)} to ${f(hi)}`;
  function describe(point){
    const r=point.runs,ms=r.map(x=>x.matches),cs=r.map(x=>x.usd);
    if(r.length===1) return `${runLabel(r[0])}, ${r[0].condition}${passText(r[0])?' '+passText(r[0]):''}`;
    return `${r.length} passes, matched ${span(Math.min(...ms),Math.max(...ms),String)}, ${span(Math.min(...cs),Math.max(...cs),usd)}`;
  }
  function svg(rows,width){
    const w=Math.max(280,Math.round(width)),h=Math.round(w<560?Math.max(380,w*1.15):Math.min(620,Math.max(340,w*.68))),s=w<560?16:18;
    const box={l:44,r:w-14,t:32,b:h-(w<560?92:72)};
    const [xlo,xhi]=xDomain(rows),[ylo,yhi]=yDomain(rows),pad=10;
    const x=v=>box.l+pad+(Math.log10(v)-Math.log10(xlo))/(Math.log10(xhi)-Math.log10(xlo))*(box.r-box.l-2*pad);
    const y=v=>box.b-pad-(v-ylo)/(yhi-ylo)*(box.b-box.t-2*pad);
    points=cluster(rows,x,y,box,s);
    const grid=ticks(ylo,yhi).map(v=>`<line x1="${box.l}" x2="${box.r}" y1="${y(v).toFixed(1)}" y2="${y(v).toFixed(1)}"/><text class="outcome-tick" x="${box.l-8}" y="${(y(v)+4).toFixed(1)}" text-anchor="end">${v}</text>`).join('')+
      ticks(xlo,xhi,true).map(v=>`<line x1="${x(v).toFixed(1)}" x2="${x(v).toFixed(1)}" y1="${box.t}" y2="${box.b}"/><text class="outcome-tick" x="${x(v).toFixed(1)}" y="${box.b+18}" text-anchor="middle">${money(v)}</text>`).join('');
    const legendItems=[['decision','Decision models'],['general','General models'],['other',points.some(p=>p.colour==='mixed')?'Other or mixed':'Other models']].filter(([key])=>points.some(p=>p.colour===key||(key==='other'&&p.colour==='mixed')));
    let lx=box.l,ly=box.b+62;
    const legend=legendItems.map(([key,label])=>{
      const wItem=22+label.length*7.2;
      if(lx+wItem>box.r && lx>box.l){lx=box.l;ly+=22;}
      const item=`<g class="outcome-legend-item" data-category="${key}"><circle cx="${lx+5}" cy="${ly-4}" r="5"/><text x="${lx+15}" y="${ly}">${label}</text></g>`;
      lx+=wItem+14;return item;
    }).join('');
    const dots=points.map(p=>`<g class="outcome-point" data-point="${esc(p.key)}" data-category="${p.colour}" tabindex="0" role="button" aria-pressed="false" aria-label="${esc(`${describe(p)}: matched ${span(Math.min(...p.runs.map(r=>r.matches)),Math.max(...p.runs.map(r=>r.matches)),String)} of 60`)}"><circle cx="${p.cx.toFixed(1)}" cy="${p.cy.toFixed(1)}" r="${p.r.toFixed(1)}"/>${p.runs.length>1?`<text x="${p.cx.toFixed(1)}" y="${(p.cy+3.5).toFixed(1)}" text-anchor="middle" aria-hidden="true">${p.runs.length}</text>`:''}</g>`).join('');
    return `<svg class="outcome-svg" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" preserveAspectRatio="xMidYMid meet" aria-hidden="false"><rect class="outcome-area" x="${box.l}" y="${box.t}" width="${box.r-box.l}" height="${box.b-box.t}"/><g class="outcome-grid" aria-hidden="true">${grid}</g><text class="outcome-axis-title" x="0" y="14" aria-hidden="true">All four matched, of 60</text><text class="outcome-axis-title" x="${(box.l+box.r)/2}" y="${box.b+40}" text-anchor="middle" aria-hidden="true">Cost of one pass, log scale</text><g class="outcome-legend" aria-hidden="true">${legend}</g>${dots}</svg>`;
  }
  function showRun(point){
    const run=point.runs.find(item=>item.id===$('outcome-run').value)||point.runs[0];
    selectedId=run.id;
    $('outcome-point-title').textContent=runLabel(run);
    const ms=point.runs.map(r=>r.matches);
    $('outcome-point-count').textContent=point.runs.length===1?'One pass at this point.':`${point.runs.length} passes at this point, matched ${span(Math.min(...ms),Math.max(...ms),String)} of 60.`;
    const source=run.priced?' data-source="subscription-price-estimates.json"':'';
    $('outcome-run-detail').innerHTML=`<p>Matched ${run.matches} of 60, prompt ${esc(run.condition)}${passText(run)?', '+passText(run):''}</p><p${source}>Cost of the pass: ${esc(usd(run.usd))}${run.apiRate?'†':''}</p>${run.apiRate?'<p class="outcome-footnote">† API-rate equivalent. This route has no bill per pass.</p>':''}<p class="outcome-run-id"><a href="?run=${encodeURIComponent(run.id)}#inspect"><code>${esc(run.id)}</code></a></p>`;
  }
  function selectPoint(point){
    $('outcome-run').innerHTML=point.runs.map(run=>`<option value="${esc(run.id)}">${esc(`${runLabel(run)}, ${run.condition}${passText(run)?' '+passText(run):''}, matched ${run.matches}`)}</option>`).join('');
    $('outcome-run').value=point.runs.some(run=>run.id===selectedId)?selectedId:point.runs[0].id;
    $('outcome-coordinate').value=point.key;
    $('outcome-plot').querySelectorAll('[data-point]').forEach(el=>el.setAttribute('aria-pressed',String(el.dataset?.point===point.key||el.getAttribute?.('data-point')===point.key)));
    showRun(point);
  }
  // The best decision-model pass in view (most matches, then cheapest); else the best pass.
  const best=rows=>[...rows].sort((a,b)=>(b.colour==='decision')-(a.colour==='decision')||b.matches-a.matches||a.usd-b.usd)[0];
  function render(){
    const rows=filtered(plotted),missing=filtered(unpriced),local=missing.filter(run=>/local/i.test(run.surface||'')).length;
    $('outcome-count').textContent=!rows.length&&missing.length?`Nothing to plot: none of these ${count(missing.length)} passes has a recorded cost.`:`${count(rows.length)} ${rows.length===1?'pass':'passes'} plotted.`+
      (missing.length?` ${count(missing.length)} more ${missing.length===1?'has':'have'} no recorded cost${local?`, ${count(local)} of them local runs,`:''} and ${missing.length===1?'is':'are'} not plotted.`:'');
    const plot=$('outcome-plot');
    lastWidth=Math.round(plot.clientWidth||720);
    plot.innerHTML=svg(rows,lastWidth);
    $('outcome-coordinate').innerHTML=points.length
      ?[...points].sort((a,b)=>b.runs[0].matches-a.runs[0].matches||a.runs[0].usd-b.runs[0].usd).map(p=>`<option value="${esc(p.key)}">${esc(describe(p))}</option>`).join('')
      :'<option value="">No passes match these filters</option>';
    plot.querySelectorAll('[data-point]').forEach(el=>{
      const pick=()=>{const key=el.dataset?.point??el.getAttribute('data-point'),point=points.find(p=>p.key===key);if(point){selectedId=null;selectPoint(point);}};
      el.addEventListener('click',pick);
      el.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault?.();pick();}});
    });
    if(!points.length){
      selectedId=null;
      $('outcome-point-title').textContent='No passes match these filters.';
      $('outcome-point-count').textContent='';$('outcome-run').innerHTML='';$('outcome-run-detail').innerHTML='';return;
    }
    if(!rows.some(run=>run.id===selectedId)) selectedId=best(rows).id;
    selectPoint(points.find(p=>p.runs.some(run=>run.id===selectedId)));
  }
  async function init(feed){
    try{
      pricing=await pricingLoad;
      const prepared=prepare(feed);
      plotted=prepared.plotted;unpriced=prepared.unpriced;
      $('outcome-category').innerHTML='<option value="">All categories</option>'+Object.entries(categoryApi.categories).map(([key,name])=>`<option value="${esc(key)}">${esc(name)}</option>`).join('');
      $('outcome-category').addEventListener('change',render);
      $('outcome-condition').addEventListener('change',render);
      $('outcome-coordinate').addEventListener('change',()=>{const point=points.find(p=>p.key===$('outcome-coordinate').value);if(point){selectedId=null;selectPoint(point);}});
      $('outcome-run').addEventListener('change',()=>{const point=points.find(p=>p.runs.some(run=>run.id===$('outcome-run').value));if(point)showRun(point);});
      render();
      if(typeof ResizeObserver==='function') new ResizeObserver(()=>{if(Math.abs(Math.round($('outcome-plot').clientWidth)-lastWidth)>2) render();}).observe($('outcome-plot'));
    }catch{
      $('outcome-count').textContent='The chart did not load.';
      $('outcome-point-title').textContent='Chart unavailable';
      $('outcome-point-count').textContent='';
    }
  }
  globalThis.OutcomeChart=Object.freeze({prepare,passCost,xDomain,yDomain,ticks,cluster,radius,points:()=>points});
  globalThis.addEventListener('benchmark:saved-runs-ready',event=>init(event.detail),{once:true});
  globalThis.addEventListener('benchmark:saved-runs-error',()=>{
    $('outcome-count').textContent='The chart did not load.';
    $('outcome-point-title').textContent='Chart unavailable';
  },{once:true});
})();
