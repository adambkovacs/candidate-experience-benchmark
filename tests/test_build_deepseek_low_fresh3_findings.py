import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_deepseek_low_fresh3_findings as report


class DeepSeekLowFresh3FindingsTests(unittest.TestCase):
    def test_closed_stages_and_shared_valid_denominators(self):
        value = report.build()
        self.assertEqual(set(value['stages']), {'P0', 'P1', 'P2'})
        self.assertEqual(value['stages']['P1']['valid'], 59)
        self.assertEqual(value['stages']['P1']['invalidIds'], ['DEV-013'])
        self.assertEqual(value['stages']['P2']['valid'], 60)
        self.assertEqual(value['earlierClosedFresh2P0']['valid'], 59)
        self.assertEqual(value['earlierClosedFresh2P0']['invalidIds'], ['DEV-013'])
        for comparison in value['comparisons'].values():
            self.assertEqual(comparison['shared_valid'] + len(comparison['excluded_ids']), 60)
            for field in report.KEYS:
                self.assertEqual(comparison['label_flips'][field]['count'],
                                 len(comparison['label_flips'][field]['ids']))
        self.assertEqual(value['comparisons']['fresh2/P1_vs_fresh3/P1']['shared_valid'], 56)
        self.assertEqual(value['comparisons']['fresh2/P0_vs_fresh3/P0']['shared_valid'], 58)

    def test_build_from_source_bindings_only_and_tamper_rejected(self):
        value = report.build()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for item in value['sourceBindings']:
                source = ROOT / item['path']
                target = root / item['path']
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
            self.assertEqual(report.build(root), value)
            projection = root / report.stage_path('P1', 'public-projection.json')
            changed = json.loads(projection.read_text())
            changed['positions'][0]['prediction']['sentiment'] = 'negative'
            projection.write_text(json.dumps(changed, indent=2) + '\n')
            with self.assertRaisesRegex(ValueError, 'projection receipt'):
                report.build(root)

    def test_pairing_uses_only_actual_shared_valid_records(self):
        labels = {record_id: {key: 'no' for key in report.KEYS} for record_id in report.IDS}
        a = [{'id': record_id, 'status': 'ok', 'prediction': labels[record_id]}
             for record_id in report.IDS]
        b = copy.deepcopy(a)
        a[0]['status'] = 'invalid_output'; a[0]['prediction'] = None
        b[1]['status'] = 'invalid_output'; b[1]['prediction'] = None
        b[2]['prediction']['follow_up_needed'] = 'yes'
        result = report.paired(a, b, labels)
        self.assertEqual(result['shared_valid'], 58)
        self.assertEqual(result['excluded_ids'], ['DEV-001', 'DEV-002'])
        self.assertEqual(result['label_flips']['follow_up_needed']['ids'], ['DEV-003'])
        self.assertEqual(result['all_four_correct_to_wrong'], ['DEV-003'])


if __name__ == '__main__':
    unittest.main()
