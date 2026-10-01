"""Closed-evidence checks for the separate Qwen27 interrupted composites."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_qwen27_second_continuation_findings as report


class SecondContinuationFindingsTests(unittest.TestCase):
    def snapshot(self):
        expected = report.build(ROOT)
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        for source in expected['sourceBindings']:
            target = root / source['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / source['path'], target)
        return tmp, root, expected

    def test_clean_bound_snapshot_has_exact_closed_composites(self):
        tmp, root, expected = self.snapshot()
        with tmp:
            actual = report.build(root)
            self.assertEqual(actual, expected)
            self.assertFalse(actual['cleanMatchedThreeEligible'])
            self.assertEqual(len(actual['sourceBindings']), 45)
            self.assertEqual({k: (v['conditions']['P0']['score']['valid'],
                                  v['conditions']['P0']['score']['allFour'],
                                  v['conditions']['P1']['score']['valid'],
                                  v['conditions']['P1']['score']['allFour'])
                              for k, v in actual['series'].items()},
                             {'medium': (59, 57, 60, 56),
                              'xhigh': (59, 58, 60, 58)})
            for item in actual['sourceBindings']:
                self.assertEqual(report.first.sha(root / item['path']), item['sha256'])
            rendered = json.dumps(actual)
            for private in ('body_base64', 'raw_response', 'response_headers',
                            'master_ledger', 'account_id', 'api_key'):
                self.assertNotIn(private, rendered)

    def test_missing_closed_stage_never_gets_score(self):
        tmp, root, _ = self.snapshot()
        with tmp:
            path = root / report.SECOND / 'medium/fresh3/P1/development/development.responses.jsonl'
            path.unlink()
            with self.assertRaisesRegex(ValueError, 'Closed source missing'):
                report.build(root)

    def test_tampered_saved_prediction_and_private_body_are_rejected(self):
        tmp, root, _ = self.snapshot()
        with tmp:
            path = root / report.SECOND / 'xhigh/fresh3/P1/suffix/suffix.attempts.jsonl'
            rows = report.first.rows(path)
            rows[0]['prediction']['sentiment'] = 'neutral'
            path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            with self.assertRaisesRegex(ValueError, 'parsed result differs'):
                report.build(root)

    def test_ledger_reconciliation_and_review_cannot_be_rewritten(self):
        tmp, root, _ = self.snapshot()
        with tmp:
            path = root / report.SECOND / 'medium/terminal-reconciliation-after-completion.json'
            record = json.loads(path.read_text())
            record['unknown_upper_bound_usd'] = '0.1'
            path.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, 'budget closure differs'):
                report.build(root)
        tmp, root, _ = self.snapshot()
        with tmp:
            path = root / report.SECOND / 'medium/fresh3/P1/development/development.root-review.json'
            record = json.loads(path.read_text())
            record['approved'] = False
            path.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, 'review, or claim differs'):
                report.build(root)

    def test_unmatched_settlement_cannot_be_hidden_in_child_total(self):
        tmp, root, _ = self.snapshot()
        with tmp:
            path = root / report.SECOND / 'xhigh/budget-qwen27-xhigh-v2-interruption-v2.jsonl'
            events = report.first.rows(path)
            events[-1:-1] = [
                {'event': 'reserve', 'attempt_id': 'extra', 'record_id': 'DEV-060',
                 'usd': '0.047001600'},
                {'event': 'settle', 'attempt_id': 'extra', 'usd': '0'},
            ]
            path.write_text(''.join(json.dumps(event) + '\n' for event in events))
            reconciliation = root / report.SECOND / 'xhigh/terminal-reconciliation-after-completion.json'
            record = json.loads(reconciliation.read_text())
            record['child_sha256'] = report.first.sha(path)
            reconciliation.write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, 'exactly the admitted stages'):
                report.build(root)


if __name__ == '__main__':
    unittest.main()
