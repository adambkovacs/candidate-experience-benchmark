"""Adversarial offline checks for Solar Decide native Choice preparation."""
from copy import deepcopy
from decimal import Decimal
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import solar_decide_offline_plan as solar
import openrouter_decision_smoke as smoke


class SolarDecideOfflinePlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        for name in [*solar.SOURCE_PATHS, str(solar.SNAPSHOT), str(solar.AUDIT),
                     'data/pilot/inputs.jsonl', 'docs/LABELING_GUIDE.md']:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, target)

    def test_six_exact_routes_conditions_and_three_full_passes(self):
        plans = solar.build_plans(self.root)
        self.assertEqual(len(plans), 6)
        self.assertEqual(set(plans), {f'solar-decide-openrouter-{tag}-native-{p}-v1'
                                      for tag in ('upstage', 'upstage-zdr') for p in ('p0', 'p1', 'p2')})
        for name, manifest in plans.items():
            self.assertEqual(manifest['api_url'], 'https://openrouter.ai/api/alpha/decisions')
            self.assertEqual(manifest['model'], solar.MODEL)
            self.assertEqual(manifest['expected_returned_model'], solar.VERSION)
            self.assertEqual(manifest['expected_returned_provider'], solar.PROVIDER)
            self.assertFalse(manifest['reference_labels_read'])
            self.assertFalse(manifest['admission']['execution_authorized'])
            self.assertFalse(manifest['parser']['solar_response_wrapper_verified'])
            self.assertEqual(len(manifest['requests']), 60)
            self.assertEqual([x['id'] for x in manifest['requests']],
                             [f'DEV-{i:03}' for i in range(1, 61)])
            self.assertEqual([p['ordinal'] for p in manifest['passes']], [1, 2, 3])
            self.assertEqual(len({p['pass_id'] for p in manifest['passes']}), 3)
            self.assertTrue(all(p['request_set_sha256'] == manifest['requests_sha256']
                                for p in manifest['passes']))
            self.assertEqual(Decimal(manifest['per_request_full_context_catalog_bound_usd']),
                             Decimal('0.0262144'))
            self.assertEqual(Decimal(manifest['three_record_smoke_catalog_bound_usd']),
                             Decimal('0.0786432'))
            self.assertEqual(Decimal(manifest['full_pass_catalog_bound_usd']), Decimal('1.572864'))
            self.assertEqual(Decimal(manifest['three_pass_catalog_bound_usd']), Decimal('4.718592'))
            for row in manifest['requests']:
                payload = row['payload']
                self.assertEqual(set(payload), {'model', 'provider', 'state', 'questions'})
                self.assertEqual(set(payload['state']), {'feedback', 'policy'})
                self.assertEqual(payload['provider']['only'], [manifest['provider_tag']])
                self.assertEqual(payload['provider']['max_price']['prompt'], 0.05)
                self.assertEqual(row['payload_sha256'], smoke.sha(smoke.canonical(payload)))
                self.assertNotIn('DEV-', smoke.canonical(payload).decode())

    def test_p1_p2_exact_instruction_only_delta_from_p0(self):
        plans = solar.build_plans(self.root)
        for tag in ('upstage', 'upstage-zdr'):
            series = [plans[f'solar-decide-openrouter-{tag}-native-{p}-v1'] for p in ('p0', 'p1', 'p2')]
            for p0, p1, p2 in zip(*(m['requests'] for m in series)):
                parent = p0['payload']
                solar.verify_delta(parent, p1['payload'], 'P1')
                solar.verify_delta(parent, p2['payload'], 'P2')
                self.assertEqual(p0['p0_payload_sha256'], p0['payload_sha256'])
                self.assertEqual(p1['p0_payload_sha256'], p0['payload_sha256'])
                self.assertEqual(p2['p0_payload_sha256'], p0['payload_sha256'])
                for key in solar.KEYS:
                    self.assertEqual(p2['payload']['questions'][key]['instructions'],
                                     p1['payload']['questions'][key]['instructions'] + solar.variants.P2[key])

    def test_rejects_catalog_price_context_and_endpoint_choice_drift(self):
        path = self.root / solar.SNAPSHOT
        original = json.loads(path.read_text())
        for change in ('price', 'context', 'tag', 'interface'):
            catalog = deepcopy(original)
            endpoint = catalog['data']['endpoints'][0]
            if change == 'price':
                endpoint['pricing']['input_cache_read'] = '0.00000006'
            elif change == 'context':
                endpoint['context_length'] -= 1
            elif change == 'tag':
                endpoint['tag'] = 'other-provider'
            else:
                catalog['data']['architecture']['modality'] = 'text->text'
            path.write_text(json.dumps(catalog))
            with self.subTest(change=change), self.assertRaises(ValueError):
                solar.build_plans(self.root)

    def test_rejects_reference_labels_and_question_schema_change(self):
        path = self.root / 'data/pilot/inputs.jsonl'
        rows = [json.loads(x) for x in path.read_text().splitlines()]
        rows[0]['reference_label'] = 'positive'
        path.write_text(''.join(json.dumps(x) + '\n' for x in rows))
        with self.assertRaisesRegex(ValueError, 'Input must contain only'):
            solar.build_plans(self.root)
        parent = solar.p0_payload('feedback', 'policy', 'upstage')
        altered = deepcopy(parent)
        altered['questions']['sentiment']['criteria']['positive'] = 'tampered'
        with self.assertRaisesRegex(ValueError, 'more than Choice instructions'):
            solar.verify_delta(parent, altered, 'P0')
        altered['questions']['sentiment']['criteria']['extra_label'] = 'extra'
        with self.assertRaisesRegex(ValueError, 'schema or label order'):
            solar.check_payload(altered, 'feedback', 'policy', 'upstage')

    def test_suffix_source_drift_and_immutable_manifest_check(self):
        out = Path(self.temp.name) / 'out'
        hashes = solar.prepare(out, self.root)
        self.assertEqual(hashes, solar.verify(out, self.root))
        with self.assertRaisesRegex(ValueError, 'must be empty'):
            solar.prepare(out, self.root)
        path = out / 'solar-decide-openrouter-upstage-native-p2-v1.json'
        value = json.loads(path.read_text())
        value['requests'][0]['payload']['state']['feedback'] = 'tampered'
        path.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError, 'differs from frozen sources'):
            solar.verify(out, self.root)
        source = self.root / 'scripts/jev_native_prompt_variants_v1.py'
        source.write_bytes(source.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, 'suffix source changed'):
            solar.build_plans(self.root)


if __name__ == '__main__':
    unittest.main()
