#!/usr/bin/env python3
"""Offline, closed-evidence report for the three fresh direct-native AnyJev L1 passes."""
import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path

from anyjev_benchmark import question_specs
from development_benchmark import VALUES, digest

ROOT = Path(__file__).resolve().parents[1]
BASE = Path('results/repeatability-v1/anyjev-l1-direct-native-cv5-v1')
MANIFEST_SHA = '19d1b8cc078a11fde4209c0cb286be8f4c171c7b10ee3d28f4385c59ca98c7ca'
L0_SHA = '29095d4a527cefaac3e4169a1dfc94879a7571f909d7f8fb4b2213e32f1a3049'
FOLD_SHA = '7be25f9bcd9dfbde383bccefe4ad9e4c5a8d6a664b4964789c532dac299dff0c'
REFERENCE_SHA = '440fa16759473b6d4ff52fe7e7296e5f2dfca0a58f5df26f20aef0daafed1464'
PASSES = ('fresh1/P0', 'fresh2/P0', 'fresh3/P0')
FIELDS = ('sentiment', 'follow_up_needed', 'serious_concern_reported', 'testimonial_potential')
IDS = tuple(f'DEV-{n:03d}' for n in range(1, 61))
SMOKE_IDS = ('DEV-001', 'DEV-002', 'DEV-003')
INVALID = '__invalid_or_missing__'


def path(root, relative):
    root = Path(root).resolve()
    target = (root / relative).resolve()
    target.relative_to(root)
    return target


def sha(filename):
    with Path(filename).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def jsonl(filename):
    data = Path(filename).read_bytes()
    if not data or not data.endswith(b'\n') or any(not line.strip() for line in data.splitlines()):
        raise ValueError(f'Incomplete JSONL: {filename}')
    return [json.loads(line) for line in data.splitlines()]


def bind_context(root):
    bindings = []
    def bind(relative, expected=None):
        relative = Path(relative)
        actual = sha(path(root, relative))
        if expected is not None and actual != expected:
            raise ValueError(f'Hash differs: {relative}')
        entry = {'path': str(relative), 'sha256': actual}
        if entry not in bindings:
            bindings.append(entry)
        return entry
    return bind, bindings


def source(root):
    bind, bindings = bind_context(root)
    bind(BASE / 'manifest.json', MANIFEST_SHA)
    plan = json.loads(path(root, BASE / 'manifest.json').read_text())
    if (plan.get('schema') != 'anyjev-l1-direct-native-cv5-candidate-v1'
            or plan.get('status') != 'frozen_plan_requires_stage_receipts'
            or plan.get('fresh_passes') != list(PASSES)
            or plan.get('smoke_ids') != list(SMOKE_IDS)
            or plan.get('smoke_folds') != [1, 4, 5]
            or plan.get('full_new_heldout_count') != 57
            or plan.get('l0_prompt_plan_sha256') != L0_SHA
            or plan.get('fold_sha256') != FOLD_SHA
            or plan.get('reference_sha256') != REFERENCE_SHA
            or plan.get('runtime', {}).get('device') != 'mps:0'
            or plan['runtime'].get('dtype') != 'torch.bfloat16'
            or plan['runtime'].get('batch_size') != 4
            or plan['calibration'].get('fit_calls_per_pass') != 20
            or plan['calibration'].get('heldout_question_calls_per_pass') != 240
            or plan['calibration'].get('fresh_decider_per_fold_fit') is not True
            or plan['calibration'].get('fresh_decider_per_heldout_id') is not True):
        raise ValueError('Frozen L1 protocol differs')
    for relative, expected in plan['source_sha256'].items():
        bind(relative, expected)
    bind('results/repeatability-v1/anyjev-l0-p0-v1/manifest.json', L0_SHA)
    bind('results/anyjev-cached-l1-cv5-2026-09-24/folds-v1.json', FOLD_SHA)
    bind('data/pilot/inputs.jsonl', plan['input_sha256'])
    bind('data/pilot/proposed_labels.jsonl', REFERENCE_SHA)
    l0 = json.loads(path(root, 'results/repeatability-v1/anyjev-l0-p0-v1/manifest.json').read_text())
    fold_file = json.loads(path(root, 'results/anyjev-cached-l1-cv5-2026-09-24/folds-v1.json').read_text())
    if fold_file['folds'] != plan['folds'] or [x['id'] for x in plan['heldout_requests']] != list(IDS):
        raise ValueError('L1 fold or held-out plan membership differs')
    if ([x['id'] for x in l0['requests']] != list(IDS)
            or any(a['input_sha256'] != b['input_sha256'] or a['prompt_sha256'] != b['request_sha256']
                   for a, b in zip(plan['heldout_requests'], l0['requests']))):
        raise ValueError('L1/L0 frozen request identity differs')
    folds = plan['folds']
    if (len(folds) != 5 or [f['fold'] for f in folds] != [1, 2, 3, 4, 5]
            or sorted(r for f in folds for r in f['test_ids']) != list(IDS)
            or any(len(f['test_ids']) != 12 or len(f['train_ids']) != 48
                   or set(f['train_ids']) != set(IDS) - set(f['test_ids']) for f in folds)
            or [f['fold'] for f in folds if set(f['test_ids']) & set(SMOKE_IDS)] != [1, 4, 5]):
        raise ValueError('Five-fold held-out isolation differs')
    fits = {(x['fold'], x['question']): x for x in plan['fit_requests']}
    if (len(fits) != 20 or set(fits) != {(n, field) for n in range(1, 6) for field in FIELDS}
            or any(fits[n, field]['train_ids'] != folds[n-1]['train_ids']
                   or fits[n, field]['n_calib'] != 48 for n, field in fits)):
        raise ValueError('L1 fit plan does not bind five fresh 48-label folds')
    policy = path(root, 'docs/LABELING_GUIDE.md').read_text().split('## Simulated routing')[0]
    specs = {x['id']: x for x in question_specs(policy)}
    if digest(policy) != plan['policy_prefix_sha256'] or digest(json.dumps(list(specs.values()),sort_keys=True)) != plan['question_specs_sha256']:
        raise ValueError('Frozen question or policy differs')
    inputs = jsonl(path(root, 'data/pilot/inputs.jsonl'))
    if [x.get('id') for x in inputs] != list(IDS):
        raise ValueError('Input membership differs')
    feedback = {x['id']:x['feedback'] for x in inputs}
    if any(digest(feedback[rid]) != request['input_sha256'] for rid, request in zip(IDS, plan['heldout_requests'])):
        raise ValueError('Held-out input hash differs')
    refs = jsonl(path(root, 'data/pilot/proposed_labels.jsonl'))
    if [x.get('id') for x in refs] != list(IDS) or any(x.get('review_version') != '0.2' for x in refs):
        raise ValueError('Provisional references differ')
    labels = {x['id']: x['proposed_labels'] for x in refs}
    if any(set(label) != set(FIELDS) or any(label[field] not in VALUES[field] for field in FIELDS)
           for label in labels.values()):
        raise ValueError('Reference fields or classes differ')
    canonical = lambda value: json.dumps(value,sort_keys=True,indent=2,ensure_ascii=False)+'\n'
    for fit in plan['fit_requests']:
        train = fit['train_ids']; field = fit['question']
        targets = [VALUES[field].index(labels[rid][field]) for rid in train]
        if (fit['train_input_sha256'] != digest(canonical([feedback[rid] for rid in train]))
                or fit['train_label_indices_sha256'] != digest(canonical(targets))):
            raise ValueError('Fold training-input or train-label provenance differs')
    return plan, l0, labels, specs, bind, bindings


def signature(item):
    return item['prompt_sha256'], tuple(item['answer_token_ids']), item['input_tokens']


def expected_signatures(l0, ids, field):
    requests = {x['id']: x for x in l0['requests']}
    first = requests[ids[0]]
    return Counter(signature(x) for x in first['native_calls'][1] if x['question'] == field) + Counter(
        signature(x) for rid in ids for x in requests[rid]['native_calls'][0] if x['question'] == field)


def decision(raw, options):
    if not isinstance(raw, dict) or raw.get('kind') != 'choice' or raw.get('level') != 'L1':
        raise ValueError('Invalid L1 decision')
    distribution = raw.get('distribution')
    if not isinstance(distribution, dict) or set(distribution) != set(options):
        raise ValueError('Invalid L1 distribution')
    probs = [distribution[x] for x in options]
    if (any(type(x) not in (int, float) or not math.isfinite(x) or x < 0 or x > 1 for x in probs)
            or abs(sum(probs)-1) > 1e-6):
        raise ValueError('Invalid L1 probabilities')
    winner = options[max(range(len(probs)), key=probs.__getitem__)]
    confidence = raw.get('confidence')
    if (raw.get('answer') != winner or type(confidence) not in (int, float)
            or not math.isfinite(confidence) or abs(confidence-max(probs)) > 1e-8):
        raise ValueError('Invalid L1 winner or confidence')
    return winner.split(': ', 1)[0]


def receipt(root, folder, stage, phase, claim, bind):
    # Admission claims may record an absolute path from the execution host. A
    # portable report requires a byte-identical receipt snapshot in this phase.
    directory = path(root, folder)
    matching = [child for child in directory.glob('*.json') if child.is_file()
                and sha(child) == claim.get('receipt_sha256')]
    if len(matching) != 1:
        raise ValueError('Exactly one portable root-review receipt snapshot is required')
    relative = matching[0].relative_to(Path(root).resolve())
    bind(relative, claim['receipt_sha256'])
    value = json.loads(matching[0].read_text())
    if (value.get('kind') != 'root-reviewed-anyjev-l1-direct-native-cv5-stage-v1'
            or value.get('approved') is not True or value.get('phase') != phase
            or value.get('stage') != stage or value.get('plan_sha256') != MANIFEST_SHA):
        raise ValueError('Root-review receipt identity differs')
    return value


def verify_stage(root, plan, l0, specs, phase, stage, bind, smoke_sha=None):
    folder = BASE / phase
    completion_path = folder / f'{stage}.completion.json'
    if not path(root, completion_path).exists():
        return None
    files = {key: folder / f'{stage}.{ext}' for key, ext in
             [('claim','claim.json'), ('journal','journal.jsonl'), ('raw','raw.jsonl'), ('records','records.jsonl')]}
    evidence = {'completion': bind(completion_path)}
    evidence.update({key: bind(relative) for key, relative in files.items()})
    completion = json.loads(path(root, completion_path).read_text())
    claim = json.loads(path(root, files['claim']).read_text())
    if (completion.get('claim_sha256') != evidence['claim']['sha256']
            or claim.get('phase') != phase or claim.get('stage') != stage
            or claim.get('plan_sha256') != MANIFEST_SHA
            or completion.get('phase') != phase or completion.get('stage') != stage
            or completion.get('plan_sha256') != MANIFEST_SHA
            or completion.get('hashes') != {key:evidence[key]['sha256'] for key in ('journal','raw','records')}):
        raise ValueError('L1 stage claim or completion hash differs')
    reviewed = receipt(root, folder, stage, phase, claim, bind)
    if stage == 'development':
        inspection_path = folder / 'smoke-inspection.json'
        inspected = json.loads(path(root, inspection_path).read_text())
        evidence['smokeInspection'] = bind(inspection_path)
        if (smoke_sha is None or completion.get('smoke_completion_sha256') != smoke_sha
                or completion.get('combined_heldout_count') != 60
                or reviewed.get('smoke_inspection_sha256') != evidence['smokeInspection']['sha256']
                or inspected.get('approved') is not True or inspected.get('phase') != phase
                or inspected.get('plan_sha256') != MANIFEST_SHA
                or inspected.get('smoke_completion_sha256') != smoke_sha
                or inspected.get('inspected_ids') != list(SMOKE_IDS)):
            raise ValueError('L1 development is not tied to inspected smoke')
    records = jsonl(path(root, files['records']))
    raw = jsonl(path(root, files['raw']))
    journal = jsonl(path(root, files['journal']))
    wanted = [rid for fold in plan['folds'] for rid in fold['test_ids']
              if (rid in SMOKE_IDS) == (stage == 'smoke')]
    expected = 3 if stage == 'smoke' else 57
    if (completion.get('count') != expected or len(records) != expected
            or [x.get('id') for x in records] != wanted
            or not journal or journal[0] != {'event':'stage_started','phase':phase,'stage':stage}
            or journal[-1] != {'event':'stage_completed','count':expected}):
        raise ValueError('L1 stage count/order/journal differs')
    started = [(x.get('kind'), x.get('operation_id')) for x in journal if x.get('event') == 'operation_started']
    returned = [(x.get('kind'), x.get('operation_id')) for x in journal if x.get('event') == 'operation_returned']
    if started != returned or len(started) != len(set(started)):
        raise ValueError('L1 started operation incomplete or duplicate')
    final_rows = [x for x in raw if x.get('kind') in ('calibration','decision')]
    finals = {(x['kind'],x['operation_id']):x['response'] for x in final_rows}
    if len(final_rows) != len(finals) or set(finals) != set(started):
        raise ValueError('L1 final raw responses differ from operation journal')
    backend = [x for x in raw if x.get('kind') == 'backend_return']
    if (len(raw) != len(final_rows)+len(backend)
            or any(x.get('operation_id') not in {op_id for _,op_id in started} for x in backend)):
        raise ValueError('Unknown or unclaimed L1 raw event')
    stage_folds = [1,4,5] if stage == 'smoke' else [2,3]
    expected_ops = [('calibration',f'{phase}/{stage}/fold-{n}/calibrate/{field}')
                    for n in stage_folds for field in FIELDS]
    expected_ops += [('decision',f'{phase}/{stage}/{rid}/{field}') for rid in wanted for field in FIELDS]
    if set(started) != set(expected_ops):
        raise ValueError('L1 fresh calibration or held-out operation set differs')
    input_positions = 0
    fold_by_id = {rid:f['fold'] for f in plan['folds'] for rid in f['test_ids']}
    for kind, op_id in started:
        field = op_id.rsplit('/',1)[1]
        ids = (plan['folds'][int(op_id.split('/')[3][5:])-1]['train_ids'] if kind == 'calibration'
               else [op_id.split('/')[-2]])
        expected_sig = expected_signatures(l0,ids,field)
        seen = Counter()
        events = [x for x in backend if x.get('operation_id') == op_id]
        if not events:
            raise ValueError('L1 backend raw capture missing')
        for event in events:
            if len(event.get('signatures',[])) != len(event.get('logprobs',[])):
                raise ValueError('L1 backend signatures/logits mismatch')
            for sig, logits in zip(event['signatures'],event['logprobs']):
                seen[signature(sig)] += 1
                if (len(logits) != len(sig['answer_token_ids'])
                        or any(type(v) not in (int,float) or not math.isfinite(v) for v in logits)):
                    raise ValueError('L1 backend logits invalid')
                input_positions += sig['input_tokens']
        if seen != expected_sig:
            raise ValueError('L1 native prompt/token identity differs')
    entries = completion.get('artifacts',[])
    required_folds = [1,4,5] if stage == 'smoke' else [1,2,3,4,5]
    if len(entries) != len(required_folds) or [x.get('fold') for x in entries] != required_folds:
        raise ValueError('L1 fold artifact membership differs')
    by_fold = {}
    for entry in entries:
        n = entry['fold']
        filename = entry.get('file')
        if filename != f'fold-{n}-artifacts.json':
            raise ValueError('L1 fold artifact filename differs')
        relative = folder / filename
        evidence[f'fold{n}'] = bind(relative,entry['sha256'])
        artifact = json.loads(path(root,relative).read_text())
        fold = plan['folds'][n-1]
        if (artifact.get('phase') != phase or artifact.get('fold') != n
                or artifact.get('train_ids') != fold['train_ids']
                or artifact.get('test_ids') != fold['test_ids']
                or artifact.get('plan_sha256') != MANIFEST_SHA
                or set(artifact.get('artifacts',{})) != set(FIELDS)):
            raise ValueError('L1 fold artifact source or train-only boundary differs')
        for field in FIELDS:
            fitted = artifact['artifacts'][field]
            prior = fitted.get('prior') if isinstance(fitted,dict) else None
            size = len(specs[field]['options'])
            if (not isinstance(fitted,dict) or fitted.get('model') != plan['model_id']
                    or fitted.get('question') != field or fitted.get('method') != 'temperature'
                    or fitted.get('n_calib') != 48 or fitted.get('prior_method') != 'content_free'
                    or fitted.get('prior_strength') != 1.0
                    or type(fitted.get('temperature')) not in (int,float)
                    or not math.isfinite(fitted['temperature']) or fitted['temperature'] <= 0
                    or not isinstance(prior,list) or len(prior) != size
                    or any(not isinstance(row,list) or len(row) != size or any(
                        type(v) not in (int,float) or not math.isfinite(v) or v < 0 for v in row)
                        for row in prior)):
                raise ValueError('L1 calibration artifact invalid')
            if stage == 'smoke' or n in (2,3):
                op_id = f'{phase}/{stage}/fold-{n}/calibrate/{field}'
                if fitted != finals.get(('calibration',op_id)):
                    raise ValueError('L1 fresh artifact differs from calibration raw')
        by_fold[n] = entry['sha256']
    for record in records:
        rid = record['id']; n = fold_by_id[rid]
        predicted = {}
        try:
            for field in FIELDS:
                raw_decision = finals.get(('decision',f'{phase}/{stage}/{rid}/{field}'))
                predicted[field] = decision(raw_decision,specs[field]['options'])
        except ValueError:
            predicted = None
        status = 'ok' if predicted is not None else 'invalid_output'
        request = next(x for x in plan['heldout_requests'] if x['id'] == rid)
        if (record.get('phase') != phase or record.get('stage') != stage or record.get('fold') != n
                or record.get('artifact_sha256') != by_fold[n]
                or record.get('reference_labels_in_prompt') is not False
                or record.get('input_sha256') != request['input_sha256']
                or record.get('status') != status or record.get('prediction') != predicted):
            raise ValueError('L1 held-out projection or fold artifact differs')
    return {'records':records,'evidence':evidence,'sha256':evidence['completion']['sha256'],
            'inputTokenPositions':input_positions,'artifactHashes':by_fold}


def score(records, labels):
    indexed = {x['id']:x for x in records}
    if set(indexed) != set(IDS):
        raise ValueError('L1 full pass must contain 60 unique held-out positions')
    valid = lambda rid: indexed[rid]['status'] == 'ok'
    by_field = {field:sum(valid(rid) and indexed[rid]['prediction'][field] == labels[rid][field] for rid in IDS)
                for field in FIELDS}
    all_four = sum(valid(rid) and all(indexed[rid]['prediction'][field] == labels[rid][field] for field in FIELDS)
                   for rid in IDS)
    outcome = Counter('valid' if valid(rid) else indexed[rid]['status'] for rid in IDS)
    return {'denominator':60,'valid':outcome['valid'],'outcomes':dict(sorted(outcome.items())),
            'fields':by_field,'allFour':all_four}, indexed


def confusion(indexed, labels):
    return {field:{reference:dict(sorted(Counter(
        indexed[rid]['prediction'][field] if indexed[rid]['status'] == 'ok' else INVALID
        for rid in IDS if labels[rid][field] == reference).items()))
        for reference in sorted({labels[rid][field] for rid in IDS})} for field in FIELDS}


def stats(values):
    return {'completedPasses':len(values),'values':values,
            'mean':sum(values)/3 if len(values)==3 else None,
            'range':[min(values),max(values)] if len(values)==3 else None}


def build(root=ROOT):
    root = Path(root)
    plan,l0,labels,specs,bind,bindings = source(root)
    passes = {}; missing = []; indexed = {}; previous_open = False
    for phase in PASSES:
        name = phase.split('/')[0]
        folder = BASE / phase
        if not path(root,folder/'development.completion.json').exists():
            claimed = any(path(root,folder/f'{stage}.claim.json').exists() for stage in ('smoke','development'))
            missing.append({'pass':name,'condition':'P0','status':'claimed_in_progress_or_interrupted' if claimed else 'not_started'})
            previous_open = True
            continue
        if previous_open:
            raise ValueError('Later closed L1 pass follows open predecessor')
        smoke = verify_stage(root,plan,l0,specs,phase,'smoke',bind)
        full = verify_stage(root,plan,l0,specs,phase,'development',bind,smoke['sha256'])
        for n in (1,4,5):
            if full['artifactHashes'][n] != smoke['artifactHashes'][n]:
                raise ValueError('Development substituted reviewed smoke fit')
        combined = smoke['records'] + full['records']
        result,indexed[name] = score(combined,labels)
        passes[name] = {'P0':{'completionStatus':'complete','score':result,
            'confusionCounts':confusion(indexed[name],labels),
            'predictedClassCounts':{field:dict(sorted(Counter(indexed[name][rid]['prediction'][field]
                for rid in IDS if indexed[name][rid]['status']=='ok').items())) for field in FIELDS},
            'usage':{'requestCount':60,'clientSeconds':None,'inferenceSeconds':None,
                     'tokens':{'input_token_positions':smoke['inputTokenPositions']+full['inputTokenPositions'],
                               'output_tokens':None,'billed_input_tokens':None},
                     'actualCostUsd':None,'costNote':'Local hardware and electricity cost not measured.'},
            'evidence':{'smoke':smoke['evidence'],'development':full['evidence']}}}
    names = list(indexed)
    scores = [passes[name]['P0']['score'] for name in names]
    flips = []
    for i,left in enumerate(names):
        for right in names[i+1:]:
            eligible = [rid for rid in IDS if indexed[left][rid]['status']=='ok' and indexed[right][rid]['status']=='ok']
            flips.append({'condition':'P0','from':left,'to':right,'denominator':len(eligible),
                'excludedIds':[rid for rid in IDS if rid not in eligible],
                'fields':{field:[rid for rid in eligible if indexed[left][rid]['prediction'][field] != indexed[right][rid]['prediction'][field]] for field in FIELDS},
                'fourFieldVector':[rid for rid in eligible if any(indexed[left][rid]['prediction'][field] != indexed[right][rid]['prediction'][field] for field in FIELDS)]})
    eligible = [rid for rid in IDS if len(names)==3 and all(indexed[name][rid]['status']=='ok' for name in names)]
    across = {'P0':{'denominator':len(eligible),'excludedIds':[rid for rid in IDS if rid not in eligible],
        'fields':{field:[rid for rid in eligible if len({indexed[name][rid]['prediction'][field] for name in names})>1] for field in FIELDS},
        'fourFieldVector':[rid for rid in eligible if len({tuple(indexed[name][rid]['prediction'][field] for field in FIELDS) for name in names})>1]}} if len(names)==3 else {}
    return {'schema':'anyjev-l1-direct-native-repeat-findings-v1',
        'configuration':plan['configuration'],'displayName':'AnyJev Qwen3 0.6B · direct-native L1 CV5',
        'model':plan['model_id'],'provider':'Local native MPS','method':'native-output-stability',
        'conditionOrder':['P0'],'passOrder':[x.split('/')[0] for x in PASSES],
        'denominator':60,'plannedConditions':3,'completedConditions':len(names),
        'referenceVersion':'0.2','referenceStatus':'AI-reviewed provisional, not independent adjudication',
        'referenceClassCounts':{field:dict(sorted(Counter(labels[rid][field] for rid in IDS).items())) for field in FIELDS},
        'passes':passes,'missingPasses':missing,'partialPasses':[],
        'threePassSummary':{'P0':{'allFour':stats([x['allFour'] for x in scores]),
                             'fields':{field:stats([x['fields'][field] for x in scores]) for field in FIELDS}}},
        'pairwiseFlips':flips,'changesAcrossThreePasses':across,'withinPassPromptDeltas':[],
        'sourceBindings':bindings,'declaredExternalSourceHashes':plan['upstream_sha256'],
        'declaredModelAssetHashes':plan['asset_sha256'],
        'limitations':['The historical cached-score L1 run is observational and is not one of these fresh passes.',
            'Fold isolation is enforced by code and receipts, not by an operating-system boundary; the worker can read all 60 provisional labels.',
            'Client request and isolated inference time were not saved by this native controller.',
            'Input token positions are from native prompt signatures, not billed token usage.',
            'Local hardware and electricity costs were not measured.',
            'Private model assets and upstream source hashes are declared from the frozen plan; this portable report does not rehash them.',
            'Provisional v0.2 references are not independent adjudication.']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--check',action='store_true')
    args = parser.parse_args(argv)
    result = build()
    value = json.dumps(result,indent=2,ensure_ascii=False)+'\n'
    if args.check:
        if not args.output.exists() or args.output.read_text()!=value:
            raise ValueError(f'Stale report: {args.output}')
    else:
        args.output.write_text(value)
    print(f"{result['configuration']} {result['completedConditions']}/3")


if __name__ == '__main__':
    main()
