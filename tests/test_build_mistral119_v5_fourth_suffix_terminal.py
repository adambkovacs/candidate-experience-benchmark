from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_mistral119_v5_fourth_suffix_terminal as terminal


class TerminalProposalTests(unittest.TestCase):
    def test_live_terminal_is_read_only_and_preserves_all_failures(self):
        result = terminal.build()
        self.assertFalse(result['approved'])
        self.assertEqual(result['valid_ids'], ['DEV-059'])
        self.assertEqual(result['failed_id'], 'DEV-060')
        self.assertEqual(result['known_actual_usd'], '0.00023835')
        self.assertEqual(result['unknown_upper_bound_usd'], '0.04177920')
        self.assertEqual(result['proposed_unused_allocation_release_usd'], '0.04798245')
        self.assertEqual(result['composite'], {
            'denominator': 60, 'valid': 55, 'failed': 5, 'never_sent': 0,
            'failed_ids': ['DEV-048', 'DEV-050', 'DEV-053', 'DEV-058', 'DEV-060'],
            'score': None})
        self.assertFalse(result['child_sealed'])
        self.assertFalse(result['retry_allowed'])

    def test_changed_child_attempt_is_rejected(self):
        original = terminal.prior.rows

        def changed(path):
            rows = original(path)
            if Path(path).name.endswith(terminal.stage.PID + '.jsonl'):
                rows[-1] = {**rows[-1], 'record_id': 'DEV-059'}
            return rows

        with patch.object(terminal.prior, 'rows', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'child ledger'):
                terminal.build()


if __name__ == '__main__':
    unittest.main()
