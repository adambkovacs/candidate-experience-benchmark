import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import gemini_billing_continuation as subject


class BillingDefaultAmendmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(subject.MANIFEST.read_text())

    def test_absent_and_explicit_false_are_documented_off(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder); p = home / '.gemini/antigravity-cli/settings.json'
            p.parent.mkdir(parents=True)
            p.write_text('{}')
            state = subject.billing_state(home)
            self.assertEqual(state['observed_setting'], 'absent_documented_default_false')
            self.assertIs(state['useG1Credits'], False)
            p.write_text('{"useG1Credits":false}')
            self.assertEqual(subject.billing_state(home)['observed_setting'], 'explicit_false')

    def test_true_null_and_nonboolean_stop(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder); p = home / '.gemini/antigravity-cli/settings.json'
            p.parent.mkdir(parents=True)
            for value in (True, None, 0, 'false'):
                p.write_text(json.dumps({'useG1Credits': value}))
                with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, 'not effectively false'):
                    subject.billing_state(home)

    def test_process_audit_captures_before_and_after_without_prompt(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder); p = home / '.gemini/antigravity-cli/settings.json'
            p.parent.mkdir(parents=True); p.write_text('{"useG1Credits":false}')
            audit = home / 'audit.jsonl'
            def simulated(command, *args, **kwargs):
                p.write_text('{}')
                return SimpleNamespace(returncode=0)
            with audit.open('x') as stream:
                proxy = subject.ProcessProxy('/pinned/agy', home, stream, run=simulated)
                proxy.run(['/pinned/agy', 'models'])
            events = [json.loads(line) for line in audit.read_text().splitlines()]
            self.assertEqual([e['event'] for e in events], ['cli_started', 'cli_finished'])
            self.assertEqual(events[0]['before']['observed_setting'], 'explicit_false')
            self.assertEqual(events[1]['after']['observed_setting'], 'absent_documented_default_false')
            self.assertNotIn('command', events[0])

    def test_process_stops_if_cli_enables_credit_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder); p = home / '.gemini/antigravity-cli/settings.json'
            p.parent.mkdir(parents=True); p.write_text('{}')
            def simulated(command, *args, **kwargs):
                p.write_text('{"useG1Credits":true}')
                return SimpleNamespace(returncode=0)
            with (home / 'audit.jsonl').open('x') as stream:
                proxy = subject.ProcessProxy('/pinned/agy', home, stream, run=simulated)
                with self.assertRaisesRegex(RuntimeError, 'not effectively false'):
                    proxy.run(['/pinned/agy', 'models'])
            saved = [json.loads(x) for x in (home / 'audit.jsonl').read_text().splitlines()]
            self.assertEqual(saved[-1]['after_error_type'], 'RuntimeError')

    def test_original_stop_proves_no_request_and_routes_are_separate(self):
        self.assertEqual(len(subject.verify_zero_request(self.manifest)), 64)
        item, journal = subject.route(self.manifest, subject.FIRST, 'P1')
        self.assertEqual(journal, subject.CONTINUATION_JOURNAL)
        self.assertIn('billing-default-continuation-v1', item['conditions']['P1']['smoke_output'])
        _, journal = subject.route(self.manifest, subject.FIRST, 'P2')
        self.assertEqual(journal, subject.GLOBAL_JOURNAL)
        _, journal = subject.route(self.manifest, self.manifest['configurations'][1]['configuration_id'], 'P2')
        self.assertEqual(journal, subject.GLOBAL_JOURNAL)

    def test_zero_request_and_other_condition_tamper_rejected(self):
        altered = copy.deepcopy(self.manifest)
        altered['continuation']['empty_events']['sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'contains a request or output'):
            subject.verify_zero_request(altered)
        altered = copy.deepcopy(self.manifest)
        altered['configurations'][0]['conditions']['P2']['smoke_output'] += '.new'
        with self.assertRaisesRegex(ValueError, 'retain original outputs'):
            subject.route(altered, subject.FIRST, 'P2')

    def test_offline_preflight_and_review_gate(self):
        result = subject.preflight()
        self.assertEqual(result['other_conditions_global_schedule'], 13)
        self.assertFalse(result['inference_performed'])
        with tempfile.TemporaryDirectory() as folder:
            receipt = Path(folder) / 'review.json'; receipt.write_text('{}')
            with patch.object(subject, 'PREFLIGHT', receipt):
                with self.assertRaises(ValueError):
                    subject.review(subject.bind(subject.MANIFEST)['sha256'], '0' * 64,
                        receipt, subject.sha(receipt.read_bytes()))

    def test_execution_injects_separate_journal_without_calling_cli(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder); settings = home / '.gemini/antigravity-cli/settings.json'
            settings.parent.mkdir(parents=True); settings.write_text('{}')
            item = copy.deepcopy(self.manifest['configurations'][0])
            item['conditions']['P1']['smoke_output'] = str(home / 'smoke.jsonl')
            separate = home / 'continuation-journal.jsonl'
            original = (subject.frozen.MANIFEST, subject.frozen.PREFLIGHT,
                subject.frozen.JOURNAL, subject.frozen.native, subject.frozen.subprocess)
            def inspect_injection(underlying, selected, condition, stage, *_):
                self.assertEqual(underlying['contract'], 'gemini-exact-draft-v2')
                self.assertEqual((selected['configuration_id'], condition, stage), (subject.FIRST, 'P1', 'smoke'))
                self.assertEqual(subject.frozen.JOURNAL, separate)
                self.assertEqual(subject.frozen.MANIFEST, subject.MANIFEST)
                self.assertEqual(subject.frozen.native.require_credits_off(home)['observed_setting'], 'absent_documented_default_false')
                self.assertIsInstance(subject.frozen.subprocess, subject.ProcessProxy)
            with patch.dict('os.environ', {'HOME': str(home)}), patch.object(subject, 'route', return_value=(item, separate)), patch.object(subject.frozen, 'run_stage', side_effect=inspect_injection):
                subject.execute(self.manifest, subject.FIRST, 'P1', 'smoke')
            self.assertEqual((subject.frozen.MANIFEST, subject.frozen.PREFLIGHT,
                subject.frozen.JOURNAL, subject.frozen.native, subject.frozen.subprocess), original)


if __name__ == '__main__': unittest.main()
