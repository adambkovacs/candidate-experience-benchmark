"""Synthetic-only offline tests for the direct-native L1 evidence report."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_anyjev_l1_repeat_findings as report

SOURCE = Path(__file__).resolve().parents[1]


def write_json(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True,indent=2)+'\n')


def write_rows(path,values):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(x,sort_keys=True)+'\n' for x in values))


class L1ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='synthetic-l1-report-')
        self.root=Path(self.tmp.name)
        required=[report.BASE/'manifest.json',
            Path('results/repeatability-v1/anyjev-l0-p0-v1/manifest.json'),
            Path('results/anyjev-cached-l1-cv5-2026-09-24/folds-v1.json'),
            Path('data/pilot/inputs.jsonl'),Path('data/pilot/proposed_labels.jsonl'),
            Path('docs/LABELING_GUIDE.md')]
        manifest=json.loads((SOURCE/required[0]).read_text())
        required += [Path(x) for x in manifest['source_sha256']]
        for relative in required:
            target=self.root/relative;target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(SOURCE/relative,target)
        self.plan,self.l0,self.labels,self.specs,self.bind,_=report.source(self.root)

    def tearDown(self):self.tmp.cleanup()

    def _stage(self,phase,stage,smoke_sha=None,wrong_artifact=None):
        folder=report.BASE/phase
        wanted=[rid for fold in self.plan['folds'] for rid in fold['test_ids']
                if (rid in report.SMOKE_IDS)==(stage=='smoke')]
        fresh=[1,4,5] if stage=='smoke' else [2,3]
        journal=[{'event':'stage_started','phase':phase,'stage':stage}]
        raw=[];records=[]; artifacts=[]
        by_id={rid:f['fold'] for f in self.plan['folds'] for rid in f['test_ids']}
        artifact_hash={}
        for n in [1,2,3,4,5]:
            if stage=='smoke' and n not in fresh:continue
            if stage=='development' and n in (1,4,5):
                original=report.BASE/phase/f'fold-{n}-artifacts.json'
                artifact_hash[n]=report.sha(report.path(self.root,original))
                artifacts.append({'fold':n,'file':original.name,'sha256':artifact_hash[n]})
                continue
            fold=self.plan['folds'][n-1]
            fitted={}
            for field in report.FIELDS:
                op=f'{phase}/{stage}/fold-{n}/calibrate/{field}'
                journal.append({'event':'operation_started','kind':'calibration','operation_id':op})
                sig=list(report.expected_signatures(self.l0,fold['train_ids'],field).elements())
                signatures=[{'prompt_sha256':x[0],'answer_token_ids':list(x[1]),'input_tokens':x[2]} for x in sig]
                raw.append({'kind':'backend_return','operation_id':op,'signatures':signatures,
                            'logprobs':[[0.0]*len(x['answer_token_ids']) for x in signatures]})
                k=len(self.specs[field]['options'])
                fitted[field]={'model':self.plan['model_path'],
                               'question':report.question_key(self.specs[field]),'method':'temperature',
                               'n_calib':48,'prior_method':'content_free','prior_strength':1.0,
                               'temperature':1.0,'prior':[[0.0]*k for _ in range(k)]}
                if wrong_artifact and n == 1 and field == 'sentiment':
                    fitted[field][wrong_artifact] = 'wrong-' + wrong_artifact
                raw.append({'kind':'calibration','operation_id':op,'response':fitted[field]})
                journal.append({'event':'operation_returned','kind':'calibration','operation_id':op})
            artifact={'phase':phase,'fold':n,'train_ids':fold['train_ids'],'test_ids':fold['test_ids'],
                      'artifacts':fitted,'plan_sha256':report.MANIFEST_SHA}
            relative=report.BASE/phase/f'fold-{n}-artifacts.json'
            write_json(self.root/relative,artifact)
            artifact_hash[n]=report.sha(self.root/relative)
            artifacts.append({'fold':n,'file':relative.name,'sha256':artifact_hash[n]})
        artifacts.sort(key=lambda x:x['fold'])
        for rid in wanted:
            prediction={}
            for field in report.FIELDS:
                op=f'{phase}/{stage}/{rid}/{field}'
                journal.append({'event':'operation_started','kind':'decision','operation_id':op})
                sig=list(report.expected_signatures(self.l0,[rid],field).elements())
                signatures=[{'prompt_sha256':x[0],'answer_token_ids':list(x[1]),'input_tokens':x[2]} for x in sig]
                raw.append({'kind':'backend_return','operation_id':op,'signatures':signatures,
                            'logprobs':[[0.0]*len(x['answer_token_ids']) for x in signatures]})
                options=self.specs[field]['options'];choice=options[0]
                distribution={x:(1.0 if x==choice else 0.0) for x in options}
                raw.append({'kind':'decision','operation_id':op,
                            'response':{'kind':'choice','level':'L1','distribution':distribution,
                                        'answer':choice,'confidence':1.0}})
                journal.append({'event':'operation_returned','kind':'decision','operation_id':op})
                prediction[field]=choice.split(': ',1)[0]
            n=by_id[rid]
            request=next(x for x in self.plan['heldout_requests'] if x['id']==rid)
            records.append({'id':rid,'fold':n,'phase':phase,'stage':stage,'status':'ok',
                            'prediction':prediction,'artifact_sha256':artifact_hash[n],
                            'input_sha256':request['input_sha256'],'reference_labels_in_prompt':False})
        journal.append({'event':'stage_completed','count':len(wanted)})
        paths={key:report.BASE/phase/f'{stage}.{suffix}' for key,suffix in
               [('journal','journal.jsonl'),('raw','raw.jsonl'),('records','records.jsonl')]}
        for key,values in [('journal',journal),('raw',raw),('records',records)]:write_rows(self.root/paths[key],values)
        receipt={'kind':'root-reviewed-anyjev-l1-direct-native-cv5-stage-v1','approved':True,
                 'phase':phase,'stage':stage,'plan_sha256':report.MANIFEST_SHA}
        if stage=='development':
            receipt['smoke_inspection_sha256']=report.sha(self.root/report.BASE/phase/'smoke-inspection.json')
        receipt_path=report.BASE/phase/f'{stage}.root-review.json';write_json(self.root/receipt_path,receipt)
        claim={'phase':phase,'stage':stage,'plan_sha256':report.MANIFEST_SHA,
               'receipt_path':str(self.root/receipt_path),'receipt_sha256':report.sha(self.root/receipt_path),
               'policy':'started native operation never automatically replayed'}
        claim_path=report.BASE/phase/f'{stage}.claim.json';write_json(self.root/claim_path,claim)
        completion={'phase':phase,'stage':stage,'plan_sha256':report.MANIFEST_SHA,
                    'count':len(wanted),'claim_sha256':report.sha(self.root/claim_path),
                    'hashes':{key:report.sha(self.root/relative) for key,relative in paths.items()},
                    'artifacts':artifacts}
        if stage=='development':
            completion['smoke_completion_sha256']=smoke_sha
            completion['combined_heldout_count']=60
        completion_path=report.BASE/phase/f'{stage}.completion.json';write_json(self.root/completion_path,completion)
        return report.sha(self.root/completion_path)

    def _closed_first(self,wrong_artifact=None):
        phase='fresh1/P0';smoke=self._stage(phase,'smoke',wrong_artifact=wrong_artifact)
        inspection={'approved':True,'phase':phase,'plan_sha256':report.MANIFEST_SHA,
                    'smoke_completion_sha256':smoke,'inspected_ids':list(report.SMOKE_IDS)}
        write_json(self.root/report.BASE/phase/'smoke-inspection.json',inspection)
        self._stage(phase,'development',smoke)

    def test_all_open_is_explicit_and_unscored(self):
        result=report.build(self.root)
        self.assertEqual(result['completedConditions'],0)
        self.assertEqual([x['status'] for x in result['missingPasses']],['not_started']*3)
        self.assertIsNone(result['threePassSummary']['P0']['allFour']['range'])

    def test_claimed_open_is_not_scored_or_parsed(self):
        folder=self.root/report.BASE/'fresh1/P0';folder.mkdir(parents=True)
        (folder/'smoke.claim.json').write_text('{"started":true}\n')
        (folder/'smoke.raw.jsonl').write_text('{incomplete')
        result=report.build(self.root)
        self.assertEqual(result['missingPasses'][0]['status'],'claimed_in_progress_or_interrupted')

    def test_synthetic_closed_pass_has_fixed_denominator_and_lineage(self):
        self._closed_first();result=report.build(self.root)
        self.assertEqual(result['completedConditions'],1)
        observed=result['passes']['fresh1']['P0']
        self.assertEqual(observed['score']['denominator'],60)
        self.assertEqual(observed['score']['valid'],60)
        self.assertEqual(sum(sum(sum(row.values()) for row in field.values()) for field in observed['confusionCounts'].values()),240)
        self.assertIsNone(observed['usage']['clientSeconds'])
        self.assertGreater(observed['usage']['tokens']['input_token_positions'],0)
        self.assertEqual(len(observed['evidence']['development']['fold1']['sha256']),64)

    def test_synthetic_artifact_and_raw_tamper_fail(self):
        self._closed_first()
        target=self.root/report.BASE/'fresh1/P0/fold-1-artifacts.json'
        artifact=json.loads(target.read_text());artifact['artifacts']['sentiment']['temperature']=2.0
        write_json(target,artifact)
        with self.assertRaisesRegex(ValueError,'Hash differs'):
            report.build(self.root)

    def test_wrong_frozen_backend_model_rejected(self):
        self._closed_first(wrong_artifact='model')
        with self.assertRaisesRegex(ValueError,'L1 calibration artifact invalid'):
            report.build(self.root)

    def test_wrong_frozen_question_key_rejected(self):
        self._closed_first(wrong_artifact='question')
        with self.assertRaisesRegex(ValueError,'L1 calibration artifact invalid'):
            report.build(self.root)

    def test_synthetic_raw_tamper_fails(self):
        self._closed_first()
        target=self.root/report.BASE/'fresh1/P0/development.raw.jsonl'
        with target.open('ab') as stream:stream.write(b'{"kind":"decision","operation_id":"extra"}\n')
        with self.assertRaisesRegex(ValueError,'hash differs'):
            report.build(self.root)

    def test_synthetic_missing_receipt_snapshot_fails(self):
        self._closed_first()
        (self.root/report.BASE/'fresh1/P0/smoke.root-review.json').unlink()
        with self.assertRaisesRegex(ValueError,'receipt snapshot'):
            report.build(self.root)

    def test_synthetic_inspection_drift_fails(self):
        self._closed_first()
        target=self.root/report.BASE/'fresh1/P0/smoke-inspection.json'
        value=json.loads(target.read_text());value['approved']=False;write_json(target,value)
        with self.assertRaisesRegex(ValueError,'inspected smoke'):
            report.build(self.root)

    def test_invalid_counts_include_missing_column(self):
        records=[{'id':rid,'status':'invalid_output' if rid=='DEV-001' else 'ok',
                  'prediction':None if rid=='DEV-001' else self.labels[rid]} for rid in report.IDS]
        scored,index=report.score(records,self.labels)
        self.assertEqual(scored['denominator'],60)
        self.assertEqual(scored['valid'],59)
        matrix=report.confusion(index,self.labels)
        self.assertEqual(sum(row.get(report.INVALID,0) for row in matrix['sentiment'].values()),1)

    def test_decision_rejects_malformed_probability(self):
        choices=self.specs['sentiment']['options']
        raw={'kind':'choice','level':'L1','distribution':{x:0.3 for x in choices},
             'answer':choices[0],'confidence':0.3}
        with self.assertRaisesRegex(ValueError,'probabilities'):
            report.decision(raw,choices)


if __name__=='__main__':unittest.main()
