import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import clef_openrouter_luna_full_v2 as bridge
import clef_openrouter_full_v1 as common
import openrouter_decision_smoke as native


class LunaFullBridgeTests(unittest.TestCase):
    def test_plan_binds_existing_common_and_exact_two_plan(self):
        with mock.patch.object(common, 'verify', return_value=({}, 'a' * 64)), \
                mock.patch.object(bridge.luna, 'verify', return_value=({}, 'b' * 64)):
            value = bridge.build(ROOT)
        self.assertEqual(value['key'], 'luna-decisions')
        self.assertEqual(value['stage'], 'fresh1/P0')
        self.assertEqual(value['common_full_plan_sha256'], 'a' * 64)
        self.assertEqual(value['luna_exact_two_plan_sha256'], 'b' * 64)
        self.assertEqual(value['wrapper_sha256'], native.sha((ROOT / 'scripts/clef_openrouter_luna_full_v2.py').read_bytes()))

    def test_composite_gate_rechecked_with_each_common_request(self):
        calls = []
        prior = common.verify_smoke_inspection
        def fake_common(key, stage, budget, **kwargs):
            calls.append((key, stage, kwargs['phase']))
            calls.append(common.verify_smoke_inspection(ROOT, key, stage, 'r' * 64, 'f' * 64))
            calls.append(common.verify_smoke_inspection(ROOT, key, stage, 'r' * 64, 'f' * 64))
        with mock.patch.object(bridge, 'verify_composite_review', return_value='i' * 64) as checked, \
                mock.patch.object(bridge, 'verify', return_value=({'common_full_plan_sha256': 'f' * 64}, 'p' * 64)), \
                mock.patch.object(common, 'run', side_effect=fake_common):
            bridge.run(Path('budget.json'))
        self.assertEqual(calls, [('luna-decisions', 'fresh1/P0', 'development'), 'i' * 64, 'i' * 64])
        self.assertEqual(checked.call_count, 3)
        self.assertIs(common.verify_smoke_inspection, prior)

    def test_missing_composite_approval_blocks_before_common_runner(self):
        with mock.patch.object(bridge, 'verify_composite_review', side_effect=ValueError('missing approval')), \
                mock.patch.object(common, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'missing approval'):
                bridge.run(Path('budget.json'))
            run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
