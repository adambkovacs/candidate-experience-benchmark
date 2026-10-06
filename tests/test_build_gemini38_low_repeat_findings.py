"""Offline checks for the recovered Gemini 3.8 low repeat series."""
import copy
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import build_gemini_repeat_findings as report

CONFIG='gemini38-low-p0-openrouter-v2'


class RecoveredGeminiLowFindingsTest(unittest.TestCase):
    def test_closed_series_preserves_recovered_p0_and_partition_money(self):
        series=report.build_series(CONFIG)
        self.assertEqual(series['completedConditions'],9)
        self.assertEqual(series['plannedConditions'],9)
        self.assertEqual(series['missingPasses'],[])
        self.assertEqual(series['partialPasses'],[])
        self.assertEqual(series['denominator'],60)
        self.assertEqual(series['provider'],'google-ai-studio')
        self.assertEqual(series['passes']['original']['P0']['score']['allFour'],57)
        self.assertIsNone(series['passes']['original']['P0']['usage']['requestSecondsTotal'])
        self.assertIsNone(series['passes']['original']['P0']['usage']['inferenceSeconds'])
        self.assertTrue(all(series['passes'][name][condition]['score']['valid']==60
                            for name in report.PASSES for condition in report.CONDITIONS))
        budget=series['budgetReconciliation']
        self.assertEqual(budget['knownActualUsd'],'0.15296100')
        self.assertEqual(budget['unknownUpperBoundUsd'],'0')
        self.assertEqual(budget['unusedAllocationReleasedUsd'],'0.14703900')
        self.assertEqual(Decimal(budget['capUsd']),Decimal(budget['knownActualUsd'])+
                         Decimal(budget['unusedAllocationReleasedUsd']))
        sources={item['path'] for item in series['sourceBindings']}
        self.assertIn('results/repeatability-v1/gemini38-low-p0-openrouter-v2/budget-reconciliation-v1.json',sources)
        self.assertIn(budget['childLedger']['path'],sources)

    def test_opt_in_keeps_existing_eight_series_before_authority_appendix(self):
        published=json.loads((ROOT/'public-site/gemini-repeats.json').read_text())
        default=report.build(ROOT)
        opt_in=report.build(ROOT,include_recovered_low=True)
        self.assertEqual(len(default['series']),7)
        self.assertEqual(len(published['series']),9)
        self.assertEqual(default['series'],published['series'][:7])
        self.assertEqual(opt_in['series'][:7],default['series'])
        self.assertEqual(opt_in['series'],published['series'][:8])
        self.assertEqual(opt_in['series'][7]['configuration'],CONFIG)
        self.assertEqual(published['series'][8]['configuration'],
                         'gemini31-pro-preview-high-p0-openrouter-v3')

    def test_recovered_p0_rejects_saved_prediction_drift(self):
        plan=report.recovered_low.expected_plan(CONFIG,'repeat2')
        history=plan['conditions']['P0']['historical']
        records=copy.deepcopy(report._rows(ROOT,history['development_records']['path']))
        records[0]['prediction']['sentiment']='negative' if records[0]['prediction']['sentiment']!='negative' else 'positive'
        original=report._rows
        def rows(root,relative):
            if relative==history['development_records']['path']:return records
            return original(root,relative)
        ids=[f'DEV-{i:03d}' for i in range(1,61)]
        labels={x['id']:x['proposed_labels'] for x in original(ROOT,report.LABELS)}
        bind,_=report._binder(ROOT)
        with patch.object(report,'_rows',side_effect=rows), self.assertRaisesRegex(ValueError,'record differs'):
            report._historical(ROOT,plan,'P0',ids,labels,bind)

    def test_budget_rejects_settlement_drift(self):
        _,_,plans,bind,_=report._source_context(ROOT,CONFIG)
        child=report.BASE/CONFIG/'budget-partition-v1-g38-low-recovered-repeat-v1.jsonl'
        events=copy.deepcopy(report._rows(ROOT,child))
        events[2]['usd']='0.00'
        original=report._rows
        with patch.object(report,'_rows',side_effect=lambda root,relative: events if relative==child else original(root,relative)):
            with self.assertRaisesRegex(ValueError,'ledger differs'):
                report._recovered_budget(ROOT,CONFIG,plans,bind)


if __name__=='__main__':unittest.main()
