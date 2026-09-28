"""Offline native OpenJev admission regressions; no server or model calls."""
import base64
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import openjev_native_repeat_admission as study


class DummyServer:
    def poll(self): return 0


class NativeOpenJevTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.plan_path = self.root / 'manifest.json'
        self.lock = self.root / 'common.lock'
        self.mode = 'fixed'
        self.phase = 'openjev-fixed/fresh1/P0'
        self.plan_sha = 'a' * 64
        saved = study.rows(study.HISTORY['fixed'] / 'smoke.jsonl')
        self.responses = [r['raw_response'] for r in saved]
        self.requests = [{'id': r['id'], 'request_sha256': r['request_sha256'],
                          'payload': {'model': 'openjev-0.1', 'state': {'feedback': r['id']}}}
                         for r in saved]
        self.plan = {'schedule': [self.phase], 'requests': {'fixed': self.requests},
                     'artifact_manifest_sha256': 'b' * 64}
        self.receipt = self.root / 'receipt.json'
        self.receipt.write_text(json.dumps({'kind': 'root-reviewed-openjev-native-stage-v1',
            'approved': True, 'phase': self.phase, 'stage': 'smoke',
            'plan_sha256': self.plan_sha, 'controller_sha256': study.sha(study.__file__),
            'predecessor_sha256': None, 'reference_labels_read': False,
            'source_commit': study.SOURCE_COMMIT,
            'artifact_manifest_sha256': self.plan['artifact_manifest_sha256']}))
        self.patchers = [mock.patch.object(study, 'PLAN_PATH', self.plan_path),
                         mock.patch.object(study, 'HOST_LOCK', self.lock),
                         mock.patch.object(study, 'start_server', side_effect=self.fake_server)]
        for patcher in self.patchers:
            patcher.start(); self.addCleanup(patcher.stop)

    @staticmethod
    def fake_server(folder, stage, lock_fd):
        assert lock_fd >= 0
        (folder / f'{stage}.server.log').touch(exist_ok=False)
        return DummyServer()

    def transport(self, payload, timeout=study.TIMEOUT):
        rid = payload['state']['feedback']
        i = (int(rid[-3:]) - 1) % 3
        return {'http_status': 200, 'headers': {'content-type': 'application/json'},
                'body_base64': base64.b64encode(json.dumps(self.responses[i]).encode()).decode(),
                'truncated': False, 'incomplete': False}

    def test_input_only_payloads_and_historical_mode_parity(self):
        rows, policy, requests = study.source_rows()
        self.assertEqual(len(rows), 60)
        self.assertEqual(set(requests), set(study.MODES))
        self.assertEqual(requests['fixed'][0]['payload']['samples'], 1)
        self.assertNotIn('samples', requests['adaptive'][0]['payload'])
        self.assertEqual(requests['thinking'][0]['payload']['think'], 512)
        self.assertNotIn('proposed_labels', json.dumps(requests))
        history = study.history(study.ROOT, requests)
        self.assertTrue(all(not x['eligible_as_fresh_pass1'] for x in history.values()))
        self.assertEqual(len(study.rows(study.HISTORY['fixed'] / 'development.jsonl')), 7)
        self.assertEqual(len(study.rows(study.HISTORY['fixed'] / 'development-continuation.jsonl')), 53)

    def test_root_receipt_fails_before_claim_and_server(self):
        receipt = json.loads(self.receipt.read_text())
        receipt['plan_sha256'] = 'wrong'
        self.receipt.write_text(json.dumps(receipt))
        with mock.patch.object(study, 'transport', side_effect=AssertionError('must not fetch')):
            with self.assertRaisesRegex(ValueError, 'not root reviewed'):
                study.execute(self.plan, self.plan_sha, self.phase, 'smoke', self.receipt)
        self.assertFalse((study.phase_folder(self.phase) / 'smoke.claim.json').exists())

    def test_smoke_raw_is_durable_before_projection_and_no_replay(self):
        observed = []
        original = study.parse_response
        def parse(body, model):
            raw = study.phase_folder(self.phase) / 'smoke.raw.jsonl'
            observed.append(len(study.rows(raw)))
            return original(body, model)
        with mock.patch.object(study, 'transport', side_effect=self.transport), \
             mock.patch.object(study, 'parse_response', side_effect=parse):
            study.execute(self.plan, self.plan_sha, self.phase, 'smoke', self.receipt)
        self.assertEqual(observed, [1, 2, 3])
        folder = study.phase_folder(self.phase)
        self.assertEqual(study.read_json(folder / 'smoke.completion.json')['status'], 'completed')
        self.assertEqual(len(study.rows(folder / 'smoke.records.jsonl')), 3)
        self.assertTrue(all(r['reference_labels_read'] is False
                            for r in study.rows(folder / 'smoke.records.jsonl')))
        with self.assertRaisesRegex(ValueError, 'already claimed'):
            study.execute(self.plan, self.plan_sha, self.phase, 'smoke', self.receipt)

    def test_successful_smoke_then_development_uses_distinct_server_log(self):
        for n in range(4, 61):
            rid = f'DEV-{n:03d}'
            payload = {'model': 'openjev-0.1', 'state': {'feedback': rid}}
            self.requests.append({'id': rid, 'request_sha256': study.digest(json.dumps(payload,sort_keys=True)),
                                  'payload': payload})
        with mock.patch.object(study, 'transport', side_effect=self.transport):
            study.execute(self.plan, self.plan_sha, self.phase, 'smoke', self.receipt)
            folder = study.phase_folder(self.phase)
            smoke = study.read_json(folder / 'smoke.completion.json')
            inspection = folder / 'smoke-inspection.json'
            inspection.write_text(json.dumps({'kind': 'openjev-native-smoke-inspection-v1',
                'approved': True, 'phase': self.phase, 'plan_sha256': self.plan_sha,
                'raw_sha256': smoke['raw_sha256'], 'records_sha256': smoke['records_sha256'],
                'reference_labels_read': False}))
            dev_receipt = self.root / 'development-receipt.json'
            receipt = json.loads(self.receipt.read_text())
            receipt.update(stage='development', predecessor_sha256=study.sha(inspection))
            dev_receipt.write_text(json.dumps(receipt))
            study.execute(self.plan, self.plan_sha, self.phase, 'development', dev_receipt)
        self.assertTrue((folder / 'smoke.server.log').exists())
        self.assertTrue((folder / 'development.server.log').exists())
        self.assertEqual(study.read_json(folder / 'development.completion.json')['count'], 60)

    def test_malformed_http200_raw_retained_and_smoke_stops(self):
        def malformed(payload, timeout=study.TIMEOUT):
            return {'http_status': 200, 'headers': {}, 'body_base64': base64.b64encode(b'{bad').decode(),
                    'truncated': False, 'incomplete': False}
        with mock.patch.object(study, 'transport', side_effect=malformed), \
             self.assertRaisesRegex(ValueError, 'Smoke intrinsic invalid'):
            study.execute(self.plan, self.plan_sha, self.phase, 'smoke', self.receipt)
        folder = study.phase_folder(self.phase)
        self.assertEqual(len(study.rows(folder / 'smoke.raw.jsonl')), 1)
        self.assertEqual(study.rows(folder / 'smoke.raw.jsonl')[0]['body_base64'],
                         base64.b64encode(b'{bad').decode())
        self.assertEqual(study.rows(folder / 'smoke.records.jsonl')[0]['decision']['status'], 'invalid_output')
        self.assertEqual(study.read_json(folder / 'smoke.completion.json')['status'], 'stopped')

    def test_unknown_transport_failure_stops_without_replay(self):
        with mock.patch.object(study, 'transport', side_effect=TimeoutError('timeout')), \
             self.assertRaisesRegex(ValueError, 'TimeoutError'):
            study.execute(self.plan, self.plan_sha, self.phase, 'smoke', self.receipt)
        folder = study.phase_folder(self.phase)
        self.assertEqual(study.read_json(folder / 'smoke.completion.json')['status'], 'stopped')
        self.assertEqual(len(study.rows(folder / 'smoke.raw.jsonl')), 1)
        self.assertEqual(study.rows(folder / 'smoke.records.jsonl'), [])
        with self.assertRaisesRegex(ValueError, 'already claimed'):
            study.execute(self.plan, self.plan_sha, self.phase, 'smoke', self.receipt)

    def test_common_lock_denies_second_process_before_claim(self):
        holder = subprocess.Popen([sys.executable, '-c',
            'import fcntl,sys,time; f=open(sys.argv[1],"a+"); fcntl.flock(f,fcntl.LOCK_EX); print("locked",flush=True);time.sleep(20)',
            str(self.lock)], stdout=subprocess.PIPE, text=True)
        def close_holder():
            if holder.poll() is None: holder.kill()
            holder.wait()
            holder.stdout.close()
        self.addCleanup(close_holder)
        self.assertEqual(holder.stdout.readline().strip(), 'locked')
        with self.assertRaises(BlockingIOError):
            study.execute(self.plan, self.plan_sha, self.phase, 'smoke', self.receipt)
        self.assertFalse((study.phase_folder(self.phase) / 'smoke.claim.json').exists())


if __name__ == '__main__': unittest.main()
