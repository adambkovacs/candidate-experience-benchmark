"""Portable native L0 reporting tests; no model weights or inference."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import build_anyjev_l0_repeat_findings as report

class L0ReportTests(unittest.TestCase):
    def test_historical_score_recomputed_and_timing_not_inference(self):
        data=report.build()
        original=data['passes']['original']['P0']
        self.assertEqual(original['score']['valid'],60)
        self.assertEqual(original['score']['allFour'],4)
        self.assertEqual(data['conditionOrder'],['P0'])
        self.assertIsNone(original['usage']['inferenceSeconds'])
        self.assertIsNone(original['usage']['actualCostUsd'])
        self.assertIn('lengths, not prompt hashes',data['limitations'][0])

    def test_confusion_counts_keep_reference_denominators(self):
        data=report.build()
        for field,matrix in data['confusionCounts']['original'].items():
            self.assertEqual(sum(sum(row.values()) for row in matrix.values()),60)
            self.assertEqual({label:sum(row.values()) for label,row in matrix.items()},
                             data['referenceClassCounts'][field])
            self.assertEqual(sum(row.get(label,0) for label,row in matrix.items()),
                             data['passes']['original']['P0']['score']['fields'][field])

    def test_no_live_phase_is_parsed_or_scored(self):
        realpath=report.path;realrows=report.rows
        def absent(root,name):
            if str(name).startswith(str(report.BASE/'repeat2')) and str(name).endswith('development.completion.json'):
                return Path('/private/tmp/l0-test-no-completion')
            if str(name).startswith(str(report.BASE/'repeat3')):
                return Path('/private/tmp/l0-test-no-phase')
            return realpath(root,name)
        def rows(root,name):
            if str(name).startswith(str(report.BASE/'repeat2')) or str(name).startswith(str(report.BASE/'repeat3')):
                raise AssertionError('Read active evidence')
            return realrows(root,name)
        with patch.object(report,'path',side_effect=absent),patch.object(report,'rows',side_effect=rows):
            data=report.build()
        self.assertEqual(data['completedConditions'],1)
        self.assertEqual(data['missingPasses'][0]['status'],'claimed_in_progress_or_interrupted')
        self.assertEqual(data['missingPasses'][1]['status'],'not_started')
        self.assertEqual(data['changesAcrossThreePasses'],{})
        self.assertIsNone(data['threePassSummary']['P0']['allFour']['range'])

    def test_closed_smoke_binds_all_shift_and_probe_signatures(self):
        plan,ids,labels,specs,_,_,bind,_=report.source_context(ROOT)
        indexed,records,raw,evidence=report.stage(ROOT,plan,'repeat2/P0','smoke',specs,bind)
        self.assertEqual(len(indexed),3)
        self.assertEqual([len(x) for x in raw[0]['native_calls']],[14,42])
        original=report.rows
        name=report.BASE/'repeat2/P0/smoke.raw.jsonl'
        changed=copy.deepcopy(raw);changed[0]['native_calls'][1][0]['prompt_sha256']='0'*64
        with patch.object(report,'rows',side_effect=lambda root,n:changed if n==name else original(root,n)):
            with self.assertRaisesRegex(ValueError,'output binding differs'):
                report.stage(ROOT,plan,'repeat2/P0','smoke',specs,bind)

    def test_invalid_distribution_cannot_be_reported_as_saved_valid(self):
        plan,ids,labels,specs,_,_,bind,_=report.source_context(ROOT)
        name=report.BASE/'repeat2/P0/smoke.raw.jsonl';raw=copy.deepcopy(report.rows(ROOT,name))
        dist=raw[0]['raw_response']['questions']['sentiment']['distribution'];dist[next(iter(dist))]=2.0
        original=report.rows
        with patch.object(report,'rows',side_effect=lambda root,n:raw if n==name else original(root,n)):
            with self.assertRaisesRegex(ValueError,'output binding differs'):
                report.stage(ROOT,plan,'repeat2/P0','smoke',specs,bind)

    def test_historical_control_drift_is_rejected(self):
        plan,ids,labels,specs,_,base,bind,_=report.source_context(ROOT)
        name=Path(plan['historical']['directory'])/'development.jsonl'
        saved=copy.deepcopy(report.rows(ROOT,name));saved[0]['prior_applied']=False
        original=report.rows
        with patch.object(report,'rows',side_effect=lambda root,n:saved if n==name else original(root,n)):
            with self.assertRaisesRegex(ValueError,'Historical AnyJev L0 row differs'):
                report.historical(ROOT,plan,ids,labels,specs,base,bind)

if __name__=='__main__':unittest.main()
