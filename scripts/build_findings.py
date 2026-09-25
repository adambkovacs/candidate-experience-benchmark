#!/usr/bin/env python3
"""Rebuild descriptive public findings from the frozen development export only."""
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'public-site/data.json'
OUTPUT = ROOT / 'public-site/findings.json'
FIELDS = ('sentiment', 'follow_up_needed', 'serious_concern_reported', 'testimonial_potential')
CONDITIONS = ('P0', 'P1', 'P2')
GITHUB = 'https://github.com/adambkovacs/candidate-experience-benchmark/blob/main/'


def case_index(cases):
    index = {}
    for case in cases:
        key = (case['configuration'], case['id'])
        if key in index:
            raise ValueError(f'duplicate configuration/case: {key}')
        index[key] = case
    return index


def state(case):
    if case is None or case.get('status') != 'ok' or case.get('prediction') is None:
        return 'invalid'
    return 'correct' if all(case['prediction'].get(f) == case['reference'].get(f) for f in FIELDS) else 'wrong'


def score_run(run, cases, expected_ids):
    selected = [cases.get((run['id'], ident)) for ident in expected_ids]
    if any(case is None for case in selected):
        raise ValueError(f'missing case for {run["id"]}')
    valid = sum(case['status'] == 'ok' and case['prediction'] is not None for case in selected)
    correct = sum(state(case) == 'correct' for case in selected)
    if valid != run['valid'] or correct != run['metrics']['all_four']:
        raise ValueError(f'saved summary disagrees with cases: {run["id"]}')
    return {'valid': valid, 'correct': correct, 'invalid': len(selected)-valid}


def classify_comparison(comp, base):
    if comp.get('eligible') and base['surface'] == 'Local / specialist':
        return 'local_historical_baseline'
    if comp.get('eligible'):
        return 'strict'
    return 'hosted_observational'


def comparison_run_ids(comp, runs):
    ident = comp['id']
    result = {'P0': ident}
    for condition in ('P1', 'P2'):
        direct = f'{ident}--{condition.lower()}'
        if direct in runs:
            result[condition] = direct
        else:
            derived = ident.replace('-p0-', f'-{condition.lower()}-').replace('-v2', '-v3')
            if derived not in runs:
                raise ValueError(f'cannot resolve {condition} for {ident}')
            result[condition] = derived
    return result


def prompt_deltas(comparisons, runs, cases, ids):
    cohorts = {key: [] for key in ('strict', 'hosted_observational', 'local_historical_baseline')}
    seen = set()
    for comp in comparisons:
        ident = comp['id']
        if ident in seen:
            raise ValueError(f'duplicate prompt comparison {ident}')
        seen.add(ident)
        base = runs[ident]
        cohort = classify_comparison(comp, base)
        run_ids = comparison_run_ids(comp, runs)
        scores = {condition: score_run(runs[rid], cases, ids) for condition, rid in run_ids.items()}
        for condition, summary in comp['conditions'].items():
            if summary['all_four'] != scores[condition]['correct']:
                raise ValueError(f'comparison summary disagrees: {ident} {condition}')
            if 'valid' in summary and summary['valid'] != scores[condition]['valid']:
                raise ValueError(f'comparison validity disagrees: {ident} {condition}')
        cohorts[cohort].append({'id': ident, 'model': comp['model'], 'surface': base['surface'],
                                'runIds': run_ids, 'scores': scores,
                                'evidenceUrl': comp['evidenceUrl'],
                                'limit': comp.get('comparisonLimit') or comp.get('sourceStatus')})
    output = []
    for cohort_id, entries in cohorts.items():
        pairs = {}
        for frm, to in (('P0','P1'),('P0','P2'),('P1','P2')):
            rows = []
            for item in entries:
                a = item['scores'][frm]['correct']; b = item['scores'][to]['correct']
                rows.append({'id': item['id'], 'model': item['model'], 'surface': item['surface'],
                             'fromRunId': item['runIds'][frm], 'toRunId': item['runIds'][to],
                             'fromCorrect': a, 'toCorrect': b, 'fromValid': item['scores'][frm]['valid'],
                             'toValid': item['scores'][to]['valid'], 'delta': b-a,
                             'evidenceUrl': item['evidenceUrl']})
            pairs[f'{frm}_to_{to}'] = {'improved': sum(r['delta']>0 for r in rows),
                                       'tied': sum(r['delta']==0 for r in rows),
                                       'worsened': sum(r['delta']<0 for r in rows),
                                       'rows': sorted(rows,key=lambda r:(-r['delta'],r['id']))}
        output.append({'id': cohort_id, 'configurations': len(entries), 'runIds': [e['runIds'] for e in entries],
                       'denominatorPerConfiguration': len(ids), 'comparisons': pairs})
    return {'groups': output, 'cohorts': output,
            'note': 'Each row is one saved configuration with the same 60 records per condition. Improved/tied/worsened counts are configuration counts, not independent trials. Strict is the export eligibility flag on hosted/subscription comparisons; one pass and nonrandomized timing limit causal interpretation. Five local historical-baseline pairs and nine Gemini hosted-observational comparisons are separate; Jev native is a fourth observational strand in charts.jev.'}


def jev_findings(runs, cases, ids):
    jev_id = 'typesafe-jev113-v2'
    jev = runs[jev_id]
    field_errors = []
    for field in FIELDS:
        confusions = Counter()
        valid_wrong = 0; invalid = 0
        for ident in ids:
            row = cases[(jev_id,ident)]
            pred = row['prediction']
            if row['status'] != 'ok' or pred is None:
                invalid += 1
            elif pred[field] != row['reference'][field]:
                valid_wrong += 1
                confusions[(row['reference'][field],pred[field])] += 1
        field_errors.append({'field':field,'correct':len(ids)-invalid-valid_wrong,'wrong':valid_wrong,
                             'invalid':invalid,'denominator':len(ids),
                             'confusions':[{'reference':a,'prediction':b,'count':n} for (a,b),n in sorted(confusions.items())]})
    comparators=[]
    for run in runs.values():
        if run['id']==jev_id or run['protocolId']!='baseline-v1' or run['condition']!='P0' or not run['complete'] or run['records']!=len(ids):
            continue
        rid=run['id']; score_run(run,cases,ids)
        overlap={key:[] for key in ('bothCorrect','jevOnlyWrong','comparatorOnlyWrong','bothWrong')}
        for ident in ids:
            j=state(cases[(jev_id,ident)])=='correct'
            c=state(cases[(rid,ident)])=='correct'
            key='bothCorrect' if j and c else 'jevOnlyWrong' if not j and c else 'comparatorOnlyWrong' if j and not c else 'bothWrong'
            overlap[key].append(ident)
        comparators.append({'id':rid,'model':run['model'],'surface':run['surface'],
                            'correct':run['metrics']['all_four'],'valid':run['valid'],
                            'overlap':{k:len(v) for k,v in overlap.items()}, 'caseIds':overlap,
                            'evidenceUrl':run['evidenceUrl']})
    comparators.sort(key=lambda r:(-r['correct'],r['id']))
    misses=[ident for ident in ids if state(cases[(jev_id,ident)])!='correct']
    detailed=[{'id':ident,'feedback':cases[(jev_id,ident)]['feedback'],
               'reference':cases[(jev_id,ident)]['reference'],
               'prediction':cases[(jev_id,ident)]['prediction'],
               'differentFields':cases[(jev_id,ident)]['different_fields'],
               'sourceUrl':GITHUB+f'data/pilot/proposed_labels.jsonl#L{int(ident.split("-")[1])}'} for ident in misses]
    return {'runId':jev_id,'model':jev['model'],'correct':jev['metrics']['all_four'],
            'valid':jev['valid'],'denominator':len(ids),'fieldErrors':field_errors,
            'disagreementCaseIds':misses,'cases':detailed,
            'comparators':comparators,'overlap':comparators,'evidenceUrl':jev['evidenceUrl'],
            'note':'Jev P0 is a historical native run. Comparator overlap is on the same records, but separate execution surfaces and controls make it descriptive. Invalid output remains wrong.'}


def cost_agreement(runs, cases, ids):
    rows=[]
    for run in runs.values():
        if run['protocolId'] not in ('baseline-v1','gemini-openrouter-hosted-batch10-v2','gemini-openrouter-hosted-batch10-v3') or run['condition']!='P0' or not run['complete'] or run['records']!=len(ids):
            continue
        cost=run['cost']; amount=cost.get('actualUsd')
        if amount is None:
            continue
        if cost.get('availability') not in ('reported','complete'):
            continue
        score_run(run,cases,ids)
        rows.append({'id':run['id'],'model':run['model'],'surface':run['surface'],
                     'effort':run['effort'],'condition':'P0','correct':run['metrics']['all_four'],
                     'valid':run['valid'],'invalid':len(ids)-run['valid'],'denominator':len(ids),
                     'actualUsd':float(amount),'costAvailability':'observed',
                     'sourceCostAvailability':cost['availability'],
                     'cohort':'hosted_observational_gemini' if run['protocolId'].startswith('gemini-openrouter-hosted') else 'baseline_p0',
                     'evidenceUrl':run['evidenceUrl']})
    rows.sort(key=lambda r:(r['actualUsd'],r['id']))
    return {'rows':rows,'note':'Observed API cost for complete saved baseline P0 and nine Gemini hosted observational P0 development attempts only; includes retries when recorded, excludes smoke. No Jev estimate, subscription fee, local hardware, or unknown-charge bound is plotted. Batch request costs are for 60 records and cannot establish per-record latency or production unit economics.'}


def hard_cases(runs, cases, ids, labels, prompt):
    strict = next(c for c in prompt['groups'] if c['id']=='strict')
    run_ids = [d['P0'] for d in strict['runIds']]
    categories = {
        'all_records': list(ids),
        'tagged_challenges': [ident for ident in ids if labels[ident].get('challenge_tags')],
        'untagged': [ident for ident in ids if not labels[ident].get('challenge_tags')],
        'reference_serious_yes': [ident for ident in ids if labels[ident]['proposed_labels']['serious_concern_reported']=='yes'],
        'reference_follow_up_yes': [ident for ident in ids if labels[ident]['proposed_labels']['follow_up_needed']=='yes'],
        'reference_has_insufficient_information': [ident for ident in ids if 'insufficient_information' in labels[ident]['proposed_labels'].values()],
    }
    def summarize(subset):
        outcomes=[state(cases[(rid,ident)]) for rid in run_ids for ident in subset]
        return {'recordCount':len(subset),'configurationCount':len(run_ids), 'denominator':len(outcomes),
                'correct':outcomes.count('correct'),'wrongValid':outcomes.count('wrong'),
                'invalid':outcomes.count('invalid')}
    category_rows=[{'id':key,'caseIds':case_ids,**summarize(case_ids)} for key,case_ids in categories.items()]
    case_rows=[]
    for number,ident in enumerate(ids,1):
        row=summarize([ident]); row.update({'id':ident,'challengeTags':labels[ident].get('challenge_tags',[]),
            'reference':labels[ident]['proposed_labels'], 'feedback':cases[(run_ids[0],ident)]['feedback'], 'sourceUrl':GITHUB+f'data/pilot/proposed_labels.jsonl#L{number}'})
        case_rows.append(row)
    case_rows.sort(key=lambda r:(-(r['wrongValid']+r['invalid']),r['id']))
    return {'categories':category_rows,'cases':case_rows,'rows':case_rows,'runIds':run_ids,
            'note':'These are P0 results for the 38 strict hosted/subscription prompt configurations. A configuration-case outcome is counted once; rows are correlated and not independent trials. Category slices overlap. Ranked cases are disagreements with provisional AI-authored references, not adjudicated task difficulty.'}


def effort_comparisons(runs, cases, ids):
    groups=defaultdict(list)
    for run in runs.values():
        if run['protocolId']!='baseline-v1' or run['condition']!='P0' or not run['complete'] or run['records']!=len(ids):
            continue
        if 'batch10' not in run['id'] or run['surface'] not in ('Codex subscription','Claude subscription') or run['effort'] not in ('low','medium','high','xhigh'):
            continue
        score_run(run,cases,ids)
        batch='batch10' if 'batch10' in run['id'] else 'individual'
        groups[(run['model'],run['surface'],batch)].append({'id':run['id'],'effort':run['effort'],
            'correct':run['metrics']['all_four'],'valid':run['valid'],'evidenceUrl':run['evidenceUrl']})
    return {'groups':[{'model':model,'surface':surface,'requestControl':batch,'condition':'P0',
                       'denominator':len(ids),'rows':sorted(rows,key=lambda r:['low','medium','high','xhigh'].index(r['effort']))}
                      for (model,surface,batch),rows in sorted(groups.items()) if len({r['effort'] for r in rows})>1],
            'note':'Only matched model, execution surface, P0, and batch control are grouped. Saved one-pass results are descriptive and do not establish an effort effect.'}


def build(source=SOURCE, labels_path=ROOT/'data/pilot/proposed_labels.jsonl'):
    raw=source.read_bytes(); data=json.loads(raw)
    labels_rows=[json.loads(line) for line in labels_path.read_text().splitlines() if line.strip()]
    labels={row['id']:row for row in labels_rows}
    ids=sorted(labels)
    if len(ids)!=60 or len(labels)!=len(labels_rows):
        raise ValueError('expected 60 unique development labels')
    if len(data['runs'])!=290 or len(data['cases'])!=17400:
        raise ValueError('frozen export size changed; reassess cohorts')
    runs={r['id']:r for r in data['runs']}
    if len(runs)!=len(data['runs']): raise ValueError('duplicate run ids')
    cases=case_index(data['cases'])
    for run in runs.values(): score_run(run,cases,ids)
    for ident in ids:
        for run in runs.values():
            if cases[(run['id'],ident)]['reference'] != labels[ident]['proposed_labels']:
                raise ValueError(f'reference mismatch: {run["id"]} {ident}')
    prompt=prompt_deltas(data['promptComparisons'],runs,cases,ids)
    return {'meta':{'sourcePath':'public-site/data.json','sourceSha256':hashlib.sha256(raw).hexdigest(),
                    'labelsPath':'data/pilot/proposed_labels.jsonl','labelsSha256':hashlib.sha256(labels_path.read_bytes()).hexdigest(),
                    'runCount':len(runs),'caseCount':len(cases),'recordCount':len(ids),
                    'referenceCaveat':data['referenceNote'],
                    'exclusions':'Prompt cohorts use each saved promptComparisons entry once. Other historical, duplicate, partial, reconciled, and independent prompt alternatives remain browsable in data.json but are not pooled into prompt deltas. Cost uses complete baseline and Gemini hosted observational P0 runs with actual observed API cost.'},
            'referenceDistributions':{field:dict(sorted(Counter(labels[i]['proposed_labels'][field] for i in ids).items())) for field in FIELDS},
            'charts':{'promptDeltas':prompt,'jev':jev_findings(runs,cases,ids),
                      'costAgreement':cost_agreement(runs,cases,ids),
                      'hardCases':hard_cases(runs,cases,ids,labels,prompt),
                      'effort':effort_comparisons(runs,cases,ids)}}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true',help='fail when findings.json differs from frozen sources')
    args=parser.parse_args()
    output=build()
    expected=json.dumps(output,ensure_ascii=False,indent=2)+'\n'
    if args.check:
        if not OUTPUT.is_file() or OUTPUT.read_text()!=expected:
            raise SystemExit('findings.json is missing or stale; run python3 scripts/build_findings.py')
        print('findings.json matches frozen sources')
    else:
        OUTPUT.write_text(expected)
        print(f'Wrote {OUTPUT}: {len(output["charts"]["jev"]["comparators"])} Jev comparators')

if __name__=='__main__': main()
