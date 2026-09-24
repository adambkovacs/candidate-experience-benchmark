#!/usr/bin/env python3
"""Offline, grouped L1 cross-validation on the frozen AnyJev L0 scores.

`freeze` reads IDs and contrast-pair membership only. `evaluate` is deliberately
gated on an externally reviewed SHA-256 of the frozen fold-map file.
"""
import argparse
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import platform
import sys

REPO = Path(__file__).resolve().parents[1]
SOURCE = Path('/Users/adamkovacs/Documents/Codex/2026-09-21/continue-the-recruitment-feedback-benchmark-from/work/anyjev-source')
CONFIG = 'anyjev-qwen06-cached-score-l1-cv5'
SCORE_SHA256 = 'fba96b08c10f8d85b2ab7e510902689dee302369f33e4f91baf152102cb524a1'
PAIR_SHA256 = '76d95b62990700a0338dd71e34c4bf7698d727deef69a344783f853f92b606da'
INPUT_SHA256 = 'bd79e602f45f6aff78796ebdca4f2d0b1585c48665b6b8a9af1fe0b5e52d2b9e'
REFERENCE_SHA256 = '440fa16759473b6d4ff52fe7e7296e5f2dfca0a58f5df26f20aef0daafed1464'
SOURCE_REVISION = '3cd8c6fcd9e90fc04214575ade6779da1e3f3704'
POSTHOC_SHA256 = 'c9db419a4273c91c4bb8259a0de5b10475d34e98dba2614b2ddc27242f8df267'
MODEL_REVISION = 'c1899de289a04d12100db370d81485cdf75e47ca'
POLICY_SHA256 = '81e5f843de69c1c54ca4f17b70df51886405ad3a7606d5644ac24aeb29f839a5'
SPECS_SHA256 = 'e20f67216751480727b1ef12be661dfd023a588b9f8896456644467577267cd6'
SCORE_FILE = REPO/'results/anyjev-qwen06-l0-mps-2026-09-23/development.jsonl'
PAIRS_FILE = REPO/'data/pilot/pairs.json'
IDS_FILE = REPO/'data/pilot/inputs.jsonl'
LABELS_FILE = REPO/'data/pilot/proposed_labels.jsonl'
KEYS = ('sentiment','follow_up_needed','serious_concern_reported','testimonial_potential')
VALUES = {'sentiment': ('positive','negative','mixed','neutral','insufficient_information'),
          **{q: ('yes','no','insufficient_information') for q in KEYS[1:]}}
BIN_EDGES = [i/10 for i in range(11)]  # fixed before any fit
MISSING_CLASS_POLICY = ('Keep all five frozen folds and all fixed option indices; fit the pinned '
                        'TemperatureScaler on the 48 training labels even if a class has zero '
                        'training support. Report support; do not alter folds, drop classes, '
                        'relabel, or add pseudocounts.')


def sha(path):
    with open(path,'rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def rows(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def canonical_ids():
    return [f'DEV-{i:03d}' for i in range(1,61)]


def pairs():
    if sha(PAIRS_FILE) != PAIR_SHA256:
        raise ValueError('Contrast-pair file hash changed')
    source = json.loads(PAIRS_FILE.read_text())
    if len(source) != 6 or len({p['id'] for p in source}) != 6:
        raise ValueError('Expected six distinct contrast pairs')
    seen = set()
    for pair in source:
        ids = pair['record_ids']
        if len(ids) != 2 or len(set(ids)) != 2 or set(ids) & seen:
            raise ValueError('Pairs overlap or have wrong cardinality')
        seen.update(ids)
    if not seen <= set(canonical_ids()):
        raise ValueError('Unknown paired ID')
    return source


def fold_payload():
    if sha(IDS_FILE) != INPUT_SHA256:
        raise ValueError('Input file hash changed')
    ids = [r['id'] for r in rows(IDS_FILE)]  # no reference-label file access
    if ids != canonical_ids() or len(ids) != len(set(ids)):
        raise ValueError('Input IDs are not canonical DEV-001...060')
    ps = pairs()
    paired = {i for p in ps for i in p['record_ids']}
    groups = [tuple(p['record_ids']) for p in ps] + [(i,) for i in ids if i not in paired]
    # Stable ID-only order. Place 2-record groups first, then 1-record groups.
    groups.sort(key=lambda g: (-len(g), hashlib.sha256(('|'.join(g)).encode()).hexdigest()))
    folds = [[] for _ in range(5)]
    for group in groups:
        eligible = [j for j in range(5) if len(folds[j])+len(group) <= 12]
        if not eligible:
            raise ValueError('Fold allocation capacity exhausted')
        chosen = min(eligible, key=lambda j: (len(folds[j]),j))
        folds[chosen].extend(group)
    folds = [sorted(fold) for fold in folds]
    if sorted(i for fold in folds for i in fold) != canonical_ids() or any(len(f)!=12 for f in folds):
        raise ValueError('Invalid 5x12 fold allocation')
    if any(sum(a in fold for a in p['record_ids']) == 1 for fold in folds for p in ps):
        raise ValueError('Contrast pair split')
    return {'configuration':CONFIG,'design':'label-blind group-aware 5-fold cached-score L1',
            'record_ids':ids,'pair_file_sha256':PAIR_SHA256,
            'pair_memberships':[{'id':p['id'],'record_ids':p['record_ids']} for p in ps],
            'folds':[{'fold':j+1,'test_ids':fold,
                      'train_ids':[i for i in ids if i not in fold]} for j,fold in enumerate(folds)],
            'metric_definition':{'nll':'mean -log(p_true)',
                                 'brier':'mean sum_class (p_class - one_hot_class)^2',
                                 'ece':'10 equal-width confidence bins; pooled top-class confidence vs accuracy; left-closed right-open except final bin',
                                 'ece_bin_edges':BIN_EDGES},
            'reference_status':'AI-reviewed provisional; development only',
            'calibration_labels_per_fold':48,
            'limitation':'48 labels per fit is below upstream recommended 100-500; exploratory only, not deployment calibration'}


def write_exclusive(path, payload):
    path.parent.mkdir(parents=True,exist_ok=True)
    with open(path,'x') as f:
        json.dump(payload,f,indent=2,ensure_ascii=False)
        f.write('\n')


def verify_fold_file(path, approved_sha):
    if sha(path) != approved_sha:
        raise ValueError('Frozen fold map hash does not match reviewed hash')
    saved = json.loads(path.read_text())
    if saved != fold_payload():
        raise ValueError('Frozen fold map differs from deterministic label-blind allocation')
    return saved


def verify_scores():
    if sha(SCORE_FILE) != SCORE_SHA256:
        raise ValueError('L0 score file hash changed')
    if sha(IDS_FILE) != INPUT_SHA256:
        raise ValueError('Input file hash changed')
    sys.path.insert(0,str(REPO/'scripts'))
    from anyjev_benchmark import question_specs
    from development_benchmark import digest
    policy = (REPO/'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    if digest(policy) != POLICY_SHA256:
        raise ValueError('Policy hash changed')
    specs = question_specs(policy)
    if digest(json.dumps(specs,sort_keys=True)) != SPECS_SHA256:
        raise ValueError('Question text/options hash changed')
    if [s['id'] for s in specs] != list(KEYS):
        raise ValueError('Question order changed')
    for spec in specs:
        if [s.split(': ',1)[0] for s in spec['options']] != list(VALUES[spec['id']]):
            raise ValueError('Question option indices changed')
    saved = rows(SCORE_FILE)
    if [r['id'] for r in saved] != canonical_ids():
        raise ValueError('Noncanonical or duplicate score IDs')
    input_hashes = {r['id']:digest(r['feedback']) for r in rows(IDS_FILE)}
    prior_by_question = {}
    for r in saved:
        if (r.get('status')!='ok' or r.get('level')!='L0' or
            r.get('requested_model')!='Qwen/Qwen3-0.6B' or
            r.get('artifact_revision')!=MODEL_REVISION or r.get('source_revision')!=SOURCE_REVISION or
            r.get('policy_sha256')!=POLICY_SHA256 or r.get('question_specs_sha256')!=SPECS_SHA256 or
            r.get('input_sha256')!=input_hashes[r['id']] or
            r.get('reference_labels_used') is not False or r.get('calibration_artifacts_loaded') is not False or
            r.get('prior')!='content_free' or r.get('prior_applied') is not True or
            r.get('prior_strength')!=1.0 or r.get('prediction') is None):
            raise ValueError('L0 provenance mismatch: '+r['id'])
        for q in KEYS:
            d = r['diagnostics'][q]
            probs = d['l0_probs']
            if (len(probs)!=len(VALUES[q]) or any(not isinstance(p,(int,float)) or not math.isfinite(p) or p<0 or p>1 for p in probs) or abs(sum(probs)-1)>1e-6):
                raise ValueError('Invalid L0 probabilities: '+r['id']+' '+q)
            if VALUES[q][max(range(len(probs)),key=probs.__getitem__)] != r['prediction'][q]:
                raise ValueError('L0 argmax mismatch: '+r['id']+' '+q)
            if d.get('prior_method')!='content_free' or d.get('prior_strength')!=1.0:
                raise ValueError('L0 prior mismatch')
            prior = d.get('prior')
            if q in prior_by_question and prior != prior_by_question[q]:
                raise ValueError('Inconsistent prior per question')
            prior_by_question[q] = prior
    return saved,prior_by_question


def load_labels():
    if sha(LABELS_FILE) != REFERENCE_SHA256:
        raise ValueError('Reference file hash changed')
    refs = rows(LABELS_FILE)
    if [r['id'] for r in refs] != canonical_ids():
        raise ValueError('Reference IDs are not canonical')
    for r in refs:
        if r.get('split')!='development' or set(r['proposed_labels'])!=set(KEYS):
            raise ValueError('Invalid development reference')
        if any(r['proposed_labels'][q] not in VALUES[q] for q in KEYS):
            raise ValueError('Unknown reference option')
    return {r['id']:r['proposed_labels'] for r in refs}


def training_label_indices(train_ids,test_ids,labels,question):
    if set(train_ids) & set(test_ids):
        raise ValueError('Held-out ID appears in calibration set')
    return [VALUES[question].index(labels[i][question]) for i in train_ids]


def metrics(probs, labels):
    n = len(labels)
    pred = [max(range(len(p)),key=p.__getitem__) for p in probs]
    confidence = [p[j] for p,j in zip(probs,pred)]
    accuracy = [int(a==b) for a,b in zip(pred,labels)]
    bins = []
    for j in range(10):
        picked = [i for i,c in enumerate(confidence) if BIN_EDGES[j] <= c < BIN_EDGES[j+1] or (j==9 and c==1.0)]
        bins.append({'lo':BIN_EDGES[j],'hi':BIN_EDGES[j+1],'count':len(picked),
                     'mean_confidence':sum(confidence[i] for i in picked)/len(picked) if picked else None,
                     'accuracy':sum(accuracy[i] for i in picked)/len(picked) if picked else None})
    return {'nll':sum(-math.log(max(p[y],1e-12)) for p,y in zip(probs,labels))/n,
            'brier':sum(sum((v-int(k==y))**2 for k,v in enumerate(p)) for p,y in zip(probs,labels))/n,
            'ece':sum(b['count']/n*abs(b['mean_confidence']-b['accuracy']) for b in bins if b['count']),
            'accuracy':sum(accuracy)/n,'correct':sum(accuracy),'bins':bins}


def evaluate(fold_map, saved, labels, source=SOURCE):
    import subprocess
    import numpy as np
    revision = subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip()
    if revision != SOURCE_REVISION:
        raise ValueError('AnyJev source revision mismatch')
    if subprocess.check_output(['git','-C',str(source),'status','--porcelain'],text=True).strip():
        raise ValueError('AnyJev source is dirty')
    if sha(source/'anyjev/calibrate/posthoc.py') != POSTHOC_SHA256:
        raise ValueError('Pinned TemperatureScaler source hash changed')
    sys.path.insert(0,str(source))
    from anyjev.calibrate.posthoc import TemperatureScaler
    by_id = {r['id']:r for r in saved}
    out = {q:{} for q in KEYS}
    temperatures = []
    for fold in fold_map['folds']:
        train,test = fold['train_ids'],fold['test_ids']
        if set(train)&set(test) or len(train)!=48 or len(test)!=12:
            raise ValueError('Invalid train/test separation')
        for q in KEYS:
            train_probs = np.asarray([by_id[i]['diagnostics'][q]['l0_probs'] for i in train])
            train_labels = training_label_indices(train,test,labels,q)
            support = {v:train_labels.count(j) for j,v in enumerate(VALUES[q])}
            scaler = TemperatureScaler.fit(train_probs,train_labels)
            if not math.isfinite(scaler.temperature) or scaler.temperature<=0:
                raise ValueError('Nonpositive fitted temperature')
            test_probs = np.asarray([by_id[i]['diagnostics'][q]['l0_probs'] for i in test])
            scaled = scaler.apply(test_probs)
            temperatures.append({'fold':fold['fold'],'question':q,'temperature':scaler.temperature,'n_calib':48,
                                 'train_class_support':support,'train_ids':train,'test_ids':test})
            for i,base,cal in zip(test,test_probs,scaled):
                if int(np.argmax(base)) != int(np.argmax(cal)) or not np.array_equal(np.argsort(base),np.argsort(cal)):
                    raise ValueError('Temperature scaling changed option rank: '+i+' '+q)
                out[q][i] = {'l0':base.tolist(),'l1':cal.tolist()}
    summary = {}
    for q in KEYS:
        ids = canonical_ids()
        if set(out[q])!=set(ids):
            raise ValueError('Out-of-fold score coverage mismatch')
        truth = [VALUES[q].index(labels[i][q]) for i in ids]
        summary[q] = {'class_support':{v:truth.count(j) for j,v in enumerate(VALUES[q])},
                      'l0':metrics([out[q][i]['l0'] for i in ids],truth),
                      'l1':metrics([out[q][i]['l1'] for i in ids],truth)}
        if summary[q]['l0']['correct']!=summary[q]['l1']['correct']:
            raise ValueError('Held-out accuracy changed')
    return {'configuration':CONFIG,'score_file_sha256':SCORE_SHA256,'input_file_sha256':INPUT_SHA256,
            'reference_file_sha256':REFERENCE_SHA256,'source_revision':SOURCE_REVISION,
            'upstream_posthoc_sha256':POSTHOC_SHA256,'runner_sha256':sha(Path(__file__)),
            'runtime':{'python':platform.python_version(),'numpy':version('numpy'),'scipy':version('scipy')},
            'fold_count':5,'held_out_per_fold':12,'training_per_fold':48,
            'missing_class_policy':MISSING_CLASS_POLICY,
            'reference_status':'AI-reviewed provisional; development only',
            'limitation':'Exploratory cross-validation; 48 labels per fit below upstream recommended 100-500; not a deployable calibration artifact',
            'temperatures':temperatures,'metrics':summary,
            'out_of_fold_predictions':[{ 'id':i,'questions':{q:out[q][i] for q in KEYS}} for i in canonical_ids()]}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    sub=p.add_subparsers(dest='command',required=True)
    f=sub.add_parser('freeze');f.add_argument('--output',type=Path,required=True)
    e=sub.add_parser('evaluate');e.add_argument('--fold-map',type=Path,required=True)
    e.add_argument('--approved-fold-sha256',required=True);e.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.command=='freeze':
        write_exclusive(args.output,fold_payload())
        print(sha(args.output))
        return
    if args.output.exists():
        raise FileExistsError(args.output)
    fold_map=verify_fold_file(args.fold_map,args.approved_fold_sha256)
    saved,_=verify_scores()  # all provenance checks precede label access
    labels=load_labels()
    result=evaluate(fold_map,saved,labels)
    result['fold_map_sha256']=sha(args.fold_map)
    write_exclusive(args.output,result)


if __name__=='__main__':
    main()
