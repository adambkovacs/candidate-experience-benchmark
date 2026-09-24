#!/usr/bin/env python3
"""Offline-only scoring of closed local prompt conditions. Never imports model clients."""
import argparse,hashlib,json,math,pathlib,statistics,sys
from datetime import datetime,timezone
ROOT=pathlib.Path('/Users/adamkovacs/Documents/codebuild/recruitment-feedback-demo')
BASE=ROOT/'results/local-prompt-exact-v1'
sys.path.insert(0,str(ROOT/'scripts'))
from development_benchmark import read_rows,score,validate,valid
HASH=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()

def percentile_nearest(values,percent):
    ordered=sorted(values)
    return ordered[max(0,math.ceil(percent*len(ordered))-1)]

def evaluate(config,variant,write=False):
    p=BASE/config/variant
    output=p/'development.jsonl';journal=p/'development.attempts.jsonl';terminal=p/'development.terminal.json'
    if not terminal.exists():return None
    term=json.loads(terminal.read_text())
    if term['status']!='completed':return None
    rows=read_rows(output);events=[json.loads(line) for line in journal.read_text().splitlines()]
    assert len(rows)==len({r['id'] for r in rows})==60 and [r['id'] for r in rows]==[f'DEV-{i:03d}' for i in range(1,61)]
    assert len(events)==120 and term['saved_rows']==term['claimed_attempts']==term['finished_attempts']==60
    assert term['output_sha256']==HASH(output) and term['journal_sha256']==HASH(journal)
    assert not term['ambiguous_timeout'] and term['stopped_reason'] is None
    manifest=BASE/'manifest.json';preflight=BASE/'preflight-summary.json';controller=ROOT/'scripts/local_prompt_execution_v1.cjs'
    assert term['manifest_sha256']==HASH(manifest) and term['preflight_sha256']==HASH(preflight) and term['controller_sha256']==HASH(controller)
    assert all(r['configuration']==config and r['variant']==variant and r['phase']=='development' for r in rows)
    assert all(r['runtime_attestation']==term['runtime_attestation'] and r['reference_labels_read'] is False for r in rows)
    for i,(row,line) in enumerate(zip(rows,output.read_text().splitlines())):
        start,finish=events[2*i:2*i+2]
        assert start['event']=='started' and finish['event']=='finished'
        assert start['id']==finish['id']==row['id'] and start['attempt_id']==finish['attempt_id']==row['attempt_id']
        assert start['request_sha256']==row['request_sha256'] and finish['output_sha256']==hashlib.sha256(line.encode()).hexdigest()
        assert finish['status']==row['decision']['status'] in ('ok','invalid_output')
        assert row['decision']['status']!='ok' or valid(row['decision']['prediction'])
    refs_file=ROOT/'data/pilot/proposed_labels.jsonl';pairs_file=ROOT/'data/pilot/pairs.json'
    refs=read_rows(refs_file);pairs=json.loads(pairs_file.read_text())
    predictions=[{'id':row['id'],'status':row['decision']['status'],**({'prediction':row['decision']['prediction']} if row['decision']['status']=='ok' else {})} for row in rows]
    scored=score(refs,predictions,pairs)
    truth={row['id']:row['proposed_labels'] for row in refs}
    all_four=sum(row['decision']['status']=='ok' and row['decision']['prediction']==truth[row['id']] for row in rows)
    elapsed=[row['elapsed_seconds'] for row in rows]
    surface=term['runtime_attestation']['surface']
    prompt_key='prompt_tokens' if surface=='local_http' else 'promptTokensCount'
    completion_key='completion_tokens' if surface=='local_http' else 'predictedTokensCount'
    missing_usage=[row['id'] for row in rows if not isinstance(row.get('stats'),dict) or not isinstance(row['stats'].get(prompt_key),int) or not isinstance(row['stats'].get(completion_key),int)]
    prompt_tokens=sum(row['stats'][prompt_key] for row in rows if row['id'] not in missing_usage)
    completion_tokens=sum(row['stats'][completion_key] for row in rows if row['id'] not in missing_usage)
    smoke=p/'smoke.jsonl';smoke_terminal=p/'smoke.terminal.json';inspection=p/'smoke-inspection.json'
    assert smoke.exists() and smoke_terminal.exists() and inspection.exists()
    report={'version':'local-prompt-offline-evaluation-v1','configuration':config,'variant':variant,
        'phase':'development','reference_status':'AI-reviewed provisional; development only',
        'source_sha256':{'development_output':HASH(output),'development_journal':HASH(journal),'development_terminal':HASH(terminal),
          'smoke_output':HASH(smoke),'smoke_terminal':HASH(smoke_terminal),'smoke_inspection':HASH(inspection),
          'manifest':HASH(manifest),'preflight':HASH(preflight),'controller':HASH(controller),
          'provisional_references':HASH(refs_file),'pairs':HASH(pairs_file),
          'scorer':HASH(ROOT/'scripts/development_benchmark.py'),
          'conversion_helper':HASH(BASE/'offline-score-helper.py')},
        'coverage':{'denominator':60,'saved_rows':60,'valid_outputs':scored['valid_outputs'],
          'invalid_outputs':60-scored['valid_outputs'],'all_four_correct':all_four},
        'resource':{'surface':surface,'cost_usd':None,'cost_note':'Local execution; API billing not applicable. Device electricity and amortization unmeasured.',
          'elapsed_prediction_seconds_sum':sum(elapsed),'elapsed_prediction_seconds_median':statistics.median(elapsed),
          'elapsed_prediction_seconds_p95_nearest_rank':percentile_nearest(elapsed,.95),
          'elapsed_prediction_seconds_max':max(elapsed),'prompt_tokens_observed_sum':prompt_tokens,
          'completion_tokens_observed_sum':completion_tokens,'usage_missing_record_ids':missing_usage,
          'cache_tokens_observed':None,'cache_note':'Native local responses did not provide a comparable cache-token count.',
          'runtime_attestation':term['runtime_attestation'],'timeout_ms':term['timeout_ms']},
        'score':scored,'computed_utc':datetime.now(timezone.utc).isoformat()}
    if write:
        target=p/'offline-evaluation.json'
        with target.open('x') as out:json.dump(report,out,indent=2);out.write('\n')
        print('saved',target.relative_to(ROOT),HASH(target))
    print(config,variant,'valid',scored['valid_outputs'],'all_four',all_four,'elapsed_sum_s',round(sum(elapsed),2),'prompt_tokens',prompt_tokens,'completion_tokens',completion_tokens)
    return report

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--write',action='store_true');args=parser.parse_args()
    assert validate()['status']=='valid'
    plan=json.loads((BASE/'smoke-plan.json').read_text())
    done=0
    for entry in plan['conditions']:
        if evaluate(entry['config'],entry['variant'],args.write) is not None:done+=1
    print('completed_condition_count',done)
if __name__=='__main__':main()
