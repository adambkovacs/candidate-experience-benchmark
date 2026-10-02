import json
from decimal import Decimal
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import mistral119_v3_second_suffix as stage


class SecondSuffixTests(unittest.TestCase):
    def test_predecessors_and_exact_unsent_requests(self):
        binding = stage.prior_gate()
        self.assertEqual(binding['failed_ids'], ['DEV-048', 'DEV-050'])
        self.assertEqual(binding['unsent_ids'], list(stage.IDS))
        manifest = stage.manifest_value()
        self.assertEqual([x['record_id'] for x in manifest['suffix_requests']],
                         list(stage.IDS))
        self.assertEqual(manifest['child_cap_usd'], '0.25')
        self.assertFalse(manifest['reference_labels_read'])
        self.assertEqual(manifest['source_sha256']['scripts/mistral119_v3_second_suffix.py'],
                         stage.smoke.sha(ROOT / 'scripts/mistral119_v3_second_suffix.py'))

    def test_previous_terminal_and_new_manifest_are_immutable(self):
        with patch.object(stage, 'PRIOR_TERMINAL_SHA', '0' * 64):
            with self.assertRaisesRegex(ValueError, 'terminal or billing'):
                stage.prior_gate()
        with tempfile.TemporaryDirectory() as directory:
            stage.prepare(directory)
            stage.verify(directory)
            path = Path(directory) / 'manifest.json'
            bad = json.loads(path.read_text())
            bad['suffix_requests'][0]['record_id'] = 'DEV-050'
            path.write_text(json.dumps(bad))
            with self.assertRaisesRegex(ValueError, 'drift'):
                stage.verify(directory)

    def test_receipt_binds_new_runner_gate_and_child(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'budget-manifest.json'
            path.write_text('{}')
            manifest = stage.manifest_value()
            digest = stage.smoke.digest_bytes(stage.smoke.canonical(manifest))
            gate = {'prior': stage.prior_gate()}
            receipt = stage.expected_receipt('fresh1', 'P0', 'suffix', manifest,
                                             digest, path, gate)
            self.assertEqual(receipt['ids'], list(stage.IDS))
            self.assertEqual(receipt['budget_partition_id'], stage.PID)
            self.assertEqual(receipt['child_cap_usd'], str(Decimal('0.25')))
            self.assertEqual(receipt['runner_sha256'], stage.smoke.sha(
                ROOT / 'scripts/mistral119_v3_second_suffix.py'))
            with self.assertRaisesRegex(ValueError, 'Only DEV-051'):
                stage.partition_id('fresh1', 'P1', 'suffix')

    def test_lifecycle_scope_and_patch_restoration(self):
        original = {name: getattr(stage.prior, name) for name in
                    ('SCHEMA', 'SUFFIX_BASE', 'verify_suffix', 'gate', 'partition_id',
                     'expected_receipt')}
        seen = []

        def lifecycle(repeat, condition, phase, receipt, budget, **kwargs):
            seen.append((repeat, condition, phase, receipt, budget, kwargs))
            self.assertEqual(stage.prior.SUFFIX_BASE, stage.BASE)
            self.assertEqual(stage.prior.partition_id(repeat, condition, phase), stage.PID)
            manifest, manifest_sha = stage.prior.verify_suffix()
            self.assertEqual(manifest['suffix_requests'][0]['record_id'], 'DEV-051')
            self.assertEqual(stage.prior.gate(repeat, condition, phase,
                                              manifest, manifest_sha)['prior']['failed_ids'],
                             ['DEV-048', 'DEV-050'])
            return 'delegated'

        with tempfile.TemporaryDirectory() as directory:
            stage.prepare(directory)
            original_verify = stage.verify
            with patch.object(stage, 'BASE', Path(directory)):
                with patch.object(stage, 'verify', side_effect=lambda: original_verify(directory)):
                    # The controller delegates the durable lifecycle; this test supplies no key.
                    with patch.object(stage.prior, 'run', side_effect=lifecycle):
                        self.assertEqual(stage.run('receipt', 'budget'), 'delegated')
        self.assertEqual(len(seen), 1)
        for name, value in original.items():
            self.assertIs(getattr(stage.prior, name), value)

    def test_no_receipt_prevents_claim_and_key_access(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            stage.prepare(base)
            budget = base / 'suffix.budget-manifest.json'
            budget.write_text('{}')
            original_verify = stage.verify
            with patch.object(stage, 'BASE', base), patch.object(
                    stage, 'verify', side_effect=lambda: original_verify(base)):
                with self.assertRaises(FileNotFoundError):
                    stage.run(base / 'suffix.root-review.json', budget,
                              live=lambda *_: self.fail('route called before receipt'),
                              open_child=lambda *_: self.fail('child opened before receipt'),
                              load_key=lambda *_: self.fail('key loaded before receipt'),
                              send=lambda *_: self.fail('request sent before receipt'))
            self.assertFalse((base / 'suffix.claim.json').exists())


if __name__ == '__main__':
    unittest.main()
