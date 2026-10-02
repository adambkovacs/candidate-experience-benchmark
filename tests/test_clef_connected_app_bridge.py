import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import clef_connected_app_bridge as bridge
import clef_native_preparation as prep
import clef_native_smoke_runner as smoke

ACCOUNT = 'a' * 32
TOKEN = 'offline-test-token'
ENV = {prep.ACCOUNT_ENV: ACCOUNT, prep.TOKEN_ENV: TOKEN}
SOURCES = {name: (name + '-reviewed-source').encode() for name in prep.MODELS}


class ConnectedAppBridgeTests(unittest.TestCase):
    def files(self, folder):
        manifest = folder / 'manifest.json'
        plan = prep.build_plan()
        manifest.write_bytes(prep.canonical(plan) + b'\n')
        grant = folder / 'grant.json'
        grant.write_bytes(prep.canonical({
            'kind': 'clef-native-initial-smoke-grant-v1', 'approved': True,
            'authorized_by_user': True, 'reviewer': 'offline-fixture',
            'plan_sha256': prep.sha(prep.canonical(plan)),
            'runner_sha256': prep.sha(Path(smoke.__file__).read_bytes()),
            'account_id_sha256': prep.sha(ACCOUNT.encode()),
            'models': list(prep.MODELS), 'stage': smoke.STAGE, 'cap_usd': '0.10',
            'exhaustion_policy': 'pause',
            'billing_source_sha256': {name: prep.sha(raw) for name, raw in SOURCES.items()},
            'input_usd_per_million': {name: str(spec['input_usd_per_million'])
                                      for name, spec in prep.MODELS.items()},
        }) + b'\n')
        review = folder / 'bridge-review.json'
        review.write_bytes(prep.canonical({
            'kind': bridge.REVIEW_KIND, 'approved': True, 'reviewer': 'offline-fixture',
            'transport': 'mcp__codex_apps__cloudflare_execute', 'model': 'clef',
            'stage': smoke.STAGE, 'manifest_sha256': prep.sha(manifest.read_bytes()),
            'grant_sha256': prep.sha(grant.read_bytes()),
            'runner_sha256': prep.sha(Path(smoke.__file__).read_bytes()),
            'bridge_sha256': prep.sha(Path(bridge.__file__).read_bytes()),
            'account_id_sha256': prep.sha(ACCOUNT.encode()), 'wait_seconds': 1,
        }) + b'\n')
        return manifest, grant, review

    def billing(self, url):
        model = next(name for name, spec in prep.MODELS.items() if spec['source'] == url)
        return SOURCES[model]

    def transport(self, output, review):
        return bridge.AppBridgeTransport(output, 'clef', ACCOUNT,
                                         prep.sha(review.read_bytes()), 1, 0.01)

    def wait_request(self, output):
        folder = output / 'clef/fresh1/P0/smoke/app-bridge'
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            files = list(folder.glob('*.request.json')) if folder.exists() else []
            if files:
                return files[0]
            time.sleep(0.01)
        self.fail('No ready request')

    def test_review_pins_code_grant_account_and_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            manifest, grant, review = self.files(folder)
            observed = bridge.checked_review(review, model='clef', manifest=manifest,
                                              grant=grant, account_id=ACCOUNT,
                                              wait_seconds=1)
            self.assertEqual(observed, prep.sha(review.read_bytes()))
            with self.assertRaisesRegex(ValueError, 'bridge receipt'):
                bridge.checked_review(review, model='clef-flash', manifest=manifest,
                                      grant=grant, account_id=ACCOUNT, wait_seconds=1)
            with self.assertRaisesRegex(ValueError, 'bridge receipt'):
                bridge.checked_review(review, model='clef', manifest=manifest,
                                      grant=grant, account_id='b' * 32, wait_seconds=1)

    def test_ready_follows_durable_reservation_and_app_error_stops(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            manifest, grant, review = self.files(folder)
            output = folder / 'results'
            result = {}
            def worker():
                result['completion'] = smoke.run_smoke('clef', manifest, grant,
                    output_root=output, environment=ENV,
                    transport=self.transport(output, review), billing_source=self.billing)
            thread = threading.Thread(target=worker)
            thread.start()
            ready_path = self.wait_request(output)
            ready = bridge.read_json(ready_path)
            self.assertEqual(ready['id'], 'DEV-001')
            self.assertEqual(ready['path'], '/accounts/{ACCOUNT_ID}/ai/run/@cf/cloudflare/clef')
            self.assertEqual(ready['body']['model'], 'clef')
            self.assertNotIn(ACCOUNT, ready_path.read_text())
            self.assertNotIn(TOKEN, ready_path.read_text())
            ledger = [json.loads(line) for line in (output / 'budget.jsonl').read_text().splitlines()]
            self.assertEqual(ledger[-1]['event'], 'reserve')
            self.assertEqual(ledger[-1]['attempt_id'], ready['attempt_id'])
            journal = [json.loads(line) for line in (output / 'clef/fresh1/P0/smoke/journal.jsonl').read_text().splitlines()]
            self.assertEqual(journal[-1]['event'], 'started')
            self.assertEqual(journal[-1]['attempt_id'], ready['attempt_id'])
            app_body = folder / 'app-envelope.json'
            app_body.write_bytes(prep.canonical({'status': 429, 'success': False,
                'errors': [{'code': 9001, 'message': 'offline fixture'}],
                'messages': [], 'result': None}))
            response = bridge.submit_response(ready_path, app_body)
            with self.assertRaises(FileExistsError):
                bridge.submit_response(ready_path, app_body)
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(result['completion']['attempted'], 1)
            self.assertEqual(result['completion']['counts']['service_error'], 1)
            self.assertEqual(result['completion']['never_sent'], ['DEV-002', 'DEV-003'])
            self.assertEqual(bridge.read_json(response)['request_sha256'], ready['request_sha256'])

    def test_missing_response_is_unknown_and_never_replayed(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            manifest, grant, review = self.files(folder)
            output = folder / 'results'
            completion = smoke.run_smoke('clef', manifest, grant, output_root=output,
                environment=ENV, transport=self.transport(output, review),
                billing_source=self.billing)
            self.assertEqual(completion['counts']['unknown_outcome'], 1)
            self.assertEqual(completion['never_sent'], ['DEV-002', 'DEV-003'])
            self.assertEqual(len(list(output.rglob('*.request.json'))), 1)
            with self.assertRaises((FileExistsError, ValueError)):
                smoke.run_smoke('clef', manifest, grant, output_root=output,
                    environment=ENV, transport=self.transport(output, review),
                    billing_source=self.billing)

    def test_bad_reply_is_unknown_and_cannot_reuse_attempt(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            manifest, grant, review = self.files(folder)
            output = folder / 'results'
            result = {}
            def worker():
                result['completion'] = smoke.run_smoke('clef', manifest, grant,
                    output_root=output, environment=ENV,
                    transport=self.transport(output, review), billing_source=self.billing)
            thread = threading.Thread(target=worker)
            thread.start()
            ready_path = self.wait_request(output)
            ready = bridge.read_json(ready_path)
            response_path = ready_path.with_name(ready['attempt_id'] + '.response.json')
            bridge.atomic_json(response_path, {'kind': bridge.KIND + '-response',
                'attempt_id': 'wrong', 'request_sha256': ready['request_sha256'],
                'http_status': 200, 'body_base64': 'e30='})
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(result['completion']['counts']['unknown_outcome'], 1)
            self.assertEqual(result['completion']['never_sent'], ['DEV-002', 'DEV-003'])


if __name__ == '__main__':
    unittest.main()
