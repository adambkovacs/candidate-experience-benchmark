"""Offline evidence and missing-phase checks for native AnyJev raw reporting."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import build_anyjev_raw_repeat_findings as report


class AnyJevRawReportTest(unittest.TestCase):
    def test_real_closed_evidence_scores_and_time_kind(self):
        value=report.build()
        self.assertEqual(value['conditionOrder'],['P0'])
        self.assertEqual(value['method'],'native-output-stability')
        self.assertEqual(value['denominator'],60)
        self.assertEqual(value['passes']['original']['P0']['score']['allFour'],0)
        self.assertEqual(value['passes']['repeat2']['P0']['score']['allFour'],0)
        self.assertEqual(value['passes']['original']['P0']['score']['valid'],60)
        self.assertEqual(value['passes']['repeat2']['P0']['score']['valid'],60)
        self.assertEqual(value['pairwiseFlips'][0]['fourFieldVector']['changed'],0)
        self.assertIsNone(value['passes']['original']['P0']['usage']['inferenceSeconds'])
        self.assertIsNone(value['passes']['repeat2']['P0']['usage']['inferenceSeconds'])
        self.assertIsNone(value['passes']['repeat2']['P0']['usage']['modelLoadSeconds'])
        self.assertIsNone(value['passes']['original']['P0']['usage']['actualCostUsd'])
        self.assertIn('lengths, not prompt hashes',value['limitations'][0])
        self.assertIn({'path':str(report.MANIFEST),'sha256':report.MANIFEST_SHA},
                      value['sourceBindings'])

    def test_open_repeat3_is_not_read_even_with_partial_journal(self):
        original_path=report.path
        original_rows=report.rows
        def missing(root,relative):
            if relative==report.BASE/'repeat3/P0/development.completion.json':
                return Path('/private/tmp/anyjev-report-nonexistent-development-completion.json')
            return original_path(root,relative)
        def only_closed(root,relative):
            if str(relative).startswith(str(report.BASE/'repeat3')):
                raise AssertionError('read live repeat3 evidence')
            return original_rows(root,relative)
        with patch.object(report,'path',side_effect=missing),patch.object(report,'rows',side_effect=only_closed):
            value=report.build()
        self.assertEqual(value['completedConditions'],2)
        self.assertEqual(value['missingPasses'],[{'pass':'repeat3','condition':'P0',
                                                  'status':'claimed_in_progress_or_interrupted'}])
        self.assertNotIn('P0',value['passes']['repeat3'])

    def test_unclaimed_repeat_is_not_started(self):
        original=report.path
        def absent(root,relative):
            if relative in (report.BASE/'repeat3/P0/development.completion.json',
                            report.BASE/'repeat3/P0/smoke.claim.json',
                            report.BASE/'repeat3/P0/development.claim.json'):
                return Path('/private/tmp/anyjev-report-absent-phase-file')
            return original(root,relative)
        with patch.object(report,'path',side_effect=absent):value=report.build()
        self.assertEqual(value['missingPasses'],[{'pass':'repeat3','condition':'P0',
                                                  'status':'not_started'}])

    def test_exact_repeat3_inspection_can_omit_optional_raw_hash(self):
        plan,ids,labels,specs,_,_,bind,_=report.source_context(ROOT)
        phase='repeat3/P0'
        _,smoke_records,_,evidence=report.stage(ROOT,plan,phase,'smoke',specs,bind)
        inspection=report.path(ROOT,report.BASE/phase/'smoke-inspection.json')
        self.assertNotIn('raw_sha256',json.loads(inspection.read_text()))
        self.assertEqual(report.check_smoke_inspection(ROOT,phase,ids,smoke_records,evidence,bind),
                         {'path':str(report.BASE/phase/'smoke-inspection.json'),
                          'sha256':report.sha(inspection)})
        real=json.loads(inspection.read_text())
        bad={**real,'raw_sha256':'0'*64}
        original_path=report.path
        with tempfile.TemporaryDirectory() as folder:
            altered=Path(folder)/'smoke-inspection.json'
            altered.write_text(json.dumps(bad))
            def substituted(root,relative):
                if relative==report.BASE/phase/'smoke-inspection.json':return altered
                return original_path(root,relative)
            with patch.object(report,'path',side_effect=substituted):
                # The development receipt remains bound to the genuine inspection.
                with self.assertRaisesRegex(ValueError,'inspected smoke'):
                    report.check_smoke_inspection(ROOT,phase,ids,smoke_records,evidence,bind)

    def test_raw_projection_or_signature_drift_is_rejected(self):
        plan,ids,labels,specs,_,_,bind,_=report.source_context(ROOT)
        folder=report.BASE/'repeat2/P0'
        relative=folder/'development.raw.jsonl'
        captures=copy.deepcopy(report.rows(ROOT,relative))
        captures[0]['native_decisions'][0]['answer_token_ids']=[0]
        original=report.rows
        with patch.object(report,'rows',side_effect=lambda root,name:
                captures if name==relative else original(root,name)):
            with self.assertRaisesRegex(ValueError,'output binding differs'):
                report.stage(ROOT,plan,'repeat2/P0','development',specs,bind)

    def test_historical_wrong_prediction_is_rejected(self):
        plan,ids,labels,specs,_,original_root,bind,_=report.source_context(ROOT)
        relative=Path(plan['historical']['directory'])/'development.jsonl'
        saved=copy.deepcopy(report.rows(ROOT,relative))
        saved[0]['prediction']['sentiment']='positive'
        original=report.rows
        with patch.object(report,'rows',side_effect=lambda root,name:
                saved if name==relative else original(root,name)):
            with self.assertRaisesRegex(ValueError,'Historical AnyJev raw row differs'):
                report.historical(ROOT,plan,ids,labels,specs,original_root,bind)

    def test_cli_check_preserves_stale_file(self):
        with tempfile.TemporaryDirectory() as folder:
            output=Path(folder)/'report.json'
            with patch.object(report,'build',return_value={'schema':'offline','passes':{},
                       'configuration':'test','completedConditions':0}):
                report.main(['--output',str(output)])
                report.main(['--output',str(output),'--check'])
                output.write_text('{}\n')
                with self.assertRaisesRegex(ValueError,'Stale report'):
                    report.main(['--output',str(output),'--check'])
                self.assertEqual(output.read_text(),'{}\n')


if __name__=='__main__':unittest.main()
