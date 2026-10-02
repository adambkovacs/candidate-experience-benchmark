import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_mistral119_second_suffix_terminal as terminal


class TerminalTests(unittest.TestCase):
    def test_sealed_suffix_and_fixed_denominator(self):
        report = terminal.build()
        self.assertEqual(report['valid_ids'], ['DEV-051', 'DEV-052'])
        self.assertEqual(report['failed_id'], 'DEV-053')
        self.assertEqual(report['earlier_failed_ids_preserved'], ['DEV-048', 'DEV-050'])
        self.assertEqual(report['unsent_ids'], [f'DEV-{i:03d}' for i in range(54, 61)])
        self.assertEqual((report['composite_valid_count'],
                          report['composite_failed_count'],
                          report['composite_never_sent_count']), (50, 3, 7))
        self.assertIsNone(report['composite_score'])
        self.assertEqual(report['unknown_cost_upper_bound_usd'], '0.04177920')
        text = json.dumps(report)
        self.assertNotIn('body_base64', text)
        self.assertNotIn('response_format', text)
        self.assertNotIn('Bearer ', text)

    def test_unsealed_child_cannot_be_reported(self):
        original_sha = terminal.smoke.sha

        def changed_child(path):
            if (str(path).startswith(str(terminal.stage.BASE)) and
                    str(path).endswith('.jsonl')):
                return '0' * 64
            return original_sha(path)

        with patch.object(terminal.smoke, 'sha', side_effect=changed_child):
            with self.assertRaisesRegex(ValueError, 'Child has not been sealed'):
                terminal.build()


if __name__ == '__main__':
    unittest.main()
