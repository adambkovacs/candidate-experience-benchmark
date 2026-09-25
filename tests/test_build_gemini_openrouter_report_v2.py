from pathlib import Path
import json
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_gemini_openrouter_report_v2 as report


class GeminiHostedReportV2(unittest.TestCase):
    def test_missing_reasoning_usage_is_unknown(self):
        attempts = [{'usage': {'completion_tokens_details': {'reasoning_tokens': 4}}},
                    {'usage': {'completion_tokens_details': {}}}]
        self.assertIsNone(report.token_total(
            attempts, lambda usage: (usage.get('completion_tokens_details') or {}).get('reasoning_tokens')))

    def test_recovered_parent_requires_exact_admission_proof(self):
        folder = report.ROOT / 'results/gemini-openrouter-prep-v3/recovered-38-low-p1-ready-v1'
        with mock.patch.object(report.adapter, 'validate_admission', side_effect=ValueError('admission rejected')):
            with self.assertRaisesRegex(ValueError, 'admission rejected'):
                report.build(folder)

    def test_closed_recovered_parent_and_p1_compare_observed_records(self):
        folder = report.ROOT / 'results/gemini-openrouter-prep-v3/recovered-38-low-p1-ready-v1'
        result = report.build(folder)
        self.assertEqual(result['kind'], 'gemini-openrouter-hosted-batch-report-v2')
        self.assertEqual([run['condition'] for run in result['public_runs']], ['P0', 'P1'])
        self.assertEqual(len(result['public_cases']), 120)
        self.assertEqual(result['public_pairs'][0]['id'], 'gemini38-low-p0-openrouter-v2')
        self.assertIn('P0_to_P1', result['public_pairs'][0]['comparisons'])
        self.assertFalse(result['causal_claim_supported'])

    def test_recovered_p0_p1_p2_group_preserves_published_baseline(self):
        result = report.build(report.ROOT / 'results/gemini-openrouter-prep-v3')
        original = json.loads((report.ROOT / 'results/gemini-openrouter-prep-v2/p0-routing-probe/gemini38-low-p0/report-v1.json').read_text())
        baseline = next(run for run in result['public_runs'] if run['id'] == 'gemini38-low-p0-openrouter-v2')
        self.assertEqual(baseline, original['public_runs'][0])
        pair = next(item for item in result['public_pairs'] if item['id'] == baseline['id'])
        self.assertEqual(set(pair['comparisons']), {'P0_to_P1', 'P0_to_P2', 'P1_to_P2'})


if __name__ == '__main__':
    unittest.main()
