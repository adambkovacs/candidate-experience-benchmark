"""Offline tests for recovered v2 P0 admission into v3 P1/P2."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import gemini_openrouter_recovered_parent_adapter_v1 as a

PARENT = ROOT / 'results/gemini-openrouter-prep-v2/p0-routing-probe/gemini38-low-p0/manifest.json'

class RecoveredParentAdapterTests(unittest.TestCase):
    def test_admission_is_input_only_and_exact60(self):
        calls = []
        original = a.read_rows
        def read(path):
            calls.append(str(path))
            return original(path)
        with mock.patch.object(a, 'read_rows', side_effect=read):
            manifest, bindings, attempts, records, journal = a.admitted_baseline(PARENT)
        self.assertEqual(len(attempts), 6)
        self.assertEqual(len(records), 60)
        self.assertEqual([r['id'] for r in records], [f'DEV-{i:03}' for i in range(1, 61)])
        self.assertEqual([r['status'] for r in records[:10]], ['ok'] * 10)
        self.assertEqual([r['original_status'] for r in records[:10]], ['identity_unverified'] * 10)
        self.assertEqual(journal[-1]['completed'], True)
        self.assertTrue(calls)
        self.assertTrue(all(p.endswith('/data/pilot/inputs.jsonl') for p in calls))
        self.assertNotIn('proposed_labels', json.dumps(bindings))

    def test_prepare_p1_p2_and_preflight_rechecks_admission(self):
        with tempfile.TemporaryDirectory(dir=ROOT / 'results') as temp:
            folder = Path(temp)
            admission_dir = folder / 'admission'
            with contextlib.redirect_stdout(io.StringIO()):
                a.admit(SimpleNamespace(parent_p0=str(PARENT), output_dir=str(admission_dir)))
            admission = admission_dir / 'recovered-p0-v1-admission.json'
            proof = a.validate_admission(admission)
            self.assertEqual(proof['total_records'], 60)
            for variant in ('P1', 'P2'):
                output = folder / variant.lower()
                with contextlib.redirect_stdout(io.StringIO()):
                    a.prepare(SimpleNamespace(variant=variant,
                        configuration_id=f'gemini38-low-{variant.lower()}-test', timeout=300,
                        output_dir=str(output), admission=str(admission)))
                path = output / 'manifest.json'
                m = json.loads(path.read_text())
                self.assertEqual(m['schema'], 'gemini-openrouter-batch-v3')
                self.assertEqual(m['parent_p0']['baseline_id'], 'gemini38-low-p0-openrouter-v2')
                self.assertEqual(m['parent_p0']['admission_proof']['sha256'], a.v3.sha(admission.read_bytes()))
                self.assertEqual(len(m['requests']), 7)
                self.assertEqual(m['requests'][0]['record_ids'], ['DEV-001','DEV-002','DEV-003'])
                self.assertEqual([len(r['record_ids']) for r in m['requests'][1:]], [10]*6)
                self.assertEqual(m['requests'], a.v3.prepared_requests(
                    a.PARENT_MODEL, a.PARENT_EFFORT, variant,
                    'gemini38-low-p0-openrouter-v2', a.v3.check_catalog(
                        a.PARENT_MODEL, a.PARENT_EFFORT,
                        json.loads((a.v3.PREP/'catalog.json').read_text()),
                        json.loads((a.v3.PREP/'gemini-3.8-flash-endpoints.json').read_text()))[1]))
                run_args = SimpleNamespace(manifest=str(path), manifest_sha256=a.v3.sha(path.read_bytes()),
                    phase='smoke', budget_manifest=str(folder/'budget.json'),
                    partition_id='fake', approval=str(folder/'receipt.json'),
                    smoke_inspection=None, env_file=None)
                with mock.patch.object(a.v3, 'run') as paid:
                    a.run(run_args)
                    paid.assert_called_once_with(run_args)
            # Altering reconciled evidence is rejected before the paid runner.
            records_path = admission_dir / 'recovered-p0-v1-records.jsonl'
            records_path.write_text(records_path.read_text() + '\n')
            with mock.patch.object(a.v3, 'run') as paid:
                with self.assertRaises(ValueError):
                    a.run(SimpleNamespace(manifest=str(folder/'p1'/'manifest.json')))
                paid.assert_not_called()

if __name__ == '__main__': unittest.main()
