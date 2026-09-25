"""Checks for descriptive findings and its frozen-source contract."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/build_findings.py'
ROOT = SCRIPT.parents[1]
spec = importlib.util.spec_from_file_location('build_findings', SCRIPT)
f = importlib.util.module_from_spec(spec)
spec.loader.exec_module(f)


class FindingsTests(unittest.TestCase):
    def test_invalid_status_retained_even_with_prediction(self):
        case = {'status':'invalid_output','prediction':{'sentiment':'positive'},'reference':{'sentiment':'positive'}}
        self.assertEqual('invalid',f.state(case))

    def test_duplicate_cases_rejected(self):
        row={'configuration':'run','id':'DEV-001'}
        with self.assertRaisesRegex(ValueError,'duplicate configuration/case'):
            f.case_index([row,row])

    def test_missing_case_rejected(self):
        run={'id':'run','valid':0,'metrics':{'all_four':0}}
        with self.assertRaisesRegex(ValueError,'missing case'):
            f.score_run(run,{},['DEV-001'])

    def test_summary_disagreement_rejected(self):
        run={'id':'run','valid':1,'metrics':{'all_four':1}}
        cases={('run','DEV-001'):{'status':'invalid_output','prediction':None}}
        with self.assertRaisesRegex(ValueError,'saved summary disagrees'):
            f.score_run(run,cases,['DEV-001'])

    def test_frozen_export_reconciles(self):
        output=f.build()
        source=(ROOT/'public-site/data.json').read_bytes()
        self.assertEqual(hashlib.sha256(source).hexdigest(),output['meta']['sourceSha256'])
        self.assertEqual(290,output['meta']['runCount'])
        self.assertEqual(17400,output['meta']['caseCount'])
        prompt=output['charts']['promptDeltas']['cohorts']
        self.assertEqual([('strict',38),('hosted_observational',9),('local_historical_baseline',5)],
                         [(r['id'],r['configurations']) for r in prompt])
        for group in prompt:
            for comparison in group['comparisons'].values():
                self.assertEqual(group['configurations'],sum(comparison[k] for k in ('improved','tied','worsened')))
                self.assertEqual(group['configurations'],len(comparison['rows']))
                for row in comparison['rows']:
                    self.assertEqual(row['toCorrect']-row['fromCorrect'],row['delta'])
        jev=output['charts']['jev']
        self.assertEqual(60,jev['valid'])
        self.assertEqual(54,jev['correct'])
        self.assertEqual(6,len(jev['cases']))
        for row in jev['comparators']:
            self.assertEqual(60,sum(row['overlap'].values()))
            self.assertEqual(54,row['overlap']['bothCorrect']+row['overlap']['comparatorOnlyWrong'])
            self.assertEqual(row['correct'],row['overlap']['bothCorrect']+row['overlap']['jevOnlyWrong'])
        cost_rows=output['charts']['costAgreement']['rows']
        self.assertEqual(24,len(cost_rows))
        self.assertEqual(9,sum(row['cohort']=='hosted_observational_gemini' for row in cost_rows))
        self.assertTrue(all(row['costAvailability']=='observed' for row in cost_rows))
        for row in output['charts']['costAgreement']['rows']:
            self.assertEqual('P0',row['condition'])
            self.assertGreaterEqual(row['actualUsd'],0)
            self.assertEqual(60,row['denominator'])
        for row in output['charts']['hardCases']['categories']:
            self.assertEqual(row['denominator'],sum(row[k] for k in ('correct','wrongValid','invalid')))

    def test_prompt_deduplication_rejected(self):
        data=json.loads((ROOT/'public-site/data.json').read_text())
        runs={r['id']:r for r in data['runs']}
        cases=f.case_index(data['cases'])
        ids=[f'DEV-{i:03d}' for i in range(1,61)]
        with self.assertRaisesRegex(ValueError,'duplicate prompt comparison'):
            f.prompt_deltas([data['promptComparisons'][0]]*2,runs,cases,ids)


if __name__=='__main__':
    unittest.main()
