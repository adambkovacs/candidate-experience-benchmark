"""Offline adversarial tests for the native OpenRouter P1/P2 plan."""
import copy
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import openrouter_native_variants_plan as plan
import openrouter_decision_smoke as smoke


class NativeVariantsPlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        files = [*plan.SOURCE_PATHS, 'data/pilot/inputs.jsonl', 'docs/LABELING_GUIDE.md',
                 str(plan.KEV_PARENT), str(plan.KEV_HISTORY), str(plan.SNAPSHOTS / 'manifest.json'),
                 str(plan.SNAPSHOTS / 'kev-endpoint.json'), str(plan.SNAPSHOTS / 'jev-endpoint.json')]
        for name in files:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)

    def test_four_input_only_configs_and_three_distinct_passes(self):
        plans = plan.build_plan(self.root)
        self.assertEqual(len(plans), 4)
        self.assertEqual(set(plans), {f'{r}-openrouter-native-{c}-choice-v1'
                                      for r in ('kev', 'jev') for c in ('p1', 'p2')})
        for name, manifest in plans.items():
            self.assertFalse(manifest['admission']['execution_authorized'])
            self.assertFalse(manifest['reference_labels_read'])
            self.assertFalse(manifest['last_saved_headroom_covers_full_pass'])
            self.assertIn('not current headroom', manifest['master_budget_snapshot']['captured_as'])
            self.assertEqual(manifest['request_count'], 60)
            self.assertEqual(len(manifest['requests']), 60)
            self.assertEqual([x['id'] for x in manifest['requests']],
                             [f'DEV-{i:03}' for i in range(1, 61)])
            self.assertEqual(len({p['pass_id'] for p in manifest['passes']}), 3)
            self.assertEqual([p['ordinal'] for p in manifest['passes']], [1, 2, 3])
            self.assertEqual([p['stage'] for p in manifest['passes']], ['full_60'] * 3)
            self.assertTrue(all(p['request_set_sha256'] == manifest['requests_sha256']
                                for p in manifest['passes']))
            for record in manifest['requests']:
                payload = record['payload']
                self.assertEqual(set(payload['state']), {'feedback', 'policy'})
                self.assertEqual(set(payload), {'model', 'provider', 'state', 'questions'})
                self.assertEqual(record['payload_sha256'], smoke.sha(smoke.canonical(payload)))
                self.assertNotIn('DEV-', smoke.canonical(payload).decode())
                self.assertNotIn('reference_label', payload['state'])
            self.assertIn('saved endpoint', manifest['catalog_snapshot']['captured_as'])
        self.assertEqual(plans['kev-openrouter-native-p1-choice-v1']['p0_parent']['fresh3_status'],
                         '59_observed_valid_plus_one_unknown_not_clean')
        self.assertEqual(plans['jev-openrouter-native-p2-choice-v1']['p0_parent']['scope'],
                         'three_record_P0_smoke_only')

    def test_only_four_instruction_strings_change_and_p2_includes_p1(self):
        manifests = plan.build_plan(self.root)
        for route_name in ('kev', 'jev'):
            p1 = manifests[f'{route_name}-openrouter-native-p1-choice-v1']
            p2 = manifests[f'{route_name}-openrouter-native-p2-choice-v1']
            for first, second in zip(p1['requests'], p2['requests']):
                self.assertEqual(first['id'], second['id'])
                parent = smoke.request_payload(first['payload']['state']['feedback'],
                                               first['payload']['state']['policy'],
                                               smoke.ROUTES[route_name])
                self.assertEqual(first['p0_payload_sha256'], smoke.sha(smoke.canonical(parent)))
                plan.verify_instruction_delta(parent, first['payload'], 'P1')
                plan.verify_instruction_delta(parent, second['payload'], 'P2')
                for key in plan.KEYS:
                    self.assertEqual(second['payload']['questions'][key]['instructions'],
                                     first['payload']['questions'][key]['instructions'] + plan.variants.P2[key])

    def test_rejects_reference_or_metadata_in_inputs(self):
        path = self.root / 'data/pilot/inputs.jsonl'
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        rows[0]['reference_label'] = 'positive'
        path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        with self.assertRaisesRegex(ValueError, 'Input must contain only'):
            plan.build_plan(self.root)

    def test_rejects_endpoint_price_and_revision_drift(self):
        path = self.root / plan.SNAPSHOTS / 'kev-endpoint.json'
        original = json.loads(path.read_text())
        for field, value in [('pricing', {'prompt': '0.000000043', 'completion': '0', 'discount': 0}),
                             ('name', 'SiliconFlow | jaredpalmer/kev-4b-unknown')]:
            changed = copy.deepcopy(original)
            changed['data']['endpoints'][0][field] = value
            path.write_text(json.dumps(changed))
            with self.subTest(field=field), self.assertRaises(ValueError):
                plan.build_plan(self.root)

    def test_rejects_p0_parent_drift_and_question_schema_change(self):
        path = self.root / plan.KEV_PARENT
        saved = json.loads(path.read_text())
        saved['requests'][0]['payload']['questions']['sentiment']['criteria']['positive'] = 'changed'
        path.write_text(json.dumps(saved))
        with self.assertRaisesRegex(ValueError, 'Kev P0 parent payload drift'):
            plan.build_plan(self.root)
        parent = smoke.request_payload('feedback', 'policy', smoke.ROUTES['kev'])
        candidate = plan.variant_payload(parent, 'P1')
        candidate['questions']['sentiment']['criteria']['positive'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'outside Choice instructions'):
            plan.verify_instruction_delta(parent, candidate, 'P1')

    def test_immutable_preparation_and_exact_verification(self):
        out = Path(self.temp.name) / 'out'
        hashes = plan.prepare(out, self.root)
        self.assertEqual(hashes, plan.verify(out, self.root))
        with self.assertRaisesRegex(ValueError, 'must be empty'):
            plan.prepare(out, self.root)
        target = out / 'kev-openrouter-native-p2-choice-v1.json'
        saved = json.loads(target.read_text())
        saved['requests'][0]['payload']['state']['feedback'] = 'tampered'
        target.write_text(json.dumps(saved))
        with self.assertRaisesRegex(ValueError, 'differs from source'):
            plan.verify(out, self.root)

    def test_suffix_source_hash_is_pinned(self):
        path = self.root / 'scripts/jev_native_prompt_variants_v1.py'
        path.write_bytes(path.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'suffix source changed'):
            plan.build_plan(self.root)


if __name__ == '__main__':
    unittest.main()
