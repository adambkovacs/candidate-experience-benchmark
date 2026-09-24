import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('recovery', ROOT / 'scripts/openrouter_mistral119_recovery_v1.py')
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


class RecoveryTest(unittest.TestCase):
    def prepared(self, effort):
        path = ROOT / f'results/mistral119-recovery-prep-v1/{effort}-smoke-manifest.json'
        return recovery.prepare(path, recovery.sha(path))

    def test_offline_preflight_binds_input_only_and_exact_routing(self):
        for effort in ('none', 'high'):
            with self.subTest(effort=effort):
                m, requests, budget = self.prepared(effort)
                self.assertIsNone(budget)
                self.assertEqual(len(requests), 3)
                self.assertEqual(m['record_ids'], ['DEV-001', 'DEV-002', 'DEV-003'])
                self.assertEqual(m['three_request_bound_usd'], '0.12533760')
                for p in requests:
                    self.assertEqual(p['provider']['only'], ['mistral/zdr'])
                    self.assertIs(p['provider']['allow_fallbacks'], False)
                    self.assertIs(p['provider']['require_parameters'], True)
                    self.assertEqual(set(json.loads(p['messages'][1]['content'])), {'feedback'})
                    self.assertNotIn('reference', json.dumps(p['messages'][1]).lower())

    def test_budget_boundary_blocks_three_request_overrun(self):
        with patch.object(recovery.paid, 'reservation', return_value=recovery.paid.Decimal('0.05000001')):
            with self.assertRaisesRegex(ValueError, 'Three-request reserve'):
                self.prepared('none')

    def test_exclusive_output_blocks_replay(self):
        m, _, _ = self.prepared('none')
        target = ROOT / m['output']
        original = Path.exists
        def exists(path):
            return True if path == target else original(path)
        with patch.object(Path, 'exists', exists):
            with self.assertRaisesRegex(FileExistsError, 'no replay'):
                self.prepared('none')

    def test_execute_routes_through_v2_partition_and_frozen_request(self):
        m, expected, _ = self.prepared('none')
        def fake_run(args):
            self.assertEqual(args.phase, 'smoke')
            self.assertEqual(args.provider, 'mistral/zdr')
            self.assertEqual(args.reasoning, 'none')
            self.assertEqual(args.max_tokens, 4096)
            self.assertEqual(args.timeout, 300)
            self.assertIs(sys.modules['paid_budget_partitions'], recovery.partitions_v2)
            original = json.loads((ROOT / m['sources']['historical_attempt']['file']).read_text())
            row = recovery.paid.select_rows(recovery.paid.read_rows(ROOT / 'data/pilot/inputs.jsonl'), 'smoke', 1)[0]
            actual = recovery.paid.make_payload(args.model, original['provider_endpoint'], row['feedback'], recovery.paid.baseline_instruction(), json.loads((ROOT / 'schemas/judgments.schema.json').read_text()), args.reasoning, args.max_tokens, args.max_input_price, args.max_output_price, original['model_catalog_entry'])
            self.assertEqual(actual, expected[0])
        with patch.object(recovery.paid, 'run', side_effect=fake_run):
            recovery.execute(m, expected, (ROOT / 'unallocated.json', 'proposed-partition'))
        self.assertIsNot(sys.modules.get('paid_budget_partitions'), recovery.partitions_v2)

    def test_execute_rejects_request_drift_before_http(self):
        m, expected, _ = self.prepared('high')
        original = json.loads((ROOT / m['sources']['historical_attempt']['file']).read_text())
        def fake_run(args):
            recovery.paid.make_payload(args.model, original['provider_endpoint'], 'tampered feedback', recovery.paid.baseline_instruction(), json.loads((ROOT / 'schemas/judgments.schema.json').read_text()), args.reasoning, args.max_tokens, args.max_input_price, args.max_output_price, original['model_catalog_entry'])
        with patch.object(recovery.paid, 'run', side_effect=fake_run):
            with self.assertRaisesRegex(ValueError, 'Live request differs'):
                recovery.execute(m, expected, (ROOT / 'unallocated.json', 'proposed-partition'))


if __name__ == '__main__':
    unittest.main()
