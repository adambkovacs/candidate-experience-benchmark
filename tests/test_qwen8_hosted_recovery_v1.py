import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('recovery', ROOT / 'scripts/qwen8_hosted_recovery_v1.py')
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)
FOLDER = ROOT / 'results/qwen8-hosted-recovery-prep-v1'


class RecoveryTest(unittest.TestCase):
    def manifest(self, mode):
        p = FOLDER / f'{mode}-smoke-manifest.json'
        return p, recovery.sha(p)

    def test_preflight_preserves_exact_json_object_input_only_routing(self):
        for mode in ('off', 'on'):
            with self.subTest(mode=mode):
                p, digest = self.manifest(mode)
                m, paths, budget = recovery.prepare(p, digest)
                self.assertIsNone(budget)
                rows, _, _, _, _, _ = recovery.adapter.reviewed_preview(paths['preview'], paths['original_review'])
                self.assertEqual([r['id'] for r in rows], ['DEV-001', 'DEV-002', 'DEV-003'])
                self.assertEqual(m['three_call_bound_usd'], '0.051597312')
                for r in rows:
                    request = r['request']
                    self.assertEqual(request['model'], 'qwen/qwen3-8b')
                    self.assertEqual(request['provider']['only'], ['alibaba'])
                    self.assertIs(request['provider']['allow_fallbacks'], False)
                    self.assertEqual(request['response_format'], {'type': 'json_object'})
                    self.assertEqual(set(json.loads(request['messages'][1]['content'])), {'feedback'})
                    self.assertEqual(request['reasoning'], {'enabled': mode == 'on'})

    def test_three_call_reserve_must_fit(self):
        p, digest = self.manifest('off')
        with patch.object(recovery, 'reservation', return_value=recovery.number('0.020000001')):
            with self.assertRaisesRegex(ValueError, 'Three-call bound'):
                recovery.prepare(p, digest)

    def test_exclusive_output_blocks_replay(self):
        p, digest = self.manifest('off')
        target = ROOT / json.loads(p.read_text())['output']
        old = Path.exists
        def exists(path):
            return True if path == target else old(path)
        with patch.object(Path, 'exists', exists):
            with self.assertRaisesRegex(FileExistsError, 'no replay'):
                recovery.prepare(p, digest)

    def test_execute_uses_v2_partition_helper(self):
        p, digest = self.manifest('on')
        m, paths, _ = recovery.prepare(p, digest)
        def fake_execute(args):
            self.assertIs(sys.modules['paid_budget_partitions'], recovery.partitions_v2)
            self.assertEqual(args.preview_file, str(paths['preview']))
            self.assertEqual(args.review_receipt, str(paths['original_review']))
            self.assertEqual(args.partition_id, 'qwen8-on-recovery')
            self.assertEqual(args.timeout, 300)
        with patch.object(recovery.adapter, 'execute', side_effect=fake_execute):
            recovery.execute(m, paths, (ROOT / 'allocated.json', 'qwen8-on-recovery'))
        self.assertIsNot(sys.modules.get('paid_budget_partitions'), recovery.partitions_v2)

    def test_root_receipt_and_partition_cap_required(self):
        p, digest = self.manifest('off')
        with tempfile.TemporaryDirectory(dir=FOLDER) as temporary:
            folder = Path(temporary)
            budget = folder / 'budget.json'
            receipt = folder / 'review.json'
            entry = {'id':'test-off','model':'qwen/qwen3-8b','provider':'alibaba','reasoning':'off','cap_usd':'0.05'}
            budget.write_text(json.dumps({'partitions':[entry]}))
            base = {'approved':True,'recovery_manifest_sha256':digest,'wrapper_sha256':recovery.sha(recovery.__file__),'budget_manifest_sha256':recovery.sha(budget),'partition_id':'test-off'}
            receipt.write_text(json.dumps(base))
            with self.assertRaisesRegex(ValueError, 'Budget partition'):
                recovery.prepare(p, digest, budget, 'test-off', receipt)
            entry['cap_usd'] = '0.06'
            budget.write_text(json.dumps({'partitions':[entry]}))
            with self.assertRaisesRegex(ValueError, 'Missing exact root review'):
                recovery.prepare(p, digest, budget, 'test-off', receipt)
            base['budget_manifest_sha256'] = recovery.sha(budget)
            receipt.write_text(json.dumps(base))
            _, _, selected = recovery.prepare(p, digest, budget, 'test-off', receipt)
            self.assertEqual(selected[1], 'test-off')


if __name__ == '__main__':
    unittest.main()
