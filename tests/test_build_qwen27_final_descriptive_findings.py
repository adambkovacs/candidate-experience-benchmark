"""Nine-slot Qwen analysis keeps interrupted positions in their denominators."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_qwen27_final_descriptive_findings as report


class FinalDescriptiveFindingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.actual = report.build(ROOT)

    def test_nine_scores_ranges_and_shared_valid_denominators(self):
        value = self.actual
        self.assertFalse(value['cleanMatchedThreeEligible'])
        self.assertEqual(len(value['sourceBindings']), 266)
        expected = {
            'medium': {'P0': [56, 59, 57], 'P1': [54, 58, 56],
                       'P2': [57, 56, 57], 'changes': [3, 4, 3],
                       'fresh3PromptFlips': 2},
            'xhigh': {'P0': [58, 57, 58], 'P1': [57, 57, 58],
                      'P2': [57, 58, 57], 'changes': [4, 3, 4],
                      'fresh3PromptFlips': 1},
        }
        for item in value['series']:
            mode = item['configuration'].rsplit('-', 1)[-1]
            self.assertEqual(item['scoredConditions'], 9)
            self.assertEqual(item['originalUninterruptedConditions'], 7)
            self.assertEqual(item['interruptedCompositeSlots'], ['fresh3/P0', 'fresh3/P1'])
            self.assertFalse(item['cleanMatchedThreeEligible'])
            for index, condition in enumerate(report.CONDITIONS):
                self.assertEqual(item['threePassSummary'][condition]['allFour']['values'],
                                 expected[mode][condition])
                across = item['changesAcrossThreePasses'][condition]
                self.assertEqual(across['denominator'], 59 if condition == 'P0' else 60)
                self.assertEqual(across['fourFieldVector']['changed'],
                                 expected[mode]['changes'][index])
            prompt = next(x for x in item['withinPassPromptFlips']
                          if x['pass'] == 'fresh3' and x['to'] == 'P1')
            self.assertEqual(prompt['denominator'], 59)
            self.assertEqual(prompt['fourFieldVector']['changed'],
                             expected[mode]['fresh3PromptFlips'])
            self.assertEqual(item['passes']['fresh3']['P0']['score']['serviceErrors'], 1)
            self.assertEqual(item['passes']['fresh3']['P1']['score']['serviceErrors'], 0)
        rendered = json.dumps(value)
        for private in ('body_base64', 'raw_response', 'response_headers',
                        'master_ledger', 'api_key'):
            self.assertNotIn(private, rendered)

    def test_relocated_bound_sources_and_tamper(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for item in self.actual['sourceBindings']:
                target = root / item['path']
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / item['path'], target)
            self.assertEqual(report.build(root), self.actual)
            file = (root / report.second.BASE / 'interruption-continuation-v1'
                    / 'medium/public-evidence-v1/prefix.positions.jsonl')
            rows = report.second.first.rows(file)
            rows[0]['prediction']['sentiment'] = 'neutral'
            file.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                report.build(root)

    def test_across_three_excludes_unscorable_and_keeps_case_ids(self):
        ids = ['DEV-001', 'DEV-002', 'DEV-003']
        pred = {'sentiment': 'positive', 'follow_up_needed': 'no',
                'serious_concern_reported': 'no', 'testimonial_potential': 'no'}
        first = [{'id': rid, 'status': 'ok', 'prediction': pred} for rid in ids]
        second = [{'id': rid, 'status': 'ok', 'prediction': pred} for rid in ids]
        third = [{'id': rid, 'status': 'ok', 'prediction': pred} for rid in ids]
        third[1] = {'id': 'DEV-002', 'status': 'service_error', 'prediction': None}
        third[2] = {'id': 'DEV-003', 'status': 'ok',
                    'prediction': {**pred, 'sentiment': 'negative'}}
        result = report.across_three([first, second, third], ids)
        self.assertEqual(result['denominator'], 2)
        self.assertEqual(result['excludedIds'], ['DEV-002'])
        self.assertEqual(result['fourFieldVector']['caseIds'], ['DEV-003'])


if __name__ == '__main__':
    unittest.main()
