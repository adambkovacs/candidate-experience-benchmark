import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_native_prompt_summary import ROOT, SOURCE, export, summarize


class NativePromptSummaryTests(unittest.TestCase):
    def test_exact_descriptive_counts_and_missing_semif_record(self):
        data = export()
        self.assertEqual(data['denominator'], 60)
        self.assertIs(data['strictPairedComparisonEligible'], False)
        self.assertEqual(len(data['conditions']), 12)
        index = {(r['id'], r['condition']): r for r in data['conditions']}
        self.assertEqual(index[('anyjev-qwen06-generated-control', 'P2')]['valid'], 30)
        self.assertEqual(index[('openjev-generated-off', 'P2')]['correct']['all_four'], 51)
        self.assertEqual(index[('semif-generated-bf16', 'P2')]['missingIds'], ['DEV-033'])
        for row in data['conditions']:
            self.assertEqual(set(row['correct']), {'sentiment', 'follow_up_needed', 'serious_concern_reported', 'testimonial_potential', 'all_four'})
            self.assertLessEqual(row['correct']['all_four'], row['valid'])
            self.assertLessEqual(row['valid'], row['saved'])
            self.assertEqual(row['saved'] + len(row['missingIds']), 60)

    def test_source_hash_and_counts_are_checked(self):
        source = json.loads((ROOT / SOURCE).read_text())
        changed = copy.deepcopy(source)
        changed['rows'][0]['sources'][0]['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Source hash mismatch'):
            summarize(changed, ROOT)
        changed = copy.deepcopy(source)
        changed['rows'][0]['all_four_reference_agreement'] += 1
        with self.assertRaisesRegex(ValueError, 'disagrees'):
            summarize(changed, ROOT)

    def test_public_payload_omits_raw_and_local_details(self):
        value = export()
        serialized = json.dumps(value)
        for forbidden in ('/Users/', '/private/', '"raw_response":', '"messages":', 'api_key', '"feedback":'):
            self.assertNotIn(forbidden, serialized)


if __name__ == '__main__':
    unittest.main()
