import copy
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import render_prompt_comparison as report
import test_prompt_variant_evaluation as fixtures
import evaluate_prompt_variants as evaluator


class ReportTests(unittest.TestCase):
    def result(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = fixtures.PairedTests()
            root, manifest = fixture.fixture(tmp)
            fixture.mutate(root, manifest, 'P1', lambda rows: rows[0].update(status='service_error', prediction=None))
            return evaluator.evaluate(manifest, root)

    def entry(self, result):
        return {'source_file': 'paired.json', 'source_sha256': 'a' * 64, 'result': result}

    def test_real_evaluator_failures_unknowns_and_gate_remain_visible(self):
        result = self.result()
        document = report.render([self.entry(result)])
        self.assertIn('NOT eligible', document)
        self.assertIn('unknown', document)
        self.assertIn('1 valid-to-failed', document)
        self.assertIn('DEV-001', document)
        self.assertIn('Denominator: 60', document)
        self.assertIn('serious_concerns', document)
        self.assertIn('pair_checks', document)
        self.assertIn('provisional', document)
        self.assertIn('Exact frozen additions', document)

    def test_feedback_and_identity_cannot_inject_html_or_script(self):
        result = self.result()
        payload = '</script><img src=x onerror=alert(1)>'
        result['parent_baseline_id'] = payload
        for condition in result['conditions'].values():
            condition['prompt_provenance']['parent_baseline_id'] = payload
        result['comparisons']['P0_to_P1']['cases'][0]['feedback'] = payload
        document = report.render([self.entry(result)])
        self.assertNotIn(payload, document)
        self.assertIn('&lt;img', document)
        self.assertEqual(document.count('<script>'), 1)

    def test_prompt_diff_must_match_evaluator_provenance(self):
        result = self.result()
        result['conditions']['P2']['prompt_provenance']['addition_sha256'] = 'wrong'
        with self.assertRaises(ValueError):
            report.render([self.entry(result)])

    def test_conflicting_prompt_identity_role_or_composition_rejected(self):
        result = self.result()
        for field, value in [('baseline_instruction_sha256', 'wrong'), ('baseline_instruction_bytes', 999), ('instruction_role', 'user'), ('variant', 'P1'), ('parent_baseline_id', 'other'), ('composition_separator', ''), ('composed_instruction_bytes', 0)]:
            with self.subTest(field=field):
                changed = copy.deepcopy(result)
                changed['conditions']['P2']['prompt_provenance'][field] = value
                with self.assertRaises(ValueError):
                    report.render([self.entry(changed)])

    def test_duplicate_or_inconsistent_coverage_rejected(self):
        result = self.result()
        with self.assertRaises(ValueError):
            report.render([self.entry(result), self.entry(result)])
        for mutate in [lambda r: r.update(denominator=59), lambda r: r['comparisons']['P0_to_P1'].update(changed_record_count=0), lambda r: r.pop('eligible_paired_comparison')]:
            changed = copy.deepcopy(result)
            mutate(changed)
            with self.assertRaises(ValueError):
                report.render([self.entry(changed)])


if __name__ == '__main__':
    unittest.main()
