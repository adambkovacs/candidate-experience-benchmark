"""Offline guards for the six distinct Codex fresh matched-three series."""
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import codex_fresh_roster as m


class FreshRosterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name) / 'series'
        self.private = Path(self.temp.name) / 'private'
        self.private.mkdir(mode=0o700)
        self.base_patch = patch.object(m, 'base_dir', return_value=self.base)
        self.base_patch.start()
        self.addCleanup(self.base_patch.stop)
        self.config = 'codex-gpt-6-astra-medium'
        self.plans = {name: m.plan_data(self.config, name) for name in m.ORDERS}
        for name, plan in self.plans.items():
            m.write_new(self.base / name / 'manifest.json', plan)
        self.hashes = {name: m.sha(self.base / name / 'manifest.json') for name in m.ORDERS}

    def review(self, fresh, condition, phase, *, age=0, weekly=30, quota_changes=None, quota_remove=()):
        manifest = self.plans[fresh]
        receipt = self.private / f'{fresh}-{condition}-{phase}.json'
        value = {'schema': m.REVIEW_SCHEMA, 'approved': True,
                 'configuration_id': self.config, 'pass': fresh, 'condition': condition,
                 'phase': phase, 'manifest_sha256': self.hashes[fresh],
                 'controller_sha256': m.sha(m.CONTROLLER), 'model': manifest['model'],
                 'effort': manifest['effort'], 'runtime': m.RUNTIME, 'cli_path': m.CODEX,
                 'quota': {'source': 'Codex get_usage_limits',
                           'checked_at_utc': (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat(),
                           'ordinary_usage_allowed': True, 'spend_control_reached': False,
                           'credits_available': False, 'unlimited_credits': False,
                           'paid_overage_disabled': True,
                           'weekly_remaining_percent': weekly,
                           'five_hour_remaining_percent': 35}}
        value['quota'].update(quota_changes or {})
        for key in quota_remove:
            value['quota'].pop(key, None)
        if phase == 'development':
            value['smoke_inspection_sha256'] = m.sha(self.base / fresh / condition / 'smoke-inspection.json')
        m.write_new(receipt, value)
        os.chmod(receipt, stat.S_IRUSR | stat.S_IWUSR)
        return receipt, m.sha(receipt)

    @staticmethod
    def backend(cmd, prompt, env, cwd):
        incoming = json.loads(prompt.splitlines()[-1])['records']
        rows = [{'id': row['id'], 'sentiment': 'neutral', 'follow_up_needed': 'no',
                 'serious_concern_reported': 'no', 'testimonial_potential': 'no'}
                for row in incoming]
        return {'returncode': 0, 'stdout': json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 100, 'output_tokens': 30}}),
                'stderr': '', 'response': json.dumps({'records': rows})}

    def run_fake(self, fresh, condition, phase, backend=None):
        receipt, receipt_hash = self.review(fresh, condition, phase)
        m.run_phase(self.plans[fresh], condition, phase, self.hashes[fresh],
                    receipt, receipt_hash, backend=backend or self.backend,
                    runtime=lambda codex: {})

    def test_six_plans_exact_membership_and_reference_isolation(self):
        for config in m.CONFIGS:
            for fresh, order in m.ORDERS.items():
                plan = m.plan_data(config, fresh)
                self.assertEqual(order, plan['condition_order'])
                self.assertFalse(plan['historical_first_pass_used'])
                for condition in ('P0', 'P1', 'P2'):
                    requests = plan['conditions'][condition]['development']
                    self.assertEqual(6, len(requests))
                    self.assertEqual([f'DEV-{i:03d}' for i in range(1, 61)],
                                     [rid for request in requests for rid in request['record_ids']])
                    prompt = requests[0]['request']['prompt']
                    self.assertNotIn(config + '-fresh-matched3', prompt)
                    self.assertNotIn('proposed_labels', prompt)
                    self.assertNotIn('prior_prediction', prompt)
                    self.assertEqual(3, len(plan['conditions'][condition]['smoke']['record_ids']))

    def test_smoke_then_development_and_no_replay(self):
        self.run_fake('fresh1', 'P0', 'smoke')
        self.assertFalse(m.completed(self.config, 'fresh1', 'P0', 'development'))
        m.inspect(self.plans['fresh1'], 'P0', 'Three raw responses and returned model inspected')
        self.run_fake('fresh1', 'P0', 'development')
        self.assertTrue(m.completed(self.config, 'fresh1', 'P0', 'development'))
        records = (self.base / 'fresh1/P0/development.records.jsonl').read_text().splitlines()
        self.assertEqual(60, len(records))
        first = json.loads((self.base / 'fresh1/P0/development.attempts.jsonl').read_text().splitlines()[0])
        self.assertEqual({'input_tokens': 100, 'output_tokens': 30}, first['usage'])
        self.assertEqual((100, 30), (first['input_tokens'], first['output_tokens']))
        self.assertIsNone(first['cost_usd'])
        self.assertIsNone(first['effective_seed'])
        self.assertIsNone(first['hardware'])
        self.assertLessEqual(datetime.fromisoformat(first['started_utc']), datetime.fromisoformat(first['finished_utc']))
        with self.assertRaises(FileExistsError):
            self.run_fake('fresh1', 'P0', 'development')

    def test_order_and_inspection_gates_before_dispatch(self):
        receipt, key = self.review('fresh1', 'P1', 'smoke')
        with self.assertRaisesRegex(ValueError, 'Prior condition'):
            m.run_phase(self.plans['fresh1'], 'P1', 'smoke', self.hashes['fresh1'], receipt, key,
                        backend=self.backend, runtime=lambda _: {})
        self.run_fake('fresh1', 'P0', 'smoke')
        self.assertFalse((self.base / 'fresh1/P0/development.claim.json').exists())
        with self.assertRaisesRegex(ValueError, 'Prior pass'):
            m.require_order(self.plans['fresh2'], 'P1')

    def test_private_quota_gate(self):
        for age, weekly in ((301, 30), (0, 0)):
            with self.subTest(age=age, weekly=weekly):
                receipt, key = self.review('fresh1', 'P0', 'smoke', age=age, weekly=weekly)
                with self.assertRaisesRegex(ValueError, 'Quota admission'):
                    m.run_phase(self.plans['fresh1'], 'P0', 'smoke', self.hashes['fresh1'], receipt, key,
                                backend=self.backend, runtime=lambda _: {})
                receipt.unlink()
        self.assertFalse((self.base / 'fresh1/P0/smoke.claim.json').exists())
        self.assertFalse((self.base / 'fresh1/P0/smoke.admission.json').exists())

    def test_paid_credit_or_unattested_overage_rejected(self):
        for changes, missing in (({'credits_available': True}, ()),
                                 ({'unlimited_credits': True}, ()),
                                 ({'paid_overage_disabled': False}, ()),
                                 ({}, ('credits_available',)),
                                 ({}, ('unlimited_credits',)),
                                 ({}, ('paid_overage_disabled',))):
            with self.subTest(changes=changes, missing=missing):
                receipt, key = self.review('fresh1', 'P0', 'smoke', quota_changes=changes, quota_remove=missing)
                with self.assertRaisesRegex(ValueError, 'Quota admission'):
                    m.run_phase(self.plans['fresh1'], 'P0', 'smoke', self.hashes['fresh1'], receipt, key,
                                backend=self.backend, runtime=lambda _: {})
                receipt.unlink()
        self.assertFalse((self.base / 'fresh1/P0/smoke.claim.json').exists())

    def test_raw_is_durable_before_parser_and_known_invalid_retained(self):
        from codex_fresh_roster import batch
        def invalid(raw, rows):
            self.assertTrue((self.base / 'fresh1/P0/smoke.raw-0.json').exists())
            raise ValueError('fully returned invalid batch')
        with patch.object(batch, 'parse_batch', side_effect=invalid):
            with self.assertRaisesRegex(RuntimeError, 'stopped on first non-ok'):
                self.run_fake('fresh1', 'P0', 'smoke')
        attempts = [json.loads(x) for x in (self.base / 'fresh1/P0/smoke.attempts.jsonl').read_text().splitlines()]
        rows = [json.loads(x) for x in (self.base / 'fresh1/P0/smoke.records.jsonl').read_text().splitlines()]
        self.assertEqual('invalid_output', attempts[0]['status'])
        self.assertEqual(['invalid_output'] * 3, [x['status'] for x in rows])
        with self.assertRaisesRegex(ValueError, 'Smoke phase not complete'):
            m.inspect(self.plans['fresh1'], 'P0', 'Inspected raw invalid')

    def test_unknown_transport_stops_without_replay(self):
        def fail(*args):
            raise RuntimeError('transport uncertain')
        with self.assertRaisesRegex(RuntimeError, 'Unknown attempted request'):
            self.run_fake('fresh1', 'P0', 'smoke', fail)
        events = [json.loads(x) for x in (self.base / 'fresh1/P0/smoke.journal.jsonl').read_text().splitlines()]
        self.assertEqual(['phase_started', 'request_started', 'phase_stopped'], [e['event'] for e in events])
        self.assertTrue((self.base / 'fresh1/P0/smoke.claim.json').exists())
        with self.assertRaises(FileExistsError):
            self.run_fake('fresh1', 'P0', 'smoke')

    def test_missing_usage_is_null_on_returned_service_failure(self):
        def failed(cmd, prompt, env, cwd):
            return {'returncode': 1, 'stdout': json.dumps({'type': 'turn.failed'}),
                    'stderr': 'service unavailable', 'response': ''}
        with self.assertRaisesRegex(RuntimeError, 'stopped on first non-ok'):
            self.run_fake('fresh1', 'P0', 'smoke', failed)
        attempt = json.loads((self.base / 'fresh1/P0/smoke.attempts.jsonl').read_text().splitlines()[0])
        self.assertEqual('service_error', attempt['status'])
        self.assertIsNone(attempt['usage'])
        self.assertIsNone(attempt['input_tokens'])
        self.assertIsNone(attempt['output_tokens'])
        self.assertIsNone(attempt['cost_usd'])
        self.assertTrue((self.base / 'fresh1/P0/smoke.raw-0.json').exists())

    def test_runtime_version_and_auth_fail_closed(self):
        class Result:
            def __init__(self, stdout='', returncode=0):
                self.stdout, self.stderr, self.returncode = stdout, '', returncode
        def runner(cmd, **kwargs):
            if cmd[1] == 'login': return Result('Logged in using ChatGPT')
            if cmd[1] == '--version': return Result('codex-cli 0.999')
            return Result('')
        with self.assertRaisesRegex(RuntimeError, 'version changed'):
            m.runtime_check(runner=runner)
        with self.assertRaisesRegex(RuntimeError, 'CLI path'):
            m.runtime_check('/tmp/other-codex', runner=runner)

    def test_manifest_source_drift_and_prepare_exclusive(self):
        self.assertEqual(self.plans['fresh1'], m.verify_manifest(self.config, 'fresh1', self.hashes['fresh1']))
        with self.assertRaises(FileExistsError):
            m.prepare(self.config)
        changed = dict(self.plans['fresh1'])
        changed['model'] = 'wrong'
        (self.base / 'fresh1/manifest.json').write_text(json.dumps(changed))
        with self.assertRaisesRegex(ValueError, 'Manifest SHA'):
            m.verify_manifest(self.config, 'fresh1', self.hashes['fresh1'])


if __name__ == '__main__':
    unittest.main()
