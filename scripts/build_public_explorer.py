#!/usr/bin/env python3
"""Export an explicit public data allowlist from completed benchmark evidence."""
import hashlib,json,math
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
FIELDS=('sentiment','follow_up_needed','serious_concern_reported','testimonial_potential')
GITHUB='https://github.com/adambkovacs/recruitment-feedback-demo/blob/main/'
def rows(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]
def number(value):
    return value if isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value) and value>=0 else None
def tokens(config,root=ROOT):
    paths=config.get('raw_batch_attempt_files') or config.get('attempt_files') or config.get('cost',{}).get('source_paths') or []
    if isinstance(paths,str):paths=[paths]
    totals={k:None for k in ('input','output','cachedInput','cacheWrite','reasoning')}; reported=0; count=0; seen=set()
    for name in paths:
        path=root/name
        if not path.is_file():continue
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in seen:continue
        seen.add(digest)
        for r in rows(path):
            count+=1;u=r.get('usage') or {};stats=r.get('stats') or {}
            # Only direct fields. Never add nested iterations or mirrored raw usage.
            details=u.get('prompt_tokens_details') or {};outdetails=u.get('completion_tokens_details') or u.get('output_tokens_details') or {}
            vals={'input':u.get('input_tokens',u.get('prompt_tokens',stats.get('promptTokensCount'))),'output':u.get('output_tokens',u.get('completion_tokens',stats.get('predictedTokensCount'))),'cachedInput':u.get('cached_input_tokens',u.get('cache_read_input_tokens',details.get('cached_tokens'))),'cacheWrite':u.get('cache_creation_input_tokens'),'reasoning':outdetails.get('reasoning_tokens',outdetails.get('thinking_tokens'))}
            vals={k:number(v) for k,v in vals.items()}
            reported+=int(vals['input'] is not None and vals['output'] is not None)
            for k,v in vals.items():
                if v is not None:totals[k]=(totals[k] or 0)+v
    return {**totals,'reportedRequests':reported,'totalRequests':count,'complete':count>0 and reported==count,'note':'Development requests only; batch usage counted once. Cache and reasoning counts are separately reported provider fields, not additional totals. Missing usage is not zero.'}
def surface(c):
    ident=c['id'];model=c.get('model','').lower()
    if 'openrouter' in ident:return 'OpenRouter'
    if ident.startswith('typesafe-'):return 'TypeSafe API'
    if ident.startswith('codex-'):return 'Codex subscription'
    if 'claude' in model or ident.startswith(('opus','sonnet','haiku','fable')):return 'Claude subscription'
    if 'gemini' in model or ident.startswith('gemini'):return 'Gemini subscription'
    return 'Local / specialist'
def metric(e,all_four):
    return {**{k:e['metrics'][k]['correct'] for k in FIELDS},'all_four':all_four}
def export(root=ROOT):
    summary=json.loads((root/'results/comparison/summary.json').read_text());runs=[]
    for c in summary:
        e=c.get('evaluation')
        if not e:continue
        t=c.get('timing') or {};batch=t.get('workflow')=='batch';kind='batch' if batch else 'record' if t.get('timed_records') else 'unavailable'
        tc=t.get('all_attempt_timing_complete',batch);cost=c.get('cost') or {}
        runs.append({'id':c['id'],'model':c.get('model',c['id']),'effort':c.get('effort') or 'not applicable','surface':surface(c),'condition':'P0','complete':c.get('prediction_records')==60 and 'partial' not in c.get('status','') and not c.get('status','').startswith(('blocked','stopped')),'records':c.get('prediction_records',0),'valid':e['valid_outputs'],'metrics':metric(e,c['exact_match']),'timing':{'totalSeconds':t.get('sum_batch_request_seconds' if batch else 'sum_record_seconds') if tc else None,'medianSeconds':t.get('batch_median_seconds' if batch else 'median_seconds') if tc else None,'p95Seconds':t.get('batch_p95_nearest_rank_seconds' if batch else 'p95_nearest_rank_seconds') if tc else None,'kind':kind,'requests':t.get('batch_requests') if batch else t.get('timed_records'),'complete':bool(tc),'note':t.get('note','Timing unavailable.')},'tokens':tokens(c,root),'cost':{'actualUsd':cost.get('total_actual_usd'),'knownUsd':cost.get('known_actual_usd'),'unknownUpperBoundUsd':cost.get('unknown_reserved_upper_bound_usd'),'availability':cost.get('availability','unavailable'),'note':'Observed development API charges only; excludes smoke. Unknown-charge bounds are not actual spending. Subscription fees and local hardware/electricity are not allocated per run.'},'evidenceUrl':GITHUB+c['predictions_file']})
    allowed={r['id'] for r in runs};cases=[]
    for c in json.loads((root/'results/comparison/cases.json').read_text()):
        if c['configuration'] in allowed:cases.append({k:c[k] for k in ('configuration','id','feedback','reference','prediction','status','different_fields')})
    pairs=[]
    for p in sorted((root/'results/prompt-comparison-v1-2026-09-24/paired-reports').glob('*/evaluation.json')):
        x=json.loads(p.read_text())
        if x.get('eligible_paired_comparison') is not True:continue
        cid=x['parent_baseline_id'];pairs.append({'id':cid,'model':cid,'conditions':{k:{'valid':v['evaluation']['valid_outputs'],**metric(v['evaluation'],v['all_four_correct'])} for k,v in x['conditions'].items()},'evidenceUrl':GITHUB+str(p.relative_to(root))})
    return {'generatedAt':datetime.now(timezone.utc).isoformat(),'denominator':60,'referenceNote':'60 synthetic development records. References drafted and reviewed by the same AI assistant; no independent human adjudication. Agreement is descriptive, not real-world hiring accuracy.','runs':runs,'cases':cases,'promptComparisons':pairs}
def main():
    value=export();dest=ROOT/'public-site/data.json';dest.parent.mkdir(exist_ok=True);dest.write_text(json.dumps(value,ensure_ascii=False,separators=(',',':'))+'\n');print(json.dumps({'runs':len(value['runs']),'cases':len(value['cases']),'promptComparisons':len(value['promptComparisons']),'output':str(dest)}))
if __name__=='__main__':main()
