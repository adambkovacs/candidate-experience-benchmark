import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import gemini_repeat_roster as original
from gemini_repeat_high import runner

class HighRosterTests(unittest.TestCase):
    def test_isolated_frozen_mechanics_and_wrapper_binding(self):
        self.assertIsNot(runner, original)
        self.assertNotIn('gemini37-flash-high-p0-openrouter-v3', original.CONFIGS)
        for config, (_, model, effort, partition, cap) in runner.CONFIGS.items():
            for repeat, order in runner.ORDERS.items():
                plan = runner.expected_plan(config, repeat)
                self.assertEqual(plan['schema'], 'gemini-openrouter-repeat-high-v1')
                self.assertEqual(plan['effort'], 'high')
                self.assertEqual(plan['condition_order'], list(order))
                self.assertEqual(plan['proposed_partition_cap_usd'], cap)
                self.assertFalse(plan['partition_allocated'])
                self.assertFalse(plan['reference_labels_read'])
                for file in ('scripts/gemini_repeat_high.py', 'scripts/gemini_repeat_roster.py'):
                    key = file if file.endswith('_high.py') else 'controller'
                    binding = plan['source_bindings'][key]
                    self.assertEqual(binding['path'], file)
                    self.assertEqual(binding['sha256'], hashlib.sha256((runner.ROOT / file).read_bytes()).hexdigest())
                for condition in ('P0', 'P1', 'P2'):
                    reqs = plan['conditions'][condition]['requests']
                    self.assertEqual(len(reqs), 7)
                    self.assertEqual([rid for q in reqs[1:] for rid in q['record_ids']], [f'DEV-{i:03}' for i in range(1,61)])
                    for q in reqs:
                        self.assertEqual(q['payload']['model'], model)
                        self.assertEqual(q['payload']['reasoning'], {'enabled':True, 'effort':effort})
                        self.assertEqual(q['payload']['provider']['only'], ['google-ai-studio'])
                        self.assertFalse(q['payload']['provider']['allow_fallbacks'])

    def test_plan_rejects_effort_change_without_dispatch(self):
        plan = runner.expected_plan('gemini37-flash-high-p0-openrouter-v3', 'repeat2')
        with tempfile.TemporaryDirectory(dir=runner.BASE) as d:
            p=Path(d)/'manifest.json';p.write_text(json.dumps(plan))
            self.assertEqual(runner.validate_plan(p),plan)
            plan['effort']='medium';p.write_text(json.dumps(plan))
            with self.assertRaisesRegex(ValueError,'differs'):
                runner.validate_plan(p)

    def test_order_gate_still_requires_inspected_smoke(self):
        plan=runner.expected_plan('gemini37-flash-high-p0-openrouter-v3','repeat2')
        with tempfile.TemporaryDirectory() as d, patch.object(runner,'BASE',Path(d)):
            runner.require_order(plan,'P1','smoke')
            with self.assertRaisesRegex(ValueError,'inspected smoke'):
                runner.require_order(plan,'P1','development')

if __name__ == '__main__':
    unittest.main()
