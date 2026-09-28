"""Offline source, billing, and terminal checks for Gemini repeat findings."""
import base64
import copy
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import build_gemini_repeat_findings as report
import gemini_repeat_study as study


def write_rows(path, rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))


class GeminiRepeatFindingsTest(unittest.TestCase):
    def test_real_historical_series_and_unknown_time(self):
        value={'series':[report.build_series(config) for config in study.CONFIGS]}
        self.assertEqual(len(value['series']),2)
        expected={'gemini36-flash-low-p0-openrouter-v3':(55,55,54),
                  'gemini37-flash-low-p0-openrouter-v3':(57,55,57)}
        for series in value['series']:
            self.assertEqual(series['denominator'],60)
            self.assertEqual(series['plannedConditions'],9)
            self.assertGreaterEqual(series['completedConditions'],3)
            self.assertEqual(sum(len(series['passes'][name]) for name in report.PASSES)+len(series['missingPasses']),9)
            self.assertEqual(tuple(series['passes']['original'][c]['score']['allFour'] for c in report.CONDITIONS),expected[series['configuration']])
            for condition in report.CONDITIONS:
                original=series['passes']['original'][condition]
                self.assertEqual(original['score']['denominator'],60)
                self.assertEqual(original['usage']['unknownCostCount'],0)
                self.assertIsNone(original['usage']['requestSecondsTotal'])
                self.assertIsNone(original['usage']['inferenceSeconds'])
                attempts=report._rows(ROOT,original['evidence']['development_attempts']['path'])
                observed=sum((Decimal(a['observed_cost_usd']) for a in attempts),Decimal(0))
                self.assertEqual(Decimal(original['usage']['actualCostUsd']),observed)

    def test_roster_medium_effort_preserved_and_mismatch_rejected(self):
        config='gemini36-flash-medium-p0-openrouter-v3'
        controller=report._controller(config)
        plan=controller.expected_plan(config,'repeat2')
        ids=[f'DEV-{i:03d}' for i in range(1,61)]
        labels={r['id']:r['proposed_labels'] for r in report._rows(ROOT,report.LABELS)}
        bind,_=report._binder(ROOT)
        entry,records=report._historical(ROOT,plan,'P1',ids,labels,bind)
        self.assertEqual(entry['score']['valid'],60)
        self.assertEqual(len(records),60)
        self.assertEqual(plan['effort'],'medium')
        bad=copy.deepcopy(plan);bad['effort']='low'
        with self.assertRaisesRegex(ValueError,'frozen request'):
            report._historical(ROOT,bad,'P1',ids,labels,bind)

    def test_open_journal_excluded_and_source_hash_enforced(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            journal=root/'open.jsonl'
            write_rows(journal,[{'event':'phase_started'}])
            self.assertIsNone(report._terminal(root,'open.jsonl'))
            journal.write_text('{"event":"phase_completed"')
            self.assertIsNone(report._terminal(root,'open.jsonl'))
            source=root/'source.json';source.write_text('{}')
            bind,_=report._binder(root)
            with self.assertRaisesRegex(ValueError,'Source hash changed'):
                bind('source.json','0'*64)

    def test_unknown_charge_does_not_become_zero(self):
        attempts=[{'raw_response':{'usage':{'prompt_tokens':4,'completion_tokens':2,
                    'prompt_tokens_details':{'cached_tokens':1,'cache_write_tokens':0},
                    'completion_tokens_details':{'reasoning_tokens':1}}},
                   'observed_cost_usd':'0.25','cost_unknown':False,'elapsed_seconds':None},
                  {'raw_response':None,'observed_cost_usd':None,'cost_unknown':True,
                   'elapsed_seconds':None}]
        usage=report._usage(attempts,pending=1)
        self.assertEqual(usage['knownCostUsd'],'0.25')
        self.assertIsNone(usage['actualCostUsd'])
        self.assertEqual(usage['unknownCostCount'],2)
        self.assertIsNone(usage['tokens']['input_tokens'])
        self.assertIsNone(usage['requestSecondsTotal'])

    def test_parseable_nonstop_finish_retains_labels_but_is_not_scored(self):
        rid='DEV-001'
        prediction={'sentiment':'positive','follow_up_needed':'no',
                    'serious_concern_reported':'no','testimonial_potential':'yes'}
        body={'model':'returned-model','provider':study.v3.PROVIDER_NAME,
              'choices':[{'message':{'content':'valid JSON'},'finish_reason':'length'}]}
        with patch.object(study,'parse_batch',return_value={rid:prediction}), \
             patch.object(study,'allowed_returned_models',return_value={'returned-model'}):
            classified=study.classify({'model':'requested-model'}, {'record_ids':[rid]},body,{})
        self.assertEqual(classified['status'],'invalid_output')
        self.assertEqual(report._saved_prediction(classified,rid),prediction)
        row={'id':rid,'status':classified['status'],
             'prediction':report._saved_prediction(classified,rid)}
        self.assertEqual(report.shared.outcome(row),'invalid_output')

    def test_historical_batch_with_saved_invalid_predictions_is_accepted(self):
        config='gemini36-flash-low-p0-openrouter-v3';condition='P0'
        plan=json.loads((ROOT/report.BASE/config/'repeat2/manifest.json').read_text())
        history=plan['conditions'][condition]['historical']
        attempts=copy.deepcopy(report._rows(ROOT,history['development_attempts']['path']))
        records=copy.deepcopy(report._rows(ROOT,history['development_records']['path']))
        attempts[0]['status']='invalid_output'
        for row in records[:10]:row['status']='invalid_output'
        ids=[f'DEV-{i:03d}' for i in range(1,61)]
        labels={row['id']:row['proposed_labels'] for row in report._rows(ROOT,report.LABELS)}
        def saved(_,relative):
            if relative==history['development_attempts']['path']:return attempts
            if relative==history['development_records']['path']:return records
            raise AssertionError(relative)
        with patch.object(report,'_rows',side_effect=saved):
            entry,_=report._historical(ROOT,plan,condition,ids,labels,
                                       lambda path,sha:{'path':path,'sha256':sha})
        self.assertEqual(entry['score']['outcomes']['invalid_output'],10)
        self.assertEqual(entry['score']['valid'],50)

    def test_raw_http_error_linkage_and_mismatch(self):
        request={'record_ids':['DEV-001'],'payload_sha256':'a'*64}
        attempt={'attempt_id':'one','status':'service_error','http_status':429,
                 'error_body':'limited','error_headers':{'retry-after':'10'},
                 'read_error':None,'body_truncated_at_limit':False}
        raw={'record_ids':['DEV-001'],'attempt_id':'one','request_sha256':'a'*64,
             'http_status':429,'error_body':'limited','error_headers':{'retry-after':'10'},
             'read_error':None,'body_truncated_at_limit':False}
        self.assertIsNone(report._raw(raw,attempt,request))
        raw['request_sha256']='b'*64
        with self.assertRaisesRegex(ValueError,'identity differs'):
            report._raw(raw,attempt,request)

    def test_closed_429_batch_keeps_sixty_denominator(self):
        config='gemini36-flash-low-p0-openrouter-v3';repeat='repeat2';condition='P1'
        plan=json.loads((ROOT/report.BASE/config/repeat/'manifest.json').read_text())
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            for name in ('repeat2','repeat3'):
                relative=report.BASE/config/name/'manifest.json'
                target=root/relative;target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(ROOT/relative,target)
            for key in ('catalog','endpoints'):
                relative=Path(plan['conditions'][condition][key]['path'])
                target=root/relative;target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(ROOT/relative,target)
            budget=report.BASE/config/'budget-partition-v1.json'
            write_rows(root/budget,[{'test':'offline'}])
            plan_hash=report._sha(root/report.BASE/config/repeat/'manifest.json')
            phase='development';request=plan['conditions'][condition]['requests'][1]
            ids=request['record_ids'];attempt_id='offline-429'
            row={'attempt_id':attempt_id,'phase':phase,'condition':condition,'repeat':repeat,
                 'batch_index':1,'ids':ids,'request':request['payload'],
                 'request_sha256':request['payload_sha256'],'reserved_cost_usd':request['reserve_usd'],
                 'model':plan['model'],'effort':'low','provider':plan['provider'],
                 'reference_labels_read':False,'plan_sha256':plan_hash,'status':'service_error',
                 'predictions':{},'cost_unknown':True,'billing_ok':False,'observed_cost_usd':None,
                 'http_status':429,'error_body':'rate limited','error_headers':{'retry-after':'8'},
                 'read_error':None,'body_truncated_at_limit':False}
            raw={'record_ids':ids,'attempt_id':attempt_id,'request_sha256':request['payload_sha256'],
                 'http_status':429,'error_body':'rate limited','error_headers':{'retry-after':'8'},
                 'read_error':None,'body_truncated_at_limit':False}
            base=report.BASE/config/repeat/condition
            inspection=root/base/'smoke-inspection.json'
            write_rows(inspection,[{'schema':'gemini-repeat-smoke-inspection-v1',
                                    'decision':'accepted_unchanged'}])
            review={'schema':study.REVIEW_SCHEMA,'approved':True,'configuration_id':config,
                    'repeat':repeat,'condition':condition,'phase':phase,'plan_sha256':plan_hash,
                    'plan_sha256_by_repeat':{name:report._sha(root/report.BASE/config/name/'manifest.json')
                                             for name in ('repeat2','repeat3')},
                    'controller_sha256':plan['source_bindings']['controller']['sha256'],
                    'partition_id':plan['partition_id'],'partition_cap_usd':study.CAP,
                    'budget_manifest':{'path':str(budget),'sha256':report._sha(root/budget)},
                    'smoke_inspection_sha256':report._sha(inspection)}
            review_path=root/base/'development-root-review.json'
            write_rows(review_path,[review])
            claim={'schema':study.SCHEMA+'-claim','plan_sha256':plan_hash,
                   'review_sha256':report._sha(review_path),'condition':condition,'phase':phase}
            write_rows(root/base/'development.claim.json',[claim])
            write_rows(root/base/'development.attempts.jsonl',[row])
            write_rows(root/base/'development.responses.jsonl',[raw])
            write_rows(root/base/'development.records.jsonl',[
                {'id':rid,'status':'service_error','prediction':None,'phase':phase,
                 'batch_index':1,'batch_position':pos,'attempt_id':attempt_id,
                 'request_sha256':request['payload_sha256']} for pos,rid in enumerate(ids)])
            events=[{'event':'phase_started','phase':phase,'condition':condition,'expected_batches':6},
                    {'event':'request_intent','record_ids':ids,'request_sha256':request['payload_sha256']},
                    {'event':'request_started','record_ids':ids,'request_sha256':request['payload_sha256'],
                     'attempt_id':attempt_id},
                    {'event':'request_finished','attempt_id':attempt_id,'status':'service_error',
                     'billing_ok':False,'cost_unknown':True},
                    {'event':'phase_stopped','attempt_id':attempt_id,'reason':'service_error'}]
            write_rows(root/base/'development.journal.jsonl',events)
            labels={r['id']:r['proposed_labels'] for r in report._rows(ROOT,report.LABELS)}
            bind,_=report._binder(root)
            entry,reason,indexed=report._phase(root,plan,plan_hash,condition,phase,
                                                 [f'DEV-{i:03d}' for i in range(1,61)],labels,bind)
            self.assertIsNone(reason)
            self.assertEqual(entry['completionStatus'],'partial')
            self.assertEqual(entry['score']['denominator'],60)
            self.assertEqual(entry['score']['outcomes']['service_error'],10)
            self.assertEqual(entry['score']['outcomes']['never_sent'],50)
            self.assertEqual(entry['usage']['unknownCostCount'],1)
            self.assertIsNone(entry['usage']['actualCostUsd'])
            write_rows(root/base/'development.journal.jsonl',[
                events[0],events[1],events[2],
                {'event':'phase_aborted','reason':'exception_or_interruption'}])
            for name in ('attempts','responses','records'):
                write_rows(root/base/f'development.{name}.jsonl',[])
            bind,_=report._binder(root)
            aborted,_,_=report._phase(root,plan,plan_hash,condition,phase,
                                       [f'DEV-{i:03d}' for i in range(1,61)],labels,bind)
            self.assertEqual(aborted['score']['outcomes']['unknown_started'],10)
            self.assertEqual(aborted['score']['outcomes']['never_sent'],50)
            self.assertEqual(aborted['usage']['unknownCostCount'],1)

    def test_cli_check_does_not_overwrite_stale_output(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(report,'build',return_value={'schema':'offline-test','series':[]}):
            output=Path(folder)/'report.json'
            report.main(['--output',str(output)])
            report.main(['--output',str(output),'--check'])
            output.write_text('{}\n')
            with self.assertRaisesRegex(ValueError,'Stale report'):
                report.main(['--output',str(output),'--check'])
            self.assertEqual(output.read_text(),'{}\n')


if __name__=='__main__':unittest.main()
