import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import openrouter_qwen27_repeat as q


class Qwen27RepeatTests(unittest.TestCase):
    def test_all_historical_requests_and_rotation(self):
        plans = {repeat: q.plan_data(repeat) for repeat in q.SPEC.orders}
        self.assertEqual(plans['repeat2']['condition_order'], ['P2', 'P1', 'P0'])
        self.assertEqual(plans['repeat3']['condition_order'], ['P1', 'P0', 'P2'])
        self.assertEqual(q.SPEC.timeout, 300.0)
        self.assertFalse(q.SPEC.continue_invalid)
        self.assertEqual(q.SPEC.cap, '0.20')
        for repeat, plan in plans.items():
            self.assertFalse(plan['reference_labels_read'])
            self.assertEqual(plan['repeat_status'], 'offline_prepared_no_inference')
            bindings = {x['path'] for x in plan['source_bindings']}
            self.assertIn('scripts/openrouter_qwen27_repeat.py', bindings)
            self.assertIn(q.PREFLIGHT, bindings)
            for condition in ('P0', 'P1', 'P2'):
                requests = plan['conditions'][condition]['development']
                self.assertEqual(len(requests), 60)
                self.assertEqual([r['record_id'] for r in requests],
                                 [f'DEV-{i:03}' for i in range(1, 61)])
                self.assertEqual(plan['conditions'][condition]['smoke'], requests[:3])
                for request in requests:
                    payload = request['payload']
                    self.assertEqual(payload['provider']['only'], ['deepinfra/bf16'])
                    self.assertFalse(payload['provider']['allow_fallbacks'])
                    self.assertEqual(payload['reasoning'], {'enabled': False})
                    self.assertNotIn('seed', payload)

    def test_public_snapshot_rebuilds_exact_requests_and_reserve(self):
        pair = json.loads((q.ROOT / q.SPEC.pair).read_text())
        source = q.ROOT / pair['conditions']['P2']['request_evidence']['file']
        original = json.loads(source.read_text().splitlines()[0])
        catalog, endpoints = original['model_catalog_entry'], original['provider_endpoint']
        with (patch.object(q.paid, 'fetch', side_effect=[{}, {}]),
              patch.object(q.paid, 'select_endpoint', return_value=(catalog, endpoints))):
            _, endpoint, reserve = q.live_controls(q.plan_data('repeat2'), 'P2')
        self.assertEqual(endpoint['tag'], 'deepinfra/bf16')
        self.assertEqual(str(reserve), '0.047001600')

    def test_route_drift_blocks_before_credential_or_claim(self):
        plan = q.plan_data('repeat2')
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            folder = base / 'repeat2/P2'
            with (patch.object(q, 'verify', return_value=plan),
                  patch.object(q.wave, 'require_order'),
                  patch.object(q.wave, 'phase_paths', return_value=(folder,
                      folder / 'smoke.claim.json', folder / 'smoke.journal.jsonl',
                      folder / 'smoke.attempts.jsonl')),
                  patch.object(q, 'review_receipt', return_value=({'partition_id': 'x'}, base)),
                  patch.object(q, 'live_controls', side_effect=ValueError('route drift')),
                  patch.object(q.paid, 'load_key') as load_key,
                  patch.object(q.partitions, 'open_partition') as open_partition):
                with self.assertRaisesRegex(ValueError, 'route drift'):
                    q.execute('repeat2', 'P2', 'smoke', 'test-hash', base)
                load_key.assert_not_called()
                open_partition.assert_not_called()
                self.assertFalse((folder / 'smoke.claim.json').exists())

    def test_root_receipt_requires_new_controller_and_budget_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'receipt.json'
            path.write_text(json.dumps({'schema': q.RECEIPT_SCHEMA, 'approved': True,
                                        'configuration_id': q.SPEC.id,
                                        'partition_cap_usd': q.SPEC.cap,
                                        'controller_sha256': 'wrong'}))
            with self.assertRaisesRegex(ValueError, 'Root review receipt'):
                q.review_receipt(path, 'repeat2', 'hash')

    def test_raw_malformed_success_body_is_durable_before_json_parse(self):
        class Response:
            status = 200
            headers = {'content-type': 'application/json', 'content-length': '5'}
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, count): return b'{bad}'
        with tempfile.TemporaryFile(mode='w+') as output:
            with patch.object(q.wave.transport.OPENER, 'open', return_value=Response()):
                with self.assertRaises(json.JSONDecodeError):
                    q.wave.fetch_recorded({'model': q.SPEC.model}, 'fake-token', 300.0,
                                          output, 'DEV-001', 'attempt', 'request-sha')
            output.seek(0)
            raw = json.loads(output.read())
        self.assertEqual(raw['http_status'], 200)
        self.assertEqual(raw['body_base64'], 'e2JhZH0=')


if __name__ == '__main__':
    unittest.main()
