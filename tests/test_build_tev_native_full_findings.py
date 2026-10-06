import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_tev_native_full_findings as report


class TevFullFindingsTests(unittest.TestCase):
    def test_repeat_and_prompt_comparison_count_changed_records(self):
        def stage(name, rows):
            return {'stage': name, 'records': [
                {'id': ident, 'prediction': {'sentiment': sentiment,
                 'follow_up_needed': 'no', 'serious_concern_reported': 'no',
                 'testimonial_potential': 'no'}} for ident, sentiment in rows]}
        left = stage('fresh1/P0', [('DEV-001', 'positive'), ('DEV-002', 'negative')])
        right = stage('fresh2/P0', [('DEV-001', 'negative'), ('DEV-002', 'negative')])
        result = report.compare(left, right)
        self.assertEqual(result['records_with_any_changed_answer'], 1)
        self.assertEqual(result['changed_record_ids'], ['DEV-001'])
        self.assertEqual(result['changed_fields']['sentiment'], 1)

    def test_public_projection_requires_receipt_in_source_only_checkout(self):
        if not (ROOT / report.RECEIPT).exists():
            self.skipTest('Tev public projection has not yet been prepared')
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            receipt = json.loads((ROOT / report.RECEIPT).read_text())
            paths = set(receipt['source_sha256']) | {str(report.RECEIPT), str(report.PROJECTION)}
            for name in paths:
                if name.endswith(('raw.jsonl', 'attempts.jsonl', 'parsed.jsonl')):
                    continue
                destination = target / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / name, destination)
            result = report.portable_check(target)
            self.assertEqual(len(result['stages']), 9)
            projection_path = target / report.PROJECTION
            projection = json.loads(projection_path.read_text())
            projection['stages'][0]['records'][0]['prediction']['sentiment'] = 'negative'
            projection_path.write_text(json.dumps(projection) + '\n')
            with self.assertRaises(ValueError):
                report.portable_check(target)

    def test_published_findings_match_closed_sources(self):
        if not (ROOT / report.OUTPUT).exists():
            self.skipTest('Tev findings have not yet been prepared')
        value = report.build()
        self.assertEqual([stage['all_four_correct'] for stage in value['stages']],
                         [45, 44, 44] * 3)
        self.assertEqual(value['development_records'], 540)
        self.assertEqual(report.check(), report.sha(ROOT / report.OUTPUT))


if __name__ == '__main__':
    unittest.main()
